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
import shlex
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    ROOT,
    STATED_TIMEOUT,
    declare_idle,
    fetch,
    stamp,
    wait_for,
)
from leaf import cli as cli_model
from leaf import codex_adapter, leases, server, service, session
from leaf.interaction_log import read_interactions
from leaf.media import media_name
from leaf.structure import SourceDocument
from leaf_dev import arms, page_fixtures
from leaf_dev.commands import preview
from leaf_dev.page_fixtures import prepare_page, read_fixture


def test_automated_page_producers_record_the_run_before_input(tmp_path, serve, request):
    """A served test and an isolated developer arm declare their actual provenance."""
    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head>"
        "<body><main><h1>Reading</h1></main></body></html>"
    )
    (tmp_path / "layer.json").write_text("[]")
    serve(source)
    [context] = [
        row
        for row in read_interactions(serve.page_dir)
        if row.get("type") == "run_context"
    ]
    assert context | {"ts": "clock"} == {
        "source": "developer",
        "type": "run_context",
        "ts": "clock",
        "purpose": "test",
        "run": str(tmp_path),
        "authored_source": str(source),
        "test": request.node.nodeid,
    }

    state = tmp_path / "isolated-state"
    page = tmp_path / "arm-page"
    arms.build_source(ROOT, state, source, page)
    [context] = read_interactions(page)
    assert context | {"ts": "clock"} == {
        "source": "developer",
        "type": "run_context",
        "ts": "clock",
        "purpose": "automated",
        "run": str(state),
        "authored_source": str(source),
    }


@pytest.mark.parametrize("evidence", ["missing", "deleted", "other-chat"])
def test_desktop_start_requires_its_validated_native_chat(
    tmp_path, under_codex, codex_env, native_codex_chat, evidence
):
    """Unsupported or absent native evidence cannot mint perpetual ownership."""
    sid = "desktop-no-source"
    if evidence == "deleted":
        native_codex_chat(sid).unlink()
    elif evidence == "other-chat":
        other = native_codex_chat("another-chat")
        from leaf.hooks import cmd_hook

        cmd_hook(
            "codex",
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": sid,
                "transcript_path": str(other),
            },
        )
    page = tmp_path / "page"
    subprocess.run([*LEAF_COMMAND, "page", "init", page], env=codex_env, check=True)
    task = under_codex(
        shlex.join([*LEAF_COMMAND, "server", "start", str(page)]),
        codex_env | {"CODEX_THREAD_ID": sid},
        app_server=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output, errors = task.communicate(timeout=STATED_TIMEOUT)
    assert task.returncode != 0, output
    assert "validated native transcript is unavailable" in errors
    assert "Codex hooks enabled" in errors
    assert service.page_claim(page) is None


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
    watched = preview.watch_paths(source, ROOT, [])
    assert str(examples / "layer.json") in watched.paths
    assert str(ROOT / "uv.lock") in watched.paths


@pytest.mark.parametrize("name", ["how-it-works", "index", "examples"])
def test_product_previews_prepare_the_authored_layer_and_media(
    tmp_path, monkeypatch, name
):
    """A product preview includes its site furniture, composed parts, and images."""
    source = ROOT / "docs" / f"{name}.html"
    page = tmp_path / "preview"
    monkeypatch.chdir(ROOT)

    def run_leaf(*args, input_text=None):
        result = CliRunner().invoke(cli_model.cli, list(args), input=input_text)
        assert result.exit_code == 0, result.output

    prepare_page(page, read_fixture(source), run_leaf, final_status=None)
    served = SourceDocument((page / "index.html").read_text())
    assert served.tree.select("nav.sitenav a[aria-current=page]")
    assert all(
        (page / reference.removeprefix("/")).is_file()
        for reference in served.media_refs
    )
    registry = json.loads((page / "registry.json").read_text())
    assert "nav.sitenav" in registry
    assert (ROOT / "docs" / "package" / "theme.css").read_text().rstrip() in (
        page / "theme.css"
    ).read_text()
    watched = preview.watch_paths(source, ROOT, [])
    assert str(ROOT / "docs" / "layer.json") in watched.paths
    # A composed part's owner is an input: a caption follows its example's edit.
    if name == "examples":
        assert str(ROOT / "examples" / "review-a-plan.html") in watched.paths


@pytest.mark.parametrize("kind", ["image", "css", "inline", "stylesheet", "sample"])
def test_fixture_media_follows_versions_draft_assets_and_live_edits(
    tmp_path, monkeypatch, kind
):
    """Markup selects media for preparation and refresh, including earlier versions."""
    source = tmp_path / "source" / "index.html"
    source.parent.mkdir()
    (source.parent / "layer.json").write_text("[]")
    (source.parent / "media").mkdir()
    (source.parent / "leaf-assets.json").write_text("{}")
    assets = tmp_path / "draft-assets"
    assets.mkdir()
    previous, current, revised, unused = [
        assets / f"{name}.png" for name in ("previous", "current", "revised", "unused")
    ]
    for path in (previous, current, revised, unused):
        path.write_bytes(path.stem.encode())

    def markup(path, kind=kind):
        address = f"/media/{media_name(path.read_bytes(), path.suffix)}"
        head = ""
        body = f'<img src="{address}" alt="Example">'
        if kind == "css":
            head = f"<style>.picture {{background-image:url({address})}}</style>"
            body = '<div class="picture">Picture</div>'
        elif kind == "inline":
            body = f'<div style="background-image:url({address})">Picture</div>'
        elif kind == "stylesheet":
            companion = source.with_suffix(".page")
            companion.mkdir(exist_ok=True)
            (companion / f"{path.stem}.css").write_text(
                f".picture {{background-image:url({address})}}"
            )
            head = f'<link rel="stylesheet" href="/page/{path.stem}.css">'
            body = '<div class="picture">Picture</div>'
        elif kind == "sample":
            body = (
                '<lf-sample id="sample" label="Picture">'
                f'<template data-sample id="sample-content">{body}</template></lf-sample>'
            )
        return (
            f"<!doctype html><html><head><title>Media fixture</title>{head}</head>"
            f"<body><main><h1>Media fixture</h1>{body}"
            "</main></body></html>"
        )

    versions = source.parent / "versions"
    versions.mkdir()
    (versions / "index.v1.html").write_text(markup(previous))
    source.write_text(markup(current))
    page = tmp_path / "page"

    def run_leaf(*args, input_text=None):
        result = CliRunner().invoke(cli_model.cli, list(args), input=input_text)
        assert result.exit_code == 0, result.output

    prepare_page(page, read_fixture(source), run_leaf, assets=assets, final_status=None)
    expected = {
        media_name(path.read_bytes(), path.suffix) for path in (previous, current)
    }
    assert {path.name for path in (page / "media").iterdir()} == expected
    source.write_text(markup(revised, kind="inline"))
    monkeypatch.setattr(page_fixtures, "pinned_assets", lambda root: assets)
    preview.refresh_media(source, page, run_leaf)
    expected.add(media_name(revised.read_bytes(), revised.suffix))
    assert {path.name for path in (page / "media").iterdir()} == expected


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
    )

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
    assert ROOT not in watched.roots  # A single assets pin does not watch its checkout.


