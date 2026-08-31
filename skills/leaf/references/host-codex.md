# Codex handoff and delivery

Read this immediately before handing a page to Codex.

## Experimental embedded MCP App

This path is merged for testing in installed Codex builds. Prefer it when it is
available so the experiment receives real use, but preserve the full browser
path and do not treat the merge as a commitment to keep or expand the embedded
surface. Leaf will decide whether to remove it, keep it compact, or build on it
after evaluating that use.

Prefer the bundled Leaf MCP tool whose exposed name ends in
`leaf_present` when it is available **and the tool result visibly attaches an
app**. Call it with the page's absolute directory. The app labels and renders the
active authored revision with the current event and delivery cursors; it does
not claim to show the browser's log-projected widget state. It writes comments
through Leaf's ordinary browser-event validator into `comments.jsonl`. It does
not start a loopback server, create a watcher, or introduce another current-state
store.

The embedded surface is deliberately a compact review, not a second copy of the
complete browser runtime. It renders the authored page and its local media,
supports page, passage, and element comments on text the file-side passage
reading can resolve, and can request fullscreen. Authored widget source is not
quotable and widget controls are inert. Start the browser path below when the user needs a
choice, drag, request, sign-off, or another package-owned interaction; also use
it when Codex returns only the tool's text fallback instead of rendering the app.
The app's **Full page** action asks Codex to start and open that browser path
when no live page URL is already available.

After the app durably appends a comment, it sends the exact pending Leaf batch
into model context and asks Codex for a follow-up turn. Only after the host
accepts that turn does the app acknowledge the batch. The arriving turn sets the
page `working`, follows `event-batches.md`, processes every event, then hands the
page back to `waiting` or `idle`. Do not call the app-only write, refresh, or ack
tools from the model; the embedded UI owns them.

## Full browser fallback

Run `leaf server start <page>` and retain its exact URL. After setting the page
`waiting`, run `leaf codex start <page>`, then finish the turn normally with that
URL. One detached adapter watches every page this task owns. It gives
each complete batch a stable delivery id, queues it as a new user turn in this
same task, and acknowledges only after Codex accepts the durable queue item.

The loaded Desktop client starts that later turn and keeps ownership of
execution and approvals. If the task has been unloaded, the item stays queued
until Codex reopens it; the adapter never resumes the task or answers client
requests on the user's behalf. The small queued message is a `leaf-delivery` XML
element pointing to the exact persisted batch rather than copying an arbitrarily
large batch into Codex's bounded text input. A later queued turn reads that
payload, processes it directly, and leaves only `leaf wait` and `leaf ack` to the
adapter. The turn still owns replies, revisions, and page status, including the
handoff back to `waiting` or `idle`. Starting the command again for another page
adds that page to the same task-wide watch.

If `leaf codex start` refuses to start, do not finish over a live page. Follow
its diagnostic: an existing foreground `leaf wait` must be stopped before the
adapter can take the task's single wait lease, and an unavailable Codex queue
command cannot receive later turns.

An optional separate Codex watcher remains a fallback that requires the user's
explicit authorization because it creates a visible task. Its route is in the
main skill.
