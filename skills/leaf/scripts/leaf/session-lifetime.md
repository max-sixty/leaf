# Session lifetime, pickup, and work claims

`status.json` is a declaration, not current agent state. The current state is
`activity`, one server projection over that declaration and the page's stronger
evidence: claim and turn identity, watcher lifetime, exact pickup transitions,
and unsettled reader moves. `/api/state`, neighboring-page entries, and
agent-facing page state all carry this same projection. Browser code paints it
and requests another reading at its next deadline; it does not run a second fold.

| Fact | Where | Writer | Stops being believed |
| --- | --- | --- | --- |
| work declaration: state, detail, event floor, source message, typed `work` seats | `status.json` | `leaf status`, from the agent's turn or a delegate it hands the command to | a short grace after the turn that wrote it closes; about a quarter of an hour with no renewal; at once when the claimant's lifetime has ended |
| exact delivery handling: event, target, detail, event floor | `handling` in `status.json` | `leaf delivery claim`, derived from an immutable delivery and current page state | when the move settles, another delivered move replaces it, the claim expires, or the claimant's lifetime ends |
| live Codex activity: session, turn, detail, event floor | optional `stream` in `status.json` | the App Server connection that starts an embedded turn, or the detached adapter's observer-only client | turn completion, connection or observer exit, loss of the wait lease, or the working grace without another event |
| live Codex reply: one displayed draft plus delivery attempt bindings by response address | optional `stream.reply` and `stream.reply_bindings` in `status.json` | an App Server connection bound to a delivery's plain reply | the displayed draft remains on failure or disconnect; each binding clears after durable commit or terminal failure, and survives connection and turn transitions until then |
| turn identity and open or closed state | the page's claim record | a prompt or direct delivery opens an opaque `turn`; the Stop hook stamps `turn_closed` | the next opening mints a turn; the next closing stamps it |
| the closed turn this page nudged its session in | `messaged_turn` in the page's claim record | browser-event admission, once the harness's nudge lands | a later closed turn carries a different `turn` |
| wait lease | `waiter.lock`, or `sessions/<id>.wait` for a host session | the live `leaf wait` or `leaf ack` process, held open for its life | process exit |
| acknowledgement cursor | `cursor.json` | `leaf ack`, after the complete batch reached its durable consumer | when its seq is past the log's end, or a fresh log replaces the one it named; monotonic within one log |
| pickup transition | a `pickup` event in `events.jsonl` | an unobserved carrier records `queued` when Codex accepts a batch; an App Server observer records `opened` with session and turn identity when its direct delivery starts | never; each event/phase/session/turn transition is idempotent |
| page claim: session, display name, harness, carrier, lifetime | `~/.local/state/leaf/claims/<page>` | `server start` from an agent host; released by the hook when the session exits | `released` is set, or the lifetime it rests on is gone: the pid, the background job's directory, or — for a host that multiplexes every session into one process, where there is no pid to name — the page going untouched for ACTIVITY_GRACE_SECS, which a *visible* tab's `viewed.json` writes keep renewing — a backgrounded tab closes the news stream and stops renewing |
| service lifetime | `service.json` | `server start` at launch: session, or standing | `leaf server stop`; a session server also retires when no live claim holds it |
| Codex queue state | the host state home's session records | the detached adapter or an embedded App Server host | an unaccepted record is inactive while the session owns no page; an accepted record moves under `history/` after every batch is receipted |
| Leaf delivery | `<state-home>/deliveries/<id>.json` | any carrier freezes the host-neutral envelope before presenting it | never; every transport resolves the same immutable id |

Delivery acceptance is a different fact from authored work, but it is exact agent
activity. These facts project into one reader-facing **Agent workflow**; the browser
does not present delivery status and work ownership as separate categories. Pickup
never rewrites `status.json`. Page activity counts one interaction
per subject and unit, for the newest unsettled reader move on it (a tick and the Done
press that followed are one). A thread's local views may also retain **Working** beside
the earlier message that prompted its standing claim. On the subject's existing target
margin entry or a compact local row, append is **Sent**, then **Waiting for pickup** after the short grace;
Codex acceptance is **Queued**; entry into a named open turn is **Picked up**; a
later `status … --on` claim on the same reader move is **Working**. That same evidence
makes page activity **queued**, **handling**, or **picked up; turn ended**. A reply,
resolution, or authored state that honors the move settles the interaction; a later
version note settles a page action whose verb has no authored record form, and a note
already standing when the move arrives cannot answer it.

The activity fold defines precedence once. An unsettled opened interaction outranks
a `waiting` declaration, so a receipt cannot say **Picked up** while the banner says
the agent awaits the reader. A fresh `working` declaration whose recorded event floor
reaches the standing obligations is current work. If newer interactions are only
**Queued**, an otherwise current declaration or live Codex activity remains visible
alongside them and the banner names both facts; the older event floor does not claim
that work has started on the queued input. Turn identity, not elapsed time, decides
whether opened delivery belongs to the turn now running.
Fresh activity from the claimed Codex task's App Server is an observation bound to one
turn and event floor, not a second work declaration. It can make a page working over a
declaration that says otherwise, because it proves a session is alive and moving. It
does not say what the work is: a current `working` declaration keeps the reading's
sentence and its own date on every host, and the observed step is reported beside it as
`observed`. `delivery claim` given no detail writes one of Leaf's own so a taken-up move says so at
once, and marks it `stated: false`; a watched step whose own floor reaches the newest
input knows more than that wording and takes the sentence back, while an older step
leaves it standing. Where no current declaration stands, the step is the sentence,
and the declaration becomes current again when the turn or observer ends.

