"""A captured revision as one HTML file that opens offline.

Every export starts from one package (`export_document`): the captured revision, its
resources, the exporting Leaf's runtime (`runtime_selection`), and a state reading of
the page, which that runtime reads. Neighboring live pages are omitted: their access
URLs grant machine-wide server access and have no place in an offline record.

Most exports are read rather than operated, so by default the file is the page the
package draws, not the package (`static_document`): the host's browser boots the
package once, and the file keeps the page's markup with each widget in its current
state, what each fold draws once opened, its images and fonts as data URLs, and no
script. It shows the same with scripts off, and it leaves out the runtime, which is
nearly all of a package's bytes. With `runtime` the file is the package, for a reader
who should operate the widgets.

Widgets draw only in the browser, so a file without the runtime needs either a browser
at export time or a second, script-free renderer for every widget. A browser keeps one
renderer and asks nothing of a package; the host already supplies one for `page check
--render`. Its cost is that what a widget computes while drawing keeps the desktop
window it was drawn in (`render_checks.RENDER_VIEWPORT`): on a phone a chart shrinks to
fit rather than redrawing, and a contents list the runtime folds for a narrow window
stays open. The file's CSS adapts the rest to its reader's window and color scheme. A
renderer per widget would need no browser, but every package, a third party's too,
would have to keep it matching the first.

An export goes to people who shouldn't see what the user and the agent said to each
other, so the file holds the page and none of the conversation. Its reading is folded
from `_page_log`, the part of the log that changes the page, with no process facts
(`capture_page_snapshot`'s `process`). Threads, obligations, queues, to-dos, activity
and history are all readings of that log, so none of them has a message to carry, and
a new kind of event stays out until `_page_log` names it. A widget in a message can
bind a data source and an image can be attached to a message, so the file holds only
the data the page's own markup binds (`markup_data`) and the media that markup and data
name.

Two other designs were rejected. Embedding the threads and turning their surface
off hides the discussion from the page's reader and leaves it readable in the file's
source. Showing the threads read-only would put the discussion in front of
the same people.

The package's resource owner allocates one object URL per embedded body before handing
the composed document to the native HTML parser; Leaf's normal
runtime then boots from that document. The normal composer also supplies the
scripts-off record: authored text, layout and alt text, with an explanation that
embedded graphics, fonts and recordings require JavaScript. Media is
embedded in full, including recordings: no size cap silently removes content, and
the reported output byte count includes the base64 expansion.

Data is embedded beside media, not in the reading the composed document carries:
the sources' values are one gzipped JSON object, embedded as one file, so they cost
startup one object URL. The runtime decodes them when it reads the page's
state, as a served page's first state answer brings them (`runtime/state/context.js`). A
value inside the composed document would cross the package's JSON, the HTML parser
and the reading's JSON before any widget read it, escaped again at each JSON layer.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from leaf.base.files import (
    published_versions,
    version_name,
    version_revisions,
)
from leaf.base.refusals import Refused
from leaf.pages.page_snapshot import capture_page_snapshot
from leaf.records.revisioning import activate_source
from leaf.records.transaction import PageTransaction
from leaf.serving.revision_delivery import (
    Delivery,
    compose_document,
    json_script,
    rebase_css,
    runtime_settings,
)
from leaf.serving.served_state.service import PageStateService
from leaf.source.data import read_data
from leaf.source.data_contracts import data_bindings
from leaf.source.registry.kernel import verb_writers
from leaf.source.render_checks import (
    RENDER_VIEWPORT,
    PageNotReady,
    open_render_page,
    wait_until_ready,
)
from leaf.source.revision_artifact import (
    Resource,
    RevisionArtifact,
    bind_imports,
    captured_imports,
    read_artifact,
    read_revision,
)
from leaf.source.runtime_selection import executing
from leaf.source.structure import UTF8_BOM, SourceDocument

ResourceReader = Callable[[str], Resource]

DRAWING = Path(__file__).with_name("static-export.js")
# Where the browser opens the package to draw it. An https origin is a secure context,
# as a file is, and `.invalid` never resolves, so a request the page makes beyond
# itself fails as it would offline. The address's path is `/`, so the drawing carries
# no local path, as the page's storage scope would from a file (`prepaint.js`).
DRAWING_URL = "https://leaf.invalid/"


def _data_url(resource: Resource) -> str:
    return f"data:{resource.mime};base64,{base64.b64encode(resource.data).decode()}"


def _data_body(values: dict) -> bytes:
    """The one embedded file holding every source's value (the module header), which
    the runtime reads (`offlineState` in `runtime/state/context.js`): a JSON object keyed by
    source, gzipped. Nothing compresses a file opened from disk or sent as an
    attachment, and gzip puts prose and code in the file at about 40% of their size,
    base64 included, where uncompressed base64 takes 133%. Level 6 packs within 1% of
    gzip's default 9 in a third to a half of the time."""
    return gzip.compress(
        json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode(),
        compresslevel=6,
    )


