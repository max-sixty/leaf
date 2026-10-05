"""Preview and offline export tests."""

import base64
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from typing import NamedTuple

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    COMPOSITE_TIMEOUT,
    STATED_TIMEOUT,
    append_carried_log_record,
    consume_pending_input,
    install_payload,
    wait_for,
)
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import media as media_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import state as cleanup_model
from leaf.render_checks import wait_until_ready
from leaf.schema import ELEMENT_ID
from leaf.structure import UTF8_BOM
from leaf_dev import preview as preview_model
from leaf_dev.example_data import patch_manifest
from playwright.sync_api import expect
from render_cases_interaction import ASK_PAGE, live_url
from render_cases_navigation import (
    source_revision,
)
from render_harness import (
    REPLAYED_PAGE,
    example_media,
    leaf_page,
    open_page,
    restarting,
    round_trip,
    sending,
    write,
)

pytestmark = pytest.mark.nightly

ROOT = Path(__file__).parent.parent
# `leaf-dev preview`, run by the interpreter this suite runs on.
PREVIEW = [sys.executable, "-m", "leaf_dev", "preview"]


@pytest.fixture
def preview_slot(tmp_path, monkeypatch):
    """A previews root of this test's own.

    `LEAF_PREVIEWS_ROOT` puts the slots under `tmp_path` instead of the checkout's
    `.tmp/previews`, which every run in this checkout shares: a run leaves nothing
    behind there, and a preview a developer has standing is not a page these tests
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
            start_new_session=True,
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


def end_preview(process) -> None:
    """Stop a preview the way a harness's runner stops a task.

    The exit status is not the evidence: a signal that lands while `watchfiles`
    waits comes back out of it as `KeyboardInterrupt`, so the same stop exits 130
    or 143 depending on where it lands. What the stop left running is.
    """
    os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=STATED_TIMEOUT)


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
        start_new_session=True,
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


@pytest.mark.parametrize("first_signal", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("next_signal", [signal.SIGINT, signal.SIGTERM])
def test_a_second_stop_signal_leaves_preview_cleanup_running(
    tmp_path, preview_slot, spawn, first_signal, next_signal
):
    """A forwarded or repeated stop cannot abandon the server's cleanup.

    Hold the real worker at service cleanup, then deliver another signal before
    releasing it. The ordinary launcher test covers uv's forwarding; this gate
    establishes the ordering without depending on when uv forwards a signal.
    """
    worker = tmp_path / "worker.py"
    worker.write_text(
        """import sys
from leaf_dev import preview

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
            start_new_session=True,
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


def test_a_watch_subscription_collects_before_its_first_read(tmp_path):
    """An edit made while nobody is reading the subscription is still in it.

    watchfiles starts its rust watcher on the subscription's first read, and the
    read a preview's loop makes comes after the preview has announced its URL —
    so the edit a developer makes the moment that URL appears used to land in a
    window nothing was watching. The interval here is that announcement: long
    enough that the write is over and reported by the platform before anything
    reads, which is what an unstarted subscription cannot survive.
    """
    edited = tmp_path / "source.html"
    edited.write_text("<p>authored</p>", encoding="utf-8")
    changes = preview_model.watch_changes(
        preview_model.Watched((tmp_path,), frozenset(), frozenset())
    )
    try:
        edited.write_text("<p>edited</p>", encoding="utf-8")
        time.sleep(1)
        reported = set()
        deadline = time.monotonic() + STATED_TIMEOUT
        while str(edited) not in reported:
            assert time.monotonic() < deadline, (
                f"the edit was never reported: {reported}"
            )
            reported |= {path for _, path in next(changes)}
    finally:
        changes.close()


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
    runtime_marker = "/* preview runtime marker */"
    installed_runtime = installed / "skills" / "leaf" / "assets" / "leaf.js"
    installed_runtime.write_text(
        installed_runtime.read_text(encoding="utf-8") + f"\n{runtime_marker}\n",
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
    assert runtime_marker not in pages[0].joinpath("leaf.js").read_text()
    assert runtime_marker in pages[1].joinpath("leaf.js").read_text()

    for url, runtime in zip(urls, runtimes, strict=True):
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        page.goto(url, wait_until="load")
        expect(page.locator(".lf-preview")).to_contain_text(f"Preview · {runtime.name}")
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
    expect(driven.locator(".lf-preview")).to_contain_text(f"Preview · {runtime.name}")
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
        ).to_be_visible(timeout=30000)
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
    expect(user.locator(".lf-preview")).to_contain_text(f"User · {runtime.name}")
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
    expect(replaced_page.locator(".lf-preview")).to_contain_text(
        f"Preview · {runtime.name}"
    )
    expect(replaced_page.locator("#opt-stage")).not_to_have_attribute("chosen", "")


def _reachable(url: str) -> bool:
    """Whether a preview's published address still answers."""
    try:
        with urllib.request.urlopen(url, timeout=STATED_TIMEOUT) as answer:
            return answer.status == 200
    except (urllib.error.URLError, OSError):
        return False


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
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": session})
    assert capsys.readouterr().out == ""


class Watched(NamedTuple):
    """A running preview of a fixture of the test's own, and where to read it."""

    source: Path
    runtime: Path
    directory: Path
    process: subprocess.Popen
    url: str
    log: Path


def watching(tmp_path, preview_slot, spawn, user: bool):
    source = tmp_path / "watched.html"
    source.write_text(REPLAYED_PAGE, encoding="utf-8")
    runtime = install_payload(tmp_path / "watched-runtime")
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
    )
    return Watched(source, runtime, directory, process, url, log)


@pytest.fixture
def watched_preview(tmp_path, preview_slot, spawn):
    """A running ordinary preview, which takes no claim."""
    return watching(tmp_path, preview_slot, spawn, user=False)


@pytest.fixture
def served_preview(tmp_path, preview_slot, spawn):
    """A running `--user` preview, for what only the durable service records."""
    return watching(tmp_path, preview_slot, spawn, user=True)


