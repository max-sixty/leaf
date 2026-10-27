"""Prepare and reuse installation trees whose committed kernel is current.

An install is the tracked tree. It serves the kernel committed under
`dist/kernel/` wherever that was compiled from the tree's own modules, and the
source modules otherwise (`leaf.runtime_selection.read_runtime`). A developer
checkout's kernel is stale whenever its runtime has been edited and not rebuilt, so the
website, the suite's browser tiers, and developer previews run a prepared installation
instead: the payload with its kernel compiled again by the same build
(`build/runtime-bundle.mjs`), so each serves the kernel an install of that tree will
serve once it is rebuilt. The website's container installs that same payload
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
import time
from pathlib import Path

import click

from leaf import state
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


def compiler_root() -> Path:
    """The developer checkout that launched a selected-runtime preview."""
    return Path(os.environ.get("LEAF_PREVIEW_COMPILER_ROOT", ROOT)).resolve()


# An entry serves one state of a checkout, so it is reused within a burst of work and
# then never again: the entries one day's sessions made were last used under 40
# minutes after they were built. The longest use that selects an entry only once is a
# browser-tier suite run, which reads its kernel for up to a little over an hour.
KEEP_SECONDS = 3 * 3600


def cache_root() -> Path:
    """Where prepared installations live: one directory per user, not per checkout.

    An entry's name is the hash of everything that determines it (payload, compiler
    inputs, provenance), so worktrees and arms with the same content share one, and
    a new worktree starts warm instead of compiling the kernel again.
    """
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(os.environ.get("LEAF_DEV_CACHE_DIR", Path(base) / "leaf-dev")) / (
        "compiled-runtime"
    )


def launched_entries() -> set[Path]:
    """The cache entries that live sessions have selected as their launcher.

    A `--user` preview saves its entry's `bin/leaf` in the session record
    (`session_runtime.select_launcher`), and the session's hooks and page server run
    from it for as long as the record exists, however long ago the entry was
    selected. The record is Leaf's own answer to "is this install in use".
    """
    sessions = state.state_home() / "sessions"
    records = (
        state.SESSION.read(path) for path in sessions.glob(f"*.{state.SESSION_SUFFIX}")
    )
    return {
        Path(record["launcher"]).parent.parent
        for record in records
        if record and not record["ended"] and record.get("launcher")
    }


def evict(cache: Path) -> None:
    """Delete entries nothing has selected for `KEEP_SECONDS` (a hit touches its
    entry) and no live session launches from, and abandoned staging directories.
    Age is read again under the entry's lock, since a reader may have selected it
    since the listing. Lock files stay: removing one would let a waiter and a
    newcomer lock different inodes."""
    now = time.time()
    launched = launched_entries()
    for path in cache.iterdir():
        if now - path.stat().st_mtime <= KEEP_SECONDS or not path.is_dir():
            continue
        if path.name.startswith(".preparing-"):
            shutil.rmtree(path, ignore_errors=True)
        elif not path.name.startswith(".") and path.resolve() not in launched:
            with flocked(cache / f"{path.name}.lock"):
                if path.is_dir() and now - path.stat().st_mtime > KEEP_SECONDS:
                    shutil.rmtree(path, ignore_errors=True)


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
    # The selected runtime owns its resource layout. Read its locators through its
    # own environment, since comparison arms can arrange their payload differently.
    resources = subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            "--no-dev",
            "--project",
            str(runtime),
            "python",
            "-c",
            (
                "import json; from leaf.schema import ASSETS, KERNEL, PLUGIN_ROOT; "
                "print(json.dumps([str(p.relative_to(PLUGIN_ROOT)) for p in (ASSETS, KERNEL)]))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assets, kernel = json.loads(resources.stdout)
    bundle_runtime(output / assets, output / kernel)
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
    compiler = compiler_root()
    inputs = {
        **{f"payload/{path.relative_to(runtime).as_posix()}": path for path in payload},
        **{f"compiler/{name}": compiler / name for name in COMPILER_INPUTS},
    }
    return {name: path for name, path in sorted(inputs.items()) if path.is_file()}


def installation_identity(runtime: Path = ROOT) -> str:
    """Content identity, independent of mtimes, Git labels, and authored revisions."""
    return files_identity(
        {name: path.read_bytes() for name, path in installation_inputs(runtime).items()}
    ).removeprefix("sha256:")


def cached_installation(runtime: Path = ROOT) -> Path:
    """Share an immutable installation for content and producer provenance.

    Git-label changes rebuild the payload as content changes do. Recheck after
    acquiring the lock and before publication so a racing edit is selected without
    another watcher event. Failed builds publish no cache entry.
    """
    runtime = runtime.resolve()
    if (runtime / "leaf-distribution.json").is_file():
        return runtime
    cache = cache_root()
    cache.mkdir(parents=True, exist_ok=True)

    def identity():
        return files_identity(
            {
                "content": installation_identity(runtime).encode(),
                "producer": json.dumps(
                    payload_provenance(root=runtime), sort_keys=True
                ).encode(),
            }
        ).removeprefix("sha256:")

    while True:
        selected = identity()
        output = cache / selected
        with flocked(cache / f"{selected}.lock"):
            if identity() != selected:
                continue
            if output.is_dir():
                if identity() != selected:
                    continue
                os.utime(output)
                return output
            with tempfile.TemporaryDirectory(prefix=".preparing-", dir=cache) as raw:
                staged = Path(raw) / "installation"
                prepare(staged, runtime)
                if identity() != selected:
                    continue
                staged.rename(output)
            # Best effort: a concurrent sweep or publisher can remove a path this one
            # listed, and the runtime is already published.
            try:
                evict(cache)
            except FileNotFoundError:
                pass
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
