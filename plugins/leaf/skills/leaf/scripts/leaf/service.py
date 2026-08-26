"""Host identity, process lifetime, page claims, and serialized transitions."""

import ctypes
import functools
import hashlib
import ipaddress
import os
import re
import secrets
import sys
import time
from pathlib import Path

from leaf.events import (
    _append_event_unlocked,
    _matching_attempt,
    flocked,
    now_iso,
    read_cursor,
    read_events,
    require_cross_process_locking,
    work_claim_version,
)
from leaf.files import json_bytes, read_json, write_json
from leaf.schema import ORPHAN_GRACE_SECS

try:
    import fcntl
except ImportError:  # pragma: no cover - rejected before a lease is read or taken
    fcntl = None


def pid_alive(pid: int) -> bool:
    # PermissionError is another user's process, and every pid this module
    # records — servers, agent sessions — runs as this user. After a reboot the
    # low pids are mostly root's, so counting EPERM alive read a stale record
    # as a live server for as long as the machine stayed up.
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def process_info(pid: int) -> tuple[int, str] | None:
    """Two facts about a live process — the pid above it, and the name of the
    program it is itself running — or None once it is gone.

    The name is the executable's own, not the words the command was written
    with: a process launched through a symlink or a `#!` script reports what the
    kernel loaded. That is the point — it answers which program a process *is*,
    which is what `session_lifetime` asks of an ancestor.

    Two platform doors because there is no portable one. `ps` reads this on
    both, and macOS ships it setuid root, which the seatbelt sandbox Codex runs
    its shell tool under refuses to exec — so the one door that looks portable
    is the one that fails exactly where this is needed (measured inside
    `codex exec --sandbox workspace-write`: `/bin/ps: Operation not
    permitted`)."""
    if sys.platform == "darwin":
        # proc_pidinfo's PROC_PIDT_SHORTBSDINFO, whose whole struct is the two
        # facts wanted; pbsi_comm is the executable's name, truncated to 16.
        class ProcBSDShortInfo(ctypes.Structure):
            _fields_ = [
                ("pbsi_pid", ctypes.c_uint32),
                ("pbsi_ppid", ctypes.c_uint32),
                ("pbsi_pgid", ctypes.c_uint32),
                ("pbsi_status", ctypes.c_uint32),
                ("pbsi_comm", ctypes.c_char * 16),
                ("pbsi_flags", ctypes.c_uint32),
                ("pbsi_uid", ctypes.c_uint32),
                ("pbsi_gid", ctypes.c_uint32),
                ("pbsi_ruid", ctypes.c_uint32),
                ("pbsi_rgid", ctypes.c_uint32),
                ("pbsi_svuid", ctypes.c_uint32),
                ("pbsi_svgid", ctypes.c_uint32),
                ("pbsi_rfu", ctypes.c_uint32),
            ]

        proc_pidt_shortbsdinfo = 13
        info = ProcBSDShortInfo()
        proc_pidinfo = ctypes.CDLL(None).proc_pidinfo
        if proc_pidinfo(
            ctypes.c_int(pid),
            ctypes.c_int(proc_pidt_shortbsdinfo),
            ctypes.c_uint64(0),
            ctypes.byref(info),
            ctypes.c_int(ctypes.sizeof(info)),
        ) != ctypes.sizeof(info):
            return None
        return info.pbsi_ppid, info.pbsi_comm.decode()

    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    # The program's name is parenthesised and may hold spaces and parens of its
    # own, so the fields after it are read from past the last ')': state, ppid.
    program = stat[stat.index("(") + 1 : stat.rindex(")")]
    return int(stat[stat.rindex(")") + 1 :].split()[1]), program


def ancestry() -> list[tuple[int, str]]:
    """This process and every process above it, nearest first: (pid, program).

    The walk ends at init, or at whichever ancestor exited while it ran — a
    parent that goes takes the rest of the chain with it, since what is left
    above a reparented process is init's."""
    walked = []
    pid = os.getpid()
    while pid > 1:
        info = process_info(pid)
        if info is None:
            break
        parent, program = info
        walked.append((pid, program))
        pid = parent
    return walked


