"""When a starting page presents and opens interaction: the first replay, controls that
wait for it, and the readable page a startup fault leaves."""

import itertools
import re

import pytest
from interact_support import append_carried_log_record, append_command, wait_for
from playwright.sync_api import expect
from render_cases_interaction import SHORT_SUGGESTION, SUGGESTION_PAGE, live_url
from render_cases_layout import SHADOWED_DIFF
from render_cases_navigation import FIRST_PRESENTATION, _publish
from render_cases_widgets import (
    CHART_PAGE,
    GENERIC_VISUAL_LAYER,
    GENERIC_VISUAL_PAGE,
    visual_widgets,
)
from render_harness import (
    LONG_PAGE,
    consume_browser_errors,
    expect_obligations_answered,
    expect_panel_offers,
    holding,
    leaf_page,
    open_page,
    open_threads,
    open_versions,
    page_comment,
    panel_field,
    panel_menu,
    panel_settled,
    panel_view,
    refuse,
    reported_browser_errors,
    selection_field,
    sending,
    watched,
    write,
)

from browser.threads import PANEL_REPLY, open_panel_thread
from leaf import event_log as events_model
from leaf.render_checks import asked_again, wait_until_ready
from leaf.render_gate.page_code import run_page_code
from leaf_dev.browser import PANEL_THREAD, open_on_me
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed

# The status the panel's empty field says while the first state answer is held.
LOADING = re.compile("^Loading comments and choices…")


VISUAL_ACTION_TIMING = """
  window.__lfVisualActionInsertions = [];
  new MutationObserver(records => {
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (!(node instanceof Element)) continue;
        const holders = [
          ...(node.matches('.lf-visual-actions') ? [node] : []),
          ...node.querySelectorAll('.lf-visual-actions'),
        ];
        for (const _holder of holders)
          window.__lfVisualActionInsertions.push(
            document.body?.hasAttribute('data-lf-upgraded') ?? false
          );
      }
    }
  }).observe(document, {childList: true, subtree: true});
"""


def test_refusing_the_storage_objects_does_not_block_startup(browser, serve):
    """Acquiring web storage can itself throw before any method is called.

    The stores' unavailable answer covers that outer browser boundary too, so a
    locked-down page loses only remembered view state and drafts, not the page.
    """
    page = open_page(
        browser,
        serve(SHORT_SUGGESTION),
        init_script="""
          for (const name of ['localStorage', 'sessionStorage'])
            Object.defineProperty(window, name, {
              configurable: true,
              get() { throw new DOMException('blocked', 'SecurityError'); },
            });
        """,
    )
    expect(page.locator("main")).to_be_visible()
    tab_store = page.evaluate(
        """async () => {
          const { tabStore } = await window.__lfWidgetApi();
          return {
            read: tabStore.read('refused'),
            wrote: tabStore.set('refused', '1'),
            keys: tabStore.keys(),
            where: tabStore.where('refused'),
            scope: document.documentElement.dataset.lfPageScope,
          };
        }"""
    )
    # A served page keeps its browser state under its own scope (`data-lf-page-scope`).
    scope = tab_store.pop("scope")
    assert tab_store == {
        "read": {"available": False, "value": None},
        "wrote": False,
        "keys": [],
        "where": {"store": "session", "key": f"{scope}refused"},
    }


