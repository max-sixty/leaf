"""Where a margin pin stands over the content, how it folds and unfolds its actions,
keeps clear of the page's controls, and hides with the annotation layer."""

import re
from math import hypot

import pytest
from interact_support import append_carried_log_record
from leaf_dev.commands import pins as pin_cases
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE
from render_cases_widgets import RAIL_BAND_PAGE
from render_harness import (
    EXAMPLES,
    PANEL,
    RELEASE_FOCUS,
    leaf_page,
    margins_laid_out,
    open_page,
    painted_words,
    pane_scroll_behavior,
    panel_control,
    panel_field,
    press_visible,
    regions_side_by_side,
    resized,
    write,
)

from browser.margin import (
    _comment_on,
)
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_pin_on_one_shape_of_a_drawing_stands_on_that_shape(browser, serve):
    """A shape inside an SVG drawing has no CSS box, so its row anchors through the
    drawing; as a pin it still stands at the shape's own top-right corner, not at the
    drawing's edge beside another shape."""
    shapes = "".join(
        f'<g id="{name}"><text x="{x}" y="20">{name}</text>'
        f'<rect x="{x}" y="30" width="240" height="160"/></g>'
        for name, x in [("left", 20), ("middle", 380), ("right", 740)]
    )
    source = leaf_page(
        "a drawing's parts",
        '<div><h1 id="t">Parts</h1><figure id="fig" data-width="wide">'
        '<svg class="drawing" viewBox="0 0 1000 200" role="img">'
        f"<title>Three shapes</title>{shapes}</svg></figure></div>",
        layout="sidebar",
    )
    page = open_page(
        browser, serve(source, events=[_comment_on("left"), _comment_on("right")])
    )
    resized(page, 1440, 900)
    margins_laid_out(page)
    for name in ("left", "right"):
        row = page.locator(f'.lf-margin-cluster[data-lf-margin-for="{name}"]')
        expect(row).to_have_attribute("data-lf-place", "pin")
        row_box = row.bounding_box()
        shape = page.locator(f"#{name}").bounding_box()
        # Beside the left shape's corner; inside the right one's, since the drawing
        # clips what stands past its edge and the shape's label fills the room above.
        right = shape["x"] + shape["width"]
        assert shape["x"] < row_box["x"] <= right + 8, (name, row_box, shape)
        assert row_box["x"] + row_box["width"] > right - 40, (name, row_box, shape)
        assert row_box["y"] == pytest.approx(shape["y"], abs=8), (name, row_box, shape)


def test_a_pin_stands_by_its_run_of_text_rather_than_over_it(browser, serve):
    """A pin is an overlay, so it finds room rather than making it: a suggestion's
    Accept and Reject stood inside the corner of its run and covered the words being
    decided. With room by the run, they stand there, touching it, over none of the
    paragraph's words."""
    source = leaf_page(
        "a suggestion's pin",
        '<div><h1 id="t">Notes</h1><p id="p">The status column is the '
        '<lf-suggestion id="s"><lf-old>release\'s only visual change</lf-old>'
        "<lf-new>only change to the run list</lf-new></lf-suggestion>.</p>"
        "<p>The next paragraph starts a new subject.</p></div>",
        layout="sidebar",
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    margins_laid_out(page)
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="s"]')
    expect(row).to_have_attribute("data-lf-place", "pin")
    reading = page.evaluate(
        """() => {
          const edges = ({left, top, right, bottom}) => ({left, top, right, bottom});
          const entries = [...document.querySelectorAll(
            '[data-lf-margin-for="s"] .lf-margin-entry')]
            .filter((entry) => entry.checkVisibility())
            .map((entry) => edges(entry.getBoundingClientRect()));
          return {entries,
            parts: [...document.getElementById('s').getClientRects()].map(edges)};
        }"""
    )
    reading["words"] = painted_words(page, "#p")
    # Accept and Reject.
    assert len(reading["entries"]) == 2, reading["entries"]
    for entry in reading["entries"]:
        covered = [
            word
            for word in reading["words"]
            if word["left"] < entry["right"]
            and entry["left"] < word["right"]
            and word["top"] < entry["bottom"]
            and entry["top"] < word["bottom"]
        ]
        assert not covered, (entry, covered)
    pair = {
        "left": min(entry["left"] for entry in reading["entries"]),
        "top": min(entry["top"] for entry in reading["entries"]),
        "right": max(entry["right"] for entry in reading["entries"]),
        "bottom": max(entry["bottom"] for entry in reading["entries"]),
    }
    assert pin_distance(pair, reading["parts"]) <= 12, (pair, reading["parts"])


