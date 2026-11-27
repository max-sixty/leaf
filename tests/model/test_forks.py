"""The line fork of a Claude Code session: the session gets each thread message at
once, as any input, and the line fork posts the agent's working line beside it, only
while the round it answers still awaits a line (`forks.py`)."""

import json
import os

import pytest
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    append_command,
    page_packages,
    serving,
    stamp,
)

from leaf.agents import clerk as clerk_model
from leaf.agents import delivery as delivery_model
from leaf.agents import forks as forks_model
from leaf.agents import presence as presence_model
from leaf.agents import thread as thread_model
from leaf.agents.presence import read_work
from leaf.base import harness as harness_model
from leaf.base import leases as leases_model
from leaf.base import page_memory as page_memory_model
from leaf.base import service as service_model
from leaf.base import state as state_model
from leaf.commands import hooks as hooks_model
from leaf.log import event_log as events_model
from leaf.log import file_changes as file_changes_model
from leaf.log.interaction_log import read_interactions
from leaf.records import revisioning as revisioning_model
from leaf.records import transaction as transaction_model
from leaf.records.transaction import PageTransaction
from leaf.serving import event_endpoint as endpoint_model
from leaf.serving import server_rows as server_rows_model

# What Leaf's Claude Code hooks module gives the pages follower of session s1
# (`hooks.cmd_pages`).
FOLLOWER = {"session_id": "s1"}


@pytest.fixture
def lane(claimed):
    """Session s1's forks lane, held as its pages follower holds it."""
    held = leases_model.take_lane("s1")
    yield held
    if not held.closed:
        leases_model.release_lease(held)


def said(page_dir, text: str, parent: str | None = None) -> dict:
    """The user's message, a comment opening a thread or a reply in one."""
    return append_carried_log_record(
        page_dir,
        {"kind": "reply", "parent": parent, "author": "user", "text": text}
        if parent
        else {"kind": "comment", "author": "user", "text": text},
    )


def deliverable(page_dir) -> list[str]:
    with PageTransaction(page_dir) as page:
        return [event["id"] for event in delivery_model.deliverable(page)]


def basis(page_dir, thread: str, *inputs: str) -> dict:
    """The round of `thread` whose waiting turns are `inputs`, as the follower lists
    it."""
    return {"page": str(page_dir), "thread": thread, "inputs": list(inputs)}


def listed(page_dir) -> list[dict]:
    """The rounds the follower lists for the page now, as one that first read it
    before anything was written."""
    reports, _after = forks_model.look("s1", page_dir, 0)
    return [report["basis"]["thread"] for report in reports]


def line_answer(line: str) -> str:
    """A line fork's answer: the agent's working line."""
    return json.dumps({"line": line})


