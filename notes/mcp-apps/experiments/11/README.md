# Experiment 11: Axe the concrete app frame

## Purpose

Complete experiment 10 after its accessibility probe confused the nested app's
`FrameLocator` with the concrete Playwright `Frame` that axe can evaluate.

**Changes from experiment 10:**

- Pass the innermost concrete frame to axe. Product code, fixture, dimensions,
  and actions are unchanged.

**Expected outcomes:**

- The evidence, scrolling, visible status, keyboard append, console, and axe
  readings all complete in one reference-host run.

## Findings

The measurement completed and found two CSS defects introduced by exposing the
evidence. The grid shell used `min-height: 100vh`, so its auto height grew to 610
pixels instead of holding the 354-pixel app viewport; the intended content
scroller never engaged and the success status landed below the visible frame.
Axe also reported three serious color-contrast violations, one for each evidence
summary using the host's secondary text token on the option panel.

The protocol and input path remained sound: all three evidence summaries were
present (303–471 characters), keyboard Enter appended the expected `choose`, and
the only console error was the reference host favicon. Experiment 12 changes
only the shell to a fixed viewport height and gives decision evidence the
primary text color.
