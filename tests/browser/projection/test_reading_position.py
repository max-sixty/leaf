"""Where the reader's view stays when a revision, news or a repaint changes the page:
lines, landmarks, active regions, panes and bounded scrollports."""

import json
import re

import pytest
from interact_support import add_test_widget
from playwright.sync_api import expect
from render_cases_interaction import (
    BOXLESS_SECTION_PAGE,
    KEPT_SECTION_PAGE,
    LIVE_READING,
    LIVE_V1,
    LIVE_V2,
    WRAP_TOP,
    live_url,
)
from render_harness import (
    EXAMPLE_PACKAGES,
    LANDING_TOP,
    leaf_page,
    open_page,
    pane_scroll_behavior,
    panel_menu,
    panel_settled,
    panel_view,
    regions_side_by_side,
    resized,
    scroll_settled,
    stamp_page,
    told,
    wait_for_revision,
)

from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize(
    "where",
    [
        pytest.param("above", marks=pytest.mark.watch_shifts),
        # Unwatched: the revision rewrites the words of the text node the reader reads,
        # and the watch compares that node's lines by their order, so every line below
        # the rewrite reads as moved, though each holds other words than it did.
        "inside",
        pytest.param("figure", marks=pytest.mark.watch_shifts),
    ],
)
def test_live_revision_keeps_the_visible_semantic_reading(browser, serve, where):
    """A content revision keeps the reader on the same passage.

    Native scroll anchoring is disabled by this page's layout, so it cannot conceal
    a broken semantic carry when five paragraphs arrive above the reader. Where the
    reader stands partway into a long paragraph, its start above the window, and the
    revision also lengthens words of it above their line, the line they read stays
    where it was, not the paragraph's opening line. Where a figure taller than the
    window fills it, with no words on screen, the part of the figure at the edge stays
    there, not the old scroll offset, which now names the arriving paragraphs.
    """
    anchoring = "<style>html { overflow-anchor: none; }</style>"
    first = LIVE_V1.replace(
        "</head>",
        anchoring + "</head>",
    )
    second = LIVE_V2.replace("</head>", anchoring + "</head>")
    if where == "inside":
        words = " ".join(f"w{n:04d}" for n in range(1, 500))
        first = first.replace(LIVE_READING, words)
        second = second.replace(LIVE_READING, words).replace(
            " w0005 ", " " + "a longer phrase standing where one word stood " * 6
        )
    if where == "figure":
        figure = (
            '<svg id="live-reading" viewBox="0 0 100 300"'
            ' style="display:block;width:100%;height:auto">'
            + "".join(
                f'<rect x="0" y="{n * 10}" width="100" height="10"'
                f' fill="hsl({n * 12} 60% 60%)"/>'
                for n in range(30)
            )
            + "</svg>"
        )
        paragraph = f'<p id="live-reading">{LIVE_READING}</p>'
        first = first.replace(paragraph, figure)
        second = second.replace(paragraph, figure)
    page = open_page(browser, live_url(serve(first)))
    resized(page, 1200, 900)
    reading = page.locator("#live-reading")
    reading.scroll_into_view_if_needed()
    page.evaluate(
        """(where) => {
          const box = document.getElementById('live-reading').getBoundingClientRect();
          document.scrollingElement.scrollBy({
            top: box.top - {above: 140, inside: -300, figure: -0.4 * box.height}[where],
            behavior: 'instant'
          });
        }""",
        where,
    )
    scroll_settled(page)
    expect(reading).to_be_in_viewport()
    # The first word at or below the landing band, and where it stands; in a figure,
    # how far through its height the band cuts it.
    word_at_band = f"""async (word) => {{
      const band = {LANDING_TOP};
      const reading = document.getElementById('live-reading');
      if (reading.localName === 'svg') {{
        const box = reading.getBoundingClientRect();
        return {{top: (band - box.top) / box.height}};
      }}
      const text = reading.firstChild;
      const range = document.createRange();
      for (const match of text.data.matchAll(/\\S+/g)) {{
        if (word && match[0] !== word) continue;
        range.setStart(text, match.index);
        range.setEnd(text, match.index + match[0].length);
        const rect = range.getClientRects()[0];
        if (word || (rect.top + rect.bottom) / 2 >= band)
          return {{word: match[0], top: rect.top}};
      }}
    }}"""
    before = page.evaluate(word_at_band, None)
    page.wait_for_timeout(600)
    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Live second")
    expect(page.locator("#live-new-4")).to_contain_text("New finding 4")
    rendered(page)
    after = page.evaluate(word_at_band, before.get("word"))
    assert after["top"] == pytest.approx(
        before["top"], abs=0.01 if where == "figure" else 4
    ), (before, after)


