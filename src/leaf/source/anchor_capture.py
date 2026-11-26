"""Capture authored anchor requests against the page's structure, and check a visual
part an agent names against what the page drew of its visual.

The browser is the only reader of anchored words: it finds a stored quote in the page
it draws (`readings/anchor-resolution.js`, `resolveAnchor`), and where it can't place
the words once, it shows the thread on the quote's section, or detaches it where the
anchor names none. So a capture here checks only what the files settle, the section
an agent names, and stores the quote it was given. The file's reading of the page
(`passages.page_passages`) stands in for the drawn page only as advice: it names the
section that encloses words it finds once, says where it finds them zero or several
times (`unplaced-quote`), and tells a revision which quotes it took out (`copies`,
`source_history.revision_reanchors`). A miss costs a note or a move the browser's
fallback makes anyway, so the reading is held to no exact parity with the browser's."""

import bisect
import functools
import itertools
from typing import NamedTuple

from leaf.base.findings import Finding
from leaf.source.passages import COLLAPSE_CHARS, collapse, page_passages
from leaf.source.registry.contract import visual_parts
from leaf.source.structure import SourceDocument


def enclosing_section(owner: list, lo: int, hi: int):
    """The innermost id in this reading that encloses every character of [lo, hi):
    the file's side of the section `selectionAnchor` takes from the nearest id around
    the passage's common ancestor."""
    first, last = owner[lo], owner[hi - 1]
    shared = 0
    while shared < min(len(first), len(last)) and first[shared] == last[shared]:
        shared += 1
    return first[shared - 1] if shared else None


class _Letters(NamedTuple):
    """A reading's text without its spaces: each letter, where it stands in the text,
    and what parts it from the letter before (0 nothing, 1 an edge, 2 a space)."""

    letters: str
    places: list
    parted: bytes


@functools.lru_cache(maxsize=16)
def _letters(text: str, edges: frozenset, soft: frozenset) -> _Letters:
    letters, places, parted = [], [], bytearray()
    for i, ch in enumerate(text):
        if ch in COLLAPSE_CHARS:
            continue
        if not places:
            kind = 0
        elif i > places[-1] + 1:
            # A space parts them, unless every space between is one an edge shows as.
            between = range(places[-1] + 1, i)
            kind = 1 if all(at in soft for at in between) else 2
        else:
            kind = 1 if i in edges else 0
        parted.append(kind)
        letters.append(ch)
        places.append(i)
    return _Letters("".join(letters), places, bytes(parted))


def occurrences(passages, quote: str, lo: int, hi: int) -> list[tuple[int, int]]:
    """Where `quote` stands in the reading's text[lo:hi], as absolute [start, end)
    spans, in order: its letters, a space or an edge between two of them where the quote
    has a space, and nothing or an edge where it has none. An edge is where two inline
    elements meet, and only the page's CSS says whether a word ends there, so either
    reading of it matches: the file side of `readings/passages.js.scan`. A copy past a fence is
    no copy, since the page has words there this text doesn't, but it takes its place
    in order: the next copy starts past it. An empty quote names no passage, as in the
    browser's `findQuote`."""
    words = [word for word in collapse(quote).split(" ") if word]
    if not words:
        return []
    letters = "".join(words)
    gaps = set(itertools.accumulate(len(word) for word in words[:-1]))
    view = _letters(passages.text, passages.edges, passages.soft)
    first = bisect.bisect_left(view.places, lo)
    stop = bisect.bisect_left(view.places, hi)
    found = []
    at = view.letters.find(letters, first, stop)
    while at != -1:
        if all(
            (view.parted[at + j] != 0) if j in gaps else (view.parted[at + j] != 2)
            for j in range(1, len(letters))
        ):
            start, end = view.places[at], view.places[at + len(letters) - 1] + 1
            if not any(start < f < end for f in passages.fences):
                found.append((start, end))
            at = view.letters.find(letters, at + len(letters), stop)
        else:
            at = view.letters.find(letters, at + 1, stop)
    return found


def copies(passages, quote: str, section: str | None) -> list[tuple[int, int]]:
    """Where the file's reading finds `quote` (`occurrences`), within `section` where
    one is named, or nowhere where the section holds no words the file reads, as a
    widget's data body doesn't."""
    span = passages.spans.get(section) if section else (0, len(passages.text))
    return occurrences(passages, collapse(quote), *span) if span else []