@dataclass
class _CssFrame:
    """One stylesheet's unfinished rewrite in the resource traversal."""

    source: str
    base: str
    references: Iterator[str]
    addresses: dict[str, str | None]
    parent_reference: str | None = None

    @classmethod
    def read(
        cls,
        source: str,
        base: str,
        parent_reference: str | None = None,
    ) -> _CssFrame:
        addresses: dict[str, str | None] = {}
        rebase_css(source, base, lambda path: addresses.setdefault(path, path))
        return cls(source, base, iter(addresses), addresses, parent_reference)


def _fragment(address: str | None, reference: str) -> str | None:
    fragment = urlsplit(reference).fragment
    return (
        address + (f"#{fragment}" if fragment else "") if address is not None else None
    )


class _Assets(ABC):
    """Traverse the CSS resource graph with the delivery's embedding policy.

    Imports remain CSS imports with embedded stylesheet URLs: their namespaces,
    cascade layers, supports clauses, and media conditions retain browser semantics.
    Each imported sheet resolves its own URLs before it is embedded. A cyclic import
    becomes an empty sheet, matching the browser's cycle suppression.
    """

    def __init__(self, read: ResourceReader):
        self.read = read
        self.resources: dict[str, Resource] = {}

    @abstractmethod
    def embed(self, resource: Resource) -> str | None:
        """Embed a resource, or omit it from this delivery."""

    def resource(self, path: str) -> Resource:
        if path not in self.resources:
            resource = self.read(path)
            self.resources[path] = Resource(resource.data, resource.mime)
        return self.resources[path]

    def address(self, reference: str) -> str | None:
        located = urlsplit(reference)
        path = unquote(located.path)
        resource = self.resource(path)
        if resource.mime == "text/css":
            resource = Resource(self.stylesheet(path).encode("utf-8"), "text/css")
        return _fragment(self.embed(resource), reference)

    def css(self, css: str, base: str) -> str:
        """Rewrite the CSS graph in depth-first order without recursive resource reads."""
        stack = [_CssFrame.read(css, base)]
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
            rewritten = rebase_css(
                frame.source, frame.base, frame.addresses.__getitem__
            )
            stack.pop()
            active.remove(frame.base)
            if not stack:
                return rewritten
            assert frame.parent_reference is not None
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


class AssetInliner(_Assets):
    """Give each resource one embedded body and one document-lifetime URL."""

    def __init__(self, read: ResourceReader):
        super().__init__(read)
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


class ReadableAssets(_Assets):
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
    artifact: RevisionArtifact, document: SourceDocument, inliner: AssetInliner
) -> dict[str, str]:
    """Embed the module graph this file can reach, and no other module.

    The computed imports an exported page makes are widget modules, asked for only
    where the widget's tag stands in markup about to be upgraded (`importWidgets` in
    `runtime/records/widget-loader.js`). Offline that markup is the captured page, since the
    embedded reading never activates another revision and holds no message. Every
    other import is literal, so the runtime entry, the page's own modules, and the
    modules of the widgets its markup names close the graph: a page that draws no diff
    carries no diff renderer.
    """
    tags = {record["tag"] for record in document.lf_elements}
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
        urls[path] = inliner.embed(Resource(source, resource.mime))
    return urls | {alias: urls[path] for alias, path in widgets.items()}


def _page_log(events: list[dict]) -> list[dict]:
    """The log an export's reading folds (the module header): each action and report on
    a page widget (`verb_writers`), each undo of one, and each stamp, which maps a
    version to its revision and names the decisions it takes back.

    A widget in a message belongs to its thread, so the file leaves its actions
    out with the thread. A stamp's changelog is the agent's words to the user, so a
    blank replaces it, since the record's schema requires text. An event's `session`
    names the agent's session, and the page has no use for it.
    """
    widget_state = {
        event["id"]
        for event in events
        if event["kind"] in verb_writers() and event["meaning"]["scope"] == "page"
    }
    page_log = []
    for event in events:
        if event["kind"] == "note":
            event = {**event, "text": " "}
        elif not (event["id"] in widget_state or event.get("undoes") in widget_state):
            continue
        page_log.append(
            {key: value for key, value in event.items() if key != "session"}
        )
    return page_log


