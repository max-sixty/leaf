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

Every transport delivers the same immutable object.
`DELIVERY` in the plugin’s `src/leaf/delivery.py` declares every field, with the thread
digests. Some harnesses put it in your context; others give a pointer, which
`leaf delivery read <id>` resolves. A large envelope reads in numbered parts
instead: each reading names its `part` of `parts` and holds a slice of the
envelope's JSON in `text`, which you join in order, and its `next` is the command
that reads the following part, or null on the last. Only the last part carries
`acknowledge`.

An envelope with `correction` retries one answer Leaf refused to post: its
`diagnostic` says why, and its `instruction` asks you to fix that failure and answer
the same input again, keeping the work you already did.

Events keep their stored fields and log order, and add:

- `subject`: the page, thread, or widget the event changes.
- `says`: the words of what the user pressed, such as each picked option, as the
  page they pressed on wrote them. A later rewording does not change them.
- `threads`: every thread the event belongs to. The event appears once in the batch
  however many threads it is in.
- `was`: on the user's rewrite of their own message, the words it replaced.
  `suggestion: true` beside it means the message is a suggestion, so its new `text`
  is the exact replacement it proposes.
- `answer`: the response the event owes. A `kind: "reply"` answer is a thread reply,
  written with `leaf response reply <answer.ref>` ([threads](threads.md)), or by your
  turn's final message where its `writer` is `"turn"`. A `kind: "markup"` answer is the
  page revision its `handling` names, and a reply does not replace it. Until the
  answer is written, `leaf status idle` refuses, and the Stop hook holds the turn
  open unless the turn started the update (`references/conversation-loop.md`,
  "Long-running work"). Events with no `answer` owe nothing: a page action outside
  any obligation, a pick still waiting for the user's Done, or a message followed by a
  newer one in its thread (your reply to the newer one covers both).
- `handling`: ids of clauses in the batch's `handling` object, in reading order. The
  object holds each clause's text once, and the ids mean nothing outside the batch.
  Follow every clause the event names.

The batch's `threads` give each thread's title (null until named), anchor, whether
it is resolved, earlier messages, and the gestures in force on widgets sent in it. A
thread's history leaves out messages that are events in the batch, and a long thread
shows only its opening and latest messages, with `elided` counting the rest; read
the whole thread with `leaf page state <page> <thread-id>`, paginated with
`--after`. A long
thread may also carry `summary_hint`
([threads, "Summarize a long discussion"](threads.md#summarize-a-long-discussion)).

## Delivery and acknowledgement

Confirm a delivery only once every part is in context, by following its
`acknowledge` instruction, which a pointer shows on its last part. Reading it again
does not confirm it. Input your harness already confirmed arrives with
`acknowledge: null`.

Confirming marks the user's updates **Delivered**; it does not answer them.

`leaf wait` waits only on pages this session holds; to take over a page, run
`leaf page claim <page>` first. A wait exits 0 with input, or 2 with a diagnostic
to follow.

## After the batch

Write every answer still owed, then return to your harness's wait loop. Run
`leaf status … waiting` once everything is answered and the next step is the
user's; while you keep working, leave the update or to-do started instead.
