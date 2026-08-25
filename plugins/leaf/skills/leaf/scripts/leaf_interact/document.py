"""Static HTML, passage, and CSS readings of an authored page."""

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple

import tinycss2

from .files import file_stamp, version_path
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

# Container selectors whose max-width defines the readable column.
COLUMN_SELECTORS = (
    "main",
    "body",
    "article",
    ".container",
    ".wrap",
    ".content",
    ".page",
)


def _names_column(selector: str) -> bool:
    """Whether a rule's selector names one of the column containers — as a selector
    component, not a substring. Matched as text, `.domain-list` contained "main" and
    one unrelated rule redefined the column every element was measured against; a
    component is the word standing as the compound's type selector or as a whole
    class, with nothing of an identifier continuing it."""
    for part in re.split(r"[,\s>+~]+", selector):
        for sel in COLUMN_SELECTORS:
            if sel.startswith("."):
                if re.search(rf"{re.escape(sel)}(?![\w-])", part):
                    return True
            elif re.match(rf"{sel}(?![\w-])", part):
                return True
    return False


COLUMN_FALLBACK = 780
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
# page directory whole; data: admits the images `version export` inlines; the
# theme arrives inline in a <style> on export, hence 'unsafe-inline' for styles
# (scripts stay 'self'-only, which is what matters). Verified over the gallery —
# every widget, mermaid and the tokenizer included — before it was required.
PAGE_CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
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


