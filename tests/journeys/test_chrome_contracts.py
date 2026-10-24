"""Everyday browser contracts for shared chrome."""

import pytest
from browser.test_chrome_contracts import (
    FACE,
    FACES,
    MARKDOWN,
    PHONE_PAGE,
)
from browser.threads import open_panel_thread
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    panel_comment,
)
from render_cases_navigation import source_revision
from render_harness import (
    LONG_PAGE,
    PANEL,
    CutOff,
    expect_panel_says,
    leaf_page,
    nudge,
    open_page,
    page_comment,
    panel_field,
    panel_settled,
    resized,
    round_trip,
    selection_field,
    sending,
    told,
    write,
)

from leaf import data as data_model
from leaf import event_log as events_model


def test_agent_reply_arrivals_keep_open_panel_drafts_and_summarize_batches(
    browser, serve
):
    """Unread replies announce once each, whether they arrive while the page is open or
    were waiting when it opened, regardless of the panel's disclosure. The user keeps
    a draft open in a thread no reply lands in, so exposure acknowledges none of them."""
    url = serve(leaf_page("Reply arrivals", "<h1>Reply arrivals</h1>"))
    directory = serve.page_dir
    drafting, a, b = (
        append_carried_log_record(
            directory,
            {"kind": "comment", "author": "user", "revision": 1, "text": text},
        )
        for text in ("Draft here", "A", "B")
    )
    append_carried_log_record(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": a["id"],
            "text": "Earlier",
        },
    )
    page = open_page(browser, url)
    live = page.locator(".lf-live")
    expect(live).to_have_text("Codex replied")

    open_panel_thread(page, drafting["id"])
    draft = panel_field(page)
    write(draft, "Keep this draft")
    draft.focus()
    page.evaluate(
        """() => {
          window.__lfReplyAnnouncements = [];
          new MutationObserver(() => {
            const words = document.querySelector('.lf-live').textContent;
            if (words) window.__lfReplyAnnouncements.push(words);
          }).observe(document.querySelector('.lf-live'), {childList: true, subtree: true});
        }"""
    )
    append_carried_log_record(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": b["id"],
            "text": "For B",
        },
    )
    told(page)
    expect(live).to_have_text("Codex replied")
    expect(draft).to_be_focused()
    expect(draft).to_have_js_property("value", "Keep this draft")

    reads = CutOff().hold(page)
    append_carried_log_record(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": a["id"],
            "text": "More for A",
        },
    )
    append_carried_log_record(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": b["id"],
            "text": "More for B",
        },
    )
    reads.restore()
    told(page)
    expect(live).to_have_text("2 replies in 2 threads")
    expect(draft).to_be_focused()
    expect(draft).to_have_js_property("value", "Keep this draft")

    # A fresh server snapshot of unchanged content makes no fresh announcement;
    # a fresh document announces what the user has still not read. Moving the
    # freshness token ensures this actually admits another read.
    nudge(directory)
    told(page)
    round_trip(page)
    expect(live).to_have_text("2 replies in 2 threads")
    assert page.evaluate("() => window.__lfReplyAnnouncements") == [
        "Codex replied",
        "2 replies in 2 threads",
    ]
    page.reload()
    expect(page.locator(".lf-live")).to_have_text("4 replies in 2 threads")


def test_interrupted_background_notice_keeps_the_newer_version(browser, serve):
    """An older visible notice cannot replace a newer one already waiting."""
    page = open_page(browser, serve(leaf_page("Notice order", "<h1>Notice order</h1>")))
    page.evaluate(
        """async () => {
          const {notice} = await window.__lfWidgetApi();
          notice('Updated to v3', {background: true});
          notice('Updated to v4', {background: true});
          notice('Saved — sent');
        }"""
    )
    expect_panel_says(page, "Saved — sent")
    expect_panel_says(page, "Updated to v4")


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


