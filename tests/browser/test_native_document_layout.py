"""Document geometry the Layouts give natively: complete before runtime modules
activate, and keeping the browser's own behavior, such as scroll anchoring."""

import pytest
from playwright.sync_api import expect
from render_harness import displayed, leaf_page, open_page, resized, wait_until_ready

from browser.margin import _comment_on

DOCUMENT = """
<aside id="route"><div class="layout-track">
  <p>Read the evidence before deciding.</p><nav><a href="#evidence">Evidence</a></nav>
</div></aside>
<div class="layout-column" id="body">
  <h1>Review</h1>
  <section id="evidence">
    <h2>Evidence</h2>
    <p id="prose">The passage keeps its reading measure.</p>
    <lf-worktree-diffs id="wide"><lf-worktree id="tree" label="Changes" path="/work/leaf"
      status="clean" files="0" additions="0" deletions="0" open>
      <p>Readable before JavaScript.</p>
    </lf-worktree></lf-worktree-diffs>
  </section>
  <p id="after">The next paragraph keeps its place.</p>
</div>
"""


def test_native_sidebar_is_placed_before_widget_activation(browser, serve):
    source = leaf_page("native startup", DOCUMENT, layout="sidebar")
    url = serve(source)
    for width in (1600, 720):
        page = browser.new_page(viewport={"width": width, "height": 900})
        held = []
        page.route("**/leaf.js", lambda route, _request, held=held: held.append(route))
        page.goto(url, wait_until="commit")
        page.locator("#prose").wait_for(state="visible")
        page.locator("#after").wait_for(state="attached")
        displayed(page)
        read = """() => Object.fromEntries(['route','body','prose','wide','after']
          .map(id => [id,document.getElementById(id).getBoundingClientRect().toJSON()]))"""
        before = page.evaluate(read)
        assert before["prose"]["width"] == min(720, width - 48)
        assert (before["route"]["top"] < before["body"]["top"]) == (width == 720)
        for route in held:
            route.continue_()
        page.unroute("**/leaf.js")
        wait_until_ready(page)
        assert page.evaluate(read) == before


