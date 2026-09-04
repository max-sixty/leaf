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

One detached adapter watches every page this task owns. The first input after a
turn ends opens a delivery epoch and queues one new user turn in this same task.
Later input joins that epoch until the turn which processes it ends. Starting the
command again for another page adds that page to the same task-wide watch.

The loaded Desktop client starts that later turn and keeps ownership of execution
and approvals. If the task has been unloaded, the item stays queued until Codex
reopens it; the adapter never resumes the task or answers client requests on the
user's behalf. The small queued message is a `leaf-delivery` XML element shown as
one line in a code block. It names the `$leaf` skill and points to the persisted
epoch. Each batch carries its page, URL, thread context, and exact events rather
than copying instructions or an arbitrarily large batch into Codex's bounded text
input.

Input arriving while the turn is active adds a batch to that same payload and
creates no queued message. The prompt and Stop hooks carry its pointer into the
running turn. If another prompt opens the task before the pending queue command
runs, that hook supplies the pointer and cancels the redundant queue item. Stop
offers any batches newer than the accepted queue snapshot. A pointer supplied only
by the prompt hook is offered again at Stop because that hook has no delivery
receipt. After Stop supplies a pointer, its next acknowledged invocation closes the
epoch unless a newer batch arrived. The adapter owns `leaf wait` and `leaf ack`;
the task owns replies, revisions, page status, and the handoff back to `waiting` or
`idle`. If an active turn produces no later hook for fifteen minutes, the adapter
queues the same epoch pointer; a legitimately long turn can therefore receive a
duplicate wake.

If `leaf codex start` refuses to start, do not finish over a live page. Follow its
diagnostic: an existing foreground `leaf wait` must be stopped before the adapter
can take the task's single wait lease, and an unavailable Codex queue command
cannot receive later turns.

An optional separate Codex watcher remains a fallback that requires the user's
explicit authorization because it creates a visible task. Its route is in the main
skill.
