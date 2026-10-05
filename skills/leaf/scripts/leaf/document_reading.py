"""Shared semantic reading of one document and its standing event log.

Browser state and agent inspection use the same retirement and Ask assembly.
Callers supply the document's reading and events from their page transaction; this
reading does no file I/O and stores no derived state. The retired passage view is
the document reading's own (`SourceReading.decided_passages`).
"""

from typing import NamedTuple

from .asks import page_ask_readings
from .events import retractions, seats_with_agent
from .passages import Passages
from .projection import PageReading, StateProjection, retirement_outcomes
from .structure import SourceDocument
from .tasks import task_ends


class DocumentReading(NamedTuple):
    document: SourceDocument
    projection: StateProjection
    spoken: dict
    passages: Passages
    asks: dict
    within: dict
    floors: dict


def read_document(page: PageReading, threads: dict) -> DocumentReading:
    """Resolve a document's durable state and its user's outstanding Asks.

    `spoken` retains authored words because retractions and action ownership are
    based on construction. `passages` removes retired slots; exact replacement
    bodies and position details remain in `projection.desired`'s winning events.
    """
    document = page.document
    revision = page.revision
    events = page.events
    registry = page.registry
    projection = page.projection
    parser = document
    spk = page.spoken
    passages = page.reading.decided_passages(retirement_outcomes(projection.actions))
    dropped = set(passages.retired) | set(passages.gone)
    asks = page_ask_readings(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        seats_with_agent(threads),
        ended=set(task_ends(events)),
        settled_away=set(passages.gone),
    )
    return DocumentReading(
        document=document,
        projection=projection,
        spoken=spk,
        passages=passages,
        asks=asks,
        within=page.within,
        floors=retractions(events, revision),
    )
