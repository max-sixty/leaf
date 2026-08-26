"""Watch, ownership, hook, and server-lifetime tests."""

import fcntl
import http.client
import http.cookiejar
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import CLAUDE_IDENTITY, CODEX_IDENTITY, INTERACT_SCRIPT
from interact_support import (
    HELD_LEASES,
    PAGE,
    PLUGIN_ROOT,
    _status,
    available_loopback_port,
    check,
    fetch,
    fifo_writer,
    page_state,
    publish,
    record_claim,
    serving,
    spawn_probe,
    start_through_the_launcher,
    state_json,
)
from leaf_interact import cli as cli_model
from leaf_interact import conversation as conversation_model
from leaf_interact import events as events_model
from leaf_interact import files as files_model
from leaf_interact import hooks as hooks_model
from leaf_interact import hosting as hosting_model
from leaf_interact import http as http_model
from leaf_interact import layer as layer_model
from leaf_interact import registry as registry_model
from leaf_interact import schema as schema_model
from leaf_interact import service as service_model
from leaf_interact import session as session_model


def test_a_work_line_says_which_thread_the_agent_is_on(page_dir, capsys, monkeypatch):
    """`leaf status --on` writes one claim at two seats: the page's line, which the
    banner reads, and a line on the thread the work is about, which the reader sees
    under their own words. One command writes both because they are one sentence — a
    delegate that reports its thread is the agent checking in, and the shared timestamp
    is what keeps a `working` claim believed across a turn boundary the session that
    made the claim can no longer write across.

    The line carries across every later write but its own. That is the case it exists
    for: a wait handing over mid-delegation writes "picking up 1 update" over the
    page's line, and a line dropped there would take the reader's only sign that their
    question is in hand with it. `idle` is the end of the agent's side, and clears them
    with the leaf."""
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "why?"}
    )
    comment_seq = events_model.read_events(page_dir)[-1]["seq"]
    # A line names a thread, says what is being done, and says it about work in hand:
    # the two other states have nothing to put on a thread, and a line with no words
    # says nothing the thread does not already show.
    assert (
        "not a comment thread"
        in _status(page_dir, "working", "reading the traces", "--on", "nope").output
    )
    assert (
        "use it with `working`"
        in _status(page_dir, "waiting", "your read on this", "--on", "c1").output
    )
    assert "needs a detail" in _status(page_dir, "working", "--on", "c1").output
    assert "work" not in files_model.read_json(page_dir / "status.json")

    monkeypatch.setenv("LEAF_AGENT", "Trace reader")
    assert (
        _status(page_dir, "working", "reading the traces", "--on", "c1").exit_code == 0
    )
    status = files_model.read_json(page_dir / "status.json")
    assert (status["state"], status["detail"]) == ("working", "reading the traces")
    work = status["work"][0]
    assert work["subject"] == {"kind": "thread", "id": "c1"}
    assert work["detail"] == "reading the traces" and work["ts"] == status["ts"]
    assert work["after"] == comment_seq
    assert work["agent"] == "Trace reader" and work["id"] and work["session"]
    # The store stays private. At the state boundary it becomes the same typed update
    # envelope a widget report uses, including the posting delegate's own voice rather
    # than the page owner's.
    live = page_state(page_dir)
    assert "work" not in live["status"]
    assert live["claims"] == [
        {
            "id": work["id"],
            "target": {"kind": "thread", "id": "c1"},
            "source": "claim",
            "action": "working",
            "detail": {"text": "reading the traces"},
            "text": "reading the traces",
            "ts": status["ts"],
            "log_floor": comment_seq,
            "agent": "Trace reader",
            "session": work["session"],
        }
    ]
    folded = state_json(page_dir)
    claim = next(update for update in folded["updates"] if update["source"] == "claim")
    assert claim == {**live["claims"][0], "disposition": "effective"}

    # A later claim about the page as a whole answers nothing on the thread.
    assert _status(page_dir, "waiting", "look at v2").exit_code == 0
    waiting = files_model.read_json(page_dir / "status.json")
    assert (waiting["state"], waiting["detail"]) == ("waiting", "look at v2")
    assert waiting["work"][0]["detail"] == "reading the traces"

    # Nor does the handoff a wait writes on its way out, which is the whole point of
    # carrying them: the pickup interrupts the delegate rather than replacing it.
    serving(page_dir, 1)
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c2", "author": "user", "text": "and this?"}
    )
    assert session_model.cmd_wait(page_dir) == 0
    capsys.readouterr()
    handed = files_model.read_json(page_dir / "status.json")
    assert (handed["state"], handed["handoff"]) == ("working", True)
    assert handed["work"][0]["detail"] == "reading the traces"

    session_model.cmd_status(page_dir, "idle", "")
    assert "work" not in files_model.read_json(page_dir / "status.json")


def test_a_working_claim_can_name_a_widget_until_a_version_completes_it(page_dir):
    """A page widget and a comment root are two kinds of subject, resolved once at
    the CLI boundary and stored with the distinction intact. Widget work ends only
    when a later published version explicitly says it completes that widget work: an
    unrelated version cannot silently cancel a local claim, while a version cannot
    remove the claim's only seat without naming the work it completed."""
    work_page = PAGE.replace(
        '<lf-diagram id="flow">',
        '<lf-board id="rollout"><lf-column id="rollout-now" label="Now">\n'
        '  <lf-card id="rollout-card"><strong>Ship the rollout</strong> '
        "Check the fallback before cutover.</lf-card>\n"
        '</lf-column></lf-board>\n<lf-diagram id="flow">',
    )
    (page_dir / "versions" / "v1.html").write_text(work_page)
    publish(page_dir)

    claimed = _status(
        page_dir, "working", "checking the rollout", "--on", "rollout-card"
    )
    assert claimed.exit_code == 0, claimed.output
    status = files_model.read_json(page_dir / "status.json")
    work = status["work"][0]
    assert work["subject"] == {"kind": "widget", "id": "rollout-card"}
    assert work["detail"] == "checking the rollout" and work["ts"] == status["ts"]
    assert work["after"] == 1 and work["id"]
    assert "version" not in work
    live = page_state(page_dir)
    assert "work" not in live["status"]
    assert live["claims"][0]["version"] == 1

    # A drawing has no prose or declared conversation in which a local line can
    # stand. The declaration, not a widget-name branch, decides that at the door.
    no_seat = _status(page_dir, "working", "checking the graph", "--on", "flow")
    assert no_seat.exit_code == 1
    assert "has no local work seat" in no_seat.output

    # A new version that leaves the widget alone does not settle the claim by mere
    # chronology. It publishes normally and the same local work remains standing.
    (page_dir / "versions" / "v2.html").write_text(work_page)
    unrelated = CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(page_dir), "--version", "2", "--text", "Elsewhere"],
    )
    assert unrelated.exit_code == 0, unrelated.output
    claim = next(
        update
        for update in state_json(page_dir)["updates"]
        if update["source"] == "claim"
    )
    assert claim["target"] == {"kind": "widget", "id": "rollout-card"}
    assert claim["disposition"] == "effective"

    # Settlement is explicit and durable on the version note.
    (page_dir / "versions" / "v3.html").write_text(work_page)
    settled = CliRunner().invoke(
        cli_model.cli,
        [
            "version",
            "publish",
            str(page_dir),
            "--version",
            "3",
            "--text",
            "Rollout checked",
            "--completes",
            "rollout-card",
        ],
    )
    assert settled.exit_code == 0, settled.output
    note = events_model.read_events(page_dir)[-1]
    assert note["settles"] == [{"kind": "work", "id": "rollout-card"}]
    claim = next(
        update
        for update in state_json(page_dir)["updates"]
        if update["source"] == "claim"
    )
    assert claim["disposition"] == "settled"

    # A later claim on the same subject starts after that answer and therefore stands.
    renewed = _status(
        page_dir, "working", "checking the fallback", "--on", "rollout-card"
    )
    assert renewed.exit_code == 0, renewed.output
    renewed_claim = next(
        update
        for update in state_json(page_dir)["updates"]
        if update["source"] == "claim"
    )
    assert renewed_claim["text"] == "checking the fallback"
    assert renewed_claim["id"] != claim["id"]
    assert renewed_claim["disposition"] == "effective"

    # Replacing the prose widget with a data widget would keep the anchor id but remove
    # the local chrome seat. Publication refuses that silent loss until this version
    # names the work it answers.
    without_seat = re.sub(
        r'<lf-board id="rollout">.*?</lf-board>',
        '<div id="rollout"><div id="rollout-now">'
        '<lf-diagram id="rollout-card"><pre>graph LR\n  A --> B\n</pre></lf-diagram>'
        "</div></div>",
        work_page,
        count=1,
        flags=re.DOTALL,
    )
    (page_dir / "versions" / "v4.html").write_text(without_seat)
    dropped = CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(page_dir), "--version", "4", "--text", "Removed"],
    )
    assert dropped.exit_code == 1
    assert (
        "would remove the local seat for active work on 'rollout-card'"
        in dropped.output
    )

    finished = CliRunner().invoke(
        cli_model.cli,
        [
            "version",
            "publish",
            str(page_dir),
            "--version",
            "4",
            "--text",
            "Removed",
            "--completes",
            "rollout-card",
        ],
    )
    assert finished.exit_code == 0, finished.output

    # Naming no active widget claim is an unearned settlement, not inert metadata.
    (page_dir / "versions" / "v5.html").write_text(without_seat)
    unearned = CliRunner().invoke(
        cli_model.cli,
        [
            "version",
            "publish",
            str(page_dir),
            "--version",
            "5",
            "--text",
            "Again",
            "--completes",
            "rollout-card",
        ],
    )
    assert unearned.exit_code == 1
    assert "no active widget work claim" in unearned.output


def test_revendoring_cannot_remove_an_active_widget_work_seat(page_dir):
    """A layer transition changes the same declaration the status door trusted.
    Re-vendoring must not leave the page-wide claim standing while silently removing
    its local half; the active claim is settled by a version note, not by new assets."""
    work_page = PAGE.replace(
        '<lf-diagram id="flow">',
        '<lf-board id="rollout"><lf-column id="rollout-now" label="Now">\n'
        '  <lf-card id="rollout-card"><strong>Ship the rollout</strong></lf-card>\n'
        '</lf-column></lf-board>\n<lf-diagram id="flow">',
    )
    (page_dir / "versions" / "v1.html").write_text(work_page)
    publish(page_dir)
    claimed = _status(
        page_dir, "working", "checking the rollout", "--on", "rollout-card"
    )
    assert claimed.exit_code == 0, claimed.output
    before = (page_dir / "registry.json").read_bytes()

    card = json.loads((schema_model.DEFAULT_PACKAGE / "registry.json").read_text())[
        "lf-card"
    ]
    card.pop("x-work")
    layer = Path.cwd() / ".leaf"
    layer.mkdir()
    (layer / "registry.json").write_text(json.dumps({"lf-card": card}))

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code == 1
    assert "incoming layer would remove the local seat" in result.output
    assert "'rollout-card'" in result.output
    assert (page_dir / "registry.json").read_bytes() == before


