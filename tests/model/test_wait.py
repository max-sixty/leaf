"""Watching a page between turns: `leaf wait` and the background Stop hook's watch,
what each watches and what wakes it, when a wait ends, bare-shell and Codex watcher
waits, the one wait a page answers to, reviving a server that died under a wait,
and messaging a Claude Code session nothing watches."""

import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    HELD_LEASES,
    STATED_TIMEOUT,
    _interaction_prompt_evidence,
    append_carried_log_record,
    append_command,
    available_loopback_port,
    claim_and_wait_command,
    declare_idle,
    delivered,
    fifo_writer,
    hold_status_read,
    last_deliverable_seq,
    page_state,
    printed,
    publish,
    receive_through,
    record_claim,
    said,
    serving,
    vendored_at_another_protocol,
    wait_for,
    woken,
    working,
    yaml_document,
)
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import hooks as hooks_model
from leaf import hosting as hosting_model
from leaf import leases as leases_model
from leaf import schema as schema_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from leaf import vendoring as vendoring_model
from leaf.detached import StartRefused


def test_wait_prints_unacknowledged_input_without_receipt_or_pickup(
    page_dir, sessionless, capsys
):
    # A held server.lock lease is what wait's liveness probe asks for.
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "b",
            "action": "move",
            "detail": {"unit": "x", "value": "y", "rank": "0i"},
            "meaning": {
                "scope": "page",
                "unit": "x",
                "depends": ["b", "x", "y"],
            },
        },
    )
    assert session_model.cmd_wait(page_dir) == 0
    payload, header, shown = printed(capsys.readouterr().out)
    assert header["page"] == str(page_dir)
    assert [e["kind"] for e in shown] == ["comment", "action"]
    assert shown[1]["detail"]["value"] == "y"
    # Printing is not acknowledgement: a detached Codex command can finish without
    # putting its output in the model's context, so wait leaves both events pending.
    assert files_model.read_json(page_dir / "cursor.json") is None
    assert page_state(page_dir)["pending"] == 2

    # An event posted between wait and acknowledgement is beyond the highest sequence
    # the model saw. Acknowledging that visible batch therefore leaves the newcomer.
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c2", "author": "user", "text": "later"}
    )
    delivered_through = shown[-1]["seq"]
    assert not any(
        event["kind"] == "pickup" for event in events_model.read_events(page_dir)
    )
    delivery_model.receive_delivery(payload["id"])
    delivery_model.receive_delivery(payload["id"])  # retries are harmless
    assert files_model.read_json(page_dir / "cursor.json")["seq"] == delivered_through
    assert page_state(page_dir)["pending"] == 1

    assert session_model.cmd_wait(page_dir) == 0
    _, _, later_events = printed(capsys.readouterr().out)
    [later] = later_events
    assert later["id"] == "c2"
    receive_through(page_dir, later["seq"])
    assert page_state(page_dir)["pending"] == 0
    # Pickup is exact log evidence and does not rewrite the agent's page-wide claim.
    status = service_model.read_status(page_dir)
    assert status["state"] == "waiting"
    pickups = [e for e in events_model.read_events(page_dir) if e["kind"] == "pickup"]
    assert [e["events"] for e in pickups] == [["c1", shown[1]["id"]], ["c2"]]
    stored = [
        json.loads(line)
        for line in (page_dir / "events.jsonl").read_text().splitlines()
    ]
    assert all("seq" not in event for event in stored if event["kind"] == "pickup")
    working(page_dir, "revising the plan")
    assert page_state(page_dir)["activity"]["detail"] == "revising the plan"

    # A worker's report wakes the watcher like a user event — it is the
    # orchestrator's to fold into a version — but the user's banner count
    # deliberately leaves it out: a report is news the agent owes the page, not
    # something the user owes an answer.
    append_carried_log_record(
        page_dir,
        {
            "kind": "report",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "widget": "t1",
            "meaning": {
                "scope": "page",
                "unit": "t1",
                "depends": ["t1"],
            },
            "action": "status",
            "detail": {"value": "review"},
            "revision": 1,
        },
    )
    assert page_state(page_dir)["pending"] == 0
    assert session_model.cmd_wait(page_dir) == 0
    _, _, shown = printed(capsys.readouterr().out)
    assert [(e["kind"], e.get("agent")) for e in shown] == [("report", "Indexer")]
    receive_through(page_dir, shown[-1]["seq"])
    assert files_model.read_json(page_dir / "cursor.json")["seq"] == shown[-1]["seq"]


def test_wait_repeats_a_stable_transport_neutral_batch_until_ack(page_dir, sessionless):
    """Repeated waits retain every input fact until receipt. Each delivery qualifies
    its own reply address; either address reaches the same input without a second answer."""
    serving(page_dir, 1)
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    )

    first = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert first.exit_code == 0, first.output
    first_payload, header, [event] = printed(first.output)
    assert header["page"] == str(page_dir)
    assert (event["id"], event["seq"], event["text"]) == ("c1", 1, "hi")
    assert files_model.read_json(page_dir / "cursor.json") is None

    reread = CliRunner().invoke(
        cli_model.cli, ["delivery", "read", first_payload["id"]]
    )
    assert reread.exit_code == 0, reread.output
    assert json.loads(reread.output) == first_payload
    invalid = CliRunner().invoke(cli_model.cli, ["delivery", "read", "../status"])
    assert invalid.exit_code != 0
    assert "invalid delivery id" in invalid.output

    retry = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert retry.exit_code == 0, retry.output
    retry_payload, retry_batch, _ = printed(retry.output)
    retry_ref = retry_batch["events"][0]["answer"]["ref"]
    first_ref = event["answer"]["ref"]
    assert retry_batch == {
        **header,
        "events": [{**event, "answer": {**event["answer"], "ref": retry_ref}}],
    }
    assert retry_payload["id"] != first_payload["id"]
    assert delivery_model.read_delivery(first_payload["id"]) == first_payload
    pickups = [e for e in events_model.read_events(page_dir) if e["kind"] == "pickup"]
    assert pickups == []

    # If wait output was lost or truncated, retrieving it again before ack can
    # include a newer event. The old event keeps the same page-and-seq identity
    # for the receiving task to skip.
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c2", "author": "user", "text": "later"}
    )
    grown = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert grown.exit_code == 0, grown.output
    _, grown_header, grown_events = printed(grown.output)
    assert grown_header["page"] == header["page"]
    assert grown_header["threads"][0] == header["threads"][0]
    assert [thread["id"] for thread in grown_header["threads"]] == ["c1", "c2"]
    assert grown_header["through_seq"] == 2
    assert [event["seq"] for event in grown_events] == [1, 2]

    progress = CliRunner().invoke(
        cli_model.cli,
        ["response", "reply", first_ref, "--ephemeral", "--text", "Checking"],
    )
    assert progress.exit_code == 0, progress.output
    assert json.loads(progress.output)["parent"] == event["id"]
    answered = CliRunner().invoke(
        cli_model.cli, ["response", "reply", "--done", retry_ref, "--text", "Hello"]
    )
    assert answered.exit_code == 0, answered.output
    reply = json.loads(answered.output)
    assert reply["responds"] == event["id"]
    retried = CliRunner().invoke(
        cli_model.cli, ["response", "reply", "--done", retry_ref, "--text", "Hello"]
    )
    assert retried.exit_code == 0, retried.output
    assert json.loads(retried.output) == reply
    assert thread_model.successful_replies(
        events_model.read_events(page_dir), event["id"]
    ) == [reply]
    assert set(
        delivery_model.current_responses(page_dir, events_model.read_events(page_dir))
    ) == {"c2"}


