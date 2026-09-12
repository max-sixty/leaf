# Agent-driven UI quality options

This note records options for combining the quality acceptance policy and discovery
allocation work previously called **#1** and **#5**. It is an options document, not a
product contract. Delete it once the operating model has been tried and its surviving
rules have moved into the skills and tests that own them.

The goal is to let agents repeatedly find and repair consequential reader-facing
problems without building a Leaf-specific QA application or maintaining an exhaustive
inventory of pages, controls, states, viewports, and failure modes.

## Constraints

The operating model should:

- exercise real rendered controls through ordinary reader gestures;
- judge complete reader tasks, including interruption, recovery, and return paths;
- let the agent derive experiments from the current product and code rather than from a
  centrally maintained checklist;
- repair clear defects in the same run and add a regression at the lowest useful
  boundary;
- use an independent pass for discoverability and rendered acceptance;
- distinguish a transition that was not reached from one that passed;
- leave enough history to vary later sweeps without creating another issue tracker;
- stop when the remaining work is low-yield or requires product intent; and
- keep exact, repetitive evidence collection in tools while leaving mission selection,
  visual coherence, and architectural ownership to agent judgment.

It should not optimize the number of findings, screenshots, tests, pages visited, or
matrix cells covered. Those measures can improve while the reader experience does not.

## Established operating patterns

### Chartered exploratory testing

