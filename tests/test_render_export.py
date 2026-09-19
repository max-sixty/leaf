"""Standalone export tests."""

import argparse
import itertools
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import preview as preview_model
import pytest
from click.testing import CliRunner
from interact_support import install_payload, wait_for
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import files as files_model
from leaf import leases as leases_model
from leaf import media as media_model
from leaf import render_checks as render_checks_model
from leaf import server as server_model
from leaf import service as service_model
from leaf.render_gate import browser as browser_model
from leaf.render_gate.preview import preview_server
from leaf.structure import UTF8_BOM, SourceDocument
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect
from render_cases_interaction import (
    REPORT_PAGE,
)
from render_cases_layout import (
    serious_axe_violations,
)
from render_cases_widgets import (
    CUT_BOXES_PAGE,
)
from render_harness import (
    CORPUS_PAGE,
    CORPUS_SOURCES,
    LONG_PAGE,
    REPLAYED_PAGE,
    leaf_page,
    open_page,
    panel_settled,
    primed,
    refuse,
    resized,
    restarting,
    round_trip,
    sending,
    watched,
)

pytestmark = pytest.mark.nightly

ROOT = Path(__file__).parent.parent


@pytest.fixture
def preview_slot(tmp_path, monkeypatch):
    """A previews root of this test's own, and every slot in it gone when it ends.

    `LEAF_PREVIEWS_ROOT` puts the slots under `tmp_path` instead of the checkout's
    `.tmp/previews`, which every run in this checkout shares. That settles both
    directions at once: a run leaves nothing behind there — a slot is a page
    directory plus a background watcher's log, and at a few hundred entries
    `test_a_detached_preview_restarts_under_its_original_codex_claim` stops meeting
    its thirty-second reload — and a preview a developer has standing is not a page
    these tests find.

    The servers then go the way every other page's do, since
    `_no_page_outlives_its_test` walks `tmp_path` for them. A watcher does not: it
    is detached into a session of its own, so `spawn` does not reach it either.
    `retire_preview` does. It is the preview's own discard, holding the stop request
    the watcher reads and waiting for the lease, so a watcher that outlived its test
    is retired rather than having its page pulled out from under it. Whatever the
    test named its slots — `{slot}-reader`, `{slot}-before` — they are all in here.

    The root comes back from `previews_root` rather than being spelled twice, so
    the directory this discards is the one the script builds slots under.
    """
    monkeypatch.setenv("LEAF_PREVIEWS_ROOT", str(tmp_path / "previews"))
    root = preview_model.previews_root()
    slot = f"pytest-{os.getpid()}-{tmp_path.name}"
    yield slot, root / slot
    for page in sorted(root.iterdir()) if root.is_dir() else ():
        if page.is_dir():
            preview_model.retire_preview(page, discard=True)
    assert not (root.is_dir() and list(root.iterdir()))


