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

| Fact                                                                   | Where                                                                                           | Writer                                                                                                                                                                                                                                | Stops being believed                                                                                                                                                                                                               |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| page declaration: `waiting` or `idle`                                  | the newest `status` event (`activity.declaration`)                                              | `leaf page open` and `leaf page close`; the website harness as it ends a turn, and as it starts one on an idle page                                                                                                                   | the next declaration; for `idle`, also a start after it, which reopens the page                                                                                                                                                    |
| the item in hand: an update or to-do, its line, the turn that wrote it | a `start` event, or an ephemeral reply's start (`todos.start_reading`)                          | `leaf task start`, or `leaf thread reply --ephemeral` on an owed update                                                                                                                                                               | the item ending; a later `status` event; as a belief, when its turn is seen to end unless the harness says work goes on in the background, a quarter of an hour without renewal, or when the lifetime ends                         |
| live App Server activity: session, turn, kind, detail                  | `activity` in `stream.json`                                                                     | the App Server connection following the turn                                                                                                                                                                                          | turn completion, connection or observer exit, loss of the wait lease, or the working grace without another event                                                                                                                   |
| live App Server reply, and reply reservations                          | `reply` and `reply_reservations` in `stream.json`                                               | an App Server connection bound to a delivery's reply                                                                                                                                                                                  | the draft, once a logged event names its attempt or address; a reservation, at commit, at terminal failure, or once its turn is no longer the claim's open turn (`activity.reply_reservation_stands`)                              |
| turn id, `turn_opened`, `turn_closed`                                  | the session lifecycle record (`state.py`)                                                       | a prompt, an App Server client, Codex's transcript (`codex_transcript.py`) or an explicit reader acknowledgement opens or renews the turn, under the harness's id where it names one; the Stop hook or an App Server client closes it | the next opening of another id; a closed id never reopens                                                                                                                                                                          |
| the harness's word on the session, dated                               | the harness's own record, read live (`Harness.live_turn`)                                       | the harness                                                                                                                                                                                                                           | read live; absent where the harness publishes nothing                                                                                                                                                                              |
| the turn ending this page last nudged its session after                | `messaged_ending` in the claim                                                                  | `PageTransaction.note_messaged`, once a nudge lands or a watch wakes the session                                                                                                                                                      | a later ending differs from it                                                                                                                                                                                                     |
| wait lease                                                             | `waiter.lock`, or `sessions/<session>.wait` for a harness session                               | `leaf wait`, or a harness's watch between turns; the kernel lock proves it live, never the file (`leases.py`)                                                                                                                         | process exit, a crash included, or a later watch superseding it; and by a Leaf at a later page protocol than the one the file names, which that watch can't read (`leases.wait_is_live`)                                           |
| the harness runs Leaf's hooks for this session                         | `sessions/<session>.hooks`                                                                      | every Leaf hook                                                                                                                                                                                                                       | SessionEnd                                                                                                                                                                                                                         |
| acknowledgement cursor                                                 | the greatest `through` among `receipt` events (`transaction.acknowledged`)                      | `delivery.receive_batch` or `delivery.receive_passed`, called by whatever confirms a delivery reached its consumer                                                                                                                    | never; it only advances within its log                                                                                                                                                                                             |
| pickup transition                                                      | a `pickup` event                                                                                | `queued`: Codex's adapter, when Codex accepts a batch it can't observe; `opened`, with session and turn: whatever puts the batch into a turn                                                                                          | never; each transition is idempotent                                                                                                                                                                                               |
| page claim: acquisition, session generation, display name, harness     | `<state-home>/claims/<page-key>.json`, located from the session's partition (`page-storage.md`) | `server start` from an agent harness, or its prompt hook serving the page again                                                                                                                                                       | its generation ended or was replaced, or the harness lifetime is gone: the pid, the background job's record, the Claude desktop app's record of the session, or a desktop Codex chat's native transcript (`service.session_lives`) |
| service lifetime                                                       | `service.json`                                                                                  | `server start`: session or persistent                                                                                                                                                                                                 | `leaf server stop`; a session server also retires when no live claim holds it                                                                                                                                                      |
| Codex delivery record                                                  | `sessions/<session>.deliveries/`                                                                | the adapter, or an embedded App Server harness                                                                                                                                                                                        | moves under `history/` once every batch is receipted, and goes at the next scan that finds all its pages gone (`codex.py`)                                                                                                         |
| Codex adapter log                                                      | `sessions/<session>.codex.log`                                                                  | the adapter, begun afresh at each adapter start                                                                                                                                                                                       | removed when the adapter retires owning no page                                                                                                                                                                                    |
| Leaf delivery                                                          | `<state-home>/deliveries/<id>.json`                                                             | whatever presents a delivery freezes it first (`delivery.freeze_delivery`)                                                                                                                                                            | removed by the sweep each page server runs as it starts, once every page it names is gone                                                                                                                                          |

