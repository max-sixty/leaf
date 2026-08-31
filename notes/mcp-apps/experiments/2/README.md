# Experiment 2: Create the result door before launch

## Purpose

Run the repository-owned compact ask through the official reference host, preserving experiment 1's code, fixture, host commit, dimensions, and browser actions.

**Changes from experiment 1:**

- Create `experiments/2/results/` before redirecting service logs into it.

**Configuration:**

- Transport: streamable HTTP adaptation of the shipped stdio MCP server
- UI: disposable `ui://` HTML resource
- Return path: `callServerTool` → Leaf `EventEndpoint`
- Supported ask: one current page-scoped, single-choice `lf-options` decision
- Durable authority: authored revision plus `comments.jsonl`
- Reference host: ext-apps commit `10195ad91851502134930e9b80ec2c04e277a720`
- Authored fixture: `examples/design-decision.html`

**Expected outcomes:**

- If the reference host exposes only `leaf_open_page` to its model-visible picker, app-only visibility is wired correctly.
- If a keyboard choice appends the declared `choose` event and teardown/reopen returns an empty ask, the app has no second state authority.
- If the app's 420×360 viewport has no horizontal overflow and all three choices are reachable, the compact layout is viable for a substantial single ask.
- If the iframe makes no network request to Leaf's page server, loopback CSP is no longer a prerequisite.

## Findings

The focused tests passed and both the Leaf server and reference host launched, proving the missing result directory was the first attempt's blocker. The browser driver then filled the tool input before the host's asynchronous server/tool selection completed; that selection reset the input to `{}`, so Leaf correctly rejected the missing required `page` argument. No event appended and the app did not render. Experiment 3 changes only that host-readiness wait.