PIN_READING = """async (id) => {
  const {shownParts} = await window.__lfCheckApi();
  const edges = ({left, top, right, bottom}) => ({left, top, right, bottom});
  const parts = shownParts(document.getElementById(id))
    .flatMap((el) => [...el.getClientRects()])
    .filter((box) => box.width && box.height).map(edges);
  const row = document.querySelector(`[data-lf-margin-for="${id}"]`);
  const entries = [...row.querySelectorAll('.lf-margin-entry')]
    .filter((entry) => entry.checkVisibility())
    .map((entry) => edges(entry.getBoundingClientRect()));
  return {parts, entries, carrier: edges(row.getBoundingClientRect())};
}"""


def pin_reading(page, target):
    """Read target parts, allocated carrier and buttons, and the words `main` paints."""
    return {**page.evaluate(PIN_READING, target), "words": painted_words(page, "main")}


def pin_distance(carrier, parts):
    """Measure the allocated pin's distance from its nearest target part."""
    return min(
        hypot(
            max(0, part["left"] - carrier["right"], carrier["left"] - part["right"]),
            max(0, part["top"] - carrier["bottom"], carrier["top"] - part["bottom"]),
        )
        for part in parts
    )


def _meets(a, b):
    return (
        a["left"] < b["right"]
        and b["left"] < a["right"]
        and a["top"] < b["bottom"]
        and b["top"] < a["bottom"]
    )


