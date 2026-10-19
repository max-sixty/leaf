"""Complete trajectories and fixed evidence contracts survive partial execution."""

import json
import os

import click
import pytest


def test_partial_native_traces_do_not_report_zero_elapsed_minutes(tmp_path):
    from leaf_dev.arms import trace_summary

    stream = tmp_path / "stream.jsonl"
    for trace, minutes in (
        ([], None),
        ([{"type": "result", "is_error": False}], None),
        ([{"type": "result", "is_error": False, "duration_ms": 2700000}], 45),
    ):
        stream.write_text("".join(json.dumps(record) + "\n" for record in trace))
        assert trace_summary(trace)["minutes"] == minutes


def test_success_readers_require_the_same_exact_agent_answer(tmp_path):
    from leaf.thread import answered_by_reply, successful_replies
    from leaf_dev import review_scenario
    from leaf_dev.commands import journey

    comment = {
        "kind": "comment",
        "author": "user",
        "id": "input",
    }
    answer = {
        "kind": "reply",
        "author": "agent",
        "seq": 2,
        "parent": "root",
        "responds": comment["id"],
        "text": "Checked",
    }
    for changes, success in (
        ({}, True),
        ({"ephemeral": True}, False),
        ({"failure": "turn_failed"}, False),
        ({"parent": "input", "responds": "later-input"}, False),
        ({"parent": "input", "responds": None}, False),
        ({"author": "user"}, False),
        ({"kind": "comment"}, False),
    ):
        reply = {**answer, **changes}
        events = [comment, reply]
        expected = [reply] if success else []
        (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
        assert successful_replies(events, "input") == expected
        assert answered_by_reply(events, "input") is success
        assert review_scenario.answers(tmp_path, "input") == expected
        assert journey.deployment_answer(events, "input") == (
            reply if success else None
        )


def test_live_round_receipts_require_exact_admitted_user_inputs():
    from leaf_dev.arms import inputs_received

    events = [
        {"id": "first", "kind": "comment", "attempt": "round-1", "attention": True},
        {"id": "second", "kind": "action", "attempt": "round-2", "attention": True},
        {"id": "error", "kind": "error"},
        {"kind": "pickup", "phase": "opened", "events": ["other"]},
        {"kind": "pickup", "phase": "queued", "events": ["first", "second"]},
        {"kind": "pickup", "phase": "failed", "events": ["first", "second"]},
    ]
    assert inputs_received(events, set())
    assert not inputs_received(events, {"unadmitted"})
    assert not inputs_received(events, {"round-1", "round-2"})
    events.append({"kind": "pickup", "phase": "opened", "events": ["first"]})
    assert inputs_received(events, {"round-1"})
    assert not inputs_received(events, {"round-1", "round-2"})
    events.append({"kind": "pickup", "phase": "opened", "events": ["second"]})
    assert inputs_received(events, {"round-1", "round-2"})


@pytest.mark.parametrize("phase", ["queued", "opened", "failed"])
def test_settled_requires_context_entry_even_with_a_reply_and_closed_turn(
    page_dir, phase
):
    """Reply success and session closure cannot substitute for delivery receipt."""
    from interact_support import stamp
    from leaf.delivery import opened_input_ids, pickup_receipts, record_pickup
    from leaf.event_contracts import append_admitted
    from leaf.harness import EmbeddedHarness
    from leaf.service import PageTransaction
    from leaf.state import close_session_turn
    from leaf_dev.review_scenario import settled

    stamped = stamp(page_dir)
    assert stamped.exit_code == 0, stamped.output
    session = "receipt-reader"
    with PageTransaction(page_dir) as page:
        page.take_claim(
            EmbeddedHarness(session=session, agent="Reader", pid=os.getpid())
        )
        comment, _ = append_admitted(
            page,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "Which items block?",
                "anchor": {"section": "plan"},
            },
        )
        receipt = record_pickup(
            page,
            [comment],
            phase=phase,
            session=session,
            failure="delivery_failed" if phase == "failed" else None,
        )
        append_admitted(
            page,
            {
                "kind": "reply",
                "author": "agent",
                "revision": 1,
                "parent": comment["id"],
                "responds": comment["id"],
                "text": "The migration.",
            },
        )
        events = list(page.events)
    close_session_turn(session)
    # The shared reading preserves provenance and the entire batch for consumers
    # that check context entry, its timing, its turn or one-delivery coverage.
    assert pickup_receipts(events, phase=phase, input_id=comment["id"]) == [receipt]
    assert pickup_receipts(events, phase=phase, input_id="other") == []
    assert pickup_receipts(events, phase=None, input_id=comment["id"]) == [receipt]
    assert pickup_receipts(events, phase=None, input_id="other") == []
    assert opened_input_ids(events) == ({comment["id"]} if phase == "opened" else set())
    if phase == "opened":
        assert settled(page_dir, session, {"idle": comment["id"]})["turn_closed"]
    else:
        with pytest.raises(
            click.ClickException, match="never entered the harness context"
        ):
            settled(page_dir, session, {"idle": comment["id"]})


