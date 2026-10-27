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
uv run leaf-dev eval 'website-replies*' --harness codex --base -j 1
uv run leaf-dev eval todo-outlasts-the-turn --harness claude-code --base
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
  another version of Leaf through it. The hosted `website-replies` experiment
  requires producer-owned hosted-turn diagnostics in each arm; an arm without
  them is refused before a native turn starts.
- **Harnesses.** `--harness claude-code`, `codex` or `both`, with no default. The selected harness uses its model pin in `dev/leaf_dev/arms.py`.
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

A complete authoring task has one final live quality judge. It returns `pass`, `defect`, or `insufficient_evidence`; native execution or invalid
judge output is `unscored`. Read
`gradingResult.componentResults[].metadata.authoring_grade` in saved results for
that status and its reason. Promptfoo's binary pass rate counts only `pass` as
passing, so its failure percentage is not a page-defect rate.

The judge explores disposable live copies of the final page and, where applicable,
the page before the user's decision, at the declared window sizes. It chooses which controls, disclosures and scroll routes to inspect,
and reads screenshots it takes. The harness serves disposable page copies and
supplies the existing browser CLI; the judge opens and operates its own browser.
The native agent stream and its screenshots retain the evidence. Report
screenshots show arrival only. Unvisited required content remains
insufficient evidence, while supported defects still fail when other parts remain
unobserved. The judge follows the requested output's scope. Where every page judged
is a Leaf page and one shows a workspace on arrival, the judge's task also carries
what `dev/leaf_dev/pane_readings.py` measured of each of its regions: how far it
scrolls, how much of it is empty and which Tab press reaches it. A pair judge
comparing Leaf with HTML gets none, so neither side alone carries measured defects.
The judgment's `metadata.judge.metadata.panes` keeps them.

## Viewports, saved comparisons and discovery

For the goal, task/model/viewport selection, sampling, improvement loop and
acceptance decisions, use the
[hill-climbing playbook](../.claude/skills/hill-climb-ui/SKILL.md).
This section describes the commands that execute a selected experiment.

`evals/workflows/eval.yaml` owns viewport presets and the default. Case definitions
do not select resolutions. Use `--viewport short` or `--viewport phone` to choose
an alternative; repeat the option to inspect several sizes within each sample.
The first selected size drives the comment and decision journey. All selected
sizes reach the author's window preference, report captures and final judge.
This does not multiply author runs or judges.

```sh
uv run leaf-dev eval patch-review --harness codex --condition both --viewport desktop
uv run leaf-dev eval patch-review --harness codex --condition leaf --viewport short --repeat 1 -j 1
```

### Compare saved samples

`leaf-dev eval-pairs RUN...` compares two provider columns, pairing each column's
Nth sample and judging each pair in both presentation orders. A winner is counted
only when both completed live judgments name it. Decision controls are judged on
the latest saved version before the decision; final evidence, layout, comment
responses and recorded decisions are judged on the final revision. Both use the
sample's original runtime. Each sample captures its task inputs, author phase
order, comparison phase roles and viewports before authoring in `comparison.json`
and returned diagnostics. Saved inputs remain authoritative if the catalog changes;
the judge methodology comes from the current checkout. Incomplete or unlike task
inputs raise an error. Unverified required observation is insufficient evidence;
a failed judge is unscored.

```sh
uv run leaf-dev eval-pairs .tmp/eval/<leaf-run> .tmp/eval/<html-run> .tmp/eval/<html-repeat> .tmp/eval/<leaf-repeat>
```

Each sample's final rubric is its absolute-quality judgment. Pairwise grading
adds a relative comparison without rerunning the author. The command writes
`pairs.json` and per-order evidence under `pairs/` in its first input run; running
it there again can replace an earlier comparison. Use fresh copied indexes for
each retained comparison, as in "Independent live audits" below, with `-` for
the default judge. Render the report from those copied run directories.

### Explore a saved sample

`leaf-dev eval-discover RUN SAMPLE [--focus TEXT]` gives an agent a saved sample
and its original runtime. The agent chooses window sizes and interaction sequences
from the requested focus and what it observes.

```sh
uv run leaf-dev eval-discover .tmp/eval/<run> <sample-directory-name> --focus 'Explore short desktop windows and decision undo.'
```

