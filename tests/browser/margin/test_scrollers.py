"""How a margin row follows its target through scrolling panes, shadow-tree scrollers,
sticky and fixed boxes, hidden tabs and authored anchor scopes."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE, PANEL_PAGE, answered_comment
from render_harness import (
    FOLLOWER_MARK,
    SUBJECT_MARK,
    assert_follows_in_every_frame,
    leaf_page,
    margins_laid_out,
    open_page,
    pane_scroll_behavior,
    resized,
    scroll_settled,
)

from browser.margin import (
    ACTION_ON_OBLIGATION,
    COMMENT_ON_OBLIGATION,
    PANE_PIN_PAGE,
    _comment_on,
)
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_comment_follows_a_target_that_escapes_an_intermediate_clip(browser, serve):
    """An absolute target remains commentable when its containing block lies outside
    an overflow clip that does not clip the target's native paint."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Escaping a clip",
                '<h1>Evidence</h1><div style="position:relative;height:360px">'
                '<div style="overflow:hidden;width:140px;height:80px">'
                '<button id="target" style="position:absolute;left:240px;top:100px;'
                'width:160px;height:60px">Escaped target</button></div></div>',
            ),
            events=[_comment_on("target")],
        ),
    )
    margins_laid_out(page)
    page.get_by_role("button", name="Escaped target", exact=True).click()
    row = page.locator('[data-lf-margin-for="target"]')
    expect(row).to_be_visible()
    row.locator(".lf-margin-marker").click()
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_visible()


def test_the_margin_keeps_its_page_coordinate_while_the_user_scrolls(browser, serve):
    """Runtime chrome and authored content share one document-space coordinate."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    target = page.locator("#bracket")

    def offset():
        return marker.bounding_box()["y"] - target.bounding_box()["y"]

    before = offset()
    page.evaluate(
        "() => document.scrollingElement.scrollBy({top: 320, behavior: 'instant'})"
    )
    margins_laid_out(page)
    assert offset() == pytest.approx(before, abs=1)


def test_a_keyboard_arrival_brings_its_card_once_its_row_is_shown(browser, serve):
    """`m` to an obligation below a pane's fold scrolls it into view while its row is still
    withheld, so there is nothing yet to hang its card from. The card of the thread the
    user leaves goes at once, and the obligation's comes once the margin shows its row, as it
    would for an arrival whose row was already there."""
    item = (
        '<lf-ask id="work"><h2>Choose</h2><lf-options id="options" choose>'
        '<lf-option id="yes">Yes</lf-option><lf-option id="no">No</lf-option>'
        "</lf-options></lf-ask>"
    )
    url = serve(PANE_PIN_PAGE.replace('<p id="pane-end">The last finding.</p>', item))
    left = answered_comment(serve.page_dir, "First finding", {"section": "pane-top"})
    root = answered_comment(serve.page_dir, "Ask discussion", {"section": "work"})
    page = open_page(browser, url)
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#pin-pane"), "bounded")
    margins_laid_out(page)
    row = page.locator('[data-lf-margin-for="work"]')
    expect(row).to_be_hidden()
    page.keyboard.press("t")
    leaving = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{left}"]')
    expect(leaving).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#work")).to_be_focused()
    expect(leaving).to_have_count(0)
    expect(row).to_be_visible()
    expect(
        page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    ).to_be_visible()
    expect(page.locator("#work")).to_be_focused()


def test_a_pin_in_a_pane_scrolls_with_it_and_leaves_with_its_target(browser, serve):
    """A pane that scrolls on its own gets a lane of its own in the margin layer. Its
    pin follows the pane's scroll through the anchor that carries it, with no layout pass
    to wait for, and once its target has scrolled out of the pane the row is withheld:
    out of the tab order, and nothing of it drawn over the pane's header or its
    neighbour."""
    page = open_page(browser, serve(PANE_PIN_PAGE, events=[_comment_on("pane-top")]))
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#pin-pane"), "bounded")
    margins_laid_out(page)
    row = page.locator('.lf-margin-lane [data-lf-margin-for="pane-top"]')
    expect(row).to_have_attribute("data-lf-place", "pin")
    moved = page.evaluate(
        """async () => {
          const row = document.querySelector('[data-lf-margin-for="pane-top"]');
          const target = document.getElementById('pane-top');
          const body = target.parentElement;
          const offset = () =>
            row.getBoundingClientRect().top - target.getBoundingClientRect().top;
          const before = offset();
          let laidOut = 0;
          document.addEventListener('lf-margin-layout', () => laidOut++);
          body.scrollTop = 40;
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
          return {before, after: offset(), laidOut};
        }"""
    )
    assert moved["after"] == pytest.approx(moved["before"], abs=1), moved
    assert moved["laidOut"] == 0, moved

    page.locator("#pin-pane > div").evaluate("body => { body.scrollTop = 900; }")
    expect(row).to_have_class(re.compile(r"\blf-withheld\b"))
    page.locator("#pin-pane > div").evaluate("body => { body.scrollTop = 0; }")
    expect(row).not_to_have_class(re.compile(r"\blf-withheld\b"))


@pytest.mark.parametrize("engine", ["firefox_browser", "webkit_browser"])
def test_rows_follow_a_pane_and_a_shadow_scroller_in_every_engine(
    request, serve, engine
):
    """Firefox and WebKit carry rows on the same anchors as Chrome: a pin in a pane,
    whose lane is a frame anchored to the pane's scroller, and a row whose target
    scrolls inside a widget's shadow tree, anchored through the part the document
    names it by. Both keep their offset from their targets through those scrolls."""
    browser = request.getfixturevalue(engine)
    page = open_page(browser, serve(PANE_PIN_PAGE, events=[_comment_on("pane-top")]))
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#pin-pane"), "bounded")
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} = await window.__lfWidgetApi();
          const host = document.createElement('div');
          const root = host.attachShadow({mode: 'open'});
          root.innerHTML = '<div id="inner" style="height: 100px; overflow: auto">'
            + '<div style="height: 40px"></div><p id="deep">Deep target</p>'
            + '<div style="height: 400px"></div></div>';
          document.querySelector('#other-pane > div').prepend(host);
          const target = root.getElementById('deep');
          const margin = registerContribution({key: 'deep', target,
            read: () => ({entries: [contributionEntry({
              key: 'deep', glyph: '!', label: 'deep controls'})]}),
            activate: () => {}});
          window.__deep = {target, margin, inner: root.getElementById('inner')};
        }"""
    )
    margins_laid_out(page)
    reading = """() => {
      const pane = document.querySelector('[data-lf-margin-for="pane-top"]');
      const {target, margin} = window.__deep;
      const deep = margin.control('deep', 'margin').closest('.lf-margin-cluster');
      const top = (a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top;
      return {pane: top(pane, document.getElementById('pane-top')),
              deep: top(deep, target),
              shown: !pane.classList.contains('lf-withheld')
                && !deep.classList.contains('lf-withheld')};
    }"""
    before = page.evaluate(reading)
    assert before["shown"], before
    page.evaluate("""() => {
      document.querySelector('#pin-pane > div').scrollTop = 40;
      window.__deep.inner.scrollTop = 20;
    }""")
    rendered(page)
    after = page.evaluate(reading)
    assert after["shown"], after
    assert after["pane"] == pytest.approx(before["pane"], abs=1), (before, after)
    assert after["deep"] == pytest.approx(before["deep"], abs=1), (before, after)


