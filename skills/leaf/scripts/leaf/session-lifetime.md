# Session lifetime, pickup, and work claims

`status.json` is a declaration, not current agent state. The current state is
`activity`, one server projection over that declaration and the page's stronger
evidence: claim and turn identity, watcher lifetime, exact pickup transitions,
and unsettled user moves. `/api/state` and agent-facing page state carry this
same projection. A neighboring-page entry carries the serving page's own compact
canonical publication (`server_rows.py`), read alongside its server lease. Browser code
paints it and requests another reading at its next deadline; it does not run a
second fold.

| Fact | Where | Writer | Stops being believed |
| --- | --- | --- | --- |
| work declaration: state, detail, event floor, source message, typed `work` seats, each naming the claimant turn that wrote it, or none for another session's | `status.json` | `leaf status`, from a turn of the session driving the page | a short grace after the turn that wrote it closes; about a quarter of an hour with no renewal; at once when the claimant's lifetime has ended |
| live App Server activity: session, turn, typed kind, detail, event floor | optional `stream` in `status.json` | the App Server connection that starts an embedded turn, or the detached adapter's task connection | turn completion, connection or observer exit, loss of the wait lease, or the working grace without another event |
| live App Server reply: one displayed draft plus delivery attempt bindings by response address | optional `stream.reply` and `stream.reply_bindings` in `status.json` | an App Server connection bound to a delivery's plain reply | the displayed draft remains on failure or disconnect and is retired by a logged event naming its delivery attempt or its response address; each binding names the claim turn it belongs to (the delivery's turn once its reply opens, the turn standing at reservation before then), clears after durable commit or terminal failure, and survives a lost connection; it stands only while that is still the claim's turn and the turn is open (`activity.reply_binding_stands`), and a turn's answer committed after its binding lapsed yields to a reply another writer already gave |
| turn identity, when it last opened or took a prompt, and open or closed state | the session lifecycle record | a prompt, a direct delivery, or a carrier following a provider turn opens `turn` and stamps `turn_opened`, or renews that stamp on a turn still open; the id is the host's where it names one (Codex's hooks and App Server name the same turn) and one Leaf mints otherwise; the Stop hook stamps `turn_closed` on whatever turn is open, and a carrier on the turn it follows | the next opening of another id; the next closing stamps it, and a closed id never reopens |
| the host's own word on the claimant's session: `idle`, `waiting` on a dialog, or `busy`, dated by its last change | the host's record, read at each state read (`Harness.live_turn`): for Claude Code, the `status` of the session's newest registry record whose process runs | the host | read live, so it moves with the host; absent where the host publishes nothing, as for a background job whose worker has retired |
| the turn ending this page nudged its session after | `messaged_ending` in the page's claim record: the turn id and its close stamp, or for an interrupted turn its last opening | browser-event admission, once the harness's nudge lands | a later ending, a close under a new id or an interrupt after a new prompt renewed the same one, differs |
| wait lease | `waiter.lock`, or `sessions/<session>.wait` for a host session | the live `leaf wait` process, or Claude Code's background Stop hook watching between turns (`leaf hook --watch`), holding an exclusive kernel lock on a stable file; file existence does not prove liveness | descriptor close or process exit, including a crash |
| the host runs Leaf's hooks for this session | `sessions/<session>.hooks` | every Leaf hook the host runs for the session | removed by its SessionEnd hook |
| acknowledgement cursor | `cursor.json` | whichever carrier confirms the complete delivery reached its durable consumer: the reader of a complete Claude Code hook delivery via `leaf delivery ack`, `leaf wait --ack` after a printed one, or the Codex adapter | when its seq is past the log's end, or a fresh log replaces the one it named; monotonic within one log |
| pickup transition | a `pickup` event in `events.jsonl` | an unobserved carrier records `queued` when Codex accepts a batch; whichever carrier puts the batch into a turn records `opened` with session and turn identity: a direct `leaf wait --ack` confirmation, the reader confirming a complete Claude Code hook delivery, the prompt hook re-presenting an acknowledged unanswered move, or an App Server turn start | never; each event/phase/session/turn transition is idempotent |
| page claim: unique acquisition, session generation, display name, harness, page freshness | `~/.local/state/leaf/claims/<page>` | `server start` from an agent host; references the session lifetime publication | `released` is set, the referenced generation ended or was replaced, or the shared host lifetime is gone: the pid, the background job's directory, or — for a host that multiplexes every session into one process, where there is no pid to name — the page going untouched for ACTIVITY_GRACE_SECS, which a *visible* tab's `viewed.json` writes keep renewing — a backgrounded tab stops its freshness reads and stops renewing |
| service lifetime | `service.json` | `server start` at launch: session, or standing | `leaf server stop`; a session server also retires when no live claim holds it |
| Codex delivery record | `sessions/<session>.deliveries/` in the state home | the detached adapter or an embedded App Server host | an unaccepted record is inactive while the session owns no page; an accepted record moves under `history/` after every batch is receipted; a record, live or archived, goes at the next scan that finds its pages all gone: its own task's reading, its next archiving, or any Codex adapter's retirement, which scans every task's records and removes a directory it empties |
| Codex adapter log | `sessions/<session>.codex.log` | the detached adapter's own output, begun afresh when serving or `leaf codex start` starts a new adapter | removed when the adapter retires owning no page; a run that ended any other way leaves it for the next start of that task |
| Leaf delivery | `<state-home>/deliveries/<id>.json` | any carrier freezes the host-neutral envelope before presenting it | once every page it names is gone, removed when the next delivery is frozen; until then every transport resolves the same immutable id |

