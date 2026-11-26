"""The bridge that runs Claude Code's sandboxed `leaf` commands outside its sandbox.

Claude Code's sandbox refuses what a `leaf` command needs: writes to the state home,
a port the user's browser reaches, Chrome for render checks, and on Linux the
session's process and a server that outlives the command. Its hooks run outside the
sandbox, so the hook Claude Code runs before a shell command naming `leaf`
(`ensure`) starts a bridge there, and `bin/leaf` hands each
command confined by Claude Code's sandbox (`SANDBOX_RUNTIME`) to it (`run`). The command then runs as an unsandboxed one
would, with its arguments, working directory and environment. Its output and exit
status pass as they come, and so does its stdin, read beside the command, so a
command that never reads a stdin that never ends still finishes. The command reads
that stdin through a pipe, so it learns from the client whether the caller's own
was piped (`piped_input`).

The only road out of that sandbox a command can take without settings is Claude
Code's network proxy, which every sandboxed command's `HTTP_PROXY` names: a direct
connection to 127.0.0.1 or to a Unix socket is refused (measured at Claude Code
2.1.300). So the bridge listens on 127.0.0.1, the client reaches it through a
CONNECT tunnel in that proxy, and the proxy admits 127.0.0.1 once the user approves
it or lists it in `sandbox.network.allowedDomains` (README, "Agent sandboxes"). The
bridge refuses a request without the token in its record, which only the user's
own processes can read: neither another user on the machine nor a page in a
browser can drive it. Codex's sandbox has no such road, so Codex's agent runs a
confined command through Leaf's MCP server instead (`codex_tool.py`).

A session that runs no `leaf` command starts no bridge and no hook for one: the
hook's `if` rules (`hooks/hooks.json`) have Claude Code start it only before a
command it reads as running `leaf` by name or by path, or one whose commands it
cannot read.

One bridge serves every copy of Leaf that ships this file (`KEY`), and runs each
command on the interpreter of the copy whose client sent it. Claude Code installs a
plugin update as a new copy beside the one a running session loaded, and both
copies reach the same bridge. The bridge serves while any session a hook
registered with it lives (`service.session_lives`), by the lifetime its claims would
record (`Harness.lifetime`), until its record says it ended. A registration is one of
its session's files, so it goes when they do (`state._retire`, once no claim keeps the
session's records); until then the session's ended record stops it counting, and the
sweep forgets it (`live_sessions`). A background job outlives the worker hosting its
current sitting, and its next sitting may run `leaf` from a script, before which no
hook runs. That script reaches this bridge where the later sitting's copy ships the
same file. Each process of a session that lives as its own pid keeps its own
registration, so the bridge serves while any of them lives, until the first to end
the session ends it for all of them (`state.end_harness_instance`). A hook registers
the session from the copy Claude Code loaded (`hooks.main`), whose client a
sandboxed bare `leaf` runs, so a checkout's sandboxed `bin/leaf` reaches a bridge
only where it ships this file as that copy does. The running bridge holds its lease
(`leases.take_lease`). A hook registers its session and tries the lease under the
registrations' lock, and a retiring bridge reads the registrations a last time
and releases the lease under that lock too (`retire`), so a session that
registers meanwhile either keeps this bridge serving, its lease held throughout,
or has started the next one. A hook that takes the lease removes the
address a gone bridge left before it lets the registrations' lock go, so once
another hook can find the lease held the address is absent or the holder's. A
client counts a bridge up only once it accepts the request, so one that reaches a
retiring bridge tries again, and it waits for the address for as long as a bridge
holds the lease, since a slow start only makes that wait longer; with no
holder it fails at once, contacting no address, since a gone bridge's port may
now be another listener's. A client that falls silent before its
command's exit status, as when Claude Code times the command out, ends the
command's process group.
"""

import base64
import contextlib
import hashlib
import json
import os
import queue
import secrets
import selectors
import signal
import socket
import socketserver
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

