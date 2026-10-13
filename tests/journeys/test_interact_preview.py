"""Preview input readings and the user handoff's harness connection.

`leaf-dev preview` resolves three things from wherever its source sits: the
package layer, the companion media and pinned assets, and the paths a watcher
subscribes to. Input tests exercise those readings and shared page preparation. The user
handoff crosses the real claim, server and delivery adapter boundaries, without
opening a browser.

That is why they are here and not beside the preview's browser tests. A `main`
mark is file-level, with no per-test escape, so a Python-decided reading filed
in a `main` module runs nowhere near the change that breaks it.
"""

import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    ROOT,
    STATED_TIMEOUT,
    consume_pending_input,
    fetch,
    fetch_hanging_up,
    record_claim,
    stamp,
    wait_for,
)
from leaf import cli as cli_model
from leaf import codex_adapter, hosting, leases, server, service, state
from leaf.harness import claim_harness
from leaf_dev import preview
from leaf_dev.page_fixtures import read_fixture
from model.test_interact_preview import _ScriptedChanges


# Archiving a chat moves its transcript away, which retires it the way deleting
# the transcript would.
@pytest.mark.parametrize("retirement", ["archive", "stop"])
def test_desktop_user_preview_survives_instance_unload_with_live_feedback(
    tmp_path, under_codex, codex_env, codex_queue, native_codex_chat, retirement
):
    """The command returns; unloading its chat keeps the watcher, URL and carrier.

    The copied Codex executable states the desktop ancestry. Its queue endpoint
    records delivery, while Leaf's detached watcher and HTTP service are real.
    """
    source = tmp_path / "review.html"
    source.write_text(
        "<!doctype html><html><head><title>Review</title></head><body>"
        '<main><h1>Review</h1><p id="candidate">Original candidate</p></main>'
        "</body></html>"
    )
    page = tmp_path / "previews" / "review"
    sid = "desktop-preview"
    transcript = native_codex_chat(sid)
    sibling = tmp_path / "sibling"
    task = under_codex(
        shlex.join(
            [
                sys.executable,
                "-m",
                "leaf_dev.preview",
                "--worker",
                "--user",
                "--source",
                str(source),
                "--runtime",
                str(ROOT),
                "--slot",
                page.name,
            ]
        ),
        codex_env
        | codex_queue
        | {
            "CODEX_THREAD_ID": sid,
            "LEAF_PREVIEWS_ROOT": str(page.parent),
        },
        app_server=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        output, errors = task.communicate(timeout=STATED_TIMEOUT)
        assert task.returncode == 0, f"{output}{errors}"
        url = next(line for line in output.splitlines() if line.startswith("http://"))
        acquired = service.page_claim(page)["acquisition"]
        before = state.session_record(sid)
        old = time.time() - timedelta(hours=12).total_seconds()
        claim_path = service.claim_path(page)
        claim = json.loads(claim_path.read_text())
        claim["ts"] = datetime.fromtimestamp(old).astimezone().isoformat()
        state.write_json(claim_path, claim)
        for entry in page.iterdir():
            os.utime(entry, (old, old))
        assert service.claim_is_active(service.page_claim(page))
        # Allow the real watchdog's orphan window to pass without any HTTP
        # request renewing page files; aged ownership must keep its listener.
        time.sleep(2)
        assert server.running_server(page)["url"] == url
        if retirement != "stop":
            shutil.copytree(
                page, sibling, ignore=shutil.ignore_patterns("service.json")
            )
            sibling_claim = record_claim(sibling, id=sid, harness="codex", chat=True)
            hosting.start_server(sibling, harness=claim_harness(sibling_claim))
        ended = subprocess.run(
            [*LEAF_COMMAND, "session-end"],
            check=False,
            input=json.dumps({"hook_event_name": "SessionEnd", "session_id": sid}),
            env=codex_env,
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
        )
        assert ended.returncode == 0, ended.stderr
        assert state.session_record(sid)["generation"] == before["generation"]
        assert state.hook_needed({"hook_event_name": "PostToolUse", "session_id": sid})
        assert leases.lock_is_held(preview.preview_lease(page))
        assert server.running_server(page)["url"] == url

        source.write_text(
            source.read_text().replace("Original candidate", "Revised candidate")
        )
        wait_for(
            lambda: (page / "index.html").read_text(),
            lambda text: "Revised candidate" in text,
            failure="the detached preview did not follow its source after unload",
        )
        endpoint = urlsplit(url)._replace(path="/api/event").geturl()
        status, body = fetch(
            endpoint,
            data=json.dumps(
                {
                    "kind": "comment",
                    "revision": 1,
                    "text": "Please revise this candidate",
                    "attempt": "desktop-after-unload",
                }
            ).encode(),
            token=None,
        )
        assert status == 200, body
        queued = Path(codex_queue["PREVIEW_QUEUE_RECORD"])
        wait_for(queued.exists, bool, failure="feedback after unload was not queued")
        assert json.loads(queued.read_text())[:4] == [
            "queue",
            "--thread",
            sid,
            "--message",
        ]
        assert service.page_claim(page)["acquisition"] == acquired
        if retirement == "archive":
            archived = transcript.parent.parent / "archived_sessions"
            archived.mkdir()
            transcript.rename(archived / transcript.name)
        else:
            hosting.cmd_stop(page)
        for served in [page, *([sibling] if sibling.exists() else [])]:
            wait_for(
                lambda served=served: server.running_server(served),
                lambda running: not running,
                failure=f"chat {retirement} left its page server running",
            )
        wait_for(
            lambda: leases.lock_is_held(preview.preview_lease(page)),
            lambda held: not held,
            failure=f"chat {retirement} left its preview watcher running",
        )
        wait_for(
            lambda: codex_adapter.adapter_is_live(sid),
            lambda live: not live,
            failure=f"chat {retirement} kept its delivery adapter",
        )
    finally:
        if (page / "events.jsonl").exists():
            hosting.cmd_stop(page)
            state.end_session(sid)
            wait_for(
                lambda: leases.lock_is_held(preview.preview_lease(page)),
                lambda held: not held,
                failure="the explicitly stopped detached preview kept watching",
            )
        if sibling.exists():
            hosting.cmd_stop(sibling)


def test_abandoned_desktop_preview_publishes_no_claim(
    tmp_path, spawn, under_codex, codex_env, native_codex_chat
):
    """Abandoning preview readiness retires its service, watcher, and acquisition."""
    source = tmp_path / "review.html"
    source.write_text(
        "<!doctype html><html><head><title>Review</title></head>"
        "<body><main><h1>Review</h1></main></body></html>"
    )
    page = tmp_path / "previews" / "review"
    native_codex_chat("abandoned-desktop")
    env = codex_env | {
        "CODEX_THREAD_ID": "abandoned-desktop",
        "LEAF_PREVIEWS_ROOT": str(page.parent),
    }
    preparing = under_codex(
        shlex.join(
            [
                sys.executable,
                "-c",
                (
                    "import json, sys; from pathlib import Path; "
                    "from leaf.harness import session_harness; "
                    "from leaf.service import prepare_claim; "
                    "print(json.dumps(prepare_claim(session_harness(), Path(sys.argv[1]))))"
                ),
                str(page),
            ]
        ),
        env,
        app_server=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output, errors = preparing.communicate(timeout=STATED_TIMEOUT)
    assert preparing.returncode == 0, f"{output}{errors}"
    intent = json.loads(output)
    caller, child = socket.socketpair()
    task = spawn(
        [
            sys.executable,
            "-m",
            "leaf_dev.preview",
            "--worker",
            "--user",
            "--source",
            str(source),
            "--runtime",
            str(ROOT),
            "--slot",
            page.name,
            "--prepared-claim",
            json.dumps(intent),
            "--handshake",
            str(child.fileno()),
        ],
        env=env,
        pass_fds=(child.fileno(),),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child.close()
    caller.settimeout(STATED_TIMEOUT)
    try:
        with caller.makefile("rb") as announced:
            ready = json.loads(announced.readline())
        assert "url" in ready, ready
        assert fetch(ready["url"])[0] == 200
    finally:
        caller.close()
        output, errors = task.communicate(timeout=STATED_TIMEOUT)
    assert task.returncode == 0, f"{output}{errors}"
    assert service.page_claim(page) is None
    assert server.running_server(page) is None
    assert not leases.lock_is_held(preview.preview_lease(page))


def test_preview_publishes_companion_edits_at_its_existing_url(
    tmp_path, monkeypatch, capsys
):
    """A custom widget edit publishes exact inputs without erasing feedback.

    Scripted input batches carry real companion edits through the running preview,
    its ordinary stamp door and HTTP delivery. Earlier executable resources retain
    their bytes, and a competing preview edit is refused until reconciled.
    """
    from leaf.files import latest_revision, revision_path

    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head>"
        '<body><main><h1>Reading</h1><lf-reading id="reading"></lf-reading>'
        "</main></body></html>"
    )
    (tmp_path / "layer.json").write_text("[]")
    companions = source.with_suffix(".page")
    widgets = companions / "widgets"
    widgets.mkdir(parents=True)
    (companions / "registry.json").write_text(
        json.dumps(
            {
                "lf-reading": {
                    "description": "A reading",
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                    "additionalProperties": False,
                    "x-content": "empty",
                    "x-upgrade": True,
                }
            }
        )
    )
    widget = widgets / "lf-reading.js"
    original = b"export const reading = 'Original';"
    revised = b"export const reading = 'Revised';"
    widget.write_bytes(original)
    page = tmp_path / "preview"

    def changes(watched):
        assert str(widget) in watched.paths
        url = next(
            line
            for line in capsys.readouterr().out.splitlines()
            if line.startswith("http://")
        )

        def at(path):
            return fetch(urlsplit(url)._replace(path=path).geturl(), token=None)

        def resource(revision):
            return (
                "/revisions/"
                + revision_path(page, revision).stem
                + "/page/widgets/lf-reading.js"
            )

        first = latest_revision(page)
        old_resource = resource(first)
        assert at(old_resource) == (200, original)
        status, body = fetch(
            urlsplit(url)._replace(path="/api/event").geturl(),
            token=None,
            data=json.dumps(
                {
                    "kind": "comment",
                    "revision": first,
                    "text": "Keep this feedback",
                    "attempt": "preview-companion",
                }
            ).encode(),
        )
        assert status == 200, body
        before = (page / "events.jsonl").read_bytes()
        widget.write_bytes(revised)
        yield {str(widget)}
        second = latest_revision(page)
        assert second > first
        assert at("/")[0] == 200
        assert at(resource(second)) == (200, revised)
        assert at(old_resource) == (200, original)
        assert (page / "events.jsonl").read_bytes().startswith(before)

        delivered = page / "page/widgets/lf-reading.js"
        delivered.write_text("export const reading = 'Preview edit';")
        widget.write_text("export const reading = 'Another source edit';")
        yield {str(widget)}
        assert latest_revision(page) == second
        assert "Preview edit" in delivered.read_text()
        assert "reconcile" in capsys.readouterr().err

        delivered.write_bytes(revised)
        yield {str(widget)}
        assert latest_revision(page) > second
        assert "Another source edit" in delivered.read_text()

        # Removing a dependency is not published while the widget still imports it.
        helper = companions / "value.js"
        helper.write_text("export const value = 'Dependency';")
        widget.write_text("export { value } from '../value.js';")
        yield {str(widget), str(helper)}
        last = latest_revision(page)
        helper.unlink()
        yield {str(helper)}
        assert latest_revision(page) == last
        assert (page / "page/value.js").is_file()
        widget.write_bytes(revised)
        yield {str(widget)}
        assert latest_revision(page) > last
        assert not (page / "page/value.js").exists()
        assert at(old_resource) == (200, original)

        # A module can replace a directory of modules without stale empty folders.
        group = companions / "components.js"
        group.mkdir()
        (group / "value.js").write_text("export const value = 'Grouped';")
        widget.write_text("export { value } from '../components.js/value.js';")
        yield {str(widget), str(group / "value.js")}
        grouped = latest_revision(page)
        (group / "value.js").unlink()
        group.rmdir()
        group.write_text("export const value = 'Single';")
        widget.write_text("export { value } from '../components.js';")
        yield {str(widget), str(group)}
        assert latest_revision(page) > grouped
        assert (page / "page/components.js").is_file()

    monkeypatch.setattr(
        preview,
        "watch_changes",
        lambda watched: _ScriptedChanges(changes(watched), watched),
    )
    with pytest.raises(StopIteration):
        preview.serve_preview(source, page, ROOT / "bin/leaf", ROOT, False)


def test_preview_filters_feedback_before_discovering_inputs(tmp_path, monkeypatch):
    """Page-side writes must not rediscover the whole installed layer."""
    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head>"
        "<body><main><h1>Reading</h1></main></body></html>"
    )
    page = tmp_path / "preview"
    readings = []
    original = preview.watch_paths

    def read_inputs(*args):
        watched = original(*args)
        readings.append(watched)
        return watched

    def changes(_watched):
        count = len(readings)
        for name in ("interactions.jsonl", "user-views.json", "viewed.json"):
            yield {str(page / name)}
            assert len(readings) == count
        source.write_text(source.read_text().replace("Reading</h1>", "Revised</h1>"))
        yield {str(source)}
        assert "Revised</h1>" in (page / "index.html").read_text()

    monkeypatch.setattr(preview, "watch_paths", read_inputs)
    monkeypatch.setattr(
        preview,
        "watch_changes",
        lambda watched: _ScriptedChanges(changes(watched), watched),
    )
    with pytest.raises(StopIteration):
        preview.serve_preview(source, page, ROOT / "bin/leaf", ROOT, False)


def test_preview_refreshes_replaced_inputs_even_without_a_native_file_batch(
    tmp_path, monkeypatch
):
    """Files can change while the old root watch is revoked before rearming."""
    directory = tmp_path / "source"
    directory.mkdir()
    source = directory / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head>"
        "<body><main><h1>Original</h1></main></body></html>"
    )
    page = tmp_path / "preview"
    batches = []

    def replaced_input(_changes):
        if not batches:
            original = source.read_text()
            shutil.rmtree(directory)
            directory.mkdir()
            source.write_text(original.replace("Original</h1>", "Revised</h1>"))
            batches.append(True)
            return set()  # Only the bounded lifetime wake survives the replacement.
        assert "Revised</h1>" in (page / "index.html").read_text()
        raise StopIteration

    monkeypatch.setattr(preview.PreviewChanges, "__next__", replaced_input)
    with pytest.raises(StopIteration):
        preview.serve_preview(source, page, ROOT / "bin/leaf", ROOT, False)


