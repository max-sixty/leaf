"""Compose the parts of the product documents that other sources own.

Every page under `docs/` is a Leaf source, authored for what only it decides: its
prose, which examples the catalog shows and under which headings, and where each part
below sits. A part whose facts another source owns is authored as an empty slot, and
every builder of a product document, the site build and a local preview alike, fills
it here from that owner as it reads the source (`page_fixtures.authored_markup`):

- `nav.sitenav`: the site's routes (`SITE_NAV`), the page's own marked current;
- an `<img>` without a `src` inside a link to `/examples/<name>/`: that example's
  catalog preview, at the address `leaf page media` gives the bytes of the asset tree
  the build reads, the pinned one unless a draft's is handed in;
- `.example-description` inside a catalog link (`a.example-link`): the example's
  `<meta name="description">`;
- `table#all-verbs`'s body: every `x-state` verb the kernel and the bundled packages
  declare, in registry order;
- `nav.reference-index` and `div.reference-list`: the kernel registry's `$keys`.

A slot that already holds content is refused, since a copy there would go stale
silently. The edits splice into the authored source at the parser's own spans, so every
byte outside a slot is published as written.
"""

import html
import json
import re
from pathlib import Path

from leaf.media import media_name
from leaf.schema import MEDIA_DIR
from leaf.structure import SourceDocument

from leaf_dev import ROOT
from leaf_dev.example_data import document_metadata
from leaf_dev.leaf_assets import pinned_assets

DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
ASSETS = ROOT / "skills" / "leaf" / "assets"
PACKAGES = ROOT / "skills" / "leaf" / "packages"

PRODUCT_ROUTES = {
    "index.html": "/",
    "examples.html": "/examples/",
    "how-it-works.html": "/how-it-works/",
    "extending.html": "/extending/",
    "registry.html": "/registry/",
    "event-log.html": "/event-log/",
    "threads.html": "/threads/",
    "website.html": "/website/",
}
# The site's route bar, the brand first.
SITE_NAV = (
    ("/", "leaf"),
    ("/examples/", "Examples"),
    ("/how-it-works/", "How it works"),
    ("/extending/", "Extending"),
    ("https://github.com/max-sixty/leaf", "GitHub"),
)
# A $keys entry longer than its first sentence by this many words keeps the rest
# behind a disclosure.
COLLAPSED_DETAIL_WORDS = 30


def media_url(source: Path) -> str:
    """The page path an image takes once `leaf page media` has stored it."""
    return f"/{MEDIA_DIR}/{media_name(source.read_bytes(), source.suffix)}"


def catalog_preview(assets: Path, name: str) -> Path:
    """Where an asset tree holds one example's catalog preview
    (`leaf_dev.example_previews`)."""
    return assets / "examples" / f"example-{name}.jpg"


def example_name(link) -> str | None:
    """The example a link opens, or None for any other destination."""
    found = re.fullmatch(r"/examples/([^/]+)/", link.attrs.get("href", ""))
    return found.group(1) if found else None


def site_nav(current: str) -> list[str]:
    links = []
    for index, (href, label) in enumerate(SITE_NAV):
        attrs = ' class="brand"' if index == 0 else ""
        attrs += f' href="{href}"'
        if href == current:
            attrs += ' aria-current="page"'
        links.append(f"<a{attrs}>{label}</a>")
    return links


def markup_record(verb_state: dict) -> str:
    """What a verb's standing state reads as in markup."""
    if "creates" in verb_state:
        return f"creates an <code>{verb_state['creates']['child']}</code>"
    shape = verb_state.get("record")
    if shape is None:
        return "none"
    if shape["kind"] == "position":
        return f"position in an <code>{shape['within']}</code>"
    if shape["kind"] == "body":
        return "body"
    written = ", written by the agent" if verb_state.get("writer") == "agent" else ""
    return f"<code>{shape['attr']}</code> attribute{written}"