def test_wait_preserves_the_work_in_hand_on_mid_work_output(page_dir, capsys):
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    working(page_dir, "running the browser suite")
    status_path = page_dir / "status.json"
    before = status_path.read_bytes()
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "one more thing"},
    )

    service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    _, _, shown = delivered(capsys)
    assert [event["id"] for event in shown] == ["c1"]
    assert status_path.read_bytes() == before
    [task] = page_state(page_dir)["browser"]["todos"]
    assert task["running"]["text"] == "running the browser suite"


def test_a_wait_watches_a_stopped_server_until_its_page_ends(
    page_dir, monkeypatch, capsys
):
    """A stopped server neither ends a `leaf wait` nor is the wait's to start
    again: the page ends the wait, by going idle or changing hands.

    A wait used to read a disabled service as a page it had lost, and end, so
    every restart, which disables the service as a stop does, had to say it was
    not a stop."""
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "persistent",
        },
    )
    session_model.cmd_waiting(page_dir, "review the page")

    def unexpected_start(*_args, **_kwargs):
        pytest.fail("a disabled service was revived")

    monkeypatch.setattr(hosting_model, "start_server", unexpected_start)
    assert hosting_model.cmd_stop(page_dir) is False

    def unexpected_delivery(reading):
        pytest.fail(f"nothing was sent, yet {reading.page_dir} delivered")

    watch = session_model.Watch(None, pages=(page_dir,))
    try:
        assert watch.acquire()
        passed = session_model.read_watch_pass(watch, page_dir, unexpected_delivery)
    finally:
        watch.release()
    assert passed.outcome is None
    assert [reading.page_dir for reading in passed.live] == [page_dir]

    declare_idle(page_dir)
    capsys.readouterr()
    service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 2
    assert "the page closed" in capsys.readouterr().err


@pytest.mark.parametrize("revival", ["refused", "died again"])
def test_a_revival_that_does_not_hold_ends_the_wait(
    page_dir, monkeypatch, capsys, revival
):
    """An enabled service whose process died gets one revival. When that does not
    bring it back, refused or dead again once it did, nothing else will, so the
    wait ends and wakes the agent with the command that serves the page."""
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "persistent",
        },
    )
    session_model.cmd_waiting(page_dir, "review the page")

    def refused_start(*_args, **_kwargs):
        raise StartRefused("the port is taken")

    def start_that_dies(*_args, **_kwargs):
        return hosting_model.PageStart("http://127.0.0.1:1/", None, page_dir)

    monkeypatch.setattr(
        hosting_model,
        "start_server",
        refused_start if revival == "refused" else start_that_dies,
    )

    def unexpected_delivery(reading):
        pytest.fail(f"nothing was sent, yet {reading.page_dir} delivered")

    watch = session_model.Watch(None, pages=(page_dir,))
    try:
        assert watch.acquire()
        passed = session_model.read_watch_pass(watch, page_dir, unexpected_delivery)
        if revival == "died again":
            assert passed.outcome is None
            # Past the recheck interval, as the next pass five seconds on would be.
            watch._check_at.clear()
            passed = session_model.read_watch_pass(watch, page_dir, unexpected_delivery)
    finally:
        watch.release()

    assert passed.outcome == 2
    assert (
        f"{page_dir}: server is not running; restart it with "
        f"`leaf server start {page_dir}`"
    ) in capsys.readouterr().err


def test_a_page_without_a_declaration_leaves_the_sessions_wait_running(
    page_dir, tmp_path
):
    """A claimed page whose agent has declared nothing, such as a copy served
    before any `leaf status`, reads as waiting on its user: the session's wait
    passes over it and still delivers a sibling page's comment, and the copy's
    own state reads as listening. The copy sorts ahead of the page, so a pass
    that stumbled on it would end before reaching the comment."""
    publish(page_dir)
    serving(page_dir, 1)
    service_model.claim_page(page_dir)
    copy = tmp_path / "copy"
    shutil.copytree(page_dir, copy)
    (copy / schema_model.STATUS_FILE).unlink(missing_ok=True)
    serving(copy, 1)
    service_model.claim_page(copy)
    assert service_model.owned_pages(session_model.session_harness().session) == [
        copy.resolve(),
        page_dir.resolve(),
    ]
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "still there?"},
    )

    waited = CliRunner().invoke(cli_model.cli, ["wait"])

    assert waited.exit_code == 0, waited.output
    _, batch, shown = woken(waited.output)
    assert batch["page"] == str(page_dir.resolve())
    assert [event["id"] for event in shown] == [comment["id"]]
    assert page_state(copy)["activity"]["kind"] == "listening"


@pytest.mark.parametrize("wait", ["named", "session"])
def test_a_wait_on_a_page_never_served_ends_at_once(page_dir, capsys, wait):
    """A page with no service record has nothing that will serve it, so a wait
    on it ends on its first pass with the command that does, whether it was
    named or claimed earlier and found by the session's wait."""
    assert not (page_dir / "service.json").exists()
    session_model.cmd_waiting(page_dir, "review the page")
    service_model.claim_page(page_dir)

    def unexpected_delivery(reading):
        pytest.fail(f"nothing was sent, yet {reading.page_dir} delivered")

    named = page_dir if wait == "named" else None
    watch = session_model.Watch(
        harness_model.session_harness(), pages=(page_dir,) if named else ()
    )
    try:
        assert watch.acquire()
        passed = session_model.read_watch_pass(watch, named, unexpected_delivery)
    finally:
        watch.release()

    assert passed.outcome == 2
    assert f"restart it with `leaf server start {page_dir}`" in (
        capsys.readouterr().err
    )


