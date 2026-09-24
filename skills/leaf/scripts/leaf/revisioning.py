"""Activation of mutable source into immutable ordered revisions.

Activation is a function of the page directory: `index.html`, its `page/`
inputs, the vendored layer, `data/`, the revisions already written, and the log
the source is checked against. Every state read asks for it first, so a page
that has not moved since the last activation answers from that one, keyed on
the page's own reading (`served_state.reading.page_reading`) — the stamp the
news stream and `leaf wait` follow. A save moves that reading, and the next
read that asks validates it and turns it into a revision, which is what makes
an edited `index.html` reach an open tab.
"""

from pathlib import Path
from typing import NamedTuple

from leaf.event_log import read_events
from leaf.files import list_revisions
from leaf.revision_artifact import read_artifact, write_artifact
from leaf.served_state.reading import page_reading
from leaf.validation.source import SourceCheck, check_source


class Activation(NamedTuple):
    revision: int | None
    error: str | None
    created: bool
    check: SourceCheck


_CACHE_LIMIT = 64
# (page, allow_transition) -> (the page reading taken before the check, its answer)
_activations: dict[tuple[Path, bool], tuple[str, Activation]] = {}


def activate_source(page_dir: Path, *, allow_transition: bool = False) -> Activation:
    """Activate complete valid source inputs, or keep the last good revision.

    The reading is taken before anything is read, so a write that lands during
    the check moves the page past the answer held here and the next call checks
    again. An activation that wrote a revision is not held: the revision moved
    the reading, and the answer at the new one is that nothing was created."""
    key = (page_dir.resolve(), allow_transition)
    reading = page_reading(page_dir)
    if (held := _activations.get(key)) and held[0] == reading:
        return held[1]
    checked = check_source(
        page_dir, read_events(page_dir), allow_transition=allow_transition
    )
    activation = activate_checked_source(page_dir, checked)
    _activations.pop(key, None)
    if not activation.created:
        _activations[key] = (reading, activation)
        if len(_activations) > _CACHE_LIMIT:
            del _activations[next(iter(_activations))]
    return activation


def activate_checked_source(page_dir: Path, checked: SourceCheck) -> Activation:
    """Activate a validation reading a caller has already inspected."""
    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else None
    if checked.errors:
        return Activation(active, "; ".join(checked.errors), False, checked)
    if (
        active is not None
        and read_artifact(page_dir, active).digest == checked.artifact.digest
    ):
        return Activation(active, None, False, checked)
    revision = (active or 0) + 1
    write_artifact(page_dir, revision, checked.artifact)
    return Activation(revision, None, True, checked)
