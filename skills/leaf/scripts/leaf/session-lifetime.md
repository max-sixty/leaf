# Session lifetime, pickup, and work claims

A page's current agent state is `activity`, which `activity.canonical_activity`
folds from `status.json` (the agent's declaration) and the stronger evidence beside
it: claim and turn identity, the wait lease, pickup events, and unsettled user
moves. `/api/state`, neighboring-page rows, `page state`, the hooks, and `leaf status
idle` all read this one fold. The browser paints it and asks for a new reading at
`next_transition_at`; it never folds the evidence itself.

| Fact | Where | Writer | Stops being believed |
| --- | --- | --- | --- |
| work declaration: state, detail, event floor, and `work` seats, each naming the claimant turn that wrote it (none for another session's) | `status.json` | `leaf status`, from a turn of the session driving the page | `TURN_RENEWAL_GRACE` after the turn that wrote it closes; `WORKING_GRACE` without renewal; at once when the claimant's lifetime ends |
| live App Server activity: session, turn, kind, detail, event floor | `stream` in `status.json` | the App Server connection that started the turn, or the adapter's observer | turn completion, connection or observer exit, loss of the wait lease, or `WORKING_GRACE` without another event |
| live App Server reply: one draft, and reply bindings keyed by response address | `stream.reply` and `stream.reply_bindings` | the connection bound to a delivery's reply | the draft, when a logged event names its attempt or address; a binding, at commit, terminal failure, or when its turn stops being the claim's open turn (`activity.reply_binding_stands`) |
| turn id, `turn_opened`, `turn_closed` | the page's claim record | a prompt hook, a delivery, or a carrier opens or renews the turn, under the host's turn id where it names one (Codex's hooks and App Server name the same one); the Stop hook or the carrier closes it | the next opening under another id; a closed id never reopens |
| the host's word on the session: `idle`, `waiting`, or `busy`, dated | the host's own record, read live (`Harness.live_turn`); for Claude Code, its session registry | the host | read live; absent where the host publishes nothing |
| the turn ending this page last nudged its session after | `messaged_ending` in the claim record | browser-event admission, once a nudge lands | a later ending differs from it |
| wait lease | `waiter.lock`, or `sessions/<session>.wait` for a host session | the live `leaf wait` | process exit |
| a wait start no tool hook has named | lock on `sessions/<session>.started` (`leases.take_session_wait`) | `leaf wait`, with its lease | the `PostToolUse` hook names it, or the wait ends |
| the host runs Leaf's hooks for this session | `sessions/<session>.hooks` | every Leaf hook | SessionEnd |
| acknowledgement cursor | `cursor.json` | the carrier that confirms a delivery reached its consumer: a Claude Code hook, `leaf wait --ack`, or the Codex adapter | reads as 0 once its seq is past the log's end (`event_log.read_cursor`); monotonic within one log |
| pickup transition | `pickup` event in `events.jsonl` | `queued` when Codex accepts a queued pointer; `opened`, with session and turn, by whichever carrier puts the batch into a turn, including the prompt hook re-presenting an acknowledged unanswered move | never; each transition is idempotent |
| page claim: session, display name, harness, carrier, lifetime | `<state-home>/claims/<page>` | `server start` from an agent host; released at SessionEnd | `released` is set, or its lifetime is gone: the pid, the background job's record, or, for a host that runs every session in one process, `ACTIVITY_GRACE_SECS` with nothing touching the page (`service._touched_recently`) |
| service lifetime | `service.json` | `server start`: `session` or `standing` | `leaf server stop`; a session server also retires when no live claim holds it |
| Codex delivery record | `sessions/<session>.deliveries/` | the Codex adapter or an embedded App Server host | moved under `history/` once every batch is receipted; removed by the next scan that finds all its pages gone |
| Codex adapter log | `sessions/<session>.codex.log` | the adapter, begun afresh by each `leaf codex start` | removed when the adapter retires owning no page |
| Leaf delivery envelope | `<state-home>/deliveries/<id>.json` | any carrier, frozen before it is presented | removed at the next freeze once every page it names is gone (`delivery.pages_gone`) |

## Page activity

Activity's `kind` is `closed`, `unheld`, `away`, `listening`, `working`, or
`stalled`. It describes the claimant and its carrier, not any one message.

Every rule that asks whether the claimant's turn is running reads
`activity.claimant_turn`, which dates each piece of evidence and lets the newest
decide. An interrupt runs no hook, so an open turn is believed only while something
in it renewed it within `WORKING_GRACE`: the opening, a status written during it, or
the claimant's streamed activity. The host's record covers what no hook sees: an
`idle` newer than every renewal ends the turn, and a `waiting` newer than the stamps
is a dialog open now, read as `awaiting_user`. Its `busy` is never read, because a
background job's record stays `busy` across turn endings.

The claimant takes input while it holds the wait lease or, under a harness whose
hooks carry input, while its turn runs (`activity.takes_input`). Fresh declared or
observed work makes the page `working` regardless of newer input; so does a delivery
opened into the running turn before any declaration. Pickup never rewrites
`status.json`.

`counts.overdue` counts owed moves that stalled with the agent to act: still Sent past
`PICKUP_GRACE`, or left by a turn seen to end or be interrupted before answering. On
an `away` page they are the moves the banner asks the user to nudge the session about.
Work that has only gone quiet is left out, since a turn Leaf stopped believing in may
still be running a long step.

A page is unheld when its claim's lifetime has ended, or when it has no claim, no
watcher, and no recently renewed declaration. Unheld is not a fault: a `standing` page
spends most of its life unheld.

## Workflows and obligations

`workflows` is the one projection of each unsettled user move. Its two readings, the
delivery `stage` and the owed `answer`, and what settles each are defined in the
`workflows.py` header. Every consumer that holds the agent to an answer reads
`answer` there. The served list adds each workflow's `thread` and `holds_thread`, and
orders them strongest first (`served_state.browser.served_workflows`), so a surface
showing one of several shows the first.

A workflow carries a `condition` beside its stage when its evidence has aged or
failed:

- stale delivery: Sent past `PICKUP_GRACE`;
- ended: its pickup's turn was seen to end, by close or by the host's record;
- stale work: a Working claim past its grace, or a pickup in an older turn or one
  nothing has renewed;
- from the response itself: `disconnected` reads stale, `interrupted` and `failed`
  read as named, and `partial` (a turn that completed without a final answer) reads
  ended. Only the input named by the reply's `responds` reads Replying.

A condition belongs to whoever holds the gesture that recovers from it. Stale, ended,
and interrupted conditions offer the user nothing to do, so they stay the agent's. A
terminal host failure hands recovery to the user: it writes the failure its answer
takes, which settles the Stop hook's obligation and leaves an `answered` workflow with
a failed response until the user moves again. A refused send is the user's too: the
browser offers Retry from its own unresolved ledger, with no workflow record. Browser
notices read the current condition, so an old failure is not news after a later
successful answer.

Three nested sets decide what holds the agent:

- `activity.obligations`: workflows with a non-null answer. Only these enter counts.
- `activity.blocking_obligations`: those the cursor has passed that nothing else
  will answer. A `queued` move waits for the turn that opens it, and a `turn` answer
  the open turn has finished is the live carrier's to commit. `leaf status idle`
  refuses over this set.
- `activity.turn_obligations`: blocking moves the open turn has not claimed. A claim
  over the move (`leaf status … --on`) that the open turn wrote since the move's
  pickup is the agent's answer for now; the turn may end over it while background
  workers carry the work. The claim does not carry into the next turn. The Stop hook
  holds the turn over this set.

Ending a turn settles nothing. A delivery's final answer keeps the delivered
`responds` address even when a resolution, the user's ✓, or authored state settled
that move during the turn. Its reply reopens the thread under the ordinary thread rule
(`events.md`) without making the move owed again.

## Declared and observed work

`leaf status` writes and renews the declaration. `--on` names the thread or widget the
work is about, which is how a delivered move reads Working; which input a thread claim
names is `work.work_subject`'s rule. Nothing in a session renews `status.json` once
its turn is over, and workers leave status to the session, so work that outlasts the
turn goes unrenewed until a later turn declares it again.

The App Server observer records typed activity (`working`, `thinking`, `tool`,
`replying`, `awaiting_approval`, `awaiting_input`) for the page's agent. A current
declaration keeps the page's sentence and date, and the observation stands beside it
as `observed` and `observed_kind`; with no declaration, the observation supplies the
sentence. A page-wide observation never refines a message workflow: no host binds a
thinking or tool step to an input. A wait on the user in the agent's own window lasts
as long as its observer; every other step needs renewal within `WORKING_GRACE`. A tool
step is not a tracked background job, and neither an old observation nor a lost
carrier proves a job failed.

A turn belongs to the session, not the page. The Stop hook closes it on every page
the session holds, and an opening advances the same set
(`service.open_session_turn`), each page under its own transaction.

## The hook

The `hook` command runs on Stop, UserPromptSubmit, SessionEnd, and Claude Code's
`PostToolUse`:

- The prompt hook opens the turn, hands over pending input, records `opened` for
  acknowledged unanswered moves, and names the pages that owe something.
- The Stop hook keeps a turn going only for what it owes: owed input arriving as it
  ends, which it hands over, or a page it leaves with no live carrier or with a move
  in `activity.turn_obligations`. Input that owes nothing waits for the watcher. A
  repeated Stop (`stop_hook_active`) has named its debts once and lets the turn end
  unless newly owed input arrived. It continues a turn through
  `Harness.continue_turn`, and stamps `turn_closed` only on a turn it lets end.
- `PostToolUse` names a `leaf wait` a background command started, read off the
  wait's start mark.
- SessionEnd releases the session's claims. `hooks/scripts/loop-guard.py` does this
  directly under each page's lock, without starting `uv`, and runs the CLI for every
  other hook.

`loop-guard.py` fails open: when the CLI cannot answer, the hook says nothing, so a
Leaf bug never blocks a turn. Without the harness the environment implies, nothing is
claimed and the hooks do nothing. Session death is not completion: work status and
desired service stay as they were.

Only a page handed to a user owes a watcher, so the unwatched clause skips a page
carrying `preview.json`, which only `leaf-dev preview` writes. The guard checks the
file's presence rather than validating it, since failing open means saying nothing.

## Carriers

A carrier brings a session's page input into its turns. Each session runs one
carrier for all its pages, separate from the page server; it re-reads the set of
pages on each pass and produces the same envelope on every transport
(`../../references/event-batches.md`, "One envelope on every transport"). The claim
records the harness name, and every later reader rebuilds the harness from it
(`host.claim_harness`) and asks it how the carrier proves itself live and what to
say when it is not. No code outside `host.py` compares the name.

A carrier takes one of three shapes (`host.Harness`):

- **wait**: direct watchers the model runs. Under Claude Code each `leaf wait` ends to
  open a turn, and the prompt or Stop hook hands the batch to that turn and advances
  the cursor; a wait also ends itself just before Claude Code's background limit
  (`Harness.wait_lifetime`). Where nothing carries input by hook, the wait prints the
  batch and `leaf wait --ack <delivery-id>` confirms it and becomes the next watcher.
- **adapter**: one detached process for a Codex task, holding the task's wait lease
  and an adapter lease of its own, since a wait lease alone cannot prove its output
  reaches a later Codex turn.
- **embedded**: a host that drives App Server itself, as the website's per-user
  container does, and starts each turn directly.

### Direct watchers and the nudge

Only a wait carrier stops while its session lives on, so only its harness has a nudge
(`Harness.nudge`). Under Claude Code the nudge is a user message sent through the
session's messaging socket (`host.message_claude_code_session`, which also records
when the session holds or drops such a message). It tells the agent to start an
unnamed `leaf wait`, which stays the one delivery path; the message fires
UserPromptSubmit, so the prompt hook opens the turn and lists the input.

Browser-event admission (`event_endpoint`) nudges when input that needs the agent
(`service.requires_agent_attention`) reaches a page whose claimant holds no wait lease
and whose turn was seen to end. A running turn needs none, since its Stop hook will
not end with the input unpicked. A turn Leaf has only stopped believing in gets none,
since it may still be running. An interrupt fires no Stop, so an interrupted turn is
nudged once the host's record reads `idle`. Each page nudges once per turn ending: a
landed nudge records the ending as `messaged_ending`, so later input after the same
ending sends nothing, and input after a nudge no socket took tries again. Admission is
the only trigger, so input that arrived while the turn ran is the Stop hook's to
report.

### The Codex adapter

The adapter collects available input, then freezes one delivery; input after the
freeze belongs to the next. It carries a delivery one of two ways
(`codex_adapter.py` header):

- Without App Server, it queues the id-only `leaf-delivery` pointer with `codex
  queue` and never calls `turn/start`. A failed or uncertain queue call retries the
  same frozen pointer while the session owns a page. The task answers a queued
  pointer with `leaf thread reply`.
- With App Server, it holds the frozen delivery until the task is idle and starts the
  turn on a connection of its own, which follows that turn to its end. A second
  connection observes the turns Leaf did not start (the user's own work, and a queued
  pointer the task picked up) and passes over any delivery this process is carrying,
  so none is answered twice. Neither connection steers input into a running turn or
  copies a delivery into App Server's queue.

The Codex CLI stays the client for every approval and user-input request. When the
session loses its last page, a collecting or offering record stays in place,
inactive, until the session claims a page again. An accepted delivery has had its
external effect, so the adapter reconciles its remaining page receipts before it
checks ownership and retires.

### Delivery records

Each delivery has one immutable envelope, addressed globally by id, and one mutable
Codex delivery record that moves through collecting, offering, and accepted. After the
freeze the record keeps only the event identities its page receipts need. Once a
page's cursor passes a batch, the record marks it receipted, so re-initializing a page
at the same path cannot revive old transport work; a batch whose events no longer
match its page is retired. Archiving moves only the record under `history/`, and `leaf
delivery read <id>` still resolves the envelope. Abandoning an unaccepted record
(`codex.abandon_codex_delivery`) leaves the envelope in place for a turn whose
acceptance may have raced the failure.

### Embedded App Server

An embedded host sends `turn/start` with the delivery id as `clientUserMessageId`
once the task is idle, and learns its turn id from the response. It then opens the
claim's turn under that id, records the pickup, advances the cursor, holds the task's
wait lease for the container's life, and follows the turn on the connection that
started it. The pickup, the claim's turn, and the streamed activity all carry that
one id, which Codex's hooks name too. A retry reads the durable pickup rather than
starting the event again.

Every Codex carrier opens and closes turns through `codex.TurnFold`, which calls
the same session-wide opening and closing the hooks do. Accepting a delivery only
records which turn took it, so a turn read back after it ended is never reopened. A
client that did not start a turn recovers its delivery from the transcript
(`codex.app_server_delivery_id`); a lost starting connection ends the turn rather
than leaving a gap to read across. How the turn's messages become the reply is
`../../references/host-codex-app-server.md`, "Replies".

### Detached starts

`server start` and `leaf codex start` spawn their process into a session of its own,
so a killed carrier costs only delivery. Both go through `detached`, whose handshake
leaves the commit to the caller; a child whose caller leaves first withdraws what it
started. The claim a start takes is `service.starting_claim`, restored if the start
does not commit unless a successor has replaced it.

## Lifetime

Whether a server stops when its session ends is decided at launch and written in
`service.json`; which lifetime to choose is `../../references/serving-pages.md`, "Page
lifetime". A serve from an agent host records the page's claim; one from a bare shell
claims nothing, and a claim on a `standing` page comes and goes without changing its
service. A successor that arrives before a session server's final recheck keeps that
process; one that arrives later revives the still-enabled service. Neither path
changes the page's work status.

`leaf wait` revives an enabled service whose process has died, once per death, and
says so on stderr. A revival is a start, so it is refused for a page vendored from
another Leaf's runtime (`layer.foreign_runtime`). A page nothing will serve is lost:
no `service.json`, or a revival that was refused or died again. A lost page ends a
wait that names it, and a session's wait once no other live page is left. A disabled
service is not lost, since a stop is the agent's own move and `page init` stops and
restarts a served page around a re-vendor; the wait neither revives nor ends on it.
