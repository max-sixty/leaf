"""Rewriting a message the user sent: opening the rewrite by keyboard or control, where
its box stands across readers, saving its exact words, and a rewrite that is refused or
overtaken."""

import io
import json
import re

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf.render_checks import one_frame, rendered, wait_until_ready
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, THREAD_DIFF_PAGE
from render_harness import (
    FEATURE_GALLERY,
    LONG_PAGE,
    consume_browser_errors,
    holding,
    http_error_console,
    leaf_page,
    open_page,
    resized,
    round_trip,
    sending,
    stored_draft_text,
    told,
    write,
)

from browser.threads import (
    focus_panel_thread,
)

pytestmark = pytest.mark.shifts_unsurveyed


def _ring_gaps(page, target):
    """The sides of `target`'s focus ring the page does not show in its colour: those a
    clipping scroller or a box painted over them hides."""
    ring = target.evaluate(
        """el => {
          const s = getComputedStyle(el), r = el.getBoundingClientRect();
          const out = parseFloat(s.outlineOffset) + parseFloat(s.outlineWidth) / 2;
          return {color: s.outlineColor, left: r.left - out, right: r.right + out,
            top: r.top - out, bottom: r.bottom + out};
        }"""
    )
    # A ring stands on the middle of each side, where no corner rounds it.
    x, y = (ring["left"] + ring["right"]) / 2, (ring["top"] + ring["bottom"]) / 2
    points = {
        "left": (ring["left"], y),
        "right": (ring["right"], y),
        "top": (x, ring["top"]),
        "bottom": (x, ring["bottom"]),
    }
    color = tuple(int(c) for c in re.findall(r"\d+", ring["color"])[:3])
    gaps = []
    for side, (px, py) in points.items():
        shot = page.screenshot(
            clip={"x": px - 0.5, "y": py - 0.5, "width": 1, "height": 1}
        )
        seen = Image.open(io.BytesIO(shot)).convert("RGB").getpixel((0, 0))
        if max(abs(a - b) for a, b in zip(seen, color)) > 40:
            gaps.append(side)
    return gaps


def test_a_rewrite_of_a_comment_just_sent_is_the_reply_box(browser, serve):
    """A rewrite of a comment just sent is as wide as the reply box, its words where
    the message's stood.

    The field's ring, drawn outside it as the reply box's is, lost its left and bottom
    sides to the transcript that scrolls it, which kept no room past its edges; and the
    card's actions painted their ground over the right side of a focused Edit's or
    Save's ring. Each ring now stands whole."""
    touch = False
    context = browser.new_context(has_touch=touch, is_mobile=touch)
    page = open_page(browser, serve(LONG_PAGE), context=context)
    resized(page, 390 if touch else 1200, 900)
    page.locator("#p1").click(modifiers=["Alt"])
    field = page.locator(".lf-fab-input")
    field.click()
    write(
        field,
        "Shorten this paragraph and keep its example, since the example is what "
        "readers remember once the rest of the section has gone by them.",
    )
    with sending(page, "the comment to rewrite"):
        page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    card = page.locator(".lf-margin-preview")
    message = card.locator(".lf-msg").first
    words = message.locator(".lf-msg-text")
    rendered(page)
    before = message.bounding_box(), words.bounding_box()
    first_line = words.evaluate(FIRST_LINE)
    message.locator(".lf-msg-edit").focus()
    one_frame(page)
    assert _ring_gaps(page, message.locator(".lf-msg-edit")) == []
    message.locator(".lf-msg-edit").click()
    editor = message.locator(".lf-msg-editor")
    expect(editor.locator("leaf-text")).to_be_focused()
    rendered(page)
    field = editor.locator(".lf-compose-field")
    reply = card.locator(".lf-thread-reply .lf-compose-field")
    box, reply_box = field.bounding_box(), reply.bounding_box()
    for side in ("x", "width"):
        assert abs(box[side] - reply_box[side]) < 0.5, (side, box, reply_box)
    # Its words keep the lines the comment wrapped to, and the message its height.
    opened = message.bounding_box()
    for side in ("y", "height"):
        assert abs(opened[side] - before[0][side]) < 0.5, (side, opened, before[0])
    editing_line = editor.locator("leaf-text").evaluate(FIRST_LINE)
    for at in (0, 1):
        assert abs(editing_line[at] - first_line[at]) < 0.5, (editing_line, first_line)
    rendered(page)
    assert _ring_gaps(page, field) == []
    save = message.get_by_role("button", name="Save", exact=True)
    save.focus()
    one_frame(page)
    assert _ring_gaps(page, save) == []


