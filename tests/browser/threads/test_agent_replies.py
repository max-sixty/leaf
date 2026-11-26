"""How an agent's replies draw in a thread: streaming into a card, completing as a
durable answer, the working message while the agent works, what an answer's head says it
leaves, and the widgets its markup carries."""

import json
import re

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    append_command,
    response_reference,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    SEATED_OBLIGATION_PAGE,
    THREAD_DIFF_PAGE,
    panel_comment,
)
from render_harness import (
    expect_on_me,
    expect_preview_words,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    sending,
    stamp_page,
    told,
    without_end_room,
    write,
)

from browser.threads import (
    PANEL_NEWS,
    PANEL_REPLY,
    SEAT_FILLER,
    STREAM_ATTEMPT,
    append_user_reply,
    claim_for_codex,
    open_panel_thread,
    stream_reply,
    thread_row,
)
from leaf.agents import thread as thread_model
from leaf.commands import cli as cli_model
from leaf.commands import tasks as tasks_model
from leaf.log import event_log as events_model
from leaf.log import interaction_log as interaction_model
from leaf.records import transaction as transaction_model
from leaf.source.render_checks import rendered
from leaf_dev.browser import open_on_me

pytestmark = pytest.mark.shifts_unsurveyed


def card_of(root):
    """The margin card reading the thread `root`."""
    return f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'


def open_margin_card(page, section):
    """Open the margin card of the thread on `section`, by its marker."""
    page.locator(f'[data-lf-margin-for="{section}"] .lf-margin-marker').click()
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_visible()


@pytest.mark.parametrize("section", [None, "title"], ids=["page", "title"])
def test_a_plain_agent_question_can_be_opened_and_answered(browser, serve, section):
    """A plain question works both on the whole page and on its title."""
    url = serve(
        leaf_page(
            "Rehearsal report",
            '<h1 id="title">Rehearsal report</h1>'
            '<p id="result">The backfill copied 310 million rows without errors.</p>',
        )
    )
    question = "Which meeting should the invitation be for?"
    opened = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "create",
            str(serve.page_dir),
            "--title",
            "Meeting details",
            "--text",
            question,
            *(["--section", section] if section else []),
        ],
    )
    assert opened.exit_code == 0, opened.output
    root = json.loads(opened.output)
    page = open_page(browser, url)
    if section:
        assert root["anchor"]["section"] == section
        open_margin_card(page, section)
        card = page.locator(card_of(root["id"]))
        reply = card.locator(".lf-thread-reply leaf-text")
    else:
        assert "anchor" not in root
        expect(page.locator('[data-lf-margin-for="title"]')).to_have_count(0)
        card = open_panel_thread(page, root["id"])
        reply = page.locator(PANEL_REPLY)
    expect(card.get_by_text(question, exact=True)).to_be_visible()
    write(reply, "Thursday's review")
    expect(reply).to_have_js_property("value", "Thursday's review")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    page.keyboard.press("Shift+t")
    expect(card.get_by_text(question, exact=True)).to_be_visible()
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Thursday's review")
    with sending(page, "the meeting answer"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(card.get_by_text("Thursday's review", exact=True)).to_be_visible()
    answer = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply" and event["author"] == "user"
    )
    assert answer["parent"] == root["id"]


