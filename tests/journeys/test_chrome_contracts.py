"""Everyday browser contracts for shared chrome."""

import re

import pytest
from browser.test_chrome_contracts import (
    FACE,
    FACES,
    FOLLOWED,
    MARKDOWN,
    PHONE_PAGE,
    REPLY_BOX,
    STATE_PAINT,
)
from interact_support import append_carried_log_record
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import (
    SUGGESTION_PAGE,
    panel_comment,
)
from render_cases_layout import (
    BANNER_ORDER,
    banner_control,
    button_radius,
    token_colour,
)
from render_cases_navigation import _publish, source_revision
from render_harness import (
    LONG_PAGE,
    CutOff,
    compare_with,
    consume_browser_errors,
    holding,
    leaf_page,
    nudge,
    open_page,
    open_versions,
    page_comment,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
    sending,
    told,
    write,
)


@pytest.mark.parametrize("viewport", [(390, 740), (1200, 900)])
def test_refusal_notice_clears_live_reply_through_wrapping_and_expiry(
    browser, serve, viewport
):
    """Feedback clears the actual reply while its controls keep their place."""
    url = serve(
        leaf_page("Reply refusal", "<h1>Reply refusal</h1><p>Keep the reply live.</p>")
    )
    panel_comment(serve.page_dir, "A reply belongs beside this question.")
    context = browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    reply = page.locator(".lf-thread[open] > .lf-thread-reply")
    field = reply.locator("leaf-text")
    send = reply.get_by_role("button", name="Send", exact=True)
    mic = reply.get_by_role("button", name="Dictate", exact=True)
    words = "Keep this reply in the writing box when the server refuses it."
    write(field, words)
    rendered(page)
    list_foot = page.locator(".lf-threads").evaluate(
        "node => [getComputedStyle(node).paddingBottom, getComputedStyle(node).scrollPaddingBottom]"
    )
    field.evaluate("""field => {
        window.__noticeReplyFrames = [];
        new ResizeObserver(() => {
            const status = document.querySelector('.lf-bottom-status');
            if (!status.checkVisibility()) return;
            const r = node => node.getBoundingClientRect().toJSON();
            window.__noticeReplyFrames.push({status:r(status), field:r(field),
                send:r(field.parentElement.querySelector('button:not([hidden])'))});
        }).observe(field);
    }""")

    held = []

    def hold_reply(route):
        command = route.request.post_data_json
        if command.get("kind") == "reply":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold_reply)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the provisional reply before refusal")
    rendered(page)
    expect(send).to_be_hidden()
    expect(mic).to_be_visible()
    before = {"field": field.bounding_box(), "send": mic.bounding_box()}
    pending = held.pop()
    pending.fulfill(
        status=400,
        json={
            "ok": False,
            "final": True,
            "attempt": pending.request.post_data_json["attempt"],
            "error": "This reply was refused; your words stay here so you can retry.",
        },
    )
    round_trip(page)
    consume_browser_errors(page, {"code": "failed-load", "status": 400})
    notice = page.locator(".lf-notice")
    expect(notice).to_contain_text("Couldn't send")
    expect(notice).to_be_visible()
    expect(field).to_have_js_property("value", words)
    expect(send).to_be_visible()
    expect(mic).to_be_hidden()
    rendered(page)
    restored = field.bounding_box()
    assert send.bounding_box() == before["send"]
    assert (restored["x"], restored["width"]) == (
        before["field"]["x"],
        before["field"]["width"],
    )
    assert restored["y"] + restored["height"] == pytest.approx(
        before["field"]["y"] + before["field"]["height"], abs=0.5
    )
    before = {"field": restored, "send": send.bounding_box()}

    write(
        field,
        words + "\nKeep the feedback clear when this draft wraps onto more lines.",
    )
    rendered(page)
    expect(notice).to_be_visible()
    assert field.bounding_box()["height"] > before["field"]["height"]
    after = {"field": field.bounding_box(), "send": send.bounding_box()}

    def send_inset(pose):
        return (
            pose["field"]["y"]
            + pose["field"]["height"]
            - pose["send"]["y"]
            - pose["send"]["height"]
        )

    assert send_inset(after) == pytest.approx(send_inset(before), abs=0.5), (
        before,
        after,
    )
    assert after["send"]["x"] == before["send"]["x"]
    frames = page.evaluate("window.__noticeReplyFrames")
    assert frames
    for frame in frames:
        for key in ("field", "send"):
            box, status = frame[key], frame["status"]
            assert (
                status["right"] <= box["left"]
                or box["right"] <= status["left"]
                or status["bottom"] <= box["top"]
                or box["bottom"] <= status["top"]
            ), frame
    assert (
        page.locator(".lf-threads").evaluate(
            "node => [getComputedStyle(node).paddingBottom, getComputedStyle(node).scrollPaddingBottom]"
        )
        == list_foot
    )
    expect(notice).to_be_hidden()
    rendered(page)
    assert {"field": field.bounding_box(), "send": send.bounding_box()} == after
    page.unroute_all(behavior="wait")


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
    notice = page.locator(".lf-notice")
    expect(live).to_have_text("Codex replied")
    expect(notice).to_have_text("Codex replied")
    expect(notice).not_to_have_class(re.compile(r"\bshow\b"))

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(f'.lf-thread[data-id="{drafting["id"]}"]')).to_have_attribute(
        "open", ""
    )
    draft = page.locator(f'.lf-thread[data-id="{drafting["id"]}"] leaf-text')
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
    expect(notice).to_have_text("Codex replied")
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
    expect(notice).to_have_text("2 replies in 2 threads")
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


