# Codex App Server handoff and delivery

Use this contract when the main skill's "Harness selection" selects Codex App
Server. Leaf starts the turns that deliver user input and writes each turn's
opening and final messages to its addressed thread. A harness that starts the
task, such as leaf.page, has already handed the page over. A terminal task hands
its page over as "Hand a page over from a terminal" describes.

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

Each slice contains at most one thread reply, with `kind: "reply"` and
`writer: "turn"`. Before your first tool call, open with a short message to the
user: the answer or what you are about to do. Leaf streams it into the captured
thread at once. Later working messages stay in Codex. Your completed final
commits the reply through the same durable writer as `leaf response reply`.

For a reply needing widgets, a prose question awaiting the user, a title or a
changed anchor, author it with `leaf response reply <answer.ref>` and the rich
options in [threads](threads.md). The command prepares the full reply on this
turn's reservation; your completed final commits that content, including its
text. Without preparation, Leaf commits your opening and final text. A failed
or interrupted turn leaves no durable prepared answer. Leaf may title an
untitled thread from its opening before your reply arrives; that name stands.

If the user resolves the thread before completion, a successful reply still posts
and reopens it. A prepared failure posts only while that input still needs an answer. A later reply remains pending for the next slice.

Other answers in the slice take the operations their delivered `handling`
clauses name.

Before finishing a turn that changed `index.html`, run `leaf page check <page>`
and fix every error. The final reply requires valid source, and its refusal arrives
after the model's turn has ended, when it can no longer correct the edit.

A `leaf-delivery` pointer queued before Leaf observed the task can still arrive as a
user message. Read it with `leaf delivery read <id>`: it was frozen for the queue, so
its reply has `writer: "agent"` for `leaf response reply <answer.ref>`, as `references/harness-codex.md`
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

If the user supplied an endpoint and `LEAF_CODEX_APP_SERVER` is absent, bind it
before serving starts an adapter on another route:

```bash
leaf codex start <page> --app-server <supplied-endpoint>
```

If an adapter already holds a different endpoint, follow the conflict diagnostic.
Terminal launch and independent-shell setup are in `references/codex-setup.md`.

### Full Leaf handoff

Use the canonical browser page by default. Run `leaf server start <page>` and
retain its exact keyed URL, and hand it over for a local browser. This runs Leaf's
theme, package widgets, anchored comments, versions, and state stream unchanged.

Serving starts or joins the task's delivery adapter before returning the URL,
using `LEAF_CODEX_APP_SERVER` as its endpoint. Re-serving restores an adapter that
stopped, including when the page server is already running. Follow
`references/conversation-loop.md`, "Status and handoff". The adapter
watches every page this task owns, and a completed turn does not stop it.

`leaf codex start <page>` connects delivery explicitly when claiming without
serving. It prints `{"task", "app_server", "started"}`; a null `app_server` means
Leaf is on the queue route in `references/harness-codex.md`. A later start reports
`started: false` and the running adapter's endpoint, and refuses an endpoint other
than the one that adapter holds.

A `leaf wait` this task already runs, or a watcher task, carries input without the
adapter, as `references/harness-codex.md`, "Routes without the adapter", describes; on those routes there is no App Server turn to bind, so
answer with `leaf response reply <answer.ref>`.

If serving refuses to connect delivery, fix its diagnostic before handing the
page over. Serving honors an existing direct `leaf wait`; an explicit
`leaf codex start` refuses while that wait holds the task's single wait lease.
