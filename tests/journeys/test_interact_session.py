"""Watch, ownership, hook, and server-lifetime tests."""

import json
import os
import shlex
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from xml.etree import ElementTree

import psutil
import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    PAGE,
    STATED_TIMEOUT,
    append_carried_log_record,
    append_command,
    check,
    declare_idle,
    fetch,
    fetch_hanging_up,
    install_payload,
    page_packages,
    page_state,
    publish,
    record_claim,
    release_codex_command,
    serving,
    spawn_probe,
    start_server_command,
    state_json,
    thread_records,
    wait_for,
    yaml_document,
)
from leaf import cli as cli_model
from leaf import codex as codex_model
from leaf import codex_adapter as codex_adapter_model
from leaf import codex_state as codex_state_model
from leaf import delivery as delivery_model
from leaf import event_contracts as event_contracts_model
from leaf import event_log as events_model
from leaf import event_meaning as event_meaning_model
from leaf import files as files_model
from leaf import hooks as hooks_model
from leaf import hosting as hosting_model
from leaf import leases as leases_model
from leaf import machine as machine_model
from leaf import page_view as page_view_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from leaf import thread_context as thread_context_model
from leaf.registry import storage as registry_storage
from leaf_dev.arms import PageClient
from leaf_dev.page_fixtures import package_selection_args
from model.test_interact_session import (  # noqa: F401 (fixtures)
    SETTLING_ACCEPT,
    SETTLING_DECISION,
    _delivery_item,
    _interaction_prompt_evidence,
    _settling_page,
    adapter_log,
    app_server_fixture,
    codex_records,
    codex_start_announcement,
    continued,
    current_codex_record,
    delivered,
    fake_codex_cli,
    last_deliverable_seq,
    receive_through,
    title_codex_fixture,
    woken,
)


def test_a_terminated_page_server_stops_its_title_server(
    title_codex, codex_claimed_page
):
    """SIGTERM, as a logout or a user's kill sends, ends a page server through its
    exit handlers, so the App Server a title request holds stops with it."""
    page = codex_claimed_page
    (page / "index.html").write_text(
        '<!doctype html>\n<html lang="en">\n<head><title>t</title></head>\n'
        '<body><main><section id="plan"><h2>Plan</h2>\n'
        "<p>Export runs nightly.</p></section></main></body>\n</html>\n"
    )
    publish(page)
    client = PageClient(server_model.running_server(page)["url"])
    client.post(
        {
            "kind": "comment",
            "revision": client.state()["active"]["revision"],
            "text": "Why is the export slow?",
        }
    )
    title_server = int(
        wait_for(
            lambda: title_codex.read_text() if title_codex.exists() else "",
            bool,
            failure="the page server started no title server",
        )
    )
    [page_server] = [
        process
        for process in psutil.process_iter(["cmdline"])
        if "_serve" in (process.info["cmdline"] or [])
        and str(page) in process.info["cmdline"]
    ]
    page_server.terminate()
    page_server.wait(timeout=STATED_TIMEOUT)
    wait_for(
        lambda: not psutil.pid_exists(title_server),
        bool,
        failure="the title server outlived its page server",
    )