Each attempt retains observations, viewport, reproduction steps, evidence,
unverified work and a proposed next check under
`RUN/discovery/SAMPLE/attempt-*/response.json`, beside native traces and captures.

### Render a report

`leaf-dev eval-report PAGE RUN...` replaces `PAGE/index.html` with one Leaf report
of the selected runs. Its Outputs view links every sample to its saved pages,
screenshots, checks and grading reasons, including failed attempts and unequal
repetitions. Task views collect the arms and saved phases; pairwise judgments and
exploratory observations retain their separate meanings. Mechanical checks alone
do not establish page quality.

The report reads the saved requests, runtimes and viewport dimensions. Short
authoring cases retain their final render-check captures and page in the same
result metadata as complete workflows. Missing evidence remains visible. Saved
Leaf pages export from disposable copies of those phases; local previews and
navigation work, while comments and agent submissions need a live session.
Plain HTML retains its authored files.

To open outputs and raw evidence in the browser, serve the report's `evidence/`
directory on a separate static origin and give its URL to the generator. Leaf's
page server continues to serve the report and screenshots. For example, replacing
`HOST` with the machine's browser-reachable hostname:

```sh
uv run leaf-dev eval-report ~/.tmp/leaf/eval-comparison .tmp/eval/<run> --output-url http://HOST:57912
uv run python -m http.server 57912 --bind 0.0.0.0 --directory ~/.tmp/leaf/eval-comparison/evidence
```

Start the report with `bin/leaf server start ~/.tmp/leaf/eval-comparison` in another
terminal. Without `--output-url`, the report names exported files without linking
to an unavailable server. Regenerate the same report with additional run directories
to keep one entry point for a campaign.

For an improvement campaign, pass `--review FILE` with an agent-authored JSON
assessment. The report is a workspace: its title and navigation stay in view
while the selected result scrolls. **Changes tested** opens one intervention at a
time, with an explicitly labeled recommendation and matched before/after outputs.
Before/after captures use Leaf’s comparison viewer for Slider, Pair and pixel views,
with shared scale and synchronized scrolling at 100%. Output links sit below the
viewer. Other paired captures share caption and image rows, including when their
links wrap. **Latest outputs** separates the
current validation from earlier attempts in **All outputs**. Run identifiers,
costs, source code and methodology sit in details beside the output they describe.
Checks distinguish a finished author, a saved output and render validation;
quality assessments retain their criteria and reasons. The agent supplies the
causal interpretation; the renderer never infers improvement from a passing score
or calls feedback turns independent before/after authors.

Keep the review beside the run results. Paths below are absolute, and every run
referenced by the review is also an argument to `eval-report`. A latest run group
can include several executions, such as a short case and a longer workflow.

```json
{
  "title": "UI improvement campaign",
  "latest": {
    "title": "Latest validation",
    "runs": ["/absolute/path/to/run"],
    "summary": "What this run establishes and what it cannot establish.",
    "findings": [
      {
        "run": "/absolute/path/to/run",
        "sample": "sample-name",
        "finding": "Observed outcome."
      }
    ]
  },
  "experiments": [
    {
      "id": "change-name",
      "label": "Short navigation label",
      "title": "The change tested",
      "period": "When this experiment ran",
      "change": "The intervention and its intended effect.",
      "recommendation": "Keep, revise or reject",
      "reason": "What improved, regressed or remains unproven.",
      "limits": "Conditions and limits of this evidence.",
      "comparisons": [
        {
          "label": "Short task label",
          "title": "Task and repetition",
          "summary": "Desktop: After preferred · Phone: Before preferred",
          "before": { "run": "/absolute/path/to/run", "sample": "before-sample" },
          "after": { "run": "/absolute/path/to/run", "sample": "after-sample" },
          "finding": "What the matched outputs show.",
          "evidence": ["/absolute/path/to/judgment.json"]
        }
      ],
      "evidence": ["/absolute/path/to/change.diff"]
    }
  ]
}
```