WIDENED_TABLE_PAGE = leaf_page(
    "a widened table",
    "<h1>Seats</h1><p>A paragraph at the measure, long enough to fill the column it "
    "stands in from one edge to the other.</p>"
    '<table id="grid" data-width="wide"><thead><tr><th></th><th>Caret elsewhere</th>'
    "<th>Caret in the field</th></tr></thead><tbody>"
    + "<tr><th>No view open</th><td>The field's placeholder says it, in place of the "
    "agent's status, for as long as the walk stands there.</td><td>The line over the "
    "field says it. It takes its own room in the panel, so it covers nothing.</td></tr>"
    * 3
    + '<tr><th>Command</th><td colspan="2"><pre id="command"><code>uv run pytest '
    "tests/browser/margin/test_scrollers.py</code></pre></td></tr></tbody></table>"
    + "<p>Prose after the table, so the page scrolls.</p>"
    * 40,
)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser", "webkit_browser"])
def test_marks_stand_on_a_widened_table_in_every_engine(request, serve, engine):
    """A table granted room is translated into place (layouts.css), and Firefox leaves
    an anchor's transforms out of `anchor()`, so every box anchored in one stood the
    translation away from what it marked: at 1728px a comment's pin on a header sat
    over the column beside it, and the Alt outline 300px left of the table. In each
    engine the pin stands on the header it marks and keeps that place through a
    scroll, the outline Alt raises after the scroll stands on the table, and a code
    block's Copy, which CSS anchors alone, stands inside the block's top-right
    corner."""
    browser = request.getfixturevalue(engine)
    comment = _comment_on("grid", quote="Caret in the field")
    page = open_page(browser, serve(WIDENED_TABLE_PAGE, events=[comment]))
    resized(page, 1728, 999)
    margins_laid_out(page)
    reading = """() => {
      const box = (el) => el.getBoundingClientRect();
      const pin = box(document.querySelector('.lf-margin-cluster'));
      const header = box(document.querySelectorAll('#grid thead th')[2]);
      return {pin: [pin.left - header.left, pin.top - header.top],
              header: [header.left, header.right, header.top]};
    }"""
    before = page.evaluate(reading)
    left, right, _ = before["header"]
    assert 0 <= before["pin"][0] <= right - left, before
    page.evaluate("() => document.scrollingElement.scrollBy(0, 120)")
    margins_laid_out(page)
    after = page.evaluate(reading)
    assert after["header"][2] == pytest.approx(before["header"][2] - 120, abs=1), after
    assert after["pin"] == pytest.approx(before["pin"], abs=1), (before, after)
    page.locator("#grid thead th").nth(2).hover()
    page.keyboard.down("Alt")
    aim = page.locator(".lf-aim")
    expect(aim).to_be_visible()
    table, outline = page.locator("#grid").bounding_box(), aim.bounding_box()
    page.keyboard.up("Alt")
    assert outline["x"] == pytest.approx(table["x"], abs=1), (outline, table)
    assert outline["y"] == pytest.approx(table["y"], abs=1), (outline, table)
    code = page.locator("#command").bounding_box()
    page.mouse.move(code["x"] + 5, code["y"] + code["height"] / 2)
    copy = page.locator(".lf-code-copy")
    expect(copy).to_have_css("opacity", "1")
    corner = copy.bounding_box()
    inset = code["x"] + code["width"] - corner["x"] - corner["width"]
    assert 0 <= inset <= 8, (corner, code)
    assert 0 <= corner["y"] - code["y"] <= 8, (corner, code)


