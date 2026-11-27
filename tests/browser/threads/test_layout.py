"""How threads are laid out and styled: message and card heads, floating surfaces
under zoom and short windows, and the chrome's rules staying apart from page and package
styles."""

import json
import re
from datetime import datetime, timedelta

import pytest
from interact_support import PLUGIN_ROOT, append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    HOLD_MOTION,
    PANEL_PAGE,
    THREAD_DIFF_PAGE,
    live_url,
    panel_comment,
)
from render_harness import (
    LONG_PAGE,
    example_media,
    holding,
    leaf_page,
    open_page,
    resized,
    round_trip,
    scroll_settled,
    select_words,
    sending,
    told,
    write,
)

from browser.margin import MARGIN_EDITOR_ROOTS
from browser.threads import (
    LANDING_WORDS,
    _shadow_tree_widget,
    append_agent_reply,
    claim_for_codex,
    long_diff_thread,
    open_panel_thread,
    paste_image,
)
from leaf.agents import thread as thread_model
from leaf.log import event_log as events_model
from leaf.source.render_checks import one_frame, rendered
from leaf_dev.browser import PANEL_THREAD

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize(("touch", "surface"), [(False, "panel"), (True, "margin")])
def test_thread_actions_share_consistently_sized_message_headers(
    browser, serve, touch, surface
):
    """A thread's actions stand on its view's head line, off the messages' rows, in
    the floating panel and on a margin card alike.

    Controls must not give the opening message a different metadata-to-body gap
    from later user and agent messages. Every header holds the input's target floor,
    and each body keeps the conversation's full reading width.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "testing", None if surface == "panel" else {"section": "lede"}
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root,
            "revision": 1,
            "text": "Another thought on the same passage.",
        },
    )
    append_agent_reply(serve.page_dir, root, "Testing received successfully.")
    context = browser.new_context(has_touch=touch, is_mobile=touch)
    page = open_page(browser, url, context=context)
    if surface == "panel":
        card = open_panel_thread(page, root)
    else:
        page.locator(".lf-margin-marker").first.click()
        card = page.locator(".lf-margin-preview .lf-page-thread")
        expect(card).to_be_visible()
    for width in (1440, 390) if surface == "panel" else (1440, 1024):
        resized(page, width, 900)
        rendered(page)
        geometry = card.evaluate(
            """card => {
              const box = selector => card.querySelector(selector).getBoundingClientRect();
              const title = card.querySelector('.lf-thread-head')?.getBoundingClientRect();
              const head = box('.lf-msg-head');
              // The panel's Resolve stands among its view's controls, outside the thread,
              // and a card's on its head line, over the first message.
              const action = card.querySelector('.lf-resolve')?.getBoundingClientRect()
                ?? null;
              const body = box('.lf-msg-body');
              return {
                headerGap: title ? head.top - title.bottom : null,
                messageGaps: [...card.querySelectorAll('.lf-msg')].map(message => {
                  const name = message.querySelector('.lf-msg-head b').getBoundingClientRect();
                  const body = message.querySelector('.lf-msg-body').getBoundingClientRect();
                  return body.top - name.bottom;
                }),
                actionBottom: action?.bottom, headTop: head.top,
                bodyLeft: body.left, headLeft: head.left,
                bodyRight: body.right, actionRight: action?.right,
              };
            }"""
        )
        assert (geometry["actionBottom"] is None) == (surface == "panel"), geometry
        if geometry["actionBottom"] is not None:
            assert geometry["actionBottom"] <= geometry["headTop"] + 0.5, geometry
            assert geometry["bodyRight"] >= geometry["actionRight"], geometry
        if geometry["headerGap"] is not None:
            assert 0 <= geometry["headerGap"] <= 12, geometry
        assert len(geometry["messageGaps"]) == 3, geometry
        assert max(geometry["messageGaps"]) - min(geometry["messageGaps"]) < 0.01, (
            geometry
        )
        assert geometry["bodyLeft"] == geometry["headLeft"], geometry


FIRST_LINE = """root => {
  const words = document.createRange();
  words.selectNodeContents(root);
  return words.getClientRects()[0].top;
}"""


def named_in_place(page, serve, request, root):
    """Name the open card's thread as an agent holding the page does, through the
    placeholder that shows while it names it, and assert neither step moves the card
    or its first message's words."""
    card = page.locator(".lf-margin-preview")
    heading = card.locator(".lf-margin-thread-title")

    def where():
        return {
            "card": card.evaluate("card => card.getBoundingClientRect().top"),
            "words": card.locator(".lf-msg-text").first.evaluate(FIRST_LINE),
        }

    expect(heading).to_be_hidden()
    rendered(page)
    before = where()
    claim_for_codex(serve.page_dir, request)
    told(page)
    expect(heading.locator(".lf-thread-name-pending")).to_be_visible()
    rendered(page)
    assert where() == pytest.approx(before, abs=0.5), "the placeholder moved them"
    append_carried_log_record(
        serve.page_dir,
        thread_model.title_event(
            root, "Workshop access", {"agent": "Codex", "session": "codex-thread"}
        ),
    )
    told(page)
    expect(heading).to_have_text("Workshop access")
    expect(heading).to_be_visible()
    rendered(page)
    assert where() == pytest.approx(before, abs=0.5), "the title moved them"
    return before


def test_a_comment_s_words_stay_put_from_send_until_its_title_comes(
    browser, serve, request
):
    """A comment's words stand where the box held them once Send makes the box a card,
    and stay there while the card's head line, which holds the card's presses from the
    start, takes the placeholder that shows while an agent names the thread and then
    the title."""
    page = open_page(browser, serve(PANEL_PAGE))
    resized(page, 1440, 900)
    page.locator("#how-store").click(modifiers=["Alt"], position={"x": 30, "y": 8})
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.keyboard.insert_text("Is the workshop room accessible?")
    rendered(page)
    typed = page.locator(".lf-fab-input").evaluate(FIRST_LINE)
    page.keyboard.press("Enter")
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", re.compile(".+"))
    round_trip(page)
    (root,) = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    sent = named_in_place(page, serve, request, root)
    assert sent["words"] == pytest.approx(typed, abs=0.5), "Send moved the words"


def test_a_card_s_head_line_keeps_its_height_in_large_type(browser, serve, request):
    """Where the reader's font size makes a line of the name face taller than a head's
    28px, the card's head line takes that height before its title comes, as its
    messages' heads do, so the placeholder and the title still move nothing."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Is the workshop room accessible?", {"section": "h-how"}
    )
    page = open_page(browser, url)
    resized(page, 1440, 900)
    page.evaluate("() => { document.documentElement.style.fontSize = '28px'; }")
    rendered(page)
    page.locator('[data-lf-margin-for="h-how"] .lf-margin-marker').click()
    named_in_place(page, serve, request, root)


def test_a_later_message_copies_its_markdown_from_the_card_s_edge(browser, serve):
    """A margin card's message heads span the card under its head line, so Copy at a
    message's head end stands at the card's edge, under Close, and copies the message's
    Markdown source; with nothing selected, the copy key in the thread presses the Copy
    of the message whose words the user clicked."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Can it **wait**?", {"section": "lede"})
    source = "Not safely:\n\n- setup runs **untrusted** code\n- `v2` is weeks away"
    append_agent_reply(serve.page_dir, root, source)
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, url, context=context)
    page.locator(".lf-margin-marker").first.click()
    card = page.locator(".lf-margin-preview .lf-page-thread")
    reply = card.locator(".lf-msg[data-lf-author=agent]")
    # A press leaves focus on the first message's Copy, and its controls still leave
    # with the pointer.
    first = card.locator(".lf-msg[data-lf-author=user]")
    first.hover()
    first.locator(".lf-msg-copy").click()
    shown = """message => [...message.querySelector('.lf-msg-controls').children]
      .map((c) => getComputedStyle(c).opacity)"""
    assert set(first.evaluate(shown)) == {"1"}
    reply.locator(".lf-msg-text p").first.hover()
    rendered(page)
    assert first.evaluate("m => m.contains(document.activeElement)")
    assert set(first.evaluate(shown)) == {"0"}
    # The hovered reply's Copy shows at its head's end.
    assert reply.locator(".lf-msg-copy").evaluate(
        """copy => { const box = copy.getBoundingClientRect();
          return getComputedStyle(copy).opacity === '1' && copy.contains(
            document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2)); }"""
    )
    reply.locator(".lf-msg-text p").first.click()
    rendered(page)
    edges = card.evaluate(
        """card => ({
          copy: card.querySelector('.lf-msg[data-lf-author=agent] .lf-msg-copy').getBoundingClientRect().right,
          close: card.closest('.lf-margin-preview').querySelector('.lf-margin-preview-close')
            .getBoundingClientRect().right,
        })"""
    )
    assert edges["copy"] == pytest.approx(edges["close"], abs=1), edges
    page.keyboard.press("ControlOrMeta+c")
    expect(reply.locator(".lf-msg-copy")).to_have_js_property("status", "success")
    assert page.evaluate("navigator.clipboard.readText()") == source


