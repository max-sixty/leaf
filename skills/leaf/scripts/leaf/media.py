"""Content-addressed page media ingestion."""

import hashlib
import sys
from pathlib import Path

from leaf.files import replace_files
from leaf.schema import MEDIA_DIR, MEDIA_TYPES


def cmd_media(page_dir: Path, files: list) -> list:
    """Copy images into the page's media directory, named by the hash of their
    bytes; returns (source, served path) per file, in the order given.

    Content-addressing is doing two jobs. It keeps the directory's promise —
    a name can only ever mean one set of bytes, so a version the user
    approved shows them the same picture forever, which is the same guarantee
    vendoring gives the layer. And it de-duplicates for free: a version that
    re-shows last version's screenshot re-uses the file rather than a second
    copy of it, which is what makes the version history cheap to keep."""
    out = []
    media_dir = page_dir / MEDIA_DIR
    media_dir.mkdir(exist_ok=True)
    for src in files:
        if src.suffix.lower() not in MEDIA_TYPES:
            sys.exit(
                f"{src}: not an image leaf serves — {', '.join(sorted(MEDIA_TYPES))}"
            )
        data = src.read_bytes()
        name = hashlib.sha256(data).hexdigest()[:16] + src.suffix.lower()
        replace_files([(media_dir / name, data, False)])
        out.append((str(src), f"/{MEDIA_DIR}/{name}"))
    return out
