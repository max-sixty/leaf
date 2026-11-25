"""A page's layer record, and the vocabulary every reader composes from it.

A page records which packages it selects (`LAYER`), never the
layer itself: every Leaf that serves, checks or exports the page composes its own
(`layer.selected_layer`), as it supplies its own runtime (`runtime_selection`)."""

import json
import re
from collections.abc import Collection
from pathlib import Path

from leaf.base.files import file_stamp, latest_revision
from leaf.base.findings import Finding
from leaf.base.page_memory import Slot, Stamped, memo, once
from leaf.base.refusals import Refused
from leaf.base.schema import LAYER_FILE
from leaf.base.state import PLUGIN_ROOT, Record, stored_record
from leaf.source.registry.contract import RegistryError, read_registry_declarations
from leaf.source.registry.kernel import kernel_protocol

LAYER = Record(
    "layer",
    {
        "description": (
            "A page's layer selection, `layer.json` in its directory: the packages"
            " every Leaf that reads the page composes, in order, and the generation"
            " an open document speaks. Its `format` names the page protocol of the"
            " Leaf that last initialized the page."
        ),
        "type": "object",
        "properties": {
            "packages": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
            "generation": {"type": "string", "minLength": 1},
        },
        "required": ["packages", "generation"],
    },
    since=kernel_protocol(),
    kept=("packages",),
)


class IncompatibleLayer(RegistryError):
    """A page another Leaf initialized, at another page protocol than this Leaf's
    (`layer_record`), refused before anything reads its layer. Its repair is the one
    its finding names."""


class _Candidate(Slot):
    """The page's candidate vocabulary, by its inputs' stamps and active revision."""


class _Revisions(Stamped):
    """The vocabularies the page's revisions are read in (`revision_vocabulary`), one
    for each layer record, set of declarations and set of page widgets a revision
    captured. Each is kept beside the layer vocabulary it was composed over, and
    composed again once another replaces that.

    They are kept with the page rather than with the layer's vocabulary, which many
    pages may share (`layer._held`). Each names its page's generation under
    `$layer`, so only the page's samples, which read its revisions under that
    generation, could share one, and each sample composes its own instead. Kept with
    a shared vocabulary, they would outlast every page that read them."""


def layer_record(page_dir: Path) -> dict | None:
    """The page's layer record, less its `format`, or None where the page holds none.
    A page whose layer record is at another format is refused (`IncompatibleLayer`),
    as `newer-layer` where the format's number is higher than this Leaf's and as
    `foreign-layer` where it is lower (`layer-registry.md`, "Page protocol")."""
    stored = stored_record(page_dir / LAYER_FILE)
    if stored is None or (recorded := LAYER.since_of(stored)) is None:
        return None
    if recorded != LAYER.since:
        values = {
            "page": str(page_dir),
            "leaf": str(PLUGIN_ROOT),
            "protocol": LAYER.since,
        }
        refusal = (
            Finding("newer-layer", values=values)
            if recorded > LAYER.since
            else Finding("foreign-layer", values={**values, "recorded": recorded})
        )
        raise IncompatibleLayer([refusal])
    del stored["format"]
    return stored


def layer_packages(page_dir: Path) -> list[str] | None:
    """The packages the page's layer record selects, whichever Leaf wrote it
    (`state.Record.read_any`), or None where the page holds no layer record."""
    record = LAYER.read_any(page_dir / LAYER_FILE)
    return None if record is None else list(record["packages"])


def selected(record: dict, page_dir: Path):
    """The layer `record` selects for the page at `page_dir`, with every file it
    serves, as this Leaf composes it to serve, export or check the page
    (`layer.selected_layer`), refused as a registry fault where a selected package
    is gone or invalid."""
    from leaf.source.layer import selected_layer

    return _compose_selected(selected_layer, record, page_dir)


def selected_vocabulary(record: dict, page_dir: Path):
    """The vocabulary of the layer `record` selects, all a reader of the page's
    documents needs (`layer.selected_vocabulary`), refused as `selected` refuses
    a selected package that is gone or whose registry can't be read or merged. Its
    registry is not validated (`layer.compose_vocabulary`)."""
    from leaf.source.layer import selected_vocabulary

    return _compose_selected(selected_vocabulary, record, page_dir)


def _compose_selected(compose, record: dict, page_dir: Path):
    try:
        return compose(tuple(record["packages"]), page_dir)
    except Refused as error:
        raise RegistryError(
            [Finding("layer-unavailable", values={"error": str(error)})]
        ) from None


def layer_vocabulary(record: dict, page_dir: Path) -> dict:
    """The vocabulary of the layer `record` selects, with the selection and the
    generation the browser speaks under `$layer`. Each call makes a new copy of the
    layer's registry, sharing its entries."""
    vocabulary = selected_vocabulary(record, page_dir)
    return {**vocabulary.registry, "$layer": layer_metadata_of(record)}


