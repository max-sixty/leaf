"""Commit website page records and frozen HTTP delivery outside the container.

Python remains the sole owner of activation, event admission and projection. A
successful page transaction publishes its canonical record and asleep responses
together to the container's Durable Object before acknowledging the write. The
record overlays this release's immutable image on startup; captured responses are
disposable delivery output and never an input to a fold. Responses retain their
exact bytes: the separately bundled public assets are a different module graph.

The user's drafts change with every keystroke and move no page reading
(`reading.UNWATCHED`), so they take a path of their own. Each write of a page's drafts
store replaces the Durable Object's copy of the store before the container replaces
its file or answers the write (`publish_drafts`), so a replacement container restores
every write a tab was answered for. While the container sleeps, the object serves that copy as `api/drafts`
and as `api/news`'s `drafts`, in place of what the page's last commit captured. A
page's record leaves `drafts.json` out, so no commit, however late it lands, puts an
older store back.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import ssl
import tarfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from functools import partial
from http.client import HTTPResponse
from pathlib import Path
from tempfile import TemporaryFile
from types import SimpleNamespace
from typing import BinaryIO
from urllib.parse import urlsplit

import anyio
from starlette.datastructures import Headers
from starlette.requests import Request

from leaf.drafts import DRAFTS, read_drafts
from leaf.files import latest_revision, revision_path
from leaf.http import assets_path
from leaf.page_snapshot import capture_page_snapshot
from leaf.revision_artifact import read_revision
from leaf.revisioning import activate_source
from leaf.runtime_selection import executing, execution_identity
from leaf.schema import (
    DRAFTS_FILE,
    MEDIA_DIR,
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    PAGE_PROCESS_FILES,
)
from leaf.served_state.reading import record_reading
from leaf.service import PageTransaction
from leaf.state import STRING, Record, described, object_schema, page_key, state_home

CHUNK_BYTES = 1024 * 1024
# Chunk uploads in flight at once.
UPLOADS = 8


class PageStoreRefused(OSError):
    """A call the page store answered with an error, carrying the store's reason
    (`worker/src/index.ts`, the `leaf-state.internal` handler), which a page fault
    records as its detail. An `OSError`, as urllib's own errors are, so callers
    handle it as they handle the store being unreachable."""


@contextmanager
def _request(path: str, payload: dict | bytes | None = None) -> Generator[HTTPResponse]:
    url = os.environ["LEAF_PAGE_STORE_URL"].rstrip("/") + path
    binary = path.startswith("/blobs/")
    request = urllib.request.Request(
        url,
        data=(
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload, separators=(",", ":")).encode()
        )
        if payload is not None
        else None,
        method="PUT" if payload is not None else "GET",
        headers={
            "Content-Type": "application/octet-stream" if binary else "application/json"
        },
    )
    certificate = os.environ.get("CODEX_CA_CERTIFICATE")
    context = ssl.create_default_context(cafile=certificate) if certificate else None
    try:
        response = urllib.request.urlopen(request, context=context, timeout=60)
    except urllib.error.HTTPError as error:
        reason = error.read().decode(errors="replace").strip()
        raise PageStoreRefused(f"{path} answered {error.code}: {reason}") from error
    with response:
        yield response


@dataclass
class _BlobSet:
    """One transfer's unique chunk bytes, spooled without retaining media history."""

    buffer: BinaryIO
    offsets: dict[str, tuple[int, int]] = field(default_factory=dict)
    # The uploads read their bodies from several threads, and a read is a seek then
    # a read of the one shared buffer.
    reading: threading.Lock = field(default_factory=threading.Lock)

    def add(self, digest: str, chunk: bytes) -> None:
        self.buffer.seek(0, os.SEEK_END)
        self.offsets[digest] = (self.buffer.tell(), len(chunk))
        self.buffer.write(chunk)

    def chunks(self, data: bytes) -> dict:
        result = []
        for offset in range(0, len(data), CHUNK_BYTES):
            chunk = data[offset : offset + CHUNK_BYTES]
            digest = hashlib.sha256(chunk).hexdigest()
            if digest not in self.offsets:
                self.add(digest, chunk)
            result.append(digest)
        return {"chunks": result}

    def body(self, digest: str) -> bytes:
        offset, length = self.offsets[digest]
        with self.reading:
            self.buffer.seek(offset)
            return self.buffer.read(length)


