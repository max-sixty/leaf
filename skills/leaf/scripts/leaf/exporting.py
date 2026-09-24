"""A stamped version as one HTML file that opens offline.

The export packages the captured revision, its resources, and the page's authoritative
state reading into one file, and Leaf's normal runtime boots from them. There is no
second rendering: whatever the page draws when served, the file draws. Asset inlining
is shared with the MCP App resource, which embeds a page the same way.
"""

import base64
import re
import secrets
import sys
from collections.abc import Callable
from html import escape
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

import tinycss2
import turbohtml

from leaf.event_log import read_events
from leaf.files import (
    published_versions,
    revision_path,
    version_name,
    version_revisions,
)
from leaf.http import head_open_end_offset
from leaf.page_snapshot import capture_page_snapshot
from leaf.revision_artifact import (
    RESOURCE_TYPES,
    Resource,
    RevisionArtifact,
    read_artifact,
    resolve_dependency,
    rewrite_captured_module,
    rewrite_module,
)
from leaf.revision_delivery import delivery_prelude, delivery_sheets, json_script
from leaf.served_state.service import PageStateService
from leaf.structure import (
    EXTERNAL_SOURCES,
    UTF8_BOM,
    SourceDocument,
    external_reference,
    rel_tokens,
    rewrite_resource_attribute,
)

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
    """Embed a resource graph using its delivered URLs and MIME types.

    Imports remain CSS imports with embedded stylesheet URLs: their namespaces,
    cascade layers, supports clauses, and media conditions retain browser semantics.
    Each imported sheet resolves its own URLs before it is embedded. A cyclic import
    becomes an empty sheet, matching the browser's cycle suppression.
    """

    def __init__(self, read: ResourceReader):
        self.read = read
        self.resources: dict[str, Resource] = {}

    def resource(self, url: str) -> Resource:
        if url not in self.resources:
            self.resources[url] = self.read(url)
        return self.resources[url]

    def url(self, reference: str, base: str, ancestors: tuple[str, ...]) -> str:
        if reference.startswith(("#", "data:")) or external_reference(reference):
            return reference
        url, fragment = urldefrag(urljoin(base, reference))
        resource = self.resource(url)
        if resource.mime == "text/css":
            css = (
                ""
                if url in ancestors
                else self.css(resource.data.decode("utf-8"), url, (*ancestors, url))
            )
            resource = Resource(css.encode("utf-8"), "text/css")
        return _data_url(resource) + (f"#{fragment}" if fragment else "")

    def css(self, css: str, base: str, ancestors: tuple[str, ...] = ()) -> str:
        def rewrite(tokens):
            import_url = False
            for token in tokens:
                if token.type in {"whitespace", "comment"}:
                    continue
                if token.type == "at-keyword" and token.lower_value == "import":
                    import_url = True
                    continue
                if import_url and token.type == "string":
                    value = self.url(token.value, base, ancestors)
                    if value != token.value:
                        token.value = value
                        token.representation = f'"{value}"'
                elif token.type == "url":
                    value = self.url(token.value, base, ancestors)
                    if value != token.value:
                        token.value = value
                        token.representation = f'url("{value}")'
                elif token.type == "function" and token.lower_name == "url":
                    args = [
                        arg
                        for arg in token.arguments
                        if arg.type not in {"whitespace", "comment"}
                    ]
                    if len(args) == 1 and args[0].type == "string":
                        value = self.url(args[0].value, base, ancestors)
                        if value != args[0].value:
                            token.arguments = tinycss2.parse_component_value_list(
                                f'"{value}"'
                            )
                else:
                    for name in ("content", "arguments"):
                        if (children := getattr(token, name, None)) is not None:
                            rewrite(children)
                import_url = False

        tokens = tinycss2.parse_component_value_list(css)
        rewrite(tokens)
        return tinycss2.serialize(tokens)


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


def _embedded_policy(policy: str) -> str:
    """Permit embedded asset bytes without relaxing navigation or script policy."""
    directives = {
        parts[0]: parts[1:]
        for directive in policy.split(";")
        if (parts := directive.split())
    }
    for name in ("style-src", "style-src-elem", "font-src", "media-src"):
        fallback = "style-src" if name == "style-src-elem" else "default-src"
        sources = directives.setdefault(name, list(directives.get(fallback, [])))
        if "data:" not in sources:
            sources.append("data:")
    return "; ".join(" ".join([name, *sources]) for name, sources in directives.items())


