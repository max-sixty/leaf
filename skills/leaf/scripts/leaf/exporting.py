"""Standalone export of a fully rendered page."""

import base64
import re
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
from leaf.render_checks import (
    RENDER_VIEWPORT,
    evaluate_probe,
    wait_for_presentation,
    wait_for_probe,
)
from leaf.render_gate.browser import (
    EXPORT_FLOOR,
    below_export_floor,
    browser_hint,
    launch_browser,
)
from leaf.render_gate.preview import preview_server
from leaf.revision_artifact import RESOURCE_TYPES, Resource
from leaf.schema import DIR_FILES, MEDIA_DIR
from leaf.structure import UTF8_BOM, SourceDocument

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
        if reference.startswith(("#", "data:")):
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
            if element.tag == "link" and "stylesheet" in attrs.get("rel", []):
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
                elif (
                    name in {"src", "poster"}
                    and element.tag not in {"script", "iframe"}
                ) or (
                    name in {"href", "xlink:href"}
                    and (
                        element.tag in {"image", "use"}
                        or element.tag == "link"
                        and "icon" in attrs.get("rel", [])
                    )
                ):
                    replacement = assets.url(value, document_url, ())
                elif (
                    element.tag == "meta"
                    and name == "content"
                    and attrs.get("http-equiv", "").lower() == "content-security-policy"
                ):
                    replacement = _embedded_policy(value)
                else:
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


