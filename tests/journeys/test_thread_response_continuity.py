"""Thread response geometry through delivery refusal and retry."""

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_navigation import source_revision
from render_harness import leaf_page, open_page, page_comment, round_trip, write

EDITOR_INSPECTION = """(() => {
  const attach = Element.prototype.attachShadow;
  window.replyEditorRoots = new WeakMap();
  Element.prototype.attachShadow = function(options) {
    const root = attach.call(this, options);
    replyEditorRoots.set(this, root);
    return root;
  };
})()"""


def reply_editing_pose(editor):
    """Read the first visible line and Send without relying on node continuity."""
    return editor.evaluate("""box => {
      const range = document.createRange();
      range.selectNodeContents(replyEditorRoots.get(box).querySelector('.cm-line'));
      const field = box.getBoundingClientRect();
      const send = box.closest('.lf-compose-field')
        .querySelector('.lf-thread-send').getBoundingClientRect();
      return {top: field.top, height: field.height,
        firstLine: range.getBoundingClientRect().top,
        sendTop: send.top, sendBottom: send.bottom};
    }""")


@pytest.mark.parametrize(
    ("place", "edit", "platform"),
    [
        ("seat", "delete", "desktop"),
        ("margin", "delete", "desktop"),
        ("seat", "mirrored", "desktop"),
        ("seat", "resize", "desktop"),
        ("seat", "resize-paste", "desktop"),
        ("seat", "resize-replace", "desktop"),
        # Android's EditContext input reaches the renderer without a DOM beforeinput.
        ("seat", "resize-insert", "android"),
        ("seat", "mirrored-composing", "android"),
    ],
)
def test_native_reply_edits_after_semantic_paint_keep_the_first_line(
    browser, serve, place, edit, platform
):
    """A semantic paint of a tall draft must not retain its height after native edits.

    These surfaces do not repaint on every keystroke as the panel does. News captures
    the same continuity extent, so a panel-only draft fix would leave them broken.
    """
    from render_cases_interaction import SEATED_ASK_PAGE
    from render_harness import told

    if place == "seat":
        source = SEATED_ASK_PAGE
        anchor = {"section": "jobs"}
        selector = '[data-lf-thread-seat="jobs"] > .lf-page-thread'
    else:
        source = leaf_page(
            "Reply editing",
            '<h1 id="h">Review the release</h1><p id="plan">Keep the order visible.</p>',
        )
        anchor = {"section": "plan"}
        selector = ".lf-margin-preview .lf-page-thread"
    url = serve(source)
    parent = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep the review clear.",
            "anchor": anchor,
        },
    )["id"]
    viewport = (
        {"width": 560, "height": 1100}
        if edit.startswith("resize")
        else {"width": 1920, "height": 900}
    )
    device = (
        {
            "user_agent": (
                "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/153.0.0.0 Mobile Safari/537.36"
            ),
            "is_mobile": True,
            "has_touch": True,
        }
        if platform == "android"
        else {}
    )
    context = browser.new_context(viewport=viewport, reduced_motion="reduce", **device)
    page = open_page(browser, url, context=context, init_script=EDITOR_INSPECTION)
    if place == "margin":
        page.locator('[data-lf-margin-for="plan"] .lf-margin-marker').click()
    owner = page.locator(selector)
    editor = owner.locator("leaf-text")
    rendered(page)
    draft = (
        "A stable native draft that wraps at the narrow width. " * 8
        if edit.startswith("resize")
        else "First line\n\n\n\n"
    )
    write(editor, draft)
    rendered(page)
    news = (
        {
            "kind": "thread_title",
            "author": "agent",
            "thread": parent,
            "title": "Release review",
        }
        if place == "margin" or edit.startswith("resize")
        else {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": parent,
            "text": "The release is ready.",
        }
    )
    events_model.append_event(serve.page_dir, news)
    told(page)
    rendered(page)
    if edit.startswith("resize"):
        narrow = editor.bounding_box()
        page.set_viewport_size({"width": 1600, "height": 1100})
        rendered(page)
        before = editor.bounding_box()
        assert before["height"] < narrow["height"] - 20, (narrow, before)
        if platform == "android":
            # CodeMirror's EditContext input updates the renderer from a native
            # textupdate, without a DOM beforeinput or an already changed layout.
            editor.evaluate("""box => {
              window.androidReplyEvents = [];
              for (const type of ['beforeinput', 'lf-before-edit', 'input'])
                document.addEventListener(type, event => {
                  if (event.composedPath().includes(box))
                    window.androidReplyEvents.push(type);
                }, {capture: true});
            }""")
        expected = draft + "!"
        if edit == "resize-paste":
            # The browser's Paste command reaches CodeMirror without keydown or
            # beforeinput, as a context-menu paste does. Preserve the OS clipboard.
            page.context.grant_permissions(["clipboard-read", "clipboard-write"])
            page.evaluate("""async () => {
              window.previousReplyClipboard = await navigator.clipboard.read();
            }""")
            try:
                page.evaluate("""async () => {
                  await navigator.clipboard.writeText('!');
                  window.replyPasteEvents = [];
                  for (const type of ['keydown', 'beforeinput', 'paste'])
                    document.addEventListener(type,
                      () => window.replyPasteEvents.push(type), {capture: true});
                }""")
                page.context.new_cdp_session(page).send(
                    "Input.dispatchKeyEvent",
                    {"type": "char", "key": "Unidentified", "commands": ["Paste"]},
                )
                expect(editor).to_have_js_property("value", expected)
                assert page.evaluate("window.replyPasteEvents") == ["paste"]
            finally:
                page.evaluate("""async () => {
                  const previous = window.previousReplyClipboard;
                  if (previous.length) await navigator.clipboard.write(previous);
                  else await navigator.clipboard.writeText('');
                }""")
        elif edit == "resize-insert":
            expected = draft + "\n\n\nMore"
            page.keyboard.insert_text("\n\n\nMore")
        elif edit == "resize-replace":
            expected = "Short replacement"
            editor.evaluate("box => box.select()")
            page.keyboard.insert_text(expected)
        else:
            page.keyboard.type("!")
        rendered(page)
        if platform == "android":
            assert page.evaluate("window.androidReplyEvents") == [
                "lf-before-edit",
                "input",
            ]
        now = editor.bounding_box()
        if edit in ("resize", "resize-paste"):
            assert now["height"] == pytest.approx(before["height"], abs=0.5), (
                before,
                now,
            )
        elif edit == "resize-insert":
            # Moving Send to the new last line can also remove a wrapped row.
            assert now["height"] > before["height"], (before, now)
            assert now["height"] == pytest.approx(
                editor.evaluate("box => box.naturalBlockSize"), abs=0.5
            ), (before, now)
        else:
            assert now["height"] < before["height"] - 50, (before, now)
        assert now["y"] == pytest.approx(before["y"], abs=0.5), (before, now)
        expect(editor).to_have_js_property("value", expected)
        expect(editor).to_be_focused()
        return
    if edit.startswith("mirrored"):
        editor.evaluate("""box => {
          window.mirroredReplyEdits = [];
          for (const type of ['lf-before-edit', 'input'])
            box.addEventListener(type, () => window.mirroredReplyEdits.push(type));
        }""")
        other = open_page(browser, url, context=context)
        if edit == "mirrored-composing":
            page.bring_to_front()
            editor.focus()
            editor.evaluate("box => box.select()")
            context.new_cdp_session(page).send(
                "Input.imeSetComposition",
                {"text": "Composing", "selectionStart": 9, "selectionEnd": 9},
            )
            expect(editor).to_have_js_property("value", "Composing")
            rendered(page)
            page.evaluate("window.mirroredReplyEdits = []")
        else:
            other.bring_to_front()
        standing = reply_editing_pose(editor)
        other.evaluate(
            """async parent => {
              const {saveDraft, tellDraft} = await window.__lfRuntimeImport('/runtime/drafts.js');
              saveDraft('reply:' + parent, 'First line');
              tellDraft('reply:' + parent, 'First line');
            }""",
            parent,
        )
        expect(other.locator(selector).locator("leaf-text")).to_have_js_property(
            "value", "First line"
        )
        expect(editor).to_have_js_property("value", "First line")
        page.bring_to_front()
        editor.focus()
        rendered(page)
        assert page.evaluate("window.mirroredReplyEdits") == []
        mirrored = reply_editing_pose(editor)
        for coordinate in standing:
            assert mirrored[coordinate] == pytest.approx(
                standing[coordinate], abs=0.5
            ), (
                standing,
                mirrored,
            )
        before = editor.bounding_box()
        if platform == "android":
            page.keyboard.insert_text("!")
        else:
            page.keyboard.type("!")
        rendered(page)
        now = editor.bounding_box()
        assert now["y"] == pytest.approx(before["y"], abs=0.5), (before, now)
        expect(editor).to_have_js_property("value", "First line!")
        expect(editor).to_be_focused()
        page.keyboard.press("ControlOrMeta+z")
        expect(editor).to_have_js_property("value", "First line")
        page.keyboard.press("ControlOrMeta+z")
        expect(editor).to_have_js_property("value", "First line")
        return
    before = editor.bounding_box()
    for _ in range(4):
        page.keyboard.press("Backspace")
        rendered(page)
        now = editor.bounding_box()
        assert now["y"] == pytest.approx(before["y"], abs=0.5), (before, now)
    assert now["height"] < before["height"] - 50, (before, now)
    expect(editor).to_have_js_property("value", "First line")
    expect(editor).to_be_focused()