def test_authored_page_paints_but_durable_controls_wait_for_first_replay(
    browser, serve
):
    """Paint readiness and semantic-interaction readiness are separate facts.

    The authored document is useful while the first state response is held: its text,
    link, structure, and generated interface in light and shadow DOM all paint after
    upgrade. A durable choice based on that not-yet-reconciled document cannot mutate or
    post. Releasing the response applies the decision in force and opens semantic
    interaction once."""
    url = serve(
        SHORT_SUGGESTION.replace(
            "<lf-old>",
            '<lf-old><a id="startup-link" href="#after">Continue reading</a>',
        ).replace(
            "</main>",
            """<lf-group id="startup-decision" label="Startup choice"><h2 id="startup-decision-h">Startup choice</h2>
<lf-options id="startup-choice">
  <lf-option id="startup-a">First</lf-option>
  <lf-option id="startup-b">Second</lf-option>
</lf-options></lf-group>
<lf-draft id="startup-note"><pre>Ship on Tuesday from the blue room.</pre></lf-draft>
"""
            + SHADOWED_DIFF,
        )
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "startup-note",
            "action": "edit",
            "detail": {"value": "Ship on Friday from the green room."},
        },
    )
    held = []
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    posts = []
    page.on(
        "request",
        lambda request: (
            posts.append(request.url) if "/api/event" in request.url else None
        ),
    )
    page.add_init_script(FIRST_PRESENTATION)
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(url, wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the first state response"
    choice = page.locator("#startup-choice .lf-pick").first
    expect(choice).to_have_attribute("aria-disabled", "true")
    expect(choice).to_be_visible()
    choice.dispatch_event("click")
    expect(page.locator("#startup-a")).not_to_have_attribute("selected", "")
    suggestion_accept = page.locator(
        "[data-lf-margin-for='sug'] [data-lf-margin-entry-key=accept]"
    )
    expect(suggestion_accept).to_be_disabled()
    assert suggestion_accept.evaluate(
        """button => lfUnwatched(() => {
              const glyph = button.firstElementChild;
              const widget = document.getElementById('sug');
              const parent = widget.parentNode;
              const next = widget.nextSibling;
              widget.remove();
              parent.insertBefore(widget, next);
              return button.firstElementChild === glyph;
            })"""
    ), "an unchanged availability paint rebuilt the suggestion control"
    suggestion_accept.dispatch_event("click")
    expect(suggestion_accept).to_be_disabled()
    assert posts == [], "a durable action posted before the first state projection"
    authored_note = page.locator("#startup-note .lf-draft-body")
    expect(authored_note).to_have_text("Ship on Tuesday from the blue room.")
    authored_note.select_text()
    # A script-selected passage offers the explicit route; only a completed native
    # selection gesture raises the adjacent field automatically.
    comment_selection = selection_field(page)
    expect(comment_selection).to_be_visible()
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    comment_selection.click()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    assert posts == [], "an anchored comment posted before the first state projection"
    page.keyboard.press("Escape")
    frames = page.evaluate("() => window.__lfPresentation.frames")
    assert frames and all(frame["height"] > 0 for frame in frames), (
        f"the authored state was never laid out: {frames}"
    )
    ready_frames = [frame for frame in frames if frame["upgraded"]]
    assert ready_frames, frames
    assert all(frame["authoredPainted"] for frame in ready_frames), (
        f"authored state did not paint while replay was pending: {frames}"
    )
    assert any(frame["authoredHit"] for frame in ready_frames), (
        f"the authored document never entered the hit-test tree: {frames}"
    )
    assert page.locator("#startup-link").evaluate(
        "element => { element.focus(); return document.activeElement === element; }"
    ), "an ordinary authored link was unavailable before replay"
    assert page.evaluate(
        "() => document.querySelector('#shadowed').shadowRoot.querySelector('pre')"
        ".checkVisibility({opacityProperty: true, visibilityProperty: true})"
    ), "ordinary authored shadow content did not paint before replay"
    assert page.evaluate(
        """() => {
              const ui = document.querySelector('#shadowed').shadowRoot
                .querySelector('.lf-ui');
              return ui?.checkVisibility({visibilityProperty: true});
            }"""
    ), "generated shadow interface remained withheld after upgrade"
    assert all(frame["startupSheet"] == "none" for frame in frames), frames

    held.pop(0).continue_()
    wait_until_ready(page)
    expect(page.locator("#sug")).to_have_attribute("data-lf-state", "accept")
    expect(authored_note).to_have_text("Ship on Friday from the green room.")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator("#sug lf-old")).to_be_hidden()
    expect(choice).to_have_attribute("aria-disabled", "false")
    expect(choice).to_be_visible()
    assert page.evaluate(
        """() => document.querySelector('#shadowed').shadowRoot
              .querySelector('.lf-ui').checkVisibility({visibilityProperty: true})"""
    ), "generated shadow interface remained withheld after replay"
    assert page.evaluate("() => window.__lfPresentation.releases") == 1


