"""Structural readings of authored HTML."""

import re
from pathlib import Path

import turbohtml

from .files import file_stamp, revision_path
from .schema import MEDIA_DIR

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
    "colgroup",
    "rp",
    "rt",
    "html",
    "head",
    "body",
}
# How a plain code block names its language, matching leaf.js's own pattern. The
# class is the universal one every Markdown renderer emits, so a block Claude wrote
# elsewhere lands here unchanged.
LANGUAGE_CLASS = re.compile(r"(?:^|\s)language-([\w+.#-]+)(?=\s|$)")

# Attribute widths only count as pixels on these elements.
PIXEL_WIDTH_TAGS = {"img", "svg", "table", "canvas", "iframe", "video", "object"}

# Blocks a user predictably points at whole rather than quoting: a run of code,
# a table, a figure, an aside set off from the prose — and the sections
# references/page-authoring.md holds to "Stable anchors". Widgets aren't listed
# because the
# registry's schemas already demand ids wherever pointing at one matters.
POINTABLE_TAGS = {"section", "article", "aside", "pre", "table", "figure"}
# Where an aim that found no tighter id has escaped to: naming one of these is
# naming most of the page.
SECTIONING_TAGS = {"section", "article", "main", "body"}
# The headings an outline of the page lists. h1 names the page, so it heads that
# outline rather than standing in it. The outline widget selects the same set in the
# browser (its own HEADING_SELECTOR).
HEADING_TAGS = {"h2", "h3", "h4", "h5", "h6"}
# The properties that overflow a column when pinned in pixels. max-width defines the
# column instead, so it is read there and never counted here.
OVERFLOW_PROPS = ("width", "min-width")
# Page-level declarations the runtime reads from <meta name="lf-*"> in the head,
# name → allowed content values (None = free-form). A misspelled name or value
# would silently declare nothing in the browser, so `version check` owns this
# vocabulary the way the registry owns lf-* elements.
LF_META = {"lf-review": frozenset({"sign-off"})}
# The one CSP every page declares, required by `version check` the way the one
# script tag is. The vendoring promise — an approved page can't change under its
# user, and can't phone home — held by convention until the browser enforced it:
# a vendored module or an inline handler could fetch any origin. 'self' is the
# page directory whole; base-uri and form-action need their own directives because
# default-src governs only fetches. data: admits the images `version export` inlines;
# the theme arrives inline in a <style> on export, hence 'unsafe-inline' for styles
# (scripts stay 'self'-only). Verified over the corpus — every widget, diagram
# renderer and tokenizer included — before it was required.
PAGE_CSP = (
    "default-src 'self'; base-uri 'none'; form-action 'none'; "
    "img-src 'self' data:; style-src 'self' 'unsafe-inline'"
)
# A meta policy cannot govern the document's ancestors. The ordinary server adds this
# separate header policy; the capability-scoped MCP transport is deliberately frameable.
FRAME_ANCESTORS_CSP = "frame-ancestors 'none'"
# Non-painting document structure that may stand outside the authored main. Head
# metadata is allowed only while the parser is actually inside head; the canonical
# module is also allowed beside main because shipped pages use both placements.
DOCUMENT_WRAPPERS = {"html", "head", "body", "main"}
HEAD_METADATA_TAGS = {"base", "link", "meta", "script", "style", "title"}


