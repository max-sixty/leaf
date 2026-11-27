"""Read revision predecessors and relocate anchors after authored edits.

Revisions may change or remove any historical subject. A thread follows its
surviving section when its passage or part disappears, and detaches when its
section leaves the authored page. A decision that hides a section, as an accepted
suggestion hides the words it replaces, moves no thread, since undoing the decision
shows the section again. The original anchor remains in the append-only log.

A passage disappears where the file's reading of the predecessor finds the quote's
words and the candidate's finds none (`anchor_capture.copies`). The reading only
approximates the drawn page. Words it still finds but the page no longer shows once
stand on their section in the browser all the same (`resolveAnchor`), and words the
page still shows where the reading finds none, as after an edit that splits a word
across two inline elements, move with the rest. The move makes the fallback durable,
so neither a later version that says the words again nor a copy the reading doesn't
hold, such as a code block's, takes the thread, and it tells the agent
(`relocated-anchor`, `rewritten_from`). A quote the reading never found gets no move,
and follows its words to the one copy a later version shows.
"""

from functools import cache
from pathlib import Path
from typing import NamedTuple

from leaf.base.files import list_revisions, stamped_version
from leaf.base.findings import Finding
from leaf.log.events import build_threads
from leaf.log.projection import page_reading
from leaf.source.anchor_capture import copies
from leaf.source.reading import SourceReading
from leaf.source.registry.contract import visual_parts
from leaf.source.revision_artifact import RevisionArtifact, read_revision
from leaf.source.structure import SourceDocument


class PredecessorReading(NamedTuple):
    """The active and predecessor documents this exact source is checked against."""

    active: int
    candidate: int
    # The candidate's captured artifact is the active revision's: its transition
    # was checked when that revision activated.
    unchanged: bool
    predecessor: int
    # The predecessor's document under the vocabulary it captured; an empty
    # document where there is none.
    previous: SourceReading


# The predecessor of a first version or an unreadable source.
EMPTY_READING = SourceReading(SourceDocument(""), {})
NO_PREDECESSOR = PredecessorReading(0, 1, False, 0, EMPTY_READING)


def revision_reanchors(
    events: list,
    reading: SourceReading,
    revision: PredecessorReading,
    *,
    candidate_revision: int,
) -> tuple[dict, list[Finding]]:
    """Relocate open threads whose authored anchor no longer survives.

    A surviving section is a precise fallback the document supplies. A dropped
    section detaches instead of guessing a different subject. Data-backed and
    runtime-produced passages stay with their own coordinate resolvers.
    """
    # A log gesture may retire a passage within the same authored revision, but
    # another gesture can restore it. Only an authored revision transition may
    # record a permanent reanchor.
    if revision.unchanged or not revision.predecessor:
        return {}, []
    previous = page_reading(revision.previous, events, revision.predecessor)
    current = page_reading(reading, events, candidate_revision)

    # Each reading holds its passages, so a stamp's second look at the same
    # candidate, and the next activation's look at this one as its predecessor,
    # walk neither page again. Only a thread a revision may have moved asks.
    def passages(page):
        return cache(lambda: page.reading.decided_passages(**page.logged_words))

    previous_passages, current_passages = passages(previous), passages(current)
    moves, advice = {}, []
    for thread in build_threads(events, previous.within).values():
        anchor = thread["anchor"]
        if thread["resolved"] or not anchor:
            continue
        section = anchor.get("section")
        # Thread markup and generated widget identities are not authored section
        # removals. Their own owners retain their coordinate and lifecycle.
        if section and section not in previous.document.ids:
            continue
        surviving = section in current_passages().enclosing
        # A selection captured as detached names no copy to lose.
        quoted = anchor.get("quote") and not (
            anchor.get("source") or anchor.get("datum") or anchor.get("detached")
        )
        if surviving and anchor.get("visual"):
            part = anchor["visual"]
            missing = part in visual_parts(
                previous.document.by_id.get(section, {}), previous.registry
            ) and part not in visual_parts(
                current.document.by_id.get(section, {}), current.registry
            )
        elif quoted and (surviving or not section):
            missing = bool(
                copies(previous_passages(), anchor["quote"], section)
            ) and not copies(current_passages(), anchor["quote"], section)
        else:
            missing = bool(section) and not surviving
        if not missing:
            continue
        moves[thread["id"]] = {"section": section} if surviving else None
        advice.append(
            Finding(
                "relocated-anchor",
                values={
                    "thread": thread["id"],
                    "section": section if surviving else None,
                },
            )
        )
    return moves, advice


def predecessor_reading(
    page_dir: Path,
    data: bytes,
    events: list,
    artifact: RevisionArtifact | None = None,
) -> PredecessorReading:
    """Read the predecessor used to place threads after a source revision."""
    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else 0
    active_data = read_revision(page_dir, active).document.data if active else None
    same_as_active = active_data == data and (
        artifact is None or artifact.digest == read_revision(page_dir, active).digest
    )
    committed_active = bool(
        active and same_as_active and stamped_version(events, active) is not None
    )
    predecessor = (
        active
        if committed_active
        else (revisions[-2] if same_as_active and len(revisions) > 1 else active)
    )
    return PredecessorReading(
        active,
        active
        if same_as_active and artifact is not None
        else max(list_revisions(page_dir), default=0) + 1,
        bool(active and same_as_active and artifact is not None),
        predecessor,
        read_revision(page_dir, predecessor) if predecessor else EMPTY_READING,
    )
