"""End-to-end journey and durable draft tests."""

import base64
import itertools
import re

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, append_command
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import service as service_model
from leaf.render_checks import one_frame, rendered, wait_until_ready
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_interaction import (
    ASK_PAGE,
    SEATED_QUESTION_PAGE,
    live_url,
    panel_comment,
)
from render_cases_layout import (
    glyph_action_face,
    in_threads_scrollport,
    token_colour,
)
from render_cases_navigation import (
    DRAFT_EDITED,
    DRAFT_TEXT,
    JOURNEY_V1,
    JOURNEY_V2,
    KEYS_PAGE,
    NOTED_PAGE,
    SENTENCE,
    SMOOTH_LONG_PAGE,
    _publish,
    compose,
    composer_quote,
    go_to_address,
    painted,
    pending_text,
    source_revision,
)
from render_harness import (
    LANDING_TOP,
    LONG_PAGE,
    RELEASE_FOCUS,
    REPLY_HOST_PAGE,
    ROOT,
    CutOff,
    _traffic,
    _until,
    compare_with,
    consume_browser_errors,
    draft_control,
    draft_key,
    example_media,
    expect_comment_notes,
    held_stale,
    hold_pending_thread_presentation,
    hold_selection,
    holding,
    leaf_page,
    open_page,
    page_comment,
    panel_settled,
    primed,
    refuse,
    reported_browser_errors,
    resized,
    round_trip,
    scroll_settled,
    select_words,
    sending,
    shortcut_bar_text,
    stamp_page,
    stored_draft,
    stored_draft_settled,
    stored_draft_text,
    take_browser_errors,
    ticked,
    told,
    until_draft_settled,
    wait_for_revision,
    write,
)


@pytest.mark.parametrize(
    ("unique", "tall", "control"),
    [
        (True, False, "editor"),
        (False, True, "editor"),
        (False, False, "checkbox"),
        (False, False, "button"),
    ],
    ids=["unique", "tall-repeated", "checkbox", "button"],
)
def test_a_visible_focused_element_is_the_reading_place_until_the_reader_scrolls_away(
    browser, serve, unique, tall, control
):
    """A pane carries visible focus across posture changes without pulling back old focus."""

    def context(prefix):
        return "".join(
            f"<p>{prefix} paragraph {number if unique else ''} stays where the reader left it.</p>"
            for number in range(35)
        )

    before = context("Reading")
    after = context("Following" if unique else "Reading")
    field_height = ' style="height:1000px"' if tall else ""
    field_markup = {
        "editor": f'<textarea aria-label="Working draft"{field_height}></textarea>',
        "checkbox": '<label><input type="checkbox">Working choice</label>',
        "button": '<button type="button">Working action</button>',
    }[control]
    source = leaf_page(
        "Editing in a reading region",
        f'<lf-pane id="editor-pane" label="Working text"><div>{before}'
        f"{field_markup}"
        f"{after}</div></lf-pane>",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1366, 768)
    role, name = {
        "editor": ("textbox", "Working draft"),
        "checkbox": ("checkbox", "Working choice"),
        "button": ("button", "Working action"),
    }[control]
    field = page.get_by_role(role, name=name)
    field.click()
    if control == "editor":
        page.keyboard.type("The reader is working here")
    rendered(page)
    if control != "editor":
        # Activation can keep focus on the same node without emitting an input.
        # Settle the focus record first so it cannot accidentally cover the key.
        field.press("Space" if control == "checkbox" else "Enter")
        rendered(page)

    def in_view():
        return field.evaluate(
            """async (node, tall) => {
          const {seenRect, shownBox} = await window.__lfRuntimeImport('/runtime/geometry.js');
          const seen = seenRect(node, new Map()), rect = shownBox(node);
          return Boolean(seen && (tall
            ? seen.bottom - seen.top > 10
            : seen.top <= rect.top + 1 && seen.bottom >= rect.bottom - 1));
        }""",
            tall,
        )

    assert in_view()
    resized(page, 390, 760)
    rendered(page)
    expect(field).to_be_focused()
    if control == "editor":
        expect(field).to_have_value("The reader is working here")
    assert in_view(), "the new page scroller lost the live focused place"
    if control == "button":
        # Clicking the same focused control must name it again, even though the
        # browser has no new focus transition to announce.
        field.click()
        rendered(page)
        resized(page, 1366, 768)
        rendered(page)
        expect(field).to_be_focused()
        assert in_view(), "a repeated click lost the focused reading place"

    # Focus alone is not a reading place: scrolling elsewhere deliberately leaves
    # the same element focused, and the next posture must retain that new reading.
    page.mouse.wheel(0, -10000)
    page.wait_for_function("document.scrollingElement.scrollTop === 0")
    scroll_settled(page)
    rendered(page)
    expect(field).to_be_focused()
    assert not in_view()
    resized(page, 1366, 768)
    rendered(page)
    expect(field).to_be_focused()
    assert not in_view(), "stale focus displaced the reader's new place"


@pytest.mark.parametrize("region", [False, True], ids=["page", "pane"])
def test_a_page_keeps_its_place_below_the_banner_as_the_window_changes_width(
    browser, serve, region
):
    """The banner takes a second row when the window narrows. The browser's scroll
    anchoring holds the line the reader landed on where it stood in the window, which is
    now under the banner; the page moves with the banner instead, in a document as in
    a pane the page carries, and back again when the window widens. A control the reader
    has focused at the top of the page, where the browser anchors nothing, stays in view
    as the words above it rewrap."""
    lines = "".join(
        f'<p id="line-{n}">Line {n} of the incident, long enough to rewrap when the '
        "window narrows to a phone and the banner takes its second row.</p>"
        for n in range(60)
    )
    lines = (
        f'<lf-pane id="reading" label="Reading"><div>{lines}</div></lf-pane>'
        if region
        else lines
    )
    question = (
        '<lf-ask id="ask"><h2>Which way?</h2><lf-options id="way" choose>'
        '<lf-option id="way-one"><strong>One</strong> the first way.</lf-option>'
        '<lf-option id="way-two"><strong>Two</strong> the second way.</lf-option>'
        "</lf-options></lf-ask>"
    )
    opening = "".join(
        f"<p>Paragraph {n} opens the page with enough words that it rewraps to more "
        "lines when the window narrows, pushing what follows further down.</p>"
        for n in range(6)
    )
    source = leaf_page("Keeping a place", f"{opening}{question}{lines}")
    page = open_page(browser, serve(source))
    resized(page, 1280, 800)
    rendered(page)
    reading = """async (id) => {
      const {landingBand} = await window.__lfRuntimeImport('/runtime/geometry.js');
      let node = document.getElementById(id) ?? document.activeElement;
      while (!id && node.shadowRoot?.activeElement) node = node.shadowRoot.activeElement;
      return {band: landingBand(document.scrollingElement).top,
              top: node.getBoundingClientRect().top,
              bottom: node.getBoundingClientRect().bottom};
    }"""

    page.evaluate("location.hash = 'line-30'")
    rendered(page)
    landed = page.evaluate(reading, "line-30")
    below = landed["top"] - landed["band"]
    resized(page, 700, 800)
    rendered(page)
    narrowed = page.evaluate(reading, "line-30")
    assert narrowed["band"] > landed["band"], "the banner should take a second row"
    assert narrowed["top"] - narrowed["band"] == pytest.approx(below, abs=2), narrowed
    resized(page, 1280, 800)
    rendered(page)
    assert page.evaluate(reading, "line-30") == pytest.approx(landed, abs=2)

    page = open_page(browser, serve(source))
    resized(page, 1280, 1100)
    rendered(page)
    page.locator("#way-one").evaluate(
        """option => [option, ...option.shadowRoot?.querySelectorAll('*') ?? [],
                     ...option.querySelectorAll('*')].find(node => node.tabIndex >= 0).focus()"""
    )
    rendered(page)
    focused = page.evaluate(reading, None)
    assert page.evaluate("document.scrollingElement.scrollTop") == 0
    assert focused["bottom"] < 1100, focused
    resized(page, 420, 1100)
    rendered(page)
    assert page.evaluate(reading, None)["bottom"] < 1100, (
        "the focused option left the window"
    )


@pytest.mark.parametrize("wheel", [False, True], ids=["landed", "wheel-over-pane"])
def test_a_heading_above_a_flowing_pane_keeps_its_place_as_the_window_changes_width(
    browser, serve, wheel
):
    """The reader landed on a section's heading; a pane the page carries starts lower in
    the window. Text between them rewraps as the window changes width, so the pane's own
    first line and the heading cannot both keep their distances. The heading is what the
    reader reads, so it stays where it stood below the banner, at each width and back,
    even after they turned the wheel with the pointer over the pane's words, as a finger
    scrolling a phone over a queue does."""
    filler = "".join(
        f"<p>Paragraph {n} sets the scene in enough words to rewrap to more lines when "
        "the window narrows to a phone, pushing what follows further down.</p>"
        for n in range(12)
    )
    lead = "".join(
        f"<p>Lead {n} introduces the pane below in enough words that it rewraps to "
        "more lines as the window narrows, moving the pane against the heading.</p>"
        for n in range(3)
    )
    lines = "".join(
        f"<p>Line {n} of the incident, long enough to read as its own passage.</p>"
        for n in range(30)
    )
    source = leaf_page(
        "Heading above a pane",
        f'{filler}<h2 id="section">The section the reader landed on</h2>{lead}'
        f'<lf-pane id="reading" label="Reading"><div>{lines}</div></lf-pane>{filler}',
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 800)
    rendered(page)
    below = """async () => {
      const {landingBand} = await window.__lfRuntimeImport('/runtime/geometry.js');
      const pane = document.querySelector('#reading').getBoundingClientRect();
      return {heading: document.getElementById('section').getBoundingClientRect().top
                - landingBand(document.scrollingElement).top,
              paneShown: pane.top < innerHeight && pane.bottom > 0};
    }"""
    page.evaluate("location.hash = 'section'")
    rendered(page)
    if wheel:
        box = page.locator("#reading p").first.bounding_box()
        page.mouse.move(box["x"] + 20, min(box["y"] + 5, 780))
        before = page.evaluate("document.scrollingElement.scrollTop")
        page.mouse.wheel(0, -8)
        page.wait_for_function(f"document.scrollingElement.scrollTop < {before}")
        scroll_settled(page)
        rendered(page)
    landed = page.evaluate(below)
    assert landed["paneShown"], landed
    for width in (390, 1280, 390, 1280):
        resized(page, width, 800)
        rendered(page)
        assert page.evaluate(below)["heading"] == pytest.approx(
            landed["heading"], abs=2
        ), width


# A page script's scroll while the page holds the place a width change restored. Each
# takes `grow` and `frames`. "settled" runs once the restore has settled; the others are
# armed before the resize and run in the frames after it, while the restore and the
# layout's settling are still at work.
HELD_PAGE_MOVES = {
    # The layout grows and the script scrolls in the same animation frame.
    "same-frame": (
        "settled",
        400,
        """async () => {
      await frames(1);
      grow();
      document.scrollingElement.scrollBy(0, 400);
    }""",
    ),
    # The layout grows, and the script scrolls in the next frame, before the observers
    # hear that layout.
    "first-frame": (
        "settled",
        400,
        """async () => {
      grow();
      await frames(1);
      document.scrollingElement.scrollBy(0, 400);
    }""",
    ),
    # The script scrolls a frame after the layout it grew was laid out.
    "next-frame": (
        "settled",
        400,
        """async () => {
      grow();
      await frames(2);
      document.scrollingElement.scrollBy(0, 400);
    }""",
    ),
    # One and two frames after the resize, while the restore lands.
    "1-frame-after-resize": (
        "armed",
        400,
        """() => addEventListener('resize',
      async () => { await frames(1); grow(); document.scrollingElement.scrollBy(0, 400); },
      {once: true})""",
    ),
    "2-frames-after-resize": (
        "armed",
        400,
        """() => addEventListener('resize',
      async () => { await frames(2); grow(); document.scrollingElement.scrollBy(0, 400); },
      {once: true})""",
    ),
    # A smooth scroll after the resize, the layout growing on each of the next six frames.
    "smooth-with-growth": (
        "armed",
        800,
        """() => addEventListener('resize',
      async () => {
        await frames(1);
        document.scrollingElement.scrollBy({top: 800, behavior: 'smooth'});
        for (let n = 0; n < 6; n++) { await frames(1); grow(); }
      }, {once: true})""",
    ),
    # A script answering the first scroll after the resize in the next frame. Answered in
    # the same task, its scroll lands in the frame layout settles in and reads as
    # layout's, here as on main.
    "frame-after-first-scroll": (
        "armed",
        400,
        """() => addEventListener('resize', () =>
      addEventListener('scroll', async () => {
        await frames(1); document.scrollingElement.scrollBy(0, 400);
      }, {once: true}), {once: true})""",
    ),
}

HELD_PAGE_HELPERS = """() => {
  window.frames = (n) => new Promise((done) => {
    const tick = () => (n-- > 0 ? requestAnimationFrame(tick) : done());
    tick();
  });
  window.grow = () => {
    const room = document.createElement('div');
    room.style.height = '200px';
    document.querySelector('main').append(room);
  };
}"""


def held_page(browser, serve):
    """A long page read by wheel at 1280, to be narrowed to 390, which restores the
    place."""
    lines = "".join(
        f"<p>Line {n} of a long page, long enough to read as a passage of its own.</p>"
        for n in range(200)
    )
    page = open_page(browser, serve(leaf_page("Held page", lines)))
    resized(page, 1280, 800)
    rendered(page)
    page.mouse.move(400, 400)
    page.mouse.wheel(0, 2000)
    page.wait_for_function("document.scrollingElement.scrollTop > 1500")
    scroll_settled(page)
    rendered(page)
    page.evaluate(HELD_PAGE_HELPERS)
    return page


@pytest.mark.parametrize("move", list(HELD_PAGE_MOVES))
def test_a_script_scroll_moves_a_held_page(browser, serve, move):
    """After a width change the page holds the reader's place and applies it again as
    the layout settles. A page script that scrolls, before the restore has landed, as it
    lands, or after, with the layout growing around it or not, has moved the page: the
    page keeps that scroll through the next layout change, and the next width change
    starts from where the script left it, not from the held place."""
    when, by, script = HELD_PAGE_MOVES[move]
    scrolled = "document.scrollingElement.scrollTop"
    # Where the restore alone leaves the page, with no script.
    control = held_page(browser, serve)
    resized(control, 390, 800)
    rendered(control)
    restored = control.evaluate(scrolled)
    control.context.close()

    page = held_page(browser, serve)
    if when == "armed":
        page.evaluate(script)
    resized(page, 390, 800)
    rendered(page)
    if when == "settled":
        page.evaluate(script)
    scroll_settled(page)
    rendered(page)
    moved = page.evaluate(scrolled)
    assert moved > restored + by - 100, f"the script's scroll was undone ({moved})"
    page.evaluate(
        "document.querySelector('main').append("
        "Object.assign(document.createElement('p'), {textContent: 'More.'}))"
    )
    rendered(page)
    assert page.evaluate(scrolled) == pytest.approx(moved, abs=2)
    line = page.evaluate(
        """() => {
          const band = parseFloat(getComputedStyle(document.scrollingElement)
            .scrollPaddingTop) || 0;
          const line = [...document.querySelectorAll('main p')]
            .find(p => p.getBoundingClientRect().top >= band);
          line.id = 'read-line';
          return line.getBoundingClientRect().top - band;
        }"""
    )
    resized(page, 1280, 800)
    rendered(page)
    after = page.evaluate(
        """() => document.getElementById('read-line').getBoundingClientRect().top
          - (parseFloat(getComputedStyle(document.scrollingElement)
            .scrollPaddingTop) || 0)"""
    )
    assert 0 <= after <= line + 60, (line, after)


def test_a_bounded_box_holds_its_place_while_its_layout_settles(browser, serve):
    """A box that scrolls on its own holds the place a width change restored in it, as
    the page does: content above the reader that a widget draws a frame later is put
    back behind them, with no anchoring of the browser's to do it, as in Safari."""
    lines = "".join(
        f'<p id="line-{n}">Line {n} of the bounded log.</p>' for n in range(80)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Held box",
                '<h1>Held box</h1><section id="log" style="height: 400px;'
                f' overflow: auto; overflow-anchor: none"><div id="late"></div>{lines}'
                "</section>" + "<p>After the log.</p>" * 40,
            )
        ),
    )
    resized(page, 1200, 800)
    rendered(page)
    page.evaluate("""async () => {
      const {registerReadingRegion} = await window.__lfRuntimeImport('/runtime/widget-api.js');
      const body = document.getElementById('log');
      registerReadingRegion({id: body.id, host: body, body});
    }""")
    rendered(page)
    box = page.locator("#log").bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 100)
    page.mouse.wheel(0, 900)
    scroll_settled(page)
    rendered(page)
    reading = """(id) => {
      const top = document.getElementById('log').getBoundingClientRect().top;
      const line = id ? document.getElementById(id) : [...document.querySelectorAll(
        '#log p')].find((p) => p.getBoundingClientRect().top >= top - 1);
      return {id: line.id, below: line.getBoundingClientRect().top - top};
    }"""
    read = page.evaluate(reading, None)
    page.evaluate(
        """() => addEventListener('resize', async () => {
          for (let n = 0; n < 2; n++) await new Promise(requestAnimationFrame);
          document.getElementById('late').style.height = '200px';
        }, {once: true})"""
    )
    resized(page, 700, 800)
    rendered(page)
    scroll_settled(page)
    rendered(page)
    assert page.evaluate(reading, read["id"])["below"] == pytest.approx(
        read["below"], abs=2
    )


def test_a_script_scroll_as_content_grows_above_ends_the_hold(browser, serve):
    """Long after a width change restored the gallery's place, one frame grows content
    above the reader, which anchoring answers, and a script scrolls on. The box and its
    landmark moved by different distances, which reads as layout's only while the
    shift's layout settles; after that it is a move someone made, so the next width
    change starts from where the script left the page, not from the held place."""
    gallery = ROOT / "examples/developer/feature-gallery.html"
    page = open_page(browser, serve(gallery))
    resized(page, 390, 800)
    rendered(page)
    page.evaluate("location.hash = 'bg-side-list'")
    rendered(page)
    box = page.locator("#bg-side-list-guide").bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 5)
    page.mouse.wheel(0, 8)
    scroll_settled(page)
    rendered(page)
    resized(page, 1200, 800)
    rendered(page)
    heading = """() => document.querySelector('#bg-side-list h2').getBoundingClientRect().top
      - (parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop) || 0)"""
    held = page.evaluate(heading)
    page.evaluate(
        """() => new Promise(done => requestAnimationFrame(() => {
          const late = document.createElement('div');
          late.style.height = '300px';
          const section = document.getElementById('bg-side-list');
          section.parentNode.insertBefore(late, section);
          document.scrollingElement.scrollBy(0, 400);
          done();
        }))"""
    )
    scroll_settled(page)
    rendered(page)
    assert page.evaluate(heading) < held - 300, "the script's scroll was undone"
    resized(page, 390, 800)
    rendered(page)
    assert page.evaluate(heading) < held - 300, "the held place came back"


def test_a_page_that_never_settles_lets_the_held_place_go_after_a_while(browser, serve):
    """A chart whose box breathes forever keeps the page's rendering from ever reading
    settled. A width change restores the reader's place and holds it while the layout
    settles, but no longer than a moment: well after, a script that scrolls as content
    grows above the reader moved the page, and the next width change starts from
    there rather than putting the held place back."""
    lead = "".join(
        f"<p>Lead paragraph {n} has enough words to rewrap at a phone width and push"
        " what follows further down the page.</p>"
        for n in range(30)
    )
    body = "".join(
        f"<p>Body paragraph {n} has enough words to rewrap at a phone width and push"
        " what follows further down the page.</p>"
        for n in range(40)
    )
    source = leaf_page(
        "A page that never settles",
        "<style>@keyframes breathe { from { width: 60%; } to { width: 100%; } }"
        " .breathe #breathing { animation: breathe 3s linear infinite alternate; }"
        "</style>"
        '<div id="breathing"><lf-chart id="spin" data-height="120"><pre>\n'
        '{ ariaLabel: "Two teams", marks: [Plot.barY([{team: "a", n: 12},'
        ' {team: "b", n: 19}], {x: "team", y: "n"})] }\n</pre></lf-chart></div>'
        f'{lead}<section id="read"><h2>The section the reader reads</h2>{body}</section>',
    )
    page = open_page(browser, serve(source))
    page.evaluate("document.documentElement.classList.add('breathe')")

    def settle():
        # The page never reads settled, so wait out its scrolls and a few frames.
        scroll_settled(page)
        page.wait_for_timeout(300)
        one_frame(page)

    resized(page, 390, 800)
    settle()
    page.evaluate("location.hash = 'read'")
    settle()
    box = page.locator("#read p").first.bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 5)
    page.mouse.wheel(0, 8)
    settle()
    resized(page, 1200, 800)
    settle()
    heading = """() => document.querySelector('#read h2').getBoundingClientRect().top
      - (parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop) || 0)"""
    held = page.evaluate(heading)
    page.wait_for_timeout(1500)
    page.evaluate(
        """() => new Promise(done => requestAnimationFrame(() => {
          const late = document.createElement('div');
          late.style.height = '300px';
          const section = document.getElementById('read');
          section.parentNode.insertBefore(late, section);
          document.scrollingElement.scrollBy(0, 400);
          done();
        }))"""
    )
    settle()
    assert page.evaluate(heading) < held - 300, "the script's scroll was undone"
    resized(page, 390, 800)
    settle()
    assert page.evaluate(heading) < held - 300, "the held place came back"


def edge_word(blocks):
    """A page expression `(step, band)` for the first word of the `blocks` (a selector)
    whose line stands at or below the landing band, written down on 'take' and found
    again on any other step: how far below the band it stands, and how far into its
    paragraph it is."""
    return (
        """(step, band) => {
  const range = document.createRange();
  const top = (text, at, length) => {
    range.setStart(text, at);
    range.setEnd(text, at + length);
    const rect = range.getClientRects()[0];
    return rect && {top: rect.top, middle: (rect.top + rect.bottom) / 2};
  };
  const blocks = [...document.querySelectorAll(BLOCKS)];
  if (step === 'take') {
    for (const [block, p] of blocks.entries())
      for (const text of [...p.childNodes].filter((n) => n.nodeType === 3))
        for (const word of text.data.matchAll(/\\S+/g)) {
          const at = top(text, word.index, word[0].length);
          if (at && at.middle >= band) {
            window.__edgeWord = {block, node: [...p.childNodes].indexOf(text),
              at: word.index, length: word[0].length};
            return {below: at.top - band,
              within: at.top - p.getBoundingClientRect().top};
          }
        }
    return null;
  }
  const {block, node, at, length} = window.__edgeWord;
  return {below: top(blocks[block].childNodes[node], at, length).top - band};
}"""
    ).replace("BLOCKS", repr(blocks))


def test_paging_down_from_a_landed_section_keeps_the_paged_passage(browser, serve):
    """A fragment lands on a section and focuses it; the reader pages down through it.
    Focus on a section the reader reads through names the passage they paged to, not
    the section, so a width change keeps that passage where they read it, without the
    browser's anchoring to hold it: the line at the landing edge, though the paragraph
    holding it starts above the edge and rewraps above that line."""
    opening = "".join(
        f"<p>Opening paragraph {n}, words enough to rewrap as the window changes.</p>"
        for n in range(10)
    )
    section = "".join(
        f"<p>Section paragraph {n} carries its own words, long enough to quote as a "
        "landmark and to rewrap at a phone's width.</p>"
        for n in range(80)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Paging a section",
                # Without native anchoring, which Safari lacks, the page's own place
                # is all that keeps the passage.
                "<style>html { overflow-anchor: none; }</style>"
                f'{opening}<section id="landed"><h2>The landed section</h2>{section}'
                "</section>",
            )
        ),
    )
    resized(page, 390, 800)
    rendered(page)
    page.evaluate("location.hash = 'landed'")
    rendered(page)
    page.keyboard.press("PageDown")
    page.wait_for_function("document.scrollingElement.scrollTop > 0")
    scroll_settled(page)
    rendered(page)
    place = f"async (step) => ({edge_word('main p')})(step, {LANDING_TOP})"
    read = page.evaluate(place, "take")
    assert read["within"] > 0, "the page should stop partway into a paragraph"
    for width in (1200, 390):
        resized(page, width, 800)
        rendered(page)
        assert page.evaluate(place, "read")["below"] == pytest.approx(
            read["below"], abs=4
        ), width


# Shapes of what stands at the landing edge in the column the reader scrolls. Each
# names where the pointer rests while the reader scrolls (none: it has not moved over
# the page, as when they read by keyboard), how far to scroll, and a reading
# `(step, band)` of where what they read stands, which may stray by `tolerance`. A
# figure taller than the window draws no text on screen, so what the reader sees is
# the part of it at the edge: how far through its height the edge cuts. With its
# caption on screen below it, the figure the edge cuts is still what they see. A box
# that scrolls on its own, scrolled partway, stands at the edge as a figure does: its
# words move with its own scroll, not the page's. Two columns stack as the window
# narrows; the reader scrolls the right one. A nav of short labels stands beside the
# text and stacks above it: the reader reads the text, whether the pointer rests on the
# nav or nowhere. A wide exhibit lower on screen reaches into the margin the pointer
# rests in, while the reader's paragraph stands at the edge.
TWO_COLUMNS = (
    "<style>.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem }"
    " @media (width < 900px) { .cols { grid-template-columns: 1fr } }</style>"
    "<div class='cols'><div>"
    + "".join(
        f"<p>Left column note {n}, a passage long enough to quote.</p>"
        for n in range(30)
    )
    + "</div><div id='right'>"
    + "".join(
        f"<p id='r{n}'>Right column passage {n}, which the reader is reading now.</p>"
        for n in range(30)
    )
    + "</div></div>"
)
NAV_BESIDE_TEXT = (
    "<style>.split { display: grid; grid-template-columns: 220px 1fr; gap: 2rem }"
    " @media (width < 900px) { .split { grid-template-columns: 1fr } }</style>"
    "<div class='split'><nav><ul>"
    + "".join(f"<li id='n{n}'>Part {n}</li>" for n in range(80))
    + "</ul></nav><div>"
    + "".join(
        "<p id='t{n}'>{words}</p>".format(
            n=n, words=" ".join(f"t{n}w{i}" for i in range(40))
        )
        for n in range(60)
    )
    + "</div></div>"
)


def landed_at(target, below):
    """A page expression for the scroll that puts `target`'s top `below` the band."""
    return f"""async () => document.querySelector({target!r}).getBoundingClientRect().top
      - ({LANDING_TOP}) - {below}"""


def top_below(target):
    """A reading of how far below the band `target`'s top stands."""
    return f"""(step, band) =>
      document.querySelector({target!r}).getBoundingClientRect().top - band"""


FIGURE_ABOVE_CAPTION = {
    "content": "".join(
        "<p>" + " ".join(f"p{n}w{i}" for i in range(150)) + "</p>" for n in range(6)
    )
    + '<svg id="edge" viewBox="0 0 100 120" style="display:block;width:100%;'
    'height:auto">'
    + "".join(
        f'<rect x="0" y="{n * 10}" width="100" height="10"'
        f' fill="hsl({n * 12} 60% 60%)"/>'
        for n in range(12)
    )
    + "</svg><p>Figure 1. "
    + " ".join(f"c{i}" for i in range(30))
    + "</p>",
    "pointer": "#edge",
    "distance": f"""async () => {{
      const box = document.getElementById('edge').getBoundingClientRect();
      return box.top - ({LANDING_TOP}) + 0.4 * box.height;
    }}""",
    "reading": """(step, band) => {
      const box = document.getElementById('edge').getBoundingClientRect();
      return (band - box.top) / box.height;
    }""",
    "tolerance": 0.01,
}


