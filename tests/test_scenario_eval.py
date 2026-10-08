"""Complete trajectories and fixed evidence contracts survive partial execution."""

import json

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
    from leaf_dev import journey, review_scenario, usability_eval

    comment = {
        "kind": "comment",
        "author": "user",
        "id": "input",
        "attempt": review_scenario.attempt("first"),
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
        assert usability_eval.answered(events, "input") == expected
        assert review_scenario.answers(tmp_path, "first") == expected
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
        {"kind": "pickup", "phase": "claimed", "events": ["first", "second"]},
    ]
    assert inputs_received(events, set())
    assert not inputs_received(events, {"unadmitted"})
    assert not inputs_received(events, {"round-1", "round-2"})
    events.append({"kind": "pickup", "phase": "opened", "events": ["first"]})
    assert inputs_received(events, {"round-1"})
    assert not inputs_received(events, {"round-1", "round-2"})
    events.append({"kind": "pickup", "phase": "opened", "events": ["second"]})
    assert inputs_received(events, {"round-1", "round-2"})
