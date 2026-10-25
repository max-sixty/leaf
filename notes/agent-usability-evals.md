# Agent usability evals

Evidence from Leaf/plain HTML comparisons and page-quality studies, with remaining
evaluation gaps. `evals/README.md` owns execution and reporting; the maintainer
`/grinding-ui` skill owns the improvement loop.

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
proof of an error. The decisions reference (`authoring-decisions.md`) now requires explicit accounting:
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

## Bad pages and the checks, 2026-10-20

`page-reads-at-every-width` has an agent author one ordinary page in a single turn,
from the request of the document, dashboard, queue or configuration task, with no
user feedback. `dev/leaf_dev/page_defects.py` then has a Codex judge (Sol 6.1, medium)
use a live copy of the final page at 1600×1000, 900×700 and 390×844 with touch,
comment on a sentence, and list every defect a user would notice, without seeing any
check. A second, text-only turn sets each defect beside `page check` on the final
page, plain and with `--render`, and beside the checks the author ran itself.

```sh
uv run leaf-dev eval 'page-reads-at-every-width*' --harness claude-code --repeat 3 -j 2
uv run leaf-dev eval 'page-reads-at-every-width*' --harness codex --repeat 3 -j 2
uv run leaf-dev eval page-reads-at-every-width page-reads-at-every-width/dashboard page-reads-at-every-width/queue --harness claude-code --repeat 2 -j 2
uv run leaf-dev eval page-reads-at-every-width page-reads-at-every-width/dashboard page-reads-at-every-width/queue --harness codex --repeat 2 -j 2
```

