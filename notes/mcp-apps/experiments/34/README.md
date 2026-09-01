# Experiment 34: Fresh Codex candidate process

## Purpose

Repeat experiment 33 with a new MCP server identity so Codex loads the current
adaptive resource, then verify the capability-gated snapshot fallback from the
desktop host logs and UI.

**Changes from experiment 33:**

- MCP server name changed from `leaf_candidate` to `leaf_candidate_final`.
- The task called only `leaf_present` on one compatible page.

**Configuration:**

- MCP server name: `leaf_candidate_final`.
- Codex task: `01a05e70-8af3-74e3-bc77-eec5400761a6`.
- Page: `.tmp/adaptive-probe`.
- Tool: `leaf_present`.

**Expected outcomes:**

- The new identity launches a fresh MCP process and reads the current shared
  resource.
- Codex's approved frame-domain set excludes Leaf's HTTP origin, so the app
  assigns no nested localhost URL and immediately calls the read-only
  `leaf_snapshot_refresh` tool.
- The presentation call and automatic refresh require no approval prompt.

## Findings

`leaf_present` completed once with zero approval prompts. On the task's first
view, desktop log lines 20769–20777 recorded the resource read, sandbox origin
`mcp-server-leaf-candidate-final`, committed widget frame, and running widget.
Line 20786 recorded one successful `mcpServer/tool/call` after app
initialization, matching the automatic `leaf_snapshot_refresh` fallback.

The server and task logs contain no `guest_load_failed`, `ERR_BLOCKED_BY_CSP`,
`replaceAll`, or nested localhost attempt. This confirms that the fresh
candidate avoided Codex's known CSP failure and started the read-only snapshot
path.

A screenshot captured 2.2 seconds after navigation shows the correct full-mode
shell (`Complete page · Draft · event 0`), no nested or broken frame, and the
status `This host did not approve the complete page frame. Opening the
comments-only snapshot…`. This visually confirms the capability-gate transition
before the snapshot content rendered. Another active app reclaimed focus a
second later, so this run still lacks a real-host screenshot of the final
snapshot. The successful refresh call in the logs and the repository's
real-Chromium tests cover that rendered fallback state. The screenshot remains
at `/tmp/leaf-experiment-34-final.png`; it is not copied into the repository.
