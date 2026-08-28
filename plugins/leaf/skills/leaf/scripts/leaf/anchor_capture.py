"""Capture authored anchor requests against the file-side passage reading."""

from .passages import collapse, page_passages, section_span
from .registry import visual_parts
from .structure import parse_structure

# How much of the surrounding text an anchor stores to tell two identical passages
# apart. The browser's capture states the same number and a test holds the two equal,
# so this side cannot come to store a neighbourhood the browser would never have
# written. The quote itself is stored whole, however long the passage: it is the extent
# the page marks, and a cap on it was a comment quietly made on less than was quoted
# (see selectionAnchor, wherever the capture lives).
CONTEXT = 24


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