def test_passive_reply_room_ends_at_native_edit_and_new_inline_measure(browser, serve):
    """Mirrors retain the writing room; canceled input retains it and edits resize it."""
    from render_cases_interaction import SEATED_ASK_PAGE
    from render_harness import stored_draft_text, told

    url = serve(SEATED_ASK_PAGE)
    parent = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep the review clear.",
            "anchor": {"section": "jobs"},
        },
    )["id"]
    context = browser.new_context(
        viewport={"width": 560, "height": 1100}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context, init_script=EDITOR_INSPECTION)
    selector = '[data-lf-thread-seat="jobs"] > .lf-page-thread leaf-text'
    editor = page.locator(selector)
    write(editor, "First line\n\n\n\n")
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "thread_title",
            "author": "agent",
            "thread": parent,
            "title": "Release review",
        },
    )
    told(page)
    rendered(page)
    standing = reply_editing_pose(editor)
    other = open_page(browser, url, context=context)
    replacement = "\n".join(
        [
            "First line",
            "Second line",
            "Third line",
            "Fourth line",
            "Fifth line",
            "Sixth line",
            "Seventh line",
            "Wrap this passage naturally at the editor's inline measure. " * 5,
        ]
    )
    other.evaluate(
        """async ({parent, value}) => {
          const {saveDraft, tellDraft} = await window.__lfRuntimeImport('/runtime/drafts.js');
          saveDraft('reply:' + parent, value);
          tellDraft('reply:' + parent, value);
        }""",
        {"parent": parent, "value": replacement},
    )
    expect(editor).to_have_js_property("value", replacement)
    rendered(page)
    mirrored = reply_editing_pose(editor)
    for coordinate in standing:
        assert mirrored[coordinate] == pytest.approx(standing[coordinate], abs=0.5), (
            standing,
            mirrored,
        )
    assert stored_draft_text(page, "reply:" + parent) == replacement
    page.bring_to_front()
    editor.focus()
    editor.evaluate("""box => {
      const content = replyEditorRoots.get(box).querySelector('.cm-content');
      content.addEventListener('beforeinput', event => {
        window.canceledReplyAttempt = {trusted: event.isTrusted,
          cancelable: event.cancelable};
        event.preventDefault();
      }, {once: true});
    }""")
    page.keyboard.insert_text("Canceled")
    assert page.evaluate("window.canceledReplyAttempt") == {
        "trusted": True,
        "cancelable": True,
    }
    expect(editor).to_have_js_property("value", replacement)
    rendered(page)
    canceled = reply_editing_pose(editor)
    for coordinate in standing:
        assert canceled[coordinate] == pytest.approx(standing[coordinate], abs=0.5), (
            standing,
            canceled,
        )
    page.keyboard.insert_text("!")
    expect(editor).to_have_js_property("value", replacement + "!")
    rendered(page)
    edited = reply_editing_pose(editor)
    assert edited["height"] > standing["height"] + 50, (standing, edited)
    for coordinate in ("top", "firstLine"):
        assert edited[coordinate] == pytest.approx(standing[coordinate], abs=0.5), (
            standing,
            edited,
        )
    page.set_viewport_size({"width": 1600, "height": 1100})
    rendered(page)
    widened = reply_editing_pose(editor)
    assert widened["height"] < edited["height"] - 20, (edited, widened)
    page.keyboard.insert_text("?")
    expect(editor).to_have_js_property("value", replacement + "!?")
    rendered(page)
    after = reply_editing_pose(editor)
    assert after["top"] == pytest.approx(widened["top"], abs=0.5), (widened, after)


