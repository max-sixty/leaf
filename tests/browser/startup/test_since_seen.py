"""Changes in place: what a revision changed since the user was last shown the page,
marked when they come back to it and walked with `h`, and where the agent is at work
while it works (since-seen.js, change-walk.js, at-work.js)."""

from interact_support import append_command, wait_for
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import open_page

from leaf import event_log as events_model
from leaf import revisioning as revisioning_model

PAGE = leaf_page(
    "Since",
    """
<h1 id="t">Plan</h1>
<p id="a">Alpha stays as it was.</p>
<p id="b">Beta reads one way.</p>
<p id="c">Gamma stays as it was.</p>
<p id="d">Delta reads one way.</p>
""",
)


def revise(page_dir, *edits):
    source = page_dir / "index.html"
    html = source.read_text()
    for old, new in edits:
        html = html.replace(old, new)
    source.write_text(html)
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None
    return activated.revision


def visibility(page, state):
    """Hide or show the tab, the lifecycle input Chromium's headless shell cannot
    produce on its own (test_freshness.py does the same)."""
    page.evaluate(
        """state => {
          window.__lfTestVisibility = state;
          Object.defineProperty(document, 'visibilityState', {
            configurable: true,
            get: () => window.__lfTestVisibility,
          });
          document.dispatchEvent(new Event('visibilitychange'));
        }""",
        state,
    )


def seen_revisions(page_dir):
    return [
        event["revision"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "seen"
    ]


def test_coming_back_marks_what_changed_since_and_h_walks_it(browser, serve):
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    marked = page.locator("main .lf-ins-block")
    # Nothing to compare on a first visit; leaving says which revision was shown.
    expect(marked).to_have_count(0)
    visibility(page, "hidden")
    wait_for(
        lambda: seen_revisions(d),
        lambda seen: seen == [1],
        failure="leaving the page named no revision it showed",
    )

    revise(d, ("Beta reads one way.", "Beta reads another way."))
    revise(d, ("Delta reads one way.", "Delta reads another way."))

    # Coming back reads what the agent revised meanwhile, and marks it.
    visibility(page, "visible")
    expect(marked).to_have_count(2)
    assert marked.evaluate_all("blocks => blocks.map(b => b.id)") == ["b", "d"]
    # The walk lands on each change in page order and comes round at the end.
    for expected in ("b", "d", "b"):
        page.keyboard.press("h")
        expect(page.locator(f"#{expected}")).to_be_focused()
    page.keyboard.press("Shift+h")
    expect(page.locator("#d")).to_be_focused()
    # The marks stand until the reader stops them: Escape lets go of the change it is
    # on, and the next takes the marks off.
    page.keyboard.press("Escape")
    expect(marked).to_have_count(2)
    page.keyboard.press("Escape")
    expect(marked).to_have_count(0)


def test_the_agent_at_work_on_a_passage_marks_its_place(browser, serve):
    url = live_url(serve(PAGE))
    d = serve.page_dir
    comment = append_command(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Say which way?",
            "anchor": {"section": "b", "quote": "Beta reads one way."},
        },
    )
    page = open_page(browser, url)
    at_work = page.locator("[data-lf-at-work]")
    # Delivered is not at work: the mark waits for the agent to start.
    expect(at_work).to_have_count(0)
    append_command(
        d,
        {
            "kind": "start",
            "author": "agent",
            "agent": "Claude",
            "item": comment["id"],
            "text": "Rewriting Beta",
        },
    )
    expect(at_work).to_have_count(1)
    expect(at_work).to_have_id("b")
    append_command(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": comment["id"],
            "responds": comment["id"],
            "revision": 1,
            "text": "The other way.",
        },
    )
    expect(at_work).to_have_count(0)
