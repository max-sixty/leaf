# leaf

Leaf is a page an agent hands to a user and the loop that carries anchored
comments and actions back. `README.md` describes the product.

## Stage

Leaf has no users, deployment, database, or persisted state that constrains new
code. Prefer the simpler interface even when it is incompatible. Delete and
regenerate stale state. Add a guard only for a reachable condition with a useful
response.

Use this freedom to try coherent new features and learn from them without
settling every product detail first. Surface architectural problems, but fix
them separately when the experiment leaves the architecture easy to change.

Make improvements that follow from the repository. Ask the user only when the
choice depends on purpose or intent the code cannot supply.

## Repository map

The repository is the plugin: `.claude-plugin/marketplace.json` and
`.agents/plugins/marketplace.json` both name `./` as the payload, and both
Claude Code and Codex install the tracked tree whole. Its main parts are:

- `pyproject.toml`, `uv.lock`, and `bin/leaf`: the uv project — runtime
  dependencies plus the suite's dev group — and the launcher that runs it;
- `skills/leaf/scripts/leaf/`: the CLI, server, event model, validation,
  projection, vendoring, and export;
- `skills/leaf/assets/`: the browser runtime, registry, theme, and icon;
- `skills/leaf/packages/`: the default and optional bundled content vocabularies,
  widgets, modules, and vendor files;
- `skills/leaf/references/`: page-authoring and internal protocol references;
- `hooks/hooks.json`: the shared host hooks.

`examples/` is the authored-page and render corpus. `tests/` covers the file,
CLI, browser, and published-site boundaries. `scripts/` owns developer preview,
site, demo, and vendor tooling.

Read the scoped instructions for the area being changed:

- `skills/leaf/CLAUDE.md`: browser, widget, registry, and theme;
- `skills/leaf/scripts/CLAUDE.md`: Python boundaries and protocol references;
- `examples/CLAUDE.md`: corpus and preview fixtures;
- `tests/CLAUDE.md`: test setup and evidence rules;
- `scripts/CLAUDE.md`: repository tooling and generated outputs.

### The install runs this tree

An install is this tracked tree, copied into a host's plugin cache. Claude Code
copies exactly the tracked files; Codex copies its marketplace clone wholesale,
`.git` included, and a local-directory marketplace would sweep in a checkout's
`.venv` too — measured, 163M — so point Codex at the git source. Nothing is
built at install time; the environment appears on the first `bin/leaf` run,
where `uv` syncs `.venv` beside `pyproject.toml`, so the install has to be
writable by the session running leaf.

`pyproject.toml` states each runtime dependency at the lowest version the suite
passes on, with no upper cap, and `uv.lock` ships beside it, so an install runs
the resolution the suite was last green on. Shipping the lock does not take the
host's index out of the loop: it records versions and hashes, and `uv sync`
asks the host's configured index for them, so a private mirror answers and an
offline run installs from `uv`'s cache. Python arrives on the same terms. The
host also supplies the `jq` authoring dependency at the minimum version named
in the README. The dev group — pytest, the accessibility checks, the demo
recorder's frames — is recorded in that same lock but never installed on a
host: `bin/leaf` passes `--no-dev`. Playwright is a runtime dependency, since
the skill's own flow renders pages; browser checks launch the host's installed
Chrome, or the executable `LEAF_BROWSER_EXECUTABLE` names where the host's browser
is some other Chromium, and leaf does not download a browser.

`uv` owns `.venv/`; a `.venv` inside an installed copy is uv doing its job, not
stray state to clean up. Nothing else is written back: no cache leaf keeps for
itself, no generated file, no repaired state. Plugin updates may replace the
directory wholesale, so what has to survive one belongs in the page directory
or the state home.

Files under `skills/leaf/assets/vendor/` and any package's `vendor/` —
`default/`, `diagram/`, `diff/` today — are committed payload outputs. A bundle
lives in the package whose widget imports it, so a page that never draws a
diagram or a diff never vendors their renderers. Their
generators and source-version choices live under `scripts/`; follow
`scripts/CLAUDE.md`, update or run the owning script, and do not patch a
generated bundle directly.

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
fold unit, and facet. Python derives winners, retractions, settlement, asks,
threads, and updates in one transaction-consistent browser view. JavaScript
resolves that view onto live DOM nodes and overlays only unresolved local
gestures. Page-widget state is bounded by document version; widgets frozen into
thread markup use the conversation window.

The page directory is the durable record and deployment unit. `index.html` is
mutable author source; revisions and stamped versions are immutable. The event
log is append-only, while `data.json` is the explicit replace-in-place authority
for typed external data. A source id keeps one contract for the page's lifetime.
`skills/leaf/references/internals/page-storage.md` defines the complete
layout.

A request is a durable, non-undoable one-shot instruction whose external effect
may precede its receipt. The append door admits one pending request per declared
seat atomically; failure reopens the seat and success completes it. Exactly one
terminal receipt names each accepted request. Page seats are scoped to their
authored revision, while a seat in frozen thread markup lasts for that document's
whole lifetime. Packages own verbs, host meaning, guidance, and UI; Leaf owns only
the typed transport and canonical lifecycle projection. A package may declare that a
ready request is a reader ask; acceptance hands the turn to the host, success closes it,
and failure returns it through that same projection.

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
CSS, tests, agent queries, and docs consume declarations rather than tag-name lists.
Layer-wide facts live under `$` keys; each tag entry is one complete schema.

## Working on the repository

Before finishing a feature:

- Keep the implementation, tests, and any owning protocol or reference aligned.
- Give every action a keyboard route. Chords keep actions reachable without spending a
  page-level binding on each one.
- Make the feature appear in at least one authored page under `examples/`.
  Implementing or changing it includes adding or updating a source example and
  regenerating the derived corpus.
- If the feature changes what an agent can do or how it should do it, update
  `skills/leaf/SKILL.md` or the routed reference that owns the workflow.
- Update any public docs or generated outputs the feature affects.

The normal suite is:

```sh
uv run pytest tests
```

`tests/CLAUDE.md` owns environment setup, focused runs, nightly selection, and
the Linux suite. `wt merge` runs pre-commit and the everyday suite on the rebased
tree. Pull requests run the same gate in CI. CI adds the complete nightly suite
after main moves.

Re-vendor before trusting a browser result after a runtime, theme, registry, or
widget change. For a user-visible layer change, an `/ui-sweep` and a look at a
composed page are worth the time; a green suite does not judge visual quality.

Hand off a visible change with the smallest artifact that proves it. For an
example, `scripts/preview.py [example] --export` prints a standalone HTML file
for static rendering; `scripts/preview.py [example]` serves an interactive
preview while its process runs. Build a behavioral prototype in its owning code
path, then serve an example that reaches it. One sentence and an `lf-shot`
before/after is the usual artifact for a static change; take the before and after
from the same fixture, viewport, and state, and add another state or width only
when the first comparison cannot show the behavior.

Land through a pull request or with `wt merge`, which squash-merges directly to
`main`. Landing requires the user's authorization. For a local merge, if a newer
`main` dislodges the merge after this branch passed the local gate,
`wt merge --no-hooks` may reuse that result; finish with
`git push origin main:main` because the skipped hook normally pushes.
`✗ Can't push to local main branch` is a fast-forward failure instead.

Installed sessions load host caches, not the checkout. After pushing, Claude
Code updates on its marketplace sweep. The post-merge hook refreshes an installed
Codex plugin; after a merge that skipped hooks, run
`codex plugin marketplace upgrade leaf`.
