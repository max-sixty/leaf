# Conversation loop

Read this before running `leaf wait`, processing a delivered batch, opening or
replying to a thread, or ending a page.

## Status and handoff

Before a handoff, run:

```bash
leaf status <page> waiting "<what you want back>"
```

The detail names the concrete answer or decision, not the fact that you are
waiting. For an informational page with no concrete ask, leave it empty; the
banner then invites the reader to select text to comment. Follow the main
skill's "Return to the user" rule for every chat message.

While the next move is yours the page is `working`. Name the local subject when
the detail is about one open comment thread or page widget:

```bash
leaf status <page> working "reading the reconnect traces" --on <thread-id>
leaf status <page> working "checking the rollout" --on <widget-id>
```

The line stands beside its subject, so a question or card in hand reads
differently from one nobody has looked at even when no conversation exists. A
thread claim ends with your next reply there. A widget claim survives unrelated
revisions; when a stamped version completes that work, say so on the stamp:

```bash
leaf version stamp <page> --text "…" --completes <widget-id>
```

Repeat `--completes` when the version completes more than one active widget
claim. Stamping accepts only widget ids with standing work. `status --on`
refuses a widget whose active registry declaration provides no `x-work` seat;
use the page-wide detail for work with no safe local line. The local line is the
banner's own claim at a second seat, and one status command writes both.

A `working` claim is believed while the turn that wrote it is open. The page is
told when that turn ends, so a claim nothing has renewed within a couple of
minutes of the ending stops being believed, and the banner reports the silence
instead of the work; a claim nobody renews at all ages out after about a
quarter of an hour. Each local line carries the same reading at its own subject,
so one delegate still reporting keeps the banner green while another's line
goes quiet beside the work it names.

Renewing it is therefore part of the work and goes with it: a delegate outlives
the turn that started it, and no part of this session can write the claim once
the turn has ended. Give the delegate the launcher path, the page path, the
subject id, and the command above to run as it starts — soon enough to land
inside that couple of minutes — and again whenever what it is doing changes.

## Host wait loops

One unnamed `leaf wait` watches every page the host session owns. A batch begins
with `{"page": …, "threads": […]}` and continues with that page's events. Name a
page only to pick up a page this session did not serve; `leaf wait <page>` claims
it.

- **Claude Code:** start `leaf wait` as a background task and end the turn. Its
  completion becomes host input. After each batch, start `leaf ack` as the next
  background task; it acknowledges that batch and waits for another.
- **Codex:** start `leaf codex start <page>` after setting the page `waiting`,
  then finish the turn normally. One detached adapter watches every page this
  task owns. It gives each complete batch a stable delivery id, queues it as a
  new user turn in this same task, and acknowledges only after Codex accepts the
  durable queue item. The loaded Desktop client starts that later turn and keeps
  ownership of execution and approvals. If the task has been unloaded, the item
  stays queued until Codex reopens it; the adapter never resumes the task or
  answers client requests on the user's behalf. The small queued message points
  to the exact persisted batch rather than copying an arbitrarily large batch
  into Codex's bounded text input. A later queued turn reads that payload,
  processes it directly, and leaves only `leaf wait` and `leaf ack` to the
  adapter. The turn still owns replies, revisions, and page status, including
  the handoff back to `waiting` or `idle`. Starting the command again for another
  page adds that page to the same task-wide watch.

  If `leaf codex start` refuses to start, do not finish over a live page. Follow
  its diagnostic: an existing foreground `leaf wait` must be stopped before the
  adapter can take the task's single wait lease, and an unavailable Codex queue
  command cannot receive later turns.

An optional separate Codex watcher remains a fallback that requires the user's
explicit authorization because it creates a visible task. Its route is in the
main skill.

The initial `leaf wait` revives a dead server under its recorded lifetime and
reports that on stderr. Its exit 2 means stderr names an ending rather than a
batch. After `leaf ack` advances the cursor, however, its exit stays 0 whether
the rearmed wait delivered or ended; read its streams rather than branching on
that status:

- JSON lines on stdout are the next batch.
- `the leaf ended` or `the leaves ended` on stderr means every page left in the
  watch is idle; `nothing to watch` means the session holds none. End the loop.
- `server is not running` gives the recovery command. After recovery, resume
  the session-wide loop with an unnamed `leaf wait`.
- `this session no longer owns` means a successor has the page. Do not name or
  reclaim it. A rearm keeps watching any other live page; when the observed
  transfer empties that set, it exits with this line.
- Stderr saying another `leaf wait` is already active means the existing
  process still owns the session lease. Leave that watcher running rather than
  starting another.

