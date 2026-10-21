"""Focus rings and element contours: one ring for every control, under reduced motion
and forced colors, and the ring and focus-stop readings that check them."""

import io
import re

import pytest
from interact_support import append_carried_log_record, element_declaration
from leaf import data as data_model
from leaf.render_checks import rendered
from PIL import Image
from playwright.sync_api import expect
from render_cases_layout import (
    mark_edges,
    ring_faults,
    rings_drawn,
    standing_ring,
    token_colour,
)
from render_harness import (
    EXAMPLES,
    LONG_PAGE,
    REPLAYED_PAGE,
    any_suggestion_control,
    leaf_page,
    open_page,
    page_comment,
    panel_settled,
    scroll_settled,
)

from browser.controls import (
    RING_NEW_STOP,
)

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("reading", ["markdown", "boxed-tab", "page-tab"])
def test_a_scrolled_tab_keeps_its_focus_ring_at_the_viewport(browser, serve, reading):
    """Code cannot cover the ring or carry it away with the scrolling content."""
    code = "".join(f"const result_{i} = await compute({i});\n" for i in range(100))
    if reading == "markdown":
        content = (
            '<lf-text-document id="document" source="draft" preview="markdown" '
            'label="Draft"></lf-text-document>'
        )
        ident = "document--preview"
    else:
        content = (
            '<lf-tabs id="readings"><lf-tab id="log" label="Log" data-bound="start">'
            f"<pre>{code}</pre></lf-tab>"
            '<lf-tab id="notes" label="Notes"><p>Notes.</p></lf-tab></lf-tabs>'
        )
        if reading == "boxed-tab":
            content = f"<section>{content}</section>"
        ident = "log"
    url = serve(leaf_page("Read the code", "<h1>Read the code</h1>" + content))
    if reading == "markdown":
        data_model.cmd_data_set(serve.page_dir, "draft", f"```js\n{code}```\n")
    page = open_page(browser, url)
    page.get_by_role("tab").first.click()
    page.keyboard.press("Tab")
    panel = page.locator(f"#{ident}")
    expect(panel).to_be_focused()
    page.keyboard.press("PageDown")
    page.wait_for_function(
        "id => document.getElementById(id).scrollTop > 100", arg=ident
    )
    scroll_settled(page, f"#{ident}")
    accent = tuple(int(n) for n in re.findall(r"\d+", token_colour(page, "--accent")))
    edges = mark_edges(page, ident, accent)
    assert all(min(widths) >= 1 for widths in edges.values()), edges


def test_an_open_part_wears_a_tab_panels_ring_on_its_own_edge(browser, serve):
    """A part is a tab panel under another tag, so it is ringed as one is: inset from
    its border box, whose start edge here is the rule between the list and the part.

    The holder draws that ring while it lays out as `display: contents`, so the ring
    reading must still find and measure it: a cover over the run is reported."""
    para = "<p>" + "Words that fill the part's measure. " * 30 + "</p>"
    url = serve(
        leaf_page(
            "Parts",
            '<h1>Parts</h1><lf-parts id="parts">'
            f'<lf-part id="first" label="First"><article class="layout-column">{para}'
            "</article></lf-part>"
            '<lf-part id="second" label="Second"><article class="layout-column">'
            "<p>Second.</p></article></lf-part></lf-parts>",
            layout=None,
        )
    )
    page = open_page(browser, url)
    page.get_by_role("tab", name="First").click()
    page.keyboard.press("Tab")
    expect(page.locator("#first")).to_be_focused()
    rendered(page)
    drawn = rings_drawn(page)
    ring = next((seen for seen in drawn if seen["sample"] and seen["here"]), None)
    assert ring, drawn
    assert ring["cuts"] == ring["covers"] == [], ring

    box = page.locator("#first").bounding_box()
    clip = {"x": round(box["x"]), "y": round(box["y"] + 40), "width": 4, "height": 1}
    shot = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    accent = tuple(int(n) for n in re.findall(r"\d+", token_colour(page, "--accent")))
    assert shot.getpixel((0, 0)) == accent, [shot.getpixel((x, 0)) for x in range(4)]

    page.evaluate(
        """(x) => {
      const band = document.body.appendChild(document.createElement('div'));
      band.style.cssText = `position: absolute; z-index: 99999; background: red;
        left: ${x}px; top: 0; width: 2px; height: 100vh;`;
    }""",
        box["x"],
    )
    covered = next(seen for seen in rings_drawn(page) if seen["who"] == ring["who"])
    assert any("left edge is under" in cover for cover in covered["covers"]), covered


