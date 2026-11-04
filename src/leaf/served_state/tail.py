"""The tail of a state answer: what a browser holding an earlier reading lacks.

A browser adopts each state answer whole (`browser/AGENTS.md`, "One writer for each
fact"), and the parts of an answer that record what happened grow with every event
while the page's content stays the same: the log, and each view's projection entries
and undo list, one entry per event. A tab therefore names the reading it holds, by the
`browser.basis.key` that reading carried, and an answer that can extend that reading
carries `since` and, in place of the whole of each of those lists:

- `events`: the events logged after the held reading's sequence;
- each view's `document.projection.entries`, `thread.projection.entries` and `undo`:
  the entries whose event is new since, or whose entry changed, with
  `since.dropped` naming, per view and list, the held entries the list no longer holds.

The browser completes the answer from the reading it named (`completeState` in
`layer-client.js`), keeping the held entries the answer neither changed nor dropped,
in the order of their events: log order, newest first for `undo`. What it assembles is
the whole answer. Every other part is whole, since it holds what the page holds now
rather than one record per event.

The held lists are read again from this transaction's snapshot at the held sequence
rather than remembered. They depend only on the log through that sequence and on the
revisions the reading viewed under the active revision it was read with, which the key
names (`basis_key`), so reading them again gives what the tab holds. A key naming
another active revision, a view this answer has that the tab lacks, a sequence the log
hasn't reached, or nothing this module can read gets the whole answer.
"""

from collections.abc import Callable


def basis_key(through_seq: int, active: int, views) -> str:
    """The name of a browser reading: the log sequence it was read through, the active
    revision it was read under, and the revisions it viewed."""
    return f"{through_seq}:{active}:{','.join(map(str, sorted(views)))}"


def _held_basis(key: str) -> tuple[int, int, frozenset[str]] | None:
    try:
        seq, active, views = key.split(":")
        return int(seq), int(active), frozenset(views.split(","))
    except ValueError:
        return None


def _changes(held: list[dict], current: list[dict]) -> tuple[list[dict], list[str]]:
    """The entries of `current` that `held` lacks or holds otherwise, and the ids of
    the held entries `current` no longer holds, each entry named by its event."""
    kept = {entry["event"]["id"]: entry for entry in held}
    ids = {entry["event"]["id"] for entry in current}
    return (
        [entry for entry in current if kept.get(entry["event"]["id"]) != entry],
        [identity for identity in kept if identity not in ids],
    )


def since(state: dict, held: str, earlier: Callable[[int], dict]) -> None:
    """Make `state`, a whole answer, the tail of the reading `held` names where it can
    extend that reading. `earlier(seq)` is the browser reading at `seq`, from the
    snapshot `state` was read from and for the same views."""
    browser = state["browser"]
    basis = _held_basis(held) if browser is not None else None
    if basis is None:
        return
    seq, active, views = basis
    through = browser["basis"]["through_seq"]
    if (
        active != state["active"]["revision"]
        or not set(browser["views"]) <= views
        or seq > through
    ):
        return
    # The same log through the same sequence reads the same lists.
    before = earlier(seq)["views"] if seq < through else browser["views"]
    dropped = {}
    for revision, view in browser["views"].items():
        then = before[revision]
        document = view["document"]["projection"]
        thread = view["thread"]["projection"]
        document["entries"], dropped_document = _changes(
            then["document"]["projection"]["entries"], document["entries"]
        )
        thread["entries"], dropped_thread = _changes(
            then["thread"]["projection"]["entries"], thread["entries"]
        )
        view["undo"], dropped_undo = _changes(then["undo"], view["undo"])
        dropped[revision] = {
            "document": dropped_document,
            "thread": dropped_thread,
            "undo": dropped_undo,
        }
    state["events"] = [event for event in state["events"] if event["seq"] > seq]
    state["since"] = {"through_seq": seq, "dropped": dropped}
