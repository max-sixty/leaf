"""Standalone export tests."""

import importlib.util
import itertools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import install_payload
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import hosting as hosting_model
from leaf import leases as leases_model
from leaf import render_checks as render_checks_model
from leaf import server as server_model
from leaf import service as service_model
from leaf.render_gate import browser as browser_model
from playwright.sync_api import expect
from render_support import (
    LONG_PAGE,
    PAGE_FIXTURES,
    REPORT_PAGE,
    leaf_page,
    open_page,
    primed,
    refuse,
    resized,
    restarting,
    sending,
    serious_axe_violations,
    watched,
)

pytestmark = pytest.mark.nightly

ROOT = Path(__file__).parent.parent


@pytest.fixture
def preview_slot(tmp_path):
    slot = f"pytest-{os.getpid()}-{tmp_path.name}"
    page = ROOT / ".tmp" / "previews" / slot
    yield slot, page
    if server_model.running_server(page):
        hosting_model.cmd_stop(page)
    shutil.rmtree(page, ignore_errors=True)


def test_interrupting_a_live_preview_exits_without_a_traceback(preview_slot, spawn):
    """Ctrl-C retires the watcher and its server without a traceback or lost feedback."""
    slot, page = preview_slot
    preview = spawn(
        [
            sys.executable,
            str(ROOT / "scripts" / "preview.py"),
            "design-decision",
            "--slot",
            slot,
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
            str(ROOT / "scripts" / "preview.py"),
            "--source",
            str(source),
            "--slot",
            slot,
            "--background",
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


def test_named_live_previews_serve_one_source_in_independent_runtime_slots(
    browser, tmp_path
):
    """A developer can hold one fixture still while two vendored runtimes serve it.

    The named pages and their background services are the public evidence. If the
    script falls back to its single default directory, the second run stops and
    replaces the first; if it ignores the shared source, the planted heading is
    absent from one or both URLs.
    """
    source = tmp_path / "shared-preview.html"
    source.write_text(
        (ROOT / "examples" / "design-decision.html")
        .read_text(encoding="utf-8")
        .replace("Where sessions live", "Shared runtime comparison", 1),
        encoding="utf-8",
    )
    prefix = f"pytest-{os.getpid()}-{tmp_path.name}"
    installed = install_payload(tmp_path / "other-runtime")
    runtime_marker = "/* preview runtime marker */"
    installed_runtime = installed / "skills" / "leaf" / "assets" / "leaf.js"
    installed_runtime.write_text(
        installed_runtime.read_text(encoding="utf-8") + f"\n{runtime_marker}\n",
        encoding="utf-8",
    )
    slots = [f"{prefix}-before", f"{prefix}-after"]
    runtimes = [ROOT, installed]
    pages = [ROOT / ".tmp" / "previews" / slot for slot in slots]
    urls = []
    try:
        for slot, runtime in zip(slots, runtimes, strict=True):
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "preview.py"),
                    "--source",
                    str(source),
                    "--runtime",
                    str(runtime),
                    "--slot",
                    slot,
                    "--background",
                ],
                cwd=ROOT,
                capture_output=True,
                check=False,
                text=True,
                timeout=90,
            )
            assert result.returncode == 0, (
                f"slot {slot}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
            output = result.stdout.splitlines()
            assert output[:2] == [
                "prepared shared-preview (1 version)",
                "",
            ]
            assert "initialized" not in result.stdout
            assert "stamped" not in result.stdout
            urls.append(output[-1])

        assert urls[0] != urls[1]
        assert all(
            page.joinpath("index.html").read_text() == source.read_text()
            for page in pages
        )
        assert runtime_marker not in pages[0].joinpath("leaf.js").read_text()
        assert runtime_marker in pages[1].joinpath("leaf.js").read_text()

        for url, runtime in zip(urls, runtimes, strict=True):
            page = browser.new_page(viewport={"width": 1200, "height": 900})
            errors = watched(page)
            page.goto(url, wait_until="load")
            expect(page.locator(".lf-preview")).to_contain_text(
                f"Preview · {runtime.name}"
            )
            expect(
                page.get_by_role("heading", name="Shared runtime comparison")
            ).to_be_visible()
            assert errors == []
            page.close()
    finally:
        for slot, page, runtime in zip(slots, pages, runtimes, strict=True):
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "preview.py"),
                    "--source",
                    str(source),
                    "--runtime",
                    str(runtime),
                    "--slot",
                    slot,
                    "--stop",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            shutil.rmtree(page, ignore_errors=True)


