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
  companion data from the examples, regression pages under `tests/fixtures/pages/`, and the developer feature gallery.
- `example_assets.py` fetches the immutable `max-sixty/leaf-assets` commit named by
  `example-previews.json` into `.tmp`; `site.py` calls it when that revision is absent.
- `example-previews.py`, invoked as `wt refresh-previews`, draws the stills selected by
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
  It also writes what a crawler reads: `robots.txt`, a `sitemap.xml` of the clean
  routes, and each page's card. A page's title and description are authored in its own
  source, and the build refuses one that has neither. The rest of the card — the
  Open Graph and Twitter declarations and the image — comes from `site_head` in
  `worker/server.py` and enters Leaf's document composer for both the edge shell and
  the container response. The canonical link is not the site's: every Leaf
  document names its own page root, so the three addresses a page answers collapse
  onto one wherever a page directory is published. Each page's image is named in the
  manifest, `docs/session-card.png` for a product page and the catalog preview for an
  example, and `check_links` resolves it the way it resolves an href.
  `verify-site-local.sh` checks that built output through that boundary and prints the
  document, widget-upgrade, and presentation milestones with the requests and bytes
  loaded by presentation. A failed check prints the Worker's log beside the browser's
  own account of the page that stopped it. Pull requests run it for review evidence.
  `.github/workflows/publish-site.yaml` deploys both halves for relevant pushes to
  `main`; it runs the local check before the first public operation, then verifies the
  exact release again after deployment. That production pass also sends one private
  comment and requires the hosted Codex task to publish a revision and reply. With
  `verify_site.py --agent`, the verifier prints the request acknowledgement, activity
  transitions, publication, reply, and changed-page presentation timings. The Worker's
  structured `startup_failed` reply triggers one retry; rate limits and all other
  unsuccessful endings fail the deployment on the first ask. `worker/README.md` owns
  the failure contract.
  `uv run scripts/verify_site.py local` runs the same delivery, App Server, edit,
  publication,
  reply, and browser-reload path against the host's Codex login. It bypasses the
  Cloudflare Worker, container resources, and outbound credential proxy, so
  it checks agent behavior without measuring production infrastructure.
  `benchmark-site.py local|ORIGIN` emits that complete journey as one JSON sample:
  browser presentation, a comment sent through the real Threads composer,
  acknowledgement and activity, the first agent reply text visible in the open thread,
  requested publication and durable reply, then the changed page's presentation and
  revision follow. Both targets run the same HTTP and browser checks. `local` only
  provisions the canonical Python adapter and explicitly starts its turn; it does not
  emulate Cloudflare's Worker, container allocation, or routing.
  `deploy-site-dev.sh` publishes the current checkout to the one standing
  `leaf-website-dev` Cloudflare environment and runs that benchmark against its
  `workers.dev` origin. The command always selects the `dev` Wrangler environment;
  production deployment stays in `publish-site.yaml`.
  Hosted-agent diagnostics live in Workers Observability. Query its REST API directly
  with the canonical event id or visible session reference; once the Container starts
  a Codex turn, its `turnId` also finds the model-request timings. Analytics Engine is
  aggregate product telemetry, not a log index.
- `record-demo.sh` regenerates `docs/demo.gif`; `record-demo.py` draws it and the three
  photographs of the same staged scene beside it — the README's light and dark
  session stills, and `session-card.png` at the 1.91:1 an unfurler draws a card at.
  Keep the latter while the product can make those frames stale.

## Vendored bundles

`vendor.py` rebuilds them — all of them by default, or the ones you name. Every pinned
version sits in one table there, and each bundle lands in the package whose widget
imports it, except `mcp-app`, which no widget imports and which lands in
`skills/leaf/mcp-app/` for an MCP host to read from the install.

A bundle reproduces its tracked bytes exactly when every input it fetches is pinned,
which holds for `marked`, `sortable`, `beautiful-mermaid`, `floating-ui`, `highlight`,
and `jsdiff`, so a clean `git status` after a run is the check that the bundle still
matches the script. `plot`, `pierre`, and `mcp-app` reach npm's resolver for transitive
dependencies and inherit its ranges, so a diff from one of those can be an upstream
patch rather than drift.

Rerun a bundle after changing its pin or the registry input it reads; do not patch a
generated bundle or `examples/corpus.html` directly.
