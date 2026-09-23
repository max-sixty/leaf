"""Disposable page instances built from an authored template and its captured layer.

A specimen owns an ordinary source, revision, data store, and event log. Its parent
supplies immutable resources and optional selected conversation history, never a live
state projection. Its browser dependency URLs retain the creating parent's exact
immutable resource namespace, including through nested children; only the document
and API identity are new. Browser gestures enter the ordinary page event door. The
HTTP server owns these directories until explicit release or server shutdown.
"""

import json
import secrets
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

from .data import source_file
from .event_log import now_iso, read_events
from .files import write_json
from .revision_artifact import RevisionArtifact
from .revisioning import activate_source
from .schema import DATA_DIR, DATA_FILE
from .structure import SourceDocument
from .thread_context import specimen_events


@dataclass
class Specimen:
    temporary: TemporaryDirectory
    parent: Path
    layer: dict
    passive: bool
    asset_root: str
    lock: Lock = field(default_factory=Lock)
    closed: bool = False

    @property
    def directory(self) -> Path:
        return Path(self.temporary.name)

    def close(self) -> None:
        with self.lock:
            self.closed = True
            self.temporary.cleanup()


class Specimens:
    """The child pages of one HTTP server, scoped to their creating parent."""

    def __init__(self) -> None:
        self.pages: dict[str, Specimen] = {}
        self.lock = Lock()

    def create(
        self,
        parent: Path,
        artifact: RevisionArtifact,
        events: list,
        data: dict,
        template_id: str,
        passive: bool,
        asset_root: str,
    ) -> str:
        document = SourceDocument(artifact.html.decode("utf-8"))
        template = next(
            (
                specimen
                for specimen in document.specimens
                if specimen["attrs"].get("id") == template_id
            ),
            None,
        )
        if template is None:
            raise ValueError(f"unknown specimen template {template_id!r}")
        selected = set(template["attrs"].get("data-specimen-threads", "").split())
        seeded = specimen_events(document, events, selected)
        source = template["document"].data
        temporary = TemporaryDirectory(prefix="leaf-specimen-")
        child = Path(temporary.name)
        try:
            for logical, resource in artifact.resources.items():
                target = child / logical.removeprefix("/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(resource.data)
            # Message attachments are content-addressed page data, not necessarily
            # dependencies of the authored revision. Preserve those bytes too.
            if (parent / "media").is_dir():
                shutil.copytree(parent / "media", child / "media", dirs_exist_ok=True)
            # The child reads the data the parent reading it was built from held,
            # which for a frozen preview is not what the parent's files hold now.
            write_json(
                child / DATA_FILE,
                {
                    "sources": {
                        name: {"contract": reading["contract"]}
                        for name, reading in data["sources"].items()
                    }
                },
            )
            (child / DATA_DIR).mkdir()
            for name, reading in data["sources"].items():
                if "value" in reading:
                    write_json(source_file(child, name), reading["value"])
            (child / "index.html").write_bytes(source)
            (child / "events.jsonl").write_text(
                "".join(json.dumps(event) + "\n" for event in seeded),
                encoding="utf-8",
            )
            write_json(
                child / "status.json",
                {
                    "state": "waiting",
                    "detail": "",
                    "ts": now_iso(),
                    "after": 0,
                    "stated": False,
                },
            )
            activation = activate_source(child, read_events(child))
            if activation.error:
                raise ValueError(f"invalid specimen: {activation.error}")
        except BaseException:
            temporary.cleanup()
            raise
        identity = secrets.token_hex(16)
        with self.lock:
            self.pages[identity] = Specimen(
                temporary, parent, artifact.registry["$layer"], passive, asset_root
            )
        return identity

    def get(self, parent: Path, identity: str) -> Specimen | None:
        with self.lock:
            specimen = self.pages.get(identity)
            return (
                specimen if specimen is not None and specimen.parent == parent else None
            )

    def release(self, parent: Path, identity: str) -> None:
        with self.lock:
            specimen = self.pages.get(identity)
            if specimen is None or specimen.parent != parent:
                return
            del self.pages[identity]
        specimen.close()
        with self.lock:
            children = [
                key
                for key, child in self.pages.items()
                if child.parent == specimen.directory
            ]
        for child in children:
            self.release(specimen.directory, child)

    def close(self) -> None:
        with self.lock:
            pages, self.pages = self.pages, {}
        for specimen in pages.values():
            specimen.close()