def test_release_notes_pins_under_a_finger_stand_by_the_words_they_decide(
    browser, serve
):
    """At 390px under a finger, each of release-notes' three suggestions has a pin, and
    each stands touching its run, over none of the words it decides: beside the run,
    folded to its one control where only that fits, or above it, over at most the end
    of the line there, where the run's own corner holds more of its words."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(
        browser,
        serve(next(e for e in EXAMPLES if e.stem == "release-notes")),
        context=context,
    )
    margins_laid_out(page)
    for target in ("rn-sug-only", "rn-sug-dry", "rn-sug-window"):
        row = page.locator(f'.lf-margin-cluster[data-lf-margin-for="{target}"]')
        expect(row).to_have_attribute("data-lf-place", "pin")
        reading = pin_reading(page, target)
        assert reading["entries"], (target, reading)
        assert pin_distance(reading["carrier"], reading["parts"]) <= 8, (
            target,
            reading,
        )
        decided = [
            word
            for word in reading["words"]
            if any(_meets(word, part) for part in reading["parts"])
        ]
        for entry in reading["entries"]:
            covered = [word for word in decided if _meets(word, entry)]
            assert not covered, (target, entry, covered)


FOLDING_PAGE = leaf_page(
    "a folded pin",
    '<h1 id="t">Notes</h1>'
    # Justified to 300px, every line but the last ends 324px into a 390px window, which
    # leaves room right of the column for one 44px control but not for a pair.
    '<p id="p" style="width: 300px; text-align: justify">The survey covered the north '
    "field, the south field and the orchard, and found the same two dead zones in "
    "each of them over the three weeks it ran. The status column is the "
    '<lf-suggestion id="s"><lf-old>release\'s only visual change</lf-old>'
    "<lf-new>only change anyone will notice in the run list</lf-new></lf-suggestion>"
    ", and the rest of the release is internal work that nobody should see at all, "
    "so the notes say nothing about it beyond the one line in the changelog that "
    "links the pull request for anyone who wants to read the diff.</p>",
)


def test_a_pin_with_no_room_for_its_actions_stands_folded_and_unfolds_in_place(
    browser, serve
):
    """Under a finger a suggestion's Accept and Reject form a pair. Where no room
    for the pair lies within reach of its run, the pin folds to one 44px control, the
    toggle to its actions, seated as any pin is, so it takes the room right of the
    paragraph and covers none of its words. A tap unfolds the actions leftward with the
    toggle staying where it was pressed, and Accept decides; the keyboard reaches the
    same actions by arriving on the toggle."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(FOLDING_PAGE), context=context)
    margins_laid_out(page)
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="s"]')
    expect(row).to_have_attribute("data-lf-place", "pin")
    expect(row).to_have_attribute("data-lf-folded", "")
    toggle = row.locator(".lf-margin-more")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle.locator("[data-lf-icon]")).to_have_attribute("data-lf-icon", "change")
    expect(toggle).to_have_attribute("aria-label", re.compile(r"^Change, rewrite"))
    reading = pin_reading(page, "s")
    # The toggle alone, over no word of the page.
    assert len(reading["entries"]) == 1, reading["entries"]
    (entry,) = reading["entries"]
    covered = [word for word in reading["words"] if _meets(word, entry)]
    assert not covered, (entry, covered)
    assert pin_distance(reading["carrier"], reading["parts"]) <= 12, reading

    pressed = toggle.bounding_box()
    toggle.tap()
    accept = row.locator(".lf-sug-accept")
    expect(accept).to_be_visible()
    expect(row.locator(".lf-sug-reject")).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    margins_laid_out(page)
    assert toggle.bounding_box() == pressed, (toggle.bounding_box(), pressed)
    assert accept.bounding_box()["x"] < pressed["x"]
    # Touch focus can remain on the toggle; keyboard arrival is checked below.
    opened = row.locator(".lf-margin-entry:visible").evaluate_all(
        "els => els.map(el => { const b = el.getBoundingClientRect();"
        " return [el.getAttribute('aria-label'), b.left, b.right]; })"
    )
    assert len(opened) == 3, opened
    for label, left, right in opened:
        assert 0 <= left < right <= 390, (label, opened)
    assert accept.evaluate(
        "el => { const b = el.getBoundingClientRect();"
        " return document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2)"
        "?.closest('.lf-margin-entry') === el; }"
    )
    accept.tap()
    expect(page.locator("#s")).to_have_attribute("data-lf-state", "accept")
    page.close()

    keyboard = open_page(browser, serve(FOLDING_PAGE), context=context)
    margins_laid_out(keyboard)
    row = keyboard.locator('.lf-margin-cluster[data-lf-margin-for="s"]')
    expect(row).to_have_attribute("data-lf-folded", "")
    # Tab through the page until focus arrives in the pin, which it does on the toggle,
    # the one control it shows; arriving unfolds it onto Accept.
    for _ in range(40):
        keyboard.keyboard.press("Tab")
        if row.evaluate("row => row.contains(document.activeElement)"):
            break
    accept = row.locator(".lf-sug-accept")
    expect(accept).to_be_focused()
    keyboard.keyboard.press("Enter")
    expect(keyboard.locator("#s")).to_have_attribute("data-lf-state", "accept")


