"""Developer tooling checks; run explicitly from dev/tests."""

import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    COMPOSITE_TIMEOUT,
    STATED_TIMEOUT,
    append_carried_log_record,
    fetch,
    install_payload,
    wait_for,
    woken,
)
from journeys.test_render_export import ROOT, _reachable
from playwright.sync_api import expect
from render_harness import (
    REPLAYED_PAGE,
    example_media,
    open_page,
    panel_menu,
    restarting,
    sending,
)

from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import state as cleanup_model
from leaf.findings import Finding
from leaf.render_checks import HANDOVER_DEADLINE_MS, wait_until_ready
from leaf.structure import SourceDocument
from leaf_dev.commands import preview as preview_model


def end_preview(process) -> None:
    """Stop a preview the way a harness's runner stops a task.

    The exit status is not the evidence: a signal that lands while `watchfiles`
    waits comes back out of it as `KeyboardInterrupt`, so the same stop exits 130
    or 143 depending on where it lands. What the stop left running is.
    """
    os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=STATED_TIMEOUT)


def expect_preview_named(page, words):
    """The leaf's menu names a preview page's preview on its diagnostics row, whose
    title says who drives it and which checkout serves it; read it and put the menu
    away."""
    row = panel_menu(page).locator('.lf-fp-item[data-row="preview"]')
    expect(row).to_have_attribute("title", re.compile(re.escape(words)))
    page.locator(".lf-fp-leaf").click()


from typing import NamedTuple

PREVIEW = [sys.executable, "-m", "leaf_dev", "preview"]


@pytest.fixture(name="preview_slot")
def preview_slot_fixture(tmp_path, monkeypatch):
    """A previews root of this test's own.

    `LEAF_PREVIEWS_ROOT` puts the slots under `tmp_path` instead of the checkout's
    `.tmp/previews`, which every run in this checkout shares: a run leaves nothing
    behind there, and a preview a developer has running is not a page these tests
    find. A preview is a foreground process, so the `spawn` that started it ends it.
    """
    monkeypatch.setenv("LEAF_PREVIEWS_ROOT", str(tmp_path / "previews"))
    root = preview_model.previews_root()
    slot = f"pytest-{os.getpid()}-{tmp_path.name}"
    yield slot, root / slot


def start_preview(spawn, command: list[str], log: Path, **kwargs):
    """Run a preview the way a harness's background runner does, and read its URL.

    Its output goes to a file the test reads, and it leads a process group of its
    own, so `spawn` ends the `uv run` child doing the work along with the launcher
    it replaced.
    """
    with log.open("w", encoding="utf-8") as output:
        process = spawn(
            command,
            cwd=ROOT,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            **kwargs,
        )

    def announced(text):
        if process.poll() is not None:
            pytest.fail(f"preview exited before serving:\n{text}")
        return any(line.startswith("http://") for line in text.splitlines())

    output = wait_for(
        log.read_text,
        announced,
        failure="the preview printed no URL",
        timeout=COMPOSITE_TIMEOUT,
    )
    url = next(line for line in output.splitlines() if line.startswith("http://"))
    return process, url


class Watched(NamedTuple):
    """A running preview of a fixture of the test's own, and where to read it."""

    source: Path
    runtime: Path
    directory: Path
    process: subprocess.Popen
    url: str
    log: Path


def watching(tmp_path, preview_slot, spawn, user: bool, *, env=None):
    source = tmp_path / "watched.html"
    source.write_text(REPLAYED_PAGE, encoding="utf-8")
    runtime = install_payload(tmp_path / "watched-runtime")
    # The runtime is a developer checkout for this preview: its compiler uses
    # the development dependencies installed in the test checkout.
    (runtime / "node_modules").symlink_to(
        ROOT / "node_modules", target_is_directory=True
    )
    slot, directory = preview_slot
    log = tmp_path / "preview.log"
    process, url = start_preview(
        spawn,
        [
            *PREVIEW,
            "--source",
            str(source),
            "--runtime",
            str(runtime),
            "--slot",
            slot,
            *(["--user"] if user else []),
        ],
        log,
        **({"env": env} if env is not None else {}),
    )
    return Watched(source, runtime, directory, process, url, log)


