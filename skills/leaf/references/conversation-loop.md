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
overflow. They are context, not a substitute for `leaf page check --render`
(`page-checkpoints.md`, "Pre-handover review"). An empty list means no browser has
reported, and a region on screen does not mean the user read it.

## When to write

When a comment asks for work, post one line in its thread saying what you are about
to do, before you read or edit anything. If the event's `answer.writer` is `"turn"`,
which only a Codex turn receives, your turn's opening message is that line
(`harness-codex.md`, "Replies"). Otherwise run first:

```bash
leaf thread reply <answer.ref> --ephemeral --text "<what you will do, in a line>"
```

The line shows at once as the thread's working message and the panel's status, and it
starts the update. Start any other item, such as a
to-do or an action on a page widget, with `leaf task start`:

```bash
leaf task start <page> <id> --text "reading the reconnect traces" && <command>
```

Post or start again whenever the user would describe your work differently, such as
moving from reading to editing or testing. Chained before the step's command, a start
costs no extra tool call. Name the operation and its subject; "Working on it" says
nothing. The user reads the line at a glance, in the panel and in the list of their
pages, so say in a few of their words what you are doing ("checking the fix in
Firefox"): not a to-do's title, which reads as an instruction to them, and without
commit hashes, ids or the mechanics of a CI run.

Work asked for in chat, or begun on your own, gets a to-do. Open it on the widget or
element it concerns, or on `page`; on a new page, open and start it before
authoring:

```bash
leaf task create <page> page --title "Add a glossary"
leaf task start <page> <todo> --text "drafting the glossary entries"
# After authoring the glossary and passing leaf page check:
leaf task end <page> <todo> done --text "<where the result is>"
```

`leaf task create` prints the to-do's `id`.
Housekeeping such as changing packages, restarting the server, or merging needs
no to-do.

When the work runs to several steps and past the turn you are in, as when some steps
wait on the user, write your plan before you start the first step. The user follows it
at the head of the panel's list of your work, and On Me groups by its goals: each goal,
its steps in order, the one under way, where each finished step's result is, and those
waiting on them. `leaf task plan <page>` reads the whole outline from stdin as a JSON
list: a goal is a `title` at depth 0 over the steps one level deeper, and each step is
a `todo`, which opens a to-do with that title, or names the `item` it is, an open
to-do's or an obligation's id:

```bash
leaf task plan <page> <<'EOF'
[{"depth": 0, "title": "Move the billing exports"},
 {"depth": 1, "item": "<to-do id>"},
 {"depth": 1, "item": "widget:<widget-id>"},
 {"depth": 1, "todo": "Retire the old export job"}]
EOF
```

Each step shows the state of its to-do or obligation, and the plan it prints names each
new to-do by id. A step of the user's that you can't ask yet, such as a check only they
can run once your patch exists, is your `todo` to have it done; when you ask it, put the
question's obligation under that step. Start and end a step's to-do as you would any
other; its end's `--text` is where the user finds the result. Write the plan again only
when the breakdown changes, naming the steps it already holds by `item`.

When input arrives:

1. Post the progress line for each update that asks for work. Answer a question you
   can already settle at once; make any related page revision after replying.
2. If it interrupted other work, start that item again, so the panel's status
   describes the work that continues.

## Page availability and handoff

Before handing over, reconcile both lists ("The On lists"). Page availability does
not ask the user for anything.

Leave the page available for optional feedback, putting down your current starts:

```bash
leaf page open <page>
```

Your to-dos stay open. An informational page with nothing on On Me simply invites
comments. Tell the user what they can do on the page, and hand over as your harness
contract says. From the first handoff on, every turn's final response includes the
exact page URL; progress messages don't repeat it. An export hands over its file URL,
and a harness that already shows the page uses its own handoff surface.

When the page's work and conversation are finished, end your side of the page with
`leaf page close <page>` (`page-checkpoints.md`, "Ending").

A to-do's start ends with the to-do, through `leaf task end` or a
stamped version that completes its widget:

```bash
leaf page stamp <page> --text "…" --completes <widget-id>
```

A start on the user's update, such as a widget action or a comment, ends with your
answer to it. The stamped version that records a widget answer takes it in without
`--completes`, which names only your own to-dos.

## Long-running work

Follow the main skill's "Stay responsive" section while workers run. When a worker
reports, review and integrate its result, put it on the page, move finished work out
of the open work (`authoring-revisions.md`, "Keep the current page current"), and
reply in the thread that asked, linking to the result.

Work that needs its own conversation with the user belongs in its own session, with
its own page.

Pages and decisions built from a worker's report tend to keep the report's shape, and
the brief sets that shape. Ask a worker to return, with each finding, the material it
rests on: the cases behind a count, each with how it was counted, or the lines of
code, quoted or in files it names (`page-authoring.md`, "Show what a claim rests
on"). When the user will decide on what a worker finds, such as an audit's
candidates, ask it for each decision's material rather than a record of each finding:
the question the finding raises, each option titled by the result the user would get
for that finding (not a kind of change shared by every finding, such as Remove), and
each result shown as the user would meet it, such as a capture of the interface with
the change applied beside today's, or a request the service would then refuse
(`authoring-on-me.md`, "What a question holds").

Each item you start shows its line where the user looks for that work: in its
thread, in On <your name>, and in the panel's status while it is the newest start. So start every item whose work is running, a worker's included, rather
than the one that best describes your own step. A start goes stale after about 15
minutes without a new line, and once your session stops working: your turn has
ended and your harness reports nothing of yours still running in the background.
While a worker produces an update's answer, start that update before you end your
turn. Where your harness reports your background work, as Claude Code does, the start
holds the update through your later turns while an agent of yours works, and until
your next turn while only a command of yours runs. Leave the update to that work. Once
nothing holds it, Leaf names it in your next turn: answer it or start it again.

For work that outlasts the turn, such as a worker's build, a wait on CI, or a change
you promise for the next version, answer the thread with a to-do, and while its work
runs, say on the same reference what is running:

```bash
leaf thread reply <answer.ref> --todo "<what you owe>" --text "<your answer>"
leaf thread reply <answer.ref> --ephemeral --text "<what is running>"
```

The reply answers the message and opens a to-do on the thread, under the reply's id.
The to-do keeps the thread on your list until you end it,
even after the user resolves the thread or your session ends. A turn's own message cannot
open one. Handing the work to another session, a background job, or a later turn is
such a promise too; a `--done` reply would tell the user nothing more is coming. So is
holding a decision the user put off until other work lands: while the to-do stays open,
the decision their thread is about stays off On Me, and ending the to-do puts it back.
Name what such a to-do waits on with `--waiting-on` (`threads.md`).

The progress line starts the to-do, so the user sees it under your reply and in On
<your name> while the work runs, rather than a promise that reads the same whether or
not anything is moving. Post it again as the work moves to its next step. When a worker
does the work, put the page and the reference in its brief, and have it post its line
there as it starts each step.

Whoever finishes the work ends the to-do: `leaf task end <page> <todo> done --text "<where>"`,
or `failed`/`dropped` with the reason. If another session will finish it, put the page
and the to-do id in its brief.

Work on an update that finishes inside the turn needs no to-do.

## The On lists

The user's **On Me** list holds everything waiting on them: each decision your work
leaves to them, whether or not your next step depends on it, and each answer,
permission, review, or outside action you need. That includes every option you
present for their judgment, not only the one you recommend. Ask each by a route in
the table below, grouped as `authoring-on-me.md` says, and keep it until the user
decides or you withdraw it. A question written in prose, a heading, a status line or
chat isn't on On Me; only the routes in the table put it there. Information they may
comment on but need not decide is not an obligation.

On Me also lists any update of the user's that failed to send. Your own list shows as
**On <your name>**. The user presses `m` to step through On Me in page order. Each
press lands where the obligation is answered; on a widget's obligation, its numbered actions
(`1`–`9`) answer it there, and on a thread message, its thread opens on it. Leaf adds
no control of its own, such as a Done, to answer an item: on the page, the user answers
through the widget's own actions or a reply in the thread, and you end a question
they answer elsewhere, such as in chat, by resolving its thread (below).

| Request                                                                          | Register it                                                                                                                                   | What answers it                                                                                                                                 |
| -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| A decision or input recorded by a widget                                         | Author a widget that records it, on the page or in a thread message (`authoring-on-me.md`)                                                    | The widget's declared answer; a multiple-choice widget also needs the user's Done                                                               |
| A question answered in words                                                     | `--obligation` on `thread create` or `thread reply` (`threads.md`)                                                                            | The user's next message there or a settling reaction                                                                                            |
| Permission for an action you take, such as merging a pull request                | Options to take the action or keep things as they are (`authoring-on-me.md`, "Permission")                                                    | The user's pick and its row in On Me                                                                                                            |
| An action only the user can take, such as trying a build or connecting a browser | A message saying what to do, asking for the user's answer with options or `--obligation` (below), in a thread on what it concerns or the page | Your resolve of its thread once you see its effect, which you check yourself wherever you can; or the user's pick, reply or a settling reaction |

For an action you take once the user agrees, such as merging a ready pull request,
ask their permission, even where they could start it themselves with a command they
would type to you. Options to take the action or hold off let one press both answer
and tell you to go on. An action only they can take, such as trying a build on their
phone or running a command that needs a login you lack, is a step. Say what to do,
and ask for their answer only for what they alone can report, such as whether the
build worked, or where your next step waits on it, since their answer is what tells
you to go on. Where its outcomes can be listed, such as installed or failed, options
usually spare them typing; words suit what only they can describe, such as what an
error said. Check the step's effect yourself wherever you can, such as a file deleted
or an issue filed.

Generally pass `--obligation` when a message hands the next move to the user,
including an answer that informs a decision already on On Me. A message that asks a
new question whose answers you can list usually asks with a widget in it instead
(`threads.md`, "Ask for a pick"). Progress and information that need no response
create no obligation.

Obligation ids are `message:<message>` for an explicit message request,
`widget:<widget-id>` for a widget that asks,
and `update:<event-id>` for an update
the user handed over.
The user's next message in a thread answers every conversational request before it,
whatever it says, so On Me clears the moment they reply. Its delivery names those
requests in `settled`, for you to read the message against. A clarification hands the
conversation back to you, as does a question about an action, such as "where do I run
it?"; if the request still stands, answer with `--obligation <id>`, which returns
the same item to On Me (`threads.md`). A new question takes `--obligation` alone. An
answer grants nothing its question did not ask.

Read the lists before a handoff, before waiting for the user, and after taking in an
answer:

```bash
leaf page state <page> | jq '{source, obligations, queues}'
```

`queues.on_user` is On Me. `queues.on_agent` is your list: the updates you owe a
reply or a version, and your to-dos. Read them as given rather than rebuilding them
from events. A row names its obligation or to-do by `id`, and in `also` the other
obligations the user answers at the same place: an answer of yours in a thread about a
widget's question rides on that widget's row. An obligation's record in
`obligations` holds its `prompt`, its `answer` once given, its `next_actor` and where
it stands: `state` is `waiting`, `running`, `blocked` or `done`, `reason` says why a
blocked one is, such as `stopped` once the turn that had it ended, and `outcome` how a
done one ended. A widget's obligation takes its answer from the widget's state. A to-do
is a record there too (`source.kind` `todo`), its title as `prompt.text` and the start
in force on it as `line`.
`activity.obligations` lists each answer you owe as its record's `id` beside the
`answer` that settles it: the reply to write, with the `ref` its delivery gave where
you can still use it, or the action a stamped version must record. Recover what you
owe there when no delivery is at hand. The user's unsent drafts and tabs on older versions
are not in this reading.
Check `source` for an invalid or missing `index.html` before taking an empty list as a
clean handoff.

An empty On Me means you need nothing from the user now. Finish authorized work
without asking again. Ask about a paused project only when resuming or dropping it
needs the user's decision. Put a blocked action on the user only when they can
unblock it, and leave questions about another session's work to that session.

When the user answers a question your message asked by another route than the one it
offered, such as in chat, or in words where it offered a choice, use the answer. If
nothing else in the question's thread waits on them, resolve the thread, which takes
the question off On Me. Resolve a thread the same way once you see the effect of a
step you asked for, checking the effect of each step you can whenever you read the
lists, and when a question no longer applies. Where the
thread should say how it ended, such as the answer they gave in chat or what you saw,
reply there first:

```bash
leaf thread reply <page> <message> --text "<how it ended>"
leaf thread resolve <page> <message>
```

A page widget's obligation ends through its state or an authored withdrawal
(`authoring-revisions.md`).
