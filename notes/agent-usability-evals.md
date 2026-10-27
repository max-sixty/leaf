# Agent usability evals

Evidence from Leaf/plain HTML comparisons and page-quality studies, with remaining
evaluation gaps. `evals/README.md` owns execution and reporting; the maintainer
`/hill-climb-ui` skill owns the improvement loop.

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
proof of an error. The On me reference (`authoring-on-me.md`) now requires explicit accounting:
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
overwriting the original verdicts. The maintainer's `/hill-climb-ui` skill owns the
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
twelve-author Codex comparison above. The continuing brief is
[issue #4017](https://github.com/max-sixty/leaf/issues/4017).

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

Two harder contexts then tested whether those widgets hold up where the values are
easier to get wrong. `widgets-draw-as-written/playground-fine-steps` gives today's
settings at values a round step skips (quality 0.82, sharpening 0.7 px, saturation
1.15×, width 1,250 px), and `visual-change-uses-captures/review-scaled` states the
captures at device scale 2, so a focus rectangle has to be in CSS pixels, half the
image's own. All 40 drew (10 per context and harness; 0 of 104 with the plain
contexts, 0–4%): every Claude Code author gave quality `step="0.01"`, and all 20
reviews set a focus rectangle that fit the 600×350 capture. One Codex author's page
script misused `generatedElement`, and its plain check, which runs any page with a
script, caught it.

```sh
uv run leaf-dev eval widgets-draw-as-written/playground-fine-steps visual-change-uses-captures/review-scaled --harness claude-code --repeat 10 -j 2
uv run leaf-dev eval widgets-draw-as-written/playground-fine-steps visual-change-uses-captures/review-scaled --harness codex --repeat 10 -j 2
```

Inferred, not measured: the thread results cover one request per widget, and the
semicolon failure is specific to Mermaid's grammar.

Decision, made on this evidence:

- Plain `page check` keeps its criterion. The left-out page widgets didn't fail, and
  every failure its browser run caught came from a trigger it already has.
- A thread message whose markup places a widget that criterion names is run once
  before it posts and refused on what the run reports (`bed5963ff`,
  `render_gate/command.message_check`), reversing #1691 for those messages only.
  Reposting the 32 eval messages with it refused exactly the 5 that don't draw and
  posted the other 27, each in 1.3–1.9 s at a load of 10–20; markup without such a
  widget waits on no browser.
- `lf-chart` refuses a mark whose `dx`, `dy` or margin is not a number before Plot
  draws it, naming the mark and the option (#3956), so plain check's chart run,
  `--render` and `leaf wait` all hear the dashboard mistake. Every NaN drawing in
  these runs came from that one cause.

The thread-diagram context then ran on Codex beside the merge base:

```sh
uv run leaf-dev eval widgets-draw-as-written/thread-diagram --harness codex --base --repeat 8 -j 2
```

On the base, 4 of 8 diagram messages didn't draw (22–78%; 9 of 14 with the first
run, 39–84%). With the message run, 7 of 8 authors had their first message refused
with Mermaid's parse error, fixed it and posted again, and all 8 final messages drew
(0 of 8, 0–32%). Mean author time rose from 1.0 to 1.2 minutes. Claude Code's
thread charts and diagrams, 6 of each per arm, all drew on both arms, and no message
was refused; mean author time was 1.1 minutes with the run and 1.4 without.

```sh
uv run leaf-dev eval widgets-draw-as-written/thread-diagram widgets-draw-as-written/thread-chart --harness claude-code --base --repeat 6 -j 2
```

An earlier run of similar cases, from the closed #3901 at `f00911ed1`, agrees and
adds two observations. In its `placed-widgets-draw` cases and a visual-review case,
agents authored 41 samples on Claude Code (Opus 5.5) and 28 on Codex (Sol 6.1), and
its grader counted a widget as failed only where the runtime posted an `error`
event. No final page or message failed on that count: text documents 0 of 13
(0–23%), markup-only playgrounds 0 of 9 (0–30%), visual reviews 0 of 13 (0–23%) and
charts in thread messages 0 of 30 (0–11%), from 29 samples.