def test_a_delayed_revival_cannot_cross_an_explicit_stop(page_dir, monkeypatch):
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    working(page_dir, "watching for a reply")
    entered, release = threading.Event(), threading.Event()
    real_start = hosting_model.start_server

    def delayed_start(*args, **kwargs):
        entered.set()
        assert release.wait(STATED_TIMEOUT)
        return real_start(*args, **kwargs)

    monkeypatch.setattr(hosting_model, "start_server", delayed_start)
    readings, errors = [], []
    watch = session_model.Watch(None, pages=(page_dir,))
    assert watch.acquire()

    def tick():
        try:
            readings.extend(watch.tick())
        except BaseException as error:  # noqa: BLE001 - carried to the assertion
            errors.append(error)
        finally:
            watch.release()

    reviving = threading.Thread(target=tick)
    reviving.start()
    assert entered.wait(STATED_TIMEOUT), "the watcher did not decide to revive"
    assert hosting_model.cmd_stop(page_dir) is False
    release.set()
    reviving.join(timeout=STATED_TIMEOUT)
    assert not reviving.is_alive(), "the revival never finished its tick"

    assert not reviving.is_alive()
    assert errors == []
    # The stop disabled the service, which the wait goes on watching.
    assert readings[0].watch_state == "watching"
    assert readings[0].lost is False
    assert readings[0].restarted is None
    assert files_model.read_json(page_dir / "service.json")["enabled"] is False
    assert not leases_model.lock_is_held(page_dir / "server.lock")


def test_wait_restarts_a_server_that_died_under_it(
    page_dir, comment_once_served, capsys, snapshot
):
    """A page whose server died is offline in the user's browser and nowhere
    else — so `leaf wait`, the one thing positioned to notice, brings it back
    rather than exiting and leaving the discovery to the user."""

    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    comment_once_served(page_dir)
    service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    info = server_model.running_server(page_dir)
    # The revived server has to answer on the URL it published, key included:
    # the user's browser has been polling that address since it died.
    assert info
    state = urllib.parse.urlsplit(info["url"])
    assert (
        urllib.request.urlopen(state._replace(path="/api/state").geturl()).status == 200
    )
    printed = capsys.readouterr()
    assert "server had died; restarted" in printed.err
    snapshot.check(
        yaml_document(
            "A wait revives its server, notes the recovery, and delivers input.\n"
            "The URL's dynamic port and access token are represented by <served-url>.",
            _interaction_prompt_evidence(
                page_dir,
                {
                    "exit": 0,
                    "stderr": said(printed.err.replace(info["url"], "<served-url>")),
                },
            ),
        )
    )
    # This session explicitly claimed the page, so what the wait revives is its
    # session's server and dies with that session. Here the session is the
    # worker (conftest), which is what keeps a killed run from stranding this.
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == "session"


def test_wait_does_not_revive_a_page_another_leaf_vendored(page_dir, capsys):
    """A server that died under a page another Leaf has since been updated past
    stays down: the wait's revival is a start like any other, served by the Leaf
    running the wait. The page reads as lost, and the refusal reaches the agent
    reading the wait with the re-vendor that brings it back."""
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    assert service_model.claim_page(page_dir)
    session_model.cmd_waiting(page_dir, "review the page")
    vendored_at_another_protocol(page_dir)

    # One pass first, so a revival that went through fails here rather than
    # leaving the wait below holding a live page open for input.
    watch = session_model.Watch(harness_model.session_harness(), pages=(page_dir,))
    try:
        assert watch.acquire()
        reading = next(watch.tick())
    finally:
        watch.release()
    assert reading.lost is True
    assert reading.restarted is None
    assert server_model.running_server(page_dir) is None
    refused = capsys.readouterr().err
    assert f"leaf page init {page_dir}" in refused

    assert session_model.cmd_wait(page_dir) == 2
    printed = capsys.readouterr().err
    assert f"leaf page init {page_dir}" in printed
    assert "server had died; restarted" not in printed


def test_wait_revival_cannot_take_a_page_back_after_claim_transfer(
    codex_claimed_page, under_codex, codex_env, monkeypatch
):
    """A stale wait cannot revive a server for a page it no longer owns.

    The FIFO holds the status read after the waiter selected the page but
    before it checks the dead server. Another session then claims the page. The
    old wait must leave without spawning a server under its stale ownership
    decision.
    """
    page = codex_claimed_page
    hosting_model.cmd_stop(page)
    session_model.cmd_waiting(page, "comment on the prototype")
    status_path = page / "status.json"
    hold_status_read(status_path)
    first = under_codex(
        claim_and_wait_command(page),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    writer = fifo_writer(status_path, "the waiter never reached its held status read")

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page)
    os.write(
        writer,
        json.dumps(
            {
                "state": "waiting",
                "detail": "comment on the prototype",
                "ts": "t",
            }
        ).encode(),
    )
    os.close(writer)
    declare_idle(page)

    first_out, first_err = first.communicate(timeout=STATED_TIMEOUT)
    assert (first.returncode, first_out) == (2, ""), first_err
    assert "no longer owns it" in first_err
    assert "the page closed" not in first_err
    session = service_model.page_claim(page)
    assert session["id"] == "replacement"
    assert server_model.running_server(page) is None


def test_session_end_cannot_be_overtaken_by_wait_revival(claimed, spawn):
    """The session-end reaper must outrank a wait's stale live-page snapshot.

    The FIFO holds the wait after it selected the page but before it checks the
    dead server. SessionEnd then releases its claim. Releasing the stale status
    read must not let that wait put a session server back up.
    """
    page = claimed
    cleanup_model.write_json(
        page / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    session_model.cmd_waiting(page, "comment on the prototype")
    status_path = page / "status.json"
    hold_status_read(status_path)
    waiter = spawn(
        [*LEAF_COMMAND, "wait", str(page)],
        env=os.environ
        | {"CLAUDE_CODE_SESSION_ID": "s1", "CLAUDE_PID": str(os.getpid())},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    writer = fifo_writer(status_path, "the waiter never reached its held status read")

    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "SessionEnd", "session_id": "s1"}
    )
    assert files_model.read_json(page / "service.json")["enabled"] is True
    assert server_model.running_server(page) is None

    os.write(
        writer,
        json.dumps(
            {
                "state": "waiting",
                "detail": "comment on the prototype",
                "ts": "t",
            }
        ).encode(),
    )
    os.close(writer)

    out, err = waiter.communicate(timeout=STATED_TIMEOUT)
    assert waiter.returncode == 2, f"{out}{err}"
    assert "this session no longer owns it" in err
    assert not service_model.claim_is_active(service_model.page_claim(page))
    assert server_model.running_server(page) is None
    # SessionEnd releases ownership only. The FIFO remains the same status path;
    # lifecycle code did not replace it with an authored idle state.
    assert status_path.is_fifo()


