"""Tests scheduled by the measured cost of their boundary."""

import re

import pytest
from interact_support import element_declaration
from playwright.sync_api import expect
from render_harness import leaf_page, open_page

from leaf.source.render_checks import rendered
from leaf_dev.rings import current_location_ring, ring_faults, rings_drawn

pytestmark = pytest.mark.shifts_unsurveyed


def test_controls_show_keyboard_focus_without_ringing_pointer_activation(
    browser, serve
):
    """Clicks retain the current location; keyboard arrivals show one ring, including carriers."""
    declaration = element_declaration("lf-shadow-focus", upgrade=True)
    declaration["shadow"] = True
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Focus routes",
                """
<h1 id="focus-heading">Focus routes</h1>
<p><button id="focus-button" type="button">Ordinary button</button></p>
<lf-tabs id="focus-tabs">
  <lf-tab id="focus-first" label="First">First panel.</lf-tab>
  <lf-tab id="focus-second" label="Second">Second panel.</lf-tab>
</lf-tabs>
<lf-group id="focus-decision" label="Which option?"><h2 id="focus-decision-h">Which option?</h2>
<lf-options id="focus-options">
  <lf-option id="focus-choice" for="focus-heading">Keep this option.</lf-option>
  <lf-option id="focus-peer" for="focus-heading">Keep another option.</lf-option>
</lf-options></lf-group>
<lf-shadow-focus id="focus-shadow"></lf-shadow-focus>
<lf-group id="focus-open-decision" label="Which other option?"><h2 id="focus-open-decision-h">Which other option?</h2>
<lf-options id="focus-open-options">
  <lf-option id="focus-open-choice">Keep this one.</lf-option>
  <lf-option id="focus-open-peer">Keep that one.</lf-option>
</lf-options></lf-group>
""",
            ),
            layer_registry={"lf-shadow-focus": declaration},
            layer_widgets={
                "lf-shadow-focus.js": """
import {shadowStage} from '/runtime/widget-api.js';
import {offerAction} from '/runtime/lib/controls.js';
import {once} from '/runtime/lib/once.js';
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
    // A widget's own control in its shadow tree, built by role as a widget builds one.
    shadowStage(this, [offerAction('word', '', 'Shadow button'), select]);
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
    choice = page.locator("#focus-choice .lf-pick")
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
        expect(page.locator('[data-lf-mark~="focus"]')).to_have_count(0)
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
            # The target painter's focus state, which the button draws as its ring.
            expect(button).to_have_attribute("data-lf-mark", re.compile(r"\bfocus\b"))
        assert carrier.evaluate(paint)["style"] == "solid"
        drawn = rings_drawn(page)
        assert len([ring for ring in drawn if ring["sample"]]) == 1, drawn
        assert not ring_faults(drawn, "after keyboard arrival")

    # A neighbour under the shadow button's ring is clean above. A real cover at
    # the same point must still be reported when the screenshot confirms its paint.
    shadow_button.evaluate("""el => {
      const b = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      const band = document.body.appendChild(document.createElement('div'));
      band.id = 'shadow-ring-cover';
      band.style.cssText = `position: fixed; z-index: 99999; background: red;
        left: ${b.left}px; top: ${b.top - parseFloat(s.outlineOffset) - parseFloat(s.outlineWidth)}px;
        width: ${b.width}px; height: ${s.outlineWidth};`;
    }""")
    assert any("top edge is under" in c for c in current_location_ring(page)["covers"])
    page.locator("#shadow-ring-cover").evaluate("el => el.remove()")

    assert page.locator("#focus-shadow").evaluate(paint)["style"] == "none", (
        "retargeting focus to the widget host drew a second ring around its button"
    )

    # An On Me arrival focuses the decision, and its location ring is its focus cue.
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
