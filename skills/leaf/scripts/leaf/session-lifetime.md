# Session lifetime, pickup, and work in hand

This file says how Leaf decides who holds a page, what the agent is doing on it, and
how the user's input reaches the agent's turn. It has three parts. "Page activity" is
the server's one reading of the agent's work, which the banner, the Stop hook and the
browser all consume. "Watchers" is how each harness carries input into a turn, and the
hooks that keep a turn from ending over it. "Lifetime" is how serving, claims and
services begin and end. The Codex transports' delivery records and App Server
observation belong to `codex.py`, `codex_adapter.py` and `codex_state.py`, whose
headers state them.

## Page activity

The page's current agent state is `activity`, one server projection over the agent's
declarations and the page's stronger evidence. `status.json` and the log's work
starts are declarations, not current agent state. The stronger evidence is claim and
turn identity, watcher lifetime, exact pickup transitions, and unsettled updates.
`/api/state` and agent-facing page state carry this same projection. A
neighboring-page entry carries the serving page's own compact canonical publication
(`server_rows.py`), read alongside its server lease. Browser code paints it and
requests another reading at its next deadline; it does not run a second fold.

The table lists each fact the projection reads, and when it stops being believed.

| Fact | Where | Writer | Stops being believed |
| --- | --- | --- | --- |
| page declaration: `waiting` or `idle`, detail | `status.json` | `leaf status`, which first writes a `put_down` to the log when a start stands | stands until the next declaration, and its age dates the page's other readings |
| the item in hand: an update's event id or an open to-do's id, the line, and the claimant turn that wrote it, or none for another session's | an explicit `start` or an addressed progress reply's `start` metadata in `events.jsonl`, read by `todos.start_reading` | `leaf task start`, or `leaf response reply --ephemeral` on an update owed, from a turn of the session driving the page | the item ending: an update's answer, or a to-do's end; a later `put_down` event, which `leaf status waiting` and `idle` write; and as a belief, a short grace after the turn that wrote it closes, about a quarter of an hour with no renewal, or at once when the claimant's lifetime has ended |
| live App Server activity: session, turn, typed kind, detail, event floor | optional `stream` in `status.json` | the App Server connection that starts an embedded turn, or the detached adapter's task connection | turn completion, connection or observer exit, loss of the wait lease, or the working grace without another event |
| live App Server reply: one displayed reply plus reply reservations by response address | optional `stream.reply` and `stream.reply_reservations` in `status.json` | an App Server connection bound to a delivery's reply; explicit `response reply` writes directly to the event log | the draft joins its thread once it has words, drawn under its response address, which the durable answer to that input shares, and remains on failure or disconnect until a logged event naming its delivery attempt or its response address retires it; each reply reservation names the claim turn it belongs to (the delivery's turn once its reply opens, the turn current at reservation before then), clears after durable commit or terminal failure, and survives a lost connection; it holds only while that is still the claim's turn and the turn is open (`activity.reply_reservation_stands`), and a turn's answer committed after its reservation lapsed yields to a reply another writer already gave |
| turn identity, when it last opened or took a prompt, and open or closed state | the session lifecycle record | a prompt, an explicit reader acknowledgement for an unnamed harness turn, the queue adapter observing Codex’s native transcript (`codex_state.py`), or an App Server client following a provider turn opens `turn` and stamps `turn_opened`, or renews that stamp on a turn still open; the id is the harness's where it names one (Codex's hooks and App Server name the same turn) and one Leaf mints otherwise; the Stop hook stamps `turn_closed` on whatever turn is open, and an App Server client on the turn it follows | the next opening of another id; the next closing stamps it, and a closed id never reopens |
| the harness's own word on the claimant's session: `idle`, `waiting` on a dialog, or `busy`, dated by its last change | the harness's record, read at each state read (`Harness.live_turn`): for Claude Code, the `status` of the session's newest registry record whose process runs | the harness | read live, so it moves with the harness; absent where the harness publishes nothing, as for a background job whose worker has retired |
| the turn ending this page nudged its session after | `messaged_ending` in the page's claim record: the turn id and its close stamp, or for an interrupted turn its last opening | browser-event admission, once the harness's nudge lands | a later ending, a close under a new id or an interrupt after a new prompt renewed the same one, differs |
| wait lease | `waiter.lock`, or `sessions/<session>.wait` for a harness session | the live `leaf wait` process, or Claude Code's background Stop hook watching between turns (`leaf hook --harness claude-code --watch`), holding an exclusive kernel lock on a stable file; file existence does not prove liveness | descriptor close or process exit, including a crash; a later hook watch's supersession, which puts a fresh, held file at the name |
| the harness runs Leaf's hooks for this session | `sessions/<session>.hooks` | every Leaf hook the harness runs for the session | removed by its SessionEnd hook |
| acknowledgement cursor | `cursor.json` | whatever confirms the complete delivery reached its durable consumer: a Claude Code or Pi hook once it has published an inline delivery, the session's explicit `leaf delivery ack` after a pointer reading, `leaf wait --ack` after a printed one, or the Codex adapter | when its seq is past the log's end, or a fresh log replaces the one it named; monotonic within one log |
| pickup transition | a `pickup` event in `events.jsonl` | the adapter records `queued` when Codex accepts a batch it does not observe; whatever puts the batch into a turn records `opened` with session and turn identity: a direct `leaf wait --ack` confirmation, an inline hook's or a pointer reader's explicit confirmation of a Claude Code or Pi hook delivery, the prompt hook re-presenting an acknowledged unanswered update, or an App Server turn start | never; each event/phase/session/turn transition is idempotent |
| page claim: unique acquisition, session generation, display name, harness | `<state-home>/claims/<page-key>.json`; the session partition holds a symlink locator to it | `server start` from an agent harness; references the session lifetime publication | the referenced generation ended or was replaced, or the shared harness lifetime is gone: the pid, the background job's directory, or the desktop Codex chat's validated native transcript at the path in its session record; archive moves that source and delete removes it |
| service lifetime | `service.json` | `server start` at launch: session, or persistent | `leaf server stop`; a session server also retires when no live claim holds it |
| Codex delivery record | `sessions/<session>.deliveries/` in the state home | the detached adapter or an embedded App Server harness | an unaccepted record is inactive while the session owns no page; an accepted record moves under `history/` after every batch is receipted; a record, live or archived, goes at the next scan that finds its pages all gone: its own task's reading, its next archiving, or any Codex adapter's retirement, which scans every task's records and removes a directory it empties |
| Codex adapter log | `sessions/<session>.codex.log` | the detached adapter's own output, begun afresh when serving or `leaf codex start` starts a new adapter | removed when the adapter retires owning no page; a run that ended any other way leaves it for the next start of that task |
| Leaf delivery | `<state-home>/deliveries/<id>.json` | whatever presents a delivery freezes its harness-neutral envelope first | once every page it names is gone, removed when the next delivery is frozen; until then every transport resolves the same immutable id |

