"""Scenario checks require every phase and recover hidden context after delivery."""

import json

import pytest
from leaf.delivery import record_pickup
from leaf.event_log import read_cursor, read_events
from leaf.service import PageTransaction
from leaf_dev import ROOT
from leaf_dev.usability_eval import (
    CASES,
    PREMISE,
    Run,
    admit,
    append_elided_history,
    attempt_key,
    build_fixture,
    checks_for,
    claimed_first,
    expected_checks,
    page_events,
    post_round,
    score_elided,
    score_mixed,
)


def test_every_scenario_has_fixed_nonvacuous_checks():
    assert len(CASES) == 19
    for case in CASES:
        expected = expected_checks(case)
        assert expected[0] == "completed"
        assert len(expected) > 1
        assert len(set(expected)) == len(expected)
        actual = checks_for(case, {}, [], False)
        assert list(actual) == expected
        assert not any(actual.values())
    handoff = checks_for("handoff", {"served": True}, [], True)
    assert handoff["served"]
    assert not handoff["question_delivered"]
    assert not handoff["question_answered"]
    near_miss = checks_for("near-miss", {"pages": 0}, [{"leaf_skill": False}], True)
    assert all(near_miss.values())
    assert not checks_for("near-miss", {"pages": 1}, [{"leaf_skill": True}], True)[
        "no_page"
    ]


@pytest.mark.parametrize(
    "case",
    [
        "reading",
        "resume",
        "constructs",
        "board",
        "package",
        "shared-source",
        "handoff",
        "mixed",
        "elided",
    ],
)
def test_fixture_builds_through_current_leaf_admission(tmp_path, case):
    run = Run(case, ROOT, tmp_path)
    run.state.mkdir()
    page = tmp_path / "page"
    build_fixture(run, CASES[case].fixture, page)
    assert page.is_dir()
    assert (page / "index.html").is_file()
    if case == "elided":
        assert PREMISE not in str(page_events(page))
        append_elided_history(run, page)
        events = page_events(page)
        assert PREMISE in str(events)
        assert len([e for e in events if e["kind"] in ("comment", "reply")]) == 24
        assert any(e["kind"] == "resolve" for e in events)
        assert read_cursor(page) >= max(
            e["seq"] for e in read_events(page) if e["author"] == "user"
        )
        (tmp_path / "work-dir").write_text(str(tmp_path))
        latest = [e for e in events if e["kind"] == "reply"][-1]
        admit(run, page, {
            "kind": "reply", "parent": latest["id"], "revision": 1,
            "attempt": "usability-eval-0-0", "text": "When does the copy start?",
        })  # fmt: skip
        read_premise = {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": PREMISE}]},
        }
        trace = [
            {"type": "result"},
            {"type": "eval_post", "round": 1},
            {"type": "system", "subtype": "hook_response",
             "output": 'leaf-delivery-v {"elided":{"messages":16}}'},
            {"type": "eval_received", "round": 1},
            read_premise,
            {"type": "result"},
        ]  # fmt: skip
        assert score_elided(run, trace)["middle_read"]
        assert not score_elided(
            run, [read_premise, *[r for r in trace if r is not read_premise]]
        )["middle_read"]


def test_live_completion_requires_every_declared_round(tmp_path):
    run = Run("handoff", ROOT, tmp_path)
    (tmp_path / "stream-1.jsonl").write_text(
        '{"type":"result","is_error":false,"result":"initial handover"}\n'
    )
    assert not run.usable()


def test_a_thread_claim_must_be_accepted_for_the_comment_before_reply():
    call = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "claim",
                    "name": "Bash",
                    "input": {"command": "leaf task start page comment 'Edit'"},
                }
            ]
        },
    }
    reply = {"type": "assistant", "message": {"content": [{
        "type": "tool_use", "id": "reply", "name": "Bash",
        "input": {"command": "leaf thread reply page --for comment --text Done"},
    }]}}  # fmt: skip

    def result(thread, refused=False):
        return {"type": "user", "message": {"content": [{
            "type": "tool_result", "tool_use_id": "claim", "is_error": refused,
            "content": json.dumps({"kind": "start", "item": thread}),
        }]}}  # fmt: skip

    accepted = result("comment")
    assert claimed_first([call, accepted, reply], "comment")
    assert not claimed_first([call, result("comment", refused=True), reply], "comment")
    assert not claimed_first([call, result("another-thread"), reply], "comment")
    assert not claimed_first([call, reply, accepted], "comment")


