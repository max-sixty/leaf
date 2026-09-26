# Serving pages

## Inspecting interactions

For a served page, read the private diagnostic stream while reproducing a user or
test-agent path:

```bash
leaf interactions <page> --follow
```

It combines browser gestures and server request outcomes in delivery order. Browser
rows carry a tab session, event time, and sequence; large values appear as ordered
`interaction_part` rows whose `json` fields concatenate to the original row.
The semantic decisions remain in `leaf events <page>`. See [page-storage.md](../scripts/leaf/page-storage.md)
for the file contract. The public site stores its browser batches in Workers
Observability; `worker/README.md` describes lookup by session reference.

## Exported files

When `$ARGUMENTS` asks for `--export`, build the page as a finished record (the
main skill's "Operate", step 3), since only a stamped version exports, then run:

```bash
leaf version export <page> -o <file>
```

Hand back the `file://` URL. Do not start a server or wait. The file opens
offline and runs the page's own runtime against the captured revision and its
state: widgets, local controls, and page-owned computation work as served. No host
stands behind it, so thread and any action or request that needs an agent or
server are unavailable. A page that declares a live specimen needs a server and
cannot be exported. Write the file where the project keeps user-facing artifacts.
A live page can be exported without ending its loop.

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
or a `server start` after a reboot. `--host` is the one thing that moves a URL: it
replaces the name and keeps the port. Deleting `service.json` makes the next serve
derive the address and lifetime again from the session running it, which gives the
same URL only when that session arrived the same way and the port derived from the
page's path is free. If another process holds the recorded port, `server start`
refuses rather than moving.

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

Re-vendor a served page with `leaf page init <page>` alone. It checks the
incoming layer against the page first, so a refused re-vendor leaves the running
server as it was. An admitted one takes the server down, re-vendors, and starts
the server again at the recorded URL under its recorded lifetime, and a `leaf wait`
watching the page carries on through the restart. A page whose server was stopped
stays stopped. Re-vendor a session's page from the session that holds it: init
refuses a page that another live session serves. A page whose session has ended
stays stopped after init, and `leaf server start` then serves it for this session.
Initialization preserves the page status and writes a new layer epoch, so an open
tab reloads onto the new layer rather than posting into it.

## Page lifetime

On a page with no recorded lifetime, a normal `server start` from an agent
session chooses a session lifetime. Its process retires when no live session
claims the page, but desired service remains enabled: a `leaf wait` watching any
enabled page revives its server under the recorded lifetime and exact URL if the
process dies, and ends if that revival does not hold. Only `leaf server stop
<page>` disables a service, and a `leaf wait` goes on watching a stopped page until
it is idle.

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

Resume a page from one session only. A named `leaf wait <page>` moves the claim to
whichever session runs it, and a watcher another session still runs stops watching
that page. First read the page:

```bash
leaf page state <page>
```

Read `content` for the current document and its construction origins, then the active
revision, open Asks, current thread state, and `measurement_lag` for figures
whose sources have run again. Before editing, follow `authoring-revisions.md`'s "Read
before editing" section. Then run `leaf wait <page>` to claim it. Starting a server
when the standing one is already live prints its URL without changing its lifetime.
