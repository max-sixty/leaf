# Claude Code handoff and wait loop

## Launcher

Run the launcher as `leaf`. It is `${CLAUDE_SKILL_DIR}/../../bin/leaf`, and Claude
Code puts it on `PATH`. Claude Code's settings match a command by its text, and the
ones that let Leaf run outside its sandbox name `leaf`.

## Serve the page

```bash
leaf server start <page>
```

It prints a JSON object whose `url` is the page's keyed URL, and returns. Then follow
`references/conversation-loop.md`, "Status and handoff". `leaf server run` never
exits, so you would see nothing it prints and could not end the turn.
`references/serving-pages.md` covers the key, the address the server binds, and a
URL the user cannot reach.

## Wait loop

Once the page is handed over, end the turn; do not run `leaf wait`. When a turn ends,
Claude Code runs Leaf's Stop hook in the background to watch every page this session
holds. New input wakes the session: it opens a turn, or joins a running one at its
next tool result. If the user turned on Leaf's hooks module, the module watches
instead, and its wake arrives as a message from the leaf plugin.

Leaf's prompt hook, or the Stop hook for input that arrives as a turn ends, puts the
whole delivery in your context. Either hook also confirms receipt, so `acknowledge`
is null and you run no acknowledgement command. A delivery the hook could not
confirm, or one too large for the context, arrives as a pointer instead: read every
part with `leaf delivery read <id>` before working, then follow the confirmation
instruction on the last part. An update a turn left unanswered comes back with the
next prompt.

To pick up a page this session did not serve, run `leaf page claim <page>`; the Stop
hook watches it from the end of the turn.

When nothing was watching, as after a turn you interrupted without the hooks module
or a background job idle for an hour, new input arrives with a message from Leaf
naming the page. It comes through Claude Code's session messaging, so it looks as if
it came from another session.

## Session list

Claude Code's session list (`claude agents`) files a session by the last line of its
last chat message: a `needs input:` line under Needs input, a `result:` line under
Completed. Without either, its classifier reads a closing like "the page will pick up
new comments" as work in progress. So when the user's On me list holds anything, end
the closing reply with a line `needs input: <what you want back>` naming those items.
Only when nothing waits on the user or on running work, end it with
`result: <what you delivered>`. Keep the line to 200 characters or fewer, on its own
line, outside a code block.

## Subagents

A subagent runs with this session's id, so Leaf takes it for this session. A page it
claims belongs to this session, and your Stop hook holds your turns open for its
updates. A `leaf wait` it runs is refused while your Stop hook watches, and otherwise
takes input from every page you hold away from you. So keep the page with you
(`references/conversation-loop.md`, "Long-running work"). A separate Claude Code
session has its own id and can drive a page of its own.