def test_opening_a_line_under_a_full_last_line_moves_no_words(browser, serve):
    """Send's room stands after the field's last words, so it changes lines with the
    keystroke that changes the lines. A last line whose words fill the field puts the
    room on a line of its own; Shift+Enter then opens the new line in that room's
    place and the first character typed there moves nothing above it. When the room
    stayed on the last line with words instead, that first character took it away and
    the field shrank under the caret."""
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
                      rows: rows.sort((a, b) => a.top - b.top)};
            }"""
        )

    page.keyboard.insert_text("The first paragraph runs long enough to wrap once")
    before = reading()
    for key in "abcde " * 40:
        page.keyboard.type(key)
        after = reading()
        if after["height"] > before["height"] and len(after["rows"]) == len(
            before["rows"]
        ):
            break
        before = after
    else:
        pytest.fail("no last line filled the field before its room")
    # A newly grown line carries the existing words with the panel edge; compare
    # the resulting places after that ride finishes.
    panel_settled(page)
    full = reading()
    page.keyboard.press("Shift+Enter")
    panel_settled(page)
    opened = reading()
    page.keyboard.type("S")
    typed = reading()
    assert opened["height"] == full["height"] == typed["height"], (full, opened, typed)
    assert opened["top"] == full["top"] == typed["top"]
    assert typed["rows"][: len(full["rows"])] == full["rows"]


@pytest.mark.parametrize("viewport", [None, "width=device-width, initial-scale=1"])
def test_a_phone_starts_the_page_and_comments_on_a_selection(iphone, serve, viewport):
    """The runtime starts in WebKit; the panel's field offers to comment on a selection.

    A module feature WebKit lacks fails the whole module graph before the runtime runs:
    CSS module scripts did, and an iPhone user saw only that Leaf could not start. A
    long press that selects words hands the page no mouseup, and Playwright cannot make
    one, so the selection is placed with no pointer gesture at all."""
    source = PHONE_PAGE
    if viewport:
        source = source.replace(
            "<head>", f'<head><meta name="viewport" content="{viewport}">'
        )
    page = open_page(None, serve(source), context=iphone)
    assert page.evaluate("innerWidth") == page.viewport_size["width"]
    metas = page.locator('meta[name="viewport"]')
    expect(metas).to_have_count(1)
    expect(metas).to_have_attribute(
        "content", viewport or "width=device-width, initial-scale=1, viewport-fit=cover"
    )
    page.locator("#p1").evaluate("""paragraph => {
      const range = document.createRange();
      range.setStart(paragraph.firstChild, 0);
      range.setEnd(paragraph.firstChild, "Paragraph one".length);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }""")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_hidden()
    # The panel's field quotes the selection, where the finger that made it finds it,
    # and the marks keep their seats; the leaf's menu stays shut.
    comment = selection_field(page)
    expect(comment).to_have_attribute("placeholder", "“Paragraph one”")
    expect(page.locator(PANEL)).not_to_have_attribute("data-menu", "")
    expect(page.locator(".lf-fp-threads")).to_be_visible()
    box = comment.bounding_box()
    assert box["x"] + box["width"] <= page.evaluate("innerWidth"), box
    comment.tap()
    expect(page.locator(PANEL)).not_to_have_attribute("data-menu", "")
    expect(field).to_be_focused()
    write(field, "From a phone")
    with sending(page, "the comment"):
        page.locator(".lf-fab-bar").get_by_role(
            "button", name="Comment", exact=True
        ).tap()
    [comment] = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert comment["text"] == "From a phone"
    assert comment["anchor"]["quote"] == "Paragraph one", comment


# The scheme reaches every surface through the same tokens, so dark runs once, on the
# composer a widget's thread outlet holds inside the widget's own tree.
@pytest.mark.parametrize(
    "surface, scheme",
    [
        *((surface, "light") for surface in ("general", "panel", "margin", "outlet")),
        ("outlet", "dark"),
    ],
)
def test_a_draft_wears_the_faces_its_sent_message_wears(
    browser, serve, surface, scheme
):
    """The composer draws each inline construct the way the message will.

    The field stands in a closed shadow root, where the theme's element rules do not
    reach, so it reads the faces from the theme's tokens instead of stating its own.
    It had stated its own from birth, and code sat a size and a chip shape away from
    how it arrived. DevTools reads the closed root, as it reads any.
    """
    if surface == "outlet":
        url = serve(
            leaf_page(
                "Draft faces",
                "<h1>Draft faces</h1>"
                '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff>',
            )
        )
        data_model.cmd_data_set(
            serve.page_dir,
            "review-patch",
            """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-return "old"
