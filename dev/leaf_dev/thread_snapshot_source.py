"""Materialize reviewed appearance from an explicit approved source, not merge base.

The tracked expectation is a reachable public main commit plus an ordinary text
patch of its payload, build inputs and examples. Generated vendors are rebuilt
through the existing locked browser/vendor generators, never copied into the patch.
This stays valid after a squash merge; no image,
private asset or dangling feature commit enters the repository. The pin changes only
with explicit acceptance. Cold setup installs Node dependencies and rebuilds the
approved vendors; ordinary checks reuse the verified image cache. Each platform
renders that source with its own browser,
which avoids separate platform PNG approvals. Both arms share the browser, so a
browser upgrade's own visual regression is outside this oracle.

The baseline owns its Python Leaf and fixtures. Only the current journey, snapshot
adapter and pytest plugin are overlaid. A recipe incompatible with approved source
fails during generation and requires a reviewed source refresh. Missing pins, failed
generation and incomplete stores never fall back to the candidate's appearance.
"""

import hashlib
import json
import shutil
import subprocess
import tempfile
from importlib.metadata import version
from pathlib import Path

from leaf.session_cleanup import flocked

from leaf_dev import ROOT
from leaf_dev.harness import PAYLOAD, build_arm, environment, extract_ref
from leaf_dev.thread_journey import STAGES
from leaf_dev.thread_snapshots import CASES, render_profile

PIN = ROOT / "tests/snapshots/thread-source.json"
PATCH = PIN.with_suffix(".patch")
INLINE_FIXTURE = (
    "tests/fixtures/pages/thread-journey-inline.html",
    "tests/fixtures/pages/thread-journey-inline.data.json",
    "tests/fixtures/pages/thread-journey-inline.patch",
)
SOURCE_PATHS = (
    *PAYLOAD,
    "build",
    "package.json",
    "package-lock.json",
    "examples",
    "leaf-assets.json",
    *INLINE_FIXTURE,
)
# These outputs are owned by build/AGENTS.md and the existing generators. Approved
# source rebuilds them; putting minified megabyte diffs in the pin would duplicate
# the bundles and exceed the repository's ordinary new-file limit.
SOURCE_PATCH_PATHS = (
    *SOURCE_PATHS,
    ":(glob,exclude)skills/**/vendor/**",
    ":(glob,exclude)build/browser/generated/**",
)
RECIPE = (
    "dev/leaf_dev/thread_journey.py",
    "dev/leaf_dev/thread_snapshots.py",
    "dev/leaf_dev/thread_snapshot_plugin.py",
    "tests/test_render_thread_snapshots.py",
)
CACHE = ROOT / ".tmp/thread-snapshots/approved"


