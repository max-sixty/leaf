"""Complete immutable inputs of one authored revision, and its one held reading.

A capture follows the resources each captured file names, as its readers find them
(`resource_urls.authored_imports`, `styles.css_dependencies`), and admits only what
the page owns and the layer's public entry points (`resource_urls.resolve_dependency`).
Neither the layer nor the runtime is captured: the Leaf delivering a revision supplies
both (`runtime_selection`), the layer composed from the selection the manifest names, so
the public entry points are addresses a capture names but never holds. Capturing `page/`
whole lets page code fetch any of its files (`page_files`).

A bundle contains exact source bytes, resources, MIME
types, the effective registry, and implementation provenance. Its canonical
manifest determines its digest, and carries a second ``executable`` digest over
the captured inputs an already-open document cannot re-evaluate in place; the
runtime it runs with is named beside it by the delivering Leaf. Scripts include
their patch region: head scripts stay installed while authored body content is patched.
Moving a script between head and body reloads, so a retained script cannot duplicate
an arriving body script. Moving among containers within body without changing
script order, or editing prose, does not reload. The HTML revision file is the commit marker: the complete bundle is made durable before
that file appears. Users never discover a staged or incomplete revision,
including after a process crash. A publication that also changes the log stages
its bundle, records the exact bundle name in its first admitted prerequisite,
and publishes this marker only after all dependent transitions are durable.
`revision_publication.finish_publications` completes that sequence before transaction
consumers read the page.

Every reader of a stored revision takes `read_revision`: one held reading per
revision, owning its manifest, captured vocabulary, parsed document, and passage
readings. The vocabulary is the declarations the revision captured over the layer its
manifest selects, which the reading Leaf composes (`revision_vocabulary`).
`read_artifact` holds immutable resource files without loading their bodies; delivery
parses the document it rewrites for serving, which is other text. Each is kept in the
memory of the page it was read from, for as long as the process keeps that page
(`page_memory`).
"""

import hashlib
import json
import mimetypes
import os
import sys
import tempfile
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cached_property, partial
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from urllib.parse import urlsplit

from leaf.base.files import (
    file_stamp,
    latest_revision,
    list_revisions,
    revision_names,
    revision_path,
)
from leaf.base.findings import Finding, note
from leaf.base.page_memory import Slot, Stamped, memo, once
from leaf.base.schema import (
    CONTENT_TYPES,
    LAYER_FILE,
    MEDIA_DIR,
    PACKAGES_DIR,
    SERVED_PATH,
)
from leaf.base.state import fsync_parents
from leaf.source.capture_refusals import ArtifactError, artifact_error, capture_finding
from leaf.source.layer import (
    LayerVocabulary,
    layer_vocabulary,
    layer_widgets,
    selected_layer,
    selected_vocabulary,
)
from leaf.source.page_inputs import page_stamps
from leaf.source.passages import enclosing_ids
from leaf.source.reading import SourceReading
from leaf.source.registry.contract import MODULES
from leaf.source.registry.page import compose_page_registry
from leaf.source.resource_urls import (
    PUBLIC_MODULES,
    authored_imports,
    dependency_reference,
    javascript_imports,
    resolve_dependency,
)
from leaf.source.structure import (
    SourceDocument,
    annotation_mode,
    delivered_sheets,
    links_with_rel,
    script_kind,
    splice,
)
from leaf.source.styles import css_dependencies, css_drops

# The page's own declarations, which a revision captures beside its modules; the
# layer they compose over is the reading Leaf's.
PAGE_DECLARATIONS = "/page/registry.json"


_RESOURCE_TYPES = {
    **CONTENT_TYPES,
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
}
# The standard library's own table, without the host's mime.types files, so a capture's
# manifest names the same types on every machine.
_STANDARD_TYPES = mimetypes.MimeTypes(filenames=())


def resource_type(path: str) -> str:
    """The MIME type a captured file is served with, by its suffix.

    Leaf's own table decides what the runtime and capture read as a module, stylesheet
    or media, and the standard library's names the rest, such as CSV, text and wasm,
    so page code fetches any page file with its usual type. A suffix neither knows
    is served as bytes."""
    suffix = PurePosixPath(path).suffix.lower()
    return (
        _RESOURCE_TYPES.get(suffix)
        or _STANDARD_TYPES.types_map[True].get(suffix)
        or "application/octet-stream"
    )


def _collect(refused: list[Finding], read, *args, **kwargs):
    """`read(*args, **kwargs)`, or None with what it refused added to `refused`, so a
    capture goes on to the next reference and refuses once with every finding. What
    depended on the refused read, such as the imports of a file that can't be read,
    is skipped rather than reported again."""
    try:
        return read(*args, **kwargs)
    except ArtifactError as error:
        refused.extend(error.findings)
        return None


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json(value) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class Resource:
    """Exact bytes or an immutable backing file, read only when a consumer needs them.

    Captured files belong to the revision bundle; callers never replace them with a
    mutable page path. A full read is explicit in `data`; HTTP passes backing files
    directly to Starlette for streaming and byte ranges.
    """

    content: bytes | Path
    mime: str

    @property
    def data(self) -> bytes:
        return (
            self.content
            if isinstance(self.content, bytes)
            else self.content.read_bytes()
        )

    @property
    def digest(self) -> str:
        return _digest(self.data)