@pytest.mark.parametrize(
    "options",
    [
        (
            '<lf-option id="o-close"><strong>Close</strong> Point at the decline.'
            "</lf-option>"
            '<lf-option id="o-leave"><strong>Leave open</strong> Resurfaces.</lf-option>'
        ),
        # Fourteen one-word options, drawn as a column of cells that all but fill the
        # group: a guess at whether a target is drawn by its parts once took them for
        # the group's own face and stood the pin in the first cell.
        '<lf-option id="o-close">Close</lf-option>'
        '<lf-option id="o-leave">Leave open</lf-option>'
        + "".join(f'<lf-option id="o-{n}">Option {n}</lf-option>' for n in range(12)),
    ],
    ids=["two", "fourteen"],
)
def test_a_choice_s_pin_stands_on_none_of_its_option_cards(browser, serve, options):
    """A choice is the group's, so its receipt pins to the options as a whole. The
    group's top-right corner lies on its first option's card, and a card reads as one
    thing, so a pin there reads as that option's: picking "Leave open" drew "Sent" on
    the "Close" card, just below its radio. Its first seat is just outside the group's
    top-right corner, so the pin stands beside the group instead, however many cards
    it holds."""
    body = (
        '<lf-ask id="a"><h2>Close #1176 as won\'t-fix?</h2>'
        f'<lf-options id="o" choose>{options}</lf-options></lf-ask>'
    )
    page = open_page(
        browser, serve(leaf_page("a choice", f"<div>{body}</div>", layout="sidebar"))
    )
    page.locator("#o-leave lf-option-control").click()
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="o"]')
    expect(row).to_have_attribute("data-lf-place", "pin")
    margins_laid_out(page)
    reading = pin_reading(page, "o")
    cards = page.locator("lf-option").evaluate_all(
        """(cards) => {
          const edges = ({left, top, right, bottom}) => ({left, top, right, bottom});
          return cards.map((card) => edges(card.getBoundingClientRect()));
        }"""
    )
    assert reading["entries"], reading
    for entry in reading["entries"]:
        assert not any(_meets(entry, card) for card in cards), (reading, cards)
    assert pin_distance(reading["carrier"], reading["parts"]) <= 12, reading


def test_a_pin_on_a_contents_target_stands_at_its_last_part(browser, serve):
    """A `display: contents` target anchors through its first shown part, but its pin
    stands at the top-right corner of every part together, and shows while they do."""
    source = leaf_page(
        "a contents target",
        '<div><h1 id="t">Pair</h1><div style="display: flex; gap: 24px">'
        '<div id="pair" style="display: contents">'
        '<p style="flex: 1">The first half.</p><p style="flex: 1">The second half.</p>'
        "</div></div></div>",
        layout="sidebar",
    )
    page = open_page(browser, serve(source, events=[_comment_on("pair")]))
    resized(page, 1440, 900)
    margins_laid_out(page)
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="pair"]')
    expect(row).to_have_attribute("data-lf-place", "pin")
    expect(row).to_be_visible()
    row_box = row.bounding_box()
    second = page.locator("#pair > p").nth(1).bounding_box()
    right = second["x"] + second["width"]
    assert right <= row_box["x"] <= right + 8, (row_box, second)
    marker = row.get_by_role("button", name=re.compile(r"^Thread,"))
    marker.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    thread = preview.locator(".lf-margin-thread .lf-page-thread")
    expect(thread).to_be_focused()


def test_a_contents_target_reply_observes_visibility_without_layout(browser, serve):
    """A reply withheld by its display: contents subject follows descendant visibility
    alone, without a resize or render request to wake its floating card."""
    source = leaf_page(
        "a contents target reply",
        '<h1>Reply visibility</h1><div id="pair" style="display: contents">'
        "<p><span>The first half.</span></p><p><span>The second half.</span></p></div>",
        layout="sidebar",
    )
    page = open_page(browser, serve(source, events=[_comment_on("pair")]))
    resized(page, 1440, 900)
    margins_laid_out(page)
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="pair"]')
    marker = row.get_by_role("button", name=re.compile(r"^Thread,"))
    marker.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    reply = preview.get_by_role("textbox", name="Reply", exact=True)
    reply.click()
    expect(reply).to_be_focused()
    words = "A reply stays while its display contents subject returns."
    write(reply, words)
    expect(reply).to_have_js_property("value", words)

    page.locator("#pair").evaluate("el => el.style.visibility='hidden'")
    expect(preview).to_be_hidden()
    page.locator("#pair").evaluate("el => el.style.visibility='visible'")
    expect(preview).to_be_visible()
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", words)


