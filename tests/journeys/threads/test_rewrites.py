"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.threads import open_panel_thread
from browser.threads.test_rewrites import PICTURE, PICTURED, _rewrite_surface
from playwright.sync_api import expect
from render_harness import round_trip

from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_an_emptied_rewrite_keeps_nothing_and_saved_deletes_its_message(browser, serve):
    """A rewrite cleared and left keeps none of its empty words, which would show an
    empty box in place of the message at every later opening, without saying it held
    anything. A rewrite keeps words: a page reloaded over an emptied one puts the user
    back in the rewrite, which holds the message's own.

    Saved, an emptied rewrite deletes its message, rather than its Save standing drawn
    live and doing nothing. The box says so before the press, its field reading Delete
    message and its Save turning to Delete; the message then reads Deleted in its place,
    above the answer given to it, offering no rewrite, and still does after a reload.

    A deletion, as any rewrite, can be taken back: ⌘Z gives the message its words back
    in the press, and the log keeps them."""
    page, _, message = _rewrite_surface(browser, serve, "panel")
    words = message.locator(".lf-msg-text")
    editor = message.locator(".lf-msg-editor leaf-text")
    words.dblclick()
    expect(editor).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    rendered(page)
    mine = message.get_attribute("data-lf-event")
    page.reload()
    wait_until_ready(page)
    open_panel_thread(page, mine)
    expect(message.locator(".lf-msg-kept")).to_have_count(0)
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "Fit the north bracket.")

    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    expect(message.locator(".lf-msg-edit-save")).to_have_accessible_name("Delete")
    assert editor.evaluate("n => n.placeholder").startswith("Delete message")
    page.keyboard.press("Enter")
    deleted = message.locator(".lf-msg-deleted")
    expect(deleted).to_have_text("Deleted")
    expect(message.locator(".lf-msg-edit, .lf-edited")).to_have_count(0)
    round_trip(page)
    assert [
        e["text"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "edit"
    ] == [""]
    page.reload()
    wait_until_ready(page)
    open_panel_thread(page, mine).focus()
    expect(deleted).to_have_text("Deleted")
    expect(message.locator(".lf-msg-edit")).to_have_count(0)

    # The log answers only once the words are back.
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+z")
    expect(words).to_have_text("Fit the north bracket.")
    expect(deleted).to_have_count(0)
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    logged = events_model.read_events(serve.page_dir)
    (deletion,) = [e for e in logged if e["kind"] == "edit"]
    assert logged[-1]["kind"] == "undo" and logged[-1]["undoes"] == deletion["id"]
    page.reload()
    wait_until_ready(page)
    open_panel_thread(page, mine)
    expect(words).to_have_text("Fit the north bracket.")
    expect(message.locator(".lf-msg-edit")).to_have_count(1)


def test_a_rewrite_saves_the_pictures_it_keeps(browser, serve):
    """A rewrite reads its words and pictures together. One that read its words alone
    would send a message with a picture unchanged again on save, and taking a picture
    off a message of pictures would close the box as no change, the picture coming
    back. A picture's removal mark stands out past its top right corner, as on a
    draft's."""
    page, _, message = _rewrite_surface(browser, serve, "panel", text=PICTURED)
    editor = message.locator(".lf-msg-editor leaf-text")
    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_be_focused()
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)

    page, _, message = _rewrite_surface(
        browser, serve, "panel", text=f"{PICTURE}\n\n{PICTURE}"
    )
    message.locator(".lf-msg-edit").click()
    editor = message.locator(".lf-msg-editor leaf-text")
    expect(editor).to_be_focused()
    remove = message.get_by_role("button", name="Remove attached image 2", exact=True)
    picture = message.locator(".lf-msg-editor img").nth(1).bounding_box()
    mark = remove.bounding_box()
    assert mark["x"] + mark["width"] > picture["x"] + picture["width"], (mark, picture)
    assert mark["y"] < picture["y"], (mark, picture)
    remove.click()
    expect(editor).to_be_focused()
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    round_trip(page)
    edits = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "edit"]
    assert [e["text"] for e in edits] == [PICTURE]
    expect(message.locator("img")).to_have_count(1)
