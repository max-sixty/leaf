# The `leaf-dev` package

`leaf_dev` is Leaf's developer tooling: the code the suite and the eval harnesses
share, and the `leaf-dev` commands built on it. `uv run leaf-dev --help` lists each
command with its summary, and each command's `--help` and module header say the rest.

Nothing in `src/` may import it; `dev/pyproject.toml` says who installs it.

A command writes under `.tmp/` unless its reader expects another path. The corpus
uses ignored `examples/corpus.*` paths so repeated previews keep their source identity.

## Where tooling goes

Keep developer tools easy to change while using them: let a failed local run show what
needs fixing rather than building product-level defenses around an experiment. A
benchmark runner tells an agent what to do and lets a judge assess the result; Promptfoo
runs the matrix, repetitions, concurrency, assertions and result storage, and custom
code covers only the agent and Leaf interactions being measured.

When agents keep writing the same throwaway script, make it a command: a module in
`leaf_dev/commands/` named after it, which the CLI finds by name (`cli.py`). A package
there is a group (`journey/chart.py` for `leaf-dev journey chart`): it gathers the
commands a developer reaches for together about one subject, while a command used
across subjects, such as `probe`, stands at the top. Tooling that CI, a hook or an alias runs is a command too,
so the repository has no directory of loose scripts. Code two tools need lives in one
module here that the others import, never through `sys.path`, `PYTHONPATH` or a file
path. A mechanism only one tool uses stays in that tool's file, and a command is named
for what it examines rather than for the mechanisms inside it, so the code a new tool
needs may sit in a command whose name doesn't suggest it. Before writing a mechanism,
or turning a script of your own into a command, search `dev/`, `evals/` and `src/leaf/`
for code that already does the job, by the calls it has to make (the widget whose markup it writes,
the library it draws or measures with) rather than by name, as `/developing-leaf`'s
**What it repeats** says. Move what you find into a module here that both tools
import. The modules beside `cli.py` hold what several tools share already, such as
the arms and harness sessions in `arms.py`, page directories in `page_fixtures.py`,
the browser in `browser.py`, and in `gallery.py` the Leaf page of captures a command
writes to show Leaf's drawing case by case. What a page or an input costs is
measured by `leaf-dev bench`, so a new page, input or reading belongs in
`commands/bench.py` (`COLLECTIONS`, `INPUTS`), whose header names what it reads.

## Experiments

`leaf-dev eval run` runs the catalog, the cases that score Leaf's shipped instructions on
its arms; a new case is `evals/<task>/case.yaml` (`evals/README.md`). Any other
question put to a model is an experiment. An experiment adds one folder under `evals/`,
and a `pnpm run eval:<name>` script that runs its config:

- `promptfooconfig.yaml` declares the arms as `providers`, the samples as `tests` and
  the graders as assertions. Use `promptfooconfig.mjs` where those have to be computed,
  as they are where providers name their models.
- The folder holds the config's `provider.mjs`, `grade.mjs` and fixtures, and a README
  saying how to run it and read the results.
- What a run must set up or summarise for the tests the config declares goes in
  Promptfoo's `beforeAll` and `afterAll` hooks, named under the config's `extensions`.
  Promptfoo applies its filters before `beforeAll` and takes no providers from it, so
  setup that produces the tests themselves runs before Promptfoo, in the script.
- A new comparison is another provider in the config, since a `--condition` value or
  option on `leaf-dev eval run` would stay in the catalog's code after the experiment ends.
  Promptfoo's own options choose what a run takes: `--filter-providers`,
  `--filter-pattern`, `--repeat`.

`evals/control-legibility/` produces its tests in its script, and
`evals/ui-review-detection/` prepares them in its hooks.

A `leaf-dev` command exists only for a mechanism two experiments share, so an experiment
gets none of its own. A mechanism stays in the first experiment's folder until a second
one needs it. It then moves into a module in `leaf_dev`, with a command if it is run on
its own.

An experiment's folder and script stay while someone will run them again. Once it has
answered its question, delete them, and have the pull request name the last commit that
holds them, so they can be restored from git.

Developer tooling picks the model it runs only through `MODELS`, `JUDGE_MODELS` and
`COMPARED_MODELS` in `arms.py`, so moving a pin moves every run. Node code reads them
through `leaf_dev/arms.mjs`, and a model new to a comparison goes in `COMPARED_MODELS`.
A table keyed by model id, such as `fork_eval.PRICES`, looks up what a run already used
and picks nothing.

## Tests

Developer-tool tests live in `dev/tests/` and run only when explicitly requested.
They are outside PR CI, main-push CI, the daily suite and landing gates, even when a
branch changes them. Keep product guarantees in `tests/`, even when a fixture uses a
developer helper.

A benchmark needs only a couple of broad smoke tests showing that a task reaches the
agent and its result reaches the grader; work out detailed failures while running the
experiment, not as a test per helper, output field or failure branch. Other tools may
keep focused tests where they save work, without making them a gate. Run only the
relevant selection:

```bash
uv run pytest dev/tests/test_evals.py -q -n0
pnpm run test:evals
```

`uv run pytest dev/tests` selects every Python developer-tool test.

## Commands with consequences outside `.tmp/`

- `leaf-dev site previews` (as `wt refresh-previews`), `site demo` and
  `site media` publish images to `max-sixty/leaf-assets`; in the tree they change
  only the pin
  in `leaf-assets.json` and the README's image URLs.
  `journey snapshots` accepts reviewed images by moving `leaf-assets.json`'s
  `thread_snapshots_revision`.
- `worker/deploy-dev.sh` (`pnpm run deploy:dev`) deploys the checkout to the
  `leaf-website-dev` environment. Production deploys only through
  `.github/workflows/publish-site.yaml`; `worker/README.md` owns diagnostics.
- `leaf-dev journey run` appends each sample to `$XDG_STATE_HOME/leaf-dev/journey.jsonl`. On
  a harness target it uses the host's authenticated accounts, as `leaf-dev eval run` does,
  so CI runs neither; `publish-site` runs the journey against each deployed release
  (`/developing-leaf`, "Run the agent journey" and "Score an instruction change").
