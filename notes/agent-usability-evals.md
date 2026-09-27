# Agent usability evals

This is an initial test plan, not a product contract. Leaf has two users: the
person looking at the rendered page and the agent authoring or continuing it. A
page succeeds only when both can recover the same meaning.

## Current observations

### First baseline, 2026-09-27

`usability-eval/harness.py` ran the first executable slice below and three cases of
the next paired check, at 387dfed45 with Opus 5.5, three scored runs per case and arm
after one pilot run that fixed each fixture and scorer. Every run's model call
completed. Per-run scores are in `usability-eval/results/`: `baseline.json`,
`paired.json` and `board.json`. The scored runs cost $18.12, and $22.84 with the
pilots.

No run failed a check, so no failure calls for a new reading interface:

| Case | Checks | Result | Cost and input per run |
| --- | --- | --- | --- |
| `cold-report` | skill loaded, page valid, checked, unstamped, no Ask, no sign-off | 3/3 each | $0.33, 192k tokens |
| `cold-decision` | skill loaded, page valid, one Ask with one single-choice group of three options, gesture named, no sign-off | 3/3 each; the Ask held 8, 6 and 8 of the prompt's 8 measurements | $0.48, 349k tokens |
| `near-miss` | skill not loaded, no page | 3/3 | $0.05, 15k tokens |
| `reading` | seven questions, one per surface | 21/21 | $0.16, 100k tokens |
| `resume` | current date, approach and next step; batch size changed where the comment points; pick marked `chosen` and still standing; thread answered; no `restated`; v3 stamped from a valid source | 3/3 each | $0.92, 752k tokens |

Every reply was also read by hand, and agreed with the regex scorer on all 21 reading
answers and all nine resume answer lines.

What the traces show:

- **Nobody reads `page state` to answer a question about a page.** In all five
  `reading` runs (pilots included) the skill never loaded, and every agent answered
  from `index.html`, `events.jsonl` and `data/*.json`, with 11 to 40 KB of tool
  output. That was enough for the external value and, in the four runs whose fixture
  had it, for a pick the user made, replaced, then undid. The skill loads once the task is to resume or revise a page.
- **The missing view state caused no failure.** Asked which tab the user is looking
  at, 3 of 3 agents said the page files don't record it and named the first tab
  only as the default. The fact is missing, not misread: only a browser observation
  could supply it, and no task here needed one.
- **The invalid candidate was read correctly.** All nine resume runs reported the
  active revision's date, named the rejected save and its error, and asked before
  publishing its unexplained date change. Phase 2's "go ahead" answers the question
  only loosely, and 2 of 9 runs took it as consent and published the rejected save's
  date, saying so; a later run should ask for the revision without that ambiguity.
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
`usability-eval/results/extension.json`; the scored runs cost $5.71, and $8.76 with the
pilots.

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
  wait, ended on a `waiting` status and repeated the URL. The first handoff's status named the
  decision ("Pick how the backfill copy runs: …") in 3 of 3, and each edit request
  was claimed on its thread before the reply.
- **A mixed batch gets each event's treatment.** No run wrote the undone card move
  into the markup, every run fixed the non-global regular expression the page error
  named, and every run answered the pick in markup and stamped it, with `chosen` on the option or
  `settled` on the group. The `shorten` reaction was handled both ways the guidance
  allows: shortened in place and closed, or proposed as an `lf-suggestion` that
  `resolves` it. One run named all four pieces of work in one page-wide status and
  claimed nothing on the comment's thread, so that comment read Picked up rather than
  Working until its reply landed.
- **The elision never bound.** Every agent picking up the page read the closed thread
  (`leaf events`, `leaf thread read` or `events.jsonl`) before serving it, and two
  rewrote the page body to record what the thread had settled, so the question
  reached an agent that already held the premise. All three answered 22:00 UTC. The
  delivery's `elided` count and `leaf thread read` serve an agent that has lost the
  middle, as a compacted session has; this harness cannot produce one.
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

Three checks failed, and no run gave a wrong answer, wrote to the wrong place or lost
a user's state. Classified:

- **The unclaimed comment is a guidance miss.** The comment's own `answering` clause
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
(`results/ab.json`, $7.11): the base, and a candidate that added to
`conversation-loop.md`, "When to write", that each move in a batch takes its own
claim, and changed the `lf-worktree` description to say it shows "the one record its
source keys by this element's id". `mixed` ran five times per arm and `shared-source`
three. Neither changed the result. Both arms claimed the comment on its thread 5 of 5
times, and both folded the other work into one claim in 2 of 5. The base read the
renderer in 2 of 3 `shared-source` runs and the candidate in 3 of 3, where every
candidate run opened the renderer before the registry, so the new description was
never read first. Both changes were reverted, and the evidence calls for no new
interface: the join is followed correctly, as the "Measured reading gaps" section
below asked to establish before adding one.

