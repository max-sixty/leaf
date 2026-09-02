# Experiment 36: Leaf directly inside the MCP resource

## Purpose

Can the canonical Leaf runtime render and record reader actions when the HTML,
theme, registry, and JavaScript arrive in `ui://` itself?

**Changes from experiment 35:** use direct MCP Apps delivery rather than an
ordinary browser page. No localhost iframe, detached adapter, or active goal.

**Configuration:**

- Fresh `design-decision` fixture, with the checkout's complete default layer.
- Fixed-page experimental MCP server, separate from the installed Leaf plugin.
- Bundle the canonical runtime and widgets; adapt asset and API transport only.
- Empty connect, resource, and frame origin allowlists.
- A separate native button calls `ui/message` only on a reader press.

**Expected outcomes:**

- A presented page, real option action, anchored comment, and server-log receipt
  prove direct delivery and interaction in the tested host.
- Merely reading the resource or returning a successful tool result does not
  prove that its runtime rendered.
- An accepted `ui/message` proves the bridge exchange, not an idle Codex wake.
  That needs a fresh reader press after the task has ended its turn.
- Version navigation, updates to the bundled layer, and cross-session draft
  persistence are outside this fixed-page transport probe.

## Findings

The launcher did not reach its first output or create the results directory.
The shell remained alive without children; no MCP resource was built or read.
An explicit `/bin/sh -x bin/leaf --version` succeeded immediately. Experiment 37
repeats with explicit system shell paths. This attempt provides no MCP evidence.
