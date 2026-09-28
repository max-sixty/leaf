"""Fetch the exact external image revision used to build leaf.page.

The generated catalog previews live in a separate Git repository so their history
does not enlarge Leaf installs. A tracked commit pin keeps every Leaf checkout tied to
one immutable image set. Downloads land under .tmp, which both local builds and CI may
discard and reconstruct.

    uv run leaf-dev fetch-previews

The site build (`leaf_dev.site`) and the preview refresh (`leaf_dev.example_previews`)
call `example_previews()`, which fetches on a miss; the command only warms the cache,
as `wt setup` does.
"""

import json
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

import click

from leaf_dev import ROOT

LOCK = ROOT / "example-previews.json"
CACHE = ROOT / ".tmp" / "example-previews"


def specification() -> tuple[str, str]:
    locked = json.loads(LOCK.read_text(encoding="utf-8"))
    return locked["repository"], locked["revision"]


def _download(repository: str, revision: str, target: Path) -> None:
    """Extract the archive's `examples/*.jpg` into `target`, renamed into place whole
    so a concurrent reader sees either nothing or the complete set."""
    url = f"https://github.com/{repository}/archive/{revision}.tar.gz"
    root = f"{repository.split('/')[1]}-{revision}/examples"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=target.parent) as raw:
            payload = Path(raw) / "payload"
            (payload / "examples").mkdir(parents=True)
            with (
                urllib.request.urlopen(url, timeout=60) as response,
                tarfile.open(fileobj=response, mode="r|gz") as bundle,
            ):
                for member in bundle:
                    path = PurePosixPath(member.name)
                    if (
                        member.isfile()
                        and path.parent.as_posix() == root
                        and path.suffix.lower() == ".jpg"
                    ):
                        (payload / "examples" / path.name).write_bytes(
                            bundle.extractfile(member).read()
                        )
            (payload / ".complete").write_text(revision, encoding="utf-8")
            try:
                payload.rename(target)
            except OSError:
                # Another build may have completed the same immutable revision first.
                if not (target / ".complete").is_file():
                    raise
    except (OSError, tarfile.TarError) as error:
        raise RuntimeError(f"could not fetch {url}: {error}") from error


def example_previews() -> Path:
    """Return the cached directory for the revision declared by this checkout."""
    repository, revision = specification()
    target = CACHE / revision
    if not (target / ".complete").is_file():
        _download(repository, revision, target)
    return target / "examples"


@click.command("fetch-previews")
def fetch_previews() -> None:
    """Fetch the catalog previews example-previews.json pins."""
    previews = example_previews()
    click.echo(f"✓ {len(list(previews.glob('example-*.jpg')))} previews → {previews}")
