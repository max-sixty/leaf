# Serving pages

Serve and hand over a page as your harness's reference says, keeping the exact keyed
URL `leaf server start` prints. This reference covers export, changing the address,
Leaf updates and resuming a page.

## Exported files

When `$ARGUMENTS` asks for `--export`, build the page as a finished record (the main
skill's "Publish and review" section), then run:

```bash
leaf page export <page> -o <file>
```

By default export writes the latest stamped version; `--version N` selects an older
stamp. The result names its `version` and captured `revision`. To inspect work in
progress without adding a checkpoint, use `leaf page export <page> --draft -o <file>`;
it checks and captures current source and reports `version: null`. `--draft` and
`--version` cannot be combined.

The file shows the page as it stands: the selected content, each widget drawn with the
decisions recorded on it, what each fold holds for the reader to open, and its images
and fonts. It holds no script, so a browser that blocks scripts shows all of it, its
controls draw but don't respond, and it is small enough to attach. Leaf draws it in the
host's browser, which `page check --render` also needs. When the file's reader should
operate the page, such as a playground's controls, add `--runtime`: the file then
carries Leaf's runtime, about 11 MB, and opens with the reading controls and the page's
own code working. Recording new Leaf choices or updates, and Undo, still require the
served page and its server, though not an active agent.

Hand back the `file://` URL; don't start a server or wait. A page with a live sample
can't be exported. Write the file where the project keeps files for the user.
Exporting a live page doesn't end its loop.

An export can go to people who shouldn't read your conversation with the user, so the
file holds none of it, on screen or in its source: no threads or their attachments,
to-dos, plan or changelogs. What you wrote into the page, or into data its markup
binds, stays, so a page meant to be passed on says nothing there that its reader
shouldn't see.

## Address and authentication

Leaf serves a new page on the hostname the user sets as `host` in Leaf's config file,
`~/.config/leaf/config.toml`, binding every interface as `--host` does. Without it,
Leaf serves on the address the session arrived through: the SSH destination for an SSH
session, otherwise loopback. The document, its files and its events all need the URL's
key, which the browser keeps in a cookie. One key covers every page on the machine, so
sharing one page's URL gives access to all of them. Leaf opens no public tunnel;
binding beyond loopback exposes the port to that network.

A page keeps its host and port in its directory's service record, so serving again,
changing its packages and reviving keep the same URL. The `host` setting applies only
to a page with no service record yet. `--host` changes the hostname and keeps the
port. On macOS, restarting a `--host` page can wait about 30 seconds for the port to
free up, and serving refuses if it is still taken.

## Unreachable URLs and `--host`

When a server binds only loopback, `server start` prints a `loopback-only` note. That
is the default for any session that didn't arrive over SSH on a machine with no `host`
setting, such as a scheduler or a background job. If you see it and the user isn't at
this machine, ask them for a hostname their browser can reach and serve on it, or
export the version as a file.

Otherwise only the user can tell you a URL doesn't load. When they do, restart the
server with a hostname their browser can use:

```bash
leaf server stop <page>
leaf server start <page> --host <reachable-name>
```

`--host` puts that name in the URL and binds every interface; the name needn't resolve
on this machine, and an overlay-network hostname works. If no route works, export the
version as a file.

A user who opens every page by the same name can set it once in
`~/.config/leaf/config.toml`, and each new page is served there:

```toml
host = "<reachable-name>"
```

## Leaf updates

A page records the packages it selects, and the Leaf serving, checking or exporting it
composes their widgets, theme and vocabulary, as it supplies its runtime. A server
keeps the Leaf it started under until the session holding its page runs an installed
update, or the harness updates the server's own copy in place, as Codex and Pi do; it
then restarts under the update at the same URL on its own. `leaf server start` from
another Leaf, such as an update, restarts it under that one at the same URL. Open
tabs reconnect, reloading where the runtime changed. Open pages keep working across
updates except one that changes the page protocol.

After a protocol change, Leaf takes the page to the new protocol for the session
holding it, keeping the log and source, and tells you only of a failure. It does so
at the session's next turn or at a `leaf` command that writes to the page. A command
that only reads the page, such as `leaf page state`, leaves it at the old protocol.

While another live session holds the page, Leaf refuses to serve or write it, and
`leaf page state` refuses it too, naming the `leaf page init` command to run from the
session that holds the page. A page a newer Leaf initialized is refused
as well; the refusal says how to load a newer Leaf.

An update can change what a widget accepts or how it draws, and a page's own widgets
may call an API the update changed. `leaf page check` reports both, the second with
`--render`; fix the source as for any other failure.

`page init` changes nothing if it refuses. When the package selection or the page
protocol changes, it restarts a running server at the same URL and reloads open tabs;
a stopped server stays stopped. If the holding session has ended, it leaves the server
stopped, and you serve it from your session. If `page init` can't read an older page's
log, write the current page into a new page directory and hand over its URL.

## Page lifetime

With its default `--lifetime session`, `server start` from an agent session claims
the page and connects the harness's delivery, even when the server is already running.
The first serve sets the page's lifetime, and later serves keep it. To make a session page
persistent, stop it and start it with `--lifetime persistent`, or start it from the
user's shell.

A session page stops when no live session holds it: when a terminal harness exits, or
when a desktop Codex chat is archived or deleted.

A persistent page keeps running between sessions. Starting it with
`--lifetime persistent` claims no page and prepares no agent delivery; only
`leaf server stop <page>` ends it.
Tell the user about that lifetime when handing the page over.

A watcher restarts an enabled server whose process dies, at the same URL. `leaf server
stop <page>` disables the server; a watcher keeps watching a stopped page until it is
closed. To end the page's conversation, follow `page-checkpoints.md`, "Ending".

## Resuming a persistent or foreign page

Resume a page from one session only. `leaf page list` prints each page on the machine
in `pages`, served or stopped, with the session holding it, by the name its harness
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
[`interaction-batch.schema.json`](../../../src/leaf/log/interaction-batch.schema.json) defines
the fields every browser row carries, and [page-storage.md](../../../src/leaf/page-storage.md)
names the file's other owners.

## Temporary test servers

`server run --lifetime temporary` serves on loopback until it is interrupted or the process
that ran it exits, with its own key and no claim. It can't be revived and delivers no
browser events to an agent. Use it for browser tests.
