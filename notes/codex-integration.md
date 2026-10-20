# Further Codex integration work

Leaf's current companion workflow is documented in
[harness-codex.md](../skills/leaf/references/harness-codex.md) and
[harness-codex-app-server.md](../skills/leaf/references/harness-codex-app-server.md).
[Session lifetime, “Watchers”](../skills/leaf/scripts/leaf/session-lifetime.md#watchers)
owns the delivery and connection lifecycle. This note holds open design work.

## Typed operations

Provide model tools for reading page state, replying, declaring work, and
validating authored changes. MCP tools or App Server dynamic tools could call the
same Python functions as the CLI. Keep event admission and reply settlement in
those existing owners.

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