@pytest.mark.parametrize("anchor", ["page", "title", "removed"])
def test_a_message_obligation_opens_its_question_and_accepts_an_answer(
    browser, serve, anchor
):
    """On Me reaches the exact question, even when its thread has lost its passage."""
    source = leaf_page(
        "Rehearsal report",
        '<h1 id="title">Rehearsal report</h1>'
        '<p id="result">The backfill copied 310 million rows without errors.</p>',
    )
    url = serve(source)
    runner = CliRunner()
    opened = runner.invoke(
        cli_model.cli,
        [
            "thread",
            "create",
            str(serve.page_dir),
            "--title",
            "Rehearsal report",
            "--text",
            "The rehearsal is complete.",
            *(["--section", "title"] if anchor != "page" else []),
        ],
    )
    assert opened.exit_code == 0, opened.output
    root = json.loads(opened.output)
    question = "Which production maintenance window did you book?"
    asked = runner.invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(serve.page_dir),
            root["id"],
            "--obligation",
            "--text",
            question,
        ],
    )
    assert asked.exit_code == 0, asked.output
    message = json.loads(asked.output)
    if anchor == "removed":
        stamp_page(
            serve.page_dir,
            source.replace('<h1 id="title">Rehearsal report</h1>', ""),
            "Remove the old heading",
        )
    page = open_page(browser, url)
    mark = page.locator(".lf-fp-leaf")
    expect_on_me(page, 1)
    mark.click()
    row = page.locator('.lf-fp-on-item[data-lf-list="you"]')
    expect(row).to_contain_text(question)
    expect(row.get_by_role("button", name="Reply", exact=True)).to_be_visible()
    row.get_by_role("button", name="Show", exact=True).click()
    shown = page.locator(
        f'.lf-page-thread:visible .lf-msg[data-lf-event="{message["id"]}"]'
    )
    expect(shown).to_be_visible()
    expect(shown).to_contain_text("Waiting on me")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    page.keyboard.press("m")
    expect(shown).to_be_visible()
    page.keyboard.press("c")
    reply = page.locator("leaf-text:focus")
    expect(reply).to_be_focused()
    write(reply, "02:00–02:40 UTC on Thursday")
    with sending(page, "the maintenance window"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect_on_me(page, 0)
    assert any(
        event["kind"] == "reply"
        and event["author"] == "user"
        and event["text"] == "02:00–02:40 UTC on Thursday"
        for event in events_model.read_events(serve.page_dir)
    )


def test_a_durable_answer_retires_the_placeholder_its_attempt_reserved(
    browser, serve, request
):
    """The answer the log holds is what the panel draws, not the draft it replaced.

    A provisional reply retired only by the response address it was sent to would let
    an answer that named only the attempt it was reserved under stand beside its own
    placeholder, and the draft would be what got drawn: its stale words in place of the
    answer. A logged event naming either identity retires the draft.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Answer me here", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "Checking the deployment.")

    page = open_page(browser, url)
    open_margin_card(page, "h-how")
    drafted = page.locator(
        f'.lf-margin-preview .lf-msg[data-lf-attempt="{STREAM_ATTEMPT}"] .lf-msg-text'
    )
    expect(drafted).to_have_text("Checking the deployment.")

    # An answer that names the attempt it was reserved under and nothing else.
    reply = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "session": "codex-thread",
            "parent": root,
            "revision": 1,
            "attempt": STREAM_ATTEMPT,
            "text": "deployment verified",
        },
    )
    assert "responds" not in reply
    told(page)

    thread = page.locator(card_of(root))
    notice = thread.get_by_role("button", name="1 new", exact=True)
    expect(notice).to_be_visible()
    expect(drafted).to_have_text("Checking the deployment.")
    notice.click()
    answered = thread.locator(f'.lf-msg[data-lf-attempt="{STREAM_ATTEMPT}"]')
    expect(thread.locator(".lf-msg[data-lf-author=agent]")).to_have_count(1)
    expect(answered).to_have_attribute("data-lf-event", reply["id"])
    expect(answered.locator(".lf-msg-text")).to_have_text("deployment verified")


def test_a_durable_reply_completes_its_stream_placeholder_in_place(
    browser, serve, request
):
    """One retained message gains its durable prose and validated authored island.

    The stream placeholder exists before the final event, so its owner must not freeze
    the absence of markup at construction. The answer completes the reply the open
    thread was already streaming, so it shows as it lands. A later edit keeps that
    owner and draws the island its new words hold, in place of the one before. The
    panel's view reads it: a passage's margin card draws no reply markup, which opens
    in the panel.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Answer me here")
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "Looking at it now.")

    page = open_page(browser, url)
    expect(thread_row(page, root).locator(".lf-row-end")).to_have_text("Replying")
    thread = open_panel_thread(page, root)
    message = thread.locator(f'.lf-msg[data-lf-attempt="{STREAM_ATTEMPT}"]')
    expect(message.locator(".lf-msg-text")).to_have_text("Looking at it now.")
    expect(message.locator(".lf-msg-head .lf-msg-sending")).to_have_count(0)
    page.evaluate(
        "attempt => { window.__streamMessage = document.querySelector("
        '`.lf-fp-view .lf-msg[data-lf-attempt="${attempt}"]`); }',
        STREAM_ATTEMPT,
    )

    def ask(choice, label):
        return (
            '<lf-group id="stream-reply-ask" label="Use this answer?">\n'
            '<h3 id="stream-reply-ask-h">Use this answer?</h3>'
            f'<lf-options id="{choice}">'
            f'<lf-option id="{choice}-now">{label}</lf-option>'
            "</lf-options></lf-group>"
        )

    reply = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "The complete answer.\n\n" + ask("stream-reply-choice", "Use it now"),
        attempt=STREAM_ATTEMPT,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with transaction_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")

    told(page)
    expect(message).to_have_attribute("data-lf-event", reply["id"])
    expect(message.locator(".lf-msg-text")).to_contain_text("The complete answer.")
    expect(message.locator("#stream-reply-choice")).to_have_count(1)
    expect(page.locator(PANEL_NEWS)).to_be_hidden()

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "session": "codex-thread",
            "message": reply["id"],
            "text": "The complete edited answer.\n\n"
            + ask("stream-reply-later", "Use it later"),
        },
    )
    told(page)
    # The edit shows at once, or behind the view's notice where it would move what
    # the user reads.
    edited = page.locator(f"{PANEL_NEWS}:not([hidden])")
    expect(
        edited.or_(message.locator(".lf-msg-text", has_text="edited")).first
    ).to_be_visible()
    if edited.count():
        edited.click()
    expect(message.locator(".lf-msg-text")).to_contain_text(
        "The complete edited answer."
    )
    expect(message.locator("#stream-reply-later")).to_contain_text("Use it later")
    expect(page.locator("#stream-reply-choice")).to_have_count(0)
    assert page.evaluate(
        f"""() => window.__streamMessage === document.querySelector(
          '.lf-fp-view .lf-msg[data-lf-event="{reply["id"]}"]')"""
    ), "the durable reply was replaced after the edit"

    # Words alone draw as prose, the island gone with the HTML.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "session": "codex-thread",
            "message": reply["id"],
            "text": "Withdrawn: the plan changed.",
        },
    )
    told(page)
    if page.locator(f"{PANEL_NEWS}:not([hidden])").count():
        page.locator(PANEL_NEWS).click()
    expect(message.locator(".lf-msg-text")).to_have_text("Withdrawn: the plan changed.")
    expect(page.locator("#stream-reply-later")).to_have_count(0)


