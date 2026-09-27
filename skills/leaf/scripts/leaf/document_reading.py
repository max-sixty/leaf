"""Shared semantic reading of one document and its standing event log.

Browser state and agent inspection use the same retirement, request, and Ask
assembly. Callers supply the document's reading and events from their page
transaction; this reading does no file I/O and stores no derived state. The retired
passage view is the document reading's own (`SourceReading.decided_passages`).
"""

from typing import NamedTuple

from .asks import page_ask_readings
from .events import document_identity, retractions, seats_with_agent
from .passages import Passages
from .projection import PageReading, StateProjection, retirement_outcomes
from .requests import request_lifecycles_for, request_phases
from .structure import SourceDocument


class DocumentReading(NamedTuple):
    document: SourceDocument
    projection: StateProjection
    spoken: dict
    passages: Passages
    requests: list
    asks: dict
    within: dict
    floors: dict


def read_document(
    page: PageReading,
    threads: dict,
    data: dict | None = None,
) -> DocumentReading:
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
    requests = request_lifecycles_for(
        events,
        parser.lf_elements,
        registry,
        document_identity("page", revision),
        data,
    )
    asks = page_ask_readings(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        seats_with_agent(threads),
        request_phases=request_phases(requests),
        settled_away=set(passages.gone),
    )
    return DocumentReading(
        document=document,
        projection=projection,
        spoken=spk,
        passages=passages,
        requests=requests,
        asks=asks,
        within=page.within,
        floors=retractions(events, revision),
    )
