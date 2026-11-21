"""Asset publication keeps authored consumers on the selected immutable bytes."""

import json

import pytest

from leaf_dev import leaf_assets

from ..model.test_leaf_assets import publisher


def test_demo_publication_adopts_what_other_publishers_published(tmp_path, monkeypatch):
    """Publishing a demo adopts the whole asset head, including another preview.

    Refusing the next draft at the asset remote leaves the pin and README unchanged.
    """
    remote = tmp_path / "remote.git"
    leaf_assets.run(
        "git", "init", "--bare", "--initial-branch=main", str(remote), cwd=tmp_path
    )
    seed = tmp_path / "seed"
    leaf_assets.run("git", "clone", str(remote), str(seed), cwd=tmp_path)
    publisher(seed)
    (seed / "examples").mkdir()
    preview = seed / "examples" / "example-decision.jpg"
    preview.write_bytes(b"old decision preview")
    (seed / "examples" / "example-retained.jpg").write_bytes(preview.read_bytes())
    (seed / "demo").mkdir()
    (seed / "demo" / "session-card.png").write_bytes(b"old demo card")
    (seed / "examples/media").mkdir()
    (seed / "examples/media/retained.png").write_bytes(b"authored example media")
    leaf_assets.run("git", "add", "-A", cwd=seed)
    leaf_assets.run("git", "commit", "-m", "Initial assets", cwd=seed)
    leaf_assets.run("git", "push", cwd=seed)
    old_revision = leaf_assets.run("git", "rev-parse", "HEAD", cwd=seed)

    source = tmp_path / "source"
    source.mkdir()
    repository = "max-sixty/leaf-assets"
    (source / ".config").mkdir()
    (source / leaf_assets.LOCK).write_text(
        json.dumps({"repository": repository, "revision": old_revision})
    )
    readme = source / "README.md"
    prefix = leaf_assets.raw_prefix(repository)
    readme.write_text(f"![Demo]({prefix}{old_revision}/demo/session-card.png)\n")
    monkeypatch.setattr(leaf_assets, "ROOT", source)
    monkeypatch.setattr(leaf_assets, "README", readme)
    # Git's normal transport routes this repository into the fixture's bare remote.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{remote.as_uri()}.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", f"https://github.com/{repository}.git")

    preview.write_bytes(b"another publisher's changed decision preview")
    (seed / "examples" / "example-unused.jpg").write_bytes(b"not in the catalog")
    leaf_assets.run("git", "add", "-A", cwd=seed)
    leaf_assets.run(
        "git", "commit", "-m", "Refresh the preview independently", cwd=seed
    )
    leaf_assets.run("git", "push", cwd=seed)
    staging = tmp_path / "staging"
    staging.mkdir()
    checkout = leaf_assets.clone(staging)
    publisher(checkout)
    (checkout / "demo" / "session-card.png").write_bytes(b"reviewed new demo card")

    revision = leaf_assets.publish(checkout, "Publish the reviewed demo")

    assert leaf_assets.run(
        "git", "show", f"{revision}:examples/example-decision.jpg", cwd=remote
    ) == ("another publisher's changed decision preview")
    assert json.loads((source / leaf_assets.LOCK).read_text()) == {
        "repository": repository,
        "revision": revision,
    }
    assert readme.read_text() == f"![Demo]({prefix}{revision}/demo/session-card.png)\n"
    assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=remote) == revision

    assert leaf_assets.publish(checkout, "Already published") == revision

    draft_dir = tmp_path / "draft"
    draft_dir.mkdir()
    ordinary = {page: page.read_bytes() for page in [source / leaf_assets.LOCK, readme]}
    draft = leaf_assets.stage(
        "examples",
        {
            "example-decision.jpg": b"next decision preview",
            "example-retained.jpg": b"old decision preview",
        },
        draft_dir,
    )
    assert (
        draft / "examples/media/retained.png"
    ).read_bytes() == b"authored example media"
    assert {page: page.read_bytes() for page in ordinary} == ordinary
    assert json.loads((source / leaf_assets.LOCK).read_text())["revision"] == revision
    assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=remote) == revision

    # A genuine bare-remote rejection exercises publish's failure boundary.
    rejection = remote / "hooks" / "pre-receive"
    rejection.write_text("#!/bin/sh\nexit 1\n")
    rejection.chmod(0o755)
    publisher(draft)
    with pytest.raises(RuntimeError, match="pre-receive hook declined"):
        leaf_assets.publish(draft, "A rejected draft")
    assert leaf_assets.run("git", "status", "--porcelain", cwd=draft) == ""
    assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=draft) != revision
    with pytest.raises(RuntimeError, match="pre-receive hook declined"):
        leaf_assets.publish(draft, "Retry the rejected draft")

    assert {page: page.read_bytes() for page in ordinary} == ordinary
    assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=remote) == revision