def test_a_codex_reply_streams_into_an_open_card_and_its_answer_completes_it(
    browser, serve, request
):
    """The agent's opening streams into the open card the user is reading, and the
    explicit answer completes that same message.

    The card must not draw an empty agent bubble as the turn starts, hold the opening's
    first words as an edit of it behind "1 new reply", and let the answer, written by
    `leaf thread reply` under a retry key of its own, take the bubble away and append
    itself. The provisional reply joins the thread with its first words, its words join
    it as they come, and the answer to the same input is the same message.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Record the release", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "")

    page = open_page(browser, url)
    expect(thread_row(page, root).locator(".lf-row-end")).to_have_text("Replying")
    open_margin_card(page, "h-how")
    thread = page.locator(card_of(root))
    expect(thread.locator(".lf-msg[data-lf-author=agent]")).to_have_count(0)

    stream_reply(serve.page_dir, root, "I'll")
    told(page)
    streamed = thread.locator(".lf-msg[data-lf-author=agent]")
    expect(streamed.locator(".lf-msg-text")).to_have_text("I'll")
    streamed.evaluate("node => { window.__streamMessage = node; }")
    stream_reply(serve.page_dir, root, "I'll record it on the board now.")
    told(page)
    expect(streamed.locator(".lf-msg-text")).to_have_text(
        "I'll record it on the board now."
    )
    expect(thread.locator(".lf-thread-news")).to_have_count(0)

    reply = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Recorded the release on the board.",
        attempt="leaf-response-explicit",
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    assert reply["responds"] == root
    with transaction_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    expect(streamed).to_have_count(1)
    expect(streamed).to_have_attribute("data-lf-event", reply["id"])
    expect(streamed.locator(".lf-msg-text")).to_have_text(
        "Recorded the release on the board."
    )
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    assert streamed.evaluate("node => node === window.__streamMessage"), (
        "the answer replaced the message it completes"
    )


def test_a_held_card_counts_a_streaming_reply_once_and_names_the_users_own_message(
    browser, serve, request
):
    """While the user writes in a card, its news waits, and the notice says what waits.

    A reply the card already streams is one new reply however often its words grow
    and whatever answer completes it, through every later reading while it waits, and
    a turn of the user's own from another tab is a message of theirs, not a reply.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Record the release", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "First words")

    page = open_page(browser, url)
    open_margin_card(page, "h-how")
    thread = page.locator(card_of(root))
    drawn = thread.locator(".lf-msg[data-lf-author=agent] .lf-msg-text")
    expect(drawn).to_have_text("First words")
    write(thread.locator(":scope > .lf-thread-reply leaf-text"), "Also note the date")

    notice = thread.locator(".lf-thread-news")
    for words in ("First words and more", "First words and more of them"):
        stream_reply(serve.page_dir, root, words)
        told(page)
        expect(notice).to_have_text("1 new")
        expect(drawn).to_have_text("First words")

    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Recorded the release on the board.",
        attempt="leaf-response-explicit",
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with transaction_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    expect(notice).to_have_text("1 new")
    expect(drawn).to_have_text("First words")

    # A later reading compares against the held drawing, which still stands for the
    # streaming reply the answer completed rather than an answer since reworded.
    append_user_reply(serve.page_dir, root, "Sent from my other tab")
    told(page)
    expect(notice).to_have_text("2 new")
    notice.click()
    expect(drawn).to_have_text("Recorded the release on the board.")
    expect(thread.locator(".lf-msg[data-lf-author=user]")).to_have_count(2)


def test_an_answer_completing_its_stream_with_the_same_words_keeps_progress_hidden(
    browser, serve, request
):
    """A final with the streamed words completes in place without news or bringing
    back progress while the user writes their next message."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Record the release", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Checking the board",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    stream_reply(serve.page_dir, root, "Recorded the release.")

    page = open_page(browser, url)
    open_margin_card(page, "h-how")
    thread = page.locator(card_of(root))
    expect(thread.locator(".lf-msg[data-lf-author=agent]:visible")).to_have_count(1)
    write(thread.locator(":scope > .lf-thread-reply leaf-text"), "Also note the date")

    answer = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Recorded the release.",
        attempt=STREAM_ATTEMPT,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with transaction_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    message = thread.locator(f'.lf-msg[data-lf-event="{answer["id"]}"]')
    expect(message.locator(".lf-msg-text")).to_have_text("Recorded the release.")
    expect(thread.locator(".lf-thread-working")).to_have_count(0)
    expect(thread.locator(".lf-msg[data-lf-author=agent]:visible")).to_have_count(1)
    expect(thread.locator(":scope > .lf-thread-reply leaf-text")).to_have_js_property(
        "value", "Also note the date"
    )


@pytest.mark.watch_shifts
@pytest.mark.parametrize("streamed", [False, True])
def test_an_idle_card_replaces_progress_with_the_answer(
    browser, serve, request, streamed
):
    """An idle card replaces progress with the answer as its first words arrive,
    streamed or durable, and keeps everything above the progress in place."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Record the release", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Checking the board",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )

    page = open_page(browser, url)
    open_margin_card(page, "h-how")
    thread = page.locator(card_of(root))
    expect(thread.locator(".lf-thread-working")).to_contain_text("Checking the board")
    if streamed:
        stream_reply(serve.page_dir, root, "Recording the release now.")
        told(page)
        expect(thread.locator(".lf-msg[data-lf-author=agent]:visible")).to_have_count(1)
    opening = thread.locator(".lf-msg").first
    resting = opening.bounding_box()

    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Recorded the release on the board.",
        attempt=STREAM_ATTEMPT,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with transaction_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    answer = thread.locator(".lf-msg[data-lf-author=agent]:visible")
    expect(answer.locator(".lf-msg-text")).to_have_text(
        "Recorded the release on the board."
    )
    expect(thread.locator(".lf-thread-checkpoint")).to_have_count(0)
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    assert opening.bounding_box() == resting, "the answer moved what stood above it"