def test_a_revived_server_keeps_the_lifetime_it_was_serving_under(
    claimed, comment_once_served
):
    """A persistent page comes back persistent. The lifetime is the page's record
    rather than the reviving process's, so the restarts a page doesn't choose —
    a crash, the revival a `leaf wait` makes under it — leave it as the serve
    that started it declared, and `leaf server stop` is still the one thing that
    ends one. Read off the launch instead, a session that happened to notice the
    server was down would inherit a dashboard somebody left up for weeks, and
    take it down when it ended."""
    cleanup_model.write_json(
        claimed / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "persistent",
        },
    )
    comment_once_served(claimed)
    assert session_model.cmd_wait(claimed) == 0
    # The reviving session did claim the page, so a lifetime read off this
    # launch would have said "session" — the claim is what the persistent
    # record has to outrank.
    assert service_model.page_claim(claimed)["id"] == "s1"
    assert files_model.read_json(claimed / "service.json")["lifetime"] == "persistent"


def test_wait_ends_when_the_leaf_does(page_dir, capsys, snapshot):
    """Idling is how a leaf ends, and it has to reach the watcher: a wait that
    held on past it left a long-running command open for a page nobody was going
    to press. The server is not
    the watcher's to end — a user is free to stay on a page the agent has
    finished with — so it is left exactly as it stands."""
    serving(page_dir, 1)
    declare_idle(page_dir)
    service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 2
    assert server_model.running_server(page_dir)
    served = capsys.readouterr()

    # And where SessionEnd idled the page and stopped its server both, a watcher
    # still winding down must not put it straight back up. Dropping the lease is
    # what makes the server read as dead.
    leases_model.release_lease(HELD_LEASES.pop())
    assert session_model.cmd_wait(page_dir) == 2
    assert server_model.running_server(page_dir) is None
    stopped = capsys.readouterr()
    snapshot.check(
        yaml_document(
            "An idle page ends its wait whether the server is still running or stopped.",
            _interaction_prompt_evidence(
                page_dir,
                {
                    "still served": {
                        "exit": 2,
                        "stdout": served.out,
                        "stderr": said(served.err),
                    },
                    "server stopped": {
                        "exit": 2,
                        "stdout": stopped.out,
                        "stderr": said(stopped.err),
                    },
                },
            ),
        )
    )


