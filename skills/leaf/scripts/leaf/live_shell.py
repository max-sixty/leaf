"""Materialize the immutable HTTP half of a live Leaf page."""

from pathlib import Path

from .event_log import read_events
from .files import (
    latest_revision,
    list_revisions,
    published_versions,
    revision_path,
    stamped_version,
    version_revisions,
)
from .http import scope_document_routes, scope_page_routes, supervised_document
from .registry.storage import layer_metadata
from .schema import BROWSER_DIRS, MEDIA_DIR, SERVED_PATH, VENDORED_FILES


def write_live_shell(
    page_dir: Path,
    destination: Path,
    *,
    page_root: str = "",
    server_id: str = "published",
    release_id: str | None = None,
    asset_root: str | None = None,
) -> None:
    """Write live documents and browser assets without copying session state.

    The runtime and its API routes remain unchanged. A static host may serve this
    derived tree while the canonical Leaf server answers those API routes.
    """
    events = read_events(page_dir)
    active = latest_revision(page_dir)
    if active is None:
        raise ValueError(f"{page_dir} has no active revision")
    versions = version_revisions(events)
    reverse_versions = {revision: version for version, revision in versions.items()}
    identity = layer_metadata(page_dir)
    bootstrap = (page_dir / "runtime" / "bootstrap.js").read_text(encoding="utf-8")

    def write(relative: Path, body: bytes) -> None:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError(f"live shell path already exists: {target}")
        target.write_bytes(body)

    def document(revision: int, version: int | None) -> bytes:
        source = revision_path(page_dir, revision).read_text(encoding="utf-8")
        return scope_document_routes(
            supervised_document(
                source,
                revision,
                version,
                server_id=server_id,
                layer_id=identity["generation"],
                bootstrap=bootstrap,
                release_id=release_id,
                page_root=page_root,
            ),
            page_root,
            asset_root=asset_root,
        )

    write(Path("index.html"), document(active, stamped_version(events, active)))
    for version in published_versions(page_dir, events):
        write(
            Path("versions") / f"v{version}.html", document(versions[version], version)
        )
    for revision in list_revisions(page_dir):
        write(
            Path("revisions") / revision_path(page_dir, revision).name,
            document(revision, reverse_versions.get(revision)),
        )

    for name in (*VENDORED_FILES, *BROWSER_DIRS, MEDIA_DIR):
        source = page_dir / name
        files = [source] if source.is_file() else sorted(source.rglob("*"))
        for file in files:
            if not file.is_file():
                continue
            relative = file.relative_to(page_dir)
            if not SERVED_PATH.fullmatch(f"/{relative.as_posix()}"):
                continue
            body = file.read_bytes()
            if file.suffix in {".css", ".js"}:
                body = scope_page_routes(body, page_root, asset_root=asset_root)
            write(relative, body)