def agents_words(page_dir) -> list[str]:
    """What the agent has said on the page, in log order."""
    return [
        event["text"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply" and event["author"] == "agent"
    ]


def on_it(page_dir) -> list[str]:
    """The inputs the served workflows of the page, which has a document, read as the
    agent's work in hand (`running`), which the page words On it while their delivery
    stands."""
    work = read_work(page_dir, events_model.read_events(page_dir))
    return sorted(
        item["input"] for item in work.workflows if item["state"] == "running"
    )


class _Untitled:
    """A harness that names no thread, so admission starts no title request."""

    inference = None


def test_a_thread_message_reaches_the_session_at_once_and_its_line_goes_in_beside_it(
    claimed, interactive, monkeypatch
):
    """Admission delivers a thread message to a Claude Code session as it does any
    input, nudging an idle session no watch follows, with no line fork to wait for.
    The follower lists the message's round for a line fork, whose line goes in as the
    agent's progress without taking the message in hand: the message reads On it
    from then until the session answers, and stays input for the session. The page's
    diagnostics note the question and what came of it."""
    assert stamp(claimed).exit_code == 0
    nudged = []
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "nudge",
        lambda harness, page, quoted: nudged.append(page) or True,
    )
    monkeypatch.setattr(endpoint_model, "claim_harness", lambda _claim: _Untitled())
    state_model.close_session_turn("s1")
    status, admitted = endpoint_model.accept_event(
        claimed, {"kind": "comment", "revision": 1, "text": "Why a 2-second poll?"}
    )
    assert status == 200, admitted
    asked = admitted["event"]["id"]
    assert nudged == [claimed.resolve()]
    assert deliverable(claimed) == [asked]
    assert on_it(claimed) == []
    assert listed(claimed) == [basis(claimed, asked, asked)]

    question = forks_model.ask("s1", basis(claimed, asked, asked), [])
    assert question is not None
    assert question["prompt"].startswith(forks_model.LINE_OPENING)
    assert "Why a 2-second poll?" in question["prompt"]
    assert "ends where the session last sent it to the model" in question["prompt"]
    posted = forks_model.route(
        "s1",
        question["thread"],
        answer=line_answer(" checking why the poll is 2 s\n"),
        failed=None,
    )
    assert posted["outcome"] == "posted", posted
    [line] = [
        event for event in events_model.read_events(claimed) if event["kind"] == "reply"
    ]
    assert line["id"] == posted["line"]
    assert (line["text"], line["session"], line["ephemeral"], line["parent"]) == (
        "checking why the poll is 2 s",
        "s1",
        True,
        asked,
    )
    # The line is the agent's words, not the session's start: every reader but the
    # word keeps the message where its delivery is until the session takes it in hand.
    assert "start" not in line
    assert on_it(claimed) == [asked]
    assert deliverable(claimed) == [asked]
    assert nudged == [claimed.resolve()]
    assert [
        (row["type"], row.get("outcome"))
        for row in read_interactions(claimed, types=("fork_asked", "fork_outcome"))
    ] == [("fork_asked", None), ("fork_outcome", "posted")]

    thread_model.post_reply(claimed, {"responds": asked}, "It matches the lease.")
    assert on_it(claimed) == []


def test_a_line_after_a_newer_message_leaves_one_its_turn_left_stopped(claimed):
    """The line is no start, so it covers no other message of its thread. Where a turn
    took in a message and ended without answering it, and a line then stands after a
    newer message there, the newer one reads On it by the line alone and the older
    still reads stopped."""
    assert stamp(claimed).exit_code == 0
    asked = said(claimed, "Why a 2-second poll?")
    claim = service_model.page_claim(claimed)
    assert claim is not None
    with PageTransaction(claimed) as page:
        delivery_model.record_pickup(
            page, [asked], session=claim["id"], turn=claim["turn"]
        )
    state_model.close_session_turn(claim["id"])
    again = said(claimed, "And why not a watch?", asked["id"])
    append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "parent": asked["id"],
            "author": "agent",
            "text": "checking why the poll is 2 s",
            "ephemeral": True,
        },
    )

    work = read_work(claimed, events_model.read_events(claimed))
    assert {
        item["input"]: (item["state"], item["reason"]) for item in work.workflows
    } == {
        asked["id"]: ("blocked", "stopped"),
        again["id"]: ("running", None),
    }


@pytest.mark.parametrize("joins", ["reply", "edit"])
def test_a_turn_joining_a_round_before_its_line_gets_a_line_fork_about_all(
    claimed, joins
):
    """A second message, or the user's rewrite of the first, before the line fork
    answers joins the round, which the follower lists again with every waiting turn.
    The first line fork's line, about the first message alone, goes in nowhere; the
    new one's goes in, and the session has every turn as input."""
    first = said(claimed, "Why 30 s?")
    earlier = basis(claimed, first["id"], first["id"])
    second = (
        said(claimed, "Or rather, why not 20?", parent=first["id"])
        if joins == "reply"
        else append_carried_log_record(
            claimed,
            {"kind": "edit", "author": "user", "message": first["id"]}
            | {"text": "Why 40 s?"},
        )
    )
    later = basis(claimed, first["id"], first["id"], second["id"])
    assert listed(claimed) == [later]
    stale = forks_model.route(
        "s1", earlier, answer=line_answer("checking why 30 s"), failed=None
    )
    assert stale["outcome"] == "dropped", stale
    question = forks_model.ask("s1", later, [])
    assert question is not None
    assert ("why not 20?" if joins == "reply" else "Why 40 s?") in question["prompt"]
    posted = forks_model.route(
        "s1", later, answer=line_answer("weighing the interval"), failed=None
    )
    assert posted["outcome"] == "posted", posted
    assert agents_words(claimed) == ["weighing the interval"]
    assert deliverable(claimed) == [first["id"], second["id"]]


