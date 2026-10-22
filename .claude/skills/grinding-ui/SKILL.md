---
name: grinding-ui
description: Runs iterative improvements to Leaf UI and authoring instructions through experiments and comparisons with plain HTML. Use to start or resume a grinding campaign.
---

# Grinding UI

Improve Leaf through repeated comparisons with plain HTML: run an experiment, make a
change and test whether it helps, continuing within the user's requested scope or
duration.

Load `/developing-leaf` for repository work. [`evals/README.md`](../../../evals/README.md)
owns running, comparing and reporting evals, and
[`notes/agent-usability-evals.md`](../../../notes/agent-usability-evals.md) holds
previous runs and findings.

## Run the improvement loop

- **Run a Leaf/plain HTML comparison.** Choose the task and inputs from what previous
  experiments suggest is worth learning next. Reuse saved HTML pages while they remain
  a suitable control for that task; changing Leaf alone needs no new HTML author.
  Inspect the pages and interaction evidence to choose a consequential weakness in
  Leaf, including its authoring instructions.
- **Make the change.** Trace that weakness to its owner and implement a candidate
  repair, keeping the starting version available for comparison.
- **Test the candidate.** Compare base and candidate on the affected task: saved Leaf
  sources against both runtimes for a runtime change, fresh Leaf authors for authoring
  guidance. Compare the result with the HTML control too, and vary inputs or tasks to
  test its reach.
- **Keep, revise or reject it.** Weigh the rendered result, working interactions and
  authoring effort, with a judge's score as one input. Undo or revise a candidate whose
  costs or regressions outweigh its benefit.
- **Choose the next experiment from the result and run it.** A rejected candidate can
  suggest another repair; a successful one can expose the next weakness.

If the user gives no run limit, complete one cycle, decide whether to retain the
change, and report. For longer runs, keep the user current through a report while
continuing. At handoff, make the retained changes and their comparison evidence clear,
including unsuccessful experiments.

## What the comparisons should reveal

Leaf's value includes comments, revisions and a retained decision record, so initial
screenshots miss part of the product. Authoring effort counts too: a good page that
takes much more work may still favor plain HTML.

The intended use is primarily fullscreen desktop, so most comparisons reflect it. Keep
a stable comparison core so progress is interpretable, and alongside it explore saved
pages and vary tasks, inputs, interaction sequences, models or viewports to find
weaknesses the core misses. Follow a promising failure into nearby variations, test
the repair on a dissimilar case, broaden when runs stop teaching anything, and
concentrate when a consequential weakness emerges. Keep discovery findings separate
from the fixed comparisons: an adaptive search finds failures, not a defect rate.

Generate new HTML controls when the task or authoring conditions change enough that
saved pages no longer answer the question, or to test dependence on one author's
output. Resizing or exploring a saved page needs no new author.

## Models and variation

Sol through Codex is the default, given its budget. Occasional Astra and Opus checks
bring independent judgment: a different judge tests the assessment of existing pages,
and fresh Opus authors through Claude Code test whether guidance transfers. A failure
specific to one harness makes that harness the focus. `MODELS` in
`dev/leaf_dev/arms.py` owns the model pins, and the README's "Independent live audits"
covers overrides.

The `desktop` viewport is the routine anchor, `short` exposes constrained desktop
behavior, and occasional `phone` runs check functional access
(`evals/workflows/eval.yaml` owns the dimensions). Resizing a saved page tests its
layout; fresh authoring at another size also tests how authors respond to it.

Configuration, document and queue tasks exercise different uses of Leaf, and quick
handoffs and multi-turn records make different demands. Varying evidence, decisions
and revision requests within a task separates a general improvement from a layout
tuned to one prompt.

## Depth and breadth

Run one experiment at a time by default, so its result informs the next choice. For
breadth, subagents can run independent loops on different tasks or competing
hypotheses, each with a distinct question and isolated candidate changes; bring their
evidence back into the next choice and check retained changes together. Stay
sequential when experiments depend on one another or change the same guidance. Size
concurrent authoring and browser work to the shared machine's capacity, which abundant
model tokens don't raise.

## Reading the evidence

Pair judgments compare content and exclude Leaf's panel and threads, which need
separate observation. Decision controls are visible in the predecision phase, and the
final record shows their outcome. Saved samples keep their original runtime.

The two presentation orders judge the same authored pages, so they are not
independent samples; order splits and disagreement with an independent judge have
occurred. `eval-discover` explores saved pages for further weaknesses without another
authoring run.