# A head's delivery receipt beside its message's controls: whether it shows whole, its
# box, the first showing control's start, and whether the receipt is what the user
# sees just before that start.
RECEIPT_BESIDE_CONTROLS = """message => {
  const receipt = message.querySelector(':scope > .lf-msg-head .lf-msg-sending');
  const box = receipt.getBoundingClientRect();
  const shown = [...message.querySelectorAll(':scope > .lf-msg-head .lf-msg-controls > *')]
    .filter((control) => getComputedStyle(control).opacity === '1')
    .map((control) => control.getBoundingClientRect().left);
  const controls = shown.length ? Math.min(...shown) : null;
  const seen = controls === null ? null : document.elementFromPoint(
    controls + 2, box.top + box.height / 2);
  return {
    whole: receipt.scrollWidth <= receipt.clientWidth,
    left: box.left,
    end: box.right,
    controls,
    receiptSeen: seen === null ? null : receipt.contains(seen),
  };
}"""


# A head's parts, in the order their shrink weights give, each one's least width (its
# minimum, or its padding and border where it sizes its border box), and each one's
# width as the head narrows from far wider than its words to nothing.
SQUEEZED_HEAD = """head => {
  const meta = head.querySelector(':scope > .lf-msg-meta');
  const parts = [];
  for (const node of [...head.children, ...meta.children])
    if (node !== meta && getComputedStyle(node).position !== 'absolute')
      parts.push({ name: node.classList[0] ?? node.localName, node });
  const style = (part) => getComputedStyle(part.node);
  parts.sort((a, b) => style(b).flexShrink - style(a).flexShrink);
  const least = parts.map((part) => {
    const box = style(part);
    const edges = ['paddingLeft', 'paddingRight', 'borderLeftWidth', 'borderRightWidth']
      .reduce((sum, side) => sum + parseFloat(box[side]), 0);
    return Math.max(parseFloat(box.minWidth) || 0, box.boxSizing === 'border-box' ? edges : 0);
  });
  const time = head.querySelector('time');
  const day = time.querySelector(':scope > span');
  const steps = [];
  const days = [];
  for (let width = 2000; width >= 0; width -= width > 400 ? 1600 : 1) {
    head.style.inlineSize = `${width}px`;
    steps.push(parts.map((part) => parseFloat(style(part).width)));
    days.push({
      time: time.getBoundingClientRect().width,
      day: day.getBoundingClientRect().width,
      whole: day.scrollWidth <= day.clientWidth &&
        day.getBoundingClientRect().right <= time.getBoundingClientRect().right + 0.5,
    });
  }
  return { parts: parts.map((part) => part.name), least, steps, days };
}"""


def test_a_head_s_words_take_its_controls_room_while_they_hide(
    browser, serve, subtests
):
    """A message's Edit and Copy show only under the pointer or focus, and its head
    lends their room to its words while they hide: a card's head that held it would cut
    its receipt to "Still qu…" beside room for controls nobody could see. At rest the
    user's queued message says its whole receipt; under the pointer the controls stand
    over the receipt's end, which neither moves nor changes its size. A head too narrow for
    its words gives up its parts one at a time, in the order the user chose
    (surfaces.css): its controls' room, its receipt, its time and its name. No part is
    cut while one before it still has room to give, so a squeezed head never reads
    "Me ju… · Que…", and each gives all it can before the head reaches nothing. The
    user's queued message holds each part."""
    url = serve(PANEL_PAGE)
    # A comment that stands taller than it is wide widens the card from its least
    # width, and the margin at this width caps it short of the head's words and
    # controls: written days ago, its head names its day and time.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can it wait until the ceiling is settled? " * 16,
            "anchor": {"section": "lede"},
            "ts": (datetime.now().astimezone() - timedelta(days=3)).isoformat(),
        },
    )
    context = browser.new_context(viewport={"width": 1456, "height": 900})
    page = open_page(browser, url, context=context)
    page.locator(".lf-margin-marker").first.click()
    message = page.locator(".lf-margin-preview .lf-msg[data-lf-author=user]").first
    expect(message.locator(".lf-msg-sending")).to_contain_text("Still queued")
    with subtests.test("the controls hide"):
        page.mouse.move(0, 0)
        rendered(page)
        rest = message.evaluate(RECEIPT_BESIDE_CONTROLS)
        assert rest["whole"] and rest["controls"] is None, rest
        message.locator(".lf-msg-text").hover()
        rendered(page)
        offered = message.evaluate(RECEIPT_BESIDE_CONTROLS)
        assert offered["whole"], offered
        assert (offered["left"], offered["end"]) == (rest["left"], rest["end"]), (
            rest,
            offered,
        )
        assert offered["controls"] < offered["end"], offered
        assert offered["receiptSeen"] is False, offered
    # The squeeze narrows the head for good, so it reads last, with the pointer away.
    with subtests.test("the head squeezed"):
        page.mouse.move(0, 0)
        rendered(page)
        squeeze = message.locator(":scope > .lf-msg-head").evaluate(SQUEEZED_HEAD)
        parts, least, steps = squeeze["parts"], squeeze["least"], squeeze["steps"]
        assert parts == ["lf-msg-control-room", "lf-msg-sending", "time", "b"], parts
        whole = steps[0]
        assert steps[-1] == pytest.approx(least, abs=0.05), (parts, least, steps[-1])
        for widths in steps:
            for at in range(len(parts)):
                if widths[at] < whole[at] - 0.05:
                    given = [widths[part] <= least[part] + 0.05 for part in range(at)]
                    assert all(given), (parts, widths)
        # A time too narrow for its day and clock gives up its clock whole, which wraps
        # out of its one line, and keeps its day whole while it has the day's room.
        days = squeeze["days"]
        day = days[0]["day"]
        assert any(day - 0.05 <= step["time"] < days[0]["time"] - 1 for step in days)
        for step in days:
            if step["time"] >= day - 0.05:
                assert step["whole"], (day, step)


