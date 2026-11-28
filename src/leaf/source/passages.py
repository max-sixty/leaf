"""Text-passage readings of authored HTML: the page's words as a reader reads them
(`page_passages`), and the words that name an element (`element_name`)."""

import re
import weakref
from functools import lru_cache
from html import escape
from typing import NamedTuple
from urllib.parse import urlsplit

import turbohtml

from leaf.source.registry.contract import (
    NAME_ATTRIBUTE,
    body_is_data,
    is_element_name,
    upgraded,
)
from leaf.source.registry.kernel import kernel_passages
from leaf.source.structure import VOID_TAGS, SourceDocument, pre_body

# ---------- passages: the page's words as a reader reads them ----------
# The browser alone finds an anchor's words, in the page it draws. This reading of the
# files gives the rest of Leaf the page's words: what an element says (`spoken`), the
# page's text the turn-end fork reads, the words a gesture names, word counts, and the
# advice `leaf thread create` gives on a quote (`anchor_capture`). It reads by the
# runtime's rules for words (readings/passages.js): the same skip list, the same space
# between blocks and between elements' words, the same collapse, so the words read as
# the page shows them. Nothing holds the two readings to each other: where they differ,
# the agent reads words a little apart from what the page draws, and `anchor_capture`
# says what its advice then gets wrong.
#
# What the file cannot know is what a widget's module will write, and the registry is
# where that is declared rather than guessed at per widget:
#
#   `verbatim`  an upgraded element that keeps its own words. Without this key the
#               upgraded element is opaque, since its module may insert or replace
#               words, and a data body it holds is withheld, as a diagram's notation
#               is once its module has drawn a picture.
#   `retired-when`  the outcome under which this element leaves the page: a
#               decided suggestion's losing slot. The browser builds its anchor pass's
#               skip list from this key too (`quotable` in readings/passages.js), so a
#               reading given the log's outcomes drops here what drops there — and a
#               widget whose decision leaves nothing showing goes with its slots
#               (settledAway there, `gone` here). Its values are also the vocabulary's
#               decision verbs, which is where `obligations` reads them from.
#   `owners` with content markup  direct prose members remain readable inside a
#               data widget; its other body content is source notation, withheld.
#   `verbs`, record kind "body"  the verb whose detail text becomes this
#               element's body once the user sends one (lf-draft's `edit`): replay
#               writes the newest surviving one into the DOM verbatim (a widget's
#               render is absolute), so a reading given the fold's word
#               (rewritten_bodies) holds their words in the authored body's place. It
#               asks nothing of the browser, whose page already shows the text this
#               substitutes.
#
# A module writes between the children of the element it upgrades — a column's heading, a
# milestone's chips, a diff's gutters — so an opaque element and each of its children is
# fenced, as the browser fences them (`fencePassageParts`). A copy across a fence is no
# copy (`anchor_capture.occurrences`), since the page has words there the file doesn't,
# so a quote across one draws the note that the file doesn't find it. A native editing
# value is fenced too, since the user may change it.
#
# A textarea's child text initializes its native value rather than showing as the
# page's words, so the reading skips it.

# The characters a whitespace run is made of, as the browser's reading collapses them
# (kernel-registry.json's `$passages` says why the set is spelled out).
COLLAPSE_CHARS = frozenset(kernel_passages()["collapse"])
COLLAPSE = re.compile("[" + re.escape("".join(sorted(COLLAPSE_CHARS))) + "]+")


def _rendered(markup: str):
    """Rendered Markdown as the browser's tree holds it once set as a block's
    content."""
    return turbohtml.parse_fragment(markup, context="div", positions=False)


def _rendered_words(markup: str, *, image_alt=False) -> str:
    """Read rendered text as the DOM does; image labels also read nested image alts."""
    parts = []

    def read(node):
        if isinstance(node, turbohtml.Text):
            parts.append(node.data)
        elif isinstance(node, turbohtml.Element):
            if image_alt and node.tag == "img":
                parts.append(node.attrs["alt"])
            for child in node.children:
                read(child)

    read(_rendered(markup))
    return "".join(parts)


