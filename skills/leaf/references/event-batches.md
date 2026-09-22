# Delivered event batches

## One envelope on every transport

Every carrier presents the same immutable object:

```json
{
  "format": "leaf-delivery-v2",
  "id": "a1b2c3d4",
  "created_at": 0,
  "batches": [
    {
      "page": "/absolute/page",
      "through_seq": 12,
      "conversations": [],
      "handling": {},
      "events": []
    }
  ]
}
```

The id is eight lowercase hexadecimal characters and addresses this envelope in the
machine's immutable delivery store.

Some hosts deliver it inline; others deliver a pointer that `leaf delivery read <id>`
resolves to the same object. Your host contract names which. These differ only in
transport. Process every batch and every event.

Each event retains its stored identity, fields and order, less the browser's
retry key `attempt`, then adds these delivery readings:

- `subject` is the stable page, conversation, or widget the event changes.
- `says`, when present, maps each element a widget gesture names to its words: the
  ids in an action's or report's `meaning.depends`, or the widget a request was made
  on. The words are the authored ones in the document the reader pressed on, which
  is the revision the event names or the frozen message that sent the widget, so a
  later version that rewords an element does not change them. They are that
  document's words and not a reading of the rendered page: what an earlier gesture
  changed, and what a widget's module draws beyond its authored text, are not in
  them. An element a reader wrote, such as an added option, is in no document: the
  event's own `detail` carries the words the reader gave it. An element that only
  encloses another named one is left out, so a pick says its options and a gesture
  naming only its widget says the whole widget. An undo carries the words of the
  gesture it takes back.
- `conversations` lists every conversation the event belongs to. Membership is
  many-to-many: it provides context and never partitions or duplicates the event.
- `obligation`, when present, freezes what response was required at capture. Its
  `as_of_seq` is evidence age and `response` is an addressed operation. `reply`
  names an event or conversation and takes `leaf reply`, or the turn's final
  message where the host binds it ("After the batch"). `version` names a
  conversation and takes a page revision closed with `leaf resolve --to` a message
  of that thread. `receipt` names a request and takes `leaf receipt`. Re-read
  current state before writing because later evidence may already have settled the
  requirement. A reply response carries both `to`, the conversation address to write
  under, and `for`, the exact event whose obligation the write must still satisfy.
- `handling`, when present, lists clause ids in the batch's `handling` object,
  in the order to read them. That object gives each distinct instruction's text
  once; ids belong only to that batch. Follow every named clause for this event.
  The vendored layer supplies its kind's clauses whose condition the event meets,
  so a plain comment is not told how to read a drawing and a page widget's pick
  is not told how a thread answers. A missing or invalid registry leaves the
  event's `handling` out and the batch's object empty rather than substituting
  another layer's rules.

The batch-level `conversations` carry each needed anchor, closure state, earlier
messages, and standing gestures on sent widgets. A long conversation includes
its opening and most recent messages, with `elided` counting omitted records.
Use `leaf conversation read <page> <conversation-id>` for an exact, bounded
current reading and paginate with `--after`; use `leaf events <page>
--conversation <conversation-id>` only for raw-log diagnostics. `leaf transcript
<page>` is the human-facing Markdown export.

A reaction carries its token, plus `means` when its package defines one.

Long-thread context may include `summary_hint`; a pointer-only host can surface the
same suggestion as XML. It names a contiguous message range to consider summarizing.
Treat it as navigation maintenance alongside the reader's request, not a request to
resolve the thread. Follow
[conversation threads](conversation-threads.md#summarize-a-long-discussion): read
the covered originals, write the summary, and keep outcomes in the document.

## Delivery and acknowledgement

Run `leaf delivery claim <delivery-id>` before anything else, including the
`delivery read` a pointer needs. It atomically selects the first delivered reader move
that is still outstanding, writes `working` with "Reading your feedback", and
strengthens that move's receipt to **Working**; a retry with no outstanding move
changes nothing. After reading the feedback, a more specific claim can name the exact
event in hand:

```bash
leaf delivery claim <delivery-id> --event <event-id> --detail "checking the rollout"
```

Printing is not receipt. The wait owner acknowledges only after the complete
batch reaches its next durable consumer, which in the direct loop is model context.
Acknowledge with `leaf ack <page> <through_seq>` for the page the batch names, by the
route the host contract gives, and address every event while ack waits for the next
batch. If wait
output is truncated or lost, acknowledge nothing and rerun with enough output
capacity for the whole batch;
a scalar cursor cannot represent a missing event in the middle. Acknowledgement
is monotonic and idempotent; an event posted between wait and ack has a higher
sequence and stays pending. Until ack, wait repeats the batch. `leaf events`
reads the full log without acking it.

Whatever the host, treat a page-and-sequence pair already handled in this task as a
retry, even if a later delivery also includes newer events; your host contract owns
the wait and acknowledgement route.

`leaf wait`, and `leaf ack` once its cursor has advanced, ends one of two ways: exit 0
with one JSON envelope on stdout, the next input, or exit 2 with the ending named on
stderr. Exit 1 from `leaf ack` means the acknowledgement was refused and the cursor
did not move. The initial wait says on stderr when it revived a dead server. The
endings:

- `the leaf ended` or `the leaves ended`: every page left in the watch is idle.
  `nothing to watch`: the session holds none. End the loop.
- `server is not running`: the line gives the recovery command. After recovery,
  resume with an unnamed `leaf wait`, which cannot reclaim a page transferred
  meanwhile.
- `this session no longer owns`: a successor has the page. Do not name or reclaim
  it. A rearm keeps watching any other live page, and exits with this line once the
  transfers empty that set.
- another `leaf wait` is already active: that process holds the session's lease.
  Leave it running rather than starting another.

Empty stdout alone is not evidence that the host stopped the process, and no reason
to run a named wait again. Resume with an unnamed wait only when the host itself
reports that it canceled or killed the command, or on a signal your host contract
names.

An embedded MCP App changes where the page is drawn, not this carrier. Its
events enter the same log, and a successful `ui/message` response is not a
delivery receipt.

## After the batch

Acknowledgement is transport receipt, not semantic settlement. Record every
still-current obligation with the Leaf operation its `response` names, then
re-enter the host's wait loop: `waiting` after every obligation has been answered and
the reader owns the next move, `working` while you continue. When the active host binds
a plain reply to its turn, the normal assistant final message is that operation; an
unbound delivery uses the explicit operation.
`page state` lists every standing reaction under `reactions`; a package-supplied
`means` appears when present. Resolve a page reaction once the live revision has
acted on it.