Page activity describes ownership, carrier availability, and current work. Its
`kind` is `closed`, `unheld`, `away`, `listening`, `working`, or `stalled`. Every
rule in the fold that asks whether the claimant's turn is running reads one answer,
`activity.claimant_turn`, which dates each piece of evidence and lets the newest
decide. The session's turn stamps are believed open only while the opening, a status
written during the turn, or the claimant's streamed activity renewed them within the
working grace. The host's record adds the two things no hook sees, each only when
newer than what it contradicts: an `idle` newer than every renewal ends the open
turn (an interrupt), and a `waiting` newer than the stamps is a dialog open now,
observed as `awaiting_user` since the record does not say whether it asks for
approval or an answer. Its `busy` is never read, since a background job's record
keeps it across turn endings. Browser-event admission reads the same turn before it
nudges a session (`presence.claimant_reading`), and nudges only after an ending
something saw: a turn Leaf merely stopped believing in may still be running a long
step. The claimant takes input while its wait lease is held or, for a harness whose
hooks carry input, while its turn runs. Fresh declared or observed work makes the
page working independently of how far newer input has progressed; a host-observed
wait on the user in its own window (an approval, a question) is observed work that
stands for as long as its observer does. Delivery opened into the claimant's running
turn also proves generic activity before its first work declaration; the receipt
itself remains Picked up. `counts.overdue` counts the owed moves that stalled with
the agent to act, still Sent past the pickup grace or left by a turn that ended or
was interrupted before answering; over an `away` page they are when the banner asks
the user to nudge the session. The banner consumes this same reading and presents
delivery counts separately; the Leaves drawer consumes each serving page's own
canonical publication.

`workflows` is the shared projection for exact user inputs and proactive subject
work. Each entry names its `input` event when it has one, its `thread` or `widget`
`subject`, its strongest proven `stage` (`sent`, `queued`, `picked_up`, `working`,
`replying`, or the retained terminal `answered` outcome), and any separately proven
`condition`. The served list also names the `thread` each workflow stands in (null for
a page widget) and whether it `holds_thread` the agent's turn, and lists the strongest
first (`served_state.browser.served_workflows`): a surface that shows one workflow of
several shows the first, and the browser places only its own unresolved sends
against that order. A Sent input that remains
unpicked after the short grace has a stale delivery condition. A pickup whose
exact turn was seen to end, by its close or by the host's record, has an ended
condition without claiming interruption. A Working claim quiet beyond its lease,
or a pickup belonging to a different or older turn or to one nothing has renewed
within the working grace, has a stale work condition while retaining its durable
stage.
A provisional response is Replying only on the input named by its `responds`
address. Disconnect, interruption, and failure require the response's own state,
and a turn that completed without a final answer (`partial`) reads ended.
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
user. It settles the Stop obligation; a failure reply or a failed pickup retains an
`answered` workflow with a failed response condition until the user moves again. A local
send refusal similarly has a browser-owned Retry gesture; that unresolved overlay may
put the thread in Needs you without persisting another workflow record.