### Activity

Page activity describes ownership, watcher availability, and current work. Its
`kind` is `closed`, `unheld`, `away`, `listening`, `working`, or `stalled`. Every
rule in the fold that asks whether the claimant's turn is running reads one answer,
`activity.claimant_turn`, which dates each piece of evidence and lets the newest
decide. The session's turn stamps are believed open only while the opening, a status
or start written during the turn, or the claimant's streamed activity renewed them
within the working grace. The harness's record adds the two things no hook sees, each
only when newer than what it contradicts: an `idle` newer than every renewal ends the
open turn (an interrupt), and a `waiting` newer than the stamps is a dialog open now,
observed as `awaiting_user` since the record does not say whether it asks for
approval or an answer. Its `busy` is never read, since a background job's record
keeps it across turn endings. Browser-event admission reads the same turn before it
nudges a session (`presence.claimant_reading`), and nudges only after an ending
something saw: a turn Leaf merely stopped believing in may still be running a long
step.

The claimant takes input while its wait lease is held or, for a harness whose hooks
carry input, while its turn runs. Fresh declared or observed work makes the page
working independently of how far newer input has progressed. A harness-observed wait
on the user in its own window, such as an approval or a question, is observed work
that lasts as long as its observer does. Delivery opened into the claimant's running
turn also proves generic activity before its first start; the receipt itself remains
Picked up. The banner's line is the newest start's, among the items still in hand.
`counts.overdue` counts the owed updates that stalled with the agent to act: still
Sent past the pickup grace, or left by a turn that ended or was interrupted before
answering. Over an `away` page, they are when the banner asks the user to nudge the
session. The banner consumes this same reading and presents delivery counts
separately; the Pages drawer consumes each serving page's own canonical publication.

