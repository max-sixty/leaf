# Arrangement comparison

Does Leaf's arrangement vocabulary make an agent's pages better, or should the agent
lay a page out in its own HTML and CSS? This eval answers that with paired authoring
runs. It is the first slice of #19 in `notes/workspace-followups.md`, run from the
harness shape in `notes/agent-usability-evals.md`.

## Arms

Both arms are the same Leaf payload, extracted from one git ref by `make_arms.sh`:
the same widgets, theme, runtime, render checks, skill and references. They differ in
how a page is arranged.

- **leaf**: the payload as shipped. The agent has `lf-grid`, `lf-workspace` and
  `lf-pane`, `data-width` on blocks and `main`, the layout idioms (`section.panel`,
  `aside.sidebar`, `aside.sidenote`), and the authoring guide's "Composing a page".
- **plain**: `plain_arm.py` removes those three elements from the registry, the three
  idioms from `$idioms`, `data-width` and every sentence naming any of them from the
  references, registry descriptions and `version check` advice, and replaces
  "Composing a page" with guidance to lay the page out in page CSS using the theme's
  published sizes (`--col`, `--wide`, `--sheet-max`, `--rail`, `--lf-banner-h`,
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

`run.sh` starts a fresh `claude -p` (Opus 5.5, Bash/Read/Write/Edit/Glob/Grep, bypass
permissions) from a scratch cwd with project-only settings, so neither the user's
`CLAUDE.md` nor the installed Leaf plugin loads. The prompt points it at the arm's
`SKILL.md` and sets `$LEAF` to the arm's launcher; the run's own `XDG_STATE_HOME`
keeps its pages and claims off this machine's. It asks for a finished record: write
the page, pass `version check --render`, stamp it, no server.

Then, resuming the same session, it delivers a standing preference: the user reads
pages in a window about 900px wide and wants the summary, status, contents or queue
kept beside the main content at that width. The agent revises and re-checks.

## Scoring

- `score.py`: per run and phase, the agent's turns, cost and time; how many times it
  ran `version check` and `--render`, and how many exited non-zero; page writes; CSS
  and JavaScript lines; which arrangement terms the page used; and an independent
  `version check --render` of the phase's page with the arm's launcher.
- `shoot.py`: screenshots at 1440×900, 900×900 and 390×844, screen by screen down
  the page, for each phase.
- `review.py`: a fresh `claude -p` that sees only the request and both pages'
  screenshots, never the HTML, arm names or guidance, picks the page the user would
  rather have, per width and overall, and says whether each honours the preference.
  Which arm is A is fixed per pair by a hash of the pair's name.

## Running

```sh
d=.tmp/arrangement-eval
notes/arrangement-eval/make_arms.sh <ref> $d/arms-<name>
notes/arrangement-eval/batch.sh $d/arms-<name> <batch> <rounds>
uv run notes/arrangement-eval/score.py $d/runs/<batch>
uv run notes/arrangement-eval/shoot.py $d/runs/<batch>
python3 notes/arrangement-eval/review.py $d/runs/<batch>
```

`score.py` before `shoot.py`: it writes the phase-one page copy that `shoot.py` serves.
A round runs all six subject × arm pairs at once, so machine load lands on both arms.
Count a run only when its trace's `is_error` is false.

## Results

Pending.
