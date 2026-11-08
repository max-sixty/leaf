"""Document geometry the Layouts give natively: complete before runtime modules
activate, and keeping the browser's own behavior, such as scroll anchoring."""

import pytest
from playwright.sync_api import expect
from render_harness import displayed, leaf_page, open_page, resized, wait_until_ready

DOCUMENT = """
<aside id="route"><div class="layout-track">
  <p>Read the evidence before deciding.</p><nav><a href="#evidence">Evidence</a></nav>
</div></aside>
<div class="layout-column layout-notes" id="body">
  <h1>Review</h1>
  <section id="evidence" class="layout-flow">
    <h2>Evidence</h2>
    <div class="layout-note"><p id="prose">The passage keeps its reading measure.</p>
      <aside class="note" id="note">A short qualification.</aside></div>
    <lf-worktree-diffs id="wide"><lf-worktree id="tree" label="Changes" path="/work/leaf"
      status="clean" files="0" additions="0" deletions="0" open>
      <p>Readable before JavaScript.</p>
    </lf-worktree></lf-worktree-diffs>
  </section>
  <p id="after">The next paragraph keeps its place.</p>
</div>
"""


def test_native_sidebar_and_note_are_placed_before_widget_activation(browser, serve):
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
        read = """() => Object.fromEntries(['route','body','prose','note','wide','after']
          .map(id => [id,document.getElementById(id).getBoundingClientRect().toJSON()]))"""
        before = page.evaluate(read)
        assert before["prose"]["width"] == min(720, width - 48)
        assert (before["route"]["top"] < before["body"]["top"]) == (width == 720)
        assert (before["note"]["left"] >= before["prose"]["right"]) == (width == 1600)
        for route in held:
            route.continue_()
        page.unroute("**/leaf.js")
        wait_until_ready(page)
        assert page.evaluate(read) == before


