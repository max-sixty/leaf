"""One document read under one vocabulary (`SourceReading`), each reading of the pair
taken once: its passages and words (`passages`), the widgets in it that ask the user
(`obligation_sources`), and the compact facts a scan of a page's revision history keeps
of it (`SourceInventory`)."""

from functools import cached_property
from typing import NamedTuple

from leaf.source.data_contracts import data_document_readings
from leaf.source.obligation_sources import (
    ObligationSources,
    obligation_registrations,
    obligation_sources,
)
from leaf.source.passages import Passages, Spoken, page_passages
from leaf.source.structure import SourceDocument


def _spoken(p: Passages) -> dict:
    """id → Spoken, for every element the reading `p` carries: the passage reading
    sliced by id rather than a second walk (see `SourceReading.spoken`)."""
    # Stripped: the separator the passage walk puts between blocks lands inside
    # whichever element the next block opens, so a slice can start or end on one. It
    # marks a boundary rather than saying anything.
    said = {wid: p.text[lo:hi].strip() for wid, (lo, hi) in p.spans.items()}
    return {wid: Spoken(said.get(wid, ""), chain) for wid, chain in p.enclosing.items()}


class SourceInventory(NamedTuple):
    """Compact authored facts needed by scans across an entire revision history."""

    ids: tuple[str, ...]
    items: dict
    data_documents: list


class SourceReading:
    """One document read under one vocabulary, each reading taken once.

    A document and its registry are immutable once read, so what the file side
    says of them is a function of the pair: the authored passage reading, its
    words by id, and where each id sits. Holders keep one of these rather than
    walking the document again per question. A stored revision's is held across
    requests (`revision_artifact.read_revision`); a candidate's lives as long as
    the check that built it.

    The log never reaches this object. A reading under the outcomes in force is the
    same `page_passages` walk with `decided`, taken by `decided_passages`, which
    returns the authored reading where no outcome names an element this document
    carries: the parser consults `decided` only by the id of an element it opens,
    so outcomes naming no such id leave every field as authored."""

    # The last outcomes read and their reading: outcomes change only when a user
    # decides, so one held pair answers every read between two decisions.
    _decided: tuple | None = None

    def __init__(self, document: SourceDocument, registry: dict | None):
        self.document = document
        self.registry = registry or {}

    @property
    def inventory(self) -> SourceInventory:
        """Read historical consumers together, without retaining parser records.
        A stored revision keeps its own in its page's compact memo instead
        (`revision_artifact.RevisionReading.inventory`)."""
        return self._inventory

    @cached_property
    def _inventory(self) -> SourceInventory:
        return SourceInventory(
            tuple(self.document.ids),
            obligation_registrations(self.document, self.registry),
            data_document_readings(self.document, "", self.registry),
        )

    @cached_property
    def obligation_sources(self) -> ObligationSources:
        """The widgets this version declares that can ask the user, which every
        reading of its obligations starts from
        (`obligation_sources.ObligationSources`)."""
        return obligation_sources(self.document, self.registry)

    @cached_property
    def passages(self) -> Passages:
        """The version as authored: every slot pending, every body the agent's."""
        return page_passages(self.document, self.registry)

    @cached_property
    def spoken(self) -> dict:
        """id → Spoken, for every element the version carries.

        This is the version's own reading of itself, so it is `page_passages`
        sliced by id rather than a second walk: chrome skipped, whitespace collapsed
        the way a captured quote is. Asking whether two versions still say the same thing has
        to mean the same text a user could have selected, or the question is about
        something else.

        Each id's words are its `Passages.spans` slice of the text, the range a
        quote scoped to that id searches.

        The two halves come from different readings because they are different
        facts, and taking both off the character scan costs the second one. Words
        are what the scan holds. Where an element *sits* is structure, so it comes
        from the parser's record of what was open — and an element that says
        nothing is somewhere all the same. Keyed on words, an image-only option and
        a card holding one diagram would be in no chain at all, so `action_rests_on`
        would drop them from what an action rests on (a floor would stop replaying),
        and `markup_value` would read a version that honoured a pick on such an option
        as showing no pick, which is the state gate refusing the very version that
        agreed with the user."""
        return _spoken(self.passages)

    @property
    def within(self) -> dict:
        """id → the ids enclosing it, outermost first, itself last: the
        containment half of `spoken`, which the walk records before it asks the
        vocabulary anything (`passages.enclosing_ids`)."""
        return self.passages.enclosing

    def decided_passages(
        self, decided: dict, rewrites: dict | None = None, additions: dict | None = None
    ) -> Passages:
        """The passage reading under the retirement outcomes in force
        (`projection.retirement_outcomes`), and under the user's rewritten bodies
        and created children where a caller passes them
        (`projection.rewritten_bodies`, `projection.generated_children`)."""
        # The parser consults an outcome only by the id of an element it opens, so
        # outcomes naming none of this document's elements leave it as authored. A
        # rewrite or a created child may stand on an element another created child
        # brought, which the authored walk never opens, so those are kept whole.
        carried = (
            tuple(
                sorted(
                    (widget, outcome)
                    for widget, outcome in decided.items()
                    if widget in self.passages.enclosing
                )
            ),
            tuple(sorted((rewrites or {}).items())),
            tuple(sorted((additions or {}).items())),
        )
        if not any(carried):
            return self.passages
        # One read of the pair: threads share a held reading, and another's
        # outcomes may replace it between a check and a second read.
        held = self._decided
        if held is None or held[0] != carried:
            held = (
                carried,
                page_passages(self.document, self.registry, *map(dict, carried)),
            )
            self._decided = held
        return held[1]
