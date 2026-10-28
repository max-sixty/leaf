"""Make a tree's committed kernel current, and prepare installation trees.

An install is the tracked tree. It serves the kernel committed under
`dist/kernel/` wherever that was compiled from the tree's own modules, and the
source modules otherwise (`leaf.runtime_selection.read_runtime`). A developer
checkout's kernel is stale whenever its runtime has been edited and not rebuilt, so the
suite's browser tiers, developer previews and probes compile it in place first
(`current_kernel`), with the same build (`build/runtime-bundle.mjs`) that
`pnpm run build:browser` commits, so each serves the kernel an install of that tree
will serve once the change is committed. The rebuild is one the change must commit
anyway (`build/AGENTS.md`). A tree whose kernel is current, as every commit on `main`
is, compiles nothing, so a base arm or a clean checkout is served as it stands.
Freshness follows the runtime modules alone: an edit to the bundler itself takes
`pnpm run build:browser`.

The website's container installs a prepared payload (`prepare`,
`leaf_dev.commands.site`). Nothing compiles during installation, page init, export, or
custom-package authoring. Package widgets remain native ESM and import the same
widget-api entry as the compiled kernel, so their state has one owner.

The payload layout preserves uv's workspace and each harness's local marketplace
layout. A prepared tree has no Git metadata, so `leaf-distribution.json` records the
producer its provenance names (`leaf.layer.payload_provenance`).
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import click

from leaf.layer import payload_provenance
from leaf.state import flocked, write_json
from leaf_dev import ROOT
from leaf_dev.arms import PAYLOAD, extract_payload


def compiler_root() -> Path:
    """The developer checkout that launched a selected-runtime preview."""
    return Path(os.environ.get("LEAF_PREVIEW_COMPILER_ROOT", ROOT)).resolve()


def bundle_runtime(assets: Path, kernel: Path) -> None:
    """Compile the browser runtime with the developer checkout's bundler."""
    compiler = compiler_root()
    if not (compiler / "node_modules").is_dir():
        # A fresh worktree's background setup may not have started or finished.
        # Setup installs browsers too, so run it by hand rather than from here.
        raise click.ClickException(
            f"{compiler} has no node_modules, which the runtime bundle needs; "
            "run `uv run --frozen leaf-dev setup` (it waits for any install in progress)"
        )
    subprocess.run(
        ["node", str(compiler / "build/runtime-bundle.mjs"), str(assets), str(kernel)],
        cwd=compiler,
        check=True,
    )


def kernel_reading(tree: Path) -> tuple[Path, Path, bool]:
    """`tree`'s resource and kernel directories, relative to it, and whether its
    kernel is current.

    The tree's own environment answers through its own `read_runtime`, since a
    comparison arm can arrange its payload differently from this checkout.
    """
    reading = subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            "--no-dev",
            "--project",
            str(tree),
            "python",
            "-c",
            (
                "import json; from leaf.schema import ASSETS, KERNEL, PLUGIN_ROOT; "
                "from leaf.runtime_selection import read_runtime; "
                "print(json.dumps([*(str(p.relative_to(PLUGIN_ROOT)) for p in "
                "(ASSETS, KERNEL)), read_runtime().kernel is not None]))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assets, kernel, current = json.loads(reading.stdout)
    return Path(assets), Path(kernel), current


def compile_kernel(assets: Path, kernel: Path) -> None:
    """Replace `kernel` with a fresh compile of `assets`, for readers that take no lock.

    The compile reads a snapshot of `assets`, so the input hashes `kernel.json`
    records are those of the bytes compiled, even when an edit lands meanwhile; that
    edit leaves the kernel stale for the next call. `kernel.json` is replaced last:
    a reader that starts after the edit that made the kernel stale finds the earlier
    record stale and opens no kernel file, or finds the new one with every file in
    place. A read already under way when that edit lands can mix the two, as any
    read of a tree being edited can; the next server start reads it whole.
    """
    with tempfile.TemporaryDirectory(prefix=".kernel-", dir=kernel.parent) as raw:
        snapshot, staged = Path(raw) / "assets", Path(raw) / "kernel"
        shutil.copytree(assets, snapshot)
        bundle_runtime(snapshot, staged)
        built = {
            path.relative_to(staged) for path in staged.rglob("*") if path.is_file()
        }
        record = Path("kernel.json")
        for name in sorted(built - {record}):
            (kernel / name).parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged / name, kernel / name)
        if kernel.is_dir():
            for path in sorted(kernel.rglob("*"), reverse=True):
                if path.is_file() and path.relative_to(kernel) not in built:
                    path.unlink()
                elif path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
        os.replace(staged / record, kernel / record)


def current_kernel(tree: Path = ROOT) -> Path:
    """Compile `tree`'s kernel in place where it is stale for its modules, and
    return `tree`. The lock serializes the suite's workers and concurrent previews."""
    tree = tree.resolve()
    (tree / ".tmp").mkdir(exist_ok=True)
    with flocked(tree / ".tmp/kernel.lock"):
        assets, kernel, current = kernel_reading(tree)
        if not current:
            compile_kernel(tree / assets, tree / kernel)
    return tree


def prepare(output: Path, runtime: Path = ROOT) -> None:
    """Build a new installation tree from this checkout or an extracted payload,
    compiling its kernel with this checkout's build where the payload's is stale."""
    if output.exists():
        raise click.ClickException(f"installation destination already exists: {output}")
    if runtime == ROOT and (ROOT / ".git").exists():
        extract_payload(output)
    else:
        output.mkdir(parents=True)
        copy_payload(runtime, output)
    # The payload is the runtime's own, so the runtime's environment reads it and
    # the installation gets no environment of its own.
    assets, kernel, current = kernel_reading(runtime)
    if not current:
        compile_kernel(output / assets, output / kernel)
    write_json(
        output / "leaf-distribution.json",
        {"producer": payload_provenance(root=runtime)},
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
