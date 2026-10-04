# Agent usability evals

These experiments measure whether an agent can author, read and revise a Leaf page
without losing the user's decisions or editing the wrong source. The retained results
are dated evidence, not a certification of the current runtime.

## Current observations

### First baseline, 2026-09-27

The original usability harness ran the first executable slice below and three cases of
the inspection comparison, at 387dfed45 with Opus 5.5, three scored runs per case and arm
after one pilot run that fixed each fixture and scorer. Every run's model call
completed. Per-run scores are in [baseline.json](usability-eval/results/baseline.json),
[paired.json](usability-eval/results/paired.json) and
[board.json](usability-eval/results/board.json). The scored runs cost $18.12, and $22.84 with the
pilots.

No run failed a check, so no failure calls for a new reading interface:

| Case | Checks | Result | Cost and input per run |
| --- | --- | --- | --- |
| `cold-report` | skill loaded, page valid, checked, unstamped, no Ask, no sign-off | 3/3 each | $0.33, 192k tokens |
| `cold-decision` | skill loaded, page valid, one Ask with one single-choice group of three options, gesture named, no sign-off | 3/3 each; the Ask held 8, 6 and 8 of the prompt's 8 measurements | $0.48, 349k tokens |
| `near-miss` | skill not loaded, no page | 3/3 | $0.05, 15k tokens |
| `reading` | seven questions, one per surface | 21/21 | $0.16, 100k tokens |
| `resume` | current date, approach and next step; batch size changed where the comment points; pick marked `chosen` and still standing; thread answered; no `restated`; v3 stamped from a valid source | 3/3 each | $0.92, 752k tokens |

Every reply was read by hand. Manual review agreed with the regex scorer on all 21
reading answers and all nine resume answer lines.

What the traces show:

- **The reading runs used page files.** In all five
  `reading` runs (pilots included) the skill never loaded, and every agent answered
  from `index.html`, `events.jsonl` and `data/*.json`, with 11 to 40 KB of tool
  output. That was enough for the external value and, in the four runs whose fixture
  had it, for a pick the user made, replaced, then undid. Resume and revision
  tasks loaded the skill.
- **The missing view state caused no failure.** Asked which tab the user is looking
  at, 3 of 3 agents said the page files don't record it and named the first tab
  only as the default. The fact is missing, not misread: only a browser observation
  could supply it, and no task here needed one.
- **The invalid candidate was read correctly.** All nine resume runs reported the
  active revision's date, named the rejected save and its error, and asked before
  publishing its unexplained date change. Phase 2's "go ahead" answers the question
  only loosely, and 2 of 9 runs took it as consent and published the rejected save's
  date, saying so. That ambiguity limits the consent criterion in this case.
- **Acknowledgement needs the wait.** A resumed page's pending events stay
  unacknowledged until `leaf wait` delivers them, even after the agent has answered
  each one. The headless prompts forbade waiting, so agents reported them as
  pending; in one run the Stop hook made the agent wait and receive them again.
- **Lifecycle varies on the decision page.** One of three `cold-decision` runs
  stamped the page twice; the other two left it unstamped. The headless prompt
  withholds the handoff, so the status and handoff criteria were not measured here;
  the second slice's `handoff` measures them.

### Second slice, 2026-09-27

The same harness added five cases at 64186bcb9, three runs each after pilots that fixed
the fixtures and scorers. In the three live cases the child serves the page from its
own session and the harness plays the user, posting moves through the served page as a
tab does, one round each time a turn ends; the other two are headless. The harness
docstring describes each case. Every run completed. Per-run scores are in
[extension.json](usability-eval/results/extension.json); the scored runs cost $5.71, and $8.76 with the
pilots. Reading the failing runs by hand corrected four scorer patterns that had
failed a correct result: an answer that also named the stale record, `&nbsp;` inside a
duration, a suggestion whose closing tags broke across lines, and a page written by a
script fed through a heredoc. Both batches were rescored with the corrected scorer.

| Case | What the user does | Checks | Cost and input per run |
| --- | --- | --- | --- |
| `handoff` | asks for a drafted page to be handed over, asks for an edit, then asks a question | 54/54 | $0.30, 324k tokens |
| `mixed` | sends a comment, an Ask's pick, a `shorten` reaction, a card move and its undo, and a page error, in one delivery | 41/42 | $0.38, 362k tokens |
| `elided` | asks, in a closed 24-message thread, a question whose premise is in the part the delivery leaves out | 27/27 | $0.43, 408k tokens |
| `package` | asks for a widget that only the page's own package supplies, without naming it | 22/24 | $0.25, 284k tokens |
| `shared-source` | asks about, then updates, one of two worktree widgets whose shared source also holds a look-alike record | 21/24 | $0.54, 309k tokens |

