"""Dependency-free machine storage and the session lifecycle authority.

The standalone SessionEnd entry runs on system Python 3.9 without a managed
Leaf environment. One atomic record owns harness lifetime, generation, turn identity
and dated opening/ending evidence. Claims reference its generation; an ending
invalidates them without page discovery, page locks or claim rewrites.

The session lock also serializes Codex delivery route reservation, making its
revision a compare-and-swap token for observations. Lock order is page then
session. Session transitions never acquire page locks or call an external harness;
only short state publications and reservations run under the session lock.
Storage replacement and cross-process locking are shared below the page model.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import secrets
import sys
from datetime import datetime
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - unsupported non-POSIX platform
    fcntl = None

EVENTS_FILE = "events.jsonl"


def state_home_path() -> Path:
    root = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(root) / "leaf"


# A session's files that end with it: hook capability and turn observations,
# and its page servers' log of the thread titles they asked for.
HOOKS_SUFFIX = "hooks"
STEP_HOOK_SUFFIX = "step-hook"
SESSION_SUFFIX = "lifecycle"
TITLES_SUFFIX = "titles.log"


def session_file(session_id: str, suffix: str) -> Path:
    """One state-home file belonging to a single harness session.

    A harness's session id is not a filename, so the session is named by a digest of
    it. Every file one session owns — its leases and their locks, and a
    Codex task's deliveries and adapter log — is that one name with a different
    suffix, in the state home's `sessions/`.
    """
    key = hashlib.sha256(session_id.encode()).hexdigest()[:32]
    return state_home_path() / "sessions" / f"{key}.{suffix}"


def page_key(page_dir: Path) -> str:
    """A filesystem-safe identity for state held outside one page directory."""
    return hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()


def require_cross_process_locking() -> None:
    """Refuse every writer/server path on a host without the log's lock."""
    if fcntl is None:
        raise RuntimeError(
            "leaf requires POSIX cross-process file locking; this platform has no fcntl"
        )


@contextlib.contextmanager
def flocked(path: Path):
    """An exclusive lock held while the block runs — the one serialization
    primitive here. The log serializes appends, cursor and status updates, and
    claim and delivery transitions. Stable purpose locks serialize contract or service
    transitions; a `.lock` beside a registry of JSON files serializes updates
    to them, since the files themselves are replaced by rename and a lock on a
    replaced inode holds nothing.

    The event log is the successful-init marker as well as a lease. A transaction
    racing page deletion must not recreate it and turn a deleted directory back into
    an initialized page, so it is opened, never created, and it outlives the lock.

    A purpose lock's file is created on first use and remains after release.
    The block's end unlocks it before closing, since a subprocess another thread
    starts meanwhile holds a copy of the descriptor until its exec, and closing
    alone would keep the next taker waiting on that child (`release_lease`).
    Every acquired descriptor is checked
    against its path, since a shared-path replacement while a taker waits must
    never let it enter a transaction on an inode other takers can no longer find.
    This also covers a page replaced with a new event log."""
    require_cross_process_locking()
    mode = "r+b" if path.name == EVENTS_FILE else "a+b"
    while True:
        with open(path, mode) as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            if still_named(f.fileno(), path):
                try:
                    yield f
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
                return