def test_the_keyboard_walks_up_through_the_users_messages_to_rewrite_one(
    browser, serve
):
    """↑ from the thread's empty reply box opens the user's latest message, and ↑ from
    the start of an open rewrite opens their message before it; a held ↑ stops at the
    start, since its repeats are the one press that took the caret there. The Edit
    control is for a pointer or a finger, so it takes no Tab stop in the thread."""
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    first = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": "cd-q"},
        },
    )
    answer = append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "parent": first["id"],
            "responds": first["id"],
            "text": "Fitted.",
        },
    )
    second = append_carried_log_record(
        d,
        {"kind": "reply", "author": "user", "parent": answer["id"], "text": "Thanks."},
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-threads-toggle").click()
    thread = page.locator(f'.lf-thread:has(.lf-msg[data-mid="{first["id"]}"])')
    expect(thread.locator(".lf-msg-edit").first).to_have_attribute("tabindex", "-1")

    thread.locator(".lf-thread-reply leaf-text").focus()
    page.keyboard.press("ArrowUp")
    latest = thread.locator(
        f'.lf-msg[data-mid="{second["id"]}"] .lf-msg-editor leaf-text'
    )
    expect(latest).to_be_focused()
    # ↑ on the box's first line goes to its start, as in any box, and ↑ from there on.
    page.keyboard.down("ArrowUp")
    page.keyboard.down("ArrowUp")
    page.keyboard.up("ArrowUp")
    expect(latest).to_be_focused()
    expect(latest).to_have_js_property("selectionStart", 0)
    page.keyboard.press("ArrowUp")
    earlier = thread.locator(
        f'.lf-msg[data-mid="{first["id"]}"] .lf-msg-editor leaf-text'
    )
    expect(earlier).to_be_focused()
    expect(thread.locator(".lf-msg-editor")).to_have_count(1)
    expect(earlier).to_have_js_property("value", "Fit the north bracket.")


def _feed_page(serve):
    """The feature gallery's package reader alone on a page, which in Feed mode draws
    each message of every conversation as a part of its own, and the selected one's
    reply box below them."""
    companion = FEATURE_GALLERY.parent / "feature-gallery.page"
    return serve(
        leaf_page(
            "Package reader",
            '<h1>Package reader</h1><p id="cd-q">The bracket notes.</p>'
            '<lf-conversation-workspace id="workspace"></lf-conversation-workspace>',
        ),
        layer_registry={
            "lf-conversation-workspace": json.loads(
                (companion / "registry.json").read_text()
            )["lf-conversation-workspace"]
        },
        layer_widgets={
            "lf-conversation-workspace.js": (
                companion / "widgets/lf-conversation-workspace.js"
            ).read_text()
        },
    )


def _rewrite_surface(
    browser, serve, surface, size=(1400, 900), resolved=False, thanks=False
):
    """A thread holding the user's message and the agent's answer, drawn on `surface`:
    the Threads panel, the seat in the page's flow, the margin card, or a package
    reader's Feed mode; `resolved`, in the panel, under its Resolved filter; `thanks`,
    with the user's own reply after the answer. Returns the page, the thread, and the
    message as that surface draws it."""
    url = (
        serve(PANEL_PAGE)
        if surface == "card"
        else _feed_page(serve)
        if surface == "feed"
        else serve(THREAD_DIFF_PAGE)
    )
    anchor = "how-store" if surface == "card" else "cd-q"
    mine = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": anchor},
        },
    )
    answer = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "parent": mine["id"],
            "responds": mine["id"],
            "text": "Fitted.",
        },
    )
    if thanks:
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "user",
                "parent": answer["id"],
                "text": "Thanks.",
            },
        )
    if resolved:
        append_carried_log_record(
            serve.page_dir, {"kind": "resolve", "author": "user", "parent": mine["id"]}
        )
    page = open_page(browser, url)
    resized(page, *size)
    if surface == "panel":
        page.locator(".lf-threads-toggle").click()
        if resolved:
            page.locator(".lf-thread-filter-toggle").click()
            page.locator('[data-filter-value="resolved"]').click()
        thread = page.locator(f'.lf-thread:has(.lf-msg[data-mid="{mine["id"]}"])')
        message = thread.locator(f'.lf-msg[data-mid="{mine["id"]}"]')
    elif surface == "seat":
        thread = page.locator("#cd-q .lf-page-thread").first
        message = thread.locator(f'.lf-msg[data-event="{mine["id"]}"]')
    elif surface == "feed":
        thread = page.locator("#workspace")
        thread.get_by_role("button", name="Feed", exact=True).click()
        message = thread.locator(f'.lf-primary-part .lf-msg[data-event="{mine["id"]}"]')
    else:
        page.locator(f'[data-lf-margin-for="{anchor}"] .lf-margin-marker').click()
        thread = page.locator(".lf-margin-preview")
        message = thread.locator(f'.lf-msg[data-event="{mine["id"]}"]')
    expect(message).to_be_visible()
    rendered(page)
    return page, thread, message


# Where the first line of a node's words stands: its first text box's left and top.
FIRST_LINE = """n => {
  const root = n.shadowRoot ?? n;
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let t = walk.nextNode(); t; t = walk.nextNode()) {
    if (!t.data.trim()) continue;
    const range = document.createRange();
    range.selectNodeContents(t);
    const box = range.getClientRects()[0];
    return [box.left, box.top];
  }
  return null;
}"""