What the traces show:

- **The live loop runs as the references describe.** Every round reached its agent
  through the prompt hook, which confirmed receipt, so no agent ran `leaf wait --ack`
  or invented another acknowledgement. Every turn that took a delivery re-armed the
  wait, ended on a `waiting` status and repeated the URL. The first handoff's status
  named the decision ("Pick how the backfill copy runs: …") in 3 of 3, and each edit
  request was claimed on its thread before the reply.
- **A mixed batch gets each event's treatment.** No run wrote the undone card move
  into the markup, every run fixed the non-global regular expression the page error
  named, and every run answered the pick in markup and stamped it, with `chosen` on
  the option or `settled` on the group. The `shorten` reaction was handled both ways the instructions
  allow: shortened in place and closed, or proposed as an `lf-suggestion` that
  `resolves` it. One run named all four pieces of work in one page-wide status and
  claimed nothing on the comment's thread, so that comment read Picked up rather than
  Working until its reply landed.
- **Elision recovery was not exercised.** Every agent picking up the page read the closed thread
  (`leaf page events`, `leaf thread read` or `events.jsonl`) before serving it, and two
  rewrote the page body to record what the thread had settled, so the question
  reached an agent that already held the premise. All three answered 22:00 UTC. The
  case did not make the agent recover a premise it had lost.
- **Package widgets are used from their entry.** All three found `lf-burn` by listing
  the page registry and wrote `consumed="0.62"` from the entry's fraction rule, valid
  on the first check. Two looked at the widget's source before writing, one in the
  same command that read the entry and one by searching for the package directory;
  all three read it or tried to, to tell the user what the widget draws, which the
  entry does not say. The markup did not need it.
- **The shared-source join is followed, and confirmed in the renderer.** All six
  answers and three updates took finch's record by its widget id, left the look-alike
  `tree-finch-old` and wren's record untouched, and put nothing into the markup. Every
  reading agent also opened `widgets/lf-worktree.js` to confirm the join. None had
  loaded the skill or read the registry at that point, and the element's description
  said only that it "projects the matching record".

Some checks failed, but no run gave a wrong answer, wrote to the wrong place or lost
a user's state. The misses fell into these classes:

- **The unclaimed comment is an instruction miss.** The comment's own `answering` clause
  asks for a claim `--on` its thread, and the other runs made one, though some folded
  the rest of the batch's work into that one claim.
- **The renderer reads on `shared-source` are missing information.** The selection
  rule, a record keyed by the element's id, is stated in the registry's
  `lf-worktree` contract and in the renderer. The element's description, which a
  lookup of the tag returns, says "the matching record".
- **The source reads on `package` have no Leaf owner.** The entry was enough for the
  markup; the agents wanted the widget's rendered words, which the fixture's own
  entry leaves out.

Two fixes were tried as a paired A/B, both arms started together
([ab.json](usability-eval/results/ab.json), $7.11): the base, and a candidate that added to
`conversation-loop.md`, "When to write", that each move in a batch takes its own
claim, and changed the `lf-worktree` description to say it shows "the one record its
source keys by this element's id". `mixed` ran five times per arm and `shared-source`
three. Neither changed the result. Both arms claimed the comment on its thread 5 of 5
times, and both folded the other work into one claim in 2 of 5. The base read the
renderer in 2 of 3 `shared-source` runs and the candidate in 3 of 3, where every
candidate run opened the renderer before the registry, so the new description was
never read first. Both changes were reverted; neither experiment supported a new
reading interface.

## First executable slice

[`leaf_dev.usability_eval`](../dev/leaf_dev/usability_eval.py) owns the case definitions,
fixture builder, controlled trajectories, and semantic scoring. The shared host
interface runs these on Claude Code or Codex and retains each native trace.
Promptfoo owns arms, repetition, concurrency, assertions, and reports. The cases cover:

- Cold authoring and discovery: `cold-report`, `cold-decision`, `near-miss`.
- Reading from different page surfaces: `reading` and `reading-<surface>`, scored
  against `fixtures/reading-answers.json`.
- Continuation and edits to different state owners: `resume`, `constructs`, `board`.
- Live delivery and handoff: `handoff`, `mixed`, `elided`.
- Unfamiliar vocabulary and external data: `package`, `shared-source`.