# Compared and hashed by identity, so a kept reading can be keyed by the artifact
# it was made from (`runtime_selection.executing`).
@dataclass(frozen=True, eq=False)
class RevisionArtifact:
    html: bytes
    resources: Mapping[str, Resource]
    manifest: bytes
    # The page whose package copies the manifest's layer names (`vendoring`).
    page_dir: Path

    @cached_property
    def digest(self) -> str:
        return _digest(self.manifest)

    @cached_property
    def registry(self) -> dict:
        """The vocabulary this Leaf reads the revision in: its own declarations over
        the layer its manifest selects (`revision_vocabulary`)."""
        declarations = self.resources.get(PAGE_DECLARATIONS)
        return revision_vocabulary(
            json.loads(self.manifest),
            declarations.data if declarations is not None else None,
            self.page_dir,
        )

    @cached_property
    def entries(self) -> list[str]:
        """The captured resources the authored document names directly."""
        return json.loads(self.manifest)["entries"]

    @cached_property
    def implementations(self) -> dict:
        return json.loads(self.manifest)["implementations"]

    @cached_property
    def declaration_sources(self) -> dict[str, str]:
        """The captured owners of widget and named data contract declarations."""
        return json.loads(self.manifest)["declarations"]

    @cached_property
    def widget_aliases(self) -> dict[str, str]:
        """The loader's widget module paths, mapped to their captured implementations.

        A page-owned implementation lives under `/page/`, but every widget is
        loaded through `/widgets/<tag>.js`. HTTP, publication and offline export
        read these aliases from the same captured provenance.
        """
        return {
            f"/widgets/{tag}.js": implementation["path"]
            for tag, implementation in self.implementations.items()
        }

    @cached_property
    def executable(self) -> str:
        """The captured module graph's executable identity."""
        return json.loads(self.manifest)["executable"]


def document_drops(document: SourceDocument) -> list[Finding]:
    """`css_drops` for every sheet delivery rewrites in `document`
    (`structure.delivered_sheets`)."""
    return [
        finding
        for css, sheet, declarations in delivered_sheets(document)
        for finding in css_drops(css, sheet, declarations)
    ]


def unanswered_media(refs, page_dir: Path) -> list[Finding]:
    """Every `/media/…` reference the page will not answer: one whose name the server
    never serves (`schema.MEDIA_DIGEST`), whatever the directory holds under it, and
    one the directory has not got."""
    errors = []
    for ref in sorted(refs):
        path = urlsplit(ref).path
        if not SERVED_PATH.fullmatch(path):
            errors.append(Finding("unserved-media", values={"ref": ref}))
        elif not (page_dir / path.lstrip("/")).is_file():
            errors.append(Finding("missing-media", values={"ref": ref}))
    return errors


def uncaptured_errors(document: SourceDocument, page_dir: Path) -> list[Finding]:
    """What a capture would refuse in markup no capture reads, such as a message's,
    which the log carries: what delivery's reader can't read in
    the stylesheets it writes (`css_dependencies`), and each `/media/` file it names
    that the page won't answer (`unanswered_media`), in an attribute or a
    stylesheet. Its stylesheets are every one delivery rewrites
    (`structure.delivered_sheets`), its samples' included; a sample child's
    attributes its own reading names
    (`authored_checks.documents.uncaptured_sample_errors`). A page's own markup the
    capture reads (`_capture_artifact`)."""
    refused = []
    media = set(document.authoring.media_refs)
    for css, sheet, declarations in delivered_sheets(document):
        for specifier in css_dependencies(css, sheet, declarations, refused=refused):
            path = _collect(refused, resolve_dependency, specifier, "/index.html")
            if path is not None and path.startswith("/media/"):
                media.add(path)
    return [*refused, *unanswered_media(media, page_dir)]


def _path_stamp(path: Path) -> tuple:
    """Identify a directory entry and the file it currently resolves to: where a
    symlink points decides whether a dependency escapes its directory, and the
    stamp of what it resolves to decides the bytes captured."""
    try:
        link = path.readlink()
    except OSError:  # not a symlink, or no longer there
        link = None
    return (link, file_stamp(path))


# The page's trees a capture may read a dependency from (`capture_local_resource`).
CAPTURED_TREES = ("page", MEDIA_DIR)


def version_written(page_dir: Path) -> int:
    """When a file a version is built from was last written, in nanoseconds since the
    epoch: the document, the layer it selects with the page's package copies, and the
    trees a capture reads. A data update, for one, moves the page's source
    (`page_inputs.source_readings`) but makes no new version. It reads the stamps the
    page's readings take (`page_inputs.page_stamps`)."""
    inputs = {"index.html", LAYER_FILE, PACKAGES_DIR, *CAPTURED_TREES}
    return max(
        (
            stamp[1]
            for name, stamp in page_stamps(page_dir)
            if isinstance(stamp, tuple) and name.split("/", 1)[0] in inputs
        ),
        default=0,
    )


def _capture_input_stamps(page_dir: Path) -> tuple[tuple[str, tuple], ...]:
    """Name every mutable filesystem input from which a capture may read."""
    paths = []
    for name in CAPTURED_TREES:
        root = page_dir / name
        paths.append(root)
        if root.is_dir() and not root.is_symlink():
            paths.extend(root.rglob("*"))
    return tuple(
        (path.relative_to(page_dir).as_posix(), _path_stamp(path))
        for path in sorted(set(paths))
    )