@pytest.fixture(name="watched_preview")
def watched_preview_fixture(tmp_path, preview_slot, spawn):
    """A running ordinary preview, which takes no claim."""
    return watching(tmp_path, preview_slot, spawn, user=False)


@pytest.fixture(name="served_preview")
def served_preview_fixture(tmp_path, preview_slot, spawn):
    """A running `--user` preview, for what only the durable service records."""
    return watching(tmp_path, preview_slot, spawn, user=True)


def test_interrupting_a_live_preview_exits_without_a_traceback(preview_slot, spawn):
    """Ctrl-C retires the watcher and its server without a traceback or lost feedback."""
    slot, page = preview_slot
    preview = spawn(
        [
            *PREVIEW,
            "heat-loss",
            "--slot",
            slot,
            "--user",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.monotonic() + COMPOSITE_TIMEOUT
    while not server_model.running_server(page):
        if preview.poll() is not None:
            output, _ = preview.communicate()
            pytest.fail(f"preview exited before serving:\n{output}")
        if time.monotonic() > deadline:
            pytest.fail("preview did not start serving within 90 seconds")
        time.sleep(0.05)

    os.killpg(preview.pid, signal.SIGINT)
    output, _ = preview.communicate(timeout=STATED_TIMEOUT)

    assert preview.returncode == 130, output
    assert server_model.running_server(page) is None
    assert (page / "events.jsonl").is_file()
    assert "Traceback" not in output


@pytest.mark.parametrize(
    ("first_signal", "next_signal"),
    [(signal.SIGINT, signal.SIGTERM), (signal.SIGTERM, signal.SIGINT)],
)
def test_a_second_stop_signal_leaves_preview_cleanup_running(
    tmp_path, preview_slot, spawn, first_signal, next_signal
):
    """A forwarded or repeated stop cannot abandon the server's cleanup.

    Hold the real worker at service cleanup, then deliver another signal before
    releasing it. The ordinary launcher test covers uv's forwarding; this gate
    establishes the ordering without depending on when uv forwards a signal. Each
    signal starts cleanup once and arrives second once, since the first ignores both.
    """
    worker = tmp_path / "worker.py"
    worker.write_text(
        """import sys
from leaf_dev.commands import preview

stop = preview.PreviewService.stop

def gated_stop(self):
    print("Cleanup started", flush=True)
    assert sys.stdin.readline() == "release\\n"
    stop(self)
    print("Cleanup finished", flush=True)

preview.PreviewService.stop = gated_stop
preview.preview.main(args=sys.argv[1:])
""",
        encoding="utf-8",
    )
    slot, page = preview_slot
    log = tmp_path / "preview.log"
    process, url = start_preview(
        spawn,
        [
            sys.executable,
            str(worker),
            "--source",
            str(ROOT / "examples" / "heat-loss.html"),
            "--slot",
            slot,
            "--user",
            "--worker",
        ],
        log,
        stdin=subprocess.PIPE,
    )
    events = (page / "events.jsonl").read_bytes()
    process.send_signal(first_signal)
    try:
        wait_for(
            log.read_text,
            lambda output: "Cleanup started" in output,
            failure="the stop signal never reached service cleanup",
        )
        process.send_signal(next_signal)
    finally:
        process.stdin.write("release\n")
        process.stdin.flush()
    process.wait(timeout=STATED_TIMEOUT)

    output = log.read_text()
    assert "Cleanup finished" in output, output
    assert process.returncode in (130, 128 + first_signal), output
    assert server_model.running_server(page) is None
    assert not _reachable(url)
    assert (page / "events.jsonl").read_bytes() == events
    assert "Traceback" not in output


def test_terminating_a_preview_stops_its_claimed_service(tmp_path, preview_slot, spawn):
    """A runner's SIGTERM ends a preview through the same cleanup Ctrl-C runs.

    Python's default SIGTERM skips every `finally`, so without the preview's own
    handler a stopped `--user` preview left its durable service serving the page.
    """
    slot, page = preview_slot
    process, url = start_preview(
        spawn,
        [*PREVIEW, "heat-loss", "--slot", slot, "--user"],
        tmp_path / "preview.log",
    )
    assert server_model.running_server(page)
    end_preview(process)
    assert server_model.running_server(page) is None
    assert not _reachable(url)
    assert "Traceback" not in (tmp_path / "preview.log").read_text()


def test_terminating_a_preview_while_its_service_starts_leaves_none(
    tmp_path, preview_slot, spawn
):
    """A stop that lands before the durable service has committed leaves none.
    The serving child runs in a session of its own, so the group signal never
    reaches it, and the preview's stop can run before the child has taken the
    page; the start used to stand behind that stop, enabled. Now the preview's
    interrupted start gives its claim back and closes the handshake, so the child
    either refuses before recording a service or withdraws the one it recorded."""
    slot, page = preview_slot
    with (tmp_path / "preview.log").open("w", encoding="utf-8") as output:
        process = spawn(
            [*PREVIEW, "heat-loss", "--slot", slot, "--user"],
            cwd=ROOT,
            stdout=output,
            stderr=subprocess.STDOUT,
        )

    def serving_child():
        found = subprocess.run(
            ["pgrep", "-f", f"server _serve {page}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return [int(pid) for pid in found.stdout.split()]

    children = wait_for(
        serving_child,
        lambda pids: pids or process.poll() is not None,
        failure="the preview never spawned its service",
        timeout=COMPOSITE_TIMEOUT,
    )
    assert children, (tmp_path / "preview.log").read_text()
    os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=STATED_TIMEOUT)
    wait_for(serving_child, lambda pids: not pids, failure="the service outlived it")
    assert server_model.running_server(page) is None
    service = files_model.read_json(page / "service.json")
    assert service is None or not service["enabled"], service


def test_a_leaf_failure_exits_the_preview_without_a_wrapper_traceback(
    tmp_path, preview_slot
):
    """The child command's diagnostic is the preview command's whole error."""
    source = tmp_path / "invalid.html"
    source.write_text("<p>outside the document</p>", encoding="utf-8")
    slot, _ = preview_slot
    result = subprocess.run(
        [
            *PREVIEW,
            "--source",
            str(source),
            "--slot",
            slot,
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=COMPOSITE_TIMEOUT,
    )

    assert result.returncode == 1, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "refusing to stamp index.html:" in result.stderr
    assert "Traceback" not in result.stdout + result.stderr
    assert "exited" not in result.stdout + result.stderr


def test_named_live_previews_serve_one_source_in_independent_runtime_slots(
    browser, tmp_path, preview_slot, spawn
):
    """A developer can hold one fixture still while two vendored runtimes serve it.

    The named pages and their services are the public evidence. If the script falls
    back to its single default directory, the second run is refused; if it ignores
    the shared source, the planted heading is absent from one or both URLs.
    """
    source = tmp_path / "shared-preview.html"
    source.write_text(
        REPLAYED_PAGE.replace("Rollout", "Shared runtime comparison", 1),
        encoding="utf-8",
    )
    prefix, default = preview_slot
    installed = install_payload(tmp_path / "other-runtime")
    runtime_marker = "selected-preview-runtime"
    installed_runtime = installed / "browser" / "leaf.js"
    installed_runtime.write_text(
        installed_runtime.read_text(encoding="utf-8")
        + f"\nglobalThis.__previewRuntimeMarker = {json.dumps(runtime_marker)};\n",
        encoding="utf-8",
    )
    slots = [f"{prefix}-before", f"{prefix}-after"]
    runtimes = [ROOT, installed]
    pages = [default.parent / slot for slot in slots]
    urls = []
    for slot, runtime in zip(slots, runtimes, strict=True):
        log = tmp_path / f"{slot}.log"
        _, url = start_preview(
            spawn,
            [
                *PREVIEW,
                "--source",
                str(source),
                "--runtime",
                str(runtime),
                "--slot",
                slot,
            ],
            log,
        )
        output = log.read_text().splitlines()
        assert output[0] == "prepared shared-preview (1 version)"
        assert "initialized" not in log.read_text()
        assert "stamped" not in log.read_text()
        urls.append(url)

    assert urls[0] != urls[1]
    assert all(
        page.joinpath("index.html").read_text() == source.read_text() for page in pages
    )
    for url, runtime, expected_marker in zip(
        urls, runtimes, [None, runtime_marker], strict=True
    ):
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        page.goto(url, wait_until="load")
        wait_until_ready(page)
        assert page.evaluate("globalThis.__previewRuntimeMarker") == expected_marker
        expect_preview_named(page, f"Preview · {runtime.name}")
        expect(
            page.get_by_role("heading", name="Shared runtime comparison")
        ).to_be_visible()


def test_a_preview_records_real_gestures_outside_the_task(
    browser, tmp_path, preview_slot, spawn
):
    """A preview and a `--user` one share the event door and differ in lifetime.

    The selected runtime's temporary server is held by the watcher rather than a
    service record. Its log survives source reloads, while a distinct `--user`
    slot is claimed for task delivery. A start into that slot while it runs is
    refused; once it has stopped, an unclaimed start rebuilds the slot and releases
    the claim with the moves it carried.
    """
    slot, page_dir = preview_slot
    source = tmp_path / "driven.html"
    source.write_text(REPLAYED_PAGE, encoding="utf-8")
    runtime = install_payload(tmp_path / "driven-runtime")
    driven_command = [
        *PREVIEW,
        "--source",
        str(source),
        "--runtime",
        str(runtime),
        "--slot",
        slot,
    ]
    driven_log = tmp_path / "driven.log"
    driven_process, driven_url = start_preview(spawn, driven_command, driven_log)
    assert driven_log.read_text().splitlines()[:2] == [
        "prepared driven (1 version)",
        "",
    ]
    assert preview_model.WATCHER_NOTE in driven_log.read_text()
    assert service_model.page_claim(page_dir) is None
    assert not (page_dir / "service.json").exists()
    assert page_dir not in service_model.owned_pages(
        os.environ["CLAUDE_CODE_SESSION_ID"]
    )
    driven = open_page(browser, driven_url)
    expect_preview_named(driven, f"Preview · {runtime.name}")
    with sending(driven, "the agent-driven option pick"):
        driven.locator("#opt-shim .lf-pick").click()
    expect(driven.locator("#opt-shim")).to_have_attribute("chosen", "")
    [automated_event] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "action" and event["author"] == "user"
    ]
    feedback = (page_dir / "events.jsonl").read_bytes()
    inode = (page_dir / "events.jsonl").stat().st_ino

    with restarting(driven):
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "Rollout", "A preview follows source edits", 1
            ),
            encoding="utf-8",
        )
        expect(
            driven.get_by_role("heading", name="A preview follows source edits")
        ).to_be_visible(timeout=HANDOVER_DEADLINE_MS)
    expect(driven.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (page_dir / "events.jsonl").read_bytes().startswith(feedback)
    assert (page_dir / "events.jsonl").stat().st_ino == inode
    assert service_model.page_claim(page_dir) is None
    assert not (page_dir / "service.json").exists()
    driven.close()
    end_preview(driven_process)

    user_slot = f"{slot}-user"
    user_dir = page_dir.with_name(user_slot)
    user_command = [
        *driven_command[:-1],
        user_slot,
        "--user",
    ]
    user_process, user_url = start_preview(spawn, user_command, tmp_path / "user.log")
    claim = service_model.page_claim(user_dir)
    assert claim is not None and claim["id"] == os.environ["CLAUDE_CODE_SESSION_ID"]
    user = open_page(browser, user_url)
    expect_preview_named(user, f"User · {runtime.name}")
    with sending(user, "the user option pick"):
        user.locator("#opt-stage .lf-pick").click()
    expect(user.locator("#opt-stage")).to_have_attribute("chosen", "")
    [user_event] = [
        event
        for event in events_model.read_events(user_dir)
        if event["kind"] == "action" and event["author"] == "user"
    ]
    assert user_event["id"] != automated_event["id"]
    assert user_event in service_model.unacknowledged(
        events_model.read_events(user_dir), 0
    )
    user_feedback = (user_dir / "events.jsonl").read_bytes()
    user.close()

    unclaimed_command = [command for command in user_command if command != "--user"]
    refused = subprocess.run(
        unclaimed_command,
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=COMPOSITE_TIMEOUT,
    )
    assert refused.returncode == 1
    assert "another preview is serving" in refused.stderr
    assert (user_dir / "events.jsonl").read_bytes() == user_feedback

    end_preview(user_process)
    _, replaced_url = start_preview(spawn, unclaimed_command, tmp_path / "replaced.log")
    assert service_model.page_claim(user_dir) is None
    assert user_event not in events_model.read_events(user_dir)
    replaced_page = open_page(browser, replaced_url)
    expect_preview_named(replaced_page, f"Preview · {runtime.name}")
    expect(replaced_page.locator("#opt-stage")).not_to_have_attribute("chosen", "")


def test_an_unclaimed_preview_keeps_its_gestures_out_of_the_stop_hook(
    tmp_path, preview_slot, spawn, capsys
):
    """An agent drives its own preview, so its presses must not read as a user's.

    While claiming and running in the background were one choice, a session driving
    four previews through browser proof read its own presses back as user input:
    six Stop hooks blocked on `.tmp/previews/` slots inside subagent worktrees no
    user could see. A `--user` preview still reports its user, which is the reading
    `test_a_preview_owes_no_watcher_but_still_carries_its_user` holds. The
    difference is upstream, in whether the preview took a claim at all.
    """
    slot, page_dir = preview_slot
    source = tmp_path / "detached.html"
    source.write_text(REPLAYED_PAGE, encoding="utf-8")
    runtime = install_payload(tmp_path / "detached-runtime")
    _, url = start_preview(
        spawn,
        [
            *PREVIEW,
            "--source",
            str(source),
            "--runtime",
            str(runtime),
            "--slot",
            slot,
        ],
        tmp_path / "preview.log",
    )
    assert _reachable(url)

    session = os.environ["CLAUDE_CODE_SESSION_ID"]
    assert service_model.page_claim(page_dir) is None
    assert page_dir not in service_model.owned_pages(session)
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "probe"},
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "Stop", "session_id": session}
    )
    assert capsys.readouterr().out == ""