def test_a_pin_in_a_pane_paints_in_the_frame_its_target_scrolls(browser, serve):
    """Every frame Chrome draws while a pane scrolls shows the pin level with its
    target, since the browser carries both through the same scroll."""
    marks = (
        f"<style>#pane-top {{ background:{SUBJECT_MARK}; }}"
        f' [data-lf-margin-for="pane-top"] {{ outline:6px solid {FOLLOWER_MARK}'
        " !important; }</style></head>"
    )
    page = open_page(
        browser,
        serve(
            PANE_PIN_PAGE.replace("</head>", marks), events=[_comment_on("pane-top")]
        ),
    )
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#pin-pane"), "bounded")
    margins_laid_out(page)
    target = page.locator("#pane-top").bounding_box()
    page.mouse.move(target["x"] + 40, target["y"] + 5)
    assert_follows_in_every_frame(page, "#pin-pane > div")


@pytest.mark.parametrize(
    "wrapper", ["overflow: hidden; border-radius: 8px", "overflow-x: auto"]
)
def test_a_pin_in_a_pane_rides_an_anchored_carrier_through_boxes_that_scroll_nothing(
    browser, serve, wrapper
):
    """A pin whose target stands in a pane stands in a carrier anchored to what the
    pane's scroll carries, rather than a scroll-driven layer, which can paint a frame
    off its scroll. A box between the target and the pane that clips but scrolls
    nothing, as a rounded wrapper or a table wrapper that fits, leaves it there."""
    source = PANE_PIN_PAGE.replace(
        '<p id="pane-top">The first finding, commented on.</p>',
        f'<div style="{wrapper}"><p id="pane-top">The first finding, commented on.</p>'
        "</div>",
    )
    page = open_page(browser, serve(source, events=[_comment_on("pane-top")]))
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#pin-pane"), "bounded")
    margins_laid_out(page)
    row = page.locator('[data-lf-margin-for="pane-top"]')
    expect(row).to_have_attribute("data-lf-place", "pin")
    assert row.evaluate(
        "row => row.parentElement.classList.contains('lf-margin-carrier')"
    ), wrapper


@pytest.mark.parametrize("change", ["size", "layout"])
def test_a_bounded_region_reflows_its_margin_without_resizing_the_page(
    browser, serve, change
):
    """A fixed-size pane can move its target through a sibling's resize or a
    same-size view rearrangement. The geometry owner hears the size owner and the
    explicit layout owner, and moves the row before their frame paints."""
    source = PANE_PIN_PAGE.replace(
        "</head>",
        "<style>#pane-top[data-offset] { transform: translateY(24px); }</style></head>",
    )
    page = open_page(browser, serve(source, events=[_comment_on("pane-top")]))
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#pin-pane"), "bounded")
    margins_laid_out(page)
    page.locator('[data-lf-margin-for="pane-top"] button').first.focus()
    rendered(page)
    reading = """() => {
      const target = document.getElementById('pane-top');
      const row = document.querySelector('[data-lf-margin-for="pane-top"]');
      const r = row.getBoundingClientRect(), t = target.getBoundingClientRect();
      return {top: r.top, offset: r.top - t.top,
        height: document.querySelector('main').getBoundingClientRect().height,
        hit: row.contains(document.elementFromPoint(r.left + r.width / 2,
                                                   r.top + r.height / 2))};
    }"""
    before = page.evaluate(reading)
    page.evaluate(
        """async change => {
          const target = document.getElementById('pane-top');
          if (change === 'size') target.previousElementSibling.style.height = '224px';
          else {
            target.setAttribute('data-offset', '');
            const {layoutChanged} = await window.__lfWidgetApi();
            await layoutChanged(target);
          }
        }""",
        change,
    )
    rendered(page)
    after = page.evaluate(reading)
    assert after["height"] == before["height"]
    if change == "size":
        assert after["top"] - before["top"] == pytest.approx(24, abs=1)
        assert after["offset"] == pytest.approx(before["offset"], abs=1)
    else:
        # Moving only the paragraph can change the clear seat around it. The layout
        # notification must settle that seat as a full geometry reading would.
        assert after["top"] != before["top"]
        page.evaluate("""async () => {
          const {layoutChanged} = await window.__lfWidgetApi();
          layoutChanged(document.body);
        }""")
        assert page.evaluate(reading) == after
    assert after["hit"]


_PARAGRAPH = (
    "<p>The export writes one file per tenant each night, and the archive would roll"
    " every tenant into a partitioned bundle that the reader opens lazily by key"
    " range.</p>"
)


SEATED_PANE_PAGE = leaf_page(
    "an Ask seated in a pane",
    '<header><h1 id="t">Pane pins</h1></header><div id="seat-panes">'
    '<lf-pane id="seat-pane" label="Left"><div>'
    + _PARAGRAPH
    * 2
    + '<lf-ask id="seat-ask"><h3>Should the nightly export keep writing one file per'
    " tenant or roll every tenant up into one archive tonight</h3>"
    '<lf-options id="seat-choice" choose>'
    '<lf-option id="sa"><strong>One file per tenant</strong></lf-option>'
    '<lf-option id="sb"><strong>One archive</strong></lf-option>'
    "</lf-options></lf-ask>" + _PARAGRAPH * 8 + "</div></lf-pane>"
    '<lf-pane id="seat-beside" label="Right"><div><p>A short pane beside it.</p></div>'
    "</lf-pane></div>",
    head="<style>#seat-panes { display: grid; grid-template-columns: 1fr 1fr;"
    " gap: var(--sp-4); } lf-ask h3 { text-align: justify; }</style>",
    layout="workspace",
)