# A native thread body, a scroll boundary inside the page, the floating card and the
# panel: the seat shares the outlet's native body, and the boundary with room to spare
# the one at its end.
@pytest.mark.parametrize("place", ["outlet", "nested-end", "margin", "panel"])
def test_refused_reply_retains_its_live_foot(browser, serve, place):
    """Removing a provisional turn preserves the live action and following passage.

    Native and panel thread bodies and both scroll boundaries exercise the same rule.
    The refused draft is retryable, and only its eventual acceptance reaches the log.
    """
    from render_harness import (
        consume_browser_errors,
        holding,
        panel_settled,
        scroll_settled,
        stored_draft_text,
    )

    tail = '<p id="continuity-tail">Review the next step here.</p>'
    if place in ("margin", "panel"):
        authored = leaf_page(
            "Response continuity",
            '<h1 id="h">Shipping order</h1><p id="plan">Keep the release order visible.</p>'
            + tail,
        )
        anchor = {"section": "plan"}
        selector = (
            ".lf-margin-preview .lf-page-thread"
            if place == "margin"
            else ".lf-threads > .lf-thread"
        )
    else:
        contents = (
            '<h1 id="h">Shipping order</h1><lf-diff id="patch" source="change"><pre></pre></lf-diff>'
            + tail
        )
        if place == "nested-end":
            contents = (
                '<div id="continuity-scroll" style="height:550px;overflow:auto"><div style="height:250px"></div>'
                + contents
                + "</div>"
            )
        authored = leaf_page("Response continuity", contents)
        anchor = {"section": "patch", "datum": '["app.py","new",1]', "source": "change"}
        selector = "lf-diff .lf-page-thread"
    url = serve(authored)
    if place not in ("margin", "panel"):
        data_model.cmd_data_set(
            serve.page_dir,
            "change",
            'diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-return "old"\n+return "new"\n',
        )
        anchor["source_revision"] = source_revision(serve.page_dir, "change")
    parent = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep the shipping order visible.",
            "anchor": anchor,
        },
    )["id"]
    context = browser.new_context(
        viewport={"width": 1600, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    if place == "margin":
        page.locator(".lf-margin-marker").first.click()
    elif place == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        if page.locator(selector).get_attribute("open") is None:
            page.locator(selector).locator(".lf-thread-summary").click()
    owner = page.locator(selector)
    draft = owner.locator("leaf-text")
    expect(draft).to_be_visible()
    if place == "nested-end":
        page.evaluate("""async () => {
          const body = document.querySelector('#continuity-scroll');
          const {registerReadingRegion} = await window.__lfRuntimeImport('/runtime/reading-regions.js');
          registerReadingRegion({id: 'continuity-scroll', host: body, body});
        }""")
    held = []

    def hold(route):
        if route.request.post_data_json["kind"] == "reply":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold)
    words = "  Preserve this newer thought.\nIts spaces matter.  "
    write(draft, words)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the reply that will be refused")
    rendered(page)
    if place == "nested-end":
        scroller = page.locator("#continuity-scroll")
        scroller.evaluate("node => {node.scrollTop = node.scrollHeight}")
        scroll_settled(page, scroller)
    attempt = held[0].request.post_data_json["attempt"]
    assert held[0].request.post_data_json["parent"] == parent

    def pose():
        return owner.evaluate("""node => {
          const rect = subject => {
            const {left, top, bottom} = subject.getBoundingClientRect();
            return {left, top, bottom};
          };
          const action = [...node.querySelectorAll('.lf-compose-submit, .lf-compose-dictate')]
            .find(button => button.checkVisibility());
          const pose = {action: rect(action),
            tail: rect(document.querySelector('#continuity-tail'))};
          const close = document.querySelector('.lf-margin-preview-close');
          if (close?.checkVisibility()) pose.close = rect(close);
          const popup = node.closest('.lf-margin-preview');
          if (popup) {
            const bounds = popup.getBoundingClientRect();
            const fits = rect => rect.left >= bounds.left && rect.right <= bounds.right
              && rect.top >= bounds.top && rect.bottom <= bounds.bottom;
            const field = node.querySelector('leaf-text').getBoundingClientRect();
            if (!fits(field) || !fits(action.getBoundingClientRect()))
              throw new Error('the floating reply exceeds its allocated card');
          }
          return pose;
        }""")

    pending = pose()
    assert 0 < pending["action"]["top"] < pending["action"]["bottom"] < 900
    held.pop().fulfill(
        status=400,
        json={
            "ok": False,
            "attempt": attempt,
            "error": "refused before append",
            "final": True,
        },
    )
    round_trip(page)
    rendered(page)
    consume_browser_errors(page, {"code": "failed-load", "status": 400})
    restored = pose()
    for node in pending:
        for edge in pending[node]:
            assert abs(restored[node][edge] - pending[node][edge]) < 0.5, (
                pending,
                restored,
            )
    assert draft.evaluate("node => node.value") == words
    assert stored_draft_text(page, f"reply:{parent}") == words
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    draft.focus()
    page.keyboard.press("Enter")
    holding(page, held, 1, "the refused reply's retry")
    assert held[0].request.post_data_json["attempt"] == attempt
    held.pop().continue_()
    round_trip(page)
    rendered(page)
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert len(replies) == 1
    assert (replies[0]["parent"], replies[0]["text"], replies[0]["attempt"]) == (
        parent,
        words,
        attempt,
    )
    assert draft.evaluate("node => node.value") == ""
    pose()
    page.unroute_all(behavior="wait")


def test_direct_comment_arrival_keeps_its_canceled_entry_motion_canceled(
    browser, serve
):
    """Clearing a sent draft and editing the next never restart thread entry motion.

    Native animation events observe the displayed transform, rather than the
    renderer's remembered flags, through the real held send and later repaint.
    """
    from leaf.render_checks import wait_for_probe
    from leaf_dev import ROOT
    from render_harness import holding, scroll_settled

    context = browser.new_context(
        viewport={"width": 1600, "height": 900}, reduced_motion="no-preference"
    )
    page = open_page(
        browser, serve(ROOT / "examples/review-a-plan.html"), context=context
    )
    page.locator(".lf-threads-toggle").click()
    field = page_comment(page)
    page.evaluate("""() => {
      window.__recuedArrivals = [];
      document.addEventListener('animationstart', event => {
        const card = event.target;
        if (!card.matches?.('.lf-thread[data-attempt]')) return;
        const transform = getComputedStyle(card).transform;
        if (transform !== 'none') window.__recuedArrivals.push({
          animation: event.animationName, transform,
          words: card.querySelector('.lf-msg-body')?.textContent.trim(),
        });
      }, true);
    }""")
    held = []

    def hold(route):
        if route.request.post_data_json["kind"] == "comment":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold)
    try:
        write(field, "Keep this comment visible while it is sent.")
        page.keyboard.press("Enter")
        holding(page, held, 1, "the general comment")
        rendered(page)
        wait_for_probe(page, "pageSettled")
        scroll_settled(page, ".lf-threads")

        def reading_place():
            return page.locator(".lf-threads").evaluate("""list => {
              const card = list.querySelector(':scope > .lf-thread[data-attempt]');
              const box = card.getBoundingClientRect();
              return {scroll: list.scrollTop, top: box.top, bottom: box.bottom};
            }""")

        before = reading_place()
        # The send put the card away; the next thought is begun in it again.
        page_comment(page)
        write(field, "Keep the next thought separate.")
        rendered(page)
        wait_for_probe(page, "pageSettled")
        scroll_settled(page, ".lf-threads")
        expect(page.locator(".lf-thread[data-attempt] .lf-msg-body")).to_have_text(
            "Keep this comment visible while it is sent."
        )
        expect(field).to_have_js_property("value", "Keep the next thought separate.")
        assert reading_place() == before
        assert page.evaluate("window.__recuedArrivals") == [], (
            "a retained repaint restarted geometry motion after direct navigation "
            f"had canceled it: {page.evaluate('window.__recuedArrivals')!r}"
        )
    finally:
        for route in held:
            route.continue_()
        page.unroute("**/api/event", hold)
        expect(page.locator('.lf-threads [aria-busy="true"]')).to_have_count(0)
