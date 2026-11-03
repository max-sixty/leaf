"""A page server's lifetime: `server start`, `stop` and `run`, persistent, session and
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
    declared,
    fetch,
    fetch_hanging_up,
    install_payload,
    page_packages,
    publish,
    read_record,
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
from leaf.registry.storage import layer_record
from leaf_dev.page_fixtures import package_selection_args


def _another_selection(page_dir):
    """`page init` arguments selecting one more package than the page does, so the
    re-vendor changes what the page runs under."""
    extra = page_dir.parent / "extra"
    extra.mkdir()
    (extra / "overrides.css").write_text("/* another selection */\n")
    return package_selection_args((*page_packages(), "./extra"))


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
    original = server_model.running_server(page_dir)
    assert original is not None
    before = original["server_id"]
    claim = service_model.page_claim(page_dir)
    layer = layer_record(page_dir)
    assert layer is not None
    generation = layer["generation"]
    session_model.cmd_waiting(page_dir)
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

    selection = _another_selection(page_dir) if changed else []
    # Reusing the recorded URL can wait through native TCP cooldown before
    # preparation finishes, independently of the session's continued watch.
    revendored = subprocess.run(
        [*LEAF_COMMAND, "page", "init", *selection, str(page_dir)],
        capture_output=True,
        text=True,
        timeout=hosting_model.PORT_WAIT_SECONDS + STATED_TIMEOUT,
        check=False,
    )
    assert revendored.returncode == 0, revendored.stderr
    layer_2 = layer_record(page_dir)
    assert layer_2 is not None
    assert (layer_2["generation"] != generation) == changed
    assert (incarnation() != before) == changed
    assert (current := server_model.running_server(page_dir)) is not None
    assert current["url"] == url
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
    layer_3 = layer_record(page_dir)
    assert layer_3 is not None
    generation = layer_3["generation"]
    if service == "stopped":
        assert hosting_model.cmd_stop(page_dir) is True
    elif service == "orphaned":
        cleanup_model.end_session("other")

    result = CliRunner().invoke(
        cli_model.cli, ["page", "init", *_another_selection(page_dir), str(page_dir)]
    )

    layer_4 = layer_record(page_dir)
    assert layer_4 is not None
    revendored = layer_4["generation"] != generation
    if service == "foreign":
        assert result.exit_code == 1
        assert "served for another session" in result.output
        assert server_model.running_server(page_dir)
        assert not revendored
        return
    assert result.exit_code == 0, result.output
    assert revendored
    assert server_model.running_server(page_dir) is None
    assert not read_record(page_dir / "service.json")["enabled"]
    assert ("has no live session owner" in result.output) == (service == "orphaned")


@pytest.mark.parametrize("lifetime", ["persistent", "session"])
def test_init_restarts_a_served_page_onto_the_replacement_contract(
    page_dir, spawn, monkeypatch, lifetime
):
    """Re-vendoring a served page restarts its server under the recorded lifetime
    and URL, onto the new layer, and preserves the active revision contract."""
    publish(page_dir)
    old_plugin = install_payload(page_dir.parent / "old-plugin")

    if lifetime == "persistent":
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
        monkeypatch.delenv("CLAUDE_PID")
    old_server = spawn(
        [
            # The old plugin's own launcher, so `PLUGIN_ROOT` resolves into it and
            # this server answers out of the registry there rather than the
            # checkout's.
            old_plugin / "bin" / "leaf",
            "server",
            "run",
            str(page_dir),
            *(["--lifetime", "persistent"] if lifetime == "persistent" else []),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    reading = json.loads(old_server.stdout.readline())
    url = reading["url"]
    assert url.startswith("http://127.0.0.1:")
    assert reading["lifetime"] == lifetime
    prior_status = declared(page_dir)
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
    (project_layer / "overrides.css").write_text(":root { --accent: red; }\n")
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
    layer_5 = layer_record(page_dir)
    assert layer_5 is not None
    assert layer_5["packages"][-1] == "./packages/.leaf"
    # The old server went down with the restart, and this checkout's came up in its
    # place at the same URL, under the lifetime and claim it had.
    old_server.wait(timeout=STATED_TIMEOUT)
    assert (current := server_model.running_server(page_dir)) is not None
    assert current["url"] == url
    assert read_record(page_dir / "service.json")["lifetime"] == lifetime
    assert service_model.page_claim(page_dir) == prior_owner
    restored = declared(page_dir)
    assert restored == prior_status

    status, body = fetch(endpoint, data=json.dumps(comment).encode(), token=None)
    assert status == 200, body
    events = events_model.read_events(page_dir)
    assert [event["kind"] for event in events] == ["note", "comment"]
    assert events[-1]["attempt"] == comment["attempt"]


from interact_support import (
    command_findings,
    record_claim,
)
from model.test_server_lifetime import reaper_retires

from leaf import harness as harness_model
from leaf import schema as schema_model


def test_a_refused_revendor_leaves_the_running_server_alone(page_dir):
    """A malformed incoming registry is refused before the server goes down.

    A restart after the refusal would put this Leaf's server over the layer the
    page keeps, so a page vendored by another Leaf would be served by code its
    runtime does not speak. The same process answers at the same URL before and
    after, which is what `Leaf-Server`, the server's incarnation, says."""
    # Original decision evidence can outlive its declaration. The malformed
    # incoming registry, rather than that history, causes this refusal.
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1"><pre>A decision.</pre></lf-draft>',
        )
    )
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "d1",
            "action": "decide",
            "detail": {"decision": "approved"},
            "meaning": {
                "scope": "page",
                "unit": "d1",
                "depends": ["d1"],
                "answer": None,
            },
        },
    )
    started = start_server_command(
        page_dir, session_id=os.environ["CLAUDE_CODE_SESSION_ID"]
    )
    assert started.returncode == 0, started.stderr
    url = json.loads(started.stdout)["url"]
    state = urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()

    def incarnation():
        with urllib.request.urlopen(state) as response:
            return response.headers["Leaf-Server"], response.headers["Leaf-Layer"]

    before = incarnation()

    overlay = page_dir.parent / ".leaf"
    overlay.mkdir()
    (overlay / "registry.json").write_text("{broken")
    [refused] = command_findings("page", "init", "--package", "./.leaf", str(page_dir))

    assert refused.code == "registry-json"
    assert (current := server_model.running_server(page_dir)) is not None
    assert current["url"] == url
    assert incarnation() == before


