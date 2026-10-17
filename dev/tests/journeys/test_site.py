"""Developer tooling checks; run explicitly from dev/tests."""

import json
import shutil
import urllib.error
import urllib.request

import pytest
from journeys.test_site import (  # noqa: F401
    DOCS,
)
from journeys.test_site import (
    hosted as hosted_fixture,  # noqa: F401
)
from journeys.test_site import (
    site as site_fixture,  # noqa: F401
)
from journeys.test_site import (
    staged_site as staged_site_fixture,  # noqa: F401
)
from leaf_dev import docs
from leaf_dev.commands import site as site_build


def test_a_link_a_host_would_404_stops_the_build(staged_site, hosted):
    """The build stops on each local link a static host would answer with a 404.

    One copy takes each break in turn and puts it back, and the untouched copy
    passes first, so each refusal is that break's own."""

    def refusal():
        with pytest.raises(SystemExit) as stopped:
            site_build.check_links(staged_site)
        return str(stopped.value)

    site_build.check_links(staged_site)
    tour = site_build.product_page(staged_site, "index.html") / "index.html"
    authored = tour.read_bytes()

    tour.write_text('<a href="whats-new.html">news</a>')
    assert "whats-new.html" in refusal()

    # The build holds each page's log and the site's own manifest, but the server
    # routes only a page's document and served resources, so these links 404 live.
    for target in ("/examples/triage-board/events.jsonl", "/_leaf/site.json"):
        assert (staged_site / target.lstrip("/")).is_file()
        with pytest.raises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(f"{hosted}{target}")
        assert missing.value.code == 404
        tour.write_text(f'<a href="{target}">record</a>')
        assert target in refusal()
    tour.write_bytes(authored)

    # What a host answers a directory with is its index, so that is what has to be
    # there. An existence check passes on the directory itself and publishes a 404.
    board = staged_site / "examples" / "triage-board" / "index.html"
    document = board.read_bytes()
    board.unlink()
    assert "triage-board" in refusal()
    board.write_bytes(document)

    # The one broken image a user of the site would never run into. A card is
    # fetched by whoever unfurls the link, not by the browser showing the page, so a
    # preview whose bytes moved out from under its content address fails silently
    # everywhere except in a shared link.
    manifest_path = staged_site / site_build.SITE_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"]["/examples/triage-board"]["image"] = "/examples/media/gone.jpg"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    refused = refusal()
    assert "og:image" in refused
    assert "gone.jpg" in refused


def test_an_invalid_product_document_stops_the_build(tmp_path, monkeypatch):
    """The builder crosses Leaf's gate rather than copying a plausible HTML shell."""
    staged_docs = tmp_path / "docs"
    shutil.copytree(DOCS, staged_docs)
    tour = staged_docs / "index.html"
    tour.write_text(
        tour.read_text().replace(
            "</head>", '<base href="https://evil.example/"></head>'
        )
    )
    monkeypatch.setattr(docs, "DOCS", staged_docs)

    with pytest.raises(SystemExit) as stopped:
        site_build.build(tmp_path / "invalid-site", site_build.checkout_leaf())
    assert "<base>" in str(stopped.value)
