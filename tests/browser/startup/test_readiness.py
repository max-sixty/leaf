"""When a starting page presents and opens interaction: the first replay, controls that
wait for it, and the readable page a startup fault leaves."""

import itertools
import json
import re
from urllib.parse import urlsplit

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
    example_media,
    expect_obligations_answered,
    expect_panel_offers,
    expect_panel_says,
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
    take_browser_errors,
    told,
    wait_for_check_api,
    watched,
    write,
)

from browser.threads import PANEL_REPLY, open_panel_thread, paste_image
from leaf.log import event_log as events_model
from leaf.pages.render_gate.page_code import run_page_code
from leaf.serving import drafts as drafts_model
from leaf.source.render_checks import asked_again, wait_until_ready
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
            "answered": True,
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
    field = page_comment(page)
    page.keyboard.type("x")
    expect(field).to_have_js_property("value", "x")
    page.keyboard.press("Backspace")
    expect(field).to_have_js_property("value", "")
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


# The page interfaces of the documents the reloads bring, numbered from the first
# reload's, that never settle (`reload_in_a_row`).
HOLD_INTERFACES = """((held) => {
  const loads = Number(sessionStorage.getItem("test-loads") || 0) + 1;
  sessionStorage.setItem("test-loads", String(loads));
  if (held.includes(loads))
    document.addEventListener("lf-page-interface", (event) =>
      event.detail.present(new Promise(() => {})),
    );
})(%s)"""


def reload_in_a_row(page, serve, waits, slow=()):
    """Reloads Leaf asks for in a row: the tab's server restarted under another Leaf
    (`answer_as_another_runtime`), and so did the server each of the documents the
    first reloads bring first hears from, so each reloads too, while its arrival still
    waits for its first answer and so before it has put the user back. `waits` runs
    one step in each of those documents while it waits, so there is one reload more
    than steps. `slow` numbers those documents, from 1, whose page interface never
    settles (readings/presentation.js, `settlePageInterface`), as a widget slow to upgrade holds
    it, so their anchoring is not yet ready as they go. Returns once the last reload
    has landed."""
    if slow:
        page.add_init_script(HOLD_INTERFACES % json.dumps(list(slow)))
    reloads = {"count": 0}
    replaced = {"documents": 0}
    # The answers each document the reloads bring asks for, by its number from 1, held
    # until it has taken its step; from then on its answers go out as it asks.
    held = {}
    released = {"through": 0}

    # Each reload asks for a new document; a rename of the entry the page makes is no
    # new document.
    def navigated(request):
        if request.is_navigation_request() and request.frame == page.main_frame:
            replaced["documents"] += 1

    def answer(route):
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={**response.headers, "Leaf-Runtime": "0123456789abcdef"},
        )

    # A document's probe of its source, the registry at the server's root, settles
    # that the runtime moved on, and the document reloads; every other answer to a
    # document still to take a step waits, its own layer's registry among them.
    def another_runtime(route):
        if reloads["count"] > len(waits):
            route.continue_()
            return
        if urlsplit(route.request.url).path == "/registry.json":
            answer(route)
            reloads["count"] += 1
        elif released["through"] < replaced["documents"] == reloads["count"]:
            held.setdefault(replaced["documents"], []).append(route)
        else:
            answer(route)

    page.on("request", navigated)
    page.route("**/api/**", another_runtime)
    page.route("**/registry.json", another_runtime)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    for document, wait in enumerate(waits, start=1):
        waiting = held.setdefault(document, [])
        holding(page, waiting, 1, "the arriving document's first answer")
        page.wait_for_function("() => document.readyState !== 'loading'")
        wait()
        with page.expect_navigation(wait_until="commit"):
            released["through"] = document
            while waiting:
                answer(waiting.pop(0))
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    page.remove_listener("request", navigated)


def test_a_value_typed_into_the_page_rides_a_reload_after_a_scroll(browser, serve):
    """A value the user typed into the page's own form comes back after two reloads
    Leaf asks for in a row though they scrolled in the document between, which ended
    its arrival before it had put them back where they were, while something slow to
    upgrade still held back that document's anchoring: an input ends the reload's claim
    on where the user was, never on what they typed."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Form</h1><p><label>Name <input id="who" autocomplete="off">'
            "</label></p>",
        )
    )
    page = open_page(browser, live_url(url))
    page.locator("#who").fill("Ada")
    page.add_init_script(HOLD_INTERFACES % json.dumps([1]))
    release = reload_with_its_answers_held(page, serve, anchored=False)
    scroll_away(page)
    release(True)
    expect(page.locator("#who")).to_have_value("Ada")


def test_a_value_typed_into_the_page_rides_two_reloads_in_a_row(browser, serve):
    """A value the user typed into the page's own form, and an option they chose before
    the one its author chose, come back after two reloads Leaf asks for in a row, the
    second before the first's arrival has put them back, while something slow to
    upgrade still holds back that document's anchoring. The form asks the browser to
    keep no value of its own, so only Leaf's carry can."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Form</h1><form autocomplete="off"><p><label>Name <input id="who">'
            "</label></p>"
            '<label><input type="radio" name="pace" id="slow"> slow</label>'
            '<label><input type="radio" name="pace" checked> steady</label>'
            '<label><input type="radio" name="pace" id="fast"> fast</label>'
            "</form>",
        )
    )
    page = open_page(browser, live_url(url))
    page.locator("#who").fill("Ada")
    page.locator("#slow").check()
    reload_in_a_row(page, serve, [lambda: None], slow={1})
    expect(page.locator("#who")).to_have_value("Ada")
    expect(page.locator("#slow")).to_be_checked()


def test_a_value_a_page_script_writes_yields_to_the_one_the_reload_carries(
    browser, serve
):
    """A value the user typed comes back after a reload Leaf asks for though the page's
    own script writes the field's first value as the page loads: the carried value is
    the user's, newer than what the page starts the field with."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Form</h1><p><label>Name <input id="who" autocomplete="off">'
            "</label></p><script>0</script>"
            "<script>document.getElementById('who').value = 'initial'</script>",
        )
    )
    page = open_page(browser, live_url(url))
    expect(page.locator("#who")).to_have_value("initial")
    page.locator("#who").fill("Ada")
    restart_under_another_runtime(page, serve)
    expect(page.locator("#who")).to_have_value("Ada")


def while_leaf_reloads(page, serve, act):
    """A reload Leaf asks for, as a server restarted under another Leaf causes, with
    `act` run in the document it brings while that document's entry module still
    loads, so before Leaf has started there. Returns once that document is ready."""
    module = []
    page.route("**/leaf.js", lambda route: module.append(route))
    answer_as_another_runtime(page)
    try:
        with page.expect_navigation(wait_until="commit"):
            append_carried_log_record(
                serve.page_dir,
                {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
            )
        holding(page, module, 1, "the arriving document's entry module")
        page.wait_for_function("document.readyState !== 'loading'")
        act()
    finally:
        page.unroute("**/leaf.js")
        for route in module:
            route.continue_()
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")


@pytest.mark.parametrize("step", ["stay", "back"])
def test_a_value_typed_before_leaf_starts_outlasts_the_one_the_reload_carries(
    browser, serve, step
):
    """A value the user types into the page's own form while the document a reload Leaf
    asked for brings is still loading Leaf stays as they typed it, whether they stayed
    on the entry the reload landed on or went Back to another first: the value the
    reload carries from the document before is older than their edit."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Form</h1><p><label>Name <input id="who" autocomplete="off">'
            '</label></p><p id="later">Later.</p>',
        )
    )
    page = open_page(browser, live_url(url))
    page.locator("#who").fill("Ada")
    page.evaluate("document.activeElement.blur()")
    if step == "back":
        page.wait_for_function("navigation.transition === null")
        page.evaluate("location.hash = '#later'")
        page.wait_for_function("navigation.transition === null")

    def type_again():
        if step == "back":
            page.evaluate("history.back()")
            page.wait_for_function("location.hash === ''")
        page.locator("#who").fill("Grace")

    while_leaf_reloads(page, serve, type_again)
    expect(page.locator("#who")).to_have_value("Grace")


