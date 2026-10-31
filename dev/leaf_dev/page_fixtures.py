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
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

import click

from leaf.event_log import read_events
from leaf.interaction_log import append_interactions
from leaf.media import media_name
from leaf.revision_artifact import Resource, capture_artifact, capture_local_resource
from leaf.schema import MEDIA_DIR, MEDIA_TYPES
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
    runtime: Path
    env: dict[str, str] | None


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
    media = layer_media(DEFAULT_PACKAGES)
    assert media is not None
    return media


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


def composition_inputs(path: Path) -> tuple[list[Path], list[Path]]:
    """Composition inputs besides `path` and the asset pin, including discovery trees."""
    from leaf_dev.commands import corpus

    if root := corpus.source_root(path):
        return corpus.composition_inputs(root)
    return (docs.inputs(path) if path.parent == docs.DOCS else []), []


def refresh_composition(source: Path) -> None:
    """Materialize a generated fixture before reading its markup and companions."""
    from leaf_dev.commands import corpus

    if root := corpus.source_root(source):
        corpus.generate(root)


def read_fixture(
    source: Path, *, runtime: Path = ROOT, env: dict[str, str] | None = None
) -> PageFixture:
    """Read authored companions using the runtime that will consume produced data.

    Source and runtime are independent: a paired preview can share one authored input
    while each arm supplies its own package producer and matching data contract, and
    admits and acknowledges the seed with its own Leaf (`admit_events`).
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
        runtime=runtime,
        env=env,
    )


@functools.cache
def _configuration_home() -> tempfile.TemporaryDirectory:
    """Keep one empty configuration directory alive for this builder process."""
    return tempfile.TemporaryDirectory(prefix="leaf-fixture-config-")


def fixture_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    """Build authored fixtures without the developer's personal configuration.

    Each CLI runner applies this at its subprocess boundary, including site templates
    and preview refreshes outside prepare_page. Keep identities and state selected by
    the runner; only configuration is empty. This also works with older comparison
    arms, whose CLI need not know any current theme-selection options.
    """
    return {
        **(os.environ if base is None else base),
        "XDG_CONFIG_HOME": _configuration_home().name,
    }


def package_selection_args(packages) -> list[str]:
    """The source's explicit content packages, including an empty selection."""
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
        if assets is not None:
            directory = assets
        else:
            assert lock is not None
            directory = pinned_assets(lock.parent)
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

    from leaf.registry.storage import layer_record, layer_vocabulary

    # The arm preparing the page may speak another protocol, which this Leaf would
    # refuse to serve; finding the media its documents name needs only a vocabulary.
    # A base arm from before pages composed their layer at read time vendored it.
    record = layer_record(page)
    registry = (
        layer_vocabulary(record, page)
        if record
        else json.loads((page / "registry.json").read_text(encoding="utf-8"))
    )
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


def refresh_captures(fixture: PageFixture, page: Path, run_leaf: LeafRunner) -> None:
    """Publish changed authored captures without replaying the page's seed data.

    `$captures` names the fixture files that remain authoritative. Literal
    companion values are initial state, so a resumed or live preview preserves
    what the page now holds there. Unchanged captures retain their run receipts;
    sources no longer captured remain available to historical revisions.
    """
    from leaf.data import read_data
    from leaf.data_contracts import working_data_bindings
    from leaf.registry.storage import load_registry

    registry = load_registry(page)
    current = read_data(page, registry)["sources"]
    bindings, _ = working_data_bindings(page, registry, read_events(page))
    for operation in fixture.data:
        if operation["kind"] != "capture":
            continue
        held = current.get(operation["source"])
        if (
            held is None
            or "value" not in held
            or json.dumps(held["value"], sort_keys=True)
            != json.dumps(operation["value"], sort_keys=True)
            or held["contract"] != bindings.get(operation["source"])
        ):
            run_leaf(
                "data",
                "set",
                str(page),
                operation["source"],
                input_text=json.dumps(operation["value"]),
            )


