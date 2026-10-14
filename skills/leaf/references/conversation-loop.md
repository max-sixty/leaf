# Conversation loop

Keep the user informed on the page, and answer their updates there, following each
event's `handling`. A chat response does not change the page.

## What the user sees

The user follows your work on the page:

| Surface | What it shows | Written by |
| --- | --- | --- |
| Banner | one sentence for the whole page: the line of the item you started last, or what you want back | `leaf task start`, `leaf status <page> waiting "<detail>"` |
| Beside a thread or widget | **Working** and your line: the thread's working message above its reply box, or on the control the work answers | `leaf response reply --ephemeral`, `leaf task start <page> <id> "<line>"` |
| Thread | your answer to the user's message, with the progress before it folded behind it | the response operation named by delivered `handling` |
| Page | the revised content in place, and a stamp's changelog | saving `index.html`, `leaf page stamp` |

Leaf marks each update **Sent**, **Queued**, and **Picked up** by itself. Your
harness may add its current step to the banner.

In `leaf page state <page>`, `viewed` is when a browser tab last showed the page, in
epoch seconds, renewed about every 30 seconds while visible and `null` if nobody has
opened it. Each thread's `unread` lists your messages the user has not read
([threads](threads.md#what-the-user-has-read)). Nothing records whether they saw a
status.

## The user's view

`user_views` in `leaf page state <page>` has one entry per browser page load over the
last day: its viewport, the area left after Leaf's chrome, color scheme, pointer,
reduced motion, scroll position, and which regions are on screen. Use it to check
that a revision fits the window the user has. `visible` says whether the load showed
the page at its last report, `freshness` turns `stale` after 45 seconds without one,
and `matches_active_revision` says whether it shows your latest revision. Each
entry's `checks` lists layout problems that browser measured, such as sideways
overflow, with their own `freshness` and `matches_view`. They are context, not a
substitute for `leaf page check --render`. An empty list means no browser has
reported, and a region on screen does not mean the user read it.

## When to write

When a comment asks for work, post one line in its thread saying what you are about
to do, before you read or edit anything. If the event's `answer.writer` is `"turn"`,
your turn's opening message is that line (your harness's "Replies"). Otherwise run
first:

```bash
leaf response reply <answer.ref> --ephemeral --text "<what you will do, in a line>"
```

The line shows at once as the thread's working message and the banner's **Working**
line, and it starts the update. Your answer later folds it away
([progress messages](threads.md#progress-messages)). Start any other item, such as a
to-do or an action on a page widget, with `leaf task start`:

```bash
leaf task start <page> <id> "reading the reconnect traces" && <command>
```

Post or start again whenever the user would describe your work differently, such as
moving from reading to editing or testing. Chained before the step's command, a start
costs no extra tool call. Name the operation and its subject; "Working on it" says
nothing.

Work asked for in chat, or begun on your own, gets a to-do. Open it on the widget or
element it concerns, or on `page`; on a new page, open and start it before
authoring:

```bash
leaf task open <page> page "Add a glossary"
leaf task start <page> <todo> "drafting the glossary entries"
leaf task end <page> <todo> done "<where the result is>"
```

`leaf task open` prints the to-do's `id`. Until you end it, `leaf status … idle`
refuses. Housekeeping such as re-vendoring, restarting the server, or merging needs
no to-do.

When input arrives during other work:

1. If the delivery's `acknowledge` names a receipt command, run it first. If it is
   `null`, your harness has confirmed receipt.
2. Post the progress line for each update that asks for work. Answer one that asks
   for no work, such as a question, right away.
3. Then start your earlier item again, so the banner describes the work that
   continues.

Reply once the revision passes `leaf page check`, the only check the main skill's
"Check the page" step requires before a reply.

## Status and handoff

Before handing over, reconcile both lists ("The On lists"), then say what you want
back:

```bash
leaf status <page> waiting "<what you want back>"
```

Name the answer or decision, not the fact that you are waiting. On an informational
page with no ask, leave it empty; the banner then invites the user to comment. Tell
the user what they can do on the page, and hand over as your harness contract says.
From the first handoff on, every turn's final response includes the exact page URL.
An export hands over its file URL, and a harness that already shows the page uses
its own handoff surface.

`waiting` ends all your earlier starts; your to-dos stay open. Your reply ends an
update's start, or, for an answer owed in markup, the stamped version that records
the user's press. A to-do's start ends with the to-do, through `leaf task end` or a
stamped version that completes its widget:

```bash
leaf page stamp <page> --text "…" --completes <widget-id>
```

`--completes` ends every open to-do on that widget `done`, citing the version; repeat
it for each widget. A to-do on a widget stays open through versions that do not
complete it, even one that removes the widget.

## Long-running work

New input reaches you only between your own operations, so a long foreground
operation, such as a test suite or a subagent you wait on, leaves the user's comment
unanswered until it finishes. For work longer than a few minutes, hand the reading,
editing, and testing to background subagents or commands, and end your turn as your
harness contract says. When a worker reports, put its result on the page, move what
it finished out of the open work (`authoring-revisions.md`, "Keep the current page
current"), and reply in the thread that asked, linking to it.

Workers return results to you and leave the page alone. The server, the watcher,
acknowledgements, replies, starts, status, `index.html`, and stamps stay yours. The
exceptions are a command hub worker (the `worker` value from
`leaf page instructions <page>`) and a Codex watcher task
(`references/codex-watcher.md`). Say so in each brief, since a worker that inherits
your conversation inherits the page too. Work that needs its own conversation with
the user belongs in its own session, with its own page.

A start lasts only for the turn that wrote it. About two minutes after the turn ends,
the banner says your turn ended and quotes the line, and within a long turn a start
goes stale after about 15 minutes. The banner shows the item you started last, so
start the one that best describes what is running. While a worker produces an
update's answer, start that update before you end your turn; the Stop hook lets a
turn end over an update it started. In the next turn, start the item again or answer
it.

For work that outlasts the turn, such as a worker's build, a wait on CI, or a change
you promise for the next version, answer the thread with a to-do:

```bash
leaf response reply <answer.ref> --todo "<what you owe>" --text "<what is under way>"
```

The reply answers the message and opens a to-do on the thread, under the reply's id.
The to-do keeps the thread on your list and in the banner until you end it, even
after the user resolves the thread or your session ends. A turn's own message cannot
open one. Handing the work to another session, a background job, or a later turn is
such a promise too; a `--done` reply would tell the user nothing more is coming.

Whoever finishes the work ends the to-do: `leaf task end <page> <todo> done "<where>"`,
or `failed`/`dropped` with the reason. If another session will finish it, put the page
and the to-do id in its brief; that session runs `leaf task start` on the to-do,
which lets it end the to-do now or on a later turn.

Work on an update that finishes inside the turn needs no to-do.

## The On lists

The user's **On me** list holds everything waiting on them: each decision your work
leaves to them, whether or not your next step depends on it, and each answer,
permission, review, or outside action you need. That includes every option you
present for their judgment, not only the one you recommend. Ask each as a direct
question by a route in the table below, grouped as `authoring-asks.md` says, and keep
it until the user decides or you withdraw it. A question written in prose, a heading,
a status line or chat isn't on On me; only the routes in the table put it there.

On me also lists any update of the user's that failed to send. Your own list shows as
**On <your name>**. The user presses `m` to step through On me in page order, landing
where each item is answered, where the ask's numbered actions (`1`–`9`) answer it.

| Request | Register it | What answers it |
| --- | --- | --- |
| A decision or input recorded by a widget | Author a decision widget (`authoring-asks.md`); optional `lf-ask` frames its question and evidence | The widget's declared answer; a multiple-choice ask also needs the user's Done |
| A conversational answer | Open an agent thread with the question, or add `--ask` to a reply (`threads.md`) | The user's next reply there or a settling reaction |
| Required version sign-off | Declare sign-off and stamp the version (`authoring-asks.md`, "Sign-off") | That version's banner approval |
| An action neither route records, such as trying a build or connecting a browser | `leaf task open <page> <id> "<direct question naming the action>" --on user`, on its widget, section, or `page` | The user's Done; end it yourself when their action is established or no longer needed |

Ask ids are `widget:<widget-id>` for a widget ask, `reply:<message-id>` for a prose
ask, and `approval:v<version>` for a version's sign-off. A to-do on the user keeps
the id `task open` printed. It cannot sit on a thread, so in a thread ask with
`--ask`. When a thread holds several prose asks, the latest unanswered one is the
current request, and the user's next reply there answers all of them. Ask a
dependent question only once its prerequisite is answered. The user's Done on a
to-do says they did it; it grants nothing its question did not ask.

Read the lists before a handoff, before waiting for the user, and after taking in an
answer:

```bash
leaf page state <page> | jq '{source, asks, todos, queues}'
```

`queues.on_user` is On me: open asks, to-dos on the user, and updates to resend.
`queues.on_agent` is your list: answers you owe, updates you are working on, and your
to-dos. Read them as given rather than rebuilding them from events. An ask holds its
`prompt`, its `answer` once given, and its `status`; a widget ask's answer comes from
the widget's state. Read a thread with `leaf page state <page> <message-id>`, and a
widget in the HTML file named by `active.file`. Unsent drafts and tabs on older
versions are not in this reading. Check `source` for an invalid or missing draft
before taking an empty list as a clean handoff.

An empty On me means you need nothing from the user now. Finish authorized work
without asking again. Ask about a paused project only when resuming or dropping it
needs the user's decision. Put a blocked action on the user only when they can
unblock it, and leave questions about another session's work to that session.

When the user answers in chat or elsewhere, use the answer and retire the page's ask
in a revision (`authoring-revisions.md`), or end their to-do with `leaf task end`. End
a prose ask answered elsewhere `done`, or `dropped` when it no longer applies:

```bash
leaf task end <page> reply:<message-id> done "<where the answer is>"
leaf task end <page> reply:<message-id> dropped "<why>"
```
