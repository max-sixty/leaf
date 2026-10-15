"""Comment-panel ordering, narrowing, and thread-motion tests."""

import io
import re

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    append_command,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import thread as thread_model
from leaf.read_state import content_version
from leaf.render_checks import rendered, wait_until_ready
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    THREAD_DIFF_PAGE,
    panel_comment,
)
from render_cases_layout import (
    COVERED_TOP,
    button_radius,
    ring_faults,
    rings_drawn,
)
from render_harness import (
    EXAMPLES,
    LONG_PAGE,
    consume_browser_errors,
    example_media,
    holding,
    open_page,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
    sending,
    told,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_threads import (
    BARE_PAGE,
    BURIED_TITLE,
    CAPTURE_SAMPLE_PAGE,
    CHANGE_PAGE,
    IN_LANDING_BAND,
    LANDING_WORDS,
    OPEN_TITLE,
    REPLY_CHANGE,
    append_agent_reply,
    capture_page,
    claim_for_codex,
    focus_panel_thread,
    open_capture_area,
    open_threads_list,
    paste_image,
    pressed_send_surface,
    reply_by_keyboard,
    seed_panel_threads,
    seed_reply,
    standing_thread,
    stream_reply,
    summarize_thread,
    thread_mark_fault,
)


@pytest.mark.watch_shifts
def test_held_news_keeps_an_agent_header_and_resizes_its_notice(browser, serve):
    """Held news keeps metadata, body and both independent actions still.

    A long agent name fills the desktop header. Narrowing the viewport while its
    replies wait must remeasure the retained metadata allocation, leaving the notice
    reachable beside the root message's reaction and the thread's Resolve action.
    """
    url = serve(PANEL_PAGE)
    opening = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Codex reviewing the presentation and interaction of the shared thread controls",
            "revision": 1,
            "text": "Which jobs should start first?",
        },
    )
    root = opening["id"]
    # This test measures the held replies; the opening agent comment is already read.
    # Its long-name arrival notice would otherwise expire during the phone layout
    # measurement and replace the status text with an unrelated reply notice.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "read",
            "author": "user",
            "messages": [{"message": root, "version": content_version(opening)}],
        },
    )
    page = open_page(browser, url)
    resized(page, 1440, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    focus_panel_thread(thread)
    thread.locator("leaf-text").focus()
    message = thread.locator(".lf-msg").first
    message.hover()
    reaction = message.locator(".lf-react-trigger")
    expect(reaction).to_be_visible()
    rendered(page)
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )

    def geometry():
        return thread.evaluate("""thread => {
          const first = thread.querySelector('.lf-msg');
          const rect = selector => {
            const r = first.querySelector(selector).getBoundingClientRect();
            return {x: r.x, y: r.y, width: r.width, height: r.height};
          };
          const r = thread.querySelector('.lf-resolve').getBoundingClientRect();
          return {author: rect('.lf-msg-head b'), time: rect('.lf-msg-head time'),
            body: rect('.lf-msg-body'), reaction: rect('.lf-react-trigger'),
            resolve: {x: r.x, y: r.y, width: r.width, height: r.height}};
        }""")

    before = geometry()
    notice_box = None
    for number in (1, 2):
        append_agent_reply(serve.page_dir, root, f"Held answer {number}.")
        told(page)
        rendered(page)
        news = thread.locator(".lf-thread-news")
        expect(news).to_be_visible()
        news.hover()
        expect(news).to_have_css("box-shadow", "none")
        expect(news).to_have_css("background-color", "rgba(0, 0, 0, 0)")
        expect(news).to_have_css("text-decoration-line", "underline")
        expect(thread.locator(".lf-msg")).to_have_count(1)
        assert geometry() == before
        if notice_box is None:
            notice_box = news.bounding_box()
        else:
            # The notice holds the room of the words it first showed, so longer news
            # is cut there rather than widening it; its title keeps the words whole.
            assert news.bounding_box() == notice_box
            expect(news).to_have_attribute("title", "2 new replies")
            assert news.evaluate(
                "n => { const w = n.querySelector('span');"
                " return w.scrollWidth > w.clientWidth; }"
            )

    resized(page, 360, 900)
    rendered(page)
    expect(news).to_have_attribute("title", "2 new replies")
    allocation = news.evaluate("""news => {
      const thread = news.closest('.lf-thread');
      const notice = news.getBoundingClientRect();
      const reaction = thread.querySelector('.lf-msg .lf-react-trigger').getBoundingClientRect();
      const resolve = thread.querySelector('.lf-resolve').getBoundingClientRect();
      const hit = news.getRootNode().elementFromPoint(
        notice.left + notice.width / 2, notice.top + notice.height / 2);
      return {width: notice.width, hit: news.contains(hit),
        noticeRight: notice.right, reactionLeft: reaction.left,
        reactionRight: reaction.right, resolveLeft: resolve.left};
    }""")
    assert allocation["width"] >= 28, allocation
    assert allocation["hit"], allocation
    assert allocation["noticeRight"] <= allocation["reactionLeft"], allocation
    assert allocation["reactionRight"] <= allocation["resolveLeft"], allocation
    news.click()
    expect(thread.locator(".lf-msg")).to_have_count(3)
    expect(thread.locator(".lf-thread-news")).to_have_count(0)


