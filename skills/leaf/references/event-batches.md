# Delivered event batches

Read this after a direct wait or Codex delivery produces a batch and before
processing any event in it.

## What a batch carries

Wait prints one page's unacknowledged events as JSON lines. The first line names
the page and carries two readings:

- `threads`: for each conversation the batch lands in, its anchor, who closed it
  if anyone has, what was said in it before this batch, and the reader's standing
  gestures on any widget sent in it. A reply event names only the message it
  answers, and an action only the widget it was made on; the exchange behind them
  is here. A long conversation arrives as its opening message and its most
  recent, with `elided` counting what was dropped between. When the missing
  records matter, `leaf events <page> --thread <thread-id>` prints the exact
  JSONL records, and `leaf transcript <page>` is the human-facing Markdown export.
- `handling`: for each event kind present in the batch, what the layer asks of
  you. The sentences are the page's vendored `$events.handling`, so a project
  layer can restate one kind and its pages say so. A reaction also carries its
  token's `means` beside it.

Then each event, one per line. Address every one of them; `handling` is the rule
for each kind, and this reference is the mechanism around it.

## Delivery and acknowledgement

Printing is not receipt. The wait owner acknowledges only after the complete
batch reaches its next durable consumer. In the direct loop that consumer is
model context: start `leaf ack <page> <highest-seq>` as the next background task
for the page the first line names, set the page `working`, and address every
event while ack waits for the next batch. If wait output is truncated or lost,
acknowledge nothing and rerun with enough output capacity for the whole batch;
a scalar cursor cannot represent a missing event in the middle. Acknowledgement
is monotonic and idempotent; an event posted between wait and ack has a higher
sequence and stays pending. Until ack, wait repeats the batch. `leaf events`
reads the full log without acking it.

In Codex the detached adapter owns wait and acknowledgement; `host-codex.md`
owns that route. Whatever the host, treat a page-and-sequence pair already
handled in this task as a retry, even if a later delivery also includes newer
events.

An embedded MCP App changes where the page is drawn, not this carrier. Its
events enter the same log, and a successful `ui/message` response is not a
delivery receipt.

## After the batch

An acknowledged reader message still requires a reply: acknowledgement only
removes it from future batches. Re-enter the host's wait loop once the batch is
handled: `waiting` when the reader owns the next move, `working` while you
continue. `page state` lists every standing reaction under `reactions`, each
with its `means`; resolve a page reaction once the live revision has acted on it.
