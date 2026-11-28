"""Changes in place: what changed since a version, which a Compare in Versions marks
with a bar and `h` walks; how much changed since the user last saw the page,
which coming back to it says; and where the agent is at work while it works
(features/version.js, host/since-seen.js, panel/change-walk.js, features/margin-bars.js).

A revision is seen when it is on the page while the user is there: the tab visible and
the window holding focus. Headless browsers report every tab visible and focused, so
the tests of what the user saw set both through the platform's own readings
(`visibility`, `attention`)."""

import re
import shutil
from datetime import UTC, datetime, timedelta

import pytest
from click.testing import CliRunner
from interact_support import append_command, response_reference, wait_for
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    compare_with,
    example_media,
    expect_panel_says,
    open_page,
    panel_field,
    preview_parts,
    sending,
    show_changes,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.records import revisioning as revisioning_model
from leaf.source.render_checks import rendered
from leaf_dev.browser import PANEL_THREAD, panel_tab, scroll_settled

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
BETA = ("Beta reads one way.", "Beta reads another way.")
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


def marked_ids(page):
    return page.locator("main .lf-ins-block").evaluate_all(
        "blocks => blocks.map(b => b.id)"
    )


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


def wait_for_seen(page_dir, revisions, failure):
    wait_for(
        lambda: [
            event["revision"]
            for event in events_model.read_events(page_dir)
            if event["kind"] == "seen"
        ],
        lambda seen: seen == revisions,
        failure=failure,
    )


def test_a_comparison_marks_each_change_with_a_bar_and_h_walks_them(browser, serve):
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    revise(d, BETA)
    revise(d, DELTA)
    wait_for_revision(page, 3)
    compare_with(page, 1)
    page.keyboard.press("Escape")
    marked = page.locator("main .lf-ins-block")
    expect(marked).to_have_count(2)
    assert marked_ids(page) == ["b", "d"]
    # Each change's mark is a bar beside it, and the block keeps its own paint.
    bars = page.locator(".lf-change-bar")
    expect(bars).to_have_count(2)
    assert sorted(bars.evaluate_all("bars => bars.map(b => b.dataset.lfFor)")) == [
        "b",
        "d",
    ]
    clear = "rgba(0, 0, 0, 0)"
    expect(page.locator("#b")).to_have_css("background-color", clear)
    # The walk lands on each change in page order and comes round at the end.
    for expected in ("b", "d", "b"):
        page.keyboard.press("h")
        expect(page.locator(f"#{expected}")).to_be_focused()
    page.keyboard.press("Shift+h")
    expect(page.locator("#d")).to_be_focused()
    # The marks are annotations: Escape lets go of the change and leaves them, and `g H`
    # hides them with the rest.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(marked).to_have_count(2)
    beta = page.locator('.lf-change-bar[data-lf-for="b"]')
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect(beta).to_have_css("background-color", clear)
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect(beta).not_to_have_css("background-color", clear)
    # Both bars stand in one lane outside the marks round their block, so no ring or
    # bracket of the user's touches one; on a changed block the agent is at work on, the
    # work's bar covers the change's.
    _start(d, _comment_on(d, "b", BETA[1], revision=3)["id"], "Rewriting Beta")
    expect(page.locator(".lf-at-work-bar")).to_have_count(1)
    lane = page.evaluate(
        """() => {
          const box = (s) => document.querySelector(s).getBoundingClientRect();
          const [block, change, work] = [
            box('#b'), box('.lf-change-bar[data-lf-for="b"]'), box('.lf-at-work-bar'),
          ];
          const room = parseFloat(getComputedStyle(document.getElementById('b'))
            .getPropertyValue('--lf-band-room'));
          const [first, second] = ['.lf-change-bar[data-lf-for="b"]', '.lf-at-work-bar']
            .map((s) => document.querySelector(s));
          return {
            shared: Math.abs(work.left - change.left) < 0.5,
            clear: change.right < block.left - room,
            covers: first.parentNode === second.parentNode
              && !!(first.compareDocumentPosition(second)
                & Node.DOCUMENT_POSITION_FOLLOWING),
          };
        }"""
    )
    assert lane == {"shared": True, "clear": True, "covers": True}, lane


