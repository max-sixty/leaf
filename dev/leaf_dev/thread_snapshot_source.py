"""Materialize reviewed appearance from an explicit approved source, not merge base.

The tracked expectation is a reachable public main commit plus an ordinary text
patch of its payload and examples. This stays valid after a squash merge; no image,
private asset or dangling feature commit enters the repository. The pin changes only
with explicit acceptance. Each platform renders that source with its own browser,
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
SOURCE_PATHS = (*PAYLOAD, "examples", "leaf-assets.json", *INLINE_FIXTURE)
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
    """Run the one journey against the approved arm's own server and runtime."""
    destination.mkdir(parents=True, exist_ok=True)
    arm, store = destination / "source", destination / "images"
    build_arm(base, arm)
    extract_ref(arm, base, ("dev", "tests", "examples", "worker", "leaf-assets.json"))
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
    result = subprocess.run(
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
        cwd=arm,
        env=environment(PYTEST_ADDOPTS="", VIRTUAL_ENV=str(arm / ".venv")),
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    (destination / "capture.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(
            f"approved source capture failed (no expectations created):\n"
            f"{result.stdout}{result.stderr}\nEvidence: {destination}"
        )
    # The approved captures are the cache. The extracted environment can exceed
    # 200 MB, so retire this owned arm after success instead of caching every copy.
    shutil.rmtree(arm)
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
    patch = git("diff", "--binary", base, "--", *SOURCE_PATHS)
    if "GIT binary patch" in patch:
        raise ValueError("approved source must contain only text")
    PIN.parent.mkdir(parents=True, exist_ok=True)
    PIN.write_text(json.dumps({"base": base}, indent=2) + "\n")
    PATCH.write_text(patch)