def test_pending_progress_is_the_threads_working_message_and_never_unread(
    browser, serve, request
):
    """While the agent works, its progress shows as one dim working message above the
    reply box, not as replies: each step replaces the last and nothing counts unread.
    The answer takes the working message's place."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Make the banner quieter", {"section": "h-how"}
    )
    claim_for_codex(serve.page_dir, request)
    codex = {"agent": "Codex", "session": "codex-thread"}
    steps = [
        thread_model.post_reply(
            serve.page_dir,
            {"responds": root},
            text,
            ephemeral=True,
            identity=codex,
        )
        for text in ("Reading the banner's styles.", "Trying a lighter weight.")
    ]
    page = open_page(browser, url)
    # The comment's line on the agent's list says the agent's last step on it, as the
    # page's status does, rather than only that it is working.
    open_on_me(page)
    panel_settled(page, view="queue")
    page.locator(".lf-fp-filters button").filter(has_text="On Codex").click()
    card = page.locator('.lf-fp-on-item[data-lf-list="agent"]')
    expect(card.locator(".lf-fp-on-line .lf-fp-running")).to_have_text(
        "Trying a lighter weight."
    )
    # Nothing counts unread.
    expect(thread_row(page, root)).not_to_have_attribute("data-lf-unread", "")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == "reply_visible"
                and entry.get("input_id") == root
                and entry["presentation_kind"] == "working_words"
                for entry in response.request.post_data_json["entries"]
            )
        )
    ):
        open_margin_card(page, "h-how")
    thread = page.locator(card_of(root))
    line = thread.locator(".lf-thread-working")
    expect(line.locator(".lf-thread-working-head b")).to_have_text("Codex")
    expect(line.locator("time")).to_have_attribute("datetime", steps[-1]["ts"])
    expect(line.locator("time")).not_to_be_empty()
    expect(line.locator(".lf-thread-working-words")).to_have_text(
        "Trying a lighter weight"
    )
    # The working line is actual agent feedback, though no step has a MessageView.
    # It uses the input's exact workflow identity, not the
    # thread parent, and carries no copy of the agent's words in diagnostics. A later
    # acknowledged gesture flushes every observation made before it.
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == "click"
                for entry in response.request.post_data_json["entries"]
            )
        )
    ):
        thread.locator(".lf-msg").first.click()
    feedback = [
        row
        for row in interaction_model.read_interactions(serve.page_dir)
        if row.get("type") == "reply_visible"
    ]
    assert any(
        row.get("input_id") == root
        and row["reply_kind"] == "work"
        and row["presentation_kind"] == "working_words"
        for row in feedback
    )
    assert any(
        row.get("input_id") == root
        and row["presentation_kind"] == "status_words"
        and row["reply_id"] == steps[-1]["id"]
        for row in feedback
    )
    assert not any(
        row["presentation_kind"] == "message_words"
        and row.get("reply_id") in {step["id"] for step in steps}
        for row in feedback
    )

    expect(line).to_have_attribute("data-lf-live", "")
    expect(line.get_by_role("button")).to_have_count(0)
    # A long step wraps as a message does, so all of it shows; in an idle open card
    # it grows the thread's foot, as an arriving reply would.
    height = line.evaluate("node => node.getBoundingClientRect().height")
    steps.append(
        thread_model.post_reply(
            serve.page_dir,
            {"responds": root},
            "Comparing the lighter weight against every banner the gallery shows, "
            "at each width the panel takes, before and after the change.",
            ephemeral=True,
            identity=codex,
        )
    )
    told(page)
    expect(line.locator(".lf-thread-working-words")).to_contain_text(
        "before and after the change"
    )
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    words = line.locator(".lf-thread-working-words")
    assert words.evaluate("node => node.scrollWidth <= node.clientWidth")
    assert line.evaluate("node => node.getBoundingClientRect().height") > height
    for step in steps:
        expect(thread.locator(f'.lf-msg[data-lf-event="{step["id"]}"]')).to_be_hidden()

    answer = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Done in v4: the banner is one weight lighter.",
        identity=codex,
    )
    told(page)
    expect(line).to_have_count(0)
    expect(thread.locator(f'.lf-msg[data-lf-event="{answer["id"]}"]')).to_be_visible()
    for step in steps:
        expect(thread.locator(f'.lf-msg[data-lf-event="{step["id"]}"]')).to_be_hidden()

    # A second session can post a step on a follow-up the first hasn't taken up; the
    # face says who wrote it and when, from the step's own message.
    append_user_reply(serve.page_dir, root, "And in the dark theme?")
    proactive = thread_model.post_reply(
        serve.page_dir,
        {"parent": root},
        "Checking the contrast in the dark theme.",
        ephemeral=True,
        identity={"agent": "Claude", "session": "claude-thread"},
    )
    told(page)
    expect(line.locator(".lf-thread-working-head b")).to_have_text("Claude")
    expect(line.locator("time")).to_have_attribute("datetime", proactive["ts"])
    expect(line.locator("time")).not_to_be_empty()


# Only "scrolls" is watched for shifts: on the short page the draft moves with no input,
# which the rule accepts where the page has no scroll to give.
@pytest.mark.parametrize(
    "room", [pytest.param("scrolls", marks=pytest.mark.watch_shifts), "short"]
)
def test_a_new_step_shows_at_once_in_the_thread_being_written_in(browser, serve, room):
    """A step's words wrap, so a new step can change the working message's height. In
    the seat's thread the user writes in, the step shows as it comes, as in a chat, and
    the draft stays where it stands while the page scrolls the step's room away above
    it ("scrolls"). A page shorter than its window ("short") has no scroll to give, so
    the step shows there too and the draft moves down by it. The thread says no news
    waits either way, since progress is no unread news."""
    source = SEATED_OBLIGATION_PAGE
    if room == "scrolls":
        source = source.replace("</lf-test-plan>", "</lf-test-plan>" + SEAT_FILLER, 1)
    url = serve(source)
    root = panel_comment(serve.page_dir, "Which job comes first?", {"section": "jobs"})
    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Reading the jobs.",
        ephemeral=True,
    )
    page = open_page(browser, url)
    if room == "short":
        without_end_room(page)
    resized(page, 390, 900)
    thread = page.locator("#jobs .lf-page-thread")
    words = thread.locator(".lf-thread-working-words")
    expect(words).to_have_text("Reading the jobs")
    editor = thread.locator("leaf-text")
    write(editor, "Start with the mounts.")
    rendered(page)
    assert page.evaluate(
        "() => document.scrollingElement.scrollHeight > innerHeight"
    ) == (room == "scrolls")
    box = editor.bounding_box()

    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Comparing the mounts, the bird bath and the camera against the frost "
        "dates, and what each one needs before it can start.",
        ephemeral=True,
    )
    told(page)
    expect(words).to_contain_text("what each one needs before it can start")
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    rendered(page)
    expect(editor).to_be_focused()
    moved = editor.bounding_box()["y"] - box["y"]
    if room == "scrolls":
        assert moved == pytest.approx(0, abs=0.5)
    else:
        assert moved > 0, "the step's growth had nowhere to go but under the draft"


# Whether a box's words stand whole inside it, to the fraction of a pixel that
# scrollWidth rounds away.
WORDS_FIT = """box => {
  const words = document.createRange();
  words.selectNodeContents(box);
  return words.getBoundingClientRect().width <= box.firstElementChild
    .getBoundingClientRect().width + 0.01;
}"""


def test_held_news_says_one_count_of_all_it_holds(browser, serve):
    """A seat's notice says one count of what waits, "1 new" and then "2 new", at the
    width it first stood at, while the user reads beside the thread. Its name is the
    count it shows, so a voice user saying it finds it, and its description says each
    fact. Saying the facts and, past its room, dropping the later ones behind a "+1"
    would read one piece of news three ways on three surfaces, and a name saying only
    the facts would say what the words shown never say."""
    url = serve(SEATED_OBLIGATION_PAGE)
    # An agent's opening message has no delivery receipt competing with the news.
    root = panel_comment(
        serve.page_dir, "Which job comes first?", {"section": "jobs"}, author="agent"
    )
    page = open_page(browser, url)
    resized(page, 390, 900)
    thread = page.locator("#jobs .lf-page-thread")
    expect(thread).to_be_visible()
    rendered(page)

    thread_model.post_reply(serve.page_dir, {"parent": root}, "The mounts come first.")
    told(page)
    notice = thread.get_by_role("button", name="1 new", exact=True)
    expect_preview_words(notice, "1 new reply")
    rendered(page)
    width = notice.bounding_box()["width"]

    append_user_reply(serve.page_dir, root, "And the bird bath?")
    told(page)
    notice = thread.get_by_role("button", name="2 new", exact=True)
    expect_preview_words(notice, "1 new reply · 1 new message")
    rendered(page)
    assert notice.bounding_box()["width"] == pytest.approx(width, abs=0.5)
    # The room "1 new" made holds "2 new" whole, figures of one width in both.
    assert notice.evaluate(WORDS_FIT), "the notice cut its count short"


def test_a_streaming_answer_hides_the_working_message_and_its_progress(
    browser, serve, request
):
    """The first words of a streamed answer end the step before them."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Record the release", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    step = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Checking the board",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    page = open_page(browser, url)
    open_margin_card(page, "h-how")
    thread = page.locator(card_of(root))
    expect(thread.locator(".lf-thread-working")).to_be_visible()

    stream_reply(serve.page_dir, root, "Recording the release now.")
    told(page)
    expect(thread.locator(".lf-thread-working")).to_have_count(0)
    streamed = thread.locator(".lf-msg[data-lf-author=agent]").last
    expect(streamed.locator(".lf-msg-text")).to_have_text("Recording the release now.")
    expect(thread.locator(f'.lf-msg[data-lf-event="{step["id"]}"]')).to_have_count(0)

    # The failure receipt, an agent message too, ends the step: neither the held
    # stream nor the receipt it gives way to brings it back.
    write(thread.locator(":scope > .lf-thread-reply leaf-text"), "Keep this draft")
    failure = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "The turn failed; please retry.",
        failure="turn_failed",
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with transaction_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    expect(streamed.locator(".lf-msg-text")).to_have_text("Recording the release now.")
    expect(thread.locator(".lf-thread-working")).to_have_count(0)
    thread.get_by_role("button", name="1 new", exact=True).click()
    expect(
        thread.locator(f'.lf-msg[data-lf-event="{failure["id"]}"] .lf-msg-failure')
    ).to_have_text("Not answered")
    expect(thread.locator(".lf-thread-working")).to_have_count(0)


