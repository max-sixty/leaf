# Further Codex integration work

Leaf reaches a Codex task in the desktop app, an IDE or a plain terminal only through
hooks and a message it queues between turns, which gives it no more control over a
turn than it has over a Claude Code session. Only on leaf.page and on an experimental
terminal route does it connect to the task's App Server. [Session lifetime,
“Watchers”](../src/leaf/session-lifetime.md#watchers) owns that delivery and
connection lifecycle, and
[harness-codex.md](../skills/leaf/references/harness-codex.md) the agent's side of it.
This note holds open design work.

## User-opened conversation panel

Leaf already has a Codex plugin and an MCP server. The current handoff serves a
page, then the agent calls Codex's `open_in_codex` with its URL to open a browser
tab beside the chat. The MCP server's `run` tool executes Leaf commands; it
registers no UI resource or panel entrypoint.

An MCP App could add a Leaf entry to the conversation's panel picker. Its main
benefit would be letting the user find and reopen this chat's pages without an
agent turn or locating their URLs. A single panel could also let the user switch
among those pages. These are discovery and navigation benefits; the existing tab
already renders Leaf and carries live revisions and comments. Faster replies,
less transcript clutter and removal of the HTTP server do not follow from a
panel registration.

The extension would add a view tool, an HTML MCP resource, and a `thread`
entrypoint. Codex invokes the entrypoint when the user selects it; the panel can
call app-visible tools through the MCP Apps bridge. Model access is a separate
visibility choice. The installed Inbox 0.2.10 keeps its view tool app-only and
notes that model-called UI tools appear inline in the transcript. Its panel
registration is a useful example, independent of its full-text queued messages.
See OpenAI's [conversation panel registration](https://developers.openai.com/plugins/build/extensions)
and [tool visibility reference](https://developers.openai.com/plugins/reference).
This is source inspection as of 22 October 2026, not a tested Leaf integration.

Revisit this when user-controlled page discovery warrants another host surface.
The first experiment would open an existing page from the picker without a model
turn, then exercise page switching, live revisions, comments and reopening. It
would establish how the existing Leaf renderer and server fit the host's iframe
and resource policy before choosing embedding or a transport adaptation. Keep
the page's event log, admission and delivery owners; adding the panel supplies no
reason to replace them. Delivering input without user messages remains the
separate capability below.

## Delivery without user messages

An idle desktop chat receives Leaf input through `codex queue` as a
`<leaf-delivery>` user message. The background `threads/wake/<id>` deep link
removes the external queue's polling delay, but checks for queued input before
resuming and supplies no input itself.

Leaf already starts message-free turns where it can reach the App Server, on the
experimental terminal route and on leaf.page:
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
  [Leaf running the agent session](leaf-run-sessions.md) weighs it across harnesses.