def _fence_words(state) -> None:
    """A message's fence shows the words on its opening line as its code's first line,
    unless one word names the language of the code below (lib/markdown.js,
    `fence_words`)."""
    for token in state.tokens:
        words = token.info.strip()
        if token.type != "fence" or not words:
            continue
        if token.content and not re.search(r"\s", words):
            continue
        token.content = f"{words}\n{token.content}"
        token.info = ""


def _file_formulas(state) -> None:
    """A file's inline formula, a code span with a `$` against each backtick, as a code
    span in the math language without the dollars (lib/markdown.js, `file_formulas`)."""
    for block in state.tokens:
        if block.type != "inline" or not block.children:
            continue
        children = block.children
        for at in range(1, len(children) - 1):
            before, code, after = children[at - 1 : at + 2]
            if (
                code.type == "code_inline"
                and before.type == "text"
                and after.type == "text"
                and before.content.endswith("$")
                and after.content.startswith("$")
            ):
                before.content = before.content[:-1]
                after.content = after.content[1:]
                code.attrJoin("class", "language-math")


@lru_cache(maxsize=3)
def markdown_dialect(message: bool, html: bool = False):
    """The browser's safe Markdown dialect for one of its readings, with its linkify
    and task lists (lib/markdown.js, `makeMarkdown`; `renderMarkdown` says how the
    readings differ). A thread message and a user-created child's words read as a
    message, and a Markdown body reads as a file. `html` keeps the raw HTML an
    agent's message holds (`message_markup`), which every other reading shows as
    text."""
    from markdown_it import MarkdownIt
    from markdown_it.renderer import RendererHTML
    from mdit_py_plugins.tasklists import tasklists_plugin

    class PageMarkdown(MarkdownIt):
        def validateLink(self, url: str) -> bool:
            return True

    parser = PageMarkdown("gfm-like", {"html": html, "breaks": message}).use(
        tasklists_plugin
    )
    if message:
        parser.disable("lheading")
        # A message reads no indented code, and no block starts on a line indented four
        # spaces, as the browser's markdown-it reads it. markdown-it-py starts one there
        # once its `code` rule is off, so the rule stays on and reads nothing.
        parser.block.ruler.at("code", lambda state, start, end, silent: False)
        parser.core.ruler.after("block", "fence_words", _fence_words)
    else:
        parser.core.ruler.before("text_join", "file_formulas", _file_formulas)
    assert parser.linkify is not None
    parser.linkify.set({"fuzzy_link": False})
    # The browser accepts syntax first, then removes unsafe link destinations while
    # retaining their label. Parse those links here too, where only visible text is read.
    renderer = parser.renderer
    assert isinstance(renderer, RendererHTML)
    # Nested image labels may retain entity/escape tokens after text joining.
    renderer.rules["text_special"] = renderer.rules["text"]

    # A picture with no alt text, `![](src)`, has no children.
    def safe_image(_renderer, tokens, idx, options, env):
        token = tokens[idx]
        alt = _rendered_words(
            renderer.renderInline(token.children or [], options, env), image_alt=True
        )
        token.attrSet("alt", alt)
        if urlsplit(token.attrGet("src") or "").scheme not in (
            "",
            "http",
            "https",
            "mailto",
        ):
            return escape(alt)
        return renderer.renderToken(tokens, idx, options, env)

    parser.add_render_rule("image", safe_image)
    link = renderer.rules.get("link_open")

    def safe_link(_renderer, tokens, idx, options, env):
        token = tokens[idx]
        if urlsplit(token.attrGet("href") or "").scheme not in (
            "",
            "http",
            "https",
            "mailto",
        ):
            for following in tokens[idx + 1 :]:
                if following.type == "link_close":
                    following.meta["unsafe"] = True
                    break
            return ""
        return (
            link(tokens, idx, options, env)
            if link
            else renderer.renderToken(tokens, idx, options, env)
        )

    parser.add_render_rule("link_open", safe_link)

    def safe_link_close(_renderer, tokens, idx, options, env):
        return (
            ""
            if tokens[idx].meta.get("unsafe")
            else renderer.renderToken(tokens, idx, options, env)
        )

    parser.add_render_rule("link_close", safe_link_close)
    return parser


