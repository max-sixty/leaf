# Session lifetime, pickup, and work in hand

This file says how Leaf decides who holds a page, what the agent is doing on it, and
how the user's input reaches the agent's turn. "Page activity" is the server's one
reading of the agent's work. "Watchers" is how each harness carries input into a turn,
and what the hooks hold a turn over. "Lifetime" is how serving, claims and services
begin and end. Each section names the modules whose headers own the detail; Codex's
delivery records and App Server clients belong to `codex.py`, `codex_adapter.py` and
`codex_state.py`.

## Page activity

`activity` (`activity.py`) is the one fold of the agent's current state on a page. It
reads the agent's declarations, the log's `status` and `start` events, against
stronger evidence: claim and turn identity, watcher leases, pickup events and
unsettled updates. `/api/state`, agent-facing page state, the hooks and
`leaf page close` all read this fold. The browser paints it and asks for another
reading at its next deadline; it never folds the evidence itself. Another page reads
it only from the row the page's server publishes (`server_rows.py`), beside that
server's lease.

The table lists each fact the fold reads, and when it stops being believed.

| Fact                                                                   | Where                                                                                           | Writer                                                                                                                                                                                                                           | Stops being believed                                                                                                                                                                                                                  |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| page declaration: `waiting` or `idle`                                  | the newest `status` event (`activity.declaration`)                                              | `leaf page open` and `leaf page close`; the website harness as it ends a turn, and as it starts one on an idle page                                                                                                              | the next declaration; for `idle`, also a start after it, which reopens the page                                                                                                                                                       |
| the item in hand: an update or to-do, its line, the turn that wrote it | a `start` event, or an ephemeral reply's start (`todos.start_reading`)                          | `leaf task start`, or `leaf thread reply --ephemeral` on an owed update                                                                                                                                                          | the item ending; a later `status` event; as a belief, a short grace after its turn closes, about a quarter of an hour after its turn was last seen running, or at once when the claimant's lifetime ends                              |
| live App Server activity: session, turn, kind, detail                  | `activity` in `stream.json`                                                                     | the App Server connection following the turn                                                                                                                                                                                     | turn completion, connection or observer exit, loss of the wait lease, or the working grace without another event                                                                                                                      |
| live App Server reply, and reply reservations                          | `reply` and `reply_reservations` in `stream.json`                                               | an App Server connection bound to a delivery's reply                                                                                                                                                                             | the draft, once a logged event names its attempt or address; a reservation, at commit, at terminal failure, or once its turn is no longer the claim's open turn (`activity.reply_reservation_stands`)                                 |
| turn id, `turn_opened`, `turn_closed`                                  | the session lifecycle record (`state.py`)                                                       | a prompt, an App Server client, Codex's transcript (`codex_state.py`) or an explicit reader acknowledgement opens or renews the turn, under the harness's id where it names one; the Stop hook or an App Server client closes it | the next opening of another id; a closed id never reopens                                                                                                                                                                             |
| the harness's word on the session: `idle`, `waiting` or `busy`, dated  | the harness's own record, read live (`Harness.live_turn`)                                       | the harness                                                                                                                                                                                                                      | read live; absent where the harness publishes nothing                                                                                                                                                                                 |
| the turn ending this page last nudged its session after                | `messaged_ending` in the claim                                                                  | `PageTransaction.note_messaged`, once a nudge lands or a watch wakes the session                                                                                                                                                 | a later ending differs from it                                                                                                                                                                                                        |
| wait lease                                                             | `waiter.lock`, or `sessions/<session>.wait` for a harness session                               | `leaf wait`, or a harness's watch between turns; the kernel lock proves it live, never the file (`leases.py`)                                                                                                                    | process exit, a crash included, or a later watch superseding it                                                                                                                                                                       |
| when the harness last ran a Leaf hook for this session                 | `sessions/<session>.hooks`                                                                      | every Leaf hook                                                                                                                                                                                                                  | SessionEnd                                                                                                                                                                                                                            |
| acknowledgement cursor                                                 | the greatest `through` among `receipt` events (`service.acknowledged`)                          | `delivery.receive_batch`, called by whatever confirms a delivery reached its consumer                                                                                                                                            | never; it only advances within its log                                                                                                                                                                                                |
| pickup transition                                                      | a `pickup` event                                                                                | `queued`: Codex's adapter, when Codex accepts a batch it can't observe; `opened`, with session and turn: whatever puts the batch into a turn                                                                                     | never; each transition is idempotent                                                                                                                                                                                                  |
| page claim: acquisition, session generation, display name, harness     | `<state-home>/claims/<page-key>.json`, located from the session's partition (`page-storage.md`) | `server start` from an agent harness                                                                                                                                                                                             | its generation ended or was replaced, or the harness lifetime is gone: the pid, the background job's record, the Claude desktop app's record of the session, or a desktop Codex chat's native transcript (`service.lifetime_is_live`) |
| service lifetime                                                       | `service.json`                                                                                  | `server start`: session or persistent                                                                                                                                                                                            | `leaf server stop`; a session server also retires when no live claim holds it                                                                                                                                                         |
| Codex delivery record                                                  | `sessions/<session>.deliveries/`                                                                | the adapter, or an embedded App Server harness                                                                                                                                                                                   | moves under `history/` once every batch is receipted, and goes at the next scan that finds all its pages gone (`codex.py`)                                                                                                            |
| Codex adapter log                                                      | `sessions/<session>.codex.log`                                                                  | the adapter, begun afresh at each adapter start                                                                                                                                                                                  | removed when the adapter retires owning no page                                                                                                                                                                                       |
| Leaf delivery                                                          | `<state-home>/deliveries/<id>.json`                                                             | whatever presents a delivery freezes it first (`delivery.freeze_delivery`)                                                                                                                                                       | removed at a later freeze once every page it names is gone                                                                                                                                                                            |