def test_playground_joins_initial_widget_settlement(browser, serve):
    """An optional package paints locally while its durable action still waits."""
    source = named_source("notification-playground")
    url = serve(source)
    held = []
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    watched(page)
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(url, wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the first state response"
    playground = page.locator("#notification-playground")
    expect(playground.locator(".lf-playground-controls-region > aside")).to_be_visible()
    expect(playground.locator(".lf-playground-presets")).to_be_visible()
    expect(playground.locator(".lf-playground-actions")).to_be_visible()
    submit = playground.get_by_role("button", name="Create notification")
    expect(submit).to_be_disabled()
    expect(panel_field(page)).to_have_attribute("placeholder", LOADING)

    playground.get_by_role("radio", name="Status strip", exact=True).check()
    playground.get_by_role("button", name="Needs attention").click()
    compact = playground.get_by_role("switch", name="Compact spacing")
    expect(compact).to_be_checked()
    expect(playground).to_have_attribute("data-playground-format", "status strip")

    held.pop(0).continue_()
    wait_until_ready(page)
    expect(submit).to_be_enabled()
    expect(compact).to_be_checked()
    expect(
        playground.get_by_role("radio", name="Status strip", exact=True)
    ).to_be_checked()
    expect(panel_field(page)).not_to_have_attribute("placeholder", LOADING)


def test_a_broken_optional_page_interface_does_not_withhold_presentation(
    browser, serve
):
    """Optional page surfaces fail independently rather than blanking every generated
    control. The failure is still reported, once."""
    source = leaf_page("broken optional interface", "<h1>Still a readable page</h1>")
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    page.add_init_script(
        """
        document.addEventListener('lf-page-interface', event => {
          event.detail.present(Promise.reject(new Error('optional sibling failed')));
        });
        """
    )
    page.goto(serve(source), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.get_by_role("heading", name="Still a readable page")).to_be_visible()
    errors = consume_browser_errors(page, "optional sibling failed")
    assert len(errors) == 1, errors


def test_on_me_claims_nothing_before_the_first_replay(browser, serve):
    """Chrome may not publish stale obligations before the log has answered.

    The log has accepted the page's one suggestion. Holding the first replay makes the
    dangerous interval deterministic: discussion stays available, but the leaf
    claims no count, and the stale bulk action stays withheld. Replay then paints the
    accepted state, counts nothing on the user and offers no Accept all."""
    url = serve(SHORT_SUGGESTION)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )
    held = []
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(url, wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the first state response"
    # The leaf stands on every page, and claims no count before the log has answered:
    # not the authored suggestion's 1, which the log has already decided.
    expect(page.locator(".lf-fp-leaf .lf-fp-badge")).to_have_text("")
    # The blanket answer claims no action before the first state answer.
    expect_panel_offers(page, "blanket:accept", offered=False)

    expect(page.locator(".lf-fp-leaf")).to_be_enabled()
    open_on_me(page)
    panel_settled(page, view="queue")
    # The page's field takes words while the first state answer is still held.
    expect(page_comment(page)).to_be_editable()
    page.keyboard.press("Escape")

    held.pop(0).continue_()
    wait_until_ready(page)
    expect(page.locator("#sug")).to_have_attribute("data-lf-state", "accept")
    # Nothing waits on the user, which the leaf says by counting nothing.
    expect(page.locator(".lf-fp-leaf .lf-fp-badge")).to_have_text("")
    expect_obligations_answered(page, "1/1")
    expect_panel_offers(page, "blanket:accept", offered=False)


def test_comments_wait_for_the_first_log_to_be_renderable(browser, serve):
    """Receiving state is not readiness while its message renderer is still loading."""
    url = serve(SHORT_SUGGESTION)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "text": "A preloaded **comment**",
        },
    )
    held = []
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    page.route("**/vendor/markdown-it.esm.js", lambda route: held.append(route))
    with page.expect_request("**/vendor/markdown-it.esm.js"):
        page.goto(url, wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the Markdown renderer"

    rows = page.locator(f"{panel_view('threads')} .lf-fp-thread")
    open_threads(page)
    expect(rows).to_have_count(0)

    held.pop(0).continue_()
    wait_until_ready(page)
    expect(rows).to_have_count(1)
    view = open_panel_thread(page, "c1")
    expect(view.locator(".lf-msg-body strong")).to_have_text("comment")


def test_an_unavailable_first_poll_releases_a_useful_page(browser, serve):
    """Presentation waits for an answer, not necessarily state.

    When the first poll cannot reach the server there is no log to apply, so the honest
    page is the authored one under an offline status. It must be visible rather than
    stranded behind the replay boundary, and the one failed answer releases it once."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    page.add_init_script(FIRST_PRESENTATION)
    page.route("**/api/state*", refuse)
    page.goto(serve(SHORT_SUGGESTION), wait_until="load")
    page.wait_for_function(
        "() => document.body.dataset.lfUpgraded === '1'"
        " && document.body.dataset.lfPresented === '1'"
    )
    expect(page.locator("main")).to_be_visible()
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile("^Lost the connection")
    )
    assert page.locator("body").get_attribute("data-lf-applied") is None
    assert page.evaluate("() => window.__lfPresentation.releases") == 1


def test_a_startup_failure_keeps_authored_page_readable(browser, serve):
    """A startup fault leaves useful HTML plus an error, not a blocking sheet."""
    url = serve(SHORT_SUGGESTION)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route(
        "**/registry.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body="{}"
        ),
    )
    with page.expect_console_message(
        predicate=lambda message: "page failed to start" in message.text
    ):
        page.goto(asked_again(url), wait_until="load")
    expect(page.get_by_role("status")).to_contain_text("Leaf couldn't start")
    expect(page.get_by_role("status")).to_be_visible()
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(page.locator("#sug lf-old")).to_be_visible()
    assert (
        page.evaluate("() => getComputedStyle(document.body, '::after').content")
        == "none"
    )
    # The deliberately empty registry has no $layer; unrelated startup failures
    # must still reach the browser fixture.
    reported_browser_errors(
        page,
        "page failed to start: Cannot read properties of undefined (reading 'generation')",
    )


def test_visual_comments_arrive_with_the_initialized_document(browser, serve):
    """A visual can accept a new comment while its saved history is loading."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held = []
    page.add_init_script(VISUAL_ACTION_TIMING)
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(serve(CHART_PAGE), wait_until="load")
    page.wait_for_function(
        "() => document.querySelectorAll('lf-chart.lf-rendered').length === 5"
    )
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(page.locator(".lf-visual-actions")).to_have_count(5)
    assert all(page.evaluate("() => window.__lfVisualActionInsertions"))

    assert held, "the first state read completed before the startup boundary was read"
    held.pop(0).continue_()
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator(".lf-visual-actions")).to_have_count(5)
    assert all(page.evaluate("() => window.__lfVisualActionInsertions"))