def lock_is_held(path: Path) -> bool:
    """Whether an exclusive lease is held on this file.

    The kernel releases the lease on exit, crash, or reboot. A durable record
    can therefore outlive its writer without being mistaken for a live process.
    """
    require_cross_process_locking()
    try:
        with open(path, "r+b") as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.flock(probe, fcntl.LOCK_UN)
            return False
    except OSError:
        return False


def page_lock(page_dir: Path, purpose: str) -> Path:
    """A stable lock for one page, outside the page it guards.

    `page init` must reject a package input without writing into it, so
    locks that can meet init cannot live in the prospective page directory. The
    resolved path gives every process the same lock while the purpose keeps the
    contract transition independent from the page's current session claim.
    """
    locks = state_home() / "page-locks"
    locks.mkdir(exist_ok=True)
    key = hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()[:32]
    return locks / f"{key}.{purpose}.lock"


def transition_lock(page_dir: Path) -> Path:
    """Serialize service changes, re-vendoring, and contract-bearing writes."""
    return page_lock(page_dir, "transition")


def contract_writer(function):
    """Keep a CLI event's validation and append on one vendored contract."""

    @functools.wraps(function)
    def locked(page_dir: Path, *args, **kwargs):
        with flocked(transition_lock(page_dir)):
            return function(page_dir, *args, **kwargs)

    return locked


def running_server(page_dir: Path):
    """The desired service, while a process holds its live-server lease."""
    if not lock_is_held(page_dir / "server.lock"):
        return None
    service = read_json(page_dir / "service.json")
    if not service or not service["enabled"]:
        return None
    return {
        **service,
        "url": page_url(service["host"], service["port"], host_key()),
    }


def lifetime_note(page_dir: Path) -> str:
    """What ends this server, said at the moment it starts.

    The two lifetimes are indistinguishable from the terminal — same command,
    same URL — and the difference only shows up hours later, when one process is
    gone and the other isn't. So the serve states which it is rather than
    leaving it to be discovered, on the line after the URL, and names the command
    where that is the only way out.

    Read from service.json, the one place a lifetime is written down. The record
    lands before the URL is printed and survives an explicit stop, so a restart
    restores the same lifetime as well as the same URL."""
    if (read_json(page_dir / "service.json") or {}).get("lifetime") == "standing":
        return (
            "standing server: no agent session claimed this page, so it outlives "
            f"this shell. `leaf server stop {page_dir}` is what stops it."
        )
    return (
        "session server: it stops when the agent session that claimed this page ends."
    )


def stop_when_service_ends(page_dir: Path) -> None:
    """Apply desired state and session ownership from inside the server.

    The process exits as the shutdown operation. That closes the listening
    socket, every accepted keep-alive socket, and the live lease together; a
    graceful `shutdown()` can release the lease while a handler thread still
    owns an accepted connection.
    """
    orphaned_at = None
    while True:
        service = read_json(page_dir / "service.json")
        if not service or not service["enabled"]:
            os._exit(0)
        if service["lifetime"] == "standing":
            time.sleep(0.1)
            continue
        claim = page_claim(page_dir)
        if claim_is_active(claim):
            orphaned_at = None
        elif orphaned_at is None:
            orphaned_at = time.monotonic()
        elif time.monotonic() - orphaned_at >= ORPHAN_GRACE_SECS:
            # A transfer may land after the unlocked observation above. Recheck
            # beside process exit under the page transaction so a new live owner
            # cannot inherit a server already committed to retiring.
            try:
                with PageTransaction(page_dir) as page:
                    service = read_json(page_dir / "service.json")
                    if not service or not service["enabled"]:
                        os._exit(0)
                    if service["lifetime"] == "standing" or page.active_claim:
                        orphaned_at = None
                        continue
                    os._exit(0)
            except FileNotFoundError:
                # Deleting the page removes its successful-init identity. The
                # service has nothing left to preserve and must not recreate it.
                os._exit(0)
        time.sleep(0.1)