### Activity

Activity says where the agent's side of the page stands in the words every record
uses (`standing.py`): `state` is `running`, `blocked`, `waiting` or `done`, with the
`reason` a blocked one is and the `next_actor` whose move changes it. Beside it,
`presence` says whether anyone is there to take input: `here`, `away` between turns,
`gone` when no session holds the page, or `closed`. It describes the claimant and its
watcher, not any one message.

Every rule that asks whether the claimant's turn is running reads one answer,
`activity.claimant_turn`, which dates each piece of evidence and lets the newest
decide. Its docstring says how the harness's own record adds what no hook sees: an
interrupt, a dialog open now, and that the session is busy, in its turn or, after
the turn closed, in the background. The fold counts busy as observed work, so a
page reads `running` while its Claude Code turn runs, whatever the agent has started.
Browser-event admission reads the same answer (`presence.claimant_reading`) and
nudges only after an ending something saw, since a turn Leaf merely stopped believing
in may still be running a long step.

The claimant takes input while its wait lease is held or, where its harness's hooks
carry input, while its turn runs (`activity.takes_input`). Admission nudges a
claimant that takes none once its turn was seen to end (`activity.nudge_due`), and
where its harness says that nudge starts a turn (`Harness.input_wakes`), the page
reads it as taking input too. Fresh declared or observed
work makes the page `running`, however far newer input has progressed, and so does a
delivery opened into the running turn before its first start. The status line is the
newest start's among the items still in hand, and the page is `blocked` once those
starts have gone quiet or their turn ended. An owed update is stranded when it stalled
with the agent to act: `undelivered` past the pickup grace, or `stopped` or
`interrupted` by a turn that ended before answering. Where nobody is `here`, a stranded
update makes the page `blocked` with the user as its next actor, and the status asks
them to nudge the session.

Observed App Server activity (`working`, `thinking`, `tool`, `replying`,
`awaiting_approval`, `awaiting_input`) refines the page's work and never a message's,
since no harness binds a step to an input. A current authored declaration keeps the
page's sentence and date; the observation is served beside it as `observed` and
`observed_kind`, and supplies the sentence only where the declaration has none. A step
that waits on the user in the agent's own window makes the page, and whatever that
turn has in hand, `blocked` with reason `terminal`. A tool invocation is not a tracked
job, so neither an old observation nor a disconnected client proves that a job failed.

### Workflows and obligations

`workflows.py` owns both readings of the updates the user has handed over: each
unsettled update's workflow, the evidence of its delivery, and each owed update's
obligation record, which says who owes it a move. Its header says when each settles.
`activity` says where each workflow stands, and each record stands where the strongest
workflow serving it does. The served list names each workflow's `thread`, strongest
first (`work_state.served_workflows`).

A workflow waits until a turn has taken it in (`seen`), and after, until the agent
starts it. It is `running` while a start stands on it, while its reply streams in
(reason `replying`), or while a progress message of the agent's stands after it in
its thread, such as a line fork's working line (`work_state.lined`). It is
`blocked` where evidence shows it has stopped moving:

- `undelivered`: no harness has carried it past the pickup grace.
- `stopped`: the exact turn that took it in was seen to end, by its close or the
  harness's record, with an answer still owed, or the start on it no longer holds
  (`activity.start_holds`). It does not claim an interruption.
- `quiet`: a start unrenewed past its lease, or a pickup in another or older
  turn, or in one nothing has renewed within the working grace.
- `terminal`: the turn that started it waits on the user in the agent's own window.
- A provisional reply moves only the input its `responds` names, by its own state:
  `quiet` when disconnected, `interrupted`, `failed`, or `stopped` for a turn that
  completed without a final answer. `response` names the delivery attempt.

