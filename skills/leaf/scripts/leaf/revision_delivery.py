"""Address a revision's documents and resources for the host delivering them.

A document and the captured resources it names use logical page paths: `/page/…` for
the author's files, `/media/…` for the page's images, and the layer's own files at the
root (`/icon.svg`, `/runtime/…`). Every host delivers the same captured bytes under an
address of its own — an HTTP server beneath a revision's URL, a published site beneath
a release, an offline export as embedded `data:` URLs — so each host passes one
`address` function, from a logical path to the URL it serves that path at, and the
walks below apply it. HTML source spans preserve prose and unrelated attributes,
JavaScript rewriting names only parsed imports, and CSS rewriting names only the URLs
`rewrite_css` reads. Nothing reads a document or a resource as text.

Over HTTP, media is the page's and everything else a document names is its revision's
(`DeliveryAddress`). `media/` holds content-addressed images shared across revisions;
the page root serves them in every host, and the runtime resolves the media a message
or a widget names against that same root (`runtime/media.js`). The layer's own module
graph imports rooted paths (`/runtime/…`, `/vendor/…`, `/widgets/…`), which the
document's import map sends to its revision (`layer_import_map`), so layer modules are
served as captured.
"""

import html
import json
import posixpath
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote, unquote, urlsplit

import turbohtml

from .revision_artifact import Resource, authored_imports, bind_imports, rewrite_css
from .schema import BROWSER_DIRS, MEDIA_DIR, VENDORED_FILES
from .structure import (
    DELIVERY_ENCODING_META,
    SourceDocument,
    rel_tokens,
    rewrite_attribute_references,
    source_index,
)

# From a logical page path to the URL one host serves it at.
Address = Callable[[str], str]

# The paths of a page's namespace a document or resource may name: the author's files,
# the page's media, and the layer. The API and the page's documents are the runtime's
# and the server's to address, never an authored reference's.
_PAGE_PATH = re.compile(
    "/(?:"
    + "|".join(
        [f"(?:page|{MEDIA_DIR}|{'|'.join(BROWSER_DIRS)})/.+"]
        + [re.escape(name) for name in VENDORED_FILES]
    )
    + ")"
)


def page_path(reference: str, base: str) -> tuple[str, str] | None:
    """The logical page path `reference` names from `base`, and the suffix it keeps.

    None for a reference that does not name the page: one to another origin, a
    `data:` URL, a fragment of this document, or a path outside the page's namespace.
    The suffix is the query and fragment, which travel with the path to its address.
    """
    if not reference or reference.startswith(("#", "data:")):
        return None
    try:
        parsed = urlsplit(reference)
    except ValueError:
        return None
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    path = unquote(parsed.path)
    resolved = posixpath.normpath(
        path if path.startswith("/") else posixpath.join(posixpath.dirname(base), path)
    )
    if not _PAGE_PATH.fullmatch(resolved):
        return None
    suffix = ("?" + parsed.query if parsed.query else "") + (
        "#" + parsed.fragment if parsed.fragment else ""
    )
    return resolved, suffix


def _rebase(reference: str, base: str, address: Address) -> str:
    located = page_path(reference, base)
    if located is None:
        return reference
    path, suffix = located
    return address(path) + suffix


@lru_cache(maxsize=32)
def rebase_css(
    source: str, base: str, address: Address, *, declarations: bool = False
) -> str:
    """Re-address every URL a stylesheet at `base` loads, the rest byte-for-byte.

    Held for the addresses a server answers again and again: parsing the theme costs
    tens of milliseconds, and every document and stylesheet request would pay it.
    """
    return rewrite_css(
        source,
        lambda reference: _rebase(reference, base, address),
        declarations=declarations,
    )


def rebase_module(data: bytes, base: str, address: Address) -> bytes:
    """Re-address every literal import of an authored module at `base`."""
    return bind_imports(data, authored_imports(data, base), address)


