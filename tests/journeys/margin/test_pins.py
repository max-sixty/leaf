"""Tests scheduled by the measured cost of their boundary."""

import re

import pytest
from browser.margin import _comment_on
from browser.margin.test_pins import (
    ROWS,
    SEATS,
)
from playwright.sync_api import expect
from render_cases_widgets import RAIL_BAND_PAGE
from render_harness import (
    CHROME_ROOT,
    RELEASE_FOCUS,
    leaf_page,
    margins_laid_out,
    open_page,
    panel_field,
    press_visible,
    resized,
)

from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_hiding_annotations_takes_down_what_is_drawn_over_the_page(browser, serve):
    """`g H` hides the annotation layer: every pin, the controls one holds included, and
    the durable marks, while the rail and what stands in it stay, since the rail covers
    nothing. Nothing in the layer takes up room, so no box of the page moves. A press on
    a passage whose mark is hidden opens nothing, and the choice is the tab's, so a
    reload keeps it. An obligation walk reveals the pin it lands on for as long as the
    user stands there.

    Hidden annotations leave a commented page looking as if nobody commented, and the
    hidden layer comes back with a reload, after its notice has passed. So while it is
    hidden the panel's field says so, ahead of the status or after a stance's name,
    until `g H` shows the layer again."""
    page = open_page(
        browser,
        serve(
            RAIL_BAND_PAGE,
            events=[_comment_on("gap", quote="Prose far enough below the changes")],
        ),
    )
    resized(page, 1440, 900)
    margins_laid_out(page)
    pin = page.locator('.lf-margin-cluster[data-lf-margin-for="sug-card"]')
    rail = page.locator('.lf-margin-cluster[data-lf-margin-for="sug-copy"]')
    expect(pin).to_have_attribute("data-lf-place", "pin")
    expect(rail).to_have_attribute("data-lf-place", "rail")
    boxes = """() => [...document.querySelectorAll('main, main *')].map(el => {
      const b = el.getBoundingClientRect();
      return [b.left, b.top, b.width, b.height].map(Math.round).join(',');
    })"""
    # The words the durable marks paint, which hiding the layer registers empty.
    marked = """() => [...(CSS.highlights.get('lf-mark') ?? [])]
      .map(range => range.toString()).join(' ')"""
    passage = "Prose far enough below the changes"
    page.wait_for_function(f"() => ({marked})() === {passage!r}")
    before = page.evaluate(boxes)

    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect(page.locator(CHROME_ROOT)).to_have_attribute(
        "data-lf-annotations-hidden", ""
    )
    expect(pin).to_be_hidden()
    expect(rail).to_be_visible()
    assert page.evaluate(marked) == ""
    margins_laid_out(page)
    assert page.evaluate(boxes) == before, "hiding the annotations moved the page"

    page.locator("#gap").click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    page.reload()
    page.wait_for_selector("body[data-lf-presented]")
    margins_laid_out(page)
    expect(page.locator(CHROME_ROOT)).to_have_attribute(
        "data-lf-annotations-hidden", ""
    )
    expect(pin).to_be_hidden()
    assert page.evaluate(marked) == ""

    field = panel_field(page)
    expect(field).to_have_attribute("data-lf-says", "status")
    expect(field).to_have_attribute(
        "placeholder", re.compile(r"^Annotations hidden · \S")
    )
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("w")
    expect(field).to_have_attribute(
        "placeholder", re.compile(r"^Annotations hidden · \S")
    )
    expect(page.locator(".lf-fp-mode")).to_have_text("Draw")
    page.keyboard.press("Escape")
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")

    # An explicit obligation walk reveals its pin until the user leaves that obligation.
    # The passage follows both obligations, so a step back lands on the last one.
    page.locator("#gap").click()
    page.keyboard.press("Shift+m")
    expect(page.locator("#sug-card")).to_be_focused()
    rendered(page)
    expect(pin).to_be_visible()
    page.evaluate(RELEASE_FOCUS)
    expect(pin).to_be_hidden()
    expect(page.locator(CHROME_ROOT)).to_have_attribute(
        "data-lf-annotations-hidden", ""
    )

    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect(pin).to_be_visible()
    assert page.evaluate(marked) == passage
    expect(page.locator(CHROME_ROOT)).not_to_have_attribute(
        "data-lf-annotations-hidden", re.compile(".*")
    )
    # The notice saying the annotations are shown passes, and the status stands alone.
    expect(field).to_have_attribute("data-lf-says", "status")
    expect(field).not_to_have_attribute("placeholder", re.compile("Annotations"))