def test_a_user_preview_restarts_under_its_original_codex_claim(
    tmp_path, preview_slot, codex_program, codex_env, codex_queue, spawn
):
    """The claim names the Codex task above the preview, and survives each restart.

    A restart is a runtime edit's: a source edit leaves the server up."""
    source = tmp_path / "detached.html"
    source.write_text(REPLAYED_PAGE)
    runtime = install_payload(tmp_path / "detached-runtime")
    theme = runtime / "skills" / "leaf" / "assets" / "theme.css"
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
        start_new_session=True,
    )
    wait_for(
        lambda: log.read_text() if log.exists() else "",
        lambda output: "Watching " in output,
        failure="the preview under the Codex task did not start",
        timeout=COMPOSITE_TIMEOUT,
    )
    claim = service_model.page_claim(directory)
    assert claim["pid"] == owner.pid
    with theme.open("a", encoding="utf-8") as stream:
        stream.write("\nh1 { color: navy; }\n")
    wait_for(
        log.read_text,
        lambda output: "Reloaded detached" in output,
        failure="the preview did not restart for its runtime",
    )
    assert server_model.running_server(directory)
    assert service_model.page_claim(directory) == claim

    # SessionEnd can win while the re-vendor waits for the page transaction.
    with service_model.PageTransaction(directory) as transaction:
        with theme.open("a", encoding="utf-8") as stream:
            stream.write("\nh1 { color: teal; }\n")
        wait_for(
            lambda: server_model.running_server(directory),
            lambda running: not running,
            failure="the refresh did not stop the service",
        )
        transaction.release_claim()
    wait_for(
        log.read_text,
        lambda output: "no longer owns" in output,
        failure="the preview did not report its lost claim",
    )
    assert server_model.running_server(directory) is None
    assert service_model.page_claim(directory)["released"] is not None
    wait_for(
        lambda: leases_model.lock_is_held(preview_model.preview_lease(directory)),
        lambda held: not held,
        failure="the released session left its preview running",
    )


def test_preview_watches_runtime_and_source_without_losing_user_state(
    browser, watched_preview
):
    """The open tab follows edits; rejected source never replaces its last good page."""
    source, runtime, directory, _, url, log = watched_preview
    original = source.read_text(encoding="utf-8")
    page = open_page(browser, url)
    with sending(page, "the watched user option pick"):
        page.locator("#opt-shim .lf-pick").click()
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    feedback = (directory / "events.jsonl").read_bytes()
    assert b'"kind": "action"' in feedback
    inode = (directory / "events.jsonl").stat().st_ino
    registry = json.loads((directory / "registry.json").read_text())
    generation = registry["$layer"]["generation"]

    theme = runtime / "skills" / "leaf" / "assets" / "theme.css"
    with restarting(page):
        with theme.open("a", encoding="utf-8") as stream:
            stream.write("\nh1 { color: rgb(17, 83, 129); }\n")
        expect(page.locator("h1")).to_have_css(
            "color", "rgb(17, 83, 129)", timeout=30000
        )
    assert (
        json.loads((directory / "registry.json").read_text())["$layer"]["generation"]
        != generation
    )
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)
    assert (directory / "events.jsonl").stat().st_ino == inode

    # A source edit leaves the server up, so it is not a restart span: the tab takes
    # the new revision in place, and anything it complains about is a fault.
    revised = original.replace("Rollout", "A watched source revision", 1)
    source.write_text(revised, encoding="utf-8")
    expect(page.get_by_role("heading", name="A watched source revision")).to_be_visible(
        timeout=30000
    )
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)

    source.write_text("<p>invalid source</p>", encoding="utf-8")
    wait_for(
        log.read_text,
        lambda output: "Preview update refused" in output,
        failure="the invalid preview update was not refused",
    )
    expect(
        page.get_by_role("heading", name="A watched source revision")
    ).to_be_visible()
    assert (directory / "index.html").read_text() == revised
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)

    source.write_text(
        revised.replace("A watched source revision", "Recovered watched source"),
        encoding="utf-8",
    )
    expect(page.get_by_role("heading", name="Recovered watched source")).to_be_visible(
        timeout=30000
    )
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)
    assert (directory / "events.jsonl").stat().st_ino == inode


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


def requested_documents(page):
    """Record each document the page's main frame requests, in order.

    A reload is a document request. `framenavigated` would also count the address the
    bootstrap rewrites in place with `history.replaceState`, which loads nothing.
    """
    documents = []
    page.on(
        "request",
        lambda request: (
            documents.append(request.url)
            if request.is_navigation_request() and request.frame == page.main_frame
            else None
        ),
    )
    return documents


@pytest.mark.parametrize(
    "resource",
    [
        "leaf.js",
        "runtime/context.js",
        "widgets/lf-options.js",
        "registry.json",
        "theme.css",
        "syntax",
    ],
)
def test_a_failed_preview_bootstrap_hears_the_replacement_server(
    browser, watched_preview, resource
):
    """Supervision precedes entry, dependency, registry and stylesheet loading."""
    _, runtime, directory, _, url, _ = watched_preview
    if resource == "widgets/lf-options.js":
        standing = open_page(browser, url)
        with sending(standing, "the standing user option pick"):
            standing.locator("#opt-shim .lf-pick").click()
        standing.close()
    page = browser.new_page()
    failures = []
    documents = requested_documents(page)

    def interrupt_resource(route):
        if failures:
            route.continue_()
            return
        failures.append(True)
        if resource == "syntax":
            route.fulfill(content_type="text/javascript", body="const = broken;")
        else:
            route.abort()

    page.route(
        "**/" + ("leaf.js" if resource == "syntax" else resource), interrupt_resource
    )
    # The interruption and the replacement server between them are a restart, and
    # what the browser says inside one is the fetch that was in flight rather than
    # the condition: a refused resource, a connection to a server that has gone, a
    # decoding that stopped halfway. The span is bracketed rather than the wordings
    # listed (tests/AGENTS.md, "A test cannot assert over noise it makes itself").
    with restarting(page):
        page.goto(url, wait_until="load")
        status = page.get_by_text(
            "Leaf couldn't start. Waiting for the server to update."
        )
        expect(status).to_be_visible()
        # Hearing the same server does not loop on a persistent syntax/startup fault.
        with page.expect_response("**/registry.json") as response:
            pass
        assert response.value.ok
        assert len(documents) == 1
        expect(status).to_be_visible()
        generation = json.loads((directory / "registry.json").read_text())["$layer"][
            "generation"
        ]
        # A refused re-vendor still replaces the server; the old layer is now loadable.
        (
            runtime / "skills" / "leaf" / "packages" / "default" / "registry.json"
        ).write_text("{", encoding="utf-8")
        expect(page.locator("body")).to_have_attribute(
            "data-lf-presented", "1", timeout=30000
        )
        expect(status).not_to_be_visible()
    if resource == "widgets/lf-options.js":
        expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert len(documents) == 2
    assert (
        json.loads((directory / "registry.json").read_text())["$layer"]["generation"]
        == generation
    )


