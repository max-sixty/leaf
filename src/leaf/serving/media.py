"""Content-addressed page media ingestion.

Page authors and users enter through different trust boundaries. ``page media``
accepts a local file the author chose; the browser upload door accepts untrusted bytes
and therefore derives the extension from a small raster MIME vocabulary and verifies
its file signature before both paths meet at the same content-addressed writer.
"""

import hashlib
from pathlib import Path

from leaf.base.files import replace_files
from leaf.base.refusals import Refused
from leaf.base.schema import MEDIA_DIGEST, MEDIA_DIR, MEDIA_TYPES
from leaf.records.transaction import PageTransaction

MAX_MEDIA_UPLOAD_BYTES = 10 * 1024 * 1024


class MediaUploadError(Refused):
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


def media_name(data: bytes, suffix: str) -> str:
    """The one name a page's media directory gives these bytes (`schema.MEDIA_DIGEST`).

    A caller that needs media's public path before the page holds it — the site
    build naming a social image it has already published — derives it here rather
    than restating the digest rule. `suffix` is the source file's, in any case.
    """
    return hashlib.sha256(data).hexdigest()[:MEDIA_DIGEST] + suffix.lower()


def write_media(directory: Path, data: bytes, suffix: str) -> str:
    """Write `data` into the media directory `directory` under its name
    (`media_name`), unless it holds them already, and return the name. A name that
    holds other bytes is a digest collision, refused. A page's own media goes through
    `cmd_media`, which serializes this with the page's other transitions."""
    name = media_name(data, suffix)
    target = directory / name
    directory.mkdir(exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file() or target.read_bytes() != data:
            raise RuntimeError(f"media digest collision at {target}")
    else:
        replace_files([(target, data, False)])
    return name


def require_media_type(path: Path) -> None:
    """Refuse `path` unless its suffix is a media type Leaf serves."""
    if path.suffix.lower() not in MEDIA_TYPES:
        raise Refused(
            f"{path}: not a media type leaf serves — {', '.join(sorted(MEDIA_TYPES))}"
        )


def _store_media(page_dir: Path, data: bytes, suffix: str) -> str:
    # The short digest is the public format already carried by page histories. Serialize
    # its compare-and-write with every other page transition so even a collision can
    # never change what an existing public name means.
    with PageTransaction(page_dir):
        name = write_media(page_dir / MEDIA_DIR, data, suffix)
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


def cmd_media(page_dir: Path, files: list) -> list[dict]:
    """Copy media into the page's media directory, named by the hash of their
    bytes; returns each file's page `path` and its `source`, in the order given.

    Content-addressing is doing two jobs. It keeps the directory's promise —
    a name can only ever mean one set of bytes, so a version the user
    approved shows them the same media forever. And it de-duplicates for free: a
    version that
    re-shows last version's screenshot re-uses the file rather than a second
    copy of it, which is what makes the version history cheap to keep."""
    out = []
    for src in files:
        require_media_type(src)
        data = src.read_bytes()
        path = _store_media(page_dir, data, src.suffix)
        out.append({"path": path, "source": str(src)})
    return out