Observed App Server activity refines the page's work and never a message's. The App
Server observer retains typed `working`, `thinking`, `tool`, `replying`,
`awaiting_approval`, and `awaiting_input` activity with the observed session and
provider turn. These are observations of the page's agent, not claims on every
message. Missing subtype evidence means generic Working. A tool invocation is not an
independently tracked background job, and neither an old observation nor a
disconnected App Server client proves a job failed. A current authored work
declaration keeps the page's sentence and date. The observed step remains separately
available as `observed` and `observed_kind`, with `awaiting` saying whether that step
waits on the user in the agent's own window; where the declaration has no authored
sentence, the observation supplies it. Only current observed work supplies a live
subtype. Delivery floors and reply reservations continue to govern local
workflows and settlement, without making newer input erase overall page work.
Thinking and tool activity stay page-wide until a harness provides an explicit input
or subject binding; the current harness contract does not.

### Workflows

`workflows` is the shared projection for exact user inputs. Each entry names its
`input` event, its `thread` or `widget` `subject`, its strongest proven `stage`
(`sent`, `queued`, `picked_up`, `working`, `replying`, or the retained terminal
`answered` outcome), and any separately proven `condition`. The served list also
names the `thread` each workflow belongs to (null for a page widget), whether the
agent is `at_work` on it (`working` or `replying`), and whether it `holds_thread` the
agent's turn. It lists the strongest first (`served_state.work.served_workflows`): a
surface that shows one workflow of several shows the first, and the browser places
only its own unresolved sends against that order.

A condition records evidence that a stage has stopped. A Sent input that remains
unpicked after the short grace has a stale delivery condition. A pickup whose exact
turn was seen to end, by its close or by the harness's record, has an ended condition
without claiming interruption. A Working start quiet beyond its lease, or a pickup
belonging to a different or older turn or to one nothing has renewed within the
working grace, has a stale work condition while retaining its durable stage. A
provisional response is Replying only on the input named by its `responds` address.
Disconnect, interruption, and failure require the response's own state, and a turn
that completed without a final answer (`partial`) reads ended. Successful settlement
removes the workflow; the logged answer remains its evidence. For an interrupted or
failed response, the workflow's `response` names the exact delivery attempt when one
exists. A durable failure receipt also names its reply event id. Browser notices read
this current workflow condition and source identity: an old failure does not become
fresh news after a later successful answer, and stale work or delivery evidence is
not a response failure.

Recovery stays with the agent unless the user has a concrete gesture to make. Ordinary
durable stale, ended, interrupted, and failed observations prove uncertainty or a
stopped operation but give the user no recovery gesture, so they remain agent-owned.
A terminal harness failure hands recovery to the user, whatever the update's answer:
`workflows.py` names the record each answer takes. It settles the Stop obligation; a
failure reply or a failed pickup retains an `answered` workflow with a failed
response condition until the user acts again. A local send refusal similarly has a
browser-owned Retry gesture; that unresolved overlay may put the thread in Needs you
without persisting another workflow record.

### Answers and obligations

A workflow's `stage` and its `answer` are separate readings. The stage reports
delivery for every update the user has handed over. The answer, which `workflows.py`
states, is what the agent owes it: a reply, a version for a thread that asked for
one, a version whose markup records a user's answer to a page ask, or null. Only owed
answers enter activity counts.

Each consumer of the obligations selects its own set. `leaf status idle` refuses over
`activity.blocking_obligations`: the acknowledged updates nothing else is set to
answer. An update still `queued` is answered by the later turn that opens it, and a
reply whose provider final the open turn has finished is committed by the claimant's
App Server client while the session's watcher is live. The Stop hook holds the
claimant's turn over the updates the turn has not started, which
`activity.turn_obligations` selects. A start the open turn wrote since the update's
pickup, on the update or on any input its thread's one reply answers, is the agent's
answer for now, and the turn may end over it while background workers carry the work.
The start does not carry into the next turn, which answers the update or starts it
again.