from leaf.base.leases import lock_is_held, release_lease, take_lease
from leaf.base.piped_input import STDIN_PIPED, piped
from leaf.base.state import (
    PLUGIN_ROOT,
    STRING,
    Record,
    described,
    flocked,
    object_schema,
    session_file,
    session_record,
    sessions_home,
    state_home,
    still_named,
)

ADDRESS = Record(
    "bridge",
    described(
        "Where the running bridge of one version of `bridge.py` listens, in the "
        "state home's `bridge/<key>.json`.",
        object_schema(
            {
                "port": described(
                    "The loopback port it listens on.", {"type": "integer"}
                ),
                "token": described("The token a request carries.", STRING),
                "pid": described("The bridge's process.", {"type": "integer"}),
            }
        ),
    ),
    since=13,
)
REGISTRATION = Record(
    "bridge-session",
    described(
        "A session the bridge serves, one of the session's own files in the state "
        "home's `sessions/` (`registrations`), with the fields of the lifetime it "
        "lives by (`Harness.lifetime`) beside its id.",
        object_schema({"id": described("The harness's session id.", STRING)}),
    ),
    since=13,
)

# Every copy that ships this file shares its bridge (module header). A copy that
# changes the file, and so perhaps the frames below, starts a bridge of its own,
# while the older one serves out the sessions registered with it.
KEY = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]

# Both ways, each frame is a channel byte, a length, and that many bytes. The
# client sends the request, then the command's stdin, ending with an empty frame,
# and a heartbeat while it waits; the bridge accepts the request once the command
# runs, then sends its stdout and stderr as they come, and its exit status.
REQUEST, STDIN, HEARTBEAT = b"r", b"i", b"h"
ACCEPTED, STDOUT, STDERR, EXIT = b"a", b"o", b"e", b"x"
HEADER = struct.Struct(">cI")

# The stdin frames, of up to 64 KiB each, a bridge holds for a command that has
# not read them, and the most a request may carry: its arguments and environment.
STDIN_FRAMES = 256
REQUEST_BYTES = 1 << 22

# Claude Code's proxy keeps the bridge's side of a tunnel open after the client on
# the other side has gone, so the bridge knows the client by its heartbeat
# (measured at Claude Code 2.1.300: open until the session ended).
HEARTBEAT_SECONDS = 5
SILENCE_SECONDS = 20

# How often the bridge looks for a registered session still alive.
SWEEP_SECONDS = 15

# How often a client looks for the bridge's address, and how many refusals from a
# published bridge, or the proxy in front of it, it takes before it gives up: the
# proxy may refuse 127.0.0.1 until the user approves it.
POLL_SECONDS = 0.1
REFUSALS = 50


def send(stream, channel: bytes, data: bytes) -> None:
    stream.write(HEADER.pack(channel, len(data)) + data)
    stream.flush()


def receive(stream, limit: int | None = None) -> tuple[bytes, bytes] | None:
    """The next frame, or None where the other side has closed or announces more
    than `limit` bytes."""
    header = stream.read(HEADER.size)
    if len(header) < HEADER.size:
        return None
    channel, length = HEADER.unpack(header)
    if limit is not None and length > limit:
        return None
    data = stream.read(length)
    return (channel, data) if len(data) == length else None


def bridge_path(suffix: str) -> Path:
    return state_home() / "bridge" / f"{KEY}.{suffix}"