@pytest.mark.parametrize("surface", ["panel", "seat", "card", "feed"])
def test_a_rewrite_is_the_reply_box_where_the_words_stood(browser, serve, surface):
    """Opening a rewrite with ↑ swapped the message for a bordered box with Cancel on a
    row of its own, pushing every turn and the reply box below it down 55px, and Escape
    left that room behind and the user standing on the thread rather than in the box
    they pressed ↑ from. A later box painted around the words, with no padding of its
    own, moved nothing but read as a thinner, narrower field than the reply box beside
    it. The rewrite is now the reply box's own field, at its width and height, with the
    words at their inset under the message's head; Cancel and Save take that head, and
    every way out steps back up to the reply box, leaving the thread as it was. In the
    margin card the reply box's taller field grew a short message, so the card kept
    that room under every message of the user's; the rewrite there is now the comment
    box the card grew from, and opening it moves nothing.

    In the margin card each keystroke in the rewrite also threw, from the reply box's
    growth-following reading a reply row the rewrite has none of; the browser fixture
    fails on that error. A double click put the caret before the words, since clearing
    the word it selected took the caret the editor had just set. A package reader's
    Feed mode, drawing each message on its own, offered no rewrite at all."""
    page, thread, message = _rewrite_surface(browser, serve, surface)
    reply = thread.locator(".lf-thread-reply leaf-text").first
    reply.click()
    rendered(page)
    words = message.locator(".lf-msg-text")
    first_line = words.evaluate(FIRST_LINE)
    rest = {"message": message.bounding_box(), "reply": reply.bounding_box()}

    def unmoved():
        now = {"message": message.bounding_box(), "reply": reply.bounding_box()}
        for name, box in rest.items():
            assert abs(now[name]["y"] - box["y"]) < 0.5, (name, box, now[name])
            assert abs(now[name]["height"] - box["height"]) < 0.5, (
                name,
                box,
                now[name],
            )

    page.keyboard.press("ArrowUp")
    editor = message.locator(".lf-msg-editor leaf-text")
    expect(editor).to_be_focused()
    rendered(page)
    # The message keeps its head's place, and its words their inset, in a box the
    # reply box's width and, outside the card, its height. The card's rewrite is the
    # comment box the card grew from, its frame in the room the words' lines keep, so
    # there the message keeps its height and the words their line.
    assert abs(message.bounding_box()["y"] - rest["message"]["y"]) < 0.5
    field = message.locator(".lf-msg-editor > .lf-compose-field").bounding_box()
    reply_field = thread.locator(".lf-thread-reply .lf-compose-field").bounding_box()
    for side in ("x", "width") if surface == "card" else ("x", "width", "height"):
        assert abs(field[side] - reply_field[side]) < 0.5, (side, field, reply_field)
    # Feed mode draws its messages at the reply box's edge, not inset in a transcript,
    # so there the words take the reply box's inset instead.
    if surface != "feed":
        editing_line = editor.evaluate(FIRST_LINE)
        assert abs(editing_line[0] - first_line[0]) < 0.5, (editing_line, first_line)
    if surface == "card":
        assert abs(editing_line[1] - first_line[1]) < 0.5, (editing_line, first_line)
        unmoved()
    head = message.locator(".lf-msg-head").bounding_box()
    for name in ("Cancel", "Save"):
        box = message.get_by_role("button", name=name, exact=True).bounding_box()
        middle = box["y"] + box["height"] / 2
        assert head["y"] - 1 <= middle <= head["y"] + head["height"] + 1, (
            name,
            box,
            head,
        )
    page.keyboard.type("Z")
    expect(editor).to_have_js_property("value", "Fit the north bracket.Z")
    page.keyboard.press("Escape")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(reply).to_be_focused()
    rendered(page)
    unmoved()

    # A double click puts the caret after the words, as ↑ does.
    words.dblclick()
    expect(editor).to_be_focused()
    page.keyboard.type("Y")
    expect(editor).to_have_js_property("value", "Fit the north bracket.Y")
    # Escape on the rewrite's own controls closes it as in its words.
    message.get_by_role("button", name="Save", exact=True).focus()
    page.keyboard.press("Escape")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(thread).to_be_visible()
    expect(reply).to_be_focused()
    # Saved, the new words take the box's place, and the user stands in the reply box.
    words.dblclick()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Fit the bracket.")
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(words).to_have_text("Fit the bracket.")
    expect(reply).to_be_focused()
    round_trip(page)
    rendered(page)
    unmoved()


def test_a_package_feed_keeps_a_rewrite_where_a_card_would(browser, serve):
    """A package reader drawing each message on its own, as the feature gallery's Feed
    mode does, offered the user's own words no rewrite: its parts had no thread card to
    open one in, and Resume writing took a kept rewrite to the Threads panel. The Edit
    control opens it there now, Save sends it, and words kept through a reload come back
    under Resume writing on the message where Feed draws it, the reader staying in
    Feed."""
    page, workspace, message = _rewrite_surface(browser, serve, "feed")
    mine = message.get_attribute("data-event")
    feed = workspace.get_by_role("button", name="Feed", exact=True)
    expect(workspace.locator(".lf-msg.agent .lf-msg-edit")).to_have_count(0)

    message.hover()
    message.get_by_role("button", name="Edit message").click()
    editor = message.locator(".lf-msg-editor leaf-text")
    expect(editor).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Fit the south bracket.")
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the south bracket.")
    expect(message.locator(".lf-edited")).to_have_text("edited")
    round_trip(page)
    edits = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "edit"]
    assert [(e["message"], e["text"]) for e in edits] == [
        (mine, "Fit the south bracket.")
    ]

    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_be_focused()
    page.keyboard.type(" Or the east.")
    page.reload()
    wait_until_ready(page)
    feed.click()
    expect(message.locator(".lf-msg-kept")).to_have_text("unsaved edit")
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "Fit the south bracket. Or the east.")
    expect(feed).to_have_attribute("aria-pressed", "true")
    message.get_by_role("button", name="Cancel").click()
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(message.locator(".lf-msg-kept")).to_have_count(0)
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the south bracket.")


def test_a_rewrite_opened_on_held_words_starts_from_the_words_as_they_stand(
    browser, serve
):
    """A rewrite another tab made, which Feed held back behind its news notice, stayed
    under a rewrite opened here: the editor opened on the old words over the old
    revision, so even a Save of words the user had not changed was sent, and the log
    refused it. Until the user changes them, the editor's words follow the message, so
    it shows the other rewrite and is written over it."""
    page, workspace, message = _rewrite_surface(browser, serve, "feed")
    mine = message.get_attribute("data-event")
    words = message.locator(".lf-msg-text")
    other = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "user",
            "message": mine,
            "base": mine,
            "text": "Fit the west bracket.",
        },
    )
    round_trip(page)
    # Feed holds the other rewrite back while the user reads the message.
    expect(workspace.locator(".lf-primary-news").first).to_have_text("1 message edited")
    expect(words).to_have_text("Fit the north bracket.")
    words.dblclick()
    editor = message.locator(".lf-msg-editor leaf-text")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "Fit the west bracket.")
    page.keyboard.type(" Twice.")
    page.keyboard.press("Enter")
    expect(words).to_have_text("Fit the west bracket. Twice.")
    round_trip(page)
    edits = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "edit"]
    assert [(e["text"], e["base"]) for e in edits] == [
        ("Fit the west bracket.", mine),
        ("Fit the west bracket. Twice.", other["id"]),
    ]


def test_one_editor_shows_a_message_across_its_readers(browser, serve):
    """A rewrite opened on a message in Feed stayed open there when the same message's
    rewrite was opened in the Threads panel, so two editors of one draft stood at once.
    Opening it in one reader closes it in the other, the message there reading as it
    stands."""
    page, _workspace, message = _rewrite_surface(browser, serve, "feed")
    mine = message.get_attribute("data-event")
    message.locator(".lf-msg-text").dblclick()
    expect(message.locator(".lf-msg-editor leaf-text")).to_be_focused()
    page.locator(".lf-threads-toggle").click()
    card = page.locator(f'.lf-thread .lf-msg[data-mid="{mine}"]')
    card.locator(".lf-msg-text").dblclick()
    expect(card.locator(".lf-msg-editor leaf-text")).to_be_focused()
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the north bracket.")


