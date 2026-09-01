# Experiment 19: Concrete reference-host form probe

## Purpose

Avoid Playwright's stale label resolution during React hydration by observing
the exact DOM value read by the host form.

**Changes from experiment 18:**

- Wait in the browser for `document.querySelectorAll('select')[1].value` to be
  `leaf_open_page`.
- Address that concrete select for the recorded invocation.
- Keep the Leaf app, framing, fixture, payload, and all page checks unchanged.

**Expected outcomes:**

- The tool call finally crosses the reference-host form with its asserted path.
- Nested frame readiness provides direct loopback `frameDomains` evidence.
- On success, inline/fullscreen layout, accessibility, console output, and a
  keyboard event characterize how much of Leaf survives unchanged.

## Findings

The browser-side select predicate crossed immediately and found
`leaf_open_page`. The next label-based lookup failed on the textarea in the same
way: the timeout accessibility snapshot showed `Input: {}`, but the label
locator saw no element. This confirms the host replaces both labeled controls
during hydration. Experiment 20 addresses the sole textarea directly and still
uses the host's rendered Tool Input panel as independent submission evidence.