def test_a_margin_message_copy_keeps_its_edge_when_send_motion_ends(browser, serve):
    """The last translated frame and rest keep Copy on the message's head line, ending
    where the card's own controls end (annotation-chrome.css, `--lf-margin-symbol-end`),
    less the transcript's scrollbar: where scrollbars take room, the reply makes the
    transcript scroll and its bar stands between the message and the card's edge."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Opening turn.", {"section": "how-store"})
    append_agent_reply(serve.page_dir, root, "A reply with words to copy. " * 8)
    page = open_page(browser, url)
    resized(page, 1200, 520)
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    rendered(page)
    page.keyboard.press("c")
    page.keyboard.type("One more turn.")
    rendered(page)
    page.evaluate("() => {" + HOLD_MOTION + "}")
    pending = []
    page.route("**/api/event", lambda route: pending.append(route))
    try:
        page.keyboard.press("ControlOrMeta+Enter")
        holding(page, pending, 1, "the margin reply")
        page.wait_for_function(
            """() => __lfHeld.some(a => a.playState !== 'idle' &&
              a.effect.target.matches('.lf-msg[data-lf-author=agent]') &&
              a.effect.getKeyframes().some(k => '--lf-box-carry' in k))"""
        )
        page.evaluate(
            """() => __lfHeld.filter(a => a.playState !== 'idle').forEach(a => {
              a.currentTime = a.effect.getComputedTiming().endTime - 0.01;
            })"""
        )
        message = page.locator(".lf-margin-preview .lf-msg[data-lf-author=agent]")
        edges = """m => {
          const box = m.getBoundingClientRect();
          const copy = m.querySelector('.lf-msg-copy').getBoundingClientRect();
          const transcript = m.closest('.lf-thread-transcript');
          const card = m.closest('.lf-margin-thread')
            .querySelector('.lf-margin-thread-controls > :last-child')
            .getBoundingClientRect();
          return {
            right: copy.right - box.right,
            top: copy.top - box.top,
            cardEnd: card.right - box.right
              - (transcript.offsetWidth - transcript.clientWidth),
          };
        }"""
        moving = message.evaluate(edges)
        assert moving["top"] == pytest.approx(0, abs=1), moving
        assert moving["right"] == pytest.approx(moving["cardEnd"], abs=1), moving
        page.evaluate(
            "() => __lfHeld.slice().filter(a => a.playState !== 'idle')"
            ".forEach(a => a.finish())"
        )
        rendered(page)
        assert message.evaluate(edges) == pytest.approx(moving, abs=1)
    finally:
        page.context.close()


def test_every_message_says_when_it_was_said(browser, serve):
    """Every message in a thread says when it was said (state/presence.js, `saidAt`): replies
    hours apart three days ago each read their own time of day and day, as the reader's
    locale writes them, where an age would read "3d ago" over all of them, and a reply
    written now reads "just now", where its time of day would read like any other."""
    url = serve(PANEL_PAGE)
    # Local wall times, each with its own offset, so a change of daylight saving
    # between them moves no clock reading.
    now = datetime.now()
    then = (now - timedelta(days=3)).replace(hour=15, minute=29, second=0).astimezone()
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Is the retry bounded?",
            "ts": then.isoformat(),
            "anchor": {"section": "lede"},
        },
    )["id"]
    for text, at in [
        ("Yes, three tries; I'm parking it now.", then + timedelta(minutes=6)),
        ("Parked after the third.", then + timedelta(hours=2, minutes=23)),
    ]:
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": root,
                "revision": 1,
                "text": text,
                "ts": at.isoformat(),
            },
        )
    append_agent_reply(serve.page_dir, root, "And the backoff doubles.")
    context = browser.new_context(locale="en-US")
    page = open_page(browser, url, context=context)
    page.locator(".lf-margin-marker").first.click()
    card = page.locator(".lf-margin-preview .lf-page-thread")
    expect(card).to_be_visible()
    times = card.locator(".lf-msg-head > .lf-msg-meta > time")
    expect(times).to_have_count(4)
    day = f"{then:%b} {then.day}" + ("" if then.year == now.year else f", {then.year}")
    assert [" ".join(time.split()) for time in times.all_text_contents()] == [
        f"{day} 3:29 PM",
        f"{day} 3:35 PM",
        f"{day} 5:52 PM",
        "just now",
    ]


# Where a message's words may run to.
WORDS_END = """message => {
  const words = message.querySelector('.lf-msg-text');
  return words.getBoundingClientRect().right
    - parseFloat(getComputedStyle(words).paddingInlineEnd);
}"""


@pytest.mark.parametrize("surface", ["panel", "seat"])
def test_the_user_s_words_end_where_the_agent_s_do(browser, serve, surface):
    """The user's own message runs to the thread's column, as the agent's under it
    does, keeping at its end only the inset its words start with, where its rewrite's
    frame stands. Keeping the room Send takes in the field they were typed in, the
    user's lines would stop short of the agent's, so every message the user sent would
    wrap narrower than the reply under it. The panel and a seated card end every
    message's words that inset in, as the margin card does (`--lf-msg-text-end`), so
    the two end together."""
    words = (
        "Check that these balance robust interfaces with code simplicity, deferring "
        "to standards and the browser wherever they can, and keeping the code simple."
    )
    url = serve(PANEL_PAGE if surface == "panel" else THREAD_DIFF_PAGE)
    root = panel_comment(
        serve.page_dir, words, None if surface == "panel" else {"section": "cd-q"}
    )
    append_agent_reply(serve.page_dir, root, words)
    page = open_page(browser, url)
    resized(page, 1280, 900)
    if surface == "panel":
        thread = open_panel_thread(page, root)
    else:
        thread = page.locator("#cd-q .lf-page-thread").first
    user, agent = (
        thread.locator(".lf-msg[data-lf-author=user]"),
        thread.locator(".lf-msg[data-lf-author=agent]"),
    )
    expect(agent).to_contain_text("Check that these")
    rendered(page)
    mine, theirs = user.evaluate(WORDS_END), agent.evaluate(WORDS_END)
    assert theirs == pytest.approx(mine, abs=0.5), (mine, theirs)


# The words of each line a node shows, from its text's own boxes, and where its words
# may run to: a message's, or a field's in its closed root.
WORDS_AS_DRAWN = """node => {
  const words = window.marginEditorRoots.get(node)?.querySelector('.cm-content') ?? node;
  const lines = new Map();
  const walk = document.createTreeWalker(words, NodeFilter.SHOW_TEXT);
  for (let text = walk.nextNode(); text; text = walk.nextNode())
    for (let at = 0; at < text.data.length; at++) {
      const range = document.createRange();
      range.setStart(text, at);
      range.setEnd(text, at + 1);
      const box = range.getClientRects()[0];
      if (!box?.width) continue;
      const top = Math.round(box.top);
      lines.set(top, (lines.get(top) ?? '') + text.data[at]);
    }
  return {
    lines: [...lines].sort(([a], [b]) => a - b).map(([, line]) => line.trim()),
    end: words.getBoundingClientRect().right
      - parseFloat(getComputedStyle(words).paddingInlineEnd),
  };
}"""


@pytest.mark.parametrize("finger", [False, True], ids=["mouse", "finger"])
@pytest.mark.parametrize("box", ["comment", "reply"])
def test_a_seat_s_boxes_break_their_lines_where_their_messages_will(
    browser, serve, box, finger
):
    """A seat's comment box and its card's reply box each run the row's width, and
    their words end where the message they become will, so Send moves no word. Wrapping
    at the row's width, a comment under a diff line broke its lines at the row's end
    and rewrapped at the seat's column once sent. Under a finger, where Send keeps its
    room at the end of every line, a reply's words ran a pixel past the message's, where
    Send's room was reckoned from Send rather than from the room a message keeps."""
    url, root = long_diff_thread(serve)
    context = browser.new_context(has_touch=finger, is_mobile=finger)
    page = open_page(browser, url, init_script=MARGIN_EDITOR_ROOTS, context=context)
    resized(page, 1280, 900)
    if box == "comment":
        page.locator("#patch").get_by_role(
            "button", name="Comment on app.py · new line 1", exact=True
        ).click()
        field = page.locator("#patch .lf-fab-bar leaf-text")
    else:
        field = page.locator(
            f'#patch .lf-page-thread[data-lf-thread="{root}"]'
        ).locator(".lf-thread-reply leaf-text")
        field.click()
    expect(field).to_be_focused()
    words = LANDING_WORDS.strip()
    page.keyboard.insert_text(words)
    rendered(page)
    typed = field.evaluate(WORDS_AS_DRAWN)
    assert len(typed["lines"]) > 1, typed
    if finger:
        field.locator("xpath=..").locator(".lf-compose-submit").click()
    else:
        page.keyboard.press("Enter")
    sent = page.locator(
        "#patch .lf-msg[data-lf-author=user] .lf-msg-text", has_text=words[:40]
    )
    expect(sent).to_be_visible()
    rendered(page)
    drawn = sent.evaluate(WORDS_AS_DRAWN)
    assert drawn["lines"] == typed["lines"]
    assert drawn["end"] == pytest.approx(typed["end"], abs=0.5), (drawn, typed)


