"""How an agent's replies draw in a thread: streaming into a card, completing as a
durable answer, the working message while the agent works, what an answer's head says it
leaves, and the widgets its markup carries."""

import re

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, response_reference
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import interaction_log as interaction_model
from leaf import service as service_model
from leaf import thread as thread_model
from leaf import todos as todos_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    SEATED_OBLIGATION_PAGE,
    THREAD_DIFF_PAGE,
    panel_comment,
)
from render_harness import (
    held_frames,
    holding,
    open_page,
    panel_settled,
    resized,
    sending,
    told,
    write,
)

from browser.threads import (
    PANEL_NEWS,
    PANEL_REPLY,
    STREAM_ATTEMPT,
    append_user_reply,
    claim_for_codex,
    open_panel_thread,
    reply_by_keyboard,
    stream_reply,
    thread_row,
)

pytestmark = pytest.mark.shifts_unsurveyed


def card_of(root):
    """The margin card reading the thread `root`."""
    return f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]'


def open_margin_card(page, section):
    """Open the margin card of the thread on `section`, by its marker."""
    page.locator(f'[data-lf-margin-for="{section}"] .lf-margin-marker').click()
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_visible()


def test_a_durable_answer_retires_the_placeholder_its_attempt_reserved(
    browser, serve, request
):
    """The answer the log holds is what the panel draws, not the draft it replaced.

    `publish-site` failed on a deployed turn that published its revision and replied:
    the container held the answer, every server reading returned it, and the user's
    panel showed one agent bubble with no words in it. The provisional reply was
    retired only by the response address it was sent to, so an answer that named only
    the attempt it was reserved under stood beside its own placeholder and the draft
    is what got drawn. A logged event naming either identity retires the draft.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Answer me here", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "Checking the deployment.")

    page = open_page(browser, url)
    open_margin_card(page, "h-how")
    drafted = page.locator(
        f'.lf-margin-preview .lf-msg[data-attempt="{STREAM_ATTEMPT}"] .lf-msg-text'
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
    notice = thread.get_by_role("button", name="1 new reply", exact=True)
    expect(notice).to_be_visible()
    expect(drafted).to_have_text("Checking the deployment.")
    notice.click()
    answered = thread.locator(f'.lf-msg[data-attempt="{STREAM_ATTEMPT}"]')
    expect(thread.locator(".lf-msg.agent")).to_have_count(1)
    expect(answered).to_have_attribute("data-event", reply["id"])
    expect(answered.locator(".lf-msg-text")).to_have_text("deployment verified")


def test_a_durable_reply_completes_its_stream_placeholder_in_place(
    browser, serve, request
):
    """One retained message gains its durable prose and validated authored island.

    The stream placeholder exists before the final event, so its owner must not freeze
    the absence of markup at construction. The answer completes the reply the open
    thread was already streaming, so it shows as it lands. A later prose edit keeps both
    that owner and the island the durable reply introduced. The panel's view reads it:
    a passage's margin card draws no reply markup, which opens in the panel.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Answer me here")
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "Looking at it now.")

    page = open_page(browser, url)
    expect(thread_row(page, root).locator(".lf-fp-value")).to_have_text("Replying")
    thread = open_panel_thread(page, root)
    message = thread.locator(f'.lf-msg[data-attempt="{STREAM_ATTEMPT}"]')
    expect(message.locator(".lf-msg-text")).to_have_text("Looking at it now.")
    expect(message.locator(".lf-msg-head .lf-msg-sending")).to_have_count(0)
    page.evaluate(
        "attempt => { window.__streamMessage = document.querySelector("
        '`.lf-fp-view .lf-msg[data-attempt="${attempt}"]`); }',
        STREAM_ATTEMPT,
    )

    reply = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "The complete answer.",
        '<lf-ask id="stream-reply-ask"><h3>Use this answer?</h3>'
        '<lf-options id="stream-reply-choice" choose>'
        '<lf-option id="stream-reply-now">Use it now</lf-option>'
        "</lf-options></lf-ask>",
        attempt=STREAM_ATTEMPT,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")

    told(page)
    expect(message).to_have_attribute("data-event", reply["id"])
    expect(message.locator(".lf-msg-text")).to_have_text("The complete answer.")
    expect(message.locator("#stream-reply-choice")).to_have_count(1)
    expect(page.locator(PANEL_NEWS)).to_be_hidden()
    page.evaluate(
        "() => { window.__streamWidget = document.querySelector("
        "'#stream-reply-choice'); }"
    )

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "session": "codex-thread",
            "message": reply["id"],
            "text": "The complete edited answer.",
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
    expect(message.locator(".lf-msg-text")).to_have_text("The complete edited answer.")
    assert page.evaluate(
        f"""() => window.__streamMessage === document.querySelector(
          '.lf-fp-view .lf-msg[data-event="{reply["id"]}"]')
          && window.__streamWidget === document.querySelector('#stream-reply-choice')"""
    ), "the durable reply or its authored island was replaced after the edit"


