"""End-to-end journey and durable draft tests."""

import base64
import itertools
import json
import re

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, append_command
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import service as service_model
from leaf.render_checks import one_frame, rendered, wait_until_ready
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_interaction import (
    ASK_PAGE,
    SEATED_QUESTION_PAGE,
    live_url,
)
from render_cases_layout import (
    glyph_action_face,
    in_threads_scrollport,
    token_colour,
)
from render_cases_navigation import (
    DRAFT_EDITED,
    DRAFT_TEXT,
    JOURNEY_V1,
    JOURNEY_V2,
    KEYS_PAGE,
    NOTED_PAGE,
    SENTENCE,
    SMOOTH_LONG_PAGE,
    _publish,
    compose,
    composer_quote,
    go_to_address,
    painted,
    pending_text,
    source_revision,
)
from render_harness import (
    FEATURE_GALLERY,
    LONG_PAGE,
    RELEASE_FOCUS,
    CutOff,
    _traffic,
    _until,
    compare_with,
    consume_browser_errors,
    draft_control,
    draft_key,
    draft_owner,
    example_media,
    expect_banner_control_offered,
    expect_comment_notes,
    held_stale,
    hold_pending_thread_presentation,
    hold_selection,
    holding,
    leaf_page,
    margin_entry,
    open_page,
    panel_settled,
    primed,
    refuse,
    resized,
    round_trip,
    scroll_settled,
    sending,
    shortcut_bar_text,
    stamp_page,
    stored_draft_settled,
    stored_draft_text,
    ticked,
    told,
    until_draft_settled,
    wait_for_revision,
    write,
)
from test_render_application_boundary import THREAD_MIRROR, THREAD_MIRROR_DECLARATION
from test_render_threads import hold_visible_thread_presentation


@pytest.mark.parametrize("bounded", [False, True])
def test_typing_in_a_visible_inline_reply_keeps_the_reading_position(
    browser, serve, bounded
):
    """Keeping a reply's controls visible does not reveal its already-scrolled-past turns."""
    content = """
<div style="height:900px"></div>
<lf-command id="hub" label="Tasks"><lf-task id="jobs" status="active" talk>
What should we do next?</lf-task></lf-command>
<div style="height:900px"></div>
"""
    if bounded:
        content = (
            '<div id="reader" data-bound="start" style="height:480px">'
            + content
            + "</div>"
        )
    url = serve(leaf_page("Reply reading", content))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "text": "A short question the reader has already passed.",
            "anchor": {"section": "jobs"},
        },
    )
    page = open_page(browser, url)
    thread = page.locator("#jobs .lf-page-thread")
    reply = thread.locator("leaf-text")
    reply.click()
    reply.evaluate(
        """(input, bounded) => {
      const scroller = bounded ? document.querySelector('#reader') : document.scrollingElement;
      const top = bounded ? scroller.getBoundingClientRect().top : 0;
      scroller.scrollBy(0, input.getBoundingClientRect().top - top - 55);
    }""",
        bounded,
    )
    scroll_settled(page)
    before = page.evaluate(
        """bounded => ({
      scroll: (bounded ? document.querySelector('#reader') : document.scrollingElement).scrollTop,
      reply: document.querySelector('#jobs leaf-text').getBoundingClientRect().top,
      thread: document.querySelector('#jobs .lf-page-thread').getBoundingClientRect().top,
    })""",
        bounded,
    )
    assert before["thread"] < (
        page.locator("#reader").bounding_box()["y"] if bounded else 0
    ), before
    expect(reply).to_be_focused()
    page.keyboard.type("A")
    round_trip(page)
    after = page.evaluate(
        """bounded => ({
      scroll: (bounded ? document.querySelector('#reader') : document.scrollingElement).scrollTop,
      reply: document.querySelector('#jobs leaf-text').getBoundingClientRect().top,
    })""",
        bounded,
    )
    assert after["scroll"] == pytest.approx(before["scroll"], abs=1), (before, after)
    assert after["reply"] == pytest.approx(before["reply"], abs=1), (before, after)


@pytest.mark.parametrize("installation", ["in-place", "fresh"])
def test_gallery_automatic_revision_keeps_the_empty_reply_focused(
    browser, serve, installation
):
    page = open_page(browser, live_url(serve(FEATURE_GALLERY)))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator('.lf-thread[data-id="72e031c5bf0d485ba9054628e09869d4"]')
    thread.locator(":scope > .lf-thread-summary").click()
    editor = thread.locator(".lf-thread-reply leaf-text")
    editor.click()
    expect(editor).to_be_focused()
    assert editor.evaluate("el => el.value") == ""
    birth = page.evaluate("performance.timeOrigin")
    revision = int(
        page.locator('meta[name="lf-revision"][data-lf-runtime]').get_attribute(
            "content"
        )
    )
    revised = FEATURE_GALLERY.read_text().replace(
        "To carry unfinished words to another item",
        "To move unfinished words to another item",
    )
    if installation == "fresh":
        revised = revised.replace(
            "</head>",
            '<script type="module">window.galleryRevision = 2;</script></head>',
        )
    stamp_page(serve.page_dir, revised, "Revise the gallery beside its empty reply")
    wait_for_revision(page, revision + 1)
    assert (page.evaluate("performance.timeOrigin") != birth) == (
        installation == "fresh"
    )
    expect(editor).to_be_focused()
    assert editor.evaluate("el => el.value") == ""


pytestmark = pytest.mark.nightly


def select_words(page, passage):
    """Triple-click a passage's words, which is not the same point as its box.

    Playwright aims at the element's centre, and a short paragraph in a wide column is
    mostly empty there. The response bar the user already opened on a neighbouring
    passage stands in that empty half — it is placed to keep its own target clear, not
    the page — so a gesture aimed at the centre lands on the field instead of on the
    words and never reaches the passage. The words are where a user aims, so the
    click goes to the start of the first line the passage draws."""
    locator = page.locator(passage)
    locator.scroll_into_view_if_needed()
    x, y = locator.evaluate(
        """element => {
          const range = element.ownerDocument.createRange();
          range.selectNodeContents(element);
          const [line] = range.getClientRects();
          const box = element.getBoundingClientRect();
          if (!line) return [box.width / 2, box.height / 2];
          return [
            line.left + Math.min(24, line.width / 2) - box.left,
            line.top + line.height / 2 - box.top,
          ];
        }"""
    )
    locator.click(click_count=3, position={"x": x, "y": y})


def choose_comment_target(page, selector):
    """Choose one visible element through the user's target-hint route."""
    page.locator(selector).scroll_into_view_if_needed()
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).not_to_have_count(0)
    code = page.evaluate(
        """selector => {
          const top = document.querySelector(selector).getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-picker-hint')]
            .sort((a, b) => Math.abs(a.getBoundingClientRect().top - top)
                          - Math.abs(b.getBoundingClientRect().top - top))[0]
            .dataset.lfHintCode;
        }""",
        selector,
    )
    page.keyboard.type(code)
    expect(page.locator(".lf-fab-input")).to_be_focused()


def test_clicking_a_visible_reply_preserves_the_thread_reading(browser, serve):
    """Pointer entry owns the caret, rather than revealing the whole containing card."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    thread = page.locator(".lf-thread[open]").first
    field = thread.locator("leaf-text")
    place = page.evaluate(
        """() => {
          const list = document.querySelector('.lf-threads');
          list.scrollTop = 70;
          return list.scrollTop;
        }"""
    )
    assert place == 70
    field.click()
    expect(field).to_be_focused()
    assert page.locator(".lf-threads").evaluate("el => el.scrollTop") == place


def test_clicking_a_shadow_widget_input_keeps_its_focus_and_thread_reading(
    browser, serve
):
    """A message's public widget keeps its native input across the thread's pointer-up."""
    url = serve(LONG_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Review the patch.",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "revision": 1,
            "text": "Filter the files in this patch.",
            "markup": """<lf-diff id="reply-patch" data-height="201"><pre>
diff --git a/reading.py b/reading.py
--- a/reading.py
+++ b/reading.py
@@ -1,2 +1,2 @@
 def reading():
-    return "before"
+    return "after"
</pre></lf-diff>""",
        },
    )
    for index in range(8):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"Another thread {index}.",
            },
        )
    page = open_page(browser, url)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    field = page.locator(".lf-thread[open] lf-diff .lf-diff-search")
    expect(field).to_be_visible()
    page.locator(".lf-threads").evaluate("list => list.scrollTop = 70")
    scroll_settled(page, ".lf-threads")
    assert field.evaluate(
        "field => field.getBoundingClientRect().top > "
        "field.getRootNode().host.closest('.lf-threads').getBoundingClientRect().top"
    ), "the shadow input must already be visible before the click"

    field.click()

    expect(field).to_be_focused()
    assert page.locator(".lf-threads").evaluate("list => list.scrollTop") == 70


@pytest.mark.watch_shifts
@pytest.mark.parametrize("box", ["general", "reply", "composer"])
def test_a_single_space_is_message_content_in_every_composer(browser, serve, box):
    """The shared field and both drawing-aware variants admit the smallest message.

    Each box sends from the one press the shared field dresses, and that press paints
    nothing of its own: at rest the accent glyph is the whole of what a user sees, and
    the disc behind it is a clear 28px that takes the accent tint under the pointer,
    which is why it stays the same size as the target around it grows.
    """
    page = open_page(browser, serve(LONG_PAGE, comments=box == "reply"))
    if box == "composer":
        select_words(page, "#p0")
        expect(page.locator(".lf-fab-input")).to_be_visible()
        page.keyboard.press("c")
        surface = page.locator(".lf-composer")
    else:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        surface = (
            page.locator(".lf-general")
            if box == "general"
            else page.locator(".lf-threads > .lf-thread").first
        )

    if box == "reply":
        surface.locator(".lf-thread-summary").click()
    field = surface.locator("leaf-text")
    send = surface.locator(".lf-compose-submit")
    write(field, " ")
    expect(send).to_have_attribute("aria-disabled", "false")
    face = glyph_action_face(send)
    assert face["press"] == "rgba(0, 0, 0, 0)", face
    assert face["glyph"] == token_colour(page, "--accent"), face
    assert face["disc"] == "rgba(0, 0, 0, 0)", face
    assert face["discWidth"] == "28px", face
    send.hover()
    hovered = glyph_action_face(send)
    assert hovered["press"] == "rgba(0, 0, 0, 0)", hovered
    assert hovered["disc"] == token_colour(page, "--accent-tint"), hovered
    assert hovered["discWidth"] == "28px", hovered
    with sending(page, f"the {box} message"):
        send.click()

    message = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] in {"comment", "reply"}
    ][-1]
    assert message["text"] == " "


# A storage fault stands in an init script, because it has to run ahead of the
# runtime's own storage listener and at the window listeners run in the order they
# were added, capture or not. That is before the page can say which key its draft is
# stored under, so the script compares against `window.lfDraftKey`, which
# `name_the_draft` sets once the page has loaded and nothing has been typed.
DEAF_TO_DRAFT_NEWS = """addEventListener('storage', event => {
  if (event.key === window.lfDraftKey) event.stopImmediatePropagation();
}, true);"""


def name_the_draft(page, ctx):
    """Point this page's storage fault at the draft at `ctx`, by the store's key."""
    page.evaluate("key => { window.lfDraftKey = key; }", draft_key(page, ctx))


def cancel_draft(page, draft_id="draft-ops"):
    """Cancel stands beside Save throughout an engaged draft edit."""
    draft_control(page, "cancel", draft_id).click()


def test_page_round_trip(browser, serve):
    """The loop the product is, driven through the real UI: select a passage and
    comment on it, drag a card to another column, rewrite a draft in place, then
    follow the next version and find the comment still anchored to its
    (relocated) passage and the draft still wearing the user's words. The
    final assertion is the event log — the trail Claude reads — down to the
    anchor's quote, the move's placement, and the edit's text."""
    page = open_page(browser, live_url(serve(JOURNEY_V1)))
    # Select the passage from the keyboard's path: a real Range, then the keyup
    # the runtime watches for keyboard selections. Comment explicitly enters its field.
    page.evaluate("""() => {
        const r = document.createRange();
        r.selectNodeContents(document.getElementById('intro'));
        getSelection().removeAllRanges();
        getSelection().addRange(r);
        document.body.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
    }""")
    page.wait_for_selector(
        ".lf-fab-input", state="visible"
    )  # the selection raised the button
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    page.wait_for_selector(".lf-composer", state="visible")
    write(page.locator(".lf-composer leaf-text"), "Is 0041 idempotent?")
    page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_selector(".lf-margin-thread")
    # The anchor pass painted the passage — a range in the highlight registry, not an
    # element, so there is no selector for it.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Put the new comment's card away before reaching for the board. A sent comment
    # leaves its thread standing in the page margin, and the board is a wide widget
    # whose columns run out into that same band, so the card lands over the column this
    # drag is aimed at and takes the pointer. A user sees the card and dismisses it;
    # a test that skipped the dismissal would be dragging under a sheet, which is a
    # scene about the margin rather than the seam below.
    page.keyboard.press("Escape")  # off the target the send landed on, and its card
    expect(page.locator(".lf-margin-thread")).to_be_hidden()
    # Drag the card between columns through the pointer path — the seam where
    # the vendored SortableJS meets the runtime, which is where drags break.
    grip = page.locator("#card-x .lf-grip").bounding_box()
    dest = page.locator("#col-done").bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        dest["x"] + dest["width"] / 2, dest["y"] + dest["height"] / 2, steps=15
    )
    page.mouse.up()
    page.wait_for_selector("#col-done #card-x")  # the drop reparented the card

    # Rewrite the draft through its own door: a press opens the text in place, Save
    # sends the whole new body. The text must have arrived without the source's
    # indentation.
    draft = page.locator("#draft-ops")
    assert draft.locator(".lf-draft-body").inner_text() == DRAFT_TEXT
    draft.locator(".lf-draft-body").dblclick()
    write(draft.locator("leaf-text"), DRAFT_EDITED)
    draft_control(page, "save", "draft-ops").click()
    page.wait_for_function(
        "t => document.querySelector('#draft-ops .lf-draft-body').textContent === t",
        arg=DRAFT_EDITED,
    )

    # Every gesture above must be in the log before v2's note lands, or the trail below
    # would interleave. The page posted them, so the page is what says they are all in:
    # polling the file for one of them would be a second reading of the same trip, and a
    # narrower one — it can only ever ask after the send it happens to name.
    d = serve.page_dir
    round_trip(page)

    # Claude ships v2 with the passage moved; the page follows on its next poll.
    stamp_page(d, JOURNEY_V2, "moved")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    assert "/versions/" not in page.url
    # The anchor pass runs at render: a mark now means the quote was re-found in
    # its new position; no mark within the wait means the anchor lost it.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert not page.evaluate(
        "document.querySelector('.lf-thread .lf-quote').classList.contains('detached')"
    ), "the passage moved and the comment lost it"
    # v2's markup carries the original draft text — Claude hasn't honored the
    # edit — so the user's words must arrive by replay, not visibly revert.
    page.wait_for_function(
        "t => document.querySelector('#draft-ops .lf-draft-body').textContent === t",
        arg=DRAFT_EDITED,
    )

    # The trail those gestures left, exactly — kinds, authorship (the server
    # stamps browser events `user`), the anchor, and the move's placement.
    events = events_model.read_events(d)
    assert [(e["kind"], e["author"], e["revision"]) for e in events] == [
        ("note", "agent", 1),
        ("comment", "user", 1),
        ("action", "user", 1),
        ("action", "user", 1),
        ("note", "agent", 2),
    ]
    # The board after the paragraph is module-rendered and therefore an opaque
    # passage cell. Context stops at that shared browser/file fence.
    assert events[1]["anchor"] == {
        "section": "intro",
        "quote": SENTENCE,
        "prefix": "Journey",
    }
    assert events[1]["text"] == "Is 0041 idempotent?"
    assert {k: events[2][k] for k in ("widget", "action", "detail")} == {
        "widget": "board",
        "action": "move",
        "detail": {"card": "card-x", "to": "col-done", "rank": "i"},
    }
    assert {k: events[3][k] for k in ("widget", "action", "detail")} == {
        "widget": "draft-ops",
        "action": "edit",
        "detail": {"text": DRAFT_EDITED},
    }


@pytest.mark.parametrize("section", ["draft-ops", None])
def test_a_comment_inside_a_widget_stays_out_of_what_the_widget_reads(
    browser, serve, section
):
    """The note that tells a screen reader a block carries a comment is chrome, and chrome
    inside a widget's own content would be chrome in the user's text: lf-draft seeds the
    editor they type into from its body div, so words left in there would arrive in the
    leaf-text and post with the edit. The note stands in the chrome, and the block the
    passage sits in, or the element the anchor names, names it as its details."""
    url = serve(JOURNEY_V1, anchored=[(section, "Run the migration before deploying.")])
    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    expect_comment_notes(page, "#draft-ops", 1)
    page.locator("#draft-ops .lf-draft-body").dblclick()
    assert (
        page.locator("#draft-ops leaf-text").evaluate("el => el.value") == DRAFT_TEXT
    ), "the user's editor opened on text the runtime had written into"


@pytest.mark.parametrize("section", ["draft-ops", None])
def test_a_reaction_inside_a_widget_keeps_its_authored_seat(browser, serve, section):
    """A passage's generated body is not the owner of the reaction's margin control."""
    url = serve(JOURNEY_V1)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "keep",
            "anchor": {
                **({"section": section} if section else {}),
                "quote": "Run the migration before deploying.",
            },
        },
    )
    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-react')?.size ?? 0) > 0")
    expect(
        page.locator(
            '[data-lf-margin-for="draft-ops"] '
            '[data-lf-margin-entry-owner="standing-reactions"]'
            '[data-lf-margin-entry-key^="reaction:"]:visible'
        )
    ).to_have_count(1)
    page.locator("#draft-ops .lf-draft-body").dblclick()
    assert page.locator("#draft-ops leaf-text").evaluate("el => el.value") == DRAFT_TEXT


def test_double_clicking_a_draft_leaves_every_word_where_it_was(browser, serve):
    """Plain words retain their geometry and native double-click selection on edit.

    The frame's inset focus paint changes without reaching outside the reading box,
    and print keeps the saved body while dropping the shared editor."""
    page = open_page(browser, serve(JOURNEY_V1))
    metrics = """(sel) => {
      const el = document.querySelector('#draft-ops ' + sel), s = getComputedStyle(el);
      const b = el.getBoundingClientRect();
      return [b.x + parseFloat(s.paddingLeft) + parseFloat(s.borderLeftWidth),
              b.y + parseFloat(s.paddingTop) + parseFloat(s.borderTopWidth), b.width, b.height];
    }"""
    read = page.evaluate(metrics, ".lf-draft-body")
    host = page.locator("#draft-ops").bounding_box()
    # A 4px band above the box, and the box's own top-left corner. The band is where
    # the answer to "did the frame move" lives and no measurement of geometry can
    # reach it: an outset ring is paint, so every rect stayed exactly as asserted
    # below while the frame the user sees grew 2px on every side, corners
    # rounding wider to match. Bytes, not pixels — the same encoder over the same
    # content gives the same file, so identical files are identical paint.
    band = {
        "x": host["x"] - 4,
        "y": host["y"] - 4,
        "width": host["width"] + 8,
        "height": 4,
    }
    inside = {"x": host["x"], "y": host["y"], "width": 40, "height": 40}
    outside_before = page.screenshot(clip=band)
    inside_before = page.screenshot(clip=inside)

    # Aimed at where the browser actually drew the word, not at an offset from the
    # box's edge. A pixel count is a fact about one font: 60px into this line was
    # "migration" while the theme set drafts in 16px system-ui, and lands in "the"
    # now that it sets them in 17px Charter — so the test read as "the editor opens
    # on the wrong word" when nothing about the gesture had changed.
    spot = page.evaluate(
        """(word) => {
            const body = document.querySelector('#draft-ops .lf-draft-body');
            const node = document.createTreeWalker(body, NodeFilter.SHOW_TEXT).nextNode();
            const at = node.data.indexOf(word);
            const r = document.createRange();
            r.setStart(node, at); r.setEnd(node, at + word.length);
            const b = r.getBoundingClientRect();
            return [b.x + b.width / 2, b.y + b.height / 2];
        }""",
        "migration",
    )
    page.mouse.dblclick(*spot)
    editor = page.locator("#draft-ops leaf-text")
    expect(editor).to_be_focused()
    pencil = draft_control(page, "edit", "draft-ops")
    assert page.screenshot(clip=band) == outside_before, (
        "opening the editor painted outside the box the draft already occupied"
    )
    assert page.screenshot(clip=inside) != inside_before, (
        "the open editor is indistinguishable from the read view at the box's edge"
    )
    assert page.evaluate(metrics, "leaf-text") == read, (
        "the editor's text sits somewhere the read view's text did not"
    )
    assert page.locator("#draft-ops").bounding_box() == host, (
        "the draft changed shape under the pointer when the editor opened"
    )
    assert (
        page.evaluate(
            "() => getSelection().rangeCount > 0 && "
            "getSelection().containsNode(document.querySelector('#draft-ops .lf-draft-body'), true)"
        )
        is False
    ), "the gesture left the page's own words selected under the open editor"
    selected = page.evaluate(
        "() => { const t = document.querySelector('#draft-ops leaf-text');"
        "        return t.value.slice(t.selectionStart, t.selectionEnd); }"
    )
    assert selected == "migration", (
        f"the box opened on {selected!r} rather than the word clicked"
    )

    # Closing states both properties in reverse, and the focus half is a question
    # only because the ✎ is CSS-hidden for as long as the editor is there: #close
    # reaches for it the instant the editor goes, so a style that hadn't caught up
    # would drop a keyboard user back at the top of the page.
    page.keyboard.press("Escape")
    expect(pencil).to_be_focused()
    expect(pencil).to_have_attribute("aria-expanded", "false")
    assert page.locator("#draft-ops").bounding_box() == host, (
        "the draft came back from an edit a different shape than it went in"
    )

    # Reopened through the other door, because print is where the box has to be
    # gone and its words still there — and print emulation blurs the leaf-text it
    # hides, so an editor opened before this point is no longer one Escape closes.
    draft_control(page, "edit", "draft-ops").click()
    expect(page.locator("#draft-ops leaf-text")).to_be_visible()
    page.emulate_media(media="print")
    assert page.locator("#draft-ops").inner_text() == DRAFT_TEXT, (
        "the printed page lost the draft's words to a box paper hasn't got"
    )
    page.emulate_media(media="screen")


