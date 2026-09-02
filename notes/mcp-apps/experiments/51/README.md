# Experiment 51: Wait for the completed comment gesture

## Purpose

Repeat experiment 50, waiting for the newly submitted comment's inline reply
to receive focus before opening Threads. This separates the durable append from
the UI continuation that follows it. No runtime or transport code changes.

Expected outcome: the fresh choice and comment, canonical thread panel,
ui/message, and no-network assertions all pass. Keep the host as a live preview.

## Findings

The corrected lifecycle check passed: the choice and fresh anchored comment
were durable, and the canonical thread panel was visible (direct-comment.png).
The test then failed trying to mouse-click the probe-only button fixed at the
bottom of a tall auto-sized iframe: Playwright could not scroll that button
into its outer viewport. The next run uses the button's native keyboard route.
This is a probe-control/host sizing issue, not a Leaf event rejection.
