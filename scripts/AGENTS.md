# Repository tooling

These scripts are developer tooling. A host copies them with the tracked tree, but
nothing under `skills/leaf` reads them at runtime. Python tools use the root
`pyproject.toml` and `uv.lock`; the JavaScript builds use `package.json` and
`package-lock.json`.

A script's output lands under `.tmp/` unless its reader finds it at a committed
path: the vendored bundles, `examples/corpus.html` and its companions, the catalog
pin in `example-previews.json`, and the demo frames the README and site cards draw.
Evidence, previews, staged sites, and probe results leave the tracked tree unchanged.

## Examples and previews

- `preview.py` serves one example or developer fixture as a live page, or exports it
  with `--export`. `/developing-leaf` says when to pass `--user`.
- `page_fixtures.py` builds a page directory from a fixture; `example_data.py` reads
  the catalog and each page's companions.
- `corpus.py` generates `examples/corpus.html` and its companions.
- `keydocs.py` writes the `x-` key index in `docs/registry.html`.
- `example_assets.py` fetches the pinned `max-sixty/leaf-assets` revision;
  `example-previews.py`, run as `wt refresh-previews`, redraws and republishes it.

## Website and demo

- `site.py` builds <https://leaf.page/> into `.tmp/site`.
- `verify-site-local.sh` checks the built site through the local Worker and
  container and prints the startup profile. CI runs it on pull requests.
- `verify_site.py` verifies a deployed release, or with `--agent` or `local` runs the
  hosted-agent journey.
- `benchmark-site.py local|ORIGIN` measures that journey as one JSON sample.
- `deploy-site-dev.sh` deploys the checkout to the standing `leaf-website-dev`
  environment. Production deploys only through `.github/workflows/publish-site.yaml`.
- `worker/README.md` owns hosted-agent diagnostics and the failure contract.
- `eval_harness.py` builds the arms and isolated `claude -p` children every Claude
  Code eval runs; `eval_claude_delivery.py`, `notes/arrangement-eval/harness.py`,
  and the A/B recipe in `evals/README.md` use it.
- `eval_claude_delivery.py [BASE_REF]` compares `leaf wait` pickup between a base
  plugin and HEAD's.
- `record-demo.sh` regenerates `docs/demo.gif`, the README stills, and
  `docs/session-card.png`.

## MCP Apps probe

`mcp-app/run-direct-probe.sh` runs the bundled runtime in the official reference
host; `mcp-app/README.md` owns it. Its evidence under `.tmp/mcp-app/experiments/`
is scratch. Copy into `notes/mcp-apps/experiments/<number>/results/` only what a
written-up result cites.

## Vendored bundles

`browser/build.mjs` builds the browser framework and `lit.js` from the TypeScript
under `scripts/browser/`; `vendor.py` rebuilds every other third-party bundle.
Installation, page init, and export consume the committed output and never run a
compiler. After `npm ci`, both reproduce the tracked bytes, so a diff after a
rebuild means the lock, a build script, or the registry input changed:

```sh
npm ci
npm run build:browser      # npm run check:browser compares without writing
uv run scripts/vendor.py   # all bundles, or name the ones to rebuild
```

Rebuild after `npm install` moves a pin or the lock, or after changing registry
input a bundle reads. `package.json` pins every JavaScript version that ships.