A workflow's `stage` and its `answer` are separate readings. The stage reports
delivery for every move the user has handed over; the answer, which `workflows.py`
states, is what the agent owes it: a reply, a version for a thread that asked
for one, a version whose markup records a user's answer to a page Ask, or null. Only owed answers enter activity counts. `leaf status idle`
refuses over one set of them, `activity.blocking_obligations`: the acknowledged
moves nothing else is set to answer. A move still `queued` is answered by the
later turn that opens it, and a `turn` answer the open turn has finished is
committed by the claimant's carrier while that carrier is live. The Stop hook holds
the claimant's turn over those the turn has not claimed as work, which
`activity.turn_obligations` selects. A standing claim over the move, one naming it,
on its widget, or on the thread that holds it, that the open turn wrote since the
move's pickup is the agent's answer for now, and the turn may end over it while
background workers carry the work. The claim does not carry into the next turn, which
answers the move or claims it again. A widget move
that answers no Ask, such as a draft edit or a moved card, owes nothing: its workflow
reports delivery until its document takes it in — for a page action, until the markup
records the move or a later version supersedes it; for a move in frozen thread markup,
until the agent's next spoken turn in that thread, or a resolution that closes the
thread after it. It does not make its thread the agent's turn.
A move the user has not finished — a pick before the Done its Ask declares — has
not been handed over and has no workflow. Consecutive user turns form one response batch
addressed by its newest input. Before settlement each input retains a workflow,
while only the newest carries the thread's `answer` and enters the obligation
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
or widget the work is about, and is how a delivered move reads **Working**. A thread
claim also records an input the thread holds, a message or a move on a widget in one
of its messages: the one a standing claim there already names while the thread still
holds it, and the newest otherwise. So one check-in keeps **Working** beside the input
that prompted the work even when the user adds another comment, while renewing it
after the user supersedes a move puts Working on the move that replaced it.
Nothing in a session touches `status.json` while its turn is over, and its workers
leave the page to it, so a declaration over work that outlasts the turn stands
unrenewed until a later turn writes it again. What holds such work across turns is
a task in the log (`tasks.py`), which no turn or session ending lapses.

The turn id and `turn_closed` stamp a declaration is judged against are the
session's rather than the page's: prompts and endings publish one atomic session
record. Page claims reference its generation and derive the current turn; no
opening or ending rewrites claims. Each acquisition has its own unique ID, so
rollback compares claim publication rather than derived lifecycle fields or
second-resolution timestamps. The first observed host lifetime may enrich an
unknown prompt-created lifetime; replacing known provenance starts a generation.
SessionEnd marks the generation ended without
page discovery or page locks. A resumed host ID gets a new generation, leaving
old claims inactive. Activity-backed ownership freshness remains per page: one
visible sibling does not renew every page in a multiplexed host. Where nothing answers for the declaration, activity reports the page
unheld rather than repeating it. Unheld is not a fault: a standing page spends most
of its life unheld and picks up again when a session takes it.

## The hook

