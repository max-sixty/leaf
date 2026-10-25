"""Markdown transcript of a page's exchange."""

from collections.abc import Iterator
from pathlib import Path

from leaf.event_log import read_events
from leaf.events import build_threads, is_reaction, taken_back
from leaf.files import revision_label
from leaf.gesture_words import GestureWords, revisions_on_disk
from leaf.registry.kernel import verb_writers
from leaf.registry.reactions import reaction_tokens
from leaf.registry.schema import json_value
from leaf.registry.storage import active_registry
from leaf.revision_artifact import latest_title, read_revision
from leaf.schema import agent_name

# A quote as a transcript names it. The anchor stores the passage whole, because that
# is the extent the page marks; a transcript is prose someone pastes into an MR, where
# a paragraph of quoted page inside every thread head buries the exchange it is there
# to carry. Both ends rather than the opening alone: a passage is identified by where
# it starts and where it stops, and an elision that keeps only the head reads as a
# short quote rather than as a long one shown briefly.
QUOTE_SHOWN = 240


def shown(quote: str) -> str:
    if len(quote) <= QUOTE_SHOWN:
        return quote
    half = QUOTE_SHOWN // 2
    return f"{quote[:half].rstrip()} … {quote[-half:].lstrip()}"


def _versions(events: list) -> Iterator[str]:
    notes = [e for e in events if e["kind"] == "note"]
    if notes:
        yield "\n### Versions\n"
        for e in notes:
            yield f"- v{e['version']}: {e['text']}"


def _edits(page_dir: Path, events: list, registry: dict) -> Iterator[str]:
    # The user's direct edits are outcomes of the exchange; without them the transcript
    # understates it whenever a changelog note doesn't restate them. So
    # is a version taking one back, which is the same understatement the other
    # way round — an edit shown as final that a later version overruled.
    # Widget-agnostic rendering: verb + detail pairs, against the version edited,
    # then what the ids it names say there. The widget's own words are left out: it
    # is named by its id, and a body edit's detail already carries the new words.
    withdrawn = taken_back(events)
    words = (
        GestureWords(events, registry, revisions_on_disk(page_dir))
        if registry
        else None
    )
    edits = [
        e
        for e in events
        if e["kind"] in verb_writers() or (e["kind"] == "note" and e.get("restated"))
    ]
    if edits:
        yield "\n### Edits\n"
        for e in edits:
            if e["kind"] == "note":
                for wid in e["restated"]:
                    yield f"- `{wid}`: rewritten by v{e['version']}, retracting what was decided on it"
                continue
            detail = " ".join(f"{k}={json_value(v)}" for k, v in e["detail"].items())
            verb = f"{e['action']} {detail}".strip()  # a bare answer carries no detail
            said = words.says(e) if words else {}
            said.pop(e["widget"], None)
            if said:
                verb += " — " + "; ".join(f"“{shown(w)}”" for w in said.values())
            if e["kind"] == "report":
                # A worker's provisional news is an outcome too, under its own name.
                yield (
                    f"- `{e['widget']}`: {e.get('agent', 'a worker')} reported "
                    f"{verb} (on {revision_label(events, e['revision'])})"
                )
            else:
                # An edit the user took back is an outcome too, and the same
                # understatement the other way round: shown as it stands it reads
                # as final, and left out it reads as never made.
                took = " — taken back" if e["id"] in withdrawn else ""
                yield (
                    f"- `{e['widget']}`: {verb} "
                    f"(on {revision_label(events, e['revision'])}){took}"
                )


def _published_within(
    page_dir: Path,
    registry: dict,
    revision: int | None,
) -> dict:
    # Against the active revision — the page as it now stands, which is what a
    # transcript is an account of. A page with no valid revision has no reading.
    if revision is None:
        return {}
    return read_revision(page_dir, revision).under(registry).within


def _thread_heading(thread: dict) -> str:
    anchor = thread["detached_from"] or thread["anchor"] or {}
    if anchor.get("quote"):
        head = f"> “{shown(anchor['quote'])}”"
    elif anchor.get("section"):
        head = f"> § {anchor['section']}"
        if anchor.get("visual"):
            head += f" · {anchor['visual']}"
    else:
        head = "> (page-level)"
    if anchor.get("part"):
        head += f" · {anchor['part']}"
    if anchor.get("detached"):
        head += "  — passage not identified"
    if thread["detached_from"]:
        head += "  — no longer in this version"
    if thread["root"].get("about") == "design":
        head += "  — about the design"
    closed = thread["resolved"]
    if closed and closed["author"] == "agent":
        # Named where the user was not the one who closed it. A transcript is
        # read away from the page, so the panel's own line saying so is not in it.
        head += "  — resolved by " + agent_name(closed)
    elif closed:
        head += "  — resolved"
    return head


def _message(message: dict, registry: dict) -> str:
    who = agent_name(message) or "User"
    if is_reaction(message):
        # A mark rather than a turn: the token's glyph and word.
        entry = reaction_tokens(registry).get(message["token"]) or {}
        said = f"{entry.get('glyph', '')} {message['token']}".strip()
        return f"- **{who}** reacted: {said}"
    edited = " *(edited)*" if message.get("edited") else ""
    body = message.get("text", "")
    if drawing := message.get("drawing"):
        over = f" over “{drawing['says']}”" if drawing.get("says") else ""
        body += f"\n_(drawing attached{over})_"
    if message.get("markup"):
        body += f"\n{message['markup']}"
    return f"- **{who}**{edited}: " + body.replace("\n", "\n  ")


def _threads(events: list, within: dict, registry: dict) -> Iterator[str]:
    threads = build_threads(events, within)
    if threads:
        yield "\n### Threads\n"
    for thread in threads.values():
        yield _thread_heading(thread)
        for message in thread["msgs"]:
            yield _message(message, registry)
        yield ""


def cmd_transcript(page_dir: Path) -> str:
    """The page's exchange as Markdown, for reuse in a PR description."""
    events = read_events(page_dir)
    registry = active_registry(page_dir) or {}
    revision, title = latest_title(page_dir)
    within = _published_within(page_dir, registry, revision)
    return "\n".join(
        [
            f"## Leaf: {title or page_dir.name}",
            *_versions(events),
            *_edits(page_dir, events, registry),
            *_threads(events, within, registry),
        ]
    )
