"""A stamped version as one HTML file that opens offline.

The export packages one current runtime, each page and message's captured widget
vocabulary, and the page's authoritative state reading into one file. Its resource
owner allocates one object URL per embedded body before handing the composed document to the native HTML parser; Leaf's normal
runtime then boots from that document. The normal composer also supplies the
scripts-off record: authored text, layout and alt text, with an explanation that
embedded graphics, fonts and recordings require JavaScript. Media is
embedded in full, including recordings: no size cap silently removes content, and
the reported output byte count includes the base64 expansion.
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from leaf.event_log import read_events
from leaf.files import (
    latest_revision,
    published_versions,
    version_name,
    version_revisions,
)
from leaf.page_snapshot import capture_page_snapshot
from leaf.refusals import Refused
from leaf.revision_artifact import (
    Resource,
    RevisionArtifact,
    artifact_name,
    bind_imports,
    captured_imports,
    dependency_path,
    read_artifact,
    read_revision,
)
from leaf.revision_delivery import (
    Delivery,
    PublicationAddress,
    RuntimeDelivery,
    compose_document,
    delivered_resource,
    json_script,
    module_address,
    publication_css,
    rebase_css,
)
from leaf.served_state.service import PageStateService
from leaf.structure import UTF8_BOM, SourceDocument
from leaf.thread_context import effective_thread_events, logged_fragment

ResourceReader = Callable[[str], Resource]


def _export_css(source, base, address, *, declarations=False):
    """Resolve captured CSS against its publication before embedding its graph."""
    if base.startswith("/revisions/"):
        _, _, publication, logical = base.split("/", 3)
        publication_address = PublicationAddress("", "/revisions/" + publication)
        return rebase_css(
            source,
            "/" + logical,
            lambda path: address(publication_address(path)),
            declarations=declarations,
        )
    return rebase_css(source, base, address, declarations=declarations)


def _data_url(resource: Resource) -> str:
    return f"data:{resource.mime};base64,{base64.b64encode(resource.data).decode()}"


@dataclass
class _CssFrame:
    """One stylesheet's unfinished rewrite in the resource traversal."""

    source: str
    base: str
    declarations: bool
    references: Iterator[str]
    addresses: dict[str, str | None]
    parent_reference: str | None = None

    @classmethod
    def read(
        cls,
        source: str,
        base: str,
        declarations: bool = False,
        parent_reference: str | None = None,
    ) -> _CssFrame:
        addresses: dict[str, str | None] = {}
        _export_css(
            source,
            base,
            lambda path: addresses.setdefault(path, path),
            declarations=declarations,
        )
        return cls(
            source, base, declarations, iter(addresses), addresses, parent_reference
        )


def _fragment(address: str | None, reference: str) -> str | None:
    fragment = urlsplit(reference).fragment
    return (
        address + (f"#{fragment}" if fragment else "") if address is not None else None
    )


