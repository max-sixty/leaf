"""Response identities exposed by the canonical browser activity readings."""

from interact_support import (
    append_carried_log_record,
    page_state,
    publish,
)
from leaf import activity, thread


def test_live_response_evidence_keeps_its_attempt_without_text():
    evidence = activity._reply_evidence(
        {
            "attempt": "reply-attempt",
            "state": "interrupted",
            "responds": "user-input",
            "text": "partial private response",
        }
    )
    assert evidence["attempt"] == "reply-attempt"
    assert evidence["state"] == "interrupted"
    assert evidence["responds"] == "user-input"
    assert evidence["has_text"] is True
    assert "text" not in evidence

    workflow = {
        "input": "user-input",
        "stage": "picked_up",
        "response": None,
        "condition": None,
    }
    activity._bind_reply(
        [workflow],
        {
            "attempt": "reply-attempt",
            "state": "interrupted",
            "responds": "user-input",
            "text": "partial private response",
        },
    )
    assert workflow["condition"] == {"kind": "interrupted", "operation": "response"}
    assert workflow["response"]["attempt"] == "reply-attempt"


def test_terminal_failure_workflow_names_exact_reply_source(page_dir):
    publish(page_dir)
    source = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "user-input", "author": "user", "text": "A"},
    )
    failure = thread.post_reply(
        page_dir,
        {"to": source["id"], "for": source["id"]},
        "The agent turn ended.",
        failure="turn_failed",
        attempt="response-attempt",
    )

    [workflow] = page_state(page_dir)["workflows"]
    assert workflow["condition"] == {"kind": "failed", "operation": "response"}
    assert workflow["response"] == {
        "id": failure["id"],
        "attempt": "response-attempt",
        "state": "failed",
        "responds": source["id"],
    }
