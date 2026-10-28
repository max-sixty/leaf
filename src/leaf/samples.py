"""Disposable pages built from authored or generated source and its revision's layer.

A sample owns an ordinary source, revision, data store, and event log. Its parent
supplies immutable resources and optional selected thread history, never a live
state projection. Each unguessable child path is a capability for that child's
ordinary document, captured dependencies, and APIs. It grants no parent routes.
Browser gestures enter the ordinary page event door. Each page owns its child
capabilities; releasing one drops its whole subtree. Admitted requests retain their
samples until delivery ends, and the last reference cleans each temporary directory.
Nothing reads one after a crash, so revisions are staged without fsync
(`revision_artifact.Disposable`).
"""

import json
import secrets
import shutil
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

from .data import write_data
from .event_log import start_log
from .page_memory import PageMemory, memory_of
from .registry.kernel import kernel_protocol
from .registry.storage import LAYER
from .revision_artifact import Disposable, RevisionArtifact
from .revisioning import activate_source
from .runtime_selection import executing
from .sample_content import initial_sample_events
from .schema import LAYER_FILE
from .structure import SourceDocument
from .thread_context import thread_structure


@dataclass
class Sample:
    temporary: TemporaryDirectory
    layer: dict
    asset_root: str | None
    # Held for the sample's life, so the sample keeps its readings however many
    # sibling samples push it out of the process's recent pages (`page_memory`).
    memory: PageMemory
    # The parent's, held for the same life: a page serving samples is being read, and
    # its own samples are what would otherwise push it out, so every state answer it
    # gave would check and capture its whole source again.
    parent_memory: PageMemory
    children: "Samples" = field(default_factory=lambda: Samples())

    def __post_init__(self) -> None:
        weakref.finalize(self, self.temporary.cleanup)

    @property
    def directory(self) -> Path:
        return Path(self.temporary.name)


class Samples:
    """The child capabilities of one page; a sample owns its own children."""

    def __init__(self) -> None:
        self.pages: dict[str, Sample] = {}
        self.lock = Lock()

    def create(
        self,
        parent: Path,
        artifact: RevisionArtifact,
        document: SourceDocument,
        events: list,
        data: dict,
        template_id: str | None,
        message: str | None,
        asset_root: str | None,
        *,
        source: str | None = None,
    ) -> str:
        """Allocate from a declared template or a complete generated document.

        Both use the layer the parent revision selects and ordinary source validation.
        Generated source
        starts with an empty log; it cannot import the parent's conversation history.
        """
        if source is None:
            content, seeded = self._template_source(
                parent, artifact, document, events, data, template_id, message
            )
        else:
            content, seeded = source.encode("utf-8"), []
        temporary = TemporaryDirectory(prefix="leaf-sample-")
        child = Path(temporary.name)
        memory = memory_of(child)
        memory.memo(Disposable).held = True
        try:
            for logical, resource in artifact.resources.items():
                target = child / logical.removeprefix("/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(resource.data)
            # The child selects the layer its parent's revision was captured under,
            # which this Leaf composes for it as for any page.
            LAYER.write(
                child / LAYER_FILE,
                {
                    **json.loads(artifact.manifest)["layer"],
                    "protocol": kernel_protocol(),
                },
            )
            # A frozen parent lends the package bytes it captured, not whatever
            # copies page init may since have replaced in its directory.
            for directory, files in executing(artifact).package_copies.items():
                for relative, content in files.items():
                    target = child / directory / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
            # Message attachments are content-addressed page data, not necessarily
            # dependencies of the authored revision. Preserve those bytes too.
            if (parent / "media").is_dir():
                shutil.copytree(parent / "media", child / "media", dirs_exist_ok=True)
            # The child reads the data the parent reading it was built from held,
            # which for a frozen preview is not what the parent's files hold now.
            write_data(
                child,
                {
                    name: {
                        key: reading[key]
                        for key in ("contract", "run", "updated", "value")
                    }
                    for name, reading in data["sources"].items()
                    if "value" in reading
                },
            )
            (child / "index.html").write_bytes(content)
            start_log(child, seeded)
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
                artifact.registry["$layer"],
                asset_root,
                memory,
                memory_of(parent),
            )
        return identity

    @staticmethod
    def _template_source(
        parent, artifact, document, events, data, template_id, message
    ):
        holder = (
            document
            if message is None
            else thread_structure(events).fragments.get(message)
        )
        if holder is None:
            raise ValueError(f"no message {message!r} carries markup")
        template = next(
            (
                sample
                for sample in holder.samples
                if sample["attrs"].get("id") == template_id
            ),
            None,
        )
        if template is None:
            raise ValueError(
                f"unknown sample template {template_id!r}"
                + (f" in message {message!r}" if message is not None else "")
            )
        seeded = initial_sample_events(
            parent,
            document,
            events,
            holder,
            template,
            artifact.registry,
            {name: reading["contract"] for name, reading in data["sources"].items()},
        )
        return template["document"].data, seeded

    def get(self, identity: str) -> Sample | None:
        with self.lock:
            return self.pages.get(identity)

    def release(self, identity: str) -> None:
        with self.lock:
            self.pages.pop(identity, None)
