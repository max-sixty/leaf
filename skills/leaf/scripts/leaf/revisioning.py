"""Activation of mutable source into immutable ordered revisions.

Activation judges a candidate: a source whose captured artifact differs from the
active revision's becomes the next revision if `check_source` finds nothing wrong
with it, and is refused otherwise, leaving the active revision live. A source
whose artifact is the active revision's is no candidate, and `check_source` judges
no transition for it (see its gate on `PredecessorReading.unchanged`).

Every state read asks for activation first, so the page's memory keeps its last
answer (`page_memory`), keyed on the page's stamps as
`served_state.reading.source_readings` splits them. A save moves the source reading,
and the next read validates it and turns it into a revision, which is what makes an
edited `index.html` reach an open tab. An answer that found the source to be the
active revision holds until the source moves: the log can grow under it without
changing it, since the door judged every event against the revision it names. A
refusal holds only until either reading moves, because an event can clear it, as
resolving the thread on an id the save dropped does.

Every affected open quoted thread is preserved at its surviving section through
admitted `reanchor` bookkeeping, under the same log transaction as activation.
An explicit replacement reply takes precedence. These transitions add no messages
and answer no outstanding move. A reply or stamp is preflighted against the
complete prospective log, including reopened threads. Its durable prerequisite
names the exact staged bundle in `publication`; the discoverable revision marker
comes last. Every PageTransaction finishes interrupted publications before
letting a reader or another writer proceed.
"""

from contextlib import nullcontext
from pathlib import Path
from typing import NamedTuple

from leaf.event_contracts import APPEND_STAMPED, admitted_event, append_admitted
from leaf.event_log import EventRefused
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
    quote_reanchors,
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
        check_source(page_dir, page.events, allow_transition=False),
    )
    settled = activation._replace(created=False) if activation.created else activation
    held.answer = _Answer(source, history, settled)
    return activation


def planned_activation(page_dir: Path, checked: SourceCheck) -> Activation:
    """Read the candidate revision without publishing any artifact or transitions."""
    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else None
    if checked.errors:
        return Activation(active, "; ".join(checked.errors), False)
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
        previous = revision - 1
        predecessor = PredecessorReading(
            previous,
            False,
            False,
            previous,
            read_revision(page.page_dir, previous) if previous else EMPTY_READING,
        )
        moves, errors, _advice = quote_reanchors(
            page.events, reading, predecessor, candidate_revision=revision
        )
        if errors:
            raise RuntimeError("incomplete publication: " + "; ".join(errors))
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
        previous = (revision - 1) if activation.created else revision
        predecessor = PredecessorReading(
            previous,
            False,
            False,
            previous,
            read_revision(page.page_dir, previous) if previous else EMPTY_READING,
        )
        moves, errors, _advice = quote_reanchors(
            [*page.events, prospective],
            checked.reading,
            predecessor,
            candidate_revision=revision,
        )
        if errors:
            raise EventRefused("; ".join(errors))
        event["id"] = prospective["id"]
    if activation.created and (event is not None or moves):
        stage_artifact(page.page_dir, revision, checked.artifact)
        if event is not None:
            accepted = append_admitted(page, event, view=view)
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
            accepted = append_admitted(page, event)
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
