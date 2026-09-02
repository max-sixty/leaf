# Experiment 54: Reproducible direct-resource probe

## Purpose

Repeat experiment 53 with the reviewed developer runner: fetch pinned build
dependencies and the reference host into this checkout, resolve Playwright from
the installed Python package, and restrict the HTTP MCP endpoint to its local
hosts and the reference-host origin. The canonical Leaf rendering and event path
are unchanged.

This is a pre-merge regression run, not a causal comparison between those
independent changes. Existing experiment results remain untouched.

Expected outcome: a clean runner setup passes the HTTP boundary checks and the
same rendered-page, durable-action, visible-comment, ui/message, and no-network
checks as experiment 53. A failure means the reviewed probe is not reproducible
yet; it says nothing new about Codex's actual inline renderer or idle wake.

## Findings

The pinned dependencies and reference host built successfully; all 21 HTTP
host/origin checks passed. The browser timed out before Leaf presented because
the official host's sandbox route returned 404. Its Express `sendFile` call uses
an absolute path and rejects hidden parent directories; this checkout was under
`.codex/.../.tmp/`. The previous working reference checkout was outside hidden
directories. No Leaf rendering or gesture conclusion follows from this attempt.

The next attempt changes only the reference checkout's location to an OS
temporary directory and checks the sandbox route before starting the browser.