def test_incoming_reply_follows_a_thread_at_its_latest_message(browser, serve):
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Start this thread.")
    for index in range(14):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root,
                "text": f"Earlier answer {index}. " * 5,
            },
        )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads")
    editor = page.locator(".lf-thread[open] .lf-thread-reply leaf-text")
    write(editor, "A short follow-up.")
    assert threads.evaluate("el => el.scrollHeight > el.clientHeight")
    threads.evaluate("el => el.scrollTop = el.scrollHeight")
    threads.evaluate("el => el.scrollTop -= 40")
    near_end = threads.evaluate("el => el.scrollTop")
    editor_top = editor.evaluate("el => el.getBoundingClientRect().top")

    newest = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "The new answer should come into view. " * 5,
        },
    )
    told(page)
    message = page.locator(f'.lf-msg[data-mid="{newest["id"]}"]')
    expect(message).to_be_visible()
    page.wait_for_function(
        "before => document.querySelector('.lf-threads').scrollTop > before",
        arg=near_end,
    )
    assert threads.evaluate("el => el.scrollTop") > near_end
    assert editor.evaluate("el => el.getBoundingClientRect().top") == pytest.approx(
        editor_top, abs=2
    )
    page.wait_for_function(
        """id => {
          const list = document.querySelector('.lf-threads');
          const message = list.querySelector(`[data-mid="${id}"]`);
          const bottom = list.getBoundingClientRect().bottom -
            parseFloat(getComputedStyle(list).scrollPaddingBottom);
          return message.getBoundingClientRect().bottom <= bottom + 2;
        }""",
        arg=newest["id"],
    )

    for length in (20, 40, 120):
        before_growth = threads.evaluate("el => el.scrollTop")
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "edit",
                "author": "agent",
                "agent": "Codex",
                "message": newest["id"],
                "text": "The answer grows while the user is following it. " * length,
            },
        )
        told(page)
        page.wait_for_function(
            "before => document.querySelector('.lf-threads').scrollTop > before",
            arg=before_growth,
        )
        assert editor.evaluate("el => el.getBoundingClientRect().top") == pytest.approx(
            editor_top, abs=2
        )
        assert message.evaluate("el => el.getBoundingClientRect().bottom") <= editor_top

    threads.evaluate("el => el.scrollTop -= 160")
    earlier_place = threads.evaluate("el => el.scrollTop")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "Later answer must not pull the user away from history.",
        },
    )
    told(page)
    assert threads.evaluate("el => el.scrollTop") == pytest.approx(earlier_place, abs=2)


# A short card with a card above it, read back toward that card, and with cards below;
# a long card with cards below it and with cards above.
@pytest.mark.parametrize(
    "earlier_cards,later_cards,answers,back_to_top",
    [
        (1, 0, 1, True),
        (0, 3, 1, False),
        (0, 3, 14, False),
        (2, 0, 14, False),
    ],
    ids=[
        "short-after-reading-above",
        "above-cards",
        "scrolled",
        "scrolled-below-cards",
    ],
)
def test_a_reply_lands_above_an_open_cards_reply_box_and_moves_neither_it_nor_its_caret(
    browser, serve, earlier_cards, later_cards, answers, back_to_top
):
    """A short card holds replies behind its notice; a long card follows them above its
    pinned editor. Both retain the writing box and caret, including after reading
    back toward an earlier card.

    The replies are news, so the browser fixture's shift watch fails any move they
    cause."""
    url = serve(LONG_PAGE)
    for index in range(earlier_cards):
        panel_comment(serve.page_dir, f"An earlier thread {index}.")
    root = panel_comment(serve.page_dir, "The thread I am answering.")
    for index in range(answers):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root,
                "text": f"Answer {index}. " * 5,
            },
        )
    for index in range(later_cards):
        panel_comment(serve.page_dir, f"A later thread {index}.")
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    if card.get_attribute("open") is None:
        card.locator(".lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    card.locator(".lf-thread-reply leaf-text").click()
    page.keyboard.type("My reply")
    # This contract starts while reading the latest turn. Entry into a visible reply
    # preserves whatever older reading preceded it; choosing the end is explicit.
    if answers > 1:
        reply_box = card.locator(".lf-thread-reply").bounding_box()
        latest = card.locator(".lf-msg").last.bounding_box()
        assert reply_box is not None and latest is not None
        before = page.locator(".lf-threads").evaluate("el => el.scrollTop")
        page.mouse.move(reply_box["x"] + 20, reply_box["y"] - 20)
        page.mouse.wheel(0, latest["y"] + latest["height"] - reply_box["y"])
        page.wait_for_function(
            "before => document.querySelector('.lf-threads').scrollTop > before",
            arg=before,
        )
        scroll_settled(page, ".lf-threads")
    if back_to_top:
        # Back up toward the card above while the current short editor stays visible.
        page.mouse.wheel(0, -200)
        page.wait_for_function(
            "() => document.querySelector('.lf-threads').scrollTop === 0"
        )
        scroll_settled(page, ".lf-threads")
    rendered(page)
    list_box = page.locator(".lf-threads").evaluate(
        "el => { const r = el.getBoundingClientRect(); return [r.top, r.bottom]; }"
    )
    resting = card.evaluate(REPLY_BOX)
    assert resting["caret"] == [True, 8, 8]
    # The live field and Send remain inside the list's visible reading band.
    assert list_box[0] <= resting["field"][0] < resting["field"][1] <= list_box[1]
    send = card.locator(".lf-thread-send").bounding_box()
    assert list_box[0] <= send["y"] < send["y"] + send["height"] <= list_box[1]

    for news_count, text in enumerate(
        ("A short answer.", "A long answer outgrows the free room. " * 60), start=1
    ):
        newest = append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root,
                "text": text,
            },
        )
        told(page)
        message = page.locator(f'.lf-msg[data-mid="{newest["id"]}"]')
        if answers == 1:
            label = "1 new reply" if news_count == 1 else "2 new replies"
            expect(card.get_by_role("button", name=label, exact=True)).to_be_visible()
            expect(message).to_have_count(0)
        else:
            expect(message).to_be_visible()
            expect(card.locator(".lf-thread-news")).to_have_count(0)
        rendered(page)
        # The list scrolls by whole pixels and a reply's height need not be one, so a
        # box the list follows lands within a pixel of where it stood (0.875px measured
        # on CI's Linux Chrome, nothing on macOS).
        now = card.evaluate(REPLY_BOX)
        assert now["caret"] == resting["caret"]
        assert now["box"] == pytest.approx(resting["box"], abs=0.99), (resting, now)
        assert now["field"] == pytest.approx(resting["field"], abs=0.99), (
            resting,
            now,
        )
        if answers > 1:
            # At the scroll limit, line leading can lie under the pinned editor.
            # The words must clear it, so measure text rather than the message box.
            tail = message.locator(".lf-msg-text > p").last.evaluate(
                """el => {
                  const range = document.createRange();
                  range.selectNodeContents(el);
                  return range.getBoundingClientRect().bottom;
                }"""
            )
            assert list_box[0] < tail <= now["box"][0], (resting, now, tail)


