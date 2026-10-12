"""Added-option presentation and replay tests."""

import pytest
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_cases_interaction import (
    ASK_PAGE,
)
from render_harness import (
    expect_asks_answered,
    open_page,
    round_trip,
    sending,
    undo,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_draft_binding_badge_and_send_press_share_the_row_end(browser, serve):
    """The empty route borrows Add's seat, then both actions keep stable seats."""
    page = open_page(browser, serve(ASK_PAGE))
    # The second Ask carries the card presentation, which is where the row's trailing
    # room is contested: its options wear their binding badges at the corner, so the
    # draft's badge is the one that had the edge.
    page.keyboard.press("q")
    page.keyboard.press("q")
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
    assert hint.locator("span").evaluate(
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
    page = open_page(browser, serve(ASK_PAGE))
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


def test_another_option_becomes_a_real_option_without_starting_a_thread(browser, serve):
    """The answer the author missed joins the control as a row of its own.

    It is not a comment with a special response contract: the user has supplied an
    answer, not opened a thread. The `add` stands on its own coordinate, so a
    later ordinary pick and a reload keep the option, and each undo takes back one
    gesture: the later pick, then the option's pick, then the option itself.
    """
    url = serve(ASK_PAGE)
    page = open_page(browser, url)
    d = serve.page_dir

    expect(page.locator("#jobs > .lf-thread-seat")).to_have_count(0)
    added = page.locator("#jobs > .lf-another")
    assert added.count() == 1, (
        f"the add-option cell was not rendered: {page.lf_errors}; "
        f"group={page.locator('#jobs').inner_html()}"
    )
    field = added.get_by_role("textbox", name="Another option", exact=True)
    expect(field).to_have_attribute("placeholder", "Add another option")
    write(field, "Insulate the camera battery")
    add = added.get_by_role("button", name="Add and select option", exact=True)
    add.focus()
    with sending(page, "the added option"):
        page.keyboard.press("Enter")
    # Pressing Add is Enter pressed in the field: the user goes on in the field.
    expect(field).to_be_focused()
    expect(added.locator(".lf-compose-submit")).to_have_attribute(
        "aria-disabled", "true"
    )
    expect_asks_answered(page, "0/3")

    new_option = page.locator("#jobs > lf-option[data-lf-added]")
    assert new_option.count() == 1, (
        f"the added option did not stand: {page.lf_errors}; events={events_model.read_events(d)}; "
        f"group={page.locator('#jobs').inner_html()}"
    )
    expect(new_option).to_contain_text("Insulate the camera battery")
    expect(new_option).to_have_attribute("chosen", "")
    identity = new_option.get_attribute("id")
    moves = [
        (event["action"], event["detail"])
        for event in events_model.read_events(d)
        if event.get("kind") == "action" and event.get("widget") == "jobs"
    ]
    assert moves == [
        ("add", {"option": identity, "text": "Insulate the camera battery"}),
        ("choose", {"value": [identity]}),
    ]
    assert not [
        event for event in events_model.read_events(d) if event["kind"] == "comment"
    ]

    page.locator("#job-heater").click()
    round_trip(page)
    expect(page.locator("#job-heater")).to_have_attribute("chosen", "")
    expect(new_option).to_have_attribute("chosen", "")

    page.reload(wait_until="load")
    page.wait_for_function(
        "() => document.body.getAttribute('data-lf-presented') === '1'"
    )
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(1)
    expect(page.locator("#job-heater")).to_have_attribute("chosen", "")

    undo(page)
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_attribute(
        "chosen", ""
    )
    undo(page)
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(1)
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(0)
    undo(page)
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(0)
