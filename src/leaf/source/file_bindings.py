"""Explicit page grants for editing existing local text files.

Only the trusted CLI chooses a path; browser requests name a binding. The file
remains the authority, outside page revisions and the semantic event log. A
revision names its canonical path and exact bytes. Saves preserve LF/CRLF and
permission bits, and serialize across Leaf processes and pages through a target lock.
The comparison plus atomic replacement is not an OS compare-and-swap: an unrelated
writer which ignores this lock can still race the final comparison and replacement.
Symlinks introduced after binding are refused rather than followed to another file.

A file inside the page's own directory is granted by its path from there, so the
grant moves with the page: a copied page edits its own copy, and a published page's
files resolve wherever its directory is restored. Every other file is granted by its
canonical absolute path.

A binding the page lacks, as in a copied page or the unbound worked example, is a
designed state rather than a fault: a read answers it as no file, so the browser's
console stays clean, and only a save against it refuses. Unbinding withdraws one
grant under the same page lock as reads and saves, leaving the file itself intact.

The browser names each file by its label (`labels`): its path below the deepest
folder holding every file the page binds, so several files read as one tree and a
single file as its name, and no label spells out a host path.

The page's reading stamps each bound file (`bound_paths`), so the news token moves
and the page's watchers wake when a bound file does, and a state answer carries each
binding's label (`bound_files`), an unreadable file's included.

Each binding is also one of the page's data sources, read as `read_bound` reads it
(`data.file_sources`), so a widget shows the file by binding its id as it would any
source, with no editor on the page. The source's run moves with every write, which
names the binding that moved to an editor that reads the file itself.
"""

import hashlib
import os
import re
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from stat import S_ISREG

from leaf.base.files import file_stamp
from leaf.base.leases import page_locked
from leaf.base.locations import canonical_path, path_lock
from leaf.base.refusals import Refused
from leaf.base.schema import FILE_BINDINGS_FILE, HTML_NAME
from leaf.base.state import STRING, Record, described, object_schema, replace_bytes

