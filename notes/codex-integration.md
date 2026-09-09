# Experimental Codex integration

This note records Leaf's experimental Codex App Server integration and the next
changes worth making. The protocol and browser path have automated coverage. The
normal interactive workflow has also been smoke-tested with a real Codex App
Server, CLI transcript, Leaf server, and browser. It describes the implementation
as of 2026-09-08.

The near-term target is Direction A: Leaf accompanies a normal user-owned Codex
task. Directions B-D remain possible, but they require Leaf to own progressively
more of the conversation and agent harness.

## What works now

`leaf codex launch` starts a private Codex App Server and an interactive Codex
terminal connected to it. From that task, `leaf codex start <page>` starts a
detached adapter that subscribes to the same task and watches every Leaf page the
task claims.

The adapter now provides:

- **Live conversation replies.** Feedback from one Leaf conversation starts a
  Codex turn. Its response streams into that thread and successful completion
  becomes an ordinary durable Leaf reply.
- **Live activity.** Plans, tool calls, reasoning summaries, and approval or input
  waits appear as the page's short current activity.
- **Event-driven wake-up.** Reader feedback to an idle task starts a Codex turn
  directly when it has one conversation target. Other input enters Codex's durable
  same-task queue. The user does not need to poll Leaf or type a message to wake it.
- **Durable delivery.** Leaf saves exact page events in a task-wide delivery epoch.
  Queue, prompt, and Stop-hook transitions preserve the input until it reaches a
  turn and receives a page-level receipt.

The direct turn receives the delivery as a structured `leaf_feedback` tool output,
so Codex does not first read a file pointer and the adapter owns its normal reply.
Codex still calls Leaf commands to revise the page, report status, and perform other
typed operations. Multi-conversation and disconnected deliveries keep the existing
file-pointer queue fallback. Leaf does not answer approvals or user-input requests.

The implementation is in `skills/leaf/scripts/leaf/codex.py`. The operating
contract is `skills/leaf/references/host-codex.md`; activity and delivery state are
specified in `skills/leaf/references/internals/session-lifetime.md`.

### Trying the prototype

For an installed Leaf plugin, this replaces the normal `codex` command:

```sh
leaf codex launch
```

Inside that Codex task, start the adapter for an initialized page:

```sh
leaf codex start <page>
```

The launcher owns the App Server and terminal together, so no server command has
to stay open in another tab. The terminal remains necessary because it is the
interactive App Server client: it displays the transcript and handles approvals.
Leaf is the delivery, response-stream, and durable-reply adapter for turns it starts.

## Direction A: a companion to the user's Codex task

Direction A keeps four boundaries:

- The existing Codex task remains the user's task, with its context and transcript.
- The Codex client remains the primary place for ordinary messages, approvals,
  interruptions, and configuration.
- Leaf may start a turn for one exact Leaf conversation. That turn remains visible
  in Codex, while its response also streams into that conversation and becomes a
  durable Leaf reply.
- Leaf conversations and page state remain durable only through explicit Leaf
  events and page revisions.

This keeps ownership at the level where the audience is unambiguous. A turn started
by the user in Codex replies only in Codex. A turn started from one Leaf conversation
replies both in the Codex transcript and in that conversation. Leaf still does not
own the task, route ordinary Codex turns, or handle approvals.

The design therefore separates four readings:

| Reading | Meaning | Lifetime |
| --- | --- | --- |
| Activity | A short reader-facing description of the current work or wait | Current operation |
| Live thread reply | Useful progress and response text for one addressed Leaf conversation | Current Leaf-started turn; final text becomes a reply event |
| Leaf conversation | An addressed exchange about a page passage or decision | Append-only Leaf event log |
| Settlement | Which exact reader events have been answered by a reply, revision, receipt, or declared action | Append-only Leaf event log |

One task may claim several Leaf pages, but the first implementation streams only a
delivery that belongs to one Leaf conversation. Several new messages in that
conversation may share the turn. A delivery spanning several conversations, a page
action without a conversation, or input from another page takes the current fallback
path. Compact activity may remain task-wide, while response text follows this rule:

| Turn origin and relationship to Leaf | Codex transcript | Leaf conversation |
| --- | --- | --- |
| Codex prompt | Full response | None |
| Leaf delivery starts the turn for exactly one conversation | Full response | Stream a live reply in that conversation, then save it as a reply event |
| More input arrives in that conversation during its Leaf-started turn | Full response | Continue the same live reply |
| Input spans another conversation, another page, or a Codex-started turn | Full response | Keep the current delivery path; do not stream the turn into a Leaf thread |

The response remains visible in Codex. Leaf also receives it when the delivery that
started the turn identifies one conversation. This is not a second transcript: the
in-progress text is a draft, and successful completion appends one ordinary Leaf
reply event.