def test_opening_message_reactions_does_not_reflow_the_thread(browser, serve):
    """The picker floats from its message corner without moving the thread.

    A reaction list that added room to its thread only while open would move every
    later message under the pointer and make choosing a reaction change the layout
    being acted on. The next message is the single-factor neighbor: opening the
    picker is the only change between these two frames."""
    url = serve(PANEL_PAGE)
    first = panel_comment(serve.page_dir, "Keep the route visible.")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": first,
            "revision": 1,
            "text": "The route stays beside the choice.",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": first,
            "revision": 1,
            "text": "Keep the cap visible too.",
        },
    )
    page = open_page(browser, url)
    view = open_panel_thread(page, first)
    card = view.locator(".lf-msg[data-lf-author=agent]")
    neighbor = view.locator(".lf-msg").last
    trigger = card.locator(".lf-react-trigger")
    assert trigger.evaluate("b => getComputedStyle(b).backgroundColor") == (
        "rgba(0, 0, 0, 0)"
    )
    trigger.hover()
    # The panel dresses its own presses; under the pointer the trigger takes a face.
    expect(trigger).not_to_have_css("background-color", "rgba(0, 0, 0, 0)")
    before = {
        "card": card.bounding_box(),
        "neighbor": neighbor.bounding_box(),
    }

    trigger.click()
    expect(trigger).to_have_attribute("aria-expanded", "true")
    palette = view.locator(".lf-react-palette")
    expect(palette).to_be_visible()
    after = {
        "card": card.bounding_box(),
        "neighbor": neighbor.bounding_box(),
    }
    assert after == before
    assert palette.bounding_box()["y"] >= (
        trigger.bounding_box()["y"] + trigger.bounding_box()["height"]
    )


@pytest.mark.parametrize("engine", ["browser", "firefox_browser", "webkit_browser"])
def test_a_pages_light_rules_stop_at_the_chrome(request, serve, engine):
    """A page's CSS is ordinary CSS over its document: its `button` and `a` rules dress
    the controls a widget builds as they dress its prose. They stop at the chrome, which
    rolls a page rule as light as one class back to Leaf's own faces
    (styles/chrome-guard.css): without that, a page's `button` rule turned all of the
    panel's buttons cursive and red. A face set on body reaches prose by inheritance and
    stops at controls and chrome, which state their own. A token set on :root, a
    condition on an ancestor and a pseudo-element keep working as page CSS does."""
    board = (
        '<h1>t</h1><lf-board id="b"><lf-column id="c1" label="To do">'
        '<lf-card id="k1">One</lf-card><lf-card id="k2">Two</lf-card></lf-column>'
        '<lf-column id="c2" label="Done"></lf-column></lf-board>'
        '<p>See <a href="#b">the board</a>.</p>'
    )
    page = open_page(
        request.getfixturevalue(engine),
        live_url(
            serve(
                leaf_page(
                    "t",
                    board,
                    head="<style>button, a, .lf-ui { font-family: cursive;"
                    " color: rgb(255, 0, 0); }"
                    "body { font-style: italic; letter-spacing: 3px; }"
                    ":root { --page-token: teal; }"
                    "html[data-lf-interactive] p > a { background-color: rgb(1, 2, 3); }"
                    "p > a::before { content: 'Kept'; }"
                    "p { border-top: 7px solid red; }</style>",
                )
            )
        ),
    )
    faces = page.evaluate("""() => {
        const adopted = new CSSStyleSheet();
        adopted.replaceSync('p { border-top-color: rgb(0, 0, 255); }');
        document.adoptedStyleSheets = [...document.adoptedStyleSheets, adopted];
        const face = el => { const cs = getComputedStyle(el);
            return [el.className, cs.fontFamily, cs.color, cs.fontStyle, cs.letterSpacing]; };
        return {
            controls: [...document.querySelectorAll('main button.lf-ui')].map(face),
            chrome: [...document.querySelectorAll('.lf-chrome button')].map(face),
            prose: face(document.querySelector('main p > a')),
            chromeToken: getComputedStyle(document.querySelector('.lf-chrome'))
                .getPropertyValue('--page-token').trim(),
            ancestor: getComputedStyle(document.querySelector('main p > a')).backgroundColor,
            pseudo: getComputedStyle(document.querySelector('main p > a'), '::before').content,
            adopted: getComputedStyle(document.querySelector('main p')).borderTopColor,
        };
    }""")
    assert faces["chromeToken"] == "teal", faces
    assert faces["ancestor"] == "rgb(1, 2, 3)", faces
    assert faces["pseudo"] == '"Kept"', faces
    assert faces["adopted"] == "rgb(0, 0, 255)", faces
    assert faces["prose"][1:5] == ["cursive", "rgb(255, 0, 0)", "italic", "3px"], faces[
        "prose"
    ]
    assert faces["controls"], "the board built no control to read"
    assert faces["chrome"], "the chrome built no button to read"
    assert {tuple(face[1:3]) for face in faces["controls"]} == {
        ("cursive", "rgb(255, 0, 0)")
    }, faces["controls"]
    inherited = [
        face for face in faces["controls"] if face[3] == "italic" or face[4] == "3px"
    ]
    assert not inherited, inherited
    reached = [
        face
        for face in faces["chrome"]
        if "cursive" in face[1]
        or face[2] == "rgb(255, 0, 0)"
        or face[3] == "italic"
        or face[4] == "3px"
    ]
    assert not reached, reached


def test_a_sheet_a_page_script_writes_later_stops_at_the_chrome(browser, serve):
    """A CSS framework such as Tailwind builds its sheet in the head after the page
    loads and rewrites it as classes change, and each rewrite is a new sheet. Its
    element rules reach the page's prose and stop at the chrome, as the page's own
    stylesheet's and its imports' do: Tailwind's reset would otherwise take the family
    of every chrome button."""
    url = serve(
        leaf_page(
            "t",
            '<h1>t</h1><p>See <a id="prose" href="#t">the link</a>.</p>',
            head="""<style>@import url("page/author.css");</style>
<script type="module">
const sheet = document.createElement("style");
document.head.append(sheet);
sheet.textContent = "button, a { font-family: fantasy; }";
setTimeout(() => {
  sheet.textContent = "button, a { font-family: cursive; }";
  window.rewritten = true;
}, 50);
</script>""",
        ),
        page_files={
            "author.css": "a { border-top: 7px solid red; } button { border-top: 77px solid red; }",
        },
    )
    page = open_page(browser, url)
    page.wait_for_function("() => window.rewritten")
    faces = page.evaluate("""() => {
        const family = el => getComputedStyle(el).fontFamily;
        return {
            chrome: [...document.querySelectorAll('.lf-chrome button')].map(family),
            prose: family(document.getElementById('prose')),
            imported: getComputedStyle(document.getElementById('prose')).borderTopWidth,
            chromeBorders: [...document.querySelectorAll('.lf-chrome button')].map(
                el => getComputedStyle(el).borderTopWidth),
        };
    }""")
    assert faces["prose"] == "cursive", faces
    assert faces["imported"] == "7px", faces
    assert "77px" not in faces["chromeBorders"], faces
    assert faces["chrome"], "the chrome built no button to read"
    assert not [f for f in faces["chrome"] if f in {"cursive", "fantasy"}], faces