def test_a_revision_keeps_the_paragraph_under_a_focused_stuck_tab(browser, serve):
    """A stuck tab strip rides over every paragraph, so it names none of them.

    The reader focused a tab and scrolled the page with no other input, so focus is
    still their last word on where they are. The strip stays in view, stuck over the
    panel's paragraphs, and a revision adding paragraphs above keeps that paragraph
    where it stood rather than the strip, which stays in view by itself.
    """

    def source(added):
        paragraphs = "".join(
            f'<p id="{name}">{name}, long enough to stand as a landmark of its own.</p>'
            for name in [f"added-{n}" for n in range(added)]
            + [f"passage-{n}" for n in range(80)]
        )
        return leaf_page(
            f"Stuck tab {added}",
            "<style>html { overflow-anchor: none; }</style>"
            f'<lf-tabs id="views" class="layout-flow"><lf-tab id="first" label="First view">{paragraphs}'
            '</lf-tab><lf-tab id="second" label="Second view"><p>Other.</p></lf-tab>'
            "</lf-tabs>",
        )

    page = open_page(browser, live_url(serve(source(0))))
    resized(page, 1200, 700)
    tab = page.get_by_role("tab", name="First view")
    tab.focus()
    rendered(page)
    page.evaluate("document.scrollingElement.scrollTop = 2500")
    scroll_settled(page)
    rendered(page)
    expect(tab).to_be_focused()
    assert tab.evaluate("""async tab => {
        const {stuckBox, seenRect} = await window.__lfCheckApi();
        return Boolean(stuckBox(tab) && seenRect(tab, new Map()));
    }"""), "the tab strip did not stick over the panel"
    landmark = page.evaluate("""() => [...document.querySelectorAll('#first p')].find(
        p => p.getBoundingClientRect().top >= 200).id""")
    reading = page.locator(f"#{landmark}")
    before = reading.evaluate("node => node.getBoundingClientRect().top")
    (serve.page_dir / "index.html").write_text(source(5))
    told(page)
    expect(page).to_have_title("Stuck tab 5")
    rendered(page)
    after = reading.evaluate("node => node.getBoundingClientRect().top")
    assert after == pytest.approx(before, abs=4), (before, after)


def test_a_box_fixed_in_the_window_rides_every_scroll_and_an_anchored_one_does_not(
    browser, serve
):
    """A box fixed in the window, as a page of parts' column is, stands over whatever
    the page scrolls to, so it names no place in it, as a stuck sticky box doesn't. A
    fixed box anchored to the page's words, as the inline thread card is, moves with
    them, so a reply focused in it still marks where the reader is, as does a fixed
    box a transformed box holds."""
    page = open_page(
        browser,
        live_url(
            serve(
                leaf_page(
                    "Fixed boxes",
                    '<p id="words">Words a card stands beside.</p>'
                    + "".join(f"<p>Paragraph {n}.</p>" for n in range(80))
                    + '<div id="column" style="position: fixed; top: 0">'
                    "<button>In the column</button></div>"
                    '<div id="card" style="position: fixed; position-anchor: --words;'
                    ' top: anchor(bottom); left: anchor(left)">'
                    "<button>In the card</button></div>"
                    '<div style="transform: translateX(0)">'
                    '<div id="held" style="position: fixed; top: 0">'
                    "<button>Held</button></div></div>"
                    "<style>#words { anchor-name: --words; }</style>",
                )
            )
        ),
    )
    page.evaluate("document.scrollingElement.scrollTop = 0")
    rendered(page)
    assert page.evaluate("""async () => {
        const {stuckBox} = await window.__lfCheckApi();
        const ask = (id) => stuckBox(document.querySelector(`#${id} button`))?.id ?? null;
        return [ask("column"), ask("card"), ask("held")];
    }""") == ["column", None, None]


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_revision_after_revision_keeps_the_reader_on_the_same_line(
    engine, request, serve
):
    """An agent adds a paragraph above the reader in each of several revisions.

    Each restore lands the reader's line within the pixel the engine rounds a scroll
    offset to, and the next revision's reading starts from where the restore aimed
    rather than where it landed: read from where it landed, each rounding would add
    to the last, and the line would creep down the screen revision by revision.
    """
    browser = request.getfixturevalue(engine)

    def source(added):
        paragraphs = "".join(
            f'<p id="{name}">{name}, long enough to stand as a landmark of its own.</p>'
            for name in [f"added-{n}" for n in range(added)]
            + [f"passage-{n}" for n in range(80)]
        )
        # A line height whose paragraphs stand a fraction of a pixel apart, which no
        # scroll offset can match.
        return leaf_page(
            f"Arrivals {added}",
            "<style>html { overflow-anchor: none; } p { line-height: 1.37; }</style>"
            + paragraphs,
        )

    page = open_page(browser, live_url(serve(source(0))))
    resized(page, 1200, 700)
    page.evaluate("document.scrollingElement.scrollTop = 1500")
    scroll_settled(page)
    rendered(page)
    reading = page.locator("#passage-45")
    before = reading.evaluate("node => node.getBoundingClientRect().top")
    for added in range(1, 7):
        (serve.page_dir / "index.html").write_text(source(added))
        told(page)
        expect(page).to_have_title(f"Arrivals {added}")
        rendered(page)
    after = reading.evaluate("node => node.getBoundingClientRect().top")
    assert after == pytest.approx(before, abs=1), (before, after)