def restore(site_root: Path) -> bool:
    """Restore before serving, from the snapshot contract in worker/src/storage.ts, and
    say whether a page store backs the site, as the container then declares its
    commits are published there (`PUBLISHER`)."""
    if not os.environ.get("LEAF_PAGE_STORE_URL"):
        return False
    from leaf_website import SITE_MANIFEST, elapsed_ms, log_agent

    started = time.monotonic()
    files = 0
    manifest = json.loads((site_root / SITE_MANIFEST).read_text())
    # Revisions and neighboring pages share most assets. Download one snapshot
    # containing each canonical digest once, before replacing any local inputs.
    with TemporaryFile() as buffer:
        blobs = _BlobSet(buffer)
        with (
            _request("/records") as response,
            tarfile.open(fileobj=response, mode="r|") as archive,
        ):
            first = archive.next()
            if first is None or first.name != "records.json":
                raise ValueError("page restore snapshot has no records")
            record_file = archive.extractfile(first)
            assert record_file is not None
            snapshot = json.load(record_file)
            records = snapshot["records"]
            while member := archive.next():
                blob_file = archive.extractfile(member)
                assert blob_file is not None
                blobs.add(member.name, blob_file.read())
        if any(
            digest not in blobs.offsets
            for record in records.values()
            for content in record.values()
            for digest in content["chunks"]
        ):
            raise ValueError("page restore snapshot is missing referenced chunks")
        for root, record in records.items():
            directory = _page_directory(site_root, manifest, root)
            targets = []
            for name, content in record.items():
                target = (directory / name).resolve()
                if not target.is_relative_to(directory) or target == directory:
                    raise ValueError("invalid stored page record path")
                targets.append((content, target))
            # These trees are complete inputs, not patches over the release.
            # Replacing them also preserves deletion of a published input.
            for name in PAGE_OWNED_DIRS:
                if name == "revisions":
                    continue
                if (directory / name).exists():
                    shutil.rmtree(directory / name)
            for name in PAGE_OWNED_FILES:
                (directory / name).unlink(missing_ok=True)
            for content, target in targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("wb") as output:
                    for digest in content["chunks"]:
                        output.write(blobs.body(digest))
                os.utime(target, (content["modified"], content["modified"]))
                files += 1
        for root, drafts in snapshot["drafts"].items():
            DRAFTS.write(
                _page_directory(site_root, manifest, root) / DRAFTS_FILE, drafts
            )
        log_agent(
            "page_restore_completed",
            durationMs=elapsed_ms(started),
            files=files,
            chunks=len(blobs.offsets),
            bytes=sum(length for _, length in blobs.offsets.values()),
        )
    return True


def _page_directory(site_root: Path, manifest: dict, root: str) -> Path:
    directory = (site_root / manifest["pages"][root]["directory"]).resolve()
    if not directory.is_relative_to(site_root.resolve()):
        raise ValueError("stored page directory escapes site root")
    return directory


def _upload(blobs: _BlobSet, digest: str) -> None:
    with _request(f"/blobs/{digest}", blobs.body(digest)):
        pass


def _record_files(page_dir: Path, published: set[int]) -> list[Path]:
    # The drafts store is published on its own (`publish_drafts`).
    files = [
        page_dir / name
        for name in PAGE_OWNED_FILES
        if name not in PAGE_PROCESS_FILES and name != DRAFTS_FILE
    ]
    for name in PAGE_OWNED_DIRS:
        if name != "revisions":
            files.extend(
                path for path in (page_dir / name).rglob("*") if path.is_file()
            )
    for path in (page_dir / "revisions").glob("r*-*"):
        # Published revisions already live in the same release's image. Only the
        # private additions belong to the per-session durable record.
        number = int(path.name.split("-", 1)[0][1:])
        if number not in published:
            files.extend(path.rglob("*") if path.is_dir() else [path])
    return sorted(path for path in files if path.is_file())


def _record(page_dir: Path, files: list[Path], blobs: _BlobSet) -> dict:
    return {
        path.relative_to(page_dir).as_posix(): {
            **blobs.chunks(path.read_bytes()),
            "modified": path.stat().st_mtime,
        }
        for path in files
    }


def _responses(
    page: PageTransaction,
    site_root: Path,
    manifest: dict,
    root: str,
    source_error: str | None,
    blobs: _BlobSet,
) -> dict:
    # A transaction can finish inside the website's event loop. Capture its ASGI
    # responses in one other thread then, where anyio can own a fresh loop.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(
                _responses, page, site_root, manifest, root, source_error, blobs
            ).result()
    from leaf_website import WebsitePageEndpoint, page_routes

    revision = latest_revision(page.page_dir)
    assert revision is not None
    source = read_revision(page.page_dir, revision)
    snapshot = capture_page_snapshot(
        page.page_dir,
        source.document,
        revision,
        url=f"/revisions/{revision_path(page.page_dir, revision).name}",
        transaction=page,
        process=False,
    )
    # Reading the drafts settles the generations this commit's sends carried, and
    # starts a store for a page that has none, publishing either (`publish_drafts`).
    # The Durable Object serves its own copy of the store in place of the one
    # captured here.
    snapshot = replace(
        snapshot, source_error=source_error, frozen_drafts=read_drafts(page.page_dir)
    )
    paths = {"", "api/state", "api/news", "api/drafts", "registry.json"}
    paths.update(f"api/state?revision={item}" for item in snapshot.artifacts)
    published = set(map(int, manifest["pages"][root]["states"]))
    for item, artifact in snapshot.artifacts.items():
        if item in published:
            continue
        paths.add(f"revisions/{snapshot.revision_names[item]}")
        # Where the container serves the revision's resources, which the revisions
        # that differ only in their document share. Media answers at the page root
        # (below), never there.
        served = assets_path(execution_identity(artifact)).lstrip("/")
        for logical in set(executing(artifact).resources) | set(
            artifact.widget_aliases
        ):
            if not logical.startswith(f"/{MEDIA_DIR}/"):
                paths.add(f"{served}{logical}")
    paths.update(
        f"versions/v{version['version']}.html" for version in snapshot.context.versions
    )
    paths.update(
        f"media/{path.name}"
        for path in (page.page_dir / "media").glob("*")
        if path.is_file()
    )
    routes = page_routes(site_root, manifest["pages"])
    result = {}
    for path in sorted(paths):
        address = urlsplit(f"{root.rstrip('/')}/{path}")
        request_sent = False

        async def receive():
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {"type": "http.request", "body": b"", "more_body": False}
            # This capture has no client to disconnect while a file streams.
            await asyncio.Event().wait()

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "scheme": "https",
                "server": ("leaf.page", 443),
                "path": address.path,
                "query_string": address.query.encode(),
                "headers": [],
            },
            receive,
        )
        endpoint = WebsitePageEndpoint(
            request,
            SimpleNamespace(server_id=f"website-{manifest['release']}"),
            routes=routes,
            pages=manifest["pages"],
            release=manifest["release"],
            agent_harness=None,
        )
        endpoint.page_snapshot = snapshot
        endpoint.housekeeping = True
        messages = []

        async def capture(message, messages=messages):
            messages.append(message)

        anyio.run(endpoint, request.scope, request.receive, capture)
        response, *body = messages
        if response["status"] != 200:
            raise RuntimeError(
                f"cannot publish saved page response {path}: {response['status']}"
            )
        result[path] = {
            "headers": dict(Headers(raw=response["headers"])),
            **blobs.chunks(b"".join(chunk["body"] for chunk in body)),
        }
    return result


