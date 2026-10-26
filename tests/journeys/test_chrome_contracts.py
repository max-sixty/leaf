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
    resized(page, 390 if touch else 1440, 900)
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


def test_opening_a_line_under_the_last_moves_no_words(browser, serve):
    """Shift+Enter opens a line under a draft's last words, and once the first
    character typed there lands, every word above rests where it did: Send's room
    stands on every line, so no keystroke at the end changes where the lines above
    wrap."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page = open_page(
        browser,
        url,
        init_script="""
          window.editorRoots = new Map();
          const attach = Element.prototype.attachShadow;
          Element.prototype.attachShadow = function(options) {
            const root = attach.call(this, options);
            if (this.localName === 'leaf-text') window.editorRoots.set(this, root);
            return root;
          };
        """,
    )
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    open_panel_thread(page, root)
    field = panel_field(page)
    field.click()

    def reading():
        return field.evaluate(
            """host => {
              const rows = [];
              for (const line of window.editorRoots.get(host).querySelectorAll('.cm-line')) {
                const range = document.createRange();
                range.selectNodeContents(line);
                for (const r of range.getClientRects()) {
                  if (r.width < 0.5) continue;
                  const row = rows.find(o => Math.abs(o.top - r.top) < 4);
                  if (row) row.right = Math.max(row.right, r.right);
                  else rows.push({top: r.top, right: r.right});
                }
              }
              const box = host.getBoundingClientRect();
              return {top: box.top, height: box.height,
                      rows: rows.sort((a, b) => a.top - b.top)
                        .map((row) => ({top: row.top - box.top, right: row.right}))};
            }"""
        )

    page.keyboard.insert_text(
        "The first paragraph runs long enough to wrap once, and then runs on a while"
    )
    # A newly grown line carries the existing words with the panel edge; compare
    # the resulting places after that ride finishes.
    panel_settled(page)
    full = reading()
    page.keyboard.press("Shift+Enter")
    panel_settled(page)
    opened = reading()
    page.keyboard.type("S")
    panel_settled(page)
    typed = reading()
    assert typed["height"] == opened["height"], (opened, typed)
    assert typed["top"] == opened["top"], (opened, typed)
    assert typed["rows"][: len(full["rows"])] == opened["rows"][: len(full["rows"])], (
        opened,
        typed,
    )
    assert [row["right"] for row in opened["rows"]] == [
        row["right"] for row in full["rows"]
    ], (full, opened)


# The scheme reaches every surface through the same tokens, so dark runs once, on the
# composer a widget's thread outlet holds inside the widget's own tree.