def test_versions_counts_the_changes_since_each_older_version(browser, serve):
    """Each version older than the one shown says before its Compare's word how many
    changes a comparison with it would mark, in the press's name too. Reopening
    Versions shows the counts it holds without asking the server again, and a pick
    that adds a change counts again. The version shown has no Compare."""
    options = PAGE.replace(
        '<p id="a">',
        '<lf-group id="g-q" label="When to ship?">'
        '<lf-options id="g"><lf-option id="g-a">Ship now</lf-option>'
        '<lf-option id="g-b">Ship later</lf-option></lf-options></lf-group>\n<p id="a">',
    )
    url = live_url(serve(options))
    d = serve.page_dir
    page = open_page(browser, url)
    stamp_page(d, revised(options, BETA), "rewrote Beta")
    stamp_page(d, revised(options, BETA, DELTA), "rewrote Delta")
    wait_for_revision(page, 3)
    page.keyboard.press("g")
    page.keyboard.press("Shift+V")
    compare = {n: page.get_by_role("button", name=f"Compare with v{n}") for n in (1, 2)}
    for n, said in ((2, "1 change"), (1, "2 changes")):
        expect(compare[n]).to_have_text(f"{said} Compare")
        expect(compare[n]).to_have_accessible_name(f"{said}, Compare with v{n}")
    expect(
        page.locator(".lf-fp-version").first.locator(".lf-fp-compare")
    ).to_have_count(0)
    views = []
    page.on("request", lambda request: "/api/view?" in request.url and views.append(1))
    page.keyboard.press("Escape")
    expect(compare[1]).to_be_hidden()
    page.keyboard.press("g")
    page.keyboard.press("Shift+V")
    expect(compare[1]).to_have_text("2 changes Compare")
    assert not views, "reopening Versions counted again with nothing changed"
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 3,
            "widget": "g",
            "action": "choose",
            "detail": {"value": ["g-a"]},
            "facts": {"answered": True},
        },
    )
    expect(compare[1]).to_have_text("3 changes Compare")
    compare[1].click()
    expect(page.locator(".lf-live")).to_contain_text("3 changes since v1")