### Activity

Activity's `kind` is `closed`, `unheld`, `away`, `listening`, `working` or `stalled`.
It describes the claimant and its watcher, not any one message.

Every rule that asks whether the claimant's turn is running reads one answer,
`activity.claimant_turn`, which dates each piece of evidence and lets the newest
decide. Its docstring says how the harness's own record adds what no hook sees: an
interrupt, a dialog open now, and background work after the turn closed.
Browser-event admission reads the same answer (`presence.claimant_reading`) and
nudges only after an ending something saw, since a turn Leaf merely stopped believing
in may still be running a long step.

The claimant takes input while its wait lease is held or, where its harness's hooks
carry input, while its turn runs (`activity.takes_input`). Admission nudges a
claimant that takes none once its turn was seen to end (`activity.nudge_due`), and
where its harness says that nudge starts a turn (`Harness.input_wakes`), the page
reads it as taking input too. Fresh declared or observed
work makes the page `working`, however far newer input has progressed, and so does a
delivery opened into the running turn before its first start. The status line is the
newest start's among the items still in hand. `counts.overdue` counts the owed updates
that stalled with the agent to act: still Sent past the pickup grace, or left by a turn
that ended before answering. On an `away` page, these are what the status asks the
user to nudge the session about.

Observed App Server activity (`working`, `thinking`, `tool`, `replying`,
`awaiting_approval`, `awaiting_input`) refines the page's work and never a message's,
since no harness binds a step to an input. A current authored declaration keeps the
page's sentence and date; the observation is served beside it as `observed`,
`observed_kind` and `awaiting`, and supplies the sentence only where the declaration
has none. A tool invocation is not a tracked job, so neither an old observation nor a
disconnected client proves that a job failed.

### Workflows and obligations

`workflows.py` owns both readings of the updates the user has handed over: each
unsettled update's workflow, whose `stage` reports its delivery, and each owed update's
obligation record, which says who owes it a move. Its header says when each settles.
The served list names each workflow's `thread` and whether the agent is `at_work` on
it, strongest first (`served_state.work.served_workflows`).

`activity` adds a `condition` where evidence shows a stage has stopped, and keeps the
durable stage:

- `stale` delivery: still Sent past the pickup grace.
- `ended` work: the exact turn the update was picked up in was seen to end, by its
  close or the harness's record. It does not claim an interruption.
- `stale` work: a Working start quiet past its lease once its turn stops running, or
  a pickup in another or older turn, or in one nothing has renewed within the working
  grace.
- A provisional reply makes only the input its `responds` names Replying, and its own
  state sets that input's condition: `stale` when disconnected, `interrupted`,
  `failed`, or `ended` for a turn that completed without a final answer. `response`
  names the delivery attempt.

Browser notices read the current condition and its source, so an old failure is not
news after a later answer, and stale work is not a failed response. These conditions
leave recovery with the agent. Only a terminal harness failure hands it to the user,
through the failure answer `thread.fail_answer` writes.

Each consumer selects its own obligations. `leaf page close` refuses over
`activity.blocking_obligations`, and the Stop hook holds the turn over
`activity.turn_obligations`, the blocking ones the open turn has not started. A start
is the agent's answer for now, and it does not carry into the next turn. Only the
records the agent owes enter activity counts. Pickup never declares a status, and
ending a turn settles none of its input.