def inline_assets(
    html: str,
    page_dir: Path | None = None,
    *,
    read_resource: ResourceReader | None = None,
    document_url: str = "/index.html",
) -> str:
    """Embed styles and media without changing prose or serialized shadow roots.

    Resource readers own the authority boundary. Export supplies its immutable HTTP
    namespace; a non-browser projection can supply the artifact's captured resources.
    HTML source locations keep unrelated markup, including foreign SVG, byte-for-byte.
    """
    if read_resource is None:
        assert page_dir is not None
        read_resource = _file_reader(page_dir)
    assets = _AssetInliner(read_resource)
    roots = [turbohtml.parse(html, source_locations=True)]
    edits = []
    for root in roots:
        for element in root.find_all(True):
            if element.shadow_root is not None:
                roots.append(element.shadow_root)
            location = element.source_location
            if location is None:
                continue
            attrs = element.attrs
            if (
                element.tag == "link"
                and "stylesheet" in rel_tokens(attrs)
                and not external_reference(attrs["href"])
            ):
                url = urljoin(document_url, attrs["href"])
                resource = assets.resource(url)
                if resource.mime != "text/css":
                    raise ValueError(
                        f"export stylesheet has MIME {resource.mime}: {url}"
                    )
                css = assets.css(resource.data.decode("utf-8"), url, (url,))
                css = re.sub(r"</style", r"<\\/style", css, flags=re.IGNORECASE)
                kept = {
                    key: value
                    for key, value in attrs.items()
                    if key in {"media", "title", "data-lf-runtime", "disabled"}
                }
                style_attrs = "".join(
                    f' {key}="{escape(value, quote=True)}"'
                    for key, value in kept.items()
                )
                edits.append(
                    (
                        location.start_tag.start_offset,
                        location.start_tag.end_offset,
                        f"<style{style_attrs}>{css}</style>",
                    )
                )
                continue
            if element.tag == "style" and location.end_tag is not None:
                start, end = (
                    location.start_tag.end_offset,
                    location.end_tag.start_offset,
                )
                edits.append((start, end, assets.css(html[start:end], document_url)))
            for name, value in attrs.items():
                if name == "style":
                    replacement = assets.css(value, document_url)
                else:
                    replacement = rewrite_resource_attribute(
                        element.tag,
                        attrs,
                        name,
                        value,
                        lambda reference: assets.url(reference, document_url, ()),
                    )
                if (
                    element.tag == "meta"
                    and name == "content"
                    and attrs.get("http-equiv", "").lower() == "content-security-policy"
                ):
                    replacement = _embedded_policy(value)
                elif replacement == value and name != "style":
                    continue
                if replacement != value:
                    span = location.attrs[name.lower()]
                    edits.append(
                        (
                            span.start_offset,
                            span.end_offset,
                            f'{name}="{escape(replacement, quote=True)}"',
                        )
                    )
    for start, end, replacement in sorted(edits, reverse=True):
        html = html[:start] + replacement + html[end:]
    return html


def _interactive_module_urls(artifact: RevisionArtifact) -> dict[str, str]:
    urls = {}
    for path, resource in artifact.resources.items():
        if resource.mime == "application/javascript":
            source = rewrite_captured_module(
                resource.data, path, "leaf:", artifact.resources
            )
            urls[path] = _data_url(Resource(source, resource.mime))
    for tag, implementation in artifact.implementations.items():
        urls[f"/widgets/{tag}.js"] = urls[implementation["path"]]
    return urls


def _bind_authored_modules(html: str, module_urls: dict[str, str], nonce: str) -> str:
    """Address captured authored modules from a self-contained file.

    Each one is also marked with the file's script nonce, which is what separates the
    blocks this export composed from markup a later user's inputs write into it.
    """
    root = turbohtml.parse(html, source_locations=True)
    edits = []
    for element in root.find_all("script"):
        location = element.source_location
        if location is None or element.attrs.get("type") != "module":
            continue
        edits.append(
            (
                location.start_tag.end_offset - 1,
                location.start_tag.end_offset - 1,
                f' nonce="{nonce}"',
            )
        )
        if source := element.attrs.get("src"):
            logical = resolve_dependency(source, "/index.html", module=True)
            if logical is None:
                continue  # an external module keeps its address
            span = location.attrs["src"]
            edits.append(
                (
                    span.start_offset,
                    span.end_offset,
                    f'src="{escape(module_urls[logical], quote=True)}"',
                )
            )
        elif location.end_tag is not None:
            start = location.start_tag.end_offset
            end = location.end_tag.start_offset
            body = rewrite_module(
                html[start:end].encode(), "/index.html", "leaf:"
            ).decode()
            edits.append((start, end, body))
    for start, end, replacement in sorted(edits, reverse=True):
        html = html[:start] + replacement + html[end:]
    return html


