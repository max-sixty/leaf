"""The document's shared, semantic margin map, with the pages and helpers its test
modules share."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import SUGGESTION_PAGE
from render_harness import (
    leaf_page,
    open_page,
    regions_side_by_side,
    resized,
    round_trip,
    scroll_settled,
    sending,
    suggestion_control,
    write,
)

from leaf import event_log as events_model
from leaf.render_checks import rendered

COMMENT_ON_OBLIGATION = {
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "text": "Check whether these jobs can share one visit.",
    "anchor": {"section": "bracket"},
}


# A comment whose lines take the card's whole measure, for a case about the room a
# placement gives the card rather than the width a short thread takes inside it.
PARAGRAPH_ON_OBLIGATION = {
    **COMMENT_ON_OBLIGATION,
    "text": "Check whether these jobs can share one visit: the mounts, the bracket and "
    "the cable run all need the same ladder and the same afternoon, and one visit would "
    "halve the call-out charge.",
}


ACTION_ON_OBLIGATION = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "bracket",
    "action": "choose",
    "detail": {"value": ["br-steel"]},
    "meaning": {
        "scope": "page",
        "unit": "bracket",
        "depends": ["br-steel", "bracket"],
        "answer": None,
        "state": {
            "origin": "lf-options",
            "unit": "widget",
            "record": {"kind": "attribute", "attr": "chosen"},
            "creates": None,
            "decides": False,
            "detail": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "array",
                        "items": {"type": "string"},
                        "uniqueItems": True,
                    }
                },
                "required": ["value"],
                "additionalProperties": False,
            },
        },
    },
}


COMMENT_ON_SUGGESTION = {
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "text": "Check this wording before accepting it.",
    "anchor": {"section": "sug-refill"},
}


def resized_shell(page, inline_size, height):
    """Resize by the container's own width, independent of scrollbar posture."""
    viewport_width = page.viewport_size["width"]
    resized(page, viewport_width, height)
    for _ in range(3):
        shell_width = page.evaluate("() => document.body.getBoundingClientRect().width")
        difference = inline_size - shell_width
        if abs(difference) <= 0.5:
            return
        viewport_width += round(difference)
        resized(page, viewport_width, height)
    assert page.evaluate(
        "() => document.body.getBoundingClientRect().width"
    ) == pytest.approx(inline_size, abs=0.5)


ACTION_PAGE = SUGGESTION_PAGE.replace(
    '<main class="layout-column">',
    '<main class="layout-column"><section id="action-section">',
).replace(
    "</main>",
    """
<lf-draft id="draft-ops"><pre>
  Run the migration before deploying.
</pre></lf-draft>
<div style="height: 500px" aria-hidden="true"></div>
    </section></main>""",
)


MARGIN_ENTRY_KEYBOARD_PAGE = SUGGESTION_PAGE.replace(
    '<p id="replace">',
    '<a id="before-margin-entries" href="#replace">Before margin entries</a><p id="replace">',
    1,
).replace(
    '<p id="insert">',
    '<a id="after-margin-entries" href="#insert">After margin entries</a><p id="insert">',
    1,
)


DENSE_SUGGESTIONS_PAGE = leaf_page(
    "Dense suggestions",
    """<p id="bg-neighbors">Pack
  <lf-suggestion id="bg-neighbor-a"><lf-old>two</lf-old><lf-new>three</lf-new></lf-suggestion>
  pencils,
  <lf-suggestion id="bg-neighbor-b"><lf-old>red</lf-old><lf-new>blue</lf-new></lf-suggestion>
  paper, and a
  <lf-suggestion id="bg-neighbor-c"><lf-old>large</lf-old><lf-new>small</lf-new></lf-suggestion>
  map.</p>""",
)


def _unfold(item):
    """Open a pin folded for want of room, as a user does to reach its actions."""
    if item.get_attribute("data-lf-folded") is not None:
        item.locator(".lf-margin-more").click()


def _unfold_suggestion_undo(page, target):
    """Find Undo where a settled suggestion now perches, even if its slot vanished."""
    control = suggestion_control(page, target, "undo", visible=False)
    _unfold(control.locator("xpath=ancestor::*[@data-lf-margin-for][1]"))
    return control


# Margin action rows on a page of their own: three suggestions sharing one paragraph, so
# a decision on one reflows the words the others stand by; a draft; and a suggestion
# whose thread and reaction in force crowd its row.
MARGIN_ACTIONS_PAGE = leaf_page(
    "Margin actions",
    """
<h1 id="t">Margin actions</h1>
<p id="change-forms">
  <span><strong>Replace.</strong> The sample meeting starts at
    <lf-suggestion id="s-replace"><lf-old>nine.</lf-old><lf-new>ten.</lf-new></lf-suggestion></span>
  <span><strong>Insert.</strong> Bring a notebook.
    <lf-suggestion id="s-insert"><lf-new> A pencil is useful too.</lf-new></lf-suggestion></span>
  <span><strong>Delete.</strong> The room is upstairs.
    <lf-suggestion id="s-delete"><lf-old> Please arrive an hour early.</lf-old></lf-suggestion></span>
</p>
<p id="editing-guide">Edit the draft below, then save it.</p>
<lf-draft id="d-draft"><pre>Write a **different invitation** here.</pre></lf-draft>
<p id="crowded-line">Use the
  <lf-suggestion id="s-crowded"><lf-old>courtyard</lf-old><lf-new>covered terrace</lf-new></lf-suggestion>
  for the practice session.</p>
""",
)


