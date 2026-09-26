# Session lifetime, pickup, and work claims

`status.json` is a declaration, not current agent state. The current state is
`activity`, one server projection over that declaration and the page's stronger
evidence: claim and turn identity, watcher lifetime, exact pickup transitions,
and unsettled user moves. `/api/state`, neighboring-page entries, and
agent-facing page state all carry this same projection. Browser code paints it
and requests another reading at its next deadline; it does not run a second fold.

| Fact | Where | Writer | Stops being believed |
| --- | --- | --- | --- |
| work declaration: state, detail, event floor, source message, typed `work` seats | `status.json` | `leaf status`, from a turn of the session driving the page | a short grace after the turn that wrote it closes; about a quarter of an hour with no renewal; at once when the claimant's lifetime has ended |
| exact delivery handling: event, target, detail, event floor | `handling` in `status.json` | `leaf delivery claim`, derived from an immutable delivery and current page state | when the move settles, another delivered move replaces it, the claim expires, or the claimant's lifetime ends |
| live App Server activity: session, turn, typed kind, detail, event floor | optional `stream` in `status.json` | the App Server connection that starts an embedded turn, or the detached adapter's observer-only client | turn completion, connection or observer exit, loss of the wait lease, or the working grace without another event |
| live App Server reply: one displayed draft plus delivery attempt bindings by response address | optional `stream.reply` and `stream.reply_bindings` in `status.json` | an App Server connection bound to a delivery's plain reply | the displayed draft remains on failure or disconnect and is retired by a logged event naming its delivery attempt or its response address; each binding clears after durable commit or terminal failure, and survives connection and turn transitions until then |
| turn identity and open or closed state | the page's claim record | a prompt or direct delivery opens an opaque `turn`; the Stop hook stamps `turn_closed` | the next opening mints a turn; the next closing stamps it |
| the closed turn this page nudged its session in | `messaged_turn` in the page's claim record | browser-event admission, once the harness's nudge lands | a later closed turn carries a different `turn` |
| wait lease | `waiter.lock`, or `sessions/<session>.wait` for a host session | the live `leaf wait` process, held open for its life and removed when it lets go, SIGTERM and SIGHUP included | process exit |
| a host wait's start that no tool hook has named | a lock on `sessions/<session>.started` | the `leaf wait` process, taken with the session's wait lease under `sessions/<session>.started.lock` and held for its life | the `PostToolUse` hook removes the file under that same lock when it names the start, or the wait does when it ends unnamed; process exit |
| acknowledgement cursor | `cursor.json` | `leaf wait --ack`, after the complete delivery reached its durable consumer | when its seq is past the log's end, or a fresh log replaces the one it named; monotonic within one log |
| pickup transition | a `pickup` event in `events.jsonl` | an unobserved carrier records `queued` when Codex accepts a batch; whichever carrier puts the batch into a turn records `opened` with session and turn identity: a direct `leaf wait --ack` confirmation, the prompt hook re-presenting an acknowledged unanswered move, or an App Server turn start | never; each event/phase/session/turn transition is idempotent |
| page claim: session, display name, harness, carrier, lifetime | `~/.local/state/leaf/claims/<page>` | `server start` from an agent host; released by the hook when the session exits | `released` is set, or the lifetime it rests on is gone: the pid, the background job's directory, or — for a host that multiplexes every session into one process, where there is no pid to name — the page going untouched for ACTIVITY_GRACE_SECS, which a *visible* tab's `viewed.json` writes keep renewing — a backgrounded tab closes the news stream and stops renewing |
| service lifetime | `service.json` | `server start` at launch: session, or standing | `leaf server stop`; a session server also retires when no live claim holds it |
| Codex delivery record | `sessions/<session>.deliveries/` in the state home | the detached adapter or an embedded App Server host | an unaccepted record is inactive while the session owns no page; an accepted record moves under `history/` after every batch is receipted; a record, live or archived, goes at the next scan that finds its pages all gone: its own task's reading, its next archiving, or any Codex adapter's retirement, which scans every task's records and removes a directory it empties |
| Codex adapter log | `sessions/<session>.codex.log` | the detached adapter's own output, begun afresh by each `leaf codex start` | removed when the adapter retires owning no page; a run that ended any other way leaves it for the next start of that task |
| Leaf delivery | `<state-home>/deliveries/<id>.json` | any carrier freezes the host-neutral envelope before presenting it | once every page it names is gone, removed when the next delivery is frozen; until then every transport resolves the same immutable id |

Page activity describes ownership, carrier availability, and current work. Its
`kind` is `unattended`, `closed`, `unheld`, `away`, `listening`, `working`, or
`stalled`. Fresh declared or observed work makes the page working independently
of how far newer input has progressed. Delivery opened into the claimant's
current turn also proves generic activity before its first work declaration;
the receipt itself remains Picked up. The banner and Leaves tray consume this
same reading and present delivery counts separately.

