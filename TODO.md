# TODO

Items are ordered by priority. Each names the result; investigation detail belongs in
the relevant design note or in git history.

## Now

- **Cover every focus indicator.** Extend
  `test_every_ring_the_layer_draws_is_shown_whole_somewhere_in_the_corpus` so accent
  `box-shadow` focus rings take part in its geometry sweep. Recheck `gallery` and
  `ship-review` at the bottom of the viewport, then fix any clipping the wider sweep
  reports.

- **Offer structural authoring advice.** Add non-blocking advice to `version check`,
  starting with pages that have two or more section headings but no `lf-toc`. Keep the
  rules deterministic and optional; the first case is specified in
  [the agent-usability notes](notes/agent-usability-evals.md#near-term-usability-todo).

- **Fit more complete cards in the thread panel.** Reduce thread-card padding and
  spacing while preserving readable grouping, reachable controls, and focus-ring room.
  Judge the change on a 24-thread page with a before-and-after visual sweep.

## Next

- **Install outside packages by name.** Let `leaf package install SOURCE` place a
  package in a user-owned store and make `--package NAME` resolve installed and bundled
  packages through the same directory contract. Leave updates, pinning, and trust to
  later dogfooding.

- **Establish the first agent-usability baseline.** Build the cold-authoring,
  reading-parity, and resume fixtures described in
  [the evaluation plan](notes/agent-usability-evals.md#first-executable-slice), then use
  their failures to choose any new reading interface.

- **Prototype short conversations in the Living Margin.** Compare a pinned marker card
  with a sparse left-comment layout on wide pages. Keep complete history and search in
  Threads, use the existing Map sheet on narrow pages, and never leave both margin
  presentations visible at once.

## Later

- **Add a foreground path for other agent hosts.** Document a blocking `leaf wait` flow
  for any host that can run a command, then use that experience to define a shared host
  adapter only if another integration needs it.

- **Measure a pending count in the favicon.** Prototype the count at 16px and keep it
  only if it remains legible beside the existing status treatment.