def test_one_unchanged_rewrite_stands_open_in_a_thread_across_its_readers(
    browser, serve
):
    """Opening a rewrite of one message closes a rewrite of another in the same thread
    whose words the user left as they were, in a thread card. A rewrite left open in
    Feed stayed open when another message's rewrite opened in the Threads panel, since
    each reader put aside only its own."""
    page, workspace, message = _rewrite_surface(browser, serve, "feed", thanks=True)
    message.locator(".lf-msg-text").dblclick()
    expect(message.locator(".lf-msg-editor leaf-text")).to_be_focused()
    page.locator(".lf-threads-toggle").click()
    said = page.locator(".lf-thread .lf-msg.user").filter(has_text="Thanks.")
    # Named by its id, since an open rewrite holds its words in the box, not as text.
    thanks = page.locator(
        f'.lf-thread .lf-msg[data-mid="{said.get_attribute("data-mid")}"]'
    )
    thanks.locator(".lf-msg-text").dblclick()
    expect(thanks.locator(".lf-msg-editor leaf-text")).to_be_focused()
    expect(workspace.locator(".lf-msg-editor")).to_have_count(0)
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the north bracket.")


def test_walking_up_through_rewrites_shows_each_one(browser, serve):
    """↑ walking up to an earlier message opened its rewrite wherever it stood, which in
    a long thread was above the panel's top or below its foot: the user typed into a box
    they could not see. Each one opened now stands in the panel's view, clear of the
    reply row pinned at its foot."""
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    first = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "rewritten",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": "cd-q"},
        },
    )
    long = " ".join(["The steel pair held through the frost of February."] * 12)
    mine = []
    for turn in range(3):
        answer = append_carried_log_record(
            d,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Indexer",
                "session": "worker-1",
                "parent": first["id"],
                "responds": mine[-1] if mine else first["id"],
                "text": long,
            },
        )
        said = append_carried_log_record(
            d,
            {
                "kind": "reply",
                "author": "user",
                "parent": answer["id"],
                "text": f"And {turn}.",
            },
        )
        mine.append(said["id"])
    page = open_page(browser, url)
    resized(page, 1400, 600)
    page.locator(".lf-threads-toggle").click()
    thread = page.locator(f'.lf-thread:has(.lf-msg[data-mid="{first["id"]}"])')
    thread.locator(".lf-thread-reply leaf-text").focus()
    page.keyboard.press("ArrowUp")
    for name in [*reversed(mine), first["id"]]:
        editor = thread.locator(f'.lf-msg[data-mid="{name}"] .lf-msg-editor leaf-text')
        expect(editor).to_be_focused()
        rendered(page)
        # The words' first line is what the hit test at its middle finds.
        assert editor.evaluate(
            """n => {
              const b = n.getBoundingClientRect();
              let at = document.elementFromPoint(b.left + 4, b.top + 8);
              while (at?.shadowRoot) {
                const inner = at.shadowRoot.elementFromPoint(b.left + 4, b.top + 8);
                if (!inner || inner === at) break;
                at = inner;
              }
              return n === at || n.contains(at) || n.shadowRoot.contains(at);
            }"""
        ), name
        page.keyboard.press("Home")
        page.keyboard.press("ArrowUp")


def test_an_emptied_rewrite_keeps_nothing(browser, serve):
    """A rewrite cleared and left kept its empty words, so every later opening showed an
    empty box in place of the message, without saying it held anything. A rewrite keeps
    words: a page reloaded over an emptied one opens on the message's own."""
    page, _, message = _rewrite_surface(browser, serve, "panel")
    words = message.locator(".lf-msg-text")
    editor = message.locator(".lf-msg-editor leaf-text")
    words.dblclick()
    expect(editor).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    rendered(page)
    page.reload()
    wait_until_ready(page)
    if not message.is_visible():
        page.locator(".lf-threads-toggle").click()
    expect(message.locator(".lf-msg-kept")).to_have_count(0)
    words.dblclick()
    expect(editor).to_have_js_property("value", "Fit the north bracket.")


def test_a_rewrite_saves_its_exact_words(browser, serve):
    """Saving the message's own words changes nothing, but a rewrite that changes only
    their leading or trailing space saves it: that space is part of what a rewrite
    sends, as a suggestion's newline is, and the editor once compared trimmed words and
    dropped it as "No change to save"."""
    page, _, message = _rewrite_surface(browser, serve, "panel")
    editor = message.locator(".lf-msg-editor leaf-text")
    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_be_focused()
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_be_focused()
    page.keyboard.type(" ")
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    round_trip(page)
    edits = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "edit"]
    assert [e["text"] for e in edits] == ["Fit the north bracket. "]


def test_a_rewrite_under_a_finger_keeps_its_message_head(browser, serve):
    """Under a finger a message's head holds the row its control stands in. An open
    rewrite's Cancel and Save took that row's height from the room they need across, so
    a message below the first grew a head 120px tall and pushed the reply box down. The
    head keeps its row, and the box's words take the floor a field's type needs on a
    phone, the one size that changes."""
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    first = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "rewritten",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": "cd-q"},
        },
    )
    answer = append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "parent": first["id"],
            "responds": first["id"],
            "text": "Fitted.",
        },
    )
    second = append_carried_log_record(
        d,
        {"kind": "reply", "author": "user", "parent": answer["id"], "text": "Thanks."},
    )
    context = browser.new_context(
        is_mobile=True, has_touch=True, viewport={"width": 390, "height": 844}
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    message = page.locator(f'.lf-thread .lf-msg[data-mid="{second["id"]}"]')
    expect(message).to_be_visible()
    rendered(page)
    head = message.locator(".lf-msg-head")
    rest = head.bounding_box()
    message.locator(".lf-msg-edit").tap()
    expect(message.locator(".lf-msg-editor leaf-text")).to_be_focused()
    rendered(page)
    now = head.bounding_box()
    assert abs(now["height"] - rest["height"]) < 0.5, (rest, now)
    for name in ("Cancel", "Save"):
        box = message.get_by_role("button", name=name, exact=True).bounding_box()
        assert (
            now["y"] - 1 <= box["y"] + box["height"] / 2 <= now["y"] + now["height"] + 1
        )


def test_a_discarded_rewrite_hands_resume_writing_back(browser, serve):
    """Resume writing returned to a rewrite Escape had just discarded, reopening it on
    the message's own words, ahead of the reply the user had been writing. A rewrite
    put away hands Resume writing back to the place written in before it."""
    page, thread, message = _rewrite_surface(browser, serve, "panel")
    reply = thread.locator(".lf-thread-reply leaf-text").first
    reply.click()
    page.keyboard.type("A reply in progress")
    message.locator(".lf-msg-text").dblclick()
    page.keyboard.type(" and more")
    page.keyboard.press("Escape")
    expect(reply).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "A reply in progress")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)


