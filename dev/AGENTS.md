# The `leaf-dev` package

`leaf_dev` is Leaf's developer tooling: the code the suite and the eval harnesses
share, and the `leaf-dev` commands built on it. `uv run leaf-dev --help` lists the
commands, and each command's `--help` says what it does.

Only the root dev dependency group installs this package, so the checkout's
environment has it and `bin/leaf`, which runs `--no-dev`, never does. Nothing in
`skills/` may import it.

A command writes under `.tmp/` unless its reader expects the output at a committed
path, as with `examples/corpus.html`. Evidence, previews and probe results leave the
tracked tree unchanged.

## Where tooling goes

When agents keep writing the same throwaway script, make it a `leaf-dev` command: a
module here that owns the job, registered in `cli.py`. Tooling that CI, a hook or an
alias runs is a command here too, so the repository has no directory of loose scripts.
Code two tools need, such as building an arm or serving a page, lives in one module
here that the others import, never through `sys.path`, `PYTHONPATH` or a file path.

- `arms.py` builds arms, the plugin as it is at a ref or in the working tree, and the
  pair an A/B compares, whose base defaults to the merge base with `main`
  (`base_ref`). It also runs the isolated `claude -p` children evals use, the live
  session (`LiveSession`) every live eval plays its user against, and the throwaway
  Claude Code, Codex and Pi homes they run under. `eval_user.py` is that user in a
  browser.
- `page_fixtures.py` builds a page directory from an authored source;
  `example_data.py` reads the catalog, names and each page's companions; `docs.py`
  fills a page under `docs/` with the parts other sources own, for the site and a
  preview alike.
- `browser.py` launches Playwright's pinned headless shell, the build the suite drives,
  and opens and waits on a tab the same way for every command.
- `leaf-dev probe SOURCE` opens a page built from this working tree, runs input steps,
  and prints what a JavaScript expression returns, the console errors and optionally a
  screenshot; `--base` does the same on the merge base. It also takes an HTTP(S) URL,
  a `--journey` file, and `--record` for a trace and video (`recording.py`, whose
  `recording(page, directory)` works in any Playwright script). Its startup report
  includes layout shifts, for diagnosis only.
- `leaf-dev stills [BASE_REF]` screenshots a catalogue of UI states on a base runtime
  and on HEAD's, and crops each state that changed into a before/after pair under
  `.tmp/stills/`. Repeat `--state NAME` to compare only some states.
- `leaf-dev pins [--base]` places comment pins on a catalogue of ordinary and awkward
  targets (`CASES` in `pins.py`) at desktop and phone widths, and writes a Leaf page of
  crops with the faults found in each. `test_render_margin.py` holds every case to the
  same reading, so a placement that looks wrong anywhere becomes a case.
- `leaf-dev thread-snapshots` (`thread_snapshots.py`) captures and accepts reviewed
  message-delivery images. Only acceptance moves `leaf-assets.json`'s
  `thread_snapshots_revision`; publishing media moves `revision`.
- `suite.py` runs a selection of the suite in a checkout and reads each outcome from
  pytest's junit report.
- `suite_profile.py` is the pytest plugin that records each test's phases, CPU and
  Playwright time; `leaf-dev suite-profile DIR` reads that report into where a run's
  time went and which tests are over their directory's `BUDGETS`.
- `leaf-dev flake NODEID...` runs tests as 18 copies, six at a time, and prints every
  failure's message, since a load flake never shows when tests run one at a time.
- `leaf-dev bugback NODEID...` runs the tests on HEAD and with the branch's non-test
  change reverted, and reports which failed.
- `leaf-dev bench-latency [BASE_REF]` times how an open page in Chrome answers a
  gesture, an agent write and a revision, on a base runtime and HEAD's; `--tree` with
  one `--page` and `--transition` times the working tree alone in under a minute.
