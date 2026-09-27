# Arrangement eval harness

Does Leaf's arrangement vocabulary make an agent's pages better, or should the agent
lay a page out in its own HTML and CSS? This harness answers that with paired authoring
runs. It is the first slice of #19 in `notes/workspace-followups.md`, built from the
harness shape in `notes/agent-usability-evals.md`.

This note is the harness. A run's scores and verdicts are committed in `results/` for
the next run to compare against; its findings go to whoever acts on them: the pull
request or page that reports the run, and a follow-up for each defect in the backlog
(#19 in `notes/workspace-followups.md` lists the first run's).

## State of the harness

It is early: two runs, and it needs work. A session that runs it improves it in the
same change, fixing what broke and adding what the run showed it lacked, and updates
this section. What the runs left:

- `plain_arm.py` replaces the authoring guide's arrangement guidance whole, from
  "Composing a page" to "Draw the subject", and empties the Layouts' stylesheet, but
  still edits registry descriptions, one other reference and five packages' guidance
  at fixed text anchors, which a rewrite of those sentences breaks.
- Plain authors read far past the references: the second run's first attempt found
  the Layout classes in `layouts.css`, reached by grepping for a size the plain guide
  names, and in the monitoring package's guidance, and three of six plain pages used
  them. `check_clean` now covers every package's guidance and registry and the
  Layouts' stylesheet, and `score` reports any vocabulary a plain page uses; read that
  column before trusting a batch.
- The second run's phase-2 children ran with the user's home, read the user's
  `~/.claude/CLAUDE.md` (and earlier runs' copies of the preference in it), and six appended
  the preference there. Its phase-2 numbers were made under the user's instructions, not
  the arm's alone. Children now run under a home of their own (`scripts/eval_harness.py`).
- The judge reads static screenshots. It cannot see a pane scroll, a rail stick, or
  any interaction, and it reads a pane's first screen as the whole pane.
- One judge model and three pairs per cell. A batch's authoring costs about $37 and
  an hour, the render checks, screenshots and both review passes another hour.
- Phase 1's judge weighs a 900px window with no preference, and in the second run it
  preferred a dashboard that stacked there; phase 2's preference asks for the
  opposite. Read the 900px column of the two phases separately.
- The plain arm can still read `lf-pane` in `references/packages.md`, and the Layout
  selectors in the theme's and runtime's own sources.
- The traces, pages and screenshots live only in `.tmp/arrangement-eval/`, which
  leaves with the worktree. What a later run compares against is committed in
  `results/`: each batch's per-run scores, its summary tables, and every verdict with
  the judge's defect lists.

## Arms

Both arms are the same Leaf payload, extracted from one git ref by `harness.py arms`:
the same widgets, theme, runtime, render checks, skill and references. They differ in
how a page is arranged.

- **leaf**: the payload as shipped. The agent has the Layout classes (`layout-column`,
  `layout-wide`, `layout-sidebar`, `layout-tiles`, `layout-workspace`), `lf-pane`,
  `data-width` and `data-rail`, the margin idioms (`section.panel`, `aside.sidebar`,
  `aside.sidenote`), and the authoring guide's "Composing a page".
- **plain**: `plain_arm.py` removes `lf-pane` from the registry, the three idioms from
  `$idioms`, every sentence naming any of the vocabulary from the references and
  registry descriptions, and the `page check` advice to give `main` a Layout class.
  It replaces the guide from "Composing a page" to "Draw the subject" with guidance to
  lay the page out in page CSS, a reading column included, using the theme's published
  sizes (`--col`, `--wide`, `--wide-page-max`, `--rail`, `--lf-view-height`, spacing and
  colour tokens). The theme's CSS for the vocabulary is still present; an agent that
  reads `layouts.css` can find the classes there, and the scorer reports any page that
  uses them.

Neither arm carries `.git`, `examples/`, `docs/`, `notes/` or the README, so an author
cannot read its way to the other arm through history or the worked corpus.

## Subjects

Three requests in `subjects/`, each with the same content in both arms:

- `document.md`: a migration review read top to bottom (the control: an argument
  needs little arrangement);
- `dashboard.md`: a rollout dashboard kept open and glanced at, with a decision;
- `queue.md`: eight escalations worked through one at a time, the queue beside the
  open ticket.

## A run

`harness.py run` starts a fresh `claude -p` (Opus 5.5, Bash/Read/Write/Edit/Glob/Grep,
bypass permissions) from a scratch cwd under a home of its own, so neither the user's
`CLAUDE.md` nor the installed Leaf plugin loads, and what the child saves as a standing
preference stays in that home (`scripts/eval_harness.py`). The prompt points it at the arm's
`SKILL.md` and sets `$LEAF` to the arm's launcher; the run's own `XDG_STATE_HOME`
keeps its pages and claims off this machine's. It asks for a finished record: write
the page, pass `page check --render`, stamp it, no server.

Then, resuming the same session, it delivers a standing preference: the user reads
pages in a window about 900px wide and wants the summary, status, contents or queue
kept beside the main content at that width. The agent revises and re-checks.

## Scoring

- `score`: per run and phase, the agent's turns, cost and time; how many times it
  ran `page check` and `--render`, and how many reported a failure; page writes; CSS
  and JavaScript lines; which arrangement terms the page used; and an independent
  `page check --render` of the phase's page with the arm's launcher.
- `shoot`: screenshots at 1440×900, 900×900 and 390×844, screen by screen down
  the page, for each phase.
- `review`: a fresh `claude -p` that sees only the request and both pages'
  screenshots, never the HTML, arm names or guidance, picks the page the user would
  rather have, per width and overall, and says whether each honours the preference.
  Which arm is A is fixed per pair by a hash of the pair's name.

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

Names resolve under `.tmp/arrangement-eval/`: the arms `<name>` are `arms-<name>/`, a
batch is `runs/<batch>/`, and each run records the arms it used in its `arms` file.
`arms` stops if `plain_arm.py`'s anchors no longer match the ref's guidance, or if the
ref's theme fails a smoke page that uses the plain guide's width hook. `review --flip`
repeats the review with every pair's sides swapped, and `summarize` tabulates both
passes. A round runs all six subject × arm pairs at once, so machine load lands on both
arms. A run's phase counts only when its traces finished without error or memory,
and `score`, `review` and `summarize` apply that one test. The docstring of
`harness.py` holds the design contract: the layout on disk, how each child is isolated,
and how the review is blinded.