def test_automation_preview_records_real_gestures_outside_the_task(
    browser, tmp_path, preview_slot, spawn, request
):
    """Automation and reader previews use the same event door but different lifetimes.

    The selected runtime's temporary server is held by the watcher rather than a
    service record. Its log survives source reloads, while a distinct reader slot is
    claimed for task delivery and cannot be overwritten by automation.
    """
    slot, page_dir = preview_slot
    source = tmp_path / "automation.html"
    source.write_text(
        (ROOT / "examples" / "design-decision.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    runtime = install_payload(tmp_path / "automation-runtime")
    automation_command = [
        sys.executable,
        str(ROOT / "scripts" / "preview.py"),
        "--source",
        str(source),
        "--runtime",
        str(runtime),
        "--slot",
        slot,
        "--automation",
    ]
    automation_process = spawn(
        automation_command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert automation_process.stdout.readline() == ("prepared automation (1 version)\n")
    assert automation_process.stdout.readline() == "\n"
    automation_url = automation_process.stdout.readline().strip()
    assert automation_url.startswith("http://127.0.0.1:")
    assert (
        automation_process.stderr.readline().strip()
        == "server   temporary (stops with this command)"
    )
    assert service_model.page_claim(page_dir) is None
    assert not (page_dir / "service.json").exists()
    watcher_metadata = page_dir.with_name(f"{page_dir.name}.preview.json")
    assert "url" not in json.loads(watcher_metadata.read_text())
    assert page_dir not in service_model.owned_pages(
        os.environ["CLAUDE_CODE_SESSION_ID"]
    )
    automation, automation_errors = open_page(browser, automation_url)
    expect(automation.locator(".lf-preview")).to_contain_text(
        f"Automation · {runtime.name}"
    )
    with sending(automation, "the automation option pick"):
        automation.locator("#opt-redis .lf-pick").click()
    expect(automation.locator("#opt-redis")).to_have_attribute("chosen", "")
    [automated_event] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "action" and event["author"] == "user"
    ]
    feedback = (page_dir / "events.jsonl").read_bytes()
    inode = (page_dir / "events.jsonl").stat().st_ino

    with restarting(automation, automation_errors):
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "Where sessions live", "Automation follows source edits", 1
            ),
            encoding="utf-8",
        )
        expect(
            automation.get_by_role("heading", name="Automation follows source edits")
        ).to_be_visible(timeout=30000)
    expect(automation.locator("#opt-redis")).to_have_attribute("chosen", "")
    assert (page_dir / "events.jsonl").read_bytes().startswith(feedback)
    assert (page_dir / "events.jsonl").stat().st_ino == inode
    assert service_model.page_claim(page_dir) is None
    assert not (page_dir / "service.json").exists()
    assert automation_errors == []
    automation.close()

    automation_process.send_signal(signal.SIGINT)
    _, automation_stderr = automation_process.communicate(timeout=10)
    assert automation_process.returncode == 130, automation_stderr
    assert "Traceback" not in automation_stderr

    reader_slot = f"{slot}-reader"
    reader_dir = page_dir.with_name(reader_slot)
    reader_command = [
        sys.executable,
        str(ROOT / "scripts" / "preview.py"),
        "--source",
        str(source),
        "--runtime",
        str(runtime),
        "--slot",
        reader_slot,
    ]

    def cleanup_reader():
        subprocess.run(
            [*reader_command, "--stop"],
            cwd=ROOT,
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        shutil.rmtree(reader_dir, ignore_errors=True)

    request.addfinalizer(cleanup_reader)
    reader_result = subprocess.run(
        [*reader_command, "--background"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=90,
    )
    assert reader_result.returncode == 0, (
        f"stdout:\n{reader_result.stdout}\nstderr:\n{reader_result.stderr}"
    )
    reader_url = reader_result.stdout.splitlines()[-1]
    claim = service_model.page_claim(reader_dir)
    assert claim is not None and claim["id"] == os.environ["CLAUDE_CODE_SESSION_ID"]
    reader, reader_errors = open_page(browser, reader_url)
    expect(reader.locator(".lf-preview")).to_contain_text(f"Preview · {runtime.name}")
    with sending(reader, "the reader option pick"):
        reader.locator("#opt-jwt .lf-pick").click()
    expect(reader.locator("#opt-jwt")).to_have_attribute("chosen", "")
    [reader_event] = [
        event
        for event in events_model.read_events(reader_dir)
        if event["kind"] == "action" and event["author"] == "user"
    ]
    assert reader_event["id"] != automated_event["id"]
    assert reader_event in service_model.unacknowledged(
        events_model.read_events(reader_dir), 0
    )
    reader_feedback = (reader_dir / "events.jsonl").read_bytes()
    refused = subprocess.run(
        [*reader_command, "--automation"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert refused.returncode == 1
    assert "choose a new --slot" in refused.stderr
    assert (reader_dir / "events.jsonl").read_bytes() == reader_feedback
    assert reader_errors == []
    reader.close()
    stopped = subprocess.run(
        [*reader_command, "--stop"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert stopped.returncode == 0, stopped.stdout + stopped.stderr


@pytest.fixture
def watched_preview(tmp_path, preview_slot):
    source = tmp_path / "watched.html"
    original = (ROOT / "examples" / "design-decision.html").read_text(encoding="utf-8")
    source.write_text(original, encoding="utf-8")
    runtime = install_payload(tmp_path / "watched-runtime")
    slot, directory = preview_slot
    command = [
        sys.executable,
        str(ROOT / "scripts" / "preview.py"),
        "--source",
        str(source),
        "--runtime",
        str(runtime),
        "--slot",
        slot,
        "--background",
    ]
    started = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False, timeout=90
    )
    assert started.returncode == 0, started.stdout + started.stderr
    url = started.stdout.splitlines()[-1]
    yield source, runtime, directory, command, url
    stopped = subprocess.run(
        [*command[:-1], "--stop"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert stopped.returncode == 0, stopped.stdout + stopped.stderr


def test_a_detached_preview_restarts_under_its_original_codex_claim(
    tmp_path, preview_slot, codex_program, codex_env, spawn
):
    """The launcher exits; the real session lifetime survives outside worker ancestry."""
    source = tmp_path / "detached.html"
    source.write_text((ROOT / "examples" / "design-decision.html").read_text())
    slot, directory = preview_slot
    command = [
        sys.executable,
        str(ROOT / "scripts" / "preview.py"),
        "--source",
        str(source),
        "--slot",
        slot,
        "--background",
    ]
    ready = tmp_path / "started.json"
    owner = spawn(
        [
            str(codex_program),
            "-c",
            (
                "import json, pathlib, subprocess, sys; "
                "result = subprocess.run(sys.argv[2:], capture_output=True, text=True); "
                "pathlib.Path(sys.argv[1]).write_text(json.dumps([result.returncode, result.stdout, result.stderr])); "
                "sys.stdin.read()"
            ),
            str(ready),
            *command,
        ],
        env=codex_env
        | {"CODEX_THREAD_ID": "preview-codex", "PYTHONHOME": sys.base_prefix},
        stdin=subprocess.PIPE,
    )
    deadline = time.monotonic() + 90
    while not ready.exists():
        assert time.monotonic() < deadline
        time.sleep(0.05)
    result = json.loads(ready.read_text())
    assert result[0] == 0, result
    claim = service_model.page_claim(directory)
    assert claim["pid"] == owner.pid
    try:
        revised = source.read_text().replace("Where sessions live", "Detached revision")
        source.write_text(revised)
        log = directory.with_name(f"{directory.name}.preview.log")
        deadline = time.monotonic() + 30
        while "Reloaded detached" not in log.read_text():
            assert time.monotonic() < deadline, log.read_text()
            time.sleep(0.05)
        assert server_model.running_server(directory)
        assert service_model.page_claim(directory) == claim

        # SessionEnd can win while recompose waits for the page transaction.
        with service_model.PageTransaction(directory) as transaction:
            source.write_text(revised.replace("Detached revision", "Released revision"))
            deadline = time.monotonic() + 30
            while server_model.running_server(directory):
                assert time.monotonic() < deadline, "refresh did not stop the service"
                time.sleep(0.05)
            transaction.release_claim()
        deadline = time.monotonic() + 30
        while "no longer owns" not in log.read_text():
            assert time.monotonic() < deadline, log.read_text()
            time.sleep(0.05)
        assert server_model.running_server(directory) is None
        assert service_model.page_claim(directory)["released"] is not None
        lease = directory.with_name(f"{directory.name}.preview.lock")
        deadline = time.monotonic() + 10
        while leases_model.lock_is_held(lease):
            assert time.monotonic() < deadline, (
                "released session left its watcher alive"
            )
            time.sleep(0.05)
        metadata = directory.with_name(f"{directory.name}.preview.json")
        assert json.loads(metadata.read_text())["enabled"] is False
    finally:
        subprocess.run(
            [*command[:-1], "--stop"], check=True, capture_output=True, timeout=30
        )


def test_preview_watches_runtime_and_source_without_losing_reader_state(
    browser, watched_preview
):
    """The open tab follows edits; rejected source never replaces its last good page."""
    source, runtime, directory, command, url = watched_preview
    original = source.read_text(encoding="utf-8")
    page, errors = open_page(browser, url)
    with sending(page, "the watched reader option pick"):
        page.locator("#opt-redis .lf-pick").click()
    expect(page.locator("#opt-redis")).to_have_attribute("chosen", "")
    feedback = (directory / "events.jsonl").read_bytes()
    assert b'"kind": "action"' in feedback
    inode = (directory / "events.jsonl").stat().st_ino
    registry = json.loads((directory / "registry.json").read_text())
    generation = registry["$layer"]["generation"]

    theme = runtime / "skills" / "leaf" / "assets" / "theme.css"
    with restarting(page, errors):
        with theme.open("a", encoding="utf-8") as stream:
            stream.write("\nh1 { color: rgb(17, 83, 129); }\n")
        expect(page.locator("h1")).to_have_css(
            "color", "rgb(17, 83, 129)", timeout=30000
        )
    assert (
        json.loads((directory / "registry.json").read_text())["$layer"]["generation"]
        != generation
    )
    expect(page.locator("#opt-redis")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)
    assert (directory / "events.jsonl").stat().st_ino == inode

    revised = original.replace("Where sessions live", "A watched source revision", 1)
    with restarting(page, errors):
        source.write_text(revised, encoding="utf-8")
        expect(
            page.get_by_role("heading", name="A watched source revision")
        ).to_be_visible(timeout=30000)
    expect(page.locator("#opt-redis")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)

    with restarting(page, errors):
        source.write_text("<p>invalid source</p>", encoding="utf-8")
        log_path = directory.with_name(f"{directory.name}.preview.log")
        deadline = time.monotonic() + 30
        while "Preview update refused" not in log_path.read_text():
            assert time.monotonic() < deadline, log_path.read_text()
            page.wait_for_timeout(50)
        refused_generation = json.loads((directory / "registry.json").read_text())[
            "$layer"
        ]["generation"]
        expect(page.locator("script[data-lf-runtime]")).to_have_attribute(
            "data-lf-layer", refused_generation, timeout=30000
        )
    expect(
        page.get_by_role("heading", name="A watched source revision")
    ).to_be_visible()
    assert (directory / "index.html").read_text() == revised
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)

    with restarting(page, errors):
        source.write_text(
            revised.replace("A watched source revision", "Recovered watched source"),
            encoding="utf-8",
        )
        expect(
            page.get_by_role("heading", name="Recovered watched source")
        ).to_be_visible(timeout=30000)
        repeated = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, check=False, timeout=30
        )
        assert repeated.returncode == 0, repeated.stdout + repeated.stderr
        assert repeated.stdout.splitlines()[-1] == url
    expect(page.locator("#opt-redis")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)
    assert (directory / "events.jsonl").stat().st_ino == inode
    assert errors == []
    page.close()


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
    _, runtime, directory, _, url = watched_preview
    if resource == "widgets/lf-options.js":
        standing, errors = open_page(browser, url)
        with sending(standing, "the standing reader option pick"):
            standing.locator("#opt-redis .lf-pick").click()
        assert errors == []
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
    page.goto(url, wait_until="load")
    status = page.get_by_text("Leaf couldn't start. Waiting for the server to update.")
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
    (runtime / "skills" / "leaf" / "packages" / "default" / "registry.json").write_text(
        "{", encoding="utf-8"
    )
    expect(page.locator("body")).to_have_attribute(
        "data-lf-presented", "1", timeout=30000
    )
    expect(status).not_to_be_visible()
    if resource == "widgets/lf-options.js":
        expect(page.locator("#opt-redis")).to_have_attribute("chosen", "")
    assert len(navigations) == 2
    assert (
        json.loads((directory / "registry.json").read_text())["$layer"]["generation"]
        == generation
    )
    page.close()


@pytest.mark.parametrize("interrupted", ["registry.json", "widgets/lf-options.js"])
def test_a_service_that_goes_away_mid_start_says_only_that_and_comes_back(
    browser, watched_preview, interrupted
):
    """A start the restart interrupts reports the vanished server and comes back.

    The other tests here reach this condition only when the machine is loaded enough to
    lose the race, so the ordering is arranged here rather than waited for. Both of the
    start's own fetches, because the words are the fetch's rather than the condition's:
    the registry is a plain `fetch` and a widget is a dynamic import, and only the second
    names the module. Whichever one the loaded machine loses is which wording arrives.
    """
    _, _, _, command, url = watched_preview
    page = browser.new_page()
    errors = watched(page)
    stopped = []

    def stop_the_service(route):
        # Both of these are the runtime's own, so a service stopped before one is answered
        # is a service that goes away between the document arriving and the start that
        # document began — the transport has nothing left to name it by. Once only: the
        # reload the recovery makes must find a server that answers.
        if not stopped:
            stopped.append(
                subprocess.run(
                    [*command[:-1], "--stop"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
            )
        route.continue_()

    page.route(f"**/{interrupted}", stop_the_service)
    with restarting(page, errors):
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
        [halted] = stopped
        assert halted.returncode == 0, halted.stdout + halted.stderr
        restarted = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, check=False, timeout=90
        )
        assert restarted.returncode == 0, restarted.stdout + restarted.stderr
    assert errors == []
    page.close()


def test_preview_adds_immutable_media_before_stamping_source(watched_preview):
    source, _, directory, _, _ = watched_preview
    media = source.parent / "media"
    media.mkdir()
    image = media / "051bee487bfb5d13.png"
    expected = (ROOT / "examples" / "media" / image.name).read_bytes()
    image.write_bytes(expected)
    revised = source.read_text().replace(
        "</main>", f'<img src="/media/{image.name}" alt="Preview proof"></main>'
    )
    source.write_text(revised)
    deadline = time.monotonic() + 30
    while (directory / "index.html").read_text() != revised:
        assert time.monotonic() < deadline, (
            "source referencing new media was not stamped"
        )
        time.sleep(0.05)
    assert (directory / "media" / image.name).read_bytes() == expected

    image.write_bytes(b"changed bytes")
    log = directory.with_name(f"{directory.name}.preview.log")
    deadline = time.monotonic() + 30
    while "use a new filename" not in log.read_text():
        assert time.monotonic() < deadline, log.read_text()
        time.sleep(0.05)
    assert (directory / "media" / image.name).read_bytes() == expected

    image.unlink()
    second = media / "a99a1b63048502d0.png"
    second.write_bytes((ROOT / "examples" / "media" / second.name).read_bytes())
    deadline = time.monotonic() + 30
    while not (directory / "media" / second.name).exists():
        assert time.monotonic() < deadline, "new media did not reach the preview"
        time.sleep(0.05)
    assert (directory / "media" / image.name).read_bytes() == expected


def test_stopping_a_preview_waits_for_its_active_recompose(watched_preview, spawn):
    """Stop intent survives an update's own stopped-service interval and returns last."""
    source, runtime, directory, command, _ = watched_preview
    metadata = directory.with_name(f"{directory.name}.preview.json")
    # Real page-transaction contention pauses init after the watcher stops the service.
    # The stop command must wait for that work and suppress its pending restart.
    with events_model.flocked(directory / "events.jsonl"):
        theme = runtime / "skills" / "leaf" / "assets" / "theme.css"
        with theme.open("a", encoding="utf-8") as stream:
            stream.write("\nh1 { color: navy; }\n")
        deadline = time.monotonic() + 30
        while json.loads((directory / "service.json").read_text())["enabled"]:
            assert time.monotonic() < deadline, "watcher did not begin the update"
            time.sleep(0.05)
        stopping = spawn(
            [*command[:-1], "--stop"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        while json.loads(metadata.read_text())["enabled"]:
            assert time.monotonic() < deadline, "stop did not record its intent"
            time.sleep(0.05)
        assert stopping.poll() is None
    stdout, stderr = stopping.communicate(timeout=30)
    assert stopping.returncode == 0, stdout + stderr
    assert server_model.running_server(directory) is None
    assert not json.loads(metadata.read_text())["enabled"]
    assert (directory / "events.jsonl").is_file()
    assert (directory / "index.html").read_bytes() == source.read_bytes()


# ---------- export: the page as one file ----------


def test_the_example_preview_command_exports_a_file_that_opens_on_its_own(
    browser,
):
    """The handoff command names one file whose drawn page needs no live server."""
    out = ROOT / ".tmp" / "example-pr-walkthrough.html"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "preview.py"),
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
    errors = watched(page)
    page.on("requestfailed", lambda request: errors.append(f"unfetched {request.url}"))
    page.goto(out.as_uri(), wait_until="load")
    source = (ROOT / "examples" / "pr-walkthrough.html").read_text(encoding="utf-8")
    title = re.search(r"<h1>(.*?)</h1>", source, re.DOTALL).group(1).strip()
    expect(page.get_by_role("heading", name=title)).to_be_visible()
    assert page.evaluate("document.compatMode") == "CSS1Compat"
    assert page.locator("body").get_attribute("data-lf-reading") is None
    assert page.locator("script").count() == 0
    assert page.locator('link[rel="stylesheet"]').count() == 0
    assert page.locator("style").count() > 0
    assert errors == []
    page.close()


def test_exporting_an_example_leaves_the_live_preview_untouched(
    monkeypatch, page_dir, standing_server
):
    """A static handoff can be made while its interactive proof stays live."""
    live_source = (page_dir / "index.html").read_bytes()
    live_server = standing_server(page_dir)
    spec = importlib.util.spec_from_file_location(
        "leaf_preview_script", ROOT / "scripts" / "preview.py"
    )
    assert spec and spec.loader
    preview = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec.loader.exec_module(preview)
    monkeypatch.setattr(preview, "TMP", page_dir.parent)
    monkeypatch.setattr(sys, "argv", ["preview.py", "pr-walkthrough", "--export"])

    try:
        preview.main()
        assert live_server.poll() is None
        assert (page_dir / "index.html").read_bytes() == live_source
    finally:
        CliRunner().invoke(cli_model.cli, ["server", "stop", str(page_dir)])
        live_server.wait(timeout=5)


def test_a_broken_probe_module_stops_export_with_a_named_error(browser, serve):
    """Export reports its instrumentation boundary instead of leaking a traceback."""

    def break_probe(page):
        page.route(
            "**/_leaf/render-checks/index.js",
            lambda route: route.fulfill(
                status=200,
                content_type="text/javascript; charset=utf-8",
                body='import { missingForTest } from "/runtime/widget-api.js";',
            ),
        )

    url = serve(LONG_PAGE)
    root_url = url.replace("/versions/v1.html", "/")
    with pytest.raises(
        SystemExit,
        match=r"v1\.html could not load its browser probe module",
    ):
        exporting_model.export_page(
            primed(browser, break_probe), root_url, serve.page_dir, "v1.html"
        )


def test_a_browser_too_old_to_copy_a_page_is_refused_by_its_own_version(
    browser, tmp_path
):
    """`bake()` ends in `root.getHTML({ serializableShadowRoots: true })`, which
    Chromium grew in 125. The render gate never bakes, so an older browser passes
    `--render` and then dies inside the probe with `root.getHTML is not a function` —
    which the export reports as a probe module it could not load, sending the reader
    to Leaf's own instrumentation rather than to the browser their host handed over.
    Asking the browser's age before the page is opened replaces that with one
    sentence naming the floor and the version.

    The old browser is a reading rather than an install, because what is under test
    is which sentence a host gets and every browser this suite can reach is younger
    than the floor. The suite's own is the control: a floor that refused it would
    turn every export in the corpus into that sentence, so the check that it does not
    is what keeps the refusal from being free."""

    class Old:
        version = "122.0.6261.128"

    with pytest.raises(
        SystemExit,
        match=r"v1\.html needs Chromium 125 or later to copy, and this browser is "
        r"122\.0\.6261\.128",
    ):
        exporting_model.export_page(Old(), "http://unused", tmp_path, "v1.html")

    assert browser_model.below_export_floor(browser) is None


def test_a_table_of_contents_keeps_native_links_in_a_static_copy(
    browser, serve, tmp_path
):
    """A table of contents is navigation rather than a live decision. Its generated
    links and targets stay in a standalone copy, where the browser can follow them
    without the runtime that supplied the smoother live-page journey."""
    source = leaf_page(
        "contents export",
        """
<h1>Migration plan</h1>
<lf-toc id="contents"></lf-toc>
<h2>Prepare</h2><p>Take a snapshot.</p>
<h2 style="margin-top: 110vh">Verify</h2><p>Compare the totals.</p>
""",
    )
    url = serve(source)
    out = tmp_path / "contents-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")
    links = page.get_by_role("navigation", name="On this page").get_by_role("link")
    expect(links).to_have_count(2)
    href = links.nth(1).get_attribute("href")
    assert href and href.startswith("#lf-contents-section-")

    links.nth(1).click()
    expect(page.locator(":target")).to_have_attribute("id", href[1:])
    assert page.locator("script").count() == 0
    assert errors == []
    page.close()


def test_a_gloss_keeps_its_explanation_in_static_media(browser, serve, tmp_path):
    """Hover is only the live page's presentation. Print and a standalone export have
    no script or pointer contract, so the author-written x-says tip becomes visible
    inline and its now-inert keyboard control leaves with the rest of the offers."""
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
    live.close()

    out = tmp_path / "gloss-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    copy = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(copy)
    copy.goto(out.as_uri(), wait_until="load")
    expect(copy.locator(".lf-gloss-popover")).to_be_visible()
    expect(copy.locator(".lf-gloss-mark")).to_have_count(0)
    expect(copy.locator("lf-gloss")).to_contain_text(
        "walking skeletonA thin path through the real system."
    )
    assert errors == []
    copy.close()


def test_an_export_drops_a_live_widget_work_claim(browser, serve, tmp_path):
    """A local receipt is live runtime chrome even though its seat is in the page.
    A standalone copy has no agent behind it, so preserving the rendered sentence
    would turn a provisional claim into a frozen lie."""
    work_page = leaf_page(
        "work export",
        """
<h1 id="h">Rollout</h1>
<lf-board id="rollout"><lf-column id="now" label="Now">
  <lf-card id="rollout-card"><strong>Ship the rollout</strong> Check the shard.</lf-card>
</lf-column></lf-board>
""",
    )
    url = serve(work_page)
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "status",
            str(serve.page_dir),
            "working",
            "checking the shard",
            "--on",
            "rollout-card",
        ],
    )
    assert result.exit_code == 0, result.output

    out = tmp_path / "work-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    page = browser.new_page()
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")

    expect(page.locator(".lf-receipt")).to_have_count(0)
    expect(page.locator("#rollout-card")).not_to_contain_text("checking the shard")
    assert errors == []
    page.close()


@pytest.mark.parametrize("resolved", [False, True], ids=["open", "resolved"])
def test_inline_threads_keep_their_words_without_live_controls_in_static_media(
    browser, serve, tmp_path, resolved
):
    """Copies keep native thread disclosure; paper shows even a closed thread."""
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
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep this check beside the changed line.",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "data_revision": 1,
            },
        },
    )
    if resolved:
        events_model.append_event(
            serve.page_dir,
            {"kind": "resolve", "author": "user", "parent": root["id"]},
        )
    selector = f'lf-diff .lf-conversation-thread[data-thread="{root["id"]}"]'
    live, live_errors = open_page(browser, url)
    thread = live.locator(selector)
    expect(thread).to_have_count(1)
    expect(thread.locator("button")).not_to_have_count(0)
    live.emulate_media(media="print")
    expect(thread.locator(".lf-conversation-body")).to_be_visible()
    assert (
        thread.locator("button:visible, textarea:visible, .lf-receipt:visible").count()
        == 0
    )
    assert live_errors == []
    live.close()

    out = tmp_path / "thread-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    copy = browser.new_page()
    errors = watched(copy)
    copy.goto(out.as_uri(), wait_until="load")
    thread = copy.locator(selector)
    expect(thread).to_have_count(1)
    expect(thread.locator("button, textarea, .lf-receipt")).to_have_count(0)
    expect(copy.locator("script, .lf-chrome, .lf-mark-note")).to_have_count(0)
    if resolved:
        expect(thread.locator(".lf-conversation-body")).to_be_hidden()
        thread.locator("summary").click()
    expect(thread.locator(".lf-conversation-body")).to_be_visible()
    expect(thread).to_contain_text("Keep this check beside the changed line.")
    if resolved:
        thread.locator("summary").click()
        expect(thread.locator(".lf-conversation-body")).to_be_hidden()
    copy.emulate_media(media="print")
    expect(thread.locator(".lf-conversation-body")).to_be_visible()
    assert errors == []
    copy.close()


RECEIPT_DRAFT = leaf_page(
    "draft",
    """
<h1 id="h">One note</h1>
<p id="p-open">The invitation still on its way.</p>
<lf-draft id="d-open"><pre>The sample workshop is in the blue room.</pre></lf-draft>
""",
)
OPEN_EDIT = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "d-open",
    "action": "edit",
    "detail": {"text": "The sample workshop is in the red room."},
    "meaning": {
        "document": {"kind": "page", "revision": 1},
        "coordinate": ["d-open", "d-open", "body"],
        "depends": ["d-open"],
        "answer": None,
    },
}