BINDINGS = Record(
    "file-bindings",
    described(
        "The local text files a page may edit, in the page directory's `files.json`.",
        object_schema(
            {
                "bindings": described(
                    "Each binding id's file: its path from the page directory when "
                    "it lies inside it, and otherwise its canonical absolute path.",
                    {"type": "object", "additionalProperties": STRING},
                )
            }
        ),
    ),
    since=50,
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
def _pathless():
    """Refuse a failed file access in words that keep OS paths out."""
    try:
        yield
    except OSError as error:
        reason = error.strerror or "filesystem operation failed"
        raise FileBindingError(f"Could not access the bound file: {reason}.") from error


@contextmanager
def _access(page_dir: Path):
    """Serialize browser file access and keep OS paths out of its refusals."""
    with _pathless(), page_locked(page_dir):
        yield


def _grants(page_dir: Path) -> dict[str, str]:
    """The grants as `files.json` records them."""
    record = BINDINGS.read(page_dir / FILE_BINDINGS_FILE)
    return record["bindings"] if record else {}


def _validate_binding(binding: str) -> None:
    if not isinstance(binding, str) or not BINDING_ID.fullmatch(binding):
        raise FileBindingError(
            "Binding id must start with a lowercase letter and use lowercase letters, digits or -."
        )


def bound_paths(page_dir: Path) -> dict[str, Path]:
    """Each binding's granted path, by binding.

    Read without the page lock, by the page's reading and its watchers. The trusted
    CLI writes canonical paths atomically; an unreadable grants record fails its
    read rather than disabling freshness tracking."""
    grants = sorted(_grants(page_dir).items())
    # A path from the page directory resolves against where the directory is now.
    root = (
        canonical_path(page_dir)
        if any(not Path(raw).is_absolute() for _, raw in grants)
        else page_dir
    )
    return {binding: root / raw for binding, raw in grants}


def labels(paths: dict[str, Path]) -> dict[str, str]:
    """Each bound file's name in the browser: its path below the deepest folder
    holding them all. Where only the filesystem's root holds them all, the path from
    there would spell out the host's, so each takes the fewest trailing parts of its
    path that tell it from every other file the page binds. Bindings of one file share
    its name. The state answer and every read and save ask this, so its work grows
    with the files and the depth of their paths, never with their pairs."""
    if not paths:
        return {}
    folder = Path(os.path.commonpath([path.parent for path in paths.values()]))
    if folder != Path(folder.anchor):
        return {
            binding: path.relative_to(folder).as_posix()
            for binding, path in paths.items()
        }
    # How many of the page's files end in each run of trailing parts.
    endings = Counter(
        path.parts[-count:]
        for path in set(paths.values())
        for count in range(1, len(path.parts))
    )

    def trailing(path: Path) -> str:
        for count in range(1, len(path.parts)):
            if endings[path.parts[-count:]] == 1:
                return "/".join(path.parts[-count:])
        return path.name

    return {binding: trailing(path) for binding, path in paths.items()}


def bound_files(page_dir: Path) -> dict[str, dict[str, str]]:
    """Each binding's label (`labels`)."""
    return {
        binding: {"label": label}
        for binding, label in labels(bound_paths(page_dir)).items()
    }


def granted_files(page_dir: Path) -> dict[str, dict[str, str]]:
    """Each binding's label, the name the page shows for it (`labels`), and the path
    it grants, for the agent: `leaf page state` reports them under the served state's
    name, `files`, with the path the browser never gets."""
    paths = bound_paths(page_dir)
    named = labels(paths)
    return {
        binding: {"label": named[binding], "path": str(path)}
        for binding, path in paths.items()
    }


def _target(page_dir: Path, binding: str) -> tuple[Path, str] | None:
    """The binding's file and label, or None where the page binds no such file."""
    _validate_binding(binding)
    paths = bound_paths(page_dir)
    if binding not in paths:
        return None
    return paths[binding], labels(paths)[binding]


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


def _snapshot(path: Path, raw: bytes, label: str) -> dict:
    """The file as the browser reads it: its label, its text with LF line endings,
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
    return {"label": label, "text": normalized, "revision": revision}


def bind_file(page_dir: Path, binding: str, file: Path) -> dict:
    """Grant this page read/write access to one existing text file, by its canonical
    path (`locations.canonical_path`), the one its watchers hear about and every
    page's save of it locks, whichever spelling named it. Returns the grant: the
    binding, the path, the label the browser shows for it and the file's size in
    bytes as bound.

    The author named the path, so a path the system cannot reach or read is refused
    in the system's own words, path included. The page's own storage failing is a
    fault."""
    _validate_binding(binding)
    try:
        path = canonical_path(file.expanduser(), strict=True)
    except OSError as error:
        raise FileBindingError(str(error)) from error
    if path == BINDINGS.file(page_dir / FILE_BINDINGS_FILE).resolve():
        raise FileBindingError("A page cannot edit its own file access grants.")
    with page_locked(page_dir):
        try:
            raw = _read(path)
        except OSError as error:
            raise FileBindingError(str(error)) from error
        # Refuse a file the editor could not hold before granting it.
        _snapshot(path, raw, path.name)
        root = canonical_path(page_dir)
        grants = _grants(page_dir)
        grants[binding] = str(
            path.relative_to(root) if path.is_relative_to(root) else path
        )
        BINDINGS.write(page_dir / FILE_BINDINGS_FILE, {"bindings": grants})
        label = labels(bound_paths(page_dir))[binding]
    return {"binding": binding, "path": str(path), "label": label, "bytes": len(raw)}


def unbind_file(page_dir: Path, binding: str) -> dict:
    """Withdraw one grant, including for browser buffers read before this call. The
    user withdraws it from every Leaf, so the records a Leaf of another shape keeps
    go whole, since this Leaf can't read which grants they hold (`state.Record`)."""
    _validate_binding(binding)
    with page_locked(page_dir):
        grants = _grants(page_dir)
        grants.pop(binding, None)
        BINDINGS.write(page_dir / FILE_BINDINGS_FILE, {"bindings": grants})
        for other in BINDINGS.others(page_dir / FILE_BINDINGS_FILE):
            other.unlink(missing_ok=True)
    return {"binding": binding, "bound": False}


def observed(path: Path):
    """What the page knows of a bound file without reading it, which its news
    (`page_inputs`), the cache of its source and the source's run (`data.file_sources`)
    all read: its stamp (`file_stamp`) and its change time. The change time moves with
    a change to the file's permissions, and with a rewrite that puts back the
    modification time and size it had, neither of which moves the stamp. The stamp
    leaves it out because Leaf's hard links of a revision's files move it, where
    nothing links a bound file. None where nothing is there."""
    stamp = file_stamp(path)
    try:
        return None if stamp is None else (stamp, path.stat().st_ctime_ns)
    except OSError:
        return None


def read_bound(path: Path, label: str) -> tuple[dict, float]:
    """The file at `path`, one `bound_paths` gives, as `read_file` reads it, and when it
    was last written, as a POSIX time. It takes no page lock, as the page's reading
    reads the grants without one (`data.read_data`): a save replaces the file whole, so
    a read sees one version or the other."""
    with _pathless():
        written = path.stat().st_mtime
        return _snapshot(path, _read(path), label), written


def read_file(page_dir: Path, binding: str) -> dict | None:
    """Read the current file, never a cached document or browser buffer; None where
    the page binds no file under this id."""
    with _access(page_dir):
        target = _target(page_dir, binding)
        if target is None:
            return None
        path, label = target
        return _snapshot(path, _read(path), label)


def save_file(page_dir: Path, binding: str, posted: dict) -> dict:
    """Compare and atomically replace one file; acknowledge exactly these bytes."""
    if set(posted) != {"revision", "text"} or not all(
        isinstance(posted[name], str) for name in ("revision", "text")
    ):
        raise FileBindingError("Save requires only revision and text strings.")
    if not re.fullmatch(r"[0-9a-f]{64}", posted["revision"]):
        raise FileBindingError("Invalid file revision.")
    with _access(page_dir):
        target = _target(page_dir, binding)
        if target is None:
            raise FileBindingError(f"No file is bound as {binding!r}.")
        path, label = target
        with path_lock(path):
            before = _read(path)
            current = _snapshot(path, before, label)
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
            submitted = _snapshot(path, raw, label)
            # Recheck path identity and contents immediately before replacement.
            latest = _snapshot(path, _read(path), label)
            if latest["revision"] != current["revision"]:
                raise StaleFileError(latest)
            replace_bytes([(path, raw, True)])
            return submitted