def test_a_revision_keeps_the_pane_read_over_a_pane_holding_offscreen_focus(
    browser, serve
):
    """Focus left in a pane the reader scrolled away from does not name their region.

    Two panes share the page scroller at a narrow width. The reader typed in the
    first, then scrolled on into the second; a revision adding paragraphs above keeps
    the paragraph they read in the second where it stood."""

    def source(added):
        notes = "".join(f"<p>Note {n}, kept with the draft.</p>" for n in range(12))
        log = "".join(
            f'<p id="{name}">{name}, long enough to stand as a landmark of its own.</p>'
            for name in [f"added-{n}" for n in range(added)]
            + [f"entry-{n}" for n in range(60)]
        )
        return leaf_page(
            f"Two panes {added}",
            "<style>html { overflow-anchor: none; }</style>"
            '<lf-pane id="notes" label="Notes"><div>'
            '<textarea aria-label="Working draft"></textarea>'
            f'{notes}</div></lf-pane><lf-pane id="log" label="Log"><div>{log}</div></lf-pane>',
            layout="workspace",
        )

    page = open_page(browser, live_url(serve(source(0))))
    resized(page, 390, 760)
    field = page.get_by_role("textbox", name="Working draft")
    field.click()
    page.keyboard.type("Words kept in the notes")
    rendered(page)
    page.locator("#entry-30").evaluate(
        "node => document.scrollingElement.scrollBy({top: node.getBoundingClientRect().top - 200, behavior: 'instant'})"
    )
    box = page.locator("#entry-30").bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 5)
    page.mouse.wheel(0, 40)
    scroll_settled(page)
    rendered(page)
    expect(field).to_be_focused()
    expect(field).not_to_be_in_viewport()
    landmark = page.evaluate("""() => [...document.querySelectorAll('#log p')].find(
        p => p.getBoundingClientRect().top >= 200).id""")
    reading = page.locator(f"#{landmark}")
    before = reading.evaluate("node => node.getBoundingClientRect().top")
    (serve.page_dir / "index.html").write_text(source(5))
    told(page)
    expect(page).to_have_title("Two panes 5")
    rendered(page)
    expect(field).to_be_focused()
    after = reading.evaluate("node => node.getBoundingClientRect().top")
    assert after == pytest.approx(before, abs=4), (landmark, before, after)


