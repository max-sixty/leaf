"""Changes in place: what changed since the version the user last saw, marked when they
come back to the page and walked with `h`, and where the agent is at work while it
works (since-seen.js, change-walk.js, margin-bars.js).

A revision is seen when it is on the page while the user is there: the tab visible and
the window holding focus, and the marks count from the newest version stamped at or
before it. Headless browsers report every tab visible and focused, so these tests set
both through the platform's own readings (`visibility`, `attention`)."""

from datetime import UTC, datetime, timedelta

from interact_support import append_command, wait_for
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import executable_revision, live_url
from render_cases_navigation import _publish
from render_harness import compare_with, open_page, wait_for_revision

from leaf import event_log as events_model
from leaf import publishing as publishing_model
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
ALPHA = ("Alpha stays as it was.", "Alpha reads another way.")
BETA = ("Beta reads one way.", "Beta reads another way.")
GAMMA = ("Gamma stays as it was.", "Gamma reads another way.")
DELTA = ("Delta reads one way.", "Delta reads another way.")


def revised(html, *edits):
    for old, new in edits:
        html = html.replace(old, new)
    return html


def revise(page_dir, *edits):
    source = page_dir / "index.html"
    source.write_text(revised(source.read_text(), *edits))
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None
    return activated.revision


def stamp(page_dir, note):
    """Make the live revision the next public version, as `leaf page stamp` does."""
    return publishing_model.cmd_stamp(page_dir, note)["version"]


def visibility(page, state):
    """Hide or show the tab (test_freshness.py does the same)."""
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


def attention(page, focused):
    """Give the window's focus to another application, as typing in a terminal beside
    the browser does, or take it back."""
    page.evaluate(
        """focused => {
          document.hasFocus = () => focused;
          window.dispatchEvent(new Event(focused ? 'focus' : 'blur'));
        }""",
        focused,
    )