def test_a_pass_for_a_change_to_the_rows_seats_them_as_a_whole_pass_would(
    browser, serve
):
    """A change to the margin's rows alone runs a pass that reads only the rows it
    changes and seats the rest from what an earlier pass read (margin-layout.js,
    `seatings`), and a box changing size reads again only the rows whose band of the
    page it reaches or whose neighbours it moved. Through any run of such changes every
    row stands where a pass over the whole margin would stand it: after a hold that
    moved a row ends, after a face grows in the task that draws it, after a row leaves,
    after a pane beside a pin scrolls, after a transition beside a pin ends, after a
    scroll and a sent comment, after a resolve, after words above the rows grow, after
    words come into a pin's seat and leave it, and after words above a pin in one column
    grow and carry it level with a button the other column holds where it was."""
    lines = "".join(f'<p id="line-{n}" style="margin:0">Line {n}.</p>' for n in (1, 2))
    options = "".join(
        f'<lf-option id="o-{i}" label="Option {i}"><strong>Option {i}</strong> a short description.</lf-option>'
        for i in (1, 2, 3)
    )
    # A pane whose words reach its right edge only once it is scrolled to its foot, and
    # under it a paragraph whose pin stands above it, over the pane's empty edge.
    long = (
        '<p style="margin:0;text-align:right">Long words in the pane that reach across'
        " to its right edge, and then some more words to be sure.</p>"
    )
    beside = (
        'style="margin:0;text-align:right">A paragraph whose words run right across'
        " its line to the far edge, so the seat in its corner covers words, and then on"
        " for a second line of words.</p>"
    )
    pane = (
        '<div id="pane" style="height:84px;overflow:auto">'
        + '<p style="margin:0">x</p>' * 8
        + long * 6
        + f'</div><p id="t" {beside}'
    )
    # A block whose words slide in to its right edge as a transition ends, into the
    # empty room the pins beside it stand in.
    slide = (
        '<div id="slide" class="away"><p style="margin:0">x</p>'
        f'{long}</div><p id="v" {beside}<p id="tail">A last paragraph.</p>'
    )
    body = (
        '<article id="document"><h1>Seats</h1>'
        '<p id="intro">Words before the lines, long enough for a paragraph the margin'
        " reads around as it seats its rows.</p>"
        f'{lines}<p id="after">Words after the lines, long enough for another'
        " paragraph.</p>"
        # A box floated over the right end of a line whose pin stands there, with no
        # words in it yet.
        '<div id="float" style="float:right;width:240px">\u200b</div>'
        '<p id="below" style="margin:0">Words under it.</p>'
        # A paragraph in one column, and in the other column a button the test places
        # where that paragraph's pin will stand once words above it grow.
        '<div style="display:grid;grid-template-columns:1fr 1fr;align-items:start">'
        '<div><p id="grow">Short.</p><div style="height:200px"></div>'
        '<p id="gridded">Words in the column.</p></div>'
        '<div id="right"><button id="neighbour" style="position:relative">A button'
        "</button></div></div>"
        '<section><h2 id="heading">A question</h2><p id="words">Some words about it.</p>'
        '<lf-group id="q" label="Which one?"><h3 id="question">Which one?</h3>'
        f'<lf-options id="o" multiple>{options}</lf-options></lf-group></section>'
        + "".join(
            f'<section><h2>Section {n}</h2><p id="far-{n}">Words about section {n},'
            " enough for a line of reading.</p></section>"
            for n in range(1, 9)
        )
        + f"{pane}{slide}</article>"
    )
    motion = (
        "<style>#slide { transition: transform 150ms linear }"
        " #slide.away { transform: translateX(-110%) }</style>"
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = open_page(
        browser,
        serve(leaf_page("Seats", body, head=motion, layout=None)),
        context=context,
    )
    differ = {}

    def settled():
        """Wait for the passes a change brings to end, not for one a layout forces."""
        page.evaluate("""() => new Promise((resolve) => {
          let quiet;
          const wait = () => { clearTimeout(quiet); quiet = setTimeout(done, 300); };
          const done = () => {
            document.removeEventListener('lf-margin-layout', wait);
            resolve();
          };
          document.addEventListener('lf-margin-layout', wait);
          wait();
        })""")

    def compare(step):
        settled()
        seats = page.evaluate(SEATS)
        margins_laid_out(page)
        whole = page.evaluate(SEATS)
        if seats != whole:
            differ[step] = [
                pair for pair in zip(seats, whole, strict=True) if pair[0] != pair[1]
            ]

    def rows(keys, entries=1, immediate=False):
        page.evaluate(ROWS, {"keys": keys, "entries": entries, "immediate": immediate})

    rows(["line-1", "line-2", "heading", "words", "question", "below"])
    rows(["gridded"], entries=2)
    rows(["t", "v"], entries=2)
    settled()
    margins_laid_out(page)

    # The second line's row held under the pointer while the first line moves onto it,
    # so the pass that move brings stands the first line's row clear of the held one;
    # then let go, and a row added beside rows the margin already watches brings a pass
    # for the rows alone.
    held = page.locator('[data-lf-margin-for="line-2"]').bounding_box()
    page.mouse.move(held["x"] + held["width"] / 2, held["y"] + held["height"] / 2)
    page.evaluate(
        "() => Object.assign(document.getElementById('line-1').style,"
        " {position: 'relative', top: '6px'})"
    )
    settled()
    page.mouse.move(4, 4)
    settled()
    rows(["after"])
    compare("a hold ends")

    # A face grown and laid out in one task, as an immediate update flushes it.
    rows(["question"], entries=3, immediate=True)
    compare("a face grows at once")

    page.evaluate("() => window.seatRows.get('line-1').registration.unregister()")
    compare("a row leaves")

    # The pane scrolled to its foot puts words under the pin above the paragraph.
    page.evaluate("() => { document.getElementById('pane').scrollTop = 10000; }")
    settled()
    rows(["intro"])
    compare("a pane beside a pin scrolls")

    page.evaluate("""() => new Promise((resolve) => {
      const slide = document.getElementById('slide');
      slide.addEventListener('transitionend', resolve, {once: true});
      slide.classList.remove('away');
    })""")
    settled()
    rows(["tail"])
    compare("a transition beside a pin ends")

    page.evaluate("""() => {
      window.scrollBy({top: 240, behavior: 'instant'});
      const words = document.getElementById('far-4').firstChild;
      getSelection().setBaseAndExtent(words, 0, words, 24);
    }""")
    page.keyboard.press("c")
    page.locator(".lf-composer leaf-text").focus()
    page.keyboard.insert_text("Why this section?")
    page.keyboard.press("ControlOrMeta+Enter")
    resolve = page.locator(".lf-margin-preview .lf-resolve")
    expect(resolve).to_be_visible()
    rendered(page)
    compare("a scroll and a sent comment")

    press_visible(page, resolve)
    rendered(page)
    compare("a resolve")

    # Words rewritten in place, which the page's observers hear only as the boxes the
    # margin watches changing size: the rows past them move, and those whose band of the
    # page they reach are read again.
    def rewrite(key, words):
        page.evaluate(
            "([key, words]) => { document.getElementById(key).firstChild.data = words; }",
            [key, words],
        )

    more = " And many more words, long enough to wrap the paragraph onto more lines."
    rewrite("intro", "Words before the lines." + more * 4)
    compare("a paragraph above the rows grows")
    rewrite("float", "Words floated beside the line." + more)
    compare("words come into a pin's seat")
    rewrite("float", "\u200b")
    compare("they leave it")
    # Where the column's pin stands once the words above it grow, and only there, the
    # other column holds a button, so that pin seats clear of it there; then the words
    # shrink and grow again, carrying the pin back down to the button's level.
    grown = "Words that wrap the column's line. " * 12
    rewrite("grow", grown)
    settled()
    page.evaluate(
        """() => {
          const pin = document.querySelector('[data-lf-margin-for="gridded"]');
          const right = document.getElementById('right');
          const column = right.getBoundingClientRect();
          const at = pin.getBoundingClientRect();
          right.style.marginTop = `${at.top - column.top - 4}px`;
          Object.assign(document.getElementById('neighbour').style, {
            left: `${at.left - column.left - 12}px`,
            width: `${at.width + 24}px`, height: `${at.height + 8}px`,
          });
        }"""
    )
    compare("a button comes beside a column's pin")
    rewrite("grow", "Short.")
    compare("the words above the column's pin shrink")
    rewrite("grow", grown)
    compare("they grow, carrying the pin to the other column's button")
    assert differ == {}, differ
