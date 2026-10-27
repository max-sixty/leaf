"""Focus rings and element contours: one ring for every control, under reduced motion
and forced colors, and the ring and focus-stop readings that check them."""

import io
import re
from html import escape

import pytest
from interact_support import append_carried_log_record, element_declaration
from journeys.test_render_controls import seen_stop
from PIL import Image
from playwright.sync_api import expect
from render_cases_layout import (
    current_location_ring,
    mark_edges,
    ring_faults,
    ring_rule,
    rings_drawn,
    token_colour,
)
from render_harness import (
    EXAMPLES,
    LONG_PAGE,
    REPLAYED_PAGE,
    any_suggestion_control,
    leaf_page,
    open_page,
    open_threads,
    page_comment,
    panel_settled,
    scroll_settled,
)

from browser.controls import (
    RING_NEW_STOP,
)
from browser.threads import open_panel_thread
from leaf import data as data_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_ring_rule_reading_uses_browser_serialization(browser):
    """Formatting cannot hide a matched ring rule or credit an unmatched selector."""
    page = browser.new_page()
    page.set_content("""
      <style>
        @scope (.surface) {
          .absent, .carrier:has(
            > :is(button,input)
          )[data-note="x,  y"] { outline: var(--focus-ring); }
        }
      </style>
      <div class="surface"><div class="carrier" data-note="x,  y">
        <button>Read</button>
      </div></div>
    """)
    assert ring_rule(page.locator(".carrier")) == (
        '@scope (.surface) { .carrier:has(> :is(button, input))[data-note="x,  y"]'
    )


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_diff_focus_distinguishes_pointer_and_keyboard_and_survives_shaded_rows(
    request, serve, engine
):
    """The reported diff click drew a ring below its positioned addition rows.

    Real Tab arrival must paint all four viewport edges before and after sideways
    scrolling; pointer arrival must preserve focus without painting a keyboard cue.
    """
    patch = (
        "diff --git a/example.py b/example.py\n--- a/example.py\n+++ b/example.py\n"
        "@@ -1,3 +1,3 @@\n context\n-"
        + "old_value " * 100
        + "\n+"
        + "new_value " * 100
        + "\n context\n"
    )
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Read a diff",
                '<h1>Read a diff</h1><lf-diff id="patch"><pre>'
                + escape(patch)
                + "</pre></lf-diff>",
            ),
            packages=("diff",),
        ),
    )
    code = page.locator("#patch code[data-code]")
    # Give the generated scrollport an address for the shared pixel-edge reader.
    code.evaluate("node => node.id = 'diff-viewport'")
    code.click(position={"x": 150, "y": 25})
    expect(code).to_be_focused()
    rendered(page)
    assert not rings_drawn(page)
    # A command can enter a reading row before Tab establishes native keyboard
    # visibility. The first arrival also lends the row its temporary focus stop.
    row = page.locator("#patch .lf-diff-line > [data-line]").first
    expect(row).not_to_have_attribute("tabindex")
    page.keyboard.press("]")
    expect(row).to_be_focused()
    rendered(page)
    assert row.evaluate("node => getComputedStyle(node).outlineStyle") == "solid"
    page.keyboard.press("c")
    expect(page.locator("leaf-text[data-lf-focus]")).to_be_focused()
    page.keyboard.press("Escape")
    expect(row).to_be_focused()
    rendered(page)
    assert row.evaluate("node => getComputedStyle(node).outlineStyle") == "solid"
    code.click(position={"x": 150, "y": 25})
    expect(code).to_be_focused()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(code).to_be_focused()
    rendered(page)
    accent = tuple(int(n) for n in re.findall(r"\d+", token_colour(page, "--accent")))
    for scrolled in (False, True):
        if scrolled:
            page.keyboard.press("ArrowRight")
            page.wait_for_function(
                "document.querySelector('#patch').shadowRoot.querySelector('code').scrollLeft > 0"
            )
        edges = mark_edges(page, "diff-viewport", accent)
        assert all(min(widths) >= 1 for widths in edges.values()), edges
    # Entering a hunk transfers the ring from the whole viewport to its first row.
    # The parent still contains visible focus, so its frame must also respond to
    # the code losing focus. Side samples below that row must lose their blue edge.
    page.keyboard.press("]")
    expect(row).to_be_focused()
    rendered(page)
    assert row.evaluate("node => getComputedStyle(node).outlineStyle") == "solid"
    edges = mark_edges(page, "diff-viewport", accent)
    assert min(edges["left"]) == min(edges["right"]) == 0, edges


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