class AssetInliner:
    """Give a resource graph one embedded body and one document-lifetime URL per resource.

    Imports remain CSS imports with embedded stylesheet URLs: their namespaces,
    cascade layers, supports clauses, and media conditions retain browser semantics.
    Each imported sheet resolves its own URLs before it is embedded. A cyclic import
    becomes an empty sheet, matching the browser's cycle suppression.
    """

    def __init__(self, read: ResourceReader):
        self.read = read
        self.resources: dict[str, Resource] = {}
        self.embedded: dict[str, Resource] = {}
        self.prefix = f"urn:leaf-resource:{uuid.uuid4().hex}:"

    def embed(self, resource: Resource) -> str | None:
        """One document-lifetime address for exact bytes and their MIME type."""
        data = resource.data
        token = (
            self.prefix
            + hashlib.sha256(resource.mime.encode() + b"\0" + data).hexdigest()
        )
        self.embedded[token] = Resource(data, resource.mime)
        return token

    def resource(self, path: str) -> Resource:
        if path not in self.resources:
            resource = self.read(path)
            self.resources[path] = Resource(
                resource.data, resource.mime, resource.dependencies
            )
        return self.resources[path]

    def address(self, reference: str) -> str | None:
        located = urlsplit(reference)
        path = unquote(located.path)
        resource = self.resource(path)
        if resource.mime == "text/css":
            resource = Resource(self.stylesheet(path).encode("utf-8"), "text/css")
        return _fragment(self.embed(resource), reference)

    def css(
        self,
        css: str,
        base: str,
        *,
        declarations: bool = False,
    ) -> str:
        """Rewrite the CSS graph in depth-first order without recursive resource reads."""
        stack = [_CssFrame.read(css, base, declarations)]
        active = {base}
        while True:
            frame = stack[-1]
            reference = next(frame.references, None)
            if reference is not None:
                path = unquote(urlsplit(reference).path)
                resource = self.resource(path)
                if resource.mime == "text/css":
                    if path not in active:
                        active.add(path)
                        stack.append(
                            _CssFrame.read(
                                resource.data.decode("utf-8"),
                                path,
                                parent_reference=reference,
                            )
                        )
                        continue
                    resource = Resource(b"", "text/css")
                frame.addresses[reference] = _fragment(self.embed(resource), reference)
                continue
            rewritten = _export_css(
                frame.source,
                frame.base,
                frame.addresses.__getitem__,
                declarations=frame.declarations,
            )
            stack.pop()
            active.remove(frame.base)
            if not stack:
                return rewritten
            stack[-1].addresses[frame.parent_reference] = _fragment(
                self.embed(Resource(rewritten.encode("utf-8"), "text/css")),
                frame.parent_reference,
            )

    def stylesheet(self, path: str) -> str:
        """A linked stylesheet's CSS, its own URLs embedded, to inline in its place."""
        resource = self.resource(path)
        if resource.mime != "text/css":
            raise ValueError(f"export stylesheet has MIME {resource.mime}: {path}")
        return self.css(resource.data.decode("utf-8"), path)


class ReadableAssets(AssetInliner):
    """The same CSS graph with unavailable binary declarations omitted.

    Native authored text, alt text and CSS layout work without scripts. Captured
    images, fonts and recordings belong to the interactive allocator, so their
    attributes and CSS declarations have no fallback address and make no requests.
    Imported sheets use nested base64 data URLs, whose output grows with every
    import level even though traversal does not consume the Python call stack.
    """

    def embed(self, resource: Resource) -> str | None:
        return _data_url(resource) if resource.mime == "text/css" else None


def _module_urls(
    resources: Mapping[str, Resource], pending: list[str]
) -> dict[str, str]:
    """Close the one runtime and publication-owned renderer graph into in-file modules."""
    urls = {}
    while pending:
        path = pending.pop()
        if path in urls:
            continue
        resource = resources[path]
        imports = list(captured_imports(resource.data, path, resources))
        pending.extend(target for _, _, target in imports)
        source = bind_imports(resource.data, imports, lambda path: f"leaf:{path}")
        urls[path] = _data_url(Resource(source, resource.mime))
    return urls


def _export_resources(kernel, publications, roots, markup, data_resources):
    """Captured resource namespaces, module entries and classic initial producers."""
    resources = dict(kernel.resources)
    resources.update(data_resources)
    pending = ["/leaf.js"]
    initializers = set()
    for revision, artifact in publications.items():
        root = roots[str(revision)]
        address = PublicationAddress("", root, artifact.shared_modules)
        for logical in artifact.resources.keys() | artifact.widget_aliases.keys():
            original = artifact.resources.get(logical)
            if original is not None and original.mime == "text/css":
                body = original.data.decode()
                if logical == "/widget-theme.css":
                    body = publication_css(body, revision)
                resource = Resource(body.encode(), "text/css")
            else:
                resource = delivered_resource(artifact, logical, address)
            resources[root + logical] = resource
        entries = [
            path
            for path in artifact.entries
            if artifact.resources[path].mime == "application/javascript"
        ]
        tags = {
            record["tag"]
            for document in markup[revision]
            for record in document.lf_elements
        }
        entries.extend(
            f"/widgets/{tag}.js"
            for tag in tags
            if artifact.registry.get(tag, {}).get("x-upgrade")
        )
        # The host addresses URLs; graph traversal consumes captured logical paths.
        pending.extend(
            dependency_path(module_address(path, address), "/index.html", module=True)
            for path in entries
        )
        initializers.update(
            root + initial
            for tag in tags
            if (initial := artifact.registry.get(tag, {}).get("x-initial"))
        )
    return resources, pending, initializers