class StructParser:
    """One browser-compatible structural reading of authored HTML.

    TurboHTML owns HTML recovery and source locations. This class retains Leaf's
    authoring-specific indexes and its stricter errors for ambiguous source constructs;
    it does not maintain a second element stack or tree-building grammar.
    """

    def __init__(self):
        self.errors = []
        self.unclosed = []  # source elements whose required end tag is absent
        self.all_ids = []
        self.external_scripts = []
        self.stylesheets = []
        self.lf_metas = []
        self.http_equivs = []
        self.body_lines = []
        self.head_elements = []
        self.main_elements = []
        self.outside_main = []
        self.media_refs = set()
        self.css = ""
        self.inline_styles = []
        self.attr_widths = []
        self.title = ""
        self.lf_elements = []
        self.within = {}
        self.language_blocks = []
        self.bare_blocks = []
        self.reserved_markers = []
        self.content = []
        self.nodes = []
        self.document = None
        self._source = ""
        self._line_offsets = [0]
        self._first_body_position = None
        self._closed = False

    def feed(self, data):
        if self._closed:
            raise ValueError("cannot feed a closed structural parser")
        self._source += data

    @staticmethod
    def _attrs(element) -> dict:
        return {
            name: " ".join(value) if isinstance(value, list) else value
            for name, value in element.attrs.items()
        }

    @staticmethod
    def _position(element) -> tuple[int, int]:
        current = element
        while current is not None:
            if current.position is not None:
                return current.position
            current = current.parent
        return (1, 0)

    def _span_source(self, span) -> str:
        return self._source[
            self._line_offsets[span.start_line - 1]
            + span.start_col : self._line_offsets[span.end_line - 1] + span.end_col
        ]

    @staticmethod
    def _source_element(element) -> bool:
        return element.source_location is not None

    def _source_errors(self) -> None:
        tokens = list(turbohtml.tokenize(self._source, capture_source=True))
        body_starts = [
            token
            for token in tokens
            if token.type is turbohtml.TokenType.START_TAG and token.tag == "body"
        ]
        self.body_lines = [token.line for token in body_starts]
        self._first_body_position = (
            (body_starts[0].line, body_starts[0].col) if body_starts else None
        )
        starts = {
            (token.line, token.col): token
            for token in tokens
            if token.type is turbohtml.TokenType.START_TAG
        }
        recognized_ends = set()
        for element in self.document.descendants:
            if not isinstance(element, turbohtml.Element):
                continue
            location = element.source_location
            if location is None:
                continue
            if location.end_tag is not None:
                recognized_ends.add(
                    (location.end_tag.start_line, location.end_tag.start_col)
                )
                continue
            start_source = self._span_source(location.start_tag).rstrip()
            if (
                element.namespace is turbohtml.Namespace.HTML
                and element.tag not in VOID_TAGS | OPTIONAL_END
                and not start_source.endswith("/>")
            ):
                self.unclosed.append((element.tag, element.source_line))

        for token in tokens:
            if (
                token.type is turbohtml.TokenType.END_TAG
                and token.tag not in VOID_TAGS | OPTIONAL_END
                and (token.line, token.col) not in recognized_ends
            ):
                self.errors.append(
                    f"stray </{token.tag}> at line {token.line} with no matching open tag"
                )

        for error in self.document.errors:
            if error.code == "duplicate-attribute":
                self.errors.append(
                    f"duplicate attribute at line {error.line}; HTML keeps the first value"
                )
            elif error.code == "non-void-html-element-start-tag-with-trailing-solidus":
                token = starts.get((error.line, error.col))
                tag = token.tag if token is not None else "element"
                self.errors.append(
                    f"<{tag}/> at line {error.line} is self-closing: HTML ignores the "
                    f"slash and the element would swallow what follows — write "
                    f"<{tag} …></{tag}>"
                )

    def _record_element(
        self,
        element,
        attrs: dict,
        *,
        parent_tag: str | None,
        ancestors: tuple,
        holder: dict | None,
    ) -> dict | None:
        tag = element.tag
        line, column = self._position(element)
        before_body = (
            self._first_body_position is None
            or (
                line,
                column,
            )
            < self._first_body_position
        )
        identity = attrs.get("id")
        if identity:
            self.all_ids.append(identity)
            self.within[identity] = holder

        in_head = "head" in ancestors
        in_main = "main" in ancestors
        if tag == "script" and attrs.get("src"):
            self.external_scripts.append(
                {
                    "attrs": attrs,
                    "parent": parent_tag,
                    "position": (line, column),
                    "early_head": in_head and before_body,
                }
            )
        if tag == "link" and "stylesheet" in (attrs.get("rel") or ""):
            self.stylesheets.append(
                {
                    "attrs": attrs,
                    "parent": parent_tag,
                    "early_head": in_head and before_body,
                }
            )
        if tag == "meta" and (attrs.get("name") or "").startswith("lf-"):
            self.lf_metas.append(
                {"name": attrs["name"], "content": attrs.get("content"), "line": line}
            )
        if tag == "meta" and attrs.get("http-equiv"):
            location = element.source_location
            self.http_equivs.append(
                {
                    "equiv": attrs["http-equiv"],
                    "content": attrs.get("content"),
                    "line": line,
                    "position": (line, column),
                    "raw": self._span_source(location.start_tag),
                }
            )
        if attrs.get("style"):
            self.inline_styles.append(attrs["style"])
        if tag in PIXEL_WIDTH_TAGS and attrs.get("width"):
            self.attr_widths.append((tag, attrs["width"]))
        markers = sorted(name for name in attrs if name.startswith("data-lf-"))
        markers += sorted(
            name
            for name in (attrs.get("class") or "").split()
            if name.startswith("lf-")
        )
        if markers:
            self.reserved_markers.append((tag, line, markers))
        self.media_refs.update(
            value
            for value in attrs.values()
            if isinstance(value, str) and value.startswith(f"/{MEDIA_DIR}/")
        )

        if tag in ("template", "noscript"):
            self.errors.append(
                f"<{tag}> at line {line}: the browser renders none of its content; "
                "write it plainly or leave it out"
            )
        if (
            not in_main
            and tag not in DOCUMENT_WRAPPERS
            and not (in_head and tag in HEAD_METADATA_TAGS)
        ):
            self.outside_main.append(f"<{tag}> at line {line}")

        if tag.startswith("lf-"):
            record = {
                "tag": tag,
                "line": line,
                "attrs": attrs,
                "parent": parent_tag,
                "direct": [],
                "children": [],
                "text": False,
                "body": "",
                "holder": holder,
            }
            self.lf_elements.append(record)
            if identity:
                self.within[identity] = record
            return record
        return None

    def _visit(
        self,
        element,
        output: list,
        *,
        ancestors: tuple = (),
        holder: dict | None = None,
        in_svg: bool = False,
    ) -> None:
        source_element = self._source_element(element)
        skip_implied = not source_element
        parent = element.parent
        parent_tag = parent.tag if isinstance(parent, turbohtml.Element) else None
        attrs = self._attrs(element)
        line, column = self._position(element)

        record = None
        if source_element:
            record = self._record_element(
                element,
                attrs,
                parent_tag=parent_tag,
                ancestors=ancestors,
                holder=holder,
            )

        if source_element and not in_svg:
            if element.tag == "head":
                direct = isinstance(parent, turbohtml.Element) and parent.tag == "html"
                self.head_elements.append(
                    (line, direct and self._source_element(parent))
                )
            elif element.tag == "main":
                direct = isinstance(parent, turbohtml.Element) and parent.tag == "body"
                self.main_elements.append(
                    (line, direct and self._source_element(parent))
                )

        next_ancestors = (*ancestors, element.tag)
        if in_svg:
            for child in element.children:
                if isinstance(child, turbohtml.Element):
                    self._visit(
                        child,
                        output,
                        ancestors=next_ancestors,
                        holder=holder,
                        in_svg=True,
                    )
            return

        if source_element and element.tag == "svg":
            location = element.source_location
            end = location.end_tag or location.start_tag
            markup = self._source[
                self._line_offsets[location.start_tag.start_line - 1]
                + location.start_tag.start_col : self._line_offsets[end.end_line - 1]
                + end.end_col
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
                    self._visit(
                        child,
                        output,
                        ancestors=next_ancestors,
                        holder=holder,
                        in_svg=True,
                    )
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

            language = LANGUAGE_CLASS.search(attrs.get("class") or "")
            if language:
                self.language_blocks.append(
                    {
                        "tag": element.tag,
                        "parent": parent_tag,
                        "lang": language.group(1),
                        "line": line,
                    }
                )
            if element.tag in POINTABLE_TAGS and not attrs.get("id"):
                under = next(
                    (
                        (ancestor.tag, self._attrs(ancestor)["id"])
                        for ancestor in element.ancestors
                        if isinstance(ancestor, turbohtml.Element)
                        and self._attrs(ancestor).get("id")
                    ),
                    None,
                )
                self.bare_blocks.append(
                    {"tag": element.tag, "line": line, "under": under}
                )

        next_holder = record or holder
        if record is not None:
            for child in element.children:
                if isinstance(child, turbohtml.Element):
                    record["children"].append(child.tag)
                    record["direct"].append(child.tag)
                elif isinstance(child, turbohtml.Text) and child.data.strip():
                    record["text"] = True
                    record["direct"].append("#text")
            pre = next(
                (
                    child
                    for child in element.children
                    if isinstance(child, turbohtml.Element) and child.tag == "pre"
                ),
                None,
            )
            if pre is not None:
                record["body"] = "".join(
                    child.data
                    for child in pre.children
                    if isinstance(child, turbohtml.Text)
                )

        for child in element.children:
            if isinstance(child, turbohtml.Element):
                self._visit(
                    child,
                    child_output,
                    ancestors=next_ancestors,
                    holder=next_holder,
                )
            elif isinstance(child, turbohtml.Text):
                child_output.append(child.data)
                if (
                    child.data.strip()
                    and "main" not in next_ancestors
                    and element.tag not in {"script", "style", "title"}
                ):
                    self.outside_main.append(f"text at line {line}")

        if element.tag == "style":
            self.css += element.text
        elif element.tag == "title":
            self.title += element.text

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._line_offsets.extend(
            match.end() for match in re.finditer(r"\r\n?|\n", self._source)
        )
        self.document = turbohtml.parse(
            self._source, scripting=True, source_locations=True
        )
        self._source_errors()
        for child in self.document.children:
            if isinstance(child, turbohtml.Element):
                self._visit(child, self.content)

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
        standing report — the agent channel's mirror of `restated`."""
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
        """Ids that trespass on the runtime's own namespace (see reserved_ids_error)."""
        return sorted({i for i in self.all_ids if i.startswith("lf-")})


def parse_structure(markup: str) -> StructParser:
    """One structural reading of a document or fragment — fed and closed, so
    every reader gets the flushed parse rather than each restating the ritual."""
    parser = StructParser()
    parser.feed(markup)
    parser.close()
    return parser


_revisions = {}  # revision file -> (its stamp, the structural reading of it)


def parse_revision(page_dir: Path, revision: int) -> StructParser:
    """One cached structural reading of an immutable working revision."""
    path = revision_path(page_dir, revision)
    stamp = file_stamp(path)
    if stamp and (held := _revisions.get(path)) and held[0] == stamp:
        return held[1]
    parser = parse_structure(path.read_text(encoding="utf-8"))
    if stamp:
        _revisions[path] = (stamp, parser)
    return parser


def revision_review_mode(page_dir: Path, revision: int):
    """The review decision declared by an exact working revision, or None."""
    parser = parse_revision(page_dir, revision)
    return next(
        (meta["content"] for meta in parser.lf_metas if meta["name"] == "lf-review"),
        None,
    )