- `leaf-dev profile SOURCE TRANSITION` shows where one of those transitions spends its
  time in this working tree: main-thread tasks, forced style recalculations and the
  writes that caused them, and JS by function, under `.tmp/profile/`.
- `leaf-dev bench-check [BASE_REF]` times `leaf page check --render` on a few examples,
  base against HEAD, with no model.
- `leaf-dev eval [CASE]... --harness claude-code|codex|both` runs the eval catalog
  through Promptfoo on the working tree, and with `--base` on the merge base too
  (`evals/README.md`). `authoring_eval.py` runs the short cases that need a writable
  page and native tools (`metadata.authoring` in the catalog).
- `leaf-dev eval-pairs RUN...` judges an authored task's samples from a run's two arms
  side by side, in both orders, and `leaf-dev eval-report PAGE RUN...` writes the
  samples, their cost and the verdicts to a Leaf page.
- `leaf-dev eval-ui-review` runs the internal viewer-review diagnostics
  (`evals/ui-review-detection/README.md`).

## Examples and previews

- `leaf-dev preview [EXAMPLE]` serves one example or developer fixture as a live page,
  or exports it with `--export`. `/developing-leaf` says when to pass `--user`.
- `leaf-dev corpus` generates `examples/corpus.html` and its companions.

## Website and demo

`leaf-dev distribution --output NEW-DIRECTORY` builds the installation the website's
container runs, with its kernel compiled again for its own modules.
`distribution.cached_installation` shares that build between suite workers and
previews, and a runtime change builds a new one. Developer arms use the kernel.

CI, the root pnpm scripts and `.config/wt.toml` run the commands below. The images
they make live in `max-sixty/leaf-assets`, so outside `.tmp/` they change only the pin
in `leaf-assets.json` and the README's image URLs.

- `leaf-dev site` builds <https://leaf.page/> into `.tmp/site`, its edge assets into
  `.tmp/site-assets`, and the installation its container runs into
  `.tmp/site-install`; `--output` gives a separate build its own destination.
  `pnpm run site:dev` builds and serves it through `wrangler dev`.
- `leaf-dev verify-site` checks a release at an origin, or with `website-worker` the
  site `leaf-dev site` built, through the local Worker and container, and prints the
  startup profile; CI runs `website-worker` on pull requests. Each run keeps its logs
  under `.tmp/verify-site/run-*/`; `worker/README.md` owns diagnostics.
- `worker/deploy-dev.sh` (`pnpm run deploy:dev`) deploys the checkout to the
  `leaf-website-dev` environment and verifies it. Production deploys only through
  `.github/workflows/publish-site.yaml`.
- `leaf-dev fetch-assets` fetches the `max-sixty/leaf-assets` revision
  `leaf-assets.json` pins (`leaf_assets.py`). `leaf-dev refresh-previews`, run as
  `wt refresh-previews`, recaptures the catalog previews, publishes them and moves the
  pin; `leaf-dev record-demo` does the same for the README's demo and the site's card,
  and `leaf-dev publish-media FILE...` for media the example pages show.

## Journeys

`leaf-dev journey TARGET` runs one user's journey against a real agent;
`/developing-leaf`, "Run the agent journey", says what it checks and when to run it.
`journey.py` owns what the targets share: a throwaway home holding only the host's
login, evidence under `.tmp/journey/`, the `Terminal` it hears a session through, and
the `User`. It times each comment on the server's clock, split into delivery, model and
tool phases. Between steps the journey fails unless every comment so far has one reply
that reached the session, and the page's claim names the session with its turn closed.
Each target's module lists its steps and the harness promises it checks
(`journey_claude_code.py`, `journey_codex.py`, `journey_pi.py`).

Each run prints one JSON sample and appends it to
`$XDG_STATE_HOME/leaf-dev/journey.jsonl`; `leaf-dev journey-chart` turns those samples
into an `lf-chart` for a page. `publish-site` runs the journey against each release.
The harness targets spend the host's logins, so CI doesn't run them.
