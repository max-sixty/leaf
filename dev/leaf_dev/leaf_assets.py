"""Fetch and publish the generated images Leaf keeps in max-sixty/leaf-assets.

Every tracked byte ships in every install, so the images Leaf generates for its README
and site live in a separate Git repository instead: `examples/` holds the catalog
previews (`leaf_dev.example_previews`) and `demo/` the README's recording and stills
and the site's card (`leaf_dev.record_demo`). `leaf-assets.json` pins one commit, so
every Leaf checkout reads one immutable image set; the README's image URLs name the
same commit. Downloads land under .tmp, which both local builds and CI may discard and
reconstruct.

    uv run leaf-dev fetch-assets

The site build and both generators call `pinned_assets()`, which fetches on a miss; the
command only warms the cache, as `wt setup` does. A generator stages its files in a
clone with `stage` and pushes them with `publish`, which moves the pin.
"""

import json
import re
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

import click

from leaf_dev import ROOT

LOCK = ROOT / "leaf-assets.json"
CACHE = ROOT / ".tmp" / "leaf-assets"
README = ROOT / "README.md"


def specification() -> tuple[str, str]:
    locked = json.loads(LOCK.read_text(encoding="utf-8"))
    return locked["repository"], locked["revision"]


def raw_prefix(repository: str) -> str:
    """Where GitHub serves the repository's files, followed by a revision and a path:
    the URL a README image takes, since GitHub renders a README without a build."""
    return f"https://raw.githubusercontent.com/{repository}/"


def _download(repository: str, revision: str, target: Path) -> None:
    """Extract the archive's files into `target`, renamed into place whole so a
    concurrent reader sees either nothing or the complete set."""
    url = f"https://github.com/{repository}/archive/{revision}.tar.gz"
    root = PurePosixPath(f"{repository.split('/')[1]}-{revision}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=target.parent) as raw:
            payload = Path(raw) / "payload"
            payload.mkdir()
            with (
                urllib.request.urlopen(url, timeout=60) as response,
                tarfile.open(fileobj=response, mode="r|gz") as bundle,
            ):
                for member in bundle:
                    if member.isfile():
                        path = payload / PurePosixPath(member.name).relative_to(root)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(bundle.extractfile(member).read())
            (payload / ".complete").write_text(revision, encoding="utf-8")
            try:
                payload.rename(target)
            except OSError:
                # Another build may have completed the same immutable revision first.
                if not (target / ".complete").is_file():
                    raise
    except (OSError, tarfile.TarError) as error:
        raise RuntimeError(f"could not fetch {url}: {error}") from error


def pinned_assets() -> Path:
    """Return the cached tree of the revision declared by this checkout."""
    repository, revision = specification()
    target = CACHE / revision
    if not (target / ".complete").is_file():
        _download(repository, revision, target)
    return target


def run(*args: str, cwd: Path) -> str:
    """Run a Git command and keep its failure attached to the operation."""
    completed = subprocess.run(
        args, cwd=cwd, check=False, capture_output=True, text=True
    )
    if completed.returncode:
        output = f"{completed.stdout}{completed.stderr}".strip()
        raise RuntimeError(f"{' '.join(args)} failed:\n{output}")
    return completed.stdout.strip()


def stage(directory: str, files: dict[str, bytes], staging: Path) -> Path:
    """Clone the asset repository into `staging` with `directory` holding exactly
    `files`, for the generator to verify before it publishes."""
    repository, _ = specification()
    checkout = staging / "leaf-assets"
    run(
        "git",
        "clone",
        f"https://github.com/{repository}.git",
        str(checkout),
        cwd=staging,
    )
    target = checkout / directory
    target.mkdir(exist_ok=True)
    for stale in target.iterdir():
        if stale.name not in files:
            stale.unlink()
    for name, content in files.items():
        (target / name).write_bytes(content)
    return checkout


def publish(checkout: Path, message: str) -> str:
    """Commit and push a staged checkout, then pin Leaf and its README to it."""
    repository, _ = specification()
    run("git", "add", "-A", cwd=checkout)
    if run("git", "status", "--porcelain", cwd=checkout):
        run("git", "commit", "-m", message, cwd=checkout)
        run("git", "push", cwd=checkout)
    revision = run("git", "rev-parse", "HEAD", cwd=checkout)
    LOCK.write_text(
        json.dumps({"repository": repository, "revision": revision}, indent=2) + "\n",
        encoding="utf-8",
    )
    README.write_text(
        re.sub(
            rf"({re.escape(raw_prefix(repository))})[0-9a-f]{{40}}/",
            rf"\g<1>{revision}/",
            README.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    return revision


@click.command("fetch-assets")
def fetch_assets() -> None:
    """Fetch the generated images leaf-assets.json pins."""
    click.echo(f"✓ {pinned_assets()}")