def test_an_answer_says_what_it_leaves_while_that_stands(browser, serve, request):
    """An answer that asks back or promises work says so in its head, beside its time,
    for as long as the obligation is the user's or the to-do stays open, and a promise
    reads On it while its work runs, as the to-do does everywhere else."""
    url = serve(PANEL_PAGE)
    asked = panel_comment(serve.page_dir, "Which store owns it?", {"section": "h-how"})
    promised = panel_comment(serve.page_dir, "Rebuild the banner", {"section": "lede"})
    claim_for_codex(serve.page_dir, request)
    codex = {"agent": "Codex", "session": "codex-thread"}
    question = thread_model.post_reply(
        serve.page_dir,
        {"responds": asked},
        "The session store or the page store?",
        obligation=True,
        identity=codex,
    )
    promise = thread_model.post_reply(
        serve.page_dir,
        {"responds": promised},
        "Rebuilding it; it lands in v4.",
        todo="Rebuild the banner quieter",
        identity=codex,
    )
    page = open_page(browser, url)
    for root, reply, words, section in (
        (asked, question, "Waiting on me", "h-how"),
        (promised, promise, "Still to do", "lede"),
    ):
        open_margin_card(page, section)
        thread = page.locator(card_of(root))
        head = thread.locator(f'.lf-msg[data-lf-event="{reply["id"]}"] .lf-msg-head')
        expect(head.locator(".lf-msg-leaves")).to_have_text(words)

    # The promise's word opens On Codex at its to-do with the card open: the keys land
    # on the to-do's line, and a pointer opens the same card.
    word = page.locator(card_of(promised)).locator(
        f'.lf-msg[data-lf-event="{promise["id"]}"] .lf-msg-leaves'
    )
    expect(word).to_have_accessible_name("Still to do, Open in On Codex")
    item = page.locator(f".lf-fp-view .lf-fp-on-item[data-lf-key='{promise['id']}']")
    word.focus()
    page.keyboard.press("Enter")
    expect(item).to_have_attribute("data-lf-open", "")
    expect(item.locator(".lf-fp-on-line")).to_be_focused()
    page.keyboard.press("Escape")
    expect(item).not_to_have_attribute("data-lf-open", "")
    word.click()
    expect(item).to_have_attribute("data-lf-open", "")

    thread_model.post_reply(
        serve.page_dir,
        {"parent": promised, "responds": promised},
        "rebuilding the banner",
        ephemeral=True,
        identity=codex,
    )
    told(page)
    head = page.locator(
        f'.lf-margin-preview .lf-msg[data-lf-event="{promise["id"]}"] .lf-msg-head'
    )
    expect(head.locator(".lf-msg-leaves")).to_have_text("On it")

    tasks_model.cmd_end(serve.page_dir, promise["id"], "done", "Rebuilt in v4")
    told(page)
    expect(head.locator(".lf-msg-leaves")).to_have_count(0)


