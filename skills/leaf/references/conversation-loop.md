# Conversation loop

Keep the user informed on the page, and answer delivered updates there using
each event's `handling` instructions. A chat response alone does not revise the
page's content.

## What the user sees

The user follows your work on the page:

| Surface | What it shows | Written by |
| --- | --- | --- |
| Banner | one sentence for the whole page: the line of the item you started last, or what you want back | `leaf task start`, `leaf status <page> waiting "<detail>"` |
| Beside a thread or widget | **Working** and your line: the thread's working message above its reply box, or on the control the work answers | `leaf response reply --ephemeral`, `leaf task start <page> <id> "<line>"` |
| Thread | your answer to the user's message, with the progress before it folded behind it | the response operation named by delivered `handling` |
| Page | the revised content in place, and a stamp's changelog | saving `index.html`, `leaf page stamp` |

Leaf itself marks each update **Sent**, **Queued**, and **Picked up**, including
one that owes you nothing, such as a moved card. Your harness contract may add its
own current step to the banner.

`leaf page state <page>` also says whether the user is there. `viewed` is the last
time a browser tab had the page visible, in epoch seconds. It renews about every 30
seconds while the tab stays visible, and is `null` if nobody has opened the page.
Each thread's `unread` lists your messages the user has not read yet
([threads](threads.md#what-the-user-has-read)). Nothing records whether the user
saw a status, so one they have not reacted to may be unread.

## The user's view

`user_views` in `leaf page state <page>` reports each page load in a browser over the
last day: its layout and visual viewport, the area left after Leaf's chrome, color
scheme, pointer type, reduced-motion preference, scroll position, and which reading
regions are on screen. Use it to judge whether a revision fits the window the user
actually has. Each load is its own entry, so two visible tabs can show different
widths or revisions, and a tab that reloads adds an entry. `visible` says whether
the load showed the page at its last report, `freshness` turns `stale` after 45
seconds without a report, and `matches_active_revision` says whether it shows your
latest revision. An empty list means no browser has reported. A region on screen
does not show that the user read it.

Each entry's `checks` holds layout findings measured in that browser, including for
content below the screen: sideways overflow, scrolling workspace regions, and
drawing labels below the size threshold. Their own `freshness` says whether they
were measured in the last 45 seconds, and `matches_view` says whether they were
measured in the view the entry now reports. Weigh them as context; they do not
replace `leaf page check --render`.

## When to write

Each piece of work you do for the user is an item on your list. An item is either
an update you owe an answer, named by its event id in the delivery, or a to-do you
opened. Before doing an item's work, start it with one line saying what you are
doing.

When a thread message asks for work, start it in the thread before you read or edit
anything. Follow the event's `handling`. For a turn-written reply, your first
message starts it, as the selected harness's "Replies" describes. For a
command-written reply, your first command after the delivery is:

```bash
leaf response reply <answer.ref> --ephemeral --text "<what you will do, in a line>"
```

This progress message starts the update. The user sees it at once as the thread's
working message, and its text becomes the **Working** line in the banner. When your
answer arrives, the progress messages fold behind it
([progress messages](threads.md#progress-messages)). Start an item that has no
thread, such as a to-do or an action on a page widget, with `leaf task start`:

```bash
leaf task start <page> <id> "reading the reconnect traces" && <command>
```

Start the item again whenever the user would describe what you are doing
differently, such as when you move from reading to editing, testing, or waiting on
a result. In a thread, a new progress message replaces the working message and
keeps the earlier one behind it. `leaf task start` changes the line without posting
a message, and chaining it before the command that begins the step costs no extra
tool call. Name the operation and its subject in one sentence. "Working on it"
tells the user nothing the banner's dot does not already say.

Work requested in chat or begun by you gets an item too. After initializing a
new page, open and start its to-do before authoring. On an existing page, open it
on the widget it concerns, or on `page`:

```bash
leaf task open <page> page "Add a glossary"
leaf task start <page> <todo> "drafting the glossary entries"
```

`leaf task open` prints the to-do's record, and its `id` is the to-do's id. When
the work is done, end it with:

```bash
leaf task end <page> <todo> done "<where the result is>"
```

A to-do stays on your list until you end it, and `leaf status … idle` refuses
while one is open. Housekeeping such as re-vendoring, restarting the
server, or merging owes the user nothing and needs no item.

Handle user input before continuing your current work, in this order:

1. If the delivery's `acknowledge` names a receipt command, run it first, so the
   user's updates read **Picked up**. If it is `null`, your harness has already
   confirmed receipt. Until you start an item, the banner can say only that you are
   working on the user's updates.
2. Start each update that asks for work, in its thread or with `leaf task start`
   as above, before doing the work. The event's `handling` clauses say how. An
   update that asks for no work, such as a question, gets its reply right away.
3. If the update interrupted other work, start that work's item again once the
   update is done, so the banner describes the work that continues rather than the
   last step before the interruption.

Then do the work, and reply once its revision passes `leaf page check`, the only
check the main skill's "Check the page" step asks before a reply.

## Status and handoff

Before a handoff, reconcile the user's On me list and your own (see "The On lists"
below), then run:

```bash
leaf status <page> waiting "<what you want back>"
```

The detail names the answer or decision you want, not the fact that you are
waiting. For an informational page with no ask, leave it empty, and the banner
invites the user to select text to comment. Tell the user what they can do on the
page, and hand over as the selected harness contract says. From the first handoff
on, include the exact page URL in every turn's final response, but not in progress
messages. An export hands over its file URL, and a harness that already shows the
page uses its own handoff surface.

`waiting` ends every start you made before it, so the banner shows what you want
back. It leaves your to-dos open.

How a start ends depends on its item. An update's start ends with the answer: your
reply, or, for an answer owed in markup, the stamped version that records the
user's press. A to-do's start ends with the to-do: `leaf task end`, or a stamped
version that completes its widget:

```bash
leaf page stamp <page> --text "…" --completes <widget-id>
```

`--completes` ends each open to-do on that widget `done`, citing the version.
Repeat it for each widget the version completes. Open a to-do on a widget, another
element of the page, or `page`. In a thread, the reply that promises the work opens
it (`--todo`, below). A to-do on a widget stays open through versions that do not
complete it, even one that removes the widget.

## Long-running work

New user input reaches you only between your own operations; your harness contract
says exactly when. A long foreground operation, such as a test suite or a subagent
you wait on, leaves the user's comment unanswered until it finishes.

For work that will run longer than a few minutes, coordinate it rather than do it
yourself. Hand the reading, editing, and testing to background subagents or
background commands, and end your turn as the harness contract says. The watcher can
then deliver new input while the work runs. When a worker reports back, put its
result on the page and move what it finished out of the open work
(`authoring-revisions.md`, "Keep the current page current"). Then reply in the thread
that asked for the work, saying what changed and linking to it.

You drive the page, and your workers do not. You keep the server, the watcher and
its acknowledgements, replies, starts and status, edits to `index.html`, and stamps.
Each worker returns its result to you. A worker touches the page only in a role
Leaf's instructions give it, and only as those instructions direct: a command hub
worker (the `worker` value returned by `leaf page instructions <page>`), or a Codex
watcher task (`references/codex-watcher.md`). Say this in each worker's brief. A
worker that inherits your conversation also inherits the page, and may otherwise
treat the page as its own. Work that needs its own conversation with the user
belongs in a session of its own, with its own page.

A start lasts only for the turn that wrote it. About two minutes after that turn
ends, whether it finished or was interrupted, the banner says your turn ended and
quotes the start's line. Within a long turn, a start goes stale after about 15
minutes unless you start the item again. While a worker produces an update's
answer, start that update in your turn: the Stop hook then lets the turn end before
the answer is written. In the turn that the worker's result or the user's next
comment opens, start the item again or answer it. To keep work on your list past
the turn, open a to-do.

Within a turn, the banner shows the line of the item you started last, so start the
item that best describes what is running.

A to-do lasts until you end it. When a thread asks for work that can outlast the
current turn, such as a worker's build, a wait on CI, or a change you promise for
the next version, answer with a to-do:

```bash
leaf response reply <answer.ref> --todo "<what you owe>" --text "<what is under way>"
```

The reply answers the user's message and opens the to-do on that thread, under the
reply's id. The to-do keeps the thread on your list and shows in the banner, even
after the user resolves the thread or your session ends. A turn-written reply
cannot open a to-do, so use this command for such a promise.

Handing the work to another session, a background job, or a later turn is such a
promise, even when the tool you hand it to counts the launch as the end of your
part. The thread still waits for the result, and a reply declared `--done` tells the
user nothing more is coming.

The to-do ends wherever the result lands, with `leaf task end` and `done` and where
the result is, or with `failed` or `dropped` and the reason. So when the work
won't come back to you, put the page and the to-do's id in its brief. The session
that continues the work starts the to-do. That start shows its line in the banner
and the thread, and makes that session the one that may end the to-do. It can
finish on a later turn, and another session takes over by starting the same to-do.

Work on an update that finishes inside the turn needs no to-do.

## The On lists

The user's **On me** list holds everything waiting on them: each decision your work
leaves to them, and each answer, permission, review, or outside action you need from
them. A decision belongs there even when your next step does not depend on it. That
includes each proposal or candidate you present for their judgment, the ones you
rank below your recommendation too, and each product choice you raise. Ask a direct
question, register it by one of the routes in the table below, grouped as
`authoring-asks.md` says, and keep it there until the user decides it or you
withdraw it. Text alone registers nothing. Prose or a heading on the page, a status
line, or a question in chat only repeats an item a route registered. Information
the user may comment on but need not decide creates no item.

The banner's On me count and the On panel show these requests, plus any update of
the user's that failed to send and needs sending again. Your own list appears to
the user as **On <your name>** and shows what waits on you. Each list has a Done
section for the items that left it. The user presses `m` to step through On me in
page order, landing where each item is answered.

| Request | Register it | What answers it |
| --- | --- | --- |
| A decision or input recorded by a widget | Author a decision widget (`authoring-asks.md`); optional `lf-ask` frames its question and evidence | The widget's declared answer; a multiple-choice ask also needs the user's Done |
| A conversational answer | Open an agent thread with the question, or add `--ask` to a reply (`threads.md`) | The user's next reply there or a settling reaction |
| Required version sign-off | Declare sign-off and stamp the version (`authoring-asks.md`, "Sign-off") | That version's banner approval |
| An action neither route records, such as trying a build or connecting a browser | `leaf task open <page> <id> "<direct question naming the action>" --on user`, on its widget, section, or `page` | The user's Done; end it yourself when their action is established or no longer needed |

A widget ask has the id `widget:<widget-id>`, a prose ask `reply:<message-id>`, and
the sign-off ask for a stamped version `approval:v<version>`. A to-do on the user
keeps the id `task open` printed. A to-do on the user cannot sit on a thread; ask
there with `--ask`. A thread can hold several prose asks. Its latest unanswered one
is the current request, and the user's next reply in the thread answers every
unanswered prose ask before it. Publish a dependent question only once its
prerequisite is answered. The user's Done on a to-do says they did it; it grants no
permission or choice its question did not state.

Read the lists before a handoff, before waiting for the user, and after taking in
an answer:

```bash
leaf page state <page> | jq '{source, asks, todos, queues}'
```

`asks` and `todos` are the records. `queues.on_user` lists what On me shows: open
asks, to-dos on the user, and updates to resend. `queues.on_agent` lists the answers
you owe, the updates you are working on, and your to-dos. Each queue item names its
`id`, `kind`, `subject`, and `thread`. Select these fields with `jq`; do not rebuild
the lists from events or widget state. An ask holds its prompt, the kind of answer
it takes, and where it stands; a widget ask's answer is in the widget's state. Read a
thread's messages with `leaf page state <page> <message-id>`. For a page widget,
read the widget in the HTML file that `leaf page state <page>` names as
`active.file`; the widget-specific state command reports its state and metadata.
This reading covers the active document and the admitted log, not unsent browser
drafts or a tab still on an older version. Check `source` for an invalid or missing
draft before treating an empty list as a successful handoff.

Reconcile the lists with what you still need and owe. An empty On me says that you
need nothing from the user **now**; your list may still hold your work or a wait on
an external result. Complete authorized work without asking for permission again. A
paused project needs an ask only when its disposition or resumption needs the user's
decision; once they choose to keep it paused, that decision is settled. A blocked
action belongs on the user only when they can take the step that unblocks it. A
question about work another session owns stays with that session; ask here only for
the decision this page needs.

An answer in chat or elsewhere still settles the question. Incorporate it and retire
its page ask in a revision (`authoring-revisions.md`), or end the user's to-do with
`leaf task end`. End a prose ask the user answered in chat `done`, which records it
answered elsewhere, and one that no longer applies `dropped`, which records it
withdrawn:

```bash
leaf task end <page> reply:<message-id> done "<where the answer is>"
leaf task end <page> reply:<message-id> dropped "<why>"
```
 Neither writes an answer on the user's behalf. Keep finished requests off
On me; answered and withdrawn asks stay in the full `asks` reading.