def test_a_codex_reply_streams_into_an_open_card_and_its_answer_completes_it(
    browser, serve, request
):
    """The agent's opening streams into the open card the user is reading, and the
    explicit answer completes that same message.

    On a real Codex App Server turn the card drew an empty agent bubble as the turn
    started, held the opening's first words as an edit of it behind "1 new reply", and
    the answer, written by `leaf response reply` under a retry key of its own, took the
    bubble away and appended itself. The provisional reply now joins the thread with
    its first words, its words join it as they come, and the answer to the same input
    is the same message.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Record the release", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "")

    page = open_page(browser, url)
    expect(thread_row(page, root).locator(".lf-fp-value")).to_have_text("Replying")
    open_margin_card(page, "h-how")
    thread = page.locator(card_of(root))
    expect(thread.locator(".lf-msg.agent")).to_have_count(0)

    stream_reply(serve.page_dir, root, "I'll")
    told(page)
    streamed = thread.locator(".lf-msg.agent")
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
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    expect(streamed).to_have_count(1)
    expect(streamed).to_have_attribute("data-event", reply["id"])
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
    drawn = thread.locator(".lf-msg.agent .lf-msg-text")
    expect(drawn).to_have_text("First words")
    write(thread.locator(":scope > .lf-thread-reply leaf-text"), "Also note the date")

    notice = thread.locator(".lf-thread-news")
    for words in ("First words and more", "First words and more of them"):
        stream_reply(serve.page_dir, root, words)
        told(page)
        expect(notice).to_have_text("1 new reply")
        expect(drawn).to_have_text("First words")

    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Recorded the release on the board.",
        attempt="leaf-response-explicit",
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    expect(notice).to_have_text("1 new reply")
    expect(drawn).to_have_text("First words")

    # A later reading compares against the held drawing, which still stands for the
    # streaming reply the answer completed rather than an answer since reworded.
    append_user_reply(serve.page_dir, root, "Sent from my other tab")
    told(page)
    expect(notice).to_have_text("1 new reply · 1 new message")
    notice.click()
    expect(drawn).to_have_text("Recorded the release on the board.")
    expect(thread.locator(".lf-msg.user")).to_have_count(2)


def test_an_answer_completing_its_stream_with_the_same_words_folds_progress_as_its_own(
    browser, serve, request
):
    """An App Server final repeats the words it streamed, and it folds the progress
    before it into its disclosure. That fold is the answer's news, so a card the user
    is writing in, which holds it, says a reply arrived rather than that a summary
    changed.
    """
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
    expect(thread.locator(".lf-msg.agent")).to_have_count(2)
    write(thread.locator(":scope > .lf-thread-reply leaf-text"), "Also note the date")

    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Recorded the release.",
        attempt=STREAM_ATTEMPT,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    notice = thread.locator(".lf-thread-news")
    expect(notice).to_have_text("1 new reply")
    notice.click()
    expect(notice).to_have_count(0)
    expect(thread.locator(".lf-msg.agent").last.locator(".lf-msg-text")).to_have_text(
        "Recorded the release."
    )


@pytest.mark.watch_shifts
@pytest.mark.parametrize("streamed", [False, True])
def test_an_idle_card_shows_an_answer_folding_the_progress_at_its_end(
    browser, serve, request, streamed
):
    """The agent acknowledges a move with progress before it answers, and the answer
    folds that progress into its disclosure. In an open card the user is reading but
    not writing in, that fold changes only the thread's end, so the answer shows as it
    lands, streamed or not. The progress disclosure stays put when the answer gains
    its feedback control, and nothing above the progress moves.
    """
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
    expect(thread.locator(".lf-msg.agent")).to_have_count(1)
    if streamed:
        stream_reply(serve.page_dir, root, "Recording the release now.")
        told(page)
        expect(thread.locator(".lf-msg.agent")).to_have_count(2)
    opening = thread.locator(".lf-msg").first
    resting = opening.bounding_box()

    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Recorded the release on the board.",
        attempt=STREAM_ATTEMPT,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    answer = thread.locator(".lf-msg.agent:not(.lf-summary-originals *)")
    expect(answer.locator(".lf-msg-text")).to_have_text(
        "Recorded the release on the board."
    )
    expect(thread.locator(".lf-thread-checkpoint")).to_have_count(1)
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    assert opening.bounding_box() == resting, "the fold moved what stood above it"


def test_pending_progress_is_the_threads_working_message_and_never_unread(
    browser, serve, request
):
    """While the agent works, its progress shows as one dim working message above the
    reply box, not as replies: each step replaces the last, nothing counts unread, and
    the earlier steps stay out of sight. The answer takes the working message's place
    and folds the steps behind its own disclosure."""
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
    # The comment's card on the agent's list says the agent's last step on it, as the
    # page's status does, rather than only that it is working.
    page.locator(".lf-fp-on-user").click()
    panel_settled(page, view="queue")
    page.locator(".lf-fp-filters button").filter(has_text="On Codex").click()
    card = page.locator('.lf-fp-on-item[data-list="agent"]')
    expect(card.locator(".lf-fp-said")).to_have_text("Trying a lighter weight.")
    # Nothing counts unread.
    expect(thread_row(page, root)).not_to_have_attribute("data-unread", "")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == "reply_visible" and entry.get("input_id") == root
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
    # The working line is actual agent feedback even while each underlying progress
    # MessageView is folded. It uses the input's exact workflow identity, not the
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
        expect(thread.locator(f'.lf-msg[data-event="{step["id"]}"]')).to_be_hidden()

    answer = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Done in v4: the banner is one weight lighter.",
        identity=codex,
    )
    told(page)
    expect(line).to_have_count(0)
    expect(thread.locator(f'.lf-msg[data-event="{answer["id"]}"]')).to_be_visible()
    expect(
        thread.get_by_role("button", name="Show 3 progress messages", exact=True)
    ).to_be_visible()

    # A second session can post progress after the first session answered. It has
    # no owed input's workflow, so its own message supplies both author and time.
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
    expect(line).not_to_have_attribute("data-lf-live", "")


@pytest.mark.watch_shifts
def test_a_new_step_waits_where_its_words_would_move_the_draft(browser, serve):
    """A step's words wrap, so a new step can change the working message's height. In a
    seat where that would move the reply being typed, the step waits behind the
    thread's notice, as a reply would, and the draft keeps its place."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?", {"section": "jobs"})
    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Reading the jobs.",
        ephemeral=True,
    )
    page = open_page(browser, url)
    resized(page, 390, 900)
    thread = page.locator("#jobs .lf-page-thread")
    words = thread.locator(".lf-thread-working-words")
    expect(words).to_have_text("Reading the jobs")
    editor = thread.locator("leaf-text")
    write(editor, "Start with the mounts.")
    rendered(page)
    box = editor.bounding_box()

    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Comparing the mounts, the bird bath and the camera against the frost "
        "dates, and what each one needs before it can start.",
        ephemeral=True,
    )
    told(page)
    notice = thread.get_by_role("button", name="1 new message", exact=True)
    expect(notice).to_be_visible()
    expect(words).to_have_text("Reading the jobs")
    rendered(page)
    assert editor.bounding_box() == pytest.approx(box, abs=0.5)

    notice.click()
    expect(words).to_contain_text("what each one needs before it can start")
    assert editor.evaluate("box => box.value") == "Start with the mounts."


