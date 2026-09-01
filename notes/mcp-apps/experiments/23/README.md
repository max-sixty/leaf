# Experiment 23: Corrected end-to-end page probe

## Purpose

Repeat the complete-page measurement after correcting the body-evidence branch's
local-variable scope.

**Changes from experiment 22:**

- Skip the disclosure-locator assertion when body-level call evidence is used.
- Change no implementation, host, fixture, or page measurement.

**Expected outcomes:**

- Leaf reaches upgraded, applied, and presented readiness in the nested frame.
- Inline and fullscreen readings characterize the usable surface.
- Axe, console, and keyboard event evidence cover accessibility and the durable
  return path.

## Findings

The complete Leaf page reached all readiness checks inside the MCP App. The
inline screenshot contains the ordinary Leaf status/navigation bar, document,
widgets, key hints, and live page footer; there were no Leaf console errors.
Requesting fullscreen also expanded the app to the host viewport.

The reference host then hid the app's display-mode button instead of exposing
the requested `Return inline` label, so the harness stopped before Axe and the
keyboard event. Experiment 24 records the post-request dimensions and control
state without requiring a return control, then completes those remaining checks.