def test_a_card_moved_on_a_board_in_a_reply_reports_delivery_on_that_reply(
    browser, serve
):
    """A board the agent sent in a reply takes a moved card as a page board does: the
    reply carrying the board reports the saved move, and the thread stays nobody's
    turn, since the move answers no obligation and wakes nobody. The agent's next turn in
    the thread takes the move in, and the receipt leaves with it, even while that turn
    waits behind the card's notice, since a held thread draws its messages' delivery
    as it stands."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Lay the work out.")
    board = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root,
            "responds": root,
            "text": "Here is the board.\n\n"
            '<lf-board id="fb"><lf-column id="fb-todo" label="To do">'
            '<lf-card id="fb-cache" label="Cache"><strong>Cache</strong></lf-card></lf-column>'
            '<lf-column id="fb-done" label="Done"></lf-column></lf-board>',
        },
    )
    page = open_page(browser, url)
    # The unread reply is the row's mark, with no turn owed by either participant.
    status = thread_row(page, root).locator(".lf-row-end")
    expect(status).to_have_text("")
    card = open_panel_thread(page, root)
    receipt = page.locator(
        f'.lf-fp-view .lf-msg[data-lf-event="{board["id"]}"] .lf-msg-sending'
    )

    page.locator("#fb-cache .lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    with sending(page, "the card move"):
        page.keyboard.press("Enter")
    expect(page.locator("#fb-done > #fb-cache")).to_be_visible()
    expect(receipt).to_have_text(re.compile(r"^Queued for "))
    status = thread_row(page, root).locator(".lf-row-end")
    expect(status).to_have_text("")
    card = open_panel_thread(page, root)

    [moved] = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert not moved["attention"]
    assert moved not in transaction_model.unacknowledged(
        events_model.read_events(serve.page_dir), 0
    )

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root,
            "text": "Cache is done, then.",
        },
    )
    told(page)
    expect(receipt).to_have_count(0)
    news = page.locator(PANEL_NEWS).filter(has_text="1 new")
    if news.count():
        news.click()
    expect(card.locator(".lf-msg").filter(has_text="Cache is done")).to_be_visible()
    expect(page.locator("#fb-done > #fb-cache")).to_be_visible()


def test_a_harness_failure_receipt_does_not_read_as_an_answer(browser, serve):
    """A reply saying no answer is coming is marked as one, in both faces of the head.

    Nothing else in the message says it: a harness receipt is a reply event, written
    under the thread's own agent name, in the same bubble as a real answer, and its
    prose is the only other difference. Without the mark, a user skimming a thread
    would read an apology from the agent rather than a notice that their message went
    nowhere, and the page's own record of the failure — `failure` — would go unread.
    The mark belongs in the head because that is the part of a message a user takes on
    trust.
    """
    url = serve(THREAD_DIFF_PAGE)
    answered, unanswered = (
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": {"section": "cd-q"},
            },
        )
        for text in ("Widen the north bracket?", "And the south pair?")
    )
    answer = thread_model.post_reply(
        serve.page_dir,
        {"responds": answered["id"]},
        "Widened it to forty.",
    )
    thread_model.post_reply(
        serve.page_dir,
        {"responds": unanswered["id"]},
        "Checking the south pair.",
        ephemeral=True,
    )
    receipt = thread_model.post_reply(
        serve.page_dir,
        {"responds": unanswered["id"]},
        "The agent's turn ended without an answer to this message. "
        "Send it again to retry.",
        failure="turn_failed",
    )

    page = open_page(browser, url)
    resized(page, 1200, 900)
    inline = page.locator(f'#cd-q .lf-msg[data-lf-event="{receipt["id"]}"]')
    # The receipt, an agent message, ends the step before it.
    expect(page.locator("#cd-q .lf-thread-working")).to_have_count(0)
    expect(inline.locator(".lf-msg-failure")).to_have_text("Not answered")
    assert inline.get_attribute("data-lf-failure") == "turn_failed"
    # The real answer above it wears nothing, so the mark is a difference the user
    # can see rather than a decoration every agent message carries.
    real = page.locator(f'#cd-q .lf-msg[data-lf-event="{answer["id"]}"]')
    expect(real.locator(".lf-msg-failure")).to_have_count(0)

    # The server settled its turn, and the thread's `attention` is still the user's
    # move, for recovery. The task seats the thread, so the margin lists none
    # for it, and Threads names the action owed on the thread's row, whole.
    status = thread_row(page, unanswered["id"]).locator(".lf-row-end")
    expect(status).to_have_text("Send it again")
    assert status.evaluate("el => el.scrollWidth <= el.clientWidth"), (
        "the row clips its failure status"
    )
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)

    # A held resend from the thread's own card leaves its box empty while the server
    # reads it; refusal restores the draft, and the recovery still stands.
    card = page.locator(f'#cd-q .lf-page-thread[data-lf-thread="{unanswered["id"]}"]')
    draft = card.locator("leaf-text")
    write(draft, "Try the south pair again.")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        card.get_by_role("button", name="Send", exact=True).click()
    holding(page, held, 1, "the recovery resend")
    expect(draft).to_have_js_property("value", "")
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    expect(draft).to_have_js_property("value", "Try the south pair again.")
    page.unroute("**/api/event")
    rendered(page)
    # The row says so still, beside the draft the refusal gave back.
    expect(thread_row(page, unanswered["id"]).locator(".lf-row-end")).to_contain_text(
        "Send it again"
    )

    # The failed answer remains distinct from the muted clock without a chip face, in
    # the colour of a warning and Leaf's italic.
    head = page.evaluate(
        """(id) => {
          const head = document.querySelector(
            `#cd-q .lf-msg[data-lf-event="${id}"] .lf-msg-head`);
          const failure = head.querySelector(".lf-msg-failure");
          const words = getComputedStyle(failure.querySelector("[data-lf-voice]"));
          return {
            failure: words.color,
            border: getComputedStyle(failure).borderTopWidth,
            style: words.fontStyle,
            clock: getComputedStyle(head.querySelector("time")).color,
          };
        }""",
        receipt["id"],
    )
    assert head["failure"] != head["clock"]
    assert head["border"] == "0px" and head["style"] == "italic"


def test_a_bounded_log_in_an_agent_reply_follows_its_end_as_a_reading_region(
    browser, serve
):
    """A reply's markup is painted where the thread draws it, not by the page's install,
    so a log bounded at its end in a reply, left to the install, would be neither held
    at its end nor the box scrolling its lines until some later revision swept the
    page."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "What did the deploy do?")
    markup = (
        "<table><caption>Deploy checks</caption><tr><th>Check</th><th>Result</th></tr>"
        "<tr><td>Smoke test</td><td>Passed</td></tr></table>"
        '<details><summary>Deploy log</summary><div data-bound="end">'
        + "".join(
            f"<p>Line {n}: the deploy copied shard {n} to the new key format.</p>"
            for n in range(60)
        )
        + "</div></details>"
    )
    reply = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(serve.page_dir, root),
            "--title",
            "Deploy log",
            "--text",
            "Here is its log." + "\n\n" + (markup),
        ],
    )
    assert reply.exit_code == 0, reply.output
    page = open_page(browser, url)
    resized(page, 1400, 900)
    card = open_panel_thread(page, root)
    expect(card.get_by_role("cell", name="Passed", exact=True)).to_be_visible()
    disclosure = card.locator(".lf-msg-body summary").filter(has_text="Deploy log")
    disclosure.click()
    expect(card.locator(".lf-msg-body details")).to_have_attribute("open", "")
    disclosure.press("Space")
    expect(card.locator(".lf-msg-body details")).not_to_have_attribute("open", "")
    disclosure.press("Enter")
    log = card.locator(".lf-msg-body [data-lf-bound]")
    expect(log).to_be_visible()
    rendered(page)
    held = log.evaluate(
        """async log => {
          const { scrollerFor } = await window.__lfWidgetApi();
          return {
            scroller: scrollerFor(log.querySelector('p')) === log,
            atEnd: log.scrollHeight > log.clientHeight
              && log.scrollHeight - log.scrollTop - log.clientHeight <= 2,
          };
        }"""
    )
    assert held == {"scroller": True, "atEnd": True}, held


