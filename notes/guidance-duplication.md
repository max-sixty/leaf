# Guidance duplication audit (2026-09-23)

Rules the agent-facing guidance states in more than one place: `SKILL.md`,
`references/`, package guidance and registry text, `$events` clauses, agent-facing
Python strings, protocol sidecars, and hand-copied `docs/` text. Each entry gives the
proposed single home; the other sites become pointers or are removed.

When copies disagreed, it was almost always because a short copy, such as a CLI
help string, a delivered clause or a docs paragraph, left out a case that the full
reference stated. A rule about handling one kind of event belongs in that event's
`$events` clause, which reaches the agent with the event even after the references
have left its context.

The authoring rules each have one home now; other sites point at it. Some overlaps
stay because each copy reaches someone the home does not: `--help` text for its own
command (`leaf reply`, `leaf conversation summarize`), the `events.md` protocol spec,
the forwarded-batch prompt in `codex-watcher.md`, a one-line "handle every event" at
the point of use, and the command-hub worker guide, the only file a worker reads.
What remains is the delivery loop below, and one rule that has no home yet: command-hub and
monitoring both say not to acknowledge a request's batch until the request reaches
the durable executor. It is a rule about every request, so it belongs in the
`$events` request handling clause, once the acknowledgement order below settles.

## Delivery loop

These rules came from the first pass, which looked only at the delivery loop. The
order's copies in `answering.reply` and `ACK_BATCH_INSTRUCTION` are on the
unmerged `message-flow` branch, which adds the order to them:
- **The acknowledge, reply, then work order.** It appears in `SKILL.md`,
  `conversation-loop.md`, `host-claude-code.md`, `ACK_BATCH_INSTRUCTION` and
  `answering.reply`. Home: the "When to write" section of `conversation-loop.md`.
- **"A host that sends your final message as the reply".** It appears in
  `ANSWER_ASK_INSTRUCTION`, `answering.reply`, `event-batches.md`,
  `conversation-loop.md` and `host-codex.md`. Home: `host-codex.md`.
- **Truncated output.** It appears in `ACK_BATCH_INSTRUCTION`, `event-batches.md`
  and `codex-watcher.md`. Home: `event-batches.md`.
- **What Picked up and Working mean.** They appear in `conversation-loop.md`,
  `event-batches.md` and `host-claude-code.md`. Home: `event-batches.md`.
- **The delivery sample in `docs/how-it-works.html`** is copied by hand. Generate it
  from a real delivery instead.