Empty stdout alone is not evidence that the host stopped the process. Start a
replacement unnamed wait only when the host itself reports that it canceled or
killed the command.

## Batch delivery and acknowledgement

Wait prints one page's unacknowledged events as JSON lines. The first line names
the page and carries `threads`: for each conversation the batch lands in, its
anchor, who closed it if anyone has, what was said in it before this batch, and
the reader's standing gestures on any widget sent in it. A reply event names
only the message it answers, and an action only the widget it was made on; the
exchange behind them is here. A long conversation arrives as its opening message
and its most recent, with `elided` counting what was dropped between, and
`leaf transcript <page>` prints one whole.

Printing is not receipt. The wait owner acknowledges only after the complete
batch reaches its next durable consumer.

In the direct loop, the durable consumer is model context. The Codex adapter
instead owns its wait and acknowledgement. It acknowledges after Codex's queue
accepts the batch; the queued turn reads its named delivery payload and does not
wait or acknowledge. If a queue command has an uncertain outcome, the adapter
retries the same pointer with the same Leaf delivery id. This is at-least-once
delivery and may create a retry turn; the task applies the page-and-sequence
retry rule below.

If wait output is truncated, acknowledge nothing and rerun with enough output
capacity for the whole batch. After the complete batch reaches its next durable
consumer, the wait owner runs `leaf ack <page> <highest-seq>` for the page the
batch's first line names. If output is lost, follow the same rule. A scalar cursor
cannot represent a missing event in the middle. Acknowledgement is monotonic and
idempotent; an event posted between wait and ack has a higher sequence and stays
pending. Ack then waits in the same process. Until ack, wait repeats the batch.
`leaf events` reads the full log without acking it.

Treat a page-and-sequence pair already handled in this task as a retry, even if a
later delivery also includes newer events.

## Process every event

Start `leaf ack` for a direct batch, set the page `working`, and address every
event the wait printed while ack waits for the next batch:

- **Comment:** a comment with `"response": {"kind": "version", "verb": "…"}` takes no reply: incorporate
  it in the next version, then resolve it. If the revision depends on the reader,
  open a separate exact-section thread on the same Decision with
  `leaf comment --section <decision-id>`. Reply to other comments in-thread and revise
  the page when warranted. A comment with `"suggestion": true` proposes exact
  replacement text; take it verbatim or reply with the reason for declining it.
- **Layer comment:** an event with `"about": "layer"` changes the relevant Leaf
  layer, followed by re-vendoring, a valid source activation, and an in-thread reply.
- **Page action:** the reader already sees the action applied. Carry its standing
  state into `index.html`. If you deliberately replace that state, use `restated`
  and explain why when stamping the resulting checkpoint.
