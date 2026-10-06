"""Response identities exposed by the canonical browser activity readings."""

from interact_support import append_carried_log_record, page_state, publish
from leaf import activity, thread
from leaf.asks import thread_awaits_user


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
    failure = thread.cmd_reply(
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


def test_user_prompt_names_the_latest_question_content_version(page_dir):
    publish(page_dir)
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "root", "author": "user", "text": "Help"},
    )
    first = append_carried_log_record(
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
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "status-update",
            "author": "agent",
            "parent": first["id"],
            "text": "Still checking.",
        },
    )
    [thread] = page_state(page_dir)["browser"]["thread"]["threads"]
    assert thread["user_prompt"] == {"message": first["id"], "version": first["id"]}

    second = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "second-question",
            "author": "agent",
            "parent": first["id"],
            "awaits": True,
            "text": "Second question?",
        },
    )
    edited = append_carried_log_record(
        page_dir,
        {
            "kind": "edit",
            "id": "second-edit",
            "author": "agent",
            "message": second["id"],
            "text": "Reworded second question?",
        },
    )
    [thread] = page_state(page_dir)["browser"]["thread"]["threads"]
    assert thread["user_prompt"] == {"message": second["id"], "version": edited["id"]}


def test_structural_ask_owns_attention_without_a_duplicate_plain_prompt():
    assert thread_awaits_user(
        "thread",
        {"resolved": False},
        {},
        {},
        None,
        {"thread"},
        set(),
    ) == (True, None)