def test_a_failed_bootstrap_hears_a_static_registry_generation(
    browser, watched_preview
):
    """A static host can supervise startup without synthesizing Leaf headers."""
    _, _, directory, _, url, _ = watched_preview
    registry = json.loads((directory / "registry.json").read_text())
    generation = registry["$layer"]["generation"]
    page = browser.new_page()
    failures = []
    probes = []
    documents = requested_documents(page)

    def interrupt_entry(route):
        if failures:
            route.continue_()
            return
        failures.append(True)
        route.abort()

    def static_registry(route):
        if len(documents) > 1:
            route.continue_()
            return
        probes.append(True)
        body = json.loads(json.dumps(registry))
        if len(probes) > 1:
            body["$layer"]["generation"] = f"{generation}-replacement"
        route.fulfill(content_type="application/json", body=json.dumps(body))

    page.route("**/leaf.js", interrupt_entry)
    page.route("**/registry.json", static_registry)
    # As above: the refused entry and the server that replaces it are one restart,
    # and its noise belongs to the span rather than to a list of wordings.
    with restarting(page):
        page.goto(url, wait_until="load")
        status = page.get_by_text(
            "Leaf couldn't start. Waiting for the server to update."
        )
        expect(status).to_be_visible()
        expect(page.locator("body")).to_have_attribute(
            "data-lf-presented", "1", timeout=10000
        )
    assert len(probes) >= 2
    assert len(documents) == 2
    expect(status).not_to_be_visible()


@pytest.mark.parametrize("interrupted", ["registry.json", "widgets/lf-options.js"])
def test_a_service_that_goes_away_mid_start_says_only_that_and_comes_back(
    browser, served_preview, interrupted
):
    """A start the restart interrupts reports the vanished server and comes back.

    The other tests here reach this condition only when the machine is loaded enough to
    lose the race, so the ordering is arranged here rather than waited for. Both of the
    start's own fetches, because the words are the fetch's rather than the condition's:
    the registry is a plain `fetch` and a widget is a dynamic import, and only the second
    names the module. Whichever one the loaded machine loses is which wording arrives.

    The restart is the preview's own, set off by a runtime edit. Holding the page
    transaction pauses it after it has stopped the service, so the service stays gone
    until the page has said so, and then comes back at the address the tab already
    has.
    """
    _, runtime, directory, _, url, _ = served_preview
    page = browser.new_page()
    errors = page.lf_errors
    paused = ExitStack()
    stopped = []

    def stop_the_service(route):
        # Both of these are the runtime's own, so a service stopped before one is answered
        # is a service that goes away between the document arriving and the start that
        # document began — the transport has nothing left to name it by. Once only: the
        # reload the recovery makes must find a server that answers.
        if not stopped:
            stopped.append(True)
            paused.enter_context(cleanup_model.flocked(directory / "events.jsonl"))
            theme = runtime / "skills" / "leaf" / "assets" / "theme.css"
            with theme.open("a", encoding="utf-8") as stream:
                stream.write("\nh1 { color: navy; }\n")
            # The record says the service is stopping before its socket closes, so
            # the address is what says the start's fetch will find nothing.
            wait_for(
                lambda: _reachable(url),
                lambda reachable: not reachable,
                failure="the runtime edit did not stop the service",
            )
        route.continue_()

    page.route(f"**/{interrupted}", stop_the_service)
    with paused, restarting(page):
        page.goto(url, wait_until="load")
        # `load` is not the boundary: a widget is imported after it, so the stop is
        # waited for through the answer the page gives it rather than read straight
        # after the goto.
        expect(
            page.get_by_text("Leaf couldn't start. Waiting for the server to update.")
        ).to_be_visible()
        # The reach: an interrupted start is a fetch the runtime made itself, which no
        # transport error names, and the words are the interrupted fetch's own, so
        # neither leg can go green on the other's.
        vanished = (
            "Failed to fetch dynamically imported module"
            if interrupted == "widgets/lf-options.js"
            else "leaf: page failed to start: Failed to fetch"
        )
        assert [error for error in errors if vanished in error], errors
        paused.close()
        # The page's own recovery is bounded; the re-vendor ahead of it is not.
        wait_for(
            lambda: server_model.running_server(directory),
            bool,
            failure="the preview did not bring its service back",
            timeout=COMPOSITE_TIMEOUT,
        )


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


def test_terminating_a_preview_mid_update_leaves_no_service(served_preview):
    """A SIGTERM during an update's stopped-service interval suppresses its restart."""
    source, runtime, directory, process, _, _ = served_preview
    # Real page-transaction contention pauses init after the watcher stops the service.
    with cleanup_model.flocked(directory / "events.jsonl"):
        theme = runtime / "skills" / "leaf" / "assets" / "theme.css"
        with theme.open("a", encoding="utf-8") as stream:
            stream.write("\nh1 { color: navy; }\n")
        wait_for(
            lambda: json.loads((directory / "service.json").read_text())["enabled"],
            lambda enabled: not enabled,
            failure="watcher did not begin the update",
        )
        os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=STATED_TIMEOUT)
    assert server_model.running_server(directory) is None
    assert (directory / "events.jsonl").is_file()
    assert (directory / "index.html").read_bytes() == source.read_bytes()


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
            start_new_session=True,
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
        theme = runtime / "skills" / "leaf" / "assets" / "theme.css"
        with theme.open("a", encoding="utf-8") as stream:
            stream.write("\nh1 { color: navy; }\n")
    wait_for(
        log.read_text,
        lambda output: "Reloaded watched" in output,
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
    assert "has new input" in waited.read_text()
    [batch] = consume_pending_input(session)["batches"]
    assert [event["text"] for event in batch["events"]] == ["still there?"]


def test_a_user_preview_brings_back_a_service_that_is_down_but_wanted(
    served_preview,
):
    """A `--user` service still enabled with no server is the preview's to bring
    back without an edit, and does not end it: that is a server that died, or
    one a re-vendor could not start again (its recorded port taken), which is left
    enabled and down in just this way. Only a stop, or the claim leaving this
    session, ends the preview."""
    _, _, directory, process, url, log = served_preview
    port = server_model.running_server(directory)["port"]
    claim = service_model.page_claim(directory)
    events = (directory / "events.jsonl").read_bytes()
    # Hold the watcher while taking the stopped server's port. The first revival
    # must refuse, then recover after that condition clears without a source edit.
    with socket.socket() as occupied:
        occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
            log.read_text,
            lambda output: "can't serve" in output,
            failure="the occupied preview address was not reported",
        )
        assert files_model.read_json(directory / "service.json")["enabled"]

    wait_for(
        lambda: server_model.running_server(directory),
        bool,
        failure="the preview did not bring its server back",
    )
    assert process.poll() is None, log.read_text()
    assert server_model.running_server(directory)["port"] == port
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
    assert service_model.page_claim(directory)["id"] == "successor"
    assert server_model.running_server(directory)
    assert _reachable(url)


