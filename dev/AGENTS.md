# The `leaf-dev` package

`leaf_dev` is Leaf's developer tooling: the mechanisms the suite and the eval
harnesses share, and the `leaf-dev` commands built on them. `uv run leaf-dev --help`
lists the commands, and each command's `--help` says what it does.

Only the root dev group depends on this uv workspace member, so the checkout's
environment installs it editable and `bin/leaf`, which runs `--no-dev`, never does.
Nothing in `skills/` may import it.

A command writes under `.tmp/` unless its reader finds the output at a committed
path, as with `examples/corpus.html` and its companions. Evidence, previews, and
probe results leave the tracked tree unchanged.

## Where tooling goes

When agents keep writing the same throwaway script, the job becomes a `leaf-dev`
command: a module in `leaf_dev/commands/` that owns its mechanism. The CLI discovers
commands there; module and function names agree, with underscores in Python and
dashes on the CLI. Recurring tooling that CI, a hook or an alias runs is a command here too, so the repository
has no directory of loose scripts. A mechanism two tools need, such as building an
arm or serving a page, lives in one module here and the others import it. Code
reaches a module by importing it from this package, never through `sys.path`,
`PYTHONPATH` or a file path.

- `arms.py`: arms (the plugin payload at a ref, or as the working tree has it) and
  an A/B's pair of them, whose base defaults to the merge base with `main`
  (`base_ref`); pages served from an authored source on an arm; the machine's load
  average a timed command prints; the isolated `claude -p` children evals run, and
  the live session (`LiveSession`) every live eval driver plays its user against;
  and the throwaway Claude Code, Codex and Pi homes a child of each runs under.
  `eval_user.py` is that user in a browser: a comment from a selection, and a
  decision a user agent makes through the page's own controls.
- `page_fixtures.py` builds a page directory from an authored source;
  `example_data.py` reads the catalog, names, and each page's companions; `docs.py`
  composes into a product document under `docs/` the parts other sources own, so
  every builder of one, the site and a preview alike, shows them.
- `browser.py` launches Playwright's pinned headless shell, the build the suite
  drives, and opens and settles a tab, the same way for every command that reads
  one.
- `leaf-dev probe SOURCE` opens a page built from this working tree, runs input
  steps, and prints what a JavaScript expression returns, the console errors, and
  optionally a screenshot; `--base` does the same on the merge base. Its startup
  evidence uses the same recorder as site verification: phases, resources, and
  native initial layout shifts with affected nodes and before/after rectangles.
  Those shifts are diagnostic, never a stability gate.
- `leaf-dev probe` also takes an HTTP(S) URL, runs a `--journey` file, and records
  a trace and video with `--record`; its `--help` owns those flags. `recording.py`
  owns capture and GIF encoding, including the demo's encoder; its
  `recording(page, directory)` context works in any Playwright script.
- `leaf-dev stills [BASE_REF]` screenshots a catalogue of UI states, at rest and
  reached by input, on a base runtime and HEAD's, and crops each state that changed
  into a before/after pair in its own run directory under `.tmp/stills/`.
  Repeat `--state NAME` to compare only the states a change touches.
