"""Deliver a revision's documents and resources for the host serving them.

A document and the resources it names use logical page paths: `/page/…` for the
author's files, `/media/…` for the page's images, and the layer's own files at the
root (`/icon.svg`, `/runtime/…`). The resources are the revision's capture with the
delivering Leaf's runtime beside it (`runtime_selection.executing`), which every
caller here is handed. Every host delivers the same bytes under an address of its
own — an HTTP server beneath a revision's URL, a published site beneath
a release, an offline export through document-lifetime object URLs — so each host
passes one
`address` function, from a logical path to the URL it serves that path at, and the
walks below apply it. HTML source spans preserve prose and unrelated attributes,
JavaScript rewriting names only parsed imports, and CSS rewriting names only the URLs
`rewrite_css` reads. Nothing reads a document or a resource as text.

Over HTTP, media is the page's and everything else a document names is its revision's
(`DeliveryAddress`). `media/` holds content-addressed images shared across revisions;
the page root serves them in every host, and the runtime resolves the media a message
or a widget names against that same root (`runtime/media.js`). The layer's own module
graph imports rooted paths (`/runtime/…`, `/vendor/…`, `/widgets/…`), which the
document's import map sends to where its revision's resources answer
(`layer_import_map`), so layer modules are served as they are held.

A document is delivered once, by `compose_document`, whoever delivers it: the HTTP
server and the static live shell, and a standalone export. A
host states what it adds as a `Delivery` value, and the composer writes every document
the same way. It also paints what each element's registry entry declares, and the size
of the page media it names, for the stylesheet to read (`mark_declared`), so the first
paint lays out what a script would otherwise only mark once the registry loads or an
image once it decodes.
"""

import html
import json
import re
import struct
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from urllib.parse import quote, unquote, urlsplit

import turbohtml

from .layer import CASCADE_LAYERS
from .passages import markdown_markup
from .registry.contract import exhibits, is_element_name
from .registry.kernel import kernel_marks
from .revision_artifact import (
    Resource,
    RevisionArtifact,
    authored_imports,
    bind_imports,
    dependency_reference,
    rewrite_css,
)
from .schema import (
    BROWSER_DIRS,
    LAYER_TOP_FILES,
    MEDIA_DIR,
    RENDER_CHECKS_DIR,
)
from .structure import (
    UTF8_BOM,
    SourceDocument,
    annotation_mode,
    element_attrs,
    page_layout,
    rel_tokens,
    rewrite_attribute_references,
    script_kind,
    source_index,
)

# From a page-local URL (path and suffix) to its delivery URL, or None if unavailable.
Address = Callable[[str], str | None]

# The paths of a page's namespace a document or resource may name: the author's files,
# the page's media, and the layer. The API and the page's documents are the runtime's
# and the server's to address, never an authored reference's.
_PAGE_PATH = re.compile(
    "/(?:"
    + "|".join(
        [f"(?:page|{MEDIA_DIR}|{'|'.join(BROWSER_DIRS)})/.+"]
        + [re.escape(name) for name in LAYER_TOP_FILES]
    )
    + ")"
)


def page_path(reference: str, base: str) -> tuple[str, str] | None:
    """The logical page path `reference` names from `base`, and the suffix it keeps.

    None for a reference that does not name the page: one to another origin, a
    `data:` URL, a fragment of this document, or a path outside the page's namespace.
    The suffix is the query and fragment, which travel with the path to its address.
    """
    if not reference:
        return None
    reference = dependency_reference(reference, base)
    if reference is None or not _PAGE_PATH.fullmatch(reference[0]):
        return None
    return reference


def _attributes(attributes: Mapping[str, str | bool | None]) -> str:
    """Attributes to write in a start tag, each value escaped: `True` writes the name
    alone, and `None` leaves the attribute out."""
    return "".join(
        f" {name}" if value is True else f' {name}="{html.escape(value, quote=True)}"'
        for name, value in attributes.items()
        if value is not None
    )


def _raw_text(tag: str, text: str) -> str:
    """`text` to write inside a `tag` element whose content the parser reads raw, a
    script or a style, where `</tag` would otherwise end the element."""
    return re.sub(rf"</{tag}", rf"<\\/{tag}", text, flags=re.IGNORECASE)


