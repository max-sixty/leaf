# Experiment 50: Capture hidden-comment geometry

## Purpose

Repeat experiment 49, adding failure-only ancestor-style and screenshot capture.
No runtime or transport changes. Determine why the headless sequence leaves
the comment hidden while the reopened page in experiment 48 displays it.

Expected outcome: either the test passes or the artifact names the hidden
ancestor. Do not treat a durable log append as proof of visible comment UI.

## Findings

The comment was visible in the floating inline thread; the separate Threads
dialog was closed. The observer waited for disk append, then opened Threads
before the asynchronous send continuation completed. That continuation opens
the inline reply and closes the overview. Existing runtime behavior, confirmed
in composing/selection.js and living-margin.js, not a transport failure.

The next observer waits for the new inline reply to receive focus before opening
Threads, matching the canonical browser suite. The screenshot also shows a
cramped inline card at this iframe width; the overview panel is readable in the
larger IAB viewport. This prototype does not establish compact-layout parity.