def capture_artifact(
    page_dir: Path,
    document: SourceDocument,
    registry: dict,
    *,
    declaration_sources: Mapping[str, str] | None = None,
    widget_sources: Mapping[str, str] | None = None,
    read_resource: Callable[[str], Resource] | None = None,
) -> RevisionArtifact:
    """Capture the candidate's complete inputs without executing authored code.

    The page keeps its last capture while every input is the same: the document's
    bytes, the vocabulary and declarations, and the stamp of every mutable file a
    capture may read. A capture that must be built is built from the caller's own
    document, which the check that asks has already parsed.

    A fixture builder may supply a resource reader that materializes missing media
    before reading it through `capture_local_resource`. That reader uses this same
    dependency discovery, including samples and transitive CSS and script inputs.
    Its inputs may live outside the page, so captures with a supplied reader are
    not cached by page-local stamps.
    """
    page_dir = page_dir.absolute()
    build = partial(
        _capture_artifact,
        page_dir,
        document,
        registry,
        declaration_sources=declaration_sources,
        widget_sources=widget_sources,
        read_resource=read_resource or partial(capture_local_resource, page_dir),
    )
    if read_resource is not None:
        return build()
    key = (
        document.data,
        _json(registry),
        _json(dict(declaration_sources or {})),
        _json(dict(widget_sources or {})) if widget_sources is not None else None,
        _capture_input_stamps(page_dir),
    )
    return memo(page_dir, _Capture).get(key, build)


class _Capture(Slot):
    """A page's last capture, by every input it was built from."""


def capture_local_resource(page_dir: Path, path: str) -> Resource:
    """Freeze one resolved page-local resource with the shared containment gate.

    Authored dependency capture and declared external-data media capture both
    read exact bytes here. Callers own URL admission before supplying a path. A file
    under `page/` or `media/` whose real path leaves its directory is refused, so a
    symlink never puts a file from elsewhere on the machine into a revision, and from
    there into a published site or an export. A `/media/` path the page won't answer
    is refused in the words the message door uses (`unanswered_media`), wherever the
    page names it: an attribute, a stylesheet or its data.
    """
    source = page_dir / path.removeprefix("/")
    root = page_dir / ("page" if path.startswith("/page/") else "media")
    if path.startswith(("/page/", "/media/")) and (
        not root.resolve().is_relative_to(page_dir.resolve())
        or not source.resolve().is_relative_to(root.resolve())
    ):
        raise artifact_error("dependency-symlink", path)
    if path.startswith("/media/") and (
        unanswered := unanswered_media([path], page_dir)
    ):
        raise ArtifactError(unanswered)
    try:
        data = source.read_bytes()
    except OSError as error:
        raise artifact_error(
            "dependency-unreadable", path, error=error.strerror
        ) from error
    return Resource(data, resource_type(path))


def page_files(page_dir: Path) -> list[str]:
    """Every file under the page's `page/`, by its logical path, as a revision holds it.

    A revision holds the whole directory, as an ordinary site serves its files, so page
    code can fetch any of them by a URL it computes at run time; content addressing
    lets an unchanged file cost a revision nothing. Hidden entries, such as an
    editor's swap file or Finder's `.DS_Store`, are left out, as static hosts leave
    them, so they never make a revision; a literal reference still captures one. A
    symlinked directory is not descended: a file reached through it is captured by
    its own path, or refused by `capture_local_resource` if it lies outside."""
    root = page_dir / "page"
    files = []
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = [
            name for name in subdirectories if not name.startswith(".")
        ]
        relative = Path(directory).relative_to(root)
        files.extend(
            "/" + (Path("page") / relative / name).as_posix()
            for name in names
            if not name.startswith(".")
        )
    return sorted(files)


def resource_dependencies(
    path: str, data: bytes, mime: str, refused: list[Finding] | None = None
) -> tuple[str, ...]:
    """The local dependencies of an authored module or stylesheet, collecting each
    reference it refuses as `authored_imports` does, with what delivery's reader
    can't read in a stylesheet (`css_dependencies`). A file that can't be read as
    text has no references to follow."""
    problems = []
    edges = []
    if mime == "application/javascript" and path.startswith("/page/"):
        edges.extend(target for _, _, target in authored_imports(data, path, problems))
    elif mime == "text/css" and path.startswith("/page/"):
        try:
            css = data.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(capture_finding("css-not-utf8", path))
        else:
            for specifier in css_dependencies(css, path, refused=problems):
                edges.append(_collect(problems, resolve_dependency, specifier, path))
    if refused is not None:
        refused.extend(problems)
    elif problems:
        raise ArtifactError(problems)
    return tuple(dict.fromkeys(edge for edge in edges if edge is not None))


class _ResourceCapture:
    """One capture's resource graph, including cycles and arbitrarily deep imports.

    Record a resource before following its edges, so each path is read once. The
    explicit worklist keeps graph depth independent of Python's call stack. A public
    entry point an authored module imports is the runtime's or the layer's, which the
    delivering Leaf supplies, so capture skips it.

    A path is visited once whether or not it could be captured, and what a capture
    refuses goes to `refused`: a file that can't be read is not followed, and a
    refused reference is not followed.
    """

    def __init__(self, read_resource: Callable[[str], Resource]) -> None:
        self.read_resource = read_resource
        self.resources: dict[str, Resource] = {}
        self.visited: set[str] = set()
        self.refused: list[Finding] = []

    def add(self, path: str) -> None:
        pending = [path]
        while pending:
            path = pending.pop()
            if path in self.visited or path in PUBLIC_MODULES:
                continue
            self.visited.add(path)
            resource = _collect(self.refused, self.read_resource, path)
            if resource is None:
                continue
            data = resource.data
            self.resources[path] = Resource(data, resource.mime)
            edges = resource_dependencies(path, data, resource.mime, self.refused)
            pending.extend(reversed(edges))


