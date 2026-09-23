# Serving pages

## Exported files

When `$ARGUMENTS` asks for `--export`, initialize, query the page registry,
author, and stamp as usual, then run:

```bash
leaf version export <page> -o <file>
```

Hand back the `file://` URL. Do not start a server or wait. An export keeps the
drawn page, standing Asks, and inline conversation messages. It removes
live chrome and handlers; native disclosures still work. Write it where the
project keeps user-facing artifacts. A live page can also be exported without
ending its loop.

When the deliverable needs local controls, page-owned computation, or navigation, use
the explicit offline-interactive mode instead:

```bash
leaf version export <page> -o <file> --interactive
```

It runs the captured revision's modules and normal Leaf renderers without host chrome
or network access. Accepted page state and contract-declared data fragments are
included, while actions and requests that need an agent or server are unavailable
before dispatch. The default command remains the script-free record.

## Address and authentication

By default Leaf serves on the address the session arrived through: the SSH
destination for an SSH session, otherwise loopback. Preserve the exact URL from
`server start`; its key is required for the document, assets, state reads, and
event writes. The browser stores the key in a cookie. The key is machine-wide,
so sharing one page URL grants access to every Leaf page on that machine.

Leaf serves only on networks the machine already joins and creates no public
tunnel. Binding beyond loopback exposes the port to that network.

A page's URL is its host and port, which the first serve records in
`<page>/service.json`, and the machine's key, which the state home keeps. None of
them belongs to the server process, so every later serve of the page answers at the
URL the user already has: a stop and start, a re-vendor, a revival by `leaf wait`,
or a `server start` after a reboot. Only two things change the URL: `--host`
replaces its name and keeps its port, and deleting `service.json` derives a new
address and lifetime from the current session. If another process holds the
recorded port, `server start` refuses rather than moving.

## Unreachable URLs and `--host`

A serve that binds loopback says so on the line after the lifetime note. That is
the no-SSH default above, and it covers sessions that are remote from the user
without having arrived over SSH: a scheduler, a daemon, a detached background job.
When that line appears and the session is not one the user is sitting at, ask them
for a name their browser routes to and serve on it before handing the URL over, or
export the version as a file.

Otherwise only the user's browser can establish that a URL is unreachable. When
they say it does not load, stop the server and restart it with a hostname their
browser can use:

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

Stopping disables desired service and waits for the old process to retire.
Initialization preserves the recorded address, lifetime, and page status, and
writes a new layer epoch so an open tab reloads onto the new layer rather than
posting into it.

## Page lifetime

On a page with no recorded lifetime, a normal `server start` from an agent
session chooses a session lifetime. Its process retires when no live session
claims the page, but desired service remains enabled: a `leaf wait` watching any
enabled page revives its server under the recorded lifetime and exact URL if the
process dies. Only `leaf server stop <page>` disables a service.

`server start --standing`, or a serve started from the user's own shell, chooses
a standing lifetime. Its process ignores session claims and remains live between
sessions. Tell the user when starting one because they inherit a process only
`server stop` ends, and do not stop it because a session's work is over: ending
the session releases the claim and leaves the service enabled.

`server run --temporary` is the browser-harness boundary. It serves on loopback
until that foreground command exits, with a per-server access key and no claim or
`service.json`. The serve cannot be revived and does not enroll its browser events
in agent-task delivery.

## Resuming a standing or foreign page

The host selects exactly one successor session; neither `page state` nor a bare
read grants exclusive ownership. The selected successor first runs:

```bash
leaf page state <page>
```

Read `content` for the current document and its construction origins, then the
active revision, open Asks, current conversation state, and `measurement_lag` for
figures whose sources have run again. Before editing, follow
`authoring-revisions.md`'s "Read before editing" section. If the state reports a live
watcher, the host ends that watcher before continuing. The
successor then runs `leaf wait <page>`, whose named wait claims the page for that
session. Starting a server when the standing one is already live prints its URL
without changing its lifetime.