def verb_rows() -> list[str]:
    registries = [
        ASSETS / "registry.json",
        *sorted(PACKAGES.glob("*/registry.json")),
    ]
    rows = []
    for path in registries:
        for tag, element in json.loads(path.read_text(encoding="utf-8")).items():
            if not tag.startswith("lf-"):
                continue
            for verb, verb_state in element.get("x-state", {}).items():
                cells = (
                    f"<code>{tag}</code>",
                    f"<code>{verb}</code>",
                    verb_state["unit"],
                    markup_record(verb_state),
                )
                rows.append(
                    "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"
                )
    return rows


def registry_keys() -> dict[str, str]:
    keys = json.loads((ASSETS / "registry.json").read_text(encoding="utf-8"))["$keys"]
    return {key: keys[key] for key in sorted(keys) if key != "description"}


def key_prose(text: str) -> str:
    """A $keys paragraph as HTML: escaped, with `code` spans marked up."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", html.escape(text, quote=False))


def key_summary(text: str) -> tuple[str, str]:
    """The visible summary and any substantial detail to disclose."""
    first, separator, detail = text.partition(". ")
    if not separator or len(detail.split()) < COLLAPSED_DETAIL_WORDS:
        return text, ""
    return first + ".", detail


def key_index() -> list[str]:
    return [f'<a href="#{key}"><code>{key}</code></a>' for key in registry_keys()]


def key_entries() -> list[str]:
    entries = []
    for key, text in registry_keys().items():
        lead, detail = key_summary(text)
        contract = ""
        if detail:
            contract = (
                '<details class="reference-more">'
                f'<summary aria-label="Full {key} contract">Full contract</summary>'
                f"<p>{key_prose(detail)}</p>"
                "</details>"
            )
        entries.append(
            f'<section class="reference-entry" id="{key}">'
            f"<h3><code>{key}</code></h3>"
            f'<div class="reference-copy"><p>{key_prose(lead)}</p>{contract}</div>'
            "</section>"
        )
    return entries


def compose(source: Path, markup: str, *, assets: Path | None = None) -> str:
    """Fill the slots of one product document from their owners."""
    document = SourceDocument(markup)
    edits: list[tuple[int, int, str]] = []

    def fill(element, children: list[str] | str) -> None:
        location = element.source_location
        _, start = document.offsets(location.start_tag)
        end, _ = document.offsets(location.end_tag)
        if markup[start:end].strip():
            raise ValueError(
                f"{source.name}:{location.start_tag.start_line}: "
                f"<{element.tag}> is composed from its owner (leaf_dev.docs); "
                "leave it empty"
            )
        if isinstance(children, str):
            edits.append((start, end, children))
            return
        line_start = markup.rfind("\n", 0, start) + 1
        indent = re.match(r"[ \t]*", markup[line_start:]).group()
        inner = "".join(f"\n{indent}  {child}" for child in children)
        edits.append((start, end, f"{inner}\n{indent}"))

    for nav in document.tree.select("nav.sitenav"):
        fill(nav, site_nav(PRODUCT_ROUTES[source.name]))
    previews = None
    for link in document.tree.select("a[href]"):
        name = example_name(link)
        if name is None:
            continue
        for image in link.select("img:not([src])"):
            if previews is None:
                previews = assets or pinned_assets()
            at = document.offsets(image.source_location.start_tag)[0] + len("<img")
            address = media_url(catalog_preview(previews, name))
            edits.append((at, at, f' src="{address}"'))
        if link.has_class("example-link"):
            _, description = document_metadata(EXAMPLES / f"{name}.html")
            for caption in link.select(".example-description"):
                fill(caption, html.escape(description, quote=False))
    for body in document.tree.select("table#all-verbs > tbody"):
        fill(body, verb_rows())
    for nav in document.tree.select("nav.reference-index"):
        fill(nav, key_index())
    for listing in document.tree.select("div.reference-list"):
        fill(listing, key_entries())
    for start, end, text in sorted(edits, reverse=True):
        markup = markup[:start] + text + markup[end:]
    return markup
