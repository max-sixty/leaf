"""A stamped version as one HTML file that opens offline.

The export packages the captured revision, its resources, and the page's authoritative
state reading into one file. Its resource owner allocates one object URL per embedded
body before handing the composed document to the native HTML parser; Leaf's normal
runtime then boots from that document. The normal composer also supplies the
scripts-off record: authored text, layout and alt text, with an explanation that
embedded graphics, fonts and recordings require JavaScript. Media is
embedded in full, including recordings: no size cap silently removes content, and
the reported output byte count includes the base64 expansion.
"""

import base64
import hashlib
import json
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote, urlsplit

from leaf.event_log import read_events
from leaf.files import (
    published_versions,
    version_name,
    version_revisions,
)
from leaf.page_snapshot import capture_page_snapshot
from leaf.revision_artifact import (
    Resource,
    RevisionArtifact,
    bind_imports,
    captured_imports,
    read_artifact,
    read_revision,
)
from leaf.revision_delivery import (
    Delivery,
    compose_document,
    json_script,
    rebase_css,
)
from leaf.served_state.service import PageStateService
from leaf.structure import UTF8_BOM, SourceDocument
from leaf.thread_context import logged_fragment

ResourceReader = Callable[[str], Resource]


def _data_url(resource: Resource) -> str:
    return f"data:{resource.mime};base64,{base64.b64encode(resource.data).decode()}"


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

    def embed(self, resource: Resource) -> str:
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

    def address(self, path: str, ancestors: tuple[str, ...] = ()) -> str | None:
        located = urlsplit(path)
        path = unquote(located.path)
        resource = self.resource(path)
        if resource.mime == "text/css":
            css = (
                ""
                if path in ancestors
                else self.css(resource.data.decode("utf-8"), path, (*ancestors, path))
            )
            resource = Resource(css.encode("utf-8"), "text/css")
        embedded = self.embed(resource)
        return (
            embedded + ("#" + located.fragment if located.fragment else "")
            if embedded is not None
            else None
        )

    def css(
        self,
        css: str,
        base: str,
        ancestors: tuple[str, ...] = (),
        *,
        declarations: bool = False,
    ) -> str:
        return rebase_css(
            css,
            base,
            lambda path: self.address(path, ancestors),
            declarations=declarations,
        )

    def stylesheet(self, path: str) -> str:
        """A linked stylesheet's CSS, its own URLs embedded, to inline in its place."""
        resource = self.resource(path)
        if resource.mime != "text/css":
            raise ValueError(f"export stylesheet has MIME {resource.mime}: {path}")
        return self.css(resource.data.decode("utf-8"), path, (path,))


class ReadableAssets(AssetInliner):
    """The same CSS graph with unavailable binary declarations omitted.

    Native authored text, alt text and CSS layout work without scripts. Captured
    images, fonts and recordings belong to the interactive allocator, so their
    attributes and CSS declarations have no fallback address and make no requests.
    """

    def embed(self, resource: Resource) -> str | None:
        return _data_url(resource) if resource.mime == "text/css" else None


def _module_urls(
    artifact: RevisionArtifact, markup: list[SourceDocument]
) -> dict[str, str]:
    """Embed the module graph this file can reach, and no other module.

    The one computed import an exported page makes is a widget's module, asked for only
    where the widget's tag stands in markup about to be upgraded (`importWidgets` in
    `runtime/widget-loader.js`). Offline that markup is the captured page and the frozen
    markup its messages carry, since the embedded reading never activates another
    revision. Every other import is literal, so the runtime entry, the page's own
    modules, and the modules of the widgets that markup names close the graph: a page
    that draws no diff carries no diff renderer.
    """
    tags = {record["tag"] for document in markup for record in document.lf_elements}
    required = {f"/widgets/{tag}.js" for tag in tags}
    widgets = {
        alias: source
        for alias, source in artifact.widget_aliases.items()
        if alias in required
    }
    pending = [
        "/leaf.js",
        *(
            path
            for path in artifact.entries
            if artifact.resources[path].mime == "application/javascript"
        ),
        *widgets.values(),
    ]
    urls = {}
    while pending:
        path = pending.pop()
        if path in urls:
            continue
        resource = artifact.resources[path]
        imports = list(captured_imports(resource.data, path, artifact.resources))
        pending.extend(target for _, _, target in imports)
        source = bind_imports(resource.data, imports, lambda path: f"leaf:{path}")
        urls[path] = _data_url(Resource(source, resource.mime))
    return urls | {alias: urls[path] for alias, path in widgets.items()}