def page_access(page_dir: Path, host: str | None = None) -> dict:
    """Where a page is reached: the name its URL carries and the interface its
    server binds. The key that URL also carries is the machine's — `host_key`.

    Derived — no `host` — the address is read from SSH_CONNECTION, whose third
    field is this machine as the client just reached it: a route the session
    carrying the request has already demonstrated, rather than a guess about what
    resolves from where. No SSH_CONNECTION is the same answer for a reader on
    this machine: loopback. The server binds that address alone, so the open port
    faces only the network the session crossed.

    But a route the session demonstrated is not one the user's browser
    shares: a jump host or NAT between them and this machine leaves it
    unroutable from where they sit, and no derivation from this end can know the
    name they do route to. `--host` states it. A stated name goes in the URL and
    the bind widens to every interface of both families (`::`, V6ONLY off),
    because the name need not resolve to an address this machine could bind (a
    NAT'd public IP), let alone say which family the user reaches it by. An
    overlay network the machine has joined (a tailnet) is just one more
    interface. That widens exposure to the machine's other networks and no
    further — leaf never creates a route that didn't exist.

    Recorded once and kept. `start_server` restarts a dead server by re-running
    `server run` bare, and a fresh address there would leave the user's open page
    polling a URL that no longer answers — which is why a stated host is recorded
    here rather than passed per run."""
    access = read_json(page_dir / "service.json")
    if access and host is None:
        return access
    if host:
        # The record's one door checks what it keeps: a scheme, a port, or a
        # path pasted into --host would mint a URL no browser resolves, handed
        # to the one reader who can't report it.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(r"[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?", host):
                sys.exit(
                    f"--host {host}: not a hostname or IP address "
                    "(no scheme, no port — leaf picks the port)"
                )
        # Over the record, not in place of it: a --host restates where the page
        # is reached, and the record's other facts — the exact port an open tab
        # polls, the standing lifetime — restate nothing and must survive, or
        # the recovery this flag exists for demotes the dashboard it recovers.
        access = {**(access or {}), "host": host, "bind": "::"}
    else:
        ssh = os.environ.get("SSH_CONNECTION", "").split()
        addr = ssh[2] if len(ssh) == 4 else "127.0.0.1"
        access = {"host": addr, "bind": addr}
    return access


def host_key() -> str:
    """The key every page this machine serves is read with, minted at the first
    `server run` and kept in the state home. It rides in the URL Claude hands
    over, and `authorized` puts it in a cookie on arrival.

    The key exists because serving anywhere but loopback puts an unauthenticated
    writer on whatever network reached us, and `POST /api/event` appends to a log
    that outranks the document and replays onto every version after.

    One key for the machine rather than one per page, because every page here
    goes to the same reader — the one person the agent is working with. A page
    has nothing to keep from another page's reader, which is what lets the
    `others` menu link them, and what lets the cookie jar, scoped by host and
    blind to the port, hold one key under one name.

    The cost is that handing out any page's URL hands out every page on the
    machine, present and future. Leaf has one reader; giving it a second
    means scoping the key back to the page first.

    The cookie is a second copy of that cost: a browser's jar is port-blind, so
    any server the reader visits on the same host string — a dev server on
    localhost:3000 — receives the key with their request. Considered and kept:
    every cookie-borne credential has this property (a port-scoped name or a
    derived value is still delivered to every port and replayable against this
    one), and dropping the cookie for a key-in-URL scheme breaks the thing the
    cookie exists for — the page's static asset references (/leaf.js, a module's
    ../leaf.js import) can carry no query, so every asset would need the auth
    the redirect-following request has. The boundary is the host string; a
    reader on a shared or hostile-local-service machine narrows it by serving
    on a name other servers don't share (--host).

    Linked into place rather than written over, so two first serves racing on a
    fresh machine agree on whichever won. Each keeping its own would have their
    servers overwrite the one shared cookie in turn, for as long as both ran."""
    path = state_home() / "access.json"
    if not path.exists():
        staged = path.with_name(f".{secrets.token_hex(8)}.tmp")
        staged.write_bytes(json_bytes({"token": secrets.token_urlsafe(16)}))
        staged.chmod(0o600)
        try:
            os.link(staged, path)
        except FileExistsError:
            pass  # someone minted first; theirs is the key, read below
        staged.unlink()
    return read_json(path)["token"]