@pytest.mark.parametrize("contents", ["short", "long"])
def test_typing_grows_a_panel_reply_in_flow_or_above_its_pinned_foot(
    browser, serve, contents
):
    """Short editors grow down in flow; pinned editors grow up above the same foot.

    Short growth leaves its preceding words and scroll still. Long growth keeps the
    previous turn readable above the editor, with later cards supplying scroll room.
    """
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "The thread I am answering.")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": (
                "A short answer."
                if contents == "short"
                else "\n\n".join(["Keep the last answer visible while writing."] * 20)
            ),
        },
    )
    for index in range(3):
        panel_comment(serve.page_dir, f"A later thread {index}.")
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card).to_have_attribute("open", "")
    card.locator(".lf-thread-reply leaf-text").click()
    rendered(page)
    if contents == "long":
        reply_box = card.locator(".lf-thread-reply").bounding_box()
        latest = card.locator(".lf-msg").last.bounding_box()
        before_scroll = page.locator(".lf-threads").evaluate("node => node.scrollTop")
        page.mouse.move(reply_box["x"] + 20, reply_box["y"] - 20)
        page.mouse.wheel(0, latest["y"] + latest["height"] - reply_box["y"])
        page.wait_for_function(
            "before => document.querySelector('.lf-threads').scrollTop > before",
            arg=before_scroll,
        )
        scroll_settled(page, ".lf-threads")
    reading = """card => ({
      scroll: card.parentElement.scrollTop,
      box: (r => [r.top, r.bottom])(card.querySelector(':scope > .lf-thread-reply')
        .getBoundingClientRect()),
      words: [...card.querySelectorAll('.lf-msg')].at(-1).getBoundingClientRect().top,
    })"""
    before = card.evaluate(reading)

    page.keyboard.type("First line")
    for line in ("Second line", "Third line", "Fourth line"):
        page.keyboard.press("Shift+Enter")
        page.keyboard.type(line)
    rendered(page)
    after = card.evaluate(reading)
    if contents == "short":
        assert after["box"][0] == pytest.approx(before["box"][0], abs=1)
        assert after["box"][1] > before["box"][1] + 40, (before, after)
        assert after["scroll"] == before["scroll"]
        assert after["words"] == pytest.approx(before["words"], abs=1)
    else:
        assert after["box"][0] < before["box"][0] - 40, (before, after)
        assert after["box"][1] == pytest.approx(before["box"][1], abs=1)
        latest = card.locator(".lf-msg").last.bounding_box()
        assert latest["y"] + latest["height"] <= after["box"][0] + 0.5, (latest, after)