def test_held_news_too_long_for_its_notice_drops_a_later_fact_whole(browser, serve):
    """A seat's notice keeps the width of the news it first said, with room at its end
    for a count. News that grows past it shows its first fact whole and drops the
    later one, which the notice's name still says, rather than cutting the first fact
    mid-word ("1 new re…"). The count says "+1" in the room the notice kept, so a
    reader with no tooltip knows more waits; the name doesn't repeat it."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?", {"section": "jobs"})
    page = open_page(browser, url)
    resized(page, 390, 900)
    thread = page.locator("#jobs .lf-page-thread")
    expect(thread).to_be_visible()
    write(thread.locator("leaf-text"), "Start with the mounts.")
    rendered(page)

    thread_model.post_reply(
        serve.page_dir, {"responds": root}, "The mounts come first."
    )
    told(page)
    notice = thread.get_by_role("button", name="1 new reply", exact=True)
    expect(notice).to_be_visible()
    rendered(page)
    width = notice.bounding_box()["width"]
    expect(notice.locator(":scope > span")).not_to_have_attribute(
        "data-lf-more", re.compile(".*")
    )

    append_user_reply(serve.page_dir, root, "And the bird bath?")
    told(page)
    notice = thread.get_by_role(
        "button", name="1 new reply · 1 new message", exact=True
    )
    expect(notice).to_be_visible()
    rendered(page)
    assert notice.bounding_box()["width"] == pytest.approx(width, abs=0.5)
    words = notice.locator(":scope > span")
    expect(words).to_have_attribute("data-lf-more", "+1")
    # The count draws in the room the notice kept past the words it follows.
    count = words.evaluate(
        """words => {
            const after = getComputedStyle(words, "::after");
            const start = words.getBoundingClientRect().right;
            return {content: after.content, end: start + parseFloat(after.width),
                right: words.parentElement.getBoundingClientRect().right};
        }"""
    )
    assert count["content"] == '"+1" / ""', count
    assert count["end"] <= count["right"] + 0.5, count
    facts = notice.locator(":scope > span > span")
    assert facts.nth(0).evaluate("fact => fact.scrollWidth <= fact.clientWidth")
    # The later fact wraps past the words' clip, so nothing of it draws or takes a press.
    assert facts.nth(1).evaluate(
        """fact => {
            const box = fact.getBoundingClientRect();
            const hit = fact
                .getRootNode()
                .elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
            return !fact.contains(hit);
        }"""
    )


def test_held_news_shows_every_fact_its_notice_first_said(browser, serve):
    """A seat's notice that first says two facts keeps both on its line. Its room
    measures the news as one line and the facts measure it in pieces, a fraction of a
    pixel wider, which dropped the last fact and left a gap where it fit."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?", {"section": "jobs"})
    page = open_page(browser, url)
    resized(page, 1200, 900)
    thread = page.locator("#jobs .lf-page-thread")
    expect(thread).to_be_visible()
    write(thread.locator("leaf-text"), "Start with the mounts.")
    rendered(page)

    thread_model.post_reply(
        serve.page_dir, {"responds": root}, "The mounts come first."
    )
    append_user_reply(serve.page_dir, root, "And the bird bath?")
    told(page)
    notice = thread.get_by_role(
        "button", name="1 new reply · 1 new message", exact=True
    )
    expect(notice).to_have_attribute("data-lf-room", "1 new reply · 1 new message")
    rendered(page)
    words = notice.locator(":scope > span")
    assert words.evaluate(
        "words => [...words.children].map(fact => fact.offsetTop)"
    ) == [0, 0]
    expect(words).not_to_have_attribute("data-lf-more", re.compile(".*"))