def test_a_questions_words_keep_the_column_beside_a_wider_block(browser, serve):
    """A question's section draws no box of its own around its blocks, so they stand
    in the page's flow: its words and its options keep the prose's edge, and a block
    declaring more room takes it. A div keeps what it holds in the column, inside a
    question or round it. A section in an open disclosure stands in the page's flow
    as well, so a comment on its heading stands by its words."""
    options = (
        '<lf-options id="{id}-options">'
        '<lf-option id="{id}-yes">Yes</lf-option></lf-options>'
    )
    question = (
        '<lf-group id="{id}" label="Ship it?"><h2 id="{id}-head">Ship it?</h2>'
        '<p id="{id}-premise">Because it fits.</p>{held}' + options + "</lf-group>"
    )
    evidence = '<div id="{id}-evidence" data-width="available">Evidence.</div>'
    source = leaf_page(
        "Questions in the flow",
        '<h1>Questions in the flow</h1><p id="prose">Prose sets the column.</p>'
        "<section>"
        + question.format(id="plain", held="")
        + question.format(id="holds", held=evidence.format(id="holds"))
        + question.format(
            id="wrapped",
            held="<div>" + evidence.format(id="wrapped") + "</div>",
        )
        + "</section><div>"
        + question.format(id="kept", held=evidence.format(id="kept"))
        + "</div>"
        + '<details open><summary>More</summary><section id="disclosed">'
        + '<h2 id="disclosed-head">Held in a disclosure</h2>'
        + evidence.format(id="disclosed")
        + "</section></details>",
    )
    page = open_page(browser, serve(source, events=[_comment_on("disclosed-head")]))
    resized(page, 1728, 900)
    boxes = page.evaluate("""() => Object.fromEntries(
      [...document.querySelectorAll('[id]')].filter(el => el.closest('main'))
        .map(el => {
          const box = el.getBoundingClientRect();
          return [el.id, [Math.round(box.left), Math.round(box.right)]];
        }))""")
    column = boxes["prose"]
    assert column == [504, 1224]
    for question_id in ("plain", "holds", "wrapped", "kept"):
        for part in ("head", "premise", "options"):
            assert boxes[f"{question_id}-{part}"] == column, (question_id, part, boxes)
    assert boxes["plain"] == column, boxes
    # The block takes the room and the question's box, which its marks stand on, holds it.
    assert boxes["holds-evidence"][0] < 100 and boxes["holds-evidence"][1] > 1628, boxes
    assert boxes["holds"] == boxes["holds-evidence"], boxes
    # A div keeps what it holds, as it does outside a question, and the question's box
    # keeps to the column with it.
    for question_id in ("wrapped", "kept"):
        assert boxes[f"{question_id}-evidence"] == boxes[question_id] == column, boxes
    # What the question asks stands by its words, not at the edge of the evidence.
    marker = page.locator("[data-lf-margin-for='holds']")
    expect(marker).to_have_attribute("data-lf-place", "rail")
    assert marker.bounding_box()["x"] < column[1] + 100
    assert boxes["disclosed-evidence"][1] > 1628, boxes
    expect(page.locator("[data-lf-margin-for='disclosed-head']")).to_have_attribute(
        "data-lf-place", "rail"
    )


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_flow_written_the_other_way_grows_toward_the_room(browser, serve, direction):
    """Beside a contents map, a question or section written in the other direction from
    the page takes the same room as the page's own blocks: an available block reaches
    the page's room, and a wide one grows from the prose toward its own end, which faces
    the map, within the room before the prose. A flow that read the room on the
    column's start side as the room on its own would grow both toward the map, the
    available block past the window's edge."""
    other = "rtl" if direction == "ltr" else "ltr"
    options = '<lf-options id="{id}-o"><lf-option id="{id}-y">Yes</lf-option>'
    question = (
        f'<lf-group id="{{id}}" dir="{other}" label="Ship it?">'
        '<h3 id="{id}-h">Ship it?</h3>'
        '<div id="{id}-block" data-width="{width}">Evidence.</div>'
        + options
        + "</lf-options></lf-group>"
    )
    source = leaf_page(
        "Flows written the other way",
        '<div class="layout-sidebar"><aside><div class="layout-track">'
        '<lf-toc id="contents"></lf-toc></div></aside><div class="layout-column">'
        '<h1>Flows written the other way</h1><p id="prose">Prose sets the column.</p>'
        '<div id="room" data-width="available">Room.</div>'
        + question.format(id="reaches", width="available")
        + question.format(id="widens", width="wide")
        + f'<section dir="{other}">'
        '<div id="section-block" data-width="available">Evidence.</div></section>'
        "</div></div>",
    ).replace('<html lang="en">', f'<html lang="en" dir="{direction}">', 1)
    page = open_page(browser, serve(source))
    resized(page, 1726, 900)
    boxes = page.evaluate("""() => Object.fromEntries(
      [...document.querySelectorAll('main [id]')].map(el => {
        const box = el.getBoundingClientRect();
        return [el.id, [Math.round(box.left), Math.round(box.right)]];
      }))""")
    prose, room = boxes["prose"], boxes["room"]
    assert room != prose and 0 <= room[0] and room[1] <= 1726, boxes
    for block in ("reaches-block", "reaches", "section-block"):
        assert boxes[block] == room, (block, boxes)
    widens, start = boxes["widens-block"], 0 if other == "ltr" else 1
    assert widens != prose and room[0] <= widens[0] and widens[1] <= room[1], boxes
    assert widens[start] == prose[start] and boxes["widens"] == widens, boxes
    for held in ("reaches-h", "widens-h"):
        assert boxes[held] == prose, (held, boxes)


def test_a_section_that_carries_a_layout_keeps_its_blocks_in_its_arrangement(
    browser, serve
):
    """A section shares the column's room with what it holds, unless it carries a
    Layout that arranges its children: tiles keep each wide block in its own cell, side
    by side, with the section at the column's width. As a flow, the tiles gave both
    blocks the column's room and drew them over each other. A plain section beside it
    is the control, whose block takes the room."""
    cell = '<div id="{id}" data-width="available">Evidence {id}.</div>'
    source = leaf_page(
        "Tiles in the column",
        '<h1>Tiles in the column</h1><p id="prose">Prose sets the column.</p>'
        '<section id="tiles" class="layout-tiles">'
        + cell.format(id="first")
        + cell.format(id="second")
        + '</section><section id="plain">'
        + cell.format(id="room")
        + "</section>",
    )
    page = open_page(browser, serve(source))
    resized(page, 1600, 900)
    boxes = page.evaluate("""() => Object.fromEntries(
      ['prose', 'tiles', 'first', 'second', 'room'].map(id => {
        const box = document.getElementById(id).getBoundingClientRect();
        return [id, [Math.round(box.left), Math.round(box.right), Math.round(box.top)]];
      }))""")
    prose, tiles = boxes["prose"], boxes["tiles"]
    assert boxes["room"][0] < prose[0] and boxes["room"][1] > prose[1], boxes
    assert tiles[:2] == prose[:2], boxes
    first, second = boxes["first"], boxes["second"]
    assert first[2] == second[2] and first[1] < second[0], boxes
    assert tiles[0] <= first[0] and second[1] <= tiles[1], boxes


