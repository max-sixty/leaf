"""User acknowledgement across the real append door and page projection."""

import json

from interact_support import fetch, published, state_json
from leaf import event_endpoint as endpoint_model
from leaf import event_log as event_log_model
from leaf import files as files_model
from leaf import service as service_model
from leaf import thread as thread_model


def _post(server, event):
    status, body = fetch(f"{server}/api/event", data=json.dumps(event).encode())
    return status, json.loads(body)


def _post_read(server, *messages):
    return _post(server, {"kind": "read", "messages": list(messages)})


def _last_id(page_dir):
    return event_log_model.read_events(page_dir)[-1]["id"]


def _unread(state, root):
    """One thread's unread reading, as the browser receives it."""
    return next(
        thread["unread"]
        for thread in state["browser"]["thread"]["threads"]
        if thread["root"]["id"] == root
    )


def test_read_acknowledges_only_the_named_content_version_without_agent_work(
    page_dir, server
):
    published(page_dir)
    message = thread_model.cmd_comment(
        page_dir, None, None, None, "First answer.", None
    )
    original = message["id"]

    status, answer = _post_read(server, {"message": original, "version": original})
    assert status == 200, answer
    assert _unread(answer["state"], original) == []
    assert answer["state"]["pending"] == 0
    assert service_model.unacknowledged(event_log_model.read_events(page_dir), 0) == []

    edit = thread_model.cmd_edit(page_dir, original, "Revised answer.")
    status, answer = _post_read(server, {"message": original, "version": original})
    assert status == 200, answer  # a delayed older acknowledgement remains valid
    assert _unread(answer["state"], original) == [
        {"message": original, "version": edit["id"]}
    ]

    status, answer = _post_read(server, {"message": original, "version": edit["id"]})
    assert status == 200, answer
    assert _unread(answer["state"], original) == []


def test_what_the_user_does_in_a_thread_acknowledges_what_it_said(page_dir, server):
    """Replying, resolving and answering a widget each imply the user took the
    thread in as it stood; an edit after the move is unread again, and the agent reads
    the same fact in page state."""
    published(page_dir)
    root = thread_model.cmd_comment(
        page_dir,
        None,
        None,
        None,
        "Which should go first?",
        '<lf-ask id="order-decision"><h3>Which first?</h3>'
        '<lf-options id="order" choose>'
        '<lf-option id="mounts">Mounts</lf-option>'
        '<lf-option id="camera">Camera</lf-option>'
        "</lf-options></lf-ask>",
    )["id"]
    status, answer = _post(
        server,
        {
            "kind": "action",
            "revision": 1,
            "widget": "order",
            "action": "choose",
            "detail": {"options": ["mounts"]},
        },
    )
    assert status == 200, answer
    assert _unread(answer["state"], root) == []

    reply = thread_model.cmd_reply(
        page_dir, None, "Mounts first, then.", None, for_event=_last_id(page_dir)
    )["id"]
    assert state_json(page_dir)["threads"][0]["unread"] == [reply]
    status, answer = _post(
        server, {"kind": "reply", "parent": reply, "revision": 1, "text": "Thanks."}
    )
    assert status == 200, answer
    assert _unread(answer["state"], root) == []

    later = thread_model.cmd_reply(
        page_dir, None, "Done.", None, for_event=_last_id(page_dir)
    )["id"]
    status, answer = _post(server, {"kind": "resolve", "parent": root})
    assert status == 200, answer
    assert _unread(answer["state"], root) == []
    # A move the user takes back is no evidence either.
    status, answer = _post(server, {"kind": "undo", "undoes": _last_id(page_dir)})
    assert status == 200, answer
    assert _unread(answer["state"], root) == [{"message": later, "version": later}]
    status, answer = _post(server, {"kind": "resolve", "parent": root})
    assert status == 200, answer
    assert _unread(answer["state"], root) == []

    edit = thread_model.cmd_edit(page_dir, later, "Done, and tested.")
    assert state_json(page_dir)["threads"][0]["unread"] == [later]
    status, answer = _post_read(server, {"message": later, "version": edit["id"]})
    assert status == 200, answer
    assert state_json(page_dir)["threads"][0]["unread"] == []


def test_read_refuses_unknown_or_wrong_message_versions(page_dir, server):
    published(page_dir)
    first = thread_model.cmd_comment(page_dir, None, None, None, "First answer.", None)
    second = thread_model.cmd_comment(
        page_dir, None, None, None, "Second answer.", None
    )
    for pair in (
        {"message": "missing", "version": first["id"]},
        {"message": first["id"], "version": second["id"]},
    ):
        status, answer = _post_read(server, pair)
        assert status == 400, answer
        assert "is not a content version" in answer["error"]
    assert not any(
        event["kind"] == "read" for event in event_log_model.read_events(page_dir)
    )


def test_read_does_not_nudge_a_closed_agent_turn(page_dir, monkeypatch):
    published(page_dir)
    message = thread_model.cmd_comment(
        page_dir, None, None, None, "An answer to read.", None
    )
    claim_path = service_model.claim_path(page_dir)
    claim_path.parent.mkdir(parents=True, exist_ok=True)
    files_model.write_json(
        claim_path,
        {
            "page": str(page_dir.resolve()),
            "ts": service_model.now_iso(),
            "released": None,
            "activity": "multiplexed",
            "id": "one-user-session",
            "harness": "claude-code",
            "agent": "Agent",
            "turn": "closed-turn",
            "turn_closed": service_model.now_iso(),
            "messaged_turn": None,
        },
    )
    nudges = []

    class Harness:
        def nudge(self, page):
            nudges.append(page)
            return True

    monkeypatch.setattr(endpoint_model, "claim_harness", lambda claim: Harness())
    monkeypatch.setattr(endpoint_model, "wait_is_live", lambda *args: False)
    status, answer = endpoint_model.accept_event(
        page_dir,
        {
            "kind": "read",
            "messages": [{"message": message["id"], "version": message["id"]}],
        },
        dict,
    )
    assert status == 200, answer
    assert nudges == []

    status, body = endpoint_model.accept_event(
        page_dir,
        {"kind": "comment", "revision": 1, "text": "Please continue."},
        dict,
    )
    assert status == 200, body
    assert nudges == [page_dir.resolve()]