# ---------- export: the page as one file ----------

OFFLINE_WIDGET = """\
import { LitElement, html, widgetController } from "/runtime/widget-api.js";

customElements.define("lf-offline-test", class extends LitElement {
  controller = widgetController(this);
  reading = this.controller.read();
  local = 0;
  stop = null;

  createRenderRoot() {
    return this.shadowRoot ?? this.attachShadow({mode: "open"});
  }

  connectedCallback() {
    super.connectedCallback();
    this.stop ??= this.controller.subscribe(reading => {
      this.reading = reading;
      this.requestUpdate();
    });
  }

  disconnectedCallback() {
    this.stop?.();
    this.stop = null;
    super.disconnectedCallback();
  }

  choose() {
    return this.controller.dispatch({
      kind: "action", verb: "choose", detail: {choice: "chosen"},
    });
  }

  render() {
    const choice = this.reading.state.choose?.value ?? this.getAttribute("choice");
    const action = this.reading.actions.choose;
    const unavailable = action.unavailable;
    return html`
      <style>#local { color: rgb(12, 34, 56); }</style>
      <button id="local" @click=${() => { this.local += 1; this.requestUpdate(); }}>
        Increment locally
      </button>
      <output id="local-value">${this.local}</output>
      <button id="choose" ?disabled=${!action.available} @click=${this.choose}>
        Choose on host
      </button>
      <output id="choice">${choice}</output>
      ${unavailable ? html`<p id="unavailable">${unavailable}</p>` : null}
    `;
  }
});
"""

OFFLINE_REGISTRY = {
    "lf-offline-test": {
        "description": "A page-owned offline export test widget.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": f"^{ELEMENT_ID}$"},
            "choice": {"type": "string"},
            "restated": {"type": "boolean"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-state": {
            "choose": {
                "detail": {
                    "type": "object",
                    "properties": {"choice": {"type": "string"}},
                    "required": ["choice"],
                    "additionalProperties": False,
                },
                "unit": "widget",
                "record": {"kind": "value", "attr": "choice", "value": "choice"},
            }
        },
        "x-example": (
            '<lf-offline-test id="offline-example" choice="idle"></lf-offline-test>'
        ),
    },
}


def test_authored_video_and_audio_play_seek_and_export_offline(
    browser, serve, tmp_path
):
    """Actual MP4 and MP3 decoders cross capture, HTTP ranges, CSP and offline URLs."""
    content = leaf_page(
        "Recorded media",
        """
        <h1>Recorded media</h1>
        <video id="video" controls playsinline width="320" height="180"
          aria-label="Test pattern" poster="/media/d7cf2b4e22c063dd.png"
          src="/media/2930ad3df7819c50.mp4"></video>
        <audio id="audio" controls aria-label="Test tone">
          <source src="/media/b5eb956d4548b3b0.mp3" type="audio/mpeg">
        </audio>
    """,
    )
    content = content.replace(
        "</main>",
        '<video id="repeated" controls preload="none" aria-label="Repeated recording" src="/media/2930ad3df7819c50.mp4?ignored=1#t=2"></video><video id="from-api" controls preload="none" aria-label="API recording"></video></main>',
    ).replace("</head>", '<script type="module" src="/page/media.js"></script></head>')
    url = serve(
        content,
        page_files={
            "media.js": "import { scopedMediaUrl } from '/runtime/widget-api.js'; document.querySelector('#from-api').src = scopedMediaUrl('/media/2930ad3df7819c50.mp4?ignored=1');"
        },
    )
    page = open_page(browser, url)
    media_responses = []
    page.on(
        "response",
        lambda response: (
            media_responses.append(response)
            if response.url.endswith((".mp4", ".mp3"))
            else None
        ),
    )
    exported = tmp_path / "recordings.html"
    exporting_model.cmd_export(serve.page_dir, exported, None)
    exported_source = exported.read_text()
    for filename in ("2930ad3df7819c50.mp4", "b5eb956d4548b3b0.mp3"):
        encoded = base64.b64encode(
            (serve.page_dir / "media" / filename).read_bytes()
        ).decode()
        assert exported_source.count(encoded) == 1
    for location in (url, exported.as_uri()):
        page.goto(location, wait_until="load")
        wait_until_ready(page)
        for selector in ("#video", "#audio"):
            player = page.locator(selector)
            page.wait_for_function(
                "selector => document.querySelector(selector).readyState >= 2",
                arg=selector,
            )
            assert player.evaluate("el => el.duration") == pytest.approx(8, abs=0.2)
            # Reach the browser's player controls through ordinary sequential focus.
            for _ in range(20):
                page.keyboard.press("Tab")
                if player.evaluate("el => document.activeElement === el"):
                    break
            assert player.evaluate("el => document.activeElement === el")
            page.keyboard.press("Space")
            page.wait_for_function(
                "selector => document.querySelector(selector).currentTime > 0",
                arg=selector,
            )
            page.keyboard.press("Space")
            assert player.evaluate("el => el.paused")
            player.evaluate("el => { el.pause(); el.currentTime = 6; }")
            page.wait_for_function(
                "selector => { const el = document.querySelector(selector); return !el.seeking && Math.abs(el.currentTime - 6) < 0.1; }",
                arg=selector,
            )
            assert player.evaluate("el => el.error") is None
        touch = browser.new_page(has_touch=True, viewport={"width": 390, "height": 844})
        touch.goto(location, wait_until="load")
        wait_until_ready(touch)
        for selector in ("#video", "#audio"):
            player = touch.locator(selector)
            bounds = player.bounding_box()
            player.tap(
                position={
                    "x": 24,
                    "y": bounds["height"] - 48 if selector == "#video" else 27,
                }
            )
            touch.wait_for_function(
                "selector => !document.querySelector(selector).paused", arg=selector
            )
            player.tap(
                position={
                    "x": 24,
                    "y": bounds["height"] - 48 if selector == "#video" else 27,
                }
            )
            assert player.evaluate("el => el.paused")
        touch.close()
    assert media_responses
    assert all(response.status == 206 for response in media_responses)
    assert all(
        response.headers["accept-ranges"] == "bytes" for response in media_responses
    )
    video_url = page.locator("#video").get_attribute("src")
    assert video_url.startswith("blob:")
    assert page.locator("#repeated").get_attribute("src") == video_url + "#t=2"
    assert page.locator("#from-api").get_attribute("src") == video_url
    assert page.locator("#audio source").get_attribute("src").startswith("blob:")


