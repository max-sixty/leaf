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
the detached adapter below carries input back to this same task. When this task
is running through an App Server, use the live-reply form below instead.

## Live Codex replies through App Server

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
Live activity ends with that server. The detached page carrier falls back to
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
current activity detail. When a delivery contains feedback from exactly one Leaf
conversation, Leaf starts a Codex turn with a structured `leaf_feedback` tool
output. Codex's response streams into that conversation as an ordinary-looking
agent reply. Successful completion appends the authoritative final text as a
durable Leaf reply; a failure or interruption leaves a labelled provisional reply
and does not settle the reader's message.

The Leaf-started turn, its `functionCallOutput`, and Codex's response remain in the
Codex transcript. A normal turn started by the user in Codex has no Leaf binding,
so its response appears only in Codex. Input that spans several conversations or
pages uses the existing `codex queue --remote` fallback and is not mirrored into
one Leaf thread. More feedback in the already-bound conversation may steer that
same active turn; its returned turn id must match. Keep the CLI open because it is
still the interactive client for approvals and user input.

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

Treat a `leaf-delivery` as input from a page that has already been presented.
Read and process the payload it names; do not call `leaf_present` or repeat the
first-handoff ceremony.

One detached adapter watches every page this task owns. It collects available
input into one delivery and freezes it. Input collected after the freeze belongs
to the next delivery. Starting the command again for another page adds that page
to the same task-wide watch.

For one-conversation feedback, the adapter calls `turn/start` directly and records
the returned Codex turn id before acknowledging pickup. It owns the live response
and appends this turn's final answer as the reply; do not duplicate it with `leaf
reply`. The task still owns page revisions, other Leaf operations, page status, and
the handoff back to `waiting` or `idle`.

The App Server's queue service remains the fallback. It starts a later turn while
the connected Codex client remains the interactive client for approvals and user
input. A completed turn does not stop the adapter. If the task has been unloaded,
the item stays queued until Codex reopens it. The queued message is a
`leaf-delivery` XML element shown as one line in a code block. It names the `$leaf`
skill and its `path` points to the persisted delivery. Read that file and process
every entry in `batches`; each carries its `page`, current `url`, `threads`,
`handling`, and exact `events`. Do not wait or acknowledge: the adapter owns both.
The payload path is permanent. The same delivery id may return after an uncertain
queue response, so treat a page-and-sequence pair already handled in this task as a
retry. Queue acceptance records **Queued** activity.

The immutable payload and mutable queue record are separate files. Once a delivery
is accepted and fully receipted, the adapter moves only its queue record into the
delivery directory's `history/` subdirectory. The path already handed to Codex keeps
naming the immutable payload, while completed transport state leaves the hot scan.

If `leaf codex start` refuses to start, do not finish over a live page. Follow its
diagnostic: an existing foreground `leaf wait` must be stopped before the adapter
can take the task's single wait lease, and an unavailable Codex queue command
cannot receive later turns.

An optional separate Codex watcher remains a fallback that requires the user's
explicit authorization because it creates a visible task. Its route is in the main
skill.
