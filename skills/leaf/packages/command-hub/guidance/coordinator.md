Leaf records and presents the work. The host creates workers, branches, and
worktrees. Keep each host task handle and the permissions needed to act on its
result; a logged session id identifies a speaker but cannot address that task.

Choose each worker's durable scope to fit the project. A worker may own one leaf,
an area subtree, or project-wide coordination. Its brief sets these variables,
which the worker guide's commands use:

- `LEAF`: the absolute launcher path
- `PAGE`: the absolute page path
- `WORKER`: the display name it reports under, the `<strong>` name on its row
- `ROW`: its `lf-agent` id
- `TASK`: its `lf-task` id

Add the required outcome and constraints, and the instruction to read
`"$LEAF" page guidance "$PAGE" worker` before its first Leaf command.

Workers write only the reports and routed replies their guidance gives them; the
rest of the page stays with you, as `references/conversation-loop.md`, "Long-running
work", describes. That includes recording `done` after accepting or landing the work.

If a worker becomes unreachable, read where its row and task stand in
`leaf page state`, then hand the remaining work to a fresh host task under a new
brief and retain its handle. Keep completed rows as history, and save the
unreachable worker's nonterminal row as `idle` without `on`.

Route an anchored comment to a worker only while the assigned row or task is
nonterminal and its host task is reachable: send the comment's text and anchor,
with its event id as `EVENT`. Comments on terminal or unreachable assignments stay
with you. The worker answers a routed comment itself. Each report it writes
reaches you as a delivered event, and that event's `handling` says how the next
stamped version of `index.html` answers it.
