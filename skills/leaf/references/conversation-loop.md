# Conversation handoff

Keep the user informed on the page, and answer delivered updates there using
each event's `handling` instructions. A chat response alone does not revise the
page's content.

## What the user sees

The user follows your work on the page:

| Surface | What it shows | Written by |
| --- | --- | --- |
| Banner | one sentence for the whole page: the line of the item you have in hand, or what you want back | `leaf task start`, `leaf status <page> waiting "<detail>"` |
| Beside a thread or widget | **Working** and your line, above the message or on the control the work answers | `leaf response reply --ephemeral`, `leaf task start <page> <id> "<line>"` |
| Thread | what you will do, your progress, and your answer to the user's message | the response operation named by delivered `handling` |
| Page | the revised content in place, and a stamp's changelog | saving `index.html`, `leaf page stamp` |

Leaf itself marks each user move **Sent**, **Queued**, and **Picked up**, including
a move that owes you nothing, such as a moved card. A pick before the Done its Ask
waits for is marked with that Done. Your harness
contract may add its own current step to the banner.

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
you are doing.

When a thread message asks for work, make your intended work visible there
before reading or editing. Follow the event's `handling`: a turn-written reply
starts with your first message, as the selected harness's "Replies" describes.
For a command-written reply, your first command after delivery is:

```bash
leaf response reply <answer.ref> --ephemeral --text "<what you will do, in a line>"
```

The user reads it at once, and it takes the move in hand: the move reads
**Working** with that line beside its thread and in the banner, and the
update folds into the progress disclosure when your answer arrives
([progress updates](threads.md#progress-updates)). Take any other item in hand,
such as a task or a move on a page widget, which has no thread, with a start:

```bash
leaf task start <page> <id> "reading the reconnect traces" && <command>
```

Take the item in hand again whenever the user would describe what you are doing
differently: a new phase such as reading, editing, testing, or waiting on a result.
Another progress update in the thread says it to the user there; a start changes
only the line, and folding it into the command that begins the step costs no extra
tool call. Name the operation and its subject in one sentence; "Working on it"
tells the user nothing the banner's dot does not already say.

Work requested in chat or begun by you gets an item too. After initializing a
new page, open and start its task before authoring. On an existing page, open it
on the widget it concerns, or on `page`:

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

1. Where the delivery's `acknowledge` names a receipt command, take it first, so the
   user's moves read **Picked up**; where it is `null`, your harness has confirmed
   receipt already. Until you start an item, the banner can say only that you are
   working on their update.
2. Say what you will do in the thread of each move that asks for work, or start
   it, as above, before starting the work. Each delivered event's `handling`
   clauses say how, with the reply carrying the result once it lands. A move that
   asks for no work, such as a question, is answered by its reply at once.
3. If the move interrupted other work, start that work's item again once the move's
   own work is done, so the banner describes the work that continues rather than
   the last step before the interruption.

Then do the work, and reply once its revision passes `leaf page check`, the only
check the main skill's "Operate", step 3, asks before a reply.

## Status and handoff

Before a handoff, reconcile Questions and Tasks as described below, then run:

```bash
leaf status <page> waiting "<what you want back>"
```

The detail names the concrete answer or decision, not the fact that you are
waiting. For an informational page with no Question, leave it empty; the
banner then invites the user to select text to comment. Name the gesture available
to the user and hand over by the selected harness contract. From the first handoff
on, include
the exact page URL in every turn's final response; intermediate progress updates
do not repeat it. An export hands over its file URL, and a harness that already
presents the page uses its own handoff surface.

A `waiting` puts down every item you
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
(the `worker` value returned by `leaf page instructions <page>`), or a Codex watcher task
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
Work on a move that finishes inside the turn needs no task.

## Questions and Tasks

Everything you need from the user belongs in **Questions**, whether an answer,
decision, permission, review, or action elsewhere. Ask a direct question and register
it by one of the routes below. Prose in the page, a status line, and a question in
chat alone do not register it. A recommendation leaves its decision open. An
optional invitation to comment creates no obligation; if you need feedback before
continuing, make it a Question.

The banner's Questions count and the Questions panel show the user's queue;
**Tasks** shows yours. The user can open either list and press `q` to reach their
next item. Questions contains these requests and any failed send that needs the
user to send again. Done holds ended items.

| Request | Register it | What answers it |
| --- | --- | --- |
| A decision or input recorded by a widget | Author an Ask (`authoring-asks.md`); `lf-ask` frames its question and evidence around one answering widget | The widget's declared answer; a multiple-choice Ask also needs the user's Done |
| A conversational answer | Open an agent thread with the question, or add `--awaits` to a reply (`threads.md`) | The user's next reply there or a settling reaction |
| An action neither route records, such as trying a build, reviewing a version, or connecting a browser | `leaf task open <page> <id> "<direct question naming the action>" --on user`, on its widget, section, or `page` | The user's Done; end it yourself when their action is established or no longer needed |

The Ask's id, the question message's id, or the id printed by `task open` identifies
the request. A thread takes no explicit user task; ask there with `--awaits`.
Keep independently answerable decisions in separate Asks or threads: a thread has
one current prose question, and its next user reply settles that question. Publish
a dependent question once its prerequisite is answered. A user task's Done reports
completion; it supplies no permission or choice that its question did not state.

Read the lists before a handoff, before waiting for the user, and after taking in
an answer:

```bash
leaf page state <page> | jq '{source, questions: .queues.on_you, tasks: .queues.on_agent}'
```

The lists are already canonical in page state: `queues.on_you` is Questions and
`queues.on_agent` is Tasks. `jq` only selects those fields; do not reconstruct
queue membership from events or widget state. Each item names its `id`, `kind`,
`subject`, and `thread`; task items also say how they end (`ends`). Read a thread with
`leaf page state <page> <message-id>` for its messages. For a page Ask, read
`leaf page state <page>`'s `active.file` and the identified Ask in that HTML;
the widget-specific state command reports its state and metadata. The reading
covers the active document and admitted log, not unsent browser drafts or a tab
pinned to an older version. Check `source` for an invalid or missing draft before
treating an empty list as a successful handoff.

Reconcile the lists with what you still need and owe. Zero Questions says that
you need nothing from the user **now**; Tasks may still contain your work or a wait
on an external result. Complete authorized work without asking for permission
again. A paused project needs a Question only when its disposition or resumption
needs the user's decision; after they choose to keep it paused, that decision is
settled. A blocked action belongs on the user only when they can take the step
that unblocks it. Work owned by another session stays there; ask here only for the
decision this page needs.

An answer in chat or another surface still settles the real question. Incorporate
it and retire its page Ask in a revision (`authoring-revisions.md`), or end its
thread question or user task with `leaf task end`. Keep standing answers and
finished decisions out of Questions. A page declaring required banner sign-off
adds a Question for its stamped version automatically; its approval answers that
Question, and undo reopens it. Stamp a draft before requesting its sign-off.
