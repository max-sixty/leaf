# The `leaf-dev` package

`leaf_dev` is Leaf's developer tooling as a package: the mechanisms the scripts, the
suite and the eval harnesses share, and the `leaf-dev` commands built on them.

```sh
uv run leaf-dev --help
```

It is a uv workspace member that only the root dev group depends on, so the checkout's
environment installs it editable and `bin/leaf`, which runs `--no-dev`, never does.
Nothing in `skills/` may import it. Its code runs under the same pre-commit hooks as
the rest of the tree.

## Where tooling goes

When agents keep writing the same throwaway script, the job becomes a `leaf-dev`
command: a module here that owns its mechanism, registered in `cli.py`. Standing
tooling that CI, a hook or an alias runs is a command here too. A mechanism
two tools need, such as building an arm or serving a page, lives in one module here
and the others import it; a script under `scripts/` imports it too.

- `harness.py`: arms (the plugin payload at a ref) and an A/B's pair of them, whose
  base defaults to the merge base with `main` (`base_ref`); pages served from an
  authored source on an arm; the machine's load average a timed command prints; the
  isolated `claude -p` children evals run; and the throwaway Codex homes a Codex
  child runs under.
- `page_fixtures.py` builds a page directory from an authored source;
  `example_data.py` reads the catalog, names, and each page's companions.
- `browser.py` launches Chrome, and opens and settles a tab, the same way for every
  command that reads one.
- `leaf-dev probe SOURCE` opens a page built from this working tree, runs input
  steps, and prints what a JavaScript expression returns, the console errors, and
  optionally a screenshot; `--base` does the same on the merge base.
- `leaf-dev stills [BASE_REF]` screenshots a catalogue of UI states, at rest and
  reached by input, on a base runtime and HEAD's, and crops each state that changed
  into a before/after pair under `.tmp/stills/`.
- `leaf-dev arm REF DEST` builds one arm, for an eval's A/B (`evals/README.md`).
- `leaf-dev bench-latency [BASE_REF]` times an open page's answer to a gesture, an
  agent write, and a revision in Chrome, with the traffic each causes, for a base
  runtime and HEAD's.
- `leaf-dev profile SOURCE TRANSITION` says where one of those transitions spends its
  time in this working tree: main-thread tasks up to the painted frame, forced style
  recalculations and the writes that invalidated them, and JS by function.
- `leaf-dev bench-check [BASE_REF]` times `leaf page check --render` on a few
  examples, base plugin against HEAD's, with no model: wall time and a phase
  breakdown traced by `tracer/sitecustomize.py`.
- `leaf-dev delivery-ab [BASE_REF]` compares how a live Claude Code agent handles a
  comment through `leaf wait`, and what the page shows meanwhile, between a base plugin
  and HEAD's. Its children cost about a dollar each.

## Website and demo

These commands write what a committed file or a deploy reads, so CI, `worker/`'s npm
scripts and `.config/wt.toml` call them. Their output lands under `.tmp/` except the
catalog pin in `example-previews.json` and the demo frames the README and site cards
draw.

- `leaf-dev site [--serve]` builds <https://leaf.page/> into `.tmp/site`;
  `scripts/verify_site.py` verifies what it built.
- `leaf-dev fetch-previews` fetches the catalog previews pinned in
  `example-previews.json` (`example_assets.py`, which the site build also calls).
  `leaf-dev refresh-previews`, run as `wt refresh-previews`, recaptures them,
  republishes them to `max-sixty/leaf-assets`, and updates the pin.
- `leaf-dev record-demo` regenerates `docs/demo.gif`, the README stills, and
  `docs/session-card.png`.
