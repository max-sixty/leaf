# Codex delivery loop

Read this immediately before starting Codex delivery for a page.

After setting the page `waiting`, run `leaf codex start <page>`, then finish the
turn normally. One detached adapter watches every page this task owns. It gives
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
