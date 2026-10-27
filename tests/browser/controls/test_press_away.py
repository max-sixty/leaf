"""A press away from a surface puts it away: one begun and completed outside it, as the
platform judges its own light dismissal (focus.js, `onPressAway`). Every surface that
goes on a press elsewhere is held to that one press, so a drag between it and the page
leaves it standing, a finger's tap away and a mouse's click away both put it away, a
finger scrolling the page does not, and Escape, its keyboard route, puts it away too."""

from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE
from render_harness import (
    LONG_PAGE,
    open_page,
    panel_settled,
    stored_draft_text,
    told,
    write,
)

from browser.drafts.test_reply_sessions import open_reply
from browser.margin.test_pins import FOLDING_PAGE
from browser.test_render_reactions import select_paragraph
from leaf import event_log as events_model

PHONE = {
    "viewport": {"width": 390, "height": 844},
    "has_touch": True,
    "is_mobile": True,
}


def centre(locator):
    box = locator.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def tap(page, at):
    """A finger's tap, which a mouse-driven page hears as a touch press, where the
    browser's touch emulation would also make the pointer coarse."""
    cdp = page.context.new_cdp_session(page)
    x, y = at
    cdp.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]},
    )
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()


def swipe(page, start, end):
    """A finger dragging the page, which the browser takes for a scroll and cancels."""
    cdp = page.context.new_cdp_session(page)
    cdp.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [dict(zip("xy", start))]},
    )
    for step in range(1, 9):
        at = [a + (b - a) * step / 8 for a, b in zip(start, end)]
        cdp.send(
            "Input.dispatchTouchEvent",
            {"type": "touchMove", "touchPoints": [dict(zip("xy", at))]},
        )
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()


def drag(page, start, end):
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=8)
    page.mouse.up()


def test_a_press_away_puts_the_panel_s_view_away(browser, serve):
    page = open_page(browser, serve(PANEL_PAGE))
    on_me = page.locator(".lf-fp-on-user")
    outside = centre(page.locator("h1"))
    on_me.click()
    panel_settled(page, view="queue")
    view = page.locator(".lf-fp-view:not([data-leaving])")
    # A drag that ends in the view, as a selection overshooting into it does, began on
    # the page but did not end there.
    drag(page, outside, centre(view))
    panel_settled(page, view="queue")
    drag(page, centre(view), outside)
    panel_settled(page, view="queue")
    swipe(page, outside, (outside[0], outside[1] + 200))
    panel_settled(page, view="queue")
    tap(page, outside)
    panel_settled(page, open=False)
    on_me.click()
    panel_settled(page, view="queue")
    page.mouse.click(*outside)
    panel_settled(page, open=False)
    on_me.click()
    panel_settled(page, view="queue")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)


def test_a_press_away_puts_the_response_bar_away(browser, serve):
    page = open_page(browser, serve(PANEL_PAGE))
    bar = page.locator(".lf-fab-bar")
    outside = centre(page.locator("h1"))
    select_paragraph(page, "#how-store")
    expect(bar).to_be_visible()
    # Selecting the words typed in its field past its edge leaves it standing.
    drag(page, centre(bar.locator(".lf-fab-input")), outside)
    expect(bar).to_be_visible()
    tap(page, outside)
    expect(bar).to_be_hidden()
    select_paragraph(page, "#how-store")
    expect(bar).to_be_visible()
    page.mouse.click(*outside)
    expect(bar).to_be_hidden()
    select_paragraph(page, "#how-store")
    expect(bar).to_be_visible()
    page.keyboard.press("Escape")
    expect(bar).to_be_hidden()


def test_a_press_away_takes_back_a_reaction_s_offered_remove(browser, serve):
    url = serve(PANEL_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "keep",
            "anchor": {"section": "how-store"},
        },
    )
    page = open_page(browser, url)
    mark = page.get_by_role("button", name="keep reaction actions", exact=True)
    remove = page.locator('[aria-label="Undo keep reaction"]:visible')
    outside = centre(page.locator("h1"))
    mark.click()
    expect(remove).to_be_visible()
    drag(page, outside, centre(remove))
    expect(mark).to_have_attribute("aria-expanded", "true")
    drag(page, centre(remove), outside)
    expect(mark).to_have_attribute("aria-expanded", "true")
    tap(page, outside)
    expect(mark).to_have_attribute("aria-expanded", "false")
    mark.click()
    expect(remove).to_be_visible()
    page.mouse.click(*outside)
    expect(mark).to_have_attribute("aria-expanded", "false")
    mark.focus()
    mark.press("Enter")
    expect(remove).to_be_focused()
    remove.press("Escape")
    expect(mark).to_have_attribute("aria-expanded", "false")


def test_a_press_away_folds_a_pin_s_unfolded_actions(browser, serve):
    page = open_page(browser, serve(FOLDING_PAGE), context=browser.new_context(**PHONE))
    row = page.locator('.lf-margin-cluster[data-lf-margin-for="s"]')
    toggle = row.locator(".lf-margin-more")
    accept = row.locator(".lf-sug-accept")
    outside = centre(page.locator("h1"))
    toggle.tap()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    # A press on the page takes focus out of the pin, which folds it as leaving it by
    # any route does, so only a drag out of it can show the press alone.
    drag(page, centre(accept), outside)
    expect(toggle).to_have_attribute("aria-expanded", "true")
    tap(page, outside)
    expect(toggle).to_have_attribute("aria-expanded", "false")
    toggle.tap()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    page.mouse.click(*outside)
    expect(toggle).to_have_attribute("aria-expanded", "false")
    # Arriving by Tab unfolds the pin onto Accept.
    for _ in range(40):
        page.keyboard.press("Tab")
        if row.evaluate("row => row.contains(document.activeElement)"):
            break
    expect(accept).to_be_focused()
    page.keyboard.press("Escape")
    expect(toggle).to_have_attribute("aria-expanded", "false")


def test_a_press_away_ends_a_reply_s_composition(browser, serve):
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url)
    _, field = open_reply(page, "margin", root)
    write(field, "A reply still being written.")
    # A resolved thread draws its reply box only while the reply's composition lasts.
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    expect(field).to_be_visible()
    # The passage the card is about keeps the card, so a press there is away from the
    # reply alone.
    passage = page.locator("#p3")
    drag(page, centre(field), centre(passage))
    expect(field).to_be_visible()
    tap(page, centre(passage))
    expect(field).not_to_be_visible()
    assert stored_draft_text(page, f"reply:{root}") == "A reply still being written."
