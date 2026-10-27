"""Where the reader's place stays as the window changes width, a script scrolls, content
settles or grows, and the reader pages through a landed section."""

import pytest
from playwright.sync_api import expect
from render_harness import (
    LANDING_TOP,
    ROOT,
    leaf_page,
    open_page,
    resized,
    scroll_settled,
)

from leaf.render_checks import one_frame, rendered

pytestmark = pytest.mark.shifts_unsurveyed


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
    """A pane carries visible focus across scroll behavior changes without pulling back old focus."""

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
          const {seenRect, shownBox} = await window.__lfCheckApi();
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
    # the same element focused, and the next scroll behavior must retain that new reading.
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
def test_a_page_keeps_its_place_as_the_window_changes_width(browser, serve, region):
    """The words above the line the reader landed on rewrap as the window narrows; the
    line stays where it stood below the landing band, in a document as in a pane the
    page carries, and back again when the window widens. A control the reader has
    focused at the top of the page, where the browser anchors nothing, stays in view as
    the words above it rewrap."""
    lines = "".join(
        f'<p id="line-{n}">Line {n} of the incident, long enough to rewrap when the '
        "window narrows to a phone.</p>"
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
      const {landingBand} = await window.__lfCheckApi();
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


def test_a_page_read_from_its_top_stays_at_its_top_as_the_window_narrows(
    browser, serve
):
    """A page the reader has not scrolled is read from its top. A wide window holds its
    header in the column beside the first section, and a narrow one drops the header
    into the flow above it; the page stays at its top with the title in view, rather
    than scrolling to keep that section's first line where it stood. A page landed
    partway down still keeps the line it was read at across the same narrowing."""
    page = open_page(browser, serve(ROOT / "tests/fixtures/pages/root-parts.html"))
    title = page.locator("main > header h1")
    heading = (
        "async () => document.querySelector('#part-plan-stages h2')"
        f".getBoundingClientRect().top - {LANDING_TOP}"
    )
    resized(page, 1200, 800)
    rendered(page)
    assert page.evaluate("document.scrollingElement.scrollTop") == 0
    resized(page, 440, 800)
    rendered(page)
    assert page.evaluate("document.scrollingElement.scrollTop") == 0
    expect(title).to_be_in_viewport(ratio=1)

    resized(page, 1200, 800)
    rendered(page)
    page.evaluate("location.hash = 'part-plan-stages'")
    rendered(page)
    landed = page.evaluate(heading)
    assert page.evaluate("document.scrollingElement.scrollTop") > 0
    resized(page, 440, 800)
    rendered(page)
    assert page.evaluate(heading) == pytest.approx(landed, abs=2)


@pytest.mark.parametrize("wheel", [False, True], ids=["landed", "wheel-over-pane"])
def test_a_heading_above_a_flowing_pane_keeps_its_place_as_the_window_changes_width(
    browser, serve, wheel
):
    """The reader landed on a section's heading; a pane the page carries starts lower in
    the window. Text between them rewraps as the window changes width, so the pane's own
    first line and the heading cannot both keep their distances. The heading is what the
    reader reads, so it stays where it stood below the landing band, at each width and
    back, even after they turned the wheel with the pointer over the pane's words, as a
    finger scrolling a phone over a queue does."""
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
      const {landingBand} = await window.__lfCheckApi();
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


def test_a_script_scroll_moves_a_held_page(browser, serve, subtests):
    """After a width change the page holds the reader's place and applies it again as
    the layout settles. A page script that scrolls, before the restore has landed, as it
    lands, or after, with the layout growing around it or not, has moved the page: the
    page keeps that scroll through the next layout change, and the next width change
    starts from where the script left it, not from the held place.

    Each move needs a page of its own, held fresh; the control they are measured
    against is the same for every move, so it is read once."""
    scrolled = "document.scrollingElement.scrollTop"
    # Where the restore alone leaves the page, with no script.
    control = held_page(browser, serve)
    resized(control, 390, 800)
    rendered(control)
    restored = control.evaluate(scrolled)
    control.context.close()

    for move, (when, by, script) in HELD_PAGE_MOVES.items():
        with subtests.test(move=move):
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
            assert moved > restored + by - 100, (
                f"the script's scroll was undone ({moved})"
            )
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
            page.context.close()


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
      const {registerReadingRegion} = await window.__lfWidgetApi();
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


def reading_section_page(title, before=""):
    """A page whose `#read` section, a heading over forty paragraphs, stands below
    thirty lead paragraphs, all long enough to rewrap at a phone's width."""
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
    return leaf_page(
        title,
        f'{before}{lead}<section id="read"><h2>The section the reader reads</h2>'
        f"{body}</section>",
    )


# Where `#read`'s heading stands below the landing band.
READ_HEADING = """() => document.querySelector('#read h2').getBoundingClientRect().top
  - (parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop) || 0)"""
# In one frame, content grows above `#read`, which anchoring answers, and a script
# scrolls on.
GROW_ABOVE_AND_SCROLL = """() => new Promise(done => requestAnimationFrame(() => {
  const late = document.createElement('div');
  late.style.height = '300px';
  const section = document.getElementById('read');
  section.parentNode.insertBefore(late, section);
  document.scrollingElement.scrollBy(0, 400);
  done();
}))"""


def test_a_script_scroll_as_content_grows_above_ends_the_hold(browser, serve):
    """Once the layout a width change restored the reader's place in has settled, one
    frame grows content above the reader, which anchoring answers, and a script scrolls
    on. The box and its landmark moved by different distances, which reads as layout's
    only while the shift's layout settles; after that it is a move someone made, so the
    next width change starts from where the script left the page, not from the held
    place."""
    page = open_page(browser, serve(reading_section_page("Content grows above")))
    resized(page, 390, 800)
    rendered(page)
    page.evaluate("location.hash = 'read'")
    rendered(page)
    box = page.locator("#read p").first.bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 5)
    page.mouse.wheel(0, 8)
    scroll_settled(page)
    rendered(page)
    resized(page, 1200, 800)
    rendered(page)
    held = page.evaluate(READ_HEADING)
    page.evaluate(GROW_ABOVE_AND_SCROLL)
    scroll_settled(page)
    rendered(page)
    assert page.evaluate(READ_HEADING) < held - 300, "the script's scroll was undone"
    resized(page, 390, 800)
    rendered(page)
    assert page.evaluate(READ_HEADING) < held - 300, "the held place came back"


