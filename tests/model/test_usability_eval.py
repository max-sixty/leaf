"""Scenario checks require every phase and recover hidden context after delivery."""

import json

import pytest
from leaf.hook_transport import DELIVERY_FIELD
from leaf_dev import ROOT
from leaf_dev.eval_cases import definition
from leaf_dev.usability_eval import (
    CASES,
    Run,
    checks_for,
    expected_checks,
    progress_shown,
)


def test_every_scenario_has_fixed_nonvacuous_checks():
    assert len(CASES) == 19
    cases = definition("usability_eval")["cases"]
    assert set(cases) == set(CASES)
    for case in CASES:
        expected = expected_checks(case)
        assert expected[0] == "completed"
        judged = [r["metric"] for r in cases[case]["assert"]]
        assert len(expected) > 1 or judged
        assert len(set(expected + judged)) == len(expected + judged)
        actual = checks_for(case, {}, False)
        assert list(actual) == expected
        assert not any(actual.values())
    handoff = checks_for("handoff", {"served": True}, True)
    assert handoff["served"]
    assert not handoff["question_delivered"]
    near_miss = checks_for("near-miss", {"pages": 0}, True)
    assert all(near_miss.values())
    assert not checks_for("near-miss", {"pages": 1}, True)["no_page"]


def test_live_completion_requires_every_declared_round(tmp_path):
    run = Run("handoff", ROOT, tmp_path)
    (tmp_path / "stream-1.jsonl").write_text(
        '{"type":"result","is_error":false,"result":"initial handover"}\n'
    )
    assert not run.usable()


def test_progress_uses_the_admitted_log_before_the_exact_answer():
    """Observation delays and command failures cannot erase admitted progress."""
    started = {"kind": "start", "seq": 2, "item": "comment", "text": "Edit"}
    answered = {
        "kind": "reply",
        "seq": 3,
        "author": "agent",
        "parent": "root",
        "responds": "comment",
        "text": "Done",
    }
    assert progress_shown([], [started, answered], "comment")
    assert not progress_shown([], [started, answered], "other-input")
    assert not progress_shown([], [{**started, "seq": 4}, answered], "comment")
    assert not progress_shown([], [{**started, "item": "other"}, answered], "comment")
    for changes in (
        {"ephemeral": True},
        {"failure": "turn_failed"},
        {"responds": "other"},
        {"author": "user"},
    ):
        assert progress_shown([], [answered | changes, started | {"seq": 4}], "comment")
    progress = {
        "kind": "reply",
        "author": "agent",
        "seq": 2,
        "ephemeral": True,
        "start": {"item": "comment"},
        "text": "Edit",
    }
    assert progress_shown([], [progress, answered], "comment")


def test_native_opening_requires_page_response_evidence_during_handling():
    opening = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "I’ll add the dry-run duration."},
            ]
        },
    }
    tool = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "id": "edit", "name": "ApplyPatch", "input": {}},
            ]
        },
    }
    workflow = {
        "input": "comment",
        "response": {"state": "active", "has_text": True},
    }
    state = {"type": "eval_first_tool_state", "workflows": [workflow]}
    assert progress_shown([opening, tool, state], [], "comment")
    assert not progress_shown([opening, tool], [], "comment")
    assert not progress_shown([tool, state, opening], [], "comment")
    assert not progress_shown([opening, tool, state], [], "other-input")
    workflow["response"]["state"] = "failed"
    assert not progress_shown([opening, tool, state], [], "comment")
    workflow["response"]["state"] = "active"
    workflow["response"]["has_text"] = False
    assert not progress_shown([opening, tool, state], [], "comment")
    workflow["response"] = None
    assert not progress_shown([opening, tool, state], [], "comment")


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
    from leaf_dev.arms import read_trace, trace_summary

    def observed_execution(run, work):
        # Replace the external model call with its recorded result shape; retain
        # actual trace files, metrics, scenario grading and provider translation.
        (run.dir / "work-dir").write_text(str(work))
        for phase, counts in enumerate(usage, 1):
            record = {"type": "result", "is_error": False, "result": "A short reply."}
            if counts is not None:
                record["usage"] = counts
            (run.dir / f"stream-{phase}.jsonl").write_text(json.dumps(record) + "\n")

    monkeypatch.setattr(usability_eval, "execute", observed_execution)
    response = usability_eval.execute_scenario(
        "near-miss", ROOT, tmp_path, harness="codex"
    )
    assert response.get("tokenUsage", {}) == expected
    # Each phase's final message is a text the judge can read.
    texts = response["metadata"]["texts"]
    assert {key: value for key, value in texts.items() if key != "trace"} == {
        f"reply-{n}": "A short reply." for n in range(1, len(usage) + 1)
    }
    assert json.loads(texts["trace"]) == [
        {"phase": n, "records": read_trace(tmp_path / f"stream-{n}.jsonl")}
        for n in range(1, len(usage) + 1)
    ]
    if not expected:
        assert "tokenUsage" not in response
    phases = response["metadata"]["diagnostics"]["phases"]
    for index, phase in enumerate(phases, 1):
        arrangement = trace_summary(read_trace(tmp_path / f"stream-{index}.jsonl"))
        for field in ("input_tokens", "output_tokens"):
            assert phase[field] == (usage[index - 1] or {}).get(field)
            assert arrangement[field] == phase[field]
        assert phase["cost_usd"] is None
        assert arrangement["cost_usd"] is None
    assert "cost" not in response


def test_live_rounds_use_confirmed_receipts_before_successful_response():
    from leaf_dev.usability_eval import live_rounds

    trace = [
        {"type": "eval_post", "round": 1},
        {
            "type": "system",
            "subtype": "hook_response",
            "output": json.dumps({DELIVERY_FIELD: {"id": "d1", "inline": True}}),
        },
        {"type": "result", "is_error": False},
    ]
    assert live_rounds(trace)[0]["end"] is None
    trace[1] = {"type": "eval_received", "round": 2}
    assert live_rounds(trace)[0]["end"] is None
    trace[1] = {"type": "eval_received", "round": 1}
    assert live_rounds(trace)[0]["end"] == 2
    assert live_rounds(trace)[0]["delivery"] == 0
    assert live_rounds(trace[:-1])[0]["end"] is None


def test_handoff_url_must_match_the_server_observed_by_the_live_run():
    from leaf_dev.usability_eval import handed_page_url

    url = "http://127.0.0.1:42041/?t=this-page"
    trace = [{"type": "eval_served", "url": url}]
    assert handed_page_url(trace, f"[Dry run]({url}#dry-run)")
    assert not handed_page_url(trace, "http://127.0.0.1:42042/?t=other-page")
    assert not handed_page_url(trace, "http://127.0.0.1:42041/?t=this-page-other-key")
    assert not handed_page_url([], url)