def _layer_files(registry: dict, page_dir: Path) -> Mapping[str, bytes]:
    """The files of the layer `registry`'s `$layer` selects, which the delivering Leaf
    serves beside the revision (`runtime_selection.executing`): a document may name
    one, such as the layer's icon, without the revision capturing it."""
    layer = registry.get("$layer")
    return selected_layer(layer, page_dir).files if layer else {}


def _capture_artifact(
    page_dir: Path,
    document: SourceDocument,
    registry: dict,
    *,
    declaration_sources: Mapping[str, str] | None = None,
    widget_sources: Mapping[str, str] | None = None,
    read_resource: Callable[[str], Resource],
) -> RevisionArtifact:
    """Build a capture after its public wrapper has identified every input."""
    capture = _ResourceCapture(read_resource)
    resources = capture.resources
    refused = capture.refused
    admit = partial(_collect, refused)

    # The layer is the reading Leaf's (`revision_vocabulary`), so a
    # revision captures only what its page owns: `page/`, its declarations among it,
    # and what its document names. Its manifest names the layer's selection.
    if widget_sources is None:
        widget_sources = registry.get(MODULES, {})
    for source in widget_sources.values():
        if source.startswith("page/"):
            capture.add("/" + source)

    entries = []
    documents = [document]
    for authored in documents:
        documents.extend(sample["document"] for sample in authored.samples)
        for script in authored.authoring.inline_scripts:
            if script_kind(script["attrs"]) not in {"module", "classic"}:
                continue
            entries.extend(
                target
                for _, _, target in authored_imports(
                    script["body"].encode("utf-8"), "/index.html", refused
                )
            )
        for script in authored.authoring.external_scripts:
            if script_kind(script["attrs"]) not in {"module", "classic"}:
                continue
            path = admit(
                resolve_dependency, script["attrs"]["src"], "/index.html", module=True
            )
            # A public runtime module, which delivery serves, is no file of the page's.
            if path is None or not path.startswith("/page/"):
                continue
            entries.append(path)
        for link in links_with_rel(authored.authoring.links, "stylesheet"):
            path = admit(
                resolve_dependency, link["attrs"].get("href", ""), "/index.html"
            )
            if path is None:
                continue
            if Path(path).suffix != ".css":
                refused.append(capture_finding("stylesheet-type", path))
                continue
            entries.append(path)
        for specifier in authored.authoring.resource_refs:
            reference = admit(dependency_reference, specifier, "/index.html")
            if reference is None or reference[0] in resources:
                continue
            if not reference[0].startswith(("/page/", "/media/")) and (
                reference[0] in _layer_files(registry, page_dir)
            ):
                continue
            entries.append(admit(resolve_dependency, specifier, "/index.html"))
    # Every sheet delivery rewrites, which a template's or a shadow root's contents
    # hold as well as the document, so a sample's are among its page's.
    for css, sheet, declarations in delivered_sheets(document):
        for specifier in css_dependencies(css, sheet, declarations, refused=refused):
            entries.append(admit(resolve_dependency, specifier, "/index.html"))
    entries = [entry for entry in entries if entry is not None]
    for entry in entries:
        capture.add(entry)
    # The rest of `page/` after what the document names, so findings name the files
    # the author wrote a reference to before those nothing names.
    for path in page_files(page_dir):
        capture.add(path)
    if refused:
        # A sample repeats its page's references, and a document may repeat one:
        # each problem is reported once.
        raise ArtifactError(list(dict.fromkeys(refused)))

    implementations = {
        tag: {
            "path": "/" + source.lstrip("/"),
            "owner": "page" if source.startswith("page/") else "layer",
            **(
                {"digest": resources["/" + source].digest}
                if source.startswith("page/")
                else {}
            ),
        }
        for tag, source in widget_sources.items()
    }
    layer = registry.get("$layer", {})
    # Which of this capture's inputs the current document cannot take on in place. A
    # module graph is evaluated once per document and a custom element is defined
    # once, so new bytes behind either need a new document. Stylesheets, media,
    # prose, and markup are absent because an open document can be given all of
    # them, and a revision that only edits those should keep the user's document.
    #
    # Only what the page owns goes in, so every Leaf that captures the same source
    # captures the same revision. A page is often read by two Leaf versions at
    # once, as a server keeps the Leaf it started with while the agent's commands
    # run a newer one, and each composes its own vocabulary: digesting that
    # vocabulary would have each publish the other's capture again and reload the
    # tab every time. What an open document runs under comes from the serving Leaf
    # instead: a change to its runtime or a bundled package reaches the tab as a
    # server that refuses it (`runtime_selection`), and a new selection or a
    # changed package copy as a new generation (`vendoring`), which a tab speaks
    # to the server (`runtime/transport/layer-client.js`).
    declarations = resources.get(PAGE_DECLARATIONS)
    executable = _digest(
        _canonical_json(
            {
                "generation": layer.get("generation"),
                "annotations": annotation_mode(document),
                "page_declarations": declarations.digest if declarations else None,
                "modules": {
                    path: resource.digest
                    for path, resource in resources.items()
                    if resource.mime == "application/javascript"
                },
                # Every script element, whole and in document order: its attributes
                # and place decide whether and when it runs, a data block's body is
                # read at boot, and a src no capture holds, such as a CDN library's,
                # is named only here.
                "scripts": [
                    {
                        "attrs": script["attrs"],
                        "patch_region": script["patch_region"],
                        "body": _digest(script.get("body", "").encode("utf-8")),
                    }
                    for script in sorted(
                        [
                            *document.authoring.inline_scripts,
                            *document.authoring.external_scripts,
                        ],
                        key=lambda script: script["position"],
                    )
                ],
            }
        )
    )
    manifest = _canonical_json(
        {
            "html": document.digest,
            "title": document.authoring.title.strip(),
            "entries": sorted(set(entries)),
            "executable": executable,
            "layer": layer,
            "declarations": dict(declaration_sources or {}),
            "implementations": implementations,
            "resources": {
                path: {
                    "digest": resource.digest,
                    "mime": resource.mime,
                }
                for path, resource in sorted(resources.items())
            },
        }
    )
    return RevisionArtifact(
        document.data, MappingProxyType(resources), manifest, page_dir
    )


