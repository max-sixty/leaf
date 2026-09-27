A command hub has one authored goal tree in `lf-command`, whose entry says where
each worker sits. The package derives the header, stopped-work reading, live-worker
view, and action record from the tree and log. Put each Ask
or input beside the goal it blocks, and author no role enum, progress count,
relative report time, or other summary of the same work. On a sidebar page (`<main
class="layout-sidebar">`), lay the tree in the body and put an empty
`lf-command-readings` naming the command at the head of the page's `aside`, so the
operator's readings stand beside the tree they summarize rather than above it. A
project-specific goal or worker widget joins the projection through `$command.widgets`, whose entry states
what it owes.

Offer a consequential host operation, such as restarting a worker, landing a branch,
or archiving work, as one `lf-option` in the `lf-ask` of the goal it acts on, inside an
`lf-options choose` group. Name the exact worker and worktree in the option's words and
state what running it changes. The pick reaches you as the user's answer, and you run
the operation with the host's own tools.
