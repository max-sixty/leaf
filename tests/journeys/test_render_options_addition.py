"""Added-option presentation and replay tests."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import (
    OBLIGATION_PAGE,
)
from render_harness import (
    open_page,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_draft_binding_badge_and_send_press_share_the_row_end(browser, serve):
    """The empty route borrows Add's seat, then both actions keep stable seats."""
    page = open_page(browser, serve(OBLIGATION_PAGE))
    # The second obligation carries the card presentation, which is where the row's trailing
    # room is contested: its options wear their binding badges at the corner, so the
    # draft's badge is the one that had the edge.
    page.keyboard.press("m")
    page.keyboard.press("m")
    expect(page.locator("#bracket > .lf-another > .lf-key-badge")).to_be_visible()
    shown = page.locator("#bracket > .lf-another").evaluate(
        """el => {
             const form = el.getBoundingClientRect();
             const press = el.querySelector('.lf-compose-submit').getBoundingClientRect();
             const mark = el.querySelector('.lf-key-badge').getBoundingClientRect();
             return {
               dx: (press.left + press.right) / 2 - (mark.left + mark.right) / 2,
               dy: (press.top + press.bottom) / 2 - (mark.top + mark.bottom) / 2,
               badgeWidth: mark.width,
               centerX: (press.left + press.right) / 2,
               bottomInset: form.bottom - press.bottom,
             };
           }"""
    )
    assert abs(shown["dx"]) < 0.5, shown
    assert abs(shown["dy"]) < 0.5, shown

    field = page.locator("#bracket > .lf-another leaf-text")
    add = page.locator("#bracket > .lf-another .lf-compose-submit")
    field.click()
    expect(page.locator("#bracket > .lf-another > .lf-key-badge")).to_be_hidden()
    hint = page.locator("#bracket > .lf-another .lf-compose-placeholder")
    expect(hint).to_be_visible()
    assert hint.locator("kbd").evaluate(
        "key => getComputedStyle(key).fontFamily"
    ) == page.evaluate(
        r"() => getComputedStyle(document.body).getPropertyValue('--mono').trim().replace(/\s+/g, ' ')"
    )
    assert hint.locator(".lf-compose-placeholder-words").evaluate(
        "label => getComputedStyle(label).fontFamily"
    ) == field.evaluate("box => getComputedStyle(box).fontFamily")
    write(field, "Something the author missed")
    expect(hint).to_be_hidden()
    expect(add).to_be_visible()
    add_box = add.bounding_box()
    assert abs(add_box["x"] + add_box["width"] / 2 - shown["centerX"]) < 0.5
    form_box = page.locator("#bracket > .lf-another").bounding_box()
    bottom_inset = form_box["y"] + form_box["height"] - add_box["y"] - add_box["height"]
    assert abs(bottom_inset - shown["bottomInset"]) < 0.5
    expected_right = shown["centerX"] + add_box["width"] / 2

    page.close()
    page = open_page(browser, serve(OBLIGATION_PAGE))
    gaps = {}
    for group in ("#jobs", "#bracket"):
        row = page.locator(f"{group} > .lf-another")
        write(row.locator("leaf-text"), "Something the author missed")
        expect(row.locator(".lf-compose-submit")).to_be_visible()
        gaps[group] = row.evaluate(
            """el => {
                 const style = getComputedStyle(el);
                 const inner = el.getBoundingClientRect().right
                   - parseFloat(style.borderRightWidth);
                 const press = el.querySelector('.lf-compose-submit');
                 const field = el.querySelector('leaf-text');
                 return {
                   end: inner - press.getBoundingClientRect().right,
                   room: parseFloat(getComputedStyle(field)
                     .getPropertyValue('--lf-field-end-room')),
                   right: press.getBoundingClientRect().right,
                 };
               }"""
        )
    assert abs(gaps["#jobs"]["end"] - gaps["#bracket"]["end"]) < 0.5, gaps
    assert 0 <= gaps["#bracket"]["end"] < 8, gaps
    spacing = page.locator("html").evaluate(
        "el => parseFloat(getComputedStyle(el).getPropertyValue('--sp-2'))"
    )
    assert gaps["#bracket"]["room"] - gaps["#jobs"]["room"] == (
        pytest.approx(shown["badgeWidth"] + spacing, abs=0.5)
    )
    # Writing in the row and putting the bindings away reveals the press in the exact
    # seat the badge vacated: the room is held whether either face is painted or not.
    assert abs(gaps["#bracket"]["right"] - expected_right) < 0.5
