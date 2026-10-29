# Controlled one-response syntax experiment

Design frozen before the retained batch, after the smoke adjustments below.
This follow-up removes the earlier
pilot's tool-assisted editing, runtime/catalog differences and author-written
behavior. It measures the first response for the existing status, choice and
form briefs in `status.md`, `choice.md`, `form.md`.

## Conditions

Both arms receive the exact same brief and `controlled-contract.md`, then a
short syntax appendix. HTML returns one raw section fragment. JSON returns the
equivalent nested `{type, props, children}` tree with string text children;
the compiler creates the same fragment. It has no flat ID-map indirection.
Both use the same content elements, actual Leaf choices, native HTML forms,
shared styles and shared form-submission listener. Neither model writes code,
styles, a registry, a document shell, or files. The same host renders both.

The form listener is benchmark-supplied behavior, not a built-in Leaf form
component. This isolates these matched authoring contracts. It does not compare
unrestricted HTML with every JSON design, Adaptive Cards, json-render,
constrained decoding, agent tool workflows, custom widgets or page revisions.
The JSON grammar is one concrete design, not a claim about JSON in general.

## Inference and order

Use `gpt-6.1-sol`, medium effort, the account's subscription and an isolated
Codex home seeded through the existing `codex_home` helper. Compose the existing
App Server transport and `leaf.inference.CODEX_CONFIG`; known tool features,
plugins, skills, hooks, web search and project instructions are disabled. Each sample gets one
fresh ephemeral thread in an empty temporary directory. Both arms return
ordinary unconstrained text: neither receives `outputSchema`. No API key is
used. Standard speed is explicitly requested with `serviceTier=default` on the
thread and `serviceTierForTurn=default` on the turn; `thread.json` retains
effective server metadata. There is no
author-side validation or repair within a first attempt. The first smoke showed
that this CLI ignores the older `include_apply_patch_tool` configuration flag.
The per-eval copy removes it. Native feature configuration does not establish
that every possible tool schema is absent. The instruction forbids tools; any
observed tool call is retained as a protocol failure and is never silently
rerun. Accordingly the measured condition is a single response with no observed
tool use, not a guarantee that the provider exposed no tool schema. This same
configuration applies to both encodings.

Promptfoo executes two format providers, serially, with three repetitions per
brief: 18 initial calls. Repetitions are explicit matrix tests so order can
alternate; Promptfoo's built-in repeat fixes provider order. Each adjacent pair
shares a brief and repetition. Each task's first format alternates across its
repetitions, independently of task order, which rotates each round. With an
odd number of pairs the first-format counts differ by one. The written schedule and
actual notification/sample times make ordering auditable. Nine calls per arm
is exploratory and cannot establish a stable speed or reliability ranking.

First run equivalent known form fixtures without a model, then one form smoke
call per format. Smoke samples are excluded from the retained batch. A fixture
or transport error is fixed before the batch; any post-smoke contract change
is recorded and frozen before new calls.

## Outcomes and repair

Retain the exact instructions, brief, raw response, request parameters,
thread/start result, full timestamped App Server notifications, token usage,
compiled fragment/page, validation diagnostics and browser captures. Report:

- Initial correctness by stage: output contract/parse, Leaf page validation,
  browser errors, operated interaction, and a separate semantic reading.
- Timing from immediately before turn/start to turn/completed. Also record
  setup before turn/start and time to the first visible agent-message text
  delta. This last measure includes medium-effort reasoning and provider wait;
  it is not time to the first internal/reasoning token. Total wall time is a
  separate number and includes server setup/cleanup and checking in Promptfoo.
- Native input/output/reasoning token fields as supplied, plus UTF-8 output
  bytes. Native outputTokens may include reasoning; do not call it visible
  code-token throughput. Provider usage is not dollar cost on a subscription.

The browser first opens a fresh context at 900 by 760. Choice checks select the
second then third option and verify exactly one authored option remains chosen.
Form checks fill a title, choose High, enter impact, submit, and verify that
the new visible receipt contains all three values. Status has no operated
interaction. The automated checks do not grade aesthetics, visual hierarchy,
all keyboard/touch routes, responsive layout, or semantic truth.

An independent reader grades all first responses from rendered text and the
shared brief, with format labels withheld in the grading material. The common
rubric is the existing case.yaml task-fit criteria: preserve supplied facts and
uncertainty; status identifies EU as the blocker, continued regions and the
checkpoint/owner; choice preserves all tradeoffs and hold recommendation but
leaves the decision to the user; form preserves the incident facts and offers
the requested fields and local review. The browser owns behavior evidence.
Keep reasons and grade identity beside samples, separate from automatic checks.

For each failed initial response, allow at most one new-context repair call.
It receives the original brief, original answer, independent check diagnostics
and the fixed instruction to return a complete corrected response. Semantic
feedback uses the same rubric and no encoding-specific hint. Save repair
results in a separate Promptfoo run and report its additional model time,
tokens and success separately. Human diagnosis/check wait is not model time.
No repair is requested for a passing response. Preserve failed attempts.

The retained batch exposed an ambiguity in the common component instructions:
they list available attributes globally but Leaf validates each tag's own
schema. Both encodings produced one `lf-options` with `aria-label`, which the
Leaf schema rejects. These are component-contract failures, not encoding parse
failures. Preserve that distinction when interpreting the run. Future runs use
the corrected contract, which lists the Leaf elements' attributes separately
from ordinary HTML attributes. The retained batch's saved `instructions.txt`
files preserve its original contract; do not pool its results with new runs as
one unchanged condition. Repairs reuse the initial sample's saved instructions,
including when the current contract has since changed.

## Commands

```sh
uv run leaf-dev eval-widget-formats --preflight
uv run leaf-dev eval-widget-formats --smoke
uv run leaf-dev eval-widget-formats
uv run leaf-dev eval-widget-formats --repair /absolute/path/to/failed-sample
pnpm run eval:view
```

An optional `semantic-feedback.txt` inside a failed sample supplies the blinded
reader's semantic diagnosis to the standardized repair. A repair sample cannot
be repaired again. Keep the initial-to-repair association in the result report.