def runtime_element(
    tag: str, attributes: Mapping[str, str | bool | None], body: str = ""
) -> str:
    """An element a host adds to a document it delivers, marked `data-lf-runtime` as
    delivery's own: the runtime reads past it as no part of the author's page, and a
    revision arriving at an open document brings the author's head across without it.
    Attribute values are escaped (`_attributes`), and a script's or style's `body`
    cannot end its element early (`_raw_text`); a JSON body comes from `json_script`,
    which also keeps a comment opener out. A `meta` or `link` is void and takes none.
    """
    opening = f"<{tag}{_attributes({**attributes, 'data-lf-runtime': True})}>"
    if tag in {"meta", "link"}:
        return opening
    return f"{opening}{_raw_text(tag, body)}</{tag}>"


def runtime_settings(
    body: str,
    *,
    layer: str,
    page_root: str,
    entry: str,
    probe: str,
    declared: Mapping[str, str | bool | None],
) -> str:
    """The script that says how a host delivered a document (`runtime/context.js`):
    the layer generation it belongs to, its page root, the runtime entry, which is
    the seam a harness finds either delivery by, and the registry probe, beside what
    the host `declared` of its own. A served document's runs `bootstrap.js`; an
    export's holds its payload as JSON (`data-lf-offline`)."""
    return runtime_element(
        "script",
        {
            **declared,
            "data-lf-layer": layer,
            "data-lf-page-root": page_root,
            "data-lf-entry": entry,
            "data-lf-probe": probe,
        },
        body,
    )


def _rebase(reference: str, base: str, address: Address) -> str:
    located = page_path(reference, base)
    if located is None:
        return reference
    path, suffix = located
    return address(quote(path, safe="/") + suffix)


def rebase_css(
    source: str, base: str, address: Address, *, declarations: bool = False
) -> str:
    """Re-address every URL a stylesheet at `base` loads, the rest byte-for-byte.

    Cheap for a sheet read before at any address: `rewrite_css` keeps each sheet's
    parse by its text.
    """
    return rewrite_css(
        source,
        lambda reference: _rebase(reference, base, address),
        declarations=declarations,
    )


def rebase_module(data: bytes, base: str, address: Address) -> bytes:
    """Re-address every literal import of an authored module at `base`."""
    return bind_imports(
        data, authored_imports(data, base), lambda path: address(quote(path, safe="/"))
    )