def still_named(held: int, path: Path) -> bool:
    """Whether PATH still names the file the descriptor HELD was opened on.

    A shared path can change while a taker waits. Checking after acquisition lets
    it retry on the currently named inode before entering its transaction."""
    try:
        return os.path.samestat(os.fstat(held), os.stat(path))
    except FileNotFoundError:
        return False


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def fsync_parents(paths) -> None:
    """Make these files' directory entries durable, not just their contents.

    A create or a rename is a directory write, and it survives a crash only once
    the directory itself is synced, so every writer that adds or replaces a page
    or package member ends with this.
    """
    for parent in {path.parent for path in paths}:
        fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def replace_bytes(writes: list) -> None:
    """Durably stage bytes before replacing their targets.

    Each write is (target, bytes, preserve_mode). The higher file boundary validates
    target identity before a multi-file replacement; a single JSON write needs no
    comparison. A caller resolving a symlink decides its target before entering.
    """
    staged = []
    try:
        for target, data, preserve_mode in writes:
            for _ in range(100):
                tmp = target.with_name(f".{secrets.token_hex(8)}.tmp")
                try:
                    fd = os.open(
                        tmp,
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | getattr(os, "O_BINARY", 0),
                        0o666,
                    )
                    break
                except FileExistsError:
                    continue
            else:  # pragma: no cover - 64 random bits collided 100 times
                raise FileExistsError(f"could not reserve a temp file beside {target}")
            staged.append((tmp, target))
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                if preserve_mode:
                    try:
                        os.fchmod(stream.fileno(), target.stat().st_mode & 0o777)
                    except FileNotFoundError:
                        pass  # no target to preserve a mode from
                stream.flush()
                os.fsync(stream.fileno())
        for tmp, target in staged:
            os.replace(tmp, target)
        fsync_parents(target for target, _data, _mode in writes)
    finally:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)


def json_bytes(obj, *, indent=None) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=indent) + "\n").encode()


def write_json(path: Path, obj) -> None:
    """Atomically replace a state record, preserving a regular target's mode."""
    replace_bytes([(path, json_bytes(obj), not path.is_symlink())])


SESSION_FIELDS = {
    "id",
    "generation",
    "ended",
    "turn",
    "turn_opened",
    "turn_closed",
    "revision",
    "provider",
    "lifetime",
}


def session_lock_path(session_id: str) -> Path:
    path = session_file(session_id, "delivery.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def session_record(session_id: str) -> dict | None:
    """Read one atomic lifecycle publication; incompatible records are absent."""
    try:
        record = json.loads(session_file(session_id, SESSION_SUFFIX).read_text())
    except (FileNotFoundError, ValueError):
        return None
    return (
        record if isinstance(record, dict) and SESSION_FIELDS <= record.keys() else None
    )


def write_session(record: dict) -> dict:
    record = {**record, "revision": record["revision"] + 1}
    path = session_file(record["id"], SESSION_SUFFIX)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, record)
    return record


def new_session(session_id: str, lifetime: dict) -> dict:
    return {
        "id": session_id,
        "generation": secrets.token_hex(16),
        "ended": None,
        "turn": None,
        "turn_opened": None,
        "turn_closed": None,
        "revision": 0,
        "provider": False,
        "lifetime": lifetime,
    }


def ensure_session(session_id: str, lifetime: dict) -> dict:
    """Claim into the active generation, or create a new lifetime after ending.

    Lifetime provenance is shared, while an activity-backed page's freshness is
    its own claim timestamp and files. No page read occurs under this lock.
    """
    with flocked(session_lock_path(session_id)):
        record = session_record(session_id)
        if record is None or record["ended"] is not None:
            record = new_session(session_id, lifetime)
            record.update(turn=secrets.token_hex(8), turn_opened=now_iso())
        elif record["lifetime"] == lifetime:
            return record
        elif not record["lifetime"]:
            record = {**record, "lifetime": lifetime}
        else:
            record = new_session(session_id, lifetime)
            record.update(turn=secrets.token_hex(8), turn_opened=now_iso())
        return write_session(record)


def renew_turn(record: dict) -> dict:
    """Renew a trusted prompt/tool observation under the caller's session lock."""
    return write_session({**record, "turn_opened": now_iso(), "turn_closed": None})