def test_one_wait_watches_every_page_the_session_holds(
    page_dir, tmp_path, monkeypatch, capsys
):
    """A session's leaves share one watcher. The watch set is the session's own
    pages rather than the argument, so four leaves cost one command between
    them, and the line that wakes the session says which page spoke."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s9")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    leases_model.mark_hooks("s9")  # its harness runs Leaf's hooks
    second = tmp_path / "second"
    vendoring_model.cmd_init(second)
    capsys.readouterr()
    session_model.cmd_waiting(second, "")
    session_model.cmd_waiting(page_dir, "")
    serving(page_dir, 1)
    serving(second, 2)
    for d in (page_dir, second):
        assert service_model.claim_page(d)
    append_carried_log_record(
        second, {"kind": "comment", "author": "user", "text": "hi"}
    )

    assert session_model.cmd_wait() == 0
    woke = capsys.readouterr().out
    assert json.loads(woke)["batches"][0]["page"] == str(second)
    _, batch, shown = woken(woke)
    assert batch["page"] == str(second)
    assert [event["text"] for event in shown] == ["hi"]
    # The page that spoke records exact pickup; neither page's status is rewritten.
    assert files_model.read_json(second / "status.json")["state"] == "waiting"
    assert files_model.read_json(page_dir / "status.json")["state"] == "waiting"
    assert events_model.read_events(second)[-1]["kind"] == "pickup"
    assert all(e["kind"] != "pickup" for e in events_model.read_events(page_dir))

    # Idling one leaf leaves the watch to the others; idling the last ends it.
    declare_idle(second)
    declare_idle(page_dir)
    assert session_model.cmd_wait() == 2


def test_the_stop_hook_watch_wakes_the_session_only_for_input(
    claimed, monkeypatch, capsys, dead_pid
):
    """Claude Code keeps Leaf's second Stop hook running in the background and
    wakes the session only when it exits 2, so that hook is the session's watch
    between turns, and the model keeps no `leaf wait` alive. It wakes for input,
    holds input that was already pending as the turn ended until the Stop hook
    beside it has answered, and ends silently where it has nothing to do."""
    leases_model.mark_hooks("s1")  # its harness runs Leaf's hooks
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "")
    stop = {"hook_event_name": "Stop", "session_id": "s1"}

    # The hook names another session: nothing to watch, and nothing wakes.
    assert hooks_model.cmd_watch("claude-code", {**stop, "session_id": "s2"}) is None
    # Under plain `--print` Claude Code would wait on the hook, holding the turn.
    launched = harness_model.process_argv
    argv = ["claude", "-p", "hello"]
    monkeypatch.setattr(harness_model, "process_argv", lambda pid: argv)
    assert hooks_model.cmd_watch("claude-code", stop) is None
    # Its stream-json output alone changes nothing; streamed input does.
    argv = ["claude", "-p", "hello", "--output-format", "stream-json"]
    assert not harness_model.session_harness().watches_between_turns()
    argv = ["claude", "-p", "--input-format", "stream-json"]
    assert harness_model.session_harness().watches_between_turns()
    monkeypatch.setattr(harness_model, "process_argv", launched)

    initialized = threading.Event()
    await_news = session_model.Watch.await_news

    def after_first_pass(watch, mark, *args, **kwargs):
        initialized.set()
        return await_news(watch, mark, *args, **kwargs)

    monkeypatch.setattr(session_model.Watch, "await_news", after_first_pass)

    def watching(outcome: list) -> threading.Thread:
        initialized.clear()
        watch = threading.Thread(
            target=lambda: outcome.append(hooks_model.cmd_watch("claude-code", stop))
        )
        watch.start()
        # The lease is acquired before the initial log snapshot. A comment sent
        # after acquisition can still enter that snapshot as pre-existing input;
        # the first completed pass proves this watch can now read later arrivals.
        assert initialized.wait(STATED_TIMEOUT), (
            "the watch never completed its first pass"
        )
        assert leases_model.wait_is_live(claimed, "s1")
        return watch

    # Input pending as the turn ends is the other Stop hook's to hand to the turn
    # it continues; once that hook lets the turn end over it, the watch wakes.
    # Date it before the watch's startup millisecond: input within that millisecond
    # deliberately wakes immediately, regardless of which call ran first.
    append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "user",
            "text": "before",
            "ts": (datetime.now().astimezone() - timedelta(seconds=1)).isoformat(
                timespec="milliseconds"
            ),
        },
    )
    outcome = []
    watch = watching(outcome)
    time.sleep(session_model.REVIVAL_CHECK_S / 5)
    assert outcome == []
    cleanup_model.close_session_turn("s1")
    watch.join(timeout=STATED_TIMEOUT)
    assert not watch.is_alive(), "the watch never woke when the turn closed"
    [woke] = outcome
    assert woke.startswith(f"{claimed} has new input")
    assert not leases_model.wait_is_live(claimed, "s1")

    # Input arriving once the watch runs wakes the session at once, between turns
    # or within one, where it reaches the turn at its next tool result.
    cleanup_model.prompt_turn("s1")
    receive_through(claimed, last_deliverable_seq(claimed))
    outcome = []
    watch = watching(outcome)
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "after"}
    )
    watch.join(timeout=STATED_TIMEOUT)
    assert not watch.is_alive(), "the watch never woke on the comment"
    [woke] = outcome
    assert woke.startswith(f"{claimed} has new input")

    # A watch whose harness process has gone, as a retired background job's worker
    # leaves it, ends silently and lets the lease go. Input admitted while it held
    # the lease was not nudged, so it nudges that input itself.
    cleanup_model.close_session_turn("s1")
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "orphaned"}
    )
    nudged = []
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "nudge",
        lambda harness, page: nudged.append(page) or True,
    )
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    assert hooks_model.cmd_watch("claude-code", stop) is None
    assert not leases_model.wait_is_live(claimed, "s1")
    assert nudged == [claimed.resolve()]
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))

    # An idle page leaves nothing to watch, and that ending wakes nobody.
    cleanup_model.prompt_turn("s1")
    receive_through(claimed, last_deliverable_seq(claimed))
    declare_idle(claimed)
    assert hooks_model.cmd_watch("claude-code", stop) is None


def test_the_newest_watch_takes_the_session_over(claimed, monkeypatch, capsys):
    """Claude Code starts a watch at every turn's end and leaves the earlier one
    running, so the newest takes the session's lease, and the watch it displaces
    ends without waking anyone. That is how a Leaf update reaches the watch: the
    earlier one may run a Leaf that cannot read a page the session now holds,
    while the new one runs the Leaf the harness runs now. A `leaf wait` the
    model left running gives way to it too."""
    leases_model.mark_hooks("s1")
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "")
    stop = {"hook_event_name": "Stop", "session_id": "s1"}
    passed = {name: threading.Event() for name in ("wait", "older", "newer")}
    await_news = session_model.Watch.await_news

    def after_a_pass(watch, mark, *args, **kwargs):
        passed[threading.current_thread().name].set()
        return await_news(watch, mark, *args, **kwargs)

    monkeypatch.setattr(session_model.Watch, "await_news", after_a_pass)

    def started(name: str, run) -> tuple[threading.Thread, list]:
        outcome = []
        thread = threading.Thread(name=name, target=lambda: outcome.append(run()))
        thread.start()
        assert passed[name].wait(STATED_TIMEOUT), f"{name} never completed a pass"
        assert leases_model.wait_is_live(claimed, "s1")
        return thread, outcome

    def ended(thread: threading.Thread, outcome: list):
        thread.join(timeout=STATED_TIMEOUT)
        assert not thread.is_alive(), f"{thread.name} went on watching"
        [result] = outcome
        return result

    wait, waited = started("wait", session_model.cmd_wait)
    older, olders = started("older", lambda: hooks_model.cmd_watch("claude-code", stop))
    assert ended(wait, waited) == 2
    assert "took over" in capsys.readouterr().err
    newer, newers = started("newer", lambda: hooks_model.cmd_watch("claude-code", stop))
    assert ended(older, olders) is None
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "after"}
    )
    assert ended(newer, newers).startswith(f"{claimed} has new input")
    assert not leases_model.wait_is_live(claimed, "s1")


def test_a_watch_superseded_during_a_pass_leaves_its_input_to_the_newer(
    claimed, monkeypatch
):
    """A watch the newer one displaces while it reads a page with input wakes
    nobody: the newer one carries that input, and a second wake would open a turn
    with nothing in it."""
    leases_model.mark_hooks("s1")
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "")
    cleanup_model.close_session_turn("s1")
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "race"}
    )
    read_watch_pass = session_model.read_watch_pass
    newer = session_model.Watch(harness_model.session_harness())

    def displaced_mid_pass(watch, *args, **kwargs):
        newer.acquire(supersede=True)
        return read_watch_pass(watch, *args, **kwargs)

    monkeypatch.setattr(session_model, "read_watch_pass", displaced_mid_pass)
    try:
        stop = {"hook_event_name": "Stop", "session_id": "s1"}
        assert hooks_model.cmd_watch("claude-code", stop) is None
        assert read_watch_pass(newer, None, lambda tick: tick.page_dir).delivered
    finally:
        newer.release()


@pytest.mark.parametrize("newer_ends", [False, True])
def test_a_lease_probe_reads_through_a_handoff(tmp_path, monkeypatch, newer_ends):
    """A probe that opened the lease file before a newer watch put its own in place
    asks again of the file the name reaches now. What the displaced file says is
    out of date: the newer lease holds once the displaced holder lets its file go,
    and has ended though the displaced holder still runs."""
    path = tmp_path / "wait"
    displaced = leases_model.take_lease(path)
    newer = []
    flock = leases_model.fcntl.flock

    def handed_over_before_the_probe(record, operation):
        probe = leases_model.fcntl.LOCK_SH | leases_model.fcntl.LOCK_NB
        if operation == probe and not newer:
            newer.append(leases_model.supersede_lease(path))
            if newer_ends:
                leases_model.release_lease(newer[0])
            else:
                leases_model.release_lease(displaced)
        return flock(record, operation)

    monkeypatch.setattr(leases_model.fcntl, "flock", handed_over_before_the_probe)
    try:
        assert leases_model.lock_is_held(path) is not newer_ends
    finally:
        monkeypatch.undo()
        leases_model.release_lease(displaced if newer_ends else newer[0])


def test_a_watch_at_an_interrupted_ending_wakes_only_for_later_input(
    claimed, monkeypatch
):
    """A harness that says its turn was interrupted, as Pi's extension does when an
    Escape settles a run, starts the watch with that Interrupt payload, which
    closes the turn before its first look. The user stopped the turn the pending
    input was handed to, so that input waits for their next prompt, and only
    unreceived input wakes the session. A watch at a Stop ending wakes for later
    pending input at once."""
    leases_model.mark_hooks("s1")
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "")
    cleanup_model.prompt_turn("s1")
    handed = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "handed over"}
    )
    receive_through(claimed, handed["seq"])

    waiting = threading.Event()
    await_news = session_model.Watch.await_news

    def after_a_pass(watch, mark, *args, **kwargs):
        waiting.set()
        return await_news(watch, mark, *args, **kwargs)

    monkeypatch.setattr(session_model.Watch, "await_news", after_a_pass)
    outcome = []
    watch = threading.Thread(
        target=lambda: outcome.append(
            hooks_model.cmd_watch(
                "claude-code", {"hook_event_name": "Interrupt", "session_id": "s1"}
            )
        )
    )
    watch.start()
    # A watch decides on its first pass; this one went on to wait for news.
    assert waiting.wait(STATED_TIMEOUT), "the watch never completed its first pass"
    assert outcome == []
    assert cleanup_model.session_record("s1")["turn_closed"] is not None
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "after"}
    )
    watch.join(timeout=STATED_TIMEOUT)
    assert not watch.is_alive(), "the watch never woke on the comment"
    [woke] = outcome
    assert woke.startswith(f"{claimed} has new input")

    waiting.clear()
    stop = {"hook_event_name": "Stop", "session_id": "s1"}
    assert hooks_model.cmd_watch("claude-code", stop).startswith(
        f"{claimed} has new input"
    )
    assert not waiting.is_set()


@pytest.mark.parametrize("failure", [None, "turn_failed", "recovered"])
def test_a_watch_does_not_reopen_for_answered_unreceived_input(
    claimed, monkeypatch, failure
):
    """A status-visible move can be answered before its delivery is received.
    It remains in the receipt batch, but that batch alone starts no new turn."""
    publish(claimed)
    leases_model.mark_hooks("s1")
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "")
    cleanup_model.prompt_turn("s1")
    source = append_command(
        claimed,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "already answered",
        },
    )
    thread_model.post_reply(
        claimed,
        {"to": source["id"], "for": source["id"]},
        "done",
        failure="turn_failed" if failure else None,
    )
    if failure == "recovered":
        thread_model.post_reply(
            claimed,
            {"to": source["id"], "for": source["id"]},
            "recovered answer",
            settlement=thread_model.ProviderFinal("test-final"),
        )
    assert thread_model.answered_by_reply(
        events_model.read_events(claimed), source["id"]
    ) is (failure != "turn_failed")
    cleanup_model.close_session_turn("s1")
    observed, waiting = threading.Event(), threading.Event()
    await_news = session_model.Watch.await_news

    def after_a_pass(watch, mark, *args, **kwargs):
        waiting.set()
        observed.set()
        return await_news(watch, mark, *args, **kwargs)

    monkeypatch.setattr(session_model.Watch, "await_news", after_a_pass)
    outcome = []

    def run():
        try:
            outcome.append(
                hooks_model.cmd_watch(
                    "claude-code", {"hook_event_name": "Stop", "session_id": "s1"}
                )
            )
        finally:
            observed.set()

    watch = threading.Thread(target=run)
    watch.start()
    try:
        assert observed.wait(STATED_TIMEOUT)
        assert waiting.is_set(), "answered input alone woke a new turn"
        assert source["id"] in {
            event["id"]
            for event in service_model.unacknowledged(
                events_model.read_events(claimed),
                service_model.PageTransaction(claimed).cursor,
            )
        }
    finally:
        append_command(
            claimed,
            {
                "kind": "reply",
                "author": "user",
                "parent": source["id"],
                "text": "retry or new question",
            },
        )
        watch.join(timeout=STATED_TIMEOUT)
    assert not watch.is_alive()
    assert outcome[0].startswith(f"{claimed} has new input")


@pytest.mark.parametrize(
    "event",
    [
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "held outside context",
        },
        {"kind": "error", "author": "page", "text": "a widget failed"},
    ],
)
def test_an_interrupt_watch_delivers_input_never_handed_to_the_stopped_turn(
    claimed, monkeypatch, event
):
    """Pi can hold a mid-run notification without entering it into context.
    Escape must not strand that input merely because it predates the watch."""
    publish(claimed)
    leases_model.mark_hooks("s1")
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "")
    cleanup_model.prompt_turn("s1")
    source = append_command(claimed, {**event, "revision": 1})
    assert source["attention"]
    observed, waiting = threading.Event(), threading.Event()
    await_news = session_model.Watch.await_news

    def after_a_pass(watch, mark, *args, **kwargs):
        waiting.set()
        observed.set()
        return await_news(watch, mark, *args, **kwargs)

    monkeypatch.setattr(session_model.Watch, "await_news", after_a_pass)
    outcome = []

    def run():
        try:
            outcome.append(
                hooks_model.cmd_watch(
                    "claude-code", {"hook_event_name": "Interrupt", "session_id": "s1"}
                )
            )
        finally:
            observed.set()

    watch = threading.Thread(target=run)
    watch.start()
    try:
        assert observed.wait(STATED_TIMEOUT)
        assert not waiting.is_set(), (
            "unreceived input was treated as handed to the stopped turn"
        )
    finally:
        append_command(
            claimed,
            {"kind": "comment", "author": "user", "revision": 1, "text": "after"},
        )
        watch.join(timeout=STATED_TIMEOUT)
    assert not watch.is_alive()
    assert outcome[0].startswith(f"{claimed} has new input")


def test_a_late_interrupt_leaves_a_turn_opened_after_it_open(claimed):
    """An extension's watch closes an interrupted turn only after the extension saw it
    end, and a Claude Code or Pi turn has no id, so a prompt in between renews
    the same turn. The Interrupt payload states when the turn ended, and a turn
    opened or renewed since then is not closed by it."""
    cleanup_model.prompt_turn("s1")
    ended = time.time()
    time.sleep(0.01)
    cleanup_model.prompt_turn("s1")
    interrupt = {"hook_event_name": "Interrupt", "session_id": "s1"}
    hooks_model.cmd_hook("claude-code", {**interrupt, "ended_at": ended})
    assert cleanup_model.session_record("s1")["turn_closed"] is None

    hooks_model.cmd_hook("claude-code", {**interrupt, "ended_at": time.time()})
    assert cleanup_model.session_record("s1")["turn_closed"] is not None


def test_a_page_served_mid_wait_joins_the_running_watch(
    page_dir, tmp_path, monkeypatch, capsys
):
    """The watch set is re-read every pass, so serving another leaf while the
    watcher holds needs no second command: the claim the serve makes is what
    puts the page in front of the running wait."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s10")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    leases_model.mark_hooks("s10")  # its harness runs Leaf's hooks
    serving(page_dir, 1)
    assert service_model.claim_page(page_dir)
    joined = tmp_path / "joined"
    vendoring_model.cmd_init(joined)
    capsys.readouterr()
    session_model.cmd_waiting(joined, "")
    serving(joined, 2)

    def join():
        service_model.claim_page(joined)
        append_carried_log_record(
            joined, {"kind": "comment", "author": "user", "text": "hi"}
        )

    threading.Timer(0.2, join).start()
    assert session_model.cmd_wait() == 0
    _, first, _ = delivered(capsys)
    assert first["page"] == str(joined)


