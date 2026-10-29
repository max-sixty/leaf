"""The bridge that runs Claude Code's sandboxed `leaf` commands outside its sandbox.

Claude Code's sandbox refuses what a `leaf` command needs: writes to the state home,
a port the user's browser reaches, Chrome for render checks, and on Linux the
session's process and a server that outlives the command. Its hooks run outside the
sandbox, so the hook Claude Code runs before a shell command naming `leaf`
(`ensure`) starts a bridge for this install there, and `bin/leaf` hands each
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

One bridge serves an install while any session a hook registered for it lives,
by the lifetime its claims would record (`Harness.lifetime`): a background job
outlives the worker hosting its current sitting, and its next sitting may run
`leaf` from a script, before which no hook runs. The running bridge holds the
install's lease (`leases.take_lease`). A hook registers its session before it
tries the lease, and a retiring bridge releases the lease before it reads the
registrations again, so a session that registers meanwhile either keeps this
bridge serving or has started the next one. A client counts a bridge up only once
it accepts the request, so one that reaches a retiring bridge tries again. A client that falls silent before its
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
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .leases import release_lease, take_lease
from .piped_input import STDIN_PIPED, piped
from .state import PLUGIN_ROOT, STRING, Record, described, object_schema, state_home

ADDRESS = Record(
    "bridge",
    described(
        "Where an installed tree's running bridge listens, in the state home's "
        "`bridge/<key>.json`.",
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
        "A session the bridge serves, in the state home's "
        "`bridge/<key>.sessions/<digest>.json`, with the fields of the lifetime it "
        "lives by (`Harness.lifetime`) beside its id.",
        object_schema({"id": described("The harness's session id.", STRING)}),
    ),
    since=13,
)

# One bridge per installed tree: a plugin update is a new tree, whose sessions
# reach its own bridge while the old one serves out the sessions still on it.
KEY = hashlib.sha256(str(Path(__file__).resolve().parent).encode()).hexdigest()[:16]

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
    """Register `session`, which lives as `lifetime` says, with this install's
    bridge, and start the bridge if none holds its lease. The started bridge
    inherits the lease."""
    # Only the user reads the bridge's directory, and with it the token.
    sessions = bridge_path("sessions")
    sessions.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    sessions.mkdir(exist_ok=True)
    key = hashlib.sha256(session.encode()).hexdigest()[:32]
    REGISTRATION.write(sessions / f"{key}.json", {"id": session, **lifetime})
    if (lease := take_lease(bridge_path("lock"))) is None:
        return
    # Closing this copy leaves the lease held by the bridge's.
    with lease, open(bridge_path("log"), "ab") as log:
        subprocess.Popen(
            [sys.executable, "-I", "-m", "leaf.bridge", "serve", str(lease.fileno())],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            pass_fds=(lease.fileno(),),
        )


def live_sessions() -> bool:
    """Whether a registered session still lives; forgets the rest."""
    from .service import lifetime_is_live
    from .state import session_record

    alive = False
    for entry in bridge_path("sessions").glob("*.json"):
        if (record := REGISTRATION.read(entry)) and lifetime_is_live(
            record, session_record(record["id"])
        ):
            alive = True
        else:
            entry.unlink(missing_ok=True)
    return alive


def serve(lease_fd: int) -> None:
    lease = open(lease_fd, "rb")  # noqa: SIM115 - held until the bridge retires
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
            # `-I` keeps the agent's directory and PYTHONPATH from supplying `leaf`.
            child = subprocess.Popen(
                [sys.executable, "-I", "-m", "leaf", *request["argv"]],
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
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    ADDRESS.write(
        bridge_path("json"),
        {"port": server.server_address[1], "token": token, "pid": os.getpid()},
    )

    def retire(lease) -> None:
        while True:
            time.sleep(SWEEP_SECONDS)
            if running or live_sessions():
                continue
            release_lease(lease)
            if not live_sessions():
                break
            if (lease := take_lease(bridge_path("lock"))) is None:
                break  # a session registered and started the next bridge
        server.shutdown()

    threading.Thread(target=retire, args=(lease,), daemon=True).start()
    server.serve_forever()
    server.server_close()


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
    request = {"argv": argv, "cwd": os.getcwd(), "env": env}
    # A bridge a hook has just started takes a moment to publish its address, and a
    # retiring one closes connections it has not accepted. Its pid may be in
    # another namespace, so only its acceptance says it is up.
    refusal = "no bridge has published its address"
    for _ in range(50):
        if record := ADDRESS.read(bridge_path("json")):
            try:
                stream = connect(record["port"]).makefile("rwb")
                body = json.dumps(request | {"token": record["token"]})
                send(stream, REQUEST, body.encode())
                if receive(stream) == (ACCEPTED, b""):
                    break
                refusal = "the bridge closed the connection"
            except OSError as error:
                refusal = str(error)
        time.sleep(0.1)
    else:
        print(
            "leaf: this command could not reach Leaf's bridge out of Claude Code's "
            f"sandbox ({refusal}). Leaf's hook starts the bridge before a Bash "
            "command whose own text runs `leaf`, not one inside a script or "
            "`bash -c`, and the sandbox lets a command reach it once you approve "
            "127.0.0.1 or add it to sandbox.network.allowedDomains "
            f'("Agent sandboxes" in {PLUGIN_ROOT / "README.md"})',
            file=sys.stderr,
        )
        return 1
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
