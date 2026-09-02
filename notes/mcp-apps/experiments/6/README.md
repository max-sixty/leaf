# Experiment 6: Install from the reference clone

## Purpose

Run the same compact ask after invoking npm from inside the pinned reference clone, which preserves its workspace link identities under npm 11.

**Changes from experiment 5:**

- Run `npm ci` and the basic-host build with the reference clone as the shell working directory instead of passing an absolute `--prefix`.

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

The vertical slice passed in the official reference host. The 420×360 outer frame gave the app a 414×354 content viewport; `scrollWidth` and `scrollHeight` equaled the client dimensions, and the three substantial authored options appeared as the short labels “Stateless JWT,” “Redis, cookie fallback,” and “Postgres table.” Keyboard activation appended an ordinary `choose` action on `session-options` selecting `opt-redis` at sequence 1. The app then showed “Nothing waiting here,” and showed the same after teardown plus a fresh model-visible open call, proving the log rather than iframe memory held the result.

The host console recorded one unattributed 404. The recorder's `focused` field also captured `document.body.textContent` after the choice and reopen, which included the 385 KB inline bundle twice and made the JSON result needlessly large. Experiment 7 changes instrumentation only to identify the request and record focus by address rather than text content.