def test_versions_counts_only_the_versions_in_view(browser, serve):
    """A count fetches its version and compares the whole page, so Versions counts
    the versions whose Compare shows in the window, and a version scrolled into view
    gets its count then. The work opening Versions sets off follows the rows on
    screen, not how many versions the session has stamped."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    for n in range(2, 16):
        stamp_page(d, revised(PAGE, (BETA[0], f"Beta reads way {n}.")), f"draft {n}")
    page = open_page(browser, url)
    page.set_viewport_size({"width": 900, "height": 420})
    views = []
    page.on("request", lambda request: "/api/view?" in request.url and views.append(1))
    page.keyboard.press("g")
    page.keyboard.press("Shift+V")
    rows = """() => {
        const presses = [...document.querySelectorAll('.lf-fp-compare')];
        const view = presses[0]?.closest('.lf-fp-view').getBoundingClientRect();
        return presses.map((press) => {
            const box = press.getBoundingClientRect();
            return {
                shown: box.bottom > view.top && box.top < view.bottom,
                said: press.querySelector('.lf-fp-changes').textContent.trim(),
            };
        });
    }"""
    page.wait_for_function(
        f"() => {{ const rows = ({rows})(); "
        "return rows.length && rows.every((row) => !row.shown || row.said); }"
    )
    in_view = page.evaluate(rows)
    shown = [row for row in in_view if row["shown"]]
    assert len(shown) < len(in_view), "every version's Compare shows; nothing to test"
    assert all(row["said"] == "1 change" for row in shown), in_view
    assert not any(row["said"] for row in in_view if not row["shown"]), in_view
    assert len(views) == len(shown), "Versions asked for counts it doesn't show"
    oldest = page.get_by_role("button", name=re.compile(r"\bCompare with v1$"))
    oldest.scroll_into_view_if_needed()
    expect(oldest).to_have_text("1 change Compare")


def test_a_change_s_place_names_the_comparison_where_the_field_does_not(browser, serve):
    """The page's field says "2 changes since v1" while a comparison stands, so a
    change's place there is its place alone. A thread open in the panel says no such
    words before its reply, so the walk's position there names the comparison's
    changes."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    revise(d, BETA)
    revise(d, DELTA)
    wait_for_revision(page, 3)
    compare_with(page, 1)
    page.keyboard.press("Escape")
    expect(page.locator("main .lf-ins-block")).to_have_count(2)
    expect(panel_field(page)).to_have_attribute("data-lf-says", "status")
    page.locator("body").focus()
    page.keyboard.press("h")
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile(r"^2 changes since v1 · 1 of 2\b")
    )
    write(panel_field(page), "Does Delta still hold?")
    with sending(page, "the page comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    view = page.locator(PANEL_THREAD)
    expect(view).to_be_visible()
    view.focus()
    page.keyboard.press("h")
    lead = page.locator(".lf-fp-field .lf-compose-placeholder-lead")
    expect(lead).to_contain_text(re.compile(r"\bChange \d of 2 since v1"))


def test_coming_back_says_how_much_changed_and_g_V_v_marks_it(browser, serve):
    """Leaving says which revision the user saw. Coming back after the agent revised
    says how much changed since the version they last saw and marks nothing, offering
    Show changes with `g V v` at the field's end. Versions names that version last seen
    and opens on it, so `g V v` marks those changes, though a newer version
    stands between. While Versions stands, the news offers no press, since there `v`
    compares whichever version the user is on."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    marked = page.locator("main .lf-ins-block")
    visibility(page, "hidden")
    wait_for_seen(d, [1], "leaving the page named no revision it showed")
    stamp_page(d, revised(PAGE, BETA), "rewrote Beta")
    revise(d, DELTA)

    visibility(page, "visible")
    expect(page.locator(".lf-live")).to_have_text("2 changes since v1")
    expect_panel_says(page, "2 changes since v1 · Show changes g V v")
    expect(marked).to_have_count(0)
    page.keyboard.press("g")
    page.keyboard.press("Shift+V")
    expect(page.locator(".lf-fp-version > .lf-fp-item:focus")).to_have_accessible_name(
        re.compile(r"^v1 \(last seen\)")
    )
    # While Versions stands, its `v` compares the version the user is on, so the news
    # offers no keys there.
    expect_panel_says(page, "2 changes since v1")
    expect_panel_says(page, "Show changes", says=False)
    page.keyboard.press("v")
    expect(marked).to_have_count(2)
    assert marked_ids(page) == ["b", "d"]
    # Once the comparison stands, the news that the press would show it goes with it,
    # read once the press has drawn, well before its moment would end.
    rendered(page)
    assert "Show changes" not in (panel_field(page).get_attribute("placeholder") or "")


def test_open_latest_says_the_keys_that_reach_it_from_where_the_user_is(browser, serve):
    """A page pinned to an older version offers Open latest at the field's end with the
    keys of Versions' own `l`: `g V l` from the page, since `g V` opens Versions, and `l`
    alone once Versions has focus."""
    url = serve(PAGE)
    d = serve.page_dir
    page = open_page(browser, url, pin=True)
    stamp_page(d, revised(PAGE, BETA), "rewrote Beta")
    expect_panel_says(page, "Open latest g V l")
    page.keyboard.press("g")
    page.keyboard.press("Shift+V")
    expect(page.locator(".lf-fp-version > .lf-fp-item:focus")).to_have_count(1)
    expect_panel_says(page, "Open latest l")


def test_on_a_touchscreen_the_news_offers_no_press(browser, serve):
    """A touchscreen shows no keys, and a press's word alone at the field's end reads as
    status rather than a control, so the news offers no press there: Versions names the
    version the user last saw, beside its Compare."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    visibility(page, "hidden")
    wait_for_seen(d, [1], "leaving the page named no revision it showed")
    stamp_page(d, revised(PAGE, BETA), "rewrote Beta")
    revise(d, DELTA)

    visibility(page, "visible")
    expect(page.locator(".lf-live")).to_have_text("2 changes since v1")
    expect_panel_says(page, "2 changes since v1")
    expect(page.locator(".lf-fp-field .lf-compose-press")).to_have_count(0)
    page.locator(".lf-fp-leaf").tap()
    panel_tab(page, "Menu").tap()
    page.locator('.lf-fp-item[data-lf-row="versions"]').tap()
    page.get_by_role("button", name="Compare with v1 (last seen)").tap()
    expect(page.locator("main .lf-ins-block")).to_have_count(2)


def test_news_s_press_goes_with_its_words_under_a_resting_pointer(browser, serve):
    """With the pointer parked on the panel, as after a return by Cmd-Tab, Show changes
    stands at the field's end while the news's words say what changed, and leaves with
    them, with no input between: news answers nothing the user did, and its words say
    why the end changed, so the panel holds no notice's press still."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    visibility(page, "hidden")
    wait_for_seen(d, [1], "leaving the page named no revision it showed")
    stamp_page(d, revised(PAGE, BETA), "rewrote Beta")
    revise(d, DELTA)
    field = panel_field(page).bounding_box()
    assert field
    page.mouse.move(field["x"] + field["width"] / 2, field["y"] + field["height"] / 2)
    show = page.locator(".lf-fp-field .lf-compose-press", has_text="Show changes")

    visibility(page, "visible")
    expect_panel_says(page, "2 changes since v1")
    expect(show).to_have_count(1)
    expect_panel_says(page, "2 changes since v1", says=False)
    expect(show).to_have_count(0)


def test_what_lands_while_the_user_works_elsewhere_counts_when_they_return(
    browser, serve
):
    """The browser beside the terminal: visible, but the user is typing elsewhere. What
    lands then is news when they come back, and `g V v` marks it."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    # Watched as it lands, a version is seen.
    stamp_page(d, revised(PAGE, BETA), "rewrote Beta")
    wait_for_revision(page, 2)
    attention(page, False)
    wait_for_seen(d, [2], "losing focus named no revision the user saw")
    # A version of its own, so counting it as seen would leave nothing to say.
    stamp_page(d, revised(PAGE, BETA, DELTA), "rewrote Delta")
    wait_for_revision(page, 3)

    attention(page, True)
    expect(page.locator(".lf-live")).to_have_text("1 change since v2")
    show_changes(page)
    expect(page.locator("main .lf-ins-block")).to_have_count(1)
    assert marked_ids(page) == ["d"]


def test_a_draft_the_user_watched_land_is_no_news_when_they_return(browser, serve):
    """A draft after the version the user last saw differs from it, but once they
    watched it land a return counts nothing; what lands while they are away is news.
    The count asks the server for the version's reading, so its requests say whether a
    return counted."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    revise(d, BETA)
    wait_for_revision(page, 2)
    attention(page, False)
    wait_for_seen(d, [2], "losing focus named no revision the user saw")
    counts = []
    page.on("request", lambda request: "api/view" in request.url and counts.append(1))
    attention(page, True)

    # The control: a revision that lands while the user is away is counted and said.
    attention(page, False)
    revise(d, DELTA)
    wait_for_revision(page, 3)
    attention(page, True)
    expect(page.locator(".lf-live")).to_have_text("2 changes since v1")
    assert len(counts) == 1, "a return to the draft the user watched counted changes"


SECTION = "<h2>Routes</h2>\n<p>The old rule.</p>\n<p>The old reason.</p>"
REWRITTEN = (
    "<h2>Who acts</h2>\n<p>The new rule.</p>\n<table>"
    "<tr><th>Finding</th><td>Leaf</td></tr><tr><th>Behind</th><td>The agent</td></tr>"
    "</table>\n<p>The new reason.</p>"
)
KEPT_TABLE = '<table id="owners"><tr><th>Owner</th><td>Leaf</td></tr></table>'


def test_a_section_rewritten_whole_is_one_change(browser, serve):
    """Rewriting a section changes every block in it, and the reader sees one edit, as
    a diff shows one hunk: each block keeps its bar, but the run has one margin entry
    and one stop of the walk. A block the revision left alone separates two changes.

    The comparison lines the two versions' blocks up in order, so the new table's
    "Leaf" cell is new, though the untouched table below holds the same word, and
    that table stays unmarked."""
    sectioned = PAGE.replace('<p id="b">Beta reads one way.</p>', SECTION).replace(
        '<p id="d">', f'{KEPT_TABLE}\n<p id="d">'
    )
    url = live_url(serve(sectioned))
    d = serve.page_dir
    # The page opens on the revision, so a rewrite that grows moves nothing on screen.
    revise(d, (SECTION, REWRITTEN), DELTA)
    page = open_page(browser, url)
    compare_with(page, 1)
    page.keyboard.press("Escape")
    # The heading, two paragraphs and four cells, and the paragraph after the gap.
    expect(page.locator("main .lf-ins-block")).to_have_count(8)
    expect(page.locator("#owners .lf-ins-block")).to_have_count(0)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="change"]')).to_have_count(2)
    for expected in ("main h2", "#d", "main h2"):
        page.keyboard.press("h")
        expect(page.locator(expected)).to_be_focused()


@pytest.mark.parametrize(
    "fold",
    [
        '<details><summary>Gamma</summary><p id="c">Gamma reads one way.</p></details>',
        # A widget's own disclosure: the settled group's row controls its options.
        '<section id="ask"><h2 id="q">Gamma?</h2><lf-options id="pick" settled>'
        '<lf-option id="keep" selected>Keep it.</lf-option>'
        '<lf-option id="c">Gamma reads one way.</lf-option></lf-options></section>',
    ],
    ids=["details", "settled-options"],
)
def test_a_change_ends_where_a_disclosure_does(browser, serve, fold):
    """A change hidden in a closed disclosure and one just after it are two changes,
    so the one the reader can see keeps a margin entry of its own."""
    folded = PAGE.replace('<p id="c">Gamma stays as it was.</p>', fold)
    url = live_url(serve(folded))
    d = serve.page_dir
    # The page opens on the revision, so a rewrite that grows moves nothing on screen.
    revise(d, ("Gamma reads one way.", "Gamma reads another way."), DELTA)
    page = open_page(browser, url)
    compare_with(page, 1)
    page.keyboard.press("Escape")
    expect(page.locator("main .lf-ins-block")).to_have_count(2)
    expect(
        page.locator('[data-lf-margin-for="d"] [data-lf-kinds~="change"]')
    ).to_be_visible()


def test_a_paragraph_removed_is_a_change_at_its_gap(browser, serve):
    """A paragraph removed with nothing in its place is a change like any other: its bar
    is the change bar at zero blocks' length, in the gap; its entry, a raised press,
    stands by the block after the gap and outlines the gap under the pointer; the walk
    stops on the gap's stand-in rather than the unchanged block, ringing the gap, and
    Enter there opens the change's card; and the entry's press opens a card over what
    follows holding the words it took out, while the page under the card holds still."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    revise(
        d,
        ('<p id="c">Gamma stays as it was.</p>\n', ""),
        ("Alpha stays as it was.", "Alpha reads another way."),
    )
    page = open_page(browser, url)
    compare_with(page, 1)
    page.keyboard.press("Escape")
    expect(page.locator("main .lf-ins-block")).to_have_count(1)
    gap = page.locator('.lf-change-bar[data-lf-gap="before"][data-lf-for="d"]')
    expect(gap).to_have_count(1)
    between = page.evaluate(
        """() => {
          const box = (s) => document.querySelector(s).getBoundingClientRect();
          const [b, d, gap] = [box('#b'), box('#d'), box('.lf-change-bar[data-lf-gap]')];
          return gap.top >= b.bottom - 1 && gap.bottom <= d.top + 1 && gap.height > 0;
        }"""
    )
    assert between, "the removal's bar doesn't stand in the gap it left"
    removal = page.locator('[data-lf-margin-for="d"] [data-lf-kinds~="change"]')
    expect(removal).to_have_css("border-top-width", "2px")
    expect(removal).not_to_have_css("box-shadow", "none")
    page.keyboard.press("h")
    expect(page.locator("#a")).to_be_focused()
    page.keyboard.press("h")
    expect(
        page.get_by_role("button", name="1 paragraph removed since v1", exact=True)
    ).to_be_focused()
    expect(page.locator(".lf-change-ring")).to_be_visible()
    rendered(page)
    expect(page.locator(".lf-proxy-ring")).to_be_hidden()
    assert page.evaluate(
        """() => {
          const box = (s) => document.querySelector(s).getBoundingClientRect();
          const [b, d, ring] = [box('#b'), box('#d'), box('.lf-change-ring')];
          return ring.top <= b.bottom && ring.bottom >= d.top && ring.bottom < d.bottom;
        }"""
    ), "the walk's ring doesn't stand round the gap"
    page.keyboard.press("Enter")
    expect(page.locator("#lf-change-card del")).to_have_text("Gamma stays as it was.")
    page.keyboard.press("Escape")
    expect(page.locator("#lf-change-card")).to_have_count(0)
    page.keyboard.press("h")
    expect(page.locator("#a")).to_be_focused()
    page.keyboard.press("Escape")

    removal.hover()
    outline = page.locator(".lf-change-outline")
    expect(outline).to_be_visible()
    assert page.evaluate(
        """() => {
          const box = (s) => document.querySelector(s).getBoundingClientRect();
          const [b, d, round] = [box('#b'), box('#d'), box('.lf-change-outline')];
          return round.top <= b.bottom && round.bottom >= d.top - 1;
        }"""
    ), "the outline doesn't stand round the gap"

    before = page.locator("#d").bounding_box()
    removal.click()
    card = page.locator("#lf-change-card")
    expect(card).to_be_visible()
    expect(removal).to_have_attribute("aria-expanded", "true")
    expect(card.locator(".lf-change-card-head")).to_have_text(
        re.compile(r"^1 paragraph removed · v1 → ")
    )
    expect(card.locator("del")).to_have_text("Gamma stays as it was.")
    assert page.locator("#d").bounding_box() == before
    page.keyboard.press("Escape")
    expect(card).to_have_count(0)


