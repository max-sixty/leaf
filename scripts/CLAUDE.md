# Repository tooling

These scripts are developer tooling: the installed plugin is the whole tracked tree,
so a host copies these along with it, but nothing under `skills/leaf` reads them at
runtime. They use the environment pinned by the root `pyproject.toml` and `uv.lock`.

Each script's own docstring and `--help` own its behavior, flags, and lifecycle. This
file says which script owns what, and the rules that hold across them.

## Examples and previews

- `preview.py [page]` serves one public example or developer fixture as a live page
  under `.tmp/previews/<source-stem>`, watching the fixture and the selected runtime.
  `--export` writes the browser-drawn result as one standalone file instead.
- `corpus.py` generates the internal `examples/corpus.html` stress fixture and its
  companion data from the public examples and the developer feature gallery.
- `example_assets.py` fetches the immutable `max-sixty/leaf-assets` commit named by
  `example-previews.json` into `.tmp`; `site.py` calls it when that revision is absent.
- `example-previews.py`, invoked as `wt refresh-previews`, draws the stills for
  `docs/examples.html` through the live published-example server. It refuses fallback
  fonts, pushes the complete image set, and updates the tracked commit pin and catalog.

Edit a source page, then regenerate the corpus. `examples/CLAUDE.md` owns the fixture
rules a new or changed example has to meet.

## Website and demo

- `site.py` builds <https://leaf.page/> as complete page directories in `.tmp/site`
  and their derived live shells in `.tmp/site-assets`, then bundles the public runtime
  with the website's esbuild dependency. Run `npm ci --prefix worker` first. `--serve`
  opens the same Wrangler asset and container boundary the deployed site uses and also
  needs a running Docker.
  `verify-site-local.sh` checks that built output through that boundary and prints the
  document, widget-upgrade, and presentation milestones with the requests and bytes
  loaded by presentation. A failed check prints the Worker's log beside the browser's
  own account of the page that stopped it. Pull requests run it for review evidence.
  `.github/workflows/publish-site.yaml` deploys both halves for relevant pushes to
  `main`; it runs the local check before the first public operation, then verifies the
  exact release again after deployment. That production pass also sends one private
  comment and requires the hosted Codex task to publish a revision and reply. With
  `LEAF_VERIFY_AGENT=1`, `verify-site.py` prints the request acknowledgement, activity
  transitions, publication, reply, and changed-page presentation timings. A turn the
  container settles with its own generation failure is asked once more, because that
  settlement reports the model rather than the release; every other ending is a red
  deployment on the first ask.
  `verify-site-agent-local.sh` runs the same delivery, App Server, edit, publication,
  reply, and browser-reload path against the host's Codex login. It bypasses the
  Cloudflare Worker, Workflow, container resources, and outbound credential proxy, so
  it checks agent behavior without measuring production infrastructure.
- `record-demo.sh` regenerates `docs/demo.gif`; `record-demo.py` draws the Leaf
  screenshots that demo uses. Keep the latter while the product can make those frames
  stale.

## Vendored bundles

`vendor.py` rebuilds them — all of them by default, or the ones you name. Every pinned
version sits in one table there, and each bundle lands in the package whose widget
imports it, except `mcp-app`, which no widget imports and which lands in
`skills/leaf/mcp-app/` for an MCP host to read from the install.

A bundle reproduces its tracked bytes exactly when every input it fetches is pinned,
which holds for `marked`, `sortable`, `beautiful-mermaid`, and `highlight`, so a clean
`git status` after a run is the check that the bundle still matches the script. `plot`
and `pierre` reach npm's resolver for transitive dependencies and inherit its ranges,
so a diff from either can be an upstream patch rather than drift.

Rerun a bundle after changing its pin or the registry input it reads; do not patch a
generated bundle or `examples/corpus.html` directly.