# The narrow window is read while walking, which stands on the same edges as reading
# without a walk and adds the walk's position to them.
@pytest.mark.parametrize(
    ("viewport", "walking"),
    [((1200, 900), False), ((390, 740), True)],
    ids=["wide", "narrow-walking"],
)
def test_reading_inside_a_long_thread_keeps_its_title_and_reply_row_on_the_lists_edges(
    browser, serve, viewport, walking
):
    """Scrolled into the middle of an open thread, its title stands on the list's top
    edge and its reply row on the bottom edge, and nothing of the transcript shows
    beyond either. The list pads both ends for focus rings; a row pinned inside that
    padding left a strip of the thread's words visible below Reply, while the title
    scrolled away with the words. Walking threads over a covering panel takes no room
    from the list: the walk's position once stood under Reply on a strip reserved for
    it. Hit tests read what the user sees at each edge, so a row standing short of it
    shows as the wrong element there."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "A thread long enough to read inside.")
    for index in range(14):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root,
                "text": f"Answer {index}. " * 12,
            },
        )
    panel_comment(serve.page_dir, "A later thread.")
    context = browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    if card.get_attribute("open") is None:
        card.locator(":scope > .lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    if walking:
        card.locator(":scope > .lf-thread-summary").evaluate(
            "el => el.focus({preventScroll: true})"
        )
        page.keyboard.press("t")
        page.keyboard.press("Shift+t")
        expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
        expect(page.locator(".lf-bottom-status")).to_be_hidden()
    edges = card.evaluate(
        """async card => {
          const {notice} = await window.__lfWidgetApi();
          notice('Keep feedback clear while reading', {announce: false});
          const list = card.parentElement;
          list.scrollTop = card.offsetTop + (card.offsetHeight - list.clientHeight) / 2;
          const port = list.getBoundingClientRect();
          const top = port.top + list.clientTop;
          const bottom = top + list.clientHeight;
          const title = card.querySelector(':scope > .lf-thread-summary');
          const reply = card.querySelector(':scope > .lf-thread-reply');
          const x = (port.left + port.right) / 2;
          const at = (y) => document.elementFromPoint(x, y);
          const foot = reply.getBoundingClientRect().bottom;
          const below = [];
          for (let y = foot + 0.5; y < bottom; y += 2) below.push(y);
          const reading = {
            top, bottom,
            title: title.getBoundingClientRect().top,
            reply: foot,
            atTop: title.contains(at(top + 1)),
            atBottom: [...below, bottom - 0.5].every((y) => reply.contains(at(y))),
            inside: card.getBoundingClientRect().top < top
              && card.getBoundingClientRect().bottom > bottom,
          };
          // Every row passes under the title: nothing it holds at rest, such as a
          // reaction trigger raised over its message, paints through it.
          const through = new Set();
          const feedback = document.querySelector('.lf-bottom-status');
          const feedbackTops = new Set();
          const start = list.scrollTop;
          for (let y = card.offsetTop; y < card.offsetTop + card.offsetHeight; y += 6) {
            list.scrollTop = y;
            await new Promise(requestAnimationFrame);
            if (feedback.checkVisibility()) feedbackTops.add(feedback.getBoundingClientRect().top);
            const box = title.getBoundingClientRect();
            for (let x = box.left + 2; x < box.right; x += 4) {
              const hit = document.elementFromPoint(x, box.top + box.height / 2);
              if (!title.contains(hit)) through.add(hit?.className?.baseVal ?? hit?.className);
            }
          }
          list.scrollTop = start;
          return {...reading, through: [...through], feedbackTops: [...feedbackTops]};
        }"""
    )
    assert edges["inside"], edges
    assert edges["title"] == pytest.approx(edges["top"], abs=0.5), edges
    # The row stands a ring's room above the list's foot, and its own ground reaches
    # the edge below it.
    assert edges["bottom"] - 20 < edges["reply"] <= edges["bottom"], edges
    assert edges["atTop"] and edges["atBottom"], edges
    assert edges["through"] == [], edges
    assert len(edges["feedbackTops"]) == 1, edges
    # What the user is reading stops at both pinned rows: the runtime's reading of what
    # is on screen, which read acknowledgement takes, leaves out the band under each
    # (geometry.js), so a turn half under Reply has not been seen there.
    seen = card.evaluate(
        """async card => {
          const {seenRect} = await window.__lfCheckApi();
          const turns = [...card.querySelectorAll('.lf-msg')];
          const turn = turns[Math.floor(turns.length / 2)];
          // Put an actual message across each edge: a fixed scroll fraction may
          // put the edge in a gap when message heights or native fonts change.
          const across = async (selector, edge) => {
            const control = card.querySelector(selector);
            const box = turn.getBoundingClientRect();
            card.parentElement.scrollTop += (box.top + box.bottom) / 2
              - control.getBoundingClientRect()[edge];
            await new Promise(requestAnimationFrame);
            const placed = turn.getBoundingClientRect();
            return {
              edge: control.getBoundingClientRect()[edge],
              top: placed.top, bottom: placed.bottom,
              seen: seenRect(turn, new Map()),
            };
          };
          return {
            under: await across(':scope > .lf-thread-reply', 'top'),
            over: await across(':scope > .lf-thread-summary', 'bottom'),
          };
        }"""
    )
    for reading in seen.values():
        assert reading["top"] < reading["edge"] < reading["bottom"], seen
        assert reading["seen"] is not None, seen
    assert seen["under"]["seen"]["bottom"] <= seen["under"]["edge"] + 0.5, seen
    assert seen["over"]["seen"]["top"] >= seen["over"]["edge"] - 0.5, seen
    # An open reaction list hangs below its trigger in the top layer, and goes once the
    # trigger leaves the list, so scrolling its message up under the title still leaves
    # the title whole.
    message = card.locator(".lf-msg.agent").first
    message.hover()
    message.locator(".lf-react-trigger").click()
    expect(message.locator(":scope > .lf-react-strip")).to_contain_class(
        "lf-react-open"
    )
    covered = message.evaluate(
        """async message => {
          const list = message.closest('.lf-threads');
          const title = list.querySelector(':scope > .lf-thread[open] > .lf-thread-summary');
          list.scrollTop += message.getBoundingClientRect().top
            - title.getBoundingClientRect().top - 12;
          for (let i = 0; i < 2; i++) await new Promise(requestAnimationFrame);
          const box = title.getBoundingClientRect();
          const xs = [];
          for (let x = box.left + 2; x < box.right; x += 4) xs.push(x);
          return xs.filter((x) => !title.contains(
            document.elementFromPoint(x, box.top + box.height / 2))).length;
        }"""
    )
    assert covered == 0
    # Wheeled on until its trigger has left the list, the list closes rather than
    # staying open unseen, so the keys answer the thread being read.
    away = message.evaluate(
        """message => {
          const list = message.closest('.lf-threads');
          const port = list.getBoundingClientRect();
          return {x: (port.left + port.right) / 2, y: (port.top + port.bottom) / 2,
                  by: message.getBoundingClientRect().bottom - port.top + 40};
        }"""
    )
    page.mouse.move(away["x"], away["y"])
    page.mouse.wheel(0, away["by"])
    expect(message.locator(":scope > .lf-react-strip")).not_to_contain_class(
        "lf-react-open"
    )
    expect(page.locator(".lf-react-palette:popover-open")).to_have_count(0)


def test_react_brings_a_long_threads_latest_reply_into_view_above_its_reply_row(
    browser, serve
):
    """`e` answers the latest reply of the thread the user stands in, wherever the
    list is scrolled. Its list hangs from the reply's trigger and closes once that
    trigger leaves the list, so the reply comes into view to be answered, above the
    pinned reply row rather than under it."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "A thread long enough to read inside.")
    for index in range(40):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root,
                "text": f"Answer {index}. " * 12,
            },
        )
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    if card.get_attribute("open") is None:
        card.locator(":scope > .lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    summary = card.locator(":scope > .lf-thread-summary")
    summary.focus()
    expect(summary).to_be_focused()
    strip = card.locator(".lf-react-strip.lf-open")
    read = """strip => {
      const list = strip.closest('.lf-threads');
      const port = list.getBoundingClientRect();
      const trigger = strip.querySelector('.lf-react-trigger').getBoundingClientRect();
      const reply = list.querySelector(':scope > .lf-thread[open] > .lf-thread-reply');
      const palette = strip.querySelector('.lf-react-palette');
      const box = palette.getBoundingClientRect();
      const hit = strip.getRootNode().elementFromPoint(
        (box.left + box.right) / 2, (box.top + box.bottom) / 2);
      return {
        inList: trigger.bottom > port.top && trigger.top < port.bottom,
        clear: reply.getBoundingClientRect().top - trigger.bottom,
        open: palette.matches(':popover-open'),
        shown: palette.contains(hit),
      };
    }"""
    # Focusing the title lands the thread's end; read from near its start instead.
    page.wait_for_function(
        """card => new Promise((done) => {
          const list = card.parentElement;
          list.scrollTop = card.offsetTop + 300;
          requestAnimationFrame(() => requestAnimationFrame(() =>
            done(list.scrollTop === card.offsetTop + 300)));
        })""",
        arg=card.element_handle(),
    )
    assert not strip.evaluate(read)["inList"]
    page.keyboard.press("e")
    expect(strip).to_contain_class("lf-react-open")
    after = strip.evaluate(read)
    assert after["open"] and after["shown"], after
    assert after["clear"] >= 0, after


def test_incoming_reply_follows_a_visible_composer_below_earlier_words(browser, serve):
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "A thread with a draft.")
    for index in range(14):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root,
                "text": f"Earlier answer {index}. " * 5,
            },
        )
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads")
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    write(card.locator(".lf-thread-reply leaf-text"), ("A draft line.\n" * 8).strip())
    threads.evaluate("el => el.scrollTop = el.scrollHeight")
    before = threads.evaluate("el => el.scrollTop")
    prior = card.locator(".lf-msg").last
    fold = threads.evaluate(
        "el => el.getBoundingClientRect().bottom - parseFloat(getComputedStyle(el).scrollPaddingBottom)"
    )
    assert prior.evaluate("el => el.getBoundingClientRect().bottom") < fold - 80
    assert prior.evaluate("el => el.getBoundingClientRect().bottom") > threads.evaluate(
        "el => el.getBoundingClientRect().top"
    )

    newest = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "This reply grows below the older words and above the draft. " * 20,
        },
    )
    told(page)
    page.wait_for_function(
        "before => document.querySelector('.lf-threads').scrollTop > before", arg=before
    )
    # The turn and the draft fit together, so the draft the user is writing stays at the
    # list's foot with the turn above it.
    assert page.evaluate(FOLLOWED, newest["id"])
    assert card.evaluate("el => el.getBoundingClientRect().bottom") == pytest.approx(
        fold, abs=2
    )