def test_a_reload_the_user_asks_for_before_leaf_starts_brings_back_no_older_value(
    browser, serve
):
    """A user who changes a value the reload Leaf asked for carries while the document
    it brings still loads Leaf, and then reloads the page themselves before Leaf has
    started, doesn't get the carried value back over theirs: their change ended the
    reload's claim, though no runtime had started there to say so."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Form</h1><p><label>Name <input id="who" autocomplete="off">'
            "</label></p>",
        )
    )
    page = open_page(browser, live_url(url))
    page.locator("#who").fill("Ada")
    page.evaluate("document.activeElement.blur()")
    module = []
    page.route("**/leaf.js", lambda route: module.append(route))
    answer_as_another_runtime(page)
    try:
        with page.expect_navigation(wait_until="commit"):
            append_carried_log_record(
                serve.page_dir,
                {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
            )
        holding(page, module, 1, "the arriving document's entry module")
        page.wait_for_function("document.readyState !== 'loading'")
        page.locator("#who").fill("Grace")
        page.reload(wait_until="commit")
    finally:
        page.unroute("**/leaf.js")
        for route in module:
            try:
                route.continue_()
            except Exception:
                pass
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    expect(page.locator("#who")).not_to_have_value("Ada")


# A form of two fields that keep no value of the browser's own across a reload, and
# a paragraph to put a second entry of the page at.
NAME_AND_TOWN = (
    '<h1>Form</h1><p><label>Name <input id="who" autocomplete="off"></label></p>'
    '<p><label>Town <input id="town" autocomplete="off"></label></p>'
    '<p id="later">Later.</p>'
)

# The handoff the tab holds for the page, if any (prepaint.js).
STORED_HANDOFF = """() => {
  const key = Object.keys(sessionStorage).find((key) => key.endsWith("lf-revision-handoff"));
  return key ? JSON.parse(sessionStorage.getItem(key)) : null;
}"""

# The page going hidden, as when the user switches tabs; a hidden tab the browser
# discards goes with no `pagehide`, so what the tab holds then is what its next load
# finds.
SHOW_AS = """(state) => {
  Object.defineProperty(document, "visibilityState", {value: state, configurable: true});
  document.dispatchEvent(new Event("visibilitychange"));
}"""


def carried_values(page):
    """The values the tab's stored handoff carries, by control id."""
    stored = page.evaluate(STORED_HANDOFF) or {}
    return {record["id"]: record.get("value") for record in stored.get("carry", [])}


def reload_before_leaf_starts(page, serve, meanwhile, by_leaf=True):
    """A reload Leaf asks for, as a server restarted under another Leaf causes, then
    `meanwhile` in the document it brings, which waits on its layer's registry so its
    runtime hasn't started, then another reload of that document: Leaf's where
    `by_leaf`, as when the registry names another layer and the source's probe, the
    registry at the server's root, says the source moved on, else the user's. Returns
    once the document that reload brings is ready."""
    documents = {"count": 0}
    held = []

    def navigated(request):
        if request.is_navigation_request() and request.frame == page.main_frame:
            documents["count"] += 1

    def another(route):
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={**response.headers, "Leaf-Runtime": "0123456789abcdef"},
        )

    def answer(route):
        path = urlsplit(route.request.url).path
        if documents["count"] < 2 and (
            path == "/registry.json" or documents["count"] == 0
        ):
            another(route)
        elif documents["count"] == 1 and path.endswith("/registry.json"):
            held.append(route)
        else:
            route.continue_()

    born = page.evaluate("performance.timeOrigin")
    page.on("request", navigated)
    page.route("**/api/**", answer)
    page.route("**/registry.json", answer)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    holding(page, held, 1, "the arriving document's layer registry")
    page.wait_for_function(
        "(born) => performance.timeOrigin !== born && document.readyState !== 'loading'",
        arg=born,
    )
    meanwhile()
    route = held.pop()
    if by_leaf:
        response = route.fetch()
        registry = response.json()
        registry["$layer"]["generation"] = "another"
        with page.expect_navigation(wait_until="commit"):
            route.fulfill(response=response, json=registry)
    else:
        page.reload(wait_until="commit")
        try:
            route.continue_()
        except Exception:
            pass
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    page.remove_listener("request", navigated)


@pytest.mark.parametrize("reloads", ["Leaf", "the user"])
def test_a_value_carried_to_an_entry_left_by_back_rides_another_reload(
    browser, serve, reloads
):
    """A value a reload Leaf asks for carries comes back after the user steps Back to
    an earlier entry of the page before Leaf has started and the page reloads again,
    whether Leaf asks for that reload or the user does: the value is the document's,
    wherever in it the user stands."""
    page = open_page(browser, live_url(serve(leaf_page("Restarted", NAME_AND_TOWN))))
    page.locator("#who").fill("Ada")
    page.evaluate("document.activeElement.blur()")
    page.wait_for_function("navigation.transition === null")
    page.evaluate("location.hash = '#later'")
    page.wait_for_function("navigation.transition === null")

    def back():
        page.evaluate("history.back()")
        page.wait_for_function("location.hash === ''")

    reload_before_leaf_starts(page, serve, back, by_leaf=reloads == "Leaf")
    expect(page.locator("#who")).to_have_value("Ada")


def test_a_reload_before_leaf_starts_carries_on_the_values_the_user_left(
    browser, serve
):
    """Values a reload Leaf asks for carries come back after a second such reload,
    taken before Leaf has started in the document between, where the user changed one
    of them: the others come back as they were, and the one they changed comes back as
    they changed it."""
    page = open_page(browser, live_url(serve(leaf_page("Restarted", NAME_AND_TOWN))))
    page.locator("#who").fill("Ada")
    page.locator("#town").fill("Paris")
    page.evaluate("document.activeElement.blur()")
    reload_before_leaf_starts(page, serve, lambda: page.locator("#who").fill("Grace"))
    expect(page.locator("#town")).to_have_value("Paris")
    expect(page.locator("#who")).to_have_value("Grace")


def test_startup_recovery_s_reload_keeps_words_typed_before_leaf_started(
    browser, serve
):
    """Words the user typed into a page whose module failed on its way, which no reload
    had handed anything, come back after startup recovery reloads it."""
    url = live_url(serve(leaf_page("Restarted", NAME_AND_TOWN)))
    page = open_page(browser, url)
    documents = {"count": 0}
    held, failed = [], []

    def navigated(request):
        if request.is_navigation_request() and request.frame == page.main_frame:
            documents["count"] += 1

    def lose(route):
        if documents["count"] == 1 and not failed:
            failed.append(route.request.url)
            route.abort("internetdisconnected")
        else:
            route.continue_()

    # Recovery's probe of the source, the registry at the server's root, waits while the
    # user types.
    def probe(route):
        if documents["count"] == 1 and urlsplit(route.request.url).path == (
            "/registry.json"
        ):
            held.append(route)
        else:
            route.continue_()

    page.on("request", navigated)
    page.route("**/runtime/base/rendering.js", lose)
    page.route("**/registry.json", probe)
    with page.expect_navigation(wait_until="commit"):
        page.goto(url, wait_until="commit")
    holding(page, held, 1, "startup recovery's probe")
    page.locator("#who").fill("Grace")
    with page.expect_navigation(wait_until="commit"):
        held.pop().continue_()
    wait_until_ready(page)
    page.unroute("**/runtime/base/rendering.js")
    page.unroute("**/registry.json")
    page.remove_listener("request", navigated)
    assert len(failed) == 1, failed
    take_browser_errors(page)
    expect(page.locator("#who")).to_have_value("Grace")


