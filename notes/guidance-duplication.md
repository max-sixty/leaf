# Guidance duplication audit (2026-09-23)

Rules the agent-facing guidance states in more than one place: `SKILL.md`,
`references/`, package guidance and registry text, `$events` clauses, agent-facing
Python strings, protocol sidecars, and hand-copied `docs/` text. Each entry gives the
proposed single home; the other sites become pointers or are removed.

When copies disagree, it is almost always because a short copy, such as a CLI help
string, a delivered clause or a docs paragraph, leaves out a case that the full
reference states. Replacing short copies with pointers removes most of the drift.

## Copies that already disagree

- **What a worker's report is owed.** The report handling clause
  (`assets/registry.json`, `$events.handling.report`) says to write the report into
  the next stamped version or mark it `overruled`. `authoring-revisions.md` says "An
  unrelated revision may leave the report standing." It is also restated in
  `$report`, `command-hub/registry.json` (`lf-agent`, `lf-task`) and
  `command-hub/guidance/coordinator.md`. Home: `$report`, because `version check`
  enforces it there.
- **When a version thread may be resolved.** `answering.version` and
  `leaf resolve --help` leave out the "or changes its declared answer where the Ask
  was already answered" case. That case appears in `conversation-threads.md`,
  `events.md`, `x-awaits` and `x-conversation`. Home: `conversation-threads.md`.
- **When the agent resolves a thread.** `leaf resolve --help` leaves out the case
  where an event rule requires resolution, which contradicts the reaction clause in
  `$events.handling.comment`. `leaf comment --help` says the user resolves.
  `events.md` also restates the rule. Home: `conversation-threads.md`.
- **Escaping a `<pre>` data body.** `x-content` says "< > escaped" and leaves out
  `&amp;`. `page-authoring.md`, `lf-tree`, `lf-code`, `lf-chart`, `lf-draft`,
  `diagram` and `diff` include it. Home: `$keys.x-content`.
- **What holds a live update.** `page-authoring.md` lists "composing, dragging, or
  has an unresolved delivery", while `docs/how-it-works.html` lists only composing
  and dragging. Home: `page-authoring.md`.
- **When sign-off is offered.** `SKILL.md` says a stamped version, and
  `authoring-asks.md` says after every Ask is answered. `docs/how-it-works.html`
  says the meta tag alone enables it, and `events.md` also restates it. Home:
  `authoring-asks.md`.
- **What an acknowledged move is owed.** `page-checkpoints.md` lists three answers
  and leaves out markup. `event-batches.md`, `session-lifetime.md`, `$events` and
  `schema.ANSWER_KINDS` list four. Home: the obligation section of
  `event-batches.md`.

## Consistent now, by number of copies

- **`restated` retracts a reader decision, with the reason in the version note**
  (14 copies). They are in `authoring-revisions.md`, `$restated` and several
  `assets`, `default` and `swipe` registry entries, swipe's author guidance,
  `docs/how-it-works.html` and `AGENTS.md`. Home: `$restated`.
- **An Ask is `lf-ask` with one leading heading holding the question** (11 copies).
  They are in `authoring-asks.md`, `default`, `x-awaits`, and the guidance and
  registries of swipe, targeting, playground and command-hub. Home:
  `lf-ask.description`.
- **Run a request at most once, keyed by the page and request id, with exactly one
  receipt** (9 copies). They are in `packages.md`, `$events` request and receipt
  clauses, `x-request`, command-hub, monitoring, `events.md` and `AGENTS.md`. Home:
  the request handling and receipt answering clauses.
- **A `multiple` Ask stays open until Done, and earlier picks owe nothing**
  (7 copies). They are in `authoring-asks.md`, `default`, `$awaits.until`, the
  action clause, `event-batches.md`, `events.md` and `session-lifetime.md`. Home:
  `$awaits.until`.
- **Images go through `leaf page media` and are never inlined** (6 copies). They
  are in `authoring-evidence.md`, `conversation-threads.md`, `lf-shot`, and the
  playground and visual-review guidance and registries. Home:
  `authoring-evidence.md`.
- **Name an untitled conversation and keep the title stable** (5 copies). They are
  in `conversation-threads.md`, two identical `$events` clauses,
  `leaf conversation title --help` and `events.md`. Home: `conversation-threads.md`;
  the clause keeps only its null-title trigger.
- **Handle every event in the batch** (5 copies). They are in `SKILL.md`,
  `event-batches.md`, `page-checkpoints.md`, `hooks.py` and `codex-watcher.md`.
  Home: `event-batches.md`.
- **Workers never wait, set status or stamp** (5 copies). They are in
  `conversation-loop.md`, command-hub coordinator and worker guidance,
  `codex-watcher.md` and `host-claude-code.md`. Home: the "Long-running work"
  section of `conversation-loop.md`.
- **The working claim's quarter-hour grace** (5 copies). They are in
  `conversation-loop.md`, `session-lifetime.md`, command-hub worker guidance and
  registry, and `leaf status --help`. Home: `session-lifetime.md`.
- **Reused behavior goes in a package, one-page behavior in `page/`** (5 copies).
  They are in `page-authoring.md`, `packages.md`, playground guidance and
  `docs/how-it-works.html`. Home: `packages.md`.
- **Page tabs are last in `main`, with the primary view first** (4 copies). They are
  in `page-authoring.md`, `authoring-revisions.md`, `lf-tabs` and `x-tab`. Home:
  `page-authoring.md`.
- **Reply mechanics: `--awaits`, moving or detaching a thread, and publishing a
  changed source** (4 copies). They are in `conversation-threads.md`,
  `answering.reply`, `leaf reply --help` and `events.md`. Home:
  `conversation-threads.md`.
- **An overlapping summary replaces the earlier one, and a summary answers
  nothing** (4 copies). They are in `conversation-threads.md`, `event-batches.md`,
  `leaf conversation summarize --help` and `events.md`. Home:
  `conversation-threads.md`.
- **`lf-num` takes `at` from the `updated` time `data set` prints** (4 copies). They
  are in `authoring-evidence.md`, two `default` entries and `x-data`. Home:
  `authoring-evidence.md`.

Rules with three copies:
- Messages render as Markdown.
- The "Another option" cell.
- The recommended chip.
- A section's id goes on its `<section>`, a rule `developing-leaf` shares with the
  shipped guidance.
- The audiences of `leaf page guidance`.
- In the playground's A/B comparison, one shared state drives both candidates.

Pairs:
- `authoring-evidence.md` duplicates the `diff` and `diagram` registry text.
- `page-authoring.md` duplicates `assets/registry.json`.
- targeting, visual-review and command-hub each repeat their guidance in their
  registry's `x-guidance`.
- The retry rule appears in `event-batches.md` and `codex-watcher.md`.
- `host-claude-code.md` and `developing-leaf` both say a subagent's claim is the
  session's.
- `host-claude-code.md` and `session-lifetime.md` both describe the nudge.

## Delivery loop

These rules came from the first pass, which looked only at the delivery loop:
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
