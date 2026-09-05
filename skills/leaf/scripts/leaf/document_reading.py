"""Shared semantic reading of one document and its standing event log.

Browser state and agent inspection use the same retirement, request, and Ask
assembly. Callers supply the HTML and events from their page transaction; this
reading does no file I/O and stores no derived state.
"""

from typing import NamedTuple

from .asks import page_ask_inventory, page_ask_projection
from .events import retractions, seats_with_agent
from .passages import Passages, enclosing_of, page_passages
from .projection import StateProjection, page_projection, retirement_outcomes
from .requests import request_lifecycles_for, request_phases
from .structure import _StructParser


class DocumentReading(NamedTuple):
    html: str
    parser: _StructParser
    projection: StateProjection
    spoken: dict
    passages: Passages
    requests: list
    asks: dict
    within: dict
    floors: dict


def read_document(
    html: str,
    events: list,
    registry: dict,
    revision: int,
    threads: dict,
    *,
    prepared: tuple | None = None,
) -> DocumentReading:
    """Resolve a document's durable state and its reader's outstanding Asks.

    `spoken` retains authored words because retractions and action ownership are
    based on construction. `passages` removes retired slots; exact replacement
    bodies and position details remain in `projection.desired`'s winning events.
    """
    projection, parser, spk = prepared or page_projection(
        html, events, registry, revision
    )
    passages = page_passages(
        html, registry, retirement_outcomes(projection.actions, registry)
    )
    dropped = set(passages.retired) | set(passages.gone)
    requests = request_lifecycles_for(
        events,
        parser.lf_elements,
        registry,
        {"kind": "page", "revision": revision},
    )
    phases = request_phases(requests)
    reader, awaiting = page_ask_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        seats_with_agent(threads),
        request_phases=phases,
    )
    unanswered, unanswered_awaiting = page_ask_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        set(),
        request_phases=phases,
    )
    inventory = page_ask_inventory(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        request_phases=phases,
        settled_away=set(passages.gone),
    )
    return DocumentReading(
        html=html,
        parser=parser,
        projection=projection,
        spoken=spk,
        passages=passages,
        requests=requests,
        asks={
            "all": inventory,
            "reader": reader,
            "unanswered": unanswered,
            "awaiting": awaiting,
            "unanswered_awaiting": unanswered_awaiting,
        },
        within=enclosing_of(spk),
        floors=retractions(events, revision),
    )
