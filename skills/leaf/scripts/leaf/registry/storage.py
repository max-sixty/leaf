"""Vendored registry storage and page lookup."""

from collections.abc import Collection
from pathlib import Path

from leaf.files import file_stamp, latest_revision, read_json
from leaf.page_memory import Slot, memo

from ..refusals import Refused
from .contract import RegistryError, read_registry_declarations, registry_error
from .layer import check_layer_facts


class _Layer(Slot):
    """The page's vendored layer, by its file's stamp."""


class _Candidate(Slot):
    """The page's candidate vocabulary, by its inputs' stamps and active revision."""


def load_registry(page_dir: Path):
    """The page's complete vendored layer, or None before `page init`.

    The layer is `page init`'s own output rather than anything an author writes, so a
    reader that rejects it wants a re-vendor rather than an edit. It checks only that
    the layer declares what every reader looks up. Its `$events` copy may be another
    Leaf's at this protocol: it is the page runtime's, and admission reads the running
    Leaf's own (`registry.kernel`); `read_page_registry` validates the vocabulary where
    it is new.

    Kept in the page's memory while the file's stamp holds, because an action POST
    asks for the whole vocabulary before it can check a single press."""
    path = page_dir / "registry.json"
    stamp = file_stamp(path)
    if not stamp:
        return _read_layer(page_dir, path)
    return memo(page_dir, _Layer).get(stamp, lambda: _read_layer(page_dir, path))


def _read_layer(page_dir: Path, path: Path) -> dict | None:
    try:
        registry = read_registry_declarations(path)
        if registry is not None:
            check_layer_facts(registry, path)
    except RegistryError as error:
        raise _revendor(page_dir, error) from None
    return registry


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
        for directory in ("widgets", "page/widgets")
        for path in widget_paths(page_dir, directory)
    )
    active = latest_revision(page_dir)
    key = (
        file_stamp(page_dir / "registry.json"),
        file_stamp(page_dir / "page" / "registry.json"),
        widgets,
        active,
    )

    def compose():
        layer = load_registry(page_dir)
        if layer is None:
            return None
        return compose_candidate(
            page_dir,
            layer,
            [path for path, _stamp in widgets],
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
    layer's `widgets/` and the page's own `page/widgets/`. `read_page_registry`
    composes the vendored layer; `page init` composes the layer it is about to
    vendor, to check a re-vendor before writing it. ``validated`` is a vocabulary
    already validated, which a composition equal to it is not validated against again.

    A fault the layer shows on its own is the vendored layer's, which a re-vendor
    repairs, whether or not the page declares anything over it; one that appears only
    with the page's declarations is the page's to fix."""
    from .page import compose_page_registry

    source = page_dir / "page" / "registry.json"
    declarations = read_registry_declarations(source) or {}

    try:
        return compose_page_registry(
            layer,
            declarations,
            widgets,
            source=source if declarations else page_dir / "registry.json",
            validated=validated,
        )
    except RegistryError as error:
        if not declarations:
            raise _revendor(page_dir, error) from None
        # The layer alone, validated afresh: the active revision's vocabulary may be
        # this same layer, stamped before this Leaf, and would excuse it unread.
        try:
            compose_page_registry(layer, {}, widgets, source=page_dir / "registry.json")
        except RegistryError as layer_error:
            raise _revendor(page_dir, layer_error) from None
        raise


def _revendor(page_dir: Path, error: RegistryError) -> RegistryError:
    """A fault in the vendored layer, which `page init` wrote and re-vendoring fixes."""
    return RegistryError(error.findings[0].but(values={"revendor": str(page_dir)}))


def _layer_packages(layer: dict, path: Path) -> list[str]:
    packages = layer.get("packages", [])
    if (
        not isinstance(packages, list)
        or not all(isinstance(value, str) and value for value in packages)
        or len(set(packages)) != len(packages)
    ):
        raise registry_error("layer-packages", path)
    return packages


def layer_packages(page_dir: Path) -> list[str]:
    """The package selections this page's vendored layer records.

    Read on its own, rather than through `layer_metadata` or the declarations
    reader, since a re-vendor exists to repair the rest of the file: `page init`
    reuses the recorded selection when no `--package` is given, so the page it
    would fix must not refuse it."""
    path = page_dir / "registry.json"
    return _layer_packages((read_json(path) or {}).get("$layer", {}), path)


def layer_metadata(page_dir: Path) -> dict:
    """The identity recorded by this page's complete vendored layer.

    `page init` writes it, so it is read as written; a layer vendored before this
    identity existed is one `page init` replaces."""
    path = page_dir / "registry.json"
    layer = (read_registry_declarations(path) or {}).get("$layer", {})
    if not (layer.get("generation") and layer.get("fingerprint")):
        raise registry_error("layer-identity", path)
    producer = {
        kind: value
        for kind in ("commit", "dirty", "committed", "installed")
        if (value := layer.get("producer", {}).get(kind)) is not None
    }
    return {
        "generation": layer["generation"],
        "fingerprint": layer["fingerprint"],
        # A page vendored before the server identity existed reads as having none.
        **({"server": layer["server"]} if "server" in layer else {}),
        "packages": _layer_packages(layer, path),
        **({"producer": producer} if producer else {}),
    }


def require_registry(page_dir: Path) -> dict:
    """The active revision's vocabulary, or the candidate before first activation."""
    registry = active_registry(page_dir)
    if registry is None:
        raise Refused(f"no registry.json in {page_dir}; run `leaf page init` first")
    return registry


def active_registry(page_dir: Path) -> dict | None:
    """Read semantic commands against the same declarations as the live document."""
    return page_vocabulary(page_dir, latest_revision(page_dir))


def page_vocabulary(page_dir: Path, revision: int | None) -> dict | None:
    """The vocabulary one of the page's documents is read in.

    A revision's is the registry its capture froze, which a later re-vendor or page
    declaration cannot reach. With no revision, the document is the candidate, so its
    vocabulary is the layer composed with the page's own declarations — the same one
    the candidate would be captured under. None before `page init`.
    """
    if revision is not None:
        from leaf.revision_artifact import read_revision

        return read_revision(page_dir, revision).registry
    candidate = read_page_registry(page_dir)
    return candidate.registry if candidate is not None else None