def rebase_document(
    source: str,
    address: Address,
    *,
    inline_stylesheet: Callable[[str], str] | None = None,
) -> str:
    """Re-address every reference an HTML document makes, and nothing else in it.

    An unavailable address removes the attribute; unavailable executable delivery
    removes script elements. CSS omits only declarations that load unavailable assets.
    The references are an authored script's `src` and its literal imports, a
    stylesheet link, every URL `attribute_references` reads, and the URLs of each
    `style` element and attribute — in the document and in each declarative shadow
    root it serializes. Authored prose is also the anchorable record, so a
    route-looking phrase in text stays byte-for-byte what the revision holds.

    `inline_stylesheet`, for a host that embeds its stylesheets, takes a linked
    stylesheet's logical path and returns its CSS, which replaces the link as a
    `style` element keeping the link's media, title, and runtime mark.
    """
    tree = turbohtml.parse(source, scripting=True, source_locations=True)
    index = source_index(source)
    edits = []

    def span(location) -> tuple[int, int]:
        return (
            index(location.start_line, location.start_col),
            index(location.end_line, location.end_col),
        )

    def rebase(reference: str) -> str:
        return _rebase(reference, "/index.html", address)

    roots = [tree]
    for root in roots:
        for element in root.find_all(True):
            if element.shadow_root is not None:
                roots.append(element.shadow_root)
            location = element.source_location
            if location is None:
                continue
            attrs = element_attrs(element)
            tag = element.tag
            if tag == "script" and address("/leaf.js") is None:
                start = span(location.start_tag)[0]
                end = span(location.end_tag or location.start_tag)[1]
                edits.append((start, end, ""))
                continue
            stylesheet = tag == "link" and "stylesheet" in rel_tokens(attrs)
            if (
                stylesheet
                and inline_stylesheet is not None
                and (located := page_path(attrs.get("href", ""), "/index.html"))
            ):
                # Preserve stylesheet declarations, such as its media and data attributes;
                # only the linked resource's address and fetch mechanism disappear.
                kept = _attributes(
                    {
                        name: value
                        for name, value in attrs.items()
                        if name not in {"rel", "href", "crossorigin", "integrity"}
                    }
                )
                css = _raw_text("style", inline_stylesheet(located[0]))
                start, end = span(location.start_tag)
                edits.append((start, end, f"<style{kept}>{css}</style>"))
                continue
            # An opaque sample shares this native delivery. CORS keeps its local
            # sheets readable by the CSSOM owners; a no-CORS link would paint but
            # deny Leaf's layout readings. Same-origin pages
            # retain their ordinary credentials, and external authored links stand.
            if (
                stylesheet
                and "crossorigin" not in attrs
                and page_path(attrs.get("href", ""), "/index.html") is not None
            ):
                _, end = span(location.start_tag)
                at = end - (2 if source[end - 2 : end] == "/>" else 1)
                edits.append((at, at, ' crossorigin="anonymous"'))
            for name, value in attrs.items():
                if name == "style":
                    delivered = rebase_css(
                        value, "/index.html", address, declarations=True
                    )
                elif (tag == "script" and name == "src") or (
                    stylesheet and name == "href"
                ):
                    delivered = rebase(value)
                else:
                    delivered = rewrite_attribute_references(
                        tag, attrs, name, value, rebase
                    )
                if delivered != value:
                    start, end = span(location.attrs[name])
                    edits.append(
                        (
                            start,
                            end,
                            f'{name}="{html.escape(delivered, quote=True)}"'
                            if delivered is not None
                            else "",
                        )
                    )
            # Delivery's own scripts (`runtime_element`) run where they stand.
            authored = "data-lf-runtime" not in attrs
            if (
                authored
                and tag == "script"
                and script_kind(attrs) in {"module", "classic"}
            ):
                edits.extend(_deferred(source, span, location, attrs))
            if tag in {"script", "style"} and location.end_tag is not None:
                start = index(location.start_tag.end_line, location.start_tag.end_col)
                end = index(location.end_tag.start_line, location.end_tag.start_col)
                body = source[start:end]
                if tag == "style":
                    delivered = rebase_css(body, "/index.html", address)
                elif script_kind(attrs) in {"module", "classic"} and not attrs.get(
                    "src"
                ):
                    delivered = rebase_module(
                        body.encode("utf-8"), "/index.html", address
                    ).decode("utf-8")
                    if authored and script_kind(attrs) == "classic":
                        # An inline classic script runs from a deferred `data:` file,
                        # which keeps its global scope and sloppy mode. Its lines are
                        # padded to where it stands, and `sourceURL` names the
                        # document, so an error it throws names its line in index.html.
                        line = location.start_tag.end_line
                        text = "\n" * (line - 1) + delivered
                        text += "\n//# sourceURL=index.html"
                        url = "data:text/javascript;charset=utf-8," + quote(
                            text, safe=""
                        )
                        _, tag_end = span(location.start_tag)
                        edits.append((tag_end - 1, tag_end - 1, f' src="{url}"'))
                        delivered = ""
                else:
                    continue
                if delivered != body:
                    edits.append((start, end, delivered))

    return _spliced(source, edits)


def _deferred(source: str, span, location, attrs: dict) -> list[tuple[int, int, str]]:
    """Edits that hold a page's script until the runtime has read the page.

    The runtime's module runs once the document has parsed, and so does every deferred
    script after it, in document order. A classic script the parser would run where it
    stands, or one marked `async`, could run first, changing what the runtime reads
    as authored and throwing before anything listens. So delivery defers it: `async`
    goes, and a classic script gains `defer`, an inline one by moving its text to a
    `data:` file (`rebase_document`). What it gives up is running mid-parse, which
    leaves `document.write` ignored."""
    edits = []
    if "async" in attrs:
        edits.append((*span(location.attrs["async"]), ""))
    if script_kind(attrs) == "classic" and "defer" not in attrs:
        _, end = span(location.start_tag)
        at = end - (2 if source[end - 2 : end] == "/>" else 1)
        edits.append((at, at, " defer"))
    return edits