@pytest.mark.parametrize("arrives", ["back at its entry", "at another entry"])
def test_a_handoff_written_as_the_page_hid_comes_back_only_to_its_entry(
    browser, serve, arrives
):
    """The handoff a page writes as it hides, before Leaf has put back what a reload
    carried, comes back to a document arriving at the same entry, as Back to a
    document the browser didn't keep, or a discarded tab's return, brings, and to no
    document at another entry of the page."""
    url = live_url(serve(leaf_page("Restarted", NAME_AND_TOWN)))
    page = open_page(browser, url)
    page.locator("#who").fill("Ada")
    page.evaluate("document.activeElement.blur()")
    module = []
    page.route("**/leaf.js", lambda route: module.append(route))
    answer_as_another_runtime(page)
    try:
        with page.expect_navigation(wait_until="commit"):
            append_carried_log_record(
                serve.page_dir,
                {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
            )
        holding(page, module, 1, "the arriving document's entry module")
        page.wait_for_function("document.readyState !== 'loading'")
        page.evaluate(SHOW_AS, "hidden")
        # The browser discards the tab: the document goes with no `pagehide`.
        page.evaluate(
            """() => addEventListener(
              "pagehide", (event) => event.stopImmediatePropagation(), {capture: true})"""
        )
        page.goto("about:blank")
    finally:
        page.unroute("**/leaf.js")
        for route in module:
            try:
                route.continue_()
            except Exception:
                pass
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    if arrives == "back at its entry":
        page.go_back()
        assert (
            page.evaluate("performance.getEntriesByType('navigation')[0].type")
            == "back_forward"
        )
    else:
        page.goto(url)
    wait_until_ready(page)
    expect(page.locator("#who")).to_have_value(
        "Ada" if arrives == "back at its entry" else ""
    )


def test_a_key_typed_while_a_page_handed_only_values_starts_ends_its_arrival(
    browser, serve
):
    """A reload that hands the document only the values the user typed, as startup
    recovery's does after a document that never started, hands back no place. So a key
    the user presses while the page starts ends its arrival, as on a fresh load: the
    thread its address names, the page's first, doesn't open, so `t` walks to that
    first thread rather than on from it to the next."""
    url = live_url(
        serve(
            leaf_page(
                "Restarted",
                '<h1>Form</h1><p id="first">The first finding.</p>'
                '<p><label>Name <input id="who" autocomplete="off"></label></p>'
                '<p id="second">The second finding.</p>',
            )
        )
    )
    for thread, section in [("one", "first"), ("two", "second")]:
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
    page = open_page(browser, url)
    documents = {"count": 0}
    probes, states, failed = [], [], []

    def navigated(request):
        if request.is_navigation_request() and request.frame == page.main_frame:
            documents["count"] += 1

    def lose(route):
        if documents["count"] == 1 and not failed:
            failed.append(route.request.url)
            route.abort("internetdisconnected")
        else:
            route.continue_()

    # Recovery's probe of the source waits while the user types into the document that
    # never started, and the reloaded document's first reading waits while the user
    # presses a key.
    def probe(route):
        if documents["count"] == 1 and urlsplit(route.request.url).path == (
            "/registry.json"
        ):
            probes.append(route)
        else:
            route.continue_()

    def state(route):
        if documents["count"] == 2:
            states.append(route)
        else:
            route.continue_()

    page.on("request", navigated)
    page.route("**/runtime/base/rendering.js", lose)
    page.route("**/registry.json", probe)
    page.route("**/api/state*", state)
    page.goto(f"{url}&thread=one", wait_until="commit")
    holding(page, probes, 1, "startup recovery's probe")
    page.locator("#who").fill("Grace")
    page.evaluate("document.activeElement.blur()")
    with page.expect_navigation(wait_until="commit"):
        probes.pop().continue_()
    holding(page, states, 1, "the reloaded document's first reading")
    page.wait_for_function("document.readyState !== 'loading'")
    page.keyboard.press("t")
    page.unroute("**/api/state*")
    for route in states:
        route.continue_()
    wait_until_ready(page)
    page.unroute("**/runtime/base/rendering.js")
    page.unroute("**/registry.json")
    page.remove_listener("request", navigated)
    assert len(failed) == 1, failed
    take_browser_errors(page)
    expect(page.locator("#who")).to_have_value("Grace")
    expect(
        page.locator(
            f'{PANEL_THREAD}[data-lf-thread="one"], '
            '.lf-margin-preview .lf-page-thread[data-lf-thread="one"]'
        )
    ).to_be_focused()


def test_a_page_that_starts_hidden_keeps_its_handoff_in_the_tab(browser, serve):
    """A document a reload brings into a hidden tab, as Leaf's reload of a background
    tab does, leaves the handoff it was given in the tab while it stays hidden, so a
    discard before Leaf has put back what it carries loses nothing."""
    page = open_page(browser, live_url(serve(leaf_page("Restarted", NAME_AND_TOWN))))
    page.locator("#who").fill("Ada")
    page.evaluate("document.activeElement.blur()")
    page.add_init_script(
        """Object.defineProperty(document, "visibilityState",
          {value: "hidden", configurable: true});"""
    )
    module = []
    page.route("**/leaf.js", lambda route: module.append(route))
    answer_as_another_runtime(page)
    try:
        with page.expect_navigation(wait_until="commit"):
            append_carried_log_record(
                serve.page_dir,
                {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
            )
        holding(page, module, 1, "the arriving document's entry module")
        page.wait_for_function("document.readyState !== 'loading'")
        assert page.evaluate("document.visibilityState") == "hidden"
        stored = carried_values(page)
    finally:
        page.unroute("**/leaf.js")
        for route in module:
            route.continue_()
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    assert stored == {"who": "Ada"}


def test_a_page_hidden_before_leaf_starts_keeps_what_its_reload_carried(browser, serve):
    """A page hidden before Leaf has started, after the user clicked in its prose, keeps
    in the tab the values the reload Leaf asked for carried, which haven't reached the
    page yet, for a tab the browser discards while hidden; shown again, it keeps
    none."""
    page = open_page(browser, live_url(serve(leaf_page("Restarted", NAME_AND_TOWN))))
    page.locator("#who").fill("Ada")
    page.locator("#town").fill("Paris")
    page.evaluate("document.activeElement.blur()")
    module = []
    page.route("**/leaf.js", lambda route: module.append(route))
    answer_as_another_runtime(page)
    try:
        with page.expect_navigation(wait_until="commit"):
            append_carried_log_record(
                serve.page_dir,
                {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
            )
        holding(page, module, 1, "the arriving document's entry module")
        page.wait_for_function("document.readyState !== 'loading'")
        page.locator("h1").click()
        page.evaluate(SHOW_AS, "hidden")
        hidden = carried_values(page)
        page.evaluate(SHOW_AS, "visible")
        shown = page.evaluate(STORED_HANDOFF)
    finally:
        page.unroute("**/leaf.js")
        for route in module:
            route.continue_()
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    assert hidden == {"who": "Ada", "town": "Paris"}
    assert shown is None


def test_startup_recovery_s_reload_carries_on_the_values_a_reload_brought(
    browser, serve
):
    """Values a reload Leaf asks for carries come back after startup recovery reloads
    the document it brought, whose module failed on its way, where the user changed one
    of them meanwhile: the others as they were, and theirs as they changed it."""
    page = open_page(browser, live_url(serve(leaf_page("Restarted", NAME_AND_TOWN))))
    page.locator("#who").fill("Ada")
    page.locator("#town").fill("Paris")
    page.evaluate("document.activeElement.blur()")
    documents = {"count": 0}
    held, failed = [], []

    def navigated(request):
        if request.is_navigation_request() and request.frame == page.main_frame:
            documents["count"] += 1

    def lose(route):
        if documents["count"] == 1 and not failed:
            failed.append(route.request.url)
            route.abort("internetdisconnected")
        else:
            route.continue_()

    def another(route):
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={**response.headers, "Leaf-Runtime": "0123456789abcdef"},
        )

    # The live document hears from a server restarted under another Leaf and reloads;
    # the document that brings loses a module on its way, and recovery's probe of the
    # source, the registry at the server's root, waits while the user types.
    def answer(route):
        if documents["count"] == 0:
            another(route)
        elif documents["count"] == 1 and urlsplit(route.request.url).path == (
            "/registry.json"
        ):
            held.append(route)
        else:
            route.continue_()

    page.on("request", navigated)
    page.route("**/runtime/base/rendering.js", lose)
    page.route("**/api/**", answer)
    page.route("**/registry.json", answer)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    holding(page, held, 1, "startup recovery's probe")
    page.locator("#who").fill("Grace")
    with page.expect_navigation(wait_until="commit"):
        held.pop().continue_()
    wait_until_ready(page)
    page.unroute("**/runtime/base/rendering.js")
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    page.remove_listener("request", navigated)
    assert len(failed) == 1, failed
    take_browser_errors(page)
    expect(page.locator("#town")).to_have_value("Paris")
    expect(page.locator("#who")).to_have_value("Grace")


def test_a_reload_s_arrival_leaves_no_handoff_in_the_tab(browser, serve):
    """Once the document a reload Leaf asked for brought has put back what it carried,
    the tab holds no handoff, so no later load can bring those values back over the
    user's newer ones."""
    page = open_page(browser, live_url(serve(leaf_page("Restarted", NAME_AND_TOWN))))
    page.locator("#who").fill("Ada")
    page.evaluate("document.activeElement.blur()")
    restart_under_another_runtime(page, serve)
    expect(page.locator("#who")).to_have_value("Ada")
    assert page.evaluate(STORED_HANDOFF) is None


def test_a_page_hidden_after_its_own_prompt_kept_it_hands_on_the_newer_value(
    browser, serve
):
    """A page whose own leave prompt kept it from a reload Leaf asked for, and which
    is then hidden, hands on the value the user typed after the earlier reload's
    values came back, not the one that reload carried."""
    page = open_page(browser, live_url(serve(leaf_page("Restarted", NAME_AND_TOWN))))
    page.locator("#who").fill("Ada")
    page.evaluate("document.activeElement.blur()")
    restart_under_another_runtime(page, serve)
    expect(page.locator("#who")).to_have_value("Ada")
    page.locator("#who").click()
    page.locator("#who").fill("Grace")
    page.evaluate("document.activeElement.blur()")
    page.on("dialog", lambda dialog: dialog.dismiss())
    page.evaluate(
        """() => addEventListener("beforeunload", (event) => {
          event.preventDefault();
          event.returnValue = "";
        })"""
    )
    answer_as_another_runtime(page)
    with page.expect_event("dialog"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Again."},
        )
    # An answer still in flight here would outlast the test, and teardown, cutting it
    # off, would fail its handler.
    page.unroute_all(behavior="wait")
    page.evaluate(SHOW_AS, "hidden")
    assert carried_values(page).get("who") == "Grace"


def test_an_option_chosen_before_leaf_starts_outlasts_the_one_the_reload_carries(
    browser, serve
):
    """An option the user chooses while the document a reload Leaf asked for brings is
    still loading Leaf stays chosen, though the reload carries another option of the
    same group, and the page's own script moves the option its author chose
    meanwhile."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Form</h1><form autocomplete="off">'
            '<p id="first"><label><input type="radio" name="pace" id="slow"> slow</label>'
            '<label><input type="radio" name="pace" id="steady" checked> steady</label>'
            '<label><input type="radio" name="pace" id="fast"> fast</label></p>'
            '<p id="second"></p></form>',
        )
    )
    page = open_page(browser, live_url(url))
    page.locator("#slow").check()

    def choose_again():
        page.locator("#fast").check()
        page.evaluate(
            "document.getElementById('second')"
            ".append(document.getElementById('steady').closest('label'))"
        )

    while_leaf_reloads(page, serve, choose_again)
    expect(page.locator("#fast")).to_be_checked()


def test_a_disclosure_closed_before_leaf_starts_stays_closed(browser, serve):
    """A disclosure the user opens and closes again by its summary while the document
    a reload Leaf asked for brings is still loading Leaf stays closed, though the
    reload carries it open."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Notes</h1><details id="more"><summary>More</summary>'
            "<p>The rest of the notes.</p></details>",
        )
    )
    page = open_page(browser, live_url(url))
    more = page.locator("#more")
    more.locator("summary").click()
    expect(more).to_have_attribute("open", "")

    def open_and_close():
        more.locator("summary").click()
        expect(more).to_have_attribute("open", "")
        more.locator("summary").click()
        expect(more).not_to_have_attribute("open", "")

    while_leaf_reloads(page, serve, open_and_close)
    expect(more).not_to_have_attribute("open", "")


