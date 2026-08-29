"""HTTP server binding, process startup, and the in-process serve command."""

import errno
import socket
import subprocess
import sys
import threading
import zlib
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .event_log import flocked, require_cross_process_locking
from .files import read_json, write_json
from .host import host_identity
from .http import handler_for
from .leases import lock_is_held, transition_lock
from .server import (
    host_key,
    lifetime_note,
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


class LeafHTTPServer(ThreadingHTTPServer):
    """Every page leaf serves — a session server, a preview, a test's fixture —
    is served from here, so the suite drives the server the product answers on.

    The one thing it states is how deep the kernel may queue connections the
    accept loop has not reached yet. `socketserver` says five, and a queue that
    overflows does not hold the sixth caller back. Linux drops the handshake's
    last packet, the client posts into a connection this side has already
    forgotten, and the reset that comes back reaches the reader as a send that
    went nowhere. Five is reachable: test_concurrent_posts_never_tear_the_log
    sends twenty at once to ask about the append itself, and on an emulated
    Linux box a quarter of them were reset before the log was ever the
    question. Nothing here wants a shallower queue than the kernel will hold,
    so the number is the kernel's own."""

    request_queue_size = socket.SOMAXCONN

    # Whether this server has been told to stop. `socketserver` keeps that fact in a
    # name-mangled private, and a news stream held open for a tab needs to see it:
    # the stream otherwise outlives the stop for as long as the tab stays.
    stopping = False

    def shutdown(self):
        self.stopping = True
        super().shutdown()

    def serve_forever(self, poll_interval=0.01):
        """How long `shutdown` may take to be noticed.

        `socketserver` waits half a second in `select` between checks of the
        shutdown flag, so a server told to stop keeps its caller for as long as
        that select still has to run: 489ms measured against 3.2ms at a
        hundredth. Nothing here waits on the interval for its own sake — the
        loop wakes on a connection either way — so shortening it buys the stop
        alone, which the suite pays for once per served fixture and around 580
        times a run.

        What it costs is wakeups. An idle server spends 0.15% of a core here
        rather than 0.006%: 1.6ms of CPU for every second it stands, against
        0.06ms at half a second. The suite's servers are seconds old and the
        trade is one-sided, but a page server outlives the session that started
        it, so that is the side to weigh if this number moves again.
        """
        super().serve_forever(poll_interval)


class DualStackHTTPServer(LeafHTTPServer):
    """For a bind with ":" in it. The stated-host wildcard is "::" with V6ONLY
    off, which answers IPv4 too (as ::ffff:...), so the URL is reachable
    whichever family the stated name resolves to; a derived IPv6 address just
    needs the family at all."""

    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def server_at(bind: str, port: int, handler) -> LeafHTTPServer:
    """A recorded bind, opened in a family this kernel actually has.

    A kernel with IPv6 switched off refuses AF_INET6 at the socket constructor,
    and the bind that asks for it is the stated-host wildcard — so `--host`, the
    one remedy the skill offers a reader who cannot reach the derived address,
    failed exactly where it is wanted: a headless box is where that address is
    loopback and no browser is local. `0.0.0.0` says what `::` says, every
    interface, in the family that is left, so the wildcard is restated rather
    than refused. Only the wildcard is: a literal v6 address has no reading in
    the other family, and answering it with every interface would widen the
    exposure the recorded address chose.

    The record keeps `::` either way. What a restart has to reproduce is the URL
    an open tab is polling, and that states the host and the port; which family
    carried it is this kernel's answer, asked again on the next serve."""
    if ":" not in bind:
        return LeafHTTPServer((bind, port), handler)
    try:
        return DualStackHTTPServer((bind, port), handler)
    except OSError as e:
        if e.errno != errno.EAFNOSUPPORT or bind != "::":
            raise
        return LeafHTTPServer(("0.0.0.0", port), handler)


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


def _reuse_server(page_dir: Path, host: str | None, standing: bool) -> bool:
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
    print(existing["url"], flush=True)
    print(lifetime_note(page_dir), file=sys.stderr, flush=True)
    return True


def _take_server_lease(page_dir: Path):
    """Take the process lease, or report the concurrent server that won it."""
    lease = open(  # noqa: SIM115 - held until the server process exits
        page_dir / "server.lock", "a+b"
    )
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lease.close()
        winner = running_server(page_dir)
        if winner:
            print(winner["url"], flush=True)
            print(lifetime_note(page_dir), file=sys.stderr, flush=True)
            return None
        sys.exit(f"another server run is serving {page_dir}; re-run")
    return lease


def _bind_server(page_dir: Path, access: dict, token: str, ports: list, lease):
    """Bind the first available port, preserving a recorded address contract."""
    for port in ports:
        try:
            return server_at(
                access["bind"],
                port,
                handler_for(page_dir, token, protocol_version="HTTP/1.1"),
            )
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


def _service_record(access: dict, httpd, standing: bool, claimed: bool) -> dict:
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
    }


def cmd_serve(
    page_dir: Path,
    host: str | None = None,
    standing: bool = False,
    revive: bool = False,
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
    with flocked(transition_lock(page_dir)), PageTransaction(page_dir) as page:
        service = read_json(page_dir / "service.json")
        claimed = _serve_claim(page_dir, page, service, standing, revive)
        if _reuse_server(page_dir, host, standing):
            return

        access = page_access(page_dir, host)
        token = host_key()
        base = 41000 + zlib.crc32(str(page_dir.resolve()).encode()) % 4000
        ports = [access["port"]] if "port" in access else [*range(base, base + 10), 0]
        lease = _take_server_lease(page_dir)
        if lease is None:
            return
        httpd = _bind_server(page_dir, access, token, ports, lease)
        service = _service_record(access, httpd, standing, claimed)
        write_json(page_dir / "service.json", service)
        url = page_url(service["host"], service["port"], token)

    print(url, flush=True)
    print(lifetime_note(page_dir), file=sys.stderr, flush=True)
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
    is the watcher. The contract in
    `../../references/internals/session-lifetime.md` carries the rest of that.

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
    # may not appear inside it: the service prints the URL once it holds the
    # record and the port, and otherwise exits having named its own reason — a
    # stale bind, a taken port, a flag the running server contradicts.
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
    return url, lifetime_note(page_dir)


def cmd_stop(page_dir: Path) -> str:
    """Disable the desired service and wait until its process lease is released."""
    require_cross_process_locking()
    with flocked(transition_lock(page_dir)):
        service = read_json(page_dir / "service.json")
        live = lock_is_held(page_dir / "server.lock")
        if service and service["enabled"]:
            write_json(page_dir / "service.json", {**service, "enabled": False})
        if live:
            # The serving process observes disabled desired state and exits.
            # Taking its lease is the barrier proving every socket is closed.
            with open(page_dir / "server.lock", "a+b") as lease:
                fcntl.flock(lease, fcntl.LOCK_EX)
            return "stopped server"
    return "no server running"