def artifact_name(revision: int, artifact: RevisionArtifact) -> str:
    return f"r{revision}-{artifact.digest.removeprefix('sha256:')[:16]}"


class Disposable:
    """Whether Leaf built this page for itself and deletes it, as a sample's child
    (`samples`), so nothing reads its revisions after a crash and staging and
    publishing them skip every fsync.

    The builder sets it in the memory it holds for the page's life
    (`page_memory.memory_of`). A page whose memory never held the mark, or dropped
    it, is written durably, so losing the mark costs time and never a revision."""

    held = False


def stage_artifact(page_dir: Path, revision: int, artifact: RevisionArtifact) -> str:
    """Make exact immutable inputs durable, unless the page is `Disposable`, without
    making a revision discoverable."""
    durable = not memo(page_dir, Disposable).held
    revisions = page_dir / "revisions"
    revisions.mkdir(exist_ok=True)
    if revision in list_revisions(page_dir):
        raise artifact_error("revision-exists", revision=revision)
    name = artifact_name(revision, artifact)
    destination = revisions / name
    if not destination.exists():
        with tempfile.TemporaryDirectory(
            prefix=".capture-", dir=revisions
        ) as temporary:
            staged = Path(temporary) / name
            staged.mkdir()
            captured = _captured_files(page_dir)
            written = []
            for relative, data in (
                ("index.html", artifact.html),
                ("manifest.json", artifact.manifest),
            ):
                written.append(_write(staged / relative, data, durable))
            for path, resource in artifact.resources.items():
                target = staged / ("resources" + path)
                target.parent.mkdir(parents=True, exist_ok=True)
                earlier = captured.get(resource.digest)
                if earlier is None:
                    _write(target, resource.data, durable)
                else:
                    os.link(earlier, target)
                written.append(target)
            if durable:
                fsync_parents(written + list(staged.rglob("*")))
            os.rename(staged, destination)
            if durable:
                fsync_parents([destination])
    elif (destination / "manifest.json").read_bytes() != artifact.manifest:
        raise artifact_error("digest-collision", destination)
    return name


def _write(target: Path, data: bytes, durable: bool) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(data)
        if durable:
            stream.flush()
            os.fsync(stream.fileno())
    return target


def _captured_files(page_dir: Path) -> dict[str, Path]:
    """The resource files the newest revision captured, by digest.

    Successive revisions of a page capture mostly the same layer, a few hundred files
    and several megabytes, so a new bundle links each resource the newest one already
    holds rather than writing and syncing its bytes again. Sharing an inode is safe
    because nothing writes a captured file after its bundle is made; whatever else
    links to one, such as a site build's deduplication, only reads it."""
    revision = latest_revision(page_dir)
    if revision is None:
        return {}
    bundle = revision_path(page_dir, revision).with_suffix("")
    manifest = json.loads((bundle / "manifest.json").read_bytes())
    return {
        record["digest"]: bundle / ("resources" + logical)
        for logical, record in manifest["resources"].items()
    }


def staged_reading(page_dir: Path, name: str) -> SourceReading:
    """Read the exact durable bundle named by an admitted publication prerequisite."""
    bundle = page_dir / "revisions" / name
    return SourceReading(
        SourceDocument((bundle / "index.html").read_bytes().decode("utf-8")),
        _bundle_vocabulary(bundle),
    )


def publish_artifact(page_dir: Path, name: str, reading: SourceReading) -> Path:
    """Commit a staged bundle only after its dependent log transitions are durable."""
    destination = page_dir / "revisions" / name
    marker = destination.with_name(f"{name}.html")
    os.link(destination / "index.html", marker)
    if not memo(page_dir, Disposable).held:
        fsync_parents([marker])
    marker = marker.absolute()
    stamp = file_stamp(marker)
    memo(page_dir, _Readings).hold(
        marker, stamp, RevisionReading(marker, stamp, reading)
    )
    return marker


def write_artifact(
    page_dir: Path, revision: int, artifact: RevisionArtifact, reading: SourceReading
) -> Path:
    """Publish a complete bundle whose revision has no prerequisite log transitions."""
    return publish_artifact(
        page_dir, stage_artifact(page_dir, revision, artifact), reading
    )


def read_artifact(page_dir: Path, revision: int) -> RevisionArtifact:
    """Read exact captured inputs, never substituting a mutable page file.

    The page keeps the last few bundle descriptors (`_Artifacts`) by path alone. A
    revision's name carries its manifest's digest and its marker appears only after
    its bundle is complete (`write_artifact`), so one path names one bundle for good,
    and a server answering a page's few hundred resource requests reads none of its
    files again."""
    path = revision_path(page_dir, revision).absolute()
    held = memo(page_dir, _Artifacts)
    if (artifact := held.get(path)) is None:
        artifact = _materialize(path, path.with_suffix(""))
        held.hold(path, artifact)
    return artifact