def test_a_long_rewrite_opens_where_its_caret_stands(browser, serve):
    """A message taller than the panel opened its rewrite with the caret, after its last
    word, far below the panel's foot, so the first key jumped the view. It opens with
    the line its caret stands on in view."""
    url = serve(THREAD_DIFF_PAGE)
    long = "\n\n".join(
        f"Paragraph {n}: the steel pair held through the frost of February."
        for n in range(30)
    )
    mine = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "rewritten",
            "author": "user",
            "revision": 1,
            "text": long,
            "anchor": {"section": "cd-q"},
        },
    )
    page = open_page(browser, url)
    resized(page, 1400, 900)
    page.locator(".lf-threads-toggle").click()
    thread = page.locator(f'.lf-thread:has(.lf-msg[data-mid="{mine["id"]}"])')
    thread.locator(".lf-thread-reply leaf-text").focus()
    page.keyboard.press("ArrowUp")
    editor = thread.locator(
        f'.lf-msg[data-mid="{mine["id"]}"] .lf-msg-editor leaf-text'
    )
    expect(editor).to_be_focused()
    rendered(page)
    last = editor.evaluate(
        """n => { const box = n.getBoundingClientRect();
          const line = parseFloat(getComputedStyle(n).lineHeight);
          const list = document.querySelector('.lf-threads').getBoundingClientRect();
          const reply = document.querySelector('.lf-threads .lf-thread-reply')
            .getBoundingClientRect();
          return [box.bottom - line, box.bottom, list.top,
            Math.min(list.bottom, reply.top)]; }"""
    )
    assert last[2] <= last[0] and last[1] <= last[3] + 1, last


def test_changed_words_are_not_walked_past(browser, serve):
    """↑ from the start of a rewrite, and opening another message's in the thread, closed
    it as Escape does, and so threw away words the user had changed. Changed words hold
    ↑ for the caret, as a reply box holding words does, and stay in their box when
    another rewrite opens beside it."""
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    first = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "rewritten",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": "cd-q"},
        },
    )
    answer = append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "parent": first["id"],
            "responds": first["id"],
            "text": "Fitted.",
        },
    )
    second = append_carried_log_record(
        d,
        {"kind": "reply", "author": "user", "parent": answer["id"], "text": "Thanks."},
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-threads-toggle").click()
    thread = page.locator(f'.lf-thread:has(.lf-msg[data-mid="{first["id"]}"])')
    latest = thread.locator(f'.lf-msg[data-mid="{second["id"]}"]')
    earlier = thread.locator(f'.lf-msg[data-mid="{first["id"]}"]')
    thread.locator(".lf-thread-reply leaf-text").focus()
    page.keyboard.press("ArrowUp")
    editor = latest.locator(".lf-msg-editor leaf-text")
    expect(editor).to_be_focused()
    page.keyboard.type(" A careful addition.")
    page.keyboard.press("ControlOrMeta+Home")
    page.keyboard.press("ArrowUp")
    expect(editor).to_be_focused()
    expect(earlier.locator(".lf-msg-editor")).to_have_count(0)
    earlier.locator(".lf-msg-text").dblclick()
    expect(earlier.locator(".lf-msg-editor leaf-text")).to_be_focused()
    expect(editor).to_have_js_property("value", "Thanks. A careful addition.")


def test_opening_a_rewrite_keeps_room_the_thread_holds(browser, serve):
    """A thread holds the room news gave back while its reply box is in view, so the box
    stays under the user's hand. Opening a rewrite let all of that room go at once, moving
    the message being rewritten. Opening and closing one changes the held room only by
    the message's own change of height."""
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    mine = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": "cd-q"},
        },
    )
    long = " ".join(["The steel pair held through the frost of February."] * 12)
    agents = [
        append_carried_log_record(
            d,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Indexer",
                "session": "worker-1",
                "parent": mine["id"],
                "responds": mine["id"],
                "text": long,
            },
        )
        for _ in range(3)
    ]
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "user",
            "parent": agents[2]["id"],
            "text": "Thanks.",
        },
    )
    page = open_page(browser, url)
    resized(page, 1400, 1000)
    thread = page.locator("#cd-q .lf-page-thread").first
    reply = thread.locator(".lf-thread-reply leaf-text").first
    reply.scroll_into_view_if_needed()
    reply.click()
    rendered(page)
    append_carried_log_record(
        d,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "message": agents[1]["id"],
            "text": "Short.",
        },
    )
    told(page)
    thread.get_by_role("button", name="1 message edited", exact=True).click()
    reply.click()
    rendered(page)
    latest = thread.locator(".lf-msg").last
    held = latest.bounding_box()
    assert thread.locator(":scope > .lf-reply-space").bounding_box()["height"] > 0, (
        "the thread holds no room, so this proves nothing"
    )
    page.keyboard.press("ArrowUp")
    expect(latest.locator(".lf-msg-editor leaf-text")).to_be_focused()
    rendered(page)
    assert abs(latest.bounding_box()["y"] - held["y"]) < 0.5
    page.keyboard.press("Escape")
    rendered(page)
    assert abs(latest.bounding_box()["y"] - held["y"]) < 0.5


