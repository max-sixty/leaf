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
command: a module here that owns its mechanism, registered in `cli.py`. A mechanism
two tools need, such as building an arm or serving a page, lives in one module here
and the others import it; a script under `scripts/` imports it too.

- `harness.py`: arms (the plugin payload at a ref, or as the working tree has it),
  pages served from an authored source on an arm, the isolated `claude -p` children
  evals run, and the throwaway Codex homes a Codex child runs under.
- `page_fixtures.py` builds a page directory from an authored source;
  `example_data.py` reads the catalog, names, and each page's companions.
- `browser.py` opens and settles a tab the same way for every command that reads one.
- `leaf-dev probe SOURCE` opens a page built from this working tree, runs input
  steps, and prints what a JavaScript expression returns, the console errors, and
  optionally a screenshot; `--base` does the same on the merge base.
- `leaf-dev stills [BASE_REF]` screenshots a catalogue of UI states, at rest and
  reached by input, on a base runtime and HEAD's, and crops each state that changed
  into a before/after pair under `.tmp/stills/`.
- `leaf-dev guidance-ab [CASE]...` runs the guidance cases in `evals/` on the merge
  base's guidance and the working tree's at once, and prints each case's passes per
  arm and a Record row (`evals/README.md`).