def advance_turn(session_id: str, turn_id: str | None, *, running: bool) -> dict | None:
    """Publish a turn observation under the caller's session lock.

    A closed provider identity never reopens. Unknown-id harnesses reuse their open
    turn and mint a new identity after its ending. Callback callers validate the
    existing identity before calling this; prompts and guarded provider starts
    are the only boundaries that introduce a known replacement.
    """
    record = session_record(session_id)
    if record is None:
        record = new_session(session_id, {})
    if record["ended"] is not None:
        return None
    if running:
        provider = turn_id is not None or record["provider"]
        if turn_id is None:
            turn_id = record["turn"] if record["turn_closed"] is None else None
            turn_id = turn_id or secrets.token_hex(8)
        if turn_id == record["turn"]:
            return record
        record = {
            **record,
            "turn": turn_id,
            "turn_opened": now_iso(),
            "turn_closed": None,
            "provider": provider,
        }
    else:
        if turn_id is not None and turn_id != record["turn"]:
            return None
        record = {**record, "turn_closed": now_iso()}
    return write_session(record)


def open_session_turn(session_id: str, turn_id: str | None = None) -> dict | None:
    with flocked(session_lock_path(session_id)):
        record = session_record(session_id)
        if record is not None and (
            record["ended"] is not None
            or (record["provider"] and record["turn_closed"] is not None)
        ):
            # A late consumer/callback cannot restart a known provider turn.
            return None
        if (
            record
            and turn_id is not None
            and (
                (record["provider"] and record["turn"] != turn_id)
                or (record["turn"] == turn_id and record["turn_closed"] is not None)
            )
        ):
            return None
        return advance_turn(session_id, turn_id, running=True)


def start_session_turn(
    session_id: str, turn_id: str, expected: dict | None
) -> dict | None:
    """Adopt a provider start result only if its request still owns this epoch."""
    with flocked(session_lock_path(session_id)):
        current = session_record(session_id)
        if (
            current
            and current["provider"]
            and current["turn"] == turn_id
            and current["turn_closed"] is not None
        ):
            return None
        if current != expected:
            # The provider may run its synchronous prompt hook before replying
            # to turn/start. That exact publication is the successful adoption,
            # not a competing turn; no identity or revision is rewritten here.
            if (
                current
                and expected
                and current["generation"] == expected["generation"]
                and current["ended"] is None
                and current["provider"]
                and current["turn"] == turn_id
            ):
                return current
            return None
        return advance_turn(session_id, turn_id, running=True)


def prompt_turn(session_id: str, turn_id: str | None = None) -> dict | None:
    """A synchronous prompt starts/resumes the harness's generation before claims."""
    with flocked(session_lock_path(session_id)):
        record = session_record(session_id)
        if record is not None and record["ended"] is not None:
            write_session(new_session(session_id, {}))
        record = session_record(session_id)
        if (
            record
            and turn_id is not None
            and turn_id == record["turn"]
            and record["turn_closed"] is not None
        ):
            return None
        if record and (
            turn_id == record["turn"]
            or (turn_id is None and record["turn_closed"] is None)
        ):
            return renew_turn(record)
        return advance_turn(session_id, turn_id, running=True)


def close_session_turn(
    session_id: str, turn_id: str | None = None, *, expected: dict | None | object = ...
) -> bool:
    with flocked(session_lock_path(session_id)):
        record = session_record(session_id)
        if (
            record is None
            or record["ended"] is not None
            or (expected is not ... and record != expected)
        ):
            return False
        return advance_turn(session_id, turn_id, running=False) is not None


def end_session(session_id: str) -> None:
    """End one generation with no page discovery or page-lock acquisition.

    Claims referencing it become inactive by this one atomic write. A later
    synchronous prompt or claim creates a new generation and cannot revive them.
    Capability files are observations, not lifecycle authority, and retire here.
    """
    if not session_id:
        return
    with flocked(session_lock_path(session_id)):
        record = session_record(session_id) or new_session(session_id, {})
        ended = now_iso()
        write_session({**record, "ended": ended, "turn_closed": ended})
        for suffix in (HOOKS_SUFFIX, STEP_HOOK_SUFFIX, TITLES_SUFFIX):
            session_file(session_id, suffix).unlink(missing_ok=True)


def main() -> None:
    payload = json.load(sys.stdin)
    if payload.get("hook_event_name") == "SessionEnd":
        end_session(payload.get("session_id") or "")


if __name__ == "__main__":
    main()
