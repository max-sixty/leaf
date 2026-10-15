# Agent usability evals

What earlier eval runs found about agents authoring, reading and revising Leaf pages,
and what remains unmeasured. The runs used harnesses the catalog has since absorbed
(`evals/README.md`); their scenarios survive as the `usability_eval` and
`arrangement_eval` executors. The per-run results were under
`notes/usability-eval/results/` and `notes/arrangement-eval/results/` until this
note was condensed; `git log --` on those paths finds them.

## Current observations

No run so far calls for a new page-reading interface. Every miss was an instruction
miss or missing information in a declaration, and agents never wrote to the wrong
place or lost a user's state. These runs establish behavior on particular revisions
with few samples.

### First baseline, 2026-09-27

At 387dfed45 with Opus 5.5, three scored runs per case after one pilot that fixed each
fixture and scorer; $5.85 scored. Every check passed:

| Case | Checks | Result |
| --- | --- | --- |
| `cold-report` | skill loaded, page valid, checked, unstamped, no Ask, no sign-off | 3/3 each |
| `cold-decision` | one Ask with one single-choice group of three options, gesture named | 3/3 each |
| `near-miss` | skill not loaded, no page | 3/3 |
| `reading` | seven questions, one per surface | 21/21 |
| `resume` | date, approach and next step; batch edit in place; pick kept; thread answered; v3 stamped | 3/3 each |

- Reading runs answered from `index.html`, `events.jsonl` and `data/*.json` without
  loading the skill, and read a pick the user made, replaced, then undid.
- Asked which tab the user is looking at, agents said the page files don't record it.
  Only a browser observation could supply that, and no task needed one.
- In `resume`, 2 of 9 runs took a loose "go ahead" as consent to publish a rejected
  save's date change, and said so.
- A resumed page's pending events stay unacknowledged until `leaf wait` delivers
  them, even after the agent has answered each one.

### Second slice, 2026-09-27

At 64186bcb9, three runs each; $5.71 scored. In the live cases the harness played the
user through the served page.

| Case | What the user does | Checks |
| --- | --- | --- |
| `handoff` | asks for a drafted page to be handed over, asks for an edit, then asks a question | 54/54 |
| `mixed` | sends a comment, a pick, a `shorten` reaction, a card move and its undo, and a page error, in one delivery | 41/42 |
| `elided` | asks a question whose premise is in the part of a long thread the delivery leaves out | 27/27 |
| `package` | asks for a widget only the page's own package supplies, without naming it | 22/24 |
| `shared-source` | asks about, then updates, one of two widgets whose shared data source also holds a look-alike record | 21/24 |

- The live loop ran as the references describe: every round arrived through the
  prompt hook, every turn re-armed the wait and ended `waiting` with the URL, and
  edit requests were claimed on their thread before the reply.
- The `mixed` miss: one run claimed all the batch's work page-wide rather than the
  comment on its thread, so the comment read "Picked up" until the reply landed.
- `shared-source` and `package` agents read the widget's renderer to confirm what
  the registry entry left unsaid: `lf-worktree`'s description says only "the
  matching record", and the fixture's entry doesn't say what the widget draws.
- `elided` did not test recovery: every agent read the closed thread before serving
  the page. The fixture now admits that history only after handover.

An A/B of the two obvious fixes (a per-move claim rule in `conversation-loop.md`; a
sharper `lf-worktree` description) changed neither result, and both were reverted.

### Inspection comparison, 2026-09-27

`page state` carrying the page's construction tree tied, on correctness, a candidate
that read the active HTML beside compact state (`resume`, `constructs`, `board`,
three runs per arm, all checks passed, $12.27), while the tree made up most of the
output:
24,422 against 4,755 bytes on the reading fixture and 122,280 against 10,360 on
`command-hub`. The page-level tree was removed; a thread keeps its construction
reading, since its frozen markup has no separate HTML file.

### Layout vocabulary, 2026-09-29

