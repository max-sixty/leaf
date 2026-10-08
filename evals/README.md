# Leaf evals

Each `evals/<task>/case.yaml` is a Promptfoo test that runs on Claude Code and Codex.
`leaf-dev eval` builds the Leaf arms, turns the selected cases into a Promptfoo
config, and runs `promptfoo eval`; Promptfoo does the rest.

```sh
npm ci --prefix evals
uv run leaf-dev eval brief-document-needs-no-outline
uv run leaf-dev eval reading document/resume --harness claude-code
uv run leaf-dev eval task-outlasts-the-turn --base
uv run leaf-dev eval document --condition both --repeat 3
npm run view --prefix evals
```

## Choosing what runs

- **Cases.** Each argument is a case name or glob. A bare task (`document`) runs
  its complete workflow; `task/context` (`document/resume`) runs one of its
  diagnostic contexts, declared under `variants`. No argument runs every task.
- **Arms.** The working tree always runs. `--base` adds the merge base with `main`
  as a second arm, and `--base REF` adds that ref; put cases before it. An arm
  holds only the plugin payload, with no git history, so an agent can't look up
  another version of Leaf through it.
- **Harnesses.** `--harness claude-code`, `codex` or `both` (the default).
- **Conditions.** `--condition html` runs the plain HTML control on the tasks that
  declare one (document, dashboard and queue); `both` runs it beside Leaf. The
  control gets the same request and judge with no Leaf skill, runtime or widgets.
- **Promptfoo options.** Anything after the cases goes to `promptfoo eval`, such as
  `--repeat 3`, `-j 4` or `--filter-pattern`.

## Reading the results

Promptfoo prints a table with a row per test and a column per provider: a harness on
one arm (`claude-code/candidate`, `codex/base`), suffixed `/workflow` for complete
tasks, and `claude-code/html/workflow` for the HTML control. A Codex workflow column
reads `codex:app-server/...`: its session takes Leaf's App Server transport, and the
queue transport the desktop app and IDE use runs only under
`leaf-dev verify-codex-task`. Each assertion's `metric` is a named score, so a
comparison reads per metric across columns.

`npm run view --prefix evals` opens Promptfoo's viewer on every run recorded on
this machine, each named by branch, commits and cases. It shows each sample's
output, assertion reasons, metadata, cost and tokens, and compares runs.

Complete tasks keep their evidence (prompts, native traces, page directories)
under `.tmp/eval/<run>/samples/`, one directory per sample named by its case, and
each sample's `metadata.work` names its directory. A judged sample's screenshots
are under `screenshots/`, in a directory of the same name. `results.json` there
holds the whole run.

Executor turns, live sessions, and native Codex provider calls allow six hours;
the outer workflow provider allows a day for multiple turns and artifact checks.
Elapsed time is diagnostic, separate from correctness. Promptfoo records
provider-call duration in `latencyMs`.
Native duration, where a workflow reports it, is unknown when its trace lacks
completion timing; it is never filled in as zero.

## Case format

A short case is one prompt with native assertions: `vars.prompt` carries the
request, and `assert` holds `regex`, `llm-rubric` or JavaScript assertions. The
runner prepends a line telling the agent to use the Leaf skill for shipped-skill
cases. The agent may only
read (Claude Code's Skill and Read tools; Codex's read-only sandbox), so a prompt
that needs a page asks for its HTML in the reply, and one that grades what the
agent would do asks for the commands it would run. Opus 5.5's safeguards refuse a
prompt asking for its tool calls with their JSON input. The leading comment records
where the case came from and what it measured, `metadata.purpose` the behavior it
pins, and `metadata.tags` its area.

Internal instruction cases declare `metadata.instructions`, a source path in
that arm. The native provider receives its contents as system/developer context;
the case grades the resulting behavior. These columns end in `/instructions`.
Shipped-skill cases instead let the agent load its skill and references. Both kinds
score the resulting answer against the task. Reading a named file is not a scored
requirement; native traces retain tool calls for diagnosing instruction loading.

