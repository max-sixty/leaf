"""Durable and process-owned page servers.

Desired service transitions need only records and leases. HTTP dependencies load
when a server is constructed, so stopping or reviving a service doesn't load a
second server stack in the client process.
"""

import contextlib
import errno
import functools
import json
import logging
import secrets
import socket
import sys
import threading
import time
import zlib
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from urllib.parse import urlsplit

from .detached import Handshake, StartRefused, starting_detached
from .files import read_json
from .harness import Harness, harness_argument, session_harness
from .leases import page_locked, release_lease, take_lease
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
from .service import (
    PageTransaction,
    claim_is_active,
    claimant_matches,
    page_claim,
    prepare_claim,
    same_claim,
)
from .state import require_cross_process_locking, write_json

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
    """One page's HTTP server: uvicorn over the endpoint each request becomes.

    The listening socket is opened here rather than by uvicorn, so the address is
    a fact before anything serves on it — a port the caller records, and a taken one
    that raises out of the constructor instead of exiting the process. Serving hands
    uvicorn a duplicate: the two halves then close their own, and a caller that
    releases the socket cannot pull it out from under a loop still winding down.

    `server_id` names the serving process on every answer. Startup recovery uses it
    to detect a replacement after failure. An ordinary page's durable record survives
    that replacement; only an active private website session loses its record and
    needs an already-presented document to reload. Uvicorn owns signal handling and
    the order of a stop; every page response completes, so no held-open response
    needs a second stop flag or an application signal wrapper. The stop's timing is
    this server's own (`_page_uvicorn`).
    """

    def __init__(self, address, endpoint) -> None:
        import uvicorn

        from .http import page_app

        self.endpoint = endpoint
        self.socket = listening_socket(address[0], address[1])
        self.server_address = self.socket.getsockname()[:2]
        self.server_id = secrets.token_hex(16)
        # Leaf says what it has to say on its own streams: the URL, the lifetime
        # note, and the page's own errors. A server with a logging voice of its own
        # would write a line per refused request into the streams a foreground
        # `server run` is read from. Silenced here because the writes are uvicorn's
        # own and nothing reads them: `log_config=None` configures no handler, which
        # leaves logging's last-resort one printing to stderr.
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            logger = logging.getLogger(name)
            logger.handlers = [logging.NullHandler()]
            logger.propagate = False
        self._uvicorn = _page_uvicorn()(
            uvicorn.Config(
                page_app(endpoint, self),
                log_config=None,
                access_log=False,
                lifespan="off",
                # A page speaks HTTP. Left on, an upgrade would arrive as a scope the
                # page's own gate never sees, ahead of the key and the page's routes.
                ws="none",
            )
        )

    def fileno(self) -> int:
        return self.socket.fileno()

    def serve_forever(self) -> None:
        """Serve on the current thread until `shutdown` or a handled signal."""
        if self._uvicorn.should_exit:
            return
        self._uvicorn.run(sockets=[self.socket.dup()])

    def shutdown(self) -> None:
        """Ask the serving loop to stop, from any thread."""
        self._uvicorn.should_exit = True
        self._uvicorn.wake()

    def server_close(self) -> None:
        """Release the listening socket this server has kept."""
        self.socket.close()
        self.samples.close()


