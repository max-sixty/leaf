#!/usr/bin/env python3
"""Fetch the exact external image revision used to build leaf.page.

The generated catalog previews live in a separate Git repository so their history
does not enlarge Leaf installs. A tracked commit pin keeps every Leaf checkout tied to
one immutable image set. Downloads land under .tmp, which both local builds and CI may
discard and reconstruct.

Usage: uv run scripts/example_assets.py
"""

import json
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "example-previews.json"
CACHE = ROOT / ".tmp" / "example-previews"


def specification() -> tuple[str, str]:
    locked = json.loads(LOCK.read_text(encoding="utf-8"))
    repository = locked["repository"]
    revision = locked["revision"]
    if not isinstance(repository, str) or not isinstance(revision, str):
        raise RuntimeError(
            f"{LOCK.name} must contain string repository and revision values"
        )
    if len(revision) != 40 or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise RuntimeError(f"{LOCK.name} revision must be a full lowercase Git commit")
    return repository, revision


def _download(repository: str, revision: str, target: Path) -> None:
    owner, name = repository.split("/", 1)
    url = f"https://github.com/{owner}/{name}/archive/{revision}.tar.gz"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(
            prefix=f"{revision}-", dir=target.parent
        ) as raw:
            staging = Path(raw)
            archive = staging / "assets.tar.gz"
            with urllib.request.urlopen(url, timeout=60) as response, archive.open(
                "wb"
            ) as output:
                shutil.copyfileobj(response, output)

            previews = staging / "payload" / "examples"
            previews.mkdir(parents=True)
            root = f"{name}-{revision}/examples"
            with tarfile.open(archive, "r:gz") as bundle:
                members = []
                for member in bundle.getmembers():
                    path = PurePosixPath(member.name)
                    if path.parent.as_posix() != root or path.suffix.lower() != ".jpg":
                        continue
                    if not member.isfile():
                        raise RuntimeError(
                            f"asset archive entry is not a file: {member.name}"
                        )
                    members.append(member)
                if not members:
                    raise RuntimeError(
                        f"{repository}@{revision} contains no example previews"
                    )
                for member in members:
                    source = bundle.extractfile(member)
                    if source is None:
                        raise RuntimeError(
                            f"could not read asset archive entry: {member.name}"
                        )
                    target_name = PurePosixPath(member.name).name
                    with source, (previews / target_name).open("wb") as output:
                        shutil.copyfileobj(source, output)
            (staging / "payload" / ".complete").write_text(
                revision, encoding="utf-8"
            )
            try:
                (staging / "payload").rename(target)
            except FileExistsError:
                # Another build may have completed the same immutable revision first.
                if not (target / ".complete").is_file():
                    raise RuntimeError(f"incomplete asset cache already exists: {target}")
    except (OSError, tarfile.TarError, urllib.error.URLError) as error:
        raise RuntimeError(
            f"could not fetch {repository}@{revision}: {error}"
        ) from error


def example_previews() -> Path:
    """Return the cached directory for the revision declared by this checkout."""
    repository, revision = specification()
    target = CACHE / revision
    if not (target / ".complete").is_file():
        _download(repository, revision, target)
    return target / "examples"


def main() -> None:
    previews = example_previews()
    print(f"✓ {len(list(previews.glob('example-*.jpg')))} previews → {previews}")


if __name__ == "__main__":
    main()
