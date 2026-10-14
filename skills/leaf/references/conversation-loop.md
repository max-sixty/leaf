# Conversation loop

Keep the user informed on the page, and answer delivered updates there using
each event's `handling` instructions. A chat response alone does not revise the
page's content.

## What the user sees

The user follows your work on the page:

| Surface | What it shows | Written by |
| --- | --- | --- |
| Banner | one sentence for the whole page: the line of the item you have in hand, or what you want back | `leaf task start`, `leaf status <page> waiting "<detail>"` |
| Beside a thread or widget | **Working** and your line: the thread's working message above its reply box, or on the control the work answers | `leaf response reply --ephemeral`, `leaf task start <page> <id> "<line>"` |
| Thread | your answer to the user's message, with the progress before it folded behind it | the response operation named by delivered `handling` |
| Page | the revised content in place, and a stamp's changelog | saving `index.html`, `leaf page stamp` |

Leaf itself marks each update **Sent**, **Queued**, and **Picked up**, including
one that owes you nothing, such as a moved card. Your harness contract may add its
own current step to the banner.

Readings in `leaf page state <page>` describe the user's side between their
updates. `viewed` says whether they are there: the last time a browser tab had the page
visible, in epoch seconds, renewed about every half minute while it stays visible, and
`null` when nobody has opened the page. Each thread's `unread` says which of your
messages they have not read yet
([threads](threads.md#what-the-user-has-read)). A status
has no such reading, so one they have not reacted to may not have been seen.

## The user's view

`user_views` in `leaf page state <page>` reports each page load in a browser over the
last day: its layout and visual viewport, the window area Leaf's chrome leaves, color
scheme, pointer type, reduced-motion preference, scroll position, and which reading
regions are on screen. Use it to judge whether a revision fits the window the user
actually has. Each load is its own entry, so two visible tabs can show different
widths or revisions, and a tab that reloads adds an entry. `visible` says whether
the load showed the page at its last report, `freshness` turns `stale` after 45
seconds without a report, and `matches_active_revision` says whether it shows your
latest revision. An empty list means no browser has reported. A region on screen
does not show that the user read it.

Each entry's `checks` holds layout findings measured in that browser, including
content below the screen: sideways overflow, scrolling workspace regions, and
drawing labels below the size threshold. Their own `freshness` says whether they
were measured in the last 45 seconds, and `matches_view` says whether they were
measured in the view the entry now reports. They are context
for your judgment rather than a required layout, and they do not replace
`leaf page check --render`.

## When to write

Everything you work on for the user is an item on your queue: an update you owe
an answer, named by the update's event id as its delivery gives it, or a to-do you
opened. Take the item in hand before starting its work, with one line saying what
you are doing.

When a thread message asks for work, make your intended work visible there
before reading or editing. Follow the event's `handling`: a turn-written reply
starts with your first message, as the selected harness's "Replies" describes.
For a command-written reply, your first command after delivery is:

```bash
leaf response reply <answer.ref> --ephemeral --text "<what you will do, in a line>"
```

The user reads it at once, and it takes the update in hand: the update reads
**Working** with that line as its thread's working message and in the banner, and
it folds into the progress disclosure when your answer arrives
([progress messages](threads.md#progress-messages)). Take any other item in hand,
such as a to-do or an action on a page widget, which has no thread, with a start:

```bash
leaf task start <page> <id> "reading the reconnect traces" && <command>
```

Take the item in hand again whenever the user would describe what you are doing
differently: a new phase such as reading, editing, testing, or waiting on a result.
Another progress message replaces the thread's working message and keeps the step
behind it; a start changes the line without one, and folding it into the command
that begins the step costs no extra tool call. Name the operation and its subject in one sentence; "Working on it"
tells the user nothing the banner's dot does not already say.

Work requested in chat or begun by you gets an item too. After initializing a
new page, open and start its to-do before authoring. On an existing page, open it
on the widget it concerns, or on `page`:

```bash
leaf task open <page> page "Add a glossary"
leaf task start <page> <todo> "drafting the glossary entries"
```

`leaf task open` prints the to-do's record; its `id` is the to-do. When its work is
done, end it with `leaf task end <page> <todo> done "<where the result is>"`; a to-do
nothing ends stays on you, and `leaf status … idle` refuses while one is open.
Housekeeping such as re-vendoring, restarting the server, or merging owes the user
nothing and needs no item.

User input comes before the work in hand, in this order:

1. Where the delivery's `acknowledge` names a receipt command, take it first, so the
   user's updates read **Picked up**; where it is `null`, your harness has confirmed
   receipt already. Until you start an item, the banner can say only that you are
   working on their update.
2. Say what you will do in the thread of each update that asks for work, or start
   it, as above, before starting the work. Each delivered event's `handling`
   clauses say how, with the reply carrying the result once it lands. An update that
   asks for no work, such as a question, is answered by its reply at once.
3. If the update interrupted other work, start that work's item again once the update's
   own work is done, so the banner describes the work that continues rather than
   the last step before the interruption.

Then do the work, and reply once its revision passes `leaf page check`, the only
check the main skill's "Check the page" step asks before a reply.

## Status and handoff

Before a handoff, reconcile the user's On me list and your own as described below,
then run:

```bash
leaf status <page> waiting "<what you want back>"
```

The detail names the concrete answer or decision, not the fact that you are
waiting. For an informational page with no ask, leave it empty; the
banner then invites the user to select text to comment. Name the gesture available
to the user and hand over by the selected harness contract. From the first handoff
on, include
the exact page URL in every turn's final response; intermediate progress messages
do not repeat it. An export hands over its file URL, and a harness that already
presents the page uses its own handoff surface.

A `waiting` ends every start you made before it, so the banner shows what you want
back; a to-do stays open on you until you end it.

What ends a start depends on its item. Your reply answering an update ends that
update's start, and so does a stamped version whose markup records a press on an
answered ask. A to-do's start ends with the to-do: `leaf task end`, or a stamped
version that completes its widget, once per completed widget:

```bash
leaf page stamp <page> --text "…" --completes <widget-id>
```

`--completes` names a widget with an open to-do, and ends each to-do on it `done`,
citing the version. `leaf task open` takes a page widget that declares `x-work` or
holds an unsettled action, any other element of the page, or `page`; work in a thread
is opened by the reply that promises it (`--todo`). A to-do on a widget survives
unrelated versions and removal of its widget.

## Long-running work

New user input reaches you only between your own operations; your harness contract
names exactly when. A long foreground operation, such as a test suite or a subagent
you wait on, leaves the user's comment unanswered for its whole length.

For work that will run longer than a few minutes, coordinate it rather than perform
it. Hand the reading, editing, and testing to background subagents or background
commands, and end your turn as the harness contract says, so the watcher's next delivery
reaches you while the work runs instead of waiting behind it. When a worker reports
back, put its result on the page, moving what it finished out of the open work
(`authoring-revisions.md`, "Keep the current page current"); the thread that asked
for it then gets a reply saying what changed and linking to it.

You drive the page and your workers do not. The server, the watcher and its
acknowledgements, replies, starts and status, edits to `index.html`, and stamps stay
with you, and a worker returns its result to you. A worker touches the page only in a
role Leaf's instructions give it, and only as those instructions direct: a command hub worker
(the `worker` value returned by `leaf page instructions <page>`), or a Codex watcher task
(`references/codex-watcher.md`). Put this in each worker's brief, because a worker that
inherits your conversation inherits the page with it and may otherwise treat the page
as its own. Work that needs its own conversation with the user belongs to a session
of its own, with its own page.

A `leaf task start` line lasts for the turn that wrote it. A couple of minutes after
that turn ends, interrupted or not, the banner says your turn ended and keeps the line
in its explanation, unless you start the item again; a line nothing renews expires
after about a quarter of an hour. While a worker produces an update's answer, start
that update in your turn: the start lets the turn end before the answer. In the turn
that the worker's result or the user's next comment wakes, start the item again or
answer it. To hold work past the turn, open a to-do (below).
Within a turn, the banner shows the line of the item you started last, so start the
item that best describes what is running; each item you have in hand shows its own
line beside its thread or widget.

A start lasts a turn; a to-do lasts until you end it. When you take on work a thread
asked for that can outlast the turn you took it on in, such as a worker's build, a
wait on CI, or a change you promise for the next version, answer with
`leaf response reply <answer.ref> --todo "<what you owe>"`, saying what is under way:
the reply answers the user's message and opens the to-do on that thread under the
reply's id, which keeps the thread on you, and named in the banner, through the user
resolving it and the end of your session. A turn-written reply carries no to-do, so
answer such a promise with this command. Handing the work to another session, a
background job, or a later turn is such a promise, even where the tool you hand it with
counts the launch as the end of your part: the thread that asked still waits for the
result, and a reply declared `--done` tells the user nothing is owed. Wherever
the result lands, the to-do ends there: `leaf task end <page> <todo> done "<where the
result is>"`, or `failed` or `dropped` with the reason, so work that won't come back
to you takes the page and the to-do's id in its brief. Start it in the session
continuing the work: the start transfers completion authority to that session
and gives the banner and thread its line. That session can finish on a later
turn; another session takes over by starting the same to-do.
Work on an update that finishes inside the turn needs no to-do.

## The On lists

Everything waiting on the user belongs in their **On me** list: each decision your
work leaves to them, and each answer, permission, review, or action elsewhere you
need from them. A decision is theirs whether or not your next step depends on it:
each proposal or candidate you present for their judgment, including the ones you
rank after the one you recommend, and each product choice you surface. Ask a direct
question and register it by one of the routes below, grouped as `authoring-asks.md`
says, and keep it there until the user decides it or you withdraw it. Prose, a
heading or a column on the page, a status line, and a question or open item in chat
repeat an On me item; on their own they register nothing. Information the user may
comment on but need not decide creates no item.

The banner's On me count and the On panel show everything waiting on the
user: these requests, and any update whose send failed and needs sending again.
Your list, which the user sees as **On <your name>**, shows what waits on you. Under
each list, its Done holds what left it: the asks the user answered or you withdrew
and the to-dos they ended under On me, and the replies you sent and the to-dos you
ended under yours. The user presses `m` to step through On me in page order. Each press lands where the next item is
answered, such as an ask's answering widget or the thread holding a prose ask, and
an ask's displayed `1`–`9` actions answer it there.

| Request | Register it | What answers it |
| --- | --- | --- |
| A decision or input recorded by a widget | Author a decision widget (`authoring-asks.md`); optional `lf-ask` frames its question and evidence | The widget's declared answer; a multiple-choice ask also needs the user's Done |
| A conversational answer | Open an agent thread with the question, or add `--ask` to a reply (`threads.md`) | The user's next reply there or a settling reaction |
| Required version sign-off | Declare sign-off and stamp the version (`authoring-asks.md`, "Sign-off") | That version's banner approval |
| An action neither route records, such as trying a build or connecting a browser | `leaf task open <page> <id> "<direct question naming the action>" --on user`, on its widget, section, or `page` | The user's Done; end it yourself when their action is established or no longer needed |

A widget ask has id `widget:<widget-id>`, a prose ask has `reply:<message-id>`,
and an approval ask for a stamped version's sign-off has `approval:v<version>`.
A to-do on the user keeps the id printed by `task open`. A thread takes no to-do
on the user; ask there with `--ask`. A thread
can retain several prose asks; its latest unanswered one is the current request,
and the next user reply settles preceding unanswered prose asks there. Publish
a dependent question once its prerequisite is answered. The user's Done on a to-do
reports completion; it supplies no permission or choice that its question did not state.

Read the lists before a handoff, before waiting for the user, and after taking in
an answer:

```bash
leaf page state <page> | jq '{source, asks, todos, queues}'
```

Page state contains separate canonical `asks` and `todos`; its
`queues.on_user` and `queues.on_agent` select those records with response obligations
and delivery retries for the panel. `jq` only selects these fields; do not reconstruct
membership from events or widget state. Each queue item names its `id`, `kind`,
`subject`, and `thread`. An ask contains its prompt, typed answer and lifecycle;
widget state owns its answer. Read a thread with `leaf page state <page> <message-id>`
for its messages. For a page widget, read
`leaf page state <page>`'s `active.file` and the identified widget in that HTML;
the widget-specific state command reports its state and metadata. The reading
covers the active document and admitted log, not unsent browser drafts or a tab
pinned to an older version. Check `source` for an invalid or missing draft before
treating an empty list as a successful handoff.

Reconcile the lists with what you still need and owe. An empty On me says
that you need nothing from the user **now**; your list may still hold your work or a wait
on an external result. Complete authorized work without asking for permission
again. A paused project needs an ask only when its disposition or resumption
needs the user's decision; after they choose to keep it paused, that decision is
settled. A blocked action belongs on the user only when they can take the step
that unblocks it. A question about work another session owns stays with that session;
ask here only for the decision this page needs.

An answer in chat or another surface still settles the real question. Incorporate
it and retire its page ask in a revision (`authoring-revisions.md`), or end
the user's to-do with `leaf task end`. Retire a prose ask the user answered there
with `leaf task end <page> reply:<message-id> done "<where the answer is>"`, which
records it answered elsewhere, and one that no longer applies with `dropped
"<why>"`, which records it withdrawn; neither invents the user's answer. Keep
finished requests off the user's On me list; answered and withdrawn ask records
remain available in the complete reading.
