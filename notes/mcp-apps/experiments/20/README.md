# Experiment 20: Hydration-stable host submission

## Purpose

Use concrete DOM controls for the reference host's small form, then rely on its
rendered call record to verify the exact tool payload before probing Leaf.

**Changes from experiment 19:**

- Address the sole `textarea` directly instead of through its stale label
  locator.
- Retain the concrete selected-tool predicate introduced in experiment 19.
- Leave the Leaf app, frame policy, fixture, and measurements unchanged.

**Expected outcomes:**

- The Tool Input record names the submitted page directory exactly.
- The tool result initializes the full-page app and exercises loopback framing.
- A successful run measures both display modes and records a standard Leaf
  keyboard event through the existing HTTP/log path.

## Findings

The host submitted the exact page path, returned `leaf.page/v1`, loaded the MCP
App, and allowed its nested loopback document. That directly answers the
`frameDomains` question for the official reference host: loopback framing is
allowed.

The document's `/theme.css` and `/leaf.js` then returned 403. Leaf's handover
request sets a `SameSite=Strict` token cookie, which a browser withholds from
subresources when Leaf is embedded under a different site. Experiment 21 keeps
the ordinary server strict but gives the process-scoped MCP server a secure,
partitioned third-party cookie and presents it on `localhost`.
