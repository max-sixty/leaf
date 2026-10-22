# Codex handoff and delivery

Use this reference for Codex in the desktop app, an IDE, a terminal or leaf.page.
Follow each event's `handling` and, for a thread reply, its `answer.writer`.

## Full Leaf handoff

Run `leaf server start <page>` and keep the exact keyed URL it prints. When Codex
offers `open_in_codex`, open that URL as a browser target beside this task;
otherwise give the user the URL. Follow `conversation-loop.md`, "Status and handoff".

`server start` connects delivery before it prints the URL, even when the server is
already running; if it refuses, follow its message before handing the page over. If
this task already runs `leaf wait` itself, serving leaves that in place. A harness
that starts the task, such as leaf.page, has already handed the page over.

## Delivery

`leaf server start` and `leaf server run` start, or join, a background adapter that
watches every page this task owns and keeps running between turns; serving a page
again restarts an adapter that stopped. To connect
delivery for a page you claim without serving it, run `leaf codex start <page>`.
Run no `leaf wait` or `leaf wait --ack`.

While your turn runs, Leaf's hooks offer new input between steps, as one line of
JSON or, when it exceeds Codex's context limit, a pointer. Read inline input
directly; for a pointer, run its `leaf delivery read <id>` and read every part.
Follow the delivery's `acknowledge` instruction before handling the input.

When the task is idle, or a hook's input wasn't confirmed before the turn ended, the
adapter either queues a `leaf-delivery` pointer as the task's next user message or
starts an App Server turn with a `leaf_delivery` tool output. Leaf acknowledges what
it queues or starts, but a pointer still needs complete reading and the confirmation
on its last part. The same delivery id can come back in a later turn; its
`leaf delivery ack` then says an earlier turn already picked it up and names any
answer it still owes. Don't redo that turn's work.

The desktop app's own App Server exposes no endpoint Leaf can use; a terminal can
connect to a separate one (`codex-setup.md`). A Codex without `codex queue` refuses a
queue connection because it can't receive later turns.

## Replies

For a thread reply, use the event's `answer.writer`:

- `"agent"`: post with `leaf response reply <answer.ref>`. Your final message stays
  in the Codex chat and never reaches the page.
- `"turn"`: the delivery reserves one thread reply for this turn. Before your first
  tool call, write a short message to the user: the answer, or what you are about to
  do. Leaf posts it in the thread as your progress line; later working messages stay
  in Codex. When the turn completes, your final message posts as the reply. A turn
  with no final message posts no reply.

For a `"turn"` reply that needs widgets, a question for the user (an `lf-ask`), work
promised beyond this turn (`--todo`), a title or a changed anchor, use
`leaf response reply <answer.ref>` with the options in `threads.md`. It posts at
once, and your final message then posts nothing.

Your final message publishes your saved page edits with it, so end the turn without
running `leaf page check` first. If Leaf refuses to post it, as it does over a saved
edit with errors or in a turn that also carries a message the user sent in Codex, it
starts a correction turn with the reason and the same reply address; fix the problem
and complete the answer. A reserved reply still posts if the user resolves the
thread first, and reopens it.

A hook or queued pointer can carry an `"agent"` reply even in a task connected to
App Server; the writer the event names decides.

## Activity

When connected to App Server, Leaf's panel also shows the task's current step, such
as a tool call or a wait for approval, beside the line your latest `leaf task start`
gave.

## Sandbox

In Codex's `workspace-write` sandbox, run `leaf` commands with the `run` tool of the
`leaf` MCP server, which runs them outside the sandbox. Your own edits to a page in
Leaf's state home need the user to add the state home's `pages` directory to Codex's
writable roots ("Agent sandboxes" in Leaf's `README.md`). Where that is missing, the
tool's first result in a task says so and gives the line; pass it to the user.

## Routes without the adapter

Two routes bring input without the adapter. On both, answer with
`leaf response reply <answer.ref>`.

- This task runs `leaf wait` in unified exec, polls it with `write_stdin`, and
  acknowledges each batch with `leaf wait --ack <delivery-id>`, which then waits for
  the next. The turn stays open as long as the page is live.
- A separate watcher task runs the wait and forwards each batch into this task as a
  background follow-up; this task runs no wait. Use it only when the user allows a
  visible watcher task, and follow `codex-watcher.md`.
