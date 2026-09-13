# TODO

Items are ordered by priority. Each names the result. When an item needs active
investigation detail, keep it in a linked note. Completed work and rejected alternatives
remain in git history.

## Now

- **Establish the first agent-usability baseline.** Build the cold-authoring,
  reading-parity, and resume fixtures described in
  [the evaluation plan](notes/agent-usability-evals.md#first-executable-slice), then use
  their failures to choose any new reading interface.

- **Prototype short conversations in the margin projection.** Compare a pinned marker card
  with a sparse left-comment layout on wide pages. Keep complete history and search in
  Threads, use the existing Page Map dialog on narrow pages, and never leave both margin
  presentations visible at once.

## General reader continuity

- **#11 — [Let newer navigation win over revision
  restoration](notes/workspace-followups.md#item-11).** Use navigation intent to prevent
  an old reading capture from overwriting input made during revision activation. The
  race belongs to version travel generally; independent pane scrollports only exposed
  more instances of it.

## Workspace follow-ups

The workspace research after [PR #455](https://github.com/max-sixty/leaf/pull/455)
produced the following backlog. IDs match the research discussion, not GitHub issues.
The [research briefs](notes/workspace-followups.md) retain evidence, completion
criteria, dependencies, and Sol/Astra assignments. Items are ordered within each group.

Continue with the remaining composition verification.
Keep the current primitives; let those uses establish demand for more. Defer the
authoring evaluation until Leaf's shape is stable enough for the comparison to last.

### Composition verification

- **#14 — [Verify the complete keyboard and accessibility
  route](notes/workspace-followups.md#item-14).** Exercise the workspace as one keyboard
  task, including reading, pane furniture, local comments and Threads.

### Authoring and product boundary

- **#19 — [Measure what Leaf saves an authoring
  agent](notes/workspace-followups.md#item-19).** Run a small blind authoring comparison
  against plain HTML, including the cost of the subsequent feedback cycle. Extend the
  existing agent-usability evaluation plan with this comparison.

- **#20 — [Teach the few compositions that earn their
  place](notes/workspace-followups.md#item-20).** Put tested document, configuration and
  queue/detail recipes into the existing package guidance.

- **#22 — [Verify workspaces at the experimental MCP
  boundary](notes/workspace-followups.md#item-22).** Check the same workspace in a full
  iframe, a constrained host and the existing snapshot/browser handoff.

- **#23 — [Find out whether people return to a
  workspace](notes/workspace-followups.md#item-23).** Run repeated real tasks to decide
  how much persistence and workspace customization Leaf should own. Requires Max to
  choose and participate in real recurring tasks.

## Later

- **Find a specific first task for the public home page.** The current page starts
  with the comment-and-revise loop: a visitor asks Leaf guide to edit their private copy.
  Replace that interim prompt only after testing a task a new visitor would actually
  bring; avoid canned choices that manufacture work for the guide.

- **Decide whether suggested replacements need a proper diff.** Compare the current
  plain replacement with a before-and-after view in Threads and inline conversations.
  Add the diff only if it makes nontrivial edits easier to review without duplicating
  the quoted passage.

- **Decide whether visual review needs expanded inspection.** Compare an embedded review
  with the same run as a bounded root review. Add expansion only if focused workspaces do
  not cover the real tasks, and keep it package-owned until a second interactive object
  proves the same entry, state-preservation, return, narrow-screen, copy, and print
  lifecycle.

- **Test whether one Leaf artifact needs several page-level views.** Start from a real
  task that cannot remain coherent as one document or one queue/detail workspace. Compare
  stable page-level tabs with separate linked Leaf pages, including URLs, revisions,
  conversations, keyboard navigation, narrow screens, and export. Do not add a router or
  another persisted selection model before that case exists.

- **Let readers disable character bindings.** Define one route filter with a complete
  persistence and accessibility contract. Commands, non-character routes, and visible
  controls remain available.

- **Add disclosed masks to visual-review evidence.** Authored case-level focus areas now
  make small changes findable without adding nested review units. Add masks only once
  repeated reviews establish the smallest disclosure and export contract.

- **Open visual-review targets beside Leaf through the host.** Coordinate the exact
  case URL in a real browser pane and report mutable-preview staleness without treating
  arbitrary iframes as live evidence.

- **Add typed motion evidence after the media boundary supports it.** Define durable
  video, poster, caption, transcript, and chapter handling in Leaf core; then let visual
  runs attach motion only to cases whose timing or continuity is under review.

- **Add a foreground path for other agent hosts.** Document a blocking `leaf wait` flow
  for any host that can run a command, then use that experience to define a shared host
  adapter only if another integration needs it.

- **Measure a pending count in the favicon.** Prototype the count at 16px and keep it
  only if it remains legible beside the existing status treatment.

- **Give the touch grip room of its own, then fit more thread cards.** At a coarse
  pointer the panel's resize grip is a 44px square laid over the list, and nothing
  reserves that space: cards run under it at every scroll position, so whether its
  focus ring lands on a button is luck. Tightening the cards' spacing moved one Send
  button up onto it and
  `test_coarse_pointer_resize_reach_stays_reachable_without_trapping_scroll` said so,
  which is why e4cd887f was reverted.
  Reserving a full-height gutter would contradict the grip's own design — a local
  handle, not a scroll-blocking wall — so settle what the phone sheet owes it first.
  Spacing alone does not fit a third card either: the card's own content already
  exceeds a third of the list's height, which is the reply box and Send/Resolve row
  every card carries. Collapsing that to a single Reply affordance until the reader
  enters the card is the change that would.

- **Make the experimental direct MCP bundle fail loud on an evaluation-order fault.**
  `scripts/mcp-app/direct-build.mjs` bundles the full runtime for the direct-page
  experiment; it is not the shipped MCP App. Esbuild hoists cross-module `let`/`const`
  into `var`s, so a fault the ordinary page throws reads `undefined` in this experimental
  bundle. Give its direct probe a reading that sees the fault, or preserve the dead zone.