Some updates owe nothing or settle without a reply. A widget action that answers no
ask, such as a draft edit or a moved card, owes nothing: its workflow reports delivery
until its document takes it in. For a page action, that is until the markup records
the action or a later version supersedes it; for an action in frozen thread markup,
until the agent's next spoken turn in that thread, or a resolution that closes the
thread after it. It does not make its thread the agent's turn. An action the user has
not finished, such as a pick before the Done its ask declares, has not been handed
over and has no workflow. A resolution or authored state that honors an update also
settles it; a later version note settles a page action whose verb has no authored
record form. A note already in force when the update arrives cannot answer it.

Consecutive user turns form one response batch addressed by its newest input. Before
settlement each input retains a workflow, while only the newest carries the thread's
`answer` and enters the obligation list. A response to an older input removes that
input and leaves the newer obligation. A response to the newest settles the batch.
Widget asks remain independent and settle through their declared state.

Pickup never rewrites `status.json` or makes the page itself Picked up. Turn identity
decides whether a receipt belongs to the open turn; ending a turn does not settle its
input. A delivery's completed final answer retains the exact delivered `responds`
address, even when a resolution, the user's ✓, or authored state settled that update
during the turn. Its substantive reply reopens the thread under the ordinary thread
rule in `events.md`, so the answer returns to Open Threads without making the
answered update owed again. Failure receipts are omitted once their update is
settled.

### Starts

A start has to be renewed, and starting the item again renews it. It names one item:
an update, by its event id, which then reads **Working**, or a to-do, which then runs
with the start's line. Nothing in a session starts an item while its turn is over,
and its workers leave the page to it, so a start over work that outlasts the turn
goes unrenewed until a later turn starts the item again. What holds such work across
turns is the to-do itself (`todos.py`), which no turn or session ending lapses.

### Turns and generations

The turn id and `turn_closed` stamp a declaration is judged against are the
session's rather than the page's: prompts and endings publish one atomic session
record. Page claims reference its generation and derive the current turn; no opening
or ending rewrites claims. Each acquisition has its own unique ID, so rollback
compares claim publication rather than derived lifecycle fields or second-resolution
timestamps. The first observed harness lifetime may enrich an unknown prompt-created
lifetime; replacing known provenance starts a generation. SessionEnd ends a
process-backed generation without page discovery or page locks; a resumed
process-backed harness ID gets a new generation, leaving old claims inactive. Desktop
Codex unloading closes its instance observations and retains the chat generation, so
resuming that chat retains its page ownership. The native chat source keeps every
page it owns alive, independently of browser attention.

Where nothing answers for the declaration, activity reports the page unheld rather
than repeating it. A page with a persistent service spends most of its life unheld,
and picks up again when a session takes it.

## Watchers

Each session runs one watcher for all its pages, separate from the page servers. The
watcher holds the session's wait lease between turns and brings the pages' input into
the next turn, and a transport then hands each delivery into the turn's context. The
claim names the harness, and a reader elsewhere rebuilds its declaration from that
name and asks it what proves the watcher live and what to say when it is not, rather
than comparing the name itself. A watcher is a hook watch, a model wait, the adapter,
or the host:

- A hook watch under Claude Code: Leaf's own Stop hook. Claude Code starts it in the
  background as each turn ends and wakes the session when it exits 2
  (`Harness.watches_between_turns`), and the model starts no watcher. It holds the
  session's wait lease until a page has input, exits 2 to wake the session, and the
  prompt hook of the turn the wake opens or reaches puts the batch in that turn's
  context; its reader acknowledges the complete envelope before work. Input that was
  already pending as the turn ended is the other Stop hook's to hand to the turn it
  continues, so the watch carries it only once that hook lets the turn end over it.
  Claude Code leaves an earlier turn's watch running when it starts the next, so
  the newest takes the lease from it (`leases.supersede_lease`), and the one it
  displaces ends without waking the session. The newest runs the Leaf the harness
  runs now; an earlier one may run a Leaf the session has since left, which cannot
  read a page vendored by a later one and would otherwise hold the lease over it.
  Claude Code bounds a background command at two hours and a hook only at its own
  `timeout`, which is why the watch is a hook. Plain `--print` runs the hook in the
  foreground, holding the turn, so there it watches nothing.
