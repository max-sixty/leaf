"""One parsed source document and its structural readings."""

import hashlib
import re
from collections.abc import Mapping
from functools import cached_property, lru_cache
from html import escape

import turbohtml

from .findings import Finding
from .registry.kernel import kernel_authored
from .resource_urls import ReferenceError, resource_reference
from .schema import EVENT_ID, MEDIA_DIR

UTF8_BOM = "\ufeff"

# ---------- check: deterministic pre-handover lint ----------

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
# Elements whose end tag HTML lets you omit — leaving one "unclosed" is valid,
# so the balance check must not flag them (only genuinely-open structural
# elements like <div>/<section> point at a real layout bug).
OPTIONAL_END = {
    "p",
    "li",
    "dd",
    "dt",
    "td",
    "th",
    "tr",
    "thead",
    "tbody",
    "tfoot",
    "option",
    "optgroup",
    "caption",
    "colgroup",
    "rp",
    "rt",
    "html",
    "head",
    "body",
}
# HTML's ASCII whitespace: an id may hold none of it.
ASCII_WHITESPACE = frozenset("\t\n\f\r ")

# Blocks a user predictably points at whole rather than quoting: a run of code,
# a table, a figure, an aside set off from the prose — and the sections
# references/page-authoring.md holds to "Stable anchors". Widgets aren't listed
# because the
# registry's schemas already demand ids wherever pointing at one matters.
POINTABLE_TAGS = {"section", "article", "aside", "pre", "table", "figure"}
# Prose and headings can use their enclosing block's address, but without one
# element selection has no target.
PROSE_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6"}
# Where an aim that found no tighter id has escaped to: naming one of these is
# naming most of the page.
SECTIONING_TAGS = {"section", "article", "main", "body"}
# The page-wide allocations the runtime reads from `body`, which a sample template
# carries onto its child's body (`$authored` in the kernel registry).
PAGE_ALLOCATIONS = kernel_authored()["allocations"]
# The allocations a page occurrence may state, each attribute with the values it takes:
# a block's width in the page's flow, whether it bounds its own height, the height in
# CSS pixels of a widget that draws into a box of a stated height (x-height), and the
# page-wide ones. Delivery honours a width, bound or height only where it means
# something (`authored_on` in the kernel registry's `$marks`), and paints it for the
# runtime to read.
AUTHORED_ALLOCATIONS = {
    "data-width": ("wide", "available"),
    "data-bound": ("start", "end"),
    "data-height": re.compile("[1-9][0-9]*"),
    **{attr: tuple(values) for attr, values in PAGE_ALLOCATIONS.items()},
}


def allocation_valid(attr: str, value: str) -> bool:
    """Whether an authored allocation's value is one of the values `attr` takes."""
    values = AUTHORED_ALLOCATIONS[attr]
    if isinstance(values, re.Pattern):
        return values.fullmatch(value) is not None
    return value in values


# The script types a browser runs as JavaScript, per the HTML standard: no type, or a
# JavaScript MIME type, runs as a classic script, and "module" as a module. It reads
# "importmap" and "speculationrules" as JSON, and never runs any other type.
JAVASCRIPT_TYPES = frozenset(
    {
        "",
        "application/ecmascript",
        "application/javascript",
        "application/x-ecmascript",
        "application/x-javascript",
        "text/ecmascript",
        "text/javascript",
        "text/javascript1.0",
        "text/javascript1.1",
        "text/javascript1.2",
        "text/javascript1.3",
        "text/javascript1.4",
        "text/javascript1.5",
        "text/jscript",
        "text/livescript",
        "text/x-ecmascript",
        "text/x-javascript",
    }
)


def script_kind(attrs: dict) -> str:
    """What a browser does with a script element: "module", "classic", "importmap",
    "speculationrules", or "data" for a block it never runs."""
    kind = (attrs.get("type") or "").strip().lower()
    if kind in {"module", "importmap", "speculationrules"}:
        return kind
    return "classic" if kind in JAVASCRIPT_TYPES else "data"


