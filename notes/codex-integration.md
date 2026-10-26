# MCP and further Codex integration work

Leaf reaches a Codex task in the desktop app, an IDE or a plain terminal only through
hooks and a message it queues between turns, which gives it no more control over a
turn than it has over a Claude Code session. Only on leaf.page and on an experimental
terminal route does it connect to the task's App Server. [Session lifetime,
“Watchers”](../src/leaf/session-lifetime.md#watchers) owns that delivery and
connection lifecycle, and
[harness-codex.md](../skills/leaf/references/harness-codex.md) the agent's side of it.
This note holds open design work.

## MCP and the CLI

Leaf can expose essentially all its agent-facing operations through MCP. The
useful architectural boundary is shared Python domain functions, with MCP and
the CLI as transport adapters. State computation, event admission and reply
settlement keep their existing owners.

There are four separate choices:

| Change                                                         | Benefit                                                                         | Cost                                                                             |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Run CLI commands through MCP, as the Codex plugin already does | Access outside the shell sandbox                                                | Still requires command syntax; subprocess and timeout handling                   |
| Expose typed operations                                        | Discoverable argument and result schemas; operation-specific permission choices | Schemas and adapters to maintain; host-dependent discovery and approval behavior |
| Serve the page through MCP Apps                                | Integrated rendering and a standard UI-to-conversation message route            | Iframe restrictions, asset delivery, navigation and host compatibility           |
| Run a remote MCP service                                       | No local Leaf installation or shared filesystem required                        | Authentication, storage, uploads, isolation and service operations               |

For coding agents already editing local files, typed tools alone offer a modest,
unmeasured improvement. The CLI already returns structured results and works
with their file tools. MCP does not inherently improve state guarantees,
rendering or response speed. Keep the CLI thin for local authoring, debugging
and automation; avoid maintaining a second implementation of the operations.

Agents without shell access are a larger opportunity, but exposing the current
commands is insufficient for them. Full authoring also needs source revision,
asset submission and package creation, preserving Leaf's open package model.
Local MCP and remote hosting are independent choices.

The recommended first experiment is the complete MCP Apps feedback loop below,
rather than converting commands one by one. Its main potential saving is removal
of browser handoff and harness-specific comment delivery. If only rendering
works, the gain is convenience while most delivery machinery remains.

## User-opened conversation panel

Leaf already has a Codex plugin and an MCP server. The current handoff serves a
page, then the agent calls Codex's `open_in_codex` with its URL to open a browser
tab beside the chat. The MCP server's `run` tool executes Leaf commands; it
registers no UI resource or panel entrypoint.

An MCP App could add a Leaf entry to the conversation's panel picker. Its main
benefit would be letting the user find and reopen this chat's pages without an
agent turn or locating their URLs. A single panel could also let the user switch
among those pages. These are discovery and navigation benefits; the existing tab
already renders Leaf and carries live revisions and comments. Panel registration
alone establishes neither faster replies nor less transcript clutter.

[MCP Apps](https://apps.extensions.modelcontextprotocol.io/api/documents/Overview.html)
can also deliver the actual interactive page as an HTML UI resource. The host
renders it in a sandboxed iframe, and the page reads state and submits actions
through the host's MCP bridge. With assets and requests carried through that
bridge, this can remove the need for a localhost HTTP listener. Leaf retains
its renderer, widgets and event log. App-only tools let widget interactions run
without model calls or tool results in the model's context, as the existing
browser page already does through HTTP.

The cost is adapting asset loading, navigation, media and nested samples to the
host's iframe and network policy. A local `codex-mcp-app` prototype explored
this transport using the canonical Leaf endpoint and renderer. Its 22 October
2026 reference-host checks reported successful interactions, but full native
Codex rendering and idle-chat delivery remained unverified. The prototype is
feasibility evidence, not proof of a better end-to-end experience.

The extension would add a view tool, an HTML MCP resource, and a `thread`
entrypoint. Codex invokes the entrypoint when the user selects it; the panel can
call app-visible tools through the MCP Apps bridge. Model access is a separate
visibility choice. The installed Inbox 0.2.10 keeps its view tool app-only and
notes that model-called UI tools appear inline in the transcript. Its panel
registration is a useful example, independent of its full-text queued messages.
See OpenAI's [conversation panel registration](https://developers.openai.com/plugins/build/extensions)
and [tool visibility reference](https://developers.openai.com/plugins/reference).
This is source inspection as of 22 October 2026, not a tested Leaf integration.

The first experiment should open an existing page, record a comment, start agent
work through `ui/message`, and show the agent's revision in the same page. Test
both idle and busy chats, then page switching, reopening and delivery after the
view closes. Check that the comment is durably recorded and delivered once,
and that the host preserves turn serialization and interruption behavior.
Measure which existing integration this replaces before expanding the surface.

## Comments from an MCP App

The [MCP Apps specification](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/draft/apps.mdx#requests-app--host),
checked on 26 October 2026, distinguishes `ui/message`, which sends a message
into the conversation and is described as triggering follow-ups, from
`ui/update-model-context`, which supplies context for future turns. A plain MCP
server notification does not itself instruct the host to start an agent turn.

An embedded Leaf page could record the user's comment through Leaf's existing
admission path, then send `ui/message` to have the host run the agent. This could
replace Codex's queued-message delivery for comments made in that view. It is
not an inherent MCP limitation; support and idle/busy behavior need testing in
the actual host. A successful message request alone does not prove the agent
received and handled the comment.

This UI-to-host route depends on a live view. Background server delivery after
the view closes still needs a host-supported mechanism. Nor does `ui/message`
promise delivery without adding a conversation message. Those are separate
requirements from rendering the page and starting work on a visible comment.

Leaf's current alternatives are described by the watcher contract linked above:
Claude Code normally uses a background Stop-hook watcher to wake its session;
an explicit `leaf wait` returns input into an already waiting agent call;
Codex's adapter queues input or starts a turn through an accessible App Server.

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

Candidate model tools would read page state, reply, declare work and validate
authored changes. MCP tools or App Server dynamic tools could call the same
Python functions as the CLI, instead of constructing arguments for the existing
generic `run` tool (`codex_tool.py`). "Evaluate a typed reply body" below records
the streaming constraint on such a tool.

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
