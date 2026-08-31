# Experiment 18: Submit from the host's selected value

## Purpose

Remove the invalid descendant-option assertion and gate the call on the actual
selected value consumed by the reference host's submission handler.

**Changes from experiment 17:**

- Wait directly for the tool select's value to equal `leaf_open_page`.
- Do not query its child options.
- Leave every product, transport, CSP, fixture, and page measurement unchanged.

**Expected outcomes:**

- The rendered Tool Input panel proves that the exact page argument was passed.
- The full Leaf iframe then provides direct evidence about loopback framing.
- If framing succeeds, the same run measures layout, accessibility, console
  output, fullscreen negotiation, and a real keyboard event.

## Findings

The direct value assertion still resolved the host's earlier empty `<select>`
through Playwright's label engine, while its timeout accessibility snapshot and
screenshot both showed the replacement select populated with `leaf_open_page`.
This is a locator identity problem during React hydration, not a missing MCP
tool. No call was made. Experiment 19 uses the form's concrete DOM order and a
browser-side value predicate, avoiding that stale label resolution.
