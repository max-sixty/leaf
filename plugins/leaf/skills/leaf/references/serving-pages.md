# Serving pages

Read this for an exported deliverable, an unreachable URL, `--host`, a standing
page, re-vendoring, or a page previously owned by another session.

## Exported files

When `$ARGUMENTS` asks for `--export`, initialize, catalog, author, and stamp as
usual, then run:

```bash
leaf version export <page> -o <file>
```

Hand back the `file://` URL. Do not start a server or wait. An export is the page
as the browser draws it, with standing decisions applied, comments and live
handlers removed, and controls replaced by their answers. Write it where the
project keeps user-facing artifacts. A live page can also be exported without
ending its loop.

## Address and authentication

By default Leaf serves on the address the session arrived through: the SSH
destination for an SSH session, otherwise loopback. Preserve the exact URL from
`server start`; its key is required for the document, assets, state reads, and
event writes. The browser stores the key in a cookie. The key is machine-wide,
so sharing one page URL grants access to every Leaf page on that machine.

Leaf serves only on networks the machine already joins and creates no public
tunnel. Binding beyond loopback exposes the port to that network.

`<page>/service.json` records address, bind, port, enabled state, and lifetime so
a restart reproduces the URL an open tab holds. Delete it only when
intentionally deriving a new address and lifetime. The access key lives in
Leaf's state home rather than in the page.

## Unreachable URLs and `--host`

Only the user's browser can establish that a URL is unreachable. When they say
it does not load, stop the server and restart it with a hostname their browser
can use:

```bash
leaf server stop <page>
leaf server start <page> --host <reachable-name>
```

`--host` places that name in the URL and binds every interface; the name need
not resolve locally. An overlay-network hostname is appropriate when that
network is the shared route. If no network route works, export the version as a
file.

## Re-vendoring and layer epochs

Re-vendor a served page only through the quiescent sequence:

```bash
leaf server stop <page>
leaf page init <page>
leaf server start <page>
```

Stopping disables desired service and waits until the old process releases its
listening socket, accepted connections, and live lease. Initialization preserves
the recorded address, port, lifetime, and page status; restarting restores the
same URL. Each successful initialization writes a new layer epoch into the
runtime and registry, so an open or half-loaded tab from the previous contract
reloads before its next read or event enters the replacement server.

## Page lifetime

On a page with no recorded lifetime, a normal `server start` from an agent
session chooses a session lifetime. Its process retires when no live session
claims the page, but desired service remains enabled so a successor's live
`leaf wait` can revive the exact URL. Only `leaf server stop <page>` disables a
service.

`server start --standing`, or a serve started from the user's own shell, chooses
a standing lifetime. Its process ignores session claims and remains live between
sessions. Tell the user when starting one because they inherit a process only
`server stop` ends. A wait watching any enabled page revives its server under the
recorded lifetime if the process dies.

## Resuming a standing or foreign page

The host selects exactly one successor session; neither `page state` nor a bare
read grants exclusive ownership. The selected successor first runs:

```bash
leaf page state <page>
```

Read the active revision and its stamped version if any, standing decisions, open asks, each thread's
exchange, record debt, and `measurement_lag` for pinned figures whose sources have run
again. If the
state reports a live watcher, the host ends that watcher before continuing. The
successor then runs `leaf wait <page>`, whose named wait claims the page for that
session. Starting a server when the standing one is already live prints its URL
without changing its lifetime.

Do not stop a standing server when the session ends. Use `leaf status <page>
idle` only when the page itself is finished; simply ending the session releases
the claim and leaves enabled service available for the next selected successor.
