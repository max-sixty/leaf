"""Reading a thread: `leaf thread read`, its summaries and the summary hint, and the
resolution events exact history and a wait share."""

import json

import pytest
from click.testing import CliRunner
from interact_support import (
    _interaction_prompt_evidence,
    append_carried_log_record,
    command_findings,
    consume_pending_input,
    delivered,
    last_deliverable_seq,
    owed,
    page_state,
    publish,
    receive_through,
    served_thread,
    serving,
    yaml_document,
)

from leaf.agents import thread as thread_model
from leaf.base.refusals import Refused
from leaf.commands import cli as cli_model
from leaf.commands import hook_transport as hook_transport_model
from leaf.commands import session as session_model
from leaf.log import event_log as events_model
from leaf.log import thread_context as thread_context_model
from leaf.records import page_view as page_view_model


def test_thread_read_is_exact_and_paginated(page_dir):
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "selected", "author": "user", "text": "one"},
    )
    parent = root["id"]
    messages = [root]
    for author, text in (("agent", "two"), ("user", "three")):
        message = append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": author, "parent": parent, "text": text},
        )
        messages.append(message)
        parent = message["id"]
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "neighbor", "author": "user", "text": "else"},
    )

    first = CliRunner().invoke(
        cli_model.cli,
        ["page", "state", str(page_dir), root["id"], "--limit", "2"],
    )
    assert first.exit_code == 0, first.output
    reading = json.loads(first.output)
    assert reading["thread"]["id"] == root["id"]
    assert "threads" not in reading
    assert "neighbor" not in first.output
    assert [item["message"] for item in reading["content"]] == [
        messages[0]["id"],
        messages[1]["id"],
    ]
    assert [item["author"] for item in reading["content"]] == ["user", "agent"]
    # When each was said, as the thread shows it beside the message.
    assert [item["ts"] for item in reading["content"]] == [
        messages[0]["ts"],
        messages[1]["ts"],
    ]
    assert reading["content"][1]["parent"] == messages[0]["id"]
    [move] = owed(reading)
    assert move["answer"] == {
        "kind": "reply",
        "parent": messages[2]["id"],
        "responds": messages[2]["id"],
    }
    second_seq = reading["content"][1]["source"]["seq"]
    assert reading["history"]["next_after"] == second_seq

    second = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "state",
            str(page_dir),
            root["id"],
            "--after",
            str(second_seq),
            "--limit",
            "2",
        ],
    )
    assert second.exit_code == 0, second.output
    continued = json.loads(second.output)
    assert [item["message"] for item in continued["content"]] == [messages[2]["id"]]
    assert continued["content"][0]["author"] == "user"
    assert continued["content"][0]["parent"] == messages[1]["id"]
    assert continued["history"]["next_after"] is None


def test_a_page_threads_later_readings_keep_what_the_user_had_on_screen(page_dir):
    """A page comment's "this one" points into the sections it records as `viewing`
    (events.md, "Anchors"). The delivery that carries the comment shows the event
    whole; a later one shows it only as the thread's opening message, and so does
    `page state`, so both keep the field there."""
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "text": "Drop this one",
            "viewing": ["results"],
        },
    )
    answer = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "agent", "parent": root["id"], "text": "Gone."},
    )
    latest = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": answer["id"], "text": "Thanks"},
    )

    [digest] = thread_context_model.batch_threads(
        events_model.read_events(page_dir),
        [latest],
        page_view_model.PageView(page_dir).within,
    )
    reading = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), root["id"]]
    )
    assert reading.exit_code == 0, reading.output
    assert digest["anchor"] is None
    assert digest["messages"][0]["viewing"] == ["results"]
    assert json.loads(reading.output)["content"][0]["viewing"] == ["results"]


