"""Scenario checks require every phase and recover hidden context after delivery."""

import json

import pytest
from leaf.event_log import read_cursor, read_events
from leaf_dev import ROOT
from leaf_dev.usability_eval import (
    CASES,
    PREMISE,
    Run,
    admit,
    append_elided_history,
    build_fixture,
    checks_for,
    claimed_first,
    expected_checks,
    page_events,
    score_elided,
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
            {"type": "eval_post"},
            {"type": "system", "subtype": "hook_response",
             "output": 'leaf-delivery-v {"elided":{"messages":16}}'},
            read_premise,
            {"type": "result"},
        ]  # fmt: skip
        assert score_elided(run, trace)["middle_read"]
        assert not score_elided(run, [read_premise, *trace[:3], trace[4]])[
            "middle_read"
        ]


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
                    "input": {
                        "command": "leaf status page working 'Edit' --on comment"
                    },
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
            "content": json.dumps({"state": "working", "work": [{
                "subject": {"kind": "thread", "id": thread},
            }]}),
        }]}}  # fmt: skip

    accepted = result("comment")
    assert claimed_first([call, accepted, reply], "comment")
    assert not claimed_first([call, result("comment", refused=True), reply], "comment")
    assert not claimed_first([call, result("another-thread"), reply], "comment")
    assert not claimed_first([call, reply, accepted], "comment")