- A hook watch under Claude Code with the `hooks_module` option on: the same watch,
  which Leaf's hooks module (`hooks/claude-code.ts`) starts as the session starts and
  as each main-loop turn ends, in place of that Stop hook. A watch that wakes an idle
  session submits its line as a prompt, whose prompt hook hands the batch over; one
  that wakes during a turn calls the prompt hook itself and appends its context to
  that turn, which reads it at its next step. An interrupted turn runs no Stop hook,
  but the module still sees it end, so it starts the watch with the Interrupt payload,
  as Pi's extension does. Claude Code prints a Stop hook's context in the user's
  terminal, so the module moves a delivery the Stop hook hands over into the session
  as an appended row, which it does not show, and the turn goes on with one line.
- A hook watch under Pi: the same watch, which Leaf's extension (`hooks/pi.ts`) starts
  as the session starts and as each run settles. When the watch exits with input and
  no run is going, the extension sends an unreceived notification to start one. The
  accepted run opens its lifecycle without receipt; its incoming message finalization
  calls the prompt hook and commits context before the first model request. Later
  input enters through its next live turn end. A canceled turn end receives nothing,
  since a steer waits in a queue Escape clears and receipt belongs to context that
  enters the session. After an interrupted run it starts the watch with the Interrupt
  payload, which first answers the Interrupt hook, closing the turn, and then wakes
  for input that never entered the stopped turn. The completed receipt advances its
  cursor before the hook returns context; an opened pickup without that cursor write
  does not prove delivery. Settled thread input stays in its next delivery batch
  without waking alone.
- A model wait: a sequence of `leaf wait` runs the model itself starts. Every explicit
  wait prints the delivery directly, including in a session whose hooks ran before but
  can no longer deliver. Large deliveries expose lossless parts with `next` commands;
  only their last part offers acknowledgement. After reading every part,
  `leaf wait --ack <delivery-id>` advances the captured cursors and becomes the next
  wait.
- The adapter: one detached process a Codex task uses on either transport. It holds
  the same task-wide wait lease plus an adapter lease of its own, and stores exact
  batches from every page in one task-wide delivery (`codex_adapter.py`).
- The host: a harness that drives App Server itself, as the website's per-user
  container does. It starts the turn directly and needs nothing between turns
  (`codex.py`).

Every watcher watches every page the session holds, re-reading the set on each pass,
and every transport hands over the same envelope (`../../references/event-batches.md`,
"One envelope on every transport"). On Codex, the adapter and the tool and Stop hooks
share one task's delivery records; `codex.py` states how a record is captured,
offered, accepted and receipted, and how an App Server client binds a turn's reply.

### The hook

The `hook` command keeps a turn from ending while the turn leaves one of this
session's pages unwatched or a delivered update unanswered and unstarted. It is
registered on SessionStart/resume, Stop, UserPromptSubmit, SessionEnd, and Codex's
PostToolUse and Interrupt, and Leaf's Pi extension (`hooks/pi.ts`) calls it at the
accepted run boundaries. An unwatched page is one whose watcher is a process of its
own; Claude Code's watch is its next Stop hook. The hook also stamps that turn's
ending and the next one's opening, surfaces unacknowledged user events at the next
prompt, ends process-backed ownership when the session exits, and retains desktop
chat ownership when its instance unloads.

The Stop hook continues a turn only for what the turn owes. It keeps a turn going
through the harness's continuation channel (`Harness.hook_context`): the non-error
`additionalContext` Claude Code and Pi's extension read, or a block where, as in
Codex, the harness's Stop output has nothing else. What the turn owes is input that
arrives as it ends and is owed an answer, which the hook hands over, or an obligation
above. Input that owes nothing, such as a resolve, a report or a page error, waits for
the watcher and rides along when the turn goes on anyway. A repeated Stop
(`stop_hook_active`) has named its obligations once and lets the turn end; only newly
arrived owed input continues it again.

