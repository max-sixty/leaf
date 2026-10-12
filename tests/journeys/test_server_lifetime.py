"""A page server's lifetime: `server start`, `stop` and `run`, standing, session and
background-job lifetimes, the reaper that retires a server, and restarts across a
re-vendor."""

import json
import os
import subprocess
import urllib.parse
import urllib.request

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    fetch,
    fetch_hanging_up,
    install_payload,
    page_packages,
    publish,
    start_server_command,
    wait_for,
    woken,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf import leases as leases_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf_dev.page_fixtures import package_selection_args


@pytest.mark.parametrize("changed", [False, True])
def test_page_init_restarts_a_served_page_under_the_sessions_wait(
    page_dir, tmp_path, spawn, changed
):
    """`page init` on a served page restarts its server itself, so the session's
    `leaf wait` carries on watching it.

    Re-vendoring a served page used to be three commands, and the first,
    `server stop`, disabled the service: a wait watching the page read that as a
    page it had lost, and ended. The comment after the re-vendor is the proof: only
    a wait still watching delivers it.
    """
    publish(page_dir)
    session = os.environ["CLAUDE_CODE_SESSION_ID"]
    started = start_server_command(page_dir, session_id=session)
    assert started.returncode == 0, started.stderr
    url = json.loads(started.stdout)["url"]
    state = urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()

    def incarnation():
        with urllib.request.urlopen(state) as response:
            return response.headers["Leaf-Server"]

    # The record names the serving incarnation, which its responses carry as
    # `Leaf-Server`. Read the record rather than the server: a fetch the server
    # closes leaves the port in TIME_WAIT, and the restart would wait that out.
    before = server_model.running_server(page_dir)["server_id"]
    claim = service_model.page_claim(page_dir)
    generation = files_model.read_json(page_dir / "registry.json")["$layer"][
        "generation"
    ]
    session_model.cmd_waiting(page_dir, "review the page")
    waited = tmp_path / "wait.log"
    with waited.open("w", encoding="utf-8") as output:
        waiter = spawn(
            [*LEAF_COMMAND, "wait"],
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )
    wait_for(
        lambda: waiter.poll() is None and leases_model.wait_is_live(page_dir, session),
        bool,
        failure="the wait did not start watching the page",
    )

    if changed:
        theme = page_dir / "theme.css"
        theme.write_text(theme.read_text() + "\n/* repair installed edit */\n")
    # Reusing the recorded URL can wait through native TCP cooldown before
    # preparation finishes, independently of the session's continued watch.
    revendored = subprocess.run(
        [*LEAF_COMMAND, "page", "init", str(page_dir)],
        capture_output=True,
        text=True,
        timeout=hosting_model.PORT_WAIT_SECONDS + STATED_TIMEOUT,
        check=False,
    )
    assert revendored.returncode == 0, revendored.stderr
    assert (
        files_model.read_json(page_dir / "registry.json")["$layer"]["generation"]
        != generation
    ) == changed
    assert (incarnation() != before) == changed
    assert server_model.running_server(page_dir)["url"] == url
    # The restart claims nothing, so the turn the claim records is left as it was.
    assert service_model.page_claim(page_dir) == claim
    assert waiter.poll() is None, waited.read_text()

    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "text": "still there?",
        },
    )
    assert waiter.wait(timeout=STATED_TIMEOUT) == 0, waited.read_text()
    _, batch, [event] = woken(waited.read_text())
    assert batch["page"] == str(page_dir)
    assert event["text"] == "still there?"


@pytest.mark.parametrize("service", ["stopped", "orphaned", "foreign"])
def test_page_init_leaves_a_service_it_cannot_restart_for_this_session(
    page_dir, service
):
    """Only an enabled service this command may restart comes back.

    A stopped service was stopped on purpose and stays stopped. A session service
    whose session has ended has nobody to come back for, so the re-vendor stops it
    and leaves it for the next `server start`. One another live session holds is
    refused before anything stops, since only that session could start it again.
    """
    publish(page_dir)
    started = start_server_command(page_dir, session_id="other")
    assert started.returncode == 0, started.stderr
    generation = files_model.read_json(page_dir / "registry.json")["$layer"][
        "generation"
    ]
    if service == "stopped":
        assert hosting_model.cmd_stop(page_dir) is True
    elif service == "orphaned":
        cleanup_model.end_session("other")

    theme = page_dir / "theme.css"
    theme.write_text(theme.read_text() + "\n/* repair installed edit */\n")
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    revendored = (
        files_model.read_json(page_dir / "registry.json")["$layer"]["generation"]
        != generation
    )
    if service == "foreign":
        assert result.exit_code == 1
        assert "served for another session" in result.output
        assert server_model.running_server(page_dir)
        assert not revendored
        return
    assert result.exit_code == 0, result.output
    assert revendored
    assert server_model.running_server(page_dir) is None
    assert not files_model.read_json(page_dir / "service.json")["enabled"]
    assert ("has no live session owner" in result.output) == (service == "orphaned")


@pytest.mark.parametrize("lifetime", ["standing", "session"])
def test_init_restarts_a_served_page_onto_the_replacement_contract(
    page_dir, spawn, monkeypatch, lifetime
):
    """Re-vendoring a served page restarts its server under the recorded lifetime
    and URL, onto the new layer, and preserves the active revision contract."""
    publish(page_dir)
    old_plugin = install_payload(page_dir.parent / "old-plugin")

    if lifetime == "standing":
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
        monkeypatch.delenv("CLAUDE_PID")
    old_server = spawn(
        [
            # The old plugin's own launcher, so `SKILL_ROOT` resolves into it and
            # this server answers out of the registry there rather than the
            # checkout's.
            old_plugin / "bin" / "leaf",
            "server",
            "run",
            str(page_dir),
            *(["--standing"] if lifetime == "standing" else []),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = json.loads(old_server.stdout.readline())["url"]
    assert url.startswith("http://127.0.0.1:")
    assert old_server.stderr.readline().startswith(f"server   {lifetime}")
    prior_status = service_model.read_status(page_dir)
    prior_owner = service_model.page_claim(page_dir)

    endpoint = urllib.parse.urlsplit(url)._replace(path="/api/event").geturl()
    comment = {
        "kind": "comment",
        "revision": 1,
        "text": "Can the replacement route this?",
        "attempt": "replacement_route_1",
    }
    status, body = fetch_hanging_up(endpoint, json.dumps(comment).encode())
    assert status == 200, body

    project_layer = page_dir.parent / ".leaf"
    project_layer.mkdir()
    (project_layer / "theme.css").write_text(":root { --accent: red; }\n")
    revendored = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )
    assert revendored.exit_code == 0, revendored.output
    assert b":root { --accent: red; }" in (page_dir / "theme.css").read_bytes()
    # The old server went down with the restart, and this checkout's came up in its
    # place at the same URL, under the lifetime and claim it had.
    old_server.wait(timeout=STATED_TIMEOUT)
    assert server_model.running_server(page_dir)["url"] == url
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == lifetime
    assert service_model.page_claim(page_dir) == prior_owner
    restored = service_model.read_status(page_dir)
    assert restored == prior_status

    status, body = fetch(endpoint, data=json.dumps(comment).encode(), token=None)
    assert status == 200, body
    events = events_model.read_events(page_dir)
    assert [event["kind"] for event in events] == ["note", "comment"]
    assert events[-1]["attempt"] == comment["attempt"]
