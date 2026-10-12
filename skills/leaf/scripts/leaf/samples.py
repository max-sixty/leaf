"""Disposable page instances built from an authored template and its captured layer.

A sample owns an ordinary source, revision, data store, and event log. Its parent
supplies immutable resources and optional selected thread history, never a live
state projection. Each unguessable child path is a capability for that child's
ordinary document, captured dependencies, and APIs. It grants no parent routes.
Browser gestures enter the ordinary page event door. The HTTP server owns these
directories until explicit release or server shutdown, and nothing reads one after a
crash, so a child's revisions are staged without fsync (`revision_artifact.Disposable`).
"""

import json
import secrets
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

from .data import source_file
from .page_memory import PageMemory, memory_of
from .revision_artifact import Disposable, write_artifact
from .revisioning import activate_source
from .sample_content import initial_sample_history, page_sample_history
from .schema import DATA_DIR, DATA_FILE
from .served_state.service import SampleInputs
from .state import now_iso, write_json
from .thread_context import thread_structure, widget_messages


@dataclass
class Sample:
    temporary: TemporaryDirectory
    parent: Path
    layer: dict
    asset_root: str | None
    # Held for the sample's life, so the sample keeps its readings however many
    # sibling samples push it out of the process's recent pages (`page_memory`).
    memory: PageMemory
    lock: Lock = field(default_factory=Lock)
    closed: bool = False

    @property
    def directory(self) -> Path:
        return Path(self.temporary.name)

    def close(self) -> None:
        with self.lock:
            self.closed = True
            self.temporary.cleanup()


class Samples:
    """The child pages of one HTTP server, scoped to their creating parent."""

    def __init__(self) -> None:
        self.pages: dict[str, Sample] = {}
        self.lock = Lock()

    def create(
        self,
        parent: Path,
        inputs: SampleInputs,
        template_id: str,
        asset_root: str | None,
    ) -> str:
        artifact = inputs.artifact
        document = inputs.readings[inputs.revision].document
        events = inputs.events
        data = inputs.data
        template = next(
            (
                sample
                for sample in document.samples
                if sample["attrs"].get("id") == template_id
            ),
            None,
        )
        if template is None:
            raise ValueError(f"unknown sample template {template_id!r}")
        parent_history = page_sample_history(
            document, events, inputs.available_revisions
        )
        seeded = initial_sample_history(
            parent,
            document,
            parent_history,
            template,
            artifact.registry,
            {name: reading["contract"] for name, reading in data["sources"].items()},
        ).events
        source = template["document"].data
        temporary = TemporaryDirectory(prefix="leaf-sample-")
        child = Path(temporary.name)
        memory = memory_of(child)
        memory.memo(Disposable).held = True
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
                    write_json(
                        source_file(child, name),
                        {key: reading[key] for key in ("run", "updated", "value")},
                    )
            frozen = widget_messages(thread_structure(seeded))
            revisions = (
                []
                if "data-sample-events" in template["attrs"]
                else sorted(
                    {
                        event["revision"]
                        for event in seeded
                        if event.get("markup")
                        and event["revision"] in inputs.available_revisions
                    }
                )
            )
            revision_map = {
                revision: index for index, revision in enumerate(revisions, 1)
            }
            for revision, copied in revision_map.items():
                write_artifact(
                    child,
                    copied,
                    inputs.artifacts[revision],
                    inputs.readings[revision],
                )
            current_revision = len(revisions) + 1
            for event in seeded:
                if "revision" not in event:
                    continue
                event["revision"] = (
                    revision_map[event["revision"]]
                    if revisions
                    and (event.get("markup") or event.get("widget") in frozen)
                    else current_revision
                )
            (child / "index.html").write_bytes(source)
            (child / "events.jsonl").write_text(
                "".join(json.dumps(event) + "\n" for event in seeded),
                encoding="utf-8",
            )
            write_json(
                child / "status.json",
                {"state": "waiting", "detail": "", "ts": now_iso()},
            )
            activation = activate_source(child)
            if activation.error:
                raise ValueError(f"invalid sample: {activation.error}")
        except BaseException:
            temporary.cleanup()
            raise
        identity = secrets.token_hex(16)
        with self.lock:
            self.pages[identity] = Sample(
                temporary,
                parent,
                artifact.registry["$layer"],
                asset_root,
                memory,
            )
        return identity

    def get(self, parent: Path, identity: str) -> Sample | None:
        with self.lock:
            sample = self.pages.get(identity)
            return sample if sample is not None and sample.parent == parent else None

    def release(self, parent: Path, identity: str) -> None:
        with self.lock:
            sample = self.pages.get(identity)
            if sample is None or sample.parent != parent:
                return
            del self.pages[identity]
        sample.close()
        with self.lock:
            children = [
                key
                for key, child in self.pages.items()
                if child.parent == sample.directory
            ]
        for child in children:
            self.release(sample.directory, child)

    def close(self) -> None:
        with self.lock:
            pages, self.pages = self.pages, {}
        for sample in pages.values():
            sample.close()