def ensure(session: str, lifetime: dict) -> None:
    """Register `session`, which lives as `lifetime` says, with this file's
    bridge, and start the bridge if none holds its lease. The started bridge
    inherits the lease."""
    # Only the user reads the bridge's directory, and with it the token.
    bridge_path("lock").parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    registration = {"id": session, **lifetime}
    named = json.dumps(registration, sort_keys=True).encode()
    digest = hashlib.sha256(named).hexdigest()[:32]
    # Under the lock a retiring bridge releases its lease under (`retire`).
    with flocked(bridge_path("sessions.lock")):
        REGISTRATION.write(
            session_file(session, f"{KEY}-{digest}.bridge"), registration
        )
        lease = take_lease(bridge_path("lock"))
        if lease is None:
            return
        # An address left while no bridge held the lease is a gone bridge's, as
        # after a crash or a reboot, so a client waits for the new one's (`run`).
        # It goes before the lock does, so a hook that then finds the lease held
        # hands its client no address but the new bridge's.
        ADDRESS.remove(bridge_path("json"))
    # Closing this copy leaves the lease held by the bridge's.
    with lease, open(bridge_path("log"), "ab") as log:
        subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-m",
                "leaf.base.bridge",
                "serve",
                str(lease.fileno()),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            pass_fds=(lease.fileno(),),
        )


def registrations() -> list[Path]:
    """The sessions registered with this file's bridge (`ensure`): one file for each
    lifetime a session registered, among the session's own files
    (`state.session_file`)."""
    return REGISTRATION.glob(sessions_home(), f"*.{KEY}-*.bridge")


def live_sessions() -> bool:
    """Whether a registered session still lives; forgets the rest."""
    from leaf.base.service import session_lives

    alive = False
    for entry in registrations():
        if (record := REGISTRATION.read(entry)) and session_lives(
            record, session_record(record["id"])
        ):
            alive = True
        else:
            REGISTRATION.remove(entry)
    return alive