def test_a_desktop_app_sessions_server_lives_as_long_as_the_app_session(
    page_dir, tmp_path, monkeypatch, dead_pid
):
    """The Claude desktop app stops a session's process to update, and resumes it
    only when the user opens the session, so a claim naming the process takes the
    page down while the user reads it in another window. The app's record of the
    session is the lifetime instead: the page stays served through the SessionEnd
    of the process's stop, comes back to the same generation when the session
    resumes, and retires once the record names another session or the user
    archives it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    record = (
        tmp_path
        / "Library/Application Support/Claude/claude-code-sessions/acct/org"
        / "local_one.json"
    )
    record.parent.mkdir(parents=True)
    app = {"cliSessionId": "app-session", "isArchived": False}
    cleanup_model.write_json(record, app)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "app-session")
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_one")
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    assert service_model.claim_page(page_dir)
    assert hosting_model.start_server(page_dir, harness=harness_model.session_harness())
    claim_record_2 = service_model.page_claim(page_dir)
    assert claim_record_2 is not None
    generation = claim_record_2["generation"]
    cleanup_model.end_harness_instance("app-session")
    assert not reaper_retires(page_dir, monkeypatch)
    assert server_model.running_server(page_dir)
    harness_2 = harness_model.session_harness()
    assert harness_2 is not None
    assert (
        cleanup_model.ensure_session("app-session", harness_2.lifetime())["generation"]
        == generation
    )
    assert service_model.claim_is_active(service_model.page_claim(page_dir))

    cleanup_model.write_json(record, {**app, "cliSessionId": "after-clear"})
    assert not service_model.claim_is_active(service_model.page_claim(page_dir))
    cleanup_model.write_json(record, {**app, "isArchived": True})
    assert reaper_retires(page_dir, monkeypatch)
    wait_for(
        lambda: server_model.running_server(page_dir),
        lambda running: not running,
        failure="the app session's server stayed up after it was archived",
    )


def test_a_live_session_can_take_over_an_existing_server(
    page_dir, session_process, managed_server
):
    first, second = session_process(), session_process()
    server = managed_server(page_dir, "first", first.pid)
    record_claim(page_dir, id="second", pid=second.pid, agent="Codex")
    first.terminate()
    first.wait(timeout=STATED_TIMEOUT)
    assert server.poll() is None

    second.terminate()
    second.wait(timeout=STATED_TIMEOUT)
    server.wait(timeout=STATED_TIMEOUT)
    assert server.returncode == 0, server.stderr.read()
    assert read_record(page_dir / "service.json")["enabled"] is True


def test_server_start_hands_the_page_to_a_process_of_its_own(page_dir):
    """The command returns and the page stays up. Two long-running commands per
    leaf was one accident: `leaf wait` has to exit, its exit being how a comment
    reaches the agent, and the server has to not exit at all — so no one process
    does both, but only the watcher is the session's to hold open. The serve gets
    a session of its own, which is also what leaves a killed background task
    costing the watcher alone."""
    started = start_server_command(page_dir)
    assert started.returncode == 0, started.stderr
    reading = json.loads(started.stdout)
    url = reading["url"]
    assert url.startswith("http://127.0.0.1:")
    assert reading["lifetime"] == "session"
    info = server_model.running_server(page_dir)
    assert info and info["url"] == url
    # The child claims only after its refusal and bind checks, which is what lets
    # the loop's hooks find the session's pages without a failed start taking one.
    claim_record_3 = service_model.page_claim(page_dir)
    assert claim_record_3 is not None
    assert claim_record_3["id"] == "starter"
    service = server_model.read_service(page_dir)
    assert service is not None
    assert service["lifetime"] == "session"
    assert set(service) == {
        "host",
        "bind",
        "port",
        "enabled",
        "lifetime",
        "runtime",
        "server_id",
    }
    assert service["runtime"]["path"] == str(schema_model.PLUGIN_ROOT)
    state = urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()
    response = urllib.request.urlopen(state)
    assert response.status == 200
    assert response.headers["Leaf-Server"] == service["server_id"]


def test_server_start_forwards_flags_and_returns_service_output(page_dir):
    """`server start` states nothing about a serve itself. The flags go verbatim
    to the service it spawns and the account comes back from there, so the
    lifetime a flag declared and the refusal a running server earns are both that
    process's own words, carried out with its exit status."""
    persistent = start_server_command(page_dir, "--lifetime", "persistent")
    assert persistent.returncode == 0, persistent.stderr
    assert json.loads(persistent.stdout)["lifetime"] == "persistent"
    assert read_record(page_dir / "service.json")["lifetime"] == "persistent"
    assert service_model.page_claim(page_dir) is None

    refused = start_server_command(page_dir, "--host", "devbox.corp.example")
    assert refused.returncode != 0
    assert "already serving at" in refused.stderr
    assert "server stop" in refused.stderr
    # Nothing on stdout, so a caller reading the URL there reads no URL.
    assert not refused.stdout.strip()
    assert service_model.page_claim(page_dir) is None