@pytest.mark.parametrize("membership", ["together", "split", "missing-error"])
def test_mixed_delivery_requires_the_admitted_native_error_in_the_same_batch(
    tmp_path, membership
):
    run = Run("mixed", ROOT, tmp_path)
    run.state.mkdir()
    page = tmp_path / "page"
    build_fixture(run, "mixed", page)
    (tmp_path / "work-dir").write_text(str(tmp_path))

    class LocalTab:
        origin = "http://127.0.0.1:12345"

        def post(self, event):
            admit(run, page, event)

    before = {e["id"] for e in page_events(page)}
    admitted_ids = post_round(run, page, LocalTab(), CASES["mixed"].rounds[0], 0)
    admitted = [e for e in page_events(page) if e["id"] not in before]
    assert len(admitted) == 6
    assert len(admitted_ids) == 3
    error = next(e for e in admitted if e["kind"] == "error")
    assert error["author"] == "page"
    assert "attempt" not in error
    assert error["id"] in admitted_ids
    users = [e for e in admitted if e["author"] == "user"]
    batches = [admitted] if membership == "together" else [users]
    if membership == "split":
        batches.append([error])
    with PageTransaction(page) as transaction:
        for batch in batches:
            record_pickup(transaction, batch, session="eval", turn="turn")
    pickups = [e for e in page_events(page) if e["kind"] == "pickup"]
    if membership == "together":
        assert set(pickups[0]["events"]) == admitted_ids
    trace = [
        {"type": "result"},
        {"type": "eval_post", "round": 1, "events": sorted(admitted_ids)},
        {"type": "eval_received", "round": 1},
        {"type": "result"},
    ]
    assert score_mixed(run, trace)["one_delivery"] == (membership == "together")


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        ([None], {}),
        ([{"input_tokens": 0, "output_tokens": 0}], {"prompt": 0, "completion": 0}),
        ([{"input_tokens": 7}], {"prompt": 7}),
        ([{"input_tokens": 7, "output_tokens": 2}, None], {}),
        (
            [
                {"input_tokens": 7, "output_tokens": 2},
                {"input_tokens": 3, "output_tokens": 1},
            ],
            {"prompt": 10, "completion": 3},
        ),
    ],
)
def test_native_scenario_output_preserves_unavailable_usage(
    tmp_path, monkeypatch, usage, expected
):
    from leaf_dev import usability_eval
    from leaf_dev.arrangement_eval import trace_scores as arrangement_trace_scores

    def observed_execution(run):
        # Replace the external model call with its recorded result shape; retain
        # actual trace files, metrics, scenario grading and provider translation.
        (run.dir / "work-dir").write_text(str(tmp_path))
        for phase, counts in enumerate(usage, 1):
            record = {"type": "result", "is_error": False, "result": "A short reply."}
            if counts is not None:
                record["usage"] = counts
            (run.dir / f"stream-{phase}.jsonl").write_text(json.dumps(record) + "\n")

    monkeypatch.setattr(usability_eval, "execute", observed_execution)
    response = usability_eval.execute_scenario(
        "near-miss", ROOT, tmp_path, host="codex"
    )
    assert response.get("tokenUsage", {}) == expected
    if not expected:
        assert "tokenUsage" not in response
    phases = response["metadata"]["diagnostics"]["phases"]
    for index, phase in enumerate(phases, 1):
        arrangement = arrangement_trace_scores(tmp_path / f"stream-{index}.jsonl")
        for field in ("input_tokens", "output_tokens"):
            assert phase[field] == (usage[index - 1] or {}).get(field)
            assert arrangement[field] == phase[field]
        assert phase["cost_usd"] is None and phase["cost_known"] is False
        assert arrangement["cost_usd"] is None and arrangement["cost_known"] is False
    assert "cost" not in response


