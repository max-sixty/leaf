"""Complete trajectories and fixed evidence contracts survive partial execution."""

import json
import os

import click
import pytest
from leaf_dev.delivery_eval import expected_checks, grade, score


def test_partial_native_traces_do_not_report_zero_elapsed_minutes(tmp_path):
    from leaf_dev import usability_eval
    from leaf_dev.arms import trace_summary

    stream = tmp_path / "stream.jsonl"
    for trace, minutes in (
        ([], None),
        ([{"type": "result", "is_error": False}], None),
        ([{"type": "result", "is_error": False, "duration_ms": 2700000}], 45),
    ):
        stream.write_text("".join(json.dumps(record) + "\n" for record in trace))
        assert trace_summary(trace)["minutes"] == minutes
        assert usability_eval.trace_scores(trace)["minutes"] == minutes


def test_delivery_requires_every_comment_and_a_completed_session():
    complete = {
        "comment": 1,
        "injection": "running",
        "active_turn": "setup-turn",
        "after_completion": False,
        "timed_out": False,
        "turn_completed": True,
        "session_completed": True,
        "pickup_s": 0,
        "claim_s": 0,
        "reply_s": 0,
        "turn_s": 0,
    }
    assert all(grade("mid-turn", [complete]).values())
    for partial in [
        [],
        [{**complete, "timed_out": True}],
        [{**complete, "turn_completed": False}],
        [{**complete, "session_completed": False}],
        [{**complete, "comment": None}],
        [complete, complete],
    ]:
        checks = grade("mid-turn", partial)
        assert set(checks) == set(expected_checks("mid-turn"))
        assert not checks["completed"]
    assert not grade("idle", [complete])["completed"]
    idle = {
        **complete,
        "injection": "idle",
        "active_turn": None,
        "after_completion": True,
    }
    assert all(grade("idle", [idle, {**idle, "comment": 2}]).values())
    assert not grade("mid-turn", [idle])["injected-as-requested-1"]
    assert not grade("mid-turn", [{**complete, "after_completion": True}])[
        "injected-as-requested-1"
    ]
    assert not grade("mid-turn", [{**complete, "reply_s": None}])["replied-1"]
    assert not grade("mid-turn", [{**complete, "claim_s": None}])["claimed-1"]


def test_delivery_reads_admitted_progress_and_exact_answers(tmp_path):
    """Slow stream observation and shell failures leave admitted work intact."""
    events = [
        {
            "kind": "comment",
            "id": "comment",
            "author": "user",
            "attempt": "delivery-eval-0001-attempt",
            "ts": "2026-10-02T00:00:00Z",
        },
        {
            "kind": "pickup",
            "phase": "opened",
            "events": ["comment"],
            "ts": "2026-10-02T00:00:01Z",
        },
        {
            "kind": "start",
            "item": "comment",
            "turn": "handling",
            "text": "Editing",
            "ts": "2026-10-02T00:00:02Z",
        },
        {
            "kind": "reply",
            "author": "agent",
            "parent": "root",
            "responds": "comment",
            "text": "Done",
            "ts": "2026-10-02T00:00:03Z",
        },
    ]
    records = [
        {
            "type": "eval_post",
            "round": 1,
            "injection": "running",
            "active_turn": "setup",
            "received_at": "2026-10-02T00:00:00Z",
        },
        {
            "type": "system",
            "subtype": "hook_response",
            "hook_event": "UserPromptSubmit",
            "output": "leaf-delivery-v",
            "received_at": "2026-10-02T00:00:04Z",
        },
        {
            "type": "result",
            "turn_id": "handling",
            "is_error": False,
            "received_at": "2026-10-02T00:00:05Z",
        },
    ]

    def checks(log=events):
        (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in log))
        (tmp_path / "stream-1.jsonl").write_text(
            "\n".join(json.dumps(r) for r in records)
        )
        return grade("mid-turn", score(tmp_path))

    assert all(checks().values())
    for phase in ("queued", "failed"):
        assert not checks([events[0], events[1] | {"phase": phase}, *events[2:]])[
            "picked-up-1"
        ]
    for changes in (
        {"ephemeral": True},
        {"failure": "turn_failed"},
        {"responds": "later-input"},
        {"author": "user"},
    ):
        assert not checks([*events[:-1], events[-1] | changes])["replied-1"]
    assert not checks([events[0], events[1], events[-1], events[2]])["claimed-1"]
    assert not checks([e for e in events if e["kind"] != "start"])["claimed-1"]
    assert not checks(
        [events[0], events[1], events[2] | {"item": "other"}, events[-1]]
    )["claimed-1"]
    records[-1]["is_error"] = True
    assert not checks()["completed"]
    assert not checks()["turn-ended-1"]
    records[-1]["is_error"] = False
    records[-1]["turn_id"] = "later"
    assert not checks()["turn-ended-1"]


def test_success_readers_require_the_same_exact_agent_answer(tmp_path):
    from leaf.thread import answered_by_reply, successful_replies
    from leaf_dev import journey, review_scenario

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
        comment = append_admitted(
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
    from leaf_dev.journey import User

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
