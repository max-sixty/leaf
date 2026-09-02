# Experiment 56: Physical temporary reference path

## Purpose

Repeat experiment 55 after resolving the reference checkout to its physical path.
The npm lockfile dry-run succeeds there; no dependency or upstream code changes.

Expected outcome: locked setup, host readiness, HTTP boundary checks, and the
same direct-resource Leaf interaction checks pass. Codex inline rendering and
idle wake remain outside this reference-host test.

## Findings

Passed from a fresh reference checkout with locked installation and no upstream
source changes. The portable runner completed all 21 HTTP host/origin checks,
then the same browser checks as experiment 53:

- Canonical Leaf theme/runtime presented directly in the MCP resource.
- A keyboard option choice and uniquely marked anchored comment reached the
  canonical log; the comment was visible in Leaf's normal Threads panel.
- No nested Leaf iframe or external resource requests; empty declared connect,
  resource, and frame domains. Browser error capture was empty.
- The reference host accepted `ui/message`; this is not idle-wake evidence.

The source hashes match the reviewed runner, worker, server, bundle entry, and
observers. The bundle contains 15 widget modules and is 3,855,441 bytes; the run
tests this fixture, not every module's behavior. The normal suite also passed
791 tests, the focused MCP browser suite passed 8, and all source hooks passed.

The preview remains running under `--keep-live`. This is still the official
reference host, not Codex's actual inline renderer. Version/data transport,
dynamic assets, and compact-layout parity remain outside the fixed-page probe.