### How Codex knows who asked

The transport tells Codex where input came from. It does not ask the model to infer
the source from prose.

A normal Codex question is a `userMessage` created by the interactive client. Leaf
submits reader feedback as a named `leaf_feedback` input containing a stable delivery
id, the page, and each event's id, kind, text, anchor, and conversation parent. A
standalone App Server `toolOutput` is distinct from ordinary user input and remains a
structured `functionCallOutput` item in task history. A live protocol smoke test
confirms that Codex accepts this input and responds to the reader's words.

This inbound `toolOutput` is separate from a model-initiated Leaf tool call. Leaf
creates the former as turn input; Codex creates the latter while handling that turn.

The model therefore sees both the words and their address. The delivery says, in
effect, “this reader comment came from this Leaf conversation.” Typed Leaf operations
carry that address into a page change when needed. The turn binding carries its final
message back to the same conversation without asking the model to select the target
again.

### How Leaf selects the stream

Leaf keeps one explicit record for the streaming path:

```text
Leaf delivery id → page, conversation, and event ids → Codex task id → Codex turn id
```

When Leaf calls `turn/start`, App Server returns the new turn id. Subsequent
notifications carry the task and turn ids, and message deltas carry an item id. The
adapter streams only agent-message items whose task and turn match that record. The
browser projects them only into the bound conversation. A normal turn started from
Codex has no Leaf delivery binding, so Leaf does not display its response.

If `turn/started` reaches Leaf before the `turn/start` response, the adapter buffers
events under that turn id until the response commits the delivery binding. It then
publishes or discards them according to the table above.

While that Leaf turn is active, another message in the same conversation enters it
through `turn/start` with another `toolOutput`; App Server treats that request as a
steer. Leaf requires the returned turn id to match the binding. Any other delivery
uses the fallback path. This rule avoids general audience routing while keeping every
event durable.

## Response streaming implementation

App Server emits `item/agentMessage/delta` while Codex writes and an authoritative
`item/completed` when the message finishes. The adapter accumulates those messages,
keeps response text out of task-wide activity, and projects it only into the bound
conversation. Writes are throttled to one update every 200 milliseconds.

Leaf's browser path is also already event-driven:

```text
App Server WebSocket notifications
        ↓
Leaf's detached Codex adapter
        ↓
replace-in-place live-reply state
        ↓
the page's /api/news EventSource announces a changed reading
        ↓
the browser fetches /api/state and redraws the thread
```

The page server checks for news every 50 milliseconds. With the client's current
throttle, a response can update roughly five times per second without introducing a
second browser transport. That is sufficient for visible streaming in the existing
conversation surface. Sending every token directly over a new socket would bypass
Leaf's state application and add recovery and ordering problems for little perceptible
benefit.

### Stream state

The activity line does not carry response text. The adapter publishes a transient
live-reply reading with:

- Codex task and turn ids;
- turn status: active, failed, interrupted, disconnected, or partial; successful
  completion with a public answer replaces the transient record with a durable reply;
- the target page and conversation;
- the current public response text and App Server item id.

Delta notifications extend the provisional text for one item. `item/completed`
replaces that text with the authoritative item. On successful `turn/completed`, the
adapter appends the final text as a Leaf reply and removes the draft. On failure or
interruption, it leaves the reader's message unsettled and marks the draft accordingly.
A reconnect reloads the active turn before consuming new deltas. If App Server cannot
return the bound turn, Leaf marks the draft disconnected and does not commit it as a
complete reply.

The draft can be replaced in place because it is not yet conversation history. Leaf's
existing state-read stamp orders crossing browser responses, so the stream does not
need a second ordering mechanism. Only the completed reply enters the append-only
event log.

### Reply body: message now, tool later

The implementation treats the turn's normal `final_answer` agent message
as the sole reply body. App Server streams that text through
`item/agentMessage/delta`, so Leaf can show it immediately and append the authoritative
completed message as a reply event.

A model-initiated `leaf_reply(text=...)` tool is also a valid design. Its call and
result would remain in the Codex turn, and Codex could still emit a final message.
Current App Server events, however, expose a dynamic tool call with its complete
arguments and do not expose argument deltas for that call. Putting the reply body in
the tool arguments would therefore make Leaf wait for the complete call instead of
streaming the body as Codex writes it.

Typed Leaf tools should initially carry page mutations and reply metadata such as
`awaits`, replacement anchors, and markup. They should not carry a second copy of the
streamed reply body. If a tool explicitly appends a reply, the adapter discards its
draft instead of appending another reply at turn completion.

If App Server later exposes argument deltas for the Leaf tool path, this choice should
be revisited. A typed reply tool could then own both the live text and the durable Leaf
event, while the final Codex message serves as a concise receipt rather than repeating
the answer.

