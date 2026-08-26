"""Text-passage readings of authored HTML."""

import re
from html.parser import HTMLParser
from typing import NamedTuple

from .registry import visual_parts
from .structure import VOID_TAGS, implicit_closes, parse_structure

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
# How much of the surrounding text an anchor stores to tell two identical passages
# apart. The browser's capture states the same number and a test holds the two equal,
# so this side cannot come to store a neighbourhood the browser would never have
# written. The quote itself is stored whole, however long the passage: it is the extent
# the page marks, and a cap on it was a comment quietly made on less than was quoted
# (see selectionAnchor, wherever the capture lives).
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
    html: str,
    registry,
    quote: str,
    section: str,
    decided=None,
    rewrites=None,
    part: str | None = None,
) -> dict:
    """The anchor a quote makes, written the way a selection's is. Raises ValueError with
    what to do about it — a quote the file doesn't hold, or holds twice, is a question
    with an answer, and asking now beats posting a comment that lands nowhere.

    `decided` and `rewrites` make this the reading the user is looking at rather
    than the version as authored: a slot their decision retired is off the page, and a
    body their edit rewrote holds their words — so an anchor is met here the way it
    would land there, instead of detaching in front of them."""
    if part and not section:
        raise ValueError("--part needs --section to name its visual")
    if part and quote:
        raise ValueError("--part names a visual box; use it without --quote")
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
    if part:
        record = parse_structure(html).by_id.get(section)
        available = visual_parts(record or {}, registry)
        if not available:
            raise ValueError(
                f"§ {section} declares no commentable visual parts in this version"
            )
        if part not in available:
            raise ValueError(
                f"§ {section} has no visual part {part!r}; known: {list(available)}"
            )
        return {"section": section, "visual": part}
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
