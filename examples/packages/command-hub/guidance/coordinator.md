# Command Hub coordinator

Leaf records and presents the work. The host creates workers, branches, and
worktrees. Keep each host task handle and the permissions needed to act on its
result; a logged session id identifies a speaker but cannot address that task.

Choose each worker's durable scope to fit the project. A worker may own one leaf,
an area subtree, or project-wide coordination. Give it:

- the absolute launcher path as `$LEAF`
- the absolute page path as `$PAGE`
- a stable display name as `LEAF_AGENT`
- its `lf-agent` row id and `lf-task` id
- the required outcome and constraints
- the instruction to read `"$LEAF" page guidance "$PAGE" worker`

The coordinator alone runs `leaf wait` and `leaf ack`, changes page status,
publishes versions, and records `done` after accepting or landing the work.

If a worker becomes unreachable, start a successor with `leaf page state`. Keep
completed rows as history, publish unreachable nonterminal rows as `idle` without
`on`, assign the remaining work to a fresh task, and retain its new handle.

Worker reports are provisional page state. A later version records the report,
marks its element `overruled` with a reason in the version note, or leaves it
visibly provisional. `version check` refuses a contradiction that does neither,
and the page must not end with report debt.

Route an anchored comment only while the assigned row or task is nonterminal and
its worker handle is reachable. Comments on terminal or unreachable assignments
stay with the coordinator. The worker replies through Leaf; the coordinator then
processes its report and publishes the version that adjudicates it.
