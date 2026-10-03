# Leaf evals

One task catalog runs through Promptfoo on Claude Code and Codex. Start small:

```sh
npm ci --prefix evals
uv run leaf-dev eval brief-document-needs-no-outline
uv run leaf-dev eval reading --host codex
uv run leaf-dev eval document --condition both
uv run leaf-dev eval document/mid-turn --host both --runs 2
uv run leaf-dev eval dashboard/reader --host cc
```

`leaf-dev eval [CASE]...` accepts case globs or a task/context address. No argument
selects the task primaries and short instruction cases. A bare `document` selects
its complete workflow; `document/*` selects its isolated diagnostic contexts.
`reading` asks about every reading surface together; `reading/plain` isolates one.
Grouping contexts saves catalog duplication, not model calls.

The defaults are both hosts, one repetition, and Leaf at the merge base with
`main` versus the working tree. `--base REF` selects another baseline. `--condition
html` runs an available plain HTML control; `--condition both` runs it beside the
Leaf revisions. HTML is sampled once per host and repetition, because it does not
consume Leaf's version. Cases without an HTML condition run only on Leaf. A
selection with no requested condition fails before executing model calls.

Every sample gets a fresh workspace and authenticated home outside the repository.
Claude Code uses Opus; Codex uses `gpt-6.1-sol` at medium reasoning. Native rubric
assertions use the same Sonnet judge for either author host; complete composition
workflows also use a fixed judge. Runs spend the signed-in accounts' usage.

Results, generated config, native traces, page evidence and an HTML report go under
`.tmp/eval/`. Assertions failing and provider errors both fail the command; the
summary distinguishes execution errors. Caching, sharing, telemetry and Promptfoo's
result database are disabled. Timing and costs remain diagnostics.

## One catalog, with different amounts of work

Each `evals/<task>/case.yaml` is the task's canonical catalog entry. Short tasks are
native Promptfoo tests: `vars.prompt` carries the request; `assert` contains native
`regex`, `not-regex`, `llm-rubric` or JavaScript assertions. Keep provenance in the
leading comment and the behavior under `metadata.purpose`. Each assertion's `metric`
names the reading. No executor is needed for a one-turn reply.

A task needing files, revisions or live feedback instead declares
`metadata.executor`, `metadata.case`, and `metadata.conditions`. The executor owns
its existing Python trajectory and the fixed checks returned by `expected_checks`;
Promptfoo still owns scheduling, repetition, assertions and reports. There is no
workflow language or second assertion registry. Missing completion or duplicate
checks fail preparation; missing evidence fails the generated native assertion.
Optional `variants` name diagnostic contexts, overriding the primary's metadata.
Each expands to a task/context address. Contexts remain selectable when larger tasks
cover the same behavior, so a failing workflow can be narrowed without another
public suite type.

The complete task primaries are document, dashboard, queue, reading,
disposable-report, short-chat-answer and unknown-package. The first three compose
and revise larger examples; their common visual judgments inspect the actual
authored request and screenshots. After the common comparison, Leaf workflows separately admit a user choice
on the authored page, ask a fresh agent to read it without editing, and check that
a further completed, stamped revision preserves it. Common screenshot judgments
use the page saved before this Leaf-only feedback. They do not replace the historical seeded
state or feedback fixtures. Those remain separately executable diagnostic contexts
until running the larger examples establishes that they detect the same failures.
Fewer task definitions does not establish fewer model calls or equivalent coverage.
Short instruction cases retain their original assertions. Candidate case merges
stay intact until replaying their earlier failures establishes that the larger case
preserves the regression signal. Topic overlap alone does not establish equivalent
coverage.

Plain HTML and Leaf receive the same user request, data, revision and quality
criteria; the HTML agent receives no Leaf skill, runtime or widgets. Composition
checks judge the resulting page, not just a promised action. Leaf-only checks are
only generated for the Leaf condition. Host and model vary together, so a CC/Codex
comparison measures the combined author configuration.

`dashboard/reader` independently calibrates the fixed Claude reader using the
shipped triage-board example: a seeded counting defect beside its corrected count control. It scores count
detection and false alarms; general usability verdicts remain diagnostics. Accepting
the count control does not establish that the entire page satisfies the request.
It uses host CC and the Leaf condition; both Leaf revisions render the controls.
It does not test the dashboard author. Selecting only Codex for this calibration
fails selection. Author comparisons still support both hosts.

## Assertions and evidence

A JavaScript reference assertion uses `reference-read.cjs` and `config.path`, a
regex for the expected file address. Reference checks require successful output
rather than attempted tool use. Codex shell matching is evidence of a read, not
exact proof of the bytes consumed; inspect the trace when that distinction matters.
`text-regex.cjs` preserves flags and negation through `config.pattern`,
`config.flags` and `config.negate`; native Promptfoo regex assertions have no flags.

Short cases score the returned response and instruction use. They do not execute
the authored HTML, plugin discovery or hooks. Complete workflows run their required
file, browser and feedback steps and preserve their evidence. `leaf-dev
verify-codex-task` remains the real plugin and transport integration check;
`verify-site` owns deployed website boundaries. Browser benchmarks and deterministic
tests keep their own commands. A model judge's pass is weak evidence until calibrated
against independent judgments.

`dev/leaf_dev/eval.py` owns catalog selection and the meaningful matrix.
`promptfoo.py` owns native invocation and reporting. `scenario_provider.py` forwards
one complete task to its declared executor with an explicit host and condition.
Host sessions are shared by those executors rather than reimplemented per task.

```sh
npm test --prefix evals
uv run pytest tests/test_eval.py tests/test_scenario_eval.py tests/test_usability_eval.py tests/test_arrangement_eval.py -q -n0
```