LONG = " ".join(["Lambda runs long."] * 400)
TALL = " ".join(["Mu runs on in its pane."] * 60)
FOLDED = leaf_page(
    "Since",
    f"""
<h1 id="t">Plan</h1>
<p id="a">Alpha stays.</p>
<p id="b">Beta goes.</p>
<details id="more"><summary id="s">More</summary>
<p id="first">The first goes.</p><p id="k">Kappa stays.</p><p id="last">The last goes.</p>
</details>
<p id="d">Delta reads one way.</p>
<lf-tabs id="views"><lf-tab id="notes" label="Notes"><p id="note">The only note goes.</p>
</lf-tab><lf-tab id="others" label="Others"><p id="other">Another stays.</p></lf-tab></lf-tabs>
<div id="pane" class="lf-scroll" style="max-height: 8rem; overflow-y: auto">
<p id="lead">The lead goes.</p><p id="tall">{TALL}</p></div>
<p id="long">{LONG}</p>
<p id="end">The end goes.</p>
""",
)
GAPS = """() => Object.fromEntries(
  [...document.querySelectorAll('.lf-change-bar[data-lf-gap]')].map((bar) => {
    const box = bar.getBoundingClientRect();
    return [`${bar.dataset.lfGap} ${bar.dataset.lfFor}`, [box.top, box.bottom]];
  }),
)"""
EDGES = """() => Object.fromEntries(['a', 'more', 's', 'k', 'notes'].map((id) => {
  const box = document.getElementById(id).getBoundingClientRect();
  return [id, [box.top, box.bottom]];
}))"""
RING = """() => {
  const box = document.querySelector('.lf-change-ring').getBoundingClientRect();
  return [box.top + scrollY, box.top >= 0 && box.bottom <= innerHeight];
}"""