def test_revision_changes_keep_the_complete_heading_below_user_chrome(browser, serve):
    """A partly cut title is the page opening, not a reading place to preserve.

    A revision change used the heading as its semantic landmark and restored its exact
    viewport coordinate. When the user had moved just far enough for the first title
    line to sit above the scroller's landable top (then under the fixed banner), both
    an arriving current revision and a chosen historical version faithfully restored
    that broken view: the later line looked like the whole heading. The scroller
    declares its landable top through scroll-padding, so a heading landmark must honor
    that edge while ordinary passage landmarks retain their exact coordinate.
    """
    title = "The page should own the complete one-off playground"
    revised_title = "The complete one-off playground belongs to the page"
    first = leaf_page(
        "Heading continuity",
        f"""
<header id="summary">
  <p class="eyebrow">Playground replacement audit</p>
  <h1>{title}</h1>
  <p>The opening account is long enough to become the next reading landmark.</p>
</header>
<div style="height: 1200px"></div>
""",
    )
    version_url = serve(first)
    page = open_page(browser, live_url(version_url))
    resized(page, 668, 704)

    # The heading's first line stands 12px above the landable top the scroller's
    # scroll-padding declares, the rest of it below.
    clip_heading = """() => {
          const heading = document.querySelector('#summary h1');
          const inset = parseFloat(
            getComputedStyle(document.scrollingElement).scrollPaddingTop
          );
          document.scrollingElement.scrollBy({
            top: heading.getBoundingClientRect().top - inset + 12,
            behavior: 'instant',
          });
          const title = heading.getBoundingClientRect();
          const summary = document.getElementById('summary').getBoundingClientRect();
          return {title: title.toJSON(), summary: summary.toJSON(), inset};
        }"""
    heading_position = """() => {
          const title = document.querySelector('#summary h1').getBoundingClientRect();
          const inset = parseFloat(
            getComputedStyle(document.scrollingElement).scrollPaddingTop
          );
          return {
            title: title.toJSON(),
            inset,
            live: document.documentElement.hasAttribute('data-lf-live'),
          };
        }"""

    clipped = page.evaluate(clip_heading)
    assert clipped["title"]["top"] < clipped["inset"], clipped
    assert clipped["title"]["bottom"] > clipped["inset"], clipped

    # The producer owns the invariant: a saved semantic heading coordinate is never
    # inside the chrome, so in-place activation and document travel consume the same
    # valid view rather than each repairing it independently.
    page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
    view = page.evaluate(
        """() => {
          for (const key of Object.keys(sessionStorage))
            if (key.endsWith('lf-view')) return JSON.parse(sessionStorage[key]);
          return null;
        }"""
    )
    assert view["quote"].startswith(title), view
    # A view measures its places from the top of the scroller's visible band, which
    # scroll-padding declares: a heading's is never above it.
    assert view["quoteTop"] >= 0, view
    assert view["section"] == "summary", view
    assert view["sectionTop"] > clipped["summary"]["top"] - clipped["inset"], view

    stamp_page(
        serve.page_dir,
        first.replace(title, revised_title).replace("1200px", "1201px"),
        "Changed evidence below the page heading",
    )
    wait_for_revision(page, 2)
    live_landed = page.evaluate(heading_position)
    assert live_landed["live"], "revision activation removed the live shell"
    assert live_landed["inset"] == clipped["inset"], live_landed
    assert live_landed["title"]["top"] >= live_landed["inset"], (
        f"the arriving revision left the heading under user chrome: {live_landed}"
    )

    clipped = page.evaluate(clip_heading)
    assert clipped["title"]["top"] < clipped["inset"], clipped
    panel_menu(page, "versions").locator(".lf-fp-version").filter(
        has_text=re.compile(r"^\s*v1(?!\d)")
    ).locator(".lf-fp-item").click()
    page.wait_for_url(re.compile(r"/versions/v1\.html"))
    wait_until_ready(page)

    landed = page.evaluate(heading_position)
    assert landed["title"]["top"] >= landed["inset"], (
        f"version travel left the heading under user chrome: {landed}"
    )


def test_revision_changes_follow_authored_text_into_declared_shadow_trees(
    browser, serve, tmp_path, monkeypatch
):
    """The semantic reading walk and resolver share the composed page reading.

    A declared shadow root is allowed to render the page's authored words. If continuity
    searches only light-DOM blocks, it records a raw page offset even though the passage
    resolver can find the rendered words, so material inserted above the widget displaces
    the user on the next revision.
    """
    monkeypatch.chdir(tmp_path)
    package = tmp_path / ".leaf"
    add_test_widget(package, "lf-shadow-reading", upgrade=True)
    registry_path = package / "registry.json"
    declarations = json.loads(registry_path.read_text())
    declarations["lf-shadow-reading"]["x-shadow"] = True
    registry_path.write_text(json.dumps(declarations))
    (package / "widgets" / "lf-shadow-reading.js").write_text(
        """import { once, shadowStage } from "/runtime/widget-api.js";
customElements.define("lf-shadow-reading", class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const paragraph = document.createElement("p");
    paragraph.textContent = this.textContent.trim();
    shadowStage(this, [paragraph]);
  }
});
"""
    )
    reading = "The shadow-rendered passage is the user's stable semantic landmark."
    first = leaf_page(
        "Shadow reading continuity",
        f"""
<h1 id="title">Shadow reading continuity</h1>
<div style="height: 700px"></div>
<lf-shadow-reading id="shadow-reading">{reading}</lf-shadow-reading>
<div style="height: 1000px"></div>
""",
    )
    page = open_page(
        browser,
        live_url(serve(first, packages=(*EXAMPLE_PACKAGES, "./.leaf"))),
    )
    paragraph = page.locator("lf-shadow-reading").locator("p")
    paragraph.scroll_into_view_if_needed()
    page.evaluate(
        """() => document.scrollingElement.scrollBy({
          top: document.querySelector('lf-shadow-reading').shadowRoot
            .querySelector('p').getBoundingClientRect().top - 150,
          behavior: 'instant',
        })"""
    )
    before = paragraph.evaluate("el => el.getBoundingClientRect().top")

    page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
    view = page.evaluate(
        """() => {
          for (const key of Object.keys(sessionStorage))
            if (key.endsWith('lf-view')) return JSON.parse(sessionStorage[key]);
          return null;
        }"""
    )
    assert view["quote"].startswith(reading), view
    assert view["section"] == "shadow-reading", view

    revised = first.replace(
        '<lf-shadow-reading id="shadow-reading">',
        '<div style="height: 320px"></div><lf-shadow-reading id="shadow-reading">',
    )
    stamp_page(serve.page_dir, revised, "add context above the shadow reading")
    wait_for_revision(page, 2)
    after = paragraph.evaluate("el => el.getBoundingClientRect().top")
    assert abs(after - before) <= 4, (before, after)