# The right edge of the column's words, inside `main`'s padding. A thread card beside
# them stands clear of it, over the margin cluster if its measure needs that room.
WORDS_RIGHT = """() => {
  const main = document.querySelector('main');
  return main.getBoundingClientRect().right - parseFloat(getComputedStyle(main).paddingRight);
}"""


# A thread longer than the card at 1440x900, so its transcript scrolls under the
# reply pinned to the card's foot.
LONG_THREAD_PAGE = leaf_page(
    "Long thread",
    """
<h1 id="title">Long thread</h1>
<p>The open questions follow.</p>
<section id="open"><h2>What this leaves open</h2>
<p>Two layers close onto the control that opened them rather than the page.</p>
</section>
""",
)


LONG_THREAD_ROOT = {
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "text": "What should we do about these, and why are they hard to follow?",
    "anchor": {"section": "open"},
    "id": "a" * 32,
    "ts": "2026-09-18T18:29:21-07:00",
}


LONG_THREAD = [
    LONG_THREAD_ROOT,
    {
        "kind": "reply",
        "author": "agent",
        "agent": "Claude",
        "parent": LONG_THREAD_ROOT["id"],
        "responds": LONG_THREAD_ROOT["id"],
        "revision": 1,
        "text": "\n\n".join(
            f"{n}. A layer the mouse opened closes to the page, so the Escape that "
            "follows a click lands where the user was reading rather than on the "
            "button they pressed."
            for n in range(1, 13)
        ),
        "id": "b" * 32,
        "ts": "2026-09-18T18:34:26-07:00",
    },
    {
        "kind": "reply",
        "author": "user",
        "parent": LONG_THREAD_ROOT["id"],
        "revision": 1,
        "text": "Start with the first two.",
        "id": "c" * 32,
        "ts": "2026-09-18T18:42:22-07:00",
    },
]


def open_long_thread(browser, serve, height=900):
    """The long thread's margin card, which opens on its latest message, scrolled
    partway back up."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=LONG_THREAD))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, height)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    transcript = preview.locator(".lf-thread-transcript")
    room = transcript.evaluate("list => list.scrollHeight - list.clientHeight")
    assert room > 300, f"the transcript scrolls {room}px, too little to stand mid-way"
    transcript.hover()
    page.wait_for_function(
        "([list, room]) => list.scrollTop >= room - 1",
        arg=[transcript.element_handle(), room],
    )
    page.mouse.wheel(0, -(room // 2))
    page.wait_for_function(
        "([list, room]) => list.scrollTop < room - 100",
        arg=[transcript.element_handle(), room],
    )
    scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")
    return page, preview, transcript


ON_THE_PAGE = (
    "() => document.activeElement !== document.body && "
    "!document.activeElement.closest('.lf-chrome')"
)


def leave_card(page):
    """Escape from a card's thread takes the card down in one press, whatever opened it,
    and leaves the user beside the target it is about rather than on any control."""
    preview = page.locator(".lf-margin-preview")
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")


def seeded_thread(page, page_dir, passage):
    """Comment on a passage by pointer and let the card go, leaving its thread behind."""
    page.locator(passage).click(click_count=3)
    page.locator(".lf-fab-input").click()
    page.keyboard.type(f"A thread on {passage}.")
    with sending(page, f"the comment on {passage}"):
        page.keyboard.press("ControlOrMeta+Enter")
    sent = events_model.read_events(page_dir)[-1]
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()
    leave_card(page)
    return sent


# Observe the actual editor glyphs without changing its closed-root behavior.
MARGIN_EDITOR_ROOTS = """window.marginEditorRoots = new WeakMap();
const attach = Element.prototype.attachShadow;
Element.prototype.attachShadow = function(options) {
    const root = attach.call(this, options);
    if (this.localName === 'leaf-text') window.marginEditorRoots.set(this, root);
    return root;
};"""


# Native text fragments grouped into visual lines, rather than inferred from width
# or the runtime's placement reading. DOM text-node splits do not change a line.
MARGIN_TEXT_LINES = """node => {
    const lines = new Map();
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
        const range = document.createRange();
        range.selectNodeContents(walker.currentNode);
        for (const rect of range.getClientRects()) {
            if (!rect.width) continue;
            const line = lines.get(rect.top);
            lines.set(rect.top, line ? {
                left: Math.min(line.left, rect.left), right: Math.max(line.right, rect.right),
                height: Math.max(line.height, rect.height),
            } : {left: rect.left, right: rect.right, height: rect.height});
        }
    }
    return [...lines].sort(([a], [b]) => a - b)
        .map(([, line]) => [line.right - line.left, line.height]);
}"""


def send_anchored_comment(page, text):
    """The gesture the contract's sentence is about: a comment accepted on a passage."""
    page.locator("#mounts-p").click(click_count=3)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), text)
    rendered(page)
    frame = page.locator(".lf-fab-bar").bounding_box()
    lines = page.locator(".lf-fab-input").evaluate(
        "(box, read) => eval(read)(window.marginEditorRoots.get(box).querySelector('.cm-content'))",
        MARGIN_TEXT_LINES,
    )
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    accepted = page.locator(".lf-margin-preview .lf-msg-body").first.evaluate(
        MARGIN_TEXT_LINES
    )
    assert len(accepted) == len(lines), (lines, accepted)
    for actual, expected in zip(accepted, lines, strict=True):
        assert actual == pytest.approx(expected, abs=0.5), (lines, accepted)
    return frame["x"], len(lines)


