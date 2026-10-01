# The `leaf-dev` package

`leaf_dev` is Leaf's developer tooling: the mechanisms the suite and the eval
harnesses share, and the `leaf-dev` commands built on them. `uv run leaf-dev --help`
lists the commands, and each command's help says what it does, what it costs, and
where its output lands.

Only the root dev group depends on this uv workspace member, so the checkout's
environment installs it editable and `bin/leaf`, which runs `--no-dev`, never does.
Nothing in `skills/` may import it.

A command writes under `.tmp/` unless its reader finds the output at a committed
path, as with `examples/corpus.html` and its companions. Evidence, previews, and
probe results leave the tracked tree unchanged.

## Where tooling goes

When agents keep writing the same throwaway script, or CI, a hook, or an alias runs
one, the job becomes a `leaf-dev` command: a module here that owns its mechanism,
registered in `cli.py`. The repository keeps no directory of loose scripts. A
mechanism two tools need lives in one module here and the others import it from
this package, never through `sys.path`, `PYTHONPATH`, or a file path. Before
writing one, reuse these:

- `harness.py`: arms, each the plugin payload at a ref or as the working tree has
  it, and an A/B's pair with its base (`base_ref`); pages served from an authored
  source on an arm; and the isolated `claude -p` children and throwaway Codex homes
  evals run under;
- `page_fixtures.py`: a page directory built from an authored source
  (`prepare_page`), and the example media it lays in;
- `example_data.py`: the catalog, example names, and each page's companions;
- `browser.py`: Chrome, and a tab on a served page, opened and settled the same way
  for every command;
- `suite.py`: a selection of the suite run in a checkout, each test's outcome read
  from pytest's junit report;
- `leaf_assets.py`: the files pinned in `max-sixty/leaf-assets`, which the site
  build also fetches through it.

## Commands with consequences outside `.tmp/`

- `leaf-dev corpus` writes `examples/corpus.html` and its companions, and
  `leaf-dev keydocs` the `x-` key index in `docs/registry.html`.
- `leaf-dev refresh-previews` (as `wt refresh-previews`), `leaf-dev record-demo`,
  and `leaf-dev publish-media` push images to `max-sixty/leaf-assets`; in the tree
  they change only the pin in `leaf-assets.json` and the README's image URLs.
- `worker/deploy-dev.sh` (`npm run deploy:dev --prefix worker`) deploys the
  checkout to the persistent `leaf-website-dev` environment. Production deploys
  only through `.github/workflows/publish-site.yaml`. `worker/README.md` owns
  hosted-agent diagnostics and the failure contract.
- `leaf-dev delivery-eval` and `leaf-dev guidance-eval` spend model calls, and
  `leaf-dev verify-codex-task` the host's Codex login, which CI does not have
  (`/developing-leaf`, "Test a terminal Codex task").