def test_a_user_preview_restarts_under_its_original_codex_claim(
    tmp_path, preview_slot, codex_program, codex_env, codex_queue, spawn
):
    """The claim names the Codex task above the preview, and survives each restart.

    A restart is a runtime edit's: a source edit leaves the server up."""
    source = tmp_path / "detached.html"
    source.write_text(REPLAYED_PAGE)
    runtime = install_payload(tmp_path / "detached-runtime")
    theme = runtime / "browser" / "base.css"
    slot, directory = preview_slot
    log = tmp_path / "preview.log"
    # The Codex task runs the preview as its own long-running command.
    owner = spawn(
        [
            str(codex_program),
            "-c",
            (
                "import subprocess, sys; "
                "log = open(sys.argv[1], 'w'); "
                "subprocess.run(sys.argv[2:], stdout=log, stderr=subprocess.STDOUT)"
            ),
            str(log),
            *PREVIEW,
            "--source",
            str(source),
            "--runtime",
            str(runtime),
            "--slot",
            slot,
            "--user",
        ],
        env=codex_env
        | codex_queue
        | {
            "CODEX_THREAD_ID": "preview-codex",
            "PYTHONHOME": sys.base_prefix,
            "LEAF_PREVIEWS_ROOT": str(directory.parent),
        },
    )
    wait_for(
        lambda: log.read_text() if log.exists() else "",
        lambda output: "Watching " in output,
        failure="the preview under the Codex task did not start",
        timeout=COMPOSITE_TIMEOUT,
    )
    claim = service_model.page_claim(directory)
    assert claim is not None
    assert claim["pid"] == owner.pid
    with theme.open("a", encoding="utf-8") as stream:
        stream.write("\nh1 { color: navy; }\n")
    wait_for(
        log.read_text,
        lambda output: "Updated detached" in output,
        failure="the preview did not restart for its runtime",
    )
    assert server_model.running_server(directory)
    assert service_model.page_claim(directory) == claim

    # Ownership can end while a runtime edit waits for the page transaction.
    # page init needs that transaction before it can stop the service, so do not
    # wait for its stop while holding the transaction ourselves.
    with service_model.PageTransaction(directory):
        with theme.open("a", encoding="utf-8") as stream:
            stream.write("\nh1 { color: teal; }\n")
        assert claim is not None
        cleanup_model.end_session(claim["id"])
    wait_for(
        lambda: server_model.running_server(directory),
        lambda running: not running,
        failure="the ended session left the service running",
    )
    assert not service_model.claim_is_active(service_model.page_claim(directory))
    wait_for(
        lambda: leases_model.lock_is_held(preview_model.preview_lease(directory)),
        lambda held: not held,
        failure="the ended session left its preview running",
    )