def test_a_block_in_a_workspace_question_fills_its_region(browser, serve):
    """A workspace states no measure, so a width written on a block in a question means
    nothing there, as it means nothing on a block beside the question."""
    source = leaf_page(
        "Question in a workspace",
        """<header><h1>Question in a workspace</h1></header>
        <div id="region"><lf-group id="asked" label="Ship it?"><h2 id="asked-h">Ship it?</h2>
          <div id="wide-evidence" data-width="wide">Evidence.</div>
          <lf-options id="choice"><lf-option id="yes">Yes</lf-option></lf-options>
        </lf-group></div>""",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1728, 900)
    width = page.evaluate(
        """id => document.getElementById(id).getBoundingClientRect().width""", "region"
    )
    for block in ("asked", "wide-evidence"):
        box = page.locator(f"#{block}").bounding_box()
        assert box["width"] == pytest.approx(width, abs=1), block


def test_growth_above_the_window_moves_nothing_read_in_a_sidebar_body(browser, serve):
    """The browser's scroll anchoring takes growth above the window into what was
    scrolled past, so the line read in a sidebar page's body stays put, as a thread's
    new reply above the screen relies on (held-news.js). The aside stands first in the
    tree and stretches along the body, holding only a sticky track, so anchoring must
    pass over it to the body: anchored on the aside, the line would move by the
    growth."""
    paragraphs = "".join(
        f'<p id="p{number}">Paragraph {number} of the evidence.</p>'
        for number in range(80)
    )
    source = leaf_page(
        "sidebar anchoring",
        '<aside id="route"><div class="layout-track"><p>The route.</p></div></aside>'
        f'<div class="layout-column" id="body">{paragraphs}</div>',
        layout="sidebar",
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 800)
    moved = page.evaluate("""async () => {
      const frame = () => new Promise(requestAnimationFrame);
      const grown = document.getElementById('p20');
      const read = document.getElementById('p26');
      scrollBy({top: grown.getBoundingClientRect().bottom + 100, behavior: 'instant'});
      await frame();
      const before = read.getBoundingClientRect().top;
      const growth = document.createElement('div');
      growth.style.blockSize = '90px';
      grown.after(growth);
      await frame();
      return {before, moved: read.getBoundingClientRect().top - before};
    }""")
    assert 0 < moved["before"] < 800, moved
    assert moved["moved"] == pytest.approx(0, abs=0.5), moved


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_growth_above_the_window_moves_nothing_read_in_a_sidebar_track(
    request, serve, engine
):
    """A sticky track scrolls its own blocks, and the browser's scroll anchoring holds
    the line read there while a block above it grows, as a widget drawing late does.
    A track that set `overflow-anchor: none` on itself would see the line move by the
    growth. The aside before the body keeps the property, which keeps the page's
    anchoring off the track."""
    follow_ups = "".join(f'<p id="f{n}">Follow-up {n} to check.</p>' for n in range(60))
    body = "".join(f"<p>Body paragraph {n} of the review.</p>" for n in range(200))
    source = leaf_page(
        "sidebar track anchoring",
        f'<aside id="route"><div class="layout-track" id="track"><div id="grown"></div>'
        f'{follow_ups}</div></aside><div id="body">{body}</div>',
        layout="sidebar",
    )
    page = open_page(request.getfixturevalue(engine), serve(source))
    resized(page, 900, 600)
    moved = page.evaluate("""async () => {
      const frame = () => new Promise(requestAnimationFrame);
      const track = document.getElementById('track');
      const read = document.getElementById('f30');
      scrollTo(0, 1500);
      track.scrollTop += read.getBoundingClientRect().top
        - track.getBoundingClientRect().top - 120;
      await frame();
      const before = read.getBoundingClientRect().top;
      document.getElementById('grown').style.blockSize = '200px';
      await frame();
      return {scrolls: track.scrollHeight > track.clientHeight, before,
              moved: read.getBoundingClientRect().top - before};
    }""")
    assert moved["scrolls"], moved
    assert moved["moved"] == pytest.approx(0, abs=0.5), moved


