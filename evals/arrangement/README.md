# Arrangement comparison

```sh
npm ci --prefix evals
uv run leaf-dev scenario-eval arrangement document [--base REF] [--runs N]
```

Choose `document`, `dashboard`, or `queue`; their requests live in `subjects/`.
Promptfoo schedules and scores each complete comparison against the base and
candidate Leaf payloads, and keeps reports with the run's traces and captures.
The scenario uses Claude Code for authors and visual judges.

Each sample compares Leaf's arrangement vocabulary with a stripped version of
the same payload. The stripped arm removes Layout classes, `lf-pane`, width and
rail declarations, and margin idioms. It retains Leaf's widgets, theme, runtime,
render checks, and feedback mechanisms, and teaches arrangement through page CSS.
This measures vocabulary inside Leaf; it does not compare Leaf's whole product
against ordinary HTML.

A fresh author writes each arm's page, then resumes the same isolated session to
apply a standing preference for summary, status, contents or queue beside the main
content at 900px. Each phase receives an independent render check and captures at
1440×900, 900×900, and 390×844, screen by screen. Fresh judges see only the request
and neutral screenshots, once with each arm on each side. Every capture must have
a successful Read result, and each judge must return a complete comparison.

Completion, page presence, render checks, captures and judge evidence are pass/fail
assertions. Winners, ties, per-width judgments, preference assessments, cost and
authoring effort are diagnostics. A negative preference assessment remains evidence
rather than an execution failure.

The stripped-arm builder uses exact replacements and checks that vocabulary was
removed. Changed instructions can prevent construction; fix those anchors before
running models. `references/packages.md` and runtime/theme source still reveal
some arrangement implementation. Inspect the authored vocabulary diagnostics
before accepting a comparison.

The judge sees static screenshots, so it cannot establish interaction, scrolling
or sticky behavior. It may mistake a pane's first screen for its complete contents.
Phase one does not demand the 900px arrangement; phase two does. Read those
judgments separately. Side swapping detects disagreement, but the single judge
model has not been calibrated against human judgments.

[Earlier research results](../../notes/arrangement-eval/README.md) retain their
original scores and verdicts. The standing mechanism lives in
`dev/leaf_dev/arrangement_eval.py`; the stripped-arm construction lives in
`dev/leaf_dev/arrangement_plain.py`.