# Same-origin parents already share the page's DOM and request authority. Permit
# embedding there; a different origin must not disguise a live decision under its
# own controls, even when same-site cookies authorize the framed page. The server
# sends this policy as a header and the site manifest carries it to the Worker.
FRAME_ANCESTORS_CSP = "frame-ancestors 'self'"
# Non-painting document structure that may stand outside the authored main. Head
# metadata is allowed only while the parser is actually inside head.
DOCUMENT_WRAPPERS = {"html", "head", "body", "main"}
HEAD_METADATA_TAGS = {"base", "link", "meta", "script", "style", "title"}


def _srcset_urls(value: str):
    """Yield URL spans from the browser's comma-and-descriptor image candidate form."""
    cursor = 0
    while cursor < len(value):
        while cursor < len(value) and (value[cursor].isspace() or value[cursor] == ","):
            cursor += 1
        start = cursor
        while cursor < len(value) and not value[cursor].isspace():
            cursor += 1
        end = cursor
        while end > start and value[end - 1] == ",":
            end -= 1
        if end > start:
            yield start, end, value[start:end]
        if end != cursor:
            continue
        depth = 0
        while cursor < len(value):
            char = value[cursor]
            if char == "(":
                depth += 1
            elif char == ")" and depth:
                depth -= 1
            elif char == "," and not depth:
                cursor += 1
                break
            cursor += 1


def source_index(source: str):
    """Map the parser's (line, column) positions back to offsets in `source`.

    The parser's own offsets count a CRLF as one character, so an edit placed by them
    lands short of its span in a CRLF source; its lines and columns do not.
    """
    lines = [0, *(match.end() for match in re.finditer(r"\r\n?|\n", source))]
    return lambda line, column: lines[line - 1] + column


def _start(element) -> tuple[int, int]:
    """Where a source element's start tag begins: its identity across walks."""
    start = element.source_location.start_tag
    return (start.start_line, start.start_col)


def element_attrs(element) -> dict:
    """An element's attributes as its source spells them, a token list joined."""
    return {
        name: " ".join(value) if isinstance(value, list) else value
        for name, value in element.attrs.items()
    }


def delivered_elements(tree):
    """Every element a parsed document delivers, in document order: its own, those
    in each template's contents, and those in each declarative shadow root, which
    delivery serializes. Delivery's rewrite (`revision_delivery.rebase_document`)
    walks this, and so does every reader of the CSS it rewrites
    (`delivered_sheets`), so they meet the same sheets."""
    roots = [tree]
    for root in roots:
        for element in root.find_all(True):
            if element.shadow_root is not None:
                roots.append(element.shadow_root)
            yield element


def delivered_sheets(document: "SourceDocument"):
    """Each stylesheet delivery rewrites in `document` (`delivered_elements`), as its
    CSS, the name its author finds it by, and whether it is a style attribute's
    declarations: each `<style>` element's text and each `style` attribute."""
    index = source_index(document.html)
    for element in delivered_elements(document.tree):
        location = element.source_location
        if location is None:
            continue
        line = location.start_tag.start_line
        style = element.attrs.get("style")
        if isinstance(style, str):
            yield style, f"<{element.tag} style> (line {line})", True
        if element.tag == "style" and location.end_tag is not None:
            start = index(location.start_tag.end_line, location.start_tag.end_col)
            end = index(location.end_tag.start_line, location.end_tag.start_col)
            yield document.html[start:end], f"page <style> (line {line})", False


@lru_cache(maxsize=4096)
def _local_resource(value: str) -> tuple[str, str] | None:
    """Read an attribute candidate; arbitrary prose need not be a valid URL.

    A pure reading of the value, asked of every attribute a document carries, so it
    is kept by value: a layer's examples and a page's revisions repeat the same
    attributes, each of which costs two WHATWG parses."""
    try:
        return resource_reference(value, "/index.html")
    except ReferenceError:
        return None


