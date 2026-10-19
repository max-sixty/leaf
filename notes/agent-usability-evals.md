# Agent usability evals

What earlier eval runs found about agents authoring, reading and revising Leaf pages,
and what remains unmeasured. The runs used harnesses the catalog has since absorbed
(`evals/README.md`); their scenarios survive as the `usability_eval` and
`arrangement_eval` executors. The per-run results were under
`notes/usability-eval/results/` and `notes/arrangement-eval/results/` until this
note was condensed; `git log --` on those paths finds them.

## Current observations

Reconciled on 2026-10-15 against main `fd68e3943`: inline ownership, scoped
validation and LeafElement are already shared. The playground now owns one immutable
working configuration. Contributors replace their named slices through `get`/`set`
handles; required views subscribe through LeafElement rather than keeping a parallel
model and read/apply callbacks. Complete restoration still preserves snapshots for late
sources. Undo follows the canonical choice identity, so two equal-valued choices
restore the earlier choice instead of leaving a later draft; pending-to-admitted
acknowledgement keeps the same attempt identity. The early drawing pass remains.
The empty all-inline rail is removed and long button labels wrap. Duplicate ownership
and export tests were dropped; existing browser journeys cover state, labels and the
short workspace, with one added contrast for a required view that fails to draw.
The historical author comparison below has not been rerun on this runtime and
establishes no broader quality result.

The initial reading and resumption probes did not call for a new page-reading
interface. Their misses were instruction misses or missing declaration information;
those agents did not write to the wrong place or lose a user's state. The later
authoring comparisons below also examine presentation and measurement faults. Each
set establishes behavior on particular revisions with few samples.

### First baseline, 2026-09-27

At 387dfed45 with Opus 5.5, three scored runs per case after one pilot that fixed each
fixture and scorer; $5.85 scored. Every check passed:

| Case            | Checks                                                                                    | Result   |
| --------------- | ----------------------------------------------------------------------------------------- | -------- |
| `cold-report`   | skill loaded, page valid, checked, unstamped, no Ask, no sign-off                         | 3/3 each |
| `cold-decision` | one Ask with one single-choice group of three options, gesture named                      | 3/3 each |
| `near-miss`     | skill not loaded, no page                                                                 | 3/3      |
| `reading`       | seven questions, one per surface                                                          | 21/21    |
| `resume`        | date, approach and next step; batch edit in place; pick kept; thread answered; v3 stamped | 3/3 each |

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

| Case            | What the user does                                                                                         | Checks |
| --------------- | ---------------------------------------------------------------------------------------------------------- | ------ |
| `handoff`       | asks for a drafted page to be handed over, asks for an edit, then asks a question                          | 54/54  |
| `mixed`         | sends a comment, a pick, a `shorten` reaction, a card move and its undo, and a page error, in one delivery | 41/42  |
| `elided`        | asks a question whose premise is in the part of a long thread the delivery leaves out                      | 27/27  |
| `package`       | asks for a widget only the page's own package supplies, without naming it                                  | 22/24  |
| `shared-source` | asks about, then updates, one of two widgets whose shared data source also holds a look-alike record       | 21/24  |

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

| Task          | Condition | Minutes | Cost  | Turns | Input tokens | CSS | Script | Page writes | Renders |
| ------------- | --------- | ------- | ----- | ----- | ------------ | --- | ------ | ----------- | ------- |
| document      | Leaf      | 7.1     | $2.40 | 48    | 3.7M         | 14  | 0      | 7.0         | 6.7     |
| document      | HTML      | 3.9     | $0.88 | 30    | 0.8M         | 99  | 69     | 7.7         | 7.3     |
| queue         | Leaf      | 6.0     | $2.03 | 45    | 3.2M         | 5   | 0      | 6.3         | 7.7     |
| queue         | HTML      | 4.6     | $1.01 | 27    | 1.0M         | 121 | 240    | 9.0         | 5.3     |
| configuration | Leaf      | 13.5    | $3.72 | 78    | 7.3M         | 44  | 132    | 12.3        | 13.7    |
| configuration | HTML      | 5.8     | $1.31 | 31    | 1.2M         | 113 | 217    | 9.7         | 5.3     |

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