def test_o_hides_what_is_drawn_over_the_page_and_moves_nothing(browser, serve):
    """`o` hides the annotation layer: every pin, the controls one holds included, and
    the durable marks, while the rail and what stands in it stay, since the rail covers
    nothing. Nothing in the layer takes up room, so no box of the page moves. A press on
    a passage whose mark is hidden opens nothing, and the choice is the tab's, so a
    reload keeps it."""
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
    wash = """() => getComputedStyle(document.documentElement)
      .getPropertyValue('--lf-annotation-wash').trim()"""
    before = page.evaluate(boxes)
    assert page.evaluate(wash) == ""

    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("o")
    expect(page.locator("html")).to_have_attribute("data-lf-annotations", "hidden")
    expect(pin).to_be_hidden()
    expect(rail).to_be_visible()
    assert page.evaluate(wash) == "transparent"
    margins_laid_out(page)
    assert page.evaluate(boxes) == before, "hiding the annotations moved the page"

    page.locator("#gap").click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    page.reload()
    page.wait_for_selector("body[data-lf-presented]")
    margins_laid_out(page)
    expect(page.locator("html")).to_have_attribute("data-lf-annotations", "hidden")
    expect(pin).to_be_hidden()
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("o")
    expect(pin).to_be_visible()
    assert page.evaluate(wash) == ""


def test_an_obligation_arrival_reveals_its_pin_while_annotations_are_hidden(
    browser, serve
):
    """An explicit obligation walk reveals its pin until the user leaves that obligation."""
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
    expect(pin).to_have_attribute("data-lf-place", "pin")
    expect(pin).to_be_visible()
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("o")
    expect(page.locator("html")).to_have_attribute("data-lf-annotations", "hidden")
    expect(pin).to_be_hidden()

    # The passage follows both obligations, so a step back lands on the last one.
    page.locator("#gap").click()
    page.keyboard.press("Shift+m")
    expect(page.locator("#sug-card")).to_be_focused()
    rendered(page)
    expect(pin).to_be_visible()
    page.evaluate(RELEASE_FOCUS)
    expect(pin).to_be_hidden()
    expect(page.locator("html")).to_have_attribute("data-lf-annotations", "hidden")