def test_a_second_rewrite_lands_over_a_first_still_sending(browser, serve):
    """A rewrite opened while the one before it was still on its way named that one by
    its pending id, which the log never knew, and was refused as stale. It names it by
    the id the log gave it, once the log has answered."""
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    mine = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "rewritten",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": "cd-q"},
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-threads-toggle").click()
    message = page.locator(f'.lf-thread .lf-msg[data-mid="{mine["id"]}"]')
    held = []
    page.route(
        "**/api/event",
        lambda route: (
            held.append(route)
            if route.request.method == "POST" and not held
            else route.continue_()
        ),
    )
    editor = message.locator(".lf-msg-editor leaf-text")
    message.locator(".lf-msg-text").dblclick()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("First.")
    page.keyboard.press("Enter")
    holding(page, held, 1, "the first rewrite")
    expect(message.locator(".lf-msg-text")).to_have_text("First.")
    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Second.")
    page.keyboard.press("Enter")
    held[0].continue_()
    round_trip(page)
    edits = [e for e in events_model.read_events(d) if e["kind"] == "edit"]
    assert [(e["text"], e["base"]) for e in edits] == [
        ("First.", mine["id"]),
        ("Second.", edits[0]["id"]),
    ]
    expect(message.locator(".lf-msg-kept")).to_have_count(0)
    page.unroute_all(behavior="wait")


def test_a_second_rewrite_over_a_refused_first_goes_with_it(browser, serve):
    """A rewrite written over one still sending names that one, by its pending id. When
    the log refuses the first, those written over it have nothing left to stand on: they
    go with it, the latest words back in the message's rewrite draft, rather than
    left on the message as unsent words over an id the log never took."""
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    mine = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "rewritten",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": "cd-q"},
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-threads-toggle").click()
    message = page.locator(f'.lf-thread .lf-msg[data-mid="{mine["id"]}"]')
    held = []
    later = []

    def route(route):
        if route.request.method != "POST":
            route.continue_()
        elif not held:
            held.append(route)
        else:
            later.append(route.request.post_data_json)
            route.continue_()

    page.route("**/api/event", route)
    editor = message.locator(".lf-msg-editor leaf-text")
    message.locator(".lf-msg-text").dblclick()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("First.")
    page.keyboard.press("Enter")
    holding(page, held, 1, "the first rewrite")
    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Second.")
    page.keyboard.press("Enter")
    # A third over the second names only the second, so it goes by way of it.
    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Third.")
    page.keyboard.press("Enter")

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
    assert [event for event in later if event.get("kind") == "edit"] == []
    assert not [e for e in events_model.read_events(d) if e["kind"] == "edit"]
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the north bracket.")
    assert stored_draft_text(page, f"rewrite:{mine['id']}") == "Third."
    consume_browser_errors(page, http_error_console(400))
    page.unroute_all(behavior="wait")


def test_typing_in_a_long_rewrite_keeps_the_view(browser, serve):
    """In a long message in the page's flow, each key in its rewrite aimed a landing at
    the whole box, pulling its top into view and then back to the caret. Typing keeps
    the view where the caret is."""
    url = serve(THREAD_DIFF_PAGE)
    long = "\n\n".join(
        f"Paragraph {n}: the steel pair held through the frost of February."
        for n in range(30)
    )
    mine = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": long,
            "anchor": {"section": "cd-q"},
        },
    )
    page = open_page(browser, url)
    resized(page, 1400, 900)
    thread = page.locator("#cd-q .lf-page-thread").first
    reply = thread.locator(".lf-thread-reply leaf-text").first
    reply.scroll_into_view_if_needed()
    reply.click()
    page.keyboard.press("ArrowUp")
    editor = thread.locator(
        f'.lf-msg[data-event="{mine["id"]}"] .lf-msg-editor leaf-text'
    )
    expect(editor).to_be_focused()
    rendered(page)
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.type("Z")
    rendered(page)
    after = page.evaluate("() => document.scrollingElement.scrollTop")
    assert abs(after - before) < 30, (before, after)