def _spliced(source: str, edits: list[tuple[int, int, str]]) -> str:
    """`source` with each `(start, end, text)` edit's range replaced by its text.

    The ranges must not overlap. Edits at one offset land in the order their texts
    sort. Joining the pieces once keeps delivery linear in the page's size, where
    splicing each of a large page's thousands of marks into a fresh copy was not."""
    pieces = []
    at = 0
    for start, end, text in sorted(edits):
        pieces += (source[at:start], text)
        at = end
    pieces.append(source[at:])
    return "".join(pieces)


def media_size(data: bytes) -> tuple[int, int] | None:
    """The width and height an image states in its header, for the raster formats page
    media holds (`schema.MEDIA_TYPES`), or None where the bytes state none: an SVG, whose
    size is its layout's, or a file cut short. A JPEG's EXIF rotation is not applied."""
    if (
        len(data) >= 24
        and data.startswith(b"\x89PNG\r\n\x1a\n")
        and data[12:16] == b"IHDR"
    ):
        return struct.unpack(">II", data[16:24])
    if data.startswith((b"GIF87a", b"GIF89a")) and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8 ":
            width, height = struct.unpack("<HH", data[26:30])
            return width & 0x3FFF, height & 0x3FFF
        if chunk == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if chunk == b"VP8X":
            return (
                int.from_bytes(data[24:27], "little") + 1,
                int.from_bytes(data[27:30], "little") + 1,
            )
        return None
    if data.startswith(b"\xff\xd8"):
        at = 2
        while at + 9 <= len(data) and data[at] == 0xFF:
            marker = data[at + 1]
            (length,) = struct.unpack(">H", data[at + 2 : at + 4])
            # Every start-of-frame marker but the three that share its range.
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack(">HH", data[at + 5 : at + 9])
                return width, height
            at += 2 + length
    return None


_ARRIVING_MARK = " data-lf-arriving"


