# Claude Code handoff and wait loop

## Launcher

The skill directory's `../../bin/leaf` launcher resolves to
`${CLAUDE_SKILL_DIR}/../../bin/leaf`. Claude Code also puts it on `PATH`.

## Serve the page

```bash
leaf server start <page>
```

It prints the page's keyed URL on stdout and returns. Hand that exact string
back. `leaf server run` prints the same URL but never exits, so nothing it says
reaches you and there is no turn to end. `references/serving-pages.md` owns the
key, the address it binds, and a URL the user cannot reach.

## Wait loop

New user input reaches you only between your own operations, at the next tool
result.

One unnamed `leaf wait` watches every page the host session owns. It prints one
complete envelope inline (`references/event-batches.md`, "One envelope on every
transport"). Name a page only to pick up a page this session did not serve;
`leaf wait <page>` claims it.

Start `leaf wait` as a background task and end the turn. Its completion becomes
host input. Once the complete envelope is in context, acknowledge it by starting
`leaf wait --ack <delivery-id>` as the next background task; it acknowledges that
delivery and waits for another. `references/conversation-loop.md`, "When to write",
orders the acknowledgement, the replies, and the work. The event reference owns the
complete-batch and acknowledgement rules.

If a turn ends without answering an acknowledged move, the next prompt hook
carries that obligation back into context and renews its **Picked up** receipt
for the new turn without a status write. The banner reports overall page activity
separately.

How `leaf wait` ends, and what each ending asks of the loop, is in
`references/event-batches.md` under "Delivery and acknowledgement". The signal that
reference leaves to the host is a message from Leaf saying a page has new input and
no `leaf wait` is running for this session: start a replacement unnamed wait. It
comes through Claude Code's session messaging, so it is presented as coming from
another session.

## Session list

Claude Code's session list (`claude agents`) shows a background session as
Working for as long as a background task runs, `leaf wait` included; Claude Code
checks for a running task before anything else, and no reply text changes that
word. It groups the session separately, by the closing line of its last chat
message, and that grouping ignores background tasks: a `needs input:` line files
the session under Needs input and a `result:` line under Completed. A reply with
neither is left to Claude Code's classifier, which reads a closing like "the
watcher will pick up new comments" as work in progress, so a session waiting on
its page stays under Working. Each time a `leaf wait` starts, Leaf's
`PostToolUse` hook adds guidance on that ending to the command's result
(`hooks/wait-started.json`), so it sits beside the reply that closes the turn.

## Subagents

A subagent runs with this session's id and process, and nothing in its
environment tells Leaf otherwise, so to Leaf it is this session. A page it
claims, by serving it or naming it to `leaf wait`, is this session's, and this
session's Stop hook holds its turns open for every user move there. A
`leaf wait` it starts competes for this session's one watcher: it is refused
while yours runs, and otherwise takes the batches from every page you hold into
the subagent's context instead of yours. That is why the page stays with you
(`references/conversation-loop.md`, "Long-running work"). A separate Claude Code
session has its own id and can drive a page of its own.
