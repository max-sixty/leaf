"""Fetch and publish the binary files Leaf keeps in max-sixty/leaf-assets.

Every tracked byte ships in every install, so Leaf's tree is text and its images live
in a separate Git repository instead, each at the path its reader would look for it in
the tree (`pinned_copy`):

- `examples/` holds the catalog previews (`leaf_dev.example_previews`), and
  `examples/media/` the images the example pages show (`leaf_dev.page_fixtures`);
- `demo/` holds the README's recording and stills and the site's card
  (`leaf_dev.record_demo`);
- `evals/<case>/` holds what an instruction case hands its child
  (`leaf_dev.instructions_eval`).

`leaf-assets.json` pins one commit, so every Leaf checkout reads one immutable set; the
README's image URLs name the same commit. Downloads land under .tmp, which both local
builds and CI may discard and reconstruct.

    uv run leaf-dev fetch-assets

Every reader calls `pinned_assets()`, which fetches on a miss; the command only warms
the cache, as `wt setup` does. A writer stages its files in a clone and pushes them with
`publish`, which moves the pin and reconciles the catalog's linked images with the
complete published asset set, including previews another writer has published.
Draft site validation consumes derived markup in its own build; staging and refused
publication leave Leaf's consumers unchanged.
"""

import json
import re
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

import click
from leaf.media import media_name

from leaf_dev import ROOT
from leaf_dev.example_data import catalog_sources

LOCK = "leaf-assets.json"
CACHE = ROOT / ".tmp" / "leaf-assets"
README = ROOT / "README.md"


def specification(root: Path = ROOT) -> tuple[str, str]:
    """The repository and revision the checkout at `root` pins."""
    locked = json.loads((root / LOCK).read_text(encoding="utf-8"))
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


def pinned_assets(root: Path = ROOT) -> Path:
    """Return the cached tree of the revision the checkout at `root` pins."""
    repository, revision = specification(root)
    target = CACHE / revision
    if not (target / ".complete").is_file():
        _download(repository, revision, target)
    return target


def assets_lock(path: Path) -> Path | None:
    """The pin governing `path`: the `leaf-assets.json` of the checkout holding it, or
    None outside any checkout that pins assets, such as a scratch source."""
    return next((up / LOCK for up in path.parents if (up / LOCK).is_file()), None)


def pinned_copy(path: Path) -> Path | None:
    """Where the pinned assets hold `path`, a path in a checkout that keeps its bytes
    there. The copy never changes under a pin, so its pin is what a watcher follows."""
    lock = assets_lock(path)
    if lock is None:
        return None
    return pinned_assets(lock.parent) / path.relative_to(lock.parent)


def run(*args: str, cwd: Path) -> str:
    """Run a Git command and keep its failure attached to the operation."""
    completed = subprocess.run(
        args, cwd=cwd, check=False, capture_output=True, text=True
    )
    if completed.returncode:
        output = f"{completed.stdout}{completed.stderr}".strip()
        raise RuntimeError(f"{' '.join(args)} failed:\n{output}")
    return completed.stdout.strip()


def clone(staging: Path) -> Path:
    """Clone the asset repository's current head into `staging`."""
    repository, _ = specification(ROOT)
    checkout = staging / "leaf-assets"
    run(
        "git",
        "clone",
        f"https://github.com/{repository}.git",
        str(checkout),
        cwd=staging,
    )
    return checkout


def catalog_updates(checkout: Path) -> dict[Path, str]:
    """Derive changed catalog documents from the selected asset bytes.

    The authored catalog selects the routes; unused files in the asset repository
    cannot add entries. Unlinked images retain their authored addresses, and pages
    whose links already name the staged bytes are left untouched.
    """
    pages = {
        path: path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "docs").glob("*.html"))
    }
    originals = dict(pages)
    for source in catalog_sources():
        preview = checkout / "examples" / f"example-{source.stem}.jpg"
        address = media_name(preview.read_bytes(), preview.suffix)
        pattern = re.compile(
            rf'(<a\b[^>]*\bhref="/examples/{re.escape(source.stem)}/"[^>]*>'
            rf'(?:(?!</a>).)*?<img\b[^>]*\bsrc=")'
            rf'/media/[0-9a-f]{{16}}\.jpg(")',
            re.DOTALL,
        )
        updated = 0
        for page, markup in pages.items():
            pages[page], count = pattern.subn(rf"\g<1>/media/{address}\g<2>", markup)
            updated += count
        if updated == 0:
            raise RuntimeError(f"{source.stem}: expected one catalog preview")
    return {page: markup for page, markup in pages.items() if markup != originals[page]}


def stage(directory: str, files: dict[str, bytes], staging: Path) -> Path:
    """Clone the asset repository into `staging` with `directory`'s files exactly
    `files`, for a generator to verify before it publishes. Subdirectories are left
    alone: `examples/media/` sits inside the previews' `examples/`. Leaf's catalog,
    pin and README continue naming published bytes."""
    checkout = clone(staging)
    target = checkout / directory
    target.mkdir(parents=True, exist_ok=True)
    for stale in target.iterdir():
        if stale.is_file() and stale.name not in files:
            stale.unlink()
    for name, content in files.items():
        (target / name).write_bytes(content)
    return checkout


def publish(checkout: Path, message: str) -> str:
    """Publish the checkout, then install its pin, README and derived catalog links."""
    repository, _ = specification(ROOT)
    updates = catalog_updates(checkout)
    run("git", "add", "-A", cwd=checkout)
    if run("git", "status", "--porcelain", cwd=checkout):
        run("git", "commit", "-m", message, cwd=checkout)
    run("git", "push", cwd=checkout)
    revision = run("git", "rev-parse", "HEAD", cwd=checkout)
    (ROOT / LOCK).write_text(
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
    for page, markup in updates.items():
        page.write_text(markup, encoding="utf-8")
    return revision


@click.command("fetch-assets")
def fetch_assets() -> None:
    """Fetch the generated images leaf-assets.json pins."""
    click.echo(f"✓ {pinned_assets()}")
