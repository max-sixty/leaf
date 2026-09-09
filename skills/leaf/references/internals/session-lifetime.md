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
| live Codex activity: session, turn, detail, event floor | optional `stream` in `status.json` | the App Server connection that starts an embedded turn, or the detached adapter's observer-only client | turn completion, connection or observer exit, loss of the wait lease, or the working grace without another event |
| turn identity and open or closed state | the page's claim record | a prompt or direct delivery opens an opaque `turn`; the Stop hook stamps `turn_closed` | the next opening mints a turn; the next closing stamps it |
| wait lease | `waiter.lock`, or `sessions/<id>.wait` for a host session | the live `leaf wait` or `leaf ack` process, held open for its life | process exit |
| acknowledgement cursor | `cursor.json` | `leaf ack`, after the complete batch reached its durable consumer | never; it is monotonic |
| pickup transition | a `pickup` event in `events.jsonl` | the carrier records `queued` when Codex accepts a batch, and the prompt hook records `opened` with session and turn identity when the queued turn opens; direct delivery records `opened` itself | never; each event/phase/session/turn transition is idempotent |
| page claim | `~/.local/state/leaf/claims/<page>` | `server start` from an agent host; released by the hook when the session exits | `released` is set, or the lifetime it rests on (the pid, or the background job's directory) is gone |
| service lifetime | `service.json` | `server start` at launch: session, or standing | `leaf server stop`; a session server also retires when no live claim holds it |
| Codex queue state | the host state home's session records | the detached adapter or an embedded App Server host | accepted and every batch receipted, then moved under `history/` |
| Codex delivery payload | the host state home's session records | the carrier freezes it before queueing or starting a turn | never; the pointer remains valid |

Delivery acceptance is a different fact from authored work, but it is exact agent
activity. Pickup never rewrites `status.json`. The server projects one interaction
per subject and unit, for the newest unsettled reader move on it (a tick and the Done
press that followed are one), on the subject's existing target margin element or a compact
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
Fresh activity from the claimed Codex task's App Server outranks that declaration
while its watcher is live. It is an observation bound to one turn and event floor,
not a second work declaration; the declaration remains underneath and becomes current
again when the turn or observer ends.

A work declaration has to be renewed, and `leaf status` renews it. `--on` names the thread
or widget the work is about, so one check-in moves the banner, the Target
margin element, and the local receipt under the reader's words; those stand until the
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
When the prompt hook opens a turn, it records a new `opened` transition for its
acknowledged, unanswered moves. A direct-delivery move that needs a reminder is
also named in the hook context. A queued Codex move needs no reminder there:
the prompt itself carries its delivery pointer, while the transition gives the
browser and the next Stop their shared handling fact.
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
delivery. Both carriers watch every page the session holds, re-reading the
set on each pass, and deliver one page's batch under a first line naming the page
and carrying the conversations its events land in.

In Codex, the adapter collects available input, then freezes the delivery before
handing its bounded `leaf-delivery` pointer to Codex's durable same-task queue.
Input collected after that boundary belongs to a later delivery. A failed or
uncertain queue call retries the same frozen pointer; a successful call marks only
that delivery accepted.
If every website startup retry fails, its deterministic fallback settles the
triggering event and removes the unaccepted queue record. The immutable payload
remains at its permanent path for a turn whose acceptance may have raced the failed
response.

Each delivery has one immutable payload and one mutable queue record. The payload
contains the exact frozen batches at the permanent path handed to Codex. The queue
record carries collecting, offering, or accepted state; after the freeze it retains
only the event identities needed for page receipts. Once a cursor advances, the
queue record records that receipt so
reinitializing the same page path cannot revive old transport work; a
reinitialized page whose events no longer match retires its old batch. The
adapter has a second lease because a generic wait lease cannot prove its output
can enter a later Codex turn. Leaf's queue
command never calls `turn/start`. While the App Server observer is connected, queueing
targets the same server as the CLI; after it disconnects, queueing returns to Codex's
durable local task queue. The observer's second connection resumes the task only to
subscribe to notifications. That subscription keeps the task loaded, so the App
Server dispatches queued input when the task is idle or its active turn completes.
The CLI remains the interactive client for every approval and user-input request.
Once every batch is receipted, only the queue record moves under `history/`; the
payload remains where the queued XML points.

An embedded host that already controls App Server can deliver the same immutable
delivery directly
with `turn/start` instead of launching the detached queue adapter. After App Server
accepts the turn, the host records the delivery against its Leaf claim turn, advances
its page cursor, holds that task's wait lease for the container host's lifetime, and
keeps the initiating connection for activity notifications. The pickup names Leaf's
claim turn, while streamed activity names App Server's task and turn; each projection
therefore reads the identity its own fold compares. A retry
therefore reads the durable pickup instead of starting the event again. A later event
creates the next delivery and resumes the same task. The resumed task's App Server
status is the turn boundary: any task that is not active closes the preceding Leaf claim
turn before the delivery opens its next one, while an active task preserves the current
Leaf claim turn because App Server treats the additional `turn/start` input as steering
for that turn. A host that owns the starting connection also observes the terminal
notification. It closes only the matching Leaf claim turn and settles the exact
accepted response obligations the model left behind; a failed or interrupted turn gets
a failure reply, while a completed turn with no reply gets an explicit empty-result
receipt. This is a
different host transport over the same page claim, event log, delivery payload, and
activity projection, not another conversation store.

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