def attribute_references(tag: str, attrs: dict, name: str, value: str):
    """Yield the `(start, end)` span of each URL one attribute value carries.

    A resource attribute carries the URLs the browser loads for it: an image's `src`
    or `srcset`, a poster, an SVG image, filter image, or use `href`, an icon link.
    Any other attribute whose whole value is a page media path names that media — a
    link to a screenshot, a widget's before and after shot. Capture keeps what these
    name and delivery re-addresses exactly these, so a revision's record and its
    delivered document agree about which references it has.
    """
    normalized_tag = tag.lower()
    if name == "srcset":
        if normalized_tag in {"img", "source"}:
            yield from ((start, end) for start, end, _ in _srcset_urls(value))
        return
    if (
        name in {"src", "poster"}
        and normalized_tag not in {"script", "iframe"}
        or name in {"href", "xlink:href"}
        and (
            normalized_tag in {"feimage", "image", "use"}
            or normalized_tag == "link"
            and "icon" in attrs.get("rel", [])
        )
        or (
            (reference := _local_resource(value)) is not None
            and reference[0].startswith(f"/{MEDIA_DIR}/")
        )
    ):
        yield 0, len(value)


def rewrite_attribute_references(
    tag: str, attrs: dict, name: str, value: str, rewrite
) -> str | None:
    """Rewrite just the URL spans `attribute_references` reads in one value."""
    for start, end in reversed(tuple(attribute_references(tag, attrs, name, value))):
        replacement = rewrite(value[start:end])
        if replacement is None:
            return None
        value = value[:start] + replacement + value[end:]
    return value


def pre_body(element) -> str | None:
    """The text of `element`'s first `<pre>` child: the body a Markdown-bodied element
    renders and a `body` state record reads, or None where it has none."""
    pre = next(
        (
            child
            for child in element.children
            if isinstance(child, turbohtml.Element) and child.tag == "pre"
        ),
        None,
    )
    if pre is None:
        return None
    return "".join(
        child.data for child in pre.children if isinstance(child, turbohtml.Text)
    )