### Browser presentation

Leaf should expose the conversation, not the agent harness:

- As soon as Leaf starts the turn, the target thread shows a live agent reply below
  the reader's message.
- Final-answer text streams into the same reply as Codex writes it.
- Successful completion turns the draft into a normal Leaf reply. The reader can
  answer it, anchor later discussion to it, and find it after a reload.
- When the answer is a page revision, the page carries the substance. The live thread
  reply says what changed and becomes the durable conversational receipt instead of
  duplicating the page in a long message.
- The page heading or status bar may show a short current action, wait, or failure.
  It should not expose tool logs, raw reasoning, turn ids, stream phases, or a second
  transcript.

This makes lower latency part of Leaf's normal message loop. The Codex transcript is
still useful to the task owner, but Leaf does not reproduce it as a separate panel.

### Implemented first slice

The first implementation includes:

1. `AppServerEvents` in `codex.py` returns separate activity and final-answer
   snapshots. Codex commentary remains in Codex rather than appearing as the
   Leaf reply.
2. An App Server turn is bound only when its delivery belongs to one Leaf conversation.
   Other deliveries continue through the existing path without response streaming.
3. The existing transient `stream` record carries the live reply rather than another
   durable store. The browser projects it only for its target page and conversation.
4. The existing thread UI renders that state as a provisional agent message and reuses
   `/api/news`; each stream write already changes the page reading and wakes visible
   tabs.
5. Successful turn completion appends the authoritative final text as one ordinary
   Leaf reply event. A failed, interrupted, disconnected, or partial stream must not
   settle the reader's message.
6. Completion of the final-answer item lets the Stop hook close the exact bound
   turn; `turn/completed` then commits the durable reply.
7. Tests cover progress-to-final transitions, authoritative completion, reconnect,
   failure, and input from another conversation taking the fallback path.
8. A fake App Server is driven through the real page server and browser, proving
   the complete WebSocket-to-thread path and durable final reply.

This slice changes delivery and presentation for one-conversation message turns. It
does not change page authoring, ordinary Codex turns, or approval handling.

## Current mechanics and further Direction A work

### Remove the per-page startup command

`leaf codex launch` should be the prototype's only special startup command. When
`leaf server start` or `leaf_present` claims the first page inside an App
Server-backed Codex task, it can idempotently ensure that task's adapter is running.
The adapter already discovers every later page the task claims, so each page does not
need its own process or command.

`leaf codex start <page>` can remain a recovery and diagnostic command while this is
proved, then leave the normal workflow. If the user's ordinary Codex client eventually
exposes the same App Server task, the launcher also becomes unnecessary: claiming the
first page is enough to attach Leaf.

### App Server's real turn lifecycle

The prompt and Stop hooks currently mint Leaf's opaque turn identity and mark its
boundaries. The client sees App Server's real `turn/started` and `turn/completed`
events and writes those ids and boundaries into each claimed page. Activity,
delivery, and the Codex transcript therefore refer to the same turn.

The hooks would still guard unanswered work and carry input when no direct App Server
delivery is available. They are no longer the primary source of turn lifecycle while
App Server is connected.

### Structured Leaf input

The delivery epoch remains the durable source of what Leaf owes Codex, while the
model receives a one-conversation delivery as structured input instead of a file
pointer:

- When the task is idle, `turn/start` with an empty ordinary input and a
  `leaf_feedback` tool output starts generation.
- During a Leaf-started turn for the same conversation, App Server can queue another
  tool output into that turn.
- During any other turn, Leaf keeps the input pending and starts its own turn later.
- The payload carries the delivery id plus exact page, event, and conversation ids.

This removes the model's preliminary read of the epoch file from the direct path.
The adapter still records transport acceptance, entry into a named Codex turn, and
settlement by Leaf operations as three separate facts.

`turn/steer` remains an alternative for more feedback from the same conversation.
The current path sends another `turn/start` with `toolOutput`; App Server steers it
into the active turn. Leaf requires the returned turn id to match, and any other
delivery takes the existing fallback path.

The current documented API has no compare-and-start operation that atomically requires
an idle task. If the interactive client starts a turn between Leaf's idle check and
`turn/start`, App Server may queue the tool output into that turn. Leaf can detect the
returned turn contents and suppress the live Leaf reply because the turn now has mixed
audiences. The feedback remains present in that Codex turn and can settle through
ordinary Leaf operations.

The current Codex queue remains the recovery path while direct App Server delivery is
experimental or the server is disconnected. Once direct delivery proves the same
durability across reconnect and resume, the duplicated hook and queue paths can be
removed where they no longer carry a distinct guarantee.

### Expose Leaf operations as model tools