Session-based exploratory testing gives a tester a short mission, lets execution and
evaluation evolve as the tester learns, bounds the investigation, and retains a compact
record. A charter names a reader goal and risk rather than prescribing steps or expected
bugs. This is the closest established model for a standing UI sweep. See the
[GOV.UK exploratory-testing guidance](https://www.gov.uk/service-manual/technology/exploratory-testing),
[Martin Fowler's summary](https://martinfowler.com/bliki/ExploratoryTesting.html), and
[the original session-based test-management paper](https://www.satisfice.com/download/session-based-test-management).

Risk-based and additional-coverage prioritization provide a way to choose the next
mission without enumerating the domain. Recent changes, escaped defects, shared
ownership boundaries, important reader tasks, and contrast with recent missions are
inputs to the decision. The
[ISTQB Foundation syllabus](https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf)
also warns that checklists decay, grow too long, and must change with defect history.

### Outcome-based agent evaluation

Agent runs should be judged from the resulting environment and reader outcome, not a
required tool-call sequence. Real failures and existing manual checks supply useful
calibration cases; traces show whether the evaluator is measuring the intended behavior.
See
[Anthropic's agent-evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

The agent that produced a change should not be its only evaluator. Anthropic's
application-development experiments found that agents often rationalized mediocre work
they had produced; a separate evaluator was one of the strongest improvements. See
[Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps).

### Graduation into deterministic tests

Open-ended agent exploration is useful while the question or interface is changing. A
stable discovered contract belongs in a deterministic test. The exploratory agent
continues looking for unknown problems rather than spending model calls repeatedly
proving a settled path.

Playwright already retains actions, DOM snapshots, screenshots, console output, network
activity, and environment metadata. Failure-only traces plus Leaf's event and server
logs cover the evidence need without a separate recorder. See the
[Playwright Trace Viewer](https://playwright.dev/docs/trace-viewer).

## Available skills in the current development environment

Leaf's `/ui-sweep` already contains most of the required workflow. The other skills in
this section are available in the current maintainer environment but do not ship with
Leaf; this note treats their methods as options rather than introducing project
dependencies on them.

- `/ui-sweep` starts with a cold reading, derives experiments from reader tasks and
  ownership relationships, uses real input, compares with the merge base, fixes
  reproduced defects, checks a sibling case, and requires an independent reviewer.
- `/iteration:norman` gives a context-blind agent a neutral task and observes whether it
  can discover and complete it without being taught the interface.
- `/review` supplies a separate acceptance pass after the repair.
- `/playwright-cli:playwright-cli` supplies persistent real-browser interaction and
  evidence collection.
- `/iteration:iterate` can drive a concrete repair through repeated edit, browser, test,
  and review cycles. It is too heavy to be the standing scheduler.
- `/iteration:fisher` can reduce a calibration corpus to one representative miss and
  one discriminating neighbor per claim.
- `/iteration:goodhart` can check whether mission selection or reporting has become a
  target instead of evidence of reader quality.
- `/frontend-design:frontend-design` can guide a genuine visual redesign. It should not
  become the sweep's permanent list of aesthetic criteria.

Only the first three are necessary to define the operating model. The others are
conditional tools, not stages every run must execute.

## Public skills and systems

This is a snapshot of relevant public work as of 2026-09-11. The useful unit is the
behavior each skill contributes; adopting a repository wholesale also adopts its
dependencies, reporting conventions, and maintenance assumptions.

### Vercel `agent-browser` dogfood

[The dogfood skill](https://github.com/vercel-labs/agent-browser/blob/main/skill-data/dogfood/SKILL.md)
drives an application as a user, explores workflows, and captures reproducible findings
with screenshots and videos. It is the strongest public example of an autonomous defect
finder.

Its default workflow is report-oriented: map the application, consult an
[issue taxonomy and exploration checklist](https://github.com/vercel-labs/agent-browser/blob/main/skill-data/dogfood/references/issue-taxonomy.md),
and preserve media for every issue. It deliberately forbids reading source. Those choices
make it useful as a cold evaluator but a poor owner of Leaf's source-informed repair loop.

### `frontend-visual-qa`

[The frontend visual QA skill](https://github.com/daymade/claude-code-skills/blob/main/frontend-visual-qa/SKILL.md)
has unusually strong treatment of rendered evidence, conditional states, responsive
behavior, information hierarchy, and the distinction between functional and visual
proof. It also records exactly what was exercised and what remains unverified.

It is an audit-only workflow with a large scope contract and detailed reporting. Its
evidence hierarchy is useful for an independent reviewer; its complete procedure would
add more process than a routine Leaf repair needs.

### `agentic-browser-testing`

[The agentic browser testing skill](https://github.com/petrkindlmann/qa-skills/blob/main/skills/agentic-browser-testing/SKILL.md)
gives an agent a natural-language goal, lets it navigate through the accessibility tree,
requires an explicit outcome oracle, and promotes stable runs into ordinary Playwright
tests. This is the best public statement of mission-driven testing rather than
selector-driven scripts.

It is designed primarily for deterministic CI gates. It places the oracle outside the
agent and intentionally avoids open-ended visual judgment, so it complements rather than
replaces `/ui-sweep`.

### Browserbase `ui-test`

[The Browserbase UI test skill](https://github.com/browserbase/skills/blob/main/skills/ui-test/SKILL.md)
combines diff-aware tests, an exploratory mode, deterministic accessibility and console
checks, screenshots, and parallel browser sessions. It explicitly tells the exploratory
agent to roam rather than claim systematic coverage.

The complete workflow also contains application-wide navigation, per-page adversarial
patterns, broad checklists, and an HTML report. Its browser recipes and evidence rules
are reusable; its full QA-program shape is not.

### OpenAI `playwright-interactive`

[The OpenAI Playwright interactive skill](https://github.com/openai/skills/blob/main/skills/.curated/playwright-interactive/SKILL.md)
keeps a browser session alive across implementation and debugging iterations and requires
separate functional and visual passes. It is a strong implementation-time browser
driver.

It begins by inventorying every relevant control, state transition, and user-facing
claim. That is appropriate for signing off a bounded change, but the inventory should
not become Leaf's standing product-coverage record.

### Anthropic `webapp-testing`

[The Anthropic web application testing skill](https://github.com/anthropics/skills/blob/main/skills/webapp-testing/SKILL.md)
provides simple local-server and Playwright mechanics: inspect, select, act, capture, and
read browser logs. It is useful tool guidance but has no exploration allocation,
independent evaluation, continuity, or repair policy.

### Browser Use `qa`

[The Browser Use QA skill](https://github.com/browser-use/browser-use/blob/main/skills/qa/SKILL.md)
runs natural-language flows in cloud browsers and can fan them out across agents. It is
an option when isolated hosted browsers or concurrency matter more than local fidelity.

Its required cloud harness, per-flow score, credit model, and report-first framing add an
external service and a scalar quality target. Leaf already has isolated local browser
pages and does not need this dependency for the initial operating model.

### Narrow audit skills

Accessibility, Lighthouse, visual-regression, and screenshot-heuristic skills can add a
specialist pass after a mission identifies the relevant risk. They should remain
conditional. Composing every specialist audit into every run recreates an exhaustive
checklist under separate names.

## Broad options

| Option | Operating model | What it adds | Main cost |
| --- | --- | --- | --- |
| **A. Leaf-native composition** | Tend selects a mission; `/ui-sweep` investigates and repairs; `/iteration:norman` or `/review` repeats it cold; stable findings become tests. | A small acceptance-policy and mission-selection change. | Leaf owns a short amount of workflow prose. |
| **B. External cold evaluator** | Option A, but Vercel dogfood or `frontend-visual-qa` performs the independent pass. | A field-tested outside perspective and richer evidence conventions. | Another browser tool, installation surface, and reporting model; still no repair ownership. |
| **C. Goal-driven CI agent** | Run `agentic-browser-testing` missions as scheduled or change-specific gates; graduate stable flows into Playwright. | Explicit oracles and repeatable natural-language journeys. | Determinism infrastructure, model cost, and limited visual judgment. |
| **D. General QA skill suite** | Adopt Browserbase `ui-test` or a similar package for exploration, checks, reports, and parallel sessions. | Broad ready-made coverage and templates. | A maintained taxonomy, report pipeline, and generic assumptions that overlap Leaf's existing suite. |
| **E. Hosted browser QA** | Send missions to Browser Use or another cloud browser service and collect judged runs. | Isolation, concurrency, and remote execution without local browser ownership. | Service dependency, credentials, spend, lower local-environment fidelity, and score-driven incentives. |
| **F. Bespoke QA system** | Build a mission scheduler, coverage database, evidence viewer, and agent coordinator around Leaf. | Complete control and consolidated history. | A second product to design and maintain before repeated runs establish that it is needed. |

Options are not mutually exclusive at the component level. Option A can later borrow one
evidence rule or browser driver from B through E without adopting that option's operating
model.

## Common mission and acceptance contract

All viable options can share one small contract.

A mission names:

- the reader's goal;
- the relationship or responsibility under challenge;
- one plausible failure and its reader-visible consequence;
- the perturbation that distinguishes the hypothesis; and
- what should change and what must survive.

For example:

> Review a proposal, comment on one passage, change the decision, and return to the
> passage after the document revises at a narrow viewport. The chosen value should
> change; the draft, focus, and reading position should survive.

The mission does not name controls, selectors, or expected defects. The agent discovers
the route through the same rendered controls a reader would use.

A reader-facing change or chartered sweep is complete when the exercised task is
discoverable and coherent through the reached forward, failure, recovery, and return
states. Every concrete anomaly encountered receives one disposition:

- fixed, pinned by the useful regression, and replayed;
- disproved with deciding evidence;
- intentional under an existing named contract; or
- unresolved because product intent or unavailable evidence is required.

“The happy path worked” does not dispose of a problem encountered on that path. “Design
judgment” applies when multiple coherent behaviors satisfy the evidence, not when a
reproducible journey loses work, hides an action, violates accessibility, or presents
equivalent states inconsistently.

## Selecting work without a coverage matrix

Each scheduled run can form candidate missions from existing durable sources:

- changed runtime, theme, registry, example, or ownership relationships;
- recent UI-fix commits and the sibling compositions where their mechanisms may recur;
- unresolved reader-facing issues and TODO entries;
- shipped examples unlike the recent Tend runs; and
- the last few Tend run summaries, including transitions not reached.

The agent chooses the mission with the greatest plausible reader consequence, strongest
connection to changed or historically fragile behavior, most useful contrast with recent
runs, and lowest cost to reach decisive evidence. This is qualitative risk and
information gain, not a score.

Discovery should not outrun repair. A confirmed repair queue takes precedence over
generating more findings. Parallel work is useful only where ownership is genuinely
independent.

## Durable record options

### Existing systems only

A clean run leaves a compact Tend summary: commit, mission, page, relevant conditions,
transitions reached, verdict, and residual risk. A repaired defect leaves its PR and
regression test. A blocked product decision leaves one issue. Git, GitHub, tests, and
Tend summaries are the index.

This is the minimum-maintenance starting point. Its weakness is that querying several
recent runs may be inconvenient or unreliable inside a scheduled agent context.

### Append-only mission receipt

If the existing systems do not give later runs enough continuity, add one versioned
JSONL record per mission. It needs only the revision, mission seed, page, conditions,
transitions reached or blocked, verdict, evidence pointer, and disposition. It records
what happened; it does not contain every possible condition that did not happen.

This is a log, not a dashboard or backlog. Add it only after a pilot demonstrates the
retrieval failure it fixes.

### Full QA store

A database and UI could index missions, artifacts, coverage dimensions, ownership, and
repair status. None of the current evidence requires this option. It should be
reconsidered only if repeated runs produce durable coordination queries that GitHub,
tests, and a small log cannot answer.

## Agent roles

Two perspectives are load-bearing; more roles are optional:

| Perspective | Context | Question |
| --- | --- | --- |
| Cold reader | Neutral task and candidate URL; no source, selectors, diagnosis, or author verdict. | Can the reader discover, complete, understand, recover, and return? |
| Engineering explorer | Source, diff, contracts, history, browser state, baseline, and candidate. | Which relationship failed, where is its canonical owner, and what sibling case distinguishes a general repair? |

A separate visual comparator is useful when the change is primarily visual or the cold
reader and explorer disagree about hierarchy. A deterministic checker remains useful for
accessibility, console, network, geometry, and final-state facts. Neither replaces the
two perspectives above.

The roles reconcile through evidence rather than voting. A reproducible task failure or
contract violation is a defect even if another agent did not notice it. A visual
difference with no task consequence, contract violation, relational inconsistency, or
merge-base regression is a preference rather than a blocker. Evidence of harm without
one determined repair is a product decision.

## Stopping and calibration

A repair stops when the original journey and one sibling case pass, the useful lower
boundary has a regression test, the required checks pass, and an independent reader
accepts the rendered result.

An exploratory mission stops at its charter and time budget after every observed anomaly
has a disposition. A broader sweep can stop after materially different clean missions
show declining yield and no remaining high-risk candidate is apparent. A clean run is a
valid result, not pressure to manufacture a finding. It does not certify the whole
product.

Product exploration stays open-ended. Evaluation of the QA instructions can use a tiny
hidden calibration set of historical misses and clean controls. That set tests whether a
skill catches consequential problems without inventing defects; it is not product
coverage. Add a case only for an observed evaluator failure and remove cases made
redundant by a stronger contrast.

## Independent Astra review

An independent GPT-6 Astra review recommended making UI quality a recurring Tend repair
responsibility rather than adding a QA application. Its proposed split was a
source-informed investigator and fixer plus a context-blind reviewer. Both start from a
reader task in the browser; the reviewer receives no author verdict before recording its
first route.

The review also recommended short exploratory charters, immediate repair of clear
defects, one issue only for unresolved product intent or a substantial independent
repair, and a brief record of what was actually exercised. It warned against rewarding
finding count, screenshot count, test count, or a beauty score, and against increasing
discovery throughput while confirmed repairs remain open. Its minimum implementation
was an acceptance-policy change, mission selection in `/ui-sweep`, and a pilot on a
previously dismissed finding. It did not recommend a Leaf runtime, scheduler, database,
or dashboard change.

## Current recommendation

Start with Option A and no new persistent service:

1. Narrow Tend's stronger UI acceptance rule to the affected reader journey and every
   anomaly genuinely encountered during `/ui-sweep`.
2. Let the standing sweep choose short missions from the diff, recent defect mechanisms,
   shipped examples, and recent run summaries.
3. Run a cold reader independently before or after the source-informed repair.
4. Use the existing PR, regression test, or unresolved issue as the durable result;
   retain rich browser evidence only for failures and visual decisions.
5. Pilot the instructions against one historical miss and one clean control before
   adding a mission log.

This recommendation preserves the option to adopt an external browser driver or
evaluator later. It rejects only the premature commitment to a checklist, scalar quality
score, complete coverage matrix, or Leaf-specific QA application.