@pytest.mark.parametrize("in_pane", [False, True], ids=["document", "pane"])
@pytest.mark.parametrize("formatted", [False, True], ids=["plain", "markdown"])
def test_opening_a_visible_line_in_a_long_draft_preserves_the_reading_position(
    browser, serve, in_pane, formatted
):
    """Editing a visible word keeps it there even when the draft exceeds the window."""
    words = (
        "The **release note** remains `editable`."
        if formatted
        else "The release note remains editable."
    )
    text = "\n".join(f"Line {i}: {words}" for i in range(60))
    draft = f'<lf-draft id="long-draft"><pre>{text}</pre></lf-draft>'
    body = (
        "<header><h1>Release notes</h1></header>"
        f'<lf-pane id="reading" label="Notes">{draft}</lf-pane>'
        if in_pane
        else f"<h1>Release notes</h1>{draft}<p>Following words.</p>"
    )
    page = open_page(
        browser,
        serve(
            leaf_page("Long draft", body, layout="workspace" if in_pane else "column")
        ),
    )
    resized(page, 800, 900)
    page.locator("#long-draft").evaluate(
        """el => {
          const box = el.closest('lf-pane') ? el : document.scrollingElement;
          box.scrollTop = 600;
        }"""
    )
    scroll_settled(page)
    point = page.locator("#long-draft .lf-draft-body").evaluate(
        """el => {
          const node = el.firstChild, word = 'Line 30:';
          const at = node.data.indexOf(word), range = document.createRange();
          range.setStart(node, at + 3); range.setEnd(node, at + 4);
          const b = range.getBoundingClientRect();
          return [b.x + b.width / 2, b.y + b.height / 2];
        }"""
    )
    assert 60 < point[1] < 850, point
    reading = """() => ({
      page: document.scrollingElement.scrollTop,
      draft: document.querySelector('#long-draft').scrollTop,
      top: document.querySelector('#long-draft').getBoundingClientRect().top
    })"""
    before = page.evaluate(reading)
    page.mouse.click(*point)
    expect(page.locator("#long-draft leaf-text")).to_be_focused()
    assert page.evaluate(reading) == before
    editor = page.locator("#long-draft leaf-text")
    offset = editor.evaluate("el => el.selectionStart")
    assert text.index("Line 30:") <= offset <= text.index("Line 30:") + 8
    expect(editor).to_have_js_property("value", text)


@pytest.mark.parametrize(
    "viewport", [(1440, 900), (390, 844)], ids=["desktop", "phone"]
)
def test_a_draft_uses_shared_editing_and_saves_exact_markdown_source(
    browser, serve, viewport
):
    """Markdown remains source through click-to-edit, undo, Cancel and Save."""
    text = (
        "A **bold invitation**, `literal code`, and [a link](https://example.com). " * 3
    ).strip()
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Draft source",
                f'<h1>Draft source</h1><lf-draft id="source"><pre>{text}</pre></lf-draft>'
                '<lf-sample id="quoted"><lf-draft id="exhibit"><pre>Read-only source.</pre></lf-draft></lf-sample>',
            )
        ),
    )
    resized(page, *viewport)
    draft = page.locator("#source")
    point = draft.locator(".lf-draft-body").evaluate("""body => {
      const node=body.firstChild, at=node.data.indexOf('literal code');
      const r=new Range();r.setStart(node,at+3);r.setEnd(node,at+4);
      const b=r.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2,at];
    }""")
    page.mouse.click(point[0], point[1])
    editor = draft.locator("leaf-text")
    expect(editor).to_be_focused()
    expect(editor).to_have_attribute("aria-label", "Edit source")
    caret = editor.evaluate("el=>el.selectionStart")
    assert point[2] <= caret <= point[2] + len("literal code")
    page.keyboard.insert_text("changed ")
    expect(editor).to_have_js_property(
        "value", text[:caret] + "changed " + text[caret:]
    )
    page.keyboard.press("ControlOrMeta+z")
    expect(editor).to_have_js_property("value", text)
    write(editor, "Discard **this**.")
    draft_control(page, "cancel", "source").click()
    expect(draft.locator(".lf-draft-body")).to_have_text(text.strip())
    draft_control(page, "edit", "source").click()
    expect(editor).to_have_js_property("value", text)
    saved = "Keep **this** and `that` exactly.\nA second line."
    write(editor, saved)
    draft_control(page, "save", "source").click()
    round_trip(page)
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text(saved)
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert [event["detail"]["text"] for event in edits] == [saved]
    page.locator("#exhibit .lf-draft-body").click()
    expect(page.locator("#exhibit leaf-text")).to_have_count(0)
    expect(page.locator("#exhibit .lf-draft-body")).to_have_text("Read-only source.")


def test_a_draft_forwards_edit_save_and_cancel_without_consuming_native_digits(
    browser, serve
):
    """Ask aliases name the current draft action while its shared editor owns typing."""
    original = "Keep **this** source editable."
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Draft contextual commands",
                '<h1>Release note</h1><lf-ask id="note-decision">'
                "<h2>How should the note read?</h2>"
                f'<lf-draft id="note" needed><pre>{original}</pre></lf-draft></lf-ask>',
            )
        ),
    )
    question = page.locator("#note-decision")
    editor = page.locator("#note leaf-text")
    hints = page.locator(".lf-command-binding-badges > .lf-command-binding-badge")

    def return_to_question():
        question.evaluate(
            """async element => {
              const {focusDestination} = await window.__lfRuntimeImport('/runtime/widget-api.js');
              focusDestination(element);
            }"""
        )
        expect(question).to_be_focused()

    page.keyboard.press("a")
    expect(question).to_be_focused()
    expect(draft_control(page, "edit", "note")).to_have_attribute(
        "aria-keyshortcuts", "1"
    )
    expect(hints).to_have_text(["1"])
    page.keyboard.press("1")
    expect(editor).to_be_focused()
    write(editor, "Keep **these** digits: ")
    page.keyboard.type("123")
    saved = "Keep **these** digits: 123"
    expect(editor).to_have_js_property("value", saved)
    expect(editor).to_be_focused()
    rendered(page)
    assert "1" not in hints.all_text_contents()
    assert "2" not in hints.all_text_contents()

    return_to_question()
    expect(hints).to_have_text(["1", "2"])
    for action, key in [("save", "1"), ("cancel", "2")]:
        assert (
            key
            in draft_control(page, action, "note")
            .get_attribute("aria-keyshortcuts")
            .split()
        )
    page.keyboard.press("?")
    page.keyboard.press("?")
    for command_id, title in [("draft.save", "Save"), ("draft.cancel", "Cancel")]:
        command = page.locator(
            f'.lf-command-reference-command[data-lf-command="{command_id}"]'
        )
        expect(command).to_have_text(title)
        expect(command).to_have_attribute("data-lf-available", "true")
    page.keyboard.press("Escape")
    expect(question).to_be_focused()
    page.keyboard.press("1")
    round_trip(page)
    expect(editor).to_have_count(0)
    expect(page.locator("#note .lf-draft-body")).to_have_text(saved)

    # The answered Ask remains an association while the source offers another edit.
    return_to_question()
    page.keyboard.press("1")
    expect(editor).to_be_focused()
    write(editor, "Discard these later words.")
    return_to_question()
    page.keyboard.press("2")
    expect(editor).to_have_count(0)
    expect(page.locator("#note .lf-draft-body")).to_have_text(saved)
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert [event["detail"]["text"] for event in edits] == [saved]


def test_a_foreign_edit_waits_for_a_live_draft_and_replays_in_order(browser, serve):
    """Replay never replaces words while the user is typing them.

    Deferring one edit must also hold later edits for that draft: otherwise the
    later absolute value lands first and the deferred earlier value overwrites it
    when the box closes. An unrelated board move proves the poll saw the same
    batch while the editor was open, without making the test depend on time.
    """
    page = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    editor = draft.locator("leaf-text")
    write(editor, "Local unsent words.")

    d = serve.page_dir
    for text in ("Foreign first edit.", "Foreign committed words."):
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "draft-ops",
                "action": "edit",
                "detail": {"text": text},
            },
        )
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "board",
            "action": "move",
            "detail": {"card": "card-x", "to": "col-done", "rank": "0i"},
        },
    )

    told(page)
    expect(page.locator("#col-done #card-x")).to_have_count(1)
    expect(editor).to_have_js_property("value", "Local unsent words.")
    expect(draft.locator(".lf-draft-history > summary")).to_have_text(
        "Changes · 0 edits"
    )

    page.route("**/api/state*", refuse)
    page.keyboard.press("Escape")
    ticked(page)
    expect(draft.locator(".lf-draft-body")).to_have_text("Foreign committed words.")
    expect(draft.locator(".lf-draft-history > summary")).to_have_text(
        "Changes · 2 edits"
    )
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "3")


def test_an_empty_draft_survives_reload_and_blocks_a_version_switch(browser, serve):
    """Empty text is a real replacement, not the absence of a saved draft. Deleting
    the whole body must hold a live editor on its version, survive reload, and arrive
    in the log as an ordinary absolute edit."""
    url = serve(JOURNEY_V1)
    page = open_page(browser, live_url(url))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    write(draft.locator("leaf-text"), "")
    assert stored_draft_text(page, "edit:draft-ops") == ""

    d = serve.page_dir
    stamp_page(d, JOURNEY_V2, "v2")
    told(page)
    expect_banner_control_offered(page.locator(".lf-latest-chip"))
    assert "/versions/" not in page.url

    page.reload(wait_until="load")
    wait_until_ready(page)
    expect(draft.locator("leaf-text")).to_be_visible()
    expect(draft.locator("leaf-text")).to_have_js_property("value", "")

    page.evaluate(
        """() => {
          window.lfActualFetch = window.fetch.bind(window);
          window.lfFailDraft = true;
          window.fetch = (input, init) => {
            const event = String(input).endsWith('/api/event') && init?.body
              ? JSON.parse(init.body) : null;
            if (window.lfFailDraft &&
                event?.kind === 'action' && event.action === 'edit')
              return Promise.resolve(new Response('offline', {status: 503}));
            return window.lfActualFetch(input, init);
          };
        }"""
    )
    draft_control(page, "save", "draft-ops").click()
    # A 503 cannot say whether the server appended before its answer was lost. Keep
    # the one saved gesture visibly pending and its draft recoverable; reopening the
    # editor would invite a second gesture while this attempt is still retrying.
    expect(draft).to_have_attribute("aria-busy", "true")
    expect(draft.locator("leaf-text")).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text("")
    assert stored_draft_text(page, "edit:draft-ops") == ""

    page.evaluate("window.lfFailDraft = false")
    wait_for_revision(page, 2)
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_text("")
    until_draft_settled(page, "edit:draft-ops")
    events = [e for e in events_model.read_events(d) if e["kind"] == "action"]
    assert events[-1]["action"] == "edit"
    assert events[-1]["detail"] == {"text": ""}


def test_a_draft_send_owns_the_editor_until_its_response(browser, serve):
    """A second gesture cannot overtake an earlier request or let that request clear
    newer unsent text. Hold the first POST in the browser: while it owns the draft,
    every edit door stays closed and the exact body remains recoverable."""
    page = open_page(browser, serve(JOURNEY_V1))
    page.evaluate(
        """() => {
          const actualFetch = window.fetch.bind(window);
          let held = true;
          window.fetch = (input, init) => {
            const event = String(input).endsWith('/api/event') && init?.body
              ? JSON.parse(init.body) : null;
            if (held && event?.kind === 'action' && event.action === 'edit') {
              return new Promise((resolve, reject) => {
                window.releaseDraftSend = () => {
                  held = false;
                  actualFetch(input, init).then(resolve, reject);
                };
              });
            }
            return actualFetch(input, init);
          };
        }"""
    )
    draft = page.locator("#draft-ops")
    sent = "The first save still owns this body."
    draft.locator(".lf-draft-body").dblclick()
    write(draft.locator("leaf-text"), sent)
    draft_control(page, "save", "draft-ops").click()
    expect(draft).to_have_attribute("aria-busy", "true")
    assert stored_draft_text(page, "edit:draft-ops") == sent

    expect(draft_control(page, "edit", "draft-ops")).to_be_disabled()
    # The projection owns a native disabled button, so a forced DOM click is refused
    # before the contributor's activation capability can run.
    draft_control(page, "edit", "draft-ops").evaluate("button => button.click()")
    expect(draft.locator("leaf-text")).to_have_count(0)

    page.evaluate("window.releaseDraftSend()")
    page.wait_for_function(
        """key => !document.getElementById('draft-ops').hasAttribute('aria-busy')
          && JSON.parse(localStorage.getItem(key))?.settled === true""",
        arg=draft_key(page, "edit:draft-ops"),
    )
    events = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["text"] for event in events] == [sent]

    draft_control(page, "edit", "draft-ops").click()
    expect(draft.locator("leaf-text")).to_be_focused()
    page.keyboard.press("Escape")


def test_a_draft_wait_only_paints_after_the_shared_busy_delay(browser, serve):
    """The layer leaves a short send unpainted, then makes a long wait visible."""
    page = open_page(browser, serve(JOURNEY_V1))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    write(draft.locator("leaf-text"), "A send held long enough to need progress paint.")

    # Sample on the CSS animation's own clock rather than racing wall time across a
    # Playwright round trip, from just before the user's press on Save until well past
    # the delay. The host is the surface without a margin entry that owns aria-busy.
    page.evaluate(
        """() => {
          const el = document.getElementById('draft-ops');
          const out = [];
          let stop = false;
          const tick = () => {
            const painted = Number(getComputedStyle(el).opacity);
            const busy = el.getAnimations().find(
              animation => animation.animationName === 'lf-runtime-4f3c2a8d-working'
            );
            out.push([
              busy ? Number(busy.currentTime) : null,
              busy ? busy.playState : null,
              painted,
            ]);
            if (!stop) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
          window.__lfBusyFrames = new Promise(resolve => setTimeout(() => {
            stop = true;
            resolve(out);
          }, 700));
        }"""
    )
    page.locator(
        '[data-lf-margin-for="draft-ops"] '
        + margin_entry(draft_owner("draft-ops"), "save")
    ).click()
    frames = page.evaluate("() => window.__lfBusyFrames")
    holding(page, held, 1, "the draft edit")

    early = [
        opacity
        for elapsed, _state, opacity in frames
        if elapsed is None or elapsed < 150
    ]
    late = [opacity for _elapsed, state, opacity in frames if state == "finished"]
    assert early and set(early) == {1}, f"a short draft wait painted busy: {early}"
    assert late and set(late) == {0.5}, f"a long draft wait stayed unpainted: {late}"
    expect(draft).to_have_attribute("aria-busy", "true")

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(draft).not_to_have_attribute("aria-busy", "true")


def test_a_refused_draft_keeps_text_and_offers_retry_without_a_details_pane(
    browser, serve
):
    """Failure is an editable state, with Retry and Cancel at the same target."""
    page = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    editor = draft.locator("leaf-text")
    write(editor, "Keep these unsent words.")
    page.route(
        "**/api/event",
        lambda route: route.fulfill(
            status=400,
            json={"ok": False, "final": True, "error": "refused before append"},
        ),
    )
    draft_control(page, "save", "draft-ops").click()
    item = page.locator('[data-lf-margin-for="draft-ops"]')
    expect(item.locator(".lf-margin-receipt")).to_have_text("Failed")
    expect(item).to_have_attribute("data-lf-state", "failed")
    expect(editor).to_have_js_property("value", "Keep these unsent words.")
    expect(item.get_by_role("button", name="Retry", exact=True)).to_be_visible()
    expect(item.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    expect(item.locator(".lf-margin-more")).to_be_hidden()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    write(editor, "Keep the revised unsent words.")
    expect(item.locator(".lf-margin-receipt")).to_have_count(0)
    expect(item).to_have_attribute("data-lf-state", "engaged")
    item.get_by_role("button", name="Save", exact=True).click()
    expect(item.locator(".lf-margin-receipt")).to_have_text("Failed")
    page.unroute("**/api/event")
    item.get_by_role("button", name="Retry", exact=True).click()
    round_trip(page)
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text(
        "Keep the revised unsent words."
    )
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert [event["detail"] for event in edits] == [
        {"text": "Keep the revised unsent words."}
    ]
    consume_browser_errors(page, "400")


def test_one_draft_edit_is_what_every_tab_of_the_page_shows(browser, serve, one_user):
    """An edit is one set of words wherever the user typed them, and the two halves
    of that fail in opposite directions. A keystroke has to reach the box the other tab
    has open, or two tabs hold two halves of one thought and whichever is closed takes
    its half with it. A settlement has to empty the other box, rather than leave it
    holding words the log already has — standing over a body replay is about to paint.

    A closed box stays closed for a keystroke made elsewhere: news arriving has no
    gesture behind it, and the words are there at the next opening either way."""
    url = serve(JOURNEY_V1)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first_draft = first.locator("#draft-ops")
    second_draft = second.locator("#draft-ops")

    edited = "Run the migration after the backup."
    first_draft.locator(".lf-draft-body").dblclick()
    second_draft.locator(".lf-draft-body").dblclick()
    write(first_draft.locator("leaf-text"), edited)
    expect(second_draft.locator("leaf-text")).to_have_js_property("value", edited)

    draft_control(first, "save", "draft-ops").click()
    round_trip(first)
    expect(second_draft.locator("leaf-text")).to_have_count(0)
    # The body the other tab is left looking at is the log's, which is what closing the
    # box in front of it was for: renderState defers while an editor stands open.
    expect(second_draft.locator(".lf-draft-body")).to_have_text(edited)
    assert stored_draft_settled(second, "edit:draft-ops")

    # A second edit, with only the first tab's box open. The store's value arriving is
    # the fact to consume before reading an absence: the storage event carrying it is
    # the same task that would have opened a box here.
    discarded = "This tab discards these words."
    first_draft.locator(".lf-draft-body").dblclick()
    write(first_draft.locator("leaf-text"), discarded)
    second.wait_for_function(
        """([key, text]) => JSON.parse(localStorage.getItem(key))?.text === text""",
        arg=[draft_key(second, "edit:draft-ops"), discarded],
    )
    assert second_draft.locator("leaf-text").count() == 0, (
        "the second tab opened an editor for a keystroke nobody made there"
    )
    cancel_draft(first)
    until_draft_settled(second, "edit:draft-ops")
    second_draft.locator(".lf-draft-body").dblclick()
    expect(second_draft.locator("leaf-text")).to_have_js_property("value", edited)

    events = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["text"] for event in events] == [edited]


def test_one_shared_draft_edit_appends_one_action_across_tabs(browser, serve, one_user):
    """The widget's local busy flag is not the shared edit's ownership boundary."""
    url = serve(JOURNEY_V1)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first_draft = first.locator("#draft-ops")
    second_draft = second.locator("#draft-ops")
    first_draft.locator(".lf-draft-body").dblclick()
    second_draft.locator(".lf-draft-body").dblclick()
    text = "One absolute edit from the shared draft generation."
    write(first_draft.locator("leaf-text"), text)
    expect(second_draft.locator("leaf-text")).to_have_js_property("value", text)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    draft_control(first, "save", "draft-ops").click()
    holding(first, held, 1, "the first draft edit")
    draft_control(second, "save", "draft-ops").click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action" and event["action"] == "edit"
    ]
    assert [event["detail"]["text"] for event in edits] == [text]
    assert edits[0]["attempt"]
    assert _traffic(first).sends == _traffic(second).sends == 1
    expect(second_draft.locator("leaf-text")).to_have_count(0)
    assert stored_draft_settled(second, "edit:draft-ops")


def test_one_shared_added_option_has_one_action_payload_across_tabs(
    browser, serve, one_user
):
    """A draft attempt owns its actions' details as well as its visible words.

    The two views deliberately start from different projected selections. Both can
    submit the one shared add-option generation: its `add` is one event by attempt, and
    the pick behind it comes from the generation's recorded choice rather than from
    each tab's own selection, so the two tabs send one pick.
    """
    url = serve(ASK_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)

    # Model a tab whose latest projection has not reached its neighbour yet. The draft
    # is born here, so this selection is the state the generation records.
    first.locator("#job-mounts").evaluate("el => el.setAttribute('chosen', '')")
    text = "Use a heated camera sleeve"
    write(first.locator("#jobs > .lf-another leaf-text"), text)
    expect(second.locator("#jobs > .lf-another leaf-text")).to_have_js_property(
        "value", text
    )

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first.locator("#jobs > .lf-another").get_by_role(
        "button", name="Add and select option", exact=True
    ).click()
    holding(first, held, 1, "the first added option")

    second.locator("#jobs > .lf-another").get_by_role(
        "button", name="Add and select option", exact=True
    ).click()
    round_trip(second)
    held_detail = held[0].request.post_data_json["detail"]
    # The pick queues behind the held `add`, so the route comes off before the `add`
    # goes on and nothing sent after it is caught.
    first.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(first)
    # The forged selection is not the state's, so the `add` renders it away and the pick
    # that follows in the same task puts it back.
    consume_browser_errors(first, "unchanged write: chosen on lf-option#job-mounts")

    moves = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("kind") == "action" and event.get("widget") == "jobs"
    ]
    adds = [event["detail"] for event in moves if event["action"] == "add"]
    assert adds == [held_detail]
    picks = {
        tuple(event["detail"]["options"])
        for event in moves
        if event["action"] == "choose"
    }
    assert picks == {("job-mounts", held_detail["option"])}
    # Each tab sent the generation's `add` and its pick once.
    assert _traffic(first).sends == _traffic(second).sends == 2


def test_a_comment_being_typed_reaches_the_pages_other_tabs(browser, serve, one_user):
    """The general box and a thread's reply box are each one draft with a view in every
    tab. Both directions of the loop are here: words typed in one tab arrive in the
    other's box live, and a send there empties it — the distinction the store's own
    vocabulary carries, an emptied box being a value and a settled draft a tombstone.
    The Send button is read with the value, since a mirrored draft the box cannot send
    is words arriving dead."""
    url = serve(LONG_PAGE, comments=1)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    for page in (first, second):
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)

    typed = "The page is missing the migration step."
    write(first.locator(".lf-general leaf-text"), typed)
    expect(second.locator(".lf-general leaf-text")).to_have_js_property("value", typed)
    expect(second.locator(".lf-general button")).to_have_attribute(
        "aria-disabled", "false"
    )

    # The tab doing the typing is the one tab the store says nothing to, which is what
    # leaves the caret where the user put it: writing .value on a focused box sends
    # the caret to the end of it, and a user typing into the middle of a sentence
    # would watch every keystroke jump there.
    first.locator(".lf-general leaf-text").click()
    first.keyboard.press("Home")
    first.keyboard.type("Late: ")
    expect(second.locator(".lf-general leaf-text")).to_have_js_property(
        "value", "Late: " + typed
    )
    assert (
        first.locator(".lf-general leaf-text").evaluate("ta => ta.selectionStart") == 6
    ), "the caret moved in the tab that did the typing"
    typed = "Late: " + typed

    reply = "Typed into the reply box of the other tab."
    second.locator(".lf-thread-summary").first.click()
    write(second.locator(".lf-thread leaf-text").first, reply)
    expect(first.locator(".lf-thread leaf-text").first).to_have_js_property(
        "value", reply
    )
    second.locator(".lf-thread").first.get_by_role(
        "button", name="Send", exact=True
    ).click()
    round_trip(second)
    expect(first.locator(".lf-thread leaf-text").first).to_have_js_property("value", "")

    first.locator(".lf-general button").click()
    round_trip(first)
    expect(second.locator(".lf-general leaf-text")).to_have_js_property("value", "")
    expect(second.locator(".lf-general button")).to_have_attribute(
        "aria-disabled", "true"
    )
    said = [e["text"] for e in events_model.read_events(serve.page_dir) if "text" in e]
    assert said[-2:] == [reply, typed]


def test_a_general_comment_appends_one_event_across_tabs(browser, serve, one_user):
    """Both tabs may POST the shared generation; its attempt appends it once."""
    url = serve(LONG_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    for page in (first, second):
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
    raw = "One general comment, however many tabs show its draft."
    write(first.locator(".lf-general leaf-text"), raw)
    expect(second.locator(".lf-general leaf-text")).to_have_js_property("value", raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first.locator(".lf-general button").click()
    holding(first, held, 1, "the first general send")
    second.locator(".lf-general button").click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]
    assert roots[0]["attempt"]
    assert _traffic(first).sends == _traffic(second).sends == 1


def test_a_held_general_send_preserves_a_newer_exact_draft(browser, serve):
    """An earlier response settles only the general generation it posted."""
    page = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    box = page.locator(".lf-general leaf-text")
    old = "The general comment already in flight."
    newer = "  The newer general thought keeps its spaces.  "
    write(box, old)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator(".lf-general button").click()
    holding(page, held, 1, "the older general send")
    write(box, newer)

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(box).to_have_js_property("value", newer)
    assert stored_draft_text(page, "general") == newer
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old]


