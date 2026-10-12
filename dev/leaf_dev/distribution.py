"""Prepare the website's plugin installation, with a compiled browser kernel.

Consumer installs follow `main` and serve the runtime's source modules; the source
tree contains no generated kernel bundles. The website build prepares this tree
beside the site: its page directories are vendored from it and its container image
installs it (`leaf_dev.site`), so a visitor loads the compiled kernel. Nothing
compiles during installation, page init, export, or custom-package authoring.
Package widgets remain native ESM and import the same widget-api entry as the
compiled kernel, so their state has one owner. How consumer installs could carry the
compiled kernel too is open in `TODO.md`.

The developer arm's payload layout preserves uv's workspace and each harness's
local marketplace layout. Only browser runtime JavaScript is replaced; source
paths retained in the distribution manifest enforce the private kernel boundary.
The Pi manifest excludes maintainer dependencies and compiler commands.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import click
from leaf.layer import (
    compose_layer,
    kernel_runtime_paths,
    layer_inputs,
    payload_provenance,
)
from leaf.schema import PLUGIN_ROOT

from leaf_dev.arms import extract_payload


def prepare(output: Path) -> None:
    """Build a new installation tree from this checkout's tracked working files."""
    if output.exists():
        raise click.ClickException(f"installation destination already exists: {output}")
    extract_payload(output)

    composition = compose_layer(layer_inputs())
    with tempfile.TemporaryDirectory(prefix="leaf-distribution-") as directory:
        layer = Path(directory)
        (layer / "leaf.js").write_bytes(composition.top_files["leaf.js"])
        for sub in ("runtime", "widgets", "vendor"):
            for name, data in composition.directory_files[sub].items():
                target = layer / sub / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        assets = output / "skills/leaf/assets"
        default_runtime = output / "skills/leaf/packages/default/runtime"
        for runtime in (assets / "runtime", default_runtime):
            for source in runtime.rglob("*.js"):
                source.unlink()
        subprocess.run(
            [
                "node",
                str(PLUGIN_ROOT / "build/runtime-bundle.mjs"),
                str(layer),
                str(assets),
            ],
            cwd=PLUGIN_ROOT,
            check=True,
        )

    package = json.loads((output / "package.json").read_text())
    (output / "package.json").write_text(
        json.dumps(
            {key: package[key] for key in ("name", "private", "type", "pi")}, indent=2
        )
        + "\n"
    )
    (output / "leaf-distribution.json").write_text(
        json.dumps(
            {
                "producer": payload_provenance(),
                "runtime_paths": sorted(kernel_runtime_paths()),
            },
            indent=2,
        )
        + "\n"
    )


@click.command("distribution")
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
