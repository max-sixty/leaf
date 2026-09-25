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

### main at `ad7504125`, 24 September 2026

Three rounds, 18 runs per arm across the three subjects and both phases (batch
`main-clean`). No run loaded auto-memory, and no plain-arm page used a vocabulary term.

**Every page passes.** The independent `version check --render` passed all 36 pages,
and the median agent saw no failing check along the way. The render checks read every
box whatever produced it, so they don't separate the arms.

**The vocabulary saves authoring work, mostly on the queue.** Phase-one totals across
nine runs per arm:

| arm | turns | cost | minutes | page CSS lines | page JS lines |
|---|---|---|---|---|---|
| leaf | 114 | $6.60 | 18 | 92 | 0 |
| plain | 161 | $7.64 | 24 | 326 | 165 |

The document and the dashboard cost about the same in both arms; the plain arm writes
two to four times the CSS. The queue is where the arms diverge: the leaf arm's median
run took 11 turns and 6 CSS lines with `lf-workspace` and `lf-pane`, while the plain
arm's took 25 turns, 45 CSS lines and 69 lines of JavaScript to select a ticket.

**The reviewer prefers the plain pages.** Each pair was judged twice, once with each
arm as page A; the judge picked the same page in 16 of 18 pairs.

| subject | phase | overall leaf/plain | layout only leaf/plain | 1440px | 900px | 390px |
|---|---|---|---|---|---|---|
| dashboard | 1 | 3/3 | 3/3 | 5/1 | 0/4 | 0/5 |
| dashboard | 2 | 1/5 | 1/5 | 2/3 | 0/5 | 0/5 |
| document | 1 | 2/4 | 2/4 | 2/4 | 2/4 | 2/3 |
| document | 2 | 0/6 | 0/6 | 0/6 | 0/6 | 2/4 |
| queue | 1 | 0/6 | 0/6 | 1/5 | 0/6 | 0/5 |
| queue | 2 | 0/6 | 0/6 | 0/6 | 0/6 | 0/4 |

Ties make up the rest of each width's six judgments. The leaf arm's one clear strength
is the dashboard at laptop width.

**The standing preference lands in the plain arm and mostly not in the leaf arm.** The
reviewer judged the 900px preference met in 18 of 18 plain judgments and 5 of 18 leaf
judgments (dashboard 3/6, document 0/6, queue 2/6). Plain agents added 76 lines of CSS
for it, setting their own breakpoints; leaf agents added 5, changing `lf-grid` ratios
and trusting the grid to hold.

What the reviewer's defects come down to, each checked against the screenshots or the
code:

- **The grid stacks at 900px.** `lf-grid` stacks a template once its narrowest track
  would fall under 16rem, and it rounds the template's ratio up to a whole number
  (`lf-grid.js:38`), so `3fr 2fr` stacks like `2fr 1fr`, below a 51rem grid. A 900px
  window leaves `main` about 769px beside the rail, so a body-and-rail split and a
  queue beside its detail both stack there. An author can't move that threshold short
  of switching to `1fr 1fr`. The #45 branch changes the rounding. `1fr 2fr` still
  stacks below 51rem after that change, because 16rem × 3 plus the gaps is that width.
- **A workspace hides its own ending.** On a laptop each pane scrolls separately, and
  the decision under a ticket sits below the pane's fold. Once the grid stacks at 900px,
  the queue pane is a short box showing two or three tickets. Two of the three plain
  queues scroll as one page with a sticky queue, and the reviewer preferred the plain
  queue at every width.
- **A wide grid in a document breaks the text's edge.** A grid in a document stands at
  the wide width, so its right edge runs well past the prose. The reviewer called that
  misaligned in 6 of its 12 document judgments.
- **Two of three leaf queues added an `lf-tabs` strip** of ticket numbers beside the
  queue, which the reviewer flagged as a second list of the same tickets.

### #45 at `54b323246`, 25 September 2026

The same three rounds against the #45 branch (batch `pr45`): one page kind, `lf-grid`
templates stacking at a 14rem narrowest track computed from the grid's real width, and
a workspace-only page taking the wide frame without `data-width`. Both arms are built
from that ref; the plain guide names `--wide-page-max`, which #45 renamed from
`--sheet-max`. All 36 pages pass the gate; no run loaded memory; no plain page used a
vocabulary term.

| arm | turns | cost | minutes | page CSS lines | page JS lines |
|---|---|---|---|---|---|
| leaf | 143 | $7.16 | 18 | 46 | 63 |
| plain | 132 | $6.88 | 19 | 202 | 169 |

One leaf queue wrote its own selection script (63 lines); the other two used none.

| subject | phase | overall leaf/plain | layout only leaf/plain | 1440px | 900px | 390px |
|---|---|---|---|---|---|---|
| dashboard | 1 | 4/2 | 3/2 | 5/0 | 0/6 | 1/1 |
| dashboard | 2 | 4/2 | 4/2 | 4/2 | 4/0 | 0/6 |
| document | 1 | 0/6 | 0/6 | 0/6 | 0/6 | 0/6 |
| document | 2 | 0/6 | 0/6 | 0/5 | 0/5 | 0/6 |
| queue | 1 | 1/5 | 0/6 | 2/3 | 0/6 | 1/2 |
| queue | 2 | 3/3 | 3/3 | 4/1 | 2/2 | 0/2 |

The judge picked the same page in 12 of 18 swapped pairs; all six disagreements are
dashboard or queue pairs, so those subjects are close. The document is not.

**The 900px preference now lands in both arms**: met in 16 of 18 judgments each, against
5 of 18 for the leaf arm on main. Leaf agents met it without adding CSS, by choosing a
ratio the fixed grid keeps side by side (`1fr 2fr` holds at a 769px main); plain agents
added 82 lines. One phase-one leaf queue used `1fr 2.4fr`, which stacks below about
785px, so it stacked at 900px until the revision changed it.

**The document still goes to the plain arm, 12 of 12.** The leaf documents' defects:

- the headline tiles and wide figures break past the prose's right edge at 1440px and
  start left of it at 900px (the grid in a document stands at the wide width);
- the body-and-rail grid keeps authored order, so on a phone the summary and the asks
  come after the whole body, while plain pages put them first;
- the rail is not sticky, so past its end the right column is empty; all three plain
  documents made their rail sticky;
- composition choices outside the vocabulary, such as a sideways-scrolling plan strip
  that cuts off steps, also counted against two leaf documents.

### What the two runs say

The render gate passes every page in both arms, so it can't tell which arrangement
serves the reader. The vocabulary cuts page CSS (92 lines against 326 on main, 46
against 202 on #45) and, for the queue, usually removes the selection script. It cut
turns and cost on main (114 turns against 161) but not on #45 (143 against 132).
Whether its pages read better depends on the subject. After #45 fixed the grid's
stacking width, the leaf arm wins the dashboard in 8 of 12 judgments. The queue goes to
the plain arm 8 to 4, but the revised queues split 3 to 3. The leaf arm loses the
document in every judgment on both refs, to wide blocks that break the text's edge and
a rail that neither sticks nor leads on a phone.

Limits: one judge model reading static screenshots; three runs per cell; a pane's inner
scroll isn't exercised (the reviewer is told it scrolls); Opus 5.5 authors only.
