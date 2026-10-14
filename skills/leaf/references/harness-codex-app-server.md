# Codex App Server handoff and delivery

Use this reference when the main skill's "Harness selection" picks Codex App Server.
Leaf starts a turn for each delivery of user input and writes that turn's opening and
final messages to the thread it answers. A harness that starts the task, such as
leaf.page, has already handed the page over; a terminal task hands it over as "Hand a
page over from a terminal" says.

## Delivery

While a task with Leaf's trusted tool hook is working, new input can arrive between
steps as a `leaf-delivery` pointer. Read it and answer with explicit commands, as
`harness-codex.md`, "Delivery", describes.

Otherwise, once the task is idle, Leaf starts a turn whose input is the delivery as a
`leaf_delivery` tool output, one slice per turn. Leaf acknowledges it, so run no
acknowledgement command, `leaf wait` or `leaf wait --ack`.

## Replies

A slice holds at most one thread reply for the turn to write, marked `kind: "reply"`
and `writer: "turn"`. Before your first tool call, write a short message to the user:
the answer, or what you are about to do. Leaf posts it to the thread at once; later
working messages stay in Codex. When the turn completes, Leaf posts your final message
as the reply.

When the reply needs widgets, an ask in prose (`--ask`), work promised beyond this turn
(`--todo`), a title or a changed anchor, write it with
`leaf response reply <answer.ref>` and the options in [threads](threads.md). The command
checks the reply and posts it at once, and your final message then posts nothing. Leaf
may title an untitled thread from your opening message, and that title stays.

If the user resolves the thread before the turn completes, your reply still posts and
reopens it. Other updates in the slice take the commands their `handling` names.

Before finishing a turn that changed `index.html`, run `leaf page check <page>` and fix
every error. If Leaf refuses to post your final message, it starts a correction turn
with the error and the same reply address; fix the problem and complete the answer.

A `leaf-delivery` pointer queued before Leaf saw the task can still arrive as a user
message. Read it with `leaf delivery read <id>` and follow its instruction; its reply has
`writer: "agent"`, so post it with `leaf response reply <answer.ref>`.

## Activity

Leaf shows the task's current step, such as a tool call or a wait for approval, in the
page's banner as what the agent is doing on the page as a whole. If you started an item
with `leaf task start`, its line stays the banner's sentence and the step appears in the
banner's details.

## Hand a page over from a terminal

A terminal task reaches App Server through a background adapter that serving starts.
It connects to the task's App Server as a second client and starts a turn for each
delivery once the task is idle. This route is experimental.

If the user gave you an endpoint and `LEAF_CODEX_APP_SERVER` isn't set, bind it before
serving:

```bash
leaf codex start <page> --app-server <supplied-endpoint>
```

If an adapter already holds a different endpoint, follow the conflict message.
`codex-setup.md` covers launching the terminal.

### Full Leaf handoff

Serve and hand over the page as `harness-codex.md`, "Full Leaf handoff", describes;
here the adapter uses `LEAF_CODEX_APP_SERVER` as its endpoint. It watches every page
this task owns and keeps running when a turn ends.

To connect delivery for a page you claim without serving it, run
`leaf codex start <page>`. It prints `{"task", "app_server", "started"}`; a null
`app_server` means Leaf is on the queue route in `harness-codex.md`.

When this task runs `leaf wait` itself, or a watcher task does, no App Server turn
writes the reply (`harness-codex.md`, "Routes without the adapter"), so answer with
`leaf response reply <answer.ref>`.