The former `leaf page catalog` output was 92,130 bytes, 13,058 words, or about
22,500 tokens under both `o200k_base` and `cl100k_base`. Before selective
registry reading and phase-specific references, an agent also read the roughly
1,400-token skill, 3,100-token authoring reference, and 3,800-token thread
reference. That made the required path about 30,800 tokens before the user's
material or the page itself.

At the initial phase split, the cold path read the skill, the core authoring
reference, the handoff reference, and exactly one host contract. In Codex that
was 390 lines and 2,934 words; in Claude Code it was 398 lines and 2,991 words,
before the selected registry entries. Decision authoring added 48 lines, live
revision rules 57, and evidence authoring 75, each loaded only in its relevant
phase. These historical counts measure context shape rather than success rates;
the construction-linked inspection guidance has since changed the references.

Three context-blind, paired walkthroughs exercised a quick informational page, a
finished decision record, and a mixed-event continuation against the former and
split layouts. Both layouts produced the same correct lifecycle choices. The
Codex informational path fell from 6,222 to 2,934 words; the decision path fell
to 4,295 words. The mixed-event split initially caused one agent to load the
first-handoff and new-decision references again, which led to grouping the
router by operating phase and narrowing those triggers. These are small
qualitative walkthroughs, not a substitute for the executable cases below.

The former catalog combined three kinds of information:

- page-authoring facts: available shapes, attributes, content rules, idioms, and
  examples;
- package-authoring facts: registry extension keys and their contracts;
- machine-facing declarations: each widget's JSON Schema for authored
  attributes, its full `x-*` behavior declarations, and layer-wide contract
  facts for state, reports, and decisions.

Only the first belongs in every page-authoring turn. Loading the whole file may
be truncated before the agent reaches the entry it needs. Even when it fits,
unrelated declarations compete with the page's subject for attention.

An agent inspects an existing page by reading `leaf page state` beside the active
revision's HTML: `state` lists the user's standing moves over that HTML,
`data_bindings` and `data/` hold external values, and `source` keeps an invalid
candidate distinct from the live revision. User decisions survive without being
copied into source. The owning contract is `skills/leaf/scripts/leaf/page-storage.md`.
`page state` used to carry a construction tree of the whole document; it went after
the paired run below, and `leaf thread read` keeps that reading for a thread's frozen
markup.

A context-blind continuation check changed one sentence in a copied feature
gallery using the public CLI and authoring references. It correctly reported the
selected Trail map, exact two-line draft, and card's first position in Tried.
The resulting source diff contained only the requested sentence replacement;
standing user state and raw data were unchanged. This checks one successful
edit route, not a paired comparison or a general comprehension score.

Long threads add a smaller version of the same problem. A delivered batch
may elide the middle of a thread. An agent that no longer holds that middle has to
notice the `elided` count and read the thread with `leaf thread read` before
answering a question that depends on the missing records. In the second slice every
agent that picked a page up read the whole thread first, so the elision never bound.

## Canonical agent access

Keep Leaf's agent-facing surface small and semantic:

- `leaf page state PAGE` reads the active revision, source and data revisions,
  standing actions and reports, decisions, requests, reactions, compact thread
  state, and an event-log watermark; the document itself is the HTML `active.file`
  names;
- `leaf thread read PAGE THREAD` selects one thread's current messages and effective
  frozen markup; its edits continue that thread;
- `leaf page guidance PAGE [AUDIENCE]` composes explicit operating guidance;
- `leaf events PAGE [--after SEQ] [--thread THREAD]` prints the append-only JSONL
  history admitted at validated write boundaries; `--after` is a sequence cursor
  and `--thread` is one exact semantic identity lookup;
- `active.file` names the readable canonical HTML when a valid revision exists,
  `source.file` names the mutable author target, `data.file` is always readable,
  and `registry.json` remains the canonical vocabulary.

Leaf should own joins whose meaning depends on event kind, authored structure,
or the registry. Agents should use `jq`, `rg`, and normal file reads to select
records and fields. Do not add general include/exclude fields, projections,
profiles, or a Leaf-specific filtering language. Exact identity lookup and the
sequence cursor are the useful low-cardinality exceptions.

## Selective registry reading

The page's vendored `registry.json` is the one vocabulary source. There is no
second author index and no command that reformats the whole registry into prose.
The authoring reference has agents list the registry's keys, then ask the same file
for the complete entries they need:

```sh
registry="PAGE/registry.json"
jq 'keys' "$registry"
jq '{"lf-chart": .["lf-chart"], "$series": .["$series"]}' "$registry"
```