def test_invalid_visual_part_ids_report_the_package_error(browser, serve):
    """An invalid package inventory fails through the ordinary startup reporter."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    with page.expect_console_message(
        predicate=lambda message: "page failed to start" in message.text
    ):
        page.goto(
            serve(
                GENERIC_VISUAL_PAGE,
                layer_registry=GENERIC_VISUAL_LAYER,
                layer_widgets=visual_widgets(invalid_part_id=True),
            ),
            wait_until="load",
        )
    expect(panel_field(page)).to_have_attribute("placeholder", re.compile("reload"))
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    consume_browser_errors(page, "Visual part 1 has no single-token id")


def test_a_malformed_first_state_keeps_interaction_unresolved(browser, serve):
    """Malformed state leaves authored content readable but interaction unresolved."""
    url = serve(SHORT_SUGGESTION)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route(
        "**/api/state*",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body="not-json"
        ),
    )
    try:
        with page.expect_console_message(
            predicate=lambda message: "read failed" in message.text
        ):
            page.goto(url, wait_until="load")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        expect(panel_field(page)).to_have_attribute(
            "placeholder", re.compile("^Couldn't show the latest — reload")
        )
        expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
        expect(page.locator("body")).not_to_have_attribute("data-lf-applied", "1")
        expect(page.locator("#sug lf-old")).to_be_visible()
        # Versions is out of reach until state applies.
        expect(
            panel_menu(page).locator('.lf-fp-item[data-lf-row="versions"]')
        ).to_be_disabled()
        # No producer below the feed saw the body, so the feed's report is the one
        # that reaches the agent.
        wait_for(
            lambda: [
                event["text"].splitlines()[0]
                for event in events_model.read_events(serve.page_dir)
                if event["kind"] == "error"
            ],
            lambda errors: any(
                error.startswith("read failed: Unexpected token") for error in errors
            ),
            failure="the malformed state body never reached the log",
        )
    finally:
        page.close()
    # As above: the malformed answer is given to every read, and the page keeps
    # asking, so the list is settled by the page ending rather than by a wait.
    consume_browser_errors(page, "read failed: Unexpected token")


def answer_as_another_runtime(page):
    """The page's server restarted under another Leaf, as the tab sees it: its answers
    name another runtime until the tab's source has said so once, which is the reading
    the reload lands on."""
    restarted = {"answers": True}

    def another_runtime(route):
        if not restarted["answers"]:
            route.continue_()
            return
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={**response.headers, "Leaf-Runtime": "0123456789abcdef"},
        )
        if route.request.url.endswith("/registry.json"):
            restarted["answers"] = False

    page.route("**/api/**", another_runtime)
    page.route("**/registry.json", another_runtime)


def restart_under_another_runtime(page, serve, answer=None):
    """The tab reloading onto the runtime its restarted server runs
    (`answer_as_another_runtime`). `answer` makes the tab ask the server something, by
    default news of a comment. Returns once the reload has landed."""
    answer_as_another_runtime(page)
    with page.expect_navigation():
        if answer:
            answer()
        else:
            append_carried_log_record(
                serve.page_dir,
                {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
            )
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")


# The page interface of the first document an init script runs in, the one the first
# reload brings, never settles (`reload_twice`).
HOLD_SECOND_INTERFACE = """(() => {
  const loads = Number(sessionStorage.getItem("test-loads") || 0) + 1;
  sessionStorage.setItem("test-loads", String(loads));
  if (loads === 1)
    document.addEventListener("lf-page-interface", (event) =>
      event.detail.present(new Promise(() => {})),
    );
})()"""


def reload_twice(page, serve, between=None, slow=False):
    """Two reloads Leaf asks for in a row: the tab's server restarted under another
    Leaf (`answer_as_another_runtime`), and so did the server the document that reload
    brings first hears from, so that document reloads too, while its arrival still
    waits for its first answer and so before it has put the user back. `between` runs
    while that document waits. With `slow`, that document's page interface never
    settles (presentation.js, `settlePageInterface`), as a widget slow to upgrade holds
    it, so its anchoring is not yet ready as it goes. Returns once the second reload
    has landed."""
    if slow:
        page.add_init_script(HOLD_SECOND_INTERFACE)
    reloads = {"count": 0}
    replaced = {"documents": 0}
    hold = {"on": True}
    held = []

    def navigated(frame):
        if frame == page.main_frame:
            replaced["documents"] += 1

    def another_runtime(route):
        if reloads["count"] >= 2:
            route.continue_()
            return
        if hold["on"] and replaced["documents"] == 1 and reloads["count"] == 1:
            held.append(route)
            return
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={**response.headers, "Leaf-Runtime": "0123456789abcdef"},
        )
        if route.request.url.endswith("/registry.json"):
            reloads["count"] += 1

    page.on("framenavigated", navigated)
    page.route("**/api/**", another_runtime)
    page.route("**/registry.json", another_runtime)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    holding(page, held, 1, "the arriving document's first answer")
    page.wait_for_function("() => document.readyState !== 'loading'")
    if between:
        between()
    hold["on"] = False
    with page.expect_navigation(wait_until="commit"):
        while held:
            another_runtime(held.pop(0))
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    page.remove_listener("framenavigated", navigated)


def test_a_value_typed_into_the_page_rides_two_reloads_in_a_row(browser, serve):
    """A value the user typed into the page's own form comes back after two reloads
    Leaf asks for in a row, the second before the first's arrival has put it back,
    while something slow to upgrade still holds back that document's anchoring. The
    field asks the browser to keep no value of its own, so only Leaf's carry can."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Form</h1><p><label>Name <input id="who" autocomplete="off">'
            "</label></p>",
        )
    )
    page = open_page(browser, live_url(url))
    page.locator("#who").fill("Ada")
    reload_twice(page, serve, slow=True)
    expect(page.locator("#who")).to_have_value("Ada")


