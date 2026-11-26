"""A session's lifecycle record: prompts, stops and provider observations opening
and closing its turn, session end releasing its pages, and the prompt that serves a
resumed session's pages again."""

import contextlib
import json
import os
import socket
import subprocess

import pytest
from interact_support import (
    LEAF_COMMAND,
    STATED_TIMEOUT,
    append_carried_log_record,
    available_loopback_port,
    fixture_service,
    inlined,
    read_record,
    record_claim,
    start_server_command,
    vendored_at_another_protocol,
    wait_for,
    write_record,
)
from model.test_session_lifecycle import (
    prompt,
)

from leaf.base import files as files_model
from leaf.base import schema as schema_model
from leaf.base import server as server_model
from leaf.base import service as service_model
from leaf.base import state as cleanup_model
from leaf.commands import hook_transport as hook_transport_model
from leaf.commands import hooks as hooks_model
from leaf.pages import hosting as hosting_model
from leaf.source.registry import storage as registry_storage


def test_the_server_a_prompt_hook_starts_lives_as_long_as_its_session(claimed):
    """The prompt hook is a process of its own that exits once it answers. The
    server it starts for a resumed session lives by the session's process, which
    the harness names to the hook, so it outlives the hook, and it retires when the
    session ends again, as one `leaf server start` started does."""
    started = start_server_command(claimed, session_id="s1")
    assert started.returncode == 0, started.stderr
    for outage in ("first", "second"):
        cleanup_model.end_harness_instance("s1")
        wait_for(
            lambda: server_model.running_server(claimed),
            lambda running: not running,
            failure=f"the server did not retire after the {outage} session ended",
        )
        hook = subprocess.run(
            [*LEAF_COMMAND, "hook", "--harness", "claude-code"],
            input=json.dumps(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "s1",
                    "prompt_id": f"{outage}-resumed",
                }
            ),
            env=os.environ | {"CLAUDE_PID": str(os.getpid())},
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert (hook.returncode, hook.stdout) == (0, ""), hook.stderr
        assert server_model.running_server(claimed), outage
        claim = service_model.page_claim(claimed)
        assert service_model.claim_is_active(claim), outage
        assert claim is not None
        assert (claim["pid"], claim["turn"]) == (os.getpid(), f"{outage}-resumed")


@pytest.mark.parametrize("cause", ["newer Leaf", "port held", "no time left"])
def test_a_prompt_says_why_a_page_did_not_start_and_tries_again(
    page_dir, capsys, monkeypatch, cause
):
    """A start refused, as for a page a newer Leaf initialized, while another
    process holds the page's port, or once the hook has no time left before its
    deadline, leaves the page as it was and tells the turn which page and why. The
    next prompt tries again, and serves the page once the cause is gone."""
    record_claim(page_dir)
    with contextlib.ExitStack() as cause_stands:
        if cause == "newer Leaf":
            fixture_service(page_dir, available_loopback_port(), "session")
            layer = page_dir / schema_model.LAYER_FILE
            recorded = layer.read_bytes()
            record = registry_storage.layer_record(page_dir)
            assert record is not None
            later = f"leaf-layer/{registry_storage.LAYER.since + 1}"
            layer.write_text(json.dumps({"format": later, **record}), encoding="utf-8")
            cause_stands.callback(layer.write_bytes, recorded)
            reason = "Use a newer Leaf"
        elif cause == "port held":
            holder = cause_stands.enter_context(socket.socket())
            holder.bind(("127.0.0.1", 0))
            holder.listen()
            fixture_service(page_dir, holder.getsockname()[1], "session")
            reason = "Address already in use"
        else:
            fixture_service(page_dir, available_loopback_port(), "session")
            bounded = cause_stands.enter_context(monkeypatch.context())
            bounded.setattr(hook_transport_model, "CONFIRM_WITHIN", 0)
            reason = "no time left"
        capsys.readouterr()
        prompt()
        context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ]
        opening, refused, *_ = context.split("\n")
        assert opening == hook_transport_model.ATTENTION_OPENING
        assert refused.startswith(
            f"- {page_dir.resolve()}: server was down and did not start again: "
        )
        assert reason in refused
        assert server_model.running_server(page_dir) is None
        assert read_record(page_dir / "service.json")["enabled"] is True

    prompt()
    assert server_model.running_server(page_dir) is not None
    assert capsys.readouterr().out == ""


