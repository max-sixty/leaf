# Session lifetime, pickup, and work claims

status.json is a claim, and a claim never expires on its own: an agent that
stopped watching renders exactly like one that is watching and has nothing to
say, so a comment can sit unread with the page still reading "Claude is
working". The directory therefore also carries what it can prove — a lease only
a live `leaf wait` can hold, the acknowledgement cursor, and whether the owning
session's lifetime stands — and `/api/state` ships those beside the claim, so the
banner can say when the claim has outlived its evidence.

Delivery acceptance is a different fact from work. Once a direct wait has
flushed its batch, or Codex's durable queue has accepted it, the carrier appends
one page-owned `pickup` event naming the reader event ids it delivered. Retries
name nothing new, so pickup is idempotent. It never rewrites `status.json` and
therefore cannot claim the agent has begun work, replace an existing claim, or
make one interaction borrow another's page-wide status.

The browser projects one acknowledgment per subject and unit, for the newest unsettled
reader move on it (a tick and the Done press that followed are one). On the page it
reuses the subject's existing Target Button; the full thread panel and widgets frozen
into conversation chrome use a compact local row because they have no page edge.
Append is **Sent**; a `pickup` naming that move is **Picked up**; a later explicit
`status … --on` claim on the same subject is **Active**. Sent becomes **Waiting for
pickup** after the short pickup grace, without inventing a new log state. A reply,
resolution, or authored state that honors the move settles the acknowledgment. A
later version note settles a page action whose verb has no authored record form; a
note already standing when the move arrives cannot answer it. The append-only log
remains the authority for every durable phase.

So a claim of work has to be renewed, and the command that makes one renews it.
`--on` names the comment thread the work is about, so one check-in moves both
the page's banner and its Target Button, plus the local receipt the reader sees
under their own words in the full thread panel. They stand until the agent's next
word in that thread. That is how a claim crosses a turn boundary the session cannot
write across: nothing in a session touches status.json while its turn is over, so
work handed to a delegate is renewed from the delegate's own hands or not at all.

A claim also has an end the page can observe rather than outwait. The Stop hook
stamps `turn_closed` on the claim record when the turn that could have renewed it
ends, and the banner stops believing a claim older than that stamp after a short
grace — much shorter than the claim's own, because it is reached by evidence
instead of by a clock. The opening of the next turn is stamped by the
prompt hook, which fires with the turn already running whatever caused it, and
by the carrier that delivers a batch — the latter only where that carrier's
handoff is the opening. A direct wait's is: it exits with the batch in model
context, so it clears the stamp under the same lock the batch left under. The
Codex adapter's queued handoff is not: its pointer waits in a durable queue that
a loaded client starts and an unloaded task leaves standing, so it leaves the
stamp alone. The prompt hook opens the claim when the turn actually starts and
puts the current delivery epoch in model context. Input that arrives later joins
that epoch without another queued message. Stop carries the same pointer and
keeps the claim open; the re-entered Stop confirms that offer and closes the turn
when no newer batch has arrived. The prompt also covers the reader who answers
where the banner sent them — a nudge in the terminal leaves no batch for any
carrier to hand over. Both stamps are the session's rather than the page's, and
both span its pages: the Stop hook closes the turn on every page the session
holds, so an opening reopens that same set, each page under its own transaction.
Without that clearing the page reads a session that came back and worked as one
that walked away, and tells the reader to nudge a turn that is running — a leaf
whose own batch was never the one delivered included.

Where nothing answers for the claim at all, the banner drops the claim rather
than repeating it. A claimant whose lifetime has ended settles the question
outright; a page nothing ever claimed has only the claim's own age to go on, so
it falls to the same grace period. Either way the page is unheld, and the banner says
that instead — "no session holds this page" is a fact the banner computed, where
"Claude is working" would be a fortnight-old sentence someone else wrote. Unheld
is also not a fault: a page that stands for weeks (below) spends most of its
life unheld, and picks up again the moment a session takes it.

The `hook` command closes the same gap from the agent's side. Registered on
Stop, UserPromptSubmit and SessionEnd, it refuses to let a turn end with one of
this session's pages unwatched, stamps that turn's ending and the next one's
opening, surfaces unacknowledged user events at the next prompt, and releases
the session's page claims when it exits. Session death is
not completion or an explicit stop: work status and desired service stay as they
were, while a session server retires once no live successor has claimed it. It
finds the session's pages through the claim records under
~/.local/state/leaf/claims/. A record is keyed by its resolved page path and
retains the last claimant as provenance after release; `released: null` and a
live lifetime — the process its pid names, or the job directory a background
job records — are what make it active. Absent the host identity the environment
carries, nothing is claimed and the hooks stand down. What the environment
cannot carry is the session's own lifetime, and `session_lifetime` says where
each host's lifetime comes from. `hooks/scripts/loop-guard.py`, which the hosts
actually run, decides none of that: it runs this command under `uv` and stays
silent when it cannot get an answer, so every rule above has one reading and a
leaf bug costs a turn nothing. Unacknowledged events are the one
thing `leaf status <page> idle` can't close over: idling is how a leaf ends, and
one can't end on comments nobody read.