def layer_widgets(record: dict, page_dir: Path) -> list[str]:
    """The page-root-relative widget entry modules the selected layer serves."""
    return sorted(
        f"widgets/{name}"
        for name in selected_vocabulary(record, page_dir).widgets
        if re.fullmatch(r"lf-[^/]*\.js", name)
    )


def revision_vocabulary(
    manifest: dict, declarations: bytes | None, page_dir: Path
) -> dict:
    """The vocabulary this Leaf reads a revision of the page at `page_dir` in: the
    declarations it captured, `declarations`, over the layer its `manifest` selects,
    with the page widgets it captured. Every revision of the page selecting the same
    layer and declaring the same shares one read-only reading (`_Revisions`)."""
    return _revision_composition(manifest, declarations, page_dir)[0]


def revision_inputs(
    manifest: dict, declarations: bytes | None, page_dir: Path
) -> tuple[dict, dict]:
    """The layer vocabulary and page declarations this Leaf composed and validated a
    revision's vocabulary from (`revision_vocabulary`), as
    `page.compose_page_registry` takes a composition already validated. The layer
    is the one that composition read, so a package installed since pairs with
    nothing it wasn't validated over."""
    return _revision_composition(manifest, declarations, page_dir)[1]


def _revision_composition(
    manifest: dict, declarations: bytes | None, page_dir: Path
) -> tuple[dict, tuple[dict, dict]]:
    widgets = tuple(
        implementation["path"].lstrip("/")
        for implementation in manifest["implementations"].values()
        if implementation["owner"] == "page"
    )
    layer = manifest["layer"]
    held = memo(page_dir, _Revisions).of(
        (json.dumps(layer, sort_keys=True), declarations, widgets),
        (selected_vocabulary(layer, page_dir),),
    )
    return once(
        held,
        "composition",
        lambda: _compose_revision(layer, declarations, widgets, page_dir),
    )


def _compose_revision(
    record: dict, declarations: bytes | None, widgets: tuple[str, ...], page_dir: Path
) -> tuple[dict, tuple[dict, dict]]:
    from leaf.source.registry.page import compose_page_registry

    # The selected layer is validated where a Leaf composes its files
    # (`layer-registry.md`), so a revision declaring nothing over it is not
    # validated on a read.
    vocabulary = layer_vocabulary(record, page_dir)
    declared = json.loads(declarations) if declarations else {}
    composed = compose_page_registry(
        vocabulary,
        declared,
        [*layer_widgets(record, page_dir), *widgets],
        validated=(vocabulary, {}),
    )
    return composed.registry, (vocabulary, declared)


def load_registry(page_dir: Path):
    """The vocabulary of the page's layer, or None before `page init`."""
    record = layer_record(page_dir)
    return None if record is None else layer_vocabulary(record, page_dir)


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
    from leaf.source.revision_artifact import read_revision

    page_dir = page_dir.absolute()
    widgets = tuple(
        (path, file_stamp(page_dir / path))
        for path in widget_paths(page_dir, "page/widgets")
    )
    active = latest_revision(page_dir)
    record = layer_record(page_dir)
    key = (
        file_stamp(page_dir / LAYER_FILE),
        # The vocabulary the record selects, which a package install resolves to
        # other roots (`layer.selected_vocabulary`).
        selected_vocabulary(record, page_dir) if record else None,
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
    from leaf.source.registry.page import compose_page_registry

    source = page_dir / "page" / "registry.json"
    declarations = read_registry_declarations(source) or {}
    return compose_page_registry(
        layer,
        declarations,
        widgets,
        source=source if declarations else page_dir / LAYER_FILE,
        validated=validated,
    )


def layer_metadata_of(record: dict) -> dict:
    """What a page's layer is to its readers: its generation and selection."""
    return {
        "generation": record["generation"],
        "packages": list(record["packages"]),
    }


def served_layer(metadata: dict, page_dir: Path) -> dict:
    """`metadata` as the served state names the layer the page at `page_dir` is read
    under: with the fingerprint of the layer this Leaf composes for it, and this Leaf
    as its producer, the one About this page shows (`runtime/panel/page-about.js`)."""
    from leaf.source.layer import running_leaf

    return {
        **metadata,
        "fingerprint": selected(metadata, page_dir).fingerprint,
        "producer": running_leaf(),
    }


def layer_metadata(page_dir: Path) -> dict:
    """The page's layer identity (`layer_metadata_of`), refused before init and at
    another page protocol (`layer_record`)."""
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
        from leaf.source.revision_artifact import read_revision

        return read_revision(page_dir, revision).registry
    candidate = read_page_registry(page_dir)
    return candidate.registry if candidate is not None else None