PUBLISHED = Record(
    "website-publication",
    described(
        "What leaf.page's container last published of a page, in its state home's "
        "`website-publications/<page key>.json`, so an unchanged page is not "
        "published again.",
        object_schema(
            {
                "fingerprint": described(
                    "The page reading the publication was made from "
                    "(`record_reading`).",
                    STRING,
                ),
            }
        ),
    ),
    since=51,
)


# The page commit provider (`service.commit_provider`) a container declares once it
# has restored its pages, so every transaction its leaf processes finish publishes its
# record (`publish`), and every write of a page's drafts its drafts (`publish_drafts`).
PUBLISHER = "leaf_website.storage"


def _published(page_dir: Path) -> Path:
    return state_home() / "website-publications" / f"{page_key(page_dir)}.json"


def _site() -> tuple[Path, dict]:
    from leaf_website import SITE_MANIFEST

    site_root = Path(os.environ["LEAF_SITE_ROOT"]).resolve()
    return site_root, json.loads((site_root / SITE_MANIFEST).read_text())


def _page_root(page_dir: Path) -> tuple[Path, dict, str] | None:
    """The site, its manifest and the root the site serves `page_dir` at, or None
    where it serves the directory at none."""
    site_root, manifest = _site()
    for root, value in manifest["pages"].items():
        if (site_root / value["directory"]).resolve() == page_dir.resolve():
            return site_root, manifest, root
    return None


def publish(page: PageTransaction) -> None:
    """Publish a page whose reading moved since this container last published it,
    under the caller's append lease; failure remains a failed commit."""
    if not os.environ.get("LEAF_PAGE_STORE_URL"):
        return
    if (site := _page_root(page.page_dir)) is None:
        return
    site_root, manifest, root = site
    activation = activate_source(page.page_dir, transaction=page)
    fingerprint = record_reading(page.page_dir)
    token = _published(page.page_dir)
    published = PUBLISHED.read(token)
    if published is not None and published["fingerprint"] == fingerprint:
        return
    files = _record_files(
        page.page_dir, set(map(int, manifest["pages"][root]["states"]))
    )
    with TemporaryFile() as buffer:
        blobs = _BlobSet(buffer)
        record = _record(page.page_dir, files, blobs)
        responses = _responses(page, site_root, manifest, root, activation.error, blobs)
        publication = {
            "root": root,
            "release": manifest["release"],
            "record": record,
            "responses": responses,
        }
        with _request("/prepare", publication) as response:
            prepared = json.load(response)
        # Each upload is a round trip to the Durable Object, and a session's first
        # write uploads its whole record, so they overlap rather than queue.
        with ThreadPoolExecutor(max_workers=UPLOADS) as uploads:
            for _ in uploads.map(partial(_upload, blobs), prepared["missing"]):
                pass
        with _request("/publication", {"root": root, "identity": prepared["identity"]}):
            pass
    token.parent.mkdir(parents=True, exist_ok=True)
    PUBLISHED.write(token, {"fingerprint": fingerprint})


def publish_drafts(page_dir: Path, drafts: dict) -> None:
    """Replace the Durable Object's copy of a page's drafts store, which `drafts.py`
    calls under the store's lock before it replaces the file; failure fails the write.
    The store travels whole in one request, since it holds only what the user is
    writing."""
    if (site := _page_root(page_dir)) is None:
        return
    _site_root, manifest, root = site
    body = {"root": root, "release": manifest["release"], "drafts": drafts}
    with _request("/drafts", body):
        pass