- **Reaction:** a `comment` or `reply` carrying `token` in place of `text`, with
  the token's meaning printed beside it as `means`. It is a mark, not a
  question: act on it — revise the passage a `cut` or `lost` stands on, expand
  where `more` stands, take an `ok` as the reader's "seen, go on" — and, once
  the live revision answers it, `leaf resolve` it so its paint
  clears. Reply on the reaction itself only where it puzzles you ("which
  part?"); that reply turns the mark into an ordinary thread. A reaction never
  gates activation or stamping, and an acknowledged one nobody replied to holds no turn.
- **Undo:** read the named event and the undo as one act. Do not answer or record
  the withdrawn gesture. An undone answering action reopens its thread; an
  undone reaction is a mark the reader took back.
- **Page error:** fix the page or widget and save the correction. The event is
  diagnostics, so do not reply unless the reader asked about it.
- **Worker report:** carry the report into markup, or mark its element
  `overruled` and state why. A page must not end with unresolved report debt.
- **Host request:** treat the request id as the host executor's idempotency and
  recovery key. Inspect the host before acting after an interruption, perform the
  package-declared operation at most once, and append exactly one terminal result
  with `leaf receipt <page> <request-id> succeeded|failed --text "…"`. A receipt
  records the external outcome; it does not rewrite the authored page. Refresh
  any bound external data, save the source revision that reflects the result, and
  stamp a checkpoint when it is worth naming.
- **Thread-widget action:** reply in that same thread. A plain options pick
  answers immediately; a `multiple` group answers only when its `answer` action
  arrives, though every toggle is delivered.
- **Done:** treat it as approval of declared sign-off, not closure of the page.

## Threads

Open a thread when the answer depends on the reader. Use a quote for a passage, a
section id for a diagram or image, a declared part for one box within a visual, and no
anchor for the page as a whole:

```bash
leaf comment <page> --quote "<passage in the current page>" --text "…"
leaf comment <page> --section <element-id> --text "…"
leaf comment <page> --section <diagram-id> --part node:<source-id> --text "…"
leaf comment <page> --text "…"
```

`leaf comment` anchors in the active revision and reads it as the user
sees it, including edits and retired content. Quote exact visible authored words
inside one widget part. The command refuses ambiguous, retired, replaced, or
cross-boundary text instead of creating a detached comment.

Use `--markup` for a small question: an `lf-decision` containing one heading and its
`lf-options` group. Thread markup is frozen in the log; versions neither carry
nor revise it. Use a page widget instead when the question and its answer belong
in the final record.

Answer in as few words as the question takes; one sentence is a complete reply.
An answer the size of a page section goes into the page instead, and the
reply is a line pointing at it. The panel is a narrow column, so an answer past a
few sentences goes in as separate Markdown paragraphs or a list with one point
each. `--text` takes a one-line answer; longer text comes in on stdin:

```bash
leaf reply <page> --to <thread-id> --text "Yes, and the page already has it."

leaf reply <page> --to <thread-id> <<'EOF'
Three things put the retry on the client:

- only the client can tell a dropped connection from a slow one
- the client already holds the request body
- retrying on the server would double the write
EOF
```

Fragment links such as `[the decision](#decision)` take the reader to page
content. `--markup` adds a validated widget after reply text; its ids must be new.
An ordinary reply leaves the thread open for follow-up without counting it as an
outstanding decision. Add `--awaits` when the reply's prose asks the reader to answer:

```bash
leaf reply <page> --to <thread-id> --awaits --text "Which store should own it?"
```

A widget whose registry entry declares a local `x-awaits` or
`x-request.decision` decision already joins the page's decision list and keeps its
thread in "Waiting on you" while that decision stands. Leaf refuses `--awaits` beside
such markup; the widget's state or request lifecycle is the one reading.

Correct one of this session's sent messages without adding another turn:

```bash
leaf edit <page> --to <comment-or-reply-id> --text "Corrected wording."
```

The page labels the message `edited`. Leaf keeps the original and every revision
in the append-only event log. Only text is revised; any widget markup stays frozen.

The reader closes a thread by default. Resolve it yourself only when they ask or
when the subject has left the page or the work has plainly answered it. Reply
before resolving:

```bash
leaf resolve <page> --to <thread-id>
```

An acknowledged reader message still requires a reply: acknowledgement only
removes it from future batches.

## Reactions

The reader's cheapest answer is a token: `ok` `no` `lost` `cut` `more` `this`
as the default package ships them, on a passage, an element, the page whole, or
one of your replies. `page state` lists every standing one under `reactions`,
each with its `means`, and the tokens themselves are the page's vendored
`$reactions` (`page catalog`), so a project's own tokens read the same way. An
`ok` on your latest reply request takes the thread out of "waiting on you";
no reply is owed for it. Resolve a page reaction once the live revision has acted
on it.

## Save revisions and stamp checkpoints

Edit `<page>/index.html` directly. Each changed valid save becomes a new immutable
revision and the live root follows it automatically; keep saving while the work
is in motion. If the source is invalid, the last valid revision remains live and
`leaf page state` reports the source diagnostic.

When the page reaches a checkpoint worth naming, stamp the exact current source
with a brief changelog:

```bash
leaf version stamp <page> --text "<what changed>"
```

Leaf assigns the next public version number and maps it to that exact revision.
Do not write `revisions/` or `versions/` yourself. A browser at the live root
follows new revisions; a browser pinned to `/versions/vN.html` stays on that
stamp. Re-enter the host's wait loop after the batch: `waiting` when the reader
owns the next move, `working` while you continue.

## Sign-off and ending

A `done` event approves the work but does not end the page. Keep the page working
and watched while doing what approval unblocked.

To finish, handle every event in the complete delivered batch and make sure every
acknowledged thread that awaits your answer has one. A finished record, including
a quick page that became one, ends on a stamped final revision that honors
standing decisions and reports. An unstamped quick page can go idle directly.
Idling ends the interaction but does not delete the page directory. Sign-off is
available only on a stamped revision. `leaf transcript <page>` prints record
debt on stderr and the full exchange as Markdown.

Then run:

```bash
leaf status <page> idle
```

`idle` is the explicit end of the agent side and refuses pending events or an
answered-by-reader thread still awaiting you. It removes the page from the watch;
the last idle page ends the waiter. A normal session-lifetime server process
retires when the page has no live claim, while its enabled service remains
available for a selected successor to revive; it needs no separate stop. A
standing page has a different lifetime and must not be idled merely because one
session's work is over.
