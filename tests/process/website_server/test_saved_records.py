"""How a container's saved website record restores a fresh release: stored chunks,
publication dates, comments, choices, private revisions and installed layers."""

import asyncio
import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import leaf_website as website_server
import pytest
from interact_support import (
    PAGE,
    add_test_widget,
    append_command,
    page_packages,
    publish,
    running_http_server,
)
from leaf.delivery import receive_batch
from leaf.event_log import read_events
from leaf.files import latest_revision, revision_path
from leaf.hosting import LeafHTTPServer
from leaf.packages import cmd_package_install
from leaf.refusals import Refused
from leaf.registry.storage import layer_packages
from leaf.runtime_selection import serving_runtime
from leaf.service import PageTransaction, acknowledged, unacknowledged
from leaf.structure import SourceDocument
from leaf.vendoring import cmd_init

from process.website_server import (
    FakeCodexHarness,
    write_manifest,
)


@contextmanager
def durable_page_store():
    """A real HTTP store boundary; Leaf still performs every admission and fold."""
    stored = {
        "publications": [],
        "records": {},
        "staged": {},
        "blobs": {},
        "uploads": [],
        "restores": 0,
        "truncate": False,
        "inventories": 0,
        "fail": False,
    }

    class Store(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/records"
            stored["restores"] += 1
            self.send_response(200)
            self.send_header("Content-Type", "application/x-tar")
            self.end_headers()
            with tarfile.open(fileobj=self.wfile, mode="w|") as archive:

                def add(name, data):
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))

                add("records.json", json.dumps(stored["records"]).encode())
                names = dict.fromkeys(
                    digest
                    for record in stored["records"].values()
                    for file in record.values()
                    for digest in file["chunks"]
                )
                for digest in names:
                    add(digest, stored["blobs"][digest])
                    if stored["truncate"]:
                        break

        def do_PUT(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if self.path.startswith("/blobs/"):
                assert len(body) <= 1024 * 1024
                digest = self.path.removeprefix("/blobs/")
                assert hashlib.sha256(body).hexdigest() == digest
                stored["blobs"][digest] = body
                stored["uploads"].append(digest)
            elif self.path == "/prepare":
                stored["inventories"] += 1
                publication = json.loads(body)
                # This HTTP double supplies an opaque identity; real Worker tests
                # cover canonical hashing and replacement of staged content.
                identity = hashlib.sha256(body).hexdigest()
                stored["staged"][publication["root"]] = (identity, publication)
                digests = {
                    digest
                    for entry in (
                        *publication["record"].values(),
                        *publication["responses"].values(),
                    )
                    for digest in entry["chunks"]
                }
                self.send_response(200)
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "identity": identity,
                            "missing": [
                                digest
                                for digest in digests
                                if digest not in stored["blobs"]
                            ],
                        }
                    ).encode()
                )
                return
            else:
                assert self.path == "/publication"
                commit = json.loads(body)
                assert set(commit) == {"root", "identity"}
                identity, publication = stored["staged"][commit["root"]]
                assert commit["identity"] == identity
                if stored["fail"]:
                    self.send_response(503)
                    self.end_headers()
                    return
                stored["publications"].append(publication)
                stored["records"][publication["root"]] = publication["record"]
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_args):
            pass

    with running_http_server(ThreadingHTTPServer(("127.0.0.1", 0), Store)) as server:
        yield f"http://127.0.0.1:{server.server_address[1]}", stored


def test_public_and_private_snapshots_keep_a_stored_revisions_publication_date(
    page_dir, monkeypatch
):
    from leaf import page_snapshot

    activation = website_server.activate_source(page_dir)
    assert activation.error is None
    revision = activation.revision
    assert not any(event["kind"] == "note" for event in read_events(page_dir))
    marker = revision_path(page_dir, revision)
    os.utime(marker, (1_700_000_000, 1_700_000_000))
    captured_at = "2030-01-01T00:00:00+00:00"
    monkeypatch.setattr(page_snapshot, "now_iso", lambda: captured_at)
    live = website_server.PageStateService(page_dir).page_state()
    public = website_server.initial_state(page_dir, "/example", "example", "release")
    expected = live["browser"]["views"][str(revision)]["published_at"]
    assert expected == "2023-11-14T22:13:20+00:00"
    assert public["browser"]["views"][str(revision)]["published_at"] == expected
    candidate = page_snapshot.capture_page_snapshot(
        page_dir,
        SourceDocument(PAGE.replace("Plan", "A fresh candidate")),
        revision + 1,
        url="/",
    )
    assert candidate.context.active["activated_at"] == captured_at


