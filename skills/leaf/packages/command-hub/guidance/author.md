# Command Hub package

This package supplies the Command Hub's goal, worker, worktree, and record
widgets. Select the bundled package by name:

```bash
leaf page init --package command-hub <page>
```

A command hub has one authored goal tree in `lf-command`, whose entry says where
each worker sits. The package derives the header, stopped-work reading, live-worker
view, and action record from the tree and log. Put each Ask
or input beside the goal it blocks, and author no role enum, progress count,
relative report time, or other summary of the same work. A project-specific goal or
worker widget joins the projection through `$command.widgets`, whose entry states
what it owes.

The coordinating agent reads `leaf page guidance <page> coordinator` before it
assigns work.