def test_canceling_a_long_stream_keeps_the_panel_reading(browser, serve, request):
    """Measuring removed content must not reset the thread's scroll: a long stream
    canceled under a reader at the thread's end leaves them at its end, with the reply
    they are writing where it stood."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep this thread here.")
    claim_for_codex(serve.page_dir, request)
    stream_reply(
        serve.page_dir,
        root,
        "\n\n".join(["A provisional answer with useful detail. " * 5] * 25),
    )
    page = open_page(browser, url)
    resized(page, 1400, 700)
    view = open_panel_thread(page, root)
    reply = page.locator(PANEL_REPLY)
    write(reply, "Half a thought")
    view.evaluate("node => node.scrollTop = node.scrollHeight")
    rendered(page)
    top = view.evaluate("node => node.scrollTop")
    reply_top = reply.bounding_box()["y"]
    assert top > 500
    with transaction_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    expect(view.locator(f'.lf-msg[data-lf-attempt="{STREAM_ATTEMPT}"]')).to_have_count(
        0
    )
    rendered(page)
    assert view.evaluate(
        "node => node.scrollHeight - node.scrollTop - node.clientHeight"
    ) == pytest.approx(0, abs=1)
    assert reply.bounding_box()["y"] == pytest.approx(reply_top, abs=1)
    expect(reply).to_have_js_property("value", "Half a thought")


# The open thread view's user messages and working message in the order they stand, each
# user message by its words.
TRANSCRIPT_ORDER = """view => [...view.querySelectorAll('.lf-msg[data-lf-author=user], .lf-thread-working')]
    .filter((node) => node.checkVisibility())
    .map((node) => node.matches('.lf-thread-working')
        ? 'working'
        : node.querySelector('.lf-msg-text')?.innerText.trim())"""


# The run's height above the user's message: the steps `ids` names, as they show, and
# its face.
def test_a_thread_shows_only_the_agent_s_newest_step_where_it_was_said(browser, serve):
    """Of the agent's steps in a row, a thread shows only the newest, as its working
    message where the step was said, with no disclosure offering the steps before it.
    A message of the user's after it leaves it standing above that message."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?", {"section": "jobs"})
    for text in ("Reading the jobs.", "Comparing the frost dates."):
        thread_model.post_reply(
            serve.page_dir, {"parent": root, "responds": root}, text, ephemeral=True
        )
    append_user_reply(serve.page_dir, root, "And the camera?")
    page = open_page(browser, url)
    resized(page, 390, 900)
    thread = page.locator("#jobs .lf-page-thread")
    face = thread.locator(".lf-thread-working")
    message = thread.locator(".lf-msg[data-lf-author=user]", has_text="And the camera?")
    expect(face).to_have_count(1)
    expect(face).to_contain_text("Comparing the frost dates")
    assert face.bounding_box()["y"] < message.bounding_box()["y"]
    expect(thread.locator(".lf-summary-expand")).to_have_count(0)


