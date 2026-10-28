"""Where the margin's rail stands beside the column, when its markers fall to pins, and
how the user reaches it."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, live_url
from render_harness import (
    EXAMPLES,
    expect_open_threads,
    leaf_page,
    margins_laid_out,
    open_page,
    resized,
    round_trip,
    sending,
    told,
    undo,
)

from browser.margin import (
    MARGIN_ENTRY_KEYBOARD_PAGE,
    _comment_on,
)
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_column_width_does_not_clear_a_sidenote(browser, serve):
    """A callout keeps the prose measure, as text does, so it must not drop below a
    sidenote that ordinary neighboring paragraphs flow beside, as a breakout does."""
    source = leaf_page(
        "Column beside sidenote",
        """
<h1 id="title">Column beside sidenote</h1>
<aside class="sidenote" id="note"><p>Supporting context in the margin, long enough to
run several lines beside the prose and the callout that follow it.</p></aside>
<p id="before">The first line of ordinary prose.</p>
<aside class="callout" id="column"><p>A callout keeps the column.</p></aside>
<p id="after">The following line of ordinary prose.</p>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    expect(page.locator("#note")).to_have_css("float", "right")
    at = page.evaluate(
        """() => ({
          column: document.getElementById('column').getBoundingClientRect().top,
          note: document.getElementById('note').getBoundingClientRect().bottom,
        })"""
    )
    assert at["column"] < at["note"], at


def test_a_held_marker_keeps_the_keyboard_when_the_rail_falls(browser, serve):
    """A marker the keyboard is on stays drawn when the shell loses its rail: it stands
    as a pin in its block's corner instead, so the user stays on it.

    The browser takes focus off an element it hides, onto body, so a posture change that
    hid the row even for a frame would drop the user there. The row is the same node in
    both postures, and only its placement changes."""
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Hold this thread's marker with the keyboard.",
        "anchor": {"section": "how-cap"},
    }
    page = open_page(browser, serve(PANEL_PAGE, events=[comment]))
    resized(page, 1440, 900)
    margins_laid_out(page)
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="how-cap"]')
    expect(row).to_have_attribute("data-lf-place", "rail")
    marker = row.locator(".lf-margin-marker.lf-margin-entry")
    marker.focus()
    expect(marker).to_be_focused()

    resized(page, 700, 900)
    margins_laid_out(page)
    expect(row).to_have_attribute("data-lf-place", "pin")
    expect(marker).to_be_visible()
    expect(marker).to_be_focused()