def test_controls_share_pointer_and_keyboard_focus_rings(browser, serve):
    """Focus has one ring for native controls, linked carriers, and shadow controls."""
    declaration = element_declaration("lf-shadow-focus", upgrade=True)
    declaration["x-shadow"] = True
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Focus routes",
                """
<h1 id="focus-heading">Focus routes</h1>
<p><button class="button" id="focus-button" type="button">Ordinary button</button></p>
<lf-tabs id="focus-tabs">
  <lf-tab id="focus-first" label="First">First panel.</lf-tab>
  <lf-tab id="focus-second" label="Second">Second panel.</lf-tab>
</lf-tabs>
<lf-ask id="focus-decision"><h2>Which option?</h2>
<lf-options id="focus-options" choose>
  <lf-option id="focus-choice" for="focus-heading">Keep this option.</lf-option>
  <lf-option id="focus-peer" for="focus-heading">Keep another option.</lf-option>
</lf-options></lf-ask>
<lf-shadow-focus id="focus-shadow"><button class="button" type="button">Shadow button</button></lf-shadow-focus>
""",
            ),
            layer_registry={"lf-shadow-focus": declaration},
            layer_widgets={
                "lf-shadow-focus.js": """
import {once, offer, shadowStage} from '/runtime/widget-api.js';
customElements.define('lf-shadow-focus', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const select = offer('select', '');
    select.ariaLabel = 'Choose a route';
    select.value = 'first';
    for (const [value, label] of [['first', 'First route'], ['second', 'Second route']]) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      select.append(option);
    }
    shadowStage(this, [...this.childNodes, select]);
  }
});
"""
            },
        ),
    )
    paint = """el => { const s = getComputedStyle(el); return {
      style: s.outlineStyle, width: s.outlineWidth, color: s.outlineColor,
      offset: s.outlineOffset
    }; }"""
    button = page.locator("#focus-button")
    tab = page.get_by_role("tab", name="First", exact=True)
    choice = page.locator("#focus-choice > .lf-pick")
    shadow_button = page.locator("#focus-shadow").get_by_role(
        "button", name="Shadow button", exact=True
    )
    for control, carrier in (
        (button, button),
        (tab, tab.locator(".lf-tab-name")),
        (choice, page.locator("#focus-choice")),
        (shadow_button, shadow_button),
    ):
        control.click()
        expect(control).to_be_focused()
        rendered(page)
        pointer = carrier.evaluate(paint)
        assert pointer["style"] == "solid", pointer
        drawn = rings_drawn(page)
        samples = [ring for ring in drawn if ring["sample"]]
        assert len(samples) == 1 and samples[0]["rule"], drawn
        assert not ring_faults(drawn, "after pointer arrival")

        # Return by sequential navigation to cover the tab list's roving stop and
        # the option row's carrier through a real keyboard arrival.
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        expect(control).to_be_focused()
        rendered(page)
        assert carrier.evaluate(paint) == pointer
        drawn = rings_drawn(page)
        assert [ring["rule"] for ring in drawn if ring["sample"]] == [
            samples[0]["rule"]
        ], drawn
        assert not ring_faults(drawn, "after keyboard arrival")

    assert page.locator("#focus-shadow").evaluate(paint)["style"] == "none", (
        "retargeting focus to the widget host drew a second ring around its button"
    )

    select = page.locator("#focus-shadow select")

    def one_select_ring(control, where):
        expect(control).to_be_focused()
        expect(control).to_be_visible()
        rendered(page)
        drawn = rings_drawn(page)
        assert len(drawn) == 1 and drawn[0]["sample"], (where, drawn)
        assert not ring_faults(drawn, where)

    select.focus()
    one_select_ring(select, "on the native select")
    select.press("ArrowDown")
    expect(select).to_have_value("second")
    one_select_ring(select, "after choosing the next native option")
    select.press("ArrowUp")
    expect(select).to_have_value("first")
    one_select_ring(select, "after returning to the first native option")
    shadow_button.click()
    one_select_ring(shadow_button, "after leaving the select")
    expect(select).not_to_have_attribute("data-lf-focus-within", "")


def test_forced_colors_restore_a_real_outline_to_shadow_focused_fields(browser, serve):
    """High-contrast mode keeps a real outline on the focused comment frame."""
    context = browser.new_context(
        viewport={"width": 420, "height": 800}, forced_colors="active"
    )
    page = open_page(browser, serve(LONG_PAGE), context=context)
    box = page_comment(page)
    focus = box.evaluate(
        "el => { const s = getComputedStyle(el.closest('.lf-compose-field'));"
        " return {style: s.outlineStyle, width: s.outlineWidth}; }"
    )
    assert focus["style"] != "none" and focus["width"] != "0px", focus


def test_a_marked_element_draws_nothing_under_the_pointer(browser, serve):
    """An element's comment draws no contour at rest, nor while the pointer rests inside
    the element, which is where a reader's mouse sits. The hand still says a press opens
    the thread."""
    context = browser.new_context(
        viewport={"width": 1801, "height": 900},
        color_scheme="light",
        device_scale_factor=2,
    )
    url = serve(REPLAYED_PAGE)
    for ident in ("approach", "col-doing"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "Say more about this.",
                "anchor": {"section": ident},
            },
        )
    page = open_page(browser, url, context=context)
    ink = tuple(int(n) for n in re.findall(r"\d+", token_colour(page, "--mark-ink")))
    for ident in ("approach", "col-doing"):
        target = page.locator(f"#{ident}")
        expect(target).to_have_class(re.compile(r"\blf-mark-el\b"))
        target.evaluate(
            "node => node.scrollIntoView({block: 'center', inline: 'nearest', "
            "behavior: 'instant'})"
        )
        box = target.bounding_box()
        inside = (box["x"] + 6, box["y"] + box["height"] / 2)
        page.mouse.move(*inside)
        expect(page.locator("body")).to_have_class(re.compile(r"\blf-over-mark\b"))
        expect(page.locator(f'.lf-visual-mark[data-for="{ident}"]')).to_have_count(0)
        rest = mark_edges(page, ident, ink)
        assert all(seen == {0} for seen in rest.values()), (
            f"the comment on #{ident} drew a contour under the pointer: {rest}"
        )


