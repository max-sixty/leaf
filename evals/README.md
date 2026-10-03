# Leaf evals

Promptfoo scores static authoring cases against the base and working-tree Leaf
instructions, using Claude Code or Codex. Start with one case:

```sh
npm ci --prefix evals
uv run leaf-dev instructions-eval brief-document-needs-no-outline
uv run leaf-dev instructions-eval 'playground-*' --host codex --runs 3
```

Both hosts and one repetition are the default. `--host cc` selects Claude Code;
`--base REF` chooses the baseline instead of the merge base with local `main`.
No case argument selects the whole library. Each host/arm/repetition has a fresh
workspace and home outside the repository, with only a copy of the local login.
Claude Code uses Opus; Codex uses `gpt-6.1-sol` at medium reasoning. Sonnet judges
both hosts with the same rubric. These runs spend the signed-in accounts' usage.

Results, native tool traces, the generated config, and an HTML report go under
`.tmp/instructions-eval/`. Assertions failing and provider errors both make the
command fail; the summary distinguishes execution errors. Reports are local;
caching, sharing, telemetry, and Promptfoo's result database are disabled.

Each `*/case.yaml` is a native Promptfoo test: `vars.prompt` carries the task,
`assert` contains `regex`, `llm-rubric`, or JavaScript assertions, and `metric`
names the reading. Keep provenance in the leading comment and the clause under
`metadata.purpose`. The runner supplies the shared prompt template, provider
matrix, and judge. A JavaScript reference assertion uses `reference-read.cjs`
and `config.path`, a regex for the expected file address.

Use `not-regex` for a forbidden pattern. Promptfoo's native regex assertions have
no flags; `text-regex.cjs` preserves case-insensitive patterns using `config.pattern`,
`config.flags`, and `config.negate`.

Reference assertions check successful reads rather than attempted tool use.
Codex shell matching is evidence of a read, not exact proof of the bytes consumed;
inspect the trace when that distinction matters. Native Claude Skill results and
Codex's staged skill directory supply the same shipped instructions. These cases
exercise instruction use, not plugin discovery or hooks; `leaf-dev
verify-codex-task` checks that integration.

Complete page, revision, arrangement and feedback trajectories also run through
Promptfoo. Their existing execution uses Claude Code, and each whole scenario is
one sample with fixed checks, including completion:

```sh
uv run leaf-dev scenario-eval usability cold-report
uv run leaf-dev scenario-eval arrangement document
uv run leaf-dev scenario-eval delivery mid-turn --runs 2
```

The defaults are one repetition, base versus working tree, and every case in the
selected suite when no case glob is given. The 19 usability cases, three arrangement
subjects and two delivery cases keep their traces and page evidence beside the native
results under `.tmp/scenario-eval/`. Missing checks and incomplete trajectories fail.
Timing, costs and arrangement preferences remain diagnostics; the arrangement's
stripped-vocabulary arm still uses Leaf's runtime and feedback, so it is not the full
Leaf-versus-plain-HTML comparison in #19. Browser benchmarks and deterministic host
integration checks keep their own commands.

`dev/leaf_dev/promptfoo.py` owns invocation and reporting for both commands.
`scenario_provider.py` is Promptfoo's native Python provider entry point; scenario
modules own their fixtures and trajectories, not scheduling or reports.

```sh
npm test --prefix evals
uv run pytest tests/test_instructions_eval.py tests/test_scenario_eval.py tests/test_usability_eval.py tests/test_arrangement_eval.py -q -n0
```