@pytest.mark.parametrize("target", ["effort", "flag-first"])
def test_only_a_declared_widget_work_seat_is_admitted(page_dir, target):
    """A content model says what authors may put inside a widget, not whether core
    may add local chrome there. Inline prose has no block slot, and a prose option is
    itself the click target of its holder; neither becomes a seat by inference."""
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        PAGE.replace(
            "<lf-chip>effort: low</lf-chip>",
            '<lf-chip id="effort">effort: low</lf-chip>',
        )
    )
    publish(page_dir)

    claimed = _status(page_dir, "working", "checking the estimate", "--on", target)
    assert claimed.exit_code == 1
    assert "has no local work seat" in claimed.output


def test_a_thread_claim_is_settled_by_log_order_not_a_second_precision_clock(page_dir):
    """A reply can land in the same timestamp second as the status command. The
    claim records the log floor it followed, so that later event settles it without
    asking two equal wall-clock strings which happened first."""
    comment = events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "why?"},
    )
    assert (
        _status(page_dir, "working", "checking", "--on", comment["id"]).exit_code == 0
    )
    status = files_model.read_json(page_dir / "status.json")
    work = status["work"][0]

    events_model.append_event(
        page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "parent": comment["id"],
            "text": "Because the retry won.",
            "ts": work["ts"],
        },
    )

    claim = next(
        update
        for update in state_json(page_dir)["updates"]
        if update["source"] == "claim"
    )
    assert claim["disposition"] == "settled"

    assert (
        _status(page_dir, "working", "checking again", "--on", comment["id"]).exit_code
        == 0
    )
    renewed = next(
        update
        for update in state_json(page_dir)["updates"]
        if update["source"] == "claim"
    )
    assert renewed["id"] != claim["id"]
    assert renewed["disposition"] == "effective"


def test_reopening_a_thread_reveals_its_unanswered_claim(page_dir):
    """Resolution hides thread work while reopening restores an unanswered claim."""
    comment = events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "why?"},
    )
    assert (
        _status(page_dir, "working", "checking", "--on", comment["id"]).exit_code == 0
    )
    events_model.append_event(
        page_dir,
        {"kind": "resolve", "author": "claude", "parent": comment["id"]},
    )
    events_model.append_event(
        page_dir,
        {"kind": "unresolve", "author": "user", "parent": comment["id"]},
    )

    claim = next(
        update
        for update in state_json(page_dir)["updates"]
        if update["source"] == "claim"
    )
    assert claim["disposition"] == "effective"


def test_wait_prints_unacknowledged_user_events_and_flips_status(page_dir, capsys):
    # A held server.lock lease is what wait's liveness probe asks for.
    serving(page_dir, 1)
    session_model.cmd_status(page_dir, "waiting", "")
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    )
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "b",
            "action": "move",
            "detail": {"card": "x", "to": "y", "index": 0},
        },
    )
    assert session_model.cmd_wait(page_dir) == 0
    header, *shown = [
        json.loads(line) for line in capsys.readouterr().out.strip().splitlines()
    ]
    assert header == {"page": str(page_dir)}
    assert [e["kind"] for e in shown] == ["comment", "action"]
    assert shown[1]["detail"]["to"] == "y"
    # Printing is not acknowledgement: a detached Codex command can finish without
    # putting its output in the model's context, so wait leaves both events pending.
    assert files_model.read_json(page_dir / "cursor.json") is None
    assert page_state(page_dir)["pending"] == 2

    # An event posted between wait and acknowledgement is beyond the highest sequence
    # the model saw. Acknowledging that visible batch therefore leaves the newcomer.
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c2", "author": "user", "text": "later"}
    )
    session_model.cmd_ack(page_dir, 2)
    session_model.cmd_ack(page_dir, 2)  # retries are harmless
    assert files_model.read_json(page_dir / "cursor.json")["seq"] == 2
    assert page_state(page_dir)["pending"] == 1

    assert session_model.cmd_wait(page_dir) == 0
    assert [
        json.loads(line)["id"] for line in capsys.readouterr().out.splitlines()[1:]
    ] == ["c2"]
    session_model.cmd_ack(page_dir, 3)
    assert page_state(page_dir)["pending"] == 0
    # The wait status is marked a handoff, which dates the claim: the agent's own
    # `leaf status` clears the mark, so the mark surviving is a pickup that never landed.
    status = files_model.read_json(page_dir / "status.json")
    assert (status["state"], status["handoff"]) == ("working", True)
    session_model.cmd_status(page_dir, "working", "revising the plan")
    assert "handoff" not in files_model.read_json(page_dir / "status.json")

    # A worker's report wakes the watcher like a user event — it is the
    # orchestrator's to fold into a version — but the reader's banner count
    # deliberately leaves it out: a report is news the agent owes the page, not
    # something the reader owes an answer.
    events_model.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "claude",
            "agent": "Indexer",
            "session": "worker-1",
            "widget": "t1",
            "action": "status",
            "detail": {"status": "review"},
            "version": 1,
        },
    )
    assert page_state(page_dir)["pending"] == 0
    assert session_model.cmd_wait(page_dir) == 0
    shown = [
        json.loads(line) for line in capsys.readouterr().out.strip().splitlines()[1:]
    ]
    assert [(e["kind"], e.get("agent")) for e in shown] == [("report", "Indexer")]
    session_model.cmd_ack(page_dir, 4)
    assert files_model.read_json(page_dir / "cursor.json")["seq"] == 4


def test_wait_repeats_a_stable_transport_neutral_batch_until_ack(page_dir):
    """The page and each event's sequence identify retries for any consumer."""
    serving(page_dir, 1)
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    )

    first = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert first.exit_code == 0, first.output
    header, event = [json.loads(line) for line in first.output.strip().splitlines()]
    assert header == {"page": str(page_dir)}
    assert (event["id"], event["seq"], event["text"]) == ("c1", 1, "hi")
    assert files_model.read_json(page_dir / "cursor.json") is None

    retry = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert retry.exit_code == 0, retry.output
    assert json.loads(retry.output.splitlines()[0]) == header

    # If wait output was lost or truncated, retrieving it again before ack can
    # include a newer event. The old event keeps the same page-and-seq identity
    # for the receiving task to skip.
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c2", "author": "user", "text": "later"}
    )
    grown = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert grown.exit_code == 0, grown.output
    grown_header, *grown_events = [
        json.loads(line) for line in grown.output.strip().splitlines()
    ]
    assert grown_header == header
    assert [event["seq"] for event in grown_events] == [1, 2]


def test_ack_checks_its_target_and_advances_monotonically(page_dir):
    events_model.append_event(
        page_dir,
        {"kind": "note", "author": "claude", "version": 1, "text": "published"},
    )
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    )
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c2", "author": "user", "text": "later"}
    )
    runner = CliRunner()

    missing = runner.invoke(cli_model.cli, ["ack", str(page_dir), "4"])
    assert missing.exit_code == 1
    assert "event 4 does not exist" in missing.output

    agent_event = runner.invoke(cli_model.cli, ["ack", str(page_dir), "1"])
    assert agent_event.exit_code == 1
    assert (
        "event 1 is not a user event, a report, or a page error" in agent_event.output
    )

    first = runner.invoke(cli_model.cli, ["ack", str(page_dir), "3"])
    retry = runner.invoke(cli_model.cli, ["ack", str(page_dir), "3"])
    older = runner.invoke(cli_model.cli, ["ack", str(page_dir), "2"])
    assert first.exit_code == retry.exit_code == older.exit_code == 0
    assert files_model.read_json(page_dir / "cursor.json") == {"seq": 3}

    # A worker's report is part of the watcher's batch, so it is a valid ack
    # target too — the same cursor covers both kinds.
    events_model.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "claude",
            "widget": "t1",
            "action": "status",
            "detail": {"status": "review"},
            "version": 1,
        },
    )
    assert runner.invoke(cli_model.cli, ["ack", str(page_dir), "4"]).exit_code == 0
    assert files_model.read_json(page_dir / "cursor.json") == {"seq": 4}


def test_wait_preserves_a_working_status_on_mid_work_output(page_dir, capsys):
    serving(page_dir, 1)
    session_model.cmd_status(page_dir, "working", "running the browser suite")
    status_path = page_dir / "status.json"
    before = status_path.read_bytes()
    events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "one more thing"},
    )

    assert session_model.cmd_wait(page_dir) == 0
    assert [
        json.loads(line)["id"] for line in capsys.readouterr().out.splitlines()[1:]
    ] == ["c1"]
    assert status_path.read_bytes() == before


def test_watch_does_not_revive_a_disabled_service(page_dir, monkeypatch):
    files_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": False,
            "lifetime": "session",
        },
    )
    session_model.cmd_status(page_dir, "waiting", "review the page")

    def unexpected_start(*_args, **_kwargs):
        pytest.fail("disabled desired state was revived")

    monkeypatch.setattr(session_model, "start_server", unexpected_start)
    watch = session_model.Watch(None, named=page_dir)
    try:
        assert watch.acquire()
        reading = next(watch.tick())
    finally:
        watch.release()

    assert reading.lost is True
    assert reading.restarted is None


