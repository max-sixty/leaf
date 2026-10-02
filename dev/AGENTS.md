# The `leaf-dev` package

`leaf_dev` is Leaf's developer tooling as a package: the mechanisms the suite and
the eval harnesses share, and the `leaf-dev` commands built on them.

```sh
uv run leaf-dev --help
```

It is a uv workspace member that only the root dev group depends on, so the checkout's
environment installs it editable and `bin/leaf`, which runs `--no-dev`, never does.
Nothing in `skills/` may import it. Its code runs under the same pre-commit hooks as
the rest of the tree.

A command's output lands under `.tmp/` unless its reader finds it at a committed
path, as `examples/corpus.html` and its companions are. Evidence, previews, and probe
results leave the tracked tree unchanged.

## Where tooling goes

When agents keep writing the same throwaway script, the job becomes a `leaf-dev`
command: a module here that owns its mechanism, registered in `cli.py`. Standing
tooling that CI, a hook or an alias runs is a command here too, so the repository
has no directory of loose scripts. A mechanism two tools need, such as building an
arm or serving a page, lives in one module here and the others import it. Code
reaches a module by importing it from this package, never through `sys.path`,
`PYTHONPATH` or a file path.

- `harness.py`: arms (the plugin payload at a ref, or as the working tree has it) and
  an A/B's pair of them, whose base defaults to the merge base with `main`
  (`base_ref`); pages served from an authored source on an arm; the machine's load
  average a timed command prints; the isolated `claude -p` children evals run; and
  the throwaway Codex homes a Codex child runs under.
- `page_fixtures.py` builds a page directory from an authored source;
  `example_data.py` reads the catalog, names, and each page's companions.
- `browser.py` launches Chrome, and opens and settles a tab, the same way for every
  command that reads one.
- `leaf-dev probe SOURCE` opens a page built from this working tree, runs input
  steps, and prints what a JavaScript expression returns, the console errors, and
  optionally a screenshot; `--base` does the same on the merge base. Its startup
  evidence uses the same recorder as site verification: phases, resources, and
  native initial layout shifts with affected nodes and before/after rectangles.
  Those shifts are diagnostic, never a stability gate.
- `leaf-dev stills [BASE_REF]` screenshots a catalogue of UI states, at rest and
  reached by input, on a base runtime and HEAD's, and crops each state that changed
  into a before/after pair under `.tmp/stills/`.
- `suite.py` runs a selection of the suite in a checkout and reads each test's
  outcome from pytest's junit report, refusing a selection pytest would not run.
- `leaf-dev flake NODEID...` runs tests from the working tree as 18 copies, six at a
  time, and prints every failure's message, since a load flake never shows serially.
  The copies share every fixed path a test writes in the checkout, such as an export
  under `.tmp/`, so a failure naming one is the copies racing there, not load.
- `leaf-dev bugback NODEID...` runs the tests on HEAD and with the branch's non-test
  change reverted, in a scratch worktree, and reports which went red.
- `leaf-dev bench-latency [BASE_REF]` times an open page's answer to a gesture, an
  agent write, and a revision in Chrome, with the traffic each causes, for a base
  runtime and HEAD's.
- `leaf-dev profile SOURCE TRANSITION` says where one of those transitions spends its
  time in this working tree: main-thread tasks up to the painted frame, forced style
  recalculations and the writes that invalidated them, and JS by function.
- `leaf-dev bench-check [BASE_REF]` times `leaf page check --render` on a few
  examples, base plugin against HEAD's, with no model, and prints each arm's wall
  time.
- `leaf-dev delivery-eval [BASE_REF]` compares how a live Claude Code agent handles a
  comment through `leaf wait` between a base plugin and HEAD's. Its children cost about
  a dollar each.
- `leaf-dev instructions-eval [CASE]...` runs the instructions cases in `evals/` on the merge
  base's instructions and the working tree's at once, and prints each case's passes per
  arm (`/developing-leaf`, "Score an instruction change").

## Examples and previews

- `leaf-dev preview [EXAMPLE]` serves one example or developer fixture as a live
  page, or exports it with `--export`. `/developing-leaf` says when to pass `--user`.
- `leaf-dev corpus` generates `examples/corpus.html` and its companions.
- `leaf-dev keydocs` writes the `x-` key index in `docs/registry.html`.

## Website and demo

CI, `worker/`'s npm scripts and `.config/wt.toml` run these. The images they
write live in `max-sixty/leaf-assets`, so outside `.tmp/` they write only the pin
in `leaf-assets.json` and the README's image URLs that name it.

- `leaf-dev site` builds <https://leaf.page/> into `.tmp/site`, and
  `npm run dev --prefix worker` builds and serves it through `wrangler dev`.
- `leaf-dev verify-site` verifies a release at an origin, or with `wrangler` the
  site `leaf-dev site` built, through the local Worker and container, and prints the
  startup profile; CI runs `wrangler` on pull requests. With `--agent`, or `local`
  for the Python adapter alone, it runs the hosted-agent journey and emits one JSON
  sample. `worker/README.md` owns hosted-agent diagnostics and the failure contract.
- `worker/deploy-dev.sh` (`npm run deploy:dev --prefix worker`) deploys the checkout
  to the standing `leaf-website-dev` environment and verifies it. Production deploys
  only through `.github/workflows/publish-site.yaml`.
- `leaf-dev fetch-assets` fetches the `max-sixty/leaf-assets` revision pinned in
  `leaf-assets.json` (`leaf_assets.py`, which the site build also calls).
  `leaf-dev refresh-previews`, run as `wt refresh-previews`, recaptures the catalog
  previews under its `examples/`, republishes them, and moves the pin.
- `leaf-dev record-demo` regenerates the README's demo GIF and stills and the site's
  card under its `demo/`, and publishes them the same way.
- `leaf-dev publish-media IMAGE...` adds images the example pages show under its
  `examples/media/`, and moves the pin.

## Codex

- `leaf-dev verify-codex-task` runs real Codex tasks with this working tree's
  plugin through both transports of `leaf codex start`. It posts comments while the
  task is idle, mid-turn, and after the adapter is killed, and fails when a comment is
  not answered exactly once, queue-backed work does not pick up and answer a comment
  in the same active turn, or the page's claim does not name the task's last turn,
  closed. It spends the host's Codex login, so CI does not run it.