def test_a_refused_selection_comment_leaves_the_words_on_their_passage(
    held_events, serve
):
    """The composer goes down with the send, so a refusal has to put the words back in
    the store rather than in whatever box was on screen — the one they were typed in has
    gone with the thread they went to."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    words = "The selection comment the server will refuse."
    compose(page, "#p3", words)
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the selection comment")

    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator('leaf-text[name="reply"]:focus')).to_be_visible()
    page.keyboard.press("ArrowRight")  # caret movement is not a later composition
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(page.locator(".lf-notice")).to_contain_text("Couldn't send")

    # Their passage still holds their draft, so opening it again finds the words.
    page.locator("h1").click()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(".lf-composer leaf-text")).to_be_focused()
    expect(page.locator(".lf-composer leaf-text")).to_have_js_property("value", words)
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == words
    ]
    consume_browser_errors(page, "400")


def test_a_reply_behind_a_refused_parent_is_withdrawn_rather_than_sent(
    held_events, serve
):
    """A gesture against a message the log refused has nothing left to be about. It
    never reaches the wire under a name only this page used, and its own words go back
    to the box they were written in."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    write(page.locator(".lf-general leaf-text"), "The parent the server will refuse.")
    page.locator(".lf-general button").click()
    holding(page, held, 1, "the parent send")

    card = page.locator('.lf-thread[data-id^="pending:"]')
    expect(card).to_have_count(1)
    words = "A reply behind a parent that never lands."
    write(card.locator("leaf-text").first, words)
    card.get_by_role("button", name="Send", exact=True).click()

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    round_trip(page)
    expect(card).to_have_count(0)
    assert not [
        route for route in held if "pending:" in (route.request.post_data or "")
    ], "a gesture reached the wire naming a thread the log never took"
    # The reply's draft keys by its thread's stable name, which is the parent's attempt.
    assert stored_draft_text(page, f"reply:{attempt}") == words
    consume_browser_errors(page, "400")


def test_a_refused_comment_takes_its_message_back_and_returns_the_words(
    held_events, serve
):
    """A refusal leaves nothing standing and the words back where they were written."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    box = page.locator(".lf-general leaf-text")
    words = "The comment the server will refuse."
    write(box, words)
    before = page.locator(".lf-threads > .lf-thread").count()
    page.locator(".lf-general button").click()
    holding(page, held, 1, "the general send")
    pending = page.locator('.lf-thread[data-id^="pending:"]')
    expect(pending).to_have_count(1)
    # The card is a native disclosure, so its title is the stop the user stands on.
    title = pending.locator(":scope > .lf-thread-summary")
    title.focus()
    expect(title).to_be_focused()

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(page.locator('.lf-thread[data-id^="pending:"]')).to_have_count(0)
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(before)
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(box).to_have_js_property("value", words)
    expect(page.locator(".lf-notice")).to_contain_text("Couldn't send")
    assert stored_draft_text(page, "general") == words
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == words
    ]
    consume_browser_errors(page, "400")


@pytest.mark.parametrize("box", ["seat", "general"])
def test_every_message_send_says_so_to_a_user_listening(held_events, serve, box):
    """A send whose result the user cannot see still reaches them.

    The message standing in the thread is the whole acknowledgement for a user
    looking at it, which is why no box writes a success notice for it. But neither the
    seat nor the panel's list is a live region, so for a user listening to the page
    that send would pass in silence. `post` says it once, where a gesture is first known
    to be a message, which is what covers every box that sends one.
    """
    browser, held = held_events
    page = open_page(browser, serve(SEATED_QUESTION_PAGE))
    live = page.locator(".lf-live")
    if box == "seat":
        seat = page.locator("#jobs > .lf-thread-seat > .lf-say")
        field = seat.locator("leaf-text")
        press = seat.get_by_role("button", name="Send", exact=True)
    else:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        field = page.locator(".lf-general leaf-text")
        press = page.locator(".lf-general").get_by_role(
            "button", name="Send", exact=True
        )
    write(field, "A remark whose arrival nothing else will say.")
    press.click()
    # Held: the gesture is the only thing that can have written the region, and the
    # words are said before the log has answered rather than because it did.
    holding(page, held, 1, "the send")
    expect(live).to_have_text("Message sent")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)


def test_a_first_answer_leaves_a_later_sends_words_masked(held_events, serve):
    """One box, two sends: answering the first must not hand back the second's words.

    A send empties the box it was written in and masks that generation, so this
    document stops showing words it is now showing in the thread. The answer lifts that
    mask — and lifting whichever mask happens to be standing, rather than the one this
    send put there, lifts a later send's: words the user is already watching as a
    pending reply go back on offer while that reply is still in flight. The outbox
    delivers in order, so the first answer always lands while the second send is
    unanswered. That makes the window ordinary rather than rare.
    """
    browser, held = held_events
    url = serve(SEATED_QUESTION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job comes first?",
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread")
    thread.locator(".lf-thread-summary").click()
    reply = thread.locator("leaf-text")
    send = thread.get_by_role("button", name="Send", exact=True)

    first = "The reply already on its way."
    write(reply, first)
    send.click()
    holding(page, held, 1, "the first reply send")
    expect(reply).to_have_js_property("value", "")

    second = "The reply the user is watching."
    write(reply, second)
    send.click()
    expect(reply).to_have_js_property("value", "")
    # Both stand, in the order they were written. A card gains messages by insertion,
    # and a receipt acknowledging an earlier one sits between them.
    expect(thread.locator(".lf-msg").last).to_contain_text(second)
    expect(thread.locator(".lf-msg").nth(-2)).to_contain_text(first)

    held.pop(0).continue_()
    holding(page, held, 1, "the second reply send, once the first is answered")

    # What a widget asks of a draft box, through the public helper surface. The boxes
    # alone would not say this: nothing repaints one when a mask is lifted, so the
    # offer stands unseen until some view of this thread is next built and reads it.
    standing = page.evaluate(
        """async (ctx) => {
          const api = await window.__lfRuntimeImport('/runtime/widget-api.js');
          return api.loadDraft(ctx);
        }""",
        f"reply:{root['id']}",
    )
    assert standing is None, "the second send's words were offered back while in flight"
    expect(reply).to_have_js_property("value", "")
    expect(page.locator("#jobs .lf-page-thread leaf-text")).to_have_js_property(
        "value", ""
    )

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    spoken = thread.locator(".lf-msg").all_inner_texts()
    assert [
        words for words in (first, second) if not any(words in s for s in spoken)
    ] == []


@pytest.mark.parametrize("same_thread", [False, True])
def test_a_held_reply_send_leaves_a_later_reply_box_focused(
    held_events, serve, same_thread
):
    """A later draft keeps its focus and remains visible when a reply arrives.

    The long sent message tests reflow above a draft in the same card; the distant
    card tests a user who has moved to another thread.
    """
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE, comments=8))
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads > .lf-thread")
    first_id = threads.nth(0).get_attribute("data-id")
    later_id = first_id if same_thread else threads.last.get_attribute("data-id")
    first = page.locator(f'.lf-thread[data-id="{first_id}"] leaf-text')
    later = page.locator(f'.lf-thread[data-id="{later_id}"] leaf-text')
    page.locator(f'.lf-thread[data-id="{first_id}"] .lf-thread-summary').click()
    write(first, "\n\n".join(["The first reply is in flight."] * 15))

    page.locator(f'.lf-thread[data-id="{first_id}"]').get_by_role(
        "button", name="Send", exact=True
    ).click()
    holding(page, held, 1, "the first reply send")

    if not same_thread:
        page.locator(f'.lf-thread[data-id="{later_id}"] .lf-thread-summary').click()
    later.click()
    newer = "The later reply keeps the user here.\n" * (14 if same_thread else 1)
    write(later, newer)
    expect(later).to_be_focused()
    in_threads_scrollport(page, f'.lf-thread[data-id="{later_id}"] leaf-text')

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(
        page.locator(f'.lf-thread[data-id="{first_id}"] .lf-msg').last
    ).to_contain_text("The first reply is in flight.")
    expect(later).to_be_focused()
    expect(later).to_have_js_property("value", newer)
    in_threads_scrollport(page, f'.lf-thread[data-id="{later_id}"] leaf-text')


@pytest.mark.parametrize("continue_inline", [False, True])
def test_a_held_reply_send_leaves_the_panel_closed(held_events, serve, continue_inline):
    """Closing Threads during delivery is later than sending the reply."""
    browser, held = held_events
    url = serve(SEATED_QUESTION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job comes first?",
        },
    )
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    toggle = page.locator(".lf-threads-toggle")
    toggle.click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread")
    thread.locator(".lf-thread-summary").click()
    reply = thread.locator("leaf-text")
    write(reply, "Send this while I return to reading.")
    thread.get_by_role("button", name="Send", exact=True).click()
    holding(page, held, 1, "the reply send")

    toggle.click()
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    expect(toggle).to_be_focused()
    inline = page.locator(
        f'#jobs .lf-page-thread[data-thread="{root["id"]}"] leaf-text'
    )
    newer = "Continue this reply beside the question."
    if continue_inline:
        write(inline, newer)
        inline.evaluate("box => box.setSelectionRange(9, 9)")
        expect(reply).to_have_js_property("value", newer)
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(reply).to_have_js_property("value", newer if continue_inline else "")
    expect(thread.locator(".lf-msg").last).to_contain_text(
        "Send this while I return to reading."
    )
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    if continue_inline:
        expect(inline).to_be_focused()
        expect(inline).to_have_js_property("value", newer)
        assert inline.evaluate("box => box.selectionStart") == 9
    else:
        expect(toggle).to_be_focused()


def test_a_held_reply_send_preserves_a_later_scroll(held_events, serve):
    """A wheel can move the reading place while the user stands on the thread the
    reply was sent in; its delivery moves neither."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE, comments=40))
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads > .lf-thread")
    first = threads.first
    later = threads.last
    first.locator(".lf-thread-summary").click()
    reply = first.locator("leaf-text")
    write(reply, "A reply whose delivery is slow.")
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the reply send")

    bounds = page.locator(".lf-threads").bounding_box()
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
    )
    expect(later).not_to_be_in_viewport()
    page.mouse.wheel(0, 3500)
    expect(later).to_be_in_viewport()
    expect(first.locator(".lf-thread-summary")).to_be_focused()
    before = later.evaluate("node => node.getBoundingClientRect().top")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(reply).to_have_js_property("value", "")
    expect(first.locator(".lf-msg").last).to_contain_text(
        "A reply whose delivery is slow."
    )
    expect(later).to_be_in_viewport()
    assert later.evaluate("node => node.getBoundingClientRect().top") == pytest.approx(
        before, abs=1
    )
    expect(first.locator(".lf-thread-summary")).to_be_focused()


def test_a_held_comment_send_leaves_a_later_reply_box_focused(browser, serve):
    """Opening a reply while a new comment is in flight is a later gesture. The
    comment still appears, but its arrival must not move focus into its new thread."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    select_words(page, "#p3")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "The earlier comment in flight.")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # Another thread than the one in flight: that one's card is in this list too now,
    # standing for the comment while the log answers for it.
    later_id = page.locator(
        '.lf-threads > .lf-thread:not([data-id^="pending:"])'
    ).first.get_attribute("data-id")
    later = page.locator(f'.lf-thread[data-id="{later_id}"] leaf-text')
    page.locator(f'.lf-thread[data-id="{later_id}"] .lf-thread-summary').click()
    write(later, "The later reply keeps the user here.")
    later.evaluate("ta => ta.setSelectionRange(9, 9)")
    expect(later).to_be_focused()

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(3)
    expect(later).to_be_focused()
    expect(later).to_have_js_property("value", "The later reply keeps the user here.")
    assert later.evaluate("ta => ta.selectionStart") == 9


def test_newer_filter_wins_over_send_waiting_for_presentation(browser, serve):
    """A delayed Send cannot widen a newer filter or navigate its reader away."""
    page = open_page(browser, serve(NOTED_PAGE, comments=1))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    search = page.get_by_role("searchbox", name="Find in threads")
    search.fill("Comment 0")
    select_words(page, "#p1")
    page.locator(".lf-fab-input").click()
    write(
        page.locator(".lf-composer leaf-text"), "Earlier Send waiting for presentation."
    )
    hold_pending_thread_presentation(page)
    page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_function("() => window.commentPresentationHeld === true")
    search.fill("Keep this newer search")
    expect(search).to_be_focused()
    page.evaluate("releaseCommentPresentation()")
    round_trip(page)
    page.wait_for_function("() => document.body.hasAttribute('data-lf-presented')")
    expect(search).to_have_value("Keep this newer search")
    expect(search).to_be_focused()

    assert any(
        event.get("text") == "Earlier Send waiting for presentation."
        for event in events_model.read_events(serve.page_dir)
    )


@pytest.mark.parametrize("later_selection", [False, True])
def test_a_comment_hidden_by_narrowing_is_revealed_in_the_open_panel(
    browser, serve, later_selection
):
    """A new comment widens the panel's filter without taking a later selection."""
    page = open_page(browser, serve(NOTED_PAGE, comments=1))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.get_by_role("searchbox", name="Find in threads").fill("Comment 0")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)

    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(
        page.locator(".lf-composer leaf-text"),
        "This comment starts outside the filter.",
    )
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the filtered comment send")
    if later_selection:
        select_words(page, "#p2")
        expect(page.locator(".lf-fab-input")).to_be_visible()
        assert pending_text(page) == "A short second passage."

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    sent = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("text") == "This comment starts outside the filter."
    )
    expect(page.locator(".lf-thread-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value("")
    thread = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
    expect(thread).to_contain_text(sent["text"])
    if later_selection:
        assert pending_text(page) == "A short second passage."
        expect(page.locator(".lf-fab-input")).to_be_visible()
        expect(page.locator(".lf-fab-input")).not_to_be_focused()
        assert composer_quote(page)["text"].strip("“”") == "A short second passage."
    else:
        expect(thread.locator(":scope > .lf-thread-summary")).to_be_focused()


def test_an_untouched_inline_reply_follows_but_an_emptied_draft_holds(browser, serve):
    """An untouched reply is not a draft; an edit to empty is."""
    page = open_page(browser, live_url(serve(NOTED_PAGE)))
    resized(page, 1440, 900)
    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "Follow this discussion.")
    # The comment's own send in the wire before the log names it. Without that the read
    # below answers with the note the page opened on, and the reply this test is about is
    # looked for under an id no thread wears.
    with sending(page, "the comment the reply follows"):
        page.keyboard.press("ControlOrMeta+Enter")

    sent = events_model.read_events(serve.page_dir)[-1]
    thread = page.locator(
        f'.lf-margin-thread .lf-page-thread[data-thread="{sent["id"]}"]'
    )
    reply = thread.locator("leaf-text")
    expect(page.locator("#p1")).to_be_focused()
    thread.get_by_role("textbox", name="Reply", exact=True).click()
    expect(reply).to_be_focused()

    d = serve.page_dir
    v2 = NOTED_PAGE.replace(
        "A short second passage.", "A revised short second passage."
    )
    stamp_page(d, v2, "v2")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")

    # The untouched reply remains disposable UI rather than becoming a draft merely
    # because the authored page advanced around it.
    expect(reply).to_be_visible()
    write(reply, "A thought I changed my mind about.")
    write(reply, "")
    # A thread's reply draft is keyed by the name the log's answer does not change —
    # the attempt the user's own comment opened it with (thread/model.js).
    assert stored_draft_text(page, f"reply:{sent['attempt']}") == ""
    v3 = v2.replace(
        "A revised short second passage.", "A twice-revised short second passage."
    )
    stamp_page(d, v3, "v3")
    told(page)
    expect_banner_control_offered(page.locator(".lf-latest-chip"))
    expect(page.locator(".lf-version")).to_contain_text("v2")
    expect(reply).to_have_js_property("value", "")
    expect(reply).to_be_focused()


def test_a_held_comment_send_leaves_the_passage_picked_out_behind_it(
    held_events, serve
):
    """A comment's send must not take a newer passage selection with its focus handoff.

    The newer selection remains native and keeps its response field available while the
    earlier send becomes a thread behind it.

    Held rather than raced: the window is one request's flight, and a machine quick
    enough closes it before the next gesture. A loaded CI runner is not, and it said so
    as a 💬 that never came up for the passage picked out after a send."""
    browser, held = held_events
    page = open_page(browser, serve(NOTED_PAGE))
    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "The first remark.")

    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")

    # The user picks out their next passage while the first send is still in the wire.
    select_words(page, "#p2")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", "")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-thread")).to_have_count(1)

    # The send landed behind them and left the passage picked out. Read as the user's
    # own next gesture rather than as the button's rendering: the button is a state that
    # only a fresh decision repaints, so it stands wherever the last one left it — while
    # the key that comments on a selection reads the live one, and answers the general
    # box where there is none.
    assert pending_text(page) == "A short second passage.", (
        "the send's landing lost the passage the user had picked out"
    )
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == "A short second passage."


def test_a_held_comment_send_leaves_a_later_keyboard_comment_open(held_events, serve):
    """The Comment opened with `s` is later than a comment already in flight."""
    browser, held = held_events
    page = open_page(browser, serve(NOTED_PAGE))
    compose(page, "#p1", "The first remark.")

    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")

    # Leave the sending field, then use the keyboard Comment path on p2.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).not_to_have_count(0)
    target_code = page.evaluate(
        """() => {
          const top = document.querySelector('#p2').getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-picker-hint')]
            .sort((a, b) => Math.abs(a.getBoundingClientRect().top - top)
                          - Math.abs(b.getBoundingClientRect().top - top))[0]
            .dataset.lfHintCode;
        }"""
    )
    page.keyboard.type(target_code)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#p2")).to_have_class(
        re.compile(r"\blf-mark-el\b.*\blf-pending\b")
    )
    expect(page.locator(".lf-fab-bar")).to_have_attribute(
        "aria-label", re.compile(r"^Respond to paragraph")
    )

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator(".lf-thread")).to_have_count(1)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#p2")).to_have_class(
        re.compile(r"\blf-mark-el\b.*\blf-pending\b")
    )
    expect(page.locator(".lf-fab-bar")).to_have_attribute(
        "aria-label", re.compile(r"^Respond to paragraph")
    )
    assert composer_quote(page)["text"].endswith("A short second passage.")


def test_an_unsent_comment_stays_with_its_passage_when_another_is_selected(
    browser, serve
):
    """Opening fields is automatic, so selecting a new passage is not re-anchoring.

    Each passage keeps its own durable draft: the newly selected passage starts empty,
    and returning to the original passage restores the words written about it."""
    page = open_page(browser, serve(NOTED_PAGE))
    field = page.locator(".lf-fab-input")
    original = "These words belong to the first passage."

    select_words(page, "#p1")
    expect(field).to_be_visible()
    expect(field).not_to_be_focused()
    write(field, original)

    select_words(page, "#p2")
    expect(field).to_have_js_property("value", "")
    expect(field).not_to_be_focused()
    assert (
        page.evaluate(
            """prefix => Object.keys(localStorage)
          .filter(key => key.startsWith(prefix)).length""",
            draft_key(page, "composer:"),
        )
        == 1
    )

    select_words(page, "#p1")
    expect(field).to_have_js_property("value", original)
    expect(field).not_to_be_focused()


def test_failed_settlement_keeps_the_base_for_a_chained_nondurable_edit(
    browser, serve, one_user
):
    """A failed tombstone does not make the next local edit descend from thin air."""
    url = serve(LONG_PAGE)
    shared = open_page(browser, url, context=one_user)
    local = open_page(browser, url, context=one_user)
    for page in (shared, local):
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
    predecessor = "The durable predecessor that this local branch replaces."
    first = "The first nondurable comment on that branch."
    second = "The chained nondurable comment keeps the same base."
    write(shared.locator(".lf-general leaf-text"), predecessor)
    expect(local.locator(".lf-general leaf-text")).to_have_js_property(
        "value", predecessor
    )
    local.evaluate(
        """([draft, first, second]) => {
          const set = Storage.prototype.setItem;
          let secondFailed = false;
          window.lfBranchAttempt = null;
          Storage.prototype.setItem = function (key, value) {
            if (key === draft) {
              const record = JSON.parse(value);
              if (record.text === first) {
                window.lfBranchAttempt = record.attempt;
                throw new DOMException('full', 'QuotaExceededError');
              }
              if (record.settled && record.attempt === window.lfBranchAttempt)
                throw new DOMException('full', 'QuotaExceededError');
              if (record.text === second && !secondFailed) {
                secondFailed = true;
                throw new DOMException('full', 'QuotaExceededError');
              }
            }
            return set.call(this, key, value);
          };
        }""",
        [draft_key(local, "general"), first, second],
    )

    write(local.locator(".lf-general leaf-text"), first)
    local.locator(".lf-general button").click()
    round_trip(local)
    expect(local.locator(".lf-general leaf-text")).to_have_js_property("value", "")
    write(local.locator(".lf-general leaf-text"), second)
    expect(local.locator(".lf-general button")).to_have_attribute(
        "aria-disabled", "false"
    )
    local.locator(".lf-general button").click()
    _until(local, lambda traffic: traffic.sends == 2, "sent the chained generation")
    round_trip(local)

    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [first, second]
    assert len({event["attempt"] for event in comments}) == 2
    # The tombstone is written where the send reads its own response, one step behind the
    # response itself: `round_trip` watches the browser's trip, and the page settles the
    # generation in the continuation after it — so the log holds the send before the store
    # holds its settlement. Read the store on the fact the page states, the way the tabs
    # below do; a plain read is the same assertion made a step early, and a loaded runner
    # lands in that step, which is what CI read here as an unsettled chain.
    until_draft_settled(local, "general")


def test_a_stale_question_first_message_cannot_append_across_tabs(
    browser, serve, one_user
):
    """A stale visible generation refreshes the shared tombstone before POST.

    The second tab's storage repaint is then deliberately suppressed. Its text box
    remains stale after the first send stored its tombstone, so a second real press
    proves that readable absence is settlement rather than permission to trust the
    old in-memory value.
    """
    url = serve(SEATED_QUESTION_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(
        browser,
        url,
        context=one_user,
        init_script="""addEventListener('storage', event => {
          if (event.key !== window.lfDraftKey) return;
          try {
            if (JSON.parse(event.newValue)?.settled)
              event.stopImmediatePropagation();
          } catch {}
        }, true);""",
    )
    name_the_draft(second, "say:jobs")
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "  Keep one exact first answer.  "
    write(first_say.locator("leaf-text"), raw)
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)
    # The init-script capture listener beats the runtime's listener for settlement,
    # leaving the old value on screen after the other tab stores its tombstone.
    cut = CutOff().hold(second)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first_say.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the first answer")

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    until_draft_settled(first, "say:jobs")
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)
    assert stored_draft_settled(second, "say:jobs")
    second_send = second_say.get_by_role("button", name="Send", exact=True)
    expect(second_send).to_have_attribute("aria-disabled", "false")
    second_send.click()
    expect(second_say.locator("leaf-text")).to_have_js_property("value", "")
    cut.restore()

    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [(event["anchor"], event["text"]) for event in roots] == [
        ({"section": "jobs"}, raw)
    ]
    assert _traffic(first).sends + _traffic(second).sends == 1