def test_a_disclosure_opened_before_leaf_starts_stays_open_beside_its_group(
    browser, serve
):
    """A named disclosure the user opens while the document a reload Leaf asked for
    brings is still loading Leaf stays open, though the reload carries another of its
    group open, which opening would close it: the user's choice in the group is
    newer than the one the reload carries."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Notes</h1><details id="first" name="notes"><summary>First</summary>'
            '<p>The first notes.</p></details><details id="second" name="notes">'
            "<summary>Second</summary><p>The second notes.</p></details>",
        )
    )
    page = open_page(browser, live_url(url))
    first, second = page.locator("#first"), page.locator("#second")
    first.locator("summary").click()
    expect(first).to_have_attribute("open", "")
    while_leaf_reloads(page, serve, lambda: second.locator("summary").click())
    expect(second).to_have_attribute("open", "")
    expect(first).not_to_have_attribute("open", "")


def test_a_right_click_on_a_summary_before_leaf_starts_leaves_its_disclosure_carried(
    browser, serve
):
    """A right-click on a disclosure's summary while the document a reload Leaf asked
    for brings is still loading Leaf opens no menu of Leaf's and toggles nothing, so
    the disclosure still comes back open as the reload carries it."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Notes</h1><details id="more"><summary>More</summary>'
            "<p>The rest of the notes.</p></details>",
        )
    )
    page = open_page(browser, live_url(url))
    more = page.locator("#more")
    more.locator("summary").click()
    expect(more).to_have_attribute("open", "")
    while_leaf_reloads(
        page, serve, lambda: more.locator("summary").click(button="right")
    )
    expect(more).to_have_attribute("open", "")