class _Artifacts:
    """A page's last immutable bundle descriptors, least recently read first.

    A bundle is a couple of hundred files and several megabytes. A server answers
    each resource request from the revision a tab shows, which is the active one and
    a few others at most, while a snapshot or a live shell walks every revision
    once."""

    LIMIT = 4

    def __init__(self) -> None:
        self.held: dict[Path, RevisionArtifact] = {}
        self.lock = threading.Lock()

    def get(self, path: Path) -> RevisionArtifact | None:
        with self.lock:
            artifact = self.held.pop(path, None)
            if artifact is not None:
                self.held[path] = artifact
            return artifact

    def hold(self, path: Path, artifact: RevisionArtifact) -> None:
        with self.lock:
            self.held.pop(path, None)
            self.held[path] = artifact
            while len(self.held) > self.LIMIT:
                self.held.pop(next(iter(self.held)))


class RevisionReading(SourceReading):
    """One stored revision, read once for every caller its page's memory serves.

    A revision's files never change after its HTML marker appears (`write_artifact`),
    so everything read from it — the manifest, the captured vocabulary, the parsed
    document, and the passage readings `SourceReading` derives under that vocabulary
    — is one fact per revision, held here and keyed by the marker's stamp. Each piece
    is read on first use, so a caller asking one revision for its registry opens one
    file, and a caller asking every revision in a long history for its document and
    registry opens two apiece. The source bytes are not kept beside the parse: the
    document holds its own (`SourceDocument.data`).

    The complete bundle is not held here. It is a couple of hundred files, several
    megabytes, and a snapshot or a live shell asks for every revision's, so
    `read_artifact` holds its manifest and immutable resource paths under its own
    small bound. What the bundle's
    identity answers, its `digest`, is the manifest's and needs none of it.

    `document` and `registry` are what `SourceReading` reads: here they are read from
    the revision on first use rather than handed in, so this reading does not run
    that initializer.
    """

    def __init__(self, marker: Path, stamp, adopted: SourceReading | None = None):
        self.marker = marker
        self.stamp = stamp
        self.bundle = marker.with_suffix("")
        if adopted is not None:
            # A revision written from a checked candidate is that candidate: its
            # document is the captured bytes, and its vocabulary the one captured.
            # So it takes the candidate's reading, with whatever words and passages
            # the check already read, rather than parsing and walking them again.
            vars(self).update(vars(adopted))

    @cached_property
    def activated_at(self) -> str:
        """The immutable marker's publication date, shared by every delivery."""
        return datetime.fromtimestamp(self.marker.stat().st_mtime, UTC).isoformat()

    @cached_property
    def document(self) -> SourceDocument:
        # Bytes, not text: universal newlines would turn CRLF into LF, and
        # `document.data` must be the captured bytes the digest and the
        # unchanged-source check compare.
        # Set before the hold, which charges a reading by whether its document is
        # set, so a concurrent `read_revision` of this one holds it charged too.
        document = vars(self)["document"] = SourceDocument(
            self.marker.read_bytes().decode("utf-8")
        )
        memo(self.marker.parent.parent, _Readings).hold(self.marker, self.stamp, self)
        return document

    @cached_property
    def registry(self) -> dict:
        """The vocabulary this Leaf reads the revision in, shared read-only with
        every revision of the page that selects the same layer and declares the same
        (`revision_vocabulary`)."""
        return _bundle_vocabulary(self.bundle)

    @cached_property
    def inputs(self) -> tuple[dict, dict]:
        """The layer vocabulary and page declarations `registry` composes
        (`revision_inputs`)."""
        return revision_inputs(
            self.manifest, _bundle_declarations(self.bundle), self.bundle.parent.parent
        )

    @property
    def inventory(self):
        """Historical consumers outlive eviction of the expensive parse.

        A long history can exceed the document budget. Keeping only these compact
        immutable facts lets retries and new revisions reuse the completed scan.
        Only `_CompactReadings` holds them, under its own budget. The reading keeps
        no copy, since `_Readings` may hold it uncharged as long as the page's
        memory lives.
        """
        return memo(self.marker.parent.parent, _CompactReadings).get(
            self.marker,
            self.stamp,
            lambda: SourceReading._inventory.func(self),
            _inventory_size,
        )

    def under(self, registry: dict) -> SourceReading:
        """This revision's document read under `registry`: this held reading where
        that is the captured vocabulary itself, else a reading of its own. A caller
        reading the active revision under the active vocabulary holds the same
        object (`vocabulary.page_vocabulary`), so it shares these readings."""
        if registry is self.registry:
            return self
        return SourceReading(self.document, registry)

    @cached_property
    def enclosing(self) -> dict:
        """Where every id sits, read with no vocabulary (`enclosing_ids`): the answer
        for a caller that must not depend on the captured registry, such as a
        delivery or the Stop hook's thread fold."""
        return enclosing_ids(self.document)

    @cached_property
    def manifest_bytes(self) -> bytes:
        return (self.bundle / "manifest.json").read_bytes()

    @cached_property
    def manifest(self) -> dict:
        return json.loads(self.manifest_bytes)

    @cached_property
    def digest(self) -> str:
        """The captured artifact's identity, `RevisionArtifact.digest`."""
        return _digest(self.manifest_bytes)


def read_revision(page_dir: Path, revision: int) -> RevisionReading:
    """The one held reading of an immutable revision."""
    marker = revision_path(page_dir, revision).absolute()
    stamp = file_stamp(marker)
    readings = memo(page_dir, _Readings)
    reading = readings.get(marker, stamp) or RevisionReading(marker, stamp)
    return readings.hold(marker, stamp, reading)