def mark_declared(
    source: str,
    registry: Mapping,
    resources: Mapping[str, Resource],
    *,
    initial: bool = False,
) -> str:
    """Paint each element's declared marks (`registry.kernel.kernel_marks`) onto its
    start tag, the rest byte-for-byte, and the size of the page media it names. With
    `initial`, an `x-initial` host is marked `data-lf-arriving`, which the theme hides
    while the runtime will run, and a parser invocation follows its end tag. The script
    takes the mark off and draws the complete host in one synchronous turn; nested
    initial hosts share the outer mark and draw deepest-first.

    The script removes itself as it runs, so the host keeps its authored siblings, and
    a rule for the first or last child still finds it. With scripts disabled, or in a
    DOMParser source reading, the mark hides nothing (`html[data-lf-interactive]`)
    and the raw authored host stays readable. A template opened by `document.write`
    once held the arriving source instead; Firefox reparses the rest of the document
    after any unbalanced write, and says so in the console of every such page.

    A mark painted by the runtime would land a registry fetch after the document first
    draws, so a workspace would draw its panes before knowing they are panes. An image
    has no size until it decodes, so an element naming page media in its attributes is
    painted with the box that holds any of them, the largest width and the largest
    height (`data-lf-media-width`, `data-lf-media-height`), for the stylesheet to lay
    out a frame that the images arrive in. What a template holds is inert until a
    module clones it, and a declarative shadow tree's content is its host's to style, so
    neither is marked.

    A mark is declared by the element's tag, so a selector idiom declares none.
    """
    tree = turbohtml.parse(source, scripting=True, source_locations=True)
    index = source_index(source)
    edits = []
    for element in tree.find_all(True):
        location = element.source_location
        if location is None or element.closest("template") is not None:
            continue
        declaration = (
            registry.get(element.tag, {}) if is_element_name(element.tag) else {}
        )
        attrs = element_attrs(element)
        content = element.tag not in {"html", "body", "main"} and (
            element.closest("main") is not None
        )
        marks = {}
        for key, mark in kernel_marks().items():
            declared = (
                exhibits(attrs, declaration)
                if key == "x-exhibit"
                else declaration.get(key)
            )
            means = {"content": content, "declared": bool(declared)}
            authored = mark.get("authored")
            if authored in attrs and means[mark["authored_on"]]:
                value = attrs[authored]
            elif declared:
                value = (
                    "" if declared is True or mark.get("presence") else str(declared)
                )
            else:
                continue
            marks[mark["paint"]] = value
        sizes = [
            size
            for value in attrs.values()
            if value
            and value.startswith(f"/{MEDIA_DIR}/")
            and (media := resources.get(urlsplit(value).path)) is not None
            and media.mime.startswith("image/")
            and (size := media_size(media.data)) is not None
        ]
        if sizes:
            marks["data-lf-media-width"] = str(max(width for width, _ in sizes))
            marks["data-lf-media-height"] = str(max(height for _, height in sizes))
        if marks:
            start = index(location.start_tag.start_line, location.start_tag.start_col)
            edits.append((start + 1 + len(element.tag), _attributes(marks)))
        if registry.get(element.tag, {}).get("x-text-format") == "markdown":
            pre = element.select_one(":scope > pre")
            if pre is not None:
                body = "".join(
                    child.data
                    for child in pre.children
                    if isinstance(child, turbohtml.Text)
                )
                text = body
                edits.append(
                    (
                        index(location.start_tag.end_line, location.start_tag.end_col),
                        (
                            '<div class="lf-markdown-body" data-lf-prepaint data-lf-gen="1" '
                            f'data-lf-source-words="{html.escape(text, quote=True)}">'
                            f"{markdown_markup(text)}</div>"
                        ),
                    )
                )
        if (
            initial
            and registry.get(element.tag, {}).get("x-initial")
            and not any(
                registry.get(getattr(parent, "tag", ""), {}).get("x-initial")
                for parent in element.ancestors
            )
        ):
            if location.end_tag is None:
                raise ValueError(
                    f"<{element.tag}> initial rendering needs a closing tag"
                )
            start = index(location.start_tag.start_line, location.start_tag.start_col)
            end = index(location.end_tag.end_line, location.end_tag.end_col)
            edits.append((start + 1 + len(element.tag), _ARRIVING_MARK))
            edits.append(
                (
                    end,
                    runtime_element(
                        "script",
                        {"data-lf-initial": True},
                        "document.documentElement.lfInitial.mount("
                        "document.currentScript.previousElementSibling);"
                        "document.currentScript.remove();",
                    ),
                )
            )
    return _spliced(source, [(offset, offset, text) for offset, text in edits])


def initial_script_paths(source: str, registry: Mapping) -> list[str]:
    """Shared Lit followed by the used classic producers, before parsing their hosts.

    Every producer can return a Lit view, including a page-owned classic script with
    no build step. Delivery owns that prerequisite; producer imports are irrelevant.
    A producer inside a template does not run during parsing.
    """
    tree = turbohtml.parse(source, scripting=True)
    used = dict.fromkeys(
        path
        for element in tree.find_all(True)
        if element.closest("template") is None
        and (path := registry.get(element.tag, {}).get("x-initial"))
    )
    return ["/vendor/lit-initial.js", *used] if used else []


def initial_scripts(paths: list[str], resources: Mapping[str, Resource]) -> str:
    """Inline captured producers and their prerequisites before the body parses."""
    return "".join(
        runtime_element("script", {}, resources[path].data.decode()) for path in paths
    )


@dataclass(frozen=True)
class DeliveryAddress:
    """Where an HTTP host serves each logical path of one revision's document.

    Media is the page's own and answers at the page root. Every other path is the
    revision's and answers beneath `asset_root`, where its capture is served.
    """

    page_root: str
    asset_root: str

    def __call__(self, path: str) -> str:
        located = urlsplit(path)
        root = (
            self.page_root
            if located.path.startswith(f"/{MEDIA_DIR}/")
            else self.asset_root
        )
        suffix = ("?" + located.query if located.query else "") + (
            "#" + located.fragment if located.fragment else ""
        )
        return root.rstrip("/") + quote(unquote(located.path), safe="/") + suffix


