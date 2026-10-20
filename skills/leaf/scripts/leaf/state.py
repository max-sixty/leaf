"""Dependency-free machine storage, the persisted record (`Record`), and the
session lifecycle authority.

The standalone SessionEnd entry runs on system Python 3.9 without a managed
Leaf environment. One atomic record owns harness lifetime, generation, turn identity
and dated opening/ending evidence. Claims reference its generation; ending the
generation invalidates them without page discovery, page locks or claim rewrites.
Desktop instance unloading closes observations while retaining chat ownership.
A session's end removes the files nothing will read again (`_retire`).

The session lock also serializes Codex transport reservation, making its
revision a compare-and-swap token for observations. Lock order is page then
session. Session transitions never acquire page locks or call an external harness;
only short state publications and reservations run under the session lock.
Storage replacement and cross-process locking are shared below the page model.
"""

from __future__ import annotations

import contextlib
import fcntl
import functools
import hashlib
import json
import os
import secrets
import stat
import sys
import time
from datetime import datetime
from pathlib import Path

EVENTS_FILE = "events.jsonl"


def state_home() -> Path:
    """$XDG_STATE_HOME/leaf (~/.local/state/leaf/) — pages/ holds page
    directories by convention, claims/ the last claimant of every known page,
    sessions/ the live watcher leases, packages/ the packages `package install` copied here,
    screens/ the last render check's screens of each page, pictures/ the
    pictures `page picture` drew of its drawing comments, and access.json
    the one key every page here is served with (`server.host_key`), beside the
    access.lock its first mint takes. State, not config: claim records carry pids
    and absolute paths, while page service records carry ports, so this state is
    bound to this machine, as is the key that reaches it.

    Owner-only: the key is what stands between another local user and a log that
    outranks the document, and a 0644 file under a traversable path hands it to
    anyone on a shared machine. Every path into the state home resolves through
    this call, which creates the home 0700 and returns an existing one to 0700, so
    the mode holds whichever Leaf or tool made the directory."""
    root = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    home = Path(root) / "leaf"
    if not home.is_dir():
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
    hold_mode(home, 0o700)
    return home


def hold_mode(path: Path, mode: int) -> None:
    """Give `path` exactly the permission bits `mode`, writing only when they
    differ, so a reader confined to reads, such as a sandboxed command, can still
    resolve a path whose mode already holds."""
    if stat.S_IMODE(path.stat().st_mode) != mode:
        path.chmod(mode)


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
    return state_home() / "sessions" / f"{key}.{suffix}"


def page_key(page_dir: Path) -> str:
    """A filesystem-safe identity for state held outside one page directory."""
    return hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()


@contextlib.contextmanager
def flocked(path: Path, *, deadline: float | None = None):
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
    This also covers a page replaced with a new event log.

    A `deadline`, a `time.monotonic()` reading, bounds the wait: a lock not taken
    by then raises TimeoutError, for a taker that must finish by a harness's
    deadline more than it must take the lock."""
    mode = "r+b" if path.name == EVENTS_FILE else "a+b"
    while True:
        with open(path, mode) as f:
            acquire(f, path, deadline)
            if still_named(f.fileno(), path):
                try:
                    yield f
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
                return


def acquire(f, path: Path, deadline: float | None) -> None:
    """Take `f`'s exclusive lock before `deadline` where one is given
    (`flocked`); a deadline already past takes no lock at all."""
    if deadline is None:
        fcntl.flock(f, fcntl.LOCK_EX)
        return
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"{path} could not be acquired before the deadline")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            time.sleep(0.01)


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
    Preserved modes include special permission bits. Apply them after flushing all
    data, since writing can clear set-user-ID and set-group-ID bits on POSIX files.
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
                stream.flush()
                if preserve_mode:
                    try:
                        os.fchmod(stream.fileno(), stat.S_IMODE(target.stat().st_mode))
                    except FileNotFoundError:
                        pass  # no target to preserve a mode from
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
    """Atomically replace a JSON file, preserving a regular target's mode."""
    replace_bytes([(path, json_bytes(obj), not path.is_symlink())])