- 2 of 29 thread-chart samples (7%, 2–22%) had a chart draft that failed while its
  author wrote it, both found by the 4 Claude Code authors who drew their chart on
  a scratch page with `--render`. One failed with `invalid lineAnchor`, which the
  runtime reports. The other logged Plot's `translate(0.5,NaN)` and was posted; the
  runtime of the time reported nothing, so it counted as drawn. Its `Plot.text`
  mark took `dy: (d) => (d.region === "us-east" ? 14 : -10)`, the per-datum offset
  #3956 now refuses. On the page at main `d91276596`, plain `page check` reports
  that chart as `marks[1] (text) has a dy that is not a number`, and `thread create`
  would refuse the message. #3901 reported no other NaN drawing, so a scan for NaN
  after the chart draws, which #3923's branch had and its merge dropped, would
  catch nothing these runs show.
- Asked for "a Leaf visual review", 3 of 3 Claude Code authors (44–100%) paired the
  captures in `lf-shot` rather than `lf-visual-review`. #3901 then named the package
  in the prompt, as `visual-change-uses-captures/review` does, so the visual-review
  rates in both runs measure whether the widget draws once chosen, not whether
  authors find it.

`dev/tests/browser/test_draw_failures.py` is #3901's control for the grader: a
playground control at `value="40"` over `max="24"` passes plain `page check`
without a browser, and `draw_failures.py` reports it from `--render`, beside a
thread message's `lf-chart` whose body throws.

## Render findings after handover, 2026-10-24

[Issue #4042](https://github.com/max-sixty/leaf/issues/4042),
"Read the full render gate after handover", would run the render readings on
the server when a version goes live and deliver them through `leaf wait`. Two
measurements decide whether to build it: how long the readings take, and whether an
agent that has handed a page over acts on findings that arrive afterwards.

**How long `page check --render` takes.** Each catalog example and the render corpus
was built with this checkout and the command timed, launcher included, plain and
with `--render`, under `LEAF_RENDER_VIEWPORT=fixed`, on the shared Mac; the eval
pages were the saved final pages, re-vendored. One run per example:

```sh
LEAF_RENDER_VIEWPORT=fixed uv run python - <<'PY'
import tempfile, time
from pathlib import Path
from leaf_dev import ROOT
from leaf_dev.arms import build_source, run_leaf
from leaf_dev.commands.distribution import cached_installation
from leaf_dev.example_data import catalog_sources
arm = cached_installation(ROOT)
scratch = Path(tempfile.mkdtemp(dir=ROOT / ".tmp"))
for source in catalog_sources():
    page = scratch / source.stem
    build_source(arm, scratch / "state", source, page)
    for flags in ((), ("--render",)):
        started = time.perf_counter()
        run_leaf(arm, scratch / "state", "page", "check", str(page), *flags)
        print(source.stem, flags, round(time.perf_counter() - started, 2))
    run_leaf(arm, scratch / "state", "server", "stop", str(page))
PY
```

| Pages, 1-minute load                                 | `--render`, median (p10–p90) | Plain, no browser run | Plain with the page-code run |
| ---------------------------------------------------- | ---------------------------- | --------------------- | ---------------------------- |
| 17 catalog examples, 3 runs each, load 6–10          | 7.0 s (5.3–11.6)             | 0.20 s (18 runs)      | 0.99 s (33 runs)             |
| 17 catalog examples, 2 runs each, load 10–22         | 8.1 s (6.0–12.5)             | 0.23 s (12)           | 1.21 s (22)                  |
| 70 final pages from `widgets-draw-as-written`, 14–39 | 7.7 s (6.2–11.1)             | 0.29 s (42)           | 1.28 s (28)                  |
| The render corpus, 2 runs, 12–18                     | 384 s                        | —                     | 15.6 s                       |

By context, eval pages took 6.5 s (text documents, thread pages) to 11.1 s (visual
reviews), and the slowest example, `pr-walkthrough`, 15 s. At the lower load the
check took about 1 s less; no run was on an idle machine.

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

The delivery came as an `error` event, whose handling clause says "The page's
runtime reported a failure the user saw. Fix the page or widget and save the fix.",
and one agent cited that framing as the reason to change a layout it had judged the
user's; the next paragraphs measure a clause of the pass's own. Not measured: this
is one fixture and one request, and a page an agent wrote itself may get a different
response than a draft the user handed over.

To see what the clause decides, the quick context ran again on both harnesses with
the `error` kind's handling in `browser/registry.json` replaced, in the arm only, by
one a render pass might carry: "Leaf's render check read the version you handed over,
as the user's browser draws it. Fix each failure it lists and save the fix. Weigh each
piece of advice against the page, and change the page only where that helps the user.
Reply only if the user asked about it." (runs `20261024-233654-7g77ma3o` and
`20261024-234904-48a2x9q8`; the registry change was not committed).

