# Conversation handoff

Read this before handing a page to the user or marking work in progress. The
main skill routes waiting, delivered events, threads, and ending to phase-specific
references.

## What the reader sees

The reader follows your work on the page:

| Surface | What it shows | Written by |
| --- | --- | --- |
| Banner | one sentence for the whole page: what you are doing, or what you want back | `leaf status <page> <state> "<detail>"` |
| Beside a thread or widget | **Working** and your sentence, above the message or on the control the work answers | `leaf delivery claim`, `leaf status … --on <id>` |
| Thread | your answer to the reader's message | `leaf reply` |
| Page | the revised content in place, and a stamp's changelog | saving `index.html`, `leaf version stamp` |
| Request | the outcome of a request the reader made | `leaf receipt` |

Leaf itself marks each reader move **Sent**, **Queued**, and **Picked up**. Your host
contract may add its own current step to the banner. Chat stays in the host and never
reaches the page.

## When to write

Write a step's status before starting the step, and write it again whenever the reader
would describe what you are doing differently: a new subject, or a new phase such as
reading, editing, testing, or waiting on a result.
Folding the write into the command that begins the step costs no extra tool call:

```bash
leaf status <page> working "running the browser suite against the new banner" && <command>
```

Name the operation and its subject in one sentence. "Working on it" tells the reader
nothing the banner's dot does not already say.

Reader input takes priority over the work in hand. Claim it first, so the receipt
beside the reader's own words says you have it, and answer it or say on the thread what
you are doing about it. Then write the page status again, so the banner describes the
work that continues rather than the last step before the interruption.

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

The claim then stands beside its subject at the page edge as well as in the
banner, so a question in hand reads differently from one nobody has looked at. A
thread claim ends with your next reply there. A widget claim survives unrelated
revisions; when a stamped version completes that work, say so on the stamp, once
per completed widget:

```bash
leaf version stamp <page> --text "…" --completes <widget-id>
```

Stamping accepts only widget ids with standing work. `status --on` refuses a
widget with neither an unsettled action receipt nor an active `x-work` seat; use
the page-wide detail when neither admits a local claim.

An inline delivery advances each included reader move to **Picked up** and the page
to **handling** when it enters this turn. A queued pointer remains **Queued** until your
host contract's own confirmation step opens it; reading its envelope alone does not.

UI feedback is the first operation for every delivery:

```bash
leaf delivery claim <delivery-id>
```

The command atomically selects the first delivered reader move that is still
outstanding, writes `working` with “Reading your feedback,” and strengthens that exact
move's receipt to **Working**. It changes nothing when a retry contains no outstanding
reader move. For a queued pointer, run `delivery read` only after this claim. An inline
delivery already carries the envelope and needs no read.

After reading the feedback, a more specific claim can name the exact delivered event:

```bash
leaf delivery claim <delivery-id> --event <event-id> --detail "checking the rollout"
```

Use `status --on` for proactive subject work that did not begin with a delivery. Do not
write `waiting` merely to end the delivery step. Write it after replies, revisions, or
receipts have settled what this turn took in; until then the canonical activity
fold continues to report the stronger exact handling evidence.

## Long-running work

New reader input reaches you only between your own operations; your host contract
names exactly when. A long foreground operation, such as a test suite or a subagent
you wait on, leaves the reader's comment unanswered for its whole length.

For work that will run longer than a few minutes, coordinate it rather than perform
it. Hand the reading, editing, and testing to background subagents or background
commands, and end your turn as the host contract says, so the watcher's next delivery
reaches you while the work runs instead of waiting behind it. Keep the replies and
`index.html` yourself, so one writer revises the page. When a reader move started the
work, reply before you end the turn with what you started and where its result will
appear: that is the answer the move is owed until the result exists. When a worker
reports back, settle its result with a reply, a revision, or a receipt.

A `working` claim is believed while the turn that wrote it is open. The page is
told when that turn ends, so a claim nothing has renewed within a couple of
minutes of the ending stops being believed, and the banner reports the silence
instead of the work; a claim nobody renews at all ages out after about a quarter
of an hour.

One writer owns the reader's reading of the work, and it is whoever is running. While
you are still in the turn, keep it yourself and tell each worker you are doing so: a
worker's report is yours to turn into one sentence, and one sentence covering three
workers reads better than three claims competing for one row. When you end the turn
while work continues, nobody in this session can write, so hand each worker the launcher
path, the page path, its subject id if it has one, and the status command to run as it
starts — soon enough to land inside that couple of minutes — and again whenever its step
changes. A thread claim written after your reply stands until your next reply there, and
claims on different subjects stand side by side at the page edge.