def test_a_delayed_revival_cannot_cross_an_explicit_stop(page_dir, monkeypatch):
    files_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    session_model.cmd_status(page_dir, "working", "watching for a reply")
    entered, release = threading.Event(), threading.Event()
    real_start = hosting_model.start_server

    def delayed_start(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return real_start(*args, **kwargs)

    monkeypatch.setattr(session_model, "start_server", delayed_start)
    readings, errors = [], []
    watch = session_model.Watch(None, named=page_dir)
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
    assert entered.wait(5), "the watcher did not decide to revive"
    assert hosting_model.cmd_stop(page_dir) == "no server running"
    release.set()
    reviving.join(timeout=10)

    assert not reviving.is_alive()
    assert errors == []
    assert readings[0].lost is True
    assert readings[0].restarted is None
    assert files_model.read_json(page_dir / "service.json")["enabled"] is False
    assert not service_model.lock_is_held(page_dir / "server.lock")


def test_wait_restarts_a_server_that_died_under_it(
    page_dir, comment_once_served, capsys
):
    """A page whose server died is offline in the user's browser and nowhere
    else — so `leaf wait`, the one thing positioned to notice, brings it back
    rather than exiting and leaving the discovery to the user."""

    files_model.write_json(
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
    assert session_model.cmd_wait(page_dir) == 0
    info = service_model.running_server(page_dir)
    # The revived server has to answer on the URL it published, key included:
    # the user's browser has been polling that address since it died.
    assert info
    state = urllib.parse.urlsplit(info["url"])
    assert (
        urllib.request.urlopen(state._replace(path="/api/state").geturl()).status == 200
    )
    assert "server had died; restarted" in capsys.readouterr().err
    # A wait claims the page it names, so what it revives is the claiming
    # session's server and dies with that session. Here the session is the
    # worker (conftest), which is what keeps a killed run from stranding this.
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == "session"


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
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    hosting_model.cmd_stop(page)
    session_model.cmd_status(page, "waiting", "comment on the prototype")
    status_path = page / "status.json"
    status_path.unlink()
    os.mkfifo(status_path)
    first = under_codex(
        shlex.join([str(launcher), "wait", str(page)]),
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
    session_model.cmd_status(page, "idle", "the page is done")

    first_out, first_err = first.communicate(timeout=60)
    assert (first.returncode, first_out) == (2, ""), first_err
    assert "no longer owns it" in first_err
    assert "the leaf ended" not in first_err
    session = service_model.page_claim(page)
    assert session["id"] == "replacement"
    assert service_model.running_server(page) is None


def test_session_end_cannot_be_overtaken_by_wait_revival(claimed, spawn):
    """The session-end reaper must outrank a wait's stale live-page snapshot.

    The FIFO holds the wait after it selected the page but before it checks the
    dead server. SessionEnd then releases its claim. Releasing the stale status
    read must not let that wait put a session server back up.
    """
    page = claimed
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    files_model.write_json(
        page / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    session_model.cmd_status(page, "waiting", "comment on the prototype")
    status_path = page / "status.json"
    status_path.unlink()
    os.mkfifo(status_path)
    waiter = spawn(
        [launcher, "wait", str(page)],
        env=os.environ
        | {"CLAUDE_CODE_SESSION_ID": "s1", "CLAUDE_PID": str(os.getpid())},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    writer = fifo_writer(status_path, "the waiter never reached its held status read")

    hooks_model.cmd_hook({"hook_event_name": "SessionEnd", "session_id": "s1"})
    assert files_model.read_json(page / "service.json")["enabled"] is True
    assert service_model.running_server(page) is None

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

    out, err = waiter.communicate(timeout=60)
    assert waiter.returncode == 2, f"{out}{err}"
    assert "this session no longer owns it" in err
    assert service_model.page_claim(page)["released"] is not None
    assert service_model.running_server(page) is None
    # SessionEnd releases ownership only. The FIFO remains the same status path;
    # lifecycle code did not replace it with an authored idle state.
    assert status_path.is_fifo()


def test_a_revived_server_keeps_the_lifetime_it_was_serving_under(
    claimed, comment_once_served
):
    """A standing page comes back standing. The lifetime is the page's record
    rather than the reviving process's, so the restarts a page doesn't choose —
    a crash, the revival a `leaf wait` makes under it — leave it as the serve
    that started it declared, and `leaf server stop` is still the one thing that
    ends one. Read off the launch instead, a session that happened to notice the
    server was down would inherit a dashboard somebody left up for weeks, and
    take it down when it ended."""
    files_model.write_json(
        claimed / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "standing",
        },
    )
    comment_once_served(claimed)
    assert session_model.cmd_wait(claimed) == 0
    # The reviving session did claim the page, so a lifetime read off this
    # launch would have said "session" — the claim is what the standing
    # record has to outrank.
    assert service_model.page_claim(claimed)["id"] == "s1"
    assert files_model.read_json(claimed / "service.json")["lifetime"] == "standing"


def test_wait_ends_when_the_leaf_does(page_dir):
    """Idling is how a leaf ends, and it has to reach the watcher: a wait that
    held on past it left a long-running command open for a page nobody was going
    to press. The server is not
    the watcher's to end — a reader is free to stay on a page the agent has
    finished with — so it is left exactly as it stands."""
    serving(page_dir, 1)
    session_model.cmd_status(page_dir, "idle", "the page is done")
    assert session_model.cmd_wait(page_dir) == 2
    assert service_model.running_server(page_dir)

    # And where SessionEnd idled the page and stopped its server both, a watcher
    # still winding down must not put it straight back up. Dropping the lease is
    # what makes the server read as dead.
    HELD_LEASES.pop().close()
    assert session_model.cmd_wait(page_dir) == 2
    assert service_model.running_server(page_dir) is None


def test_one_wait_watches_every_page_the_session_holds(
    page_dir, tmp_path, monkeypatch, capsys
):
    """A session's leaves share one watcher. The watch set is the session's own
    pages rather than the argument, so four leaves cost one command between
    them, and the batch's first line says which page it belongs to — the ack
    has to go back to the right log."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s9")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    second = tmp_path / "second"
    layer_model.cmd_init(second)
    capsys.readouterr()
    session_model.cmd_status(second, "waiting", "")
    session_model.cmd_status(page_dir, "waiting", "")
    serving(page_dir, 1)
    serving(second, 2)
    for d in (page_dir, second):
        assert service_model.claim_page(d)
    events_model.append_event(
        second, {"kind": "comment", "author": "user", "text": "hi"}
    )

    assert session_model.cmd_wait() == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert json.loads(lines[0]) == {"page": str(second)}
    assert [json.loads(line)["text"] for line in lines[1:]] == ["hi"]
    # The page that spoke picked up the handoff status; the other is untouched.
    assert files_model.read_json(second / "status.json")["state"] == "working"
    assert files_model.read_json(page_dir / "status.json")["state"] == "waiting"

    # Idling one leaf leaves the watch to the others; idling the last ends it.
    session_model.cmd_ack(second, 1)
    session_model.cmd_status(second, "idle", "")
    session_model.cmd_status(page_dir, "idle", "")
    assert session_model.cmd_wait() == 2


def test_a_page_served_mid_wait_joins_the_running_watch(
    page_dir, tmp_path, monkeypatch, capsys
):
    """The watch set is re-read every pass, so serving another leaf while the
    watcher holds needs no second command: the claim the serve makes is what
    puts the page in front of the running wait."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s10")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    serving(page_dir, 1)
    assert service_model.claim_page(page_dir)
    joined = tmp_path / "joined"
    layer_model.cmd_init(joined)
    capsys.readouterr()
    session_model.cmd_status(joined, "waiting", "")
    serving(joined, 2)

    def join():
        service_model.claim_page(joined)
        events_model.append_event(
            joined, {"kind": "comment", "author": "user", "text": "hi"}
        )

    threading.Timer(0.2, join).start()
    assert session_model.cmd_wait() == 0
    assert json.loads(capsys.readouterr().out.splitlines()[0]) == {"page": str(joined)}


def test_a_wait_holding_events_delivers_them_whatever_became_of_the_page(
    page_dir, capsys
):
    """The batch outranks the page's state: an idled leaf can still hold a
    comment the reader got in before the end, and a wait that exited on the
    idle instead would strand it unread until a hook complained."""
    serving(page_dir, 1)
    events_model.append_event(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    session_model.cmd_status(page_dir, "idle", "the page is done")
    assert session_model.cmd_wait(page_dir) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[0]) == {
        "page": str(page_dir)
    }


def test_wait_with_nothing_to_watch_says_so(monkeypatch, capsys):
    """A no-argument wait in a session that holds no pages has nothing to hold
    open — exit rather than sleep forever on an empty set."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-empty")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert session_model.cmd_wait() == 2
    assert "nothing to watch" in capsys.readouterr().err


def test_wait_holds_a_page_nobody_has_opened(page_dir, capsys):
    """Nothing the server can observe tells a page the user hasn't opened yet
    from one they can't reach, so the wait doesn't guess between them: over a page
    no request has ever touched it holds for the user exactly as it would for
    one reading, and reports nothing of its own."""
    serving(page_dir, 1)
    session_model.cmd_status(page_dir, "waiting", "")
    threading.Timer(
        0.2,
        lambda: events_model.append_event(
            page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
        ),
    ).start()

    assert session_model.cmd_wait(page_dir) == 0
    printed = capsys.readouterr()
    assert json.loads(printed.out.splitlines()[0]) == {"page": str(page_dir)}
    assert [json.loads(line)["id"] for line in printed.out.splitlines()[1:]] == ["c1"]
    assert printed.err == ""


def test_a_named_bare_shell_wait_keeps_its_directory_without_a_claim(
    page_dir, sessionless, capsys
):
    """A terminal has no session ownership to gain or lose."""
    serving(page_dir, 1)
    events_model.append_event(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )

    assert session_model.cmd_wait(page_dir) == 0
    header = json.loads(capsys.readouterr().out.splitlines()[0])
    assert header == {"page": str(page_dir)}
    assert service_model.page_claim(page_dir) is None


def test_an_unnamed_bare_shell_wait_has_no_watch_set(page_dir, sessionless, capsys):
    """Without a host identity or a named page, there is nothing to watch."""
    session_model.cmd_status(page_dir, "waiting", "")
    serving(page_dir, 1)
    record_claim(page_dir, id="foreign-session")
    events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "foreign", "author": "user", "text": "private"},
    )

    assert session_model.cmd_wait() == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "nothing to watch" in printed.err


def test_a_host_claim_supersedes_a_bare_shell_wait(page_dir, sessionless, spawn):
    """A page has one wait owner even when the first has no host identity."""
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    session_model.cmd_status(page_dir, "waiting", "")
    serving(page_dir, 1)
    bare = spawn(
        [launcher, "wait", str(page_dir)],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not service_model.lock_is_held(
        page_dir / "waiter.lock"
    ):
        time.sleep(0.05)
    assert service_model.lock_is_held(page_dir / "waiter.lock")

    host_env = os.environ | {
        "CLAUDE_CODE_SESSION_ID": "host-owner",
        "CLAUDE_PID": str(os.getpid()),
    }
    host = spawn(
        [launcher, "wait", str(page_dir)],
        env=host_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        claim = service_model.page_claim(page_dir)
        if (
            claim
            and claim["id"] == "host-owner"
            and service_model.lock_is_held(
                service_model.waiter_lease_path(page_dir, claim)
            )
        ):
            break
        time.sleep(0.05)
    else:
        pytest.fail("the host wait never claimed the page")

    events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "once", "author": "user", "text": "hi"},
    )
    bare_out, bare_err = bare.communicate(timeout=10)
    host_out, host_err = host.communicate(timeout=10)

    assert (bare.returncode, bare_out) == (2, ""), bare_err
    assert "no longer owns it" in bare_err
    assert host.returncode == 0, host_err
    assert [json.loads(line)["id"] for line in host_out.splitlines()[1:]] == ["once"]


def test_codex_launcher_claims_the_page_for_its_thread(codex_claimed_page):
    session = service_model.page_claim(codex_claimed_page)
    assert session["id"] == "codex-thread"
    assert session["agent"] == "Codex" and session["host"] == "codex"
    assert set(session) == {
        "page",
        "id",
        "agent",
        "host",
        "pid",
        "cwd",
        "ts",
        "turn_closed",
        "released",
    }
    assert page_state(codex_claimed_page)["agent"] == "Codex"


def test_a_codex_claim_records_the_session_not_the_shell_it_ran_through(
    tmp_path, under_codex, codex_env
):
    """The claim's pid is the one two reapers read as the session's life, and
    `$PPID` is not it: it is a fact about the shape of the command. Measured
    through `codex exec`, a bare command and an `&&` chain reported the codex
    process because the wrapping shell exec'd leaf in place, and a pipeline
        reported that shell — which exits with the command, so ownership would go
        inactive and its server would stop a second later. Here the
    shell is between the session and the command and has exited by the time this
    reads what was written, so a pid it could have recorded is one this cannot
    match."""
    page = tmp_path / "codex-page"
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    env = codex_env | {"CODEX_THREAD_ID": "thread-shape"}
    subprocess.run([launcher, "page", "init", page], env=env, check=True)
    events_model.append_event(page, {"kind": "comment", "author": "user", "text": "hi"})
    session = under_codex(shlex.join([str(launcher), "wait", str(page)]), env)
    assert session.wait(timeout=60) == 0
    assert service_model.page_claim(page)["pid"] == session.pid


def test_a_codex_session_id_with_no_codex_above_it_is_refused(tmp_path, codex_env):
    """A hand-built environment: LEAF_SESSION_ID states a Codex session and
    nothing running Codex is above this process, so there is no process whose
    life is that session's. Nothing to fall back on either — a pid guessed here
    is a claim that expires by itself, and every state that follows from one is
    silent, so the refusal names what it walked.

    Its premise is this process's own ancestry, which is the developer's to
    supply: run the suite from inside Codex and the walk finds that session,
    correctly, and there is no refusal here to read."""
    if any(program == "codex" for _, program in service_model.ancestry()):
        pytest.skip("run from inside Codex, which is the codex above this one")
    page = tmp_path / "handmade-page"
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    env = codex_env | {"CODEX_THREAD_ID": "thread-nobody"}
    subprocess.run([launcher, "page", "init", page], env=env, check=True)
    events_model.append_event(page, {"kind": "comment", "author": "user", "text": "hi"})
    refused = subprocess.run(
        [launcher, "wait", page],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode == 1, refused.stdout
    assert "no codex process runs above this one" in refused.stderr
    assert service_model.page_claim(page) is None


def test_a_claim_records_where_the_session_is_working(page_dir, tmp_path, monkeypatch):
    """What tells one leaf from another on the tray is the work behind it, which
    neither the title somebody wrote nor the state directory nobody chose says — so
    the claim records the directory the claiming command ran in, the same reading
    `layer_dirs` already takes cwd to be. Every seat gets it through `presence`, and a
    page nothing ever claimed says so rather than borrowing a path from somewhere."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    work = tmp_path / "api"
    work.mkdir()
    monkeypatch.chdir(work)
    assert service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir)["cwd"] == str(work)
    assert http_model.presence(page_dir, [])["session_cwd"] == str(work)
    with service_model.PageTransaction(page_dir) as page:
        page.release_claim()
    assert http_model.presence(page_dir, [])["session_cwd"] == str(work)
    assert http_model.presence(page_dir, [])["session_alive"] is False


def test_reinitializing_a_deleted_page_path_drops_its_old_claim(page_dir, monkeypatch):
    """A regenerated page is not the deleted page that occupied its path."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "old-session")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)

    shutil.rmtree(page_dir)
    initialized = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert initialized.exit_code == 0, initialized.output

    assert service_model.page_claim(page_dir) is None
    assert service_model.owned_pages("old-session") == []


def test_a_fresh_init_does_not_delete_a_concurrently_created_pages_claim(
    tmp_path, monkeypatch, spawn
):
    """The first page creation is one serialized transition."""
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "concurrent-page"
    reached_layer = threading.Event()
    resume = threading.Event()
    original_composed_theme = layer_model.composed_theme

    def held_composed_theme(sources):
        reached_layer.set()
        assert resume.wait(timeout=10), "the concurrent init never released its peer"
        return original_composed_theme(sources)

    monkeypatch.setattr(layer_model, "composed_theme", held_composed_theme)
    executor = ThreadPoolExecutor(max_workers=1)
    first = executor.submit(layer_model.cmd_init, page)
    try:
        assert reached_layer.wait(timeout=10), (
            "the first init never reached its held read"
        )

        launcher = PLUGIN_ROOT / "bin" / "leaf"
        second = spawn(
            [launcher, "page", "init", page],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(0.1)
        assert second.poll() is None, "the overlapping init bypassed the page lease"
        resume.set()
        first.result(timeout=10)
        second_out, second_err = second.communicate(timeout=10)
        assert second.returncode == 0, f"{second_out}{second_err}"
        idled = subprocess.run(
            [launcher, "status", page, "idle"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert idled.returncode == 0, idled.stderr
        picked_up = subprocess.run(
            [launcher, "wait", page],
            env=os.environ
            | {
                "CLAUDE_CODE_SESSION_ID": "new-owner",
                "CLAUDE_PID": str(os.getpid()),
            },
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert picked_up.returncode == 2, picked_up.stderr
        assert service_model.page_claim(page)["id"] == "new-owner"
    finally:
        resume.set()
        executor.shutdown(wait=True, cancel_futures=True)
    assert first.done()
    assert service_model.page_claim(page)["id"] == "new-owner"


def test_the_launcher_defaults_the_name_but_a_worker_keeps_its_own(
    tmp_path, under_codex, codex_env
):
    """A Codex worker launched with LEAF_AGENT set keeps that voice: the
    launcher's Codex branch supplies the default name, not the last word."""
    page = tmp_path / "worker-page"
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    env = codex_env | {"CODEX_THREAD_ID": "thread-9", "LEAF_AGENT": "Indexer"}
    subprocess.run([launcher, "page", "init", page], env=env, check=True)
    events_model.append_event(page, {"kind": "comment", "author": "user", "text": "hi"})
    waited = under_codex(shlex.join([str(launcher), "wait", str(page)]), env)
    assert waited.wait(timeout=60) == 0
    session = service_model.page_claim(page)
    assert session["id"] == "thread-9"
    assert session["agent"] == "Indexer" and session["host"] == "codex"


def test_hook_remedies_follow_the_host_not_the_display_name(
    tmp_path, under_codex, codex_env, capsys
):
    """LEAF_AGENT names the voice the banner and threads show; which
    machinery the hook prescribes (unified exec vs background tasks) keys on the
    recorded host, so a renamed Codex worker still gets Codex remedies."""
    page = tmp_path / "worker-page"
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    env = codex_env | {"CODEX_THREAD_ID": "w1", "LEAF_AGENT": "Indexer"}
    subprocess.run([launcher, "page", "init", page], env=env, check=True)
    events_model.append_event(page, {"kind": "comment", "author": "user", "text": "hi"})
    waited = under_codex(shlex.join([str(launcher), "wait", str(page)]), env)
    assert waited.wait(timeout=60) == 0
    claim = service_model.page_claim(page)
    files_model.write_json(
        service_model.claim_path(page), {**claim, "pid": os.getpid()}
    )
    session_model.cmd_status(page, "waiting", "")

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "w1"})
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "unified exec" in reason and "write_stdin" in reason
    assert service_model.page_claim(page)["agent"] == "Indexer"