def test_interactive_export_with_an_ask_reaches_application_presentation(
    browser, serve, tmp_path
):
    """Offline mode omits thread chrome without leaving its ticket pending."""
    serve(ROOT / "examples" / "notification-playground.html")
    interactive = tmp_path / "interactive-with-ask.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive),
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output

    page = browser.new_page()
    page.goto(interactive.as_uri(), wait_until="load")
    expect(page.locator('meta[name="viewport"]')).to_have_attribute(
        "content", "width=device-width, initial-scale=1, viewport-fit=cover"
    )
    expect(page.locator("body")).to_have_attribute(
        "data-lf-presented", "1", timeout=10000
    )
    expect(page.locator(".lf-chrome")).to_have_count(0)


def test_an_interactive_export_paints_a_widget_owned_text_box(browser, serve, tmp_path):
    """A text box paints in the standing paint, which an export mounts without chrome.

    A choosable group builds its addition field offline too. Its placeholder, disabled
    Add and empty-field flag are that paint's; focus alone repaints the placeholder with
    its send key, and typing repaints the flag."""
    serve(ASK_PAGE)
    interactive = tmp_path / "interactive-addition.html"
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "export", str(serve.page_dir), "--out", str(interactive)],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output

    page = browser.new_page()
    page.goto(interactive.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute(
        "data-lf-presented", "1", timeout=10000
    )
    form = page.locator("#jobs > .lf-another")
    field = form.locator("leaf-text")
    add = form.locator(".lf-compose-submit")
    expect(field).to_have_attribute("placeholder", "Add another option")
    expect(add).to_have_attribute("aria-disabled", "true")
    expect(add).to_have_attribute("data-lf-empty", "")
    expect(add).to_be_hidden()
    field.click()
    expect(field).to_have_attribute("placeholder", "Add another option ⏎")
    write(field, "Portrait sketch")
    expect(add).not_to_have_attribute("data-lf-empty", "")


def test_interactive_export_runs_captured_local_behavior_without_a_host(
    browser, serve, tmp_path
):
    """One file boots the captured runtime, but never resurrects its host boundary."""
    source = leaf_page(
        "offline interactive",
        """
<h1>Offline interactive</h1>
<lf-offline-test id="offline-widget" choice="idle"></lf-offline-test>
<a id="jump" href="#destination">Jump locally</a>
<h2 id="destination">Destination</h2>
""",
    )
    url = serve(
        source,
        page_files={
            "registry.json": json.dumps(OFFLINE_REGISTRY),
            "widgets/lf-offline-test.js": OFFLINE_WIDGET,
        },
    )
    live = open_page(browser, url)
    with sending(live, "the accepted page-owned choice"):
        live.locator("#offline-widget").get_by_role(
            "button", name="Choose on host"
        ).click()
    round_trip(live)
    expect(live.locator("#offline-widget #choice")).to_have_text("chosen")
    live.close()

    # Export resolves the stamped artifact, never the mutable aliases left in the page
    # directory after activation.
    (serve.page_dir / "widgets" / "lf-offline-test.js").write_text(
        'throw new Error("mutable widget source escaped its revision");',
        encoding="utf-8",
    )

    interactive = tmp_path / "interactive.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive),
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["file"] == str(interactive)

    page = browser.new_page(viewport={"width": 1000, "height": 800})
    external = []
    document_url = interactive.as_uri()
    page.on(
        "request",
        lambda request: (
            external.append(request.url)
            if request.url != document_url and not request.url.startswith("data:")
            else None
        ),
    )
    page.goto(document_url, wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator("#offline-widget #choice")).to_have_text("chosen")
    expect(page.locator(".lf-chrome")).to_have_count(0)
    assert (
        page.locator("#offline-widget #local").evaluate(
            "control => getComputedStyle(control).color"
        )
        == "rgb(12, 34, 56)"
    )

    page.locator("#offline-widget").get_by_role(
        "button", name="Increment locally"
    ).click()
    expect(page.locator("#offline-widget #local-value")).to_have_text("1")
    page.locator("#jump").click()
    assert page.url.endswith("#destination")

    expect(page.locator("#offline-widget #choose")).to_be_disabled()
    expect(page.locator("#offline-widget #unavailable")).to_have_text(
        "no agent or server is available"
    )
    refused = page.locator("#offline-widget").evaluate(
        """owner => [
          owner.choose(),
          owner.controller.dispatch({kind: 'undo', target: 'missing'}),
        ]"""
    )
    assert refused == [None, None]
    expect(page.locator("#offline-widget #choice")).to_have_text("chosen")
    assert external == []


def test_interactive_export_hydrates_captured_deferred_values_offline(
    browser, serve, tmp_path
):
    """A frozen interactive copy keeps unopened deferred payloads usable."""
    serve(
        leaf_page(
            "offline deferred data",
            '<h1>Review</h1><lf-diff id="patch" source="review-patch" collapsed>'
            "<pre></pre></lf-diff>",
        )
    )
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch_manifest(patch))
    interactive = tmp_path / "deferred-interactive.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive),
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output

    page = browser.new_page()
    external = []
    document_url = interactive.as_uri()
    page.on(
        "request",
        lambda request: (
            external.append(request.url)
            if request.url != document_url and not request.url.startswith("data:")
            else None
        ),
    )
    page.goto(document_url, wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    page.locator("lf-diff summary").click()
    expect(
        page.locator('lf-diff [data-lf-datum=\'["app.py","new",1]\']')
    ).to_have_count(1)
    assert external == []


@pytest.mark.parametrize(
    "stem",
    ["notification-playground", "data-explorer", "code-comparison"],
)
def test_playground_examples_keep_their_offline_interaction_mode(
    browser, serve, tmp_path, stem
):
    source = ROOT / "examples" / f"{stem}.html"
    url = serve(source)
    live = open_page(browser, url)
    playground = live.locator("lf-playground")

    if stem == "notification-playground":
        playground.get_by_role("button", name="Needs attention").click()
        submit = playground.get_by_role("button", name="Create notification")
    elif stem == "data-explorer":
        live.locator('.query-row[data-filter-id="filter-2"] input').fill("80")
        submit = playground.get_by_role("button", name="Build query")
    else:
        playground.get_by_role("button", name="Wrapped reader").click()
        submit = playground.get_by_role("button", name="Apply treatment")
    with sending(live, f"the {stem} configuration"):
        submit.click()
    live.close()

    interactive_path = tmp_path / f"{stem}-interactive.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive_path),
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output

    offline = browser.new_page(viewport={"width": 900, "height": 700})
    external = []
    document_url = interactive_path.as_uri()
    offline.on(
        "request",
        lambda request: (
            external.append(request.url)
            if request.url != document_url and not request.url.startswith("data:")
            else None
        ),
    )
    offline.goto(document_url, wait_until="load")
    expect(offline.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(offline.locator(".lf-chrome")).to_have_count(0)
    expect(offline.locator(".lf-playground-submit")).to_be_disabled()
    expect(offline.locator(".lf-playground-unavailable")).to_have_text(
        "Submission unavailable: no agent or server is available."
    )
    if stem == "notification-playground":
        pressure = offline.get_by_role("slider", name="Concurrent release events")
        pressure.press("Home")
        pressure.press("ArrowRight")
        expect(offline.locator(".notification-demo-card-banner")).to_have_count(2)
    elif stem == "data-explorer":
        offline.get_by_role("button", name="Add filter").click()
        expect(offline.locator(".query-row")).to_have_count(3)
    else:
        width = offline.get_by_role("slider", name="Comparison viewport")
        width.press("Home")
        for _ in range(7):
            width.press("ArrowRight")
        expect(offline.locator('[data-candidate="A"]')).to_have_attribute(
            "style", re.compile(r"width: 420px")
        )
        expect(offline.locator('[data-candidate="B"]')).to_have_attribute(
            "style", re.compile(r"width: 420px")
        )
    assert external == []


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
        lambda request: page.lf_errors.append(f"unfetched {request.url}"),
    )
    page.goto(out.as_uri(), wait_until="load")
    source = (ROOT / "examples" / "pr-walkthrough.html").read_text(encoding="utf-8")
    title = re.search(r"<h1>(.*?)</h1>", source, re.DOTALL).group(1).strip()
    expect(page.get_by_role("heading", name=title)).to_be_visible()
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    assert page.evaluate("document.compatMode") == "CSS1Compat"
    assert page.locator('link[rel="stylesheet"]').count() == 0
    assert page.locator("style").count() > 0


def test_exporting_an_example_leaves_the_live_preview_untouched(
    monkeypatch, page_dir, standing_server
):
    """An offline handoff can be made while its live preview keeps serving."""
    live_source = (page_dir / "index.html").read_bytes()
    live_server = standing_server(page_dir)
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


def test_export_refuses_server_dependent_samples(serve, tmp_path):
    serve(
        leaf_page(
            "Live sample",
            '<lf-sample id="practice" label="practice">'
            '<template id="practice-source" data-sample><h1>Child</h1></template>'
            "</lf-sample>",
        )
    )
    output = tmp_path / "offline.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(output),
        ],
    )
    assert result.exit_code != 0
    assert "Live samples need a server" in result.output
    assert not output.exists()


