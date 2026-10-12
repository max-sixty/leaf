# Leaf evals

Each `evals/<task>/case.yaml` is a Promptfoo test that runs on Claude Code and Codex.
`leaf-dev eval` builds the Leaf arms, turns the selected cases into a Promptfoo
config, and runs `promptfoo eval`; Promptfoo does the rest.

Internal viewer-review diagnostics run with `leaf-dev eval-ui-review`.
They use Promptfoo's assertions and viewer with automatic evidence-aware grading.
Their exception to the usual suite scope, retained cases and grading workflow are
in [UI review detection](ui-review-detection/README.md).

```sh
pnpm install --frozen-lockfile
uv run leaf-dev eval brief-document-needs-no-outline --harness claude-code
uv run leaf-dev eval reading document/resume --harness codex
uv run leaf-dev eval task-outlasts-the-turn --harness claude-code --base
uv run leaf-dev eval document --harness both --condition both --repeat 3
pnpm run eval:view
```

## Choosing what runs

- **Cases.** Each argument is a case name or glob. A bare task (`document`) runs
  its complete workflow; `task/context` (`document/resume`) runs one of its
  diagnostic contexts, declared under `variants`. No argument runs every task.
- **Arms.** The working tree always runs. `--base` adds the merge base with `main`
  as a second arm, and `--base REF` adds that ref; put cases before it. An arm
  holds only the plugin payload, with no git history, so an agent can't look up
  another version of Leaf through it.
- **Harnesses.** `--harness claude-code`, `codex` or `both`, with no default. Run
  the harness the motivating failure came from, or the one you are working in when
  no session failed. Run `both` when the change is about how the harnesses differ,
  such as a harness contract.
- **Conditions.** `--condition html` runs the plain HTML control on the tasks whose
  `metadata.conditions` declare one; `both` runs it beside Leaf. The control gets
  the same request, revisions and judge with no Leaf skill, runtime or widgets.
- **Promptfoo options.** Anything after the cases goes to `promptfoo eval`, such as
  `--repeat 3`, `-j 4` or `--filter-pattern`.

## Reading the results

Promptfoo prints a table with a row per test and a column per provider: a harness on
one arm (`claude-code/candidate`, `codex/base`), suffixed `/authoring` for short
authoring cases or `/workflow` for complete tasks, and `claude-code/html/workflow`
for the HTML control. A Codex authoring or workflow column
reads `codex:app-server/...`: its session takes Leaf's App Server transport, and the
queue transport the desktop app and IDE use runs under
`leaf-dev journey codex-queue`. Each assertion's `metric` is a named score, so a
comparison reads per metric across columns.

An authored task's quality score is `uv run leaf-dev eval-pairs RUN...`, which
judges its samples in two columns side by side, each pair in both orders, and counts
a winner only when both orders name it; each sample's own screenshot rubrics are
diagnostics. Run each column the same number of times; the Nth samples pair. To keep
host load and drift from favoring one column, alternate one-repeat runs of each
condition, swapping which goes first, and pass every run:

```sh
uv run leaf-dev eval configuration --harness claude-code --condition leaf --repeat 1 -j 1
uv run leaf-dev eval configuration --harness claude-code --condition html --repeat 1 -j 1
uv run leaf-dev eval configuration --harness claude-code --condition html --repeat 1 -j 1
uv run leaf-dev eval configuration --harness claude-code --condition leaf --repeat 1 -j 1
uv run leaf-dev eval-pairs .tmp/eval/<run>...
```

`uv run leaf-dev eval-report PAGE RUN...` then writes a Leaf page showing each pair's
final screens side by side with what each sample spent, whether it applied the
user's decision, and what the judge said.

`pnpm run eval:view` opens Promptfoo's viewer on every run recorded on
this machine, each named by branch, commits and cases. It shows each sample's
output, assertion reasons, metadata, cost and tokens, and compares runs.

