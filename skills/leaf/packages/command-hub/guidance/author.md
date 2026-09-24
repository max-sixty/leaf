A command hub has one authored goal tree in `lf-command`, whose entry says where
each worker sits. The package derives the header, stopped-work reading, live-worker
view, and action record from the tree and log. Put each Ask
or input beside the goal it blocks, and author no role enum, progress count,
relative report time, or other summary of the same work. On a sheet, lay the tree
in the body and put an empty `lf-command-readings` naming the command at the head of
the rail, so the operator's readings stand beside the tree they summarize rather than
above it. A project-specific goal or
worker widget joins the projection through `$command.widgets`, whose entry states
what it owes.
