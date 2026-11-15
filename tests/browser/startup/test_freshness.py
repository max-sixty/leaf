"""How a page keeps its state current: freshness reads, hidden pages, coalesced
state reads and what ends one, offline authored state and recovery, and reloads."""

import re
from urllib.parse import urlparse

import pytest
from interact_support import (
    append_carried_log_record,
    append_command,
    declare_work,
)
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    LONG_PAGE,
    _traffic,
    consume_browser_errors,
    expect_preview_words,
    holding,
    http_error_console,
    leaf_page,
    nudge,
    open_page,
    open_threads,
    panel_field,
    refuse,
    told,
    watched,
    write,
)

from leaf import render_checks as render_checks_model
from leaf.leases import release_lease, take_wait_lease, waiter_lease_path

pytestmark = pytest.mark.shifts_unsurveyed

# The status the panel's empty field says while the server does not answer.
OFFLINE = re.compile(r"^Lost the connection")


# Counts, in the page, each freshness look and each state read it asks, so a count is
# current when an ordered event has come and gone: Playwright hands a request or a
# route to Python on its own schedule, after the page's call.
COUNT_ASKS = """
window.__lfAsked = {news: 0, state: 0};
const nativeFetch = window.fetch.bind(window);
window.fetch = (...args) => {
  const url = String(args[0] instanceof Request ? args[0].url : args[0]);
  if (url.includes("api/news")) window.__lfAsked.news += 1;
  else if (url.includes("api/state")) window.__lfAsked.state += 1;
  return nativeFetch(...args);
};
"""


def looked_since(page):
    """Wait until the page has handled a freshness look asked after this call.

    The page asks each look only once it has handled the one before, so the second look
    asked after this call starts once the first has been handled."""
    since = page.evaluate("window.__lfAsked.news")
    page.wait_for_function("since => window.__lfAsked.news >= since + 2", arg=since)


# The page's shared clock (`TICK_MS` in runtime/state-feed.js), which asks again after a
# failed read and otherwise only repaints.
TICK_MS = 2000


def ran_its_clock(page):
    """Wait until the page's shared clock has come round, and every look it had due.

    A timer the page sets now, for longer than one round of the clock, fires after each
    timer that falls due before it, since the page runs its timers in deadline order:
    the clock's next round and any freshness look still scheduled come first, however
    slowly the machine runs them."""
    page.evaluate(
        "ms => new Promise(resolve => setTimeout(resolve, ms))", TICK_MS + 500
    )


def test_a_quiet_page_reads_only_freshness_and_hears_changes(browser, serve):
    """Quiet freshness looks do not rebuild state; an external append does."""
    page = open_page(browser, serve(LONG_PAGE), init_script=COUNT_ASKS)
    open_threads(page)
    asked = _traffic(page).asked
    # A round of the clock, and a look handled after it.
    ran_its_clock(page)
    looked_since(page)
    assert _traffic(page).asked == asked, "a quiet page asked for state on a timer"

    append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "News."},
    )
    told(page)
    assert _traffic(page).asked == asked + 1
    notice = page.locator(".lf-fp-joined .lf-thread-news")
    expect_preview_words(notice, "1 new thread")
    notice.click()
    expect(page.locator(".lf-fp-thread", has_text="News.")).to_have_count(1)


