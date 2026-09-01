# Agent usability evals

This is an initial test plan, not a product contract. Leaf has two readers: the
person looking at the rendered page and the agent authoring or continuing it. A
page succeeds only when both can recover the same meaning.

## Current observations

The former `leaf page catalog` output was 92,130 bytes, 13,058 words, or about
22,500 tokens under both `o200k_base` and `cl100k_base`. Before selective
registry reading and phase-specific references, an agent also read the roughly
1,400-token skill, 3,100-token authoring reference, and 3,800-token conversation
reference. That made the required path about 30,800 tokens before the user's
material or the page itself.

The current cold path reads the skill, the core authoring reference, the handoff
reference, and exactly one host contract. In Codex that is 390 lines and 2,934
words; in Claude Code it is 398 lines and 2,991 words, before the selected
registry entries. Decision authoring adds 48 lines when the page authors a new,
unanswered ask or sign-off. Live revision rules add 57 lines only after a page
has been handed over, or when a page proposes wording or carries reader state. Evidence
authoring adds 75 lines only when the page uses measured, visual, source, or
media evidence. Event, thread, and ending contracts load only after those phases
begin. These counts measure context shape rather than broad success rates.

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

Understanding an existing page also requires a join. Authored words live in the
active HTML revision, standing decisions live in the event projection, and
replaceable inputs live in `data.json`. `leaf page state` exposes the semantic
projection and points at the exact active revision and data-file revision, but it
does not present the page's current words with those facts applied. A successor
has to discover and perform that join correctly. Invalid mutable source adds
another distinction: the live page remains on the last valid revision while
`index.html` contains the rejected candidate.

Long conversations add a smaller version of the same problem. A delivered batch
may elide the middle of a thread. The agent has to notice the marker, use the
thread id from `page state`, and retrieve `leaf events --thread ID` before
answering a question that depends on the missing records.

## Canonical agent access

Keep Leaf's agent-facing surface small and semantic:

- `leaf page state PAGE` computes the current semantic index: active source and
  data revisions, standing actions and reports, decisions, requests, reactions,
  current thread state, and the event-log watermark folded into the snapshot;
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
- standing reader decisions and stable anchors survive a revision;
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
| Reading parity | Facts are distributed across prose, a disclosure, an inactive tab, a chart, projected data, and a reader-selected option | The agent answers a fixed question set from the current reading with no omissions or stale values. |
| Competing authorities | `index.html` conflicts with the last valid revision; a standing action also overrides authored state | The agent identifies what the person currently sees and does not report the rejected source or superseded authored state as current. |
| Resume a foreign page | Several versions, open and resolved threads, record lag, and updated external data | The agent gives the current conclusion, open work, and next required action without treating the event log as a transcript to retell. |
| Revise after feedback | A comment changes prose beside an already chosen option | The comment is answered; the prose changes; surviving ids and the choice remain; `restated` appears only if the agent deliberately replaces the decision. |
| Elided conversation | The decisive premise is in the elided middle of a long thread | The agent uses the thread id to select its raw events before replying and answers from the missing premise. |
| Mixed event batch | A comment, action, reaction, undo, and page error arrive together | Each event receives its defined treatment; the withdrawn gesture is not carried; acknowledgement advances only after the complete batch is available. |

## First executable slice

Start with three fixture families:

1. **Cold authoring.** Run the informational and decision prompts against a
   full-registry arm and a selective-registry arm. This tests discovery,
   valid output, lifecycle choice, and context cost. Add one near-miss prompt
   that should receive an ordinary chat answer without creating a page, so the
   slice measures discovery precision as well as recall.
2. **Reading parity.** Build one page with six facts, each represented through a
   different surface: plain HTML, collapsed HTML, an inactive tab, widget data,
   external data, and standing action state. Ask one direct question per fact and
   score each answer against a checked answer file. Keep single-surface versions
   of the fixture so a failure in the combined page can be isolated.
3. **Resume.** Give the agent only a page directory containing version history,
   one invalid source candidate, two threads, and one unrecorded standing choice.
   Ask for the current truth and the next action. Score the answer and the files
   it reads.

`ask-placement-eval/` is one authoring case already runnable: it pastes two
wordings of the ask guidance into a prompt with three subjects and scores where
each ask lands.

Pair and interleave the authoring arms with the same model and settings. Count a
run only when the model call completes. The first run of each case is for fixing
the fixture and scorer; retain a case only after its expected answer is
unambiguous.

Both authoring arms and the comprehension fixtures can establish a baseline now.
Before automating the slice, choose the agent runner and host, model settings,
fixture builder, trace format, arm isolation, answer normalization, and
result-retention policy.

## Near-term usability TODO

Design a coherent set of optional authoring defaults that `version check` can
offer as non-blocking advice rather than adding one-off hints. The first case is
a page with two or more section headings and no `lf-toc`: recommend a table of
contents while leaving an author free to omit it when the outline is already
visible. Keep the advice structural and deterministic rather than attempting to
judge prose quality.

## Possible supporting interface after the baseline

Selective registry access addresses creation. Existing-page comprehension may
need a separate derived reading, for example `leaf page read PAGE`: a compact,
hierarchical text projection of the reader-accessible words, widget meanings,
standing decisions, external values, threads, open decisions, version identity, and
source diagnostics. It would be emitted on demand from the same document, log,
data, and registry authorities, not stored as another current-state file. It
would include collapsed and inactive content with labels rather than hiding it,
and it would state when invalid source is not live.

Do not build that command until the reading-parity and resume baselines establish
that agents fail with today's HTML-plus-state path. Those failures would show
which joins a deterministic view should own. A browser or accessibility snapshot
can help check the eval oracle, but it omits some inactive content and includes
generated presentation, so it should not become another page authority.