| Quick context, harness, clause  | Ran `--render` first | Failures delivered: fixed | Advice only delivered: page changed | Final pages keeping the advice |
| ------------------------------- | -------------------- | ------------------------- | ----------------------------------- | ------------------------------ |
| Claude Code, `error` clause     | 7 of 10              | 4 of 5                    | 5 of 5                              | 3 of 10                        |
| Claude Code, render-pass clause | 7 of 10              | 5 of 5                    | 1 of 5                              | 9 of 10                        |
| Codex, `error` clause           | 5 of 10              | 5 of 5                    | 3 of 3                              | 0 of 10                        |
| Codex, render-pass clause       | 5 of 10              | 5 of 5                    | 1 of 1                              | 0 of 10                        |

With the render-pass clause every agent that got failures fixed them (10 of 10,
72–100%), and Claude Code left the shrunk labels as they were in 4 of 5 advice-only
deliveries, where the `error` clause had it change the chart every time. Codex changed
the page for advice under either clause.

For that issue: the readings take 7–8 s on a typical page. An agent that handed
over without them did so about 40 s sooner, the check plus the reading and fixing it
prompted, and every such agent that got the failures afterwards fixed them. That
supports building the pass. Its delivery decides what agents do with advice: a clause
of its own that tells failures from advice kept the failure fixes and let Claude Code
weigh the advice.

## Authoring effort, 2026-10-24

An overnight campaign read Claude Code (Opus 5.5) and Codex (Sol 6.1) authors' tool
timelines for where a Leaf author spends time an HTML author doesn't. On the full
configuration workflow at main `73222dc97`, Opus Leaf authors took 9.6 native minutes
(n=5) against HTML's 6.3 (n=2), and the gap sat in the first authoring turn (4.2 against
2.05 minutes); the width, comment and decision phases were alike. So most measurement
ran only that first turn, with arrangement_eval's real first prompt and no browser
user or judge, several authors per arm, arms interleaved. Minutes vary by about a
quarter between authors on one arm and with host load (10–58 tonight), so three per
arm separate a mechanism (a refusal fires or not, a grep happens or not) but rarely
minutes.

