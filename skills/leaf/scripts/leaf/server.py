"""Server address, access, liveness, and lifetime state."""

import ipaddress
import os
import re
import secrets
import sys
import time
from pathlib import Path

from .files import json_bytes, read_json
from .host import state_home
from .leases import lock_is_held
from .schema import ORPHAN_GRACE_SECS, PREVIEW_FILE
from .service import PageTransaction, claim_is_active, page_claim


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


def preview_metadata(page_dir: Path) -> dict | None:
    """Read the safe identity a developer preview may show in browser chrome."""
    path = page_dir / PREVIEW_FILE
    preview = read_json(path)
    if preview is None:
        return None
    if not isinstance(preview, dict) or preview.get("kind") != "example":
        sys.exit(f"{path}: preview metadata must describe an example")
    for field in ("example", "checkout", "started"):
        if not isinstance(preview.get(field), str) or not preview[field]:
            sys.exit(f"{path}: preview {field} must be a non-empty string")
    commit = preview.get("commit")
    if commit is not None and not (
        isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{7,40}", commit)
    ):
        sys.exit(f"{path}: preview commit must be a Git object name")
    dirty = preview.get("dirty")
    if dirty is not None and not isinstance(dirty, bool):
        sys.exit(f"{path}: preview dirty must be true or false")
    return {
        "kind": "example",
        "example": preview["example"],
        "checkout": preview["checkout"],
        "started": preview["started"],
        **({"commit": commit} if commit is not None else {}),
        **({"dirty": dirty} if dirty is not None else {}),
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
        try:
            staged.write_bytes(json_bytes({"token": secrets.token_urlsafe(16)}))
            staged.chmod(0o600)
            try:
                os.link(staged, path)
            except FileExistsError:
                pass  # someone minted first; theirs is the key, read below
        finally:
            staged.unlink(missing_ok=True)
    return read_json(path)["token"]


def page_url(host: str, port: int, token: str) -> str:
    """The handover URL. A bare IPv6 address is bracketed, since the authority
    already separates its port with a colon."""
    host = f"[{host}]" if ":" in host else host
    return f"http://{host}:{port}/?t={token}"
