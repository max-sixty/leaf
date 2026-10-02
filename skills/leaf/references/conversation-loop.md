# Conversation handoff

## What the user sees

The user follows your work on the page:

| Surface | What it shows | Written by |
| --- | --- | --- |
| Banner | one sentence for the whole page: what you are doing, or what you want back | `leaf status <page> <state> "<detail>"` |
| Beside a thread or widget | **Working** and your sentence, above the message or on the control the work answers | `leaf status … --on <id>` |
| Thread | your answer to the user's message | `leaf thread reply` |
| Page | the revised content in place, and a stamp's changelog | saving `index.html`, `leaf page stamp` |

Leaf itself marks each user move **Sent**, **Queued**, and **Picked up**, including
a move that owes you nothing, such as a moved card. A pick before the Done its Ask
waits for is marked with that Done. Your host
contract may add its own current step to the banner. Chat stays in the host and never
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

Write a step's status before starting the step, and write it again whenever the user
would describe what you are doing differently: a new subject, or a new phase such as
reading, editing, testing, or waiting on a result.
Folding the write into the command that begins the step costs no extra tool call:

```bash
leaf status <page> working "running the browser suite against the new banner" && <command>
```

Name the operation and its subject in one sentence. "Working on it" tells the user
nothing the banner's dot does not already say, and `leaf status` refuses `working`
with no sentence at all.

User input comes before the work in hand, in this order:

1. Where the delivery's `acknowledge` names a receipt route, take it first, so the
   user's moves read **Picked up**; every other carrier has confirmed receipt
   already. Until you write a status, the banner can say only that you are working
   on their update.
2. Name the work each move asks for on the page before starting it. Each delivered
   event's `answering` clauses say how: for a comment, a status claim on its
   thread, with the reply carrying the result once it lands. A move that asks for
   no work, such as a question, is answered by its reply at once.
3. If the move interrupted other work, write the page status again once its own
   work is done, so the banner describes the work that continues rather than the
   last step before the interruption.

Then do the work.

## Status and handoff

Before a handoff, run:

```bash
leaf status <page> waiting "<what you want back>"
```

The detail names the concrete answer or decision, not the fact that you are
waiting. For an informational page with no concrete ask, leave it empty; the
banner then invites the user to select text to comment. Finish the turn by the
handoff route in the main skill, "Operate".

While the next move is yours the page is `working`. Name the local subject when
the detail is about one open comment thread or page widget:

```bash
leaf status <page> working "reading the reconnect traces" --on <thread-id>
leaf status <page> working "checking the rollout" --on <widget-id>
```

The claim then stands beside its subject at the page edge as well as in the
banner, so a question in hand reads differently from one nobody has looked at. A
thread claim ends with your next reply there. A widget claim survives unrelated
revisions; when a stamped version completes that work, say so on the stamp, once
per completed widget:

```bash
leaf page stamp <page> --text "…" --completes <widget-id>
```

Stamping accepts only widget ids with standing work. `status --on` refuses a
widget with neither an unsettled action receipt nor an `x-work` declaration; use
the page-wide detail when neither admits a local claim.

Use `status --on` for work on a thread or widget, whether a delivered move asked
for it or you began it yourself. It takes whatever id a delivered event's
`answering` clauses name as its address: a thread by any message in it, a page
widget, or a widget in a thread message. The delivered move then reads
**Working**.

## Long-running work

New user input reaches you only between your own operations; your host contract
names exactly when. A long foreground operation, such as a test suite or a subagent
you wait on, leaves the user's comment unanswered for its whole length.

For work that will run longer than a few minutes, coordinate it rather than perform
it. Hand the reading, editing, and testing to background subagents or background
commands, and end your turn as the host contract says, so the watcher's next delivery
reaches you while the work runs instead of waiting behind it. When a worker reports
back, put its result on the page; the thread that asked for it then gets a reply
saying what changed and linking to it.

You drive the page and your workers do not. The server, the watcher and its
acknowledgements, replies, status, edits to `index.html`, and stamps stay
with you, and a worker returns its result to you. A worker touches the page only in a
role Leaf's instructions give it, and only as those instructions direct: a command hub worker
(`leaf page instructions <page> worker`), or a Codex watcher task
(`references/codex-watcher.md`). Put this in each worker's brief, because a worker that
inherits your conversation inherits the page with it and may otherwise treat the page
as its own. Work that needs its own conversation with the user belongs to a session
of its own, with its own page.

A `working` claim is believed while the turn that wrote it is open. The page is told
when that turn ends, an interrupted one included, so a claim nothing has renewed
within a couple of minutes of the ending stops being believed: the banner reports that
your turn ended, and its explanation keeps the claim's words. A claim nobody renews at
all ages out after about a quarter of an hour. Before you end a turn while workers
run, make your last status say what is still running, and write it again in the turn
that a worker's result or the user's next comment wakes. A move whose answer a worker
is producing takes that status `--on` it: a claim written in this turn lets the turn
end before the answer, and the turn that wakes answers the move or claims it again.
Within a turn, fold your workers' progress into your own status: one sentence covering
three workers reads better than three claims competing for one row, while claims on
different subjects stand side by side at the page edge.