def read_event_lines(path: Path) -> list[dict]:
    """The events a log file holds, one JSON object per line, as each writer would
    hand it over. The log's grammar joins events with "\n", never `splitlines()`,
    whose wider class breaks a U+2028 inside a message."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").split("\n")
        if line.strip()
    ]


# Run by the page's own runtime, so its admission admits each event and writes the
# receipt: another Leaf refuses a page at a different protocol, and would
# write the events in its own shape rather than the page's. Each event goes through
# the door every writer uses, so the log holds what a real page's would: admission
# refuses an event no writer could send and writes the fields it derives, such as an
# action's meaning. With `stamped`, an event waits for the stamp of the revision it
# names, as its writer did; otherwise the door refuses one naming a revision the page
# lacks. With `acknowledge`, a receipt acknowledges every event in the log. It prints
# how many events it admitted.
ADMIT = """
import json
import sys
from pathlib import Path
from leaf.delivery import record_receipt
from leaf.event_contracts import append_admitted
from leaf.event_log import EventRefused
from leaf.files import list_revisions
from leaf.service import PageTransaction

page = Path(sys.argv[1])
stamped, acknowledge = (flag == "1" for flag in sys.argv[2:])
newest = list_revisions(page)[-1]
admitted = 0
with PageTransaction(page) as transaction:
    for event in json.load(sys.stdin):
        if stamped and event.get("revision", newest) > newest:
            break
        try:
            append_admitted(transaction, event)
        except EventRefused as error:
            sys.exit(f"event {event.get('id')!r} refused: {error}")
        admitted += 1
    if acknowledge and transaction.events:
        record_receipt(transaction, transaction.events[-1]["seq"])
print(admitted)
"""


def admit_events(
    runtime: Path,
    page: Path,
    events: list[dict],
    *,
    log: Path,
    env: dict[str, str] | None,
    stamped: bool = False,
    acknowledge: bool = False,
) -> int:
    """Append the leading `events` to `page` through `runtime`'s own door
    (`ADMIT`) and return how many it admitted: all of them unless `stamped` holds
    back those naming a revision not yet stamped. A refusal fails with the
    admission's message, naming `log`, the file the events came from."""
    result = subprocess.run(
        [
            *("uv", "run", "-q", "--no-dev", "--project", str(runtime)),
            *("python", "-I", "-c", ADMIT, str(page)),
            *("1" if flag else "0" for flag in (stamped, acknowledge)),
        ],
        input=json.dumps(events),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode:
        raise click.ClickException(f"admitting {log}: {result.stderr.strip()}")
    return int(result.stdout)


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
    and each seed event is admitted once the revision it names is stamped, so a
    revised example reads in the order it happened: a version, what the user said
    about it, then the version that answered and the reply that says so. A receipt
    acknowledges the seed, since a seed is history: an unacknowledged one would hand
    the next agent session questions the log already answers.

    `each_version` is called with each version's source once it is stamped and the
    seed events it holds are in the log, so it reads the page as a builder leaves it
    at that version.
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
    seed = seed_log and fixture.seed is not None
    pending = read_event_lines(fixture.seed) if seed else []
    for order, version in enumerate(fixture.versions):
        last = order == len(fixture.versions) - 1
        (page / "index.html").write_text(markup[version], encoding="utf-8")
        run_leaf(
            "page", "stamp", str(page), "--text", current_note if last else earlier_note
        )
        if seed and (pending or last):
            admitted = admit_events(
                fixture.runtime,
                page,
                pending,
                log=fixture.seed,
                env=fixture.env,
                stamped=not last,
                acknowledge=last,
            )
            del pending[:admitted]
        if each_version is not None:
            each_version(version)
    if final_status is not None:
        run_leaf("page", "close" if final_status == "idle" else "open", str(page))
    return PreparedPage(
        data_sources=len({operation["source"] for operation in fixture.data}),
        versions=len(fixture.versions),
    )
