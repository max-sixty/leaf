# Claude Code handoff and wait loop

## Launcher

The launcher is `${CLAUDE_SKILL_DIR}/../../bin/leaf`, and Claude Code puts it on
`PATH`.

## Serve the page

```bash
leaf server start <page>
```

It prints a JSON object whose `url` is the page's keyed URL, and returns. Then follow
`references/conversation-loop.md`, "Page availability and handoff". `leaf server run` never
exits, so you would see nothing it prints and could not end the turn.
`references/serving-pages.md` covers the key, the address the server binds, and a
URL the user cannot reach.

## Wait loop

Once the page is handed over, end the turn; do not run `leaf wait`. When a turn ends,
Claude Code runs Leaf's Stop hook in the background to watch every page this session
holds. New input wakes the session: it opens a turn, or joins a running one at its
next tool result.

Leaf's hooks put the whole delivery in your context. Leaf confirms receipt itself
once your turn goes on past the delivery, so `acknowledge` is null and you run no
acknowledgement command. A delivery the hook could not confirm, or one too large
for Claude Code to show whole, arrives as a pointer instead (`event-batches.md`,
"Handle the input"). An update a turn left unanswered comes back once, in a turn
of its own, and again with the next prompt the user types.

To pick up a page this session did not serve, run `leaf page claim <page>`; Leaf
watches it from the end of the turn.

When nothing was watching, as can happen after the user interrupts a turn, new input arrives with a message from Leaf
naming the page. It comes through Claude
Code's session messaging, so it looks as if it came from another session.

## Turn-end check

As each turn ends, an experimental check of Leaf's reads the conversation for
decisions, answers or steps you left to the user that On Me doesn't hold. It asks each
as your message, usually as a choice where its answers can be listed and otherwise
with `--obligation`, in a new thread on the passage it concerns or the page, or, for a
question asked before, in that question's thread under its id, which reopens the
thread if the user closed it. It tells you at your next step what it wrote. Where a
few of a page's words have gone stale, it swaps in new ones and tells you the old and
new words; change them back or rewrite them if they're wrong, and carry the change
into any file you build the page from. It also tells you what else it found, such as a
page holding what no longer fits the work, an On Me item the user settled elsewhere,
or work you set running that no page shows, for you to act on where it still holds;
`turn-end-check.md` is what it asks. That catches what slips; it doesn't ask for you,
so keep asking by the routes in `conversation-loop.md`, "The On lists". What it writes
is yours like anything you write: the user's reply reaches you as any reply does, and
you resolve the thread of one that isn't theirs, as that section says for a question
that no longer applies.

## Session list

Claude Code's session list (`claude agents`) files a session by the last line of its
last chat message: a `needs input:` line under Needs input, a `result:` line under
Completed. Without either, its classifier reads a closing like "the page will pick up
new comments" as work in progress. So when the user's On Me list holds anything, end
the closing reply with a line `needs input: <what you want back>` naming those items.
Only when nothing waits on the user or on running work, end it with
`result: <what you delivered>`. Keep the line to 200 characters or fewer, on its own
line, outside a code block.

## Subagents

A subagent runs with this session's id and leaves your input for you. A page it
claims belongs to this session. A `leaf wait` it runs is refused while Leaf watches,
and otherwise takes input from every page you hold away from you, so keep `leaf wait`
with you. A separate Claude Code session has its own id and can drive a page of its
own.

Each thread message comes to you, and you decide who does its work, so that the user
hears back soon while your own work goes on. Give a message whose work can run beside
yours to a fork of yourself in the background (the Agent tool's `fork` type): work
that changes nothing you are working on, such as your files and branch, the page's
source or your pull requests, settles no question you are weighing, and waits on
nothing you have under way, such as a command you are running or a change you have
started. Reading, a lookup, or research that writes only its own scratch files is
such work, and the fork's answer in the thread carries what it found. Answer a
message yourself where its work is a step or two, or you have nothing else under way.
Unlike a worker that reports to you, the fork answers the message itself, with its
`answer.ref`. A later message in that thread can go to the same fork with
SendMessage, or to a new fork, each with its `answer.ref`. Start each message you
give a fork, as `conversation-loop.md`, "Long-running work", says for any worker's
update: `leaf task start <page> <message> --text "<what the fork is doing>"`. The
working line Leaf posts in the thread doesn't start it.
