# Agent usability evals

What earlier eval runs found about agents authoring, reading and revising Leaf pages,
and what remains unmeasured. The runs used harnesses the catalog has since absorbed
(`evals/README.md`); their scenarios survive as the `usability_eval` and
`arrangement_eval` executors. The per-run results were under
`notes/usability-eval/results/` and `notes/arrangement-eval/results/` until this
note was condensed; `git log --` on those paths finds them. The findings through
2026-10-12, which have landed, are in Git history; `d91b67b26` is the last commit
holding them.

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
  0.95 and 0.93, and a fifth contact called the fourth. The judge is a Codex model and no
  second judge read the pages, so the gap between Claude Code's 17 of 19 and Codex's
  0 of 18 is unconfirmed. Codex pages restated the supplied facts more nearly word
  for word, and Claude Code pages added derived claims; the "half of eu-west's
  checkouts" claim appeared on 5 of 6 Claude Code dashboards.
- The 3 render-reported defects match the check messages the matching turn quoted.
  A second matching turn, given each check's whole output and each tool call whole
  where the first had cut them, read 65 of the 66 defects the same way; it found that
  the author of the faint labels had changed them after a check reported them shrunk.
  The other readings were not checked by hand.

The overlap from a playground followed by a note came from `lf-ask`: its full-height
rule gave every child the height signal, so a playground that was not the last child
shrank below the floors of its rows and drew past its own box. The fix holds the
context at its own height. The three configuration pages authored after it have no
such overlap, including one with a note after its playground;
`test_a_playground_followed_by_a_note_keeps_its_instruction_off_the_note` holds it.

Both queue pages where the judge commented on an item and cleared its answer showed
"1 of 8 to answer" beside a disabled Next on me: the comment hands the item to the
agent (`obligations.discussed`), and `lf-tally` counted every open obligation as to
answer. Reproduced on a three-item queue, the tally now splits the open ones by next
actor ("1 of 3 on Claude"), and
`test_a_tally_counts_its_regions_obligations_and_walks_them` holds it.

The other recurring Leaf-owned defects follow from recorded choices, and are open
decisions rather than fixes:

- A thread card opens over the text near its passage, which Escape uncovers (root
  `AGENTS.md`, "Working on the repository"); the judge counted it on 14 pages.
- On a phone a thread's pin stands over the end of the line it marks (5 pages).
- A playground in a workspace keeps its stage bounded down to 500px tall, which
  `test_inline_playground_keeps_evidence_and_long_instruction_reachable_in_a_short_workspace`
  pins; at 900×700 the judge found the stage too short on 4 of 9 configuration
  pages.

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