def rebase_document(
    source: str,
    address: Address,
    *,
    inline_stylesheet: Callable[[str], str] | None = None,
) -> str:
    """Re-address every reference an HTML document makes, and nothing else in it.

    The references are an authored module's `src` and its literal imports, a
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
            attrs = SourceDocument._attrs(element)
            tag = element.tag
            stylesheet = tag == "link" and "stylesheet" in rel_tokens(attrs)
            if (
                stylesheet
                and inline_stylesheet is not None
                and (located := page_path(attrs.get("href", ""), "/index.html"))
            ):
                kept = "".join(
                    f' {name}="{html.escape(value, quote=True)}"'
                    for name, value in attrs.items()
                    if name in {"media", "title", "data-lf-runtime", "disabled"}
                )
                css = re.sub(
                    r"</style",
                    r"<\\/style",
                    inline_stylesheet(located[0]),
                    flags=re.IGNORECASE,
                )
                start, end = span(location.start_tag)
                edits.append((start, end, f"<style{kept}>{css}</style>"))
                continue
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
                        (start, end, f'{name}="{html.escape(delivered, quote=True)}"')
                    )
            if tag in {"script", "style"} and location.end_tag is not None:
                start = index(location.start_tag.end_line, location.start_tag.end_col)
                end = index(location.end_tag.start_line, location.end_tag.start_col)
                body = source[start:end]
                if tag == "style":
                    delivered = rebase_css(body, "/index.html", address)
                elif attrs.get("type") == "module" and not attrs.get("src"):
                    delivered = rebase_module(
                        body.encode("utf-8"), "/index.html", address
                    ).decode("utf-8")
                else:
                    continue
                if delivered != body:
                    edits.append((start, end, delivered))

    for start, end, value in sorted(edits, reverse=True):
        source = source[:start] + value + source[end:]
    return source


@dataclass(frozen=True)
class DeliveryAddress:
    """Where an HTTP host serves each logical path of one revision's document.

    Media is the page's own and answers at the page root. Every other path is the
    revision's and answers beneath `asset_root`, where its capture is served. A value,
    so a stylesheet addressed for one revision is parsed once (`rebase_css`).
    """

    page_root: str
    asset_root: str

    def __call__(self, path: str) -> str:
        root = self.page_root if path.startswith(f"/{MEDIA_DIR}/") else self.asset_root
        return root.rstrip("/") + quote(path, safe="/")


def layer_import_map(asset_root: str) -> str:
    """Send the layer's rooted module imports to the revision serving them.

    Every layer module names its dependencies by rooted path, as the page directory
    lays them out. The map rebinds each directory for the whole document, so a module
    keeps its captured bytes wherever the revision is served, and a page module or a
    render probe importing `/runtime/widget-api.js` reaches the runtime's own instance.
    """
    root = asset_root.rstrip("/")
    return json_script(
        {"imports": {f"/{name}/": f"{root}/{name}/" for name in BROWSER_DIRS}}
    )


def deliver_resource(resource: Resource, logical_path: str, address: Address) -> bytes:
    """Address one captured resource, including a page widget served under an alias.

    A stylesheet's URLs and an authored module's imports are re-addressed; a layer
    module keeps its bytes, since the import map addresses its imports. A page widget
    served through ``widgets/<tag>.js`` must pass its manifest path here
    (``/page/widgets/<tag>.js``), which is the base of its authored imports.
    """
    if resource.mime == "application/javascript" and logical_path.startswith("/page/"):
        return rebase_module(resource.data, logical_path, address)
    if resource.mime == "text/css":
        return rebase_css(resource.data.decode("utf-8"), logical_path, address).encode(
            "utf-8"
        )
    return resource.data


def delivery_identity(
    revision: int, version: int | None, executable: str | None, widgets: dict
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

    Every delivery writes this, whoever is delivering: the HTTP boundary, the static
    live shell, the MCP app's document, and a standalone export. A document that says
    part of it is a document the next reader of the contract has to guess about.
    """
    # A revision captured before these were recorded says neither, rather than saying it
    # is something called "None". A document that does not state its executable identity
    # is one an open page cannot take a revision from, which is the reload path.
    return (
        f'<meta name="lf-revision" data-lf-runtime content="{revision}">'
        + (
            f'<meta name="lf-executable" data-lf-runtime content="{executable}">'
            f'<meta name="lf-widgets" data-lf-runtime '
            f'content="{html.escape(json.dumps(widgets, separators=(",", ":")), quote=True)}">'
            if executable is not None
            else ""
        )
        + (
            f'<meta name="lf-version" data-lf-runtime content="{version}">'
            if version is not None
            else ""
        )
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


def delivery_sheets(resources: Mapping[str, Resource], address: Address) -> str:
    """Carry the layer's adopted stylesheets in the document that runs the layer.

    `runtime/stylesheets.js` constructs the chrome's and the marks' sheets while it
    evaluates, so their text must be in hand without a request. WebKit has no CSS module
    scripts to import them with, and a fetch awaited at module scope would make every
    page module that imports the widget API evaluate after `DOMContentLoaded`. Like the
    identity above, every delivery writes this, with the sheets' own URLs at the
    delivery's `address`: a constructed sheet resolves them against the document.

    The sheets go out as they are written, comments included. They used to be stripped
    here, which is the one thing that made the text a user receives differ from the
    file a maintainer reads, and a page has no build step to make that difference
    anywhere else. The comments are most of the weight: 62KB of sheet becomes 134KB,
    or 11KB against 39KB over the wire, at the head of every delivered document.
    """
    sheets = {
        name: rebase_css(resources[path].data.decode("utf-8"), path, address)
        for name, path in (
            ("chrome", "/runtime/chrome.css"),
            ("marks", "/runtime/marks.css"),
        )
    }
    return (
        '<script type="application/json" data-lf-runtime data-lf-sheets>'
        f"{json_script(sheets)}</script>"
    )


def delivery_prelude(
    document: SourceDocument,
    revision: int,
    version: int | None,
    executable: str | None,
    widgets: dict,
) -> str:
    """Declare encoding, a device-width viewport, and immutable Leaf identity.

    Authors can supply their own viewport. Otherwise every delivery starts at the
    device width, so a phone uses responsive layout instead of a scaled desktop page.
    Edge-to-edge layout lets the chrome use the device's safe-area insets.
    """
    viewport = (
        ""
        if any(meta["name"].lower() == "viewport" for meta in document.named_metas)
        else '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
    )
    return (
        DELIVERY_ENCODING_META
        + delivery_identity(revision, version, executable, widgets)
        + viewport
    )
