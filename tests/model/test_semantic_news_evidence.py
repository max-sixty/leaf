"""Response identities exposed by the canonical browser activity readings."""

from interact_support import (
    append_carried_log_record,
    page_state,
    publish,
    record_claim,
)

from leaf import thread
from leaf.service import PageTransaction


def test_live_response_evidence_keeps_its_attempt_without_text(page_dir):
    publish(page_dir)
    source = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "A"}
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    with PageTransaction(page_dir) as page:
        page.set_stream_reply(
            "codex-thread",
            "turn-1",
            {"parent": source["id"], "responds": source["id"]},
            "reply-attempt",
            "item-1",
            "partial private response",
            "interrupted",
        )
    [workflow] = page_state(page_dir)["workflows"]
    assert workflow["condition"] == {"kind": "interrupted", "operation": "response"}
    assert workflow["response"] == {
        "state": "interrupted",
        "turn": "turn-1",
        "settles": False,
        "attempt": "reply-attempt",
    }


def test_terminal_failure_workflow_names_exact_reply_source(page_dir):
    publish(page_dir)
    source = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "user-input", "author": "user", "text": "A"},
    )
    failure = thread.post_reply(
        page_dir,
        {"parent": source["id"], "responds": source["id"]},
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
    }
