"""A page's layer record: the packages it selects, at the page protocol of the Leaf
that initialized it.

A page records which packages it selects (`LAYER`), never the
layer itself: every Leaf that serves, checks or exports the page composes its own
(`layer.selected_layer`), as it supplies its own runtime (`runtime_selection`)."""

from pathlib import Path

from leaf.base.findings import Finding
from leaf.base.schema import LAYER_FILE
from leaf.base.state import (
    PLUGIN_ROOT,
    Record,
    kernel_protocol,
    replace_bytes,
    stored_record,
)
from leaf.source.registry.contract import RegistryError

LAYER = Record(
    "layer",
    {
        "description": (
            "A page's layer selection, `layer.json` in its directory: the packages"
            " every Leaf that reads the page composes, in order, and the generation"
            " an open document speaks. Its `format` names the page protocol of the"
            " Leaf that last initialized the page, so unlike every other record it"
            " keeps one file whatever its shape (`write_layer`)."
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
)


class IncompatibleLayer(RegistryError):
    """A page another Leaf initialized, at another page protocol than this Leaf's
    (`layer_record`), refused before anything reads its layer. Its repair is the one
    its finding names."""


def layer_record(page_dir: Path) -> dict | None:
    """The page's layer record, less its `format`, or None where the page holds none.
    A page whose layer record is at another format is refused (`IncompatibleLayer`),
    as `newer-layer` where the format's number is higher than this Leaf's and as
    `foreign-layer` where it is lower (`layer-registry.md`, "Page protocol")."""
    stored = stored_record(page_dir / LAYER_FILE)
    if stored is None or (recorded := _protocol(stored)) is None:
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
    """The packages the page's layer record selects, at whichever protocol a Leaf
    wrote it, or None where the page holds no layer record. A renewal carries them
    to this Leaf's protocol (`vendoring.renew_layer`), since it replaces the record
    rather than leaving it beside a new one (`write_layer`)."""
    stored = stored_record(page_dir / LAYER_FILE)
    if stored is None or _protocol(stored) is None:
        return None
    return list(stored["packages"])


def write_layer(page_dir: Path, record: dict) -> None:
    """Write the page's layer record, replacing one at any protocol. A record of
    every other kind keeps a file per shape (`state.Record.file`), but the layer's
    `format` is the page's protocol, which every Leaf reads to refuse a page at
    another (`layer_record`), so a page holds one: two would let two protocols
    write one log. Only the session holding the page moves it to another protocol
    (`service.refuse_held`)."""
    path = page_dir / LAYER_FILE
    replace_bytes([(path, LAYER.encode(record), not path.is_symlink())])


def _protocol(stored: dict) -> int | None:
    """The page protocol a stored layer record's `format` names, or None where it
    is no layer record."""
    kind, _, protocol = str(stored.get("format", "")).rpartition("/")
    return int(protocol) if kind == "leaf-layer" and protocol.isdecimal() else None


def layer_metadata_of(record: dict) -> dict:
    """What a page's layer is to its readers: its generation and selection."""
    return {
        "generation": record["generation"],
        "packages": list(record["packages"]),
    }


def layer_metadata(page_dir: Path) -> dict:
    """The page's layer identity (`layer_metadata_of`), refused before init and at
    another page protocol (`layer_record`)."""
    record = layer_record(page_dir)
    if record is None:
        raise RegistryError([Finding("no-layer", values={"page": str(page_dir)})])
    return layer_metadata_of(record)