# A page holding a paragraph and one control, for the readings below that plant the
# shape they are about rather than finding it in the product: which of the layer's
# controls draws an inset ring, or names no z-index, moves with the product and is not
# what these readings are held to.
RING_PROBE_PAGE = leaf_page(
    "ring",
    "<h1>Ring</h1><p>Words.</p>"
    '<div id="ring-holder"><button id="ring-control" type="button">Control</button></div>'
    "<p>After.</p>",
)


def test_the_ring_reading_names_every_way_a_box_can_draw_nothing_past_its_edge(
    browser, serve
):
    """Overflow is one of three, and the other two leave `overflow` computing `visible`.

    The gate below reports a cut ring by asking each box on the way up what band it
    shows. A reading that knows only `overflow` answers "nothing is wrong" for a box that
    clips by paint containment or by `content-visibility`, and answers it in the same
    words it uses when nothing is wrong — which is why the corpus staying green could not
    have told anyone. `shownBand` is the product's own reading and names all three; this
    holds the probe to it rather than to a copy free to drift from it again.

    One control, one ring pushed out past its box, three parents differing only in how
    they clip. The first case is the control: without it a reading that reported at every
    stop would pass the other three and prove nothing.
    """
    example = next(e for e in EXAMPLES if e.stem == "release-notes")
    url = serve(example, comments=2, seed_log=False)
    page = open_page(browser, url)
    any_suggestion_control(page, "accept").first.focus()
    # The probe's control must begin clear of the viewport edge. Its subject is each
    # ancestor's clipping behavior, not where the corpus happened to place this button.
    page.evaluate("document.activeElement.scrollIntoView({block: 'center'})")

    plant = """(how) => {
      const el = document.activeElement;
      const p = el.parentElement;
      p.style.overflow = p.style.contain = p.style.contentVisibility = '';
      // The ring past the parent's edge with the control still inside it. Moving the
      // control out instead takes its own edge out of the box too, and a box is held to
      // a ring only on the sides where it is showing the control's own edge — so all
      // three cases below would be declined for the reason the control case is.
      el.style.outlineOffset = '8px';
      if (how === 'overflow') p.style.overflow = 'hidden';
      if (how === 'contain') p.style.contain = 'paint';
      if (how === 'content-visibility') p.style.contentVisibility = 'auto';
      const s = getComputedStyle(p);
      return `${s.overflowX}/${s.contain}/${s.contentVisibility}`;
    }"""

    clean = page.evaluate(plant, "none")
    assert standing_ring(page)["cuts"] == [], (
        f"the displaced ring is reported cut with nothing clipping it ({clean}), so the "
        "cases below would only be repeating whatever this reading always says"
    )
    for how in ("overflow", "contain", "content-visibility"):
        style = page.evaluate(plant, how)
        cuts = standing_ring(page)["cuts"]
        assert any("left edge" in c for c in cuts), (
            f"a parent clipping by {how} ({style}) drew the ring away and the reading "
            f"said {cuts}"
        )