def test_restarting_a_preview_discards_its_state_and_starts_it_fresh(
    browser, tmp_path, preview_slot, spawn
):
    """A slot's page lives as long as its preview; the next start builds it anew."""
    source, _, directory, process, url, _ = watching(
        tmp_path, preview_slot, spawn, user=False
    )
    page = open_page(browser, url)
    with sending(page, "the user option pick before restart"):
        page.locator("#opt-shim .lf-pick").click()
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    page.close()

    end_preview(process)
    # A stopped preview leaves what the page collected readable until the next start.
    assert b'"kind": "action"' in (directory / "events.jsonl").read_bytes()

    _, restarted_url = start_preview(spawn, process.args, tmp_path / "restarted.log")
    assert (directory / "index.html").read_bytes() == source.read_bytes()
    assert b'"kind": "action"' not in (directory / "events.jsonl").read_bytes()
    fresh = open_page(browser, restarted_url)
    expect(fresh.locator("#opt-shim")).not_to_have_attribute("chosen", "")


def test_preview_adds_immutable_media_before_stamping_source(watched_preview):
    source, _, directory, _, _, log = watched_preview
    media = source.parent / "media"
    media.mkdir()
    image = media / "051bee487bfb5d13.png"
    expected = (example_media() / image.name).read_bytes()
    image.write_bytes(expected)
    revised = source.read_text().replace(
        "</main>", f'<img src="/media/{image.name}" alt="Preview proof"></main>'
    )
    source.write_text(revised)
    wait_for(
        lambda: (directory / "index.html").read_text(),
        lambda source: source == revised,
        failure="the source referencing new media was not stamped",
    )
    assert (directory / "media" / image.name).read_bytes() == expected

    image.write_bytes(b"changed bytes")
    wait_for(
        log.read_text,
        lambda output: "use a new filename" in output,
        failure="the changed media bytes were not refused",
    )
    assert (directory / "media" / image.name).read_bytes() == expected

    image.unlink()
    second = media / "a99a1b63048502d0.png"
    second.write_bytes((example_media() / second.name).read_bytes())
    wait_for(
        lambda: (directory / "media" / second.name).exists(),
        bool,
        failure="the new media did not reach the preview",
    )
    assert (directory / "media" / image.name).read_bytes() == expected


