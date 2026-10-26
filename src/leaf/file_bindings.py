"""Explicit page grants for editing existing local text files.

Only the trusted CLI chooses a path; browser requests name a binding. The file
remains the authority, outside page revisions and the semantic event log. A
revision names its canonical path and exact bytes. Saves preserve LF/CRLF and
permission bits, and serialize across Leaf processes and pages through a target lock.
The comparison plus atomic replacement is not an OS compare-and-swap: an unrelated
writer which ignores this lock can still race the final comparison and replacement.
Symlinks introduced after binding are refused rather than followed to another file.

A binding the page lacks, as in a copied page or the unbound worked example, is a
designed state rather than a fault: a read answers it as no file, so the browser's
console stays clean, and only a save against it refuses. Unbinding withdraws one
grant under the same page lock as reads and saves, leaving the file itself intact.

The page's reading stamps each bound file (`bound_paths`), so the news token moves
and the page's watchers wake when a bound file does, and a state answer carries each
binding's stamp (`binding_stamps`), naming which binding moved. A stamp only prompts
a read; the read's revision decides what changed.
"""

import hashlib
import os
import re
from contextlib import contextmanager
from pathlib import Path
from stat import S_ISREG

from .files import file_stamp
from .leases import page_locked
from .locations import canonical_path
from .refusals import Refused
from .schema import FILE_BINDINGS_FILE, HTML_NAME
from .state import (
    STRING,
    Record,
    described,
    flocked,
    object_schema,
    replace_bytes,
    state_home,
)

BINDINGS = Record(
    "file-bindings",
    described(
        "The local text files a page may edit, in the page directory's `files.json`.",
        object_schema(
            {
                "bindings": described(
                    "Each binding id's file, by its canonical absolute path.",
                    {"type": "object", "additionalProperties": STRING},
                )
            }
        ),
    ),
    since=13,
)

MAX_FILE_BYTES = 256 * 1024
BINDING_ID = re.compile(HTML_NAME)


class FileBindingError(Refused):
    """A file access this page's grants do not allow, or the file refuses."""


class StaleFileError(FileBindingError):
    def __init__(self, current: dict):
        super().__init__("The file changed since this editor read it.")
        self.current = current


@contextmanager
def _access(page_dir: Path):
    """Serialize browser file access and keep OS paths out of its refusals."""
    try:
        with page_locked(page_dir):
            yield
    except OSError as error:
        reason = error.strerror or "filesystem operation failed"
        raise FileBindingError(f"Could not access the bound file: {reason}.") from error


def _bindings(page_dir: Path) -> dict:
    record = BINDINGS.read(page_dir / FILE_BINDINGS_FILE)
    return record["bindings"] if record else {}


def _validate_binding(binding: str) -> None:
    if not isinstance(binding, str) or not BINDING_ID.fullmatch(binding):
        raise FileBindingError(
            "Binding id must start with a lowercase letter and use lowercase letters, digits or -."
        )


def _target(page_dir: Path, binding: str) -> Path | None:
    _validate_binding(binding)
    bindings = _bindings(page_dir)
    if binding not in bindings:
        return None
    return Path(bindings[binding])


def bound_paths(page_dir: Path) -> dict[str, Path]:
    """Each binding's granted path, by binding.

    Read without the page lock, by the page's reading and its watchers. The trusted
    CLI writes canonical paths atomically; an unreadable grants record fails its
    read rather than disabling freshness tracking."""
    return {binding: Path(raw) for binding, raw in sorted(_bindings(page_dir).items())}


def binding_stamps(page_dir: Path) -> dict[str, str]:
    """Each binding's short token, moving whenever its path or what the filesystem
    says of the file there (`file_stamp`) does."""
    return {
        binding: hashlib.sha256(
            repr((str(path), file_stamp(path))).encode()
        ).hexdigest()[:16]
        for binding, path in bound_paths(page_dir).items()
    }


def _read(path: Path) -> bytes:
    if path.resolve() != path:
        raise FileBindingError(
            "The bound file path now contains a symlink; bind it again."
        )
    # O_NONBLOCK lets a file replaced by a FIFO refuse instead of waiting forever.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise FileBindingError("The bound path is not a regular file.")
        return stream.read(MAX_FILE_BYTES + 1)


