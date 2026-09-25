# Arrangement eval harness

Does Leaf's arrangement vocabulary make an agent's pages better, or should the agent
lay a page out in its own HTML and CSS? This harness answers that with paired authoring
runs. It is the first slice of #19 in `notes/workspace-followups.md`, built from the
harness shape in `notes/agent-usability-evals.md`.

This note is the harness, not its results. A run's findings go to whoever acts on them:
the pull request or page that reports the run, and a follow-up for each defect in the
backlog (#19 in `notes/workspace-followups.md` lists the first run's).

## State of the harness

It is early: one run on two refs, and it needs work. A session that runs it improves
it in the same change, fixing what broke and adding what the run showed it lacked, and
updates this section. What the first run left:

- `plain_arm.py` edits the authoring guide at fixed text anchors, so each rewrite of
  the guide breaks the plain arm until its anchors are rewritten, as #1171's did.
  Deriving the plain arm from the guide's structure, or keeping the arrangement
  guidance in one section it can drop whole, would end that.
- The judge reads static screenshots. It cannot see a pane scroll, a rail stick, or
  any interaction, and it reads a pane's first screen as the whole pane.
- One judge model and three pairs per cell. A batch costs about $50 and 1.5 hours.
- The plain arm can still read the vocabulary in `references/packages.md` and the
  optional packages' guidance.
- Results live only in `.tmp/arrangement-eval/`, which leaves with the worktree.
  `summarize` prints tables; nothing writes a result a later run can compare against.

## Arms

Both arms are the same Leaf payload, extracted from one git ref by `harness.py arms`:
the same widgets, theme, runtime, render checks, skill and references. They differ in
how a page is arranged.

- **leaf**: the payload as shipped. The agent has `lf-grid`, `lf-workspace` and
  `lf-pane`, `data-width` on blocks and `main`, the layout idioms (`section.panel`,
  `aside.sidebar`, `aside.sidenote`), and the authoring guide's "Composing a page".
- **plain**: `plain_arm.py` removes those three elements from the registry, the three
  idioms from `$idioms`, `data-width` and every sentence naming any of them from the
  references, registry descriptions and `version check` advice, and replaces
  "Composing a page" and "The rail and the margin" with guidance to lay the page out in page CSS using the theme's
  published sizes (`--col`, `--wide`, `--wide-page-max`, `--rail`, `--lf-banner-h`,
  spacing and colour tokens). The theme's CSS for the vocabulary is still present;
  an agent that reads `theme.css` can find `data-width` there, and the scorer reports
  any page that uses it.

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
bypass permissions) from a scratch cwd with project-only settings, so neither the user's
`CLAUDE.md` nor the installed Leaf plugin loads. The prompt points it at the arm's
`SKILL.md` and sets `$LEAF` to the arm's launcher; the run's own `XDG_STATE_HOME`
keeps its pages and claims off this machine's. It asks for a finished record: write
the page, pass `version check --render`, stamp it, no server.

Then, resuming the same session, it delivers a standing preference: the user reads
pages in a window about 900px wide and wants the summary, status, contents or queue
kept beside the main content at that width. The agent revises and re-checks.

## Scoring

- `score`: per run and phase, the agent's turns, cost and time; how many times it
  ran `version check` and `--render`, and how many reported a failure; page writes; CSS
  and JavaScript lines; which arrangement terms the page used; and an independent
  `version check --render` of the phase's page with the arm's launcher.
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
arms. Count a run only when its trace's `is_error` is false. The docstring of
`harness.py` holds the design contract: the layout on disk, how each child is isolated,
and how the review is blinded.
