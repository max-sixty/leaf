"""Durable and process-owned page servers."""

import errno
import secrets
import socket
import subprocess
import sys
import threading
import zlib
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn

from .event_log import flocked, require_cross_process_locking
from .files import read_json, write_json
from .host import host_identity
from .http import handler_for, page_app
from .layer import payload_provenance
from .leases import lock_is_held, transition_lock
from .registry.storage import layer_metadata
from .schema import SERVER_LOCK, SERVICE_FILE
from .server import (
    host_key,
    lifetime_note,
    loopback_note,
    page_access,
    page_url,
    running_server,
    stop_when_service_ends,
)
from .service import PageTransaction

try:
    import fcntl
except ImportError:  # pragma: no cover - unsupported non-POSIX platform
    fcntl = None

TEMPORARY_SERVER_NOTE = "server   temporary (stops with this command)"


def listening_socket(bind: str, port: int) -> socket.socket:
    """Open the recorded bind, using IPv4 for `::` when IPv6 is unavailable.

    A literal IPv6 address still fails rather than widening to every interface.
    The record keeps `::`; each serve chooses the family the current kernel has.
    A stated host binds the wildcard of both families, so IPV6_V6ONLY is cleared
    before the bind that a v4 client would otherwise never reach.
    """

    def bound(family: int, host: str) -> socket.socket:
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if family == socket.AF_INET6:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            sock.bind((host, port))
            sock.listen(socket.SOMAXCONN)
        except BaseException:
            sock.close()
            raise
        return sock

    if ":" not in bind:
        return bound(socket.AF_INET, bind)
    try:
        return bound(socket.AF_INET6, bind)
    except OSError as e:
        if e.errno != errno.EAFNOSUPPORT or bind != "::":
            raise
        return bound(socket.AF_INET, "0.0.0.0")


class LeafHTTPServer:
    """One page's HTTP server: uvicorn over the handler class it is given.

    The listening socket is opened here rather than by uvicorn, so the address is
    a fact before anything serves on it — a port the caller records, and a taken one
    that raises out of the constructor instead of exiting the process. Serving hands
    uvicorn a duplicate: the two halves then close their own, and a caller that
    releases the socket cannot pull it out from under a loop still winding down.

    `stopping` is the state a held-open news stream reads. A stop has to reach a
    response that is deliberately never finishing, and the stream looks at this
    between its own looks; uvicorn's graceful shutdown then has nothing left to
    wait for.
    """

    def __init__(self, address, handler_class) -> None:
        self.handler_class = handler_class
        self.socket = listening_socket(address[0], address[1])
        self.server_address = self.socket.getsockname()[:2]
        self.stopping = False
        self._uvicorn = None
        self._config = uvicorn.Config(
            page_app(handler_class, self),
            # Leaf says what it has to say on its own streams: the URL, the
            # lifetime note, and the page's own errors. A server with a logging
            # voice of its own would write into the handshake those are read from.
            log_config=None,
            access_log=False,
            lifespan="off",
        )

    def fileno(self) -> int:
        return self.socket.fileno()

    def serve_forever(self) -> None:
        """Serve on the current thread until `shutdown` or a handled signal."""
        self._uvicorn = uvicorn.Server(self._config)
        # A signal reaches uvicorn alone, and its graceful shutdown has no bound:
        # a news stream that never learns of the stop holds the process open.
        handled_exit = self._uvicorn.handle_exit

        def stop(sig, frame):
            self.stopping = True
            handled_exit(sig, frame)

        self._uvicorn.handle_exit = stop
        if self.stopping:
            return
        self._uvicorn.run(sockets=[self.socket.dup()])

    def shutdown(self) -> None:
        """Ask the serving loop to stop, and tell open streams to end."""
        self.stopping = True
        if self._uvicorn is not None:
            self._uvicorn.should_exit = True

    def server_close(self) -> None:
        """Release the listening socket this server has kept."""
        self.socket.close()


class TemporaryPageServer:
    """Serve one page on loopback for the lifetime of this process.

    The server owns a per-instance access key and no durable service record or page
    claim. Browser tests and automation therefore exercise the real HTTP and event-log
    boundary without enrolling the page in an agent session's delivery loop.
    """

    def __init__(
        self,
        page_dir: Path,
        *,
        token: str | None = None,
        port: int = 0,
        handler_options: dict | None = None,
    ) -> None:
        self.token = token or secrets.token_urlsafe(16)
        self.httpd = LeafHTTPServer(
            ("127.0.0.1", port),
            handler_for(page_dir, self.token, **(handler_options or {})),
        )
        self._thread = None
        self._closed = False

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    @property
    def port(self) -> int:
        return self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"{self.origin}/?t={self.token}"

    @property
    def running(self) -> bool:
        return not self._closed and self._thread is not None and self._thread.is_alive()

    def start(self):
        """Start the server in a thread owned by this object."""
        if self._closed or self._thread is not None:
            raise RuntimeError("temporary page server cannot be started twice")
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def run(self) -> None:
        """Serve on the current thread until the process is interrupted."""
        if self._closed or self._thread is not None:
            raise RuntimeError("temporary page server is already running")
        try:
            self.httpd.serve_forever()
        finally:
            self.httpd.server_close()
            self._closed = True

    def close(self) -> None:
        """Stop a threaded server and release its socket.

        A threaded server shares its process with its caller, which may reuse or
        remove the page as soon as this returns, so the stop waits for the requests
        already in flight rather than leaving them writing into a page nobody owns.
        """
        if self._closed:
            return
        self.httpd.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self.httpd.server_close()
        self._closed = True

    def __enter__(self):
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.close()


