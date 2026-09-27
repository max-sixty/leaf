# Repository tooling

These scripts are developer tooling. A host copies them with the tracked tree, but
nothing under `skills/leaf` reads them at runtime. They use the root `pyproject.toml`
and `uv.lock`. What they share, and the `leaf-dev` commands, live in the `leaf_dev`
package under `dev/` (`dev/AGENTS.md`); what builds the committed browser bundles
lives in `build/` (`build/AGENTS.md`).

A script's output lands under `.tmp/` unless its reader finds it at a committed
path, as `examples/corpus.html` and its companions are. Evidence, previews, and probe
results leave the tracked tree unchanged.

## Examples and previews

- `preview.py` serves one example or developer fixture as a live page, or exports it
  with `--export`. `/developing-leaf` says when to pass `--user`.
- `corpus.py` generates `examples/corpus.html` and its companions.
- `keydocs.py` writes the `x-` key index in `docs/registry.html`.

## Website, evals and profiling

- `verify_site.py` verifies a release at an origin, or with `wrangler` the site
  `leaf-dev site` built, through the local Worker and container, and prints the
  startup profile;
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
- `eval_claude_delivery.py [BASE_REF]` compares how an agent handles a comment
  through `leaf wait`, and what the page shows meanwhile, between a base plugin
  and HEAD's.
- `bench_render_check.py [BASE_REF]` times `leaf page check --render` on a few
  examples, base plugin against HEAD's, with no model: wall time and a phase
  breakdown traced by `bench-render-check/sitecustomize.py`.
- `bench_page_latency.py [BASE_REF]` times an open page's answer to a gesture, an
  agent write, and a revision in Chrome, with the traffic each causes, for a base
  runtime and HEAD's.
- `profile_page.py SOURCE TRANSITION` says where one of those transitions spends its
  time in this checkout: main-thread tasks up to the painted frame, forced style
  recalculations and the writes that invalidated them, and JS by function.
