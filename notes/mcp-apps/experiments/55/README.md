# Experiment 55: Reference host outside hidden directories

## Purpose

Repeat experiment 54 with the official reference checkout in an OS temporary
directory. The host's absolute Express `sendFile` path rejects hidden parents;
this keeps its upstream code unchanged. Check `/sandbox.html` during readiness
so a file-serving failure stops before browser interaction.

Expected outcome: the same direct-resource interaction checks pass once the host
can serve its sandbox. HTTP security checks, bundled Leaf, and the event path
are unchanged. This still does not test Codex's actual inline renderer or wake.

## Findings

Stopped during `npm ci`, before host launch. The macOS temporary path used the
`/var` symlink, and npm misidentified the workspace root while validating its
lockfile. The same checkout and lockfile passed a read-only `npm ci --dry-run
--ignore-scripts --no-audit --no-fund` under its physical `/private/var` path.
The next attempt resolves the temporary directory with `pwd -P` before use.
