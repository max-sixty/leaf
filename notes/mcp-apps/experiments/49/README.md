# Experiment 49: Complete direct-resource regression

## Purpose

Repeat experiment 47 with the Threads toggle state respected, as observed in
experiment 48. Keep the successful host running as the user's preview. The
fixture banner explicitly says this transport probe has no agent wake attached.

Expected outcome: all rendering, fresh-action, fresh-comment, ui/message, CSP,
and resource-request assertions pass. No claim about Codex's own app host or
idle wake is made.

## Findings

The headless observer still found the comment hidden despite checking the
Threads toggle. This contradicts the panel-toggle explanation inferred in
experiment 48. Rendering and durable events passed; experiment 50 captures
the hidden node's ancestor styles and a failure screenshot to locate the cause.
