# Arrangement eval harness

This harness compares Leaf's Layout vocabulary with page HTML and CSS. It covers
arrangement authoring and a standing-preference revision; the complete authoring and
feedback comparison remains [#19](../workspace-followups.md#item-19).

## Retained results

The committed evidence includes per-run scores, summary tables and blinded verdicts:

- [r2-main-7ea3](results/r2-main-7ea3.md), with
  [scores](results/r2-main-7ea3.json) and [reviews](results/r2-main-7ea3-reviews.json).
  Phase 2 ran under the user's home and could read or change standing instructions,
  so those results do not isolate the arm's guidance.
- [r3-main-0feb](results/r3-main-0feb.md), with
  [scores](results/r3-main-0feb.json) and [reviews](results/r3-main-0feb-reviews.json).
  This run used an isolated home.

These runs compare particular revisions and subjects. They do not establish the
advantage of Leaf's whole feedback loop. Product findings belong in
[TODO.md](../../TODO.md); the judge's historical defect lists are evidence for a new
reproduction, not an inventory of defects in the current runtime.

## State of the harness

Before a new batch, rebuild the arms and check their isolation:

- `plain_arm.py` replaces the guide from "Composing a page" to "Draw the subject"
  and empties `layouts.css`. Other edits match exact text in registry entries,
  references and package guidance, so changed wording can prevent arm construction.
- `check_clean` checks package guidance, registries and the Layout stylesheet.
  The plain arm can still find `lf-pane` in `references/packages.md` and Layout
  selectors in runtime or theme source. `score` reports arrangement vocabulary
  used by each authored page; inspect it before accepting the comparison.
- The judge sees static screenshots. It cannot establish scrolling, sticky behavior
  or interaction outcomes, and may mistake a pane's first screen for its contents.
- Each subject/phase has few pairs and one judge model. `review --flip` tests whether
  swapping the displayed sides changes the verdict.
- Phase 1 has no preference for a side-by-side layout at 900px; phase 2 does.
  Interpret their 900px verdicts separately.

A new run should fix a harness failure it exposes before producing scored results.
The runner's current model and isolation contract live in `harness.py` and
`dev/leaf_dev/harness.py`.

## Arms

`harness.py arms` extracts the same Leaf payload from one git ref for both arms:
widgets, theme, runtime, render checks, skill and references.

- **leaf:** the shipped Layout classes, `lf-pane`, width and rail declarations,
  margin idioms, and "Composing a page" guidance.
- **plain:** `plain_arm.py` removes the arrangement declarations and guidance it
  targets, empties the Layout stylesheet, and teaches page CSS using the theme's
  published size, spacing and color tokens. The widgets and feedback mechanisms
  remain Leaf's.

The extracted payload omits `.git`, examples, docs, notes and the README. Both arms
therefore lack the worked corpus and history. This compares arrangement choices
inside Leaf; it is not a plain-HTML-only product comparison.

## Subjects and revision

The requests in `subjects/` share content across arms:

- `document.md`: a migration review read top to bottom.
- `dashboard.md`: a rollout dashboard kept open and glanced at, with a decision.
- `queue.md`: escalations worked one at a time with the queue beside the open ticket.

Each author runs in a fresh scratch directory and isolated home. The first phase
writes a page, passes `page check --render` and stamps it, without starting a server.
The second phase resumes that session and asks for the summary, status, contents or
queue to remain beside the main content at about 900px wide. The author revises and
checks the page again.

## Scoring

`score` records turns, cost, time, page writes, validation attempts and failures,
CSS/JavaScript lines, vocabulary use and an independent render check. `shoot`
captures each phase at 1440×900, 900×900 and 390×844, screen by screen. `review`
shows the request and screenshots to a fresh judge, with neither source, arm names
nor guidance. It records preference and whether each page meets the revision request.
The pair's name determines which arm appears on each side.

## Running

```sh
uv run notes/arrangement-eval/harness.py arms <ref> <name>
uv run notes/arrangement-eval/harness.py run <name> <batch> <rounds> [subject ...]
uv run notes/arrangement-eval/harness.py score <batch>
uv run notes/arrangement-eval/harness.py shoot <batch>
uv run notes/arrangement-eval/harness.py review <batch>
uv run notes/arrangement-eval/harness.py review <batch> --flip
uv run notes/arrangement-eval/harness.py summarize <batch>
```

Arms live under `.tmp/arrangement-eval/arms-<name>/`; batches under
`.tmp/arrangement-eval/runs/<batch>/`. Each run records its arms. Arm construction
checks the text replacements and a smoke page using the plain guide's width hook.
A round runs the selected subjects in both arms concurrently. Scoring accepts a
phase only when its traces completed without error or memory writes.

Traces, pages and screenshots leave with the worktree. `results/` retains scores,
summaries and verdicts for later comparison; reproducing a judge's visual finding
requires the original page or a fresh run.