def test_thread_summary_is_admitted_as_one_ordered_thread_range(page_dir):
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "one"},
    )
    internal_reaction = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": root["id"], "token": "mark"},
    )
    second = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": root["id"], "text": "two"},
    )
    third = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": second["id"], "text": "three"},
    )
    neighbor = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "elsewhere"},
    )

    def summarize(
        start: str,
        end: str,
        text: str = "The first exchange.",
    ):
        return CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "summarize",
                str(page_dir),
                "--from",
                start,
                "--through",
                end,
                "--text",
                text,
            ],
        )

    def refused(start: str, end: str) -> str:
        [finding] = command_findings(
            "thread",
            "summarize",
            page_dir,
            "--from",
            start,
            "--through",
            end,
            "--text",
            "The first exchange.",
        )
        return finding.code

    assert refused(second["id"], root["id"]) == "summary-order"
    assert refused(root["id"], neighbor["id"]) == "summary-endpoints"

    reaction = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": third["id"],
            "token": "mark",
        },
    )
    assert refused(third["id"], reaction["id"]) == "summary-endpoints"

    append_carried_log_record(
        page_dir,
        {"kind": "undo", "author": "user", "undoes": reaction["id"]},
    )
    assert refused(third["id"], reaction["id"]) == "summary-endpoints"

    # One message is a range too; the next summary overlaps it and replaces it.
    alone = summarize(second["id"], second["id"])
    assert alone.exit_code == 0, alone.output

    described = summarize(second["id"], third["id"])
    assert described.exit_code == 0, described.output
    assert json.loads(described.output)["through"] == third["id"]

    accepted = summarize(root["id"], second["id"])
    assert accepted.exit_code == 0, accepted.output
    summary = json.loads(accepted.output)
    assert {
        key: summary[key] for key in ("kind", "thread", "from", "through", "text")
    } == {
        "kind": "summary",
        "thread": root["id"],
        "from": root["id"],
        "through": second["id"],
        "text": "The first exchange.",
    }

    read = CliRunner().invoke(
        cli_model.cli,
        ["page", "state", str(page_dir), root["id"]],
    )
    assert read.exit_code == 0, read.output
    [projected] = json.loads(read.output)["thread"]["summaries"]
    assert projected["id"] == summary["id"]
    assert projected["covers"] == [
        root["id"],
        internal_reaction["id"],
        second["id"],
    ]
    browser_thread = served_thread(page_state(page_dir)["browser"])["threads"][0]
    assert [message["id"] for message in browser_thread["msgs"]] == [
        root["id"],
        internal_reaction["id"],
        second["id"],
        third["id"],
    ]
    # The agent reads the summary the user is shown, which messages it leaves in view
    # included.
    assert browser_thread["summaries"] == [projected]


def test_the_agents_edit_leaves_its_summary_standing_and_names_it(page_dir):
    """Only the agent knows whether its edit changes what a summary reports, so the
    summary folding the message stands, and the edit names it and the range to
    summarize again."""
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Which cache?"}
    )
    reply = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "text": "LRU, capped at 100.",
        },
    )
    summary = thread_model.cmd_summarize(
        page_dir, root["id"], reply["id"], "Settled on LRU."
    )
    edited = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "edit",
            str(page_dir),
            reply["id"],
            "--text",
            "LRU, capped at 1,000.",
        ],
    )
    assert edited.exit_code == 0, edited.output
    [named] = json.loads(edited.output)["findings"]
    assert (named["code"], named["severity"]) == ("edit-under-summary", "advice")
    assert summary["id"] in named["text"] and "leaf thread summarize" in named["text"]
    read = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), root["id"]]
    )
    assert [s["text"] for s in json.loads(read.output)["thread"]["summaries"]] == [
        "Settled on LRU."
    ]