def test_a_prompt_serves_only_a_page_its_session_still_means_to_serve(page_dir, capsys):
    """A retained record alone cannot have a prompt serve a page the agent stopped,
    one served persistently or as a preview, one another session or harness holds,
    one whose records this Leaf can't read, or one never served. Nor does a
    session's start serve the session's own page, whatever brought it back."""
    service = {
        "host": "127.0.0.1",
        "bind": "127.0.0.1",
        "port": available_loopback_port(),
        "enabled": True,
        "lifetime": "session",
        "server_id": "retired-server",
    }
    for case in (
        "stop",
        "persistent",
        "preview",
        "transferred",
        "foreign-harness",
        "obsolete-claim",
        "obsolete-service",
        "missing-service",
        "uninitialized-page",
        "new-session",
    ):
        sid = f"reconnect-{case}"
        record_claim(page_dir, id=sid)
        write_record(page_dir / "service.json", service)
        claim_path = service_model.CLAIM.file(service_model.claim_path(page_dir))
        raw = files_model.read_json(claim_path)
        service_file = server_model.SERVICE.file(page_dir / "service.json")
        # A Leaf of another shape's records, which this Leaf reads none of.
        older_claim = claim_path.with_name(
            f"{service_model.claim_path(page_dir).stem}@0.json"
        )
        older_service = page_dir / "service@0.json"
        watched = claim_path
        events = (page_dir / "events.jsonl").read_bytes()
        if case == "stop":
            assert not hosting_model.cmd_stop(page_dir)
        elif case == "persistent":
            write_record(
                page_dir / "service.json", {**service, "lifetime": "persistent"}
            )
        elif case == "preview":
            cleanup_model.write_json(
                service_model.PREVIEW.file(page_dir / "preview.json"), {}
            )
        elif case == "transferred":
            record_claim(page_dir, id="successor")
        elif case == "foreign-harness":
            record_claim(page_dir, id=sid, harness="codex")
        elif case == "obsolete-claim":
            cleanup_model.write_json(older_claim, {**raw, "format": "leaf-claim/0"})
            claim_path.unlink()
            watched = older_claim
        elif case == "obsolete-service":
            cleanup_model.write_json(
                older_service,
                {
                    **files_model.read_json(service_file),
                    "format": "leaf-service/0",
                },
            )
            service_file.unlink()
        elif case == "missing-service":
            service_file.unlink()
        elif case == "uninitialized-page":
            (page_dir / "events.jsonl").unlink()
        elif case == "new-session":
            sid = "never-claimed-a-leaf"
        claimed_before = watched.read_bytes()
        prompt(sid)
        assert "did not start again" not in capsys.readouterr().out, case
        assert server_model.running_server(page_dir) is None, case
        assert watched.read_bytes() == claimed_before, case
        (page_dir / "events.jsonl").write_bytes(events)
        service_model.PREVIEW.remove(page_dir / "preview.json")
        older_claim.unlink(missing_ok=True)
        older_service.unlink(missing_ok=True)

    record_claim(page_dir, id="reconnect-control")
    write_record(page_dir / "service.json", service)
    for source in ("startup", "compact", "resume"):
        hooks_model.cmd_hook(
            "claude-code",
            {
                "hook_event_name": "SessionStart",
                "session_id": "reconnect-control",
                "source": source,
            },
        )
        assert server_model.running_server(page_dir) is None, source
    prompt("reconnect-control")
    assert server_model.running_server(page_dir) is not None


@pytest.mark.parametrize(
    "resumed", ["after its end", "at an older protocol", "after a crash"]
)
def test_a_resumed_sessions_first_prompt_serves_its_page_again(
    page_dir, capsys, dead_pid, resumed
):
    """A resumed session holds a claim whose lifetime has gone, and its page's
    server retired with it, leaving the service enabled. Its first prompt takes the
    page back and serves it at the recorded address, taking a page at an older page
    protocol to this Leaf's first, as `leaf server start` would. The prompt's turn
    is the claim's, even after a crash, which leaves the old generation live under
    a dead process: a claim made after the prompt opened would start a generation
    with a turn of its own. The prompt hands that turn the input the user left
    meanwhile. The session's start serves nothing: it opens no turn."""
    if resumed == "after a crash":
        record_claim(page_dir, pid=dead_pid)
    else:
        record_claim(page_dir)
        cleanup_model.end_harness_instance("s1")
    port = available_loopback_port()
    fixture_service(page_dir, port, "session")
    left = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Still there?"}
    )
    if resumed == "at an older protocol":
        vendored_at_another_protocol(page_dir)
    capsys.readouterr()

    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "SessionStart", "session_id": "s1", "source": "resume"},
    )
    assert capsys.readouterr().out == ""
    assert server_model.running_server(page_dir) is None

    prompt(prompt_id="resumed")
    running = server_model.running_server(page_dir)
    assert running is not None and running["port"] == port
    assert registry_storage.layer_record(page_dir) is not None
    claim = service_model.page_claim(page_dir)
    assert service_model.claim_is_active(claim)
    assert claim is not None and claim["turn"] == "resumed"
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    [batch] = inlined(context)["batches"]
    assert [event["id"] for event in batch["events"]] == [left["id"]]
    assert hook_transport_model.ATTENTION_OPENING not in context