The optional `label` fields shorten navigation without shortening the evidence's
title; a comparison's optional `summary` gives the assessment beside its images,
with the full `finding` in details. Use empty comparison/evidence arrays where
no such evidence exists, and say why in the assessment. Screenshot evidence
renders inline; other files are linked.
Same-page runtime probes and sequential repairs describe that scope explicitly.
Without a review, the report remains a result browser and says no change-retention
assessment was supplied.

`pnpm run eval:view` opens Promptfoo's diagnostic viewer on every run recorded on
this machine, each named by branch, commits and cases. It shows each sample's
output, assertion reasons, metadata, cost and tokens, and compares runs.

Authoring cases and complete tasks keep their evidence (prompts, native traces,
page directories) under `.tmp/eval/<run>/samples/`, one directory per sample named
by its case, and each sample's `metadata.work` names its directory. Original runtime
arms are retained under `arms/` for later live grading. A judged sample's screenshots
are under `screenshots/`, in a directory of the same name. `results.json` there
holds the whole run.

Executor turns, live sessions, and native Codex provider calls allow six hours;
the outer workflow provider allows a day for multiple turns and artifact checks.
Elapsed time is diagnostic, separate from correctness. Promptfoo records
provider-call duration in `latencyMs`.
Native duration, where a workflow reports it, is unknown when its trace lacks
completion timing; it is never filled in as zero. A Leaf live session's existing
`eval_served` observation retains the active revision and event boundary beside its
observation time. This identifies an available candidate, not first HTTP response,
handoff or usability; HTML controls have no equivalent early revision history.

## Case format

A short case is one prompt with native assertions: `vars.prompt` carries the
request, and `assert` judges what the agent wrote, its markup, code and prose, with
`llm-rubric` assertions that each state the property the case is about. A `regex`
or `not-regex` matches only a literal the reply must or must not contain, such as a
command name or a URL: replies spell markup and commands in too many ways (attribute
order, quoting, launcher paths, continued lines) for a pattern to grade them. The
runner invokes the installed arm's Leaf skill through Codex's native skill input
for source and reading probes; Claude Code receives a request to use the plugin's
skill. These probes may only read (Claude Code's Skill and Read tools; Codex's
read-only sandbox), so a prompt that needs a page asks for its HTML in the reply,
and one that grades what the
agent would do asks for the commands it would run. The runner tells such a probe
the time first, `now` in `workflows/eval.yaml` or the case's own `vars.now`, so
the ages its fixtures' times give hold whenever it runs. Opus 5.5's safeguards refuse a
prompt asking for its tool calls with their JSON input. The leading comment records
where the case came from and what it measured, `metadata.purpose` the behavior it
pins, and `metadata.tags` its area. `description` is the short task name shown in
reports (for example, "CSS cascade survey"); the directory address remains the case
ID used for selection and grouping.

A short case that needs real authoring declares `metadata.authoring: true`.
Its agent has native file and command tools, an initialized writable page, the
arm's launcher first on `PATH`, and a fresh workspace, home, temporary directory and
Leaf state for every sample. Pinned files under `evals/<case>/` are copied into
that workspace at the same relative paths. Cite those paths in the prompt; the
agent can open, register, crop or mark the captures. Ask it to write the page.
Assertions grade the saved `index.html`, with additional `completed` and
`page-valid` checks; the executor independently runs `page check`, plain and with
`--render`, and keeps the page, native trace, reply, and check output under the
sample's evidence. A prompt may reuse a complete task's request by naming it, as
`file://<task>/request.md`. A `python` assertion naming
`dev/leaf_dev/page_defects.py` grades the page by the defects its user would notice
at three widths, beside what the checks reported; its header says what it records,
and `page-reads-at-every-width` uses it. A visual `agent-rubric` can use `metadata.capture_evidence` to compare original
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

A complete task names `metadata.executor`, a `leaf_dev` Python module, and
`metadata.scenario`, a case in `workflows/<module-name>.yaml`. That YAML owns the
authored prompts, scenario inputs and native Promptfoo `assert` blocks, including
text `llm-rubric` and screenshot `agent-rubric` assertions. Complete authoring
tasks use one JavaScript assertion to pass the final live judge's verdict through
the Python provider. Shared request files
and fixture data stay beside their tasks and are read by the executor.
`arrangement_eval` copies pinned assets under `evals/<task>/` to the same relative
path in each author's isolated workspace, as short authoring cases do.