def test_a_page_ask_that_settles_a_thread_carries_its_thread(page_dir, capsys):
    """A gesture settles a thread through its widget's `resolves`, and the
    widget it is made on need not stand in that thread — for the one shipped
    settling verb, `lf-suggestion`'s decide, it stands on the page and in no
    thread at all. Reading the sending widget alone therefore left the gesture
    that closes a thread as the one gesture arriving with nothing behind it."""
    _settling_page(page_dir)
    receive_through(page_dir, 1)  # c1 delivered; its words are the
    capsys.readouterr()  # envelope's to carry from here
    append_command(page_dir, dict(SETTLING_ACCEPT))
    # The action door accepts this event, so the shape is the product's own.
    events = events_model.read_events(page_dir)
    assert (
        event_contracts_model.action_contract_error(
            page_view_model.PageView(page_dir),
            events[-1],
            event_meaning_model.AdmissionReadings(
                page_view_model.PageView(page_dir),
                events,
                registry_storage.require_registry(page_dir),
            ),
        )
        is None
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [t["resolved"] for t in state_json(page_dir)["threads"]] == ["user"]
    assert [t["id"] for t in header["threads"]] == ["c1"], json.dumps(header)
    message = header["threads"][0]["messages"][0]
    assert "text" not in message
    assert message["drawing"] == SETTLING_DECISION["drawing"]


def test_an_undo_of_a_page_ask_carries_the_thread_it_reopens(page_dir, capsys):
    """Withdrawing that gesture reopens the thread, so the delivery owes
    the same reading the accept did."""
    _settling_page(page_dir)
    accepted = append_command(page_dir, dict(SETTLING_ACCEPT))
    receive_through(page_dir, last_deliverable_seq(page_dir))
    capsys.readouterr()
    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": accepted["id"]}
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [t["resolved"] for t in state_json(page_dir)["threads"]] == [None]
    assert [t["id"] for t in header["threads"]] == ["c1"], json.dumps(header)


def test_exact_thread_history_and_wait_share_indirect_resolution_events(
    page_dir, capsys
):
    """Rejecting an accepted answer, undoing that rejection, and later restating
    what the answer rested on all change the same thread without naming it
    directly. Exact history and live delivery use one Leaf-owned membership join."""
    _settling_page(page_dir)
    accepted = append_command(page_dir, dict(SETTLING_ACCEPT))
    receive_through(page_dir, last_deliverable_seq(page_dir))
    capsys.readouterr()

    rejected = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-refill",
            "action": "decide",
            "detail": {"outcome": "reject"},
        },
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [thread["id"] for thread in header["threads"]] == ["c1"]

    rejected_seq = next(
        event["seq"]
        for event in events_model.read_events(page_dir)
        if event["id"] == rejected["id"]
    )
    receive_through(page_dir, rejected_seq)
    capsys.readouterr()
    undone = append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": rejected["id"]}
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [thread["id"] for thread in header["threads"]] == ["c1"]

    restated = append_carried_log_record(
        page_dir,
        {
            "kind": "note",
            "author": "agent",
            "version": 2,
            "revision": 2,
            "text": "rewrote the suggestion",
            "restated": ["sug-refill"],
        },
    )
    assert thread_records(page_dir, "c1") == [
        "c1",
        accepted["id"],
        rejected["id"],
        undone["id"],
        restated["id"],
    ]
    assert state_json(page_dir)["threads"][0]["resolved"] is None


def test_the_envelope_stops_growing_with_the_thread(page_dir, capsys):
    """A delivery reprints the whole thread every time, because the agent it is
    for may hold none of it. Unbounded, the header grows with the thread
    until it alone outgrows the output it prints into — and that is the one
    shape acknowledgement cannot recover from, since the ack rule's remedy for
    truncation is to rerun, and a rerun prints the same oversize header. So the
    digest keeps the message that opened the thread and the most recent, and
    says how many it dropped between."""
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    serving(page_dir, 1)
    markup = (
        '<lf-options id="{i}" choose>'
        + "".join(
            f'<lf-option id="{{i}}-o{n}"><strong>Option {n}</strong> '
            + "z" * 60
            + "</lf-option>"
            for n in range(3)
        )
        + "</lf-options>"
    )
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "y" * 188},
    )
    initial_thread_state_size = len(json.dumps(state_json(page_dir)["threads"]))
    parent, headers = root["id"], []
    assert service_model.claim_page(page_dir)
    for turn in range(30):
        agent = append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": parent,
                "text": "x" * 532,  # the shipped ship-review example's reply length
                "markup": markup.format(i=f"w{turn}"),
            },
        )
        parent = append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": "user", "parent": agent["id"], "text": "ok"},
        )["id"]
        assert session_model.cmd_wait(page_dir) == 0
        _, batch, _ = delivered(capsys)
        headers.append(len(json.dumps(batch["threads"])))
        receive_through(page_dir, last_deliverable_seq(page_dir))
        capsys.readouterr()

    # Flat, not merely slower: twenty further exchanges add only the few
    # characters a longer sequence number spends. Page state likewise keeps the
    # thread itself flat; its separate element inventory grows here because
    # every reply deliberately adds a live widget contract.
    assert headers[-1] - headers[9] < 100, headers
    assert (
        len(json.dumps(state_json(page_dir)["threads"])) - initial_thread_state_size
        < 100
    )
    [thread] = batch["threads"]
    assert len(thread["messages"]) == thread_context_model.SHOWN
    assert thread["elided"]["messages"] == 52
    # The opening message survives the bound: it holds what the thread is about.
    assert thread["messages"][0]["id"] == root["id"]


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