The key list against a page with the current default registry is 671 bytes. An exact
lookup carries the widget's purpose and instructions in its `description`, plus its
constraints, example, and relevant contracts without loading unrelated entries.
Custom package tags and `$` facts join the same flat namespace and therefore appear
without Leaf knowing their names in advance. `leaf page guidance` remains separate
because it composes instructions for a named operating audience rather than
declaring the vocabulary.

## What the evals should measure

Run each case in a fresh session with the installed Leaf payload, an isolated
page directory, and no prior explanation. Capture the agent's command trace,
CLI output delivered to the model, resulting files and events, elapsed turns,
and token use.

Score each outcome independently rather than treating the whole session as one
pass or inspecting instruction wording:

- the skill is discovered when appropriate and stays quiet on a near-miss;
- the authored page passes the required validation and uses the intended
  lifecycle;
- every factual answer matches the page's current canonical state;
- standing user decisions and stable anchors survive a revision;
- every delivered event is handled once and the page ends in the right status;
- an unfamiliar package widget is used from its declarations rather than from a
  guessed tag contract;
- failures lead to the documented recovery path.

Keep context cost beside correctness. A design that reaches the right result by
loading the whole registry, every revision, and the whole event log has not
solved the agent experience.

## Candidate cases

| Case | Fixture or request | Binary criteria |
| --- | --- | --- |
| Cold informational page | A short report with three sections and no decision | Leaf triggers; the page validates; the default table of contents is present; the first handoff is unstamped; the status has no invented decision. |
| Discovery guardrail | A normal request for a concise answer that does not ask for a page or shared review | Leaf does not trigger and no page directory or server is created. |
| Cold decision page | Evidence and three mutually exclusive choices | One visible Decision contains the evidence and an `lf-options` control; the handoff says what gesture answers it; no duplicate sign-off is invented. |
| Unfamiliar package | A fixture adds a widget whose name and contract are absent from the base package | The agent discovers it in the page's registry, retrieves its entry, and authors valid markup without reading package source. |
| Reading parity | Facts are distributed across prose, a disclosure, an inactive tab, a chart, projected data, and a user-selected option | The agent answers a fixed question set from the current reading with no omissions or stale values. |
| Competing authorities | `index.html` conflicts with the last valid revision; a standing action also overrides authored state | The agent identifies what the person currently sees and does not report the rejected source or superseded authored state as current. |
| Resume a foreign page | Several versions, open and resolved threads, user overrides, and updated external data | The agent gives the current conclusion, open work, and next required action without treating the event log as a transcript to retell. |
| Read then revise | Plain prose, a user-owned draft, live data, and a pinned capture | The agent changes the correct construction input, preserves user authority, and rebinds a fresh capture when changing pinned data. |
| Work lands on a handed-over page | A plan, a list of problems found, or a refuted finding, with a user's pick standing, a milestone rail whose next step is now done, prose the user has seen that would read better at half the length, a user-owned draft holding a fact the work moved, and a task line that only asks to note what merged | The title and headings state the present; finished items sit in a collapsed section rather than marked done in the open list; the answered Ask moves there under the words it was picked under and what remains is a new Ask; the rail keeps its done members; the shorter prose is put to the user as an `lf-suggestion` with the current words verbatim in `lf-old`; the draft's moved fact is written into the draft's body with `restated` on the draft, and no suggestion wraps it. |
| Revise after feedback | A comment changes prose beside an already chosen option | The comment is answered; the prose changes; surviving ids and the choice remain; `restated` appears only if the agent deliberately replaces the decision. |
| Elided thread | The decisive premise is in the elided middle of a long thread | The agent uses the thread id to select its raw events before replying and answers from the missing premise. |
| Mixed event batch | A comment, action, reaction, undo, and page error arrive together | Each event receives its defined treatment; the withdrawn gesture is not carried; acknowledgement advances only after the complete batch is available. |

## First executable slice

`usability-eval/harness.py` runs this slice; its docstring records the runner, model,
fixture builder, trace format, arm isolation, answer normalization and retention
choices. The first baseline is under "Current observations".

1. **Cold authoring** (`cold-report`, `cold-decision`, `near-miss`). An
   informational request, a decision request with evidence and three exclusive
   choices, and a near-miss ("explain the difference between…") that should get an
   ordinary chat answer. None names Leaf, so the cases measure discovery precision
   as well as recall. The full-registry arm is gone with `leaf page catalog`, so
   these run on one arm.
2. **Reading parity** (`reading`). One page with seven facts: plain HTML, collapsed
   HTML, an inactive tab, chart data, external data, a standing pick the user
   replaced and then undid, and which tab the user is looking at, which no page file
   records. `usability-eval/fixtures/reading-answers.json` is the checked answer
   file. `reading-<surface>` cuts the page down to one surface, to isolate a failure
   the combined page shows.
