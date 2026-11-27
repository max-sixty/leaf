"""How a container's saved website record restores a fresh release: stored chunks,
publication dates, comments, choices, private revisions and installed layers."""

import asyncio
import hashlib
import io
import json
import os
import shutil
import tarfile
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from interact_support import (
    PAGE,
    append_command,
    publish,
    running_http_server,
)

import leaf_website as website_server
from leaf.base.files import latest_revision, revision_path
from leaf.log.event_log import read_events
from leaf.pages.hosting import LeafHTTPServer
from leaf.records.transaction import PageTransaction
from leaf.serving import drafts as drafts_model
from leaf.serving import media as media_model
from leaf.source.file_bindings import bind_file, unbind_file
from leaf.source.structure import SourceDocument
from leaf_dev.page_fixtures import example_media
from process.website_server import (
    FakeCodexHarness,
    get,
    post,
    write_manifest,
)


@contextmanager
def durable_page_store():
    """A real HTTP store boundary; Leaf still performs every admission and fold."""
    stored: dict = {
        "publications": [],
        "records": {},
        "drafts": {},
        "staged": {},
        "blobs": {},
        "uploads": [],
        "restores": 0,
        "truncate": False,
        "inventories": 0,
        "fail": False,
        # Whether the next drafts save loses its answer after the store has had it.
        "lose": False,
        # The release the store serves, the one `write_manifest` names.
        "release": "0" * 64,
    }

    class Store(BaseHTTPRequestHandler):
        def refused(self):
            # As the session object does (`pageStore`), refuse a container on another
            # release before reading or writing anything.
            if self.headers["Leaf-Release"] == stored["release"]:
                return False
            self.send_response(409)
            self.end_headers()
            self.wfile.write(
                f"the page store serves release {stored['release']}".encode()
            )
            return True

        def do_GET(self):
            assert self.path == "/records"
            if self.refused():
                return
            stored["restores"] += 1
            self.send_response(200)
            self.send_header("Content-Type", "application/x-tar")
            self.end_headers()
            with tarfile.open(fileobj=self.wfile, mode="w|") as archive:

                def add(name, data):
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))

                add(
                    "records.json",
                    json.dumps(
                        {"records": stored["records"], "drafts": stored["drafts"]}
                    ).encode(),
                )
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
            if self.refused():
                return
            if self.path.startswith("/blobs/"):
                assert len(body) <= 1024 * 1024
                digest = self.path.removeprefix("/blobs/")
                assert hashlib.sha256(body).hexdigest() == digest
                stored["blobs"][digest] = body
                stored["uploads"].append(digest)
            elif self.path == "/drafts":
                # As the Durable Object does (`saveDrafts`), take the store only over
                # the one it replaces, and answer with the store held.
                save = json.loads(body)
                held = stored["drafts"].get(save["root"])
                if save["replaces"] == (
                    held and {"store": held["store"], "version": held["version"]}
                ):
                    held = stored["drafts"][save["root"]] = save["drafts"]
                if stored["lose"]:
                    stored["lose"] = False
                    self.send_response(503)
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"drafts": held}).encode())
                return
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
                    self.wfile.write(b"page store unavailable")
                    return
                stored["publications"].append(publication)
                stored["records"][publication["root"]] = publication["record"]
            self.send_response(204)
            self.end_headers()

        def log_message(self, format, *_args):
            pass

    with running_http_server(ThreadingHTTPServer(("127.0.0.1", 0), Store)) as server:
        yield f"http://127.0.0.1:{server.server_address[1]}", stored


def test_public_and_private_snapshots_keep_a_stored_revisions_publication_date(
    page_dir, monkeypatch
):
    from leaf.pages import page_snapshot

    activation = website_server.activate_source(page_dir)
    assert activation.error is None
    revision = activation.revision
    assert not any(event["kind"] == "note" for event in read_events(page_dir))
    assert revision is not None
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
    assert candidate.context.active is not None
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