def test_a_copy_keeps_applied_widget_state_and_drops_live_handoff_status(
    browser, serve, tmp_path
):
    """The action projection is durable; its delivery report belongs only to the live
    session. A standalone file therefore carries the edited draft itself, not a second
    page-map record saying that the move happened or that an agent picked it up."""
    url = serve(RECEIPT_DRAFT, events=[OPEN_EDIT])
    in_flight = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("widget") == "d-open"
    ][-1]
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "pickup",
            "author": "page",
            "events": [in_flight["id"]],
            "phase": "opened",
            "session": None,
            "turn": None,
        },
    )

    live = browser.new_page(viewport={"width": 1200, "height": 900})
    live.goto(url, wait_until="load")
    resized(live, 1200, 900)
    expect(
        live.locator(
            "[data-lf-margin-for='d-open'] [data-lf-behavior='status']:visible"
        )
    ).to_have_attribute("data-lf-kinds", "pickup")
    expect(live.get_by_text("Outcome", exact=True)).to_have_count(0)
    live.close()

    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")

    expect(page.locator('[data-lf-behavior="status"]')).to_have_count(0)
    expect(page.get_by_text("Outcome", exact=True)).to_have_count(0)
    expect(page.locator("#d-open")).to_contain_text(
        "The sample workshop is in the red room."
    )
    assert errors == []
    page.close()


