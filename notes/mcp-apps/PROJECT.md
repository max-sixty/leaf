# MCP Apps

Leaf shipped an experimental MCP Apps transport until 2026-09-29 and removed it. It
was opt-in, Codex's default handoff opens the page in its browser pane instead, and
it had to follow every change to delivery, anchoring and the runtime. The last tree
that carries it is `a8ed55e68`:

```sh
git ls-tree -r --name-only a8ed55e68 -- skills/leaf/mcp-app skills/leaf/scripts/leaf build/mcp-app tests notes/mcp-apps | grep -i mcp
```

## What it was

`leaf mcp` ran a stdio MCP server that the Codex plugin registered. It exposed
`leaf_present` and one `ui://leaf/page/v1.html` resource, a bundle of
`@modelcontextprotocol/ext-apps` and Leaf's own app code. That resource framed the
real page from a process-scoped loopback server at an unguessable `/p/<capability>`
path, or, when a host refused the frame, drew a comments-only snapshot of its own. The
snapshot was a second, reduced rendering of the page: every change to anchoring,
threads or delivery had to be made there too.

## What experiment 56 found

A developer probe bundled the canonical vendored runtime straight into the `ui://`
resource and routed its reads and writes through MCP tools to the same
`PageStateService` and event door, with no nested frame. In the official reference
host the real design-decision page rendered, a keyboard choice and an anchored comment
reached the page's log and showed in the Threads panel, and the resource made no
network requests. `ui/message` was accepted, which is not evidence that it wakes an
idle Codex task. It was never tried in Codex's own inline renderer. By 2026-09-27
the probe no longer passed: the page rendered, but a pressed choice never reached the
log (`observe-direct.mjs` stopped at "No new matching durable event"). The next step
was to compare the fetch and `EventSource` stand-ins in
`a8ed55e68:notes/mcp-apps/probe/direct-entry.js` with how the runtime now sends a
gesture.

## Rebuilding it

Rebuild from the direct-resource design rather than the shipped transport: it keeps
one rendering, needs no loopback frame or capability paths, and puts nothing in the
page server's way. Before building, confirm in the host the user runs that its inline
renderer accepts the resource, that the resource's CSP admits what pages need
(`'unsafe-eval'` for `lf-chart` bodies), and that `ui/message` reaches an idle task.
