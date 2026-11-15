"""Prepare installation trees with a compiled kernel.

An install is the tracked tree, which commits no kernel, so it serves the browser
runtime's source modules (`leaf.runtime_selection.read_runtime`), as does every
developer checkout, the suite and the previews. The website's container installs a
prepared payload (`prepare`, `leaf_dev.commands.site.build`) instead: the tree with the
kernel compiled into `dist/kernel/` by `build/runtime-bundle.mjs`, which loads in a
few dozen requests rather than a few hundred. Nothing compiles during installation,
page init, export, or custom-package authoring. Package widgets remain native ESM and
import the same widget-api entry as the compiled kernel, so their state has one owner.

The payload layout preserves uv's workspace and each harness's local marketplace
layout. A prepared tree has no Git metadata, so `leaf-distribution.json` records the
producer its provenance names (`leaf.layer.payload_provenance`).
"""

import shutil
import subprocess
from pathlib import Path

import click

from leaf.layer import payload_provenance
from leaf.schema import ASSETS, KERNEL
from leaf.state import PLUGIN_ROOT, write_json
from leaf_dev import ROOT
from leaf_dev.arms import PAYLOAD, extract_payload


def bundle_runtime(assets: Path, kernel: Path) -> None:
    """Compile the browser runtime with this checkout's bundler."""
    if not (ROOT / "node_modules").is_dir():
        # A fresh worktree's background setup may not have started or finished.
        # Setup installs browsers too, so run it by hand rather than from here.
        raise click.ClickException(
            f"{ROOT} has no node_modules, which the runtime bundle needs; "
            "run `uv run --frozen leaf-dev setup` (it waits for any install in progress)"
        )
    subprocess.run(
        ["node", str(ROOT / "build/runtime-bundle.mjs"), str(assets), str(kernel)],
        cwd=ROOT,
        check=True,
    )


def prepare(output: Path) -> None:
    """Build a new installation tree from this checkout, with its kernel compiled."""
    if output.exists():
        raise click.ClickException(f"installation destination already exists: {output}")
    if (ROOT / ".git").exists():
        extract_payload(output)
    else:
        output.mkdir(parents=True)
        copy_payload(ROOT, output)
    bundle_runtime(
        output / ASSETS.relative_to(PLUGIN_ROOT),
        output / KERNEL.relative_to(PLUGIN_ROOT),
    )
    write_json(
        output / "leaf-distribution.json",
        {"producer": payload_provenance(root=ROOT)},
    )


def copy_payload(runtime: Path, output: Path) -> None:
    """Copy an extracted installation's payload without requiring Git metadata."""
    for name in PAYLOAD:
        source, target = runtime / name, output / name
        if source.is_dir():
            shutil.copytree(
                source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


@click.command()
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="New installation-tree directory; must not already exist.",
)
def distribution(output: Path) -> None:
    """Build a prepared, compiler-free plugin installation tree."""
    prepare(output.resolve())
    click.echo(f"✓ Prepared installation → {output}")