def test_an_export_keeps_the_non_fetch_policy(browser, serve, tmp_path):
    source = leaf_page(
        "Export CSP",
        """
<h1>Export CSP</h1>
<a id="relative" href="relative-target">Relative target</a>
<form id="escape" action="https://outside.invalid/collect" method="post">
  <input name="page-state" value="reader decision">
  <button type="submit">Send page state</button>
</form>
""",
        head='<base href="https://outside.invalid/rebased/">',
    )
    url = serve(source)
    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))

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
    try:
        page.goto(out.as_uri(), wait_until="load")
        page.wait_for_function("() => window.__cspViolations.includes('base-uri')")
        assert page.locator("#relative").evaluate("link => link.protocol") == "file:"
        page.locator("#escape").evaluate("form => form.requestSubmit()")
        page.wait_for_function("() => window.__cspViolations.includes('form-action')")
        assert escaped == []
    finally:
        page.close()


@pytest.mark.parametrize("page_fixture", PAGE_FIXTURES, ids=lambda p: p.stem)
def test_an_exported_page_fixture_stands_on_its_own(
    page_fixture, browser, serve, tmp_path
):
    """Every shipped example and the developer gallery is copied to a file and opened
    from disk. No server answers, so anything still reaching for one is a hole, and the
    console is where a hole says so. Every page fixture runs because what a copy loses
    is per-widget — the corpus alone would pass while a widget it lacks was broken.

    A copy over-promising is the other half of that, and it went unread for as long as
    there was nothing here asking. Tab into an exported decision page landed on a pick
    mark, which summoned the keyboard address for a key that answers nothing, into a row
    holding no column for it; a board's ten grips each opened a grab cursor; twenty
    options lit under a pointer that could not pick one. So the copy is asked what it
    still offers, in the three registers an offer is made in — a widget's chrome still
    holding a tab stop or a role, a control standing there with nothing left behind it,
    and a hand or a grab under the pointer — and every question is put to the markers
    rather than to any widget."""
    url = serve(page_fixture)
    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))

    page = browser.new_page(viewport={"width": 1200, "height": 900}, bypass_csp=True)
    errors = watched(page)
    page.on("requestfailed", lambda r: errors.append(f"unfetched {r.url}"))
    render_checks_model.prepare_standalone_probes(page)
    page.goto(out.as_uri(), wait_until="load")
    state = page.evaluate("""() => ({
        scripts: document.querySelectorAll('script').length,
        chrome: document.querySelectorAll('.lf-chrome').length,
        toServer: [...document.querySelectorAll('[src^="/"], [href^="/"]')]
            .map(e => e.getAttribute('src') ?? e.getAttribute('href')),
        links: document.querySelectorAll('link[rel="stylesheet"]').length,
        column: getComputedStyle(document.querySelector('main')).maxWidth,
        // A page gives up a CSS shell claim for what it hangs in the margin, and
        // a copy keeps only the strips whose residents came with it: a suggestion's
        // controls are gone from a file that can decide nothing, and its rail with them,
        // while sidenotes are the page's own words and stand in a copy exactly as they
        // stand on screen. So the reading is not that the column is centred — a page
        // carrying notes is deliberately not — but that no strip is held open for
        // nothing. Resolve the shell's custom-property lengths through a probe, then
        // ask whether anything is actually standing in each claimed band.
        //
        // The bands stand against the column's own edges and not against the page's.
        // A strip is what main gives up beside itself and the shift then re-centres
        // what is left, so on a window wider than the column plus its strips the
        // leftover room sits outside both — and a reading taken from body's edges
        // asks about that leftover instead, which is nobody's claim and always empty.
        //
        // And it is put to the residents that make the claim rather than to everything
        // under main. A widget asking for width is drawn past the column by design and
        // lands in the band beside it while claiming nothing, so a reading satisfied by
        // any overlap at all answered for a board or a diagram on three of the five
        // copies that hold a strip: the strip could have been held open for nothing and
        // the band still read as occupied. The claimants are the ones the cascade names
        // — aside.sidebar writes --strip-l, while aside.sidenote and the living
        // margin's items write --claim-note, --claim-rail, and --claim-map. A copy
        // carries no .lf-chrome, read above, and a project layer's own --lf-claim-right
        // furniture is outside the corpus this runs over.
        empty: ((main) => {
            const box = main.getBoundingClientRect();
            const length = (name) => {
                const probe = document.createElement('i');
                probe.style.cssText = `position:fixed;visibility:hidden;height:0;padding:0;border:0;width:var(${name})`;
                main.append(probe);
                const width = probe.getBoundingClientRect().width;
                probe.remove();
                return width;
            };
            const left = length('--strip-l'), right = length('--strip-r');
            const residents = 'aside.sidebar, aside.sidenote, .lf-margin-item';
            const held = (lo, hi) => hi - lo > 1
                && ![...document.querySelectorAll(residents)]
                .some(el => { const r = el.getBoundingClientRect();
                              return el.checkVisibility() && r.width > 1
                                     && r.left < hi - 1 && r.right > lo + 1; });
            return [
                held(box.left - left, box.left) && 'left',
                held(box.right, box.right + right) && 'right',
            ].filter(Boolean);
        })(document.querySelector('main')),
        unshown: [...document.querySelectorAll('main *')]
            .filter(el => el.textContent.trim() && !el.checkVisibility()
                          // A disclosure the reader can still work, a control's own
                          // label, a slot a standing decision deliberately retired, and
                          // an element with no box by design are all fine; what is not
                          // is the page's words with nothing to reveal them.
                          && !el.closest('details, [data-lf-offer], [data-lf-retired], '
                                         + '.lf-ui, style, script')
                          && getComputedStyle(el).display !== 'contents')
            .map(el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')),
        // A press a widget injected is a tab stop wearing an interactive role, and the
        // handler that answered both went with the scripts. Asked of the chrome marker
        // and of any role at all, never of a role by name: offer writes role="button"
        // and a widget keeping an ARIA pattern writes over it (lf-tabs' presses say
        // "tab"), so a list of roles here would be a list that stops at the ones it was
        // taught. The twelfth widget is covered by having used offer.
        //
        // The role a control the browser drives wears is the copy telling the truth —
        // lf-shot's label still flips its frames, its checkbox still takes the keyboard —
        // so the role half stands down for one of the platform's own controls. The tab
        // stop's half does not: offer writes that on presses of its own making and on
        // nothing else.
        pressable: [...document.querySelectorAll('[data-lf-offer][tabindex]'),
                    ...[...document.querySelectorAll('[data-lf-offer][role]')]
                        .filter(el => !el.querySelector(
                            'input, select, textarea, a[href], button'))]
            .map(el => el.className || el.tagName.toLowerCase()),
        // The claim a disarmed attribute leaves standing, since a control nothing can
        // work is still a control on the page. What a copy may show of a widget's
        // chrome is one the browser works itself and a label the page speaks through
        // (data-lf-said); the rest belonged to a runtime the file has not got, so a
        // mark reading "choose one" invites a reader who cannot answer it.
            inert: [...document.querySelectorAll('[data-lf-offer]:not([data-lf-said])')]
                .filter(el => el.checkVisibility() && el.textContent.trim()
                              && !el.matches(':has(input, select, textarea, a[href], button)')
                              // A label may name a native control outside its offered
                              // wrapper. `label.control` is the platform's resolved
                              // association, so this is just as live as a descendant.
                              && ![...el.querySelectorAll('label')]
                                  .some(label => label.control)
                              && !el.closest('label, summary, a[href]'))
            .map(el => (el.className || el.tagName.toLowerCase()) + ': '
                       + el.textContent.trim().replace(/\\s+/g, ' ').slice(0, 24)),
        // The same claim in paint. A hand or a grab says a gesture lands here, and in a
        // copy one lands nowhere the browser isn't the thing acting: a label's checkbox, a
        // link, a disclosure. The exemptions are the platform's own controls, so no
        // widget is named here either.
        offering: [...document.querySelectorAll('main *')]
            .filter(el => el.checkVisibility()
                          && ['pointer', 'grab'].includes(getComputedStyle(el).cursor)
                          && !el.closest('a[href], label, summary, input, select, textarea'))
            .map(el => el.tagName.toLowerCase() + '.'
                       + String(el.className?.baseVal ?? el.className ?? '')),
    })""")
    # The gate's own reading, on the medium that most needs it: a copy is laid out by
    # rules no other medium runs, and the last two ways one went out wrong were both a
    # widget's words landing on the page's.
    covered = render_checks_model.evaluate_probe(page, "coveredWords")
    assert render_checks_model.evaluate_probe(page, "coveredWords") == covered
    # The other direction of every question above: not what the copy still offers,
    # but what it under-delivers. BAKE is a remover, and until this ran the only
    # gates on it asked whether it removed enough — a wide diagram lost its scroll
    # stop in every copy, and no sweep read one. 420, because that is the width
    # where boxes start scrolling, and a scrolling box with no way in from the
    # keyboard is the exact class that slipped.
    resized(page, 420, 900)
    axe_violations, axe_report = serious_axe_violations(page)
    page.close()

    assert state["scripts"] == 0, "a copy with no server behind it keeps no script"
    assert state["chrome"] == 0, (
        "the runtime's layer came along — a comment box that swallows what you type"
    )
    assert state["toServer"] == [], "the copy still points at a server that isn't there"
    assert state["links"] == 0, "a stylesheet link survived, pointing at nothing"
    assert state["column"] != "none", "the theme didn't inline; the copy opens unstyled"
    assert state["empty"] == [], (
        "the copy holds a strip of its own width open with nothing standing in it, so "
        "the column sits off to one side of a page it has all of — a rail reserved for "
        f"something the file hasn't got: {state['empty']}"
    )
    assert state["unshown"] == [], (
        "the copy says less than the page did: content sitting behind a control that "
        f"needed a handler, and nothing in a file can press one — {state['unshown']}"
    )
    assert state["pressable"] == [], (
        "the copy offers a press nothing can take: Tab reaches it, a screen reader calls "
        f"it a button, and no handler is left to answer either — {state['pressable']}"
    )
    assert state["inert"] == [], (
        "the copy still shows a control the file has nothing to work with, which asks "
        f"the reader for something they cannot give: {state['inert']}"
    )
    assert state["offering"] == [], (
        "the copy draws a hand over a gesture it cannot take — the pointer promises "
        f"something the file has no script to do: {state['offering']}"
    )
    assert covered == [], f"the copy draws its own words over each other: {covered}"
    assert axe_violations == [], axe_report
    assert errors == [], f"{page_fixture.stem} needs a server to render: {errors}"


