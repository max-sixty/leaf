"""Tests scheduled by the measured cost of their boundary."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import LEAF_COMMAND
from interact_support import (
    COMPOSITE_TIMEOUT,
    PLUGIN_ROOT,
    STATED_TIMEOUT,
    acknowledged_through,
    append_carried_log_record,
    record_claim,
)
from model.test_hook_registration import _registered_hook_command

from leaf import files as files_model
from leaf import service as service_model
from leaf import state as cleanup_model


@pytest.mark.parametrize("event", ["PostToolBatch", "UserPromptSubmit"])
def test_the_registered_hook_delivers_or_says_nothing(claimed, event):
    """The harness command calls Leaf's launcher, and Leaf answers under uv.

    Exercise the exact registration, stdin, environment selection and returned
    context; an unowned session has nothing to hand over.
    """

    def run(payload, env=None):
        return subprocess.run(
            ["/bin/sh", "-c", _registered_hook_command("claude-code", event)],
            input=payload,
            env=(env or os.environ) | {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)},
            capture_output=True,
            text=True,
            timeout=COMPOSITE_TIMEOUT,
            check=False,
        )

    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    payload = json.dumps({"hook_event_name": event, "session_id": "s1"})
    claim_record = service_model.page_claim(claimed)
    assert claim_record is not None
    turn = claim_record["turn"]
    if event == "PostToolBatch":
        worker = run(
            json.dumps(
                {"hook_event_name": event, "session_id": "s1", "agent_id": "worker"}
            )
        )
        assert (worker.returncode, worker.stdout, worker.stderr) == (0, "", "")
        assert acknowledged_through(claimed) == 0
    answered = run(payload)
    assert answered.returncode == 0, answered.stderr
    assert answered.stdout, "nothing came back: the CLI never answered under uv"
    output = json.loads(answered.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == event
    context = output["hookSpecificOutput"]["additionalContext"]
    [batch] = json.loads(context.split("\n")[1])["batches"]
    assert [event["text"] for event in batch["events"]] == ["hi"]
    if event == "PostToolBatch":
        claim_record_2 = service_model.page_claim(claimed)
        assert claim_record_2 is not None
        assert claim_record_2["turn"] == turn
        claim_record_3 = service_model.page_claim(claimed)
        assert claim_record_3 is not None
        assert claim_record_3["turn_closed"] is None
        # The next tool boundary adds no repeated response-debt reminders.
        again = run(payload)
        assert (again.returncode, again.stdout, again.stderr) == (0, "", "")

    # The library answers an unowned session silently under uv as well.
    stranger = run(json.dumps({"hook_event_name": event, "session_id": "s2"}))
    assert (stranger.returncode, stranger.stdout, stranger.stderr) == (0, "", "")


def test_the_registered_session_end_releases_shared_claims_without_an_environment(
    page_dir, tmp_path
):
    """A fresh install releases another checkout's claims within harness shutdown.

    Only the launcher and standalone stdlib cleanup exist in this install, since
    each record's format names its own `since`. No package can be imported and uv
    refuses to run; macOS's system Python 3.9 exercises the same entry without
    site packages.
    """
    project = tmp_path / "cold-plugin"
    launcher = project / "bin/leaf"
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes((PLUGIN_ROOT / "bin/leaf").read_bytes())
    launcher.chmod(0o755)
    program = project / "src/leaf/state.py"
    program.parent.mkdir(parents=True)
    program.write_bytes((PLUGIN_ROOT / "src/leaf/state.py").read_bytes())
    tools = tmp_path / "tools"
    tools.mkdir()
    system_python = Path("/usr/bin/python3")
    (tools / "python3").symlink_to(
        system_python if system_python.exists() else sys.executable
    )
    uv_called = tmp_path / "uv-called"
    uv = tools / "uv"
    uv.write_text('#!/bin/sh\nprintf called > "$UV_CALLED"\nexit 99\n')
    uv.chmod(0o755)

    record_claim(page_dir, id="ended-session")
    marker_files = [
        cleanup_model.session_file("ended-session", cleanup_model.HOOKS_SUFFIX)
    ]
    for marker in marker_files:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("session evidence")
    claims = service_model.claim_path(page_dir).parent
    (claims / "malformed.json").write_text("{")
    (claims / "wrong-shape.json").write_text("[]")
    missing_page = tmp_path / "missing-page"
    missing_claim = {"id": "ended-session", "page": str(missing_page)}
    missing_path = service_model.claim_path(missing_page)
    cleanup_model.write_json(missing_path, missing_claim)
    foreign = page_dir.parent / "foreign-page"
    foreign.mkdir()
    (foreign / cleanup_model.EVENTS_FILE).touch()
    record_claim(foreign, id="another-session")
    foreign_claim = service_model.page_claim(foreign)

    done = subprocess.run(
        ["/bin/sh", "-c", _registered_hook_command("claude-code", "SessionEnd")],
        input=json.dumps(
            {"hook_event_name": "SessionEnd", "session_id": "ended-session"}
        ),
        env=os.environ
        | {
            "CLAUDE_PLUGIN_ROOT": str(project),
            "PATH": f"{tools}:/usr/bin:/bin",
            "UV_CALLED": str(uv_called),
        },
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert not uv_called.exists()
    assert not service_model.claim_is_active(service_model.page_claim(page_dir))
    assert not any(marker.exists() for marker in marker_files)
    assert service_model.page_claim(foreign) == foreign_claim
    assert files_model.read_json(missing_path) == missing_claim
    assert not missing_page.exists()

    # An empty shutdown needs neither a page nor a managed environment either.
    done = subprocess.run(
        ["/bin/sh", "-c", _registered_hook_command("claude-code", "SessionEnd")],
        input=json.dumps({"hook_event_name": "SessionEnd", "session_id": "empty"}),
        env=os.environ
        | {
            "CLAUDE_PLUGIN_ROOT": str(project),
            "PATH": f"{tools}:/usr/bin:/bin",
            "UV_CALLED": str(uv_called),
        },
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert not uv_called.exists()

    # The console and module entry use the same cleanup in a managed runtime.
    record_claim(page_dir, id="managed-session")
    done = subprocess.run(
        [*LEAF_COMMAND, "session-end"],
        input=json.dumps(
            {"hook_event_name": "SessionEnd", "session_id": "managed-session"}
        ),
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert not service_model.claim_is_active(service_model.page_claim(page_dir))