3. **Resume** (`resume`). A page directory with two stamped versions, an invalid
   `index.html` candidate that changes a date, a resolved and an open thread, and a
   pick no markup records. Phase 1 asks for the current truth and the next action;
   phase 2 asks for the revision.
4. **The live loop** (`handoff`, `mixed`, `elided`). The child serves the page and
   waits; the harness posts the user's moves through the served page and scores each
   delivered round. Results are under "Second slice".
5. **Unfamiliar vocabulary and shared data** (`package`, `shared-source`), headless.

`arrangement-eval/` is the other authoring case: fresh agents write three subjects
with and without Leaf's arrangement vocabulary, revise each for a standing
preference, and a blind reviewer compares screenshots at three widths.

Not yet covered: competing authorities beyond the invalid candidate, and a session
that has lost a long thread's middle, which only a compacted session can.

## Evaluate the integrated inspection path

The first paired run below compared the HTML-plus-state path with the
construction-linked tree on the same reading and revision tasks, scoring mutations as
well as answers: a user who understands a value but edits a derived display has not
recovered its construction. Context cost with large data manifests is still
unmeasured.

A browser or accessibility snapshot can check the oracle for rendered semantics.
It omits some inactive content and includes generated presentation, so keep it as
evaluation evidence rather than another page authority. Extend shared construction
semantics only where failures identify a missing fact; custom-renderer limits
should remain explicit.

### Measured reading gaps

The feature-gallery tree inspected on 2026-09-04 was 184,247 bytes formatted
against 26,732 bytes of source HTML; repeated structure and edit metadata, not the
page's 13,925 bytes of text, made up most of it.

A separate browser context established a visibility gap:

| Selected tab | Visible sentence | Construction content | Event sequence |
| --- | --- | --- | --- |
| Current | The current sample route is under review. | Identical | 23 |
| Context | The earlier route crossed the courtyard. | Identical | 23 |

The tabs keep their selection locally; source and the event log cannot supply
that observation. Closed disclosures and responsive visibility make the same
distinction relevant elsewhere. The active HTML holds every tab's content, while
questions about the current screen need browser observation.
That observation must come from the user's actual browser state or an explicit
capture of it: opening another preview can select a different tab and cannot
establish what the user sees.
Keep the observed element ids, projected-record labels, and `data-lf-origin`
addresses beside rendered content so that seeing a value also identifies its
construction. Reuse those existing declarations instead of adding a separate
widget-summary implementation.

A shared-source discriminator used two `lf-worktree` widgets and an unrelated
third record, listed first and resembling one widget's record. The browser
rendered the correct records and stamped their exact paths. The former tree
repeated all three records under each widget with `path: []`; the registry contract
states that records are selected by authored widget id, and the value file keys each
record by that id, so the edit target is recoverable without reading widget source.
This is an indirect join, not missing semantics or a wrong-target ambiguity. The
second slice's `shared-source` case tested whether cold agents follow it: they did in
every run, confirming it in the renderer's code, so it needs no further abstraction; do
not duplicate the renderer in Python.

### Next paired check

Use isolated copies of the same page and fixed tasks under three conditions:
active HTML plus the compact state indexes; construction plus HTML; construction
plus HTML and browser observation. Keep model settings and tool access equal
apart from the information being compared.

Cover a user-owned draft overriding source, live versus pinned data, the
shared-source record case, a chart or diagram referent, and locally selected
versus hidden content. State the expected answer and mutation target before
running each case. Check factual answers, the chosen edit owner, preservation of
user state, and actual context usage. Do not score visual resemblance or the
number of JSON lines as comprehension.

First classify each failure: missing information, inaccessible information, or
information the agent misread. Missing view state calls for browser observation;
an incorrect record selection calls for a construction link; repeated metadata
calls for a smaller reading. A concise prose rendering is warranted only when
the remaining failures show a benefit over these simpler changes. If HTML plus
compact state performs as well as the expanded tree at lower context cost,
remove the redundant tree output rather than preserving it as another default.

#### First paired run, 2026-09-27

Two of the three conditions ran, paired and started together, three scored runs each:
the shipped arm, whose `page state` carries the `content` tree, and an arm built by
`harness.py arm --without-tree`, whose `page state` drops `content` and whose
references read the active HTML beside the compact state. No browser-observation
condition exists to run. The cases were `resume` and `constructs`, a page with a
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

HTML plus compact state performed as well as the expanded tree at lower context
cost, so the condition above held and the page-level tree went: `page state` no
longer carries `content`, and the references read the active HTML beside `state`.
`leaf thread read` keeps its construction reading, since a thread's frozen markup has
no HTML file to read instead.

The change itself then ran against its base, both arms built from their refs and
started together, three scored runs of `resume`, `constructs` and `board` each
(`results/change.json`, $12.55). Both passed all 90 checks.
