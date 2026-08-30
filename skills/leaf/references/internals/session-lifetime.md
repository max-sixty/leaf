# Session lifetime and work claims

status.json is a claim, and a claim never expires on its own: an agent that
stopped watching renders exactly like one that is watching and has nothing to
say, so a comment can sit unread with the page still reading "Claude is
working". The directory therefore also carries what it can prove — a lease only
a live `leaf wait` can hold, the acknowledgement cursor, and whether the owning
session's lifetime stands — and `/api/state` ships those beside the claim, so the
banner can say when
the claim has outlived its evidence. When a wait prints for a
non-working page, it marks the status it writes "handoff", which dates that
claim: after acknowledgement the agent writes its own `leaf status`, so a
handoff mark that survives means a dropped pickup rather than a long turn, and
the banner gives it a much shorter rope. Wait output that lands while the agent
is already working leaves the existing claim untouched; there is no pickup gap
to date.

So a claim of work has to be renewed, and the command that makes one renews it.
`--on` names the comment thread the work is about, so one check-in moves both
the page's line and the note the reader sees under their own words in the
thread panel, where it stands until the agent's next word in that thread. That
is how a claim crosses a turn boundary the session cannot write across: nothing
in a session touches status.json while its turn is over, so work handed to a
delegate is renewed from the delegate's own hands or not at all.

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
this session's pages unwatched, surfaces unacknowledged user events at the next
prompt, and releases the session's page claims when it exits. Session death is
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

A session's leaves cost it one long-running carrier between them, and that
carrier is separate from the page server. Claude Code uses a sequence of direct
watchers: `leaf wait` exits to put a batch in model context, then `leaf ack`
advances its cursor and becomes the next watcher. Codex uses one detached
adapter instead. It holds the same task-wide wait lease, persists the exact
batch it captured, and hands a bounded pointer in a `leaf-delivery` XML element
to Codex's durable same-task queue. It advances the cursor after acceptance and
keeps watching while the foreground turn is over. The already-loaded Desktop
client keeps the task writer, consumes the shared durable queue, and owns every
execution or approval request. Leaf's queue command never resumes or starts the
task. An unloaded task therefore keeps the accepted item standing until the
Codex client reopens it.
The adapter has a second lease because a generic wait lease cannot prove that
its output can enter a later Codex turn; the Stop hook trusts only the pair.
Both carriers watch every page the session holds, re-reading the set on each
pass, and deliver one page's batch under a first line naming the page and
carrying the conversations its events land in.

The Codex delivery intent and its immutable payload live under the host state
home's session records, not in the page. They are transport recovery state: the
document and event log remain the page authority, while the intent preserves one
stable Leaf delivery id and exact pointer prompt across queue acceptance before
cursor acknowledgement. An uncertain queue command is retried with that same
pointer. The resulting delivery is at least once; a repeated turn recognizes
the delivery id and applies the page-and-sequence retry rule. Once a queue
command succeeds, the adapter advances the page cursor and removes the intent.
The payload stays as conservative recovery state because queue acceptance does
not prove that a later turn read it.

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