def test_a_theme_package_styles_every_page_as_the_pages_own_sheet_does_one(
    browser, serve, tmp_path
):
    """A package's overrides, even beside a widget, outrank the Layouts and
    every widget package's defaults (layer.py, `lf-overrides`), so its `main` padding beats
    the column Layout's and its plain `lf-card` rule beats the board's own `lf-card`
    rule. Like the page's own rules, its `button` rule dresses the page's buttons and the
    controls the board builds."""
    theme = tmp_path / "theme"
    theme.mkdir()
    (theme / "registry.json").write_text(
        json.dumps(
            {
                "lf-theme-box": {
                    "description": "A widget beside a page-wide theme.",
                    "attributes": {
                        "properties": {},
                        "required": ["id"],
                    },
                    "content": "markup",
                }
            }
        )
    )
    (theme / "overrides.css").write_text(
        "main { padding-top: 11px; }\n"
        "lf-card { padding-left: 13px; }\n"
        "main button { font-family: cursive; }\n"
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "t",
                '<h1>t</h1><p><button id="own" type="button">Own</button></p>'
                '<lf-board id="b"><lf-column id="c1" label="To do">'
                '<lf-card id="k1">One</lf-card></lf-column></lf-board>',
            ),
            packages=("./theme",),
        ),
    )
    faces = page.evaluate("""() => {
        const cs = el => getComputedStyle(el);
        return {
            main: cs(document.querySelector('main')).paddingTop,
            card: cs(document.getElementById('k1')).paddingLeft,
            own: cs(document.getElementById('own')).fontFamily,
            controls: [...document.querySelectorAll('lf-board button.lf-ui')].map(
                el => cs(el).fontFamily),
        };
    }""")
    assert faces["main"] == "11px", faces
    assert faces["card"] == "13px", faces
    assert faces["own"] == "cursive", faces
    assert faces["controls"], "the board built no control to read"
    assert set(faces["controls"]) == {"cursive"}, faces


@pytest.mark.parametrize("engine", ["browser", "firefox_browser", "webkit_browser"])
def test_a_packages_shadow_rules_reach_only_trees_its_widgets_host(
    request, serve, tmp_path, engine
):
    """Every declared shadow tree receives the layer's composed shadow sheet in every
    engine, so a package's `widget-shadow.css` rule naming its host, `:host(lf-own-tree)
    span`, dresses that widget's tree and not another package's. Each engine reads the
    composed sheet itself: Firefox can apply none of a generated `:host` scope, which
    Leaf doesn't write."""
    own, own_module = _shadow_tree_widget("lf-own-tree")
    other, other_module = _shadow_tree_widget("lf-other-tree")
    project = tmp_path / ".leaf"
    project.mkdir()
    (project / "widget-shadow.css").write_text(
        ":host(lf-own-tree) span { color: rgb(0, 128, 0); }\n"
    )
    neighbour = tmp_path / "other"
    (neighbour / "widgets").mkdir(parents=True)
    (neighbour / "registry.json").write_text(json.dumps({"lf-other-tree": other}))
    (neighbour / "widgets" / "lf-other-tree.js").write_text(other_module)
    url = serve(
        leaf_page(
            "t",
            '<h1>t</h1><lf-own-tree id="own"></lf-own-tree>'
            '<lf-other-tree id="other"></lf-other-tree>',
        ),
        packages=("./other",),
        layer_registry={"lf-own-tree": own},
        layer_widgets={"lf-own-tree.js": own_module},
    )
    page = open_page(request.getfixturevalue(engine), url)
    colors = page.evaluate("""() => Object.fromEntries(['own', 'other'].map(id => [id,
        getComputedStyle(document.getElementById(id).shadowRoot.querySelector('span'))
            .color]))""")
    assert colors["own"] == "rgb(0, 128, 0)", colors
    assert colors["other"] != "rgb(0, 128, 0)", colors


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_package_restyles_an_idiom_whatever_its_rule_weighs(
    request, serve, tmp_path, engine
):
    """Leaf's idioms are defaults (idioms.css), so a package's rule for an idiom's
    element outranks Leaf's however little it weighs. In the document, a theme's
    `.lf-tag` beats the tone of Leaf's `.lf-tag.warn` and its bare `dt` beats
    `dl.lf-facts dt`; in a declared shadow tree, the package's
    `:host(lf-idiom-tree) :where(dt)` beats `dl.lf-facts dt` too. The idioms still
    outrank markup's reading face, so a fact's label stays regular where the face sets
    a `dt` bold, and a numeric cell stands right where the face sets a cell at its
    start."""
    declaration, _module = _shadow_tree_widget("lf-idiom-tree")
    look = tmp_path / "look"
    (look / "widgets").mkdir(parents=True)
    (look / "registry.json").write_text(json.dumps({"lf-idiom-tree": declaration}))
    (look / "widgets" / "lf-idiom-tree.js").write_text("""
import {shadowStage} from '/runtime/widget-api.js';
customElements.define('lf-idiom-tree', class extends HTMLElement {
  connectedCallback() {
    if (this.shadowRoot) return;
    const facts = document.createElement('dl');
    facts.className = 'lf-facts';
    facts.append(document.createElement('dt'), document.createElement('dd'));
    facts.firstChild.textContent = 'Owner';
    facts.lastChild.textContent = 'Imani';
    shadowStage(this, [facts]);
  }
});
""")
    (look / "defaults.css").write_text(
        ".lf-tag { background-color: rgb(0, 128, 0); }\ndt { color: rgb(0, 0, 255); }\n"
    )
    (look / "widget-shadow.css").write_text(
        ":host(lf-idiom-tree) :where(dt) { color: rgb(0, 0, 255); }\n"
    )
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Idioms",
                '<h1>Idioms</h1><p><span class="lf-tag warn" id="tag">late</span></p>'
                '<dl class="lf-facts"><dt id="label">Owner</dt><dd>Imani</dd></dl>'
                "<table><tr><th>Run</th><th>Time</th></tr>"
                '<tr><td>one</td><td class="lf-numeric" id="figure">12</td></tr></table>'
                '<lf-idiom-tree id="tree"></lf-idiom-tree>',
            ),
            packages=("./look",),
        ),
    )
    drawn = page.evaluate("""() => {
      const cs = el => getComputedStyle(el);
      const tree = document.getElementById('tree').shadowRoot;
      return {
        tag: cs(document.getElementById('tag')).backgroundColor,
        label: cs(document.getElementById('label')).color,
        labelWeight: cs(document.getElementById('label')).fontWeight,
        figure: cs(document.getElementById('figure')).textAlign,
        treeLabel: cs(tree.querySelector('dt')).color,
        treeFacts: cs(tree.querySelector('dl')).display,
      };
    }""")
    assert drawn == {
        "tag": "rgb(0, 128, 0)",
        "label": "rgb(0, 0, 255)",
        "labelWeight": "400",
        "figure": "right",
        "treeLabel": "rgb(0, 0, 255)",
        "treeFacts": "grid",
    }, drawn


