# Codex handoff and delivery

Read this immediately before handing a page to Codex.

## Full Leaf handoff

Use the canonical browser page by default. Run `leaf server start <page>` and
retain its exact keyed URL. When Codex exposes `open_in_codex`, open that URL as a
browser target beside this task; otherwise hand over the URL for a local browser.
This runs Leaf's theme, package widgets, anchored comments, versions, and state
stream unchanged.

Set the page to `waiting` and run `leaf codex start <page>` before finishing the
turn with the URL and a concrete gesture. The browser pane is the presentation;
the adapter below carries input back to this same task.

## Codex App Server transport

This experimental transport connects Leaf to a task controlled through the
Codex CLI. Its protocol and browser path have automated coverage, and the normal
interactive workflow has been smoke-tested with a real Codex App Server and CLI.
The normal entry point starts a private Unix-socket App Server and runs the
terminal client against it:

```sh
leaf codex launch
```

The launcher exports its endpoint to the task. Start Leaf normally from that
task; `leaf codex start` subscribes to the exported App Server without another
option:

```sh
leaf codex start <page>
```

The launcher owns both processes. Exiting the terminal stops its App Server, so
each terminal is independent and no fixed port or separate server tab remains.
Observed activity ends with that server. The detached page carrier falls back to
Codex's durable local task queue, so later reader input can still open a turn
when the task is resumed in the CLI or Desktop app.

To run the two processes separately instead, start a loopback WebSocket listener
and pass the same endpoint to both clients:

```sh
codex app-server --listen ws://127.0.0.1:4500
codex --remote ws://127.0.0.1:4500
```

From that remote CLI task, start Leaf with the same endpoint:

```sh
leaf codex start <page> --app-server ws://127.0.0.1:4500
```

Leaf resumes the current task as a second client. Plan updates, tool starts,
reasoning summaries, and waits for approval or user input become the page's short
current activity detail. If the task is idle, Leaf starts one turn with the
complete delivery as a structured `leaf_delivery` tool output. If the task is
already active, Leaf queues the same immutable delivery rather than steering
unrelated page input into that turn. A delivery can span pages and conversations;
neither case changes its shape or response rules.

The delivery, its provider turn, and each response obligation have stable identities.
A directly started turn records the delivery id as its client message id. When that
`leaf_delivery` has exactly one plain reply obligation, write the reply as the normal
final message. Leaf streams that message into the addressed thread and commits its
completed text through the same reply contract as `leaf reply`; do not run a reply
command for that response. The committed reply retains the thread's standing anchor.

A `leaf-delivery` pointer may arrive through Codex's durable local queue with no App
Server observer left to bind or stream its turn. Claiming its first outstanding move
updates the page immediately; reading the immutable envelope does not. Follow the
UI-first delivery claim in `conversation-loop.md`, then use the
explicit `reply`, `resolve`, or `receipt` operation for every obligation, including one
plain reply. A live observer may also recognize the exact pointer, but its final-message
commit skips an obligation the explicit operation already settled. The immutable
delivery address remains authoritative if the turn closes, the observer reconnects, or
a later turn starts; current-turn identity governs only live activity and provisional
text.
Keep the CLI open because it is still the interactive client for approvals and
user input.

Only private absolute Unix sockets and unauthenticated loopback `ws://` endpoints
are accepted. The loopback WebSocket listener is experimental; do not expose it
on a network. The task is still stored in Codex's task history and can be resumed
later from the CLI or Desktop app after the standalone server releases its writer.
The Desktop app is not a live client of this separately started server.

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

## Same-task delivery

Treat a `leaf_delivery` tool output or `leaf-delivery` pointer as input from a
page that has already been presented. Process every batch and event; do not call
`leaf_present` or repeat the first-handoff ceremony.

One detached adapter watches every page this task owns. It collects available
input into one delivery and freezes it. Input collected after the freeze belongs
to the next delivery. Starting the command again for another page adds that page
to the same task-wide watch.

The App Server starts the complete envelope directly only when its task is idle.
Its acceptance records the returned turn before acknowledging pickup. Otherwise
the queue service starts a later turn while the connected Codex client remains the
interactive client for approvals and user input. A completed turn does not stop
the adapter. If the task has been unloaded, the item stays queued until Codex
reopens it.

The queued message is a `leaf-delivery` XML element shown as one line in a code
block. It names the canonical `delivery claim` operation and an immutable delivery
`id`; run it before `leaf delivery read <id>`, then process the envelope's `batches`
with explicit Leaf operations. Do not wait or acknowledge: the adapter owns
both. The same delivery id may return after an uncertain queue
response, so treat a page-and-sequence pair already handled in this task as a
retry. Queue acceptance records **Queued** activity.

The immutable delivery and mutable adapter queue record are separate. Once a
delivery is accepted and every page batch is acknowledged, the adapter archives
only its queue record. The globally addressed delivery remains readable by id.

If `leaf codex start` refuses to start, do not finish over a live page. Follow its
diagnostic: an existing foreground `leaf wait` must be stopped before the adapter
can take the task's single wait lease, and an unavailable Codex queue command
cannot receive later turns.

An optional separate Codex watcher remains a fallback that requires the user's
explicit authorization because it creates a visible task. Its route is in the main
skill.