# Where a card and its reply stand: the card's edges, the first turn's top, the reply's
# edges and scroll (its first line stands at its top only while it is unscrolled), the
# visible action's top, and the window's head and foot the card stops at.
CARD_AND_REPLY = """async () => {
  const card = document.querySelector('.lf-margin-preview');
  const box = card.getBoundingClientRect();
  const editor = card.querySelector('leaf-text');
  const reply = editor.getBoundingClientRect();
  const geometry = await window.__lfWidgetApi();
  return {cardTop: box.top, cardBottom: box.bottom,
          turn: card.querySelector('.lf-msg').getBoundingClientRect().top,
          editorTop: reply.top, editorBottom: reply.bottom, scrolled: editor.scrollTop,
          send: card.querySelector('.lf-thread-reply .lf-compose-field > button:not([hidden])')
            .getBoundingClientRect().top,
          placement: card.dataset.lfThreadPlacement,
          head: geometry.shownWindow({gap: 8, across: box}).top,
          foot: geometry.shownWindow({gap: 8, across: box}).bottom};
}"""


def drafting_in_a_short_card(browser, serve, width, height):
    """A one-comment thread's card at this window, a word typed into its open reply."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]))
    page.emulate_media(reduced_motion="reduce")
    resized(page, width, height)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    editor = preview.locator("leaf-text")
    expect(editor).to_be_focused()
    editor.type("words")
    rendered(page)
    return page, preview, editor


DRAFTING_CARD = """preview => {
  const editor = preview.querySelector('leaf-text').getBoundingClientRect();
  return {side: preview.dataset.lfThreadPlacement,
          editorTop: Math.round(editor.top), editorFoot: Math.round(editor.bottom)};
}"""


def _comment_on(section, text="A comment on this.", quote=None):
    anchor = {"section": section, **({"quote": quote} if quote else {})}
    return {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": text,
        "anchor": anchor,
    }


PANE_PIN_PAGE = leaf_page(
    "a pin in a pane",
    """
  <div id="pin-split">
    <lf-pane id="pin-pane" label="Findings">
      <div>
        <div style="height: 200px"></div>
        <p id="pane-top">The first finding, commented on.</p>
        <div style="height: 1600px"></div>
        <p id="pane-end">The last finding.</p>
      </div>
    </lf-pane>
    <lf-pane id="other-pane" label="Notes"><div><p>Notes.</p></div></lf-pane>
  </div>
""",
    head=regions_side_by_side("pin-split"),
    layout="workspace",
)


def _focused_editor_caret(page):
    """Read the real caret inside the control's closed root, through Chrome's DOM."""
    session = page.context.new_cdp_session(page)
    try:
        focused = session.send(
            "Runtime.evaluate", {"expression": "document.activeElement"}
        )["result"]["objectId"]
        node = session.send("DOM.describeNode", {"objectId": focused, "depth": 1})[
            "node"
        ]
        root = session.send(
            "DOM.resolveNode",
            {"backendNodeId": node["shadowRoots"][0]["backendNodeId"]},
        )["object"]["objectId"]
        return session.send(
            "Runtime.callFunctionOn",
            {
                "objectId": root,
                "returnByValue": True,
                "functionDeclaration": """function() {
                  const caret = this.getSelection().getRangeAt(0).getBoundingClientRect();
                  const box = this.host.getBoundingClientRect();
                  return {caretTop: caret.top, caretBottom: caret.bottom,
                    boxTop: box.top, boxBottom: box.bottom,
                    selection: this.host.selectionEnd, length: this.host.value.length};
                }""",
            },
        )["result"]["value"]
    finally:
        session.detach()
