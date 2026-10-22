# Further Codex integration work

Leaf's current companion workflow is documented in
[harness-codex.md](../skills/leaf/references/harness-codex.md).
[Session lifetime, “Watchers”](../skills/leaf/scripts/leaf/session-lifetime.md#watchers)
owns the delivery and connection lifecycle. This note holds open design work.

## Delivery without user messages

An idle desktop chat receives Leaf input through `codex queue` as a
`<leaf-delivery>` user message. The background `threads/wake/<id>` deep link
removes the external queue's polling delay, but checks for queued input before
resuming and supplies no input itself.

Leaf already starts message-free turns through an accessible App Server:
`codex.start_app_server_delivery` sends `turn/start` with a `leaf_delivery` tool
output. The desktop implements this capability internally, but the 22 October
2026 inspection found no supported external desktop or MCP interface exposing
it. Leaf's MCP `run` tool carries commands from the agent to Leaf; registering
that server supplies no reverse delivery channel.

The missing capability is access to the desktop-owned App Server, or an API for
queuing non-user input. When one is available, reuse the existing delivery
envelope and acceptance path. Prove that an action on a page starts work in its
idle owning chat without adding a user message, while Codex retains turn
serialization and interruption policy.

## Typed operations

Provide model tools for reading page state, replying, declaring work, and
validating authored changes. MCP tools or App Server dynamic tools could call the
same Python functions as the CLI. Leaf's Codex plugin already declares an MCP server
whose one generic tool, `run`, runs a `leaf` command outside the sandbox
(`codex_tool.py`); a typed tool would stand beside it. Keep event admission and reply
settlement in those existing owners. "Evaluate a typed reply body" below measures
what Codex would send such a tool.

First test a complete feedback turn with the smallest useful tool set. Compare
it with the CLI path for target-selection errors and unnecessary model work.
The model still decides whether feedback calls for a reply, a revision, or both.

## Evaluate a typed reply body

A typed reply tool would own both the streamed text and the durable reply event only
if App Server streamed its arguments, and 0.160.0 does not. Its schema, experimental
methods included, streams agent messages, plans, reasoning, command and file output,
and file-change patches (`item/fileChange/patchUpdated`). No notification carries a
tool call's arguments while the model writes them, and a dynamic tool call's request
(`DynamicToolCallParams`) receives them complete. A typed reply would
therefore appear only when its call finished, later than today's streamed final
message. Check a later Codex with:

```bash
codex app-server generate-json-schema --experimental --out .tmp/schema
jq -r '.oneOf[].properties.method.enum[0]' .tmp/schema/ServerNotification.json
```

## Broader product choices

These alternatives need a user-facing purpose before implementation:

- Route several threads' responses within one Codex turn. This needs explicit
  response targets and a policy for approvals and input requests.
- Delegate a page to a Leaf-owned child task. This needs context transfer and
  coordinated workspace ownership; persistent pages are one possible use.
- Make Leaf the Codex client. This would add transcript, approval, interruption,
  and reconnect ownership to Leaf's page and feedback responsibilities.