Authoring cases and complete tasks keep their evidence (prompts, native traces,
page directories) under `.tmp/eval/<run>/samples/`, one directory per sample named
by its case, and each sample's `metadata.work` names its directory. A judged sample's screenshots
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
request, and `assert` judges what the agent wrote, its markup, code and prose, with
`llm-rubric` assertions that each state the property the case is about. A `regex`
or `not-regex` matches only a literal the reply must or must not contain, such as a
command name or a URL: replies spell markup and commands in too many ways (attribute
order, quoting, launcher paths, continued lines) for a pattern to grade them. The
runner prepends a line telling the agent to use the Leaf skill for shipped-skill
cases. A source or reading probe may only
read (Claude Code's Skill and Read tools; Codex's read-only sandbox), so a prompt
that needs a page asks for its HTML in the reply, and one that grades what the
agent would do asks for the commands it would run. Opus 5.5's safeguards refuse a
prompt asking for its tool calls with their JSON input. The leading comment records
where the case came from and what it measured, `metadata.purpose` the behavior it
pins, and `metadata.tags` its area.

A short case that needs real authoring declares `metadata.authoring: true`.
Its agent has native file and command tools, an initialized writable page, the
arm's launcher as `$LEAF`, and a fresh workspace, home, temporary directory and
Leaf state for every sample. Pinned files under `evals/<case>/` are copied into
that workspace at the same relative paths. Cite those paths in the prompt; the
agent can open, register, crop or mark the captures. Ask it to write the page.
Assertions grade the saved `index.html`, with additional `completed` and
`page-valid` checks; the executor independently runs `page check --render` and
keeps the page, native trace, reply, and check output under the sample's evidence.
A visual `agent-rubric` can use `metadata.capture_evidence` to compare original
captures with registered page media, including cropped or marked images. Its
`exact_inputs` records computed source matches, leaving visual comparison to
transformed images. The judge can read only copied images under the run's
screenshot tree; the assertion
supplies authored HTML to identify the references, without the author's trace.

Use authoring cases for media preparation, widget markup and checking or repairing
rendering. Keep source and reading probes for decisions that need no writable
artifact. Use complete tasks for revisions, user feedback and delivery rounds.
Authoring adds page initialization, tool turns and a render check to each sample;
`setup_seconds`, native trace accounting and Promptfoo's `latencyMs` expose those
costs separately. Each sample has its own temp directory. Native tool permissions
match the complete-task executors: Codex allows native tools without approval;
on macOS, Claude Code's sandbox prevents writes to shared temporary paths while
allowing its owned directories, as described under **Isolation**.

Internal instruction cases exercise developing Leaf itself; `/developing-leaf`,
"Score an instruction change", owns when to use one. They declare
`metadata.instructions`, a source path in
that arm. The agent receives its contents and source file location as
system/developer context, retaining the origin of its linked references;
the case grades the resulting behavior. Read-only probe columns end in
`/instructions:` and that path, so cases injecting different files never share
a provider. An authoring case resolves and injects the source separately for every
sample, retaining it as `instructions.txt` beside its native trace; its column keeps
the `/authoring` suffix.
Shipped-skill cases instead let the agent load its skill and references. Both kinds
score the resulting answer against the task. Reading a named file is not a scored
requirement; native traces retain tool calls for diagnosing instruction loading.

Grader controls set `providerOutput` to a fixed answer and reuse the case's rubric,
with `not-llm-rubric` for an answer the judge should reject. Promptfoo skips agent
generation and grades that answer; `review-shows-the-change/grader-*` exercises
this path. These scores measure the judge, not the agent's behavior.

A complete task instead names `metadata.executor`, a `leaf_dev` module, and
`metadata.scenario`, a key of that module's `CASES`. The executor builds fixtures, runs the agent
through resumed phases or live user rounds, and returns a boolean per deterministic check.
Its `expected_checks` declares the check names, which become one assertion each, so a
check that never ran fails rather than disappearing. An executor may also declare
`rubrics`: text `llm-rubric` or screenshot `agent-rubric` assertions. A
deterministic check reads a fact the page or the trace states; anything said in
prose, a reply or a passage on the page, goes to the text judge. A text rubric's
`transform` can hand the judge one entry of the response's `metadata.texts`, such
as one phase's reply or one paragraph, in place of the whole output. A screenshot executor lists captures beside the request
they answer and writes them to the supplied `shots` directory, the only place its
judge may read. `metadata.conditions` and `metadata.harnesses` restrict where it runs.

