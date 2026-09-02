# Experiment 3: Wait for the host's tool selection

## Purpose

Run the same compact ask after making the browser driver wait until the official host has selected `leaf_open_page` and populated its default `{}` input.

**Changes from experiment 2:**

- Wait for the Tool select to hold `leaf_open_page` and the Input textarea to hold `{}` before filling the page path.
- Raise the browser assertion timeout to 15 seconds for the nested sandbox handshake.

**Configuration:**

- Transport: streamable HTTP adaptation of the shipped stdio MCP server
- UI: disposable `ui://` HTML resource
- Return path: `callServerTool` → Leaf `EventEndpoint`
- Supported ask: one current page-scoped, single-choice `lf-options` decision
- Durable authority: authored revision plus `events.jsonl`
- Reference host: ext-apps commit `10195ad91851502134930e9b80ec2c04e277a720`
- Authored fixture: `examples/design-decision.html`

**Expected outcomes:**

- If a keyboard choice appends `choose` and teardown/reopen returns an empty ask, the app has no second state authority.
- If the 420×360 iframe has no horizontal overflow and exposes three short option labels, the compact projection is viable for the shipped substantial decision.
- If the host console is clean and the app never contacts a Leaf page server, the bundled resource and app-only tools are sufficient.

## Findings

The readiness wait worked: the reference host passed the page argument and Leaf accepted `leaf_open_page`. The app did not load because the experiment launched the host's TypeScript server with `tsx`; in this mode `import.meta.url` was undefined, so the host derived the wrong `dist/` path and returned 404 for its own sandbox HTML. A direct request reproduced the 404 while the built file existed. The host's package script specifies Bun, so experiment 4 changes only that runner.
