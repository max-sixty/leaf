"""When a starting page presents and opens interaction: the first replay, controls that
wait for it, and the readable page a startup fault leaves."""

import itertools
import re

import pytest
from interact_support import append_carried_log_record, append_command, wait_for
from playwright.sync_api import expect
from render_cases_interaction import SHORT_SUGGESTION, SUGGESTION_PAGE
from render_cases_layout import SHADOWED_DIFF
from render_cases_navigation import FIRST_PRESENTATION, _publish
from render_cases_widgets import (
    CHART_PAGE,
    GENERIC_VISUAL_LAYER,
    GENERIC_VISUAL_PAGE,
    visual_widgets,
)
from render_harness import (
    EXAMPLES,
    LONG_PAGE,
    consume_browser_errors,
    expect_obligations_answered,
    expect_panel_offers,
    is_problem,
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
)

from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.render_checks import wait_until_ready
from leaf.render_gate.page_code import run_page_code

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
          };
        }"""
    )
    assert tab_store == {
        "read": {"available": False, "value": None},
        "wrote": False,
        "keys": [],
        "where": {"store": "session", "key": "refused"},
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
            """<lf-ask id="startup-decision"><h2>Startup choice</h2>
<lf-options id="startup-choice" choose>
  <lf-option id="startup-a">First</lf-option>
  <lf-option id="startup-b">Second</lf-option>
</lf-options></lf-ask>
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
    expect(page.locator("#startup-a")).not_to_have_attribute("chosen", "")
    suggestion_accept = page.locator("[data-lf-margin-for='sug'] .lf-sug-accept")
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
    source = next(path for path in EXAMPLES if path.stem == "notification-playground")
    url = serve(source)
    held = []
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    watched(page)
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(url, wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the first state response"
    playground = page.locator("#notification-playground")
    expect(playground.locator(".lf-playground-controls")).to_be_visible()
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
    dangerous interval deterministic: discussion stays available, but the On me mark
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
    # The mark stands on every page, and claims no count before the log has answered:
    # not the authored suggestion's 1, which the log has already decided.
    on_me = page.locator(".lf-fp-on-user")
    expect(on_me).to_have_attribute("title", "On me")
    # The blanket answer claims no action before the first state answer.
    expect_panel_offers(page, "blanket:accept", offered=False)

    on_me = page.locator(".lf-fp-on-user")
    expect(on_me).to_be_enabled()
    on_me.click()
    panel_settled(page, view="queue")
    # The page's field takes words while the first state answer is still held.
    expect(page_comment(page)).to_be_editable()
    page.keyboard.press("Escape")

    held.pop(0).continue_()
    wait_until_ready(page)
    expect(page.locator("#sug")).to_have_attribute("data-lf-state", "accept")
    # Nothing waits on the user, which the mark says by counting nothing.
    expect(on_me).to_have_attribute("title", "On me")
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
        page.goto(url, wait_until="load")
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
            panel_menu(page).locator('.lf-fp-item[data-row="versions"]')
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


def test_a_tab_reloads_into_the_runtime_its_restarted_server_runs(browser, serve):
    """A server restarted under another Leaf runs another runtime, whose state the
    tab's code may misread. The tab refuses that server's answer, asks its source, and
    reloads onto the document the server now serves (`runtime_selection.py`)."""
    page = open_page(
        browser, serve(leaf_page("Restarted", "<h1>Readable authored content</h1>"))
    )
    page.evaluate("() => { window.lfSameDocument = true; }")
    restarted = {"answers": True}

    # The server's answers name another runtime until its source has said so once,
    # which is the reading the reload lands on.
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

    page.route("**/api/state", another_runtime)
    page.route("**/registry.json", another_runtime)
    with page.expect_navigation():
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    wait_until_ready(page)
    assert page.evaluate("() => window.lfSameDocument") is None


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
    page.goto(serve(SHORT_SUGGESTION), wait_until="load")
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
    page.goto(serve(SHORT_SUGGESTION), wait_until="load")
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
        page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
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
                    '<lf-options id="ship" choose><lf-option id="now">Now</lf-option>'
                    '<lf-option id="later">Later</lf-option></lf-options>',
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
    # Firefox may also classify the loopback host as a bounce tracker during
    # navigation. That browser privacy notice says nothing about page startup.
    errors = consume_browser_errors(
        page, "Loading failed for the module", "classified as a bounce tracker"
    )
    assert any(is_problem(error, "Loading failed for the module") for error in errors)
    assert not page.lf_errors
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "error"
    ]