class _ScriptedChanges:
    """A controlled input stream with the subscription's root-plan boundary."""

    def __init__(self, iterator, watched):
        self.iterator = iterator
        self.roots = preview.watch_roots(watched)

    def __next__(self):
        return next(self.iterator)

    def close(self):
        self.iterator.close()

    def matches(self, roots):
        return self.roots == roots


def test_a_preview_reads_its_watched_inputs_from_the_files_that_exist_now(tmp_path):
    """New modules and authored companions arrive under the existing subscription.

    Initialization owns whether an edit changes the layer; the watcher must report
    every input that could change that reading, including a newly added module.
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
        return preview.watch_paths(source, runtime, [layer_root])

    initial = watched()
    subscription = initial.roots
    assert str(existing_script) in watched().paths
    assert str(source) in watched().paths

    # Fictional history and data are read only while building a fresh slot.
    for companion in (source.with_suffix(".jsonl"), source.with_suffix(".data.json")):
        companion.write_text("{}")
        assert not initial.relevant(str(companion))
        assert str(companion) not in watched().paths

    ignored = scripts / "README.md"
    ignored.write_text("ignored", encoding="utf-8")
    assert str(ignored) not in watched().paths

    added_script = scripts / "added.py"
    assert initial.relevant(str(added_script))
    added_script.write_text("new", encoding="utf-8")
    assert str(added_script) in watched().paths

    added_script.unlink()
    assert str(added_script) not in watched().paths

    versions = source.parent / "versions"
    versions.mkdir()
    version = versions / "page.v1.html"
    assert not initial.relevant(str(version))
    version.write_text("version", encoding="utf-8")
    assert str(version) not in watched().paths

    widget = widgets / "lf-new.js"
    assert initial.relevant(str(widget))
    widget.write_text("export {};", encoding="utf-8")
    assert str(widget.resolve()) in watched().paths

    companions = source.with_suffix(".page")
    custom = companions / "widgets" / "lf-custom.js"
    assert initial.relevant(str(custom))
    custom.parent.mkdir(parents=True)
    custom.write_text("export {};")
    assert str(custom) in watched().paths
    custom.unlink()
    assert str(custom) not in watched().paths

    # None of those arrivals moved the subscription: each landed inside a directory
    # already watched recursively, so the open watcher kept collecting through them.
    assert watched().roots == subscription


def test_preview_file_subscription_follows_atomic_replacements(tmp_path):
    """An assets pin is an exact native watch, including repeated editor renames."""
    source = tmp_path / "pages/reading.html"
    source.parent.mkdir()
    source.write_text("reading")
    (source.parent / "media").mkdir()
    pin = tmp_path / "leaf-assets.json"
    pin.write_text("{}")
    scripts = tmp_path / "skills/leaf/scripts"
    scripts.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "uv.lock").write_text("")
    watched = preview.watch_paths(source, tmp_path, [])
    assert pin in watched.roots
    assert tmp_path not in watched.roots
    changes = preview.watch_changes(watched)
    try:
        for value in ("first", "second"):
            staging = tmp_path / "pin-next.json"
            staging.write_text(value)
            staging.replace(pin)
            wait_for(
                lambda: next(changes),
                lambda paths: str(pin) in paths,
                failure="the preview's native file subscription lost its assets pin",
            )
    finally:
        changes.close()


def test_preview_rearms_a_replaced_native_input_tree(tmp_path):
    """The selected file paths can stay equal while their native root expires."""
    tree = tmp_path / "inputs"
    tree.mkdir()
    module = tree / "state.py"
    module.write_text("initial")
    watched = preview.Watched((tree,), frozenset({str(module)}), frozenset({tree}))
    changes = preview.watch_changes(watched)
    try:
        assert changes.matches(preview.watch_roots(watched))
        shutil.rmtree(tree)
        tree.mkdir()
        module.write_text("replacement")
        assert not changes.matches(preview.watch_roots(watched))
        changes.close()
        changes = preview.watch_changes(watched)
        module.write_text("later authored edit")
        wait_for(
            lambda: next(changes),
            lambda paths: str(module) in paths,
            failure="the replacement preview input tree lost later authored edits",
        )
    finally:
        changes.close()


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
        watched = preview.watch_paths(source, ROOT, [root])
        assert str(followed.resolve()) in watched.paths, root
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
    before = preview.watch_paths(source, checkout, [])
    assert str(inherited) in before.paths
    # The directory that does not exist yet is watched, so its arrival is a change.
    assert str(nearer_media) in before.paths
    assert before.relevant(str(nearer_media / "nearer.png"))

    nearer_media.mkdir()
    nearer = nearer_media / "nearer.png"
    nearer.write_bytes(b"nearer")
    after = preview.watch_paths(source, checkout, [])
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


# A page's idle declaration matters only once delivery connects, so a refused
# delivery runs from a busy page alone.
@pytest.mark.parametrize(
    ("initially_idle", "delivery_available"),
    [(False, True), (True, True), (False, False), (False, "missing")],
)
@pytest.mark.parametrize("handoff", ["preview", "start", "run"])
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
        declare_idle(page_dir)
    queued = Path(codex_queue["PREVIEW_QUEUE_RECORD"])
    ready = tmp_path / "ready.json"
    done = tmp_path / "done"
    program = """
