"""Fetch and publish the binary files Leaf keeps in max-sixty/leaf-assets.

Every tracked byte ships in every install, so Leaf's tree is text and its images live
in a separate Git repository instead, each at the path its reader would look for it in
the tree (`pinned_copy`):

- `examples/` holds the catalog previews (`leaf_dev.commands.site.previews`),
  `examples/media/` the images the example pages show (`leaf_dev.commands.site.media`),
  and `examples/traces/` the Playwright archives the examples link and the manifests
  imported from them, which an example names as an `asset` capture
  (`leaf_dev.example_data`);
- `demo/` holds the README's recording and stills and the site's card
  (`leaf_dev.commands.site.demo`);
- `evals/<case>/` holds what an instruction case hands its child
  (`leaf_dev.commands.eval.run`).

`leaf-assets.json` pins one commit of the asset repository. Downloads land under .tmp,
which both local builds and CI may discard and reconstruct.

Every reader calls `pinned_assets()`, which fetches on a miss; `leaf-dev setup` warms
the cache. A writer stages its files in a clone of the revision its checkout pins, so
what it adds, replaces or removes is measured against the set its own branch reads.
`publish` replays that change onto the repository's head, which keeps files other
branches published since, then moves the pin. The site's pages name catalog previews
by example (`leaf_dev.docs`), so a moved pin changes no page source; only the README,
which GitHub renders without a build, names the pinned commit. Staging and refused
publication leave Leaf's consumers unchanged.

The head's history is a line and every pin is a commit on it, so in a merge conflict
over `leaf-assets.json`, take the later `revision`: it holds both branches' files.
Where both branches published the same file, the later pin holds the later
publication's copy, so publish that file again from the merged tree.
"""

import json
import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from leaf_dev import ROOT

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
    """Fetch the pinned commit over Git and publish its files atomically.

    Cloud environments allow Git transport where GitHub's archive endpoints are
    blocked. Git archives the selected commit locally, so neither the remote head
    nor checkout filters can change the bytes a pin selects.
    """
    url = f"https://github.com/{repository}.git"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=target.parent) as raw:
            payload = Path(raw) / "payload"
            payload.mkdir()
            git = Path(raw) / "repository.git"
            run("git", "init", "--bare", str(git), cwd=Path(raw))
            run("git", "fetch", "--depth", "1", url, revision, cwd=git)
            archive = Path(raw) / "assets.tar"
            run(
                "git",
                "-c",
                f"core.attributesFile={os.devnull}",
                "-c",
                "core.autocrlf=false",
                "archive",
                "--worktree-attributes",
                f"--output={archive}",
                revision,
                cwd=git,
            )
            with tarfile.open(archive) as bundle:
                for member in bundle:
                    if member.isfile():
                        path = payload / PurePosixPath(member.name)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        content = bundle.extractfile(member)
                        assert content is not None
                        path.write_bytes(content.read())
            (payload / ".complete").write_text(revision, encoding="utf-8")
            try:
                payload.rename(target)
            except OSError:
                # Another build may have completed the same immutable revision first.
                if not (target / ".complete").is_file():
                    raise
    except (OSError, tarfile.TarError, RuntimeError) as error:
        raise RuntimeError(f"could not fetch {url} at {revision}: {error}") from error


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
    """Clone the asset repository into `staging`, checked out at the revision Leaf pins,
    so a writer changes the set this checkout reads."""
    repository, revision = specification(ROOT)
    path = staging / "leaf-assets"
    run(
        "git",
        "clone",
        "--depth",
        "1",
        f"https://github.com/{repository}.git",
        str(path),
        cwd=staging,
    )
    run("git", "fetch", "--depth", "1", "origin", revision, cwd=path)
    run("git", "checkout", "--detach", revision, cwd=path)
    return path


def stage(directory: str, files: dict[str, bytes], staging: Path) -> Path:
    """Clone the pinned assets into `staging` with `directory`'s files exactly `files`,
    for a generator to verify before it publishes. A file the pin holds and `files`
    lacks is removed; one another branch published since the pin is not there to
    remove. Subdirectories are left alone: `examples/media/` sits inside the previews'
    `examples/`. Leaf's pin and README continue naming published bytes."""
    checkout = clone(staging)
    target = checkout / directory
    target.mkdir(parents=True, exist_ok=True)
    for stale in target.iterdir():
        if stale.is_file() and stale.name not in files:
            stale.unlink()
    for name, content in files.items():
        (target / name).write_bytes(content)
    return checkout


# Where a clone keeps the change it publishes, so a retry replays the same change.
CHANGE = "refs/leaf-assets/change"


def replay(path: Path, branch: str) -> None:
    """Check out the remote head with the change applied in the clone at `path`: each
    file the change added or altered takes the change's copy, and each it removed is
    removed, whatever another writer did to that file since the pin."""
    run("git", "fetch", "--depth", "1", "origin", branch, cwd=path)
    run("git", "checkout", "--detach", "FETCH_HEAD", cwd=path)
    fields = run(
        "git",
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        f"{CHANGE}^",
        CHANGE,
        cwd=path,
    ).split("\0")[:-1]
    changed = dict(zip(fields[1::2], fields[0::2], strict=True))
    if kept := [name for name, status in changed.items() if status != "D"]:
        run("git", "checkout", CHANGE, "--", *kept, cwd=path)
    if removed := [name for name, status in changed.items() if status == "D"]:
        run("git", "rm", "-q", "--ignore-unmatch", "--", *removed, cwd=path)
    if run("git", "status", "--porcelain", cwd=path):
        run("git", "commit", "-C", CHANGE, cwd=path)


def publish(path: Path, message: str) -> str:
    """Commit the change in the clone at `path` to its pin, replay it onto the
    repository's head and push it, then advance the pin the clone was made from and the
    README's image links. Where another writer changed or removed the same file since
    the pin, this change's copy stands, as it would have on the pin. A rejected push
    leaves its change available for an explicit retry; an unchanged clone keeps its
    pin."""
    repository, pinned = specification(ROOT)
    branch = run(
        "git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=path
    ).removeprefix("origin/")
    run("git", "add", "-A", cwd=path)
    if run("git", "status", "--porcelain", cwd=path):
        run("git", "commit", "-m", message, cwd=path)
        run("git", "update-ref", CHANGE, "HEAD", cwd=path)
    has_change = bool(run("git", "for-each-ref", CHANGE, cwd=path))
    if has_change:
        replay(path, branch)
    revision = run("git", "rev-parse", "HEAD", cwd=path)
    if revision != pinned:
        run("git", "push", "origin", f"HEAD:refs/heads/{branch}", cwd=path)
    lock = ROOT / LOCK
    locked = json.loads(lock.read_text(encoding="utf-8"))
    locked["revision"] = revision
    lock.write_text(
        json.dumps(locked, indent=2) + "\n",
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
