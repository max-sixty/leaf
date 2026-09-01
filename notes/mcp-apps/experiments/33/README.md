# Experiment 33: Reused Codex candidate process

## Purpose

Submit the capability- and readiness-gated candidate from experiment 32 and
verify that Codex skips its disallowed localhost frame before rendering the
snapshot fallback.

**Changes from experiment 32:**

- The app checks the host-approved frame domains before assigning the complete
  page URL.
- An attempted frame remains hidden until the canonical page posts its readiness
  marker, with a bounded snapshot fallback when no marker arrives.

**Configuration:**

- MCP server name: `leaf_candidate`.
- Codex task: `01a05e6e-c363-7fc2-a0e3-b774e2c68f4a`.
- Tool: `leaf_present`.

**Expected outcomes:**

- A newly launched candidate process serves the current adaptive bundle.
- Codex reports no approved HTTP frame domain, so the app avoids a nested
  localhost request and calls `leaf_snapshot_refresh`.

## Findings

This attempt was invalid because `leaf_candidate` reused the already-running
pre-fix MCP process. The tool call completed without an approval prompt, but the
card still ran the old snapshot bundle against the full-page result. It showed
`rundefined` and failed while calling `replaceAll`.

The result measures process reuse, not the submitted candidate. Screenshot
evidence remains at `/tmp/leaf-experiment-33.png`; it is not copied into the
repository. Experiment 34 changes the server identity so Codex must launch a new
process.