def git(*args: str) -> str:
    """Read the checkout's source, keeping a failed command's evidence."""
    result = subprocess.run(
        ["git", "-C", ROOT, *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise RuntimeError(
            f"git {' '.join(args)} failed:\n{result.stdout}{result.stderr}"
        )
    return result.stdout


def source_pin(*, prepare: bool) -> tuple[str, bytes]:
    locked = json.loads(PIN.read_text())
    base = locked["base"]
    patch = PATCH.read_bytes()
    if "GIT binary patch" in patch.decode():
        raise ValueError("approved source must contain only text")
    CACHE.mkdir(parents=True, exist_ok=True)
    with flocked(CACHE / "source-fetch.lock"):
        available = subprocess.run(
            ["git", "-C", ROOT, "cat-file", "-e", f"{base}^{{commit}}"],
            capture_output=True,
            check=False,
        )
        if available.returncode and prepare:
            # A clean CI checkout is shallow. This reads a durable main commit
            # once across pytest workers, without publishing or changing the tree.
            git("fetch", "--no-tags", "origin", base)
    return base, patch


def capture_source(base: str, patch: bytes, destination: Path) -> Path:
    """Run approved source's own builds/server; retire every extracted environment."""
    destination.mkdir(parents=True, exist_ok=True)
    store = destination / "images"
    log = destination / "capture.log"
    log.write_text("")
    (destination / "approved.patch").write_bytes(patch)
    (destination / "provenance.json").write_text(
        json.dumps(
            {
                "base": base,
                "patch_sha256": hashlib.sha256(patch).hexdigest(),
                "recipe": {
                    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                    for name in RECIPE
                },
            },
            indent=2,
        )
        + "\n"
    )
    with tempfile.TemporaryDirectory(prefix="leaf-thread-snapshot-") as scratch:
        arm = Path(scratch)
        try:
            build_arm(base, arm)
            extract_ref(
                arm,
                base,
                (
                    "dev",
                    "tests",
                    "examples",
                    "worker",
                    "leaf-assets.json",
                    "build",
                    "package.json",
                    "package-lock.json",
                ),
            )
            if patch:
                applied = subprocess.run(
                    ["git", "apply", "-"],
                    cwd=arm,
                    input=patch,
                    capture_output=True,
                    check=False,
                    env=environment(GIT_CEILING_DIRECTORIES=str(arm.parent)),
                )
                if applied.returncode:
                    raise RuntimeError(
                        f"approved source patch failed:\n{applied.stderr.decode()}"
                    )
            for name in RECIPE:
                target = arm / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            commands = (
                ["npm", "ci"],
                ["npm", "run", "build:browser"],
                ["uv", "run", "--project", str(arm), "build/vendor.py"],
                [
                    "uv",
                    "run",
                    "--project",
                    str(arm),
                    "--with",
                    f"pytest-image-snapshot[pixelmatch]=={version('pytest-image-snapshot')}",
                    "--with",
                    f"playwright=={version('playwright')}",
                    "pytest",
                    "-n0",
                    "-q",
                    "-p",
                    "leaf_dev.thread_snapshot_plugin",
                    "--image-snapshot-update",
                    "--image-snapshot-save-diff",
                    "--thread-snapshot-store",
                    str(store),
                    "tests/test_render_thread_snapshots.py",
                ],
            )
            for command in commands:
                with log.open("a") as evidence:
                    evidence.write(" ".join(command) + "\n")
                result = subprocess.run(
                    command,
                    cwd=arm,
                    env=environment(PYTEST_ADDOPTS="", VIRTUAL_ENV=str(arm / ".venv")),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=600,
                )
                with log.open("a") as evidence:
                    evidence.write(result.stdout + result.stderr)
                if result.returncode:
                    raise RuntimeError(
                        f"approved source preparation failed (no expectations created):\n"
                        f"{result.stdout}{result.stderr}\nEvidence: {destination}"
                    )
        finally:
            # Keep readings and images, not hundreds of MB of disposable Python/Node
            # environments. A failed preparation has the same retirement boundary.
            observations = destination / "observations"
            for reading in (arm / ".tmp/thread-snapshots/runs").glob(
                "*/*/observations.json"
            ):
                observations.mkdir(exist_ok=True)
                shutil.copyfile(reading, observations / f"{reading.parent.name}.json")
    return store


def approved_store(browser_version: str) -> Path:
    """Read the prepared cache without fetching source or installing dependencies."""
    return snapshot_store(browser_version, prepare=False)


def prepare_store(browser_version: str) -> Path:
    """Materialize explicit approved source during setup, once per recipe/profile."""
    return snapshot_store(browser_version, prepare=True)


def snapshot_store(browser_version: str, *, prepare: bool) -> Path:
    """One fingerprint and inventory owner for preparation and read-only checks."""
    base, patch = source_pin(prepare=prepare)
    digest = hashlib.sha256(base.encode() + patch)
    for name in (
        *RECIPE,
        "dev/leaf_dev/thread_snapshot_source.py",
        "dev/leaf_dev/harness.py",
        "dev/leaf_dev/browser.py",
        "uv.lock",
    ):
        digest.update((ROOT / name).read_bytes())
    digest.update(render_profile(browser_version).encode())
    digest.update(version("playwright").encode())
    destination = CACHE / digest.hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)
    with flocked(destination.with_suffix(".lock")):
        complete = destination / "complete.json"
        store = destination / "images"
        if not complete.is_file():
            if not prepare:
                raise RuntimeError(
                    "approved thread snapshots are not prepared; run "
                    "uv run leaf-dev thread-snapshots prepare"
                )
            store = capture_source(base, patch, destination)
            images = {
                str(path.relative_to(store)): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in store.rglob("*")
                if path.is_file()
            }
            complete.write_text(json.dumps(images, indent=2) + "\n")
        images = json.loads(complete.read_text())
        for case in CASES:
            for stage in STAGES:
                for suffix in ("png", "json"):
                    name = f"{render_profile(browser_version)}/{case.name}-{stage}.{suffix}"
                    path = store / name
                    if hashlib.sha256(path.read_bytes()).hexdigest() != images[name]:
                        raise RuntimeError(f"approved snapshot cache changed: {path}")
    return store


def accept_source() -> None:
    """Freeze current tracked payload against a public main ancestor, squash-safe."""
    untracked = git("ls-files", "--others", "--exclude-standard", "--", *SOURCE_PATHS)
    if untracked.strip():
        raise ValueError(f"stage new source files before acceptance:\n{untracked}")
    base = git("merge-base", "HEAD", "origin/main").strip()
    patch = git("diff", "--binary", base, "--", *SOURCE_PATCH_PATHS)
    if "GIT binary patch" in patch:
        raise ValueError("approved source must contain only text")
    PIN.parent.mkdir(parents=True, exist_ok=True)
    PIN.write_text(json.dumps({"base": base}, indent=2) + "\n")
    PATCH.write_text(patch)