`workflows` is the shared projection for exact user inputs and proactive subject
work. Each entry names its `input` event when it has one, its `thread` or `widget`
`subject`, its strongest proven `stage` (`sent`, `queued`, `picked_up`, `working`,
`replying`, or the retained terminal `answered` outcome), and any separately proven
`condition`. A Sent input that remains
unpicked after the short grace has a stale delivery condition. Ending the exact
turn that picked input up adds an ended condition without claiming interruption.
A Working claim quiet beyond its lease, or a pickup belonging to a different or
unknown old turn, has a stale work condition while retaining its durable stage.
A provisional response is Replying only on the input named by its `responds`
address. Disconnect, interruption, and failure require the response's own state.
Successful settlement removes the workflow; the logged answer remains its evidence.
For an interrupted or failed response, the workflow's `response` names the exact
delivery attempt when one exists. A durable failure receipt also names its reply
event id. Browser notices read this current workflow condition and source identity:
an old failure does not become fresh news after a later successful answer, and
stale work or delivery evidence is not a response failure.

Ordinary durable stale, ended, interrupted, and failed observations prove uncertainty
or a stopped operation but no concrete user recovery gesture, so they remain
agent-owned. A terminal host failure is the exception, whatever the move's answer:
`workflows.py` names the record each answer takes, and each hands recovery to the
user. It settles the Stop obligation; a failed request receipt ends the request
outright, while a failure reply or a failed pickup retains an `answered` workflow with
a failed response condition until the user moves again. A local
send refusal similarly has a browser-owned Retry gesture; that unresolved overlay may
put the thread in Needs you without persisting another workflow record.

A workflow's `stage` and its `answer` are separate readings. The stage reports
delivery for every move the user has handed over; the answer, which `workflows.py`
states, is what the agent owes it: a reply, a version for a thread that asked
for one, a version whose markup records a user's answer to a page Ask, a request's
receipt, or null. Every owed answer blocks the Stop hook and `leaf status idle` once
its move is acknowledged, and only owed answers enter activity counts. A widget move
that answers no Ask, such as a draft edit or a moved card, owes nothing: its workflow
reports delivery until its document takes it in — for a page action, until the markup
records the move or a later version supersedes it; for a move in frozen thread markup,
until the agent's next spoken turn in that thread, or a resolution that closes the
thread after it. It does not make its thread the agent's turn.
A move the user has not finished — a pick before the Done its Ask declares — has
not been handed over and has no workflow. Consecutive user turns form one response batch
addressed by its newest input. Before settlement each input retains a workflow,
while only the newest carries the thread's `answer` and enters the Stop obligation
list. A response to an older input removes that input and leaves the newer
obligation. A response to the newest settles the batch. Widget Asks remain
independent and settle through their declared state. Pickup never rewrites `status.json` or makes the page itself Picked up. A
resolution or authored state that honors a move also settles it; a later version
note settles a page action whose verb has no authored record form. A note already
standing when the move arrives cannot answer it. Turn identity decides whether
a receipt belongs to the open turn; ending a turn does not settle its input.
A delivery's completed final answer retains the exact delivered `responds` address,
even when a resolution, the user's ✓, or authored state settled that move during
the turn. Its substantive reply reopens the thread under the ordinary thread
rule in `events.md`, so the answer returns to Open Threads without making the
answered move owed again. Failure receipts are omitted once their move is settled.

The App Server observer retains typed `working`, `thinking`, `tool`, `replying`,
`awaiting_approval`, and `awaiting_input` activity with the observed session and
provider turn. These are observations of the page's agent, not claims on every
message. Missing subtype evidence means generic Working. A tool invocation is
not an independently tracked background job, and neither an old observation nor
a disconnected carrier proves a job failed.

A current authored work declaration keeps the page's sentence and date. The
observed step remains separately available as `observed` and `observed_kind`;
where the declaration has no authored sentence, the observation supplies it.
Only current observed work supplies a live subtype. Delivery floors and exact
response bindings continue to govern local workflows and settlement, without
making newer input erase overall page work. A page-wide observation alone never
refines a message workflow. Thinking and tool activity stay page-wide until a host
provides an explicit input or subject binding; the current host contract does not.

A work declaration has to be renewed, and `leaf status` renews it. `--on` names the thread
or widget the work is about. `leaf delivery claim` instead records one event from an
immutable delivery after checking under the page lock that the exact move remains
outstanding; it never transfers a claim to newer input on the same subject. A thread
claim also records the current unanswered message, so one check-in keeps **Working**
beside the words that prompted the work even when the user adds another comment.
Nothing in a session touches `status.json` while its turn is over, and its workers
leave the page to it, so a declaration over work that outlasts the turn stands
unrenewed until a later turn writes it again.

