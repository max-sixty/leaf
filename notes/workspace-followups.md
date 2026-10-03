# Workspace follow-ups

Briefs for the remaining workspace items in [TODO.md](../TODO.md). IDs are stable
references; their order here is not a priority ranking. The authoring comparison in
#19 precedes the instructions experiment in #20. The recurring-use study in #23 requires
Max's real tasks.

## Keyboard and accessibility

<a id="item-14"></a>

- **#14 — Verify the complete keyboard and accessibility route.** Follow one named
  two-pane example through authored landmarks, header/footer controls, reading keys,
  a local comment, Threads, Escape and a change of workspace posture.

  Existing visual-review tests cover parts of this journey. The remaining check is
  their composition: every action has a comprehensible accessible name, every focus
  mark is visible, and closing a covering surface returns the user to the task.
  Exercise both an open Threads panel beside a usable page and the modal boundary
  where the panel covers it. Focus containment must follow that modality.

## Authoring comparison

<a id="item-19"></a>

- **#19 — Measure what Leaf saves an authoring agent.** Compare document-review,
  configuration and queue/detail tasks against plain HTML, including a comment and
  revision on each result. Give comparable agents the same content and acceptance
  criteria, and counterbalance task order.

  The [catalog](../evals/README.md) now compares document, dashboard and queue
  authoring and width revision with actual plain HTML controls. The [agent-usability baseline](agent-usability-evals.md#current-observations)
  measures reading, revision and the live loop. Neither establishes the advantage of
  Leaf's complete authoring and feedback cycle over plain HTML.

  The common quality judge reads the original request and screenshots. Leaf-only
  choice reading and preservation run after the shared comparison. Extend the
  comparison with equivalent comment/feedback cycles before claiming the whole
  loop saves author effort; then use repeated paired results to choose improvements.

  Assess usable output independently and retain failures, time/tokens, custom CSS
  and repair iterations. Use those results to choose which instructions or primitive to
  improve. Keep render-check defects and Layout choices in [TODO.md](../TODO.md),
  rather than treating a historical judge's finding as a current defect here.

<a id="item-20"></a>

- **#20 — Teach the compositions that prove useful.** After #19, test short
  composition suggestions against its observed failures with an unfamiliar author.
  Keep widget-specific advice in `x-instructions`, cross-widget compositions in package
  instructions, and general selection principles in the authoring reference.

  The optional `code-review` package already suggests behavior comparisons; whether
  a cold author discovers and uses those instructions remains unmeasured. Test discovery
  before package selection and through `leaf page instructions PAGE author`. Compare
  process simplification, structural change and an unchanged system: judge whether
  the user can identify the differences, rather than requiring a diagram everywhere.

  Keep instructions only when they improve the task without duplicated state or runtime
  internals. Add a discovery route only if the current routes fail that test.

## Recurring use

<a id="item-23"></a>

- **#23 — Find out whether people return to a workspace.** Use configuration, review
  and monitoring on recurring work Max chooses. Observe whether users reopen the
  page, need saved navigation or selection, abandon the flow, or prefer a fresh page.
  Compare the complete feedback cycle with their existing tools.

  Those observations should decide how much persistence and customization Leaf
  owns. Resizing, docking and saved layout presets need a demonstrated task before
  implementation.
