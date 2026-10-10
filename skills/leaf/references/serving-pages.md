# Serving pages

Serve and hand over by the selected harness contract. Use this reference for
export, address changes, re-vendoring, and resuming a page. Keep the exact keyed
URL returned by `leaf server start`.

## Exported files

When `$ARGUMENTS` asks for `--export`, build the page as a finished record (the
main skill's "Operate", step 3), since only a stamped version exports, then run:

```bash
leaf page export <page> -o <file>
```

Hand back the `file://` URL. Do not start a server or wait. The file opens
offline and runs the page's own runtime against the captured revision and its
state: widgets, local controls, and page-owned computation work as served. Embedded
images, fonts, and recordings need JavaScript; with scripts disabled, the file keeps
authored text, layout, and image alt text and explains the unavailable graphics. No host
stands behind it, so threads and any action that needs an agent or server are
unavailable. A page that declares a live sample needs a server and
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

A page retains its host and port in `<page>/service.json`, and its key in the
machine's state home. Re-serving, re-vendoring and reviving it use the same URL.
`--host` changes the hostname while preserving the port. A recorded port occupied
by another process makes serving refuse; it never silently moves the page.

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

After a Leaf update or a checkout runtime edit, re-vendor the page from its
owning session:

```bash
leaf page init <page>
```

Init validates incoming layer declarations and file destinations first; refusal
leaves the page and server unchanged. An unchanged layer and serving payload
preserve installed files and the running server without reloading open tabs.
A layer, server-code, dependency, package selection, or installed-file change
writes a new layer epoch, restarts a running server at its recorded URL and
lifetime, and reloads open tabs. Page status is preserved, and a stopped server
stays stopped. For a session service, init refuses a change while another live
session owns it. If its previous session has ended, init leaves it stopped;
serve it from the session that will now own it. An enabled standing service
restarts independently of session ownership.

Serving an older runtime refuses with the same init command. If restart fails,
follow init's diagnostic; an enabled page's watcher also tries one revival.
Init reads the log under Leaf's kernel transport contract. If an earlier page's
log cannot be read or the page misbehaves after an update, initialize a new
directory, write the current page there, and hand over its new URL.

## Page lifetime

A normal `server start` from an agent session claims the page and connects the
selected harness's delivery route before returning. Re-serving restores delivery
even when its server is already running. The page's first serve records its
lifetime. Normal re-serving from an agent session preserves that lifetime. To
change a session service to standing, stop it and start with `--standing`;
starting a stopped service from the user's shell also selects standing.

A session page retires when no live session holds it. Desktop Codex keeps the
chat's ownership and delivery across idle instance unloading and long absences.
Archiving or deleting the chat ends that lifetime. Terminal sessions release
ownership when their harness ends.

`server start --standing`, or serving from the user's shell, makes a page stay
live between sessions and prepares no agent delivery. Tell the user when starting
one: they inherit a process that only `leaf server stop <page>` ends. Ending a
session releases its claim and leaves the standing service enabled.

A watcher revives an enabled service whose process dies, at its recorded URL and
lifetime, and ends if revival fails. `leaf server stop <page>` disables service;
a watcher still watches a stopped page until it is idle. Ending the page's
conversation follows `page-checkpoints.md`, "Sign-off and ending".

## Resuming a standing or foreign page

Resume a page from one session only. `leaf page claim <page>` moves the claim to
whichever session runs it, and a watcher another session still runs stops watching
that page. First read the page:

```bash
leaf page state <page>
```

Read the active revision's HTML (`active.file`) and the standing `state` over it,
then open Questions, current thread state, and `measurement_lag` for figures whose sources
have run again. Before editing, follow `authoring-revisions.md`'s "Read
before editing" section. Then run `leaf page claim <page>` and follow your harness
contract for watching it. Starting a server
when the standing one is already live prints its URL without changing its lifetime.

## Inspecting interactions

For a served page, read the private diagnostic stream to reconstruct a user or
test-agent path. Select a browser tab and a time window using ISO times with
explicit timezone offsets:

```bash
leaf page interactions <page> --session TAB \
  --since 2026-10-08T23:08:42-07:00 --until 2026-10-08T23:08:54-07:00 \
  --type keydown --type command --type focusin
```

Omit the session filter to include server requests, which have no browser session
association. Use `--json` for complete structured values, or `tail -F
<page>/interactions.jsonl` to follow raw delivery order while reproducing. The
reader orders observations by their recorded time, deduplicates retries,
reconstructs split values, and retains visible gap diagnostics under type filters.
Browser and server clocks can differ; recorded order alone does not prove causation.
The semantic decisions remain in `leaf page events <page>`. See [page-storage.md](../scripts/leaf/page-storage.md)
for the file contract. The public site stores its browser batches in Workers
Observability; `worker/README.md` describes lookup by session reference.

## Temporary test servers

`server run --temporary` serves on loopback until its foreground command exits,
with a per-server key and no claim or `service.json`. It cannot be revived and
does not deliver its browser events to an agent. Use it for browser-harness tests.
