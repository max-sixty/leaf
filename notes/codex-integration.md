# MCP and further Codex integration work

Leaf reaches a Codex task in the desktop app, an IDE or a plain terminal only through
hooks, a message it queues between turns and, in a chat the desktop app holds open, a
turn it asks the app to start, which gives it no more control over a
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
Codex's adapter queues input, or starts a turn through the desktop app or an
accessible App Server.

## Delivery without user messages

An idle desktop chat that a window of the app has opened takes Leaf input as a turn
the app starts, through the router the app's own clients share
(`src/leaf/codex_desktop.py`). Any other desktop chat, such as one not opened since
the app last launched, still takes it through `codex queue` as a `<leaf-delivery>`
user message. The background `threads/wake/<id>` deep link removes the external
queue's polling delay, but checks for queued input before resuming and supplies no
input itself. A chat woken that way gains no owner, so it stays on the queue until a
window opens it. Ending that case needs an app that gives a chat an owner without a
window, or a queue that takes non-user input (`thread/queue/add` takes only
`UserInput`).

The router is private and could change with any app release. A change that stops the
start before it goes out falls back to the queue, and one that leaves its answer
unreadable leaves the start to the chat's transcript, so neither sends input twice. The
adapter's log (`sessions/<session>.codex.log`) gives the reason for each. A version
bump the app doesn't know reads as `no-client-found`, the same as a chat with no owner,
so a chat that returns to queued messages while a window shows it is the sign to read
the app's method table, which lives in its `app.asar` beside
`thread-follower-start-turn`.

What running each route on 4 November 2026 showed, with the desktop app at
26.1029.61003, its bundled Codex at 0.166.0-alpha.6 and the daemon at 0.166.0:

- **The local daemon and its proxy reach no desktop chat.** The app's chats run on an
  App Server child it speaks to over stdio, whose standard streams are socket pairs to
  the app's main process. `codex app-server daemon` is a separate process. Through it
  `thread/list` lists every chat, because it reads the shared `CODEX_HOME`, but each
  reads `notLoaded`, the chat in use included, and `thread/loaded/list` is empty.
  It can't take a chat over either. On a scratch chat the app held, `thread/resume`
  through the daemon was refused with `already has an active writer`, the lock at
  `$CODEX_HOME/thread-writer-locks/<id>.lock`, and `turn/start` with `thread not found`.
  `codex app-server proxy` relays bytes to a socket that speaks WebSocket, which is
  why JSON written to it gets no reply. Connect as `app_server_connect` does. On this
  Mac the daemon's cached login had also gone stale, so its turns failed `unauthorized`.
- **`CODEX_APP_SERVER_USE_LOCAL_DAEMON=1` doesn't move the app onto the daemon.** Its
  gate refuses any config override, and the app always passes one
  (`plugins.codex-app-tools@openai-bundled.mcp_servers.codex_app.enabled`). With the
  variable set and a daemon answering `daemon version`, the app still started its stdio
  child and the daemon loaded nothing.
- **`CODEX_APP_SERVER_WS_URL` does move it, for an app launched with it.** With
  `codex app-server --listen ws://127.0.0.1:<port>` and the variable set, a second
  client saw the app's open chat in `thread/loaded/list`, `turn/start` with a tool
  output ran in it, and the window drew the answer with no user message. That reaches
  every chat and would give the desktop the whole App Server route, streamed replies
  included, without the router. It wasn't built because it asks the user to launch the
  app that way, which a Dock launch doesn't, and to keep a server running, and because
  the router is off in that mode, along with what the app coordinates through it. The
  server also takes none of the app's own config overrides.
- **The router reaches an open chat.** `thread-follower-start-turn` carrying
  `codex.app_server_turn_start_params` started a turn in about 40 ms. Its stored items
  open on a `functionCallOutput` with no `userMessage`, and the window draws only the
  answer. That held for an idle chat, for one the window had moved away from, and with
  `thread_unload_delay_secs = 0`. During a running turn it steered into that turn,
  whose next boundary showed the tool output, and the turn finished as it would have.
  Through a Leaf adapter, a page comment opened its turn within a second and the
  agent's reply posted on the page.