The runs authored 37 pages at main `e1ed34cec`: 19 on Claude Code with Opus 5.5
(mean $1.29 a page) and 18 on Codex with Sol 6.1. The last two commands ran with
[#3328](https://github.com/max-sixty/leaf/pull/3328) in the tree, which changes only
an ask that holds a playground before other content. Three more configuration pages,
authored after that fix to check it, count in the defect table but not in the rates.
Each defect's owner is a hand classification from the judge's description and
screenshots. Each judgment's `metadata.page_defects` in `results.json` holds the
defects and check readings.

Pages with at least one defect, by the defect's owner, with Wilson 95% intervals:

| Owner of the defect                                 | Claude Code, 19 pages | Codex, 18 pages | All, 37 pages    |
| --------------------------------------------------- | --------------------- | --------------- | ---------------- |
| Author's content: a supplied fact wrong or left out | 17 (69–97%)           | 0 (0–18%)       | 17, 46% (31–62%) |
| Author's layout: a drawing, chart, table or order   | 5 (12–49%)            | 2 (3–33%)       | 7, 19% (9–34%)   |
| A Leaf widget                                       | 2 (3–31%)             | 4 (9–45%)       | 6, 16% (8–31%)   |
| Leaf's thread chrome                                | 10 (32–73%)           | 7 (20–61%)      | 17, 46% (31–62%) |
| Any rendering defect but the chrome's               | 7 (19–59%)            | 5 (12–51%)      | 12, 32% (20–49%) |
| Any defect but the chrome's                         | 18 (75–99%)           | 5 (12–51%)      | 23, 62% (46–76%) |

Rendering defects other than the chrome's fell on 6 of 11 dashboards, 4 of 6
configurations, 2 of 10 queues and no document. Every defect on all 40 pages, beside
the checks:

| Defect                                                                                                                                                                                                                                                        | Owner                          | Defects (pages) | Final plain check | Final render check | Author's own checks                |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | --------------- | ----------------- | ------------------ | ---------------------------------- |
| A supplied fact stated wrongly or left out                                                                                                                                                                                                                    | author                         | 26 (19)         | 0                 | 0                  | none reported                      |
| SVG labels a few pixels high on a phone or at 900px                                                                                                                                                                                                           | author                         | 3 (3)           | 0                 | 3                  | reported; changed, not enough      |
| Other author layout: a chart annotation cut off at the phone's edge (2), labels too faint, a chart tooltip reading "UTC 935", a phone table dropping a column, a note's table clipped, headline metrics three screens down (2), two footer spans run together | author                         | 9 (7)           | 0                 | 0                  | 1 reported and changed, not enough |
| A playground followed by a note draws its instruction over the note at 900×700                                                                                                                                                                                | `lf-ask` (fixed, #3328)        | 2 (2)           | 0                 | 0                  | none reported                      |
| A playground's stage gets 190–280px at 900×700, under its presets and instruction                                                                                                                                                                             | `lf-playground` in a workspace | 4 (4)           | 0                 | 0                  | none reported                      |
| The tally says "1 of 8 to answer" while its Next on me is disabled                                                                                                                                                                                            | `lf-tally`                     | 2 (2)           | 0                 | 0                  | none reported                      |
| An open thread card covers the text near its passage at 900px and on a phone                                                                                                                                                                                  | thread chrome                  | 14 (14)         | 0                 | 0                  | none reported                      |
| A thread's pin covers words at a line's end on a phone                                                                                                                                                                                                        | thread chrome                  | 5 (5)           | 0                 | 0                  | none reported                      |
| The inline thread header's pencil overlaps "Waiting for pickup" on a phone                                                                                                                                                                                    | thread chrome                  | 1 (1)           | 0                 | 0                  | none reported                      |

Of the 66 defects, the final render check reported 3 and the plain check none. The
checks read neither the page's facts nor Leaf's own chrome (`render_gate/readings.py`
leaves chrome to the suite), so their reach is the 20 rendering defects outside the
chrome, of which they reported 3. Their value shows earlier: on 35 of the 40 pages the
author's own checks reported 142 distinct findings, as the matching turn groups repeats,
and the final page still had 10 of them. The render check's were labels shrunk below
10px (52 on 10 pages, 9 kept on 4), tables squeezed at 360px (7), labels drawn over
each other in a chart (6), scrollbar clearance (3), content past the column (1), a
verbatim mismatch (2) and a console error (1). The plain check's were markup: targets with no id (35 on 18 pages), schema
refusals (25 on 7 pages), and 10 runs before `index.html` existed. Every author ran a
check, and 27 of 40 ran `--render`; on the 13 pages whose authors did not, mostly
queues and Codex pages, the final render check found nothing.

For "Decide what plain `page check` runs in a browser" (TODO.md): on no final page did
the judge see a widget fail to draw or the render check report a console error. The
one console error during authoring, an `lf-chart` transform reading `NaN`, came from
the render check and was fixed. Every plain-check finding was markup.

How far to trust these numbers:

- The rates are what this judge reported. It misses defects: every judge opened a
  thread, yet it reported the thread card over neighbouring text on 14 of the 40
  pages. How often it reports a defect that isn't there was not measured.
- Four content defects checked against the requests were real: a backfill of
  "about 550k" sessions where the request says 312k, "holding keeps half its
  checkouts timing out" where 50% is the rollout stage and the error rate is 0.91%,
  errors that "held at 0.91% since the pause" though the buckets after it read 0.97,
  0.95 and 0.93, and a fifth contact called the fourth. Codex pages restated the
  supplied facts more nearly word for word, and Claude Code pages added derived
  claims; the "half of eu-west's checkouts" claim appeared on 5 of 6 Claude Code
  dashboards.
- A second reading of the same 37 pages confirmed the gap, though not through a
  second live judge. Opus 5.5 given the same pages and prompt reported a fact defect
  on 6 of 19 Claude Code pages and 3 of 18 Codex pages, catching 6 of the 26 real
  ones on Claude Code pages; it spent its turn on layout. A text-only audit that sets
  the request beside the page's source, run once with Opus 5.5 and once with Sol
  6.1, flagged 16 and 18 of the 19 Claude Code pages and 8 and 10 of the 18 Codex
  pages, most Codex flags being rewordings a reader wouldn't notice. Reading every
  flag by hand, a supplied fact was misstated on 12 of 19 Claude Code pages (41–81%)
  and 0 of 18 Codex pages (0–18%; 1 counting a reworded recommendation), and
  misstated or left out on 17 of 19 and 1 of 18. The Codex live judge caught 23 of
  the 26 on Claude Code pages, and 3 of its 24 fact reports were not real (a
  discrepancy the page had labelled, a disputable date, a phone layout), so it shows
  no bias toward Codex pages. Five Codex dashboards also said errors "remain at
  0.91%" after the pause, but only in a chart's screen-reader label.
- The 3 render-reported defects match the check messages the matching turn quoted.
  A second matching turn, given each check's whole output and each tool call whole
  where the first had cut them, read 65 of the 66 defects the same way; it found that
  the author of the faint labels had changed them after a check reported them shrunk.
  The other readings were not checked by hand.

A paragraph in `skills/leaf/references/page-authoring.md`, "Reading cost", now asks
the author to keep supplied facts as given and to keep the figures a derived claim
rests on beside it. Over two batches of Claude Code pages from the document,
dashboard, queue and configuration requests (the second without the document,
whose pages misstated nothing in either arm), labelled by hand without knowing the
arm, pages misstating a supplied fact fell from 22 of 37 to 12 of 36 (−26 points,
95% interval −45 to −3), and pages where the Codex judge reported a fact defect from
26 of 37 to 17 of 36 (−23, −43 to −1). Configuration pages improved most (5 of 10 to
1 of 10). Dashboards still misstate (9 of 11 to 7 of 11), mostly as "half of
eu-west's checkouts" and errors that "sat at 0.91%" after the pause, and queues
still count Orbis's contacts one short (8 of 11 to 4 of 10). The second batch ran
because the first alone (−29 points, −53 to +1) did not exclude no change. Six Codex
pages per arm showed no change.

The recurring Leaf-owned defects below follow from recorded choices, and are open
decisions rather than fixes:

- A thread card opens over the text near its passage, which Escape uncovers (root
  `AGENTS.md`, "Working on the repository"); the judge counted it on 14 pages.
- On a phone a thread's pin stands over the end of the line it marks (5 pages).

## Current configuration anchor, 2026-10-21

One bounded block used four fresh Codex authors, in Leaf, HTML, HTML, Leaf order,
at `0cc2760636d14b9fc8873f3be69337486ecb723c`. All used `gpt-6.1-sol` with medium
reasoning and the same configuration task at 1600×1000. All four saved
`comparison.json` inputs match, as do the 639 non-cache files in each saved
`skills/leaf` tree. The working-tree changes during authoring were maintainer
instructions, outside that shipped tree.

| Round | Condition | Native author minutes | Initial turn minutes | Final record      |
| ----- | --------- | --------------------- | -------------------- | ----------------- |
| 1     | Leaf      | 9.5                   | 4.7                  | All six decisions |
| 2     | HTML      | 5.0                   | 2.1                  | All six decisions |
| 3     | HTML      | 6.0                   | 3.0                  | All six decisions |
| 4     | Leaf      | 11.1                  | 4.8                  | All six decisions |

Leaf averaged 10.3 author minutes and HTML 5.5, across four turns each. These are
native author durations, excluding browser users, live judges and command elapsed
time. Dollar cost and first usable handoff time remain unmeasured. The older
comparison used a different harness revision; these figures do not measure a
causal before/after gain.

Both Leaf decision journeys used its event log; both HTML journeys copied the
page's settings without typed fallback. All final records retained Finance
ownership, separate finance-ops paging and the remaining noisy payments page,
without claiming a live alert configuration change. Execution and page checks
completed for all four. The first HTML's final judge reported a threshold-keyboard
defect; the other three final judges passed. Replaying the same keys on the first
HTML and on a bare, script-free native select produced the same non-response in
headless Chromium and Firefox. That test does not isolate an authored defect, so
the attribution remains unconfirmed. The original verdict is retained; the browser
users and pair judges completed the offered selection and copying routes.

Both paired Sol judgments preferred HTML in both presentation orders: slight/clear
for the first pair and slight/slight for the second. HTML kept six settings visible
beside navigable evidence. Leaf's first page required tab switching; the second's
header and instruction area left a short scrolling preview. Evidence favored Leaf
in three judgments and tied in one; comments and applied decisions tied in all
four. These are local composition trade-offs, not a general product ranking.

A separate 1600×1000 chrome journey on the first Leaf's saved phase 3 typed a
draft, retained it through Escape/reopen, sent a visible comment that persisted in
the log, and reached another alert through Escape and its tab. It reported no
console findings or horizontal overflow. It does not cover other chrome journeys
or mobile.

A fresh `gpt-6-astra` judge independently operated the first pair's saved phase 3
and phase 4 pages in both presentation orders, without prior verdicts in its
prompt. Both judgments preferred HTML slightly for its overview, while favoring
Leaf's historical evidence and noting its direct-send route. The second pair has
Sol judging only. The exact README copied-index recipe completed successfully;
both native `thread/started` notifications confirm Astra, and hashes establish
that all four original result indexes and the main verdict file stayed unchanged.
Audit evidence is `.tmp/eval/audit-yci6yzij/0/`, with its provenance recorded in
`.tmp/ui-grinding/cycle/astra-audit.json`. Opus reviewed the proposed skill and
audit recipe; this block did not run fresh Opus authors.

The four runs are under `.tmp/eval/` in this checkout:

- `20261021-135550-9h8_k04r` — Leaf, `configuration-ocar5rb0`.
- `20261021-141858-mlmwdqua` — HTML, `configuration-dmgg6mb1`.
- `20261021-142853-coaxw4ab` — HTML, `configuration-jskgsnus`.
- `20261021-143958-54gvyi2w` — Leaf, `configuration-b7p94ayd`.

`.tmp/ui-grinding/cycle/provenance-checked.json` retains runtime hashes, native
model fields and phase paths. `eval-report` on those four runs regenerates the
comparison; use the README's isolated copied-index recipe for rejudging without
overwriting the original verdicts. The maintainer's `/grinding-ui` skill owns the
improvement loop and experiment design, with command mechanics kept in the README.
The keyboard and chrome replays use disposable original-runtime copies:

```sh
uv run python .tmp/ui-grinding/replay_saved.py html 20261021-141858-mlmwdqua .tmp/ui-grinding/keyboard_journey.py
uv run python .tmp/ui-grinding/replay_saved.py html 20261021-141858-mlmwdqua .tmp/ui-grinding/keyboard_journey.py --firefox
uv run python .tmp/ui-grinding/replay_saved.py leaf 20261021-135550-9h8_k04r .tmp/ui-grinding/chrome_journey.py
```

The original October 12 brief and refinements were recovered from Claude session
`0cc26736-55c9-40c3-80bf-c13a77d209db` (lines 6, 1685, 2335–2337, 2427 and 3892),
and the follow-on brief from Codex session `01a13358-0141-70f0-8bb4-a8defb75b07e`
(line 13). The original nine-pair Claude report survives at
`~/.local/state/leaf/pages/eval-plain-html/`, with its raw runs at
`~/.tmp/leaf.authoring-vs-plain-html/eval/`; those are distinct from the recovered
twelve-author Codex comparison above. The continuing brief is TODO #20.

## Widgets plain page check doesn't run, 2026-10-24

Plain `page check` runs a page in a browser only where `needs_browser`
(`render_gate/page_code.py`) finds a script, a page widget, a data widget or a widget
naming page media. `widgets-draw-as-written` measures the kinds it left out: a tuning
playground (the case's primary context), a playground of candidates
(`/playground-candidates`), a text document with a Markdown preview
(`/text-document`), and a chart or a Mermaid diagram in a thread message
(`/thread-chart`, `/thread-diagram`). `visual-change-uses-captures/review` does the
same for a visual review, since that case holds the captures. `/dashboard` is the
control: its charts are a kind plain check already runs. Each sample authors one page
in one turn; `dev/leaf_dev/draw_failures.py` reads the executor's final
`page check --render`, which opens every thread holding markup, and every check the
author ran, for findings that say a widget or the page's code failed to run or draw.

```sh
uv run leaf-dev eval 'widgets-draw-as-written*' visual-change-uses-captures/review --harness claude-code --repeat 10 -j 2
uv run leaf-dev eval 'widgets-draw-as-written*' visual-change-uses-captures/review --harness codex --repeat 6 -j 2
```

The runs authored at `73222dc97` with the cases of `371e34337`: 70 pages on Claude Code
with Opus 5.5 (mean $0.41–1.77 a page by context) and 42 on Codex with Sol 6.1
(medium). Codex samples' own checks are read since `ff445bcdc`, which keeps a
`leaf` MCP call's output in the check log; before it, a Codex author's checks never
reached the log, so earlier readings of "the author's own checks" undercount Codex.
Every sample placed the widget its context asks for.

| Kind                                | Claude Code: a check saw it fail / final page fails | Codex      | Authors who ran `--render` |
| ----------------------------------- | --------------------------------------------------- | ---------- | -------------------------- |
| Tuning playground                   | 0 / 0 of 10                                         | 0 / 0 of 6 | 10 of 10; 0 of 6           |
| Playground of candidates            | 0 / 0 of 10                                         | 0 / 0 of 6 | 7 of 10; 0 of 6            |
| Text document with preview          | 0 / 0 of 10                                         | 0 / 0 of 6 | 2 of 10; 6 of 6            |
| Visual review of supplied captures  | 0 / 0 of 10                                         | 0 / 0 of 6 | 10 of 10; 1 of 6           |
| Chart in a thread message           | 0 / 0 of 10                                         | 0 / 0 of 6 | 1 of 10; 0 of 6            |
| Mermaid diagram in a thread message | 0 / 0 of 10                                         | 0 / 5 of 6 | 5 of 10; 0 of 6            |
| Control: charts on a dashboard page | 5 / 0 of 10                                         | 1 / 0 of 6 | 10 of 10; 6 of 6           |

Measured:

- None of the 64 pages with a playground, text document or visual review had the
  widget fail to draw, at any check its author ran or on the final page (0 of 64,
  0–6%). Authors wrote values on the step, choices that exist and focus rectangles
  inside their captures; all 16 visual reviews set a focus rectangle.
- 5 of 6 Codex thread messages holding a sequence diagram didn't draw (44–97%):
  each put a `;` in a `loop` label or a `Note`, which Mermaid reads as the end of a
  statement. None of those authors ran `--render`, and plain check never draws a
  thread, so all five reached the user as an error box; Leaf would have told the
  author only once the user opened the thread. Claude Code's 10 diagrams and all 16
  thread charts drew.
- On dashboards, 5 of 10 Claude Code authors and 1 of 6 Codex authors first gave a
  Plot `text` mark a function for `dy`, which Plot takes as a constant, after
  `--render` reported their end labels drawn over each other. Plot drew those labels
  at `translate(x,NaN)`. Plain check runs those charts and passed them, since it hears
  only what the runtime reports and nothing threw; only `--render`, which reads the
  console, reported them. Every dashboard author ran `--render`, so every final page
  was clean.
- The run plain check already gives a page caught the page-code failures Codex
  authors made: a playground script that created an `lf-chart` at runtime ("has no
  captured widget descriptor", then the chart's body throwing) and a script that
  registered a command id the runtime refused. No author's plain check run failed on
  a widget's authored values.
- Two Claude Code playground authors (in 11, counting the smoke run) hit the render
  gate's own crash, `gate-failed` from `shrunkLabels` reading `ownerSVGElement` of a
  `<text>` in the HTML namespace, which a lit `html` sub-template inside an `<svg>`
  makes. Each read the gate's `words.js` to work out why, and rebuilt the drawing
  with `createElementNS`.

Inferred, not measured: the playground, text document and visual review results
cover one request each; a request with harder constraints (a step the values don't
divide, captures at device scale 2) could fail more. The thread results cover one
request per widget, and the semicolon failure is specific to Mermaid's grammar.

Decision, made on this evidence:

- Plain `page check` keeps its criterion. The left-out page widgets didn't fail, and
  every failure its browser run caught came from a trigger it already has.
- A thread message whose markup places a widget that criterion names is run once
  before it posts and refused on what the run reports (`bed5963ff`,
  `render_gate/command.message_check`), reversing #1691 for those messages only.
  Reposting the 32 eval messages with it refused exactly the 5 that don't draw and
  posted the other 27, each in 1.3–1.9 s at a load of 10–20; markup without such a
  widget waits on no browser.
- `lf-chart` reports a mark it drew at NaN, keeping the drawing (`79c1a185e`), so
  plain check's chart run, `--render` and `leaf wait` all hear the dashboard mistake.

The thread-diagram context then ran on Codex beside the merge base:

```sh
uv run leaf-dev eval widgets-draw-as-written/thread-diagram --harness codex --base --repeat 8 -j 2
```

On the base, 4 of 8 diagram messages didn't draw (22–78%; 9 of 14 with the first
run, 39–84%). With the message run, 7 of 8 authors had their first message refused
with Mermaid's parse error, fixed it and posted again, and all 8 final messages drew
(0 of 8, 0–32%). Mean author time rose from 1.0 to 1.2 minutes.

## Render findings after handover, 2026-10-24

TODO.md's "Read the full render gate after handover" would run the render readings on
the server when a version goes live and deliver them through `leaf wait`. Two
measurements decide whether to build it: how long the readings take, and whether an
agent that has handed a page over acts on findings that arrive afterwards.

**How long `page check --render` takes.** `.tmp/overnight/time_checks.py` (kept with
the run evidence, not in the tree) built each catalog example and the render corpus
with this checkout and timed the command, launcher included, plain and with
`--render`, under `LEAF_RENDER_VIEWPORT=fixed`, on a shared Mac at a 1-minute load of
10–39.

| Pages                                         | `--render`, median (p10–p90) | Plain, no browser run | Plain with the page-code run |
| --------------------------------------------- | ---------------------------- | --------------------- | ---------------------------- |
| 17 catalog examples, 2 runs each              | 8.1 s (6.0–12.5)             | 0.23 s (12 runs)      | 1.21 s (22 runs)             |
| 70 final pages from `widgets-draw-as-written` | 7.7 s (6.2–11.1)             | 0.29 s (42)           | 1.28 s (28)                  |
| The render corpus                             | 384 s (2 runs)               | —                     | 15.6 s                       |

By context, eval pages took 6.5 s (text documents, thread pages) to 11.1 s (visual
reviews). Plain check with its page-code run took the 1.3 s that #1691 measured for a
page with a chart, so the load seems to have stretched these little; `--render` was
not timed on an idle machine.

**Whether agents act on findings delivered after handover.**
`document/render-after-handover` hands the agent `evals/usability/fixtures/cutover.html`,
a drafted status page whose four consumer cards run out of any window up to 920px
wide (`page-scrolls`, `past-column` and `clipped-out` failures) and whose SVG chart's
labels shrink below 10px (`shrunk-labels` advice). The user asks for a one-line date
change and a handover. Once the agent's turn ends, the driver's `render` move runs
`page check --render` on the page as served and posts what plain check doesn't report
as the page's `error` event, the channel a failure the user's browser saw takes; a
page with nothing to report gets no delivery. The `-quick` context drops the closing
line other live cases share, "Use headless browser tooling for your own inspection",
and says only that the user will open the page.

```sh
uv run leaf-dev eval document/render-after-handover document/render-after-handover-quick --harness claude-code --repeat 10 -j 2
uv run leaf-dev eval document/render-after-handover document/render-after-handover-quick --harness codex --repeat 10 -j 2
```

| Context, harness           | Ran `--render` before handing over | Got a delivery: failures / advice only | Edited and checked again after it | Final page fails `--render` |
| -------------------------- | ---------------------------------- | -------------------------------------- | --------------------------------- | --------------------------- |
| with the line, Claude Code | 10 of 10                           | 0 / 2                                  | 2 of 2                            | 0 of 10                     |
| with the line, Codex       | 10 of 10                           | 0 / 1                                  | 1 of 1                            | 0 of 10                     |
| quick, Claude Code         | 7 of 10                            | 5 / 5                                  | 9 of 10                           | 1 of 10                     |
| quick, Codex               | 5 of 10                            | 5 / 3                                  | 8 of 8                            | 0 of 10                     |

Measured (40 sessions, Opus 5.5 and Sol 6.1, on runtimes that differ from
`73222dc97` only outside this fixture's path):

- Every agent told to inspect ran `--render` before handing over a one-line edit,
  though the skill says a quick page takes plain `page check` alone. Without that
  line, 8 of 20 skipped it (40%, 22–61%).
- Of the 21 sessions that got a delivery, 20 edited the page and ran
  `--render` again in the same wake (95%, 77–99%), finishing a median 34 s (Claude
  Code) and 39 s (Codex) after the delivery in the quick runs. All 11 advice-only
  deliveries (the shrunk labels) were acted on too (74–100%).
- The one that didn't act had run `--render` itself, judged the overflowing cards the
  user's own drafting choice, and asked the user about them in a thread before
  handing over; it read the delivery as a repeat of that question. One other agent
  asked the same question before handing over and then fixed the cards when the
  delivery arrived, saying Leaf had marked them as errors.
- Handing over without `--render` took a median 37 s (Claude Code, 3) and 36 s
  (Codex, 5); with it, 78 s and 67 s.
- All 8 agents who skipped `--render` and got the failures fixed them, so every
  final page in the quick runs is clean of failures but one, the agent above.

Inferred, not measured: the delivery came as an `error` event, whose handling clause
says "The page's runtime reported a failure the user saw. Fix the page or widget and
save the fix." A server-side pass would likely deliver advice through a gentler
clause, so the 11 of 11 advice fixes are an upper bound, and one agent cited the
error framing as the reason to change a layout it had judged the user's. One
fixture and one request; a page an agent wrote itself may get a different response
than a draft the user handed over.

What this says about the TODO item: the readings take about 8 s on typical pages, the
time an agent saves by not waiting on them (about 40 s per handover including the
reading and fixing it prompts) is real, and agents that skip them do act when the
findings arrive afterwards. The measurements support building the pass, with a
handling clause per severity rather than the `error` channel's.

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