### Authoring owner comparison, 2026-10-12

The configuration layout hypothesis reached a primitive constraint. Diagnostic
configuration authors received the complete skill, page-authoring, asks, and composed
playground instructions before writing. The registry required direct controls, and
the initial renderer moved all of them into a shared panel. Guidance alone could not
put an alert's controls with its evidence.

Controls now belong to their nearest playground, including inside its preview.
Direct controls form the shared panel; inline controls keep their authored positions.
Both use the same typed configuration, presets, reset, persistence, copy, submission,
and undo. The authoring change explains this capability without prescribing cards.

One cold native author per arm completed the same four-phase alert configuration
workflow on baseline `4f7cc21c1497ce6d449f6ec22d9508651fd654c3` and an initial inline
trial. Both preserved and independently read back all twelve user-selected settings.
The trial increased effort: 107 versus 71 turns, 31 versus 11 page writes, and $4.925
versus $3.450 author spend. It is a diagnostic trial, not efficiency evidence for the
final candidate. The author read private theme code and added three layout overrides.
Removing only those overrides from the same page, the owner default widened its
900px preview from 552 to 852px and alert column from 230 to 530px. At 600px, preview
and alert dimensions matched; presets now precede the preview. All values matched.

Contrasting query editing exposed stale restoration: an unrelated built-in gesture
could erase an unnotified contributor draft. Local gestures now adopt live sources;
reset and projection restore snapshots. Late contributors join a pending chosen
snapshot, and undo replaces it. Focused browser journeys cover these transitions,
copy/submission, reload, short workspaces with and without presets, and existing
structured explorers. Reproduce the central case with:

```sh
uv run pytest -q -n0 tests/browser/test_render_widgets.py::test_playground_adopts_live_sources_without_restoring_their_drafts
```

Two further native authors built independent proposals. Both began with three open
Questions and no selected defaults. Ordinary Remove/Keep clicks left one unanswered
proposal; an unrelated heading revision preserved both exact answers. Read-only
source probes had produced an invalid candidate proposal, which this native workflow
did not reproduce. Source sketches and validated working pages are distinct evidence.

The final authoring arm is `candidate-inline-v3`, payload manifest SHA256
`33225dc70ba0c1b9dff9a2edd325c4e096bf43fbc4e79736e1d90b951f963784`.
The executor is frozen at `c3060df98bc2e6b73d9a81a624d0499fc4221e44`.
One fresh cold author per arm completed the final matched workflow with that same
executor. Both passed every deterministic check and independently read back all
twelve settings. The candidate used 98 versus 103 turns, $5.209 versus $5.922,
and 5 versus 24 recorded page-write operations (the executor's approximate tool and
shell-command count). Complete intended instructions appeared before each author's
first page write; normalized initial prompts and evaluator source hashes matched.
This supports reduced effort on this pair, not a general efficiency improvement.
Independent comparison found stronger local tuning caveats in the candidate, but the
baseline better kept the final overview beside its summary at 900px. Both phone
tables fragmented alert identities. Preserved decisions do not imply a uniformly
better final page; no unqualified quality improvement is established.

A later owner repair removes unconditional `nowrap` from the shared ordinary
button face. The same candidate page's long preset labels then fit on a phone;
its 900px presets, compact banner, and twelve values remain unchanged. The original
button matrix was trimmed to one narrow-browser regression: long preset and short
Reset labels fit, and both actions work. Composition and state-preservation coverage
is retained. Delivery
arm `candidate-inline-v4` has manifest
`70efc1093fe7f2c6c1fe2e15ba82375290c8dd0326132ecfb91bd14020737b04`;
the matched author results remain tied to v3.

The separate clipboard-permission change for live samples is deferred at the user's
request; it is not required by these repairs.

The frozen executor's observation/replay code is reviewed, but its quality rubric remains preliminary:
calibration found unsupported explanations. Quality conclusions therefore use
independent inspection, with no calibrated aggregate score. Raw runs, exact
instruction receipts, payload manifests, and browser evidence remain under
`.tmp/authoring-quality/` and `.tmp/playground-browser-evidence/` in this worktree.

