"""Tests scheduled by the measured cost of their boundary."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_navigation import go_to_address
from render_harness import leaf_page, open_page

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("touch", [False, True])
def test_native_disclosure_inherits_the_offered_control_target(browser, serve, touch):
    """A native disclosure gets the same press target without a widget-specific rule."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=touch
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Native disclosure",
                """<h1>Comparison</h1>
<details id="comparison"><p>Inspection controls.</p></details>
<details id="wrapped-comparison" style="width: 160px"><p>Wrapped controls.</p></details>
<script type="module">
import {offer} from '/runtime/widget-api.js';
const summary = offer('summary', '', 'Inspect comparison');
summary.id = 'inspect';
document.querySelector('#comparison').prepend(summary);
const wrapped = offer('summary', '', 'A long disclosure label that wraps across several lines');
wrapped.id = 'wrapped-inspect';
document.querySelector('#wrapped-comparison').prepend(wrapped);
</script>""",
            )
        ),
        context=context,
    )
    for control_id, detail_id in (
        ("inspect", "comparison"),
        ("wrapped-inspect", "wrapped-comparison"),
    ):
        control = page.locator(f"#{control_id}")
        before = control.bounding_box()
        floor = 44 if touch else 24
        assert min(before["width"], before["height"]) >= floor - 0.5, before
        label_room = control.evaluate(
            """node => {
              const range = document.createRange(); range.selectNodeContents(node);
              const box = node.getBoundingClientRect(), text = range.getBoundingClientRect();
              return {above: text.top-box.top, below: box.bottom-text.bottom,
                      display: getComputedStyle(node).display};
            }"""
        )
        assert abs(label_room["above"] - label_room["below"]) <= 2, label_room
        assert label_room["display"] == "list-item", label_room
        if touch:
            control.tap()
        else:
            control.click()
        expect(page.locator(f"#{detail_id}")).to_have_attribute("open", "")
        assert control.bounding_box() == before
        control.press("Space")
        expect(page.locator(f"#{detail_id}")).not_to_have_attribute("open", "")
        assert control.bounding_box() == before
        control.press("Enter")
        expect(page.locator(f"#{detail_id}")).to_have_attribute("open", "")
        assert control.bounding_box() == before


def test_offered_native_targets_keep_their_navigation_meaning(browser, serve):
    """An offered disclosure or link keeps its native Go-to arrival, not a generic press."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Native routes",
                """<h1>Comparison</h1>
<details id="comparison"><p>Inspection controls.</p></details>
<p id="destination">Destination evidence.</p>
<script type="module">
import {offer} from '/runtime/widget-api.js';
const summary = offer('summary', '', 'Inspect comparison');
summary.id = 'inspect';
document.querySelector('#comparison').prepend(summary);
const link = offer('a', '', 'Evidence');
link.id = 'evidence';
link.href = '#destination';
document.querySelector('main').append(link);
</script>""",
            )
        ),
    )
    summary = page.locator("#inspect")
    go_to_address(page, "Fold", "inspect")
    expect(summary).to_be_focused()
    expect(page.locator("#comparison")).to_have_attribute("open", "")
    page.keyboard.press("Enter")
    expect(page.locator("#comparison")).not_to_have_attribute("open", "")
    go_to_address(page, "Link", "evidence")
    expect(page).to_have_url(re.compile(r"#destination$"))