The turn id and `turn_closed` stamp a declaration is judged against are the
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
Registered on Claude Code's `PostToolUse` too, it names a wait that a background
command started, read off the wait's start mark rather than the command.
Its unanswered-work guard reads `activity.obligations`, selected from the same
`workflows` projection the browser reads; it does not reconstruct threads
itself. The App Server adapter presents at most one thread reply in each turn's
chronological delivery slice, frozen as a `turn` answer; once the turn binds it, its
workflow's `answer` reads `turn` too. Its completed final-answer item finishes that
exact response; the hook lets the provider turn close, and the observer commits the
same text through the canonical reply writer when the terminal notification arrives.
When the prompt hook opens a turn, it records a new `opened` transition for its
acknowledged, unanswered moves. A plugin-free embedded host records the same
transition from the queued turn's App Server `turn/started` notification. A
direct-delivery move that needs a reminder is also named in the hook context. A
queued Codex move needs no reminder there: the prompt itself carries its delivery
pointer, while the transition gives the browser and the next Stop their shared
handling fact.
Session death is not completion or an explicit stop: work status and desired
service stay as they were. Absent the harness the environment implies, nothing is
claimed and the hooks stand down. `hooks/scripts/loop-guard.py`, which the hosts
run, decides none of that: it runs this command under `uv` and stays silent when
it cannot get an answer, so a leaf bug costs a turn nothing.

Only a page handed to a user owes a watcher, so the unwatched clause passes
over a page carrying `preview.json`, which only a checkout's `scripts/preview.py`
writes; nothing else about that page changes. The guard reads the file's presence
rather than the serve path's validating reader, because it fails open by saying
nothing.

## Carriers

A session's leaves cost it one long-running carrier between them, separate from
the page server. The claim names the harness, and a reader elsewhere rebuilds its
declaration from that name and asks it what proves the carrier live and what to
say when it is not, rather than comparing the name itself. There are three
shapes:

- A sequence of direct watchers the model itself runs, which Claude Code uses:
  `leaf wait` exits to put a batch in model context, then `leaf wait --ack <delivery-id>` advances
  the captured cursors and becomes the next watcher.
- One detached process, which a Codex task uses on either transport: it holds the same task-wide wait lease
  plus an adapter lease of its own, and stores exact batches from every page in
  one task-wide delivery.
- A host that drives App Server itself, which the website's per-user container
  uses: it starts the turn directly and needs nothing between them.

