"""Read and prepare one complete authored page fixture."""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from example_data import data_operations, example_versions

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACKAGES = ROOT / "examples" / "layer.json"


@dataclass(frozen=True, slots=True)
class PageFixture:
    source: Path
    packages: tuple[str, ...]
    media: Path
    data: tuple[dict, ...]
    versions: tuple[Path, ...]
    seed: Path | None


@dataclass(frozen=True, slots=True)
class PreparedPage:
    data_sources: int
    versions: int


def source_manifest_candidates(source: Path) -> list[Path]:
    candidates = [source.parent / "layer.json"]
    examples = source.parent.parent
    checkout = examples.parent
    if (
        source.parent.name == "developer"
        and examples.name == "examples"
        and (checkout / "bin" / "leaf").is_file()
    ):
        candidates.append(examples / "layer.json")
    return candidates


def source_manifest(source: Path) -> Path | None:
    return next(
        (path for path in source_manifest_candidates(source) if path.is_file()), None
    )


def source_packages(source: Path) -> list[str]:
    manifest = source_manifest(source) or DEFAULT_PACKAGES
    return json.loads(manifest.read_text(encoding="utf-8"))


def media_source(source: Path) -> Path:
    media = source.parent / "media"
    manifest = source_manifest(source)
    if not media.is_dir() and manifest is not None:
        layer_media = manifest.parent / "media"
        if layer_media.is_dir():
            return layer_media
    return media


def read_fixture(source: Path) -> PageFixture:
    seed = source.with_suffix(".jsonl")
    return PageFixture(
        source=source,
        packages=tuple(source_packages(source)),
        media=media_source(source),
        data=tuple(data_operations(source)),
        versions=tuple(example_versions(source)),
        seed=seed if seed.is_file() else None,
    )


def package_selection_args(packages) -> list[str]:
    """Render one package selection, including the explicit empty layer."""
    return [arg for package in packages for arg in ("--package", package)] or [
        "--no-packages"
    ]


def _seed_data(fixture: PageFixture, page: Path, run_leaf: Callable) -> None:
    for operation in fixture.data:
        if operation["kind"] == "set":
            args = ["data", "set", str(page), operation["source"]]
            if operation["capture_label"] is not None:
                args.extend(("--capture-label", operation["capture_label"]))
            run_leaf(*args, input_text=json.dumps(operation["value"]))
            continue
        args = [
            "data",
            "capture",
            str(page),
            operation["source"],
            "--file",
            str(operation["input_file"]),
            "--format",
            operation["format"],
        ]
        if operation["label"] is not None:
            args.extend(("--label", operation["label"]))
        if operation["lines"] is not None:
            args.extend(("--lines", operation["lines"]))
        run_leaf(*args)


def _seed_log(fixture: PageFixture, page: Path) -> None:
    if fixture.seed is None:
        return
    with (page / "events.jsonl").open("a", encoding="utf-8") as log:
        log.write(fixture.seed.read_text(encoding="utf-8"))


def _acknowledge_seed(fixture: PageFixture, page: Path) -> None:
    if fixture.seed is None:
        return
    lines = [
        line
        for line in (page / "events.jsonl").read_text(encoding="utf-8").split("\n")
        if line.strip()
    ]
    (page / "cursor.json").write_text(
        json.dumps({"seq": len(lines)}) + "\n", encoding="utf-8"
    )


def prepare_page(
    page: Path,
    fixture: PageFixture,
    run_leaf: Callable,
    *,
    initialize: bool = True,
    seed_log: bool = True,
    final_status: str | None = "waiting",
    current_note: str = "Draft as authored",
    earlier_note: str = "Earlier draft",
) -> PreparedPage:
    selection = package_selection_args(fixture.packages)
    if initialize:
        run_leaf("page", "init", *selection, str(page))
    (page / "index.html").write_text(
        fixture.source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    if fixture.media.is_dir():
        shutil.copytree(fixture.media, page / "media", dirs_exist_ok=True)
    _seed_data(fixture, page, run_leaf)
    for order, version in enumerate(fixture.versions):
        (page / "index.html").write_text(
            version.read_text(encoding="utf-8"), encoding="utf-8"
        )
        run_leaf(
            "version",
            "stamp",
            str(page),
            "--text",
            current_note if order == len(fixture.versions) - 1 else earlier_note,
        )
        if order == 0 and seed_log:
            _seed_log(fixture, page)
    if seed_log:
        _acknowledge_seed(fixture, page)
    if final_status is not None:
        run_leaf("status", str(page), final_status)
    return PreparedPage(
        data_sources=len({operation["source"] for operation in fixture.data}),
        versions=len(fixture.versions),
    )