def test_a_sessionless_server_ignores_a_stale_claim_and_requires_explicit_stop(
    page_dir, dead_pid, persistent_server, monkeypatch
):
    record_claim(page_dir, id="old-session", pid=dead_pid, agent="Codex")
    server = persistent_server(page_dir)
    assert not reaper_retires(page_dir, monkeypatch)
    assert server.poll() is None, "a manual server inherited the stale session claim"
    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)


def test_a_persistent_server_outlives_a_session_that_picks_the_page_up(
    page_dir, persistent_server, monkeypatch, capsys
):
    """The persistent serve, the whole way round: a page kept up across sessions, and a
    session that works on it for an afternoon and goes. Picking a page up earns the
    watch obligation and nothing else, so the session's end must take down neither the
    process it didn't start nor a leaf that outlives it."""
    server = persistent_server(page_dir)
    launched = server_model.running_server(page_dir)
    assert launched is not None
    assert read_record(page_dir / "service.json")["lifetime"] == "persistent"

    # A session picks the page up, the way `leaf wait` does.
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "later")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    session_model.cmd_waiting(page_dir)
    # Without this the hook would skip the page for the wrong reason and the test
    # would pass with the bug in: the persistent check has to be what spares it.
    assert page_dir in service_model.owned_pages("later")

    # A `server run` of its own finds this one up and reports the lifetime the
    # running server has, not the one this claiming launch would have given it.
    hosting_model.cmd_serve(page_dir, harness=harness_model.session_harness())
    served = json.loads(capsys.readouterr().out)
    assert (served["url"], served["lifetime"]) == (launched["url"], "persistent")

    cleanup_model.end_harness_instance("later")

    # The synchronous hook left the persistent service enabled and live.
    assert server_model.running_server(page_dir) == launched
    assert declared(page_dir)["state"] == "waiting"
    assert not service_model.claim_is_active(service_model.page_claim(page_dir))
    assert page_dir not in service_model.owned_pages("later")
    # Explicit stop crosses that server's release barrier before returning.
    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)
