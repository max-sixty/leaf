# Experiment 5: Keep the reference host out of a dot-directory

## Purpose

Run the same compact ask with the pinned reference host cloned under `/tmp`, where Express can serve its sandbox HTML through the host's default `sendFile` policy.

**Changes from experiment 4:**

- Clone/cache the official reference host at `/tmp/leaf-mcp-apps-reference-10195ad9` instead of Leaf's hidden `.tmp/` directory.

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

The clone moved outside the hidden path, but npm 11 stopped before host launch
when `npm ci` was invoked with an absolute `--prefix`: it resolved workspace
links incorrectly and treated the clone directory name as a missing package.
The same install completed when run from inside the clone. Experiment 6 changes
only the install/build invocation's working directory.
