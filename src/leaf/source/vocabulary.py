"""The vocabulary each of a page's documents is read in (`page_vocabulary`): a
revision's, the page declarations its capture kept, composed by this Leaf over the layer
of the package selection it kept (`revision_artifact.revision_vocabulary`), or the
candidate's, the page's own declarations over the layer its record selects
(`read_page_registry`)."""

from collections.abc import Collection
from pathlib import Path

from leaf.base.files import file_stamp, latest_revision
from leaf.base.page_memory import Slot, memo
from leaf.base.refusals import Refused
from leaf.base.schema import LAYER_FILE
from leaf.source.layer import layer_vocabulary, layer_widgets, selected_vocabulary
from leaf.source.registry.contract import read_registry_declarations
from leaf.source.registry.page import compose_page_registry
from leaf.source.registry.storage import layer_record
from leaf.source.revision_artifact import read_revision


class _Candidate(Slot):
    """The page's candidate vocabulary, by its inputs' stamps and active revision."""


def load_registry(page_dir: Path):
    """The vocabulary of the page's layer, or None before `page init`."""
    record = layer_record(page_dir)
    if record is None:
        return None
    return layer_vocabulary(record, selected_vocabulary(record, page_dir))


def read_page_registry(page_dir: Path):
    """Read the mutable candidate's vocabulary and widget provenance.

    Revision capture uses ``compose_page_registry`` directly with its captured
    declarations and file inventory. This filesystem reading is for callers
    examining the authored candidate, never an already activated revision.

    The candidate is validated where its layer or declarations differ from the
    active revision's, which were validated together when its vocabulary was
    composed: a page whose layer and declarations have not moved is not validated
    again. The page keeps the composition until any input file or the active
    revision changes.
    """
    page_dir = page_dir.absolute()
    widgets = tuple(
        (path, file_stamp(page_dir / path))
        for path in widget_paths(page_dir, "page/widgets")
    )
    active = latest_revision(page_dir)
    stamp = file_stamp(page_dir / LAYER_FILE)
    record = layer_record(page_dir)
    if record is None:
        return None
    # The key and the composition read one resolution of the selection
    # (`layer.selected_vocabulary`).
    layer = selected_vocabulary(record, page_dir)
    key = (
        stamp,
        layer,
        file_stamp(page_dir / "page" / "registry.json"),
        widgets,
        active,
    )

    def compose():
        return compose_candidate(
            page_dir,
            layer_vocabulary(record, layer),
            [*layer_widgets(layer), *(path for path, _ in widgets)],
            validated=read_revision(page_dir, active).inputs if active else None,
        )

    return memo(page_dir, _Candidate).get(key, compose)


def widget_paths(page_dir: Path, directory: str) -> list[str]:
    """The widget modules under one of a page's directories, page-root-relative."""
    return sorted(
        path.relative_to(page_dir).as_posix()
        for path in (page_dir / directory).glob("lf-*.js")
        if path.is_file()
    )


def compose_candidate(
    page_dir: Path,
    layer: dict,
    widgets: Collection[str],
    *,
    validated: tuple[dict, dict] | None = None,
):
    """The candidate's vocabulary: the page's own declarations over `layer`.

    `widgets` are the page-root-relative widget files the candidate can load, the
    layer's `widgets/` and the page's own `page/widgets/`. ``validated`` is the
    layer and declarations of a composition already validated, which a composition
    of the same two is not validated against again."""
    source = page_dir / "page" / "registry.json"
    declarations = read_registry_declarations(source) or {}
    return compose_page_registry(
        layer,
        declarations,
        widgets,
        source=source if declarations else page_dir / LAYER_FILE,
        validated=validated,
    )


def page_vocabulary(page_dir: Path, revision: int | None) -> dict | None:
    """The vocabulary one of the page's documents is read in.

    A revision's is composed from the page declarations and package selection its
    capture kept (`revision_artifact.revision_vocabulary`), so the page's later
    declarations and layer record don't change it. With no revision, the document is
    the candidate, so its vocabulary is the layer its record selects composed with the
    page's own declarations, the inputs a capture of it would keep. None before
    `page init`.
    """
    if revision is not None:
        return read_revision(page_dir, revision).registry
    candidate = read_page_registry(page_dir)
    return candidate.registry if candidate is not None else None


def active_registry(page_dir: Path) -> dict | None:
    """Read semantic commands against the same declarations as the live document."""
    return page_vocabulary(page_dir, latest_revision(page_dir))


def require_registry(page_dir: Path) -> dict:
    """The active revision's vocabulary, or the candidate before first activation."""
    registry = active_registry(page_dir)
    if registry is None:
        raise Refused(f"no {LAYER_FILE} in {page_dir}; run `leaf page init` first")
    return registry


def require_candidate(page_dir: Path):
    """The candidate's vocabulary (`read_page_registry`), refused before init."""
    candidate = read_page_registry(page_dir)
    if candidate is None:
        raise Refused(f"no {LAYER_FILE} in {page_dir}; run `leaf page init` first")
    return candidate