def test_stop_hook_keeps_codex_inside_the_exact_wait_session(
    codex_claimed_page, capsys
):
    page = codex_claimed_page
    session_model.cmd_status(page, "waiting", "")
    session = service_model.page_claim(page)
    lease = service_model.take_waiter_lease(
        service_model.waiter_lease_path(page, session)
    )
    assert lease

    # A live wait lets Claude end its turn, but Codex must keep this one active and
    # poll the unified-exec session whose output can enter this context.
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "poll the existing" in reason and "write_stdin" in reason

    # The existing one-shot escape still prevents a hook recursion.
    hooks_model.cmd_hook(
        {
            "hook_event_name": "Stop",
            "session_id": "codex-thread",
            "stop_hook_active": True,
        }
    )
    assert capsys.readouterr().out == ""

    # With no waiter, the remedy names both halves of the Codex loop.
    lease.close()
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "Start `leaf wait`" in reason
    assert "unified exec" in reason and "write_stdin" in reason

    # Pending output still has to cross context and be acknowledged before handling.
    events_model.append_event(page, {"kind": "comment", "author": "user", "text": "hi"})
    lease = service_model.take_waiter_lease(
        service_model.waiter_lease_path(page, session)
    )
    assert lease
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "leaf ack" in reason and "If this task is the consumer" in reason
    assert schema_model.ACK_BATCH_INSTRUCTION in reason
    lease.close()

    session_model.cmd_ack(page, 1)
    # Answered before the page closes: an acknowledged comment with nothing
    # under it holds the turn on its own account, which is the subject of
    # test_an_acknowledged_comment_nobody_answered_holds_the_turn.
    conversation_model.cmd_reply(
        page, events_model.read_events(page)[0]["id"], "so it does", None
    )
    session_model.cmd_status(page, "idle", "")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
    assert capsys.readouterr().out == ""


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
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    session_model.cmd_status(page, "waiting", "comment on the prototype")
    watcher = under_codex(
        shlex.join([str(launcher), "wait", str(page)]),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        session = service_model.page_claim(page) or {}
        if session.get("id") == "leaf-watcher" and page_state(page)["listening"]:
            break
        time.sleep(0.05)
    else:
        pytest.fail("the watcher task never claimed the page and entered leaf wait")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
    assert capsys.readouterr().out == ""

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "leaf-watcher"})
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "Keep this turn active" in reason and "poll the existing" in reason

    events_model.append_event(page, {"kind": "comment", "author": "user", "text": "hi"})
    out, err = watcher.communicate(timeout=60)
    assert watcher.returncode == 0, f"{out}{err}"
    header, event = [json.loads(line) for line in out.splitlines()]
    assert header == {"page": str(page)}
    assert event["text"] == "hi"
    assert files_model.read_json(page / "cursor.json") is None


