# Workspace follow-ups

Briefs for the remaining workspace items in [TODO.md](../TODO.md). IDs are stable
references; their order here is not a priority ranking. The recurring-use study in #23
requires Max's real tasks.

## Authoring comparison

<a id="item-20"></a>

- **#20 — Teach the compositions that prove useful.** Test short composition
  suggestions against the failures the [plain HTML comparison](agent-usability-evals.md#authoring-against-plain-html-2026-10-12)
  observed, with an unfamiliar author.
  Keep widget-specific advice in `x-instructions`, cross-widget compositions in package
  instructions, and general selection principles in the authoring reference.

  The optional `code-review` package already suggests behavior comparisons; whether
  a cold author discovers and uses those instructions remains unmeasured. Test discovery
  before package selection and through the `author` value from `leaf page instructions PAGE`. Compare
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