Each harness has its own registrations, which pass its name
(`hook --harness <name>`); the hook takes the session from its payload and infers
neither from its environment (`harness.hook_harness`). A server the hook's watch
revives is handed that harness too (`harness.harness_argument`). A second Claude Code
Stop registration runs the watch (`--watch`), which Claude Code keeps in the
background (`asyncRewake`) as the session's watch between turns
(`session.watch_between_turns`): its exit 2 wakes the session with its stderr, and
startup or application failures retain stderr and return nonblocking exit 1.
Cancellation stays quiet. Where the user turns on the plugin's `hooks_module` option
and Claude Code loads hooks modules, Leaf's module (`hooks/claude-code.ts`) runs the
watch itself and marks the Stop payload it passes on, and the registration given a
marked payload stands down (`hooks/scripts/background-watch.py`). Pi opens its
lifecycle with `TurnStart` only after the SDK accepts the run. That hook reads no page
and receives no input. Accepted incoming messages are finalized with context before
the first model request; later live turn boundaries return persisted context entries.
Preparation or a cleared wake notification cannot confirm receipt.

The hook reads each page once and decides from that one reading. Its unanswered-work
guard reads `activity.turn_obligations` over the page's activity, selected from the
same `workflows` projection the browser reads; it does not reconstruct threads
itself. The hook planner reads each page once under its transaction, including
ownership, log, cursor, status and the shared live work reading. Its typed input,
response obligation and watcher facts feed Stop policy before harness formatting;
prompt pickup is an explicit transition and rechecks that the obligation remains
unsettled. Every hook effect checks its captured session generation and revision,
including no-ID and same-ID prompt renewal, and the decision to publish is taken under
that epoch guard.

A hook hands a delivery over inline only when the harness will read all of it. A
harness reads a hook's output only once it exits, discards it for a hook it times out,
and Claude Code cuts a large context to a preview, so the hook hands a delivery over
inline only once it fits, and only once the hook has confirmed every batch while well
inside its timeout (`hook_transport.CONFIRM_WITHIN`); otherwise it hands over a
pointer. After reading all its parts, the session confirms receipt with
`leaf delivery ack`, which shows any refusal the hook met. Every hook envelope's
`acknowledge` is null. Receipt revalidates current ownership and exact event
identities under page→session locks held through pickup and cursor commit, batch by
batch, so a page the session no longer holds keeps its input pending. Hook and
provider receipt observe an open turn and cannot open or replace one. Explicit reader
acknowledgement can open a fresh unnamed harness turn after a missed prompt hook;
known provider turns remain authoritative. Input stays pending if a hook is stopped
before it confirms, or a pointer is never confirmed. Codex's hooks and App Server
clients follow the provider's own turn: `codex_state.py` states how its hooks observe
it, and `codex_adapter.py` and `codex.py` (`TurnFold`) how its App Server clients do.

When the prompt hook opens a turn, it records a new `opened` transition for its
acknowledged, unanswered updates. An embedded harness records the same transition
from the queued turn's App Server `turn/started` notification. A direct-delivery
update that needs a reminder is also named in the hook context. A queued Codex update
needs no reminder there: the prompt itself carries its delivery pointer, while the
transition gives the browser and the next Stop their shared handling fact.

Session death is not completion or an explicit stop: work status and desired service
stay as they were. Absent the harness the environment implies, nothing is claimed and
the hooks stand down. Turn hooks call `bin/leaf hook`; that shell launcher runs the
application through `uv`, which supplies the supported interpreter and dependencies.
The application entry routes the hook to its lightweight owner before importing the
CLI or page reading. It marks the session and records Codex provider turns even
before a page is acquired. It reads active ownership through `service.owned_pages`;
resume and prompt hooks also inspect retained claims for reconnect notices. A session
with no retained page avoids the delivery and page-reading stacks.

SessionEnd calls the launcher's `session-end` entry, which runs its standalone stdlib
state owner directly. That program supports Python 3.9 and publishes the session
transition: process-backed generations end, while desktop chat generations retain
ownership and close their instance observations. It needs no page discovery, page
locks or claim rewrites, including for claims made by another checkout when this
plugin has no uv environment. Managed Leaf delegates SessionEnd to the same owner.
Registrations retain stderr and return nonblocking exit 1 when the application cannot
answer, including when uv uses exit 2 for its own startup failure. The harness owns
their deadlines. `hooks/scripts/background-watch.py` supervises the background watch,
calling the launcher and converting its successful result into Claude Code's exit-2
wake.

