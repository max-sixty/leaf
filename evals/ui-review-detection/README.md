# Internal UI review diagnostics

These retained `leaf-dev` evals reconstruct two failures missed during the Leaf
recording-viewer work: unclear point-event time anchors and application-image
movement during stepping. Each defective candidate has a corrected control.

We generally do not keep model evals of maintainer development work. Diagnosing
recurring CI issues has become such a drag on productivity that we are retaining
this small internal diagnostic set. Its tasks measure whether models identify
specific viewer defects and distinguish repaired controls. The ordinary
`leaf-dev eval` catalog continues to score shipped instructions and agent loops;
these diagnostics run separately with `leaf-dev eval-ui-review`.

They use the same Promptfoo framework, results database and viewer as the standard
suite. The separate launcher prepares the review-specific evidence conditions;
`grade.mjs` is a JavaScript assertion using Promptfoo's native Codex provider and
Leaf's standard isolated screenshot-judge configuration. A run includes candidate
inference and automatic correctness grading; it needs neither the projects repo
nor a supervising session.

## Run

From the checkout, install the eval dependencies and check the fixtures without
calling a model:

```sh
npm ci --prefix evals
uv run leaf-dev eval-ui-review --prepare-only
```

Start with Sol, then compare models on the same frozen cases:

```sh
uv run leaf-dev eval-ui-review --model sol --condition both --mode recognition
uv run leaf-dev eval-ui-review \
  --model sol --model opus --model fable --model astra \
  --condition both --mode recognition
uv run leaf-dev eval-ui-review \
  --model sol --model opus --model fable --model astra \
  --condition browser --mode discovery
uv run leaf-dev eval-ui-review --model sol --condition code-only
uv run leaf-dev eval-ui-review \
  --model sol --model opus --model fable --model astra \
  --condition code-only
```

`--repeat 2` runs independent conversations. Every run needs a fresh `--output`
directory; the default is under `.tmp/eval-ui-review/`. Models use the host's
signed-in subscriptions. No dollar-cost estimate is reported.
Grading also uses the host's Codex login, with the standard Sol judge.

Recognition supplies the same labelled screenshot sequence to both arms. The
browser arm additionally has one host-owned operation for snapshots, clicks,
keyboard input and scrolling. No-tools exposes no native tool definitions.
Discovery supplies only the arrival screenshot, so the browser model must discover
transitions. A transition-only defect is unobservable in no-tools discovery and
must not be scored as a miss.

Code-only supplies the same review task plus the candidate's authored HTML/CSS,
its local JavaScript and adapter, and SVG source text where used. It supplies no
image content blocks, screenshots, browser capability or other tools. `both`
continues to mean the two visual recognition arms; choose `code-only` separately.
Code-only cannot be combined with arrival-only discovery.

These are complete reconstructed fixture packets, not the full Leaf repository.
The timing packet includes the complete pinned Timeline/DataSet bundle and its
CSS as source text, rather than selecting explanatory excerpts. It contributes
about 450 KB of minified code; record actual input tokens and completion integrity.
The stepping packet includes its module, styling, adapter and vector source.
Grade supported source inferences separately from claims of observed rendering;
exact pixel geometry is not an observed fact in this condition. Source review and
screenshot review answer different evidence questions, so differences are not
a causal estimate of image benefit.

An initial partial-source Sol calibration omitted the timeline bundle. Preserve
that run separately: its timing uncertainty cannot be counted as a comparable
miss against the complete-source condition.

## Retained cases and calibration

| Case | Target | Corrected control |
| --- | --- | --- |
| `recording-times` | Label boxes lack a visible point anchor, making event time or apparent duration ambiguous. | Restores point dots and stems while retaining label widths, stacking and dense timing. |
| `recording-stepping` | Variable checkpoint metadata moves the application image during intermediate-frame stepping. | Places the image before variable metadata so its origin stays fixed. |

Manual calibration on 2026-10-10 found that Sol missed the timing target in three
screenshot-only reviews; Opus and Fable detected it in their screenshot-only
comparison runs, while Astra missed it. All four detected image movement from
screenshots. These are narrow fresh
review observations, mostly one conversation per comparative cell, not a general
model ranking or a replay of the long authoring sessions. The ambiguous grouped
navigation probe was exploratory and is not retained here.

The calibration browser providers omitted computed accessibility and nested scroll
targets. The current provider corrects those evidence gaps; their effect on model
detection has not been measured. Do not pool different provider versions as if
they supplied identical evidence.

## Evidence and grading