def cmd_serve_temporary(page_dir: Path) -> None:
    """Run the process-owned page server used by browser automation."""
    require_cross_process_locking()
    server = TemporaryPageServer(page_dir)
    print(server.url, flush=True)
    print(TEMPORARY_SERVER_NOTE, file=sys.stderr, flush=True)
    server.run()


def _provenance_label(provenance: dict) -> str:
    commit = provenance.get("commit")
    if not commit:
        return "unknown source"
    return commit + ("+dirty" if provenance.get("dirty") else "")


def startup_note(page_dir: Path) -> str:
    """Identify the page, vendored bytes, and serving Leaf beside its lifetime."""
    layer = layer_metadata(page_dir)
    service = read_json(page_dir / SERVICE_FILE) or {}
    # An older live service has no trustworthy runtime identity. Naming this
    # command's payload instead would make the exact stale-server case this note
    # exists to expose look current merely because a newer client inspected it.
    runtime = service.get("runtime") or {}
    fingerprint = layer["fingerprint"]
    # After the lifetime line, not before: a served subprocess's first line of
    # stderr is the lifetime, and readers of that handshake take exactly one.
    return "\n".join(
        line
        for line in (
            lifetime_note(page_dir),
            loopback_note(page_dir),
            f"page     {page_dir}",
            f"layer    {fingerprint} ({_provenance_label(layer.get('producer', {}))})",
            (
                f"runtime  {runtime.get('path', 'unknown payload')} "
                f"({_provenance_label(runtime)})"
            ),
        )
        if line
    )


def _serve_claim(
    page_dir: Path,
    page: PageTransaction,
    service: dict | None,
    standing: bool,
    revive: bool,
) -> bool:
    """Validate this launch against desired state and page ownership."""
    if revive and (not service or not service["enabled"]):
        sys.exit("service was stopped; not reviving")

    identity = host_identity()
    claim = page.claim
    claimed = bool(
        not standing
        and identity is not None
        and claim is not None
        and claim["released"] is None
        and (claim["host"], claim["id"]) == (identity["host"], identity["id"])
    )
    if not standing and identity is not None and not claimed:
        sys.exit(
            f"this host session no longer owns {page_dir}; the server was not started"
        )
    if revive and service and service["lifetime"] == "session" and not claimed:
        sys.exit("this session no longer owns the service; not reviving")
    return claimed


def _announce_server(page_dir: Path, url: str, detached: bool) -> None:
    """Print a server's URL and lifetime in the order its caller consumes them."""
    note = startup_note(page_dir)
    if detached:
        # The parent reads the URL as the successful-start handshake and then
        # closes these private pipes. Finish the note before that handshake.
        print(note, file=sys.stderr, flush=True)
        print(url, flush=True)
        return
    print(url, flush=True)
    print(note, file=sys.stderr, flush=True)


def _reuse_server(
    page_dir: Path, host: str | None, standing: bool, detached: bool
) -> bool:
    """Report a compatible running server, or say a fresh bind is needed."""
    existing = running_server(page_dir)
    if not existing:
        return False
    if host and urlsplit(existing["url"]).hostname != host.lower():
        sys.exit(
            f"already serving at {existing['url']}; "
            "leaf server stop first, then re-run with --host"
        )
    if standing and existing["lifetime"] != "standing":
        sys.exit(
            f"already serving as a session server at {existing['url']}; "
            "leaf server stop first, then re-run with --standing"
        )
    _announce_server(page_dir, existing["url"], detached)
    return True


def _take_server_lease(page_dir: Path, detached: bool):
    """Take the process lease, or report the concurrent server that won it."""
    lease = open(  # noqa: SIM115 - held until the server process exits
        page_dir / SERVER_LOCK, "a+b"
    )
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lease.close()
        winner = running_server(page_dir)
        if winner:
            _announce_server(page_dir, winner["url"], detached)
            return None
        sys.exit(f"another server run is serving {page_dir}; re-run")
    return lease


