# Delivered event batches

## Handle the input

Process every event in every batch. Before working, read a delivery pointer with
`leaf delivery read <id>`, following each `next` command until you have every part,
and confirm it as "Delivery and acknowledgement" says. Read each event's named
`handling` clauses from the batch's `handling` object, in their listed order. These
clauses name the response the event needs; an event without an `answer` owes none of
its own.

Before work, follow [conversation loop, "When to write"](conversation-loop.md#when-to-write).
Read [threads](threads.md) for messages and replies, or
[authoring revisions](authoring-revisions.md) for an answer recorded in markup.
Reread current state when later input could change the work. Treat already handled
input as a retry: do not repeat repository edits or external actions. The selected
harness contract owns waiting and receipt.

## One envelope on every transport

Every transport into your context presents an immutable object of the same shape:

```json
{
  "format": "leaf-delivery/<protocol>",
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

Some harnesses deliver it inline; others deliver a pointer that `leaf delivery read
<id>` resolves, naming the envelope by its `id`. A large envelope reads in numbered
parts: their `text` values together contain the complete envelope, and `next` names
the next read. Your harness contract names the transport.

Each event keeps its stored fields and order, less the browser's retry key
`attempt`, and adds these:

- `subject` is the stable page, thread, or widget the event changes.
- `says`, when present, maps each element a widget gesture names (the ids in its
  `meaning.depends`) to that element's authored words in the document the user
  pressed on: the revision the event names, or the frozen message that sent the
  widget. A later version that rewords the element does not change them. They are
  authored text, so they leave out what an earlier gesture changed and what a
  widget's module draws beyond it. An element the user wrote, such as an added
  option, has no authored words; `says` gives it the words recorded by the action
  that created it. An element that only
  encloses another named one is left out, so a pick gives its options' words and a
  gesture naming only its widget gives the whole widget's. An undo carries the words
  of the gesture it takes back.
- `threads` lists every thread the event belongs to, for context. The event
  appears once in the batch however many threads it belongs to.
- `answer`, when present, is what the event owes. A `kind: "reply"` answer is
  written with `leaf response reply <answer.ref>` ([threads](threads.md)); it
  carries `to`, the thread, and `for`, the input it answers. A `kind: "markup"`
  answer is the page revision its `handling` names, and no conversation reply
  replaces it. Until the answer is written, `leaf status idle` refuses, and the Stop
  hook holds the turn open unless that turn started the update
  (`references/conversation-loop.md`, "Long-running work"). An event without an
  answer owes nothing of its own: a page action that answers no ask, a pick before
  the Done its ask waits for, or a message a newer one in its thread answers through.
- `handling`, when present, lists clause ids in the batch's `handling` object,
  in the order to read them. That object gives each distinct instruction's text
  once; ids belong only to that batch. Follow every named clause for this event:
  together they cover this event's case and the answer it owes.

The batch-level `threads` carry each thread's title (null until named),
anchor, closure state, earlier messages, and gestures in force on sent widgets.
A newly opened thread still carries its metadata; messages already in the
batch are omitted from its history. A long thread includes
its opening and most recent messages, with `elided` counting omitted records.
Use `leaf page state <page> <thread-id>` for an exact, bounded
current reading and paginate with `--after`; `leaf page state <page>` lists the
reactions in force under `reactions`. Use `leaf page events <page>` only for raw-log
diagnostics. `leaf page transcript <page>` is the human-facing Markdown export.

Long-thread context may include `summary_hint`, naming a contiguous message range to
review, and new input in that thread carries a `handling` clause pointing to
[threads, "Summarize a long discussion"](threads.md#summarize-a-long-discussion)
for when and how to summarize. The hint adds no response obligation and does not
resolve the thread.

## Delivery and acknowledgement

Confirm a delivery only after every part is in context, following its
`acknowledge` instruction. A pointer reading shows that instruction on its last part,
and rereading never acknowledges it. Inline hook input and App Server turns arrive
with `acknowledge: null`, since your harness has already confirmed receipt. Commands
state the next step and any recovery needed.

Receipt records **Picked up** in the current turn; it does not answer the update.
A progress message in its thread or `leaf task start <page> <event-id>` records
**Working** while it remains outstanding ([conversation loop](conversation-loop.md#when-to-write)).

`leaf wait` observes ownership already held. Use `leaf page claim <page>` for an
intentional handoff, then wait according to the selected harness contract. A wait
returns input with exit 0, or ends with exit 2 and a diagnostic; follow that
diagnostic. Receipt commands refuse input that no longer belongs to their receiver.

## After the batch

Write every still-current `answer` with the operation its kind names, starting each
update whose work you take on as its `handling` clauses say
(`references/conversation-loop.md`, "When to write"), then re-enter the harness's
wait loop: `leaf status … waiting` once every obligation is answered and the next
step is the user's, or a started item while you continue.