def export_document(
    artifact: RevisionArtifact,
    document: SourceDocument,
    state: dict,
    data: dict,
    revision: int,
    version: int,
    data_resources: Mapping[str, Resource],
    *,
    kernel: RevisionArtifact,
    publications: dict[int, RevisionArtifact],
) -> str:
    """Package one captured revision for Leaf's normal runtime without a host.

    `document` is that revision's parsed markup (`read_revision`); a page declaring a
    live sample is refused before this, by `cmd_export`.

    The import map is an address table: every module is the exact
    captured module with only its parsed local imports rebound to an in-file ``data:``
    URL. The normal application publisher, widgets, and presentation coordinator boot
    against the embedded authoritative reading, so the file opens offline wherever the
    page itself names no other server.
    """
    roots = {
        str(publication): "/revisions/" + artifact_name(publication, captured)
        for publication, captured in publications.items()
    }
    events = effective_thread_events(state["events"], publications)
    state = {**state, "events": events}
    markup = {publication: [] for publication in publications}
    markup[revision].append(document)
    for event in events:
        if event.get("markup"):
            markup[event["revision"]].append(logged_fragment(event))
    resources, pending, initializers = _export_resources(
        kernel, publications, roots, markup, data_resources
    )
    modules = _module_urls(resources, pending)
    publication_address = PublicationAddress(
        "", roots[str(revision)], artifact.shared_modules
    )
    state = {**state, "vocabularies": roots}
    inliner = AssetInliner(resources.__getitem__)
    # Replacement markers belong to delivery, never to authored prose, state, data or
    # CSS strings. Reserve a fresh namespace absent from every text it will rewrite.
    authored_text = [
        artifact.html.decode(),
        json_script({"state": state, "data": data}),
        *(
            resource.data.decode()
            for resource in resources.values()
            if resource.mime == "text/css"
        ),
    ]
    while any(inliner.prefix in text for text in authored_text):
        inliner.prefix = f"urn:leaf-resource:{uuid.uuid4().hex}:"
    embedded_resources = {
        path: inliner.address(path)
        for path, resource in resources.items()
        if resource.mime not in {"application/javascript", "text/css"}
    }
    # Initial producers execute as classic scripts so registration can read the
    # publication carried by document.currentScript. They are resources, not ESM.
    embedded_resources.update(
        (path, inliner.address(path)) for path in sorted(initializers)
    )
    embedded_resources["/shadow.css"] = inliner.address("/shadow.css")
    for root in roots.values():
        for path in ("/shadow.css", "/widget-theme.css"):
            embedded_resources[root + path] = inliner.address(root + path)
    embedded_resources["/registry.json"] = inliner.address("/registry.json")
    payload = json_script(
        {"state": state, "data": data, "resources": embedded_resources}
    )

    # An authored module is addressed at the same embedded URL the import map gives
    # its `leaf:` name, so a page module is one instance however it is reached.
    def address(path):
        located = publication_address(path)
        logical = unquote(urlsplit(located).path)
        return modules[logical] if logical in modules else inliner.address(located)

    def stylesheet(path):
        return inliner.stylesheet(
            path if path == "/theme.css" else publication_address(path)
        )

    composed = compose_document(
        artifact.html.decode("utf-8"),
        revision,
        version,
        executable=artifact.executable,
        widgets=artifact.widgets,
        resources=artifact.resources | data_resources,
        registry=artifact.registry,
        delivery=Delivery(
            address=address,
            kernel=RuntimeDelivery(
                kernel.resources,
                lambda path: (
                    modules[path] if path in modules else inliner.address(path)
                ),
            ),
            inline_stylesheet=stylesheet,
            import_map={
                "imports": {
                    f"leaf:{path}": url for path, url in sorted(modules.items())
                }
            },
            runtime=(
                '<script type="application/json" data-lf-runtime data-lf-offline '
                'data-lf-page-root="" data-lf-entry="leaf:/leaf.js" data-lf-probe="/registry.json" '
                f'data-lf-vocabulary-root="{roots[str(revision)]}/registry.json">'
                f"{payload}</script>"
            ),
        ),
    )
    # Native attributes, inline styles, CSS imports and the runtime address table all
    # name the same tokens. Allocate their object URLs before this composed document
    # enters the HTML parser, so no consumer can fetch an unresolved reference.
    package = json_script(
        {
            "document": composed.removeprefix(UTF8_BOM),
            "prefix": inliner.prefix,
            "resources": {
                token: {
                    "mime": resource.mime,
                    "base64": base64.b64encode(resource.data).decode(),
                }
                for token, resource in inliner.embedded.items()
            },
        }
    )
    readable = ReadableAssets(inliner.resource)
    bootstrap = kernel.resources["/runtime/offline-delivery.js"].data.decode()
    fallback = compose_document(
        artifact.html.decode("utf-8"),
        revision,
        version,
        executable=artifact.executable,
        widgets=artifact.widgets,
        resources=artifact.resources | data_resources,
        registry=artifact.registry,
        delivery=Delivery(
            address=lambda path: readable.address(publication_address(path)),
            kernel=RuntimeDelivery(kernel.resources, readable.address),
            inline_stylesheet=lambda path: readable.stylesheet(
                path if path == "/theme.css" else publication_address(path)
            ),
            html_attributes={"data-lf-export-pending": ""},
            head=(
                "<style>[data-lf-export-pending] body {visibility:hidden}</style>"
                "<noscript><style>[data-lf-export-pending] body {visibility:visible}</style></noscript>"
                f'<script type="application/json" data-lf-export>{package}</script>'
                f"<script>{bootstrap}</script>"
            ),
        ),
    )
    # The readable record is the outer document, not raw text inside a noscript
    # wrapper: authored noscript elements keep native semantics in both parser modes.
    body = SourceDocument(fallback).wrapper_tags["body"][1]
    note = (
        '<noscript><p role="note">This file needs JavaScript to display embedded '
        "images, fonts, and recordings. The captured text is shown below.</p></noscript>"
    )
    return fallback[:body] + note + fallback[body:]