def test_a_copy_carries_a_workers_standing_report(browser, serve, tmp_path):
    """The copy is the page as replay left it, and a report is replay's other channel —
    none of the corpus can say so, because an example is one version with an empty log.

    The gap the wait covers is real and narrow: the first read starts beside widget
    startup, but the runtime can stamp `lf-upgraded` while that read is still unanswered,
    so the stamp export opens on is no promise that anything in the log has been painted.
    Ordinarily the answer is ready by then, which is why the page arrives painted however
    the wait is written and why the count being wrong stayed invisible. Refusing that
    first read is the whole difference — replay is left to the state reads on the far side of
    the stamp: the one the news stream prompts as it opens, and the 2s tick behind it,
    which is exactly where a loaded machine would have put it. Counting actions alone
    leaves nothing to wait for on a log holding one report, and the copy goes out blank.

    The refusal is served to export's own page rather than the copy's, through the
    stand-in `primed` supplies."""
    url = serve(REPORT_PAGE)
    sent = CliRunner().invoke(
        cli_model.cli,
        ["report", str(serve.page_dir), "t-parser", "status", "status=done"],
    )
    assert sent.exit_code == 0, sent.output

    def refuse_the_first_poll(page):
        polls = itertools.count()
        page.route(
            "**/api/state*",
            lambda route: refuse(route) if next(polls) == 0 else route.continue_(),
        )

    out = tmp_path / "standalone.html"
    out.write_text(
        exporting_model.export_page(
            primed(browser, refuse_the_first_poll), url, serve.page_dir, "v1.html"
        )
    )

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("#t-parser")).to_have_attribute("status", "done")
    expect(page.locator("#t-feeders > .lf-chips")).to_contain_text("2/2 done")
    page.close()