def test_a_pick_after_the_rounds_message_takes_its_line(claimed):
    """A pick on an option the agent offered in the thread, made after the user's
    message, joins that message's batch and carries the thread's one answer
    (`workflows.handed_over`). The round is still the message's, and its line goes in
    at the thread's answer."""
    assert revisioning_model.activate_source(claimed).error is None
    asked = append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": 'File it?\n\n<lf-options id="file-issue">'
            '<lf-option id="file" label="File it"><strong>File it</strong></lf-option>'
            "</lf-options>",
        },
    )
    message = said(claimed, "ok, can we file an issue?", parent=asked["id"])
    append_command(
        claimed,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "file-issue",
            "action": "choose",
            "detail": {"value": ["file"]},
            "answered": True,
        },
    )
    round_ = basis(claimed, asked["id"], message["id"])
    assert listed(claimed) == [round_]
    assert forks_model.ask("s1", round_, []) is not None
    posted = forks_model.route(
        "s1", round_, answer=line_answer("filing the issue"), failed=None
    )
    assert posted["outcome"] == "posted", posted
    assert agents_words(claimed) == ["filing the issue"]


@pytest.mark.parametrize("first", ["answer", "message", "progress", "rewrite"])
def test_a_line_the_agent_spoke_before_goes_in_nowhere(claimed, first):
    """The session has the message at once, so it may speak in the thread before the
    line fork answers: an answer, a message that answers nothing, its own progress,
    or a rewrite of its earlier answer. The line then goes in nowhere, so it never
    stands after the agent's own words."""
    opened = said(claimed, "Which TTL should the cache use?")
    earlier = thread_model.post_reply(claimed, {"responds": opened["id"]}, "Ten s.")
    asked = said(claimed, "Make it five.", parent=opened["id"])
    round_ = basis(claimed, opened["id"], asked["id"])
    if first == "answer":
        thread_model.post_reply(claimed, {"responds": asked["id"]}, "Five it is.")
    elif first == "message":
        thread_model.post_reply(claimed, {"parent": asked["id"]}, "Five it is.")
    elif first == "progress":
        thread_model.post_reply(
            claimed, {"responds": asked["id"]}, "Five it is.", ephemeral=True
        )
    else:
        thread_model.cmd_edit(claimed, earlier["id"], "Five s.")
    assert forks_model.ask("s1", round_, []) is None
    dropped = forks_model.route(
        "s1", round_, answer=line_answer("making it five"), failed=None
    )
    assert dropped["outcome"] == "dropped", dropped
    assert "making it five" not in agents_words(claimed)


def test_a_message_joining_as_the_line_goes_in_drops_the_line(claimed, monkeypatch):
    """Whether the round still awaits the line is asked under the lock the line's
    append takes, so a message the user sends while the line is on its way, which the
    page's server admits without the writers' lock, drops the line rather than
    standing it as if it spoke for the new message too."""
    asked = said(claimed, "Is the fence inside the append?")
    checked = thread_model.checked_text
    joined = []

    def joining_meanwhile(page_dir, text, **options):
        joined.append(said(claimed, "And the summary fork's?", parent=asked["id"]))
        return checked(page_dir, text, **options)

    monkeypatch.setattr(thread_model, "checked_text", joining_meanwhile)
    dropped = forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=line_answer("checking the fence"),
        failed=None,
    )
    assert dropped["outcome"] == "dropped", dropped
    assert agents_words(claimed) == []
    assert listed(claimed) == [
        basis(claimed, asked["id"], asked["id"], joined[0]["id"])
    ]