@pytest.mark.parametrize("touch", [False, True], ids=["mouse", "finger"])
def test_the_rail_stands_where_the_room_beside_the_column_holds_it(
    browser, serve, touch
):
    """The rail claims nothing: its markers stand in it wherever the room between a
    centred column and the shell's right edge holds it, and as pins on their blocks
    everywhere else, so the column keeps its measure at every width. A finger's larger
    entries widen the rail, so each pointer flips at its own width: the column's box
    (720 and 2 x 24 of padding) and a rail on each side. The sweep walks down through
    that width and reads where the markers stand."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, has_touch=touch
    )
    page = open_page(
        browser, serve(PANEL_PAGE, events=[_comment_on("lede")]), context=context
    )
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches") == touch
    rail = page.evaluate(
        """() => parseFloat(getComputedStyle(document.querySelector('main'))
             .getPropertyValue('--rail'))"""
    )
    floor = 720 + 2 * 24 + 2 * rail
    places = set()
    for width in range(round(floor) + 30, round(floor) - 30, -6):
        resized(page, width, 900)
        margins_laid_out(page)
        reading = page.evaluate(
            """() => {
              const main = document.querySelector('main');
              const style = getComputedStyle(main);
              const row = document.querySelector('[data-lf-margin-for="lede"]');
              return {
                place: row.dataset.lfPlace,
                column: Math.round(parseFloat(style.width)),
                shell: document.body.clientWidth,
              };
            }"""
        )
        assert reading["column"] == 720, reading
        if abs(reading["shell"] - floor) <= 2:
            continue
        expected = "rail" if reading["shell"] > floor else "pin"
        assert reading["place"] == expected, (
            f"at a {reading['shell']}px shell, with a {rail:g}px rail needing "
            f"{floor:g}px, the markers stood as {reading['place']}"
        )
        places.add(reading["place"])
    assert places == {"rail", "pin"}, "the sweep never crossed the rail's width"


def test_the_first_rail_allocation_matches_its_native_row(browser, serve):
    """A first comment clears touch-sized entries and the actual focus-ring inset."""
    source = leaf_page(
        "First rail allocation",
        "<h1>First rail allocation</h1>"
        '<p id="subject">A passage without an existing margin entry.</p>'
        '<p id="next-subject">Another passage beside the same rail.</p>',
        head="<style>:root {--focus-ring-w:7px; --focus-ring-gap:4px}</style>",
    )
    context = browser.new_context(
        viewport={"width": 1400, "height": 900}, has_touch=True
    )
    page = open_page(browser, serve(source), context=context)
    expect(page.locator("main")).to_have_attribute(
        "data-lf-margin", re.compile(r"rail")
    )
    expect(page.locator(".lf-margin-entry")).to_have_count(0)
    prospective = page.evaluate("""async () => {
      const owner = await window.__lfOverlayApi();
      return owner.marginSpot(document.querySelector('#subject'));
    }""")
    assert prospective["right"] - prospective["left"] == pytest.approx(55)
    expect(page.locator(".lf-margin-entry")).to_have_count(0)
    page.locator("#subject").click(modifiers=["Alt"])
    editor = page.locator(".lf-fab-input")
    expect(editor).to_be_focused()
    editor.press_sequentially("The first comment")
    with sending(page, "the first rail comment"):
        editor.press("Control+Enter")
    entry = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    expect(entry).to_be_visible()
    actual = entry.evaluate("""entry => {
      const row = entry.closest('.lf-margin-cluster').getBoundingClientRect();
      return {left:row.left, right:row.right, entry:entry.offsetWidth};
    }""")
    assert actual["entry"] == 44
    assert actual["left"] == pytest.approx(prospective["left"])
    assert actual["right"] == pytest.approx(prospective["right"])
    reused = page.evaluate("""async () => {
      const owner = await window.__lfOverlayApi();
      const observer = new MutationObserver(() => {});
      observer.observe(document.body, {childList:true, subtree:true});
      const spot = owner.marginSpot(document.querySelector('#next-subject'));
      const writes = observer.takeRecords().length;
      observer.disconnect();
      return {spot, writes};
    }""")
    assert reused["spot"]["right"] - reused["spot"]["left"] == pytest.approx(55)
    assert reused["writes"] == 0, "An existing rail should need no measuring DOM writes"

    # Opening peer actions leaves one direct entry beside an options group. That
    # wider row cannot supply the allocation of a new single-entry comment row.
    page.evaluate("""async () => {
      const {contributionEntry, registerContribution} =
        await window.__lfWidgetApi();
      registerContribution({key: 'rail-details', target: document.querySelector('#subject'),
        read: () => ({entries: [contributionEntry({
          key: 'details', icon: 'comment', label: 'Rail details',
          behavior: 'disclosure', rank: 'reading'
        })]}), activate: () => {}});
    }""")
    entry.focus()
    expect(
        entry.locator("xpath=..").locator(":scope > .lf-margin-options")
    ).to_be_visible()
    expanded = page.evaluate("""async () => {
      const owner = await window.__lfOverlayApi();
      return owner.marginSpot(document.querySelector('#next-subject'));
    }""")
    assert expanded["right"] - expanded["left"] == pytest.approx(55)


# Either side of the width where the prose column gains its rail, and a catalog
# narrower and wider than its own measure.
@pytest.mark.parametrize(
    ("width", "wide"),
    [(1207, False), (1208, False), (1000, True), (1720, True)],
    ids=["prose-1207", "prose-1208", "catalog-1000", "catalog-1720"],
)
def test_a_live_page_leaves_no_empty_thread_column_and_keeps_its_reading_position(
    browser, serve, width, wide
):
    """Possible comments cost only the control rail; actual comments never move prose."""
    source = leaf_page(
        "A passage",
        '<p id="passage">A passage to discuss.</p>',
        head=(
            "<style>main { width: min(var(--wide), var(--lf-room)); "
            "max-width: var(--wide); }</style>"
            if wide
            else ""
        ),
    )
    page = open_page(browser, serve(source))
    resized(page, width, 900)

    def position():
        return page.locator("main").evaluate(
            """main => {
              const box = main.getBoundingClientRect();
              const shell = document.body.getBoundingClientRect();
              return {left: box.left, width: box.width, shellWidth: shell.width,
                offset: (box.left + box.right - shell.left - shell.right) / 2};
            }"""
        )

    # The rail is 95px, so the page's axis stands at most half of it off the shell's.
    initial = position()
    assert abs(initial["offset"]) <= 48, initial
    # The wide measure is 840px plus the page's 48px of inline padding.
    assert (
        initial["width"] >= min(888 if wide else 768, initial["shellWidth"] - 95) - 1
    ), initial

    comment = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "A first thought",
            "anchor": {"section": "passage"},
        },
    )
    told(page)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    expect(marker).to_be_visible()
    assert position() == initial
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    assert position() == initial

    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": comment["id"]},
    )
    told(page)
    expect_open_threads(page, 0)
    assert position() == initial


def test_a_page_that_can_grow_margin_status_reserves_its_rail_before_the_first_gesture(
    browser, serve
):
    """The user's first move must not be the gesture that pays for the margin.

    Moving a card raises an acknowledgment status at the page edge. Reserved only while
    that status stood, the strip arrived with the move and left again with the undo, and
    the column moved 29px each way — for a reading the page had always been going to
    offer. So the reservation is read off what the page declares, a tag whose registry
    entry has an action or work channel, and the column stands where it will stand
    before the user touches anything.

    Measured on the shipped board rather than a fixture, because the strip is only worth
    reserving where a real page's width, its claims and its exhibits meet; a fixture
    built to make those agree would prove nothing about any page a user opens."""
    example = next(page for page in EXAMPLES if page.stem == "triage-board")
    page = open_page(browser, live_url(serve(example)))
    margins_laid_out(page)
    column = page.locator("main").evaluate(
        "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
    )

    page.locator("#card-export .lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    round_trip(page)
    expect(page.locator("#col-defer #card-export")).to_have_count(1)
    margins_laid_out(page)
    # Without a status in the margin the readings below would agree for the wrong reason.
    expect(page.locator(".lf-margin-cluster")).to_have_count(1)
    assert (
        page.locator("main").evaluate(
            "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
        )
        == column
    ), "raising the acknowledgment status moved the readable column"

    undo(page)
    expect(page.locator("#col-next #card-export")).to_have_count(1)
    margins_laid_out(page)
    assert (
        page.locator("main").evaluate(
            "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
        )
        == column
    ), "withdrawing the move handed the strip back and moved the column with it"


def test_a_marker_level_with_a_hanging_note_pins_and_one_below_it_keeps_the_rail(
    browser, serve
):
    """A sidenote hanging in the right margin holds the strip the rail stands in, so the
    marker of a paragraph level with it stands on the paragraph as a pin rather than
    over the note. The control is a paragraph far below the note, whose marker keeps
    the rail."""
    filler = "".join(f"<p>Filler paragraph {i}.</p>" for i in range(12))
    source = leaf_page(
        "a note beside its paragraph",
        '<h1 id="t">Notes</h1><aside class="sidenote" id="note">A note beside the '
        "paragraph it glosses, long enough to stand a few lines tall.</aside>"
        f'<p id="beside">The paragraph the note glosses.</p>{filler}'
        '<p id="below">A paragraph well below the note.</p>',
    )
    page = open_page(
        browser, serve(source, events=[_comment_on("beside"), _comment_on("below")])
    )
    resized(page, 1600, 900)
    margins_laid_out(page)
    assert (
        page.evaluate("() => getComputedStyle(document.getElementById('note')).float")
        == "right"
    )
    for target, place in (("beside", "pin"), ("below", "rail")):
        row = page.locator(f'.lf-margin-cluster[data-lf-margin-for="{target}"]')
        expect(row).to_have_attribute("data-lf-place", place)


@pytest.mark.parametrize(
    ("main", "body", "place"),
    [
        ('<main class="layout-column">', "<body>", "rail"),
        ('<main class="layout-sidebar">', "<body>", "pin"),
        ('<main class="layout-sidebar">', '<body data-rail="right">', "rail"),
        ('<main class="layout-column">', '<body data-rail="none">', "pin"),
    ],
    ids=["column", "sidebar", "sidebar-keeps-the-rail", "column-gives-it-up"],
)
def test_the_page_form_decides_the_rail_and_body_can_say_otherwise(
    browser, serve, main, body, place
):
    """A column page keeps a rail beside its column and a sidebar page does not: its markers
    stand as pins on their blocks. `data-rail` on `body` turns either round: `right`
    gives up the rail's width at the shell's right edge, and `none` keeps the margin for
    the page's own margin content. Only `right` takes room from the page, and only above a
    phone's width: on a phone every form's markers pin and the page keeps its width."""
    source = (
        leaf_page(
            "rail by form",
            '<div><h1 id="t">Rail by form</h1>'
            '<p id="p">A paragraph with a comment on it.</p></div>',
        )
        .replace('<main class="layout-column">', main)
        .replace("<body>", body)
    )
    page = open_page(browser, serve(source, events=[_comment_on("p")]))
    resized(page, 1440, 900)
    margins_laid_out(page)
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="p"]')
    expect(row).to_have_attribute("data-lf-place", place)
    given = "() => parseFloat(getComputedStyle(document.body).paddingInlineEnd)"
    assert (page.evaluate(given) > 0) == ('data-rail="right"' in body)
    resized(page, 390, 844)
    margins_laid_out(page)
    expect(row).to_have_attribute("data-lf-place", "pin")
    assert page.evaluate(given) == 0


@pytest.mark.parametrize("rail", [None, "right"])
def test_a_workspace_page_keeps_no_rail(browser, serve, rail):
    """A workspace takes the window, which leaves no room beside it for a rail, so a
    comment in a pane stands on its block as a pin. Asking for a rail changes neither:
    a row stands in the rail only beside what the page scrolls, and a workspace scrolls
    its panes, so the strip would only stand empty beside them."""
    source = leaf_page(
        "workspace page",
        '<header><h1 id="t">Workspace</h1></header>'
        '<lf-pane id="pane" label="Queue"><div><p id="p">A paragraph.</p></div>'
        "</lf-pane>",
        layout="workspace",
    )
    if rail:
        source = source.replace("<body>", f'<body data-rail="{rail}">')
    page = open_page(browser, serve(source, events=[_comment_on("p")]))
    resized(page, 1440, 900)
    margins_laid_out(page)
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="p"]')
    expect(row).to_have_attribute("data-lf-place", "pin")
    assert (
        page.evaluate("document.querySelector('main').getBoundingClientRect().right")
        == 1440
    )


WIDE_TABLE_ROW_PAGE = leaf_page(
    "a comment in a wide table",
    """