def test_a_streaming_answer_takes_the_working_messages_place_and_disclosure(
    browser, serve, request
):
    """An answer streaming in is the agent's next word: the working message gives way to
    it, and its head holds the progress disclosure the fold will hold once it lands."""
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
    streamed = thread.locator(".lf-msg.agent").last
    expect(streamed.locator(".lf-msg-text")).to_have_text("Recording the release now.")
    show = streamed.locator(".lf-msg-head").get_by_role(
        "button", name="Show 1 progress message", exact=True
    )
    show.press("Enter")
    expect(thread.locator(f'.lf-msg[data-event="{step["id"]}"]')).to_be_visible()


def test_an_answer_says_what_it_leaves_while_that_stands(browser, serve, request):
    """An answer that asks back or promises work says so in its head, beside its time,
    for as long as the obligation is the user's or the to-do stays open."""
    url = serve(PANEL_PAGE)
    asked = panel_comment(serve.page_dir, "Which store owns it?", {"section": "h-how"})
    promised = panel_comment(serve.page_dir, "Rebuild the banner", {"section": "lede"})
    claim_for_codex(serve.page_dir, request)
    codex = {"agent": "Codex", "session": "codex-thread"}
    question = thread_model.post_reply(
        serve.page_dir,
        {"responds": asked},
        "One question:",
        markup='<lf-ask id="store-choice">The session store or the page store?</lf-ask>',
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
        (promised, promise, "To-do open", "lede"),
    ):
        open_margin_card(page, section)
        thread = page.locator(card_of(root))
        head = thread.locator(f'.lf-msg[data-event="{reply["id"]}"] .lf-msg-head')
        expect(head.locator(".lf-msg-leaves")).to_have_text(words)

    todos_model.cmd_end(serve.page_dir, promise["id"], "done", "Rebuilt in v4")
    told(page)
    head = page.locator(
        f'.lf-margin-preview .lf-msg[data-event="{promise["id"]}"] .lf-msg-head'
    )
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
            "text": "Here is the board.",
            "markup": '<lf-board id="fb"><lf-column id="fb-todo" label="To do">'
            '<lf-card id="fb-cache"><strong>Cache</strong></lf-card></lf-column>'
            '<lf-column id="fb-done" label="Done"></lf-column></lf-board>',
        },
    )
    page = open_page(browser, url)
    # Nobody's turn: the thread's row says it is open and no more.
    status = thread_row(page, root).locator(".lf-fp-value")
    expect(status).to_have_text(re.compile(r"^(Open)?$"))
    card = open_panel_thread(page, root)
    receipt = page.locator(
        f'.lf-fp-view .lf-msg[data-event="{board["id"]}"] .lf-msg-sending'
    )

    page.locator("#fb-cache .lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    with sending(page, "the card move"):
        page.keyboard.press("Enter")
    expect(page.locator("#fb-done > #fb-cache")).to_be_visible()
    expect(receipt).to_have_text("Sent")
    status = thread_row(page, root).locator(".lf-fp-value")
    expect(status).to_have_text(re.compile(r"^(Open)?$"))
    card = open_panel_thread(page, root)

    [moved] = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert not moved["attention"]
    assert moved not in service_model.unacknowledged(
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
    news = page.locator(PANEL_NEWS).filter(has_text="1 new reply")
    if news.count():
        news.click()
    expect(card.locator(".lf-msg").filter(has_text="Cache is done")).to_be_visible()
    expect(page.locator("#fb-done > #fb-cache")).to_be_visible()


def test_a_harness_failure_receipt_does_not_read_as_an_answer(browser, serve):
    """A reply saying no answer is coming is marked as one, in both faces of the head.

    Nothing else in the message says it: a harness receipt is a reply event, written
    under the thread's own agent name, in the same bubble as a real answer, and its
    prose is the only other difference. So a user skimming a thread reads an
    apology from the agent rather than a notice that their message went nowhere, and
    the page's own record of the failure — `failure` — went unread. The mark belongs
    in the head because that is the part of a message a user takes on trust.
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
    receipt = thread_model.post_reply(
        serve.page_dir,
        {"responds": unanswered["id"]},
        "The agent's turn ended without an answer to this message. "
        "Send it again to retry.",
        failure="turn_failed",
    )

    page = open_page(browser, url)
    resized(page, 1200, 900)
    inline = page.locator(f'#cd-q .lf-msg[data-event="{receipt["id"]}"]')
    expect(inline.locator(".lf-msg-failure")).to_have_text("Not answered")
    assert inline.get_attribute("data-failure") == "turn_failed"
    # The real answer above it wears nothing, so the mark is a difference the user
    # can see rather than a decoration every agent message carries.
    real = page.locator(f'#cd-q .lf-msg[data-event="{answer["id"]}"]')
    expect(real.locator(".lf-msg-failure")).to_have_count(0)

    # The server settled its turn, and the thread's `attention` still reads
    # `needs_user` for recovery: the margin and panel name the action owed.
    margin = page.locator('[data-lf-margin-for="cd-q"] > .lf-margin-marker')
    expect(margin).to_have_attribute("data-lf-turn", "user")
    expect(margin.locator(".lf-margin-entry-context")).to_have_text("My turn to resend")

    # Threads names the action owed on the thread's row, whole.
    status = thread_row(page, unanswered["id"]).locator(".lf-fp-value")
    expect(status).to_have_text("My turn to resend")
    assert status.evaluate("el => el.scrollWidth <= el.clientWidth"), (
        "the row clips its failure status"
    )
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)

    # A held resend from the thread's own card leaves its box empty while the server
    # reads it; refusal restores the draft, and the recovery still stands.
    card = page.locator(f'#cd-q .lf-page-thread[data-thread="{unanswered["id"]}"]')
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
    expect(margin.locator(".lf-margin-entry-context")).to_have_text("My turn to resend")

    # The failed answer remains distinct from the muted clock without a chip face.
    head = page.evaluate(
        """(id) => {
          const head = document.querySelector(
            `#cd-q .lf-msg[data-event="${id}"] .lf-msg-head`);
          const failure = getComputedStyle(head.querySelector(".lf-msg-failure"));
          return {
            failure: failure.color,
            border: failure.borderTopWidth,
            weight: failure.fontWeight,
            clock: getComputedStyle(head.querySelector("time")).color,
          };
        }""",
        receipt["id"],
    )
    assert head["failure"] != head["clock"]
    assert head["border"] == "0px" and int(head["weight"]) >= 600


def test_a_bounded_log_in_an_agent_reply_follows_its_end_as_a_reading_region(
    browser, serve
):
    """A reply's markup is painted where the thread draws it, not by the page's install,
    so a log bounded at its end in a reply was neither held at its end nor the box
    scrolling its lines until some later revision swept the page."""
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
            "response",
            "reply",
            "--done",
            response_reference(serve.page_dir, root),
            "--text",
            "Here is its log.",
            "--markup",
            markup,
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


def test_collapsing_progress_preserves_room_for_a_later_canceled_stream(
    browser, serve, request
):
    """Only the disclosure's own change resizes the card, even before a frame paints:
    the canceled stream's room stays, so the reply stands where it stood."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep this thread here.", {"section": "h-how"})
    for words in ("Checking labels.", "Measuring controls.", "Checking both schemes."):
        thread_model.post_reply(
            serve.page_dir, {"responds": root}, words, ephemeral=True
        )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root,
            "text": "The labels work.",
        },
    )
    claim_for_codex(serve.page_dir, request)
    stream_reply(
        serve.page_dir,
        root,
        "This provisional answer has several lines of useful context. " * 5,
    )
    page = open_page(browser, url)
    resized(page, 1400, 1200)
    open_margin_card(page, "h-how")
    card = page.locator(card_of(root))
    stream = card.locator(f'.lf-msg[data-attempt="{STREAM_ATTEMPT}"]')
    expect(stream).to_be_visible()
    rendered(page)
    reply = card.locator(".lf-thread-reply")
    compact = card.bounding_box()["height"]
    standing = reply.bounding_box()["y"]
    progress = card.locator(".lf-summary-expand")
    progress.press("Enter")
    rendered(page)
    with held_frames(page):
        progress.press("Enter")
        expect(progress).to_have_attribute("aria-expanded", "false")
        with service_model.PageTransaction(serve.page_dir) as transaction:
            transaction.clear_stream_reply("codex-thread", "leaf-turn")
        expect(stream).to_have_count(0)
    rendered(page)
    assert card.bounding_box()["height"] == pytest.approx(compact, abs=0.5)
    assert reply.bounding_box()["y"] == pytest.approx(standing, abs=0.5)


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
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    expect(view.locator(f'.lf-msg[data-attempt="{STREAM_ATTEMPT}"]')).to_have_count(0)
    rendered(page)
    assert view.evaluate(
        "node => node.scrollHeight - node.scrollTop - node.clientHeight"
    ) == pytest.approx(0, abs=1)
    assert reply.bounding_box()["y"] == pytest.approx(reply_top, abs=1)
    expect(reply).to_have_js_property("value", "Half a thought")