def test_an_export_keeps_utf8(browser, serve, tmp_path):
    literal = "urn:leaf-resource:" + "a" * 64
    source = leaf_page(
        "Café handoff",
        f'<h1>Café handoff</h1><p id="literal">{literal}</p><section id="native-shadow"><template shadowrootmode="open"><p id="shadow-text">Captured shadow text</p></template></section><script id="body-probe" type="module">window.order.push("body");</script>',
        head='<style>#literal::after {content:"</noscript>";}</style><meta name="parser-probe" content="head"><script id="head-probe" type="module">window.order = [document.querySelector("#head-probe").parentElement.tagName.toLowerCase()];</script>',
    )
    serve(source)
    out = tmp_path / "cafe.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    assert out.read_text(encoding="utf-8").startswith(UTF8_BOM)

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    wait_until_ready(page)
    assert page.evaluate("document.characterSet") == "UTF-8"
    assert page.evaluate("window.order") == ["head", "body"]
    assert page.evaluate("document.doctype.name") == "html"
    assert page.locator("head > meta[charset]").count() == 1
    expect(page.locator("#native-shadow #shadow-text")).to_have_text(
        "Captured shadow text"
    )
    expect(page.locator("#literal")).to_have_text(literal)
    expect(page.get_by_role("heading", name="Café handoff")).to_have_count(1)
    expect(page.get_by_role("heading", name="Café handoff")).to_be_visible()
    disabled = browser.new_page(java_script_enabled=False)
    disabled.goto(out.as_uri(), wait_until="load")
    expect(disabled.get_by_role("heading", name="Café handoff")).to_have_count(1)
    expect(disabled.locator("#literal")).to_have_text(literal)
    expect(disabled.locator("#literal")).to_have_css(
        "content", '"</noscript>"', pseudo="after"
    )


def test_an_export_without_scripts_keeps_text_layout_and_alt_text(
    browser, serve, tmp_path
):
    source = (
        leaf_page(
            "Readable record",
            '<h1>Readable record</h1><p id="words">The recording compares two routes.</p>'
            '<img id="poster" src="/media/d7cf2b4e22c063dd.png?ignored=1#frame" alt="First frame: two routes">'
            '<video controls src="/media/2930ad3df7819c50.mp4#t=2"></video>'
            '<div id="layout" style="display:grid;grid-template-columns:1fr 1fr;background:url(/media/d7cf2b4e22c063dd.png)"><p>Before</p><p>After</p></div>',
            head="<style>@media screen { #words { color: rgb(12, 34, 56); background:url(/media/d7cf2b4e22c063dd.png); } }</style>",
        )
        .replace("<html ", '<html data-author="record" ')
        .replace("<body>", '<body class="authored">')
    )
    serve(source)
    out = tmp_path / "readable.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    page = browser.new_page(
        java_script_enabled=False, viewport={"width": 390, "height": 844}
    )
    requests = []
    failures = []
    page.on("request", lambda request: requests.append(request.url))
    page.on("requestfailed", lambda request: failures.append(request.url))
    page.goto(out.as_uri(), wait_until="load")
    expect(page.get_by_role("heading", name="Readable record")).to_be_visible()
    expect(page.get_by_role("note")).to_contain_text("JavaScript")
    expect(page.locator("#words")).to_have_css("color", "rgb(12, 34, 56)")
    expect(page.locator("#layout")).to_have_css("display", "grid")
    assert page.locator("#poster").get_attribute("alt") == "First frame: two routes"
    assert page.locator("#poster").get_attribute("src") is None
    assert page.locator("video").get_attribute("src") is None
    assert page.locator("#poster").get_attribute("data-lf-media-width") == "320"
    assert page.locator("html").get_attribute("data-author") == "record"
    assert page.locator("body").get_attribute("class") == "authored"
    assert page.locator("script[src]").count() == 0
    assert failures == []
    assert requests == [out.as_uri()]
    assert page.locator("body").bounding_box()["width"] <= 390