Codex should see a small, typed Leaf interface rather than construct shell commands
for routine operations. The first useful operations are:

- read the current page state and outstanding obligations;
- reply to an exact conversation, including `awaits` and a replacement anchor;
- set task status on an exact page or subject; and
- validate the page after Codex edits its authored source.

MCP tools, or client-defined tools registered with App Server as `dynamicTools`, can
call Leaf's Python functions directly and return the appended event ids, active
revision, and remaining obligations. The current integration instead asks Codex to
run the `leaf` CLI. The CLI and tools should share the same Python functions rather
than implement two event paths.

This removes syntax and target-selection work from the model. It does not remove the
semantic decision: Codex still chooses whether feedback calls for a reply, a page
revision, both, or neither.

For the initial split between streamed messages and typed operations, see
[Reply body: message now, tool later](#reply-body-message-now-tool-later).

### Make delivery visible

Leaf already distinguishes **Sent**, **Queued**, **Picked up**, and **Active** from
durable evidence. Direct App Server delivery should sharpen those receipts:

- **Accepted** means App Server accepted this delivery id.
- **In turn** names the Codex turn that contains it.
- **Answered** appears only when a durable Leaf reply, revision, receipt, or declared
  action settles the exact event.

The streamed response is not evidence for **Answered**. This keeps the browser honest
while the reply is still provisional. **Answered** follows when the adapter appends the
completed response as a reply event, or another durable Leaf operation settles the
exact reader event.

## Implementation order

1. ~~Replace opaque Leaf turn ids with App Server turn ids and bind one conversation
   to each streaming Leaf-started turn.~~ Implemented in the first slice.
2. ~~Build and browser-test the live thread reply, including its durable
   completion.~~ Implemented in the first slice.
3. Start the task adapter automatically when its first page is claimed.
4. Add structured model-facing Leaf operations.
5. Run a vertical experiment with `toolOutput` delivery for idle and active turns,
   including disconnects and events racing turn completion.
6. Use `turn/steer` only for feedback in the same conversation if the tool-output path
   cannot deliver it with acceptable latency or semantics.
7. Remove queue and hook choreography only after the direct path has equivalent
   recovery evidence.
8. Re-evaluate a typed reply tool as the text transport if App Server adds argument
   deltas for the relevant tool-call path.

The first three steps provide streaming and a one-command workflow while ordinary
Codex turns and approvals stay in the Codex client. The later steps remove
model-mediated delivery work while preserving the same user-owned task and Codex
transcript.

## Directions kept for later

### Direction B: Leaf routes multiple conversations in the shared task

Leaf can extend from one addressed conversation per turn to turns that receive several
conversations or pages. Codex would then need to route each response or page change to
its exact audience rather than letting the turn binding decide. Leaf would also need a
defined route for approvals and input requests raised by those turns.

### Direction C: a Leaf-owned child task

The user's task hands a page to a separate Codex task that Leaf controls. This gives
each task one primary audience, but the child needs copied context and coordinated
workspace state. It is most plausible for standing pages or delegated work.

### Direction D: Leaf as the Codex client

Leaf owns the task, transcript, turns, approvals, interruptions, and reconnects. This
provides one continuous Leaf interface but makes Leaf an agent harness rather than a
page and feedback layer.

## Invariants

- The page directory and append-only event log remain Leaf's durable authority. App
  Server events are observations and delivery evidence, not another page history.
- Task activity, provisional thread replies, durable conversation events, page
  mutations, and settlement remain distinct.
- Routing uses stable task, turn, item, page, event, and conversation ids rather than
  matching phrases in model prose.
- The streaming path binds one Leaf-started turn to one conversation. Other deliveries
  use the existing path.
- Transport acceptance, model-context entry, and Leaf settlement are recorded
  separately. Recovery cannot silently drop or duplicate an event's effect.
- Raw reasoning is not streamed to the reader.
- Approvals remain in the user-controlled Codex client under Direction A.
- Codex-specific transport state does not enter Leaf's page or event schema.

## Relevant App Server primitives

The [Codex App Server documentation](https://developers.openai.com/codex/app-server/)
defines the primitives behind this plan. `thread/resume` subscribes a client to an
existing task. `turn/start` starts a turn. `turn/steer` appends input to the active
turn and requires its id. `item/agentMessage/delta` streams text, while
`item/completed` supplies the authoritative item. A standalone `toolOutput` can start
a turn or queue into an active one. App Server can also expose client-defined
`dynamicTools` to Codex, but its current event schema supplies complete tool arguments
rather than tool-argument deltas.

App Server supplies the transport and lifecycle. Leaf still defines which conversation
receives a live reply, when that reply becomes durable, which page events entered the
turn, and what settles them.
