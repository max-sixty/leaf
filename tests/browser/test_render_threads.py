"Comment-panel ordering, narrowing, and thread-motion tests."

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    THREAD_DIFF_PAGE,
    panel_comment,
)
from render_harness import (
    RELEASE_FOCUS,
    open_page,
    panel_field,
    panel_settled,
    resized,
    round_trip,
    sending,
    told,
    write,
)

from browser.threads import (
    IN_LANDING_BAND,
    append_agent_reply,
    claim_for_codex,
    open_panel_thread,
    seed_panel_threads,
    stream_reply,
)
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered, wait_until_ready
from leaf_dev.browser import PANEL_THREAD

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.watch_shifts
def test_a_reply_sent_while_the_agent_streams_moves_nothing_when_accepted(
    browser, serve, request
):
    """The user's message joins the thread above the reply still streaming, where the
    log will take that reply's answer, so the log accepting it moves nothing, and the
    stream's growth in the same readings is its arrival, not an edit.

    A panel drawing the user's pending message below the streaming reply would see the
    accepted reading, whose live reply stands after every logged message, move the
    reply below it.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Record the release", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "First words")

    page = open_page(browser, url)
    thread = open_panel_thread(page, root)
    streamed = thread.locator(".lf-msg[data-lf-author=agent]")
    expect(streamed.locator(".lf-msg-text")).to_have_text("First words")
    write(panel_field(page), "And note the date")
    # The shift watch holds the acceptance to moving nothing; the order is where the
    # send drew it.
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    told(page)
    messages = thread.locator(".lf-msg")
    expect(messages).to_have_count(3)
    expect(messages.nth(1)).to_contain_text("And note the date")
    expect(messages.nth(2)).to_contain_text("First words")

    page.evaluate(RELEASE_FOCUS)
    stream_reply(serve.page_dir, root, "First words and more of them")
    told(page)
    expect(streamed.locator(".lf-msg-text")).to_have_text(
        "First words and more of them"
    )
    expect(page.locator(".lf-fp-head .lf-thread-news:visible")).to_have_count(0)


# Where a panel thread's message stands: its offset within the view, the view's scroll,
# and the view's and the message's tops in the window.
MESSAGE_PLACE = """m => {
  const view = m.closest('.lf-fp-view');
  const top = m.getBoundingClientRect().top, viewTop = view.getBoundingClientRect().top;
  return {offset: top - viewTop, scroll: view.scrollTop, view_top: viewTop, top};
}"""


@pytest.mark.watch_shifts
@pytest.mark.parametrize("reply_size", ["short", "tall"])
def test_an_idle_open_panel_thread_shows_appended_replies(browser, serve, reply_size):
    """An append to a thread open in the panel, with no reply being written, shows at
    once below the messages the user reads, which keep their place.

    Even an answer taller than the view must leave the previous reading in place."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep the discussion here.")
    page = open_page(browser, url)
    thread = open_panel_thread(page, root)
    page.evaluate(RELEASE_FOCUS)
    message = thread.locator(".lf-msg").first
    rendered(page)
    before = message.evaluate(MESSAGE_PLACE)
    words = "The answer arrived without another click."
    if reply_size == "tall":
        words = "\n\n".join([words] * 30)
    reply = append_agent_reply(serve.page_dir, root, words)
    told(page)
    expect(thread.locator(f'.lf-msg[data-lf-event="{reply["id"]}"]')).to_be_visible()
    expect(page.locator(".lf-fp-head .lf-thread-news:visible")).to_have_count(0)
    rendered(page)
    # The view grows to hold the answer, the message keeping its place within it. The
    # growth carries the message up from where it stood on screen to that place
    # (dom/box-motion.js), so the place is read where the panel's motion ends.
    panel_settled(page, view="thread")
    after = message.evaluate(MESSAGE_PLACE)
    # One comparison of the whole reading, so a failure shows whether the view
    # scrolled, moved on screen, or the message moved within it.
    assert after["offset"] == pytest.approx(before["offset"], abs=0.5) and (
        after["scroll"] == before["scroll"]
    ), {"before": before, "after": after}