@pytest.mark.parametrize("engine", ["browser", "firefox_browser", "webkit_browser"])
def test_a_package_restyles_the_chrome_by_its_parts(tmp_path, request, serve, engine):
    """A theme restyles Leaf's chrome on purpose from its chrome.css, naming surfaces
    by part (`layer.chrome_restyle`). Its rules beat the chrome's own whatever either's
    selector, inside a condition too, and reach nothing outside the chrome, even by a
    selector naming the page around it. A page's
    own rule naming a part sets the tokens there and nothing else, which the guard
    rolls back as it does any light page rule (styles/chrome-guard.css). A face set on a
    part reaches the words there, since each part resolves the fonts again (base.css).
    A rule keyed on the page around the chrome reaches a part through `&`, and the
    parts the chrome carries are the ones package-themes.md documents."""
    package = tmp_path / "chrome-look"
    package.mkdir()
    (package / "chrome.css").write_text(
        '[part~="panel"] { font-family: cursive; --lf-r-l: 0px; }'
        'html & [part~="card"] { --lf-r-l: 5px; }'
        '@media screen { [part~="composer"] { letter-spacing: 3px; } }'
        "p { color: rgb(255, 0, 0); }"
        "body:has(&) { border-top: 9px solid rgb(255, 0, 0); }"
    )
    page = open_page(
        request.getfixturevalue(engine),
        live_url(
            serve(
                leaf_page(
                    "t",
                    "<h1>t</h1><p>Words.</p>",
                    head='<style>[part~="panel"] { font-family: fantasy;'
                    " color: rgb(0, 128, 0); --lf-ink: rgb(1, 2, 3); }"
                    '[part~="composer"] { --lf-sans: monospace; }</style>',
                ),
                packages=(package,),
            )
        ),
    )
    faces = page.evaluate("""() => {
        const panel = document.querySelector('[part~="panel"].lf-floating-panel');
        const cs = el => getComputedStyle(el);
        return {
            family: cs(panel).fontFamily,
            color: cs(panel).color,
            corner: cs(panel.querySelector('.lf-fp-card')).borderTopLeftRadius,
            composer: cs(document.querySelector('[part~="composer"]')).letterSpacing,
            font: cs(document.querySelector('[part~="composer"]'))
                .getPropertyValue('--lf-font-message').trim().split(' ').at(-1),
            card: cs(document.querySelector('.lf-chrome [part~="card"]'))
                .getPropertyValue('--lf-r-l').trim(),
            parts: [...new Set([...document.querySelectorAll('.lf-chrome [part]')]
                .flatMap(e => e.getAttribute('part').split(' ')))].sort(),
            prose: cs(document.querySelector('main p')).color,
            body: cs(document.body).borderTopWidth,
        };
    }""")
    section = (PLUGIN_ROOT / "skills/leaf/references/package-themes.md").read_text()
    section = section.split("## Leaf's chrome", 1)[1].split("\n## ", 1)[0]
    assert faces == {
        "family": "cursive",
        "color": "rgb(1, 2, 3)",
        "corner": "0px",
        "composer": "3px",
        "font": "monospace",
        "card": "5px",
        "parts": sorted(re.findall(r"^\| `([a-z-]+)` ", section, re.M)),
        "prose": faces["prose"],
        "body": "0px",
    }, faces
    assert faces["prose"] != "rgb(255, 0, 0)", faces


def test_a_coined_class_cannot_reach_the_chromes_rules(browser, serve):
    """The chrome's private rules live in one @scope block rooted at the runtime's
    own container, so whatever name a widget or a page coins, it matches none of
    them: lf-tabs marking itself lf-live — the chrome's name for its
    visually-hidden live region — would otherwise clip every tabbed page to a pixel. An
    element in the page wearing every private class at once must render exactly as
    its unclassed twin.

    The chrome sheet reaches the page only through the classes its owner declares
    shared (`chromeSharedClasses`, runtime/base/stylesheets.js): a rule written outside the
    block that names any other class is a private rule leaking out, not a widening. The
    guard against page rules (styles/chrome-guard.css) stands outside the block and names
    only `lf-chrome`, the chrome's own root, which no authored element may wear since
    the `lf-` namespace is Leaf's; it reaches nothing in the page. Those classes, and the faces the authored theme states for a private name at
    document level, stay off the probe, since the movement their rules cause is the
    reach they were given on purpose."""
    page = open_page(
        browser,
        serve(leaf_page("t", "<h1>t</h1><section id=s><p>words</p></section>")),
    )
    surface = page.evaluate("""async () => {
        const {chromeSheet: sheet, chromeSharedClasses: declared} =
            await window.__lfCheckApi();
        const classes = sel => [...(sel || "").matchAll(/\\.([A-Za-z0-9_-]+)/g)].map(m => m[1]);
        const scoped = new Set(), unscoped = new Set(), themed = new Set();
        const collect = (rules, into, privateRules = null) => { for (const r of rules) {
            if (r instanceof CSSScopeRule) {
                if (privateRules) collect(r.cssRules, privateRules, privateRules);
            }
            else if (r.selectorText) classes(r.selectorText).forEach(c => into.add(c));
            else if (r.cssRules) collect(r.cssRules, into, privateRules); } };
        collect(sheet.cssRules, unscoped, scoped);
        unscoped.delete("lf-chrome");
        for (const other of [...document.styleSheets, ...document.adoptedStyleSheets]
                 .filter(s => s !== sheet))
            collect(other.cssRules, themed);
        const probe = document.createElement("div"), plain = document.createElement("div");
        const worn = [...scoped].filter(c => !declared.includes(c) && !themed.has(c));
        probe.className = worn.join(" ");
        probe.textContent = plain.textContent = "probe";
        // A block after both, so neither twin stands at the section's edge, where the
        // theme trims a margin whichever classes it wears.
        const after = document.createElement("p");
        after.textContent = "after";
        document.getElementById("s").append(plain, probe, after);
        const cs = el => { const c = getComputedStyle(el), out = {};
                           for (const p of c) out[p] = c.getPropertyValue(p); return out; };
        const a = cs(probe), b = cs(plain);
        const body = document.createElement("div");
        body.className = "lf-msg-body";
        body.textContent = "Authored thread words";
        document.getElementById("s").append(body);
        return { worn, unscoped: [...unscoped], declared: [...declared],
                 moved: Object.keys(a).filter(p => a[p] !== b[p]),
                 bodySelection: getComputedStyle(body).userSelect,
                 plainSelection: getComputedStyle(plain).userSelect };
    }""")
    unscoped, declared = set(surface["unscoped"]), set(surface["declared"])
    assert not unscoped - declared, (
        "chrome rules outside its @scope block name classes the sheet does not declare "
        f"shared, so a page element wearing one meets them: {sorted(unscoped - declared)}"
        " — move the rule into the block, or add the class to chromeSharedClasses"
    )
    assert not declared - unscoped, (
        "chromeSharedClasses declares classes no rule outside the @scope block names: "
        f"{sorted(declared - unscoped)}"
    )
    assert surface["worn"], (
        "the probe wears no private class — the @scope block is missing or empty, so "
        "this compares two unclassed twins"
    )
    assert surface["moved"] == [], (
        f"scoped chrome rules reached an element in the page: {surface['moved']}"
    )
    # The shared message body gets selectable-island rules only inside chrome.
    # Its authored copy keeps the document's selection behavior.
    assert surface["bodySelection"] == surface["plainSelection"]


# Whether the card's transcript fades its words at its top, which it does while they
# run on past it (annotation-chrome.css), and where its head line stands.
CARD_EDGES = """transcript => {
  const mask = getComputedStyle(transcript).maskImage;
  const line = transcript.parentElement
    .querySelector(':scope > .lf-margin-thread-controls').getBoundingClientRect();
  return {topFade: mask.includes('linear-gradient(rgba(0, 0, 0, 0), rgb(0, 0, 0) 12px'),
          mask,
          lineBottom: line.bottom, top: transcript.getBoundingClientRect().top,
          scrolled: transcript.scrollTop > 0};
}"""