def test_mixed_round_requires_receipts_only_for_admitted_attention(tmp_path):
    from leaf_dev.harness import inputs_received

    run = Run("mixed", ROOT, tmp_path)
    run.state.mkdir()
    page = tmp_path / "page"
    build_fixture(run, "mixed", page)

    class Browser:
        origin = "http://127.0.0.1:1"

        def post(self, event):
            admit(run, page, event)

    moves = CASES["mixed"].rounds[0]
    post_round(run, page, Browser(), moves, 0)
    events = page_events(page)
    attempts = {
        attempt_key(0, i) for i, move in enumerate(moves) if move["kind"] != "error"
    }
    posted = [event for event in events if event.get("attempt") in attempts]
    assert len(posted) == 5
    assert [event["attention"] for event in posted] == [True, True, False, False, False]
    assert not inputs_received(events, attempts)
    attention = [event["id"] for event in posted if event["attention"]]
    events.append({"kind": "pickup", "phase": "opened", "events": attention})
    assert inputs_received(events, attempts)
    assert not inputs_received(events, attempts | {"never-admitted"})


def test_live_rounds_use_confirmed_receipts_before_successful_response():
    from leaf_dev.usability_eval import live_rounds

    trace = [
        {"type": "eval_post", "round": 1},
        {"type": "system", "subtype": "hook_response", "output": "leaf-delivery-v"},
        {"type": "result", "is_error": False},
    ]
    assert live_rounds(trace)[0]["end"] is None
    trace[1] = {"type": "eval_received", "round": 2}
    assert live_rounds(trace)[0]["end"] is None
    trace[1] = {"type": "eval_received", "round": 1}
    assert live_rounds(trace)[0]["end"] == 2
    assert live_rounds(trace)[0]["delivery"] == 0
    assert live_rounds(trace[:-1])[0]["end"] is None


def test_round_scoring_leaves_the_watch_with_leaf():
    from leaf_dev.usability_eval import live_rounds, round_scores

    trace = [
        {"type": "eval_post", "round": 1},
        {"type": "eval_received", "round": 1},
        {"type": "result", "result": "http://127.0.0.1:1234/?t=abc", "is_error": False},
        {"type": "eval_status", "status": {"state": "waiting"}},
    ]
    assert round_scores(trace, live_rounds(trace)[0], "input")[
        "input_watch_left_to_leaf"
    ]
    trace.insert(
        2,
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "manual",
                        "name": "Bash",
                        "input": {
                            "command": "leaf wait page",
                            "run_in_background": True,
                        },
                    }
                ]
            },
        },
    )
    assert not round_scores(trace, live_rounds(trace)[0], "input")[
        "input_watch_left_to_leaf"
    ]


@pytest.mark.parametrize("host", ["cc", "codex"])
def test_live_injection_reads_the_claimants_turn_from_the_isolated_home(tmp_path, host):
    import os
    from types import SimpleNamespace

    from leaf_dev.usability_eval import arm_python, observed_active_turn

    run = Run("mixed", ROOT, tmp_path, host)
    run.state.mkdir()
    page = tmp_path / "page"
    build_fixture(run, "mixed", page)
    # Create actual session and page-claim publications in the child state home.
    # Only the external model transport is replaced; the CLI joins the canonical
    # claim and lifecycle under the arm's own isolated environment.
    arm_python(
        run,
        """
import os, sys
from pathlib import Path
from leaf.host import ClaudeCodeHarness
from leaf.service import PageTransaction
from leaf.state import prompt_turn
os.environ["CLAUDE_PID"] = sys.argv[2]
with PageTransaction(Path(sys.argv[1])) as page:
    page.take_claim(ClaudeCodeHarness(session="injection-observer", agent="Claude"))
prompt_turn("injection-observer", "actual-parent-turn")
""",
        str(page),
        str(os.getpid()),
    )
    child = SimpleNamespace(task=SimpleNamespace(running={"actual-parent-turn"}))
    assert observed_active_turn(run, page, child) == "actual-parent-turn"
    if host == "codex":
        child.task.running.clear()
        assert observed_active_turn(run, page, child) is None
        child.task.running.add("actual-parent-turn")
    arm_python(
        run,
        """
from leaf.state import close_session_turn
assert close_session_turn("injection-observer", "actual-parent-turn")
""",
    )
    assert observed_active_turn(run, page, child) is None