def test_a_release_that_drops_a_page_restores_the_sessions_others(
    tmp_path, monkeypatch
):
    """A session's record outlives a deploy, so it can hold a page the new release no
    longer publishes. Its other pages restore, and the dropped page's record and drafts
    stay unread."""
    from leaf_website.storage import restore

    site = tmp_path / "site"
    site.mkdir()
    write_manifest(site, {"/kept": ("kept", "example")})
    body = b"kept"
    digest = hashlib.sha256(body).hexdigest()
    with durable_page_store() as (store_url, stored):
        stored["blobs"][digest] = body
        stored["records"] = {
            root: {"page/app.js": {"chunks": [digest], "modified": 0}}
            for root in ("/kept", "/dropped")
        }
        stored["drafts"] = {"/dropped": {"store": "s", "version": 1, "drafts": {}}}
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        assert restore(site)
    assert (site / "kept/page/app.js").read_bytes() == body
    assert sorted(path.name for path in site.iterdir()) == ["_leaf", "kept"]


def test_a_container_on_another_release_does_not_start(tmp_path, monkeypatch):
    """After a deploy a session's container can still run the previous image until
    its session's next request stops it, and that code may misread a record the new
    release shaped, and its saved responses would name the previous release's
    document. The store refuses it before it reads anything, and a refusal at restore
    ends a start, so nothing it would write reaches the session's record."""
    from leaf_website.storage import PageStoreRefused, restore

    site = tmp_path / "site"
    site.mkdir()
    write_manifest(site, {"/first": ("first", "example")})
    with durable_page_store() as (store_url, stored):
        stored["release"] = "1" * 64
        stored["records"] = {"/first": {"page/kept.js": {"chunks": [], "modified": 0}}}
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        with pytest.raises(PageStoreRefused, match="409"):
            restore(site)
        assert stored["restores"] == 0
    assert not (site / "first").exists()


def test_publishing_saved_responses_keeps_the_reading_a_tab_holds(
    page_dir, tmp_path, monkeypatch
):
    """Saving a published page's responses reads its state once for each revision.
    None of those readings is one a tab goes on to extend, so they leave the server's
    remembered readings alone, and the tab's next answer is still only what changed
    (`served_state.tail`), even where the server remembers a single reading."""
    from leaf.serving.served_state import tail
    from leaf_website.storage import PUBLISHER, restore

    monkeypatch.setattr(tail, "REMEMBERED", 1)
    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/example": ("page", "example")})
    assert website_server.activate_source(private).error is None
    service = website_server.PageStateService(private)
    held = tail.answer(service.page_state(), None, private)["browser"]["basis"]["key"]
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))
    with durable_page_store() as (store_url, stored):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        assert restore(site)
        monkeypatch.setenv("LEAF_PAGE_COMMIT", PUBLISHER)

        def commit():
            with PageTransaction(private):
                pass

        # Playwright's session fixture may already own this thread's event loop.
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(commit).result()
        assert stored["publications"]
    assert "since" in tail.answer(service.page_state(), held, private)


def test_saved_website_record_keeps_an_unstamped_revisions_publication_date(
    page_dir, tmp_path, monkeypatch
):
    from leaf_website.storage import PUBLISHER, restore

    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/example": ("page", "example")})
    activation = website_server.activate_source(private)
    assert activation.error is None
    assert activation.revision is not None
    os.utime(
        revision_path(private, activation.revision), (1_700_000_000, 1_700_000_000)
    )
    expected = website_server.PageStateService(private).page_state()["browser"][
        "views"
    ][str(activation.revision)]["published_at"]
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))
    with durable_page_store() as (store_url, _stored):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        assert restore(site)
        monkeypatch.setenv("LEAF_PAGE_COMMIT", PUBLISHER)

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
    from leaf_website.storage import PUBLISHER, restore

    publish(page_dir)
    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/example": ("page", "example")})
    manifest_path = site / website_server.SITE_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    page = manifest["pages"]["/example"]
    page["revisions"] = [revision_path(private, 1).stem]
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))
    with durable_page_store() as (store_url, stored):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        assert restore(site)
        monkeypatch.setenv("LEAF_PAGE_COMMIT", PUBLISHER)
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


