"""Materialize the immutable HTTP half of a live Leaf page.

Every document selects its captured registry, bootstrap, layer, and authored
resources. Revision resource trees share the same logical URLs as HTTP delivery,
including widget aliases resolved through implementation provenance. Mutable
candidate inputs never participate in publishing. Content-addressed media is written
at the page root, where every document, message, and card addresses it.
"""

import json
from dataclasses import replace
from pathlib import Path

from .event_log import read_events
from .files import (
    latest_revision,
    list_revisions,
    published_versions,
    revision_path,
    version_revisions,
)
from .http import page_delivery
from .revision_artifact import read_artifact
from .revision_delivery import DeliveryAddress, compose_document, deliver_resource
from .schema import MEDIA_DIR, SERVED_PATH


def write_live_shell(
    page_dir: Path,
    destination: Path,
    *,
    page_root: str = "",
    server_id: str = "published",
    release_id: str | None = None,
    asset_root: str | None = None,
    head: str = "",
) -> None:
    """Write live documents and browser assets without copying session state.

    The runtime and its API routes remain unchanged. A static host may serve this
    derived tree while the canonical Leaf server answers those API routes. `head` is
    the host's own metadata in each document (`Delivery.head`).

    Each document's script nonce is minted here, once, and every user of that
    release receives the same one in the page source. It still admits only the inline
    scripts delivery composed, but it is not a secret the way a per-response nonce is:
    markup able to read the page could carry it.
    """
    events = read_events(page_dir)
    active = latest_revision(page_dir)
    if active is None:
        raise ValueError(f"{page_dir} has no active revision")
    versions = version_revisions(events)
    reverse_versions = {revision: version for version, revision in versions.items()}

    def write(relative: Path, body: bytes) -> None:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError(f"live shell path already exists: {target}")
        target.write_bytes(body)

    documents = {}
    for revision in list_revisions(page_dir):
        artifact = read_artifact(page_dir, revision)
        relative_root = Path("revisions") / revision_path(page_dir, revision).stem
        root = asset_root if asset_root is not None else page_root
        revision_root = root.rstrip("/") + "/" + relative_root.as_posix()
        version = reverse_versions.get(revision)
        delivery = page_delivery(
            artifact.resources,
            server_id=server_id,
            layer_id=artifact.registry["$layer"]["generation"],
            release_id=release_id,
            page_root=page_root,
            asset_root=revision_root,
        )
        documents[revision] = compose_document(
            artifact.html.decode("utf-8"),
            revision,
            version,
            executable=artifact.executable,
            widgets=artifact.widgets,
            resources=artifact.resources,
            registry=artifact.registry,
            delivery=replace(delivery, head=head),
        ).encode()
        aliases = {
            f"/widgets/{tag}.js": implementation["path"]
            for tag, implementation in artifact.implementations.items()
        }
        address = DeliveryAddress(page_root, revision_root)
        for logical in sorted(artifact.resources.keys() | aliases.keys()):
            source = aliases.get(logical, logical)
            body = (
                f"export * from {json.dumps(revision_root + source)};\n".encode()
                if logical != source
                else deliver_resource(artifact.resources[source], source, address)
            )
            write(relative_root / logical.lstrip("/"), body)

    write(Path("index.html"), documents[active])
    for version in published_versions(page_dir, events):
        write(Path("versions") / f"v{version}.html", documents[versions[version]])
    for revision in list_revisions(page_dir):
        write(
            Path("revisions") / revision_path(page_dir, revision).name,
            documents[revision],
        )

    for file in sorted((page_dir / MEDIA_DIR).rglob("*")):
        relative = file.relative_to(page_dir)
        if file.is_file() and SERVED_PATH.fullmatch(f"/{relative.as_posix()}"):
            write(relative, file.read_bytes())
