"""Reading a thread: `leaf thread read`, its summaries and the summary hint, and the
resolution events exact history and a wait share."""

import json

import pytest
from click.testing import CliRunner
from interact_support import (
    _interaction_prompt_evidence,
    append_carried_log_record,
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
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import hook_transport as hook_transport_model
from leaf import page_view as page_view_model
from leaf import session as session_model
from leaf import thread as thread_model
from leaf import thread_context as thread_context_model
from leaf.refusals import Refused


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
    assert reading["content"][1]["parent"] == messages[0]["id"]
    [move] = owed(reading)
    assert move["answer"] == {
        "kind": "reply",
        "to": messages[2]["id"],
        "for": messages[2]["id"],
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

    reversed_range = summarize(second["id"], root["id"])
    assert reversed_range.exit_code != 0
    assert "at least two messages in thread order" in reversed_range.output

    cross_thread = summarize(root["id"], neighbor["id"])
    assert cross_thread.exit_code != 0
    assert "endpoints must name spoken turns in one thread" in cross_thread.output

    reaction = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": third["id"],
            "token": "mark",
        },
    )
    standing_reaction_range = summarize(third["id"], reaction["id"])
    assert standing_reaction_range.exit_code != 0
    assert (
        "endpoints must name spoken turns in one thread"
        in standing_reaction_range.output
    )

    append_carried_log_record(
        page_dir,
        {"kind": "undo", "author": "user", "undoes": reaction["id"]},
    )
    withdrawn_range = summarize(third["id"], reaction["id"])
    assert withdrawn_range.exit_code != 0
    assert "endpoints must name spoken turns in one thread" in withdrawn_range.output

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
    assert (fold["label"], fold["text"], fold["covers"]) == (
        label if label is not None else "Earlier discussion",
        "",
        [root["id"], reply["id"]],
    )
    assert [message["text"] for message in thread["msgs"]] == [
        "Fix the layout.",
        "Checking the label row.",
    ]

    # Allowing an empty summary body must not admit an empty reply.
    with pytest.raises(Refused, match="empty text"):
        thread_model.post_reply(page_dir, {"to": root["id"], "for": root["id"]}, "")


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


def test_summary_hint_does_not_cross_a_fold_of_ephemeral_updates(page_dir):
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "x" * 1000}
    )
    updates = [
        append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": root["id"],
                "text": "Checking details.",
                "ephemeral": True,
            },
        )
        for _ in range(2)
    ]
    older = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "agent", "parent": root["id"], "text": "y" * 1000},
    )
    for author in ("agent", "user"):
        latest = append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": author, "parent": root["id"], "text": "Next?"},
        )
    within = page_view_model.PageView(page_dir).within
    events = events_model.read_events(page_dir)
    update_ids = {update["id"] for update in updates}
    [unfolded] = thread_context_model.batch_threads(
        [event for event in events if event["id"] not in update_ids], [latest], within
    )
    assert unfolded["summary_hint"] == {"from": root["id"], "through": older["id"]}
    [folded] = thread_context_model.batch_threads(events, [latest], within)
    assert folded["summaries"][0]["covers"] == [update["id"] for update in updates]
    assert "summary_hint" not in folded


def test_summary_hint_chooses_a_qualifying_run_over_more_short_messages(page_dir):
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "x" * 1000}
    )
    long_reply = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "agent", "parent": root["id"], "text": "y" * 1000},
    )
    for _ in range(2):
        append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": root["id"],
                "text": "Checking details.",
                "ephemeral": True,
            },
        )
    # Three short older messages form a longer run, but the earlier two long
    # messages are the only run that qualifies for a suggestion.
    for author in ("agent", "user", "agent", "agent", "user"):
        latest = append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": author, "parent": root["id"], "text": "Next?"},
        )
    [digest] = thread_context_model.batch_threads(
        events_model.read_events(page_dir),
        [latest],
        page_view_model.PageView(page_dir).within,
    )
    assert digest["summary_hint"] == {"from": root["id"], "through": long_reply["id"]}


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
        {"to": current["id"], "for": current["id"]},
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
    # The event carries the ask as well as the digest, so an agent that reads only
    # what is new can still choose whether to summarize the older discussion.
    [event] = batch["events"]
    assert any("summary_hint" in batch["handling"][h] for h in event["handling"])
    snapshot.check(
        yaml_document(
            "The summary hint from real thread events and the delivery an explicit wait prints.",
            _interaction_prompt_evidence(page_dir, {"delivery": envelope}),
        )
    )