def test_a_session_that_swaps_an_image_goes_on_saving(page_dir, tmp_path, monkeypatch):
    """Revisions that differ only in the images they show share the address their
    resources answer at, and an image answers at the page root, never there. A
    session that shows a screenshot, swaps it for another and goes on editing saves
    every revision, and both images at the page root."""
    from leaf_website.storage import PUBLISHER, restore

    publish(page_dir)
    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/example": ("page", "example")})
    manifest_path = site / website_server.SITE_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"]["/example"]["revisions"] = [revision_path(private, 1).stem]
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))
    with durable_page_store() as (store_url, stored):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        assert restore(site)
        monkeypatch.setenv("LEAF_PAGE_COMMIT", PUBLISHER)
        shots = media_model.cmd_media(
            private,
            [
                example_media() / "051bee487bfb5d13.png",
                example_media() / "006a318b091c6d1d.png",
            ],
        )
        for heading in [
            f'<h2>Plan</h2><p><img src="{shot["path"]}" alt="A shot"></p>'
            for shot in shots
        ] + ["<h2>Plan, later</h2>"]:
            (private / "index.html").write_text(PAGE.replace("<h2>Plan</h2>", heading))
            with PageTransaction(private):
                pass
        publication = stored["publications"][-1]
    assert latest_revision(private) == 4
    assert b"Plan, later" in b"".join(
        stored["blobs"][digest] for digest in publication["responses"][""]["chunks"]
    )
    assert {shot["path"].lstrip("/") for shot in shots} <= set(publication["responses"])


def test_a_draft_write_is_answered_only_once_the_page_store_holds_it(
    page_dir, tmp_path, monkeypatch
):
    """A container answers a draft write once the page store holds it, with no commit
    of the page, so one that dies without stopping loses no words a tab was told were
    saved: the next container restores them, under the store and at the version the
    answer named."""
    from leaf_website.storage import PUBLISHER, restore

    publish(page_dir)
    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/example": ("page", "example")})
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))
    words = "Words typed after the last send"
    with durable_page_store() as (store_url, stored):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        assert restore(site)
        monkeypatch.setenv("LEAF_PAGE_COMMIT", PUBLISHER)
        answer = drafts_model.write_draft(
            private,
            {
                "context": "general",
                "expect": [],
                "record": {"attempt": "a1", "text": words},
            },
        )
        assert answer["written"]
        assert not stored["publications"]

        # The container dies where it stands: the next starts from the release's image.
        shutil.rmtree(private)
        shutil.copytree(page_dir, private)
        assert restore(site)
    restored = drafts_model.read_drafts(private)
    assert restored["store"] == answer["store"]
    assert restored["version"] == answer["version"]
    assert restored["drafts"]["general"]["text"] == words


@contextmanager
def a_hosted_file_editor(page_dir, tmp_path, monkeypatch):
    """A site serving a page that binds `files/notes.md` from its own directory as
    `notes`, as the file editor's example binds `files/`, over a durable page store.
    Yields the private page directory, the store, a save of the reader's words over
    the revision the file was first read at, answering its status and body, and a
    restart, which starts the page from the release as a stopped container's
    successor does and answers the file's text."""
    from leaf_website.storage import PUBLISHER, restore

    notes = page_dir / "files" / "notes.md"
    notes.parent.mkdir()
    notes.write_text("Published words.\n")
    bind_file(page_dir, "notes", notes)
    publish(page_dir)
    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/example": ("page", "example")})
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))
    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, FakeCodexHarness())
    )
    address = f"http://127.0.0.1:{httpd.server_address[1]}"
    url = f"{address}/example/api/files/notes"
    with durable_page_store() as (store_url, stored), running_http_server(httpd):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        assert restore(site)
        monkeypatch.setenv("LEAF_PAGE_COMMIT", PUBLISHER)
        revision = json.loads(get(url)[0])["revision"]

        def save():
            body = {"revision": revision, "text": "Reader saved words.\n"}
            try:
                return 200, post(url, body, {"Origin": address})[0]
            except urllib.error.HTTPError as error:
                return error.code, error.read()

        def restart():
            shutil.rmtree(private)
            shutil.copytree(page_dir, private)
            assert restore(site)
            return (private / "files" / "notes.md").read_text()

        yield private, stored, save, restart