def layer_import_map(asset_root: str) -> dict:
    """Send the layer's rooted module imports to the revision serving them.

    Every layer module names its dependencies by rooted path, as the layer lays them
    out. The map rebinds each directory for the whole document, so a module keeps its
    bytes wherever the revision is served, and a page module or a render probe
    importing `/runtime/widget-api.js` reaches the runtime's own instance.
    """
    root = asset_root.rstrip("/")
    # Server-owned passive checks must read this document's runtime instance too,
    # and are served beside it.
    return {
        "imports": {
            f"/{name}/": f"{root}/{name}/"
            for name in (*BROWSER_DIRS, RENDER_CHECKS_DIR)
        }
    }


def deliver_resource(
    resource: Resource, logical_path: str, address: Address
) -> Resource:
    """Address one captured resource, including a page widget served under an alias.

    A stylesheet's URLs and an authored module's imports are re-addressed; a layer
    module keeps its bytes, since the import map addresses its imports. A page widget
    served through ``widgets/<tag>.js`` must pass its manifest path here
    (``/page/widgets/<tag>.js``), which is the base of its authored imports.
    """
    if resource.mime == "application/javascript" and logical_path.startswith("/page/"):
        return Resource(
            rebase_module(resource.data, logical_path, address), resource.mime
        )
    if resource.mime == "text/css":
        return Resource(
            rebase_css(resource.data.decode("utf-8"), logical_path, address).encode(
                "utf-8"
            ),
            resource.mime,
        )
    return resource


def delivered_resource(
    artifact: RevisionArtifact, logical_path: str, address: Address
) -> Resource | None:
    """One resource as an HTTP or static host serves it, including widget aliases.

    Aliases re-export the addressed captured implementation rather than copying
    its module: loading either path then shares one module instance. Ordinary
    resources are rebased against their own captured path, and a missing path
    remains absent for the transport to report.
    """
    source = artifact.widget_aliases.get(logical_path, logical_path)
    if source != logical_path:
        return Resource(
            f"export * from {json.dumps(address(source))};\n".encode(),
            "application/javascript",
        )
    resource = artifact.resources.get(source)
    if resource is None:
        return None
    return deliver_resource(resource, source, address)


def delivery_identity(
    revision: int, version: int | None, executable: str, widgets: dict
) -> str:
    """State which revision a delivered document is, and what it is made of.

    A later revision reaches an open document as a state reading, and two questions
    decide what the user gets. The executable digest says whether this document can
    take that revision on at all: a running document evaluates a module graph once and
    defines an element once, so new bytes behind either need a fresh one. The widget
    digests then say which widgets the user keeps, one per declared widget — by id,
    or by tag and place among the unnamed of that tag — over the markup its author
    wrote. Both travel in the head, where a document knows its own
    answer without asking, and where the revision document a patch already fetches
    carries the other one for free.

    Every delivered document carries this (`compose_document`). A document that says
    part of it is a document the next reader of the contract has to guess about.
    """
    named = {
        "lf-revision": str(revision),
        "lf-executable": executable,
        "lf-widgets": json.dumps(widgets, separators=(",", ":")),
        **({"lf-version": str(version)} if version is not None else {}),
    }
    return "".join(
        runtime_element("meta", {"name": name, "content": content})
        for name, content in named.items()
    )


def json_script(value) -> str:
    """Serialize inert JSON that cannot end or reshape the script element holding it.

    `</script` ends the element and `<!--` opens a comment the parser then reads the
    rest of the document inside, so no `<` survives: escaped, it is the same JSON and
    the same string once parsed.
    """
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    )


