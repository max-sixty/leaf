# TODO

Items are ordered by priority. Each names the result; investigation detail belongs in
the relevant design note or in git history.

## Now

- **Cover every focus indicator.** Extend
  `test_every_ring_the_layer_draws_is_shown_whole_somewhere_in_the_corpus` so accent
  `box-shadow` focus rings take part in its geometry sweep. Recheck `corpus` and
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

- **Wire elements where they are built.** Let each chrome element's owner attach its
  own DOM listeners and scopes at module scope and call the behavior's owner from the
  handler, so `mountChrome` keeps only the steps that need the document (the banner's
  reservations, the layout observers, the margin's appends). While there, settle one
  idiom for owner state other owners read: `export let` bindings or reader functions,
  not both.

- **Validate scopes at the first paint.** Stop `keys()` running row callbacks as a
  module evaluates: validate every scope on its first paint, the way capability-gated
  scopes already are, and move the ambiguous-row refusal in
  `test_a_scope_cannot_give_one_live_key_two_meanings` to that boundary. This closes the
  one evaluation-order path the `leaf/evaluation-order` rule cannot see.

- **Make the MCP bundle fail loud on an evaluation-order fault.** esbuild hoists
  cross-module `let`/`const` into `var`s, so a fault the browser throws on reads
  `undefined` in the bundle; give `test_render_mcp` a probe that would see it, or build
  the bundle in a form that keeps the dead zone.