To repeat this without touching a running app or its chats, start a second instance on
its own home, in the background, and read its window over DevTools. It has its own
router at `$CODEX_HOME/ipc/ipc.sock`:

```bash
open -n -g -j --env CODEX_HOME="$home" --env CODEX_ELECTRON_USER_DATA_PATH="$data" \
  --env CODEX_ELECTRON_START_IN_BACKGROUND=1 /Applications/ChatGPT.app \
  --args --user-data-dir="$data" --remote-debugging-port=9347 \
  --disable-backgrounding-occluded-windows --disable-renderer-backgrounding \
  "codex://threads/$id"
```

Symlink the login into `$home` (`leaf_dev.arms.codex_home` says why). The window stays
on its first-run screen for a new home. It got past that screen with an old
`desktop-first-seen-at-ms` and a saved workspace root in
`$home/.codex-global-state.json`, and `electron:onboarding-projectless-completed` and
`last_completed_onboarding` among its `electron-persisted-atom-state`; which of them
it needs wasn't isolated. `open` sends a `codex://` link to the default handler, the
user's own app, so give a running instance its links as arguments to its binary with
the same `--user-data-dir`. `open -j` doesn't keep a window from showing once the app
starts, so hide it with `NSRunningApplication`'s `hide`, under which it keeps working.
An instance also rewrites every browser's `com.openai.codexextension.json` native host
manifest to point into its own home. Afterwards, put each `path` back to the
`extensionHostPath` in `~/.codex/chrome-native-hosts-v2.json`, or ChatGPT for Chrome
stops reaching the user's app.

When Leaf can't read the app's answer to a start, it settles the start from the
chat's transcript, the rollout file under `$CODEX_HOME/sessions/`, by finding the
record of the turn's `leaf_delivery` tool output (`codex.transcript_delivery_turn`).
The app's bundled Codex 0.166.0-alpha.6, from app 26.1029.61003, wrote this record at
06:37 UTC on 5 November 2026. It was in a scratch chat that a probe client drove
through that binary's App Server, so the rollout's `session_meta` names the originator
`leaf-probe`, and the output is the probe's own text rather than a Leaf envelope:

```text
{"timestamp":"2026-11-05T06:37:47.820Z","ordinal":24,"type":"event_msg","payload":{"type":"item_completed","thread_id":"01a1aa6d-7a33-7b10-bfa5-4abf3d94c58c","turn_id":"01a1aa6d-8980-78a3-a770-578d863dcacd","item":{"type":"FunctionCallOutput","id":"fco_01a1aa6d-8980-78a3-a770-579bc2e71e00","name":"leaf_delivery","output":"{\"id\": \"probe0001\", \"note\": \"Leaf probe baseline. Reply with exactly the word: baseline\"}"},"started_at_ms":1793860667820,"completed_at_ms":1793860667820}}
```

The app runs the same binary as its chats' App Server
(`Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex app-server`), and
the rollouts of its own chats record every completed item in the same `item_completed`
envelope. No record was captured from a turn a window of the app started. Through
the same binary, Leaf envelopes of 55 bytes, 60 KB and 400 KB were each stored
verbatim, and `transcript_delivery_turn` returned the turn `turn/start` had answered.
In 711 transcripts from late October and early November, Codex wrote every record in
timestamp order, which lets the reader stop at the first record older than the
delivery.

To capture the record again, run the app's binary as `app-server` on stdio with
`CODEX_HOME` set to an empty directory. Send `initialize`, `initialized`,
`thread/start` and a `turn/start` built by `codex.app_server_turn_start_params`, then
read the record back:

```bash
jq -c 'select(.type == "event_msg" and .payload.type == "item_completed"
  and .payload.item.type == "FunctionCallOutput")' \
  "$CODEX_HOME"/sessions/*/*/*/rollout-*.jsonl
```

The home needs no login. Codex writes the tool output's record before it calls the
model, and the turn then retries the model's `401`; `turn/interrupt` ends it.

The app's transcript also hides or restyles a user message by its shape, which could
quiet the queue route: a text that parses as `<external_event …>` draws as an activity
row, and one whose `text_elements` carry the placeholder `aeon-continuation` isn't
drawn. This comes from reading the bundle and hasn't been run.

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