@pytest.mark.parametrize("shell", ["body", "child", "part"])
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_stuck_sidebar_track_keeps_its_place_to_the_page_end(
    request, serve, engine, shell
):
    """A sidebar page's stuck track stays where it sticks to the page's end, the
    document's end room included, even one reaching the window's foot, as the contents
    map does, so its start stays in view through the last of the scroll. That holds for
    a sidebar that is `main`, the child of a `main` with no Layout, and a part's, and
    beside the elements browser extensions append to the body. A footer, the sidebar's
    or one the page writes after the sidebar or after `main`, stops the track, so it
    never stands over the footer."""
    follow_ups = "".join(f"<p>Follow-up {n} to check.</p>" for n in range(80))
    body = "".join(f"<p>Body paragraph {n} of the review.</p>" for n in range(200))
    regions = (
        f'<aside id="route"><div class="layout-track" id="track">{follow_ups}</div>'
        f'</aside><div id="body">{body}</div>'
    )
    source = (
        leaf_page("sidebar track end", regions, layout="sidebar")
        if shell == "body"
        else leaf_page(
            "sidebar track end",
            f'<div class="layout-sidebar">{regions}</div>',
            layout=None,
        )
        if shell == "child"
        else leaf_page(
            "sidebar track end",
            '<header><h1>Release review</h1></header><lf-parts id="parts">'
            '<lf-part id="plan" label="Plan">'
            f'<div class="layout-sidebar">{regions}</div></lf-part></lf-parts>',
            layout=None,
        )
    )
    page = open_page(request.getfixturevalue(engine), serve(source))
    resized(page, 1400, 600)
    stood = page.evaluate(
        """async (shell) => {
      const frame = () => new Promise(requestAnimationFrame);
      const track = document.getElementById('track');
      const sidebar = track.closest('.layout-sidebar');
      const atEnd = async () => {
        scrollTo(0, document.scrollingElement.scrollHeight);
        await frame();
        return track.getBoundingClientRect();
      };
      const stops = async (place) => {
        const footer = document.createElement('footer');
        footer.textContent = 'Reviewed in March.';
        place(footer);
        const {bottom} = await atEnd();
        // Firefox lays the two edges out a rounding error apart.
        const stopped = bottom <= footer.getBoundingClientRect().top + 0.5;
        footer.remove();
        return stopped;
      };
      scrollTo(0, 1500);
      await frame();
      const {top: mid, bottom} = track.getBoundingClientRect();
      const end = (await atEnd()).top;
      // A live region a browser extension appends to the body, as password managers do.
      const extension = document.createElement('div');
      extension.setAttribute('aria-live', 'polite');
      document.body.append(extension);
      const withExtension = (await atEnd()).top;
      extension.remove();
      return {mid, end, withExtension, bottom, window: innerHeight,
              after: await stops((footer) => sidebar.after(footer)),
              // A page of parts holds nothing beside `main` (page-layout.md).
              site: shell === 'part'
                || await stops((footer) => document.querySelector('main').after(footer)),
              inSidebar: await stops((footer) => sidebar.append(footer))};
    }""",
        shell,
    )
    # The track reaches the window's foot, short only by the gap it keeps there.
    assert stood["bottom"] == pytest.approx(stood["window"] - 24, abs=1), stood
    assert stood["end"] == pytest.approx(stood["mid"], abs=0.5), stood
    assert stood["withExtension"] == pytest.approx(stood["mid"], abs=0.5), stood
    assert stood["after"], stood
    assert stood["site"], stood
    assert stood["inSidebar"], stood


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("held", ["follow-ups", "contents map"])
def test_a_sidebar_among_a_column_s_blocks_keeps_its_track_off_what_follows(
    request, serve, engine, held
):
    """A sidebar among a column page's blocks isn't the page's Layout box, so its stuck
    track ends with the sidebar rather than hanging through the document's end room
    over the column's blocks after it. The contents map's track, which stands fixed in
    the window where its sidebar spans the page, sticks here as any other does."""
    if held == "contents map":
        track = '<lf-toc id="contents"></lf-toc>'
        body = (
            '<div class="layout-column">'
            + "".join(
                f'<h2 id="part-{n}">Part {n}</h2>'
                + "".join(f"<p>Paragraph {k} of part {n}.</p>" for k in range(20))
                for n in range(10)
            )
            + "</div>"
        )
    else:
        track = "".join(f"<p>Follow-up {n} to check.</p>" for n in range(80))
        body = (
            "<div>"
            + "".join(f"<p>Body paragraph {n} of the review.</p>" for n in range(200))
            + "</div>"
        )
    after = "".join(f"<p>Column paragraph {n}.</p>" for n in range(60))
    source = leaf_page(
        "sidebar among a column's blocks",
        f'<div class="layout-sidebar"><aside><div class="layout-track" id="track">'
        f'{track}</div></aside>{body}</div><div id="after">{after}</div>',
    )
    page = open_page(request.getfixturevalue(engine), serve(source))
    resized(page, 1400, 600)
    overlap = page.evaluate("""async () => {
      const sidebar = document.querySelector('.layout-sidebar');
      scrollTo(0, scrollY + sidebar.getBoundingClientRect().bottom - 300);
      await new Promise(requestAnimationFrame);
      return document.getElementById('track').getBoundingClientRect().bottom
        - document.getElementById('after').getBoundingClientRect().top;
    }""")
    assert overlap <= 0.5, overlap


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize(
    "header", ["in the sidebar", "before the sidebar", "before main"]
)
def test_a_header_above_a_contents_map_keeps_the_map_below_it(
    request, serve, engine, header
):
    """The contents map's track stands fixed in the window only where nothing stands
    above its sidebar. A header in the sidebar, before it or before its `main`, as a
    site header, keeps the map below the header as the page opens."""
    head = '<header id="head"><h1>Release review</h1><p>Three parts.</p></header>'
    regions = (
        '<aside><div class="layout-track" id="track"><lf-toc id="contents"></lf-toc>'
        '</div></aside><div class="layout-column">'
        + "".join(
            f'<h2 id="part-{n}">Part {n}</h2>'
            + "".join(f"<p>Paragraph {k} of part {n}.</p>" for k in range(20))
            for n in range(3)
        )
        + "</div>"
    )
    if header == "in the sidebar":
        source = leaf_page("header above a map", head + regions, layout="sidebar")
    elif header == "before the sidebar":
        source = leaf_page(
            "header above a map",
            f'{head}<div class="layout-sidebar">{regions}</div>',
            layout=None,
        )
    else:
        source = leaf_page("header above a map", regions, layout="sidebar").replace(
            "<main", f"{head}<main", 1
        )
    page = open_page(request.getfixturevalue(engine), serve(source))
    resized(page, 1400, 900)
    gap = page.evaluate("""() =>
      document.getElementById('track').getBoundingClientRect().top
        - document.getElementById('head').getBoundingClientRect().bottom""")
    assert gap >= 0, gap


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_annotations_read_the_native_prose_track_with_authored_geometry(
    browser, serve, direction
):
    source = leaf_page(
        "authored tracks",
        '<h1>Reading</h1><p id="prose">A paragraph on the prose track.</p>',
        head=f"""<style>main {{direction:{direction};width:1000px;max-width:100%;
          box-sizing:border-box;padding-inline:43px;--lf-col:34rem;
          transform:scale(.85);transform-origin:top left}}</style>""",
    )
    page = open_page(browser, serve(source))
    reading = page.evaluate("""async () => {
      const {proseRect}=await import('/runtime/readings/content-layout.js');
      const prose=document.querySelector('#prose').getBoundingClientRect();
      return {computed:proseRect(),actual:{left:prose.left,right:prose.right}};
    }""")
    assert reading["computed"]["left"] == pytest.approx(
        reading["actual"]["left"], abs=0.5
    )
    assert reading["computed"]["right"] == pytest.approx(
        reading["actual"]["right"], abs=0.5
    )