`metadata.authoring` and `metadata.executor` select distinct execution modes;
declaring both on a case, including through inherited variant metadata, is an error.

| Executor | Runs |
| --- | --- |
| `arrangement_eval` | Runs a page task the way its user would, in one live session per sample. The author builds the page from `request.md`; the user then asks in chat for the 900px preference, comments on a passage, and makes the page's decision in a browser before asking for it to be applied. Leaf runs as the installed plugin: its agent serves and hands over the page, the comment is posted from a browser selection on that page, and the hook delivers it. HTML gets the comment in chat, and pastes what its page offered to copy, or types the decision. A user agent (`eval_user.py`) makes the decision through the page's own controls; the judge reads the author's answer to the comment, a reader checks the applied result against what was chosen, and on Leaf a fresh reader also reports the decision from the page's state. Screenshots each version on a laptop, at 900px with tall and short windows, and on a phone, with the commented item open once a version carries the comment, and records each phase's time, tokens, cost, authored CSS and script lines, and how often it wrote and rendered the page. |
| `usability_eval` | Seeded pages read, resumed and revised, and live handoffs where the harness posts user updates through the served page. Checks read Leaf's page state and its parse of the markup; answers and edited prose go to the text judge; script repairs exercise the affected control. Fixtures are in `usability/fixtures/`. |
| `delivery_eval` | Comments posted between turns and mid-turn, each of which must be picked up, started and answered. |
| `reader_eval` | Calibrates the screenshot judge: `dashboard/reader-seeded` and `reader-clean` each show it one triage board, with a seeded count defect or the correct count, and ask both whether the count matches the cards. |

`sidebar-page-at-900px` runs the complete authoring and render loop. Its
`/instructions` diagnostic retains the read-only source probe, and `/live` checks
the contrasting bounded live stream. The primary judge reads the rendered record:
the completed log grows in document flow, and checks and navigation stay reachable
while reading, including in the short window. Source-property checks in the
instruction diagnostic do not establish that rendered behavior.

## Isolation and models

Every provider runs in a fresh workspace outside the repository, under a home of its
own seeded only with a copy of the host's login, so runs spend the signed-in accounts'
usage and never an API key. Authoring agents write scratch files in `/tmp` under
names their task suggests, so on macOS a Claude Code child runs under a sandbox
profile that refuses those writes outside its own directories (`private_tmp` in `dev/leaf_dev/arms.py`); its own
`TMPDIR` takes them, and two complete tasks can run together. A Codex child still
shares `/tmp`, so run its complete tasks at `-j 1`. The decision round's user agent
drives the page with the host's `playwright-cli`. Native Codex probes install the complete arm through the
host Codex CLI's plugin installer in that home, and use the same CLI to run the
read-only task. `MODELS` in `dev/leaf_dev/arms.py` pins the agent and judge
models. The `llm-rubric` judge grades text and opens nothing. The screenshot judge
runs on the installed `codex` under a permission profile that lets it read the
run's `screenshots/` and no other file of the repository. Promptfoo counts a
judge's tokens but not its cost, and doesn't record which screenshots it opened, so
read its reason. No judge has been calibrated against human judgments, so treat a
judged pass as weak evidence and read the outputs.

Another judge may grade the same samples differently, so a judged difference is
partly the judge's. To compare judges, point `screenshot_judge` in
`dev/leaf_dev/eval.py` at another model or provider (an `anthropic:claude-agent-sdk`
grader restricted to `Read` on the screenshot tree works), rerun the same cases, and
compare the runs in the viewer, starting with the `dashboard/reader-*` calibration.

These cases score instruction use and the agent loop. `leaf-dev journey` covers
plugin installation, discovery and hooks on each harness, and `leaf-dev verify-site`
the website.

```sh
pnpm run test:evals
uv run pytest tests/model/test_eval.py tests/model/test_scenario_eval.py tests/*/test_usability_eval.py tests/*/test_arrangement_eval.py -q -n0
```
