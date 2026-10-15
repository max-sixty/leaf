"""Read and prepare one complete authored page fixture.

The source owns its package selection, versions, history, data and media addresses.
A product document's markup is read with the parts other sources own composed into it
(`leaf_dev.docs`). Preparation supplies local companion media and resolves any
remaining addresses from the checkout's pinned asset tree, or a build's explicit draft
tree. Preview, publication and render probes share this boundary rather than adding
content inputs in their callers.
"""

import functools
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from leaf.event_log import read_events
from leaf.interaction_log import append_interactions
from leaf.media import media_name
from leaf.revision_artifact import Resource, capture_artifact, capture_local_resource
from leaf.schema import CURSOR_FILE, MEDIA_DIR, MEDIA_TYPES
from leaf.state import now_iso, write_json
from leaf.structure import SourceDocument

from leaf_dev import ROOT, docs
from leaf_dev.example_data import (
    data_operations,
    example_versions,
    page_files,
    seed_log,
)
from leaf_dev.leaf_assets import assets_lock, pinned_assets, pinned_copy

DEFAULT_PACKAGES = ROOT / "examples" / "layer.json"


@dataclass(frozen=True, slots=True)
class PageFixture:
    source: Path
    page_files: Path | None
    packages: tuple[str, ...]
    media: Path
    data: tuple[dict, ...]
    versions: tuple[Path, ...]
    seed: Path | None


@dataclass(frozen=True, slots=True)
class PreparedPage:
    data_sources: int
    versions: int


def record_run_context(
    page: Path,
    *,
    purpose: Literal["test", "automated", "user-review", "author-preview"],
    run: Path,
    authored_source: Path | None = None,
    test: str | None = None,
) -> None:
    """Record a developer run's declared purpose in the page's diagnostic history.

    Call at the boundary that knows why this page will be used, before its inputs,
    including after a pooled page is copied or a retained preview resumes. Fixture
    preparation alone says nothing about its eventual reader. `run` reuses that
    caller's existing run, isolated state, or preview-slot path; neither this
    declaration nor its absence identifies who makes an individual gesture.
    """
    append_interactions(
        page,
        [
            {
                "source": "developer",
                "type": "run_context",
                "ts": now_iso(),
                "purpose": purpose,
                "run": str(run.resolve()),
                **(
                    {"authored_source": str(authored_source.resolve())}
                    if authored_source is not None
                    else {}
                ),
                **({"test": test} if test is not None else {}),
            }
        ],
    )


def source_manifest_candidates(source: Path) -> list[Path]:
    candidates = [source.parent / "layer.json"]
    # `examples/developer/` pages take the catalog's package selection.
    if source.parent.name == "developer":
        candidates.append(source.parent.parent / "layer.json")
    return candidates


def source_manifest(source: Path) -> Path | None:
    return next(
        (path for path in source_manifest_candidates(source) if path.is_file()), None
    )


def source_packages(source: Path) -> list[str]:
    manifest = source_manifest(source) or DEFAULT_PACKAGES
    return json.loads(manifest.read_text(encoding="utf-8"))


def layer_media(manifest: Path) -> Path | None:
    """The media a layer's pages share: `media/` beside its manifest in the tree, or
    else at that path in the checkout's pinned assets, where the example catalog's
    live (`leaf_dev.leaf_assets`)."""
    media = manifest.parent / "media"
    return media if media.is_dir() else pinned_copy(media)


@functools.cache
def example_media() -> Path:
    """The media the example catalog's pages share, content-addressed as
    `leaf page media` names them (examples/AGENTS.md, "Media")."""
    return layer_media(DEFAULT_PACKAGES)


def media_source(source: Path) -> Path:
    """A page's own `media/`, else its layer's. A page in this checkout with no layer
    of its own, such as a test fixture, shares the example catalog's media, as it
    shares its packages; a page outside the checkout keeps only its own."""
    media = source.parent / "media"
    manifest = source_manifest(source)
    if manifest is None and source.resolve().is_relative_to(ROOT):
        manifest = DEFAULT_PACKAGES
    if media.is_dir() or manifest is None:
        return media
    return layer_media(manifest) or media


def authored_markup(path: Path, assets: Path | None = None) -> str:
    """The markup a builder installs for one authored version: the file as written, and
    for a product document, with what other sources own composed into it."""
    markup = path.read_text(encoding="utf-8")
    if path.parent != docs.DOCS:
        return markup
    return docs.compose(path, markup, assets=assets)


def composition_inputs(path: Path) -> list[Path]:
    """The files besides `path` and the asset pin that `authored_markup` reads."""
    return docs.inputs(path) if path.parent == docs.DOCS else []


def read_fixture(
    source: Path, *, runtime: Path = ROOT, env: dict[str, str] | None = None
) -> PageFixture:
    """Read authored companions using the runtime that will consume produced data.

    Source and runtime are independent: a paired preview can share one authored input
    while each arm supplies its own package producer and matching data contract.
    """
    seed = seed_log(source)
    files = page_files(source)
    return PageFixture(
        source=source,
        page_files=files if files.is_dir() else None,
        packages=tuple(source_packages(source)),
        media=media_source(source),
        data=tuple(data_operations(source, runtime=runtime, env=env)),
        versions=tuple(example_versions(source)),
        seed=seed if seed.is_file() else None,
    )