def test_words_typed_through_two_reloads_in_a_row_reach_the_reply(browser, serve):
    """Words the user types on as the tab reloads, into the reply box they were writing
    in, reach that box though a second reload Leaf asks for comes before the first
    document has put the box back, as typed words survive every path (SOUL.md)."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Rehearsal</h1><p id="result">The backfill copied 310 million rows.</p>',
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "id": "rows",
            "text": "Which rows?",
            "anchor": {"section": "result"},
        },
    )
    page = open_page(browser, live_url(url))
    page.locator('[data-lf-margin-for="result"] .lf-margin-marker').click()
    reply = page.locator(
        '.lf-margin-preview .lf-page-thread[data-lf-thread="rows"] '
        ".lf-thread-reply leaf-text"
    )
    write(reply, "Hold")
    reload_twice(page, serve, between=lambda: page.keyboard.type(" the resend"))
    expect(reply).to_have_js_property("value", "Hold the resend")


def test_a_tab_reloads_into_the_runtime_its_restarted_server_runs(browser, serve):
    """A server restarted under another Leaf runs another runtime, whose state the
    tab's code may misread. The tab refuses that server's answer, asks its source, and
    reloads onto the document the server now serves (`runtime_selection.py`)."""
    page = open_page(
        browser, serve(leaf_page("Restarted", "<h1>Readable authored content</h1>"))
    )
    page.evaluate("() => { window.lfSameDocument = true; }")
    restart_under_another_runtime(page, serve)
    assert page.evaluate("() => window.lfSameDocument") is None


# Where the user is writing a reply, and the page's address: its live root or a
# version's own.
@pytest.mark.parametrize(
    ("view", "address"),
    [("card", "live"), ("card", "version"), ("panel", "live")],
    ids=["card", "card-at-version", "panel"],
)
def test_a_reload_into_another_runtime_keeps_the_user_where_they_were(
    browser, serve, view, address
):
    """Leaf reloads the tab, not the user, so their place rides across the reload, as
    it does into a revision that needs a fresh document, in the entry's record
    (history.js) and the reload's handoff (version.js, `handOff`): the thread they had
    open, in the margin card or the floating panel they had it in, its reply box with
    the words they had selected, and a disclosure they opened. The
    handoff is spent on that reload, so an ordinary one after it keeps only what a
    reload keeps, such as the thread its address names, and not the disclosure."""
    version_url = serve(
        leaf_page(
            "Restarted",
            '<h1>Rehearsal</h1><p id="result">The backfill copied 310 million rows.</p>'
            '<details id="why"><summary>Why</summary><p>No errors.</p></details>',
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "id": "rows",
            "text": "Which rows?",
            "anchor": {"section": "result"},
        },
    )
    page = open_page(
        browser, live_url(version_url) if address == "live" else version_url
    )
    page.locator("#why > summary").click()
    if view == "card":
        page.locator('[data-lf-margin-for="result"] .lf-margin-marker').click()
        thread = page.locator(
            '.lf-margin-preview .lf-page-thread[data-lf-thread="rows"]'
        )
        reply = thread.locator(".lf-thread-reply leaf-text")
    else:
        thread = open_panel_thread(page, "rows")
        reply = page.locator(PANEL_REPLY)
    write(reply, "Hello there world")
    page.keyboard.press("Home")
    for _ in range(5):
        page.keyboard.press("ArrowRight")
    for _ in range(6):
        page.keyboard.press("Shift+ArrowRight")
    original_document = page.evaluate("performance.timeOrigin")

    restart_under_another_runtime(page, serve)

    assert page.evaluate("performance.timeOrigin") != original_document
    expect(thread).to_be_visible()
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Hello there world")
    assert reply.evaluate("box => [box.selectionStart, box.selectionEnd]") == [5, 11]
    expect(page.locator("#why")).to_have_js_property("open", True)

    page.reload()
    wait_until_ready(page)
    expect(page.locator("#why")).to_have_js_property("open", False)


def test_words_typed_as_the_server_restarts_go_with_the_reload_unasked(browser, serve):
    """The restarted server refuses the old tab's draft writes, so the words typed as it
    restarts wait in the tab. The reload Leaf then asks for carries them, with the
    caret, and puts no leave prompt in front of the user, which they would have to
    answer for a reload they never asked for (drafts.js, `beforeunload`)."""
    page = open_page(browser, serve(leaf_page("Restarted", "<h1>Rehearsal</h1>")))
    # A user who meets the prompt for a reload they never asked for stays, and the
    # tab is left on the server it can no longer read.
    prompts = []
    page.on("dialog", lambda dialog: (prompts.append(dialog.type), dialog.dismiss()))
    field = page.locator(".lf-fp-field leaf-text")
    write(field, "Hello")

    restart_under_another_runtime(
        page, serve, answer=lambda: page.keyboard.insert_text(" world")
    )

    assert prompts == []
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Hello world")
    assert field.evaluate("box => [box.selectionStart, box.selectionEnd]") == [11, 11]


def test_a_page_s_own_prompt_the_user_stays_at_leaves_leaf_asking_before_they_leave(
    browser, serve
):
    """Leaf's reload asks nothing, but a page's own leave prompt can keep the document,
    as when the user stays there. The next departure is the user's, so Leaf asks before
    it drops the words the restarted server refused (drafts.js, `beforeunload`)."""
    page = open_page(browser, serve(leaf_page("Restarted", "<h1>Rehearsal</h1>")))
    prompts = []
    page.on("dialog", lambda dialog: (prompts.append(dialog.type), dialog.dismiss()))
    page.evaluate(
        """() => {
          window.ownPrompt = (event) => { event.preventDefault(); event.returnValue = ""; };
          addEventListener("beforeunload", window.ownPrompt);
        }"""
    )
    field = page.locator(".lf-fp-field leaf-text")
    write(field, "Hello")
    answer_as_another_runtime(page)
    # The words are stranded once the server has refused their write; until then the
    # write carries them, and leaving asks nothing.
    with (
        page.expect_event("dialog"),
        page.expect_response(lambda response: response.url.endswith("/api/draft")),
    ):
        page.keyboard.insert_text(" world")
    page.evaluate('() => removeEventListener("beforeunload", window.ownPrompt)')
    # A reload of the user's own, which no Leaf code asks for.
    with page.expect_event("dialog"):
        page.evaluate("() => location.reload()")
    assert prompts == ["beforeunload", "beforeunload"]
    expect(field).to_have_js_property("value", "Hello world")


@pytest.mark.parametrize("view", ["threads", "queue"])
def test_a_reload_into_another_runtime_keeps_the_panel_s_list_open(
    browser, serve, view
):
    """The panel's lists are where the user is too: Threads, with the user on the row
    they were on, and On Me come back open across the reload, as the entry's record
    has them (history.js)."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Rehearsal</h1><p id="result">The backfill copied 310 million rows.</p>',
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "id": "rows",
            "text": "Which rows?",
            "anchor": {"section": "result"},
        },
    )
    page = open_page(browser, live_url(url))
    if view == "threads":
        open_threads(page)
        on = page.locator(f"{panel_view('threads')} .lf-fp-thread[data-lf-key]").first
        on.focus()
    else:
        on = open_on_me(page)
        on.focus()
    expect(on).to_be_focused()
    key = on.get_attribute("data-lf-key")

    restart_under_another_runtime(page, serve)

    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-lf-open", view)
    focused = page.locator(f"{panel_view(view)} :focus, {panel_view(view)}:focus")
    expect(focused).to_have_count(1)
    assert focused.get_attribute("data-lf-key") == key