def export_page(browser, url: str, page_dir: Path, name: str) -> str:
    """The served document named by `name`, copied as one self-contained file.

    Callers own the browser lifetime: `version export` launches the host's browser,
    the site builder reuses one across its product documents, and the suite drives
    shipped examples with its Chromium headless shell. The rendering and bake remain
    one implementation without claiming those browser launch paths are identical.

    The user's decisions come with it. Replay is what puts them on the page, so
    this waits for the runtime's caught-up stamp exactly as the gate does, and a page
    whose board was rearranged copies rearranged.

    The browser's own age is read before the page is opened, because the bake this
    ends in needs one younger than some of the browsers a host can hand over, and
    the render gate — which never bakes — passes them. Refusing here says that in
    one sentence, where the alternative is a TypeError from inside the probe."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    if old := below_export_floor(browser):
        sys.exit(
            f"{name} needs Chromium {EXPORT_FLOOR} or later to copy, and this "
            f"browser is {old}. A copy is the drawn page, and the widgets draw "
            "into shadow roots this browser cannot serialize."
        )

    page = browser.new_page(viewport=RENDER_VIEWPORT)
    try:
        # See the gate: a page listening for news is never network-idle. The
        # stamps below are the arrival signal, and they are the precise one.
        page.goto(url, wait_until="load")
        try:
            wait_for_probe(page, "upgraded")
            # Read expectations through the same server the browser is applying. A
            # preview freezes that server at one PageSnapshot; rereading page files
            # here could otherwise wait for state the browser cannot receive.
            readiness = page.evaluate(
                """async () => {
                  const root = document.querySelector(
                    'link[rel="canonical"][data-lf-runtime]'
                  );
                  if (!root) throw new Error('document has no canonical page root');
                  const response = await fetch(new URL('api/state', root.href));
                  if (!response.ok)
                    throw new Error(`state returned ${response.status}`);
                  const state = await response.json();
                  return {
                    pageRoot: root.href,
                    theme: document.querySelector(
                      'link[rel="stylesheet"][data-lf-runtime]'
                    ).href,
                    dataRevision: state.data.revision,
                    replayedEvents: state.events.filter(
                      event => event.kind === 'action' || event.kind === 'report'
                    ).length,
                  };
                }"""
            )
            failed_stage = wait_for_presentation(
                page, readiness["dataRevision"], readiness["replayedEvents"]
            )
            if failed_stage:
                raise PlaywrightTimeout(f"presentation stopped at {failed_stage}")
            # A live fragmented widget deliberately keeps unopened payloads out of the
            # DOM. A standalone copy has no fragment door after scripts are removed, so
            # let any renderer that owns such payloads materialize them before baking.
            page.evaluate(
                """async () => {
                  const pending = [...document.querySelectorAll('*')]
                    .map((element) => element.lfPrepareExport?.())
                    .filter((result) => result?.then);
                  await Promise.all(pending);
                }"""
            )
            # Materializing a live fragment can mount required descendants or overlap a
            # newer semantic publication. Re-read the coordinator immediately before
            # baking rather than treating the initial arrival latch as permanent.
            wait_for_probe(page, "currentPresented")
            asset_root = readiness["theme"].removesuffix("theme.css")
            origin = urlsplit(asset_root)
            page_root = urlsplit(readiness["pageRoot"]).path

            def read_resource(resource_url: str) -> Resource:
                parsed = urlsplit(resource_url)
                if (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc):
                    raise ValueError(
                        f"export resource is outside the page: {resource_url}"
                    )
                path = parsed.path
                logical = path.removeprefix(page_root).lstrip("/")
                message_media = re.fullmatch(
                    rf"{MEDIA_DIR}/{DIR_FILES[MEDIA_DIR]}", logical
                )
                if not path.startswith(origin.path):
                    # Runtime-produced markup (including the bake's adopted sheets)
                    # can still name logical page routes. Read those only through
                    # the document's captured namespace, never the mutable alias.
                    # Media added by later conversation events is page-owned and
                    # content-addressed, not an input of the authored revision.
                    resource_url = urljoin(
                        readiness["pageRoot"] if message_media else asset_root,
                        logical,
                    )
                if not message_media and not urlsplit(resource_url).path.startswith(
                    origin.path
                ):
                    raise ValueError(
                        f"export resource escapes its revision: {resource_url}"
                    )
                response = page.request.get(resource_url, max_redirects=0)
                if not response.ok:
                    raise ValueError(
                        f"export resource returned {response.status}: {resource_url}"
                    )
                mime = response.headers["content-type"].split(";", 1)[0].strip()
                return Resource(response.body(), mime)

            return UTF8_BOM + inline_assets(
                evaluate_probe(page, "bake"),
                read_resource=read_resource,
                document_url=urljoin(asset_root, "index.html"),
            )
        except PlaywrightTimeout:
            sys.exit(
                f"{name} never finished applying its live state in "
                "the browser, so a copy would be half-drawn. `leaf version check "
                "<page> --render` says what is wrong with it."
            )
        except PlaywrightError as error:
            sys.exit(
                f"{name} could not read its browser state or probe module "
                f"({str(error).strip().splitlines()[0]}), so Leaf could not make a "
                "trustworthy copy."
            )
        except ValueError as error:
            sys.exit(f"{name} could not embed its captured assets: {error}")
    finally:
        page.close()


def cmd_export(page_dir: Path, out: Path, version) -> int:
    """One stamped version as a standalone HTML file.

    The copy is the page as the browser finished drawing it, which is the only way to
    get one: half the document is written by the widget layer at runtime, a diagram
    becomes an SVG only once its renderer has drawn it, and a code block is colored
    by the vendored tokenizer in the page rather than by anything that can read the
    file. So a browser is not an optimisation here and no `x-` key exempts a widget
    from it; without one there is nothing to copy at all."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

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

    with (
        preview_server(page_dir, document, revision, version=version) as url,
        sync_playwright() as p,
    ):
        try:
            browser, _ = launch_browser(p)
        except PlaywrightError as e:
            sys.exit(
                "export needs a browser, and none launched "
                f"({str(e).strip().splitlines()[0]}). A copy is the drawn page, so "
                f"there is nothing to write without one. {browser_hint()}"
            )
        try:
            html = export_page(browser, url, page_dir, name)
        finally:
            browser.close()

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"✓ {name} → {out} ({out.stat().st_size // 1024} KB, opens with no server)")
    return 0