def export_document(
    artifact: RevisionArtifact,
    document: SourceDocument,
    state: dict,
    data: dict,
    revision: int,
    version: int,
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
    modules = _module_urls(
        artifact,
        [
            document,
            *(
                logged_fragment(event)
                for event in state["events"]
                if event.get("markup")
            ),
        ],
    )
    inliner = AssetInliner(artifact.resources.__getitem__)
    # Replacement markers belong to delivery, never to authored prose, state, data or
    # CSS strings. Reserve a fresh namespace absent from every text it will rewrite.
    authored_text = [
        artifact.html.decode(),
        json_script({"state": state, "data": data}),
        *(
            resource.data.decode()
            for resource in artifact.resources.values()
            if resource.mime == "text/css"
        ),
    ]
    while any(inliner.prefix in text for text in authored_text):
        inliner.prefix = f"urn:leaf-resource:{uuid.uuid4().hex}:"
    embedded_resources = {
        path: inliner.address(path)
        for path, resource in artifact.resources.items()
        if resource.mime not in {"application/javascript", "text/css"}
    }
    embedded_resources["/shadow.css"] = inliner.address("/shadow.css")
    embedded_resources["/registry.json"] = inliner.address("/registry.json")
    payload = json_script(
        {"state": state, "data": data, "resources": embedded_resources}
    )
    # An authored module is addressed at the same embedded URL the import map gives
    # its `leaf:` name, so a page module is one instance however it is reached.
    composed = compose_document(
        artifact.html.decode("utf-8"),
        revision,
        version,
        executable=artifact.executable,
        widgets=artifact.widgets,
        resources=artifact.resources,
        registry=artifact.registry,
        delivery=Delivery(
            address=lambda path: (
                modules[path] if path in modules else inliner.address(path)
            ),
            inline_stylesheet=inliner.stylesheet,
            import_map={
                "imports": {
                    f"leaf:{path}": url for path, url in sorted(modules.items())
                }
            },
            runtime=(
                '<script type="application/json" data-lf-runtime data-lf-offline '
                'data-lf-page-root="" data-lf-entry="leaf:/leaf.js" data-lf-probe="">'
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
    fallback = compose_document(
        artifact.html.decode("utf-8"),
        revision,
        version,
        executable=artifact.executable,
        widgets=artifact.widgets,
        resources=artifact.resources,
        registry=artifact.registry,
        delivery=Delivery(
            address=readable.address,
            inline_stylesheet=readable.stylesheet,
        ),
    ).removeprefix(UTF8_BOM)
    bootstrap = artifact.resources["/runtime/offline-delivery.js"].data.decode()
    return (
        (UTF8_BOM if composed.startswith(UTF8_BOM) else "")
        + '<!doctype html><html><head><meta charset="utf-8">'
        + "<noscript>"
        + '<p role="note">This file needs JavaScript to display embedded images, fonts, '
        + "and recordings. The captured text is shown below.</p>"
        + fallback
        + "</noscript>"
        + f'<script type="application/json" data-lf-export>{package}</script>'
        + f"<script>{bootstrap}</script></head><body></body></html>"
    )


def cmd_export(page_dir: Path, out: Path, version) -> int:
    """One stamped version as a standalone HTML file that opens offline.

    The file carries the captured revision and Leaf's normal runtime, which boots from
    the embedded authoritative reading. It has no host command or transport capability."""
    events = read_events(page_dir)
    published = published_versions(page_dir, events)
    if not published:
        sys.exit(
            f"{page_dir} has no stamped version to export; run `leaf page stamp` first"
        )
    version = version if version else published[-1]
    if version not in published:
        sys.exit(
            f"v{version} is not stamped — stamped: "
            + ", ".join(f"v{v}" for v in published)
        )
    name = version_name(version)
    revision = version_revisions(events)[version]
    document = read_revision(page_dir, revision).document
    if document.samples:
        sys.exit(
            "Live samples need a server, so a page that declares one "
            "cannot be exported."
        )
    artifact = read_artifact(page_dir, revision)
    active = {"revision": revision, "version": version, "url": f"/versions/{name}"}
    snapshot = capture_page_snapshot(page_dir, document, active, artifact=artifact)
    state = PageStateService(
        page_dir,
        page_snapshot=snapshot,
        layer_identity=snapshot.context.layer,
    ).page_state(revision)
    html = export_document(
        artifact, document, state, snapshot.context.data, revision, version
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(
        json.dumps({"file": str(out), "version": version, "bytes": out.stat().st_size})
    )
    return 0