The runner freezes and hashes its source, provider, grader, prompts, rubric, public assets
and candidate packets before inference. It retains the dependency lock, installed
direct dependency versions, and Node/Python/Chrome and grader Codex CLI identities. Installed transitive
bytes rely on `npm ci` rather than independent hashes. The private provenance
records historical sources and reconstruction limits. Screenshots are generated
from text fixtures; run captures and raw outputs stay under `.tmp/`.

The server exposes only public assets. Candidate models receive no diagnosis,
variant label or prior complaints; visual arms also withhold source code.
Codex uses pi-ai's native OAuth
Responses transport; Claude uses its Agent SDK with built-ins disabled and an
isolated login home. In the browser condition, both receive the same controlled
browser capability. Native harness differences remain a comparison limitation.
Code-only audits record the
Codex native request payload or the exact user message handed to Claude's SDK,
alongside its empty initialized tool roster. SDK input does not establish HTTP
wire-level byte equality or exclude SDK transformations.

Each sample retains its request, any supplied images, native trace, browser captures,
answer, observed assistant identity and usage, or an execution-error record.
The automatic judge grades each completed answer against the run's frozen
`rubric.json` and that answer's actual evidence:

- On defective cases, score specific target detection and supporting evidence.
- On controls, score allegations of the repaired target separately. Other valid
  findings are allowed.
- Record unsupported observations and execution integrity independently.
- Exclude infrastructure failures from correctness totals.

The judge receives an anonymous packet with the task, answer, supplied source or
images, and actual browser operations/results. Candidate model/harness identity,
native reasoning and other candidates' evidence are withheld. Screenshots are
copied into that sample's allowed evidence tree; its login home is temporary and
outside the retained evidence. Grading has no runner-imposed wall-clock cap.

`results.json` and Promptfoo's viewer contain assertion reasons and named metrics:
`target_detection` (0–2, defective cases), `target_false_alarm` (0–1, controls),
and `unsupported_observations` (count). Inapplicable metrics are omitted from the
named scores; structured grades retain nulls. A full pass requires full target
detection or no control alarm, and no unsupported observations.

`grading-summary.json` separates scored samples from execution failures, judge
failures and unobservable targets. Each sample's `grade.json` retains the structured
grade and audit; anonymous grading inputs and native judge responses are under
`grading/`. Invalid judge output stays unscored. A valid miss is an assertion
failure, not an infrastructure failure. The command follows Promptfoo's exit
convention: 0 for all passes and 100 for assertion failures or unscored samples.

Automated scores are model judgments, not proof of UI correctness. The frozen
rubric and evidence remain available for inspection and regrading. Historical
study grades were manual and are not overwritten by new automatic judgments.

Native grader calibration on 2026-10-10 replayed eight historical answers and
five retained semantic controls (`grader-controls.json`). All six clear historical
target judgments agreed, and all thirteen unsupported-observation checks agreed.
Four of five semantic controls matched exactly. The remaining timing answer raises
a specific duration concern: the automatic judge and original manual grade gave
full credit, while an independent reviewer gave partial credit. That partial/full
boundary remains uncertain; this small calibration is not a general accuracy
estimate. Both ambiguous historical judgments and the failed setup attempts remain
in the study evidence.

A fresh end-to-end Sol recognition run then completed all eight reviews and
automatic grades: both timing defects missed, both movement defects detected,
zero target alarms on four controls, zero unsupported observations and zero
unscored samples. Frozen inputs were unchanged. This verifies the complete
Leaf-only command, including actual browser traces, rather than replay alone.

## Browser tool experiments

`provider.mjs` owns the shared browser capability. Its exported
`openBrowser(manifest, evidenceDir, limit)` returns `invoke(args)`, `calls`,
`captures` and `close()`. Change that capability for a new tool experiment while
holding task, fixtures, rubric and initial evidence fixed. Retain each provider
version and compare its real traces and answers.

The browser states its 12-operation cap and returns `remainingOperations` with
each snapshot. Playwright's accessibility snapshot supplies accessible names,
roles and state; numbered controls carry only a `labelHint`. Scroll owners are
indexed with their axes and positions even when they are not interactive controls.

Model conversations have no runner-imposed wall-clock deadline. Every 30 seconds,
the provider reports elapsed time and time since native activity to stderr and
the sample's `trace.jsonl`. `timing.json` records elapsed time, activity count and
completion status on exit. Inspect these measurements when a run is slow;
elapsed time alone does not abort it. Browser operation limits remain part of the
frozen tool condition. Provider or transport failures remain unscored.

Earlier runs imposed a five-minute Claude query deadline and a Codex response-header
deadline. Preserve those runs as historical evidence; their aborted answers stay
unscored. Claude's native usage may include auxiliary models; observed assistant
identity and complete native model-usage keys are retained.
