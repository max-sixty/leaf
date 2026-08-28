"""Validation of mutable source against its revision and event history."""

from pathlib import Path
from typing import NamedTuple

from leaf.events import retractions
from leaf.files import list_revisions, revision_path
from leaf.passages import spoken
from leaf.projection import (
    StateProjection,
    protected_ids,
    retirement_holders,
    state_projection,
)
from leaf.registry import visual_parts
from leaf.structure import parse_structure
from leaf.validation.transitions import report_errors, restatement_errors


class RevisionReading(NamedTuple):
    """The active and predecessor documents this exact source is checked against."""

    revisions: list[int]
    active: int
    committed_active: bool
    predecessor: int
    previous: object
    previous_words: dict


class TransitionReading(NamedTuple):
    """The current document's words and standing projection at its predecessor."""

    words: dict
    floors: dict
    projection: StateProjection


def revision_reading(
    page_dir: Path,
    data: bytes,
    events: list,
    registry: dict | None,
) -> RevisionReading:
    """Read the predecessor whose still-standing decisions this source must keep."""
    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else 0
    active_data = revision_path(page_dir, active).read_bytes() if active else None
    same_as_active = active_data == data
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
    previous = parse_structure("")
    previous_words = {}
    if predecessor:
        previous_html = revision_path(page_dir, predecessor).read_text(encoding="utf-8")
        previous = parse_structure(previous_html)
        previous_words = spoken(previous_html, registry or {})
    return RevisionReading(
        revisions,
        active,
        committed_active,
        predecessor,
        previous,
        previous_words,
    )


def continuity_errors(
    events: list,
    parser,
    registry: dict | None,
    revision: RevisionReading,
) -> tuple[list[str], list[str]]:
    """Protect predecessor anchors, standing state, and retirement holders."""
    if not revision.predecessor or revision.committed_active or registry is None:
        return [], []
    gone = revision.previous.ids - parser.ids
    previous_parts = {
        (record["attrs"]["id"], part)
        for record in revision.previous.lf_elements
        if record["attrs"].get("id")
        for part in visual_parts(record, registry)
    }
    current_parts = {
        (record["attrs"]["id"], part)
        for record in parser.lf_elements
        if record["attrs"].get("id")
        for part in visual_parts(record, registry)
    }
    dropped_parts = sorted(
        f"{section} · {part}"
        for section, part in previous_parts - current_parts
        if section in parser.ids
    )
    errors = []
    if dropped_parts:
        errors.append(
            f"visual parts present in revision r{revision.predecessor} but dropped in "
            f"index.html (anchors on them will break): {dropped_parts}"
        )
    previous_projection = state_projection(
        events,
        revision.previous.by_id,
        revision.previous_words,
        registry,
        revision.predecessor,
    )
    protected = protected_ids(
        retirement_holders(revision.previous, registry),
        events,
        gone,
        previous_projection,
        revision.previous_words,
        registry,
    )
    dropped = sorted(gone & protected)
    dropped_advice = sorted(gone - protected)
    if dropped:
        errors.append(
            f"protected ids present in revision r{revision.predecessor} but dropped in "
            "index.html (unresolved threads, standing state, or widget "
            f"retirement still need them): {dropped}"
        )
    return errors, dropped_advice


def transition_reading(
    html: str,
    events: list,
    parser,
    registry: dict | None,
    revision: RevisionReading,
) -> TransitionReading:
    """Project standing log changes onto this source from its predecessor."""
    words = spoken(html, registry or {})
    floors = retractions(events, revision.predecessor)
    projection = state_projection(
        events,
        parser.by_id,
        words,
        registry or {},
        revision.predecessor,
        floors,
    )
    return TransitionReading(words, floors, projection)


def transition_errors(
    parser,
    registry: dict | None,
    revision: RevisionReading,
    transition: TransitionReading,
    allow_transition: bool,
) -> list[str]:
    """Validate decision retractions and report settlements in changed source."""
    if revision.committed_active:
        return []
    errors = restatement_errors(
        parser,
        revision.previous,
        revision.previous_words,
        transition.words,
        revision.predecessor,
        registry or {},
        transition.projection,
        transition.floors,
    )
    errors.extend(
        report_errors(
            parser,
            revision.previous,
            revision.previous_words,
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
