"""Shared semantic reading of one document and its standing event log.

Browser state and agent inspection use the same retirement and Question assembly.
Callers supply the document's reading and events from their page transaction; this
reading stores no derived state. Registration history is read lazily through the
transaction-owned revision reader supplied by the caller. The retired passage view is
the document reading's own (`SourceReading.decided_passages`).
"""

from typing import NamedTuple

from .events import retractions, seats_with_agent
from .passages import Passages
from .projection import PageReading, StateProjection, retirement_outcomes
from .questions import approval_question, collection, page_question_readings
from .structure import SourceDocument


class DocumentReading(NamedTuple):
    document: SourceDocument
    projection: StateProjection
    spoken: dict
    passages: Passages
    questions: dict
    within: dict
    floors: dict


def read_document(page: PageReading, threads: dict) -> DocumentReading:
    """Resolve a document's durable state and its user's outstanding Questions.

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
    questions = page_question_readings(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        seats_with_agent(threads),
        settled_away=set(passages.gone),
        prior=page.prior,
        revision=revision,
        events=events,
    )
    if approval := approval_question(document, revision, events):
        questions = collection([*questions["all"], approval])
    return DocumentReading(
        document=document,
        projection=projection,
        spoken=spk,
        passages=passages,
        questions=questions,
        within=page.within,
        floors=retractions(events, revision),
    )