EDGE_SHAPES = {
    "figure": {
        "content": "".join(
            "<p>" + " ".join(f"p{n}w{i}" for i in range(150)) + "</p>"
            for n in range(12)
        )
        + '<svg id="edge" viewBox="0 0 100 300" style="display:block;width:100%;'
        'height:auto">'
        + "".join(
            f'<rect x="0" y="{n * 10}" width="100" height="10"'
            f' fill="hsl({n * 12} 60% 60%)"/>'
            for n in range(30)
        )
        + "</svg>",
        "pointer": "#edge",
        "distance": f"""async () => {{
          const box = document.getElementById('edge').getBoundingClientRect();
          return box.top - ({LANDING_TOP}) + 0.4 * box.height;
        }}""",
        "reading": """(step, band) => {
          const box = document.getElementById('edge').getBoundingClientRect();
          return (band - box.top) / box.height;
        }""",
        "tolerance": 0.01,
    },
    "figure-above-caption": FIGURE_ABOVE_CAPTION,
    # The same figure read from a narrow window, the column at the window's edge, with
    # the pointer nowhere over the page.
    "figure-above-caption-from-narrow": {
        **FIGURE_ABOVE_CAPTION,
        "pointer": None,
        "start": 600,
    },
    "box-clipping-what-hangs-past-it": {
        "content": '<div id="article" style="overflow: hidden; position: relative">'
        + "".join(
            "<p>" + " ".join(f"a{n}w{i}" for i in range(120)) + "</p>"
            for n in range(10)
        )
        + "<img alt='' style='display: block; height: 40px; width: 40px;"
        " margin-bottom: -12px' src='data:image/svg+xml,"
        "%3Csvg xmlns=%22http://www.w3.org/2000/svg%22/%3E'></div>",
        "pointer": "#article",
        "distance": landed_at("#article p:nth-of-type(5)", -60),
        "reading": f"(step, band) => ({edge_word('#article p')})(step, band).below",
        "tolerance": 3,
    },
    "box-scrolling-alone": {
        "content": "".join(
            "<p>" + " ".join(f"p{n}w{i}" for i in range(60)) + "</p>" for n in range(6)
        )
        + '<div id="inner" tabindex="0" style="height: 420px; overflow: auto">'
        + "".join(
            "<p>" + " ".join(f"i{n}w{i}" for i in range(40)) + "</p>" for n in range(30)
        )
        + "</div><p>"
        + " ".join(f"a{i}" for i in range(60))
        + "</p>",
        "setup": "document.getElementById('inner').scrollTop = 900",
        "pointer": None,
        "distance": landed_at("#inner", -200),
        "reading": """(step, band) => {
          const box = document.getElementById('inner').getBoundingClientRect();
          return band - box.top;
        }""",
        "tolerance": 3,
    },
    "right-column": {
        "content": TWO_COLUMNS,
        "pointer": "#r10",
        "distance": landed_at("#r10", 5),
        "reading": top_below("#r10"),
        "tolerance": 3,
    },
    "nav-under-pointer": {
        "content": NAV_BESIDE_TEXT,
        "pointer": "#n3",
        "distance": landed_at("#t12", 5),
        "reading": f"(step, band) => ({edge_word('.split > div p')})(step, band).below",
        "tolerance": 3,
    },
    "nav-with-no-pointer": {
        "content": NAV_BESIDE_TEXT,
        "pointer": None,
        "distance": landed_at("#t12", 5),
        "reading": f"(step, band) => ({edge_word('.split > div p')})(step, band).below",
        "tolerance": 3,
    },
    "wide-exhibit-in-margin": {
        "content": "".join(
            "<p>" + " ".join(f"o{n}w{i}" for i in range(60)) + "</p>" for n in range(6)
        )
        + '<p id="long">'
        + " ".join(f"w{i}" for i in range(200))
        + '</p><div data-width="wide"><p id="wide">'
        + " ".join(f"x{i}" for i in range(80))
        + "</p></div>",
        "pointer": "#wide",
        "distance": landed_at("#long", -150),
        "reading": f"(step, band) => ({edge_word('#long')})(step, band).below",
        "tolerance": 3,
    },
}


@pytest.mark.parametrize("shape", list(EDGE_SHAPES))
def test_a_width_change_keeps_what_stands_at_the_landing_edge(browser, serve, shape):
    """The reader scrolls until what they read stands at the landing edge: 40% of the
    way into a figure, taller than the window or with its caption below it; partway
    into a box that scrolls on its own; a paragraph of the right column of two; a
    paragraph of the text beside a nav of short labels; or a line partway into a
    paragraph while the pointer rests in a margin that only a wide exhibit lower on
    screen reaches. As the window narrows and widens, the figure scales and columns
    stack, and at each width the reader still sees what they saw at the edge: the same
    part of the figure or the box, not its top where it stood, the caption below it, a
    line inside the box, nor the old offset; and the line or paragraph they read, not
    the left column's, the nav's, or the exhibit's, which a reading in document order
    or under the pointer alone would take."""
    case = EDGE_SHAPES[shape]
    filler = "".join(
        f"<p>Filler paragraph {n} keeps the page long enough to scroll freely.</p>"
        for n in range(40)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "What stands at the edge", f"<h1>Edge</h1>{case['content']}{filler}"
            )
        ),
    )
    resized(page, case.get("start", 1200), 800)
    rendered(page)
    if "setup" in case:
        page.evaluate(case["setup"])
    distance = page.evaluate(case["distance"])
    if case["pointer"]:
        box = page.locator(case["pointer"]).bounding_box()
        page.mouse.move(box["x"] + 10, 400)
        page.mouse.wheel(0, distance)
    else:
        page.evaluate(f"document.scrollingElement.scrollBy(0, {distance})")
    scroll_settled(page)
    rendered(page)

    def now(step):
        return page.evaluate(
            f"async (step) => ({case['reading']})(step, {LANDING_TOP})", step
        )

    read = now("take")
    for width in (600, 1200, 800, 1200):
        resized(page, width, 800)
        rendered(page)
        assert now("read") == pytest.approx(read, abs=case["tolerance"]), width


@pytest.mark.parametrize("bounded", [False, True])
def test_typing_in_a_visible_inline_reply_keeps_the_reading_position(
    browser, serve, bounded
):
    """Keeping a reply's controls visible does not reveal its already-scrolled-past turns."""
    content = """
<div style="height:900px"></div>
<lf-test-plan id="hub" label="Tasks"><lf-test-task id="jobs" status="active" talk>
What should we do next?</lf-test-task></lf-test-plan>
<div style="height:900px"></div>
"""
    if bounded:
        content = (
            '<div id="reader" data-bound="start" style="height:480px">'
            + content
            + "</div>"
        )
    url = serve(leaf_page("Reply reading", content))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "text": "A short question the reader has already passed.",
            "anchor": {"section": "jobs"},
        },
    )
    page = open_page(browser, url)
    thread = page.locator("#jobs .lf-page-thread")
    reply = thread.locator("leaf-text")
    reply.click()
    reply.evaluate(
        """(input, bounded) => {
      const scroller = bounded ? document.querySelector('#reader') : document.scrollingElement;
      const top = bounded ? scroller.getBoundingClientRect().top : 0;
      scroller.scrollBy(0, input.getBoundingClientRect().top - top - 55);
    }""",
        bounded,
    )
    scroll_settled(page)
    before = page.evaluate(
        """bounded => ({
      scroll: (bounded ? document.querySelector('#reader') : document.scrollingElement).scrollTop,
      reply: document.querySelector('#jobs leaf-text').getBoundingClientRect().top,
      thread: document.querySelector('#jobs .lf-page-thread').getBoundingClientRect().top,
    })""",
        bounded,
    )
    assert before["thread"] < (
        page.locator("#reader").bounding_box()["y"] if bounded else 0
    ), before
    expect(reply).to_be_focused()
    page.keyboard.type("A")
    round_trip(page)
    after = page.evaluate(
        """bounded => ({
      scroll: (bounded ? document.querySelector('#reader') : document.scrollingElement).scrollTop,
      reply: document.querySelector('#jobs leaf-text').getBoundingClientRect().top,
    })""",
        bounded,
    )
    assert after["scroll"] == pytest.approx(before["scroll"], abs=1), (before, after)
    assert after["reply"] == pytest.approx(before["reply"], abs=1), (before, after)


@pytest.mark.parametrize("installation", ["in-place", "fresh"])
def test_an_automatic_revision_keeps_the_empty_panel_reply_focused(
    browser, serve, installation
):
    """A revision, installed in place or as a fresh document, leaves the Threads
    panel's empty reply box focused and empty."""
    url = live_url(serve(REPLY_HOST_PAGE))
    root = panel_comment(serve.page_dir, "Should reads fall back?", author="agent")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    thread.locator(":scope > .lf-thread-summary").click()
    editor = thread.locator(".lf-thread-reply leaf-text")
    editor.click()
    expect(editor).to_be_focused()
    assert editor.evaluate("el => el.value") == ""
    birth = page.evaluate("performance.timeOrigin")
    revision = int(
        page.locator('meta[name="lf-revision"][data-lf-runtime]').get_attribute(
            "content"
        )
    )
    revised = REPLY_HOST_PAGE.replace(
        "with a signed-cookie fallback", "with a session-cookie fallback"
    )
    if installation == "fresh":
        revised = revised.replace(
            "</head>",
            '<script type="module">window.pageRevision = 2;</script></head>',
        )
    stamp_page(serve.page_dir, revised, "Revise the page beside its empty reply")
    wait_for_revision(page, revision + 1)
    assert (page.evaluate("performance.timeOrigin") != birth) == (
        installation == "fresh"
    )
    expect(editor).to_be_focused()
    assert editor.evaluate("el => el.value") == ""


pytestmark = pytest.mark.shifts_unsurveyed


def choose_comment_target(page, selector):
    """Choose one visible element through the user's target-hint route."""
    page.locator(selector).scroll_into_view_if_needed()
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).not_to_have_count(0)
    code = page.evaluate(
        """selector => {
          const top = document.querySelector(selector).getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-picker-hint')]
            .sort((a, b) => Math.abs(a.getBoundingClientRect().top - top)
                          - Math.abs(b.getBoundingClientRect().top - top))[0]
            .dataset.lfHintCode;
        }""",
        selector,
    )
    page.keyboard.type(code)
    expect(page.locator(".lf-fab-input")).to_be_focused()


def test_clicking_a_visible_reply_preserves_the_thread_reading(browser, serve):
    """Pointer entry owns the caret, rather than revealing the whole containing card."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    thread = page.locator(".lf-thread[open]").first
    field = thread.locator("leaf-text")
    place = page.evaluate(
        """() => {
          const list = document.querySelector('.lf-threads');
          list.scrollTop = 70;
          return list.scrollTop;
        }"""
    )
    assert place == 70
    field.click()
    expect(field).to_be_focused()
    assert page.locator(".lf-threads").evaluate("el => el.scrollTop") == place


def test_clicking_a_shadow_widget_input_keeps_its_focus_and_thread_reading(
    browser, serve
):
    """A message's public widget keeps its native input across the thread's pointer-up."""
    url = serve(LONG_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Review the patch.",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "revision": 1,
            "text": "Filter the files in this patch.",
            "markup": """<lf-diff id="reply-patch" data-height="151"><pre>
diff --git a/reading.py b/reading.py
--- a/reading.py
+++ b/reading.py
@@ -1,2 +1,2 @@
 def reading():
-    return "before"
+    return "after"
</pre></lf-diff>""",
        },
    )
    for index in range(16):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"Another thread {index}.",
            },
        )
    page = open_page(browser, url)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    field = page.locator(".lf-thread[open] lf-diff .lf-diff-search")
    expect(field).to_be_visible()
    page.locator(".lf-threads").evaluate("list => list.scrollTop = 70")
    scroll_settled(page, ".lf-threads")
    before_click = page.locator(".lf-threads").evaluate("list => list.scrollTop")
    assert before_click > 0
    assert field.evaluate(
        "field => field.getBoundingClientRect().top > "
        "field.getRootNode().host.closest('.lf-threads').getBoundingClientRect().top"
    ), "the shadow input must already be visible before the click"

    field.click()

    expect(field).to_be_focused()
    assert (
        page.locator(".lf-threads").evaluate("list => list.scrollTop") == before_click
    )


@pytest.mark.watch_shifts
def test_a_single_space_is_message_content_in_every_composer(browser, serve):
    """The shared field and both drawing-aware variants admit the smallest message,
    each box sending in turn on one page.

    Each box sends from the one press the shared field dresses, and that press paints
    nothing of its own: at rest the accent glyph is the whole of what a user sees, and
    the disc behind it is a clear 28px that takes the accent tint under the pointer,
    which is why it stays the same size as the target around it grows.
    """
    page = open_page(browser, serve(LONG_PAGE, comments=True))
    for box in ("reply", "general", "composer"):
        if box == "composer":
            select_words(page, "#p0")
            expect(page.locator(".lf-fab-input")).to_be_visible()
            page.keyboard.press("c")
            surface = page.locator(".lf-composer")
        elif box == "general":
            page_comment(page)
            surface = page.locator(".lf-general")
        else:
            page.locator(".lf-threads-toggle").click()
            panel_settled(page)
            surface = page.locator(".lf-threads > .lf-thread").first
            surface.locator(".lf-thread-summary").click()
        field = surface.locator("leaf-text")
        send = surface.locator(".lf-compose-submit")
        write(field, " ")
        expect(send).to_have_attribute("aria-disabled", "false")
        face = glyph_action_face(send)
        assert face["press"] == "rgba(0, 0, 0, 0)", (box, face)
        assert face["glyph"] == token_colour(page, "--accent"), (box, face)
        assert face["disc"] == "rgba(0, 0, 0, 0)", (box, face)
        assert face["discWidth"] == "28px", (box, face)
        send.hover()
        hovered = glyph_action_face(send)
        assert hovered["press"] == "rgba(0, 0, 0, 0)", (box, hovered)
        assert hovered["disc"] == token_colour(page, "--accent-tint"), (box, hovered)
        assert hovered["discWidth"] == "28px", (box, hovered)
        with sending(page, f"the {box} message"):
            send.click()

        message = [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] in {"comment", "reply"}
        ][-1]
        assert message["text"] == " ", box
        if box == "reply":
            page.locator(".lf-threads-toggle").click()
            panel_settled(page, open=False)


# A storage fault stands in an init script, because it has to run ahead of the
# runtime's own storage listener and at the window listeners run in the order they
# were added, capture or not. That is before the page can say which key its draft is
# stored under, so the script compares against `window.lfDraftKey`, which
# `name_the_draft` sets once the page has loaded and nothing has been typed.
DEAF_TO_DRAFT_NEWS = """addEventListener('storage', event => {
  if (event.key === window.lfDraftKey) event.stopImmediatePropagation();
}, true);"""


def name_the_draft(page, ctx):
    """Point this page's storage fault at the draft at `ctx`, by the store's key."""
    page.evaluate("key => { window.lfDraftKey = key; }", draft_key(page, ctx))


def cancel_draft(page, draft_id="draft-ops"):
    """Cancel stands beside Save throughout an engaged draft edit."""
    draft_control(page, "cancel", draft_id).click()


def test_completed_page_selection_opens_its_own_comment(browser, serve):
    """A real page selection opens Comment without focusing it or carrying earlier
    words, whether a mouse drag, a drag inside a bounded scroller, or the keyboard's
    select-all made it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Selection gestures",
                '<p id="earlier">Earlier subject.</p>'
                '<p id="later">A later passage keeps native selection.</p>'
                '<p id="later-box" style="height:72px;overflow:auto">'
                "A later boxed passage keeps native selection.<br>"
                + "Another line of evidence.<br>" * 40
                + "</p>",
            )
        ),
    )
    field = page.locator(".lf-fab-input")
    for gesture, later in (
        ("mouse", "#later"),
        ("mouse-in-scroller", "#later-box"),
        ("keyboard", "#later"),
    ):
        page.locator("#earlier").click(modifiers=["Alt"])
        write(field, "Words about the earlier subject")
        if gesture.startswith("mouse"):
            line = page.locator(later).evaluate("""p => {
                const range = document.createRange();
                range.selectNodeContents(p);
                return range.getClientRects()[0].toJSON();
            }""")
            y = line["y"] + line["height"] / 2
            hold_selection(page, (line["x"] + 2, y), (line["x"] + line["width"] - 2, y))
            page.mouse.up()
            if gesture == "mouse-in-scroller":
                # A bounded reading region takes native focus as the drag begins.
                expect(page.locator(later)).to_be_focused()
        else:
            page.locator(later).click()
            page.keyboard.press("ControlOrMeta+a")
        rendered(page)
        assert page.evaluate("() => getSelection().toString()"), gesture
        expect(field).to_be_visible()
        expect(field).not_to_be_focused()
        expect(field).to_have_js_property("value", "")
        page.keyboard.press("c")
        expect(field).to_be_focused()
        page.keyboard.press("Escape")
        page.locator("#earlier").click(modifiers=["Alt"])
        expect(field).to_have_js_property("value", "Words about the earlier subject")
        page.keyboard.press("Escape")


@pytest.mark.parametrize(
    "touch, words",
    [(False, "An unfinished earlier comment"), (True, "")],
    ids=["browser-command-unfinished", "touch-handles-empty"],
)
def test_observed_selection_offers_comment_without_replacing_the_editor(
    browser, serve, touch, words
):
    """Browser-owned selection offers an explicit action while an existing editor stays.

    Chromium's native SelectAll command supplies desktop selection without a keyup.
    Touch emulation has no OS handles; Selection.extend exercises their endpoint
    notification without inventing a page pointer gesture.
    """
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, has_touch=touch
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Observed selection",
                '<p id="earlier">Earlier subject.</p>'
                '<p id="later">A later passage keeps native selection.</p>',
            )
        ),
        context=context,
    )
    page.locator("#earlier").click(modifiers=["Alt"])
    field = page.locator(".lf-fab-input")
    write(field, words)
    field.evaluate("el => { window.heldSelectionEditor = el; }")
    action = page.get_by_role("button", name="Comment on selection", exact=True)

    def select_in_browser():
        field.evaluate("el => el.blur()")
        if touch:
            page.locator("#later").evaluate("""async p => {
            const changed = new Promise(resolve => document.addEventListener(
              'selectionchange', resolve, {once: true}));
            getSelection().setBaseAndExtent(p.firstChild, 2, p.firstChild, 7);
            getSelection().extend(p.firstChild, 15);
            await changed;
        }""")
        else:
            context.new_cdp_session(page).send(
                "Input.dispatchKeyEvent", {"type": "keyDown", "commands": ["SelectAll"]}
            )
        expect(action).to_be_visible()

    select_in_browser()
    selected = page.evaluate("() => getSelection().toString()")
    assert selected
    # A modifier's release observes the passage; it does not select it for Comment.
    page.keyboard.press("Shift")
    rendered(page)
    assert field.evaluate("el => el === window.heldSelectionEditor")
    expect(field).to_be_visible()
    expect(field).to_have_js_property("value", words)
    assert page.evaluate("() => getSelection().toString()") == selected

    # Returning to this editor retires the browser-owned selection and its offer.
    if touch:
        field.tap()
    else:
        field.click()
    rendered(page)
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    assert page.evaluate("() => getSelection().toString()") == ""
    expect(action).to_be_hidden()
    select_in_browser()

    # Both routes activate the same native banner control and its captured passage.
    if touch:
        action.tap()
    else:
        action.focus()
        page.keyboard.press("Enter")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "")
    assert pending_text(page) == selected.replace("\n", "")
    assert page.evaluate("() => getSelection().toString()") == ""
    page.keyboard.press("Escape")
    page.locator("#earlier").click(modifiers=["Alt"])
    expect(field).to_have_js_property("value", words)


def test_a_passages_comment_box_undoes_only_its_own_draft(browser, serve):
    """The comment box moves from passage to passage, and its undo history belongs to
    the draft it stands on: words typed and deleted on one passage are not what ⌘Z
    brings into the next one's draft, even when both drafts read the same."""
    page = open_page(browser, serve(LONG_PAGE))
    field = page.locator(".lf-fab-input")
    compose(page, "#p0")
    page.keyboard.type("x")
    page.keyboard.press("ArrowLeft")  # a caret move ends the typing's undo step
    page.keyboard.press("End")
    page.keyboard.press("Backspace")
    expect(field).to_have_js_property("value", "")
    compose(page, "#p1")
    page.keyboard.press("ControlOrMeta+z")
    page.keyboard.type("y")
    expect(field).to_have_js_property("value", "y")


def test_page_round_trip(browser, serve):
    """The loop the product is, driven through the real UI: select a passage and
    comment on it, drag a card to another column, rewrite a draft in place, then
    follow the next version and find the comment still anchored to its
    (relocated) passage and the draft still wearing the user's words. The
    final assertion is the event log — the trail Claude reads — down to the
    anchor's quote, the move's placement, and the edit's text."""
    page = open_page(browser, live_url(serve(JOURNEY_V1)))
    # The browser selects the exact passage; Comment explicitly enters its field.
    page.locator("#intro").evaluate("""p => {
        const range = document.createRange();
        range.selectNodeContents(p);
        getSelection().removeAllRanges();
        getSelection().addRange(range);
    }""")
    expect(
        page.get_by_role("button", name="Comment on selection", exact=True)
    ).to_be_visible()
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    page.wait_for_selector(".lf-composer", state="visible")
    write(page.locator(".lf-composer leaf-text"), "Is 0041 idempotent?")
    page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_selector(".lf-margin-thread")
    # The anchor pass painted the passage — a range in the highlight registry, not an
    # element, so there is no selector for it.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Put the new comment's card away before reaching for the board. A sent comment
    # leaves its thread standing in the page margin, and the board is a wide widget
    # whose columns run out into that same band, so the card lands over the column this
    # drag is aimed at and takes the pointer. A user sees the card and dismisses it;
    # a test that skipped the dismissal would be dragging under a sheet, which is a
    # scene about the margin rather than the seam below.
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()
    page.keyboard.press("Escape")  # from the sent card to its passage
    page.keyboard.press("Escape")  # off the passage, dismissing its card
    expect(page.locator(".lf-margin-thread")).to_be_hidden()
    # Drag the card between columns through the pointer path — the seam where
    # the vendored SortableJS meets the runtime, which is where drags break.
    grip = page.locator("#card-x .lf-grip").bounding_box()
    dest = page.locator("#col-done").bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        dest["x"] + dest["width"] / 2, dest["y"] + dest["height"] / 2, steps=15
    )
    page.mouse.up()
    page.wait_for_selector("#col-done #card-x")  # the drop reparented the card

    # Rewrite the draft through its own door: a press opens the text in place, Save
    # sends the whole new body. The text must have arrived without the source's
    # indentation.
    draft = page.locator("#draft-ops")
    assert draft.locator(".lf-draft-body").inner_text() == DRAFT_TEXT
    draft.locator(".lf-draft-body").dblclick()
    write(draft.locator("leaf-text"), DRAFT_EDITED)
    draft_control(page, "save", "draft-ops").click()
    expect(draft.locator(".lf-draft-body")).to_have_text(DRAFT_EDITED)

    # Every gesture above must be in the log before v2's note lands, or the trail below
    # would interleave. The page posted them, so the page is what says they are all in:
    # polling the file for one of them would be a second reading of the same trip, and a
    # narrower one — it can only ever ask after the send it happens to name.
    d = serve.page_dir
    round_trip(page)

    # Claude ships v2 with the passage moved; the page follows on its next poll.
    stamp_page(d, JOURNEY_V2, "moved")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    assert "/versions/" not in page.url
    # The anchor pass runs at render: a mark now means the quote was re-found in
    # its new position; no mark within the wait means the anchor lost it.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert not page.evaluate(
        "document.querySelector('.lf-thread .lf-quote').classList.contains('detached')"
    ), "the passage moved and the comment lost it"
    # v2's markup carries the original draft text — Claude hasn't honored the
    # edit — so the user's words must arrive by replay, not visibly revert.
    expect(draft.locator(".lf-draft-body")).to_have_text(DRAFT_EDITED)

    # The trail those gestures left, exactly — kinds, authorship (the server
    # stamps browser events `user`), the anchor, and the move's placement.
    events = events_model.read_events(d)
    assert [(e["kind"], e["author"], e["revision"]) for e in events] == [
        ("note", "agent", 1),
        ("comment", "user", 1),
        ("action", "user", 1),
        ("action", "user", 1),
        ("note", "agent", 2),
    ]
    # The board after the paragraph is module-rendered and therefore an opaque
    # passage cell. Context stops at that shared browser/file fence.
    assert events[1]["anchor"] == {
        "section": "intro",
        "quote": SENTENCE,
        "prefix": "Journey",
    }
    assert events[1]["text"] == "Is 0041 idempotent?"
    assert {k: events[2][k] for k in ("widget", "action", "detail")} == {
        "widget": "board",
        "action": "move",
        "detail": {"unit": "card-x", "value": "col-done", "rank": "i"},
    }
    assert {k: events[3][k] for k in ("widget", "action", "detail")} == {
        "widget": "draft-ops",
        "action": "edit",
        "detail": {"value": DRAFT_EDITED},
    }


@pytest.mark.parametrize("section", ["draft-ops", None])
def test_a_comment_inside_a_widget_stays_out_of_what_the_widget_reads(
    browser, serve, section
):
    """The note that tells a screen reader a block carries a comment is chrome, and chrome
    inside a widget's own content would be chrome in the user's text: lf-draft seeds the
    editor they type into from its body div, so words left in there would arrive in the
    leaf-text and post with the edit. The note stands in the chrome, and the block the
    passage sits in, or the element the anchor names, names it as its details. A
    reaction on the same words keeps the widget as its seat too: the passage's generated
    body is not the owner of the reaction's margin control."""
    url = serve(JOURNEY_V1, anchored=[(section, "Run the migration before deploying.")])
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "keep",
            "anchor": {
                **({"section": section} if section else {}),
                "quote": "Run the migration before deploying.",
            },
        },
    )
    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    page.wait_for_function("() => (CSS.highlights.get('lf-react')?.size ?? 0) > 0")
    expect(
        page.locator(
            '[data-lf-margin-for="draft-ops"] '
            '[data-lf-margin-entry-owner="standing-reactions"]'
            '[data-lf-margin-entry-key^="reaction:"]:visible'
        )
    ).to_have_count(1)
    expect_comment_notes(page, "#draft-ops", 1)
    # The thread's margin row stands at the same seat as its note: the widget, not the
    # paragraph its Markdown body renders.
    expect(page.locator("[data-lf-margin-for]")).to_have_attribute(
        "data-lf-margin-for", "draft-ops"
    )
    page.locator("#draft-ops .lf-draft-body").dblclick()
    assert (
        page.locator("#draft-ops leaf-text").evaluate("el => el.value") == DRAFT_TEXT
    ), "the user's editor opened on text the runtime had written into"