@pytest.mark.parametrize("edit", ["source", "runtime"])
def test_a_user_preview_update_keeps_the_sessions_wait_watching(
    tmp_path, served_preview, spawn, edit
):
    """A `--user` preview's update leaves the session's wait watching.

    The update used to disable the page's service for its whole length, and a wait
    watching the page read that as a page it had lost: with no other page to carry,
    it ended on every save. A source edit leaves the server up, and a runtime edit's
    re-vendor restarts it, which a wait watches through as it watches any stopped
    server. The comment after the update is the proof: only a wait still watching
    delivers it.
    """
    source, runtime, directory, _, _, log = served_preview
    waited = tmp_path / "wait.log"
    with waited.open("w", encoding="utf-8") as output:
        waiter = spawn(
            [*LEAF_COMMAND, "wait"],
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )
    session = os.environ["CLAUDE_CODE_SESSION_ID"]
    wait_for(
        lambda: waiter.poll() is None and leases_model.wait_is_live(directory, session),
        bool,
        failure="the wait did not start watching the preview",
    )
    if edit == "source":
        source.write_text(
            source.read_text().replace("Rollout", "A watched revision", 1)
        )
    else:
        theme = runtime / "browser" / "base.css"
        with theme.open("a", encoding="utf-8") as stream:
            stream.write("\nh1 { color: navy; }\n")
    wait_for(
        log.read_text,
        lambda output: "Updated watched" in output,
        failure="the preview did not finish its update",
    )
    assert server_model.running_server(directory)
    assert waiter.poll() is None, waited.read_text()

    append_carried_log_record(
        directory,
        {
            "kind": "comment",
            "author": "user",
            "revision": files_model.latest_revision(directory),
            "text": "still there?",
        },
    )
    assert waiter.wait(timeout=STATED_TIMEOUT) == 0, waited.read_text()
    payload, _, events = woken(waited.read_text(), session=session)
    assert f"leaf delivery ack {payload['id']} && leaf wait" in payload["acknowledge"]
    assert [event["text"] for event in events] == ["still there?"]