Only a page handed to a user owes a watcher, so the unwatched clause passes over a
page carrying `preview.json`, which only a checkout's `leaf-dev preview` writes;
nothing else about that page changes. The guard reads the file's presence rather than
the serve path's validating reader, because it fails open by saying nothing.

### Reconnect notices

Resume and prompt hooks tell the agent how to restore a page the session still means
to serve. They inspect the session's retained claims, including those whose ownership
has expired. An enabled session service with inactive ownership or no exact live
server lease emits a reconnect notice with `leaf server start <page>`, which restores
serving and the delivery of updates. The notice also covers the orphan grace period,
while the old listener may still be running. Stopped services, persistent services,
developer previews, and pages another session claimed are excluded.

`reconnect.py` reserves one notice per harness/session/page in
`sessions/<session>.<harness>.reconnect`. This notification record survives
SessionEnd and generation changes. Matching active ownership and exact live serving
close the outage, both when a hook observes recovery and when a serve commits it. A
later outage can then emit another notice. Reservation is serialized with ownership
and desired service changes and the final lifecycle check through stdout publication.
A stale hook reserves nothing, leaving its successor able to notify. Hook stdout
proves no model receipt, so output is at-most-once. SessionStart does not open a new
turn or reacquire a page. The Stop hook does not continue a turn to deliver a
reconnect notice.

### Nudging a session with no watcher

When a watcher stops while its session lives on, browser-event admission asks the
claimant's harness to nudge the session. Only a watcher the session's own turns start
can stop that way: a turn interrupted without its Stop hooks starts no watch unless
Leaf's hooks module keeps it, a watch fails open or reaches its hook's timeout, or a
model-run wait is stopped after the turn ends. Input that reaches the page after that
has no watcher, and a nudge is the one way to reach such a session, which only some
harnesses offer. Claude Code's is the Unix socket it binds for each session, found by
session id in Claude Code's session registry (`message_claude_code_session`).

Admission sends when an event is appended to a page whose claimant takes no input by
the activity fold's reading: no wait lease, and no running turn, an interrupted one
read as ended. A running turn is excluded because its Stop hook already refuses to
end with the input unpicked, and a waking watch and the prompt hook both reopen the
turn. Each page messages its session once per ending of a turn: when a socket takes
the message, the claim records that ending as `messaged_ending`, so later input after
the same ending sends nothing more, a later ending sends again, and input after a send
no socket took tries again. Input that arrived before a repeated Stop let the turn end
gets no message, because the blocked Stop already reported it and a message would
reopen the turn the hook just let end.

The message names the page, and the input arrives with it: Claude Code 2.1.274 fires
UserPromptSubmit for a delivered message, so the prompt hook reopens the turn and
lists the input as it would for a typed prompt, and that turn's ending starts the
watch again. Delivery is the recipient's decision, and nothing reports it back. A
session that bypasses permissions holds the message behind an approval dialog unless
its user set `crossSessionInbound` to `accept`. A background job's daemon retires an
idle job's worker after about an hour, with its socket and the Stop hook's watch,
which ends once its harness process is gone (`Harness.process_runs`). Such a job is
resumed instead: `claude --bg --resume` runs the message as the job's next prompt on a
fresh worker (`resume_claude_code_job`), which a job a live worker hosts is spared,
since the command would start a copy. The command is started rather than awaited,
since the turn it starts takes the page's lock in its prompt hook, so the ending is
marked messaged once it starts. Stop does not fire on an interrupted turn (measured),
so an interrupted turn is messaged once the session's registry record reads `idle`;
with no record, not until a Stop closes a later turn. The adapter and the host declare
no nudge and need none: each queues or starts turns itself, and if it is gone so is
the session it served.

## Lifetime

Whether a session's end reaches a server is decided at launch and written in
`service.json`; which lifetime a serve chooses, and what each asks of the agent, is
`../../references/serving-pages.md`, "Page lifetime". A serve from an agent harness
records the page's claim under the state home's claims directory; a successor
arriving before the session server's final recheck keeps that process, and one
arriving afterward finds the process and lease gone and revives the still-enabled
service. A revival is a start by the Leaf running the wait, so it is refused as any
start is for a page this Leaf cannot serve (`layer.incompatible_layer`): the
wait prints the refusal and reads the page as lost, and the service stays enabled
until `server stop`. Neither path changes the page's authored work status. A serve
from a bare shell claims nothing, and a claim on a persistent page comes and goes
without changing its service.