@pytest.mark.watch_shifts
def test_a_reply_sent_while_the_agent_streams_moves_nothing_when_accepted(
    browser, serve, request
):
    """The user's message joins the thread above the reply still streaming, where the
    log will take that reply's answer, so the log accepting it moves nothing, and the
    stream's growth in the same readings is its arrival, not an edit.

    The panel drew the user's pending message below the streaming reply, and the
    accepted reading, whose live reply stands after every logged message, moved the
    reply below it.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Record the release", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "First words")

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    streamed = thread.locator(".lf-msg.agent")
    expect(streamed.locator(".lf-msg-text")).to_have_text("First words")
    write(thread.locator(":scope > .lf-thread-reply leaf-text"), "And note the date")
    # The shift watch holds the acceptance to moving nothing; the order is where the
    # send drew it.
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    told(page)
    messages = thread.locator(".lf-msg")
    expect(messages).to_have_count(3)
    expect(messages.nth(1)).to_contain_text("And note the date")
    expect(messages.nth(2)).to_contain_text("First words")

    page.locator("body").click(position={"x": 5, "y": 5})
    stream_reply(serve.page_dir, root, "First words and more of them")
    told(page)
    expect(streamed.locator(".lf-msg-text")).to_have_text(
        "First words and more of them"
    )
    expect(thread.locator(".lf-thread-news")).to_have_count(0)


@pytest.mark.watch_shifts
def test_a_reopen_refused_after_the_input_window_moves_nothing(held_events, serve):
    """The refusal returns the user to Resolved without a gesture of theirs, so the
    filters and the thread they stand on hold still through it. Resolved hid the
    Waiting on filters that Open shows, so the return took that row away and moved
    everything below it up by its height; and each count that gained a digit, as
    Page (1) does becoming Page (24), pushed the choices after it along the row."""
    browser, held = held_events
    url = serve(LONG_PAGE)
    roots = []
    for i in range(24):
        root = panel_comment(serve.page_dir, f"Resolved thread {i}. " + LANDING_WORDS)
        append_carried_log_record(
            serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
        )
        roots.append(root)
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    resolved = page.locator('[data-filter-value="resolved"]')
    resolved.click()
    card = page.locator(f'.lf-thread[data-id="{roots[0]}"]')
    title = card.locator(":scope > .lf-thread-summary")
    focus_panel_thread(card)
    page.keyboard.press("r")
    holding(page, held, 1, "the reopen the log will refuse")
    expect(resolved).to_have_attribute("aria-pressed", "false")
    rendered(page)
    scroll_settled(page, ".lf-threads")
    # Chrome reports no shift within 500ms of input, so the refusal lands after it.
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    before = title.bounding_box()["y"]
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    round_trip(page)
    expect(resolved).to_have_attribute("aria-pressed", "true")
    expect(title).to_be_focused()
    rendered(page)
    scroll_settled(page, ".lf-threads")
    assert abs(title.bounding_box()["y"] - before) < 1


def test_a_diff_outlet_keeps_the_shared_attachment_controls(browser, serve):
    """An attachment keeps its face and keyboard routes inside a widget tree."""
    page = open_page(
        browser, serve(next(p for p in EXAMPLES if p.stem == "pr-walkthrough"))
    )
    page.locator("#pr-exact-patch .lf-diff-file-comment").first.click()
    bar = page.locator('lf-diff .lf-fab-bar[data-lf-presentation="inline"]')
    field = bar.locator("leaf-text")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    paste_image(field, pixels)
    image_open = bar.get_by_role("button", name="View attached image 1", exact=True)
    remove = bar.get_by_role("button", name="Remove attached image 1", exact=True)
    expect(image_open.locator("img")).to_be_visible()
    expect(bar.locator(".lf-composer-media-item")).to_have_css(
        "border-radius", button_radius(page)
    )
    expect(image_open).to_have_css("cursor", "zoom-in")
    assert remove.evaluate("""button => {
      const box = button.getBoundingClientRect();
      const root = button.getRootNode();
      return [box.top + 1, box.bottom - 1].every(y =>
        button.contains(root.elementFromPoint(box.left + box.width / 2, y)));
    }"""), "the whole removal control must accept a press inside the scrolling shelf"
    field.press("Shift+Tab")
    expect(remove).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(image_open).to_be_focused()
    expect(image_open).to_have_css("outline-style", "solid")
    page.keyboard.press("Enter")
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    expect(viewer.locator("img")).to_have_attribute(
        "src", "/media/051bee487bfb5d13.png"
    )
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    rendered(page)
    expect(image_open).to_be_focused()
    image_open.click()
    expect(viewer).to_be_visible()
    viewer.get_by_role("button", name="Close image preview", exact=True).click()
    expect(viewer).to_be_hidden()
    rendered(page)
    expect(image_open).to_be_focused()
    page.keyboard.press("Tab")
    expect(remove).to_be_focused()
    page.keyboard.press("Enter")
    expect(bar.locator(".lf-composer-media")).to_be_hidden()
    expect(field).to_be_focused()
    field.press("Tab")
    expect(bar).to_have_class(re.compile(r"\blf-response-open\b"))
    page.keyboard.press("Escape")
    expect(field).to_be_focused()
    action = bar.locator(".lf-compose-field > button:visible")
    action.focus()
    expect(action).to_be_focused()
    page.keyboard.press("Escape")
    expect(bar).to_be_hidden()

    page.locator("#pr-exact-patch .lf-diff-file-comment").first.click()
    paste_image(field, pixels)
    with sending(page, "the image in a file comment"):
        field.press("ControlOrMeta+Enter")
    sent = page.locator("#pr-exact-patch .lf-message-media img")
    expect(sent).to_be_visible()
    sizing = sent.evaluate("""image => {
      const box = image.getBoundingClientRect();
      return {width: box.width, height: box.height, ratio:
        image.naturalWidth / image.naturalHeight, ceiling: Math.min(innerHeight * .6, 480)};
    }""")
    assert sizing["height"] <= sizing["ceiling"]
    assert sizing["width"] == pytest.approx(sizing["height"] * sizing["ratio"], abs=1)
    sent.click()
    expect(viewer).to_be_visible()
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()


def test_a_phone_editor_inside_a_marked_widget_keeps_pointer_entry(browser, serve):
    """Inspecting an attachment and pressing its editor cannot activate the page mark."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(
        browser,
        serve(next(p for p in EXAMPLES if p.stem == "pr-walkthrough")),
        context=context,
    )
    comment = page.locator("#pr-exact-patch .lf-diff-file-comment").first
    comment.click()
    field = page.get_by_role("textbox", name=re.compile(r"^Comment on .+ · file$"))
    expect(field).to_be_focused()
    page.keyboard.type("Earlier file comment.")
    with sending(page, "the earlier file comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    first = events_model.read_events(serve.page_dir)[-1]

    comment.click()
    expect(field).to_be_focused()
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    paste_image(field, pixels)
    page.get_by_role("button", name="View attached image 1", exact=True).click()
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    field.click()
    expect(field).to_be_focused()
    words = "Phone final review: image and greeting checked."
    page.keyboard.type(words)
    expect(field).to_have_js_property("value", words)
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")
    with sending(page, "the file comment after image inspection"):
        page.keyboard.press("ControlOrMeta+Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["kind"] == "comment"
    assert sent["anchor"] == first["anchor"]
    assert sent["text"] == words + "\n\n![Attached image](/media/051bee487bfb5d13.png)"
    assert "about" not in sent


def test_a_pasted_image_survives_the_reply_draft_and_renders_from_the_message(
    browser, serve
):
    """Every thread text box shares one paste path, exercised through a reply.

    The binary body becomes page media before its Markdown reference enters the normal
    draft generation. Reload and Send then prove the existing durable-text path owns the
    rest of the loop, down to the exact pixels the rendered message reads back.
    """
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Can you show me the rendering fault?",
        {"section": "how-store"},
        "agent",
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    thread.locator(".lf-thread-summary").click()
    reply = thread.locator("leaf-text")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()

    paste_image(reply, pixels)

    image_markdown = "![Attached image](/media/051bee487bfb5d13.png)"
    expect(reply).to_have_js_property("value", "")
    draft_image = thread.locator(".lf-composer-media img")
    expect(draft_image).to_be_visible()
    expect(draft_image).to_have_attribute("src", "/media/051bee487bfb5d13.png")
    remove = thread.locator(".lf-composer-media-remove")
    expect(remove.locator("..")).to_have_css("border-radius", button_radius(page))
    expect(thread.get_by_role("button", name="Send", exact=True)).to_have_attribute(
        "aria-disabled", "false"
    )

    page.reload()
    wait_until_ready(page)
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    thread.locator(".lf-thread-summary").click()
    reply = thread.locator("leaf-text")
    expect(reply).to_have_js_property("value", "")
    expect(thread.locator(".lf-composer-media img")).to_be_visible()
    # Mirroring compares the complete draft rather than the text box's projection. A
    # local keystroke must therefore keep the caret where the user put it even while
    # hidden image Markdown rides beside the visible words.
    write(reply, "Fault here")
    reply.evaluate("box => box.setSelectionRange(6, 6)")
    reply.press_sequentially("is ")
    expect(reply).to_have_js_property("value", "Fault is here")

    with sending(page, "the reply containing the pasted image"):
        thread.get_by_role("button", name="Send", exact=True).click()
    saved = events_model.read_events(serve.page_dir)[-1]
    assert (saved["kind"], saved["parent"], saved["text"]) == (
        "reply",
        root,
        f"Fault is here\n\n{image_markdown}",
    )
    image = thread.locator(".lf-msg.user .lf-msg-body img")
    expect(image).to_have_attribute("src", "/media/051bee487bfb5d13.png")
    media_open = image.locator("xpath=..")
    expect(media_open).to_have_attribute(
        "data-lf-media-url", "/media/051bee487bfb5d13.png"
    )
    page.wait_for_function(
        "image => image.naturalWidth > 0", arg=image.element_handle()
    )
    url_before = page.url
    media_open.click()
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    assert viewer.evaluate("dialog => dialog.matches(':modal')")
    expect(viewer.locator("img")).to_have_attribute(
        "src", "/media/051bee487bfb5d13.png"
    )
    assert page.url == url_before
    # The modal viewer holds the keyboard: a page command does not reach the page.
    page.keyboard.press("w")
    expect(viewer).to_be_visible()
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")
    close = viewer.get_by_role("button", name="Close image preview", exact=True)
    expect(close.locator('svg[data-lf-icon="cross"]')).to_have_count(1)
    close.click()
    expect(viewer).to_be_hidden()
    expect(media_open).to_be_focused()
    media_open.click()
    expect(viewer).to_be_visible()
    expect(viewer.locator("img")).to_have_attribute(
        "src", "/media/051bee487bfb5d13.png"
    )
    expect(viewer.locator("img")).to_have_attribute("alt", "Attached image")
    # Native close notification arrives after its gesture. An image opened before that
    # notification belongs to the new opening and keeps both its pixels and focus.
    reopened = media_open.evaluate(
        """trigger => new Promise(resolve => {
          const viewer = document.querySelector('#lf-media-viewer');
          viewer.addEventListener('close', () => resolve({
            open: viewer.open,
            image: viewer.querySelector('img')?.getAttribute('src') ?? null,
            focused: viewer.contains(document.activeElement),
          }), {once: true});
          // The sensor sees one task ending where it began as an unchanged `open`
          // write; here the two native transitions deliberately exercise that race.
          window.lfUnwatched(() => {
            viewer.close();
            trigger.click();
          });
        })"""
    )
    assert reopened == {
        "open": True,
        "image": "/media/051bee487bfb5d13.png",
        "focused": True,
    }
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    expect(media_open).to_be_focused()
    assert (serve.page_dir / "media" / "051bee487bfb5d13.png").read_bytes() == pixels


@pytest.mark.watch_shifts
@pytest.mark.parametrize("reply_size", ["short", "tall"])
def test_an_idle_open_panel_thread_shows_appended_replies(browser, serve, reply_size):
    """An append moves the idle reply and later cards, preserving existing messages.

    Even an answer taller than the panel must leave the previous reading in place;
    following the end is reserved for a reply row that was already pinned.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep the discussion here.")
    later = panel_comment(serve.page_dir, "A later conversation.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    focus_panel_thread(thread)
    message = thread.locator(".lf-msg").first
    field = thread.locator("leaf-text")
    following = page.locator(f'.lf-threads > .lf-thread[data-id="{later}"]')
    rendered(page)
    before = {
        "message": message.bounding_box(),
        "reply": field.bounding_box(),
        "following": following.bounding_box(),
        "scroll": page.locator(".lf-threads").evaluate("list => list.scrollTop"),
    }
    words = "The answer arrived without another click."
    if reply_size == "tall":
        words = "\n\n".join([words] * 30)
    reply = append_agent_reply(serve.page_dir, root, words)
    told(page)
    expect(thread.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_be_visible()
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    rendered(page)
    assert message.bounding_box() == before["message"]
    assert field.bounding_box()["y"] > before["reply"]["y"]
    assert following.bounding_box()["y"] > before["following"]["y"]
    assert (
        page.locator(".lf-threads").evaluate("list => list.scrollTop")
        == before["scroll"]
    )


@pytest.mark.watch_shifts
def test_news_from_elsewhere_moves_nothing_in_a_short_panel_thread(browser, serve):
    """A reaction made in another tab waits behind a short card's notice, as a reply does.

    Its strip would add a row under the answer and push Reply down. While it waits, a
    press on the strip means what the strip drew, so choosing the reaction that already
    stands sends nothing, and shows what waits. A count news changes keeps its filter's
    width."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep the discussion here.")
    answer = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "parent": root,
            "text": "An answer to react to.",
        },
    )["id"]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    if thread.get_attribute("open") is None:
        thread.locator(".lf-thread-summary").click()
    page.locator(".lf-thread-filter-toggle").click()
    strip = thread.locator(f'.lf-msg[data-mid="{answer}"] > .lf-react-strip')
    keep = strip.locator('.lf-react[data-token="keep"]')
    field = thread.locator("leaf-text")
    filters = page.locator(".lf-thread-filter:visible")
    rendered(page)
    # Chrome reports no shift within 500ms of input, so the news lands after it.
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    before = field.bounding_box()
    widths = filters.evaluate_all("bs => bs.map(b => b.getBoundingClientRect().width)")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": answer,
            "token": "keep",
        },
    )
    panel_comment(serve.page_dir, "A second thread raises a count.", author="agent")
    told(page)
    notice = thread.get_by_role("button", name="1 reaction changed", exact=True)
    expect(notice).to_be_visible()
    expect(keep).to_have_attribute("aria-pressed", "false")
    expect(page.get_by_role("button", name="Open (2)", exact=True)).to_be_visible()
    rendered(page)
    assert field.bounding_box() == before
    assert (
        filters.evaluate_all("bs => bs.map(b => b.getBoundingClientRect().width)")
        == widths
    )

    # The press means the face it drew, so the reaction already in force sends
    # nothing, and acting in the thread shows what it holds.
    logged = len(events_model.read_events(serve.page_dir))
    thread.locator(f'.lf-msg[data-mid="{answer}"]').hover()
    strip.locator(".lf-react-trigger").click()
    keep.click()
    expect(notice).to_have_count(0)
    expect(keep).to_have_attribute("aria-pressed", "true")
    expect(keep).to_be_visible()
    rendered(page)
    assert len(events_model.read_events(serve.page_dir)) == logged


