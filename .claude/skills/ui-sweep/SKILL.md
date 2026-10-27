---
name: ui-sweep
description: Audits shipped examples in a real browser and fixes interaction and visual defects. Use after runtime or theme changes, or as a recurring dispatch.
---

# UI sweep

Use the gallery and a composed example to find defects beyond the suite's stated
invariants. Derive experiments from the user's task and the code's interaction
structure, then drive, judge, and fix them in the browser.

## First reading

Open the exact candidate before reading its implementation or the author's verdict,
and use the page for its stated task at ordinary browser zoom. Before an input, name
the subject information the reader needs to choose and correct it. Inspect the
user-controlled intermediate states, compare that information with its pre-input view,
and judge whether the interaction's controls and feedback preserve access to it. Vary
user-controlled sizes from the smallest useful case to the largest, and positions
through their useful range, alongside viewport dimensions. Record the initial visual problems in the subject,
actions, evidence, and supporting information. Give an independent reviewer the task
and candidate before the author's assessment.

## Derive

For a recurring sweep, start from a user workflow in the examples.
`browser/AGENTS.md` holds the UI contracts, render gates, and the
ownership map. Read the source as part of the audit, including when delegating it.

Keep a short working model of the interaction: the user's goal; the source, control,
surface, focus, and retained state involved; and the transitions that create,
transfer, or end their relationships, noting where different owners cooperate.
Derive expected behavior from the contracts and the user's goal, use the
implementation to establish reachable states and mechanisms, and name unsettled
design assumptions.

## External review

Choose an additional perspective from "External UI skills" in
`../developing-leaf/SKILL.md`. When review scope is open, offer the relevant options
with a recommendation, such as visual critique, technical audit, or a broader sweep,
and continue the authorized review while the choice is pending.

Apply the current
[Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md)
to changed controls and their dependent interactions. For composition questions,
start with Impeccable's `critique`, then its relevant focused workflows. Read the
installed skill and the selected playbook in full. When a skill is unavailable, say so
and use its upstream guidance or Leaf's browser workflow.

Verify findings against ordinary browser use and Leaf's owning contracts; authoring
preferences remain the author's and user's choices, and Leaf's browser proof,
baseline comparisons and retained-state checks still apply. Report verified findings,
coverage and unresolved judgments.

## Review a design system

For changes to the theme or reusable controls, judge the affected design decisions
across foundations, component states, and a real user task, extending the existing
gallery or package scenarios to show them and sizing the review to what changed.

Map the affected color roles, type scale, spacing, radius, elevation, and control
sizes to their canonical tokens and component styles, and keep related controls
aligned when dimensions change. Distinguish a design brief's choices from anything
inferred, such as a dark scheme.

Show text on the surfaces it actually uses, labeled with the tokens, resolved colors,
and contrast measured from the rendered foreground and background in the affected
schemes and states, including translucent layers. Judge it against current
accessibility guidance; a specified color can still fail.

For primitives, show representative variants and their default, hover, focus,
pressed, and disabled states side by side, with labels outside the control, using the
component's real renderer and styles and confirming the states with ordinary input.
For composed controls, show the typical use and the edge cases that change behavior or
layout, such as long content, empty, error, or loading, choosing cases that expose
different decisions rather than every combination. Then exercise a realistic composed
example built from the same tokens and components through its user journey, to judge
whether hierarchy, density, and control relationships serve the task.

## Challenge

Before validating a proposed result, write competing failure hypotheses for the
riskiest relationships, prioritizing changed ownership boundaries and relationships
the existing tests leave unexercised. Give each a mechanism, an observable
consequence, and an experiment that could disprove it.

Generate experiments by perturbing the model: nest or replace an interaction, reverse
or cancel it, exhaust its available room, or change external state while it remains
active. Where several modes take turns in one place, switch through each with no
content in it and compare the place's box with the token that sizes it
(`browser/AGENTS.md`, "Shared containers determine control dimensions"). Vary one factor at a time across an ownership boundary, exercise both the
forward and return paths, and include an unrelated change that should preserve the
active relationship. State what must change and what must survive before driving.
When a change sends an existing surface into a different layout or fallback, compare
the same user task against the merge base; the candidate must preserve its
task-relevant information and actions.

Choose content density, viewport boundaries, input routes, and visual states that
distinguish the hypotheses, and carry a tested relationship into a different composed
example. For a changed layout, find a width or content length where a group first
wraps or rearranges and inspect both sides of that transition. Include a constrained
height when the surface claims to fit the viewport.

## Observe

Serve pages with `serve` and `open_page` from `tests/render_harness.py`, or a plain
`uv run leaf-dev preview <example>` in the background. Both exercise the real HTTP and
event-log loop without delivering feedback to the task. Give independent runs separate
page state, drive with real input, and confirm each intended transition occurred.

For each experiment record initial state → input → expected relationship → observed
result, with the evidence that decides the claim: focus, surface and owner identities
and retained values where they matter, measured geometry for spatial claims, paired
screenshots for hierarchy, spacing, and paint. For motion, capture the path as well as
the endpoints (`tests/AGENTS.md`, "Frames, sequences, and instants"). `HOLD_MOTION`
patches `Element.prototype.animate`, which CSS animations bypass, so sample their
geometry frame by frame. For a paint-only transition, compare the target's hit-test
rectangle before, during, and after it.

Judge the whole composition and its details at native scale, region by region: the
subject, actions, evidence, and supporting information. Check that labels and values
group and align, text wraps at meaningful boundaries, controls and icons stay legible,
and space follows the active task. Capture the full viewport for composition, and
native-scale details where the full image can't support the judgment. Computed styles
and geometry explain a visual result but don't establish that it looks coherent. Test
affected paint in both color schemes and in print.

Judge against `browser/AGENTS.md`, "Interface principles". Visual grammar stays a browser
judgment; automate only the concrete failures it finds.

## Reconcile

Give every finding a disposition, including discoveries outside the planned route:
reproduced and fixed, disproved with evidence, or unresolved with the missing evidence
named. Fix a reproduced defect at its owning boundary, then repeat the failing
experiment and a sibling derived from the same relationship.

Pin a measurable page defect in `render_version` and a gesture defect in the owning
`test_render_*.py` module, and put the bug back once to watch the new check fail.
Report established behavior, unresolved findings, and untested relationships, counting
an uncompleted transition as untested. Report functional and visual coverage
separately, naming the regions and states judged in the browser; passing interaction
checks or collecting screenshots is not a visual verdict.
