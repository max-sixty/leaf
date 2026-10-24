# Conversation loop

Keep the user informed on the page, and answer their updates there, following each
event's `handling`. A chat response does not change the page.

## What the user sees

In `leaf page state <page>`, `viewed` is when a browser tab last showed the page, in
epoch seconds, renewed about every 10 seconds while visible and `null` if nobody has
opened it. Each thread's `unread` lists your messages the user has not read
([threads](threads.md#what-the-user-has-read)). Nothing records whether they saw a
status.

## The user's view

`user_views` in `leaf page state <page>` has one entry per browser page load over the
last day: its viewport, the area left after Leaf's chrome, color scheme, pointer,
scroll position, and which regions are on screen. Use it to check
that a revision fits the window the user has. `visible` says whether the load showed
the page at its last report, `freshness` turns `stale` after 45 seconds without one,
and `matches_active_revision` says whether it shows your latest revision. Each
entry's `checks` lists layout problems that browser measured, such as sideways
overflow. They are context, not a substitute for `leaf page check --render`, which
reads the desktop at the latest entry's viewport. An empty list means no browser has
reported, and a region on screen does not mean the user read it.

## When to write

When a comment asks for work, post one line in its thread saying what you are about
to do, before you read or edit anything. If the event's `answer.writer` is `"turn"`,
your turn's opening message is that line (your harness's "Replies"). Otherwise run
first:

```bash
leaf thread reply <answer.ref> --ephemeral --text "<what you will do, in a line>"
```

The line shows at once as the thread's working message and the panel's **Working**
status, and it starts the update. Start any other item, such as a
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
# After authoring the glossary and passing leaf page check:
leaf task end <page> <todo> done "<where the result is>"
```

`leaf task open` prints the to-do's `id`.
Housekeeping such as re-vendoring, restarting the server, or merging needs
no to-do.

When the work runs to several steps, some of which may wait on the user, write your plan
before you start the first step, so the user can follow it in the panel's list of your
work, under the plan's progress, and see On me grouped by its goals: the goal, its steps
in order, the one under way, and those waiting on them.
`leaf task plan <page>` reads the whole outline from stdin as a JSON list of steps: the
goal at depth 0, each step one deeper than the step it belongs to, and each either a
`title` with a `state` (`open`, `working`, `done` or `dropped`) or the `item` it names:

```bash
leaf task plan <page> <<'EOF'
[{"depth": 0, "title": "Move the billing exports", "state": "working"},
 {"depth": 1, "item": "<to-do id>"},
 {"depth": 1, "item": "widget:<widget-id>"},
 {"depth": 1, "title": "Retire the old export job", "state": "open"}]
EOF
```

Make each step that stays owed past your turn a to-do or obligation the plan names by
id, so it follows that one's state; a plain step's state is yours to keep current. Write
the plan again when a step finishes or the breakdown changes.

When input arrives:

1. Post the progress line for each update that asks for work. Answer a question you
   can already settle at once; make any related page revision after replying.
2. If it interrupted other work, start that item again, so the panel's status
   describes the work that continues.

## Page availability and handoff

Before handing over, reconcile both lists ("The On lists"). Put questions that need
an answer in a thread message with `--obligation`, so the user can open the thread
from On me and reply there. Page availability does not ask the user for anything.

Leave the page available for optional feedback, putting down your current starts:

```bash
leaf page open <page>
```

Your to-dos stay open. An informational page with nothing on On me simply invites
comments. Tell the user what they can do on the page, and hand over as your harness
contract says. From the first handoff on, every turn's final response includes the
exact page URL; progress messages don't repeat it. An export hands over its file URL,
and a harness that already shows the page uses its own handoff surface.

When the page's work and conversation are finished, `leaf page close <page>` stops
watching it. It refuses while updates are unread, answers are owed or agent to-dos
remain open; closing settles no obligation.

A to-do's start ends with the to-do, through `leaf task end` or a
stamped version that completes its widget:

```bash
leaf page stamp <page> --text "…" --completes <widget-id>
```

## Long-running work

Follow the parent and worker roles in the main skill's "Stay responsive" section.
New input reaches you between your own operations, so leave workers running while
you follow the harness's delivery loop. When a worker reports, review and integrate
its result, put it on the page, move finished work out of the open work
(`authoring-revisions.md`, "Keep the current page current"), and reply in the thread
that asked, linking to the result.

Workers return results to you and leave the page alone. The server, the watcher,
acknowledgements, replies, starts, status, `index.html`, and stamps stay yours. The
exceptions are a command hub worker (the `worker` value from
`leaf page instructions <page>`) and a Codex watcher task
(`references/codex-watcher.md`). Say so in each brief, since a worker that inherits
your conversation inherits the page too. Work that needs its own conversation with
the user belongs in its own session, with its own page.

A start lasts only for the turn that wrote it.
Within a long turn a start goes stale after about 15 minutes. The status shows the item you started last, so
start the one that best describes what is running. While a worker produces an
update's answer, start that update before you end your turn; the Stop hook lets a
turn end over an update it started. In the next turn, start the item again or answer
it.

For work that outlasts the turn, such as a worker's build, a wait on CI, or a change
you promise for the next version, answer the thread with a to-do:

```bash
leaf thread reply <answer.ref> --todo "<what you owe>" --text "<what is under way>"
```

The reply answers the message and opens a to-do on the thread, under the reply's id.
The to-do keeps the thread on your list and in the panel's status until you end it,
even after the user resolves the thread or your session ends. A turn's own message cannot
open one. Handing the work to another session, a background job, or a later turn is
such a promise too; a `--done` reply would tell the user nothing more is coming. So is
holding a decision the user put off until other work lands: while the to-do stays open,
the decision their thread is about stays off On me, and ending the to-do puts it back.

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
question by a route in the table below, grouped as `authoring-decisions.md` says, and keep
it until the user decides or you withdraw it. A question written in prose, a heading,
a status line or chat isn't on On me; only the routes in the table put it there.
Information they may comment on but need not decide is not an obligation.

On me also lists any update of the user's that failed to send. Your own list shows as
**On <your name>**. The user presses `m` to step through On me in page order. Each
press lands where the obligation is answered; on a widget's obligation, its numbered actions
(`1`–`9`) answer it there.

| Request                                                                         | Register it                                                                                                             | What answers it                                                                       |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| A decision or input recorded by a widget                                        | Author a decision widget (`authoring-decisions.md`); optional `lf-ask` frames its question and evidence                 | The widget's declared answer; a multiple-choice widget also needs the user's Done     |
| A conversational answer                                                         | `--obligation` on `thread open` or `thread reply` (`threads.md`)                                                        | The user's next message there or a settling reaction                                  |
| Approval of a stated action                                                     | Write `lf-approval` with the exact subject (`authoring-decisions.md`, "Approval")                                       | The widget's recorded approval and its row in On me                                   |
| An action neither route records, such as trying a build or connecting a browser | `leaf task open <page> <id> "<direct question naming the action>" --on user`, on its thread, widget, section, or `page` | The user's Done; end it yourself when their action is established or no longer needed |

Generally pass `--obligation` when a message hands the next move to the user.
Progress and information that need no response create no obligation. When a widget
already captures the same answer, its obligation is sufficient.

Obligation ids are `message:<message-id>` for an explicit message request,
`widget:<widget-id>` for a widget, `lf-ask` and `lf-approval` included,
and `update:<event-id>` for an update
the user handed over. A to-do on the user keeps the id `task open` printed. It can sit on a thread; replies discuss the action and Done completes it.
The user's next message in a thread answers every conversational request before it.
A clarification hands the conversation back to you; if you still need input, make
the next request with `--obligation`. A reply does not claim outside work is done.
Ask a dependent question only once its prerequisite is answered. The user's Done on a
to-do says they did it; it grants nothing its question did not ask.

Read the lists before a handoff, before waiting for the user, and after taking in an
answer:

```bash
leaf page state <page> | jq '{source, obligations, todos, queues}'
```

`queues.on_user` is On me. `queues.on_agent` is your list: the updates you owe a
reply or a version, and your to-dos. Read them as given rather than rebuilding them
from events. A row names its obligation or to-do by `id`. An obligation's record in
`obligations` holds its `prompt`, its `answer` once given, its `status` and its
`next_actor`, and a widget's obligation takes its answer from the widget's state; a
to-do's record in `todos` holds its `title` and the start `running` on it.
`activity.obligations` lists each answer you owe as its record's `id` beside the
`answer` that settles it: the reply to write, with the `ref` its delivery gave where
you can still use it, or the action a stamped version must record. Recover what you
owe there when no delivery is at hand. Unsent browser drafts and tabs on older versions
are not in this reading.
Check `source` for an invalid or missing `index.html` before taking an empty list as a
clean handoff.

An empty On me means you need nothing from the user now. Finish authorized work
without asking again. Ask about a paused project only when resuming or dropping it
needs the user's decision. Put a blocked action on the user only when they can
unblock it, and leave questions about another session's work to that session.

When the user answers in chat or elsewhere, use the answer and retire the page's obligation
in a revision (`authoring-revisions.md`), or end their to-do with `leaf task end`. End
a question in a thread answered elsewhere `done`, or `dropped` when it no longer
applies:

```bash
leaf task end <page> message:<message-id> done "<where the answer is>"
leaf task end <page> message:<message-id> dropped "<why>"
```

For a reply-answered widget, use its `widget:<widget-id>` obligation id instead.