class SourceDocument:
    """One browser-compatible structural reading of authored HTML.

    TurboHTML owns HTML recovery and source locations. This class retains Leaf's
    authoring-specific indexes and its stricter errors for ambiguous source constructs:
    element ids and their enclosing widget, external assets and metadata, each lf-*
    element's attributes and direct contents, title and styles, and the
    exact authored construction. It does not maintain a second element stack or
    tree-building grammar, and it keeps foreign SVG as exact source rather than
    reconstructing it.

    Construction reads only the element index: ids and their holders, the lf-*
    records and the live samples. A revision inventory scan of a page's whole
    history reads nothing else of each revision, and the rest costs twenty times the
    tree's parse. Everything else is one more reading, `authoring`, taken on first
    use.

    Registry examples are fragments, so `fragment=True` parses in template context:
    table rows, cells and select options survive without a surrounding document.
    """

    def __init__(self, source: str, *, fragment: bool = False):
        self.html = source
        self.data = source.encode("utf-8")
        self.digest = f"sha256:{hashlib.sha256(self.data).hexdigest()}"
        self.all_ids = []
        # {tag, line, attrs, parent, direct, children, text, body, holder}
        self.lf_elements = []
        self.samples = []
        # id → the record of the innermost lf-* element standing around it, an
        # element's own id standing in itself. Where an id lives is structure; which of
        # those elements is a slot a decision retires and which widget holds it is the
        # registry's word, read by whoever has one, so this parse need not know a widget
        # by name. Containment as enclosing ids, which liveness reads, is
        # `passages.enclosing_ids`.
        self.holders = {}
        self._source = source
        # The record of each lf-* element, by where its start tag begins, for the
        # authoring walk: the parser hands out a new object per visit of an element.
        self._records = {}
        self.tree = (
            turbohtml.parse_fragment(
                source, context="template", scripting=True, source_locations=True
            ).parent
            if fragment
            else turbohtml.parse(source, scripting=True, source_locations=True)
        )
        for child in self.tree.children:
            if isinstance(child, turbohtml.Element):
                self._index(child, holder=None, in_svg=False)

    @cached_property
    def authoring(self) -> "Authoring":
        """What a check, delivery or capture reads beyond the element index."""
        return Authoring(self)

    @cached_property
    def _source_index(self):
        return source_index(self._source)

    @staticmethod
    def _position(element) -> tuple[int, int]:
        current = element
        while current is not None:
            if current.position is not None:
                return current.position
            current = current.parent
        return (1, 0)

    def offsets(self, span) -> tuple[int, int]:
        """Where one of the parser's source spans starts and ends in this source, so
        a caller can splice the source at an element's own tags."""
        return (
            self._source_index(span.start_line, span.start_col),
            self._source_index(span.end_line, span.end_col),
        )

    def _span_source(self, span) -> str:
        start, end = self.offsets(span)
        return self._source[start:end]

    @staticmethod
    def _source_element(element) -> bool:
        return element.source_location is not None

    def _index(self, element, *, holder: dict | None, in_svg: bool) -> None:
        """Record ids, their holders, lf-* elements and live samples: all a
        revision inventory scan reads, so the one walk construction takes."""
        tag = element.tag
        located = element.source_location is not None
        record = None
        if located and (tag.startswith("lf-") or element.attrs.get("id")):
            attrs = element_attrs(element)
            identity = attrs.get("id")
            if identity:
                self.all_ids.append(identity)
                self.holders[identity] = holder
            if tag.startswith("lf-"):
                parent = element.parent
                record = {
                    "tag": tag,
                    "line": self._position(element)[0],
                    "attrs": attrs,
                    "parent": parent.tag
                    if isinstance(parent, turbohtml.Element)
                    else None,
                    "direct": [],
                    "children": [],
                    "text": False,
                    "body": "",
                    "holder": holder,
                }
                self.lf_elements.append(record)
                self._records[_start(element)] = record
                if identity:
                    self.holders[identity] = record

        if in_svg or (located and tag == "svg"):
            for child in element.children:
                if isinstance(child, turbohtml.Element):
                    self._index(child, holder=holder, in_svg=True)
            return

        if record is not None:
            self._record_direct_contents(record, element)
        for child in element.children:
            if isinstance(child, turbohtml.Element):
                self._index(child, holder=record or holder, in_svg=False)

        if tag == "template" and "data-sample" in element.attrs:
            self._sample_resources(element)

    @staticmethod
    def _record_direct_contents(record: dict, element) -> None:
        for child in element.children:
            if isinstance(child, turbohtml.Element):
                record["children"].append(child.tag)
                record["direct"].append(child.tag)
            elif isinstance(child, turbohtml.Text) and child.data.strip():
                record["text"] = True
                record["direct"].append("#text")
        if (body := pre_body(element)) is not None:
            record["body"] = body

    def _sample_resources(self, template) -> None:
        """Read the complete child document without merging its identity space.

        The template owns the child's body declarations; their values are validated
        once on that synthesized body by the ordinary child document reader.
        """
        attrs = element_attrs(template)
        location = template.source_location
        content_start = self._source_index(
            location.start_tag.end_line, location.start_tag.end_col
        )
        content_end = (
            self._source_index(location.end_tag.start_line, location.end_tag.start_col)
            if location.end_tag
            else len(self._source)
        )
        body = "".join(
            f' {name}="{escape(value)}"'
            for name, value in attrs.items()
            if name in PAGE_ALLOCATIONS
        )
        source = (
            '<!doctype html><html lang="en"><head>'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{escape(attrs.get('id', 'Sample'))}</title></head>"
            # The template is the child's content, not its frame. The child is a column
            # page unless the template names its `main`'s classes, as a workspace's
            # `layout-workspace` does, since a document's Layout is not every page's.
            f'<body{body}><main class="{escape(attrs.get("class") or "layout-column")}">'
            # Preserve authored lines, including multiline tags in nested samples.
            + "\n" * (location.start_tag.end_line - 1)
            + self._source[content_start:content_end]
            + "</main></body></html>"
        )
        self.samples.append(
            {
                "attrs": attrs,
                "document": SourceDocument(source),
            }
        )

    @property
    def ids(self) -> set:
        return set(self.all_ids)

    @property
    def by_id(self) -> dict:
        """id → its element record, for every id-bearing lf-* element."""
        return {r["attrs"]["id"]: r for r in self.lf_elements if r["attrs"].get("id")}

    @property
    def restated(self) -> set:
        """Ids this version declares it has rewritten, retracting whatever the
        user had recorded on them."""
        return {
            rec["attrs"]["id"]
            for rec in self.lf_elements
            if rec["attrs"].get("id") and "restated" in rec["attrs"]
        }

    @property
    def overruled(self) -> set:
        """Ids this version declares it keeps its own state on, over a worker's
        report in force — the agent writer's mirror of `restated`."""
        return {
            rec["attrs"]["id"]
            for rec in self.lf_elements
            if rec["attrs"].get("id") and "overruled" in rec["attrs"]
        }

    @property
    def duplicate_ids(self) -> list:
        seen, dupes = set(), set()
        for i in self.all_ids:
            (dupes if i in seen else seen).add(i)
        return sorted(dupes)

    @property
    def reserved_ids(self) -> list:
        """Ids that trespass on the runtime's own namespace (see id_errors)."""
        return sorted({i for i in self.all_ids if i.startswith("lf-")})

    @property
    def event_shaped_ids(self) -> list:
        """Ids in the log's own event-id shape (see id_errors)."""
        return sorted({i for i in self.all_ids if re.fullmatch(EVENT_ID, i)})

    @property
    def spaced_ids(self) -> list:
        """Ids holding ASCII whitespace, which HTML forbids in one (see id_errors)."""
        return sorted({i for i in self.all_ids if not ASCII_WHITESPACE.isdisjoint(i)})