@pytest.mark.watch_shifts
def test_a_settlement_from_elsewhere_moves_nothing_in_a_short_panel_thread(
    browser, serve
):
    """A thread resolved or reopened elsewhere waits behind the open card's notice.

    Resolving would take away the card's reply box and its answer's reaction strip,
    and reopening would put them back, moving the card and every card below it. The
    card stands as drawn and says which, and a press on its Resolve means what it drew,
    so on a thread already resolved it sends nothing and shows the resolution. A
    folded card draws one title row whatever its thread's state, so news reaches it
    at once."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep the discussion here.")
    answer = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "parent": root,
            "text": "An answer to react to.",
        },
    )["id"]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": answer,
            "token": "keep",
        },
    )
    folded = panel_comment(serve.page_dir, "A folded thread below it.")
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": folded}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # Every thread, so a resolved card stays in the view.
    page.locator(".lf-thread-filter-toggle").click()
    for value in ("open", "resolved"):
        choice = page.locator(f'[data-filter-value="{value}"]')
        if choice.get_attribute("aria-pressed") == "true":
            choice.click()
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    below = page.locator(f'.lf-threads > .lf-thread[data-id="{folded}"]')
    if thread.get_attribute("open") is None:
        thread.locator(".lf-thread-summary").click()
    keep = thread.locator(f'.lf-msg[data-mid="{answer}"] .lf-react[data-token="keep"]')
    field = thread.locator("leaf-text")
    words = thread.locator(f'.lf-msg[data-mid="{answer}"] .lf-msg-text')

    def news_lands(record):
        rendered(page)
        # Chrome reports no shift within 500ms of input, so the news lands after it.
        page.wait_for_function(
            "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
        )
        boxes = words.bounding_box(), below.bounding_box()
        append_carried_log_record(serve.page_dir, record)
        told(page)
        rendered(page)
        assert (words.bounding_box(), below.bounding_box()) == boxes

    news_lands({"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root})
    expect(thread.get_by_role("button", name="Resolved", exact=True)).to_be_visible()
    expect(keep).to_have_attribute("aria-pressed", "true")
    logged = len(events_model.read_events(serve.page_dir))
    thread.get_by_role("button", name="Resolve thread").click()
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    expect(field).to_have_count(0)
    expect(thread).to_have_attribute("data-resolved", "true")
    rendered(page)
    assert len(events_model.read_events(serve.page_dir)) == logged

    # The resolved card draws no row below its messages, so its notice stands in the
    # title, in Reopen's place, and takes the user standing on Reopen with it. It is the
    # thread's reopen control there, so `r` presses it.
    reopen = thread.locator(":scope > .lf-reopen")
    reopen.focus()
    news_lands({"kind": "unresolve", "author": "user", "parent": root})
    notice = thread.locator(":scope > .lf-thread-news")
    expect(notice).to_have_text("Reopened")
    expect(notice).to_be_visible()
    expect(notice).to_be_focused()
    expect(thread).to_have_attribute("data-resolved", "true")
    page.keyboard.press("r")
    expect(thread).to_have_attribute("data-resolved", "false")
    expect(field).to_be_visible()
    expect(thread.locator(":scope > .lf-thread-summary")).to_be_focused()

    append_carried_log_record(
        serve.page_dir, {"kind": "unresolve", "author": "user", "parent": folded}
    )
    told(page)
    expect(below).to_have_attribute("data-resolved", "false")


@pytest.mark.watch_shifts
@pytest.mark.parametrize("replies", [3, 14])
def test_a_summary_from_elsewhere_moves_nothing_in_an_open_panel_card(
    browser, serve, replies
):
    """An agent's summary over replies the user can see waits behind the card's notice.

    Drawing it would put the checkpoint's label and words above the replies it covers,
    opened around them since they are being read, and move them and everything after
    them: in a short card the cards below, and in one taller than the panel, whose reply
    box is pinned to the list's foot, the rest of the card under the user. The card
    stands as drawn, and pressing the notice draws the summary."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Check the schedule.")
    sent = [
        append_agent_reply(serve.page_dir, root, f"Checking dependency {number}.")
        for number in range(replies)
    ]
    second, third = sent[replies // 2 - 1], sent[replies // 2]
    below = panel_comment(serve.page_dir, "A thread below it.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    after = page.locator(f'.lf-threads > .lf-thread[data-id="{below}"]')
    if thread.get_attribute("open") is None:
        thread.locator(".lf-thread-summary").click()
    words = thread.locator(f'.lf-msg[data-mid="{third["id"]}"] .lf-msg-text')
    words.evaluate("node => node.scrollIntoView({block: 'center'})")
    if replies > 3:
        after = thread.locator(f'.lf-msg[data-mid="{sent[replies // 2 + 1]["id"]}"]')
        assert thread.locator(":scope > .lf-thread-reply").evaluate(
            "reply => getComputedStyle(reply).position === 'sticky'"
            " && reply.getBoundingClientRect().bottom"
            " < reply.closest('.lf-thread').getBoundingClientRect().bottom"
        ), "the reply box is not pinned, so the tall card proves nothing"
    rendered(page)
    # Chrome reports no shift within 500ms of input, so the news lands after it.
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    boxes = words.bounding_box(), after.bounding_box()
    summary = summarize_thread(
        serve.page_dir, second["id"], third["id"], "The schedule was confirmed."
    )
    told(page)
    notice = thread.get_by_role("button", name="1 summary changed", exact=True)
    expect(notice).to_be_visible()
    expect(thread.locator(".lf-thread-checkpoint")).to_have_count(0)
    rendered(page)
    assert (words.bounding_box(), after.bounding_box()) == boxes

    notice.click()
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    expect(
        thread.locator(f'.lf-thread-checkpoint[data-summary-id="{summary["id"]}"]')
    ).to_be_visible()


def test_the_panel_composes_state_scope_subject_and_placement_facets(browser, serve):
    """Optional status, waiting, scope, subject and placement refinements compose.
    Counts describe named subsets, and pointer and keyboard toggles clear the same
    restrictions without restoring a status the user already cleared."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    pagewide = panel_comment(d, "A page-wide content note.")
    waiting = panel_comment(
        d, "Which local wording is right?", {"section": "lede"}, "agent"
    )
    design = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "about": "design",
            "text": "The shortcut control is crowded.",
            "anchor": {"section": "lf-shortcut-bar"},
        },
    )["id"]
    gone = panel_comment(d, "The removed section still matters.", {"section": "gone"})
    resolved = panel_comment(d, "This local note is done.", {"section": "how-cap"})
    append_carried_log_record(
        d, {"kind": "resolve", "author": "user", "parent": resolved}
    )

    # One open thread awaits neither party after a complete agent answer.
    settled_turn = panel_comment(d, "A complete answer is available.")
    thread_model.post_reply(
        d, {"to": settled_turn, "for": settled_turn}, "Done; nothing more is needed."
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    visible = page.locator(".lf-threads > .lf-thread:not([hidden])")

    def pick(kind, value):
        return page.locator(f'[data-filter-kind="{kind}"][data-filter-value="{value}"]')

    waiting_group = page.get_by_role("group", name="Waiting on", exact=True)
    waiting_group.evaluate("node => window.__waitingGroup = node")
    for label in ("Status", "Waiting on", "Location", "Subject"):
        expect(page.get_by_role("group", name=label, exact=True)).to_be_visible()
    expect(visible).to_have_count(5)
    expect(pick("status", "open")).to_have_text("Open (5)")
    expect(pick("status", "resolved")).to_have_text("Resolved (1)")
    expect(pick("waiting", "user")).to_have_text("Me (1)")
    expect(pick("waiting", "agent")).to_have_text("Claude (3)")
    expect(pick("scope", "page")).to_have_text("Page (2)")
    expect(pick("scope", "local")).to_have_text("Anchored (3)")
    expect(pick("subject", "content")).to_have_text("Content (4)")
    expect(pick("subject", "design")).to_have_text("Design (1)")

    # Status predicts its transition: Resolved clears Waiting on, so its count is
    # still one while the current user-only selection has no resolved result.
    pick("waiting", "user").click()
    expect(visible).to_have_count(1)
    expect(pick("status", "resolved")).to_have_text("Resolved (1)")
    pick("status", "open").click()
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "true")
    expect(visible).to_have_count(1)
    # Resolved keeps every choice where it stood: Waiting on counts the open threads
    # a press there switches to, and the placement refinement stands while any thread
    # is detached, with nothing to find among the resolved.
    pick("status", "resolved").click()
    expect(waiting_group).to_be_visible()
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "false")
    expect(pick("waiting", "user")).to_have_text("Me (1)")
    expect(pick("waiting", "agent")).to_have_text("Claude (3)")
    expect(pick("unplaced", "unplaced")).to_be_visible()
    expect(pick("unplaced", "unplaced")).to_be_disabled()
    expect(visible).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{resolved}"]')).to_be_visible()
    pick("status", "resolved").click()
    expect(visible).to_have_count(6)
    expect(waiting_group).to_be_visible()
    expect(pick("status", "resolved")).to_have_attribute("aria-pressed", "false")
    pick("status", "open").click()
    expect(waiting_group).to_be_visible()
    assert waiting_group.evaluate("node => node === window.__waitingGroup"), (
        "changing status replaced the retained Waiting on group"
    )
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "false")
    expect(pick("waiting", "agent")).to_have_attribute("aria-pressed", "false")
    expect(visible).to_have_count(5)

    # No selected status means both open and resolved threads. The same active
    # box clears with either a pointer click or Space, without an All control.
    expect(page.get_by_role("button", name=re.compile(r"^All(?: \(|$)"))).to_have_count(
        0
    )
    pick("status", "open").click()
    expect(visible).to_have_count(6)
    expect(pick("status", "open")).to_have_attribute("aria-pressed", "false")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("6 threads")
    pick("waiting", "user").focus()
    page.keyboard.press("Space")
    expect(visible).to_have_count(1)
    page.keyboard.press("Space")
    expect(visible).to_have_count(6)
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "false")
    # The shortcut follows the same toggle as Space, including leaving status
    # unrestricted rather than silently restoring Open when it clears waiting.
    page.locator(".lf-threads").focus()
    page.keyboard.press("w")
    expect(visible).to_have_count(1)
    expect(pick("status", "open")).to_have_attribute("aria-pressed", "false")
    page.keyboard.press("w")
    expect(visible).to_have_count(6)
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "false")
    expect(pick("status", "open")).to_have_attribute("aria-pressed", "false")
    pick("status", "open").click()
    expect(visible).to_have_count(5)
    pick("scope", "local").click()
    expect(visible).to_have_count(3)
    pick("scope", "local").click()
    expect(visible).to_have_count(5)
    pick("scope", "local").click()
    pick("scope", "page").click()
    expect(visible).to_have_count(2)
    expect(pick("scope", "local")).to_have_attribute("aria-pressed", "false")
    expect(pick("waiting", "user")).to_be_disabled()
    page.locator(".lf-threads").focus()
    page.keyboard.press("w")
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "false")
    expect(visible).to_have_count(2)
    pick("scope", "page").click()
    expect(visible).to_have_count(5)

    pick("waiting", "agent").click()
    pick("scope", "local").click()
    expect(visible).to_have_count(2)
    expect(page.locator(f'.lf-thread[data-id="{pagewide}"]')).to_be_hidden()
    expect(page.locator(f'.lf-thread[data-id="{waiting}"]')).to_be_hidden()
    pick("subject", "content").click()
    expect(visible).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{gone}"]')).to_be_visible()
    expect(page.locator(f'.lf-thread[data-id="{design}"]')).to_be_hidden()
    pick("unplaced", "unplaced").click()
    expect(visible).to_have_count(1)
    expect(pick("unplaced", "unplaced")).to_have_text("Not located (1)")
    page.locator(".lf-thread-filter-toggle").click()
    expect(page.locator(".lf-thread-view-summary")).to_have_text(
        "1 of 5 open threads · On Claude · Anchored · Content · Not located"
    )
    page.get_by_role("button", name="Reset thread filters").click()
    expect(visible).to_have_count(5)
    expect(page.locator(".lf-thread-filter-toggle")).to_be_focused()
    page.keyboard.press("Space")

    # A search may empty the selected choice. It stays enabled so the user can
    # clear it, even though only clearing the search can recover matching results.
    pick("scope", "local").click()
    search = page.get_by_role("searchbox", name="Find in threads")
    search.fill("no thread contains these words")
    expect(visible).to_have_count(0)
    expect(pick("scope", "local")).to_have_attribute("aria-pressed", "true")
    expect(pick("scope", "local")).to_be_enabled()
    pick("scope", "local").click()
    expect(pick("scope", "local")).to_have_attribute("aria-pressed", "false")
    expect(pick("status", "open")).to_be_enabled()
    expect(page.locator(".lf-empty")).to_have_text(
        "No open threads match “no thread contains these words”."
    )
    search.fill("")
    expect(visible).to_have_count(5)
    pick("scope", "local").click()
    expect(visible).to_have_count(3)

    # The shortcut toggles only Waiting on and retains Location across both presses.
    page.locator(".lf-threads").focus()
    page.keyboard.press("w")
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "true")
    expect(pick("scope", "local")).to_have_attribute("aria-pressed", "true")
    expect(visible).to_have_count(1)
    page.keyboard.press("w")
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "false")
    expect(pick("waiting", "agent")).to_have_attribute("aria-pressed", "false")
    expect(visible).to_have_count(3)
    pick("status", "resolved").click()
    page.locator(".lf-threads").focus()
    page.keyboard.press("w")
    expect(pick("status", "open")).to_have_attribute("aria-pressed", "true")
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "true")
    expect(pick("scope", "local")).to_have_attribute("aria-pressed", "true")
    expect(visible).to_have_count(1)
    page.keyboard.press("Escape")
    expect(visible).to_have_count(5)
    resized(page, 320, 720)
    rail_size = page.locator(".lf-thread-filters").evaluate(
        "el => ({client: el.clientWidth, scroll: el.scrollWidth})"
    )
    assert rail_size["scroll"] == rail_size["client"], rail_size


def test_a_settlement_in_a_reply_leaves_its_own_anchor_on_the_page(browser, serve):
    """A decided change keeps whatever of itself is still showing, wherever it stands.

    `settledAway` asks whether a decision emptied an element: every child now a retired
    slot or the runtime's own apparatus, with no words of its own left. Asked about the
    page that test is right; asked about a change an agent sent in a reply it was asked
    the wrong way round, because the panel holding it is itself the runtime's apparatus
    and so every child of it answered yes. One accepted slot then emptied a change whose
    other half was on screen: the anchor a user had put on it stopped resolving, the
    outline came off, and the thread stood detached beside the words it was about.

    The same change on the page is the control, and the two must agree."""
    for where, markup, wid in (
        ("the page", CHANGE_PAGE, "tv-doc-sug"),
        ("a reply", BARE_PAGE, "tv-msg-sug"),
    ):
        url = serve(markup)
        d = serve.page_dir
        if wid.startswith("tv-msg"):
            seed_reply(d, REPLY_CHANGE, wid)
        else:
            append_carried_log_record(
                d,
                {
                    "kind": "comment",
                    "id": "tv-on-it",
                    "author": "user",
                    "revision": 1,
                    "text": "Why ninety?",
                    "anchor": {"section": wid},
                },
            )
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": wid,
                "action": "decide",
                "detail": {"outcome": "accept"},
            },
        )
        page = open_page(browser, url)
        resized(page, 1280, 900)
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        if wid.startswith("tv-msg"):
            focus_panel_thread(page.locator('.lf-thread[data-id="tv-decisioned"]'))
            rendered(page)
        settled = page.evaluate(
            """(wid) => {
                 const el = document.getElementById(wid);
                 const quote = document.querySelector('.lf-thread[data-id="tv-on-it"] .lf-quote');
                 return { state: el?.dataset.lfState,
                          retired: [...(el?.querySelectorAll('[data-lf-retired]') ?? [])].length,
                          marked: Boolean(el?.classList.contains('lf-mark-el')),
                          detached: quote?.classList.contains('detached') };
               }""",
            wid,
        )
        assert settled["state"] == "accept" and settled["retired"] == 1, (
            f"{where}: the change did not settle, so nothing here is being read "
            f"({settled})"
        )
        assert not settled["detached"] and settled["marked"], (
            f"{where}: the accepted change took its own anchor off the page "
            f"({settled}) — its other half is still showing"
        )


def test_no_focus_mark_the_panel_draws_on_a_walk_down_its_list_is_cut_or_covered(
    browser, serve
):
    """Where the user is standing has to be visible from wherever they walked to it.
    A walked-to thread wears the inset ring over its own quiet ground; compact controls
    inside the list draw the ring outside themselves. Either treatment can disappear at
    a scroll edge or beneath a neighbour, and the thread list has had both failures in
    both directions.

    So this walks the list the way a user does and asks the invariant at every landing,
    rather than naming the collisions one at a time. A rule stated once is a rule a new
    control inherits; a list of known collisions is a thing to keep adding to.

    Reduced motion, so a landing is a jump: what is asserted is where a walk ends, and
    the runtime reads the preference at load to decide between a glide and a jump."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    # A run per section and enough threads to make the list scroll, which is the whole
    # of what the cut half needs: a list that fits in the panel has no edge to fall off.
    for i in range(5):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})
        panel_comment(d, f"About the whole page, {i}.")

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads > .lf-thread:not([hidden])").count()
    assert threads == 20, f"the fixture built {threads} threads, not the 20 it needs"
    assert page.evaluate(
        "() => { const l = document.querySelector('.lf-threads');"
        " return l.scrollHeight > l.clientHeight; }"
    ), "the list does not scroll, so nothing here can be cut by its edge"

    # The walk keys, not Tab: t/T opens a thread and lands its native summary.
    # Every landing on the way down and again on the way up, because
    # the two directions align opposite edges of the box with the scrollport and
    # only one of them was ever wrong at a time.
    # Standing nowhere, said rather than clicked for: `c` goes to the box belonging to
    # whatever the user is standing in, and a click on the body lands wherever the
    # middle of the document happens to be — which on this page is a diff, whose `pre`
    # takes focus. The press then opened that widget's composer and the walk below
    # typed its keys into the box, which is exactly what the non-vacuity check at the
    # end caught: every landing asserted, none of them on a thread.
    page.evaluate("() => document.activeElement?.blur()")
    # The named address toggles the panel it names, so from a panel opened by its
    # visible control the first completion closes it and the second is the arrival.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(OPEN_TITLE)).to_be_focused()
    walked, faults = 0, []
    # From the first title to the last and back, short of the press that would come
    # round an end.
    for key in ("t",) * (threads - 1) + ("Shift+t",) * (threads - 1):
        page.keyboard.press(key)
        rendered(page)
        walked += 1
        mark_fault = thread_mark_fault(standing_thread(page))
        if mark_fault:
            faults.append(f"after {walked} presses, {mark_fault}")
        faults += ring_faults(rings_drawn(page), f"after {walked} presses of the walk")
        under = page.evaluate(COVERED_TOP)
        if under:
            faults.append(
                f"after {walked} presses, the thread landed past the list's "
                f"top edge: {under}"
            )
    assert not faults, "\n  ".join([f"{len(faults)} of {walked} landings:"] + faults)

    # Non-vacuity: the walk has to have been on a thread inside the scrolling list,
    # repainting its existing card, or the loop above asserted nothing at every step.
    standing = standing_thread(page)
    assert standing, "the walk ends outside a thread"
    assert standing["scrolled"], (
        "the walk ends outside a scroll region, so the cut half proved nothing"
    )

    # The list's own controls, which t and T never reach: Reply and Resolve inside a
    # card draw their rings outside themselves. They are what the room reserved at this list's edges is for — the
    # current thread's paint stays inside its card — so without this pass half of
    # that scroll-padding is unheld. Tab scrolls each stop into view itself,
    # which is the gesture that puts one against an edge. Focus given to the list
    # lands on the open thread's title, which the walk left as the list's first stop.
    page.locator(".lf-threads").focus()
    expect(page.locator(OPEN_TITLE)).to_be_focused()
    # Chromium removes a closed details' contents from both the focus order and
    # checkVisibility, so this is the focus order the browser owns.
    tabbable = page.eval_on_selector_all(
        ".lf-threads *",
        "els => els.filter((e) => e.tabIndex >= 0 && e.checkVisibility()).length",
    )
    assert tabbable, "the list holds no control to tab to"
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-threads *')].find("
        "e => e.tabIndex >= 0 && e.checkVisibility()) === document.activeElement"
    ), "the open thread's title is not the list's first stop"
    faults += ring_faults(rings_drawn(page), "on the open thread's title")
    # Each title Tab reaches opens its thread, so the list's stops grow as the walk goes:
    # it has held every one when it leaves the list from the last.
    on_last = (
        "() => [...document.querySelectorAll('.lf-threads *')]"
        ".filter((e) => e.tabIndex >= 0 && e.checkVisibility()).at(-1)"
        " === document.activeElement"
    )
    stops = 1
    left_from_last = False
    for _ in range(threads * 8):
        last = page.evaluate(on_last)
        page.keyboard.press("Tab")
        rendered(page)
        if not page.evaluate(
            "() => document.querySelector('.lf-threads')"
            ".contains(document.activeElement)"
        ):
            left_from_last = last
            break
        stops += 1
        faults += ring_faults(
            rings_drawn(page), f"tabbing to stop {stops} inside the list"
        )
    assert left_from_last and stops > threads, (
        f"the walk left the list after {stops} stops, before its last control, so the "
        "room it reserves at its edges is only partly held by this"
    )
    assert not faults, "\n  ".join([f"{len(faults)} faults:"] + faults)


