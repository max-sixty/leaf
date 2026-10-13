"""Asset publication keeps authored consumers on the selected immutable bytes."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from leaf_dev import leaf_assets


def test_fetches_the_pin_over_git_and_publishes_a_complete_cache(tmp_path, monkeypatch):
    """Concurrent cold readers get the pin's bytes even when the remote head moved."""
    remote = tmp_path / "remote"
    remote.mkdir()
    leaf_assets.run("git", "init", "--initial-branch=main", cwd=remote)
    publisher(remote)
    image = remote / "example.png"
    image.write_bytes(b"pinned image\x00\xff")
    (remote / ".gitattributes").write_text("*.png filter=unavailable\n")
    (remote / "caption.json").write_bytes(b'{"caption":"pinned"}\n')
    leaf_assets.run("git", "add", "-A", cwd=remote)
    leaf_assets.run("git", "commit", "-m", "Pinned image", cwd=remote)
    pin = leaf_assets.run("git", "rev-parse", "HEAD", cwd=remote)
    image.write_bytes(b"later image")
    leaf_assets.run("git", "commit", "-am", "Move the head", cwd=remote)

    source = tmp_path / "source"
    source.mkdir()
    lock = source / "leaf-assets.json"
    lock.write_text(json.dumps({"repository": "fixture/assets", "revision": pin}))
    cache = tmp_path / "cache"
    monkeypatch.setattr(leaf_assets, "CACHE", cache)
    attributes = tmp_path / "global-attributes"
    attributes.write_text("*.png filter=unavailable\n")
    settings = {
        f"url.{remote.as_uri()}.insteadOf": "https://github.com/fixture/assets.git",
        "core.attributesFile": str(attributes),
        "core.autocrlf": "true",
        "filter.unavailable.required": "true",
        "filter.unavailable.smudge": "missing-asset-filter",
    }
    monkeypatch.setenv("GIT_CONFIG_COUNT", str(len(settings)))
    for index, (key, value) in enumerate(settings.items()):
        monkeypatch.setenv(f"GIT_CONFIG_KEY_{index}", key)
        monkeypatch.setenv(f"GIT_CONFIG_VALUE_{index}", value)

    with ThreadPoolExecutor(max_workers=2) as readers:
        paths = list(readers.map(leaf_assets.pinned_assets, [source, source]))
    assert paths == [cache / pin, cache / pin]
    assert (paths[0] / "example.png").read_bytes() == b"pinned image\x00\xff"
    assert (paths[0] / "caption.json").read_bytes() == b'{"caption":"pinned"}\n'
    assert sorted(path.name for path in paths[0].iterdir()) == [
        ".complete",
        ".gitattributes",
        "caption.json",
        "example.png",
    ]
    assert (paths[0] / ".complete").read_text() == pin

    missing = "0" * 40
    lock.write_text(json.dumps({"repository": "fixture/assets", "revision": missing}))
    with pytest.raises(RuntimeError, match=f"could not fetch .* at {missing}"):
        leaf_assets.pinned_assets(source)
    assert not (cache / missing).exists()