def test_a_user_preview_brings_back_a_service_that_is_down_but_wanted(
    served_preview,
):
    """A `--user` service still enabled with no server is the preview's to bring
    back without an edit, and does not end it: that is a server that died, or
    one a re-vendor could not start again (its recorded port taken), which is left
    enabled and down in just this way. Only a stop, or the claim leaving this
    session, ends the preview."""
    _, _, directory, process, url, log = served_preview
    original = server_model.running_server(directory)
    assert original is not None
    port = original["port"]
    claim = service_model.page_claim(directory)
    events = (directory / "events.jsonl").read_bytes()
    # Hold the watcher while taking the stopped server's port. Revival waits for
    # native availability, then recovers without a source edit.
    with socket.socket() as occupied:
        os.killpg(process.pid, signal.SIGSTOP)
        try:
            killed = subprocess.run(
                ["pkill", "-KILL", "-f", f"server _serve {directory}"], check=False
            )
            assert killed.returncode == 0
            wait_for(
                lambda: server_model.running_server(directory),
                lambda running: running is None,
                failure="the killed server still held its lease",
            )
            occupied.bind(("127.0.0.1", port))
            occupied.listen()
        finally:
            os.killpg(process.pid, signal.SIGCONT)
        wait_for(
            lambda: leases_model.lock_is_held(directory / "server.lock"),
            bool,
            failure="the preview did not prepare a replacement server",
        )
        assert server_model.running_server(directory) is None
        assert files_model.read_json(directory / "service.json")["enabled"]

    restored = wait_for(
        lambda: server_model.running_server(directory),
        bool,
        failure="the preview did not bring its server back",
    )
    assert process.poll() is None, log.read_text()
    assert restored["port"] == port
    wait_for(
        lambda: _reachable(url),
        bool,
        failure="the restored preview did not answer at its original keyed URL",
    )
    assert service_model.page_claim(directory) == claim
    assert (directory / "events.jsonl").read_bytes() == events