def test_a_removal_stands_in_the_part_of_the_page_it_left(browser, serve):
    """A block removed with nothing in its place stands in the gap it left, in the part
    of the page it stood in: the paragraph before a `details` stands before the
    `details`, not inside it; the last paragraph of the `details` stands inside it,
    after the block it followed, even where the paragraph after the `details` was
    rewritten and a new element wraps them both; and a tab's only paragraph stands in
    that tab, which counts it. The walk stops on each gap's stand-in, two gaps beside
    one block included, and rings the gap, bringing it into view past a block taller
    than the window or inside a scroller, and opening a `details` only for a gap inside
    it. Each of the two entries beside one block outlines its own gap, and the preview
    of one stands by the other when the pointer moves across."""
    url = live_url(serve(FOLDED))
    revise(
        serve.page_dir,
        ('<p id="b">Beta goes.</p>\n', ""),
        ('<p id="first">The first goes.</p>', ""),
        ('<p id="last">The last goes.</p>', ""),
        ("Delta reads one way.</p>", "Delta reads another way.</p></div>"),
        ('<details id="more">', '<div id="wrap"><details id="more">'),
        ('<p id="note">The only note goes.</p>', ""),
        ('<p id="lead">The lead goes.</p>', ""),
        ('\n<p id="end">The end goes.</p>', ""),
    )
    page = open_page(browser, url)
    compare_with(page, 1)
    page.keyboard.press("Escape")
    expect(page.locator('[data-lf-carry="tab-notes"] .lf-tabdiff')).to_have_text("Δ1")
    expect(page.locator('[data-lf-carry="tab-others"] .lf-tabdiff')).to_have_text("")

    pane = page.locator("#pane")
    pane.evaluate("pane => { pane.scrollTop = pane.scrollHeight; }")
    stops = []
    for _ in range(8):
        page.keyboard.press("h")
        rendered(page)
        scroll_settled(page)
        on_block = page.evaluate("() => document.activeElement.id")
        stops.append(on_block or page.evaluate(RING))
        if len(stops) == 1:
            expect(page.locator("#more")).not_to_have_attribute("open", "")
        if len(stops) == 6:
            assert pane.evaluate("pane => pane.scrollTop") < 20, "the pane kept its gap"
    assert stops[3] == "d", stops
    gaps_walked = [stop for stop in stops if stop != "d"]
    tops = [top for top, _ in gaps_walked]
    assert tops[:6] == sorted(tops[:6]) and len(set(tops[:6])) == 6, stops
    assert tops[6] == tops[0], "the walk didn't come round to the first gap"
    assert all(shown for _, shown in gaps_walked), (
        f"a gap the walk is on is out of view: {stops}"
    )
    expect(page.locator("#more")).to_have_attribute("open", "")
    page.keyboard.press("Escape")

    # A bar stands only while its block is near the window.
    page.evaluate("() => scrollTo(0, 0)")
    near = ["after k", "before k", "before more", "in notes"]
    for gap in near:
        side, at = gap.split()
        expect(
            page.locator(f'[data-lf-gap="{side}"][data-lf-for="{at}"]')
        ).to_be_attached()
    gaps, edges = page.evaluate(GAPS), page.evaluate(EDGES)
    assert set(near) <= set(gaps), gaps
    a, more, summary, kappa, notes = (
        edges[key] for key in ("a", "more", "s", "k", "notes")
    )
    # Each bar stands between the boxes on either side of its gap, or in its element.
    assert a[1] - 1 <= gaps["before more"][0] and gaps["before more"][1] <= more[0] + 1
    assert summary[1] - 1 <= gaps["before k"][0] and gaps["before k"][1] <= kappa[0] + 1
    assert kappa[1] - 1 <= gaps["after k"][0] and gaps["after k"][1] <= more[1] + 1
    assert notes[0] - 1 <= gaps["in notes"][0]

    outline = page.locator(".lf-change-outline:not(.lf-change-ring)")
    entries = page.locator('[data-lf-margin-for="k"] [data-lf-kinds~="change"]')
    expect(entries).to_have_count(2)
    preview = page.locator("#lf-preview")
    tops = []
    for index in range(2):
        entries.nth(index).hover()
        expect(outline).to_be_visible()
        # The first entry's preview stands, so the second takes it over at once.
        expect(preview).to_be_visible()
        tops.append(outline.bounding_box()["y"])
    assert tops[0] != tops[1], "both entries outline the same gap"