def latest_title(page_dir: Path) -> tuple[int | None, str]:
    """The page's latest revision and its authored title, empty where the page has
    no revision or the revision no title."""
    revision = latest_revision(page_dir)
    if revision is None:
        return None, ""
    return revision, read_revision(page_dir, revision).document.authoring.title.strip()


class _Readings:
    """A page's held revision readings, least recently read first, within a budget.

    The budget is in authored source, since that is what a marker's stamp tells
    without a parse, and a reading's weight scales with it: a document, its passages
    and its words come to about twenty times the source (the corpus example's 336 KB
    to 8 MB, a median example's 11 KB to 0.2 MB). So 8 MB of source keeps one page's
    parses under about 160 MB. A reading is charged its source once it parses its
    document (`RevisionReading.document`), and nothing before, since until then it
    holds little more than the revision's manifest, once read. Each state read asks
    every earlier revision for its obligation registrations, which
    `_CompactReadings` keeps without a parse; charging those readings their source
    would push the active revision's parse out of a long history's budget, to be
    parsed again on the next read. A normal history fits whole: some 180 revisions of the largest
    shipped example page (44 KB), about 700 of the median one. A longer one
    re-parses an evicted revision a reader asks for again; a scan of the whole
    history reads each revision once (`revision_history`).

    Endpoints read from a thread pool, so every change is under the lock."""

    BUDGET = 8 * 1024 * 1024

    def __init__(self) -> None:
        # revision marker → (its stamp, the reading, what it is charged)
        self.held: dict[Path, tuple[tuple, RevisionReading, int]] = {}
        self.size = 0
        self.lock = threading.Lock()

    def get(self, marker: Path, stamp) -> RevisionReading | None:
        with self.lock:
            held = self.held.get(marker)
        return held[1] if held and held[0] == stamp else None

    def hold(self, marker: Path, stamp, reading: RevisionReading) -> RevisionReading:
        """Hold `reading` as the newest read, charged its source once it has parsed
        its document, within the budget."""
        with self.lock:
            held = self.held.pop(marker, None)
            if held:
                self.size -= held[2]
            if stamp:
                charge = stamp[2] if "document" in vars(reading) else 0
                self.held[marker] = (stamp, reading, charge)
                self.size += charge
                while self.size > self.BUDGET and len(self.held) > 1:
                    *_, evicted = self.held.pop(next(iter(self.held)))
                    self.size -= evicted
        return reading


def _inventory_size(value):
    """Charge retained compact objects once."""
    seen = set()

    def size(item):
        if id(item) in seen:
            return 0
        seen.add(id(item))
        held = sys.getsizeof(item)
        if isinstance(item, dict):
            return held + sum(size(key) + size(value) for key, value in item.items())
        if isinstance(item, (tuple, list, frozenset)):
            return held + sum(size(value) for value in item)
        return held

    return size(value)


class _CompactReadings:
    """Compact revision readings with their own byte budget and page lifetime.

    Element identities, obligation registration and data consumers are small facts
    about immutable documents. Keeping them separately prevents long-history scans
    from evicting their own completed work with full parses. Each owner charges its retained
    representation. Keys include the marker stamp. No document, full registry, SourceReading or event log is retained.
    """

    BUDGET = 8 * 1024 * 1024

    def __init__(self):
        self.held = {}
        self.size = 0
        self.lock = threading.Lock()

    def get(self, key, stamp, read, weight):
        with self.lock:
            held = self.held.pop(key, None)
            if held is not None:
                self.size -= held[2]
                if held[0] == stamp:
                    self.held[key] = held
                    self.size += held[2]
                    return held[1]
            value = read()
            size = weight(value)
            self.held[key] = (stamp, value, size)
            self.size += size
            while self.size > self.BUDGET and len(self.held) > 1:
                _, _, evicted_size = self.held.pop(next(iter(self.held)))
                self.size -= evicted_size
            return value


@dataclass(frozen=True)
class RevisionHistory:
    """What a scan across every stored revision reads: each id any revision
    authored, and each revision's data consumers (`SourceInventory`), oldest
    first. Callers read these and change neither."""

    ids: frozenset[str] = frozenset()
    data_documents: tuple[tuple[int, list], ...] = ()


class _History:
    """A page's `RevisionHistory` and the revision markers it has read.

    Markers are named by their content and only ever added, so a newer listing
    extends the one read, and only the revisions it adds are read. A scan that read
    each revision on every call would re-parse each one the compact budget had
    evicted."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.markers: tuple = ()
        self.history = RevisionHistory()


def revision_history(page_dir: Path) -> RevisionHistory:
    """The page's `RevisionHistory` through its newest revision."""
    markers = tuple(revision_names(page_dir).items())
    held = memo(page_dir, _History)
    with held.lock:
        if markers[: len(held.markers)] != held.markers:
            held.markers, held.history = (), RevisionHistory()
        if added := markers[len(held.markers) :]:
            inventories = [
                (revision, read_revision(page_dir, revision).inventory)
                for revision, _name in added
            ]
            held.history = RevisionHistory(
                held.history.ids.union(
                    *(inventory.ids for _, inventory in inventories)
                ),
                held.history.data_documents
                + tuple(
                    (revision, inventory.data_documents)
                    for revision, inventory in inventories
                ),
            )
            held.markers = markers
        return held.history


def active_enclosing(page_dir: Path) -> dict:
    """Where every id sits on the page the user is looking at.

    The newest valid revision is the live page. A page with no valid revision has
    nowhere for an element to sit."""
    revision = latest_revision(page_dir)
    if revision is None:
        return {}
    return read_revision(page_dir, revision).enclosing