def serve(lease_fd: int) -> None:
    # The sweep's lifetime rule, loaded while the copy that started this bridge
    # stands: the bridge serves other copies and may outlive its own, and a sweep
    # that failed to import would end it while sessions it serves live.
    from leaf.base import service  # noqa: F401

    lease = open(lease_fd, "rb")
    token = secrets.token_urlsafe(32)
    running: set[int] = set()

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            # Anything on the machine can connect, so a request that has not
            # arrived whole within the silence a client may keep is not the
            # client's, however slowly its bytes come.
            self.connection.settimeout(SILENCE_SECONDS)
            deadline = threading.Timer(SILENCE_SECONDS, self.cut)
            deadline.start()
            try:
                frame = receive(self.rfile, REQUEST_BYTES)
            except OSError:
                return
            finally:
                deadline.cancel()
            if frame is None or frame[0] != REQUEST:
                return
            request = json.loads(frame[1])
            if not secrets.compare_digest(request["token"], token):
                return
            # The requesting copy's interpreter, so the command runs as that
            # copy's Leaf. `-I` keeps the agent's directory and PYTHONPATH from
            # supplying `leaf`.
            child = subprocess.Popen(
                [request["python"], "-I", "-m", "leaf", *request["argv"]],
                cwd=request["cwd"],
                env=request["env"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            running.add(child.pid)
            stdin: queue.Queue[bytes] = queue.Queue(maxsize=STDIN_FRAMES)
            finished = threading.Event()
            try:
                send(self.wfile, ACCEPTED, b"")
                threading.Thread(
                    target=pour, args=(stdin, child.stdin), daemon=True
                ).start()
                threading.Thread(
                    target=self.feed, args=(child, stdin, finished), daemon=True
                ).start()
                self.relay(child)
                finished.set()
            finally:
                running.discard(child.pid)
                with contextlib.suppress(queue.Full):
                    stdin.put_nowait(b"")

        def cut(self) -> None:
            with contextlib.suppress(OSError):
                self.connection.shutdown(socket.SHUT_RDWR)

        def feed(
            self, child: subprocess.Popen, stdin: queue.Queue, finished: threading.Event
        ) -> None:
            """Queue the client's stdin for the command, and end the command's
            process group if the client falls silent before its exit status, as
            when Claude Code times the command out."""
            with contextlib.suppress(OSError):
                while frame := receive(self.rfile):
                    if frame[0] == STDIN:
                        stdin.put(frame[1])
            if not finished.is_set():
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGTERM)

        def relay(self, child: subprocess.Popen) -> None:
            assert child.stdout is not None and child.stderr is not None
            channels = {child.stdout.fileno(): STDOUT, child.stderr.fileno(): STDERR}
            with selectors.DefaultSelector() as selector:
                for pipe in channels:
                    selector.register(pipe, selectors.EVENT_READ)
                while selector.get_map():
                    for key, _ in selector.select():
                        if data := os.read(key.fd, 65536):
                            send(self.wfile, channels[key.fd], data)
                        else:
                            selector.unregister(key.fileobj)
            # A shell reports a command a signal ended as 128 plus the signal.
            status = child.wait()
            send(self.wfile, EXIT, str(128 - status if status < 0 else status).encode())

    # Closing the server waits for the commands it is running.
    socketserver.ThreadingTCPServer.daemon_threads = False
    # A hook takes the lease and clears a gone bridge's address under this lock
    # (`ensure`). If the state home was removed while this bridge started, a
    # later hook may already have started the next bridge on a new lease file,
    # so this one ends without writing over that bridge's address.
    with flocked(bridge_path("sessions.lock")):
        if not still_named(lease.fileno(), bridge_path("lock")):
            release_lease(lease)
            return
        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        ADDRESS.write(
            bridge_path("json"),
            {"port": server.server_address[1], "token": token, "pid": os.getpid()},
        )
    # The bridge lives only as long as its sweep, so a sweep that raises ends it
    # rather than leaving it serving with nothing to retire it.
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        retire(lease, running)
    finally:
        # A failed sweep leaves the lease held. Releasing it before waiting for
        # the running commands lets the next hook start a bridge meanwhile, as
        # after `retire` returns.
        if not lease.closed:
            release_lease(lease)
        server.shutdown()
        server.server_close()


def retire(lease, running: set[int]) -> None:
    """Hold the bridge's lease while a command it runs or a session registered
    with it lives, then release it. The last read of the registrations and the
    release share the lock a hook registers under (`ensure`), so a hook that finds
    the lease held has registered a session this bridge goes on serving, and its
    client never finds the lease unheld while this bridge serves it (`run`).

    Hooks and clients find the bridge only by its lease's path. Once that path
    names another file or none, as when an eval removes the scratch state home
    its session ran under, nothing can reach this bridge, so it releases the
    lease at once. The path is resolved once, since resolving a path through
    `state_home` creates the state home again."""
    lock = bridge_path("lock")
    while True:
        time.sleep(SWEEP_SECONDS)
        if not still_named(lease.fileno(), lock):
            release_lease(lease)
            return
        if running or live_sessions():
            continue
        with flocked(bridge_path("sessions.lock")):
            if not live_sessions():
                release_lease(lease)
                return


def pour(stdin: queue.Queue, pipe) -> None:
    """Write what the client sends to the command's stdin, closing it at the
    empty frame that ends it. It runs on a thread of its own, since a command that
    never reads its stdin blocks the write; once STDIN_FRAMES wait unread, the
    client's further frames, its heartbeat among them, wait too."""
    with contextlib.suppress(BrokenPipeError), pipe:
        while data := stdin.get():
            pipe.write(data)
            pipe.flush()


def connect(port: int) -> socket.socket:
    """A connection to the bridge: through the sandbox's proxy, which Claude Code
    names in HTTP_PROXY, as a CONNECT tunnel, so stdin and output flow both ways.
    Raises OSError with the proxy's answer where it refuses."""
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if not proxy:
        return socket.create_connection(("127.0.0.1", port))
    from http.client import HTTPConnection

    via = urlsplit(proxy)
    assert via.hostname is not None
    tunnel = HTTPConnection(via.hostname, via.port)
    headers = {}
    if via.username:
        credentials = f"{unquote(via.username)}:{unquote(via.password or '')}"
        headers["Proxy-Authorization"] = (
            "Basic " + base64.b64encode(credentials.encode()).decode()
        )
    tunnel.set_tunnel("127.0.0.1", port, headers)
    tunnel.connect()
    return tunnel.sock


def attempt(record: dict, request: dict):
    """The stream to the bridge at `record` once it accepts `request`, or None
    and why not, with whatever the attempt opened closed."""
    stream = None
    try:
        with connect(record["port"]) as connection:
            stream = connection.makefile("rwb")
        send(stream, REQUEST, json.dumps(request | {"token": record["token"]}).encode())
        if receive(stream) == (ACCEPTED, b""):
            return stream, None
        refusal = "the bridge closed the connection"
    except OSError as error:
        refusal = str(error)
    if stream is not None:
        stream.close()
    return None, refusal


def run(argv: list[str]) -> int:
    """Run `leaf ARGV` through the bridge and relay its output; its exit status."""
    env = {
        name: value
        for name, value in os.environ.items()
        if name != "SANDBOX_RUNTIME" and "proxy" not in name.lower()
    }
    # The command reads the pipe this relays stdin over, so it learns from here
    # whether the caller's own stdin was piped (`piped_input`).
    try:
        env[STDIN_PIPED] = "1" if piped(0) else "0"
    except OSError:
        env[STDIN_PIPED] = "0"
    request = {"argv": argv, "cwd": os.getcwd(), "env": env, "python": sys.executable}
    # A bridge a hook has just started publishes its address once it has loaded,
    # however long that takes on a loaded machine, and holds the lease meanwhile;
    # a retiring one closes connections it has not accepted. Its pid may be in
    # another namespace, so the lease says whether one runs, and only its
    # acceptance says it is up.
    refusals = 0
    while True:
        # An address with no lease holder is a gone bridge's, and its port may
        # now be another listener's, which could hold the request unanswered.
        if not lock_is_held(bridge_path("lock")):
            print(
                "leaf: no Leaf bridge is running to take this command out of Claude "
                "Code's sandbox. Leaf's hook starts the bridge before a Bash command "
                "whose own text runs `leaf`, not one inside a script or `bash -c`",
                file=sys.stderr,
            )
            return 1
        if record := ADDRESS.read(bridge_path("json")):
            stream, refusal = attempt(record, request)
            if stream is not None:
                break
            refusals += 1
        if refusals == REFUSALS:
            print(
                "leaf: this command could not reach Leaf's bridge out of Claude "
                f"Code's sandbox ({refusal}). The sandbox lets a command reach it "
                "once you approve 127.0.0.1 or add it to "
                "sandbox.network.allowedDomains "
                f'("Agent sandboxes" in {PLUGIN_ROOT / "README.md"})',
                file=sys.stderr,
            )
            return 1
        time.sleep(POLL_SECONDS)
    writing = threading.Lock()

    def write(channel: bytes, data: bytes) -> None:
        with writing:
            send(stream, channel, data)

    def feed() -> None:
        # Stdin may never end, as a harness's open socket doesn't, so it is read
        # beside the command rather than before it.
        with contextlib.suppress(OSError):
            while data := os.read(0, 65536):
                write(STDIN, data)
        # A closed stdin fails the read above, and the command still gets its end.
        with contextlib.suppress(OSError):
            write(STDIN, b"")

    def beat() -> None:
        with contextlib.suppress(OSError):
            while True:
                time.sleep(HEARTBEAT_SECONDS)
                write(HEARTBEAT, b"")

    threading.Thread(target=feed, daemon=True).start()
    threading.Thread(target=beat, daemon=True).start()
    outputs = {STDOUT: sys.stdout.buffer, STDERR: sys.stderr.buffer}
    while frame := receive(stream):
        channel, data = frame
        if channel == EXIT:
            return int(data)
        outputs[channel].write(data)
        outputs[channel].flush()
    print("leaf: Leaf's bridge closed before the command finished", file=sys.stderr)
    return 1


def main() -> None:
    if sys.argv[1] == "serve":
        serve(int(sys.argv[2]))
    else:
        sys.exit(run(sys.argv[2:]))


if __name__ == "__main__":
    main()
