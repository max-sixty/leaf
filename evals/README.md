# Leaf evals

Each `evals/<task>/case.yaml` is a Promptfoo test that runs on Claude Code and Codex.
`leaf-dev eval` builds the Leaf arms, turns the selected cases into a Promptfoo
config, and runs `promptfoo eval`; Promptfoo does the rest.

```sh
npm ci --prefix evals
uv run leaf-dev eval brief-document-needs-no-outline
uv run leaf-dev eval reading document/resume --host cc
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
- **Hosts.** `--host cc`, `codex` or `both` (the default).
- **Conditions.** `--condition html` runs the plain HTML control on the tasks that
  declare one (document, dashboard and queue); `both` runs it beside Leaf. The
  control gets the same request and judge with no Leaf skill, runtime or widgets.
- **Promptfoo options.** Anything after the cases goes to `promptfoo eval`, such as
  `--repeat 3`, `-j 4` or `--filter-pattern`.

## Reading the results

Promptfoo prints a table with a row per test and a column per provider: a host on
one arm (`cc/candidate`, `codex/base`), suffixed `/workflow` for complete tasks, and
`cc/html/workflow` for the HTML control. Each assertion's `metric` is a named score,
so a comparison reads per metric across columns.

`npm run view --prefix evals` opens Promptfoo's viewer on every run recorded on
this machine, each named by branch, commits and cases. It shows each sample's
output, assertion reasons, metadata, cost and tokens, and compares runs.

Complete tasks keep their evidence (prompts, native traces, page directories)
under `.tmp/eval/<run>/samples/`, one directory per sample named by its case, and
each sample's `metadata.work` names its directory. A judged sample's screenshots
are under `screenshots/`, in a directory of the same name. `results.json` there
holds the whole run.

## Case format

A short case is one prompt with native assertions: `vars.prompt` carries the
request, and `assert` holds `regex`, `llm-rubric` or JavaScript assertions. The
runner prepends a line telling the agent to use the Leaf skill. The agent may only
read (Claude Code's Skill and Read tools; Codex's read-only sandbox), so a prompt
that needs a page asks for its HTML in the reply. The leading comment records where
the case came from and what it measured, `metadata.purpose` the behavior it pins,
and `metadata.tags` its area.

A complete task instead names `metadata.executor`, a `leaf_dev` module, and
`metadata.scenario`, a key of that module's `CASES`. The executor builds fixtures, runs the agent
through resumed phases or live user rounds, and returns a boolean per check; its
`expected_checks` declares the check names, which become one assertion each, so a
check that never ran fails rather than disappearing. An executor whose output lists
screenshots, beside the request they answer, also declares `rubrics`: `agent-rubric`
assertions a screenshot judge grades by opening them. It writes them to the `shots`
directory it is given, the only place the judge may read. `metadata.conditions` and
`metadata.hosts` restrict where it runs.

| Executor | Runs |
| --- | --- |
| `arrangement_eval` | Authors and revises a page from `request.md` and screenshots each version at three widths for the judge, and on Leaf seeds a user choice, has a fresh reader report it, and checks a further revision keeps it. |
| `usability_eval` | Seeded pages read, resumed and revised, and live handoffs where the harness posts user moves through the served page. Fixtures are in `usability/fixtures/`. |
| `delivery_eval` | Comments posted between turns and mid-turn, each of which must be picked up, claimed and answered. |
| `reader_eval` | Calibrates the screenshot judge: `dashboard/reader-seeded` and `reader-clean` each show it one triage board, with a seeded count defect or the correct count, and ask both whether the count matches the cards. |

The assertion helpers live here: `reference-read.cjs` passes when the agent read a
file matching `config.path` (Codex shell reads are matched heuristically, so read
the trace when it matters); `text-regex.cjs` is a regex with flags and negation;
`scenario-check.cjs` reads an executor's check.

## Isolation and models

Every provider runs in a fresh workspace outside the repository, under a home of its
own holding only a copy of the host's login, so runs spend the signed-in accounts'
usage and never an API key. `harness.MODELS` pins the models: Opus for Claude
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