<h1 id="t">A wide table</h1>
<p id="before">A paragraph above the table.</p>
<table id="wide-table">
  <tr><td id="first-cell">First</td>"""
    + "".join(f"<td>column {i} with a long heading</td>" for i in range(12))
    + """</tr>
</table>
""",
)


def test_a_comment_in_a_table_wider_than_the_column_keeps_the_rail(browser, serve):
    """A table wider than the column scrolls inside it, so its rows reach far past the
    rail without the table growing at all. A comment on one of its cells is not a figure
    grown past the rail: its marker keeps the rail."""
    page = open_page(
        browser, serve(WIDE_TABLE_ROW_PAGE, events=[_comment_on("first-cell")])
    )
    resized(page, 1440, 900)
    margins_laid_out(page)
    scrolls = page.locator("#wide-table").evaluate(
        "t => t.scrollWidth > t.clientWidth + 1"
    )
    assert scrolls, "the table fits its column, so nothing here is tested"
    expect(
        page.locator('.lf-margin-cluster[data-lf-margin-for="first-cell"]')
    ).to_have_attribute("data-lf-place", "rail")


def test_the_margin_layer_follows_the_page_in_the_tab_order(browser, serve):
    """Leaf inserts nothing into the page's content, so a suggestion's controls stand in
    the margin layer and come after the page's content in the tab order. Tab from the
    page's last control reaches them, and Shift+Tab goes back the way it came."""
    page = open_page(browser, serve(MARGIN_ENTRY_KEYBOARD_PAGE))
    resized(page, 1440, 900)
    accept = page.locator('[data-lf-margin-for="sug-refill"] .lf-sug-accept')
    page.locator("#after-margin-entries").focus()
    reached = 0
    for presses in range(1, 80):
        page.keyboard.press("Tab")
        if accept.evaluate("el => el === document.activeElement"):
            reached = presses
            break
    assert reached, "Tab never reached the suggestion's Accept in the margin layer"
    for _ in range(reached):
        page.keyboard.press("Shift+Tab")
    expect(page.locator("#after-margin-entries")).to_be_focused()