The `hook` command, registered on Stop, UserPromptSubmit, SessionEnd, and Codex's
PostToolUse and Interrupt, keeps a turn from ending while it leaves one of this session's pages unwatched
(a page whose carrier is a process of its own; Claude Code's watch is its next
Stop hook)
or a delivered move unanswered and unclaimed, stamps that turn's ending and the
next one's opening, surfaces unacknowledged user events at the next prompt, and
releases the session's page claims when it exits. The Stop hook keeps a turn
going through the host's continuation channel (`Harness.continue_turn`): Claude
Code's non-error `additionalContext`, or a block where, as in Codex, the host's
Stop output has nothing else. It continues a turn only for what the turn owes: input
arriving as it ends that is owed an answer, which it hands over, or a debt above.
Input that owes nothing, such as a resolve, a report or a page error, waits for the
watcher and rides along when the turn goes on anyway. A repeated Stop
(`stop_hook_active`) has named its debts once and lets the turn end; only newly
arrived owed input continues it again.
A second Stop registration, gated on `$CLAUDECODE`, runs `hook --watch`, which
Claude Code keeps in the background (`asyncRewake`) as the session's watch between
turns (`session.watch_between_turns`): its exit 2 wakes the session with its
stderr, and every other ending is silent.
Its unanswered-work guard reads `activity.turn_obligations` over the page's
activity, selected from the same `workflows` projection the browser reads; it does not reconstruct threads
itself. The hook planner reads each page once under its transaction, including
ownership, log, cursor, status and the full served projection. Its typed input,
response debt and carrier facts feed Stop policy before host formatting; prompt
pickup is an explicit transition and rechecks that debt remains unsettled.
Every hook effect checks its captured session generation and revision, including
no-ID and same-ID prompt renewal. The complete context is published and flushed
under that epoch guard. Hook stdout cannot prove receipt, since a host timeout
discards it. Every hook envelope names `leaf delivery ack`; its reader confirms
only once every batch is in context. Receipt then revalidates current ownership
and exact event identities under page→session locks held through pickup and
cursor commit. Receipt observes an open turn and cannot open or replace one. Input stays pending if
context is lost, whether the envelope was inline or a large pointer. Provider callbacks
can only bind an unknown turn or match the known one; an App Server start result
introduces a new identity only by comparing the epoch captured before its request.
The subscribed observer captures its epoch before resume and advances that token
only with accepted messages and matching completion for its current provider turn.
Ordered starts adopt against this token before running identity or fold selection.
A resume response uses its pre-request token even when newer notifications arrived
during that request; a rejected stale snapshot never marks the observer running.
Historical delivery completion settles its immutable answer without adopting a
current lifecycle identity. The shared start boundary returns its admitted
publication to both carriers, and their folds retain that generation and provider ID
through construction, activity and cleanup. Live projection requires an exact
current publication with an open matching turn under page→session locks; cleanup
uses the matching publication after closure. A resumed new generation replaces
an older live fold instead of borrowing it.
Codex's synchronous prompt hook records the provider turn even before a
page is claimed. Its asynchronous PostToolUse hook identifies an unknown session-scoped turn
once, or renews only the already observed running provider turn and offers one immutable pointer between steps. The observation's
revision advances on a prompt, ending, or tool step: the queue rechecks it under
the same delivery lock before reserving its route, so even a renewed step within
the same turn invalidates an idle reading taken before it. Completing the hook does not prove
the model read its output: `delivery read` in the owning task takes receipt and
records opened pickup. Hook reads, App Server entry, and durable queue acceptance
all use `codex.accept_codex_delivery` against the exact delivery id. It persists
acceptance before page IO; normal receipt and interrupted-acceptance recovery use
`codex.finish_codex_batch`, which never opens a turn. Stop or Interrupt closes the
observed turn, including a
page acquired before its first tool hook. Stale provider callbacks are rejected
before planning or printing context, and a newer prompt protects its generation
and turn.
The App Server adapter presents at most one thread reply in each turn's
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
claimed and the hooks stand down. Turn hooks call `bin/leaf hook`; that shell
launcher runs the application through `uv`, which supplies the supported
interpreter and dependencies. The application entry routes the hook to its
lightweight owner before importing the CLI or page reading. It marks the session
and records Codex provider turns even before a page is acquired. It reads active
ownership through `service.owned_pages`; a session holding no page avoids the
delivery and page-reading stacks.

SessionEnd calls the launcher's `session-end` entry, which runs its standalone
stdlib state owner directly. That program supports Python 3.9 and publishes
one ended session generation. Every claim referencing it becomes inactive without
page discovery, page locks or claim rewrites, including claims made by another
checkout when this plugin has no uv environment.
Managed Leaf delegates SessionEnd to the same owner. Registrations suppress errors
and return success when the application cannot answer. The host owns their
deadlines. `hooks/scripts/loop-guard.py` supervises the background watch, calling
the launcher and converting its successful result into Claude Code's exit-2 wake.