class Authoring:
    """A `SourceDocument`'s indexes beyond its element index, read in one walk of
    its tree (`SourceDocument.authoring`): its assets, metadata, styles, references,
    allocations, the content tree, and the source errors a check reports."""

    def __init__(self, document: SourceDocument):
        self._document = document
        # The content node of each of the document's lf-* records, by the record.
        self._nodes_of = {}
        self.errors = []
        self.unclosed = []  # source elements whose required end tag is absent
        # {attrs, parent, position, early_head} per external asset. Applicability and
        # placement belong to the asset record: parallel lists made one fact several
        # representations and let a later parser edit silently misalign them.
        self.external_scripts = []
        # Exact text of each inline script: the capture digests it.
        self.inline_scripts = []
        # Every <link>, whatever relation it declares. Two checks read these — the one
        # stylesheet a page dresses itself with, and the canonical address only
        # delivery may name — and indexing the tag answers both from one parse.
        self.links = []
        # {tag, line} per element that declares something about the whole document:
        # a <base>, an http-equiv <meta>, an import map.
        self.document_declarations = []
        # {name, content, line} per <meta name>, lf- declarations and ordinary
        # document metadata alike: one index of what the head names, so a user
        # after a description does not need a second parse of the same head.
        self.named_metas = []
        # The authored page lives under one direct body > main because that is the
        # element the first-replay presentation boundary withholds. Both assets that
        # establish that boundary belong in head; anything paintable outside main would
        # stand outside it. Scripts carry no paint; executable identity owns their
        # lifetime, including moves between head, main, and retained body.
        # Body lines come from source tokens because recovery erases a
        # duplicate <body>; main placement comes from the recovered tree.
        self.body_lines = []
        self.head_lines = []
        self.head_elements = []  # (line, direct child of authored html)
        self.main_elements = []  # (line, direct child of authored body)
        self.outside_main = []  # paintable content with no main ancestor
        # /media/ paths any attribute points at, so the check reads references and not
        # mentions: a page documenting Leaf can write one in prose without demanding a
        # screenshot that nothing displays.
        self.media_refs = set()
        self.resource_refs = set()
        self.style_blocks = []  # {css, line, attrs} per independent <style> sheet
        self.inline_styles = []  # {tag, line, style} per style="" declaration list
        # {tag, line, attr, value} per authored allocation: a data-width or data-bound.
        self.authored_allocations = []
        self.title = ""  # what <title> says, for the transcript's heading
        # {tag, line, under} per id-less pointable block, where under is the nearest
        # ancestor carrying an id. This is where a user's aim would otherwise land.
        self.bare_blocks = []
        # (tag, line, markers) per element wearing a data-lf-* attribute or lf-* class.
        # The prefix reserves names the runtime may coin later, without another list.
        self.reserved_markers = []
        # The same parse retains ordinary HTML, exact text, and construction locations
        # for inspection. Widget validation keeps its specialized index; content is one
        # tree, with no reconstructed HTML or parent objects.
        self.content = []
        self.nodes = []
        # (start, end) of the first html, head, and body start tag the source spells:
        # where delivery writes into the document.
        self.wrapper_tags = {}
        self._first_body_position = None
        self._source_errors()
        for child in document.tree.children:
            if isinstance(child, turbohtml.Element):
                self._visit(child, self.content)
        del self._document, self._first_body_position

    def node_of(self, record: dict) -> dict | None:
        """The content node of one of the document's lf-* records, or None for one
        inside SVG, which keeps its exact source rather than a tree."""
        return self._nodes_of.get(id(record))

    def _source_errors(self) -> None:
        document = self._document
        tokens = list(turbohtml.tokenize(document._source, capture_source=True))
        body_starts = [
            token
            for token in tokens
            if token.type is turbohtml.TokenType.START_TAG and token.tag == "body"
        ]
        self.body_lines = [token.line for token in body_starts]
        self._first_body_position = (
            (body_starts[0].line, body_starts[0].col) if body_starts else None
        )
        head_starts = [
            token
            for token in tokens
            if token.type is turbohtml.TokenType.START_TAG and token.tag == "head"
        ]
        self.head_lines = [token.line for token in head_starts]
        for token in tokens:
            if token.type is turbohtml.TokenType.START_TAG and token.tag in {
                "html",
                "head",
                "body",
            }:
                start = document._source_index(token.line, token.col)
                self.wrapper_tags.setdefault(
                    token.tag, (start, start + len(token.source))
                )
        starts = {
            (token.line, token.col): token
            for token in tokens
            if token.type is turbohtml.TokenType.START_TAG
        }
        for element in document.tree.descendants:
            if not isinstance(element, turbohtml.Element):
                continue
            location = element.source_location
            if location is None or location.end_tag is not None:
                continue
            start_source = document._span_source(location.start_tag).rstrip()
            if (
                element.tag not in VOID_TAGS | OPTIONAL_END
                and not start_source.endswith("/>")
            ):
                self.unclosed.append((element.tag, element.source_line))

        for error in document.tree.errors:
            if error.code == "non-void-html-element-start-tag-with-trailing-solidus":
                token = starts.get((error.line, error.col))
                tag = token.tag if token is not None else "element"
                self.errors.append(
                    Finding("self-closing", f"<{tag}>", {"line": error.line})
                )

    def _record_element(
        self,
        element,
        attrs: dict,
        *,
        parent_tag: str | None,
        ancestors: tuple,
    ) -> None:
        tag = element.tag
        line, column = SourceDocument._position(element)
        before_body = (
            self._first_body_position is None
            or (
                line,
                column,
            )
            < self._first_body_position
        )
        in_head = "head" in ancestors
        in_main = "main" in ancestors
        if tag == "script":
            script = {
                "attrs": attrs,
                "parent": parent_tag,
                "patch_region": "head" if in_head else "main" if in_main else "body",
                "position": (line, column),
                "early_head": in_head and before_body,
                "line": line,
            }
            if attrs.get("src"):
                self.external_scripts.append(script)
            else:
                self.inline_scripts.append({**script, "body": element.text})
        if (
            tag == "base"
            or (tag == "meta" and "http-equiv" in attrs)
            or (tag == "script" and script_kind(attrs) == "importmap")
        ):
            self.document_declarations.append({"tag": tag, "line": line})
        if tag == "link":
            self.links.append(
                {
                    "attrs": attrs,
                    "parent": parent_tag,
                    "early_head": in_head and before_body,
                    "line": line,
                }
            )
        if tag == "meta" and attrs.get("name"):
            self.named_metas.append(
                {"name": attrs["name"], "content": attrs.get("content"), "line": line}
            )
        if attrs.get("style"):
            self.inline_styles.append(
                {"tag": tag, "line": line, "style": attrs["style"]}
            )
        for attr in AUTHORED_ALLOCATIONS:
            if attr in attrs and not (
                tag == "template"
                and "data-sample" in attrs
                and attr in PAGE_ALLOCATIONS
            ):
                self.authored_allocations.append(
                    {"tag": tag, "line": line, "attr": attr, "value": attrs[attr]}
                )
        markers = sorted(name for name in attrs if name.startswith("data-lf-"))
        markers += sorted(
            name
            for name in (attrs.get("class") or "").split()
            if name.startswith("lf-")
        )
        if markers:
            self.reserved_markers.append((tag, line, markers))
        references = [
            (name, value[start:end])
            for name, value in attrs.items()
            if isinstance(value, str)
            for start, end in attribute_references(tag, attrs, name, value)
        ]
        self.resource_refs.update(reference for _, reference in references if reference)
        for _, reference in references:
            resolved = _local_resource(reference)
            if resolved is None:
                continue
            path, _suffix = resolved
            if path.startswith(f"/{MEDIA_DIR}/"):
                self.media_refs.add(path)

        if tag == "noscript":
            self.errors.append(Finding("noscript", "<noscript>", {"line": line}))
        # Only the outermost: an element inside one already named moves with it.
        if (
            not in_main
            and tag not in DOCUMENT_WRAPPERS
            and tag != "script"
            and not (in_head and tag in HEAD_METADATA_TAGS)
            and (parent_tag is None or parent_tag in DOCUMENT_WRAPPERS)
        ):
            self.outside_main.append({"tag": tag, "line": line, "text": False})

    def _visit(
        self,
        element,
        output: list,
        *,
        ancestors: tuple = (),
        in_svg: bool = False,
    ) -> None:
        document = self._document
        source_element = document._source_element(element)
        skip_implied = not source_element
        parent = element.parent
        parent_tag = parent.tag if isinstance(parent, turbohtml.Element) else None
        record = document._records.get(_start(element)) if source_element else None
        # A record and its node share one attribute dict, as they share one element.
        attrs = record["attrs"] if record is not None else element_attrs(element)
        line, column = document._position(element)

        if source_element:
            self._record_element(
                element, attrs, parent_tag=parent_tag, ancestors=ancestors
            )

        if source_element and not in_svg:
            if element.tag == "head":
                direct = isinstance(parent, turbohtml.Element) and parent.tag == "html"
                self.head_elements.append(
                    (line, direct and document._source_element(parent))
                )
            elif element.tag == "main":
                direct = isinstance(parent, turbohtml.Element) and parent.tag == "body"
                self.main_elements.append(
                    (line, direct and document._source_element(parent))
                )

        next_ancestors = (*ancestors, element.tag)
        if in_svg:
            for child in element.children:
                if isinstance(child, turbohtml.Element):
                    self._visit(child, output, ancestors=next_ancestors, in_svg=True)
            return

        if source_element and element.tag == "svg":
            location = element.source_location
            end = location.end_tag or location.start_tag
            markup = document._source[
                document._source_index(
                    location.start_tag.start_line, location.start_tag.start_col
                ) : document._source_index(end.end_line, end.end_col)
            ]
            node = {
                "tag": element.tag,
                "attrs": attrs,
                "line": line,
                "column": column + 1,
                "content": [],
                "markup": markup,
            }
            output.append(node)
            self.nodes.append(node)
            for child in element.children:
                if isinstance(child, turbohtml.Element):
                    self._visit(child, output, ancestors=next_ancestors, in_svg=True)
            return

        child_output = output
        if not skip_implied:
            node = {
                "tag": element.tag,
                "attrs": attrs,
                "line": line,
                "column": column + 1,
                "content": [],
            }
            output.append(node)
            self.nodes.append(node)
            child_output = node["content"]
            if record is not None:
                self._nodes_of[id(record)] = node

            if element.tag in POINTABLE_TAGS | PROSE_TAGS and not attrs.get("id"):
                under = next(
                    (
                        (ancestor.tag, element_attrs(ancestor)["id"])
                        for ancestor in element.ancestors
                        if isinstance(ancestor, turbohtml.Element)
                        and element_attrs(ancestor).get("id")
                    ),
                    None,
                )
                self.bare_blocks.append(
                    {"tag": element.tag, "line": line, "under": under}
                )

        for child in element.children:
            if isinstance(child, turbohtml.Element):
                self._visit(child, child_output, ancestors=next_ancestors)
            elif isinstance(child, turbohtml.Text):
                child_output.append(child.data)
                if (
                    child.data.strip()
                    and "main" not in next_ancestors
                    and element.tag in DOCUMENT_WRAPPERS
                ):
                    self.outside_main.append(
                        {"tag": element.tag, "line": line, "text": True}
                    )

        if element.tag == "template" and "data-sample" in attrs and not attrs.get("id"):
            self.errors.append(Finding("unnamed-sample", "<template>", {"line": line}))

        if element.tag == "style":
            self.style_blocks.append(
                {"css": element.text, "line": line, "attrs": attrs}
            )
        elif element.tag == "title":
            self.title += element.text


