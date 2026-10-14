"""Turn a page's editable source into numbered, immutable revisions.

`activate_source` makes the source the next revision when its artifact differs from
the active revision's and `check_source` finds no errors. Otherwise it refuses, and
the active revision stays live. A source whose artifact matches the active revision
is not a candidate, and `check_source` checks no transition for it (see its gate on
`PredecessorReading.unchanged`).

Every state read calls `activate_source` first, so `page_memory` keeps its last
answer, keyed on the two readings `served_state.reading.source_readings` returns:
the source, and the history (the log and the revisions). That is how a saved
`index.html` reaches an open tab: the next read sees the source change and makes
the revision. A cached "no new revision" stays valid while only the log grows,
because admission checked each event against the revision it names. A refusal is
checked again when the source or the history changes.

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
"""

from contextlib import nullcontext
from pathlib import Path
from typing import NamedTuple

from leaf.event_contracts import admitted_event, append_admitted
from leaf.event_log import APPEND_STAMPED
from leaf.files import list_revisions
from leaf.page_memory import memo
from leaf.page_view import CandidatePageView, PageView
from leaf.revision_artifact import (
    artifact_name,
    publish_artifact,
    read_revision,
    stage_artifact,
    staged_reading,
    write_artifact,
)
from leaf.served_state.reading import source_readings
from leaf.service import PageTransaction
from leaf.validation.source import SourceCheck, check_source
from leaf.validation.source_history import (
    EMPTY_READING,
    PredecessorReading,
    revision_reanchors,
)


class Activation(NamedTuple):
    revision: int | None
    error: str | None
    created: bool


class _Answer(NamedTuple):
    source: str
    history: str
    activation: Activation


class _Held:
    """The page's last activation answer and the readings it was given under."""

    answer: _Answer | None = None


def activate_source(page_dir: Path, *, transaction=None) -> Activation:
    """Activate complete valid source inputs, or keep the last good revision.

    The readings are taken before anything is read, so a write that lands during
    the check moves the page past the answer held here and the next call checks
    again. An activation that wrote a revision is held as the answer the next call
    would give: the source is now the active revision, and nothing was created."""
    with (
        nullcontext(transaction)
        if transaction is not None
        else PageTransaction(page_dir) as page
    ):
        return _activate_source(page_dir, page)


def _activate_source(page_dir: Path, page) -> Activation:
    source, history = source_readings(page_dir)
    held = memo(page_dir, _Held)
    answer = held.answer
    if (
        answer
        and answer.source == source
        and (answer.activation.error is None or answer.history == history)
    ):
        return answer.activation
    activation = activate_checked_source(
        page,
        check_source(page_dir, page.events),
    )
    settled = activation._replace(created=False) if activation.created else activation
    held.answer = _Answer(source, history, settled)
    return activation


def planned_activation(page_dir: Path, checked: SourceCheck) -> Activation:
    """Read the candidate revision without publishing any artifact or transitions."""
    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else None
    if checked.errors:
        return Activation(active, "; ".join(map(str, checked.errors)), False)
    return Activation(checked.revision.candidate, None, not checked.revision.unchanged)


def _append_reanchors(page, revision, moves, *, view=None, publication=None):
    for thread, anchor in moves.items():
        append_admitted(
            page,
            {
                "kind": "reanchor",
                "author": "page",
                "revision": revision,
                "thread": thread,
                "anchor": anchor,
                **({"publication": publication} if publication else {}),
            },
            view=view,
        )
        publication = None


def finish_publications(page: PageTransaction, publications: list[dict]) -> None:
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
    moves = checked.reanchors or {}
    accepted = None
    publication = (
        artifact_name(revision, checked.artifact) if activation.created else None
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
        # Judge the complete prospective log before making any prerequisite durable:
        # a stamp can reopen a thread by retracting the action that had settled it.
        prospective = {
            **APPEND_STAMPED,
            **admitted_event(view or PageView(page.page_dir), page.events, event),
            "seq": page.events[-1]["seq"] + 1 if page.events else 1,
        }
        previous = checked.revision.active if activation.created else revision
        predecessor = PredecessorReading(
            previous,
            revision,
            False,
            False,
            previous,
            read_revision(page.page_dir, previous) if previous else EMPTY_READING,
        )
        moves, _advice = revision_reanchors(
            [*page.events, prospective],
            checked.reading,
            predecessor,
            candidate_revision=revision,
        )
        event["id"] = prospective["id"]
    if activation.created and (event is not None or moves):
        stage_artifact(page.page_dir, revision, checked.artifact)
        if event is not None:
            accepted, _ = append_admitted(page, event, view=view)
        _append_reanchors(
            page,
            revision,
            moves,
            view=view,
            publication=publication if event is None else None,
        )
        publish_artifact(page.page_dir, publication, checked.reading)
    else:
        if activation.created:
            write_artifact(page.page_dir, revision, checked.artifact, checked.reading)
        if event is not None:
            accepted, _ = append_admitted(page, event)
        _append_reanchors(page, revision, moves)
    return activation, accepted


def activate_checked_source(page: PageTransaction, checked: SourceCheck) -> Activation:
    """Activate inputs checked under this same transaction and preserve every quote."""
    return _publish_checked_source(page, checked)[0]


def publish_checked_event(
    page: PageTransaction, checked: SourceCheck, event: dict
) -> dict:
    """Publish checked inputs and their required reply or version note as one transition."""
    activation, accepted = _publish_checked_source(page, checked, event)
    if activation.error:
        raise ValueError(activation.error)
    return accepted
