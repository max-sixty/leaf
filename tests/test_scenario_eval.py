"""Complete trajectories and fixed evidence contracts survive partial execution."""

import json

from leaf_dev.delivery_eval import expected_checks, grade, score


def test_partial_native_traces_do_not_report_zero_elapsed_minutes(tmp_path):
    from leaf_dev import arrangement_eval, usability_eval

    stream = tmp_path / "stream.jsonl"
    for trace, minutes in (
        ([], None),
        ([{"type": "result", "is_error": False}], None),
        ([{"type": "result", "is_error": False, "duration_ms": 2700000}], 45),
    ):
        stream.write_text("".join(json.dumps(record) + "\n" for record in trace))
        assert arrangement_eval.trace_scores(stream)["minutes"] == minutes
        assert usability_eval.trace_scores(trace)["minutes"] == minutes


def test_delivery_requires_every_comment_and_a_completed_reply_turn():
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
        "done_s": 0,
        "turn_s": 0,
        "before_claim": [],
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
    assert not grade("mid-turn", [{**complete, "done_s": None}])["replied-1"]
    assert not grade("mid-turn", [{**complete, "claim_s": None}])["claimed-1"]


def test_delivery_uses_successful_turns_and_accepted_exact_thread_claims(tmp_path):
    # Native CC stream and Leaf start record shapes, recorded at the scorer boundary.
    status = {
        "attention": False,
        "id": "a1b2c3d4",
        "author": "agent",
        "seq": 1,
        "ts": "2026-10-02T00:00:02.500+00:00",
        "kind": "start",
        "item": "comment",
        "text": "editing",
    }
    records = [
        {
            "type": "eval_post",
            "round": 1,
            "injection": "running",
            "active_turn": "setup-turn",
        },
        {
            "type": "system",
            "subtype": "hook_response",
            "hook_event": "UserPromptSubmit",
            "output": "leaf-delivery-v",
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "claim",
                        "name": "Bash",
                        "input": {"command": "leaf task start page comment editing"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "claim",
                        "is_error": False,
                        "content": json.dumps(status),
                    }
                ]
            },
        },
        {"type": "result", "is_error": False},
    ]
    for n, record in enumerate(records):
        record["received_at"] = f"2026-10-02T00:00:0{n}+00:00"
    events = [
        {
            "kind": "comment",
            "id": "comment",
            "author": "user",
            "attempt": "delivery-eval-0001-attempt",
            "ts": records[0]["received_at"],
        },
        {
            "kind": "pickup",
            "phase": "opened",
            "events": ["comment"],
            "ts": records[1]["received_at"],
        },
        {
            "kind": "reply",
            "author": "agent",
            "parent": "comment",
            "responds": "comment",
            "ts": records[3]["received_at"],
        },
    ]
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))

    def checks():
        (tmp_path / "stream-1.jsonl").write_text(
            "\n".join(json.dumps(r) for r in records)
        )
        return grade("mid-turn", score(tmp_path))

    assert all(checks().values())
    reply = events[-1]
    for changes in (
        {"ephemeral": True},
        {"failure": "turn_failed"},
        {"responds": "later-input"},
        {"responds": None},
        {"author": "user"},
    ):
        (tmp_path / "events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in [*events[:-1], {**reply, **changes}])
        )
        assert not checks()["replied-1"]
    # Presentation can live under another root; the response address owns success.
    (tmp_path / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in [*events[:-1], {**reply, "parent": "root"}])
    )
    assert checks()["replied-1"]
    records[-1]["is_error"] = True
    assert not checks()["completed"]
    assert not checks()["turn-ended-1"]
    records[-1]["is_error"] = False
    returned = records[3]["message"]["content"][0]
    returned["is_error"] = True
    assert not checks()["claimed-1"]
    returned["is_error"] = False
    for other in [{"kind": "task"}, {"item": "unrelated"}]:
        returned["content"] = json.dumps({**status, **other})
        assert not checks()["claimed-1"]

    returned["content"] = json.dumps(status)
    records[2]["message"]["content"].insert(
        0,
        {
            "type": "tool_use",
            "id": "read",
            "name": "Read",
            "input": {"file_path": "page/index.html"},
        },
    )
    assert checks()["claimed-1"]
    assert score(tmp_path)[0]["before_claim"] == ["Read"]


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