def scroll_away(page):
    """Scroll the page with the wheel, and wait until the document has heard it: an
    input of the user's, as its clock counts them (base/document-inputs.js). A document
    that has not painted yet may not hear a wheel at all."""
    page.mouse.move(400, 300)
    page.mouse.wheel(0, 200)
    page.wait_for_function('Reflect.get(window, Symbol.for("leaf.inputs")).count > 0')


def reload_with_its_answers_held(page, serve, anchored=True):
    """A reload Leaf asks for, as a server restarted under another Leaf causes, whose
    document then waits on the server's answers, as on a slow server, with its runtime
    started and, where `anchored`, the page's words anchored, so the document records
    where the user is as it goes. Returns `release(again, then)`: `then()` runs, as a
    reload the user asks for, say, and the document's waiting requests are answered, as
    are those it makes from then on, as another Leaf would answer them where `again`,
    which has it reload once more as Leaf asks; it returns once the document then
    standing is ready, or at once where `presents` is false, as for a page that
    reported a fault of its own."""
    documents = {"count": 0, "again": False, "released": False}
    held = []

    def navigated(request):
        if request.is_navigation_request() and request.frame == page.main_frame:
            documents["count"] += 1

    def another(route):
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={**response.headers, "Leaf-Runtime": "0123456789abcdef"},
        )

    def answer(route):
        url = route.request.url
        asked = "/api/" in url or urlsplit(url).path == "/registry.json"
        if documents["count"] == 0 or (
            documents["count"] == 1 and documents["again"] and asked
        ):
            another(route)
        elif documents["count"] == 1 and "/api/" in url and not documents["released"]:
            held.append(route)
        else:
            route.continue_()

    page.on("request", navigated)
    page.route("**/api/**", answer)
    page.route("**/registry.json", answer)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    holding(page, held, 1, "the arriving document's first answer")
    if anchored:
        wait_for_check_api(page, "(api) => api.anchoringIsReady()")
    else:
        # The panel mounts in the task that begins the document's arrival (leaf.js), and
        # takes over the row the document served before its runtime started
        # (bootstrap.js, `standRow`), which carries `data-lf-served`.
        page.wait_for_function(
            "document.querySelector('.lf-floating-panel:not([data-lf-served])') !== null"
        )

    def answer_held(again):
        for route in held:
            try:
                another(route) if again else route.continue_()
            except Exception:
                pass

    def release(again, then=lambda: None, presents=True):
        documents["again"] = again
        documents["released"] = True
        then()
        if again:
            with page.expect_navigation(wait_until="commit"):
                answer_held(True)
        else:
            answer_held(False)
        if presents:
            wait_until_ready(page)
        page.unroute("**/api/**")
        page.unroute("**/registry.json")
        page.remove_listener("request", navigated)

    return release


def writing_a_reply(browser, serve, form="", filled=None):
    """A page with `form` above a paragraph a thread is about, open at the user's reply
    to the thread in its card, which holds the words "Hold" and has focus. `filled`
    maps the fields of `form` to the values the user typed there first."""
    url = serve(
        leaf_page(
            "Restarted",
            f"<h1>Rehearsal</h1>{form}"
            '<p id="result">The backfill copied 310 million rows.</p>',
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
    for field, value in (filled or {}).items():
        page.locator(field).fill(value)
    page.locator('[data-lf-margin-for="result"] .lf-margin-marker').click()
    reply = page.locator(
        '.lf-margin-preview .lf-page-thread[data-lf-thread="rows"] '
        ".lf-thread-reply leaf-text"
    )
    write(reply, "Hold")
    return page, reply


def test_words_typed_through_two_reloads_in_a_row_reach_the_reply(browser, serve):
    """Words the user types on as the tab reloads, into the reply box they were writing
    in, reach that box though a second reload Leaf asks for comes before the first
    document has put the box back, as typed words survive every path (SOUL.md)."""
    page, reply = writing_a_reply(browser, serve)
    reload_in_a_row(page, serve, [lambda: page.keyboard.type(" the resend")])
    expect(reply).to_have_js_property("value", "Hold the resend")


# Whether the panel's field has said "Draft kept" in this document (`PANEL_SAYS`).
SAYS_DRAFT_KEPT = """new MutationObserver(() => {
  const said = document.querySelector('.lf-fp-field leaf-text')?.getAttribute('placeholder');
  if (said?.includes('Draft kept')) window.saidDraftKept = true;
}).observe(document, { subtree: true, childList: true, attributes: true })"""


def reply_draft(serve):
    """The words the server holds in the draft of the reply to the thread `rows`."""
    record = drafts_model.read_drafts(serve.page_dir)["drafts"].get("reply:rows")
    return record and record.get("text")


def test_a_key_held_through_a_reload_goes_with_a_scroll_across_another(browser, serve):
    """A key typed while a reload's arrival waits is a word for the reply it puts
    back, which the reply's draft takes as it is typed. Scrolling the page ends that
    arrival, so a second reload Leaf asks for, which hands back where the user has gone
    instead, a field of the page's own, brings the word there no more: a word typed
    there is the only one, and the reply keeps its own."""
    page, _ = writing_a_reply(
        browser, serve, '<p><input id="who" aria-label="Name" autocomplete="off"></p>'
    )

    release = reload_with_its_answers_held(page, serve)
    page.keyboard.type("x")
    scroll_away(page)
    page.focus("#who")

    release(True)
    who = page.locator("#who")
    expect(who).to_be_focused()
    page.keyboard.type("y")
    expect(who).to_have_value("y")
    wait_for(
        lambda: reply_draft(serve),
        lambda words: words == "Holdx",
        failure=lambda: f"the reply's draft reads {reply_draft(serve)!r}",
    )


@pytest.mark.parametrize(
    ("engine", "ending"),
    [
        *(
            ("browser", ending)
            for ending in ["scroll", "pointer", "Backspace", "Enter"]
        ),
        ("firefox_browser", "scroll"),
        ("firefox_browser", "Backspace"),
    ],
)
def test_words_typed_through_a_reload_stay_in_the_reply_when_the_user_moves_on(
    request, serve, engine, ending
):
    """Words the user types on as a reload Leaf asked for comes are words for the reply
    they were writing in. Moving on before the reload has put them back there, by
    scrolling, pressing the page or pressing a key that prints nothing, ends the
    return, not the user's wish for the words. They go into the reply's draft as they
    are typed, which the panel says beside them; the reply isn't on screen once the
    page has answered, so the panel says the draft is kept, and Resume writing takes
    the user back to their end (SOUL.md, "Preserve the user's attention and work")."""
    page, _ = writing_a_reply(request.getfixturevalue(engine), serve)
    release = reload_with_its_answers_held(page, serve)
    page.keyboard.type(" more")
    expect_panel_says(page, "kept in the draft")
    if ending == "scroll":
        scroll_away(page)
    elif ending == "pointer":
        page.locator("h1").click()
    else:
        page.keyboard.press(ending)
    release(False)
    expect_panel_says(page, "Draft kept")
    wait_for(
        lambda: reply_draft(serve),
        lambda words: words == "Hold more",
        failure=lambda: f"the reply's draft reads {reply_draft(serve)!r}",
    )
    page.keyboard.press("g")
    page.keyboard.press("i")
    resumed = page.locator("leaf-text:focus")
    expect(resumed).to_have_js_property("value", "Hold more")
    page.keyboard.type(" now")
    expect(resumed).to_have_js_property("value", "Hold more now")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_words_typed_through_a_reload_stay_in_the_reply_across_a_step_back(
    request, serve, engine
):
    """Words the user types on as a reload Leaf asked for comes are words for the reply
    they were writing in. A step Back before the reload has put them back there takes
    the user to another entry, and in Firefox, which says no step is the user's, the
    keys stay held there, but they are still the reply's words: they go into its draft
    rather than run there as the page's single-key commands, one of which resolves the
    thread. The entry the step reaches shows no reply, so the panel says the draft is
    kept, in Firefox as in Chromium."""
    page, reply = writing_a_reply(request.getfixturevalue(engine), serve)
    # The entry the step goes back to stands on the thread rather than in its reply.
    page.keyboard.press("Escape")
    expect(reply).not_to_be_focused()
    page.evaluate("location.hash = '#result'")
    page.wait_for_function("navigation.transition === null")
    reply.click()
    page.keyboard.press("End")
    page.add_init_script(SAYS_DRAFT_KEPT)
    release = reload_with_its_answers_held(page, serve)
    page.keyboard.type(" more")
    expect(page.locator(".lf-held-key").first).to_be_visible()
    page.go_back(wait_until="commit")
    page.wait_for_function("location.hash === ''")
    # Keys typed at the entry the step reached are the page's, not the reply's.
    page.keyboard.type("jj")
    release(False)
    expect(page.locator(".lf-held-key")).to_have_count(0)
    wait_for(
        lambda: reply_draft(serve),
        lambda words: words == "Hold more",
        failure=lambda: f"the reply's draft reads {reply_draft(serve)!r}",
    )
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "resolve"
    ]
    expect(reply).to_have_count(0)
    page.wait_for_function("window.saidDraftKept === true")


def test_words_typed_through_a_reload_reach_the_reply_when_the_page_opens_anew(
    browser, serve
):
    """Words the user types on as a reload Leaf asked for comes are words for the reply
    they were writing in. Leaving the page before the reload has put them back there,
    and opening it again at an entry of its own, which puts the user back nowhere,
    finds them in the reply's draft, where Resume writing takes the user to their
    end."""
    page, _ = writing_a_reply(browser, serve)
    url = page.url
    reload_with_its_answers_held(page, serve)
    page.keyboard.type(" more")
    expect(page.locator(".lf-held-key").first).to_be_visible()
    page.goto("about:blank")
    page.goto(url, wait_until="commit")
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    wait_for(
        lambda: reply_draft(serve),
        lambda words: words == "Hold more",
        failure=lambda: f"the reply's draft reads {reply_draft(serve)!r}",
    )
    page.keyboard.press("g")
    page.keyboard.press("i")
    resumed = page.locator("leaf-text:focus")
    expect(resumed).to_have_js_property("value", "Hold more")
    page.keyboard.type(" now")
    expect(resumed).to_have_js_property("value", "Hold more now")


def test_keys_typed_once_the_user_moves_on_are_the_pages_again(browser, serve):
    """Keys typed while a reload Leaf asked for puts the user back are words for the
    reply they were writing in, until the user moves on: a scroll ends the return, and
    the keys they type after it are the page's single-key commands, not more words
    for the reply."""
    page, _ = writing_a_reply(browser, serve)
    release = reload_with_its_answers_held(page, serve)
    page.keyboard.type(" more")
    expect(page.locator(".lf-held-key").first).to_be_visible()
    scroll_away(page)
    page.keyboard.type("jjk")
    release(False)
    expect(page.locator(".lf-held-key")).to_have_count(0)
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator("leaf-text:focus")).to_have_js_property("value", "Hold more")