Document, dashboard and queue pages were authored and then revised for a 900px
window, with Leaf's Layout vocabulary and without it, three runs per arm, and
compared pairwise by a blinded Claude judge on screenshots. Every page passed the
render check in both arms. With the vocabulary, agents wrote about half the CSS
(62 against 135 lines over the first versions, 92 against 219 after the revision).
On the first versions the judge preferred the queue with the vocabulary in all three
pairs and the document without it in all three; on the dashboard the version without
it won one pair and the judge split on the other two. After the
revision the vocabulary won 3, 2 and 1 of the three queue, dashboard and document
pairs, and every revision met the width preference.
Its reasons kept naming tiny text at 900px and on a phone, which the render check
now reads at every swept width, and an Ask whose premise and controls fall below the
first screen (TODO.md, "Measure how often agents produce bad pages").

### Authoring against plain HTML, 2026-10-12

The same request, width revision and user comment, built once with Leaf and once
with ordinary HTML/CSS/JS and no Leaf payload. Nine pairs at a2cf7a001 with Opus 5.5
on Claude Code: three each of `document` (a review the team decides from), `queue`
(eight escalations, list beside detail) and `configuration` (six alert thresholds to
tune). The first configuration pair ran at 51ef3d615, whose prompts are the same.
Each sample authors the page, revises it for the 900px lasting preference, then
handles a comment that adds a fact to one passage. Leaf gets the comment anchored on
the passage, or on the page whole where no candidate quote appears exactly once
(5 of 9, including every configuration, whose alert text the author's script
renders), and HTML gets it in chat naming the passage. Agent spend was about $40 at
API prices on the signed-in login, including a discarded document sample whose
comment named the wrong weekday; the Codex screenshot judge read about 7M tokens and
the pairwise judge cost $11.

Within each task, the three Leaf samples ran before the three HTML samples, so the
minutes are confounded with any drift in host load (load average 4 to 7 throughout);
tokens, cost and code are not.

The executor has since been rebuilt on the real loop, so these commands no longer
reproduce this run: Leaf runs as the installed plugin and hands the page over, the
comment is posted from a browser selection and delivered by the hook, every task
ends with a decision the user makes on the page and asks to have applied, and
`eval-pairs` is the quality score (`evals/README.md`, "Reading the results").
Runs alternate the conditions, one repeat each, swapping which goes first:

```sh
for task in document queue configuration; do
  uv run leaf-dev eval $task --harness claude-code --condition leaf --repeat 1 -j 1
  uv run leaf-dev eval $task --harness claude-code --condition html --repeat 1 -j 1
  uv run leaf-dev eval $task --harness claude-code --condition html --repeat 1 -j 1
  uv run leaf-dev eval $task --harness claude-code --condition leaf --repeat 1 -j 1
done
uv run leaf-dev eval-pairs .tmp/eval/<run>...
uv run leaf-dev eval-report "$(mktemp -d)/report" .tmp/eval/<run>...
```

Every sample completed every phase and passed its render gate; every page's files
carried the comment's fact, and every answer named it, on the comment's thread in Leaf and in
chat in HTML; every Leaf document and queue reader read the seeded choice back
correctly. The configuration seeds no choice, so whether Leaf reads its settings back
went unmeasured. The catalog checks the comment's fact in the page's text; only
`eval-pairs` judges where a reader finds it.

Means per sample over the three phases, with the last version's authored CSS and
script lines:

| Task | Condition | Minutes | Cost | Turns | Input tokens | CSS | Script | Page writes | Renders |
|---|---|---|---|---|---|---|---|---|---|
| document | Leaf | 7.1 | $2.40 | 48 | 3.7M | 14 | 0 | 7.0 | 6.7 |
| document | HTML | 3.9 | $0.88 | 30 | 0.8M | 99 | 69 | 7.7 | 7.3 |
| queue | Leaf | 6.0 | $2.03 | 45 | 3.2M | 5 | 0 | 6.3 | 7.7 |
| queue | HTML | 4.6 | $1.01 | 27 | 1.0M | 121 | 240 | 9.0 | 5.3 |
| configuration | Leaf | 13.5 | $3.72 | 78 | 7.3M | 44 | 132 | 12.3 | 13.7 |
| configuration | HTML | 5.8 | $1.31 | 31 | 1.2M | 113 | 217 | 9.7 | 5.3 |

Page writes and renders count tool calls that write the page and that run a check or
a browser on it; repair iterations show as writes beyond the first, and the two
conditions repaired about equally often.

