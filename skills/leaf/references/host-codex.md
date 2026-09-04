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
the detached adapter below carries input back to this same task.

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

One detached adapter watches every page this task owns. The event log is the durable
mailbox; Codex's queue is only its edge-triggered wake. When the task is between
turns, the first batch gets a stable delivery id and queues a new user turn in this
same task. Leaf acknowledges that snapshot only after Codex accepts the durable
queue item, then keeps one wake marker standing until the prompt hook proves that a
later turn opened. A later Stop boundary retires the marker too, so a missed prompt
hook cannot park the adapter. Events arriving behind that marker remain in the
mailbox and do not queue more messages; the prompt hook snapshots them into hidden
delivery pointers before the model starts. Starting the command again for another
page adds that page to the same task-wide watch.

The loaded Desktop client starts that later turn and keeps ownership of execution
and approvals. If the task has been unloaded, the item stays queued until Codex
reopens it; the adapter never resumes the task or answers client requests on the
user's behalf. The small queued message is a `leaf-delivery` XML element shown as one
line in a code block. It names the `$leaf` skill and points to the exact persisted
batch. The skill owns the processing contract, and the payload carries the page URL
and batch rather than copying either instructions or an arbitrarily large batch into
Codex's bounded text input. The later turn reads that payload and the hidden pointers
for anything accumulated behind it. While a turn is open, the adapter never queues.
Its Stop hook snapshots every event that arrived during the model's work and carries
their same small delivery pointers into a continuation of that turn. The re-entered
Stop acknowledges exactly that snapshot. A missing continuation leaves the events
unacknowledged; after the task's fifteen-minute recovery window, they return to the
visible wake path. A continuation still running at that boundary can produce a retry
wake; its stable delivery id and page-and-sequence coordinates make the mandatory
pre-action log refresh a no-op rather than repeated work. Thus several clicks around
one wake produce one visible user
message without waiting for a debounce timer. A Stop hook can safely block only once;
an event arriving after its snapshot crosses the sharp boundary into the next wake
rather than being silently acknowledged. The adapter and hook own
`leaf wait` and `leaf ack`; the task owns replies, revisions, page status, and the
handoff back to `waiting` or `idle`.

If `leaf codex start` refuses to start, do not finish over a live page. Follow its
diagnostic: an existing foreground `leaf wait` must be stopped before the adapter
can take the task's single wait lease, and an unavailable Codex queue command
cannot receive later turns.

An optional separate Codex watcher remains a fallback that requires the user's
explicit authorization because it creates a visible task. Its route is in the main
skill.
