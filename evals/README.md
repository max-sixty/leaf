# Leaf evals

Each `evals/<task>/case.yaml` is a Promptfoo test that runs on Claude Code and Codex.
`leaf-dev eval` builds the Leaf arms, turns the selected cases into a Promptfoo
config, and runs `promptfoo eval`; Promptfoo does the rest.

A folder here with a `promptfooconfig` of its own is an experiment, which its README
says how to run (`dev/AGENTS.md`, "Experiments"). The commands below run the cases.

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
- **Arms.** `head`, the working tree, always runs. `--base` adds the merge base
  with `main` as a second arm, `base`, and `--base REF` adds that ref; put cases
  before it. An arm holds only the plugin payload, with no git history, so an agent
  can't look up another version of Leaf through it. The hosted `website-replies` experiment
  requires producer-owned hosted-turn diagnostics in each arm; an arm without
  them is refused before a native turn starts.
- **Harnesses.** `--harness claude-code`, `codex` or `both`, with no default. Author
  models use `MODELS` in `dev/leaf_dev/arms.py`; judging uses the separate
  `JUDGE_MODELS` pins. The hill-climbing playbook owns judge selection. `--model MODEL`
  selects one Codex author model for every selected condition in that run.
- **Conditions.** `--condition html` runs the plain HTML control on the tasks whose
  `metadata.conditions` declare one; `both` runs it beside Leaf. The control gets
  the same request, revisions and judge with no Leaf skill, runtime or widgets.
- **Promptfoo options.** Anything after the cases goes to `promptfoo eval`, such as
  `--repeat 3`, `-j 4` or `--filter-pattern`.

## Reading the results

Promptfoo prints a table with a row per test and a column per provider: a harness on
one arm (`claude-code/head`, `codex/base`), suffixed `/authoring` for short
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
the pages before the user's decision and final revision request, at the declared
window sizes. The page before that last request supplies the starting point for
judging what the revision preserves or changes. It chooses which controls, disclosures and scroll routes to inspect,
and reads screenshots it takes. The harness serves disposable page copies and
supplies the existing browser CLI; the judge opens and operates its own browser.
User and judge browsers grant clipboard access, so a page's Copy route can complete
in the headless shell as it does in the host browser.
The native agent stream and its screenshots retain the evidence. Report
screenshots show arrival only. Unvisited required content remains
insufficient evidence, while supported defects still fail when other parts remain
unobserved. The judge follows the requested output's scope. Where every page judged
is a Leaf page and one shows a workspace on arrival, the judge's task also carries
what `dev/leaf_dev/pane_readings.py` measured of each of its regions: how far it
scrolls, how much of it is empty and which Tab press reaches it. A pair judge
comparing Leaf with HTML gets none, so neither side alone carries measured defects.
The judgment's `metadata.judge.metadata.panes` keeps them.

## Viewports and saved samples

For the goal, task/model/viewport selection, sampling, improvement loop and
acceptance decisions, use the
[hill-climbing playbook](../.claude/skills/hill-climb-ui/SKILL.md).
This section describes the commands that execute a selected experiment.

`WINDOWS` in `dev/leaf_dev/browser.py` names the windows a run can open, and
`evals/workflows/eval.yaml` sets the default. Case definitions do not select
resolutions. Use `--viewport NAME` to choose another window; repeat the option to
inspect several sizes within each sample.
The first selected size drives the comment and decision journey. All selected
sizes reach the author's window preference, report captures and final judge.
Full workflows introduce that preference after the first draft; short authoring
cases include it in the initial request. This does not multiply author runs or
judges, but it changes the task the author must satisfy. To inspect another size
without changing that task, explore the saved sample with `--judge discovery` below.

```sh
uv run leaf-dev eval patch-review --harness codex --condition both --viewport desktop
uv run leaf-dev eval patch-review --harness codex --condition leaf --viewport short --repeat 1 -j 1
```

### Grade saved samples again

