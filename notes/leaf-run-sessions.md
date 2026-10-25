# Leaf running the agent session

Leaf works inside the user's harness. Hooks and watchers carry page input into a
Claude Code, Codex or Pi session the user started
([session lifetime](../src/leaf/session-lifetime.md#watchers)). This note weighs
the alternative, Leaf starting and driving the session itself through the Claude
Agent SDK, Pi or a Codex App Server, mainly for responsiveness: whether control
over what is sent when, priorities and interrupts would make replies faster. It
holds the evidence from October 2026 and the options; no option is chosen.

## Where a reply's time goes

[A small page change's reply](user-feedback-responsiveness.md#a-small-page-changes-reply)
times the whole reply on each harness. The model takes 17–28 s of every reply,
mostly generation and most of that thinking, and owning the loop doesn't shorten
it. Leaf's own share, delivery, hooks and `leaf` commands, is 1.2–4.9 s. When the
comment arrives during a 25 s shell command, the reply first waits about 25 s for
the command's tool boundary, the point between a tool's result and the next model
request where every harness takes new input. In real use that wait lasts as long
as whatever the agent runs.

## Waits on real pages

A survey of this Mac's real pages read 209 user messages on 44 pages from 19 to
24 October 2026, after #3169 made a busy Claude Code session take a comment at its
next tool boundary. Pages counted as real when their log held user text and agent
events carrying a harness session; replay sandboxes and messages to sessions that
had ended were left out. Busy means the agent's turn was running when the message
arrived, read from the Claude Code transcripts, and for Codex only from the page
log, which misses turns that wrote nothing to it.

| On arrival | Messages | Pickup, median / p90 | First reply, median / p90 | First reply over 30 s / 5 min | Real answer, median |
| ---------- | -------: | -------------------: | ------------------------: | ----------------------------: | ------------------: |
| Busy       |       65 |           8 s / 77 s |               21 s / 80 s |                        22 / 3 |               100 s |
| Idle       |      144 |        1 s / 4.2 min |            17 s / 4.6 min |                       45 / 14 |                48 s |

- 154 of 207 first replies were progress lines, so a faster path would speed up
  the answer itself, about 50 s slower when busy than idle at the median.
- Of the 22 busy messages whose first reply took over 30 s, one reader labelled 10
  questions, 10 change requests and 2 both. Counting by the real answer, 54 busy
  messages waited over 30 s; 12 of them were labelled questions and 25 went
  unlabelled, which puts the rate between 1.7 and about 6 questions a day.
- Of the 14 idle messages that waited over 5 min, about 6 are Claude Code wake-up
  gaps, where the comment sat until the user next typed in the terminal. The rest
  were test fixtures, a slow agent, or Codex sessions whose idleness the log can't
  confirm. Making wake-up reliable is the `TODO.md` item "Simplify the harness,
  host, and CLI workflow".

## What each surface lets Leaf control

Checked on 24 October 2026 against Claude Code 2.1.310, the Codex App Server
0.163 schema (`codex app-server generate-json-schema --experimental`), Pi 1.0.4's
extension types (`dev/pi/`) and `claude-agent-sdk` 0.2.174.

| Control                                 | Claude Code hooks                              | Codex app hooks and queue | Terminal Codex on App Server          | Pi extension                              | Agent SDK or `claude -p` stream-json |
| --------------------------------------- | ---------------------------------------------- | ------------------------- | ------------------------------------- | ----------------------------------------- | ------------------------------------ |
| A side lane with the session's context  | Outside the session: `--resume --fork-session` | Not checked               | `thread/fork`                         | No: `fork()` replaces the session         | `fork_session`                       |
| Model and effort per input              | No                                             | No                        | `model`, `effort` on `turn/start`     | `setModel`, `setThinkingLevel`            | `set_model`, `effort`                |
| Reply words as generated                | No: the transcript lands whole messages        | No                        | The final message; not tool arguments | `message_update` carries tool-call deltas | Partial messages, `input_json_delta` |
| Interrupt the turn                      | No                                             | No                        | `turn/interrupt`                      | `ctx.abort()`                             | `interrupt()`                        |
| Reorder queued input                    | No                                             | No                        | `thread/queue/reorder`                | No                                        | Leaf sends the next input itself     |
| Input at the next tool boundary         | PostToolBatch                                  | PostToolUse               | `turn/steer`                          | `turn_end`                                | Streaming input                      |
| Leaf's tools without a process per call | No                                             | No                        | Dynamic tools                         | `registerTool`, in Node                   | In-process MCP server, in Python     |

The desktop Codex app's own App Server exposes no endpoint Leaf can use
([harness-codex.md](../skills/leaf/references/harness-codex.md#delivery)), so Leaf
reaches it as it reaches Claude Code. The surfaces most users run, Claude Code and
the Codex app, expose none of these controls to a companion; reaching them means
Leaf driving the agent itself.

Leaf's process overhead doesn't need an owned loop. Each hook and command starts
`bin/leaf` afresh, 120–620 ms each under load; a hook that asked the running page
server instead might cut most of that on every harness, though nobody has measured
it.

## A forked Claude Code side lane

A side lane is a short separate run that shares the session's context and answers
a question while the main turn keeps running its tool. On Claude Code 2.1.310 with
Opus 5.5 and a 9k-token context, a `claude -p` parent read a file, then ran
`sleep 45` in the foreground; three seconds into the sleep a second process forked
the parent's session and asked about the file:

```bash
echo "<question>" | claude -p --resume <parent-session-id> --fork-session \
  --output-format stream-json --verbose --include-partial-messages
```

One run per setting:

| Fork                | First word after spawn | Model time | Cache read / written | Answer                               |
| ------------------- | ---------------------: | ---------: | -------------------: | ------------------------------------ |
| `--effort low`      |                 2.24 s |     1.46 s |            0 / 9,073 | Correct                              |
| The parent's effort |                 3.41 s |     2.95 s |        5,258 / 3,826 | Correct; noted the sleep was cut off |

Both parents finished normally. A fork at another effort read none of the cached
context, and one at the parent's effort read 58% of it, so on a long session the
cost of a side answer is unknown until runs on a real session price it. The fork
reads the running tool call as cut off, and one fork offered to rerun it. The
parent needs `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` to keep a long command in the
foreground, and prompts go on stdin because `--tools` swallows a trailing
argument.

## Subscriptions

As of 25 October 2026; Anthropic revised these terms several times in 2026.

| Route                                                 | Draws on                                              | Source                                                                                                                                                                                                                                                                                                         |
| ----------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Agent SDK or `claude -p` on the user's `claude login` | Plan limits                                           | [Plan article](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan), 7 October: "You can still use the Claude Agent SDK, `claude -p`, and third-party apps with your subscription limits."                                                                          |
| Pi through `pi-claude-bridge`                         | Plan limits                                           | The [community extension](https://github.com/elidickinson/pi-claude-bridge) runs Claude Code through the Agent SDK                                                                                                                                                                                             |
| Pi's own Claude login                                 | Extra usage, per Pi users' reports                    | Presents Claude Code's OAuth client id (`pi-ai`'s `anthropic.js`); [pi#3808](https://github.com/earendil-works/pi/issues/3808), [pi#9838](https://github.com/earendil-works/pi/issues/9838); [login help](https://support.claude.com/en/articles/13189465-log-in-to-your-claude-account) reserves that billing |
| Codex App Server, or Pi, with a ChatGPT login         | Plan limits, permitted for local and open-source apps | [OpenAI](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)                                                                                                                                                                                                                        |

Whether a tool others install may use the Agent SDK on the user's login is
ambiguous. The [legal page](https://code.claude.com/docs/en/legal-and-compliance)
allows "an end user … signing in to the unmodified Claude Code binary with their
own Claude subscription" and says plan limits "assume ordinary, individual usage";
the [SDK overview](https://code.claude.com/docs/en/agent-sdk/overview) says third
parties may not "offer claude.ai login … including agents built on the Claude
Agent SDK". `inference.py` already runs the user's own `claude -p` and never holds
a token, which is the shape the legal page allows.

## Options

- **Keep Leaf a companion and use what each harness exposes.** Effort per delivery
  and interrupt on an explicit stop on a terminal Codex and Pi; Claude Code and
  Codex app users see no change, and a question asked during a long tool still
  waits for its boundary.
- **Add a Leaf-run side lane that answers while the session works.** Questions get
  answered in seconds during long tools, and the user's session still does every
  edit. Costs: a second voice in the thread that can answer from a stale
  transcript, an answer the main session must be told about, cache misses, and
  extra usage against limits that assume ordinary use.
- **Host the whole session in Leaf.** Leaf owns every turn and every control above,
  and with them the transcript, approvals, interruption, reconnects, permission
  modes, compaction and the chat surface, as `leaf.page` already does for Codex
  (`EmbeddedHarness`). It ends wake-up gaps only for sessions Leaf hosts, and turns
  Leaf from a page beside the user's agent into the place they work.

The October 2026 recommendation was to keep Leaf a companion, since the measured
busy wait is a few questions a day. Revisit the side lane when busy waits grow,
for example if agents stop delegating long work, and hosting when a user wants
Leaf to be where they work.