def test_a_finger_hides_the_annotations_from_the_leaf_s_menu(browser, serve):
    """A phone has no `o` to press, so the leaf's menu holds the same toggle under
    Annotate: the pin goes, no box of the page moves, and the row's word turns to the way
    back."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(
        browser, serve(PANEL_PAGE, events=[_comment_on("lede")]), context=context
    )
    margins_laid_out(page)
    pin = page.locator('.lf-margin-cluster[data-lf-margin-for="lede"]')
    expect(pin).to_have_attribute("data-lf-place", "pin")
    expect(pin).to_be_visible()
    boxes = """() => [...document.querySelectorAll('main, main *')].map(el => {
      const b = el.getBoundingClientRect();
      return [b.left, b.top, b.width, b.height].map(Math.round).join(',');
    })"""
    before = page.evaluate(boxes)

    toggle = panel_control(page, "command:annotations.toggle", at="annotate")
    expect(toggle).to_contain_text("Hide annotations")
    press_visible(page, toggle, touch=True)
    expect(page.locator(PANEL)).not_to_have_attribute("data-menu", "")
    expect(page.locator("html")).to_have_attribute("data-lf-annotations", "hidden")
    expect(pin).to_be_hidden()
    margins_laid_out(page)
    assert page.evaluate(boxes) == before, "hiding the annotations moved the page"

    toggle = panel_control(page, "command:annotations.toggle", at="annotate")
    expect(toggle).to_contain_text("Show annotations")
    press_visible(page, toggle, touch=True)
    expect(page.locator("html")).not_to_have_attribute(
        "data-lf-annotations", re.compile(".*")
    )
    expect(pin).to_be_visible()


def test_the_panel_says_the_annotations_are_hidden_while_they_are(browser, serve):
    """Hidden annotations leave a commented page looking as if nobody commented, and
    the hidden layer comes back with a reload, after its notice has passed. So while it
    is hidden the panel's field says so, ahead of the status or after a stance's name,
    until `o` shows the layer again."""
    page = open_page(browser, serve(PANEL_PAGE, events=[_comment_on("lede")]))
    margins_laid_out(page)
    field = panel_field(page)
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("o")
    expect(page.locator("html")).to_have_attribute("data-lf-annotations", "hidden")

    page.reload()
    page.wait_for_selector("body[data-lf-presented]")
    expect(field).to_have_attribute("data-says", "status")
    expect(field).to_have_attribute(
        "placeholder", re.compile(r"^Annotations hidden · \S")
    )

    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("w")
    expect(field).to_have_attribute("data-says", "stance")
    expect(field).to_have_attribute(
        "placeholder", re.compile("^In Draw mode · Annotations hidden")
    )
    page.keyboard.press("Escape")
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")

    page.keyboard.press("o")
    expect(page.locator("html")).not_to_have_attribute(
        "data-lf-annotations", re.compile(".*")
    )
    # The notice saying the annotations are shown passes, and the status stands alone.
    expect(field).to_have_attribute("data-says", "status")
    expect(field).not_to_have_attribute("placeholder", re.compile("Annotations"))


FOOTER_OBLIGATION_PAGE = leaf_page(
    "an Ask in a pane's footer",
    """
  <div id="ask-split">
    <lf-pane id="ask-pane" label="Summary">
      <div id="ask-body">
        <p>The change, summarised in a paragraph long enough to read as one.</p>
        <div style="height: 1200px"></div>
        <lf-ask id="body-ask">
          <h3>Which follow-up comes first?</h3>
          <lf-options id="body-choice" choose>
            <lf-option id="body-bench">Benchmark selected-row demand</lf-option>
            <lf-option id="body-dryrun">Close the dry-run gap</lf-option>
          </lf-options>
        </lf-ask>
        <div style="height: 1200px"></div>
      </div>
      <footer>
        <lf-ask id="foot-ask">
          <h3>Merge this revision?</h3>
          <lf-options id="foot-choice" choose>
            <lf-option id="foot-approve">Approve and merge</lf-option>
            <lf-option id="foot-hold">Hold for the benchmark</lf-option>
          </lf-options>
        </lf-ask>
      </footer>
    </lf-pane>
    <lf-pane id="ask-other" label="Notes"><div><p>Notes.</p></div></lf-pane>
  </div>
""",
    head=regions_side_by_side("ask-split"),
    layout="workspace",
)


def test_a_pin_keeps_clear_only_of_controls_the_user_can_see(browser, serve):
    """A pin goes below a control of the page level with it rather than take its
    presses. The controls were read at their whole boxes, so a body obligation's controls
    scrolled behind the pane's footer, where nobody can see or press them, pushed the
    footer obligation's marker below the heading it stands beside."""
    page = open_page(browser, serve(FOOTER_OBLIGATION_PAGE))
    resized(page, 1440, 900)
    pane_scroll_behavior(page, page.locator("#ask-pane"), "bounded")
    # Scroll the body until its obligation's last control, at the obligation's right edge where a
    # pin stands, is behind the footer obligation's heading, with the body obligation's heading in
    # view.
    page.evaluate(
        """() => {
          const body = document.getElementById('ask-body');
          const control = [...document.querySelectorAll('#body-ask button')].at(-1)
            .getBoundingClientRect();
          const heading = document.querySelector('#foot-ask > h3').getBoundingClientRect();
          body.scrollTop += control.top - heading.top - 2;
        }"""
    )
    margins_laid_out(page)
    expect(
        page.locator('[data-lf-margin-for="body-ask"] .lf-margin-marker')
    ).to_be_visible()
    marker = page.locator('[data-lf-margin-for="foot-ask"] .lf-margin-marker')
    expect(marker).to_be_visible()
    tops = page.evaluate(
        """() => {
          const hidden = [...document.querySelectorAll('#body-ask button')].at(-1)
            .getBoundingClientRect();
          const foot = document.querySelector('#ask-pane > footer').getBoundingClientRect();
          return {
            hiddenTop: hidden.top, footTop: foot.top,
            heading: document.querySelector('#foot-ask > h3').getBoundingClientRect().top,
            marker: document.querySelector('[data-lf-margin-for="foot-ask"] .lf-margin-marker')
              .getBoundingClientRect().top,
          };
        }"""
    )
    assert tops["hiddenTop"] > tops["footTop"], tops
    assert tops["marker"] == pytest.approx(tops["heading"], abs=1), tops