def test_an_export_draws_a_chart_whose_body_is_plot_code(browser, serve, tmp_path):
    """An lf-chart body is a Plot expression the widget compiles, so the export's policy
    admits compiling it as the served page's does. Refused, the chart shows an error
    over its source in the file a user was sent, while it drew in the author's
    preview."""
    serve(
        leaf_page(
            "Exported chart",
            '<h1>Exported chart</h1><lf-chart id="c"><pre>'
            '{ariaLabel: "one bar of 3", marks: [Plot.barY([3])]}'
            "</pre></lf-chart>",
        )
    )
    out = tmp_path / "chart.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator("#c svg[role=img]")).to_have_attribute(
        "aria-label", "one bar of 3"
    )
    expect(page.locator("#c .lf-error")).to_have_count(0)


def test_an_export_keeps_its_quiet_words_off_screen(browser, serve, tmp_path):
    """A status word written for a user listening (`.lf-quiet`) is clipped on screen in
    an export as in the live page. The rule that clips it once lived only in the
    chrome's sheet, which an export never adopts, so every milestone in an exported
    file read "done" or "active" beside the dot that already said it."""
    serve(
        leaf_page(
            "Quiet words",
            '<h1>Quiet words</h1><lf-milestones><lf-milestone id="m" status="done">'
            "<strong>Ship</strong></lf-milestone></lf-milestones>",
        )
    )
    out = tmp_path / "quiet.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    quiet = page.locator("#m .lf-quiet")
    expect(quiet).to_have_count(1)
    box = quiet.evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return [r.width, r.height, getComputedStyle(el).clipPath]; }"
    )
    assert box[0] <= 1 and box[1] <= 1 and box[2] != "none", box


def test_an_export_embeds_only_the_widgets_its_markup_names(browser, serve, tmp_path):
    """A widget the page and its messages never name brings none of its modules.

    The page draws code and a reply carries a diagram; nothing names a diff, so
    Pierre's renderer, the largest bundle the layer vendors, stays out of the file.
    """
    serve(
        leaf_page(
            "Reachable modules",
            '<h1>Reachable</h1><lf-code id="snippet" language="python">'
            "<pre>print('hi')</pre></lf-code>",
        )
    )
    root = append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Sketch it?"},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "revision": 1,
            "text": "Here:",
            "markup": '<lf-diagram id="sketch"><pre>flowchart LR\n  A --> B\n'
            "</pre></lf-diagram>",
        },
    )
    assert (serve.page_dir / "vendor" / "pierre-diffs.esm.js").is_file()
    out = tmp_path / "reachable.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    html = out.read_text(encoding="utf-8")
    composed = json.loads(
        re.search(
            r'<script type="application/json" data-lf-export>(.*?)</script>',
            html,
            re.DOTALL,
        )[1]
    )["document"]
    imports = json.loads(
        re.search(r'<script type="importmap"[^>]*>(.*?)</script>', composed, re.DOTALL)[
            1
        ]
    )["imports"]
    assert {"leaf:/widgets/lf-code.js", "leaf:/widgets/lf-diagram.js"} <= set(imports)
    assert not {
        "leaf:/widgets/lf-diff.js",
        "leaf:/vendor/pierre-diffs.esm.js",
    } & set(imports)

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator("#snippet")).to_contain_text("print")


def test_a_historical_export_embeds_its_captured_css_graph(browser, serve, tmp_path):
    """Nested imports and images come from the captured revision, not mutable files."""
    icon = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><rect width="24" height="24" fill="navy"/></svg>'
    source = leaf_page(
        "Captured appearance",
        """
<h1 id="title">Captured appearance</h1>
<figure id="badge"><img src="/page/icon.svg" alt="Captured badge" width="24" height="24"></figure>
<svg id="vector" width="24" height="24"><image href="/page/icon.svg" width="24" height="24"></image></svg>
<img id="responsive" srcset="/page/icon.svg 1x, /page/icon-2.svg 2x" alt="Responsive badge">
<p id="inline" style="background-image: url('/page/icon.svg')">Inline asset</p>
<pre id="quoted"><code>url('/page/icon.svg')</code></pre>
""",
        head='<link rel="stylesheet" href="/page/styles/main.css">',
    )
    serve(
        source,
        page_files={
            "icon.svg": icon,
            "icon-2.svg": icon.replace("navy", "green"),
            "styles/main.css": """
@import "./nested/palette.css" layer(captured) supports(display: grid) screen;
#title { color: var(--export-tone) !important; }
""",
            "styles/nested/palette.css": """
@import "../main.css";
body { --export-tone: rgb(12, 34, 56); }
#badge { background-image: url('../../icon.svg'); }
""",
        },
    )
    # Replacing, not writing through the initialized fixture's immutable hardlinks.
    files_model.replace_files(
        [
            (
                serve.page_dir / "theme.css",
                b":root { --mutable-theme-only: 1; }",
                False,
            ),
            (
                serve.page_dir / "runtime/chrome.css",
                b":root { --mutable-chrome-only: 1; }",
                False,
            ),
            (
                serve.page_dir / "page/styles/nested/palette.css",
                b"body { --export-tone: red; }",
                False,
            ),
            (
                serve.page_dir / "page/icon.svg",
                icon.replace('"24"', '"48"').encode(),
                False,
            ),
        ]
    )
    out = tmp_path / "captured.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    exported = out.read_text(encoding="utf-8")
    assert "--mutable-theme-only" not in exported
    assert "--mutable-chrome-only" not in exported
    page = browser.new_page()
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator("#title")).to_have_css("color", "rgb(12, 34, 56)")
    expect(page.get_by_role("img", name="Captured badge")).to_have_js_property(
        "naturalWidth", 24
    )
    assert page.locator("#vector image").get_attribute("href").startswith("blob:")
    assert page.locator("#responsive").get_attribute("srcset").count("blob:") == 2
    expect(page.locator("#quoted")).to_have_text("url('/page/icon.svg')")
    for selector in ("#badge", "#inline"):
        assert (
            page.locator(selector)
            .evaluate("el => getComputedStyle(el).backgroundImage")
            .startswith('url("blob:')
        )
    assert [url for url in requests if not url.startswith(("data:", "blob:"))] == [
        out.as_uri()
    ]