class _Revisions(Stamped):
    """The vocabularies the page's revisions are read in (`revision_vocabulary`), one
    for each layer record, set of declarations and set of page widgets a revision
    captured. Each is kept beside the layer vocabulary it was composed over, and
    composed again once another replaces that.

    They are kept with the page rather than with the layer's vocabulary, which many
    pages may share (`layer._held`). Each names its page's generation under
    `$layer`, so only the page's samples, which read its revisions under that
    generation, could share one, and each sample composes its own instead. Kept with
    a shared vocabulary, they would outlast every page that read them."""


def revision_vocabulary(
    manifest: dict,
    declarations: bytes | None,
    page_dir: Path,
    *,
    layer: LayerVocabulary | None = None,
) -> dict:
    """The vocabulary this Leaf reads a revision of the page at `page_dir` in: the
    declarations it captured, `declarations`, over the layer its `manifest` selects,
    with the page widgets it captured. Every revision of the page selecting the same
    layer and declaring the same shares one read-only reading (`_Revisions`).

    A caller that also reads the layer's files passes the vocabulary they were
    composed with as `layer`, so both come from one installation
    (`layer.selected_vocabulary`); without it, the selection is resolved here."""
    return _revision_composition(manifest, declarations, page_dir, layer)[0]


def revision_inputs(
    manifest: dict, declarations: bytes | None, page_dir: Path
) -> tuple[dict, dict]:
    """The layer vocabulary and page declarations this Leaf composed and validated a
    revision's vocabulary from (`revision_vocabulary`), as
    `page.compose_page_registry` takes a composition already validated. The layer
    is the one that composition read, so a package installed since pairs with
    nothing it wasn't validated over."""
    return _revision_composition(manifest, declarations, page_dir, None)[1]


def _revision_composition(
    manifest: dict,
    declarations: bytes | None,
    page_dir: Path,
    layer: LayerVocabulary | None,
) -> tuple[dict, tuple[dict, dict]]:
    widgets = tuple(
        implementation["path"].lstrip("/")
        for implementation in manifest["implementations"].values()
        if implementation["owner"] == "page"
    )
    record = manifest["layer"]
    if layer is None:
        layer = selected_vocabulary(record, page_dir)
    # The composition is kept beside the one resolution it reads.
    held = memo(page_dir, _Revisions).of(
        (json.dumps(record, sort_keys=True), declarations, widgets), (layer,)
    )
    return once(
        held,
        "composition",
        lambda: _compose_revision(record, layer, declarations, widgets),
    )


def _compose_revision(
    record: dict,
    layer: LayerVocabulary,
    declarations: bytes | None,
    widgets: tuple[str, ...],
) -> tuple[dict, tuple[dict, dict]]:
    # The selected layer is validated where a Leaf composes its files
    # (`layer-registry.md`), so a revision declaring nothing over it is not
    # validated on a read.
    vocabulary = layer_vocabulary(record, layer)
    declared = json.loads(declarations) if declarations else {}
    composed = compose_page_registry(
        vocabulary,
        declared,
        [*layer_widgets(layer), *widgets],
        validated=(vocabulary, {}),
    )
    return composed.registry, (vocabulary, declared)


def _bundle_vocabulary(bundle: Path) -> dict:
    """The vocabulary of a stored bundle, as `RevisionArtifact.registry` reads it."""
    return revision_vocabulary(
        json.loads((bundle / "manifest.json").read_bytes()),
        _bundle_declarations(bundle),
        bundle.parent.parent,
    )


def _bundle_declarations(bundle: Path) -> bytes | None:
    """The page declarations a stored bundle captured, if it captured any."""
    declarations = bundle / ("resources" + PAGE_DECLARATIONS)
    return declarations.read_bytes() if declarations.is_file() else None


def _materialize(path: Path, bundle: Path) -> RevisionArtifact:
    """Read one immutable revision's manifest and retain its exact resource paths."""
    manifest_bytes = (bundle / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    resources = {
        logical: Resource(
            (bundle / ("resources" + logical)),
            record["mime"],
        )
        for logical, record in manifest["resources"].items()
    }
    html = path.read_bytes()
    artifact = RevisionArtifact(
        html, MappingProxyType(resources), manifest_bytes, bundle.parent.parent
    )
    if not path.stem.endswith(artifact.digest.removeprefix("sha256:")[:16]):
        raise artifact_error("manifest-digest", bundle)
    return artifact


def bind_imports(data: bytes, imports, address) -> bytes:
    """Rewrite each ``(start, end, target)`` import span to ``address(target)``."""
    return splice(
        data, [(start, end, _json(address(target))) for start, end, target in imports]
    )


def captured_imports(data: bytes, logical_path: str, resources: Mapping[str, Resource]):
    """Yield each literal import of one captured module as its span and target.

    Page modules resolve through `resource_urls.authored_imports`, whose public-import
    boundary is intentionally narrower. The layer's modules and the runtime's are
    trusted, so a local import need only be among `resources`, which a caller passes
    as the revision runs them (`runtime_selection.executing`). An import from another
    server is left to load from there, as a page module's is, and noted
    (`layer-import-remote`). A computed import, such as widget loading from the
    captured registry, binds at execution time and is not yielded.
    """
    if logical_path.startswith("/page/"):
        yield from authored_imports(data, logical_path)
        return
    for start, end, specifier in javascript_imports(data, logical_path):
        reference = dependency_reference(specifier, logical_path, module=True)
        if reference is None:
            note(capture_finding("layer-import-remote", logical_path, specifier))
            continue
        target, _suffix = reference
        if target not in resources:
            raise artifact_error("layer-import-missing", logical_path, specifier)
        yield start, end, target