Only a page handed to a user owes a watcher, so the unwatched clause passes
over a page carrying `preview.json`, which only a checkout's `leaf-dev preview`
writes; nothing else about that page changes. The guard reads the file's presence
rather than the serve path's validating reader, because it fails open by saying
nothing.

## Carriers

A session's leaves cost it one long-running carrier between them, separate from
the page server. The claim names the harness, and a reader elsewhere rebuilds its
declaration from that name and asks it what proves the carrier live and what to
say when it is not, rather than comparing the name itself. There are three
shapes:

- Under Claude Code, Leaf's own Stop hook. Claude Code starts it in the
  background as each turn ends and wakes the session when it exits 2
  (`Harness.watches_between_turns`), and the model starts no watcher. It holds the
  session's wait lease until a page has input, exits 2 to wake the session, and the
  prompt hook of the turn the wake opens or reaches puts the batch in that turn's
  context; its reader acknowledges the complete envelope before work. Input that was already pending as the turn
  ended is the other Stop hook's to hand to the turn it continues, so the watch
  carries it only once that hook lets the turn end over it. Claude Code bounds a
  background command at two hours and a hook only at its own `timeout`, which is
  why the watch is a hook. Plain `--print` runs the hook in the foreground,
  holding the turn, so there it watches nothing.
- A sequence of direct watchers the model itself runs, where the wait prints the
  batch (a Codex task's own loop, a bare shell, a Claude Code session under plain
  `--print`): `leaf wait --ack <delivery-id>` advances the captured cursors and
  becomes the next watcher.
- One detached process, which a Codex task uses on either transport: it holds the same task-wide wait lease
  plus an adapter lease of its own, and stores exact batches from every page in
  one task-wide delivery.
- A host that drives App Server itself, which the website's per-user container
  uses: it starts the turn directly and needs nothing between them.

