# TODO

Items are ordered by priority. Each names the result; investigation detail belongs in
the relevant design note or in git history.

## Now

- **Establish the first agent-usability baseline.** Build the cold-authoring,
  reading-parity, and resume fixtures described in
  [the evaluation plan](notes/agent-usability-evals.md#first-executable-slice), then use
  their failures to choose any new reading interface.

- **Prototype short conversations in the Living Margin.** Compare a pinned marker card
  with a sparse left-comment layout on wide pages. Keep complete history and search in
  Threads, use the existing Map sheet on narrow pages, and never leave both margin
  presentations visible at once.

## Workspace follow-ups

The workspace research after [PR #455](https://github.com/max-sixty/leaf/pull/455)
produced the following backlog. IDs match the research discussion, not GitHub issues.
The [research briefs](notes/workspace-followups.md) retain evidence, completion
criteria, dependencies, and Sol/Astra assignments. Items are ordered within each group.

Continue with the remaining reader-continuity checks and composition experiments.
Keep the current primitives; let those uses establish demand for more. Defer the
authoring evaluation until Leaf's shape is stable enough for the comparison to last.

### Reader continuity

- **#10 — [Make pane overflow discoverable](notes/workspace-followups.md#item-10).**
  Test a subtle continuation cue for bounded panes with more content below the visible
  edge.

- **#11 — [Let newer navigation win over revision
  restoration](notes/workspace-followups.md#item-11).** Use navigation intent to prevent
  an old reading capture from overwriting input made during revision activation.

- **#12 — [Compare Threads overlay with Keep
  beside](notes/workspace-followups.md#item-12).** Try overlay as the quick-access
  default, with an explicit Keep beside choice for sustained conversation.

- **#14 — [Verify the complete keyboard and accessibility
  route](notes/workspace-followups.md#item-14).** Exercise the workspace as one keyboard
  task, including reading, pane furniture, local comments and Threads.

### Complete workflows

- **#16 — [Prove a current-versus-proposed
  comparison](notes/workspace-followups.md#item-16).** Show two real alternatives
  simultaneously and let the reader discuss each before committing one choice.

- **#18 — [Try an exception-driven monitoring
  workspace](notes/workspace-followups.md#item-18).** Use the existing live-progress
  example to test a stable overview beside changing evidence and an exception that needs
  a decision.

### Authoring and product boundary

- **#19 — [Measure what Leaf saves an authoring
  agent](notes/workspace-followups.md#item-19).** Run a small blind authoring comparison
  against plain HTML, including the cost of the subsequent feedback cycle. Extend the
  existing agent-usability evaluation plan with this comparison.

- **#20 — [Teach the few compositions that earn their
  place](notes/workspace-followups.md#item-20).** Put tested document, configuration and
  queue/detail recipes into the existing package guidance.

- **#21 — [Test whether custom roots need shared fitting
  policy](notes/workspace-followups.md#item-21).** Use one genuinely different package
  root to decide whether responsive fit ownership belongs in the shared API.

- **#22 — [Verify workspaces at the experimental MCP
  boundary](notes/workspace-followups.md#item-22).** Check the same workspace in a full
  iframe, a constrained host and the existing snapshot/browser handoff.

- **#23 — [Find out whether people return to a
  workspace](notes/workspace-followups.md#item-23).** Run repeated real tasks to decide
  how much persistence and workspace customization Leaf should own. Requires Max to
  choose and participate in real recurring tasks.

## Later

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