def test_double_clicking_a_draft_leaves_every_word_where_it_was(browser, serve):
    """Plain words retain their geometry and native double-click selection on edit.

    The frame's inset focus paint changes without reaching outside the reading box,
    and print keeps the saved body while dropping the shared editor."""
    page = open_page(browser, serve(JOURNEY_V1))
    metrics = """(sel) => {
      const el = document.querySelector('#draft-ops ' + sel), s = getComputedStyle(el);
      const b = el.getBoundingClientRect();
      return [b.x + parseFloat(s.paddingLeft) + parseFloat(s.borderLeftWidth),
              b.y + parseFloat(s.paddingTop) + parseFloat(s.borderTopWidth), b.width, b.height];
    }"""
    read = page.evaluate(metrics, ".lf-draft-body")
    host = page.locator("#draft-ops").bounding_box()
    # A 4px band above the box, and the box's own top-left corner. The band is where
    # the answer to "did the frame move" lives and no measurement of geometry can
    # reach it: an outset ring is paint, so every rect stayed exactly as asserted
    # below while the frame the user sees grew 2px on every side, corners
    # rounding wider to match. Bytes, not pixels — the same encoder over the same
    # content gives the same file, so identical files are identical paint.
    band = {
        "x": host["x"] - 4,
        "y": host["y"] - 4,
        "width": host["width"] + 8,
        "height": 4,
    }
    inside = {"x": host["x"], "y": host["y"], "width": 40, "height": 40}
    outside_before = page.screenshot(clip=band)
    inside_before = page.screenshot(clip=inside)

    # Aimed at where the browser actually drew the word, not at an offset from the
    # box's edge. A pixel count is a fact about one font: 60px into this line was
    # "migration" while the theme set drafts in 16px system-ui, and lands in "the"
    # now that it sets them in 17px Charter — so the test read as "the editor opens
    # on the wrong word" when nothing about the gesture had changed.
    spot = page.evaluate(
        """(word) => {
            const body = document.querySelector('#draft-ops .lf-draft-body');
            const node = document.createTreeWalker(body, NodeFilter.SHOW_TEXT).nextNode();
            const at = node.data.indexOf(word);
            const r = document.createRange();
            r.setStart(node, at); r.setEnd(node, at + word.length);
            const b = r.getBoundingClientRect();
            return [b.x + b.width / 2, b.y + b.height / 2];
        }""",
        "migration",
    )
    page.mouse.dblclick(*spot)
    editor = page.locator("#draft-ops leaf-text")
    expect(editor).to_be_focused()
    pencil = draft_control(page, "edit", "draft-ops")
    assert page.screenshot(clip=band) == outside_before, (
        "opening the editor painted outside the box the draft already occupied"
    )
    assert page.screenshot(clip=inside) != inside_before, (
        "the open editor is indistinguishable from the read view at the box's edge"
    )
    assert page.evaluate(metrics, "leaf-text") == read, (
        "the editor's text sits somewhere the read view's text did not"
    )
    assert page.locator("#draft-ops").bounding_box() == host, (
        "the draft changed shape under the pointer when the editor opened"
    )
    assert (
        page.evaluate(
            "() => getSelection().rangeCount > 0 && "
            "getSelection().containsNode(document.querySelector('#draft-ops .lf-draft-body'), true)"
        )
        is False
    ), "the gesture left the page's own words selected under the open editor"
    selected = page.evaluate(
        "() => { const t = document.querySelector('#draft-ops leaf-text');"
        "        return t.value.slice(t.selectionStart, t.selectionEnd); }"
    )
    assert selected == "migration", (
        f"the box opened on {selected!r} rather than the word clicked"
    )

    # Closing states both properties in reverse, and the focus half is a question
    # only because the ✎ is CSS-hidden for as long as the editor is there: #close
    # reaches for it the instant the editor goes, so a style that hadn't caught up
    # would drop a keyboard user back at the top of the page.
    page.keyboard.press("Escape")
    expect(pencil).to_be_focused()
    expect(pencil).to_have_attribute("aria-expanded", "false")
    assert page.locator("#draft-ops").bounding_box() == host, (
        "the draft came back from an edit a different shape than it went in"
    )

    # Reopened through the other door, because print is where the box has to be
    # gone and its words still there — and print emulation blurs the leaf-text it
    # hides, so an editor opened before this point is no longer one Escape closes.
    draft_control(page, "edit", "draft-ops").click()
    expect(page.locator("#draft-ops leaf-text")).to_be_visible()
    page.emulate_media(media="print")
    assert page.locator("#draft-ops").inner_text() == DRAFT_TEXT, (
        "the printed page lost the draft's words to a box paper hasn't got"
    )
    page.emulate_media(media="screen")


@pytest.mark.parametrize(
    "in_pane, formatted",
    [(False, True), (True, False)],
    ids=["document-markdown", "pane-plain"],
)
def test_opening_a_visible_line_in_a_long_draft_preserves_the_reading_position(
    browser, serve, in_pane, formatted
):
    """Editing a visible word keeps it there even when the draft exceeds the window."""
    words = (
        "The **release note** remains `editable`."
        if formatted
        else "The release note remains editable."
    )
    text = "\n".join(f"Line {i}: {words}" for i in range(60))
    draft = f'<lf-draft id="long-draft"><pre>{text}</pre></lf-draft>'
    body = (
        "<header><h1>Release notes</h1></header>"
        f'<lf-pane id="reading" label="Notes">{draft}</lf-pane>'
        if in_pane
        else f"<h1>Release notes</h1>{draft}<p>Following words.</p>"
    )
    page = open_page(
        browser,
        serve(
            leaf_page("Long draft", body, layout="workspace" if in_pane else "column")
        ),
    )
    resized(page, 800, 900)
    page.locator("#long-draft").evaluate(
        """el => {
          const box = el.closest('lf-pane') ? el : document.scrollingElement;
          box.scrollTop = 600;
        }"""
    )
    scroll_settled(page)
    point = page.locator("#long-draft .lf-draft-body").evaluate(
        """el => {
          const word = 'Line 30:', walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
          let node;
          while ((node = walker.nextNode()) && !node.data.includes(word)) {}
          const at = node.data.indexOf(word), range = document.createRange();
          range.setStart(node, at + 3); range.setEnd(node, at + 4);
          const b = range.getBoundingClientRect();
          return [b.x + b.width / 2, b.y + b.height / 2];
        }"""
    )
    assert 60 < point[1] < 850, point
    reading = """() => ({
      page: document.scrollingElement.scrollTop,
      draft: document.querySelector('#long-draft').scrollTop,
      top: document.querySelector('#long-draft').getBoundingClientRect().top
    })"""
    before = page.evaluate(reading)
    page.mouse.click(*point)
    expect(page.locator("#long-draft leaf-text")).to_be_focused()
    assert page.evaluate(reading) == before
    editor = page.locator("#long-draft leaf-text")
    offset = editor.evaluate("el => el.selectionStart")
    assert text.index("Line 30:") <= offset <= text.index("Line 30:") + 8
    expect(editor).to_have_js_property("value", text)


def test_a_draft_uses_shared_editing_and_saves_exact_markdown_source(browser, serve):
    """Formatted reading retains exact Markdown through caret placement and editing, at
    a phone's width, where the formatted words wrap most."""
    text = (
        "A **bold invitation**, `literal code`, and [a link](https://example.com). " * 3
    ).strip()
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Draft source",
                f'<h1>Draft source</h1><lf-draft id="source"><pre>{text}</pre></lf-draft>'
                '<lf-sample id="quoted"><lf-draft id="exhibit"><pre>Read-only source.</pre></lf-draft></lf-sample>',
            )
        ),
    )
    resized(page, 390, 844)
    draft = page.locator("#source")
    point = draft.locator(".lf-draft-body").evaluate("""body => {
      const node=body.querySelector('code').firstChild;
      const r=new Range();r.setStart(node,3);r.setEnd(node,4);
      const b=r.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2];
    }""")
    expect(draft.locator(".lf-draft-body strong")).to_have_count(3)
    expect(draft.locator(".lf-draft-body code")).to_have_count(3)
    expect(draft.locator(".lf-draft-body a[href='https://example.com']")).to_have_count(
        3
    )
    page.mouse.click(point[0], point[1])
    editor = draft.locator("leaf-text")
    expect(editor).to_be_focused()
    expect(editor).to_have_attribute("aria-label", "Edit source")
    caret = editor.evaluate("el=>el.selectionStart")
    at = text.index("literal code")
    assert at <= caret <= at + len("literal code")
    page.keyboard.insert_text("changed ")
    expect(editor).to_have_js_property(
        "value", text[:caret] + "changed " + text[caret:]
    )
    page.keyboard.press("ControlOrMeta+z")
    expect(editor).to_have_js_property("value", text)
    write(editor, "Discard **this**.")
    draft_control(page, "cancel", "source").click()
    expect(draft.locator(".lf-draft-body strong")).to_have_count(3)
    draft_control(page, "edit", "source").click()
    expect(editor).to_have_js_property("value", text)
    saved = "Keep **this** and `that` exactly.\nA second line."
    write(editor, saved)
    draft_control(page, "save", "source").click()
    round_trip(page)
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body strong")).to_have_text("this")
    expect(draft.locator(".lf-draft-body code")).to_have_text("that")
    expect(draft.locator(".lf-draft-body")).to_have_text(
        "Keep this and that exactly. A second line.", use_inner_text=True
    )
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert [event["detail"]["value"] for event in edits] == [saved]
    page.locator("#exhibit .lf-draft-body").click()
    expect(page.locator("#exhibit leaf-text")).to_have_count(0)
    expect(page.locator("#exhibit .lf-draft-body")).to_have_text("Read-only source.")


def test_a_rendered_continuation_click_edits_the_exact_source_position(browser, serve):
    """Parser-expanded indentation keeps the native pointer's source coordinate."""
    sources = ["- first\n\tcontinued **target**", "1. first\n\tcontinued **target**"]
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Continuation carets",
                "<h1>Continuation carets</h1>"
                + "".join(
                    f'<lf-draft id="continuation-{i}"><pre>{source}</pre></lf-draft>'
                    for i, source in enumerate(sources)
                ),
            )
        ),
    )
    for i, source in enumerate(sources):
        draft = page.locator(f"#continuation-{i}")
        point = draft.locator(".lf-draft-body strong").evaluate("""strong => {
          const node=strong.firstChild, range=new Range();
          range.setStart(node,2);range.setEnd(node,3);
          const box=range.getBoundingClientRect(),x=box.x+0.01,y=box.y+box.height/2;
          return {x,y,offset:document.caretPositionFromPoint(x,y).offset};
        }""")
        page.mouse.click(point["x"], point["y"])
        editor = draft.locator("leaf-text")
        expect(editor).to_be_focused()
        at = source.index("target") + point["offset"]
        expect(editor).to_have_js_property("selectionStart", at)
        page.keyboard.insert_text("here")
        expect(editor).to_have_js_property("value", source[:at] + "here" + source[at:])
        draft_control(page, "cancel", f"continuation-{i}").click()


def test_a_draft_in_an_ask_takes_no_digits_and_answers_from_its_controls(
    browser, serve
):
    """A draft lends its Ask no digits, so a digit typed while standing on the Ask
    or in the editor is not a command; the user Tabs to Edit and saves with
    Mod+Enter."""
    original = "Keep **this** source editable."
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Draft in an Ask",
                '<h1>Release note</h1><lf-ask id="note-decision">'
                "<h2>How should the note read?</h2>"
                f'<lf-draft id="note" needed><pre>{original}</pre></lf-draft></lf-ask>',
            )
        ),
    )
    question = page.locator("#note-decision")
    editor = page.locator("#note leaf-text")
    edit = draft_control(page, "edit", "note")

    page.keyboard.press("q")
    expect(question).to_be_focused()
    expect(edit).not_to_have_attribute("aria-keyshortcuts", re.compile(r"\d"))
    page.keyboard.press("1")
    rendered(page)
    expect(editor).to_have_count(0)
    page.keyboard.press("Tab")
    expect(edit).to_be_focused()
    page.keyboard.press("Enter")
    expect(editor).to_be_focused()
    write(editor, "Keep **these** digits: ")
    page.keyboard.type("12")
    saved = "Keep **these** digits: 12"
    expect(editor).to_have_js_property("value", saved)
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    expect(editor).to_have_count(0)
    expect(page.locator("#note .lf-draft-body")).to_have_text("Keep these digits: 12")
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert [event["detail"]["value"] for event in edits] == [saved]


def test_a_foreign_edit_waits_for_a_live_draft_and_replays_in_order(browser, serve):
    """Replay never replaces words while the user is typing them.

    Deferring one edit must also hold later edits for that draft: otherwise the
    later absolute value lands first and the deferred earlier value overwrites it
    when the box closes. An unrelated board move proves the poll saw the same
    batch while the editor was open, without making the test depend on time.
    Reconnecting the same editor restores its local deferral before semantic catchup.
    """
    page = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    editor = draft.locator("leaf-text")
    write(editor, "Local unsent words.")

    draft.evaluate(
        """node => {
          window.__lfEditingDraft = {
            node, parent: node.parentNode, next: node.nextSibling,
            editor: node.querySelector('leaf-text'),
          };
          node.remove();
        }"""
    )
    # The fixture deliberately removes the editor's subject. Consume that allowed
    # disappearance at the frame where the words watcher observes the removal.
    one_frame(page)
    consume_browser_errors(page, "typed words left the screen without a key or press")
    page.evaluate(
        """() => {
          const {node, parent, next} = window.__lfEditingDraft;
          parent.insertBefore(node, next);
        }"""
    )
    assert editor.evaluate("node => node === window.__lfEditingDraft.editor")
    editor.focus()

    d = serve.page_dir
    for text in ("Foreign first edit.", "Foreign committed words."):
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "draft-ops",
                "action": "edit",
                "detail": {"value": text},
            },
        )
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "board",
            "action": "move",
            "detail": {"unit": "card-x", "value": "col-done", "rank": "0i"},
        },
    )

    told(page)
    expect(page.locator("#col-done #card-x")).to_have_count(1)
    expect(editor).to_have_js_property("value", "Local unsent words.")
    expect(draft.locator(".lf-draft-history")).to_have_count(0)

    page.route("**/api/state*", refuse)
    page.keyboard.press("Escape")
    ticked(page)
    expect(draft.locator(".lf-draft-body")).to_have_text("Foreign committed words.")
    expect(draft.locator(".lf-draft-history > summary")).to_have_text(
        "Changes · 2 edits"
    )
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "3")


def test_a_draft_send_owns_the_editor_until_its_response(browser, serve):
    """A second gesture cannot overtake an earlier request or let that request clear
    newer unsent text. Hold the first POST in the browser: while it owns the draft,
    every edit door stays closed and the exact body remains recoverable, and the busy
    draft is readable content.

    A refused save is then an editable state, with Retry and Cancel at the same
    target."""
    page = open_page(browser, serve(JOURNEY_V1))
    page.evaluate(
        """() => {
          const actualFetch = window.fetch.bind(window);
          let held = true;
          window.fetch = (input, init) => {
            const event = String(input).endsWith('/api/event') && init?.body
              ? JSON.parse(init.body) : null;
            if (held && event?.kind === 'action' && event.action === 'edit') {
              return new Promise((resolve, reject) => {
                window.releaseDraftSend = () => {
                  held = false;
                  actualFetch(input, init).then(resolve, reject);
                };
              });
            }
            return actualFetch(input, init);
          };
        }"""
    )
    draft = page.locator("#draft-ops")
    sent = "The first save still owns this body."
    draft.locator(".lf-draft-body").dblclick()
    write(draft.locator("leaf-text"), sent)
    draft_control(page, "save", "draft-ops").click()
    expect(draft).to_have_attribute("aria-busy", "true")
    assert stored_draft_text(page, "edit:draft-ops") == sent
    expect(draft.locator(".lf-draft-body")).to_have_text(sent)
    expect(draft).to_have_css("opacity", "1")
    expect(draft).to_have_css("cursor", "progress")
    assert draft.evaluate("node => node.getAnimations().length") == 0

    expect(draft_control(page, "edit", "draft-ops")).to_be_disabled()
    # The projection owns a native disabled button, so a forced DOM click is refused
    # before the contributor's activation capability can run.
    draft_control(page, "edit", "draft-ops").evaluate("button => button.click()")
    expect(draft.locator("leaf-text")).to_have_count(0)

    page.evaluate("window.releaseDraftSend()")
    page.wait_for_function(
        """key => !document.getElementById('draft-ops').hasAttribute('aria-busy')
          && JSON.parse(localStorage.getItem(key))?.settled === true""",
        arg=draft_key(page, "edit:draft-ops"),
    )
    events = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["value"] for event in events] == [sent]
    expect(draft.locator(".lf-draft-body")).to_have_text(sent)

    draft_control(page, "edit", "draft-ops").click()
    editor = draft.locator("leaf-text")
    expect(editor).to_be_focused()
    write(editor, "Keep these unsent words.")
    page.route(
        "**/api/event",
        lambda route: route.fulfill(
            status=400,
            json={"ok": False, "final": True, "error": "refused before append"},
        ),
    )
    draft_control(page, "save", "draft-ops").click()
    item = draft.locator(".lf-draft-footer")
    expect(item.get_by_role("status")).to_have_text("Save failed. Your edit is kept.")
    expect(editor).to_have_js_property("value", "Keep these unsent words.")
    expect(item.get_by_role("button", name="Retry", exact=True)).to_be_visible()
    expect(item.get_by_role("button", name="Cancel", exact=True)).to_be_visible()

    write(editor, "Keep the revised unsent words.")
    expect(item.locator(".lf-draft-status")).to_be_empty()
    item.get_by_role("button", name="Save", exact=True).click()
    expect(item.get_by_role("status")).to_have_text("Save failed. Your edit is kept.")
    page.unroute("**/api/event")
    item.get_by_role("button", name="Retry", exact=True).click()
    round_trip(page)
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text(
        "Keep the revised unsent words."
    )
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert [event["detail"] for event in edits] == [
        {"value": sent},
        {"value": "Keep the revised unsent words."},
    ]
    consume_browser_errors(page, "400")


def test_one_shared_draft_edit_appends_one_action_across_tabs(browser, serve, one_user):
    """The widget's local busy flag is not the shared edit's ownership boundary."""
    url = serve(JOURNEY_V1)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first_draft = first.locator("#draft-ops")
    second_draft = second.locator("#draft-ops")
    first_draft.locator(".lf-draft-body").dblclick()
    second_draft.locator(".lf-draft-body").dblclick()
    text = "One absolute edit from the shared draft generation."
    write(first_draft.locator("leaf-text"), text)
    expect(second_draft.locator("leaf-text")).to_have_js_property("value", text)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    draft_control(first, "save", "draft-ops").click()
    holding(first, held, 1, "the first draft edit")
    draft_control(second, "save", "draft-ops").click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action" and event["action"] == "edit"
    ]
    assert [event["detail"]["value"] for event in edits] == [text]
    assert edits[0]["attempt"]
    assert _traffic(first).sends == _traffic(second).sends == 1
    expect(second_draft.locator("leaf-text")).to_have_count(0)
    assert stored_draft_settled(second, "edit:draft-ops")


def test_one_shared_added_option_has_one_action_payload_across_tabs(
    browser, serve, one_user
):
    """A draft attempt owns its actions' details as well as its visible words.

    The two views deliberately start from different projected selections. Both can
    submit the one shared add-option generation: its `add` is one event by attempt, and
    the pick behind it comes from the generation's recorded choice rather than from
    each tab's own selection, so the two tabs send one pick.
    """
    url = serve(ASK_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)

    # Model a tab whose latest projection has not reached its neighbour yet. The draft
    # is born here, so this selection is the state the generation records.
    first.locator("#job-mounts").evaluate("el => el.setAttribute('chosen', '')")
    text = "Use a heated camera sleeve"
    write(first.locator("#jobs > .lf-another leaf-text"), text)
    expect(second.locator("#jobs > .lf-another leaf-text")).to_have_js_property(
        "value", text
    )

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first.locator("#jobs > .lf-another").get_by_role(
        "button", name="Add and select option", exact=True
    ).click()
    holding(first, held, 1, "the first added option")

    second.locator("#jobs > .lf-another").get_by_role(
        "button", name="Add and select option", exact=True
    ).click()
    round_trip(second)
    held_detail = held[0].request.post_data_json["detail"]
    # The pick queues behind the held `add`, so the route comes off before the `add`
    # goes on and nothing sent after it is caught.
    first.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(first)
    # The forged selection is not the state's, so the `add` renders it away and the pick
    # that follows in the same task puts it back.
    consume_browser_errors(first, "unchanged write: chosen on lf-option#job-mounts")

    moves = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("kind") == "action" and event.get("widget") == "jobs"
    ]
    adds = [event["detail"] for event in moves if event["action"] == "add"]
    assert adds == [held_detail]
    picks = {
        tuple(event["detail"]["value"])
        for event in moves
        if event["action"] == "choose"
    }
    assert picks == {("job-mounts", held_detail["option"])}
    # Each tab sent the generation's `add` and its pick once.
    assert _traffic(first).sends == _traffic(second).sends == 2


def test_a_general_comment_appends_one_event_across_tabs(browser, serve, one_user):
    """Both tabs may POST the shared generation; its attempt appends it once."""
    url = serve(LONG_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    raw = "One general comment, however many tabs show its draft."
    write(page_comment(first), raw)
    expect(page_comment(second)).to_have_js_property("value", raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first.locator(".lf-general .lf-compose-submit").click()
    holding(first, held, 1, "the first general send")
    second.locator(".lf-general .lf-compose-submit").click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]
    assert roots[0]["attempt"]
    assert _traffic(first).sends == _traffic(second).sends == 1


def test_a_held_general_send_preserves_a_newer_exact_draft(browser, serve):
    """An earlier response settles only the general generation it posted."""
    page = open_page(browser, serve(LONG_PAGE))
    box = page_comment(page)
    old = "The general comment already in flight."
    newer = "  The newer general thought keeps its spaces.  "
    write(box, old)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator(".lf-general .lf-compose-submit").click()
    holding(page, held, 1, "the older general send")
    # The send put the card away; the newer thought is written in it opened again.
    write(page_comment(page), newer)

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(box).to_have_js_property("value", newer)
    assert stored_draft_text(page, "general") == newer
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old]


def test_a_refused_selection_comment_leaves_the_words_on_their_passage(
    held_events, serve
):
    """The composer goes down with the send, so a refusal has to put the words back in
    the store rather than in whatever box was on screen — the one they were typed in has
    gone with the thread they went to."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    words = "The selection comment the server will refuse."
    compose(page, "#p3", words)
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the selection comment")

    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator('leaf-text[name="reply"]:focus')).to_be_visible()
    page.keyboard.press("ArrowRight")  # caret movement is not a later composition
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    # The words went back to a box out of view, so the refusal says where they are.
    expect(page.locator(".lf-notice")).to_have_text(
        "Couldn't send — refused before append. Draft kept — g i resumes writing"
    )

    # Their passage still holds their draft, so opening it again finds the words.
    page.locator("h1").click()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(".lf-composer leaf-text")).to_be_focused()
    expect(page.locator(".lf-composer leaf-text")).to_have_js_property("value", words)
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == words
    ]
    consume_browser_errors(page, "400")


def test_a_refused_selection_comment_reopens_its_words_while_the_send_owns_intent(
    held_events, serve
):
    """A refusal that lands while the user is still where the send left them puts the
    words back in front of them, in the box on their passage, as the page comment card
    does. Left in the store alone, they read as lost: the thread the send drew goes
    away, and nothing on screen says the sentence still exists."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    words = "The selection comment the server will refuse."
    compose(page, "#p3", words)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the selection comment")
    expect(page.locator(".lf-fab-input")).not_to_be_visible()

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)
    # The box is back with the words, so the refusal names no address for them.
    expect(page.locator(".lf-notice")).to_have_text(
        "Couldn't send — refused before append"
    )
    consume_browser_errors(page, "400")


def test_a_refused_selection_comment_written_past_is_where_resume_writing_goes(
    held_events, serve
):
    """The user has gone on to write somewhere else when the refusal lands. Their
    refused words go back to the passage's box, which is out of view, so the notice says
    they are kept and Resume writing takes the user to them, rather than to the box they
    can already see."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    words = "The selection comment the server will refuse."
    compose(page, "#p3", words)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the selection comment")
    later = "A page comment written while the first was in flight."
    write(page_comment(page), later)

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(page.locator(".lf-notice")).to_have_text(
        "Couldn't send — refused before append. Draft kept — g i resumes writing"
    )
    expect(page.locator(".lf-fab-input")).not_to_be_visible()

    page.keyboard.press("Escape")
    expect(page.locator(".lf-page-comment-card")).not_to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)
    assert stored_draft_text(page, "general") == later
    consume_browser_errors(page, "400")


@pytest.mark.parametrize("reply_sent", [True, False], ids=["sent", "unsent"])
@pytest.mark.parametrize("edited", [False, True], ids=["as-sent", "edited"])
def test_a_reply_under_a_refused_parent_comes_back_with_it(
    held_events, serve, reply_sent, edited
):
    """A refusal takes down the thread a comment opened, and the box under it: a reply
    written there, sent behind the comment or not, keys by the comment's attempt, which
    the refusal withdraws and an edit of the comment replaces. The words go to the
    comment's own draft instead, so the notice says where they wait, Resume writing
    leads to that draft, and the thread its next send opens, edited or not, has the
    reply back in its box. A reply sent behind the comment never reaches the wire under
    the pending name only this page used."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    parent = "The parent the server will refuse."
    write(page_comment(page), parent)
    page.locator(".lf-general .lf-compose-submit").click()
    holding(page, held, 1, "the parent send")

    card = page.locator('.lf-thread[data-id^="pending:"]')
    expect(card).to_have_count(1)
    reply = "A reply written while the parent was in flight."
    write(card.locator("leaf-text").first, reply)
    if reply_sent:
        card.get_by_role("button", name="Send", exact=True).click()
    # The user goes back to the page comment box, so the parent's words return in view.
    box = page_comment(page)

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(box).to_have_js_property("value", parent)
    expect(page.locator(".lf-notice")).to_have_text(
        "Couldn't send — refused before append. "
        "Reply kept — it returns when its comment sends"
    )
    expect(card).to_have_count(0)
    assert not [
        route for route in held if "pending:" in (route.request.post_data or "")
    ], "a gesture reached the wire naming a thread the log never took"
    # The thread went with its parent, so the reply's words wait in the parent's draft.
    assert stored_draft_text(page, f"reply:{attempt}") is None
    assert (
        page.evaluate(
            "([read, ctx]) => read(ctx)?.held ?? null",
            [stored_draft(page), "general"],
        )
        == reply
    )

    # Resume writing leads to the comment, the one place that brings the reply back.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-page-comment-card")).to_be_hidden()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", parent)
    text = parent
    if edited:
        page.keyboard.press("ControlOrMeta+End")
        page.keyboard.type(" Edited.")
        text = parent + " Edited."

    page.locator(".lf-general .lf-compose-submit").click()
    holding(page, held, 1, "the parent sent again")
    assert (held[0].request.post_data_json["attempt"] == attempt) is not edited
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    sent = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == text
    )
    thread = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
    expect(thread.locator("leaf-text").first).to_have_js_property("value", reply)
    # An unsent reply's box goes down with the thread; the notice says where its words
    # went, which is what the guard's report is about.
    consume_browser_errors(
        page,
        "400",
        *(
            []
            if reply_sent
            else [f'typed words left the screen without a key or press: "{reply}"']
        ),
    )


def test_a_refused_comments_reply_travels_with_it_to_another_passage(
    held_events, serve
):
    """The reply a refusal hands back is part of the comment's draft, so whatever moves
    the draft moves the reply: carried with Alt-click to another passage and sent from
    there, the comment's new thread has the reply back in its box."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    parent = "The anchored parent the server will refuse."
    compose(page, "#p3", parent)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the anchored parent")
    card = page.locator('.lf-threads .lf-thread[data-id^="pending:"]')
    expect(card).to_have_count(1)
    reply = "A reply under the anchored parent."
    write(card.locator("leaf-text").first, reply)
    card.get_by_role("button", name="Send", exact=True).click()

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(page.locator(".lf-notice")).to_contain_text(
        "Reply kept — it returns when its comment sends"
    )

    page.locator("h1").click()
    page.keyboard.press("g")
    page.keyboard.press("i")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", parent)
    page.locator("#p5").scroll_into_view_if_needed()
    page.locator("#p5").click(modifiers=["Alt"])
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", parent)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the parent sent from its new passage")
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    sent = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == parent
    )
    assert sent["anchor"]["section"] == "p5"
    thread = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
    expect(thread.locator("leaf-text").first).to_have_js_property("value", reply)
    consume_browser_errors(page, "400")


def test_a_refused_comment_takes_its_message_back_and_returns_the_words(
    held_events, serve
):
    """A refusal leaves nothing standing and the words back where they were written.

    The user has moved on to the pending thread in Threads by the time the refusal
    lands, so the card's box does not take their keys back: the words wait in it, and
    focus falls from the withdrawn thread to the list it stood in."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    box = page_comment(page)
    words = "The comment the server will refuse."
    write(box, words)
    before = page.locator(".lf-threads > .lf-thread").count()
    page.locator(".lf-general .lf-compose-submit").click()
    holding(page, held, 1, "the general send")
    pending = page.locator('.lf-thread[data-id^="pending:"]')
    expect(pending).to_have_count(1)
    # The card is a native disclosure, so its title is the stop the user stands on.
    title = pending.locator(":scope > .lf-thread-summary")
    title.focus()
    expect(title).to_be_focused()

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(page.locator('.lf-thread[data-id^="pending:"]')).to_have_count(0)
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(before)
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(box).not_to_be_focused()
    expect(box).to_have_js_property("value", words)
    # The card the box stands in closed with the send, so the words are back out of
    # view, and the refusal names the address that opens it again.
    expect(page.locator(".lf-notice")).to_have_text(
        "Couldn't send — refused before append. Draft kept — g i resumes writing"
    )
    assert stored_draft_text(page, "general") == words
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == words
    ]
    consume_browser_errors(page, "400")