def markdown_markup(source: str) -> str:
    """A Markdown body (`content: markdown`) as the browser paints it, read as
    a file (lib/markdown.js, `paintMarkdown`), as inert markup for passage reading and a
    revision's prepaint."""
    return markdown_dialect(False).render(source)


def message_markup(text: str) -> str:
    """The markup an agent's message draws: its Markdown read as a message, with the
    raw HTML in it kept, as the browser renders
    it (lib/markdown.js, `renderAuthoredMarkdown`). Every reading of the message's
    elements, its check among them, parses this."""
    return markdown_dialect(True, html=True).render(text)


def holds_html(text: str) -> bool:
    """Whether an agent's Markdown holds raw HTML, by whether keeping it changes what
    the message draws. Raw HTML opens with `<`, so text without one holds none."""
    return "<" in text and message_markup(text) != markdown_dialect(True).render(text)


def feed_markdown(parser, source: str) -> None:
    """Apply inert rendered markup through the ordinary passage handlers."""
    for child in _rendered(markdown_markup(source)).children:
        _walk(parser, child)


def created_words(words: str) -> str:
    """A created child's words (`creates`) as the browser shows them: the user typed
    them, so they read as inline Markdown, as a message does."""
    return _rendered_words(markdown_dialect(True).renderInline(words))


def shown_words(words: str, entry: dict, *, added: bool) -> str:
    """The words an element's text shows: an `added` child's (one a user created,
    `data-lf-added`) as `created_words`, else as its entry's `content` reads them."""
    if added:
        return created_words(words)
    if entry.get("content") == "markdown":
        return _rendered_words(markdown_markup(words))
    return words


def collapse(text: str) -> str:
    """One space per whitespace run, none at the edges — the reading every quote and
    state comparison uses, the browser's quoteFrom in Python."""
    return COLLAPSE.sub(" ", text).strip(" ")


# The elements a line of words runs through (`$passages.phrasing`), as the runtime's
# `enter` reads it. Every other element, a text block among them, and a widget unless it
# is declared `inline`, reads its words apart from those around it: one space goes
# between two runs of words read in different elements. Two runs read in one meet with
# nothing between them, or with a space by the rule below, since only the page's CSS
# says whether `<strong>Status</strong><span>Ready</span>` shows one word or two.
JOINS_WORDS_TAGS = frozenset(kernel_passages()["phrasing"])
# The tags whose words are prose: inside one, two runs of words that meet show nothing
# between them, as `set<em>up</em>` reads "setup"; outside any, where two elements meet
# they show a space, as a chip beside its title does, unless a closing mark follows it
# or an opening one precedes it (`CLOSING`, `OPENING`; `_write`, the runtime's
# `shownApart`).
TEXT_BLOCK_TAGS = frozenset(kernel_passages()["blocks"])
# The marks no shown space stands before (`CLOSING`) or after (`OPENING`) where two
# elements' words meet (`$passages.why-closing-and-opening`).
CLOSING = frozenset(kernel_passages()["closing"])
OPENING = frozenset(kernel_passages()["opening"])
# Text no anchor can reach: executable/style content, native field defaults, and the
# fallback a browser running Leaf's scripts never draws (`noscript`). head is outside
# the browser's tree altogether, which starts at document.body — without it a page's
# <title> would be quotable and land nowhere.
UNQUOTABLE_TAGS = {"script", "style", "head", "textarea", "noscript"}