def rel_tokens(attrs: dict) -> frozenset[str]:
    """The case-insensitive token set carried by one parsed ``rel`` attribute."""
    value = attrs.get("rel") or []
    tokens = value.split() if isinstance(value, str) else value
    return frozenset(token.lower() for token in tokens)


def links_with_rel(links: list[dict], rel: str) -> list[dict]:
    """The indexed links declaring one relation. `rel` carries a space-separated
    token list, so a relation is a token in it rather than a substring of it."""
    return [link for link in links if rel.lower() in rel_tokens(link["attrs"])]


def annotation_mode(document: SourceDocument) -> str:
    """The document's selected annotation presentation; omission keeps the overlay.

    This is immutable boot configuration, distinct from the tab's current annotation
    visibility. A revision that changes it replaces the executable document lifetime.
    """
    body = document.tree.select_one("body")
    return element_attrs(body).get("data-annotations", "overlay") if body else "overlay"


def page_layout(document: SourceDocument, registry: Mapping):
    """The `layout-` names the document's `main` and the boxes under it that can be its
    Layout's carry (`layout-column` is `column`), space-separated, or None.

    A page Layout's class is on `main`, on a shown child of a `main` that carries none,
    or on the child of each part of such a `main`'s parts (`x-views: "parts"`,
    layouts.css, `--lf-layout-box`). The parser reaches those after it has begun
    painting the body, so delivery repeats them on the root for the Layout's own body
    rules to read before the first paint. Which part opens is the browser's, so every
    part's names go across. A child the page hides is not the page's shape, so its names
    stay off. Every other name goes across, since a block's own (`layout-tiles`) can
    stand beside the page's and the body rules read only the page Layouts' names."""
    main = document.tree.select_one("body > main")
    if main is None:
        return None

    def shown(parent):
        return [
            child
            for child in parent.children
            if isinstance(child, turbohtml.Element) and "hidden" not in child.attrs
        ]

    def carried(box):
        return [
            token.removeprefix("layout-")
            for token in box.attrs.get("class", [])
            if token.startswith("layout-")
        ]

    boxes = [main, *shown(main)]
    if not carried(main):
        boxes += [
            child
            for holder in shown(main)
            if registry.get(holder.tag, {}).get("x-views") == "parts"
            for part in shown(holder)
            for child in shown(part)
        ]
    names = []
    for box in boxes:
        for name in carried(box):
            if name not in names:
                names.append(name)
    return " ".join(names) or None
