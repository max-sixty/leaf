"""Response identities exposed by the canonical browser activity readings."""

from interact_support import page_state, publish
from leaf import activity, conversation, event_log, requests
from leaf.served_state.conversation import _thread_awaits_reader


def test_live_response_evidence_keeps_its_attempt_without_text():
    evidence = activity._reply_evidence(
        {
            "attempt": "reply-attempt",
            "state": "interrupted",
            "responds": "reader-input",
            "text": "partial private response",
        }
    )
    assert evidence["attempt"] == "reply-attempt"
    assert evidence["state"] == "interrupted"
    assert evidence["responds"] == "reader-input"
    assert evidence["has_text"] is True
    assert "text" not in evidence

    workflow = {"input": "reader-input", "response": None, "condition": None}
    activity._bind_reply(
        [workflow],
        {
            "attempt": "reply-attempt",
            "state": "interrupted",
            "responds": "reader-input",
            "text": "partial private response",
        },
    )
    assert workflow["condition"] == {"kind": "interrupted", "operation": "response"}
    assert workflow["response"]["attempt"] == "reply-attempt"


def test_terminal_failure_workflow_names_exact_reply_source(page_dir):
    publish(page_dir)
    source = event_log.append_event(
        page_dir,
        {"kind": "comment", "id": "reader-input", "author": "user", "text": "A"},
    )
    failure = conversation.cmd_reply(
        page_dir,
        source["id"],
        "The agent turn ended.",
        None,
        for_event=source["id"],
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


def test_reader_prompt_names_the_latest_question_content_version(page_dir):
    publish(page_dir)
    root = event_log.append_event(
        page_dir,
        {"kind": "comment", "id": "root", "author": "user", "text": "Help"},
    )
    first = event_log.append_event(
        page_dir,
        {
            "kind": "reply",
            "id": "first-question",
            "author": "agent",
            "parent": root["id"],
            "responds": root["id"],
            "awaits": True,
            "text": "First question?",
        },
    )
    event_log.append_event(
        page_dir,
        {
            "kind": "reply",
            "id": "status-update",
            "author": "agent",
            "parent": first["id"],
            "initiates": True,
            "text": "Still checking.",
        },
    )
    [thread] = page_state(page_dir)["browser"]["conversation"]["threads"]
    assert thread["reader_prompt"] == {"message": first["id"], "version": first["id"]}

    second = event_log.append_event(
        page_dir,
        {
            "kind": "reply",
            "id": "second-question",
            "author": "agent",
            "parent": first["id"],
            "initiates": True,
            "awaits": True,
            "text": "Second question?",
        },
    )
    edited = event_log.append_event(
        page_dir,
        {
            "kind": "edit",
            "id": "second-edit",
            "author": "agent",
            "message": second["id"],
            "text": "Reworded second question?",
        },
    )
    [thread] = page_state(page_dir)["browser"]["conversation"]["threads"]
    assert thread["reader_prompt"] == {"message": second["id"], "version": edited["id"]}


def test_structural_ask_owns_attention_without_a_duplicate_plain_prompt():
    assert _thread_awaits_reader(
        "thread",
        {"resolved": False},
        {},
        {},
        None,
        {"thread"},
    ) == (True, None)


def test_request_outcomes_keep_receipts_after_the_seat_is_removed():
    events = [
        {
            "kind": "request",
            "id": "first",
            "widget": "old-seat",
            "action": "submit",
            "meaning": {"document": {"kind": "page", "revision": 1}, "unit": "old-seat"},
        },
        {
            "kind": "receipt",
            "id": "first-failed",
            "request": "first",
            "status": "failed",
            "seq": 2,
        },
        {
            "kind": "request",
            "id": "second",
            "widget": "old-seat",
            "action": "submit",
            "meaning": {"document": {"kind": "page", "revision": 1}, "unit": "old-seat"},
        },
        {
            "kind": "receipt",
            "id": "second-succeeded",
            "request": "second",
            "status": "succeeded",
            "seq": 4,
        },
    ]
    assert [
        (item["request"], item["receipt"]["id"], item["document"])
        for item in requests.request_outcomes(events)
    ] == [
        ("first", "first-failed", {"kind": "page", "revision": 1}),
        ("second", "second-succeeded", {"kind": "page", "revision": 1}),
    ]
