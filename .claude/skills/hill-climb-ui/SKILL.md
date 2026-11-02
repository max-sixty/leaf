---
name: hill-climb-ui
description: Runs iterative improvements to Leaf UI and authoring instructions through experiments and comparisons with plain HTML. Use to start or resume a hill-climbing campaign.
---

# Hill-climb UI

Improve Leaf's runtime, packages and shipped authoring instructions within the user's
requested scope or duration. Compare with plain HTML to find and validate changes
whose benefits reach future authors. Load `/developing-leaf` for repository work.
[`evals/README.md`](../../../evals/README.md) owns running, pairing and reporting
evals, and [`notes/agent-usability-evals.md`](../../../notes/agent-usability-evals.md)
holds previous runs and findings.

## Run the improvement loop

- **Compare.** Choose a consequential weakness in the user's experience from the pages
  and interaction evidence. Use previous experiments to choose the improvement to attempt
  next and the inputs that can expose whether it works. Saved HTML pages stay the
  control while they still answer the question and still exist; changing Leaf alone
  needs no new HTML author, so author HTML once per task in a campaign. Before
  blaming Leaf for a weakness, check that the eval reproduces real use: a fixture or
  harness setting the user wouldn't impose can be the cause. Repair an evaluation
  blocker far enough to continue that product experiment, then return to it.
- **Change.** Trace the weakness to its owner and implement a candidate repair, keeping
  the starting version for comparison. A saved-page redesign can prove a useful
  behavior; carry that behavior into the maintained runtime, package or authoring
  instructions so another author can produce it.
- **Test.** Compare base and candidate on the affected task: saved Leaf sources against
  both runtimes for a runtime change, fresh Leaf authors for authoring guidance. Compare
  with the HTML control too, and vary inputs or tasks to test the repair's reach.
  Measure the phase the repair changes: authoring effort shows mostly in the first
  authoring turn, which several interleaved authors per arm can run without the user
  or judge, and layout guidance shows in the first version's height and first screen,
  which pair judges reading later phases miss. Validate a retained repair on the full
  workflow.
- **Decide.** Keep the change in Leaf, revise it or undo it by its rendered result,
  working interactions and authoring effort, with a judge's score as one input. For a
  recurring failure, compare its occurrences in author traces and use a regression
  test where code decides the outcome. Small author samples can expose recurring
  failures but rarely establish a timing difference.
- **Continue** from the result: a rejected candidate can suggest another repair, and a
  successful one can expose the next weakness.

With no run limit, complete one cycle and report. Spend a cycle on repairs and fresh
comparisons; record provenance briefly rather than re-auditing earlier runs. Choose
its scope to leave time for a change and its confirmation: saved-page probes and
focused fresh-author tasks give faster feedback on a local hypothesis, while full
multi-turn workflows test the whole exchange.

For longer runs, keep the standard eval report current. Lead with what changed in
Leaf and the matched before/after outputs supporting each retained change. Include
revised and rejected candidates, and distinguish supporting tooling and experiments
from improvements authors now receive. A current-state pass without a baseline
doesn't establish improvement. Keep earlier experiments as supporting history and
exploration distinct from scored comparisons; `evals/README.md`, "Render a report",
owns the format and commands. At handoff, review each page the user can open, including
linked demonstrations, through `/developing-leaf`, "Author or revise a page".

## What the comparisons should reveal

Leaf's value includes comments, revisions and a retained decision record, so initial
screenshots miss part of it, and a good page that takes much more authoring work may
still favor plain HTML. Most comparisons use the default desktop viewport,
around a stable core that makes progress interpretable. Beside the core, vary
tasks, inputs, interaction sequences, models and viewports to find weaknesses it
misses, and test each repair on a dissimilar case. Adaptive search finds failures, not
a defect rate, so report it apart from the fixed comparisons.

`MODELS` and `JUDGE_MODELS` in `dev/leaf_dev/arms.py` own the author and judge
model pins. Use only Astra or Opus for judging, including independent visual review;
Sol can author pages. Vary author models to test guidance transfer, and cross-check
judgments with the other allowed judge. A failure specific to one harness makes
that harness the focus. Validate a repair on both
harnesses, since their authors hit different refusals and read different references. `evals/workflows/eval.yaml` owns
the viewport presets and dimensions. Use `desktop` for routine authoring and primary
judging; occasionally add `large`, `short` or `phone` to answer a concrete layout or
access question. Extra sizes on saved pages can be explored with `eval-discover`
without expanding the original authoring task.

## Depth and breadth

Run one improvement loop at a time by default, taking a promising candidate through
implementation and a keep, revise or reject decision before expanding the search.
Independent authoring and judging can overlap. For breadth, subagents can own loops
on different tasks or competing hypotheses, each responsible for its candidate
implementation and validation. Integrate retained changes and check them together.
Size concurrent authoring and browser work to the shared machine.

## Reading the evidence

Read each author's tool timeline as well as its page: time per call, check rounds,
each refusal and the call after it, and reads of Leaf's own source or theme. Weigh
recurring authoring friction alongside the quality of the resulting page when choosing
which weakness to repair.

Pair judgments compare content and exclude Leaf's panel and threads, which need their
own observation. The pair judge carries most of the layout signal; the live judge
mostly finds content defects. The two presentation orders judge the same authored pages, so they
are not independent samples. `leaf-dev eval-discover` explores saved pages for further
weaknesses without another authoring run.