def test_a_press_that_opens_a_thread_lands_it_and_holds_it_at_once(browser, serve):
    """Two writers meet inside one press on a thread title. The press lands the thread
    back inside the list's top edge at `pointerup`, and the click that follows
    opens it, which reflows the list and brings its hold down on `scrollTop` a frame
    later. A `scrollTop` write cancels a smooth scroll rather than composing with it, so
    an animated landing is not superseded by what the gesture asks for next — it is
    dropped, and the user is left with neither: the title held exactly where the
    edge was cutting it. The landing under a press is therefore instant, which is
    also what lets the hold take its reference from where the landing put the title.

    Motion stays at its default here. The reduced-motion context the test above builds
    finishes the landing at `pointerup` and hides the collision, and that test presses a
    card's body, which opens nothing."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(viewport={"width": 1200, "height": 900})
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").first.click()
    rendered(page)

    # Nudge until a closed title is cut a few pixels, the user's own case. The open
    # card fills the list's height, so the closed titles start a list's height down.
    buried = None
    reach = page.locator(".lf-threads").evaluate(
        "el => el.scrollHeight - el.clientHeight"
    )
    for top in range(0, reach, 3):
        page.evaluate(
            "t => { document.querySelector('.lf-threads').scrollTop = t; }", top
        )
        rendered(page)
        buried = page.evaluate(BURIED_TITLE)
        if buried and 3 <= buried["covered"] <= 10:
            break
        buried = None
    assert buried, "no closed title ended up part-way past the list's top edge"

    box = buried["box"]
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(page.locator(f'.lf-thread[data-id="{buried["id"]}"][open]')).to_have_count(1)
    # Longer than any landing this could animate, so a cancelled smooth scroll reads as
    # a stationary title rather than one still on its way.
    page.wait_for_timeout(600)
    rendered(page)

    assert page.evaluate(COVERED_TOP) is None, (
        f"the press opened the thread but left its title past the list's top edge: "
        f"{page.evaluate(COVERED_TOP)}"
    )
    title = page.locator(f'.lf-thread[data-id="{buried["id"]}"] > .lf-thread-summary')
    after = title.evaluate("el => el.getBoundingClientRect().top")
    assert after >= box["y"], (
        f"the hold carried the pressed title up from {box['y']:.1f}px to {after:.1f}px "
        f"instead of holding it where the landing put it"
    )


def test_leaving_a_long_threads_reply_scrolled_out_of_view_lands_it(browser, serve):
    """Escape out of the reply of a thread taller than the list, once the user has
    scrolled the list past all of it, lands the thread's latest turn. Only a thread
    already shown stands around the box; this one left focus on a title nothing
    showed."""
    url = serve(PANEL_PAGE)
    # Closed threads are short, so it takes a run of them to fill the list above it.
    root = seed_panel_threads(serve.page_dir, 30, long_index=29)[29]
    page = open_page(browser, url)
    open_threads_list(page, 1200, 900)
    card = reply_by_keyboard(page, root)
    page.locator(".lf-threads").evaluate("list => { list.scrollTop = 0; }")
    scroll_settled(page, ".lf-threads")
    assert card.evaluate(
        "card => card.getBoundingClientRect().top"
        " >= card.closest('.lf-threads').getBoundingClientRect().bottom"
    ), "the list still shows the thread, so this proves nothing"
    page.keyboard.press("Escape")
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    rendered(page)
    scroll_settled(page, ".lf-threads")
    landed = card.locator(".lf-msg").last.evaluate(IN_LANDING_BAND)
    assert landed["inside"], f"the thread was left out of the list's band: {landed}"


def test_walking_the_list_lands_each_thread_on_its_latest_message(browser, serve):
    """`t` and `T` land each thread on its latest message, as a direct arrival does.
    A thread taller than the list landed its title, first at the list's foot with none
    of the thread under it and then at the top with the opening turn, so a user walking
    back to a conversation scrolled to reach its newest turn."""
    url = serve(PANEL_PAGE)
    roots = seed_panel_threads(serve.page_dir, 8, long_index=3)
    page = open_page(browser, url)
    open_threads_list(page, 800, 520)
    # Focus given to the list stands on the first thread, which it shows open.
    page.locator(".lf-threads").focus()
    expect(
        page.locator(f'.lf-thread[data-id="{roots[0]}"] > .lf-thread-summary')
    ).to_be_focused()

    def walk(key, root):
        page.keyboard.press(key)
        thread = page.locator(f'.lf-thread[data-id="{root}"]')
        expect(thread.locator(":scope > .lf-thread-summary")).to_be_focused()
        rendered(page)
        scroll_settled(page, ".lf-threads")
        return {
            "title": thread.locator(":scope > .lf-thread-summary").evaluate(
                IN_LANDING_BAND
            ),
            "latest": thread.locator(".lf-msg").last.evaluate(IN_LANDING_BAND),
        }

    forward = {root: walk("t", root) for root in roots[1:7]}
    back = [walk("Shift+t", root) for root in (roots[5], roots[4], roots[3])][-1]

    assert all(landed["latest"]["inside"] for landed in forward.values()), forward
    assert back["latest"]["inside"], back
    assert not forward[roots[3]]["title"]["inside"], (
        f"the long thread landed at its title, not its latest message: {forward}"
    )


def test_firefox_paints_the_author_and_words_in_the_same_send_flash(
    firefox_browser, serve
):
    """A natural send fades its sticky author and words together in actual frames.

    Pausing the animation or repeatedly reading styles invalidates Firefox's paint
    and conceals a stale inherited background. Native screencast frames observe its
    ordinary compositor path, including the receipt repaint, without those reads.
    """
    page, _box, send, _after, _reply = pressed_send_surface(
        firefox_browser, serve, "card"
    )
    page.emulate_media(reduced_motion="no-preference")
    page.evaluate(
        """() => {
          window.__sendFlash = new Promise((resolve, reject) => {
            const root = document.querySelector('.lf-margin-preview');
            const observer = new MutationObserver(() => {
              const message = [...root.querySelectorAll('.lf-msg')].find(node =>
                node.textContent.includes('Sent from the box.'));
              if (!message) return;
              observer.disconnect();
              const cue = message.getAnimations()[0];
              if (!cue) {
                reject(new Error('the sent message has no arrival cue'));
                return;
              }
              cue.finished.then(() => {
                const head = message.querySelector('.lf-msg-head').getBoundingClientRect();
                const body = message.querySelector('.lf-msg-body').getBoundingClientRect();
                const x = head.left + head.width * 0.7;
                resolve({head: [x, head.top + 3], body: [x, body.bottom - 3]});
              }, reject);
            });
            observer.observe(root, {subtree: true, childList: true});
          });
        }"""
    )
    frames = []
    with page.screencast.start(
        on_frame=lambda frame: frames.append(frame),
        quality=100,
        size=page.viewport_size,
    ):
        send.click()
        points = page.evaluate("() => window.__sendFlash")
    readings = []
    for frame in frames:
        pixels = Image.open(io.BytesIO(frame["data"])).convert("RGB")
        colours = {
            name: pixels.getpixel(tuple(round(coordinate) for coordinate in point))
            for name, point in points.items()
        }
        readings.append(colours)
    # The light card fades from yellow (#fff8c5) to paper. Require an actual
    # sequence of intermediate colours: a discrete jump, or the constant .5
    # pending opacity blending yellow with paper, must not pass as a fade.
    fading = [
        reading
        for reading in readings
        if reading["body"][0] > 245 and 205 < reading["body"][2] < 240
    ]
    assert fading, readings
    blues = {reading["body"][2] for reading in fading}
    assert len(blues) >= 3 and max(blues) - min(blues) >= 12, fading
    assert all(
        max(abs(a - b) for a, b in zip(reading["head"], reading["body"], strict=True))
        <= 3  # Native JPEG rounding of otherwise uniform ground.
        for reading in fading
    ), fading


def test_agent_titles_update_without_losing_the_users_draft(browser, serve):
    url = serve(PANEL_PAGE)
    opening = "I was wondering which space would be easier for everyone to find."
    root = panel_comment(serve.page_dir, opening, {"section": "h-how"})
    other = panel_comment(serve.page_dir, "Keep the filter rows compact.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    topic = thread.locator(".lf-thread-topic")
    expect(topic).to_have_text("Generating title")
    paint = """element => {
      const style = getComputedStyle(element);
      return [style.animationName, style.backgroundClip, style.webkitTextFillColor];
    }"""
    sweep, clip, fill = topic.evaluate(paint)
    assert (sweep, clip, fill) == ("lf-sheen", "text", "rgba(0, 0, 0, 0)")
    assert topic.evaluate("el => getComputedStyle(el).backgroundImage") != "none"
    # Reduced motion paints ordinary text instead of an animated clipped gradient.
    page.emulate_media(reduced_motion="reduce")
    expect(topic).not_to_have_css("background-clip", "text")
    assert topic.evaluate(paint)[2] != "rgba(0, 0, 0, 0)"
    page.emulate_media(reduced_motion="no-preference")
    focus_panel_thread(thread)
    editor = thread.locator("leaf-text")
    write(editor, "Keep this unfinished reply")
    for title in ("Workshop venue", "Terrace accessibility"):
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "edit",
                str(serve.page_dir),
                root,
                "--title",
                title,
            ],
        )
        assert result.exit_code == 0, result.output
        told(page)
        expect(thread.locator(".lf-thread-topic")).to_have_text(title)
        expect(topic).not_to_have_attribute("data-lf-pending-title", "")
        expect(editor).to_have_js_property("value", "Keep this unfinished reply")
        expect(thread.get_by_text(opening, exact=True)).to_be_visible()
    find = page.get_by_role("searchbox", name="Find in threads")
    find.fill("Terrace accessibility")
    expect(page.locator(f'.lf-threads > .lf-thread[data-id="{other}"]')).to_be_hidden()
    expect(thread).to_be_visible()
    find.fill("")
    expect(page.locator(f'.lf-threads > .lf-thread[data-id="{other}"]')).to_be_visible()
    page.reload()
    expect(
        page.locator(f'.lf-threads > .lf-thread[data-id="{root}"] .lf-thread-topic')
    ).to_have_text("Terrace accessibility")


def test_the_user_rewrites_their_own_message_where_it_stands(browser, serve):
    """A double click, or ↑ from the thread's empty reply box, opens the user's own
    words in place. Enter sends the rewrite; Escape and Cancel leave the message as it
    was and discard the words, so one Escape undoes the ↑ (the user's decision,
    2026-10-06). Words a rewrite still holds when the page goes, as on a reload, wait
    for the next opening, which Resume writing reaches.

    The rewrite draws on the message in the gesture, labelled edited, and reaches the
    log as one `edit` naming the message. The agent's words offer no rewrite, and the
    same message in the page's seat stays as it reads while the panel edits it.
    """
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
    append_carried_log_record(
        d,
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
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-threads-toggle").click()
    thread = page.locator(f'.lf-thread:has(.lf-msg[data-mid="{mine["id"]}"])')
    message = thread.locator(f'.lf-msg[data-mid="{mine["id"]}"]')
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the north bracket.")
    expect(thread.locator(".lf-msg.agent .lf-msg-edit")).to_have_count(0)

    message.locator(".lf-msg-text").dblclick()
    editor = message.locator(".lf-msg-editor leaf-text")
    expect(editor).to_be_focused()
    seat = page.locator(f'#cd-q .lf-msg[data-event="{mine["id"]}"]')
    expect(seat.locator(".lf-msg-text")).to_have_text("Fit the north bracket.")
    expect(seat.locator(".lf-msg-editor")).to_have_count(0)
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Fit the south bracket.")
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the south bracket.")
    expect(message.locator(".lf-edited")).to_have_text("edited")
    round_trip(page)
    edits = [e for e in events_model.read_events(d) if e["kind"] == "edit"]
    assert [(e["author"], e["message"], e["text"]) for e in edits] == [
        ("user", mine["id"], "Fit the south bracket.")
    ]

    reply = thread.locator(".lf-thread-reply leaf-text")
    reply.focus()
    page.keyboard.press("ArrowUp")
    expect(editor).to_be_focused()
    page.keyboard.type(" Or not.")
    page.keyboard.press("Escape")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the south bracket.")
    expect(message.locator(".lf-msg-kept")).to_have_count(0)
    # Escape steps back up one rung, to the reply box ↑ came from.
    expect(reply).to_be_focused()
    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_have_js_property("value", "Fit the south bracket.")
    page.keyboard.type(" Or the east.")
    # Words a rewrite holds when the page goes wait for its next opening.
    page.reload()
    wait_until_ready(page)
    if not message.is_visible():
        page.locator(".lf-threads-toggle").click()
    expect(message.locator(".lf-msg-kept")).to_have_text("unsaved edit")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "Fit the south bracket. Or the east.")
    message.get_by_role("button", name="Cancel").click()
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(message.locator(".lf-msg-kept")).to_have_count(0)
    round_trip(page)
    assert len([e for e in events_model.read_events(d) if e["kind"] == "edit"]) == 1


def test_a_rewrite_never_replaces_words_it_did_not_see(browser, serve):
    """Another tab holding a message's old words behind its news notice opened a rewrite
    on them, and its save silently took the place of the rewrite the first tab had made.
    A rewrite opened before the words changed is refused, its words kept; opened again,
    it shows the other's words on the message and is written over them."""
    url = serve(THREAD_DIFF_PAGE)
    mine = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "rewritten",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": "cd-q"},
        },
    )
    context = browser.new_context()
    tabs = []
    for _ in range(2):
        tab = open_page(browser, url, context=context)
        resized(tab, 1200, 900)
        # The panel's state is the user's, which the first tab already opened.
        if tab.locator(".lf-thread-panel").is_hidden():
            tab.locator(".lf-threads-toggle").click()
        tabs.append(tab)
    a, b = tabs
    in_a, in_b = (
        tab.locator(f'.lf-thread .lf-msg[data-mid="{mine["id"]}"]').first
        for tab in tabs
    )
    expect(in_a).to_be_visible()
    expect(in_b).to_be_visible()
    # B opens a rewrite before A's lands.
    in_b.locator(".lf-msg-text").dblclick()
    expect(in_b.locator(".lf-msg-editor leaf-text")).to_be_focused()
    a.bring_to_front()
    in_a.locator(".lf-msg-text").dblclick()
    a.keyboard.press("ControlOrMeta+a")
    a.keyboard.type("Saved in A.")
    a.keyboard.press("Enter")
    round_trip(a)
    b.bring_to_front()
    in_b.locator(".lf-msg-editor leaf-text").focus()
    b.keyboard.press("ControlOrMeta+a")
    b.keyboard.type("Saved in B.")
    b.keyboard.press("Enter")
    round_trip(b)
    consume_browser_errors(b, {"code": "failed-load", "status": 400})
    # Refused, B's words wait as its rewrite.
    expect(in_b.locator(".lf-msg-editor")).to_have_count(0)
    expect(in_b.locator(".lf-msg-kept")).to_have_text("unsaved edit")
    told(b)
    edits = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "edit"]
    assert [e["text"] for e in edits] == ["Saved in A."]
    # Opened again, the rewrite shows A's words on the message and is written over them.
    in_b.locator(".lf-msg-text").dblclick()
    editor = in_b.locator(".lf-msg-editor leaf-text")
    expect(editor).to_have_js_property("value", "Saved in B.")
    expect(in_b.locator(".lf-edited")).to_have_attribute(
        "title", re.compile("Before, it said: “Fit the north bracket.”")
    )
    b.keyboard.press("Enter")
    round_trip(b)
    edits = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "edit"]
    assert [(e["text"], e["base"]) for e in edits] == [
        ("Saved in A.", mine["id"]),
        ("Saved in B.", edits[0]["id"]),
    ]


