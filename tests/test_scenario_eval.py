"""Complete trajectories and fixed evidence contracts survive partial execution."""

import json
from pathlib import Path

import pytest
from leaf_dev.delivery_eval import expected_checks, grade, score
from leaf_dev.scenario_eval import prepare


def test_delivery_requires_every_comment_and_a_completed_reply_turn():
    complete = {
        "comment": 1,
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
    assert all(grade("idle", [complete, {**complete, "comment": 2}]).values())
    assert not grade("mid-turn", [{**complete, "done_s": None}])["replied-1"]
    assert not grade("mid-turn", [{**complete, "claim_s": None}])["claimed-1"]


def test_delivery_uses_successful_turns_and_accepted_exact_thread_claims(tmp_path):
    # Native CC stream and Leaf status JSON shapes, recorded at the scorer boundary.
    status = {
        "state": "working",
        "work": [{"subject": {"kind": "thread", "id": "comment"}}],
    }
    records = [
        {"type": "eval_comment", "n": 1},
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
                        "input": {
                            "command": "leaf status page working editing --on comment"
                        },
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
        {"kind": "reply", "parent": "comment", "ts": records[3]["received_at"]},
    ]
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))

    def checks():
        (tmp_path / "stream.jsonl").write_text(
            "\n".join(json.dumps(r) for r in records)
        )
        return grade("mid-turn", score(tmp_path))

    assert all(checks().values())
    records[-1]["is_error"] = True
    assert not checks()["completed"]
    assert not checks()["turn-ended-1"]
    records[-1]["is_error"] = False
    returned = records[3]["message"]["content"][0]
    returned["is_error"] = True
    assert not checks()["claimed-1"]
    returned["is_error"] = False
    for work in [[], [{"subject": {"kind": "thread", "id": "unrelated"}}]]:
        returned["content"] = json.dumps({**status, "work": work})
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


def test_scenario_matrix_pairs_arms_and_keeps_repetition_evidence_distinct(tmp_path):
    arms = {arm: tmp_path / arm for arm in ("base", "candidate")}
    config = prepare("delivery", ["idle", "mid-turn"], arms, tmp_path / "results", 2)
    assert len(config["providers"]) == 2
    assert len(config["tests"]) == 8
    tests = config["tests"]
    assert [t["metadata"]["arm"] for t in tests] == ["base", "candidate"] * 4
    assert len({t["vars"]["work"] for t in tests}) == 8
    for test in tests:
        assert [a["config"]["check"] for a in test["assert"]] == expected_checks(
            test["vars"]["case"]
        )
        assert test["providers"] == [f"cc/{test['metadata']['arm']}"]
        assert Path(test["vars"]["work"]).is_relative_to(tmp_path / "results")


@pytest.mark.parametrize("suite", ["usability", "arrangement", "delivery"])
def test_every_existing_scenario_declares_completion_and_fixed_checks(suite, tmp_path):
    from leaf_dev.scenario_eval import select_cases

    cases = select_cases(suite, ())
    config = prepare(suite, cases, {"candidate": tmp_path / "payload"}, tmp_path, 1)
    assert len(config["tests"]) == len(cases) > 0
    for test in config["tests"]:
        checks = [a["config"]["check"] for a in test["assert"]]
        assert "completed" in checks
        assert len(checks) == len(set(checks))


def test_live_round_receipts_require_exact_admitted_user_inputs():
    from leaf_dev.harness import inputs_received

    events = [
        {"id": "first", "kind": "comment", "attempt": "round-1"},
        {"id": "second", "kind": "action", "attempt": "round-2"},
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
