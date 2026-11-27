"""The page server's records and the readings taken from them: the page's desired
service (`SERVICE`), the key every page this machine serves is read with (`ACCESS`),
the address and URL a page is reached at, and whether its server runs
(`running_server`). The serving process's own lifetime is
`server_lifetime`'s."""

from __future__ import annotations

import ipaddress
import os
import re
import secrets
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from leaf.base.leases import lock_is_held
from leaf.base.refusals import Refused
from leaf.base.schema import PREVIEW_FILE, SERVER_LOCK, SERVICE_FILE
from leaf.base.service import PREVIEW
from leaf.base.state import (
    STRING,
    Record,
    described,
    flocked,
    hold_mode,
    object_schema,
    state_home,
)

if TYPE_CHECKING:
    from leaf.base.record_types import AccessRecord, ServiceRecord

    class PageAddress(TypedDict):
        host: str
        bind: str

    class RunningService(ServiceRecord):
        url: str


SERVICE: Record[ServiceRecord] = Record(
    "service",
    described(
        "The page's desired service, in the page directory's `service.json`, which "
        "`hosting.py` writes.",
        object_schema(
            {
                "host": described("The address a URL names.", STRING),
                "bind": described("The address the server binds.", STRING),
                "port": described(
                    "The port the server listens on.", {"type": "integer"}
                ),
                "enabled": described(
                    "Whether the page should be served.", {"type": "boolean"}
                ),
                "lifetime": described(
                    "Whether the server stops when no live session claims the page, "
                    "or runs until `leaf server stop`.",
                    {"enum": ["session", "persistent"]},
                ),
                "runtime": described(
                    "The Leaf that served it (`layer.payload_provenance`).",
                    {"type": "object"},
                ),
                "server_id": described(
                    "The serving incarnation the server lease names.", STRING
                ),
            },
            {
                "restart": described(
                    "The mark `hosting.restarting_server` leaves while it holds a "
                    "served page down to restart it.",
                    STRING,
                )
            },
        ),
    ),
    since=13,
)
ACCESS: Record[AccessRecord] = Record(
    "access",
    described(
        "The key every page this machine serves is read with (`host_key`), in the "
        "state home's `access.json`.",
        object_schema({"token": STRING}),
    ),
    since=13,
)
# The hostname the user reaches every page on this machine by, stated once in the
# environment `leaf` runs in (`page_access`).
HOST_VARIABLE = "LEAF_HOST"


def read_service(page_dir: Path) -> ServiceRecord | None:
    """The page's desired service (`service.json`), or None where there is none this
    version can read."""
    return SERVICE.read(page_dir / SERVICE_FILE)


def write_service(page_dir: Path, service: ServiceRecord) -> None:
    """The one writer of the page's desired service."""
    SERVICE.write(page_dir / SERVICE_FILE, service)


def running_server(page_dir: Path) -> RunningService | None:
    """The desired service, while its exact serving incarnation holds the lease.

    A preparation clears old lease metadata before taking an exclusive lock, then
    names its privately bound HTTP server. Only a matching committed service can
    appear live, so a retained desired record cannot lend its identity to revival.
    """
    if not lock_is_held(page_dir / SERVER_LOCK):
        return None
    service = read_service(page_dir)
    if not service or not service["enabled"]:
        return None
    try:
        held_incarnation = (page_dir / SERVER_LOCK).read_bytes()
    except FileNotFoundError:
        return None
    if held_incarnation != service["server_id"].encode():
        return None
    return {
        **service,
        "url": page_url(service["host"], service["port"], host_key()),
    }


def preview_metadata(page_dir: Path) -> dict | None:
    """The identity a developer preview shows in browser chrome, as
    `leaf-dev preview` wrote it, or None for a page that is not a preview.
    The script writes only what the chrome shows."""
    return PREVIEW.read(page_dir / PREVIEW_FILE)


def served_lifetime(page_dir: Path) -> str:
    """What ends this server, said at the moment it starts: `session` or
    `persistent`.

    The two lifetimes are indistinguishable from the terminal — same command,
    same URL — and the difference only shows up hours later, when one process is
    gone and the other isn't. So the serve states which it is beside the URL
    rather than leaving it to be discovered, and names the command where that is
    the only way out (`hosting.server_reading`).

    Read from service.json, the one place a lifetime is written down. The record
    lands before the URL is printed and survives an explicit stop, so a restart
    restores the same lifetime as well as the same URL."""
    service = read_service(page_dir)
    return service["lifetime"] if service else "session"


def loopback_only(page_dir: Path) -> bool:
    """Whether the URL just printed stays on this machine, said before it is handed
    over rather than after the user reports a dead link.

    A derived address is loopback whenever SSH_CONNECTION is absent, and that is
    not only a session sitting with its user: a scheduler, a daemon, or a
    detached background job is remote from the user without having arrived over
    SSH, and takes the same branch. Neither the URL nor the lifetime says
    the address is machine-local, so the one user who cannot report it is the
    one who receives it.

    Read from the recorded bind rather than from SSH_CONNECTION, because the
    record is what the server bound: a restart re-serving a loopback record says
    the same thing in an environment that would derive something else. A stated
    host binds the wildcard, which is not loopback, and says nothing."""
    service = read_service(page_dir)
    if service is None:
        return False
    try:
        return ipaddress.ip_address(service["bind"]).is_loopback
    except ValueError:
        return False