def test_a_thread_card_opens_on_its_latest_message_and_fades_where_words_run_on(
    browser, serve
):
    """A card opened on a long thread shows its latest message, as a walk to it in the
    Threads list does, under the card's head line, which stays put while the messages
    scroll beneath it, each with its own name. The words fade where they run on past
    the transcript's top, and not while its first message stands there. A jump stands
    over the turns toward each edge they run on past, and a press on one glides them
    to that edge."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Opening turn. " + LANDING_WORDS, {"section": "how-store"}
    )
    for turn in range(1, 12):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent" if turn % 2 else "user",
                "parent": root,
                "text": f"Turn {turn}. " + LANDING_WORDS,
            },
        )
    page = open_page(browser, url)
    resized(page, 1200, 880)
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    selector = (
        f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
        " > .lf-thread-transcript"
    )
    transcript = page.locator(selector)
    expect(transcript).to_be_visible()
    rendered(page)
    scroll_settled(page, selector)
    assert transcript.evaluate("box => box.scrollHeight > box.clientHeight")
    latest = transcript.locator(".lf-msg").last.bounding_box()
    shown = transcript.bounding_box()
    assert latest["y"] + latest["height"] <= shown["y"] + shown["height"] + 1
    assert not transcript.evaluate("box => box.hasAttribute('data-lf-more-below')")
    edges = transcript.evaluate(CARD_EDGES)
    assert edges["scrolled"] and edges["topFade"], edges
    assert edges["lineBottom"] <= edges["top"] + 0.5, edges

    def jump(to):
        return page.locator(
            f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
            f' > .lf-thread-jump[data-lf-jump="{to}"]'
        )

    def jumps(above, below):
        """Whether the jump to the turns' start and the jump to their end stand."""
        for to, stands in (("start", above), ("end", below)):
            if stands:
                expect(jump(to)).to_be_visible()
            else:
                expect(jump(to)).to_be_hidden()

    jumps(above=True, below=False)
    jump("start").click()
    jumps(above=False, below=True)
    assert transcript.evaluate("box => box.scrollTop") == 0
    edges = transcript.evaluate(CARD_EDGES)
    assert not edges["topFade"], edges
    jump("end").click()
    jumps(above=True, below=False)
    assert transcript.evaluate(
        "box => box.scrollHeight - box.clientHeight - box.scrollTop <= 2"
    )
    assert transcript.evaluate(CARD_EDGES)["topFade"]


@pytest.mark.parametrize("scaled", [False, True])
def test_a_short_window_keeps_media_choices_and_send_around_the_scrolling_draft(
    browser, serve, scaled
):
    """A whole-frame cap reserves the choices and Send before text scrolls; the attached
    image hangs outside the frame (annotation-chrome.css).

    Scaled, the bar's containing block is a transformed box the window's size, which
    the chrome's root is made into here, since its own box is empty (base.css)."""
    source = LONG_PAGE
    if scaled:
        source = source.replace(
            "</head>",
            """<style>
              div.lf-chrome { position:fixed; inset:0; width:auto; height:auto;
                pointer-events:none; transform:scale(1.2); transform-origin:0 0; }
              .lf-fab-bar, .lf-margin-preview { zoom:1.2; }
            </style></head>""",
        )
    page = open_page(browser, serve(source))
    width, height = (315, 450) if scaled else (390, 300)
    resized(page, width, height)
    page.locator("#p1").click(click_count=3)
    bar = page.locator(".lf-fab-bar")
    field = bar.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    paste_image(field, pixels)
    expect(bar.locator(".lf-composer-media img")).to_be_visible()
    content = "\n".join(
        f"Line {n}: the draft shares room with its picture and response choices."
        for n in range(80)
    )
    write(field, content)
    field.press("Tab")
    expect(bar.locator(".lf-react:visible")).to_have_count(6)
    rendered(page)
    expect(field).to_have_js_property("value", content)
    assert field.evaluate("el => el.scrollHeight > el.clientHeight")
    bounds = bar.evaluate("el => el.getBoundingClientRect().toJSON()")
    assert bounds["top"] >= 6
    assert bounds["bottom"] <= height - 8
    parts = bar.locator(
        ".lf-compose-field, .lf-fab-input, .lf-compose-submit, "
        ".lf-response-options, .lf-response-action:visible"
    ).evaluate_all("nodes => nodes.map(node => node.getBoundingClientRect().toJSON())")
    for part in parts:
        assert bounds["left"] <= part["left"] < part["right"] <= bounds["right"], (
            bounds,
            parts,
        )
        assert bounds["top"] <= part["top"] < part["bottom"] <= bounds["bottom"], (
            bounds,
            parts,
        )
    resized(page, width, 120)
    expect(bar).to_be_hidden()
    resized(page, width, height)
    expect(field).to_be_visible()
    expect(field).to_have_js_property("value", content)
    expect(bar.locator(".lf-composer-media img")).to_be_visible()
    expect(bar.locator(".lf-react:visible")).to_have_count(6)


def test_a_zoomed_window_places_floating_surfaces_by_their_held_edges(browser, serve):
    """Held insets use the surface's units in both window and element blocks."""
    page = open_page(browser, serve(leaf_page("Placement", "<p>Reference</p>")))
    resized(page, 605, 898)
    readings = page.evaluate(
        """async () => {
          document.documentElement.style.zoom = '1.25';
          const {floatingPlacement, floatingUi} = await window.__lfOverlayApi();
          const {computePosition, shift} = await floatingUi();
          const readings = [];
          for (const [transform, border] of [
            ['none', 0], ['scale(1.2,0.8)', 0], ['scale(1.2,0.8)', 8],
          ]) {
            const holder = document.createElement('div');
            holder.style.cssText = 'position:fixed;left:10px;top:20px;width:500px;height:600px;'
              + `transform:${transform};transform-origin:0 0;border:${border}px solid transparent`;
            document.body.append(holder);
            for (const left of [200, 440]) {
              const reference = document.createElement('div');
              reference.style.cssText = `position:fixed;left:${left}px;top:200px;width:20px;height:20px`;
              holder.append(reference);
              for (const zoom of [1, 1.2]) {
                const floating = document.createElement('div');
                floating.style.cssText = `position:fixed;width:100px;height:50px;zoom:${zoom}`;
                holder.append(floating);
                const driver = floatingPlacement({floating, update() {}});
                const answer = await driver.position(computePosition, reference,
                  {placement:'top-end', middleware:[shift({
                    boundary:[], rootBoundary:new DOMRect(8,8,589,882), padding:0,
                  })]}, () => 'window', reference);
                driver.stand(answer);
                await new Promise(requestAnimationFrame);
                const target = reference.getBoundingClientRect();
                const actual = floating.getBoundingClientRect();
                readings.push({transform, border, left, zoom, right:actual.right, bottom:actual.bottom,
                  targetRight:Math.min(target.right,597), targetTop:target.top});
                driver.stop();
                floating.remove();
              }
              reference.remove();
            }
            holder.remove();
          }
          return readings;
        }"""
    )
    for reading in readings:
        assert reading["right"] == pytest.approx(reading["targetRight"], abs=0.5), (
            reading
        )
        assert reading["bottom"] == pytest.approx(reading["targetTop"], abs=0.5), (
            reading
        )