def cmd_export(page_dir: Path, out: Path, version) -> int:
    """One stamped version as a standalone HTML file that opens offline.

    The file carries the captured revision and Leaf's normal runtime, which boots from
    the embedded authoritative reading. It has no host command or transport capability."""
    events = read_events(page_dir)
    published = published_versions(page_dir, events)
    if not published:
        raise Refused(
            f"{page_dir} has no stamped version to export; run `leaf page stamp` first"
        )
    version = version if version else published[-1]
    if version not in published:
        raise Refused(
            f"v{version} is not stamped — stamped: "
            + ", ".join(f"v{v}" for v in published)
        )
    name = version_name(version)
    revision = version_revisions(events)[version]
    document = read_revision(page_dir, revision).document
    if document.samples:
        raise Refused(
            "Live samples need a server, so a page that declares one "
            "cannot be exported."
        )
    artifact = read_artifact(page_dir, revision)
    snapshot = capture_page_snapshot(
        page_dir, document, revision, url=f"/versions/{name}", artifact=artifact
    )
    state = PageStateService(
        page_dir,
        source=snapshot,
    ).page_state(revision)
    html = export_document(
        artifact,
        document,
        state,
        snapshot.context.data,
        revision,
        version,
        snapshot.data_resources,
        kernel=read_artifact(page_dir, latest_revision(page_dir)),
        publications={
            publication: read_artifact(page_dir, publication)
            for publication in {
                revision,
                *(
                    event["revision"]
                    for event in state["events"]
                    if event.get("markup")
                ),
            }
        },
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(
        json.dumps({"file": str(out), "version": version, "bytes": out.stat().st_size})
    )
    return 0