- `leaf-dev pins [--base]` seats comment pins on a small, unselected catalogue of
  ordinary and pathological targets (`pins.py`'s `CASES`) at a desktop and a phone
  width, and writes a Leaf page of crops beside the faults read in each; with `--base`
  each crop is a before/after pair. `test_render_margin.py` holds every case to the
  same reading, so a placement that looks wrong anywhere becomes a case.
- `leaf-dev thread-snapshots` owns reviewed message-delivery images in leaf-assets;
  `thread_snapshots.py` owns capture and acceptance. Acceptance alone advances
  `leaf-assets.json`'s `thread_snapshots_revision`; media publication advances
  `revision`, so new demo assets cannot replace a runtime's reviewed expectations.
- `suite.py` runs a selection of the suite in a checkout and reads each test's
  outcome from pytest's junit report, refusing a selection pytest would not run.
- `suite_profile.py` is the pytest plugin that gives each test a junit `profile`
  property, its phases, the CPU its worker's cgroup used, and its time in Playwright's
  sync API by method and caller, and `leaf-dev suite-profile DIR` reads that report,
  with the py-spy stacks and process CPU CI records beside it, into where a run's CPU
  and worker time went, and which tests are over their tier directory's budget, which
  `BUDGETS` there holds.
- `leaf-dev flake NODEID...` runs tests from the working tree as 18 copies, six at a
  time, and prints every failure's message, since a load flake never shows serially.
  It snapshots the candidate once; each copy owns its checkout and test output.
- `leaf-dev bugback NODEID...` runs the tests on HEAD and with the branch's non-test
  change reverted, in a scratch worktree, and reports which went red.
- `leaf-dev bench-latency [BASE_REF]` times an open page's answer to a gesture, an
  agent write, and a revision in Chrome, with the traffic each causes and who held
  the main thread, for a base runtime and HEAD's; `--tree` with one `--page` and
  `--transition` times the working tree alone in under a minute.
- `leaf-dev profile SOURCE TRANSITION` says where one of those transitions spends its
  time in this working tree: main-thread tasks up to its last painted goal, forced style
  recalculations and the writes that invalidated them, and JS by function. Traces and
  CPU profiles stay in its own run directory under `.tmp/profile/`.
- `leaf-dev bench-check [BASE_REF]` times `leaf page check --render` on a few
  examples, base plugin against HEAD's, with no model, and prints each arm's wall
  time. Its arms, pages and state stay in its own run directory under
  `.tmp/bench-check/`.
- `leaf-dev eval [CASE]... --harness claude-code|codex|both` runs the eval catalog
  through Promptfoo on the working tree, and with `--base` the merge base too.
  `evals/README.md` owns the format and how to read the results.
- `authoring_eval.py` runs short cases that need a writable page and native tools,
  using the shared isolated child and page checks; their assertions read the saved
  HTML. `metadata.authoring` selects this mode in the catalog.
- `leaf-dev eval-pairs RUN...` judges an authored task's samples across a run's two
  columns side by side, in both orders, and `leaf-dev eval-report PAGE RUN...` writes
  those samples, their spend and the verdicts to a Leaf page.
- `leaf-dev eval-ui-review` runs the retained internal viewer-review diagnostics;
  `evals/ui-review-detection/README.md` owns their scope, controls and automatic grading.

## Examples and previews

- `leaf-dev preview [EXAMPLE]` serves one example or developer fixture as a live
  page, or exports it with `--export`. `/developing-leaf` says when to pass `--user`.
- `leaf-dev corpus` generates `examples/corpus.html` and its companions.

## Website and demo

`leaf-dev distribution --output NEW-DIRECTORY` builds the installation tree the
website's container runs, with its kernel compiled again for its own modules.
`distribution.cached_installation` shares the same preparation between suite workers
and developer previews, keyed by payload and compiler inputs. Authored-page edits reuse
it; relevant runtime revisions build a new immutable payload. Consumer installs and
custom-package authoring retain their build-free workflow. Developer arms use the
kernel.

CI, the root pnpm scripts and `.config/wt.toml` run these. The images they
write live in `max-sixty/leaf-assets`, so outside `.tmp/` they write only the pin
in `leaf-assets.json` and the README's image URLs that name it.

- `leaf-dev site` builds <https://leaf.page/> into `.tmp/site`, its edge assets into
  `.tmp/site-assets`, and the prepared installation that vendors its pages and that
  the container image installs into `.tmp/site-install`; `--output` gives an
  independent build its own destination. Writes to one destination are serialized.
  `pnpm run site:dev` builds and serves it through `wrangler dev`, which
  chooses available HTTP and inspector ports.
- `leaf-dev verify-site` verifies a release at an origin, or with `website-worker`
  the site `leaf-dev site` built, through the local Worker and container, and prints
  the startup profile; CI runs `website-worker` on pull requests. Each local run
  has private listener ports, temporary site, container build context and state,
  and retained logs under `.tmp/verify-site/run-*/`. `worker/README.md` owns hosted-agent
  diagnostics and the failure contract.
- `worker/deploy-dev.sh` (`pnpm run deploy:dev`) deploys the checkout
  to the persistent `leaf-website-dev` environment and verifies it. Production deploys
  only through `.github/workflows/publish-site.yaml`.
- `leaf-dev fetch-assets` fetches the `max-sixty/leaf-assets` revision pinned in
  `leaf-assets.json` (`leaf_assets.py`, which the site build also calls).
  `leaf-dev refresh-previews`, run as `wt refresh-previews`, recaptures the catalog
  previews under its `examples/`, republishes them, and moves the pin.
- `leaf-dev record-demo` regenerates the README's demo GIF and stills and the site's
  card under its `demo/`, and publishes them the same way.
- `leaf-dev publish-media FILE...` adds media the example pages show under its
  `examples/media/`, and moves the pin.

## Journeys

`leaf-dev journey TARGET` runs one user's journey against a real agent;
`/developing-leaf`, "Run the agent journey", says what it checks and when to run it,
and its `--help` lists the targets and where the user is. `journey.py` owns what the
targets share: the isolation (a harness session runs under a throwaway home holding only
the host's login) and its evidence under `.tmp/journey/`; the `Terminal` every wait
hears a session through; and the `User`. Each comment is timed from the page's log on the server's clock,
with the agent's work on it split into delivery, model and tool phases. Between
steps the journey fails unless every comment so far has one reply and entered the
session's context, and the page's claim names the session with its turn closed;
what else each target checks is its harness's promise, which its module lists with
its steps (`journey_claude_code.py`, `journey_codex.py`, `journey_pi.py`).

Each run prints one JSON sample and appends it to
`$XDG_STATE_HOME/leaf-dev/journey.jsonl` on the machine that ran it; `leaf-dev
journey-chart` (`journey_chart.py`) prints an `lf-chart` of those samples, for the latest version each
target ran at each user end, to put on a page. `publish-site` runs the journey
against each release. The harness targets spend the host's logins, so CI does not
run them.
