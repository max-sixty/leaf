"""Commit website page records and frozen HTTP delivery outside the container.

Python remains the sole owner of activation, event admission and projection. A
successful page transaction publishes its canonical record and asleep responses
together to the container's Durable Object before acknowledging the write. The
record overlays this release's immutable image on startup; captured responses are
disposable delivery output and never an input to a fold. Responses retain their
exact bytes: the separately bundled public assets are a different module graph.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import ssl
import tarfile
import time
import urllib.request
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from http.client import HTTPResponse
from pathlib import Path
from tempfile import TemporaryFile
from types import SimpleNamespace
from typing import BinaryIO
from urllib.parse import urlencode, urlsplit

import anyio
from starlette.datastructures import Headers
from starlette.requests import Request

from leaf.data import deferred_records
from leaf.files import latest_revision, revision_path
from leaf.page_snapshot import capture_page_snapshot
from leaf.revision_artifact import read_revision
from leaf.revisioning import activate_source
from leaf.runtime_selection import executing, serving_runtime
from leaf.schema import (
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    PAGE_PROCESS_FILES,
)
from leaf.served_state.reading import record_reading
from leaf.service import PageTransaction
from leaf.state import STRING, Record, described, object_schema, page_key, state_home

CHUNK_BYTES = 1024 * 1024


@contextmanager
def _request(path: str, payload: dict | bytes | None = None) -> Iterator[HTTPResponse]:
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
    with urllib.request.urlopen(request, context=context, timeout=60) as response:
        yield response


@dataclass
class _BlobSet:
    """One transfer's unique chunk bytes, spooled without retaining media history."""

    buffer: BinaryIO
    offsets: dict[str, tuple[int, int]] = field(default_factory=dict)

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
        self.buffer.seek(offset)
        return self.buffer.read(length)


def restore(site_root: Path) -> None:
    """Restore before serving, from the snapshot contract in worker/src/storage.ts."""
    if not os.environ.get("LEAF_PAGE_STORE_URL"):
        return
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
            records = json.load(archive.extractfile(first))
            while member := archive.next():
                blobs.add(member.name, archive.extractfile(member).read())
        if any(
            digest not in blobs.offsets
            for record in records.values()
            for content in record.values()
            for digest in content["chunks"]
        ):
            raise ValueError("page restore snapshot is missing referenced chunks")
        for root, record in records.items():
            directory = (site_root / manifest["pages"][root]["directory"]).resolve()
            if not directory.is_relative_to(site_root.resolve()):
                raise ValueError("stored page directory escapes site root")
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
        log_agent(
            "page_restore_completed",
            durationMs=elapsed_ms(started),
            files=files,
            chunks=len(blobs.offsets),
            bytes=sum(length for _, length in blobs.offsets.values()),
        )
    os.environ["LEAF_PAGE_COMMIT"] = "leaf_website.storage:publish"


def _record_files(page_dir: Path, published: set[int]) -> list[Path]:
    files = [
        page_dir / name for name in PAGE_OWNED_FILES if name not in PAGE_PROCESS_FILES
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
    source = read_revision(page.page_dir, revision)
    snapshot = capture_page_snapshot(
        page.page_dir,
        source.document,
        revision,
        url=f"/revisions/{revision_path(page.page_dir, revision).name}",
        transaction=page,
        process=False,
    )
    snapshot = replace(snapshot, source_error=source_error)
    paths = {"", "api/state", "api/news", "registry.json"}
    paths.update(f"api/state?revision={item}" for item in snapshot.artifacts)
    for source_name, reading in snapshot.context.data["sources"].items():
        value = reading.get("value")
        spec = deferred_records(value, reading["contract"], snapshot.context.registry)
        if spec is not None:
            paths.update(
                "api/deferred?"
                + urlencode(
                    {
                        "source": source_name,
                        "source_revision": reading["revision"],
                        "key": record[spec["key"]],
                    }
                )
                for record in value[spec["items"]]
                if spec["deferred"] in record
            )
    published = set(map(int, manifest["pages"][root]["states"]))
    for item, artifact in snapshot.artifacts.items():
        if item in published:
            continue
        name = snapshot.revision_names[item]
        paths.add(f"revisions/{name}")
        # Where the container serves the revision's resources: beside the runtime it
        # runs, under that runtime's identity (`http.PageEndpoint._named_root`).
        served = f"revisions/{name.removesuffix('.html')}/{serving_runtime().identity}"
        for logical in set(executing(artifact).resources) | set(
            artifact.widget_aliases
        ):
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
                )
            }
        ),
    ),
    since=13,
)


def publish(page: PageTransaction) -> None:
    """Publish under the caller's append lease; failure remains a failed commit."""
    if not os.environ.get("LEAF_PAGE_STORE_URL"):
        return
    from leaf_website import SITE_MANIFEST

    site_root = Path(os.environ["LEAF_SITE_ROOT"]).resolve()
    manifest = json.loads((site_root / SITE_MANIFEST).read_text())
    root = next(
        (
            root
            for root, value in manifest["pages"].items()
            if (site_root / value["directory"]).resolve() == page.page_dir
        ),
        None,
    )
    if root is None:
        return
    activation = activate_source(page.page_dir, transaction=page)
    fingerprint = record_reading(page.page_dir)
    token = state_home() / "website-publications" / f"{page_key(page.page_dir)}.json"
    if (published := PUBLISHED.read(token)) and published["fingerprint"] == fingerprint:
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
        for digest in prepared["missing"]:
            with _request(f"/blobs/{digest}", blobs.body(digest)):
                pass
        with _request("/publication", {"root": root, "identity": prepared["identity"]}):
            pass
    token.parent.mkdir(parents=True, exist_ok=True)
    PUBLISHED.write(token, {"fingerprint": fingerprint})