def seen_revisions(page_dir):
    return [
        event["revision"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "seen"
    ]


def wait_for_seen(page_dir, revisions, failure):
    wait_for(
        lambda: seen_revisions(page_dir),
        lambda seen: seen == revisions,
        failure=failure,
    )


def marked_ids(page):
    return page.locator("main .lf-ins-block").evaluate_all(
        "blocks => blocks.map(b => b.id)"
    )


def test_coming_back_marks_what_changed_since_and_h_walks_it(browser, serve):
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    marked = page.locator("main .lf-ins-block")
    # Nothing to compare on a first visit; leaving says which revision was seen.
    expect(marked).to_have_count(0)
    visibility(page, "hidden")
    wait_for_seen(d, [1], "leaving the page named no revision it showed")

    revise(d, BETA)
    revise(d, DELTA)

    # Coming back reads what the agent revised meanwhile, and marks it.
    visibility(page, "visible")
    expect(marked).to_have_count(2)
    assert marked_ids(page) == ["b", "d"]
    # The walk lands on each change in page order and comes round at the end.
    for expected in ("b", "d", "b"):
        page.keyboard.press("h")
        expect(page.locator(f"#{expected}")).to_be_focused()
    page.keyboard.press("Shift+h")
    expect(page.locator("#d")).to_be_focused()
    # Each change's mark is a bar beside it, and the block keeps its own paint.
    bars = page.locator(".lf-change-bar")
    expect(bars).to_have_count(2)
    assert sorted(bars.evaluate_all("bars => bars.map(b => b.dataset.for)")) == [
        "b",
        "d",
    ]
    clear = "rgba(0, 0, 0, 0)"
    expect(page.locator("#b")).to_have_css("background-color", clear)
    # The marks are annotations: Escape lets go of the change and leaves them, and `o`
    # hides them with the rest.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(marked).to_have_count(2)
    beta = page.locator('.lf-change-bar[data-for="b"]')
    page.keyboard.press("o")
    expect(beta).to_have_css("background-color", clear)
    page.keyboard.press("o")
    expect(beta).not_to_have_css("background-color", clear)
    # A changed block the agent is at work on shows both bars, the change's nearer it.
    _start(d, _comment_on(d, "b", BETA[1], revision=3)["id"], "Rewriting Beta")
    expect(page.locator(".lf-at-work-bar")).to_have_count(1)
    lanes = page.evaluate(
        """() => {
          const box = (s) => document.querySelector(s).getBoundingClientRect();
          const [block, change, work] = [
            box('#b'), box('.lf-change-bar[data-for="b"]'), box('.lf-at-work-bar'),
          ];
          return change.right <= block.left && work.right <= change.left
            && change.top < block.bottom && change.bottom > block.top;
        }"""
    )
    assert lanes, "the change bar and the at-work bar don't stand in lanes of their own"


def test_what_lands_while_the_user_works_elsewhere_is_marked_when_they_return(
    browser, serve
):
    """The browser beside the terminal: visible, but the user is typing elsewhere."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    marked = page.locator("main .lf-ins-block")

    # Watched as it lands, a revision only flashes.
    (d / "index.html").write_text(revised(PAGE, BETA))
    wait_for_revision(page, 2)
    expect(marked).to_have_count(0)

    # Focus goes to another application: what the user saw is said as they go.
    attention(page, False)
    wait_for_seen(d, [2], "losing focus named no revision the user saw")
    (d / "index.html").write_text(revised(PAGE, BETA, DELTA))
    wait_for_revision(page, 3)
    expect(marked).to_have_count(0)

    # The marks count from the version the user last saw, so the draft they watched
    # land is marked with the one they missed.
    attention(page, True)
    page.wait_for_function(
        "() => [...document.querySelectorAll('main .lf-ins-block')]"
        ".map(b => b.id).join() === 'b,d'"
    )
    # A glance at the terminal that brings nothing new keeps the marks.
    attention(page, False)
    wait_for_seen(d, [2, 3], "losing focus again named no revision the user saw")
    attention(page, True)
    page.wait_for_timeout(300)
    assert marked_ids(page) == ["b", "d"]
    # Nor does a draft landing while they are away: no newer version has been seen.
    attention(page, False)
    (d / "index.html").write_text(revised(PAGE, BETA, DELTA, ALPHA))
    wait_for_revision(page, 4)
    attention(page, True)
    page.wait_for_function(
        "() => [...document.querySelectorAll('main .lf-ins-block')]"
        ".map(b => b.id).join() === 'a,b,d'"
    )
    # Once they have seen a newer version, the next return counts from it.
    assert stamp(d, "Second plan") == 2
    attention(page, False)
    wait_for_seen(d, [2, 3, 4], "losing focus named no revision the user saw")
    (d / "index.html").write_text(revised(PAGE, BETA, DELTA, ALPHA, GAMMA))
    wait_for_revision(page, 5)
    attention(page, True)
    page.wait_for_function(
        "() => [...document.querySelectorAll('main .lf-ins-block')]"
        ".map(b => b.id).join() === 'c'"
    )


def test_a_chosen_comparison_outranks_the_one_offered(browser, serve):
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    visibility(page, "hidden")
    wait_for_seen(d, [1], "leaving the page named no revision it showed")
    _publish(d, 2, revised(PAGE, BETA), "Beta")
    revise(d, BETA, DELTA)

    visibility(page, "visible")
    expect(page.locator("main .lf-ins-block")).to_have_count(2)
    # The reader's own base replaces the offered one.
    compare_with(page, 2)
    page.wait_for_function(
        "() => [...document.querySelectorAll('main .lf-ins-block')]"
        ".map(b => b.id).join() === 'd'"
    )


def test_an_offer_follows_what_another_tab_says_it_saw(browser, serve):
    """A tab's first reading can come before another tab's departing send lands; the
    marks it offered then follow the server's reading as it catches up."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    append_command(d, {"kind": "seen", "author": "user", "revision": 1})
    _publish(d, 2, revised(PAGE, BETA), "Beta")
    _publish(d, 3, revised(PAGE, BETA, DELTA), "Delta")
    page = open_page(browser, url)
    marked = page.locator("main .lf-ins-block")
    expect(marked).to_have_count(2)
    # Another tab saw v2: only what came after it stays marked.
    append_command(d, {"kind": "seen", "author": "user", "revision": 2})
    page.wait_for_function(
        "() => [...document.querySelectorAll('main .lf-ins-block')]"
        ".map(b => b.id).join() === 'd'"
    )
    # And once it saw v3, the page itself, nothing is.
    append_command(d, {"kind": "seen", "author": "user", "revision": 3})
    expect(marked).to_have_count(0)


def test_an_offer_that_finds_nothing_says_nothing(browser, serve):
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    visibility(page, "hidden")
    wait_for_seen(d, [1], "leaving the page named no revision it showed")
    # A revision that changes no words the page shows.
    revise(d, ("</main>", "<!-- a note to self --></main>"))
    visibility(page, "visible")
    wait_for_revision(page, 2)
    page.wait_for_timeout(500)
    expect(page.locator("main .lf-ins-block")).to_have_count(0)
    assert "No text changes" not in (page.locator(".lf-live").text_content() or "")


def test_a_revision_that_reloads_the_page_is_marked_in_the_new_document(browser, serve):
    """A revision whose code changed arrives as a fresh document, which can't flash
    what changed, so the new document marks it."""
    d_url = serve(executable_revision(PAGE, "one"))
    d = serve.page_dir
    page = open_page(browser, live_url(d_url))
    (d / "index.html").write_text(executable_revision(revised(PAGE, BETA), "two"))
    page.wait_for_function("() => window.__leafRevisionMark === 'two'")
    expect(page.locator("main .lf-ins-block")).to_have_count(1)
    assert marked_ids(page) == ["b"]


def _comment_on(d, section, words, revision=1):
    return append_command(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": revision,
            "text": "Say which way?",
            "anchor": {"section": section, "quote": words},
        },
    )


