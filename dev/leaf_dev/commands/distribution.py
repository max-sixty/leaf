"""Prepare and reuse installation trees whose committed kernel is current.

An install is the tracked tree. It serves the kernel committed under
`skills/leaf/kernel/` wherever that was compiled from the tree's own modules, and the
source modules otherwise (`leaf.layer.current_kernel`). A developer checkout's kernel
is stale whenever its runtime has been edited and not rebuilt, so the website, the
suite's browser tiers, and developer previews run a prepared installation instead:
the payload with its kernel compiled again by the same build
(`build/runtime-bundle.mjs`), so each vendors the kernel an install of that tree
will serve once it is rebuilt. The website's container installs that same payload
(`leaf_dev.commands.site`). Nothing compiles during installation, page init, export, or
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
from leaf.layer import files_identity, payload_provenance
from leaf.state import flocked, write_json

from leaf_dev import ROOT
from leaf_dev.arms import PAYLOAD, extract_payload

COMPILER_INPUTS = (
    "build/runtime-bundle.mjs",
    "build/browser/build.mjs",
    "package.json",
    "pnpm-lock.yaml",
    "dev/leaf_dev/commands/distribution.py",
    "dev/leaf_dev/arms.py",
)


def prepare(output: Path, runtime: Path = ROOT) -> None:
    """Build a new installation tree from this checkout or an extracted payload.

    The developer checkout supplies the compiler, so an older comparison arm gets the
    kernel this checkout's build makes of its modules.
    """
    if output.exists():
        raise click.ClickException(f"installation destination already exists: {output}")
    if runtime == ROOT and (ROOT / ".git").exists():
        extract_payload(output)
    else:
        output.mkdir(parents=True)
        copy_payload(runtime, output)
    subprocess.run(
        [
            "node",
            str(ROOT / "build/runtime-bundle.mjs"),
            str(output / "skills/leaf/assets"),
            str(output / "skills/leaf/kernel"),
        ],
        cwd=ROOT,
        check=True,
    )
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
    builds a new kernel, so every page these installations vendor gets the kernel
    rather than the source modules. Recheck after lock acquisition and before
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
                    prepare(staged, runtime)
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