# The box the user writes in (a card's reply, or a comment on a passage, which the page
# reopens on its own as it starts), the words it already holds, the first keys the
# reloaded page hears (a capital with its Shift, or a Space, which on another page still
# loading scrolls it), and whether single-key commands are on.
@pytest.mark.parametrize(
    ("box", "held", "first", "reads", "quick"),
    [
        ("card", "Hold ", ["Shift+T", "he resend"], "Hold The resend", True),
        ("card", "Hold", [" the resend"], "Hold the resend", True),
        ("comment", "Hold", [" the resend"], "Hold the resend", True),
        ("card", "Hold", [" the resend"], "Hold the resend", False),
    ],
    ids=["capital", "space", "comment", "single-keys-off"],
)
def test_keys_typed_through_the_reload_go_into_the_reply_it_hands_back(
    browser, serve, box, held, first, reads, quick
):
    """A user typing on as the tab reloads means the keys for the box they were
    writing in. Those the new document hears before it has handed the box back wait for
    it and go there, a capital's Shift and a Space included, and the keys after go on
    into it, rather than running the page's single-key commands, one of which resolves
    the thread (keyboard/bindings.js, `placeHandedBack`; bootstrap.js, `typingBack`).
    The new document's first state answer is held while the keys are typed, so they
    reach it before the hand-back however fast the machine is."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Rehearsal</h1><p id="result">The backfill copied 310 million rows.</p>',
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "id": "rows",
            "text": "Which rows?",
            "anchor": {"section": "result"},
        },
    )
    page = open_page(browser, live_url(url))
    if not quick:
        page.evaluate("() => window.lfKeyboard.setQuick(false)")
    if box == "card":
        page.locator('[data-lf-margin-for="result"] .lf-margin-marker').click()
        reply = page.locator(
            '.lf-margin-preview .lf-page-thread[data-lf-thread="rows"] '
            ".lf-thread-reply leaf-text"
        )
    else:
        page.locator("#result").click(modifiers=["Alt"])
        reply = page.locator(".lf-fab-input")
    write(reply, held)
    original_document = page.evaluate("performance.timeOrigin")
    replaced = {"document": False}
    answers = []

    def navigated(frame):
        if frame == page.main_frame:
            replaced["document"] = True

    def state_answer(route):
        if replaced["document"]:
            answers.append(route)
        else:
            route.fallback()

    answer_as_another_runtime(page)
    page.on("framenavigated", navigated)
    page.route("**/api/state*", state_answer)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    page.wait_for_function("() => document.readyState !== 'loading'")
    for keys in first:
        if keys.startswith("Shift+"):
            page.keyboard.press(keys)
        else:
            page.keyboard.type(keys)
    page.unroute("**/api/state*", state_answer)
    for route in answers:
        route.fallback()
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")

    assert page.evaluate("performance.timeOrigin") != original_document
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", reads)
    page.keyboard.type(" now")
    expect(reply).to_have_js_property("value", reads + " now")
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "resolve"
    ]


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_key_typed_through_the_reload_acts_where_the_user_is_put_back(
    request, serve, engine
):
    """A key the user presses on as the tab reloads acts in the thread view the reload
    puts them back in, as the entry's record has it (history.js): `r` resolves the
    thread they were on in the panel, not another, though the new document hears it
    before it has opened the view (keyboard/bindings.js, `placeHandedBack`), and the
    panel goes on to the next thread, as a resolve there does."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Rehearsal</h1><p id="result">The backfill copied 310 million rows.</p>'
            '<p id="cost">It cost four hours.</p>',
        )
    )
    for thread, section in [("rows", "result"), ("hours", "cost")]:
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "id": thread,
                "text": f"Why {section}?",
                "anchor": {"section": section},
            },
        )
    page = open_page(request.getfixturevalue(engine), live_url(url))
    open_panel_thread(page, "rows").focus()
    expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="rows"]')).to_be_focused()
    replaced = {"document": False}
    answers = []

    def navigated(frame):
        if frame == page.main_frame:
            replaced["document"] = True

    def state_answer(route):
        if replaced["document"]:
            answers.append(route)
        else:
            route.fallback()

    answer_as_another_runtime(page)
    page.on("framenavigated", navigated)
    page.route("**/api/state*", state_answer)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    page.wait_for_function("() => document.readyState !== 'loading'")
    page.keyboard.press("r")
    page.unroute("**/api/state*", state_answer)
    for route in answers:
        route.fallback()
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")

    resolved = wait_for(
        lambda: [
            event["parent"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "resolve"
        ],
        bool,
        failure="the key typed through the reload resolved no thread",
    )
    assert resolved == ["rows"]
    expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="hours"]')).to_be_focused()


