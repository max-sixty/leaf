"""What the append door is allowed to read about a page.

Admission folds three things: the page, the current log, and the event being
appended. The log and the event are already arguments the door is handed. This
is the third, so that no gate reaches past it to a file of its own.

A page directory answers all of it, and `PageView` is that reading. Nothing in
the door depends on one existing, though: a caller holding a page's markup as
literal text answers the same questions from it and gets the same refusals,
which is what lets a test of one rule state the markup and the log the rule is
about and stop there.

The readings: which revisions exist, what each one's markup and captured
vocabulary say, where the live page's ids sit, and which contract each typed data
source holds.
"""

from pathlib import Path

from leaf.base.files import list_revisions
from leaf.source.data import read_contracts, source_reading
from leaf.source.passages import enclosing_ids
from leaf.source.reading import SourceReading
from leaf.source.revision_artifact import active_enclosing, read_revision
from leaf.source.structure import SourceDocument
from leaf.source.vocabulary import page_vocabulary


class PageView:
    """One page directory's answers, each read when a gate asks for it.

    Nothing is read on construction, so the door makes one of these per append
    and a gate that asks nothing reads nothing.
    """

    def __init__(self, page_dir: Path):
        # Private: a gate that took the directory back out would be reading the
        # page in some way this class does not state.
        self._page_dir = page_dir

    @property
    def revisions(self) -> list[int]:
        """Every immutable revision this page holds, oldest first."""
        return list_revisions(self._page_dir)

    def document(self, revision: int) -> SourceDocument:
        """The authored markup one immutable revision froze."""
        return read_revision(self._page_dir, revision).document

    def reading(self, revision: int, registry: dict) -> SourceReading:
        """That markup read under `registry`, held across appends where it is the
        vocabulary the revision captured (`RevisionReading.under`)."""
        return read_revision(self._page_dir, revision).under(registry)

    def registry(self, revision: int | None) -> dict | None:
        """The vocabulary a revision captured, or the candidate's where the page has
        no revision yet (`page_vocabulary`). None on a page with no layer record."""
        return page_vocabulary(self._page_dir, revision)

    @property
    def within(self) -> dict:
        """Where every id sits on the page the user is looking at."""
        return active_enclosing(self._page_dir)

    @property
    def contracts(self) -> dict[str, str]:
        """Each recorded data source's contract, without reading its value."""
        return read_contracts(self._page_dir)

    def source(self, source: str, registry: dict) -> dict | None:
        """The value `source` holds now, as readers judged under `registry` receive it
        (`data.source_reading`)."""
        return source_reading(self._page_dir, source, registry)


class CandidatePageView(PageView):
    """Admission against checked immutable inputs before their revision is exposed."""

    def __init__(
        self, page_dir: Path, revision: int, reading: SourceReading, publication: str
    ):
        super().__init__(page_dir)
        self._revision = revision
        self._reading = reading
        self.publication = publication

    @property
    def revisions(self) -> list[int]:
        return [*super().revisions, self._revision]

    def document(self, revision: int) -> SourceDocument:
        return (
            self._reading.document
            if revision == self._revision
            else super().document(revision)
        )

    def reading(self, revision: int, registry: dict) -> SourceReading:
        if revision == self._revision:
            return SourceReading(self._reading.document, registry)
        return super().reading(revision, registry)

    def registry(self, revision: int | None) -> dict | None:
        return (
            self._reading.registry
            if revision == self._revision
            else super().registry(revision)
        )

    @property
    def within(self) -> dict:
        return self._reading.within


class InitialPageView:
    """A fresh single-revision page, before its directory is allocated.

    Sample source validation and allocation put the same literal document and
    captured vocabulary to ordinary admission.
    """

    def __init__(self, document: SourceDocument, registry: dict, contracts: dict):
        self._document = document
        self._registry = registry
        self._contracts = contracts

    @property
    def revisions(self) -> list[int]:
        return [1]

    def document(self, revision: int) -> SourceDocument:
        return self._document

    def reading(self, revision: int, registry: dict) -> SourceReading:
        return SourceReading(self._document, registry)

    def registry(self, revision: int | None) -> dict:
        return self._registry

    @property
    def within(self) -> dict:
        return enclosing_ids(self._document)

    @property
    def contracts(self) -> dict:
        return self._contracts

    def source(self, source: str, registry: dict) -> None:
        """A fresh page holds no value of its own until it is allocated."""
        return None
