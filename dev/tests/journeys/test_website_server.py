"""Developer tooling checks; run explicitly from dev/tests."""

import json
import shutil

from process.website_server import (
    _no_harness_outlives_its_test_fixture,  # noqa: F401 (fixtures)
    get,
)

from leaf_dev import ROOT
from leaf_dev.commands import refresh_previews


def test_the_preview_generator_bootstraps_a_new_catalog_entry(tmp_path, monkeypatch):
    pinned = refresh_previews.pinned_assets()
    current = tmp_path / "current"
    (current / "examples").mkdir(parents=True)
    shutil.copytree(pinned / "demo", current / "demo")
    existing = current / "examples" / "example-existing.jpg"
    shutil.copy2(next((pinned / "examples").glob("example-*.jpg")), existing)
    source = ROOT / "examples" / "ideas-to-implement.html"
    sources = [source]
    monkeypatch.setattr(refresh_previews, "pinned_assets", lambda: current)
    monkeypatch.setattr(refresh_previews, "catalog_sources", lambda: sources)
    monkeypatch.setattr(refresh_previews.site_build, "catalog_sources", lambda: sources)
    monkeypatch.setattr(
        refresh_previews.site_build, "published_page_sources", lambda: sources
    )

    assets = refresh_previews.bootstrap_assets(tmp_path / "assets")
    site = tmp_path / "site"
    refresh_previews.site_build.build_examples(
        site, refresh_previews.site_build.checkout_leaf(), assets=assets
    )

    assert (
        assets / "examples" / "example-ideas-to-implement.jpg"
    ).read_bytes() == existing.read_bytes()
    with refresh_previews.serve_examples(site) as root:
        state = json.loads(get(f"{root}/examples/ideas-to-implement/api/state")[0])
    assert state["publication"]["kind"] == "example"
