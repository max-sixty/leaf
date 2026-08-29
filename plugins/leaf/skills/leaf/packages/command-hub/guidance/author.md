# Command Hub package

This package supplies the Command Hub's goal, worker, worktree, and record
widgets. Select the bundled package by name:

```bash
leaf page init --package command-hub <page>
```

A command hub has one authored goal tree. Put the outcome in `lf-command`, then
place each worker once at the narrowest level matching its durable remit. A
project-wide coordinator sits directly under the command, an area owner under an
intermediate goal, and a specialist under a leaf. The optional `on` attribute is
only the worker's current focus.

Put each decision or input beside the goal it blocks. The package derives the header, stopped-work
reading, live-worker view, and action record from the tree and log. A
project-specific goal or worker widget can join the projection through
`$command.widgets`. Do not author a role enum, second roster, decisions list, progress
count, relative report time, or another summary of the same work.

The coordinating agent reads `leaf page guidance <page> coordinator` before it
assigns work.
