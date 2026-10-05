"""Asset publication keeps authored consumers on the selected immutable bytes."""

import json

import pytest
from leaf.files import list_revisions, revision_path
from leaf.media import media_name
from leaf_dev import example_data, leaf_assets, site


@pytest.mark.parametrize("failure", ["validation", "push"])
def test_demo_publication_reconciles_the_catalog_with_other_published_previews(
    tmp_path, monkeypatch, failure
):
    """Publishing a demo adopts the whole asset head, including another preview.

    The linked images follow those bytes; an unlinked image and an unused preview
    cannot become catalog entries. Refusing the next draft, at either site validation
    or the asset remote, leaves the ordinary catalog, pin and README unchanged.
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
    (seed / "examples" / "example-retained.jpg").write_bytes(preview.read_bytes())
    (seed / "demo").mkdir()
    (seed / "demo" / "session-card.png").write_bytes(b"old demo card")
    snapshots = seed / "tests/thread-snapshots"
    (snapshots / "linux").mkdir(parents=True)
    (snapshots / "linux/checkpoint.png").write_bytes(b"this runtime's Linux pixels")
    (seed / "examples/media").mkdir()
    (seed / "examples/media/retained.png").write_bytes(b"authored example media")
    leaf_assets.run("git", "add", "-A", cwd=seed)
    leaf_assets.run("git", "commit", "-m", "Initial assets", cwd=seed)
    leaf_assets.run("git", "push", cwd=seed)
    old_revision = leaf_assets.run("git", "rev-parse", "HEAD", cwd=seed)

    source = tmp_path / "source"
    (source / "examples").mkdir(parents=True)
    (source / "examples" / "decision.html").write_text("<h1>A decision</h1>")
    (source / "examples" / "retained.html").write_text("<h1>A retained preview</h1>")
    docs = source / "docs"
    docs.mkdir()
    old = f"/media/{media_name(preview.read_bytes(), preview.suffix)}"
    (docs / "examples.html").write_text(
        f'<a class="example-link" href="/examples/decision/">\n'
        f'  <span><img src="{old}"></span>\n</a>\n'
        f'<a class="example-link" href="/examples/retained/"><img src="{old}"></a>\n'
    )
    (docs / "index.html").write_text(
        f'<a href="/examples/decision/"><img src="{old}" loading="lazy"></a>\n'
        f'<img src="{old}" alt="unlinked">\n'
    )
    if failure == "validation":
        header = (
            "<!doctype html><html><head><title>Catalog fixture</title>"
            '<meta name="description" content="Asset publication fixture">'
            "</head>"
            '<body><main class="layout-column">'
        )
        for page in [*docs.glob("*.html"), *(source / "examples").glob("*.html")]:
            page.write_text(header + page.read_text() + "</main></body></html>")
        (docs / "media").mkdir()
        (docs / old.removeprefix("/")).write_bytes(b"old decision preview")
        versions = docs / "versions"
        versions.mkdir()
        (versions / "index.v1.html").write_text(
            header + "<p>An earlier authored version</p></main></body></html>"
        )
        companions = docs / "index.page"
        companions.mkdir()
        (companions / "evidence.txt").write_text("An authored companion")
        (source / "examples" / "layer.json").write_bytes(
            (site.EXAMPLES / "layer.json").read_bytes()
        )
        (source / "examples" / "media").mkdir()
        monkeypatch.setattr(site, "DOCS", docs)
        monkeypatch.setattr(site, "EXAMPLES", source / "examples")
        monkeypatch.setattr(site, "DEVELOPER_PAGES", ())
        monkeypatch.setattr(
            site, "PRODUCT_ROUTES", {"index.html": "/", "examples.html": "/examples/"}
        )
    repository = "max-sixty/leaf-assets"
    (source / "leaf-assets.json").write_text(
        json.dumps(
            {
                "repository": repository,
                "revision": old_revision,
                "thread_snapshots_revision": old_revision,
            }
        )
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
    (snapshots / "linux/checkpoint.png").write_bytes(b"another runtime's Linux pixels")
    (snapshots / "head-only").mkdir()
    (snapshots / "head-only/checkpoint.png").write_bytes(b"an unreviewed profile")
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
        "thread_snapshots_revision": old_revision,
    }
    assert readme.read_text() == f"![Demo]({prefix}{revision}/demo/session-card.png)\n"
    assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=remote) == revision

    unchanged = {page: page.stat().st_mtime_ns for page in docs.glob("*.html")}
    assert leaf_assets.publish(checkout, "Already published") == revision
    assert {page: page.stat().st_mtime_ns for page in unchanged} == unchanged

    draft_dir = tmp_path / "draft"
    draft_dir.mkdir()
    ordinary = {
        page: page.read_bytes()
        for page in [*docs.glob("*.html"), source / "leaf-assets.json", readme]
    }
    draft = leaf_assets.stage(
        "examples",
        {
            "example-decision.jpg": b"next decision preview",
            "example-retained.jpg": b"old decision preview",
        },
        draft_dir,
    )
    next_preview = draft / "examples" / "example-decision.jpg"
    assert (
        draft / "examples/media/retained.png"
    ).read_bytes() == b"authored example media"
    next_address = (
        f"/media/{media_name(next_preview.read_bytes(), next_preview.suffix)}"
    )
    assert {page: page.read_bytes() for page in ordinary} == ordinary
    assert json.loads((source / "leaf-assets.json").read_text())["revision"] == revision
    assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=remote) == revision

    if failure == "validation":
        # The real site gate first accepts the draft catalog and its selected bytes,
        # then refuses an unrelated dead image without installing the draft.
        draft_markup = leaf_assets.catalog_updates(draft)
        home = docs / "index.html"
        # Refuse the draft at the real site gate after it has completed its stamps.
        draft_markup[home] = draft_markup[home].replace(
            "</main>", '<a href="/missing-by-validation.png">A dead link</a></main>'
        )
        ordinary_build = tmp_path / "ordinary-site"
        actual_leaf = site.leaf
        interleaved = False

        def validate_with_an_ordinary_build(env, *args, **kwargs):
            nonlocal interleaved
            if not interleaved and args[:2] == ("page", "check"):
                interleaved = True
                assert {page: page.read_bytes() for page in ordinary} == ordinary
                home.write_text(
                    home.read_text().replace(
                        "</main>", "<p>A concurrent authored edit</p></main>"
                    )
                )
                ordinary[home] = home.read_bytes()
                # Another output builds the published bytes while draft validation
                # is live; neither its sources nor its final stamp may see the draft.
                site.build(ordinary_build, assets=checkout)
                ordinary_home = site.product_page(ordinary_build, "index.html")
                ordinary_html = (ordinary_home / "index.html").read_text()
                assert replacement in ordinary_html
                assert next_address not in ordinary_html
                assert "A concurrent authored edit" in ordinary_html
            return actual_leaf(env, *args, **kwargs)

        monkeypatch.setattr(site, "leaf", validate_with_an_ordinary_build)
        draft_build = tmp_path / "draft-site"
        with pytest.raises(SystemExit, match="missing-by-validation.png"):
            site.build(draft_build, assets=draft, source_markup=draft_markup)
        assert interleaved
        draft_home = site.product_page(draft_build, "index.html")
        draft_html = (draft_home / "index.html").read_text()
        assert next_address in draft_html
        assert replacement not in draft_html
        assert "A concurrent authored edit" not in draft_html
        assert (
            draft_home / "page" / "evidence.txt"
        ).read_text() == "An authored companion"
        revisions = list_revisions(draft_home)
        assert len(revisions) == 2
        assert (
            "An earlier authored version"
            in revision_path(draft_home, revisions[0]).read_text()
        )
        assert next_address in revision_path(draft_home, revisions[-1]).read_text()
        assert (versions / "index.v1.html").read_text().startswith(header)
        assert (
            json.loads((source / "leaf-assets.json").read_text())["revision"]
            == revision
        )
        assert readme.read_bytes() == ordinary[readme]
    else:
        # A genuine bare-remote rejection exercises publish's failure boundary.
        rejection = remote / "hooks" / "pre-receive"
        rejection.write_text("#!/bin/sh\nexit 1\n")
        rejection.chmod(0o755)
        for name, value in (
            ("user.name", "Leaf test"),
            ("user.email", "leaf@example.test"),
        ):
            leaf_assets.run("git", "config", name, value, cwd=draft)
        with pytest.raises(RuntimeError, match="pre-receive hook declined"):
            leaf_assets.publish(draft, "A rejected draft")
        assert leaf_assets.run("git", "status", "--porcelain", cwd=draft) == ""
        assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=draft) != revision
        with pytest.raises(RuntimeError, match="pre-receive hook declined"):
            leaf_assets.publish(draft, "Retry the rejected draft")

    assert {page: page.read_bytes() for page in ordinary} == ordinary
    assert leaf_assets.run("git", "rev-parse", "HEAD", cwd=remote) == revision

    # Accepting a reviewed runtime expectation advances only its own consumer.
    if failure == "push":
        rejection.write_text("#!/bin/sh\nexit 0\n")
    acceptance_dir = tmp_path / "acceptance"
    acceptance_dir.mkdir()
    reviewed = {
        "profile/checkpoint.png": b"reviewed runtime pixels",
        "linux/checkpoint.png": b"this runtime's Linux pixels",
    }
    accepted_checkout = leaf_assets.stage(
        "tests/thread-snapshots", reviewed, acceptance_dir, replace_tree=True
    )
    for name, value in (
        ("user.name", "Leaf test"),
        ("user.email", "leaf@example.test"),
    ):
        leaf_assets.run("git", "config", name, value, cwd=accepted_checkout)
    accepted = leaf_assets.publish(
        accepted_checkout,
        "Accept thread expectations",
        revision_key="thread_snapshots_revision",
    )
    assert accepted != revision
    assert leaf_assets.specification(source) == (repository, revision)
    assert leaf_assets.specification(
        source, revision_key="thread_snapshots_revision"
    ) == (repository, accepted)
    assert readme.read_bytes() == ordinary[readme]
    assert {page: page.read_bytes() for page in docs.glob("*.html")} == {
        page: ordinary[page] for page in docs.glob("*.html")
    }
    committed = leaf_assets.run(
        "git",
        "ls-tree",
        "-r",
        "--name-only",
        accepted,
        "tests/thread-snapshots",
        cwd=remote,
    ).splitlines()
    assert committed == [f"tests/thread-snapshots/{name}" for name in sorted(reviewed)]
    for name, content in reviewed.items():
        assert (
            accepted_checkout / "tests/thread-snapshots" / name
        ).read_bytes() == content
    assert (
        accepted_checkout / "examples/media/retained.png"
    ).read_bytes() == b"authored example media"