def test_a_pin_in_a_pane_takes_one_seat_at_every_scroll(browser, serve):
    """A pin whose corner covers words is seated beside its target, and in a pane that
    seat is found in the pane's whole content, not the part it shows: seated against the
    shown part and the pane header's controls, the same obligation's pin stood 28px above its
    heading at one scroll and 55px down inside the obligation at another. Seated outside its
    target, a pin can leave the pane while its target is still in view, so it is
    withheld by where it stands rather than by where its target does."""
    page = open_page(browser, serve(SEATED_PANE_PAGE))
    resized(page, 1024, 600)
    body = page.locator("#seat-pane > div")
    pane_scroll_behavior(page, page.locator("#seat-pane"), "bounded")
    row = page.locator('.lf-margin-lane [data-lf-margin-for="seat-ask"]')
    expect(row).to_have_attribute("data-lf-place", "pin")

    def seat_at(gap):
        """The pin's offset from its obligation, laid out with the obligation `gap` below the pane's
        top, and where the pin's top stands against that top."""
        body.evaluate(
            """(body, gap) => {
              const ask = document.getElementById('seat-ask');
              body.scrollTop += ask.getBoundingClientRect().top
                - body.getBoundingClientRect().top - gap;
            }""",
            gap,
        )
        margins_laid_out(page)
        # Anchor positioning takes a scroll's offset at the next frame.
        return page.evaluate(
            """async () => {
              await new Promise((done) =>
                requestAnimationFrame(() => requestAnimationFrame(done)));
              const row = document.querySelector('[data-lf-margin-for="seat-ask"]');
              const ask = document.getElementById('seat-ask').getBoundingClientRect();
              const pane = document.querySelector('#seat-pane > div')
                .getBoundingClientRect();
              const pin = row.getBoundingClientRect();
              return {
                withheld: row.classList.contains('lf-withheld'),
                dx: Math.round(pin.right - ask.right),
                dy: Math.round(pin.top - ask.top),
                above: Math.round(pane.top - pin.top),
              };
            }"""
        )

    far = seat_at(160)
    assert not far["withheld"], far
    near = seat_at(40)
    assert (near["dx"], near["dy"]) == (far["dx"], far["dy"]), (far, near)
    # Scrolled to the pane's top, the obligation's heading is in view, and the pin either
    # stands inside the pane at its seat or is withheld; it never stands above the pane.
    top = seat_at(2)
    assert top["withheld"] or (
        (top["dx"], top["dy"]) == (far["dx"], far["dy"]) and top["above"] <= 1
    ), (far, top)


@pytest.mark.parametrize("target_tree", ["shadow", "slotted"])
def test_a_row_follows_its_target_through_a_scroller_inside_a_shadow_tree(
    browser, serve, target_tree
):
    """Rendered ancestry owns motion and clipping, including a light-DOM target
    slotted into a shadow scrollport. A target in the shadow tree is anchored through
    the part the document names it by, so its row keeps its seat through the shadow
    scroller's scroll, then is withheld when its target leaves the view."""
    page = open_page(browser, serve(PANEL_PAGE))
    resized(page, 1440, 900)
    page.evaluate(
        """async (tree) => {
          const { contributionEntry, registerContribution } =
            await window.__lfWidgetApi();
          const host = document.createElement('div');
          const root = host.attachShadow({mode: 'open'});
          root.innerHTML = '<div id="inner" style="height: 100px; overflow: auto">'
            + '<div style="height: 40px"></div><p id="deep">Deep target</p>'
            + '<div style="height: 400px"></div></div>'
            + '<div id="wide" style="width: 100px; overflow: auto">'
            + '<div style="display: flex; width: 600px">'
            + '<p id="side" style="flex: none; width: 80px; margin: 0">Side</p>'
            + '</div></div>'
            + '<div style="height: 100px; overflow: auto">'
            + '<div style="height: 20px"></div><slot name="moved"></slot>'
            + '<div style="height: 400px"></div></div>';
          document.querySelector('main').prepend(host);
          let target = root.getElementById('deep');
          let side = root.getElementById('side');
          if (tree === 'slotted') {
            for (const [element, name] of [[target, 'deep'], [side, 'side']]) {
              const slot = document.createElement('slot');
              slot.name = name;
              element.replaceWith(slot);
              element.slot = name;
              host.append(element);
            }
          }
          const margin = registerContribution({key: 'deep', target,
            read: () => ({entries: [contributionEntry({
              key: 'deep', glyph: '!', label: 'deep controls'})]}),
            activate: () => {}});
          const sideways = registerContribution({key: 'side',
            target: side,
            read: () => ({entries: [contributionEntry({
              key: 'side', glyph: '!', label: 'side controls'})]}),
            activate: () => {}});
          window.__deep = {host, target, inner: root.getElementById('inner'), margin,
                           wide: root.getElementById('wide'), sideways};
        }""",
        target_tree,
    )
    rendered(page)
    offset = """() => {
      const {target, margin} = window.__deep;
      const row = margin.control('deep', 'margin').closest('.lf-margin-cluster');
      return {offset: row.getBoundingClientRect().top - target.getBoundingClientRect().top,
              withheld: row.classList.contains('lf-withheld')};
    }"""
    before = page.evaluate(offset)
    assert not before["withheld"], before
    if target_tree == "slotted":
        # Reassignment changes the geometry owner without changing any box's size.
        # The old and new roots must both hear their own subsequent scrolls.
        page.evaluate("() => { window.__deep.target.slot = 'moved'; }")
        rendered(page)
        reassigned = page.evaluate(offset)
        assert not reassigned["withheld"], reassigned
        assert reassigned["offset"] == pytest.approx(before["offset"], abs=1)
        page.evaluate("() => { window.__deep.target.slot = 'deep'; }")
        rendered(page)
        assert page.evaluate(offset) == before
    # A widget rendering its part attribute again takes the anchor's part with it, here
    # from the box the scroller carries beside the target, which the runtime gives back
    # before the row needs it.
    if target_tree == "shadow":
        page.evaluate(
            "() => window.__deep.inner.firstElementChild.setAttribute('part', 'own')"
        )
        rendered(page)
        page.evaluate("() => { window.__deep.inner.scrollTop = 10; }")
        rendered(page)
        kept = page.evaluate(offset)
        assert kept["offset"] == pytest.approx(before["offset"], abs=1), kept
        page.evaluate("() => { window.__deep.inner.scrollTop = 0; }")
        rendered(page)
    # A mutation remeasures placement in the scroll's own task, before another
    # frame can sample its native translation. The row must keep following.
    page.evaluate("""() => {
      window.__deep.inner.scrollTop = 20;
      window.__deep.target.classList.add('after-scroll');
    }""")
    rendered(page)
    after = page.evaluate(offset)
    assert after["offset"] == pytest.approx(before["offset"], abs=1), (before, after)
    page.evaluate("() => { window.__deep.inner.scrollTop = 200; }")
    rendered(page)
    assert page.evaluate(offset)["withheld"]

    side = """() => window.__deep.sideways.control('side', 'margin')
      .closest('.lf-margin-cluster').classList.contains('lf-withheld')"""
    assert not page.evaluate(side)
    page.evaluate("() => { window.__deep.wide.scrollLeft = 200; }")
    rendered(page)
    assert page.evaluate(side), "a target scrolled sideways out of view keeps its row"