def test_a_question_reply_appends_one_event_across_tabs(browser, serve, one_user):
    """Both inline views may POST the shared reply; its attempt appends it once."""
    url = serve(SEATED_QUESTION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job should come first?",
        },
    )
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    selector = f'#jobs > .lf-thread-seat > .lf-page-thread[data-thread="{root["id"]}"]'
    first_thread = first.locator(selector)
    second_thread = second.locator(selector)
    raw = "  The camera, then the mounting work.  "
    write(first_thread.locator("leaf-text"), raw)
    expect(second_thread.locator("leaf-text")).to_have_js_property("value", raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first_thread.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the first reply")
    second_thread.get_by_role("button", name="Send", exact=True).click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert [(event["parent"], event["text"]) for event in replies] == [
        (root["id"], raw)
    ]
    assert _traffic(first).sends == _traffic(second).sends == 1


def test_a_held_thread_send_cannot_clear_a_newer_raw_draft(browser, serve, one_user):
    """Settlement compares raw words, so an older POST cannot erase a later edit."""
    url = serve(SEATED_QUESTION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "What should the order be?",
        },
    )
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first.locator(".lf-threads-toggle").click()
    panel_settled(first)
    inline = first.locator(
        f'#jobs .lf-page-thread[data-thread="{root["id"]}"] leaf-text'
    )
    panel = first.locator(f'.lf-thread[data-id="{root["id"]}"]')
    second_inline = second.locator(
        f'#jobs .lf-page-thread[data-thread="{root["id"]}"] leaf-text'
    )
    sent_raw = "  Send this part first.  "
    newer_raw = "  A later thought stays raw.  "
    write(inline, sent_raw)
    expect(panel.locator("leaf-text")).to_have_js_property("value", sent_raw)
    expect(second_inline).to_have_js_property("value", sent_raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    panel.locator(".lf-thread-summary").click()
    panel.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the older reply")
    write(second_inline, newer_raw)
    expect(inline).to_have_js_property("value", newer_raw)
    expect(panel.locator("leaf-text")).to_have_js_property("value", newer_raw)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    expect(inline).to_have_js_property("value", newer_raw)
    expect(panel.locator("leaf-text")).to_have_js_property("value", newer_raw)
    expect(second_inline).to_have_js_property("value", newer_raw)
    # This root was appended by the agent, so it carries no attempt and its reply draft
    # keys by the id, which for such a thread never changes either.
    assert stored_draft_text(first, f"reply:{root['id']}") == newer_raw
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert [event["text"] for event in replies] == [sent_raw]


def test_a_failed_concurrent_question_send_keeps_the_accepted_attempt(
    browser, serve, one_user
):
    """One request may lose its answer while another tab gets the same attempt
    accepted. The first tab adopts that durable outcome instead of reporting failure
    or offering the words as a second message."""
    url = serve(SEATED_QUESTION_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "  Retry this exact answer.  "
    write(first_say.locator("leaf-text"), raw)
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first_say.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the failing answer")
    second_say.get_by_role("button", name="Send", exact=True).click()
    round_trip(second)

    refuse(held[0])
    first.unroute("**/api/event")
    round_trip(first)
    # The words standing in the seat's own thread are what says the send landed;
    # a notice saying so beside them would be the same acknowledgement twice.
    expect(first.locator("#jobs > .lf-thread-seat")).to_contain_text(raw.strip())
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]
    # Asked of the words rather than of the box: a seat that can hold keeps its composer
    # standing after every root (renderSeats), so an empty one is what says the
    # tab adopted the durable outcome instead of holding the words for a second send.
    expect(first_say.locator("leaf-text")).to_have_js_property("value", "")
    expect(second_say.locator("leaf-text")).to_have_js_property("value", "")


@pytest.mark.parametrize("newer", [None, "A newer thought must survive."])
def test_a_late_refusal_cannot_restore_an_attempt_another_tab_settled(
    browser, serve, one_user, newer
):
    """A final answer belongs to one execution; the accepted log owns the draft."""
    url = serve(SEATED_QUESTION_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "The shared generation one tab will accept."
    write(first_say.locator("leaf-text"), raw)
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)

    held_event = []
    held_state = []
    first.route("**/api/event", lambda route: held_event.append(route))
    first.route("**/api/state*", lambda route: held_state.append(route))
    try:
        first_say.get_by_role("button", name="Send", exact=True).click()
        holding(first, held_event, 1, "the first tab's answer")
        attempt = held_event[0].request.post_data_json["attempt"]

        second_say.get_by_role("button", name="Send", exact=True).click()
        round_trip(second)
        expect(first_say.locator("leaf-text")).to_have_js_property("value", "")
        until_draft_settled(first, "say:jobs")
        holding(first, held_state, 1, "the accepted attempt's state read")
        if newer is not None:
            write(first_say.locator("leaf-text"), newer)

        with first.expect_response(
            lambda response: "/api/event" in response.url
        ) as refused:
            held_event.pop(0).fulfill(
                status=400,
                json={
                    "ok": False,
                    "final": True,
                    "attempt": attempt,
                    "error": "the earlier execution was refused",
                },
            )
        expect(first.locator(".lf-notice")).to_contain_text("Couldn't send")
        expected_error = f"400 {refused.value.url}"
        first_errors = first.lf_errors
        first_errors.remove(expected_error)
        first_errors.remove(
            "Failed to load resource: the server responded with a status of 400 "
            "(Bad Request)"
        )
        expect(first_say.locator("leaf-text")).to_have_js_property("value", newer or "")

        held_state.pop(0).continue_()
        first.unroute("**/api/state*")
        round_trip(first)
        expect(first_say.locator("leaf-text")).to_have_js_property("value", newer or "")
    finally:
        for route in held_event + held_state:
            refuse(route)
        first.unroute_all(behavior="wait")


def test_a_question_can_send_when_draft_storage_refuses_writes(browser, serve):
    """Persistence failure costs recovery, not the live box's Send action."""
    page = open_page(
        browser,
        serve(SEATED_QUESTION_PAGE),
        init_script="""Storage.prototype.setItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
    say = page.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "  Send even though this draft cannot persist.  "
    write(say.locator("leaf-text"), raw)
    say.get_by_role("button", name="Send", exact=True).click()
    _until(page, lambda t: t.sends == 1, "sent the live unpersisted answer")
    round_trip(page)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]


def test_a_closed_sender_cannot_append_its_accepted_attempt_twice(
    browser, serve, one_user
):
    """The log returns the accepted attempt when its first sender cannot settle it.

    Both tabs are held stale, and each refusal states one half of that sentence. The
    wrapper below closes the send path — the POST lands, the runtime never hears the
    answer — and the poll is the other way the same tab settles a draft
    (settleAcceptedDrafts), so a sender left polling can still tombstone the shared
    generation out from under the replacement. It did: within a poll of the server
    taking the answer, first's own next poll read the attempt back out of the log and
    settled it, second's box emptied, and the send this test is about had nothing left
    to send — sends=0, the failure landing either on `sendDraft` refusing a settled
    record or on Playwright refusing a Send the box had already disabled, depending on
    which side of the click the storage event fell. The race was one poll interval
    against Playwright's own click, which is a gap only a loaded machine loses.

    Second's refusal is the older half and states the same fact from its own side: the
    replacement must not learn the attempt is in the log before it sends, or it would
    correctly decline to. Both go through `held_stale` rather than a live `page.route`,
    which reaches no poll already in the wire."""
    url = serve(SEATED_QUESTION_PAGE)
    first = open_page(browser, url, context=held_stale(one_user))
    second_held = held_stale(one_user)
    second = open_page(browser, url, context=second_held)
    raw = "One answer survives its sender closing."
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    write(first_say.locator("leaf-text"), raw)
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)
    first.evaluate(
        """() => {
          const actualFetch = window.fetch.bind(window);
          window.fetch = (input, init) => {
            const sent = actualFetch(input, init);
            if (!String(input).endsWith('/api/event')) return sent;
            return sent.then(() => {
              window.lfAcceptedAttempt = true;
              return new Promise(() => {});
            });
          };
        }"""
    )
    first_say.get_by_role("button", name="Send", exact=True).click()
    _until(first, lambda t: t.sends == 1, "sent the first answer to the server")
    first.wait_for_function("() => window.lfAcceptedAttempt === true")
    second_say.get_by_role("button", name="Send", exact=True).click()
    _until(second, lambda t: t.acked == 1, "received the accepted attempt")

    first.close()
    second_held.restore()
    told(second)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert len(roots) == 1
    assert roots[0]["text"] == raw
    assert roots[0]["attempt"]


def test_an_older_settlement_cannot_erase_a_newer_failed_write(
    browser, serve, one_user
):
    """A nondurable local generation outranks storage news about its predecessor."""
    url = serve(SEATED_QUESTION_PAGE)
    other = open_page(browser, url, context=one_user)
    old = "The older persisted answer."
    other_say = other.locator("#jobs > .lf-thread-seat > .lf-say")
    write(other_say.locator("leaf-text"), old)

    local = open_page(
        browser,
        url,
        context=one_user,
        init_script="""Storage.prototype.setItem = function () {
          throw new DOMException('full', 'QuotaExceededError');
        };""",
    )
    local_say = local.locator("#jobs > .lf-thread-seat > .lf-say")
    expect(local_say.locator("leaf-text")).to_have_js_property("value", old)
    newer = "The newer local answer whose write failed."
    write(local_say.locator("leaf-text"), "A first nondurable edit on the same branch.")
    write(local_say.locator("leaf-text"), newer)
    expect(other_say.locator("leaf-text")).to_have_js_property("value", old)

    other_say.get_by_role("button", name="Send", exact=True).click()
    round_trip(other)
    until_draft_settled(other, "say:jobs")
    expect(local_say.locator("leaf-text")).to_have_js_property("value", newer)

    local_say.get_by_role("button", name="Send", exact=True).click()
    _until(local, lambda t: t.sends == 1, "sent the nondurable newer answer")
    round_trip(local)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old, newer]
    assert len({event["attempt"] for event in roots}) == 2


def test_an_accepted_nondurable_branch_cannot_tombstone_a_newer_shared_generation(
    browser, serve, one_user
):
    """A held older send reconciles its base before writing settlement."""
    url = serve(SEATED_QUESTION_PAGE)
    older = open_page(
        browser,
        url,
        context=one_user,
        init_script="""(() => {
          const set = Storage.prototype.setItem;
          let refuse = true;
          Storage.prototype.setItem = function (key, value) {
            if (refuse && key === window.lfDraftKey) {
              refuse = false;
              throw new DOMException('full', 'QuotaExceededError');
            }
            return set.call(this, key, value);
          };
        })();"""
        + DEAF_TO_DRAFT_NEWS,
    )
    name_the_draft(older, "say:jobs")
    newer_tab = open_page(browser, url, context=one_user)
    older_say = older.locator("#jobs > .lf-thread-seat > .lf-say")
    newer_say = newer_tab.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The older nondurable answer already in flight."
    newer = "The newer durable answer survives the older response."
    write(older_say.locator("leaf-text"), old)

    held = []
    older.route("**/api/event", lambda route: held.append(route))
    older_say.get_by_role("button", name="Send", exact=True).click()
    holding(older, held, 1, "the nondurable send")
    write(newer_say.locator("leaf-text"), newer)
    assert stored_draft_text(newer_tab, "say:jobs") == newer
    newer_tab.close()

    held[0].continue_()
    older.unroute("**/api/event")
    round_trip(older)
    restored = older.locator("#jobs > .lf-thread-seat > .lf-say leaf-text")
    expect(restored).to_have_js_property("value", newer)
    assert stored_draft_text(older, "say:jobs") == newer
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old]


def test_a_nondurable_branch_yields_to_unrelated_live_storage_news(
    browser, serve, one_user
):
    """Only news from a branch's base may be replaced by that local branch."""
    url = serve(SEATED_QUESTION_PAGE)
    local = open_page(
        browser,
        url,
        context=one_user,
        init_script="""(() => {
          const set = Storage.prototype.setItem;
          let refuse = true;
          Storage.prototype.setItem = function (key, value) {
            if (refuse && key === window.lfDraftKey) {
              refuse = false;
              throw new DOMException('full', 'QuotaExceededError');
            }
            return set.call(this, key, value);
          };
          window.lfDraftNews = 0;
          addEventListener('storage', event => {
            if (event.key === window.lfDraftKey) window.lfDraftNews += 1;
          }, true);
        })();""",
    )
    name_the_draft(local, "say:jobs")
    shared = open_page(browser, url, context=one_user)
    local_say = local.locator("#jobs > .lf-thread-seat > .lf-say")
    shared_say = shared.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The local write failed before shared storage changed."
    newer = "The later durable generation owns the user now."
    write(local_say.locator("leaf-text"), old)
    write(shared_say.locator("leaf-text"), newer)
    local.wait_for_function("() => window.lfDraftNews > 0")

    expect(local_say.locator("leaf-text")).to_have_js_property("value", newer)
    expect(shared_say.locator("leaf-text")).to_have_js_property("value", newer)
    assert stored_draft_text(local, "say:jobs") == newer


def test_a_delayed_storage_event_cannot_send_a_stale_durable_generation(
    browser, serve, one_user
):
    """Send refreshes shared storage instead of trusting a stale durable cache."""
    url = serve(SEATED_QUESTION_PAGE)
    stale = open_page(
        browser, url, context=held_stale(one_user), init_script=DEAF_TO_DRAFT_NEWS
    )
    name_the_draft(stale, "say:jobs")
    current = open_page(browser, url, context=one_user)
    stale_say = stale.locator("#jobs > .lf-thread-seat > .lf-say")
    current_say = current.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The stale tab's older generation."
    newer = "The newer shared generation."
    write(stale_say.locator("leaf-text"), old)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", old)
    write(current_say.locator("leaf-text"), newer)
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", old)
    assert stored_draft_text(stale, "say:jobs") == newer

    stale_say.get_by_role("button", name="Send", exact=True).click()
    assert _traffic(stale).sends == 0
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", newer)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", newer)
    assert [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ] == []


def test_a_stale_cancel_cannot_settle_a_newer_durable_generation(
    browser, serve, one_user
):
    """Cancel refreshes ownership before writing the shared tombstone."""
    url = serve(JOURNEY_V1)
    stale = open_page(
        browser, url, context=held_stale(one_user), init_script=DEAF_TO_DRAFT_NEWS
    )
    name_the_draft(stale, "edit:draft-ops")
    current = open_page(browser, url, context=one_user)
    stale_draft = stale.locator("#draft-ops")
    current_draft = current.locator("#draft-ops")
    stale_draft.locator(".lf-draft-body").dblclick()
    current_draft.locator(".lf-draft-body").dblclick()
    old = "The older edit visible in the stale tab."
    newer = "The newer edit now owned by shared storage."
    write(stale_draft.locator("leaf-text"), old)
    expect(current_draft.locator("leaf-text")).to_have_js_property("value", old)
    write(current_draft.locator("leaf-text"), newer)
    expect(stale_draft.locator("leaf-text")).to_have_js_property("value", old)
    assert stored_draft_text(stale, "edit:draft-ops") == newer

    cancel_draft(stale)
    expect(current_draft.locator("leaf-text")).to_have_js_property("value", newer)
    assert stored_draft_text(current, "edit:draft-ops") == newer
    stale_draft.locator(".lf-draft-body").dblclick()
    expect(stale_draft.locator("leaf-text")).to_have_js_property("value", newer)


def test_poll_settlement_cannot_tombstone_a_newer_durable_generation(
    browser, serve, one_user
):
    """Log reconciliation settles only the generation still shared by storage."""
    url = serve(SEATED_QUESTION_PAGE)
    # The hold costs the most here, where the poll released at the end is the subject
    # rather than an interruption: an earlier poll reconciling this tab onto the newer
    # generation leaves settlement nothing older to be tempted by, so the assertions
    # below would pass while asking nothing rather than fail.
    stale_held = held_stale(one_user)
    stale = open_page(browser, url, context=stale_held, init_script=DEAF_TO_DRAFT_NEWS)
    name_the_draft(stale, "say:jobs")
    current = open_page(browser, url, context=one_user)
    stale_say = stale.locator("#jobs > .lf-thread-seat > .lf-say")
    current_say = current.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The accepted generation cached by the stale tab."
    newer = "The newer generation shared before settlement arrived."
    write(stale_say.locator("leaf-text"), old)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", old)
    old_attempt = stale.evaluate(
        "key => JSON.parse(localStorage.getItem(key)).attempt",
        draft_key(stale, "say:jobs"),
    )
    write(current_say.locator("leaf-text"), newer)
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", old)

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": old,
            "attempt": old_attempt,
        },
    )
    # Settlement reconciles before it claims, so this poll adopts the newer generation
    # and leaves it standing. `held_stale`'s refusal is lifted here rather than earlier,
    # with the older attempt in the log and the older generation still cached, which is
    # the only arrangement that asks anything.
    stale_held.restore()
    told(stale)
    assert stored_draft_text(current, "say:jobs") == newer
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", newer)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", newer)


def test_a_read_failure_cannot_make_a_successfully_written_draft_unsendable(
    browser, serve
):
    """The document cache owns its generation even when getItem later refuses it."""
    page = open_page(
        browser,
        serve(SEATED_QUESTION_PAGE),
        init_script="""Storage.prototype.getItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
    raw = "A live value remains sendable when storage reads fail."
    say = page.locator("#jobs > .lf-thread-seat > .lf-say")
    write(say.locator("leaf-text"), raw)
    say.get_by_role("button", name="Send", exact=True).click()
    _until(page, lambda t: t.sends == 1, "sent the cached draft")
    round_trip(page)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]


def test_a_remove_failure_cannot_resurrect_an_accepted_draft(browser, serve, one_user):
    """Settlement is a record and a log fact; draft cleanup never calls removeItem."""
    url = serve(SEATED_QUESTION_PAGE)
    first = open_page(
        browser,
        url,
        context=one_user,
        init_script="""Storage.prototype.removeItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
    raw = "A sent draft must not return."
    say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    write(say.locator("leaf-text"), raw)
    say.get_by_role("button", name="Send", exact=True).click()
    round_trip(first)
    until_draft_settled(first, "say:jobs")

    again = open_page(browser, url, context=one_user)
    # The composer is still standing — a seat that can hold keeps it — so the claim is
    # about what it opens with: a settled draft is words the next tab must not be handed.
    expect(
        again.locator("#jobs > .lf-thread-seat > .lf-say leaf-text")
    ).to_have_js_property("value", "")
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]


def test_an_intentional_later_identical_reply_gets_a_fresh_attempt(browser, serve):
    """Identity follows the edit generation, never content or a time window."""
    url = serve(SEATED_QUESTION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Repeat the confirmation if it remains true.",
        },
    )
    page = open_page(browser, url)
    thread = page.locator(f'#jobs .lf-page-thread[data-thread="{root["id"]}"]')
    text = "Still true."
    for _ in range(2):
        write(thread.locator("leaf-text"), text)
        thread.get_by_role("button", name="Send", exact=True).click()
        round_trip(page)
        expect(thread.locator("leaf-text")).to_have_js_property("value", "")

    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert [event["text"] for event in replies] == [text, text]
    assert len({event["attempt"] for event in replies}) == 2


def test_an_unsent_draft_outlives_the_tab_it_was_typed_in(browser, serve, one_user):
    """The one gesture the tab-local store lost a draft to, and it is the ordinary one:
    every round's reply hands the URL over again, so a page's tabs accumulate and the
    one holding a half-written sentence is as likely to be shut as any other."""
    url = serve(LONG_PAGE)
    page = open_page(browser, url, context=one_user)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    typed = "Half a thought, and then the tab went."
    write(page.locator(".lf-general leaf-text"), typed)
    page.close()

    again = open_page(browser, url, context=one_user)
    expect(again.locator(".lf-general leaf-text")).to_have_js_property("value", typed)


def test_a_draft_the_chrome_stands_down_says_so_and_keeps_an_address(browser, serve):
    """A press on the banner takes the composer off screen and keeps the words, and for
    a long time that was the whole of it: the bar went, the mark went, no notice and no
    dialog said anything, and the only way back was returning to that version and
    reselecting that exact passage. Words a user cannot find again are words they have
    lost, whatever localStorage still holds.

    So the moment says what became of them and names the address that answers — and the
    address is offered only while there is a draft standing to go to, which is the half
    that keeps the sentence honest."""
    page = open_page(browser, serve(LONG_PAGE))
    kept = "Half a sentence, and then the banner."

    # Nothing written, nothing to return to: the sequence does not offer the destination.
    page.keyboard.press("g")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("Threads panel")
    draft_route = page.locator('.lf-shortcut[data-lf-command-ids~="writing.resume"]')
    expect(draft_route).to_have_count(0)
    page.keyboard.press("Escape")

    compose(page, "#p3", kept)
    assert pending_text(page), "the open box left its own passage unmarked"

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert pending_text(page) == "", "a box off screen left its passage marked"
    notice = page.locator(".lf-notice")
    expect(notice).to_have_class(re.compile(r"\bshow\b"))
    assert notice.inner_text() == "Draft kept — g i resumes writing"

    page.keyboard.press("g")
    shortcut_bar_text(page)
    # The one-row line can trim this destination while leaving it in the register.
    expect(draft_route).to_have_count(1)
    page.keyboard.press("i")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", kept)
    assert pending_text(page), "the box came back on nothing"


