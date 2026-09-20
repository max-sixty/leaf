"""What a preview reads off a checkout before it serves anything.

`scripts/preview.py` resolves three things from wherever its source sits: the
package layer, the media directory, and the set of paths a watcher subscribes
to. Each is a pure reading of a directory tree, so these state the tree and ask
for the reading — no server is started, no watcher subscribes, and no browser
opens.

That is why they are here and not beside the preview's browser tests. A nightly
mark is file-level, with no per-test escape, so a Python-decided reading filed
in a nightly module runs nowhere near the change that breaks it.
"""

import argparse
import json
import subprocess
from pathlib import Path

from interact_support import ROOT


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