def test_a_rewrite_leaves_a_card_at_the_windows_foot_as_it_stood(browser, serve):
    """A card whose target stands low in the window stands against the window's foot,
    where it grows no taller than the room under its top, or than it has stood. Saving
    a rewrite of its message unchanged left the message a scrolling box clipped
    mid-line, as did discarding words shortened in the rewrite: the open rewrite was
    shorter than the message, and the card shrank with it from the top, the window's
    foot keeping its foot, and grew no taller than it then stood. It now grows back to
    the tallest it stood while its line stays put.

    Unchanged words were shorter in the card's rewrite because its field ended them
    17px further out than the message did, so lines rewrapped as it opened. They now
    end where the message's do."""
    url = serve(LONG_PAGE)
    mine = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": (
                "/dispatch\n\nI think this makes sense, but we need to think about "
                "how to change our Todos first, to handle a tree structure.\n\nLay out "
                "options for our ontology.\n\nAlso, look first at how we can complete "
                "any existing clean-ups, given recent changes, as a precursor to "
                "embarking on adding this\n\nThen after that we can come back to this "
                "session and look at changing our implementation"
            ),
            "anchor": {"section": "p30"},
        },
    )
    page = open_page(browser, url)
    resized(page, 1512, 860)
    page.locator("#p30").evaluate("n => n.scrollIntoView({block: 'end'})")
    rendered(page)
    page.locator('[data-lf-margin-for="p30"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    message = card.locator(f'.lf-msg[data-event="{mine["id"]}"]')
    words = message.locator(".lf-msg-text")
    editor = message.locator(".lf-msg-editor leaf-text")
    expect(message).to_be_visible()
    rendered(page)
    assert card.get_attribute("data-lf-plane") == "window", (
        "the card does not stand against the window's foot, so this proves nothing"
    )
    column = """n => { const r = n.getBoundingClientRect(), s = getComputedStyle(n);
      return [r.left + parseFloat(s.paddingLeft) + parseFloat(s.borderLeftWidth),
              r.right - parseFloat(s.paddingRight) - parseFloat(s.borderRightWidth)]; }"""
    text_column = words.evaluate(column)

    def standing():
        return {
            "card": card.bounding_box(),
            "words": words.evaluate(FIRST_LINE),
            "scrolls": card.locator(".lf-thread-transcript").evaluate(
                "t => t.scrollHeight > t.clientHeight"
            ),
        }

    stood = standing()
    assert not stood["scrolls"]

    def as_it_stood():
        now = standing()
        for side in ("y", "height"):
            assert abs(now["card"][side] - stood["card"][side]) < 0.5, (now, stood)
        assert abs(now["words"][1] - stood["words"][1]) < 0.5, (now, stood)
        assert not now["scrolls"], now

    words.dblclick()
    expect(editor).to_be_focused()
    rendered(page)
    for edge, at in zip(editor.evaluate(column), text_column):
        assert abs(edge - at) < 0.5, (editor.evaluate(column), text_column)
    # Open, the rewrite takes the message's place exactly: the card neither grows nor
    # scrolls the rewrite's top under the message's head, and its words keep their line.
    for side in ("y", "height"):
        assert abs(card.bounding_box()[side] - stood["card"][side]) < 0.5
    assert not card.locator(".lf-thread-transcript").evaluate(
        "t => t.scrollHeight > t.clientHeight"
    )
    assert abs(editor.evaluate(FIRST_LINE)[1] - stood["words"][1]) < 0.5
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    rendered(page)
    as_it_stood()

    words.dblclick()
    expect(editor).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Short.")
    rendered(page)
    page.keyboard.press("Escape")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    rendered(page)
    as_it_stood()


def test_a_card_at_the_windows_foot_grows_back_to_how_it_stood(browser, serve):
    """A message taller than the rewrite's field, which scrolls past half the window,
    shrinks a card standing against the window's foot as its rewrite opens. The card
    kept its foot there and dropped its top, and once saved unchanged it came back a
    scrolling box clipped by what it had shrunk, as it did once shorter words were saved
    and then the long ones again. It now grows back to the tallest it stood while its
    line stays put."""
    url = serve(LONG_PAGE)
    line = "The steel pair held through the frost of February, and the bracket with it."
    long = "\n\n".join([line] * 9)
    mine = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": long,
            "anchor": {"section": "p30"},
        },
    )
    page = open_page(browser, url)
    resized(page, 1512, 860)
    page.locator("#p30").evaluate("n => n.scrollIntoView({block: 'end'})")
    rendered(page)
    page.locator('[data-lf-margin-for="p30"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    message = card.locator(f'.lf-msg[data-event="{mine["id"]}"]')
    body = message.locator(".lf-msg-body")
    editor = message.locator(".lf-msg-editor leaf-text")
    expect(message).to_be_visible()
    rendered(page)
    assert card.get_attribute("data-lf-plane") == "window", (
        "the card does not stand against the window's foot, so this proves nothing"
    )

    def standing():
        return {
            "card": card.bounding_box(),
            "words": body.bounding_box()["y"],
            "scrolls": card.locator(".lf-thread-transcript").evaluate(
                "t => t.scrollHeight > t.clientHeight"
            ),
        }

    stood = standing()
    assert not stood["scrolls"]

    def as_it_stood():
        now = standing()
        for side in ("y", "height"):
            assert abs(now["card"][side] - stood["card"][side]) < 0.5, (now, stood)
        assert abs(now["words"] - stood["words"]) < 0.5, (now, stood)
        assert not now["scrolls"], now

    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_be_focused()
    rendered(page)
    assert editor.evaluate("n => n.scrollHeight > n.clientHeight"), (
        "the rewrite's field holds the whole message, so nothing shrinks"
    )
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    rendered(page)
    as_it_stood()
    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Short.")
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-text")).to_have_text("Short.")
    rendered(page)
    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text(long)
    rendered(page)
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    rendered(page)
    as_it_stood()


def test_saving_one_of_two_open_rewrites_leaves_no_gap(browser, serve):
    """With a changed rewrite left open higher in the thread, saving a shorter one below
    it followed the open one and not the saved one, so the reply box jumped back down
    and the room the shorter words gave back stayed as a gap."""
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    first = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": "cd-q"},
        },
    )
    answer = append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "parent": first["id"],
            "responds": first["id"],
            "text": "Fitted.",
        },
    )
    long = " ".join(["The steel pair held through the frost of February."] * 4)
    second = append_carried_log_record(
        d, {"kind": "reply", "author": "user", "parent": answer["id"], "text": long}
    )
    page = open_page(browser, url)
    resized(page, 1400, 900)
    thread = page.locator("#cd-q .lf-page-thread").first
    earlier = thread.locator(f'.lf-msg[data-event="{first["id"]}"]')
    latest = thread.locator(f'.lf-msg[data-event="{second["id"]}"]')
    reply = thread.locator(".lf-thread-reply leaf-text").first
    earlier.scroll_into_view_if_needed()
    earlier.locator(".lf-msg-text").dblclick()
    page.keyboard.type(" And the east.")
    latest.locator(".lf-msg-text").dblclick()
    expect(latest.locator(".lf-msg-editor leaf-text")).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Short.")
    rendered(page)
    typed = reply.bounding_box()["y"], latest.bounding_box()["height"]
    page.keyboard.press("Enter")
    expect(latest.locator(".lf-msg-text")).to_have_text("Short.")
    round_trip(page)
    rendered(page)
    # The reply box moves by what the message gave back as its box closed, and no more.
    given_back = latest.bounding_box()["height"] - typed[1]
    assert abs(reply.bounding_box()["y"] - (typed[0] + given_back)) < 0.5, (
        typed,
        given_back,
        reply.bounding_box(),
    )
    expect(earlier.locator(".lf-msg-editor leaf-text")).to_have_js_property(
        "value", "Fit the north bracket. And the east."
    )


