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
with few samples; the complete authoring and feedback comparison with plain HTML is
still [#19](workspace-followups.md#item-19).

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
first screen (TODO.md, "Verify the Ask's premise").

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

When a real failure or the #19 comparison supplies a case, state its expected answer
and edit owner before running it, and classify a miss as missing information,
inaccessible information, or information misread.
