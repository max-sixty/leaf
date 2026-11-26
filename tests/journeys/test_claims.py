"""Page claims: which session and harness hold a page, what a claim records, when it
is active, and the leases and page locks that keep a wait and a claim exclusive."""

import json
import shlex
import subprocess
import time
from typing import cast

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND, hooks_run_this_tree
from interact_support import STATED_TIMEOUT, fetch, neighbour_page, record_claim

from leaf.base import harness as harness_model
from leaf.base import leases as leases_model
from leaf.base import server as server_model
from leaf.base import service as service_model
from leaf.base import state as cleanup_model
from leaf.base.detached import Handshake
from leaf.commands import cli as cli_model
from leaf_dev.commands import preview


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


import os
import threading
from concurrent.futures import ThreadPoolExecutor

from interact_support import (
    claim_and_wait_command,
    spawn_probe,
    wait_for,
)

from leaf.pages import vendoring as vendoring_model


def test_a_fresh_init_does_not_delete_a_concurrently_created_pages_claim(
    tmp_path, monkeypatch, spawn
):
    """The first page creation is one serialized transition."""
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "concurrent-page"
    reached_layer = threading.Event()
    resume = threading.Event()
    original_compose_layer = vendoring_model.compose_layer

    # Held where init composes the selection under the page lock, which runs on
    # every init.
    def held_compose_layer(*roots):
        reached_layer.set()
        assert resume.wait(timeout=STATED_TIMEOUT), (
            "the concurrent init never released its peer"
        )
        return original_compose_layer(*roots)

    monkeypatch.setattr(vendoring_model, "compose_layer", held_compose_layer)
    executor = ThreadPoolExecutor(max_workers=1)
    first = executor.submit(vendoring_model.cmd_init, page)
    try:
        assert reached_layer.wait(timeout=STATED_TIMEOUT), (
            "the first init never reached its held read"
        )
        requested = tmp_path / "second-init-requested"
        second = spawn_probe(
            spawn,
            page,
            """\
import fcntl
native_flock = fcntl.flock
identity = Path(os.environ["PAGE"]).stat()
def observed_flock(fd, operation):
    descriptor = fd if isinstance(fd, int) else fd.fileno()
    if operation == fcntl.LOCK_EX and os.path.samestat(os.fstat(descriptor), identity):
        try:
            native_flock(fd, operation | fcntl.LOCK_NB)
        except BlockingIOError:
            Path(os.environ["REQUESTED"]).write_text("blocked")
        else:
            raise AssertionError("the overlapping init bypassed the page lease")
    return native_flock(fd, operation)
fcntl.flock = observed_flock
sys.argv = ["leaf", "page", "init", os.environ["PAGE"]]
cli_model.cli()
""",
            REQUESTED=requested,
        )
        wait_for(
            requested.exists,
            bool,
            failure="the overlapping init never attempted the held page lease",
        )
        resume.set()
        first.result(timeout=STATED_TIMEOUT)
        second_out, second_err = second.communicate(timeout=STATED_TIMEOUT)
        assert second.returncode == 0, f"{second_out}{second_err}"
        idled = subprocess.run(
            [*LEAF_COMMAND, "page", "close", page],
            capture_output=True,
            text=True,
            check=False,
        )
        assert idled.returncode == 0, idled.stderr
        hooks_run_this_tree("new-owner")
        picked_up = subprocess.run(
            claim_and_wait_command(page),
            shell=True,
            env=os.environ
            | {
                "CLAUDE_CODE_SESSION_ID": "new-owner",
                "CLAUDE_PID": str(os.getpid()),
            },
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert picked_up.returncode == 2, picked_up.stderr
        claim_record_5 = service_model.page_claim(page)
        assert claim_record_5 is not None
        assert claim_record_5["id"] == "new-owner"
    finally:
        resume.set()
        executor.shutdown(wait=True, cancel_futures=True)
    assert first.done()
    claim_record_6 = service_model.page_claim(page)
    assert claim_record_6 is not None
    assert claim_record_6["id"] == "new-owner"


def test_page_list_names_each_page_and_the_session_holding_it(dead_pid):
    """`leaf page list` is how a session finds the machine's pages and which session
    each one's comments reach. A claimed page is listed with its claimant even
    while nothing serves it, since that is when "who holds it" matters most; a page
    nothing claimed is listed only while it serves, by its row."""
    pages = cleanup_model.state_home() / "pages"
    held, stopped, unclaimed = pages / "held", pages / "stopped", pages / "unclaimed"
    url = neighbour_page(held, title="Held page", port=59001)
    record_claim(held, id="s1", cwd="/work/held")
    registry = harness_model.claude_code_sessions()
    registry.mkdir(parents=True, exist_ok=True)
    cleanup_model.write_json(
        registry / f"{os.getpid()}.json",
        {
            "pid": os.getpid(),
            "sessionId": "s1",
            "status": "idle",
            "statusUpdatedAt": int(time.time() * 1000),
            "name": "Fix the build",
        },
    )
    neighbour_page(stopped, title="Stopped page", dead=True)
    record_claim(stopped, id="s2", pid=dead_pid, cwd="/work/stopped")
    neighbour_page(unclaimed, title="Unclaimed page", port=59002)

    listed = CliRunner().invoke(cli_model.cli, ["page", "list"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["pages"] == [
        {
            "page": str(held.resolve()),
            "title": "Held page",
            "url": url,
            "on_user": 0,
            "threads": {"open": 0, "unread": 0},
            "harness": "claude-code",
            "claim_session": "s1",
            "session_name": "Fix the build",
            "session_cwd": "/work/held",
            "session_alive": True,
        },
        {
            "page": str(stopped.resolve()),
            "title": "Stopped page",
            "url": None,
            "on_user": None,
            "threads": None,
            "harness": "claude-code",
            "claim_session": "s2",
            "session_name": None,
            "session_cwd": "/work/stopped",
            "session_alive": False,
        },
        {
            "page": str(unclaimed.resolve()),
            "title": "Unclaimed page",
            "url": server_model.page_url("127.0.0.1", 59002, server_model.host_key()),
            "on_user": 0,
            "threads": {"open": 0, "unread": 0},
            "harness": None,
            "claim_session": None,
            "session_name": None,
            "session_cwd": None,
            "session_alive": None,
        },
    ]


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
@pytest.mark.parametrize("handoff", ["start", "run"])
def test_failed_delivery_preserves_the_existing_preview(
    page_dir, monkeypatch, failure, handoff
):
    """Failure before acceptance preserves both listener and original watcher."""
    from leaf.base.harness import session_harness
    from leaf.base.server import running_server
    from leaf.base.service import page_claim
    from leaf.pages import hosting as hosting_model
    from leaf.pages.hosting import claim_and_start, cmd_serve, cmd_stop

    original = preview.PreviewService(page_dir, user=True)
    with original.starting() as url:
        pass
    claim = page_claim(page_dir)
    published = json.loads(
        server_model.SERVICE.file(page_dir / "service.json").read_text()
    )

    def refuse(_harness):
        assert page_claim(page_dir) == claim
        assert not original.ended
        raise failure("delivery refused")

    monkeypatch.setattr(hosting_model, "preparing_delivery", refuse)
    try:
        with pytest.raises(failure, match="delivery refused"):
            if handoff == "start":
                with claim_and_start(page_dir):
                    pass
            else:
                cmd_serve(page_dir, harness=session_harness(), acquire=True)
        assert page_claim(page_dir) == claim
        assert not original.ended
        assert (
            json.loads(server_model.SERVICE.file(page_dir / "service.json").read_text())
            == published
        )
        assert (current := running_server(page_dir)) is not None
        assert current["url"] == url
        assert fetch(url)[0] == 200
    finally:
        cmd_stop(page_dir)


@pytest.mark.parametrize("refusal", ["layer", "cancel"])
def test_failed_serving_preparation_never_publishes_a_takeover(
    page_dir, monkeypatch, refusal
):
    """A takeover refused or cancelled in preparation leaves the original claim."""
    from leaf.base.detached import StartRefused
    from leaf.base.service import page_claim
    from leaf.pages.hosting import claim_and_start, cmd_stop

    original = preview.PreviewService(page_dir, user=True)
    with original.starting():
        pass
    claim = page_claim(page_dir)
    cmd_stop(page_dir)
    # Keep the original watcher/claim, with its server down. Its next revival is
    # independent of a failed takeover's private preparation.
    record = json.loads(
        server_model.SERVICE.file(page_dir / "service.json").read_text()
    )
    record["enabled"] = True
    server_model.SERVICE.file(page_dir / "service.json").write_text(json.dumps(record))
    if refusal == "layer":
        from interact_support import vendored_at_another_protocol

        vendored_at_another_protocol(page_dir)
    else:
        from leaf.base import detached

        def interrupted(_socket, _data):
            assert page_claim(page_dir) == claim
            assert not original.ended
            raise KeyboardInterrupt

        monkeypatch.setattr(detached.socket.socket, "sendall", interrupted)
    try:
        with (
            pytest.raises(KeyboardInterrupt if refusal == "cancel" else StartRefused),
            claim_and_start(page_dir),
        ):
            assert page_claim(page_dir) == claim
            assert not original.ended
        assert page_claim(page_dir) == claim
        assert not original.ended
    finally:
        cmd_stop(page_dir)


@pytest.mark.parametrize("refusal", ["abort_reuse", "ended_session", "new_generation"])
def test_private_startup_keeps_previous_owner_until_acceptance(
    page_dir, monkeypatch, refusal
):
    from leaf.base.detached import StartRefused
    from leaf.base.service import page_claim
    from leaf.base.state import end_session, ensure_session
    from leaf.pages.hosting import claim_and_start, cmd_stop

    original = preview.PreviewService(page_dir, user=True)
    with original.starting() as url:
        pass
    previous = page_claim(page_dir)
    # A different harness is the candidate, so ending its session cannot itself end
    # the original watcher while the candidate is still unpublished.
    from leaf.base import harness

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "candidate")
    hooks_run_this_tree("candidate")
    try:
        expected = ValueError if refusal == "abort_reuse" else StartRefused
        with pytest.raises(expected), claim_and_start(page_dir) as prepared:
            assert previous is not None
            assert prepared.claim["acquisition"] != previous["acquisition"]
            assert page_claim(page_dir) == previous
            assert not original.ended
            if refusal == "abort_reuse":
                raise ValueError("caller leaves before accepting reuse")
            end_session(prepared.claim["id"])
            if refusal == "new_generation":
                # The new generation's first hook marks the tree it runs again.
                hooks_run_this_tree("candidate")
                harness_3 = harness.session_harness()
                assert harness_3 is not None
                ensure_session(prepared.claim["id"], harness_3.lifetime())
        assert page_claim(page_dir) == previous
        assert not original.ended
        assert fetch(url)[0] == 200
    finally:
        cmd_stop(page_dir)


def test_service_publication_failure_keeps_previous_preview_claim(
    page_dir, monkeypatch
):
    from leaf.base.harness import session_harness
    from leaf.base.service import page_claim, prepare_claim
    from leaf.base.state import write_json
    from leaf.pages import hosting

    original = preview.PreviewService(page_dir, user=True)
    with original.starting():
        pass
    previous = page_claim(page_dir)
    hosting.cmd_stop(page_dir)
    published = json.loads(
        server_model.SERVICE.file(page_dir / "service.json").read_text()
    )
    published["enabled"] = True
    write_json(server_model.SERVICE.file(page_dir / "service.json"), published)
    harness_2 = session_harness()
    assert harness_2 is not None
    intent = prepare_claim(harness_2, page_dir)

    class Accepted:
        def announce(self, _ready, *, commit):
            commit()
            return True

    def unavailable(_directory, _record):
        raise PermissionError("service cannot be published")

    monkeypatch.setattr(hosting, "write_service", unavailable)
    try:
        with pytest.raises(PermissionError, match="service cannot be published"):
            hosting.cmd_serve(
                page_dir,
                harness=session_harness(),
                acquire=True,
                prepared_claim=intent,
                handshake=cast(Handshake, Accepted()),
            )
        assert page_claim(page_dir) == previous
        assert not original.ended
        assert not leases_model.lock_is_held(page_dir / "server.lock")
        assert (
            json.loads(server_model.SERVICE.file(page_dir / "service.json").read_text())
            == published
        )
    finally:
        monkeypatch.undo()
        hosting.cmd_stop(page_dir)