def page_url(host: str, port: int, token: str) -> str:
    """The handover URL. A bare IPv6 address is bracketed, since the authority
    already separates its port with a colon."""
    host = f"[{host}]" if ":" in host else host
    return f"http://{host}:{port}/?t={token}"


def config_home() -> Path:
    """$XDG_CONFIG_HOME/leaf (~/.config/leaf/) — the user's implicit package."""
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "leaf"


def state_home() -> Path:
    """$XDG_STATE_HOME/leaf (~/.local/state/leaf/) — pages/ holds page
    directories by convention, claims/ the last claimant of every known page,
    sessions/ the live watcher leases, init/ the stable per-path creation
    leases, and access.json the one key every page here is served with
    (`host_key`). State, not config:
    claim records carry pids and absolute paths, while page service records
    carry ports, so this state is bound to this machine, as is the key that
    reaches it.

    Created here, owner-only: the key is what stands between another local user
    and a log that outranks the document, and a 0644 file under a traversable
    path hands it to anyone on a shared machine. One writer for the mode, since
    every path into the state home resolves through this call."""
    home = (
        Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
        / "leaf"
    )
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    return home


def host_identity() -> dict | None:
    """The identity the host session supplies through the environment, or None
    outside an agent host: `id`, the session's own stable id; `host`, which
    program is running it; `agent`, the display name the page shows for it.

    The name is LEAF_AGENT where the launch set one — naming a worker in its
    environment needs no cooperation from the agent, so every command it runs
    speaks as that voice — and the host's own name otherwise. `host` stays a
    separate fact because behavior keys on it (unattended_pages prescribes
    unified exec or background tasks by host) and a display name is anyone's to
    choose. The LEAF_* door is the launcher's mapping of Codex today; a
    third host earns its own value when one arrives — the id and the name, which
    are the whole of what a launcher can state. What outlives the command is
    `session_lifetime`'s to find."""
    if sid := os.environ.get("CLAUDE_CODE_SESSION_ID"):
        agent = os.environ.get("LEAF_AGENT") or "Claude"
        return {"id": sid, "host": "claude-code", "agent": agent}
    if sid := os.environ.get("LEAF_SESSION_ID"):
        agent = os.environ.get("LEAF_AGENT") or "Codex"
        return {"id": sid, "host": "codex", "agent": agent}
    return None


def message_identity() -> dict:
    """The voice an agent-authored event carries: the posting session's display
    name and session id, read from its own environment rather than the page's
    claim record — the claimant is whoever watches the page, and on a page
    several sessions report to, that is usually not the poster. Empty outside a
    host session: the readers' generic label covers an event with no voice, and
    a stored placeholder would only impersonate a name."""
    identity = host_identity()
    if identity is None:
        return {}
    return {"agent": identity["agent"], "session": identity["id"]}


