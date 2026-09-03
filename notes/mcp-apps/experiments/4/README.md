# Experiment 4: Use the reference host's own runner

## Purpose

Run the same compact ask with Bun, the runner declared by the pinned reference host, so its sandbox server resolves `import.meta.url` and serves the built iframe proxy.

**Changes from experiment 3:**

- Launch `serve.ts` with `bun --watch`, matching the official package script, instead of `tsx`.

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

The Bun runner resolved the host source correctly, but Express's sandbox `sendFile` still returned 404 because its absolute path crossed Leaf's hidden `.tmp/` directory; the `send` package ignores dot-paths by default. A direct request against the identical pinned clone under `/tmp` returned the sandbox with status 200 and byte-for-byte equality. Leaf accepted the open call and appended nothing. Experiment 5 changes only the clone location.
