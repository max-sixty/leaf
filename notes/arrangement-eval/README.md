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
FLIP=1 python3 notes/arrangement-eval/review.py $d/runs/<batch>
python3 notes/arrangement-eval/summarize.py $d/runs/<batch>
```

`make_arms.sh` renders a smoke page that uses the plain guide's width hook, and stops if
that ref's theme no longer passes it. `score.py` runs before `shoot.py`, because it
writes the phase-one page copy that `shoot.py` serves. `FLIP=1 review.py` repeats the
review with every pair's sides swapped, and `summarize.py` tabulates both passes.
A round runs all six subject × arm pairs at once, so machine load lands on both arms.
Count a run only when its trace's `is_error` is false.

## Results

Two batches of three rounds each: main at `ad7504125` (`main-clean`, arms built by
the harness at `5d0eeaa0a`, whose plain guide lacked the sentence on fixed chrome) and
the #45 branch at `54b323246` (`pr45`: one page kind, `lf-grid` templates stacking at
a 14rem narrowest track read from the grid's width, and the plain guide naming
`--wide-page-max`, which #45 renamed from `--sheet-max`). All 72 pages pass the
independent `version check --render`. No run loaded auto-memory, and no plain page used
a vocabulary term.

The screenshots were judged blind: under neutral file names, in a directory holding
nothing else. Each pair was judged twice, once with each arm as page A. A pair counts
for an arm only when both passes pick it; otherwise it is a split. The judge agreed
with itself on 15 of 18 pairs in each batch. In 5 of the 6 splits it picked page B both
times, so a split pair is a close one.

### Pairs won in both passes

Leaf/plain/split out of three pairs per row. Preference: of six judgments per arm, how
many said the page kept its summary, status, contents or queue beside the content at
900px.

| subject | phase | main: overall | main: preference leaf, plain | #45: overall | #45: preference leaf, plain |
|---|---|---|---|---|---|
| document | 1 | 0/2/1 | | 1/2/0 | |
| document | 2 | 0/3/0 | 0, 6 | 0/2/1 | 6, 6 |
| dashboard | 1 | 0/1/2 | | 1/1/1 | |
| dashboard | 2 | 1/2/0 | 3, 6 | 1/2/0 | 6, 6 |
| queue | 1 | 0/3/0 | | 0/3/0 | |
| queue | 2 | 0/3/0 | 4, 6 | 1/1/1 | 6, 6 |
| total | | 1/14/3 | 7, 18 | 4/11/3 | 18, 18 |

`summarize.py` prints the same tables at each width.

### Effort

Totals over nine runs per arm and phase:

| batch | arm | phase 1 turns | phase 1 cost | phase 2 turns | phase 2 cost | CSS lines | JS lines |
|---|---|---|---|---|---|---|---|
| main | leaf | 114 | $6.60 | 86 | $9.67 | 92 → 97 | 0 |
| main | plain | 161 | $7.64 | 82 | $10.40 | 326 → 402 | 165 |
| #45 | leaf | 143 | $7.16 | 137 | $11.53 | 46 → 46 | 63 |
| #45 | plain | 132 | $6.88 | 71 | $9.14 | 202 → 284 | 169 |

CSS is after phase 1 → after phase 2. By subject, the gap is in the dashboard (main:
39 lines against 150) and the queue (16 against 134, plus 165 lines of JavaScript to
select a ticket). A document takes little CSS in either arm (37 against 42 on main).
On #45 the leaf revisions took longer in every subject (dashboard 44 turns against 18,
document 55 against 42, queue 38 against 11), though they changed no CSS.

### Findings

**The render gate doesn't separate the arms.** It reads every box, whatever produced
it, and all 72 pages pass.

**On main, a reader prefers the plain pages: 14 pairs to 1.** The preference lands in
the plain arm every time and in the leaf arm in 7 of 18 judgments.

**#45 fixes the preference and narrows the gap to 11 pairs to 4.** With the grid's
stacking width fixed, the leaf arm meets the 900px preference in 18 of 18 judgments. It
does so without CSS, by choosing a ratio the grid keeps side by side at a 769px `main`
(`1fr 2fr`). In phase 1 all three #45 leaf queues chose `1fr 2.4fr`, which stacks below
about 786px, and so stacked at 900px until the revision.

**The vocabulary saves CSS and a selection script, but not turns.** The plain arm writes
three to four times the CSS on the dashboard and queue, and writes its own ticket
selection. The leaf arm used fewer turns on main (114 against 161) and more on #45 (143
against 132, and 137 against 71 for the revision).

**The defects the judge names in leaf pages.** These are keyword counts over the
judge's defect lists, 12 judgments per subject and batch; I checked the document edge
and the queue stacking against main's screenshots:

- *Document*: wide tiles and figures run past the prose's right edge (6 on main, 7 on
  #45), because a grid in a document stands at the wide width; the rail comes last on a
  phone (6, 5), because the body-and-rail grid keeps authored order; the rail isn't
  sticky (5, 4). All three #45 plain documents made their rail sticky.
- *Queue*: the ticket's decision sits below the pane's fold and the queue shows only
  part of itself (6, 7), because each pane scrolls on its own. A static screenshot shows
  only a pane's first screen, so the capture itself accounts for part of this.
  Stacking at 900px (5, 5) is the grid threshold on main and the `2.4fr` choice on #45.

### Limits

- One judge model reading static screenshots, three pairs per cell.
- Opus 5.5 authors only.
- The plain arm can still read the vocabulary in `references/packages.md` and in the
  optional packages' guidance. No plain page used it, but every plain queue agent
  searched for `lf-workspace`, which adds to that arm's turns.
- Runs before the harness at `4158aa599` shared `/tmp` across arms and could write into
  the payload. In #45 round 3 the two dashboard agents wrote the same `/tmp` file
  names about six seconds apart, close enough that one agent could have read the
  other's screenshot.