Grader controls set `providerOutput` to a fixed answer and reuse the case's rubric,
with `not-llm-rubric` for an answer the judge should reject. Promptfoo skips agent
generation and grades that answer; `review-shows-the-change/grader-*` exercises
this path. These scores measure the judge, not the agent's behavior.

A complete task instead names `metadata.executor`, a `leaf_dev` module, and
`metadata.scenario`, a key of that module's `CASES`. The executor builds fixtures, runs the agent
through resumed phases or live user rounds, and returns a boolean per check; its
`expected_checks` declares the check names, which become one assertion each, so a
check that never ran fails rather than disappearing. An executor whose output lists
screenshots, beside the request they answer, also declares `rubrics`: `agent-rubric`
assertions a screenshot judge grades by opening them. It writes them to the `shots`
directory it is given, the only place the judge may read. `metadata.conditions` and
`metadata.harnesses` restrict where it runs.

| Executor | Runs |
| --- | --- |
| `arrangement_eval` | Authors, checks and revises a page from `request.md`; screenshots each version on a laptop, at 900px with tall and short windows, and on a phone. For tasks that request a decision, Leaf also seeds a user choice, has a fresh reader report it, and checks a further revision keeps it. |
| `usability_eval` | Seeded pages read, resumed and revised, and live handoffs where the harness posts user moves through the served page. Fixtures are in `usability/fixtures/`. |
| `delivery_eval` | Comments posted between turns and mid-turn, each of which must be picked up, started and answered. |
| `reader_eval` | Calibrates the screenshot judge: `dashboard/reader-seeded` and `reader-clean` each show it one triage board, with a seeded count defect or the correct count, and ask both whether the count matches the cards. |

`sidebar-page-at-900px` runs the complete authoring and render loop. Its
`/instructions` diagnostic retains the read-only source probe, and `/live` checks
the contrasting bounded live stream. The primary judge reads the rendered record:
the completed log grows in document flow, and checks and navigation stay reachable
while reading, including in the short window. Source-property checks in the
instruction diagnostic do not establish that rendered behavior.

Case-insensitive patterns use native `regex` or `not-regex` assertions with
`transform: output.toLowerCase()`. Workflow checks use inline JavaScript over the
provider's check metadata.

## Isolation and models

Every provider runs in a fresh workspace outside the repository, under a home of its
own seeded only with a copy of the host's login, so runs spend the signed-in accounts'
usage and never an API key. Native Codex probes install the complete arm through the
host Codex CLI's plugin installer in that home, and use the same CLI to run the
read-only task. `harness.MODELS` pins the models: Opus for Claude
Code, `gpt-6.1-sol` at medium reasoning for Codex, Sonnet for `llm-rubric`, which
grades text and opens nothing, and `gpt-6.1-sol` for the screenshot judge. That
judge runs on the installed `codex` under a permission profile that lets it read
the run's `screenshots/` and no other file of the repository. Promptfoo counts a
judge's tokens but not its cost, and doesn't record which screenshots it opened, so
read its reason. No judge has been calibrated against human judgments, so treat a
judged pass as weak evidence and read the outputs.

Another judge may grade the same samples differently, so a judged difference is
partly the judge's. To compare judges, point `screenshot_judge` in
`dev/leaf_dev/eval.py` at another model or provider (an `anthropic:claude-agent-sdk`
grader restricted to `Read` on the screenshot tree works), rerun the same cases, and
compare the runs in the viewer, starting with the `dashboard/reader-*` calibration.

These cases score instruction use and the agent loop. `leaf-dev verify-codex-task`
covers plugin installation, discovery and hooks, and `leaf-dev verify-site` the
website.

```sh
npm test --prefix evals
uv run pytest tests/test_eval.py tests/test_scenario_eval.py tests/test_usability_eval.py tests/test_arrangement_eval.py -q -n0
```