Browser notices read the current standing and its source, so an old failure is not
news after a later answer, and work gone quiet is not a failed response. These readings
leave recovery with the agent. Only a terminal harness failure hands it to the user,
through the failure answer `thread.fail_answer` writes, which leaves the update
`blocked` with reason `failed` and the user as its next actor.

Each consumer selects its own obligations. `leaf page close` refuses over
`activity.blocking_obligations`, and the Stop hook holds the turn over
`activity.turn_obligations`, the blocking ones no start holds. A start is the agent's
answer for now. It holds its update while the
turn that wrote it runs, and after that turn while the harness says the session has
worked without a break since the start, in the background (`activity.start_holds`).
A harness that says nothing of the session (`Harness.live_turn`) never does, so
there a start lapses with its turn.
The page reads the update in hand, and no prompt or wake reminds the agent of it,
for exactly that long. Only the records the agent owes enter activity counts. Pickup never declares a status, and
ending a turn settles none of its input.

A start names one item and has to be renewed: it is a lease on the item, held by the
turn that wrote it. Work that outlives that turn, such as a delegate, a background
command or a wait on CI, is whatever else holds the lease: another session's start, or
the claimant's background work while its harness reports some. Such a job has no record
of its own; its item reads `running` while the lease is renewed and `blocked` once it
lapses (`standing.py`). What stays owed across turns is the to-do itself, which no turn
or session ending lapses (`todos.py`).

### Turns and generations

A turn's stamps and generation belong to the session's one lifecycle record, so no
opening or ending rewrites a claim (`state.py`). That module alone reads the stamps
as a phase: no turn yet, open, closed, or ended, which closes the turn too. Every
other reader, of the record or of a claim's view of it, asks `state.turn_open`,
`state.turn_closed` or `state.session_live`, and every opening refuses a turn id the
record holds closed. `state.end_harness_instance` says
which generations SessionEnd ends and which, such as a desktop Codex chat's or a
background job's, outlive the harness instance. A command acts in its session's turn
whoever ran it, a subagent the session spawned included (`state.acting_turn`).

Where nothing answers for the declaration, activity reports the agent `gone`. A page
with a persistent service spends most of its life unheld, and picks up again when a
session takes it.

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
  lease and a lease of its own (`codex_run.py`). In the desktop app, an IDE
  extension and a plain terminal, Leaf can't reach Codex's App Server. A desktop chat
  a window of the app has opened takes each delivery as a turn the app starts, with no
  message in the user's name (`codex_desktop.py`). Anywhere else the adapter queues it
  as the task's next message with `codex queue`. There Leaf
  reaches the task only through its hooks, its transcript and those two offers, and
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
  turn, for each owed update no start holds (`activity.turn_obligations`).
  Where a watch follows the turn, the turn ends on its answer, and the watch wakes a
  turn of its own that names an owed update once per delivery (`session.left_owed`).
- A page carrying `preview.json` owes no watcher for its status, since only a page
  handed to a user does.
- A hook hands a delivery over inline only where the harness will show the model all
  of it (`Harness.fits_hook_context`) and, for Claude Code and Pi, the hook records it
  before its deadline. Otherwise it hands over a pointer the agent confirms with
  `leaf delivery ack`.
- Under Claude Code, the prompt and tool-boundary hooks also carry the lines Leaf
  queued for the session's next step in `sessions/<session>.clerk`, and take each off
  the queue once printed (`clerk.py`). A line that tells the session of work it now
  owes wakes it: the watch wakes for it once the turn has closed, following that file
  itself since no page's reading stamps it.

`delivery.py` owns receipt: when each harness's hook output counts as read, and how a
handover the turn never confirmed becomes input again. Session death is neither
completion nor an explicit stop, so work status and the desired service stay as they
were.

### Serving again at the next prompt

Before it opens its turn or reads a page, the prompt hook serves again, as
`leaf server start` would, each page the session still means to serve whose ownership
or server is down, such as a resumed session's (`reconnect.py`, which lists the
exclusions). The turn hears only of a page that did not start.

### Nudging a session with no watcher