@pytest.mark.watch_shifts
def test_a_rewrite_saved_under_the_resolved_filter_goes_with_its_thread(browser, serve):
    """Saving a rewrite reopens its thread, which took the card out of the Resolved
    filter it was written under and dropped the user's focus on the list. The save
    carries them into the open thread, landing in its reply box, with nothing moving
    after the key (#46, the user's decision, 2026-10-07)."""
    page, thread, message = _rewrite_surface(browser, serve, "panel", resolved=True)
    resolved_filter = page.locator('[data-filter-value="resolved"]')
    reply = thread.locator(":scope > .lf-thread-reply leaf-text")
    held = []
    page.route(
        "**/api/event",
        lambda route: (
            held.append(route) if route.request.method == "POST" else route.continue_()
        ),
    )
    message.locator(".lf-msg-text").dblclick()
    page.keyboard.press("End")
    page.keyboard.type(" Now.")
    page.keyboard.press("Enter")
    holding(page, held, 1, "the rewrite")
    expect(reply).to_be_focused()
    expect(resolved_filter).to_have_attribute("aria-pressed", "false")
    held.pop().continue_()
    round_trip(page)
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the north bracket. Now.")
    expect(reply).to_be_focused()
    page.unroute_all(behavior="wait")


@pytest.mark.watch_shifts
def test_a_refused_rewrite_puts_the_resolved_filter_back(browser, serve):
    """A refused rewrite saved under the Resolved filter puts that filter and the user
    back on the thread, and its words wait on the message. The refusal lands after
    the input window, so nothing it puts back may move."""
    page, thread, message = _rewrite_surface(browser, serve, "panel", resolved=True)
    resolved_filter = page.locator('[data-filter-value="resolved"]')
    held = []
    page.route(
        "**/api/event",
        lambda route: (
            held.append(route) if route.request.method == "POST" else route.continue_()
        ),
    )
    message.locator(".lf-msg-text").dblclick()
    page.keyboard.press("End")
    page.keyboard.type(" Now.")
    page.keyboard.press("Enter")
    holding(page, held, 1, "the refused rewrite")
    expect(resolved_filter).to_have_attribute("aria-pressed", "false")
    rendered(page)
    # Chrome reports no shift within 500ms of input, so the refusal lands after it.
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    round_trip(page)
    expect(resolved_filter).to_have_attribute("aria-pressed", "true")
    expect(thread.locator(":scope > .lf-thread-summary")).to_be_focused()
    expect(message.locator(".lf-msg-kept")).to_have_text("unsaved edit")
    # The reply box still holds the card open, so Reopen stands in Resolve's place in
    # the head, in the room the head keeps for it: the word ran over the pencil.
    pencil = message.locator(".lf-msg-edit").bounding_box()
    reopen = thread.locator(".lf-thread-meta-actions .lf-reopen").bounding_box()
    assert pencil["x"] + pencil["width"] <= reopen["x"], (pencil, reopen)
    page.unroute_all(behavior="wait")


def test_a_refusal_leaves_the_view_on_a_thread_the_user_spoke_in_since(browser, serve):
    """A refused rewrite puts back the view it left only while the user has not acted
    since: once they have replied in the reopened thread, the Resolved view would take
    away the thread they are working in."""
    page, thread, message = _rewrite_surface(browser, serve, "panel", resolved=True)
    resolved_filter = page.locator('[data-filter-value="resolved"]')
    reply = thread.locator(":scope > .lf-thread-reply leaf-text")
    held = []
    posts = []

    def hold_first(route):
        if route.request.method != "POST":
            return route.continue_()
        posts.append(route)
        if len(posts) == 1:
            return held.append(route)
        return route.continue_()

    page.route("**/api/event", hold_first)
    message.locator(".lf-msg-text").dblclick()
    page.keyboard.press("End")
    page.keyboard.type(" Now.")
    page.keyboard.press("Enter")
    holding(page, held, 1, "the rewrite")
    expect(reply).to_be_focused()
    write(reply, "And the south one.")
    page.keyboard.press("ControlOrMeta+Enter")
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    round_trip(page)
    expect(resolved_filter).to_have_attribute("aria-pressed", "false")
    expect(thread).to_be_visible()
    page.unroute_all(behavior="wait")


def test_a_reopen_in_a_view_that_still_holds_its_thread_keeps_that_view(browser, serve):
    """Reopening a thread the current view goes on showing, as under All with a search
    its words match, leaves the view as the user set it: only a view that leaves the
    thread out is changed to one that holds it."""
    page, thread, _ = _rewrite_surface(browser, serve, "panel", resolved=True)
    page.locator('[data-filter-value="resolved"]').click()
    search = page.get_by_role("searchbox", name="Find in threads")
    search.fill("north bracket")
    expect(thread).to_be_visible()
    focus_panel_thread(thread)
    with sending(page, "the reopen"):
        page.keyboard.press("r")
    round_trip(page)
    expect(search).to_have_value("north bracket")
    expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(thread.locator(":scope > .lf-thread-reply leaf-text")).to_be_focused()


def test_a_rewrite_in_a_card_news_kept_goes_with_its_thread(browser, serve):
    """A card news keeps in a view it no longer belongs to, as the agent reopening a
    thread shown under Resolved does, becomes the user's once they send words in it:
    their rewrite takes them with the thread into the view that holds it, rather than
    leaving an open thread under a Resolved view that counts none."""
    page, thread, message = _rewrite_surface(browser, serve, "panel", resolved=True)
    thread.locator(":scope > .lf-thread-summary").click()
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "unresolve",
            "author": "agent",
            "agent": "Indexer",
            "parent": thread.get_attribute("data-id"),
        },
    )
    told(page)
    rendered(page)
    resolved_filter = page.locator('[data-filter-value="resolved"]')
    expect(resolved_filter).to_have_attribute("aria-pressed", "true")
    expect(thread).to_be_visible()
    message.locator(".lf-msg-text").dblclick()
    page.keyboard.press("End")
    page.keyboard.type(" Now.")
    page.keyboard.press("Enter")
    expect(resolved_filter).to_have_attribute("aria-pressed", "false")
    expect(thread.locator(":scope > .lf-thread-reply leaf-text")).to_be_focused()
    round_trip(page)