def session_lifetime(identity: dict) -> dict:
    """The claim fields naming what the agent session's lifetime is, which is
    what the claim records and its readers act on: a lifetime that has ended
    makes ownership inactive, and a session-managed server retires
    ORPHAN_GRACE_SECS after it (`stop_when_service_ends`).

    A session the user sits at is a process, `pid`. Claude Code states it
    outright as CLAUDE_PID, and Codex states nothing, so the Codex half is
    discovered: the nearest ancestor running the `codex` program. The
    launcher cannot hand it over, because a shell tool's $PPID is a fact about
    the *shape* of the command rather than about the session. Measured through
    `codex exec` at 0.147.0: a bare command, an `&&` chain and a `bash -lc` all
    reported the codex process, because the shell it wraps them in can exec a
    last simple command in place; `leaf … | cat` reported the wrapping shell
    itself, which exits with the pipeline. Recording that one would have taken
    the page's server down a second after the command that started it, and the
    page would have told its reader no session holds it while the session sat
    there working.

    A Claude Code background job (`claude --bg`, the agents view) has no such
    process. Its turns run on daemon workers, and CLAUDE_PID names the worker
    hosting the current sitting. The daemon retires that worker about an hour
    after the job goes idle and claims a fresh one at the next wake — measured
    at Claude Code 2.1.241 from its daemon log, `bg settled … (done)` then `bg
    claimed-spare …` — while the job, the session every wake resumes, stands
    until it is deleted. So a job's lifetime is `job`, the directory
    CLAUDE_JOB_DIR names, and a page held by one stays served until the job is
    deleted or `leaf server stop` ends it. The fact read there is the job
    record, `state.json`, which the daemon writes as it creates the job and
    takes with it; the directory alone can stand empty, for a spare never
    assigned or a job an older daemon cleaned. The record's `sessionId` has to
    be this session's, because the variable is inherited: a session started
    under the job's own shell tool carries the job's directory and is a process
    of its own."""
    if identity["host"] == "claude-code":
        if job := os.environ.get("CLAUDE_JOB_DIR"):
            record = read_json(Path(job) / "state.json")
            if record is None:
                sys.exit(
                    f"CLAUDE_JOB_DIR names no job record ({job}/state.json); "
                    "leaf takes a background job's lifetime from it"
                )
            if record["sessionId"] == identity["id"]:
                return {"job": str(Path(job).resolve())}
        return {"pid": int(os.environ["CLAUDE_PID"])}
    walked = ancestry()
    for pid, program in walked:
        if program == "codex":
            return {"pid": pid}
    # Nothing to fall back to: any pid guessed here is a claim that expires on
    # its own, and the states that follow from one are silent. LEAF_SESSION_ID
    # with no codex above it is a hand-built environment, so say what was walked.
    chain = " → ".join(program for _, program in walked)
    sys.exit(
        "LEAF_SESSION_ID names a Codex session but no codex process runs above "
        f"this one ({chain}); leaf takes the session's lifetime from it"
    )


def claim_path(page_dir: Path) -> Path:
    """The one ownership record for a resolved page path."""
    return state_home() / "claims" / f"{page_key(page_dir)}.json"


def page_key(page_dir: Path) -> str:
    """A filesystem-safe identity for state held outside one page directory."""
    return hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()


def init_lock_path(page_dir: Path) -> Path:
    """The lease serializing creation before a page has its own transaction."""
    return state_home() / "init" / f"{page_key(page_dir)}.lock"


def page_claim(page_dir: Path) -> dict | None:
    """The page's last claim, including one released or whose lifetime ended."""
    return read_json(claim_path(page_dir))


def claim_is_active(claim: dict | None) -> bool:
    """Whether a claim still names a live owner: the job record a background
    job's claim points at, or the process every other claim's pid names
    (`session_lifetime`). The only reading of that rule: the hooks reach it
    through `uv` rather than keeping a copy, so a host that states its lifetime a
    new way joins here alone."""
    if not claim or claim["released"] is not None:
        return False
    if "job" in claim:
        return (Path(claim["job"]) / "state.json").is_file()
    return pid_alive(claim["pid"])


def claim_records() -> list:
    """Every atomic page claim record currently on this machine."""
    directory = state_home() / "claims"
    if not directory.is_dir():
        return []
    return [claim for path in directory.glob("*.json") if (claim := read_json(path))]


