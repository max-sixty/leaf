"""Shared semantic reading of one document and its current event log.

Browser state and agent inspection use the same retirement and obligation assembly.
Callers supply the document's reading and events from their page transaction; this
reading stores no derived state. Registration history is read lazily through the
transaction-owned revision reader supplied by the caller. The retired passage view is
the document reading's own (`SourceReading.decided_passages`).
"""

from typing import NamedTuple

from .events import retractions
from .obligations import page_obligation_readings
from .passages import Passages
from .projection import PageReading, StateProjection, retirement_outcomes
from .structure import SourceDocument
from .todos import TodoReading


class DocumentReading(NamedTuple):
    document: SourceDocument
    projection: StateProjection
    spoken: dict
    passages: Passages
    items: dict
    within: dict
    floors: dict


def read_document(
    page: PageReading, threads: dict, log: TodoReading, *, data: dict | None = None
) -> DocumentReading:
    """Resolve a document's durable state and its user's outstanding obligations.

    `spoken` retains authored words because retractions and action ownership are
    based on construction. `passages` removes retired slots; exact replacement
    bodies and position details remain in `projection.desired`'s winning events.
    """
    document = page.document
    revision = page.revision
    events = page.events
    registry = page.registry
    projection = page.projection
    spk = page.spoken
    passages = page.reading.decided_passages(retirement_outcomes(projection.actions))
    dropped = set(passages.retired) | set(passages.gone)
    items = page_obligation_readings(
        page.reading.obligation_sources,
        projection,
        document.by_id,
        spk,
        registry,
        dropped,
        threads,
        page.within,
        log,
        settled_away=set(passages.gone),
        prior=page.prior,
        revision=revision,
        events=events,
        data=data,
    )
    return DocumentReading(
        document=document,
        projection=projection,
        spoken=spk,
        passages=passages,
        items=items,
        within=page.within,
        floors=retractions(events, revision),
    )
