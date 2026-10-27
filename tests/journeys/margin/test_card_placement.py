"Where an open margin thread card stands beside its target, and how it holds still\nthrough news, presses, reflows and scrolls, panes included."

from datetime import datetime, timedelta

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import (
    open_page,
    resized,
    ticked,
    told,
)

from leaf import thread as thread_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.watch_shifts
def test_an_open_card_takes_news_without_moving_its_controls(browser, serve):
    """The card keeps the width it opened at, so a longer step wraps inside it rather
    than carrying Resolve, Close and Send sideways. Read idle, a step shows at once and
    the card grows down past its reply row. While the user writes, a step and an
    answer wait behind the thread's notice, as a held reply does in a seat, so nothing
    moves. Pressing the notice shows them under the press: the head row stays and
    the card grows down, keeping the draft's words."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Make the banner quieter", {"section": "h-how"}
    )
    address = {"parent": root, "responds": root}
    thread_model.post_reply(
        serve.page_dir, address, "Reading the banner's styles.", ephemeral=True
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    words = preview.locator(".lf-thread-working-words")
    expect(words).to_have_text("Reading the banner's styles")
    rendered(page)
    controls = {
        name: preview.get_by_role("button", name=name, exact=True)
        for name in ("Resolve thread", "Dismiss thread view")
    }
    opened = preview.bounding_box()
    boxes = {name: control.bounding_box() for name, control in controls.items()}

    long_step = (
        "Comparing the lighter weight against every banner the gallery shows, at each "
        "width the panel takes, before and after the change."
    )
    thread_model.post_reply(serve.page_dir, address, long_step, ephemeral=True)
    told(page)
    expect(words).to_contain_text("before and after the change")
    rendered(page)
    grown = preview.bounding_box()
    assert grown["width"] == pytest.approx(opened["width"], abs=0.5), (opened, grown)
    assert grown["y"] == pytest.approx(opened["y"], abs=0.5), (opened, grown)
    assert grown["height"] > opened["height"]
    for name, control in controls.items():
        assert control.bounding_box() == pytest.approx(boxes[name], abs=0.5), name

    editor = preview.locator("leaf-text")
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    page.keyboard.type("Also check the dark scheme")
    rendered(page)
    writing = preview.bounding_box()
    send = preview.locator(".lf-thread-reply .lf-compose-submit")
    pinned = {name: control.bounding_box() for name, control in controls.items()}
    pinned["Send"] = send.bounding_box()
    pinned["editor"] = editor.bounding_box()

    thread_model.post_reply(
        serve.page_dir,
        address,
        "Measuring the status line's contrast in both schemes, against the paper and "
        "against the banner's own ground.",
        ephemeral=True,
    )
    told(page)
    notice = preview.locator(".lf-thread-notice-news")
    expect(notice).to_have_count(0)
    expect(words).to_contain_text("before and after the change")
    thread_model.post_reply(
        serve.page_dir,
        address,
        "Done: the banner's status line is one weight lighter, and its title sets in "
        "the muted ink, so the banner reads as chrome rather than as the page's first "
        "heading in both schemes.",
    )
    told(page)
    expect(notice).to_contain_text("new reply")
    # It reads whole in the head row, before the card's actions.
    expect(
        preview.locator(".lf-margin-thread-controls .lf-thread-news")
    ).to_be_visible()
    assert notice.evaluate("node => node.scrollWidth <= node.clientWidth")
    rendered(page)
    assert preview.bounding_box() == pytest.approx(writing, abs=0.5)
    held = {name: control.bounding_box() for name, control in controls.items()}
    held["Send"] = send.bounding_box()
    held["editor"] = editor.bounding_box()
    for name, box in pinned.items():
        assert held[name] == pytest.approx(box, abs=0.5), name

    notice.click()
    expect(preview).to_contain_text("one weight lighter")
    assert editor.evaluate("box => box.value") == "Also check the dark scheme"
    rendered(page)
    for name, control in controls.items():
        assert control.bounding_box() == pytest.approx(held[name], abs=0.5), name
    assert editor.bounding_box()["y"] > held["editor"]["y"] + 20


@pytest.mark.watch_shifts
@pytest.mark.parametrize("how", ["press", "key"])
def test_a_press_in_the_card_keeps_the_pressed_spot_still(browser, serve, how):
    """What a press shows grows the card from where the user pressed, as a seat on
    the page grows: opening pending progress, by pointer or key, grows the card up
    past the disclosure, which stays where it was pressed. The hold ends with that
    input, so a draft typed next grows the card down from its head row."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Make the banner quieter", {"section": "h-how"}
    )
    address = {"parent": root, "responds": root}
    for words in ("Comparing the banner.", "Checking both schemes.", "Measuring."):
        thread_model.post_reply(serve.page_dir, address, words, ephemeral=True)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root,
            "text": "And check the dark scheme?",
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    disclosure = preview.locator(".lf-summary-expand")
    expect(disclosure).to_have_text("Show 3 progress messages")
    rendered(page)
    pressed = disclosure.bounding_box()
    compact = preview.bounding_box()

    if how == "key":
        disclosure.focus()
        page.keyboard.press("Enter")
    else:
        disclosure.click()
    expect(disclosure).to_have_text("Hide 3 progress messages")
    expect(preview).to_contain_text("Checking both schemes")
    rendered(page)
    after = disclosure.bounding_box()
    assert (after["x"], after["y"]) == pytest.approx(
        (pressed["x"], pressed["y"]), abs=0.5
    )

    expanded = preview.bounding_box()
    assert expanded["height"] > compact["height"]
    if how == "key":
        page.keyboard.press("Enter")
    else:
        disclosure.click()
    expect(disclosure).to_have_text("Show 3 progress messages")
    rendered(page)
    assert preview.bounding_box()["height"] == pytest.approx(compact["height"], abs=0.5)
    expect(disclosure).to_be_focused()
    collapsed = disclosure.bounding_box()
    assert (collapsed["x"], collapsed["y"]) == pytest.approx(
        (after["x"], after["y"]), abs=0.5
    )

    close = preview.get_by_role("button", name="Dismiss thread view", exact=True)
    head = close.bounding_box()
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    page.keyboard.type("Also check the dark scheme, " * 6, delay=0)
    rendered(page)
    assert close.bounding_box() == pytest.approx(head, abs=0.5)

    if how == "press":
        age = preview.locator(".lf-msg-meta time").last
        timestamp = datetime.fromisoformat(age.get_attribute("datetime"))
        page.clock.set_fixed_time(timestamp + timedelta(seconds=30))
        ticked(page)
        expect(age).to_have_text("just now")
        before_tick = disclosure.bounding_box()
        page.clock.set_fixed_time(timestamp + timedelta(seconds=60))
        ticked(page)
        expect(age).to_have_text("1m ago")
        rendered(page)
        assert disclosure.bounding_box()["x"] == pytest.approx(
            before_tick["x"], abs=0.5
        )
