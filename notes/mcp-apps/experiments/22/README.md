# Experiment 22: End-to-end complete Leaf page

## Purpose

Continue past the reference host's unstable diagnostic subtree and measure the
now-authorized full Leaf page.

**Changes from experiment 21:**

- Verify the submitted page path in the host's rendered body rather than in a
  replaced `<pre>` child.
- Change no Leaf code, cookie policy, frame declaration, fixture, or page check.

**Expected outcomes:**

- The normal Leaf runtime reaches upgraded, applied, and presented readiness.
- The inline surface remains a constrained preview and fullscreen restores the
  ordinary page layout.
- Accessibility and console readings are clean, and a keyboard choice appends
  the normal action event to the page log.

## Findings

The host body verified the exact page path, but the new bypass then referenced
the skipped disclosure locator variable and exited with `UnboundLocalError`.
This is solely experiment control flow; the tool call and app had no console
errors before the typo. Experiment 23 scopes that locator assertion to the old
diagnostic branches and changes nothing under test.
