"""Asset publication keeps authored consumers on the selected immutable bytes."""

import json

from leaf.media import media_name
from leaf_dev import example_data, leaf_assets


def test_demo_publication_reconciles_the_catalog_with_other_published_previews(
    tmp_path, monkeypatch
):
    """Publishing a demo adopts the whole asset head, including another preview.

    The linked images follow those bytes; an unlinked image and an unused preview
    cannot become catalog entries. Staging the next capture also prepares its links
    before a caller validates the staged site, without republishing that draft.
    """
    remote = tmp_path / "remote.git"
    leaf_assets.run(
        "git", "init", "--bare", "--initial-branch=main", str(remote), cwd=tmp_path
    )
    seed = tmp_path / "seed"
    leaf_assets.run("git", "clone", str(remote), str(seed), cwd=tmp_path)
    for name, value in (
        ("user.name", "Leaf test"),
        ("user.email", "leaf@example.test"),
    ):
        leaf_assets.run("git", "config", name, value, cwd=seed)
    (seed / "examples").mkdir()
    preview = seed / "examples" / "example-decision.jpg"
    preview.write_bytes(b"old decision preview")
    (seed / "demo").mkdir()
    (seed / "demo" / "session-card.png").write_bytes(b"old demo card")
    leaf_assets.run("git", "add", "-A", cwd=seed)
    leaf_assets.run("git", "commit", "-m", "Initial assets", cwd=seed)
    leaf_assets.run("git", "push", cwd=seed)
    old_revision = leaf_assets.run("git", "rev-parse", "HEAD", cwd=seed)

    source = tmp_path / "source"
    (source / "examples").mkdir(parents=True)
    (source / "examples" / "decision.html").write_text("<h1>A decision</h1>")
    docs = source / "docs"
    docs.mkdir()
    old = f"/media/{media_name(preview.read_bytes(), preview.suffix)}"
    (docs / "examples.html").write_text(
        f'<a class="example-link" href="/examples/decision/">\n'
        f'  <span><img src="{old}"></span>\n</a>\n'
    )
    (docs / "index.html").write_text(
        f'<a href="/examples/decision/"><img src="{old}" loading="lazy"></a>\n'
        f'<img src="{old}" alt="unlinked">\n'
    )
    repository = "max-sixty/leaf-assets"
    (source / "leaf-assets.json").write_text(
        json.dumps({"repository": repository, "revision": old_revision})
    )
    readme = source / "README.md"
    prefix = leaf_assets.raw_prefix(repository)
    readme.write_text(f"![Demo]({prefix}{old_revision}/demo/session-card.png)\n")
    monkeypatch.setattr(leaf_assets, "ROOT", source)
    monkeypatch.setattr(leaf_assets, "README", readme)
    monkeypatch.setattr(example_data, "ROOT", source)
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
    for name, value in (
        ("user.name", "Leaf test"),
        ("user.email", "leaf@example.test"),
    ):
        leaf_assets.run("git", "config", name, value, cwd=checkout)
    (checkout / "demo" / "session-card.png").write_bytes(b"reviewed new demo card")

    revision = leaf_assets.publish(checkout, "Publish the reviewed demo")

    replacement = f"/media/{media_name(preview.read_bytes(), preview.suffix)}"
    assert replacement in (docs / "examples.html").read_text()
    home = (docs / "index.html").read_text()
    assert replacement in home
    assert f'<img src="{old}" alt="unlinked">' in home
    assert json.loads((source / "leaf-assets.json").read_text()) == {
        "repository": repository,
        "revision": revision,
    }
    assert readme.read_text() == f"![Demo]({prefix}{revision}/demo/session-card.png)\n"
    assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=remote) == revision

    unchanged = {page: page.stat().st_mtime_ns for page in docs.glob("*.html")}
    assert leaf_assets.publish(checkout, "Already published") == revision
    assert {page: page.stat().st_mtime_ns for page in unchanged} == unchanged

    draft_dir = tmp_path / "draft"
    draft_dir.mkdir()
    draft = leaf_assets.stage(
        "examples", {"example-decision.jpg": b"next decision preview"}, draft_dir
    )
    next_preview = draft / "examples" / "example-decision.jpg"
    next_address = (
        f"/media/{media_name(next_preview.read_bytes(), next_preview.suffix)}"
    )
    assert next_address in (docs / "examples.html").read_text()
    assert next_address in (docs / "index.html").read_text()
    assert f'<img src="{old}" alt="unlinked">' in (docs / "index.html").read_text()
    assert json.loads((source / "leaf-assets.json").read_text())["revision"] == revision
    assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=remote) == revision