def test_a_summary_folds_the_range_its_agent_names(page_dir):
    """Admission takes the range the agent names, though older discussion stays in
    full above it: which messages the user still needs in full is the agent's to
    judge (`references/threads.md`, "Summarize a long discussion")."""
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Plan the rollout."}
    )
    _first, second, third = (
        append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": author, "parent": root["id"], "text": text},
        )
        for author, text in (
            ("agent", "Two regions first."),
            ("user", "Which two?"),
            ("agent", "East and west."),
        )
    )
    findings = command_findings(
        "thread",
        "summarize",
        page_dir,
        "--from",
        second["id"],
        "--through",
        third["id"],
        "--text",
        "The regions.",
    )
    assert findings == []
    read = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), root["id"]]
    )
    assert read.exit_code == 0, read.output
    [summary] = json.loads(read.output)["thread"]["summaries"]
    assert summary["covers"] == [second["id"], third["id"]]


@pytest.mark.parametrize("start", [1, 2], ids=["from-its-start", "from-inside-it"])
def test_a_summary_replaces_whole_the_summaries_it_overlaps(page_dir, start):
    """A summary replaces those it overlaps whole, so one that ends inside an earlier
    summary uncovers that summary's tail, which the thread then shows in full."""
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Start."}
    )
    m = [root["id"]] + [
        append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent" if number % 2 else "user",
                "parent": root["id"],
                "text": f"m{number}",
            },
        )["id"]
        for number in range(1, 13)
    ]

    def summarize(first: str, last: str) -> list:
        return command_findings(
            "thread",
            "summarize",
            page_dir,
            "--from",
            first,
            "--through",
            last,
            "--text",
            "Earlier.",
        )

    assert summarize(m[1], m[5]) == []
    assert summarize(m[6], m[10]) == []
    assert summarize(m[start], m[3]) == []
    read = CliRunner().invoke(cli_model.cli, ["page", "state", str(page_dir), m[0]])
    assert read.exit_code == 0, read.output
    summaries = json.loads(read.output)["thread"]["summaries"]
    covered = [identity for summary in summaries for identity in summary["covers"]]
    assert covered == m[start:4] + m[6:11]


@pytest.mark.parametrize("label", [None, "Previous progress messages"])
def test_summary_cli_can_fold_without_prose_only_when_explicit(page_dir, label):
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Fix the layout."}
    )
    reply = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "text": "Checking the label row.",
        },
    )
    command = [
        "thread",
        "summarize",
        str(page_dir),
        "--from",
        root["id"],
        "--through",
        reply["id"],
    ]
    if label is not None:
        command.extend(["--label", label])

    missing = CliRunner().invoke(cli_model.cli, command)
    assert missing.exit_code != 0
    assert "empty text" in missing.output

    result = CliRunner().invoke(cli_model.cli, [*command, "--text", ""])
    assert result.exit_code == 0, result.output
    event = json.loads(result.output)
    assert event["text"] == ""
    if label is None:
        assert "label" not in event
    else:
        assert event["label"] == label
    read = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), root["id"]]
    )
    assert read.exit_code == 0, read.output
    [agent_fold] = json.loads(read.output)["thread"]["summaries"]
    [thread] = served_thread(page_state(page_dir)["browser"])["threads"]
    [fold] = thread["summaries"]
    assert fold == agent_fold
    assert (fold.get("label"), fold["text"], fold["covers"]) == (
        label,
        "",
        [root["id"], reply["id"]],
    )
    assert [message["text"] for message in thread["msgs"]] == [
        "Fix the layout.",
        "Checking the label row.",
    ]

    # Allowing an empty summary body must not admit an empty reply.
    with pytest.raises(Refused, match="empty text"):
        thread_model.post_reply(
            page_dir, {"parent": root["id"], "responds": root["id"]}, ""
        )