def markup_data(page_dir: Path, document: SourceDocument, registry: dict) -> dict:
    """The stored data the file holds (the module header), and the state a hosted
    page's first visit reads: each source `document` binds, which leaves out a source
    only a message's widget or an earlier revision binds, and a file the page grants
    that no markup shows. A widget a page's script creates finds its source only if
    the page's markup binds it too."""
    stored = read_data(page_dir, registry)
    bound = {source for *_, source in data_bindings(document.lf_elements, registry)}
    return {
        **stored,
        "sources": {
            source: reading
            for source, reading in stored["sources"].items()
            if source in bound
        },
    }


def export_document(
    artifact: RevisionArtifact,
    document: SourceDocument,
    state: dict,
    revision: int,
    version: int | None,
    data_resources: Mapping[str, Resource],
) -> str:
    """Package one captured revision for Leaf's normal runtime without a host.

    `document` is that revision's parsed markup (`read_revision`); a page declaring a
    live sample is refused before this, by `cmd_export`.

    The import map is an address table: every module is the exact
    captured module with its parsed local imports rebound to ``leaf:`` names.
    The shared resource allocator gives each embedded module one object URL.
    The normal application publisher, widgets, and presentation coordinator boot
    against the embedded authoritative reading, so the file opens offline wherever the
    page itself names no other server.
    """
    # The reading leaves out the values, which the data file holds (the module header).
    values = {
        source: reading["value"]
        for source, reading in state["data"]["sources"].items()
        if "value" in reading
    }
    state = {
        **state,
        "data": {
            **state["data"],
            "sources": {
                source: {key: item for key, item in reading.items() if key != "value"}
                for source, reading in state["data"]["sources"].items()
            },
        },
    }
    resources = {**artifact.resources, **data_resources}
    inliner = AssetInliner(resources.__getitem__)
    # Replacement markers belong to delivery, never to authored prose, state or CSS
    # strings. Reserve a fresh namespace absent from every text it will rewrite. Data
    # bodies are never rewritten, so their text may hold anything.
    authored_text = [
        artifact.html.decode(),
        json_script(state),
        *(
            resource.data.decode()
            for resource in artifact.resources.values()
            if resource.mime == "text/css"
        ),
    ]
    while any(inliner.prefix in text for text in authored_text):
        inliner.prefix = f"urn:leaf-resource:{uuid.uuid4().hex}:"
    modules = _module_urls(artifact, document, inliner)
    embedded_resources = {
        path: inliner.address(path)
        for path, resource in resources.items()
        if resource.mime not in {"application/javascript", "text/css"}
    }
    embedded_resources["/shadow.css"] = inliner.address("/shadow.css")
    embedded_resources["/registry.json"] = inliner.address("/registry.json")
    payload = json_script(
        {
            "state": state,
            "data": inliner.embed(Resource(_data_body(values), "application/gzip")),
            "resources": embedded_resources,
        }
    )

    # An authored module is addressed at the same embedded URL the import map gives
    # its `leaf:` name, so a page module is one instance however it is reached.
    def address(path):
        logical = unquote(urlsplit(path).path)
        return modules[logical] if logical in modules else inliner.address(path)

    composed = compose_document(
        artifact.html.decode("utf-8"),
        revision,
        version,
        executable=artifact.executable,
        resources=resources,
        registry=artifact.registry,
        delivery=Delivery(
            address=address,
            inline_stylesheet=inliner.stylesheet,
            import_map={
                "imports": {
                    f"leaf:{path}": url for path, url in sorted(modules.items())
                }
            },
            # The generation the revision was captured at, which the runtime holds
            # the embedded registry and reading to (`transport/layer-client.js`), as it holds a
            # served document's.
            runtime=runtime_settings(
                payload,
                layer=str(artifact.registry["$layer"]["generation"]),
                page_root="",
                entry="leaf:/leaf.js",
                probe="",
                declared={"type": "application/json", "data-lf-offline": True},
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
    bootstrap = artifact.resources["/runtime/base/offline-delivery.js"].data.decode()
    fallback = compose_document(
        artifact.html.decode("utf-8"),
        revision,
        version,
        executable=artifact.executable,
        resources=resources,
        registry=artifact.registry,
        delivery=Delivery(
            address=readable.address,
            inline_stylesheet=readable.stylesheet,
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
    body = SourceDocument(fallback).authoring.wrapper_tags["body"][1]
    note = (
        '<noscript><p role="note">This file needs JavaScript to display embedded '
        "images, fonts, and recordings. The captured text is shown below.</p></noscript>"
    )
    return fallback[:body] + note + fallback[body:]


def static_document(package: str) -> str:
    """The page `package` (`export_document`) draws, as one file with no script.

    The host's browser opens the package at the fixed desktop window
    (`render_checks.RENDER_VIEWPORT`) and waits until the page is ready, as any reader
    outside it does. It then opens the page's folds, waiting again after each round,
    until a round finds none, closes them again, and once the page is ready once more
    serializes what it drew (`static-export.js`).
    Refused where the host has no browser, or the page cannot start, since there is
    then no drawing to keep."""
    from leaf.pages.render_gate.command import NoBrowser, run_in_browser

    def draw(browser) -> str:
        page = open_render_page(browser, viewport=RENDER_VIEWPORT)
        page.add_init_script(path=DRAWING)
        page.route(
            DRAWING_URL,
            lambda route: route.fulfill(body=package, content_type="text/html"),
        )
        page.goto(DRAWING_URL, wait_until="load")
        wait_until_ready(page, fixed_server=True)
        while page.evaluate("globalThis.__leafStaticExport.unfold()"):
            wait_until_ready(page, fixed_server=True)
        page.evaluate("globalThis.__leafStaticExport.refold()")
        wait_until_ready(page, fixed_server=True)
        return page.evaluate("globalThis.__leafStaticExport.document()")

    try:
        drawn, _ = run_in_browser(draw)
    except NoBrowser as error:
        raise Refused(
            f"An export draws the page in a browser, and {error} "
            "`--runtime` exports the page with Leaf's runtime, which needs none."
        ) from error
    except PageNotReady as error:
        raise Refused(f"The page didn't draw: {error}") from error
    return drawn


def cmd_export(
    page_dir: Path,
    out: Path,
    version: int | None,
    *,
    draft: bool = False,
    runtime: bool = False,
) -> dict:
    """Export the selected stamp, or current valid source with `draft`, as the page
    it draws, or with `runtime` as the package that draws it (the module header).

    Draft export activates source through the same check as a live page, preserving
    decisions and reanchors without adding a version checkpoint. Selection and the
    authoritative snapshot share one page transaction. The file has no host command
    or transport capability, and no conversation (the module header).
    """
    if draft and version is not None:
        raise Refused("--draft and --version cannot be used together")
    with PageTransaction(page_dir) as page:
        if draft:
            activation = activate_source(page_dir, transaction=page)
            if activation.error:
                raise Refused(activation.error)
            revision = activation.revision
            assert revision is not None
            url = "/"
        else:
            published = published_versions(page_dir, page.events)
            if not published:
                raise Refused(
                    f"{page_dir} has no stamped version to export; "
                    "use --draft for current source or run `leaf page stamp` first"
                )
            version = published[-1] if version is None else version
            if version not in published:
                raise Refused(
                    f"v{version} is not stamped — stamped: "
                    + ", ".join(f"v{v}" for v in published)
                )
            revision = version_revisions(page.events)[version]
            url = f"/versions/{version_name(version)}"
        document = read_revision(page_dir, revision).document
        if document.samples:
            raise Refused(
                "Live samples need a server, so a page that declares one "
                "cannot be exported."
            )
        artifact = executing(read_artifact(page_dir, revision))
        snapshot = capture_page_snapshot(
            page_dir,
            document,
            revision,
            url=url,
            artifact=artifact,
            transaction=page,
            process=False,
            log=_page_log(page.events),
            data=markup_data(page_dir, document, artifact.registry),
        )
    state = PageStateService(
        page_dir,
        source=snapshot,
    ).page_state(revision)
    html = export_document(
        artifact,
        document,
        state,
        revision,
        version,
        snapshot.data_resources,
    )
    if not runtime:
        html = static_document(html)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return {
        "file": str(out),
        "version": version,
        "revision": revision,
        "bytes": out.stat().st_size,
    }
