"""Capture authored anchor requests against the file-side passage reading."""

import bisect
import functools
import itertools
from typing import NamedTuple

from .passages import collapse, page_passages
from .registry.contract import visual_parts
from .registry.kernel import kernel_passages
from .structure import SourceDocument

# Initial context shared with browser capture. The CLI already requires a unique
# quote; a browser selection identifies an occurrence and may grow this context to
# its semantic fences until the shared resolver identifies that exact span. Both
# readers accept that complete context, and neither guesses by document order.
CONTEXT = kernel_passages()["context"]


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
        if ch.isspace():
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
    reading of it matches: the file side of `passages.js.scan`. A copy past a fence is
    no copy, since the page has words there this text doesn't, but it takes its place
    in order: the next copy starts past it. An empty quote names no passage, as in the
    browser's `findQuote`."""
    words = quote.split()
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


def _context(passages, lo: int, hi: int) -> tuple[str, str]:
    """The trimmed words before `lo` and after `hi`, each reaching only to the nearest
    passage-cell fence: the file side of `passages.js.neighbourhood`, which capture
    stores and resolution compares against. The text is collapsed, so the space is
    the only collapse character left to trim; Python's own whitespace is wider."""
    text, fences = passages.text, passages.fences
    before = text[max([0, *[f for f in fences if f <= lo]]) : lo].strip(" ")
    after = text[hi : min([len(text), *[f for f in fences if f >= hi]])].strip(" ")
    return before, after


def resolve_quote(passages, anchor: dict) -> int | None:
    """Resolve a stored quote by exact context, or a sole surviving occurrence.

    This is the file side of `passages.js.findQuote`: document order never
    disambiguates repeated words, and a passage-cell fence cannot be crossed.
    An observation already detached at capture cannot become exact by losing siblings.
    """
    if anchor.get("detached"):
        return None
    quote = collapse(anchor["quote"])
    lo, hi = 0, len(passages.text)
    if section := anchor.get("section"):
        span = passages.spans.get(section)
        if span is None:
            return None
        lo, hi = span
    hits = occurrences(passages, quote, lo, hi)
    exact = []
    for start, end in hits:
        before, after = _context(passages, start, end)
        prefix, suffix = anchor.get("prefix", ""), anchor.get("suffix", "")
        if (before.endswith(prefix) if prefix else not before) and (
            after.startswith(suffix) if suffix else not after
        ):
            exact.append(start)
    if len(exact) == 1:
        return exact[0]
    return hits[0][0] if not exact and len(hits) == 1 else None


def capture_anchor(
    document: SourceDocument,
    registry,
    quote: str,
    section: str | None,
    decided=None,
    rewrites=None,
    part: str | None = None,
    additions: dict | None = None,
) -> dict:
    """The anchor a quote makes, written the way a selection's is. Raises ValueError with
    what to do about it — a quote the file doesn't hold, or holds twice, is a question
    with an answer, and asking now beats posting a comment that lands nowhere.

    A refusal about a quote or a section names what the reading found and a recourse in
    the reader's terms — quote more of the surrounding text, or name the section. Only a
    refusal about a CLI-only input, such as `--part`, names its flag.

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
    text = passages.text
    owner = passages.owner
    retired = passages.retired
    gone = passages.gone
    enclosing = passages.enclosing
    if section:
        # Against the structure, not the text: an element anchor is the one a click makes
        # on a diagram or an image, and those hold no text to look for.
        if section not in enclosing:
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
        return {"section": section, "visual": part}
    if not quote:
        return {"section": section}

    wanted = collapse(quote)
    lo_bound, hi_bound = 0, len(text)
    if section:
        span = passages.spans.get(section)
        if span is None:
            raise ValueError(
                f"§ {section} holds no quotable text — a widget's data body is its source, "
                "not its words. Anchor on the element itself, without a quote."
            )
        lo_bound, hi_bound = span
    where = "the page" if not section else f"§ {section}"
    hits = occurrences(passages, wanted, lo_bound, hi_bound)
    if not hits:
        raise ValueError(
            f"{where} doesn't say {wanted!r}; quote the words this version shows, "
            "or name the section"
        )
    if len(hits) > 1:
        around = [
            f"  - …{text[max(lo_bound, start - 30) : end + 30]}…"
            for start, end in hits[:4]
        ]
        if len(hits) > len(around):
            around.append(f"  - …and {len(hits) - len(around)} more")
        raise ValueError(
            f"{where} says {wanted!r} {len(hits)} times, so this quote names no one "
            "passage. Quote more of the surrounding text, or name the section it sits "
            "in:\n" + "\n".join(around)
        )

    lo, hi = hits[0]
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
    before, after = _context(passages, lo, hi)
    prefix, suffix = before[-CONTEXT:], after[:CONTEXT]
    return {
        "section": section,
        "quote": wanted,
        **({"prefix": prefix} if prefix else {}),
        **({"suffix": suffix} if suffix else {}),
    }