def test_a_root_module_failure_leaves_authored_document_readable(browser, serve):
    """CSS never turns a broken root module into a blank or blocking page."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route(
        "**/leaf.js",
        lambda route: route.fulfill(
            status=200,
            content_type="text/javascript",
            body="throw new Error('root module failed')",
        ),
    )
    page.goto(serve(SHORT_SUGGESTION), wait_until="load")
    consume_browser_errors(page, "root module failed")
    expect(page.locator("main")).to_be_visible()
    expect(page.locator("h1")).to_have_text("Short")
    assert (
        page.evaluate("() => getComputedStyle(document.body, '::after').content")
        == "none"
    )


def test_the_first_startup_fault_names_the_page(browser, serve):
    """The first fault before upgrade names the page, and later faults leave the
    name alone: the first is the earliest evidence, and a later one is often its
    consequence. A later incomplete fault still gives back the readable fallback."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route(
        "**/leaf.js",
        lambda route: route.fulfill(
            status=200,
            content_type="text/javascript",
            body="for (const word of ['first fault', 'first fault', 'later fault'])"
            " setTimeout(() => { throw new Error(word); });"
            " setTimeout(() => { window.dispatchEvent(new CustomEvent("
            "'lf-startup-failed', { detail: { reason: 'declared fault' } }));"
            " window.faulted = true; });",
        ),
    )
    page.goto(asked_again(serve(SHORT_SUGGESTION)), wait_until="load")
    page.wait_for_function("() => window.faulted")
    root = page.locator("html")
    expect(root).to_have_attribute("data-lf-startup-error", re.compile("first fault"))
    assert root.evaluate("root => root.lfStartupException.message") == "first fault"
    expect(root).not_to_have_attribute("data-lf-interactive", "")
    reported_browser_errors(
        page, "Error: first fault", "Error: first fault", "Error: later fault"
    )