@functools.cache
def _page_uvicorn():
    """Uvicorn's server, stopping when asked rather than on its next poll.

    Uvicorn notices `should_exit` on a 0.1 s tick, then sleeps a fixed 0.1 s after
    asking each connection to finish and polls every 0.1 s until they have. A page
    server that has nothing in flight therefore took ~0.18 s to stop, and the browser
    suite stops one per test. Here the tick also wakes on `wake()`, and the stop waits
    exactly as long as its connections and tasks take, polling at 5 ms. The order is
    uvicorn's: close the listeners, ask each connection to finish, wait for them
    unless a second signal forces the exit, then for the servers. Its graceful-shutdown timeout and lifespan shutdown are absent
    because a page server sets neither. Built on first use, since uvicorn loads only
    when a server is constructed.
    """
    import asyncio

    import uvicorn

    class PageUvicorn(uvicorn.Server):
        _loop = None
        _woken = None

        async def main_loop(self) -> None:
            self._woken = asyncio.Event()
            self._loop = asyncio.get_running_loop()
            counter = 0
            while not await self.on_tick(counter):
                counter = (counter + 1) % 864000
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self._woken.wait(), 0.1)

        def wake(self) -> None:
            if self._loop is None:
                return  # not serving yet; the first tick reads `should_exit`
            # A loop that already closed has already stopped: nothing to wake.
            with contextlib.suppress(RuntimeError):
                self._loop.call_soon_threadsafe(self._woken.set)

        async def shutdown(self, sockets=None) -> None:
            for server in self.servers:
                server.close()
            for sock in sockets or []:
                sock.close()
            for connection in list(self.server_state.connections):
                connection.shutdown()
            state = self.server_state
            while (state.connections or state.tasks) and not self.force_exit:
                await asyncio.sleep(0.005)
            for server in self.servers:
                await server.wait_closed()

    return PageUvicorn


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
        page_options: dict | None = None,
    ) -> None:
        from .http import page_endpoint

        self.token = token or secrets.token_urlsafe(16)
        self.httpd = LeafHTTPServer(
            ("127.0.0.1", port),
            page_endpoint(page_dir, self.token, **(page_options or {})),
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
            self._thread.join()
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
    print(json.dumps({"url": server.url}), flush=True)
    print(TEMPORARY_SERVER_NOTE, file=sys.stderr, flush=True)
    server.run()


def startup_note(page_dir: Path) -> str:
    """Identify the page, vendored bytes, and serving Leaf beside its lifetime."""
    from .layer import provenance_label
    from .registry.storage import layer_metadata

    layer = layer_metadata(page_dir)
    service = read_json(page_dir / SERVICE_FILE) or {}
    # An older live service has no trustworthy runtime identity. Naming this
    # command's payload instead would make the exact stale-server case this note
    # exists to expose look current merely because a newer client inspected it.
    runtime = service.get("runtime") or {}
    fingerprint = layer["fingerprint"]
    # After the lifetime line, not before: a foreground serve's first line of
    # stderr is the lifetime, and its readers take exactly one.
    return "\n".join(
        line
        for line in (
            lifetime_note(page_dir),
            loopback_note(page_dir),
            f"page     {page_dir}",
            f"layer    {fingerprint} ({provenance_label(layer.get('producer', {}))})",
            (
                f"runtime  {runtime.get('path', 'unknown payload')} "
                f"({provenance_label(runtime)})"
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
    harness: Harness | None,
) -> bool:
    """Validate this launch, for `harness`, against desired state and page
    ownership."""
    if revive and (not service or not service["enabled"]):
        sys.exit("service was stopped; not reviving")

    claimed = bool(
        not standing
        and harness is not None
        and claimant_matches(page.active_claim, harness)
    )
    if not standing and harness is not None and not claimed:
        sys.exit(
            f"this harness session no longer owns {page_dir}; the server was not started"
        )
    if revive and service and service["lifetime"] == "session" and not claimed:
        sys.exit("this session no longer owns the service; not reviving")
    return claimed


def _announce_server(page_dir: Path, url: str) -> bool:
    """Print a committed foreground URL, then its lifetime note."""
    print(json.dumps({"url": url}), flush=True)
    print(startup_note(page_dir), file=sys.stderr, flush=True)
    return True


def _reuse_server(page_dir: Path, host: str | None, standing: bool) -> str | None:
    """Read a compatible running server's URL, or say a fresh bind is needed."""
    existing = running_server(page_dir)
    if not existing:
        return None
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
    return existing["url"]


def _take_server_lease(page_dir: Path):
    """Take the process lease after checking reuse under the page lock."""

    def clear_identity(held):
        held.truncate(0)
        held.flush()

    lease = take_lease(page_dir / SERVER_LOCK, prepare=clear_identity)
    if lease is not None:
        return lease
    sys.exit(f"another server run is serving {page_dir}; re-run")


def _bind_server(page_dir: Path, access: dict, endpoint, ports: list):
    """Bind the first available port, preserving a recorded address contract."""
    for port in ports:
        try:
            return LeafHTTPServer((access["bind"], port), endpoint)
        except OSError as error:
            if error.errno == errno.EADDRINUSE and "port" not in access:
                continue
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
        "server_id": httpd.server_id,
    }


def cmd_serve(
    page_dir: Path,
    host: str | None = None,
    standing: bool = False,
    revive: bool = False,
    *,
    harness: Harness | None,
    handshake: Handshake | None = None,
    acquire: bool = False,
    prepared_claim: dict | None = None,
) -> None:
    """Prepare a serving resource for `harness`, the session its starter acts
    for, then publish it and ownership on acceptance.

    The page lock serializes preparation through commitment, so another start
    cannot adopt an uncommitted listener. Binding and delivery preparation happen
    before publication. Only the accepted commit takes a claim and enables a new
    service, in a short page transaction. The serving row producer is prepared
    privately with its server incarnation and starts only after commitment,
    outside the page lock. The live lease names this exact HTTP incarnation;
    private preparation cannot advertise a retained service or neighbor row.
    A revival takes no acquisition.
    """
    from .http import page_endpoint
    from .layer import payload_provenance
    from .server_rows import RowPublisher

    require_cross_process_locking()
    lease = None
    httpd = None
    delivery = (
        harness.preparing_delivery()
        if acquire and not standing and harness is not None and handshake is None
        else contextlib.nullcontext()
    )
    try:
        with delivery, page_locked(page_dir):
            if acquire and not standing and harness is not None:
                prepared_claim = prepared_claim or prepare_claim(harness, page_dir)
            previous_service = service = read_json(page_dir / SERVICE_FILE)
            with PageTransaction(page_dir) as page:
                claimed = (
                    bool(not standing and harness is not None)
                    if acquire
                    else _serve_claim(
                        page_dir, page, service, standing, revive, harness
                    )
                )
            url = _reuse_server(page_dir, host, standing)
            if url is None:
                access = page_access(page_dir, host)
                token = host_key()
                endpoint = page_endpoint(page_dir, token)
                base = 41000 + zlib.crc32(str(page_dir.resolve()).encode()) % 4000
                ports = (
                    [access["port"]]
                    if "port" in access
                    else [*range(base, base + 10), 0]
                )
                lease = _take_server_lease(page_dir)
                httpd = _bind_server(page_dir, access, endpoint, ports)
                lease.write(httpd.server_id.encode())
                lease.flush()
                rows = RowPublisher(page_dir, httpd.server_id)
                service = _service_record(
                    access,
                    httpd,
                    standing,
                    claimed,
                    payload_provenance(include_path=True),
                )
                url = page_url(service["host"], service["port"], token)

            def commit() -> dict:
                try:
                    with PageTransaction(page_dir) as page:
                        if acquire and claimed:
                            with page.publishing_claim(prepared_claim) as (_, claim):
                                if httpd is not None:
                                    write_json(page_dir / SERVICE_FILE, service)
                        else:
                            _serve_claim(
                                page_dir, page, service, standing, revive, harness
                            )
                            claim = page.claim if claimed else None
                            if httpd is not None:
                                write_json(page_dir / SERVICE_FILE, service)
                        return {"url": url, "claim": claim}
                except BaseException:
                    # A freshly bound resource is ours to withdraw. Reused servers
                    # have no mutation to undo. Once acquisition published, owner
                    # cleanup instead governs the accepted, unconfirmed start.
                    if httpd is not None and (
                        prepared_claim is None
                        or not same_claim(page_claim(page_dir), prepared_claim)
                    ):
                        if previous_service is None:
                            (page_dir / SERVICE_FILE).unlink(missing_ok=True)
                        else:
                            write_json(page_dir / SERVICE_FILE, previous_service)
                    raise

            if handshake is not None:
                announced = handshake.announce(
                    {"url": url, "claim": prepared_claim if acquire else None},
                    commit=commit,
                )
            else:
                commit()
                announced = _announce_server(page_dir, url)
        if httpd is None or not announced:
            return
        threading.Thread(target=rows.run, daemon=True).start()
        threading.Thread(
            target=stop_when_service_ends,
            args=(page_dir,),
            daemon=True,
        ).start()
        httpd.serve_forever()
    finally:
        if httpd is not None:
            httpd.server_close()
        if lease is not None:
            release_lease(lease)


@dataclass(frozen=True)
class PageStart:
    """A prepared serving address and acquisition, committed on context exit.

    Consumers capture ownership while preparation is still unpublished. They
    hand the address to the user only after the context confirms commitment.
    """

    url: str
    claim: dict | None
    page: Path

    @property
    def note(self) -> str:
        return startup_note(self.page)


@contextlib.contextmanager
def _starting_server(
    page_dir: Path,
    host: str | None = None,
    standing: bool = False,
    revive: bool = False,
    *,
    harness: Harness | None,
    acquire: bool = False,
    claim: dict | None = None,
):
    """Prepare a private serving resource and expose its owner before accepting."""
    require_cross_process_locking()
    with starting_detached(
        [
            "server",
            "_serve",
            str(page_dir),
            *(["--host", host] if host else []),
            *(["--standing"] if standing else []),
            *(["--revive"] if revive else []),
            *(["--acquire"] if acquire else []),
            *(["--claim", json.dumps(claim)] if claim is not None else []),
            "--harness",
            harness_argument(harness),
        ],
        harness=harness,
        what=f"the server for {page_dir}",
    ) as ready:
        yield PageStart(ready["url"], ready["claim"], page_dir)


def start_server(
    page_dir: Path,
    host: str | None = None,
    standing: bool = False,
    revive: bool = False,
    *,
    harness: Harness | None,
) -> PageStart:
    """Start or reuse a server for `harness` without acquiring page ownership.

    A revival commits only while the desired service remains enabled and
    `harness`'s session still owns it. The detached producer checks those facts
    while holding
    the page transition lock. Every revival retains the recorded address.
    """
    with _starting_server(page_dir, host, standing, revive, harness=harness) as started:
        pass
    return started


@contextlib.contextmanager
def claim_and_start(page_dir: Path, host: str | None = None, standing: bool = False):
    """Prepare delivery and serving, expose their acquisition, then commit.

    Preparation failures and cancellation before acceptance publish no takeover.
    The caller captures its exact acquisition inside this context and exposes the
    URL only after exit confirms publication. Once accepted, cancellation cannot
    restore a superseded owner; the captured acquisition governs owner cleanup.
    """
    harness = session_harness()
    delivery = (
        harness.preparing_delivery()
        if not standing and harness is not None
        else contextlib.nullcontext()
    )
    with delivery:
        claim = prepare_claim(harness, page_dir) if not standing and harness else None
        try:
            with _starting_server(
                page_dir, host, standing, harness=harness, acquire=True, claim=claim
            ) as ready:
                yield ready
        except BaseException:
            if claim is not None:
                cmd_stop(page_dir, owner=claim)
            raise


class _StopScope(Enum):
    ANY_OWNER = auto()


def cmd_stop(
    page_dir: Path,
    restart: str | None = None,
    *,
    owner: dict | None | _StopScope = _StopScope.ANY_OWNER,
) -> bool:
    """Disable the desired service, wait until its process lease is released, and
    say whether a server was running.

    The barrier is taking the lease under the page lock, without waiting:
    held together, they keep a new start out of the gap between the old server's
    exit and this return. The wait between attempts is outside the transition,
    since a serving process may need it to withdraw an uncommitted start.

    `restart` marks the disabled record as `restarting_server`'s own. A plain stop
    writes an unmarked one even over a service already down, so a stop made while
    a restart holds the service down takes the restart's claim to it away. The
    record is this stop's to write once, on its first pass: a later pass only
    disables a service something enabled meanwhile, and keeps whatever mark the
    record then carries, so a restart waiting out the old server's lease does not
    write its mark back over a plain stop that landed during the wait."""
    require_cross_process_locking()
    stopped = False
    first = True
    while True:
        # A resource owner's cleanup cannot disable its successor's service.
        # Check that identity in every transition, including after waiting for
        # the former server to exit. Explicit stops supply no owner restriction.
        with (
            page_locked(page_dir),
            PageTransaction(page_dir)
            if owner is not _StopScope.ANY_OWNER
            else contextlib.nullcontext() as page,
        ):
            if owner is not _StopScope.ANY_OWNER and not same_claim(page.claim, owner):
                return stopped
            # The server may release its lease immediately after we disable it.
            stopped = stopped or running_server(page_dir) is not None
            service = read_json(page_dir / SERVICE_FILE)
            if service and first:
                disabled = {
                    **{
                        key: value for key, value in service.items() if key != "restart"
                    },
                    "enabled": False,
                    **({"restart": restart} if restart else {}),
                }
                if disabled != service:
                    write_json(page_dir / SERVICE_FILE, disabled)
            elif service and service["enabled"]:
                write_json(page_dir / SERVICE_FILE, {**service, "enabled": False})
            first = False
            lease = take_lease(page_dir / SERVER_LOCK)
            if lease is not None:
                release_lease(lease)
                return stopped
        time.sleep(0.05)


@contextlib.contextmanager
def restarting_server(page_dir: Path):
    """Hold a page's service down for the block, and start it again after.

    `page init` re-vendors inside this, since no server runs across a re-vendor:
    the layer it serves and the code it runs are both what the re-vendor replaces.
    The service goes down through `cmd_stop`, since a disabled service is what keeps
    a revival and a second start out of the block. A watching `leaf wait` goes on
    watching through the gap: a stopped service does not end a wait
    (`session-lifetime.md`, "Lifetime").

    Only an enabled service comes back, under its recorded lifetime and address; a
    stopped one stays stopped, and a page never served has nothing to hold down. A
    session service comes back only for the session holding its claim, and claims
    nothing to do it: the claim is still that session's, and taking it again would
    reopen a turn the Stop hook closed. Another live session's service is refused
    before anything stops, since only that session could start it again. One whose
    session has ended has no owner to come back for, so it is stopped and stays
    stopped for the next `server start` to claim.

    The service comes back only after a block that completed. The caller decides
    whatever can refuse before it enters, while the page is still served; a block
    that fails anyway, or is interrupted, leaves a page nobody vouches for, and a
    server started over it could run this Leaf's code against the layer the page
    kept. So the service stays stopped, and says so.

    Nor does it come back over a stop made during the block. The disabled record
    this writes carries a mark of its own, which any other stop replaces, and the
    service is enabled again only while the mark is still there. The start that
    follows is a revival, "only if still enabled", so a stop after that is kept
    too. A start the server then refuses leaves the service enabled and down, as
    a dead server is, for a watching `leaf wait` to revive or report. Nothing but
    this block reads the mark, so one a killed restart leaves behind is inert: the
    next start or stop writes a record without it.
    """
    service = read_json(page_dir / SERVICE_FILE)
    if not service or not service["enabled"]:
        yield
        return
    standing = service["lifetime"] == "standing"
    comes_back = standing or _restarts_for_this_session(page_dir)
    mark = secrets.token_hex(8) if comes_back else None
    cmd_stop(page_dir, restart=mark)
    if not comes_back:
        print(
            f"{page_dir}'s server belonged to a session that has ended, so it stays "
            f"stopped; `leaf server start {page_dir}` serves it for this one.",
            file=sys.stderr,
        )
        yield
        return
    try:
        yield
    except BaseException:
        print(
            f"{page_dir}'s server stays stopped; `leaf server start {page_dir}` "
            "serves it again.",
            file=sys.stderr,
        )
        raise
    with page_locked(page_dir):
        service = read_json(page_dir / SERVICE_FILE)
        resumed = bool(service and service.get("restart") == mark)
        if resumed:
            del service["restart"]
            write_json(page_dir / SERVICE_FILE, {**service, "enabled": True})
    if not resumed:
        print(
            f"{page_dir}'s server was stopped while it was re-vendored, so it stays "
            "stopped.",
            file=sys.stderr,
        )
        return
    try:
        start_server(
            page_dir, standing=standing, revive=True, harness=session_harness()
        )
    except StartRefused as error:
        sys.exit(f"{page_dir}'s server did not start again: {error}")


def _restarts_for_this_session(page_dir: Path) -> bool:
    """Whether this command may restart a session service: its claim is this
    session's. False when no live session holds it any more; an exit when
    another one does."""
    claim = page_claim(page_dir)
    if not claim_is_active(claim):
        return False
    harness = session_harness()
    if harness is None or not claimant_matches(claim, harness):
        sys.exit(
            f"{page_dir} is served for another session, and only that session can "
            "start its server again; re-vendor it from there, or take the page over "
            f"first with `leaf server start {page_dir}`"
        )
    return True