def test_every_message_send_says_so_to_a_user_listening(held_events, serve):
    """A send whose result the user cannot see still reaches them.

    The message standing in the thread is the whole acknowledgement for a user
    looking at it, which is why no box writes a success notice for it. But neither the
    seat nor the Threads list is a live region, so for a user listening to the page
    that send would pass in silence. `post` says it once, where a gesture is first known
    to be a message, which is what covers every box that sends one.
    """
    browser, held = held_events
    page = open_page(browser, serve(SEATED_QUESTION_PAGE))
    live = page.locator(".lf-live")
    seat = page.locator("#jobs > .lf-thread-seat > .lf-say")
    field = seat.locator("leaf-text")
    press = seat.get_by_role("button", name="Send", exact=True)
    write(field, "A remark whose arrival nothing else will say.")
    press.click()
    # Held: the gesture is the only thing that can have written the region, and the
    # words are said before the log has answered rather than because it did.
    holding(page, held, 1, "the send")
    expect(live).to_have_text("Message sent")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)


def test_a_first_answer_leaves_a_later_sends_words_masked(held_events, serve):
    """One box, two sends: answering the first must not hand back the second's words.

    A send empties the box it was written in and masks that generation, so this
    document stops showing words it is now showing in the thread. The answer lifts that
    mask — and lifting whichever mask happens to be standing, rather than the one this
    send put there, lifts a later send's: words the user is already watching as a
    pending reply go back on offer while that reply is still in flight. The outbox
    delivers in order, so the first answer always lands while the second send is
    unanswered. That makes the window ordinary rather than rare.
    """
    browser, held = held_events
    url = serve(SEATED_QUESTION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job comes first?",
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread")
    thread.locator(".lf-thread-summary").click()
    reply = thread.locator("leaf-text")
    send = thread.get_by_role("button", name="Send", exact=True)

    first = "The reply already on its way."
    write(reply, first)
    send.click()
    holding(page, held, 1, "the first reply send")
    expect(reply).to_have_js_property("value", "")

    second = "The reply the user is watching."
    write(reply, second)
    send.click()
    expect(reply).to_have_js_property("value", "")
    # Both stand, in the order they were written. A card gains messages by insertion,
    # and a receipt acknowledging an earlier one sits between them.
    expect(thread.locator(".lf-msg").last).to_contain_text(second)
    expect(thread.locator(".lf-msg").nth(-2)).to_contain_text(first)

    held.pop(0).continue_()
    holding(page, held, 1, "the second reply send, once the first is answered")

    # What a widget asks of a draft box, through the public helper surface. The boxes
    # alone would not say this: nothing repaints one when a mask is lifted, so the
    # offer stands unseen until some view of this thread is next built and reads it.
    standing = page.evaluate(
        """async (ctx) => {
          const api = await window.__lfRuntimeImport('/runtime/widget-api.js');
          return api.loadDraft(ctx);
        }""",
        f"reply:{root['id']}",
    )
    assert standing is None, "the second send's words were offered back while in flight"
    expect(reply).to_have_js_property("value", "")
    expect(page.locator("#jobs .lf-page-thread leaf-text")).to_have_js_property(
        "value", ""
    )

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    spoken = thread.locator(".lf-msg").all_inner_texts()
    assert [
        words for words in (first, second) if not any(words in s for s in spoken)
    ] == []


@pytest.mark.parametrize("same_thread", [False, True])
def test_a_held_reply_send_leaves_a_later_reply_box_focused(
    held_events, serve, same_thread
):
    """A later draft keeps its focus and remains visible when a reply arrives.

    The long sent message tests reflow above a draft in the same card; the distant
    card tests a user who has moved to another thread.
    """
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE, comments=8))
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads > .lf-thread")
    first_id = threads.nth(0).get_attribute("data-id")
    later_id = first_id if same_thread else threads.last.get_attribute("data-id")
    first = page.locator(f'.lf-thread[data-id="{first_id}"] leaf-text')
    later = page.locator(f'.lf-thread[data-id="{later_id}"] leaf-text')
    page.locator(f'.lf-thread[data-id="{first_id}"] .lf-thread-summary').click()
    write(first, "\n\n".join(["The first reply is in flight."] * 15))

    page.locator(f'.lf-thread[data-id="{first_id}"]').get_by_role(
        "button", name="Send", exact=True
    ).click()
    holding(page, held, 1, "the first reply send")

    if not same_thread:
        page.locator(f'.lf-thread[data-id="{later_id}"] .lf-thread-summary').click()
    later.click()
    newer = "The later reply keeps the user here.\n" * (14 if same_thread else 1)
    write(later, newer)
    expect(later).to_be_focused()
    in_threads_scrollport(page, f'.lf-thread[data-id="{later_id}"] leaf-text')

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(
        page.locator(f'.lf-thread[data-id="{first_id}"] .lf-msg').last
    ).to_contain_text("The first reply is in flight.")
    expect(later).to_be_focused()
    expect(later).to_have_js_property("value", newer)
    in_threads_scrollport(page, f'.lf-thread[data-id="{later_id}"] leaf-text')


@pytest.mark.parametrize("continue_inline", [False, True])
def test_a_held_reply_send_leaves_the_panel_closed(held_events, serve, continue_inline):
    """Closing Threads during delivery is later than sending the reply."""
    browser, held = held_events
    url = serve(SEATED_QUESTION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job comes first?",
        },
    )
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    toggle = page.locator(".lf-threads-toggle")
    toggle.click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread")
    thread.locator(".lf-thread-summary").click()
    reply = thread.locator("leaf-text")
    write(reply, "Send this while I return to reading.")
    thread.get_by_role("button", name="Send", exact=True).click()
    holding(page, held, 1, "the reply send")

    toggle.click()
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    expect(toggle).to_be_focused()
    inline = page.locator(
        f'#jobs .lf-page-thread[data-thread="{root["id"]}"] leaf-text'
    )
    newer = "Continue this reply beside the question."
    if continue_inline:
        write(inline, newer)
        inline.evaluate("box => box.setSelectionRange(9, 9)")
        expect(reply).to_have_js_property("value", newer)
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(reply).to_have_js_property("value", newer if continue_inline else "")
    expect(thread.locator(".lf-msg").last).to_contain_text(
        "Send this while I return to reading."
    )
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    if continue_inline:
        expect(inline).to_be_focused()
        expect(inline).to_have_js_property("value", newer)
        assert inline.evaluate("box => box.selectionStart") == 9
    else:
        expect(toggle).to_be_focused()


def test_a_held_reply_send_preserves_a_later_scroll(held_events, serve):
    """A wheel can move the reading place while the user stands on the thread the
    reply was sent in; its delivery moves neither."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE, comments=40))
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads > .lf-thread")
    first = threads.first
    later = threads.last
    first.locator(".lf-thread-summary").click()
    reply = first.locator("leaf-text")
    write(reply, "A reply whose delivery is slow.")
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the reply send")

    bounds = page.locator(".lf-threads").bounding_box()
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
    )
    expect(later).not_to_be_in_viewport()
    page.mouse.wheel(0, 3500)
    expect(later).to_be_in_viewport()
    expect(first.locator(".lf-thread-summary")).to_be_focused()
    before = later.evaluate("node => node.getBoundingClientRect().top")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(reply).to_have_js_property("value", "")
    expect(first.locator(".lf-msg").last).to_contain_text(
        "A reply whose delivery is slow."
    )
    expect(later).to_be_in_viewport()
    assert later.evaluate("node => node.getBoundingClientRect().top") == pytest.approx(
        before, abs=1
    )
    expect(first.locator(".lf-thread-summary")).to_be_focused()


def test_a_held_comment_send_leaves_a_later_reply_box_focused(browser, serve):
    """Opening a reply while a new comment is in flight is a later gesture. The
    comment still appears, but its arrival must not move focus into its new thread."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    select_words(page, "#p3")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "The earlier comment in flight.")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # Another thread than the one in flight: that one's card is in this list too now,
    # standing for the comment while the log answers for it.
    later_id = page.locator(
        '.lf-threads > .lf-thread:not([data-id^="pending:"])'
    ).first.get_attribute("data-id")
    later = page.locator(f'.lf-thread[data-id="{later_id}"] leaf-text')
    page.locator(f'.lf-thread[data-id="{later_id}"] .lf-thread-summary').click()
    write(later, "The later reply keeps the user here.")
    later.evaluate("ta => ta.setSelectionRange(9, 9)")
    expect(later).to_be_focused()

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(3)
    expect(later).to_be_focused()
    expect(later).to_have_js_property("value", "The later reply keeps the user here.")
    assert later.evaluate("ta => ta.selectionStart") == 9


def test_newer_filter_wins_over_send_waiting_for_presentation(browser, serve):
    """A delayed Send cannot widen a newer filter or navigate its reader away."""
    page = open_page(browser, serve(NOTED_PAGE, comments=1))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    search = page.get_by_role("searchbox", name="Find in threads")
    search.fill("Comment 0")
    select_words(page, "#p1")
    page.locator(".lf-fab-input").click()
    write(
        page.locator(".lf-composer leaf-text"), "Earlier Send waiting for presentation."
    )
    hold_pending_thread_presentation(page)
    page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_function("() => window.commentPresentationHeld === true")
    search.fill("Keep this newer search")
    expect(search).to_be_focused()
    page.evaluate("releaseCommentPresentation()")
    round_trip(page)
    page.wait_for_function("() => document.body.hasAttribute('data-lf-presented')")
    expect(search).to_have_value("Keep this newer search")
    expect(search).to_be_focused()

    assert any(
        event.get("text") == "Earlier Send waiting for presentation."
        for event in events_model.read_events(serve.page_dir)
    )


@pytest.mark.parametrize("later_selection", [False, True])
def test_a_comment_hidden_by_narrowing_is_revealed_in_the_open_panel(
    browser, serve, later_selection
):
    """A new comment widens the panel's filter without taking a later selection."""
    page = open_page(browser, serve(NOTED_PAGE, comments=1))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.get_by_role("searchbox", name="Find in threads").fill("Comment 0")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)

    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(
        page.locator(".lf-composer leaf-text"),
        "This comment starts outside the filter.",
    )
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the filtered comment send")
    if later_selection:
        select_words(page, "#p2")
        expect(page.locator(".lf-fab-input")).to_be_visible()
        assert pending_text(page) == "A short second passage."

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    sent = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("text") == "This comment starts outside the filter."
    )
    expect(page.locator(".lf-thread-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value("")
    thread = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
    expect(thread).to_contain_text(sent["text"])
    if later_selection:
        assert pending_text(page) == "A short second passage."
        expect(page.locator(".lf-fab-input")).to_be_visible()
        expect(page.locator(".lf-fab-input")).not_to_be_focused()
        assert composer_quote(page)["text"].strip("“”") == "A short second passage."
    else:
        expect(thread.locator(":scope > .lf-thread-summary")).to_be_focused()


def test_an_untouched_and_an_emptied_reply_follow_live_revisions(browser, serve):
    """Emptying a reply keeps its editing session while unrelated revisions arrive."""
    page = open_page(browser, live_url(serve(NOTED_PAGE)))
    resized(page, 1440, 900)
    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "Follow this discussion.")
    # The comment's own send in the wire before the log names it. Without that the read
    # below answers with the note the page opened on, and the reply this test is about is
    # looked for under an id no thread wears.
    with sending(page, "the comment the reply follows"):
        page.keyboard.press("ControlOrMeta+Enter")

    sent = events_model.read_events(serve.page_dir)[-1]
    thread = page.locator(
        f'.lf-margin-thread .lf-page-thread[data-thread="{sent["id"]}"]'
    )
    reply = thread.locator("leaf-text")
    expect(thread).to_be_focused()
    thread.get_by_role("textbox", name="Reply", exact=True).click()
    expect(reply).to_be_focused()

    d = serve.page_dir
    v2 = NOTED_PAGE.replace(
        "A short second passage.", "A revised short second passage."
    )
    stamp_page(d, v2, "v2")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")

    # The untouched reply remains disposable UI rather than becoming a draft merely
    # because the authored page advanced around it.
    expect(reply).to_be_visible()
    write(reply, "A thought I changed my mind about.")
    write(reply, "")
    # A thread's reply draft is keyed by the name the log's answer does not change —
    # the attempt the user's own comment opened it with (thread/model.js).
    assert stored_draft_text(page, f"reply:{sent['attempt']}") == ""
    v3 = v2.replace(
        "A revised short second passage.", "A twice-revised short second passage."
    )
    stamp_page(d, v3, "v3")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v3")
    expect(reply).to_have_js_property("value", "")
    expect(reply).to_be_focused()


def test_a_held_comment_send_leaves_the_passage_picked_out_behind_it(
    held_events, serve
):
    """A comment's send must not take a newer passage selection with its focus handoff.

    The newer selection remains native and keeps its response field available while the
    earlier send becomes a thread behind it.

    Held rather than raced: the window is one request's flight, and a machine quick
    enough closes it before the next gesture. A loaded CI runner is not, and it said so
    as a 💬 that never came up for the passage picked out after a send.

    The next passage is the one above the first, because the sent comment's card stands
    under its passage, over whatever follows it. The card is placed and revealed some
    frames after the send, so a passage below was reachable only on a machine quick
    enough to press it before the card arrived."""
    browser, held = held_events
    page = open_page(browser, serve(NOTED_PAGE))
    select_words(page, "#p2")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "The first remark.")

    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")
    # Every machine reaches the next gesture with the card standing, as a user would.
    expect(page.locator(".lf-margin-preview[data-lf-thread-placement]")).to_be_visible()

    # The user picks out their next passage while the first send is still in the wire.
    passage = " ".join(page.locator("#p1").inner_text().split())
    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", "")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-thread")).to_have_count(1)

    # The send landed behind them and left the passage picked out. Read as the user's
    # own next gesture rather than as the button's rendering: the button is a state that
    # only a fresh decision repaints, so it stands wherever the last one left it — while
    # the key that comments on a selection reads the live one, and answers the general
    # box where there is none.
    assert pending_text(page) == passage, (
        "the send's landing lost the passage the user had picked out"
    )
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == passage


def test_a_held_comment_send_leaves_a_later_keyboard_comment_open(held_events, serve):
    """The Comment opened with `s` is later than a comment already in flight."""
    browser, held = held_events
    page = open_page(browser, serve(NOTED_PAGE))
    compose(page, "#p1", "The first remark.")

    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")

    # Leave the sending field, then use the keyboard Comment path on p2.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).not_to_have_count(0)
    target_code = page.evaluate(
        """() => {
          const top = document.querySelector('#p2').getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-picker-hint')]
            .sort((a, b) => Math.abs(a.getBoundingClientRect().top - top)
                          - Math.abs(b.getBoundingClientRect().top - top))[0]
            .dataset.lfHintCode;
        }"""
    )
    page.keyboard.type(target_code)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#p2")).to_have_class(
        re.compile(r"\blf-mark-el\b.*\blf-pending\b")
    )
    expect(page.locator(".lf-fab-bar")).to_have_attribute(
        "aria-label", re.compile(r"^Respond to paragraph")
    )

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator(".lf-thread")).to_have_count(1)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#p2")).to_have_class(
        re.compile(r"\blf-mark-el\b.*\blf-pending\b")
    )
    expect(page.locator(".lf-fab-bar")).to_have_attribute(
        "aria-label", re.compile(r"^Respond to paragraph")
    )
    assert composer_quote(page)["text"].endswith("A short second passage.")


def test_an_unsent_comment_stays_with_its_passage_when_another_is_selected(
    browser, serve
):
    """Opening fields is automatic, so selecting a new passage is not re-anchoring.

    Each passage keeps its own durable draft: the newly selected passage starts empty,
    and returning to the original passage restores the words written about it."""
    page = open_page(browser, serve(NOTED_PAGE))
    field = page.locator(".lf-fab-input")
    original = "These words belong to the first passage."

    select_words(page, "#p1")
    expect(field).to_be_visible()
    expect(field).not_to_be_focused()
    write(field, original)

    select_words(page, "#p2")
    expect(field).to_have_js_property("value", "")
    expect(field).not_to_be_focused()
    assert (
        page.evaluate(
            """prefix => Object.keys(localStorage)
          .filter(key => key.startsWith(prefix)).length""",
            draft_key(page, "composer:"),
        )
        == 1
    )

    select_words(page, "#p1")
    expect(field).to_have_js_property("value", original)
    expect(field).not_to_be_focused()


def test_failed_settlement_keeps_the_base_for_a_chained_nondurable_edit(
    browser, serve, one_user
):
    """A failed tombstone does not make the next local edit descend from thin air."""
    url = serve(LONG_PAGE)
    shared = open_page(browser, url, context=one_user)
    local = open_page(browser, url, context=one_user)
    predecessor = "The durable predecessor that this local branch replaces."
    first = "The first nondurable comment on that branch."
    second = "The chained nondurable comment keeps the same base."
    write(page_comment(shared), predecessor)
    expect(page_comment(local)).to_have_js_property("value", predecessor)
    local.evaluate(
        """([draft, first, second]) => {
          const set = Storage.prototype.setItem;
          let secondFailed = false;
          window.lfBranchAttempt = null;
          Storage.prototype.setItem = function (key, value) {
            if (key === draft) {
              const record = JSON.parse(value);
              if (record.text === first) {
                window.lfBranchAttempt = record.attempt;
                throw new DOMException('full', 'QuotaExceededError');
              }
              if (record.settled && record.attempt === window.lfBranchAttempt)
                throw new DOMException('full', 'QuotaExceededError');
              if (record.text === second && !secondFailed) {
                secondFailed = true;
                throw new DOMException('full', 'QuotaExceededError');
              }
            }
            return set.call(this, key, value);
          };
        }""",
        [draft_key(local, "general"), first, second],
    )

    write(page_comment(local), first)
    local.locator(".lf-general .lf-compose-submit").click()
    round_trip(local)
    expect(local.locator(".lf-general leaf-text")).to_have_js_property("value", "")
    write(page_comment(local), second)
    expect(local.locator(".lf-general .lf-compose-submit")).to_have_attribute(
        "aria-disabled", "false"
    )
    local.locator(".lf-general .lf-compose-submit").click()
    _until(local, lambda traffic: traffic.sends == 2, "sent the chained generation")
    round_trip(local)

    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [first, second]
    assert len({event["attempt"] for event in comments}) == 2
    # The tombstone is written where the send reads its own response, one step behind the
    # response itself: `round_trip` watches the browser's trip, and the page settles the
    # generation in the continuation after it — so the log holds the send before the store
    # holds its settlement. Read the store on the fact the page states, the way the tabs
    # below do; a plain read is the same assertion made a step early, and a loaded runner
    # lands in that step, which is what CI read here as an unsettled chain.
    until_draft_settled(local, "general")


def test_a_stale_question_first_message_cannot_append_across_tabs(
    browser, serve, one_user
):
    """A stale visible generation refreshes the shared tombstone before POST.

    The second tab's storage repaint is then deliberately suppressed. Its text box
    remains stale after the first send stored its tombstone, so a second real press
    proves that readable absence is settlement rather than permission to trust the
    old in-memory value.
    """
    url = serve(SEATED_QUESTION_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(
        browser,
        url,
        context=one_user,
        init_script="""addEventListener('storage', event => {
          if (event.key !== window.lfDraftKey) return;
          try {
            if (JSON.parse(event.newValue)?.settled)
              event.stopImmediatePropagation();
          } catch {}
        }, true);""",
    )
    name_the_draft(second, "say:jobs")
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "  Keep one exact first answer.  "
    write(first_say.locator("leaf-text"), raw)
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)
    # The init-script capture listener beats the runtime's listener for settlement,
    # leaving the old value on screen after the other tab stores its tombstone.
    cut = CutOff().hold(second)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first_say.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the first answer")

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    until_draft_settled(first, "say:jobs")
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)
    assert stored_draft_settled(second, "say:jobs")
    second_send = second_say.get_by_role("button", name="Send", exact=True)
    expect(second_send).to_have_attribute("aria-disabled", "false")
    second_send.click()
    expect(second_say.locator("leaf-text")).to_have_js_property("value", "")
    cut.restore()

    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [(event["anchor"], event["text"]) for event in roots] == [
        ({"section": "jobs"}, raw)
    ]
    assert _traffic(first).sends + _traffic(second).sends == 1


