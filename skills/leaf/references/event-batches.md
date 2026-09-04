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
instead owns its wait and acknowledgement. The first batch after a turn ends is
acknowledged after Codex accepts its queued pointer. While a turn is active, the
delivery machinery acknowledges after atomically adding the batch to that turn's
durable epoch. Prompt and Stop hooks put the pointer in model context. Stop repeats
input that was not covered by an accepted queue snapshot or acknowledged Stop
offer; this includes a prompt-hook pointer, because that hook has no delivery
receipt. The task reads every entry in `batches`, each containing `page`, `url`,
`threads`, and `events`; it does not wait or acknowledge. If a queue command has an
uncertain outcome, the adapter retries the same pointer with the same Leaf delivery
id. This is at-least-once delivery and may create a retry turn; the task applies
the page-and-sequence retry rule below. If an active turn produces no later hook
for fifteen minutes, the adapter queues the same epoch pointer so its stored input
cannot remain hidden. A long-running turn can therefore produce a duplicate wake.

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

## Process every event

Start `leaf ack` for a direct batch, set the page `working`, and address every
event the wait printed while ack waits for the next batch. In a Codex delivery,
the detached adapter owns ack; set each page `working` and process every batch in
the persisted epoch directly.

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