A `leaf wait` revives an enabled service whose process has died, once per death, and
says on stderr that it did. A page nothing will serve is lost: one with no
`service.json`, never served, or one whose revival was refused or died again. A lost
page ends a named wait, and a session's wait once no other live page is left to carry,
with the `leaf server start` command that serves it. A disabled service is not lost,
since a stop is the agent's own choice and may be followed by a start: `page init`
stops and restarts a served page's server around a re-vendor. The wait neither revives
nor ends on it, and goes on watching until the page goes idle or changes hands.

### Starting a server

`server start` prepares the service in a detached process. A claimed handoff prepares
delivery before any page acquisition: Codex holds its adapter-start lock until the
serving producer commits the claim, so a newly ready adapter cannot retire for lack of
pages during that handoff. An existing direct wait is honored. `server run` prepares
the same delivery before binding in the foreground. Persistent and temporary serves
prepare no delivery. `leaf codex start` prepares the adapter under its start lock and
then publishes the page claim, without serving.

A serving producer holds the page transition lock from private bind or reuse through
acceptance. A second start and an explicit stop wait for that transition; neither can
adopt an uncommitted listener. Binding refusal, delivery refusal and cancellation
before acceptance leave the previous claim, service and preview watcher intact. The
acquisition is prepared in the launching process, where session lifetime and cwd are
known, and validated under the session lock at publication. The short page→session
commit publishes the service before the claim as its final mutation; it performs no
harness or network work while those locks are held.

`hosting.claim_and_start` exposes its prepared `PageStart` through
`detached.starting_detached`. The caller captures ownership inside that context, then
accepts on normal exit. The child server publishes and confirms before the context
returns. A preview captures its exact acquisition before acceptance, and CLI/demo
callers report the URL only after confirmation. A server abandoned before acceptance
closes its private socket and lease without publishing. After acceptance, lost
confirmation is uncertain commitment, and cleanup uses the captured acquisition. It
cannot restore a superseded owner. Revival acquires nothing and preserves both the
recorded address and the existing acquisition.

Recording what a session's task already took needs less than taking new input. Taking
new input from a page needs the session's claim active, but recording what the
session's task already took or answered there (a receipt, a turn's final answer, a
failure answer) needs only that the claim still names the session and the session has
not ended (`service.claim_names_session`). A restart begins the session's new
generation before it publishes that generation's claim, and a task holding several
pages claims them back one at a time, so an App Server client reading the task back
after a restart meets claims that name an older generation of its own session.
Refusing there would retire an accepted batch without advancing the page's cursor, so
its input would be delivered again once the page is claimed, and would lose the turn's
answer. Another session's claim or the session's end still refuses.

### Adapter lifetime

Desktop Codex unloads an idle running instance without ending the chat. Its
persisted-chat lifecycle retains the generation at `SessionEnd`, closes an open turn,
and retires hook capability observations while keeping the claimed-page marker. The
next prompt and tool hook therefore resume the same ownership and delivery route. The
session record owns the one validated `transcript_path`; lifetime records only
`chat: true`. Missing source evidence refuses a new desktop start. An existing chat
keeps its server, preview and adapter across inactivity and unload; archival or
deletion of its native source and transfer retire ownership. Process-backed harness
sessions invalidate their generation at `SessionEnd`.

Desktop user previews also detach their input watcher from the launching command. The
launcher captures the claim's lifetime and cwd and holds delivery preparation until
the watcher starts its server and confirms its input subscription. The preview
reserves and rebuilds its own slot before serving, so startup may publish that fresh
page before the launcher receives readiness. Abandoning startup or ending the watcher
stops its service and withdraws its exact acquisition; a successor's ownership is
preserved. The watcher exits on explicit service stop or lost ownership, without
touching page files just to renew itself.

The detached Codex adapter follows active session/page ownership, including when all
owned pages declare idle. Idle pages deliver no input and direct waits end; a later
start or waiting declaration resumes delivery through the existing adapter. The
adapter waits for page news while idle and retires once ownership ends through
transfer, chat archival/deletion or a process-backed SessionEnd. Serving a closed page
therefore does not lose its adapter before the agent's next declaration.
