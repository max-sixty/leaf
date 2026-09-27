"""Shared semantic reading of one document and its standing event log.

Browser state and agent inspection use the same retirement and Ask
assembly. Callers supply the HTML and events from their page transaction; this
reading does no file I/O and stores no derived state.
"""

from typing import NamedTuple

from .asks import page_ask_readings
from .events import retractions, seats_with_agent
from .passages import Passages, enclosing_of, page_passages
from .projection import PageReading, StateProjection, retirement_outcomes
from .structure import SourceDocument


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
    passages = page_passages(
        document, registry, retirement_outcomes(projection.actions)
    )
    dropped = set(passages.retired) | set(passages.gone)
    asks = page_ask_readings(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        seats_with_agent(threads),
        settled_away=set(passages.gone),
    )
    return DocumentReading(
        document=document,
        projection=projection,
        spoken=spk,
        passages=passages,
        asks=asks,
        within=enclosing_of(spk),
        floors=retractions(events, revision),
    )
