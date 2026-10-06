# Codex App Server handoff and delivery

This contract is for a Codex task Leaf reaches over Codex App Server
(`codex app-server`), the JSON-RPC server Codex's clients drive a task through. Leaf
is a client of the task's server: it starts the turns that carry user input and takes
each turn's opening and final messages as its reply. A terminal task is on App Server when its
environment sets `LEAF_CODEX_APP_SERVER`, as a `leaf codex launch` terminal does, or
when the user gave you the task's App Server endpoint; it hands its own page over, as
"Hand a page over from a terminal" describes. A harness that starts the task itself, as
leaf.page does, says so in its own instructions and has already handed the page over.
Any other Codex task, the desktop app's included, follows `references/harness-codex.md`.

## Delivery

While a task with Leaf's trusted tool hook is working, new input can arrive between
steps as a `leaf-delivery` pointer. Read it and answer with explicit commands as
`references/harness-codex.md`, "Delivery", describes. That reply is not bound to
your turn's final message.

Otherwise a delivery starts a turn of its own: once the task is idle, Leaf starts one with the complete
delivery as a structured `leaf_delivery` tool output. A delivery can span pages and
threads, presented as one chronological slice per turn. Leaf acknowledges the
delivery itself once it enters that turn, so this contract leaves no acknowledgement to
you: run no acknowledgement command, and no `leaf wait` or `leaf wait --ack` while Leaf
delivers to this task over App Server.

## Replies

Each slice contains at most one thread reply, delivered as a `turn` answer, and
your turn's first message and final message write it. Before your first tool call,
open with a short message to the user: the answer, or what you are about to do. Leaf streams it into the addressed thread at
once, so the user reads it while you work. Later working messages stay in Codex. Your
final message completes the reply, and Leaf commits the opening and the final message
together through the same reply contract as `leaf thread reply`. Do not run `leaf thread reply` for
that response, which refuses it. The final message cannot move or detach its
thread, so the thread keeps its anchor. Leaf titles an untitled thread the reply
answers from its opening message, so it needs no title from you. If the user
resolves the thread before the turn completes, the reply still posts and reopens
it. A later plain reply remains pending for the next slice.

Other answers in the slice take the operations their delivered `handling`
clauses name.

Before finishing a turn that changed `index.html`, run `leaf page check <page>`
and fix every error. The final reply requires valid source, and its refusal arrives
after the model's turn has ended, when it can no longer correct the edit.

A `leaf-delivery` pointer queued before Leaf observed the task can still arrive as a
user message. Read it with `leaf delivery read <id>`: it was frozen for the queue, so
its reply is a plain `reply` for `leaf thread reply`, as `references/harness-codex.md`
describes.

## Activity

Plan updates, tool starts, reasoning summaries, and waits for approval or user input
are watched as the task's current step. Leaf retains thinking, tool use, replying,
approval waits, and input waits as distinct observations. They describe overall page
activity; an observed step alone does not start a particular message. The line of
an item you started with `leaf task start` stays the page's sentence, and the step
stands beside it in the banner's disclosure; with no item in hand, the step is the
sentence.

## Hand a page over from a terminal

A terminal task reaches App Server through a detached adapter that
serving leaves running: it connects to the task's server as a second
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

To run the two processes separately, create a private socket directory and print
its endpoint before starting App Server:

```sh
socket_dir=$(mktemp -d /tmp/leaf-codex.XXXXXX)
endpoint="unix://$socket_dir/app-server.sock"
printf '%s\n' "$endpoint"
codex app-server --listen "$endpoint"
```

In the terminal client's shell, copy that printed endpoint:

```sh
export LEAF_CODEX_APP_SERVER="<printed endpoint>"
codex --remote "$LEAF_CODEX_APP_SERVER"
```

The task inherits the endpoint, so `leaf codex start` connects to that App Server.
Each pair of processes has its own socket; parallel versions need no port assignment.

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

Serving starts or joins the task's delivery adapter before returning the URL,
using `LEAF_CODEX_APP_SERVER` as its endpoint. Re-serving restores an adapter that
stopped, including when the page server is already running. Set the page to
`waiting`, then finish the turn with the URL and a concrete gesture. The adapter
watches every page this task owns, and a completed turn does not stop it.

`leaf codex start <page>` connects delivery explicitly when claiming without
serving. It prints `{"task", "app_server", "started"}`; a null `app_server` means
Leaf is on the queue route in `references/harness-codex.md`. A later start reports
`started: false` and the running adapter's endpoint, and refuses an endpoint other
than the one that adapter holds.

A `leaf wait` this task already runs, or a watcher task, carries input without the
adapter, as `references/harness-codex.md`, "Routes without the adapter", describes; on those routes there is no App Server turn to bind, so
answer with `leaf thread reply`.

If serving refuses to connect delivery, fix its diagnostic before handing the
page over. Serving honors an existing direct `leaf wait`; an explicit
`leaf codex start` refuses while that wait holds the task's single wait lease.
