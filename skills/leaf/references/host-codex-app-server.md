# Codex App Server handoff and delivery

This contract is for a Codex task Leaf reaches over Codex App Server
(`codex app-server`), the JSON-RPC server Codex's clients drive a task through. Leaf
is a client of the task's server: it starts the turns that carry user input and takes
each turn's opening and final messages as its reply. A terminal task is on App Server when its
environment sets `LEAF_CODEX_APP_SERVER`, as a `leaf codex launch` terminal does, or
when the user gave you the task's App Server endpoint; it hands its own page over, as
"Hand a page over from a terminal" describes. A host that starts the task itself, as
leaf.page does, says so in its own instructions and has already handed the page over.
Any other Codex task, the desktop app's included, follows `references/host-codex.md`.

## Delivery

New user input reaches you only once the current turn ends, because a delivery
starts a turn of its own: once the task is idle, Leaf starts one with the complete
delivery as a structured `leaf_delivery` tool output. A delivery can span pages and
conversations, presented as one chronological slice per turn. Leaf acknowledges the
delivery itself once it enters that turn, so this contract leaves no acknowledgement to
you: run no acknowledgement command, and no `leaf wait` or `leaf wait --ack` while Leaf
delivers to this task over App Server.

## Replies

Each slice contains at most one plain reply, and your turn's first message and final
message write it. Before your first tool call, open with a short message to the user:
the answer, or what you are about to do. Leaf streams it into the addressed thread at
once, so the user reads it while you work. Later working messages stay in Codex. Your
final message completes the reply, and Leaf commits the opening and the final message
together through the same reply contract as `leaf reply`. Do not run `leaf reply` for
that response, which refuses it. The final message cannot move or detach its
thread, so the thread keeps its anchor. If the user resolves the thread before the
turn completes, the reply still posts and reopens it. A later plain reply remains pending for the next slice.

Other obligations in the slice take the operations their delivered `answering`
clauses name.

A `leaf-delivery` pointer queued before Leaf observed the task can still arrive as a
user message; read it with `leaf delivery read <id>`, and Leaf binds its reply to the
turn's messages the same way. Wherever `leaf reply` refuses an event as answered by
this turn's messages, answer it in your final message.

## Activity

Plan updates, tool starts, reasoning summaries, and waits for approval or user input
are watched as the task's current step. Leaf retains thinking, tool use, replying,
approval waits, and input waits as distinct observations. They describe overall page
activity; an observed step alone does not claim work on a particular message. A
sentence declared with `leaf status` stays the page's sentence, and the step stands
beside it in the banner's disclosure; without a declared sentence for this work, the
step is the sentence.

## Hand a page over from a terminal

A terminal task reaches App Server through a detached adapter that
`leaf codex start` leaves running: it connects to the task's server as a second
client, watches the task's own turns, and starts a delivery's turn once the task is
idle. This route is experimental.

### Start the terminal

The normal entry point starts a private Unix-socket App Server and runs the terminal
client against it:

```sh
leaf codex launch
```

The launcher exports its endpoint to the task as `LEAF_CODEX_APP_SERVER` and owns
both processes. Exiting the terminal stops its App Server, so each terminal is
independent and no fixed port or separate server tab remains. Observed activity ends
with that server.

To run the two processes separately instead, start a loopback WebSocket listener
and pass the same endpoint to both clients:

```sh
codex app-server --listen ws://127.0.0.1:4500
codex --remote ws://127.0.0.1:4500
```

From that remote CLI task, pass the same endpoint to `leaf codex start` with
`--app-server ws://127.0.0.1:4500`.

Only `unix://<absolute path>` sockets and unauthenticated loopback `ws://` endpoints
are accepted; keep a socket you supply in a directory only you can reach, as
`leaf codex launch` does. The loopback WebSocket listener is experimental; do not
expose it on a network. Keep the CLI open because it is still the interactive client for
approvals and user input. The task is still stored in Codex's task history and can be
resumed later from the CLI or desktop app after the standalone server releases its
writer; the desktop app is not a live client of this separately started server.

### Full Leaf handoff

Use the canonical browser page by default. Run `leaf server start <page>` and
retain its exact keyed URL, and hand it over for a local browser. This runs Leaf's
theme, package widgets, anchored comments, versions, and state stream unchanged.

Set the page to `waiting` and run `leaf codex start <page>` before finishing the turn
with the URL and a concrete gesture. The first start in a task leaves a detached
adapter connected to the App Server, and its output ends
`through App Server <endpoint>`; output without that ending means Leaf is not on the
App Server, and `references/host-codex.md` applies. A later start adds its page to the
running adapter and reports that adapter's transport the same way; it refuses an
`--app-server` endpoint other than the one the adapter holds. The adapter watches
every page this task owns, and a completed turn does not stop it.

For an inline MCP App, follow `references/host-codex.md`, "Experimental inline MCP
App": it starts this same adapter. A `leaf wait` this task already runs, or a
watcher task, carries input without the adapter, as that contract's "Routes without
the adapter" describes; on those routes there is no App Server turn to bind, so
answer with `leaf reply`.

If `leaf codex start` refuses to start, do not finish over a live page. Follow its
diagnostic: an existing foreground `leaf wait` must be stopped before the adapter
can take the task's single wait lease, and an unreachable endpoint must be fixed.