def test_a_save_to_a_file_the_page_binds_is_answered_once_the_page_store_holds_it(
    page_dir, tmp_path, monkeypatch
):
    """A file the page binds from its own directory is part of the page. The editor
    is told a save is kept only once the page store holds it, so a container that
    stops after the answer comes back with the reader's words, not the ones the
    release published."""
    with a_hosted_file_editor(page_dir, tmp_path, monkeypatch) as (*_, save, restart):
        status, saved = save()
        assert status == 200
        assert saved["text"] == "Reader saved words.\n"
        assert restart() == "Reader saved words.\n"


def test_a_saved_file_outlasts_its_grant_as_it_does_on_this_machine(
    page_dir, tmp_path, monkeypatch
):
    """Withdrawing a grant leaves the file itself as the reader saved it, so the
    agent can bind it again. The page's record is its directory, whatever the page
    grants, so a container that stops after the unbind keeps the file too."""
    with a_hosted_file_editor(page_dir, tmp_path, monkeypatch) as (
        private,
        _stored,
        save,
        restart,
    ):
        assert save()[0] == 200
        unbind_file(private, "notes")
        with PageTransaction(private):
            pass
        assert restart() == "Reader saved words.\n"


def test_a_file_save_the_page_store_refused_is_kept_once_its_retry_is_answered(
    page_dir, tmp_path, monkeypatch
):
    """A save whose commit the page store refuses fails, though the container's file
    holds it. The editor's retry meets that file as a newer one, and takes it as its
    own words kept, so that answer too waits until the page store holds them."""
    with a_hosted_file_editor(page_dir, tmp_path, monkeypatch) as (
        _private,
        stored,
        save,
        restart,
    ):
        stored["fail"] = True
        assert save()[0] == 500
        stored["fail"] = False
        status, stale = save()
        assert status == 409
        assert json.loads(stale)["current"]["text"] == "Reader saved words.\n"
        assert restart() == "Reader saved words.\n"


def test_a_drafts_save_answered_too_late_is_the_store_the_next_write_runs_on(
    page_dir, tmp_path, monkeypatch
):
    """The page store holds the drafts store of record. A save it took whose answer
    the container never heard leaves it a version ahead of the container's file. The
    next write finds that store there, takes it as the file and runs once more against
    it, so it is answered as any write is, and the page store keeps both writes."""
    from leaf_website.storage import PUBLISHER, PageStoreRefused, restore

    publish(page_dir)
    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/example": ("page", "example")})
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))

    def write(context, attempt, expect=()):
        return drafts_model.write_draft(
            private,
            {
                "context": context,
                "expect": list(expect),
                "record": {"attempt": attempt, "text": f"Words {attempt}"},
            },
        )

    with durable_page_store() as (store_url, stored):
        monkeypatch.setenv("LEAF_PAGE_STORE_URL", store_url)
        assert restore(site)
        monkeypatch.setenv("LEAF_PAGE_COMMIT", PUBLISHER)
        write("general", "a1")
        stored["lose"] = True
        with pytest.raises(PageStoreRefused):
            write("general", "a2", ["a1"])
        answer = write("reply:other", "b1")
        assert answer["written"]
        assert answer["version"] == 3
        assert drafts_model.read_drafts(private) == stored["drafts"]["/example"]

        shutil.rmtree(private)
        shutil.copytree(page_dir, private)
        assert restore(site)
    restored = drafts_model.read_drafts(private)
    assert restored["version"] == 3
    assert {
        context: draft["attempt"] for context, draft in restored["drafts"].items()
    } == {
        "general": "a2",
        "reply:other": "b1",
    }