def test_a_repeated_line_fork_step_posts_nothing_more(claimed):
    """A step repeated for a round whose line went in, as a module reloaded mid-fork
    repeats it, finds the round no longer awaiting a line: its question asks no fork
    and its answer posts no second line."""
    asked = said(claimed, "Which Python?")
    round_ = basis(claimed, asked["id"], asked["id"])
    posted = forks_model.route("s1", round_, answer=line_answer("looking"), failed=None)
    assert posted["outcome"] == "posted", posted
    assert forks_model.ask("s1", round_, []) is None
    again = forks_model.route("s1", round_, answer=line_answer("again"), failed=None)
    assert again["outcome"] == "dropped", again
    assert agents_words(claimed) == ["looking"]


def test_a_failed_line_fork_posts_nothing(claimed):
    """A line fork that failed, or whose answer isn't the line Leaf asked for, posts
    nothing, and the message reads as its delivery stands."""
    assert stamp(claimed).exit_code == 0
    failed = said(claimed, "And the lane?")
    blank = said(claimed, "What does the follower print?")
    assert forks_model.route(
        "s1", basis(claimed, failed["id"], failed["id"]), answer=None, failed="aborted"
    ) == {"outcome": "failed", "why": "the fork failed: aborted"}
    assert forks_model.route(
        "s1",
        basis(claimed, blank["id"], blank["id"]),
        answer=line_answer(" "),
        failed=None,
    )["why"].startswith("the fork failed: the fork's answer doesn't fit its schema")
    assert agents_words(claimed) == []
    assert deliverable(claimed) == [failed["id"], blank["id"]]
    assert on_it(claimed) == []


def test_a_line_fork_of_a_session_the_page_has_left_writes_nothing(claimed):
    """The line goes in as the claimant's: a line fork of another session's
    conversation, as one answering after the page passed to a new session, posts
    nothing."""
    asked = said(claimed, "Who holds this?")
    round_ = basis(claimed, asked["id"], asked["id"])
    assert forks_model.ask("s2", round_, []) is None
    dropped = forks_model.route(
        "s2", round_, answer=line_answer("checking"), failed=None
    )
    assert dropped["outcome"] == "dropped", dropped
    assert agents_words(claimed) == []


def test_a_round_the_agent_spoke_in_gets_no_line_and_the_next_round_does(claimed):
    """A message that joins a round the agent has spoken in, by its line here, gets
    no line fork: the agent's words already stand after the round's first message.
    Once the agent answers, the user's follow-up starts a new round, whose line fork
    sees the earlier exchange."""
    asked = said(claimed, "Where does the line go in?")
    forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=line_answer("reading the fence"),
        failed=None,
    )
    more = said(claimed, "And who reads it?", parent=asked["id"])
    assert listed(claimed) == []
    assert more["id"] in deliverable(claimed)
    thread_model.post_reply(claimed, {"responds": more["id"]}, "In `forks._line`.")
    follow_up = said(claimed, "Thanks. Does the follower too?", parent=asked["id"])
    assert listed(claimed) == [basis(claimed, asked["id"], follow_up["id"])]
    question = forks_model.ask("s1", basis(claimed, asked["id"], follow_up["id"]), [])
    assert question is not None
    assert "In `forks._line`." in question["prompt"]


def test_the_running_tool_reaches_the_prompt(claimed):
    """Mid-turn, the session's last request predates the call it is running, so the
    fork's prompt names that call."""
    asked = said(claimed, "What are you running?")
    question = forks_model.ask(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        [{"tool": "Bash", "input": {"command": "pytest -x", "description": "tests"}}],
    )
    assert question is not None
    assert 'Bash command: "pytest -x" description: "tests"' in question["prompt"]


def long_thread(page_dir) -> tuple[dict, list[dict]]:
    """A thread of twelve answered messages: its opening comment, and the messages
    after it."""
    state_model.close_session_turn("s1")
    opened = said(page_dir, "Which TTL should the quote cache use?")
    later = [thread_model.post_reply(page_dir, {"responds": opened["id"]}, "Ten.")]
    for n in range(1, 6):
        asked = said(page_dir, f"Follow-up {n}?", parent=opened["id"])
        later += [
            asked,
            thread_model.post_reply(
                page_dir, {"responds": asked["id"]}, f"Answer {n}."
            ),
        ]
    return opened, later