LOG_ROW_FILLER = "".join(
    f"<p>Filler paragraph {n}, long enough to occupy a line of reading.</p>"
    for n in range(20)
)


LOG_ROW_PAGE = leaf_page(
    "a comment in a bounded log",
    f'<h1 id="t">Deploy</h1>{LOG_ROW_FILLER}<div id="log" data-bound="end">'
    + "".join(
        f'<p id="entry-{n}">Entry {n}: the deploy copied shard {n} to the new key.</p>'
        for n in range(60)
    )
    + f"</div>{LOG_ROW_FILLER}",
)


def test_a_row_in_a_bounded_log_stands_in_the_rail_inside_what_the_log_shows(
    browser, serve
):
    """A block that bounds its height scrolls what it holds, so its rows stand in a lane
    clipped to what the block shows. The rail beside the column is beside the block
    too, so the rows stay there rather than turning to pins over the entries; one whose
    entry the log has scrolled away is withheld, and one whose entry stands at the
    log's foot draws nothing past it."""
    page = open_page(
        browser,
        serve(LOG_ROW_PAGE, events=[_comment_on("entry-3"), _comment_on("entry-55")]),
    )
    resized(page, 1440, 900)
    log = page.locator("#log")
    page.evaluate(
        """log => { const at = log.getBoundingClientRect();
          document.scrollingElement.scrollBy({
            top: at.top + at.height / 2 - innerHeight / 2, behavior: 'instant'}); }""",
        log.element_handle(),
    )
    scroll_settled(page)
    margins_laid_out(page)
    early = page.locator('.lf-margin-cluster[data-lf-margin-for="entry-3"]')
    late = page.locator('.lf-margin-cluster[data-lf-margin-for="entry-55"]')
    expect(late).to_have_attribute("data-lf-place", "rail")
    expect(late).not_to_have_class(re.compile(r"\blf-withheld\b"))
    expect(early).to_have_class(re.compile(r"\blf-withheld\b"))

    # The late entry's top a few pixels inside the log's foot: its row, level with it,
    # reaches past the foot, and nothing of it is there to see or press.
    log.evaluate(
        """log => { const entry = document.getElementById('entry-55');
          log.scrollTop += entry.getBoundingClientRect().top
            - (log.getBoundingClientRect().bottom - 12); }"""
    )
    scroll_settled(page, "#log")
    margins_laid_out(page)
    expect(late).not_to_have_class(re.compile(r"\blf-withheld\b"))
    below = page.evaluate(
        """([row, log]) => {
          const at = row.getBoundingClientRect();
          const foot = log.getBoundingClientRect().bottom;
          const hit = document.elementFromPoint(
            (at.left + at.right) / 2, Math.min(at.bottom, foot + 12) - 2);
          return {reaches: at.bottom > foot + 4, hit: row.contains(hit)};
        }""",
        [late.element_handle(), log.element_handle()],
    )
    assert below["reaches"], below
    assert not below["hit"], "the row drew past the log's foot"

    log.evaluate("log => log.scrollTop = 0")
    scroll_settled(page, "#log")
    margins_laid_out(page)
    expect(early).not_to_have_class(re.compile(r"\blf-withheld\b"))
    expect(early).to_have_attribute("data-lf-place", "rail")
    expect(late).to_have_class(re.compile(r"\blf-withheld\b"))