def test_interrupting_a_live_preview_exits_without_a_traceback(preview_slot, spawn):
    """Ctrl-C retires the watcher and its server without a traceback or lost feedback."""
    slot, page = preview_slot
    preview = spawn(
        [
            sys.executable,
            str(ROOT / "scripts" / "preview.py"),
            "heat-loss",
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


def test_a_preview_source_uses_its_checkout_layer_and_media(tmp_path):
    """A comparison fixture carries the package and asset context of its checkout."""
    import preview

    examples = tmp_path / "baseline" / "examples"
    source = examples / "developer" / "comparison.html"
    source.parent.mkdir(parents=True)
    launcher = examples.parent / "bin" / "leaf"
    launcher.parent.mkdir()
    launcher.touch()
    source.write_text("<!doctype html>", encoding="utf-8")
    (examples / "layer.json").write_text('["diagram"]\n', encoding="utf-8")
    media = examples / "media"
    media.mkdir()

    assert preview.source_packages(source) == ["diagram"]
    assert preview.media_source(source) == media
    watched = preview.watch_paths(source, ROOT, [], {})
    assert str(examples / "layer.json") in watched.paths
    # The layer is told apart from the page's own inputs, because re-vendoring changes
    # what a revision is as executable code and editing the source does not.
    assert str(examples / "layer.json") not in watched.layer
    assert str(ROOT / "uv.lock") in watched.layer


def test_a_preview_asks_the_launcher_for_its_payload_root(tmp_path, monkeypatch):
    """The version interface is provenance; checkout validation retains its own flag."""
    import preview

    runtime = tmp_path / "runtime"
    launcher = runtime / "bin" / "leaf"
    launcher.parent.mkdir(parents=True)
    launcher.touch()
    calls = []

    def run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, stdout=f"{runtime}\n", stderr="")

    monkeypatch.setattr(preview.subprocess, "run", run)

    assert preview.checkout(argparse.ArgumentParser(), runtime) == (runtime, launcher)
    assert calls[0][0] == ([str(launcher), "--root"],)


def test_a_preview_subscribes_to_a_root_over_every_input_it_follows():
    """A path outside the subscribed roots is never reported, so it can never refresh.

    watchfiles watches each root recursively and names the path that changed; the
    watcher decides from that name alone. Any watched path the roots do not cover is
    therefore an input the preview silently stops following. The page directory is the
    other half: its own writes are a reader's feedback, and watching them would make
    every gesture a reload.
    """
    import preview
    from leaf.layer import layer_inputs

    source = ROOT / "examples" / "heat-loss.html"
    packages = json.loads((ROOT / "examples" / "layer.json").read_text())
    watched = preview.watch_paths(
        source,
        ROOT,
        layer_inputs(tuple(packages)),
        preview.fixture_seed(source),
    )

    assert watched.layer < watched.paths
    assert [
        path
        for path in sorted(watched.paths)
        if not any(
            Path(path) == root or root in Path(path).parents for root in watched.roots
        )
    ] == []
    assert [root for root in watched.roots if ".tmp" in root.parts] == []


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


def test_a_preview_reads_its_watched_inputs_from_the_files_that_exist_now(tmp_path):
    """Which set a reported path lands in is what decides whether the refresh vendors.

    The sets are read from the files as they now stand, so a module added since the
    last reading is layer, a file beside it that nothing vendors is neither, and a
    prior version of the source is the page's own.
    """
    import preview

    source = tmp_path / "examples" / "page.html"
    source.parent.mkdir()
    source.write_text("first", encoding="utf-8")
    runtime = tmp_path / "runtime"
    scripts = runtime / "skills" / "leaf" / "scripts" / "nested"
    scripts.mkdir(parents=True)
    existing_script = scripts / "existing.py"
    existing_script.write_text("first", encoding="utf-8")
    layer_root = tmp_path / "layer"
    widgets = layer_root / "widgets"
    widgets.mkdir(parents=True)

    def watched():
        return preview.watch_paths(source, runtime, [layer_root], {})

    subscription = watched().roots
    assert str(existing_script) in watched().layer
    assert str(source) in watched().paths
    assert str(source) not in watched().layer

    ignored = scripts / "README.md"
    ignored.write_text("ignored", encoding="utf-8")
    assert str(ignored) not in watched().paths

    added_script = scripts / "added.py"
    added_script.write_text("new", encoding="utf-8")
    assert str(added_script) in watched().layer

    added_script.unlink()
    assert str(added_script) not in watched().paths

    versions = source.parent / "versions"
    versions.mkdir()
    version = versions / "page.v1.html"
    version.write_text("version", encoding="utf-8")
    assert str(version) in watched().paths
    assert str(version) not in watched().layer

    widget = widgets / "lf-new.js"
    widget.write_text("export {};", encoding="utf-8")
    assert str(widget.resolve()) in watched().layer

    # None of those arrivals moved the subscription: each landed inside a directory
    # already watched recursively, so the open watcher kept collecting through them.
    assert watched().roots == subscription


def test_a_preview_follows_a_linked_package_wherever_its_files_resolve(tmp_path):
    """A package reached through a link is followed under the paths it resolves to.

    The layer reading answers in resolved paths, following a link at the package root
    and one inside it alike, while a watcher reports a change only under a directory it
    subscribed to, and can name it under the root string it was given. So each watched
    path has to be resolved, and has to sit under a subscribed root; a path that does
    not is an input the preview has silently stopped following.
    """
    import preview

    source = tmp_path / "pages" / "page.html"
    source.parent.mkdir()
    source.write_text("page", encoding="utf-8")
    package = tmp_path / "elsewhere" / "package"
    (package / "widgets").mkdir(parents=True)
    (package / "registry.json").write_text("{}", encoding="utf-8")
    module = package / "widgets" / "lf-linked.js"
    module.write_text("export {};", encoding="utf-8")
    linked = tmp_path / "links" / "package"
    linked.parent.mkdir()
    linked.symlink_to(package)
    dotted = source.parent / ".." / "elsewhere" / "package"
    # A package whose widgets directory is itself a link to a tree outside it.
    outside = tmp_path / "outside" / "widgets"
    outside.mkdir(parents=True)
    outside_module = outside / "lf-outside.js"
    outside_module.write_text("export {};", encoding="utf-8")
    nested = tmp_path / "nested" / "package"
    nested.mkdir(parents=True)
    (nested / "registry.json").write_text("{}", encoding="utf-8")
    (nested / "widgets").symlink_to(outside)

    for root, followed in (
        (linked, module),
        (dotted, module),
        (nested, outside_module),
    ):
        watched = preview.watch_paths(source, ROOT, [root], {})
        assert str(followed.resolve()) in watched.layer, root
        assert all(path == path.resolve() for path in watched.roots), watched.roots
        assert [
            path
            for path in sorted(watched.paths)
            if Path(path) != Path(path).resolve()
            or not any(
                Path(path) == subscribed or subscribed in Path(path).parents
                for subscribed in watched.roots
            )
        ] == [], (root, watched.roots)


def test_a_preview_follows_a_nearer_media_directory_when_one_appears(tmp_path):
    """The images move to the nearer directory while the subscription stands still.

    A subscription is fixed for its lifetime, and rebuilding one drops the changes
    its watcher has collected. The first file a page's `media/` ever holds arrives
    inside a directory already watched recursively, so the set does not move; when it
    did, the edit made while that refresh ran was lost.
    """
    import preview

    checkout = tmp_path / "checkout"
    source = checkout / "examples" / "developer" / "page.html"
    source.parent.mkdir(parents=True)
    source.write_text("page", encoding="utf-8")
    launcher = checkout / "bin" / "leaf"
    launcher.parent.mkdir()
    launcher.touch()
    manifest = checkout / "examples" / "layer.json"
    manifest.write_text("[]", encoding="utf-8")
    inherited_media = checkout / "examples" / "media"
    inherited_media.mkdir()
    inherited = inherited_media / "inherited.png"
    inherited.write_bytes(b"inherited")

    nearer_media = source.parent / "media"
    before = preview.watch_paths(source, checkout, [], {})
    assert str(inherited) in before.paths
    # The directory that does not exist yet is watched, so its arrival is a change.
    assert str(nearer_media) in before.paths

    nearer_media.mkdir()
    nearer = nearer_media / "nearer.png"
    nearer.write_bytes(b"nearer")
    after = preview.watch_paths(source, checkout, [], {})
    assert str(nearer) in after.paths
    assert str(inherited) not in after.paths
    assert after.roots == before.roots


def test_an_unrelated_ancestor_layer_does_not_change_an_external_source(tmp_path):
    import preview

    source = tmp_path / "project" / "docs" / "page.html"
    source.parent.mkdir(parents=True)
    source.touch()
    (source.parents[1] / "layer.json").write_text(
        '{"unrelated": true}\n', encoding="utf-8"
    )
    (source.parents[1] / "media").mkdir()

    assert preview.source_packages(source) == json.loads(
        (ROOT / "examples" / "layer.json").read_text()
    )
    assert preview.media_source(source) == source.parent / "media"


def test_named_live_previews_serve_one_source_in_independent_runtime_slots(
    browser, tmp_path, preview_slot
):
    """A developer can hold one fixture still while two vendored runtimes serve it.

    The named pages and their background services are the public evidence. If the
    script falls back to its single default directory, the second run stops and
    replaces the first; if it ignores the shared source, the planted heading is
    absent from one or both URLs.
    """
    source = tmp_path / "shared-preview.html"
    source.write_text(
        REPLAYED_PAGE.replace("Rollout", "Shared runtime comparison", 1),
        encoding="utf-8",
    )
    # Both slots sit in the fixture's own previews root, so its teardown discards them.
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
            watched(page)
            page.goto(url, wait_until="load")
            expect(page.locator(".lf-preview")).to_contain_text(
                f"Preview · {runtime.name}"
            )
            expect(
                page.get_by_role("heading", name="Shared runtime comparison")
            ).to_be_visible()
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
        REPLAYED_PAGE,
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
    assert "url" not in json.loads((page_dir / "preview.json").read_text())
    assert page_dir not in service_model.owned_pages(
        os.environ["CLAUDE_CODE_SESSION_ID"]
    )
    automation = open_page(browser, automation_url)
    expect(automation.locator(".lf-preview")).to_contain_text(
        f"Automation · {runtime.name}"
    )
    with sending(automation, "the automation option pick"):
        automation.locator("#opt-shim .lf-pick").click()
    expect(automation.locator("#opt-shim")).to_have_attribute("chosen", "")
    [automated_event] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "action" and event["author"] == "user"
    ]
    feedback = (page_dir / "events.jsonl").read_bytes()
    inode = (page_dir / "events.jsonl").stat().st_ino

    # A source edit takes down neither kind of server, so the temporary one an
    # automation slot holds keeps answering across it, exactly as the durable one does.
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "Rollout", "Automation follows source edits", 1
        ),
        encoding="utf-8",
    )
    expect(
        automation.get_by_role("heading", name="Automation follows source edits")
    ).to_be_visible(timeout=30000)
    expect(automation.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (page_dir / "events.jsonl").read_bytes().startswith(feedback)
    assert (page_dir / "events.jsonl").stat().st_ino == inode
    assert service_model.page_claim(page_dir) is None
    assert not (page_dir / "service.json").exists()
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
    reader = open_page(browser, reader_url)
    expect(reader.locator(".lf-preview")).to_contain_text(f"Preview · {runtime.name}")
    with sending(reader, "the reader option pick"):
        reader.locator("#opt-stage .lf-pick").click()
    expect(reader.locator("#opt-stage")).to_have_attribute("chosen", "")
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
    assert "--reset" in refused.stderr
    assert (reader_dir / "events.jsonl").read_bytes() == reader_feedback
    reader.close()

    reset_automation = spawn(
        [*reader_command, "--automation", "--reset"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert reset_automation.stdout.readline() == "prepared automation (1 version)\n"
    assert reset_automation.stdout.readline() == "\n"
    reset_url = reset_automation.stdout.readline().strip()
    assert reset_url.startswith("http://127.0.0.1:")
    assert (
        reset_automation.stderr.readline().strip()
        == "server   temporary (stops with this command)"
    )
    assert service_model.page_claim(reader_dir) is None
    assert reader_event not in events_model.read_events(reader_dir)

    reset_page = open_page(browser, reset_url)
    expect(reset_page.locator(".lf-preview")).to_contain_text(
        f"Automation · {runtime.name}"
    )
    expect(reset_page.locator("#opt-stage")).not_to_have_attribute("chosen", "")
    reset_page.close()

    reset_automation.send_signal(signal.SIGINT)
    _, reset_stderr = reset_automation.communicate(timeout=10)
    assert reset_automation.returncode == 130, reset_stderr
    assert "Traceback" not in reset_stderr


@pytest.fixture
def watched_preview(tmp_path, preview_slot):
    source = tmp_path / "watched.html"
    original = REPLAYED_PAGE
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
    source.write_text(REPLAYED_PAGE)
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
    wait_for(
        ready.exists,
        bool,
        failure="the detached preview command did not report its result",
        timeout=90,
    )
    result = json.loads(ready.read_text())
    assert result[0] == 0, result
    claim = service_model.page_claim(directory)
    assert claim["pid"] == owner.pid
    try:
        # A source edit re-vendors nothing, so it is stamped into the page the
        # reader is standing in and the service is never taken down. Every stop
        # and every start replaces service.json, so the inode it kept is the
        # reading that says the server the reader has is the one that was up.
        service = directory / "service.json"
        serving = service.stat().st_ino
        revised = source.read_text().replace("Rollout", "Detached revision")
        source.write_text(revised)
        log = directory.with_name(f"{directory.name}.preview.log")
        wait_for(
            log.read_text,
            lambda output: "Revised detached" in output,
            failure="the detached preview did not revise its source",
            timeout=30,
        )
        assert service.stat().st_ino == serving
        assert server_model.running_server(directory)
        assert service_model.page_claim(directory) == claim

        # SessionEnd can win while recompose waits for the page transaction. A
        # selection the source did not vendor is the edit that re-vendors, which
        # is the one update `page init` needs the service down for.
        with service_model.PageTransaction(directory) as transaction:
            (source.parent / "layer.json").write_text("[]", encoding="utf-8")
            wait_for(
                lambda: server_model.running_server(directory),
                lambda running: not running,
                failure="the re-vendor did not stop the service",
                timeout=30,
            )
            transaction.release_claim()
        wait_for(
            log.read_text,
            lambda output: "no longer owns" in output,
            failure="the detached preview did not report its lost claim",
            timeout=30,
        )
        assert server_model.running_server(directory) is None
        assert service_model.page_claim(directory)["released"] is not None
        lease, _ = preview_model.preview_locks(directory)
        wait_for(
            lambda: leases_model.lock_is_held(lease),
            lambda held: not held,
            failure="the released session left its watcher alive",
        )
        # The slot's own record outlives the watcher, so a later start resumes it.
        assert json.loads((directory / "preview.json").read_text())["source"] == str(
            source
        )
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
    page = open_page(browser, url)
    with sending(page, "the watched reader option pick"):
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

    # The rest are source edits, which re-vendor nothing and so never take the
    # server down. No `restarting` block covers them: the reader keeps the page
    # they are standing in, and anything the browser complains about across one
    # of these is a complaint this preview caused for real.
    service = (directory / "service.json").stat().st_ino
    revised = original.replace("Rollout", "A watched source revision", 1)
    source.write_text(revised, encoding="utf-8")
    expect(page.get_by_role("heading", name="A watched source revision")).to_be_visible(
        timeout=30000
    )
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)

    source.write_text("<p>invalid source</p>", encoding="utf-8")
    log_path = directory.with_name(f"{directory.name}.preview.log")
    wait_for(
        log_path.read_text,
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
    repeated = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False, timeout=30
    )
    assert repeated.returncode == 0, repeated.stdout + repeated.stderr
    assert repeated.stdout.splitlines()[-1] == url
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)
    assert (directory / "events.jsonl").stat().st_ino == inode
    # One server answered every one of those edits, as it does for a reader.
    assert (directory / "service.json").stat().st_ino == service


def test_resetting_a_preview_discards_reader_state_and_starts_it_fresh(
    browser, watched_preview
):
    """Reset replaces the selected preview instead of carrying its event log over."""
    source, _, directory, command, url = watched_preview
    page = open_page(browser, url)
    with sending(page, "the reader option pick before reset"):
        page.locator("#opt-shim .lf-pick").click()
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert b'"kind": "action"' in (directory / "events.jsonl").read_bytes()
    page.close()

    reset = subprocess.run(
        [*command, "--reset"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=90,
    )
    assert reset.returncode == 0, reset.stdout + reset.stderr
    assert (directory / "index.html").read_bytes() == source.read_bytes()
    assert b'"kind": "action"' not in (directory / "events.jsonl").read_bytes()

    fresh = open_page(browser, reset.stdout.splitlines()[-1])
    expect(fresh.locator("#opt-shim")).not_to_have_attribute("chosen", "")
    fresh.close()


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
        standing = open_page(browser, url)
        with sending(standing, "the standing reader option pick"):
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
    _, _, directory, _, url = watched_preview
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
    page.goto(url, wait_until="load")
    status = page.get_by_text("Leaf couldn't start. Waiting for the server to update.")
    expect(status).to_be_visible()
    expect(page.locator("body")).to_have_attribute(
        "data-lf-presented", "1", timeout=10000
    )
    assert len(probes) >= 2
    assert len(navigations) == 2
    expect(status).not_to_be_visible()


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
    with restarting(page):
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
    wait_for(
        lambda: (directory / "index.html").read_text(),
        lambda source: source == revised,
        failure="the source referencing new media was not stamped",
        timeout=30,
    )
    assert (directory / "media" / image.name).read_bytes() == expected

    image.write_bytes(b"changed bytes")
    log = directory.with_name(f"{directory.name}.preview.log")
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


def test_stopping_a_preview_waits_for_its_active_recompose(watched_preview, spawn):
    """Stop intent survives an update's own stopped-service interval and returns last."""
    source, runtime, directory, command, _ = watched_preview
    _, stop_request = preview_model.preview_locks(directory)
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
        while not leases_model.lock_is_held(stop_request):
            assert time.monotonic() < deadline, "stop did not record its intent"
            time.sleep(0.05)
        assert stopping.poll() is None
    stdout, stderr = stopping.communicate(timeout=30)
    assert stopping.returncode == 0, stdout + stderr
    assert server_model.running_server(directory) is None
    # The request is the stop command's own; nothing is left holding it afterwards.
    assert not leases_model.lock_is_held(stop_request)
    assert (directory / "events.jsonl").is_file()
    assert (directory / "index.html").read_bytes() == source.read_bytes()


# ---------- export: the page as one file ----------

OFFLINE_WIDGET = """\
import { LitElement, html, widgetController } from "/runtime/widget-api.js";

customElements.define("lf-offline-test", class extends LitElement {
  controller = widgetController(this);
  reading = this.controller.read();
  local = 0;
  stop = null;

  createRenderRoot() {
    return this.shadowRoot ?? this.attachShadow({mode: "open", serializable: true});
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
    const choice = this.reading.state.choice?.value ?? this.getAttribute("choice");
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
                "facet": "choice",
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
    """Offline mode omits conversation chrome without leaving its ticket pending."""
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
            "--interactive",
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output

    page = browser.new_page()
    watched(page)
    page.goto(interactive.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute(
        "data-lf-presented", "1", timeout=10000
    )
    expect(page.locator(".lf-chrome")).to_have_count(0)
    page.close()


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
            "--interactive",
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output
    assert "offline interactive" in result.output

    static = exporting_model.export_page(browser, url, serve.page_dir, "v1.html")
    assert "<script" not in static.lower()

    page = browser.new_page(viewport={"width": 1000, "height": 800})
    watched(page)
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
    assert page.locator("#offline-widget").evaluate(
        "owner => owner.shadowRoot.serializable"
    )
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
    page.close()


def test_interactive_export_hydrates_captured_data_fragments_offline(
    browser, serve, tmp_path
):
    """A frozen interactive copy keeps unopened fragmented payloads usable."""
    serve(
        leaf_page(
            "offline fragmented data",
            '<h1>Review</h1><lf-diff id="patch" source="review-patch" collapsed>'
            "<pre></pre></lf-diff>",
        )
    )
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", data_model.unified_diff_manifest(patch)
    )
    interactive = tmp_path / "fragmented-interactive.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "version",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive),
            "--interactive",
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output

    page = browser.new_page()
    watched(page)
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
    page.close()


@pytest.mark.parametrize(
    "stem",
    ["notification-playground", "data-explorer", "code-comparison"],
)
def test_playground_examples_keep_their_record_and_offline_interaction_modes(
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

    static_path = tmp_path / f"{stem}-record.html"
    static_path.write_text(
        exporting_model.export_page(browser, url, serve.page_dir, "v1.html"),
        encoding="utf-8",
    )
    live.close()

    record = browser.new_page(viewport={"width": 480, "height": 700})
    watched(record)
    record.goto(static_path.as_uri(), wait_until="load")
    expect(record.locator("script")).to_have_count(0)
    expect(record.locator("lf-playground").get_by_role("button")).to_have_count(0)
    expect(record.locator("lf-playground-output")).not_to_be_empty()
    if stem == "notification-playground":
        expect(record.locator(".notification-demo-card-banner")).to_have_count(4)
    elif stem == "data-explorer":
        expect(record.locator(".query-result-count")).to_have_text("1 matching release")
    else:
        expect(record.locator("lf-code.lf-rendered")).to_have_count(3)
        expect(record.locator("#code-comparison-instruction")).to_contain_text(
            "comfortable reading density"
        )
    assert record.evaluate("document.documentElement.scrollWidth") == 480
    record.emulate_media(media="print")
    expect(record.locator("lf-playground-output")).to_be_visible()
    record.close()

    interactive_path = tmp_path / f"{stem}-interactive.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "version",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive_path),
            "--interactive",
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output

    offline = browser.new_page(viewport={"width": 900, "height": 700})
    watched(offline)
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
        offline.locator('lf-playground-control[name="events"] input').fill("2")
        expect(offline.locator(".notification-demo-card-banner")).to_have_count(2)
    elif stem == "data-explorer":
        offline.get_by_role("button", name="Add filter").click()
        expect(offline.locator(".query-row")).to_have_count(3)
    else:
        offline.locator('lf-playground-control[name="width"] input').fill("420")
        expect(offline.locator('[data-candidate="A"]')).to_have_attribute(
            "style", re.compile(r"width: 420px")
        )
        expect(offline.locator('[data-candidate="B"]')).to_have_attribute(
            "style", re.compile(r"width: 420px")
        )
    assert external == []
    offline.close()


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
    watched(page)
    page.on(
        "requestfailed",
        lambda request: page.lf_errors.append(f"unfetched {request.url}"),
    )
    page.goto(out.as_uri(), wait_until="load")
    source = (ROOT / "examples" / "pr-walkthrough.html").read_text(encoding="utf-8")
    title = re.search(r"<h1>(.*?)</h1>", source, re.DOTALL).group(1).strip()
    expect(page.get_by_role("heading", name=title)).to_be_visible()
    assert page.evaluate("document.compatMode") == "CSS1Compat"
    assert page.locator("body").get_attribute("data-lf-reading") is None
    assert page.locator("script").count() == 0
    assert page.locator('link[rel="stylesheet"]').count() == 0
    assert page.locator("style").count() > 0


def test_exporting_an_example_leaves_the_live_preview_untouched(
    monkeypatch, page_dir, standing_server
):
    """A static handoff can be made while its interactive proof stays live."""
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
        match=r"v1\.html could not read its browser state or probe module",
    ):
        exporting_model.export_page(
            primed(browser, break_probe), root_url, serve.page_dir, "v1.html"
        )


def test_export_waits_for_a_current_presentation_opened_after_arrival(
    browser, serve, monkeypatch
):
    """The monotonic arrival latch cannot authorize a later half-drawn copy."""
    source = leaf_page(
        "current export readiness",
        '<h1>Current export readiness</h1><p id="export-reading">initial</p>',
    )

    def hold_later_presentation(page):
        page.add_init_script(
            """addEventListener('DOMContentLoaded', () => {
              const arm = async () => {
                if (
                  window.__lfExportPresentation ||
                  document.body.dataset.lfPresented !== '1'
                ) return;
                const entry = document.querySelector(
                  'script[data-lf-entry]'
                ).dataset.lfEntry;
                const {attachApplicationPresentation} = await import(
                  new URL(
                    'runtime/semantic-state.js',
                    new URL(entry, location.href),
                  ).href
                );
                const target = document.querySelector('#export-reading');
                const presentation = attachApplicationPresentation(
                  'test:export-current-readiness', target,
                );
                let settle;
                const completion = new Promise(resolve => { settle = resolve; });
                window.__lfExportPresentation = presentation;
                window.__lfReleaseExportPresentation = () => {
                  target.textContent = 'current';
                  settle();
                };
                void presentation.present('current', completion);
              };
              new MutationObserver(arm).observe(document.body, {
                attributes: true,
                attributeFilter: ['data-lf-presented'],
              });
              void arm();
            }, {once: true});"""
        )

    original_wait = render_checks_model.wait_for_probe
    probed = []

    def release_at_current_probe(page, name, *args):
        if name == "currentPresented":
            probed.append(name)
            page.wait_for_function(
                "() => Boolean(window.__lfReleaseExportPresentation)"
            )
            page.evaluate("() => window.__lfReleaseExportPresentation()")
        return original_wait(page, name, *args)

    monkeypatch.setattr(render_checks_model, "wait_for_probe", release_at_current_probe)
    exported = exporting_model.export_page(
        primed(browser, hold_later_presentation),
        serve(source),
        serve.page_dir,
        "v1.html",
    )

    assert probed == ["currentPresented"]
    assert '<p id="export-reading">current</p>' in exported


def test_export_waits_for_the_snapshot_the_browser_can_receive(
    browser, serve, monkeypatch
):
    """Later file writes cannot move readiness beyond a frozen preview."""
    serve(REPORT_PAGE)
    revision = files_model.latest_revision(serve.page_dir)
    assert revision is not None
    document = SourceDocument(
        files_model.revision_path(serve.page_dir, revision).read_text(encoding="utf-8")
    )
    monkeypatch.setattr(render_checks_model, "SERVED_TIMEOUT_MS", 1_000)

    with preview_server(serve.page_dir, document, revision, version=1) as url:
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "report",
                "author": "agent",
                "revision": revision,
                "text": "Arrived after the preview snapshot.",
            },
        )
        data_path = serve.page_dir / "data.json"
        later_data = json.loads(data_path.read_text(encoding="utf-8"))
        later_data["revision"] += 1
        data_path.write_text(json.dumps(later_data), encoding="utf-8")

        exported = exporting_model.export_page(browser, url, serve.page_dir, "v1.html")

    assert "The feeders" in exported
    assert exported.startswith(UTF8_BOM)


def test_export_state_route_follows_the_canonical_page_root(browser):
    """A multiplexed page keeps its capability prefix when export reads state."""
    page = browser.new_page()
    page.set_content(
        '<link rel="canonical" href="/p/page-capability/" data-lf-runtime>'
    )
    try:
        assert (
            exporting_model._state_url(
                page,
                "https://leaf.invalid/p/page-capability/versions/v2.html",
            )
            == "https://leaf.invalid/p/page-capability/api/state"
        )
    finally:
        page.close()


def test_export_state_route_refuses_a_missing_canonical_without_waiting():
    """An absent root is known from the locator count, without an attribute wait."""

    class MissingCanonical:
        def count(self):
            return 0

        def get_attribute(self, _name):
            pytest.fail("the absent canonical must not start an attribute wait")

    class Page:
        def locator(self, selector):
            assert selector == 'link[rel="canonical"][data-lf-runtime]'
            return MissingCanonical()

    with pytest.raises(PlaywrightError, match="document has no canonical page root"):
        exporting_model._state_url(Page(), "https://leaf.invalid/versions/v1.html")


def test_an_export_keeps_utf8_when_root_serialization_expands(browser, serve, tmp_path):
    source = leaf_page("Café handoff", "<h1>Café handoff</h1>").replace(
        '<html lang="en">', '<html data-padding="' + "&" * 300 + '">'
    )
    exported = exporting_model.export_page(
        browser, serve(source), serve.page_dir, "v1.html"
    )
    charset = exported.index('<meta charset="utf-8"')

    assert len(exported[:charset].encode()) > 1024
    assert exported.startswith(UTF8_BOM)

    out = tmp_path / "expanded-root.html"
    out.write_text(exported, encoding="utf-8")
    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    assert page.evaluate("document.characterSet") == "UTF-8"
    expect(page.get_by_role("heading", name="Café handoff")).to_be_visible()


def test_a_historical_export_embeds_its_captured_css_graph(browser, serve, tmp_path):
    """Nested imports and images come from the drawn revision, not mutable files."""
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
    url = serve(
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
    exported = exporting_model.export_page(browser, url, serve.page_dir, "v1.html")
    assert "--mutable-theme-only" not in exported
    assert "--mutable-chrome-only" not in exported
    out = tmp_path / "captured.html"
    out.write_text(exported, encoding="utf-8")
    page = browser.new_page()
    watched(page)
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    try:
        page.goto(out.as_uri(), wait_until="load")
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
        assert requests == [out.as_uri()]
    finally:
        page.close()


def test_export_refuses_a_rendered_asset_outside_the_page(browser, serve):
    source = leaf_page(
        "External rendered image",
        '<h1>External rendered image</h1><img id="external" alt="External evidence">',
        head="""<script type="module">
document.querySelector('#external').src = 'https://outside.invalid/evidence.svg';
</script>""",
    )
    url = serve(source)
    with pytest.raises(
        SystemExit,
        match="could not embed its captured assets: export resource is outside the page",
    ):
        exporting_model.export_page(browser, url, serve.page_dir, "v1.html")


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_an_exported_scroll_cue_follows_its_native_scroller(
    direction, browser, serve, tmp_path
):
    """A copy drops the runtime that updates live reach marks, but scrolling remains a
    native browser action. Its cue follows that scroll instead of freezing the edge the
    exporter's window happened to show."""
    source = CUT_BOXES_PAGE
    if direction == "rtl":
        source = source.replace(
            "</head>", "<style>html { direction: rtl; }</style></head>"
        )
    url = serve(source)
    out = tmp_path / "scroll-cue.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.emulate_media(reduced_motion="reduce")
    page.goto(out.as_uri(), wait_until="load")
    flow = page.locator("#flow")
    expect(flow).to_have_attribute("data-lf-copy-scroll", direction)
    expect(flow).not_to_have_attribute("data-lf-more-before", "")
    expect(flow).not_to_have_attribute("data-lf-more-after", "")

    def reading():
        return flow.evaluate(
            """el => {
            const style = getComputedStyle(el);
            return {
                position: Number(style.getPropertyValue('--lf-copy-scroll-position')),
                left: Number(style.getPropertyValue('--lf-copy-left-opacity')),
                right: Number(style.getPropertyValue('--lf-copy-right-opacity')),
                mask: style.maskImage,
            };
        }"""
        )

    start = reading()
    flow.evaluate(
        """(el, direction) => {
        const distance = (el.scrollWidth - el.clientWidth) / 2;
        el.scrollLeft = direction === 'rtl' ? -distance : distance;
    }""",
        direction,
    )
    page.wait_for_function(
        "el => Number(getComputedStyle(el).getPropertyValue('--lf-copy-scroll-position')) > .4",
        arg=flow.element_handle(),
    )
    middle = reading()
    flow.evaluate(
        "(el, direction) => { el.scrollLeft = direction === 'rtl' ? -el.scrollWidth : el.scrollWidth; }",
        direction,
    )
    page.wait_for_function(
        "el => Number(getComputedStyle(el).getPropertyValue('--lf-copy-scroll-position')) > .99",
        arg=flow.element_handle(),
    )
    end = reading()

    start_edges = (1, 0) if direction == "ltr" else (0, 1)
    end_edges = tuple(reversed(start_edges))
    assert start["position"] == 0, start
    assert (start["left"], start["right"]) == start_edges, start
    assert 0.4 < middle["position"] < 0.6, middle
    assert middle["left"] == 0 and middle["right"] == 0, middle
    assert end["position"] > 0.99, end
    assert (end["left"], end["right"]) == end_edges, end
    assert len({start["mask"], middle["mask"], end["mask"]}) == 3


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
    watched(page)
    page.goto(out.as_uri(), wait_until="load")
    links = page.get_by_role("navigation", name="On this page").get_by_role("link")
    expect(links).to_have_count(2)
    href = links.nth(1).get_attribute("href")
    assert href and href.startswith("#lf-contents-section-")

    links.nth(1).click()
    expect(page.locator(":target")).to_have_attribute("id", href[1:])
    assert page.locator("script").count() == 0


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
    watched(copy)
    copy.goto(out.as_uri(), wait_until="load")
    expect(copy.locator(".lf-gloss-popover")).to_be_visible()
    expect(copy.locator(".lf-gloss-mark")).to_have_count(0)
    expect(copy.locator("lf-gloss")).to_contain_text(
        "walking skeletonA thin path through the real system."
    )
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
    watched(page)
    page.goto(out.as_uri(), wait_until="load")

    expect(page.locator(".lf-receipt")).to_have_count(0)
    expect(page.locator("#rollout-card")).not_to_contain_text("checking the shard")


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
    live = open_page(browser, url)
    thread = live.locator(selector)
    expect(thread).to_have_count(1)
    expect(thread.locator("button")).not_to_have_count(0)
    live.emulate_media(media="print")
    expect(thread.locator(".lf-conversation-body")).to_be_visible()
    assert (
        thread.locator("button:visible, textarea:visible, .lf-receipt:visible").count()
        == 0
    )
    live.close()

    out = tmp_path / "thread-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    copy = browser.new_page()
    watched(copy)
    copy.goto(out.as_uri(), wait_until="load")
    thread = copy.locator(selector)
    expect(thread).to_have_count(1)
    expect(thread.locator("button, textarea, .lf-receipt")).to_have_count(0)
    expect(
        copy.locator("script, .lf-chrome, leaf-anchor-note, .lf-mark-note")
    ).to_have_count(0)
    if resolved:
        expect(thread.locator(".lf-conversation-body")).to_be_hidden()
        thread.locator("summary").click()
    expect(thread.locator(".lf-conversation-body")).to_be_visible()
    expect(thread).to_contain_text("Keep this check beside the changed line.")
    expect(thread.get_by_role("img", name="Review evidence")).to_have_js_property(
        "naturalWidth", 24
    )
    if resolved:
        thread.locator("summary").click()
        expect(thread.locator(".lf-conversation-body")).to_be_hidden()
    copy.emulate_media(media="print")
    expect(thread.locator(".lf-conversation-body")).to_be_visible()
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
    # A handoff colors the target's surviving semantic control rather than standing up
    # a second margin row of its own, so read the exact pencil the draft currently owns.
    edit = live.get_by_role("button", name="Edit d-open", exact=True)
    expect(edit).to_be_visible()
    expect(edit).to_have_attribute("data-lf-agent-workflow", "picked_up")
    expect(live.get_by_text("Outcome", exact=True)).to_have_count(0)
    live.close()

    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    page.goto(out.as_uri(), wait_until="load")

    expect(page.locator('[data-lf-behavior="status"]')).to_have_count(0)
    # Both seats a live handoff can speak from: the status row, and the phase on the
    # control that carries it.
    expect(page.locator("[data-lf-agent-workflow]")).to_have_count(0)
    expect(page.get_by_text("Outcome", exact=True)).to_have_count(0)
    expect(page.locator("#d-open")).to_contain_text(
        "The sample workshop is in the red room."
    )


def test_a_copy_speaks_reader_origin_after_live_map_is_removed(
    browser, serve, tmp_path
):
    """A standalone copy keeps the decision's origin after removing live chrome.

    Structural state such as a card move still differs from the authored version after
    export, so the retained origin attribute needs a local spoken word when Page Map is
    no longer present.
    """
    url = serve(REPLAYED_PAGE)
    live = open_page(browser, url)
    live.get_by_role("button", name="Move: Wire the importer — Doing").focus()
    live.keyboard.press("Enter")
    live.keyboard.press("ArrowRight")
    live.keyboard.press("Enter")
    expect(live.locator("#card-importer")).to_have_attribute(
        "data-lf-reader-override", "1"
    )
    live.close()

    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    page = browser.new_page()
    watched(page)
    page.goto(out.as_uri(), wait_until="load")
    card = page.locator("#card-importer")
    expect(card).to_have_attribute("data-lf-reader-override", "1")
    expect(card.locator(":scope > .lf-quiet")).to_have_text("your change")
    expect(page.locator(".lf-chrome")).to_have_count(0)


def test_a_copy_keeps_generated_native_controls_and_their_labels(
    browser, serve, tmp_path
):
    source = leaf_page(
        "Native controls in a copy",
        """
<h1>Native controls in a copy</h1>
<section id="native-controls">
  <p id="native-detail">The browser reveals this detail.</p>
</section>
<label>Review note <input name="review-note" value="Keep this note"></label>
""",
        head="""
<style>
  #native-detail { display: none; }
  #native-toggle:checked ~ #native-detail { display: block; }
</style>
<script type="module">
  import { offer } from '/runtime/widget-api.js';
  const root = document.querySelector('#native-controls');
  const wrapper = offer('div', 'native-label-wrapper');
  const label = offer('label', '', 'Show detail');
  label.htmlFor = 'native-toggle';
  wrapper.append(label);
  const input = offer('input', '', undefined, 'checkbox');
  input.id = label.htmlFor;
  root.prepend(wrapper, input, offer('button', '', 'Run scripted action'));
</script>
""",
    )
    url = serve(source)
    live = open_page(browser, url)
    expect(live.get_by_role("checkbox", name="Show detail")).to_be_visible()
    expect(live.get_by_role("button", name="Run scripted action")).to_be_visible()
    live.close()

    out = tmp_path / "native-controls-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    copy = browser.new_page()
    copy.goto(out.as_uri(), wait_until="load")
    expect(copy.get_by_role("button", name="Run scripted action")).to_have_count(0)
    expect(copy.locator("#native-detail")).to_be_hidden()
    copy.get_by_text("Show detail", exact=True).click()
    expect(copy.get_by_role("checkbox", name="Show detail")).to_be_checked()
    expect(copy.locator("#native-detail")).to_be_visible()
    copy.get_by_role("textbox", name="Review note").fill("Retained native input")
    expect(copy.get_by_role("textbox", name="Review note")).to_have_value(
        "Retained native input"
    )
    copy.close()


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


def test_the_exported_corpus_stands_on_its_own(browser, serve, tmp_path):
    """The composed page corpus is copied to a file and opened from disk. No server
    answers, so anything still reaching for one is a hole, and the console is where a
    hole says so. The generated corpus contains every authored fixture and widget; its
    outer tabs are revealed before the complete standalone document is read.

    A copy over-promising is the other half of that, and it went unread for as long as
    there was nothing here asking. Tab into an exported decision page landed on a pick
    mark, which summoned the binding badge for a key that answers nothing, into a row
    holding no column for it; a board's ten grips each opened a grab cursor; twenty
    options lit under a pointer that could not pick one. So the copy is asked what it
    still offers, in the three registers an offer is made in — a widget's chrome still
    holding a tab stop or a role, a control standing there with nothing left behind it,
    and a hand or a grab under the pointer — and every question is put to the markers
    rather than to any widget."""
    url = serve(CORPUS_PAGE)
    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))

    page = browser.new_page(viewport={"width": 1200, "height": 900}, bypass_csp=True)
    watched(page)
    page.on("requestfailed", lambda r: page.lf_errors.append(f"unfetched {r.url}"))
    render_checks_model.prepare_standalone_probes(page)
    page.goto(out.as_uri(), wait_until="load")
    outer_tabs = page.locator("#corpus > lf-tab")
    assert outer_tabs.count() == len(CORPUS_SOURCES), (
        "the generated corpus does not contain every authored source"
    )
    assert outer_tabs.evaluate_all(
        "tabs => { tabs.forEach(tab => tab.hidden = false); "
        "return tabs.every(tab => tab.checkVisibility()); }"
    ), "the complete exported corpus is not visible to the inspection"
    state = page.evaluate("""() => ({
        live: document.documentElement.hasAttribute('data-lf-live'),
        scripts: document.querySelectorAll('script').length,
        chrome: document.querySelectorAll('.lf-chrome').length,
        toServer: [...document.querySelectorAll('[src^="/"], [href^="/"]')]
            .map(e => e.getAttribute('src') ?? e.getAttribute('href')),
        links: document.querySelectorAll('link[rel="stylesheet"]').length,
        presented: document.body.dataset.lfPresented,
        themeMarker: getComputedStyle(document.querySelector('main'))
            .getPropertyValue('--lf-reading-column').trim(),
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
        // any overlap at all can answer for a board or a diagram while the strip is held
        // open for nothing. The claimants are the ones the cascade names
        // — aside.sidebar writes --strip-l, while aside.sidenote and the living
        // margin's items write --claim-note and --claim-rail. A copy
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
            const residents = 'aside.sidebar, aside.sidenote, .lf-margin-cluster';
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
                          // label, a slot a standing decision deliberately retired, a
                          // slot the markup itself hides, and an element with no box by
                          // design are all fine; what is not is the page's words with
                          // nothing to reveal them. A hidden slot is the author's own
                          // silence and it holds in every medium: the notification
                          // playground declares its artifact binding before the agent
                          // captures one, so the live page shows that slot no more than
                          // the copy does and the copy withholds nothing. Read against
                          // the corpus, this exempts that slot and nothing else.
                          && !el.closest('details, [data-lf-offer], [data-lf-retired], '
                                         + '[hidden], .lf-ui, style, script')
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
    # The other direction of every question above: not what the copy still offers,
    # but what it under-delivers. BAKE is a remover, and until this ran the only
    # gates on it asked whether it removed enough — a wide diagram lost its scroll
    # stop in every copy, and no sweep read one. 420, because that is the width
    # where boxes start scrolling, and a scrolling box with no way in from the
    # keyboard is the exact class that slipped.
    resized(page, 420, 900)
    axe_violations, axe_report = serious_axe_violations(page)
    page.close()

    assert not state["live"], "a copy kept the live server shell"
    assert state["scripts"] == 0, "a copy with no server behind it keeps no script"
    assert state["chrome"] == 0, (
        "the runtime's layer came along — a comment box that swallows what you type"
    )
    assert state["toServer"] == [], "the copy still points at a server that isn't there"
    assert state["links"] == 0, "a stylesheet link survived, pointing at nothing"
    assert state["presented"] == "1", "the copy was taken before presentation finished"
    assert state["themeMarker"] == "1", (
        "the theme didn't inline; the copy opens unstyled"
    )
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


def test_comparison_export_keeps_both_results_and_the_recorded_choice(
    browser, serve, tmp_path
):
    """A standalone comparison keeps both policy readings and their decision."""
    example = ROOT / "tests" / "fixtures" / "pages" / "current-proposed-comparison.html"
    url = serve(example)
    out = tmp_path / "comparison.html"
    out.write_text(
        exporting_model.export_page(browser, url, serve.page_dir, "comparison.html")
    )

    page = browser.new_page(viewport={"width": 760, "height": 900}, bypass_csp=True)
    watched(page)
    page.goto(out.as_uri(), wait_until="load")
    current = page.locator("#comparison-current")
    proposed = page.locator("#comparison-proposed")
    expect(current).to_contain_text("5")
    expect(proposed).to_contain_text("1")
    boxes = [
        current.evaluate("el => el.getBoundingClientRect().toJSON()"),
        proposed.evaluate("el => el.getBoundingClientRect().toJSON()"),
    ]
    assert boxes[0]["right"] <= boxes[1]["x"] + 1, boxes
    assert page.evaluate(
        "document.scrollingElement.scrollWidth === document.scrollingElement.clientWidth"
    )
    expect(page.locator("#comparison-policy")).to_contain_text(
        "Adopt one shared refresh per tab"
    )
    assert page.locator("script, .lf-chrome").count() == 0


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
    expect(page.locator("#t-parser > .lf-quiet")).to_contain_text("reported update")


def test_a_copy_carries_none_of_the_exporters_own_window(browser, serve, tmp_path):
    """A live page measures the window it is in and states the numbers inline on the
    root: the room a wide widget may take, the width the margin strips are sized
    against, where each edge stands. An inline value outranks every rule a stylesheet
    could write, so a copy keeping one is laid out against the width the exporter's
    headless window happened to have, on a file whose whole point is being opened
    somewhere else.

    What separates those from the rail is not where they are written but whether the
    copy still has the thing they measure. The panel and the tray leave with the chrome;
    the room is a reading of a window nobody will open this file in. The rail is the
    width of a margin contribution the copy still carries, and
    `test_a_copy_keeps_a_wide_widget_inside_its_standing_reaction_rail` is what says so —
    a sweep of every inline custom property on the root takes it and puts the exported
    board off the left of the page. So this asks for the named ones and asks the rail's
    own test for the rail.

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
    session = (
        "--lf-thread-panel-width",
        "--lf-tray-slot-width",
        "--lf-bottom-chrome-clear",
    )

    live = browser.new_page(viewport={"width": 1200, "height": 900})
    live.goto(url, wait_until="load")
    live.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    live.locator(".lf-threads-toggle").click()
    panel_settled(live)
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
    machine that served it (test_the_exported_corpus_stands_on_its_own is what says no
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


def test_a_copy_drops_live_element_projection_state(browser, serve, tmp_path):
    """The projection belongs to runtime chrome and must leave with that chrome."""
    source = leaf_page(
        "projected comment",
        '<h1>Review</h1><figure id="fig"><p>Annotated figure.</p></figure>',
    )
    url = serve(source)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Check this figure.",
            "anchor": {"section": "fig"},
        },
    )

    live = open_page(browser, url)
    figure = live.locator("#fig")
    expect(figure).to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(figure).to_have_class(re.compile(r"\blf-projected-mark\b"))
    live.close()

    out = tmp_path / "projected-comment.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    copy = browser.new_page()
    copy.goto(out.as_uri(), wait_until="load")
    expect(copy.locator("#fig")).not_to_have_class(
        re.compile(r"\blf-(?:mark-el|projected-mark)\b")
    )
    copy.close()