def test_a_region_capture_keeps_scrolled_shadow_pixels_and_its_comment_anchor(
    browser, serve
):
    page = capture_page(browser, serve)
    target = page.locator("#capture-target").bounding_box()
    left, top = int(target["x"]) + 10, int(target["y"]) + 10
    surface = open_capture_area(page)
    page.mouse.move(left, top)
    page.mouse.down()
    page.mouse.move(left + 360, top + 170, steps=5)
    page.mouse.up()
    selection = surface.locator(".lf-region-selection")
    expect(selection).to_be_visible()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Shift+ArrowDown")
    selected = selection.bounding_box()
    assert selected["x"] == pytest.approx(left + 10)
    assert selected["y"] == pytest.approx(top)
    assert selected["width"] == pytest.approx(360)
    assert selected["height"] == pytest.approx(180)

    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.keyboard.press("Enter")
    expect(surface).to_be_hidden()
    attachment = page.locator(".lf-composer-media-item img")
    expect(attachment).to_be_visible()
    media_url = attachment.get_attribute("src")
    pixels = (serve.page_dir / media_url.lstrip("/")).read_bytes()
    image = Image.open(io.BytesIO(pixels)).convert("RGB")
    assert image.size == (720, 360)
    assert image.getpixel((40, 80)) == (30, 80, 240)
    assert image.getpixel((440, 280)) == (10, 150, 30)
    field = page.locator(".lf-fab-bar leaf-text")
    expect(field).to_be_focused()
    write(field, "Inspect this captured diagram.")
    with sending(page, "the anchored screenshot comment"):
        field.press("ControlOrMeta+Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["kind"] == "comment"
    assert sent["anchor"]["section"] == "capture-target"
    assert media_url in sent["text"]
    assert "Inspect this captured diagram." in sent["text"]
    page.reload()
    wait_until_ready(page)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
    thread.locator(".lf-thread-summary").click()
    expect(thread.locator(".lf-message-media img")).to_have_attribute("src", media_url)
    assert (serve.page_dir / media_url.lstrip("/")).read_bytes() == pixels


def test_a_region_capture_draws_live_samples_and_survives_removed_links(browser, serve):
    """The parent cannot read a sample's opaque frame, so a capture without the child's
    own image showed a placeholder box where the user saw the practice page. An image
    SnapDOM cannot read attaches the capture anyway, with a notice: SnapDOM reads a
    margin beyond the crop and cannot say whether the image fell inside it. A capture
    also leaves SnapDOM watching mutations, and a removed link's subtree once threw from
    that observer as an uncaught page error."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, device_scale_factor=2
    )
    page = open_page(browser, serve(CAPTURE_SAMPLE_PAGE), context=context)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    warnings = []
    page.on("console", lambda message: warnings.append(message.text))
    page.evaluate("document.querySelector('#capture-sample').ready")
    # Another origin without CORS: visible to the reader, unreadable to SnapDOM.
    page.evaluate("""() => new Promise(resolve => {
        const image = document.createElement('img');
        image.src = new URL('icon.svg', location.href).href
            .replace('127.0.0.1', 'localhost');
        image.onload = image.onerror = resolve;
        document.querySelector('#capture-sample').before(image);
    })""")
    sample = page.locator("#capture-sample").bounding_box()
    frame = page.locator("#capture-sample iframe").bounding_box()
    surface = open_capture_area(page)
    left, top = int(sample["x"]) + 1, int(sample["y"]) + 1
    page.mouse.move(left, top)
    page.mouse.down()
    page.mouse.move(
        int(frame["x"] + frame["width"]) - 1, int(frame["y"]) + 260, steps=5
    )
    page.mouse.up()
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.keyboard.press("Enter")
    expect(surface).to_be_hidden()
    media_url = page.locator(".lf-composer-media-item img").get_attribute("src")
    image = Image.open(
        io.BytesIO((serve.page_dir / media_url.lstrip("/")).read_bytes())
    ).convert("RGB")
    paint = page.locator("#capture-sample iframe").content_frame.locator("#child-paint")
    inside = paint.bounding_box()
    at = (round((inside["x"] + 20 - left) * 2), round((inside["y"] + 20 - top) * 2))
    assert image.getpixel(at) == (200, 40, 40)
    assert not [text for text in warnings if "cross-origin iframe" in text]
    expect(page.locator(".lf-status-notice")).to_contain_text(
        "An image near this area could not be drawn"
    )
    consume_browser_errors(page, "localhost", "ERR_FAILED")

    page.evaluate("""() => new Promise(resolve => {
        const link = document.createElement('a');
        link.href = 'http://127.0.0.1:9/elsewhere';
        const label = link.appendChild(document.createElement('span'));
        document.querySelector('main').append(link);
        setTimeout(() => {
            label.setAttribute('data-moved', '');
            link.remove();
            setTimeout(resolve, 50);
        });
    })""")
    assert errors == []


def test_capture_adjustment_leaves_the_preexisting_editor_and_draft_intact(
    browser, serve
):
    page = capture_page(browser, serve)
    root = panel_comment(
        serve.page_dir, "Review this passage.", {"section": "capture-target"}, "agent"
    )
    page.reload()
    wait_until_ready(page)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    thread.locator(".lf-thread-summary").click()
    field = thread.locator("leaf-text")
    write(field, "Keep these draft words.")
    field.press("Home")
    caret = field.evaluate("box => box.selectionStart")
    surface = open_capture_area(page)
    selected = surface.locator(".lf-region-selection")
    before = selected.bounding_box()
    page.keyboard.press("ArrowRight")
    assert selected.bounding_box()["x"] == pytest.approx(before["x"] + 10)
    expect(field).to_have_js_property("value", "Keep these draft words.")
    assert field.evaluate("box => box.selectionStart") == caret

    # Returning to an existing editor ends selection before its keys edit the draft.
    field.click()
    expect(surface).to_be_hidden()
    expect(field).to_be_focused()
    field.press("End")
    field.press("ArrowLeft")
    assert (
        field.evaluate("box => box.selectionStart")
        == len("Keep these draft words.") - 1
    )
    field.press("ArrowRight")
    with sending(page, "the existing draft after leaving capture"):
        field.press("Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["kind"] == "reply"
    assert sent["parent"] == root
    assert sent["text"] == "Keep these draft words."
    expect(field).to_have_js_property("value", "")
    draft = "Still drafting."
    write(field, draft)
    expect(field).to_have_js_property("value", draft)

    surface = open_capture_area(page)
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.get_by_role("button", name="Attach capture", exact=True).click()
    expect(surface).to_be_hidden()
    expect(page.locator(".lf-composer-media-item img")).to_be_visible()
    expect(field).to_have_js_property("value", draft)