- **Leaf authors wrote less code and spent more.** Their CSS was a seventh of HTML's
  on the document, a twenty-fifth on the queue and two fifths on the configuration,
  with no script for the document and queue and three fifths of HTML's for the
  configuration's playground. They cost 2.0–2.8 times as much, over 1.6–2.5 times as
  many turns, each carrying a larger context: the skill and its references (30–100
  KB read in the first phase) stay in every later turn. Configuration authors also
  read the playground's own source (35–46 KB of widget script and theme) to learn
  it. The page check's screenshot review (11 to 25 screenshots) mostly ran in a
  subagent, and added little to the author's context.
- **Answering a comment the agent found on the page took most of the comment phase.**
  Six of the nine Leaf agents ran `leaf thread reply`. Five were refused because
  the thread owed a response, with a refusal that names
  `leaf response reply <answer.ref>` without saying where the reference comes
  from; one passed a flag it lacks, and three read only its help. All nine then took the page, with `leaf page claim` or
  `leaf server start`, and ran a timed `leaf wait` to obtain a delivery. Finding
  the comment and the route took 11 to 15 of each phase's 13 to 22 tool calls, and
  the phase cost $0.56–1.08 against $0.10–0.46 in HTML. Every phase's prompt says
  not to wait for input, so the agents reached `leaf wait` only after other routes
  failed, and a live session's delivery carries the reference; what remains is that
  the refusal names a reference no command it mentions supplies.
- **Judged quality is close, and each task's composition decided it.** The Codex
  screenshot judge failed almost every version in both conditions (Leaf 2 of 27,
  HTML 4 of 27). Its reasons were mostly evidence it may not open, such as a
  collapsed disclosure or an unselected queue item, and phone clipping in HTML; the
  Leaf configurations also left out request facts (24/7 cover, the incidents a 5%
  threshold misses). `eval-pairs`, judging each pair's final versions in both
  orders, preferred HTML on all three configurations by a clear margin in each
  order, Leaf on two of three documents and HTML on one of three queues, slightly;
  it split on the other three pairs, picking the same position both times. The
  pairwise judge runs the authors' model, Opus 5.5, and Leaf's viewer chrome in the
  screenshots shows it which page is Leaf's.
  - Documents: on the two documents Leaf won, it won on decisions in both orders,
    since it put both decisions on the page as asks where HTML offered a reply
    to copy. HTML's sticky contents ran out of the short 900px window on all three;
    both conditions' comparison tables lost a column at 390px.
  - Configurations: every Leaf author used `lf-playground`, whose control panel sits
    apart from each alert's 30-day evidence. Every HTML author put each alert's
    choices, evidence and outcome in one card, and HTML won evidence, decisions and
    the comment in every order.
  - Queues: HTML won on decisions in every order, with progress through the eight,
    previous and next, and a decision record; Leaf queues became a sideways strip on
    a phone. One Leaf author answered the comment by marking ESC-4110's new route
    outcome as chosen, labelled "your call". Neither condition showed
    the comment's change in the open ticket, since the commented ticket was not the
    one open.

What this points #20 and the instructions at, strongest first:

- Configuration wants each item's controls beside its evidence. Test a composition
  suggestion for per-item controls against the playground's single panel, and
  check that a configuration keeps the request's facts.
- A queue worked through in one sitting wants progress and a way to the next
  undecided item; test that as a composition suggestion.
- The skill and references an author reads stay in every later turn's context.
  Measure how much of the cost they account for, and what a first page needs to
  read, before trimming them.
- An owed input without a delivery has no stated route to an answer. The refusal
  from `leaf thread reply` could say where `<answer.ref>` comes from (the delivery
  `leaf wait` prints, after `leaf page claim` on a page another session held).
- On-page decisions are where Leaf's documents won; keep them in whatever #20
  changes.

## Remaining evaluation gaps

- Recovering a long thread's middle after the agent has lost it. `elided` now
  requires the premise to reach the agent after the question, but has not been run
  enough to establish reliability.
- Reading cost with large data manifests, and conflicts beyond the rejected save in
  `resume`.
- Revision after implementation lands: current conclusions and remaining work,
  preserved decisions, and user-owned text.
- Questions that need the user's selected tab or visible content, which needs a
  browser observation.

When a real failure supplies a case, state its expected answer
and edit owner before running it, and classify a miss as missing information,
inaccessible information, or information misread.
