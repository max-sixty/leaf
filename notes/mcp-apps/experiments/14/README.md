# Experiment 14: The complete Leaf page in an MCP App

## Purpose

Test whether an MCP App can carry Leaf's existing browser interface without
reducing the document to a compact projection. The app embeds the ordinary Leaf
page served from a process-scoped loopback server, so the authored document,
runtime, widgets, comments, versions, and event endpoint remain unchanged.

**Changes from experiment 13:**

- Replace the compact ask renderer with a full-page MCP resource.
- Let the MCP server own an ephemeral loopback page server for the lifetime of
  the MCP process.
- Declare that loopback origin through the app resource's `frameDomains` CSP.
- Offer the protocol's negotiated fullscreen mode while retaining an inline
  preview.

**Expected outcomes:**

- If the reference host honors the declared loopback frame origin, the real
  Leaf page reaches all three runtime readiness stamps inside the MCP App.
- A keyboard choice made inside the embedded page appends the ordinary Leaf
  event and repaints through the existing runtime.
- Fullscreen gives the page enough room for its normal layout; the inline frame
  remains usable as a constrained preview.
- If the nested page is blocked, the browser console and frame state identify
  whether CSP, mixed-content policy, sandbox inheritance, or loopback routing is
  the boundary.

## Findings

The run did not reach the frame-policy question. The official host called
`leaf_open_page`, but the MCP server rejected its `page` argument during tool
validation. The app resource still rendered and created `#leaf-page`; because
the originating tool result carried no page state, that iframe remained the
empty `about:blank` document and never acquired Leaf's readiness stamps.

The focused suite and the same tool over a real stdio MCP session both accepted
the page string. Experiment 15 must capture the reference host's concrete tool
arguments and returned error before changing CSP or page framing. This failed
run provides no evidence for or against loopback `frameDomains`.
