# Agent-driven UI quality

The remaining work is to calibrate diagnosis, bound its cost and decide whether
Tend's acceptance policy should change. `/ui-sweep` already owns mission selection,
real-browser evidence, repair, a distinguishing sibling case and independent
review. Leaf already produces quality reports; this proposal does not require
another QA application or coverage inventory.

## Acceptance policy

Tend's ordinary review threshold follows the change's claimed path. The proposed
change is narrow: an anomaly actually encountered while exercising an affected
user journey receives a disposition even when the author did not claim it. Keep
unrelated bounded edge cases outside that threshold.

The policy belongs in `running-tend`, rather than a copy of `/ui-sweep`. Review the
proposal with that control-plane owner before editing its instructions. This note
records the proposal; it does not authorize the policy change.

## Calibration pilot

Use one known historical miss and one intentional behavior or invalid experiment.
Give a source-informed explorer and a cold user the same neutral task with fresh
page state and different responsibilities. Do not reveal the prior verdict.

The explorer owns reproduction, architectural diagnosis, repair and focused
verification. The cold user owns discoverability and rendered acceptance. Add a
specialist only when the evidence names a specific unresolved question. One agent
consolidates findings, and the repair owner runs broad verification.

A candidate carries its revision, initial state, exact ordinary gesture, viewport
and input conditions, expected relationship, observed result, transition actually
reached and deciding evidence. Reproduce it against a distinguishing control before
calling it a defect. Use four dispositions:

- Confirmed defect, with repair and regression evidence.
- Intentional behavior under a named contract.
- Invalid experiment, with the deciding flaw.
- Unresolved intent or evidence, with the missing decision or observation.

Judge whether the agents reproduce the real defect and reject the control for the
right reason. Add a calibration case only after an observed evaluator failure.
A list of visited pages or captured screenshots does not measure user quality.

## Trial evidence

The September 2026 trial confirmed two defects: retargeting could destroy a
destination's draft, and a clipped board target could open its composer outside
the viewport. Both landed with gesture-level regressions in
[PR #636](https://github.com/max-sixty/leaf/pull/636).

Two rejected candidates are useful controls. Coarse-pointer board behavior matched
the intended interaction; the reported `g D` failure came from synthetic modifier
state rather than the ordinary gesture. The trial showed that exploration could
produce repairs, but overlapping agents repeated evidence and left attribution
and cost unclear. It did not establish a routine operating model.

## Continuity and cost

Use Tend's existing summary as the next run's receipt: mission, page and conditions,
reached and unreached transitions, dispositions, evidence, repair, agent allocation
and aggregate cost. Record model, reasoning effort, inherited context, elapsed time
and available token usage as diagnostic inputs, not quotas. A repair remains durable
in its PR and test; use a `visual-run` when aligned rendered evidence is part of the
decision.

Read recent receipts to choose a different high-risk relationship or an unreached
state. Add an append-only mission record only if those summaries prove difficult
to retrieve or compare. Run the bounded pair repeatedly before adding orchestration.
Review defect yield, false-positive causes, unresolved findings, cost and whether
receipts improved mission selection. Automate an observed repeated mechanical
failure, rather than adding a scheduler, database or dashboard in advance.

## Research retained

The original survey was made on 11 September 2026. Its useful methods have primary
references: [session-based exploratory testing](https://www.satisfice.com/download/session-based-test-management),
[agent outcome evaluation](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents),
and [Playwright traces](https://playwright.dev/docs/trace-viewer). This is dated
research, not a claim that those external tools were refreshed during reconciliation.
Retire the note once the calibrated rules live with their workflow owners.