def test_a_change_s_card_reads_it_in_order(browser, serve):
    """A change's card reads it in the order the reader met it: a paragraph the revision
    took out between two it edited stands struck between their word diffs, and a new
    paragraph reads as inserted. Assistive technology reaches the card as the entry's
    disclosure, and a redline taller than the window scrolls inside the card."""
    long = " ".join(["Beta reads one way."] * 400)
    url = live_url(serve(PAGE.replace("Beta reads one way.", long)))
    revise(
        serve.page_dir,
        ("Alpha stays as it was.", "Alpha reads another way."),
        (f'<p id="b">{long}</p>\n', ""),
        ("Gamma stays as it was.</p>", "Gamma reads another way.</p>\n<p>Epsilon.</p>"),
    )
    page = open_page(browser, url)
    compare_with(page, 1)
    page.keyboard.press("Escape")
    entry = page.locator('[data-lf-margin-for="a"] [data-lf-kinds~="change"]')
    expect(entry).to_have_attribute("aria-expanded", "false")
    entry.click()
    card = page.get_by_role("group", name="2 paragraphs edited, 1 replaced by 1")
    expect(card).to_be_visible()
    expect(entry).to_have_attribute("aria-expanded", "true")
    lines = card.locator(".lf-change-card-block")
    expect(lines).to_have_count(4)
    expect(lines.nth(0).locator("del")).to_have_text("Alpha stays as it was.")
    expect(lines.nth(0).locator("ins")).to_have_text("Alpha reads another way.")
    expect(lines.nth(1).locator("del")).to_have_text(long)
    expect(lines.nth(2)).to_contain_text("Gamma")
    expect(lines.nth(3).locator("ins")).to_have_text("Epsilon.")
    assert card.evaluate(
        "card => card.offsetHeight <= innerHeight && card.scrollHeight > card.clientHeight"
    ), "the long redline doesn't scroll inside a card that fits the window"


