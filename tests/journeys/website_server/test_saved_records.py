"How a container's saved website record restores a fresh release: stored chunks,\npublication dates, comments, choices and private revisions."

import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

import leaf_website as website_server
import pytest
from interact_support import (
    PAGE,
    append_command,
    publish,
    running_http_server,
)
from process.website_server import (
    FakeCodexHarness,
    write_manifest,
)
from process.website_server.test_saved_records import durable_page_store

from leaf.delivery import receive_batch
from leaf.event_log import read_events
from leaf.files import revision_path
from leaf.hosting import LeafHTTPServer
from leaf.runtime_selection import serving_runtime
from leaf.service import PageTransaction, acknowledged, unacknowledged


def test_saved_website_record_restores_comments_choices_and_private_revision(
    page_dir, tmp_path, monkeypatch
):
    """A container's replacement recovers the record, not a second state model."""
    from leaf_website.storage import restore

    (page_dir / "page").mkdir(exist_ok=True)
    (page_dir / "page" / "obsolete.txt").write_text("Remove this input")
    (page_dir / "index.html").write_text(
        PAGE.replace("<lf-options>", '<lf-options id="choice" choose>')
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
        monkeypatch.delenv("LEAF_PAGE_COMMIT", raising=False)
        # Restore installs the inherited transaction provider before serving.
        restore(site)
        assert os.environ["LEAF_PAGE_COMMIT"] == "leaf_website.storage:publish"
        chosen = append_command(
            private,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["backfill-first"]},
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
            ("127.0.0.1", 0), website_server.site_endpoint(site, FakeCodexHarness())
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
                    "from pathlib import Path; import sys; from leaf.service import PageTransaction; "
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
        assert body("api/news").decode() == state["reading"]
        assert b"Revised plan" in body("")
        [private_entry] = [
            key
            for key in publication["responses"]
            if key.startswith("revisions/r2-") and key.endswith("/leaf.js")
        ]
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
        # Storage failure prevents success; retries can commit the local log.
        stored["fail"] = True
        with pytest.raises(urllib.error.HTTPError):
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