# The open thread view's user messages and working message in the order they stand, each
# user message by its words.
TRANSCRIPT_ORDER = """view => [...view.querySelectorAll('.lf-msg.user, .lf-thread-working')]
    .filter((node) => node.checkVisibility())
    .map((node) => node.matches('.lf-thread-working')
        ? 'working'
        : node.querySelector('.lf-msg-text')?.innerText.trim())"""


@pytest.mark.watch_shifts
def test_a_reply_sent_after_progress_stands_below_it(browser, serve, request):
    """A thread reads in the order its messages were said, and nothing moves above the
    user's message as the agent goes on. The agent's progress line was said before the
    user's next message, so that message stands below it, both as the send draws it
    and once the log holds it; the agent's next step stands below the message, the
    earlier one staying where it was, still; and the answer folds only the step it
    follows."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Record the release", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    thread_model.post_reply(
        serve.page_dir,
        {"parent": root, "responds": root},
        "Checking the board",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    page = open_page(browser, url)
    view = reply_by_keyboard(page, root)
    expect(view.locator(".lf-thread-working")).to_be_visible()
    page.keyboard.type("And the changelog?")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(view.locator(".lf-msg.user", has_text="And the changelog?")).to_be_visible()
    assert view.evaluate(TRANSCRIPT_ORDER)[-2:] == ["working", "And the changelog?"]
    told(page)
    assert view.evaluate(TRANSCRIPT_ORDER)[-2:] == ["working", "And the changelog?"]

    # The agent's next step is said after the user's message, so it stands below it.
    asked = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply" and event["author"] == "user"
    )
    thread_model.post_reply(
        serve.page_dir,
        {"responds": asked["id"]},
        "Reading the changelog",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    told(page)
    assert view.evaluate(TRANSCRIPT_ORDER)[-3:] == [
        "working",
        "And the changelog?",
        "working",
    ]
    faces = view.locator(".lf-thread-working")
    expect(faces.first).not_to_have_attribute("data-lf-live", "")
    expect(faces.last).to_have_attribute("data-lf-live", "")
    expect(faces.last).to_have_text(re.compile("Reading the changelog"))

    # The answer folds the step it follows behind its head; the step the user spoke
    # after stays where it was said.
    answer = thread_model.post_reply(
        serve.page_dir,
        {"responds": asked["id"]},
        "Recorded, with the changelog.",
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    told(page)
    expect(view.locator(f'.lf-msg[data-event="{answer["id"]}"]')).to_be_visible()
    assert view.evaluate(TRANSCRIPT_ORDER)[-2:] == ["working", "And the changelog?"]
    expect(view.locator(".lf-thread-working")).to_have_text(
        re.compile("Checking the board")
    )
    expect(view.locator(".lf-thread-working")).not_to_have_attribute("data-lf-live", "")
    expect(
        view.get_by_role("button", name="Show 1 progress message", exact=True)
    ).to_be_visible()


@pytest.mark.watch_shifts
def test_progress_the_user_spoke_after_keeps_its_steps_and_its_place(browser, serve):
    """A run of progress the user spoke after is one no answer folds, so its face
    offers its earlier steps itself, and a rewrite of the step it shows waits behind the
    thread's notice where it would move the user's message below it."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?", {"section": "jobs"})
    steps = [
        thread_model.post_reply(
            serve.page_dir, {"parent": root, "responds": root}, text, ephemeral=True
        )
        for text in ("Reading the jobs.", "Comparing the frost dates.")
    ]
    asked = append_user_reply(serve.page_dir, root, "And the camera?")
    thread_model.post_reply(
        serve.page_dir,
        {"responds": asked["id"]},
        "Checking the camera.",
        ephemeral=True,
    )
    page = open_page(browser, url)
    resized(page, 390, 900)
    thread = page.locator("#jobs .lf-page-thread")
    first = thread.locator(f'.lf-msg[data-event="{steps[0]["id"]}"]')
    expect(first).to_be_hidden()
    show = thread.get_by_role("button", name="Show 2 progress messages", exact=True)
    show.press("Enter")
    expect(first).to_be_visible()
    thread.get_by_role("button", name="Hide 2 progress messages", exact=True).press(
        "Enter"
    )
    expect(first).to_be_hidden()

    message = thread.locator(".lf-msg.user", has_text="And the camera?")
    rendered(page)
    box = message.bounding_box()
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "session": "pytest",
            "message": steps[1]["id"],
            "text": "Comparing the frost dates for the mounts, the bird bath and the "
            "camera, and what each one needs before it can start.",
        },
    )
    told(page)
    notice = thread.get_by_role("button", name="1 message edited", exact=True)
    expect(notice).to_be_visible()
    rendered(page)
    assert message.bounding_box() == pytest.approx(box, abs=0.5)
    notice.click()
    expect(thread.locator(".lf-thread-working").first).to_contain_text("bird bath")

    # Opened, the run shows the step itself above its face, which can stand below the
    # window while the step shows; a rewrite of it holds the same.
    show.press("Enter")
    expect(first).to_be_visible()
    resized(page, 390, 540)
    page.evaluate("scrollTo(0, 0)")
    rendered(page)
    box = message.bounding_box()
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "session": "pytest",
            "message": steps[1]["id"],
            "text": "Comparing the frost dates.",
        },
    )
    told(page)
    expect(notice).to_be_visible()
    rendered(page)
    assert message.bounding_box() == pytest.approx(box, abs=0.5)