def delivery_sheets(
    resources: Mapping[str, Resource], address: Address, document: SourceDocument
) -> str:
    """Carry the selected layer's adopted sheets, with their own text and addressed URLs.

    `runtime/stylesheets.js` constructs these synchronously while it evaluates, so
    every document running the layer carries their text without a request or await.
    Shared chrome and marks are always present; physical annotation sheets are absent
    in page mode. The browser constructs only the sheets this carrier actually holds.
    """
    sheets = {
        name: rebase_css(resources[path].data.decode("utf-8"), path, address)
        for name, path in (
            ("chrome", "/runtime/chrome.css"),
            ("marks", "/runtime/marks.css"),
        )
    }
    if annotation_mode(document) == "overlay":
        sheets["annotations"] = {
            name: rebase_css(resources[path].data.decode("utf-8"), path, address)
            for name, path in (
                ("chrome", "/runtime/annotation-overlay/annotation-chrome.css"),
                ("marks", "/runtime/annotation-overlay/annotation-marks.css"),
            )
        }
    return runtime_element(
        "script",
        {"type": "application/json", "data-lf-sheets": True},
        json_script(sheets),
    )


def delivery_prelude(
    document: SourceDocument,
    revision: int,
    version: int | None,
    executable: str,
    widgets: dict,
) -> str:
    """Declare encoding, a device-width viewport, and immutable Leaf identity.

    Authors can supply their own viewport. Otherwise every delivery starts at the
    device width, so a phone uses responsive layout instead of a scaled desktop page.
    Edge-to-edge layout lets the chrome use the device's safe-area insets.
    """
    viewport = (
        ""
        if any(
            meta["name"].lower() == "viewport"
            for meta in document.authoring.named_metas
        )
        else '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
    )
    return (
        runtime_element("meta", {"charset": "utf-8"})
        + delivery_identity(revision, version, executable, widgets)
        + viewport
    )


@dataclass(frozen=True)
class Delivery:
    """What one host writes into the documents it delivers.

    Every host delivers a document the same way (`compose_document`), and these fields
    are the whole of what hosts differ in: where the document's references go, whether
    its stylesheets are embedded, the runtime script a served or exported page starts
    under, and the marks a host puts on the document around its source.
    """

    address: Address
    # Embeds stylesheets in place of linking them: a stylesheet's CSS by its path.
    inline_stylesheet: Callable[[str], str] | None = None
    import_map: dict | None = None
    # The runtime's own inline script. A document with one runs the layer, so it also
    # carries the layer's adopted sheets (`delivery_sheets`) and the prepaint.
    runtime: str | None = None
    # The host's own head metadata, such as a published page's link card.
    head: str = ""
    # The page root the document names as canonical: the live root, each stamped
    # version, and each immutable revision all serve it, and the page root stands for
    # them. Relative to the delivery, which has no origin to know.
    page_root: str | None = None
    html_attributes: Mapping[str, str] = field(default_factory=dict)
    body_attributes: Mapping[str, str] = field(default_factory=dict)


