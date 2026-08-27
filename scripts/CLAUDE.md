# Repository tooling

These scripts are developer tools, not part of the installed plugin. They use the
environment pinned by the root `pyproject.toml` and `uv.lock`.

## Examples and previews

`preview.py [example]` freshly vendors and serves one shipped example. It copies
the example's companion log, data, and media, then sets the event cursor past
seeded history. `examples/CLAUDE.md` owns those fixture rules.

`gallery.py` generates `examples/gallery.html` and its companion data from the
individual examples. Edit the source examples, then regenerate the gallery.

## Website and demo

`site.py` builds <https://leaf.page/> in `.tmp/site`. The build publishes one
vendored layer plus each example, rewrites checkout-relative assets, and refuses
unresolved local links. `.github/workflows/publish-site.yaml` runs it for relevant
pushes to `main`.

`record-demo.sh` drives the shipped server and Chrome to regenerate
`docs/demo.gif`. `record-demo.py` draws the Leaf screenshots used by that demo;
keep it when the product can make those frames stale.

## Vendored bundles

- `vendor-highlight.sh` rebuilds
  `plugins/leaf/skills/leaf/assets/vendor/highlight.esm.js` from the registry's
  `$languages.names`.
- `vendor-marked.sh` copies the dependency-free Markdown renderer used for
  thread messages.
- `vendor-plot.sh` bundles Observable Plot with d3 into
  `plugins/leaf/skills/leaf/packages/default/vendor/plot.esm.js`; Plot's
  published ESM leaves d3 as a bare external import, so copying it alone is not
  a browser-loadable bundle.

Run the owning script after changing its source dependency or registry input;
do not patch generated bundles or `examples/gallery.html` directly.