def test_website_restore_streams_shared_chunks_once_across_files_and_pages(
    tmp_path, monkeypatch
):
    from leaf_website.storage import CHUNK_BYTES, restore

    site = tmp_path / "site"
    site.mkdir()
    write_manifest(site, {"/first": ("first", "example"), "/next": ("next", "example")})
    chunks = [b"a" * CHUNK_BYTES, b"b" * CHUNK_BYTES, b"tail"]
    digests = [hashlib.sha256(chunk).hexdigest() for chunk in chunks]
    modified = 1_700_000_000.25
    shared = {"chunks": [*digests[:2], digests[0], digests[2]], "modified": modified}
    with durable_page_store() as (store_url, stored):
        stored["blobs"].update(zip(digests, chunks, strict=True))
        stored["records"] = {
            "/first": {
                "page/shared.js": shared,
                "revisions/r2-private/shared.js": shared,
            },
            "/next": {"page/shared.js": shared},
        }
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        restore(site)
        assert stored["restores"] == 1
        expected = chunks[0] + chunks[1] + chunks[0] + chunks[2]
        for directory, record in stored["records"].items():
            for name in record:
                target = site / directory.strip("/") / name
                assert target.read_bytes() == expected
                assert target.stat().st_mtime == modified
        # A complete TAR can still omit bodies its descriptors reference.
        # Refuse that snapshot before replacing the previous local inputs.
        previous = site / "first/page/shared.js"
        previous.write_bytes(b"previous local input")
        stored["truncate"] = True
        with pytest.raises(ValueError, match="missing referenced chunks"):
            restore(site)
        assert previous.read_bytes() == b"previous local input"


def test_saved_website_record_keeps_an_unstamped_revisions_publication_date(
    page_dir, tmp_path, monkeypatch
):
    from leaf_website.storage import restore

    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/example": ("page", "example")})
    activation = website_server.activate_source(private)
    assert activation.error is None
    os.utime(revision_path(private, activation.revision), (1_700_000_000,) * 2)
    expected = website_server.PageStateService(private).page_state()["browser"][
        "views"
    ][str(activation.revision)]["published_at"]
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))
    with durable_page_store() as (store_url, _stored):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        restore(site)

        async def commit_with_running_loop():
            with PageTransaction(private):
                pass

        # Playwright's session fixture may already own this thread's event loop.
        # Give the active-loop publication case its own loop regardless of order.
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(asyncio.run, commit_with_running_loop()).result()
        replacement = tmp_path / "replacement"
        shutil.copytree(site, replacement)
        restore(replacement)
    recovered = website_server.initial_state(
        replacement / "page", "/example", "example", "release"
    )
    assert (
        recovered["browser"]["views"][str(activation.revision)]["published_at"]
        == expected
    )


def test_a_saved_published_revision_loads_its_layer_from_the_release(
    page_dir, tmp_path, monkeypatch
):
    """A comment on a published revision saves its document, not the revision's
    resources: the release publishes those beside the runtime it runs, so the saved
    document names them there, and a reload while the container sleeps loads them
    from the edge rather than waking it for them."""
    from leaf_website.storage import restore

    publish(page_dir)
    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/example": ("page", "example")})
    manifest_path = site / website_server.SITE_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    page = manifest["pages"]["/example"]
    page["states"] = {"1": "unused"}
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))
    with durable_page_store() as (store_url, stored):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        monkeypatch.delenv("LEAF_PAGE_COMMIT", raising=False)
        restore(site)
        append_command(
            private,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "Saved beside the published revision",
                "attempt": "saved-comment-0001",
            },
        )
        with PageTransaction(private):
            pass
        publication = stored["publications"][-1]
    response = publication["responses"][""]
    document = b"".join(stored["blobs"][digest] for digest in response["chunks"])
    published = f"{page['assets']}/revisions/{revision_path(private, 1).stem}"
    assert f'data-lf-entry="{published}/leaf.js"'.encode() in document
    assert not any(path.startswith("revisions/") for path in publication["responses"])


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
        (private / "page" / "obsolete.txt").unlink()
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
        assert body(private_entry) == serving_runtime().resources({})["/leaf.js"].data
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