def test_a_wait_holding_events_delivers_them_whatever_became_of_the_page(
    page_dir, capsys
):
    """The batch outranks the page's state: an idled leaf can still hold a
    comment the user got in before the end, and a wait that exited on the
    idle instead would strand it unread until a hook complained."""
    serving(page_dir, 1)
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    declare_idle(page_dir)
    service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    _, first, _ = delivered(capsys)
    assert first["page"] == str(page_dir)


def test_wait_with_nothing_to_watch_says_so(monkeypatch, capsys, snapshot):
    """A no-argument wait in a session that holds no pages has nothing to hold
    open — exit rather than sleep forever on an empty set."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-empty")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert session_model.cmd_wait() == 2
    printed = capsys.readouterr()
    assert "nothing to watch" in printed.err
    snapshot.check(
        yaml_document(
            "An unnamed wait exits when the session owns no page.",
            {"exit": 2, "stdout": printed.out, "stderr": said(printed.err)},
        )
    )


def test_wait_holds_a_page_nobody_has_opened(page_dir, capsys):
    """Nothing the server can observe tells a page the user hasn't opened yet
    from one they can't reach, so the wait doesn't guess between them: over a page
    no request has ever touched it holds for the user exactly as it would for
    one reading, and reports nothing of its own."""
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    threading.Timer(
        0.2,
        lambda: append_carried_log_record(
            page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
        ),
    ).start()

    service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    output = capsys.readouterr()
    _, first, shown = woken(output.out)
    assert first["page"] == str(page_dir)
    assert [event["id"] for event in shown] == ["c1"]
    assert output.err == ""


def test_a_named_bare_shell_wait_keeps_its_directory_without_a_claim(
    page_dir, sessionless, capsys
):
    """A terminal has no session ownership to gain or lose."""
    serving(page_dir, 1)
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = printed(capsys.readouterr().out)
    assert header["page"] == str(page_dir)
    assert service_model.page_claim(page_dir) is None


def test_a_bare_shell_receipt_rearms_every_page_in_its_delivery(
    page_dir, tmp_path, sessionless, spawn
):
    other = tmp_path / "other"
    shutil.copytree(page_dir, other)
    batches = []
    for index, page in enumerate((page_dir, other), 1):
        serving(page, index)
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "first"}
        )
        with service_model.PageTransaction(page) as transaction:
            batches.append(
                delivery_model.batch_data(page, transaction, transaction.events)
            )
    payload = delivery_model.freeze_delivery(batches)
    watching = spawn(
        [*LEAF_COMMAND, "wait", "--ack", payload["id"]],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: (
            leases_model.lock_is_held(page_dir / "waiter.lock"),
            leases_model.lock_is_held(other / "waiter.lock"),
        ),
        all,
        failure="receipt did not rearm both standalone pages",
    )
    later = append_carried_log_record(
        other, {"kind": "comment", "author": "user", "text": "next"}
    )
    out, err = watching.communicate(timeout=STATED_TIMEOUT)
    assert watching.returncode == 0, out + err
    _, batch, [event] = printed(out)
    assert batch["page"] == str(other)
    assert event["id"] == later["id"]
    for page in (page_dir, other):
        assert service_model.page_claim(page) is None
        assert files_model.read_json(page / "cursor.json") == {"seq": 1}


def test_an_unnamed_bare_shell_wait_has_no_watch_set(page_dir, sessionless, capsys):
    """Without a harness identity or a named page, there is nothing to watch."""
    session_model.cmd_waiting(page_dir, "")
    serving(page_dir, 1)
    record_claim(page_dir, id="foreign-session")
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "foreign", "author": "user", "text": "private"},
    )

    assert session_model.cmd_wait() == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "nothing to watch" in printed.err


def test_a_harness_claim_supersedes_a_bare_shell_wait(page_dir, sessionless, spawn):
    """A page has one wait owner even when the first has no harness identity."""
    session_model.cmd_waiting(page_dir, "")
    serving(page_dir, 1)
    bare = spawn(
        [*LEAF_COMMAND, "wait", str(page_dir)],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: leases_model.lock_is_held(page_dir / "waiter.lock"),
        bool,
        failure="the bare wait never took its lease",
    )

    harness_env = os.environ | {
        "CLAUDE_CODE_SESSION_ID": "harness-owner",
        "CLAUDE_PID": str(os.getpid()),
    }
    leases_model.mark_hooks("harness-owner")  # its harness runs Leaf's hooks
    subprocess.run(
        [*LEAF_COMMAND, "page", "claim", str(page_dir)], env=harness_env, check=True
    )
    harness = spawn(
        [*LEAF_COMMAND, "wait", str(page_dir)],
        env=harness_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: service_model.page_claim(page_dir),
        lambda claim: bool(
            claim
            and claim["id"] == "harness-owner"
            and leases_model.lock_is_held(
                leases_model.waiter_lease_path(page_dir, claim["id"])
            )
        ),
        failure="the harness wait never claimed the page and took its lease",
    )

    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "once", "author": "user", "text": "hi"},
    )
    bare_out, bare_err = bare.communicate(timeout=STATED_TIMEOUT)
    harness_out, harness_err = harness.communicate(timeout=STATED_TIMEOUT)

    assert (bare.returncode, bare_out) == (2, ""), bare_err
    assert "no longer owns it" in bare_err
    assert harness.returncode == 0, harness_err
    _, _, shown = woken(harness_out, "harness-owner")
    assert [event["id"] for event in shown] == ["once"]


def test_a_codex_watcher_task_takes_the_parent_watch_obligation(
    codex_claimed_page, under_codex, codex_env, capsys
):
    """The task that blocks in wait is the claimant, not the task it wakes.

    That transfer is the bridge: the parent may finish its turn because it no
    longer owns an unattended page, while the helper's own Stop hook keeps the
    wait inside a live turn. Leaf does not need to know where that task sends the
    batch.
    """
    page = codex_claimed_page
    session_model.cmd_waiting(page, "comment on the prototype")
    watcher = under_codex(
        claim_and_wait_command(page),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    wait_for(
        lambda: (service_model.page_claim(page) or {}, page_state(page)["listening"]),
        lambda reading: reading[0].get("id") == "leaf-watcher" and reading[1],
        failure="the watcher task never claimed the page and entered leaf wait",
    )
    hooks_model.cmd_hook(
        "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
    )
    assert capsys.readouterr().out == ""

    hooks_model.cmd_hook(
        "codex", {"hook_event_name": "Stop", "session_id": "leaf-watcher"}
    )
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "Keep this turn active" in reason and "poll the existing" in reason

    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    out, err = watcher.communicate(timeout=STATED_TIMEOUT)
    assert watcher.returncode == 0, f"{out}{err}"
    _, header, [event] = printed(out)
    assert header["page"] == str(page)
    assert event["text"] == "hi"
    assert files_model.read_json(page / "cursor.json") is None


def test_a_superseded_waiter_cannot_deliver_the_new_owners_batch(
    codex_claimed_page, under_codex, codex_env
):
    """One page has one cursor owner even if two watcher tasks are started.

    The later explicit claim transfers ownership before its wait starts. The earlier wait must then leave the
    watch set rather than print the same event from a task that no longer owns
    either the page or its acknowledgement cursor.
    """
    page = codex_claimed_page
    session_model.cmd_waiting(page, "comment on the prototype")

    first = under_codex(
        claim_and_wait_command(page),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: (service_model.page_claim(page) or {}, page_state(page)["listening"]),
        lambda reading: reading[0].get("id") == "leaf-watcher-1" and reading[1],
        failure="the first watcher never claimed the page and entered leaf wait",
    )

    second = under_codex(
        claim_and_wait_command(page),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-2"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: (service_model.page_claim(page) or {}, page_state(page)["listening"]),
        lambda reading: reading[0].get("id") == "leaf-watcher-2" and reading[1],
        failure="the replacement watcher never claimed the page and entered leaf wait",
    )

    first_out, first_err = first.communicate(timeout=STATED_TIMEOUT)
    assert (first.returncode, first_out) == (2, ""), first_err
    assert second.poll() is None
    assert page_state(page)["listening"]

    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    second_out, second_err = second.communicate(timeout=STATED_TIMEOUT)

    assert second.returncode == 0, f"{second_out}{second_err}"
    _, header, [event] = printed(second_out)
    assert header["page"] == str(page)
    assert event["seq"] == 1


def test_a_claim_transfer_stops_a_waiter_already_inside_a_poll(
    codex_claimed_page, under_codex, codex_env, monkeypatch
):
    """Ownership is checked at delivery, not only at the start of a poll.

    The probe holds a normal status read after the first watcher has already
    selected its page. A second session then takes the claim and an event arrives.
    The old watcher must re-read ownership before it prints that event; otherwise
    two sessions can act as cursor owner despite the supersession check passing on
    every ordinary run.
    """
    page = codex_claimed_page
    session_model.cmd_waiting(page, "comment on the prototype")
    selected = page.parent / "waiter-selected-page"
    probe = """
