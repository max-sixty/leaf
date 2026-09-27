# Repository tooling

These scripts are developer tooling. A host copies them with the tracked tree, but
nothing under `skills/leaf` reads them at runtime. They use the root `pyproject.toml`
and `uv.lock`. What they share, and the `leaf-dev` commands, live in the `leaf_dev`
package under `dev/` (`dev/AGENTS.md`); what builds the committed browser bundles
lives in `build/` (`build/AGENTS.md`).

A script's output lands under `.tmp/` unless its reader finds it at a committed
path: `examples/corpus.html` and its companions, the catalog
pin in `example-previews.json`, and the demo frames the README and site cards draw.
Evidence, previews, staged sites, and probe results leave the tracked tree unchanged.

## Examples and previews

- `preview.py` serves one example or developer fixture as a live page, or exports it
  with `--export`. `/developing-leaf` says when to pass `--user`.
- `corpus.py` generates `examples/corpus.html` and its companions.
- `keydocs.py` writes the `x-` key index in `docs/registry.html`.
- `example_assets.py` fetches the pinned `max-sixty/leaf-assets` revision;
  `example-previews.py`, run as `wt refresh-previews`, redraws and republishes it.

## Website and demo

- `site.py` builds <https://leaf.page/> into `.tmp/site`.
- `verify_site.py` verifies a release at an origin, or with `wrangler` the built
  site through the local Worker and container, and prints the startup profile;
  CI runs `wrangler` on pull requests. With `--agent`, or `local` for the Python
  adapter alone, it runs the hosted-agent journey and emits one JSON sample.
- `deploy-site-dev.sh` deploys the checkout to the standing `leaf-website-dev`
  environment. Production deploys only through `.github/workflows/publish-site.yaml`.
- `worker/README.md` owns hosted-agent diagnostics and the failure contract.
- `verify_codex_task.py` runs one real Codex task with this working tree's plugin
  through `leaf codex start`'s App Server adapter. It posts comments while the task
  is idle, mid-turn, and after the adapter is killed, and fails when a comment is
  not answered exactly once or the page's claim does not name the task's last turn,
  closed. It spends the host's Codex login, so CI does not run it.
- `record-demo.py` regenerates `docs/demo.gif`, the README stills, and
  `docs/session-card.png`.
