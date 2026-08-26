"""Raw event and Markdown transcript readings."""

import sys
from pathlib import Path

from leaf_interact.document import parse_version
from leaf_interact.events import build_threads, jsonl_line, read_events, taken_back
from leaf_interact.files import published_versions, version_path
from leaf_interact.projection import page_projection, record_lag
from leaf_interact.registry import load_registry


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


def cmd_transcript(page_dir: Path) -> None:
    """The page's exchange as Markdown, for reuse in a PR description."""
    events = read_events(page_dir)
    published = published_versions(page_dir, events)
    registry = load_registry(page_dir) or {}
    title = ""
    if published:
        title = parse_version(page_dir, published[-1]).title.strip()
    print(f"## Leaf: {title or page_dir.name}")

    notes = [e for e in events if e["kind"] == "note"]
    if notes:
        print("\n### Versions\n")
        for e in notes:
            print(f"- v{e['version']}: {e['text']}")

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
                    f"{verb} (on v{e['version']})"
                )
            else:
                # An edit the reader took back is an outcome too, and the same
                # understatement the other way round: shown as it stands it reads
                # as final, and left out it reads as never made.
                took = " — taken back" if e["id"] in withdrawn else ""
                print(f"- `{e['widget']}`: {verb} (on v{e['version']}){took}")

    # Against the newest published version — the page as it now stands, which is
    # what a transcript is an account of. A page with nothing published yet has no
    # reading to give, and no action can have been made against one either.
    latest = (
        version_path(page_dir, published[-1]).read_text(encoding="utf-8")
        if published
        else ""
    )
    projection = parser = None
    spk = {}
    if published:
        projection, parser, spk = page_projection(
            latest, events, registry, published[-1]
        )
    threads = build_threads(events, spk)
    if threads:
        print("\n### Threads\n")
    for t in threads.values():
        anchor = t["root"].get("anchor") or {}
        if anchor.get("quote"):
            head = f"> “{shown(anchor['quote'])}”"
        elif anchor.get("section"):
            head = f"> § {anchor['section']}"
            if anchor.get("part"):
                head += f" · {anchor['part']}"
        else:
            head = "> (page-level)"
        if t["root"].get("about") == "layer":
            head += "  — about the layer"
        closed = t["resolved"]
        if closed and closed["author"] == "claude":
            # Named where the reader was not the one who closed it. A transcript is
            # read away from the page, so the panel's own line saying so is not in it.
            head += "  — resolved by " + closed.get("agent", "Agent")
        elif closed:
            head += "  — resolved"
        print(head)
        for m in t["msgs"]:
            who = m.get("agent", "Agent") if m["author"] == "claude" else "User"
            body = m["text"] + (f"\n{m['markup']}" if m.get("markup") else "")
            print(f"- **{who}**: " + body.replace("\n", "\n  "))
        print()
    for e in events:
        if e["kind"] == "done":
            print(f"Approved at {e['ts']}.")
            break

    # To stderr — stdout is the artifact. A transcript is a page's closing act,
    # and the record debt it reports here is about to stop being fixable.
    if projection and registry:
        for line in record_lag(projection, parser.by_id, spk, registry):
            print(f"record behind the log — {line}", file=sys.stderr)
