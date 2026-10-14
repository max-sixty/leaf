# Delivered event batches

## Handle the input

Process every event in every batch. Before working, read a delivery pointer with
`leaf delivery read <id>`, following each `next` command until you have every part,
then confirm it as "Delivery and acknowledgement" says. For each event, read the
`handling` clauses it names, in order, from the batch's `handling` object. They say
what response the event needs.

Before work, follow [conversation loop, "When to write"](conversation-loop.md#when-to-write).
Read [threads](threads.md) for messages and replies, or
[authoring revisions](authoring-revisions.md) for an answer recorded in markup.
Reread current state when later input could change the work. Input you already
handled is a retry: do not repeat its repository edits or external actions. Your
harness contract says how to wait and how receipt is confirmed.

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

Events keep their stored fields and log order, except the browser's retry key
`attempt`, and add these:

- `subject` is the stable page, thread, or widget the event changes.
- `says`, when present, gives the words of the elements a widget gesture names.
  For a pick, it maps each picked option's id to that option's words. The ids are
  those in the event's `meaning.depends`. The words come from the markup of the
  document the user pressed on: the revision the event names, or the thread
  message that carried the widget. Rewording the element in a later version does
  not change them. Because they come from markup, they leave out changes an
  earlier gesture made and anything the widget's module draws. An option the user
  added has no markup, so its words come from the action that added it. An element
  that only contains other named elements is left out, so a pick lists its options
  and not the whole list. An undo carries the words of the gesture it undoes.
- `threads` lists every thread the event belongs to, for context. The event
  appears once in the batch however many threads it belongs to.
- `answer`, when present, is the response the event owes. A `kind: "reply"`
  answer is a thread reply, written with `leaf response reply <answer.ref>`
  ([threads](threads.md)); its `to` names the thread and `for` the input it
  answers. A `kind: "markup"` answer is the page revision its `handling` names, and
  a thread reply does not replace it. Until the answer is written,
  `leaf status idle` refuses. The Stop hook also holds the turn open, unless that
  turn started the update (`references/conversation-loop.md`, "Long-running
  work"). An event with no `answer` owes nothing itself. Examples are a page action outside any ask,
  a pick whose ask still waits for the user's Done, and a message with a newer one
  after it in the same thread, since your reply to the newer one answers both.
- `handling`, when present, lists clause ids in reading order. The batch's
  `handling` object holds each clause's text once, and the ids mean nothing outside
  that batch. Follow every clause the event names.

The batch-level `threads` carry each thread's title (null until named), anchor,
whether it is resolved, earlier messages, and the gestures in force on widgets sent
in it. A thread's history leaves out messages that are events in the same batch. A
long thread includes its opening and most recent messages, with `elided` counting
the ones left out.
Use `leaf page state <page> <thread-id>` for an exact, bounded
current reading and paginate with `--after`; `leaf page state <page>` lists the
reactions in force under `reactions`. Use `leaf page events <page>` only for raw-log
diagnostics. `leaf page transcript <page>` is the human-facing Markdown export.

A long thread may carry `summary_hint`, a range of messages worth summarizing. New
input in that thread then carries a `handling` clause pointing to
[threads, "Summarize a long discussion"](threads.md#summarize-a-long-discussion).
The hint owes no response of its own.

## Delivery and acknowledgement

Confirm a delivery only after every part is in context, by following its
`acknowledge` instruction. A pointer reading shows that instruction on its last
part; reading again does not confirm it. Inline hook input and App Server turns
arrive with `acknowledge: null`, since your harness has already confirmed receipt.

Confirming receipt marks the user's updates **Picked up**; it does not answer them.
A progress message in the update's thread, or `leaf task start <page> <event-id>`,
marks it **Working** until you answer it
([conversation loop](conversation-loop.md#when-to-write)).

`leaf wait` waits only on pages this session already holds. To take over a page,
run `leaf page claim <page>`, then wait as the selected harness contract says. A
wait returns input with exit 0, or exits 2 with a diagnostic to follow. Receipt
commands refuse input that no longer belongs to this session.

## After the batch

Write every answer still owed, with the operation its `kind` names, and start each
update whose work you take on, as its `handling` clauses say
(`references/conversation-loop.md`, "When to write"). Then return to the harness's
wait loop. Run `leaf status … waiting` once every answer is written and the next
step is the user's; while you keep working, leave an item started instead.