class _PassageParser:
    """A version's prose as the anchor pass reads it. `text` is the whole page collapsed
    the way a captured quote is; `owner[i]` is the ids enclosing text[i], outermost
    first, so a match can name the section it fell in and be re-read within it.

    `decided` is the outcome each suggestion stands under (`retirement_outcomes`). A
    decision retires a slot — the registry's `retired-when` names which outcome —
    and the browser's anchor pass reads the same key (`quotable` in readings/passages.js), so
    this reading drops it the same way. A decision that leaves its widget with nothing —
    a deletion accepted, an insertion refused — empties the wrapper too (`gone`),
    because an element showing nothing is one nobody can point at, however present its
    markup. `rewrites` is the user's current text per element whose element declaration
    records a verb as the body (`rewritten_bodies`): their words stand in the authored
    body's place, because replay writes exactly that into the DOM. Without either, the
    reading is the version as authored — every slot pending, every body Claude's.
    `additions` supplies the generated children in force from the same projection. They
    pass through the ordinary element reading at the end of their declared owner,
    including retirement, ancestry, and the fences around opaque widgets."""

    def __init__(
        self,
        registry=None,
        decided=None,
        rewrites=None,
        additions=None,
    ):
        self.registry = registry or {}
        self.decided = decided or {}
        self.rewrites = rewrites or {}
        self.additions = additions or {}
        # The collapsed run, one entry per character: a list, since `str +=` on an
        # attribute copies the whole string and makes a large page's reading quadratic.
        self.chars = []
        self.owner = []  # per character: the tuple of enclosing ids
        self.spans = {}  # id → [first, end): the characters it holds
        self.fences = set()  # indices a quote may not span
        self.breaks = set()  # indices of the spaces that end one block's words
        self.retired = {}  # id under a retired slot → the suggestion whose decision did it
        self.gone = {}  # decided id whose decision left it empty → the outcome that did it
        # id → the ids enclosing it, outermost first, itself last. Structure, not
        # words: an element is somewhere on the page whether or not it says
        # anything, which is what the containment questions downstream ask (see
        # `spoken`). Written for every id the markup carries, since a widget's
        # detail may name one the page holds outside the vocabulary.
        self.enclosing = {}
        self.bearing = (
            set()
        )  # ids still showing something: text under them, or a surviving child
        self.stack = []  # [{"tag", "key", "id", "added", "ids", "skip", "withheld", "silenced", "sub", "retired_by", "opaque", "editable", "fenced", "tb", "block"}]
        self._uid = 0
        self._block = None  # the block the last character came from
        self._space = False  # a separator waiting for a character to follow it
        self._break = False  # whether that separator ends a block
        self._holder = None  # the key of the node holding the last text written

    def _fresh(self) -> int:
        self._uid += 1
        return self._uid

    def _write(
        self,
        data: str,
        block: int,
        ids: tuple,
        holder: int | None = None,
        prose: bool = False,
    ) -> None:
        """Text into the collapsed run, one space per whitespace run and none leading.
        Where the text runs on from the last text in its block with no whitespace
        between, a space goes between them where `holder`, the key of the element or
        said value's span holding the text, is not the one that held the last text,
        neither stands in prose (a text block), and no closing mark follows or opening
        one precedes the meeting: the runtime's `shownApart`."""
        if data.strip():
            self.bearing.update(ids)
        edge = bool(self.chars) and block == self._block
        first = True
        if self.chars and block != self._block:
            self._space = self._break = True
        self._block = block
        start = len(self.chars)
        for ch in data:
            if ch in COLLAPSE_CHARS:
                self._space = bool(self.chars)
                continue
            if self._space:
                if self._break:
                    self.breaks.add(len(self.chars))
                self.chars.append(" ")
                self.owner.append(ids)
                self._space = self._break = False
            elif (
                edge
                and not prose
                and holder is not None
                and holder != self._holder
                and ch not in CLOSING
                and self.chars[-1] not in OPENING
            ):
                self.chars.append(" ")
                self.owner.append(ids)
            if first:
                self._holder = holder
                first = False
            edge = False
            self.chars.append(ch)
            self.owner.append(ids)
        if (end := len(self.chars)) > start:
            for wid in ids:
                self.spans.setdefault(wid, [start, end])[1] = end

    def _fence(self) -> None:
        """Words may stand here that this reading knows nothing about. Recorded as a
        position rather than written into the text, so `text` stays the page's own words
        and no quote can be built out of one."""
        self.fences.add(len(self.chars))

    def _close(self, frame: dict) -> None:
        """Everything an element's end does, whether it was written or inferred — an
        omitted </p> inside a widget still ends what the element was saying."""
        if additions := self.additions.get(frame["id"]):
            # The owner has just left the stack. Restore it while its declared
            # generated children pass through the ordinary passage rules, so
            # ancestry, retirement, text blocks, and widget fences stay shared.
            self.stack.append(frame)
            for child in additions:
                self.handle_starttag(
                    child["tag"], [("id", child["id"]), ("data-lf-added", "")]
                )
                self.handle_data(child["text"])
                self.handle_endtag(child["tag"])
            self.stack.pop()
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
        parent = self.stack[-1] if self.stack else None
        if tag == "br" and parent and not parent["skip"]:
            self._write(" ", parent["block"], parent["ids"])
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
        joins = tag in JOINS_WORDS_TAGS or bool(entry.get("inline"))
        block = parent["block"] if parent and joins else self._fresh()
        # An upgrade is opaque unless it keeps its own words (`verbatim`). Descendants
        # keep their own contracts.
        opaque = upgraded(self.registry, tag) and not entry.get("verbatim")
        editable = bool(parent and parent["editable"])
        if "contenteditable" in attrs_d:
            value = (attrs_d["contenteditable"] or "").lower()
            if value in {"", "true", "plaintext-only"}:
                editable = True
            elif value == "false":
                editable = False
        editing_boundary = editable != bool(parent and parent["editable"])
        # A slot a decision retired: its words left the page with the outcome the
        # registry names, and everything under it goes too. Looked up by the parent's
        # own id — the same child-of-suggestion shape as the browser's selector.
        retired_by = (parent["retired_by"] if parent else None) or (
            parent["id"]
            if parent
            and (retiring := entry.get("retired-when"))
            and self.decided.get(parent["id"]) == retiring
            else None
        )
        # A wall this element raises itself: its words are off the user's page, whatever
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
        silenced = bool(
            (
                parent
                and (
                    parent["silenced"] or (parent["skip"] and parent["sub"] is not None)
                )
            )
            or own_wall
        )
        # Data notation is withheld, but a declared prose member is authored text
        # the widget preserves independently of that notation. Only a direct member
        # reopens that reading; nesting a member tag in source does not.
        prose_member = bool(
            parent
            and parent["tag"] in entry.get("owners", ())
            and entry.get("content") == "markup"
        )
        withheld = bool(
            (parent and parent["withheld"] and not prose_member)
            or (opaque and body_is_data(entry))
        )
        # A surviving child keeps its parent on the page even where it holds no text —
        # a kept slot whose only content is an image. The text case marks every
        # enclosing id in _write.
        if parent and not silenced:
            self.bearing.add(parent["id"])
        # A body the user rewrote. `rewritten_bodies` already resolved the verb
        # through this element's `verbs`, so an id in the dict is the whole test:
        # the fold decides, this pass only applies.
        sub = self.rewrites.get(attrs_d.get("id")) if not silenced else None
        frame = {
            "tag": tag,
            # The element's identity for this whole reading, which `_write` compares
            # long after the element closed: a parser frame dies with its element,
            # and Python reuses a dead object's `id()`.
            "key": self._fresh(),
            "id": attrs_d.get("id"),
            "added": "data-lf-added" in attrs_d,
            "ids": ids,
            "skip": silenced or sub is not None or withheld,
            "withheld": withheld,
            "silenced": silenced,
            "sub": sub,
            "retired_by": retired_by,
            "opaque": opaque,
            "editable": editable,
            "fenced": opaque or bool(parent and parent["opaque"]) or editing_boundary,
            # Whether its words are prose: it or an element around it is a text block.
            "tb": tag in TEXT_BLOCK_TAGS or bool(parent and parent["tb"]),
            # The element its words are read in, as the runtime's walk carries it
            # (`enter`, `words`): fresh for every element whose words stand apart, a
            # text block among them, its parent's for one that joins them
            # (`JOINS_WORDS_TAGS`), so `a<em>b</em>c` reads as one run under a <div> as
            # under a <p>, `<div>a</div><div>b</div>` as two, and a <button>'s label
            # apart from the words beside it.
            "block": block,
        }
        if frame["fenced"]:
            self._fence()
        if retired_by and frame["id"]:
            self.retired[frame["id"]] = retired_by
        self.stack.append(frame)
        if sub is not None:
            # The body's own write path, so the words beside the element's edge meet
            # as the screen shows them — no fence, nothing withheld.
            _verb, their_text = sub
            if entry.get("content") == "markdown":
                frame["skip"] = False
                feed_markdown(self, their_text)
                frame["skip"] = True
            else:
                self._write(
                    their_text, frame["block"], frame["ids"], frame["key"], frame["tb"]
                )

    def handle_data(self, data):
        frame = self.stack[-1] if self.stack else None
        if not frame:
            return
        data = shown_words(
            data, self.registry.get(frame["tag"], {}), added=frame["added"]
        )
        if not frame["skip"]:
            self._write(data, frame["block"], frame["ids"], frame["key"], frame["tb"])

    def handle_endtag(self, tag):
        # Every caller walks a parsed tree or replays a declared child, so ends arrive
        # balanced and this one closes the innermost open element.
        if tag in VOID_TAGS:
            return
        self._close(self.stack.pop())