Active fixtures live in [`evals/usability/fixtures`](../evals/usability/fixtures).
The retained `usability-eval/results/` files document the earlier experiments.

The [catalog](../evals/README.md) also runs document, dashboard and queue authoring
and width revision with actual plain HTML controls. Broader conclusions about the
complete authoring and feedback cycle remain [#19](workspace-followups.md#item-19).

## Running

Run selected whole scenarios through Promptfoo:

```sh
npm ci --prefix evals
uv run leaf-dev eval short-chat-answer reading document/resume
```

The default runs each selected case once against the merge base and working tree.
Each sample includes all resumed phases or live feedback rounds, with a fresh selected-host
session and isolated state. Every declared check stays in the report, including
missing rounds and incomplete phases, which fail instead of disappearing.
Traces and fixture pages stay under `.tmp/eval/`; read the replies alongside
the score, since a regex can reject a correct answer. The retained JSON results above
remain historical evidence, not a second runner.

The `elided` fixture now admits its answered history only after initial handover,
under one append/receipt transaction, so the setup cannot preload the premise. Its
`middle_read` check requires the premise to reach the agent after the new question;
reading it during setup no longer passes as recovery.

## Remaining evaluation gaps

The current cases leave these questions unmeasured:

- General recovery after the agent has lost a long thread's middle. Historical
  `elided` runs preloaded the premise. The current context prevents that preload,
  but the earlier measurements do not establish reliability of the stronger check.
- Reading cost with large data manifests and conflicts beyond the rejected source
  candidate in `resume`.
- Revision after implementation lands: current conclusions and remaining work,
  preserved decisions, and correct treatment of user-owned text.
- Questions that require the user's actual selected tab or visible content. The
  file-only baseline correctly reports that this observation is absent; another
  preview cannot establish the user's view. Add browser observation when a task
  needs it.

Extend the scenario cases when a real failure or the #19 comparison supplies a useful case.
State the expected answer and edit owner before running it. Compare correctness and
context cost, and classify a miss as missing information, inaccessible information
or information misread. The measured results below do not call for another page
reading interface.

## Inspection comparison, 2026-09-27

Paired runs compared the payload at 387dfed45, whose `page state` carried a
construction tree, with a candidate that read the active HTML beside compact state.
Both arms started together, with three scored runs each. No browser-observation arm
was tested. The cases were `resume` and `constructs`, a page with a
draft the user rewrote, a figure stated at one measurement whose source has since
run again, and a chart. `constructs` asks what each says, then for three changes
whose owners differ: a date inside the user's draft (their words kept, `restated`),
the figure (text and `at` from the latest measurement, source untouched) and a chart
value (its CSV). `board` covers the one join the tree made that the compact state
leaves to the reader: the user moved two cards into a column at ranks between the
authored cards and moved a third, then undid that move. It asks for the column's order,
then for a card added to another column, which obliges the version to write the moved
cards where the fold puts them. The shared-source record case came later, in the
second slice.

| Case | Arm | Checks passed | `page state` bytes read per run | Cost per run |
| --- | --- | --- | --- | --- |
| `constructs` | tree | 33/33 | 13,151 | $0.63 |
| `constructs` | without tree | 33/33 | 7,426 | $0.55 |
| `resume` | tree | 33/33 | 8,006 | $0.81 |
| `resume` | without tree | 33/33 | 8,385 | $0.97 |
| `board` | tree | 24/24 | 5,865 | $0.57 |
| `board` | without tree | 24/24 | 6,368 | $0.55 |

Every failure class is empty, so the arms tie on correctness; without the tree,
agents ordered the cards from the ranks in `state` themselves. Agents in the tree
arm often filtered the tree out themselves (`jq 'del(.content)'`), which is why
their `page state` reads are close on `resume`. Unfiltered, the tree is most of the
output: without it `page state` shrinks from 24,422 to 4,755 bytes on the reading
fixture, 11,625 to 4,197 on `constructs`, 58,528 to 4,117 on `review-a-plan` and
122,280 to 10,360 on `command-hub`, where the page's own HTML is 13,814 bytes. Total
input tokens per run do not separate the arms; the references a run reads dominate
them.

HTML plus compact state matched the expanded tree on correctness with smaller
state output. The change removed the page-level tree; a thread retains its
construction reading because its frozen markup has no separate HTML file.

The change itself then ran against its base, both arms built from their refs and
started together, three scored runs of `resume`, `constructs` and `board` each
([change.json](usability-eval/results/change.json), $12.55). Both passed all 90 checks.