def test_a_pin_keeps_clear_of_controls_slotted_into_its_reading_region(browser, serve):
    """A native control in a slotted obligation takes presses before the obligation's overlay
    pin."""
    source = leaf_page(
        "A slotted Ask",
        '<div><h1>Reading region</h1><div id="reader-host">'
        '<lf-ask id="slotted-ask">'
        "<h3>Which channel?</h3>"
        '<button id="ask-help" style="position:absolute; top:0; right:0; '
        'width:120px; height:44px">Explain channels</button>'
        '<lf-options id="channel" choose><lf-option id="email">Email</lf-option>'
        '<lf-option id="chat">Chat</lf-option></lf-options></lf-ask></div></div>',
        head="<style>#slotted-ask { position:relative; height:180px; margin:0; }</style>",
        layout="sidebar",
    )
    page = open_page(browser, serve(source))
    page.evaluate("""async () => {
      const { registerReadingRegion } =
        await window.__lfWidgetApi();
      const host = document.getElementById('reader-host');
      const root = host.attachShadow({mode:'open'});
      root.innerHTML = '<section style="height:240px; overflow:auto">'
        + '<slot></slot><div style="height:400px"></div></section>';
      const body = root.querySelector('section');
      window.stopSlottedRegion = registerReadingRegion({id:'slotted-reader', host, body});
      document.getElementById('ask-help').addEventListener('click', event => {
        event.currentTarget.textContent = 'Channel explanation';
      });
    }""")
    margins_laid_out(page)
    row = page.locator('[data-lf-margin-for="slotted-ask"]')
    expect(row).to_have_attribute("data-lf-place", "pin")
    expect(row).to_be_visible()
    reading = page.evaluate("""() => {
      const edges = ({left, top, right, bottom}) => ({left, top, right, bottom});
      const row = document.querySelector('[data-lf-margin-for="slotted-ask"]');
      return {
        controls: [...row.querySelectorAll('.lf-margin-entry')]
          .filter(node => node.checkVisibility()).map(node => edges(node.getBoundingClientRect())),
        help: edges(document.getElementById('ask-help').getBoundingClientRect()),
      };
    }""")
    assert reading["controls"], reading
    assert not any(
        _meets(control, reading["help"]) for control in reading["controls"]
    ), reading
    page.get_by_role("button", name="Explain channels", exact=True).click()
    expect(page.locator("#ask-help")).to_have_text("Channel explanation")


