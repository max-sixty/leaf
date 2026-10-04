"""Validation of mutable source against its revision and event history."""

from pathlib import Path
from typing import NamedTuple

from leaf.anchor_capture import resolve_quote
from leaf.events import anchored_parts, bare_reaction, build_threads, retractions
from leaf.files import list_revisions
from leaf.passages import SourceReading, page_passages
from leaf.projection import (
    StateProjection,
    frozen_thread_reading,
    generated_children,
    page_reading,
    protected_ids,
    retirement_holders,
    retirement_outcomes,
    rewritten_bodies,
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

    @property
    def candidate(self) -> int:
        return self.active if self.unchanged else self.active + 1


class TransitionReading(NamedTuple):
    """The current document's words and standing projection at its predecessor."""

    words: dict
    floors: dict
    projection: StateProjection


# An empty document under no vocabulary: the predecessor of a first version or a
# sample's child, and the reading of a source that could not be read at all.
EMPTY_READING = SourceReading(SourceDocument(""), {})
NO_PREDECESSOR = PredecessorReading(0, False, False, 0, EMPTY_READING)


def quote_reanchors(
    events: list,
    reading: SourceReading,
    revision: PredecessorReading,
    *,
    candidate_revision: int,
) -> tuple[dict, list[str], list[str]]:
    """Keep every open quoted thread attached when authored words change.

    An existing section is the only replacement the document establishes without
    inferring the subject. The author can choose a more precise passage in a reply.
    Runtime-produced words absent from the predecessor's file reading are outside
    this check; their widget remains the owner of those coordinates.
    """
    if not revision.predecessor:
        return {}, [], []
    previous = page_reading(revision.previous, events, revision.predecessor)
    current = page_reading(reading, events, candidate_revision)

    def passages(page):
        desired = page.projection.desired
        return page_passages(
            page.document,
            page.registry,
            retirement_outcomes(page.projection.actions),
            rewritten_bodies(page.projection.actions),
            generated_children(desired, page.document.ids),
        )

    previous_passages, current_passages = passages(previous), passages(current)
    moves, errors, advice = {}, [], []
    threads = build_threads(events, previous.within)
    workflows = None
    for thread in threads.values():
        anchor = thread["anchor"]
        if (
            thread["resolved"]
            or bare_reaction(thread)
            or not anchor
            or not anchor.get("quote")
        ):
            continue
        if anchor.get("source") or anchor.get("datum") or anchor.get("part"):
            continue
        if (
            resolve_quote(previous_passages, anchor) is None
            or resolve_quote(current_passages, anchor) is not None
        ):
            continue
        identity, section = thread["id"], anchor.get("section")
        if workflows is None:
            from leaf.workflows import canonical_workflows

            workflows = canonical_workflows(
                [],
                threads,
                frozen_thread_reading(events, previous.registry),
                page=previous,
            )
        answer = next(
            (
                workflow["answer"]
                for workflow in workflows
                if workflow["subject"] == {"kind": "thread", "id": identity}
                and workflow["answer"]
            ),
            None,
        )
        address = f"--for {answer['for']}" if answer else identity
        command = f"leaf thread reply <page> {address} --section <replacement-id> --quote <new-passage>"
        if (
            section
            and section in current_passages.enclosing
            and section not in current_passages.retired
            and section not in current_passages.gone
        ):
            moves[identity] = {"section": section}
            advice.append(
                f"open thread {identity} quote {anchor['quote']!r} no longer resolves; activation will move it to section {section!r}. To choose its replacement passage: {command}; detach only if its subject left the page"
            )
        else:
            errors.append(
                f"open thread {identity} quote {anchor['quote']!r} no longer resolves and has no surviving section; move it with {command}, or --detach if its subject left the page"
            )
    return moves, errors, advice


def predecessor_reading(
    page_dir: Path,
    data: bytes,
    events: list,
    artifact: RevisionArtifact | None = None,
) -> PredecessorReading:
    """Read the predecessor whose still-standing decisions this source must keep."""
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
    reading: SourceReading,
    events: list,
    revision: PredecessorReading,
) -> TransitionReading:
    """Project standing log changes onto this source from its predecessor."""
    words = reading.spoken
    floors = retractions(events, revision.predecessor)
    projection = state_projection(
        events,
        reading.document.by_id,
        words,
        reading.registry,
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