def test_the_ring_reading_distinguishes_element_marks_from_focus(browser, serve):
    """The reading ignores element contours and still recognizes the real focus ring.

    A hovered passage deliberately shares the ring's accent and width but its rule
    writes the contour out rather than drawing the ring's token, so the browser's
    answer for which rule drew it keeps it out of the population of keyboard rings. The
    focus state on that same element, a token ring on a plain box, and a contour on a
    focused mark follow as positive controls; without them a reading that ignored all
    element contours would pass the first case and prove only that it was silent."""
    example = next(e for e in EXAMPLES if e.stem == "release-notes")
    url = serve(example, comments=2, seed_log=False)
    page = open_page(browser, url)
    any_suggestion_control(page, "accept").first.focus()

    plant = """(how) => {
      const box = document.querySelector('main p');
      box.classList.toggle('probe-target', true);
      for (const name of ['lf-mark-el', 'lf-mark-hover'])
        box.classList.toggle(name, false);
      box.toggleAttribute('data-lf-focus', how === 'focused mark');
      box.style.outline = '';
      if (how === 'mark') box.classList.add('lf-mark-el', 'lf-mark-hover');
      if (how === 'focused mark') box.classList.add('lf-mark-el');
      if (how === 'the ring itself') box.style.outline = 'var(--focus-ring)';
      if (how === 'contour on a focused mark') {
        box.classList.add('lf-mark-el');
        box.style.outline = 'var(--focus-ring-w) solid var(--accent)';
        box.tabIndex = -1;
        box.focus();
      }
      const cs = getComputedStyle(box);
      return [cs.outlineStyle, cs.outlineWidth, cs.outlineColor];
    }"""

    def claimed():
        """The reading's ring claims for this one box.

        Asked of the box rather than of how many rings the page has: the runtime
        repaints the panel on its own schedule, so two whole-page counts taken a moment
        apart differ for reasons that have nothing to do with what was planted here.
        """
        return [
            seen
            for seen in rings_drawn(page)
            if seen["here"] and "probe-target" in seen["who"]
        ]

    page.evaluate(plant, "none")
    assert not claimed(), "the box is called a ring before anything is painted on it"
    standing = standing_ring(page)
    assert standing and standing["here"], (
        "no ring is painted with the keyboard on a control, so the reading is silent "
        "here and would pass this test however it behaved"
    )

    mark_paint = page.evaluate(plant, "mark")
    style, _width, colour = mark_paint
    assert style == "solid", "the element comment lost its complete contour"
    assert not claimed(), (
        f"the reading counted the mark ({colour}) as a focus ring: {claimed()}"
    )

    _style, _width, colour = page.evaluate(plant, "focused mark")
    focused_claims = claimed()
    assert [".lf-mark-el" in seen["rule"] for seen in focused_claims] == [True], (
        f"the marked element's focus ring ({colour}) was not credited to its rule: "
        f"{focused_claims}"
    )

    ring_paint = page.evaluate(plant, "the ring itself")
    assert mark_paint == ring_paint, (
        f"the mark paints {mark_paint} and the ring paints {ring_paint}, so the mark "
        "case above was kept out by paint rather than by the element-feedback role "
        "this reading now divides on"
    )
    ring_claims = claimed()
    assert [seen["rule"] for seen in ring_claims] == ["style attribute"], (
        f"a box wearing the layer's own ring ({ring_paint}) was not counted, so the cases "
        "above prove only that this reading is silent"
    )

    focused_mark_paint = page.evaluate(plant, "contour on a focused mark")
    focused_mark_claims = claimed()
    assert [seen["rule"] for seen in focused_mark_claims] == [""], (
        f"a focused element mark wearing a contour no ring rule drew "
        f"({focused_mark_paint}) was not counted: {focused_mark_claims}"
    )


def test_the_ring_reading_sees_and_measures_a_ring_cast_as_a_shadow(browser, serve):
    """The band has two carriers, and a reading that knew one was blind to the other.

    Most of the layer's rules draw the ring as an outline. A target hint the keyboard
    is browsing casts it as a shadow, on a chip in a layer nothing can focus. To a user
    those are the same band, and a sweep asking only the outline misses the shadow's
    indication and geometry.

    Knowing one on sight is the first half, and the layer offers three shadows to mistake
    for it: the elevation lift every floating surface wears, the inset accent wash a
    search match and an open draft wear, and the accent band a milestone's active dot
    wears at a width of its own. Offsets, blur, `inset` and the ring's own width are what
    separate the four, and nothing else does.

    Measuring it is the second half, and the one the corpus floor rests on. A spread has
    no offset, so the band's width is the whole of what the box draws past its edge — and
    a reading that never finds the band measures nought, drops the box without a word,
    and reports what a clean page reports. So the plant is a box standing on the window's
    own foot, where the band is the only part of it that can be outside the window, with
    the same box and the same place as the control once the band is taken off.
    """
    page = open_page(browser, serve(RING_PROBE_PAGE))

    # On the window's foot, so the only thing that can be outside the window is the band.
    # Placed from `innerHeight` rather than from `100vh`, which is the viewport a
    # scrollbar is not taken out of and so is the same number only while there is none.
    plant = """(how) => {
      const box = document.querySelector('main p');
      box.classList.toggle('probe-target', true);
      box.style.cssText = `position: fixed; left: 40px; top: ${innerHeight - 30}px;
        width: 120px; height: 30px; box-sizing: border-box; margin: 0`;
      if (how === 'a lift') box.style.boxShadow = '0 2px 8px var(--shade)';
      if (how === 'an inset wash')
        box.style.boxShadow = 'inset var(--focus-shadow)';
      if (how === 'a wider band')
        box.style.boxShadow = '0 0 0 calc(var(--focus-ring-w) + 1px) var(--accent)';
      if (how === 'the band itself')
        box.style.boxShadow = 'var(--focus-shadow)';
      const cs = getComputedStyle(box);
      return [cs.boxShadow, cs.outlineStyle, box.getBoundingClientRect().bottom,
              innerHeight];
    }"""

    def reading():
        """What the sweep says about this one box: whether it is a ring, and its cuts.

        Asked of the box and not of the page, because the runtime repaints the panel on
        its own schedule and two whole-page readings a moment apart differ for reasons
        that have nothing to do with what was planted here.
        """
        return next(
            (
                seen
                for seen in rings_drawn(page)
                if "probe-target" in seen["who"] and seen["here"]
            ),
            None,
        )

    for how in ("nothing", "a lift", "an inset wash", "a wider band"):
        shadow, outline, bottom, foot = page.evaluate(plant, how)
        assert outline == "none" and bottom == foot, (
            f"{how} left the box wearing {outline} at {bottom} of {foot}, so the reading "
            "was asked about a box other than the one this is written against"
        )
        assert reading() is None, (
            f"the reading counted {how} ({shadow}) as the focus ring: {reading()}"
        )

    shadow, outline, bottom, foot = page.evaluate(plant, "the band itself")
    seen = reading()
    assert seen, (
        f"a box casting the layer's own band ({shadow}) was not counted, so the four "
        "cases above prove only that this reading is silent"
    )
    # And the band is measured, not merely noticed: the box's own edge is on the window's
    # foot, so the width reported outside it is the whole of the band and nothing else.
    width = page.evaluate(
        "() => parseFloat(getComputedStyle(document.documentElement)"
        "  .getPropertyValue('--focus-ring-w'))"
    )
    assert any(
        f"its bottom edge is {width:g}px outside the window" in cut
        for cut in seen["cuts"]
    ), (
        f"the band stood {width}px past the window's foot and the reading said "
        f"{seen['cuts']}, so nothing above measured it"
    )


