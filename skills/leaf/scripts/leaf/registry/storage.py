"""Vendored registry storage and page lookup."""

import re
import sys
from collections.abc import Collection
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from leaf.files import file_stamp, latest_revision, read_json

from .contract import RegistryError, read_registry_declarations
from .layer import required_layer_declarations, validate_event_contracts

_registries = {}  # registry.json -> (its stamp, the vocabulary it holds)


def load_registry(page_dir: Path):
    """The page's complete vendored layer, or None before `page init`.

    The layer is `page init`'s own output rather than anything an author writes, so a
    reader that rejects it wants a re-vendor rather than an edit. It checks only what
    the running Leaf can disagree with, the kernel's event contract, which a page
    vendored by an earlier Leaf may carry in an older form; `read_page_registry`
    validates the vocabulary where it is new.

    Held once per vendored file, because an action POST asks for the whole vocabulary
    before it can check a single press."""
    path = page_dir / "registry.json"
    stamp = file_stamp(path)
    if stamp and (held := _registries.get(path)) and held[0] == stamp:
        return held[1]
    try:
        registry = read_registry_declarations(path)
        if registry is not None:
            kinds = required_layer_declarations(registry, path)[0]
            validate_event_contracts(kinds, path)
    except RegistryError as error:
        raise _revendor(page_dir, error) from None
    if stamp:
        _registries[path] = (stamp, registry)
    return registry


def read_page_registry(page_dir: Path):
    """Read the mutable candidate's vocabulary and widget provenance.

    Revision capture uses ``compose_page_registry`` directly with its captured
    declarations and file inventory. This filesystem reading is for callers
    examining the authored candidate, never an already activated revision.

    The candidate is validated where it differs from the active revision's
    vocabulary, which was validated when its revision activated: a page whose layer
    and declarations have not moved is not validated again.
    """
    page_dir = page_dir.absolute()
    widgets = tuple(
        (path, file_stamp(page_dir / path))
        for directory in ("widgets", "page/widgets")
        for path in widget_paths(page_dir, directory)
    )
    return _read_page_registry_stamped(
        page_dir,
        file_stamp(page_dir / "registry.json"),
        file_stamp(page_dir / "page" / "registry.json"),
        widgets,
        latest_revision(page_dir),
    )


@lru_cache(maxsize=128)
def _read_page_registry_stamped(
    page_dir: Path,
    layer_stamp: tuple | None,
    declaration_stamp: tuple | None,
    widgets: tuple[tuple[str, tuple], ...],
    active: int | None,
):
    """Compose one candidate vocabulary until any input file or the active revision
    changes."""
    from leaf.revision_artifact import read_artifact

    layer = load_registry(page_dir)
    if layer is None:
        return None
    return compose_candidate(
        page_dir,
        layer,
        [path for path, _stamp in widgets],
        validated=read_artifact(page_dir, active).registry if active else None,
    )


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

    A page that declares nothing composes the layer alone, so a fault in it is the
    vendored layer's, which a re-vendor repairs."""
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
        if declarations:
            raise
        raise _revendor(page_dir, error) from None


def _revendor(page_dir: Path, error: RegistryError) -> RegistryError:
    """A fault in the vendored layer, which `page init` wrote and re-vendoring fixes."""
    return RegistryError(f"{error}; run `leaf page init {page_dir}` to re-vendor it")


def _layer_packages(layer: dict, path: Path) -> list[str]:
    packages = layer.get("packages", [])
    if (
        not isinstance(packages, list)
        or not all(isinstance(value, str) and value for value in packages)
        or len(set(packages)) != len(packages)
    ):
        raise RegistryError(
            f"{path}: $layer.packages must be a unique list of non-empty strings"
        )
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
    """The identity recorded by this page's complete vendored layer."""
    path = page_dir / "registry.json"
    registry = read_registry_declarations(path)
    layer = (registry or {}).get("$layer", {})
    generation = layer.get("generation")
    if not isinstance(generation, str) or not generation:
        raise RegistryError(
            f"{path}: vendored registry lacks $layer.generation; run `leaf page init`"
        )
    packages = _layer_packages(layer, path)
    fingerprint = layer.get("fingerprint")
    if not (
        isinstance(fingerprint, str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint)
    ):
        raise RegistryError(f"{path}: $layer.fingerprint must be a SHA-256 identity")
    # A page vendored before this identity existed reads as having none, which is what
    # the browser gates refuse on: nothing here can say which runtime it carries.
    runtime = layer.get("runtime")
    if runtime is not None and not (
        isinstance(runtime, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", runtime)
    ):
        raise RegistryError(f"{path}: $layer.runtime must be a SHA-256 identity")
    producer = layer.get("producer")
    if producer is not None and not isinstance(producer, dict):
        raise RegistryError(f"{path}: $layer.producer must be an object")
    if producer is not None:
        commit = producer.get("commit")
        dirty = producer.get("dirty")
        if commit is not None and not (
            isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{7,40}", commit)
        ):
            raise RegistryError(
                f"{path}: $layer.producer.commit must be a Git object name"
            )
        if dirty is not None and not isinstance(dirty, bool):
            raise RegistryError(f"{path}: $layer.producer.dirty must be true or false")
        dates = {
            kind: producer[kind]
            for kind in ("committed", "installed")
            if producer.get(kind) is not None
        }
        # An offset is required: without one, each viewer's browser reads the time
        # in its own zone, and one page shows different ages.
        for kind, value in dates.items():
            try:
                offset = datetime.fromisoformat(value).utcoffset()
            except (TypeError, ValueError):
                offset = None
            if offset is None:
                raise RegistryError(
                    f"{path}: $layer.producer.{kind} must be an ISO 8601 date "
                    "with a timezone offset"
                )
        producer = {
            **({"commit": commit} if commit is not None else {}),
            **({"dirty": dirty} if dirty is not None else {}),
            **dates,
        }
    return {
        "generation": generation,
        "fingerprint": fingerprint,
        **({"runtime": runtime} if runtime else {}),
        "packages": packages,
        **({"producer": producer} if producer else {}),
    }


def layer_generation(page_dir: Path) -> str:
    """The epoch shared by this page's vendored runtime and server contract."""
    return layer_metadata(page_dir)["generation"]


def require_registry(page_dir: Path) -> dict:
    """The active revision's vocabulary, or the candidate before first activation."""
    registry = active_registry(page_dir)
    if registry is None:
        sys.exit(f"no registry.json in {page_dir}; run `leaf page init` first")
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
        from leaf.revision_artifact import read_registry

        return read_registry(page_dir, revision)
    candidate = read_page_registry(page_dir)
    return candidate.registry if candidate is not None else None