def test_a_version_says_which_comments_it_was_saved_after(browser, serve):
    """Comparing a version with the one before it, each change's ⇄ entry says under
    what it did which of the user's comments waited while that version was saved,
    with the words each then had: not one the agent had answered before, wherever on
    the page it stands, and the change walk says the same to a listener. A comparison
    across several versions says nothing of it, since nothing knows which version made
    which change (features/change-provenance.js)."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    # The answered comment stands on the last paragraph. On `c` its entry would stand
    # 65 px under the title's ⇄ and the waiting comment's entry just above it, so no
    # place would hold the preview's lines clear of both, and it would cut the quote
    # (annotations/preview.js, `stand`).
    asked = _comment_on(
        d, "d", "Delta reads one way.", text="Beta first?\nIt reads one way."
    )
    stamp_page(d, revised(PAGE, BETA), "rewrote Beta")
    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(d, asked),
            "--title",
            "Beta wording",
            "--text",
            "Beta reads another way now.",
        ],
    )
    assert replied.exit_code == 0, replied.output
    _comment_on(d, "t", "Plan", revision=2, text="Is the title right?")
    revise(d, ('<h1 id="t">Plan</h1>', '<h1 id="t">Plan for spring</h1>'))
    page = open_page(browser, url)
    wait_for_revision(page, 3)
    entries = page.locator('[data-lf-kinds~="change"]')
    compare_with(page)
    expect(entries).to_have_count(1)
    parts = preview_parts(entries.first)
    assert parts[-2:] == [
        "Draft saved while your comment waited:",
        "“Is the title right?”",
    ], parts
    page.keyboard.press("h")
    expect(page.locator(".lf-live")).to_contain_text(
        "Draft saved while your comment waited: “Is the title right?”"
    )
    compare_with(page, 1)
    page.keyboard.press("Escape")
    expect(entries).to_have_count(2)
    for at in range(2):
        assert not any("saved" in part for part in preview_parts(entries.nth(at)))


def test_a_change_with_no_card_still_says_what_its_version_was_saved_after(
    browser, serve
):
    """A version that restates the option the user chose changes its state and none of
    its words, so its change opens no card, but its ⇄ entry still says what the
    version was saved after: that is the comparison's reading, not the card's."""
    options = PAGE.replace(
        '<p id="d">',
        '<lf-group id="g-q" label="When to ship?">'
        '<lf-options id="g"><lf-option id="g-a">Ship now</lf-option>'
        '<lf-option id="g-b">Ship later</lf-option></lf-options></lf-group>\n<p id="d">',
    )
    url = live_url(serve(options))
    d = serve.page_dir
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g",
            "action": "choose",
            "detail": {"value": ["g-a"]},
            "facts": {"answered": True},
        },
    )
    _comment_on(d, "t", "Plan", text="Should we wait?")
    stamp_page(
        d,
        options.replace('<lf-option id="g-a">', '<lf-option id="g-a" restated>'),
        "Asked again",
    )
    page = open_page(browser, url)
    wait_for_revision(page, 2)
    compare_with(page, 1)
    page.keyboard.press("Escape")
    entries = page.locator('[data-lf-kinds~="change"]')
    expect(entries).to_have_count(1)
    expect(entries).not_to_have_attribute("aria-controls", "lf-change-card")
    assert preview_parts(entries.first)[-2:] == [
        "v2 saved while your comment waited:",
        "“Should we wait?”",
    ]


def test_a_version_quotes_each_waiting_message_as_its_thread_shows_it(browser, serve):
    """The line quotes a message as its thread reads it: a code block opening with
    words shows both its lines, a suggestion its words literally, and a picture with
    no words the name its thread gives it."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    _comment_on(d, "t", "Plan", text="```first words\nsecond words\n```")
    append_command(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "**literal stars**",
            "suggestion": True,
            "anchor": {"section": "a", "quote": "Alpha stays as it was."},
        },
    )
    # A picture the user pasted alone, as an upload leaves it.
    (d / "media").mkdir(exist_ok=True)
    shutil.copy(example_media() / "051bee487bfb5d13.png", d / "media")
    _comment_on(
        d,
        "c",
        "Gamma stays as it was.",
        text="![Attached image](/media/051bee487bfb5d13.png)",
    )
    revise(d, ('<h1 id="t">Plan</h1>', '<h1 id="t">Plan for spring</h1>'))
    page = open_page(browser, url)
    wait_for_revision(page, 2)
    entries = page.locator('[data-lf-kinds~="change"]')
    compare_with(page)
    expect(entries).to_have_count(1)
    assert preview_parts(entries.first)[-4:] == [
        "Draft saved while your 3 comments waited:",
        "“first words second words”",
        "“**literal stars**”",
        "“Attached image”",
    ]


