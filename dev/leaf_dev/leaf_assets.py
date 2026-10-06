"""Fetch and publish the binary files Leaf keeps in max-sixty/leaf-assets.

Every tracked byte ships in every install, so Leaf's tree is text and its images live
in a separate Git repository instead, each at the path its reader would look for it in
the tree (`pinned_copy`):

- `examples/` holds the catalog previews (`leaf_dev.example_previews`), and
  `examples/media/` the images the example pages show (`leaf_dev.page_fixtures`);
- `demo/` holds the README's recording and stills and the site's card
  (`leaf_dev.record_demo`);
- `evals/<case>/` holds what an instruction case hands its child
  (`leaf_dev.eval`).

`leaf-assets.json` pins media and reviewed thread expectations independently. Media
publication follows the asset head; only snapshot acceptance advances the expectations
that belong to this runtime. README image URLs name the media commit. Downloads land
under .tmp, which both local builds and CI may discard and reconstruct.

    uv run leaf-dev fetch-assets

Every reader calls `pinned_assets()`, which fetches on a miss; the command only warms
the cache, as `wt setup` does. A writer stages its files in a clone of the revision its
checkout pins, so what it adds, replaces or removes is measured against the set its own
branch reads. `publish` replays that change onto the repository's head, which keeps
files other branches published since, then moves the pin and reconciles the catalog's
linked images with the complete published asset set, including previews another
writer has published. A writer that owns a whole tree, as snapshot acceptance owns
the expectations, publishes that tree exactly as it staged it. The head's history is a
line and every pin is a commit on it, so of two media pins that meet in a merge the
later holds both branches' files.
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
from typing import Literal

import click
from leaf.media import media_name

from leaf_dev import ROOT
from leaf_dev.example_data import catalog_sources

LOCK = "leaf-assets.json"
CACHE = ROOT / ".tmp" / "leaf-assets"
README = ROOT / "README.md"
RevisionKey = Literal["revision", "thread_snapshots_revision"]


def specification(
    root: Path = ROOT, *, revision_key: RevisionKey = "revision"
) -> tuple[str, str]:
    """The repository and revision the checkout at `root` pins."""
    locked = json.loads((root / LOCK).read_text(encoding="utf-8"))
    return locked["repository"], locked[revision_key]


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


def pinned_assets(root: Path = ROOT, *, revision_key: RevisionKey = "revision") -> Path:
    """Return the cached tree of the revision the checkout at `root` pins."""
    repository, revision = specification(root, revision_key=revision_key)
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


def clone(staging: Path, *, revision_key: RevisionKey = "revision") -> Path:
    """Clone the asset repository into `staging`, checked out at the revision Leaf pins
    under `revision_key`, so a writer changes the set this checkout reads. The checkout
    remembers that pin for `publish`."""
    repository, revision = specification(ROOT, revision_key=revision_key)
    checkout = staging / "leaf-assets"
    run(
        "git",
        "clone",
        "--depth",
        "1",
        f"https://github.com/{repository}.git",
        str(checkout),
        cwd=staging,
    )
    run("git", "fetch", "--depth", "1", "origin", revision, cwd=checkout)
    run("git", "checkout", "--detach", revision, cwd=checkout)
    run("git", "config", "leaf-assets.pin", revision_key, cwd=checkout)
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


def stage(
    directory: str,
    files: dict[str, bytes],
    staging: Path,
    *,
    replace_tree: bool = False,
    revision_key: RevisionKey = "revision",
) -> Path:
    """Clone the assets pinned under `revision_key` into `staging` with `directory`'s
    files exactly `files`, for a generator to verify before it publishes. A file the
    pin holds and `files` lacks is removed; one another branch published since the pin
    is not there to remove. Subdirectories are left alone unless the caller owns the
    complete tree, which `publish` then installs whole: `examples/media/` sits inside
    the previews' `examples/`. Leaf's catalog, pin and README continue naming
    published bytes."""
    checkout = clone(staging, revision_key=revision_key)
    if replace_tree:
        run("git", "config", "leaf-assets.tree", directory, cwd=checkout)
    target = checkout / directory
    target.mkdir(parents=True, exist_ok=True)
    for stale in target.rglob("*") if replace_tree else target.iterdir():
        if stale.is_file() and stale.relative_to(target).as_posix() not in files:
            stale.unlink()
    for name, content in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return checkout


# Where a checkout keeps the change it publishes, so a retry replays the same change.
CHANGE = "refs/leaf-assets/change"
# Pushes a publication tries before reporting the last rejection: another publisher
# may move the head between one attempt's fetch and its push.
PUSH_ATTEMPTS = 3


def setting(checkout: Path, name: str) -> str:
    """What `clone` or `stage` recorded in the checkout, or "" where nothing was."""
    return run("git", "config", "--default", "", "--get", name, cwd=checkout)


def replay(checkout: Path, branch: str) -> None:
    """Check out the remote head with the change applied: each file the change added or
    altered takes the change's copy, and each it removed is removed, whatever another
    writer did to that file since the pin. A tree the stage owns takes the change's
    tree whole."""
    run("git", "fetch", "--depth", "1", "origin", branch, cwd=checkout)
    run("git", "checkout", "--detach", "FETCH_HEAD", cwd=checkout)
    if tree := setting(checkout, "leaf-assets.tree"):
        run("git", "rm", "-r", "-q", "--ignore-unmatch", "--", tree, cwd=checkout)
        if run("git", "ls-tree", "--name-only", CHANGE, tree, cwd=checkout):
            run("git", "checkout", CHANGE, "--", tree, cwd=checkout)
    fields = run(
        "git",
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        f"{CHANGE}^",
        CHANGE,
        cwd=checkout,
    ).split("\0")
    changed = dict(zip(fields[1::2], fields[0::2]))
    if kept := [path for path, status in changed.items() if status != "D"]:
        run("git", "checkout", CHANGE, "--", *kept, cwd=checkout)
    if removed := [path for path, status in changed.items() if status == "D"]:
        run("git", "rm", "-q", "--ignore-unmatch", "--", *removed, cwd=checkout)
    if run("git", "status", "--porcelain", cwd=checkout):
        run("git", "commit", "-C", CHANGE, cwd=checkout)


def publish(checkout: Path, message: str) -> str:
    """Commit the checkout's change to its pin, replay it onto the repository's head and
    push it, then advance the pin the checkout was cloned from. Media also updates the
    README and catalog links. Where another writer changed or removed the same file
    since the pin, this change's copy stands, as it would have on the pin. A rejected
    push replays the change onto the head again; an unchanged checkout keeps its pin."""
    revision_key = setting(checkout, "leaf-assets.pin")
    repository, pinned = specification(ROOT, revision_key=revision_key)
    branch = run(
        "git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=checkout
    ).removeprefix("origin/")
    run("git", "add", "-A", cwd=checkout)
    if run("git", "status", "--porcelain", cwd=checkout):
        run("git", "commit", "-m", message, cwd=checkout)
        run("git", "update-ref", CHANGE, "HEAD", cwd=checkout)
    has_change = bool(run("git", "for-each-ref", CHANGE, cwd=checkout))
    for attempt in range(PUSH_ATTEMPTS):
        if has_change:
            replay(checkout, branch)
        revision = run("git", "rev-parse", "HEAD", cwd=checkout)
        updates = catalog_updates(checkout) if revision_key == "revision" else {}
        if revision == pinned:
            break
        try:
            run("git", "push", "origin", f"HEAD:refs/heads/{branch}", cwd=checkout)
            break
        except RuntimeError:
            if attempt + 1 == PUSH_ATTEMPTS:
                raise
    lock = ROOT / LOCK
    locked = json.loads(lock.read_text(encoding="utf-8"))
    locked[revision_key] = revision
    lock.write_text(
        json.dumps(locked, indent=2) + "\n",
        encoding="utf-8",
    )
    if revision_key == "revision":
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
    for revision_key in ("revision", "thread_snapshots_revision"):
        click.echo(f"✓ {pinned_assets(revision_key=revision_key)}")
