"""Activation of mutable source into immutable ordered revisions.

Activation judges a candidate: a source whose captured artifact differs from the
active revision's becomes the next revision if `check_source` finds nothing wrong
with it, and is refused otherwise, leaving the active revision live. A source
whose artifact is the active revision's is no candidate, and `check_source` judges
no transition for it (see its gate on `RevisionReading.unchanged`).

Every state read asks for activation first, so each page holds its last answer,
keyed on the page's stamps as `served_state.reading.source_readings` splits them.
A save moves the source reading, and the next read validates it and turns it into
a revision, which is what makes an edited `index.html` reach an open tab. An
answer that found the source to be the active revision holds until the source
moves: the log can grow under it without changing it, since the door judged every
event against the revision it names. A refusal holds only until either reading
moves, because an event can clear it, as resolving the thread on an id the save
dropped does.
"""

from pathlib import Path
from typing import NamedTuple

from leaf.event_log import read_events
from leaf.files import list_revisions
from leaf.revision_artifact import read_artifact, write_artifact
from leaf.served_state.reading import source_readings
from leaf.validation.source import SourceCheck, check_source


class Activation(NamedTuple):
    revision: int | None
    error: str | None
    created: bool


class _Held(NamedTuple):
    source: str
    history: str
    activation: Activation


_CACHE_LIMIT = 64
_held: dict[Path, _Held] = {}


def activate_source(page_dir: Path) -> Activation:
    """Activate complete valid source inputs, or keep the last good revision.

    The readings are taken before anything is read, so a write that lands during
    the check moves the page past the answer held here and the next call checks
    again. An activation that wrote a revision is held as the answer the next call
    would give: the source is now the active revision, and nothing was created."""
    key = page_dir.resolve()
    source, history = source_readings(page_dir)
    held = _held.get(key)
    if (
        held
        and held.source == source
        and (held.activation.error is None or held.history == history)
    ):
        return held.activation
    activation = activate_checked_source(
        page_dir, check_source(page_dir, read_events(page_dir), allow_transition=False)
    )
    _held.pop(key, None)
    settled = activation._replace(created=False) if activation.created else activation
    _held[key] = _Held(source, history, settled)
    if len(_held) > _CACHE_LIMIT:
        del _held[next(iter(_held))]
    return activation


def activate_checked_source(page_dir: Path, checked: SourceCheck) -> Activation:
    """Activate a validation reading a caller has already inspected."""
    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else None
    if checked.errors:
        return Activation(active, "; ".join(checked.errors), False)
    if (
        active is not None
        and read_artifact(page_dir, active).digest == checked.artifact.digest
    ):
        return Activation(active, None, False)
    revision = (active or 0) + 1
    write_artifact(page_dir, revision, checked.artifact)
    return Activation(revision, None, True)
