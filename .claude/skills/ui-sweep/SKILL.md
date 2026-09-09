---
name: ui-sweep
description: Use the shipped examples like a user in a real browser and fix the interaction defects the sweeps can't see — placement, tracking, legibility, crowding. Run after runtime or theme changes, or as a standing dispatch.
---

# UI sweep

The suite holds the invariants somebody has already stated: render_version gates a
page's rendering, and the press and poll sweeps hold it still under the aim. The
defects that reach the user first are the ones nobody has stated yet — a float
that parts from its passage on scroll, a diagram scaled below legibility, an input
that stops growing at ten lines. Those are found by using the page. This skill is
that use: drive, judge, fix, pin.

## Drive

Serve pages the way the browser suite does (`serve` and `open_page`, which
tests/render_harness.py owns, or `scripts/preview.py <example> --automation` for a
live preview) and drive them with real input. Both routes use the process-owned
temporary server, so gestures traverse the real HTTP and event-log loop without
becoming reader feedback in the task. Tour the gallery and one prose-heavy example,
at 1200×900 and 1440×900, in both color schemes. At each station take a screenshot
and record the geometry it claims:

1. Select mid-paragraph, raise the 💬, open the composer, type twenty lines.
2. Scroll ±300px with the composer open.
3. ⌥-click a widget and repeat 2.
4. Repeat 1 with the panel open, and at the covering-sheet width.
5. Work the widgets: drag a card, pick an option, accept a suggestion, switch a
   tab, edit a draft.
6. Switch versions with a draft unsent.
7. Emulate print and compare with the screen reading.

Watch the route into and out of each state, not only the frame after it settles. Motion
starts inside the gesture that causes it and `motion()` cancels each animation a
microtask after it finishes, so hold it before driving rather than on noticing:
`open_page(..., init_script=HOLD_MOTION)`, using the hold from
`tests/render_cases_interaction.py`, pauses every `motion()` animation at time zero to
seek. CSS animations run outside that patch, so sample their geometry frame by frame
instead. Record the endpoints and the path. A route that reverses, overshoots its
settled boxes, or repeatedly changes responsive posture is a finding even when both
endpoints are sound.

For every paint-only transition, compare the same target's hit-test rectangle before,
during, and after the state change. Hover, focus, and keyboard hints may add paint around
a target; they do not move the target itself.

## Judge

Read the frames against the layer-wide UI laws and render-gate table in
`skills/leaf/assets/CLAUDE.md`, and the module headers its ownership map names; each
norm there is a checklist row. Then judge the craft the norms don't state: nothing
stands on words being read or written about, nothing renders below legibility, nothing
runs out of room while the screen has some, floats track what they point at. A finding
is a reproduced number or screenshot, not an impression.

Avoid AI-slop visual patterns. Do not use rounded one-sided borders, and do not
reflexively wrap sections in rounded cards, tints, gradients, or soft shadows. Start
from the page's content and hierarchy; use a visual treatment only when it communicates
a real relationship or state.

## Fix and pin

Fix each finding. Pin only behavior that a check can decide without reproducing the
design judgment: a measurable page defect goes in render_version, and a gesture defect
becomes a test in whichever test_render_*.py module owns it. Put the bug back once and
watch the new check fail. Keep visual grammar in this skill and the browser review,
rather than writing detectors for particular CSS treatments. When a treatment causes a
concrete failure such as covered content, test that failure. The run ends as a green
branch and a report, and landing waits for the go-ahead.