def test_revision_remembers_the_active_region_when_a_workspace_reflows(browser, serve):
    """One active semantic reading wins when several regions begin sharing the page.

    The revision puts prose before the workspace, so it stops being the page and flows,
    and every pane's reading moves onto the one page scroll."""

    def pane(side):
        return f"""
    <lf-pane id="{side}-reading" label="{side.title()} reading"><div>
      <p id="{side}-start">{side.title()} start with enough words for a landmark.</p>
      <div style="height: 320px"></div>
      <p id="{side}-landmark">The current {side} reading has a stable semantic landmark.
        {'<button id="right-subject">Right subject</button>' if side == "right" else ""}
      </p>
      <div style="height: 700px"></div>
      <p>{side.title()} end.</p>
    </div></lf-pane>"""

    workspace_markup = f"""
<header><h1>Reading workspace</h1></header>
<div id="reading-split">
  {pane("left")}
  {pane("right")}
</div>
"""
    split = regions_side_by_side("reading-split")
    first = leaf_page(
        "Active region continuity", workspace_markup, head=split, layout="workspace"
    )
    page = open_page(browser, live_url(serve(first)))
    resized(page, 900, 760)
    right_pane = page.locator("#right-reading")
    pane_scroll_behavior(page, right_pane, "bounded")
    left = page.locator("#left-reading > div")
    right = page.locator("#right-reading > div")
    left.evaluate("el => el.scrollTop = 180")
    right.evaluate("el => el.scrollTop = 360")
    page.locator("#right-subject").click()
    before = page.locator("#right-landmark").evaluate(
        """el => el.getBoundingClientRect().top -
          el.closest('lf-pane > div').getBoundingClientRect().top"""
    )

    revised = leaf_page(
        "Active region continuity",
        "<p>The revision adds context before the workspace.</p>" + workspace_markup,
        head=split,
    )
    stamp_page(serve.page_dir, revised, "put the workspace in the document")
    wait_for_revision(page, 2)
    pane_scroll_behavior(page, right_pane, "flow")
    # The page's band starts where scroll-padding says; the landmark
    # keeps its distance below the top of what the user can see.
    after = page.locator("#right-landmark").evaluate(
        """el => el.getBoundingClientRect().top -
          parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)"""
    )
    assert abs(after - before) <= 4, (before, after)


def test_revision_keeps_a_focused_control_visible_without_a_text_landmark(
    browser, serve
):
    """A focused control remains the place when its pane has no quotable text."""
    content = """
<header><h1>Control workspace</h1></header>
<div id="reading-split">
  <lf-pane id="left-reading" label="Left reading"><div>
    <p>Another pane's reading does not name the active control.</p>
  </div></lf-pane>
  <lf-pane id="right-reading" label="Right reading"><div>
    <div style="height: 1100px"></div>
    <button id="right-subject">Right subject</button>
    <div style="height: 500px"></div>
  </div></lf-pane>
</div>
"""
    split = regions_side_by_side("reading-split")
    first = leaf_page(
        "Focused control continuity", content, head=split, layout="workspace"
    )
    page = open_page(browser, live_url(serve(first)))
    resized(page, 900, 760)
    pane_scroll_behavior(page, page.locator("#right-reading"), "bounded")
    page.locator("#right-subject").click()

    revised = leaf_page(
        "Focused control continuity",
        '<div style="height: 1000px"></div>' + content,
        head=split,
    )
    stamp_page(serve.page_dir, revised, "put the workspace in the document")
    wait_for_revision(page, 2)
    pane_scroll_behavior(page, page.locator("#right-reading"), "flow")
    visible = page.locator("#right-subject").evaluate(
        """el => {
          const rect = el.getBoundingClientRect();
          return rect.top >= 0 && rect.bottom <= innerHeight;
        }"""
    )
    assert visible