What a first turn spent, at main: reading the skill and references (~50 s against
HTML's ~10), render checks (13 s each; 3–11 per dashboard, 41–133 s of tool time,
where an HTML author's tools total 1–13 s), the author's own revisions after reading
the saved screens, and avoidable rounds:

| Sink at main                                                                                   | Seen in                                                               | Repair                                                                                                                                  | After                                                     |
| ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Grepping Leaf's source for how a page script reaches the playground (6–9 calls)                | 3/3 configuration authors, 3/3 on a retry-policy playground           | The playground's author instructions show the whole page script (#3952)                                                                 | 0/3 and 0/3; configuration first turn 4.4 → 3.5 min (3+3) |
| `name="5xx-threshold"` refused by a leading-letter pattern                                     | 2/3                                                                   | Names take ids' pattern (#3952)                                                                                                         | gone                                                      |
| `class` or `style` on a playground control refused                                             | 8 and 2 samples                                                       | Both are outside every widget schema (#3954)                                                                                            | can't fire                                                |
| `id` on a playground control refused, though page-authoring.md asks for ids                    | 4/4 Codex authors                                                     | Controls, choices and presets declare `id` (#3952)                                                                                      | can't fire                                                |
| Per-datum `dy` in lf-chart → NaN, reported only as a console error from Plot's bundle          | 14/17 dashboards                                                      | The chart names the mark and option; its instructions say offsets are one per mark (#3956)                                              | 0/3                                                       |
| squeezed-table advice chased over many render checks, ending in a column hidden at phone width | 7/8 dashboards hid data                                               | The advice says every column stays in reach (#3956)                                                                                     | 1/15                                                      |
| `stamp --completes <playground>` refused with no fix                                           | 4/4 Codex decision phases                                             | The refusal lists open to-dos and says an answer needs no flag; conversation-loop.md says how a start on the user's update ends (#3959) | 2/3 with the message alone, 0/3 with both                 |
| Sticky boxes painted with guessed tokens (`var(--bg)`)                                         | 9/37 pages used an undefined token                                    | page-authoring.md states the `--lf-ground` rule (#3959)                                                                                 | 3/3 use it                                                |
| `--playground-choice-columns` ignored by plain threshold choices, so authors read theme.css    | 24 configuration samples; 13/78 pages styled `.lf-playground-choices` | Plain choices read the property too (#3952)                                                                                             | probe: one column with the property set                   |

On the configuration first turn, main against the campaign branch with every
repair through the harness fix, 5 interleaved authors each: 3.6 against 4.1 minutes,
$1.09 against $1.28, 20 against 29 tool calls; main's mean over all 10 of its first
turns tonight was 4.3 minutes. Validation on the full configuration workflow, main
against the branch through the chart offsets, Opus, 3 per arm: totals 9.0, 9.2, 13.2
against 7.6, 8.5, 9.7 minutes, first turns 4.4, 4.8, 4.4 against 2.8, 3.3, 5.6, cost
$3.14 against $2.49 a sample; every final judge passed.
Codex, two runs pooled: first turns 2.7 against 2.5 minutes (n=5 each), all completed
judgments passed. In three Codex runs, 3 of 8 base samples and none of 8 candidates
errored in the harness's comment journey (a 15 s wait for the selection field or a
response); the cause wasn't traced. Dashboard and document first turns didn't get
faster; their time is the record review: render checks, up to 23 screenshot reads, the
fresh-eyes subagent page-checkpoints.md asks for, and the author's own rounds after
clean checks. On the full dashboard workflow, Opus Leaf took 8.9 minutes at main (n=6)
and 9.1 at the branch (n=9). The branch's dashboards wrote a final status such as
"eu-west is rolling back to 4.11" after the user had only decided in 6 of 15 samples,
against 0 of 6 at main (5 of 12 against 0 of 6 for the final branch, Fisher p ≈ 0.11);
removing conversation-loop.md's sentence on how a start ends left it at 1 of 3. The
workflow's last message is "Apply them: update the page so it records them as final",
and authoring-revisions.md asked the record to "say beside it what came of the
choice": of the 21 Opus Leaf dashboard samples, the 3 that read that reference (all on
the branch) were all failed for the overclaim, against 3 of the 18 that didn't. #3959
rewrites the sentence so what a choice sets in motion reads as decided, not under way,
unscored; why branch authors read the reference, and the other 3 cases, are open.

Removing that subagent on the document task (`page-reads-at-every-width`, two runs of
3 per arm) cut 4.3 to 3.3 minutes and $1.39 to $0.92 a page, with 4 against 3 judged
defects the author owned beside the thread chrome's. That judge reads layout and the
supplied facts, not whether a reader can follow the argument, so the result prices
the review rather than showing it adds nothing.

The configuration anchor, restated with same-night HTML controls: Opus Leaf took 9.6
minutes at main (n=5) and 8.1 at the branch with the harness fix below (n=5), against
HTML's 7.3 (n=5); Sol Leaf took 7.8 at main (n=6) and 7.6 at the branch (n=8), against
HTML's 7.1 (n=3), with Leaf's first turns now shorter than HTML's (2.7 against 3.5).
The 2026-10-21 gap (10.3 against 5.5 on Sol) had mostly closed on main before this
campaign.

Until 2026-10-25 the arrangement executor pinned the author's render check to the
fixed 1280×720 window and the browser user first opened the page in the comment
phase, so in the width phase, where the user states a 1600×1000 window, 8 of 12 Opus
Leaf authors hunted for a way to change the check's window (setting
`LEAF_RENDER_VIEWPORT=1600x1000`, grepping Leaf's source). In use the check reads the
user's window. The executor now opens the handed-over page at the run's window and
leaves authors unpinned; earlier width-phase minutes include that hunt.

The driver, analysis scripts and per-cycle log are in the campaign worktree's
`.tmp/overnight/` (`firstturn.py`, `timing.py`, `rounds.py`, `buckets.py`,
`toolsplit.py`, `friction.py`, `authoring-effort.md`).

## Opus page-quality campaign, 2026-10-24

An overnight `/hill-climb-ui` run with fresh Claude Code authors (Opus 5.5) and Sol live
and pair judges, on the arrangement tasks at 1600×1000. The runs named in the two
sections above no longer existed, so every control was authored fresh. Each repair
was compared on its own task against the commit before it (`--base`), then on a
dissimilar task, then against HTML controls through an index of chosen samples, since
`eval-pairs` pairs only the two columns inside its runs.

Retained, in commit order on the campaign branch:

- Playground label choices wrap between whole labels instead of filling equal grid
  cells, which broke "over 1% (today)" across two lines in a half-empty card; one
  author had overridden the cells in page CSS.
- Dashboards and tuning pages keep their working state in the first window
  (`page-authoring.md`, "Composing a page"), and a working-density `main` on a column
  or sidebar page takes the working title and a 28px head. Leaf dashboards authored on
  main were 2667–3390px tall at their first version (median about 3020), with the
  chart, region table or checks below the window; with the change, 1704–1947px
  (median about 1790), with metrics, regions, chart and decision in the window. Pair
  judgments against main: 7 of 8. Configuration first versions fell from
  1804–3332px to 1000–1944px, though both arms reached a fitting page once the user
  stated the window, and the pair judges then split 1 of 4 for the change.
- A panel heading names its region and the panel's first line states its finding. All
  7 Leaf dashboards with panels written without that line had a panel heading over 40
  characters (up to 129, in small capitals); the 2 written with it had none over 20.
- Queue summaries take `--t-working-label` instead of the label size, in an 18rem list.
- An applied playground stays open, authored at the chosen values, as its record
  (`authoring-revisions.md`). Authors given the line did so 7 of 8 times, authors on
  main 0 of 4 (today's values, or the tuner in a disclosure). Judgments against base
  on the first pair of runs: 4 of 4.
- `lf-diff` joins the pieces `@pierre/diffs` 1.6 splits an uneven change into, so a
  rewrite reads deletions above additions in the unified view.

Rejected: a 24em measure for the wide-page title (no visible change on 55–60
character titles), and laying a page out by how its reader uses its parts (patch
review, latency review and a document control: 4 of 10 judgments for the change
against base, 0 of 4 against HTML), and asking for a configuration's items as aligned
rows (every author already wrote rows; base won 4 of 4).

At the end, two fresh samples per task on main and on the campaign branch: the
branch won 17 of 24 judgments against main, 4 of 4 on configuration, dashboard and
queue, 3 of 4 on latency review, 2 of 4 on the document control and 0 of 4 on patch
review, where the judges cited each page's content (which diff it showed, how it
recorded the approval). Two queue judgments named the branch's larger, "more
readable" summaries. Codex authors (Sol 6.1) wrote working-density dashboards,
workspaces and short panel headings on both arms, so the instruction changes moved
nothing there; their configuration and queue pairs went to main 4 of 4 on a browser
user's wrong click and a queue item the branch's author left open. At a 900×600
window (one sample per arm) the branch took 3 of 6: configuration 2 of 2, queue 1 of
2, and dashboard 0 of 2, where main's author wrote a workspace of independently
scrolling columns and the branch's a sidebar page, which the guidance names for a
dashboard. Against the
same HTML controls both arms gave identical winners: Leaf for dashboard, document
and queue, HTML for configuration, latency review and patch review. The HTML
dashboard, queue and document controls each had a decision route that recorded
nothing or lost a decision, which the judges weighed heavily. HTML's remaining
advantages as the judges named them: aligned rows and summary links on configuration
pages, a chart beside all its rows and the plan where Leaf used separate views, and
code at 13.5px beside the decision where Leaf set it at 12px in another part.

Runs and pair indexes are under `.tmp/eval/` in the campaign's worktree,
`leaf.agent-a10f091f355e3a600`; the running log with each cycle's screenshots is
`.tmp/overnight/page-quality.md` there.

## Layouts under revision, 2026-10-24

The backlog item "Test the Layouts on agents"
([#4033](https://github.com/max-sixty/leaf/issues/4033)) asked whether pages hold
when an agent revises them into another shape. Three variants of the complete tasks run the usual author,
width preference, passage comment and browser decision, then send a revision that
changes what the page is for: `document/live-status` turns the review into the page
the team follows during the TTL rollout, `dashboard/write-up` adds the eu-west
write-up to the rollout dashboard, and `queue/hand-off` adds a hand-off for the
support lead to the worked queue. Each keeps its comment thread. `dashboard/cold`
asks a fresh author for "a dashboard" from a pile of mixed material, with a text
rubric for over-tiling and `page_defects.py`'s live judge. The workflow judges saw
1600×1000 and 900×600.

```sh
uv run leaf-dev eval document/live-status dashboard/write-up queue/hand-off dashboard/cold --harness claude-code --viewport desktop --viewport short --repeat 2 -j 2
uv run leaf-dev eval document/live-status dashboard/write-up queue/hand-off dashboard/cold --harness codex --viewport desktop --viewport short --repeat 2 -j 1
```

Main was `f00911ed1`: Opus 5.5 on Claude Code, Sol 6.1 on Codex, Sol judges. A
Claude Code revision sample cost $3.5–4.8 and took 12–21 minutes; a cold dashboard
$0.67–0.73.

### What the revisions did

The shape of each final page, read from its markup, and the live judge's verdict:

| Task        | Harness     | Final page after the revision                                    | Judge  |
| ----------- | ----------- | ---------------------------------------------------------------- | ------ |
| live status | Claude Code | page of parts: status column, review sidebar                     | defect |
| live status | Claude Code | column page with page tabs for status and review                 | defect |
| live status | Codex       | sidebar page, status in the aside                                | pass   |
| live status | Codex       | sidebar page, status in the aside                                | defect |
| write-up    | Claude Code | page of parts: workspace, write-up column                        | defect |
| write-up    | Claude Code | page tabs, each holding a workspace or a column (see below)      | defect |
| write-up    | Codex       | write-up as one more tab inside a workspace pane                 | defect |
| write-up    | Codex       | write-up as a 2×2 grid of prose sections beside the status aside | defect |
| hand-off    | Claude Code | hand-off as the first tab in the queue's side list               | defect |
| hand-off    | Claude Code | hand-off as the first tab in the queue's side list               | pass   |
| hand-off    | Codex       | the workspace body split into page tabs: queue, hand-off         | pass   |
| hand-off    | Codex       | hand-off on a second page, linked by a tokened `127.0.0.1` URL   | none   |

The last sample finished every phase, but the run's scratch cleanup failed with
"Directory not empty", so it was never judged.

Adding a document to a working surface was the revision that broke composition.
`page-authoring.md`, "Composing a page", already says parts of one subject that
each want their own Layout are a page of parts, but only 1 of these 7 judged
dashboard and queue authors built one. (A later run on main, below, built one 3 of 4
times on Claude Code, so this first rate was partly sampling.) The others put the
document where it reads in a slot
sized for the work: a 475px pane, a 618×484 pane at 900×600 holding 4.5 screens,
or a grid of prose tiles. One Claude Code author gave each root page tab a Layout.
`layouts.css` arranges a Layout only on `main`, a child of `main` or a part's
child, so that workspace silently flowed with the page, and the judge found the
event log scrolling the page rather than its pane. Nothing reported it. A scan of
517 saved pages carrying a page Layout (the pages under
`~/.local/state/leaf/pages/` and the eval samples saved in this machine's Leaf
worktrees) found this the only one, so it is not worth a check yet.

Status added to the review composed by Layouts in every sample. The defects there
came from content: both judged Claude Code authors deleted the commented
database-owner ask once Redis was chosen, leaving the thread reporting its passage
gone, and two authors' status ran below the fold or under the floating panel at
900×600. Codex kept the ask in both samples.

The width preference, naming a 1600×1000 and a 900×600 window, turned three of
four dashboards from sidebar pages into three-pane workspaces before any
revision. Every workspace dashboard then drew a judge defect at 900×600: one
author's "Log and checks" pane was 224×173px and held 6.5 of its own heights,
while at 1600×1000 the same page's rollout pane was 65% empty. The 900×600
defects on dashboards that stayed sidebar pages were about the write-up's width or
what the arrival view left out, not cramped panes. This is the likeliest next
target ([#4098](https://github.com/max-sixty/leaf/issues/4098)), and it needs its
own before/after.

### The cold dashboard

None of the four over-tiled (`tiles-hold-peers` 4 of 4). Each put the four
headline figures in equal cells, one also the card networks and two charts, kept
the eight services in one table and listed the incidents with their owners. Claude
Code used `layout-tiles` on a sidebar or column page with 268–454 bytes of page
CSS. Codex rebuilt the frame itself, with 3.5 and
6.8 KB of CSS setting its own grids, colours, font and panel cards, and one page
overriding `main.layout-sidebar`'s tracks. `page_defects.py` found a defect on
every page: on a phone, identifiers broken mid-word in the services table (2
pages), charts and a timeline too small to read (1), a column dropped (1) and two
spans run together (1); at the wider sizes, the services table using 435px of a
995px section (1); and a thread card covering metrics or hiding its message (2).

### Pane readings

`dev/leaf_dev/pane_readings.py` now measures each Leaf-scrolled region of a shown
workspace before a live judge explores, and the judge's task carries the readings.
Across every judged workspace, Tab reached every pane whose content ran past its
box. The panes
Tab never reached neither scrolled nor held a control, or flowed with the page
inside the misplaced workspace. On arrival at 1600×1000 the queue's selected ticket
pane was 73–79% empty, and dashboard panes 38–69%. The readings cover only the
part shown on arrival, so a workspace in a later part goes unmeasured.

### A guidance sentence, tried and dropped

Two wordings in `page-authoring.md`, "Composing a page", were scored and neither
ships. The first, on the parts bullet, said a revision adding a part that wants its
own Layout composes the same way, and named a write-up added to a dashboard and a
hand-off added to a queue. Scored against the first run on main, it built pages of
parts in every revision:

| Arm           | Harness     | Dashboard and queue revisions built as parts | Judge passes |
| ------------- | ----------- | -------------------------------------------- | ------------ |
| main          | Claude Code | 1 of 4                                       | 1 of 4       |
| first wording | Claude Code | 4 of 4                                       | 2 of 4       |
| main          | Codex       | 0 of 3 (and the unjudged second page)        | 1 of 3       |
| first wording | Codex       | 4 of 4                                       | 3 of 4       |

That wording restated the parts bullet for the two cases the evals use, and on Claude
Code it also turned both `document/live-status` revisions into pages of parts, where
a sidebar page fits the status. It was replaced by a goal for the whole list: choose
the arrangement from what the page holds now, on each revision as on the first
version, so content a revision adds takes the form the list gives its kind even when
that changes the page's Layout. That wording was scored with `--base` paired arms:

```sh
uv run leaf-dev eval dashboard/write-up queue/hand-off document/live-status exhibit-playground-stays-in-the-column --harness claude-code --viewport desktop --viewport short --base --repeat 2 -j 2
uv run leaf-dev eval dashboard/write-up queue/hand-off --harness codex --viewport desktop --viewport short --base --repeat 1 -j 1
```

| Arm          | Harness     | Dashboard and queue built as parts | Live status built as parts | Judge passes, all three tasks |
| ------------ | ----------- | ---------------------------------- | -------------------------- | ----------------------------- |
| main         | Claude Code | 3 of 4                             | 1 of 2                     | 3 of 6                        |
| goal wording | Claude Code | 4 of 4                             | 1 of 2                     | 4 of 6                        |
| main         | Codex       | 0 of 1 (the queue sample errored)  | not run                    | 0 of 1                        |
| goal wording | Codex       | 0 of 2                             | not run                    | 1 of 2                        |

Main on Claude Code built parts 3 of 4 times this run, against 1 of 4 in the first,
so the first wording's Claude Code gain was mostly sampling. The goal wording
changes nothing measurable there, and on Codex its authors appended the write-up as
a section of the sidebar page's body and put the hand-off in a workspace tab, as
main does. Only the first wording moved Codex (4 of 4 against 0 of 4 judged on main
across both runs). That suggests, from these few samples, that Codex authors keep
the existing Layout when a revision adds a document unless an instruction names
that case, which is the lead for a later change. The guardrail `exhibit-playground-stays-in-the-column` passed 2 of 2 on both
arms, and the read-only layout probes `parts-take-their-own-layouts`,
`page-arrangement-uses-layouts` and `surface-page-takes-the-window` passed 12 of 12
on both arms with the first wording.

The judges' defects in these runs were mostly not about composition: an arrival
view at 900×600 missing a status line or covered by the floating comment bar, a
hand-off leaving one ticket without a next owner, a write-up omitting Dana's
confirmation, and, on Codex, a queue's ticket pane that would not scroll at 900×600
beside a mostly empty decision column.

### Harness fixes from the runs

The browser user's passage selection picked the contents outline's copy of a
heading, which Leaf echoes from the heading and offers no comment route for, and
the sample failed. `eval_user.py` now selects only words in the page's own reading
(`pageText`, passages.js), the words a comment can anchor to: tab labels and board
column headings stay selectable, and Leaf's chrome and echoed copies don't.

The dashboard comment fell back to a whole-page comment wherever the follow-ups
sat in a tab or a closed disclosure the page didn't show on arrival, since the
scenario's `reveal` names nothing to open. That was 4 of 4 dashboards in the first
run on main and both Codex dashboards with the first wording, while both Claude Code
dashboards with it showed the follow-ups and anchored, so the first wording's Claude
Code cell also differs from main in how the comment arrived. In the paired run all
four Claude Code dashboards anchored, and both Codex dashboards fell back.

Two Codex queue samples, one in each run on main, finished or nearly finished their
phases and then failed in the scratch cleanup with "Directory not empty", so they
were never judged.

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