def test_a_quoted_passage_stands_its_own_rail_row_level_with_its_words(browser, serve):
    """Comments quoting words deep in a long paragraph stand a margin row of their own,
    level with the passage's first line rather than at the paragraph's top, where the
    paragraph's own comment stands; comments quoting the same words share it."""
    text = " ".join(
        f"Sentence number {i} says something about the release." for i in range(40)
    )
    body = f'<h1>Passage rows</h1><p id="long">{text} Finally the last words land.</p>'
    events = [
        {"kind": "comment", "author": "user", "revision": 1, "text": says, "anchor": a}
        for says, a in (
            ("On the paragraph", {"section": "long"}),
            ("On its end", {"section": "long", "quote": "the last words land"}),
            ("On its end again", {"section": "long", "quote": "the last words land"}),
        )
    ]
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = open_page(
        browser, serve(leaf_page("Passage rows", body), events=events), context=context
    )
    margins_laid_out(page)
    read = page.evaluate("""() => {
      const p = document.getElementById('long');
      const node = p.firstChild;
      const at = node.data.indexOf('the last words land');
      const words = document.createRange();
      words.setStart(node, at);
      words.setEnd(node, at + 'the last words land'.length);
      return {
        paragraph: p.getBoundingClientRect().top,
        line: words.getClientRects()[0].top,
        rows: [...document.querySelectorAll('[data-lf-margin-for="long"]')]
          .map((row) => ({
            place: row.dataset.lfPlace,
            top: row.getBoundingClientRect().top,
            says: row.lfEntry.items.map((item) => item.text),
          }))
          .sort((a, b) => a.top - b.top),
      };
    }""")
    assert [row["says"] for row in read["rows"]] == [
        ["On the paragraph"],
        ["On its end", "On its end again"],
    ], read
    whole, passage = read["rows"]
    assert whole["place"] == passage["place"] == "rail", read
    assert abs(whole["top"] - read["paragraph"]) < 1, read
    assert abs(passage["top"] - read["line"]) < 1, read