def test_picture_paste_belongs_to_the_composer_not_the_shared_text_field(
    browser, serve
):
    """A direct editor pastes text; a composer takes pictures before text insertion."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Paste ownership",
                '<h1>Paste ownership</h1><p id="passage">Comment on this passage.</p>'
                '<lf-draft id="text-only"><pre>Keep WORD tail</pre></lf-draft>',
            )
        ),
    )
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    pixels = base64.b64encode(
        (example_media() / "051bee487bfb5d13.png").read_bytes()
    ).decode()
    page.evaluate(
        """async encoded => {
      window.clipboardBeforePasteTest = await navigator.clipboard.read();
      const bytes=Uint8Array.from(atob(encoded), char=>char.charCodeAt(0));
      window.pasteTestPicture=new Blob([bytes], {type:'image/png'});
    }""",
        pixels,
    )

    def paste(box, text, picture):
        box.focus()
        box.evaluate("el=>el.setSelectionRange(5,9)")
        page.evaluate(
            """async ([text,picture]) => {
          const payload={};
          if(text!==null)payload['text/plain']=new Blob([text],{type:'text/plain'});
          if(picture)payload['image/png']=window.pasteTestPicture;
          await navigator.clipboard.write([new ClipboardItem(payload)]);
        }""",
            [text, picture],
        )
        page.keyboard.press("ControlOrMeta+v")

    try:
        draft_control(page, "edit", "text-only").click()
        editor = page.locator("#text-only leaf-text")
        for text, picture, expected in [
            ("Pasted words", False, "Keep Pasted words tail"),
            ("Pasted words", True, "Keep Pasted words tail"),
            (None, True, "Keep  tail"),
        ]:
            write(editor, "Keep WORD tail")
            paste(editor, text, picture)
            expect(editor).to_have_js_property("value", expected)
        draft_control(page, "cancel", "text-only").click()

        compose(page, "#passage")
        composer = page.locator(".lf-fab-input")
        write(composer, "Keep WORD tail")
        with page.expect_response(lambda response: response.url.endswith("/api/media")):
            paste(composer, "Pasted words", True)
        expect(page.locator(".lf-composer-media img")).to_have_count(1)
        expect(composer).to_have_js_property("value", "Keep WORD tail")
        # Editing another surface chooses it; attachment removal is an edit that
        # chooses this composer again even though focusing it alone did not.
        page.keyboard.press("Escape")
        draft_control(page, "edit", "text-only").click()
        write(editor, "A later document edit")
        page.keyboard.press("Escape")
        compose(page, "#passage")
        page.get_by_role("button", name="Remove pasted image 1", exact=True).click()
        expect(page.locator(".lf-composer-media img")).to_have_count(0)
        page.locator("h1").click()
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(composer).to_be_focused()
        expect(composer).to_have_js_property("value", "Keep WORD tail")
    finally:
        page.evaluate("""async () => {
          const previous=window.clipboardBeforePasteTest;
          if(previous.length)await navigator.clipboard.write(previous);
          else await navigator.clipboard.writeText('');
        }""")


@pytest.mark.parametrize("leave", [False, True])
def test_image_upload_completion_preserves_the_readers_focus_and_scroll(
    browser, serve, leave
):
    """Finishing a paste updates the draft without repeating the user's entry gesture."""
    held = []
    controlled = primed(
        browser,
        lambda page: page.route("**/api/media", lambda route: held.append(route)),
    )
    page = open_page(controlled, serve(LONG_PAGE))
    compose(page, "#p3")
    box = page.locator(".lf-fab-input")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    box.evaluate(
        """(box, encoded) => {
          const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
          const transfer = new DataTransfer();
          transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
          box.dispatchEvent(new ClipboardEvent('paste', {
            bubbles: true, cancelable: true, clipboardData: transfer,
          }));
        }""",
        base64.b64encode(pixels).decode(),
    )
    holding(page, held, 1, "the pasted image")
    expect(box).to_have_attribute("aria-busy", "true")
    expect(box).to_be_focused()
    if leave:
        page.keyboard.press("Tab")
        expect(box).not_to_be_focused()
        page.mouse.move(100, 500)
        page.mouse.wheel(0, 1000)
        page.wait_for_function("scrollY > 800")
        scroll_settled(page)
    before = page.evaluate("scrollY")
    page.evaluate("window.uploadFocus = document.activeElement")
    held.pop().continue_()
    expect(box).not_to_have_attribute("aria-busy", "true")
    expect(page.locator(".lf-composer-media img")).to_have_count(1)
    assert page.evaluate("scrollY") == before
    assert page.evaluate("document.activeElement === window.uploadFocus")


def test_a_pasted_image_is_a_whole_draft_and_leaves_with_the_send_that_took_it(
    browser, serve
):
    """An image and no words is a draft, and the text box is the one place it does not
    show: the box keeps the Markdown and the shelf shows the thumbnail. So a reading
    that asks the text box whether anything is in here answers "empty" about a box the
    user can see holds a picture, and the two directions fail in opposite ways — the
    kept notice never appears for a picture put away, and it appears for a picture that
    has just been sent, over a box with nothing left in it.

    Both directions here, and the box the user opens next, because a shelf that
    outlived its send is an image that rides into the next passage's draft."""
    page = open_page(browser, serve(LONG_PAGE))
    image_markdown = "![Pasted image](/media/051bee487bfb5d13.png)"
    compose(page, "#p3")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.locator(".lf-fab-input").evaluate(
            """(box, encoded) => {
              const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
              const transfer = new DataTransfer();
              transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
              box.dispatchEvent(new ClipboardEvent('paste', {
                bubbles: true,
                cancelable: true,
                clipboardData: transfer,
              }));
            }""",
            base64.b64encode(pixels).decode(),
        )
    shelf = page.locator(".lf-composer .lf-composer-media")
    expect(shelf.locator("img")).to_be_visible()

    # Put away: the picture is words enough to keep, and to be told about.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-composer")).to_be_hidden()
    notice = page.locator(".lf-notice")
    assert notice.inner_text() == "Draft kept — g i resumes writing"
    page.keyboard.press("g")
    shortcut_bar_text(page)
    expect(
        page.locator('.lf-shortcut[data-lf-command-ids~="writing.resume"]')
    ).to_have_count(1)
    page.keyboard.press("i")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", "")
    expect(shelf.locator("img")).to_be_visible()

    # Sent: the box is empty because the send emptied it, and says nothing about drafts.
    # Every word the status line says through the send, not the one left standing at the
    # end of it: a wrong sentence four seconds long is one the user reads.
    page.evaluate("""() => {
      const el = document.querySelector('.lf-notice');
      window.__said = [];
      new MutationObserver(() => window.__said.push(el.textContent)).observe(el, {
        childList: true,
        characterData: true,
        subtree: true,
      });
    }""")
    with sending(page, "the image-only comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert events_model.read_events(serve.page_dir)[-1]["text"] == image_markdown
    assert page.evaluate("window.__said") == []

    # And the next passage's box opens on nothing, shelf included.
    typed = "A second comment, and no image with it."
    compose(page, "#p5", typed)
    expect(shelf).to_be_hidden()
    with sending(page, "the second comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    assert events_model.read_events(serve.page_dir)[-1]["text"] == typed


def test_a_held_selection_comment_preserves_a_newer_exact_draft(held_events, serve):
    """A selection send owns one composer generation, not the passage.

    The send takes its own words with it — they stand in the thread it drew before the
    log has answered — and the composer opened again on that passage holds a generation
    of its own, which the older answer must not settle."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    old = "The selected passage needs this first comment."
    newer = "  A newer selection comment remains in the composer.  "
    compose(page, "#p3", old)
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the selection comment")
    expect(page.locator("[data-attempt]").first).to_contain_text(old)

    compose(page, "#p3", newer)
    box = page.locator(".lf-composer leaf-text")
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(box).to_have_js_property("value", newer)
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [old]
    assert comments[0]["attempt"]


def test_two_passages_hold_two_composer_drafts(browser, serve, one_user):
    """One key for the composer was enough while a draft died with its tab; shared, it
    is a draft on one passage overwriting the words being typed on another. The key is
    the anchor, so the two coexist — and the record says when it was touched, which is
    what a tab arriving to both of them reopens on."""
    url = serve(LONG_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)

    early = "This paragraph buries the point."
    late = "And this one repeats it."
    compose(first, "#p3", early)
    compose(second, "#p9", late)
    expect(first.locator(".lf-composer leaf-text")).to_have_js_property("value", early)
    expect(second.locator(".lf-composer leaf-text")).to_have_js_property("value", late)

    # A tab arriving now: one composer, on the passage touched last.
    third = open_page(browser, url, context=one_user)
    expect(third.locator(".lf-composer leaf-text")).to_have_js_property("value", late)


def test_comment_follows_a_new_standing_instead_of_an_earlier_draft(browser, serve):
    """The earlier draft keeps its subject while a later keyboard landing names
    the next comment. Resume recovers the editor that followed its earlier passage."""
    source = LONG_PAGE.replace(
        "<p id='p40'>", '<p id="p40"><a id="later-link" href="#p41">Later item</a> '
    )
    page = open_page(browser, serve(source))
    words = "Carry these unfinished words to the item I am at now."
    choose_comment_target(page, "#p3")
    write(page.locator(".lf-fab-input"), words)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    rendered(page)
    earlier = page.locator(".lf-fab-input")
    earlier.evaluate("node => {window.earlierEditor = node;}")
    before_field = earlier.bounding_box()
    before_target = page.locator("#p3").bounding_box()
    page.keyboard.press("Shift+Tab")
    page.locator("#later-link").scroll_into_view_if_needed()
    go_to_address(page, "Link", "later-link")
    expect(page.locator("#p3")).not_to_be_in_viewport()
    expect(earlier).not_to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_attribute("aria-label", re.compile("Paragraph 3"))
    after_field = earlier.bounding_box()
    after_target = page.locator("#p3").bounding_box()
    for axis in ("x", "y"):
        assert after_field[axis] - before_field[axis] == pytest.approx(
            after_target[axis] - before_target[axis], abs=2
        )

    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(earlier).to_be_focused()
    expect(earlier).to_be_in_viewport()
    expect(page.locator("#p3")).to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_js_property("selectionStart", 1)
    expect(earlier).to_have_js_property("selectionEnd", 1)
    assert earlier.evaluate("node => node === window.earlierEditor")
    page.keyboard.press("Shift+Tab")
    page.locator("#later-link").scroll_into_view_if_needed()
    go_to_address(page, "Link", "later-link")
    expect(page.locator("#p41")).to_be_focused()
    expect(earlier).not_to_be_in_viewport()

    page.keyboard.press("c")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    expect(field).to_have_attribute("aria-label", re.compile("Paragraph 41"))
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    expect(field).to_have_attribute("aria-label", re.compile("Paragraph 41"))
    expect(field).to_have_js_property("selectionStart", 1)
    with sending(page, "comment"):
        page.keyboard.press("Enter")
    sent = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [(event["text"], event["anchor"]) for event in sent] == [
        (words, {"section": "p41"})
    ]


@pytest.mark.parametrize("existing_reply", ["", "This thread already holds a reply."])
def test_comment_follows_a_thread_standing_instead_of_an_earlier_draft(
    browser, serve, existing_reply
):
    """A chrome thread is a destination; an earlier draft follows its own passage.

    Resume returns its words and caret before Comment answers the standing thread.
    """
    page = open_page(browser, serve(LONG_PAGE, anchored=[("p41", "Paragraph 41.")]))
    thread = page.locator(".lf-margin-preview .lf-page-thread")
    if existing_reply:
        page.keyboard.press("t")
        page.keyboard.press("c")
        write(thread.locator("leaf-text"), existing_reply)
        page.keyboard.press("Escape")
    words = "These words belong to my earlier unfinished comment."
    choose_comment_target(page, "#p3")
    write(page.locator(".lf-fab-input"), words)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    rendered(page)
    earlier = page.locator(".lf-fab-input")
    earlier.evaluate("node => {window.earlierEditor = node;}")
    before_field = earlier.bounding_box()
    before_target = page.locator("#p3").bounding_box()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator("#p3")).not_to_be_in_viewport()
    expect(earlier).not_to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_attribute("aria-label", re.compile("Paragraph 3"))
    after_field = earlier.bounding_box()
    after_target = page.locator("#p3").bounding_box()
    for axis in ("x", "y"):
        assert after_field[axis] - before_field[axis] == pytest.approx(
            after_target[axis] - before_target[axis], abs=2
        )

    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(earlier).to_be_focused()
    expect(earlier).to_be_in_viewport()
    expect(page.locator("#p3")).to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_js_property("selectionStart", 1)
    expect(earlier).to_have_js_property("selectionEnd", 1)
    assert earlier.evaluate("node => node === window.earlierEditor")
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator("#p3")).not_to_be_in_viewport()
    expect(earlier).not_to_be_in_viewport()
    page.keyboard.press("c")
    reply = thread.locator("leaf-text")
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", existing_reply or words)
    if existing_reply:
        page.keyboard.press("Escape")
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(page.locator(".lf-fab-input")).to_be_focused()
        expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)
    else:
        page.keyboard.press("Escape")
        page.keyboard.press("g")
        page.keyboard.press("i")
        reply = page.locator("leaf-text[name=reply]:focus")
        expect(reply).to_be_focused()
        expect(reply).to_have_js_property("value", words)
        expect(reply).to_have_js_property("selectionStart", 1)
        with sending(page, "carried reply"):
            page.keyboard.press("Enter")
        replies = [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "reply"
        ]
        assert [event["text"] for event in replies] == [words]


@pytest.mark.parametrize("surface", ["panel", "margin"])
@pytest.mark.parametrize("answer", ["accepted", "refused"])
def test_reply_admission_finishes_or_restores_its_native_session(
    browser, serve, one_user, surface, answer
):
    """A provisional send keeps the editor owed a refusal; acceptance finishes editing.

    Refusal returns words to the agent-resolved thread and retries the same attempt.
    After acceptance, another tab's words remain saved without activating this editor.
    """
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url, context=one_user)
    if surface == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        card = page.locator(f'.lf-thread[data-id="{root}"]')
        card.locator(".lf-thread-summary").focus()
    else:
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
        page.keyboard.press("c")
    field = card.locator("leaf-text")
    words = "This reply still belongs to the resolved thread."
    write(field, words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    expect(field).to_be_focused()
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the provisional reply")
    attempt = held[0].request.post_data_json["attempt"]
    expect(field).to_have_js_property("value", "")
    expect(card).to_have_attribute("data-resolved", "false")
    if answer == "accepted":
        held.pop().continue_()
    else:
        held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    page.unroute("**/api/event")
    round_trip(page)
    rendered(page)
    if answer == "refused":
        expect(card).to_be_visible()
        expect(card).to_have_attribute("data-resolved", "true")
        expect(field).to_be_visible()
        expect(field).to_have_js_property("value", words)
        assert stored_draft_text(page, "reply:" + root) == words
        with sending(page, "the same reply after refusal"):
            field.focus()
            page.keyboard.press("ControlOrMeta+Enter")
        reply = events_model.read_events(serve.page_dir)[-1]
        assert (reply["kind"], reply["parent"], reply["text"], reply["attempt"]) == (
            "reply",
            root,
            words,
            attempt,
        )
        return
    expect(field).to_have_js_property("value", "")
    second = open_page(browser, url, context=one_user)
    if second.locator(".lf-threads-toggle").get_attribute("aria-expanded") != "true":
        second.locator(".lf-threads-toggle").click()
    panel_settled(second)
    other = second.locator(f'.lf-thread[data-id="{root}"]')
    other.locator(".lf-thread-summary").focus()
    next_words = "A saved reply written in the other tab."
    write(other.locator("leaf-text"), next_words)
    expect(field).to_have_js_property("value", next_words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    rendered(page)
    expect(field).to_be_hidden()
    assert stored_draft_text(page, "reply:" + root) == next_words


@pytest.mark.parametrize("surface", ["panel", "margin"])
@pytest.mark.parametrize("resolution", ["user", "active-agent", "inactive-agent"])
def test_reply_editing_and_saved_words_have_separate_resolution_lifetimes(
    browser, serve, surface, resolution
):
    """Only an external settlement interrupting active editing retains the editor.

    Deliberate Resolve and reload close it. Every path preserves the words for an
    explicit Reopen, while an interrupted writer retains the native caret.
    """
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url)
    if surface == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root["id"]}"]')
        thread.locator(".lf-thread-summary").click()
    else:
        page.keyboard.press("t")
        thread = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-thread="{root["id"]}"]'
        )
        page.keyboard.press("c")
    field = thread.locator("leaf-text")
    words = "An unfinished thought about this thread."
    write(field, words)
    field.evaluate("box => box.setSelectionRange(5, 5)")
    if resolution == "user":
        with sending(page, "the deliberate resolution"):
            thread.locator(".lf-resolve").click()
    else:
        if resolution == "inactive-agent":
            page.keyboard.press("Escape")
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "resolve",
                "author": "agent",
                "agent": "Codex",
                "parent": root["id"],
            },
        )
        told(page)
    if resolution == "active-agent":
        expect(field).to_be_visible()
        expect(field).to_be_focused()
        expect(field).to_have_js_property("value", words)
        assert field.evaluate("box => [box.selectionStart, box.selectionEnd]") == [5, 5]
        page.keyboard.press("Escape")
        expect(field).not_to_be_visible()
    else:
        expect(thread.locator("leaf-text")).not_to_be_visible()
    assert stored_draft_text(page, f"reply:{root['id']}") == words

    page.reload()
    wait_until_ready(page)
    if surface == "margin":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    recovered = page.locator(f'.lf-threads > .lf-thread[data-id="{root["id"]}"]')
    recovered.locator(".lf-thread-summary").click()
    expect(recovered.locator("leaf-text")).to_have_count(0)
    with sending(page, "reopen with the saved reply"):
        recovered.locator(".lf-reopen").click()
    expect(recovered.locator("leaf-text")).to_be_focused()
    expect(recovered.locator("leaf-text")).to_have_js_property("value", words)


@pytest.mark.parametrize("surface", ["panel", "margin"])
@pytest.mark.parametrize("continuation", ["send", "dismiss"])
def test_a_resolved_reply_composition_stays_open_until_deliberately_dismissed(
    browser, serve, surface, continuation
):
    """Tab preserves the composition; Send or a deliberate press elsewhere ends it."""
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url)
    if surface == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root["id"]}"]')
        thread.locator(".lf-thread-summary").click()
    else:
        page.keyboard.press("t")
        thread = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-thread="{root["id"]}"]'
        )
        page.keyboard.press("c")
    words = "I still need to send this reply."
    write(thread.locator("leaf-text"), words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root["id"]},
    )
    told(page)
    page.keyboard.press("Tab")
    send = thread.get_by_role("button", name="Send", exact=True)
    expect(send).to_be_focused()
    rendered(page)
    expect(send).to_be_visible()
    expect(thread.locator("leaf-text")).to_have_js_property("value", words)
    if continuation == "send":
        with sending(page, "the retained reply"):
            page.keyboard.press("Enter")
        replies = [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "reply"
        ]
        assert [(event["parent"], event["text"]) for event in replies] == [
            (root["id"], words)
        ]
    else:
        page.keyboard.press("Tab")
        rendered(page)
        expect(thread.locator("leaf-text")).to_be_visible()
        page.locator("#p3").click(position={"x": 10, "y": 10})
        expect(thread.locator("leaf-text")).not_to_be_visible()
        if surface == "margin":
            expect(page.locator('[data-lf-margin-for="p3"]')).to_have_count(0)
        assert stored_draft_text(page, f"reply:{root['id']}") == words


@pytest.mark.parametrize("resolved", [False, True])
def test_send_follows_a_reply_composition_whose_diff_outlet_disappears(
    browser, serve, resolved
):
    """A replaced patch carries the same Send control to the thread's margin card."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><p id="p3">',
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can this line return a different value?",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    page = open_page(browser, url)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    words = "I still need to send my answer about that line."
    write(inline.locator("leaf-text"), words)
    if resolved:
        events_model.append_event(
            serve.page_dir,
            {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
        )
        told(page)
    page.keyboard.press("Tab")
    expect(inline.get_by_role("button", name="Send", exact=True)).to_be_focused()
    rendered(page)
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    expect(inline).to_have_count(0)
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    expect(card.get_by_role("button", name="Send", exact=True)).to_be_focused()
    expect(card.locator("leaf-text")).to_have_js_property("value", words)
    with sending(page, "the reply after its Send moved"):
        page.keyboard.press("Enter")
    reply = events_model.read_events(serve.page_dir)[-1]
    assert (reply["kind"], reply["parent"], reply["text"]) == ("reply", root, words)


@pytest.mark.parametrize("resolved", [False, True])
def test_tab_browsing_keeps_a_reply_when_its_diff_outlet_is_replaced(
    browser, serve, resolved
):
    """External source replacement carries editing without reversing native Tab."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><a id="after-diff" href="#p3">After the diff</a><p id="p3">',
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can this line return a different value?",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    page = open_page(browser, url)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    words = "I still need to send my answer about that line."
    write(inline.locator("leaf-text"), words)
    if resolved:
        events_model.append_event(
            serve.page_dir,
            {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
        )
        told(page)
    page.keyboard.press("Tab")
    expect(inline.get_by_role("button", name="Send", exact=True)).to_be_focused()
    rendered(page)
    after = page.locator("#after-diff")
    for _ in range(20):
        page.keyboard.press("Tab")
        if after.evaluate('node => node.matches(":focus")'):
            break
    expect(after).to_be_focused()
    rendered(page)
    expect(inline.locator("leaf-text")).to_be_visible()
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    expect(page.locator("lf-diff").get_by_text("new = 1", exact=True)).to_be_visible()
    expect(inline).to_have_count(0)
    expect(after).to_be_focused()
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    expect(card.locator("leaf-text")).to_be_visible()
    expect(card.locator("leaf-text")).to_have_js_property("value", words)


@pytest.mark.parametrize("resolved", [False, True])
def test_tab_browsing_continues_a_displaced_reply_without_an_annotation_overlay(
    browser, serve, resolved
):
    """Native Tab during core continuation preserves its caret and newer authored focus."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><a id="after-diff" href="#p3">After the diff</a><a id="second-link" href="#p3">Second link</a><p id="p3">',
    )
    source = source.replace("<body>", '<body data-annotations="page">', 1)
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can this line return a different value?",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    page = open_page(browser, url)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    page.keyboard.press("t")
    page.keyboard.press("c")
    words = "I still need to send my answer about that line."
    write(inline.locator("leaf-text"), words)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    if resolved:
        events_model.append_event(
            serve.page_dir,
            {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
        )
        told(page)
    page.keyboard.press("Tab")
    expect(inline.get_by_role("button", name="Send", exact=True)).to_be_focused()
    rendered(page)
    after = page.locator("#after-diff")
    for _ in range(20):
        page.keyboard.press("Tab")
        if after.evaluate('node => node.matches(":focus")'):
            break
    expect(after).to_be_focused()
    rendered(page)
    expect(inline.locator("leaf-text")).to_be_visible()
    # Hold the actual panel presentation, after its route was chosen. Tab is a
    # newer standing intent while the same native editing generation remains alive.
    page.evaluate(
        """() => {
          const list = document.querySelector('.lf-threads');
          const present = list.present.bind(list);
          const held = Promise.withResolvers();
          list.present = model => {
            if (!document.querySelector('.lf-thread-panel').open) return present(model);
            window.replyContinuationHeld = true;
            return held.promise.then(() => present(model));
          };
          window.releaseReplyContinuation = () => {
            list.present = present;
            held.resolve();
          };
        }"""
    )
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    page.wait_for_function("window.replyContinuationHeld === true")
    expect(after).to_be_focused()
    page.keyboard.press("Tab")
    second = page.locator("#second-link")
    expect(second).to_be_focused()
    page.evaluate("releaseReplyContinuation()")
    wait_until_ready(page)
    expect(page.locator("lf-diff").get_by_text("new = 1", exact=True)).to_be_visible()
    expect(inline).to_have_count(0)
    expect(second).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_have_count(0)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card.locator("leaf-text")).to_be_visible()
    expect(card.locator("leaf-text")).to_have_js_property("value", words)

    assert card.locator("leaf-text").evaluate(
        "node => [node.selectionStart,node.selectionEnd]"
    ) == [1, 1]
    card.locator("leaf-text").focus()
    with sending(page, "the continued reply in Threads"):
        page.keyboard.press("Enter")
    reply = events_model.read_events(serve.page_dir)[-1]
    assert (reply["kind"], reply["parent"], reply["text"]) == ("reply", root, words)


@pytest.mark.parametrize("leave", ["send", "escape"])
def test_replaced_reply_compositions_keep_their_carets_and_leave_commands(
    browser, serve, leave
):
    """One selected card can carry several native sessions without merging their exits.

    Both agent-resolved replies retain their words and carets through source replacement.
    Existing disclosure selects each; Send and Escape dismiss only the addressed one.
    """
    patch = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n-old = 1\n+new = 1\n-old = 2\n+new = 2\n"
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><a id="after-diff" href="#p3">After the diff</a><p id="p3">',
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    roots = [
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"Please review line {line}.",
                "anchor": {
                    "section": "patch",
                    "datum": f'["app.py","new",{line}]',
                    "source": "review-patch",
                    "source_revision": source_revision(serve.page_dir, "review-patch"),
                },
            },
        )["id"]
        for line in (1, 2)
    ]
    page = open_page(browser, url)
    inputs = [
        page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"] leaf-text')
        for root in roots
    ]
    words = ["My unfinished first answer.", "My unfinished second answer."]
    write(inputs[0], words[0])
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Tab")
    write(inputs[1], words[1])
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    after = page.locator("#after-diff")
    for _ in range(20):
        page.keyboard.press("Tab")
        if after.evaluate('node => node.matches(":focus")'):
            break
    expect(after).to_be_focused()
    for root in roots:
        events_model.append_event(
            serve.page_dir,
            {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
        )
    told(page)
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 9\n+new = 9\n"
    )
    told(page)
    expect(after).to_be_focused()
    # One margin card remains the current selection. The other native session keeps
    # its caret until the user selects its next route; a hidden mirror is not that route.
    page.evaluate("() => window.lfWordsJudged()")
    consume_browser_errors(
        page,
        'typed words left the screen without a key or press: "My unfinished first answer."',
    )
    for root, word in zip(roots, words):
        box = page.locator(f'.lf-thread[data-id="{root}"] leaf-text')
        expect(box).to_have_js_property("value", word)
    current = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{roots[1]}"] leaf-text'
    )
    assert current.evaluate("node => [node.selectionStart,node.selectionEnd]") == [2, 2]
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    first = page.locator(f'.lf-thread[data-id="{roots[0]}"]')
    first.locator(".lf-thread-summary").focus()
    expect(first.locator("leaf-text")).to_be_visible()
    expect(first.locator("leaf-text")).to_have_js_property("value", words[0])

    for index, (root, word) in enumerate(zip(roots, words), 1):
        card = page.locator(f'.lf-thread[data-id="{root}"]')
        card.locator(".lf-thread-summary").focus()
        page.keyboard.press("c")
        expect(card.locator("leaf-text")).to_be_focused()
        assert card.locator("leaf-text").evaluate(
            "node => [node.selectionStart,node.selectionEnd]"
        ) == [index, index]
        if index == 1 and leave == "escape":
            page.keyboard.press("Escape")
            expect(card.locator("leaf-text")).to_have_count(0)
            assert stored_draft_text(page, "reply:" + root) == word
            continue
        with sending(page, "the retained composition selected in Threads"):
            page.keyboard.press("Enter")
        reply = events_model.read_events(serve.page_dir)[-1]
        assert (reply["kind"], reply["parent"], reply["text"]) == ("reply", root, word)