def test_a_questions_words_keep_the_column_beside_a_wider_block(browser, serve):
    """An lf-ask draws no box of its own around its blocks, so they stand in the page's
    flow: its words and its options keep the prose's edge, and a block declaring more
    room takes it, on a page with both. A width written on the question moves nothing.
    The words used to go with the question's box, 480px left of the page's column."""
    options = (
        '<lf-options id="{id}-options" choose>'
        '<lf-option id="{id}-yes">Yes</lf-option></lf-options>'
    )
    question = (
        '<lf-ask id="{id}"{width}><h2 id="{id}-head">Ship it?</h2>'
        '<p id="{id}-premise">Because it fits.</p>{held}' + options + "</lf-ask>"
    )
    evidence = '<div id="{id}-evidence" data-width="available">Evidence.</div>'
    source = leaf_page(
        "Questions in the flow",
        '<h1>Questions in the flow</h1><p id="prose">Prose sets the column.</p>'
        '<section class="layout-flow">'
        + question.format(id="plain", width="", held="")
        + question.format(id="stated", width=' data-width="available"', held="")
        + question.format(id="holds", width="", held=evidence.format(id="holds"))
        + question.format(
            id="wrapped",
            width="",
            held="<section>" + evidence.format(id="wrapped") + "</section>",
        )
        + "</section><section>"
        + question.format(id="kept", width="", held=evidence.format(id="kept"))
        + "</section>",
    )
    page = open_page(browser, serve(source))
    resized(page, 1728, 900)
    boxes = page.evaluate("""() => Object.fromEntries(
      [...document.querySelectorAll('[id]')].filter(el => el.closest('main'))
        .map(el => {
          const box = el.getBoundingClientRect();
          return [el.id, [Math.round(box.left), Math.round(box.right)]];
        }))""")
    column = boxes["prose"]
    assert column == [504, 1224]
    for question_id in ("plain", "stated", "holds", "wrapped", "kept"):
        for part in ("head", "premise", "options"):
            assert boxes[f"{question_id}-{part}"] == column, (question_id, part, boxes)
    assert boxes["plain"] == boxes["stated"] == column, boxes
    # The block takes the room and the question's box, which its marks stand on, holds it.
    assert boxes["holds-evidence"][0] < 100 and boxes["holds-evidence"][1] > 1628, boxes
    assert boxes["holds"] == boxes["holds-evidence"], boxes
    # A plain section keeps what it holds, as it does outside a question, and the
    # question's box keeps to the column with it.
    for question_id in ("wrapped", "kept"):
        assert boxes[f"{question_id}-evidence"] == boxes[question_id] == column, boxes
    # What the question asks stands by its words, not at the edge of the evidence.
    marker = page.locator("[data-lf-margin-for='holds']")
    expect(marker).to_have_attribute("data-lf-place", "rail")
    assert marker.bounding_box()["x"] < column[1] + 100


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_flow_written_the_other_way_grows_toward_the_room(browser, serve, direction):
    """Beside a contents map the room lies on one side of the column only. A question or
    section written in the other direction from the page takes the same room as the
    page's own blocks: an available block reaches the free side, and a wide one, whose
    end faces the map, keeps to the prose. Both used to grow toward the map, the
    available block 334px past the window's edge, since the flow read the room on the
    column's start side as the room on its own."""
    other = "rtl" if direction == "ltr" else "ltr"
    options = '<lf-options id="{id}-o" choose><lf-option id="{id}-y">Yes</lf-option>'
    question = (
        f'<lf-ask id="{{id}}" dir="{other}"><h3 id="{{id}}-h">Ship it?</h3>'
        '<div id="{id}-block" data-width="{width}">Evidence.</div>'
        + options
        + "</lf-options></lf-ask>"
    )
    source = leaf_page(
        "Flows written the other way",
        '<div class="layout-sidebar"><aside><div class="layout-track">'
        '<lf-toc id="contents"></lf-toc></div></aside><div class="layout-column">'
        '<h1>Flows written the other way</h1><p id="prose">Prose sets the column.</p>'
        '<div id="room" data-width="available">Room.</div>'
        + question.format(id="reaches", width="available")
        + question.format(id="widens", width="wide")
        + f'<section class="layout-flow" dir="{other}">'
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
    for held in ("widens-block", "widens", "reaches-h", "widens-h"):
        assert boxes[held] == prose, (held, boxes)


def test_a_block_in_a_workspace_question_fills_its_region(browser, serve):
    """A workspace states no measure, so a width written on a block in a question means
    nothing there, as it means nothing on a block beside the question."""
    source = leaf_page(
        "Question in a workspace",
        """<header><h1>Question in a workspace</h1></header>
        <div id="region"><lf-ask id="asked"><h2>Ship it?</h2>
          <div id="wide-evidence" data-width="wide">Evidence.</div>
          <lf-options id="choice" choose><lf-option id="yes">Yes</lf-option></lf-options>
        </lf-ask></div>""",
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
    pass over it to the body: anchored on the aside, the line moved by the growth."""
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
    The track set `overflow-anchor: none` on itself, and the line moved by the growth,
    200px in both engines. The aside before the body keeps the property, which keeps
    the page's anchoring off the track."""
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


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_annotations_read_the_native_prose_track_with_authored_geometry(
    browser, serve, direction
):
    source = leaf_page(
        "authored tracks",
        '<h1>Reading</h1><p id="prose">A paragraph on the prose track.</p>',
        head=f"""<style>main {{direction:{direction};width:1000px;max-width:100%;
          box-sizing:border-box;padding-inline:43px;--col:34rem;
          transform:scale(.85);transform-origin:top left}}</style>""",
    )
    page = open_page(browser, serve(source))
    reading = page.evaluate("""async () => {
      const {proseRect}=await import('/runtime/content-layout.js');
      const prose=document.querySelector('#prose').getBoundingClientRect();
      return {computed:proseRect(),actual:{left:prose.left,right:prose.right}};
    }""")
    assert reading["computed"]["left"] == pytest.approx(
        reading["actual"]["left"], abs=0.5
    )
    assert reading["computed"]["right"] == pytest.approx(
        reading["actual"]["right"], abs=0.5
    )


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_note_rows_fit_their_column_without_moving_other_columns(
    browser, serve, subtests, direction
):
    source = leaf_page(
        "note tracks",
        """<section class="layout-column layout-notes" id="noted">
          <p id="intro">The passage and its note share a reading axis.</p>
          <section class="layout-flow"><section class="layout-flow">
            <div class="layout-note" id="row">
              <p id="passage">A passage with a qualification.</p>
              <aside class="note" id="qualification">The qualification belongs to
                this passage, before the next exhibit.</aside>
            </div>
            <div id="exhibit">The next exhibit.</div>
          </section></section>
          <div class="layout-column" id="nested"><p id="nested-prose">
            An independent nested column keeps its own axis.</p></div>
        </section>
        <section class="layout-column"><p id="plain">
          An unrelated column has no notes and remains centered.</p></section>
        <section class="layout-column"><p id="outer-prose">
          An inner column's note never moves this outer prose.</p>
          <section class="layout-column layout-notes" id="inner">
            <div class="layout-note"><p id="inner-prose">An independent passage.</p>
              <aside class="note" id="inner-note">Its independent qualification.</aside>
            </div>
          </section>
        </section>""",
        layout=None,
        head=f"""<style>body {{margin:0}} main {{direction:{direction}}}</style>""",
    )
    page = open_page(browser, serve(source))
    for width in (1600, 1200, 1152, 1151, 900, 390):
        with subtests.test(width=width):
            page.set_viewport_size({"width": width, "height": 900})
            boxes = page.evaluate("""() => Object.fromEntries(
              ['intro','passage','qualification','exhibit','plain','nested','nested-prose','outer-prose','inner-prose','inner-note']
                .map(id => [id,document.getElementById(id).getBoundingClientRect().toJSON()]))""")
            passage, note = boxes["passage"], boxes["qualification"]
            assert passage["width"] == min(720, width - 48)
            assert note["width"] <= passage["width"]
            assert boxes["intro"]["left"] == passage["left"]
            assert boxes["plain"]["left"] == max(24, (width - 720) / 2)
            assert boxes["outer-prose"]["left"] == boxes["plain"]["left"]
            inner, inner_note = boxes["inner-prose"], boxes["inner-note"]
            assert inner["width"] == min(720, width - 48) - 48
            assert inner_note["width"] <= inner["width"]
            nested = boxes["nested"]
            assert boxes["nested-prose"]["left"] == nested["left"] + max(
                24, (nested["width"] - 720) / 2
            )
            assert boxes["exhibit"]["top"] - note["bottom"] >= 24
            if width >= 1152:
                assert note["top"] == passage["top"]
                if direction == "ltr":
                    assert note["left"] - passage["right"] == 24
                else:
                    assert passage["left"] - note["right"] == 24
            else:
                assert note["top"] - passage["bottom"] == 8
                assert note["left"] == passage["left"]
