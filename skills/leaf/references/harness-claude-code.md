# Claude Code handoff and wait loop

## Launcher

The skill directory's `../../bin/leaf` launcher resolves to
`${CLAUDE_SKILL_DIR}/../../bin/leaf`. Claude Code also puts it on `PATH`, so run
it as `leaf`: Claude Code's settings match a command by its text, and the ones
that run Leaf outside its sandbox name `leaf`.

## Serve the page

```bash
leaf server start <page>
```

It prints a JSON object whose `url` is the page's keyed URL, and returns. Follow
`references/conversation-loop.md`, "Status and handoff". `leaf server run`
prints the same but never exits, so nothing it says reaches you and there is no
turn to end. `references/serving-pages.md` owns the key, the address it binds,
and a URL the user cannot reach.

## Wait loop

New user input reaches you only between your own operations, at the next tool
result.

Once the page is handed over, end the turn, and do not run `leaf wait`: Leaf's
Stop hook watches for you. When a turn ends, Claude Code runs the hook in the
background, and it watches every page this session holds. When one of them gets new
input, the hook wakes the session. It opens a new turn, or, if a turn is running,
adds the input at that turn's next tool result. If the user turned on Leaf's hooks
module, the module does this watching instead, and its wake arrives as a message
from the leaf plugin.

Leaf's prompt hook puts the whole delivery in your context
(`references/event-batches.md`, "One envelope on every transport"), and so does the
Stop hook for input that arrives as a turn ends. The hook also confirms receipt, so
the user's updates read **Picked up** and the delivery's `acknowledge` is null; run
no acknowledgement command. A delivery the hook could not confirm, or one too large
for the context, arrives as a pointer instead: `leaf delivery read <id>`. Read every
part before working or replying, then follow the confirmation instruction on the
last part.

To pick up a page this session did not serve, run `leaf page claim <page>`; the
Stop hook watches it from the end of the turn.

If a turn ends without answering a delivered update, the next prompt hook puts that
update back in your context and marks it **Picked up** again for the new turn.

When nothing was watching, as after a turn you interrupted without the hooks module,
or once a background job has been idle for an hour, new input reaches you as a
message from Leaf naming the page. It comes through Claude Code's session
messaging, so it appears to come from another session. The input arrives with it,
and the watch starts again when that turn ends.

## Session list

Claude Code's session list (`claude agents`) shows a background session as
Working while a background task runs. Leaf's watch is a hook rather than a task,
so a session waiting on its page reads as idle there. The list groups the session
by the closing line of its last chat message: a `needs input:` line files it
under Needs input and a `result:` line under Completed. A reply with neither is
left to Claude Code's classifier, which reads a closing like "the page will pick
up new comments" as work in progress. So when the user's On me list holds
anything, end the closing reply with a line `needs input: <what you want back>`
naming those items; only when nothing waits on the user or on work still running,
end it with `result: <what you delivered>`.
Keep either line to 200 characters or fewer, on its own line, not in a code block.

## Subagents

A subagent runs with this session's id and process, so Leaf takes it for this
session. A page the subagent claims, by serving it or running `leaf page claim`,
belongs to this session, and this session's Stop hook holds your turns open for
every update there. A `leaf wait` the subagent runs uses this session's one
watcher. Leaf refuses it while the Stop hook's watch runs; otherwise the input from
every page you hold goes to the subagent instead of you. So keep the page with you
(`references/conversation-loop.md`, "Long-running work"). A separate Claude Code
session has its own id and can drive a page of its own.
