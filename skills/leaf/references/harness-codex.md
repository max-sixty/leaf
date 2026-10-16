# Codex handoff and delivery

Use this reference when the main skill's "Harness selection" picks ordinary Codex,
whether in the desktop app, an IDE or a terminal. Leaf brings the user's input back to
this task through Codex's queue.

## Full Leaf handoff

Run `leaf server start <page>` and keep the exact keyed URL it prints. When Codex offers
`open_in_codex`, open that URL as a browser target beside this task; otherwise give the
user the URL. Follow `conversation-loop.md`, "Status and handoff".

`server start` connects delivery before it prints the URL, even when the server is
already running; if it refuses, follow its message before handing the page over. If
this task already runs `leaf wait` itself, serving leaves that in place.

## Delivery

`leaf server start` and `leaf server run` start, or join, a background adapter that
watches every page this task owns, and keeps running when a turn ends. Serving a page
again restarts an adapter that stopped. To connect delivery for a page you claim
without serving it, run `leaf codex start <page>`.

While your turn runs, Leaf's hooks offer new input between steps and when the turn tries
to end. Run the `leaf delivery read <id>` it names, read every part, then follow its
confirmation instruction.

When the task is idle, or a hook's input wasn't confirmed before the turn ended, the
adapter sends the input through `codex queue` as the task's next user message: a
`leaf-delivery` element naming `leaf delivery read <id>`. The adapter acknowledges it, so
don't run `leaf wait` or `leaf wait --ack`. The same delivery id can come back after an
uncertain queue response; that is the retry `event-batches.md` describes. Input
confirmed during a turn isn't queued again.

Answer each update with the command its delivered `handling` names, such as
`leaf response reply <answer.ref>` for a reply. Your final message stays in the Codex
chat and never reaches the page.

A Codex without the `codex queue` command can't receive later turns, so serving refuses
to connect delivery there.

## Routes without the adapter

Two routes bring input without the adapter. On both, answer with
`leaf response reply <answer.ref>`.

- This task runs `leaf wait` in unified exec, polls it with `write_stdin`, and
  acknowledges each batch with `leaf wait --ack <delivery-id>`, which then waits for the
  next. The turn stays open as long as the page is live.
- A separate watcher task runs the wait and forwards each batch into this task as a
  background follow-up; this task runs no wait. Use it only when the user allows a
  visible watcher task, and follow `codex-watcher.md`.
