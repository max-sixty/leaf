"""Commit website page records and frozen HTTP delivery outside the container.

Python remains the sole owner of activation, event admission and projection. A
successful page transaction publishes its canonical record and asleep responses
together to the container's Durable Object before acknowledging the write. The
record overlays this release's immutable image on startup; captured responses are
disposable delivery output and never an input to a fold. Responses retain their
exact bytes: the separately bundled public assets are a different module graph.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import ssl
import urllib.request
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryFile
from types import SimpleNamespace
from typing import BinaryIO
from urllib.parse import urlencode, urlsplit

from leaf.data import deferred_records
from leaf.files import active_descriptor, latest_revision, revision_path
from leaf.machine import state_home
from leaf.page_snapshot import capture_page_snapshot
from leaf.revision_artifact import read_revision
from leaf.revisioning import activate_source
from leaf.schema import (
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    PAGE_PROCESS_FILES,
    UNNAMED_AGENT,
)
from leaf.service import PageTransaction
from leaf.state import page_key, write_json
from starlette.requests import Request

CHUNK_BYTES = 1024 * 1024


def _request(path: str, payload: dict | bytes | None = None) -> dict | bytes:
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
        if response.status == 204:
            return {}
        return response.read() if binary else json.load(response)


@dataclass
class _BlobSet:
    """One publication's unique chunk bytes, spooled without retaining media history."""

    buffer: BinaryIO
    offsets: dict[str, tuple[int, int]] = field(default_factory=dict)

    def chunks(self, data: bytes) -> dict:
        result = []
        for offset in range(0, len(data), CHUNK_BYTES):
            chunk = data[offset : offset + CHUNK_BYTES]
            digest = hashlib.sha256(chunk).hexdigest()
            if digest not in self.offsets:
                self.offsets[digest] = (self.buffer.tell(), len(chunk))
                self.buffer.write(chunk)
            result.append(digest)
        return {"chunks": result}

    def body(self, digest: str) -> bytes:
        offset, length = self.offsets[digest]
        self.buffer.seek(offset)
        return self.buffer.read(length)


def restore(site_root: Path) -> None:
    """Restore durable records before any HTTP request or agent can change them."""
    if not os.environ.get("LEAF_PAGE_STORE_URL"):
        return
    from leaf_website import SITE_MANIFEST

    manifest = json.loads((site_root / SITE_MANIFEST).read_text())
    for root, record in _request("/records").items():
        record = json.loads(
            b"".join(_request(f"/blobs/{digest}") for digest in record["chunks"])
        )
        directory = (site_root / manifest["pages"][root]["directory"]).resolve()
        if not directory.is_relative_to(site_root.resolve()):
            raise ValueError("stored page directory escapes site root")
        targets = []
        links = []
        for name, content in record.items():
            target = (directory / name).resolve()
            if not target.is_relative_to(directory) or target == directory:
                raise ValueError("invalid stored page record path")
            if "asset" in content:
                source = (directory / content["asset"]).resolve()
                if not source.is_relative_to(directory / "revisions"):
                    raise ValueError("invalid stored page resource reference")
                links.append((source, target))
            else:
                targets.append((content["chunks"], target))
        # These trees are complete inputs, not patches over the release.
        # Replacing them also preserves deletion of a published input.
        for name in PAGE_OWNED_DIRS:
            if name == "revisions":
                continue
            if (directory / name).exists():
                shutil.rmtree(directory / name)
        for name in PAGE_OWNED_FILES:
            (directory / name).unlink(missing_ok=True)
        for chunks, target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as output:
                for digest in chunks:
                    output.write(_request(f"/blobs/{digest}"))
        for source, target in links:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.unlink(missing_ok=True)
            if target.is_relative_to(directory / "revisions"):
                os.link(source, target)
            else:
                shutil.copyfile(source, target)
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


@lru_cache(maxsize=8)
def _baseline_files(page_dir: Path, published: tuple[int, ...]) -> dict[bytes, str]:
    """Immutable same-release files already installed in a replacement image."""
    result = {}
    for revision in published:
        marker = revision_path(page_dir, revision)
        for path in (marker, *marker.with_suffix("").rglob("*")):
            if path.is_file():
                result[hashlib.sha256(path.read_bytes()).digest()] = path.relative_to(
                    page_dir
                ).as_posix()
    return result


