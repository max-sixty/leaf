"""Content-addressed page media ingestion.

Page authors and readers enter through different trust boundaries. ``page media``
accepts a local file the author chose; the browser upload door accepts untrusted bytes
and therefore derives the extension from a small raster MIME vocabulary and verifies
its file signature before both paths meet at the same content-addressed writer.
"""

import hashlib
import sys
from pathlib import Path

from leaf.files import replace_files
from leaf.schema import MEDIA_DIR, MEDIA_TYPES
from leaf.service import PageTransaction

MAX_MEDIA_UPLOAD_BYTES = 10 * 1024 * 1024


class MediaUploadError(ValueError):
    """A browser upload that cannot become served page media."""


_UPLOAD_TYPES = {
    "image/gif": (".gif", lambda data: data.startswith((b"GIF87a", b"GIF89a"))),
    "image/jpeg": (".jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/png": (".png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/webp": (
        ".webp",
        lambda data: (
            len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
        ),
    ),
}


def _store_media(page_dir: Path, data: bytes, suffix: str) -> str:
    suffix = ".jpg" if suffix == ".jpeg" else suffix
    name = hashlib.sha256(data).hexdigest()[:16] + suffix
    media_dir = page_dir / MEDIA_DIR
    target = media_dir / name
    # The short digest is the public format already carried by page histories. Serialize
    # its compare-and-write with every other page transition so even a collision can
    # never change what an existing public name means.
    with PageTransaction(page_dir):
        media_dir.mkdir(exist_ok=True)
        if target.exists() or target.is_symlink():
            if (
                target.is_symlink()
                or not target.is_file()
                or target.read_bytes() != data
            ):
                raise RuntimeError(f"media digest collision at {target}")
        else:
            replace_files([(target, data, False)])
    return f"/{MEDIA_DIR}/{name}"


def store_uploaded_media(page_dir: Path, data: bytes, content_type: str) -> str:
    """Validate one browser-supplied raster image and return its canonical page path."""
    media_type = content_type.partition(";")[0].strip().lower()
    declared = _UPLOAD_TYPES.get(media_type)
    if declared is None:
        allowed = ", ".join(sorted(_UPLOAD_TYPES))
        raise MediaUploadError(f"image type must be one of: {allowed}")
    suffix, matches = declared
    if not matches(data):
        raise MediaUploadError(f"image bytes do not match {media_type}")
    return _store_media(page_dir, data, suffix)


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
    for src in files:
        if src.suffix.lower() not in MEDIA_TYPES:
            sys.exit(
                f"{src}: not an image leaf serves — {', '.join(sorted(MEDIA_TYPES))}"
            )
        data = src.read_bytes()
        path = _store_media(page_dir, data, src.suffix.lower())
        out.append((str(src), path))
    return out