def test_the_ring_reading_still_sees_what_is_painted_over_a_ring(browser, serve):
    """The half that answers by hit test, held to firing where it can and not where it

    cannot. It takes whatever the ring's own pixels hit as standing over them, and an
    outline is painted by its control at its control's level while an outline's pixels
    are not hit-testable — so a sample outside the control's box returns whatever is
    beneath. That is sound while the control's surface takes hits and unsound inside one
    that does not, where the answer comes back inverted: the old shortcut bar stood over
    the page at z-index 8940 with `pointer-events: none`, and the code under its More
    button read as standing over it.

    So the reading declines inside such a surface, and that is a way for it to go quiet
    everywhere by accident. The plant is the population assertion: thin enough to lie
    over the ring and not over the control, because a cover across the control's own body
    is excused on purpose — a control put where something stands over it is a fact about
    where it was put, not about its ring leaving its box.
    """
    page = open_page(browser, serve(RING_PROBE_PAGE))
    page.locator("body").click()
    # Reach the stop by keyboard before testing what can cover its ring.
    page.locator("#ring-control").focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    assert standing_ring(page), "no ring is drawn, so nothing is covered"

    assert standing_ring(page)["covers"] == [], (
        "the control is reported covered before anything is put over it"
    )
    page.evaluate(
        """() => {
          const b = document.activeElement.getBoundingClientRect();
          const d = document.createElement('div');
          // Over the ring's top run and clear of the control's own box.
          d.style.cssText = `position: fixed; z-index: 99999; background: red;
            left: ${b.left - 8}px; top: ${b.top - 5}px;
            width: ${b.width + 16}px; height: 4px;`;
          document.body.append(d);
        }"""
    )
    assert any("top edge is under" in c for c in standing_ring(page)["covers"]), (
        "a band laid over the ring's top run was not reported, so this reading answers "
        "nothing and the pages it passes are not evidence"
    )


