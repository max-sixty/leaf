# Conversation handoff

## What the reader sees

The reader follows your work on the page:

| Surface | What it shows | Written by |
| --- | --- | --- |
| Banner | one sentence for the whole page: what you are doing, or what you want back | `leaf status <page> <state> "<detail>"` |
| Beside a thread or widget | **Working** and your sentence, above the message or on the control the work answers | `leaf delivery claim`, `leaf status … --on <id>` |
| Thread | your answer to the reader's message | `leaf reply` |
| Page | the revised content in place, and a stamp's changelog | saving `index.html`, `leaf version stamp` |
| Request | the outcome of a request the reader made | `leaf receipt` |

Leaf itself marks each reader move **Sent**, **Queued**, and **Picked up**, including
a move that owes you nothing, such as a moved card. A pick before the Done its Ask
waits for is marked with that Done. Your host
contract may add its own current step to the banner. Chat stays in the host and never
reaches the page.

Two readings in `leaf page state <page>` describe the reader's side between their
moves. `viewed` says whether they are there: the last time a browser tab had the page
visible, in epoch seconds, renewed about every half minute while it stays visible, and
`null` when nobody has opened the page. Each conversation's `unread` says which of your
messages they have not read yet
([conversation threads](conversation-threads.md#what-the-reader-has-read)). A status
has no such reading, so one they have not reacted to may not have been seen.

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

Reader input comes before the work in hand, in this order:

1. Acknowledge the delivery by the host's receipt route, so the reader's moves read
   **Picked up**. Where a package's guidance says to hold the acknowledgement until a
   request reaches its executor, hand the request over first, then acknowledge.
2. Reply to each move that owes a reply, before starting the work it asks for. The
   delivered `answering` clause for a reply says how to write the reply now and how
   to report the result later. A host that sends your final message as the reply
   fixes the reply at the end of the turn instead; its host contract says so.
3. Write the page status again, so the banner describes the work that continues
   rather than the last step before the interruption.

Then do the work.

## Status and handoff

Before a handoff, run:

```bash
leaf status <page> waiting "<what you want back>"
```

The detail names the concrete answer or decision, not the fact that you are
waiting. For an informational page with no concrete ask, leave it empty; the
banner then invites the reader to select text to comment. Every chat message
from here on repeats the page's exact URL (the main skill, "Operate").

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

Use `status --on` for proactive subject work that did not begin with a delivery. An
optional delivery claim names an exact delivered event (`references/event-batches.md`,
"Delivery and acknowledgement").

## Long-running work

New reader input reaches you only between your own operations; your host contract
names exactly when. A long foreground operation, such as a test suite or a subagent
you wait on, leaves the reader's comment unanswered for its whole length.

For work that will run longer than a few minutes, coordinate it rather than perform
it. Hand the reading, editing, and testing to background subagents or background
commands, and end your turn as the host contract says, so the watcher's next delivery
reaches you while the work runs instead of waiting behind it. When a worker reports
back, settle its result with a reply, a revision, or a receipt.

You drive the page and your workers do not. The server, the watcher and its
acknowledgements, replies, receipts, status, edits to `index.html`, and stamps stay
with you, and a worker returns its result to you. A worker touches the page only in a
role Leaf's guidance gives it, and only as that guidance directs: a command hub worker
(`leaf page guidance <page> worker`), or a Codex watcher task
(`references/codex-watcher.md`). Put this in each worker's brief, because a worker that
inherits your conversation inherits the page with it and may otherwise treat the page
as its own. Work that needs its own conversation with the reader belongs to a session
of its own, with its own page.

A `working` claim is believed while the turn that wrote it is open. The page is
told when that turn ends, so a claim nothing has renewed within a couple of
minutes of the ending stops being believed: the banner reports that your turn ended,
and its explanation keeps the claim's words. A claim nobody renews at all ages out
after about a quarter of an hour. Before you end a turn while workers run, make your
last status say what is still running, and write it again in the turn that a worker's
result or the reader's next comment wakes. Within a turn, fold your workers' progress
into your own status: one sentence covering three workers reads better than three
claims competing for one row, while claims on different subjects stand side by side at
the page edge.