@pytest.mark.parametrize(
    ("kind", "ending"),
    [
        ("text", "scroll"),
        ("password", "scroll"),
        ("text", "put-back"),
        ("text", "cannot-start"),
    ],
    ids=["text", "password", "put-back", "cannot-start"],
)
def test_words_typed_through_a_reload_for_a_field_of_the_page_stay_in_it(
    browser, serve, kind, ending
):
    """Words the user types on as a reload Leaf asked for comes, while writing in a
    field of the page's own, are that field's. The reload puts the user back in the
    field with the words after the ones it held and the caret after them, as startup
    recovery does where the document the reload brings can't start; a scroll that ends
    that return leaves the words in the field all the same. None reaches the drafts
    the server keeps or the panel's field, as a password's characters must not."""
    url = serve(
        leaf_page(
            "Restarted",
            "<h1>Sign in</h1>"
            f'<p><input id="who" type="{kind}" aria-label="Name" autocomplete="off"></p>'
            "<script>document.getElementById('who').addEventListener('input',"
            " (event) => { window.heard = event.target.value; })</script>",
        )
    )
    page = open_page(browser, live_url(url))
    who = page.locator("#who")
    who.fill("ab")
    expect(who).to_be_focused()
    documents = {"count": 0}
    module = []

    def navigated(request):
        if request.is_navigation_request() and request.frame == page.main_frame:
            documents["count"] += 1

    def hold(route):
        if documents["count"] == 1 and not module:
            module.append(route)
        else:
            route.continue_()

    page.on("request", navigated)
    needed = (
        "**/runtime/base/rendering.js" if ending == "cannot-start" else "**/leaf.js"
    )
    page.route(needed, hold)
    answer_as_another_runtime(page)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    holding(page, module, 1, "a module the arriving document needs")
    page.wait_for_function("document.readyState !== 'loading'")
    page.keyboard.type("cd")
    expect(who).to_have_value("abcd")
    if ending == "scroll":
        scroll_away(page)
    if ending == "cannot-start":
        with page.expect_navigation(wait_until="commit"):
            module.pop().abort("internetdisconnected")
    else:
        module.pop().continue_()
    wait_until_ready(page)
    page.unroute(needed)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    page.remove_listener("request", navigated)
    if ending == "cannot-start":
        take_browser_errors(page)
    expect(who).to_have_value("abcd")
    expect(panel_field(page)).not_to_have_js_property("value", "cd")
    assert "cd" not in json.dumps(drafts_model.read_drafts(serve.page_dir)["drafts"])
    if ending != "scroll":
        expect(who).to_be_focused()
        page.keyboard.type("e")
        expect(who).to_have_value("abcde")


@pytest.mark.parametrize(
    ("engine", "kind", "value", "key"),
    [
        ("browser", "date", "2026-11-24", "1"),
        ("firefox_browser", "date", "2026-11-24", "1"),
        ("browser", "number", "12", "x"),
    ],
    ids=["date-browser", "date-firefox_browser", "number-browser"],
)
def test_a_key_typed_through_a_reload_leaves_a_field_with_no_caret_as_it_takes_it(
    request, serve, engine, kind, value, key
):
    """A date or number field of the page's own holds no caret to type at, so a key
    the user types through a reload Leaf asks for, while writing in it, waits to run
    in the field once the reload puts them back, which takes it as it takes any key,
    and the value the reload carries comes back whole rather than emptied by a
    character the field can't hold. Firefox's number field takes a letter as it takes
    a typed one, so only Chromium's, which refuses it, shows the difference."""
    url = serve(
        leaf_page(
            "Restarted",
            f'<h1>Form</h1><p><input id="when" type="{kind}" aria-label="When"'
            ' autocomplete="off"></p>',
        )
    )
    page = open_page(request.getfixturevalue(engine), live_url(url))
    field = page.locator("#when")
    field.fill(value)
    expect(field).to_be_focused()
    documents = {"count": 0}
    module = []

    def navigated(request):
        if request.is_navigation_request() and request.frame == page.main_frame:
            documents["count"] += 1

    def hold(route):
        if documents["count"] == 1 and not module:
            module.append(route)
        else:
            route.continue_()

    page.on("request", navigated)
    page.route("**/leaf.js", hold)
    answer_as_another_runtime(page)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    holding(page, module, 1, "the arriving document's entry module")
    page.wait_for_function("document.readyState !== 'loading'")
    page.keyboard.type(key)
    module.pop().continue_()
    wait_until_ready(page)
    page.unroute("**/leaf.js")
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    page.remove_listener("request", navigated)
    expect(field).to_be_focused()
    expect(field).to_have_value(value)