def test_controls_show_keyboard_focus_without_ringing_pointer_activation(
    browser, serve
):
    """Clicks retain the current location; keyboard arrivals show one ring, including carriers."""
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
<lf-ask id="focus-open-decision"><h2>Which other option?</h2>
<lf-options id="focus-open-options" choose>
  <lf-option id="focus-open-choice">Keep this one.</lf-option>
  <lf-option id="focus-open-peer">Keep that one.</lf-option>
</lf-options></lf-ask>
""",
            ),
            layer_registry={"lf-shadow-focus": declaration},
            layer_widgets={
                "lf-shadow-focus.js": """
import {once, shadowStage} from '/runtime/widget-api.js';
import '/vendor/webawesome.esm.js';
customElements.define('lf-shadow-focus', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const select = document.createElement('wa-select');
    select.label = 'Choose a route';
    select.withClear = true;
    select.value = 'first';
    for (const [value, label] of [['first', 'First route'], ['second', 'Second route']]) {
      const option = document.createElement('wa-option');
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
        assert pointer["style"] == "none", pointer
        expect(page.locator(".lf-visual-mark-focus")).to_have_count(0)
        drawn = rings_drawn(page)
        samples = [ring for ring in drawn if ring["sample"]]
        assert not samples, drawn
        assert not ring_faults(drawn, "after pointer arrival")

        # Return by sequential navigation to cover the tab list's roving stop and
        # the option row's carrier through a real keyboard arrival.
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        expect(control).to_be_focused()
        rendered(page)
        if control is button:
            projected = page.locator(".lf-visual-mark-focus")
            expect(projected).to_have_attribute("data-for", "focus-button")
            assert (
                projected.evaluate(
                    "node => getComputedStyle(node, '::after').outlineStyle"
                )
                == "solid"
            )
        else:
            assert carrier.evaluate(paint)["style"] == "solid"
        drawn = rings_drawn(page)
        assert len([ring for ring in drawn if ring["sample"]]) == 1, drawn
        assert not ring_faults(drawn, "after keyboard arrival")

    assert page.locator("#focus-shadow").evaluate(paint)["style"] == "none", (
        "retargeting focus to the widget host drew a second ring around its button"
    )

    # An On me arrival focuses the decision, and its location ring is its focus cue.
    page.keyboard.press("m")
    expect(page.locator("#focus-open-decision")).to_be_focused()
    rendered(page)
    drawn = rings_drawn(page)
    assert len([ring for ring in drawn if ring["sample"]]) == 1, (
        "the arrived-at decision wore a projected focus contour beside its location ring",
        drawn,
    )

    select = page.locator("#focus-shadow wa-select")
    combobox = select.get_by_role("combobox")
    listbox = select.locator('[part~="listbox"]')
    first = select.get_by_role("option", name="First route", exact=True)
    second = select.get_by_role("option", name="Second route", exact=True)

    def one_select_ring(control, where):
        expect(control).to_be_focused()
        expect(control).to_be_visible()
        rendered(page)
        drawn = rings_drawn(page)
        assert len(drawn) == 1 and drawn[0]["sample"], (where, drawn)
        assert not ring_faults(drawn, where)

    # The popup's options are slotted beside the combobox. Focus within the select
    # host must not ring both the combobox and an option outside its ancestry.
    combobox.click()
    one_select_ring(first, "after opening the select")
    page.keyboard.press("ArrowDown")
    one_select_ring(second, "after moving to the next option")
    page.keyboard.press("Enter")
    expect(select).to_have_js_property("value", "second")
    one_select_ring(combobox, "after choosing an option")
    expect(listbox).to_be_hidden()
    combobox.click()
    one_select_ring(second, "after reopening the select")
    page.keyboard.press("Escape")
    one_select_ring(combobox, "after closing the select")
    expect(listbox).to_be_hidden()
    select.locator('[part~="clear-button"]').click()
    expect(select).to_have_js_property("value", None)
    one_select_ring(combobox, "after clearing the select")
    shadow_button.click()
    expect(shadow_button).to_be_focused()
    rendered(page)
    assert not rings_drawn(page)
    assert not select.locator('[part~="combobox"]').evaluate(
        "el => el.part.contains('lf-focus-within')"
    ), "the field retained its public focus part after focus left"


def _button_pairs(serve):
    """A page holding two symbols, two worded buttons and a two-mode toggle."""
    return serve(
        leaf_page(
            "Button pairs",
            '<h1 id="pairs-heading">Button pairs</h1>\n<lf-button-pairs id="pairs"></lf-button-pairs>',
        ),
        layer_registry={
            "lf-button-pairs": element_declaration("lf-button-pairs", upgrade=True)
        },
        layer_widgets={
            "lf-button-pairs.js": """
import {offerAction, once} from '/runtime/widget-api.js';
customElements.define('lf-button-pairs', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    for (const [id, role, icon] of [
      ['quiet-back', 'symbol', 'previous'],
      ['quiet-next', 'symbol', 'next'],
      ['plain-back', 'word'],
      ['plain-next', 'word'],
      ['mode-on', 'word'],
      ['mode-off', 'word'],
    ]) {
      const button = offerAction(role, '', id, {icon});
      button.id = id;
      if (id.startsWith('mode-')) button.setAttribute('aria-pressed', String(id === 'mode-on'));
      this.append(button);
    }
  }
});
"""
        },
    )


FACE = "el => getComputedStyle(el).backgroundColor"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_pressed_quiet_action_looks_like_its_neighbour(request, serve, engine):
    """A press leaves focus on a quiet action, as on any button, and leaves its face
    alone: once the pointer goes, it matches the action beside it until a key moves
    focus there, which wears the chip."""
    page = open_page(request.getfixturevalue(engine), _button_pairs(serve))
    back, forward = page.locator("#quiet-back"), page.locator("#quiet-next")
    forward.click()
    page.mouse.move(0, 0)
    expect(forward).to_be_focused()
    rendered(page)
    assert forward.evaluate(FACE) == back.evaluate(FACE)
    page.keyboard.press("Shift+Tab")
    expect(back).to_be_focused()
    rendered(page)
    assert back.evaluate(FACE) != forward.evaluate(FACE)


def test_a_tapped_button_looks_like_its_neighbour(browser, serve):
    """A finger leaves the button it tapped matching :hover, so a tapped button of
    either face keeps the face of the untapped one beside it."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, _button_pairs(serve), context=context)
    for tapped, beside in (("quiet-next", "quiet-back"), ("plain-next", "plain-back")):
        page.locator(f"#{tapped}").tap()
        rendered(page)
        assert page.locator(f"#{tapped}").evaluate(FACE) == page.locator(
            f"#{beside}"
        ).evaluate(FACE), tapped


def test_choice_rings_fit_clipped_edges_and_follow_native_visibility(browser, serve):
    """A whole-label cue survives clipping without turning every click into a cue."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Choices",
                """
<h1>Choices</h1>
<div style="overflow:clip;display:flex;gap:16px">
<label class="choice"><input id="check" type="checkbox">Outline changes</label>
<label class="choice"><input id="radio" type="radio" name="view">Full frame</label>
</div>
<p><button>Next</button></p>
""",
            )
        ),
    )
    for ident in ("check", "radio"):
        page.get_by_role("button", name="Next", exact=True).click()
        control = page.locator(f"#{ident}")
        label = control.locator("..")
        control.click()
        expect(control).to_be_focused()
        rendered(page)
        assert label.evaluate("n => getComputedStyle(n).outlineStyle") == "none"
        # A key changes visibility even when focus stays on the same control.
        page.keyboard.press("Space")
        rendered(page)
        assert label.evaluate("n => getComputedStyle(n).outlineStyle") == "solid"
        assert not ring_faults(rings_drawn(page), "choice inside a clipped toolbar")
        geometry = label.evaluate("""n => {
          const r=n.getBoundingClientRect(), c=n.querySelector('input').getBoundingClientRect();
          const s=getComputedStyle(n);
          return {offset:parseFloat(s.outlineOffset), width:parseFloat(s.outlineWidth),
                  room:c.left-r.left};
        }""")
        assert geometry["offset"] + geometry["width"] <= 0, geometry
        assert geometry["room"] > geometry["width"], geometry
        page.keyboard.press("Tab")


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


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_contour_stands_inside_a_target_its_clip_leaves_no_room_around(
    request, serve, engine
):
    """A joined option group clips its cells to its frame, so the brackets of the thread
    the user is in, drawn flush outside a cell, lost their sides and left stubs across
    the neighbouring cells. Inside the frame they stand just within the cell's edge; a
    paragraph with room around it is the control that keeps them outside."""
    url = serve(
        leaf_page(
            "Contours",
            """
<h1>Contours</h1>
<p id="said">A paragraph with room around it.</p>
<lf-options id="pick" choose>
  <lf-option id="keep"><strong>Keep</strong> the words alone.</lf-option>
  <lf-option id="place" chosen><strong>Place</strong> them in the line.</lf-option>
</lf-options>
""",
        )
    )
    for ident in ("said", "place"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "id": f"on-{ident}",
                "author": "user",
                "revision": 1,
                "text": "Say more about this.",
                "anchor": {"section": ident},
            },
        )
    page = open_page(request.getfixturevalue(engine), url)
    for ident, inside in (("said", False), ("place", True)):
        open_panel_thread(page, f"on-{ident}")
        page.locator(".lf-fp-aux").get_by_role(
            "button", name="Show on page", exact=True
        ).click()
        panel_settled(page, open=False)
        mark = page.locator(f'.lf-visual-mark-here[data-for="{ident}"]')
        expect(mark).to_be_visible()
        room = mark.evaluate(
            "n => { const s = getComputedStyle(n, '::after');"
            " return parseFloat(s.outlineOffset) + parseFloat(s.outlineWidth); }"
        )
        assert (room <= 0) is inside, (ident, room)


