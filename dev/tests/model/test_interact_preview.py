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
from functools import partial
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    ROOT,
    STATED_TIMEOUT,
    declare_idle,
    declared,
    fetch,
    stamp,
    wait_for,
)

from leaf import cli as cli_model
from leaf import codex_adapter, leases, server, service, session
from leaf.detached import Handshake
from leaf.interaction_log import read_interactions
from leaf.layer import stylesheet
from leaf.media import media_name
from leaf.registry.storage import layer_record, load_registry, selected
from leaf.structure import SourceDocument
from leaf_dev import arms, page_fixtures
from leaf_dev.commands import preview, record_demo, site
from leaf_dev.page_fixtures import prepare_page, read_fixture

LEAF_S_THEME = {"name": "reading", "source": "default"}


def test_developer_fixtures_do_not_capture_the_developers_personal_theme(tmp_path):
    from leaf.packages import cmd_package_install
    from leaf.registry.storage import layer_metadata

    personal = tmp_path / "personal"
    personal.mkdir()
    (personal / "overrides.css").write_text(":root { --accent: #814b07; }")
    cmd_package_install(personal)
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "leaf/themes.toml"
    config.parent.mkdir(parents=True)
    config.write_text('themes = ["personal"]\ndefault = "personal"\n')
    ordinary = tmp_path / "ordinary"
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(ordinary)])
    assert result.exit_code == 0, result.output
    assert layer_metadata(ordinary)["theme"]["name"] == "personal"

    runners = {
        "arm": partial(
            arms.run_leaf, ROOT, Path(os.environ["XDG_STATE_HOME"]), check=True
        ),
        "preview": partial(preview.leaf, ROOT / "bin/leaf", ROOT),
        "site": site.checkout_leaf(),
    }
    for name, run in runners.items():
        page = tmp_path / name
        run(
            "page",
            "init",
            *page_fixtures.package_selection_args(("diagram",)),
            str(page),
        )
        assert layer_metadata(page)["packages"] == ["diagram"]
        assert layer_metadata(page)["theme"] == LEAF_S_THEME

    page = tmp_path / "demo"
    with record_demo.demo_session(tmp_path / "demo-run"):
        record_demo.cmd_init(page)
        assert layer_metadata(page)["theme"] == LEAF_S_THEME


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
    [context] = read_interactions(page, types=("run_context",))
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
        for reference in served.authoring.media_refs
    )
    registry = load_registry(page)
    assert "nav.sitenav" in registry
    package = ROOT / "docs" / "package"
    layer_2 = layer_record(page)
    assert layer_2 is not None
    assert (
        stylesheet(package / "overrides.css", package).rstrip()
        in selected(layer_2, page).top_files["theme.css"].decode()
    )
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
    scripts = runtime / "src" / "nested"
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

    # History remains a seed; data companions also declare live capture inputs.
    history = source.with_suffix(".jsonl")
    history.write_text("{}")
    assert not initial.relevant(str(history))
    assert str(history) not in watched().paths
    data = source.with_suffix(".data.json")
    data.write_text("{}")
    assert initial.relevant(str(data))
    assert str(data) in watched().paths

    ignored = scripts / "README.md"
    ignored.write_text("ignored", encoding="utf-8")
    assert str(ignored) not in watched().paths

    added_script = scripts / "added.py"
    assert initial.relevant(str(added_script))
    added_script.write_text("new", encoding="utf-8")
    assert str(added_script) in watched().paths

    added_script.unlink()
    assert str(added_script) not in watched().paths

    # Python loads schema data at import time too; changing it needs both the
    # server's refresh and a fresh watcher, just like changing a Python module.
    schema = scripts / "state.schema.json"
    schema.write_text("{}")
    assert str(schema) in watched().paths
    assert schema in preview.worker_inputs(runtime)

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
    scripts = tmp_path / "src"
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