`leaf-dev eval --from RUN` grades a retained run's saved outputs again without
rerunning their authors. Each saved output becomes a test in its original column,
graded by its case's assertions as this checkout states them, so a changed rubric,
check or judge can be measured on outputs that already exist. Repeat `--from` to
grade several runs together. CASE globs select cases from the saved runs, and
Promptfoo's options follow them as usual: each test's description ends with its
sample's directory name, so `--filter-pattern NAME` selects one sample, and
`--repeat 3` judges each sample three times to show the judge's own spread. The
options that choose what to author, such as `--base` and `--harness`, don't apply.

```sh
uv run leaf-dev eval --from .tmp/eval/<run> page-reads-at-every-width/dashboard
```

The grading is a run like any other, in Promptfoo's store and viewer, with its
config and `results.json` in a new directory under `.tmp/eval/`. A judge that an
assertion runs keeps its evidence beside the sample, in a directory of its own, so
the earlier judge's stays. A result whose provider failed, such as an author that
did not complete, replays its error and stays ungraded, as it was the first time.
A case gone from the catalog has no current assertions to grade by. To read the
new grades in a report, render the grading run in place of the run it graded;
rendered together, each output appears once for each grading.

### Compare saved samples

`--judge pair` compares two provider columns of the saved runs, pairing each
task's Nth sample in one column with its Nth in the other, in the order the runs
and their results list them. Each pair is judged in both presentation orders, as
two tests in a column named for both. A winner is counted only when both completed
live judgments name it. Decision controls are judged on the latest saved version
before the decision; final evidence, layout, comment responses and recorded
decisions are judged on the final revision. Both use the sample's original
runtime. Each sample captures its task inputs, author phase order, comparison
phase roles and viewports before authoring in `comparison.json` and returned
diagnostics. Saved inputs remain authoritative if the catalog changes; the judge
methodology comes from the current checkout. Unlike task inputs fail the test.
Unverified required observation is insufficient evidence; a failed judge, or an
author that did not complete, leaves the pair unscored. A result that saved no
task at all, such as a provider timeout, is left out of the pairing.

```sh
uv run leaf-dev eval --from .tmp/eval/<leaf-run> --from .tmp/eval/<html-run> --judge pair
```

Each sample's final rubric is its absolute-quality judgment. Pairwise grading
adds a relative comparison without rerunning the author. Each judgment's evidence
goes under `judgments/` in the new run, so judging the same samples again adds a
comparison rather than replacing one. Render the report from the judging run and
the runs it judged.

### Explore a saved sample

`--judge discovery` gives an agent each selected saved sample and its original
runtime. The agent chooses window sizes and interaction sequences from the focus,
which Promptfoo's `--var focus=TEXT` sets, and what it observes.

```sh
uv run leaf-dev eval --from .tmp/eval/<run> --judge discovery --filter-pattern <sample-directory-name> --var focus='Explore short desktop windows and decision undo.'
```

Each test's assertion metadata keeps the judge's response as `judge`, with the
observations, viewport, reproduction steps, evidence, unverified work and a
proposed next check in its output, and the native traces and captures go under
`judgments/` in the new run. The test passes when the exploration finished,
whatever it found.

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
to keep one entry point for a hill-climbing journey.

The browser's **Judge preferences** view reads each retained native pair judgment
and shows both presentation orders separately. Its five overall preference categories
are ordinal, not numerical quality scores or independent author replications. Only
pairs identified by their saved output metadata as one Leaf and one Plain HTML output
appear on the format axis; other pairs remain in the exact-outcome table. Saved-output
views lead with the page and its interactive copy, with earlier phases and other
captured sizes beneath it.

For a hill-climbing journey, write a review and pass it with `--review FILE`. It is
ordinary Leaf markup (`skills/leaf/SKILL.md`): the report's `<h1>` and any lede, then
an `lf-tabs` of its views, to which the report adds the browser as a last tab,
**Outputs**. The report writes the document around the review, titling it with the
`<h1>`'s text and giving it a fixed description, so the review starts at its `<h1>`.
`leaf page check PAGE` validates the regenerated report as it does any
page. Reports stay comparable across a campaign when they keep the same sections, so
keep these, leaving out one only where the campaign has nothing for it:

