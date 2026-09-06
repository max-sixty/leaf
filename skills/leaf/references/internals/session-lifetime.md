# Session lifetime, pickup, and work claims

`status.json` is a declaration, not current agent state. The current state is
`activity`, one server projection over that declaration and the page's stronger
evidence: claim and turn identity, watcher lifetime, exact pickup transitions,
and unsettled reader moves. `/api/state`, neighboring-page entries, and
agent-facing page state all carry this same projection. Browser code paints it
and requests another reading at its next deadline; it does not run a second fold.

| Fact | Where | Writer | Stops being believed |
| --- | --- | --- | --- |
| work declaration: state, detail, event floor, typed `work` seats | `status.json` | `leaf status`, from the agent's turn or a delegate it hands the command to | a short grace after the turn that wrote it closes; about a quarter of an hour with no renewal; at once when the claimant's lifetime has ended |
| turn identity and open or closed state | the page's claim record | a prompt or direct delivery opens an opaque `turn`; the Stop hook stamps `turn_closed` | the next opening mints a turn; the next closing stamps it |
| wait lease | `waiter.lock`, or `sessions/<id>.wait` for a host session | the live `leaf wait` or `leaf ack` process, held open for its life | process exit |
| acknowledgement cursor | `cursor.json` | `leaf ack`, after the complete batch reached its durable consumer | never; it is monotonic |
| pickup transition | a `pickup` event in `events.jsonl` | the carrier records `queued` when Codex accepts a batch, then `opened` with session and turn identity when it enters model context; direct delivery records `opened` | never; each event/phase/session/turn transition is idempotent |
| page claim | `~/.local/state/leaf/claims/<page>` | `server start` from an agent host; released by the hook when the session exits | `released` is set, or the lifetime it rests on (the pid, or the background job's directory) is gone |
| service lifetime | `service.json` | `server start` at launch: session, or standing | `leaf server stop`; a session server also retires when no live claim holds it |
| Codex delivery epoch | the host state home's session records | the detached adapter | closed and every batch receipted, then moved under `history/` |

Delivery acceptance is a different fact from authored work, but it is exact agent
activity. Pickup never rewrites `status.json`. The server projects one interaction
per subject and unit, for the newest unsettled reader move on it (a tick and the Done
press that followed are one), on the subject's existing Target Button or a compact
local row: append is **Sent**, then **Waiting for pickup** after the short grace;
Codex acceptance is **Queued**; entry into a named open turn is **Picked up**; a
later `status … --on` claim on the same subject is **Active**. That same evidence
makes page activity **queued**, **handling**, or **picked up; turn ended**. A reply,
resolution, or authored state that honors the move settles the interaction; a later
version note settles a page action whose verb has no authored record form, and a note
already standing when the move arrives cannot answer it.

The activity fold defines precedence once. An unsettled opened interaction outranks
a `waiting` declaration, so a receipt cannot say **Picked up** while the banner says
the agent awaits the reader. A fresh `working` declaration is considered only when
its recorded event floor reaches the obligations it could describe. Turn identity,
not elapsed time, decides whether opened delivery belongs to the turn now running.

A work declaration has to be renewed, and `leaf status` renews it. `--on` names the thread
or widget the work is about, so one check-in moves the banner, the Target
Button, and the local receipt under the reader's words; those stand until the
agent's next word in that thread. Nothing in a session touches `status.json`
while its turn is over, so work handed to a delegate is renewed from the
delegate's own hands or not at all.

Canonical activity stops believing a work declaration older than the
`turn_closed` stamp after a short grace. Both turn id and closing stamp are the
session's rather than the page's: the Stop hook closes the turn on every page the
session holds, and an opening advances that same set, each page under its own
transaction. Where nothing answers for the declaration, activity reports the page
unheld rather than repeating it. Unheld is not a fault: a standing page spends most
of its life unheld and picks up again when a session takes it.

## The hook

The `hook` command, registered on Stop, UserPromptSubmit, and SessionEnd,
refuses to let a turn end with one of this session's pages unwatched, stamps
that turn's ending and the next one's opening, surfaces unacknowledged user
events at the next prompt, and releases the session's page claims when it exits.
Its unanswered-work guard reads `activity.obligations`, the same settled
interaction projection the browser reads; it does not reconstruct threads itself.
When the prompt hook carries an acknowledged, unanswered move back into model
context, it records a new `opened` transition for the new turn as well as naming
the move in the hook context. The reminder and the browser's handling state are
therefore one delivery fact.
Session death is not completion or an explicit stop: work status and desired
service stay as they were, while a session server retires once no live successor
has claimed it. Absent the host identity the environment carries, nothing is
claimed and the hooks stand down. `hooks/scripts/loop-guard.py`, which the hosts
run, decides none of that: it runs this command under `uv` and stays silent when
it cannot get an answer, so a leaf bug costs a turn nothing.

Only a page handed to a reader owes a watcher, so the unwatched clause passes
over a page carrying `preview.json`. Nothing else about that page changes: a
delivery it has not taken, or a comment nobody answered, is reported as on any
other. The guard reads the file's presence rather than the serve path's
validating reader, because it fails open by saying nothing. Unacknowledged
events are the one thing `leaf status <page> idle` cannot close over.

## Carriers

A session's leaves cost it one long-running carrier between them, separate from
the page server. Claude Code uses a sequence of direct watchers: `leaf wait`
exits to put a batch in model context, then `leaf ack` advances its cursor and
becomes the next watcher. Codex uses one detached adapter that holds the same
task-wide wait lease and stores exact batches from every page in one task-wide
delivery epoch. Both carriers watch every page the session holds, re-reading the
set on each pass, and deliver one page's batch under a first line naming the page
and carrying the conversations its events land in.

In Codex, the first batch after a turn ends hands a bounded `leaf-delivery`
pointer to Codex's durable same-task queue; input arriving before that queued
turn starts joins the same payload. While a turn is open the adapter adds input
to the current epoch and queues nothing; the prompt and Stop hooks put the pointer
in model context. A prompt that arrives before an unissued queue item consumes
it. The prompt hook has no delivery receipt, so Stop offers that input again
unless an accepted queue already carries it; `stop_hook_active` confirms the offer
on re-entry, and no newer input closes the epoch and turn. An active epoch with
input newer than its accepted queue snapshot returns to the queued-pointer path
after fifteen minutes without another hook, so a long-running turn may receive an
at-least-once retry. The Stop hook locks every owned page in stable path order
before the session delivery state, captures and acknowledges the input already
behind those locks, then keeps the turn open or marks it closed; the adapter
takes locks in the same order, so an append that reaches a page after the hook
releases it opens the next epoch. A closed stamp on any one page preserves the
boundary if Stop was interrupted mid-way.

Each epoch file is one transport authority: whether its queue was accepted, how
many batches that covered, how many the last Stop offer covered, whether the
epoch is closed, when its last input or hook transition occurred, and the batches
themselves. Once a cursor advances, its batch records that receipt so
reinitializing the same page path cannot revive old transport work; a
reinitialized page whose events no longer match retires its old batch. The
adapter has a second lease because a generic wait lease cannot prove its output
can enter a later Codex turn; the Stop hook trusts only the pair. Leaf's queue
command never resumes or starts the task; the loaded Desktop client keeps the
task writer and owns every execution or approval request.

`server start` spawns the service into a session of its own and hands back the
URL that process printed and the lifetime it recorded, so a killed carrier costs
only delivery and leaves every page up. A direct-loop recovery is one
`leaf wait`; a Codex recovery is one `leaf codex start <page>`.

## Lifetime

Whether a session's end reaches a server is decided at launch and written in
`service.json`. A serve from an agent host records the page's claim under the
state home's claims directory; a successor arriving before the session server's
final recheck keeps that process, and one arriving afterward finds the process
and lease gone and revives the still-enabled service. Neither path changes the
page's authored work status. A serve from a bare shell claims nothing, and that
is the standing serve: a long-lived dashboard someone leaves open for weeks.
`server start --standing` makes the same statement from inside a host. No daemon
is involved; a server that dies under a `leaf wait` watching an enabled page is
revived with the lifetime and exact URL in `service.json`. `leaf server stop` is
a standing server's one reaper. A session that picks the page up later owes it a
watcher while the session lives, and its claim comes and goes without changing
the standing service or the page's status.