import sys
from pathlib import Path
from leaf import session

read_status = session.read_status
def held_status(page):
    Path(sys.argv[2]).write_text("selected", encoding="utf-8")
    sys.stdin.readline()
    return read_status(page)

session.read_status = held_status
from leaf.service import claim_page
claim_page(Path(sys.argv[1]))
sys.exit(session.cmd_wait(Path(sys.argv[1])))
"""
    first = under_codex(
        shlex.join([sys.executable, "-c", probe, str(page), str(selected)]),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-1"},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    wait_for(
        selected.exists,
        bool,
        failure="the first watcher never selected its page before the transaction",
    )
    assert service_model.page_claim(page)["id"] == "leaf-watcher-1"

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page)
    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    first_out, first_err = first.communicate(input="continue\n", timeout=STATED_TIMEOUT)
    assert (first.returncode, first_out) == (2, ""), first_err
    session = service_model.page_claim(page)
    assert session["id"] == "replacement"


@pytest.mark.parametrize("acknowledge", ["receive_delivery", "cmd_delivery_ack"])
def test_a_wait_delivers_input_even_after_its_hooks_stop(
    page_dir, monkeypatch, capsys, acknowledge
):
    """An explicit wait is a complete delivery route even when hooks succeeded
    earlier but cannot run now. A permanent capability mark cannot establish
    that the next hook will deliver; no timeout can establish that either."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "unhooked")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    first = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "first"}
    )

    service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    payload = json.loads(capsys.readouterr().out)
    assert f"leaf wait --ack {payload['id']}" in payload["acknowledge"]
    assert [event["id"] for event in payload["batches"][0]["events"]] == [first["id"]]
    getattr(delivery_model, acknowledge)(payload["id"])

    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "unhooked"}
    )
    capsys.readouterr()
    assert leases_model.hooks_ran("unhooked")
    cleanup_model.close_session_turn("unhooked")
    previous_turn = cleanup_model.session_record("unhooked")["turn"]
    # The next prompt hook fails before running Python: the last observed turn
    # stays closed, and no hook runs to take the following input.
    second = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "second"}
    )
    assert session_model.cmd_wait(page_dir) == 0
    payload, _, shown = printed(capsys.readouterr().out)
    assert [event["id"] for event in shown] == [second["id"]]
    assert page_state(page_dir)["pending"] == 1
    getattr(delivery_model, acknowledge)(payload["id"])
    assert page_state(page_dir)["pending"] == 0
    observed = cleanup_model.session_record("unhooked")
    assert observed["turn"] != previous_turn
    assert observed["turn_closed"] is None

    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "SessionEnd", "session_id": "unhooked"}
    )
    assert not leases_model.hooks_ran("unhooked")


def test_a_named_wait_observes_ownership_without_taking_it(claimed, capsys):
    session = service_model.page_claim(claimed)["id"]
    record_claim(claimed, id="successor", agent="Successor")
    assert session_model.cmd_wait(claimed) == 2
    assert service_model.page_claim(claimed)["id"] == "successor"
    assert "no longer owns" in capsys.readouterr().err
    assert session != "successor"
