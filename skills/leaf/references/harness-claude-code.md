# Claude Code handoff and wait loop

## Launcher

The skill directory's `../../bin/leaf` launcher resolves to
`${CLAUDE_SKILL_DIR}/../../bin/leaf`. Claude Code also puts it on `PATH`.

## Serve the page

```bash
leaf server start <page>
```

It prints `{"url": ...}`, the page's keyed URL, on stdout and returns. Hand that
exact URL back. `leaf server run` prints the same but never exits, so nothing it says
reaches you and there is no turn to end. `references/serving-pages.md` owns the
key, the address it binds, and a URL the user cannot reach.

## Wait loop

New user input reaches you only between your own operations, at the next tool
result.

Leaf's own Stop hook watches for you. As each turn ends, Claude Code starts it in
the background, and it watches every page this session holds until one has new
input; then it wakes the session, opening a turn, or reaching the current one at
its next tool result. So once the page is handed over, end the turn: start no
`leaf wait`. As the turn the input reaches takes it, Leaf's prompt hook puts the
whole delivery in your context (`references/event-batches.md`, "One envelope on
every transport"). Once the complete envelope is in context, take its
`acknowledge` route (`leaf delivery ack <id>`) before working or replying, so the
user's moves read **Picked up**. Large input arrives as a `leaf delivery read <id>`
pointer; read the whole envelope before acknowledging it. Hook completion cannot
prove receipt: a harness timeout discards its output. Input that arrives as a turn ends
comes through the Stop hook the same way.

To pick up a page this session did not serve, run `leaf page claim <page>`; the
Stop hook watches it from the end of the turn.

If a turn ends without answering a delivered move, the next prompt hook carries
that obligation back into context and renews its **Picked up** receipt for the new
turn without a status write. The banner reports overall page activity separately.

When nothing was watching, as after a turn you interrupted or once a background
job has been idle for an hour, new input reaches you as a message from Leaf naming
the page. It comes through Claude Code's session
messaging, so it is presented as coming from another session; the input arrives
with it, and the watch starts again when that turn ends.

## Session list

Claude Code's session list (`claude agents`) shows a background session as
Working while a background task runs. Leaf's watch is a hook rather than a task,
so a session waiting on its page reads as idle there. The list groups the session
by the closing line of its last chat message: a `needs input:` line files it
under Needs input and a `result:` line under Completed. A reply with neither is
left to Claude Code's classifier, which reads a closing like "the page will pick
up new comments" as work in progress. So when a turn leaves anything only the user
can give (an answer on the page, or a decision about other work), end the closing
reply with a line `needs input: <what you want back>`; only when nothing waits on
the user or on work still running, end it with `result: <what you delivered>`.
Keep either line to 200 characters or fewer, on its own line, not in a code block.

## Subagents

A subagent runs with this session's id and process, and nothing in its
environment tells Leaf otherwise, so to Leaf it is this session. A page it
claims, by serving it or naming it to `leaf wait`, is this session's, and this
session's Stop hook holds its turns open for every user move there. A
`leaf wait` it starts competes for this session's one watcher: it is refused
while the watch runs, and otherwise wakes the subagent instead of you, so the
input from every page you hold goes into the subagent's turn. That is why the page stays with you
(`references/conversation-loop.md`, "Long-running work"). A separate Claude Code
session has its own id and can drive a page of its own.
