"""Preview input readings and the user handoff's harness connection.

`leaf-dev preview` resolves three things from wherever its source sits: the
package layer, the media directory, and the set of paths a watcher subscribes
to. Input tests state a directory tree and ask for those pure readings. The user
handoff crosses the real claim, server and delivery adapter boundaries, without
opening a browser.

That is why they are here and not beside the preview's browser tests. A nightly
mark is file-level, with no per-test escape, so a Python-decided reading filed
in a nightly module runs nowhere near the change that breaks it.
"""

import json
import shlex
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from conftest import LEAF_COMMAND
from interact_support import ROOT, fetch, stamp, wait_for
from leaf import codex_adapter, leases, server, service, session
from leaf_dev import preview


def test_a_preview_source_uses_its_checkout_layer_and_media(tmp_path):
    """A comparison fixture carries the package and asset context of its checkout."""

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


def test_a_preview_subscribes_to_a_root_over_every_input_it_follows():
    """A path outside the subscribed roots is never reported, so it can never refresh.

    watchfiles watches each root recursively and names the path that changed; the
    watcher decides from that name alone. Any watched path the roots do not cover is
    therefore an input the preview silently stops following. The page directory is the
    other half: its own writes are a user's feedback, and watching them would make
    every gesture a reload.
    """
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
    # The example images are a pinned copy under `.tmp`, so their pin stands in.
    assert str(ROOT / "leaf-assets.json") in watched.paths


def test_a_preview_reads_its_watched_inputs_from_the_files_that_exist_now(tmp_path):
    """Which set a reported path lands in is what decides whether the refresh vendors.

    The sets are read from the files as they now stand, so a module added since the
    last reading is layer, a file beside it that nothing vendors is neither, and a
    prior version of the source is the page's own.
    """

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