def test_preview_tracks_committed_layer_across_refused_source_edits(
    tmp_path, monkeypatch
):
    """Real preparation, vendoring and revision publication consume scripted events.

    The scripted filesystem stream batches real edits without relying on timing.
    A committed layer survives a later source refusal without being re-vendored on
    retry. Fixture-history edits do not block a concurrent layer update.
    """
    import os

    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head>"
        '<body><main><h1>Reading</h1><p id="reading">Original</p></main></body></html>'
    )
    seed = source.with_suffix(".jsonl")
    seed.write_text("")
    package = tmp_path / "package"
    package.mkdir()
    (package / "registry.json").write_text("{}")
    theme = package / "theme.css"
    theme.write_text(":root { --proof: 1; }")
    (tmp_path / "layer.json").write_text(
        json.dumps(["./" + os.path.relpath(package, ROOT)])
    )
    page = tmp_path / "preview"

    def changes(_watched):
        def layer():
            return json.loads((page / "registry.json").read_text())["$layer"]

        before = layer()
        theme.write_bytes(theme.read_bytes())
        yield {str(theme)}
        assert layer()["generation"] == before["generation"]

        original = source.read_text()
        theme.write_text(":root { --proof: 2; }")
        source.write_text(
            original.replace("</main>", "<lf-undefined></lf-undefined></main>")
        )
        yield {str(theme), str(source)}
        committed = layer()
        assert committed["generation"] != before["generation"]
        assert (page / "index.html").read_text() == original

        source.write_bytes(source.read_bytes())
        yield {str(source)}
        assert layer()["generation"] == committed["generation"]

        theme.unlink()
        seed.write_text("\n")
        yield {str(theme), str(seed)}
        removed = layer()
        assert removed["generation"] != committed["generation"]

        seed.write_text("")
        source.write_text(original.replace("Original", "Revised"))
        yield {str(seed), str(source)}
        after = layer()
        assert after["generation"] == removed["generation"]
        assert after["fingerprint"] != committed["fingerprint"]
        assert "Revised" in (page / "index.html").read_text()

    monkeypatch.setattr(
        preview,
        "watch_changes",
        lambda watched: _ScriptedChanges(changes(watched), watched),
    )
    with pytest.raises(StopIteration):
        preview.serve_preview(source, page, ROOT / "bin/leaf", ROOT, False)


