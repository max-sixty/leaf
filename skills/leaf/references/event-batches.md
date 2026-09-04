# Delivered event batches

Read this after a direct wait or Codex delivery produces a batch and before
processing any event in it.

- [Delivery and acknowledgement](#delivery-and-acknowledgement)
- [Process every event](#process-every-event)
- [Reactions](#reactions)

## Delivery and acknowledgement

Wait prints one page's unacknowledged events as JSON lines. The first line names
the page and carries `threads`: for each conversation the batch lands in, its
anchor, who closed it if anyone has, what was said in it before this batch, and
the reader's standing gestures on any widget sent in it. A reply event names
only the message it answers, and an action only the widget it was made on; the
exchange behind them is here. A long conversation arrives as its opening message
and its most recent, with `elided` counting what was dropped between. When the
missing records matter, use the thread id from `leaf page state <page>` with
`leaf events <page> --thread <thread-id>` to print its exact JSONL records.
`leaf transcript <page>` is the human-facing Markdown export of the exchange.

Printing is not receipt. The wait owner acknowledges only after the complete
batch reaches its next durable consumer.

In the direct loop, the durable consumer is model context. The Codex adapter
instead owns its wait and acknowledgement. It acknowledges the wake's first
snapshot after Codex's queue accepts it; the queued turn reads its named delivery
payload and does not wait or acknowledge. One accepted wake suppresses later queue
messages until that turn opens. The events accumulated behind it stay
unacknowledged; the prompt hook carries their delivery pointers into the same turn
before the model starts and takes receipt at Stop. Events arriving during the work
take the same route through one Stop continuation. If a queue command has an
uncertain outcome, the adapter retries the same pointer with the same Leaf delivery
id. This is at-least-once delivery and may create a retry turn; the task applies the
page-and-sequence retry rule below.

An embedded MCP App changes where the page is drawn, not this carrier. Its events
enter the same append-only log; the detached Codex adapter still owns wait,
durable queue acceptance, and acknowledgement. A successful `ui/message` response
is not a delivery receipt.

If direct wait output is truncated, acknowledge nothing and rerun with enough
output capacity for the whole batch. After the complete batch reaches model
context, run `leaf ack <page> <highest-seq>` for the page the batch's first line
names. If output is lost, follow the same rule. A scalar cursor cannot represent
a missing event in the middle. Acknowledgement is monotonic and idempotent; an
event posted between wait and ack has a higher sequence and stays pending. Ack
then waits in the same process. Until ack, wait repeats the batch. `leaf events`
reads the full log without acking it.

Treat a page-and-sequence pair already handled in this task as a retry, even if a
later delivery also includes newer events.

For a Codex delivery, collect every payload already attached to the turn before
choosing an implementation direction. Then refresh each page immediately before
acting, using the greatest `through` value among its payloads:

```sh
leaf events <page> --after <through>
```

This returns immediately and does not acknowledge anything. Add any newer reader
events, reports, or page errors it prints to the work you are about to do. Ignore
transport records such as `pickup`. The Stop hook will deliver those events again
for receipt, so apply the page-and-sequence retry rule rather than doing the work
twice. This refresh introduces no batching delay; an event that arrives after it
remains the Stop hook's responsibility.

## Process every event

Start `leaf ack` for a direct batch, set the page `working`, and address every
event the wait printed while ack waits for the next batch. In a Codex delivery,
whether its pointer came from the visible wake or the hidden Stop continuation,
the detached adapter and hook own ack; set the page `working` and process every
persisted batch directly.

- **Comment:** a comment with `"response": {"kind": "version", "verb": "…"}` takes no reply: incorporate
  it in the next version, then resolve it. If the revision depends on the reader,
  open a separate exact-section thread on the same Decision with
  `leaf comment --section <decision-id>`. Reply to other comments in-thread and revise
  the page when warranted; follow the closure rule in `conversation-threads.md`.
  A comment with `"suggestion": true` proposes exact replacement text; take it
  verbatim or reply with the reason for declining it.
- **Layer comment:** an event with `"about": "layer"` changes the relevant Leaf
  layer, followed by re-vendoring, a valid source activation, and an in-thread reply.
- **Page action:** the reader already sees the action applied. Carry its standing
  state into `index.html`. For an `lf-options` `choose` action with `additions`,
  insert each id key and its text value as an ordinary `lf-option`, then carry the
  standing `options` as `chosen`. Start a separate option-anchored thread only if
  clarification is needed. Continue the work the page says the action selects or
  unblocks. If you deliberately replace standing state, use `restated` and explain
  why when stamping the resulting checkpoint.
- **Reaction:** a `comment` or `reply` carrying `token` in place of `text`, with
  the token's meaning printed beside it as `means`. It is a mark, not a
  question: act on it — revise the passage a `cut` or `lost` stands on, expand
  where `more` stands, take an `ok` as the reader's "seen, go on" — and, once
  the live revision answers it, `leaf resolve` it so its paint clears. Reply on
  the reaction itself only where it puzzles you ("which part?"); that reply
  turns the mark into an ordinary thread. A reaction never gates activation or
  stamping, and an acknowledged one nobody replied to holds no turn.
- **Undo:** read the named event and the undo as one act. Do not answer or record
  the withdrawn gesture. An undone answering action reopens its thread; an
  undone reaction is a mark the reader took back.
- **Page error:** fix the page or widget and save the correction. The event is
  diagnostics, so do not reply unless the reader asked about it.
- **Worker report:** carry the report into markup, or mark its element
  `overruled` and state why. A page must not end with unresolved report debt.
- **Host request:** treat the request id as the host executor's idempotency and
  recovery key. Inspect the host before acting after an interruption, perform the
  package-declared operation at most once, and append exactly one terminal result
  with `leaf receipt <page> <request-id> succeeded|failed --text "…"`. A receipt
  records the external outcome; it does not rewrite the authored page. Refresh
  any bound external data, save the source revision that reflects the result, and
  stamp a checkpoint when it is worth naming.
- **Thread-widget action:** reply in that same thread. A plain options pick
  answers immediately; a `multiple` group answers only when its `answer` action
  arrives, though every toggle is delivered.
- **Done:** treat it as approval of declared sign-off, not closure of the page.

## Reactions

The reader's cheapest answer is a token: `ok` `no` `lost` `cut` `more` `this`
as the default package ships them, on a passage, an element, the page whole, or
one of your replies. `page state` lists every standing one under `reactions`,
each with its `means`, and the tokens themselves are the page's vendored
`$reactions` entry in `registry.json`, so a project's own tokens read the same
way. An `ok` on your latest reply request takes the thread out of "waiting on
you"; no reply is owed for it. Resolve a page reaction once the live revision
has acted on it.