@pytest.mark.parametrize("delivery_available", [True, False, "missing"])
@pytest.mark.parametrize("handoff", ["preview", "start", "run"])
@pytest.mark.parametrize("initially_idle", [False, True])
def test_serving_connects_codex_feedback_before_handing_over_its_url(
    page_dir,
    tmp_path,
    under_codex,
    codex_env,
    codex_queue,
    delivery_available,
    handoff,
    initially_idle,
):
    """HTTP feedback reaches the current task without a second `codex start`.

    The detached adapter, claim and page server are real. Only the external Codex
    CLI is replaced: its queue boundary acknowledges and records the submitted
    task and delivery pointer instead of starting a model turn.
    """
    stamp(page_dir)
    if initially_idle:
        session.cmd_status(page_dir, "idle", "")
    queued = Path(codex_queue["PREVIEW_QUEUE_RECORD"])
    ready = tmp_path / "ready.json"
    done = tmp_path / "done"
    program = """
import json
import subprocess
import sys
import time
from pathlib import Path
from leaf.service import PageTransaction, page_claim
from leaf.state import write_json
from leaf.harness import session_harness
from leaf.hosting import cmd_stop
from leaf_dev.preview import PreviewService

page, ready, done = map(Path, sys.argv[1:4])
handoff = sys.argv[4]
preview = PreviewService(page, True)
foreground = None
try:
    if handoff == "preview":
        started = preview.start()
        # Joining the current carrier preserves the preview's acquisition.
        session_harness().ensure_delivery()
        assert page_claim(page)["acquisition"] == preview.claim["acquisition"]
        assert not preview.ended
    elif handoff == "start":
        result = subprocess.run(
            [sys.executable, "-m", "leaf", "server", "start", str(page)],
            capture_output=True, text=True,
        )
        if result.returncode:
            sys.exit(result.stderr)
        started = (json.loads(result.stdout)["url"], result.stderr)
    else:
        foreground = subprocess.Popen(
            [sys.executable, "-m", "leaf", "server", "run", str(page)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        line = foreground.stdout.readline()
        if not line:
            output, errors = foreground.communicate(timeout=30)
            sys.exit(errors)
        started = (json.loads(line)["url"], "")
    write_json(ready, started)
    while not done.exists():
        time.sleep(0.01)
finally:
    if handoff == "preview":
        preview.stop()
    else:
        cmd_stop(page)
    if foreground is not None:
        foreground.communicate(timeout=30)
    if ready.exists():
        with PageTransaction(page) as transaction:
            transaction.release_claim()
"""
    delivery_env = (
        codex_env
        | codex_queue
        | {
            "CODEX_THREAD_ID": "preview-thread",
            "PREVIEW_QUEUE_AVAILABLE": str(delivery_available),
        }
    )
    if delivery_available == "missing":
        delivery_env["PATH"] = str(tmp_path / "no-codex")
    task = under_codex(
        shlex.join(
            [
                sys.executable,
                "-c",
                program,
                str(page_dir),
                str(ready),
                str(done),
                handoff,
            ]
        ),
        delivery_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if delivery_available is not True:
        output, errors = task.communicate(timeout=60)
        assert task.returncode != 0, f"{output}{errors}"
        expected = (
            "cannot find the `codex` executable"
            if delivery_available == "missing"
            else "queue unsupported"
        )
        assert expected in errors
        if handoff != "preview":
            assert "Traceback" not in errors
        assert not ready.exists()
        assert service.page_claim(page_dir) is None
        assert server.running_server(page_dir) is None
        assert not codex_adapter.adapter_is_live("preview-thread")
        return
    try:
        wait_for(
            ready.exists,
            bool,
            failure="the user preview never handed over its URL",
            timeout=60,
        )
        url, _ = json.loads(ready.read_text())
        claim = service.page_claim(page_dir)
        assert claim["id"] == "preview-thread"
        assert claim["pid"] == task.pid, (
            "detached child replaced its launching harness lifetime"
        )
        assert codex_adapter.adapter_is_live("preview-thread")
        if initially_idle:
            assert service.read_status(page_dir)["state"] == "idle"
            session.cmd_status(page_dir, "waiting", "Review this page")
        endpoint = urlsplit(url)._replace(path="/api/event").geturl()
        status, body = fetch(
            endpoint,
            data=json.dumps(
                {
                    "kind": "comment",
                    "revision": 1,
                    "text": "Please revise this candidate",
                    "attempt": "preview_feedback",
                }
            ).encode(),
            token=None,
        )
        assert status == 200, body
        wait_for(
            queued.exists,
            bool,
            failure="the preview's feedback did not reach Codex",
        )
        arguments = json.loads(queued.read_text())
        assert arguments[:4] == ["queue", "--thread", "preview-thread", "--message"]
        assert 'operation="delivery read"' in arguments[-1]
    finally:
        done.touch()
        output, errors = task.communicate(timeout=15)
    assert task.returncode == 0, f"{output}{errors}"
    wait_for(
        lambda: codex_adapter.adapter_is_live("preview-thread"),
        lambda live: not live,
        failure="the task's delivery carrier outlived its preview",
    )


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
from leaf.session import cmd_status
page = Path(sys.argv[1])
cmd_status(page, "waiting", "Review this page")
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
    stopped = subprocess.run([sys.executable, "-m", "leaf", "hook"],
                             input=json.dumps({"hook_event_name": "Stop", "session_id": "codex-thread"}),
                             capture_output=True, text=True)
    assert stopped.returncode == 0, stopped.stderr
    reason = json.loads(stopped.stdout)["reason"]
    assert "leaf wait" in reason and "no delivery adapter" not in reason
finally:
    cmd_status(page, "idle", "")
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
    output, errors = task.communicate(timeout=60)
    assert task.returncode == 0, f"{output}{errors}"


def test_an_abandoned_handoff_does_not_disable_the_server_it_reuses(
    codex_claimed_page, spawn, codex_env
):
    """Dropping a reused server's real handshake withdraws no existing service."""
    page = codex_claimed_page
    before = server.running_server(page)
    caller, child = socket.socketpair()
    task = spawn(
        [
            *LEAF_COMMAND,
            "server",
            "_serve",
            str(page),
            "--handshake",
            str(child.fileno()),
        ],
        env=codex_env | {"CODEX_THREAD_ID": "codex-thread"},
        pass_fds=(child.fileno(),),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child.close()
    caller.settimeout(30)
    try:
        with caller.makefile("rb") as announced:
            assert json.loads(announced.readline())["url"] == before["url"]
    finally:
        caller.close()
    output, errors = task.communicate(timeout=60)
    assert task.returncode == 0, f"{output}{errors}"
    assert server.running_server(page) == before


def test_serving_adopts_existing_pages_and_joins_one_codex_delivery(
    codex_claimed_page, tmp_path, under_codex, codex_env, codex_queue
):
    """A revived handoff connects once, including a reused foreground server.

    The first server already exists with no carrier. Two public starts and a
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
from leaf.service import PageTransaction
from leaf.state import write_json
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
        [sys.executable, "-m", "leaf", "hook"],
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
        with PageTransaction(page) as transaction:
            transaction.release_claim()
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
            timeout=60,
        )
        assert len(set(json.loads(ready.read_text()))) == 1
        assert leases.wait_is_live(first, "codex-thread")
        assert leases.wait_is_live(second, "codex-thread")
        assert codex_adapter.adapter_is_live("codex-thread")
    finally:
        done.touch()
        output, errors = task.communicate(timeout=15)
    assert task.returncode == 0, f"{output}{errors}"


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
@pytest.mark.parametrize("handoff", ["preview", "start", "run"])
def test_failed_delivery_preserves_the_existing_preview(
    page_dir, monkeypatch, failure, handoff
):
    """Failure before acceptance preserves both listener and original watcher."""
    from leaf.harness import session_harness
    from leaf.hosting import claim_and_start, cmd_serve, cmd_stop
    from leaf.server import running_server
    from leaf.service import page_claim

    original = preview.PreviewService(page_dir, user=True)
    url, _ = original.start()
    claim = page_claim(page_dir)
    published = json.loads((page_dir / "service.json").read_text())
    successor = preview.PreviewService(page_dir, user=True)

    def refuse(_harness):
        assert page_claim(page_dir) == claim
        assert not original.ended
        raise failure("delivery refused")

    monkeypatch.setattr(type(session_harness()), "ensure_delivery", refuse)
    try:
        with pytest.raises(failure, match="delivery refused"):
            if handoff == "preview":
                successor.start()
            elif handoff == "start":
                with claim_and_start(page_dir):
                    pass
            else:
                cmd_serve(page_dir, acquire=True)
        assert page_claim(page_dir) == claim
        assert not original.ended
        assert json.loads((page_dir / "service.json").read_text()) == published
        assert running_server(page_dir)["url"] == url
        assert fetch(url)[0] == 200
    finally:
        cmd_stop(page_dir)


@pytest.mark.parametrize("refusal", ["bind", "layer", "cancel"])
def test_failed_serving_preparation_never_publishes_a_takeover(
    page_dir, monkeypatch, refusal
):
    from leaf.detached import StartRefused
    from leaf.hosting import claim_and_start, cmd_stop
    from leaf.service import page_claim

    original = preview.PreviewService(page_dir, user=True)
    original.start()
    claim = page_claim(page_dir)
    cmd_stop(page_dir)
    # Keep the original watcher/claim, with its server down. Its next revival is
    # independent of a failed takeover's private preparation.
    record = json.loads((page_dir / "service.json").read_text())
    record["enabled"] = True
    (page_dir / "service.json").write_text(json.dumps(record))
    occupied = socket.socket()
    if refusal == "bind":
        occupied.bind((record["bind"], record["port"]))
        occupied.listen()
    elif refusal == "layer":
        from interact_support import vendored_by_another_leaf

        vendored_by_another_leaf(page_dir)
    else:
        from leaf import detached

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
        occupied.close()
        cmd_stop(page_dir)


@pytest.mark.parametrize("transferred", [False, True])
def test_a_preview_captures_acquisition_before_an_accepted_commit_is_interrupted(
    page_dir, monkeypatch, transferred
):
    from leaf import detached
    from leaf.hosting import cmd_stop
    from leaf.service import page_claim

    owner = preview.PreviewService(page_dir, user=True)
    sent = detached.socket.socket.sendall

    def accept_then_interrupt(speaker, data):
        if data == b"\n":
            assert owner.claim is not None
            sent(speaker, data)
            wait_for(
                lambda: page_claim(page_dir),
                lambda claim: claim is not None,
                failure="accepted start did not publish its claim",
            )
            if transferred:
                from leaf.harness import ClaudeCodeHarness

                with service.PageTransaction(page_dir) as page:
                    page.take_claim(ClaudeCodeHarness("successor", "Claude"))
            raise KeyboardInterrupt
        return sent(speaker, data)

    monkeypatch.setattr(detached.socket.socket, "sendall", accept_then_interrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            owner.start()
        assert (
            page_claim(page_dir)["acquisition"] != owner.claim["acquisition"]
        ) == transferred
        owner.stop()
        assert bool(server.running_server(page_dir)) == transferred
    finally:
        cmd_stop(page_dir)


@pytest.mark.parametrize("refusal", ["abort_reuse", "ended_session", "new_generation"])
def test_private_startup_keeps_previous_owner_until_acceptance(
    page_dir, monkeypatch, refusal
):
    from leaf.hosting import claim_and_start, cmd_stop
    from leaf.service import page_claim
    from leaf.state import end_session, ensure_session

    original = preview.PreviewService(page_dir, user=True)
    url, _ = original.start()
    previous = page_claim(page_dir)
    # A different harness is the candidate, so ending its session cannot itself end
    # the original watcher while the candidate is still unpublished.
    from leaf import harness

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "candidate")
    try:
        expected = ValueError if refusal == "abort_reuse" else RuntimeError
        with pytest.raises(expected), claim_and_start(page_dir) as prepared:
            assert prepared.claim["acquisition"] != previous["acquisition"]
            assert page_claim(page_dir) == previous
            assert not original.ended
            if refusal == "abort_reuse":
                raise ValueError("caller leaves before accepting reuse")
            end_session(prepared.claim["id"])
            if refusal == "new_generation":
                ensure_session(
                    prepared.claim["id"], harness.session_harness().lifetime()
                )
        assert page_claim(page_dir) == previous
        assert not original.ended
        assert fetch(url)[0] == 200
    finally:
        cmd_stop(page_dir)


def test_service_publication_failure_keeps_previous_preview_claim(
    page_dir, monkeypatch
):
    from leaf import hosting
    from leaf.harness import session_harness
    from leaf.service import page_claim, prepare_claim
    from leaf.state import write_json

    original = preview.PreviewService(page_dir, user=True)
    original.start()
    previous = page_claim(page_dir)
    hosting.cmd_stop(page_dir)
    published = json.loads((page_dir / "service.json").read_text())
    published["enabled"] = True
    write_json(page_dir / "service.json", published)
    intent = prepare_claim(session_harness(), page_dir)

    class Accepted:
        def announce(self, _ready, *, commit):
            commit()
            return True

    def unavailable(path, record):
        if path == page_dir / "service.json":
            raise PermissionError("service cannot be published")
        write_json(path, record)

    monkeypatch.setattr(hosting, "write_json", unavailable)
    try:
        with pytest.raises(PermissionError, match="service cannot be published"):
            hosting.cmd_serve(
                page_dir, acquire=True, prepared_claim=intent, handshake=Accepted()
            )
        assert page_claim(page_dir) == previous
        assert not original.ended
        assert not leases.lock_is_held(page_dir / "server.lock")
        assert json.loads((page_dir / "service.json").read_text()) == published
    finally:
        monkeypatch.undo()
        hosting.cmd_stop(page_dir)