TAB_PIN_PAGE = leaf_page(
    "a comment behind a tab",
    """
<h1 id="t">Views</h1>
<lf-tabs id="views">
  <lf-tab id="first-view" label="First"><p id="shown-para">Shown first.</p></lf-tab>
  <lf-tab id="second-view" label="Second"><p id="behind">Behind the second tab.</p></lf-tab>
</lf-tabs>
""",
)


def test_a_row_behind_an_inactive_tab_is_withheld(browser, serve):
    """An inactive tab keeps its content laid out under `content-visibility: hidden`,
    where an anchor is invalid and a row would be drawn wherever it stood with no
    anchor at all. The row is withheld instead — nothing drawn, nothing to Tab to — and
    comes back with its tab."""
    page = open_page(browser, serve(TAB_PIN_PAGE, events=[_comment_on("behind")]))
    resized(page, 1440, 900)
    margins_laid_out(page)
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="behind"]')
    expect(row).to_have_class(re.compile(r"\blf-withheld\b"))
    expect(row).to_be_hidden()
    page.get_by_role("tab", name="Second").click()
    margins_laid_out(page)
    expect(row).not_to_have_class(re.compile(r"\blf-withheld\b"))
    expect(row).to_be_visible()


STRIP_FILL = "".join(
    f"<p>Filler paragraph {n}, a line of reading.</p>" for n in range(40)
)


STRIP_PIN_PAGE = leaf_page(
    "a pin under a stuck tab strip",
    f"""
<lf-tabs id="views">
  <lf-tab id="first-view" label="First">
    {STRIP_FILL[:600]}<p id="under-strip">A finding the strip will stand over.</p>
    <pre id="under-code"><code>let answer = 42;
let question = unknown;</code></pre>{STRIP_FILL}
  </lf-tab>
  <lf-tab id="second-view" label="Second"><p>Second.</p></lf-tab>
</lf-tabs>
""",
    layout=None,
)


def test_a_pin_and_copy_pass_under_a_stuck_tab_strip(browser, serve):
    """A page's tab strip is a declared sticky header, and what scrolls under it passes
    under it: a pin whose target scrolls under the stuck strip is cut at the strip's
    foot, as the target's words are, so a press on the strip there reaches the strip,
    and so is a code block's Copy."""
    page = open_page(
        browser, serve(STRIP_PIN_PAGE, events=[_comment_on("under-strip")])
    )
    resized(page, 1280, 800)
    margins_laid_out(page)
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="under-strip"]')
    expect(row).to_have_attribute("data-lf-place", "pin")
    under = """selector => {
      const strip = document.querySelector('#views .lf-tabstrip');
      const box = document.querySelector(selector);
      const t = box.getBoundingClientRect(), s = strip.getBoundingClientRect();
      const hit = document.elementFromPoint((t.left + t.right) / 2, s.bottom - 4);
      return {top: t.top, strip: [s.top, s.bottom], hitStrip: strip.contains(hit),
              below: box.contains(document.elementFromPoint(
                (t.left + t.right) / 2, Math.min(t.bottom, s.bottom + 4) - 1))};
    }"""
    page.evaluate("""() => {
      const strip = document.querySelector('#views .lf-tabstrip');
      const t = document.querySelector('[data-lf-margin-for="under-strip"]').getBoundingClientRect();
      window.scrollBy(0, t.top - strip.getBoundingClientRect().height + 10);
    }""")
    rendered(page)
    pin = page.evaluate(under, '[data-lf-margin-for="under-strip"]')
    assert pin["strip"][0] < pin["top"] < pin["strip"][1], pin
    assert pin["hitStrip"], pin
    assert pin["below"], pin

    page.evaluate("""() => {
      const strip = document.querySelector('#views .lf-tabstrip');
      const t = document.getElementById('under-code').getBoundingClientRect();
      window.scrollBy(0, t.top - strip.getBoundingClientRect().top - 20);
    }""")
    rendered(page)
    code = page.locator("#under-code").bounding_box()
    page.mouse.move(code["x"] + 30, code["y"] + code["height"] - 4)
    expect(page.locator(".lf-code-copy")).to_have_class(
        re.compile("lf-code-copy-hover")
    )
    copy = page.evaluate(under, ".lf-code-copy")
    assert copy["strip"][0] < copy["top"] < copy["strip"][1], copy
    assert copy["hitStrip"], copy


def test_a_pane_row_withheld_at_load_stands_once_its_target_scrolls_in(browser, serve):
    """A row whose target starts below its pane's fold is withheld, and it is anchored
    all the same: once the pane scrolls its target in, the row stands on it rather than
    at the off-screen place an unanchored row would wait in."""
    page = open_page(browser, serve(PANE_PIN_PAGE, events=[_comment_on("pane-end")]))
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#pin-pane"), "bounded")
    margins_laid_out(page)
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="pane-end"]')
    expect(row).to_have_class(re.compile(r"\blf-withheld\b"))
    page.locator("#pin-pane > div").evaluate(
        "body => { body.scrollTop = body.scrollHeight; }"
    )
    expect(row).not_to_have_class(re.compile(r"\blf-withheld\b"))
    stands = row.evaluate(
        """row => {
          const r = row.getBoundingClientRect();
          const t = document.getElementById('pane-end').getBoundingClientRect();
          return Math.abs(r.top - t.top) < 2 && r.left < t.right + 40;
        }"""
    )
    assert stands


