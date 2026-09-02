# Experiment 46: Direct Leaf after host restart

## Purpose

Repeat experiment 45 after the user's restart cleared native-library startup
stalls. The protocol and fixed design-decision fixture are unchanged. Tighten
the observer to require fresh durable events and verify the new server identity.

**Expected outcomes:** the actual Leaf banner, widgets, choice, and anchored
comment render inside the MCP resource with no nested Leaf iframe or HTTP asset
requests. A successful reference-host message response proves only message
transport, not Codex idle wake-up. A failure localizes the missing adapter work.

## Findings

The real runtime presented successfully (15 widget modules bundled, no child
Leaf iframe). Keyboard selection appended action `b9e1f49767b7f7dd1c7b97266b2d2710`;
an anchored comment appended `66a469374792255073f614099fda8f1e`. The observer
then waited for a hidden thread copy instead of opening the Threads panel, so
the run failed before its message/CSP assertions. The next run fixes that
observer error, not the page transport.

Reference-host setup was restored from the official repository at commit
`10195ad91851502134930e9b80ec2c04e277a720`; locked `npm ci` and its basic-host
TypeScript/Vite build passed. Setup commands are in `setup.sh`.