@pytest.mark.parametrize("later_cards", [4, 30])
def test_incoming_reply_follows_a_selected_thread_before_later_cards(
    browser, serve, later_cards
):
    url = serve(LONG_PAGE)
    selected = panel_comment(serve.page_dir, "The thread I am reading.")
    for index in range(14):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": selected,
                "text": f"Selected answer {index}. " * 5,
            },
        )
    for index in range(later_cards):
        panel_comment(serve.page_dir, f"A later thread {index}.")
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{selected}"]')
    card.locator(".lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    # At the thread's end: its last words stand above the reply box at the list's foot.
    card.evaluate("el => el.scrollIntoView({block: 'end', behavior: 'instant'})")
    threads = page.locator(".lf-threads")
    before = threads.evaluate("el => el.scrollTop")
    assert (
        threads.evaluate("el => el.scrollHeight - el.clientHeight - el.scrollTop") > 80
    )
    end = card.evaluate("el => el.getBoundingClientRect().bottom")

    newest = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": selected,
            "text": "This new answer belongs to the selected thread. " * 5,
        },
    )
    told(page)
    page.wait_for_function(
        "before => document.querySelector('.lf-threads').scrollTop > before",
        arg=before,
    )
    assert page.evaluate(FOLLOWED, newest["id"])
    # The turn grew up into the room scrolled past: its reply box and the cards after it
    # stand where they stood.
    assert card.evaluate("el => el.getBoundingClientRect().bottom") == pytest.approx(
        end, abs=2
    )

    card.locator(".lf-msg").last.evaluate(
        "el => el.scrollIntoView({block: 'start', behavior: 'instant'})"
    )
    # Naming a later card transfers the reading anchor to it. The idle thread still
    # draws appended replies immediately, without moving that later reading.
    later = page.locator(f'.lf-thread[data-id="{selected}"] + .lf-thread')
    later.locator(".lf-thread-summary").hover()
    reading_later = later.evaluate("el => el.getBoundingClientRect().top")
    also_visible = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": selected,
            "text": "This short answer arrives while I read later cards.",
        },
    )
    told(page)
    arriving = card.locator(f'.lf-msg[data-mid="{also_visible["id"]}"]')
    expect(arriving).to_have_count(1)
    expect(card.locator(".lf-thread-news")).to_have_count(0)
    assert later.evaluate("el => el.getBoundingClientRect().top") == pytest.approx(
        reading_later, abs=2
    )

    if later_cards == 30:
        threads.evaluate("el => el.scrollTop += 160")
        reading_later = later.evaluate("el => el.getBoundingClientRect().top")
        assert card.evaluate(
            "el => el.getBoundingClientRect().bottom"
        ) < threads.evaluate(
            "el => el.getBoundingClientRect().bottom - parseFloat(getComputedStyle(el).scrollPaddingBottom) - 80"
        )
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": selected,
                "text": "A long answer must not pull me back to this thread. " * 120,
            },
        )
        told(page)
        assert later.evaluate("el => el.getBoundingClientRect().top") == pytest.approx(
            reading_later, abs=2
        )