def test_an_authored_anchor_scope_leaves_margin_controls_reachable(browser, serve):
    """Margin coordinates do not cross the author's CSS anchor scope. Both scoped
    and ordinary targets keep their controls reachable, with the same target and
    row identities when the scope changes."""
    source = leaf_page(
        "a scoped note",
        '<h1 id="t">Scoped</h1><p id="flow">In the flow.</p>'
        '<div id="scope" style="anchor-scope: all"><p id="fixed-note">Behind a scope.</p>'
        '<p id="sticky-note" style="position: sticky; top: 0">Sticky behind it.</p></div>',
    )
    page = open_page(
        browser,
        serve(
            source,
            events=[
                _comment_on("fixed-note"),
                _comment_on("flow"),
                _comment_on("sticky-note"),
            ],
        ),
    )
    resized(page, 1440, 900)
    margins_laid_out(page)
    margins_laid_out(page)
    stuck = page.locator('.lf-margin-cluster[data-lf-margin-for="fixed-note"]')
    flow = page.locator('.lf-margin-cluster[data-lf-margin-for="flow"]')
    expect(flow).to_be_visible()
    expect(stuck).to_be_visible()
    # A sticky target's row stands in a carrier, anchored outside the scope its own
    # name could not leave, so it stands level with its target rather than at the
    # anchor's fallback off the page.
    sticky = page.locator('.lf-margin-cluster[data-lf-margin-for="sticky-note"]')
    expect(sticky).to_be_visible()
    assert sticky.bounding_box()["y"] == pytest.approx(
        page.locator("#sticky-note").bounding_box()["y"], abs=12
    )

    # The author's scope can change while the target and its row keep their identity.
    page.locator("#scope").evaluate("el => el.style.anchorScope = 'none'")
    margins_laid_out(page)
    expect(stuck).to_be_visible()


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_a_constrained_target_carries_its_row_through_scroll(
    request, serve, subtests, engine
):
    """A sticky or fixed box between a target and its scroller moves the target as no
    scroll alone does, so its row's carrier is anchored to the target itself, which
    carries the row in the first frame after every scroll with no pass to reseat it.

    Sticky constraints can belong to the target or an ancestor, and a fixed target
    stays put through the document's scroll. Firefox draws a stuck target's row where
    the target would stand unstuck, and WebKit moves a fixed target's row with the
    document's scroll (notes/browser-support.md, "A stuck sticky anchor in Firefox",
    "An anchor under a fixed box in WebKit"). Chromium also reads the compositor's frames,
    which only it traces; WebKit checks the rectangles after each scroll.
    """
    page = open_page(request.getfixturevalue(engine), serve(PANEL_PAGE))
    resized(page, 1280, 900)
    # Each case adds its own scroller and row, replacing the case before; the fixed
    # target, which also lengthens the document, goes last.
    for position in ("sticky", "sticky-ancestor", "fixed"):
        with subtests.test(position=position):
            # The last case left the pointer where this case's target will stand.
            page.mouse.move(0, 0)
            page.evaluate(
                """async (position) => {
                  const {contributionEntry, registerContribution} =
                    await window.__lfWidgetApi();
                  if (window.__nonlinear) {
                    // The case before leaves its host, or its fixed target, and its row.
                    const {host, target, contribution} = window.__nonlinear;
                    contribution.unregister();
                    host.remove();
                    target.remove();
                  }
                  const host = document.createElement('div');
                  host.style.cssText = 'height: 300px; width: 400px; overflow: auto';
                  host.dataset.bound = 'start';
                  host.innerHTML = '<div style="height: 80px"></div>'
                    + '<div id="constraint"><p id="nonlinear-target" '
                    + 'style="height: 30px; margin: 0">Constrained passage.</p></div>'
                    + '<div style="height: 700px"></div>';
                  document.querySelector('main').prepend(host);
                  const target = host.querySelector('p');
                  if (position === 'sticky') host.querySelector('#constraint').replaceWith(target);
                  const constrained = position === 'sticky-ancestor'
                    ? host.querySelector('#constraint') : target;
                  constrained.style.position = position === 'fixed' ? 'fixed' : 'sticky';
                  constrained.style.top = position === 'fixed' ? '300px' : '0';
                  if (position === 'fixed') {
                    target.style.left = '180px'; target.style.width = '300px';
                    document.querySelector('main').append(target);
                    host.remove();
                    document.body.style.minHeight = '2000px';
                  }
                  const contribution = registerContribution({key: 'nonlinear', target,
                    read: () => ({entries: [contributionEntry({key: 'nonlinear',
                      glyph: '!', label: 'Constrained controls'})]}), activate: () => {}});
                  window.__nonlinear = {host, target, position, contribution};
                }""",
                position,
            )
            rendered(page)
            # Inserting the scroller can retain the old content by scrolling the page.
            # Put the newly registered target on screen before testing its inner scroll.
            page.evaluate("window.scrollTo(0, 0)")
            rendered(page)
            reading = """() => {
              const {target, contribution} = window.__nonlinear;
              const row = contribution.control('nonlinear', 'margin').closest('.lf-margin-cluster');
              const r = row.getBoundingClientRect(), t = target.getBoundingClientRect();
              return {offset: r.top-t.top, top: r.top, target: t.top,
                hit: row.contains(document.elementFromPoint(r.left+r.width/2, r.top+r.height/2)),
                withheld: row.classList.contains('lf-withheld')};
            }"""
            before = page.evaluate(reading)
            assert before["hit"] and not before["withheld"], before
            for scroll in (30, 80, 100, 150):
                page.evaluate(
                    """scroll => {
                      const {host, position} = window.__nonlinear;
                      if (position === 'fixed') window.scrollTo(0, scroll);
                      else host.scrollTop = scroll;
                    }""",
                    scroll,
                )
                rendered(page)
                after = page.evaluate(reading)
                assert after["offset"] == pytest.approx(before["offset"], abs=1), after
                assert after["hit"] and not after["withheld"], after
            if position == "fixed" or engine != "browser":
                continue
            # A rectangle read in the frame after a scroll shows where the last frame drew an
            # anchored box, so the compositor's own frames are what show it carried.
            page.evaluate(
                f"""() => {{
                  const {{host, target, contribution}} = window.__nonlinear;
                  host.scrollTop = 0;
                  host.id = 'constrained-host';
                  target.style.background = '{SUBJECT_MARK}';
                  contribution.control('nonlinear', 'margin').closest('.lf-margin-cluster')
                    .style.outline = '6px solid {FOLLOWER_MARK}';
                }}"""
            )
            rendered(page)
            box = page.locator("#nonlinear-target").bounding_box()
            page.mouse.move(box["x"] + 20, box["y"] + 40)
            assert_follows_in_every_frame(page, "#constrained-host")