## Recovered Codex comparison, 2026-10-14

The interrupted rerun supplied two samples per condition for configuration, document
and queue: twelve saved author sessions using `gpt-6.1-sol`, medium reasoning, on
Codex 0.160.0. They authored against `a9358590`, after per-item playground controls
landed in [#2711](https://github.com/max-sixty/leaf/pull/2711). One configuration's
post-processing was recovered; an interrupted duplicate document was excluded.
The missing runtime was rebuilt at that commit to serve the untouched saved pages.
All Leaf pages share protocol 4 and the same recorded server fingerprint; matching
browser files and package-specific layer fingerprints establish the comparison's
runtime provenance. This is evidence about that revision, not current main.

Across all four author phases, Leaf averaged 12.5 minutes and HTML 9.0 minutes.
Configuration accounted for the largest difference: 14.4 versus 10.0 minutes.
Dollar cost is unavailable. Raw first-turn result time averaged 5.7 versus 5.2 minutes,
including one Leaf author that stopped with a model-capacity error and a saved page. Neither
completion nor a server URL establishes a usable handoff. Independent rendering ran
after all author phases, so first-usable-page time remains unmeasured (#24).

All twelve final records contained the requested decisions. Leaf sent six sets through
its event log; HTML sent four through copied text and two through typed fallback when
the browser user could not read a downloaded export. The latter proves that the author
could apply a supplied decision, not that the export completed the feedback loop.
Model-capacity failures in authors, readers and judges, and a socket failure in one
HTML render gate, must be kept separate from page-quality failures.

The paired grader had a phase mismatch: it asked how well the page supported tuning
and selection but opened only the final record, after the author had legitimately
replaced those controls. It now opens version 3 for making the decision and version 4
for reading the final record. The first corrected configuration pair split across
presentation orders, where final-only judging had preferred Leaf in both. All twelve
corrected judgments completed: Leaf won two pairs, HTML two, and two split by order.

| Task          | First pair   | Second pair  | What distinguished these pages                                                                                                                                                                                                                                         |
| ------------- | ------------ | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Configuration | Split        | HTML, slight | HTML exposed evidence directly and read better on phones; Leaf retained more baseline facts. In the split pair, Leaf separated Finance pages from the payments budget while HTML pooled them; the request leaves the budget's service-versus-rotation scope ambiguous. |
| Document      | Split        | Leaf, slight | Leaf offered separate on-page decisions and retained more evidence; HTML exposed more evidence directly and better preserved the capacity-request context in the split pair.                                                                                           |
| Queue         | Leaf, slight | HTML, slight | Leaf's compact phone view reduced scrolling; HTML's next-ticket controls and consolidated decision record made final review easier.                                                                                                                                    |

These are differences between two authored samples per task, not a general ranking of
Leaf and HTML. Phone readability, accessible evidence and review navigation mattered
more than the presence of a particular widget.

Both Leaf document authors retired the user's Wednesday capacity request to Mei
Tanaka's team after recording Redis as the store choice. Whether that assessment
still matters for the unselected alternative is ambiguous; retiring it is not itself
proof of an error. The ask-authoring reference now requires explicit accounting:
keep an unanswered request open or explain why changed circumstances make it
unnecessary. An independent decision does not silently answer or retire it.

Earlier short and replay probes passed on both arms and did not reproduce a failure.
A later base/candidate check accepting either a still-open assessment or reasoned
retirement likewise passed one sample per arm. Those checks validate the distinctions,
not a reduced error rate. The temporary case was archived with experiment evidence
rather than kept as a permanent rule that this particular assessment must stay open.

Both Leaf configuration authors encountered playground initialization failures under
the old per-publication widget runtime. That runtime was removed in
[#2742](https://github.com/max-sixty/leaf/pull/2742); current playground registration
uses the global custom-element registry. Those traces do not justify another startup
instruction or widget change. Later phases also ran Leaf's task, reply, state, check
and stamp commands; their extra calls alone do not identify work safe to remove.

Reproduce the recovered grading from this session's local result copies, which retain
references to the original saved pages:

```sh
uv run leaf-dev eval-pairs .tmp/comparison/phase-aware-runs/*
uv run leaf-dev eval-report .tmp/comparison/report .tmp/comparison/phase-aware-runs/*
```

The audit is `.tmp/comparison/audit.json`; the original saved runs are under
`/Users/maximilian/workspace/leaf.rerun-leaf-vs-html-comparison/.tmp/eval/`.
This pass repairs grading across decision and final-record phases and clarifies who
may retire an ask. Further compositions and authoring advice need current task-specific
evidence, rather than the older configuration verdict alone.

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

## Current authoring UX loop

Fresh Sol 6.1 medium comparisons now cover configuration, queue, document and dashboard.
These are individual authored samples: configuration and document preferences vary by
sample and presentation order, queue clearly favors Leaf, and dashboard slightly
favors Leaf. Independent Astra audits support those queue/dashboard judgments while
recognizing HTML's more compact dashboard decision. Baseline advantages do not establish
that a branch change improved the product.

A second independently authored HTML queue accepts the prescribed seven choices but
also blocks finish at seven of eight when the comment-settled ticket stays untouched.
Both judging orders prefer the retained Leaf queue. A fresh Leaf dashboard is slightly
preferred to the fixed HTML control in both orders. Its Astra evidence audit supports
that margin but qualifies stale wording as partly shared immediately after submission;
selected-state and transmission feedback differ. Opening full checks or exact buckets
is an interaction cost, not an established failure when the failing check and central
trend remain exposed. That audit saw the verdict summary before browser inspection,
so it is not a fully blind rescore.

The second HTML document retains the conditional migration plan that the first
control omitted. Against the same Leaf document it splits: one order slightly
prefers HTML's directly exposed review and compact phone opening; the other slightly
prefers Leaf's direct send and fitting phone comparison table. Both preserve the
Redis decision and Mei's Wednesday request. The earlier clear Leaf result remains
evidence about that first control, not a general document advantage.

Two shared presentation repairs have controlled evidence on identical authored pages:

- Queue outcomes get a reserved line beside the existing title and summary. Normal
  Fix/Escalate labels become readable; phone navigation spends one additional 17px line.
  Choosing, correcting and undoing preserve row positions. Long arbitrary answers still
  ellipsize. A fresh queue retains the substantive Orbis/Quanta context that an earlier
  author sample omitted.
- Settled options collapse every hidden child’s box, including generated add/Done
  controls, despite ordinary authored padding or minimum heights. The dashboard had
  retained 64px of empty card space. Expanded cards and rationale are unchanged;
  pointer, keyboard, anchored reveal and print remain available. The feature gallery’s
  settled answer demonstrates spacious expanded cards returning to one disclosure.

Revision guidance now distinguishes a current decision record and needed evidence from
its superseded interaction. A result-first wording has not established an overall
quality gain; unchanged repeats span losses and wins, so that extra wording was removed. An isolated A/B of playground
guidance about consequences at the controls showed no intended benefit and slightly
favored the original in both orders; the added wording was removed.

The browser user’s model report is not the canonical observation of copying. Handover
uses observed clipboard activity first, then admitted attention-bearing user events,
then reported manual export text, and finally the typed fallback. Incomplete decisions
retain the fallback. A successful settings Send was previously mislabeled as copying
because the model quoted the displayed instruction. Its final record was correct, but
verbatim chat feedback prevented it independently proving native-event recovery.
Saved runs retain that original evidence and limitation.

The existing first-served observation now retains the active revision and event boundary
without another state read. This identifies a candidate for later usability review;
it is not first HTTP response, first handoff or first usability. HTML controls have no
equivalent early immutable history. Author completion remains a separate metric.

Reproduce the focused product contracts:

```sh
uv run pytest tests/browser/test_render_options_settled.py -k 'collapse_without_going_out_of_reach or reconciles_added_options or printed_page' -q -n0
uv run pytest tests/browser/test_render_widgets.py -k side_tab -q -n0
pnpm run test:runtime
```

A later audit reproduced pooled budget behavior after Finance ownership changed, but
could not establish that the request excludes Finance pages from the cap. A payments
service-wide budget and a payments-rotation budget are both plausible. The judge prompt now asks for assumptions behind concerns based on ambiguous intent. Rejudging the same
configuration pair and the explicit Brightline constraint checks that calibration;
no product rule about budget ownership follows from the ambiguity.

A prospective first-served descriptor now has one bounded usability proof: the fresh
dashboard’s exact observed revision supported status, evidence navigation and a real
rollback selection at 900×600 after 155.7 seconds, 65.6 seconds before initial author
completion. The proof replays captured resources and the event boundary in a disposable
writable page. It does not establish the earliest usable revision, actual handoff, or
a comparable early HTML time.

The original HTML dashboard also retains a usable candidate before author completion.
Its first file write completed 173.6 seconds after the initial author phase began,
65.6 seconds before its answer. The literal heredoc can be reconstructed without
executing recorded commands; replaying four later literal replacements exactly
reproduces the saved first-phase file. In a disposable 900×600 browser, that earlier
source exposes rollout status and metrics and records rollback in fresh localStorage.
After recording, the top request remains stale except for its Edit decision button;
the explicit choice appears farther down. This is a retrospective usable-candidate
bound, not historical browser readiness. Leaf's served-revision observation and HTML's
completed-write observation, on different environment packets, do not establish a
causal or earliest-time comparison.

A separate registry-owner label-instruction pilot also did not establish its intended
behavior: neither author put consequences in choice labels despite confirmed exposure.
Both full workflows passed, and the pair split overall; both orders preferred the
candidate’s phone table and the base’s direct final navigation. The candidate also read
the reformatted raw registry, exposing a JSON-whitespace context difference. The added
instruction is rejected; the maintained registry remains unchanged. The independent
initial-control audit found better desktop evidence adjacency in the candidate, but
that composition difference does not show a consequence-label gain.

The fresh dashboard v1/v2 ablation slightly favors restored v2 in both completed
judgments; both workflows and quality checks pass. Both orders favor v2 phone
presentation and v1 decision experience, with width/comment/application tied. They
flag v1’s omitted memory comparison against 4.11. The independent reader, before
learning arm identities or verdicts, found the same phone advantage and v1’s advantage
for showing all four metrics at 900×600; v2 exposes the full trend there instead.
Both actual rollback routes and final decisions are correct.

This is a real whole-workflow one-guide contrast with one fresh author per arm. The
guide was read before initial composition, so an earlier influence is possible;
author variation remains unresolved. Source order already differs before finalization,
preventing attribution specifically to the phase4 rewrite, not invalidating the
contrast. Pruning v2 is therefore not an established phone-framing fix. Maintained v1
stays as the minimal rule given the prior mixed configuration results and no established
general benefit. No additional compactness instruction follows.

Later comparisons extend the same four-phase workflow to `patch-review`,
`notification-design`, `dependency-review`, `latency-review` and `draft-review`.
These add code review, visual design, directed data-flow correction, quantitative
chart inspection and user-owned freeform wording. They retain the same task in
Leaf and HTML; the user corrects a fact before making a final decision. The fixtures
and `evals/README.md` own their requirements and the current model configuration;
`MODELS` in `dev/leaf_dev/arms.py` owns pins. Historical runs used different frozen
runtimes, so this is case coverage, not one homogeneous benchmark population.

Main judgments and independent ordinary-reader audits sometimes disagree. Patch
review exposes a real tradeoff between code density and wrapped readability; its
split judgment is not a clear winner. Dependency review separates initial diagram
and interaction quality from the final record's prominence. Latency review's main
judgments and independent audit slightly prefer Leaf. These observations do not
establish a general advantage for either implementation or a runtime speed gain.
The original draft comparison remains unscored after an incomplete judge route;
its independent audit prefers HTML. An incomplete order is not a tie or a win.

The controlled rendering evidence now includes the earlier queue labels and settled
options repairs, native contents disclosure, and live diff reply sizing. In-flow
contents starts closed, reducing the opening footprint while preserving ordinary
links, reader open state, margin navigation and print. Cross-engine checking found
that CSS could not make closed-details links reachable in Firefox's margin posture;
the retained implementation follows the actual disclosure lifecycle. The live diff
repair seeds Pierre's existing column applier synchronously, then schedules resize
observations through Leaf's frame scheduler. It preserves initial sizing and avoids
the reproduced ResizeObserver feedback loop during a streamed line reply. Hidden
content retains the dependency's zero-width behavior. Neither repair proves a faster
whole authoring task. Optional code wrapping separately gives readers a choice
without changing copied source; it is not evidence that every code view should wrap.

Two retained authoring clarifications describe existing contracts. `serving-pages.md`
distinguishes offline reading and local page behavior from new recorded choices,
Undo and threads, which need the live server, not necessarily an active agent.
Both before/after comprehension probes chose the live route correctly. The Sign-off
paragraph in `authoring-asks.md` states that later widget edits neither withdraw a
version approval nor approve new wording: editable content must distinguish the
approved wording from the current draft. No new approval primitive or automatic
invalidation was introduced.

In the fresh draft guidance contrast, both authors already preserved a separate
approved record; the clarified arm won slightly in both orders for phone navigation.
Against the retained original HTML control, that preselected treatment artifact lost
slightly in both orders; an independent audit also preferred HTML's focused complete-
copy confirmation and nearby facts. The whole-document guardrail passed its workflow
checks but slightly favored unchanged guidance for directly visible evidence. These
results support retaining a factual clarification, not claiming it caused a UX or
speed improvement. Both document authors retired Mei Tanaka's Wednesday assessment
after Redis was chosen. The request does not explicitly cancel that assessment or
condition it on selecting Postgres; retirement is a plausible scope inference, not
an established ownership violation or unqualified compliance.

Native failures also exposed canonical boundaries worth repairing. Before a first
valid revision, `page state` must report the invalid source without reparsing its
invalid registry and aborting an author who just received actionable check feedback.
It now uses the existing accepted-page reading; invalid source still fails checking.
Script placement exposed a separate lifetime bug: moving an unchanged script between
head and patched main could leave duplicate nodes. Executable identity now includes
the DOM patch region, so crossing regions reloads; prose-only changes do not.
Validated scripts may consequently follow main, while inline classic execution and
other content/security restrictions remain checked. The aborted author attempt and
original failed diagnostics remain evidence, separate from subsequent successful runs.

Reproduce current tasks and the narrow contracts below. Replace `RUN_DIRECTORY`
with a run directory printed by `eval`; saved comparisons retain original payloads and
both predecision and final pages. Reusing a control or judging both presentation
orders adds no author sample. Native primary and helper durations are separate;
cached input is included in input totals and is not a dollar estimate. These runs
leave the broader measurement question in TODO #24 open.

```sh
uv run leaf-dev eval patch-review notification-design dependency-review latency-review draft-review --harness codex --condition both --repeat 1 -j 1
uv run leaf-dev eval-pairs .tmp/eval/RUN_DIRECTORY
uv run pytest tests/browser/test_render_toc_disclosure.py::test_contents_disclosure_keeps_its_links_focus_and_open_state tests/browser/test_render_code_reading.py::test_code_wrapping_keeps_source_copy_and_reader_choice tests/browser/test_render_code_reading.py::test_code_reference_keeps_command_context_and_cancel_destination -q -n0
uv run pytest tests/browser/test_render_diff_controls.py::test_a_live_line_reply_wraps_without_resize_observer_feedback tests/browser/test_chrome_contracts.py::test_script_region_moves_reload_without_leaving_duplicate_nodes -q -n0
uv run pytest tests/model/test_interact_document.py::test_page_state_keeps_accepted_registry_while_source_is_invalid tests/model/test_interact_document.py::test_tail_script_still_requires_deferred_execution -q -n0
```