Python prepares fixtures, drives live chat turns or user input through the page,
and extracts evidence. Complete authoring tasks have only two execution
checks: the author completed all turns, and a final page exists. The one live
judge owns result correctness, including decision values and the requested
comment changes. The installed skill owns the author's review workflow; the harness does not
repeat render checks or run a separate decision-reading agent after every sample.
Other executors declare their execution facts in `expected_checks`. Semantic grading stays with Promptfoo: anything said
in prose, a reply or a passage on the page, goes to the text judge. A text rubric's
`transform` can hand the judge one entry of the response's `metadata.texts`, such
as one phase's reply or one paragraph, in place of the whole output. A screenshot executor lists captures beside the request
they answer and writes them to the supplied `shots` directory, the only place its
judge may read. `metadata.conditions` and `metadata.harnesses` restrict where it runs.

`metadata.authoring` and `metadata.executor` select distinct execution modes;
declaring both on a case, including through inherited variant metadata, is an error.

| Executor           | Runs                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `arrangement_eval` | One live author builds the page, receives the width preference and passage comment, and applies the browser user's decision; a scenario's `revision` then changes what the page is for, and `request` names another task whose request it starts from. Leaf uses its installed plugin and anchored comments; HTML uses chat and the page's copy route or a typed decision. Python retains the revisions, native traces, final/predecision screenshots and author accounting. One final live judge checks the outcome and operates the earlier decision controls. Optional `eval-pairs` compares saved samples. |
| `usability_eval`   | Seeded pages read, resumed and revised, and live handoffs where the driver posts user updates through the served page. One agent rubric judges the task from canonical page state, active markup, data, events, delivery envelopes and the full native trace. The driver retains exact input, turn and progress observations as metadata; it does not grade per-case tags, card counts or word ratios. Fixtures are in `usability/fixtures/`.                                                                                                                                                                  |
| `delivery_eval`    | Comments posted between turns and mid-turn through the shared live session. `parent-keeps-leaf-responsive/during-work` adds a repair task and consecutive comments. The response-times query retains exact first feedback, answers and missing observations at a fixed cutoff. The fixture checks the retained repair; semantic rubrics judge answers and the published result. A completed addressed reply checks thread closure separately from task correctness and page content. Native parent and worker traces are retained by the session.                                                              |
| `website_eval`     | Runs the arm's hosted App Server adapter and installed plugin on its configured model and reasoning effort. Asks a page question and a contextual follow-up, without requesting page construction. Queries the adapter's private page diagnostics for native turn status, the opening and final reply updates actually published, and follower completion after cleanup. Retains exact-input completed replies. Checks successful turns, replies and an unchanged page; judges whether the answers and visible openings address the user.                                                                      |
| `reader_eval`      | Calibrates the screenshot judge: `dashboard/reader-seeded` and `reader-clean` each show it one triage board, with a seeded count defect or the correct count, and ask both whether the count matches the cards.                                                                                                                                                                                                                                                                                                                                                                                                |

The responsiveness workload uses the same stream session as other live evals.
It does not force native compaction: that required a separate interactive driver,
and these cases do not establish compaction as the cause of reply delays.

`sidebar-page-at-900px` runs the complete authoring and render loop. Its
`/instructions` diagnostic retains the read-only source probe, and `/live` checks
the contrasting bounded live stream. The final live judge reads the rendered record: the completed log grows in
document flow, and checks and navigation stay reachable while reading, including
in the short window. Source-property checks in the
instruction diagnostic do not establish that rendered behavior.

## Isolation and models