A watcher the session's own turns start can stop while the session lives on: a watch
fails or reaches its hook's timeout, or a model-run wait is stopped after the turn
ends. Claude Code's prompt hook starts a watch as each turn starts, so a turn an
interrupt ends still has one, except a turn whose prompt came before the session
held any page: its watch ended at once, so nothing watches once that turn claims a
page and is interrupted. Input that reaches the page after that has no watcher, and
the claimant's harness may offer a nudge, the one way to reach such a session.

Admission sends a nudge when an event is appended to a page whose claimant takes no
input, once per ending of its turn (`delivery.nudge_unwatched`). An interrupted turn
runs no hook, so Claude Code also starts the watch as each prompt starts, which waits
while that turn runs and wakes for what an interrupt leaves (`hooks.cmd_watch`). Where
no watch holds the lease, the page's server sends for the input an interrupted turn
left once its presence look reads the turn ended by the harness's record
(`server_rows.nudge_interrupted`). Claude Code's nudge is a user message through the session's messaging socket
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
Leaf cannot serve (`registry.storage.layer_record`). A page nothing will serve is lost:
never served, or one whose revival was refused or died again. A refused revival leaves
the service enabled until `server stop`. A lost
page ends a wait that names it, and a session's wait once no other live page is left,
with the `leaf server start` command that serves it. A watch between turns ends then
without waking the session, leaving the page to the next prompt. A stopped service is
not lost (`session.Watch`): the wait watches it without reviving it until the page goes
idle or changes hands.

### Which Leaf runs a session

A session's hooks, watch, pages follower and bare `leaf` commands run the copy of
Leaf its harness loaded, whose `bin/leaf` its hooks run, and a Codex task's adapter
starts from that copy too, the only one that claims for the session. Claude Code
installs each update as a new copy and keeps a running process on the copy it loaded
until `/reload-plugins`, or until a new process of the session, such as a resume or
a background job's wake, loads the update. Codex and Pi each keep one copy and
update it in place, so the session's next hook runs the update. A path names no
version there, so Leaf identifies a copy by its path and commit
(`state.installed_copy`, `layer.payload_provenance`).

Each hook records the root of the Leaf it runs (`leases.mark_root`). At the
session's next hook, a page at an older protocol is renewed (`layer-registry.md`,
"Page protocol"). The skill the agent read is the harness's to renew: Leaf tells
the agent nothing when an update or a merge changes it (`commands/hooks.py`).
`server start` from another Leaf restarts a page's server under that one at the
same address (`hosting.start_page`).

A command acts for the session its environment names only from a Leaf that runs
that session: an installed copy, as the copy the session loaded is, or a checkout
the session's hooks run, as one Claude Code loads in place is (`state.runs_session`).
Any other Leaf, such as a checkout's `bin/leaf` run from the session's shell, acts
for no session, as a command from a bare shell does (`harness.session_harness`),
from the session's first command on. The user chose that developing Leaf works as
developing any project does, so that Leaf's version, page protocol included, never
reaches the session: it claims nothing, writes none of the session's records, and
serves a page unclaimed, which its own `leaf wait` hears, as `leaf server start`
and `leaf server run` then say (`serves-for-no-session`). The server's row names the
session whose shell started it (`server_rows`), so the session's line above Claude
Code's prompt lists the page beside those the session holds (`hooks.cmd_pages`). A
page the session holds it treats as another session's.

Only the session holding a page, through its own Leaf, serves the page or changes
its layer record, its server up or down (`service.refuse_held`); another session
takes the page over first by claiming it. Whether a claim holds its page comes from
its session's record alone, whatever harness the claim names
(`service.held_elsewhere`). So no other Leaf moves a held page to a protocol its
session's hooks can't read, whatever the two protocols are.

A Leaf reads a session's lifecycle record and its claims only at its own shapes,
and reads a page as held while a claim of another shape stands, or a lifecycle of
another shape for a claim's session whose generation this Leaf's record doesn't name
(`service.page_holder`). So across an update that changes either record's
shape, the session's pages stay held: no terminal re-initializes them, no `leaf wait`
takes their input, and another session takes them only by claiming them, which ends
the claim at every shape (`service.publish_claim`). One that changes the lifecycle's
shape meets the session as a resumed one: its first prompt under the new Leaf starts
a generation and serves its pages again (`reconnect`). One that changes the claim's
shape leaves the new Leaf no claim of the session's to read, so nothing follows its
pages to the new copy and their input waits until the session takes each again with
`leaf server start`, which the refusals of its other commands on the page name. A
session that ended under the older Leaf leaves that Leaf's lifecycle standing, so its
pages stay held for the newer one until an agent's session takes each over the same
way.