def test_preview_follows_a_committed_package_after_a_source_refusal(
    tmp_path, monkeypatch
):
    """A failed source edit cannot hide edits to its newly installed package."""
    import os

    source = tmp_path / "pages/reading.html"
    source.parent.mkdir()
    original = (
        "<!doctype html><html><head><title>Reading</title></head>"
        "<body><main><h1>Reading</h1></main></body></html>"
    )
    source.write_text(original)
    manifest = source.parent / "layer.json"
    manifest.write_text("[]")
    package = tmp_path / "elsewhere/package"
    package.mkdir(parents=True)
    (package / "registry.json").write_text("{}")
    theme = package / "theme.css"
    theme.write_text(":root { --package-proof: 1; }")
    selection = "./" + os.path.relpath(package, ROOT)
    page = tmp_path / "preview"
    subscriptions = []

    def changes(watched):
        subscriptions.append(watched)
        if len(subscriptions) == 1:
            assert str(theme) not in watched.paths
            manifest.write_text(json.dumps([selection]))
            source.write_text(
                original.replace("</main>", "<lf-undefined></lf-undefined></main>")
            )
            yield {str(manifest), str(source)}
            pytest.fail("Committed package did not rebuild the watch subscription")
        else:
            installed = json.loads((page / "registry.json").read_text())["$layer"]
            assert installed["packages"] == [selection]
            assert (page / "index.html").read_text() == original
            assert str(theme) in watched.paths
            assert any(
                root == package or root in package.parents for root in watched.roots
            )
            theme.write_text(":root { --package-proof: 2; }")
            yield {str(theme)}
            after = json.loads((page / "registry.json").read_text())["$layer"]
            assert after["generation"] != installed["generation"]
            assert "--package-proof: 2" in (page / "theme.css").read_text()

    monkeypatch.setattr(
        preview,
        "watch_changes",
        lambda watched: _ScriptedChanges(changes(watched), watched),
    )
    with pytest.raises(StopIteration):
        preview.serve_preview(source, page, ROOT / "bin/leaf", ROOT, False)
    assert len(subscriptions) == 2


