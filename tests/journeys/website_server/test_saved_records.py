"How a container's saved website record restores a fresh release: stored chunks,\npublication dates, comments, choices and private revisions."

import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.request

import pytest
from interact_support import (
    PAGE,
    PAGE_GROUP,
    append_command,
    page_packages,
    publish,
    revision_root,
    running_http_server,
)
from process.website_server import (
    FakeCodexHarness,
    write_manifest,
)
from process.website_server.test_saved_records import durable_page_store

import leaf_website as website_server
from leaf.agents.delivery import receive_batch
from leaf.base.files import revision_path
from leaf.log.event_log import read_events
from leaf.pages.hosting import LeafHTTPServer
from leaf.records.transaction import PageTransaction, acknowledged, unacknowledged
from leaf.serving.drafts import read_drafts, write_draft
from leaf.source.runtime_selection import serving_runtime


def test_saved_website_record_restores_comments_choices_and_private_revision(
    page_dir, tmp_path, monkeypatch
):
    """A container's replacement recovers the record, not a second state model."""
    from leaf_website.storage import PUBLISHER, PageStoreRefused, restore

    (page_dir / "page").mkdir(exist_ok=True)
    (page_dir / "page" / "obsolete.txt").write_text("Remove this input")
    (page_dir / "index.html").write_text(
        PAGE.replace(PAGE_GROUP, '<lf-options id="choice">')
    )
    publish(page_dir)
    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/example": ("page", "example")})
    manifest_path = site / website_server.SITE_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"]["/example"]["states"] = {"1": "unused"}
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))
    with durable_page_store() as (store_url, stored):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        # A container restored from its store publishes every commit there, as its
        # `main` declares (`storage.PUBLISHER`).
        assert restore(site)
        monkeypatch.setenv("LEAF_PAGE_COMMIT", PUBLISHER)
        chosen = append_command(
            private,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["backfill-first"]},
                "facts": {"answered": True},
            },
        )
        comment = append_command(
            private,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "Retain this comment",
                "attempt": "saved-comment-0001",
            },
        )
        reply = append_command(
            private,
            {
                "kind": "reply",
                "author": "agent",
                "revision": 1,
                "parent": comment["id"],
                "responds": comment["id"],
                "text": "Retain this reply",
            },
        )
        with (
            PageTransaction(private) as page,
            receive_batch(page, {"events": [chosen, comment, reply]}, session_id=None),
        ):
            pass
        # A draft the visitor is writing is saved as it is written, apart from commits.
        draft = {"attempt": "saved-draft-0001", "text": "Keep these words"}
        write_draft(private, {"context": "general", "expect": [], "record": draft})
        # One private revision drops a page input and revises the document. Each
        # commit activates the source, so the two edits land before the same one.
        (private / "page" / "obsolete.txt").unlink()
        (private / "index.html").write_text(
            (private / "index.html")
            .read_text()
            .replace("<h2>Plan</h2>", "<h2>Revised plan</h2>")
        )
        with PageTransaction(private):
            pass
        httpd = LeafHTTPServer(
            ("127.0.0.1", 0),
            website_server.site_endpoint(site, FakeCodexHarness()),
        )
        with running_http_server(httpd):
            media = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
            )
            request = urllib.request.Request(
                f"http://127.0.0.1:{httpd.server_address[1]}/example/api/media",
                data=media,
                headers={
                    "Content-Type": "image/png",
                    "Leaf-Layer": website_server.page_binding(private)[0]["generation"],
                },
            )
            with urllib.request.urlopen(request) as response:
                media_answer = json.load(response)
                assert "path" in media_answer, media_answer
                media_path = media_answer["path"]
        # A fresh process with no local receipts negotiates against the store's
        # inventory. Only newly captured responses may need new chunks.
        uploads = len(stored["uploads"])
        previous = set(stored["blobs"])
        inventories = stored["inventories"]
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; import sys; from leaf.records.transaction import PageTransaction; "
                    "page = PageTransaction(Path(sys.argv[1])); page.__enter__(); page.__exit__(None, None, None)"
                ),
                str(private),
            ],
            env={**os.environ, "XDG_STATE_HOME": str(tmp_path / "fresh-process-state")},
            check=True,
        )
        assert not previous.intersection(stored["uploads"][uploads:])
        assert stored["inventories"] == inventories + 1
        publication = stored["publications"][-1]

        def body(path):
            response = publication["responses"][path]
            return b"".join(stored["blobs"][digest] for digest in response["chunks"])

        state = json.loads(body("api/state"))
        assert {chosen["id"], comment["id"], reply["id"]} <= {
            event["id"] for event in state["events"]
        }
        assert state["cursor"] == reply["seq"]
        assert state["pending"] == 0
        assert state["active"]["revision"] == 2
        assert state["session_alive"] is None and state["listening"] is False
        assert state["activity"].get("next_transition_at") is None
        # The commit captures the drafts answers the Durable Object serves while the
        # container sleeps, with the store it holds in their place.
        drafts = json.loads(body("api/drafts"))
        assert drafts["drafts"] == {"general": {**draft, "version": 1}}
        assert json.loads(body("api/news")) == {
            "reading": state["reading"],
            "pages": None,
            "drafts": {"store": drafts["store"], "version": drafts["version"]},
        }
        assert b"Revised plan" in body("")
        # A release's document carries no drafts (`http.py`), so the one saved here
        # never shows words the drafts store has replaced since.
        assert b'id="lf-drafts"' not in body("")
        private_entry = revision_root(private, 2).lstrip("/") + "/leaf.js"
        assert private_entry in publication["responses"]
        assert (
            body(private_entry) == serving_runtime().resources({}, {})["/leaf.js"].data
        )
        # Start a fresh filesystem from the same release image.
        replacement = tmp_path / "replacement"
        shutil.copytree(site, replacement, ignore=shutil.ignore_patterns("page"))
        shutil.copytree(page_dir, replacement / "page")
        restore(replacement)
        recovered = replacement / "page"
        assert read_events(recovered) == read_events(private)
        assert acknowledged(read_events(recovered)) == reply["seq"]
        assert (recovered / "index.html").read_bytes() == (
            private / "index.html"
        ).read_bytes()
        assert revision_path(recovered, 2).is_file()
        assert read_drafts(recovered) == drafts
        assert (recovered / media_path.lstrip("/")).read_bytes() == media
        assert not (recovered / "page" / "obsolete.txt").exists()
        recovered_state = website_server.initial_state(
            recovered, "/example", "example", manifest["release"]
        )
        assert {
            key: view["document"]
            for key, view in recovered_state["browser"]["views"].items()
        } == {key: view["document"] for key, view in state["browser"]["views"].items()}
        # Reads do not republish an unchanged canonical record.
        count = len(stored["publications"])
        with PageTransaction(private):
            pass
        assert len(stored["publications"]) == count
        # Storage failure prevents success, naming the store's reason; retries can
        # commit the local log.
        stored["fail"] = True
        with pytest.raises(
            PageStoreRefused, match="/publication answered 503: page store unavailable"
        ):
            append_command(
                private,
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 2,
                    "text": "Retry this commit",
                    "attempt": "saved-comment-0002",
                },
            )
        stored["fail"] = False
        with PageTransaction(private):
            pass
        assert len(stored["publications"]) == count + 1
        (private / "index.html").write_text(
            "<html><body>No valid document</body></html>"
        )
        with PageTransaction(private):
            pass
        publication = stored["publications"][-1]
        invalid_state = json.loads(body("api/state"))
        assert invalid_state["source_error"]
        assert invalid_state["active"]["revision"] == 2
        monkeypatch.setenv("LEAF_SITE_ROOT", str(replacement))
        next_comment = append_command(
            recovered,
            {
                "kind": "comment",
                "author": "user",
                "revision": 2,
                "text": "Only this needs delivery",
                "attempt": "saved-comment-0003",
            },
        )
        assert [
            event["id"]
            for event in unacknowledged(
                read_events(recovered), acknowledged(read_events(recovered))
            )
        ] == [next_comment["id"]]