def _bind_server(page_dir: Path, access: dict, token: str, ports: list, lease):
    """Bind the first available port, preserving a recorded address contract."""
    for port in ports:
        try:
            return LeafHTTPServer((access["bind"], port), handler_for(page_dir, token))
        except OSError as error:
            if error.errno == errno.EADDRINUSE and "port" not in access:
                continue
            lease.close()
            sys.exit(
                f"can't serve {page_dir} on {access['bind']}"
                f"{':' + str(access['port']) if 'port' in access else ''}: "
                f"{error}\nthat address is kept in "
                f"{page_dir / 'service.json'}; delete that file to derive "
                "the address again from this session, or re-run with --host NAME."
            )
    return None


def _service_record(
    access: dict, httpd, standing: bool, claimed: bool, runtime: dict
) -> dict:
    """The durable desired state for a newly bound server."""
    lifetime = (
        "standing"
        if standing or access.get("lifetime") == "standing" or not claimed
        else "session"
    )
    return {
        "host": access["host"],
        "bind": access["bind"],
        "port": httpd.server_address[1],
        "enabled": True,
        "lifetime": lifetime,
        "runtime": runtime,
    }


def cmd_serve(
    page_dir: Path,
    host: str | None = None,
    standing: bool = False,
    revive: bool = False,
    *,
    detached: bool = False,
) -> None:
    """Serve one initialized page under its durable service contract.

    Claiming is deliberately outside this process: server start claims before
    spawning it, server run claims at the CLI boundary, and a wait already owns
    the page it revives. This child only verifies that the matching claim still
    stands, then owns service.json and the server.lock process lease.
    """
    require_cross_process_locking()
    lease = None
    httpd = None
    runtime = payload_provenance(include_path=True)
    with flocked(transition_lock(page_dir)), PageTransaction(page_dir) as page:
        service = read_json(page_dir / SERVICE_FILE)
        claimed = _serve_claim(page_dir, page, service, standing, revive)
        if _reuse_server(page_dir, host, standing, detached):
            return

        access = page_access(page_dir, host)
        token = host_key()
        base = 41000 + zlib.crc32(str(page_dir.resolve()).encode()) % 4000
        ports = [access["port"]] if "port" in access else [*range(base, base + 10), 0]
        lease = _take_server_lease(page_dir, detached)
        if lease is None:
            return
        httpd = _bind_server(page_dir, access, token, ports, lease)
        service = _service_record(access, httpd, standing, claimed, runtime)
        write_json(page_dir / SERVICE_FILE, service)
        url = page_url(service["host"], service["port"], token)

    _announce_server(page_dir, url, detached)
    threading.Thread(
        target=stop_when_service_ends,
        args=(page_dir,),
        daemon=True,
    ).start()
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        lease.close()


def start_server(
    page_dir: Path,
    host: str | None = None,
    standing: bool = False,
    revive: bool = False,
) -> tuple[str, str] | None:
    """Put the page's server up in a session of its own, and report where.

    The serve has to outlive this command — the browser polls it between turns
    and across every `leaf wait`, which exits to deliver — so it is spawned
    rather than held, and the one long-running command a leaf costs its session
    is the watcher. The maintainer `session-lifetime.md` contract carries the
    rest of that.

    `server run` in a session of its own is the whole mechanism. An explicit
    start may enable a stopped service; a revival carries the narrower intent
    "only if still enabled," which the child checks inside the transition.
    sys.executable is the resolved uv environment, so this skips uv.

    Returns where the page is and what ends it — the URL the child minted and
    the note for the lifetime it recorded — or None, having put the child's
    reason on stderr.
    """
    require_cross_process_locking()
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "leaf",
            "server",
            "_serve",
            str(page_dir),
            *(["--host", host] if host else []),
            *(["--standing"] if standing else []),
            *(["--revive"] if revive else []),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    # The child's own handshake, rather than a deadline over a file that may or
    # may not appear inside it: a detached serve prints the URL after it holds
    # the record and the port and finishes its startup note. Otherwise it exits
    # having named its own reason — a stale bind, a taken port, or a flag the
    # running server contradicts.
    url = child.stdout.readline().strip()
    if not url:
        print(
            child.stderr.read().strip() or f"the server for {page_dir} did not start",
            file=sys.stderr,
        )
        return None
    # Nothing drains the child's streams from here on, which is safe because the
    # URL and the note printed beside it are everything a server ever says — the
    # handler logs nothing (`log_message`) — so there is nothing left to write
    # into pipes this process closes on its way out.
    return url, startup_note(page_dir)


def cmd_stop(page_dir: Path) -> str:
    """Disable the desired service and wait until its process lease is released."""
    require_cross_process_locking()
    with flocked(transition_lock(page_dir)):
        service = read_json(page_dir / SERVICE_FILE)
        live = lock_is_held(page_dir / SERVER_LOCK)
        if service and service["enabled"]:
            write_json(page_dir / SERVICE_FILE, {**service, "enabled": False})
        if live:
            # The serving process observes disabled desired state and exits.
            # Taking its lease is the barrier proving every socket is closed.
            with open(page_dir / SERVER_LOCK, "a+b") as lease:
                fcntl.flock(lease, fcntl.LOCK_EX)
            return "stopped server"
    return "no server running"