```html
<h1 id="title">Keyboard judgment follows each control</h1>

<lf-tabs id="review-views">
  <lf-tab id="report-introduction" label="Introduction">
    <section id="latest-run">
      <h2>Latest validation</h2>
      <p>What changed in Leaf, what this journey establishes and what it cannot.</p>
      <table id="score-summary">
        <thead>
          <tr>
            <th scope="col">Comparison</th>
            <th scope="col">Scope / baseline</th>
            <th scope="col">Observed result</th>
            <th scope="col">Interpretation</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row"><a href="#experiment-keyboard">Approval trial</a></th>
            <td>0 of 2 passed</td>
            <td>2 of 2 passed</td>
            <td>Two authors per arm; not a population success rate.</td>
          </tr>
        </tbody>
      </table>
      <h3>Remaining defects and limits</h3>
      <ul>
        <li>What the evidence does not establish.</li>
      </ul>
    </section>
    <section id="campaign-journey">
      <h2>Campaign journey</h2>
      <lf-diagram id="campaign-flow" parts="all">
        <pre>
flowchart TD
  accTitle: Campaign study
  accDescr: The baseline split into a candidate and a control, then a comparison decided.
  baseline["Authoring · Baseline"] --> candidate["Repair · Candidate"]
  baseline --> control["Authoring · Saved control"]
  candidate --> decide["Judging · Compare and decide"]
  control --> decide
</pre>
      </lf-diagram>
    </section>
  </lf-tab>

  <lf-tab id="cases" label="Cases">
    <section id="case-navigation">
      <h2>Patch navigation</h2>
      <p>The task given to the authors.</p>
      <section id="case-navigation-baseline">
        <h3>Baseline outputs</h3>
        <p>What we observed, tried, learned and chose to do next.</p>
        <lf-eval-cite
          before="RUN/leaf-sample"
          before-label="Leaf baseline"
          after="RUN/html-sample"
          after-label="Plain HTML control"
        ></lf-eval-cite>
      </section>
    </section>
  </lf-tab>

  <lf-tab id="changes-tested" label="Changes to Leaf">
    <section id="experiments-retained">
      <h2>Retained changes</h2>
      <section id="experiment-keyboard">
        <h3>Keyboard judgment follows each control</h3>
        <p>Keep: the after arm passed 2 of 2 approval trials, against 0 of 2.</p>
        <p>
          The intervention, what improved or regressed, and the limits of this evidence.
        </p>
        <lf-eval-cite
          before="RUN/before-sample"
          after="RUN/after-sample"
        ></lf-eval-cite>
        <lf-eval-cite
          file="/absolute/path/to/change.diff"
          label="Exact retained change"
        ></lf-eval-cite>
        <lf-ask id="keyboard-review">
          <h4>Keep the keyboard change?</h4>
          <lf-options id="keyboard" choose>
            <lf-option id="keyboard-approve"><strong>Approve change</strong></lf-option>
            <lf-option id="keyboard-revisit"><strong>Revisit change</strong></lf-option>
          </lf-options>
        </lf-ask>
      </section>
    </section>
    <section id="experiments-rejected">
      <h2>Rejected trials</h2>
      <p>What each trial tried and why it was dropped.</p>
    </section>
    <section id="experiments-evaluation">
      <h2>Evaluation corrections</h2>
      <p>What changed in the grading or the report, and the original grades.</p>
    </section>
    <section id="experiments-exploration">
      <h2>Exploration and supporting evidence</h2>
      <p>Earlier runs, and tooling that page authors don't receive.</p>
    </section>
    <section id="implementation">
      <h2>What the current code changes</h2>
      <p>The retained code's size and interfaces, and how it was validated.</p>
      <h3>For your review</h3>
      <p>What each change means before and after, and why it deserves attention.</p>
      <h3>Weaknesses</h3>
      <p>Material limitations and where the assessment is least certain.</p>
      <h3>What is left undone</h3>
      <p>What remains within the stated scope.</p>
    </section>
  </lf-tab>
</lf-tabs>
```

