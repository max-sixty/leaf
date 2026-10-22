# Conversation loop

Keep the user informed on the page, and answer their updates there, following each
event's `handling`. A chat response does not change the page.

## The user's view

`leaf page state <page>` says what the user has seen. `viewed` is when a browser tab
last showed the page, in epoch seconds, renewed about every 10 seconds while visible
and `null` if nobody has opened it. Each thread's `unread` lists your messages the
user has not read ([threads](threads.md#what-the-user-has-read)). Nothing records
whether they saw a status.

`user_views` has one entry per browser page load over the last day, with its
viewport, the area left after Leaf's chrome, color scheme, pointer, scroll position
and the regions on screen. Use it to fit a revision to the window the user has.
Before taking an entry as the user's current view, read `visible`, `freshness`
(`stale` after 45 seconds without a report) and `matches_active_revision`. Each
entry's `checks` lists layout problems that browser measured, such as sideways
overflow. They are context for your judgment, not a substitute for
`leaf page check --render`. An empty list means no browser has reported, and a region
on screen does not mean the user read it.

## When to write

When a comment asks for work, post one line in its thread saying what you are about
to do, before you read or edit anything. If the event's `answer.writer` is `"turn"`,
your turn's opening message is that line (your harness's "Replies"). Otherwise run
first:

```bash
leaf response reply <answer.ref> --ephemeral --text "<what you will do, in a line>"
```

The line shows at once in the thread and as **Working** in Leaf's panel, at the foot
of the window, and it starts the update. Start any other item, such as a to-do or an
action on a page widget, with `leaf task start`. Chained before the step's command, a
start costs no extra tool call:

```bash
leaf task start <page> <id> "reading the reconnect traces" && <command>
```

Post or start again whenever the user would describe your work differently, such as
moving from reading to editing or testing, and after input interrupts other work.
Name the operation and its subject; "Working on it" says nothing. The panel shows
the item you started last, so start the one that best describes what is running.

Work asked for in chat, or begun on your own, gets a to-do, opened on the widget or
element it concerns or on `page`. On a new page, open and start it before authoring:

```bash
leaf task open <page> page "Add a glossary"   # prints the to-do's id
leaf task start <page> <todo> "drafting the glossary entries"
# After authoring the glossary and passing leaf page check:
leaf task end <page> <todo> done "<where the result is>"
```

A stamped version can end a widget's to-dos instead, with
`leaf page stamp <page> --text "…" --completes <widget-id>`. Housekeeping such as
re-vendoring, restarting the server, or merging needs no to-do.

When the work runs to several steps, some of which may wait on the user, write your
plan before you start the first step, so the user can follow it in the panel's Plan
tab. `leaf task plan <page>` reads the whole outline from stdin as a JSON list of
steps: the goal at depth 0, each step one deeper than the step it belongs to, and
each either a `title` with a `state` (`open`, `working`, `done` or `dropped`) or the
`item` it names:

```bash
leaf task plan <page> <<'EOF'
[{"depth": 0, "title": "Move the billing exports", "state": "working"},
 {"depth": 1, "item": "<to-do id>"},
 {"depth": 1, "item": "widget:<widget-id>"},
 {"depth": 1, "title": "Retire the old export job", "state": "open"}]
EOF
```

Make each step that stays owed past your turn a to-do or obligation the plan names by
id, so it follows that item's state. Keep a plain step's state current yourself, and
write the plan again when a step finishes or the breakdown changes.

## Status and handoff

Before handing over, reconcile both lists ("The On lists"), then say in the panel
what you want back, naming the answer or decision rather than the fact that you are
waiting:

```bash
leaf status <page> waiting "<what you want back>"
```

On an informational page with nothing on On me, leave the detail empty; the panel
then invites the user to comment. `waiting` ends your starts and leaves your to-dos
open. Tell the user what they can do on the page, and hand over as your harness
contract says. From the first handoff on, every turn's final response includes the
exact page URL; progress messages don't repeat it. An export hands over its file
URL, and a harness that already shows the page uses its own handoff surface.

## Long-running work

New input reaches you between your own operations, so leave workers running while
you follow the harness's delivery loop (the main skill's "Stay responsive"). When a
worker reports, review and integrate its result, put it on the page, move finished
work out of the open work (`authoring-revisions.md`, "Keep the current page
current"), and reply in the thread that asked, linking to the result.

Workers return results to you and leave the page alone: the server, the watcher,
acknowledgements, replies, starts, status, `index.html` and stamps stay yours. Say so
in each brief, since a worker that inherits your conversation inherits the page too.
The exceptions are a command hub worker (the `worker` value from
`leaf page instructions <page>`) and a Codex watcher task (`codex-watcher.md`). Work
that needs its own conversation with the user belongs in its own session, with its
own page.

A start lasts only for the turn that wrote it, and within a long turn it goes stale
after about 15 minutes. While a worker produces an update's answer, start that update
before you end your turn, since the Stop hook lets a turn end over an update it
started. In the next turn, start the item again or answer it.

For work that outlasts the turn, such as a worker's build, a wait on CI, or a change
you promise for the next version, answer the thread with a to-do:

```bash
leaf response reply <answer.ref> --todo "<what you owe>" --text "<what is under way>"
```

The reply answers the message and opens a to-do on the thread, under the reply's id.
The to-do keeps the thread on your list until you end it, even after the user
resolves the thread or your session ends. A turn's own final message cannot open
one. Handing the work to another session, a background job, or a later turn is such
a promise too; a `--done` reply would tell the user nothing more is coming. So is
holding a decision the user put off until other work lands: while the to-do stays
open, the decision their thread is about stays off On me, and ending the to-do puts
it back.

Whoever finishes the work ends the to-do: `leaf task end <page> <todo> done "<where>"`,
or `failed` or `dropped` with the reason. If another session
will finish it, put the page and the to-do id in its brief; that session runs
`leaf task start` on the to-do, which lets it end the to-do now or on a later turn.

## The On lists

The user's **On me** list holds everything waiting on them: each decision your work
leaves to them, whether or not your next step depends on it, and each answer,
permission, review, or outside action you need. That includes every option you
present for their judgment, not only the one you recommend. Ask each as a direct
question by a route in the table below, grouped as `authoring-decisions.md` says, and
keep it until the user decides or you withdraw it. A question written in prose, a
heading, a status line or chat isn't on On me. Information they may comment on but
need not decide is not an obligation.

On me also lists any update of the user's that failed to send, and your own list
shows as **On <your name>**. The user presses `m` to step through On me in page
order; each press lands where the obligation is answered, and on a widget's
obligation its numbered actions (`1`–`9`) answer it there.

| Request                                                                         | Register it                                                                                                     | What answers it                                                                       |
| ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| A decision or input recorded by a widget                                        | Author a decision widget (`authoring-decisions.md`); optional `lf-ask` frames its question and evidence         | The widget's declared answer; a multiple-choice widget also needs the user's Done     |
| A conversational answer                                                         | An `lf-ask` holding the question, with no widget inside, in a reply's or new thread's markup (`threads.md`)     | The user's next message there or a settling reaction                                  |
| Required version sign-off                                                       | Declare sign-off and stamp the version (`authoring-decisions.md`, "Sign-off")                                   | The user's approval of that version, its row in On me                                 |
| An action neither route records, such as trying a build or connecting a browser | `leaf task open <page> <id> "<direct question naming the action>" --on user`, on its widget, section, or `page` | The user's Done; end it yourself when their action is established or no longer needed |

Obligation ids are `widget:<widget-id>` for a widget, `lf-ask` included,
`approval:v<version>` for a version's sign-off, and `update:<event-id>` for an update
the user handed over. A to-do on the user keeps the id `task open` printed. It cannot
sit on a thread, so in a thread ask with an `lf-ask`. The user's next message in a
thread answers every question asked before it there. Ask a dependent question only
once its prerequisite is answered. The user's Done on a to-do says they did it; it
grants nothing its question did not ask.

Read the lists before a handoff, before waiting for the user, and after taking in an
answer:

```bash
leaf page state <page> | jq '{source, obligations, todos, queues}'
```

`queues.on_user` is On me and `queues.on_agent` is your list, the updates you owe a
reply or a version and your to-dos. Read them as given rather than rebuilding them
from events. A row names its obligation or to-do by `id`; the obligation's record in
`obligations` holds its `prompt`, its `answer` once given, its `status` and its
`next_actor`, and the to-do's record in `todos` holds its `title` and the start
`running` on it. When no delivery is at hand, `activity.obligations` lists each
answer you owe beside what settles it: the reply to write, with its `ref` where you
can still use it, or the action a stamped version must record. Unsent drafts and
tabs on older versions are not in this reading, and an invalid or missing draft
shows in `source`, so check it before taking an empty list as a clean handoff.

An empty On me means you need nothing from the user now. Finish authorized work
without asking again. Ask about a paused project only when resuming or dropping it
needs the user's decision. Put a blocked action on the user only when they can
unblock it, and leave questions about another session's work to that session.

When the user answers in chat or elsewhere, use the answer and retire the page's
obligation in a revision (`authoring-revisions.md`), or end their to-do with
`leaf task end`. End a question in a thread answered elsewhere `done`, or `dropped`
when it no longer applies:

```bash
leaf task end <page> widget:<lf-ask-id> done "<where the answer is>"
leaf task end <page> widget:<lf-ask-id> dropped "<why>"
```
