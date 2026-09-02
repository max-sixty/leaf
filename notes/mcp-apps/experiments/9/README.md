# Experiment 9: Shipped stdio boundary

## Purpose

Exercise the user-facing `leaf mcp run` command as a real subprocess with the
official Python MCP client, rather than calling the server object in-process or
adapting it to HTTP for the reference host.

**Changes from experiment 8:**

- Transport is the shipped stdio command, with no HTTP adapter or browser host.
- Negotiate the MCP protocol and inspect advertised tools and resources.
- Read the actual bundled `ui://` HTML through MCP.
- Call open and post, end the process, then read from a second fresh process.

**Configuration:**

- Server command: `bin/leaf mcp run`
- Client: the official Python MCP SDK resolved by this repository
- Authored fixture: `examples/design-decision.html`

**Expected outcomes:**

- Initialization, discovery, resource read, and tool calls complete without
  protocol or stderr contamination.
- The HTML resource is the committed self-contained app and carries the MCP App
  MIME profile.
- A second process reconstructs the settled state from `events.jsonl`.

## Findings

The shipped command completed the full MCP exchange in two independent stdio
processes. Both negotiated protocol `2025-11-25`; discovery returned one
model-visible open tool, two app-only read/write tools, and the single
`ui://leaf/compact-ask.html` resource with
`text/html;profile=mcp-app`. Reading that resource produced the exact SHA-256 of
the committed bundle (`f8dbab209fb870925c48016c196181ac4cc5cf047d58c070a232aadf10a29339`).

The first process opened the design-decision ask and posted `opt-redis` through
`leaf_post_event`, receiving status 200 and an empty projection at event 1. It
then exited. The second process independently opened the page at event 1 and
returned the same empty projection. `events.jsonl` contained the ordinary
validated `choose` action. No protocol diagnostics contaminated stdout or
appeared on stderr.