@functools.cache
def kernel_registry() -> dict:
    """The running Leaf's shipped registry, whose `$events` state its page protocol
    (`registry.kernel`)."""
    path = Path(__file__).resolve().parents[2] / "assets" / "registry.json"
    return json.loads(path.read_text(encoding="utf-8"))


# Every declared `Record` by its kind, which names one shape.
RECORDS: dict = {}


class Record:
    """One kind of JSON object Leaf keeps outside a page's log and document, such as
    a page's status, a claim or a session's lifecycle.

    Each kind is declared once, beside the module that owns it, whose functions are
    its only writers, and `schema` declares the object. Objects stay open, so a
    field another Leaf adds leaves a record readable. Leaf alone writes these files,
    and the hooks that read several of them must not load a schema engine, so
    nothing validates a record whole while Leaf runs; the suite checks every record
    a test writes against its schema instead (`tests/conftest.py`).

    Every installed Leaf on the machine shares the state home, any of them may serve
    a page, and the worktrees writing them are each on their own commit. So a record
    carries `format`, `leaf-<kind>/<since>`, where `since` is the page protocol at
    which this kind's shape last changed, so a bump for anything else leaves the
    record readable (`layer-registry.md`, "Page protocol", says when `since`
    moves, which the browser build checks against every kind in `RECORDS`). `read`
    takes only a record at this format that has every field this Leaf's schema
    requires, at each level of its declared objects. Any other
    record another Leaf wrote, at another format or with none, or one written before
    a field was added, reads as absent, as a missing file does, and the next write
    replaces it. Every write replaces the file whole, so a file that is not JSON no
    Leaf wrote, and reading it raises, naming the file."""

    def __init__(self, kind: str, schema: dict, *, since: int):
        if kind in RECORDS:
            raise ValueError(f"two records declare the kind {kind}")
        RECORDS[kind] = self
        self.kind = kind
        self.schema = schema
        self.since = since

    @property
    def format(self) -> str:
        return f"leaf-{self.kind}/{self.since}"

    def read(self, path: Path) -> dict | None:
        """The record at `path`, less its `format`, or None where this Leaf reads
        none there."""
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        try:
            stored = json.loads(text)
        except ValueError as error:
            raise ValueError(f"{path} is not a JSON record: {error}") from error
        if (
            not isinstance(stored, dict)
            or stored.pop("format", None) != self.format
            or not _complete(self.schema, stored)
        ):
            return None
        return stored

    def stored(self, value: dict) -> dict:
        """`value` as `write` stores it, led by its `format`."""
        return {"format": self.format} | {
            name: item for name, item in value.items() if name != "format"
        }

    def encode(self, value: dict) -> bytes:
        """The bytes `write` writes, for a writer that replaces several files at
        once or writes through a lease it holds."""
        return json_bytes(self.stored(value))

    def write(self, path: Path, value: dict) -> dict:
        """Atomically replace the record at `path`, preserving a regular target's
        mode, and return `value` as `read` will."""
        replace_bytes([(path, self.encode(value), not path.is_symlink())])
        return value


def _complete(schema: dict, value) -> bool:
    """Whether `value` has each field `schema` requires, and so does every object
    within it that the schema declares: through properties, maps and arrays, and
    through each `allOf` clause, a conditional one where its `if` names, by `enum`
    or `const`, the values `value` holds. Types and values are the writers' to hold
    (`tests/conftest.py`)."""
    if isinstance(value, list):
        return all(_complete(schema.get("items", {}), item) for item in value)
    if not isinstance(value, dict):
        return True
    properties = schema.get("properties", {})
    others = schema.get("additionalProperties")
    return (
        set(schema.get("required", ())) <= value.keys()
        and all(
            _complete(properties[name], item)
            if name in properties
            else not isinstance(others, dict) or _complete(others, item)
            for name, item in value.items()
        )
        and all(_clause_complete(clause, value) for clause in schema.get("allOf", ()))
    )


def _clause_complete(clause: dict, value: dict) -> bool:
    if "if" not in clause:
        return _complete(clause, value)
    applies = all(
        name in value and value[name] in declared.get("enum", [declared.get("const")])
        for name, declared in clause["if"].get("properties", {}).items()
    )
    return not applies or _complete(clause.get("then", {}), value)