def test_a_superseded_waiter_cannot_deliver_the_new_owners_batch(
    codex_claimed_page, under_codex, codex_env
):
    """One page has one cursor owner even if two watcher tasks are started.

    The later wait takes the page's claim. The earlier wait must then leave the
    watch set rather than print the same event from a task that no longer owns
    either the page or its acknowledgement cursor.
    """
    page = codex_claimed_page
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    session_model.cmd_status(page, "waiting", "comment on the prototype")

    first = under_codex(
        shlex.join([str(launcher), "wait", str(page)]),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        session = service_model.page_claim(page) or {}
        if session.get("id") == "leaf-watcher-1" and page_state(page)["listening"]:
            break
        time.sleep(0.05)
    else:
        pytest.fail("the first watcher never claimed the page")

    second = under_codex(
        shlex.join([str(launcher), "wait", str(page)]),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-2"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        session = service_model.page_claim(page) or {}
        if session.get("id") == "leaf-watcher-2" and page_state(page)["listening"]:
            break
        time.sleep(0.05)
    else:
        pytest.fail("the replacement watcher never claimed the page")

    first_out, first_err = first.communicate(timeout=60)
    assert (first.returncode, first_out) == (2, ""), first_err
    assert second.poll() is None
    assert page_state(page)["listening"]

    events_model.append_event(page, {"kind": "comment", "author": "user", "text": "hi"})
    second_out, second_err = second.communicate(timeout=60)

    assert second.returncode == 0, f"{second_out}{second_err}"
    header, event = [json.loads(line) for line in second_out.splitlines()]
    assert header == {"page": str(page)}
    assert event["seq"] == 1


def test_a_claim_transfer_stops_a_waiter_already_inside_a_poll(
    codex_claimed_page, under_codex, codex_env, monkeypatch
):
    """Ownership is checked at delivery, not only at the start of a poll.

    The FIFO holds a normal status read after the first watcher has already
    selected its page. A second session then takes the claim and an event arrives.
    The old watcher must re-read ownership before it prints that event; otherwise
    two sessions can act as cursor owner despite the supersession check passing on
    every ordinary run.
    """
    page = codex_claimed_page
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    session_model.cmd_status(page, "waiting", "comment on the prototype")
    first = under_codex(
        shlex.join([str(launcher), "wait", str(page)]),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        session = service_model.page_claim(page) or {}
        if session.get("id") == "leaf-watcher-1" and page_state(page)["listening"]:
            break
        time.sleep(0.05)
    else:
        pytest.fail("the first watcher never claimed the page")

    status_path = page / "status.json"
    status_path.unlink()
    os.mkfifo(status_path)
    writer = fifo_writer(
        status_path, "the first watcher never reached its held status read"
    )

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page)
    events_model.append_event(page, {"kind": "comment", "author": "user", "text": "hi"})
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

    first_out, first_err = first.communicate(timeout=60)
    assert (first.returncode, first_out) == (2, ""), first_err
    session = service_model.page_claim(page)
    assert session["id"] == "replacement"


@pytest.mark.parametrize(
    "identity_names",
    [
        pytest.param(CLAUDE_IDENTITY + CODEX_IDENTITY, id="bare-shell"),
        pytest.param((), id="host-session"),
    ],
)
def test_wait_lease_is_exact_and_excludes_another_wait(
    page_dir, monkeypatch, spawn, identity_names
):
    """The held lease, not a timestamp or pid, is the wait's liveness."""
    for name in identity_names:
        monkeypatch.delenv(name, raising=False)
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    serving(page_dir, 1)
    session_model.cmd_status(page_dir, "waiting", "comment on the prototype")
    # A bare waiter may hold an unclaimed page; a host waiter claims the page
    # from its prior owner before taking its session-scoped lease.
    if not identity_names:
        record_claim(page_dir, id="past-session")
    lease_path = (
        page_dir / "waiter.lock"
        if identity_names
        else service_model.waiter_lease_path(page_dir, service_model.host_identity())
    )
    first = spawn(
        [launcher, "wait", str(page_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not service_model.lock_is_held(lease_path):
        time.sleep(0.05)
    assert service_model.lock_is_held(lease_path)

    second = subprocess.run(
        [launcher, "wait", str(page_dir)],
        capture_output=True,
        text=True,
        timeout=10,
        env=os.environ,
        check=False,
    )
    assert second.returncode == 2
    assert "another `leaf wait` is already active" in second.stderr

    first.terminate()
    first.communicate(timeout=10)
    assert not service_model.lock_is_held(lease_path)


def test_a_new_claim_cannot_borrow_the_previous_sessions_wait_lease(
    page_dir, monkeypatch
):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "first")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    first = service_model.host_identity()
    lease = service_model.take_waiter_lease(
        service_model.waiter_lease_path(page_dir, first)
    )
    assert lease and page_state(page_dir)["listening"]

    assert service_model.claim_page(page_dir)
    assert page_state(page_dir)["listening"]

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
    assert service_model.claim_page(page_dir)
    assert not page_state(page_dir)["listening"]
    lease.close()


def test_stop_hook_does_not_borrow_a_foreign_bare_waiter_lease(
    page_dir, monkeypatch, capsys
):
    """A page-local lease proves only an unclaimed bare-shell watch."""
    session_model.cmd_status(page_dir, "waiting", "")
    bare = service_model.take_waiter_lease(page_dir / "waiter.lock")
    assert bare
    try:
        assert page_state(page_dir)["listening"]
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "host-owner")
        monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
        assert service_model.claim_page(page_dir)
        claim = service_model.page_claim(page_dir)
        assert not service_model.lock_is_held(
            service_model.waiter_lease_path(page_dir, claim)
        )
        assert service_model.lock_is_held(page_dir / "waiter.lock")
        assert not page_state(page_dir)["listening"]

        hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "host-owner"})
        answer = json.loads(capsys.readouterr().out)
        assert answer["decision"] == "block"
        assert "no watcher" in answer["reason"]

        with service_model.PageTransaction(page_dir) as page:
            page.release_claim()
        assert page_state(page_dir)["listening"]
    finally:
        bare.close()


def test_the_stop_hook_records_the_ending_of_the_turn_behind_a_claim(claimed, capsys):
    """A `working` claim is written by a model's turn, and a turn can end at any token
    without running anything — so nothing writes its close, and the page was left to
    find an abandoned claim by outwaiting a clock. The Stop hook is the harness
    watching that same moment, which is what these hooks are for.

    It stamps whether or not it has a nudge to make, and ahead of both of the guard's
    early returns: a turn that ends with nothing outstanding is exactly the turn that
    walks away from a `working` claim. The stamp is provenance and lands on the claim
    record rather than in status.json — what the agent said it was doing stays the
    agent's to write, which is the line SessionEnd already draws."""
    session_model.cmd_status(claimed, "working", "reading the reconnect traces")
    assert service_model.page_claim(claimed)["turn_closed"] is None
    events = events_model.read_events(claimed)
    assert http_model.presence(claimed, events)["turn_closed"] is None

    # A live watcher: the guard has nothing to say, and the ending is recorded anyway.
    session = service_model.page_claim(claimed)
    lease = service_model.take_waiter_lease(
        service_model.waiter_lease_path(claimed, session)
    )
    assert lease
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    closed = service_model.page_claim(claimed)["turn_closed"]
    assert closed
    assert http_model.presence(claimed, events)["turn_closed"] == closed
    # And what the agent said it was doing is untouched by the observation of it.
    assert (
        files_model.read_json(claimed / "status.json")["detail"]
        == "reading the reconnect traces"
    )

    # Re-entry after a block stands the guard down before it would speak; the stamp is
    # the turn's own and is taken on that ending too.
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    assert capsys.readouterr().out == ""
    assert service_model.page_claim(claimed)["turn_closed"] >= closed

    # Another session's turn ending says nothing about a page that is not one of its
    # own — the stamp names when this claim's turn ended or it means nothing.
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s2"})
    assert service_model.page_claim(claimed)["turn_closed"] == closed
    lease.close()


def test_the_state_payload_carries_the_clock_its_timestamps_were_written_by(page_dir):
    """Every ts a seat dates is written here, while the reader's `Date.now()` is
    another machine's opinion. The payload states the writer's clock so the reading is
    made against that one; without it a skewed laptop misreads every age on the page,
    in one direction and with nothing to give it away."""
    state = http_model.full_state(page_dir, [], [])
    written = datetime.fromisoformat(state["now"])
    assert abs((datetime.now().astimezone() - written).total_seconds()) < 60


def test_stop_hook_blocks_a_turn_that_leaves_a_page_unwatched(claimed, capsys):
    """Between turns a page is either watched or idle. The failure this prevents:
    a `leaf wait` exits, its notification is buried behind the next thing the
    user types, and the page keeps saying "Claude is working" over nobody."""
    session_model.cmd_status(claimed, "waiting", "")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert answer["decision"] == "block"
    assert "no watcher" in answer["reason"] and str(claimed) in answer["reason"]

    # Blocking twice in a row is how a Stop hook loops, so a block already in
    # flight stands down.
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    assert capsys.readouterr().out == ""

    # A live watcher, and a closed page, each end the turn cleanly.
    session = service_model.page_claim(claimed)
    lease = service_model.take_waiter_lease(
        service_model.waiter_lease_path(claimed, session)
    )
    assert lease
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    lease.close()
    session_model.cmd_status(claimed, "idle", "")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # A page a second session has since picked up is that session's to watch, so
    # s1 is no longer held to it.
    session_model.cmd_status(claimed, "waiting", "")
    record_claim(claimed, id="s2")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""


def test_hook_drops_a_page_transferred_after_ownership_discovery(claimed, monkeypatch):
    """A Stop decision belongs to the page's owner at decision time.

    Hold the old owner's hook after it discovers the page, transfer the claim,
    then let the hook finish reading. It must not block the old session on the
    new owner's unwatched page.
    """
    session_model.cmd_status(claimed, "waiting", "")
    status = files_model.read_json(claimed / "status.json")
    status_path = claimed / "status.json"
    status_path.unlink()
    os.mkfifo(status_path)
    answers = []
    hook = threading.Thread(
        target=lambda: answers.append(hooks_model.unattended_pages("s1")), daemon=True
    )
    hook.start()
    writer = fifo_writer(status_path, "the hook never reached its held status read")

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
    assert service_model.claim_page(claimed)
    os.write(writer, files_model.json_bytes(status))
    os.close(writer)
    hook.join(timeout=5)

    assert not hook.is_alive()
    assert answers == [[]]


def test_an_acknowledged_comment_nobody_answered_holds_the_turn(claimed, capsys):
    """Acknowledging is what takes a comment off the batch, so after it no
    watcher will raise that comment again and every other gate reads the page as
    clean. The failure, from a live channel session: a comment arrived while the
    agent was mid-turn on something else, the agent acknowledged it, answered
    the person in the terminal instead of on the page, and the reader was left
    with a question that nothing would ever deliver again."""
    session_model.cmd_status(claimed, "waiting", "")
    # Watched, which is the whole of what clears the guard's other case and
    # clears nothing here.
    session = service_model.page_claim(claimed)
    lease = service_model.take_waiter_lease(
        service_model.waiter_lease_path(claimed, session)
    )
    assert lease
    asked = events_model.append_event(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    session_model.cmd_ack(claimed, events_model.read_events(claimed)[-1]["seq"])

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert answer["decision"] == "block"
    assert "1 acknowledged comment with no answer" in answer["reason"]
    assert asked["id"] in answer["reason"]

    # A reply clears it, and the thread stays open behind it: closing one is the
    # reader's to do, so an open thread is not an unanswered one.
    conversation_model.cmd_reply(
        claimed, asked["id"], "because the fold is absolute", None
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # The reader's follow-up puts the ask back, and this is the case that picks
    # the reading. The browser posts a follow-up as a reply of the reader's own,
    # so a gate asking whether anyone but them has *ever* spoken is answered
    # "yes" by the reply above and never fires for this thread again — the drop
    # this test is named for, one level down and just as permanent. Reading the
    # last word costs a thread that wants no answer one `leaf resolve`, which is
    # a question the agent is holding the context to settle; the other reading
    # costs the reader their question, which nobody sees at all.
    follow = events_model.append_event(
        claimed,
        {
            "kind": "reply",
            "author": "user",
            "parent": asked["id"],
            "text": "but why not C?",
        },
    )
    # Until it is acknowledged the follow-up is not this clause's, which is why
    # the cursor is read against the last word and not the root: a watcher is
    # still going to deliver this one. Read against the root — acknowledged long
    # ago — the turn would block over a message the agent has not been handed.
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    session_model.cmd_ack(claimed, events_model.read_events(claimed)[-1]["seq"])
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert asked["id"] in json.loads(capsys.readouterr().out)["reason"]
    conversation_model.cmd_reply(
        claimed, follow["id"], "C is slower on the hot path", None
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # Closing the thread is the other way to answer for one, for the cases where
    # waiting on the reader says nothing.
    moot = events_model.append_event(
        claimed, {"kind": "comment", "author": "user", "text": "and C?"}
    )
    session_model.cmd_ack(claimed, events_model.read_events(claimed)[-1]["seq"])
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert moot["id"] in json.loads(capsys.readouterr().out)["reason"]
    conversation_model.cmd_resolve(claimed, moot["id"])
    capsys.readouterr()  # cmd_resolve prints the event it wrote
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # The agent's own ask holds nothing while the reader has yet to answer it:
    # the last word there is the agent's. When they answer in the thread — which
    # is where the panel's reply box puts it — the ask is the agent's again, and
    # it is the last word rather than any reading of the root that says so.
    ask = events_model.append_event(
        claimed,
        {"kind": "comment", "author": "claude", "text": "which storage engine?"},
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    events_model.append_event(
        claimed,
        {"kind": "reply", "author": "user", "parent": ask["id"], "text": "sqlite"},
    )
    session_model.cmd_ack(claimed, events_model.read_events(claimed)[-1]["seq"])
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert ask["id"] in json.loads(capsys.readouterr().out)["reason"]
    conversation_model.cmd_reply(claimed, ask["id"], "sqlite it is", None)
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    lease.close()


def test_the_guard_survives_a_page_vendored_before_the_layer_moved(claimed, capsys):
    """A page directory holds the copy of the layer it was created with, and the
    stamp refuses a copy the current layer has outgrown — by design, since that
    refusal is what sends an agent to re-vendor. The Stop hook is the one reader
    that must never put the question: `loop-guard.py` fails open, so a raise
    here stands the *whole* guard down, watch clause included, on any page a
    little older than the checkout, and says nothing about it. Found by running
    the guard against a real page from an earlier vendoring, where reading the
    published version to settle threads loaded that page's registry."""
    registry = files_model.read_json(claimed / "registry.json")
    del registry["$events"]["kinds"]["action"]
    files_model.write_json(claimed / "registry.json", registry)
    # Without this the test passes for the wrong reason: it has to be a page
    # whose registry the current layer really does refuse.
    with pytest.raises(registry_model.RegistryError):
        registry_model.load_registry(claimed)

    session_model.cmd_status(claimed, "waiting", "")
    session = service_model.page_claim(claimed)
    lease = service_model.take_waiter_lease(
        service_model.waiter_lease_path(claimed, session)
    )
    assert lease
    asked = events_model.append_event(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    session_model.cmd_ack(claimed, events_model.read_events(claimed)[-1]["seq"])
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert answer["decision"] == "block"
    assert asked["id"] in answer["reason"]
    lease.close()


def test_prompt_hook_surfaces_comments_claude_never_picked_up(claimed, capsys):
    session_model.cmd_status(claimed, "working", "revising")
    events_model.append_event(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    assert page_state(claimed)["pending"] == 1
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert "1 update you haven't picked up" in context

    # Not while a watcher is live: it prints them itself, and sending Claude to start a
    # second `leaf wait` would print every unacknowledged event twice.
    session = service_model.page_claim(claimed)
    lease = service_model.take_waiter_lease(
        service_model.waiter_lease_path(claimed, session)
    )
    assert lease
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    lease.close()


def test_only_serving_or_watching_a_page_puts_the_session_under_the_guard(
    page_dir, monkeypatch, capsys
):
    """Verifying a change to the page layer means driving throwaway pages, and the
    guard must not read a handful of test fixtures as a handful of abandoned
    pages. A directory this session only built and linted was handed to nobody.
    Listening on one is what puts a user on the other end, and from there the
    guard holds the session to it."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s7")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert check(page_dir).exit_code == 0
    assert (
        CliRunner().invoke(cli_model.cli, ["page", "catalog", str(page_dir)]).exit_code
        == 0
    )
    assert service_model.owned_pages("s7") == []
    # `page init` left the page "working", which is the state the guard blocks on —
    # but only for a page some session answers for, and none does.
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s7"})
    assert capsys.readouterr().out == ""

    events_model.append_event(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    assert CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)]).exit_code == 0
    assert service_model.owned_pages("s7") == [page_dir.resolve()]

    # If wait's process finished without its output entering model context, the event
    # remains recoverable and the next hook names it rather than calling it delivered.
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s7"})
    assert "1 update" in json.loads(capsys.readouterr().out)["reason"]

    session_model.cmd_ack(page_dir, 1)
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s7"})
    assert "no watcher" in json.loads(capsys.readouterr().out)["reason"]


def test_a_claim_is_active_while_the_lifetime_it_names_holds(
    tmp_path, monkeypatch, dead_pid
):
    """One reading of what makes a claim active, and every hook comes through it.

    The claims this writes have to go to a relocated home. A record left in a shared
    directory outlives the run that made it, and a constant id in one is a name every
    run answers to: an earlier version of this test wrote into the developer's own
    `~/.local/state/leaf/claims`, one unreleased claim per run under this same id and
    nothing ever sweeping them. Seventy-six had collected when one of their pids came
    round again on a live process, and the rule below read as true for a claim no run
    of this test had made. `isolated_session` supplies the home.
    """
    page = tmp_path / "page"
    page.mkdir()
    record_claim(page, id="guarded")
    assert service_model.claim_is_active(service_model.page_claim(page))
    record_claim(page, id="guarded", released=events_model.now_iso())
    assert not service_model.claim_is_active(service_model.page_claim(page))
    record_claim(page, id="guarded", pid=dead_pid)
    assert not service_model.claim_is_active(service_model.page_claim(page))

    # A background job's claim names the job's record and no process at all, so the
    # pid the environment states — dead here — is nothing to this reader. Claimed
    # through the real door, which asks for an initialized page.
    (page / "comments.jsonl").write_bytes(b"")
    job = tmp_path / "job"
    job.mkdir()
    files_model.write_json(job / "state.json", {"sessionId": "guarded"})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "guarded")
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    assert service_model.claim_page(page)
    assert "pid" not in service_model.page_claim(page)
    assert service_model.claim_is_active(service_model.page_claim(page))
    # Deleting the job takes its record; the directory can stay behind empty.
    (job / "state.json").unlink()
    assert not service_model.claim_is_active(service_model.page_claim(page))

    # A dead claim answers for its own page and no more: the session's other
    # records are still walked, and the live one is still the session's page.
    other = tmp_path / "other"
    other.mkdir()
    (other / "comments.jsonl").write_bytes(b"")
    record_claim(other, id="guarded")
    assert service_model.owned_pages("guarded") == [other.resolve()]


def test_the_registered_hook_answers_out_of_interact_or_says_nothing(claimed, tmp_path):
    """The script a host actually runs decides nothing; it runs interact.py under uv.

    Driven the way a host drives it — a separate `python3`, the payload's own copy of
    the script, the hook payload on stdin — because the wiring is the subject, and no
    part of it (uv, the path to interact.py, the command name, the stdin protocol) is
    visible from inside this process.

    Failing open is the other half, and the case worth arranging is the one where
    interact.py never starts: silence on both streams and a return code that leaves
    the turn alone. It is also the case a hook cannot report, so nothing but this
    test ever sees it.
    """
    guard = PLUGIN_ROOT / "hooks" / "scripts" / "loop-guard.py"

    def run(payload, env=None):
        return subprocess.run(
            [sys.executable, str(guard)],
            input=payload,
            env=env or os.environ,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    stop = json.dumps({"hook_event_name": "Stop", "session_id": "s1"})
    answered = run(stop)
    assert answered.returncode == 0, answered.stderr
    assert answered.stdout, "nothing came back: interact.py never answered under uv"
    blocked = json.loads(answered.stdout)
    assert blocked["decision"] == "block"
    assert f"{claimed.resolve()}: no watcher" in blocked["reason"]

    # A session holding nothing is interact.py's answer too, now that the hook keeps
    # no cheaper reading of the claims to stand itself down by.
    stranger = run(json.dumps({"hook_event_name": "Stop", "session_id": "s2"}))
    assert (stranger.returncode, stranger.stdout, stranger.stderr) == (0, "", "")

    # The two shapes of a leaf failure a turn must not notice: interact.py raising,
    # and no uv there to raise it.
    crashed = run("not a hook payload")
    assert (crashed.returncode, crashed.stdout, crashed.stderr) == (0, "", "")
    unresolvable = run(stop, env=os.environ | {"PATH": str(tmp_path / "no-tools")})
    assert (unresolvable.returncode, unresolvable.stdout, unresolvable.stderr) == (
        0,
        "",
        "",
    )


def test_idle_cannot_close_a_page_over_events_nobody_read(claimed, capsys):
    """`leaf status PAGE idle` is the way out of the guard's other case, so it
    reads as the way out of this one too. The events are the user's: a page
    idled over them ends the leaf on someone still waiting for an answer, and
    from the browser that looks exactly like one that ran its course."""
    events_model.append_event(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    refused = CliRunner().invoke(cli_model.cli, ["status", str(claimed), "idle"])
    assert refused.exit_code == 1
    assert "1 update nobody has picked up" in refused.output
    assert schema_model.ACK_BATCH_INSTRUCTION in refused.output
    assert "wait owner must finish the delivery contract" in refused.output
    assert files_model.read_json(claimed / "status.json")["state"] != "idle"

    # `leaf wait` returns at once, and acknowledgement records that its output
    # reached model context. Reading it is not answering it, though: the same
    # user is still waiting, and now nothing will raise the comment again, so
    # idle holds until the thread has something under it.
    assert CliRunner().invoke(cli_model.cli, ["wait", str(claimed)]).exit_code == 0
    assert CliRunner().invoke(cli_model.cli, ["ack", str(claimed), "1"]).exit_code == 0
    refused = CliRunner().invoke(cli_model.cli, ["status", str(claimed), "idle"])
    assert refused.exit_code == 1
    assert "1 acknowledged comment with no answer" in refused.output
    assert files_model.read_json(claimed / "status.json")["state"] != "idle"

    comment = events_model.read_events(claimed)[0]["id"]
    assert (
        CliRunner()
        .invoke(cli_model.cli, ["reply", str(claimed), "--to", comment, "--text", "ok"])
        .exit_code
        == 0
    )
    assert (
        CliRunner().invoke(cli_model.cli, ["status", str(claimed), "idle"]).exit_code
        == 0
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # A worker's report holds idle the same way: idling over one would freeze its
    # provisional state on the page forever, with nobody left to absorb it.
    events_model.append_event(
        claimed,
        {
            "kind": "report",
            "author": "claude",
            "widget": "t1",
            "action": "status",
            "detail": {"status": "review"},
            "version": 1,
        },
    )
    refused = CliRunner().invoke(cli_model.cli, ["status", str(claimed), "idle"])
    assert refused.exit_code == 1
    assert "1 update nobody has picked up" in refused.output
    report = str(events_model.read_events(claimed)[-1]["seq"])
    assert (
        CliRunner().invoke(cli_model.cli, ["ack", str(claimed), report]).exit_code == 0
    )
    # A report is the agent's own news, so acknowledging it is the whole of what
    # it asks for; only a reader's comment owes an answer as well.
    assert (
        CliRunner().invoke(cli_model.cli, ["status", str(claimed), "idle"]).exit_code
        == 0
    )


def test_idle_cannot_race_past_an_event_arriving_after_its_pending_check(
    page_dir, spawn
):
    """The pending check and idle transition are one decision.

    A browser post serialized after the check but before the status write must
    keep the page open. Otherwise Stop sees an idle page, permits the turn to
    end, and leaves the newly appended event with no watcher to deliver it.
    """
    session_model.cmd_status(page_dir, "waiting", "comment on the prototype")
    marker = page_dir / "status-lock-requested"
    comments = open(  # noqa: SIM115 - held across the child transition
        page_dir / "comments.jsonl", "a+b"
    )
    fcntl.flock(comments, fcntl.LOCK_EX)
    probe = """\
from leaf_interact import service as service_model

original_flocked = service_model.flocked
comments = Path(os.environ["COMMENTS"]).resolve()
marker = Path(os.environ["MARKER"])

@contextlib.contextmanager
def observed_flocked(path, **kwargs):
    if Path(path).resolve() == comments:
        marker.write_text("requested", encoding="utf-8")
    with original_flocked(path, **kwargs) as stream:
        yield stream

service_model.flocked = observed_flocked
sys.argv = ["leaf", "status", os.environ["PAGE"], "idle"]
cli_model.cli()
"""
    process = spawn_probe(
        spawn,
        page_dir,
        probe,
        COMMENTS=page_dir / "comments.jsonl",
        MARKER=marker,
    )

    deadline = time.monotonic() + 10
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not marker.exists():
        comments.close()
        process.kill()
        process.communicate()
        pytest.fail("the idle command never requested the held comments-log lock")

    # The marker is immediately before the command's lock acquisition. In the
    # broken ordering it appears only after the empty pending read; in the fixed
    # ordering it appears before that read. Appending while this process owns the
    # lock therefore makes the old command idle and the fixed command refuse.
    comments.seek(0, os.SEEK_END)
    comments.write(
        (
            events_model.jsonl_line(
                {
                    "kind": "comment",
                    "id": "c1",
                    "author": "user",
                    "text": "one last thing",
                }
            )
            + "\n"
        ).encode()
    )
    comments.flush()
    os.fsync(comments.fileno())
    fcntl.flock(comments, fcntl.LOCK_UN)
    comments.close()

    out, err = process.communicate(timeout=60)
    assert process.returncode == 1, f"{out}{err}"
    assert "1 update nobody has picked up" in err
    assert files_model.read_json(page_dir / "status.json")["state"] == "waiting"


def test_session_end_releases_the_page_and_its_session_server_retires(claimed):
    assert hosting_model.start_server(claimed)  # a real detached server to clean up
    session_model.cmd_status(claimed, "waiting", "")
    hooks_model.cmd_hook({"hook_event_name": "SessionEnd", "session_id": "s1"})
    deadline = time.time() + 5
    while service_model.running_server(claimed):
        assert time.time() < deadline, "the unclaimed session server stayed up"
        time.sleep(0.05)
    assert files_model.read_json(claimed / "status.json")["state"] == "waiting"
    assert files_model.read_json(claimed / "service.json")["enabled"] is True
    claim = service_model.page_claim(claimed)
    assert claim is not None
    assert claim["released"] is not None
    assert service_model.owned_pages("s1") == []


def test_a_background_jobs_server_lives_as_long_as_the_job(
    page_dir, tmp_path, monkeypatch, dead_pid
):
    """A background job runs each sitting on a worker its daemon retires between
    them, so a claim naming that worker's pid takes the page down an hour after
    every turn. The job's record is the lifetime instead: the page stays held
    and served whatever became of the process that claimed it, and retires when
    the job is deleted — which takes the record and may leave the directory."""
    job = tmp_path / "job"
    job.mkdir()
    files_model.write_json(job / "state.json", {"sessionId": "bg-job"})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "bg-job")
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    assert service_model.claim_page(page_dir)
    assert hosting_model.start_server(page_dir)
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == "session"
    # Longer than the reaper's grace, so a server that was going to retire on the
    # dead pid has had the chance.
    time.sleep(schema_model.ORPHAN_GRACE_SECS + 0.5)
    assert service_model.running_server(page_dir)
    assert service_model.owned_pages("bg-job") == [page_dir.resolve()]
    assert http_model.presence(page_dir, [])["session_alive"] is True

    (job / "state.json").unlink()
    deadline = time.time() + 5
    while service_model.running_server(page_dir):
        assert time.time() < deadline, "the deleted job's server stayed up"
        time.sleep(0.05)
    assert service_model.owned_pages("bg-job") == []
    assert http_model.presence(page_dir, [])["session_alive"] is False


def test_a_claim_takes_the_job_lifetime_only_for_the_jobs_own_session(
    page_dir, tmp_path, monkeypatch
):
    """CLAUDE_JOB_DIR is inherited, so a session started under a background job's
    shell tool carries the job's directory while being a process of its own: its
    claim names its pid. A job record that is not there is refused, since a claim
    written on it would be over before the server it licensed came up."""
    job = tmp_path / "job"
    job.mkdir()
    files_model.write_json(job / "state.json", {"sessionId": "the-job"})
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "nested")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir)["pid"] == os.getpid()
    assert "job" not in service_model.page_claim(page_dir)

    (job / "state.json").unlink()
    with pytest.raises(SystemExit, match="names no job record"):
        service_model.claim_page(page_dir)


def test_a_server_exits_when_its_session_is_hard_killed(
    page_dir, session_process, managed_server
):
    owner = session_process()
    server = managed_server(page_dir, "abandoned", owner.pid)
    owner.terminate()
    owner.wait(timeout=5)

    server.wait(timeout=5)
    assert server.returncode == 0, server.stderr.read()
    assert files_model.read_json(page_dir / "service.json")["enabled"] is True
    assert not service_model.lock_is_held(page_dir / "server.lock")


def test_a_live_session_can_take_over_an_existing_server(
    page_dir, session_process, managed_server
):
    first, second = session_process(), session_process()
    server = managed_server(page_dir, "first", first.pid)
    record_claim(page_dir, id="second", pid=second.pid, agent="Codex")
    first.terminate()
    first.wait(timeout=5)
    assert server.poll() is None

    second.terminate()
    second.wait(timeout=5)
    server.wait(timeout=5)
    assert server.returncode == 0, server.stderr.read()
    assert files_model.read_json(page_dir / "service.json")["enabled"] is True


def test_server_start_hands_the_page_to_a_process_of_its_own(page_dir):
    """The command returns and the page stays up. Two long-running commands per
    leaf was one accident: `leaf wait` has to exit, its exit being how a comment
    reaches the agent, and the server has to not exit at all — so no one process
    does both, but only the watcher is the session's to hold open. The serve gets
    a session of its own, which is also what leaves a killed background task
    costing the watcher alone."""
    started = start_through_the_launcher(page_dir)
    assert started.returncode == 0, started.stderr
    url = started.stdout.strip()
    assert url.startswith("http://127.0.0.1:")
    assert "session server" in started.stderr
    info = service_model.running_server(page_dir)
    assert info and info["url"] == url
    # The child claims only after its refusal and bind checks, which is what lets
    # the loop's hooks find the session's pages without a failed start taking one.
    assert service_model.page_claim(page_dir)["id"] == "starter"
    service = files_model.read_json(page_dir / "service.json")
    assert service["lifetime"] == "session"
    assert set(service) == {"host", "bind", "port", "enabled", "lifetime"}
    state = urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()
    assert urllib.request.urlopen(state).status == 200


def test_server_start_forwards_flags_and_returns_service_output(page_dir):
    """`server start` states nothing about a serve itself. The flags go verbatim
    to the service it spawns and the account comes back from there, so the
    lifetime a flag declared and the refusal a running server earns are both that
    process's own words, carried out with its exit status."""
    standing = start_through_the_launcher(page_dir, "--standing")
    assert standing.returncode == 0, standing.stderr
    assert "standing server" in standing.stderr
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == "standing"
    assert service_model.page_claim(page_dir) is None

    refused = start_through_the_launcher(page_dir, "--host", "devbox.corp.example")
    assert refused.returncode != 0
    assert "already serving at" in refused.stderr
    assert "server stop" in refused.stderr
    # Nothing on stdout, so a caller reading the URL there reads no URL.
    assert not refused.stdout.strip()
    assert service_model.page_claim(page_dir) is None


@pytest.mark.parametrize("lifetime", ["standing", "session"])
def test_init_requires_explicit_quiescence_before_revendoring_the_contract(
    page_dir, spawn, monkeypatch, lifetime
):
    """Disabled desired state makes re-vendor replace the whole contract."""
    publish(page_dir)
    old_skill = page_dir.parent / "old-skill"
    old_script = old_skill / "scripts" / "interact.py"
    old_script.parent.mkdir(parents=True)
    old_script.write_text(Path(INTERACT_SCRIPT).read_text())
    shutil.copytree(
        Path(INTERACT_SCRIPT).parent / "leaf_interact",
        old_script.parent / "leaf_interact",
    )
    shutil.copytree(schema_model.ASSETS, old_skill / "assets")
    old_registry = files_model.read_json(page_dir / "registry.json")
    del old_registry["$events"]["kinds"]["comment"]["record"]["properties"]["attempt"]
    files_model.write_json(page_dir / "registry.json", old_registry)
    files_model.write_json(old_skill / "assets" / "registry.json", old_registry)

    if lifetime == "standing":
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
        monkeypatch.delenv("CLAUDE_PID")
    old_server = spawn(
        [
            sys.executable,
            str(old_script),
            "server",
            "run",
            str(page_dir),
            *(["--standing"] if lifetime == "standing" else []),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = old_server.stdout.readline().strip()
    assert url.startswith("http://127.0.0.1:")
    assert f"{lifetime} server" in old_server.stderr.readline()
    prior_status = files_model.read_json(page_dir / "status.json")
    prior_owner = service_model.page_claim(page_dir)

    endpoint = urllib.parse.urlsplit(url)._replace(path="/api/event").geturl()
    comment = {
        "kind": "comment",
        "version": 1,
        "text": "Can the replacement route this?",
        "attempt": "replacement_route_1",
    }
    status, body = fetch(endpoint, data=json.dumps(comment).encode(), token=None)
    assert status == 400
    assert (
        "Additional properties are not allowed ('attempt' was unexpected)"
        in (json.loads(body)["error"])
    )

    project_layer = page_dir.parent / ".leaf"
    project_layer.mkdir()
    (project_layer / "theme.css").write_text(":root { --accent: red; }\n")
    files_before = {
        path.relative_to(page_dir): path.read_bytes()
        for path in page_dir.rglob("*")
        if path.is_file()
    }
    runner = CliRunner()
    refused = runner.invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert refused.exit_code == 1
    assert "cannot re-vendor" in refused.output
    assert "server stop" in refused.output
    assert old_server.poll() is None
    assert {
        path.relative_to(page_dir): path.read_bytes()
        for path in page_dir.rglob("*")
        if path.is_file()
    } == files_before

    stopped = runner.invoke(cli_model.cli, ["server", "stop", str(page_dir)])
    assert stopped.exit_code == 0, stopped.output
    old_server.wait(timeout=5)

    revendored = runner.invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert revendored.exit_code == 0, revendored.output
    assert b":root { --accent: red; }" in (page_dir / "theme.css").read_bytes()
    owner_id = prior_owner["id"] if prior_owner else "starter"
    started = start_through_the_launcher(
        page_dir,
        session_id=owner_id,
    )
    assert started.returncode == 0, started.stderr
    assert started.stdout.strip() == url
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == lifetime
    assert service_model.page_claim(page_dir)["id"] == owner_id
    restored = files_model.read_json(page_dir / "status.json")
    assert restored == prior_status

    status, body = fetch(endpoint, data=json.dumps(comment).encode(), token=None)
    assert status == 200, body
    events = events_model.read_events(page_dir)
    assert [event["kind"] for event in events] == ["note", "comment"]
    assert events[-1]["attempt"] == comment["attempt"]


def test_server_stop_disables_desired_state_without_signalling_a_pid(
    page_dir, monkeypatch
):
    files_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": 41000,
            "enabled": True,
            "lifetime": "standing",
        },
    )
    (page_dir / "server.lock").write_bytes(b"")

    def unexpected_signal(*_args):
        pytest.fail("an unlocked record's pid was signalled")

    monkeypatch.setattr(os, "kill", unexpected_signal)

    assert hosting_model.cmd_stop(page_dir) == "no server running"
    assert files_model.read_json(page_dir / "service.json")["enabled"] is False


def test_session_end_cannot_release_a_page_claimed_by_its_successor(
    page_dir, monkeypatch
):
    serving(page_dir, 41000, "session")
    record_claim(page_dir, id="successor")
    session_model.cmd_status(page_dir, "waiting", "successor is reviewing")
    monkeypatch.setattr(hooks_model, "owned_pages", lambda _session_id: [page_dir])

    hooks_model.cmd_hook({"hook_event_name": "SessionEnd", "session_id": "predecessor"})

    assert service_model.page_claim(page_dir)["id"] == "successor"
    assert files_model.read_json(page_dir / "service.json")["enabled"] is True
    assert files_model.read_json(page_dir / "status.json")["detail"] == (
        "successor is reviewing"
    )
    assert service_model.running_server(page_dir)


def test_server_stop_waits_for_the_live_server_to_release_its_lease(
    page_dir, standing_server
):
    server = standing_server(page_dir)
    os.kill(server.pid, signal.SIGSTOP)
    outcomes, errors = [], []

    def stop():
        try:
            outcomes.append(hosting_model.cmd_stop(page_dir))
        except BaseException as error:  # noqa: BLE001 - carried to the assertion
            errors.append(error)

    stopping = threading.Thread(target=stop)
    stopping.start()
    try:
        deadline = time.time() + 5
        while files_model.read_json(page_dir / "service.json")["enabled"]:
            assert time.time() < deadline, "server stop never disabled the service"
            time.sleep(0.01)
        returned_while_paused = not stopping.is_alive()
    finally:
        os.kill(server.pid, signal.SIGCONT)
    stopping.join(timeout=5)
    server.wait(timeout=5)

    assert not returned_while_paused, "server stop returned before lock release"
    assert not stopping.is_alive(), "server stop did not cross the release barrier"
    assert errors == []
    assert outcomes == ["stopped server"]
    assert not service_model.lock_is_held(page_dir / "server.lock")


def test_server_stop_closes_accepted_keep_alive_connections(page_dir, standing_server):
    server = standing_server(page_dir)
    service = files_model.read_json(page_dir / "service.json")
    connection = http.client.HTTPConnection(service["host"], service["port"])
    connection.request("GET", f"/api/state?t={service_model.host_key()}")
    response = connection.getresponse()
    assert response.status == 200
    response.read()
    accepted = connection.sock
    accepted.sendall(
        (
            f"GET /api/state?t={service_model.host_key()} HTTP/1.1\r\n"
            f"Host: {service['host']}\r\n"
        ).encode()
    )

    assert hosting_model.cmd_stop(page_dir) == "stopped server"
    server.wait(timeout=5)

    accepted.settimeout(1)
    try:
        accepted.sendall(b"\r\n")
        remainder = accepted.recv(1)
    except OSError:
        remainder = b""
    assert remainder == b""


def test_a_sessionless_server_ignores_a_stale_claim_and_requires_explicit_stop(
    page_dir, dead_pid, standing_server
):
    record_claim(page_dir, id="old-session", pid=dead_pid, agent="Codex")
    server = standing_server(page_dir)
    # The only held window in the suite, because it is the only assertion with nothing
    # to consume: a watcher that never starts states nothing, and the server going on
    # living is not an event to wait for (tests/CLAUDE.md, "A wait consumes a fact the
    # system states"). So the window is the grace a watcher would have acted after,
    # plus room to act — long enough that the bug, had it been here, would have shown.
    time.sleep(schema_model.ORPHAN_GRACE_SECS + 0.5)
    assert server.poll() is None, "a manual server inherited the stale session claim"
    assert "stopped server" in hosting_model.cmd_stop(page_dir)
    server.wait(timeout=5)


def test_server_run_standing_declines_the_claim_a_host_session_offers(page_dir, spawn):
    """`--standing` from inside a host is the bare-shell statement made
    explicit: the launch declines the claim it could have made, so the server
    records the standing lifetime and the page stays nobody's — no watcher
    thread to stop it when the host pid goes, no SessionEnd reaper. The host is
    the suite's own session, which every command here already runs under."""
    process = spawn(
        [
            sys.executable,
            str(INTERACT_SCRIPT),
            "server",
            "run",
            "--standing",
            str(page_dir),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout.readline().startswith("http://127.0.0.1:")
    assert "standing server" in process.stderr.readline()
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == "standing"
    assert service_model.page_claim(page_dir) is None


def test_server_run_standing_refuses_to_adopt_a_session_server(page_dir):
    """A stated lifetime contradicted by the running server is refused with the
    way out named, exactly as a stated `--host` is — not silently ignored."""
    serving(page_dir, 1, "session")
    result = CliRunner().invoke(
        cli_model.cli, ["server", "run", "--standing", str(page_dir)]
    )
    assert result.exit_code != 0
    assert "server stop" in result.output


def test_a_standing_server_outlives_a_session_that_picks_the_page_up(
    page_dir, standing_server, monkeypatch, capsys
):
    """The standing serve, the whole way round: a page kept up across sessions, and a
    session that works on it for an afternoon and goes. Picking a page up earns the
    watch obligation and nothing else, so the session's end must take down neither the
    process it didn't start nor a leaf that outlives it."""
    server = standing_server(page_dir)
    launched = service_model.running_server(page_dir)
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == "standing"

    # A session picks the page up, the way `leaf wait` does.
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "later")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    session_model.cmd_status(page_dir, "waiting", "")
    # Without this the hook would skip the page for the wrong reason and the test
    # would pass with the bug in: the standing check has to be what spares it.
    assert page_dir in service_model.owned_pages("later")

    # A `server run` of its own finds this one up and reports the lifetime the
    # running server has, not the one this claiming launch would have given it.
    hosting_model.cmd_serve(page_dir)
    served = capsys.readouterr()
    assert served.out.strip() == launched["url"]
    assert "standing server" in served.err

    hooks_model.cmd_hook({"hook_event_name": "SessionEnd", "session_id": "later"})

    # The synchronous hook left the standing service enabled and live.
    assert service_model.running_server(page_dir) == launched
    assert files_model.read_json(page_dir / "status.json")["state"] == "waiting"
    assert service_model.page_claim(page_dir)["released"] is not None
    assert page_dir not in service_model.owned_pages("later")
    # Explicit stop crosses that server's release barrier before returning.
    assert "stopped server" in hosting_model.cmd_stop(page_dir)
    server.wait(timeout=5)


def test_state_reports_whether_the_owning_session_still_exists(claimed, dead_pid):
    """The banner's one hard fact: a status.json claim outlives its session, the
    owning pid doesn't."""
    assert page_state(claimed)["session_alive"] is True
    record_claim(claimed, pid=dead_pid)
    assert page_state(claimed)["session_alive"] is False