def test_corpus_preview_follows_authored_sources(tmp_path, monkeypatch, capsys):
    """Native source events regenerate the corpus before its live page is refreshed."""
    from leaf.data import read_data
    from leaf.registry.storage import load_registry
    from leaf_dev.commands import corpus
    from leaf_dev.example_data import data_file, named_source, page_files

    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "layer.json").write_text('["default"]')
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "examples.html").write_text("")
    (tmp_path / "tests/fixtures/pages").mkdir(parents=True)
    monkeypatch.setattr(corpus, "DEVELOPER_SOURCES", ())
    source = examples / "reading.html"
    source.write_text(
        "<html><head><title>Reading</title></head><body><main><h1>Before</h1>"
        '<lf-text-document id="reading" source="text"></lf-text-document>'
        "</main></body></html>"
    )
    captured = tmp_path / "code.txt"
    captured.write_text("First capture")
    data_file(source).write_text(
        json.dumps({"$captures": {"text": {"file": "../code.txt"}}})
    )
    files = page_files(source)
    files.mkdir()
    module = files / "reading.js"
    module.write_text("// before")
    output = named_source("corpus", root=tmp_path)
    page = tmp_path / "preview"
    native_watch = preview.watch_changes

    def editing_watch(watched):
        native = native_watch(watched)

        def changed(path):
            return wait_for(
                lambda: next(native),
                lambda paths: str(path) in paths,
                failure=f"native corpus subscription missed {path}",
            )

        def edits():
            try:
                source.write_text(source.read_text().replace("Before", "After"))
                module.write_text("// after")
                yield changed(source)
                assert "After" in (page / "index.html").read_text()
                assert (page / "page/reading.js").read_text() == "// after"

                captured.write_text("Edited capture")
                yield changed(captured)
                assert (
                    read_data(page, load_registry(page))["sources"]["text"]["value"]
                    == "Edited capture"
                )

                # A companion can change how a capture is read without new markup.
                data_file(source).write_text(
                    json.dumps(
                        {"$captures": {"text": {"file": "../code.txt", "lines": "1:1"}}}
                    )
                )
                yield changed(data_file(source))
                assert (
                    json.loads(data_file(output).read_text())["$captures"]["text"][
                        "lines"
                    ]
                    == "1:1"
                )

                added = examples / "added.html"
                added.write_text(
                    "<html><head><title>Added</title></head><body><main><p>New example</p></main></body></html>"
                )
                yield changed(added)
                assert "New example" in (page / "index.html").read_text()

                added.unlink()
                module.unlink()
                yield changed(added)
                assert "New example" not in (page / "index.html").read_text()
                assert not (page / "page/reading.js").exists()

                source.write_text(
                    source.read_text().replace("<h1>", '<h1 id="reading">')
                )
                yield changed(source)
                assert "Preview update refused" in capsys.readouterr().err
                source.write_text(
                    source.read_text().replace('<h1 id="reading">After', "<h1>Repaired")
                )
                yield changed(source)
                assert "Repaired" in (page / "index.html").read_text()
            finally:
                native.close()

        return _ScriptedChanges(edits(), watched)

    monkeypatch.setattr(preview, "watch_changes", editing_watch)
    with pytest.raises(StopIteration):
        preview.serve_preview(output, page, ROOT / "bin/leaf", ROOT, False)


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
    """HTTP feedback reaches the current task without a second `page claim`.

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
        assert claim is not None
        assert claim["id"] == "preview-thread"
        assert claim["pid"] == task.pid, (
            "detached child replaced its launching harness lifetime"
        )
        assert codex_adapter.adapter_is_live("preview-thread")
        if initially_idle:
            assert declared(page_dir)["state"] == "idle"
            session.cmd_waiting(page_dir)
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
    assert before is not None
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
        assert owner.claim is not None
        claim_record = page_claim(page_dir)
        assert claim_record is not None
        assert (
            claim_record["acquisition"] != owner.claim["acquisition"]
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
            assert previous is not None
            assert prepared.claim["acquisition"] != previous["acquisition"]
            assert page_claim(page_dir) == previous
            assert not original.ended
            if refusal == "abort_reuse":
                raise ValueError("caller leaves before accepting reuse")
            end_session(prepared.claim["id"])
            if refusal == "new_generation":
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
    producer = runtime / "packages/diff/scripts/patch_manifest.py"
    producer.write_text(
        "# /// script\n# dependencies = []\n# ///\n"
        "import json, sys\n"
        f"assert sys.prefix != {sys.prefix!r}, 'producer used authoring environment'\n"
        "json.dump({'producer': 'selected arm', 'patch': sys.stdin.read()}, sys.stdout)\n"
    )
    host_state = tmp_path / "host-state"
    foreign = tmp_path / "host-diff"
    shutil.copytree(runtime / "packages/diff", foreign)
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
        {
            "kind": "capture",
            "source": "patch",
            "value": {"producer": "selected arm", "patch": patch},
        },
        {"kind": "capture", "source": "notes", "value": "second\n"},
        {"kind": "seed", "source": "written", "value": "Authored value"},
    )


def test_a_fixture_acknowledges_its_seed_with_the_runtime_it_was_read_for(tmp_path):
    """An arm at another protocol acknowledges a seeded page it vendored, so a paired
    comparison across a protocol bump builds both arms (`leaf-dev stills`)."""
    runtime = tmp_path / "runtime"
    arms.extract_payload(runtime)
    registry = runtime / "browser/runtime/kernel-registry.json"
    layer = json.loads(registry.read_text())
    layer["$events"]["protocol"] += 1
    registry.write_text(json.dumps(layer, ensure_ascii=False))
    state = tmp_path / "state"
    page = tmp_path / "page"
    prepare_page(
        page,
        read_fixture(
            ROOT / "examples/log-retention.html",
            runtime=runtime,
            env=arms.environment(XDG_STATE_HOME=str(state)),
        ),
        partial(arms.run_leaf, runtime, state, check=True),
        final_status=None,
    )
    events = [
        json.loads(line) for line in (page / "events.jsonl").read_text().splitlines()
    ]
    assert events[-1]["kind"] == "receipt"
    assert events[-1]["through"] == len(events) - 1


def test_resumed_preview_follows_capture_bindings_and_files_without_replaying_seeds(
    tmp_path,
):
    """A retained page adopts new capture names and later edits to their files.

    The source and value publication use the same real refresh as a resumed or
    live preview; a literal seed edited on the page remains that page's data.
    """
    from leaf.data import read_data
    from leaf.publishing import authored_digest
    from leaf.registry.storage import load_registry

    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head><body><main>"
        '<h1>Reading</h1><lf-text-document id="capture" source="before"></lf-text-document>'
        '<lf-text-document id="notes" source="notes"></lf-text-document></main></body></html>'
    )
    (tmp_path / "layer.json").write_text('["default"]')
    captured = tmp_path / "code.txt"
    captured.write_text("First capture")
    companion = source.with_suffix(".data.json")
    companion.write_text(
        json.dumps(
            {"$captures": {"before": {"file": "code.txt"}}, "notes": "Initial seed"}
        )
    )
    run_leaf = partial(preview.leaf, ROOT / "bin/leaf", ROOT)
    page = tmp_path / "page"
    prepare_page(page, read_fixture(source, runtime=ROOT), run_leaf)
    state = {"authored": authored_digest(preview.incoming_files(source))}
    run_leaf("data", "set", str(page), "notes", input_text=json.dumps("Page edit"))
    retained_log = (page / "events.jsonl").read_bytes()

    # This is the existing-slot path: its old data remains while the new fixture
    # binds a different source. Seeds must not overwrite the page's current data.
    source.write_text(source.read_text().replace('source="before"', 'source="after"'))
    companion.write_text(
        json.dumps(
            {"$captures": {"after": {"file": "code.txt"}}, "notes": "Replacement seed"}
        )
    )
    service = preview.PreviewService(page, False)
    try:
        assert preview.refresh_preview(
            source, page, ROOT / "bin/leaf", ROOT, state, service
        )
        values = read_data(page, load_registry(page))["sources"]
        assert values["after"]["value"] == "First capture"
        assert values["before"]["value"] == "First capture"
        assert values["notes"]["value"] == "Page edit"
        run = values["after"]["run"]
        watched = preview.watch_paths(source, ROOT, [])
        assert watched.relevant(str(companion))
        assert watched.relevant(str(captured))

        captured.write_text("Edited capture")
        assert preview.refresh_preview(
            source, page, ROOT / "bin/leaf", ROOT, state, service
        )
        values = read_data(page, load_registry(page))["sources"]
        assert values["after"]["value"] == "Edited capture"
        assert values["after"]["run"] != run
        assert values["notes"]["value"] == "Page edit"
        run = values["after"]["run"]
        assert preview.refresh_preview(
            source, page, ROOT / "bin/leaf", ROOT, state, service
        )
        assert read_data(page, load_registry(page))["sources"]["after"]["run"] == run
        assert (page / "events.jsonl").read_bytes().startswith(retained_log)
        # Refused captures must not publish a source that would draw empty.
        published = (page / "index.html").read_bytes()
        source.write_text(
            source.read_text().replace('source="after"', 'source="invalid"')
        )
        for spec in ({"file": "missing.txt"}, {"file": "code.txt", "format": "json"}):
            captured.write_text("42")
            companion.write_text(json.dumps({"$captures": {"invalid": spec}}))
            assert not preview.refresh_preview(
                source, page, ROOT / "bin/leaf", ROOT, state, service
            )
            assert (page / "index.html").read_bytes() == published
            assert (
                read_data(page, load_registry(page))["sources"]["after"]["run"] == run
            )
        # A current binding supersedes the stored contract even for equal values.
        source.write_bytes(published)
        captured.write_text("1")
        companion.write_text(json.dumps({"$captures": {"after": {"file": "code.txt"}}}))
        assert preview.refresh_preview(
            source, page, ROOT / "bin/leaf", ROOT, state, service
        )
        source.write_text(
            source.read_text().replace(
                '<lf-text-document id="capture" source="after"></lf-text-document>',
                '<lf-num id="capture" source="after" run="initial">1</lf-num>',
            )
        )
        assert preview.refresh_preview(
            source, page, ROOT / "bin/leaf", ROOT, state, service
        )
        assert (
            read_data(page, load_registry(page))["sources"]["after"]["contract"]
            == "measured-scalar"
        )
        companion.write_text(
            json.dumps({"$captures": {"after": {"file": "code.txt", "format": "json"}}})
        )
        assert preview.refresh_preview(
            source, page, ROOT / "bin/leaf", ROOT, state, service
        )
        captured.write_text(
            "true"
        )  # Python compares True == 1; JSON distinguishes them.
        assert not preview.refresh_preview(
            source, page, ROOT / "bin/leaf", ROOT, state, service
        )
        assert (
            type(read_data(page, load_registry(page))["sources"]["after"]["value"])
            is int
        )
    finally:
        service.stop()


def test_preview_keeps_watching_after_unreadable_inputs(tmp_path, monkeypatch, capsys):
    """Unreadable runtime inputs or incomplete captures leave the last page serving."""
    from leaf.data import read_data
    from leaf.registry.storage import load_registry

    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head><body><main><h1>Reading</h1>"
        '<lf-text-document id="reading" source="text"></lf-text-document></main></body></html>'
    )
    (tmp_path / "layer.json").write_text('["default"]')
    captured = tmp_path / "code.txt"
    captured.write_text("First capture")
    companion = source.with_suffix(".data.json")
    declaration = json.dumps({"$captures": {"text": {"file": "code.txt"}}})
    companion.write_text(declaration)
    page = tmp_path / "page"

    def edits():
        output = capsys.readouterr().out
        url = next(line for line in output.splitlines() if line.startswith("http://"))

        def unavailable(_runtime):
            raise OSError("runtime input temporarily unavailable")

        with monkeypatch.context() as unreadable:
            unreadable.setattr(preview, "worker_identity", unavailable)
            yield {str(captured)}
            assert "runtime input temporarily unavailable" in capsys.readouterr().err
            assert fetch(url)[0] == 200
        companion.write_text("{")
        yield {str(companion)}
        assert (
            read_data(page, load_registry(page))["sources"]["text"]["value"]
            == "First capture"
        )
        assert "Preview update refused" in capsys.readouterr().err
        for incomplete in (
            {"$captures": {"text": {}}},
            {"$captures": {"text": {"file": None}}},
            {"$captures": []},
            [],
        ):
            companion.write_text(json.dumps(incomplete))
            yield {str(companion)}
            assert "Preview update refused" in capsys.readouterr().err
        captured.write_text("Repaired capture")
        companion.write_text(declaration)
        yield {str(companion)}
        assert (
            read_data(page, load_registry(page))["sources"]["text"]["value"]
            == "Repaired capture"
        )

    batches = edits()
    monkeypatch.setattr(
        preview, "watch_changes", lambda watched: _ScriptedChanges(batches, watched)
    )
    with pytest.raises(StopIteration):
        preview.serve_preview(source, page, ROOT / "bin/leaf", ROOT, False)