class Passages(NamedTuple):
    """A version's words, and what a search over them needs to know."""

    text: str  # collapsed the way a captured quote is
    owner: list  # per character: the tuple of enclosing ids, outermost first
    fences: set  # indices a quote may not span: where a module may write
    retired: dict  # id under a retired slot → the suggestion whose decision did it
    gone: dict  # decided id whose decision left it empty → the outcome that did it
    enclosing: dict  # id → the ids enclosing it, outermost first, itself last
    breaks: set  # indices of the spaces that end one block's words and start the next's
    # id → the half-open range of characters inside it, for each id with text in it.
    # An element is contiguous in document order, so its characters are too, which
    # is what lets a search be scoped by slicing.
    spans: dict


def _walk(parser: "_PassageParser", node) -> None:
    """Hand one parsed node and its subtree to the passage reader, in document order:
    a Markdown-bodied element reads its body as rendered Markdown."""
    if isinstance(node, turbohtml.Text):
        parser.handle_data(node.data)
        return
    if not isinstance(node, turbohtml.Element):
        return
    parser.handle_starttag(
        node.tag,
        [
            (name, " ".join(value) if isinstance(value, list) else value)
            for name, value in node.attrs.items()
        ],
    )
    if parser.registry.get(node.tag, {}).get("content") == "markdown":
        body = pre_body(node)
        assert body is not None
        feed_markdown(parser, body)
    else:
        for child in node.children:
            _walk(parser, child)
    parser.handle_endtag(node.tag)