def test_a_durable_server_restart_keeps_the_current_editor(browser, serve):
    """The process may change while this page's document and log still stand."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Durable draft",
                '<h1>Durable draft</h1><lf-draft id="draft"><pre>Original</pre></lf-draft>',
            )
        ),
        init_script=COUNT_ASKS,
    )
    page.locator("#draft .lf-draft-body").dblclick()
    editor = page.locator("#draft leaf-text")
    write(editor, "An unfinished durable draft")
    editor.press("Home")
    editor.press("Shift+ArrowRight")
    editor.press("Shift+ArrowRight")
    before = editor.evaluate(
        "el=>[el.selectionStart,el.selectionEnd,el.selectionDirection]"
    )
    page.evaluate("window.__originalDocument = true")
    reading = page.locator("body").get_attribute("data-lf-reading")
    # A poll already in flight can finish after the route is registered without
    # passing through it. Read the response that actually identifies the new server.
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/news")
            and response.headers.get("leaf-server") == "replacement-server"
        ),
    ) as restarted:
        serve.httpd.server_id = "replacement-server"
    assert restarted.value.text() == reading
    # The page asks its next look only once it has handled the one that heard the new
    # server, so a reload it decided on is under way by then; a document it reloaded
    # into ends the wait at once.
    since = page.evaluate("window.__lfAsked.news")
    page.wait_for_function(
        "since => !window.__originalDocument || window.__lfAsked.news >= since + 2",
        arg=since,
    )
    assert page.evaluate("window.__originalDocument === true")
    expect(editor).to_be_focused()
    assert (
        editor.evaluate("el=>[el.selectionStart,el.selectionEnd,el.selectionDirection]")
        == before
    )
    expect(editor).to_have_js_property("value", "An unfinished durable draft")


def test_a_hidden_page_stops_its_freshness_reads_until_it_is_visible(browser, serve):
    """Hidden documents stop attention checks; visibility immediately catches up.

    The overridden platform reading is the lifecycle input Chromium's headless
    shell cannot otherwise produce: all its tabs report visible.
    """
    page = open_page(browser, serve(LONG_PAGE), init_script=COUNT_ASKS)
    asked = _traffic(page).asked

    looks = page.evaluate(
        """() => {
          window.__lfTestVisibility = 'hidden';
          Object.defineProperty(document, 'visibilityState', {
            configurable: true,
            get: () => window.__lfTestVisibility,
          });
          document.dispatchEvent(new Event('visibilitychange'));
          return window.__lfAsked.news;
        }"""
    )
    # Once a canceled request has drained, news arrives while the tab is hidden.
    page.wait_for_timeout(100)
    append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "While away."},
    )
    # A look the page failed to cancel was due before the clock's next round, which
    # would also ask for the news it missed.
    ran_its_clock(page)
    assert page.evaluate("window.__lfAsked.news") == looks, (
        "a hidden page still looked for news"
    )
    assert _traffic(page).asked == asked, "a hidden page still polled for state"

    with page.expect_request("**/api/news"):
        page.evaluate(
            """() => {
              window.__lfTestVisibility = 'visible';
              document.dispatchEvent(new Event('visibilitychange'));
            }"""
        )
    told(page)
    assert _traffic(page).asked == asked + 1
    open_threads(page)
    expect(page.locator(".lf-fp-thread", has_text="While away.")).to_have_count(1)


def test_a_presence_read_crossing_freshness_returns_to_the_current_lease(
    browser, serve
):
    """A short-lived real wait lease inside a state read cannot strand its answer.

    The state read sees the lease held, and once it is released the page comes back
    to the current lease. This page is unclaimed, so its wait lease is a file in the
    page directory: taking it moves the news token, and the look asks again.
    """
    url = live_url(serve(LONG_PAGE))
    lease_path = waiter_lease_path(serve.page_dir, None)
    assert lease_path is not None
    with take_wait_lease(lease_path) as lease:
        page = open_page(browser, url)
        runtime = page.evaluate_handle("""async () =>
          (await window.__lfCheckApi()).readApplication""")
        assert runtime.evaluate("read => read().authoritative.listening") is True
        # Let the freshness reader observe the original held lease too.
        page.wait_for_timeout(700)
        crossed = []

        def crossing(route):
            if urlparse(route.request.url).path != "/api/state" or crossed:
                route.continue_()
                return
            assert lease_path is not None
            # Ask for a whole answer, which says whether the lease was held, rather
            # than a patch from the reading the tab holds (`served_state.tail`).
            headers = {
                name: value
                for name, value in route.request.headers.items()
                if name != "leaf-held-basis"
            }
            with take_wait_lease(lease_path):
                response = route.fetch(headers=headers)
                assert response.json()["listening"] is True
            crossed.append(response.json()["reading"])
            route.fulfill(response=response)

        page.route("**/api/state*", crossing)
        release_lease(lease)
        page.wait_for_function(
            "read => read().authoritative.listening === false", arg=runtime
        )
        assert crossed, "the state read did not cross the temporary lease"
        told(page)
        page.unroute_all(behavior="wait")


def test_status_changes_coalesce_behind_one_state_read(browser, serve):
    """Rapid starts do not build a queue of state requests.

    Freshness looks may announce several new readings while the container is still
    answering one. They collapse into one trailing read, which takes the newest state.
    """
    page = open_page(browser, serve(LONG_PAGE), init_script=COUNT_ASKS)
    d = serve.page_dir
    status = panel_field(page)

    def declare(detail):
        declare_work(d, detail)

    def reads():
        return page.evaluate("window.__lfAsked.state")

    # The state reads the page has asked so far, the startup read among them.
    before = reads()
    # Every ask is held; the test answers each admitted read by hand.
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    with page.expect_request("**/api/state*"):
        declare("first")
    while not held:
        page.wait_for_timeout(20)
    first = held[0]
    # An answer taken before the writes the looks hear next.
    older = first.fetch().json()
    declare("second")
    declare("third")
    looked_since(page)
    assert reads() == before + 1

    # The news the answer doesn't name earns exactly one follow-up read, not one read
    # per status write.
    with page.expect_request("**/api/state*"):
        first.fulfill(json=older)
    while len(held) < 2:
        page.wait_for_timeout(20)

    # That read takes the latest file state, so the page has nothing left to ask for.
    trailing = held[1]
    trailing.fulfill(json=trailing.fetch().json())
    expect(status).to_have_attribute("placeholder", re.compile(r"third"))
    looked_since(page)
    assert reads() == before + 2


def test_a_state_read_timing_out_during_its_body_is_offline(browser, serve):
    delay_state_body_past_deadline = """
      const nativeFetch = window.fetch.bind(window);
      window.fetch = async (...args) => {
        const input = args[0];
        const url = typeof input === 'string' ? input : input.url;
        if (new URL(url, location.href).pathname !== '/api/state')
          return nativeFetch(...args);
        const response = await nativeFetch(...args);
        return {
          ok: response.ok,
          headers: response.headers,
          text: async () => { throw new DOMException('timed out', 'TimeoutError'); },
        };
      };
    """
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    page.add_init_script(delay_state_body_past_deadline)
    page.goto(live_url(serve(LONG_PAGE)), wait_until="load")
    expect(panel_field(page)).to_have_attribute("placeholder", OFFLINE)


# Takes every bound the page sets on a request into the test's hands, so none ends a
# request on its own, and keeps the bound each state read was given: the page sets a
# read's bound just before it asks. `__lfOutlast(ms)` ends, as the browser ends an
# expired one, each state read's bound that a read lasting `ms` would have passed, and
# returns those bounds.
HELD_BOUNDS = """
window.__lfBounds = {last: null, reads: []};
Object.defineProperty(AbortSignal, 'timeout', {
  value: (ms) => {
    const controller = new AbortController();
    window.__lfBounds.last = {ms, controller};
    return controller.signal;
  },
});
const boundedFetch = window.fetch.bind(window);
window.fetch = (...args) => {
  const url = String(args[0] instanceof Request ? args[0].url : args[0]);
  if (url.includes("api/state")) window.__lfBounds.reads.push(window.__lfBounds.last);
  return boundedFetch(...args);
};
window.__lfOutlast = (ms) => window.__lfBounds.reads
  .filter((bound) => bound.ms <= ms && !bound.controller.signal.aborted)
  .map((bound) => {
    bound.controller.abort(new DOMException("signal timed out", "TimeoutError"));
    return bound.ms;
  });