@pytest.mark.parametrize("surface", ["card", "composer"])
def test_a_dropped_surface_keeps_its_box_until_placement_commits(
    browser, serve, surface
):
    """Release transfers the carried box without a visit to its old placement.

    Firefox drops hover during that visit, then restarts the delayed border tint.
    Read when the carry ends, before asynchronous placement can hide a gap.
    The comment box shares the same handoff even where hover happens to survive.
    """
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "Keep this explanation.", {"section": "how-store"})
    page = open_page(browser, url)
    if surface == "card":
        page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
        holder = page.locator(".lf-margin-preview")
        expect(holder).to_have_attribute("data-lf-thread-placement", re.compile(".+"))
    else:
        select_words(page, "#how-cap")
        page.keyboard.press("c")
        holder = page.locator(".lf-fab-bar")
        expect(holder.locator(".lf-fab-input")).to_be_focused()
    grip = holder.locator(":scope > .lf-surface-grip")
    box = grip.bounding_box()
    x, y = box["x"] + 25, box["y"] + (6 if surface == "card" else 2)
    # A press without travel leaves placement alone, including its inline style.
    # The write watch catches a zero translation added and removed within the click.
    resting = holder.bounding_box()
    page.mouse.click(x, y)
    rendered(page)
    assert holder.bounding_box() == resting
    page.mouse.move(x, y)
    page.mouse.down()
    expect(holder).to_have_attribute("data-lf-carried", "")
    page.mouse.move(x - 100, y - 30, steps=6)
    one_frame(page)
    held = holder.bounding_box()
    holder.evaluate(
        """surface => {
          const observer = new MutationObserver(() => {
            if (surface.hasAttribute('data-lf-carried')) return;
            surface.lfDroppedBox = surface.getBoundingClientRect().toJSON();
            observer.disconnect();
          });
          observer.observe(surface, {attributes:true, attributeFilter:['data-lf-carried']});
        }"""
    )
    page.mouse.up()
    released = holder.evaluate("surface => surface.lfDroppedBox")
    assert released is not None, "the release never reached the grip"
    for axis in ("x", "y"):
        assert released[axis] == pytest.approx(held[axis], abs=0.5), (
            f"{surface} returned to its old {axis} at release: {held} -> {released}"
        )
    expect(holder).not_to_have_attribute("data-lf-carried", "")
    landed = holder.bounding_box()
    for axis in ("x", "y"):
        assert landed[axis] == pytest.approx(held[axis], abs=0.5), (held, landed)


@pytest.mark.parametrize("turned", ["root", "card"])
def test_a_carried_card_travels_with_the_pointer_when_turned(browser, serve, turned):
    """The carry's translate moves the card along the axes of the box it stands in, at
    the card's own zoom (dom/element-axes.js, `translateAxes`): a transform on the root
    turns those axes, and the card's own turn, which applies inside its translate,
    leaves them alone. So on a page turned half round, and as a card turned half round
    and zoomed, the card travels the way the pointer does, standing under it from the
    first frame of the move, rather than away from it."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "Keep this explanation.", {"section": "how-store"})
    page = open_page(browser, url)
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", re.compile(".+"))
    # The root turned about the card's centre leaves the card's box where it stood.
    card.evaluate(
        """(card, turned) => {
          if (turned === 'card') {
            card.style.rotate = '180deg';
            card.style.zoom = '1.5';
            return;
          }
          const box = card.getBoundingClientRect();
          const root = document.documentElement;
          root.style.transformOrigin = `${box.left + box.width / 2 + scrollX}px `
            + `${box.top + box.height / 2 + scrollY}px`;
          root.style.rotate = '180deg';
        }""",
        turned,
    )
    rendered(page)
    # The middle of the grip's band along the card's top edge, wherever the turn puts it.
    start = card.locator(":scope > .lf-surface-grip").evaluate(
        """grip => {
          const mark = document.createElement('i');
          mark.style.cssText = 'position:absolute;left:50%;top:3px';
          grip.append(mark);
          const at = mark.getBoundingClientRect();
          mark.remove();
          return {x: at.left, y: at.top};
        }"""
    )
    resting = card.bounding_box()
    page.mouse.move(start["x"], start["y"])
    page.mouse.down()
    expect(card).to_have_attribute("data-lf-carried", "")
    page.mouse.move(start["x"] - 40, start["y"] - 30)
    one_frame(page)
    held = card.bounding_box()
    page.mouse.up()
    assert (held["x"] - resting["x"], held["y"] - resting["y"]) == pytest.approx(
        (-40, -30), abs=0.5
    ), (resting, held)


def test_a_zoomed_floating_draft_and_sent_comment_fit_a_narrow_window(browser, serve):
    """Under root zoom, the draft and the thread Send opens in the panel keep to a
    narrow window, and the card the thread moves to in a wide one shows its words."""
    width = 605
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, width, 898)
    page.evaluate("document.documentElement.style.zoom = '1.25'")
    one_frame(page)
    page.locator("#p1").click(click_count=3)
    page.keyboard.press("c")
    bar = page.locator(".lf-fab-bar")
    field = bar.locator(".lf-fab-input")
    expect(field).to_be_focused()
    content = "better; is there a way of shortening? or maybe we just remove it??"
    page.keyboard.insert_text(content)
    rendered(page)
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", content)
    bounds = bar.bounding_box()
    assert 0 <= bounds["x"] and bounds["x"] + bounds["width"] <= width + 0.1, bounds
    for part in bar.locator(
        ".lf-compose-field, .lf-fab-input, .lf-compose-submit"
    ).all():
        box = part.bounding_box()
        assert bounds["x"] <= box["x"] and box["x"] + box["width"] <= (
            bounds["x"] + bounds["width"] + 0.1
        ), (bounds, box)
    with sending(page, "the zoomed narrow-window comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    view = page.locator(PANEL_THREAD)
    expect(view).to_be_visible()
    expect(view.locator(".lf-msg-text").first).to_contain_text(content)
    bounds = view.bounding_box()
    assert 0 <= bounds["x"] and bounds["x"] + bounds["width"] <= width + 0.1, bounds
    resized(page, 1440, 900)
    rendered(page)
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    text = card.locator(".lf-msg-text").first
    assert text.evaluate("el => el.scrollHeight <= el.clientHeight + 1")


def test_a_scaled_floating_draft_keeps_its_room_when_its_passage_scrolls_away(
    browser, serve
):
    """A scaled draft keeps its allocation and native editor until Resume reveals it."""
    page = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-fab-bar").evaluate(
        """bar => {
          const holder = document.createElement('div');
          holder.style.cssText = 'position:fixed;inset:0;pointer-events:none;'
            + 'transform:scale(1.2);transform-origin:0 0';
          const home = bar.parentElement;
          home.before(holder); holder.append(home);
        }"""
    )
    resized(page, 390, 620)
    page.locator("#p1").click(click_count=3)
    bar = page.locator(".lf-fab-bar")
    field = bar.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    content = "\n".join(
        f"Line {n}: every word stays in the scaled editor." for n in range(80)
    )
    write(field, content)
    rendered(page)
    native_field = field.element_handle()
    before = bar.bounding_box()
    scale = bar.evaluate(
        "el => el.getBoundingClientRect().width / parseFloat(getComputedStyle(el).width)"
    )
    assert scale == pytest.approx(1.2, abs=0.001)
    page.mouse.move(20, 100)
    page.mouse.wheel(0, 1000)
    page.wait_for_function(
        "document.querySelector('#p1').getBoundingClientRect().bottom < 0"
    )
    scroll_settled(page)
    resized(page, 390, 600)
    rendered(page)
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", content)
    after = bar.bounding_box()
    assert field.evaluate("(node, original) => node === original", native_field)
    assert after["y"] + after["height"] < 0, after
    assert after["height"] <= before["height"] + 0.1, (before, after)
    assert 8 <= after["x"] and after["x"] + after["width"] <= 382.1, (before, after)
    assert after["width"] <= before["width"] + 0.1, (before, after)

    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(field).to_be_focused()
    scroll_settled(page)
    rendered(page)
    expect(field).to_have_js_property("value", content)
    assert field.evaluate("(node, original) => node === original", native_field)
    resumed = bar.bounding_box()
    assert 8 <= resumed["x"] and resumed["x"] + resumed["width"] <= 382.1, resumed
    assert 6 <= resumed["y"] + 0.1, resumed
    assert resumed["y"] + resumed["height"] <= 592.1, resumed