@pytest.mark.parametrize("destination", ["passage", "reply"])
def test_a_transfer_keeps_its_persisted_source_when_the_destination_write_fails(
    browser, serve, destination
):
    """A failed larger destination write cannot be followed by a smaller tombstone."""
    page = open_page(browser, serve(LONG_PAGE, anchored=[("p41", "Paragraph 41.")]))
    words = "The only persisted copy must survive the transfer and reload."
    choose_comment_target(page, "#p3")
    write(page.locator(".lf-fab-input"), words)
    page.evaluate(
        """prefix => {
          const set = Storage.prototype.setItem;
          window.lfRefusedTransferWrites = 0;
          Storage.prototype.setItem = function (key, value) {
            if (key.startsWith(prefix) && !JSON.parse(value).settled) {
              window.lfRefusedTransferWrites++;
              throw new DOMException('full', 'QuotaExceededError');
            }
            return set.call(this, key, value);
          };
        }""",
        draft_key(page, ""),
    )
    if destination == "passage":
        page.keyboard.press("Escape")
        choose_comment_target(page, "#p9")
        field = page.locator(".lf-fab-input")
    else:
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("t")
        page.keyboard.press("c")
        field = page.locator(".lf-margin-preview .lf-page-thread leaf-text")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    assert page.evaluate("() => window.lfRefusedTransferWrites") > 0

    page.reload()
    wait_until_ready(page)
    page.keyboard.press("Escape")
    choose_comment_target(page, "#p3")
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)


def test_an_explicit_target_does_not_overwrite_its_existing_draft(
    browser, serve, one_user
):
    """A deliberate retarget carries words only into an empty passage.

    Two passages may already hold independent work. Choosing the second from the first
    tab should therefore reopen the draft at the chosen destination and leave the source
    draft where it was, rather than tombstoning the source and replacing the destination.
    The target picker is the real explicit gesture whose carry path owns that choice.
    """
    url = serve(LONG_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)

    source = "This paragraph buries the point."
    destination = "This later paragraph already has its own note."
    choose_comment_target(first, "#p3")
    write(first.locator(".lf-fab-input"), source)
    choose_comment_target(second, "#p9")
    write(second.locator(".lf-fab-input"), destination)

    first.keyboard.press("Escape")
    expect(first.locator(".lf-composer")).to_be_hidden()
    choose_comment_target(first, "#p9")
    expect(first.locator(".lf-fab-input")).to_have_js_property("value", destination)

    first.keyboard.press("Escape")
    choose_comment_target(first, "#p3")
    expect(first.locator(".lf-fab-input")).to_have_js_property("value", source)


def test_an_explicit_target_carries_into_an_emptied_draft(browser, serve):
    """A cleared destination record holds no work that should outrank a carried draft."""
    page = open_page(browser, serve(LONG_PAGE))
    field = page.locator(".lf-fab-input")

    choose_comment_target(page, "#p9")
    write(field, "Words the user removes.")
    write(field, "")
    page.keyboard.press("Escape")

    source = "Words to carry to the later paragraph."
    choose_comment_target(page, "#p3")
    write(field, source)
    page.keyboard.press("Escape")
    choose_comment_target(page, "#p9")
    expect(field).to_have_js_property("value", source)


def test_a_composer_on_one_passage_is_one_box_in_every_tab(browser, serve, one_user):
    """The composer is a box and a piece of chrome at once, so a second tab owes it
    more than the words. An emptied box is a box the user is still holding open and
    must stay up; a settled one has nothing left to be open about and goes down, or the
    other tab is left offering to send words the log already carries.

    The mirrored value is read for its height as well, because a box that took another
    tab's words and did not grow to them is one whose text is out of sight — the shape
    of bug a script sizing the box on `input` alone would reintroduce.

    Read in a window whose margin holds the bar beside the passage, so both tabs size
    one box in one place."""
    url = serve(LONG_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    for tab in (first, second):
        resized(tab, 1440, 900)

    height = "ta => Math.round(ta.getBoundingClientRect().height)"
    compose(first, "#p3")
    compact_height = first.locator(".lf-composer leaf-text").evaluate(height)
    opened = "This paragraph buries the point."
    write(first.locator(".lf-composer leaf-text"), opened)
    compose(second, "#p3")
    expect(second.locator(".lf-composer leaf-text")).to_have_js_property(
        "value", opened
    )

    grown = opened + "\n\n" + "And the one after it says the same thing again. " * 4
    write(first.locator(".lf-composer leaf-text"), grown)
    expect(second.locator(".lf-composer leaf-text")).to_have_js_property("value", grown)
    assert first.locator(".lf-composer leaf-text").evaluate(height) > compact_height
    assert second.locator(".lf-composer leaf-text").evaluate(height) == first.locator(
        ".lf-composer leaf-text"
    ).evaluate(height), (
        "a box grown from another tab's keystrokes must be laid out like a typed one"
    )

    # Emptying is an edit and not a settlement: the box stays up, holding nothing.
    write(first.locator(".lf-composer leaf-text"), "")
    expect(second.locator(".lf-composer leaf-text")).to_have_js_property("value", "")
    expect(second.locator(".lf-composer")).to_be_visible()
    assert second.locator(".lf-composer leaf-text").evaluate(height) == compact_height

    sent = "The point is buried, and the paragraph after it repeats it."
    write(first.locator(".lf-composer leaf-text"), sent)
    first.keyboard.press("ControlOrMeta+Enter")
    round_trip(first)
    expect(second.locator(".lf-composer")).to_be_hidden()
    said = [
        e["text"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    assert said == [sent], "one box, and so one comment however many tabs showed it"


def test_text_alignment_is_lossless_and_keeps_a_shared_spine(browser, serve):
    """The draft renderer is allowed to choose where an ambiguous repeated word
    aligns, but never to lose or invent a character. The two projections are the
    contract: same+delete is the old text, same+insert the new one. Unicode,
    whitespace and repetition are where a character or regex diff quietly breaks.

    Both granularities, because the unit is the caller's and the contract is not: a
    draft's history aligns by word, while an inline version comparison starts with
    sentences and refines a local edit by word. Neither may drop or invent a character."""
    page = open_page(browser, serve(JOURNEY_V1))
    cases = [
        ("", ""),
        ("one line", "one longer line"),
        ("first\nsecond  line", "first\nsecond line\nthird"),
        ("l’écran est prêt 😀", "l’écran était prêt 🟢"),
        ("迁移完成。再次迁移。", "迁移完成。回滚完成。"),
        ("Retry once. Retry once. Then stop.", "Retry once. Retry twice. Then stop."),
        (
            "shared " + " ".join(f"old-{i}" for i in range(2500)) + " ending",
            "shared " + " ".join(f"new-{i}" for i in range(2500)) + " ending",
        ),
    ]
    aligned, by_sentence, inline = page.evaluate(
        """async (pairs) => {
          const {alignInlineText, alignText, sentenceUnits} =
            await window.__lfRuntimeImport('/runtime/text-alignment.js');
          return [
            pairs.map(([before, after]) => alignText(before, after)),
            pairs.map(([before, after]) => alignText(before, after, sentenceUnits)),
            pairs.map(([before, after]) => alignInlineText(before, after)),
          ];
        }""",
        cases,
    )
    for unit, walked in (
        ("word", aligned),
        ("sentence", by_sentence),
        ("inline", inline),
    ):
        for (before, after), runs in zip(cases, walked):
            joined = "".join(run["text"] for run in runs if run["kind"] != "insert")
            assert joined == before, (unit, joined, before)
            joined = "".join(run["text"] for run in runs if run["kind"] != "delete")
            assert joined == after, (unit, joined, after)
            assert all(a["kind"] != b["kind"] for a, b in itertools.pairwise(runs)), (
                unit
            )

    repeated = aligned[-2]
    assert "".join(r["text"] for r in repeated if r["kind"] == "delete") == "once"
    assert "".join(r["text"] for r in repeated if r["kind"] == "insert") == "twice"
    assert "Then stop." in "".join(r["text"] for r in repeated if r["kind"] == "same")
    assert [run["kind"] for run in aligned[-1]] == ["same", "delete", "insert", "same"]

    local = page.evaluate(
        """async () => {
          const {alignInlineText} = await window.__lfRuntimeImport('/runtime/text-alignment.js');
          return alignInlineText(
            'Each section names a feature and provides a live example.',
            'Each section names a feature and provides a live example, including focused replays of its motion.'
          );
        }"""
    )
    assert "".join(run["text"] for run in local if run["kind"] == "delete") == ""
    assert "".join(run["text"] for run in local if run["kind"] == "insert") == (
        ", including focused replays of its motion"
    )


def test_a_draft_explains_its_change_and_restores_history_as_an_edit(browser, serve):
    """One disclosure answers both deferred draft decisions. It compares this version's
    authored body with the standing body, retains every absolute edit in log order,
    and walks back by posting another ordinary edit. A second tab proves restore is
    durable replay rather than local history state; copy mode proves the local history
    does not survive without its handlers."""
    url = serve(JOURNEY_V1)
    page = open_page(browser, url)
    draft = page.locator("#draft-ops")
    edits = [
        "Run the migration before deploying. It takes one minute.",
        "Run the migration after the backup. It takes two minutes.",
    ]
    for index, text in enumerate(edits, 1):
        draft.locator(".lf-draft-body").dblclick()
        write(draft.locator("leaf-text"), text)
        draft_control(page, "save", "draft-ops").click()
        round_trip(page)  # the history is drawn from the log, not the box
        expect(draft.locator(".lf-draft-history > summary")).to_have_text(
            f"Changes · {index} {'edit' if index == 1 else 'edits'}"
        )

    # The disclosure is the platform's to work and the register says so, naming the
    # press where the user is standing on it and reading which way it goes off the
    # state they can already see.
    history = draft.locator(".lf-draft-history > summary")
    history.focus()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("show the history")
    history.click()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("hide the history")

    current_deleted = "".join(draft.locator(".lf-draft-current del").all_inner_texts())
    current_inserted = "".join(draft.locator(".lf-draft-current ins").all_inner_texts())
    assert "before" in current_deleted and "deploying" in current_deleted
    assert "afterthebackup" in re.sub(r"\s+", "", current_inserted)
    labels = draft.locator(".lf-draft-revision-head strong").all_inner_texts()
    assert labels == ["Version text", "Edit 1 · v1", "Edit 2 · v1"]
    # Adjacent recorded edits are aligned too, rather than rendered as two unrelated
    # snapshots. The first has no knowable predecessor on a later pinned version.
    second_delta = draft.locator(".lf-draft-revisions > li").nth(2)
    second_deleted = "".join(second_delta.locator("del").all_inner_texts())
    second_inserted = "".join(second_delta.locator("ins").all_inner_texts())
    assert "before" in second_deleted and "deploying" in second_deleted
    assert "afterthebackup" in re.sub(r"\s+", "", second_inserted)

    draft.get_by_role("button", name="Restore edit 1 · v1").focus()
    page.keyboard.press("Enter")
    round_trip(page)
    expect(draft.locator(".lf-draft-body")).to_have_text(edits[0])
    expect(draft.locator(".lf-draft-history > summary")).to_have_text(
        "Changes · 3 edits"
    )
    expect(draft.locator(".lf-draft-history > summary")).to_be_focused()
    expect(draft).to_have_attribute("data-lf-user-override", "1")

    events = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["text"] for event in events] == [
        edits[0],
        edits[1],
        edits[0],
    ]
    assert [event["action"] for event in events] == ["edit", "edit", "edit"]

    sequence = page.evaluate(
        """async () => {
          const {widgetController} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const widget = document.getElementById('draft-ops');
          const controller = widgetController(widget);
          const first = controller.read().actions.edit.history;
          first[0].detail.text = 'A widget must not mutate the runtime log.';
          return controller.read().actions.edit.history
            .map(event => [event.seq, event.detail.text]);
        }"""
    )
    assert [text for _, text in sequence] == [edits[0], edits[1], edits[0]]
    assert [seq for seq, _ in sequence] == sorted(seq for seq, _ in sequence)

    # The handover URL, since the key it carries has left this tab's address.
    other = open_page(browser, url)
    expect(other.locator("#draft-ops .lf-draft-body")).to_have_text(edits[0])
    expect(other.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 3 edits"
    )


def test_action_history_is_bounded_by_the_pinned_version(browser, serve):
    """A historical page cannot narrate an edit that had not happened yet. The
    helper owns the same version boundary replay does, so every future widget that
    consumes a sequence gets this right without copying the filter."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    for version, text in ((1, "First recorded body."), (2, "Second recorded body.")):
        if version == 2:
            stamp_page(d, JOURNEY_V2, "v2")
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": version,
                "widget": "draft-ops",
                "action": "edit",
                "detail": {"text": text},
            },
        )

    old = open_page(browser, url, pin=True)
    expect(old.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 1 edit"
    )
    old_sequence = old.evaluate(
        """async () => (await window.__lfRuntimeImport('/runtime/widget-api.js'))
          .widgetController(document.getElementById('draft-ops')).read().actions.edit.history
          .map(event => event.revision)"""
    )
    assert old_sequence == [1]

    latest = open_page(browser, url.replace("v1.html", "v2.html"), pin=True)
    expect(latest.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 2 edits"
    )
    latest_sequence = latest.evaluate(
        """async () => (await window.__lfRuntimeImport('/runtime/widget-api.js'))
          .widgetController(document.getElementById('draft-ops')).read().actions.edit.history
          .map(event => event.revision)"""
    )
    assert latest_sequence == [1, 2]


def test_an_acknowledged_decision_still_survives_the_next_version(browser, serve):
    """The round trip above, differing in one fact: the agent has acknowledged the
    actions before v2 publishes. That is the ordinary case — the agent writes a
    version *because* it was handed the user's edits — and it used to be the
    one that lost them: replay stopped at the handoff cursor, on the premise
    that a version written after seeing an action encodes it. Nothing checks that
    premise, so a version that quietly omits the state re-emitted the widget as
    untouched and the user's work vanished with no error anywhere.

    Acknowledgement is not assent. Only the next version's markup can say what the
    agent did with an edit, and until it says otherwise the log is what the user
    did."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "board",
            "action": "move",
            "detail": {"card": "card-x", "to": "col-done", "rank": "0i"},
        },
    )
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"text": DRAFT_EDITED},
        },
    )
    # The highest user event reached context, so everything so far is ours to answer.
    with service_model.PageTransaction(d) as transaction:
        batch = {"events": transaction.events}
        with delivery_model.receive_batch(
            transaction, batch, session_id=None
        ) as events:
            delivery_model.record_pickup(transaction, events)
    # And the agent answers with a version that carries neither — the page generator
    # emitting its own idea of the board and the draft, as one did for five
    # versions running.
    stamp_page(d, JOURNEY_V2, "v2")

    page = open_page(browser, url.replace("v1.html", "v2.html"))
    page.wait_for_function(
        "t => document.querySelector('#draft-ops .lf-draft-body').textContent === t",
        arg=DRAFT_EDITED,
    )
    expect(page.locator("#col-done #card-x")).to_have_count(1)


def test_a_comment_written_on_an_edited_draft_lands_on_their_words(browser, serve):
    """`leaf thread open` reads the mapped revision plus the log; the user's tab reads
    the DOM replay builds from the same two. An edited draft is where those readings
    used to drift — the file holds words the page stopped showing — so write the anchor
    blind, on the user's own words, and prove the page paints it. The words the edit
    replaced are refused at the CLI, naming the edit, because posted they would detach
    in front of the user."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"text": DRAFT_EDITED},
        },
    )
    refused = CliRunner().invoke(
        cli_model.cli,
        ["thread", "open", str(d), "--quote", "It is online.", "--text", "x"],
    )
    assert refused.exit_code != 0 and "rewrote § draft-ops" in refused.output
    written = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "open",
            str(d),
            "--quote",
            "It takes about a minute.",
            "--text",
            "Measured where?",
        ],
        catch_exceptions=False,
    )
    assert written.exit_code == 0, written.output

    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    thread = page.locator(".lf-thread .lf-quote").first
    expect(thread).not_to_have_class(re.compile(r"\bdetached\b"))
    assert painted(page, "lf-mark") == "It takes about a minute."


def test_registered_control_keys_activate_once(browser, serve):
    """A native draft button activates without a Leaf binding. The selectable option
    mark is the explicit exception and owns its Space row.

    Activation happens once per press however long the key is held. A keydown listener
    hears repeats, and a mark that toggles per repeat posts a `choose` for each one. Repeats
    are dispatched rather than driven because no automation holds a key down; the browser
    delivers this event with `repeat` set."""
    page = open_page(browser, serve(KEYS_PAGE))

    pencil = draft_control(page, "edit", "draft-ops")
    assert pencil.evaluate("el => el.localName") == "button"
    expect(pencil).to_have_attribute("type", "button")
    pencil.focus()
    page.keyboard.press("Enter")
    editor = page.locator("#draft-ops leaf-text")
    expect(editor).to_be_focused()
    focus_paint = page.locator("#draft-ops").evaluate(
        """host => {
          const editor = host.querySelector('leaf-text');
          const hs = getComputedStyle(host), es = getComputedStyle(editor);
          return {
            host: {outline: hs.outlineStyle, width: parseFloat(hs.outlineWidth)},
            editor: {outline: es.outlineStyle, shadow: es.boxShadow,
                     ring: es.getPropertyValue('--lf-focus-ring').trim()},
          };
        }"""
    )
    assert focus_paint["host"]["outline"] != "none"
    assert focus_paint["host"]["width"] >= 2
    assert focus_paint["editor"] == {
        "outline": "none",
        "shadow": "none",
        "ring": "none",
    }, "the draft's one editing surface acquired a second focus box"
    page.emulate_media(forced_colors="active")
    forced = page.locator("#draft-ops").evaluate(
        """host => {
          const editor = host.querySelector('leaf-text');
          return {
            host: getComputedStyle(host).outlineStyle,
            editor: getComputedStyle(editor).outlineStyle,
          };
        }"""
    )
    assert forced == {"host": "solid", "editor": "none"}
    page.emulate_media(forced_colors="none")
    page.keyboard.press("Escape")

    mark = page.locator("#opts .lf-pick").first
    mark.focus()
    page.keyboard.press(" ")
    expect(page.locator("#opts > lf-option[chosen]")).to_have_count(1)
    chosen = page.locator("#opts > lf-option[chosen]").get_attribute("id")
    mark.evaluate("""el => {
        for (let i = 0; i < 5; i++)
            el.dispatchEvent(new KeyboardEvent('keydown',
                {key: ' ', repeat: true, bubbles: true, cancelable: true}));
    }""")
    expect(page.locator(f"#{chosen}[chosen]")).to_have_count(1)
    # The mark paints its own press before the post answers, so the DOM leads the log:
    # read the file straight after and the first press's event may not be in it yet,
    # which reads exactly like a press that sent nothing. A press that sent nothing
    # satisfies this too, which is what makes it the right wait for both assertions —
    # the repeats below must add none of their own.
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)
    assert [e for e in sent if e.get("action") == "choose"] != [], (
        "the first press sent nothing, so the repeats below had nothing to duplicate"
    )
    assert len([e for e in sent if e.get("action") == "choose"]) == 1, (
        "a held key sent one decision per repeat"
    )


def test_global_shortcuts_leave_other_browser_navigation_keys_alone(browser, serve):
    """The document-level dispatcher owns a few character key shortcuts, not the
    keyboard. Space, arrows, Home/End, and PageUp/PageDown must still reach the browser
    when focus is in the authored page
    rather than a widget control.

    Observe `defaultPrevented` on real key events instead of asserting that Chrome
    happened to scroll: scrolling depends on viewport and focus geometry, while
    canceling the event is the runtime decision under test. `?` is the positive
    control proving this observer sees a key the dispatcher intentionally consumes."""
    page = open_page(browser, serve(KEYS_PAGE))
    keys = [
        " ",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        "?",
    ]
    page.evaluate(
        """keys => {
          const pageContent = document.querySelector("main");
          pageContent.tabIndex = -1;
          pageContent.focus();
          window.lfObservedKeys = {};
          document.addEventListener("keydown", event => {
            if (keys.includes(event.key))
              window.lfObservedKeys[event.key] = event.defaultPrevented;
          });
        }""",
        keys,
    )
    for key in keys:
        page.keyboard.press(key)

    observed = page.evaluate("() => window.lfObservedKeys")
    assert observed.pop("?") is True, (
        "the positive-control shortcut was not consumed, so the probe did not "
        "observe the runtime dispatcher"
    )
    assert observed == dict.fromkeys(keys[:-1], False)


def test_the_browser_pages_the_document_with_space(browser, serve):
    """Space and Shift+Space are ordinary browser paging keys on authored content.

    Leaf does not prescribe a distance or animation. The browser chooses both; the
    contract here is simply that the document moves down and then back up without the
    runtime canceling either key."""
    page = open_page(browser, serve(SMOOTH_LONG_PAGE))
    page.evaluate(RELEASE_FOCUS)

    def press_and_settle(key):
        page.evaluate("""() => {
          window.__lfScrollEnded = false;
          addEventListener('scrollend', () => { window.__lfScrollEnded = true; },
                           {once: true});
        }""")
        page.keyboard.press(key)
        page.wait_for_function("() => window.__lfScrollEnded")
        return page.evaluate("() => document.scrollingElement.scrollTop")

    down = press_and_settle("Space")
    assert down > 0, "the browser did not page the document down"
    up = press_and_settle("Shift+Space")
    assert up < down, "the browser did not page the document back up"


@pytest.mark.parametrize(("down", "up"), [("d", "u"), ("j", "k")])
def test_the_reading_keys_accumulate_and_reverse(browser, serve, down, up):
    """d/u move 60% of the visible page; j/k take small steps through the same glide.
    The page sets scroll-behavior: smooth on the box, as an authored page may —
    a step whose writes ride that rule instead of stating `instant` never lands.

    Every phase waits on its destination, never on scrollend or a timer: the glide
    writes a frame at a time and Chrome answers each write with a scrollend, so
    "scrolling ended" is a fact about a frame, while the destination is the one
    position a glide approaching it never passes through early. A wrong step then
    reads as the wrong number, which says what happened.

    The second press follows the first with no wait between them, landing inside the
    first glide, so presses have to add up from the goal rather than from wherever
    the glide has got to. Taking the box mid-glide — programmatically, because the
    cancel reads positions and any hand looks the same to it, and this one lands at
    a number the assertion can hold — must stand the step down: the next press
    measures from where the user left the box, not from the goal it dropped, and a
    glide that ignored the taking presses on to that goal and fails both reads.
    Pressing on at the foot moves nothing and banks nothing, so u from there
    is one step back."""
    page = open_page(browser, serve(SMOOTH_LONG_PAGE))
    step = (
        60
        if down == "j"
        else page.evaluate(
            "() => { const s = getComputedStyle(document.scrollingElement); return ("
            " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
            " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
        )
    )
    assert page.evaluate(
        "() => document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight * 3"
    ), "the page is too short for these steps to be told apart"
    # A callback's frame timestamp may predate performance.now() in the key handler.
    # Make that browser timing deterministic: a negative first fraction used to write
    # above the page, get clamped to zero, then cancel the glide as if the user moved.
    page.evaluate(
        """down => {
      const raf = requestAnimationFrame;
      let stale = false;
      addEventListener('keydown', event => {
        if (event.key === down) stale = true;
      }, {capture: true});
      window.requestAnimationFrame = callback => {
        const firstAfterPress = stale;
        stale = false;
        return raf(now => callback(firstAfterPress ? -1 : now));
      };
    }""",
        down,
    )

    def rests_at(act, expected):
        """Position after `act`, awaited at `expected` and handed to the assertion:
        the bounded wait consumes the arrival, and the assert is what speaks when
        the step went somewhere else instead."""
        act()
        try:
            page.wait_for_function(
                "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
                arg=expected,
                timeout=5000,
            )
        except PlaywrightTimeout:
            pass
        return page.evaluate("() => document.scrollingElement.scrollTop")

    assert rests_at(lambda: page.keyboard.press(down), step) == pytest.approx(
        step, abs=1
    )

    def twice():
        page.keyboard.down(down)
        page.keyboard.down(down)  # a held key emits a repeated keydown
        page.keyboard.up(down)

    assert rests_at(twice, step * 3) == pytest.approx(step * 3, abs=1), (
        "the second press measured from the glide in flight, so the two together "
        "moved less than their full distance"
    )
    assert rests_at(lambda: page.keyboard.press(up), step * 2) == pytest.approx(
        step * 2, abs=1
    )

    def taken():
        page.keyboard.press(down)
        page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 400, behavior: 'instant'})"
        )

    assert rests_at(taken, 400) == pytest.approx(400, abs=1), (
        "the glide pressed on to its goal after the user took the box"
    )
    assert rests_at(lambda: page.keyboard.press(down), 400 + step) == pytest.approx(
        400 + step, abs=1
    ), (
        "the press after the user took the box measured from the goal the taking "
        "had cancelled rather than from where they left it"
    )

    foot = page.evaluate(
        "() => document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight"
    )
    assert rests_at(
        lambda: page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 1e9, behavior: 'instant'})"
        ),
        foot,
    ) == pytest.approx(foot, abs=1)
    for _ in range(4):
        page.keyboard.press(down)  # nothing left to move, and nothing banked either
    assert rests_at(lambda: page.keyboard.press(up), foot - step) == pytest.approx(
        foot - step, abs=1
    ), (
        "presses at the foot of the page ran the destination past it, and reversing spent "
        "itself paying that back"
    )


def test_the_reading_page_step_never_paints_behind_where_it_started(browser, serve):
    """The step's own frames, read at real speed from the middle of the page where the
    box clamps nothing: d may not paint the page above where the press found it. A rAF
    tick carries its frame's own start, so a press handled inside a frame already under
    way is stamped after the tick it schedules, and an ease reading that as elapsed time
    walks back out through its own start (stepReading says the rest). At the ends of the box
    that write is one the box clamps, and what the clamp does to the press is a resting
    position the test above reads; in the middle every write lands, the glide arrives
    exactly where it promised, and the user is thrown up to most of a page the wrong
    way on the route — which no resting position can see.

    Whether a press loses that race is the platform's to say, so the window is stated
    rather than run for: a throttled CPU is a longer frame, and a longer frame is a wider
    gap between its start and the press dispatched inside it. Unfloored, this machine
    flicked on one press in ten at its own speed and on eight in ten throttled, where a
    floored clock flicks on none of either. The injection buys the record, not the wait,
    which is still the destination's."""
    page = open_page(browser, serve(SMOOTH_LONG_PAGE))
    page.context.new_cdp_session(page).send(
        "Emulation.setCPUThrottlingRate", {"rate": 20}
    )
    step = page.evaluate(
        "() => { const s = getComputedStyle(document.scrollingElement); return ("
        " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
        " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
    )
    start = round(step * 2)
    page.evaluate("""() => {
        window.lfFrames = [];
        const sample = () => {
            window.lfFrames.push(document.scrollingElement.scrollTop);
            requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
    }""")
    for _ in range(5):
        page.evaluate(
            "at => document.scrollingElement.scrollTo({top: at, behavior: 'instant'})",
            start,
        )
        page.wait_for_function(
            "at => document.scrollingElement.scrollTop === at", arg=start
        )
        page.evaluate("() => (window.lfFrames = [])")
        page.keyboard.press("d")
        page.wait_for_function(
            "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
            arg=start + step,
        )
        assert min(page.evaluate("() => window.lfFrames")) >= start - 1, (
            "the step painted the page above where the press found it"
        )