def test_serving_preserves_a_direct_codex_wait(
    codex_claimed_page, under_codex, codex_env, codex_queue
):
    """An active direct watcher keeps its lease instead of being replaced.

    The queue is deliberately unavailable: a successful handoff must use the
    real wait already watching this task. Stop still keeps that turn open.
    """
    page = codex_claimed_page
    stamp(page)
    program = """
import json, subprocess, sys, time
from pathlib import Path
from leaf.leases import wait_is_live, adapter_is_live
from leaf.service import PageTransaction, claim_page
from leaf.session import cmd_waiting
page = Path(sys.argv[1])
claim_page(page)
cmd_waiting(page, "Review this page")
watch = subprocess.Popen([sys.executable, "-m", "leaf", "wait", str(page)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
try:
    deadline = time.monotonic() + 30
    while not wait_is_live(page, "codex-thread"):
        assert watch.poll() is None, watch.communicate()
        assert time.monotonic() < deadline, "the direct wait never took its lease"
        time.sleep(0.01)
    for command in ("start", "run"):
        served = subprocess.run([sys.executable, "-m", "leaf", "server", command, str(page)],
                                capture_output=True, text=True)
        assert served.returncode == 0, served.stderr
        assert json.loads(served.stdout)["url"]
        assert watch.poll() is None
        assert not adapter_is_live("codex-thread")
    stopped = subprocess.run([sys.executable, "-m", "leaf", "hook", "--harness", "codex"],
                             input=json.dumps({"hook_event_name": "Stop", "session_id": "codex-thread"}),
                             capture_output=True, text=True)
    assert stopped.returncode == 0, stopped.stderr
    reason = json.loads(stopped.stdout)["reason"]
    assert "leaf wait" in reason and "no delivery adapter" not in reason
finally:
    with PageTransaction(page) as held:
        held.set_status("idle", "")
    output, errors = watch.communicate(timeout=30)
    assert watch.returncode == 2, (output, errors)
"""
    task = under_codex(
        shlex.join([sys.executable, "-c", program, str(page)]),
        codex_env
        | codex_queue
        | {"CODEX_THREAD_ID": "codex-thread", "PREVIEW_QUEUE_AVAILABLE": "False"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output, errors = task.communicate(timeout=STATED_TIMEOUT)
    assert task.returncode == 0, f"{output}{errors}"


def test_user_preview_restart_keeps_feedback_and_authored_progress(
    tmp_path, spawn, monkeypatch
):
    """A user slot resumes its durable page rather than replaying its fixture."""
    from leaf.data import read_data
    from leaf.event_log import read_events
    from leaf.files import latest_revision, revision_path
    from leaf.harness import session_harness
    from leaf.registry.storage import load_registry

    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head><body><main>"
        '<h1>Initial reading</h1><lf-text-document id="receipt" source="receipt"></lf-text-document>'
        '<lf-options id="route" choose><lf-option id="first">First</lf-option>'
        '<lf-option id="second">Second</lf-option></lf-options></main></body></html>'
    )
    source.with_suffix(".data.json").write_text('{"receipt":"Original value"}')
    package = tmp_path / "package"
    package.mkdir()
    (package / "registry.json").write_text("{}")
    theme = package / "theme.css"
    theme.write_text(":root { --proof: 1; }")
    (tmp_path / "layer.json").write_text(
        json.dumps(["default", "./" + os.path.relpath(package, ROOT)])
    )
    monkeypatch.setenv("LEAF_PREVIEWS_ROOT", str(tmp_path / "previews"))
    page = tmp_path / "previews" / "reading-user"
    valid_initial = source.read_text()
    source.write_text(
        valid_initial.replace("</main>", "<lf-undefined></lf-undefined></main>")
    )
    refused = subprocess.run(
        ["uv", "run", "leaf-dev", "preview", "--user", "--source", str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode != 0 and "unknown widget" in refused.stderr
    assert not page.exists()
    source.write_text(valid_initial)

    def start(number):
        log = tmp_path / f"preview-{number}.log"
        with log.open("w") as stream:
            task = spawn(
                ["uv", "run", "leaf-dev", "preview", "--user", "--source", str(source)],
                stdout=stream,
                stderr=subprocess.STDOUT,
            )

        def announced():
            assert task.poll() is None, log.read_text()
            return next(
                (
                    line
                    for line in log.read_text().splitlines()
                    if line.startswith("http://")
                ),
                None,
            )

        url = wait_for(
            announced,
            bool,
            failure=log.read_text,
            timeout=hosting.PORT_WAIT_SECONDS + STATED_TIMEOUT,
        )
        status, body = fetch_hanging_up(url)
        assert status == 200, body
        return task, url, log

    def stop(task):
        task.terminate()
        task.wait(timeout=STATED_TIMEOUT)

    task, url, _ = start(1)
    endpoint = urlsplit(url)._replace(path="/api/event").geturl()
    for entry in (
        {
            "kind": "comment",
            "revision": 1,
            "text": "Keep this feedback",
            "attempt": "restart-comment-0001",
        },
        {
            "kind": "action",
            "revision": 1,
            "widget": "route",
            "action": "choose",
            "detail": {"value": ["second"]},
            "attempt": "restart-choice-0001",
        },
    ):
        status, body = fetch_hanging_up(endpoint, json.dumps(entry).encode())
        assert status == 200, body
    payload = consume_pending_input(session_harness().session)
    comment = next(
        event for event in payload["batches"][0]["events"] if event["kind"] == "comment"
    )
    reply = CliRunner().invoke(
        cli_model.cli,
        [
            "response",
            "reply",
            "--done",
            comment["answer"]["ref"],
            "--text",
            "Preserved reply",
        ],
    )
    assert reply.exit_code == 0, reply.output
    status, body = fetch_hanging_up(
        endpoint,
        json.dumps(
            {
                "kind": "comment",
                "revision": 1,
                "text": "Still pending across restart",
                "attempt": "restart-pending-0001",
            }
        ).encode(),
    )
    assert status == 200, body
    pending = read_events(page)[-1]["id"]
    before = (page / "events.jsonl").read_bytes()
    cursor = (page / "cursor.json").read_bytes()
    data = read_data(page, load_registry(page))
    first = latest_revision(page)
    layer = load_registry(page)["$layer"]["generation"]
    media = page / "media" / "retained.svg"
    media.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    media_bytes = media.read_bytes()
    stop(task)
    task, resumed, _ = start(2)
    assert resumed == url
    assert (page / "events.jsonl").read_bytes().startswith(before)
    assert (page / "cursor.json").read_bytes() == cursor
    assert read_data(page, load_registry(page)) == data
    assert latest_revision(page) == first
    assert any(event.get("text") == "Preserved reply" for event in read_events(page))
    delivered = consume_pending_input(session_harness().session)
    assert any(
        event["id"] == pending
        for batch in delivered["batches"]
        for event in batch["events"]
    )
    before = (page / "events.jsonl").read_bytes()
    cursor = (page / "cursor.json").read_bytes()
    stop(task)

    # A restart updates authored and runtime inputs, but never replays new seeds
    # over the existing log or changes data the page already holds.
    fictional = next(event for event in read_events(page) if event["kind"] == "comment")
    fictional |= {"id": "fictional", "text": "A different fictional seed"}
    source.with_suffix(".jsonl").write_text(json.dumps(fictional) + "\n")
    source.with_suffix(".data.json").write_text('{"receipt":"Replacement seed"}')
    source.write_text(source.read_text().replace("Initial reading", "Revised reading"))
    theme.write_text(":root { --proof: 2; }")
    task, resumed, _ = start(3)
    assert resumed == url
    assert (page / "events.jsonl").read_bytes().startswith(before)
    assert all(event["id"] != "fictional" for event in read_events(page))
    assert (page / "cursor.json").read_bytes() == cursor
    assert read_data(page, load_registry(page)) == data
    assert latest_revision(page) > first
    assert revision_path(page, first).is_file()
    assert load_registry(page)["$layer"]["generation"] != layer
    assert media.read_bytes() == media_bytes
    assert "Revised reading" in fetch_hanging_up(resumed)[1].decode()
    stop(task)

    # A rejected authored update leaves the old publication and its feedback live.
    valid_source = source.read_text()
    source.write_text(
        valid_source.replace("</main>", "<lf-undefined></lf-undefined></main>")
    )
    task, resumed, log = start(4)
    assert "Preview update refused" in log.read_text()
    assert "lf-undefined" not in (page / "index.html").read_text()
    assert (page / "events.jsonl").read_bytes().startswith(before)
    stop(task)
    source.write_text(valid_source)

    # Fixture progress is not the page's authority: the agent's own revision
    # survives an unchanged fixture and a runtime update while the watcher is away.
    agent_source = (
        (page / "index.html").read_text().replace("Revised reading", "Agent revision")
    )
    (page / "index.html").write_text(agent_source)
    stamped = CliRunner().invoke(
        cli_model.cli, ["page", "stamp", str(page), "--text", "Agent revision"]
    )
    assert stamped.exit_code == 0, stamped.output
    agent_revision = latest_revision(page)
    theme.write_text(":root { --proof: 3; }")
    task, resumed, _ = start(5)
    assert (page / "index.html").read_text() == agent_source
    assert revision_path(page, agent_revision).is_file()
    agent_revision = latest_revision(page)
    stop(task)

    # When both authors changed their inputs, restarting refuses the fixture's
    # overwrite and continues serving the agent's committed revision.
    source.write_text(valid_source.replace("Revised reading", "Competing fixture"))
    task, resumed, log = start(6)
    assert "reconcile" in log.read_text()
    assert (page / "index.html").read_text() == agent_source
    assert latest_revision(page) == agent_revision
    assert "Agent revision" in fetch_hanging_up(resumed)[1].decode()
    stop(task)

    # Reconciliation to the already-published page consumes the fixture update
    # without trying to stamp the same immutable revision again.
    source.write_text(agent_source)
    task, _, log = start(7)
    assert "Preview update refused" not in log.read_text()
    assert latest_revision(page) == agent_revision
    assert (page / "events.jsonl").read_bytes().startswith(before)
    stop(task)


@pytest.mark.parametrize("failure", ["prepare", "publish"])
@pytest.mark.parametrize("claimed", [False, True])
def test_fresh_preview_preparation_cannot_remove_a_successor(
    tmp_path, monkeypatch, failure, claimed
):
    """A complete private fixture can fail or lose its slot without owning it."""
    from leaf.harness import IDENTITY_VARIABLES

    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head>"
        "<body><main><h1>Reading</h1></main></body></html>"
    )
    (tmp_path / "layer.json").write_text("[]")
    page = tmp_path / "preview"
    successor = preview.PreviewService(page, user=True)
    prepare = preview.prepare_page
    held = {}

    def prepare_before_successor(*args, **kwargs):
        result = prepare(*args, **kwargs)
        with monkeypatch.context() as context:
            if not claimed:
                for name in IDENTITY_VARIABLES:
                    context.delenv(name, raising=False)
            prepare(
                page,
                read_fixture(source),
                partial(preview.leaf, ROOT / "bin/leaf", ROOT),
            )
            with successor.starting() as url:
                held["url"] = url
            held["claim"] = service.page_claim(page)
            held["log"] = (page / "events.jsonl").read_bytes()
        if failure == "prepare":
            raise ValueError("fixture preparation refused")
        return result

    monkeypatch.setattr(preview, "prepare_page", prepare_before_successor)
    try:
        with pytest.raises(ValueError if failure == "prepare" else OSError):
            preview.run_preview(source, page, ROOT / "bin/leaf", ROOT, True)
        assert service.page_claim(page) == held["claim"]
        assert (page / "events.jsonl").read_bytes() == held["log"]
        assert server.running_server(page)["url"] == held["url"]
        assert fetch(held["url"], token=None)[0] == 200
    finally:
        successor.stop()


def test_serving_adopts_existing_pages_and_joins_one_codex_delivery(
    codex_claimed_page, tmp_path, under_codex, codex_env, codex_queue
):
    """A revived handoff connects once, including a reused foreground server.

    The first server already exists with no adapter. Two public starts and a
    foreground reuse must retain one adapter and leave Stop nothing to repair.
    """
    first = codex_claimed_page
    second = tmp_path / "sibling"
    shutil.copytree(first, second)
    (second / "service.json").unlink()
    ready, done = tmp_path / "ready.json", tmp_path / "done"
    program = """
import json, subprocess, sys, time
from pathlib import Path
from leaf.hosting import cmd_stop
from leaf.leases import adapter_lease_path
from leaf.state import end_session, write_json
pages = list(map(Path, sys.argv[1:3]))
ready, done = map(Path, sys.argv[3:])
lease = adapter_lease_path("codex-thread")
try:
    identities = []
    for command, page in (("start", pages[0]), ("start", pages[1]), ("run", pages[0])):
        result = subprocess.run(
            [sys.executable, "-m", "leaf", "server", command, str(page)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["url"]
        identities.append(lease.stat().st_ino)
    stopped = subprocess.run(
        [sys.executable, "-m", "leaf", "hook", "--harness", "codex"],
        input=json.dumps({"hook_event_name": "Stop", "session_id": "codex-thread"}),
        capture_output=True, text=True,
    )
    assert stopped.returncode == 0, stopped.stderr
    assert not stopped.stdout, stopped.stdout
    write_json(ready, identities)
    while not done.exists():
        time.sleep(0.01)
finally:
    for page in pages:
        cmd_stop(page)
    end_session("codex-thread")
"""
    task = under_codex(
        shlex.join(
            [
                sys.executable,
                "-c",
                program,
                str(first),
                str(second),
                str(ready),
                str(done),
            ]
        ),
        codex_env | codex_queue | {"CODEX_THREAD_ID": "codex-thread"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for(
            ready.exists,
            bool,
            failure="the shared delivery handoff did not finish",
        )
        assert len(set(json.loads(ready.read_text()))) == 1
        assert leases.wait_is_live(first, "codex-thread")
        assert leases.wait_is_live(second, "codex-thread")
        assert codex_adapter.adapter_is_live("codex-thread")
    finally:
        done.touch()
        output, errors = task.communicate(timeout=STATED_TIMEOUT)
    assert task.returncode == 0, f"{output}{errors}"
