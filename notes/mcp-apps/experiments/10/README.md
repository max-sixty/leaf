# Experiment 10: Evidence-bearing compact ask

## Purpose

Repeat the official reference-host path after review exposed the option evidence,
made status messages visible, rejected invalid mutable source explicitly, and
corrected the open/read tools' side-effect annotations.

**Changes from experiment 8:**

- Each choice retains its short label and visibly includes the authored spoken
  evidence that distinguishes it.
- The footer visibly reports recording, success, refresh, and errors.
- Run axe-core inside the app frame.
- Measure the internal content scroller separately from document overflow.

**Configuration:**

- Transport, fixture, reference-host commit, outer frame (420×360), and keyboard
  action unchanged from the successful reference-host experiments.

**Expected outcomes:**

- All three option labels and all three non-empty evidence summaries are present.
- The document itself does not overflow; the bounded content region may scroll to
  preserve complete evidence at narrow width.
- Keyboard choice appends the ordinary action and exposes a visible success status.
- Axe reports no violations in the app frame.

## Findings

The app loaded and the nine focused protocol tests passed, but the run stopped at
the new accessibility check. `base.app_frame` returns a `FrameLocator`, while
`axe-playwright-python` calls `evaluate` on the concrete object it receives;
`FrameLocator` has no such method. No product assertion failed and the keyboard
action was not reached. Experiment 11 changes only the axe target to the innermost
concrete Playwright `Frame`.