A page server or Codex's adapter from an installed copy outlives the hooks that start
it, and asks on each pass which copy should run it now (`state.LoadedCopy.successor`):
the installed copy that the hooks of the session it serves last ran, where that is
another, as after Claude Code moves the session onto an update, or else the copy
Codex or Pi puts in place of its own. It then has that copy take over from it. A
watch between turns asks only whether another copy was put in place of its own,
since under Claude Code each turn's hooks start a new watch from the session's copy,
and the newest watch supersedes an older one (`session.watch_between_turns`). A
process from a checkout follows no copy.

An update that moves the page protocol leaves the session's pages at the old one.
The restart of each page's server renews the page first, as the session's next hook
would (`vendoring.follow_copy`), and the renewal restarts the server itself; the
successor adapter or watch delivers the page's input once the renewal lands. What
holds a renewal back is queued for the session's next step, and wakes an idle session
where a watch runs between turns.

A server whose service is persistent, or whose page a live session holds, has the copy
it follows restart it at the same address, for the session holding the page where one
does, and serves meanwhile (`server_lifetime.stop_when_service_ends`). The adapter
releases its leases and starts a successor from the copy it follows. It holds the
task's start lock until the successor holds its leases and its transport answers, so a
claim meanwhile waits and then joins the successor (`codex_run.py`). Until then, a hook that
reads the adapter lease without the start lock finds no adapter. Pi's watch lets its
lease go and execs the new copy's watch with the payload that started it, so the
process Pi's extension started stays the one it reads and stops (`hooks.main`).
Until the new watch takes the lease, a reader finds no watch, and the new watch's
first pass reads the input that arrived meanwhile.

### A session's files

Every file a session keeps in the state home's `sessions/` carries its name
(`state.session_file`), and its end removes those nothing will read again
(`state.end_session`). While a claim still names the session, its lifecycle and
session lock stay, since the page shows that session's turn from the lifecycle, and
so does the record of the Leaf its hooks last ran (`leases.mark_root`), which a
resumed process's page servers and commands read before its first hook. A
session holding no claim on a page that still stands (`state.held_claims`) loses every
file no other process holds a lock on, so a lease still held, such as a watch's, stays
with its holder. A session that never used Leaf ends without writing a file, and one
whose harness died without a SessionEnd keeps its files.

### Starting a server

`server start` prepares delivery before it acquires the page, so a newly ready Codex
adapter can't retire for lack of pages during the handoff; `leaf page claim` prepares
the harness's delivery and then publishes the claim without serving. Persistent and
temporary serves prepare no delivery. An explicit watcher passes `--manual-delivery`
before its first `leaf wait` in the same turn, and only a prompt hook, serving a page
again, starts an adapter.

A serving producer holds the page's transition lock from bind through acceptance, so a
second start or a stop waits for it and never adopts an uncommitted listener. A
refusal or cancellation before acceptance leaves the previous claim, service and
preview watcher as they were. The lock order is page, then session
(`transaction.PageTransaction.publishing_claim`): the commit publishes the service and
then the claim, and does no harness or network work while it holds them. Each acquisition has its own id,
so a rollback compares claim publications rather than lifecycle fields or timestamps.
`hosting.claim_and_start` and `detached.py` own the handshake that accepts a start and
the cleanup an unconfirmed one leaves.

Taking new input from a page needs the session's claim active, but recording what the
session's task already took or answered there needs only that the claim names the
session and the session has not ended (`service.claim_names_session`).

### Adapter lifetime

Desktop Codex unloads an idle instance without ending the chat, so an existing chat
keeps its server and adapter across inactivity and unload, and loses them only on
archive, deletion or transfer. Its startup hook captures the chat's native
transcript (`codex_transcript.py`), without which a new desktop start owns nothing
(`state.chat_exists`).

The adapter follows the session's page ownership, not the pages' declarations, and
retires once ownership ends (`codex_run.py`).