def object_schema(required: dict, optional: dict | None = None) -> dict:
    """The JSON Schema of an open object with these properties, each in `required`
    required."""
    return {
        "type": "object",
        "properties": {**required, **(optional or {})},
        "required": list(required),
    }


STRING = {"type": "string"}
TIME = {"type": "string", "format": "date-time"}
_TIME_OR_NONE = {"anyOf": [{"type": "null"}, TIME]}
SESSION = Record(
    "session",
    object_schema(
        {
            "id": STRING,
            # Replaced when a claim made before can no longer name this lifetime.
            "generation": STRING,
            "ended": _TIME_OR_NONE,
            "turn": {"type": ["string", "null"]},
            "turn_opened": _TIME_OR_NONE,
            "turn_closed": _TIME_OR_NONE,
            "revision": {"type": "integer", "minimum": 1},
            # Whether the harness, rather than Leaf, names the turn.
            "provider": {"type": "boolean"},
            # What keeps the session alive (`Harness.lifetime`).
            "lifetime": {"type": "object"},
        },
        # The native chat a desktop Codex lifetime stands on (`chat_exists`).
        {"transcript_path": STRING},
    ),
    since=13,
)


def session_lock_path(session_id: str) -> Path:
    path = session_file(session_id, "delivery.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def session_record(session_id: str) -> dict | None:
    """The session's lifecycle, or None for a session this Leaf has no record of."""
    return SESSION.read(session_file(session_id, SESSION_SUFFIX))


def write_session(record: dict) -> dict:
    path = session_file(record["id"], SESSION_SUFFIX)
    path.parent.mkdir(parents=True, exist_ok=True)
    return SESSION.write(path, {**record, "revision": record["revision"] + 1})


def chat_exists(record: dict | None) -> bool:
    """Whether the native chat source validated by its hooks still exists.

    The canonical session record owns the source path; lifetime stores only the
    kind of owner. Codex preserves that source across instance unloads, moves it
    on archive and removes it on delete. Missing source evidence owns nothing.
    """
    source = record.get("transcript_path") if record else None
    return source is not None and Path(source).is_file()


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

    Lifetime provenance is shared; native transcript evidence already published
    by a prompt is retained when the first page establishes its lifetime.
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


def advance_turn(
    session_id: str,
    turn_id: str | None,
    *,
    running: bool,
    observed_at: str | None = None,
) -> dict | None:
    """Publish a turn observation under the caller's session lock.

    A closed provider identity never reopens. Unknown-id harnesses reuse their open
    turn and mint a new identity after its ending. Callback callers validate the
    existing identity before calling this; prompts and guarded provider starts
    introduce a known replacement. A provider transcript observation supplies
    its own timestamp so reading old evidence does not renew its lifetime.
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
            "turn_opened": observed_at or now_iso(),
            "turn_closed": None,
            "provider": provider,
        }
    else:
        if turn_id is not None and turn_id != record["turn"]:
            return None
        record = {**record, "turn_closed": observed_at or now_iso()}
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
            # The provider may run its synchronous prompt hook before Leaf reads
            # the turn's start. That exact publication is the successful adoption,
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
    session_id: str,
    turn_id: str | None = None,
    *,
    expected: dict | None | object = ...,
    ended_at: float | None = None,
) -> bool:
    """Close the session's turn. `ended_at` is when the harness saw the turn end, in
    POSIX seconds, for a close that reaches here later: a turn a prompt opened or
    renewed since then is a newer one, which an unnamed close must not end."""
    with flocked(session_lock_path(session_id)):
        record = session_record(session_id)
        if (
            record is None
            or record["ended"] is not None
            or (expected is not ... and record != expected)
            or (
                ended_at is not None
                and record["turn_opened"] is not None
                and datetime.fromisoformat(record["turn_opened"]).timestamp() > ended_at
            )
        ):
            return False
        return advance_turn(session_id, turn_id, running=False) is not None


def end_session(session_id: str) -> None:
    """End one generation with no page discovery or page-lock acquisition.

    Claims referencing it become inactive by this one atomic write. A later
    synchronous prompt or claim creates a new generation and cannot revive them,
    though while that generation runs the session may still record on such a page
    what its task took or answered there (`service.claim_names_session`).
    Capability files are observations, not lifecycle authority, and retire here.
    A session that left no file, as most sessions of a harness Leaf is installed
    in never use it, has nothing to end and is left without one.
    """
    if not session_id or not _session_paths(session_id):
        return
    with flocked(session_lock_path(session_id)):
        _end_session(session_id)


def _end_session(session_id: str) -> None:
    """Publish the ending while the caller holds the session lock."""
    if record := session_record(session_id):
        ended = now_iso()
        write_session({**record, "ended": ended, "turn_closed": ended})
    _retire(session_id)


def _session_paths(session_id: str) -> list[Path]:
    """Every file and directory in the state home's `sessions/` that belongs to the
    session (`session_file`)."""
    pattern = session_file(session_id, "*")
    return list(pattern.parent.glob(pattern.name))


def _retire(session_id: str) -> None:
    """Remove what an ended session no longer needs, under its lock.

    The records a claim naming the session reads stay, since a claim can name it
    again after its end: a failed takeover restores the claim it replaced
    (`service.restore_page_claim`). Its page shows the session's turn from the
    lifecycle, and a resumed session's hooks read its reconnect notices
    (`session-lifetime.md`, "Reconnect notices"). While a claim names the session,
    only the observations that end with it go. Once none does, each other file goes
    that no process holds a lock on, such as a wait lease of a watch still running:
    a lease taker checks the name it locked (`leases.take_lease`), so none starts on
    a file removed under it. Directories, such as a Codex task's delivery records,
    are their owner's to retire."""
    if holds_claims(session_id):
        for suffix in (HOOKS_SUFFIX, STEP_HOOK_SUFFIX, TITLES_SUFFIX):
            session_file(session_id, suffix).unlink(missing_ok=True)
        return
    kept = {session_file(session_id, SESSION_SUFFIX), session_lock_path(session_id)}
    for path in _session_paths(session_id):
        if path not in kept and path.suffix != ".reconnect" and not path.is_dir():
            _unlink_unheld(path)


def _unlink_unheld(path: Path) -> None:
    try:
        held = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return
    try:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if still_named(held, path):
            path.unlink(missing_ok=True)
    except BlockingIOError:
        pass
    finally:
        os.close(held)


def end_harness_instance(session_id: str) -> None:
    """End a process-backed session, or suspend an instance its owner outlives.

    Desktop unloads an idle Codex instance while its chat remains available to
    resume or receive queued input, and a Claude Code background job's daemon
    retires the job's worker between sittings and resumes the job on its next
    prompt. Their claims keep their generation while the native source or job
    record exists (`service.lifetime_is_live`); the instance's end closes only
    turn and hook observations.
    """
    if not session_id or not _session_paths(session_id):
        return
    with flocked(session_lock_path(session_id)):
        record = session_record(session_id)
        if record and (
            "job" in record["lifetime"] or record["lifetime"] == {"chat": True}
        ):
            if record["ended"] is None and record["turn_closed"] is None:
                advance_turn(session_id, record["turn"], running=False)
            for suffix in (HOOKS_SUFFIX, STEP_HOOK_SUFFIX):
                session_file(session_id, suffix).unlink(missing_ok=True)
            return
        _end_session(session_id)


def session_claims(session_id: str) -> Path:
    """This session's discovery locators; payloads remain canonical by page."""
    return state_home().resolve() / "claims" / session_file(session_id, "claims").stem


def holds_claims(session_id: str) -> bool:
    """Whether the session holds a claim, in this generation or a kept one from
    before: a page it claimed that no other session has claimed since."""
    try:
        with os.scandir(session_claims(session_id)) as entries:
            return next(entries, None) is not None
    except FileNotFoundError:
        return False


def main() -> None:
    payload = json.load(sys.stdin)
    if sys.argv[1:2] == ["hook-gate"]:
        # `bin/leaf` asks this before starting uv for a hook registered
        # `--if-claimed`, and a hook it skips takes about 25 ms in place of about
        # 70 (measured on macOS). 3 alone says "nothing to do": a failure here
        # must not skip the hook.
        sys.exit(0 if holds_claims(payload.get("session_id") or "") else 3)
    if payload.get("hook_event_name") == "SessionEnd":
        end_harness_instance(payload.get("session_id") or "")


if __name__ == "__main__":
    main()