def _start(d, item, text, ts=None):
    event = {"kind": "start", "author": "agent", "agent": "Claude", "item": item}
    if ts is None:
        return append_command(d, {**event, "text": text})
    # A start long past, as a turn that went quiet left it.
    return events_model.append_event(
        d,
        {**event, "text": text, "id": "stalled1", "ts": ts, "attention": False},
    )


def test_the_agent_at_work_on_a_passage_marks_its_place(browser, serve):
    url = live_url(serve(PAGE))
    d = serve.page_dir
    comment = _comment_on(d, "b", "Beta reads one way.")
    quiet = _comment_on(d, "d", "Delta reads one way.")
    page = open_page(browser, url)
    bars = page.locator(".lf-at-work-bar")
    # Delivered is not at work: the bar waits for the agent to start.
    expect(bars).to_have_count(0)
    # Work gone quiet is not shown as under way.
    long_ago = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    _start(d, quiet["id"], "Rewriting Delta", ts=long_ago)
    _start(d, comment["id"], "Rewriting Beta")
    expect(bars).to_have_count(1)
    expect(bars).to_have_attribute("data-for", "b")
    stalled = page.evaluate(
        """async () => (await (await fetch('/api/state')).json()).workflows
          .filter(w => w.at_work && w.condition?.kind === 'stale').length"""
    )
    assert stalled == 1, "the quiet start was not read as work gone quiet"
    # The bar stands in the margin beside its block and takes no room from it.
    beside = page.evaluate(
        """() => {
          const bar = document.querySelector('.lf-at-work-bar').getBoundingClientRect();
          const block = document.getElementById('b').getBoundingClientRect();
          return bar.right <= block.left && bar.top < block.bottom
            && bar.bottom > block.top;
        }"""
    )
    assert beside
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
    expect(bars).to_have_count(0)


def test_a_to_do_running_on_an_element_marks_it(browser, serve):
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    todo = append_command(
        d,
        {
            "kind": "todo",
            "author": "agent",
            "agent": "Claude",
            "owner": "agent",
            "subject": {"kind": "element", "id": "c"},
            "title": "Rewrite Gamma",
        },
    )
    bars = page.locator(".lf-at-work-bar")
    page.wait_for_timeout(300)
    # Open, but nothing running on it yet.
    expect(bars).to_have_count(0)
    _start(d, todo["id"], "Rewriting Gamma")
    expect(bars).to_have_count(1)
    expect(bars).to_have_attribute("data-for", "c")
