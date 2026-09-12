"""Activation of mutable source into immutable ordered revisions."""

from pathlib import Path
from typing import NamedTuple

from leaf.files import list_revisions
from leaf.revision_artifact import read_artifact, write_artifact
from leaf.validation.source import SourceCheck, check_source


class Activation(NamedTuple):
    revision: int | None
    error: str | None
    created: bool
    check: SourceCheck


def activate_source(
    page_dir: Path,
    events: list,
    allow_transition: bool = False,
) -> Activation:
    """Activate complete valid source inputs, or keep the last good revision."""
    checked = check_source(page_dir, events, allow_transition=allow_transition)
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