def test_words_let_go_into_a_field_of_the_page_are_its_input(browser, serve):
    """Words the user types on as a reload Leaf asked for comes, into a field of the
    page's own, before Leaf has started and after it has put the user back in the field
    but before the reload's return has ended, go into the field when a scroll ends that
    return, and the page's own script, running by then, hears them as the field's input,
    as it hears the words of a return that ends in the field."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Sign in</h1><p><input id="who" aria-label="Name" autocomplete="off"></p>'
            "<script>document.getElementById('who').addEventListener('input',"
            " (event) => { window.heard = event.target.value; });"
            " window.listening = true</script>",
        )
    )
    page = open_page(browser, live_url(url))
    who = page.locator("#who")
    who.fill("ab")
    documents = {"count": 0}
    module, answers = [], []

    def navigated(request):
        if request.is_navigation_request() and request.frame == page.main_frame:
            documents["count"] += 1

    def hold_module(route):
        if documents["count"] == 1 and not module:
            module.append(route)
        else:
            route.continue_()

    def hold_answer(route):
        if documents["count"] == 1:
            answers.append(route)
        else:
            route.fallback()

    page.on("request", navigated)
    page.route("**/leaf.js", hold_module)
    answer_as_another_runtime(page)
    page.route("**/api/state*", hold_answer)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    holding(page, module, 1, "the arriving document's entry module")
    page.wait_for_function("document.readyState !== 'loading'")
    page.keyboard.type("c")
    expect(who).to_have_value("abc")
    module.pop().continue_()
    page.wait_for_function("window.listening === true")
    expect(who).to_be_focused()
    page.keyboard.type("d")
    scroll_away(page)
    page.wait_for_function("window.heard === 'abcd'")
    page.unroute("**/api/state*", hold_answer)
    for route in answers:
        route.fallback()
    wait_until_ready(page)
    page.unroute("**/leaf.js")
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    page.remove_listener("request", navigated)
    expect(who).to_have_value("abcd")


def test_words_typed_through_a_reload_keep_the_replies_picture(browser, serve):
    """A reply the user was writing holds a picture as well as words. Words they type
    on as a reload Leaf asked for comes, then scroll before it has put them back, go
    in after the reply's words, and the picture stays attached after them."""
    page, reply = writing_a_reply(browser, serve)
    paste_image(reply, (example_media() / "051bee487bfb5d13.png").read_bytes())
    picture = "![Attached image](/media/051bee487bfb5d13.png)"
    wait_for(
        lambda: reply_draft(serve),
        lambda words: words == f"Hold\n\n{picture}",
        failure=lambda: f"the reply's draft reads {reply_draft(serve)!r}",
    )
    release = reload_with_its_answers_held(page, serve)
    page.keyboard.type(" more")
    expect(page.locator(".lf-held-key").first).to_be_visible()
    scroll_away(page)
    release(False)
    wait_for(
        lambda: reply_draft(serve),
        lambda words: words == f"Hold more\n\n{picture}",
        failure=lambda: f"the reply's draft reads {reply_draft(serve)!r}",
    )


def test_words_typed_through_a_reload_whose_page_has_a_fault_reach_the_reply(
    browser, serve
):
    """A page that reports a fault of its own while a reload Leaf asked for puts the
    user back stops holding keys but goes on, and no reload follows to take the words
    the user typed through it: they go into the reply's draft at once."""
    page, _ = writing_a_reply(browser, serve)
    release = reload_with_its_answers_held(page, serve)
    page.keyboard.type(" more")
    expect(page.locator(".lf-held-key").first).to_be_visible()
    page.evaluate(
        """() => dispatchEvent(new CustomEvent("lf-startup-failed", {
          detail: { reason: "a module staged words the page cannot read", page: true },
        }))"""
    )
    expect(page.locator(".lf-held-key")).to_have_count(0)
    release(False, presents=False)
    wait_for(
        lambda: reply_draft(serve),
        lambda words: words == "Hold more",
        failure=lambda: f"the reply's draft reads {reply_draft(serve)!r}",
    )
    take_browser_errors(page)


def test_words_kept_for_a_reply_join_its_draft_once_a_document_served_without_drafts_has_it(
    browser, serve
):
    """A document served without the drafts, as a release's is, hears them only at its
    first look. Words kept in the tab for a reply, as after the user left the page
    while a reload Leaf asked for was putting them back, wait for that look, then go in
    where the user's caret was, rather than starting the draft over and being joined
    to its words as another tab's."""
    page, _ = writing_a_reply(browser, serve)
    url = page.url
    reload_with_its_answers_held(page, serve)
    page.keyboard.type(" more")
    expect(page.locator(".lf-held-key").first).to_be_visible()
    page.goto("about:blank")

    def without_drafts(route):
        response = route.fetch()
        body = re.sub(
            r'<script[^>]*id="lf-drafts"[^>]*>.*?</script>',
            "",
            response.text(),
            flags=re.S,
        )
        route.fulfill(response=response, body=body)

    page.route(lambda address: address == url, without_drafts)
    page.goto(url, wait_until="commit")
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    wait_for(
        lambda: reply_draft(serve),
        lambda words: words == "Hold more",
        failure=lambda: f"the reply's draft reads {reply_draft(serve)!r}",
    )


def test_a_reload_the_user_asks_for_keeps_words_typed_through_another(browser, serve):
    """Words the user types on as a reload Leaf asked for comes are the reply's draft
    as soon as they are typed, so a reload the user then asks for, before the first
    has put them back, puts the user back in the reply with the words there."""
    page, reply = writing_a_reply(browser, serve)
    reload_with_its_answers_held(page, serve)
    page.keyboard.type(" more")
    expect(page.locator(".lf-held-key").first).to_be_visible()
    page.reload(wait_until="commit")
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Hold more")


def test_words_typed_through_a_reload_whose_page_cannot_start_reach_the_reply(
    browser, serve
):
    """Words the user types on as a reload Leaf asked for comes are words for the reply
    they were writing in, though the document the reload brings can't start: once
    startup recovery has loaded the page again, it puts the user back in the reply
    with the words typed there, and typing goes on after them. The panel doesn't say
    the draft is kept, since the words never left the user's place."""
    page, reply = writing_a_reply(browser, serve)
    page.add_init_script(SAYS_DRAFT_KEPT)
    documents = {"count": 0}
    held = []

    def navigated(request):
        if request.is_navigation_request() and request.frame == page.main_frame:
            documents["count"] += 1

    def hold(route):
        if documents["count"] == 1 and not held:
            held.append(route)
        else:
            route.continue_()

    page.on("request", navigated)
    page.route("**/runtime/base/rendering.js", hold)
    answer_as_another_runtime(page)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    holding(page, held, 1, "a module the arriving document needs")
    page.wait_for_function("() => document.readyState !== 'loading'")
    page.keyboard.type(" more")
    expect(page.locator(".lf-held-key").first).to_be_visible()
    with page.expect_navigation(wait_until="commit"):
        held.pop().abort("internetdisconnected")
    wait_until_ready(page)
    page.unroute("**/runtime/base/rendering.js")
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    page.remove_listener("request", navigated)
    take_browser_errors(page)
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Hold more")
    page.keyboard.type(" now")
    expect(reply).to_have_js_property("value", "Hold more now")
    assert not page.evaluate("window.saidDraftKept")