def test_a_boot_that_fails_after_it_waits_names_the_startup_fault(browser, serve):
    """The entry boots in an async function, which the bundler needs (leaf.js), and a
    failure after its first wait still reaches the window as an uncaught error, which
    names the page's startup fault. Its annotation renderer, the module the boot
    waits for, is refused here."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route(re.compile(r"annotation-overlay(/index)?\.js$"), refuse)
    page.goto(asked_again(serve(SHORT_SUGGESTION)), wait_until="load")
    root = page.locator("html")
    expect(root).to_have_attribute(
        "data-lf-startup-error", re.compile("dynamically imported module")
    )
    assert "annotation-overlay" in root.evaluate(
        "root => root.lfStartupException.message"
    )
    consume_browser_errors(page, "dynamically imported module")


def test_what_an_inline_classic_script_throws_reaches_the_check(browser, serve):
    """An inline classic script throws, and rejects, at once. Delivery holds it until
    the runtime has read the page and listens (`revision_delivery._deferred`), so
    plain `page check`, which hears what the runtime reports, names each with its
    throw site as it would a module's."""
    url = serve(
        leaf_page("Early fault", '<p id="words">Words.</p>').replace(
            "</main>",
            "</main><script>function parseTimeFault() {"
            " throw new TypeError('thrown while parsing'); }"
            " Promise.reject(new RangeError('rejected while parsing'));"
            " parseTimeFault();</script>",
        )
    )
    reports = [
        finding.values["text"]
        for finding in run_page_code(browser.unwatched, url)
        if finding.code == "page-report"
    ]
    assert any(
        "TypeError: thrown while parsing" in text and "parseTimeFault" in text
        for text in reports
    ), reports
    assert any("RangeError: rejected while parsing" in text for text in reports), (
        reports
    )


def test_a_page_the_suite_opens_has_read_the_log(browser, serve):
    """`open_page` promises a page that has finished becoming itself, and the log is half
    of what that means. The instrument is a refusal of the first `/api/state`. Replay then
    lands on the 2s retry, past the document's stamp, which is where a loaded Linux runner
    put it — so this press meets the same page those runs handed the test above, on any
    machine and in a second.

    Only a press can state it. A read lives through the interval, since `expect` re-decisions
    for five seconds and the retry lands in two; a keystroke into a page that has no
    versions yet is gone, and the picker never opens."""
    url = serve(LONG_PAGE)
    _publish(
        serve.page_dir,
        2,
        LONG_PAGE.replace("Paragraph 3.", "Paragraph three."),
        "reworded a paragraph",
    )
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, color_scheme="light"
    )
    polls = itertools.count()
    context.route(
        "**/api/state*",
        lambda route: refuse(route) if next(polls) == 0 else route.continue_(),
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"), context=context)
    open_versions(page)
    expect(page.locator(panel_view("versions"))).to_be_visible()


def test_unavailable_optional_user_view_checks_create_no_agent_work(browser, serve):
    """Optional view checks cannot turn a failed module request into page debt."""
    page = browser.new_page()
    page.route("**/checks/view.js", refuse)
    with page.expect_event(
        "requestfailed",
        predicate=lambda request: request.url.endswith("/checks/view.js"),
    ):
        page.goto(serve(SUGGESTION_PAGE), wait_until="load")
    wait_until_ready(page)
    with sending(page, "the suggestion decision"):
        page.locator(
            "[data-lf-margin-for='sug-refill'] [data-lf-margin-entry-key=accept]"
        ).click()
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "error"
    ]
    assert not page.lf_errors


def test_a_firefox_departure_reports_none_of_the_loads_it_aborts(
    firefox_browser, serve
):
    """Firefox aborts a document's loads as a navigation lets it go, and keeps the
    document running until the destination answers (prepaint.js, the document's
    lifetime). A widget module that fails that way is the departure's, not a startup
    fault the page reports or posts to the log."""
    page = firefox_browser.new_page()
    # Neither request is answered: the module stays in flight, and the departing
    # document stays shown and running while its destination is awaited.
    for held in ("**/widgets/lf-options.js", "**/elsewhere"):
        page.route(held, lambda route: None)
    with page.expect_request("**/widgets/lf-options.js"):
        page.goto(
            serve(
                leaf_page(
                    "Departing",
                    '<lf-group id="ship-q" label="When?">'
                    '<lf-options id="ship"><lf-option id="now">Now</lf-option>'
                    '<lf-option id="later">Later</lf-option></lf-options></lf-group>',
                )
            ),
            wait_until="commit",
        )
    with page.expect_event(
        "requestfailed",
        predicate=lambda request: request.url.endswith("/widgets/lf-options.js"),
    ):
        page.evaluate("location.href = 'elsewhere'")
    # The import's rejection settles startup within the task that delivers it.
    page.evaluate("() => new Promise(done => setTimeout(() => setTimeout(done)))")
    assert page.evaluate("document.documentElement.dataset.lfStartupError") is None
    assert not page.lf_errors
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "error"
    ]