def test_distant_margin_coordinates_follow_small_moves_without_restatement(
    browser, serve
):
    """Document coordinates retain layout precision beyond CSS length serialization."""
    page = open_page(browser, serve(PANEL_PAGE))
    resized(page, 1280, 900)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          const main = document.querySelector('main');
          const space = document.createElement('div');
          space.style.cssText = 'position: relative; height: 1400000px';
          const target = document.createElement('p');
          target.id = 'distant-margin-target';
          target.textContent = 'A distant passage';
          target.style.cssText = 'position: absolute; left: 40px; top: var(--target-y);'
            + 'width: 300px; height: 30px; margin: 0';
          target.style.setProperty('--target-y', '1234567.578125px');
          space.append(target); main.append(space);
          const contribution = registerContribution({key: 'distant', target,
            read: () => ({entries: [contributionEntry({key: 'distant',
              glyph: '!', label: 'Distant controls'})]}), activate: () => {}});
          window.__distantMargin = {target, contribution};
        }"""
    )
    page.locator("#distant-margin-target").scroll_into_view_if_needed()
    rendered(page)
    reading = """() => {
      const {target, contribution} = window.__distantMargin;
      const row = contribution.control('distant', 'margin').closest('.lf-margin-cluster');
      return {target: target.getBoundingClientRect().top, row: row.getBoundingClientRect().top};
    }"""
    before = page.evaluate(reading)
    for delta in (1, 2, 4):
        page.locator("#distant-margin-target").evaluate(
            "(target, y) => target.style.setProperty('--target-y', `${y}px`)",
            1234567.578125 + delta,
        )
        page.wait_for_function(
            """expected => {
              const {contribution} = window.__distantMargin;
              const row = contribution.control('distant', 'margin').closest('.lf-margin-cluster');
              return row.getBoundingClientRect().top === expected;
            }""",
            arg=before["row"] + delta,
        )
        after = page.evaluate(reading)
        assert after["target"] - before["target"] == delta, after
    # The shared browser write watch rejects any unchanged style during these passes.
    for _ in range(3):
        page.evaluate("window.dispatchEvent(new Event('resize'))")
        rendered(page)


@pytest.mark.parametrize(
    "pane",
    ['style="height:160px;overflow:auto"', 'data-bound="start" style="height:160px"'],
    ids=["box", "reading-region"],
)
def test_a_quoted_passage_scrolled_out_of_its_pane_withholds_its_row(
    browser, serve, pane
):
    """A passage's row is about its words, so where a pane shows its paragraph but has
    scrolled the quoted words out of view, the row is withheld rather than standing
    beside other words, and it comes back when the pane brings the words in."""
    text = " ".join(
        f"Sentence number {i} says something about the release." for i in range(40)
    )
    body = (
        f'<h1>Pane</h1><div id="pane" {pane}>'
        f'<p id="long">{text} Finally the last words land.</p></div>'
    )
    events = [
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "On its end",
            "anchor": {"section": "long", "quote": "the last words land"},
        }
    ]
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = open_page(
        browser, serve(leaf_page("Pane", body), events=events), context=context
    )
    margins_laid_out(page)
    row = page.locator('[data-lf-margin-for="long"]')
    expect(row).to_have_class(re.compile(r"\blf-withheld\b"))
    page.locator("#pane").evaluate("pane => { pane.scrollTop = pane.scrollHeight; }")
    margins_laid_out(page)
    expect(row).not_to_have_class(re.compile(r"\blf-withheld\b"))
    # Scrolling alone, with no layout announced, takes the words away again, within a
    # frame or two rather than at some later pass.
    page.locator("#pane").evaluate("pane => { pane.scrollTop = 0; }")
    expect(row).to_have_class(re.compile(r"\blf-withheld\b"))