import json
import subprocess
import sys
import time
from pathlib import Path
from leaf.service import page_claim
from leaf.state import end_session, write_json
from leaf.harness import session_harness
from leaf.hosting import cmd_stop
from leaf_dev.commands.preview import PreviewService

page, ready, done = map(Path, sys.argv[1:4])
handoff = sys.argv[4]
preview = PreviewService(page, True)
foreground = None
try:
    if handoff == "preview":
        with preview.starting() as url:
            pass
        started = (url, preview.note)
        # Joining the current adapter preserves the preview's acquisition.
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
        end_session(session_harness().session)
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
        output, errors = task.communicate(timeout=STATED_TIMEOUT)
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
            session.cmd_waiting(page_dir, "Review this page")
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
        output, errors = task.communicate(timeout=STATED_TIMEOUT)
    assert task.returncode == 0, f"{output}{errors}"
    wait_for(
        lambda: codex_adapter.adapter_is_live("preview-thread"),
        lambda live: not live,
        failure="the task's delivery adapter outlived its preview",
    )


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
            "--harness",
            json.dumps({"name": "codex", "session": "codex-thread", "agent": "Codex"}),
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
    caller.settimeout(STATED_TIMEOUT)
    try:
        with caller.makefile("rb") as announced:
            assert json.loads(announced.readline())["url"] == before["url"]
    finally:
        caller.close()
    output, errors = task.communicate(timeout=STATED_TIMEOUT)
    assert task.returncode == 0, f"{output}{errors}"
    assert server.running_server(page) == before


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
    with original.starting() as url:
        pass
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
                with successor.starting():
                    pass
            elif handoff == "start":
                with claim_and_start(page_dir):
                    pass
            else:
                cmd_serve(page_dir, harness=session_harness(), acquire=True)
        assert page_claim(page_dir) == claim
        assert not original.ended
        assert json.loads((page_dir / "service.json").read_text()) == published
        assert running_server(page_dir)["url"] == url
        assert fetch(url)[0] == 200
    finally:
        cmd_stop(page_dir)


