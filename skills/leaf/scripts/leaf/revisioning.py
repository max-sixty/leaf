"""Activation of mutable source into immutable ordered revisions."""

from pathlib import Path
from typing import NamedTuple

from leaf.files import list_revisions, revision_path, write_revision
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
    """Validate and activate exact ``index.html`` bytes, or keep the last revision."""
    checked = check_source(page_dir, events, allow_transition=allow_transition)
    return activate_checked_source(page_dir, checked)


def activate_checked_source(page_dir: Path, checked: SourceCheck) -> Activation:
    """Activate a validation reading a caller has already inspected."""
    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else None
    if checked.errors:
        return Activation(active, "; ".join(checked.errors), False, checked)
    if (
        active is not None
        and revision_path(page_dir, active).read_bytes() == checked.document.data
    ):
        return Activation(active, None, False, checked)
    revision = (active or 0) + 1
    write_revision(page_dir, revision, checked.document.data)
    return Activation(revision, None, True, checked)