def test_a_question_reply_appends_one_event_across_tabs(browser, serve, one_user):
    """Both inline views may POST the shared reply; its attempt appends it once."""
    url = serve(SEATED_QUESTION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job should come first?",
        },
    )
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    selector = f'#jobs > .lf-thread-seat > .lf-page-thread[data-thread="{root["id"]}"]'
    first_thread = first.locator(selector)
    second_thread = second.locator(selector)
    raw = "  The camera, then the mounting work.  "
    write(first_thread.locator("leaf-text"), raw)
    expect(second_thread.locator("leaf-text")).to_have_js_property("value", raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first_thread.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the first reply")
    second_thread.get_by_role("button", name="Send", exact=True).click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert [(event["parent"], event["text"]) for event in replies] == [
        (root["id"], raw)
    ]
    assert _traffic(first).sends == _traffic(second).sends == 1


def test_a_held_thread_send_cannot_clear_a_newer_raw_draft(browser, serve, one_user):
    """Settlement compares raw words, so an older POST cannot erase a later edit."""
    url = serve(SEATED_QUESTION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "What should the order be?",
        },
    )
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first.locator(".lf-threads-toggle").click()
    panel_settled(first)
    inline = first.locator(
        f'#jobs .lf-page-thread[data-thread="{root["id"]}"] leaf-text'
    )
    panel = first.locator(f'.lf-thread[data-id="{root["id"]}"]')
    second_inline = second.locator(
        f'#jobs .lf-page-thread[data-thread="{root["id"]}"] leaf-text'
    )
    sent_raw = "  Send this part first.  "
    newer_raw = "  A later thought stays raw.  "
    write(inline, sent_raw)
    expect(panel.locator("leaf-text")).to_have_js_property("value", sent_raw)
    expect(second_inline).to_have_js_property("value", sent_raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    panel.locator(".lf-thread-summary").click()
    panel.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the older reply")
    write(second_inline, newer_raw)
    expect(inline).to_have_js_property("value", newer_raw)
    expect(panel.locator("leaf-text")).to_have_js_property("value", newer_raw)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    expect(inline).to_have_js_property("value", newer_raw)
    expect(panel.locator("leaf-text")).to_have_js_property("value", newer_raw)
    expect(second_inline).to_have_js_property("value", newer_raw)
    # This root was appended by the agent, so it carries no attempt and its reply draft
    # keys by the id, which for such a thread never changes either.
    assert stored_draft_text(first, f"reply:{root['id']}") == newer_raw
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert [event["text"] for event in replies] == [sent_raw]


@pytest.mark.parametrize("newer", [None, "A newer thought must survive."])
def test_a_late_refusal_cannot_restore_an_attempt_another_tab_settled(
    browser, serve, one_user, newer
):
    """A final answer belongs to one execution; the accepted log owns the draft."""
    url = serve(SEATED_QUESTION_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "The shared generation one tab will accept."
    write(first_say.locator("leaf-text"), raw)
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)

    held_event = []
    held_state = []
    first.route("**/api/event", lambda route: held_event.append(route))
    first.route("**/api/state*", lambda route: held_state.append(route))
    try:
        first_say.get_by_role("button", name="Send", exact=True).click()
        holding(first, held_event, 1, "the first tab's answer")
        attempt = held_event[0].request.post_data_json["attempt"]

        second_say.get_by_role("button", name="Send", exact=True).click()
        round_trip(second)
        expect(first_say.locator("leaf-text")).to_have_js_property("value", "")
        until_draft_settled(first, "say:jobs")
        holding(first, held_state, 1, "the accepted attempt's state read")
        if newer is not None:
            write(first_say.locator("leaf-text"), newer)

        with first.expect_response(
            lambda response: "/api/event" in response.url
        ) as refused:
            held_event.pop(0).fulfill(
                status=400,
                json={
                    "ok": False,
                    "final": True,
                    "attempt": attempt,
                    "error": "the earlier execution was refused",
                },
            )
        expect(first.locator(".lf-notice")).to_contain_text("Couldn't send")
        expected_error = f"400 {refused.value.url}"
        first_errors = first.lf_errors
        first_errors.remove(expected_error)
        expect(first_say.locator("leaf-text")).to_have_js_property("value", newer or "")

        held_state.pop(0).continue_()
        first.unroute("**/api/state*")
        round_trip(first)
        expect(first_say.locator("leaf-text")).to_have_js_property("value", newer or "")
    finally:
        for route in held_event + held_state:
            refuse(route)
        first.unroute_all(behavior="wait")


def test_a_question_can_send_when_draft_storage_refuses_writes(browser, serve):
    """Persistence failure costs recovery, not the live box's Send action."""
    page = open_page(
        browser,
        serve(SEATED_QUESTION_PAGE),
        init_script="""Storage.prototype.setItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
    say = page.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "  Send even though this draft cannot persist.  "
    write(say.locator("leaf-text"), raw)
    say.get_by_role("button", name="Send", exact=True).click()
    _until(page, lambda t: t.sends == 1, "sent the live unpersisted answer")
    round_trip(page)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]


def test_a_closed_sender_cannot_append_its_accepted_attempt_twice(
    browser, serve, one_user
):
    """The log returns the accepted attempt when its first sender cannot settle it.

    Both tabs are held stale, and each refusal states one half of that sentence. The
    wrapper below closes the send path — the POST lands, the runtime never hears the
    answer — and the poll is the other way the same tab settles a draft
    (settleAcceptedDrafts), so a sender left polling can still tombstone the shared
    generation out from under the replacement. It did: within a poll of the server
    taking the answer, first's own next poll read the attempt back out of the log and
    settled it, second's box emptied, and the send this test is about had nothing left
    to send — sends=0, the failure landing either on `sendDraft` refusing a settled
    record or on Playwright refusing a Send the box had already disabled, depending on
    which side of the click the storage event fell. The race was one poll interval
    against Playwright's own click, which is a gap only a loaded machine loses.

    Second's refusal is the older half and states the same fact from its own side: the
    replacement must not learn the attempt is in the log before it sends, or it would
    correctly decline to. Both go through `held_stale` rather than a live `page.route`,
    which reaches no poll already in the wire."""
    url = serve(SEATED_QUESTION_PAGE)
    first = open_page(browser, url, context=held_stale(one_user))
    second_held = held_stale(one_user)
    second = open_page(browser, url, context=second_held)
    raw = "One answer survives its sender closing."
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    write(first_say.locator("leaf-text"), raw)
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)
    first.evaluate(
        """() => {
          const actualFetch = window.fetch.bind(window);
          window.fetch = (input, init) => {
            const sent = actualFetch(input, init);
            if (!String(input).endsWith('/api/event')) return sent;
            return sent.then(() => {
              window.lfAcceptedAttempt = true;
              return new Promise(() => {});
            });
          };
        }"""
    )
    first_say.get_by_role("button", name="Send", exact=True).click()
    _until(first, lambda t: t.sends == 1, "sent the first answer to the server")
    first.wait_for_function("() => window.lfAcceptedAttempt === true")
    second_say.get_by_role("button", name="Send", exact=True).click()
    _until(second, lambda t: t.acked == 1, "received the accepted attempt")

    first.close()
    second_held.restore()
    told(second)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert len(roots) == 1
    assert roots[0]["text"] == raw
    assert roots[0]["attempt"]


def test_an_older_settlement_cannot_erase_a_newer_failed_write(
    browser, serve, one_user
):
    """A nondurable local generation outranks storage news about its predecessor."""
    url = serve(SEATED_QUESTION_PAGE)
    other = open_page(browser, url, context=one_user)
    old = "The older persisted answer."
    other_say = other.locator("#jobs > .lf-thread-seat > .lf-say")
    write(other_say.locator("leaf-text"), old)

    local = open_page(
        browser,
        url,
        context=one_user,
        init_script="""Storage.prototype.setItem = function () {
          throw new DOMException('full', 'QuotaExceededError');
        };""",
    )
    local_say = local.locator("#jobs > .lf-thread-seat > .lf-say")
    expect(local_say.locator("leaf-text")).to_have_js_property("value", old)
    newer = "The newer local answer whose write failed."
    write(local_say.locator("leaf-text"), "A first nondurable edit on the same branch.")
    write(local_say.locator("leaf-text"), newer)
    expect(other_say.locator("leaf-text")).to_have_js_property("value", old)

    other_say.get_by_role("button", name="Send", exact=True).click()
    round_trip(other)
    until_draft_settled(other, "say:jobs")
    expect(local_say.locator("leaf-text")).to_have_js_property("value", newer)

    local_say.get_by_role("button", name="Send", exact=True).click()
    _until(local, lambda t: t.sends == 1, "sent the nondurable newer answer")
    round_trip(local)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old, newer]
    assert len({event["attempt"] for event in roots}) == 2


def test_an_accepted_nondurable_branch_cannot_tombstone_a_newer_shared_generation(
    browser, serve, one_user
):
    """A held older send reconciles its base before writing settlement."""
    url = serve(SEATED_QUESTION_PAGE)
    older = open_page(
        browser,
        url,
        context=one_user,
        init_script="""(() => {
          const set = Storage.prototype.setItem;
          let refuse = true;
          Storage.prototype.setItem = function (key, value) {
            if (refuse && key === window.lfDraftKey) {
              refuse = false;
              throw new DOMException('full', 'QuotaExceededError');
            }
            return set.call(this, key, value);
          };
        })();"""
        + DEAF_TO_DRAFT_NEWS,
    )
    name_the_draft(older, "say:jobs")
    newer_tab = open_page(browser, url, context=one_user)
    older_say = older.locator("#jobs > .lf-thread-seat > .lf-say")
    newer_say = newer_tab.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The older nondurable answer already in flight."
    newer = "The newer durable answer survives the older response."
    write(older_say.locator("leaf-text"), old)

    held = []
    older.route("**/api/event", lambda route: held.append(route))
    older_say.get_by_role("button", name="Send", exact=True).click()
    holding(older, held, 1, "the nondurable send")
    write(newer_say.locator("leaf-text"), newer)
    assert stored_draft_text(newer_tab, "say:jobs") == newer
    newer_tab.close()

    held[0].continue_()
    older.unroute("**/api/event")
    round_trip(older)
    restored = older.locator("#jobs > .lf-thread-seat > .lf-say leaf-text")
    expect(restored).to_have_js_property("value", newer)
    assert stored_draft_text(older, "say:jobs") == newer
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old]


def test_a_nondurable_branch_yields_to_unrelated_live_storage_news(
    browser, serve, one_user
):
    """Only news from a branch's base may be replaced by that local branch."""
    url = serve(SEATED_QUESTION_PAGE)
    local = open_page(
        browser,
        url,
        context=one_user,
        init_script="""(() => {
          const set = Storage.prototype.setItem;
          let refuse = true;
          Storage.prototype.setItem = function (key, value) {
            if (refuse && key === window.lfDraftKey) {
              refuse = false;
              throw new DOMException('full', 'QuotaExceededError');
            }
            return set.call(this, key, value);
          };
          window.lfDraftNews = 0;
          addEventListener('storage', event => {
            if (event.key === window.lfDraftKey) window.lfDraftNews += 1;
          }, true);
        })();""",
    )
    name_the_draft(local, "say:jobs")
    shared = open_page(browser, url, context=one_user)
    local_say = local.locator("#jobs > .lf-thread-seat > .lf-say")
    shared_say = shared.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The local write failed before shared storage changed."
    newer = "The later durable generation owns the user now."
    write(local_say.locator("leaf-text"), old)
    write(shared_say.locator("leaf-text"), newer)
    local.wait_for_function("() => window.lfDraftNews > 0")

    expect(local_say.locator("leaf-text")).to_have_js_property("value", newer)
    expect(shared_say.locator("leaf-text")).to_have_js_property("value", newer)
    assert stored_draft_text(local, "say:jobs") == newer


def test_a_delayed_storage_event_cannot_send_a_stale_durable_generation(
    browser, serve, one_user
):
    """Send refreshes shared storage instead of trusting a stale durable cache."""
    url = serve(SEATED_QUESTION_PAGE)
    stale = open_page(
        browser, url, context=held_stale(one_user), init_script=DEAF_TO_DRAFT_NEWS
    )
    name_the_draft(stale, "say:jobs")
    current = open_page(browser, url, context=one_user)
    stale_say = stale.locator("#jobs > .lf-thread-seat > .lf-say")
    current_say = current.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The stale tab's older generation."
    newer = "The newer shared generation."
    write(stale_say.locator("leaf-text"), old)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", old)
    write(current_say.locator("leaf-text"), newer)
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", old)
    assert stored_draft_text(stale, "say:jobs") == newer

    stale_say.get_by_role("button", name="Send", exact=True).click()
    assert _traffic(stale).sends == 0
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", newer)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", newer)
    assert [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ] == []


def test_a_stale_cancel_cannot_settle_a_newer_durable_generation(
    browser, serve, one_user
):
    """Cancel refreshes ownership before writing the shared tombstone."""
    url = serve(JOURNEY_V1)
    stale = open_page(
        browser, url, context=held_stale(one_user), init_script=DEAF_TO_DRAFT_NEWS
    )
    name_the_draft(stale, "edit:draft-ops")
    current = open_page(browser, url, context=one_user)
    stale_draft = stale.locator("#draft-ops")
    current_draft = current.locator("#draft-ops")
    stale_draft.locator(".lf-draft-body").dblclick()
    current_draft.locator(".lf-draft-body").dblclick()
    old = "The older edit visible in the stale tab."
    newer = "The newer edit now owned by shared storage."
    write(stale_draft.locator("leaf-text"), old)
    expect(current_draft.locator("leaf-text")).to_have_js_property("value", old)
    write(current_draft.locator("leaf-text"), newer)
    expect(stale_draft.locator("leaf-text")).to_have_js_property("value", old)
    assert stored_draft_text(stale, "edit:draft-ops") == newer

    cancel_draft(stale)
    expect(current_draft.locator("leaf-text")).to_have_js_property("value", newer)
    assert stored_draft_text(current, "edit:draft-ops") == newer
    stale_draft.locator(".lf-draft-body").dblclick()
    expect(stale_draft.locator("leaf-text")).to_have_js_property("value", newer)


def test_poll_settlement_cannot_tombstone_a_newer_durable_generation(
    browser, serve, one_user
):
    """Log reconciliation settles only the generation still shared by storage."""
    url = serve(SEATED_QUESTION_PAGE)
    # The hold costs the most here, where the poll released at the end is the subject
    # rather than an interruption: an earlier poll reconciling this tab onto the newer
    # generation leaves settlement nothing older to be tempted by, so the assertions
    # below would pass while asking nothing rather than fail.
    stale_held = held_stale(one_user)
    stale = open_page(browser, url, context=stale_held, init_script=DEAF_TO_DRAFT_NEWS)
    name_the_draft(stale, "say:jobs")
    current = open_page(browser, url, context=one_user)
    stale_say = stale.locator("#jobs > .lf-thread-seat > .lf-say")
    current_say = current.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The accepted generation cached by the stale tab."
    newer = "The newer generation shared before settlement arrived."
    write(stale_say.locator("leaf-text"), old)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", old)
    old_attempt = stale.evaluate(
        "key => JSON.parse(localStorage.getItem(key)).attempt",
        draft_key(stale, "say:jobs"),
    )
    write(current_say.locator("leaf-text"), newer)
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", old)

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": old,
            "attempt": old_attempt,
        },
    )
    # Settlement reconciles before it claims, so this poll adopts the newer generation
    # and leaves it standing. `held_stale`'s refusal is lifted here rather than earlier,
    # with the older attempt in the log and the older generation still cached, which is
    # the only arrangement that asks anything.
    accepted_words = (
        f'typed words left the screen without a key or press: "{old}" in '
        + stale_say.locator("leaf-text").evaluate("field => window.lfPlace(field)")
    )
    stale_held.restore()
    told(stale)
    # The fixture blocked the real storage gesture, then explicitly accepted its
    # old generation. Polling must retire those old words in favour of the newer one.
    stale.evaluate("lfWordsJudged()")
    reported_browser_errors(stale, accepted_words)
    assert stored_draft_text(current, "say:jobs") == newer
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", newer)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", newer)


def test_a_read_failure_cannot_make_a_successfully_written_draft_unsendable(
    browser, serve
):
    """The document cache owns its generation even when getItem later refuses it."""
    page = open_page(
        browser,
        serve(SEATED_QUESTION_PAGE),
        init_script="""Storage.prototype.getItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
    raw = "A live value remains sendable when storage reads fail."
    say = page.locator("#jobs > .lf-thread-seat > .lf-say")
    write(say.locator("leaf-text"), raw)
    say.get_by_role("button", name="Send", exact=True).click()
    _until(page, lambda t: t.sends == 1, "sent the cached draft")
    round_trip(page)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]


def test_a_remove_failure_cannot_resurrect_an_accepted_draft(browser, serve, one_user):
    """Settlement is a record and a log fact; draft cleanup never calls removeItem."""
    url = serve(SEATED_QUESTION_PAGE)
    first = open_page(
        browser,
        url,
        context=one_user,
        init_script="""Storage.prototype.removeItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
    raw = "A sent draft must not return."
    say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    write(say.locator("leaf-text"), raw)
    say.get_by_role("button", name="Send", exact=True).click()
    round_trip(first)
    until_draft_settled(first, "say:jobs")

    again = open_page(browser, url, context=one_user)
    # The composer is still standing — a seat that can hold keeps it — so the claim is
    # about what it opens with: a settled draft is words the next tab must not be handed.
    expect(
        again.locator("#jobs > .lf-thread-seat > .lf-say leaf-text")
    ).to_have_js_property("value", "")
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]


def test_an_intentional_later_identical_reply_gets_a_fresh_attempt(browser, serve):
    """Identity follows the edit generation, never content or a time window."""
    url = serve(SEATED_QUESTION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Repeat the confirmation if it remains true.",
        },
    )
    page = open_page(browser, url)
    thread = page.locator(f'#jobs .lf-page-thread[data-thread="{root["id"]}"]')
    text = "Still true."
    for _ in range(2):
        write(thread.locator("leaf-text"), text)
        thread.get_by_role("button", name="Send", exact=True).click()
        round_trip(page)
        expect(thread.locator("leaf-text")).to_have_js_property("value", "")

    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert [event["text"] for event in replies] == [text, text]
    assert len({event["attempt"] for event in replies}) == 2


def test_an_unsent_draft_outlives_the_tab_it_was_typed_in(browser, serve, one_user):
    """The one gesture the tab-local store lost a draft to, and it is the ordinary one:
    every round's reply hands the URL over again, so a page's tabs accumulate and the
    one holding a half-written sentence is as likely to be shut as any other."""
    url = serve(LONG_PAGE)
    page = open_page(browser, url, context=one_user)
    typed = "Half a thought, and then the tab went."
    write(page_comment(page), typed)
    page.close()

    again = open_page(browser, url, context=one_user)
    expect(page_comment(again)).to_have_js_property("value", typed)


def test_a_draft_the_chrome_stands_down_says_so_and_keeps_an_address(browser, serve):
    """A press on the banner takes the composer off screen and keeps the words, and for
    a long time that was the whole of it: the bar went, the mark went, no notice and no
    dialog said anything, and the only way back was returning to that version and
    reselecting that exact passage. Words a user cannot find again are words they have
    lost, whatever localStorage still holds.

    So the moment says what became of them and names the address that answers — and the
    address is offered only while there is a draft standing to go to, which is the half
    that keeps the sentence honest."""
    page = open_page(browser, serve(LONG_PAGE))
    kept = "Half a sentence, and then the banner."

    # Nothing written, nothing to return to: the sequence does not offer the destination.
    page.keyboard.press("g")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("Threads panel")
    draft_route = page.locator('.lf-shortcut[data-lf-command-ids~="writing.resume"]')
    expect(draft_route).to_have_count(0)
    page.keyboard.press("Escape")

    compose(page, "#p3", kept)
    assert pending_text(page), "the open box left its own passage unmarked"

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert pending_text(page) == "", "a box off screen left its passage marked"
    notice = page.locator(".lf-notice")
    expect(notice).to_have_class(re.compile(r"\bshow\b"))
    assert notice.inner_text() == "Draft kept — g i resumes writing"

    page.keyboard.press("g")
    shortcut_bar_text(page)
    # The one-row line can trim this destination while leaving it in the register.
    expect(draft_route).to_have_count(1)
    page.keyboard.press("i")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", kept)
    assert pending_text(page), "the box came back on nothing"


def test_picture_paste_belongs_to_the_composer_not_the_shared_text_field(
    browser, serve
):
    """A direct editor pastes text; a composer takes pictures before text insertion."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Paste ownership",
                '<h1>Paste ownership</h1><p id="passage">Comment on this passage.</p>'
                '<lf-draft id="text-only"><pre>Keep WORD tail</pre></lf-draft>',
            )
        ),
    )
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    pixels = base64.b64encode(
        (example_media() / "051bee487bfb5d13.png").read_bytes()
    ).decode()
    page.evaluate(
        """async encoded => {
      window.clipboardBeforePasteTest = await navigator.clipboard.read();
      const bytes=Uint8Array.from(atob(encoded), char=>char.charCodeAt(0));
      window.pasteTestPicture=new Blob([bytes], {type:'image/png'});
    }""",
        pixels,
    )

    def paste(box, text, picture):
        box.focus()
        box.evaluate("el=>el.setSelectionRange(5,9)")
        page.evaluate(
            """async ([text,picture]) => {
          const payload={};
          if(text!==null)payload['text/plain']=new Blob([text],{type:'text/plain'});
          if(picture)payload['image/png']=window.pasteTestPicture;
          await navigator.clipboard.write([new ClipboardItem(payload)]);
        }""",
            [text, picture],
        )
        page.keyboard.press("ControlOrMeta+v")

    try:
        draft_control(page, "edit", "text-only").click()
        editor = page.locator("#text-only leaf-text")
        for text, picture, expected in [
            ("Pasted words", False, "Keep Pasted words tail"),
            ("Pasted words", True, "Keep Pasted words tail"),
            (None, True, "Keep  tail"),
        ]:
            write(editor, "Keep WORD tail")
            paste(editor, text, picture)
            expect(editor).to_have_js_property("value", expected)
        draft_control(page, "cancel", "text-only").click()

        compose(page, "#passage")
        composer = page.locator(".lf-fab-input")
        write(composer, "Keep WORD tail")
        with page.expect_response(lambda response: response.url.endswith("/api/media")):
            paste(composer, "Pasted words", True)
        expect(page.locator(".lf-composer-media img")).to_have_count(1)
        expect(composer).to_have_js_property("value", "Keep WORD tail")
        # Editing another surface chooses it; attachment removal is an edit that
        # chooses this composer again even though focusing it alone did not.
        page.keyboard.press("Escape")
        draft_control(page, "edit", "text-only").click()
        write(editor, "A later document edit")
        page.keyboard.press("Escape")
        compose(page, "#passage")
        page.get_by_role("button", name="Remove attached image 1", exact=True).click()
        expect(page.locator(".lf-composer-media img")).to_have_count(0)
        page.locator("h1").click()
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(composer).to_be_focused()
        expect(composer).to_have_js_property("value", "Keep WORD tail")
    finally:
        page.evaluate("""async () => {
          const previous=window.clipboardBeforePasteTest;
          if(previous.length)await navigator.clipboard.write(previous);
          else await navigator.clipboard.writeText('');
        }""")


@pytest.mark.parametrize("leave", [False, True])
def test_image_upload_completion_preserves_the_readers_focus_and_scroll(
    browser, serve, leave
):
    """Finishing a paste updates the draft without repeating the user's entry gesture."""
    held = []
    controlled = primed(
        browser,
        lambda page: page.route("**/api/media", lambda route: held.append(route)),
    )
    page = open_page(controlled, serve(LONG_PAGE))
    compose(page, "#p3")
    box = page.locator(".lf-fab-input")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    box.evaluate(
        """(box, encoded) => {
          const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
          const transfer = new DataTransfer();
          transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
          box.dispatchEvent(new ClipboardEvent('paste', {
            bubbles: true, cancelable: true, clipboardData: transfer,
          }));
        }""",
        base64.b64encode(pixels).decode(),
    )
    holding(page, held, 1, "the pasted image")
    expect(box).to_have_attribute("aria-busy", "true")
    expect(box).to_be_focused()
    if leave:
        page.keyboard.press("Tab")
        expect(box).not_to_be_focused()
        page.mouse.move(100, 500)
        page.mouse.wheel(0, 1000)
        page.wait_for_function("scrollY > 800")
        scroll_settled(page)
    before = page.evaluate("scrollY")
    page.evaluate("window.uploadFocus = document.activeElement")
    held.pop().continue_()
    expect(box).not_to_have_attribute("aria-busy", "true")
    expect(page.locator(".lf-composer-media img")).to_have_count(1)
    assert page.evaluate("scrollY") == before
    assert page.evaluate("document.activeElement === window.uploadFocus")


def test_a_picture_still_uploading_stays_out_of_the_next_passages_draft(browser, serve):
    """The comment box moves to another passage while a pasted picture uploads. The
    picture was the first passage's, so it does not land in the second one's draft, and
    the user is told it was not added rather than finding it somewhere they did not put
    it."""
    held = []
    controlled = primed(
        browser,
        lambda page: page.route("**/api/media", lambda route: held.append(route)),
    )
    page = open_page(controlled, serve(LONG_PAGE))
    compose(page, "#p3")
    box = page.locator(".lf-fab-input")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    box.evaluate(
        """(box, encoded) => {
          const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
          const transfer = new DataTransfer();
          transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
          box.dispatchEvent(new ClipboardEvent('paste', {
            bubbles: true, cancelable: true, clipboardData: transfer,
          }));
        }""",
        base64.b64encode(pixels).decode(),
    )
    holding(page, held, 1, "the pasted image")
    compose(page, "#p1")
    held.pop().continue_()
    expect(page.locator(".lf-notice")).to_contain_text("Image not added")
    expect(box).not_to_have_attribute("aria-busy", "true")
    expect(page.locator(".lf-composer-media img")).to_have_count(0)