def test_revision_reveals_a_page_landmark_around_an_empty_active_region(browser, serve):
    """An empty flow region does not displace the page reading that contains it.

    The page is read a little past its top, so the title is its reading place; a page
    at its very top would stay there, and the result the revision adds above the title
    would push the title down."""
    content = """
<h1 id="reading-title">The page landmark surrounding these controls remains stable.</h1>
<lf-pane id="controls-pane" label="Controls">
  <button id="focused-control">Change setting</button>
</lf-pane>
<div style="height: 1000px"></div>
    """
    first = leaf_page("Empty active region continuity", content)
    page = open_page(browser, live_url(serve(first)))
    page.evaluate("scrollTo({top: 20, behavior: 'instant'})")
    page.locator("#focused-control").focus()
    before = page.locator("#reading-title").evaluate(
        "heading => heading.getBoundingClientRect().top"
    )

    revised = leaf_page(
        "Empty active region continuity",
        f"""
<p>The arriving revision adds a result above the prior content.</p>
<details id="prior-controls">
  <summary>Prior controls</summary>
  {content}
</details>
""",
    )
    stamp_page(serve.page_dir, revised, "wrap the prior controls")
    wait_for_revision(page, 2)

    expect(page.locator("#prior-controls")).to_have_attribute("open", "")
    # The revision wrapped the control, so the element the user was on is gone and
    # focus went to the page with it. What the region still owes them is the way back
    # to it: revealed rather than shut inside a disclosure they never closed.
    expect(page.locator("#focused-control")).to_be_visible()
    after = page.locator("#reading-title").evaluate(
        "heading => heading.getBoundingClientRect().top"
    )
    assert abs(after - before) <= 4, (before, after)


def test_revision_reveals_an_active_region_without_any_reading_landmark(browser, serve):
    """A surviving active region remains reachable even when no passage names it."""
    content = """
<lf-pane id="controls-pane" label="Controls">
  <button id="focused-control">Change setting</button>
</lf-pane>
<div style="height: 1000px"></div>
    """
    first = leaf_page("Textless active region continuity", content)
    page = open_page(browser, live_url(serve(first)))
    page.locator("#focused-control").focus()

    revised = leaf_page(
        "Textless active region continuity",
        f"""
<details id="prior-controls">
  <summary>Prior controls</summary>
  {content}
</details>
""",
    )
    stamp_page(serve.page_dir, revised, "wrap the textless active region")
    wait_for_revision(page, 2)

    expect(page.locator("#prior-controls")).to_have_attribute("open", "")
    # Reachable, not focused: the revision wrapped the control, so the element the
    # user was located on is gone and the region owes them the way back to its replacement.
    expect(page.locator("#focused-control")).to_be_visible()


def test_obligation_repaints_keep_the_on_me_view_s_reading(browser, serve):
    """Obligation repaint keeps the reading of the panel's On me view the user scrolled."""
    questions = "".join(
        f'<lf-ask id="ask-{index}"><h2>Question {index} about this project</h2>'
        f'<lf-options id="options-{index}" choose>'
        f'<lf-option id="yes-{index}">Proceed with this choice</lf-option>'
        f'<lf-option id="no-{index}">Leave this choice for now</lf-option>'
        "</lf-options></lf-ask>"
        for index in range(30)
    )
    page = open_page(
        browser, serve(leaf_page("Reading the Question inventory", questions))
    )
    resized(page, 1200, 900)
    # With nothing focused, the walk enters the first Ask the reader sees.
    page.keyboard.press("m")
    expect(page.locator("#ask-0")).to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    list_selector = panel_view("queue")
    view = page.locator(list_selector)
    view.evaluate(
        """list => list.addEventListener('scroll', () => {
          if (list.scrollTop > 100) window.readLaterObligations = true;
        })"""
    )
    box = view.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 700)
    page.wait_for_function("() => window.readLaterObligations")
    scroll_settled(page, list_selector)
    reading = view.evaluate("list => list.scrollTop")
    assert reading > 100, "painting the current card must not undo scrolling the list"

    resized(page, 1180, 900)
    scroll_settled(page, list_selector)
    assert view.evaluate("list => list.scrollTop") == reading


