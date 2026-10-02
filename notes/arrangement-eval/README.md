# Arrangement comparison evidence

The current Promptfoo scenario is documented in [evals/arrangement](../../evals/arrangement/README.md).
This directory retains earlier research results. The comparison covers Leaf's Layout
vocabulary and a standing-preference revision; the complete authoring and feedback
comparison remains [#19](../workspace-followups.md#item-19).

## Retained results

The committed evidence includes per-run scores, summary tables and blinded verdicts:

- [r2-main-7ea3](results/r2-main-7ea3.md), with
  [scores](results/r2-main-7ea3.json) and [reviews](results/r2-main-7ea3-reviews.json).
  Phase 2 ran under the user's home and could read or change standing instructions,
  so those results do not isolate the arm's instructions.
- [r3-main-0feb](results/r3-main-0feb.md), with
  [scores](results/r3-main-0feb.json) and [reviews](results/r3-main-0feb-reviews.json).
  This run used an isolated home.

These runs compare particular revisions and subjects. They do not establish the
advantage of Leaf's whole feedback loop. Product findings belong in
[TODO.md](../../TODO.md); the judge's historical defect lists are evidence for a new
reproduction, not an inventory of defects in the current runtime.