def test_a_pasted_image_is_a_whole_draft_and_leaves_with_the_send_that_took_it(
    browser, serve
):
    """An image and no words is a draft, and the text box is the one place it does not
    show: the box keeps the Markdown and the shelf shows the thumbnail. So a reading
    that asks the text box whether anything is in here answers "empty" about a box the
    user can see holds a picture, and the two directions fail in opposite ways — the
    kept notice never appears for a picture put away, and it appears for a picture that
    has just been sent, over a box with nothing left in it.

    Both directions here, and the box the user opens next, because a shelf that
    outlived its send is an image that rides into the next passage's draft."""
    page = open_page(browser, serve(LONG_PAGE))
    image_markdown = "![Attached image](/media/051bee487bfb5d13.png)"
    compose(page, "#p3")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.locator(".lf-fab-input").evaluate(
            """(box, encoded) => {
              const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
              const transfer = new DataTransfer();
              transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
              box.dispatchEvent(new ClipboardEvent('paste', {
                bubbles: true,
                cancelable: true,
                clipboardData: transfer,
              }));
            }""",
            base64.b64encode(pixels).decode(),
        )
    shelf = page.locator(".lf-composer .lf-composer-media")
    expect(shelf.locator("img")).to_be_visible()

    # Put away: the picture is words enough to keep, and to be told about.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-composer")).to_be_hidden()
    notice = page.locator(".lf-notice")
    assert notice.inner_text() == "Draft kept — g i resumes writing"
    page.keyboard.press("g")
    shortcut_bar_text(page)
    expect(
        page.locator('.lf-shortcut[data-lf-command-ids~="writing.resume"]')
    ).to_have_count(1)
    page.keyboard.press("i")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", "")
    expect(shelf.locator("img")).to_be_visible()

    # Sent: the box is empty because the send emptied it, and says nothing about drafts.
    # Every word the status line says through the send, not the one left standing at the
    # end of it: a wrong sentence four seconds long is one the user reads.
    page.evaluate("""() => {
      const el = document.querySelector('.lf-notice');
      window.__said = [];
      new MutationObserver(() => window.__said.push(el.textContent)).observe(el, {
        childList: true,
        characterData: true,
        subtree: true,
      });
    }""")
    with sending(page, "the image-only comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert events_model.read_events(serve.page_dir)[-1]["text"] == image_markdown
    assert page.evaluate("window.__said") == []

    # And the next passage's box opens on nothing, shelf included.
    typed = "A second comment, and no image with it."
    compose(page, "#p5", typed)
    expect(shelf).to_be_hidden()
    with sending(page, "the second comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    assert events_model.read_events(serve.page_dir)[-1]["text"] == typed


def test_a_held_selection_comment_preserves_a_newer_exact_draft(held_events, serve):
    """A selection send owns one composer generation, not the passage.

    The send takes its own words with it — they stand in the thread it drew before the
    log has answered — and the composer opened again on that passage holds a generation
    of its own, which the older answer must not settle."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    old = "The selected passage needs this first comment."
    newer = "  A newer selection comment remains in the composer.  "
    compose(page, "#p3", old)
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the selection comment")
    expect(page.locator("[data-attempt]").first).to_contain_text(old)

    compose(page, "#p3", newer)
    box = page.locator(".lf-composer leaf-text")
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(box).to_have_js_property("value", newer)
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [old]
    assert comments[0]["attempt"]


def _draft_attachment_boxes(field, passage):
    """Read both moving boxes in one layout instant during native smooth travel.

    Separate driver calls can straddle scroll frames and invent relative movement.
    """
    return field.evaluate(
        """(node, selector) => [
          node.getBoundingClientRect().toJSON(),
          document.querySelector(selector).getBoundingClientRect().toJSON(),
        ]""",
        passage,
    )


def test_comment_follows_a_new_standing_instead_of_an_earlier_draft(browser, serve):
    """The earlier draft keeps its subject while a later keyboard landing names
    the next comment. Resume recovers the editor that followed its earlier passage."""
    source = LONG_PAGE.replace(
        "<p id='p40'>", '<p id="p40"><a id="later-link" href="#p41">Later item</a> '
    )
    page = open_page(browser, serve(source))
    words = "Carry these unfinished words to the item I am at now."
    choose_comment_target(page, "#p3")
    write(page.locator(".lf-fab-input"), words)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    rendered(page)
    earlier = page.locator(".lf-fab-input")
    earlier.evaluate("node => {window.earlierEditor = node;}")
    before_field, before_target = _draft_attachment_boxes(earlier, "#p3")
    page.keyboard.press("Shift+Tab")
    page.locator("#later-link").scroll_into_view_if_needed()
    go_to_address(page, "Link", "later-link")
    expect(page.locator("#p3")).not_to_be_in_viewport()
    expect(earlier).not_to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_attribute("aria-label", re.compile("Paragraph 3"))
    after_field, after_target = _draft_attachment_boxes(earlier, "#p3")
    for axis in ("x", "y"):
        assert after_field[axis] - before_field[axis] == pytest.approx(
            after_target[axis] - before_target[axis], abs=2
        )

    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(earlier).to_be_focused()
    expect(earlier).to_be_in_viewport()
    expect(page.locator("#p3")).to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_js_property("selectionStart", 1)
    expect(earlier).to_have_js_property("selectionEnd", 1)
    assert earlier.evaluate("node => node === window.earlierEditor")
    page.keyboard.press("Shift+Tab")
    page.locator("#later-link").scroll_into_view_if_needed()
    go_to_address(page, "Link", "later-link")
    expect(page.locator("#p41")).to_be_focused()
    expect(earlier).not_to_be_in_viewport()

    page.keyboard.press("c")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    expect(field).to_have_attribute("aria-label", re.compile("Paragraph 41"))
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    expect(field).to_have_attribute("aria-label", re.compile("Paragraph 41"))
    expect(field).to_have_js_property("selectionStart", 1)
    with sending(page, "comment"):
        page.keyboard.press("Enter")
    sent = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [(event["text"], event["anchor"]) for event in sent] == [
        (words, {"section": "p41"})
    ]


@pytest.mark.parametrize("existing_reply", ["", "This thread already holds a reply."])
def test_comment_follows_a_thread_standing_instead_of_an_earlier_draft(
    browser, serve, existing_reply
):
    """A chrome thread is a destination; an earlier draft follows its own passage.

    Resume returns its words and caret before Comment answers the standing thread.
    """
    page = open_page(browser, serve(LONG_PAGE, anchored=[("p41", "Paragraph 41.")]))
    thread = page.locator(".lf-margin-preview .lf-page-thread")
    if existing_reply:
        page.keyboard.press("t")
        page.keyboard.press("c")
        write(thread.locator("leaf-text"), existing_reply)
        page.keyboard.press("Escape")
    words = "These words belong to my earlier unfinished comment."
    choose_comment_target(page, "#p3")
    write(page.locator(".lf-fab-input"), words)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    rendered(page)
    earlier = page.locator(".lf-fab-input")
    earlier.evaluate("node => {window.earlierEditor = node;}")
    before_field, before_target = _draft_attachment_boxes(earlier, "#p3")
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator("#p3")).not_to_be_in_viewport()
    expect(earlier).not_to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_attribute("aria-label", re.compile("Paragraph 3"))
    after_field, after_target = _draft_attachment_boxes(earlier, "#p3")
    for axis in ("x", "y"):
        assert after_field[axis] - before_field[axis] == pytest.approx(
            after_target[axis] - before_target[axis], abs=2
        )

    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(earlier).to_be_focused()
    expect(earlier).to_be_in_viewport()
    expect(page.locator("#p3")).to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_js_property("selectionStart", 1)
    expect(earlier).to_have_js_property("selectionEnd", 1)
    assert earlier.evaluate("node => node === window.earlierEditor")
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator("#p3")).not_to_be_in_viewport()
    expect(earlier).not_to_be_in_viewport()
    page.keyboard.press("c")
    reply = thread.locator("leaf-text")
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", existing_reply or words)
    if existing_reply:
        page.keyboard.press("Escape")
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(page.locator(".lf-fab-input")).to_be_focused()
        expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)
    else:
        page.keyboard.press("Escape")
        page.keyboard.press("g")
        page.keyboard.press("i")
        reply = page.locator("leaf-text[name=reply]:focus")
        expect(reply).to_be_focused()
        expect(reply).to_have_js_property("value", words)
        expect(reply).to_have_js_property("selectionStart", 1)
        with sending(page, "carried reply"):
            page.keyboard.press("Enter")
        replies = [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "reply"
        ]
        assert [event["text"] for event in replies] == [words]


@pytest.mark.parametrize(
    "surface, answer", [("panel", "refused"), ("margin", "accepted")]
)
def test_reply_admission_finishes_or_restores_its_native_session(
    browser, serve, one_user, surface, answer
):
    """A provisional send keeps the editor owed a refusal; acceptance finishes editing.

    Refusal returns words to the agent-resolved thread and retries the same attempt.
    After acceptance, another tab's words remain saved without activating this editor.
    """
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url, context=one_user)
    if surface == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        card = page.locator(f'.lf-thread[data-id="{root}"]')
        card.locator(".lf-thread-summary").focus()
    else:
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
        page.keyboard.press("c")
    field = card.locator("leaf-text")
    words = "This reply still belongs to the resolved thread."
    write(field, words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    expect(field).to_be_focused()
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the provisional reply")
    attempt = held[0].request.post_data_json["attempt"]
    expect(field).to_have_js_property("value", "")
    expect(card).to_have_attribute("data-resolved", "false")
    if answer == "accepted":
        held.pop().continue_()
    else:
        held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    page.unroute("**/api/event")
    round_trip(page)
    rendered(page)
    if answer == "refused":
        expect(card).to_be_visible()
        expect(card).to_have_attribute("data-resolved", "true")
        expect(field).to_be_visible()
        expect(field).to_have_js_property("value", words)
        assert stored_draft_text(page, "reply:" + root) == words
        with sending(page, "the same reply after refusal"):
            field.focus()
            page.keyboard.press("ControlOrMeta+Enter")
        reply = events_model.read_events(serve.page_dir)[-1]
        assert (reply["kind"], reply["parent"], reply["text"], reply["attempt"]) == (
            "reply",
            root,
            words,
            attempt,
        )
        return
    expect(field).to_have_js_property("value", "")
    second = open_page(browser, url, context=one_user)
    if second.locator(".lf-threads-toggle").get_attribute("aria-expanded") != "true":
        second.locator(".lf-threads-toggle").click()
    panel_settled(second)
    other = second.locator(f'.lf-thread[data-id="{root}"]')
    other.locator(".lf-thread-summary").focus()
    next_words = "A saved reply written in the other tab."
    write(other.locator("leaf-text"), next_words)
    expect(field).to_have_js_property("value", next_words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    rendered(page)
    if surface == "panel":
        # The open card holds the resolution behind its notice until the user asks.
        card.get_by_role("button", name="Resolved", exact=True).click()
    expect(field).to_be_hidden()
    assert stored_draft_text(page, "reply:" + root) == next_words


@pytest.mark.parametrize(
    "surface, resolution",
    [("panel", "user"), ("margin", "active-agent"), ("panel", "inactive-agent")],
)
def test_reply_editing_and_saved_words_have_separate_resolution_lifetimes(
    browser, serve, surface, resolution
):
    """Only an external settlement interrupting active editing retains the editor.

    Deliberate Resolve and reload close it. Every path preserves the words for an
    explicit Reopen, while an interrupted writer retains the native caret.
    """
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url)
    if surface == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root["id"]}"]')
        thread.locator(".lf-thread-summary").click()
    else:
        page.keyboard.press("t")
        thread = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-thread="{root["id"]}"]'
        )
        page.keyboard.press("c")
    field = thread.locator("leaf-text")
    words = "An unfinished thought about this thread."
    write(field, words)
    field.evaluate("box => box.setSelectionRange(5, 5)")
    if resolution == "user":
        with sending(page, "the deliberate resolution"):
            thread.locator(".lf-resolve").click()
    else:
        if resolution == "inactive-agent":
            page.keyboard.press("Escape")
            assert take_browser_errors(page) == []
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "resolve",
                "author": "agent",
                "agent": "Codex",
                "parent": root["id"],
            },
        )
        told(page)
    if resolution == "active-agent":
        expect(field).to_be_visible()
        expect(field).to_be_focused()
        expect(field).to_have_js_property("value", words)
        assert field.evaluate("box => [box.selectionStart, box.selectionEnd]") == [5, 5]
        page.keyboard.press("Escape")
        if surface == "panel":
            # Escape ends the editing and lands on the card's title, a move within the
            # thread, so the card still holds the resolution behind its notice.
            expect(field).to_be_visible()
            thread.get_by_role("button", name="Resolved", exact=True).click()
        expect(field).not_to_be_visible()
    elif resolution == "inactive-agent" and surface == "panel":
        # The open card holds the resolution behind its notice, words and all, until
        # the user presses it.
        expect(field).to_be_visible()
        expect(field).to_have_js_property("value", words)
        thread.get_by_role("button", name="Resolved", exact=True).click()
        expect(field).not_to_be_visible()
    else:
        expect(thread.locator("leaf-text")).not_to_be_visible()
    assert stored_draft_text(page, f"reply:{root['id']}") == words
    if resolution == "inactive-agent" and surface == "margin":
        # An unresolved thread still draws its inactive reply box after Escape.
        # Agent settlement then closes it, as this lifecycle deliberately requires.
        # The generic words sensor cannot infer that ending the editing session made
        # this later passive close legitimate. Calibrate only this exact loss here;
        # Escape itself, active settlement, and every other field remain strict.
        errors = consume_browser_errors(
            page,
            f'typed words left the screen without a key or press: "{words}" in leaf-text.lf-ui',
        )
        assert len(errors) == 1

    page.reload()
    wait_until_ready(page)
    if surface == "margin":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    recovered = page.locator(f'.lf-threads > .lf-thread[data-id="{root["id"]}"]')
    recovered.locator(".lf-thread-summary").click()
    expect(recovered.locator("leaf-text")).to_have_count(0)
    with sending(page, "reopen with the saved reply"):
        recovered.locator(".lf-reopen").click()
    expect(recovered.locator("leaf-text")).to_be_focused()
    expect(recovered.locator("leaf-text")).to_have_js_property("value", words)


@pytest.mark.parametrize(
    "surface, continuation",
    [("panel", "send"), ("margin", "dismiss"), ("panel", "clear")],
)
def test_a_resolved_reply_composition_stays_open_until_deliberately_dismissed(
    browser, serve, surface, continuation
):
    """Tab preserves the composition; Send or a deliberate press elsewhere ends it."""
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url)
    if surface == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root["id"]}"]')
        thread.locator(".lf-thread-summary").click()
    else:
        page.keyboard.press("t")
        thread = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-thread="{root["id"]}"]'
        )
        page.keyboard.press("c")
    words = "I still need to send this reply."
    write(thread.locator("leaf-text"), words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root["id"]},
    )
    told(page)
    if continuation == "clear":
        field = thread.locator("leaf-text")
        field.press("ControlOrMeta+a")
        field.press("Backspace")
        rendered(page)
        expect(field).to_be_visible()
        expect(field).to_be_focused()
        expect(field).to_have_js_property("value", "")
        field.press("Escape")
        if surface == "panel":
            # The card holds the resolution behind its notice until the user asks.
            thread.get_by_role("button", name="Resolved", exact=True).click()
        expect(field).not_to_be_visible()
        assert stored_draft_text(page, f"reply:{root['id']}") == ""
        return
    page.keyboard.press("Tab")
    send = thread.get_by_role("button", name="Send", exact=True)
    expect(send).to_be_focused()
    rendered(page)
    expect(send).to_be_visible()
    expect(thread.locator("leaf-text")).to_have_js_property("value", words)
    if continuation == "send":
        with sending(page, "the retained reply"):
            page.keyboard.press("Enter")
        replies = [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "reply"
        ]
        assert [(event["parent"], event["text"]) for event in replies] == [
            (root["id"], words)
        ]
    else:
        page.keyboard.press("Tab")
        rendered(page)
        expect(thread.locator("leaf-text")).to_be_visible()
        page.locator("#p3").click(position={"x": 10, "y": 10})
        if surface == "panel":
            # The open card holds the resolution behind its notice, so it still draws
            # an open thread's reply box until the user asks to see the resolution.
            expect(thread.locator("leaf-text")).to_be_visible()
            thread.get_by_role("button", name="Resolved", exact=True).click()
        expect(thread.locator("leaf-text")).not_to_be_visible()
        if surface == "margin":
            expect(page.locator('[data-lf-margin-for="p3"]')).to_have_count(0)
        assert stored_draft_text(page, f"reply:{root['id']}") == words


def test_send_follows_a_reply_composition_whose_diff_outlet_disappears(browser, serve):
    """A replaced patch carries the same Send control to the thread's margin card."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><p id="p3">',
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can this line return a different value?",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    page = open_page(browser, url)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    words = "I still need to send my answer about that line."
    write(inline.locator("leaf-text"), words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    page.keyboard.press("Tab")
    expect(inline.get_by_role("button", name="Send", exact=True)).to_be_focused()
    rendered(page)
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    expect(inline).to_have_count(0)
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    expect(card.get_by_role("button", name="Send", exact=True)).to_be_focused()
    expect(card.locator("leaf-text")).to_have_js_property("value", words)
    with sending(page, "the reply after its Send moved"):
        page.keyboard.press("Enter")
    reply = events_model.read_events(serve.page_dir)[-1]
    assert (reply["kind"], reply["parent"], reply["text"]) == ("reply", root, words)


@pytest.mark.parametrize("resolved, cleared", [(False, True), (True, False)])
def test_tab_browsing_keeps_a_reply_when_its_diff_outlet_is_replaced(
    browser, serve, resolved, cleared
):
    """External source replacement carries editing without reversing native Tab."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><a id="after-diff" href="#p3">After the diff</a><p id="p3">',
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can this line return a different value?",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    page = open_page(browser, url)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    words = "I still need to send my answer about that line."
    write(inline.locator("leaf-text"), words)
    if cleared:
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.press("Backspace")
        words = ""
    if resolved:
        events_model.append_event(
            serve.page_dir,
            {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
        )
        told(page)
    page.keyboard.press("Tab")
    if not cleared:
        expect(inline.get_by_role("button", name="Send", exact=True)).to_be_focused()
    rendered(page)
    after = page.locator("#after-diff")
    for _ in range(20):
        page.keyboard.press("Tab")
        if after.evaluate('node => node.matches(":focus")'):
            break
    expect(after).to_be_focused()
    rendered(page)
    expect(inline.locator("leaf-text")).to_be_visible()
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    expect(page.locator("lf-diff").get_by_text("new = 1", exact=True)).to_be_visible()
    expect(inline).to_have_count(0)
    expect(after).to_be_focused()
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    expect(card.locator("leaf-text")).to_be_visible()
    expect(card.locator("leaf-text")).to_have_js_property("value", words)


def test_tab_browsing_continues_a_displaced_reply_without_an_annotation_overlay(
    browser, serve
):
    """Native Tab during core continuation preserves its caret and newer authored focus."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><a id="after-diff" href="#p3">After the diff</a><a id="second-link" href="#p3">Second link</a><p id="p3">',
    )
    source = source.replace("<body>", '<body data-annotations="page">', 1)
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can this line return a different value?",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    page = open_page(browser, url)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    page.keyboard.press("t")
    page.keyboard.press("c")
    words = "I still need to send my answer about that line."
    write(inline.locator("leaf-text"), words)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    page.keyboard.press("Tab")
    expect(inline.get_by_role("button", name="Send", exact=True)).to_be_focused()
    rendered(page)
    after = page.locator("#after-diff")
    for _ in range(20):
        page.keyboard.press("Tab")
        if after.evaluate('node => node.matches(":focus")'):
            break
    expect(after).to_be_focused()
    rendered(page)
    expect(inline.locator("leaf-text")).to_be_visible()
    # Hold the actual panel presentation, after its route was chosen. Tab is a
    # newer standing intent while the same native editing generation remains alive.
    page.evaluate(
        """() => {
          const list = document.querySelector('.lf-threads');
          const present = list.present.bind(list);
          const held = Promise.withResolvers();
          list.present = model => {
            if (!document.querySelector('.lf-thread-panel').classList.contains('open')) return present(model);
            window.replyContinuationHeld = true;
            return held.promise.then(() => present(model));
          };
          window.releaseReplyContinuation = () => {
            list.present = present;
            held.resolve();
          };
        }"""
    )
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    page.wait_for_function("window.replyContinuationHeld === true")
    expect(after).to_be_focused()
    page.keyboard.press("Tab")
    second = page.locator("#second-link")
    expect(second).to_be_focused()
    page.evaluate("releaseReplyContinuation()")
    wait_until_ready(page)
    expect(page.locator("lf-diff").get_by_text("new = 1", exact=True)).to_be_visible()
    expect(inline).to_have_count(0)
    expect(second).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_have_count(0)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card.locator("leaf-text")).to_be_visible()
    expect(card.locator("leaf-text")).to_have_js_property("value", words)

    assert card.locator("leaf-text").evaluate(
        "node => [node.selectionStart,node.selectionEnd]"
    ) == [1, 1]
    card.locator("leaf-text").focus()
    with sending(page, "the continued reply in Threads"):
        page.keyboard.press("Enter")
    reply = events_model.read_events(serve.page_dir)[-1]
    assert (reply["kind"], reply["parent"], reply["text"]) == ("reply", root, words)


@pytest.mark.parametrize("leave", ["send", "escape"])
def test_replaced_reply_compositions_keep_their_carets_and_leave_commands(
    browser, serve, leave
):
    """One selected card can carry several native sessions without merging their exits.

    Both agent-resolved replies retain their words and carets through source replacement.
    Existing disclosure selects each; Send and Escape dismiss only the addressed one.
    """
    patch = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n-old = 1\n+new = 1\n-old = 2\n+new = 2\n"
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><a id="after-diff" href="#p3">After the diff</a><p id="p3">',
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    roots = [
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"Please review line {line}.",
                "anchor": {
                    "section": "patch",
                    "datum": f'["app.py","new",{line}]',
                    "source": "review-patch",
                    "source_revision": source_revision(serve.page_dir, "review-patch"),
                },
            },
        )["id"]
        for line in (1, 2)
    ]
    page = open_page(browser, url)
    inputs = [
        page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"] leaf-text')
        for root in roots
    ]
    words = ["My unfinished first answer.", "My unfinished second answer."]
    write(inputs[0], words[0])
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Tab")
    write(inputs[1], words[1])
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    after = page.locator("#after-diff")
    for _ in range(20):
        page.keyboard.press("Tab")
        if after.evaluate('node => node.matches(":focus")'):
            break
    expect(after).to_be_focused()
    for root in roots:
        events_model.append_event(
            serve.page_dir,
            {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
        )
    told(page)
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 9\n+new = 9\n"
    )
    told(page)
    expect(after).to_be_focused()
    # One margin card remains the current selection. The other native session keeps
    # its words and caret until the user selects its next route.
    page.evaluate("() => window.lfWordsJudged()")
    assert take_browser_errors(page) == []
    for root, word in zip(roots, words):
        box = page.locator(f'.lf-thread[data-id="{root}"] leaf-text')
        expect(box).to_have_js_property("value", word)
    current = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{roots[1]}"] leaf-text'
    )
    assert current.evaluate("node => [node.selectionStart,node.selectionEnd]") == [2, 2]
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    first = page.locator(f'.lf-thread[data-id="{roots[0]}"]')
    first.locator(".lf-thread-summary").focus()
    expect(first.locator("leaf-text")).to_be_visible()
    expect(first.locator("leaf-text")).to_have_js_property("value", words[0])

    for index, (root, word) in enumerate(zip(roots, words), 1):
        card = page.locator(f'.lf-thread[data-id="{root}"]')
        card.locator(".lf-thread-summary").focus()
        page.keyboard.press("c")
        expect(card.locator("leaf-text")).to_be_focused()
        assert card.locator("leaf-text").evaluate(
            "node => [node.selectionStart,node.selectionEnd]"
        ) == [index, index]
        if index == 1 and leave == "escape":
            page.keyboard.press("Escape")
            expect(card.locator("leaf-text")).to_have_count(0)
            assert stored_draft_text(page, "reply:" + root) == word
            continue
        with sending(page, "the retained composition selected in Threads"):
            page.keyboard.press("Enter")
        reply = events_model.read_events(serve.page_dir)[-1]
        assert (reply["kind"], reply["parent"], reply["text"]) == ("reply", root, word)


@pytest.mark.parametrize("destination", ["passage", "reply"])
def test_a_transfer_keeps_its_persisted_source_when_the_destination_write_fails(
    browser, serve, destination
):
    """A failed larger destination write cannot be followed by a smaller tombstone."""
    page = open_page(browser, serve(LONG_PAGE, anchored=[("p41", "Paragraph 41.")]))
    words = "The only persisted copy must survive the transfer and reload."
    choose_comment_target(page, "#p3")
    write(page.locator(".lf-fab-input"), words)
    page.evaluate(
        """prefix => {
          const set = Storage.prototype.setItem;
          window.lfRefusedTransferWrites = 0;
          Storage.prototype.setItem = function (key, value) {
            if (key.startsWith(prefix) && !JSON.parse(value).settled) {
              window.lfRefusedTransferWrites++;
              throw new DOMException('full', 'QuotaExceededError');
            }
            return set.call(this, key, value);
          };
        }""",
        draft_key(page, ""),
    )
    if destination == "passage":
        page.keyboard.press("Escape")
        choose_comment_target(page, "#p9")
        field = page.locator(".lf-fab-input")
    else:
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("t")
        page.keyboard.press("c")
        field = page.locator(".lf-margin-preview .lf-page-thread leaf-text")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    assert page.evaluate("() => window.lfRefusedTransferWrites") > 0

    page.reload()
    wait_until_ready(page)
    page.keyboard.press("Escape")
    choose_comment_target(page, "#p3")
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)


def test_an_explicit_target_does_not_overwrite_its_existing_draft(
    browser, serve, one_user
):
    """A deliberate retarget carries words only into an empty passage.

    Two passages may already hold independent work. Choosing the second from the first
    tab should therefore reopen the draft at the chosen destination and leave the source
    draft where it was, rather than tombstoning the source and replacing the destination.
    The target picker is the real explicit gesture whose carry path owns that choice.
    """
    url = serve(LONG_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)

    source = "This paragraph buries the point."
    destination = "This later paragraph already has its own note."
    choose_comment_target(first, "#p3")
    write(first.locator(".lf-fab-input"), source)
    choose_comment_target(second, "#p9")
    write(second.locator(".lf-fab-input"), destination)

    first.keyboard.press("Escape")
    expect(first.locator(".lf-composer")).to_be_hidden()
    choose_comment_target(first, "#p9")
    expect(first.locator(".lf-fab-input")).to_have_js_property("value", destination)

    first.keyboard.press("Escape")
    choose_comment_target(first, "#p3")
    expect(first.locator(".lf-fab-input")).to_have_js_property("value", source)


def test_an_explicit_target_carries_into_an_emptied_draft(browser, serve):
    """A cleared destination record holds no work that should outrank a carried draft."""
    page = open_page(browser, serve(LONG_PAGE))
    field = page.locator(".lf-fab-input")

    choose_comment_target(page, "#p9")
    write(field, "Words the user removes.")
    write(field, "")
    page.keyboard.press("Escape")

    source = "Words to carry to the later paragraph."
    choose_comment_target(page, "#p3")
    write(field, source)
    page.keyboard.press("Escape")
    choose_comment_target(page, "#p9")
    expect(field).to_have_js_property("value", source)


def test_a_composer_on_one_passage_is_one_box_in_every_tab(browser, serve, one_user):
    """The composer is a box and a piece of chrome at once, so a second tab owes it
    more than the words. An emptied box is a box the user is still holding open and
    must stay up; a settled one has nothing left to be open about and goes down, or the
    other tab is left offering to send words the log already carries.

    The mirrored value is read for its height as well, because a box that took another
    tab's words and did not grow to them is one whose text is out of sight — the shape
    of bug a script sizing the box on `input` alone would reintroduce.

    Read in a window whose margin holds the bar beside the passage, so both tabs size
    one box in one place."""
    url = serve(LONG_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    for tab in (first, second):
        resized(tab, 1440, 900)

    height = "ta => Math.round(ta.getBoundingClientRect().height)"
    compose(first, "#p3")
    compact_height = first.locator(".lf-composer leaf-text").evaluate(height)
    opened = "This paragraph buries the point."
    write(first.locator(".lf-composer leaf-text"), opened)
    compose(second, "#p3")
    expect(second.locator(".lf-composer leaf-text")).to_have_js_property(
        "value", opened
    )

    grown = opened + "\n\n" + "And the one after it says the same thing again. " * 4
    write(first.locator(".lf-composer leaf-text"), grown)
    expect(second.locator(".lf-composer leaf-text")).to_have_js_property("value", grown)
    assert first.locator(".lf-composer leaf-text").evaluate(height) > compact_height
    assert second.locator(".lf-composer leaf-text").evaluate(height) == first.locator(
        ".lf-composer leaf-text"
    ).evaluate(height), (
        "a box grown from another tab's keystrokes must be laid out like a typed one"
    )

    # Emptying is an edit and not a settlement: the box stays up, holding nothing.
    write(first.locator(".lf-composer leaf-text"), "")
    expect(second.locator(".lf-composer leaf-text")).to_have_js_property("value", "")
    expect(second.locator(".lf-composer")).to_be_visible()
    assert second.locator(".lf-composer leaf-text").evaluate(height) == compact_height

    sent = "The point is buried, and the paragraph after it repeats it."
    write(first.locator(".lf-composer leaf-text"), sent)
    first.keyboard.press("ControlOrMeta+Enter")
    round_trip(first)
    expect(second.locator(".lf-composer")).to_be_hidden()
    said = [
        e["text"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    assert said == [sent], "one box, and so one comment however many tabs showed it"


def test_a_draft_explains_its_change_and_restores_history_as_an_edit(browser, serve):
    """One disclosure answers both deferred draft decisions. It compares this version's
    authored body with the standing body, retains every absolute edit in log order,
    and walks back by posting another ordinary edit. A second tab proves restore is
    durable replay rather than local history state; copy mode proves the local history
    does not survive without its handlers.

    The comparison is drawn by the text aligner, which is allowed to choose where an
    ambiguous repeated word aligns, but never to lose or invent a character: same+delete
    is the old text, same+insert the new one. Unicode, whitespace and repetition are
    where a character or regex diff quietly breaks. Both granularities, because the unit
    is the caller's and the contract is not: a draft's history aligns by word, while an
    inline version comparison starts with sentences and refines a local edit by word.
    Its words come from Intl.Segmenter, so it is read in the browser."""
    url = serve(JOURNEY_V1)
    page = open_page(browser, url)
    cases = [
        ("", ""),
        ("one line", "one longer line"),
        ("first\nsecond  line", "first\nsecond line\nthird"),
        ("l’écran est prêt 😀", "l’écran était prêt 🟢"),
        ("迁移完成。再次迁移。", "迁移完成。回滚完成。"),
        ("Retry once. Retry once. Then stop.", "Retry once. Retry twice. Then stop."),
        (
            "shared " + " ".join(f"old-{i}" for i in range(2500)) + " ending",
            "shared " + " ".join(f"new-{i}" for i in range(2500)) + " ending",
        ),
    ]
    aligned, by_sentence, inline = page.evaluate(
        """async (pairs) => {
          const {alignInlineText, alignText, sentenceUnits} =
            await window.__lfRuntimeImport('/runtime/text-alignment.js');
          return [
            pairs.map(([before, after]) => alignText(before, after)),
            pairs.map(([before, after]) => alignText(before, after, sentenceUnits)),
            pairs.map(([before, after]) => alignInlineText(before, after)),
          ];
        }""",
        cases,
    )
    for unit, walked in (
        ("word", aligned),
        ("sentence", by_sentence),
        ("inline", inline),
    ):
        for (before, after), runs in zip(cases, walked):
            joined = "".join(run["text"] for run in runs if run["kind"] != "insert")
            assert joined == before, (unit, joined, before)
            joined = "".join(run["text"] for run in runs if run["kind"] != "delete")
            assert joined == after, (unit, joined, after)
            assert all(a["kind"] != b["kind"] for a, b in itertools.pairwise(runs)), (
                unit
            )

    repeated = aligned[-2]
    assert "".join(r["text"] for r in repeated if r["kind"] == "delete") == "once"
    assert "".join(r["text"] for r in repeated if r["kind"] == "insert") == "twice"
    assert "Then stop." in "".join(r["text"] for r in repeated if r["kind"] == "same")
    assert [run["kind"] for run in aligned[-1]] == ["same", "delete", "insert", "same"]

    local = page.evaluate(
        """async () => {
          const {alignInlineText} = await window.__lfRuntimeImport('/runtime/text-alignment.js');
          return alignInlineText(
            'Each section names a feature and provides a live example.',
            'Each section names a feature and provides a live example, including focused replays of its motion.'
          );
        }"""
    )
    assert "".join(run["text"] for run in local if run["kind"] == "delete") == ""
    assert "".join(run["text"] for run in local if run["kind"] == "insert") == (
        ", including focused replays of its motion"
    )

    draft = page.locator("#draft-ops")
    edits = [
        "Run the migration before deploying. It takes one minute.",
        "Run the migration after the backup. It takes two minutes.",
    ]
    for index, text in enumerate(edits, 1):
        draft.locator(".lf-draft-body").dblclick()
        write(draft.locator("leaf-text"), text)
        draft_control(page, "save", "draft-ops").click()
        round_trip(page)  # the history is drawn from the log, not the box
        expect(draft.locator(".lf-draft-history > summary")).to_have_text(
            f"Changes · {index} {'edit' if index == 1 else 'edits'}"
        )

    # The disclosure is the platform's to work and the register says so, naming the
    # press where the user is standing on it and reading which way it goes off the
    # state they can already see.
    history = draft.locator(".lf-draft-history > summary")
    history.focus()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("show the history")
    history.click()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("hide the history")

    current_deleted = "".join(draft.locator(".lf-draft-current del").all_inner_texts())
    current_inserted = "".join(draft.locator(".lf-draft-current ins").all_inner_texts())
    assert "before" in current_deleted and "deploying" in current_deleted
    assert "afterthebackup" in re.sub(r"\s+", "", current_inserted)
    labels = draft.locator(".lf-draft-revision-head strong").all_inner_texts()
    assert labels == ["Version text", "Edit 1 · v1", "Edit 2 · v1"]
    # Adjacent recorded edits are aligned too, rather than rendered as two unrelated
    # snapshots. The first has no knowable predecessor on a later pinned version.
    second_delta = draft.locator(".lf-draft-revisions > li").nth(2)
    second_deleted = "".join(second_delta.locator("del").all_inner_texts())
    second_inserted = "".join(second_delta.locator("ins").all_inner_texts())
    assert "before" in second_deleted and "deploying" in second_deleted
    assert "afterthebackup" in re.sub(r"\s+", "", second_inserted)
    # Comparisons preserve source whitespace; template indentation is visible here.
    comparison = second_delta.locator(".lf-draft-delta").text_content()
    assert comparison == comparison.strip()

    draft.get_by_role("button", name="Restore edit 1 · v1").focus()
    page.keyboard.press("Enter")
    round_trip(page)
    expect(draft.locator(".lf-draft-body")).to_have_text(edits[0])
    expect(draft.locator(".lf-draft-history > summary")).to_have_text(
        "Changes · 3 edits"
    )
    expect(draft.locator(".lf-draft-history > summary")).to_be_focused()
    expect(draft.locator(".lf-draft-history")).to_have_attribute("open", "")
    expect(draft).to_have_attribute("data-lf-user-override", "1")

    events = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["value"] for event in events] == [
        edits[0],
        edits[1],
        edits[0],
    ]
    assert [event["action"] for event in events] == ["edit", "edit", "edit"]

    sequence = page.evaluate(
        """async () => {
          const {widgetController} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const widget = document.getElementById('draft-ops');
          const controller = widgetController(widget);
          const first = controller.read().actions.edit.history;
          first[0].detail.value = 'A widget must not mutate the runtime log.';
          return controller.read().actions.edit.history
            .map(event => [event.seq, event.detail.value]);
        }"""
    )
    assert [text for _, text in sequence] == [edits[0], edits[1], edits[0]]
    assert [seq for seq, _ in sequence] == sorted(seq for seq, _ in sequence)

    # The handover URL, since the key it carries has left this tab's address.
    other = open_page(browser, url)
    expect(other.locator("#draft-ops .lf-draft-body")).to_have_text(edits[0])
    expect(other.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 3 edits"
    )


def test_action_history_is_bounded_by_the_pinned_version(browser, serve):
    """A historical page cannot narrate an edit that had not happened yet. The
    helper owns the same version boundary replay does, so every future widget that
    consumes a sequence gets this right without copying the filter."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    for version, text in ((1, "First recorded body."), (2, "Second recorded body.")):
        if version == 2:
            stamp_page(d, JOURNEY_V2, "v2")
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": version,
                "widget": "draft-ops",
                "action": "edit",
                "detail": {"value": text},
            },
        )

    old = open_page(browser, url, pin=True)
    expect(old.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 1 edit"
    )
    old_sequence = old.evaluate(
        """async () => (await window.__lfRuntimeImport('/runtime/widget-api.js'))
          .widgetController(document.getElementById('draft-ops')).read().actions.edit.history
          .map(event => event.revision)"""
    )
    assert old_sequence == [1]

    latest = open_page(browser, url.replace("v1.html", "v2.html"), pin=True)
    expect(latest.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 2 edits"
    )
    latest_sequence = latest.evaluate(
        """async () => (await window.__lfRuntimeImport('/runtime/widget-api.js'))
          .widgetController(document.getElementById('draft-ops')).read().actions.edit.history
          .map(event => event.revision)"""
    )
    assert latest_sequence == [1, 2]


def test_an_acknowledged_decision_still_survives_the_next_version(browser, serve):
    """The round trip above, differing in one fact: the agent has acknowledged the
    actions before v2 publishes. That is the ordinary case — the agent writes a
    version *because* it was handed the user's edits — and it used to be the
    one that lost them: replay stopped at the handoff cursor, on the premise
    that a version written after seeing an action encodes it. Nothing checks that
    premise, so a version that quietly omits the state re-emitted the widget as
    untouched and the user's work vanished with no error anywhere.

    Acknowledgement is not assent. Only the next version's markup can say what the
    agent did with an edit, and until it says otherwise the log is what the user
    did."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "board",
            "action": "move",
            "detail": {"unit": "card-x", "value": "col-done", "rank": "0i"},
        },
    )
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"value": DRAFT_EDITED},
        },
    )
    # The highest user event reached context, so everything so far is ours to answer.
    with service_model.PageTransaction(d) as transaction:
        batch = {"events": transaction.events}
        with delivery_model.receive_batch(
            transaction, batch, session_id=None
        ) as events:
            delivery_model.record_pickup(transaction, events)
    # And the agent answers with a version that carries neither — the page generator
    # emitting its own idea of the board and the draft, as one did for five
    # versions running.
    stamp_page(d, JOURNEY_V2, "v2")

    page = open_page(browser, url.replace("v1.html", "v2.html"))
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_attribute(
        "data-lf-source-words", DRAFT_EDITED
    )
    expect(page.locator("#col-done #card-x")).to_have_count(1)


