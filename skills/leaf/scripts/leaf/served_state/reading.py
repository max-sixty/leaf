"""Filesystem change readings for a served page."""

import hashlib
from pathlib import Path

from ..files import STAGED, file_stamp
from ..schema import VIEWED_FILE
from ..service import claim_path

# The one thing a reading must not be built from. The server writes `viewed.json` for
# as long as a tab holds the page open, so counting it would make the page's own
# presence change the page's token: a stream asking "has anything changed?" would be
# told yes, by its own listener.
UNWATCHED = frozenset({VIEWED_FILE})


def page_reading(page_dir: Path) -> str:
    """A short token naming this reading of the page.

    Every direct child of the page directory, rather than the files a state response is
    known to read. The known-list is unmaintainable in the way that does not fail
    loudly: leave one out and the page simply stops hearing about that kind of news,
    with nothing red to say so. Directories are stamped without descending, which is
    enough — a new revision moves `revisions/`, a stamp moves `events.jsonl`, and the
    vendored layer cannot change under a served page at all, since re-vendoring restarts
    the server.

    Stat stamps rather than contents: the question is only whether anything moved, and
    the answer has to be cheap enough to ask many times a second.
    """
    stamps = sorted(
        (entry.name, file_stamp(entry))
        for entry in page_dir.iterdir()
        if entry.name not in UNWATCHED and not STAGED.fullmatch(entry.name)
    )
    stamps.append(("", file_stamp(claim_path(page_dir))))
    return hashlib.sha256(repr(stamps).encode()).hexdigest()[:16]