def test_a_version_quotes_a_comment_taken_back_since_in_the_words_it_had(
    browser, serve
):
    """A comment the user took back after a version went live waited while it was
    saved all the same, and the line quotes the words it had then, which no thread
    shows any longer."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    asked = _comment_on(d, "b", "Beta reads one way.", text="Is Beta right?")
    revise(d, BETA)
    append_command(d, {"kind": "undo", "author": "user", "undoes": asked["id"]})
    page = open_page(browser, url)
    wait_for_revision(page, 2)
    entries = page.locator('[data-lf-kinds~="change"]')
    compare_with(page)
    expect(entries).to_have_count(1)
    assert preview_parts(entries.first)[-2:] == [
        "Draft saved while your comment waited:",
        "“Is Beta right?”",
    ]


def test_a_version_saved_while_a_deletion_waited_says_the_message_was_deleted(
    browser, serve
):
    """A comment the user deleted by rewriting it to nothing waits in its deletion,
    and a version saved meanwhile says the message as its thread then read it:
    deleted."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    asked = _comment_on(d, "b", "Beta reads one way.", text="Is Beta right?")
    append_command(
        d, {"kind": "edit", "author": "user", "message": asked["id"], "text": ""}
    )
    revise(d, BETA)
    page = open_page(browser, url)
    wait_for_revision(page, 2)
    entries = page.locator('[data-lf-kinds~="change"]')
    compare_with(page)
    expect(entries).to_have_count(1)
    assert preview_parts(entries.first)[-2:] == [
        "Draft saved while your comment waited:",
        "“Deleted message”",
    ]


def _comment_on(d, section, words, revision=1, text="Say which way?"):
    return append_command(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": revision,
            "text": text,
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
    expect(bars).to_have_attribute("data-lf-for", "b")
    stalled = page.evaluate(
        """async () => (await (await fetch('/api/state')).json()).workflows
          .filter(w => w.state === 'blocked' && w.reason === 'quiet').length"""
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
            "subject": {"kind": "element", "id": "c"},
            "title": "Rewrite Gamma",
        },
    )
    bars = page.locator(".lf-at-work-bar")
    # The page has taken in the to-do, which is open with nothing running on it yet.
    told(page)
    expect(bars).to_have_count(0)
    _start(d, todo["id"], "Rewriting Gamma")
    expect(bars).to_have_count(1)
    expect(bars).to_have_attribute("data-lf-for", "c")


def test_the_bar_beside_a_list_item_stands_clear_of_its_marker(browser, serve):
    """The browser draws a list item's marker outside the item's box, in its list's
    inset, so the bar beside an item, or beside a block in one, stands beyond that
    inset rather than across the marker, as it does beside an item's block that a
    `display: contents` wrapper holds. An item in a list laid out as a grid of cards
    keeps its bar beside its own card."""
    url = live_url(
        serve(
            leaf_page(
                "List",
                """
<ul id="l">
  <li id="i">An item.</li>
  <li><p id="p">A paragraph in an item.</p></li>
  <li><div id="w" style="display: contents"><p>A wrapped paragraph.</p></div></li>
</ul>
<ul id="g" style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;
    list-style: none; padding: 0">
  <li id="g1">First card.</li>
  <li id="g2">Second card.</li>
</ul>
""",
            )
        )
    )
    d = serve.page_dir
    page = open_page(browser, url)
    for section, words in (
        ("i", "An item."),
        ("p", "A paragraph in an item."),
        ("g2", "Second card."),
    ):
        _start(d, _comment_on(d, section, words)["id"], "Rewording it")
    # A to-do on the wrapper is about the wrapper itself, where a quote in it would be
    # about the paragraph holding the words.
    wrapper = {"kind": "element", "id": "w"}
    todo = {"kind": "todo", "author": "agent", "agent": "Claude", "title": "Reword it"}
    _start(d, append_command(d, {**todo, "subject": wrapper})["id"], "Rewording it")
    expect(page.locator(".lf-at-work-bar")).to_have_count(4)
    placed = page.evaluate(
        """() => {
          const box = (s) => document.querySelector(s).getBoundingClientRect();
          const bar = (id) => box(`.lf-at-work-bar[data-lf-for="${id}"]`);
          const [list, first, second] = [box('#l'), box('#g1'), box('#g2')];
          return {
            clear: ['i', 'p', 'w'].map(
              (id) => [id, bar(id).right <= list.left && bar(id).left > 0],
            ),
            beside: bar('g2').right <= second.left && bar('g2').left > first.right,
          };
        }"""
    )
    for target, clear in placed["clear"]:
        assert clear, (
            f"#{target}'s bar stands off the list's start or across its marker"
        )
    assert placed["beside"], "a grid card's bar stands away from its own card"
