"""Everyday browser contracts for shared chrome."""

import pytest
from browser.threads import open_panel_thread
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    panel_comment,
)
from render_harness import (
    LONG_PAGE,
    open_page,
    panel_field,
    panel_settled,
    resized,
    sending,
    write,
)

from leaf import event_log as events_model


# Each scheme and each pointer once: the faces compared are the same scheme's, and a
# finger changes the layout the two places stand in rather than their colours.
@pytest.mark.parametrize(
    ("touch", "scheme"),
    [(False, "light"), (True, "dark")],
    ids=["desktop-light", "touch-dark"],
)
def test_a_conversation_keeps_its_face_and_sends_from_margin_and_panel(
    browser, serve, scheme, touch
):
    """One conversation has the same typography and reply field in both places.

    A short opening and a long Markdown answer exercise both message roles. Compare
    the rendered faces instead of pinning a font size: changing the shared theme is
    allowed, shrinking only the panel's face is not. Both reply routes append to the
    same conversation.
    """
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Which detail should we keep?", {"section": "p0"}
    )
    answer = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "**Keep the evidence.** "
            + "Explain how the result was measured. " * 40,
        },
    )
    context = browser.new_context(has_touch=touch, is_mobile=touch, color_scheme=scheme)
    page = open_page(browser, url, context=context)
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
    margin = page.locator(".lf-margin-preview .lf-page-thread")
    expect(margin.get_by_role("textbox", name="Reply", exact=True)).to_be_visible()

    def faces(thread):
        return thread.evaluate(
            """thread => {
              const styles = (node, properties) => {
                const style = getComputedStyle(node);
                return Object.fromEntries(properties.map(p => [p, style.getPropertyValue(p)]));
              };
              const type = ['font-family', 'font-size', 'font-weight', 'line-height', 'color'];
              const field = thread.querySelector(
                '.lf-thread-reply leaf-text, .lf-fp-field leaf-text');
              return {
                messages: [...thread.querySelectorAll('.lf-msg')].map(message => ({
                  body: styles(message.querySelector('.lf-msg-body'), type),
                  author: styles(message.querySelector(':scope > .lf-msg-head b'), type),
                })),
                metadata: styles(thread.querySelector('.lf-msg-meta'), type),
                field: styles(field, [...type, 'padding-top', 'padding-right', 'padding-bottom',
                  'padding-left', 'min-height']),
                surround: styles(field.closest('.lf-compose-field'),
                  ['border-radius', 'border-top-width', 'border-top-color', 'background-color']),
              };
            }"""
        )

    anchored = faces(margin)
    assert len(anchored["messages"]) == 2
    panel = open_panel_thread(page, root)
    # The panel's view draws the messages, and its reply stands in the panel's field.
    viewed = faces(page.locator(".lf-floating-panel"))
    assert viewed["messages"] == anchored["messages"], scheme
    assert viewed["metadata"] == anchored["metadata"], scheme
    expect(panel.locator(f'.lf-msg[data-event="{answer["id"]}"]')).to_contain_text(
        "Keep the evidence."
    )
    write(panel_field(page), "Sent from Threads.")
    with sending(page, "the panel follow-up"):
        page.locator(".lf-fp-field").get_by_role(
            "button", name="Send", exact=True
        ).click()
    expect(panel.locator(".lf-msg").last).to_contain_text("Sent from Threads.")

    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
    write(
        margin.get_by_role("textbox", name="Reply", exact=True), "Sent beside the page."
    )
    with sending(page, "the anchored follow-up"):
        margin.get_by_role("button", name="Send", exact=True).click()
    expect(margin.locator(".lf-msg").last).to_contain_text("Sent beside the page.")
    sent = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply" and event["author"] == "user"
    ]
    assert [(event["parent"], event["text"]) for event in sent] == [
        (root, "Sent from Threads."),
        (root, "Sent beside the page."),
    ]


# The scheme reaches every surface through the same tokens, so dark runs once, on the
# composer a widget's thread outlet holds inside the widget's own tree.


import pytest
from render_harness import (
    page_comment,
)

from leaf.render_checks import rendered


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_scrolling_draft_shows_the_caret_s_row_with_the_padding_beside_it(
    engine, request, serve
):
    """A line typed at the end of a draft that scrolls leaves nothing below it to scroll
    to, and the caret taken to the first line leaves nothing above. Revealing only the
    caret, as a native textarea does, left the field's padding out of view, and in
    Firefox the foot of the caret's row too."""
    page = open_page(request.getfixturevalue(engine), serve(LONG_PAGE))
    field = page_comment(page)
    hidden = """box => ({
      below: box.scrollHeight - box.clientHeight - box.scrollTop,
      above: box.scrollTop,
    })"""
    page.keyboard.type("line 0")
    for line in range(1, 40):
        page.keyboard.press("Shift+Enter")
        page.keyboard.type(f"line {line}")
        if field.evaluate("box => box.scrollHeight > box.clientHeight + 40"):
            break
    else:
        raise AssertionError("the draft never scrolled")
    for key in ("Shift+Enter", "w", "ControlOrMeta+Home"):
        page.keyboard.press(key)
        rendered(page)
        shown = field.evaluate(hidden)
        if key == "ControlOrMeta+Home":
            assert shown["above"] < 1, shown
        else:
            assert shown["below"] < 1, (key, shown)
