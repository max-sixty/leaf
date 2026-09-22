"""Reader acknowledgement across the real append door and page projection."""

import json

from interact_support import fetch, published
from leaf import conversation as conversation_model
from leaf import event_log as event_log_model
from leaf import event_endpoint as endpoint_model
from leaf import files as files_model
from leaf import service as service_model


def _post_read(server, *messages):
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "read", "messages": list(messages)}).encode(),
    )
    return status, json.loads(body)


def _agent_message(state, identity):
    return next(
        message
        for thread in state["browser"]["conversation"]["threads"]
        for message in thread["msgs"]
        if message["id"] == identity
    )


def test_read_acknowledges_only_the_named_content_version_without_agent_work(
    page_dir, server
):
    published(page_dir)
    message = conversation_model.cmd_comment(
        page_dir, None, None, None, "First answer.", None
    )
    original = message["id"]

    status, answer = _post_read(server, {"message": original, "version": original})
    assert status == 200, answer
    assert _agent_message(answer["state"], original)["unread"] is False
    assert answer["state"]["pending"] == 0
    assert service_model.unacknowledged(event_log_model.read_events(page_dir), 0) == []

    edit = conversation_model.cmd_edit(page_dir, original, "Revised answer.")
    status, answer = _post_read(server, {"message": original, "version": original})
    assert status == 200, answer  # a delayed older acknowledgement remains valid
    latest = _agent_message(answer["state"], original)
    assert latest["content_version"] == edit["id"]
    assert latest["unread"] is True

    status, answer = _post_read(server, {"message": original, "version": edit["id"]})
    assert status == 200, answer
    assert _agent_message(answer["state"], original)["unread"] is False


def test_read_refuses_unknown_or_wrong_message_versions(page_dir, server):
    published(page_dir)
    first = conversation_model.cmd_comment(
        page_dir, None, None, None, "First answer.", None
    )
    second = conversation_model.cmd_comment(
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
    message = conversation_model.cmd_comment(
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
            "id": "one-reader-session",
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
        {"kind": "read", "messages": [{"message": message["id"], "version": message["id"]}]},
        lambda: {},
    )
    assert status == 200, answer
    assert nudges == []

    status, body = endpoint_model.accept_event(
        page_dir,
        {"kind": "comment", "revision": 1, "text": "Please continue."},
        lambda: {},
    )
    assert status == 200, body
    assert nudges == [page_dir.resolve()]
