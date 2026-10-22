# Serving pages

Serve and hand over a page as your harness's reference says, keeping the exact keyed
URL `leaf server start` prints. This reference covers export, the page's address,
re-vendoring, lifetime and resuming a page.

## Exported files

When `$ARGUMENTS` asks for `--export`, build the page as a finished record (the main
skill's "Review and stamp a record" step), since only a stamped version exports, then
run:

```bash
leaf page export <page> -o <file>
```

Write the file where the project keeps files for the user and hand back its
`file://` URL; don't start a server or wait. The file opens offline with the stamped
content and recorded decisions, and its reading controls and the page's own code
work. Recording new choices or updates, Undo and threads need the served page. A
page with a live sample can't be exported. Exporting a live page doesn't end its
loop.

## Address and authentication

By default Leaf serves on the address the session arrived through: the SSH
destination for an SSH session, otherwise loopback. The page and its events need the
URL's key, and one key covers every page on the machine, so sharing one page's URL
gives access to all of them. Leaf opens no public tunnel; binding beyond loopback
exposes the port to that network. A page keeps its host and port in
`<page>/service.json`, so serving again, re-vendoring and reviving keep the same
URL.

When a server binds only loopback, `server start` prints a `loopback-only` note. If
you see it and the user isn't at this machine, ask them for a hostname their browser
can reach, or export the version as a file. Otherwise only the user can tell you a
URL doesn't load. Then restart the server with a name their browser can use, such as
an overlay-network hostname, which needn't resolve on this machine:

```bash
leaf server stop <page>
leaf server start <page> --host <reachable-name>
```

`--host` puts that name in the URL, binds every interface and keeps the port. On
macOS the restart can wait about 30 seconds for the port to free up. If no route
works, export the version as a file.

## Re-vendoring

A page keeps the runtime that vendored it. After an update that changes the page
protocol, the session holding the page re-vendors it at its first `leaf` command or
hook, keeping the log and source, and reports only a failure. Where Leaf can't do
that, as when the update removed a registry key the page's layer declares or
another live session holds the page, it refuses to serve or write the page, and
`leaf page state` names the `leaf page init` command to run in `source.error`. Run
it from the session that holds the page. Run it too when you want a newer runtime,
theme or package:

```bash
leaf page init <page>
```

`page init` changes nothing if it refuses. Otherwise it restarts a running server at
the same URL and reloads open tabs; if the session that held the page has ended, it
leaves the server stopped for you to serve. A page vendored by a newer Leaf than the one you
run is refused, and the refusal says how to load a newer Leaf.

While Leaf is in alpha, an update can also break an older page without a protocol
change. `page check` and the leaf's menu in the page's panel name the Leaf that
vendored the page and the one running, with their dates. If a page misbehaves and
its Leaf is much older, re-vendor it rather than working around the fault. Don't
re-vendor a working page for its age alone, since that reloads the user's open tabs.

Versions saved before a protocol change stay in the history but no longer open. If
`page init` can't read an older page's log, or the page still misbehaves after
re-vendoring, write the current page into a new page directory and hand over its
URL.

## Page lifetime

`server start` from an agent session claims the page for that session and connects
the harness's delivery, even when the server is already running. The first serve
sets the page's lifetime, and later serves keep it. A session page stops when no
live session holds it: when a terminal harness exits, or when a desktop Codex chat
is archived or deleted. To make a session page persistent, stop it and start it with
`--persistent`, or start it from the user's shell.

A persistent page keeps running between sessions, with no agent delivery. Tell the
user when you start one: they now own a process that only `leaf server stop <page>`
ends. A watcher restarts an enabled server whose process dies, at the same URL. To
end the page's conversation, follow `page-checkpoints.md`, "Sign-off and ending".

## Resuming a persistent or foreign page

Resume a page from one session only. First read it with `leaf page state <page>`:
the active revision's HTML (`active.file`) and the `state` over it, then the open
obligations, the threads, and `measurement_lag` for figures whose sources have run
again, as `authoring-revisions.md`, "Read before editing", describes. Then run
`leaf page claim <page>`, which moves the page to your session, and watch it as your
harness's reference says.

## Inspecting interactions

To reconstruct the path a user or test agent took on a served page, read its private
diagnostic stream for a browser tab and a time window, with ISO times that carry a
timezone offset:

```bash
leaf page interactions <page> --session TAB \
  --since 2026-10-08T23:08:42-07:00 --until 2026-10-08T23:08:54-07:00 \
  --type keydown --type command --type focusin
```

Omit `--session` to include server requests and raw event records. The raw
`<page>/observations.jsonl`, which `tail -F` follows live while you reproduce a
problem, is in arrival order and still holds retries; browser wall time is in
`observed_at`, and order alone does not prove cause. The user's decisions are in
`leaf page events <page>`, and [page-storage.md](../../../src/leaf/page-storage.md)
defines the files.

## Temporary test servers

`server run --temporary` serves on loopback until its foreground command exits, with
its own key and no claim. It can't be revived and delivers no browser events to an
agent. Use it for browser tests.
