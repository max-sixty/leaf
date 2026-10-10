---
name: ui-sweep
description: Audits shipped examples in a real browser and fixes interaction and visual defects. Use after runtime or theme changes, or as a standing dispatch.
---

# UI sweep

Use the gallery and a composed example to find defects beyond the suite's stated
invariants. Derive experiments from the user's task and the code's interaction
structure, then drive, judge, and fix them in the browser.

## First reading

Open the exact candidate before reading its implementation or the author's verdict.
Use the page for its stated task at ordinary browser zoom. Before an input, name
the subject information the reader needs to choose and correct it. Inspect
user-controlled intermediate states and compare that information with its pre-input
view: judge whether the interaction's controls and feedback preserve access to it.
Vary user-controlled sizes from the smallest useful case to the largest, and
positions through their useful range, alongside viewport dimensions.
Record the initial visual problems in the subject, actions, evidence, and supporting
information. Give an independent reviewer the task and candidate before giving them
the author's assessment.

## Derive

For a standing sweep, start from a user workflow in the examples. Use
`skills/leaf/assets/AGENTS.md` for UI contracts, render gates, and the
ownership map.
Source access belongs in this audit, including when delegating it.

Keep a short working interaction model: the user's goal; the source, control,
surface, focus, and retained state involved; and the transitions that create,
transfer, or end their relationships. Identify where different owners cooperate.
Derive expected behavior from the contracts and user's goal; use implementation
to establish reachable states and mechanisms. Name unsettled design assumptions.

## External review

Use "External UI skills" in `../developing-leaf/SKILL.md` to choose an
additional review perspective. When review scope is open, offer the relevant
options with a recommendation: visual critique, technical audit, or a broader
sweep. Select the tool for the user's question and proceed with authorized
review work while any optional preference is pending.

Apply the current
[Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md)
to changed controls and their dependent interactions. For composition questions,
start with Impeccable's `critique`; follow its relevant focused workflows when
refining the result. Read the installed skill and the selected playbook in full.
When a skill is unavailable, state that and use its upstream guidance or Leaf's
browser workflow; keep the review moving.

Verify findings against ordinary browser use and Leaf's owning contracts.
Authoring preferences remain the author's and user's choices. External guidance
adds a perspective; Leaf's browser proof, baseline comparisons and retained-state
checks still apply. Report verified findings, coverage and unresolved judgments.
A comparison of review methods records matched inputs and cost separately from
ordinary review; finding counts alone do not establish a tool's contribution.

## Review a design system

For changes to the theme or reusable controls, judge the affected design decisions
across foundations, component states, and a real user task. Extend the existing
gallery or package scenarios to make those decisions visible; size the review to
what changed.

Read any design brief and the existing theme before editing. Map the affected color
roles, type scale, spacing, radius, elevation, and control sizes to their canonical
tokens and component styles. Keep related controls aligned when dimensions change.
Distinguish the brief's choices from anything inferred, such as a dark scheme.

Show text on the surfaces it actually uses, labeled with the tokens, resolved
colors, and measured contrast. Measure the rendered foreground/background pairs
in the affected schemes and states, including translucent layers. Judge them
against the current accessibility guidance from "External review"; a specified
color can still fail it.

For primitives, show representative variants and default, hover, focus, pressed,
and disabled states side by side where they apply, with labels outside the control.
Use the component's real renderer and styles, and confirm the states with ordinary
input in the live component. For composed controls, show the typical use and the
edge cases that change its behavior or layout, such as long content, empty, error,
or loading. Choose cases that expose different decisions rather than every
combination.

Use a realistic composed example built from the same tokens and components, with
task-specific content. Exercise its user journey to judge whether the hierarchy,
density, and control relationships work together. The specimens make individual
choices inspectable; the composed example shows how they serve the task.

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
driving. When a change sends an existing surface into a different posture or
fallback, compare the same user task against the merge base; the candidate must
preserve its task-relevant information and actions. Include an unrelated change
that should preserve the active relationship.

Choose content density, viewport boundaries, input routes, and visual states that
distinguish the hypotheses. Carry a tested relationship into a different composed
example to challenge assumptions the gallery makes easy. For a changed layout, find a
width or content length where a group first wraps or rearranges and inspect both sides
of that transition. Include a constrained height when the surface claims to fit the
viewport.

## Observe

Use `serve` and `open_page` from `tests/render_harness.py`, or
`uv run leaf-dev preview <example>` run as a background task.
These process-owned servers exercise the real HTTP and event-log loop without
delivering user feedback to the task. Give independent runs separate page state.
Drive with real input and confirm each intended transition occurred.

For each experiment record initial state → input → expected relationship →
observed result, with the evidence that decides the claim. Read focus, surface
and owner identities, and retained values where those matter. Measure geometry
for spatial claims; inspect paired screenshots for hierarchy, spacing, and paint.
For motion, capture the path as well as endpoints: `tests/AGENTS.md`,
"Frames, sequences, and instants", owns the recording and
`HOLD_MOTION` mechanics. The hold patches `Element.prototype.animate`; CSS
animations bypass it, so sample their geometry frame by frame. Settled boxes
cannot establish a smooth transition.
For paint-only transitions, compare the same target's hit-test rectangle before,
during, and after the state change; added paint does not move its target.

Judge both the whole composition and its details at native scale. Inspect the subject,
actions, evidence, and supporting information; quality in one region says nothing about
another. Check whether labels and values group and align, text wraps at meaningful
boundaries, controls and icons remain legible, and space follows the active task. Capture
the full viewport for composition and native-scale details wherever the full image cannot
support that judgment. Computed styles and geometry explain a visual result; they do not
establish that it looks coherent. Test affected paint in both color schemes and in
print.

Judge against `skills/leaf/assets/AGENTS.md`, "Layout and motion". Keep visual
grammar in browser judgment; automate the concrete failures it causes.

## Reconcile

Give every finding a disposition, including discoveries outside the planned
route: reproduced and fixed, disproved with evidence, or unresolved with the
missing evidence named. Fix reproduced defects at their owning boundary, then
repeat the failing experiment and a sibling derived from the same relationship.

Pin measurable page defects in render_version and gesture defects in the owning
`test_render_*.py` module. Put the bug back once and watch the new check fail.
Report established behavior, unresolved findings, and untested
relationships explicitly; uncompleted transitions remain untested. Report functional and
visual coverage separately, naming the regions and states judged in the browser. Passing
interaction checks or collecting screenshots is not a visual verdict.