@pytest.mark.parametrize("intent", ["focus", "pointer"])
def test_a_later_cards_reader_stays_at_the_list_end(browser, serve, intent):
    url = serve(LONG_PAGE)
    selected = panel_comment(serve.page_dir, "The thread above.")
    for index in range(14):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": selected,
                "text": f"Earlier answer {index}. " * 5,
            },
        )
    for index in range(4):
        panel_comment(serve.page_dir, f"A later thread {index}.")
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{selected}"]')
    card.locator(".lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    threads = page.locator(".lf-threads")
    threads.evaluate("el => el.scrollTop = el.scrollHeight")
    before = threads.evaluate("el => el.scrollTop")
    assert before > 0
    later_card = threads.locator(":scope > .lf-thread:not([hidden])").last
    if intent == "focus":
        # Walked to by key, so the later thread opens under the user's own input and
        # the thread above closes: the reader stands in the later thread.
        for _ in range(4):
            page.keyboard.press("t")
        expect(later_card.locator(".lf-thread-summary")).to_be_focused()
        expect(later_card).to_have_attribute("open", "")
        rendered(page)
    else:
        later_card.locator(".lf-thread-summary").hover()
    later_top = later_card.evaluate("el => el.getBoundingClientRect().top")

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": selected,
            "text": "A long answer should not pull me from the later cards. " * 120,
        },
    )
    told(page)
    assert later_card.evaluate("el => el.getBoundingClientRect().top") == pytest.approx(
        later_top, abs=2
    )


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
    shown = page.locator(".lf-notice")
    expect(shown).to_have_text("Saved — sent")
    expect(shown).to_have_text("Updated to v4")


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
              const field = thread.querySelector('.lf-thread-reply leaf-text');
              return {
                messages: [...thread.querySelectorAll('.lf-msg')].map(message => ({
                  body: styles(message.querySelector('.lf-msg-body'), type),
                  author: styles(message.querySelector(':scope > .lf-msg-head b'), type),
                })),
                metadata: styles(thread.querySelector('.lf-msg-meta'), type),
                field: styles(field, [...type, 'padding-top', 'padding-right', 'padding-bottom',
                  'padding-left', 'min-height']),
                surround: styles(thread.querySelector('.lf-thread-reply .lf-compose-field'),
                  ['border-radius', 'border-top-width', 'border-top-color', 'background-color']),
              };
            }"""
        )

    anchored = faces(margin)
    assert len(anchored["messages"]) == 2
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    panel = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    if panel.get_attribute("open") is None:
        panel.locator(".lf-thread-summary").click()
    expect(panel.get_by_role("textbox", name="Reply", exact=True)).to_be_visible()
    assert faces(panel) == anchored, scheme
    expect(panel.locator(f'.lf-msg[data-mid="{answer["id"]}"]')).to_contain_text(
        "Keep the evidence."
    )
    write(panel.get_by_role("textbox", name="Reply", exact=True), "Sent from Threads.")
    with sending(page, "the panel follow-up"):
        panel.get_by_role("button", name="Send", exact=True).click()
    expect(panel.locator(".lf-msg").last).to_contain_text("Sent from Threads.")

    page.get_by_role("button", name="Close threads", exact=True).click()
    panel_settled(page, False)
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


def test_a_news_resolved_card_keeps_its_place_after_an_offscreen_draft_is_cleared(
    browser, serve
):
    """Going off screen with words does not turn news into the user's settlement.

    The reader returns to the retained card and explicitly reopens its conversation
    to recover the saved draft. Another agent settlement keeps that actual editing
    session. Clearing its words keeps that empty editor active; Escape ends editing,
    a move within the thread, so the card holds the settlement behind its notice until
    the user presses it, and stays put.
    """
    url = serve(LONG_PAGE, comments=24)
    first, second = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ][:2]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-threads > .lf-thread[data-id="{first}"]')
    after = page.locator(f'.lf-threads > .lf-thread[data-id="{second}"]')
    expect(card).to_have_attribute("open", "")
    reply = card.locator("leaf-text")
    words = "Keep this draft while I read the next thread."
    write(reply, words)
    below = after.bounding_box()

    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "agent", "parent": first}
    )
    told(page)
    rendered(page)
    expect(card.get_by_role("button", name="Resolved", exact=True)).to_be_visible()
    expect(reply).to_have_js_property("value", words)
    assert after.bounding_box() == below

    threads = page.locator(".lf-threads")
    threads.hover()
    page.mouse.wheel(0, card.bounding_box()["height"] + 30)
    scroll_settled(page, ".lf-threads")
    after.locator(".lf-thread-summary").click()
    expect(after).to_have_attribute("open", "")
    expect(card).not_to_have_attribute("open", "")
    page.mouse.wheel(0, 100)
    scroll_settled(page, ".lf-threads")
    assert card.evaluate("node => node.getBoundingClientRect().bottom") < (
        threads.evaluate("list => list.getBoundingClientRect().top")
    ), "the resolved card must be closed and entirely off screen"
    rendered(page)

    page.mouse.wheel(0, -4000)
    scroll_settled(page, ".lf-threads")
    assert threads.evaluate("list => list.scrollTop") == 0
    card.locator(".lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    expect(card).to_have_attribute("data-resolved", "true")
    expect(reply).to_have_count(0)
    with sending(page, "explicitly reopen the saved reply"):
        card.get_by_role("button", name="Reopen", exact=True).click()
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", words)
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "agent", "parent": first}
    )
    told(page)
    rendered(page)
    expect(reply).to_be_focused()
    stood = after.bounding_box()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    rendered(page)
    expect(card).to_be_visible()
    expect(card.get_by_role("button", name="Resolved", exact=True)).to_be_visible()
    expect(reply).to_be_visible()
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "")
    assert after.bounding_box() == stood
    page.keyboard.press("Escape")
    rendered(page)
    expect(reply).to_be_visible()
    card.get_by_role("button", name="Resolved", exact=True).click()
    rendered(page)
    expect(reply).to_have_count(0)
    expect(card).to_be_visible()
    assert after.bounding_box() == stood


@pytest.mark.parametrize(("scheme", "width"), [("dark", 320), ("light", 800)])
def test_a_thread_keeps_submit_in_its_field_and_resolve_beside_its_header(
    browser, serve, width, scheme
):
    """The field action belongs to the field; Resolve shares the first message's line.

    Empty fields offer Dictate; typing replaces it with Send in the same slot.
    Growing the field leaves its action at its foot and Resolve fixed. The field
    puts its words on the messages' reading edge, and keeps their inset as the
    field grows and scrolls, leaving room for its action in the same row.
    Resolve stays beside the first header while each message keeps its author and time.
    The same layout holds at narrow and wide panel widths in both palettes."""
    context = browser.new_context(
        viewport={"width": width, "height": 720}, color_scheme=scheme
    )
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread:not([hidden])")
    thread.locator(".lf-thread-summary").click()
    compose = thread.locator(".lf-thread-reply")
    field_box = compose.locator("leaf-text")
    send = thread.get_by_role("button", name="Send", exact=True)
    mic = thread.get_by_role("button", name="Dictate", exact=True)
    resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    close = page.get_by_role("button", name="Close threads", exact=True)
    expect(mic).to_be_visible()
    expect(send).to_be_hidden()
    expect(resolve).to_be_visible()
    expect(mic.locator('svg[data-lf-icon="microphone"]')).to_have_count(1)
    expect(resolve.locator('svg[data-lf-icon="check"]')).to_have_count(1)
    expect(close.locator('svg[data-lf-icon="cross"]')).to_have_count(1)
    expect(thread.get_by_role("button", name="Close thread", exact=True)).to_have_count(
        0
    )
    expect(mic).to_have_text("")
    expect(resolve).to_have_text("")
    expect(close).to_have_text("")

    def geometry():
        return thread.evaluate(
            """thread => {
                  const action = '.lf-compose-field > button:not([hidden])';
                  const rect = sel => {
                    const r = thread.querySelector(sel).getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height,
                            right: r.right, bottom: r.bottom};
                  };
                  const own = thread.getBoundingClientRect();
                  const inputStyle = getComputedStyle(thread.querySelector('leaf-text'));
                  const messageStyle = getComputedStyle(thread.querySelector('.lf-msg-body'));
                  const padding = parseFloat(inputStyle.paddingInlineEnd);
                  // The action's room beyond the padding, kept after the last words.
                  const room = parseFloat(inputStyle.getPropertyValue('--lf-field-end-room'));
                  const radius = (selector, pseudo = null) => getComputedStyle(
                    selector.startsWith('.lf-thread-panel')
                      ? document.querySelector(selector)
                      : thread.querySelector(selector), pseudo).borderRadius;
                  return {thread: {x: own.x, y: own.y, width: own.width,
                                   height: own.height, right: own.right, bottom: own.bottom},
                          compose: rect('.lf-thread-reply'), field: rect('.lf-compose-field'),
                          field_box: rect('.lf-thread-reply leaf-text'),
                          metadataActions: rect('.lf-thread-meta-actions'),
                          action: rect(action), resolve: rect('.lf-resolve'),
                          closeBorder: getComputedStyle(document.querySelector(
                            '.lf-thread-panel-head [aria-label="Close threads"]')).borderTopWidth,
                          resolveBorder: getComputedStyle(thread.querySelector(
                            '.lf-resolve'), '::before').borderTopWidth,
                          actionBorder: getComputedStyle(thread.querySelector(
                            action), '::before').borderTopWidth,
                          radii: {
                            action: radius(action),
                            actionFill: radius(action, '::before'),
                            resolve: radius('.lf-resolve'),
                            resolveFill: radius('.lf-resolve', '::before'),
                            close: radius('.lf-thread-panel-head [aria-label="Close threads"]'),
                          },
                          message: rect('.lf-msg-body'),
                          header: rect('.lf-msg > .lf-msg-head'),
                          author: rect('.lf-msg > .lf-msg-head b'),
                          messageFont: messageStyle.font,
                          inputFont: inputStyle.font,
                          textStart: rect('.lf-thread-reply leaf-text').x +
                            parseFloat(inputStyle.borderInlineStartWidth) +
                            parseFloat(inputStyle.paddingInlineStart),
                          textEnd: rect('.lf-thread-reply leaf-text').right -
                            parseFloat(inputStyle.borderInlineEndWidth) - padding - room,
                          padding,
                          overflow: thread.scrollWidth - thread.clientWidth};
                }"""
        )

    short = geometry()
    assert field_box.evaluate("el => el.endRoom") == "none"
    text_inset = short["textStart"] - short["field"]["x"]
    assert short["textStart"] == pytest.approx(short["message"]["x"], abs=1)
    assert short["field"]["right"] == pytest.approx(short["message"]["right"], abs=1)
    assert short["field"]["x"] - short["thread"]["x"] == pytest.approx(
        short["thread"]["right"] - short["field"]["right"], abs=1
    )
    assert short["field_box"]["right"] == pytest.approx(short["field"]["right"], abs=1)
    assert short["action"]["right"] < short["field_box"]["right"]
    assert short["field_box"]["y"] < short["action"]["y"]
    assert short["action"]["bottom"] < short["field_box"]["bottom"]
    assert short["textEnd"] <= short["action"]["x"]
    assert short["field"]["height"] < 50
    assert short["resolve"]["y"] == pytest.approx(short["header"]["y"], abs=1)
    assert short["metadataActions"]["right"] == pytest.approx(
        short["message"]["right"], abs=1
    )
    assert short["resolve"]["right"] == pytest.approx(
        short["metadataActions"]["right"], abs=1
    )
    assert short["author"]["x"] == pytest.approx(short["message"]["x"], abs=1)
    assert short["header"]["right"] <= short["resolve"]["x"]
    assert float(short["closeBorder"][:-2]) == 0
    assert float(short["resolveBorder"][:-2]) == 0
    assert float(short["actionBorder"][:-2]) == 0
    assert set(short["radii"].values()) == {button_radius(page)}
    assert short["overflow"] == 0

    field_box.focus()
    focused = geometry()
    assert focused["action"] == short["action"]
    assert focused["resolve"] == short["resolve"]

    write(field_box, "First line.\nSecond line.\nThird line.\nFourth line.")
    expect(send).to_be_visible()
    expect(mic).to_be_hidden()
    expect(send.locator('svg[data-lf-icon="send"]')).to_have_count(1)
    expect(send).to_have_text("")
    grown = geometry()
    assert grown["inputFont"] == grown["messageFont"]
    assert grown["textStart"] - grown["field"]["x"] == pytest.approx(text_inset, abs=1)
    assert grown["textEnd"] <= grown["action"]["x"]
    assert grown["padding"] == pytest.approx(short["padding"], abs=1)
    assert grown["action"]["bottom"] < grown["field_box"]["bottom"]
    # The short field grows downward and its action stays at the field's foot.
    assert grown["field_box"]["y"] == pytest.approx(short["field_box"]["y"], abs=1)
    growth = grown["field_box"]["height"] - short["field_box"]["height"]
    assert growth > 0
    assert grown["action"]["y"] - short["action"]["y"] == pytest.approx(growth, abs=1)
    assert grown["action"]["x"] == short["action"]["x"]
    assert grown["metadataActions"] == short["metadataActions"]
    assert grown["resolve"] == short["resolve"]
    assert grown["overflow"] == 0

    write(field_box, "A long draft remains readable while scrolling. " * 120)
    assert field_box.evaluate("el => el.scrollHeight > el.clientHeight")
    for position in (0, 80, 99999):
        field_box.evaluate("(el, top) => el.scrollTop = top", position)
        scrolling = geometry()
        # A scrolled draft carries every line past Send, so each keeps its room.
        assert field_box.evaluate("el => el.endRoom") == "every-line"
        assert scrolling["action"]["bottom"] < scrolling["field_box"]["bottom"]
        assert scrolling["textStart"] - scrolling["field"]["x"] == pytest.approx(
            text_inset, abs=1
        )
        assert scrolling["textEnd"] <= scrolling["action"]["x"]


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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread:not([hidden])")
    thread.locator(".lf-thread-summary").click()
    field = thread.locator(".lf-thread-reply leaf-text")
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
    full = reading()
    page.keyboard.press("Shift+Enter")
    opened = reading()
    page.keyboard.type("S")
    typed = reading()
    assert opened["height"] == full["height"] == typed["height"], (full, opened, typed)
    assert opened["top"] == full["top"] == typed["top"]
    assert typed["rows"][: len(full["rows"])] == full["rows"]


def test_a_menu_comparison_keeps_its_active_paint(browser, serve):
    """An active comparison remains legible in its fixed menu seat."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    _publish(serve.page_dir, 2, html, "reworded the suggestion")
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    picker = page.locator(".lf-version")
    expect(picker).to_be_enabled()

    resized(page, 1440, 900)
    compare_with(page, 1)
    expect(picker).to_have_class(re.compile(r"\bon\b"))
    expect(page.locator(".lf-banner-menu > .lf-version")).to_have_count(1)
    banner_control(page, ".lf-version")
    page.evaluate("scrollTo(0, document.documentElement.scrollHeight)")
    box = picker.bounding_box()
    assert box and 0 <= box["y"] < page.evaluate("innerHeight"), box
    active = picker.evaluate(STATE_PAINT)
    assert (
        active["shadow"] != "none" and "rgba(0, 0, 0, 0)" not in active["background"]
    ), f"the comparison stood in the menu with nothing but ink: {active}"

    resized(page, 320, 844)
    expect(page.locator(".lf-banner-menu > .lf-version")).to_have_count(1)
    banner_control(page, ".lf-version")
    assert picker.evaluate(STATE_PAINT) == active
    picker.click()
    versions = page.locator(".lf-version-menu")
    expect(versions).to_be_visible()
    box = versions.bounding_box()
    assert box and 0 <= box["y"] < page.evaluate("innerHeight"), box
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    open_versions(page)
    expect(versions).to_be_visible()
    box = versions.bounding_box()
    assert box and 0 <= box["y"] < page.evaluate("innerHeight"), box
    # The door's news is the toolbar's to state, and it restates it on every paint. A
    # newer version puts the urgent latest chip in the menu, so the dot the door
    # takes is the one the page arrived at rather than one the test wrote on it, beside
    # the suggestion's question already waiting behind it. The
    # news is a dot and not an accent contour, which is the focus ring's face: a door
    # drawn that way read as focused while the user typed somewhere else.
    door = page.locator(".lf-banner-more")
    _publish(serve.page_dir, 3, html, "reworded the suggestion again")
    told(page)
    expect(door).to_have_attribute(
        "aria-label", "More page controls, questions waiting, new"
    )
    accent = token_colour(page, "--accent")
    face = door.evaluate(
        "d => ({dot: getComputedStyle(d, '::after').backgroundColor,"
        " edge: getComputedStyle(d).borderTopColor})"
    )
    assert face["dot"] == accent and face["edge"] != accent, face