def page_passages(
    document: SourceDocument,
    registry=None,
    decided=None,
    rewrites=None,
    additions=None,
) -> Passages:
    parser = _PassageParser(registry, decided, rewrites, additions)
    for child in document.tree.children:
        _walk(parser, child)
    return Passages(
        "".join(parser.chars),
        parser.owner,
        parser.fences,
        parser.retired,
        parser.gone,
        parser.enclosing,
        parser.breaks,
        {wid: (lo, hi) for wid, (lo, hi) in parser.spans.items()},
    )


class Spoken(NamedTuple):
    """What one element says, and where it sits."""

    words: str  # the words under it, as the anchor pass reads them
    within: tuple  # the ids enclosing it, outermost first, itself last


# An id this version doesn't carry — nothing said, and nowhere it sits. An element
# that is here and silent is not this: it has a chain, which is what lets a fold
# reach a card holding one diagram.
EMPTY = Spoken("", ())


HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
SECTIONS = frozenset({"section", "article"})


def _text(node, root: bool = True) -> str:
    """A node's words as a name reads them: a popover's below it, such as a gloss's
    explanation, stand apart until shown and name nothing (readings/passages.js, `named`)."""
    if isinstance(node, str):
        return node
    if not root and "popover" in node["attrs"]:
        return ""
    return "".join(_text(child, root=False) for child in node["content"])