def test_a_later_release_restores_a_visitors_page_as_they_left_it(
    page_dir, tmp_path, monkeypatch, initialized_page
):
    """A deploy at the same page protocol restores the visitor's page whole, though the
    new release publishes its own first revision: their comment stands on the revision
    they read, which the container then serves itself, since the new release's assets
    hold only the revisions it published."""
    from leaf_website.storage import PUBLISHER, restore

    def release_site(name, page, release):
        site = tmp_path / name
        shutil.copytree(page, site / "page")
        write_manifest(site, {"/example": ("page", "example")})
        manifest_path = site / website_server.SITE_MANIFEST
        manifest = json.loads(manifest_path.read_text())
        manifest["release"] = release
        entry = manifest["pages"]["/example"]
        entry["assets"] = f"/_leaf-release/{release}/example"
        entry["revisions"] = [revision_path(page, 1).stem]
        manifest_path.write_text(json.dumps(manifest))
        return site, entry

    publish(page_dir)
    earlier, _ = release_site("earlier", page_dir, "0" * 64)
    visited = revision_path(earlier / "page", 1).stem
    republished = initialized_page(
        tmp_path / "republished",
        page_packages(),
        (
            "PAGE-republished",
            lambda template: (template / "index.html").write_text(
                PAGE.replace("<h2>Plan</h2>", "<h2>Plan, republished</h2>")
            ),
        ),
    )
    publish(republished)
    later, entry = release_site("later", republished, "1" * 64)
    assert revision_path(later / "page", 1).stem != visited
    with durable_page_store() as (store_url, stored):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        monkeypatch.setenv("LEAF_SITE_ROOT", str(earlier))
        assert restore(earlier)
        monkeypatch.setenv("LEAF_PAGE_COMMIT", PUBLISHER)
        append_command(
            earlier / "page",
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "Kept across the deploy",
                "attempt": "kept-comment-0001",
            },
        )
        with PageTransaction(earlier / "page"):
            pass

        stored["release"] = "1" * 64
        monkeypatch.setenv("LEAF_SITE_ROOT", str(later))
        monkeypatch.delenv("LEAF_PAGE_COMMIT")
        assert restore(later)
        monkeypatch.setenv("LEAF_PAGE_COMMIT", PUBLISHER)
        restored = later / "page"
        assert revision_path(restored, 1).stem == visited
        assert b"Plan, republished" not in revision_path(restored, 1).read_bytes()
        assert any(
            event.get("text") == "Kept across the deploy"
            for event in read_events(restored)
        )
        with PageTransaction(restored):
            pass
        publication = stored["publications"][-1]
    document = b"".join(
        stored["blobs"][digest] for digest in publication["responses"][""]["chunks"]
    )
    assert f"{entry['assets']}/revisions/".encode() not in document
    assert any(
        path.startswith(f"revisions/{visited}") for path in publication["responses"]
    )