def test_the_ring_reading_passes_over_a_neighbour_the_control_paints_across(
    browser, serve
):
    """The same half held to the other order, which it read backwards. An outline is
    painted by its control at its control's level, so a box the control stands in front
    of cannot stand over the ring around it — but the hit test that answers this half
    samples the band outside the control's box, where whatever is beneath comes back.

    The side panel's edge grip was the shape that made that matter: it floated over the
    threads at z-index 1, so its band crossed their own lines at every width and scroll
    position, and the reading named whichever line it happened to land on. A two-pixel
    change to a card's padding (#374) put a receipt under the grip's foot and took a
    resize test down with nothing about the page wrong. The plant keeps that shape: a
    control at z-index 1 in a positioned holder.

    So: one neighbour under the grip's band and clear of its box, planted three times —
    where the grip paints across it, where a z-index of its own lifts it past the grip,
    and where it is `position: fixed` inside a static box that ranks behind the grip. The
    lifted half is the population assertion; a reading gone quiet would pass the others on
    its own. The third is the grip's `z-index: 1` again: a neighbour that names no z-index
    paints in the layer below it whatever holds it, so leaving its holder's flow does not
    put it over the ring, and the reading that reported it there would be inventing a
    cover the page does not paint.
    """
    page = open_page(browser, serve(RING_PROBE_PAGE))
    page.evaluate(
        """() => {
          document.getElementById('ring-holder').style.position = 'relative';
          const control = document.getElementById('ring-control');
          control.style.cssText = `position: relative; z-index: 1;
            outline: var(--focus-ring); outline-offset: 2px;`;
          control.focus();
        }"""
    )
    standing = standing_ring(page)
    assert standing and standing["covers"] == [], (
        f"the control is reported covered before anything is put over it: {standing}"
    )

    # A band under the grip's right ring run and clear of its own box, inside a holder
    # beside the grip. The holder is what the reading can rank, and putting the band
    # in the page leaves it with nothing to rank against. Neither paints anything the
    # grip does not already stand in front of, until the band names the z-index that
    # lifts it past.
    plant = """({z, wrap, isolate = false}) => {
      document.querySelector('.lf-under-plant')?.remove();
      const grip = document.getElementById('ring-control');
      const cs = getComputedStyle(grip);
      const grow = parseFloat(cs.outlineWidth) + parseFloat(cs.outlineOffset);
      const b = grip.getBoundingClientRect();
      const mid = (Math.max(b.top - grow, 0) + Math.min(b.bottom + grow, innerHeight)) / 2;
      const holder = document.getElementById('ring-holder')
        .appendChild(document.createElement('div'));
      holder.className = 'lf-under-plant';
      Object.assign(holder.style, {position: 'absolute', inset: '0'});
      // A static box filling that holder, when the plant wants one: it is what the walk
      // ranks then, and it stands in the flow where the grip is painted over it.
      const under = wrap ? holder.appendChild(document.createElement('div')) : holder;
      if (wrap) Object.assign(under.style, {height: '100%'});
      // A static stacking context around the band, which orders the band's z-index inside
      // it and paints in the positioned layer around it.
      if (isolate) under.style.opacity = '0.99';
      const band = under.appendChild(document.createElement('div'));
      Object.assign(band.style, {
        position: 'fixed', background: 'red',
        left: `${b.right}px`, top: `${mid - 20}px`,
        width: `${grow + 1}px`, height: '40px',
      });
      if (z) band.style.zIndex = String(z);
      return grow;
    }"""

    grow = page.evaluate(plant, {"z": 0, "wrap": False})
    assert grow > 0, (
        f"the grip draws its ring {grow}px outside its box, so there is no band outside "
        "it to lay anything under and this holds nothing"
    )
    assert standing_ring(page)["covers"] == [], (
        "a neighbour the grip paints across was read as standing over its ring"
    )

    page.evaluate(plant, {"z": 2, "wrap": False})
    covers = standing_ring(page)["covers"]
    assert any("right edge is under" in c for c in covers), (
        f"the same band lifted past the grip by a z-index of its own read as {covers}, "
        "so the half above passed on a reading that answers nothing"
    )

    # The same band inside a static box, which is the shape that leaves a holder's flow:
    # it paints in the positioned layer rather than the one its holder is ranked in. That
    # is still the layer under the grip's own, so the page paints the grip in front and
    # the reading has nothing to report.
    page.evaluate(plant, {"z": 0, "wrap": True})
    covers = standing_ring(page)["covers"]
    assert covers == [], (
        f"a band the grip's own z-index stands over read as {covers}, so leaving a "
        "holder's flow was taken for standing over the control that names one"
    )

    # A band whose z-index orders it inside a static stacking context: the walk goes on
    # from that context, so the reading has to agree with the pixels the page paints on
    # the ring's run there, red where the band stands over it.
    for z in (1, 2):
        page.evaluate(plant, {"z": z, "wrap": True, "isolate": True})
        x, y = page.evaluate("""() => {
          const grip = document.getElementById('ring-control');
          const cs = getComputedStyle(grip);
          const b = grip.getBoundingClientRect();
          return [b.right + parseFloat(cs.outlineOffset) + parseFloat(cs.outlineWidth) / 2,
                  (b.top + b.bottom) / 2];
        }""")
        shot = page.screenshot(
            clip={"x": x - 0.5, "y": y - 0.5, "width": 1, "height": 1}
        )
        red, green, blue = Image.open(io.BytesIO(shot)).convert("RGB").getpixel((0, 0))
        painted = red > 200 and green < 80 and blue < 80
        covers = standing_ring(page)["covers"]
        assert bool(covers) == painted, (
            f"a band inside a stacking context at z-index {z} read as {covers} while "
            f"the page {'paints' if painted else 'does not paint'} it over the ring"
        )

    page.evaluate("() => document.querySelector('.lf-under-plant').remove()")