def _registered(node: dict, registry: dict) -> bool:
    return is_element_name(node["tag"]) and node["tag"] in registry


def caption_node(node: dict) -> dict | None:
    """The caption that names plain markup: a disclosure's first <summary>, an
    <hgroup>'s heading, or the heading a section or article opens with, alone or in an
    <hgroup>. No other element is named by a heading inside it, and a <strong> names
    nothing."""
    elements = [child for child in node["content"] if not isinstance(child, str)]
    if node["tag"] == "details":
        return next((child for child in elements if child["tag"] == "summary"), None)
    if node["tag"] == "hgroup":
        return next((child for child in elements if child["tag"] in HEADINGS), None)
    if node["tag"] not in SECTIONS:
        return None
    first = next((child for child in node["content"] if not _blank(child)), None)
    if first is None or isinstance(first, str):
        return None
    if first["tag"] == "hgroup":
        return caption_node(first)
    return first if first["tag"] in HEADINGS else None


def _blank(node) -> bool:
    return isinstance(node, str) and not node.strip()


def element_name(node: dict, registry: dict) -> str:
    """What the authoring contract calls an element away from itself, in the words the
    author wrote: a widget's `label` attribute (`contract.NAME_ATTRIBUTE`), else plain
    markup's caption. A widget takes no name from its markup. The browser's
    `addressableName` reads the same rule off the live page; `tests/name_cases.json`
    holds both to the same cases."""
    if _registered(node, registry):
        return (node["attrs"].get(NAME_ATTRIBUTE) or "").strip()
    caption = caption_node(node)
    return collapse(_text(caption)) if caption else ""


def enclosing_of(spk: dict) -> dict:
    """The containment half of a `spoken` reading, keyed the same.

    What liveness asks of a page is where an element sits, never what it says —
    so a caller holding the whole reading hands over the half that answers."""
    return {wid: said.within for wid, said in spk.items()}


def enclosing_ids(document: SourceDocument) -> dict:
    """id → the ids enclosing it, outermost first, itself last, with no
    vocabulary loaded.

    The same answer `spoken` gives against the real layer: the walk records where
    an element sits off the tag stack, before anything asks the registry what it
    shows. Words are the other half and the vocabulary's word entirely, so this
    is the reading for a caller that may not raise on the registry gate — it can
    have where an element sits, and must not ask what it says.

    A document is immutable, so the walk runs once per document: checking a page
    reads its containment once for each live sample it declares."""
    if (held := _ENCLOSING.get(document)) is None:
        held = _ENCLOSING[document] = page_passages(document, {}).enclosing
    return held


_ENCLOSING: "weakref.WeakKeyDictionary[SourceDocument, dict]" = (
    weakref.WeakKeyDictionary()
)