def test_summary_hint_keeps_the_latest_spoken_exchange_outside_reactions(page_dir):
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "turn 1"},
    )
    spoken = [root]
    for number in range(2, 5):
        spoken.append(
            append_carried_log_record(
                page_dir,
                {
                    "kind": "reply",
                    "author": "user" if number % 2 else "agent",
                    "parent": root["id"],
                    "text": f"turn {number}",
                },
            )
        )
    middle_reaction = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": root["id"], "token": "mark"},
    )
    for number in range(5, 7):
        spoken.append(
            append_carried_log_record(
                page_dir,
                {
                    "kind": "reply",
                    "author": "user" if number % 2 else "agent",
                    "parent": root["id"],
                    "text": f"turn {number}",
                },
            )
        )
    trailing_reaction = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": root["id"], "token": "mark"},
    )
    events = events_model.read_events(page_dir)
    latest = next(event for event in events if event["id"] == spoken[-1]["id"])

    [digest] = thread_context_model.batch_threads(
        events,
        [latest],
        page_view_model.PageView(page_dir).within,
    )

    assert digest["summary_hint"] == {
        "from": spoken[0]["id"],
        "through": spoken[3]["id"],
    }
    assert digest["summary_hint"]["through"] not in {
        middle_reaction["id"],
        trailing_reaction["id"],
    }


def test_summary_hint_passes_over_progress(page_dir):
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "x" * 1000}
    )
    progress = {
        "kind": "reply",
        "author": "agent",
        "parent": root["id"],
        "text": "Checking details.",
        "ephemeral": True,
    }
    append_carried_log_record(page_dir, progress)
    append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "agent", "parent": root["id"], "text": "y" * 1000},
    )
    # A user who keeps writing while the agent is mid-work leaves a step standing
    # among spoken turns old enough to suggest, which the run passes over too.
    append_carried_log_record(page_dir, progress)
    said = [
        append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": "user", "parent": root["id"], "text": "Next?"},
        )
        for _ in range(4)
    ]
    [digest] = thread_context_model.batch_threads(
        events_model.read_events(page_dir),
        [said[-1]],
        page_view_model.PageView(page_dir).within,
    )
    assert digest["summaries"] == []
    # The newest exchange stays whole.
    assert digest["summary_hint"] == {"from": root["id"], "through": said[1]["id"]}


def test_summary_hint_leaves_no_older_discussion_above_it(page_dir):
    """Were a step mid-thread to split the earlier discussion into runs, a hint that
    took the longest would leave the older run in full above the summary."""
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Plan the rollout."}
    )
    spoken = [root]

    def say(author, text, **extra):
        return append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": author,
                "parent": root["id"],
                "text": text,
                **extra,
            },
        )

    spoken.append(say("agent", "First pass."))
    say("agent", "Checking the config.", ephemeral=True)
    for number in range(8):
        spoken.append(say("user" if number % 2 else "agent", f"Detail {number}."))
    [digest] = thread_context_model.batch_threads(
        events_model.read_events(page_dir),
        [spoken[-1]],
        page_view_model.PageView(page_dir).within,
    )
    assert digest["summary_hint"] == {
        "from": root["id"],
        "through": spoken[-3]["id"],
    }


@pytest.mark.parametrize(
    ("reply_text", "widened"),
    [
        pytest.param("y" * 1000, False, id="older-run-long-enough"),
        pytest.param("Short.", True, id="older-run-too-short"),
    ],
)
def test_a_summary_hint_takes_in_a_run_left_in_full_above_a_summary(
    page_dir, reply_text, widened
):
    """A hint never leaves older discussion in full above a summary, though the agent
    may summarize a later run and keep an earlier one in full. Where that run is
    long enough, the hint names it and the later summary. Where it is too short, the
    hint names the next long-enough run widened over it, so a short stretch left above
    a summary doesn't stop every later hint. Either way the hint replaces the later
    summary, and following it leaves the thread one summary."""
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "x" * 1000}
    )

    def say(author, text):
        return append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": author, "parent": root["id"], "text": text},
        )

    reply = say("agent", reply_text)
    folded = [say("agent", "z") for _ in range(2)]
    later = thread_model.cmd_summarize(page_dir, folded[0]["id"], folded[-1]["id"], "")
    newer = [
        say(author, "Next?")
        for author in ("agent", "user", "agent", "agent", "user", "agent", "user")
    ]
    [digest] = thread_context_model.batch_threads(
        events_model.read_events(page_dir),
        [newer[-1]],
        page_view_model.PageView(page_dir).within,
    )
    assert [summary["id"] for summary in digest["summaries"]] == [later["id"]]
    hint = digest["summary_hint"]
    if widened:
        assert hint == {"from": reply["id"], "through": newer[4]["id"]}
    else:
        assert hint == {"from": root["id"], "through": folded[-1]["id"]}
    assert (
        command_findings(
            "thread",
            "summarize",
            page_dir,
            "--from",
            hint["from"],
            "--through",
            hint["through"],
            "--text",
            "Earlier.",
        )
        == []
    )
    read = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), root["id"]]
    )
    assert read.exit_code == 0, read.output
    assert [s["text"] for s in json.loads(read.output)["thread"]["summaries"]] == [
        "Earlier."
    ]


