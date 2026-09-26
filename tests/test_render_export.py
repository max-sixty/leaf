"""Preview and offline export tests."""

import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from typing import NamedTuple

import preview as preview_model
import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from example_data import patch_manifest
from interact_support import install_payload, wait_for
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import files as files_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import media as media_model
from leaf import server as server_model
from leaf import service as service_model
from leaf.structure import UTF8_BOM
from playwright.sync_api import expect
from render_cases_navigation import (
    source_revision,
)
from render_harness import (
    REPLAYED_PAGE,
    consume_browser_errors,
    leaf_page,
    open_page,
    restarting,
    round_trip,
    sending,
)

pytestmark = pytest.mark.nightly

ROOT = Path(__file__).parent.parent
PREVIEW_SCRIPT = str(ROOT / "scripts" / "preview.py")


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
    """Run a preview the way a host's background runner does, and read its URL.

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
        log.read_text, announced, failure="the preview printed no URL", timeout=90
    )
    url = next(line for line in output.splitlines() if line.startswith("http://"))
    return process, url


def end_preview(process) -> None:
    """Stop a preview the way a host's runner stops a task.

    The exit status is not the evidence: a signal that lands while `watchfiles`
    waits comes back out of it as `KeyboardInterrupt`, so the same stop exits 130
    or 143 depending on where it lands. What the stop left running is.
    """
    os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=30)


def test_interrupting_a_live_preview_exits_without_a_traceback(preview_slot, spawn):
    """Ctrl-C retires the watcher and its server without a traceback or lost feedback."""
    slot, page = preview_slot
    preview = spawn(
        [
            sys.executable,
            PREVIEW_SCRIPT,
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

    deadline = time.monotonic() + 90
    while not server_model.running_server(page):
        if preview.poll() is not None:
            output, _ = preview.communicate()
            pytest.fail(f"preview exited before serving:\n{output}")
        if time.monotonic() > deadline:
            pytest.fail("preview did not start serving within 90 seconds")
        time.sleep(0.05)

    os.killpg(preview.pid, signal.SIGINT)
    output, _ = preview.communicate(timeout=10)

    assert preview.returncode == 130, output
    assert server_model.running_server(page) is None
    assert (page / "events.jsonl").is_file()
    assert "Traceback" not in output


def test_terminating_a_preview_stops_its_claimed_service(tmp_path, preview_slot, spawn):
    """A runner's SIGTERM ends a preview through the same cleanup Ctrl-C runs.

    Python's default SIGTERM skips every `finally`, so without the preview's own
    handler a stopped `--user` preview left its durable service serving the page.
    """
    slot, page = preview_slot
    process, url = start_preview(
        spawn,
        [sys.executable, PREVIEW_SCRIPT, "heat-loss", "--slot", slot, "--user"],
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
            [sys.executable, PREVIEW_SCRIPT, "heat-loss", "--slot", slot, "--user"],
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
        timeout=90,
    )
    assert children, (tmp_path / "preview.log").read_text()
    os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=30)
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
            sys.executable,
            PREVIEW_SCRIPT,
            "--source",
            str(source),
            "--slot",
            slot,
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=90,
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
        deadline = time.monotonic() + 10
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
                sys.executable,
                PREVIEW_SCRIPT,
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
        sys.executable,
        PREVIEW_SCRIPT,
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
        timeout=90,
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
        with urllib.request.urlopen(url, timeout=5) as answer:
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
            sys.executable,
            PREVIEW_SCRIPT,
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
    events_model.append_event(
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
            sys.executable,
            PREVIEW_SCRIPT,
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
    tmp_path, preview_slot, codex_program, codex_env, spawn
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
            sys.executable,
            PREVIEW_SCRIPT,
            "--source",
            str(source),
            "--runtime",
            str(runtime),
            "--slot",
            slot,
            "--user",
        ],
        env=codex_env
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
        timeout=90,
    )
    claim = service_model.page_claim(directory)
    assert claim["pid"] == owner.pid
    with theme.open("a", encoding="utf-8") as stream:
        stream.write("\nh1 { color: navy; }\n")
    wait_for(
        log.read_text,
        lambda output: "Reloaded detached" in output,
        failure="the preview did not restart for its runtime",
        timeout=60,
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
            timeout=30,
        )
        transaction.release_claim()
    wait_for(
        log.read_text,
        lambda output: "no longer owns" in output,
        failure="the preview did not report its lost claim",
        timeout=30,
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
        timeout=30,
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
    navigations = []
    page.on(
        "framenavigated",
        lambda frame: (
            navigations.append(frame.url) if frame == page.main_frame else None
        ),
    )

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
        assert len(navigations) == 1
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
    assert len(navigations) == 2
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
    navigations = []
    page.on(
        "framenavigated",
        lambda frame: (
            navigations.append(frame.url) if frame == page.main_frame else None
        ),
    )

    def interrupt_entry(route):
        if failures:
            route.continue_()
            return
        failures.append(True)
        route.abort()

    def static_registry(route):
        if len(navigations) > 1:
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
    assert len(navigations) == 2
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
            paused.enter_context(events_model.flocked(directory / "events.jsonl"))
            theme = runtime / "skills" / "leaf" / "assets" / "theme.css"
            with theme.open("a", encoding="utf-8") as stream:
                stream.write("\nh1 { color: navy; }\n")
            # The record says the service is stopping before its socket closes, so
            # the address is what says the start's fetch will find nothing.
            wait_for(
                lambda: _reachable(url),
                lambda reachable: not reachable,
                failure="the runtime edit did not stop the service",
                timeout=30,
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
            timeout=90,
        )


def test_preview_adds_immutable_media_before_stamping_source(watched_preview):
    source, _, directory, _, _, log = watched_preview
    media = source.parent / "media"
    media.mkdir()
    image = media / "051bee487bfb5d13.png"
    expected = (ROOT / "examples" / "media" / image.name).read_bytes()
    image.write_bytes(expected)
    revised = source.read_text().replace(
        "</main>", f'<img src="/media/{image.name}" alt="Preview proof"></main>'
    )
    source.write_text(revised)
    wait_for(
        lambda: (directory / "index.html").read_text(),
        lambda source: source == revised,
        failure="the source referencing new media was not stamped",
        timeout=30,
    )
    assert (directory / "media" / image.name).read_bytes() == expected

    image.write_bytes(b"changed bytes")
    wait_for(
        log.read_text,
        lambda output: "use a new filename" in output,
        failure="the changed media bytes were not refused",
        timeout=30,
    )
    assert (directory / "media" / image.name).read_bytes() == expected

    image.unlink()
    second = media / "a99a1b63048502d0.png"
    second.write_bytes((ROOT / "examples" / "media" / second.name).read_bytes())
    wait_for(
        lambda: (directory / "media" / second.name).exists(),
        bool,
        failure="the new media did not reach the preview",
        timeout=30,
    )
    assert (directory / "media" / image.name).read_bytes() == expected


def test_terminating_a_preview_mid_update_leaves_no_service(served_preview):
    """A SIGTERM during an update's stopped-service interval suppresses its restart."""
    source, runtime, directory, process, _, _ = served_preview
    # Real page-transaction contention pauses init after the watcher stops the service.
    with events_model.flocked(directory / "events.jsonl"):
        theme = runtime / "skills" / "leaf" / "assets" / "theme.css"
        with theme.open("a", encoding="utf-8") as stream:
            stream.write("\nh1 { color: navy; }\n")
        deadline = time.monotonic() + 30
        while json.loads((directory / "service.json").read_text())["enabled"]:
            assert time.monotonic() < deadline, "watcher did not begin the update"
            time.sleep(0.05)
        os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=30)
    assert server_model.running_server(directory) is None
    assert (directory / "events.jsonl").is_file()
    assert (directory / "index.html").read_bytes() == source.read_bytes()