A section left out reads as not assessed. Where you assessed one and found nothing,
keep its heading and say so with the reason, such as “No code changed; this campaign
only graded saved outputs again.” A diagram reserves no height before it draws, so
the content below it moves when it does. Set its `data-height` to the drawing's height
in pixels, which `leaf page check --render PAGE` reports wherever the two differ. The
value stays the diagram's minimum height, so a larger one leaves blank room under the
drawing.

`lf-eval-cite` reaches what an author can't write by hand, and the report replaces it
with elements Leaf ships, so the served page holds none. A citation that names an
output, phase or file the report can't find stops the report.

- `output="RUN/SAMPLE"`, with an optional `label`, draws the output's captures at each
  recorded viewport, its saved-page link and the author's model.
- `before="RUN/SAMPLE" after="RUN/SAMPLE"`, with optional `before-label` and
  `after-label`, draws two outputs side by side at the viewports both recorded.
  Independently authored outputs need their complete frames. Add `aligned` only for
  captures of the same source and state before and after a change, where the wipe in
  `lf-shot` can reveal that change.
- `file="/absolute/path"`, with an optional `label`, copies a retained file into the
  report's evidence: an image draws in place, a `.diff` draws in `lf-diff` beside its
  source link, and any other file is a link.
- `links`, added to any citation, draws text in place of its captures, image or diff,
  and that text can stand inside a `<p>`, as can a citation of any other kind of file.
  For each output it draws the label, the saved page and a link to the output's
  details, with its condition, author model and phase on a line of their own; for a
  file, a link to the file. Without `--output-url`, each saved page and file shows as
  its path instead of a link. A citation that draws anything else stands where a block
  can, outside a `<p>`.

`RUN` is the name of a run directory given to `eval-report`. `SAMPLE` is the directory
`metadata.work` names, which an output's run details show as its Output ID. `SAMPLE@3`
selects the page as the sample's third phase left it: a workflow sample keeps phase N
in `page-phaseN`, and a short authoring case has only `@1`. Without `@`, the citation
shows the final phase. A workflow captures only the phases its `comparison.json` names:
the final one and, where the case has them, `_before_decision` and `_before_revision`.
Any other phase draws “No screens.” beside its links, and the checks pass. Choose the
state the change affects, such as the page before a later user request corrects its
layout. For the controls before a decision is recorded, cite the phase
`comparison.json` lists as `_before_decision`, which the report labels “Before
decision”. Give a citation an `id` where the review links to it or cites the same
thing twice. The cited sample's checks in the browser link back to each citation drawn
without `links`, and the browser's tasks follow the order the review first cites them.

Each section keeps what its reader needs to judge it:

- A case is the task given to an author; an output is one saved authored page. An
  experiment tests a hypothesis, and a run is an eval execution. Reusing an output in
  a comparison creates no second author attempt, and a fresh author at a later
  checkpoint doesn't isolate the effect of a repair. Same-page runtime probes and
  sequential repairs state that scope. A case's section shows the outputs its authors
  produced, including a Leaf output beside its plain HTML control, and a before and
  after of one change goes under that change's experiment. A Leaf output and its plain
  HTML control come from independent authors, so say in the prose that their
  differences don't show the effect of a change to Leaf.
- A score row states its denominator and meaning, keeping an experiment's pass counts
  separate from ordinal pair preferences. Qualifications that apply to the recorded
  reviews go beside the scores. Name the arms for the reader in the review; the browser
  keeps their recorded labels. Pass each pair-judgment run to `eval-report` too, so the
  Judge preferences view shows its pairs, and don't retype that view's winners or
  margins. Beside it, say which retained changes the judged pairs were produced under,
  which no pair covers, and which author or model changes limit the reading. Report a
  before and after observation of one source page as its own table or prose, never as
  a preference or a score.
- A title names concrete behavior, so a reader can tell what changed without the
  campaign's terminology. The diagram's edges state observed dependencies or decisions,
  rather than inferring causality from timestamps. Order cases and steps as the campaign
  took them, not by score or file time, and leave parallel lanes unordered against each
  other. Keep the original grades when explaining a change to an evaluation contract.
