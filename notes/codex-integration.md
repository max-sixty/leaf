# Further Codex integration work

Leaf's current companion workflow is documented in
[host-codex.md](../skills/leaf/references/host-codex.md) and
[host-codex-app-server.md](../skills/leaf/references/host-codex-app-server.md).
[Session lifetime, “Carriers”](../skills/leaf/scripts/leaf/session-lifetime.md#carriers)
owns the delivery and connection lifecycle. This note holds open design work.

## Start the adapter when the first page is claimed

An App Server-backed task could ensure its adapter is running when `server start`
or `leaf_present` claims the first page. The adapter already discovers later
pages held by that task. This would remove the separate startup step from the
normal handoff, while retaining an explicit command for recovery and diagnostics.

Check both claim paths and task-wide lease handling before making startup
automatic. The terminal remains the interactive client for approvals and input.

## Expose typed Leaf operations

Provide model tools for reading page state, replying, declaring work, and
validating authored changes. MCP tools or App Server dynamic tools could call the
same Python functions as the CLI. Keep event admission and reply settlement in
those existing owners.

First test a complete feedback turn with the smallest useful tool set. Compare
it with the CLI path for target-selection errors and unnecessary model work.
The model still decides whether feedback calls for a reply, a revision, or both.

## Decide how additional input joins a running turn

Leaf currently gives each delivery slice its own turn. Before adding steering,
define what a user should see when their message joins a turn already answering
other input: which message the final answer settles, where that answer appears,
and what remains outstanding if the turn fails.

There is also a start race to resolve. `codex_adapter.start_delivery_turn` checks
that the task is idle before starting, but another client can start a turn between
those requests. Test that race and interruption/reconnect behavior against the
installed App Server before changing delivery policy. Generate its current schema
with `codex app-server generate-json-schema`; do not infer turn preconditions from
an older protocol snapshot.

## Evaluate a typed reply body

A typed reply tool could own both streamed text and the durable reply event if
App Server exposes its argument deltas. Verify that capability with the installed
server first. Complete arguments alone would delay the visible reply until the
call finishes. Any experiment must preserve the canonical reply writer and avoid
committing the same answer through both a tool and final-message handling.

## Broader product choices

These alternatives need a user-facing purpose before implementation:

- Route several threads' responses within one Codex turn. This needs explicit
  response targets and a policy for approvals and input requests.
- Delegate a page to a Leaf-owned child task. This needs context transfer and
  coordinated workspace ownership; standing pages are one possible use.
- Make Leaf the Codex client. This would add transcript, approval, interruption,
  and reconnect ownership to Leaf's page and feedback responsibilities.