@pytest.mark.parametrize("edit", ["source", "runtime"])
def test_a_user_preview_update_keeps_the_sessions_wait_watching(
    tmp_path, served_preview, spawn, edit
):
    """A `--user` preview's update is not a stop, so the session's wait carries on.

    The update used to disable the page's service for its whole length, and a wait
    watching the page read that as a server someone stopped: with no other page to
    carry, it ended with `server is not running` on every save. A source edit now
    leaves the server up, and a runtime edit's restart says it is one while it runs.
    The comment after the update is the proof: only a wait still watching delivers it.
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
        timeout=30,
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
        timeout=60,
    )
    assert server_model.running_server(directory)
    assert waiter.poll() is None, waited.read_text()

    events_model.append_event(
        directory,
        {
            "kind": "comment",
            "author": "user",
            "revision": files_model.latest_revision(directory),
            "text": "still there?",
        },
    )
    assert waiter.wait(timeout=30) == 0, waited.read_text()
    assert "still there?" in waited.read_text()


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

  requestRun() {
    return this.controller.dispatch({kind: "request", verb: "run", detail: {}});
  }

  render() {
    const choice = this.reading.state.choose?.value ?? this.getAttribute("choice");
    const action = this.reading.actions.choose;
    const request = this.reading.requests.run;
    const unavailable = action.unavailable ?? request.unavailable;
    return html`
      <style>#local { color: rgb(12, 34, 56); }</style>
      <button id="local" @click=${() => { this.local += 1; this.requestUpdate(); }}>
        Increment locally
      </button>
      <output id="local-value">${this.local}</output>
      <button id="choose" ?disabled=${!action.available} @click=${this.choose}>
        Choose on host
      </button>
      <button id="request" ?disabled=${!request.available} @click=${this.requestRun}>
        Request host work
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
            "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
            "choice": {"type": "string"},
            "restated": {"type": "boolean"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "members",
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
        "x-request": {
            "offers": {"lf-offline-command": "verb"},
            "verbs": {
                "run": {
                    "detail": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    }
                }
            },
        },
        "x-example": (
            '<lf-offline-test id="offline-example" choice="idle">'
            '<lf-offline-command verb="run">Run</lf-offline-command>'
            "</lf-offline-test>"
        ),
    },
    "lf-offline-command": {
        "description": "One host request offered by the test widget.",
        "type": "object",
        "properties": {"verb": {"enum": ["run"]}},
        "required": ["verb"],
        "additionalProperties": False,
        "x-owners": ["lf-offline-test"],
        "x-content": "markup",
        "x-upgrade": False,
    },
}


def test_interactive_export_with_an_ask_reaches_application_presentation(
    browser, serve, tmp_path
):
    """Offline mode omits thread chrome without leaving its ticket pending."""
    serve(ROOT / "examples" / "notification-playground.html")
    interactive = tmp_path / "interactive-with-ask.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "version",
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


def test_interactive_export_runs_captured_local_behavior_without_a_host(
    browser, serve, tmp_path
):
    """One file boots the captured runtime, but never resurrects its host boundary."""
    source = leaf_page(
        "offline interactive",
        """