class PageTransaction:
    """One page transition serialized by its append-only log."""

    def __init__(self, page_dir: Path):
        self.page_dir = page_dir.resolve()
        self._lock = None
        self._log = None

    def __enter__(self):
        self._lock = flocked(self.page_dir / "comments.jsonl")
        self._log = self._lock.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self._lock.__exit__(exc_type, exc, traceback)

    @property
    def claim(self) -> dict | None:
        return page_claim(self.page_dir)

    @property
    def active_claim(self) -> dict | None:
        claim = self.claim
        return claim if claim_is_active(claim) else None

    def take_claim(self, identity: dict, lifetime: dict) -> tuple[dict | None, dict]:
        previous = self.claim
        path = claim_path(self.page_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        claim = {
            "page": str(self.page_dir),
            "id": identity["id"],
            "host": identity["host"],
            **lifetime,
            "agent": identity["agent"],
            "cwd": os.getcwd(),
            "ts": now_iso(),
            "released": None,
            # When this session's last turn ended. None until one has, and reset
            # by nothing: a claim taken again is a new record. See close_turn.
            "turn_closed": None,
        }
        write_json(path, claim)
        return previous, claim

    def restore_claim(self, expected: dict, previous: dict | None) -> None:
        """Roll back one failed claim without erasing a successor's."""
        if self.claim != expected:
            return
        path = claim_path(self.page_dir)
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            write_json(path, previous)

    def owned_by(self, identity: dict | None) -> bool:
        """Whether this transaction may act for the given waiter."""
        if identity is None:
            return self.active_claim is None
        claim = self.active_claim
        return bool(
            claim and (claim["host"], claim["id"]) == (identity["host"], identity["id"])
        )

    def release_claim(self) -> None:
        claim = self.claim
        if claim and claim["released"] is None:
            write_json(claim_path(self.page_dir), {**claim, "released": now_iso()})

    def close_turn(self, session_id: str) -> None:
        """Record that the turn which could have renewed this page's claim has ended.

        A `working` claim is written by a model's turn rather than by a process,
        and a turn can end at any token without running anything — so there is no
        close to write on the way out, and a claim nobody renewed used to be
        found only by a clock fifteen minutes later. The Stop hook is the harness
        observing that same moment exactly, which is what the hooks are for.

        It lands here with the rest of the claim's provenance and not in
        status.json, the line SessionEnd already draws: what the agent said it
        was doing stays the agent's to write, and whether anything is still
        behind those words stays the page's to judge from evidence.
        """
        claim = self.claim
        if claim and claim["released"] is None and claim["id"] == session_id:
            write_json(claim_path(self.page_dir), {**claim, "turn_closed": now_iso()})

    @property
    def status(self) -> dict:
        return read_json(self.page_dir / "status.json") or {"state": "idle"}

    def set_status(
        self,
        state: str,
        detail: str,
        *,
        handoff: bool = False,
        work: dict | None = None,
    ) -> None:
        """Write the page claim and any typed local claim it renews.

        A local line is the same sentence read at a second seat: the page's one
        line says what the agent is doing, and a typed subject says so where the
        work lives. One command writes both because they are one claim — a
        delegate reporting its subject is also the agent checking in, which is
        what keeps `working` believed across a turn boundary the session itself
        cannot write across.

        Standing work carries across every other status write, so a handoff's
        "picking up 2 updates" does not silently drop what a helper is holding.
        A new claim replaces the old claim on its semantic subject; `idle`
        clears them all with the leaf.
        """
        status = {"state": state, "detail": detail, "ts": now_iso()}
        if handoff:
            status["handoff"] = True
        claims = [] if state == "idle" else list(self.status.get("work", []))
        if work:
            identity = message_identity()
            claims = [held for held in claims if held["subject"] != work["subject"]]
            claims.append(
                {
                    "id": secrets.token_hex(4),
                    **work,
                    "detail": detail,
                    "ts": status["ts"],
                    "agent": identity.get("agent")
                    or (self.claim or {}).get("agent", "Claude"),
                    "session": identity.get("session") or (self.claim or {}).get("id"),
                }
            )
        if claims:
            status["work"] = claims
        write_json(self.page_dir / "status.json", status)

    @property
    def events(self) -> list:
        return read_events(self.page_dir)

    def matching_attempt(self, event: dict) -> dict | None:
        """An accepted retry, read under this transaction's log lease."""
        return _matching_attempt(self._log, event)

    def append_event(self, event: dict) -> dict:
        """Append under this transaction without re-entering its log lease."""
        return _append_event_unlocked(self._log, event)

    @property
    def cursor(self) -> int:
        return read_cursor(self.page_dir)

    def watch_state(self, identity: dict | None) -> str:
        if not self.owned_by(identity):
            return "lost"
        return "ended" if self.status["state"] == "idle" else "watching"


def take_page_claim(page_dir: Path) -> tuple[dict | None, dict] | None:
    """Make the host session the page's watcher, if a host supplied one.

    `server start` and named `leaf wait` claim; authoring commands do not. A
    bare-shell serve makes no claim and therefore starts as standing.
    """
    identity = host_identity()
    if not identity:
        return None
    lifetime = session_lifetime(identity)
    with PageTransaction(page_dir) as page:
        return page.take_claim(identity, lifetime)


def claim_page(page_dir: Path) -> bool:
    return take_page_claim(page_dir) is not None


def restore_page_claim(
    page_dir: Path, transition: tuple[dict | None, dict] | None
) -> None:
    """Undo a failed startup's claim, provided no successor replaced it."""
    if transition is None:
        return
    previous, expected = transition
    with PageTransaction(page_dir) as page:
        page.restore_claim(expected, previous)


def owned_pages(session_id: str | None) -> list:
    """Active pages owned by one session, or by every session when id is None."""
    pages = {
        Path(claim["page"])
        for claim in claim_records()
        if claim_is_active(claim)
        and (session_id is None or claim["id"] == session_id)
        and (Path(claim["page"]) / "comments.jsonl").is_file()
    }
    return sorted(pages, key=str)


def unacknowledged(events: list, cursor: int) -> list:
    """The events past the acknowledgement cursor that the page's watcher owes a
    reading: the user's own, and workers' reports — a report moves the page the
    way a user's action does, and the watcher is the one who can absorb it into
    a version. One cursor and one predicate for the whole batch, so `leaf
    wait`'s output, the Stop hook's count, and the idle gate cannot disagree
    about what is still owed. The reader's banner counts only the user half
    (full_state's `pending`): a report is news the agent owes the page, not
    something the reader owes an answer. A session that reports to a page it
    also watches reads its own report back once — rare enough (workers report,
    the watcher publishes) that a session-keyed carve-out would cost a second,
    parameterized predicate for no failure anyone has hit."""
    return [
        e
        for e in events
        if e["seq"] > cursor
        # The user's own, a worker's report, and the page reporting itself
        # broken — the last is the agent's debt exactly as a report is.
        and (
            e["author"] == "user"
            or e["kind"] in ("report", "error")
            or (e["author"] == "page" and e["kind"] == "action")
        )
    ]


def waiter_lease_path(page_dir: Path | None, session: dict | None) -> Path | None:
    """The one lease a wait holds for its watch set.

    A host wait covers every page its session owns, so its lease belongs to the
    session. Outside a host, a named page is the entire watch set and holds a
    page-local lease. An unnamed bare-shell wait has no watch set and no lease.
    """
    if session:
        return state_home() / "sessions" / f"{session['id']}.wait"
    return page_dir / "waiter.lock" if page_dir is not None else None


def take_waiter_lease(path: Path):
    """Take and return a wait lease, or None when another wait already holds it."""
    require_cross_process_locking()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = open(path, "a+b")  # noqa: SIM115 - returned and held for the wait's life
    try:
        fcntl.flock(record, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        record.close()
        return None
    return record


def wait_is_live(page_dir: Path, session: dict | None) -> bool:
    """Whether this ownership scope's exact wait lease is held now."""
    lease_path = waiter_lease_path(page_dir, session)
    return bool(lease_path and lock_is_held(lease_path))


def claim_update_sources(status: dict, events: list) -> list[dict]:
    """The status store's work claims at their public boundary.

    `status.json` remains the small replace-in-place store its transient claims
    need. The browser and `page state` receive typed source envelopes instead, so
    every downstream consumer reads the same target and lifecycle vocabulary.
    """
    sources = []
    for claim in status.get("work", []):
        target = claim["subject"]
        source = {
            "id": claim.get("id")
            or f"claim:{target['kind']}:{target['id']}:{claim['after']}",
            "target": target,
            "source": "claim",
            "action": "working",
            "detail": {"text": claim["detail"]},
            "text": claim["detail"],
            "ts": claim["ts"],
            "log_floor": claim["after"],
            "agent": claim.get("agent"),
            "session": claim.get("session"),
        }
        if target["kind"] == "widget":
            source["version"] = work_claim_version(claim, events)
        sources.append(source)
    return sources