@pytest.mark.parametrize("newer_reading", [False, True])
def test_a_panes_scroll_behavior_change_keeps_the_reading_after_scrolling_past_focus(
    browser, serve, newer_reading
):
    """An automatic scroll-container change preserves reading rather than stale focus."""
    paragraphs = "".join(
        f'<p id="line-{index}">Reading paragraph {index}. '
        + "Words holding the current reading. " * 10
        + "</p>"
        for index in range(30)
    )
    source = leaf_page(
        "Reading beyond the focused control",
        '<lf-pane id="reading" label="Reading"><div id="reading-body">'
        '<button id="control">Earlier focused control</button>'
        f"{paragraphs}</div></lf-pane>",
        head="""<style>
#reading-body { height: 400px; overflow: auto; }
@media (width < 720px) { #reading-body { height: auto; overflow: visible; } }
</style>""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1200, 900)
    body = page.locator("#reading-body")
    control = page.locator("#control")
    control.focus()
    body.evaluate("body => body.scrollTop = 900")
    scroll_settled(page, "#reading-body")
    assert control.evaluate("control => control.getBoundingClientRect().bottom") < 0
    landmark_id = body.evaluate(
        """body => [...body.querySelectorAll('p')].find(paragraph =>
          paragraph.getBoundingClientRect().top >= body.getBoundingClientRect().top).id"""
    )
    if newer_reading:
        # Interleave at the announced handover, before its deferred restoration. The
        # platform input supersedes that restoration just as a trackpad gesture does.
        page.evaluate("""async () => {
          const regions = await window.__lfWidgetApi();
          const stop = regions.watchReadingRegionTransitions(({phase, shifted}) => {
            if (phase !== 'shift' || !shifted.some(({region}) => region.id === 'reading'))
              return;
            stop();
            document.body.dispatchEvent(new WheelEvent('wheel', {deltaY: 500, bubbles: true}));
            scrollTo({top: 1900, behavior: 'instant'});
            window.laterReading = scrollY;
          });
        }""")

    resized(page, 520, 900)
    pane_scroll_behavior(page, page.locator("#reading"), "flow")
    scroll_settled(page)

    expect(control).to_be_focused()
    if newer_reading:
        assert page.evaluate("() => window.laterReading") > 1000
        assert page.evaluate("() => scrollY === window.laterReading"), (
            "a queued scroll behavior restore must yield to the user's later reading"
        )
        return
    landmark = page.locator(f"#{landmark_id}")
    assert landmark.evaluate(
        "paragraph => paragraph.getBoundingClientRect().top < innerHeight"
    ), "changing scroll behavior must keep the passage being read on screen"
    assert control.evaluate("control => control.getBoundingClientRect().bottom") < 0


def test_revision_does_not_move_a_page_offset_into_a_new_bounded_region(browser, serve):
    """A raw offset belongs to the scrollport that supplied it.

    The workspace flows under prose in the first version and is the page in the second,
    so the scroll the user left on the page has no place in the pane that now scrolls.
    """

    def pane(name, *, with_control=False):
        control = (
            '<button id="focused-control">Change setting</button>'
            if with_control
            else ""
        )
        return f"""
<lf-pane id="{name}-pane" label="{name.title()}">
  <div>{control}<div style="height: 1100px"></div></div>
</lf-pane>
"""

    workspace_markup = f"""
<div id="all-panes">
  {pane("active", with_control=True)}
  {pane("second")}
</div>
"""
    split = regions_side_by_side("all-panes")
    first = leaf_page(
        "Changing offset ownership",
        "<p>Context before the workspace.</p>" + workspace_markup,
        head=split,
    )
    page = open_page(browser, live_url(serve(first)))
    resized(page, 900, 760)
    active = page.locator("#active-pane")
    pane_scroll_behavior(page, active, "flow")
    page.locator("#focused-control").evaluate(
        "control => control.focus({preventScroll: true})"
    )
    page.evaluate("document.scrollingElement.scrollTop = 300")
    before = page.evaluate("document.scrollingElement.scrollTop")
    assert before == 300

    revised = leaf_page(
        "Changing offset ownership", workspace_markup, head=split, layout="workspace"
    )
    stamp_page(serve.page_dir, revised, "make the workspace the page")
    wait_for_revision(page, 2)

    pane_scroll_behavior(page, active, "bounded")
    assert page.locator("#active-pane > div").evaluate("pane => pane.scrollTop") == 0


def test_revision_does_not_move_an_offset_between_bounded_region_owners(browser, serve):
    """A nested flow region cannot carry one parent's offset into another parent."""
    entry = {
        "description": "A test-owned reading scroller.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-upgrade": True,
        "x-example": (
            '<lf-owned-scroll id="example">'
            "<div data-scroll-body><button>Control</button></div>"
            "</lf-owned-scroll>"
        ),
    }
    module = """
import {registerReadingRegion} from '/runtime/widget-api.js';
customElements.define('lf-owned-scroll', class extends HTMLElement {
  #stop = null;
  connectedCallback() {
    const body = this.querySelector(':scope > [data-scroll-body]');
    this.#stop = registerReadingRegion({id: this.id, host: this, body});
  }
  disconnectedCallback() {
    this.#stop?.();
    this.#stop = null;
  }
});
"""
    active = """
<div style="height: 250px"></div>
<lf-owned-scroll id="active-region">
  <div data-scroll-body>
    <section id="removed-landmark">
      <p>The nested region landmark disappears in the arriving revision.</p>
    </section>
    <button id="focused-control">Change setting</button>
  </div>
</lf-owned-scroll>
"""
    active_without_landmark = active.replace(
        """    <section id="removed-landmark">
      <p>The nested region landmark disappears in the arriving revision.</p>
    </section>
""",
        "",
    )

    def parent(name, content=""):
        return f"""
<lf-owned-scroll id="{name}-region">
  <div data-scroll-body style="height: 240px; overflow: auto">
    {content}<div style="height: 700px"></div>
  </div>
</lf-owned-scroll>
"""

    first = leaf_page(
        "Nested offset ownership",
        parent("left", active) + parent("right"),
    )
    page = open_page(
        browser,
        live_url(
            serve(
                first,
                layer_registry={"lf-owned-scroll": entry},
                layer_widgets={"lf-owned-scroll.js": module},
            )
        ),
    )
    left = page.locator("#left-region > [data-scroll-body]")
    right = page.locator("#right-region > [data-scroll-body]")
    left.evaluate("scroller => scroller.scrollTop = 150")
    page.locator("#focused-control").evaluate(
        "control => control.focus({preventScroll: true})"
    )
    assert left.evaluate("scroller => scroller.scrollTop") == 150
    assert right.evaluate("scroller => scroller.scrollTop") == 0

    revised = leaf_page(
        "Nested offset ownership",
        parent("left") + parent("right", active_without_landmark),
    )
    stamp_page(serve.page_dir, revised, "move the active region")
    wait_for_revision(page, 2)

    assert right.evaluate("scroller => scroller.scrollTop") == 0
    # The region moved parents, so its control is a new element under the other one.
    expect(page.locator("#right-region #focused-control")).to_be_visible()


def test_the_reading_position_restores_onto_a_section_that_draws_no_box(browser, serve):
    """The landmark a reading position falls back to is an element like any other, and
    an element that generates no box measures (0,0) at the document's origin.

    Read raw, that answer arrives on both sides of the subtraction — once when the
    place is written down and once when it is put back — so the correction came out 0
    and a restore that had somewhere to land did nothing at all. The user was left at
    the top of a page they had been thirty paragraphs into. It is quiet twice over: only
    a user whose quote the new version rewrote reaches this branch, and a page whose
    sections all draw boxes never sees it."""
    url = serve(BOXLESS_SECTION_PAGE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    resized(page, 900, 600)

    # Read from inside the wrapper, so every block on screen is one of its own and the
    # nearest id above them is the wrapper: its second block's opening words stand at
    # the top of the band the page shows, which scroll-padding declares.
    page.evaluate("""() => {
      const scroller = document.scrollingElement;
      const block = document.querySelectorAll('#wrap p')[1];
      scroller.scrollTop += block.getBoundingClientRect().top
        - parseFloat(getComputedStyle(scroller).scrollPaddingTop); }""")
    before = page.evaluate(WRAP_TOP)

    # The branch under test, stated rather than assumed. In-place activation carries this
    # object directly; pagehide stores the same capture for document travel, which gives
    # the test a view of it without adding a second diagnostic representation.
    page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
    view = page.evaluate("""() => {
      for (const k of Object.keys(sessionStorage))
        if (k.endsWith('lf-view')) return JSON.parse(sessionStorage[k]);
      return null; }""")
    assert view and view["section"] == "wrap", (
        f"the landmark was not the boxless wrapper: {view}"
    )
    assert view["quote"].startswith("Held"), (
        f"v2 still holds this quote, so the section branch never ran: {view}"
    )

    stamp_page(d, KEPT_SECTION_PAGE, "two")
    wait_for_revision(page, 2)

    after = page.evaluate(WRAP_TOP)
    assert abs(after - before) <= 4, (
        f"the user left the wrapper's words {before}px from the top of the window and "
        f"was put back at {after}px"
    )


def test_an_arrival_keeps_a_readable_native_fragment_where_the_browser_landed_it(
    browser, serve
):
    """Startup does not centre a static fragment that is already wholly readable."""
    url = serve(
        leaf_page(
            "native fragment arrival",
            """
<h1>Native fragment arrival</h1>
<div style="height: 900px"></div>
<section id="arrival"><h2>Arrival</h2><p>The whole destination is visible.</p></section>
<div style="height: 900px"></div>
""",
        )
    )
    page = open_page(browser, f"{url}#arrival")
    arrival = page.locator("#arrival")
    position = arrival.evaluate(
        """element => ({
          top: element.getBoundingClientRect().top,
          clear: parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop),
        })"""
    )
    assert abs(position["top"] - position["clear"]) < 2, position
