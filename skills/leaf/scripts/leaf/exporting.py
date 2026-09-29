"""A stamped version as one HTML file that opens offline.

The export packages the captured revision, its resources, and the page's authoritative
state reading into one file, and Leaf's normal runtime boots from them. There is no
second rendering: whatever the page draws when served, the file draws. Asset inlining
is shared with the MCP App resource, which embeds a page the same way.
"""

import base64
import json
import sys
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

from leaf.event_log import read_events
from leaf.files import (
    published_versions,
    version_name,
    version_revisions,
)
from leaf.page_snapshot import capture_page_snapshot
from leaf.revision_artifact import (
    RESOURCE_TYPES,
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
from leaf.structure import SourceDocument, page_policy
from leaf.thread_context import logged_fragment

ResourceReader = Callable[[str], Resource]


def _file_reader(page_dir: Path) -> ResourceReader:
    def read(url: str) -> Resource:
        parsed = urlsplit(url)
        path = (page_dir / parsed.path.lstrip("/")).resolve()
        if (
            parsed.scheme
            or parsed.netloc
            or not path.is_relative_to(page_dir.resolve())
        ):
            raise ValueError(f"export resource is outside the page: {url}")
        return Resource(path.read_bytes(), RESOURCE_TYPES[path.suffix])

    return read


def _data_url(resource: Resource) -> str:
    return f"data:{resource.mime};base64,{base64.b64encode(resource.data).decode()}"


class _AssetInliner:
    """Embed a resource graph as `data:` URLs, each with its captured MIME type.

    Imports remain CSS imports with embedded stylesheet URLs: their namespaces,
    cascade layers, supports clauses, and media conditions retain browser semantics.
    Each imported sheet resolves its own URLs before it is embedded. A cyclic import
    becomes an empty sheet, matching the browser's cycle suppression.
    """

    def __init__(self, read: ResourceReader):
        self.read = read
        self.resources: dict[str, Resource] = {}

    def resource(self, path: str) -> Resource:
        if path not in self.resources:
            self.resources[path] = self.read(path)
        return self.resources[path]

    def address(self, path: str, ancestors: tuple[str, ...] = ()) -> str:
        resource = self.resource(path)
        if resource.mime == "text/css":
            css = (
                ""
                if path in ancestors
                else self.css(resource.data.decode("utf-8"), path, (*ancestors, path))
            )
            resource = Resource(css.encode("utf-8"), "text/css")
        return _data_url(resource)

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


def inline_css_assets(
    css: str,
    page_dir: Path | None = None,
    *,
    read_resource: ResourceReader | None = None,
    document_url: str = "/index.html",
) -> str:
    """Embed CSS dependencies from one page directory or exact revision reader."""
    if read_resource is None:
        assert page_dir is not None
        read_resource = _file_reader(page_dir)
    return _AssetInliner(read_resource).css(css, document_url)


def embedding(
    page_dir: Path | None = None, *, read_resource: ResourceReader | None = None
) -> Delivery:
    """Deliver a document with its styles and media embedded, its modules as named.

    Resource readers own the authority boundary. A projection of the page directory
    reads its files; a non-browser projection can supply the artifact's captured
    resources. Delivery's own walk finds the references, so an embedded document names
    exactly what a served one does.
    """
    if read_resource is None:
        assert page_dir is not None
        read_resource = _file_reader(page_dir)
    assets = _AssetInliner(read_resource)
    return Delivery(
        address=lambda path: (
            path if Path(path).suffix in {".js", ".mjs"} else assets.address(path)
        ),
        inline_stylesheet=assets.stylesheet,
    )


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
    widgets = {
        f"/widgets/{tag}.js": implementation["path"]
        for tag, implementation in artifact.implementations.items()
        if tag in tags
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

    The import map is an address table, not another runtime: every module is the exact
    captured module with only its parsed local imports rebound to an in-file ``data:``
    URL. The normal application publisher, widgets, and presentation coordinator boot
    against the embedded authoritative reading. CSP admits embedded bytes and the
    external origins a page may name, so the file reaches no other network and opens
    offline wherever the page itself loads nothing from a CDN.
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
    inliner = _AssetInliner(artifact.resources.__getitem__)
    embedded_resources = {
        path: _data_url(resource)
        for path, resource in artifact.resources.items()
        if resource.mime not in {"application/javascript", "text/css"}
    }
    embedded_resources["/shadow.css"] = inliner.address("/shadow.css")
    embedded_resources["/registry.json"] = _data_url(
        artifact.resources["/registry.json"]
    )
    payload = json_script(
        {"state": state, "data": data, "resources": embedded_resources}
    )
    # An authored module is addressed at the same embedded URL the import map gives
    # its `leaf:` name, so a page module is one instance however it is reached.
    return compose_document(
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
            policy=lambda nonce: page_policy(nonce, ""),
            import_map={
                "imports": {
                    f"leaf:{path}": url for path, url in sorted(modules.items())
                }
            },
            runtime=lambda _nonce: (
                '<script type="application/json" data-lf-runtime data-lf-offline '
                'data-lf-page-root="" data-lf-entry="leaf:/leaf.js" data-lf-probe="">'
                f"{payload}</script>"
            ),
        ),
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
        layer_identity=snapshot.layer,
    ).page_state(revision)
    html = export_document(artifact, document, state, snapshot.data, revision, version)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(
        json.dumps({"file": str(out), "version": version, "bytes": out.stat().st_size})
    )
    return 0