def test_a_comment_written_on_an_edited_draft_lands_on_their_words(browser, serve):
    """`leaf thread open` reads the mapped revision plus the log; the user's tab reads
    the DOM replay builds from the same two. An edited draft is where those readings
    used to drift — the file holds words the page stopped showing — so write the anchor
    blind, on the user's own words, and prove the page paints it. The words the edit
    replaced are refused at the CLI, because posted they would detach in front of the
    user."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"value": DRAFT_EDITED},
        },
    )
    refused = CliRunner().invoke(
        cli_model.cli,
        ["thread", "open", str(d), "--quote", "It is online.", "--text", "x"],
    )
    assert refused.exit_code != 0 and "doesn't say" in refused.output
    written = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "open",
            str(d),
            "--quote",
            "It takes about a minute.",
            "--text",
            "Measured where?",
        ],
        catch_exceptions=False,
    )
    assert written.exit_code == 0, written.output

    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    thread = page.locator(".lf-thread .lf-quote").first
    expect(thread).not_to_have_class(re.compile(r"\bdetached\b"))
    assert painted(page, "lf-mark") == "It takes about a minute."


def test_registered_control_keys_activate_once(browser, serve):
    """A native draft button activates without a Leaf binding. The selectable option
    mark is the explicit exception and owns its Space row.

    Activation happens once per press however long the key is held. A keydown listener
    hears repeats, and a mark that toggles per repeat posts a `choose` for each one. Repeats
    are dispatched rather than driven because no automation holds a key down; the browser
    delivers this event with `repeat` set."""
    page = open_page(browser, serve(KEYS_PAGE))

    pencil = draft_control(page, "edit", "draft-ops")
    assert pencil.evaluate("el => el.localName") == "button"
    expect(pencil).to_have_attribute("type", "button")
    pencil.focus()
    page.keyboard.press("Enter")
    editor = page.locator("#draft-ops leaf-text")
    expect(editor).to_be_focused()
    focus_paint = page.locator("#draft-ops").evaluate(
        """host => {
          const editor = host.querySelector('leaf-text');
          const hs = getComputedStyle(host), es = getComputedStyle(editor);
          return {
            host: {outline: hs.outlineStyle, width: parseFloat(hs.outlineWidth)},
            editor: {outline: es.outlineStyle, shadow: es.boxShadow,
                     ring: es.getPropertyValue('--lf-focus-ring').trim()},
          };
        }"""
    )
    assert focus_paint["host"]["outline"] != "none"
    assert focus_paint["host"]["width"] >= 2
    assert focus_paint["editor"] == {
        "outline": "none",
        "shadow": "none",
        "ring": "none",
    }, "the draft's one editing surface acquired a second focus box"
    page.emulate_media(forced_colors="active")
    forced = page.locator("#draft-ops").evaluate(
        """host => {
          const editor = host.querySelector('leaf-text');
          return {
            host: getComputedStyle(host).outlineStyle,
            editor: getComputedStyle(editor).outlineStyle,
          };
        }"""
    )
    assert forced == {"host": "solid", "editor": "none"}
    page.emulate_media(forced_colors="none")
    page.keyboard.press("Escape")

    mark = page.locator("#opts .lf-pick").first
    mark.focus()
    page.keyboard.press(" ")
    expect(page.locator("#opts > lf-option[chosen]")).to_have_count(1)
    chosen = page.locator("#opts > lf-option[chosen]").get_attribute("id")
    mark.evaluate("""el => {
        for (let i = 0; i < 5; i++)
            el.dispatchEvent(new KeyboardEvent('keydown',
                {key: ' ', repeat: true, bubbles: true, cancelable: true}));
    }""")
    expect(page.locator(f"#{chosen}[chosen]")).to_have_count(1)
    # The mark paints its own press before the post answers, so the DOM leads the log:
    # read the file straight after and the first press's event may not be in it yet,
    # which reads exactly like a press that sent nothing. A press that sent nothing
    # satisfies this too, which is what makes it the right wait for both assertions —
    # the repeats below must add none of their own.
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)
    assert [e for e in sent if e.get("action") == "choose"] != [], (
        "the first press sent nothing, so the repeats below had nothing to duplicate"
    )
    assert len([e for e in sent if e.get("action") == "choose"]) == 1, (
        "a held key sent one decision per repeat"
    )


def test_global_shortcuts_leave_other_browser_navigation_keys_alone(browser, serve):
    """The document-level dispatcher owns a few character key shortcuts, not the
    keyboard. Space, arrows, Home/End, and PageUp/PageDown must still reach the browser
    when focus is in the authored page
    rather than a widget control.

    Observe `defaultPrevented` on real key events instead of asserting that Chrome
    happened to scroll: scrolling depends on viewport and focus geometry, while
    canceling the event is the runtime decision under test. `?` is the positive
    control proving this observer sees a key the dispatcher intentionally consumes."""
    page = open_page(browser, serve(KEYS_PAGE))
    keys = [
        " ",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        "?",
    ]
    page.evaluate(
        """keys => {
          const pageContent = document.querySelector("main");
          pageContent.tabIndex = -1;
          pageContent.focus();
          window.lfObservedKeys = {};
          document.addEventListener("keydown", event => {
            if (keys.includes(event.key))
              window.lfObservedKeys[event.key] = event.defaultPrevented;
          });
        }""",
        keys,
    )
    for key in keys:
        page.keyboard.press(key)

    observed = page.evaluate("() => window.lfObservedKeys")
    assert observed.pop("?") is True, (
        "the positive-control shortcut was not consumed, so the probe did not "
        "observe the runtime dispatcher"
    )
    assert observed == dict.fromkeys(keys[:-1], False)


def test_the_browser_pages_the_document_with_space(browser, serve):
    """Space and Shift+Space are ordinary browser paging keys on authored content.

    Leaf does not prescribe a distance or animation. The browser chooses both; the
    contract here is simply that the document moves down and then back up without the
    runtime canceling either key."""
    page = open_page(browser, serve(SMOOTH_LONG_PAGE))
    page.evaluate(RELEASE_FOCUS)

    def press_and_settle(key):
        page.evaluate("""() => {
          window.__lfScrollEnded = false;
          addEventListener('scrollend', () => { window.__lfScrollEnded = true; },
                           {once: true});
        }""")
        page.keyboard.press(key)
        page.wait_for_function("() => window.__lfScrollEnded")
        return page.evaluate("() => document.scrollingElement.scrollTop")

    down = press_and_settle("Space")
    assert down > 0, "the browser did not page the document down"
    up = press_and_settle("Shift+Space")
    assert up < down, "the browser did not page the document back up"


def test_the_reading_keys_accumulate_and_reverse(browser, serve):
    """d/u move 60% of the visible page; j/k take small steps through the same glide.
    The page sets scroll-behavior: smooth on the box, as an authored page may —
    a step whose writes ride that rule instead of stating `instant` never lands.

    Every phase waits on its destination, never on scrollend or a timer: the glide
    writes a frame at a time and Chrome answers each write with a scrollend, so
    "scrolling ended" is a fact about a frame, while the destination is the one
    position a glide approaching it never passes through early. A wrong step then
    reads as the wrong number, which says what happened.

    The second press follows the first with no wait between them, landing inside the
    first glide, so presses have to add up from the goal rather than from wherever
    the glide has got to. Taking the box mid-glide — programmatically, because the
    cancel reads positions and any hand looks the same to it, and this one lands at
    a number the assertion can hold — must stand the step down: the next press
    measures from where the user left the box, not from the goal it dropped, and a
    glide that ignored the taking presses on to that goal and fails both reads.
    Pressing on at the foot moves nothing and banks nothing, so u from there
    is one step back. Both pairs of keys walk the same page in turn, each from its top."""
    page = open_page(browser, serve(SMOOTH_LONG_PAGE))
    assert page.evaluate(
        "() => document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight * 3"
    ), "the page is too short for these steps to be told apart"
    # A callback's frame timestamp may predate performance.now() in the key handler.
    # Make that browser timing deterministic: a negative first fraction used to write
    # above the page, get clamped to zero, then cancel the glide as if the user moved.
    page.evaluate(
        """downs => {
      const raf = requestAnimationFrame;
      let stale = false;
      addEventListener('keydown', event => {
        if (downs.includes(event.key)) stale = true;
      }, {capture: true});
      window.requestAnimationFrame = callback => {
        const firstAfterPress = stale;
        stale = false;
        return raf(now => callback(firstAfterPress ? -1 : now));
      };
    }""",
        ["d", "j"],
    )

    for down, up in (("d", "u"), ("j", "k")):
        page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})"
        )
        reading_keys_walk(page, down, up)


def reading_keys_walk(page, down, up):
    """Step, double-step, reverse, take the box mid-glide and press past the foot
    with `down` and `up`, from the top of the page."""
    step = (
        60
        if down == "j"
        else page.evaluate(
            "() => { const s = getComputedStyle(document.scrollingElement); return ("
            " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
            " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
        )
    )

    def rests_at(act, expected):
        """Position after `act`, awaited at `expected` and handed to the assertion:
        the bounded wait consumes the arrival, and the assert is what speaks when
        the step went somewhere else instead."""
        act()
        try:
            page.wait_for_function(
                "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
                arg=expected,
            )
        except PlaywrightTimeout:
            pass
        return page.evaluate("() => document.scrollingElement.scrollTop")

    assert rests_at(lambda: page.keyboard.press(down), step) == pytest.approx(
        step, abs=1
    )

    def twice():
        page.keyboard.down(down)
        page.keyboard.down(down)  # a held key emits a repeated keydown
        page.keyboard.up(down)

    assert rests_at(twice, step * 3) == pytest.approx(step * 3, abs=1), (
        "the second press measured from the glide in flight, so the two together "
        "moved less than their full distance"
    )
    assert rests_at(lambda: page.keyboard.press(up), step * 2) == pytest.approx(
        step * 2, abs=1
    )

    def taken():
        page.keyboard.press(down)
        page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 400, behavior: 'instant'})"
        )

    assert rests_at(taken, 400) == pytest.approx(400, abs=1), (
        "the glide pressed on to its goal after the user took the box"
    )
    assert rests_at(lambda: page.keyboard.press(down), 400 + step) == pytest.approx(
        400 + step, abs=1
    ), (
        "the press after the user took the box measured from the goal the taking "
        "had cancelled rather than from where they left it"
    )

    foot = page.evaluate(
        "() => document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight"
    )
    assert rests_at(
        lambda: page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 1e9, behavior: 'instant'})"
        ),
        foot,
    ) == pytest.approx(foot, abs=1)
    for _ in range(4):
        page.keyboard.press(down)  # nothing left to move, and nothing banked either
    assert rests_at(lambda: page.keyboard.press(up), foot - step) == pytest.approx(
        foot - step, abs=1
    ), (
        "presses at the foot of the page ran the destination past it, and reversing spent "
        "itself paying that back"
    )


def test_the_reading_page_step_never_paints_behind_where_it_started(browser, serve):
    """The step's own frames, read at real speed from the middle of the page where the
    box clamps nothing: d may not paint the page above where the press found it. A rAF
    tick carries its frame's own start, so a press handled inside a frame already under
    way is stamped after the tick it schedules, and an ease reading that as elapsed time
    walks back out through its own start (stepReading says the rest). At the ends of the box
    that write is one the box clamps, and what the clamp does to the press is a resting
    position the test above reads; in the middle every write lands, the glide arrives
    exactly where it promised, and the user is thrown up to most of a page the wrong
    way on the route — which no resting position can see.

    Whether a press loses that race is the platform's to say, so the window is stated
    rather than run for: a throttled CPU is a longer frame, and a longer frame is a wider
    gap between its start and the press dispatched inside it. Unfloored, this machine
    flicked on one press in ten at its own speed and on eight in ten throttled, where a
    floored clock flicks on none of either. The injection buys the record, not the wait,
    which is still the destination's."""
    page = open_page(browser, serve(SMOOTH_LONG_PAGE))
    page.context.new_cdp_session(page).send(
        "Emulation.setCPUThrottlingRate", {"rate": 20}
    )
    step = page.evaluate(
        "() => { const s = getComputedStyle(document.scrollingElement); return ("
        " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
        " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
    )
    start = round(step * 2)
    page.evaluate("""() => {
        window.lfFrames = [];
        const sample = () => {
            window.lfFrames.push(document.scrollingElement.scrollTop);
            requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
    }""")
    for _ in range(5):
        page.evaluate(
            "at => document.scrollingElement.scrollTo({top: at, behavior: 'instant'})",
            start,
        )
        page.wait_for_function(
            "at => document.scrollingElement.scrollTop === at", arg=start
        )
        page.evaluate("() => (window.lfFrames = [])")
        page.keyboard.press("d")
        page.wait_for_function(
            "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
            arg=start + step,
        )
        assert min(page.evaluate("() => window.lfFrames")) >= start - 1, (
            "the step painted the page above where the press found it"
        )


def test_the_reading_keys_jump_under_reduced_motion(browser, serve):
    """Both reading distances jump immediately under reduced motion."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    page = open_page(browser, serve(SMOOTH_LONG_PAGE), context=context)
    for down, up in (("d", "u"), ("j", "k")):
        step = (
            60
            if down == "j"
            else page.evaluate(
                "() => { const s = getComputedStyle(document.scrollingElement); return ("
                " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
                " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
            )
        )
        page.keyboard.press(down)
        assert page.evaluate(
            "() => document.scrollingElement.scrollTop"
        ) == pytest.approx(step, abs=1), (
            down,
            "the step had not reached its destination when the press returned",
        )
        page.keyboard.press(up)
        assert page.evaluate(
            "() => document.scrollingElement.scrollTop"
        ) == pytest.approx(0, abs=1), up


def test_the_reading_page_keys_move_the_region_the_user_is_scrolling(browser, serve):
    """Two scroll regions, so d has to pick the one the user is looking at. Beside the
    page the panel is a column of its own and the keys are the document's. Under the
    breakpoint the sheet covers the page and the page hands scrolling over with it — one
    gesture moves one region, and while the sheet is up that region is its thread list.
    A key is no different from a wheel there: a page scrolling behind the sheet shows
    the user nothing, so the key reads as dead, and the document is somewhere else
    when the sheet closes."""
    page = open_page(browser, serve(LONG_PAGE, comments=40))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # Put the user on the page before asking which reading region the page gesture chooses.
    page.evaluate(RELEASE_FOCUS)
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        " return t.scrollHeight > t.clientHeight; }"
    ), "the thread list does not overflow, so it could not be seen to scroll below"

    def offsets():
        return page.evaluate(
            "() => [document.scrollingElement.scrollTop,"
            " document.querySelector('.lf-threads').scrollTop]"
        )

    def press_down():
        """Both offsets once a region answers the press — the glide's first write is
        already the answer to which region moved, and movement is the fact waited on
        because movement is the question. Scrollend was the wait here while a press
        could die outright, which read as the platform withholding the event; it
        withholds nothing, answering the step's frame-at-a-time writes seven times to
        the press on Linux, and a press that moves no region states neither fact.
        Waiting on whichever region speaks makes the wrong one answering two numbers
        to compare rather than half a minute of silence and a timeout."""
        was = offsets()
        page.keyboard.press("d")
        page.wait_for_function(
            "w => { const t = document.querySelector('.lf-threads');"
            " return document.scrollingElement.scrollTop !== w[0] || t.scrollTop !== w[1]; }",
            arg=was,
        )
        return was, offsets()

    (page_was, threads_was), (page_now, threads_now) = press_down()
    assert threads_now == threads_was, "the panel took a key aimed at the document"
    assert page_now > page_was, "the document did not move for a key of its own"
    scroll_settled(page)

    resized(page, 400, 600)
    panel_settled(page)
    (page_was, threads_was), (page_now, threads_now) = press_down()
    assert page_now == page_was, (
        "the page moved behind the covering sheet, where the user cannot see it"
    )
    assert threads_now > threads_was, "the sheet did not move for the key it now owns"


def test_the_reading_page_keys_follow_the_user_into_the_panel(browser, serve):
    """Which region the keys move is where the user is standing, and covering is only
    one of the two ways they come to be standing in the list. Beside the page — the wide
    window, where the page beside the panel stays live — a user working down a long
    thread presses d and the page behind them steps instead, which is the same
    nothing the covering case was written to prevent: the region they are reading does
    not move, and the document is somewhere else when they look back at it.

    One factor separates the two halves here. The window, the layout, the panel and the
    list are the same at both presses; only where the focus stands changes. So the first
    press is the control that says the layout is beside — the user stands on the page,
    outside the panel, and the document is theirs to step — and the second is the subject.
    The Go-to sequence then supplies the neighboring
    contrast: focus changes which region d/u page through, but `g g` still names the
    document's edge while both regions have somewhere observable to move."""
    page = open_page(browser, serve(LONG_PAGE, comments=40))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.evaluate(RELEASE_FOCUS)
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        " return t.scrollHeight > t.clientHeight; }"
    ), "the thread list does not overflow, so it could not be seen to scroll below"

    def offsets():
        return page.evaluate(
            "() => [document.scrollingElement.scrollTop,"
            " document.querySelector('.lf-threads').scrollTop]"
        )

    # The control, and the wait that makes the subject's baseline a resting one: the
    # document's own step is a glide, and the position it is going to is the one place
    # it does not pass through early (the reading-page test says the rest).
    step = page.evaluate(
        "() => { const s = getComputedStyle(document.scrollingElement); return ("
        " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
        " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
    )
    page_was, threads_was = offsets()
    page.keyboard.press("d")
    page.wait_for_function(
        "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
        arg=step,
    )
    page_now, threads_now = offsets()
    assert page_now > page_was, (
        "the document did not move for a key pressed from outside the panel, so the "
        "panel is not beside the page here and the case below is not the one named"
    )
    assert threads_now == threads_was, "the panel took a key aimed at the document"

    # Into the panel, standing on its open thread's title rather than in a box — `g T`'s
    # landing, which travels nothing, so the baseline below is the one the control left.
    # The address toggles the panel it names, so from the standing one the first
    # completion closes it and the second is the arrival.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(
        page.locator(
            ".lf-threads > .lf-thread:not([hidden])[open] > .lf-thread-summary"
        )
    ).to_be_focused()

    page_was, threads_was = offsets()
    page.keyboard.press("d")
    page.wait_for_function(
        "w => { const t = document.querySelector('.lf-threads');"
        " return document.scrollingElement.scrollTop !== w[0] || t.scrollTop !== w[1]; }",
        arg=[page_was, threads_was],
    )
    thread_step = page.locator(".lf-threads").evaluate(
        "t => { const s = getComputedStyle(t); return (t.clientHeight"
        " - parseFloat(s.scrollPaddingTop) - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
    )
    page.wait_for_function(
        "w => { const t = document.querySelector('.lf-threads');"
        " return Math.abs(t.scrollTop - w[0]) < 1"
        " || Math.abs(document.scrollingElement.scrollTop - w[1]) >= 1; }",
        arg=[thread_step, page_was],
    )
    page_now, threads_now = offsets()
    assert threads_now > threads_was, (
        "the list the user is standing in did not move for the key they pressed"
    )
    assert page_now == pytest.approx(page_was, abs=1), (
        "the page stepped behind a user who was working down the comment list"
    )

    # Both regions now stand away from their top edge. A correct g g returns the page;
    # the shared-scroller regression returns the panel instead. Wait for either answer so
    # the failure reports both offsets rather than timing out while expecting only one.
    assert page_now > 0 and threads_now > 0
    page.keyboard.press("g")
    page.keyboard.press("g")
    page.wait_for_function(
        "() => { const t = document.querySelector('.lf-threads');"
        " return document.scrollingElement.scrollTop < 1 || t.scrollTop < 1; }",
    )
    edge_page, edge_threads = offsets()
    assert edge_page == pytest.approx(0, abs=1), (
        f"g g left the page at {edge_page} and moved the panel to {edge_threads}"
    )
    assert edge_threads == pytest.approx(threads_now, abs=1), (
        f"g g moved the panel from {threads_now} to {edge_threads}"
    )


