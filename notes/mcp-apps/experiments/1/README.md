# Experiment 1: Repository-owned compact ask

## Purpose

Test whether the successful transport probe can become a narrow Leaf primitive without introducing a new state model. The slice should present one current `lf-options` ask, submit the ordinary declared action through Leaf's existing event endpoint, and reconstruct the settled result from the log after reopening.

**Changes from the pre-project feasibility probe:**

- Move the server boundary from ignored probe code into Leaf's Python package.
- Replace probe-specific state with a declaration-derived compact-ask projection.
- Replace direct loopback fetches with app-only MCP server tools.
- Build the UI resource reproducibly from tracked source and a pinned MCP Apps SDK.

**Configuration:**

- Transport: stdio MCP server
- UI: disposable `ui://` HTML resource
- Return path: `callServerTool` → Leaf `EventEndpoint`
- Supported ask in this experiment: one current page-scoped `lf-options` decision
- Durable authority: authored revision plus `events.jsonl`
- Reference host: ext-apps commit `10195ad91851502134930e9b80ec2c04e277a720`
- Authored fixture: `examples/design-decision.html`

**Expected outcomes:**

- If the app lists exactly one current ask and posts a schema-valid action, the boundary is narrow enough to productize experimentally.
- If teardown and a fresh read reconstruct the settled choice from `events.jsonl`, no second state authority was introduced.
- If unsupported or ambiguous decisions return an explicit fallback instead of guessed controls, the compact mode can remain deliberately partial.
- If the bundled app fits at 420×360 without horizontal overflow and keeps keyboard/focus behavior, the disposable inline surface is viable for small asks.
- If the app requires loopback network access, the design has accidentally retained the probe's host-specific dependency and should be revised.

## Findings

The seven focused repository tests passed and the pinned official reference host built. The attempt then stopped before either service launched because `commands.sh` redirected their logs into a `results/` directory it had not created. It produced no browser or host-policy evidence; experiment 2 repeats the unchanged subject with that launch-path error fixed.