def test_a_copy_carries_none_of_the_exporters_own_window(browser, serve, tmp_path):
    """A live page measures the window it is in and states the numbers inline on the
    root: the room a wide widget may take, the width the margin strips are sized
    against, where each edge stands. An inline value outranks every rule a stylesheet
    could write, so a copy keeping one is laid out against the width the exporter's
    headless window happened to have, on a file whose whole point is being opened
    somewhere else.

    What separates those from the rail is not where they are written but whether the
    copy still has the thing they measure. The panel and the tray leave with the chrome;
    the room is a reading of a window nobody will open this file in. A suggestion's rail
    is the width of a control a decided change keeps, and
    `test_a_copy_keeps_the_rail_a_decided_change_left` is what says so — a sweep of every
    inline custom property on the root takes it and puts the exported board off the left
    of the page. So this asks for the named ones and asks the rail's own test for the
    rail.

    The live half is the non-vacuity: unless this page really states them, a copy that
    carries none says nothing at all."""
    url = serve(LONG_PAGE, comments=2)

    inline_custom = """() => {
        const inline = document.documentElement.style;
        const found = {};
        for (let i = 0; i < inline.length; i++)
            if (inline[i].startsWith('--'))
                found[inline[i]] = inline.getPropertyValue(inline[i]);
        return found;
    }"""
    session = ("--lf-panel-w", "--lf-tray-w")

    live = browser.new_page(viewport={"width": 1200, "height": 900})
    live.goto(url, wait_until="load")
    live.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    live.locator(".lf-threads-toggle").click()
    live.wait_for_timeout(600)
    measured = live.evaluate(inline_custom)
    live.close()
    stated = [name for name in session if name in measured]
    assert stated, (
        "the live page states none of the window measurements this is about "
        f"({measured}), so a copy carrying none of them proves nothing"
    )

    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    copy = browser.new_page()
    copy.goto(out.as_uri(), wait_until="load")
    carried = copy.evaluate(inline_custom)
    copy.close()

    assert not [name for name in session if name in carried], (
        "the copy is laid out against the exporter's own window rather than the "
        f"reader's: {carried}"
    )


