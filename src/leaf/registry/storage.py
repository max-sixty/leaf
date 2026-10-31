"""A page's layer record, and the vocabulary every reader composes from it.

A page records which packages and theme it selects (`LAYER`), never the
layer itself: every Leaf that serves, checks or exports the page composes its own
(`layer.selected_layer`), as it supplies its own runtime (`runtime_selection`)."""

import json
import re
from collections.abc import Collection
from pathlib import Path

from leaf.files import file_stamp, latest_revision
from leaf.findings import Finding
from leaf.page_memory import Slot, memo
from leaf.schema import LAYER_FILE
from leaf.state import Record

from ..refusals import Refused
from .contract import (
    RegistryError,
    read_registry_declarations,
)

LAYER = Record(
    "layer",
    {
        "description": (
            "A page's layer selection, `layer.json` in its directory: the packages"
            " and theme every Leaf that reads the page composes, the"
            " generation an open document speaks, and the page protocol a Leaf last"
            " initialized it at."
        ),
        "type": "object",
        "properties": {
            "packages": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
            "theme": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "minLength": 1},
                            "source": {"enum": ["explicit", "default"]},
                        },
                        "required": ["name", "source"],
                    },
                ]
            },
            "generation": {"type": "string", "minLength": 1},
            "protocol": {"type": "integer"},
        },
        "required": ["packages", "theme", "generation", "protocol"],
    },
    since=36,
)


class IncompatibleLayer(RegistryError):
    """A page initialized at another page protocol than this Leaf's
    (`layer.incompatible_layer`), refused before its layer is composed. Its repair
    is the one that refusal names."""


class _Candidate(Slot):
    """The page's candidate vocabulary, by its inputs' stamps and active revision."""


def layer_record(page_dir: Path) -> dict | None:
    """The page's layer record, or None before `page init`. A newer Leaf's record,
    at a later shape than this Leaf reads, refuses the page as `newer-layer`
    (`IncompatibleLayer`) rather than reading as none, which would have `page init`
    replace the page's selection under this Leaf."""
    path = page_dir / LAYER_FILE
    record = LAYER.read(path)
    if record is None and LAYER.newer(path):
        from leaf.layer import newer_layer

        raise IncompatibleLayer([newer_layer(page_dir)])
    return record


def selected(record: dict, page_dir: Path):
    """The layer `record` selects for the page at `page_dir`, as this Leaf composes
    it (`layer.selected_layer`), refused as a registry fault where a selected package
    is gone or invalid."""
    from leaf.layer import selected_layer
    from leaf.themes import theme_package

    theme = theme_package(record["theme"])
    try:
        return selected_layer(tuple(record["packages"]), theme, page_dir)
    except Refused as error:
        raise RegistryError(
            [Finding("layer-unavailable", values={"error": str(error)})]
        ) from None


def layer_vocabulary(record: dict, page_dir: Path) -> dict:
    """The vocabulary of the layer `record` selects, with the selection and the
    generation the browser speaks under `$layer`, held with the composition, since
    an action POST asks for the whole vocabulary before it can check a press."""
    metadata = layer_metadata_of(record)
    layer = selected(record, page_dir)
    key = ("layer", json.dumps(metadata, sort_keys=True))
    if key not in layer.readings:
        layer.readings[key] = {**layer.registry, "$layer": metadata}
    return layer.readings[key]


def layer_widgets(record: dict, page_dir: Path) -> list[str]:
    """The page-root-relative widget entry modules the selected layer serves."""
    return sorted(
        f"widgets/{name}"
        for name in selected(record, page_dir).directory_files["widgets"]
        if re.fullmatch(r"lf-[^/]*\.js", name)
    )


def revision_vocabulary(
    manifest: dict, declarations: bytes | None, page_dir: Path
) -> dict:
    """The vocabulary this Leaf reads a revision of the page at `page_dir` in: the
    declarations it captured, `declarations`, over the layer its `manifest` selects,
    with the page widgets it captured. Every revision selecting the same layer and declaring the same shares
    one read-only reading."""
    widgets = tuple(
        implementation["path"].lstrip("/")
        for implementation in manifest["implementations"].values()
        if implementation["owner"] == "page"
    )
    layer = manifest["layer"]
    readings = selected(layer, page_dir).readings
    key = ("revision", json.dumps(layer, sort_keys=True), declarations, widgets)
    if key not in readings:
        readings[key] = _revision_vocabulary(layer, declarations, widgets, page_dir)
    return readings[key]


def _revision_vocabulary(
    record: dict, declarations: bytes | None, widgets: tuple[str, ...], page_dir: Path
) -> dict:
    from .page import compose_page_registry

    # The selected layer was validated where it was composed, so a revision
    # declaring nothing over it is not validated again.
    vocabulary = layer_vocabulary(record, page_dir)
    return compose_page_registry(
        vocabulary,
        json.loads(declarations) if declarations else {},
        [*layer_widgets(record, page_dir), *widgets],
        validated=vocabulary,
    ).registry