<h1>Offline interactive</h1>
<lf-offline-test id="offline-widget" choice="idle">
  <lf-offline-command verb="run">Run</lf-offline-command>
</lf-offline-test>
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
            "version",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive),
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output
    assert "opens with no server" in result.output

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
    expect(page.locator("#offline-widget #request")).to_be_disabled()
    expect(page.locator("#offline-widget #unavailable")).to_have_text(
        "no agent or server is available"
    )
    refused = page.locator("#offline-widget").evaluate(
        """owner => [
          owner.choose(),
          owner.requestRun(),
          owner.controller.dispatch({kind: 'undo', target: 'missing'}),
        ]"""
    )
    assert refused == [None, None, None]
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
            "version",
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
            "version",
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
    out = ROOT / ".tmp" / "example-pr-walkthrough.html"
    result = subprocess.run(
        [
            sys.executable,
            PREVIEW_SCRIPT,
            "pr-walkthrough",
            "--export",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.stdout.splitlines()[-1] == str(out.resolve())

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
    import preview

    monkeypatch.setattr(preview, "TMP", page_dir.parent)
    monkeypatch.setattr(sys, "argv", ["preview.py", "pr-walkthrough", "--export"])

    try:
        preview.main()
        assert live_server.poll() is None
        assert (page_dir / "index.html").read_bytes() == live_source
    finally:
        CliRunner().invoke(cli_model.cli, ["server", "stop", str(page_dir)])
        live_server.wait(timeout=5)


def test_export_refuses_server_dependent_specimens(serve, tmp_path):
    serve(
        leaf_page(
            "Live specimen",
            '<lf-specimen id="practice" label="practice">'
            '<template id="practice-source" data-specimen><h1>Child</h1></template>'
            "</lf-specimen>",
        )
    )
    output = tmp_path / "offline.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "version",
            "export",
            str(serve.page_dir),
            "--out",
            str(output),
        ],
    )
    assert result.exit_code != 0
    assert "Live specimens need a server" in result.output
    assert not output.exists()