def test_the_ring_reading_sees_a_neighbour_lifted_out_of_the_flow_it_was_ranked_in(
    browser, serve
):
    """The other side of the half above, against a control that names no z-index.

    The reading excuses a neighbour by ranking the box that holds it, and a box that
    ranks behind the control puts what stays in its flow behind the control too. A
    positioned neighbour does not stay: it leaves its holder's place in the flow to paint
    in the positioned layer of the nearest ancestor stacking context, which is the layer a
    control with `position: relative; z-index: auto` is in (a thread card's buttons). So
    a static holder's rank says nothing about it, and taken for an answer it drops a
    cover the page paints.

    The plant is that shape: a fixed band over the ring's top run, held by a static box
    beside the control. The band comes back topmost where the ring is sampled, and the
    reading has to say so. The clean reading first, because a reading that reports at
    every control would pass the planted one without seeing it.
    """
    page = open_page(browser, serve(RING_PROBE_PAGE))
    page.evaluate(
        """() => {
          const control = document.getElementById('ring-control');
          control.style.cssText = `position: relative; z-index: auto;
            outline: var(--focus-ring); outline-offset: 2px;`;
          control.focus();
        }"""
    )
    standing = standing_ring(page)
    assert standing and standing["covers"] == [], (
        f"the control is reported covered before anything is put over it: {standing}"
    )

    page.evaluate(
        """() => {
          const b = document.activeElement.getBoundingClientRect();
          // A static box, so the flow is what its own rank answers for, pulled back over
          // the control it is appended beside rather than adding height under it.
          const holder = document.createElement('div');
          holder.style.cssText = 'margin-top: -100vh; height: 100vh;';
          const band = document.createElement('div');
          // Over the ring's top run and clear of the control's own box, and positioned,
          // so it leaves the holder's flow for the layer the control is in.
          band.style.cssText = `position: fixed; background: red;
            left: ${b.left - 8}px; top: ${b.top - 5}px;
            width: ${b.width + 16}px; height: 4px;`;
          holder.append(band);
          document.getElementById('ring-holder').append(holder);
        }"""
    )
    covers = standing_ring(page)["covers"]
    assert any("top edge is under" in c for c in covers), (
        f"a band standing over the ring read as {covers}, so a neighbour that left the "
        "flow its holder was ranked in goes unreported"
    )

    # The same band with a z-index of its own inside a static stacking context. The
    # z-index orders it only inside that context, which paints in the control's layer
    # after it, so the band still stands over the ring, and the walk that goes on from
    # the context has to say so rather than rank the static holder.
    page.evaluate(
        """() => {
          const band = document.querySelector('#ring-holder > div:last-child > div');
          const context = document.createElement('div');
          context.style.opacity = '0.99';
          band.style.zIndex = '1';
          band.replaceWith(context);
          context.append(band);
        }"""
    )
    covers = standing_ring(page)["covers"]
    assert any("top edge is under" in c for c in covers), (
        f"a band lifted inside a stacking context read as {covers}, so a z-index that "
        "orders a box only inside its context hid a cover the page paints"
    )

    # The same context standing before the control in the tree and overlapping it: it
    # paints as one unit in the control's layer, before the control, so the ring stands
    # over the band, as the page's pixels say. The context's own rank answers for it.
    page.evaluate(
        """() => {
          const context = document.querySelector('#ring-holder > div:last-child > div');
          Object.assign(context.style, {height: '100vh', marginBottom: '-100vh'});
          const holder = document.getElementById('ring-holder');
          holder.prepend(context);
          document.querySelector('#ring-holder > div:last-child').remove();
        }"""
    )
    x, y = page.evaluate("""() => {
      const b = document.activeElement.getBoundingClientRect();
      return [b.left + b.width / 2, b.top - 3];
    }""")
    shot = page.screenshot(clip={"x": x - 0.5, "y": y - 0.5, "width": 1, "height": 1})
    red, green, blue = Image.open(io.BytesIO(shot)).convert("RGB").getpixel((0, 0))
    assert not (red > 200 and green < 80 and blue < 80), (
        "the page paints the band over the ring here, so this case holds nothing"
    )
    covers = standing_ring(page)["covers"]
    assert covers == [], (
        f"a band inside a context the control paints over read as {covers}, so the "
        "walk hoisted the context past the rank that answers for it"
    )


def test_a_user_who_asked_for_no_motion_gets_a_ring_that_does_not_arrive(
    browser, serve
):
    """A duration is a way of keeping an animation and no way at all of keeping a
    transition. An animation is declared and named, and the layer reads `animationend`
    to know one has run, so the guard's near-zero duration keeps that event and spends
    no time on it. A transition is declared by nobody — `transition-property` is `all`
    until something says otherwise — so the same duration over every element made a
    transition out of every property that changed on any of them.

    None of which anybody wrote or listened for, and none of which was free: a ring is
    `outline-width`, `outline-offset` and `outline-color` all changing at once, so a
    user who asked for no motion got a medium currentColor ring at offset nought
    animating into the real one, on every focus, on every page. It is also what a
    computed-style reading of a ring taken in those frames was told, which is how
    `RINGS_DRAWN` came to invent one.

    So this asks the user's own question — is anything moving — of the control they
    just landed on, in the one setting where the answer has to be no."""
    url = serve(LONG_PAGE, comments=3)
    context = browser.new_context(reduced_motion="reduce")
    page = open_page(browser, url, context=context)
    assert page.evaluate(
        "() => matchMedia('(prefers-reduced-motion: reduce)').matches"
    ), "the context did not ask for reduced motion, so the guard under test is off"
    page.locator(".lf-fp-threads").click()
    panel_settled(page, view="threads")
    control = page.locator(".lf-fp-thread").first
    control.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")

    seen = page.evaluate(
        """() => {
          const el = document.activeElement;
          const cs = getComputedStyle(el);
          return {
            moving: el.getAnimations().map(
              (a) => a.transitionProperty || a.animationName || 'animation'),
            ring: [cs.outlineWidth, cs.outlineStyle, cs.outlineOffset],
            want: cs.getPropertyValue('--focus-ring').trim(),
          };
        }"""
    )
    assert seen["moving"] == [], (
        f"the ring is still arriving under reduced motion: {seen['moving']} are "
        "running, so what the user sees and what any reading of this control gets "
        "is a value on its way rather than the one the rule states"
    )
    # Non-vacuity: a control with no ring has nothing that could have transitioned.
    assert seen["ring"][:2] == [seen["want"].split()[0], "solid"], (
        f"the control reads {seen['ring']} where its ring is {seen['want']}, so "
        "nothing here was ever going to move"
    )