- Only a change selected for the user's decision gets an `lf-ask`, with a scoped exact
  diff to read. Scores never make that decision, and existing authorization and landing
  rules still govern what follows from it. Link a change to an experiment only where
  one tested it; a grading or report change has none.

The report selects the `diff` and `diagram` packages and keeps any already on the page;
select another with `leaf page init PAGE --package NAME` before regenerating it.

`pnpm run eval:view` opens Promptfoo's diagnostic viewer on every run recorded on
this machine, each named by branch, commits and cases. It shows each sample's
output, assertion reasons, metadata, cost and tokens, and compares runs.

Authoring cases and complete tasks keep their evidence (prompts, native traces,
page directories) under `.tmp/eval/<run>/samples/`, one directory per sample named
by its case, and each sample's `metadata.work` names its directory. Original runtime
arms are retained under `arms/` for later live grading. A judged sample's screenshots
are under `screenshots/`, in a directory of the same name. `results.json` there
holds the whole run.

### Recorded execution data

`results.json` is the run record, including its frozen Promptfoo configuration.
Each result's `provider.label` joins `config.providers[].label`; provider ids alone
are shared by multiple arms and models. That provider's `config` records the
requested author `model`. Workflow and authoring providers also record `harness`,
`condition`, runtime `payload` and selected `viewports`; native probe provider IDs
identify their harness and carry their own installed-skill configuration.
Reports read these saved values, never the current model pins. A copied
or recovered run index retains the provider configurations its results name.

The result's `testCase.metadata` distinguishes `authoring`, an `executor` workflow,
and other probes. `response.metadata.diagnostics.comparison.widths` records the
actual comparison dimensions in CSS pixels; selected viewport names in the provider
configuration remain distinct from those dimensions. Phase records hold the saved
pages, captures and native author traces. Each live judge's response records its own
model under `metadata.model`, separately from the author. `eval_records.py` reads
this identity for the report without introducing another stored representation.

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
Declaring `html` in `metadata.conditions` adds the plain HTML control, which gets
the same prompt without the Leaf skill prefix, an empty directory and the headless
Chrome path; its `page-valid` means the page loaded without script errors. A
case that declares more than one condition gives its judges each page on arrival
at the run's windows; a Leaf-only case also gives them the render check's screens.
Assertions grade the saved `index.html`, with additional `completed` and
`page-valid` checks; the executor independently runs `page check`, plain and with
`--render`, and keeps the page, native trace, reply, and check output under the
sample's evidence. A prompt may reuse a complete task's request by naming it, as
`file://<task>/request.md`. The selected `--viewport` sizes reach the author in its
request and determine the report captures; the render check retains its own wider
diagnostic sweep. A `python` assertion naming
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

| Executor           | Runs                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `arrangement_eval` | One live author builds the page, receives the width preference and passage comment, and applies the browser user's decision; a scenario's `revision` then changes what the page is for, and `request` names another task whose request it starts from. Leaf uses its installed plugin and anchored comments; HTML uses chat and the page's copy route or a typed decision. Python retains the revisions, native traces, comparison screenshots and author accounting. One final live judge checks the outcome against its decision and revision starting points. `--from --judge pair` compares saved samples.                                                                                                                                                          |
| `usability_eval`   | Seeded pages read, resumed and revised, and live handoffs where the driver posts user updates through the served page. One agent rubric judges the task from canonical page state, active markup, data, events, delivery envelopes and the full native trace. The driver retains exact input, turn and progress observations as metadata; it does not grade per-case tags, card counts or word ratios. Fixtures are in `usability/fixtures/`.                                                                                                                                                                                                                                                                                                                           |
| `delivery_eval`    | Comments posted between turns and mid-turn through the shared live session. `parent-keeps-leaf-responsive/during-work` adds a repair task and consecutive comments. The response-times query retains exact first feedback, answers and missing observations at a fixed cutoff. The fixture checks the retained repair; semantic rubrics judge answers and the published result. A completed addressed reply checks thread closure separately from task correctness and page content. Native parent and worker traces are retained by the session.                                                                                                                                                                                                                       |
| `website_eval`     | Runs the arm's hosted App Server adapter and installed plugin on its configured model and reasoning effort. Asks a page question and a contextual follow-up, without requesting page construction. Queries the adapter's private page diagnostics for native turn status, the opening and final reply updates actually published, and follower completion after cleanup. Retains exact-input completed replies. Checks successful turns, replies and an unchanged page; judges whether the answers and visible openings address the user.                                                                                                                                                                                                                               |
| `reader_eval`      | Calibrates the screenshot judge: `dashboard/reader-seeded` and `reader-clean` each show it one triage board, with a seeded count defect or the correct count, and ask both whether the count matches the cards.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `fork_eval`        | Replays Leaf's conversation forks on short constructed conversations: `turn-end-check/*` for the clerk's turn-end check, `line-fork/*` for a kept-back thread's working line. The arm's Leaf builds the page and session and writes the question; `claude -p --resume` answers it from the rendered transcript; the arm's Leaf takes the answer, and the score reads what it took, so an answer it refuses fails either fork. Turn-end items are matched to labels by the words they rest on, a labelled edit must remove the stale words from the page, and the text judge reads every item and change; the judge reads the working line a reply fork posted, and its judgment of who should do the work is checked against the case's `work` label. Claude Code only. |

