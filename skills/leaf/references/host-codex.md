# Codex handoff and delivery

This contract is for a Codex task that Leaf reaches through Codex's durable queue:
the desktop app, an IDE extension, or a terminal CLI started the ordinary way. A task
whose environment sets `LEAF_CODEX_APP_SERVER`, as a `leaf codex launch` terminal
does, or whose App Server endpoint the user gave you, is one Leaf reaches over Codex
App Server instead, and follows `references/host-codex-app-server.md`. The desktop
app runs an App Server of its own, but Leaf cannot connect to it, so a desktop task
follows this contract.

## Full Leaf handoff

Use the canonical browser page by default. Run `leaf server start <page>` and
retain its exact keyed URL. When Codex exposes `open_in_codex`, open that URL as a
browser target beside this task; otherwise hand over the URL for a local browser.
This runs Leaf's theme, package widgets, anchored comments, versions, and state
stream unchanged.

Set the page to `waiting` and run `leaf codex start <page>` before finishing the
turn with the URL and a concrete gesture. The browser pane is the presentation;
the adapter below carries input back to this same task.

## Delivery

`leaf codex start` leaves a detached adapter that watches every page this task owns.
Starting the command again for another page adds that page to the same task-wide
watch, and a completed turn does not stop the adapter.

New user input reaches you after the current turn ends. The adapter hands each
delivery to `codex queue`, which queues it as the task's next user message: a
`leaf-delivery` XML element shown as one line in a code block, naming
`leaf delivery read <id>`, which resolves the immutable envelope. The adapter
acknowledges the delivery once Codex's queue accepts it, so do not run `leaf wait` or
`leaf wait --ack` while it holds the task. The same delivery id may return after an
uncertain queue response, which is the retry `references/event-batches.md` describes.

Answer every obligation with the operation its delivered `answering` clause names,
`leaf reply` for a plain reply. Your final message stays in the Codex
chat and never reaches the page. Leaf does not observe the task's turns either, so
the banner shows only the status you declare.

This is Claude Code's delivery with the wait and the acknowledgement moved into the
adapter: input arrives between turns, and the answers are the same commands.

If `leaf codex start` refuses to start, do not finish over a live page. Follow its
diagnostic: an existing foreground `leaf wait` must be stopped before the adapter
can take the task's single wait lease, and a Codex without the `codex queue` command
cannot receive later turns.

## Routes without the adapter

Two routes carry input without the adapter, and both answer with `leaf reply` as
above.

- This task runs `leaf wait` in unified exec, polls it with `write_stdin`, and
  acknowledges each complete batch with `leaf wait --ack <delivery-id>`, which then
  waits for the next. That is Claude Code's loop held inside one turn, so the turn
  stays open for as long as the page is live.
- A separate watcher task runs the wait, forwards each batch into this task as a
  background follow-up, and acknowledges it; this task runs no wait at all. Take it
  only when the user authorizes a visible watcher task, and follow
  `references/codex-watcher.md`.

## Experimental inline MCP App

Use the bundled model tool whose exposed name ends in `leaf_present` when the
user requests an inline MCP App or a host-capability experiment. Pass the
initialized page's absolute directory. The app attempts to frame the canonical
page from a process-scoped localhost origin; hosts that disallow that frame get a
comments-only snapshot. That snapshot has no package actions or version travel;
open the full browser page whenever the observed mode lacks what the user needs.

Judge the rendered mode from the visible app or host diagnostics. Model-visible
text and a successful tool call do not establish which UI the host displayed.
If visual evidence is unavailable, say the rendering is unverified. Use
`leaf_present_snapshot` only when deliberately requesting the comments-only view;
the app already handles automatic fallback. Do not call app-only tools from the
model.

Set the page to `waiting` and start the same Codex adapter before handing over an
inline app. Name the review and report its observed mode or unverified rendering;
its ephemeral iframe URL is not a durable browser handoff. A successful
`ui/message` response is not a delivery receipt.
