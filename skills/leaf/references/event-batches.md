# Delivered event batches

## Handle the input

Process every event in every batch. If you got a pointer, read it with
`leaf delivery read <id>`, following each `next` command until you have every part,
then confirm it ("Delivery and acknowledgement"). For each event, follow the
`handling` clauses it names, in order; they say what response it needs.

Before working, post your progress line
([conversation loop, "When to write"](conversation-loop.md#when-to-write)). Read
[threads](threads.md) for messages and replies, or
[authoring revisions](authoring-revisions.md) for an answer recorded in markup.
Reread current state when later input could change the work. Input you already
handled is a retry: do not repeat its repository edits or external actions.

## One envelope on every transport

Every transport delivers the same immutable object:

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

Some harnesses put it in your context; others give a pointer, which
`leaf delivery read <id>` resolves. A large envelope reads in numbered parts whose
`text` values together make the envelope.

Events keep their stored fields and log order, without the browser's retry key
`attempt`, and add:

- `subject`: the page, thread, or widget the event changes.
- `says`: the words of what the user pressed, such as each picked option, as the
  page they pressed on wrote them. A later rewording does not change them.
- `threads`: every thread the event belongs to. The event appears once in the batch
  however many threads it is in.
- `answer`: the response the event owes. A `kind: "reply"` answer is a thread reply,
  written with `leaf response reply <answer.ref>` ([threads](threads.md)); `to`
  names the thread and `for` the input it answers. A `kind: "markup"` answer is the
  page revision its `handling` names, and a reply does not replace it. Until the
  answer is written, `leaf status idle` refuses, and the Stop hook holds the turn
  open unless the turn started the update (`references/conversation-loop.md`,
  "Long-running work"). Events with no `answer` owe nothing: a page action outside
  any ask, a pick still waiting for the user's Done, or a message followed by a
  newer one in its thread (your reply to the newer one covers both).
- `handling`: ids of clauses in the batch's `handling` object, in reading order. The
  object holds each clause's text once, and the ids mean nothing outside the batch.
  Follow every clause the event names.

The batch's `threads` give each thread's title (null until named), anchor, whether
it is resolved, earlier messages, and the gestures in force on widgets sent in it. A
thread's history leaves out messages that are events in the batch, and a long thread
shows only its opening and latest messages, with `elided` counting the rest; read
the whole thread with `leaf page state <page> <thread-id>`, paginated with
`--after`. `leaf page events <page>` prints the raw log, for diagnostics only. A long
thread may also carry `summary_hint`
([threads, "Summarize a long discussion"](threads.md#summarize-a-long-discussion)).

## Delivery and acknowledgement

Confirm a delivery only once every part is in context, by following its
`acknowledge` instruction, which a pointer shows on its last part. Reading it again
does not confirm it. Inline hook input and App Server turns arrive with
`acknowledge: null` because your harness has already confirmed them.

Confirming marks the user's updates **Picked up**; it does not answer them.

`leaf wait` waits only on pages this session holds; to take over a page, run
`leaf page claim <page>` first. A wait exits 0 with input, or 2 with a diagnostic
to follow. Receipt commands refuse input that no longer belongs to this session.

## After the batch

Write every answer still owed, then return to your harness's wait loop. Run
`leaf status … waiting` once everything is answered and the next step is the
user's; while you keep working, leave an item started instead.
