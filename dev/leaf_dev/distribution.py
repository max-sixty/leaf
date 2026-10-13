"""Prepare and reuse installations with the compiled browser kernel.

Consumer installs follow `main` and serve the runtime's source modules; the source
tree contains no generated kernel bundles. The website, suite, and developer previews
prepare an installation before vendoring pages. The website's container installs
that same payload (`leaf_dev.site`). Nothing
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
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import click
from leaf.layer import (
    compose_layer,
    files_identity,
    kernel_runtime_paths,
    layer_inputs,
    payload_provenance,
)
from leaf.state import flocked, write_json

from leaf_dev import ROOT
from leaf_dev.arms import PAYLOAD, extract_payload

COMPILER_INPUTS = (
    "build/runtime-bundle.mjs",
    "build/browser/build.mjs",
    "package.json",
    "pnpm-lock.yaml",
    "dev/leaf_dev/distribution.py",
    "dev/leaf_dev/arms.py",
)


def prepare(output: Path) -> None:
    """Build a new installation tree from this checkout's tracked working files."""
    if output.exists():
        raise click.ClickException(f"installation destination already exists: {output}")
    extract_payload(output)
    compile_installation(output)


def compile_installation(output: Path) -> None:
    """Compile this interpreter's Leaf into an already extracted payload.

    A comparison arm runs this helper in its own environment, so its own composer
    supplies the graph and contracts; the developer checkout supplies the compiler.
    Native package modules retain their public widget-api import and share the
    kernel's instance. The completed payload needs neither Node nor developer tools.
    """

    composition = compose_layer(layer_inputs())
    runtime_paths = sorted(kernel_runtime_paths())
    producer = payload_provenance()
    with tempfile.TemporaryDirectory(prefix="leaf-distribution-") as directory:
        layer = Path(directory)
        (layer / "leaf.js").write_bytes(composition.top_files["leaf.js"])
        for sub in ("runtime", "widgets", "vendor"):
            for name, data in composition.directory_files[sub].items():
                target = layer / sub / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        assets = output / "skills/leaf/assets"
        for source in (assets / "runtime").rglob("*.js"):
            source.unlink()
        subprocess.run(
            [
                "node",
                str(ROOT / "build/runtime-bundle.mjs"),
                str(layer),
                str(assets),
            ],
            cwd=ROOT,
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
                "producer": producer,
                "runtime_paths": runtime_paths,
            },
            indent=2,
        )
        + "\n"
    )


def installation_inputs(runtime: Path = ROOT) -> dict[str, Path]:
    """Logical payload and compiler inputs a prepared installation depends on.

    Git supplies the install's file set, including unignored new files. Extracted
    comparison arms have no Git metadata and already contain exactly their payload.
    """
    if (runtime / ".git").exists():
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(runtime),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                *PAYLOAD,
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split("\0")
        payload = [runtime / name for name in set(filter(None, listed))]
    else:
        payload = [
            path
            for name in PAYLOAD
            for path in (
                (runtime / name).rglob("*")
                if (runtime / name).is_dir()
                else (runtime / name,)
            )
            if "__pycache__" not in path.parts and path.suffix != ".pyc"
        ]
    inputs = {
        **{f"payload/{path.relative_to(runtime).as_posix()}": path for path in payload},
        **{f"compiler/{name}": ROOT / name for name in COMPILER_INPUTS},
    }
    return {name: path for name, path in sorted(inputs.items()) if path.is_file()}


def installation_identity(runtime: Path = ROOT) -> str:
    """Content identity, independent of mtimes, Git labels, and authored revisions."""
    return files_identity(
        {name: path.read_bytes() for name, path in installation_inputs(runtime).items()}
    ).removeprefix("sha256:")


def cached_installation(runtime: Path = ROOT) -> Path:
    """Share one complete compiled payload per relevant working-tree revision.

    Suite workers and preview slots serialize preparation, then use an immutable
    installation. Authored-page edits and Git-label changes reuse its compiled
    bytes while publishing accurate producer metadata. A payload or compiler edit
    builds a new kernel; no page ever receives private source
    modules alongside the kernel. Recheck after lock acquisition and before
    returning or publishing: an edit that overtakes this attempt retries selection
    without needing another watcher event. A failed build publishes no cache entry.
    """
    runtime = runtime.resolve()
    if (runtime / "leaf-distribution.json").is_file():
        return runtime
    cache = ROOT / ".tmp/compiled-runtime"
    cache.mkdir(parents=True, exist_ok=True)

    def revision_is_current(identity: str, producer: dict) -> bool:
        return (
            payload_provenance(root=runtime) == producer
            and installation_identity(runtime) == identity
        )

    while True:
        identity = installation_identity(runtime)
        content = cache / f"content-{identity}"
        with flocked(cache / f"{identity}.lock"):
            if installation_identity(runtime) != identity:
                continue
            if not content.is_dir():
                with tempfile.TemporaryDirectory(
                    prefix=".preparing-", dir=cache
                ) as raw:
                    staged = Path(raw) / "installation"
                    if runtime == ROOT:
                        prepare(staged)
                    else:
                        staged.mkdir()
                        for name in PAYLOAD:
                            source, target = runtime / name, staged / name
                            if source.is_dir():
                                shutil.copytree(
                                    source,
                                    target,
                                    ignore=shutil.ignore_patterns(
                                        "__pycache__", "*.pyc"
                                    ),
                                )
                            elif source.is_file():
                                target.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(source, target)
                        subprocess.run(
                            [
                                "uv",
                                "run",
                                "-q",
                                "--no-dev",
                                "--project",
                                str(runtime),
                                "--with-editable",
                                str(ROOT / "dev"),
                                "python",
                                "-c",
                                (
                                    "import sys; from pathlib import Path; "
                                    "from leaf_dev.distribution import compile_installation; "
                                    "compile_installation(Path(sys.argv[1]))"
                                ),
                                str(staged),
                            ],
                            cwd=runtime,
                            check=True,
                        )
                    if installation_identity(runtime) != identity:
                        continue
                    staged.rename(content)
            producer = payload_provenance(root=runtime)

            publication = files_identity(
                {
                    "content": identity.encode(),
                    "producer": json.dumps(producer, sort_keys=True).encode(),
                }
            ).removeprefix("sha256:")
            output = cache / publication
            if output.is_dir():
                if revision_is_current(identity, producer):
                    return output
                continue
            with tempfile.TemporaryDirectory(prefix=".publishing-", dir=cache) as raw:
                staged = Path(raw) / "installation"
                # Prepared bytes are immutable. Hard links reuse the compiled kernel;
                # atomic JSON replacement gives this snapshot its own producer record.
                shutil.copytree(content, staged, copy_function=os.link)
                manifest = staged / "leaf-distribution.json"
                record = json.loads(manifest.read_text())
                record["producer"] = producer
                write_json(manifest, record)
                if not revision_is_current(identity, producer):
                    continue
                staged.rename(output)
            return output


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