def test_an_export_keeps_utf8(browser, serve, tmp_path):
    serve(leaf_page("Café handoff", "<h1>Café handoff</h1>"))
    out = tmp_path / "cafe.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    assert out.read_text(encoding="utf-8").startswith(UTF8_BOM)

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    assert page.evaluate("document.characterSet") == "UTF-8"
    expect(page.get_by_role("heading", name="Café handoff")).to_be_visible()


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
    root = events_model.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Sketch it?"},
    )
    events_model.append_event(
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
    imports = json.loads(
        re.search(r'<script type="importmap"[^>]*>(.*?)</script>', html, re.DOTALL)[1]
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
    assert (
        page.locator("#vector image")
        .get_attribute("href")
        .startswith("data:image/svg+xml;base64,")
    )
    assert (
        page.locator("#responsive")
        .get_attribute("srcset")
        .count("data:image/svg+xml;base64,")
        == 2
    )
    expect(page.locator("#quoted")).to_have_text("url('/page/icon.svg')")
    for selector in ("#badge", "#inline"):
        assert (
            page.locator(selector)
            .evaluate("el => getComputedStyle(el).backgroundImage")
            .startswith('url("data:image/svg+xml;base64,')
        )
    assert [url for url in requests if not url.startswith("data:")] == [out.as_uri()]


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
    root = events_model.append_event(
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
        events_model.append_event(
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
    expect(thread.locator(".lf-page-thread-body")).to_be_visible()
    assert (
        thread.locator(
            "button:visible, textarea:visible, .lf-msg-sending:visible"
        ).count()
        == 0
    )


def test_an_export_keeps_the_non_fetch_policy(browser, serve, tmp_path):
    source = leaf_page(
        "Export CSP",
        """
<h1>Export CSP</h1>
<a id="relative" href="relative-target">Relative target</a>
<form id="escape" action="https://outside.invalid/collect" method="post">
  <input name="page-state" value="user decision">
  <button type="submit">Send page state</button>
</form>
""",
        head='<base href="https://outside.invalid/rebased/">',
    )
    serve(source)
    out = tmp_path / "offline.html"
    exporting_model.cmd_export(serve.page_dir, out, None)

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.add_init_script(
        """
          window.__cspViolations = [];
          document.addEventListener('securitypolicyviolation', event => {
            window.__cspViolations.push(event.effectiveDirective);
          });
        """
    )
    escaped = []
    page.route(
        "https://outside.invalid/**",
        lambda route: (
            escaped.append(route.request.url),
            route.fulfill(status=204, body=""),
        ),
    )
    page.goto(out.as_uri(), wait_until="load")
    page.wait_for_function("() => window.__cspViolations.includes('base-uri')")
    assert page.locator("#relative").evaluate("link => link.protocol") == "file:"
    page.locator("#escape").evaluate("form => form.requestSubmit()")
    page.wait_for_function("() => window.__cspViolations.includes('form-action')")
    assert escaped == []
    # Both refusals asserted above are reported on the console as well.
    consume_browser_errors(page, "violates the following Content Security Policy")
