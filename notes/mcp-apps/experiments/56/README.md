# Experiment 56: Physical temporary reference path

## Purpose

Resolve the reference checkout to its physical path.
The npm lockfile dry-run succeeded there; no dependency or upstream code changes.

Expected outcome: locked setup, host readiness, HTTP boundary checks, and the
same direct-resource Leaf interaction checks pass. Codex inline rendering and
idle wake remain outside this reference-host test.

## Findings

Passed from a fresh reference checkout with locked installation and no upstream
source changes. The portable runner completed all 21 HTTP host/origin checks,
then the browser checks:

- Canonical Leaf theme/runtime presented directly in the MCP resource;
  `results/direct-leaf.png` is the presented page.
- A keyboard option choice and uniquely marked anchored comment reached the
  canonical log; the comment was visible in Leaf's normal Threads panel, as
  `results/direct-comment.png` shows.
- No nested Leaf iframe or external resource requests; empty declared connect,
  resource, and frame domains. Browser error capture was empty.
- The reference host accepted `ui/message`; this is not idle-wake evidence.

The source hashes match the reviewed runner, worker, server, bundle entry, and
observers. The bundle contains 15 widget modules and is 3,855,441 bytes; the run
tests this fixture, not every module's behavior. The normal suite also passed
791 tests, the focused MCP browser suite passed 8, and all source hooks passed.

This was the official reference host, not Codex's actual inline renderer.
Version/data transport, dynamic assets, and compact-layout parity remain outside
the fixed-page probe.

The compact [host result](results/reference-host.json),
[HTTP checks](results/http-security.json),
[browser observations](results/observations.jsonl), and
[source hashes](results/source.sha256) record the run. A new probe writes its
evidence under ignored `.tmp/`.