def asked_in(page_dir, opened: dict, text: str) -> tuple[dict, dict]:
    """The user's newest message in the thread `opened` began, and what Leaf asks the
    module to fork for it (`forks.ask`)."""
    newest = said(page_dir, text, parent=opened["id"])
    question = forks_model.ask("s1", basis(page_dir, opened["id"], newest["id"]), [])
    assert question is not None
    return newest, question


def test_a_long_threads_summary_stays_the_forks_once_the_agent_speaks_first(
    claimed, lane
):
    """A delivery of a message that came to a round awaiting a line leaves the
    thread's summary to the fork beside that round's line fork, so the agent's own
    progress in the thread before the follower's report reaches Leaf, which leaves
    the line nothing to do, still gets the summary fork made: the summary keeps an
    owner."""
    opened, _ = long_thread(claimed)
    newest = said(claimed, "And the newest?", parent=opened["id"])
    thread_model.post_reply(
        claimed, {"responds": newest["id"]}, "Checking.", ephemeral=True
    )
    with PageTransaction(claimed) as page:
        [delivered] = delivery_model.batch_data(claimed, page, [newest])["threads"]
    assert "summary_hint" not in delivered
    [round_] = listed(claimed)
    made = forks_model.step(
        "s1",
        {"done": "line", "do": "report", "basis": {"kind": "line", "thread": round_}},
    )
    assert made is not None
    assert [instruction["basis"]["kind"] for instruction in made["do"]] == ["beside"]


def test_a_line_fork_reads_the_whole_of_a_long_thread(claimed):
    """A delivery to the session shows a long thread's opening and latest messages and
    leaves the middle to `leaf page state`, which a line fork can't run, so the fork's
    prompt carries every message of the thread."""
    opened, _ = long_thread(claimed)
    newest, question = asked_in(claimed, opened, "And the newest?")
    with PageTransaction(claimed) as page:
        [bounded] = delivery_model.batch_data(claimed, page, [newest])["threads"]
    assert bounded["elided"]["messages"] == 4
    assert "Follow-up 1?" not in json.dumps(bounded)
    assert "Follow-up 1?" in question["prompt"]
    assert '"messages": 0' in question["prompt"]


def summary_beside(page_dir) -> tuple[dict, list[dict], dict, dict]:
    """A long thread, the user's newest message in it, and the summary fork Leaf asks
    for beside its line fork: the thread's opening, its later messages, the newest
    message, and the summary fork's `{"prompt", "basis"}`."""
    opened, later = long_thread(page_dir)
    newest, question = asked_in(page_dir, opened, "And the newest?")
    [summary] = question["beside"]
    return opened, later, newest, summary


def summarized(summary: dict, answer: dict) -> dict:
    """What Leaf did with the summary fork's `answer`."""
    outcome = forks_model.step(
        "s1",
        {
            "done": "summary",
            "do": "fork",
            "basis": {"kind": "beside", **summary["basis"]},
            "answer": json.dumps(answer),
        },
    )
    assert outcome is not None
    assert outcome.pop("log").startswith("the summary fork for thread ")
    return outcome


def summaries_written(page_dir) -> list[tuple]:
    """Each summary the page's log holds, as its range and text."""
    with PageTransaction(page_dir) as page:
        return [
            (event["from"], event["through"], event["text"])
            for event in page.events
            if event["kind"] == "summary"
        ]