Every carrier watches every page the session holds, re-reading the set on each
pass, and produces the same envelope (`../../references/event-batches.md`, "One envelope
on every transport").

A `wait` carrier is the one that stops while its session lives on, because the Stop
hook fails open on a repeated stop or the wait is stopped after the turn ends. Input
that reaches the page after that has no carrier, so browser-event admission asks the
claimant's harness for its nudge — the way to reach a session with nothing watching,
which only a `wait` harness has. Claude Code's is the Unix socket it binds for each
session, found by session id in Claude Code's session registry
(`message_claude_code_session`). It sends when an
event is appended to a page whose turn is
closed and whose session holds no wait lease. A running turn is excluded because
its Stop hook already refuses to end with the input unpicked, and a delivering wait
and the prompt hook both reopen the turn. Each page messages its session once per
closed turn: when a socket takes the message, the claim records the turn as
`messaged_turn`, and an opening mints a new turn id, so later input in the same
closed turn sends nothing more, while input after a send no socket took tries again.
Input that arrived before a repeated Stop let the turn end gets no message, because
the blocked Stop already reported it and a message would reopen the turn the hook
just let end.

The message names the page and tells the agent to start an unnamed `leaf wait`,
which remains the one delivery path. Claude Code 2.1.274 fires UserPromptSubmit for
a delivered message, so the prompt hook reopens the turn and lists the input as it
would for a typed prompt. Delivery is the recipient's decision, and nothing reports
it back. A session that bypasses permissions holds the message behind an approval
dialog unless its user set `crossSessionInbound` to `accept`. A background job whose
worker has retired has no socket to reach. A turn nobody closed is never messaged
either: Stop does not fire on an interrupted turn (measured), so that page waits for
the session's next close. An `adapter` or `embedded` carrier declares no nudge and
needs none: its process queues or starts turns itself, and if that process is gone
so is the session it served.

In Codex, on either transport, the adapter collects available input, then freezes the delivery. Input
collected after that boundary belongs to a later delivery. Without an App Server
observer, it hands the bounded id-only `leaf-delivery` pointer to Codex's durable
same-task queue. A failed or uncertain queue call retries the same frozen pointer while
the session owns a page. With an observer, as with the embedded host below, Leaf
retains the frozen delivery in its own offering state until the task is idle, then
starts it directly; neither steers page input into the running turn nor copies the
delivery into App Server's queue. Losing the session's final page leaves the
collecting or offering record standing but inactive until the same session claims a
page again. Acceptance has crossed the external-effect boundary, so its remaining page
receipts are reconciled before the adapter checks ownership and retires.
If every website startup retry fails, its deterministic fallback settles the
triggering event and removes the unaccepted delivery record. The immutable payload
remains at its permanent path for a turn whose acceptance may have raced the failed
response.

Each delivery has one globally addressed immutable envelope and one mutable delivery
record. The record carries collecting, offering, or accepted state;
after the freeze it retains only the event identities needed for page receipts.
Once a cursor advances, the
delivery record keeps that receipt so
reinitializing the same page path cannot revive old transport work; a
reinitialized page whose events no longer match retires its old batch. The
adapter has a second lease because a generic wait lease cannot prove its output can
enter a later Codex turn. Leaf's unobserved queue command never calls `turn/start`.
With an App Server the adapter holds two connections instead. One observes: it resumes
the task, keeps the subscription that resume opens, and projects the turns Leaf did not
start — the user's own work in the terminal, and a queued pointer the task picks up by
itself. It binds a reply only to a delivery frozen for App Server: a queued pointer's
delivery owes a plain `reply`, which its agent writes with `leaf thread reply`. The other belongs to one delivery for one turn: it resumes, reads the task's
status, starts the turn while the task is idle, and follows that turn to its reply on
the connection it started it on. Two connections may resume one thread and both then
receive everything it says, so the observer passes over a delivery this process is
carrying rather than answering for it a second time. The CLI remains the interactive
client for every approval and user-input request.
Once every batch is acknowledged, only the delivery record moves under `history/`;
`leaf delivery read <id>` continues to resolve the immutable envelope.

An embedded host that already controls App Server can deliver the same immutable
envelope directly with `turn/start` when the task is idle. After App Server accepts
the turn, the host records the delivery against its Leaf claim turn, advances its
page cursor, holds that task's wait lease for the container host's lifetime, and
keeps the initiating connection for activity notifications. The pickup names
Leaf's claim turn, while streamed activity names App Server's task and turn; each
projection reads the identity its own fold compares. A retry reads the durable
pickup instead of starting the event again. Its subscription spans the active turn,
the delivery turn's opening, and that turn's terminal notification, recording both
`opened` and the exact turn close. A host
that owns a starting connection closes only the matching Leaf claim turn on its
terminal notification. A direct start binds from its own answer. The request carries
the delivery id as its client message id, and App Server answers with the turn it made
from it, so the starter knows its turn before reading a notification. The structured
delivery also stays in the transcript, which is how a client that did not start a turn
recovers the same binding — one resuming a task after the fact, or reading the turn the
task opened for a queued pointer. A lost subscription is not one of those cases:
losing the starting connection ends the turn rather than opening a gap to read across.
Reply binding is the hook's contract above and, for the agent,
`../../references/host-codex-app-server.md`, "Replies". This is another carrier over
the same delivery, page claim, event log, and activity projection, not another
thread store or response policy.

`server start` spawns the service into a session of its own and hands back the
URL that process announced and the lifetime it recorded, so a killed carrier costs
only delivery and leaves every page up. `leaf codex start` spawns its adapter the
same way. Both go through `detached`, whose handshake makes the caller's commit the
end of a start: the child announces, and the caller acknowledges as the last thing
it does. A child whose caller leaves before acknowledging withdraws — a service
disables the record it wrote, an adapter releases its leases — since the caller's
cleanup may already have run: a stop that found nothing to stop, or the claim the
start took given back. That claim is `service.starting_claim`, the one transition
`server start`, `server run`, a `--user` preview's first start, and `leaf codex
start` take, and it is restored only if no successor has replaced it.

## Lifetime

Whether a session's end reaches a server is decided at launch and written in
`service.json`; which lifetime a serve chooses, and what each asks of the agent, is
`../../references/serving-pages.md`, "Page lifetime". A serve from an agent host
records the page's claim under the state home's claims directory; a successor arriving
before the session server's final recheck keeps that process, and one arriving
afterward finds the process and lease gone and revives the still-enabled service.
Neither path changes the page's authored work status. A serve from a bare shell claims
nothing, and a claim on a standing page comes and goes without changing its service.
A `leaf wait` watches each live page its session claims whatever its server is
doing, and ends only when those pages go idle or change hands. It revives an
enabled service whose process has died, once per death, and says on stderr whether
the server came back; one that did not stays watched, and a later `server start`
serves it again. A disabled service it leaves alone and goes on watching, since a
stop is the agent's own move: `page init` stops and restarts a served page's
server around a re-vendor, and the wait carries on through the gap.