Every carrier watches every page the session holds, re-reading the set on each
pass, and produces the same envelope (`../../references/event-batches.md`, "One envelope
on every transport").

A carrier the session's own turns start is the one that stops while its session
lives on: a turn interrupted without its Stop hooks starts no watch, a watch fails
open or reaches its hook's timeout, or a model-run wait is stopped after the turn
ends. Input that reaches the page after that has no carrier, so browser-event
admission asks the claimant's harness for its nudge — the way to reach a session
with nothing watching, which only such a harness has. Claude Code's is the Unix socket it binds for each
session, found by session id in Claude Code's session registry
(`message_claude_code_session`). It sends when an event is appended to a page whose
claimant takes no input by the activity fold's reading: no wait lease, and no
running turn, an interrupted one read as ended. A running turn is excluded because
its Stop hook already refuses to end with the input unpicked, and a waking watch
and the prompt hook both reopen the turn. Each page messages its session once per
ending of a turn: when a socket takes the message, the claim records that ending as
`messaged_ending`, so later input after the same ending sends nothing more, a later
ending sends again, and input after a send no socket took tries again. Input that
arrived before a repeated Stop let the turn end gets no message, because the blocked
Stop already reported it and a message would reopen the turn the hook just let end.

The message names the page, and the input arrives with it: Claude Code 2.1.274 fires UserPromptSubmit for
a delivered message, so the prompt hook reopens the turn and lists the input as it
would for a typed prompt, and that turn's ending starts the watch again. Delivery
is the recipient's decision, and nothing reports
it back. A session that bypasses permissions holds the message behind an approval
dialog unless its user set `crossSessionInbound` to `accept`. A background job's
daemon retires an idle job's worker after about an hour, with its socket and the
Stop hook's watch, which ends once its host process is gone
(`Harness.host_runs`). Such a job is resumed instead: `claude --bg --resume` runs
the message as the job's next prompt on a fresh worker (`resume_claude_code_job`),
which a job a live worker hosts is spared, since the command would start a copy.
The command is started rather than awaited, since the turn it starts takes the
page's lock in its prompt hook, so the ending is marked messaged once it starts. Stop does not fire on an interrupted turn
(measured), so an interrupted turn is messaged once the session's registry record
reads `idle`; with no record, not until a Stop closes a later turn. An `adapter` or
`embedded` carrier declares no nudge and needs none: its process queues or starts
turns itself, and if that process is gone so is the session it served.

In Codex, the adapter and tool hook collect available input into the same delivery
records under the session's delivery lock. Capture excludes events already in any
standing record, including an offer whose transport has not yet accepted it.
While a proven tool hook can reach the running claimant turn, the queue adapter
holds input for that hook. The hook freezes a plain-reply envelope and records
its offer's exact turn; another hook does not repeat that pointer or take an offer
another transport owns. Reading the pointer in the task reserves acceptance before
taking page receipts. The adapter reconciles interrupted receipts the same way as
every accepted delivery. An unread hook offer takes the idle queue once Stop or
Interrupt closes the turn, or the canonical activity reading stops believing it.
Input collected after the freeze belongs to a later delivery. Without an App Server
observer, it hands the bounded id-only `leaf-delivery` pointer to Codex's durable
same-task queue. A failed or uncertain queue call retries the same frozen pointer while
the session owns a page. With an observer, as with the embedded host below, Leaf
retains the frozen delivery in its own offering state until the task is idle, then
starts it directly; tool-hook delivery during work remains a plain reply, while
an idle App Server delivery binds the final message. Losing the session's final page leaves the
collecting or offering record standing but inactive until the same session claims a
page again. Acceptance has crossed the external-effect boundary, so its remaining page
receipts are reconciled before the adapter checks ownership and retires.
If every website startup retry fails, its deterministic fallback settles the
triggering event and removes the unaccepted delivery record. The immutable payload
remains at its permanent path for a turn whose acceptance may have raced the failed
response.

Each delivery has one globally addressed immutable envelope and one mutable delivery
record. The record carries collecting, offering, accepted, or abandoned state;
after the freeze it retains only the event identities needed for page receipts.
Once a cursor advances, the
delivery record keeps that receipt so
reinitializing the same page path cannot revive old transport work; a
reinitialized page whose events no longer match retires its old batch. The
adapter has a second lease because a generic wait lease cannot prove its output can
enter a later Codex turn. Leaf's unobserved queue command never calls `turn/start`.
With an App Server the adapter's `TaskConnection` owns one subscribed connection.
Its receiver serializes delivery starts beside incoming notifications and routes
every provider turn to one `TurnFold`, whether the user or Leaf started it. A start
first resumes the task for fresh idle evidence; cached activity only holds an offer
back. Its reply binds before buffered notifications are replayed, including a
completion that arrived before the start response. Queue deliveries still owe plain
replies; App Server deliveries bind the turn's final message. The interactive client
continues to handle approvals and user-input requests.

The delivery record marks `starting` before a start request is sent. If its response
is lost, the offer is never blindly sent again, including after adapter restart or
when no streamed reply seat exists. Resuming reconciles the exact delivery identity
in the provider transcript. Losing the subscription disconnects its reply and clears
live activity without inventing an ending or releasing a running turn's reservation.
A later provider completion settles it; a later session turn withdraws the old reply
binding, so an explicit reply wins over a recovered final message. An uncertain start
is never blindly repeated. Recovery exhausts full, paginated provider history;
summary and unloaded items cannot settle an answer or prove absence. When complete
history and a fresh idle reading show no matching delivery, Leaf abandons its own
attempt, releases its reply seat and reports that delivery could not be confirmed
and is not retried automatically. This does not assert that a provider turn failed.
The archived immutable identity retains correlation for late provider evidence;
a successful manual reply still wins. Accepted or abandoned deliveries without a
successful exact reply also hydrate from full history, even when the initial resume
omits their turns or the user resolved the thread. A manual reply retires an unknown
offer through the watcher's receipt recovery, including while disconnected.
Once every batch is acknowledged, only the delivery record moves under `history/`;
`leaf delivery read <id>` continues to resolve the immutable envelope.

An embedded host that already controls App Server can deliver the same immutable
envelope directly with `turn/start` when the task is idle. After App Server accepts
the turn, the host opens the claim turn under App Server's turn id, records the
delivery against it, advances its page cursor, holds that task's wait lease for the
container host's lifetime, and keeps the initiating connection for activity
notifications. The pickup, the claim turn, and streamed activity all name that one
id, which is also the id Codex's own hooks name. A retry reads the durable
pickup instead of starting the event again. Its subscription spans the active turn,
the delivery turn's opening, and that turn's terminal notification, recording both
`opened` and the exact turn close. A host
that owns a starting connection closes only that turn on its terminal
notification. Every carrier opens and closes a turn through `TurnFold`, which calls
the same session-wide opening and closing the hooks do; accepting a delivery only
records which turn took it, so a turn read back after it ended is never reopened. A direct start binds from its own answer. The request carries
the delivery id as its client message id, and App Server answers with the turn it made
from it, so the starter knows its turn before reading a notification. The structured
delivery also stays in the transcript, which is how a client that did not start a turn
recovers the same binding — one resuming a task after the fact, or reading the turn the
task opened for a queued pointer. An embedded host owns the provider task and
interrupts its turn when its initiating stream fails; a terminal adapter observes a
user-owned task and reconnects without interrupting it.
Reply binding is the hook's contract above and, for the agent,
`../../references/host-codex-app-server.md`, "Replies". This is another carrier over
the same delivery, page claim, event log, and activity projection, not another
thread store or response policy.

`server start` prepares the service in a detached process. A claimed handoff
prepares delivery before any page acquisition: Codex holds its adapter-start lock
until the serving producer commits the claim, so a newly ready carrier cannot
retire for lack of pages during that handoff. An existing direct wait is honored.
`server run` prepares the same delivery before binding in the foreground. Standing
and temporary serves prepare no delivery. `leaf codex start` prepares the adapter
under its start lock and then publishes the page claim, without serving.

A serving producer holds the page transition lock from private bind or reuse
through acceptance. A second start and an explicit stop wait for that transition;
neither can adopt an uncommitted listener. Binding refusal, delivery refusal and
cancellation before acceptance leave the previous claim, service and preview
watcher intact. The acquisition is prepared in the launching process, where
session lifetime and cwd are known, and validated under the session lock at
publication. The short page→session commit publishes the service before the claim
as its final mutation; it performs no host or network work while those locks stand.

`detached.starting_detached` first yields the child's private announcement. The
caller captures ownership inside that context, then accepts on normal exit. The
child publishes and confirms before the context returns. `hosting.claim_and_start`
exposes that prepared `PageStart`; a preview captures its exact acquisition before
acceptance, and CLI/demo callers report the URL only after confirmation. A child
abandoned before acceptance closes its private socket and lease without publishing.
After acceptance, lost confirmation is uncertain commitment, and cleanup uses the
captured acquisition. It cannot restore a superseded owner. Revival acquires
nothing and preserves both the recorded address and the existing acquisition.

## Lifetime

Whether a session's end reaches a server is decided at launch and written in
`service.json`; which lifetime a serve chooses, and what each asks of the agent, is
`../../references/serving-pages.md`, "Page lifetime". A serve from an agent host
records the page's claim under the state home's claims directory; a successor arriving
before the session server's final recheck keeps that process, and one arriving
afterward finds the process and lease gone and revives the still-enabled service.
A revival is a start by the Leaf running the wait, so it is refused as any start is
for a page vendored from another Leaf's runtime (`layer.foreign_runtime`): the wait
prints the refusal and reads the page as lost, and the service stays enabled until
`server stop`. Neither path changes the page's authored work status. A serve from a bare shell claims
nothing, and a claim on a standing page comes and goes without changing its service.
A `leaf wait` revives an enabled service whose process has died, once per death,
and says on stderr that it did. A page nothing will serve is lost: one with no
`service.json`, never served, or one whose revival was refused or died again. A
lost page ends a named wait, and a session's wait once no other live page is
left to carry, with the `leaf server start` command that serves it. A disabled
service is not lost, since a stop is the agent's own move and may be followed by
a start: `page init` stops and restarts a served page's server around a
re-vendor. The wait neither revives nor ends on it, and goes on watching until
the page goes idle or changes hands.

### Detached route lifetime

The detached Codex adapter follows active session/page ownership, including when
all owned pages declare idle. Idle pages deliver no input and direct waits end;
a later working or waiting declaration resumes the existing route. The adapter
waits for page news while idle and retires once ownership ends through release,
transfer, expiry or SessionEnd. Serving a closed page therefore does not lose
its delivery route before the agent's next declaration.