def test_a_long_thread_is_summarized_by_a_fork_beside_its_line_fork(claimed, lane):
    """A message that starts a round in a thread long enough to suggest a range to
    summarize gets a second fork beside the line fork, offered that range and asked to
    choose its own and summarize it from the whole thread by the agent's guidance. Its
    answer goes in as the agent's summary, which the agent hears of as its own. That
    message's delivery leaves the suggestion out while a follower lists the
    session's line forks, since the fork has it; the delivery of a message no line
    fork took up still carries it, as does every delivery once no follower does."""
    _, later, newest, summary = summary_beside(claimed)
    with PageTransaction(claimed) as page:
        [forked] = delivery_model.batch_data(claimed, page, [newest])["threads"]
        [unforked] = delivery_model.batch_data(claimed, page, [later[-2]])["threads"]
        leases_model.release_lease(lane)
        [unlisted] = delivery_model.batch_data(claimed, page, [newest])["threads"]
    hint = unforked["summary_hint"]
    assert "summary_hint" not in forked
    assert unlisted["summary_hint"] == hint
    assert (summary["basis"]["from"], summary["basis"]["through"]) == (
        hint["from"],
        hint["through"],
    )
    assert summary["prompt"].startswith("<leaf-summary-fork>")
    assert "Follow-up 1?" in summary["prompt"]
    assert "> Fold what compresses most" in summary["prompt"]
    assert "> A summary is what the user reads" in summary["prompt"]

    outcome = summarized(summary, {**hint, "text": "The TTL went to ten, then five."})
    assert outcome["outcome"] == "summarized"
    assert summaries_written(claimed) == [
        (hint["from"], hint["through"], "The TTL went to ten, then five.")
    ]
    with PageTransaction(claimed) as page:
        [written] = [event for event in page.events if event["kind"] == "summary"]
    assert (written["id"], written["author"]) == (outcome["summary"], "agent")
    [told] = clerk_model.queued("s1")
    assert outcome["summary"] in told and "> The TTL went to ten, then five." in told
    [noted] = read_interactions(claimed, types=("summary_fork",))
    assert noted["outcome"] == "summarized"


@pytest.mark.parametrize("withdrawn", [False, True])
def test_the_fork_folds_the_range_it_chose(claimed, withdrawn):
    """The fork chooses what to fold, with Leaf's range as a suggestion: here it keeps
    the opening message in full and folds past the suggestion's end, up to the
    agent's last answer, and Leaf writes that range. It does so though the
    suggestion's last message no longer stands, as when the user took it back."""
    opened, later, _, summary = summary_beside(claimed)
    basis_ = summary["basis"]
    assert (basis_["from"], basis_["through"]) == (opened["id"], later[-2]["id"])
    if withdrawn:
        summary = {**summary, "basis": {**basis_, "through": "taken-back"}}
    chosen = {"from": later[0]["id"], "through": later[-1]["id"]}
    outcome = summarized(summary, {**chosen, "text": "The TTL went to ten."})
    assert outcome["outcome"] == "summarized"
    assert summaries_written(claimed) == [
        (chosen["from"], chosen["through"], "The TTL went to ten.")
    ]
    [noted] = read_interactions(claimed, types=("summary_fork",))
    assert noted["suggested"] == {
        "from": basis_["from"],
        "through": summary["basis"]["through"],
    }
    assert (noted["from"], noted["through"]) == (chosen["from"], chosen["through"])


def test_the_fork_may_fold_nothing(claimed):
    """Where nothing compresses without losing wording the current exchange turns on,
    the fork folds nothing: Leaf writes no summary and hands the agent nothing."""
    *_, summary = summary_beside(claimed)
    assert summarized(summary, {"fold": False}) == {"outcome": "declined"}
    assert summaries_written(claimed) == []
    assert clerk_model.queued("s1") == []


@pytest.mark.parametrize("shape", ["the newest message", "backwards"])
def test_a_range_leaf_cant_take_hands_the_suggestion_to_the_agent(claimed, shape):
    """Leaf takes the fork's range only where it runs forward over the thread's spoken
    messages and ends before the user's newest messages, which the main session
    answers. Otherwise it writes nothing and hands the agent the suggested range."""
    opened, later, newest, summary = summary_beside(claimed)
    chosen = {
        "the newest message": {"from": opened["id"], "through": newest["id"]},
        "backwards": {"from": later[4]["id"], "through": later[2]["id"]},
    }[shape]
    outcome = summarized(summary, {**chosen, "text": "The fork's."})
    assert outcome["outcome"] == "failed"
    assert "its range" in outcome["why"]
    assert summaries_written(claimed) == []
    [handed] = clerk_model.queued("s1")
    basis_ = summary["basis"]
    assert f"`summary_hint` of {basis_['from']} through {basis_['through']}." in handed