def test_saved_website_record_restores_an_installed_layer(
    page_dir, tmp_path, monkeypatch
):
    """A package vendored by the agent remains usable in a fresh release image."""
    from leaf_website.storage import restore

    publish(page_dir)
    (page_dir / "vendor" / "obsolete.txt").write_text("Remove this installed input")
    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/example": ("page", "example")})
    manifest_path = site / website_server.SITE_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"]["/example"]["states"] = {"1": "unused"}
    manifest_path.write_text(json.dumps(manifest))
    source = tmp_path / "saved-widget"
    add_test_widget(source, "lf-restored", upgrade=True)
    (source / "instructions" / "author.md").write_text(
        "Use lf-restored to preserve the installed widget.\n"
    )
    cmd_package_install(source)
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))
    monkeypatch.delenv("LEAF_PAGE_COMMIT", raising=False)
    with durable_page_store() as (store_url, stored):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        restore(site)
        cmd_init(private, (*page_packages(), "saved-widget"))
        (private / "index.html").write_text(
            (private / "index.html")
            .read_text()
            .replace(
                "</main>",
                '<lf-restored id="installed">Installed widget</lf-restored></main>',
            )
        )
        with PageTransaction(private):
            pass
        revision = latest_revision(private)
        assert "lf-restored" in json.loads((private / "registry.json").read_text())
        replacement = tmp_path / "replacement"
        shutil.copytree(site, replacement, ignore=shutil.ignore_patterns("page"))
        shutil.copytree(page_dir, replacement / "page")
        monkeypatch.setenv("LEAF_SITE_ROOT", str(replacement))
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "empty-machine-state"))
        restore(replacement)
        recovered = replacement / "page"
        assert not (recovered / "vendor" / "obsolete.txt").exists()
        for name in ("registry.json", "theme.css", "widgets/lf-restored.js"):
            assert (recovered / name).read_bytes() == (private / name).read_bytes()
        assert (recovered / "instructions" / "author.md").read_bytes() == (
            private / "instructions" / "author.md"
        ).read_bytes()
        # Mutable restored layer files must not share writable inodes with the
        # immutable same-release revision used as their storage reference.
        baseline = (
            revision_path(recovered, 1).with_suffix("") / "resources" / "theme.css"
        )
        original = baseline.read_bytes()
        (recovered / "theme.css").write_bytes(b"edited mutable layer")
        assert baseline.read_bytes() == original
        (recovered / "theme.css").write_bytes((private / "theme.css").read_bytes())
        state = website_server.initial_state(
            recovered, "/example", "example", manifest["release"]
        )
        assert state["source_error"] is None
        assert state["active"]["revision"] == revision
        assert "lf-restored" in json.loads((recovered / "registry.json").read_text())
        # A restored process negotiates once and never retransmits stored blobs.
        uploads = len(stored["uploads"])
        previous = set(stored["blobs"])
        with PageTransaction(recovered):
            pass
        assert not previous.intersection(stored["uploads"][uploads:])
        # Package contract: delivery is self-contained, but rebuilding a selected
        # package on another machine requires installing its original source there.
        # Refusal must leave the already-restored layer usable.
        registry = (recovered / "registry.json").read_bytes()
        with pytest.raises(Refused, match="unknown package 'saved-widget'"):
            cmd_init(recovered, tuple(layer_packages(recovered)))
        assert (recovered / "registry.json").read_bytes() == registry
        assert latest_revision(recovered) == revision
        assert (
            website_server.initial_state(
                recovered, "/example", "example", manifest["release"]
            )["source_error"]
            is None
        )