@pytest.mark.parametrize(("down", "up"), [("d", "u"), ("j", "k")])
def test_the_reading_keys_jump_under_reduced_motion(browser, serve, down, up):
    """Both reading distances jump immediately under reduced motion."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    page = open_page(browser, serve(SMOOTH_LONG_PAGE), context=context)
    step = (
        60
        if down == "j"
        else page.evaluate(
            "() => { const s = getComputedStyle(document.scrollingElement); return ("
            " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
            " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
        )
    )
    page.keyboard.press(down)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        step, abs=1
    ), "the step had not reached its destination when the press returned"
    page.keyboard.press(up)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        0, abs=1
    )


def test_the_reading_page_keys_move_the_region_the_user_is_scrolling(browser, serve):
    """Two scroll regions, so d has to pick the one the user is looking at. Beside the
    page the panel is a column of its own and the keys are the document's. Under the
    breakpoint the sheet covers the page and the page hands scrolling over with it — one
    gesture moves one region, and while the sheet is up that region is its thread list.
    A key is no different from a wheel there: a page scrolling behind the sheet shows
    the user nothing, so the key reads as dead, and the document is somewhere else
    when the sheet closes."""
    page = open_page(browser, serve(LONG_PAGE, comments=40))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # Put the user on the page before asking which reading region the page gesture chooses.
    page.evaluate(RELEASE_FOCUS)
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        " return t.scrollHeight > t.clientHeight; }"
    ), "the thread list does not overflow, so it could not be seen to scroll below"

    def offsets():
        return page.evaluate(
            "() => [document.scrollingElement.scrollTop,"
            " document.querySelector('.lf-threads').scrollTop]"
        )

    def press_down():
        """Both offsets once a region answers the press — the glide's first write is
        already the answer to which region moved, and movement is the fact waited on
        because movement is the question. Scrollend was the wait here while a press
        could die outright, which read as the platform withholding the event; it
        withholds nothing, answering the step's frame-at-a-time writes seven times to
        the press on Linux, and a press that moves no region states neither fact.
        Waiting on whichever region speaks makes the wrong one answering two numbers
        to compare rather than half a minute of silence and a timeout."""
        was = offsets()
        page.keyboard.press("d")
        page.wait_for_function(
            "w => { const t = document.querySelector('.lf-threads');"
            " return document.scrollingElement.scrollTop !== w[0] || t.scrollTop !== w[1]; }",
            arg=was,
        )
        return was, offsets()

    (page_was, threads_was), (page_now, threads_now) = press_down()
    assert threads_now == threads_was, "the panel took a key aimed at the document"
    assert page_now > page_was, "the document did not move for a key of its own"
    scroll_settled(page)

    resized(page, 400, 600)
    panel_settled(page)
    (page_was, threads_was), (page_now, threads_now) = press_down()
    assert page_now == page_was, (
        "the page moved behind the covering sheet, where the user cannot see it"
    )
    assert threads_now > threads_was, "the sheet did not move for the key it now owns"


def test_the_reading_page_keys_follow_the_user_into_the_panel(browser, serve):
    """Which region the keys move is where the user is standing, and covering is only
    one of the two ways they come to be standing in the list. Beside the page — the wide
    window, where the page beside the panel stays live — a user working down a long
    thread presses d and the page behind them steps instead, which is the same
    nothing the covering case was written to prevent: the region they are reading does
    not move, and the document is somewhere else when they look back at it.

    One factor separates the two halves here. The window, the layout, the panel and the
    list are the same at both presses; only where the focus stands changes. So the first
    press is the control that says the layout is beside — the user stands on the page,
    outside the panel, and the document is theirs to step — and the second is the subject.
    The Go-to sequence then supplies the neighboring
    contrast: focus changes which region d/u page through, but `g g` still names the
    document's edge while both regions have somewhere observable to move."""
    page = open_page(browser, serve(LONG_PAGE, comments=40))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.evaluate(RELEASE_FOCUS)
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        " return t.scrollHeight > t.clientHeight; }"
    ), "the thread list does not overflow, so it could not be seen to scroll below"

    def offsets():
        return page.evaluate(
            "() => [document.scrollingElement.scrollTop,"
            " document.querySelector('.lf-threads').scrollTop]"
        )

    # The control, and the wait that makes the subject's baseline a resting one: the
    # document's own step is a glide, and the position it is going to is the one place
    # it does not pass through early (the reading-page test says the rest).
    step = page.evaluate(
        "() => { const s = getComputedStyle(document.scrollingElement); return ("
        " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
        " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
    )
    page_was, threads_was = offsets()
    page.keyboard.press("d")
    page.wait_for_function(
        "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
        arg=step,
        timeout=5000,
    )
    page_now, threads_now = offsets()
    assert page_now > page_was, (
        "the document did not move for a key pressed from outside the panel, so the "
        "panel is not beside the page here and the case below is not the one named"
    )
    assert threads_now == threads_was, "the panel took a key aimed at the document"

    # Into the panel, standing on its open thread's title rather than in a box — `g T`'s
    # landing, which travels nothing, so the baseline below is the one the control left.
    # The address toggles the panel it names, so from the standing one the first
    # completion closes it and the second is the arrival.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(
        page.locator(
            ".lf-threads > .lf-thread:not([hidden])[open] > .lf-thread-summary"
        )
    ).to_be_focused()

    page_was, threads_was = offsets()
    page.keyboard.press("d")
    page.wait_for_function(
        "w => { const t = document.querySelector('.lf-threads');"
        " return document.scrollingElement.scrollTop !== w[0] || t.scrollTop !== w[1]; }",
        arg=[page_was, threads_was],
    )
    thread_step = page.locator(".lf-threads").evaluate(
        "t => { const s = getComputedStyle(t); return (t.clientHeight"
        " - parseFloat(s.scrollPaddingTop) - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
    )
    page.wait_for_function(
        "w => { const t = document.querySelector('.lf-threads');"
        " return Math.abs(t.scrollTop - w[0]) < 1"
        " || Math.abs(document.scrollingElement.scrollTop - w[1]) >= 1; }",
        arg=[thread_step, page_was],
        timeout=5000,
    )
    page_now, threads_now = offsets()
    assert threads_now > threads_was, (
        "the list the user is standing in did not move for the key they pressed"
    )
    assert page_now == pytest.approx(page_was, abs=1), (
        "the page stepped behind a user who was working down the comment list"
    )

    # Both regions now stand away from their top edge. A correct g g returns the page;
    # the shared-scroller regression returns the panel instead. Wait for either answer so
    # the failure reports both offsets rather than timing out while expecting only one.
    assert page_now > 0 and threads_now > 0
    page.keyboard.press("g")
    page.keyboard.press("g")
    page.wait_for_function(
        "() => { const t = document.querySelector('.lf-threads');"
        " return document.scrollingElement.scrollTop < 1 || t.scrollTop < 1; }",
        timeout=5000,
    )
    edge_page, edge_threads = offsets()
    assert edge_page == pytest.approx(0, abs=1), (
        f"g g left the page at {edge_page} and moved the panel to {edge_threads}"
    )
    assert edge_threads == pytest.approx(threads_now, abs=1), (
        f"g g moved the panel from {threads_now} to {edge_threads}"
    )


def test_the_page_has_one_door_to_a_comparison(browser, serve):
    """`=` marked what changed since the previous version from anywhere on the page, and
    the case for it was that it named no version — "since the last one I saw" is a
    question a user has without opening anything. Naming no version is also naming
    nothing to check, and the two are not the same question: on a page that ships a
    version whenever the work moves, a user back after a week got v(n-1) and no way to
    see that they had. So the door is the menu, where every base says which one it is.

    Pressed rather than read off the table, on both sides: a key bound to nothing looks
    exactly like one that works in the command reference dialog, which is how the removal would go
    unnoticed here and the marks would go unnoticed on the page."""
    url = serve(LONG_PAGE)
    _publish(
        serve.page_dir,
        2,
        LONG_PAGE.replace("Paragraph 3.", "Paragraph three."),
        "reworded a paragraph",
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    line = page.locator(".lf-shortcut-bar")
    # The door is a go-to destination rather than a bare letter, so the line names it
    # once the sequence is armed. The word that must not be anywhere is read behind that
    # arrival, so the absence is taken off a line the press has already repainted.
    page.keyboard.press("g")
    expect(line).to_contain_text("versions")
    expect(line).not_to_contain_text("mark changes")
    page.keyboard.press("Escape")
    page.keyboard.press("=")
    expect(page.locator(".lf-version-menu")).to_be_hidden()
    expect(page.locator(".lf-ins-block")).to_have_count(0)
    page.keyboard.press("g")
    expect(line).to_contain_text("versions")
    page.keyboard.press("Shift+v")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    page.keyboard.press("Escape")

    # The door, and it marks the same passage the key used to.
    compare_with(page)
    expect(page.locator("#p3")).to_have_class(re.compile(r"lf-ins-block"))


def test_the_draft_box_is_its_own_door(browser, serve):
    """A draft is the one block on a page whose whole purpose is that the user rewrites
    it, and until now the only thing that said so was a pencil in the margin 45px away.
    The block itself ignored a press. The gesture that did open it in place was a
    double-click, which is a thing you have to already know.

    So the box is the door, and the caret lands where the press did. Which is a door that
    has to be opened carefully, because the same words are the page's words: a user
    drawing across them to quote them ends that drag with a mouseup inside the box, and
    opening on it would throw the selection away at the moment it was finished. That is
    the question `reachedForWords` answers for every other press on the page's own words,
    asked here rather than answered again. The drag runs through the harness's own
    `hold_selection`, which floors the press - a fractional start point loses the
    selection outright, and an empty one would read exactly like the door swallowing it -
    and the words are read while the drag is still held, because the runtime re-seats the
    selection on a timer after the release and a read in that gap comes back empty.

    And the door is exactly the box - not the chrome inside it. `offer` writes its marker
    on everything a widget builds, controls row and edit box included, and only names a
    kind for the things to press; the guard reads that, so a press on the row does not
    reopen the editor and the row does not wear a hand it has no use for."""
    page = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    body = draft.locator(".lf-draft-body")
    expect(body).to_have_text(DRAFT_TEXT)

    # A drag across the words takes the words. Read as the selection the user is left
    # holding, which is the thing the door would have destroyed.
    box = body.bounding_box()
    line = box["y"] + 8
    hold_selection(page, (box["x"] + 2, line), (box["x"] + box["width"] - 2, line))
    held = page.evaluate("() => getSelection().toString()")
    assert held.strip() != "", (
        f"the drag selected nothing, so this says nothing about the door: {held!r}"
    )
    page.mouse.up()
    expect(draft.locator("leaf-text")).to_have_count(0)

    # A press opens it, with the caret where the press landed rather than at the top.
    page.evaluate("() => getSelection().removeAllRanges()")
    at = page.evaluate(
        """(word) => {
            const node = document.createTreeWalker(
              document.querySelector('#draft-ops .lf-draft-body'),
              NodeFilter.SHOW_TEXT).nextNode();
            const start = node.data.indexOf(word);
            const range = document.createRange();
            range.setStart(node, start); range.setEnd(node, start + word.length);
            const r = range.getBoundingClientRect();
            return [r.x + r.width / 2, r.y + r.height / 2, start, word.length];
        }""",
        "migration",
    )
    page.mouse.click(at[0], at[1])
    editor = draft.locator("leaf-text")
    expect(editor).to_be_focused()
    caret = page.evaluate(
        "() => { const t = document.querySelector('#draft-ops leaf-text');"
        "        return [t.selectionStart, t.selectionEnd]; }"
    )
    assert caret[0] == caret[1], (
        f"one press selected a range rather than placing a caret: {caret}"
    )
    assert at[2] <= caret[0] <= at[2] + at[3], (
        f"the box opened with the caret at {caret[0]}, not in the word pressed "
        f"({at[2]}..{at[2] + at[3]})"
    )

    # The chrome inside the box is not the door, and does not dress as one. The controls
    # row and the edit box are both things `offer` built and neither names a kind.
    inside = page.evaluate(
        """() => [...document.querySelectorAll('#draft-ops [data-lf-offer=""]')]
             .map((el) => [el.localName, getComputedStyle(el).cursor])"""
    )
    assert inside, "the draft built no generated chrome, so this proves nothing"
    assert all(cursor != "pointer" for _tag, cursor in inside), (
        f"generated chrome inside the draft dresses as a press: {inside}"
    )

    # And the pencil is still there, still the keyboard's way in.
    page.keyboard.press("Escape")
    pencil = draft_control(page, "edit", "draft-ops")
    expect(pencil).to_be_focused()
    pencil.click()
    expect(draft.locator("leaf-text")).to_be_visible()


# Generated editors carry native editing under their existing durable draft identity.
def editing_revision_source(mode):
    body = '<h1 id="subject">Editor continuity</h1><p id="passage">A stable passage stays exact across the revision.</p><textarea id="authored-draft" aria-label="Authored draft" style="height:80px"></textarea><lf-draft id="draft-root"><pre>Standing editable text.</pre></lf-draft><lf-ask id="choice-root"><h2>Which choice?</h2><lf-options id="options-root" choose><lf-option id="initial">Initial choice</lf-option></lf-options></lf-ask><lf-command id="command-root" label="Tasks"><lf-task id="seat-root" status="active" talk>What should we do?</lf-task></lf-command>'
    module = """<script type="module">
window.__rendererLifetime={birth:performance.timeOrigin,hits:0,version:'MODE'};
addEventListener('renderer-lifetime-probe',()=>window.__rendererLifetime.hits++);
// Native prototype activation route: activate the offered Latest control without
// transferring the editor's focus to the toolbar before the carry is captured.
addEventListener('keydown',event=>{
  if(event.code==='KeyR' && event.ctrlKey && event.altKey){
    event.preventDefault();
    document.querySelector('.lf-latest-chip')?.click();
  }
});
</script>""".replace("MODE", mode)
    return leaf_page("Editor continuity", body).replace("</head>", module + "</head>")


def editing_read(editor):
    return editor.evaluate(
        "el=>({value:el.value,focused:el.matches(':focus'),caret:[el.selectionStart,el.selectionEnd,el.selectionDirection]})"
    )


@pytest.mark.parametrize(
    "kind",
    [
        "authored",
        "composer",
        "reply",
        "panel-reply",
        "general",
        "first-message",
        "edit",
        "option",
    ],
)
def test_executable_revision_preserves_each_editor_identity(browser, serve, kind):
    page = open_page(browser, live_url(serve(editing_revision_source("overlay"))))
    if kind == "authored":
        editor = page.locator("#authored-draft")
    elif kind == "general":
        page.locator(".lf-threads-toggle").click()
        editor = page.locator(".lf-general leaf-text")
    elif kind == "first-message":
        editor = page.locator("#seat-root > .lf-thread-seat > .lf-say leaf-text")
    elif kind == "edit":
        page.locator("#draft-root .lf-draft-body").click()
        editor = page.locator("#draft-root leaf-text")
    elif kind == "option":
        editor = page.locator("#options-root > .lf-another leaf-text")
    else:
        page.locator("#passage").click(click_count=3)
        page.keyboard.press("c")
        editor = page.locator(".lf-composer leaf-text")
        expect(editor).to_be_focused()
        if kind in {"reply", "panel-reply"}:
            write(editor, "A canonical root comment.")
            page.keyboard.press("Control+Enter")
            round_trip(page)
            page.keyboard.press("c")
            editor = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
            expect(editor).to_be_focused()
            if kind == "panel-reply":
                page.locator(".lf-threads-toggle").click()
                editor = page.locator(".lf-threads .lf-thread-reply leaf-text").first
                write(editor, "A native panel draft.")
    words = "Kept words with a selected span."
    if kind == "authored":
        words = "\n".join([words] * 200)
    write(editor, words)
    editor.evaluate("el=>el.setSelectionRange(5,10,'backward')")
    before = editing_read(editor)
    if kind == "authored":
        editor.evaluate("el=>el.scrollTop=20")
        before["scroll"] = editor.evaluate("el=>el.scrollTop")
        assert before["scroll"] > 0, "the native edit field must actually scroll"
    first_document = page.evaluate("performance.timeOrigin")
    page.evaluate(
        "window.__oldRendererRealm=true;dispatchEvent(new Event('renderer-lifetime-probe'))"
    )
    before_digest = page.locator('meta[name="lf-executable"]').get_attribute("content")
    stamp_page(
        serve.page_dir, editing_revision_source("page"), "Change the page executable"
    )
    told(page)
    if page.evaluate("performance.timeOrigin") == first_document:
        page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    after_digest = page.locator('meta[name="lf-executable"]').get_attribute("content")
    assert after_digest != before_digest
    assert page.evaluate("performance.timeOrigin") != first_document
    assert page.evaluate("window.__oldRendererRealm===undefined")
    page.evaluate("dispatchEvent(new Event('renderer-lifetime-probe'))")
    assert page.evaluate("window.__rendererLifetime.hits") == 1
    after = editing_read(editor) if editor.count() else None
    if kind == "authored":
        after["scroll"] = editor.evaluate("el=>el.scrollTop")
    assert after == before


def editing_mirror_source(mode):
    return editing_revision_source(mode).replace(
        "</main>",
        '<lf-thread-mirror id="first"></lf-thread-mirror><lf-thread-mirror id="second"></lf-thread-mirror></main>',
    )


def test_executable_revision_routes_one_editor_among_visible_reply_mirrors(
    browser, serve
):
    page = open_page(
        browser,
        live_url(
            serve(
                editing_mirror_source("overlay"),
                layer_registry={"lf-thread-mirror": THREAD_MIRROR_DECLARATION},
                layer_widgets={"lf-thread-mirror.js": THREAD_MIRROR},
            )
        ),
    )
    page.locator("#passage").click(click_count=3)
    page.keyboard.press("c")
    write(page.locator(".lf-composer leaf-text"), "Canonical root for both mirrors.")
    page.keyboard.press("Control+Enter")
    round_trip(page)
    first = page.locator("#first .lf-thread-reply leaf-text")
    second = page.locator("#second .lf-thread-reply leaf-text")
    expect(first).to_be_visible()
    expect(second).to_be_visible()
    write(first, "Kept mirror words with backward selection.")
    first.evaluate("el=>el.setSelectionRange(5,10,'backward')")
    expect(second).to_have_js_property("value", first.evaluate("el=>el.value"))
    before = editing_read(first)
    birth = page.evaluate("performance.timeOrigin")
    stamp_page(
        serve.page_dir,
        editing_mirror_source("page"),
        "Change the mirror page executable",
    )
    told(page)
    if page.evaluate("performance.timeOrigin") == birth:
        page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    current = page.evaluate(
        """async()=>{
      const {focused}=await window.__lfRuntimeImport('/runtime/keyboard/scopes.js');
      const el=focused();
      return {tag:el.tagName,value:el.value,caret:[el.selectionStart,el.selectionEnd,el.selectionDirection]};
    }"""
    )
    assert current.get("value") == before["value"]
    assert current["caret"] == before["caret"]


def editing_reply_page(browser, serve, context=None):
    page = open_page(
        browser, live_url(serve(editing_revision_source("before"))), context=context
    )
    page.locator("#passage").click(click_count=3)
    page.keyboard.press("c")
    write(page.locator(".lf-composer leaf-text"), "An anchored root.")
    page.keyboard.press("Control+Enter")
    round_trip(page)
    page.keyboard.press("c")
    return page


def replace_editing_document(page, serve):
    birth = page.evaluate("performance.timeOrigin")
    stamp_page(
        serve.page_dir,
        editing_revision_source("after"),
        "Change real inline module body",
    )
    told(page)
    if page.evaluate("performance.timeOrigin") == birth:
        page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    assert page.evaluate("performance.timeOrigin") != birth


def test_executable_revision_preserves_non_editor_thread_standing(browser, serve):
    page = editing_reply_page(browser, serve)
    page.keyboard.press("Escape")
    captured = page.evaluate(
        "async()=> (await window.__lfRuntimeImport('/runtime/drafts.js')).captureDraftEditing()"
    )
    assert captured is None
    replace_editing_document(page, serve)
    expect(page.locator(".lf-composer leaf-text")).not_to_be_visible()
    assert (
        page.evaluate(
            "async()=> (await window.__lfRuntimeImport('/runtime/drafts.js')).captureDraftEditing()"
        )
        is None
    )


def test_executable_revision_does_not_restore_a_new_draft_generation(browser, serve):
    page = editing_reply_page(browser, serve)
    editor = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
    write(editor, "Old reply generation with selected words.")
    editor.evaluate("el=>el.setSelectionRange(4,9,'backward')")
    saved = page.evaluate(
        """async()=>{
      const owner=await window.__lfRuntimeImport('/runtime/drafts.js');
      const editing=owner.captureDraftEditing();
      return {editing,key:owner.whereDraft(editing.context).key};
    }"""
    )
    page.add_init_script(
        """(() => {
      const key=KEY;
      const record=JSON.parse(localStorage.getItem(key));
      localStorage.setItem(key,JSON.stringify({...record,attempt:'1234567890abcdef1234567890abcdef',base:record.attempt}));
    })()""".replace("KEY", json.dumps(saved["key"]))
    )
    replace_editing_document(page, serve)
    assert (
        page.evaluate(
            "async()=> (await window.__lfRuntimeImport('/runtime/drafts.js')).captureDraftEditing()"
        )
        is None
    )
    expect(page.locator(".lf-composer leaf-text")).not_to_be_visible()
    actual = page.evaluate("(key)=>JSON.parse(localStorage.getItem(key))", saved["key"])
    assert actual["attempt"] == "1234567890abcdef1234567890abcdef"
    assert actual["text"] == saved["editing"]["words"]


@pytest.mark.parametrize("interruption", ["generation", "input"])
def test_delayed_thread_destination_yields_to_shared_generation_or_new_input(
    browser, serve, one_user, interruption
):
    page = editing_reply_page(browser, serve, one_user)
    reply = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
    write(reply, "The exact generation whose route is waiting.")
    other = open_page(browser, page.url, context=one_user)
    held = page.evaluate(
        """async()=>{
      const drafts=await window.__lfRuntimeImport('/runtime/drafts.js');
      const focus=await window.__lfRuntimeImport('/runtime/thread/focus.js');
      return {editing:drafts.captureDraftEditing(),id:focus.heldThreadId()};
    }"""
    )
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-filter-toggle").click()
    page.get_by_role("searchbox", name="Find in threads").fill(
        "A query that hides this thread"
    )
    expect(page.locator(f""".lf-thread[data-id="{held["id"]}"]""")).to_be_hidden()
    hold_visible_thread_presentation(page, held["id"])
    page.evaluate(
        """async held=>{
      const drafts=await window.__lfRuntimeImport('/runtime/drafts.js');
      const {replyDestination}=await window.__lfRuntimeImport('/runtime/thread/focus.js');
      const {retainUserIntent,restrictUserIntent}=await window.__lfRuntimeImport('/runtime/user-intent.js');
      const {openThread}=await window.__lfRuntimeImport('/runtime/widget-api.js');
      const button=document.createElement('button');button.id='held-reply-route';button.textContent='Continue the held reply';document.querySelector('main').append(button);
      button.onclick=()=>{
        const original=retainUserIntent();window.readOriginalIntent=original;
        const permission=restrictUserIntent(original,()=>drafts.draftEditingStands(held.editing));
        window.heldRouteResult=undefined;
        void replyDestination(held.id,openThread,permission).then(destination=>window.heldRouteResult=Boolean(destination));
      };
      window.heldEditing=held.editing;
    }""",
        held,
    )
    page.locator("#held-reply-route").click()
    page.wait_for_function("window.visibleThreadPresentationHeld===true")
    if interruption == "generation":
        assert page.evaluate("window.readOriginalIntent()")
        other.evaluate(
            """async editing=>{
          const drafts=await window.__lfRuntimeImport('/runtime/drafts.js');
          drafts.saveDraft(editing.context,editing.words);
        }""",
            held["editing"],
        )
        page.wait_for_function(
            "async()=>!(await window.__lfRuntimeImport('/runtime/drafts.js')).draftEditingStands(heldEditing)"
        )
        assert page.evaluate("window.readOriginalIntent()"), (
            "the state change must not supersede input intent"
        )
    else:
        write(page.locator("#authored-draft"), "Newer native input owns focus.")
    page.evaluate("releaseVisibleThreadPresentation()")
    page.wait_for_function("window.heldRouteResult!==undefined")
    assert page.evaluate("window.heldRouteResult") is False
    if interruption == "generation":
        expect(page.locator("#held-reply-route")).to_be_focused()
    else:
        expect(page.locator("#authored-draft")).to_be_focused()


@pytest.mark.parametrize("surface", ["panel", "margin"])
def test_live_executable_replacement_keeps_a_resolved_reply_session(
    browser, serve, surface
):
    """A live replacement continues actual editing; an ordinary reload only saves words."""
    page = editing_reply_page(browser, serve)
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    if surface == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
        thread.locator(".lf-thread-summary").focus()
    else:
        thread = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]'
        )
    editor = thread.locator("leaf-text")
    words = "Keep this actual editing session through the executable replacement."
    write(editor, words)
    editor.evaluate("el=>el.setSelectionRange(5,12,'backward')")
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    expect(editor).to_be_focused()
    before = editing_read(editor)
    context = page.evaluate(
        "async()=> (await window.__lfRuntimeImport('/runtime/drafts.js')).captureDraftEditing().context"
    )
    replace_editing_document(page, serve)
    expect(editor).to_be_focused()
    assert editing_read(editor) == before
    assert stored_draft_text(page, context) == words

    page.reload()
    wait_until_ready(page)
    expect(page.locator(".lf-thread-reply leaf-text")).not_to_be_visible()
    assert stored_draft_text(page, context) == words