def test_the_ring_reading_sees_a_neighbour_paint_over_a_ring_drawn_inside_its_box(
    browser, serve
):
    """The same half asked of the other shape of ring, and the shape it was quiet about.
    A cover is excused where the control is under the same thing — a control put under a
    fixed bar is where it was put, not a ring leaving its box — and how far in the
    reading looks to ask that is the ring's own band.

    Which is inside the box when the ring is. The test above plants over a ring drawn
    outside its control, where the band is outside too and any step in clears it; asked
    one pixel in, as it was, the same question over an inset ring lands on the ring
    rather than past it, so every covered inset ring answered that the control was under
    the same thing and the reading returned what it returns when nothing is wrong.

    So: a control drawing the layer's ring inside itself, as a thread title does, under a
    band exactly as deep as that ring. The control case first, because a reading that
    reports over any inset control would pass the planted one without seeing it.
    """
    page = open_page(browser, serve(RING_PROBE_PAGE))
    # The layer's band, widened past two pixels: a step in of one pixel from the middle of
    # a 2px band lands on its inner edge, which hit testing may or may not count as the
    # band, so only a wider ring makes a step that stops inside it a step that fails.
    inset = page.evaluate(
        """() => {
      const control = document.getElementById('ring-control');
      control.style.cssText = `--focus-ring-w: 4px;
        outline: var(--focus-ring-w) solid var(--accent);
        outline-offset: calc(-1 * var(--focus-ring-w)); padding: 12px 24px;`;
      control.focus();
      const s = getComputedStyle(control);
      return [parseFloat(s.outlineWidth), parseFloat(s.outlineOffset)];
    }"""
    )
    assert inset[0] > 0 and inset[1] <= -inset[0], (
        f"the control's ring is {inset[0]}px at offset {inset[1]}px, which is not drawn "
        "inside its box, so this holds nothing about a reading of one that is"
    )

    # A band of the page's own paper over the control's top run, and nothing else of it.
    # Fixed and outside the control, because the reading passes over an ancestor or a
    # descendant of the control by design — a widget painting its own edge is not a
    # neighbour.
    plant = """(depth) => {
      document.querySelector('.lf-ring-plant')?.remove();
      if (!depth) return null;
      const r = document.activeElement.getBoundingClientRect();
      const over = document.documentElement.appendChild(
        document.createElement('div'));
      over.className = 'lf-ring-plant';
      Object.assign(over.style, {
        position: 'fixed', zIndex: '9999',
        background: 'var(--card)',
        left: `${r.left}px`, top: `${r.top}px`,
        width: `${r.width}px`, height: `${depth}px`,
      });
      return over.getBoundingClientRect().height;
    }"""

    page.evaluate(plant, 0)
    assert standing_ring(page)["covers"] == [], (
        "the control is reported covered with nothing over it, so the planted case "
        "below would only be repeating whatever this reading always says"
    )

    laid = page.evaluate(plant, inset[0])
    covers = standing_ring(page)["covers"]
    assert any("top edge" in c for c in covers), (
        f"a {laid}px band over the whole of the control's {inset[0]}px inset ring, "
        f"with the rest of the control in full view, and the reading said {covers}"
    )


def test_the_focus_sweep_distinguishes_stops_inside_a_live_frame(browser):
    page = browser.new_page()
    page.set_content(
        '<iframe srcdoc="<button id=first>First</button>'
        '<button id=second>Second</button>"></iframe>'
    )
    page.evaluate("() => { window.__lfSeen = new WeakSet(); }")
    page.frame_locator("iframe").locator("#first").focus()
    assert page.evaluate(RING_NEW_STOP) == "new"
    page.frame_locator("iframe").locator("#second").focus()
    assert page.evaluate(RING_NEW_STOP) == "new"


def test_the_ring_reading_measures_a_displaced_pseudo_element(browser, serve):
    """A pseudo's ring is checked where it paints, even outside its originating box."""
    page = open_page(browser, serve(RING_PROBE_PAGE))
    page.evaluate("""() => {
      const sheet = document.head.appendChild(document.createElement('style'));
      sheet.textContent = `
        #ring-holder { position: relative; height: 200px; }
        #ring-control { outline: none; }
        #ring-control::after {
          content: ''; position: absolute; pointer-events: none;
          left: 80px; top: 80px; width: 120px; height: 30px;
          outline: var(--focus-ring); outline-offset: -2px;
        }`;
      document.getElementById('ring-control').focus();
    }""")
    standing = standing_ring(page)
    assert standing and standing["pseudo"] == "after", standing
    assert standing["cuts"] == standing["covers"] == [], standing

    page.evaluate("""() => {
      const holder = document.getElementById('ring-holder').getBoundingClientRect();
      const band = document.body.appendChild(document.createElement('div'));
      band.style.cssText = `position: fixed; z-index: 99999; background: red;
        left: ${holder.left + 80}px; top: ${holder.top + 80}px;
        width: 120px; height: 2px;`;
    }""")
    assert any("top edge is under" in c for c in standing_ring(page)["covers"])