def test_a_failed_summary_fork_hands_the_range_to_the_agent(claimed):
    """An answer Leaf can't take writes nothing, and the agent is told the range to
    summarize, so the thread's summary still has an owner."""
    *_, summary = summary_beside(claimed)
    outcome = summarized(summary, {"summary": "Not the answer's form."})
    assert outcome["outcome"] == "failed"
    [handed] = clerk_model.queued("s1")
    basis_ = summary["basis"]
    assert f"`summary_hint` of {basis_['from']} through {basis_['through']}." in handed
    assert summaries_written(claimed) == []


def test_a_summary_written_meanwhile_drops_the_forks_summary(claimed):
    """Leaf writes nothing where the fork's summary would no longer be in force, as
    when one written in the thread since replaces it."""
    *_, summary = summary_beside(claimed)
    basis_ = summary["basis"]
    thread_model.cmd_summarize(
        claimed, basis_["from"], basis_["through"], "The agent's."
    )
    answer = {
        "from": summary["basis"]["from"],
        "through": summary["basis"]["through"],
        "text": "The fork's.",
    }
    assert summarized(summary, answer) == {"outcome": "dropped"}
    assert "The fork's." not in [text for *_, text in summaries_written(claimed)]
    assert clerk_model.queued("s1") == []


def test_the_follower_reads_a_thread_a_version_reopened_as_the_fold_does(
    claimed, monkeypatch
):
    """A thread a widget's answer closed, which a later version takes back through
    an element containing the widget, waits again: the follower builds the page's
    threads with its containment, as the fold does, so both read the same message
    waiting."""
    events = events_model.read_events(claimed)
    seq = events[-1]["seq"] if events else 0
    ts = "2026-11-14T00:00:00+00:00"
    logged = [
        {"kind": "comment", "id": "contained-c1", "author": "user"}
        | {"text": "Tighten this section?"},
        {"kind": "action", "id": "contained-a1", "author": "user", "revision": 1}
        | {"widget": "w1", "action": "answer", "detail": {}}
        | {"meaning": {"unit": "w1", "answer": "contained-c1", "depends": ["sec1"]}},
        {"kind": "note", "id": "contained-n1", "author": "agent", "revision": 2}
        | {"restated": ["sec1"], "text": "Rewrote the section."},
    ]
    with (claimed / "events.jsonl").open("a", encoding="utf-8") as log:
        for offset, event in enumerate(logged, 1):
            log.write(json.dumps({**event, "seq": seq + offset, "ts": ts}) + "\n")
    monkeypatch.setattr(
        forks_model, "active_enclosing", lambda page_dir: {"sec1": ["w1"]}
    )
    assert listed(claimed) == [basis(claimed, "contained-c1", "contained-c1")]


def test_the_pages_follower_lists_a_line_fork_for_each_round_newer_than_itself(
    claimed, monkeypatch, capsys
):
    """The follower is the session's lane while it runs and lists a report for each
    round that awaits a line for the module, but none for a round older than its
    first look at the page, as one an earlier follower listed. It waits on the page's
    subscription, so a message wakes it as it is admitted rather than at the next
    presence read."""
    serving(claimed, 1)
    server_rows_model.RowPublisher(claimed, "fixture-server").refresh()
    older = said(claimed, "Asked before the follower started")
    asked = []
    waiting = file_changes_model.wait

    class Stopped(Exception):
        pass

    def wait(marks, _timeout):
        # A subscription a pass makes wakes those made before it once, and the
        # follower looks again.
        if waiting(marks, 0):
            return True
        if asked:
            raise Stopped
        assert leases_model.lane_up("s1")
        heard, generation = file_changes_model.page_changes(claimed.resolve())
        assert heard in [changes for changes, _generation in marks]
        # Notifications of the fixture's own writes may still arrive.
        while waiting([(heard, generation)], 0.2):
            generation = heard.mark()
        asked.append(said(claimed, "Is anyone forking?"))
        assert waiting([(heard, generation)], STATED_TIMEOUT), (
            "the message woke nothing"
        )
        return True

    monkeypatch.setattr(file_changes_model, "wait", wait)
    with pytest.raises(Stopped):
        hooks_model.cmd_pages(FOLLOWER)
    assert not leases_model.lane_up("s1")
    assert older["id"] in [round_["thread"] for round_ in listed(claimed)]
    shown = [json.loads(line)["do"] for line in capsys.readouterr().out.splitlines()]
    new = asked[0]["id"]
    assert shown[0] == []
    assert shown[1] == [
        {
            "id": f"line:{state_model.page_key(claimed)}:{new}",
            "do": "report",
            "basis": {"kind": "line", "thread": basis(claimed.resolve(), new, new)},
        }
    ]


