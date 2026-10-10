"""Explicit page grants for editing existing local text files.

Only the trusted CLI chooses a path; browser requests name a binding. The file
remains the authority, outside page revisions and the semantic event log. A
revision names its canonical path and exact bytes. Saves preserve LF/CRLF and
permission bits, and serialize across Leaf processes and pages through a target lock.
The comparison plus atomic replacement is not an OS compare-and-swap: an unrelated
writer which ignores this lock can still race the final comparison and replacement.
Symlinks introduced after binding are refused rather than followed to another file.
"""

import hashlib
import os
import re
from contextlib import contextmanager
from pathlib import Path
from stat import S_ISREG

from .files import read_json
from .leases import page_locked
from .schema import FILE_BINDINGS_FILE, HTML_NAME
from .state import flocked, replace_bytes, state_home_path, write_json

MAX_FILE_BYTES = 256 * 1024
BINDING_ID = re.compile(HTML_NAME)


class FileBindingError(ValueError):
    """An expected refusal, suitable for a CLI or HTTP response."""


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
    record = read_json(page_dir / FILE_BINDINGS_FILE)
    if record is None:
        return {}
    if not isinstance(record, dict) or not isinstance(record.get("bindings"), dict):
        raise FileBindingError("Invalid file bindings; bind the file again.")
    return record["bindings"]


def _target(page_dir: Path, binding: str) -> Path:
    if not isinstance(binding, str) or not BINDING_ID.fullmatch(binding):
        raise FileBindingError("Invalid file binding id.")
    raw = _bindings(page_dir).get(binding)
    if not isinstance(raw, str) or not Path(raw).is_absolute():
        raise FileBindingError(f"No file is bound as {binding!r}.")
    return Path(raw)


def _read(path: Path) -> dict:
    if path.resolve() != path:
        raise FileBindingError(
            "The bound file path now contains a symlink; bind it again."
        )
    # O_NONBLOCK lets a file replaced by a FIFO refuse instead of waiting forever.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise FileBindingError("The bound path is not a regular file.")
        raw = stream.read(MAX_FILE_BYTES + 1)
    return _snapshot(path, raw)


def _snapshot(path: Path, raw: bytes) -> dict:
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
    return {
        "label": path.name,
        "text": normalized,
        "revision": revision,
        "newline": newline,
        "bytes": len(raw),
    }


def bind_file(page_dir: Path, binding: str, file: Path) -> dict:
    """Grant this page read/write access to one existing canonical text path."""
    if not BINDING_ID.fullmatch(binding):
        raise FileBindingError(
            "Binding id must start with a lowercase letter and use lowercase letters, digits or -."
        )
    path = file.expanduser().resolve(strict=True)
    if path == (page_dir / FILE_BINDINGS_FILE).resolve():
        raise FileBindingError("A page cannot edit its own file access grants.")
    with page_locked(page_dir):
        snapshot = _read(path)
        bindings = _bindings(page_dir)
        bindings[binding] = str(path)
        write_json(page_dir / FILE_BINDINGS_FILE, {"bindings": bindings})
    return snapshot


def read_file(page_dir: Path, binding: str) -> dict:
    """Read the current file, never a cached document or browser buffer."""
    with _access(page_dir):
        return _read(_target(page_dir, binding))


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
        key = hashlib.sha256(os.fsencode(path)).hexdigest()
        locks = state_home_path() / "files"
        locks.mkdir(parents=True, exist_ok=True)
        with flocked(locks / f"{key}.lock"):
            current = _read(path)
            if posted["revision"] != current["revision"]:
                raise StaleFileError(current)
            text = posted["text"]
            if "\r" in text:
                raise FileBindingError("Editor text must use LF line endings.")
            raw = (
                text.replace("\n", "\r\n").encode()
                if current["newline"] == "CRLF"
                else text.encode()
            )
            submitted = _snapshot(path, raw)
            # Recheck path identity and contents immediately before replacement.
            latest = _read(path)
            if latest["revision"] != current["revision"]:
                raise StaleFileError(latest)
            replace_bytes([(path, raw, True)])
            return submitted