def test_a_gloss_keeps_its_explanation_in_print(browser, serve):
    """Hover is only the live page's presentation. Print has no pointer contract, so
    the author-written tip becomes visible inline."""
    source = leaf_page(
        "gloss export",
        """
<h1>Rollout</h1>
<p>Start with a <lf-gloss tip="A thin path through the real system."
  >walking skeleton</lf-gloss> before parallelizing.</p>
""",
    )
    url = serve(source)

    live = browser.new_page(viewport={"width": 1200, "height": 900})
    live.goto(url, wait_until="load")
    live.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    tip = live.locator(".lf-gloss-popover")
    expect(tip).to_be_hidden()
    live.emulate_media(media="print")
    expect(tip).to_be_visible()
    assert tip.evaluate("el => getComputedStyle(el).position") == "static"


@pytest.mark.parametrize("resolved", [False, True], ids=["open", "resolved"])
def test_inline_threads_keep_their_words_without_live_controls_in_print(
    browser, serve, tmp_path, resolved
):
    """Paper shows even a closed thread, and none of its live controls."""
    url = serve(
        leaf_page(
            "thread export",
            '<h1>Review</h1><lf-diff id="patch" source="review-patch">'
            "<pre></pre></lf-diff>",
        )
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n',
    )
    image = tmp_path / "evidence.svg"
    image.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">'
        '<rect width="24" height="24" fill="navy"/></svg>'
    )
    _, image_url = media_model.cmd_media(serve.page_dir, [image])[0]
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep this check beside the changed line.\n\n"
            f"![Review evidence]({image_url})",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )
    if not resolved:
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "status",
                str(serve.page_dir),
                "working",
                "checking the shard",
                "--on",
                root["id"],
            ],
        )
        assert result.exit_code == 0, result.output
    if resolved:
        append_carried_log_record(
            serve.page_dir,
            {"kind": "resolve", "author": "user", "parent": root["id"]},
        )
    selector = f'lf-diff .lf-page-thread[data-thread="{root["id"]}"]'
    live = open_page(browser, url)
    thread = live.locator(selector)
    expect(thread).to_have_count(1)
    expect(thread.locator("button")).not_to_have_count(0)
    if not resolved:
        inline_workflow = thread.locator(".lf-msg-sending")
        expect(inline_workflow).to_have_text("Working")
        live.keyboard.press("c")
        panel_workflow = live.locator(
            f'.lf-chrome .lf-thread[data-id="{root["id"]}"] .lf-msg-sending'
        )
        expect(panel_workflow).to_have_text("Working")
        workflow_face = """node => {
          const style = getComputedStyle(node);
          const separator = getComputedStyle(node, '::before');
          return [style.color, style.fontWeight, style.whiteSpace,
            separator.content, separator.color];
        }"""
        assert inline_workflow.evaluate(workflow_face) == panel_workflow.evaluate(
            workflow_face
        )
    live.emulate_media(media="print")
    expect(thread.locator(".lf-msg-body")).to_be_visible()
    assert (
        thread.locator(
            "button:visible, leaf-text:visible, .lf-msg-sending:visible"
        ).count()
        == 0
    )


# What a page's own module does, attempted in turn.
POLICY_ATTEMPTS = """\
const image = (src) => new Promise((resolve) => {
  const img = new Image();
  img.onload = () => resolve("ran");
  img.onerror = () => resolve("refused");
  img.src = src;
});
const attempts = {
  eval: () => eval("'ran'"),
  "blob worker": () => new Promise((resolve) => {
    const source = new Blob(["postMessage('ran')"], {type: "text/javascript"});
    const worker = new Worker(URL.createObjectURL(source));
    worker.onmessage = (event) => resolve(event.data);
    worker.onerror = () => resolve("refused");
  }),
  "classic script": () => window.classicRan,
  "remote image": () => image("https://outside.invalid/pixel.png"),
  "remote fetch": async () => (await fetch("https://outside.invalid/data.json")).text(),
};
window.policyOutcomes = (async () => {
  const outcomes = {};
  for (const [name, attempt] of Object.entries(attempts)) {
    try {
      outcomes[name] = await attempt();
    } catch (error) {
      outcomes[name] = error.name;
    }
  }
  return outcomes;
})();
"""
# One transparent pixel, what another server answers with.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def test_an_export_runs_what_its_served_page_runs(browser, serve, tmp_path):
    """A page's scripts, a deferred classic file and a module, run the same in the
    served page and its export, so a library draws in both or neither: its code may
    compile at run time, start a blob: worker, and reach any server."""
    source = leaf_page(
        "One page",
        "<h1>One page</h1>",
        head='<script defer src="/page/classic.js"></script>\n'
        '<script type="module" src="/page/attempts.js"></script>',
    )
    version = serve(
        source,
        page_files={
            "classic.js": "window.classicRan = 'ran';\n",
            "attempts.js": POLICY_ATTEMPTS,
        },
    )
    out = tmp_path / "offline.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    expected = {
        "eval": "ran",
        "blob worker": "ran",
        "classic script": "ran",
        "remote image": "ran",
        "remote fetch": "data",
    }

    def outside(route):
        is_image = route.request.url.endswith(".png")
        route.fulfill(
            body=PIXEL if is_image else b"data",
            content_type="image/png" if is_image else "text/plain",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    for url in (live_url(version), out.as_uri()):
        context = browser.new_context(viewport={"width": 1200, "height": 900})
        context.route("https://outside.invalid/**", outside)
        page = open_page(browser, url, context=context)
        assert page.evaluate("() => window.policyOutcomes") == expected, url