def test_the_page_has_one_door_to_a_comparison(browser, serve):
    """`=` marked what changed since the previous version from anywhere on the page, and
    the case for it was that it named no version — "since the last one I saw" is a
    question a user has without opening anything. Naming no version is also naming
    nothing to check, and the two are not the same question: on a page that ships a
    version whenever the work moves, a user back after a week got v(n-1) and no way to
    see that they had. So the door is the menu, where every base says which one it is.

    Pressed rather than read off the table, on both sides: a key bound to nothing looks
    exactly like one that works in the command reference dialog, which is how the removal would go
    unnoticed here and the marks would go unnoticed on the page."""
    url = serve(LONG_PAGE)
    _publish(
        serve.page_dir,
        2,
        LONG_PAGE.replace("Paragraph 3.", "Paragraph three."),
        "reworded a paragraph",
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    line = page.locator(".lf-shortcut-bar")
    # The door is a go-to destination rather than a bare letter, so the line names it
    # once the sequence is armed. The word that must not be anywhere is read behind that
    # arrival, so the absence is taken off a line the press has already repainted.
    page.keyboard.press("g")
    expect(line).to_contain_text("versions")
    expect(line).not_to_contain_text("mark changes")
    page.keyboard.press("Escape")
    page.keyboard.press("=")
    expect(page.locator(".lf-version-menu")).to_be_hidden()
    expect(page.locator(".lf-ins-block")).to_have_count(0)
    page.keyboard.press("g")
    expect(line).to_contain_text("versions")
    page.keyboard.press("Shift+v")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    page.keyboard.press("Escape")

    # The door, and it marks the same passage the key used to.
    compare_with(page)
    expect(page.locator("#p3")).to_have_class(re.compile(r"lf-ins-block"))


def test_the_draft_box_is_its_own_door(browser, serve):
    """A draft is the one block on a page whose whole purpose is that the user rewrites
    it, and until now the only thing that said so was a pencil in the margin 45px away.
    The block itself ignored a press. The gesture that did open it in place was a
    double-click, which is a thing you have to already know.

    So the box is the door, and the caret lands where the press did. Which is a door that
    has to be opened carefully, because the same words are the page's words: a user
    drawing across them to quote them ends that drag with a mouseup inside the box, and
    opening on it would throw the selection away at the moment it was finished. That is
    the question `reachedForWords` answers for every other press on the page's own words,
    asked here rather than answered again. The drag runs through the harness's own
    `hold_selection`, which floors the press - a fractional start point loses the
    selection outright, and an empty one would read exactly like the door swallowing it -
    and the words are read while the drag is still held, because the runtime re-seats the
    selection on a timer after the release and a read in that gap comes back empty.

    And the door is exactly the box - not the chrome inside it. `offer` writes its marker
    on everything a widget builds, controls row and edit box included, and only names a
    kind for the things to press; the guard reads that, so a press on the row does not
    reopen the editor and the row does not wear a hand it has no use for."""
    page = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    body = draft.locator(".lf-draft-body")
    expect(body).to_have_text(DRAFT_TEXT, use_inner_text=True)

    # A drag across the words takes the words. Read as the selection the user is left
    # holding, which is the thing the door would have destroyed.
    box = body.bounding_box()
    line = box["y"] + 8
    hold_selection(page, (box["x"] + 2, line), (box["x"] + box["width"] - 2, line))
    held = page.evaluate("() => getSelection().toString()")
    assert held.strip() != "", (
        f"the drag selected nothing, so this says nothing about the door: {held!r}"
    )
    page.mouse.up()
    expect(draft.locator("leaf-text")).to_have_count(0)

    # A press opens it, with the caret where the press landed rather than at the top.
    page.evaluate("() => getSelection().removeAllRanges()")
    at = page.evaluate(
        """(word) => {
            const node = document.createTreeWalker(
              document.querySelector('#draft-ops .lf-draft-body'),
              NodeFilter.SHOW_TEXT).nextNode();
            const start = node.data.indexOf(word);
            const range = document.createRange();
            range.setStart(node, start); range.setEnd(node, start + word.length);
            const r = range.getBoundingClientRect();
            return [r.x + r.width / 2, r.y + r.height / 2, start, word.length];
        }""",
        "migration",
    )
    page.mouse.click(at[0], at[1])
    editor = draft.locator("leaf-text")
    expect(editor).to_be_focused()
    caret = page.evaluate(
        "() => { const t = document.querySelector('#draft-ops leaf-text');"
        "        return [t.selectionStart, t.selectionEnd]; }"
    )
    assert caret[0] == caret[1], (
        f"one press selected a range rather than placing a caret: {caret}"
    )
    assert at[2] <= caret[0] <= at[2] + at[3], (
        f"the box opened with the caret at {caret[0]}, not in the word pressed "
        f"({at[2]}..{at[2] + at[3]})"
    )

    # The chrome inside the box is not the door, and does not dress as one. The controls
    # row and the edit box are both things `offer` built and neither names a kind.
    inside = page.evaluate(
        """() => [...document.querySelectorAll('#draft-ops [data-lf-offer=""]')]
             .filter(el => !el.closest("button"))
        .map((el) => [el.localName, getComputedStyle(el).cursor])"""
    )
    assert inside, "the draft built no generated chrome, so this proves nothing"
    assert all(cursor != "pointer" for _tag, cursor in inside), (
        f"generated chrome inside the draft dresses as a press: {inside}"
    )

    # And the pencil is still there, still the keyboard's way in.
    page.keyboard.press("Escape")
    pencil = draft_control(page, "edit", "draft-ops")
    expect(pencil).to_be_focused()
    pencil.click()
    expect(draft.locator("leaf-text")).to_be_visible()


# Generated editors carry native editing under their existing durable draft identity.
def editing_revision_source(mode):
    body = '<h1 id="subject">Editor continuity</h1><p id="passage">A stable passage stays exact across the revision.</p><textarea id="authored-draft" aria-label="Authored draft" style="height:80px"></textarea><lf-draft id="draft-root"><pre>Standing editable text.</pre></lf-draft><lf-ask id="choice-root"><h2>Which choice?</h2><lf-options id="options-root" choose><lf-option id="initial">Initial choice</lf-option></lf-options></lf-ask><lf-test-plan id="command-root" label="Tasks"><lf-test-task id="seat-root" status="active" talk>What should we do?</lf-test-task></lf-test-plan>'
    module = """<script type="module">
window.__rendererLifetime={birth:performance.timeOrigin,hits:0,version:'MODE'};
addEventListener('renderer-lifetime-probe',()=>window.__rendererLifetime.hits++);
// Native prototype activation route: activate the offered Latest control without
// transferring the editor's focus to the toolbar before the carry is captured.
addEventListener('keydown',event=>{
  if(event.code==='KeyR' && event.ctrlKey && event.altKey){
    event.preventDefault();
    document.querySelector('.lf-latest-chip')?.click();
  }
});
</script>""".replace("MODE", mode)
    return leaf_page("Editor continuity", body).replace("</head>", module + "</head>")


def editing_read(editor):
    return editor.evaluate(
        "el=>({value:el.value,focused:el.matches(':focus'),caret:[el.selectionStart,el.selectionEnd,el.selectionDirection]})"
    )


@pytest.mark.parametrize(
    "kind",
    [
        "authored",
        "composer",
        # The margin card's reply; the panel's open thread holds the same reply editor.
        "reply",
        "general",
        "first-message",
        "edit",
        # A document edit opened and selected in, with no words changed, so no draft.
        "edit-unchanged",
        "option",
    ],
)
def test_executable_revision_preserves_each_editor_identity(browser, serve, kind):
    page = open_page(browser, live_url(serve(editing_revision_source("overlay"))))
    if kind == "authored":
        editor = page.locator("#authored-draft")
    elif kind == "general":
        editor = page_comment(page)
    elif kind == "first-message":
        editor = page.locator("#seat-root > .lf-thread-seat > .lf-say leaf-text")
    elif kind in {"edit", "edit-unchanged"}:
        page.locator("#draft-root .lf-draft-body").click()
        editor = page.locator("#draft-root leaf-text")
    elif kind == "option":
        editor = page.locator("#options-root > .lf-another leaf-text")
    else:
        page.locator("#passage").click(click_count=3)
        page.keyboard.press("c")
        editor = page.locator(".lf-composer leaf-text")
        expect(editor).to_be_focused()
        if kind == "reply":
            write(editor, "A canonical root comment.")
            page.keyboard.press("Control+Enter")
            round_trip(page)
            page.keyboard.press("c")
            editor = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
            expect(editor).to_be_focused()
    words = "Kept words with a selected span."
    if kind == "authored":
        words = "\n".join([words] * 200)
    if kind != "edit-unchanged":
        write(editor, words)
    editor.evaluate("el=>el.setSelectionRange(5,10,'backward')")
    before = editing_read(editor)
    if kind == "authored":
        editor.evaluate("el=>el.scrollTop=20")
        before["scroll"] = editor.evaluate("el=>el.scrollTop")
        assert before["scroll"] > 0, "the native edit field must actually scroll"
    first_document = page.evaluate("performance.timeOrigin")
    page.evaluate(
        "window.__oldRendererRealm=true;dispatchEvent(new Event('renderer-lifetime-probe'))"
    )
    before_digest = page.locator('meta[name="lf-executable"]').get_attribute("content")
    stamp_page(
        serve.page_dir, editing_revision_source("page"), "Change the page executable"
    )
    told(page)
    if page.evaluate("performance.timeOrigin") == first_document:
        page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    after_digest = page.locator('meta[name="lf-executable"]').get_attribute("content")
    assert after_digest != before_digest
    assert page.evaluate("performance.timeOrigin") != first_document
    assert page.evaluate("window.__oldRendererRealm===undefined")
    page.evaluate("dispatchEvent(new Event('renderer-lifetime-probe'))")
    assert page.evaluate("window.__rendererLifetime.hits") == 1
    after = editing_read(editor) if editor.count() else None
    if kind == "authored":
        after["scroll"] = editor.evaluate("el=>el.scrollTop")
    assert after == before


def editing_mirror_source(mode):
    return editing_revision_source(mode).replace(
        "</main>",
        '<lf-thread-mirror id="first"></lf-thread-mirror><lf-thread-mirror id="second"></lf-thread-mirror></main>',
    )


def editing_reply_page(browser, serve, context=None):
    page = open_page(
        browser, live_url(serve(editing_revision_source("before"))), context=context
    )
    page.locator("#passage").click(click_count=3)
    page.keyboard.press("c")
    write(page.locator(".lf-composer leaf-text"), "An anchored root.")
    page.keyboard.press("Control+Enter")
    round_trip(page)
    page.keyboard.press("c")
    return page


def replace_editing_document(page, serve):
    birth = page.evaluate("performance.timeOrigin")
    stamp_page(
        serve.page_dir,
        editing_revision_source("after"),
        "Change real inline module body",
    )
    told(page)
    if page.evaluate("performance.timeOrigin") == birth:
        page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    assert page.evaluate("performance.timeOrigin") != birth


def test_executable_revision_preserves_non_editor_thread_standing(browser, serve):
    page = editing_reply_page(browser, serve)
    page.keyboard.press("Escape")
    captured = page.evaluate(
        "async()=> (await window.__lfRuntimeImport('/runtime/drafts.js')).captureDraftEditing()"
    )
    assert captured is None
    replace_editing_document(page, serve)
    expect(page.locator(".lf-composer leaf-text")).not_to_be_visible()
    assert (
        page.evaluate(
            "async()=> (await window.__lfRuntimeImport('/runtime/drafts.js')).captureDraftEditing()"
        )
        is None
    )


def test_live_executable_replacement_keeps_a_resolved_reply_session(browser, serve):
    """A live replacement continues actual editing; an ordinary reload only saves words."""
    page = editing_reply_page(browser, serve)
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    thread.locator(".lf-thread-summary").focus()
    editor = thread.locator("leaf-text")
    words = "Keep this actual editing session through the executable replacement."
    write(editor, words)
    editor.evaluate("el=>el.setSelectionRange(5,12,'backward')")
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    expect(editor).to_be_focused()
    before = editing_read(editor)
    context = page.evaluate(
        "async()=> (await window.__lfRuntimeImport('/runtime/drafts.js')).captureDraftEditing().context"
    )
    replace_editing_document(page, serve)
    expect(editor).to_be_focused()
    assert editing_read(editor) == before
    assert stored_draft_text(page, context) == words

    page.reload()
    wait_until_ready(page)
    expect(page.locator(".lf-thread-reply leaf-text")).not_to_be_visible()
    assert stored_draft_text(page, context) == words


@pytest.mark.parametrize("kind", ["edit", "first-message", "option"])
def test_in_place_revision_restores_the_current_generated_editor(browser, serve, kind):
    original = editing_revision_source("same-module")
    page = open_page(browser, live_url(serve(original)))
    if kind == "edit":
        page.locator("#draft-root .lf-draft-body").click()
        editor = page.locator("#draft-root leaf-text")
        revised = original.replace(
            "Standing editable text.", "A revised authored draft body."
        )
    elif kind == "first-message":
        editor = page.locator("#seat-root > .lf-thread-seat > .lf-say leaf-text")
        revised = original.replace("What should we do?", "What should we do next?")
    else:
        editor = page.locator("#options-root > .lf-another leaf-text")
        revised = original.replace("Initial choice", "A revised initial choice")
    write(editor, "An unsent edit keeps its exact selection.")
    editor.evaluate("el=>el.setSelectionRange(4,9,'backward')")
    before = editing_read(editor)
    editor.evaluate("el=>el.__outgoingEditor=true")
    birth = page.evaluate("performance.timeOrigin")
    stamp_page(serve.page_dir, revised, "Replace authored widget, retain executable")
    told(page)
    if (
        page.evaluate(
            "document.querySelector('.lf-latest-chip')?.getAttribute('hidden')"
        )
        is None
    ):
        page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    assert page.evaluate("performance.timeOrigin") == birth
    expect(editor).to_be_visible()
    if kind != "option":
        assert not editor.evaluate("el=>Boolean(el.__outgoingEditor)")
    expect(editor).to_be_focused()
    assert editing_read(editor) == before


def test_a_mechanical_revision_failure_leaves_accepted_publication_ready(
    browser, serve
):
    original = editing_revision_source("same-module")
    page = open_page(browser, live_url(serve(original)))
    page.locator("#draft-root .lf-draft-body").click()
    editor = page.locator("#draft-root leaf-text")
    write(editor, "The actual editor keeps these unsent words.")
    before = editing_read(editor)
    later_readings = []

    def hold_later_readings(route):
        later_readings.append(route)

    page.evaluate(
        "() => document.addEventListener('lf-page-interface',event=>{\n      event.detail.present(Promise.resolve().then(()=>{\n        const editor=document.querySelector('#draft-root leaf-text');\n        if(!editor)throw new Error('failure arrangement did not create its editor');\n        editor.setSelectionRange=()=>{window.__mechanicalCaretFailure=true;throw new Error('mechanical caret fixture failed')};\n      }));\n    },{once:true})"
    )
    stamp_page(
        serve.page_dir,
        original.replace("Standing editable text.", "New authored body."),
        "Install while generated editor has a failing caret",
    )
    told(page)
    before_reading = page.locator("body").get_attribute("data-lf-reading")
    page.route("**/api/state**", hold_later_readings)
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "installation-evidence",
            "kind": "comment",
            "author": "agent",
            "revision": 2,
            "text": "This fact joins the first installed publication.",
            "anchor": {"section": "passage"},
        },
    )
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/event")
            and response.request.method == "POST"
            and response.request.post_data_json.get("kind") == "error"
        )
    ):
        with page.expect_request("**/api/state**") as requested:
            page.keyboard.press("Control+Alt+r")
        first = next(
            route for route in later_readings if route.request == requested.value
        )
        answer = first.fetch()
        first_reading = answer.json()["reading"]
        assert first_reading != before_reading
        later_readings.remove(first)
        first.fulfill(response=answer)
    page.wait_for_function(
        "document.querySelector('meta[name=lf-revision][data-lf-runtime]')?.content==='2'"
        " && window.__mechanicalCaretFailure"
    )
    expect(editor).to_have_js_property("value", before["value"])
    expect(page.locator("body")).to_have_attribute("data-lf-reading", first_reading)
    page.wait_for_function(
        "async()=> (await window.__lfRuntimeImport('/runtime/semantic-state.js')).applicationPresented()"
    )
    errors = consume_browser_errors(page, "mechanical caret fixture failed")
    assert len(errors) == 1, errors
    assert "Revision continuity failed" in errors[0], errors
    page.wait_for_function(
        "async()=> (await window.__lfRuntimeImport('/runtime/semantic-state.js')).readApplication().document.revision===2"
    )
    reported = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "error"
    ]
    assert len(reported) == 1, reported
    assert reported[0]["text"].startswith(
        "Revision continuity failed: mechanical caret fixture failed\n"
    )

    # Error reporting may advance server freshness, but no later state answer may
    # rescue this reading: the first proved application must complete itself.
    page.unroute("**/api/state**", hold_later_readings)
    for route in later_readings:
        route.continue_()


def test_a_fresh_revision_caret_failure_does_not_strand_deferred_arrivals(
    browser, serve
):
    original = editing_revision_source("before")
    page = open_page(browser, live_url(serve(original)))
    page.locator("#draft-root .lf-draft-body").click()
    editor = page.locator("#draft-root leaf-text")
    write(editor, "Fresh words preserve exact original draft attempt.")
    editor.evaluate("el=>el.setSelectionRange(4,9,'backward')")
    revised = editing_revision_source("after").replace(
        "window.__rendererLifetime=",
        "import {afterPresentation,TEXT_FIELD} from '/runtime/widget-api.js';afterPresentation(()=>window.__deferredArrivalRan=true);document.addEventListener('lf-presentation',()=>window.__presentationDispatched=true);\nconst field=customElements.get(TEXT_FIELD).prototype;const setRange=field.setSelectionRange;\nfield.setSelectionRange=function(a,b,d){if(a===4&&b===9)throw new Error('fresh mechanical caret fixture failed');return setRange.call(this,a,b,d)};\nwindow.__rendererLifetime=",
    )
    stamp_page(serve.page_dir, revised, "Fresh executable with mechanical failure")
    told(page)
    page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    errors = consume_browser_errors(page, "fresh mechanical caret fixture failed")
    assert page.evaluate("Boolean(window.__presentationDispatched)")
    page.wait_for_function("window.__deferredArrivalRan===true")
    assert len(errors) == 1, errors
    assert "Revision continuity failed" in errors[0], errors


def test_first_draft_save_and_refusal_keep_the_local_editor_controls(browser, serve):
    """A failed first save retains exact source and usable controls without empty history."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "First draft refusal",
                "<h1>First draft refusal</h1>"
                '<lf-draft id="first-draft"><pre>Original words.</pre></lf-draft>'
                '<p id="following">The following passage stays where the reader found it.</p>',
            )
        ),
    )
    draft = page.locator("#first-draft")
    expect(draft.locator(".lf-draft-history")).to_have_count(0)
    draft_control(page, "edit", "first-draft").click()
    write(draft.locator("leaf-text"), "Changed words.")
    before = page.locator("#following").bounding_box()
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    draft_control(page, "save", "first-draft").click()
    holding(page, held, 1, "the refused first draft Save")
    expect(draft.locator(".lf-draft-body")).to_have_text("Changed words.")
    held[0].fulfill(
        status=400, json={"ok": False, "final": True, "error": "refused first edit"}
    )
    expect(draft.locator("leaf-text")).to_have_js_property("value", "Changed words.")
    expect(draft.locator(".lf-draft-body")).to_have_text("Original words.")
    expect(draft_control(page, "retry", "first-draft")).to_be_visible()
    expect(draft_control(page, "cancel", "first-draft")).to_be_visible()
    expect(draft.locator(".lf-draft-history")).to_have_count(0)
    assert page.locator("#following").bounding_box() == before
    consume_browser_errors(page, "400")


def test_draft_controls_survive_hiding_annotations_and_close_keeps_source(
    browser, serve
):
    """Editing operations stay in their box while the annotation layer is hidden."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Local draft controls",
                "<h1>Local draft controls</h1>"
                '<lf-draft id="local"><pre>Saved **source**.</pre></lf-draft>',
            )
        ),
    )
    draft = page.locator("#local")
    edit = draft_control(page, "edit", "local")
    edit.click()
    editor = draft.locator("leaf-text")
    write(editor, "Unsent `source`.")
    page.keyboard.press("Tab")
    expect(draft_control(page, "save", "local")).to_be_focused()
    page.keyboard.press("o")
    expect(page.locator("html")).to_have_attribute("data-lf-annotations", "hidden")
    expect(draft_control(page, "save", "local")).to_be_visible()
    expect(draft_control(page, "cancel", "local")).to_be_visible()
    draft_control(page, "close", "local").click()
    expect(editor).to_have_count(0)
    expect(edit).to_be_focused()
    edit.press("Enter")
    expect(editor).to_have_js_property("value", "Unsent `source`.")
    draft_control(page, "cancel", "local").click()
    expect(edit).to_be_focused()
    edit.click()
    expect(editor).to_have_js_property("value", "Saved **source**.")


def test_resume_writing_is_a_touch_action_and_does_not_steal_hint_addresses(
    browser, serve
):
    """A finger can resume the general box; gi never collides with generated hints."""
    source = leaf_page(
        "Resume targets",
        '<h1 id="heading">Resume targets</h1>'
        + "".join(
            f'<p><a id="link{index}" href="#heading">Jump {index}</a></p>'
            for index in range(30)
        ),
    )
    page = open_page(browser, serve(source))
    write(page_comment(page), "A page-wide draft")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-page-comment-card")).to_be_hidden()
    page.keyboard.press("g")
    expect(page.locator(".lf-go-to-hint[data-lf-hint-code]").first).to_be_visible()
    labels = page.locator(".lf-go-to-hint[data-lf-hint-code]").evaluate_all(
        "els => els.map(el => el.dataset.lfHintCode)"
    )
    assert labels and all("i" not in label for label in labels)
    # The page's draft resumes in the banner's page comment card.
    page.keyboard.press("i")
    card_box = page.locator(".lf-page-comment-card leaf-text")
    expect(card_box).to_be_focused()
    expect(card_box).to_have_js_property("value", "A page-wide draft")
    page.keyboard.press("Escape")
    context = browser.new_context(
        is_mobile=True, has_touch=True, viewport={"width": 390, "height": 844}
    )
    touch = open_page(browser, serve(LONG_PAGE), context=context)
    touch.keyboard.press("c")
    general = touch.locator(".lf-page-comment-card leaf-text")
    write(general, "A touch draft")
    touch.keyboard.press("Escape")
    touch.get_by_role("button", name="More page controls", exact=True).click()
    touch.get_by_role("button", name="Resume writing", exact=True).click()
    expect(general).to_be_focused()
    expect(general).to_have_js_property("value", "A touch draft")


@pytest.mark.parametrize("hidden_tab", [False, True])
def test_resume_writing_reveals_page_editor_from_a_covering_panel_and_keeps_back(
    browser, serve, hidden_tab
):
    """Resume exposes a hidden editor's place immediately and keeps the outgoing reading."""
    writing = (
        '<details id="fold" open><summary>Editable content</summary>'
        '<lf-draft id="editable"><pre>Initial words</pre></lf-draft></details>'
    )
    reading = (
        '<div style="height:2200px"></div><h2 id="elsewhere">Elsewhere</h2>'
        "<p>Keep this reading position.</p>"
    )
    body = writing + reading
    if hidden_tab:
        body = (
            '<lf-tabs id="views"><lf-tab id="writing-view" label="Writing">'
            + writing
            + '<div style="height:3300px"></div>'
            '</lf-tab><lf-tab id="reading-view" label="Reading">'
            + reading
            + "</lf-tab></lf-tabs>"
        )
    page = open_page(
        browser,
        serve(leaf_page("Resume travel", '<h1 id="top">Resume travel</h1>' + body)),
    )
    page.locator("#editable .lf-draft-body").click()
    edit = page.locator("#editable .lf-draft-edit")
    write(edit, "Last edit")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Escape")
    page.locator("#fold > summary").click()
    if hidden_tab:
        page.get_by_role("tab", name="Reading", exact=True).click()
    page.locator("#elsewhere").click()
    resized(page, 390, 844)
    scroll_settled(page)
    source_entry = page.evaluate("navigation.currentEntry.key")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    if hidden_tab:
        page.evaluate("""() => {
          const held = new Promise(resolve => { window.releaseResumeLayout = resolve; });
          document.querySelector('#views').addEventListener('lf-layout', event => {
            event.detail.present(held);
            window.resumeLayoutStarted = true;
          }, {once: true});
        }""")
        try:
            page.keyboard.press("g")
            page.keyboard.press("i")
            page.wait_for_function("window.resumeLayoutStarted === true")
            one_frame(page)
            expect(page.locator("#writing-view")).to_be_visible()
            first_view = page.locator("#editable").evaluate("""async draft => {
              const {landingBand} = await window.__lfRuntimeImport('/runtime/geometry.js');
              const rect = draft.getBoundingClientRect();
              const band = landingBand(document.scrollingElement);
              return {top: rect.top, bottom: rect.bottom, low: band.top, high: band.bottom};
            }""")
            assert first_view["top"] >= first_view["low"], first_view
            assert first_view["bottom"] <= first_view["high"], first_view
        finally:
            page.evaluate("releaseResumeLayout()")
    else:
        page.keyboard.press("g")
        page.keyboard.press("i")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    expect(edit).to_be_focused()
    expect(edit).to_be_in_viewport()
    expect(edit).to_have_js_property("value", "Last edit")
    assert edit.evaluate("el => el.selectionStart") == 1
    page.go_back()
    scroll_settled(page)
    expect(page.locator("#elsewhere")).to_be_in_viewport()
    assert page.evaluate("navigation.currentEntry.key") == source_entry
    # Clearing every word still records a real editor destination.
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(edit).to_be_focused()
    edit.press("ControlOrMeta+a")
    edit.press("Backspace")
    page.keyboard.press("Escape")
    if hidden_tab:
        page.get_by_role("tab", name="Reading", exact=True).click()
    page.locator("#elsewhere").click()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(edit).to_be_focused()
    expect(edit).to_have_js_property("value", "")


@pytest.mark.parametrize("keyboard", ["desktop", "touch", "android"])
def test_composer_return_edits_or_sends_according_to_its_keyboard(
    browser, serve, keyboard
):
    """Mobile Return keeps a source newline, including Android's EditContext path."""
    options = {
        "viewport": {"width": 360 if keyboard != "desktop" else 1280, "height": 732},
        "is_mobile": keyboard != "desktop",
        "has_touch": keyboard != "desktop",
    }
    if keyboard == "android":
        options["user_agent"] = (
            "Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/155.0.8059.12 Mobile Safari/537.36"
        )
    context = browser.new_context(**options)
    page = open_page(browser, serve(LONG_PAGE), context=context)
    editor = page_comment(page)
    page.keyboard.type("First sentence.")
    editor.press("Shift+Enter" if keyboard == "desktop" else "Enter")
    expect(editor).to_have_js_property("value", "First sentence.\n")
    page.keyboard.type("Second sentence.")
    exact = "First sentence.\nSecond sentence."
    expect(editor).to_have_js_property("value", exact)
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    with sending(page, "the complete multiline comment"):
        editor.press("Enter" if keyboard == "desktop" else "ControlOrMeta+Enter")
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [exact]


@pytest.mark.parametrize("android", [False, True])
def test_document_edit_enter_adds_a_line_and_modified_enter_saves_exact_source(
    browser, serve, android
):
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/155.0.8059.12 Mobile Safari/537.36"
        )
        if android
        else None,
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Markdown source editing",
                "<h1>Markdown source editing</h1>"
                '<lf-draft id="source"><pre>Original **source**.</pre></lf-draft>',
            )
        ),
        context=context,
    )
    draft = page.locator("#source")
    draft_control(page, "edit", "source").click()
    editor = draft.locator("leaf-text")
    write(editor, "First **paragraph**.")
    editor.press("End")
    editor.press("Enter")
    expect(editor).to_have_js_property("value", "First **paragraph**.\n")
    editor.press("Enter")
    expect(editor).to_have_js_property("value", "First **paragraph**.\n\n")
    page.keyboard.insert_text("Second `paragraph`.")
    exact = "First **paragraph**.\n\nSecond `paragraph`."
    expect(editor).to_have_js_property("value", exact)
    assert not [
        e for e in events_model.read_events(serve.page_dir) if e.get("action") == "edit"
    ]
    with sending(page, "the exact source edit"):
        editor.press("ControlOrMeta+Enter")
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body > p")).to_have_count(2)
    expect(draft.locator(".lf-draft-body strong")).to_have_text("paragraph")
    expect(draft.locator(".lf-draft-body code")).to_have_text("paragraph")
    edits = [
        e for e in events_model.read_events(serve.page_dir) if e.get("action") == "edit"
    ]
    assert [e["detail"]["value"] for e in edits] == [exact]


def test_draft_comparison_detects_format_changes_but_not_the_same_standing_edit(
    browser, serve
):
    first = leaf_page(
        "Markdown revision comparison",
        "<h1>Markdown revision comparison</h1>"
        '<lf-draft id="source"><pre>Keep **these** words.</pre></lf-draft>'
        '<p id="following">Following passage.</p>',
    )
    url = serve(first)
    _publish(
        serve.page_dir, 2, first.replace("**these**", "*these*"), "Change emphasis"
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    compare_with(page)
    expect(page.locator("#source")).to_have_class(re.compile(r"lf-ins-block"))
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 2,
            "widget": "source",
            "action": "edit",
            "detail": {"value": "Standing **edit**."},
        },
    )
    _publish(
        serve.page_dir,
        3,
        first.replace("**these**", "*these*").replace(
            "Following passage.", "Revised following passage."
        ),
        "Revise following prose",
    )
    page.goto(url.replace("v1.html", "v3.html"))
    wait_until_ready(page)
    compare_with(page)
    expect(page.locator("#following")).to_have_class(re.compile(r"lf-ins-block"))
    expect(page.locator("#source")).not_to_have_class(re.compile(r"lf-ins-block"))
    expect(page.locator("#source .lf-draft-body strong")).to_have_text("edit")


def test_a_draft_button_keeps_its_target_when_pointerdown_focuses_it(browser, serve):
    """Raw pointer down must not move the button before the matching up arrives. Either
    edge detects a button that moves under the press, so each action, pressed in turn
    on one draft, takes one."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Stable draft",
                '<h1>Release note</h1><lf-draft id="note"><pre>Keep `this` note.</pre></lf-draft>',
            )
        ),
    )
    draft = page.locator("#note")
    # Save keeps its words; cancel and close discard theirs.
    saved = "Keep this note."
    for action, edge in (
        ("edit", "left"),
        ("save", "right"),
        ("cancel", "left"),
        ("close", "right"),
    ):
        if action != "edit":
            draft_control(page, "edit", "note").click()
            write(
                draft.locator("leaf-text"),
                f"Keep `the corrected` note before {action}.",
            )
        page.get_by_role("heading", name="Release note").click()
        rendered(page)
        controls = draft.locator("[data-lf-draft-action]:visible")
        before = controls.evaluate_all(
            "ns => ns.map(n=>({action:n.dataset.lfDraftAction,box:n.getBoundingClientRect().toJSON()}))"
        )
        button = draft_control(page, action, "note")
        box = button.bounding_box()
        x = box["x"] + (2 if edge == "left" else box["width"] - 2)
        page.mouse.move(x, box["y"] + box["height"] / 2)
        page.mouse.down()
        expect(button).to_be_focused()
        rendered(page)
        assert (
            controls.evaluate_all(
                "ns => ns.map(n=>({action:n.dataset.lfDraftAction,box:n.getBoundingClientRect().toJSON()}))"
            )
            == before
        ), action
        page.mouse.up()
        if action == "edit":
            expect(draft.locator("leaf-text")).to_be_focused()
            page.keyboard.press("Escape")
            expect(draft.locator("leaf-text")).to_have_count(0)
        else:
            expect(draft.locator("leaf-text")).to_have_count(0)
            round_trip(page)
        if action == "save":
            saved = "Keep the corrected note before save."
        expect(draft.locator(".lf-draft-body")).to_have_text(saved)
        round_trip(page)
        edits = [
            e
            for e in events_model.read_events(serve.page_dir)
            if e.get("action") == "edit"
        ]
        assert len(edits) == (0 if saved == "Keep this note." else 1), action


def test_a_delayed_draft_close_yields_to_a_newer_page_selection(browser, serve):
    """Returning editor focus cannot overwrite a real gesture made before that handoff."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Close focus",
                '<p id="reading">Another passage for the reader to select.</p>'
                '<lf-draft id="local"><pre>Editable source.</pre></lf-draft>',
            )
        ),
        init_script="""(() => {
          const frame=requestAnimationFrame.bind(window);
          window.heldFrames=[];window.holdFrames=false;
          window.requestAnimationFrame=callback=>frame(now=>{
            if(window.holdFrames)heldFrames.push(callback);else callback(now);
          });
          window.releaseFrames=()=>{
            window.holdFrames=false;
            const callbacks=heldFrames.splice(0);
            frame(now=>callbacks.forEach(callback=>callback(now)));
          };
        })();""",
    )
    draft_control(page, "edit", "local").click()
    expect(page.locator("#local leaf-text")).to_be_focused()
    rendered(page)
    page.evaluate("""async()=>{
      const {observeQueuedWork}=await window.__lfRuntimeImport('/runtime/queued-work.js');
      window.closeJobs=new Set();window.captureClose=true;
      window.stopCloseObserver=observeQueuedWork((phase,job)=>{
        if(phase==='enqueue'&&captureClose)closeJobs.add(job);
        if(phase==='finish'||phase==='cancel')closeJobs.delete(job);
      });
      window.holdFrames=true;
    }""")
    page.keyboard.press("Escape")
    page.evaluate("window.captureClose=false")
    expect(page.locator("#local leaf-text")).to_have_count(0)
    page.wait_for_function("heldFrames.length>0", polling=20)
    assert page.evaluate("closeJobs.size") > 0
    start, end = page.locator("#reading").evaluate("""p=>[2,24].map(at=>{
      const range=new Range();range.setStart(p.firstChild,at);range.setEnd(p.firstChild,at+1);
      const box=range.getBoundingClientRect();return [box.left+0.01,box.top+box.height/2];
    })""")
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=5)
    page.mouse.up()
    selected = page.evaluate("getSelection().toString()")
    assert selected
    assert page.evaluate("document.activeElement===document.body")
    page.evaluate("releaseFrames()")
    page.wait_for_function("closeJobs.size===0", polling=20)
    rendered(page)
    assert page.evaluate("document.activeElement===document.body")
    # The shared selection owner may expand partial words; the newer passage remains.
    assert selected in page.evaluate("getSelection().toString()")
    page.evaluate("stopCloseObserver()")