def compose_document(
    source: str,
    revision: int,
    version: int | None,
    *,
    executable: str,
    widgets: dict,
    resources: Mapping[str, Resource],
    registry: Mapping,
    delivery: Delivery,
) -> str:
    """Deliver one authored document under a host's `delivery`.

    The source is marked with what its `registry` declares and the size of the media
    it names (`mark_declared`), re-addressed (`rebase_document`), and then receives
    delivery's head
    right after the head's start tag, ahead of any authored executable content: the
    prelude, the import map, the canonical address, the prepaint, the runtime script,
    the theme, the adopted sheets, the host's metadata, and the runtime entry, each
    where the host has one. A document with a runtime, served or exported, carries the
    prepaint (`runtime/prepaint.js`), which says before the first paint what the
    runtime will draw and whether it could not start. It reads the canonical address,
    so that comes first; it names a startup fault before the host's runtime script
    hears of it, so it comes before that. The shared Lit implementation follows the
    prepaint whenever the document uses an `x-initial` producer. Used bundles then
    register the package producers that the body's parser invocations run. Later
    modules export this same Lit instance; other pages load Lit as a normal module.
    These scripts stand before the theme, since a
    script after a stylesheet still loading waits for it. The root carries the host's attributes and the
    page's Layout (`data-lf-layout`), whose body rules must hold before `main` is parsed. The
    import map precedes every script, since a browser reads no map once a module has
    begun to load.
    """
    initial = (
        initial_script_paths(source, registry) if delivery.runtime is not None else []
    )
    import_map = delivery.import_map
    if initial and import_map is not None:
        imports = import_map["imports"]
        # Hosted documents map directories. Export's exact leaf: graph already
        # embeds the selected facade under Lit's canonical module identity. Both
        # rooted layer imports and rebased page imports must select that instance.
        if "/vendor/" in imports:
            import_map = {
                **import_map,
                "imports": {
                    **imports,
                    "/vendor/lit.js": delivery.address("/vendor/lit-shared.js"),
                    delivery.address("/vendor/lit.js"): delivery.address(
                        "/vendor/lit-shared.js"
                    ),
                },
            }
    source = rebase_document(
        mark_declared(
            source, registry, resources, initial=delivery.runtime is not None
        ),
        delivery.address,
        inline_stylesheet=delivery.inline_stylesheet,
    )
    document = SourceDocument(source)
    if "head" not in document.authoring.wrapper_tags:
        raise ValueError("document has no explicit <head>")
    theme = (
        runtime_element("style", {}, delivery.inline_stylesheet("/theme.css"))
        if delivery.inline_stylesheet is not None
        else runtime_element(
            "link",
            {
                "rel": "stylesheet",
                "href": delivery.address("/theme.css"),
                "crossorigin": "anonymous",
            },
        )
    )
    # Physical page-side placement keeps the theme's lf-base contract, below package
    # and authored overrides. An adopted sheet would rank after those same defaults.
    if delivery.runtime is not None and annotation_mode(document) == "overlay":
        annotation_theme = rebase_css(
            resources["/runtime/annotation-overlay/annotation-theme.css"].data.decode(
                "utf-8"
            ),
            "/runtime/annotation-overlay/annotation-theme.css",
            delivery.address,
        )
        theme = (
            runtime_element(
                "style",
                {"data-lf-annotation-theme": True},
                f"@layer {', '.join(CASCADE_LAYERS)};\n"
                f"@layer lf-base {{\n{annotation_theme}\n}}",
            )
            + theme
        )
    head = (
        delivery_prelude(document, revision, version, executable, widgets)
        + (
            runtime_element("script", {"type": "importmap"}, json_script(import_map))
            if import_map is not None
            else ""
        )
        + (
            runtime_element(
                "link", {"rel": "canonical", "href": f"{delivery.page_root}/"}
            )
            if delivery.page_root is not None
            else ""
        )
        + (
            runtime_element(
                "script", {}, resources["/runtime/prepaint.js"].data.decode()
            )
            + initial_scripts(initial, resources)
            if delivery.runtime is not None
            else ""
        )
        + (delivery.runtime or "")
        + theme
        + (
            delivery_sheets(resources, delivery.address, document)
            if delivery.runtime is not None
            else ""
        )
        + delivery.head
        + (
            runtime_element("script", {"type": "module", "src": entry})
            if (entry := delivery.address("/leaf.js")) is not None
            else ""
        )
    )
    head_start, head_end = document.authoring.wrapper_tags["head"]
    insertions = [(head_end, head)]
    if delivery.runtime is not None:
        # A classic parser checkpoint waits for every preceding stylesheet, including
        # the author's head overrides. The initial observer then receives styled body
        # nodes before their first paint, rather than placing margin content on CSS load's
        # later task. It shares the same margin layout computation used after upgrade.
        insertions.append(
            (
                document.authoring.wrapper_tags["body"][1],
                runtime_element(
                    "script",
                    {},
                    "document.documentElement.lfInitial.marginContentLayout()",
                ),
            )
        )
    root = dict(delivery.html_attributes)
    if (layout := page_layout(document, registry)) is not None:
        root["data-lf-layout"] = layout
    if root:
        attributes = _attributes(root)
        insertions.append(
            (document.authoring.wrapper_tags["html"][1] - 1, attributes)
            if "html" in document.authoring.wrapper_tags
            # A source may leave <html> implicit; the tag is then written where the
            # parser would have implied it, before the head.
            else (head_start, f"<html{attributes}>")
        )
    if delivery.body_attributes:
        insertions.append(
            (
                document.authoring.wrapper_tags["body"][1] - 1,
                _attributes(delivery.body_attributes),
            )
        )
    for offset, text in sorted(insertions, key=lambda item: item[0], reverse=True):
        source = source[:offset] + text + source[offset:]
    return UTF8_BOM + source