def test_a_copy_wears_the_mark_and_claims_no_session(browser, serve, tmp_path):
    """A copy keeps the mark and drops the status painted on it. The live page was
    exported under a working claim — `page init` leaves one — so the tone it was wearing
    is a session that does not exist behind a file, which is the same lie the chrome is
    dropped for. Nothing else on the tab is worth losing over it: the mark still says
    which product wrote the file, and it is inlined, so it survives the copy leaving the
    machine that served it (test_an_exported_page_fixture_stands_on_its_own is what says no
    link here still points at a server)."""
    url = serve(LONG_PAGE)
    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    assert page.locator('link[rel="icon"]').count() == 1
    # The tone is a stylesheet the runtime appends to the mark, so what says the copy is
    # wearing none is the mark carrying only the one its file was written with.
    icon = page.evaluate("""() => {
        const el = document.querySelector('link[rel=icon]');
        const prefix = 'data:image/svg+xml,';
        const href = el.getAttribute('href');
        if (!href.startsWith(prefix)) return { inlined: false };
        const svg = new DOMParser()
            .parseFromString(decodeURIComponent(href.slice(prefix.length)), 'image/svg+xml')
            .documentElement;
        return {
            inlined: true,
            rest: el.getAttribute('data-lf-rest'),
            toned: svg.querySelectorAll('style').length,
            mark: Boolean(svg.querySelector('.lf-tone')),
        };
    }""")
    page.close()

    assert icon["inlined"], "the copy's tab icon is not a mark the file carries itself"
    assert icon["mark"], "the copy lost the mark rather than the status painted on it"
    assert icon["toned"] == 1, (
        "the copy's tab wears a tone it was exported under, claiming a session no file "
        f"has — {icon['toned']} stylesheets on a mark authored with one"
    )
    assert icon["rest"] is None, "the handover attribute rode along into the copy"