@pytest.mark.watch_shifts
def test_a_pin_by_a_card_full_of_controls_stands_on_it_clear_of_them(browser, serve):
    """Cards that run edge to edge, each a tinted header with Action at its right, leave
    a pin no clear seat by the second card: the window's edge, the first card's Action
    above, and the second's own Action in its corner. The pin stays on its card, slid
    left along the header past Action, so the comment still reads as the card's and
    every Action still takes a press."""
    cards = "".join(
        f'<section id="card{i}" style="border:1px solid var(--rule);'
        'background:var(--card);margin:0;height:44px">'
        '<div style="background:var(--chip);height:44px">'
        f'<button id="action{i}" class="button" style="float:right" '
        "onclick=\"this.textContent='Opened'\">Action</button></div></section>"
        for i in range(12)
    )
    url = serve(
        leaf_page(
            "Pin controls",
            "<h1>Pin controls</h1>" + cards,
            head="<style>body { margin: 0 } main { padding-block: 28px 72px }</style>",
            layout=None,
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can we inspect the source here?",
            "anchor": {"section": "card1"},
        },
    )
    context = browser.new_context(
        viewport={"width": 360, "height": 800}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    margins_laid_out(page)
    marker = page.locator('[data-lf-margin-for="card1"]')
    expect(marker).to_be_visible()
    pin = marker.bounding_box()
    card = page.locator("#card1").bounding_box()
    action = page.locator("#action1").bounding_box()
    assert card["x"] <= pin["x"] and pin["x"] + pin["width"] <= action["x"], (
        pin,
        action,
    )
    assert card["y"] <= pin["y"] < card["y"] + card["height"], (pin, card)
    for identity in ("#action0", "#action1", "#action11"):
        action = page.locator(identity)
        action.tap()
        expect(action).to_have_text("Opened")


@pytest.mark.parametrize("viewport", list(pin_cases.VIEWPORTS))
def test_each_pin_case_seats_its_pins_by_their_targets_clear_of_what_they_hide(
    browser, serve, viewport
):
    """Every case of `leaf-dev pins`, ordinary and pathological, seats each pin by its
    target over no words, control or media, inside the window and clear of the other
    pins, except where the case accepts a fault and says why. A placement the gallery
    shows wrong becomes a case there, and so a failure here."""
    (width, height), touch = pin_cases.VIEWPORTS[viewport]
    context = browser.new_context(
        viewport={"width": width, "height": height}, has_touch=touch, is_mobile=touch
    )
    page = open_page(
        browser, serve(pin_cases.source(), events=pin_cases.events()), context=context
    )
    margins_laid_out(page)
    found = {
        case.name: pin_cases.unaccepted(case, pin_cases.read(page, case), viewport)
        for case in pin_cases.CASES
    }
    assert not {name: faults for name, faults in found.items() if faults}


def test_pin_cover_leaves_hidden_panel_contents_unmeasured(browser, serve):
    """A full-width hidden panel in the pin's band must not cost descendant layout."""
    source = leaf_page(
        "Hidden cover",
        '<div id="subject" style="position:relative"><section hidden="until-found" style="position:absolute;inset:0">'
        "Hidden text.<div data-cover-probe><p>Hidden words beside the pin.</p></div>"
        "</section><h1>Shown title</h1></div>",
        layout="sidebar",
    )
    page = open_page(
        browser,
        serve(source, events=[_comment_on("subject")]),
        init_script="""(() => {
          window.hiddenCoverReads = [];
          const ranges = Range.prototype.getClientRects;
          Range.prototype.getClientRects = function (...args) {
            if (this.startContainer.parentElement?.closest('[hidden="until-found"]') &&
                new Error().stack.includes('margin-layout')) hiddenCoverReads.push('text');
            return ranges.apply(this, args);
          };
          const rect = Element.prototype.getBoundingClientRect;
          Element.prototype.getBoundingClientRect = function (...args) {
            if (this.hasAttribute('data-cover-probe') &&
                new Error().stack.includes('margin-layout')) hiddenCoverReads.push('rect');
            return rect.apply(this, args);
          };
        })()""",
    )
    margins_laid_out(page)
    expect(
        page.locator('.lf-margin-cluster[data-lf-margin-for="subject"]')
    ).to_have_attribute("data-lf-place", "pin")
    assert page.evaluate("hiddenCoverReads") == []