@pytest.mark.parametrize("reclaimed", ["delivered", "another"])
def test_codex_app_server_restart_finishes_an_accepted_batch_without_starting_it_again(
    codex_claimed_page, app_server, under_codex, codex_env, tmp_path, reclaimed
):
    """The App Server twin of the queue case above. The restarted adapter reads back
    the turn that took the delivery while the page's claim still names the task's
    previous generation, before the restart claims it again, or when the restart
    claims another page first. The batch's receipt and the turn's final answer both
    land on the page all the same, so the comment is not started a second time."""
    page = codex_claimed_page
    claimed = page
    if reclaimed == "another":
        claimed = tmp_path / "another-page"
        subprocess.run(
            [*LEAF_COMMAND, "page", "init", claimed], env=codex_env, check=True
        )
    # The turn's answer is a reply, which needs a valid page to land on.
    (page / "index.html").write_text(PAGE, encoding="utf-8")
    publish(page)
    program, _log = fake_codex_cli(tmp_path)
    append_carried_log_record(
        page,
        {"kind": "comment", "id": "accepted", "author": "user", "text": "hi"},
    )
    delivered = events_model.read_events(page)[-1]
    session_model.cmd_waiting(page, "comment on the prototype")
    with service_model.PageTransaction(page) as transaction:
        reading = session_model.PageTick(
            page,
            transaction.status,
            [delivered],
            True,
            "watching",
            False,
            None,
            transaction,
        )
        assert codex_adapter_model.capture_batch("codex-thread", reading)
    record_path, record = current_codex_record("codex-thread")
    prepared = codex_model.offer_delivery(
        record_path, codex_model.read_record(record_path), transport="app-server"
    )
    record = files_model.read_json(record_path)
    record.update(
        state="opened", turn="taken", pending=list(range(len(record["batches"])))
    )
    cleanup_model.write_json(record_path, record)
    starts = []

    def handle(socket):
        for raw in socket:
            request = json.loads(raw)
            method = request.get("method")
            if method == "initialize":
                socket.send(json.dumps({"id": request["id"], "result": {}}))
            elif method == "thread/resume":
                turns = [
                    {
                        "id": "taken",
                        "status": "completed",
                        "items": [
                            _delivery_item(prepared.payload),
                            {
                                "id": "answer",
                                "type": "agentMessage",
                                "phase": "final_answer",
                                "text": "Answered before the restart",
                            },
                        ],
                    }
                ]
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {
                                "thread": {
                                    "id": "codex-thread",
                                    "status": {"type": "idle"},
                                    "turns": turns,
                                }
                            },
                        }
                    )
                )
            elif method == "thread/turns/list":
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {"data": [], "nextCursor": None},
                        }
                    )
                )
            elif method == "turn/start":
                starts.append(request)
                socket.send(
                    json.dumps(
                        {"id": request["id"], "result": {"turn": {"id": "again"}}}
                    )
                )

    endpoint = app_server(handle)
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join(
            [
                *LEAF_COMMAND,
                "codex",
                "start",
                str(claimed),
                "--codex-path",
                str(program),
                "--app-server",
                endpoint,
            ]
        ),
        codex_env | {"CODEX_THREAD_ID": "codex-thread"},
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    release_codex_command(claimed, started, finished)
    out, err = started.communicate(timeout=STATED_TIMEOUT)
    assert started.returncode == 0, f"{out}{err}"

    try:
        wait_for(
            lambda: [
                event["text"]
                for event in events_model.read_events(page)
                if event["kind"] == "reply"
            ],
            lambda replies: replies == ["Answered before the restart"],
            failure="the restarted turn's answer did not reach the page",
        )
        wait_for(
            lambda: files_model.read_json(page / "cursor.json"),
            lambda cursor: cursor == {"seq": delivered["seq"]},
            failure="the accepted delivery cursor was not recovered",
        )
        assert starts == []
    finally:
        for held in {page, claimed}:
            declare_idle(held)
        cleanup_model.end_session("codex-thread")
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        lambda live: not live,
        failure="the Codex adapter stayed live after releasing its page",
    )