Every provider runs in a fresh workspace outside the repository, under a home of its
own using only the host's login, so runs spend the signed-in accounts'
usage and never an API key. Authoring agents write scratch files in `/tmp` under
names their task suggests, so on macOS a Claude Code child runs under a sandbox
profile that refuses those writes outside its own directories (`private_tmp` in `dev/leaf_dev/arms.py`); its own
`TMPDIR` takes them. Eval defaults to serial provider calls and assertions for
browser load. The decision round's user agent drives the page with the pinned
Playwright CLI from development dependencies. Native Codex probes install the complete arm through the
host Codex CLI's plugin installer in that home, and use the same CLI to run the
read-only task. `MODELS` in `dev/leaf_dev/arms.py` owns the model pins. Native
Codex turns use the Codex harness pin, including the final live judge and optional
pair judges; their reasoning effort is medium. Text grading uses `judge`, the
browser user uses `user`, and static screenshot grading uses `screenshots`. Hosted response
cases instead read the model, reasoning effort and
instructions from each arm's website adapter, so they follow the deployed agent
configuration. They use the local login and adapter, without the Worker, container
or browser; `leaf-dev journey website-adapter` and the website delivery checks
cover those boundaries. The `llm-rubric` judge grades text and opens nothing. The screenshot judge
runs on the installed `codex` under a permission profile that lets it read the
run's `screenshots/` and no other file of the repository. Promptfoo counts a
judge's tokens but not its cost, so read its reason and recorded evidence. Complete
authoring judges instead use the pinned Playwright CLI and the existing Codex
agent runner to operate live copies. The judge has ordinary tool access and owns
browser setup and exploration; the harness retires its browser sessions when the
turn ends. Each judgment retains the native agent trace and screenshots under its
sample. Its task asks for rendered evidence, keeps exploratory choices distinct
from authored state and excludes expected verdicts. Run complete-task grading
serially (`-j 1`) to bound browser load.
Successful execution does not prove the judge understood every image. Read its
actions, screenshots and reasons before accepting a judgment.

Another judge may grade the same samples differently, so a judged difference is
partly the judge's. For static screenshot cases, point `screenshot_judge` in
`dev/leaf_dev/commands/eval.py` at another model or provider (an `anthropic:claude-agent-sdk`
grader restricted to `Read` on the screenshot tree works), rerun the same cases, and
compare the runs in the viewer, starting with the `dashboard/reader-*` calibration.
That setting does not change complete-task live judges. Their model follows the
Codex harness pin; `eval-pairs` rejudges saved samples with the current live judge
while retaining their original authored pages and runtimes.

### Independent live audits

This recipe creates an isolated output directory for one comparison and can
optionally select another judge model served by the Codex login. Use `-` instead
of the model name to keep the current default judge. The indexes retain absolute sample and runtime paths; links keep screenshots and
discovery evidence available to the report without copying captures. The
standard pair command handles both presentation orders and writes its evidence
under the new directories. The override changes no shared model pin or original
verdict. For example, audit one completed Leaf/HTML pair with Astra:

```sh
uv run python - gpt-6-astra .tmp/eval/<leaf-run> .tmp/eval/<html-run> <<'PY'
import shutil
import sys
import tempfile
from pathlib import Path

from leaf_dev.arms import MODELS
from leaf_dev.commands.eval_pairs import eval_pairs

audit = Path(tempfile.mkdtemp(prefix="audit-", dir=Path(".tmp/eval").resolve()))
runs = []
for index, source in enumerate(sys.argv[2:]):
    target = audit / str(index)
    target.mkdir()
    source = Path(source).resolve()
    shutil.copyfile(source / "results.json", target / "results.json")
    for name in ("screenshots", "discovery"):
        if (source / name).is_dir():
            (target / name).symlink_to(source / name, target_is_directory=True)
    runs.append(str(target))
if sys.argv[1] != "-":
    MODELS["codex"] = sys.argv[1]
print("Comparison indexes:", *runs, sep="\n")
eval_pairs.main(args=runs, standalone_mode=False)
PY
```

Verify the model in each native `err.codex.jsonl` trace's `thread/started`
notification (`params.thread.model`), then inspect the judge's actions and images.
These audits retain the Codex harness's medium reasoning effort. Opus authoring
uses `--harness claude-code`; selecting a different Codex model does not change
the harness. Cross-harness authoring and independent judging answer different
questions.

These cases score instruction use and the agent loop. `leaf-dev journey` covers
plugin installation, discovery and hooks on each harness, and `leaf-dev verify-site`
the website.

Benchmark runs are development experiments, not release gates. Run a selected
case when changing its behavior, inspect its saved pages and judge evidence, and
repair mistakes in that loop. Keep only a couple of no-model smoke tests for the
provider wiring in `dev/tests`; these and other `leaf-dev` tests run explicitly,
outside product PR CI.
