# Conversation loop

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

Leaf itself marks each update **Sent**, **Queued**, and **Picked up**, including
one that owes you nothing, such as a moved card. A pick before the Done its ask
waits for is marked with that Done. Your harness
contract may add its own current step to the banner.

Readings in `leaf page state <page>` describe the user's side between their
updates. `viewed` says whether they are there: the last time a browser tab had the page
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
and follows viewport and preference changes. It creates no update, agent turn,
or automatic edit. A public website page starts observing once the user's interaction
has activated its private page. The readings are also available through the
page's authenticated `GET /api/user-view`; captured render previews record none.

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
**Working** with that line beside its thread and in the banner, and the
progress line folds into the progress disclosure when your answer arrives
([progress messages](threads.md#progress-messages)). Take any other item in hand,
such as a to-do or an action on a page widget, which has no thread, with a start:

```bash
leaf task start <page> <id> "reading the reconnect traces" && <command>
```

Take the item in hand again whenever the user would describe what you are doing
differently: a new phase such as reading, editing, testing, or waiting on a result.
Another progress message in the thread says it to the user there; a start changes
only the line, and folding it into the command that begins the step costs no extra
tool call. Name the operation and its subject in one sentence; "Working on it"
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
check the main skill's "Quick pages and records" step asks before a reply.

## Status and handoff

Before a handoff, reconcile Questions and Tasks as described below, then run:

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

A `waiting` puts down every item you
started before it, so the banner shows what you want back; a to-do stays open on
you until you end it.

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
is opened by the reply that promises it (`--todo`). A to-do on a widget survives unrelated versions, and a
version cannot drop that widget while the to-do stands.

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
after about a quarter of an hour. An update whose answer a worker is producing takes a
start while your turn runs; a start written in this turn lets the turn end before the
answer. In the turn that a worker's result or the user's next comment wakes, start
the item again or answer it. What holds the work after the turn is a to-do (below).
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
answer such a promise with this command. Wherever
the result lands, the to-do ends there: `leaf task end <page> <todo> done "<where the
result is>"`, or `failed` or `dropped` with the reason, so work that won't come back
to you takes the page and the to-do's id in its brief. While you work on it, start it,
so the banner and the thread show your line.
Work on an update that finishes inside the turn needs no to-do.

## Questions and Tasks

Everything you need from the user belongs in **Questions**, whether an answer,
decision, permission, review, or action elsewhere. Ask a direct question and register
it by one of the routes below. Prose in the page, a status line, and a question in
chat alone do not register it. A recommendation leaves its decision open. An
optional invitation to comment creates no obligation; if you need feedback before
continuing, make it an ask.

The banner's Questions count and the Questions panel show the user's queue;
**Tasks** shows yours. The user can open either list and press `q` to reach their
next item. Questions contains these requests and any failed send that needs the
user to send again. Done holds ended items.

| Request | Register it | What answers it |
| --- | --- | --- |
| A decision or input recorded by a widget | Author a decision widget (`authoring-questions.md`); optional `lf-ask` frames its question and evidence | The widget's declared answer; a multiple-choice ask also needs the user's Done |
| A conversational answer | Open an agent thread with the question, or add `--ask` to a reply (`threads.md`) | The user's next reply there or a settling reaction |
| Required version sign-off | Declare sign-off and stamp the version (`authoring-questions.md`, "Asks and sign-off") | That version's banner approval |
| An action neither route records, such as trying a build or connecting a browser | `leaf task open <page> <id> "<direct question naming the action>" --on user`, on its widget, section, or `page` | The user's Done; end it yourself when their action is established or no longer needed |

A widget ask has id `widget:<widget-id>`, a prose ask has `reply:<message-id>`,
and an approval ask for a stamped version's sign-off has `approval:v<version>`.
A to-do on the user keeps the id printed by `task open`. A thread takes no to-do
on the user; ask there with `--ask`.
Keep independently answerable decisions in separate widgets or threads. A thread
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
`queues.questions` and `queues.tasks` select those records with response obligations
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

Reconcile the lists with what you still need and owe. Zero Questions says that
you need nothing from the user **now**; Tasks may still contain your work or a wait
on an external result. Complete authorized work without asking for permission
again. A paused project needs an ask only when its disposition or resumption
needs the user's decision; after they choose to keep it paused, that decision is
settled. A blocked action belongs on the user only when they can take the step
that unblocks it. Work owned by another session stays there; ask here only for the
decision this page needs.

An answer in chat or another surface still settles the real question. Incorporate
it and retire its page ask in a revision (`authoring-revisions.md`), or end
the user's to-do with `leaf task end`. Withdraw a prose ask that no longer
applies with `leaf task end <page> reply:<message-id> dropped "<why>"`; this records
withdrawal, not a user answer. Keep finished requests out of the user's queue;
answered and withdrawn ask records remain available in the complete reading.
A page declaring required banner sign-off adds an approval ask for its stamped version automatically; its approval answers that
ask, and undo reopens it. Stamp a draft before requesting its sign-off.
