# Direct-resource MCP Apps experiment

The open experiment is to render Leaf's canonical runtime inside a host's
`ui://` resource and carry reads and gestures through MCP tools to the existing
`PageStateService` and event append boundary. It should keep one renderer and
one durable log, without a nested loopback frame or a reduced snapshot UI.

## Acceptance criteria

Test in the host the user actually runs:

- Its inline renderer accepts the resource and supports Leaf's required content
  security policy, including evaluation of `lf-chart` bodies.
- A keyboard choice and an anchored comment reach the durable page log and appear
  in the Threads panel.
- Reopening the view reconstructs the same state from the page directory.
- Version navigation, newly loaded layer assets, and external data use the same
  transport rather than bypassing it.
- Delivery reaches an idle task. A host accepting `ui/message` is not evidence
  that it starts a turn.

A successful reference-host render does not establish these properties in Codex's
inline renderer.

## Probe provenance

Leaf removed its experimental MCP Apps transport on 2026-09-29. The last tree
carrying the implementation and direct-resource probe is `a8ed55e68`. Inspect
its files without treating them as the current runtime:

```sh
git ls-tree -r --name-only a8ed55e68 -- notes/mcp-apps/probe
```

The direct-resource probe initially rendered a design-decision page in the
official reference host, saved a keyboard choice and an anchored comment, and
made no network requests. It was not tried in Codex's inline renderer. The
2026-09-27 run rendered the page but failed to save a choice:
`observe-direct.mjs` reported “No new matching durable event”. Compare the
fetch and `EventSource` adapters in
`a8ed55e68:notes/mcp-apps/probe/direct-entry.js` with the runtime's current gesture
transport before reusing the probe.

The probe's README records its runner and environment requirements. Its initial
scope did not carry version navigation, new layer assets, or dynamic external
data; those remain acceptance work rather than demonstrated capabilities.