+return "new"
""",
        )
        anchor = {
            "section": "patch",
            "datum": '["app.py","new",1]',
            "source": "review-patch",
            "source_revision": source_revision(serve.page_dir, "review-patch"),
        }
    else:
        url = serve(LONG_PAGE)
        anchor = {"section": "p0"}
    panel_comment(serve.page_dir, MARKDOWN, anchor)
    page = open_page(browser, url, color_scheme=scheme)
    if surface == "outlet":
        thread = page.locator("#patch .lf-page-thread")
        box_selector = "#patch .lf-thread-reply leaf-text"
    elif surface == "margin":
        resized(page, 1440, 900)
        page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
        thread = page.locator(".lf-margin-preview .lf-page-thread")
        box_selector = ".lf-margin-preview .lf-thread-reply leaf-text"
    else:
        root = next(
            event["id"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "comment"
        )
        thread = open_panel_thread(page, root)
        box_selector = '.lf-fp-field leaf-text[name="reply"]'
    body = thread.locator(".lf-msg-body").first
    expect(body.locator("blockquote")).to_be_visible()
    # A source renderer can leave the code's colors correct while turning an inline
    # phrase into a separate block. Read its line beside the preceding prose too.
    flow = body.locator("p code").evaluate("""code => {
      const words = document.createRange();
      words.selectNode(code.previousSibling);
      return {words: words.getBoundingClientRect().top,
              code: code.getBoundingClientRect().top};
    }""")
    assert flow["code"] == pytest.approx(flow["words"], abs=4), flow
    # Read first: the page's general box stands in the panel's field with no view open,
    # the one place a page thread starts, so writing there puts the thread's view away.
    sent = body.evaluate(
        """(body, [faces, face]) => Object.fromEntries(Object.entries(faces)
          .map(([name, [selector]]) => {
            const style = getComputedStyle(body.querySelector(selector));
            return [name, Object.fromEntries(
              [...face, "font-size"].map((p) => [p, style.getPropertyValue(p)]))];
          }))""",
        [FACES, FACE],
    )
    sent_size = body.evaluate("body => getComputedStyle(body).fontSize")
    box = page_comment(page) if surface == "general" else page.locator(box_selector)
    write(box, MARKDOWN)
    box.evaluate("box => box.id = 'draft-face-editor'")
    cdp = page.context.new_cdp_session(page)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    document = cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})["root"]

    def find(node):
        attrs = node.get("attributes", [])
        if dict(zip(attrs[::2], attrs[1::2])).get("id") == "draft-face-editor":
            return node
        for child in node.get("children", []) + node.get("shadowRoots", []):
            if found := find(child):
                return found
        return None

    root = find(document)["shadowRoots"][0]["nodeId"]

    def drawn(selector):
        node = cdp.send("DOM.querySelector", {"nodeId": root, "selector": selector})
        assert node["nodeId"], f"the draft draws no {selector}"
        style = {
            entry["name"]: entry["value"]
            for entry in cdp.send(
                "CSS.getComputedStyleForNode", {"nodeId": node["nodeId"]}
            )["computedStyle"]
        }
        return {name: style[name] for name in [*FACE, "font-size"]}

    draft = {name: drawn(selector) for name, (_, selector) in FACES.items()}

    # Inline constructs are sized against the words around them, and the draft's words
    # are the box's type where the message's are the body's.
    def px(value):
        return float(value.removesuffix("px"))

    size = {
        "draft": box.evaluate("box => getComputedStyle(box).fontSize"),
        "sent": sent_size,
    }
    for face, which in ((draft, "draft"), (sent, "sent")):
        for name in FACES:
            share = px(face[name]["font-size"]) / px(size[which])
            face[name]["font-size"] = round(share, 3)
    differ = {
        name: {
            k: (v, sent[name][k]) for k, v in draft[name].items() if v != sent[name][k]
        }
        for name in FACES
    }
    assert not any(differ.values()), differ