def package_selection_args(packages) -> list[str]:
    """Render one package selection, including the explicit empty layer."""
    return [arg for package in packages for arg in ("--package", package)] or [
        "--no-packages"
    ]


class LeafRunner(Protocol):
    """Runs one leaf command to completion and fails if it does. Preparation reads
    nothing it returns; each caller's runner keeps its own environment, working
    directory and failure report."""

    def __call__(self, *args: str, input_text: str | None = None) -> object: ...


def import_referenced_media(
    page: Path,
    documents: list[str],
    run_leaf: LeafRunner,
    *,
    source: Path,
    assets: Path | None = None,
) -> None:
    """Materialize authored media addresses from the source checkout's asset tree.

    Revision capture discovers the inputs, including CSS and live samples; asset
    filenames do not select page content. Local
    media already copied into the page wins. A build may supply unpublished assets
    explicitly, so draft markup is validated against its own bytes rather than the
    ordinary pin. Unresolved references keep capture's ordinary refusal.
    """
    lock = assets_lock(source)
    if assets is None and lock is None:
        return

    @functools.cache
    def selected_media() -> dict[str, Path]:
        """Index the selected asset tree only when a missing reference needs it."""
        directory = assets if assets is not None else pinned_assets(lock.parent)
        return {
            media_name(candidate.read_bytes(), candidate.suffix): candidate
            for candidate in sorted(directory.rglob("*"))
            if candidate.is_file() and candidate.suffix.lower() in MEDIA_TYPES
        }

    def read_resource(path: str) -> Resource:
        if (
            path.startswith(f"/{MEDIA_DIR}/")
            and not (page / path.removeprefix("/")).is_file()
            and (candidate := selected_media().get(path.removeprefix(f"/{MEDIA_DIR}/")))
        ):
            run_leaf("page", "media", str(page), str(candidate))
        return capture_local_resource(page, path)

    registry = json.loads((page / "registry.json").read_text(encoding="utf-8"))
    for document in documents:
        capture_artifact(
            page, SourceDocument(document), registry, read_resource=read_resource
        )


def _seed_data(fixture: PageFixture, page: Path, run_leaf: LeafRunner) -> None:
    for operation in fixture.data:
        run_leaf(
            "data",
            "set",
            str(page),
            operation["source"],
            input_text=json.dumps(operation["value"]),
        )


def _seed_log(fixture: PageFixture, page: Path) -> None:
    if fixture.seed is None:
        return
    with (page / "events.jsonl").open("a", encoding="utf-8") as log:
        log.write(fixture.seed.read_text(encoding="utf-8"))


def _acknowledge_seed(fixture: PageFixture, page: Path) -> None:
    if fixture.seed is None:
        return
    events = read_events(page)
    write_json(page / CURSOR_FILE, {"seq": events[-1]["seq"] if events else 0})


def prepare_page(
    page: Path,
    fixture: PageFixture,
    run_leaf: LeafRunner,
    *,
    initialize: bool = True,
    seed_log: bool = True,
    final_status: str | None = "waiting",
    current_note: str = "Draft as authored",
    earlier_note: str = "Earlier draft",
    each_version: Callable[[Path], None] | None = None,
    assets: Path | None = None,
) -> PreparedPage:
    """Build one page directory from an authored fixture.

    `leaf-dev preview`, `leaf-dev site`, and the render harness's `serve` all build through
    here. The current source is written before the data operations, because
    `leaf data set` validates a source against the page's markup and the current
    version is the one that has to bind it. Versions are then stamped oldest first,
    and the seed log goes in after the first stamp and before any later one, so a
    revised example reads in the order it happened: a version, what the user said
    about it, then the version that answered. The cursor ends past the seed, since a
    seed is history: a cursor at zero would hand the next agent session questions
    the log already answers.

    `each_version` is called with each version's source once it is stamped, and once
    the seed is in the log after the first, so it reads the page as a builder
    leaves it at that version.
    """
    selection = package_selection_args(fixture.packages)
    if initialize:
        run_leaf("page", "init", *selection, str(page))
    if fixture.page_files is not None:
        shutil.copytree(fixture.page_files, page / "page", dirs_exist_ok=True)
    markup = {version: authored_markup(version, assets) for version in fixture.versions}
    (page / "index.html").write_text(markup[fixture.source], encoding="utf-8")
    if fixture.media.is_dir():
        shutil.copytree(fixture.media, page / "media", dirs_exist_ok=True)
    import_referenced_media(
        page,
        list(markup.values()),
        run_leaf,
        source=fixture.source,
        assets=assets,
    )
    _seed_data(fixture, page, run_leaf)
    for order, version in enumerate(fixture.versions):
        (page / "index.html").write_text(markup[version], encoding="utf-8")
        run_leaf(
            "page",
            "stamp",
            str(page),
            "--text",
            current_note if order == len(fixture.versions) - 1 else earlier_note,
        )
        if order == 0 and seed_log:
            _seed_log(fixture, page)
        if each_version is not None:
            each_version(version)
    if seed_log:
        _acknowledge_seed(fixture, page)
    if final_status is not None:
        run_leaf("status", str(page), final_status)
    return PreparedPage(
        data_sources=len({operation["source"] for operation in fixture.data}),
        versions=len(fixture.versions),
    )
