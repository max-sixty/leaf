# Codex handoff and delivery

This contract is for a Codex task that Leaf reaches through Codex's durable queue:
the desktop app, an IDE extension, or a terminal CLI started the ordinary way. A task
whose environment sets `LEAF_CODEX_APP_SERVER`, as a `leaf codex launch` terminal
does, or whose App Server endpoint the user gave you, is one Leaf reaches over Codex
App Server instead, and follows `references/harness-codex-app-server.md`. The desktop
app runs an App Server of its own, but Leaf cannot connect to it, so a desktop task
follows this contract.

## Full Leaf handoff

Use the canonical browser page by default. Run `leaf server start <page>` and
retain its exact keyed URL. When Codex exposes `open_in_codex`, open that URL as a
browser target beside this task; otherwise hand over the URL for a local browser.
This runs Leaf's theme, package widgets, anchored comments, versions, and state
stream unchanged.

Serving connects delivery before returning the URL, including when the page's
server is already running. Set the page to `waiting`, then finish the turn with
the URL and a concrete gesture. The browser pane is the presentation; the adapter
below carries input back to this same task.

## Delivery

`leaf server start` and `leaf server run` start or join a detached adapter that
watches every page this task owns. Serving another page adds it to the same
task-wide watch, and a completed turn does not stop the adapter. Re-serving a page
restores an adapter that stopped. `leaf codex start <page>` connects delivery
explicitly when you are claiming a page without serving it.

While your turn is running, Leaf's asynchronous tool hook offers new input between
steps, after the current model request and tool calls finish. Read its pointer
with `leaf delivery read <id>`; reading it confirms pickup in this turn. The
hook cannot interrupt a running request or start an idle turn.

When your task is idle, or a hook's pointer was not read before the turn ended,
the adapter hands the delivery to `codex queue` as the task's next user message: a
`leaf-delivery` XML element shown as one line in a code block, naming
`leaf delivery read <id>`, which resolves the immutable envelope. The adapter
acknowledges queued delivery once Codex's queue accepts it, so do not run `leaf wait` or
`leaf wait --ack` while it holds the task. The same delivery id may return after an
uncertain queue response, which is the retry `references/event-batches.md` describes.

Answer every obligation with the operation its delivered `handling` clause names,
`leaf thread reply` for a plain reply. Your final message stays in the Codex
chat and never reaches the page. Leaf does not observe the task's turns either, so
the banner shows only the items you start and the status you declare.

The tool hook and adapter share one delivery record, so input read during work is
not queued again. Without a running trusted tool hook, delivery uses the queue.

If serving refuses to connect delivery, follow its diagnostic before handing the
page over: a Codex without the `codex queue` command cannot receive later turns.
Serving honors a direct `leaf wait` this task already runs; that route keeps the
current turn open as described below. An explicit `leaf codex start` refuses while
that wait holds the task's single wait lease.

## Routes without the adapter

Two routes carry input without the adapter, and both answer with `leaf thread reply` as
above.

- This task runs `leaf wait` in unified exec, polls it with `write_stdin`, and
  acknowledges each complete batch with `leaf wait --ack <delivery-id>`, which then
  waits for the next. That is Claude Code's loop held inside one turn, so the turn
  stays open for as long as the page is live.
- A separate watcher task runs the wait, forwards each batch into this task as a
  background follow-up, and acknowledges it; this task runs no wait at all. Take it
  only when the user authorizes a visible watcher task, and follow
  `references/codex-watcher.md`.
