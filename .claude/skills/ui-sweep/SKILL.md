---
name: ui-sweep
description: Audits shipped examples in a real browser and fixes interaction and visual defects. Use after runtime or theme changes, or as a standing dispatch.
---

# UI sweep

Use the gallery and a composed example to find defects beyond the suite's stated
invariants. Derive experiments from the reader's task and the code's interaction
structure, then drive, judge, and fix them in the browser.

## Derive

Read the changed code and its callers. For a standing sweep, start from a reader
workflow in the examples. Use `skills/leaf/assets/CLAUDE.md` for UI contracts,
render gates, and the ownership map; read the relevant owners' module headers.
Source access belongs in this audit, including when delegating it.

Keep a short working interaction model: the reader's goal; the source, control,
surface, focus, and retained state involved; and the transitions that create,
transfer, or end their relationships. Identify where different owners cooperate.
Derive expected behavior from the contracts and reader's goal; use implementation
to establish reachable states and mechanisms. Name unsettled design assumptions.

## Challenge

Before validating a proposed result, write competing failure hypotheses for the
riskiest relationships. Give each a mechanism, an observable consequence, and an
experiment that could disprove it. Prioritize changed ownership boundaries and
relationships the existing tests leave unexercised.

Generate experiments by perturbing the model: nest or replace an interaction,
reverse or cancel it, exhaust its available room, or change external state while
it remains active. Choose the operators that challenge the hypothesized mechanism.
Vary one factor at a time across an ownership boundary and exercise both the
forward and return paths. State what must change and what must survive before
driving. Include an unrelated change that should preserve the active relationship.

Choose content density, viewport boundaries, input routes, and visual states that
distinguish the hypotheses. Carry a tested relationship into a different composed
example to challenge assumptions the gallery makes easy.

## Observe

Re-vendor before testing. Use `serve` and `open_page` from
`tests/render_harness.py`, or `scripts/preview.py <example> --automation`.
These process-owned servers exercise the real HTTP and event-log loop without
delivering reader feedback to the task. Give independent runs separate page state.
Drive with real input and confirm each intended transition occurred.

For each experiment record initial state → input → expected relationship →
observed result, with the evidence that decides the claim. Read focus, surface
and owner identities, and retained values where those matter. Measure geometry
for spatial claims; inspect paired screenshots for hierarchy, spacing, and paint.
For motion, capture the path as well as endpoints: `tests/CLAUDE.md`,
"Distinguish a frame, a sequence, and an instant", owns the recording and
`HOLD_MOTION` mechanics. The hold patches `Element.prototype.animate`; CSS
animations bypass it, so sample their geometry frame by frame. Settled boxes
cannot establish a smooth transition.
For paint-only transitions, compare the same target's hit-test rectangle before,
during, and after the state change; added paint does not move its target.

Judge the rendered experience: can the reader identify the subject, read the
surface alongside its context, and find the next action? Check legibility, room,
and visual continuity. Rank competing space claims by their relationship to the
active task. Test affected paint in both color schemes and affected export
behavior in print. Support visual findings with an inspected image and explain
the failed hierarchy, spacing, legibility, or interaction, even when tests pass.

Use visual treatments to communicate content hierarchy and state. Avoid rounded
one-sided borders and reflexive cards, tints, gradients, or soft shadows. Keep
visual grammar in browser judgment; automate the concrete failures it causes.

## Reconcile

Give every finding a disposition, including discoveries outside the planned
route: reproduced and fixed, disproved with evidence, or unresolved with the
missing evidence named. Fix reproduced defects at their owning boundary, then
repeat the failing experiment and a sibling derived from the same relationship.

Pin measurable page defects in render_version and gesture defects in the owning
`test_render_*.py` module. Put the bug back once and watch the new check fail.
Keep the implementation, tests, and owning contracts aligned, and run the
required checks. Report established behavior, unresolved findings, and untested
relationships explicitly; uncompleted transitions remain untested. Hand over the
reviewed branch and evidence; landing waits for the go-ahead.