Only a page handed to a reader owes a watcher, so the unwatched clause passes
over a page carrying `preview.json` — a developer preview, put up to be looked
at. Nothing else about that page changes: a delivery it has not taken, or a
comment nobody answered, is reported as on any other. It reads the file's
presence rather than the serve path's validating reader, because this guard fails
open by saying nothing, and an exit inside it would take every page the session
holds down without a word.

A session's leaves cost it one long-running carrier between them, and that
carrier is separate from the page server. Claude Code uses a sequence of direct
watchers: `leaf wait` exits to put a batch in model context, then `leaf ack`
advances its cursor and becomes the next watcher. Codex uses one detached
adapter instead. It holds the same task-wide wait lease and stores exact batches
from every page in one task-wide delivery epoch. The first batch after a turn ends
hands a bounded `leaf-delivery` pointer to Codex's durable same-task queue. Input
arriving before that queued turn starts joins the same payload without another
message. An unloaded task therefore keeps one accepted item standing while its
payload grows, until the Codex client reopens it.

The page claim says whether the task's last turn has ended. While its turn is open,
the adapter adds input to the current epoch and queues nothing. The prompt and Stop
hooks put the pointer in model context. A prompt which gets there before an unissued
queue item consumes that item, because its context has already opened the task with
the same pointer. The prompt hook has no delivery receipt, so Stop offers that input
again unless an accepted queue already carries it. A Stop offer records how many
batches it carried. `stop_hook_active` confirms that offer on re-entry; input added
after it produces another offer, while no newer input closes the epoch and turn.
An active epoch with input newer than its accepted queue snapshot returns to the
same queued-pointer path after fifteen minutes without another hook. This recovers
an interrupted turn; a long-running turn may receive the at-least-once retry.

The Stop hook locks every currently owned page in stable path order before it
locks the session delivery state. It captures and acknowledges all input already
behind those page locks, then either keeps the turn open or marks it closed. An
event append that reaches a page first joins the active epoch; one that reaches it
after the hook releases the page sees the closed session and opens the next queued
epoch. The adapter takes locks in the same page-then-session order. This boundary
does not depend on a debounce interval or on the adapter's polling cadence. Because
the turn belongs to the task, a closed stamp on any one of its pages is also enough
to preserve that boundary if Stop was interrupted while stamping multiple pages.

The visible pointer is one line in a code block. It names the `$leaf` skill,
whose current copy owns the processing contract. Its epoch file carries each
batch's page, URL, thread context, and exact events. Each queue, prompt, or Stop
offer first refreshes every batch for one page to that page server's current URL.
The adapter acknowledges a queued epoch after queue acceptance and an in-turn batch
after durable epoch storage.
The already-loaded Desktop client keeps the task writer, consumes the shared
durable queue, and owns every execution or approval request. Leaf's queue command
never resumes or starts the task.
The adapter has a second lease because a generic wait lease cannot prove that
its output can enter a later Codex turn; the Stop hook trusts only the pair.
Both carriers watch every page the session holds, re-reading the set on each
pass, and deliver one page's batch under a first line naming the page and
carrying the conversations its events land in.

Codex delivery epochs live under the host state home's session records, not in the
page. Each file is one transport authority: whether its queue was accepted, how
many batches that queue covered, how many the last Stop offer covered, whether the
epoch is closed, when its last input or hook transition occurred, and the batches
themselves. The sole unclosed file is the current epoch. Page claims remain the turn
authority and page cursors remain the receipt authority during a page's lifetime.
Once a cursor advances, its batch records that receipt so reinitializing the same
page path cannot revive old transport work or block receipts still due on another
page. A reinitialized page whose events no longer match terminally retires its old
batch, so it cannot starve receipts for the task's other pages. An uncertain queue
command retries the same file pointer. Delivery is therefore at least once; a repeated
turn recognizes the id in the filename and applies the page-and-sequence retry rule.
Once a file is closed and every batch has a receipt, it moves under `history/`: the
record remains durable while the adapter's one-second live scan reads only actionable
epochs.

`server start` spawns the service into a session of its own and hands back the
URL that process printed and the lifetime it recorded — so a killed carrier
costs only delivery and leaves every page up. A direct-loop recovery is one
`leaf wait`; a Codex recovery is one `leaf codex start <page>`.

Whether a session's end reaches a server is decided at launch and written in
service.json as its lifetime. A serve from an agent host records the page's
claim under the state home's claims directory. Claim replacement and release
cross the page transaction: a
successor arriving before the session server's final recheck keeps that process;
one arriving afterward finds the old process and lease already gone and revives
the still-enabled service. Neither path changes the page's authored work status.
A serve from a bare shell — a terminal, a launchd job — claims nothing, and that
is the standing serve: a long-lived dashboard someone leaves open for weeks.
`server start --standing` makes the
same statement from inside a host: the launch declines the claim, for a page
meant to outlive the session that starts it. No daemon is involved, and a server
that dies under a `leaf wait` watching an enabled page is revived with the
lifetime and exact URL in service.json. `leaf server stop` is a standing
server's one reaper, and that is the whole of what "standing" means. A session
that picks the page up later owes it a watcher while the session lives, exactly
as it would any page. Its claim comes and goes without changing the standing
service or the page's status.
