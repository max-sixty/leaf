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

| Sink at main                                                                                   | Seen in                                                     | Repair                                                                                                                                                  | After                                                     |
| ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Grepping Leaf's source for how a page script reaches the playground (6–9 calls)                | 3/3 configuration authors, 3/3 on a retry-policy playground | The playground's author instructions show the whole page script (de65d626c)                                                                             | 0/3 and 0/3; configuration first turn 4.4 → 3.5 min (3+3) |
| `name="5xx-threshold"` refused by a leading-letter pattern                                     | 2/3                                                         | Names take ids' pattern (22930f891)                                                                                                                     | gone                                                      |
| `class` or `style` on a playground control refused                                             | 8 and 2 samples                                             | Both are outside every widget schema (a5f9a7865, 80166e8bd)                                                                                             | can't fire                                                |
| `id` on a playground control refused, though page-authoring.md asks for ids                    | 4/4 Codex authors                                           | Controls, choices and presets declare `id` (77f90772f)                                                                                                  | can't fire                                                |
| Per-datum `dy` in lf-chart → NaN, reported only as a console error from Plot's bundle          | 14/17 dashboards                                            | The chart names the mark and option (4c0cc3fa9); its instructions say offsets are one per mark (51624ea6a)                                              | 0/3                                                       |
| squeezed-table advice chased over many render checks, ending in a column hidden at phone width | 7/8 dashboards hid data                                     | The advice says every column stays in reach (9550eecf2)                                                                                                 | 1/15                                                      |
| `stamp --completes <playground>` refused with no fix                                           | 4/4 Codex decision phases                                   | The refusal lists open to-dos and says an answer needs no flag (1696e4877); conversation-loop.md says how a start on the user's update ends (9098577d8) | 2/3 with the message alone, 0/3 with both                 |
| Sticky boxes painted with guessed tokens (`var(--bg)`)                                         | 9/37 pages used an undefined token                          | page-authoring.md states the `--lf-ground` rule (5b39487f6)                                                                                             | 3/3 use it                                                |

On the configuration first turn, main against `3e605af8e`, 5 interleaved authors each:
3.6 against 4.1 minutes, $1.09 against $1.28, 20 against 29 tool calls; main's mean
over all 10 of its first turns tonight was 4.3 minutes. Validation on the full
configuration workflow, main against `51624ea6a`, Opus, 3 per arm: totals 9.0, 9.2, 13.2 against 7.6, 8.5, 9.7 minutes, first turns 4.4, 4.8, 4.4
against 2.8, 3.3, 5.6, cost $3.14 against $2.49 a sample; every final judge passed.
Codex, two runs pooled: first turns 2.7 against 2.5 minutes (n=5 each), all completed
judgments passed. In three Codex runs, 3 of 8 base samples and none of 8 candidates
errored in the harness's comment journey (a 15 s wait for the selection field or a
response); the cause wasn't traced. Dashboard and document first turns didn't get faster; their time
is the record review: render checks, up to 23 screenshot reads, the fresh-eyes subagent
page-checkpoints.md asks for, and the author's own rounds after clean checks.

Removing that subagent on the document task (`page-reads-at-every-width`, two runs of
3 per arm) cut 4.3 to 3.3 minutes and $1.39 to $0.92 a page, with 4 against 3 judged
defects the author owned beside the thread chrome's. That judge reads layout and the
supplied facts, not whether a reader can follow the argument, so the result prices
the review rather than showing it adds nothing.

Until ca736ac63 the arrangement executor pinned the author's render check to the
fixed 1280×720 window and the browser user first opened the page in the comment
phase, so in the width phase, where the user states a 1600×1000 window, 8 of 12 Opus
Leaf authors hunted for a way to change the check's window (setting
`LEAF_RENDER_VIEWPORT=1600x1000`, grepping Leaf's source). In use the check reads the
user's window. The executor now opens the handed-over page at the run's window and
leaves authors unpinned; earlier width-phase minutes include that hunt.

The driver, analysis scripts and per-cycle log are in the campaign worktree's
`.tmp/overnight/` (`firstturn.py`, `timing.py`, `rounds.py`, `buckets.py`,
`toolsplit.py`, `friction.py`, `authoring-effort.md`).

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