def test_a_summary_hint_spans_the_summaries_above_its_run(page_dir):
    """A thread summarized once and grown long again is offered one range from its
    earlier summary through the new run, so following each hint leaves one summary
    of the earlier discussion rather than a row of them. It takes in a fold of
    progress alone, and starts on a message the thread still says, though the user
    took back the first message an earlier summary named."""
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Plan the rollout."}
    )
    spoken = [root]

    def say(author, parent=root):
        spoken.append(
            append_carried_log_record(
                page_dir,
                {
                    "kind": "reply",
                    "author": author,
                    "parent": parent["id"],
                    "text": f"Detail {len(spoken)}.",
                },
            )
        )

    progress = [
        append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": root["id"],
                "text": "Checking.",
                "ephemeral": True,
            },
        )
        for _ in range(2)
    ]
    thread_model.cmd_summarize(page_dir, progress[0]["id"], progress[-1]["id"], "")
    say("user")
    # A reply to it keeps the message in its place once the user takes it back, and
    # a fold without prose outlives that.
    say("agent", parent=spoken[1])
    for author in ("user", "agent"):
        say(author)
    thread_model.cmd_summarize(page_dir, spoken[1]["id"], spoken[4]["id"], "")
    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": spoken[1]["id"]}
    )
    for author in ("user", "agent", "user", "agent", "user", "agent"):
        say(author)

    [digest] = thread_context_model.batch_threads(
        events_model.read_events(page_dir),
        [spoken[-1]],
        page_view_model.PageView(page_dir).within,
    )
    assert digest["summary_hint"] == {
        "from": progress[0]["id"],
        "through": spoken[-3]["id"],
    }

    thread_model.cmd_summarize(
        page_dir, progress[0]["id"], spoken[-3]["id"], "All of it."
    )
    read = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), root["id"]]
    )
    assert read.exit_code == 0, read.output
    [summary] = json.loads(read.output)["thread"]["summaries"]
    assert summary["text"] == "All of it."


def test_a_summary_hint_replaces_whole_the_summaries_it_reaches_into(page_dir):
    """The hint stops short of the newest exchange, so it may end inside a summary
    that reaches into it. A summary replaces that one whole, so the hint is widened
    over the messages it uncovers, and following it leaves no gap."""
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "x" * 1000}
    )

    def say(author, text="Next?", **extra):
        return append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": author,
                "parent": root["id"],
                "text": text,
                **extra,
            },
        )

    first = say("agent", "y" * 1000)
    m = [root, first, *(say(author) for author in ("user", "agent", "user", "agent"))]
    m.append(say("user"))
    progress = say("agent", "Checking.", ephemeral=True)
    # The agent keeps the opening's two long messages in full, leaving them to suggest.
    thread_model.cmd_summarize(page_dir, m[2]["id"], m[5]["id"], "The middle.")
    thread_model.cmd_summarize(page_dir, m[6]["id"], progress["id"], "")

    [digest] = thread_context_model.batch_threads(
        events_model.read_events(page_dir),
        [m[-1]],
        page_view_model.PageView(page_dir).within,
    )
    hint = digest["summary_hint"]
    assert hint == {"from": root["id"], "through": m[5]["id"]}
    thread_model.cmd_summarize(page_dir, hint["from"], hint["through"], "Earlier.")
    read = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), root["id"]]
    )
    assert read.exit_code == 0, read.output
    summaries = json.loads(read.output)["thread"]["summaries"]
    assert [summary["text"] for summary in summaries] == ["Earlier.", ""]