def test_a_page_that_never_settles_lets_the_held_place_go_after_a_while(browser, serve):
    """A chart whose box breathes forever keeps the page's rendering from ever reading
    settled. A width change restores the reader's place and holds it while the layout
    settles, but no longer than a moment: well after, a script that scrolls as content
    grows above the reader moved the page, and the next width change starts from
    there rather than putting the held place back."""
    source = reading_section_page(
        "A page that never settles",
        "<style>@keyframes breathe { from { width: 60%; } to { width: 100%; } }"
        " .breathe #breathing { animation: breathe 3s linear infinite alternate; }"
        "</style>"
        '<div id="breathing"><lf-chart id="spin" data-height="120"><pre>\n'
        '{ ariaLabel: "Two teams", marks: [Plot.barY([{team: "a", n: 12},'
        ' {team: "b", n: 19}], {x: "team", y: "n"})] }\n</pre></lf-chart></div>',
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
    held = page.evaluate(READ_HEADING)
    page.wait_for_timeout(1500)
    page.evaluate(GROW_ABOVE_AND_SCROLL)
    settle()
    assert page.evaluate(READ_HEADING) < held - 300, "the script's scroll was undone"
    resized(page, 390, 800)
    settle()
    assert page.evaluate(READ_HEADING) < held - 300, "the held place came back"


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