The responsiveness workload uses the same stream session as other live evals.
It does not force native compaction: that required a separate interactive driver,
and these cases do not establish compaction as the cause of reply delays.

`sidebar-page-at-900px` runs the complete authoring and render loop. Its
`/instructions` diagnostic retains the read-only source probe, and `/live` checks
the contrasting bounded live stream. The final live judge assesses complete chronological
reading, usable space, and access to checks and navigation, including the cost of managing
scroll positions in a short window. The instruction diagnostic assesses the source;
it does not establish rendered behavior.

## Isolation and models

Every provider runs in a fresh workspace outside the repository, under a home of its
own using only the host's login, so runs spend the signed-in accounts'
usage and never an API key. On macOS, native authoring sessions use
`authoring_sandbox` in `dev/leaf_dev/arms.py` to isolate shared `/tmp` content and
host plugin payloads; their own `TMPDIR` holds scratch files. Read-only probes use
their provider's restrictions. Eval defaults to serial provider calls and assertions for
browser load. The decision round's user agent drives the page with the pinned
Playwright CLI from development dependencies. Native Codex probes install the complete arm through the
host Codex CLI's plugin installer in that home, and use the same CLI to run the
read-only task. `MODELS` in `dev/leaf_dev/arms.py` owns author and simulated-user
pins; `JUDGE_MODELS` owns quality judges independently. Native Codex author turns
use `MODELS["codex"]`; final live, pair and static screenshot judges use
`JUDGE_MODELS["codex"]`. Native Codex author, live and pair turns use medium reasoning
effort. Text grading uses the Claude
judge pin, and the browser user runs on Codex with `MODELS["user"]`. Hosted response
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
grader restricted to `Read` on the screenshot tree works), grade the same run again
with `--from`, and compare the runs in the viewer, starting with the
`dashboard/reader-*` calibration. That setting does not change complete-task live
judges. Their model follows the Codex judge pin, `JUDGE_MODELS["codex"]`, which
`--from` reads from the checkout it runs in: grading a run again from a checkout
with that pin changed cross-checks its live judgments with another Codex model,
on the original authored pages and runtimes.
Both live and pair judges receive each author's recorded decision handover alongside
the common task: the actual page events or copied/typed message can differ from the
prescribed decision summary. Those inputs establish what the final revision responds
to; they do not change the decision task the judge operates on the earlier page.

These cases score instruction use and the agent loop. `leaf-dev journey` covers
plugin installation, discovery and hooks on each harness, and `leaf-dev verify-site`
the website.

Benchmark runs are development experiments, not release gates. Run a selected
case when changing its behavior, inspect its saved pages and judge evidence, and
repair mistakes in that loop. Keep only a couple of no-model smoke tests for the
provider wiring in `dev/tests`; these and other `leaf-dev` tests run explicitly,
outside product PR CI.