def load_registry(page_dir: Path):
    """The vocabulary of the page's layer, or None before `page init`.

    It refuses a page at another page protocol first (`IncompatibleLayer`)."""
    from leaf.layer import incompatible_layer

    record = layer_record(page_dir)
    if record is None:
        return None
    if refusal := incompatible_layer(page_dir, record):
        raise IncompatibleLayer([refusal])
    return layer_vocabulary(record, page_dir)


def read_page_registry(page_dir: Path):
    """Read the mutable candidate's vocabulary and widget provenance.

    Revision capture uses ``compose_page_registry`` directly with its captured
    declarations and file inventory. This filesystem reading is for callers
    examining the authored candidate, never an already activated revision.

    The candidate is validated where it differs from the active revision's
    vocabulary, which was validated when its revision activated: a page whose layer
    and declarations have not moved is not validated again. The page keeps the
    composition until any input file or the active revision changes.
    """
    from leaf.revision_artifact import read_revision

    page_dir = page_dir.absolute()
    widgets = tuple(
        (path, file_stamp(page_dir / path))
        for path in widget_paths(page_dir, "page/widgets")
    )
    active = latest_revision(page_dir)
    record = layer_record(page_dir)
    key = (
        file_stamp(page_dir / LAYER_FILE),
        # The composition the record selects, which a package install resolves to
        # other roots (`layer.selected_layer`).
        selected(record, page_dir) if record else None,
        file_stamp(page_dir / "page" / "registry.json"),
        widgets,
        active,
    )

    def compose():
        layer = load_registry(page_dir)
        if layer is None:
            return None
        record = layer_record(page_dir)
        assert record is not None
        return compose_candidate(
            page_dir,
            layer,
            [
                *layer_widgets(record, page_dir),
                *(path for path, _ in widgets),
            ],
            validated=read_revision(page_dir, active).registry if active else None,
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
    validated: dict | None = None,
):
    """The candidate's vocabulary: the page's own declarations over `layer`.

    `widgets` are the page-root-relative widget files the candidate can load, the
    layer's `widgets/` and the page's own `page/widgets/`. ``validated`` is a
    vocabulary already validated, which a composition equal to it is not validated
    against again."""
    from .page import compose_page_registry

    source = page_dir / "page" / "registry.json"
    declarations = read_registry_declarations(source) or {}
    return compose_page_registry(
        layer,
        declarations,
        widgets,
        source=source if declarations else page_dir / LAYER_FILE,
        validated=validated,
    )


def layer_packages(page_dir: Path) -> list[str]:
    """The package selections this page's layer record names; none before init."""
    record = layer_record(page_dir)
    return list(record["packages"]) if record else []


def layer_metadata_of(record: dict) -> dict:
    """What a page's layer is to its readers: its generation and selection."""
    return {
        "generation": record["generation"],
        "packages": list(record["packages"]),
        "theme": record["theme"],
    }


def served_layer(metadata: dict, page_dir: Path) -> dict:
    """`metadata` as the served state names the layer the page at `page_dir` is read
    under: with the fingerprint of the layer this Leaf composes for it, and this Leaf
    as its producer, the one the leaf's menu shows (`runtime/page-about.js`)."""
    from leaf.layer import running_leaf

    return {
        **metadata,
        "fingerprint": selected(metadata, page_dir).fingerprint,
        "producer": running_leaf(),
    }


def layer_metadata(page_dir: Path) -> dict:
    """The page's layer identity (`layer_metadata_of`), refused before init."""
    record = layer_record(page_dir)
    if record is None:
        raise RegistryError([Finding("no-layer", values={"page": str(page_dir)})])
    return layer_metadata_of(record)


def require_candidate(page_dir: Path):
    """The candidate's vocabulary (`read_page_registry`), refused before init."""
    candidate = read_page_registry(page_dir)
    if candidate is None:
        raise Refused(f"no {LAYER_FILE} in {page_dir}; run `leaf page init` first")
    return candidate


def require_registry(page_dir: Path) -> dict:
    """The active revision's vocabulary, or the candidate before first activation."""
    registry = active_registry(page_dir)
    if registry is None:
        raise Refused(f"no {LAYER_FILE} in {page_dir}; run `leaf page init` first")
    return registry


def active_registry(page_dir: Path) -> dict | None:
    """Read semantic commands against the same declarations as the live document."""
    return page_vocabulary(page_dir, latest_revision(page_dir))


def page_vocabulary(page_dir: Path, revision: int | None) -> dict | None:
    """The vocabulary one of the page's documents is read in.

    A revision's is the registry its capture froze, which a later `page init` or page
    declaration cannot reach. With no revision, the document is the candidate, so its
    vocabulary is the layer composed with the page's own declarations — the same one
    the candidate would be captured under. None before `page init`.
    """
    if revision is not None:
        from leaf.revision_artifact import read_revision

        return read_revision(page_dir, revision).registry
    candidate = read_page_registry(page_dir)
    return candidate.registry if candidate is not None else None
