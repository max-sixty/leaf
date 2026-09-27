"""Validation of mutable source against its revision and event history."""

from pathlib import Path
from typing import NamedTuple

from leaf.events import anchored_parts, retractions
from leaf.files import list_revisions
from leaf.passages import SourceReading
from leaf.projection import (
    StateProjection,
    protected_ids,
    retirement_holders,
    state_projection,
)
from leaf.registry.contract import visual_parts
from leaf.revision_artifact import RevisionArtifact, read_revision
from leaf.structure import SourceDocument
from leaf.validation.transitions import report_errors, restatement_errors

# What a revision that dropped a protected id does instead, by each reason the id is
# needed (`protected_ids`). A reason names the way out it leaves open, so the author
# reads the route off the refusal instead of trying attributes against the gate.
PROTECTED_REMEDIES = {
    "thread": (
        "an unresolved thread is anchored on each: keep the element, wherever on "
        "the page it goes, or first move the thread to another passage, detach it, "
        "or resolve it"
    ),
    "state": (
        "the user's standing state rests on each: keep the element inside its "
        "widget, and the widget may go anywhere on the page, such as a collapsed "
        "section of finished work. To drop it instead, put `restated` on the "
        "rewritten element the state rests on, stamp that version, and drop it in "
        "a later one"
    ),
    "report": (
        "a worker's standing report rests on each: keep the element until a "
        "stamped version absorbs the report into its markup or marks the element "
        "`overruled`"
    ),
    "retirement": (
        "a decision's markup holds each: keep it. A version may drop only what the "
        "decision's outcome retires or, while the decision is unanswered and no "
        "open thread is anchored inside it, what withdrawing it whole retires"
    ),
}


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


class TransitionReading(NamedTuple):
    """The current document's words and standing projection at its predecessor."""

    words: dict
    floors: dict
    projection: StateProjection


def predecessor_reading(
    page_dir: Path,
    data: bytes,
    events: list,
    artifact: RevisionArtifact | None = None,
) -> PredecessorReading:
    """Read the predecessor whose still-standing decisions this source must keep."""
    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else 0
    active_data = read_revision(page_dir, active).html if active else None
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
        (
            read_revision(page_dir, predecessor)
            if predecessor
            else SourceReading(SourceDocument(""), {})
        ),
    )


def continuity_errors(
    events: list,
    parser,
    registry: dict | None,
    revision: PredecessorReading,
) -> tuple[list[str], list[str]]:
    """Protect predecessor anchors, standing state, and retirement holders."""
    if not revision.predecessor or revision.committed_active or registry is None:
        return [], []
    previous = revision.previous
    gone = previous.document.ids - parser.ids
    # Only the parts a live thread still points at, read exactly as the
    # protected ids below are. A declared part is authored markup, not a promise:
    # once every thread on it has moved, detached, or closed, the picture may lose
    # the node with them, the way an id no thread holds is dropped. Held for the
    # life of the widget instead, a diagram could never follow the thing it draws.
    # Prefixes admit ids the file never lists, so for such a widget only a
    # declaration that stops admitting a held id drops it here; a part its drawing
    # stops rendering detaches in the browser.
    previous_records, current_records = previous.document.by_id, parser.by_id
    dropped_parts = sorted(
        f"{section} · {part}"
        for section, part in anchored_parts(events, previous.within)
        if section in parser.ids
        and part in visual_parts(previous_records.get(section, {}), previous.registry)
        and part not in visual_parts(current_records.get(section, {}), registry)
    )
    errors = []
    if dropped_parts:
        errors.append(
            "visual parts an open thread anchors on, present in revision "
            f"r{revision.predecessor} but dropped in index.html: {dropped_parts} — "
            "move, detach, or resolve those threads first"
        )
    previous_projection = state_projection(
        events,
        previous_records,
        previous.spoken,
        previous.registry,
        revision.predecessor,
    )
    protected = protected_ids(
        retirement_holders(previous.document, previous.registry),
        events,
        gone,
        previous_projection,
        previous.spoken,
        previous.registry,
    )
    dropped = sorted(gone & protected.keys())
    generated = {
        (unit, widget, spec["creates"]["child"])
        for (widget, unit, _verb), (
            _event,
            spec,
        ) in previous_projection.desired.items()
        if spec.get("creates")
    }
    current_by_id = parser.by_id

    def carried_by_sender(identity: str, widget_id: str, child_tag: str) -> bool:
        """Whether a generated unit is the sender's direct authored child."""
        unit = current_by_id.get(identity)
        widget = current_by_id.get(widget_id)
        return bool(
            unit
            and widget
            and unit["tag"] == child_tag
            and unit.get("holder") is widget
            and unit.get("parent") == widget["tag"]
        )

    misplaced = sorted(
        identity
        for identity, widget_id, child_tag in generated
        if identity in parser.ids
        and not carried_by_sender(identity, widget_id, child_tag)
    )
    dropped_advice = sorted(gone - protected.keys())
    held: dict = {}
    for identity in dropped:
        for why in protected[identity]:
            held.setdefault(why, []).append(identity)
    for why in sorted(held):
        errors.append(
            f"protected ids present in revision r{revision.predecessor} but "
            f"dropped in index.html: {held[why]} — {PROTECTED_REMEDIES[why]}"
        )
    if misplaced:
        errors.append(
            "authored user-generated ids must be direct children of their "
            f"sending widgets with the declared child tag: {misplaced}"
        )
    return errors, dropped_advice


def transition_reading(
    document: SourceDocument,
    events: list,
    registry: dict | None,
    revision: PredecessorReading,
) -> TransitionReading:
    """Project standing log changes onto this source from its predecessor."""
    words = SourceReading(document, registry).spoken
    floors = retractions(events, revision.predecessor)
    projection = state_projection(
        events,
        document.by_id,
        words,
        registry or {},
        revision.predecessor,
        floors,
    )
    return TransitionReading(words, floors, projection)


def transition_errors(
    parser,
    registry: dict | None,
    revision: PredecessorReading,
    transition: TransitionReading,
    allow_transition: bool,
) -> list[str]:
    """Validate decision retractions and report settlements in changed source."""
    if revision.committed_active:
        return []
    errors = restatement_errors(
        parser,
        revision.previous.document,
        revision.previous.spoken,
        transition.words,
        revision.predecessor,
        registry or {},
        transition.projection,
        transition.floors,
    )
    errors.extend(
        report_errors(
            parser,
            revision.previous.document,
            revision.previous.spoken,
            transition.words,
            registry or {},
            transition.projection,
        )
    )
    if not allow_transition:
        if parser.restated:
            errors.append(
                "index.html carries restated decisions; stamp these exact bytes "
                "to record their retraction"
            )
        if parser.overruled:
            errors.append(
                "index.html overrules standing reports; stamp these exact bytes "
                "to record their settlement"
            )
    return errors
