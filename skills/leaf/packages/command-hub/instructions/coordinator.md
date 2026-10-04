Leaf records and presents the work. The harness creates workers, branches, and
worktrees. Keep each harness task handle and the permissions needed to act on its
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
`"$LEAF" page instructions "$PAGE" worker` before its first Leaf command.

Workers write only the reports and routed replies their instructions give them; the
rest of the page stays with you, as `references/conversation-loop.md`, "Long-running
work", describes. That includes recording `done` after accepting or landing the work.

If a worker becomes unreachable, read where its row and task stand in
`leaf page state`, then hand the remaining work to a fresh harness task under a new
brief and retain its handle. Keep completed rows as history, and save the
unreachable worker's nonterminal row as `idle` without `on`.

A pick in a goal's Ask that names a harness operation is the user's instruction to run
it while it stands. A later pick in the same group replaces it, and the delivery
still carries the earlier one, so before acting read the group's current answer in
`leaf page state` and proceed only with the option that stands there. Verify the
worker and worktree it names against current harness state, and check there for an
earlier run of the same operation before you start, merge, or remove anything. The version you stamp afterwards records the plan the operation produced.

Route an anchored comment to a worker only while the assigned row or task is
nonterminal and its harness task is reachable: send the comment's text and anchor,
with its event id as `EVENT`. Comments on terminal or unreachable assignments stay
with you. The worker answers a routed comment itself. Each report it writes
reaches you as a delivered event, and that event's `handling` says how the next
stamped version of `index.html` answers it.