"""


def test_a_state_read_waits_while_news_answers_and_ends_when_a_look_fails(
    browser, serve
):
    """A state read waits for its answer while the server answers the page's news
    looks, and ends as offline once a look goes unanswered.

    `publish-site` deployed release `5b6be522…`, ran a hosted agent turn on it, and
    then read the reloaded page still on the revision from before the turn. A
    container that has just run a turn answers its next state read in seconds rather
    than milliseconds — measured against a live deployment at 123 ms before a turn and
    2252-3918 ms after one. A bound inside that spread does not delay such a read, it
    ends it: an expiry is a completed offline answer, so the page takes the container
    for gone while the answer it asked for is still on its way. A slow container still
    answers news, so the looks, not a deadline on the read, say when the server is gone.
    """
    page = open_page(browser, serve(LONG_PAGE), init_script=COUNT_ASKS + HELD_BOUNDS)
    open_threads(page)
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Slow."},
    )
    holding(page, held, 1, "the read the news asked for")
    # A read ten times as slow as the slowest the deployment answered.
    assert page.evaluate("ms => window.__lfOutlast(ms)", 40_000) == [], (
        "a read the server was still answering ended on time"
    )
    looked_since(page)
    held[0].continue_()
    notice = page.locator(".lf-fp-joined .lf-thread-news")
    expect_preview_words(notice, "1 new thread")

    append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Gone."},
    )
    holding(page, held, 2, "the read the next news asked for")
    page.route("**/api/news*", refuse)
    expect(panel_field(page)).to_have_attribute("placeholder", OFFLINE)
    page.unroute_all(behavior="ignoreErrors")


def test_a_widget_presents_its_authored_state_offline_and_the_log_on_recovery(
    browser, serve
):
    """A first read that fails presents each widget at its authored state, and the
    read that recovers draws the choice the log holds."""
    url = serve(
        leaf_page(
            "Offline choice",
            '<h1>Offline choice</h1><lf-ask id="ask"><h2>Which?</h2>'
            '<lf-options id="options" choose><lf-option id="one">First</lf-option>'
            '<lf-option id="two">Second</lf-option></lf-options></lf-ask>',
        )
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "options",
            "action": "choose",
            "detail": {"value": ["two"]},
        },
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route("**/api/state*", refuse)
    page.goto(url, wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(panel_field(page)).to_have_attribute("placeholder", OFFLINE)
    expect(page.locator("#options .lf-pick")).to_have_count(2)
    expect(page.locator("#two")).not_to_have_attribute("chosen", "")
    page.unroute("**/api/state*")
    told(page)
    expect(page.locator("#two")).to_have_attribute("chosen", "")


def test_a_widget_draws_its_authored_state_while_its_first_read_waits(browser, serve):
    """Before the first state read answers, a widget's reading is its authored state,
    whole, so it draws that rather than nothing or a guess; the read draws the log's
    choice."""
    url = serve(
        leaf_page(
            "Waiting choice",
            '<h1>Waiting choice</h1><lf-ask id="ask"><h2>Which?</h2>'
            '<lf-options id="options" choose><lf-option id="one">First</lf-option>'
            '<lf-option id="two">Second</lf-option></lf-options></lf-ask>',
        )
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "options",
            "action": "choose",
            "detail": {"value": ["two"]},
        },
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(url, wait_until="load")
    holding(page, held, 1, "the first state read")
    waiting = page.evaluate(
        """async () => {
          const {widgetController} = await window.__lfWidgetApi();
          const options = document.querySelector('#options');
          await options.updateComplete;
          const {state} = widgetController(options).read();
          return {
            verbs: Object.keys(state).sort(),
            chosen: state.choose.value,
            drawn: [...options.querySelectorAll('lf-option[chosen]')].map((o) => o.id),
          };
        }"""
    )
    assert waiting == {"verbs": ["add", "answer", "choose"], "chosen": [], "drawn": []}
    page.unroute("**/api/state*")
    for route in held:
        route.continue_()
    told(page)
    expect(page.locator("#two")).to_have_attribute("chosen", "")


def test_a_pending_offline_paint_does_not_block_a_recovery_read(browser, serve):
    """The network slot ends with the read, not an unbounded package repaint."""
    page = open_page(browser, serve(LONG_PAGE))
    page.evaluate(
        """async () => {
          const {LeafElement, noChange, clockValue} = await window.__lfWidgetApi();
          window.probeVersion = 0;
          window.probePaints = 0;
          customElements.define('lf-pending-paint', class extends LeafElement {
            render() {
              clockValue(() => window.probeVersion);
              window.probePaints += 1;
              return noChange;
            }
            // A drawing that never finishes.
            getUpdateComplete() {
              return new Promise(() => {});
            }
          });
          const probe = document.createElement('lf-pending-paint');
          document.body.append(probe);
          await new Promise((resolve) => setTimeout(resolve));
          window.probeVersion = 1;
        }"""
    )
    page.route("**/api/state*", lambda route: route.fulfill(status=503, body=""))
    nudge(serve.page_dir)
    expect(panel_field(page)).to_have_attribute("placeholder", OFFLINE)
    page.wait_for_function("() => window.probePaints >= 2")

    page.unroute("**/api/state*")
    with page.expect_request("**/api/state*"):
        nudge(serve.page_dir)
    told(page)
    expect(panel_field(page)).not_to_have_attribute("placeholder", OFFLINE)
    consume_browser_errors(page, http_error_console(503))


def test_a_page_whose_read_failed_asks_again_on_its_own(browser, serve):
    """A wake-up the page could not act on is not lost. A freshness answer says when the
    page has moved wakes state once per changed reading, so a read that failed — refused here, a
    dropped request in the world — is asked again on the page's own tick, the
    spacing a failed exchange has always had. Without that a page would sit under
    an offline status until something else happened to it."""
    page = open_page(browser, serve(LONG_PAGE), init_script=COUNT_ASKS)
    open_threads(page)
    page.route("**/api/state*", refuse)
    with page.expect_event(
        "requestfailed", predicate=lambda request: "/api/state" in request.url
    ):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Missed."},
        )
    expect(panel_field(page)).to_have_attribute("placeholder", OFFLINE)
    # A failed answer does not turn every unchanged freshness look into another
    # expensive state read: over eight looks the page asks at most once for each round
    # of its clock, by the page's own time, and once more for a round under way.
    asked, began = page.evaluate("[window.__lfAsked.state, performance.now()]")
    for _ in range(4):
        looked_since(page)
    reads, ended = page.evaluate("[window.__lfAsked.state, performance.now()]")
    assert reads - asked <= (ended - began) // TICK_MS + 1
    page.unroute("**/api/state*")
    told(page)
    notice = page.locator(".lf-fp-joined .lf-thread-news")
    expect_preview_words(notice, "1 new thread")
    notice.click()
    expect(page.locator(".lf-fp-thread", has_text="Missed.")).to_have_count(1)
    expect(panel_field(page)).not_to_have_attribute("placeholder", OFFLINE)


def test_a_page_asks_its_source_before_reloading_onto_the_same_document(browser, serve):
    """A reload is only an answer when the document would come back different.

    The page refuses an answer from another layer because it cannot read that state, and
    it used to reload on the spot. That is right when re-vendoring has moved the page out
    from under an open tab. It is wrong the other way around — a server behind the
    document it served, which is what the website looks like while a release's containers
    are still starting — because the reload lands on the same document and the next answer
    says the same thing, so the user watches the page restart for as long as the
    disagreement lasts. The source of documents is the one party that can tell the two
    apart, so the page asks it and then holds still: the answers stay refused, the
    authored page stays readable, and the feed keeps asking until the server is back on
    this delivery.

    Each refused answer gets its own reading, because the source can move while the page
    waits — this page can be re-vendored during the hold. A page that asked once and
    remembered the answer would spend the rest of the tab's life refusing state with no
    way back.
    """
    page = open_page(browser, serve(LONG_PAGE))
    page.evaluate("() => { window.lfSameDocument = true; }")
    reads = []
    probes = []

    # The layer is read before the body is, so a foreign answer needs no state in it.
    def foreign(route):
        reads.append(route)
        route.fulfill(
            status=200,
            headers={"Content-Type": "application/json", "Leaf-Layer": "another-layer"},
            body="{}",
        )

    # The source stands still until the test moves it, and then says so once, because a
    # re-vendor rewrites the page directory the reload goes on to be served from.
    moved = {"pending": False}

    def source(route):
        probes.append(route)
        if not moved["pending"]:
            route.continue_()
            return
        moved["pending"] = False
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={**response.headers, "Leaf-Layer": "re-vendored"},
        )

    def wake(text):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": text},
        )

    page.route("**/registry.json", source)
    page.route("**/api/state", foreign)
    try:
        for index in range(3):
            wake(f"Note {index}.")
            holding(page, reads, index + 1, "the reads the news woke")
            if index == 0:
                expect(panel_field(page)).to_have_attribute(
                    "placeholder",
                    re.compile("^Waiting for Leaf to finish updating."),
                )
        assert page.evaluate("() => window.lfSameDocument === true"), (
            "the page reloaded onto the document it was already being served"
        )
        # The ask leaves the page a beat before the route records it, so the count is
        # read behind its own wait rather than behind the reads that caused it.
        holding(page, probes, len(reads), "the asks the refusals made of the source")
        assert len(probes) == len(reads), (
            "one refusal asked the source more than once: "
            f"{len(probes)} asks over {len(reads)} answers"
        )

        moved["pending"] = True
        wake("The source moved.")
        page.wait_for_function(
            "() => window.lfSameDocument === undefined",
            timeout=render_checks_model.HANDOVER_DEADLINE_MS,
        )
    finally:
        page.unroute("**/api/state", foreign)
        page.unroute("**/registry.json", source)