def test_a_publication_keeps_what_others_published_since_its_pin(tmp_path, monkeypatch):
    """Two branches pinned to one revision each publish a directory's files. The second
    keeps what the first added, which its own run never saw, since a stage is measured
    against the branch's pin and not the head. Where both touched one file, the second's
    choice stands, whether that is a copy or a removal. A publication whose push was
    refused lands on the head as it stands when it is tried again."""
    remote = tmp_path / "remote.git"
    leaf_assets.run(
        "git", "init", "--bare", "--initial-branch=main", str(remote), cwd=tmp_path
    )
    seed = tmp_path / "seed"
    leaf_assets.run("git", "clone", str(remote), str(seed), cwd=tmp_path)
    (seed / "examples").mkdir()
    (seed / "examples" / "example-decision.jpg").write_bytes(b"decision preview")
    (seed / "threads").mkdir()
    for name in ("kept", "shared", "edited", "dropped"):
        (seed / "threads" / f"{name}.png").write_bytes(b"the pin's")
    publisher(seed)
    leaf_assets.run("git", "add", "-A", cwd=seed)
    leaf_assets.run("git", "commit", "-m", "Initial assets", cwd=seed)
    leaf_assets.run("git", "push", cwd=seed)
    pin = leaf_assets.run("git", "rev-parse", "HEAD", cwd=seed)

    repository = "max-sixty/leaf-assets"
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{remote.as_uri()}.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", f"https://github.com/{repository}.git")

    def staged(name, directory, files):
        source = tmp_path / name
        source.mkdir()
        (source / "README.md").write_text("No images.\n")
        (source / "leaf-assets.json").write_text(
            json.dumps({"repository": repository, "revision": pin})
        )
        monkeypatch.setattr(leaf_assets, "ROOT", source)
        monkeypatch.setattr(leaf_assets, "README", source / "README.md")
        staging = tmp_path / f"staging-{name}"
        staging.mkdir()
        checkout = leaf_assets.stage(directory, files, staging)
        publisher(checkout.path)
        return checkout

    def published(revision):
        return {
            path: leaf_assets.run("git", "show", f"{revision}:{path}", cwd=remote)
            for path in leaf_assets.run(
                "git", "ls-tree", "-r", "--name-only", revision, cwd=remote
            ).split()
        }

    # The first adds a file, rewrites two, and removes `edited`.
    first = staged(
        "first",
        "threads",
        {
            "kept.png": b"the pin's",
            "added.png": b"first's",
            "shared.png": b"first's",
            "dropped.png": b"first's",
        },
    )
    leaf_assets.publish(first, "Publish the first branch's threads")
    # The second, from the same pin, rewrites `shared` and `edited` and removes
    # `dropped`, each a file the first touched.
    second = staged(
        "second",
        "threads",
        {
            "kept.png": b"the pin's",
            "own.png": b"second's",
            "shared.png": b"second's",
            "edited.png": b"second's",
        },
    )
    revision = leaf_assets.publish(second, "Publish the second branch's threads")
    assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=remote) == revision
    assert published(revision) == {
        "examples/example-decision.jpg": "decision preview",
        "threads/kept.png": "the pin's",
        "threads/added.png": "first's",
        "threads/own.png": "second's",
        "threads/shared.png": "second's",
        "threads/edited.png": "second's",
    }

    third = staged("third", "media", {"third.png": b"third's"})
    rejection = remote / "hooks" / "pre-receive"
    rejection.write_text("#!/bin/sh\nexit 1\n")
    rejection.chmod(0o755)
    with pytest.raises(RuntimeError, match="pre-receive hook declined"):
        leaf_assets.publish(third, "Publish the third branch's media")
    rejection.unlink()
    # Another publisher lands while the third waits to try again.
    leaf_assets.run("git", "pull", "-q", cwd=seed)
    (seed / "late.png").write_bytes(b"late")
    leaf_assets.run("git", "add", "-A", cwd=seed)
    leaf_assets.run("git", "commit", "-m", "Publish meanwhile", cwd=seed)
    leaf_assets.run("git", "push", cwd=seed)

    retried = leaf_assets.publish(third, "Publish the third branch's media")
    assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=remote) == retried
    assert published(retried) == {
        **published(revision),
        "late.png": "late",
        "media/third.png": "third's",
    }
    assert json.loads((tmp_path / "third" / "leaf-assets.json").read_text()) == {
        "repository": repository,
        "revision": retried,
    }


def publisher(clone):
    """Give a fixture clone the identity its commits need."""
    for name, value in (
        ("user.name", "Leaf test"),
        ("user.email", "leaf@example.test"),
    ):
        leaf_assets.run("git", "config", name, value, cwd=clone)
