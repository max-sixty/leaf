"""Raw event and Markdown transcript readings."""

import os
import signal
import sys
from pathlib import Path

from leaf.event_log import follow_events, jsonl_line, read_events
from leaf.events import build_threads, is_reaction, standing_approvals, taken_back
from leaf.files import latest_revision, revision_label
from leaf.gesture_words import GestureWords
from leaf.passages import active_enclosing, enclosing_of, spoken
from leaf.registry.reactions import reaction_tokens
from leaf.registry.storage import active_registry
from leaf.structure import parse_revision
from leaf.thread_context import (
    thread_memberships,
    thread_roots,
    thread_structure,
    thread_widgets,
)


def cmd_events(page_dir: Path, after: int, conversation: str | None = None) -> None:
    events = read_events(page_dir)
    if conversation is not None:
        within = active_enclosing(page_dir)
        threads = build_threads(events, within)
        if conversation not in threads:
            sys.exit(f"unknown conversation id {conversation!r}")
        roots = thread_roots(events)
        structure = thread_structure(events)
        memberships = thread_memberships(
            events,
            roots,
            thread_widgets(structure, roots),
            within,
        )
        events = [event for event in events if conversation in memberships[event["id"]]]
    for event in events:
        if event["seq"] > after:
            print(jsonl_line(event))


def cmd_follow_events(page_dir: Path, after: int) -> None:
    """Print each event after `after`, then each one appended, until stopped.

    A follower is stopped by its consumer, so a stop is the ordinary end rather
    than a failure: SIGINT and SIGTERM exit 0, and so does a reader that goes away,
    after which nothing more can be said to it. Each line is flushed as it is
    printed, since a follower's stdout is a pipe whose reader waits on that line.
    """
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        for event in follow_events(page_dir, after):
            print(jsonl_line(event), flush=True)
    except KeyboardInterrupt:
        sys.exit(0)
    except BrokenPipeError:
        # The interpreter flushes stdout again on exit, into the same closed pipe.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
    except FileNotFoundError as error:
        sys.exit(str(error))


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


def _revision_title(page_dir: Path) -> tuple[int | None, str]:
    """The active revision and its authored title, if the page has one."""
    title = ""
    revision = latest_revision(page_dir)
    if revision is not None:
        title = parse_revision(page_dir, revision).title.strip()
    return revision, title


def _print_versions(events: list) -> None:
    notes = [e for e in events if e["kind"] == "note"]
    if notes:
        print("\n### Versions\n")
        for e in notes:
            print(f"- v{e['version']}: {e['text']}")


def _print_edits(page_dir: Path, events: list, registry: dict) -> None:
    # The user's direct edits are outcomes of the exchange; without them the transcript
    # understates it whenever a changelog note doesn't restate them. So
    # is a version taking one back, which is the same understatement the other
    # way round — an edit shown as final that a later version overruled.
    # Widget-agnostic rendering: verb + detail pairs, against the version edited,
    # then what the ids it names say there. The widget's own words are left out: it
    # is named by its id, and a body edit's detail already carries the new words.
    withdrawn = taken_back(events)
    words = GestureWords(page_dir, events, registry) if registry else None
    edits = [
        e
        for e in events
        if e["kind"] in {"action", "report"}
        or (e["kind"] == "note" and e.get("restated"))
    ]
    if edits:
        print("\n### Edits\n")
        for e in edits:
            if e["kind"] == "note":
                for wid in e["restated"]:
                    print(
                        f"- `{wid}`: rewritten by v{e['version']}, retracting what was decided on it"
                    )
                continue
            detail = " ".join(f"{k}={v}" for k, v in e["detail"].items())
            verb = f"{e['action']} {detail}".strip()  # a bare answer carries no detail
            said = words.says(e) if words else {}
            said.pop(e["widget"], None)
            if said:
                verb += " — " + "; ".join(f"“{shown(w)}”" for w in said.values())
            if e["kind"] == "report":
                # A worker's provisional news is an outcome too, under its own name.
                print(
                    f"- `{e['widget']}`: {e.get('agent', 'a worker')} reported "
                    f"{verb} (on {revision_label(events, e['revision'])})"
                )
            else:
                # An edit the user took back is an outcome too, and the same
                # understatement the other way round: shown as it stands it reads
                # as final, and left out it reads as never made.
                took = " — taken back" if e["id"] in withdrawn else ""
                print(
                    f"- `{e['widget']}`: {verb} "
                    f"(on {revision_label(events, e['revision'])}){took}"
                )


def _published_reading(
    page_dir: Path,
    registry: dict,
    revision: int | None,
) -> dict:
    # Against the active revision — the page as it now stands, which is what a
    # transcript is an account of. A page with no valid revision has no reading.
    if revision is None:
        return {}
    return spoken(parse_revision(page_dir, revision), registry)


def _thread_heading(thread: dict) -> str:
    anchor = thread["detached_from"] or thread["anchor"] or {}
    if anchor.get("quote"):
        head = f"> “{shown(anchor['quote'])}”"
    elif anchor.get("section"):
        head = f"> § {anchor['section']}"
        if anchor.get("visual"):
            head += f" · {anchor['visual']}"
        if anchor.get("part"):
            head += f" · {anchor['part']}"
    else:
        head = "> (page-level)"
    if thread["detached_from"]:
        head += "  — no longer in this version"
    if thread["root"].get("about") == "design":
        head += "  — about the design"
    closed = thread["resolved"]
    if closed and closed["author"] == "agent":
        # Named where the user was not the one who closed it. A transcript is
        # read away from the page, so the panel's own line saying so is not in it.
        head += "  — resolved by " + closed.get("agent", "Agent")
    elif closed:
        head += "  — resolved"
    return head


def _print_message(message: dict, registry: dict) -> None:
    who = message.get("agent", "Agent") if message["author"] == "agent" else "User"
    if is_reaction(message):
        # A mark rather than a turn: the token's glyph and word, plus an explanation
        # only when the page's package deliberately supplied one.
        entry = reaction_tokens(registry).get(message["token"]) or {}
        said = f"{entry.get('glyph', '')} {message['token']}".strip()
        if entry.get("means"):
            said += f" — {entry['means']}"
        print(f"- **{who}** reacted: {said}")
        return
    edited = " *(edited)*" if message.get("edited") else ""
    body = message.get("text", "")
    if drawing := message.get("drawing"):
        over = f" over “{drawing['says']}”" if drawing.get("says") else ""
        body += f"\n_(drawing attached{over})_"
    if message.get("markup"):
        body += f"\n{message['markup']}"
    print(f"- **{who}**{edited}: " + body.replace("\n", "\n  "))


def _print_threads(events: list, spk: dict, registry: dict) -> None:
    threads = build_threads(events, enclosing_of(spk))
    if threads:
        print("\n### Threads\n")
    for thread in threads.values():
        print(_thread_heading(thread))
        for message in thread["msgs"]:
            _print_message(message, registry)
        print()


def _print_approvals(events: list) -> None:
    for approval in standing_approvals(events):
        print(f"Approved v{approval['version']} at {approval['ts']}.")


def cmd_transcript(page_dir: Path) -> None:
    """The page's exchange as Markdown, for reuse in a PR description."""
    events = read_events(page_dir)
    registry = active_registry(page_dir) or {}
    revision, title = _revision_title(page_dir)
    print(f"## Leaf: {title or page_dir.name}")
    _print_versions(events)
    _print_edits(page_dir, events, registry)
    spk = _published_reading(page_dir, registry, revision)
    _print_threads(events, spk, registry)
    _print_approvals(events)
