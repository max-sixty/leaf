"""Structural readings of authored HTML."""

import re
from html.parser import HTMLParser
from pathlib import Path

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
    "caption",
    "colgroup",
    "rp",
    "rt",
    "html",
    "head",
    "body",
}
# A start tag on the left implicitly closes matching open elements on the right.
P_CLOSERS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "details",
    "div",
    "dl",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hgroup",
    "hr",
    "main",
    "menu",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "ul",
}
# …and closes its own kind: a start tag ends the open siblings it can't nest inside.
SIBLING_CLOSERS = {
    "li": ("li",),
    "dt": ("dt", "dd"),
    "dd": ("dt", "dd"),
    "td": ("td", "th"),
    "th": ("td", "th"),
    "tr": ("td", "th", "tr"),
    "thead": ("td", "th", "tr", "thead", "tbody", "tfoot"),
    "tbody": ("td", "th", "tr", "thead", "tbody", "tfoot"),
    "tfoot": ("td", "th", "tr", "thead", "tbody", "tfoot"),
    "option": ("option",),
    "optgroup": ("option", "optgroup"),
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


def implicit_closes(open_tags: list, tag: str) -> int:
    """How many elements at the top of an open-element stack this start tag closes,
    under HTML's optional-end-tag rules. Two parsers walk the same documents — the
    structure lint and the passage reader — and `version check` accepts an omitted
    </p>, so a tree they disagreed about would be a passage one of them puts in the
    wrong section."""
    closed = 0
    if tag in P_CLOSERS:
        while closed < len(open_tags) and open_tags[-1 - closed] == "p":
            closed += 1
    siblings = SIBLING_CLOSERS.get(tag, ())
    while closed < len(open_tags) and open_tags[-1 - closed] in siblings:
        closed += 1
    return closed


class StructParser(HTMLParser):
    """Tracks a tag stack to catch unclosed and mismatched tags, and collects what the
    rest of `version check` reads off a version: element ids and the widget each
    stands in, every <script src> tag, stylesheet links, each lf-* element
    (attributes, direct parent, direct content order, direct children, direct text)
    for registry validation, the page's title, and everything it says about width.
    Structure only — no tag here is known by name, so every question about what a
    widget *means* is asked of the registry by whoever holds one. Foreign markup
    inside <svg> is skipped (SVG has its own self-closing rules that don't matter
    here)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []  # (tag, lineno, lf_record | None, id | None)
        self.errors = []
        self.all_ids = []
        # {attrs, parent, position, early_head} per external asset. Applicability and
        # placement belong to the asset record: parallel lists made one fact several
        # representations and let a later parser edit silently misalign them.
        self.external_scripts = []
        self.stylesheets = []
        self.lf_metas = []  # {"name", "content", "line"} for <meta name="lf-*">
        self.http_equivs = []  # {"equiv", "content", "line"} per http-equiv meta
        # The authored page lives under one direct body > main because that is the
        # element the first-replay presentation boundary withholds. Both assets that
        # establish that boundary belong in head; anything paintable outside main would
        # stand outside it.
        self.body_lines = []
        self.head_elements = []  # (line, direct child of html)
        self.main_elements = []  # (line, direct child of body)
        self.outside_main = []  # paintable content with no main ancestor
        # /media/ paths any attribute points at, so the check that the file is
        # there reads references and not mentions: a page documenting leaf
        # writes one of these paths in prose, and a raw scan of the markup
        # would send its author hunting for a screenshot nothing asks for.
        self.media_refs = set()
        # What the version says about width, each where a document says it: CSS is
        # what a <style> block holds, and a fixed width is what a rule, a style="" or
        # a width="" states. The column check reads these three and nothing else.
        self.css = ""
        self.inline_styles = []  # each style="" declaration list
        self.attr_widths = []  # (tag, value) per width="" that counts as pixels
        self.title = ""  # what <title> says, for the transcript's heading
        # {"tag", "line", "attrs", "parent", "direct", "children", "text"}
        self.lf_elements = []
        # id → the innermost lf-* element standing around it, an element's own id
        # standing in itself. Where an id lives is structure; which of those
        # elements is a slot a decision retires and which the widget holding it is
        # the registry's word, read by whoever has one (`retirement_holders`), so
        # what a version's outcome licenses is worked out without this parse
        # knowing a widget by name.
        self.within = {}
        # {"tag", "parent", "lang", "line"} per element claiming a language — the
        # coloring the runtime honors on a plain <pre><code>, checked here because a
        # class it doesn't honor is a request that silently isn't answered.
        self.language_blocks = []
        # {"tag", "line", "under"} per id-less occurrence of a pointable block,
        # with the nearest open ancestor carrying an id — (tag, id) or None — so
        # unpointable_blocks can judge where a user's aim would land.
        self.bare_blocks = []
        # (tag, line, markers) per element wearing the runtime's own record: a
        # data-lf-* attribute, or a class in the runtime's own lf- namespace.
        # All three reserve by prefix, as an id does, because the runtime coins
        # names in that namespace as it grows and a page may not author what the
        # runtime reads back as its own record: words inside .lf-chrome leave
        # the reading position and every quote, .lf-quiet clips them to a point
        # nobody can see or select, and data-lf-gen words become fenced cells
        # the file's reading has no fence for. Naming the classes it coins today
        # is a list that goes on admitting the next one it coins.
        self.reserved_markers = []
        self._svg_depth = 0
        # The same parse retains ordinary HTML, exact text, and construction
        # locations for inspection. Widget validation keeps its specialized index;
        # content is one tree, with no parent objects or reconstructed HTML.
        self.content = []
        self.nodes = []
        self._nodes_at_depth = {}
        self._source = ""
        self._svg_source = None

    def feed(self, data):
        self._source += data
        super().feed(data)

    def _source_offset(self):
        line, column = self.getpos()
        return (
            sum(len(part) + 1 for part in self._source.split("\n")[: line - 1]) + column
        )

    def _content_node(self, tag, attrs, *, push=True):
        parent = self._nodes_at_depth.get(len(self.stack) - 1)
        node = {
            "tag": tag,
            "attrs": dict(attrs),
            "line": self.getpos()[0],
            "column": self.getpos()[1] + 1,
            "content": [],
        }
        (parent["content"] if parent is not None else self.content).append(node)
        self.nodes.append(node)
        if push:
            self._nodes_at_depth[len(self.stack)] = node
        return node

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

    def _implicit_close(self, tag):
        for _ in range(implicit_closes([t for t, *_ in self.stack], tag)):
            self.stack.pop()

    def _open_widget(self):
        """The innermost lf-* element still open, or None outside every one."""
        return next(
            (record for _, _, record, _ in reversed(self.stack) if record), None
        )

    def _harvest(self, tag, attrs_d):
        if attrs_d.get("id"):
            self.all_ids.append(attrs_d["id"])
            # An lf-* element's own id stands in the element itself, which
            # handle_starttag writes over this the moment the record exists.
            self.within[attrs_d["id"]] = self._open_widget()
        if tag == "script" and attrs_d.get("src"):
            self.external_scripts.append(
                {
                    "attrs": attrs_d,
                    "parent": self.stack[-1][0] if self.stack else None,
                    "position": self.getpos(),
                    "early_head": bool(self.head_elements)
                    and self.head_elements[-1][1]
                    and not self.body_lines,
                }
            )
        if tag == "link" and "stylesheet" in (attrs_d.get("rel") or ""):
            self.stylesheets.append(
                {
                    "attrs": attrs_d,
                    "parent": self.stack[-1][0] if self.stack else None,
                    "early_head": bool(self.head_elements)
                    and self.head_elements[-1][1]
                    and not self.body_lines,
                }
            )
        if tag == "meta" and (attrs_d.get("name") or "").startswith("lf-"):
            self.lf_metas.append(
                {
                    "name": attrs_d["name"],
                    "content": attrs_d.get("content"),
                    "line": self.getpos()[0],
                }
            )
        if tag == "meta" and attrs_d.get("http-equiv"):
            self.http_equivs.append(
                {
                    "equiv": attrs_d["http-equiv"],
                    "content": attrs_d.get("content"),
                    "line": self.getpos()[0],
                    "position": self.getpos(),
                    "raw": self.get_starttag_text(),
                }
            )
        if attrs_d.get("style"):
            self.inline_styles.append(attrs_d["style"])
        if tag in PIXEL_WIDTH_TAGS and attrs_d.get("width"):
            self.attr_widths.append((tag, attrs_d["width"]))
        markers = sorted(name for name in attrs_d if name.startswith("data-lf-"))
        markers += sorted(
            c for c in (attrs_d.get("class") or "").split() if c.startswith("lf-")
        )
        if markers:
            self.reserved_markers.append((tag, self.getpos()[0], markers))
        self.media_refs.update(
            v for v in attrs_d.values() if v and v.startswith(f"/{MEDIA_DIR}/")
        )

    def _attributes(self, tag, attrs):
        """The browser's attribute reading: first value wins, duplicates are invalid."""
        values = {}
        duplicates = set()
        for name, value in attrs:
            if name in values:
                duplicates.add(name)
            else:
                values[name] = value
        if duplicates:
            self.errors.append(
                f"<{tag}> at line {self.getpos()[0]} has duplicate attribute "
                f"names {sorted(duplicates)}; HTML keeps the first value"
            )
        return values

    def _record_outside_main(self, tag):
        """Record markup Chrome can paint without crossing the authored main."""
        ancestors = {open_tag for open_tag, *_ in self.stack}
        if "main" in ancestors or tag in DOCUMENT_WRAPPERS:
            return
        if "head" in ancestors and tag in HEAD_METADATA_TAGS:
            return
        self.outside_main.append(f"<{tag}> at line {self.getpos()[0]}")

    def handle_starttag(self, tag, attrs):
        attrs_d = self._attributes(tag, attrs)
        # The browser renders neither: template content parses into an inert
        # fragment and noscript stays text in any scripting browser, while the
        # file's reading would take both for the page's words — so a comment
        # could anchor on words no reader ever sees. Nothing in the vocabulary
        # has a use for markup the page won't render; refuse it at the door
        # instead of teaching every reading to look away.
        if tag in ("template", "noscript"):
            self.errors.append(
                f"<{tag}> at line {self.getpos()[0]}: the browser renders none of "
                "its content; write it plainly or leave it out"
            )
        self._harvest(tag, attrs_d)
        if tag == "svg":
            self._record_outside_main(tag)
            if not self._svg_depth:
                self._svg_source = (
                    self._content_node(tag, attrs_d),
                    self._source_offset(),
                )
            self._svg_depth += 1
            self.stack.append((tag, self.getpos()[0], None, attrs_d.get("id")))
            return
        if self._svg_depth:  # don't tag-balance inside SVG
            return
        # Before the void check: <hr> is void and closes an open <p>, and a void tag
        # left inside a paragraph it ended puts the rest of the section in it.
        self._implicit_close(tag)
        self._content_node(tag, attrs_d, push=tag not in VOID_TAGS)
        parent = self.stack[-1][0] if self.stack else None
        if tag == "head":
            self.head_elements.append((self.getpos()[0], parent == "html"))
        if tag == "body":
            self.body_lines.append(self.getpos()[0])
        if tag == "main":
            self.main_elements.append((self.getpos()[0], parent == "body"))
        self._record_outside_main(tag)
        # After it, so the parent recorded here is the one the browser will see.
        lang = LANGUAGE_CLASS.search(attrs_d.get("class") or "")
        if lang:
            self.language_blocks.append(
                {
                    "tag": tag,
                    "parent": self.stack[-1][0] if self.stack else None,
                    "lang": lang.group(1),
                    "line": self.getpos()[0],
                }
            )
        if tag in POINTABLE_TAGS and not attrs_d.get("id"):
            self.bare_blocks.append(
                {
                    "tag": tag,
                    "line": self.getpos()[0],
                    "under": next(
                        ((t, i) for t, _, _, i in reversed(self.stack) if i), None
                    ),
                }
            )
        if tag in VOID_TAGS:
            if self.stack and self.stack[-1][2] is not None:
                self.stack[-1][2]["children"].append(tag)
                self.stack[-1][2]["direct"].append(tag)
            return
        if self.stack and self.stack[-1][2] is not None:
            self.stack[-1][2]["children"].append(tag)
            self.stack[-1][2]["direct"].append(tag)
        record = None
        if tag.startswith("lf-"):
            record = {
                "tag": tag,
                "line": self.getpos()[0],
                "attrs": attrs_d,
                "parent": self.stack[-1][0] if self.stack else None,
                "direct": [],
                "children": [],
                "text": False,
                "body": "",  # a <pre> data body's text, for the x-lines gate
                # The nearest enclosing lf element's record, so a child's line
                # reference (x-lines) can find the data body it points into, and
                # so a reading with the registry to hand can walk out of a slot
                # to the widget whose decision retires it.
                "holder": self._open_widget(),
            }
            self.lf_elements.append(record)
            if attrs_d.get("id"):
                self.within[attrs_d["id"]] = record
        self.stack.append((tag, self.getpos()[0], record, attrs_d.get("id")))

    def handle_startendtag(self, tag, attrs):
        # <foo/> — self-closing; still harvest but never pushed. Outside SVG the
        # slash is a trap on any non-void tag: HTML ignores it, the element stays
        # open in a browser and swallows the rest of its parent, so from here on
        # this parser's tree and the browser's would diverge. Reject the form
        # outright rather than model a tree the user's page won't have.
        attrs_d = self._attributes(tag, attrs)
        self._harvest(tag, attrs_d)
        if self._svg_depth:  # SVG has real self-closing syntax
            return
        self._implicit_close(tag)
        self._content_node(tag, attrs_d, push=False)
        self._record_outside_main(tag)
        if tag not in VOID_TAGS:
            self.errors.append(
                f"<{tag}/> at line {self.getpos()[0]} is self-closing: HTML ignores "
                f"the slash and the element would swallow what follows — write "
                f"<{tag} …></{tag}>"
            )
        elif self.stack and self.stack[-1][2] is not None:
            self.stack[-1][2]["children"].append(tag)
            self.stack[-1][2]["direct"].append(tag)

    def handle_data(self, data):
        node = self._nodes_at_depth.get(len(self.stack) - 1)
        if not self._svg_depth:
            (node["content"] if node is not None else self.content).append(data)
        ancestors = {open_tag for open_tag, *_ in self.stack}
        holder = self.stack[-1][0] if self.stack else None
        if (
            data.strip()
            and "main" not in ancestors
            and holder not in {"script", "style", "title"}
        ):
            self.outside_main.append(f"text at line {self.getpos()[0]}")
        if self.stack and self.stack[-1][2] is not None and data.strip():
            self.stack[-1][2]["text"] = True
            self.stack[-1][2]["direct"].append("#text")
        if holder == "style":
            self.css += data
        elif holder == "title":
            self.title += data
        elif holder == "pre" and len(self.stack) > 1 and self.stack[-2][2] is not None:
            # A data body: the <pre> directly under an lf element, collected for
            # the x-lines gate to count lines against.
            self.stack[-2][2]["body"] += data

    def handle_endtag(self, tag):
        if tag == "svg":
            while self.stack and self.stack[-1][0] != "svg":
                self.stack.pop()
            if self.stack:
                self.stack.pop()
            self._svg_depth = max(0, self._svg_depth - 1)
            if not self._svg_depth and self._svg_source is not None:
                # Keep foreign markup as exact source. SVG and foreignObject
                # have their own structure rules; the HTML reading exposes the
                # construction without inventing a second rendering of it.
                node, start = self._svg_source
                end = self._source.index(">", self._source_offset()) + 1
                node["markup"] = self._source[start:end]
                self._svg_source = None
            return
        if self._svg_depth or tag in VOID_TAGS:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                orphaned = [
                    (t, ln)
                    for t, ln, *_ in self.stack[i + 1 :]
                    if t not in OPTIONAL_END
                ]
                if orphaned:
                    unclosed = ", ".join(f"<{t}> (line {ln})" for t, ln in orphaned)
                    self.errors.append(
                        f"</{tag}> at line {self.getpos()[0]} closes over unclosed: {unclosed}"
                    )
                del self.stack[i:]
                return
        if tag not in OPTIONAL_END:
            self.errors.append(
                f"stray </{tag}> at line {self.getpos()[0]} with no matching open tag"
            )


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