def _record(
    page_dir: Path, files: list[Path], published: set[int], blobs: _BlobSet
) -> dict:
    baseline = _baseline_files(page_dir, tuple(sorted(published)))
    record = {}
    for path in files:
        name = path.relative_to(page_dir).as_posix()
        data = path.read_bytes()
        source = baseline.get(hashlib.sha256(data).digest())
        record[name] = {"asset": source} if source is not None else blobs.chunks(data)
    return blobs.chunks(json.dumps(record, separators=(",", ":")).encode())


def _responses(
    page: PageTransaction,
    site_root: Path,
    manifest: dict,
    root: str,
    source_error: str | None,
    blobs: _BlobSet,
) -> dict:
    from leaf_website import WebsitePageEndpoint

    revision = latest_revision(page.page_dir)
    source = read_revision(page.page_dir, revision)
    snapshot = capture_page_snapshot(
        page.page_dir,
        source.document,
        revision,
        url=f"/revisions/{revision_path(page.page_dir, revision).name}",
        transaction=page,
    )
    # An asleep publication is a reading without a process. Feed that fact into
    # the same activity fold rather than persisting a claim or expiring it in JS.
    presence = {
        **snapshot.context.presence,
        "status": {"state": "waiting", "detail": ""},
        "listening": False,
        "session_alive": None,
        "live_turn": None,
        "agent": UNNAMED_AGENT,
        "claim_session": None,
        "claim_turn": None,
        "turn_closed": None,
        "turn_opened": None,
        "turn_takes_input": False,
        "session_cwd": None,
        "viewed": None,
    }
    snapshot = replace(
        snapshot,
        context=replace(
            snapshot.context,
            active=active_descriptor(page.page_dir, page.events),
            presence=presence,
            live_stream=None,
        ),
        others=(),
        source_error=source_error,
    )
    paths = {"", "api/state", "api/news", "api/user-view", "registry.json"}
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
        for logical in set(artifact.resources) | set(artifact.widget_aliases):
            path = f"revisions/{name.removesuffix('.html')}{logical}"
            paths.add(path)
    paths.update(
        f"versions/v{version['version']}.html" for version in snapshot.context.versions
    )
    paths.update(
        f"media/{path.name}"
        for path in (page.page_dir / "media").glob("*")
        if path.is_file()
    )
    result = {}
    for path in sorted(paths):
        address = urlsplit(f"{root.rstrip('/')}/{path}")
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "scheme": "https",
                "server": ("leaf.page", 443),
                "path": address.path,
                "query_string": address.query.encode(),
                "headers": [],
            }
        )
        endpoint = WebsitePageEndpoint(
            request,
            SimpleNamespace(server_id=f"website-{manifest['release']}"),
            site_root=site_root,
            pages=manifest["pages"],
            release=manifest["release"],
            agent_harness=None,
        )
        endpoint.page_snapshot = snapshot
        endpoint.housekeeping = True
        response = endpoint.respond()
        if response.status_code != 200:
            raise RuntimeError(
                f"cannot publish saved page response {path}: {response.status_code}"
            )
        result[path] = {
            "status": response.status_code,
            "headers": dict(response.headers),
            **blobs.chunks(response.body),
        }
    return result


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
    files = _record_files(
        page.page_dir, set(map(int, manifest["pages"][root]["states"]))
    )
    fingerprint = hashlib.sha256(
        repr(
            [
                (
                    str(path.relative_to(page.page_dir)),
                    path.stat().st_mtime_ns,
                    path.stat().st_size,
                )
                for path in files
            ]
        ).encode()
    ).hexdigest()
    token = state_home() / "website-publications" / f"{page_key(page.page_dir)}.json"
    if token.is_file() and json.loads(token.read_text())["fingerprint"] == fingerprint:
        return
    with TemporaryFile() as buffer:
        blobs = _BlobSet(buffer)
        record = _record(
            page.page_dir,
            files,
            set(map(int, manifest["pages"][root]["states"])),
            blobs,
        )
        responses = _responses(page, site_root, manifest, root, activation.error, blobs)
        missing = _request("/missing", {"digests": list(blobs.offsets)})["missing"]
        for digest in missing:
            _request(f"/blobs/{digest}", blobs.body(digest))
        _request(
            "/publication",
            {
                "root": root,
                "release": manifest["release"],
                "record": record,
                "responses": responses,
            },
        )
    token.parent.mkdir(parents=True, exist_ok=True)
    write_json(token, {"fingerprint": fingerprint})
