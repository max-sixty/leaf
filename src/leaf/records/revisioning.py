"""Turn a page's editable source into numbered, immutable revisions as the page is
read.

`activate_source` makes the source the next revision when its artifact differs from
the active revision's and `check_source` finds no errors. Otherwise it refuses, and
the active revision stays live. A source whose artifact matches the active revision
is not a candidate, and `check_source` checks no transition for it (see its gate on
`PredecessorReading.unchanged`). How it publishes the revision, with the events and
anchor moves the revision causes, is `revision_publication`'s.

Every read of a live page activates the source first. A state read calls
`activate_source`, and the news a visible tab asks for calls it only when
`held_activation` doesn't cover the page as it stands. So `page_memory` keeps the
last answer, keyed on the two readings `page_inputs.source_readings`
returns: the source, and the history (the log and the revisions). That is how a
saved `index.html` reaches an open tab: the next read sees the source change and
makes the revision. A cached "no
new revision" stays valid while only the log grows, because admission checked each
event against the revision it names. A refusal is checked again when the source or
the history changes. A stamp leaves the answer for the source it published
(`hold_published`), so the next read in that process doesn't check the same source
again.
"""

from contextlib import nullcontext
from pathlib import Path
from typing import NamedTuple

from leaf.base.page_memory import memo
from leaf.records.authored_checks.source import check_source
from leaf.records.revision_publication import Activation, activate_checked_source
from leaf.records.transaction import PageTransaction
from leaf.source.page_inputs import source_readings


class _Answer(NamedTuple):
    source: str
    history: str
    activation: Activation


class _Held:
    """The page's last activation answer and the readings it was given under."""

    answer: _Answer | None = None


def activate_source(page_dir: Path, *, transaction=None) -> Activation:
    """Activate complete valid source inputs, or keep the last good revision.

    The readings are taken before anything is read, so a write that lands during
    the check moves the page past the answer held here and the next call checks
    again. An activation that wrote a revision is held as the answer the next call
    would give: the source is now the active revision, and nothing was created."""
    with (
        nullcontext(transaction)
        if transaction is not None
        else PageTransaction(page_dir) as page
    ):
        return _activate_source(page_dir, page)


def held_activation(page_dir: Path, source: str, history: str) -> Activation | None:
    """The answer `activate_source` would give without checking anything, while the
    one it holds still covers these `source_readings`, else None. A reader that
    asks often, such as the news a tab polls, asks this first and takes the page's
    transaction only to activate (`LivePage._activated`)."""
    answer = memo(page_dir, _Held).answer
    if (
        answer
        and answer.source == source
        and (answer.activation.error is None or answer.history == history)
    ):
        return answer.activation
    return None


def _activate_source(page_dir: Path, page) -> Activation:
    source, history = source_readings(page_dir)
    if (held := held_activation(page_dir, source, history)) is not None:
        return held
    activation = activate_checked_source(
        page,
        check_source(page_dir, page.events),
    )
    settled = activation._replace(created=False) if activation.created else activation
    memo(page_dir, _Held).answer = _Answer(source, history, settled)
    return activation


def hold_published(page_dir: Path, source: str, activation: Activation) -> None:
    """Hold a publication as the answer the next `activate_source` gives.

    `source` is the source reading taken before the check that published, as
    `_activate_source` takes its own. A stamp checks the source and publishes it as
    the active revision, so a state read in the same process, such as a page server
    beside the command, finds it active rather than checking it again; a write since
    that reading moves the page past this answer."""
    memo(page_dir, _Held).answer = _Answer(
        source, "", activation._replace(created=False)
    )
