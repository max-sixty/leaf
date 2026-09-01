# Codex handoff and delivery

Read this immediately before handing a page to Codex.

## Embedded MCP App

Prefer the bundled model tool whose exposed name ends in `leaf_present`. Call it
with the initialized page's absolute directory. Continue only when its result
visibly attaches an app; a text result alone means this Codex build did not render
the surface.

The attached app frames the complete canonical Leaf page: the same projected
document, package modules, comments, actions, versions, state stream, and event
endpoint as the browser handoff. The MCP process supplies one ephemeral localhost
origin, while each page receives a random capability path under it. That server is
presentation plumbing only. It creates no `service.json`, owns no current state,
and stops with the MCP session; the page directory and append-only log remain the
authorities.

If the app shell appears but its page cannot load, use the model tool ending in
`leaf_present_snapshot` for a comments-only authored view, or follow the browser
fallback below when the user needs package controls. Do not call the app-only
refresh or write tools from the model.

The app does not claim that a host's `ui/message` response delivered anything to
Codex. Before finishing the handoff, set the page to `waiting` and run `leaf codex
start <page>`. The detached adapter is the sole wake and acknowledgement carrier:
it queues the persisted batch into a later turn of this task and advances the
cursor only after Codex accepts that durable queue item. Then finish the turn by
saying the Leaf page is attached; an embedded page has no durable URL to invent.

## Full browser fallback

Use this path when `leaf_present` returns only text, when the host refuses the
nested local page, or when the user asks to open Leaf separately. Run `leaf server
start <page>` and retain its exact URL. After setting the page `waiting`, run `leaf
codex start <page>`, then finish the turn normally with that URL.

One detached adapter watches every page this task owns. It gives each complete
batch a stable delivery id, queues it as a new user turn in this same task, and
acknowledges only after Codex accepts the durable queue item. Starting the command
again for another page adds that page to the same task-wide watch.

The loaded Desktop client starts that later turn and keeps ownership of execution
and approvals. If the task has been unloaded, the item stays queued until Codex
reopens it; the adapter never resumes the task or answers client requests on the
user's behalf. The small queued message is a `leaf-delivery` XML element pointing
to the exact persisted batch rather than copying an arbitrarily large batch into
Codex's bounded text input. The later turn reads that payload and leaves only
`leaf wait` and `leaf ack` to the adapter. It still owns replies, revisions, page
status, and the handoff back to `waiting` or `idle`.

If `leaf codex start` refuses to start, do not finish over a live page. Follow its
diagnostic: an existing foreground `leaf wait` must be stopped before the adapter
can take the task's single wait lease, and an unavailable Codex queue command
cannot receive later turns.

An optional separate Codex watcher remains a fallback that requires the user's
explicit authorization because it creates a visible task. Its route is in the main
skill.
