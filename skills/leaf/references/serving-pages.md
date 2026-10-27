# Serving pages

Serve and hand over a page as your harness's reference says, keeping the exact keyed
URL `leaf server start` prints. This reference covers export, changing the address,
re-vendoring and resuming a page.

## Exported files

When `$ARGUMENTS` asks for `--export`, build the page as a finished record (the main
skill's "Review an important page in the browser" and "Stamp a record" steps), since
only a stamped version exports, then
run:

```bash
leaf page export <page> -o <file>
```

Hand back the `file://` URL; don't start a server or wait. The file opens offline with
the stamped content and recorded decisions. Reading controls and the page's own code
work, but recording new Leaf choices or updates, Undo and threads require the served
page and its server; an active agent is not required to record a choice. A page with a
live sample can't be exported. Write the file where the project keeps files for the
user. Exporting a live page doesn't end its loop.

## Address and authentication

By default Leaf serves on the address the session arrived through: the SSH destination
for an SSH session, otherwise loopback. The document, its files and its events all need
the URL's key, which the browser keeps in a cookie. One key covers every page on the
machine, so sharing one page's URL gives access to all of them. Leaf opens no public
tunnel; binding beyond loopback exposes the port to that network.

A page keeps its host and port in `<page>/service.json`, so serving again, re-vendoring
and reviving keep the same URL. `--host` changes the hostname and keeps the port. On
macOS, restarting a `--host` page can wait about 30 seconds for the port to free up, and
serving refuses if it is still taken.

## Unreachable URLs and `--host`

When a server binds only loopback, `server start` prints a `loopback-only` note. That
is the default for any session that didn't arrive over SSH, such as a scheduler or a
background job. If you see it and the user isn't at this machine, ask them for a
hostname their browser can reach and serve on it, or export the version as a file.

Otherwise only the user can tell you a URL doesn't load. When they do, restart the
server with a hostname their browser can use:

```bash
leaf server stop <page>
leaf server start <page> --host <reachable-name>
```

`--host` puts that name in the URL and binds every interface; the name needn't resolve
on this machine, and an overlay-network hostname works. If no route works, export the
version as a file.

## Re-vendoring

Open pages keep working across Leaf updates, except after an update that changes the
page protocol or removes a registry key the page's layer declares.

After a protocol change, the session holding the page re-vendors it at its first `leaf`
command or hook, keeping the log and source, and reports only a failure. Leaf refuses
to serve or write the page in two cases: the update removed a registry key the page's
layer declares, or it changed the protocol while another live session holds the page.
`leaf page state` then explains in `source.error`, naming the `leaf page init` command
to run. Run it from the session that
holds the page. Run it too when you want a newer runtime, theme or package:

```bash
leaf page init <page>
```

A page vendored by a newer Leaf than the one you run is refused as well;
the refusal says how to load a newer Leaf.

While Leaf is in alpha, an update can also break an older page without a protocol
change. `page check` and the leaf's menu in the page's panel name the Leaf that
vendored the page and the one running, with their dates. If a page misbehaves and its Leaf is much older,
re-vendor it rather than working around the fault. Don't re-vendor a working page for
its age alone, since that reloads the user's open tabs.

`page init` changes nothing if it refuses. When the layer, server code, dependencies,
package selection or installed files changed, it restarts a running server at the same
URL and reloads open tabs; a stopped server stays stopped. If the holding session
has ended, it leaves the server stopped, and you serve it from your session.

Versions saved before a protocol change stay in the history but no longer open. If
`page init` can't read an older page's log, or the page still misbehaves after
re-vendoring, write the current page into a new page directory and hand over its URL.

## Page lifetime

`server start` from an agent session claims the page for that session and connects
the harness's delivery, even when the server is already running. The first serve sets
the page's lifetime, and later serves keep it. To make a session page persistent, stop
it and start it with `--lifetime persistent`, or start it from the user's shell.

A session page stops when no live session holds it: when a terminal harness exits, or
when a desktop Codex chat is archived or deleted.

A persistent page keeps running between sessions; starting it prepares no agent
delivery. Tell the user
when you start one: they now own a process that only `leaf server stop <page>` ends.

A watcher restarts an enabled server whose process dies, at the same URL. `leaf server
stop <page>` disables the server; a watcher keeps watching a stopped page until it is
closed. To end the page's conversation, follow `page-checkpoints.md`, "Ending".

## Resuming a persistent or foreign page

Resume a page from one session only. `leaf page list` prints each page on the machine
as a JSON line, served or stopped, with the session holding it, by the name its harness
gives it (`session_name`) and whether it still runs (`session_alive`). Use it to find
the page the user means, and to see whether another live session holds it before you
claim it. Then read the page:

```bash
leaf page state <page>
```

Read the active revision's HTML (`active.file`) and the `state` over it, then the open
obligations, the threads, and `measurement_lag` for figures whose sources have run again, as
`authoring-revisions.md`, "Read before editing", describes. Then run
`leaf page claim <page>`, which moves the page to your session and prepares delivery
for your harness; it does not start or stop the page's server.

## Inspecting interactions

To reconstruct the path a user or test agent took on a served page, read its private
diagnostic stream for a browser tab and a time window, with ISO times that carry a
timezone offset:

```bash
leaf page interactions <page> --session TAB \
  --since 2026-10-08T23:08:42-07:00 --until 2026-10-08T23:08:54-07:00 \
  --type keydown --type command --type focusin
```

Omit `--session` to include server requests and raw event records. The raw `<page>/observations.jsonl`,
which `tail -F` follows live while you reproduce a problem, is in arrival order and
still holds retries. Browser wall time stays in `observed_at`; order alone does not
prove cause. The user's decisions are in `leaf page events <page>`, and
[`interaction-batch.schema.json`](../../../src/leaf/interaction-batch.schema.json) defines
the fields every browser row carries, and [page-storage.md](../../../src/leaf/page-storage.md)
names the file's other owners.

## Temporary test servers

`server run --lifetime temporary` serves on loopback until its foreground command exits, with
its own key and no claim. It can't be revived and delivers no browser events to an
agent. Use it for browser tests.