@pytest.mark.parametrize(
    ("older_texts", "suggested"),
    [
        pytest.param(["x" * 2000], False, id="one-message-is-too-few"),
        pytest.param(["x" * 1000, "x" * 999], False, id="below-character-threshold"),
        pytest.param(["x" * 1000, "x" * 1000], True, id="two-long-messages"),
        pytest.param(["Earlier detail."] * 3, False, id="three-short-messages"),
        pytest.param(["Earlier detail."] * 4, True, id="four-short-messages"),
    ],
)
def test_summary_suggestions_only_accompany_new_input(claimed, older_texts, suggested):
    publish(claimed)
    root = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": older_texts[0]}
    )
    older = [root]
    for number, text in enumerate(older_texts[1:], start=1):
        older.append(
            append_carried_log_record(
                claimed,
                {
                    "kind": "reply",
                    "author": "agent" if number % 2 else "user",
                    "parent": root["id"],
                    "text": text,
                },
            )
        )
    updates = [
        append_carried_log_record(
            claimed,
            {
                "kind": "reply",
                "author": "agent",
                "parent": root["id"],
                "text": "Checking the rollout details." * 100,
                "ephemeral": True,
            },
        )
        for _ in range(2)
    ]
    previous = append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "text": "The newest exchange stays readable." * 100,
        },
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    assert not any(plan.batch for plan in hook_transport_model.read_plans("s1"))

    current = append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "user",
            "parent": root["id"],
            "text": "What do you recommend now?" * 100,
        },
    )
    payload = consume_pending_input("s1")
    [batch] = payload["batches"]
    assert [event["id"] for event in batch["events"]] == [current["id"]]
    [thread] = batch["threads"]
    assert {
        message["id"] for message in thread["messages"] if message.get("ephemeral")
    } == {update["id"] for update in updates}
    assert ("summary_hint" in thread) is suggested
    if suggested:
        assert thread["summary_hint"] == {
            "from": older[0]["id"],
            "through": older[-1]["id"],
        }
        assert previous["id"] != thread["summary_hint"]["through"]
    assert consume_pending_input("s1") is None

    # An answer clears the response obligation even when the agent leaves the
    # optional suggestion alone. It produces no separate summary delivery.
    thread_model.post_reply(
        claimed,
        {"parent": current["id"], "responds": current["id"]},
        "Proceed with the rollout.",
    )
    assert not any(plan.batch for plan in hook_transport_model.read_plans("s1"))
    [plan] = hook_transport_model.read_plans("s1")
    assert not plan.owed
    assert plan.state["activity"]["obligations"] == []


def test_agent_sees_a_real_summary_suggestion(page_dir, capsys, snapshot):
    publish(page_dir)
    serving(page_dir, 1)
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Which rollout?"}
    )
    for number in range(1, 5):
        append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent" if number % 2 else "user",
                "parent": root["id"],
                "text": f"Rollout consideration {number}.",
            },
        )
    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root["id"],
            "text": "What do you recommend now?",
        },
    )
    assert session_model.cmd_wait(page_dir) == 0
    payload, _, _ = delivered(capsys)
    envelope = json.loads(json.dumps(payload).replace(payload["id"], "<delivery>"))
    [batch] = envelope["batches"]
    assert batch["threads"][0]["summary_hint"]
    # The event carries the obligation as well as the digest, so an agent that reads only
    # what is new can still choose whether to summarize the older discussion.
    [event] = batch["events"]
    assert any("summary_hint" in batch["handling"][h] for h in event["handling"])
    snapshot.check(
        yaml_document(
            "The summary hint from real thread events and the delivery an explicit wait prints.",
            _interaction_prompt_evidence(page_dir, {"delivery": envelope}),
        )
    )