A start names one item and has to be renewed. What holds work across turns is the
to-do itself, which no turn or session ending lapses (`todos.py`).

### Turns and generations

A turn's stamps and generation belong to the session's one lifecycle record, so no
opening or ending rewrites a claim (`state.py`). `state.end_harness_instance` says
which generations SessionEnd ends and which, such as a desktop Codex chat's or a
background job's, outlive the harness instance.

Where nothing answers for the declaration, activity reports the page `unheld`. A page
with a persistent service spends most of its life unheld, and picks up again when a
session takes it.

A developer user preview can select the runtime that delivers for its session
(`session_runtime.py`); page servers keep their own.

## Watchers

Each session runs one watcher for all its pages, apart from the page servers. The
watcher holds the session's wait lease between turns and brings the pages' input into
the next turn. The claim names the harness, and a reader rebuilds the harness from that
name (`harness.claim_harness`) to ask what proves its watcher live, rather than
comparing the name. A watcher is one of:

- **A hook watch under Claude Code**: a second Stop registration (`--watch`) that
  Claude Code keeps in the background (`asyncRewake`), which wakes the session by
  exiting 2 (`hooks/scripts/background-watch.py`). It is a hook because Claude Code
  bounds a background command at two hours and a hook only by its `timeout`.
  `session.watch_between_turns` says what it wakes for and when, and
  `Harness.watches_between_turns` why plain `--print` has none.
- **A hook watch under Pi**: the same watch, which Leaf's extension (`hooks/pi.ts`)
  starts as the session starts and as each run settles. When the watch exits with input
  and no run is going, the extension starts one.
- **A model wait**: `leaf wait` runs the model starts itself. Every explicit wait prints
  the delivery; a large one comes in parts, and after the last part
  `leaf delivery ack <delivery-id> && leaf wait` advances the cursor and starts the
  next wait, which names the page again where no harness session holds it.
- **The adapter**: one detached process per Codex task, holding the task's wait
  lease and a lease of its own (`codex_adapter.py`). In the desktop app, an IDE
  extension and a plain terminal, Leaf can't reach Codex's App Server, so the adapter
  queues each delivery as the task's next message with `codex queue`. There Leaf
  reaches the task only through its hooks, its transcript and that queued message, and
  has no more control over a turn than under Claude Code. A task that inherits
  `LEAF_CODEX_APP_SERVER`, as a terminal started by `leaf codex launch` does, connects
  the adapter to its App Server instead, where Leaf starts turns without a message and
  follows each turn's items. That route is experimental
  (`../../skills/leaf/references/codex-setup.md`).
- **The host**: a harness that drives App Server itself, as the website's container
  does, starting each turn directly (`codex.py`).