@pytest.mark.parametrize("moved", ["protocol", "removed"])
def test_the_follower_ends_once_its_tree_moves_on_under_it(
    claimed, monkeypatch, capsys, moved
):
    """A follower runs as long as its session, while the tree it runs from can move
    on under it: a checkout Claude Code loads in place moved past a protocol bump, or
    a tree removed. The follower then ends, giving up the lane, with EX_TEMPFAIL for
    the module to start it again from the tree as it stands."""
    serving(claimed, 1)
    server_rows_model.RowPublisher(claimed, "fixture-server").refresh()
    monkeypatch.setattr(presence_model, "PRESENCE_CACHE_S", 0.0)
    waited = []

    def wait(_marks, _timeout):
        waited.append(True)
        return True

    monkeypatch.setattr(file_changes_model, "wait", wait)
    if moved == "protocol":
        monkeypatch.setattr(
            hooks_model,
            "installed_protocol",
            lambda: state_model.kernel_protocol() + len(waited),
        )
    else:
        launcher = state_model.PLUGIN_ROOT / "bin" / "leaf"
        access = os.access
        monkeypatch.setattr(
            hooks_model.os,
            "access",
            lambda path, mode: not (waited and path == launcher) and access(path, mode),
        )
    with pytest.raises(SystemExit) as ended:
        hooks_model.cmd_pages(FOLLOWER)
    assert ended.value.code == os.EX_TEMPFAIL
    assert not leases_model.lane_up("s1")
    [listed] = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert listed["do"] == []


def test_the_follower_keeps_open_the_subscription_of_every_page_it_holds(
    claimed, initialized_page, tmp_path, monkeypatch
):
    """Each page's subscription lives in the page's memory, and a process keeps
    the memories of only its most recent pages unless something holds them. The
    follower holds those of every page it waits on, since with more pages than
    that it would otherwise close its own subscriptions and wake at once, pass
    after pass."""
    for n in range(page_memory_model.PageMemories.LIMIT):
        transaction_model.claim_page(
            initialized_page(tmp_path / f"more-{n}", page_packages())
        )

    class Stopped(Exception):
        pass

    def wait(marks, _timeout):
        assert len(marks) > page_memory_model.PageMemories.LIMIT
        assert not any(changes.closed for changes, _generation in marks)
        raise Stopped

    monkeypatch.setattr(file_changes_model, "wait", wait)
    with pytest.raises(Stopped):
        hooks_model.cmd_pages(FOLLOWER)


def test_a_round_reads_as_it_arrived_whatever_the_agent_rewrites_later(claimed):
    """The follower and a delivery read a round as it stood when its newest message
    arrived, and no later write of the agent's moves that reading: rewriting its
    earlier answer twice across the user's messages leaves the round listed as it
    was, so its forks are asked once and the summary keeps one owner."""
    opened = said(claimed, "Which TTL should the cache use?")
    earlier = thread_model.post_reply(claimed, {"responds": opened["id"]}, "Ten s.")
    first = said(claimed, "Make it five.", parent=opened["id"])
    thread_model.cmd_edit(claimed, earlier["id"], "Five s.")
    second = said(claimed, "And the retries?", parent=opened["id"])
    arrived = [basis(claimed, opened["id"], first["id"], second["id"])]
    assert listed(claimed) == arrived
    thread_model.cmd_edit(claimed, earlier["id"], "Five s, and three retries.")
    assert listed(claimed) == arrived