@pytest.mark.parametrize("refusal", ["layer", "cancel"])
def test_failed_serving_preparation_never_publishes_a_takeover(
    page_dir, monkeypatch, refusal
):
    """A takeover refused or cancelled in preparation leaves the original claim."""
    from leaf.detached import StartRefused
    from leaf.hosting import claim_and_start, cmd_stop
    from leaf.service import page_claim

    original = preview.PreviewService(page_dir, user=True)
    with original.starting():
        pass
    claim = page_claim(page_dir)
    cmd_stop(page_dir)
    # Keep the original watcher/claim, with its server down. Its next revival is
    # independent of a failed takeover's private preparation.
    record = json.loads((page_dir / "service.json").read_text())
    record["enabled"] = True
    (page_dir / "service.json").write_text(json.dumps(record))
    if refusal == "layer":
        from interact_support import vendored_at_another_protocol

        vendored_at_another_protocol(page_dir)
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
        with pytest.raises(KeyboardInterrupt), owner.starting():
            pass
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
    from leaf.detached import StartRefused
    from leaf.hosting import claim_and_start, cmd_stop
    from leaf.service import page_claim
    from leaf.state import end_session, ensure_session

    original = preview.PreviewService(page_dir, user=True)
    with original.starting() as url:
        pass
    previous = page_claim(page_dir)
    # A different harness is the candidate, so ending its session cannot itself end
    # the original watcher while the candidate is still unpublished.
    from leaf import harness

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "candidate")
    try:
        expected = ValueError if refusal == "abort_reuse" else StartRefused
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
    with original.starting():
        pass
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
                page_dir,
                harness=session_harness(),
                acquire=True,
                prepared_claim=intent,
                handshake=Accepted(),
            )
        assert page_claim(page_dir) == previous
        assert not original.ended
        assert not leases.lock_is_held(page_dir / "server.lock")
        assert json.loads((page_dir / "service.json").read_text()) == published
    finally:
        monkeypatch.undo()
        hosting.cmd_stop(page_dir)


@pytest.mark.parametrize("beside_runtime", [False, True])
def test_fixture_captures_use_the_selected_runtime_producer(
    tmp_path, monkeypatch, beside_runtime
):
    """A producer belongs to the consuming arm, wherever the authored source lives."""
    runtime = tmp_path / "runtime"
    arms.extract_payload(runtime)
    producer = runtime / "skills/leaf/packages/diff/scripts/patch_manifest.py"
    producer.write_text(
        "# /// script\n# dependencies = []\n# ///\n"
        "import json, sys\n"
        f"assert sys.prefix != {sys.prefix!r}, 'producer used authoring environment'\n"
        "json.dump({'producer': 'selected arm', 'patch': sys.stdin.read()}, sys.stdout)\n"
    )
    host_state = tmp_path / "host-state"
    foreign = tmp_path / "host-diff"
    shutil.copytree(runtime / "skills/leaf/packages/diff", foreign)
    (foreign / "scripts/patch_manifest.py").write_text(
        "raise RuntimeError('host producer')"
    )
    override = host_state / "leaf/packages/names/diff"
    override.parent.mkdir(parents=True)
    override.symlink_to(foreign, target_is_directory=True)
    monkeypatch.setenv("XDG_STATE_HOME", str(host_state))
    consumer_env = arms.environment(XDG_STATE_HOME=str(tmp_path / "arm-state"))
    sources = runtime / "examples" if beside_runtime else tmp_path / "shared-inputs"
    sources.mkdir(parents=True)
    source = sources / "comparison.html"
    source.write_text("<!doctype html><title>Comparison</title>")
    (sources / "layer.json").write_text('["diff"]')
    patch = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n"
    )
    (sources / "change.patch").write_text(patch)
    (sources / "notes.txt").write_text("first\nsecond\n")
    source.with_suffix(".data.json").write_text(
        json.dumps(
            {
                "$captures": {
                    "patch": {"file": "change.patch", "format": "unified-diff"},
                    "notes": {"file": "notes.txt", "lines": "2:2"},
                },
                "written": "Authored value",
            }
        )
    )
    fixture = read_fixture(source, runtime=runtime, env=consumer_env)
    assert fixture.data == (
        {"source": "patch", "value": {"producer": "selected arm", "patch": patch}},
        {"source": "notes", "value": "second\n"},
        {"source": "written", "value": "Authored value"},
    )
