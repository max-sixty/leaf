# leaf

Leaf is a page an agent hands to a user and the loop that carries anchored
comments and actions back. `README.md` describes the product.

## Stage

Leaf has no users, deployment, database, or persisted state that constrains new
code. Prefer the simpler interface even when it is incompatible. Delete and
regenerate stale state. Add a guard only for a reachable condition with a useful
response.

Make improvements that follow from the repository. Ask the user only when the
choice depends on purpose or intent the code cannot supply.

## Repository map

`plugins/leaf/` is the payload installed by both Claude Code and Codex. The root
`.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` files
point at it. Its main parts are:

- `skills/leaf/scripts/interact.py` and `scripts/leaf/`: the CLI, server, event
  model, validation, projection, vendoring, and export;
- `skills/leaf/assets/`: the browser runtime, registry, theme, and icon;
- `skills/leaf/packages/default/`: the bundled content vocabulary, widgets,
  modules, and vendor files;
- `skills/leaf/references/`: page-authoring and internal protocol references;
- `hooks/hooks.json`: the shared host hooks.

`examples/` is the authored-page and render corpus. `tests/` covers the file,
CLI, browser, and published-site boundaries. `scripts/` owns developer preview,
site, demo, and vendor tooling.

Read the scoped instructions for the area being changed:

- `plugins/leaf/CLAUDE.md`: shipped-payload and host dependency rules;
- `plugins/leaf/skills/leaf/CLAUDE.md`: browser, widget, registry, and theme;
- `plugins/leaf/skills/leaf/scripts/CLAUDE.md`: Python boundaries and protocol
  references;
- `examples/CLAUDE.md`: corpus and preview fixtures;
- `tests/CLAUDE.md`: test setup and evidence rules;
- `scripts/CLAUDE.md`: repository tooling and generated outputs.

## Cross-runtime invariants

### The document starts state; the log changes it

Authored markup is the initial condition. The append-only event log records
transitions. Every current-state projection starts with markup and applies the
standing log; do not add a database, derived current-state file, widget-specific
replay list, or DOM-backed authority beside them.

A later version preserves a reader decision unless it explicitly retracts what
the decision rests on. Use `restated` when a rewrite invalidates one. An `undo`
event names the gesture withdrawn; it never deletes or invents a counter-event.

Actions and reports share the registry-declared coordinate of owner widget,
fold unit, and facet. Python and JavaScript derive winners, retractions, and
settlement from the same declarations. Page-widget state is bounded by document
version; widgets frozen into thread markup use the conversation window.

The page directory is the durable record and deployment unit. `index.html` is
mutable author source; revisions and stamped versions are immutable. The event
log is append-only, while `data.json` is the explicit replace-in-place authority
for typed external data. A source id keeps one contract for the page's lifetime.
`plugins/leaf/skills/leaf/references/internals/page-storage.md` defines the
complete layout.

### Validate once and share readings

Validate each input at its boundary: browser events at `POST /api/event`,
authored markup at `version check`, message markup at `check_markup`, and replayed
action detail in `applyAction`. Downstream code reads validated fields directly.

A passage is one sequence of `{node, start, end}` segments. The file and browser
readings share collapse and resolution rules. `says` is visible, pointable text;
`wrote` is authored text. File capture must never accept an anchor the rendered
page cannot resolve. Repeated text without unique context detaches instead of
falling back to order or offsets.

### Keep the layer open

Content widgets stay anonymous outside their module. A new family should require
only a complete registry entry, its module, and theme rules. Runtime, Python,
CSS, tests, catalog, and docs consume declarations rather than tag-name lists.
Layer-wide facts live under `$` keys; each tag entry is one complete schema.

## Working on the repository

The normal suite is:

```sh
uv run pytest tests
```

`tests/CLAUDE.md` owns environment setup, focused runs, nightly selection, and
the Linux suite. `wt merge` runs pre-commit and the complete nightly suite on the
rebased tree.

Re-vendor before trusting a browser result after a runtime, theme, registry, or
widget change. Run `/ui-sweep` and inspect a composed page for any user-visible
layer change; a green suite does not judge visual quality.

Hand off a visible change with the smallest preview that proves it. A static
change needs one sentence and an `lf-shot` before/after from the same fixture,
viewport, and state. Add another state, width, recording, or live link only when
the first comparison cannot show the behavior.

Land with `wt merge`, a direct local squash merge to `main`, never a PR. Landing
still requires the user's authorization. If a newer `main` dislodges a merge
after this branch passed the full suite, `wt merge --no-hooks` may reuse that
result; finish with `git push origin main:main` because the skipped hook normally
pushes. `✗ Can't push to local main branch` is a fast-forward failure instead.

Installed sessions load host caches, not the checkout. After pushing, Claude
Code updates on its marketplace sweep. Codex needs
`codex plugin marketplace upgrade leaf`, then `codex plugin add leaf@leaf`.
