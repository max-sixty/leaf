"""What the append door is allowed to read about a page.

Admission folds three things: the page, the standing log, and the event being
appended. The log and the event are already arguments the door is handed. This
is the third, so that no gate reaches past it to a file of its own.

A page directory answers all of it, and `PageView` is that reading. Nothing in
the door depends on one existing, though: a caller holding a page's markup as
literal text answers the same questions from it and gets the same refusals,
which is what lets a test of one rule state the markup and the log the rule is
about and stop there.

The readings: which revisions exist, what each one's markup and captured
vocabulary say, where the live page's ids sit, what the typed data store holds,
and what the log still owes. The last is there so that a refusal can tell an
agent that reached for the wrong id where the right one goes.
"""

from pathlib import Path

from .data import read_data
from .files import list_revisions
from .passages import active_enclosing
from .registry.storage import load_registry
from .revision_artifact import read_registry
from .structure import SourceDocument, parse_revision


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
        return parse_revision(self._page_dir, revision)

    def registry(self, revision: int | None) -> dict | None:
        """The vocabulary a revision captured, or the page's own where it has no
        revision yet. None on a page nothing has vendored a layer into."""
        if revision is None:
            return load_registry(self._page_dir)
        return read_registry(self._page_dir, revision)

    @property
    def within(self) -> dict:
        """Where every id sits on the page the user is looking at."""
        return active_enclosing(self._page_dir)

    @property
    def data(self) -> dict:
        """The typed external store, as its last replacement left it."""
        return read_data(self._page_dir)

    def responses(self, events: list) -> dict[str, dict]:
        """Where each event the log still owes work for is answered."""
        # This reads the page's whole state, which is far more than any gate does.
        # `delivery` loads it on the refusal that names it rather than at import.
        from .delivery import current_responses

        return current_responses(self._page_dir, events)