def capture_anchor(
    document: SourceDocument,
    registry,
    quote: str,
    section: str | None,
    decided=None,
    rewrites=None,
    part: str | None = None,
    additions: dict | None = None,
) -> tuple[dict, Finding | None]:
    """The anchor a target makes, written the way a selection's is, and the note to
    give beside the thread, or None. Raises ValueError with what to do about a
    structural target the files refuse: a `section` this version doesn't hold, one a
    decision took off the page, or a `part` its visual doesn't declare. A refusal names
    what the reading found and a recourse in the reader's terms; only a refusal about a
    CLI-only input, such as `--part`, names its flag.

    A quote is never refused for its words, since only the drawn page says whether it
    shows them (`resolveAnchor`). The anchor holds the quote and `section`, or, where
    the agent named none, the innermost id enclosing the one place the file's reading
    finds the words, else no section. Where that reading finds them zero or several
    times, the note says where the page shows the thread if the drawn page doesn't show
    them once either.

    A `part` passes here where its visual's declaration admits the id; whether the page
    draws it is `drawn_part`'s to say, since only a drawing of the page knows.

    `decided` and `rewrites` make this the reading the user is looking at rather
    than the version as authored: a slot their decision retired is off the page, and a
    body their edit rewrote holds their words. `additions` supplies the declared
    children of events in force, so user-created elements are reachable before
    an author incorporates them in source."""
    if part and not section:
        raise ValueError("--part needs --section to name its visual")
    if part and quote:
        raise ValueError("--part names a visual box; use it without --quote")
    passages = page_passages(document, registry, decided, rewrites, additions)
    retired, gone = passages.retired, passages.gone
    if section:
        # Against the structure, not the text: an element anchor is the one a click makes
        # on a diagram or an image, and those hold no text to look for.
        if section not in passages.enclosing:
            raise ValueError(f"no element id {section!r} in this version")
        if section in retired:
            assert decided is not None
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
        record = document.by_id.get(section)
        available = visual_parts(record or {}, registry)
        if not available:
            raise ValueError(
                f"§ {section} declares no commentable visual parts in this version"
            )
        if part not in available:
            raise ValueError(f"§ {section} has no visual part {part!r}; {available}")
        return {"section": section, "visual": part}, None
    if not quote:
        return {"section": section}, None

    wanted = collapse(quote)
    if not wanted:
        raise ValueError("the quote holds no words; quote the words the passage shows")
    hits = copies(passages, wanted, section)
    if not section and len(hits) == 1:
        section = enclosing_section(passages.owner, *hits[0])
    # No context: the agent named words, not one copy of them, so the page takes the
    # words where it shows them once (`findQuote`, an absent side).
    anchor = {"section": section or None, "quote": wanted}
    if len(hits) == 1:
        return anchor, None
    return anchor, Finding(
        "unplaced-quote",
        values={"section": section, "quote": wanted, "found": len(hits)},
    )


class Drawing(NamedTuple):
    """What one drawing of a version read of each visual, by the visual's id, as the
    render reading keeps it (`render_reading.READING`, `visuals`); None where no
    browser could draw the page. `when` names the drawing in a message's words, such
    as "when the page was last checked"."""

    visuals: dict[str, dict] | None
    when: str


def drawn_part(section: str, part: str, drawing: Drawing) -> Finding | None:
    """What `drawing` says of a thread on `part` in the visual `section`, whose
    declaration admits the id (`capture_anchor`), as the browser resolves its anchor
    (`resolveAnchor`): the note to give beside the thread, or None.

    - The visual drew the part: None.
    - It didn't, and the page puts the thread on the whole visual until the visual
      draws the part (`whole`): a note naming the parts it drew, or None where it
      lists no parts, as a chart lists none of the points it finds by id when asked,
      since there is no list to offer.
    - It didn't, and the page would show the thread nowhere: a ValueError naming the
      parts it drew and the way to put the thread on the whole visual, which every
      visual takes, so the agent can always post.
    - No drawing read the visual: a note saying the part went unchecked."""
    visual = (drawing.visuals or {}).get(section)
    if visual is None:
        return Finding("unchecked-part", values={"section": section, "part": part})
    drew = [drawn["id"] for drawn in visual["parts"]]
    if part in drew or (visual["whole"] and not drew):
        return None
    if visual["whole"]:
        return Finding(
            "part-on-whole",
            values={
                "section": section,
                "part": part,
                "when": drawing.when,
                "drew": drew,
            },
        )
    named = (
        f"it drew {', '.join(drew)}. Name one of those, or leave"
        if drew
        else "it drew no part at all. Leave"
    )
    raise ValueError(
        f"§ {section} drew no part {part!r} {drawing.when}; {named} out --part to put "
        "the thread on the whole visual"
    )