def test_the_banner_reads_in_one_order_at_every_width(browser, serve, other_leaf):
    """The fixed menu and primary row keep one reading order at every desk width, and
    a phone reads the same order with Approval, Comment on the page and Questions,
    which stand before Threads on a desk, moved to the head of More."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    panel_comment(serve.page_dir, "Is this ready?", author="agent")
    page = open_page(browser, url)
    expect(page.locator(".lf-others")).to_have_text("All pages (2)")
    expect(page.locator(".lf-signoff")).to_be_disabled()
    expect(page.locator(".lf-signoff")).to_have_attribute(
        "title", "Answer every ask before approving this work"
    )
    banner_control(page, ".lf-answer-all")

    orders = {}
    for width in (1440, 860, 800, 390):
        resized(page, width, 900)
        orders[width] = page.evaluate(BANNER_ORDER)
    phone = orders.pop(390)
    moved = ["Approve version", "Comment on the page", "Questions"]
    assert phone[: len(moved)] == moved, phone
    rest = phone[len(moved) :]
    assert rest[:-1] + moved + rest[-1:] == orders[800], (phone, orders[800])

    first = {}
    for width, order in orders.items():
        for index, before in enumerate(order):
            for after in order[index + 1 :]:
                assert (after, before) not in first, (
                    f"{after!r} comes before {before!r} at {first[(after, before)]}px "
                    f"and after it at {width}px: {orders}"
                )
                first.setdefault((before, after), width)
    assert len(first) >= 15, (
        f"too few controls stood at these widths to have an order at all: {orders}"
    )

    # More follows the primary reading loop, with one order at every width.
    widest = max(orders.values(), key=len)
    for wanted in ("All pages", "Questions", "Accept all", "v1", "Approve version"):
        assert any(wanted in name for name in widest), (
            f"{wanted} was not on the row at all, so this order proves little: {widest}"
        )
    for width, order in orders.items():
        assert order[-1].startswith("Open threads:"), order
    expect(page.locator(".lf-banner-actions > :last-child")).to_have_class(
        re.compile(r"\blf-banner-more\b")
    )
    resized(page, 500, 900)
    control = banner_control(page, ".lf-others")
    control.click()
    page.mouse.move(0, page.viewport_size["height"] - 1)
    expect(control).to_have_attribute("aria-expanded", "true")
    expect(control).to_have_css("background-color", token_colour(page, "--chip"))


@pytest.mark.parametrize("viewport", [None, "width=device-width, initial-scale=1"])
def test_a_phone_starts_the_page_and_comments_on_a_selection(iphone, serve, viewport):
    """The runtime starts in WebKit; selection offers an explicit Comment action.

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
    # The selection's next step stands on the row in the reading loop's place, where
    # the finger that made the selection finds it; More stays shut.
    comment = page.locator(".lf-banner-actions").get_by_role(
        "button", name="Comment on selection"
    )
    expect(comment).to_be_visible()
    expect(page.locator(".lf-banner-menu")).to_be_hidden()
    expect(page.locator(".lf-threads-toggle")).to_be_hidden()
    box = comment.bounding_box()
    assert box["x"] + box["width"] <= page.evaluate("innerWidth"), box
    comment.tap()
    expect(page.locator(".lf-banner-menu")).to_be_hidden()
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
    """The composer's Markdown preview draws each construct the way the message will.

    The preview stands in the field's closed shadow root, where the theme's element
    rules do not reach, so it reads the faces from the theme's tokens instead of
    stating its own. It had stated its own from birth: a quote drafted upright with a
    heavy dark rule was sent italic with a light one, and code sat a size and a chip
    shape away from how it arrived. DevTools reads the closed root, as it reads any.
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
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        page.locator(".lf-thread-summary").first.click()
        thread = page.locator(".lf-thread[open]")
        box_selector = ".lf-thread[open] .lf-thread-reply leaf-text"
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
    # The page's general box stands in the page comment card, the one place a page
    # thread starts.
    box = page_comment(page) if surface == "general" else page.locator(box_selector)
    write(box, MARKDOWN)
    box.evaluate("box => box.id = 'draft-face-editor'")

    sent = body.evaluate(
        """(body, [faces, face]) => Object.fromEntries(Object.entries(faces)
          .map(([name, [selector]]) => {
            const style = getComputedStyle(body.querySelector(selector));
            return [name, Object.fromEntries(
              [...face, "font-size"].map((p) => [p, style.getPropertyValue(p)]))];
          }))""",
        [FACES, FACE],
    )
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
    # are the box's type where the message's are the body's; a code block is set at the
    # code size whatever holds it. A draft marks a heading by weight alone, at the size
    # of its words, so a heading's size is left out.
    def px(value):
        return float(value.removesuffix("px"))

    size = {
        "draft": box.evaluate("box => getComputedStyle(box).fontSize"),
        "sent": body.evaluate("body => getComputedStyle(body).fontSize"),
    }
    for face, which in ((draft, "draft"), (sent, "sent")):
        del face["heading"]["font-size"]
        for name in FACES.keys() - {"heading", "code block"}:
            share = px(face[name]["font-size"]) / px(size[which])
            face[name]["font-size"] = round(share, 3)
    differ = {
        name: {
            k: (v, sent[name][k]) for k, v in draft[name].items() if v != sent[name][k]
        }
        for name in FACES
    }
    assert not any(differ.values()), differ
