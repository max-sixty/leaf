"""Read revision predecessors and relocate anchors after authored edits.

Revisions may change or remove any historical subject. A thread follows its
surviving section when its passage or part disappears, and detaches when its
section leaves the page. The original anchor remains in the append-only log.
"""

from pathlib import Path
from typing import NamedTuple

from leaf.anchor_capture import resolve_quote
from leaf.events import build_threads
from leaf.files import list_revisions
from leaf.passages import SourceReading, page_passages
from leaf.projection import (
    generated_children,
    page_reading,
    retirement_outcomes,
    rewritten_bodies,
)
from leaf.registry.contract import visual_parts
from leaf.revision_artifact import RevisionArtifact, read_revision
from leaf.structure import SourceDocument


class PredecessorReading(NamedTuple):
    """The active and predecessor documents this exact source is checked against."""

    active: int
    committed_active: bool
    # The candidate's captured artifact is the active revision's: its transition
    # was checked when that revision activated.
    unchanged: bool
    predecessor: int
    # The predecessor's document under the vocabulary it captured; an empty
    # document where there is none.
    previous: SourceReading

    @property
    def candidate(self) -> int:
        return self.active if self.unchanged else self.active + 1


# The predecessor of a first version or an unreadable source.
EMPTY_READING = SourceReading(SourceDocument(""), {})
NO_PREDECESSOR = PredecessorReading(0, False, False, 0, EMPTY_READING)


def revision_reanchors(
    events: list,
    reading: SourceReading,
    revision: PredecessorReading,
    *,
    candidate_revision: int,
) -> tuple[dict, list[str]]:
    """Relocate open threads whose authored anchor no longer survives.

    A surviving section is a precise fallback the document supplies. A dropped
    section detaches instead of guessing a different subject. Data-backed and
    runtime-produced passages stay with their own coordinate resolvers.
    """
    if not revision.predecessor:
        return {}, []
    previous = page_reading(revision.previous, events, revision.predecessor)
    current = page_reading(reading, events, candidate_revision)

    def passages(page):
        return page_passages(
            page.document,
            page.registry,
            retirement_outcomes(page.projection.actions),
            rewritten_bodies(page.projection.actions),
            generated_children(page.projection.desired, page.document.ids),
        )

    previous_passages, current_passages = passages(previous), passages(current)
    moves, advice = {}, []
    for thread in build_threads(events, previous.within).values():
        anchor = thread["anchor"]
        if thread["resolved"] or not anchor:
            continue
        section = anchor.get("section")
        # Frozen thread and generated widget identities are not authored section
        # removals. Their own owners retain their coordinate and lifecycle.
        if section and section not in previous.document.ids:
            continue
        surviving = (
            section in current_passages.enclosing
            and section not in current_passages.retired
            and section not in current_passages.gone
        )
        missing = bool(section) and not surviving
        if (
            not section
            and anchor.get("quote")
            and not (anchor.get("source") or anchor.get("datum"))
        ):
            missing = (
                resolve_quote(previous_passages, anchor) is not None
                and resolve_quote(current_passages, anchor) is None
            )
        if surviving and anchor.get("visual"):
            part = anchor["visual"]
            missing = part in visual_parts(
                previous.document.by_id.get(section, {}), previous.registry
            ) and part not in visual_parts(
                current.document.by_id.get(section, {}), current.registry
            )
        elif (
            surviving
            and anchor.get("quote")
            and not (anchor.get("source") or anchor.get("datum"))
        ):
            missing = (
                resolve_quote(previous_passages, anchor) is not None
                and resolve_quote(current_passages, anchor) is None
            )
        if not missing:
            continue
        moves[thread["id"]] = {"section": section} if surviving else None
        destination = f"section {section!r}" if surviving else "a detached thread"
        advice.append(
            f"open thread {thread['id']} anchor no longer resolves; activation will move it to {destination}"
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
        active
        and same_as_active
        and any(
            event["kind"] == "note" and event["revision"] == active for event in events
        )
    )
    predecessor = (
        active
        if committed_active
        else (revisions[-2] if same_as_active and len(revisions) > 1 else active)
    )
    return PredecessorReading(
        active,
        committed_active,
        bool(active and same_as_active and artifact is not None),
        predecessor,
        read_revision(page_dir, predecessor) if predecessor else EMPTY_READING,
    )
