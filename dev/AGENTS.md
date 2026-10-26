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
`leaf_dev/commands/` named after it (`journey_chart.py` for `leaf-dev journey-chart`),
which the CLI finds by name. Tooling that CI, a hook or an alias runs is a command too,
so the repository has no directory of loose scripts. Code two tools need lives in one
module
here that the others import, never through `sys.path`, `PYTHONPATH` or a file path.
Before writing a mechanism, read the headers of the modules beside `cli.py`: `arms.py`
builds arms and isolated harness sessions, `page_fixtures.py` page directories, and
`browser.py` the browser every command drives.

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

- `leaf-dev refresh-previews` (as `wt refresh-previews`), `record-demo` and
  `publish-media` publish images to `max-sixty/leaf-assets`; in the tree they change
  only the pin
  in `leaf-assets.json` and the README's image URLs.
  `thread-snapshots` accepts reviewed images by moving `leaf-assets.json`'s
  `thread_snapshots_revision`.
- `worker/deploy-dev.sh` (`pnpm run deploy:dev`) deploys the checkout to the
  `leaf-website-dev` environment. Production deploys only through
  `.github/workflows/publish-site.yaml`; `worker/README.md` owns diagnostics.
- `leaf-dev journey` appends each sample to `$XDG_STATE_HOME/leaf-dev/journey.jsonl`. On
  a harness target it uses the host's authenticated accounts, as `leaf-dev eval` does,
  so CI runs neither; `publish-site` runs the journey against each deployed release
  (`/developing-leaf`, "Run the agent journey" and "Score an instruction change").
