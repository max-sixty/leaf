"""Publish a checked source as the page's next revision, under the page transaction
its caller holds (`activate_checked_source`, `publish_checked_event`), and finish a
publication an interruption left (`finish_publications`). Nothing here opens a
transaction: `revisioning.activate_source` does, for a read that activates the
source, and the transaction finishes an interrupted publication as it opens.

When a revision drops the passage an open thread is anchored to, activation appends
a `reanchor` event in the same log transaction, which moves the thread to the
section that survives or detaches it. A reply that moves the thread itself
(`--quote`/`--section`/`--part`/`--detach`) takes precedence. A `reanchor` adds no
message and answers no update.

`publish_checked_event` publishes a reply or version note together with the
revision it needs. It computes reanchors against the log with that event appended,
because a stamp can reopen a thread by retracting the action that settled it. It
stages the revision's files, appends the event naming the staged bundle in
`publication`, and writes the revision marker last. If that is interrupted, the next
`PageTransaction` finishes it (`finish_publications`) before anyone else reads or
writes the page.

A revision a read activates has no reply or note to name it, so its activation
appends an `activation` event naming the bundle, before the reanchors it causes,
where the revision can be compared against an earlier one. The event gives the
revision its place in the log, and a comparison reads only the places of the
revisions after its base (`provenance.saved_after`), so a revision with none live
before it appends nothing: a fresh page, a sample and a published page's first read
write nothing to the log. An event naming the bundle is the first of its
publication: the publication's prerequisite, which `finish_publications` completes,
and its seq is the revision's place. A first revision a read activates has no
prerequisite, so one interrupted before its marker stays absent until a read
activates the source again; a first revision a reply or note publishes has that event
as its prerequisite, and the next transaction finishes it. A refused reply or note
appends nothing, its revision included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from leaf.base.files import latest_revision, list_revisions
from leaf.records.authored_checks.source_history import (
    EMPTY_READING,
    PredecessorReading,
    revision_reanchors,
)
from leaf.records.event_contracts import OpenTransaction, append_admitted
from leaf.records.page_view import CandidatePageView
from leaf.source.revision_artifact import (
    publish_artifact,
    read_revision,
    stage_artifact,
    staged_reading,
)

if TYPE_CHECKING:
    from pathlib import Path

    from leaf.records.authored_checks.source import SourceCheck


class Activation(NamedTuple):
    revision: int | None
    error: str | None
    created: bool


def planned_activation(page_dir: Path, checked: SourceCheck) -> Activation:
    """Read the candidate revision without publishing any artifact or transitions."""
    active = latest_revision(page_dir)
    if checked.errors:
        return Activation(active, "; ".join(map(str, checked.errors)), False)
    return Activation(checked.revision.candidate, None, not checked.revision.unchanged)


def _append_reanchors(page, revision, moves, *, view=None):
    for thread, anchor in moves.items():
        append_admitted(
            page,
            {
                "kind": "reanchor",
                "author": "page",
                "revision": revision,
                "thread": thread,
                "anchor": anchor,
            },
            view=view,
        )


def finish_publications(page: OpenTransaction, publications: list[dict]) -> None:
    """Finish each journaled publication `files.unfinished_publications` found,
    before any transaction consumer reads the page.

    An admitted prerequisite names the exact durable bundle. Mutable source is
    irrelevant to recovery, and bundles staged without a prerequisite stay absent.
    The revision marker is last, after every required anchor transition.
    """
    for event in publications:
        revision = event["revision"]
        reading = staged_reading(page.page_dir, event["publication"])
        previous = max(
            (value for value in list_revisions(page.page_dir) if value < revision),
            default=0,
        )
        predecessor = PredecessorReading(
            previous,
            revision,
            False,
            previous,
            read_revision(page.page_dir, previous) if previous else EMPTY_READING,
        )
        moves, _advice = revision_reanchors(
            page.events, reading, predecessor, candidate_revision=revision
        )
        _append_reanchors(
            page,
            revision,
            moves,
            view=CandidatePageView(
                page.page_dir, revision, reading, event["publication"]
            ),
        )
        publish_artifact(page.page_dir, event["publication"], reading)


def _publish_checked_source(page, checked, event=None):
    activation = planned_activation(page.page_dir, checked)
    if activation.error:
        return activation, None
    revision = activation.revision
    assert revision is not None
    moves = checked.reanchors or {}
    accepted = None
    publication = (
        stage_artifact(page.page_dir, revision, checked.artifact)
        if activation.created
        else None
    )
    view = (
        CandidatePageView(page.page_dir, revision, checked.reading, publication)
        if publication
        else None
    )
    if event is not None:
        event = {
            **event,
            "revision": revision,
            **({"publication": publication} if publication else {}),
        }
        # A note may take back the decision that resolved a quoted thread. Read
        # its effects from the admitted log, as interrupted publication does,
        # before making the revision discoverable.
        accepted, _ = append_admitted(page, event, view=view)
        previous = checked.revision.active if activation.created else revision
        predecessor = PredecessorReading(
            previous,
            revision,
            False,
            previous,
            read_revision(page.page_dir, previous) if previous else EMPTY_READING,
        )
        moves, _advice = revision_reanchors(
            page.events,
            checked.reading,
            predecessor,
            candidate_revision=revision,
        )
    elif publication and checked.revision.active:
        append_admitted(
            page,
            {
                "kind": "activation",
                "author": "page",
                "revision": revision,
                "publication": publication,
            },
            view=view,
        )
    _append_reanchors(page, revision, moves, view=view)
    if publication:
        publish_artifact(page.page_dir, publication, checked.reading)
    return activation, accepted


def activate_checked_source(page: OpenTransaction, checked: SourceCheck) -> Activation:
    """Activate inputs checked under this same transaction and preserve every quote."""
    return _publish_checked_source(page, checked)[0]


def publish_checked_event(
    page: OpenTransaction, checked: SourceCheck, event: dict
) -> dict:
    """Publish checked inputs and their required reply or version note as one transition."""
    activation, accepted = _publish_checked_source(page, checked, event)
    if activation.error:
        raise ValueError(activation.error)
    return accepted