A work declaration has to be renewed, and `leaf status` renews it. `--on` names the thread
or widget the work is about. `leaf delivery claim` instead records one event from an
immutable delivery after checking under the page lock that the exact move remains
outstanding; it never transfers a claim to newer input on the same subject. A thread
claim also records the current unanswered message,
so one check-in keeps **Working** beside the words that prompted the work even when the
reader adds another comment. Widget work appears on the Target margin entry. These
readings stand until the agent's next word in that thread. Nothing in a session touches `status.json`
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
interaction projection the browser reads; it does not reconstruct conversations
itself. The App Server adapter presents at most one plain reply in each turn's
chronological delivery slice. Its completed final-answer item finishes that exact
response; the hook lets the provider turn close, and the observer commits the same text
through the canonical reply writer when the terminal notification arrives. Version
and request obligations still record their explicit resolution or receipt before Stop
can consider them answered.
When the prompt hook opens a turn, it records a new `opened` transition for its
acknowledged, unanswered moves. A plugin-free embedded host records the same
transition from the queued turn's App Server `turn/started` notification. A
direct-delivery move that needs a reminder is also named in the hook context. A
queued Codex move needs no reminder there: the prompt itself carries its delivery
pointer, while the transition gives the browser and the next Stop their shared
handling fact.
Session death is not completion or an explicit stop: work status and desired
service stay as they were, while a session server retires once no live successor
has claimed it. Absent the harness the environment implies, nothing is
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
the page server. Each harness declares which of three it uses, and its claim
records that with the page, so a reader elsewhere acts on the carrier rather
than on the harness's name:

- `wait`, a sequence of direct watchers the model itself runs, which Claude Code
  uses: `leaf wait` exits to put a batch in model context, then `leaf ack`
  advances its cursor and becomes the next watcher.
- `adapter`, one detached process, which Codex uses: it holds the same task-wide
  wait lease plus an adapter lease of its own, and stores exact batches from
  every page in one task-wide delivery.
- `embedded`, a host that drives App Server itself, which the website's
  per-reader container uses: it starts the turn directly and needs nothing
  between them.

Every carrier watches every page the session holds, re-reading the set on each
pass, and produces the same `leaf-delivery-v1` envelope. Each batch names its
page, monotonic `through_seq`, conversation context, layer handling, and complete
ordered events.

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

In Codex, the adapter collects available input, then freezes the delivery. Input
collected after that boundary belongs to a later delivery. Without an App Server
observer, it hands the bounded id-only `leaf-delivery` pointer to Codex's durable
same-task queue. A failed or uncertain queue call retries the same frozen pointer while
the session owns a page. With an observer, Leaf retains the frozen delivery in its own
offering state until the task is idle, then starts it directly; it does not also copy
the delivery into App Server's queue. Losing the session's final page leaves the
collecting or offering record standing but inactive until the same session claims a
page again. Acceptance has crossed the external-effect boundary, so its remaining page
receipts are reconciled before the adapter checks ownership and retires.
If every website startup retry fails, its deterministic fallback settles the
triggering event and removes the unaccepted queue record. The immutable payload
remains at its permanent path for a turn whose acceptance may have raced the failed
response.

Each delivery has one globally addressed immutable envelope and one mutable adapter
queue record. The queue record carries collecting, offering, or accepted state;
after the freeze it retains only the event identities needed for page receipts.
Once a cursor advances, the
queue record records that receipt so
reinitializing the same page path cannot revive old transport work; a
reinitialized page whose events no longer match retires its old batch. The
adapter has a second lease because a generic wait lease cannot prove its output can
enter a later Codex turn. Leaf's unobserved queue command never calls `turn/start`. An
App Server observer instead resumes the task, subscribes to notifications, and waits
for the active turn to complete before starting the frozen delivery itself. The CLI
remains the interactive client for every approval and user-input request.
Once every batch is acknowledged, only the queue record moves under `history/`;
`leaf delivery read <id>` continues to resolve the immutable envelope.

An embedded host that already controls App Server can deliver the same immutable
envelope directly with `turn/start` when the task is idle. After App Server accepts
the turn, the host records the delivery against its Leaf claim turn, advances its
page cursor, holds that task's wait lease for the container host's lifetime, and
keeps the initiating connection for activity notifications. The pickup names
Leaf's claim turn, while streamed activity names App Server's task and turn; each
projection reads the identity its own fold compares. A retry reads the durable
pickup instead of starting the event again. If the task is active, the host queues
the same delivery locally for a later direct start instead of using page input as
steering or adding it to App Server's queue. Its subscription spans the active turn,
the delivery turn's opening, and that turn's terminal notification, recording both
`opened` and the exact turn close. A host
that owns a starting connection closes only the matching Leaf claim turn on its
terminal notification. A direct start carries the delivery id as its client message id
and retains the structured delivery in the transcript. The transcript therefore
restores the same binding after a lost subscription. The adapter keeps the delivery's
chronological prefix through the first
plain reply and leaves any later plain reply for the next turn. The connection streams
the assistant final message into that thread and commits the completed message through
the ordinary reply operation. The delivery address survives a turn close or a later
turn opening; those turn transitions govern activity, not response ownership. Version
and request responses remain explicit. This is another carrier over the same
delivery, page claim, event log, and activity projection, not another conversation
store or response policy.

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
