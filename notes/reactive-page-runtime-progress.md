# Joint implementation checkpoint

This is a handoff for the unfinished [page-instance boundary](page-instance-boundary.md)
and [reactive runtime](reactive-browser-runtime.md) program, not another specification.
The user requested Astra implementation in worktrees, then asked to conserve tokens.
The implementation remains local on `reactive-page-runtime`; it is not ready to merge.

## Integrated foundation

- Page-owned declarations and widgets compose with the selected layer.
- Revisions capture HTML, registry, runtime, authored modules, styles, and media as an
  immutable dependency graph. Historical documents and event admission use captured
  contracts instead of mutable candidate files.
- Activation starts a fresh document with explicit continuity handoff. Parsed delivery
  rewrites imports and URLs without changing prose or duplicating page-module execution.
- Live shells and website bundles publish revision-specific resources. Static export
  inlines captured styles and media, including images added in conversation afterward.
- A locked contributor build supplies Lit, Signals, and TypeScript output as committed
  self-contained assets. Authors and plugin users need no Node build.

## Remaining implementation

Finish and verify the real immutable semantic publisher before converting widget
templates. Its root must hold accepted truth, authored inputs, unresolved gestures,
and complete effective projections. Presentation failure must not roll accepted truth
back. Pending delivery and DOM commit proofs remain mechanical state, not another fold.

The publisher implementation is isolated in its worktree, not integrated. Eight Node
build/domain tests and two focused browser cases passed, but broader outbox/startup
tests have failures, including an unanswered-resolution regression and assertions for
the superseded accepted-state rollback contract. Resume from that agent's checkpoint;
do not cherry-pick it as a verified slice.

The broader Lit conversion, public read/command/presentation API, semantic/presentation
tickets, and offline interactive export remain unfinished. Do not describe the program
as complete because the dependency build or revision capture is green.

Candidate vocabulary compatibility needs a targeted implementation: preserve frozen
thread markup and commands, and every page-event contract still participating in the
candidate projection, including predecessors an undo can expose. Historical-only page
records can use their captured registry. The existing whole-log `vocabulary_gaps`
re-vendor validator is not a safe activation gate: it reads mutable prior registry and
revalidates unrelated historical records. An experimental unconditional invocation was
removed, not retained as a compatibility solution.

## Verification checkpoint

The last everyday suite before the latest integration fixes was **1052 passed, 14
failed**. The failures covered captured-contract fixture expectations, revision-scoped
website paths, and MCP/media behavior. Focused fixes are being verified; this is not a
green full-suite result. Subsequently, all 470 contract/document/product interaction
tests passed, as did eight focused session, website-server, and real-browser smoke
cases. Run the final everyday suite after all slices are integrated.

The website bundler slice passed 61 worker tests, typecheck, five immutable-shell tests,
three site tests, and a complete site build/bundle. Local pre-commit passes.

One render-gate failure was reproduced at clean base `214588e3`: the `new-widget`
parameter of `test_render_accepts_actions_made_after_the_authored_change` lacked its
banner at dark 1200×900 under `-n0`. That evidence covers only that exact failure.

Before landing, run the remaining browser journeys and compare startup requests/bytes
with the base using `scripts/verify-site-local.sh`; no performance improvement is
established yet. Review the integrated semantic publication path and refresh this
checkpoint with final test evidence. Landing still needs explicit authorization.

## Worktree ownership

- Integration: `/Users/maximilian/workspace/leaf.reactive-page-runtime`.
- Semantic publisher: `/Users/maximilian/workspace/leaf.astra-fresh-revision-activation`.
- Contributor build and website bundler: `/Users/maximilian/workspace/leaf.astra-browser-build`.
- Captured revisions, static export, and MCP: `/Users/maximilian/workspace/leaf.astra-revision-artifact`.

Do not discard these branches or treat another worktree's unfinished edits as integrated.
Use the integration branch's commit history to identify which slices were cherry-picked.