@pytest.mark.parametrize("kind", ["edit", "first-message", "option"])
def test_in_place_revision_restores_the_current_generated_editor(browser, serve, kind):
    original = editing_revision_source("same-module")
    page = open_page(browser, live_url(serve(original)))
    if kind == "edit":
        page.locator("#draft-root .lf-draft-body").click()
        editor = page.locator("#draft-root leaf-text")
        revised = original.replace(
            "Standing editable text.", "A revised authored draft body."
        )
    elif kind == "first-message":
        editor = page.locator("#seat-root > .lf-thread-seat > .lf-say leaf-text")
        revised = original.replace("What should we do?", "What should we do next?")
    else:
        editor = page.locator("#options-root > .lf-another leaf-text")
        revised = original.replace("Initial choice", "A revised initial choice")
    write(editor, "An unsent edit keeps its exact selection.")
    editor.evaluate("el=>el.setSelectionRange(4,9,'backward')")
    before = editing_read(editor)
    editor.evaluate("el=>el.__outgoingEditor=true")
    birth = page.evaluate("performance.timeOrigin")
    stamp_page(serve.page_dir, revised, "Replace authored widget, retain executable")
    told(page)
    if (
        page.evaluate(
            "document.querySelector('.lf-latest-chip')?.getAttribute('hidden')"
        )
        is None
    ):
        page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    assert page.evaluate("performance.timeOrigin") == birth
    expect(editor).to_be_visible()
    if kind != "option":
        assert not editor.evaluate("el=>Boolean(el.__outgoingEditor)")
    expect(editor).to_be_focused()
    assert editing_read(editor) == before


def test_a_mechanical_revision_failure_leaves_accepted_publication_ready(
    browser, serve
):
    original = editing_revision_source("same-module")
    page = open_page(browser, live_url(serve(original)))
    page.locator("#draft-root .lf-draft-body").click()
    editor = page.locator("#draft-root leaf-text")
    write(editor, "The actual editor keeps these unsent words.")
    before = editing_read(editor)
    later_readings = []

    def hold_later_readings(route):
        later_readings.append(route)

    page.evaluate(
        "() => document.addEventListener('lf-page-interface',event=>{\n      event.detail.present(Promise.resolve().then(()=>{\n        const editor=document.querySelector('#draft-root leaf-text');\n        if(!editor)throw new Error('failure arrangement did not create its editor');\n        editor.setSelectionRange=()=>{window.__mechanicalCaretFailure=true;throw new Error('mechanical caret fixture failed')};\n      }));\n    },{once:true})"
    )
    stamp_page(
        serve.page_dir,
        original.replace("Standing editable text.", "New authored body."),
        "Install while generated editor has a failing caret",
    )
    told(page)
    before_reading = page.locator("body").get_attribute("data-lf-reading")
    page.route("**/api/state**", hold_later_readings)
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "installation-evidence",
            "kind": "comment",
            "author": "agent",
            "revision": 2,
            "text": "This fact joins the first installed publication.",
            "anchor": {"section": "passage"},
        },
    )
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/event")
            and response.request.method == "POST"
            and response.request.post_data_json.get("kind") == "error"
        )
    ):
        with page.expect_request("**/api/state**") as requested:
            page.keyboard.press("Control+Alt+r")
        first = next(
            route for route in later_readings if route.request == requested.value
        )
        answer = first.fetch()
        first_reading = answer.json()["reading"]
        assert first_reading != before_reading
        later_readings.remove(first)
        first.fulfill(response=answer)
    page.wait_for_function(
        "document.querySelector('meta[name=lf-revision][data-lf-runtime]')?.content==='2'"
        " && window.__mechanicalCaretFailure"
    )
    expect(editor).to_have_js_property("value", before["value"])
    expect(page.locator("body")).to_have_attribute("data-lf-reading", first_reading)
    page.wait_for_function(
        "async()=> (await window.__lfRuntimeImport('/runtime/semantic-state.js')).applicationPresented()"
    )
    errors = consume_browser_errors(page, "mechanical caret fixture failed")
    assert len(errors) == 1, errors
    assert "Revision continuity failed" in errors[0], errors
    page.wait_for_function(
        "async()=> (await window.__lfRuntimeImport('/runtime/semantic-state.js')).readApplication().document.revision===2"
    )
    reported = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "error"
    ]
    assert len(reported) == 1, reported
    assert (
        reported[0]["text"]
        == "Revision continuity failed: mechanical caret fixture failed"
    )

    # Error reporting may advance server freshness, but no later state answer may
    # rescue this reading: the first proved application must complete itself.
    page.unroute("**/api/state**", hold_later_readings)
    for route in later_readings:
        route.continue_()


def test_a_fresh_revision_caret_failure_does_not_strand_deferred_arrivals(
    browser, serve
):
    original = editing_revision_source("before")
    page = open_page(browser, live_url(serve(original)))
    page.locator("#draft-root .lf-draft-body").click()
    editor = page.locator("#draft-root leaf-text")
    write(editor, "Fresh words preserve exact original draft attempt.")
    editor.evaluate("el=>el.setSelectionRange(4,9,'backward')")
    revised = editing_revision_source("after").replace(
        "window.__rendererLifetime=",
        "import {afterPresentation,TEXT_FIELD} from '/runtime/widget-api.js';afterPresentation(()=>window.__deferredArrivalRan=true);document.addEventListener('lf-presentation',()=>window.__presentationDispatched=true);\nconst field=customElements.get(TEXT_FIELD).prototype;const setRange=field.setSelectionRange;\nfield.setSelectionRange=function(a,b,d){if(a===4&&b===9)throw new Error('fresh mechanical caret fixture failed');return setRange.call(this,a,b,d)};\nwindow.__rendererLifetime=",
    )
    stamp_page(serve.page_dir, revised, "Fresh executable with mechanical failure")
    told(page)
    page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    errors = consume_browser_errors(page, "fresh mechanical caret fixture failed")
    assert page.evaluate("Boolean(window.__presentationDispatched)")
    page.wait_for_function("window.__deferredArrivalRan===true")
    assert len(errors) == 1, errors
    assert "Revision continuity failed" in errors[0], errors


def test_first_draft_save_and_refusal_keep_the_history_allocation(browser, serve):
    """Current text and the zero-edit history keep one box through a refused first Save."""
    source = leaf_page(
        "First draft refusal",
        "<h1>First draft refusal</h1>"
        '<lf-draft id="first-draft"><pre>Original words.</pre></lf-draft>'
        '<p id="following">The following passage stays where the reader found it.</p>',
    )
    page = open_page(browser, serve(source))
    draft = page.locator("#first-draft")
    history = draft.locator(".lf-draft-history > summary")
    expect(history).to_have_text("Changes · 0 edits")
    draft_control(page, "edit", "first-draft").click()
    write(draft.locator("leaf-text"), "Changed words.")
    before = page.locator("#following").bounding_box()
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    draft_control(page, "save", "first-draft").click()
    holding(page, held, 1, "the refused first draft Save")
    expect(draft.locator(".lf-draft-body")).to_have_text("Changed words.")
    expect(draft.locator(".lf-draft-current")).to_contain_text(
        "This version → standing text"
    )
    assert page.locator("#following").bounding_box() == before
    held[0].fulfill(
        status=400, json={"ok": False, "final": True, "error": "refused first edit"}
    )
    expect(draft.locator("leaf-text")).to_have_js_property("value", "Changed words.")
    expect(draft.locator(".lf-draft-body")).to_have_text("Original words.")
    expect(history).to_have_text("Changes · 0 edits")
    assert page.locator("#following").bounding_box() == before
    consume_browser_errors(page, "400")


def test_resume_writing_keeps_editor_identity_caret_and_sent_conversation(
    browser, serve
):
    """Resume follows actual edits across comment, reply and document editors."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Resume writing",
                '<h1>Resume writing</h1><p id="subject">A passage worth discussing.</p>'
                '<lf-draft id="editable"><pre>Original page text</pre></lf-draft>',
            )
        ),
    )
    compose(page, "#subject", "My original comment")
    box = page.locator(".lf-fab-input")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    caret = box.evaluate("el => el.selectionStart")
    page.keyboard.press("Escape")
    page.locator("#editable .lf-draft-body").click()
    expect(page.locator("#editable .lf-draft-edit")).to_be_focused()
    page.keyboard.press("Escape")  # focusing an editor is not an edit
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "My original comment")
    assert box.evaluate("el => el.selectionStart") == caret
    # Native input still owns the letters; gi must never run inside an editor.
    page.keyboard.type("gi")
    expect(box).to_have_js_property("value", "Mygi original comment")
    page.keyboard.press("Escape")
    held = []
    page.route("**/api/state", lambda route: held.append(route))
    page.reload()
    holding(page, held, 1, "the reloaded page's initial state")
    # A user gesture while presentation waits supersedes automatic draft recovery.
    # It must not later steal focus and turn the page shortcut into typed letters.
    page.keyboard.press("Escape")
    held[0].continue_()
    page.unroute("**/api/state")
    wait_until_ready(page)
    expect(box).not_to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "Mygi original comment")
    expect(box).to_have_js_property("selectionStart", caret + 2)
    with sending(page, "first comment"):
        page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    reply = page.locator("leaf-text[name=reply]:focus")
    expect(reply).to_be_visible()
    expect(reply).to_have_js_property("value", "")
    write(reply, "Continue this thread")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator("leaf-text[name=reply]:focus")).to_have_js_property(
        "value", "Continue this thread"
    )
    assert (
        page.locator("leaf-text[name=reply]:focus").evaluate("el => el.selectionStart")
        == 1
    )
    page.keyboard.press("Escape")
    page.locator("#editable .lf-draft-body").click()
    edit = page.locator("#editable .lf-draft-edit")
    write(edit, "Rewritten page text")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Escape")
    # The desktop More reference invokes the same semantic command as gi.
    page.keyboard.press("?")
    page.keyboard.press("?")
    page.get_by_role("combobox", name="Search commands").fill("Resume writing")
    page.get_by_role("button", name="Resume writing", exact=True).click()
    expect(edit).to_be_focused()
    expect(edit).to_have_js_property("value", "Rewritten page text")
    assert edit.evaluate("el => el.selectionStart") == 1


def test_resume_writing_is_a_touch_action_and_does_not_steal_hint_addresses(
    browser, serve
):
    """A finger can resume the general box; gi never collides with generated hints."""
    source = leaf_page(
        "Resume targets",
        '<h1 id="heading">Resume targets</h1>'
        + "".join(
            f'<p><a id="link{index}" href="#heading">Jump {index}</a></p>'
            for index in range(30)
        ),
    )
    page = open_page(browser, serve(source))
    page.locator(".lf-threads-toggle").click()
    general = page.locator(".lf-general leaf-text")
    write(general, "A page-wide draft")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    expect(page.locator(".lf-go-to-hint[data-lf-hint-code]").first).to_be_visible()
    labels = page.locator(".lf-go-to-hint[data-lf-hint-code]").evaluate_all(
        "els => els.map(el => el.dataset.lfHintCode)"
    )
    assert labels and all("i" not in label for label in labels)
    page.keyboard.press("i")
    expect(general).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    context = browser.new_context(
        is_mobile=True, has_touch=True, viewport={"width": 390, "height": 844}
    )
    touch = open_page(browser, serve(LONG_PAGE), context=context)
    touch.keyboard.press("c")
    general = touch.locator(".lf-general leaf-text")
    write(general, "A touch draft")
    touch.keyboard.press("Escape")
    touch.keyboard.press("Escape")
    touch.get_by_role("button", name="More page controls", exact=True).click()
    touch.get_by_role("button", name="Resume writing", exact=True).click()
    expect(general).to_be_focused()
    expect(general).to_have_js_property("value", "A touch draft")


@pytest.mark.parametrize("hidden_tab", [False, True])
def test_resume_writing_reveals_page_editor_from_a_covering_panel_and_keeps_back(
    browser, serve, hidden_tab
):
    """Resume exposes a hidden editor's place immediately and keeps the outgoing reading."""
    writing = (
        '<details id="fold" open><summary>Editable content</summary>'
        '<lf-draft id="editable"><pre>Initial words</pre></lf-draft></details>'
    )
    reading = (
        '<div style="height:2200px"></div><h2 id="elsewhere">Elsewhere</h2>'
        "<p>Keep this reading position.</p>"
    )
    body = writing + reading
    if hidden_tab:
        body = (
            '<lf-tabs id="views"><lf-tab id="writing-view" label="Writing">'
            + writing
            + '<div style="height:3300px"></div>'
            '</lf-tab><lf-tab id="reading-view" label="Reading">'
            + reading
            + "</lf-tab></lf-tabs>"
        )
    page = open_page(
        browser,
        serve(leaf_page("Resume travel", '<h1 id="top">Resume travel</h1>' + body)),
    )
    page.locator("#editable .lf-draft-body").click()
    edit = page.locator("#editable .lf-draft-edit")
    write(edit, "Last edit")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Escape")
    page.locator("#fold > summary").click()
    if hidden_tab:
        page.get_by_role("tab", name="Reading", exact=True).click()
    page.locator("#elsewhere").click()
    resized(page, 390, 844)
    scroll_settled(page)
    source_entry = page.evaluate("navigation.currentEntry.key")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    if hidden_tab:
        page.evaluate("""() => {
          const held = new Promise(resolve => { window.releaseResumeLayout = resolve; });
          document.querySelector('#views').addEventListener('lf-layout', event => {
            event.detail.present(held);
            window.resumeLayoutStarted = true;
          }, {once: true});
        }""")
        try:
            page.keyboard.press("g")
            page.keyboard.press("i")
            page.wait_for_function("window.resumeLayoutStarted === true")
            one_frame(page)
            expect(page.locator("#writing-view")).to_be_visible()
            first_view = page.locator("#editable").evaluate("""async draft => {
              const {landingBand} = await window.__lfRuntimeImport('/runtime/geometry.js');
              const rect = draft.getBoundingClientRect();
              const band = landingBand(document.scrollingElement);
              return {top: rect.top, bottom: rect.bottom, low: band.top, high: band.bottom};
            }""")
            assert first_view["top"] >= first_view["low"], first_view
            assert first_view["bottom"] <= first_view["high"], first_view
        finally:
            page.evaluate("releaseResumeLayout()")
    else:
        page.keyboard.press("g")
        page.keyboard.press("i")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    expect(edit).to_be_focused()
    expect(edit).to_be_in_viewport()
    expect(edit).to_have_js_property("value", "Last edit")
    assert edit.evaluate("el => el.selectionStart") == 1
    page.go_back()
    scroll_settled(page)
    expect(page.locator("#elsewhere")).to_be_in_viewport()
    assert page.evaluate("navigation.currentEntry.key") == source_entry
    # Clearing every word still records a real editor destination.
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(edit).to_be_focused()
    edit.press("ControlOrMeta+a")
    edit.press("Backspace")
    page.keyboard.press("Escape")
    if hidden_tab:
        page.get_by_role("tab", name="Reading", exact=True).click()
    page.locator("#elsewhere").click()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(edit).to_be_focused()
    expect(edit).to_have_js_property("value", "")