def test_journey_timing_reports_context_entry_after_queue_acceptance():
    from leaf_dev.commands.journey import User

    comment = {
        "kind": "comment",
        "id": "input",
        "author": "user",
        "ts": "2026-10-08T12:00:00-07:00",
    }
    events = [comment]
    for phase, second, input_id in [
        ("queued", 1, "input"),
        ("failed", 2, "input"),
        ("opened", 3, "other"),
        ("opened", 4, "input"),
    ]:
        events.append(
            {
                "kind": "pickup",
                "id": f"pickup-{second}",
                "phase": phase,
                "events": [input_id],
                "session": "reader",
                "turn": "turn",
                "ts": f"2026-10-08T12:00:0{second}-07:00",
            }
        )
    events.append(
        {
            "kind": "reply",
            "id": "answer",
            "author": "agent",
            "parent": "input",
            "responds": "input",
            "text": "Done",
            "ts": "2026-10-08T12:00:05-07:00",
        }
    )
    user = User(None, "version", lambda: events)
    user.ids["idle"] = "input"
    assert user.timing("idle") == "`idle` picked up after 4.0 s, answered after 5 s"


def test_delivery_workload_keeps_unanswered_inputs_at_cutoff(tmp_path):
    """Failed/late replies stay missing, and unrelated setup asks stay outside the cohort."""
    from datetime import UTC, datetime

    def at(second):
        return datetime(2026, 10, 8, 9, 0, second, tzinfo=UTC).isoformat()

    from leaf.event_log import append_event
    from leaf_dev.delivery_eval import capture_measurements

    for identity, second in [("setup", 0), ("known", 1), ("steer", 2)]:
        append_event(
            tmp_path,
            {
                "kind": "comment",
                "id": identity,
                "ts": at(second),
                "author": "user",
                "attention": True,
                "text": identity,
            },
        )
    for identity, parent, second in [("answer", "known", 4), ("late", "steer", 25)]:
        append_event(
            tmp_path,
            {
                "kind": "reply",
                "id": identity,
                "parent": parent,
                "responds": parent,
                "ts": at(second),
                "author": "agent",
                "attention": False,
            },
        )
    result = capture_measurements(
        tmp_path,
        [{"input_id": "known"}, {"input_id": "steer"}, {"input_id": "unrecorded"}],
        datetime(2026, 10, 8, 9, 0, 20, tzinfo=UTC),
    )
    assert [row["input_id"] for row in result["samples"]] == [
        "known",
        "steer",
        "unrecorded",
    ]
    assert result["unrecorded_inputs"] == ["unrecorded"]
    assert result["first_reply"]["observed"] == 1
    assert result["first_reply"]["inputs"] == 3
    assert result["first_reply"]["missing"] == 2
    assert result["samples"][2]["observed_for_s"] is None
    assert result["samples"][1]["observed_for_s"] == 18
    assert result["samples"][0]["milestones"]["first_reply"]["elapsed_s"] == 3
