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

- **Make the MCP bundle fail loud on an evaluation-order fault.** esbuild hoists
  cross-module `let`/`const` into `var`s, so a fault the browser throws on reads
  `undefined` in the bundle; give `test_render_mcp` a probe that would see it, or build
  the bundle in a form that keeps the dead zone.