def test_walking_the_threads_lands_each_on_its_latest_message(browser, serve):
    """`t` and `T` open each thread in the panel on its latest message, as a direct
    arrival does, so a user walking back to a conversation taller than the view
    reads its newest turn without scrolling to it."""
    url = serve(PANEL_PAGE)
    roots = seed_panel_threads(serve.page_dir, 8, long_index=3)
    page = open_page(browser, url)
    resized(page, 800, 520)
    page.evaluate(RELEASE_FOCUS)

    def walk(key, root):
        page.keyboard.press(key)
        view = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
        expect(view).to_be_focused()
        panel_settled(page, view="thread")
        rendered(page)
        return view.locator(".lf-msg").last.evaluate(IN_LANDING_BAND)

    forward = {root: walk("t", root) for root in roots[:7]}
    back = [walk("Shift+t", root) for root in (roots[5], roots[4], roots[3])][-1]

    assert all(landed["inside"] for landed in forward.values()), forward
    assert back["inside"], back
    assert page.locator(f'{PANEL_THREAD}[data-lf-thread="{roots[3]}"]').evaluate(
        "view => view.scrollHeight > view.clientHeight"
    ), "the long thread fits its view, so landing its latest message proves nothing"


def test_agent_titles_update_without_losing_the_users_draft(browser, serve):
    url = serve(PANEL_PAGE)
    opening = "I was wondering which space would be easier for everyone to find."
    root = panel_comment(serve.page_dir, opening, {"section": "h-how"})
    other = panel_comment(serve.page_dir, "Keep the filter rows compact.")
    page = open_page(browser, url)
    thread = open_panel_thread(page, root)
    title = page.locator(".lf-fp-head .lf-fp-title")
    # Untitled, the view's head reads Untitled rather than repeat the opening message
    # right under it.
    expect(title).to_have_text("Untitled")
    editor = panel_field(page)
    write(editor, "Keep this unfinished reply")
    for name in ("Workshop venue", "Terrace accessibility"):
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "edit",
                str(serve.page_dir),
                root,
                "--title",
                name,
            ],
        )
        assert result.exit_code == 0, result.output
        told(page)
        expect(title).to_have_text(name)
        expect(editor).to_have_js_property("value", "Keep this unfinished reply")
        expect(thread.get_by_text(opening, exact=True)).to_be_visible()
    # Threads finds the thread by the title the agent gave it.
    page.locator(".lf-fp-back").click()
    panel_settled(page, view="threads")
    page.get_by_role("button", name="Find a thread or message").click()
    page.locator("input.lf-fp-search").fill("Terrace accessibility")
    expect(page.locator(f'.lf-fp-thread[data-lf-key="{other}"]')).to_have_count(0)
    expect(page.locator(f'.lf-fp-thread[data-lf-key="{root}"]')).to_be_visible()
    page.locator("input.lf-fp-search").fill("")
    expect(page.locator(f'.lf-fp-thread[data-lf-key="{other}"]')).to_be_visible()
    page.reload()
    wait_until_ready(page)
    open_panel_thread(page, root)
    expect(page.locator(".lf-fp-head .lf-fp-title")).to_have_text(
        "Terrace accessibility"
    )


def test_the_user_rewrites_their_own_message_where_it_stands(browser, serve):
    """A double click, or ↑ from the thread's empty reply box, opens the user's own
    words in place. Enter sends the rewrite; Escape and Cancel leave the message as it
    was and discard the words, so one Escape undoes the ↑ (the user's decision).
    Words a rewrite still holds when the page goes wait for the next opening, which
    Resume writing reaches, on a visit that isn't a return to the entry (a reload's is
    in tests/browser/navigation/test_arrival_record.py).

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
    thread = open_panel_thread(page, mine["id"])
    message = thread.locator(f'.lf-msg[data-lf-message="{mine["id"]}"]')
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the north bracket.")
    expect(thread.locator(".lf-msg[data-lf-author=agent] .lf-msg-edit")).to_have_count(
        0
    )

    message.locator(".lf-msg-text").dblclick()
    editor = message.locator(".lf-msg-editor leaf-text")
    expect(editor).to_be_focused()
    seat = page.locator(f'#cd-q .lf-msg[data-lf-event="{mine["id"]}"]')
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

    reply = panel_field(page)
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
    page.goto(page.url)
    wait_until_ready(page)
    open_panel_thread(page, mine["id"])
    expect(message.locator(".lf-msg-kept")).to_have_text("unsaved edit")
    # The address names the thread, so the arrival opens it standing on its view; with
    # the caret in its reply, Escape stands on the thread, which stays open in the panel.
    panel_field(page).focus()
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "Fit the south bracket. Or the east.")
    message.get_by_role("button", name="Discard").click()
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(message.locator(".lf-msg-kept")).to_have_count(0)
    round_trip(page)
    assert len([e for e in events_model.read_events(d) if e["kind"] == "edit"]) == 1
