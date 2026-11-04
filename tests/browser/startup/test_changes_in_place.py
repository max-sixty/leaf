"""Changes in place: what changed since a version, which `v` or a Compare in Versions
marks with a bar and `h` walks, and where the agent is at work while it works
(version.js, change-walk.js, margin-bars.js)."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from interact_support import append_command
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import compare_with, open_page, stamp_page, wait_for_revision

from leaf import event_log as events_model
from leaf import revisioning as revisioning_model
from leaf.render_checks import rendered
from leaf_dev.browser import scroll_settled

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
    # The marks are annotations: Escape lets go of the change and leaves them, and `o`
    # hides them with the rest.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(marked).to_have_count(2)
    beta = page.locator('.lf-change-bar[data-lf-for="b"]')
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
            box('#b'), box('.lf-change-bar[data-lf-for="b"]'), box('.lf-at-work-bar'),
          ];
          return change.right <= block.left && work.right <= change.left
            && change.top < block.bottom && change.bottom > block.top;
        }"""
    )
    assert lanes, "the change bar and the at-work bar don't stand in lanes of their own"


def test_v_marks_what_changed_since_the_latest_version_and_takes_marks_off(
    browser, serve
):
    """`v` compares with the newest version older than the one being read, and takes
    any comparison off again, one a Compare in Versions started included."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    stamp_page(d, revised(PAGE, BETA), "rewrote Beta")
    wait_for_revision(page, 2)
    revise(d, DELTA)
    wait_for_revision(page, 3)
    marked = page.locator("main .lf-ins-block")
    # Since v2, not v1: only Delta changed.
    page.keyboard.press("v")
    expect(page.locator('.lf-change-bar[data-lf-for="d"]')).to_have_count(1)
    assert marked_ids(page) == ["d"]
    page.keyboard.press("v")
    expect(marked).to_have_count(0)
    # A screen reader hears the marks go.
    expect(page.locator(".lf-live")).to_have_text("Changes hidden")
    compare_with(page, 1)
    page.keyboard.press("Escape")
    expect(marked).to_have_count(2)
    page.keyboard.press("v")
    expect(marked).to_have_count(0)


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
        '<lf-ask id="ask"><h2 id="q">Gamma?</h2><lf-options id="pick" choose settled>'
        '<lf-option id="keep" chosen>Keep it.</lf-option>'
        '<lf-option id="c">Gamma reads one way.</lf-option></lf-options></lf-ask>',
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
<div id="pane" class="scroll" style="max-height: 8rem; overflow-y: auto">
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
    it. Each of the two entries beside one block outlines its own gap."""
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
    expect(page.locator('[aria-controls="notes"] .lf-tabdiff')).to_have_text("Δ1")
    expect(page.locator('[aria-controls="others"] .lf-tabdiff')).to_have_text("")

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
    tops = []
    for index in range(2):
        entries.nth(index).hover()
        expect(outline).to_be_visible()
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
    page.locator('[data-lf-margin-for="a"] [data-lf-kinds~="change"]').click()
    card = page.get_by_role("group", name="2 paragraphs edited, 1 replaced by 1")
    expect(card).to_be_visible()
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
    expect(bars).to_have_attribute("data-lf-for", "b")
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
    expect(bars).to_have_attribute("data-lf-for", "c")
