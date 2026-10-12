"""The native dictation affordance shares the comment editor's normal send contract.

Recognition events are covered at their controller boundary under tests/runtime;
this browser journey checks the real composers and their registered controls without
depending on a remote speech service or replacing a browser API.
"""

from playwright.sync_api import expect
from render_cases_interaction import SEATED_ASK_LAYER, SEATED_ASK_WIDGETS
from render_harness import leaf_page, open_page, page_comment, sending, write


def test_every_comment_surface_shares_the_empty_microphone_and_typed_send(
    browser, serve
):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Comment dictation",
                '<h1 id="title">Weekend service</h1>'
                '<p id="passage">The shuttle runs every hour on Sunday.</p>'
                '<lf-verdict id="proposal" asks>Should the shuttle run earlier?</lf-verdict>',
            ),
            layer_registry=SEATED_ASK_LAYER,
            layer_widgets=SEATED_ASK_WIDGETS,
        ),
    )
    supported = page.evaluate(
        "!!(window.SpeechRecognition || window.webkitSpeechRecognition)"
    )

    def enter_words(box, words):
        field = box.locator("leaf-text")
        mic = box.locator(".lf-compose-dictate")
        send = box.locator(".lf-compose-submit:not(.lf-compose-dictate)")
        if supported:
            expect(mic).to_be_visible()
            expect(mic).to_have_attribute("aria-label", "Dictate")
            before = mic.bounding_box()
            before_field = box.locator(".lf-compose-field").bounding_box()
            expect(send).to_be_hidden()
        else:
            expect(mic).to_have_count(0)
        write(field, words)
        expect(mic).to_be_hidden()
        expect(send).to_be_visible()
        expect(send).to_have_attribute("aria-disabled", "false")
        if supported:
            after = send.bounding_box()
            after_field = box.locator(".lf-compose-field").bounding_box()
            assert (
                abs(
                    (before_field["x"] + before_field["width"] - before["x"])
                    - (after_field["x"] + after_field["width"] - after["x"])
                )
                < 1
            )
            assert (
                abs((before["y"] - before_field["y"]) - (after["y"] - after_field["y"]))
                < 1
            )
        return field

    # The page card returns empty after sending.
    page_comment(page)
    card = page.locator(".lf-page-comment-card")
    field = enter_words(card, "Please add the Sunday timetable.")
    with sending(page, "page comment"):
        field.press("Enter")
    expect(card).to_be_hidden()
    page_comment(page)
    if supported:
        expect(card.locator(".lf-compose-dictate")).to_be_visible()
    card.locator("leaf-text").press("Escape")

    # A widget's first message and its continuing reply use the same composer.
    first = page.locator("#proposal > .lf-thread-seat > .lf-say")
    field = enter_words(first, "An earlier shuttle would help.")
    with sending(page, "widget comment"):
        field.press("Enter")
    widget_reply = page.locator("#proposal .lf-page-thread > .lf-thread-reply")
    expect(widget_reply).to_be_visible()
    field = enter_words(widget_reply, "Especially on Sunday mornings.")
    with sending(page, "widget reply"):
        field.press("Enter")
    if supported:
        expect(widget_reply.locator(".lf-compose-dictate")).to_be_visible()

    # The floating anchored composer uses the identical action position.
    page.locator("#passage").click(modifiers=["Alt"], position={"x": 30, "y": 8})
    anchored = page.locator(".lf-composer")
    expect(anchored).to_be_visible()
    field = enter_words(anchored, "Could this run every half hour?")
    with sending(page, "anchored comment"):
        field.press("Enter")

    # A reply retained in Threads restores the microphone when its send clears it.
    page.locator(".lf-threads-toggle").click()
    thread = page.locator(".lf-threads > .lf-thread").filter(
        has_text="Please add the Sunday timetable."
    )
    thread.locator(":scope > .lf-thread-summary").click()
    reply = thread.locator(":scope > .lf-thread-reply")
    field = enter_words(reply, "And the first departure time.")
    with sending(page, "panel reply"):
        field.press("Enter")
    expect(thread).to_contain_text("And the first departure time.")
    if supported:
        expect(reply.locator(".lf-compose-dictate")).to_be_visible()
