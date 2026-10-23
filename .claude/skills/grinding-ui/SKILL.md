---
name: grinding-ui
description: Runs iterative improvements to Leaf UI and authoring instructions through experiments and comparisons with plain HTML. Use to start or resume a grinding campaign.
---

# Grinding UI

Improve Leaf through repeated comparisons with plain HTML: run an experiment,
make a change and test whether it helps. Continue the loop within the user’s
requested scope or duration.

Load `/developing-leaf` for repository work. [`evals/README.md`](../../../evals/README.md)
owns individual eval execution, comparison and reporting mechanics.
[`notes/agent-usability-evals.md`](../../../notes/agent-usability-evals.md) contains
previous runs and findings.

## Run the improvement loop

- **Run a Leaf/plain HTML comparison.** Choose the task and inputs from what
  previous experiments suggest is worth learning next. Reuse saved HTML pages
  while they remain a suitable control for that task; changing Leaf alone does
  not require another HTML author. Run the comparison and inspect the pages and
  interaction evidence to choose a consequential weakness in Leaf, including its
  authoring instructions.
- **Make the change.** Trace that weakness to its owner and implement a candidate
  repair in Leaf. Keep the starting version available for comparison.
- **Test the candidate.** Compare base and candidate on the affected task. For
  runtime changes, test saved Leaf sources against both runtimes. For authoring
  guidance, use fresh Leaf authors to test what the instructions produce. Compare
  the result with the HTML control too, and vary inputs or tasks to test its reach.
- **Keep, revise or reject it.** Weigh the rendered result, working interactions
  and authoring effort. Retain useful improvements; revise or undo candidates
  whose costs or regressions outweigh their benefit. A judge's score informs
  that decision alongside the evidence.
- **Use the result to choose the next experiment and run it.** A rejected
  candidate can suggest another repair; a successful one can expose the next
  weakness. Feed those observations into the next Leaf/plain HTML comparison.

If the user gives no run limit, complete an initial improvement cycle, decide
whether to retain the change, and report the result. For longer runs, keep the user
current through a report while continuing. At handoff, leave the retained changes
and their comparison evidence clear, including unsuccessful experiments.

## What the comparisons should reveal

Leaf's value includes comments, revisions and a retained decision record, so a
comparison of initial screenshots misses part of the product. Authoring effort
also matters: a good page that takes much more work may still favor plain HTML.

The intended use is primarily fullscreen desktop. Most comparisons should reflect
that use, with variation in tasks, inputs and screen sizes to expose overfitting.
A stable comparison core makes progress interpretable. Alongside it, explore
saved pages and vary tasks, inputs, interaction sequences, models or viewports
to find weaknesses the core misses. Let observations steer that exploration:
follow a promising failure into nearby variations to understand it, then test
the repair on a dissimilar case. Broaden the search when repeated runs stop
teaching anything useful; concentrate when a consequential weakness emerges.

Generate new HTML controls when the task or authoring conditions change enough
that saved pages no longer answer the question, or when broader sampling would
test dependence on a particular author's output. Resizing or exploring a saved
page needs no new author. Keep discovery findings separate from the fixed
comparisons: an adaptive search finds useful failures, not a defect rate.

## Models and variation

Sol through Codex is the default given its abundant budget. Occasional Astra and
Opus checks bring independent judgment. A different judge tests the assessment
of existing pages; fresh Opus authors through Claude Code test whether guidance
transfers. A failure specific to a harness makes that harness the useful focus.
`MODELS` in `dev/leaf_dev/arms.py` owns the model pins; the README's independent
live-audit recipe covers overrides.

The `desktop` viewport is the routine anchor, `short` exposes constrained desktop
behavior, and occasional `phone` runs check functional access.
`evals/workflows/eval.yaml` owns the dimensions. Resizing a saved page tests its
layout; fresh authoring at another size also tests how authors respond to it.

Configuration, document and queue tasks exercise different uses of Leaf. Varying
evidence, decisions and revision requests within them helps distinguish a general
improvement from a layout tuned to one prompt. Quick handoffs and multi-turn
records also have different demands.

## Depth and breadth

Run one experiment at a time by default, so its result informs the next choice.
For breadth, subagents can run independent comparison-and-improvement loops on
different tasks or competing hypotheses. Give each a distinct question and
isolated candidate changes; bring their evidence back into the next choice of
focus and check retained changes together. Sequential work is more useful when
experiments depend on one another or change the same underlying guidance.

Abundant model tokens do not remove the shared machine's browser bottleneck.
Size concurrent authoring and browser work to the host's capacity.

## Reading the evidence

Pair judgments compare content and exclude Leaf's panel and threads. Those need
separate observation. Decision controls are visible in the predecision phase;
the final record shows their outcome. Saved samples retain their original
runtime.

The two presentation orders judge the same authored pages; they are not two
independent samples. Order splits and disagreement with an independent judge
have occurred in previous runs. Saved-page exploration with `eval-discover` can
find additional weaknesses without another authoring run.