def test_a_key_typed_during_an_arrival_reaches_the_reply_once_across_more_reloads(
    browser, serve
):
    """A key typed while a reload's arrival waits goes into the reply's draft as it is
    typed. Escape in the document a second reload brings, and a third reload coming
    before that document's anchoring is ready, leave it there once (bootstrap.js,
    `typeBack`)."""
    page, reply = writing_a_reply(browser, serve)
    reload_in_a_row(
        page,
        serve,
        [lambda: page.keyboard.type("x"), lambda: page.keyboard.press("Escape")],
        slow={2},
    )
    expect(reply).to_have_js_property("value", "Holdx")


# The user leaving the window and coming back, as switching to another application
# does: the document loses focus, which a headless browser never lets it do, so the
# page is told so for the length of the window's `blur`.
LEAVE_THE_WINDOW = """() => {
  Object.defineProperty(document, "hasFocus", { value: () => false, configurable: true });
  dispatchEvent(new FocusEvent("blur"));
  delete document.hasFocus;
}"""


def test_leaving_the_window_while_a_reload_arrives_leaves_the_return_owed(
    browser, serve
):
    """A user writing a reply when Leaf reloads the page, who types on and then leaves
    the window and comes back while the server is slow to answer the document the
    reload brings, comes back to the reply with the words they typed: leaving the
    window is no input within the page, as a step Back is none, so the reload still
    owes them their place, and the keys held for it still land there."""
    page, reply = writing_a_reply(browser, serve)
    release = reload_with_its_answers_held(page, serve)
    page.keyboard.type(" more")
    page.evaluate(LEAVE_THE_WINDOW)
    release(False)
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Hold more")


def test_a_reload_the_user_asks_for_after_moving_on_returns_where_they_went(
    browser, serve
):
    """A reload Leaf asks for hands back the reply the user was writing and a value
    they typed into the page's form. Scrolling away while the server is slow to answer
    ends that return, so a reload the user then asks for comes back to where they
    went, as the entry's record says, rather than into the reply, and the value the
    handoff carried doesn't come back over the one they typed after the scroll: the
    tab keeps the handoff only while its arrival owes it. The thread the address names
    opens again, as on any reload."""
    page, reply = writing_a_reply(
        browser,
        serve,
        '<p><input id="who" aria-label="Name"></p>',
        filled={"#who": "Ada"},
    )
    who = page.locator("#who")
    release = reload_with_its_answers_held(page, serve)
    scroll_away(page)
    who.fill("Grace")
    release(False, lambda: page.reload(wait_until="commit"))
    # A carried value lands as the arrival begins, long before readiness, so it would
    # stand by now. The browser keeps no value of its own on this reload.
    expect(who).not_to_have_value("Ada")
    expect(reply).to_have_js_property("value", "Hold")
    expect(reply).not_to_be_focused()


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


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_reload_returns_a_selection_beside_focus_on_a_control_of_the_page(
    request, serve, engine
):
    """A passage the user selected on the page comes back after a reload Leaf asks
    for, though focus stands on a checkbox of the page's own, which holds no caret: the
    handoff puts focus back on the checkbox, and the entry's record the selection."""
    url = serve(
        leaf_page(
            "Restarted",
            '<h1>Rehearsal</h1><p id="result">The backfill copied 310 million rows.</p>'
            '<p><label>Checked <input id="tick" type="checkbox"></label></p>',
        )
    )
    page = open_page(request.getfixturevalue(engine), live_url(url))
    page.evaluate(
        """() => {
          const words = document.querySelector('#result').firstChild;
          getSelection().setBaseAndExtent(words, 4, words, 12);
          document.querySelector('#tick').focus();
        }"""
    )
    expect(page.locator("#tick")).to_be_focused()
    assert page.evaluate("getSelection().toString()") == "backfill"
    restart_under_another_runtime(page, serve)
    expect(page.locator("#tick")).to_be_focused()
    page.wait_for_function("getSelection().toString() === 'backfill'")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_reload_into_a_revision_without_the_focused_control_lands_at_the_reading(
    request, serve, engine
):
    """Focus on a checkbox of the page's own that the revision a reload brings no
    longer has comes back nowhere, so the reload lands the user at the reading place
    instead, and Tab goes on from what they read rather than from the page's top."""
    notes = "".join(f"<p>Rehearsal note {n}.</p>" for n in range(40))

    def revision(tick, mark):
        return leaf_page(
            "Restarted",
            f'<h1>Rehearsal</h1><p><a id="top" href="#top">Top</a></p>{notes}'
            f'<p id="near">The backfill copied 310 million rows.</p>{tick}'
            f'<p><a id="next" href="#next">Next</a></p>{notes}',
        ).replace(
            "</head>", f'<script type="module">window.mark = "{mark}";</script></head>'
        )

    page = open_page(
        request.getfixturevalue(engine),
        live_url(
            serve(
                revision(
                    '<p><label>Checked <input id="tick" type="checkbox"></label></p>',
                    "first",
                )
            )
        ),
    )
    tick = page.locator("#tick")
    tick.scroll_into_view_if_needed()
    tick.focus()
    expect(tick).to_be_focused()
    original_document = page.evaluate("performance.timeOrigin")
    (serve.page_dir / "index.html").write_text(revision("", "second"))
    told(page)
    page.wait_for_function(
        "(before) => performance.timeOrigin !== before", arg=original_document
    )
    wait_until_ready(page)
    expect(tick).to_have_count(0)
    page.keyboard.press("Tab")
    expect(page.locator("#next")).to_be_focused()


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
    (records/history.js) and the reload's handoff (features/version.js, `handOff`): the thread they had
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
    answer for a reload they never asked for (records/drafts.js, `beforeunload`)."""
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
    it drops the words the restarted server refused (records/drafts.js, `beforeunload`)."""
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
    has them (records/history.js)."""
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
    the thread (dom/keyboard/bindings.js, `placeHandedBack`; bootstrap.js, `typingBack`).
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
    page.add_init_script(SAYS_DRAFT_KEPT)
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
    assert not page.evaluate("window.saidDraftKept")
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
    puts them back in, as the entry's record has it (records/history.js): `r` resolves the
    thread they were on in the panel, not another, though the new document hears it
    before it has opened the view (dom/keyboard/bindings.js, `placeHandedBack`), and the
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

    # A key pressed before the replacement document has focus reaches no document of
    # the page, so nothing of Leaf hears it. Firefox gives that document focus after it
    # leaves `loading`, and loses a key pressed before its window's `focus` event,
    # which can come after `document.hasFocus()` already says true. Chromium sends no
    # such event, and its document takes the key from the start.
    page.add_init_script(
        "addEventListener('focus', () => { window.lfTestFocused = true; }, true)"
    )
    focused = (
        "window.lfTestFocused" if engine == "firefox_browser" else "document.hasFocus()"
    )
    answer_as_another_runtime(page)
    page.on("framenavigated", navigated)
    page.route("**/api/state*", state_answer)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    page.wait_for_function(f"() => document.readyState !== 'loading' && {focused}")
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
