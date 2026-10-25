---
name: grinding-ui
description: Runs iterative improvements to Leaf UI and authoring instructions through experiments and comparisons with plain HTML. Use to start or resume a grinding campaign.
---

# Grinding UI

Improve Leaf through repeated comparisons with plain HTML, within the user's requested
scope or duration. Load `/developing-leaf` for repository work.
[`evals/README.md`](../../../evals/README.md) owns running, pairing and reporting
evals, and [`notes/agent-usability-evals.md`](../../../notes/agent-usability-evals.md)
holds previous runs and findings.

## Run the improvement loop

- **Compare.** Choose the task and inputs from what previous experiments suggest is
  worth learning next, and pick a consequential weakness in Leaf or its authoring
  instructions from the pages and interaction evidence. Saved HTML pages stay the
  control while they still answer the question; changing Leaf alone needs no new HTML
  author.
- **Change.** Trace the weakness to its owner and implement a candidate repair, keeping
  the starting version for comparison.
- **Test.** Compare base and candidate on the affected task: saved Leaf sources against
  both runtimes for a runtime change, fresh Leaf authors for authoring guidance. Compare
  with the HTML control too, and vary inputs or tasks to test the repair's reach.
- **Decide.** Keep, revise or undo the candidate by its rendered result, working
  interactions and authoring effort, with a judge's score as one input.
- **Continue** from the result: a rejected candidate can suggest another repair, and a
  successful one can expose the next weakness.

With no run limit, complete one cycle and report. At handoff, make the retained changes
and their comparison evidence clear, including unsuccessful experiments.

## What the comparisons should reveal

Leaf's value includes comments, revisions and a retained decision record, so initial
screenshots miss part of it, and a good page that takes much more authoring work may
still favor plain HTML. Most comparisons reflect fullscreen desktop use, the intended
one, around a stable core that makes progress interpretable. Beside the core, vary
tasks, inputs, interaction sequences, models and viewports to find weaknesses it
misses, and test each repair on a dissimilar case. Adaptive search finds failures, not
a defect rate, so report it apart from the fixed comparisons.

`MODELS` in `dev/leaf_dev/arms.py` owns the default models; occasional authors or
judges on another model test whether guidance and assessments transfer, and a failure
specific to one harness makes that harness the focus. `evals/workflows/eval.yaml` owns
the viewports: `desktop` is the routine anchor, `short` constrained desktop, and an
occasional `phone` run checks functional access.

## Depth and breadth

Run one experiment at a time by default, so each result informs the next. For breadth,
subagents can run independent loops on different tasks or competing hypotheses, each
with isolated candidate changes; check retained changes together. Size concurrent
authoring and browser work to the shared machine.

## Reading the evidence

Pair judgments compare content and exclude Leaf's panel and threads, which need their
own observation. The two presentation orders judge the same authored pages, so they
are not independent samples. `leaf-dev eval-discover` explores saved pages for further
weaknesses without another authoring run.
