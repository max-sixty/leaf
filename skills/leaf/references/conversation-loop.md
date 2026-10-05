# Conversation handoff

## What the user sees

The user follows your work on the page:

| Surface | What it shows | Written by |
| --- | --- | --- |
| Banner | one sentence for the whole page: the line of the item you have in hand, or what you want back | `leaf task start`, `leaf status <page> waiting "<detail>"` |
| Beside a thread or widget | **Working** and your line, above the message or on the control the work answers | `leaf task start <page> <id> "<line>"` |
| Thread | your answer to the user's message | `leaf thread reply` |
| Page | the revised content in place, and a stamp's changelog | saving `index.html`, `leaf page stamp` |

Leaf itself marks each user move **Sent**, **Queued**, and **Picked up**, including
a move that owes you nothing, such as a moved card. A pick before the Done its Ask
waits for is marked with that Done. Your harness
contract may add its own current step to the banner. Chat stays in the harness and never
reaches the page.

Readings in `leaf page state <page>` describe the user's side between their
moves. `viewed` says whether they are there: the last time a browser tab had the page
visible, in epoch seconds, renewed about every half minute while it stays visible, and
`null` when nobody has opened the page. Each thread's `unread` says which of your
messages they have not read yet
([threads](threads.md#what-the-user-has-read)). A status
has no such reading, so one they have not reacted to may not have been seen.

## The user's view

`user_views` in `leaf page state <page>` supplies context from the actual browser
rather than a headless preview. Each document reports its layout viewport, visual
viewport (pinch zoom and the software keyboard included), the window area left by
Leaf's chrome, color scheme, pointer type, reduced-motion preference, scroll position,
and visible reading-region ids. A visible region is a measured place on screen,
not evidence that the user read it.

Sessions remain separate: two visible tabs may show different widths or revisions.
`visible` records the last visibility report; `freshness` becomes `stale` after
45 seconds without a report. `matches_active_revision` says whether this document
shows the current authored revision. Recent hidden and stale readings remain
available for a day. An empty list means there is no observation, not that the page
has no reader.

Each session's `checks` has its own revision, log position, viewport, visual viewport,
window area, scheme, and `checked_at`. Its `freshness` and `matches_view` distinguish
current checks from a recent context carrying an older sample. Checks measure the
rendered arrangement, including content below the screen: sideways overflow,
scrolling workspace regions, and drawing labels below the attached size threshold.
Arrangement rows and margin residents are context alongside those findings. These
are observations and heuristics, not a required layout or a complete render gate;
the author decides whether a finding warrants a revision. They do not establish
that the user saw a finding.

Observation starts after presentation, renews about every ten seconds while visible,
and follows viewport and preference changes. It creates no user move, agent turn,
or automatic edit. A public website page starts observing once the user's interaction
has activated its private page. The readings are also available through the
page's authenticated `GET /api/user-view`; captured render previews record none.

## When to write

Everything you work on for the user is an item on your queue: a user move you owe
an answer, named by the move's event id as its delivery gives it, or a task you
opened. Take the item in hand before starting its work, with one line saying what
you are doing:

```bash
leaf task start <page> <id> "reading the reconnect traces" && <command>
```

The move or task then reads **Working** with your line, beside its thread or
widget and in the banner. Start it again whenever the user would describe what you
are doing differently: a new phase such as reading, editing, testing, or waiting on
a result. Folding the start into the command that begins the step costs no extra
tool call. Name the operation and its subject in one sentence; "Working on it"
tells the user nothing the banner's dot does not already say.

Work no user move asked for, such as a request made in the terminal or a revision
you begin yourself, gets an item too: open a task for it on the page, or on the
widget it concerns, and start that task:

```bash
leaf task open <page> page "Add a glossary"
leaf task start <page> <task> "drafting the glossary entries"
```

`leaf task open` prints the task's record; its `id` is the task. When its work is
done, end it with `leaf task end <page> <task> done "<where the result is>"`; a task
nothing ends stays on you, and `leaf status … idle` refuses while one is open.
Housekeeping such as re-vendoring, restarting the server, or merging owes the user
nothing and needs no item.

User input comes before the work in hand, in this order:

1. Where the delivery's `acknowledge` names a receipt route, take it first, so the
   user's moves read **Picked up**; every other carrier has confirmed receipt
   already. Until you start an item, the banner can say only that you are working
   on their update.
2. Start each move that asks for work before starting the work. Each delivered
   event's `handling` clauses say how, with the reply carrying the result once it
   lands. A move that asks for no work, such as a question, is answered by its
   reply at once.
3. If the move interrupted other work, start that work's item again once the move's
   own work is done, so the banner describes the work that continues rather than
   the last step before the interruption.

Then do the work.

## Status and handoff

Before a handoff, run:

```bash
leaf status <page> waiting "<what you want back>"
```

The detail names the concrete answer or decision, not the fact that you are
waiting. For an informational page with no concrete ask, leave it empty; the
banner then invites the user to select text to comment. Finish the turn by the
handoff route in the main skill, "Operate". A `waiting` puts down every item you
started before it, so the banner shows what you want back; a task stays open on
you until you end it.

What ends a start depends on its item. Your reply answering a move ends that
move's start, and so does a stamped version whose markup records a press on an
answered Ask. A task's start ends with the task: `leaf task end`, or a stamped
version that completes its widget, once per completed widget:

```bash
leaf page stamp <page> --text "…" --completes <widget-id>
```

`--completes` names a widget with an open task, and ends each task on it `done`,
citing the version. `leaf task open` takes a thread, by any message in it or a
widget in one of its messages; a page widget that declares `x-work` or holds an
unsettled move; or `page`. A task on a widget survives unrelated versions, and a
version cannot drop that widget while the task stands.

## Long-running work

New user input reaches you only between your own operations; your harness contract
names exactly when. A long foreground operation, such as a test suite or a subagent
you wait on, leaves the user's comment unanswered for its whole length.

For work that will run longer than a few minutes, coordinate it rather than perform
it. Hand the reading, editing, and testing to background subagents or background
commands, and end your turn as the harness contract says, so the watcher's next delivery
reaches you while the work runs instead of waiting behind it. When a worker reports
back, put its result on the page; the thread that asked for it then gets a reply
saying what changed and linking to it.

You drive the page and your workers do not. The server, the watcher and its
acknowledgements, replies, starts and status, edits to `index.html`, and stamps stay
with you, and a worker returns its result to you. A worker touches the page only in a
role Leaf's instructions give it, and only as those instructions direct: a command hub worker
(`leaf page instructions <page> worker`), or a Codex watcher task
(`references/codex-watcher.md`). Put this in each worker's brief, because a worker that
inherits your conversation inherits the page with it and may otherwise treat the page
as its own. Work that needs its own conversation with the user belongs to a session
of its own, with its own page.

A start holds its item for the turn that wrote it. The page is told when that turn
ends, an interrupted one included, so a start nothing has renewed within a couple of
minutes of the ending stops being believed: the banner reports that your turn ended,
and its explanation keeps the start's line. A start nobody renews at all ages out
after about a quarter of an hour. A move whose answer a worker is producing takes a
start while your turn runs; a start written in this turn lets the turn end before the
answer. In the turn that a worker's result or the user's next comment wakes, start
the item again or answer it. What holds the work after the turn is a task (below).
Within a turn, the banner shows the line of the item you started last, so start the
item that best describes what is running; each item you have in hand shows its own
line beside its thread or widget.

A start lasts a turn; a task lasts until you end it. When you take on work a thread
asked for that can outlast the turn you took it on in, such as a worker's build, a
wait on CI, or a change you promise for the next version, open a task on that thread:
`leaf task open <page> <id> "<what you owe>"`. Then reply, saying what is under way:
the reply answers the user's message, and the task keeps the thread on you, and named
in the banner, through the user resolving it and the end of your session. When the
result lands, write its outcome with `leaf task end <page> <task> done "<where the
result is>"`, or `failed` or `dropped` with the reason, beside the reply that links
it. While you work on it, start it, so the banner and the thread show your line.
Work on a move that finishes inside the turn needs no task. `leaf page state` lists the
open `tasks` with their `owner`: yours, and the user's, which include each open Ask
and each question a thread leaves them. Its `queues` say what is on the user
(`on_you`) and on you (`on_agent`).
