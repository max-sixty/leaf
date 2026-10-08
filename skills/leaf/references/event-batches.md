# Delivered event batches

## Handle the input

Process every event in every batch. Read a delivery pointer with
`leaf delivery read <id>` before working, so the complete envelope is in context.
Follow its `acknowledge` instruction, then read each event's named `handling`
clauses from the batch's `handling` object, in their listed order. These clauses
name the response the event needs; an event without an `answer` owes none of its own.

Before work, follow [conversation handoff, "When to write"](conversation-loop.md#when-to-write).
Read [threads](threads.md) for messages and replies, or
[authoring revisions](authoring-revisions.md) for an answer recorded in markup.
Re-read current page state before answering, since later input may already have
settled the obligation. Treat a page-and-sequence pair already handled in this
task as a retry. The selected harness contract owns waiting and receipt.

## One envelope on every transport

Every transport into your context presents an immutable object of the same shape:

```json
{
  "format": "leaf-delivery-v5",
  "id": "a1b2c3d4",
  "created_at": 0,
  "acknowledge": "Whoever ran the `leaf wait` that printed this delivery acknowledges it; …",
  "batches": [
    {
      "page": "/absolute/page",
      "claim": "page-session",
      "through_seq": 12,
      "threads": [],
      "handling": {},
      "events": []
    }
  ]
}
```

The id is eight lowercase hexadecimal characters and addresses this envelope in the
machine's immutable delivery store.

Some harnesses deliver it inline; others deliver a pointer that `leaf delivery read <id>`
resolves to the same object. Your harness contract names which. The envelope states
once how to confirm receipt and how to answer:

- `acknowledge` says how to confirm receipt after the complete envelope is in
  context. Follow that instruction. When it is `null`, your harness confirms
  receipt; run no separate acknowledgement command. Your harness contract explains
  its mechanism.
- Each `answer` has a complete immutable `ref`. For `kind: "reply"`,
  `leaf response reply <answer.ref>` authors it. Its `writer` records custody at
  capture, with the `agent` command or provider `turn`; the selected harness
  contract describes that turn's opening and completion.

Each event retains its stored identity, fields and order, less the browser's
retry key `attempt`, then adds these delivery readings:

- `subject` is the stable page, thread, or widget the event changes.
- `says`, when present, maps each element a widget gesture names to its words: the
  ids in an action's or report's `meaning.depends`. The words are the authored ones
  in the document the user pressed on, which is the revision the event names or the
  frozen message that sent the widget, so a later version that rewords an element does not change them. They are that
  document's words and not a reading of the rendered page: what an earlier gesture
  changed, and what a widget's module draws beyond its authored text, are not in
  them. An element a user wrote, such as an added option, is in no document: the
  event's own `detail` carries the words the user gave it. An element that only
  encloses another named one is left out, so a pick says its options and a gesture
  naming only its widget says the whole widget. An undo carries the words of the
  gesture it takes back.
- `threads` lists every thread the event belongs to. Membership is
  many-to-many: it provides context and never partitions or duplicates the event.
- `answer`, when present, freezes the answer the event owed at capture: its
  `kind` (`reply` or `markup`) with its immutable response reference.
  `leaf page state` lists the current move's obligation; the delivered reference
  retains the exact captured page and input. The
  event's `handling` clauses say how to write it. Until the answer is written,
  `leaf status idle` refuses, and the Stop hook holds the turn open unless that turn
  started the move (`references/conversation-loop.md`, "Long-running work").
  Re-read current state before writing because later evidence may already have
  settled the requirement. A `reply` carries `to`, the captured thread address,
  and `for`, the exact input; its `writer` records custody at capture.
  [Threads](threads.md) owns rich authoring on the reference, including preparation
  for a provider's final. A `markup` answer names the page revision operation its
  `handling` requires; a conversation reply cannot replace that operation.
  An event without an answer owes nothing of its own:
  a page action that answers no Ask, a pick before the Done its Ask waits for, or a
  message a newer one in its thread answers through.
- `handling`, when present, lists clause ids in the batch's `handling` object,
  in the order to read them. That object gives each distinct instruction's text
  once; ids belong only to that batch. Follow every named clause for this event:
  together they cover this event's case and the answer it owes.

The batch-level `threads` carry each thread's title (null until named),
anchor, closure state, earlier messages, and standing gestures on sent widgets.
A newly opened thread still carries its metadata; messages already in the
batch are omitted from its history. A long thread includes
its opening and most recent messages, with `elided` counting omitted records.
Use `leaf page state <page> <thread-id>` for an exact, bounded
current reading and paginate with `--after`; use `leaf page events <page>`
only for raw-log diagnostics. `leaf page transcript
<page>` is the human-facing Markdown export.

Long-thread context may include `summary_hint`, naming a contiguous message range to
review, and new input in that thread carries a `handling` clause pointing to
[threads, "Summarize a long discussion"](threads.md#summarize-a-long-discussion)
for when and how to summarize. The hint adds no response obligation and does not
resolve the thread.

## Delivery and acknowledgement

Printing is not receipt. Once every batch of a printed delivery is in context,
follow the envelope's `acknowledge` instruction, which names the harness's next
wait:

```bash
leaf wait --ack <delivery-id>
```

This acknowledges every batch in that delivery and waits for the next envelope.
Process the received events while it waits. If output is truncated or lost,
acknowledge nothing and rerun with enough output capacity for the whole envelope;
a scalar cursor cannot represent a missing event in the middle. Acknowledgement
is monotonic and idempotent; an event posted after capture has a higher sequence
and stays pending. Until a delivery is confirmed, a wait that prints it repeats
the events. `leaf page events` reads the
full log without acking it.

Receipt and work have separate evidence. Confirming a direct delivery records its
moves as **Picked up** in the current turn. **Picked up** means the delivery is in
your context, whether or not you have read it yet. Other harnesses record that
opening when the delivery enters the turn's context: as a hook hands it over, as the agent
reads a pointer with `leaf delivery read`, or as a turn Leaf started begins. Leaf
derives overall page activity from that evidence. Taking the move in hand, with a
progress update in its thread or `leaf task start <page> <event-id>`
([conversation handoff](conversation-loop.md#when-to-write)), strengthens its
receipt to **Working** while it remains outstanding. That neither acknowledges the
delivery nor answers the move.

Whatever the harness, treat a page-and-sequence pair already handled in this task as a
retry, even if a later delivery also includes newer events; your harness contract owns
how you wait and acknowledge.

`leaf wait` ends one of two ways: exit 0 with the next input, or exit 2 with the
ending named on stderr. The input is one JSON envelope, or, where the harness's hook
carries input, one line naming the page with new input. Exit 1 from `leaf wait
--ack` means the acknowledgement was refused. A wait that restarted a dead server
says so on stderr. The exit 2 endings:

- `the leaf ended` or `the leaves ended`: every page left in the watch is idle.
  `nothing to watch`: the session holds none. End the loop.
- `server is not running`: the page was never served, or its server died and
  the wait's one restart did not bring it back. The line gives the recovery
  command. After recovery, resume with an unnamed `leaf wait`, which cannot
  reclaim a page transferred meanwhile. A server stopped with `leaf server stop`,
  or held down while `leaf page init` re-vendors the page, is not this ending: the
  wait goes on watching it.
- `this session no longer owns`: a successor has the page. Do not name or reclaim
  it. A rearm keeps watching any other live page, and exits with this line once the
  transfers empty that set.
- another `leaf wait` is already active: that process holds the session's lease.
  Leave it running rather than starting another.

Empty stdout alone is not evidence that the harness stopped the process, and no reason
to run a named wait again. Resume with an unnamed wait only when the harness itself
reports that it canceled or killed the command, or on a signal your harness contract
names.

## After the batch

Acknowledgement is transport receipt, not semantic settlement. Write every
still-current `answer` with the operation its kind names, starting each move whose
work you take on as its `handling` clauses say (`references/conversation-loop.md`,
"When to write"), then re-enter the harness's wait loop: `leaf status … waiting` after
every obligation has been answered and the user owns the next move, and a started
item while you continue.
`page state` lists every standing reaction under `reactions`.