def export_document(
    artifact: RevisionArtifact,
    state: dict,
    data: dict,
    revision: int,
    version: int,
) -> str:
    """Package one captured revision for Leaf's normal runtime without a host.

    The import map is an address table, not another runtime: every module is the exact
    captured module with only its parsed local imports rebound to an in-file ``data:``
    URL. The normal application publisher, widgets, and presentation coordinator boot
    against the embedded authoritative reading. CSP admits embedded bytes and the
    external origins a page may name, so the file reaches no other network and opens
    offline wherever the page itself loads nothing from a CDN.
    """
    if SourceDocument(artifact.html.decode("utf-8")).specimens:
        sys.exit(
            "Live specimens need a server, so a page that declares one "
            "cannot be exported."
        )
    modules = _interactive_module_urls(artifact)
    html = inline_assets(
        artifact.html.decode("utf-8"),
        read_resource=artifact.resources.__getitem__,
        document_url="/index.html",
    )
    nonce = secrets.token_urlsafe(16)
    html = _bind_authored_modules(html, modules, nonce)
    embedded_resources = {
        path: _data_url(resource)
        for path, resource in artifact.resources.items()
        if resource.mime not in {"application/javascript", "text/css"}
    }
    inliner = _AssetInliner(artifact.resources.__getitem__)

    def sheet(path: str) -> str:
        return inliner.css(artifact.resources[path].data.decode("utf-8"), path, (path,))

    theme = sheet("/theme.css")
    embedded_resources["/shadow.css"] = _data_url(
        Resource(sheet("/shadow.css").encode(), "text/css")
    )
    embedded_resources["/registry.json"] = _data_url(
        artifact.resources["/registry.json"]
    )
    import_map = json_script(
        {"imports": {f"leaf:{path}": url for path, url in sorted(modules.items())}}
    )
    payload = json_script(
        {"state": state, "data": data, "resources": embedded_resources}
    )
    policy = (
        "default-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'; "
        f"connect-src data: {EXTERNAL_SOURCES}; img-src data: {EXTERNAL_SOURCES}; "
        f"media-src data: {EXTERNAL_SOURCES}; font-src data: {EXTERNAL_SOURCES}; "
        f"style-src 'unsafe-inline' data: {EXTERNAL_SOURCES}; "
        f"script-src data: 'nonce-{nonce}' {EXTERNAL_SOURCES}"
    )
    escaped_theme = re.sub(r"</style", r"<\/style", theme, flags=re.IGNORECASE)
    document = SourceDocument(html)
    runtime_head = (
        delivery_prelude(
            document, revision, version, artifact.executable, artifact.widgets
        )
        + f'<meta http-equiv="Content-Security-Policy" content="{escape(policy, quote=True)}">'
        f'<script type="importmap" nonce="{nonce}">{import_map}</script>'
        '<script type="application/json" data-lf-runtime data-lf-offline '
        'data-lf-page-root="" data-lf-entry="leaf:/leaf.js" data-lf-probe="">'
        f"{payload}</script>"
        + delivery_sheets(
            artifact.resources, lambda css, path: inliner.css(css, path, (path,))
        )
        + f"<style data-lf-runtime>{escaped_theme}</style>"
        f'<script type="module" src="{escape(modules["/leaf.js"], quote=True)}" '
        "data-lf-runtime></script>"
    )
    offset = head_open_end_offset(document)
    return UTF8_BOM + html[:offset] + runtime_head + html[offset:]


def cmd_export(page_dir: Path, out: Path, version) -> int:
    """One stamped version as a standalone HTML file that opens offline.

    The file carries the captured revision and Leaf's normal runtime, which boots from
    the embedded authoritative reading. It has no host command or transport capability."""
    events = read_events(page_dir)
    published = published_versions(page_dir, events)
    if not published:
        sys.exit(
            f"{page_dir} has no stamped version to export; "
            "run `leaf version stamp` first"
        )
    version = version if version else published[-1]
    if version not in published:
        sys.exit(
            f"v{version} is not stamped — stamped: "
            + ", ".join(f"v{v}" for v in published)
        )
    name = version_name(version)
    revision = version_revisions(events)[version]
    document = SourceDocument(
        revision_path(page_dir, revision).read_text(encoding="utf-8")
    )
    artifact = read_artifact(page_dir, revision)
    active = {"revision": revision, "version": version, "url": f"/versions/{name}"}
    snapshot = capture_page_snapshot(page_dir, document, active, artifact=artifact)
    state = PageStateService(
        page_dir,
        page_snapshot=snapshot,
        layer_identity=snapshot.layer,
    ).page_state(revision)
    html = export_document(artifact, state, snapshot.data, revision, version)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"✓ {name} → {out} ({out.stat().st_size // 1024} KB, opens with no server)")
    return 0