def page_access(page_dir: Path, host: str | None = None) -> ServiceRecord | PageAddress:
    """Where a page is reached: the name its URL carries and the interface its
    server binds. The key that URL also carries is the machine's — `host_key`.

    Derived — no `host` — the address is read from SSH_CONNECTION, whose third
    field is this machine as the client just reached it: a route the session
    carrying the request has already demonstrated, rather than a guess about what
    resolves from where. No SSH_CONNECTION is the same answer for a user on
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

    A user who reaches every page by one name, such as a phone on their tailnet,
    states it once in `LEAF_HOST` (`HOST_VARIABLE`), which a page with no record
    takes as if `--host` had named it. Like `--host`, it outranks SSH_CONNECTION:
    the user named the route their browser takes, which the session's route may
    not be.

    Recorded once and kept. `start_server` restarts a dead server by re-running
    `server run` bare, and a fresh address there would leave the user's open page
    polling a URL that no longer answers — which is why a stated host is recorded
    here rather than passed per run. For the same reason a record outranks
    `LEAF_HOST`: a page first served elsewhere, or before the user set it, keeps
    its address until a `--host` restates it."""
    access: ServiceRecord | PageAddress | None = read_service(page_dir)
    if access and not host:
        return access
    if stated := host or os.environ.get(HOST_VARIABLE):
        # The record's one door checks what it keeps: a scheme, a port, or a
        # path pasted into --host would mint a URL no browser resolves, handed
        # to the one user who can't report it.
        try:
            ipaddress.ip_address(stated)
        except ValueError:
            if not re.fullmatch(r"[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?", stated):
                source = f"--host {host}" if host else f"{HOST_VARIABLE}={stated}"
                raise Refused(
                    f"{source}: not a hostname or IP address "
                    "(no scheme, no port — leaf picks the port)"
                ) from None
        # Over the record, not in place of it: a --host restates where the page
        # is reached, and the record's other facts — the exact port an open tab
        # polls, the persistent lifetime — restate nothing and must survive, or
        # the recovery this flag exists for demotes the dashboard it recovers.
        access = {**(access or {}), "host": stated, "bind": "::"}
    else:
        ssh = os.environ.get("SSH_CONNECTION", "").split()
        addr = ssh[2] if len(ssh) == 4 else "127.0.0.1"
        access = {"host": addr, "bind": addr}
    return access


def host_key() -> str:
    """The key every page this machine serves is read with, minted at the first
    `server run` and kept in the state home. It rides in the URL Claude hands
    over, `authorized` puts it in a cookie on arrival, and the runtime's bootstrap
    takes it back out of the address bar, so the link a user copies from the tab
    is the bare address and reaches only a browser already holding the cookie.

    The key exists because serving anywhere but loopback puts an unauthenticated
    writer on whatever network reached us, and `POST /api/event` appends to a log
    that outranks the document and replays onto every version after.

    One key for the machine rather than one per page, because every page here
    goes to the same user — the one person the agent is working with. A page
    has nothing to keep from another page's user, which is what lets the
    list of other pages (`/api/pages`) link them with that key. The cookie name derives from the key
    (`PageEndpoint.key_cookie`), so a keyed arrival authorizes bare links to
    other same-key listeners on the host. Temporary previews with different keys
    get different cookie names and cannot overwrite one another's authorization.

    The cost is that handing out any page's URL hands out every page on the
    machine, present and future. Leaf has one user; giving it a second
    means scoping the key back to the page first.

    The cookie is a second copy of that cost: a browser's jar is port-blind, so
    any server the user visits on the same host string — a dev server on
    localhost:3000 — receives the key with their request. Considered and kept:
    every cookie-borne credential has this property (a port-scoped name or a
    derived value is still delivered to every port and replayable against this
    one), and dropping the cookie for a key-in-URL scheme breaks the thing the
    cookie exists for — the page's static asset references (/leaf.js, a module's
    ../leaf.js import) can carry no query, so every asset would need the auth
    the redirect-following request has. The boundary is the host string; a
    user on a shared or hostile-local-service machine narrows it by serving
    on a name other servers don't share (--host).

    The cookie outlives the browser session (`KEY_COOKIE_MAX_AGE`), because the
    address bar no longer holds the key: a restored tab or a bookmarked bare
    address after a restart would otherwise be refused. Each handover link renews
    it, so the added cost is that same-host servers keep receiving the key for
    that long after the last handover, rather than until the browser quits.

    Minted under a lock, so two first serves racing on a fresh machine agree on
    whichever won. Each keeping its own would have their servers overwrite the one
    shared cookie in turn, for as long as both ran. A file holding a record this
    Leaf doesn't read, at another `ACCESS` format, is replaced, which signs out the
    tabs that held its key."""
    path = state_home() / "access.json"
    if (access := ACCESS.read(path)) is None:
        with flocked(path.with_name("access.lock")):
            if (access := ACCESS.read(path)) is None:
                access = ACCESS.write(path, {"token": secrets.token_urlsafe(16)})
    # Whoever made the file, only the user reads the key.
    hold_mode(ACCESS.file(path), 0o600)
    return access["token"]


def page_origin(host: str, port: int) -> str:
    """The origin a page's URL names. A bare IPv6 address is bracketed, since the
    authority already separates its port with a colon."""
    host = f"[{host}]" if ":" in host else host
    return f"http://{host}:{port}"


def page_url(host: str, port: int, token: str) -> str:
    """The handover URL."""
    return f"{page_origin(host, port)}/?t={token}"
