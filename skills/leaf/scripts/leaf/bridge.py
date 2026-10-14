"""The bridge that runs Claude Code's sandboxed `leaf` commands outside its sandbox.

Claude Code's sandbox refuses what a `leaf` command needs: writes to the state home,
a port the user's browser reaches, Chrome for render checks, and on Linux the
session's process and a server that outlives the command. Its hooks run outside the
sandbox, so a Claude Code hook (`ensure`) keeps a bridge for this install running
there, and `bin/leaf` hands each command confined by Claude Code's sandbox
(`SANDBOX_RUNTIME`) to it (`run`). The command then runs as an unsandboxed one
would, with its arguments, working directory and environment. Its stdin, output
and exit status pass as they come, so a command that never reads a stdin that
never ends still finishes.

The only road out of that sandbox a command can take without settings is Claude
Code's network proxy, which every sandboxed command's `HTTP_PROXY` names: a direct
connection to 127.0.0.1 or to a Unix socket is refused (measured at Claude Code
2.1.300). So the bridge listens on 127.0.0.1, the client reaches it through a
CONNECT tunnel in that proxy, and the proxy admits 127.0.0.1 once the user approves
it or lists it in `sandbox.network.allowedDomains` (README, "Agent sandboxes"). The
bridge refuses a request without the token in its record, which only the user's
own processes can read: neither another user on the machine nor a page in a
browser can drive it. Codex's sandbox has no such road; its commands still run
confined (`TODO.md`).

One bridge serves an install while any Claude Code process a hook registered for
it is alive. A hook writes its pid before it looks at the bridge's lock, and a
retiring bridge lets the lock go before it reads the registrations again, so a
session that registers meanwhile either keeps this bridge serving or has started
the next one. A client counts a bridge up only once it accepts the request, so one
that reaches a retiring bridge tries again. A client that falls silent before its
command's exit status, as when Claude Code times the command out, ends the
command's process group.
"""

import base64
import contextlib
import fcntl
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

from .state import state_home_path, write_json

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
    return state_home_path() / "bridge" / f"{KEY}.{suffix}"


def ensure(pid: int) -> None:
    """Register Claude Code's process `pid` with this install's bridge, and start
    the bridge if none holds its lock. The started bridge inherits the lock."""
    # Only the user reads the bridge's directory, and with it the token.
    sessions = bridge_path("sessions")
    sessions.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    sessions.mkdir(exist_ok=True)
    (sessions / str(pid)).touch()
    lock = os.open(bridge_path("lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        with open(bridge_path("log"), "ab") as log:
            subprocess.Popen(
                [sys.executable, "-I", "-m", "leaf.bridge", "serve", str(lock)],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
                pass_fds=(lock,),
            )
    finally:
        os.close(lock)


def live_sessions() -> bool:
    """Whether a registered Claude Code process is alive; forgets the rest."""
    from .machine import pid_alive

    sessions = bridge_path("sessions")
    alive = False
    for entry in sessions.iterdir() if sessions.is_dir() else ():
        if pid_alive(int(entry.name)):
            alive = True
        else:
            entry.unlink(missing_ok=True)
    return alive


def serve(lock: int) -> None:
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
            channels = {child.stdout: STDOUT, child.stderr: STDERR}
            with selectors.DefaultSelector() as selector:
                for pipe in channels:
                    selector.register(pipe, selectors.EVENT_READ)
                while selector.get_map():
                    for key, _ in selector.select():
                        if data := os.read(key.fd, 65536):
                            send(self.wfile, channels[key.fileobj], data)
                        else:
                            selector.unregister(key.fileobj)
            # A shell reports a command a signal ended as 128 plus the signal.
            status = child.wait()
            send(self.wfile, EXIT, str(128 - status if status < 0 else status).encode())

    # Closing the server waits for the commands it is running.
    socketserver.ThreadingTCPServer.daemon_threads = False
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    write_json(
        bridge_path("json"),
        {"port": server.server_address[1], "token": token, "pid": os.getpid()},
    )

    def retire() -> None:
        while True:
            time.sleep(SWEEP_SECONDS)
            if running or live_sessions():
                continue
            fcntl.flock(lock, fcntl.LOCK_UN)
            if not live_sessions():
                break
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                break  # a session registered and started the next bridge
        server.shutdown()

    threading.Thread(target=retire, daemon=True).start()
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
    Raises ConnectionError with the proxy's answer where it refuses."""
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if not proxy:
        return socket.create_connection(("127.0.0.1", port))
    via = urlsplit(proxy)
    tunnel = socket.create_connection((via.hostname, via.port))
    request = f"CONNECT 127.0.0.1:{port} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
    if via.username:
        credentials = f"{unquote(via.username)}:{unquote(via.password or '')}"
        request += (
            "Proxy-Authorization: Basic "
            f"{base64.b64encode(credentials.encode()).decode()}\r\n"
        )
    tunnel.sendall(f"{request}\r\n".encode())
    answer = b""
    while b"\r\n\r\n" not in answer:
        if not (chunk := tunnel.recv(4096)):
            break
        answer += chunk
    status = answer.split(b"\r\n", 1)[0].decode(errors="replace")
    if status.split()[1:2] != ["200"]:
        tunnel.close()
        raise ConnectionError(status or "the proxy closed the connection")
    return tunnel


def run(argv: list[str]) -> int:
    """Run `leaf ARGV` through the bridge and relay its output; its exit status."""
    env = {
        name: value
        for name, value in os.environ.items()
        if name != "SANDBOX_RUNTIME" and "proxy" not in name.lower()
    }
    request = {"argv": argv, "cwd": os.getcwd(), "env": env}
    # A bridge a hook has just started takes a moment to publish its address, and a
    # retiring one closes connections it has not accepted. Its pid may be in
    # another namespace, so only its acceptance says it is up.
    refusal = "no bridge has published its address"
    for _ in range(50):
        with contextlib.suppress(FileNotFoundError):
            record = json.loads(bridge_path("json").read_text())
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
            f"sandbox ({refusal}). Leaf's SessionStart and UserPromptSubmit hooks "
            "start the bridge, and the sandbox lets a command reach it once you "
            "approve 127.0.0.1 or add it to sandbox.network.allowedDomains "
            f'("Agent sandboxes" in {Path(__file__).resolve().parents[4] / "README.md"})',
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