class _StructParser(HTMLParser):
    """Tracks a tag stack to catch unclosed and mismatched tags, and collects what the
    rest of `version check` reads off a version: element ids and the widget each
    stands in, every <script src> tag, stylesheet links, each lf-* element
    (attributes, direct parent, direct children, direct text) for registry
    validation, the page's title, and everything it says about width. Structure
    only — no tag here is known by name, so every question about what a widget
    *means* is asked of the registry by whoever holds one. Foreign markup inside
    <svg> is skipped (SVG has its own self-closing rules that don't matter here)."""

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
        # {"tag", "line", "attrs", "parent", "children", "text"}
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
        # (tag, line, markers) per element wearing the runtime's own record:
        # a data-lf-* attribute, or one of the classes that answer "which
        # document is this" (.lf-chrome), "this is the live region" (.lf-live),
        # "this is a copy" (.lf-copy). The runtime writes these and reads them
        # back, so an authored copy makes it misread the page it stands on —
        # authored words inside .lf-chrome leave the reading position and every
        # quote, and data-lf-gen words become fenced cells the file's reading
        # has no fence for.
        self.reserved_markers = []
        self._svg_depth = 0

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
                }
            )
        if attrs_d.get("style"):
            self.inline_styles.append(attrs_d["style"])
        if tag in PIXEL_WIDTH_TAGS and attrs_d.get("width"):
            self.attr_widths.append((tag, attrs_d["width"]))
        markers = sorted(name for name in attrs_d if name.startswith("data-lf-"))
        markers += sorted(
            {"lf-chrome", "lf-live", "lf-copy", "lf-ui"}
            & set((attrs_d.get("class") or "").split())
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
            self._svg_depth += 1
            self.stack.append((tag, self.getpos()[0], None, attrs_d.get("id")))
            return
        if self._svg_depth:  # don't tag-balance inside SVG
            return
        # Before the void check: <hr> is void and closes an open <p>, and a void tag
        # left inside a paragraph it ended puts the rest of the section in it.
        self._implicit_close(tag)
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
            return
        if self.stack and self.stack[-1][2] is not None:
            self.stack[-1][2]["children"].append(tag)
        record = None
        if tag.startswith("lf-"):
            record = {
                "tag": tag,
                "line": self.getpos()[0],
                "attrs": attrs_d,
                "parent": self.stack[-1][0] if self.stack else None,
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
        self._record_outside_main(tag)
        if tag not in VOID_TAGS:
            self.errors.append(
                f"<{tag}/> at line {self.getpos()[0]} is self-closing: HTML ignores "
                f"the slash and the element would swallow what follows — write "
                f"<{tag} …></{tag}>"
            )
        elif self.stack and self.stack[-1][2] is not None:
            self.stack[-1][2]["children"].append(tag)

    def handle_data(self, data):
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


def parse_structure(markup: str) -> _StructParser:
    """One structural reading of a document or fragment — fed and closed, so
    every reader gets the flushed parse rather than each restating the ritual."""
    parser = _StructParser()
    parser.feed(markup)
    parser.close()
    return parser


_versions = {}  # version file -> (its stamp, the structural reading of it)


def parse_version(page_dir: Path, version: int) -> _StructParser:
    """One structural reading per published version file.

    `version publish` writes a version and nothing writes it again, while the
    readings that cost most are the ones a reader waits through: the action door
    checks a press against the version it was made on, and every poll reads each
    live neighbour's newest version for the one string the tray shows of it. That
    last one made a title cost a parse of the whole page, once a second, per
    neighbour — seven neighbours put more time between a press and its paint than
    everything else the server did for it put together."""
    path = version_path(page_dir, version)
    stamp = file_stamp(path)
    if stamp and (held := _versions.get(path)) and held[0] == stamp:
        return held[1]
    parser = parse_structure(path.read_text(encoding="utf-8"))
    if stamp:
        _versions[path] = (stamp, parser)
    return parser


def version_review_mode(page_dir: Path, version: int):
    """The review ask declared by a published version, or None for comments only."""
    parser = parse_version(page_dir, version)
    return next(
        (meta["content"] for meta in parser.lf_metas if meta["name"] == "lf-review"),
        None,
    )


# ---------- passages: the text an anchor points at ----------
# The runtime resolves an anchor against the DOM; `leaf comment` writes one down
# against the file. The two have to read the same page or the anchor lands somewhere it
# was never made, so this mirrors leaf.js's capture rather than approximating it:
# the same skip list, the same block-boundary space, the same collapse, the same caps.
#
# What the file cannot know is what a widget's module will write, and the registry is
# where that is declared rather than guessed at per widget. Three keywords carry what
# can be declared, and a fence carries the rest:
#
#   x-says      attribute values the reader sees. renderSaid puts them in the DOM, so
#               they go in here too, at the edge the registry names.
#   x-verbatim  an upgraded element whose body reaches the reader as its own words
#               (lf-draft renders the authored text into a plain div, deliberately
#               unmarked so anchoring can see it). Without it, an upgraded element is
#               opaque: a mermaid body is a picture by the time it is read.
#   x-retired-when  the outcome under which this element leaves the page: a decided
#               suggestion's losing slot. The browser builds its anchor pass's skip
#               list from this key too (`quotable` in leaf.js), so a reading given
#               the log's outcomes drops here exactly what drops there — and a widget
#               whose decision leaves nothing showing goes with its slots (settledAway
#               there, `gone` here). Its values are also the vocabulary's decision
#               verbs, which is where `decisions` reads them from.
#   x-state, record kind "body"  the verb whose detail text becomes this element's
#               body once the user sends one (lf-draft's `edit`): replay writes
#               the newest surviving one into the DOM verbatim (applyAction is
#               absolute), so a reading given the fold's word (rewritten_bodies)
#               holds their words in the authored body's place. It asks nothing of
#               the browser, whose page already shows the text this substitutes.
#
# A module writes between the children of the element it upgrades — a column's heading, a
# milestone's chips, a diff's gutters — so an opaque element and each of its children is
# fenced. A quote never spans a fence, which turns "the page has words here that the file
# doesn't" from an anchor that silently detaches in the user's browser into a refusal
# at the moment it is written, addressed to the one party who can still fix it.
#
# Retirement drops and rewriting substitutes rather than fencing, because that is what
# each leaves on the screen. A fence says the reading doesn't know what stands there, and
# in both of these it knows exactly.
#
# x-paints is the key that writes into an upgraded element and belongs in none of this.
# Its word is clipped to nothing and marked as the runtime's (.lf-quiet, .lf-ui), so the
# browser's own reading of the page skips it exactly as this one never sees it: the two
# readings agree by both being silent, and a fence would be room reserved for words no
# reader on either side can reach.

# The collapse class, stated outright: the characters a whitespace run is made of, one
# spelling the set and the regex both derive from, matching leaf.js's COLLAPSE exactly.
# JS's \s and Python's str.isspace() disagree at the edges — U+FEFF is whitespace to JS
# alone, U+0085 and U+001C–001F to Python alone — and a page carrying one of those in
# prose read differently on the two sides, so a `leaf comment` quote could be written
# against text the browser never produces. The browser is the producer of every captured
# quote, so its set is the one both sides speak.
COLLAPSE_CHARS = frozenset(
    "\t\n\x0b\x0c\r \u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000\ufeff"
)
COLLAPSE = re.compile("[" + re.escape("".join(sorted(COLLAPSE_CHARS))) + "]+")


def collapse(text: str) -> str:
    """One space per whitespace run, none at the edges — the reading every quote and
    facet comparison uses, the browser's quoteFrom in Python."""
    return COLLAPSE.sub(" ", text).strip(" ")


# What a text node's "block" resolves to, matching the runtime's TEXT_BLOCK: one space
# goes wherever two runs of text sit in different blocks, and none where they share one,
# so `<p>a</p><p>b</p>` reads "a b" and `set<em>up</em>` reads "setup".
TEXT_BLOCK_TAGS = {
    "p",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "td",
    "th",
    "pre",
    "blockquote",
    "dd",
    "dt",
    "figcaption",
    "summary",
}
# Text no anchor can reach. script/style are the anchor pass's own skip list; head is
# outside the tree it searches at all, the runtime rooting a section-less anchor at
# document.body — without it a page's <title> would be quotable and land nowhere.
UNQUOTABLE_TAGS = {"script", "style", "head"}
# How much of the surrounding text an anchor stores to tell two identical passages
# apart, as leaf.js captures it. The quote itself is stored whole, however long the
# passage: it is the extent the page marks, and a cap on it was a comment quietly made
# on less than was quoted (leaf.js, above selectionAnchor).
CONTEXT = 24


class _PassageParser(HTMLParser):
    """A version's prose as the anchor pass reads it. `text` is the whole page collapsed
    the way a captured quote is; `owner[i]` is the ids enclosing text[i], outermost
    first, so a match can name the section it fell in and be re-read within it.

    `decided` is the accept/reject each suggestion stands under (`decisions`).
    A decision retires a slot — the registry's `x-retired-when` names which outcome —
    and the browser's anchor pass reads the same key (`quotable` in leaf.js), so
    this reading drops it the same way. A decision that leaves its
    widget with nothing — a deletion accepted, an insertion refused — empties the
    wrapper too (`gone`), because an element showing nothing is one nobody can point
    at, however present its markup. `rewrites` is the user's
    standing text per element whose registry entry records a verb as the body
    (`rewritten_bodies`): their words stand in the authored body's place, because
    replay writes exactly that into the DOM. Without either, the reading is the
    version as authored — every slot pending, every body Claude's.

    close() deliberately does not unwind the stack. An element still open at EOF
    would lose its `_close` work — the x-says tail, a `gone` verdict — but those
    attach only to lf-* elements, and every path into this reading is gated on
    `structure_errors`, which refuses any lf-* left open (versions at check and
    publish, thread fragments at their own door, prev_html by the published-note
    filter). The tags legitimately open at EOF (p, li, body, html) lose nothing
    in `_close`. A guard here would defend a state no gated input reaches."""

    def __init__(self, registry=None, decided=None, rewrites=None):
        super().__init__(convert_charrefs=True)
        self.registry = registry or {}
        self.decided = decided or {}
        self.rewrites = rewrites or {}
        self.text = ""
        self.owner = []  # per character: the tuple of enclosing ids
        self.fences = set()  # indices a quote may not span
        self.retired = {}  # id under a retired slot → the suggestion whose decision did it
        self.rewritten = {}  # id whose body the user rewrote → the verb that did it
        self.gone = {}  # decided id whose decision left it empty → the outcome that did it
        self.shown = {}  # id whose data body this reading withheld → the words in it
        # id → the ids enclosing it, outermost first, itself last. Structure, not
        # words: an element is somewhere on the page whether or not it says
        # anything, which is what the containment questions downstream ask (see
        # `spoken`). Written for every id the markup carries, since a widget's
        # detail may name one the page holds outside the vocabulary.
        self.enclosing = {}
        self.bearing = (
            set()
        )  # ids still showing something: text under them, or a surviving child
        self.stack = []  # [{"tag", "id", "ids", "skip", "shows", "sub", "opaque", "fenced", "retired_by", "tb", "block", "tail"}]
        self._uid = 0
        self._block = None  # the block the last character came from
        self._space = False  # a separator waiting for a character to follow it

    def _fresh(self) -> int:
        self._uid += 1
        return self._uid

    def _write(self, data: str, block: int, ids: tuple) -> None:
        """Text into the collapsed run, one space per whitespace run and none leading."""
        if data.strip():
            self.bearing.update(ids)
        if self.text and block != self._block:
            self._space = True
        self._block = block
        for ch in data:
            if ch in COLLAPSE_CHARS:
                self._space = bool(self.text)
                continue
            if self._space:
                self.text += " "
                self.owner.append(ids)
                self._space = False
            self.text += ch
            self.owner.append(ids)

    def _fence(self) -> None:
        """Words may stand here that this reading knows nothing about. Recorded as a
        position rather than written into the text, so `text` stays the page's own words
        and no quote can be built out of one."""
        self.fences.add(len(self.text))

    def _said(self, frame: dict, values: list) -> None:
        # renderSaid puts each value in its own <span>, so each is its own block wherever
        # the widget sits outside a text block — the same rule, applied to the span.
        for value in values:
            self._write(
                value, frame["tb"] if frame["tb"] else self._fresh(), frame["ids"]
            )

    def _close(self, frame: dict) -> None:
        """Everything an element's end does, whether it was written or inferred — an
        omitted </p> inside a widget still ends what the element was saying."""
        if not frame["skip"]:
            self._said(frame, frame["tail"])
        if frame["fenced"]:
            self._fence()
        # A decided element closing with nothing shown left the page with its decision:
        # a deletion accepted, an insertion refused. Everything it held is either a
        # retired slot or silent, so there is nothing on screen for an anchor to reach.
        if (
            frame["id"] in self.decided
            and not frame["skip"]
            and frame["id"] not in self.bearing
        ):
            self.gone[frame["id"]] = self.decided[frame["id"]]

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        # Before the void check, unlike the structure lint's: <hr> is both void and a
        # paragraph closer, and text after it is in a different block.
        for _ in range(implicit_closes([f["tag"] for f in self.stack], tag)):
            self._close(self.stack.pop())
        parent = self.stack[-1] if self.stack else None
        # Recorded before the void check, and before anything asks what this element
        # shows: where an element sits is a fact about the markup, so an image, an
        # opaque widget and a slot a decision retired each answer it like any other.
        ids = (parent["ids"] if parent else ()) + (
            (attrs_d["id"],) if attrs_d.get("id") else ()
        )
        if attrs_d.get("id"):
            self.enclosing[attrs_d["id"]] = ids
        if tag in VOID_TAGS:
            return
        entry = self.registry.get(tag) or {}
        # The innermost open text block, if any: the runtime's `closest(TEXT_BLOCK)`.
        tb = (
            self._fresh()
            if tag in TEXT_BLOCK_TAGS
            else (parent["tb"] if parent else None)
        )
        # A module may write anywhere inside the element it upgrades, unless the registry
        # says the body reaches the reader as its own words.
        opaque = bool(entry.get("x-upgrade") and not entry.get("x-verbatim"))
        # A slot a decision retired: its words left the page with the outcome the
        # registry names, and everything under it goes too. Looked up by the parent's
        # own id — the same child-of-suggestion shape as the browser's selector.
        retired_by = (parent["retired_by"] if parent else None) or (
            parent["id"]
            if parent
            and entry.get("x-retired-when")
            and self.decided.get(parent["id"]) == entry["x-retired-when"]
            else None
        )
        # A wall this element raises itself: its words are off the reader's page, whatever
        # holds it. Named apart from the inherited half below because the two answer
        # different questions — an element under a withheld data body is still showing
        # its words, and one under a retired slot is not.
        own_wall = bool(
            retired_by
            or tag in UNQUOTABLE_TAGS
            or "lf-ui" in (attrs_d.get("class") or "").split()
        )
        # Silenced from above: the element shows nothing of its own, so a rewrite of
        # its body has nothing to stand in for — an edited draft inside a slot the
        # user accepted away left the page with the slot.
        silenced = bool((parent and parent["skip"]) or own_wall)
        # A surviving child keeps its parent on the page even where it holds no text —
        # a kept slot whose only content is an image. The text case marks every
        # enclosing id in _write.
        if parent and not silenced:
            self.bearing.add(parent["id"])
        # A body the user rewrote. `rewritten_bodies` already resolved the verb
        # through this element's x-state, so an id in the dict is the whole test:
        # the fold decides, this pass only applies.
        sub = self.rewrites.get(attrs_d.get("id")) if not silenced else None
        # The element whose data body this reading is withholding, carried down to
        # everything under it. The page shows whatever its module made of that body, so a
        # quote landing inside one is told where it landed rather than told the page never
        # said it — a claim wider than this reading can make. Only where the body still
        # stands: a retired or rewritten one is `retired`/`rewritten`'s to answer for, and
        # each of those names the act that did it.
        shows = (
            None
            if own_wall or sub is not None
            else (parent["shows"] if parent else None)
            or (
                attrs_d.get("id")
                if opaque and entry.get("x-content") == "data"
                else None
            )
        )
        frame = {
            "tag": tag,
            "id": attrs_d.get("id"),
            "ids": ids,
            "skip": silenced
            or sub is not None
            or (opaque and entry.get("x-content") == "data"),
            "shows": shows,
            "sub": sub,
            "retired_by": retired_by,
            "opaque": opaque,
            "fenced": opaque or bool(parent and parent["opaque"]),
            "tb": tb,
            # …and where there is none, the element is its own text node's parent, which
            # is what the runtime falls back to. Fresh per element, so `a<em>b</em>c`
            # under a <div> reads as three blocks and under a <p> as one.
            "block": tb if tb else self._fresh(),
            "tail": [],
        }
        # Each x-says value at the edge of the element's own words, in registry order,
        # which is where renderSaid puts it and where a pseudo-element stood before it.
        head = []
        for attr, edge in (entry.get("x-says") or {}).items():
            value = attrs_d.get(attr)
            if value is None:
                continue
            (head if edge == "before" else frame["tail"]).append(value)
        if frame["fenced"]:
            self._fence()
        if retired_by and frame["id"]:
            self.retired[frame["id"]] = retired_by
        self.stack.append(frame)
        if not frame["skip"]:
            self._said(frame, head)
        elif sub is not None:
            # The body's own write path, so a quote across the element's edge sees
            # the same adjacency the screen shows — no fence, nothing withheld.
            verb, their_text = sub
            self._write(their_text, frame["block"], frame["ids"])
            self.rewritten[frame["id"]] = verb

    def handle_data(self, data):
        frame = self.stack[-1] if self.stack else None
        if not frame:
            return
        if not frame["skip"]:
            self._write(data, frame["block"], frame["ids"])
        elif frame["shows"]:
            self.shown[frame["shows"]] = self.shown.get(frame["shows"], "") + data

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                # Innermost first, so an element closing over unclosed children ends them
                # in the order they were opened in.
                while len(self.stack) > i:
                    self._close(self.stack.pop())
                return

    def close(self):
        super().close()
        # An element still open at EOF owes its close all the same: a frame never
        # closed loses its `gone` verdict and its trailing x-says values. `version
        # check` refuses unbalanced markup, but this parser also reads `prev_html`
        # and fragments that never passed that gate.
        while self.stack:
            self._close(self.stack.pop())


class Passages(NamedTuple):
    """A version's words, and what a search over them needs to know."""

    text: str  # collapsed the way a captured quote is
    owner: list  # per character: the tuple of enclosing ids, outermost first
    fences: set  # indices a quote may not span: where a module may write
    retired: dict  # id under a retired slot → the suggestion whose decision did it
    rewritten: dict  # id whose body the user rewrote → the verb that did it
    gone: dict  # decided id whose decision left it empty → the outcome that did it
    shown: dict  # id whose data body this withheld → the words a module shows there
    enclosing: dict  # id → the ids enclosing it, outermost first, itself last


def page_passages(html: str, registry=None, decided=None, rewrites=None) -> Passages:
    parser = _PassageParser(registry, decided, rewrites)
    parser.feed(html)
    parser.close()
    return Passages(
        parser.text,
        parser.owner,
        parser.fences,
        parser.retired,
        parser.rewritten,
        parser.gone,
        # Collapsed the way `text` is, so one comparison answers for both.
        {id: collapse(words) for id, words in parser.shown.items()},
        parser.enclosing,
    )


def section_span(owner: list, section: str):
    """The half-open range of characters inside `section`, or None when the version has
    no such element with text in it. An element is contiguous in document order, so its
    characters are too — which is what lets a search be scoped by slicing."""
    inside = [i for i, ids in enumerate(owner) if section in ids]
    return (inside[0], inside[-1] + 1) if inside else None


class Spoken(NamedTuple):
    """What one element says, and where it sits."""

    words: str  # the words under it, as the anchor pass reads them
    within: tuple  # the ids enclosing it, outermost first, itself last


# An id this version doesn't carry — nothing said, and nowhere it sits. An element
# that is here and silent is not this: it has a chain, which is what lets a fold
# reach a card holding one diagram.
EMPTY = Spoken("", ())


def spoken(html: str, registry: dict) -> dict:
    """id → Spoken, for every element the version carries.

    This is the version's own reading of itself, so it is `page_passages` sliced by
    id rather than a second walk: chrome skipped, x-says attributes counted (a
    picked option's `effort` is a word on the page now, so changing it changes what
    the user decided about), whitespace collapsed the way a captured quote is.
    Asking whether two versions still say the same thing has to mean the same text a
    user could have selected, or the question is about something else.

    `section_span` answers this for one id by scanning the page; every id at once is
    that same scan, done once.

    The two halves come from different readings because they are different facts,
    and taking both off the character scan cost the second one. Words are what the
    scan holds. Where an element *sits* is structure, so it comes from the parser's
    record of what was open — and an element that says nothing is somewhere all the
    same. Keyed on words, an image-only option and a card holding one diagram were
    in no chain at all, so `action_rests_on` dropped them from what an action rests
    on where the browser's `restsOn` keeps them (a floor stopped replaying on one
    side only), and `markup_facet` read a version that honoured a pick on such an
    option as showing no pick, which is the state gate refusing the very version
    that agreed with the user."""
    p = page_passages(html, registry)
    first, last = {}, {}
    for i, ids in enumerate(p.owner):
        for wid in ids:
            first.setdefault(wid, i)
            last[wid] = i
    # Stripped: the separator `_write` puts between blocks lands inside whichever
    # element the next block opens, so a slice can start or end on one. It marks a
    # boundary rather than saying anything.
    said = {wid: p.text[lo : last[wid] + 1].strip() for wid, lo in first.items()}
    return {wid: Spoken(said.get(wid, ""), chain) for wid, chain in p.enclosing.items()}


def enclosing_section(owner: list, lo: int, hi: int):
    """The innermost id enclosing every character of [lo, hi) — the runtime's
    `closest("[id]")` on the passage's common ancestor."""
    first, last = owner[lo], owner[hi - 1]
    shared = 0
    while shared < min(len(first), len(last)) and first[shared] == last[shared]:
        shared += 1
    return first[shared - 1] if shared else None


def occurrences(text: str, quote: str, lo: int, hi: int, fences=frozenset()) -> list:
    """Where `quote` sits in text[lo:hi], as absolute indices. A match that runs across a
    fence is not one: the page has words there that this text doesn't."""
    found = []
    at = text.find(quote, lo, hi)
    while at != -1:
        if not any(at < f < at + len(quote) for f in fences):
            found.append(at)
        at = text.find(quote, at + len(quote), hi)
    return found


def capture_anchor(
    html: str, registry, quote: str, section: str, decided=None, rewrites=None
) -> dict:
    """The anchor a quote makes, written the way a selection's is. Raises ValueError with
    what to do about it — a quote the file doesn't hold, or holds twice, is a question
    with an answer, and asking now beats posting a comment that lands nowhere.

    `decided` and `rewrites` make this the reading the user is looking at rather
    than the version as authored: a slot their decision retired is off the page, and a
    body their edit rewrote holds their words — so an anchor is met here the way it
    would land there, instead of detaching in front of them."""
    text, owner, fences, retired, rewritten, gone, shown, enclosing = page_passages(
        html, registry, decided, rewrites
    )
    if section:
        # Against the structure, not the text: an element anchor is the one a click makes
        # on a diagram or an image, and those hold no text to look for.
        if section not in enclosing:
            raise ValueError(f"no element id {section!r} in this version")
        if section in retired:
            sid = retired[section]
            raise ValueError(
                f"§ {section} left the page when the user chose to {decided[sid]} "
                f"§ {sid} — a decision retires the slot its outcome names, and an anchor "
                "on it would reach nobody. Anchor on the settled text instead."
            )
        if section in gone:
            raise ValueError(
                f"§ {section} settled to nothing when the user chose to {gone[section]} "
                "it — the decision removed everything it held from the page, and an anchor "
                "on it would reach nobody. Anchor on the surrounding text instead."
            )
    if not quote:
        return {"section": section}

    wanted = collapse(quote)
    lo_bound, hi_bound = 0, len(text)
    if section:
        span = section_span(owner, section)
        if span is None:
            raise ValueError(
                f"§ {section} holds no quotable text — a widget's data body is its source, "
                "not its words. Drop --quote to anchor on the element itself."
            )
        lo_bound, hi_bound = span
    where = "the page" if not section else f"§ {section}"
    hits = occurrences(text, wanted, lo_bound, hi_bound, fences)
    if not hits:
        if occurrences(text, wanted, lo_bound, hi_bound):
            raise ValueError(
                f"{wanted!r} runs across a widget's parts, and a widget writes words of "
                "its own between them — a column's heading, a milestone's chips, a "
                "diagram in place of its source. Quote within one part, or --section the "
                "widget to point at the whole of it."
            )
        was = _removed_by(html, registry, wanted, section, decided or {}, rewritten)
        if was:
            raise ValueError(f"{where} said {wanted!r} until {was}")
        holder = next((el for el, words in shown.items() if wanted in words), None)
        if holder:
            raise ValueError(
                f"{wanted!r} is in § {holder}'s data body, which is the widget's source "
                "and not its words — the page shows whatever its module made of that, "
                "and this reading holds nothing there to anchor on. Point at the element "
                f"instead: --section {holder}."
            )
        raise ValueError(
            f"{where} doesn't say {wanted!r} — quote it as the version file holds it. A "
            "widget's data body is the widget's source, not its words (a diagram's body "
            "is a picture by the time it is read), so --section the element instead."
        )
    if len(hits) > 1:
        around = [
            f"  - …{text[max(lo_bound, at - 30) : at + len(wanted) + 30]}…"
            for at in hits[:4]
        ]
        if len(hits) > len(around):
            around.append(f"  - …and {len(hits) - len(around)} more")
        raise ValueError(
            f"{where} says {wanted!r} {len(hits)} times, so this quote names no one "
            "passage. Extend it, or scope it with --section:\n" + "\n".join(around)
        )

    lo = hits[0]
    hi = lo + len(wanted)
    section = section or enclosing_section(owner, lo, hi)
    # The neighbours come from the whole reading, as the browser's do — the section
    # filters where the search may land, never what surrounds a passage — so a passage
    # closing its section still stores a full suffix. Each side reaches only to the
    # nearest fence, because past one the page holds words this doesn't: context the
    # runtime can never confirm leaves every copy equally unconfirmed, which is where
    # an anchor carrying none starts anyway.
    # Both are trimmed before they are cut, since the runtime reads its side back through
    # the same collapse, which trims — a stored space no occurrence produces fails at the
    # first comparison.
    prefix = text[max([0] + [f for f in fences if f <= lo]) : lo].strip()[-CONTEXT:]
    suffix = text[hi : min([len(text)] + [f for f in fences if f >= hi])].strip()[
        :CONTEXT
    ]
    return {
        "section": section,
        "quote": wanted,
        **({"prefix": prefix} if prefix else {}),
        **({"suffix": suffix} if suffix else {}),
    }


def _removed_by(html, registry, wanted: str, section: str, decided, rewritten):
    """What took `wanted` off the user's page, when the version as authored still
    holds it: the decision that retired the slot it sat in, or the edit that rewrote
    the element saying it. Naming that act beats telling the writer the page never
    said it."""
    if not (decided or rewritten):
        return None
    p = page_passages(html, registry)
    lo, hi = 0, len(p.text)
    if section:
        span = section_span(p.owner, section)
        if span is None:
            return None
        lo, hi = span
    for at in occurrences(p.text, wanted, lo, hi, p.fences):
        for ids in p.owner[at : at + len(wanted)]:
            sid = next((wid for wid in ids if wid in decided), None)
            if sid:
                return (
                    f"the user chose to {decided[sid]} § {sid} — that decision "
                    "retired these words from the page. Quote it as it now stands."
                )
            wid = next((wid for wid in ids if wid in rewritten), None)
            if wid:
                return (
                    f"the user rewrote § {wid} — their {rewritten[wid]} replaced "
                    "these words. Quote the text as they left it."
                )
    return None


# ---------- the readable column ----------
# A rule, a style="" and a width="" are the three places a document states a width.
# The first two are CSS, so tinycss2 reads them; the third is an attribute, so the
# markup parser does.
#
# Three patterns over the file's text came first, and each answered something adjacent
# to the question asked: the document read as a stylesheet handed a screenshot's base64
# to the rule walker, `width` needed a lookbehind to exclude `max-width` because it
# matched a name instead of reading a property, and the scan for `style=""` never saw
# one written with the other quote. Hand-rolling the parser is the same mistake a level
# down, and harder to see, because a hand-rolled parser is right about the grammar it
# was written against: the brace walk those patterns became knew that a comment's braces
# are not braces, and still read a `}` inside `content: "}"` as the end of the block,
# dropping every declaration after it in that rule; still read a rule holding both
# declarations and a nested rule as declaring nothing of its own; and still told a fixed
# `900px` from a `calc(100% - 900px)` by asking whether the string ended in `px`, which
# `900px !important` does not. CSS has no parser in the stdlib, so the dependency is a
# real cost — one more wheel behind every `version check`, ~6ms to read the theme — and
# it buys the grammar whole rather than one bug's worth at a time.


def css_block(css):
    """What a block holds: the declarations it states, and the rules nested inside it. A
    style="" attribute is a block written without the braces around it."""
    return tinycss2.parse_blocks_contents(css, skip_comments=True, skip_whitespace=True)


def css_rules(css: str):
    """(selector, block, conditional) per qualified rule, at every depth — a rule that
    holds both declarations and a nested rule states one of its own. `conditional` is
    true for a rule inside an at-rule, which applies only when a condition this check
    never evaluates holds: `@media print`, a viewport query. Nesting alone is not a
    condition, so a rule nested in a conditional one is conditional and no more."""
    yield from _rules(
        tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
    )


def _css_unclosed_blocks(css: str) -> int:
    """How many blocks a stylesheet leaves open at end of file.

    The CSS parser auto-closes these (so tinycss2 reports no error), which is
    exactly what makes one dangerous here: stylesheets are layer sources that
    concatenate, so a block left open swallows every rule after it — the rest
    of the file's and every later layer's — into its own scope. Counted
    outside comments and strings; an over-closed sheet floors at zero, since
    the stray brace is a parse error tinycss2 already names."""
    depth = 0
    i = 0
    while i < len(css):
        ch = css[i]
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = len(css) if end == -1 else end + 2
        elif ch in "\"'":
            quote = ch
            i += 1
            while i < len(css) and css[i] not in (quote, "\n"):
                i += 2 if css[i] == "\\" else 1
            i += 1
        else:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth = max(0, depth - 1)
            i += 1
    return depth


def css_syntax_errors(css: str, source: str, *, block=False) -> list:
    """Every parse error in a stylesheet or declaration block, including nested rules."""
    parse = (
        css_block
        if block
        else lambda value: tinycss2.parse_stylesheet(
            value, skip_comments=True, skip_whitespace=True
        )
    )
    errors = []
    seen = set()
    if not block and (depth := _css_unclosed_blocks(css)):
        errors.append(
            f"{source}: {depth} block(s) left open at end of file — every rule "
            "after the unclosed brace, this stylesheet's or a later layer's, "
            "lands inside its scope"
        )

    def record(node):
        key = (node.source_line, node.source_column, node.message)
        if key in seen:
            return
        seen.add(key)
        errors.append(
            f"{source} syntax error at "
            f"{node.source_line}:{node.source_column}: {node.message}"
        )

    def walk_tokens(tokens):
        for token in tokens:
            if token.type == "error":
                record(token)
            for attr in ("arguments", "content"):
                nested = getattr(token, attr, None)
                if isinstance(nested, list):
                    walk_tokens(nested)

    def walk_rules(nodes):
        for node in nodes:
            if node.type == "error":
                record(node)
            for attr in ("prelude", "value"):
                tokens = getattr(node, attr, None)
                if isinstance(tokens, list):
                    walk_tokens(tokens)
            if node.type in {"qualified-rule", "at-rule"} and node.content is not None:
                walk_tokens(node.content)
                walk_rules(css_block(node.content))

    walk_rules(parse(css))
    return errors


def _rules(nodes, conditional=False):
    """`nodes` and every rule nested inside them, as (selector, block, conditional)."""
    for node in nodes:
        if node.type == "qualified-rule":
            block = css_block(node.content)
            yield tinycss2.serialize(node.prelude).strip(), block, conditional
            yield from _rules(block, conditional)
        elif node.type == "at-rule" and node.content:
            yield from _rules(css_block(node.content), True)


def _number(text: str):
    """`text` as a number, or None when it is not one. A width="" attribute states a
    bare count of pixels, so it has no unit for the CSS parser to read."""
    try:
        return float(text)
    except ValueError:
        return None


def _lone_px(value):
    """The pixel length a value states outright, or None. A value keeps the whitespace
    around it, which is a token like any other and not part of what the value says."""
    tokens = [t for t in value if t.type != "whitespace"]
    if (
        len(tokens) == 1
        and tokens[0].type == "dimension"
        and tokens[0].lower_unit == "px"
    ):
        return tokens[0].value
    return None


def root_tokens(css: str) -> dict:
    """The pixel lengths a stylesheet states outright as custom properties on the root.

    A width naming one of these states a number as certainly as writing it out, so the
    readings below resolve it. Only the root, and only unconditionally: a token set on
    some element or inside a query is that element's or that condition's, and taking it
    for the page's would be the same reading the column refuses a media query for.

    One level. A token defined as another token is a stylesheet answering a different
    question than these readings ask, and following it would be a resolver rather than
    the two facts this needs."""
    tokens = {}
    for selector, block, conditional in css_rules(css):
        if conditional or selector.strip() != ":root":
            continue
        for declaration in block:
            if declaration.type == "declaration" and declaration.name.startswith("--"):
                px = _lone_px(declaration.value)
                if px is not None:
                    tokens[declaration.name] = px
    return tokens


def _px(declaration, tokens: dict | None = None):
    """The pixel length a declaration states, or None where it states something else: a
    percentage, a vw, a calc() with a px term inside it. Only a fixed pixel length is a
    hard overflow, and only a lone length is fixed.

    A lone `var()` naming a root token is one too. The stylesheet stated the number and
    then named it, and a check that stopped at the name would read the fallback width
    for a theme that had tidied its own constants into `:root` — which is a check that
    quietly stops measuring the moment the file it measures gets tidier. The `var()`'s
    own fallback answers where nothing declared the token, which is what the browser
    would use."""
    value = [t for t in declaration.value if t.type != "whitespace"]
    px = _lone_px(value)
    if px is not None:
        return px
    if len(value) == 1 and value[0].type == "function" and value[0].lower_name == "var":
        args = [t for t in value[0].arguments if t.type != "whitespace"]
        if args and args[0].type == "ident" and args[0].value.startswith("--"):
            named = (tokens or {}).get(args[0].value)
            if named is not None:
                return named
            if len(args) > 2 and args[1] == ",":
                return _lone_px(args[2:])
    return None


def _px_widths(declarations, props: tuple, tokens: dict | None = None):
    """(property, pixels) per declaration in `props` pinned to a fixed pixel length."""
    for declaration in declarations:
        if declaration.type == "declaration" and declaration.lower_name in props:
            px = _px(declaration, tokens)
            if px is not None:
                yield declaration.lower_name, px


def _column_width(page_css: str, theme_css: str) -> int:
    """Best-effort readable-column width from the max-width of a container rule.
    A page's own <style> wins over the vendored theme, which wins over the fallback.

    Only what a stylesheet states outright counts: a column is the baseline everything
    else is measured against, so it has to be certain, and a conditional rule states a
    column for some condition rather than for the page. Reading them too let a page
    disable this check with one line of print CSS — `@media print { main { max-width:
    2000px } }` measured every screen element against 2000px."""
    for css in (page_css, theme_css):
        tokens = root_tokens(css)
        widths = [
            px
            for selector, block, conditional in css_rules(css)
            if not conditional and _names_column(selector)
            for _, px in _px_widths(block, ("max-width",), tokens)
        ]
        if widths:
            return int(max(widths))
    return COLUMN_FALLBACK


def _overwide_elements(
    parser: _StructParser, column: int, theme_tokens: dict | None = None
) -> list:
    """Everything a version pins wider than the column: its own rules, its inline
    styles, and the width="" attributes that count as pixels.

    A conditional rule counts here, where it cannot define the column: a pin is a risk
    rather than a baseline, and it overflows whenever its condition holds.

    A width naming a token resolves against the page's own root first and the layer's
    behind it, which is the order the cascade reads them in. A page pinning
    `var(--wide)` is stating the layer's number, and a reading that knew only the page's
    own tokens would let the vocabulary's own widths through unmeasured."""
    hits = []
    tokens = {**(theme_tokens or {}), **root_tokens(parser.css)}
    for selector, block, _ in css_rules(parser.css):
        for prop, px in _px_widths(block, OVERFLOW_PROPS, tokens):
            if px > column:
                hits.append(
                    f"rule `{selector}` sets {prop}: {px:g}px (column is {column}px)"
                )
    for style in parser.inline_styles:
        for prop, px in _px_widths(css_block(style), OVERFLOW_PROPS, tokens):
            if px > column:
                hits.append(f"inline style {prop}: {px:g}px (column is {column}px)")
    for tag, value in parser.attr_widths:
        px = _number(value)
        if px is not None and px > column:
            hits.append(f'<{tag} width="{value}"> exceeds column ({column}px)')
    return hits


PRESENTATION_PROPERTIES = {
    "all",
    "display",
    "interactivity",
    "opacity",
    "pointer-events",
    "visibility",
}


def inline_presentation_override_errors(parser: _StructParser) -> list:
    """Inline importance outranks even the theme's first important cascade layer."""
    errors = []
    for number, style in enumerate(parser.inline_styles, 1):
        for declaration in css_block(style):
            if (
                declaration.type == "declaration"
                and declaration.important
                and declaration.lower_name in PRESENTATION_PROPERTIES
            ):
                errors.append(
                    f"inline style #{number} makes protected presentation property "
                    f"{declaration.lower_name} important"
                )
    return errors
