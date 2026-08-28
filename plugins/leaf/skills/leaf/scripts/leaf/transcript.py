"""Raw event and Markdown transcript readings."""

import sys
from pathlib import Path

from leaf.event_log import jsonl_line, read_events
from leaf.events import build_threads, is_reaction, taken_back
from leaf.files import latest_revision, revision_label, revision_path
from leaf.passages import enclosing_of
from leaf.projection import page_projection, record_lag
from leaf.registry import load_registry, reaction_tokens
from leaf.structure import parse_revision


def cmd_events(page_dir: Path, after: int) -> None:
    for event in read_events(page_dir):
        if event["seq"] > after:
            print(jsonl_line(event))


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
    try:
        revision = latest_revision(page_dir)
    except SystemExit:
        revision = None
    if revision is not None:
        title = parse_revision(page_dir, revision).title.strip()
    return revision, title


def _print_versions(events: list) -> None:
    notes = [e for e in events if e["kind"] == "note"]
    if notes:
        print("\n### Versions\n")
        for e in notes:
            print(f"- v{e['version']}: {e['text']}")


def _print_edits(events: list) -> None:
    # The user's direct edits are outcomes of the exchange; without them the transcript
    # understates it whenever a changelog note doesn't restate them. So
    # is a version taking one back, which is the same understatement the other
    # way round — an edit shown as final that a later version overruled.
    # Widget-agnostic rendering: verb + detail pairs, against the version edited.
    withdrawn = taken_back(events)
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
            verb = f"{e['action']} {detail}".strip()  # a bare reject carries no detail
            if e["kind"] == "report":
                # A worker's provisional news is an outcome too, under its own name.
                print(
                    f"- `{e['widget']}`: {e.get('agent', 'a worker')} reported "
                    f"{verb} (on {revision_label(events, e['revision'])})"
                )
            else:
                # An edit the reader took back is an outcome too, and the same
                # understatement the other way round: shown as it stands it reads
                # as final, and left out it reads as never made.
                took = " — taken back" if e["id"] in withdrawn else ""
                print(
                    f"- `{e['widget']}`: {verb} "
                    f"(on {revision_label(events, e['revision'])}){took}"
                )


def _published_reading(
    page_dir: Path,
    events: list,
    registry: dict,
    revision: int | None,
) -> tuple:
    # Against the active revision — the page as it now stands, which is what a
    # transcript is an account of. A page with no valid revision has no reading.
    latest = (
        revision_path(page_dir, revision).read_text(encoding="utf-8")
        if revision
        else ""
    )
    projection = parser = None
    spk = {}
    if revision is not None:
        projection, parser, spk = page_projection(latest, events, registry, revision)
    return projection, parser, spk


def _thread_heading(thread: dict) -> str:
    anchor = thread["root"].get("anchor") or {}
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
    if thread["root"].get("about") == "layer":
        head += "  — about the layer"
    closed = thread["resolved"]
    if closed and closed["author"] == "claude":
        # Named where the reader was not the one who closed it. A transcript is
        # read away from the page, so the panel's own line saying so is not in it.
        head += "  — resolved by " + closed.get("agent", "Agent")
    elif closed:
        head += "  — resolved"
    return head


def _print_message(message: dict, registry: dict) -> None:
    who = message.get("agent", "Agent") if message["author"] == "claude" else "User"
    if is_reaction(message):
        # A mark rather than a turn: the token's glyph and word, and the
        # meaning the layer gave it, since a transcript is read where no
        # bar is there to explain the glyph.
        entry = reaction_tokens(registry).get(message["token"]) or {}
        said = f"{entry.get('glyph', '')} {message['token']}".strip()
        if entry.get("means"):
            said += f" — {entry['means']}"
        print(f"- **{who}** reacted: {said}")
        return
    edited = " *(edited)*" if message.get("edited") else ""
    body = message["text"] + (f"\n{message['markup']}" if message.get("markup") else "")
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


def _print_approval(events: list) -> None:
    for e in events:
        if e["kind"] == "done":
            print(f"Approved at {e['ts']}.")
            break


def _print_record_lag(projection, parser, spk: dict, registry: dict) -> None:
    # To stderr — stdout is the artifact. A transcript is a page's closing act,
    # and the record debt it reports here is about to stop being fixable.
    if projection and registry:
        for line in record_lag(projection, parser.by_id, spk, registry):
            print(f"record behind the log — {line}", file=sys.stderr)


def cmd_transcript(page_dir: Path) -> None:
    """The page's exchange as Markdown, for reuse in a PR description."""
    events = read_events(page_dir)
    registry = load_registry(page_dir) or {}
    revision, title = _revision_title(page_dir)
    print(f"## Leaf: {title or page_dir.name}")
    _print_versions(events)
    _print_edits(events)
    projection, parser, spk = _published_reading(page_dir, events, registry, revision)
    _print_threads(events, spk, registry)
    _print_approval(events)
    _print_record_lag(projection, parser, spk, registry)