@pytest.mark.watch_shifts
@pytest.mark.parametrize("focused", [False, True])
def test_new_rail_keeps_a_pin_reachable(browser, serve, focused):
    body = '<h1>Held marker</h1><section style="position:relative"><div id="pin-target" style="height:100px;width:calc(100% + 96px);max-width:none">Wide figure</div><p id="rail-target" style="position:absolute;top:0;left:0;margin:0">Rail target</p></section>'
    events = [
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Hold the figure marker",
            "anchor": {"section": "pin-target"},
        }
    ]
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = open_page(
        browser,
        serve(leaf_page("Held pin and new rail", body), events=events),
        context=context,
    )
    margins_laid_out(page)
    pin = page.locator('[data-lf-margin-for="pin-target"]')
    expect(pin).to_have_attribute("data-lf-place", "pin")
    marker = pin.get_by_role("button", name="Thread,", exact=False)
    if focused:
        marker.focus()
        expect(marker).to_have_attribute("data-lf-label-side", re.compile(".+"))
        label_before = marker.locator(".lf-margin-entry-label").bounding_box()
    else:
        page.mouse.move(20, 20)
    before = pin.bounding_box()
    page.evaluate("""async()=>{
      const {contributionEntry,registerContribution}=await window.__lfWidgetApi();
      registerContribution({key:'new-rail',target:document.querySelector('#rail-target'),read:()=>({entries:[contributionEntry({key:'activate',glyph:'R',label:'Activate rail'})]}),activate:()=>{window.railActivated=true;}});
    }""")
    margins_laid_out(page)
    rail = page.locator('[data-lf-margin-for="rail-target"]')
    expect(rail).to_have_attribute("data-lf-place", "rail")
    a, b = pin.bounding_box(), rail.bounding_box()
    assert a == before
    if focused:
        assert marker.locator(".lf-margin-entry-label").bounding_box() == label_before
        expect(marker).to_be_focused()
    assert not (
        a["x"] < b["x"] + b["width"]
        and b["x"] < a["x"] + a["width"]
        and a["y"] < b["y"] + b["height"]
        and b["y"] < a["y"] + a["height"]
    )
    marker.press("Enter")
    rendered(page)
    expect(page.locator("#lf-margin-preview")).to_contain_text("Hold the figure marker")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    rail.get_by_role("button", name="Activate rail", exact=True).click()
    assert page.evaluate("()=>window.railActivated")