def test_an_older_answer_keeps_newer_work_visible_without_its_progress_history(
    browser, serve
):
    """Answering an earlier input hides progress without breaking the thread while
    another input's workflow still runs."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "First task")
    newer = append_command(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root,
            "text": "New task",
        },
    )
    progress = thread_model.post_reply(
        serve.page_dir,
        {"responds": newer["id"]},
        "Checking the new task.",
        ephemeral=True,
    )
    answer = append_command(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root,
            "responds": root,
            "text": "First task done.",
        },
    )
    page = open_page(browser, url)
    workflows = page.evaluate(
        """async id => {
          const {readThreads} = await window.__lfWidgetApi();
          return readThreads().threads.find(thread => thread.id === id).workflows;
        }""",
        root,
    )
    assert any(workflow["state"] == "running" for workflow in workflows), workflows
    thread = open_panel_thread(page, root)
    expect(thread.locator(f'.lf-msg[data-lf-event="{answer["id"]}"]')).to_be_visible()
    expect(thread.locator(".lf-thread-working")).to_contain_text(
        "Checking the new task"
    )
    expect(thread.locator(f'.lf-msg[data-lf-event="{progress["id"]}"]')).to_be_hidden()
    expect(
        thread.get_by_role("button", name=re.compile("progress message"))
    ).to_have_count(0)
    expect(thread.get_by_text("New task", exact=True)).to_be_visible()
