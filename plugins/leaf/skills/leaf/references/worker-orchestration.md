# Worker orchestration

Read this only when other sessions report into an orchestrator-owned page, or
when a worker receives a Leaf assignment. Leaf reports page state; it does not
create workers, branches, or worktrees.

## Orchestrator assignment

Before work starts, give the worker:

- the absolute path to the launcher that initialized the page (`$LEAF`)
- the absolute page path (`$PAGE`)
- a stable display name for `LEAF_AGENT`
- the worker's `lf-agent` row id and `lf-task` id
- the required outcome and constraints

Retain the host task handle and execution permissions. The orchestrator alone
waits, acknowledges batches, changes page status, publishes versions, and writes
`done` after accepting or landing the work.

Leaf persists the page, log, and event attribution; it does not persist host
task handles. A logged session id identifies who spoke and is never an address.
When a worker becomes unreachable, a host-selected successor starts with
`leaf page state`, keeps completed rows as history, publishes unreachable
nonterminal rows as `idle` without `on`, then assigns the remaining work to a
fresh task and retains that new handle locally.

A page normally carries an `lf-roster` beside its work. Each worker owns its row;
the row's `state` and `doing` say who holds the work and what they are doing.
Elapsed time is calculated from reports, so never author “just now,” “12 min
ago,” or a wall-clock report time in markup.

## Worker reports

Use the assigned launcher for every Leaf write. Start by moving the roster row
and task:

```bash
LEAF_AGENT="$WORKER" "$LEAF" report "$PAGE" "$ROW" state state=working doing="<current activity>"
LEAF_AGENT="$WORKER" "$LEAF" report "$PAGE" "$TASK" status status=active
```

If `report` fails, return its exact error through the retained host task and run
no other Leaf command.

Report the row whenever the activity changes and often enough that silence means
something; keep it within the roughly quarter-hour working claim the page shows.
Both `state` and `doing` are required on a row report.

- A blocker moves row and task to `blocked`, with the immediate blocker in
  `doing`.
- A completed handoff moves the task to `review` and the row to `waiting`.
- The orchestrator writes `done` only after review or landing.

For a routed user comment, reply under the worker's identity, then report any
resulting state change:

```bash
LEAF_AGENT="$WORKER" "$LEAF" reply "$PAGE" --to "$THREAD" --text "<answer>"
```

The worker never runs `leaf wait` or `leaf ack`, changes page status, publishes a
version, or handles an event the orchestrator did not route to it.

## Orchestrator handling

A report is provisional page state. It wakes the page's wait like a user event.
The next version either carries the reported state, marks the element `overruled`
with the reason in the version note, or leaves the report visibly provisional.
Publishing absorbs a report whose state the markup records. `version check`
refuses a contradictory version that neither absorbs nor overrules the report,
and a page must not end with report debt.

Route an anchored comment only when the orchestrator still retains the worker
handle for that assigned, nonterminal row or task. Comments on terminal rows or
tasks, and assignments whose handles are unreachable, remain with the
orchestrator. The worker replies through Leaf; the orchestrator processes the
report event and publishes the version that adjudicates it.
