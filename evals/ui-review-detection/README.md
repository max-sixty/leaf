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
```

`--repeat 2` runs independent conversations. Every run needs a fresh `--output`
directory; the default is under `.tmp/eval-ui-review/`. Models use the host's
signed-in subscriptions. No dollar-cost estimate is reported.

Recognition supplies the same labelled screenshot sequence to both arms. The
browser arm additionally has one host-owned operation for snapshots, clicks,
keyboard input and scrolling. No-tools exposes no native tool definitions.
Discovery supplies only the arrival screenshot, so the browser model must discover
transitions. A transition-only defect is unobservable in no-tools discovery and
must not be scored as a miss.

## Retained cases and calibration

| Case | Target | Corrected control |
| --- | --- | --- |
| `recording-times` | Label boxes lack a visible point anchor, making event time or apparent duration ambiguous. | Restores point dots and stems while retaining label widths, stacking and dense timing. |
| `recording-stepping` | Variable checkpoint metadata moves the application image during intermediate-frame stepping. | Places the image before variable metadata so its origin stays fixed. |

Calibration on 2026-10-10 found that Sol missed the timing target in three static
reviews; Opus and Fable detected it in their static comparison runs, while Astra
missed it. All four detected image movement statically. These are narrow fresh
review observations, mostly one conversation per comparative cell, not a general
model ranking or a replay of the long authoring sessions. The ambiguous grouped
navigation probe was exploratory and is not retained here.

The calibration browser providers omitted computed accessibility and nested scroll
targets. The current provider corrects those evidence gaps; their effect on model
detection has not been measured. Do not pool different provider versions as if
they supplied identical evidence.

## Evidence and grading

The runner freezes and hashes its source, provider, prompts, rubric, public assets
and candidate packets before inference. It retains the dependency lock, installed
direct dependency versions, and Node/Python/Chrome identities. Installed transitive
bytes rely on `npm ci` rather than independent hashes. The private provenance
records historical sources and reconstruction limits. Screenshots are generated
from text fixtures; run captures and raw outputs stay under `.tmp/`.

The server exposes only public assets. Candidate models receive no diagnosis,
variant label, source code or prior complaints. Codex uses pi-ai's native OAuth
Responses transport; Claude uses its Agent SDK with built-ins disabled and an
isolated login home. Both receive the same controlled browser capability. Native
harness differences remain a comparison limitation.

Each sample retains its request, supplied images, native trace, browser captures,
answer, observed assistant identity and usage, or an execution-error record.
Grade every completed answer against the run's frozen `rubric.json` and actual
evidence, preferably with model identity withheld:

- On defective cases, score specific target detection and supporting evidence.
- On controls, score allegations of the repaired target separately. Other valid
  findings are allowed.
- Record unsupported observations and execution integrity independently.
- Exclude infrastructure failures from correctness totals.

**Promptfoo completion indicators are not correctness scores.** Its table records
whether execution returned an answer; the semantic findings require grading.

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

Timeouts are unscored: Codex applies its timeout per request, whereas Claude
applies it to the whole query. Do not compare latency under those different
limits. Claude's native usage may include auxiliary models; observed assistant
identity and complete native model-usage keys are retained.