@pytest.mark.watch_shifts
@pytest.mark.parametrize("focused", [False, True])
def test_new_pin_keeps_a_rail_reachable(browser, serve, focused):
    body = '<h1>Held rail</h1><section style="position:relative"><div id="pin-target" style="height:100px;width:calc(100% + 96px);max-width:none">Wide figure</div><p id="rail-target" style="position:absolute;top:0;left:0;margin:0">Rail target</p></section>'
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = open_page(
        browser, serve(leaf_page("Held rail and new pin", body)), context=context
    )
    page.evaluate("""async()=>{
      const {contributionEntry,registerContribution}=await window.__lfWidgetApi();
      window.registerPlacementControl=id=>registerContribution({key:id,target:document.getElementById(id+'-target'),read:()=>({entries:[contributionEntry({key:'activate',glyph:'R',label:'Activate '+id})]}),activate:()=>{window.placementActivated=id;}});
      window.registerPlacementControl('rail');
    }""")
    margins_laid_out(page)
    rail = page.locator('[data-lf-margin-for="rail-target"]')
    expect(rail).to_have_attribute("data-lf-place", "rail")
    control = rail.get_by_role("button", name="Activate rail", exact=True)
    if focused:
        control.focus()
        expect(control).to_have_attribute("data-lf-label-side", re.compile(".+"))
        label_before = control.locator(".lf-margin-entry-label").bounding_box()
    else:
        page.mouse.move(20, 20)
    before = rail.bounding_box()
    page.evaluate("()=>window.registerPlacementControl('pin')")
    margins_laid_out(page)
    pin = page.locator('[data-lf-margin-for="pin-target"]')
    expect(pin).to_have_attribute("data-lf-place", "pin")
    expect(pin).to_be_visible()
    a, b = rail.bounding_box(), pin.bounding_box()
    assert a == before
    if focused:
        assert control.locator(".lf-margin-entry-label").bounding_box() == label_before
        expect(control).to_be_focused()
    assert not (
        a["x"] < b["x"] + b["width"]
        and b["x"] < a["x"] + a["width"]
        and a["y"] < b["y"] + b["height"]
        and b["y"] < a["y"] + a["height"]
    )
    control.press("Enter")
    assert page.evaluate("()=>window.placementActivated") == "rail"
    pin.get_by_role("button", name="Activate pin", exact=True).click()
    assert page.evaluate("()=>window.placementActivated") == "pin"