def _snapshot(path: Path, raw: bytes) -> dict:
    """The file as the browser reads it: its name, its text with LF line endings,
    and the revision a save names."""
    if len(raw) > MAX_FILE_BYTES:
        raise FileBindingError("File exceeds the 256 KiB limit.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FileBindingError("File must be UTF-8 text.") from error
    if any(ord(char) < 32 and char not in "\t\r\n" for char in text):
        raise FileBindingError("File contains binary control characters.")
    newline = "CRLF" if "\r\n" in text else "LF"
    normalized = text.replace("\r\n", "\n")
    if "\r" in normalized or (newline == "CRLF" and "\n" in text.replace("\r\n", "")):
        raise FileBindingError("File has mixed or unsupported line endings.")
    revision = hashlib.sha256(os.fsencode(path) + b"\0" + raw).hexdigest()
    return {"label": path.name, "text": normalized, "revision": revision}


def bind_file(page_dir: Path, binding: str, file: Path) -> dict:
    """Grant this page read/write access to one existing text file, recorded by its
    canonical path (`locations.canonical_path`), the one its watchers hear about and
    every page's save of it locks, whichever spelling named it. Returns the grant:
    the binding, the path and the file's size in bytes as bound.

    The author named the path, so a path the system cannot reach or read is refused
    in the system's own words, path included. The page's own storage failing is a
    fault."""
    _validate_binding(binding)
    try:
        path = canonical_path(file.expanduser(), strict=True)
    except OSError as error:
        raise FileBindingError(str(error)) from error
    if path == (page_dir / FILE_BINDINGS_FILE).resolve():
        raise FileBindingError("A page cannot edit its own file access grants.")
    with page_locked(page_dir):
        try:
            raw = _read(path)
        except OSError as error:
            raise FileBindingError(str(error)) from error
        # Refuse a file the editor could not hold before granting it.
        _snapshot(path, raw)
        bindings = _bindings(page_dir)
        bindings[binding] = str(path)
        BINDINGS.write(page_dir / FILE_BINDINGS_FILE, {"bindings": bindings})
    return {"binding": binding, "path": str(path), "bytes": len(raw)}


def unbind_file(page_dir: Path, binding: str) -> dict:
    """Withdraw one grant, including for browser buffers read before this call."""
    _validate_binding(binding)
    with page_locked(page_dir):
        bindings = _bindings(page_dir)
        bindings.pop(binding, None)
        BINDINGS.write(page_dir / FILE_BINDINGS_FILE, {"bindings": bindings})
    return {"binding": binding, "bound": False}


def read_file(page_dir: Path, binding: str) -> dict | None:
    """Read the current file, never a cached document or browser buffer; None where
    the page binds no file under this id."""
    with _access(page_dir):
        path = _target(page_dir, binding)
        return None if path is None else _snapshot(path, _read(path))


def save_file(page_dir: Path, binding: str, posted: dict) -> dict:
    """Compare and atomically replace one file; acknowledge exactly these bytes."""
    if set(posted) != {"revision", "text"} or not all(
        isinstance(posted[name], str) for name in ("revision", "text")
    ):
        raise FileBindingError("Save requires only revision and text strings.")
    if not re.fullmatch(r"[0-9a-f]{64}", posted["revision"]):
        raise FileBindingError("Invalid file revision.")
    with _access(page_dir):
        path = _target(page_dir, binding)
        if path is None:
            raise FileBindingError(f"No file is bound as {binding!r}.")
        key = hashlib.sha256(os.fsencode(path)).hexdigest()
        locks = state_home() / "files"
        locks.mkdir(parents=True, exist_ok=True)
        with flocked(locks / f"{key}.lock"):
            before = _read(path)
            current = _snapshot(path, before)
            if posted["revision"] != current["revision"]:
                raise StaleFileError(current)
            text = posted["text"]
            if "\r" in text:
                raise FileBindingError("Editor text must use LF line endings.")
            raw = (
                text.replace("\n", "\r\n").encode()
                if b"\r\n" in before
                else text.encode()
            )
            submitted = _snapshot(path, raw)
            # Recheck path identity and contents immediately before replacement.
            latest = _snapshot(path, _read(path))
            if latest["revision"] != current["revision"]:
                raise StaleFileError(latest)
            replace_bytes([(path, raw, True)])
            return submitted
