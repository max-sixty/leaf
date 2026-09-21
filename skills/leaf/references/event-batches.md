# Delivered event batches

Read this after your host produces a delivery batch and before processing any event
in it.

## One envelope on every transport

Every carrier presents the same immutable object:

```json
{
  "format": "leaf-delivery-v1",
  "id": "…",
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

Some hosts deliver it inline; others deliver a pointer that `leaf delivery read <id>`
resolves to the same object. Your host contract names which. These differ only in
transport. Process every batch and every event.

Each event retains its stored identity and order, then adds four delivery
readings:

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
  `as_of_seq` is evidence age and `response` is an addressed operation: `reply`
  names an event or conversation, `version` names a conversation, and `receipt`
  names a request. Re-read current state before writing because later evidence
  may already have settled the requirement. A reply response carries both `to`, the
  conversation address to write under, and `for`, the exact event whose obligation the
  write must still satisfy.

The batch-level `conversations` carry each needed anchor, closure state, earlier
messages, and standing gestures on sent widgets. A long conversation includes
its opening and most recent messages, with `elided` counting omitted records.
Use `leaf conversation read <page> <conversation-id>` for an exact, bounded
current reading and paginate with `--after`; use `leaf events <page>
--conversation <conversation-id>` only for raw-log diagnostics. `leaf transcript
<page>` is the human-facing Markdown export.

`handling` carries the vendored layer's instruction for every event kind present.
A missing or invalid registry leaves it empty rather than substituting another
layer's rules. A reaction carries its token, plus `means` when its package defines
one.

Long-thread context may include `summary_hint`; a pointer-only host can surface the
same suggestion as XML. It names a contiguous message range to consider summarizing.
Treat it as navigation maintenance alongside the reader's request, not a request to
resolve the thread. Follow
[conversation threads](conversation-threads.md#summarize-a-long-discussion): read
the covered originals, write the summary, and keep outcomes in the document.

## Delivery and acknowledgement

Run `leaf delivery claim <delivery-id>` before processing the envelope. It marks the
first exact delivered move that remains outstanding as Working and changes nothing for
a settled retry.

Printing is not receipt. The wait owner acknowledges only after the complete
batch reaches its next durable consumer. In the direct loop that consumer is
model context: direct delivery records the included events as opened in this turn.
Start `leaf ack <page> <through_seq>` as the next background task for the page the
batch names, and address every event while ack waits for the next batch. Use
`delivery claim --event ... --detail ...` to move the Working receipt to another
delivered event or make its detail more specific. If wait output is truncated or lost,
acknowledge nothing and rerun with enough output capacity for the whole batch;
a scalar cursor cannot represent a missing event in the middle. Acknowledgement
is monotonic and idempotent; an event posted between wait and ack has a higher
sequence and stays pending. Until ack, wait repeats the batch. `leaf events`
reads the full log without acking it.

Whatever the host, treat a page-and-sequence pair already handled in this task as a
retry, even if a later delivery also includes newer events; your host contract owns
the wait and acknowledgement route.

An embedded MCP App changes where the page is drawn, not this carrier. Its
events enter the same log, and a successful `ui/message` response is not a
delivery receipt.

## After the batch

Acknowledgement is transport receipt, not semantic settlement. Record every
still-current obligation with the Leaf operation its `response` names, then
re-enter the host's wait loop: `waiting` after every obligation has been answered and
the reader owns the next move, `working` while you continue. When the active host binds
a plain reply to its turn, the normal assistant final message is that operation; an
unbound delivery uses the explicit operation. A premature `waiting` declaration cannot
override an opened, unsettled interaction in canonical activity.
`page state` lists every standing reaction under `reactions`; a package-supplied
`means` appears when present. Resolve a page reaction once the live revision has
acted on it.