@pytest.mark.parametrize("unclaimed", [False, True])
def test_a_preview_relinquishes_a_service_another_session_claims(
    served_preview, monkeypatch, unclaimed
):
    """The old author's watcher ends without disabling the successor's service."""
    _, _, directory, process, url, log = served_preview
    if unclaimed:
        # A plain-terminal --user preview has no harness session. Exercise its same
        # cleanup boundary directly; the subprocess owns the serving resource.
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
        cleanup = preview_model.PreviewService(directory, user=True)
    with service_model.PageTransaction(directory) as transaction:
        transaction.take_claim(harness_model.ClaudeCodeHarness("successor", "Claude"))
    if unclaimed:
        assert cleanup.ended
        cleanup.stop()
    wait_for(
        lambda: process.poll(),
        lambda status: status is not None,
        failure="the former owner's preview kept following the successor's page",
    )
    assert process.returncode == 0, log.read_text()
    claim_record = service_model.page_claim(directory)
    assert claim_record is not None
    assert claim_record["id"] == "successor"
    assert server_model.running_server(directory)
    assert _reachable(url)


def test_the_example_preview_command_exports_a_file_that_opens_on_its_own(
    browser,
):
    """The handoff command names one file whose page draws with no live server."""
    result = subprocess.run(
        [
            *PREVIEW,
            "pr-walkthrough",
            "--export",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=COMPOSITE_TIMEOUT,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    out = Path(result.stdout.splitlines()[-1])
    assert out.is_absolute()
    assert out.name == "example-pr-walkthrough.html"

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.on(
        "requestfailed",
        lambda request: page.lf_errors.append(
            Finding(
                "request-failed",
                values={
                    "kind": request.resource_type,
                    "error": request.failure,
                    "frame": request.frame.url,
                    "url": request.url,
                },
            )
        ),
    )
    page.goto(out.as_uri(), wait_until="load")
    source = (ROOT / "examples" / "pr-walkthrough.html").read_text(encoding="utf-8")
    select_one_result = SourceDocument(source).tree.select_one("h1")
    assert select_one_result is not None
    title = " ".join(select_one_result.text.split())
    expect(page.get_by_role("heading", name=title)).to_be_visible()
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    assert page.evaluate("document.compatMode") == "CSS1Compat"
    assert page.locator('link[rel="stylesheet"]').count() == 0
    assert page.locator("style").count() > 0


def test_exporting_an_example_leaves_the_live_preview_untouched(
    monkeypatch, page_dir, persistent_server
):
    """An offline handoff can be made while its live preview keeps serving."""
    live_source = (page_dir / "index.html").read_bytes()
    live_server = persistent_server(page_dir)
    monkeypatch.setattr(preview_model, "TMP", page_dir.parent)

    try:
        result = CliRunner().invoke(
            preview_model.preview, ["pr-walkthrough", "--export"]
        )
        assert result.exit_code == 0, result.output
        assert live_server.poll() is None
        assert (page_dir / "index.html").read_bytes() == live_source
    finally:
        CliRunner().invoke(cli_model.cli, ["server", "stop", str(page_dir)])
        live_server.wait(timeout=STATED_TIMEOUT)


def test_preview_resumes_loaded_code_changes_without_losing_feedback(
    tmp_path, preview_slot, spawn
):
    """Python edits keep the old page serving until an explicit restart."""
    from urllib.parse import urlsplit

    source, runtime, directory, process, url, log = watching(
        tmp_path, preview_slot, spawn, user=True
    )
    state_url = urlsplit(url)._replace(path="/api/state").geturl()
    event_url = urlsplit(url)._replace(path="/api/event").geturl()
    status, body = fetch(
        event_url,
        token=None,
        data=json.dumps(
            {
                "kind": "comment",
                "revision": files_model.latest_revision(directory),
                "text": "Keep this feedback through the update",
                "attempt": "preview-runtime-update",
            }
        ).encode(),
    )
    assert status == 200, body
    feedback = (directory / "events.jsonl").read_bytes()
    assert b"Keep this feedback through the update" in feedback
    status, body = fetch(state_url, token=None)
    assert status == 200, body
    old_grace = json.loads(body)["working_grace_ms"]

    edited = runtime / "src/leaf/served_state/page.py"
    original = edited.read_text()
    updated = original.replace("WORKING_GRACE // timedelta(milliseconds=1)", "12345")
    assert updated != original
    edited.write_text(updated)

    def restart_requested(text):
        assert process.poll() is None, text
        return "restart this preview" in text

    wait_for(
        log.read_text,
        restart_requested,
        timeout=STATED_TIMEOUT,
        failure="the preview did not request a restart for its changed Python code",
    )
    assert _reachable(url)
    status, body = fetch(state_url, token=None)
    assert status == 200, body
    assert json.loads(body)["working_grace_ms"] == old_grace

    # The same command resumes a user preview; no process identity is a contract.
    result = CliRunner().invoke(cli_model.cli, ["server", "stop", str(directory)])
    assert result.exit_code == 0, result.output
    process.wait(timeout=STATED_TIMEOUT)
    restarted, restarted_url = start_preview(
        spawn, process.args, tmp_path / "restarted.log"
    )
    assert restarted_url == url
    status, body = fetch(state_url, token=None)
    assert status == 200, body
    assert json.loads(body)["working_grace_ms"] == 12345
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)

    source.write_text(source.read_text().replace("Rollout", "Updated rollout"))
    wait_for(
        lambda: (directory / "index.html").read_text(),
        lambda text: "Updated rollout" in text,
        timeout=COMPOSITE_TIMEOUT,
        failure="the restarted preview did not resume authored-page updates",
    )
    assert restarted.poll() is None