# A page holding a paragraph and one control, for the readings below that plant the
# shape they are about rather than finding it in the product: which of the layer's
# controls draws an inset ring, or names no z-index, moves with the product and is not
# what these readings are held to. A runtime control keeps its native carrier so
# the probe can move and cover that carrier independently of target projection.
RING_PROBE_PAGE = leaf_page(
    "ring",
    "<h1>Ring</h1><p>Words.</p>"
    '<div id="ring-holder"><button id="ring-control" type="button">Control</button></div>'
    "<p>After.</p>"
    '<script type="module">document.getElementById("ring-control").classList.add("lf-ui");</script>',
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
    assert current_location_ring(page)["cuts"] == [], (
        f"the displaced ring is reported cut with nothing clipping it ({clean}), so the "
        "cases below would only be repeating whatever this reading always says"
    )
    for how in ("overflow", "contain", "content-visibility"):
        style = page.evaluate(plant, how)
        cuts = current_location_ring(page)["cuts"]
        assert any("left edge" in c for c in cuts), (
            f"a parent clipping by {how} ({style}) drew the ring away and the reading "
            f"said {cuts}"
        )


def test_the_ring_reading_distinguishes_target_brackets_from_focus(browser, serve):
    """Shared outline ink identifies a target; only its full focus state is a ring."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Target rings",
                '<h1>Target rings</h1><button id="target">Review</button>',
            )
        ),
    )
    target = page.locator("#target")
    target.hover()
    page.keyboard.down("Alt")
    aim = page.locator(".lf-aim")
    expect(aim).to_have_attribute("data-for", "target")
    assert (
        aim.evaluate("node => getComputedStyle(node, '::before').outlineStyle")
        == "solid"
    )
    assert not any("lf-aim" in seen["who"] for seen in rings_drawn(page))
    page.keyboard.up("Alt")
    page.keyboard.press("Tab")
    expect(target).to_be_focused()
    rendered(page)
    ring = current_location_ring(page)
    assert ring and ring["here"] and ring["pseudo"] == "after", ring
    assert "lf-visual-mark-focus" in ring["who"], ring
    assert ring["cuts"] == ring["covers"] == [], ring
    assert seen_stop(page) is None
    page.locator(".lf-visual-mark-focus").evaluate(
        "node => node.style.setProperty('--lf-target-outline', 'none')"
    )
    assert seen_stop(page), (
        "the focused target has no ring, but the stop reading accepts it"
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
    assert current_location_ring(page), "no ring is drawn, so nothing is covered"

    assert current_location_ring(page)["covers"] == [], (
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
    assert any(
        "top edge is under" in c for c in current_location_ring(page)["covers"]
    ), (
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
    current_location = current_location_ring(page)
    assert current_location and current_location["covers"] == [], (
        f"the control is reported covered before anything is put over it: {current_location}"
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
    assert current_location_ring(page)["covers"] == [], (
        "a neighbour the grip paints across was read as standing over its ring"
    )

    page.evaluate(plant, {"z": 2, "wrap": False})
    covers = current_location_ring(page)["covers"]
    assert any("right edge is under" in c for c in covers), (
        f"the same band lifted past the grip by a z-index of its own read as {covers}, "
        "so the half above passed on a reading that answers nothing"
    )

    # The same band inside a static box, which is the shape that leaves a holder's flow:
    # it paints in the positioned layer rather than the one its holder is ranked in. That
    # is still the layer under the grip's own, so the page paints the grip in front and
    # the reading has nothing to report.
    page.evaluate(plant, {"z": 0, "wrap": True})
    covers = current_location_ring(page)["covers"]
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
        covers = current_location_ring(page)["covers"]
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
    current_location = current_location_ring(page)
    assert current_location and current_location["covers"] == [], (
        f"the control is reported covered before anything is put over it: {current_location}"
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
    covers = current_location_ring(page)["covers"]
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
    covers = current_location_ring(page)["covers"]
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
    covers = current_location_ring(page)["covers"]
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
    open_threads(page)
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
    assert current_location_ring(page)["covers"] == [], (
        "the control is reported covered with nothing over it, so the planted case "
        "below would only be repeating whatever this reading always says"
    )

    laid = page.evaluate(plant, inset[0])
    covers = current_location_ring(page)["covers"]
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
      const sheet = document.createElement('style');
      sheet.setAttribute('data-controls', '');
      document.head.append(sheet);
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
    current_location = current_location_ring(page)
    assert current_location and current_location["pseudo"] == "after", current_location
    assert current_location["cuts"] == current_location["covers"] == [], (
        current_location
    )

    page.evaluate("""() => {
      const holder = document.getElementById('ring-holder').getBoundingClientRect();
      const band = document.body.appendChild(document.createElement('div'));
      band.style.cssText = `position: fixed; z-index: 99999; background: red;
        left: ${holder.left + 80}px; top: ${holder.top + 80}px;
        width: 120px; height: 2px;`;
    }""")
    assert any("top edge is under" in c for c in current_location_ring(page)["covers"])


def test_a_quiet_toggle_still_shows_its_chosen_mode(browser, serve):
    """Words are quiet, with no frame at rest, so a mode toggle's chosen mode draws its
    own selected face: a frame and ground the unchosen word beside it lacks."""
    page = open_page(browser, _button_pairs(serve))
    page.mouse.move(0, 0)
    rendered(page)
    face = "el => [getComputedStyle(el).borderTopColor, getComputedStyle(el).backgroundColor]"
    chosen = page.locator("#mode-on").evaluate(face)
    other = page.locator("#mode-off").evaluate(face)
    assert other == page.locator("#plain-back").evaluate(face)
    assert chosen[0] != other[0] and chosen[1] != other[1], (chosen, other)