Every watcher watches every page the session holds, and every transport hands over the
same envelope (`../../skills/leaf/references/event-batches.md`, "One envelope on every
transport"). What a watcher delivers is `delivery.deliverable`, which includes the
updates a page's previous owner received and left unanswered.

### The hook

Each harness registers its hooks in `hooks/hooks.json`, `hooks/codex.json` or
`hooks/pi.ts`, passing its name to `leaf hook --harness`, and the hook takes the
session from its payload (`harness.hook_harness`). `hooks.py` owns what each hook does
before it reads a page. SessionEnd runs `leaf session-end`, which `bin/leaf` hands to
`state.py`'s standalone stdlib entry. `hook_transport.py` owns what the prompt,
tool-boundary and Stop hooks hand into a turn:

- Stop continues a turn for a page of the session's that has no running watcher and
  holds pending input or a status other than idle, and, where no watch follows the
  turn, for each owed update the turn has not started (`activity.turn_obligations`).
  Where a watch follows the turn, the turn ends on its answer, and the watch wakes a
  turn of its own that names an owed update once per delivery (`session.left_owed`).
- A page carrying `preview.json` owes no watcher for its status, since only a page
  handed to a user does.
- A hook hands a delivery over inline only where the harness will show the model all
  of it (`Harness.fits_hook_context`) and, for Claude Code and Pi, the hook records it
  before its deadline. Otherwise it hands over a pointer the agent confirms with
  `leaf delivery ack`.

`delivery.py` owns receipt: when each harness's hook output counts as read, and how a
handover the turn never confirmed becomes input again. Session death is neither
completion nor an explicit stop, so work status and the desired service stay as they
were.

### Reconnect notices

Session-start and prompt hooks repeat `leaf server start <page>` for a page whose session
service is enabled but whose ownership or server is down (`reconnect.py`, which lists
the exclusions). The Stop hook never continues a turn to deliver one.

### Nudging a session with no watcher

A watcher the session's own turns start can stop while the session lives on: a watch
fails or reaches its hook's timeout, or a model-run wait is stopped after the turn
ends. Claude Code's prompt hook starts a watch as each turn starts, so a turn an
interrupt ends still has one, except a turn whose prompt came before the session
held any page: its watch ended at once, so nothing watches once that turn claims a
page and is interrupted. Input that reaches the page after that has no watcher, and
the claimant's harness may offer a nudge, the one way to reach such a session.

Admission sends a nudge when an event is appended to a page whose claimant takes no
input, once per ending of its turn (`presence.nudge_unwatched`). An interrupted turn
runs no hook, so Claude Code also starts the watch as each prompt starts, which waits
while that turn runs and wakes for what an interrupt leaves (`hooks.cmd_watch`). Where
no watch holds the lease, the page's server sends for the input an interrupted turn
left once its presence look reads the turn ended by the harness's record
(`presence.nudge_interrupted`). Claude Code's nudge is a user message through the session's messaging socket
(`harness.message_claude_code_session`), whose docstring says when the recipient holds
it; a background job whose worker has retired is resumed with the message as its next
prompt instead (`harness.resume_claude_code_job`). The adapter and the host declare no
nudge and need none: each queues or starts turns itself.

## Lifetime

Whether a session's end reaches a server is decided at launch and written in
`service.json`; which lifetime a serve chooses is `../../skills/leaf/references/serving-pages.md`,
"Page lifetime". A serve from an agent harness records the page's claim, and a serve
from a bare shell claims nothing. A claim on a persistent page comes and goes without
changing its service. A successor that arrives before a session server's final recheck
keeps that process, and one that arrives later revives the still-enabled service.
Neither changes the page's authored work status.

`leaf wait` revives an enabled service whose process has died, once per death, and
notes it (`server-restarted`). A revival is a start, so it is refused for a page this
Leaf cannot serve (`layer.incompatible_layer`). A page nothing will serve is lost:
never served, or one whose revival was refused or died again. A refused revival leaves
the service enabled until `server stop`. A lost
page ends a wait that names it, and a session's wait once no other live page is left,
with the `leaf server start` command that serves it. A stopped service is not lost
(`session.Watch`): the wait watches it without reviving it until the page goes idle or
changes hands.

### A session's files

Every file a session keeps in the state home's `sessions/` carries its name
(`state.session_file`), and its end removes those nothing will read again
(`state.end_session`). While a claim still names the session, its lifecycle and
session lock stay, since the page shows that session's turn from the lifecycle. A
session holding no claim on a page that still stands (`state.held_claims`) loses every
file no other process holds a lock on, so a lease still held, such as a watch's, stays
with its holder. A session that never used Leaf ends without writing a file, and one
whose harness died without a SessionEnd keeps its files.

### Starting a server

`server start` prepares delivery before it acquires the page, so a newly ready Codex
adapter can't retire for lack of pages during the handoff; `leaf page claim` prepares
the harness's delivery and then publishes the claim without serving. Persistent and
temporary serves prepare no delivery. An explicit watcher passes `--manual-delivery`
before its first `leaf wait`, and hooks start no adapter in that interval.

A serving producer holds the page's transition lock from bind through acceptance, so a
second start or a stop waits for it and never adopts an uncommitted listener. A
refusal or cancellation before acceptance leaves the previous claim, service and
preview watcher as they were. The lock order is page, then session
(`service.publishing_claim`): the commit publishes the service and then the claim, and
does no harness or network work while it holds them. Each acquisition has its own id,
so a rollback compares claim publications rather than lifecycle fields or timestamps.
`hosting.claim_and_start` and `detached.py` own the handshake that accepts a start and
the cleanup an unconfirmed one leaves.

Taking new input from a page needs the session's claim active, but recording what the
session's task already took or answered there needs only that the claim names the
session and the session has not ended (`service.claim_names_session`).

### Adapter lifetime

Desktop Codex unloads an idle instance without ending the chat, so an existing chat
keeps its server, preview and adapter across inactivity and unload, and loses them
only on archive, deletion or transfer. Its startup hook captures the chat's native
transcript (`codex_state.py`), without which a new desktop start owns nothing
(`state.chat_exists`). A desktop user preview detaches its input watcher for the same
reason (`dev/leaf_dev/commands/preview.py`).

The adapter follows the session's page ownership, not the pages' declarations, and
retires once ownership ends (`codex_adapter.py`).