@pytest.mark.parametrize(
    "delivery_fault",
    [None, "retry"],
    ids=["steady", "uncertain-queue-retry"],
)
def test_codex_delivery_outlives_the_starting_command_and_acknowledges(
    codex_claimed_page, under_codex, codex_env, tmp_path, delivery_fault, capsys
):
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page, "comment on the prototype")
    environment = codex_env | {
        "CODEX_THREAD_ID": "codex-thread",
        "FAKE_CODEX_LOG": str(log),
        "FAKE_CODEX_EXPECT_CWD": str(machine_model.state_home()),
    }
    if delivery_fault == "retry":
        environment["FAKE_CODEX_QUEUE_FAILURE_ONCE"] = str(
            tmp_path / "uncertain-queue-response"
        )
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join(
            [
                *LEAF_COMMAND,
                "codex",
                "start",
                str(page),
                "--codex-path",
                os.path.relpath(program),
            ]
        ),
        environment,
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # The fake Codex wrapper models one shell command, while a real task's Codex
    # ancestor remains alive. Keep that already-proven lifetime standing so this
    # test can isolate the adapter after its starting shell is gone.
    # Transfer the claim while that ancestor is still alive.
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        bool,
        failure="the Codex adapter did not start",
    )
    announcement = codex_start_announcement(started)
    claim = service_model.page_claim(page)
    before_release = cleanup_model.session_record("codex-thread")
    release_codex_command(page, started, finished)
    after_release = cleanup_model.session_record("codex-thread")
    assert service_model.page_claim(page)["generation"] == claim["generation"]
    assert after_release["generation"] == before_release["generation"]
    assert after_release["turn"] == before_release["turn"]
    out, err = started.communicate(timeout=STATED_TIMEOUT)
    out = announcement + out
    assert started.returncode == 0, f"{out}{err}"
    assert json.loads(out)["task"] == "codex-thread"
    assert json.loads(out)["started"] is True
    try:
        wait_for(
            lambda: (
                codex_adapter_model.adapter_is_live("codex-thread"),
                page_state(page)["listening"],
            ),
            all,
            failure="the Codex adapter did not become live and listening",
        )

        assert service_model.page_claim(page)["turn_closed"] is None
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "hello adapter"}
        )
        comments = [events_model.read_events(page)[-1]]
        wait_for(
            lambda: files_model.read_json(page / "cursor.json"),
            lambda cursor: cursor == {"seq": 1},
            failure=lambda: (
                "the adapter did not acknowledge its batch: "
                f"deliveries={codex_records('codex-thread')!r}; "
                f"log={adapter_log('codex-thread')!r}"
            ),
        )

        hooks_model.cmd_hook(
            "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
        )
        assert capsys.readouterr().out == ""

        hooks_model.cmd_hook(
            "codex",
            {"hook_event_name": "UserPromptSubmit", "session_id": "codex-thread"},
        )
        assert capsys.readouterr().out == ""
        assert [
            item["stage"] for item in page_state(page)["activity"]["obligations"]
        ] == ["picked_up"]
        hooks_model.cmd_hook(
            "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
        )
        reason = json.loads(capsys.readouterr().out)["reason"]
        assert "1 acknowledged user update with no answer" in reason

        for text in ("second click", "third click"):
            append_carried_log_record(
                page, {"kind": "comment", "author": "user", "text": text}
            )
            comments.append(events_model.read_events(page)[-1])
        wait_for(
            lambda: files_model.read_json(page / "cursor.json"),
            lambda cursor: cursor == {"seq": comments[-1]["seq"]},
            failure="the cursor did not reach the later delivery",
        )

        calls = [json.loads(line) for line in log.read_text().splitlines()]
        assert calls[0] == ["queue", "--help"]
        queued = [call for call in calls if "--thread" in call]
        assert len(queued) == (4 if delivery_fault == "retry" else 3)
        prompts = [call[call.index("--message") + 1] for call in queued]
        assert len(set(prompts)) == 3
        unique_prompts = list(dict.fromkeys(prompts))
        assert len(unique_prompts) == 3
        payloads = []
        for prompt in unique_prompts:
            delivery = ElementTree.fromstring(prompt.splitlines()[1])
            assert delivery.tag == "leaf-delivery"
            assert delivery.attrib["operation"] == "delivery read"
            assert set(delivery.attrib) == {"operation", "id"}
            payload_path = delivery_model.delivery_path(delivery.attrib["id"])
            assert payload_path.exists()
            payload = files_model.read_json(payload_path)
            assert payload["format"] == delivery_model.DELIVERY_FORMAT
            assert all(
                set(batch)
                == {"page", "claim", "through_seq", "threads", "handling", "events"}
                for batch in payload["batches"]
            )
            queue_history = (
                codex_state_model.delivery_dir("codex-thread")
                / "history"
                / payload_path.name
            )
            # The page cursor is durable before the adapter records that receipt and
            # archives its queue. Wait for that second boundary instead of treating the
            # cursor's visibility as proof that the history move is already complete.
            queue = wait_for(
                lambda queue_history=queue_history: files_model.read_json(
                    queue_history
                ),
                lambda reading: reading is not None,
                failure=f"the delivery did not reach history at {queue_history}",
            )
            assert queue["state"] == "queued"
            assert queue["pending"] == []
            payloads.append(payload)
            assert len(prompt.encode()) < 1024
        assert [
            event["id"]
            for payload in payloads
            for batch in payload["batches"]
            for event in batch["events"]
        ] == [comment["id"] for comment in comments]
        assert files_model.read_json(page / "cursor.json") == {
            "seq": comments[-1]["seq"]
        }
        assert codex_adapter_model.adapter_is_live("codex-thread")

        for comment in comments:
            thread_model.post_reply(
                page, {"to": comment["id"], "for": comment["id"]}, "received"
            )
        declare_idle(page)
    finally:
        cleanup_model.end_session("codex-thread")

    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        lambda live: not live,
        failure="the Codex adapter stayed live after finishing its deliveries",
    )


