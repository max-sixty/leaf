"""Text-passage readings of authored HTML."""

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple

from .files import latest_revision, revision_path
from .structure import VOID_TAGS, implicit_closes

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
#               opaque: a diagram body is a picture by the time it is read.
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


# What a text node's "block" resolves to: one space goes wherever two runs of text sit in
# different blocks, and none where they share one, so `<p>a</p><p>b</p>` reads "a b" and
# `set<em>up</em>` reads "setup". The runtime spells the same list as a selector
# (TEXT_BLOCK), and the two are held equal by a test rather than by this sentence — a
# tag one side calls a block and the other does not gives the two readings different
# text, which is every quote-shaped thing at once.
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


def enclosing_of(spk: dict) -> dict:
    """The containment half of a `spoken` reading, keyed the same.

    What liveness asks of a page is where an element sits, never what it says —
    so a caller holding the whole reading hands over the half that answers."""
    return {wid: said.within for wid, said in spk.items()}


def enclosing_ids(html: str) -> dict:
    """id → the ids enclosing it, outermost first, itself last, with no
    vocabulary loaded.

    The same answer `spoken` gives against the real layer: the walk records where
    an element sits off the tag stack, before anything asks the registry what it
    shows. Words are the other half and the vocabulary's word entirely, so this
    is the reading for a caller that may not raise on the registry gate — it can
    have where an element sits, and must not ask what it says."""
    return page_passages(html, {}).enclosing


def active_enclosing(page_dir: Path) -> dict:
    """Where every id sits on the page the reader is looking at.

    The newest valid revision is the live page. A page with no valid revision has
    nowhere for an element to sit."""
    try:
        revision = latest_revision(page_dir)
    except SystemExit:
        return {}
    html = revision_path(page_dir, revision).read_text(encoding="utf-8")
    return enclosing_ids(html)