def test_adding_a_page_cannot_race_the_codex_adapter_exit(
    codex_claimed_page, under_codex, codex_env, tmp_path, spawn
):
    first = codex_claimed_page
    second = tmp_path / "second-page"
    program, log = fake_codex_cli(tmp_path)
    environment = codex_env | {
        "CODEX_THREAD_ID": "codex-thread",
        "FAKE_CODEX_LOG": str(log),
    }
    session_model.cmd_waiting(first, "first page")
    start_lock = codex_adapter_model.adapter_start_lock_path("codex-thread")
    read_gate = tmp_path / "adapter-read-gate"
    os.mkfifo(read_gate)
    reading = tmp_path / "adapter-reading"
    marker = tmp_path / "adapter-final-recheck"
    probe = """\
from leaf import codex_adapter as codex_adapter_model
from leaf import codex_state as codex_state_model

native_read_watch_pass = codex_adapter_model.read_watch_pass
native_flocked = codex_adapter_model.flocked
finishing = False

def observed_read_watch_pass(*args, **kwargs):
    global finishing
    reading = Path(os.environ["READING"])
    if not reading.exists():
        reading.write_text("reading", encoding="utf-8")
        with open(os.environ["READ_GATE"], "rb") as gate:
            gate.read(1)
    reading = native_read_watch_pass(*args, **kwargs)
    finishing = reading.outcome is not None or not reading.live
    return reading

@contextlib.contextmanager
def observed_flocked(path, **kwargs):
    if finishing and Path(path).resolve() == Path(os.environ["START_LOCK"]).resolve():
        Path(os.environ["MARKER"]).write_text("requested", encoding="utf-8")
    with native_flocked(path, **kwargs) as stream:
        yield stream

codex_adapter_model.read_watch_pass = observed_read_watch_pass
codex_adapter_model.flocked = observed_flocked
raise SystemExit(codex_adapter_model.run_adapter(os.environ["CODEX_PATH"]))
"""
    adapter = spawn_probe(
        spawn,
        first,
        probe,
        CLAUDE_CODE_SESSION_ID="",
        CLAUDE_PID="",
        CLAUDE_JOB_DIR="",
        CODEX_THREAD_ID="codex-thread",
        CODEX_PATH=program,
        START_LOCK=start_lock,
        READ_GATE=read_gate,
        READING=reading,
        MARKER=marker,
        FAKE_CODEX_LOG=log,
    )
    wait_for(
        lambda: (
            codex_adapter_model.adapter_is_live("codex-thread"),
            page_state(first)["listening"],
            reading.exists(),
        ),
        all,
        failure="the first adapter did not begin its page read",
    )

    subprocess.run([*LEAF_COMMAND, "page", "init", second], check=True)
    standing = subprocess.run(
        [*LEAF_COMMAND, "server", "start", second, "--standing"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(standing.stdout)["url"].startswith("http://127.0.0.1:")
    session_model.cmd_waiting(second, "second page")
    starter = None
    finished = tmp_path / "second-start-finished"
    starter_ready = tmp_path / "second-start-lock"
    start_program = """\
import contextlib, json, os, sys
from pathlib import Path
from leaf import codex_adapter
native_flocked = codex_adapter.flocked
@contextlib.contextmanager
def observed_flocked(path):
    if Path(path).resolve() == Path(sys.argv[3]).resolve():
        Path(sys.argv[4]).write_text("requested")
    with native_flocked(path) as held:
        yield held
codex_adapter.flocked = observed_flocked
print(json.dumps(codex_adapter.cmd_codex_start(Path(sys.argv[1]), sys.argv[2])), flush=True)
"""
    try:
        with cleanup_model.flocked(start_lock):
            declare_idle(first)
            with open(read_gate, "wb") as gate:
                gate.write(b"1")
            wait_for(
                marker.exists,
                bool,
                failure="the first adapter did not reach its final start-lock recheck",
            )
            starter = under_codex(
                shlex.join(
                    [
                        sys.executable,
                        "-c",
                        start_program,
                        str(second),
                        str(program),
                        str(start_lock),
                        str(starter_ready),
                    ]
                ),
                environment,
                finished=finished,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            wait_for(
                starter_ready.exists,
                bool,
                failure="the second start did not request the startup lock",
            )
            assert service_model.page_claim(second) is None

        announcement = codex_start_announcement(starter)
        release_codex_command(second, starter, finished)
        out, err = starter.communicate(timeout=STATED_TIMEOUT)
        out = announcement + out
        assert starter.returncode == 0, f"{out}{err}"
        wait_for(
            lambda: (
                codex_adapter_model.adapter_is_live("codex-thread"),
                page_state(second)["listening"],
            ),
            all,
            failure="the adapter exited after the second page joined its watch",
        )
    finally:
        if starter is not None and starter.poll() is None:
            starter.terminate()
            starter.wait(timeout=STATED_TIMEOUT)
        declare_idle(second)
        cleanup_model.end_session("codex-thread")
        subprocess.run([*LEAF_COMMAND, "server", "stop", second], check=True)

    out, err = adapter.communicate(timeout=STATED_TIMEOUT)
    assert adapter.returncode == 0, f"{out}{err}"


def test_a_user_move_no_watcher_will_pick_up_messages_its_claude_code_session(
    server, page_dir, tmp_path, monkeypatch, socket_dir, snapshot
):
    """A running turn's Stop hook carries a user move into that turn, and a live
    `leaf wait` wakes the session for one, so the move nobody picks up arrives at a Claude
    Code claim whose turn has closed with no wait lease held — a watcher that died
    after the turn ended. The server then messages that session's socket, found
    by session id in Claude Code's session registry, once per closed turn: a user
    ticking three boxes must not queue three turns or three approvals, and input
    left unacknowledged when the Stop hook failed open must not silence the next
    closed turn.

    The server sends inside the event request, and a Unix connection is queued in
    the listener's backlog before `connect` returns, so a listener with nothing to
    accept once the POST has answered was never messaged."""
    closed = "2026-09-17T09:00:00+00:00"
    publish(page_dir)
    config = tmp_path / "claude"
    (config / "sessions").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    listeners = {}
    for pid, session_id in ((4101, "s1"), (4102, "s2")):
        address = str(socket_dir / f"{pid}.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(address)
        listener.listen()
        listener.setblocking(False)
        listeners[session_id] = listener
        cleanup_model.write_json(
            config / "sessions" / f"{pid}.json",
            {"pid": pid, "sessionId": session_id, "messagingSocketPath": address},
        )
        cleanup_model.write_json(
            config / "sessions" / f"{pid}.k{pid}.key",
            {"peerToken": f"token-{session_id}"},
        )

    def react(text):
        status, body = fetch(
            f"{server}/api/event",
            data=json.dumps({"kind": "comment", "revision": 1, "text": text}).encode(),
        )
        assert status == 200, body
        return json.loads(body)["state"]["events"][-1]["seq"]

    def messages(session_id):
        try:
            peer, _ = listeners[session_id].accept()
        except BlockingIOError:
            return None
        with peer:
            peer.settimeout(STATED_TIMEOUT)
            data = b"".join(iter(lambda: peer.recv(4096), b""))
        return [json.loads(line) for line in data.decode().splitlines()]

    try:
        # A turn still running: its Stop hook carries the move.
        record_claim(page_dir)
        react("while the turn runs")
        assert messages("s1") is None

        # A live watcher delivers it.
        claim = record_claim(page_dir, turn_closed=closed)
        lease = leases_model.take_lease(
            leases_model.waiter_lease_path(page_dir, claim["id"])
        )
        assert lease
        react("while a wait holds the lease")
        leases_model.release_lease(lease)
        assert messages("s1") is None

        # Codex's detached adapter queues its own turns; the socket is Claude Code's.
        record_claim(page_dir, harness="codex", turn_closed=closed)
        react("to a Codex task")
        assert messages("s1") is None

        record_claim(page_dir, turn_closed=closed)
        react("after the watcher died")
        auth, user = messages("s1")
        assert auth == {"type": "auth", "token": "token-s1"}
        assert user["type"] == "user" and user["session_id"] == "s1"
        assert user["message"]["role"] == "user"
        assert str(page_dir.resolve()) in user["message"]["content"]
        snapshot.check(
            yaml_document(
                "A real user POST reaches the Claude Code socket after its watcher died.\n"
                "This is the complete user frame, without the separate authentication frame.",
                _interaction_prompt_evidence(page_dir, {"socket user frame": user}),
            )
        )
        assert messages("s2") is None
        react("in the same closed turn")
        assert messages("s1") is None

        # The next closed turn is messaged, whatever is still unacknowledged.
        record_claim(page_dir, turn="turn-2", turn_closed=closed)
        react("in the next closed turn")
        assert messages("s1") is not None

        # Another live session's socket is never a stand-in for the claimant's,
        # and input after a send nobody took tries again.
        record_path = config / "sessions" / "4101.json"
        record = files_model.read_json(record_path)
        record_path.unlink()
        record_claim(page_dir, turn="turn-3", turn_closed=closed)
        react("once the claimant's session has left the registry")
        assert messages("s1") is None and messages("s2") is None
        cleanup_model.write_json(record_path, record)
        react("once it is back")
        assert messages("s1") is not None

        # An interrupted turn runs no Stop hook, so only the session's own record
        # says it ended. A turn nothing has renewed for longer than the working
        # grace may still be running a long step, so it is not messaged; once the
        # record reads idle the input is, once for that ending and again for the
        # next interrupt under the same turn id.
        live = os.getpid()
        cleanup_model.write_json(
            config / "sessions" / f"{live}.k{live}.key", {"peerToken": "token-s1"}
        )
        opened = datetime.now().astimezone() - timedelta(minutes=20)
        record_claim(page_dir, turn="turn-4", turn_opened=opened.isoformat())
        cleanup_model.write_json(
            page_dir / "status.json",
            {"state": "waiting", "detail": "", "ts": opened.isoformat()},
        )
        # `None` leaves the record as it stands: more input after the same ending.
        # A `shell` flip is the same ending seen again; a new prompt renews the
        # turn, and the interrupt after it is a new one.
        for status, prompt, messaged in (
            ("busy", False, False),
            ("idle", False, True),
            (None, False, False),
            ("shell", False, False),
            ("busy", True, False),
            ("idle", False, True),
        ):
            if prompt:
                time.sleep(1)
                cleanup_model.prompt_turn("s1")
            if status is not None:
                time.sleep(0.01)
                cleanup_model.write_json(
                    record_path,
                    {
                        **record,
                        "pid": live,
                        "status": status,
                        "statusUpdatedAt": int(time.time() * 1000),
                    },
                )
            react(f"while the session's record reads {status}")
            assert (messages("s1") is not None) is messaged, status
    finally:
        for listener in listeners.values():
            listener.close()


def test_only_serving_or_claiming_a_page_puts_the_session_under_the_guard(
    page_dir, monkeypatch, capsys
):
    """Verifying a change to the page layer means driving throwaway pages, and the
    guard must not read a handful of test fixtures as a handful of abandoned
    pages. A directory this session only built and linted was handed to nobody.
    Claiming one is what puts a user on the other end, and from there the
    guard holds the session to it."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s7")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert check(page_dir).exit_code == 0
    assert service_model.owned_pages("s7") == []
    # `page init` left the page "working", which is the state the guard blocks on —
    # but only for a page some session answers for, and none does.
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s7"})
    assert capsys.readouterr().out == ""

    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    assert CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)]).exit_code == 2
    assert service_model.owned_pages("s7") == []
    claimed = CliRunner().invoke(cli_model.cli, ["page", "claim", str(page_dir)])
    assert claimed.exit_code == 0, claimed.output
    assert CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)]).exit_code == 0
    assert service_model.owned_pages("s7") == [page_dir.resolve()]

    # The Stop hook carries the input the wait woke the session for into the turn.
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s7"})
    reason = continued(capsys.readouterr().out)
    [batch] = json.loads(reason.split("\n")[1])["batches"]
    assert [event["text"] for event in batch["events"]] == ["hi"]


def test_revendor_and_serve_restore_input_after_an_unreadable_old_claim(
    claimed, capsys
):
    """A fresh serve restores delivery without interpreting an older claim.

    A plugin update may leave a claim and session record this version cannot
    read. Re-vendoring and serving again from the running session keeps the
    user's pending input and establishes current ownership for its prompt hook.
    """
    publish(claimed)
    started = start_server_command(claimed, session_id="s1")
    assert started.returncode == 0, started.stderr
    prior_claim = files_model.read_json(service_model.claim_path(claimed))
    prior_claim.pop("generation")
    prior_claim.pop("acquisition")
    prior_claim.update(pid=os.getpid(), turn="old-turn", turn_closed=None)
    cleanup_model.write_json(service_model.claim_path(claimed), prior_claim)
    cleanup_model.session_file("s1", cleanup_model.SESSION_SUFFIX).unlink()
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Still here"}
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    assert capsys.readouterr().out == ""
    assert service_model.page_claim(claimed) is None
    assert cleanup_model.session_record("s1") is not None

    theme = claimed / "theme.css"
    theme.write_text(theme.read_text() + "\n/* repair installed edit */\n")
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(claimed)])
    assert result.exit_code == 0, result.output
    assert "has no live session owner" in result.output
    restarted = start_server_command(claimed, session_id="s1")
    assert restarted.returncode == 0, restarted.stderr
    state_url = (
        urllib.parse.urlsplit(json.loads(restarted.stdout)["url"])
        ._replace(path="/api/state")
        .geturl()
    )
    with urllib.request.urlopen(state_url) as response:
        assert response.status == 200
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    [batch] = json.loads(context["additionalContext"].split("\n")[1])["batches"]
    assert batch["page"] == str(claimed)
    assert [event["id"] for event in batch["events"]] == [asked["id"]]


def test_the_app_s_shared_codex_is_not_taken_for_one_session_s_lifetime(
    tmp_path, under_codex, codex_env, codex_queue, native_codex_chat
):
    """The one word that separates the two Codex shapes, and the claim each writes.

    `CodexHarness.lifetime` finds a session by walking for the nearest `codex`
    ancestor. Under the CLI that process is the session and its pid is exact.
    The ChatGPT app runs one `codex ... app-server` for the whole app and every
    thread hangs off it, so the same walk handed every session one pid
    that outlives them all: a session-managed server checks `pid_alive` and
    never sees it die, and the page stays served until the app quits. Found in
    the wild as 133 unreleased claims naming a single app-server pid, 49 of
    their servers still up, the oldest 28 hours past its thread.

    Both runs go through the real claim door under a real process of that name,
    so what is asserted is the claim leaf writes rather than a reading of the
    walk. Nothing varies between them but the word.
    """

    def claimed(name, *, app_server):
        if app_server:
            native_codex_chat(name)
        page = tmp_path / name
        subprocess.run([*LEAF_COMMAND, "page", "init", page], env=codex_env, check=True)
        started = under_codex(
            shlex.join([*LEAF_COMMAND, "server", "start", str(page)]),
            codex_env | codex_queue | {"CODEX_THREAD_ID": name},
            app_server=app_server,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = started.communicate(timeout=STATED_TIMEOUT)
        assert started.returncode == 0, f"{out}{err}"
        claim = service_model.page_claim(page)
        subprocess.run(
            [*LEAF_COMMAND, "server", "stop", page], env=codex_env, check=True
        )
        return claim

    session = claimed("cli-thread", app_server=False)
    assert session["pid"] > 0
    assert "chat" not in session

    app = claimed("app-thread", app_server=True)
    assert "pid" not in app
    assert app["chat"] is True


def test_normal_server_restart_rearms_reconnect_notice_before_the_next_hook(
    claimed, capsys
):
    """A quick second outage earns a new notice without an intervening healthy hook."""
    first = start_server_command(claimed, session_id="s1")
    assert first.returncode == 0, first.stderr
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "SessionEnd", "session_id": "s1"}
    )
    wait_for(
        lambda: server_model.running_server(claimed),
        lambda running: not running,
        failure="the first ended session's server did not retire",
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    command = f"leaf server start {shlex.quote(str(claimed.resolve()))}"
    assert (
        command
        in json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ]
    )

    restarted = start_server_command(claimed, session_id="s1")
    assert restarted.returncode == 0, restarted.stderr
    assert service_model.claim_is_active(service_model.page_claim(claimed))
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "SessionEnd", "session_id": "s1"}
    )
    wait_for(
        lambda: server_model.running_server(claimed),
        lambda running: not running,
        failure="the restarted server did not retire after its session ended",
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    assert (
        command
        in json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ]
    )


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
