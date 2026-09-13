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
  projection, vendoring, export, and their code-adjacent internal contracts;
- `skills/leaf/assets/`: the browser runtime, registry, theme, and icon;
- `skills/leaf/packages/`: the default and optional bundled content vocabularies,
  widgets, modules, and vendor files;
- `skills/leaf/mcp-app/`: the MCP App resource an MCP host reads;
- `skills/leaf/references/`: public contracts for page authors, package authors, and
  hosts;
- `.claude/skills/developing-leaf/`: the maintainer workflow and implementation
  vocabulary;
- `hooks/hooks.json`: the shared host hooks.

`examples/` is the authored-page and render corpus. `tests/` covers the file,
CLI, browser, and published-site boundaries. `scripts/` owns developer preview,
site, demo, and vendor tooling. `worker/` is the Cloudflare Worker behind
<https://leaf.page/> — it serves the built site and routes each example to the
canonical Python server in a per-reader container. Its container adapter,
`worker/server.py`, is ordinary Python that `tests/` covers; its TypeScript half
is the one part of the tree with a gate of its own that `tests/` does not reach.
Agents on `max-sixty` use the finely grained Cloudflare token available there
for API and Wrangler access.

`docs/` is the site's own content: each product document there is a Leaf source,
which `scripts/site.py` publishes as a complete page directory beside the worked
examples. Changing what <https://leaf.page/> says is a page edit, not a template
edit.

`TODO.md` is the ordered priority list. `notes/` holds active research,
experiments, and plans for unresolved or future work. Once a design lands, move
its contract beside the code or into the public reference whose reader acts on
it, then delete the note. Git history carries superseded plans and rejected
alternatives; a note is never a second specification for shipped behavior.

Read the scoped instructions for the area being changed:

- `skills/leaf/assets/CLAUDE.md`: browser runtime, widget modules, registry, and theme;
- `skills/leaf/scripts/CLAUDE.md`: Python boundaries and protocol references;
- `examples/CLAUDE.md`: corpus and preview fixtures;
- `tests/CLAUDE.md`: test setup and evidence rules;
- `scripts/CLAUDE.md`: repository tooling and generated outputs.

For any change to Leaf itself, load `/developing-leaf`. The shipped `/leaf`
skill is for agents that use Leaf or extend its public package interface.

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
Chrome — or, ahead of it, whichever executable `LEAF_BROWSER_EXECUTABLE`,
`CHROME_PATH`, or `CHROME_BIN` names — else the first browser on `PATH`, and
leaf does not download a browser.

`uv` owns `.venv/`; a `.venv` inside an installed copy is uv doing its job, not
stray state to clean up. Nothing else is written back: no cache leaf keeps for
itself, no generated file, no repaired state. Plugin updates may replace the
directory wholesale, so what has to survive one belongs in the page directory
or the state home.

Files under `skills/leaf/assets/vendor/`, any package's `vendor/` — `default/`,
`diagram/`, `diff/` today — and `skills/leaf/mcp-app/` are committed payload
outputs, and each sits where its consumer reads it. A bundle lives in the
package whose widget imports it, so a page that never draws a diagram or a diff
never vendors their renderers; the MCP App resource sits outside the layer
because an MCP host reads it from the install rather than from a page. Their
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
fold unit, and facet. Admission records the command's declared meaning in the
event, so historical readers do not need a surviving widget to recover it.
Python derives winners, retractions, settlement, asks, threads, and updates in
one transaction-consistent browser view. JavaScript combines that view with
authored initial values and unresolved local gestures to derive complete widget
and conversation state. Every forward gesture whose semantic result the page can draw is on
screen in the turn that sends it, before the log answers; a disabled control, spinner,
or other delivery status is not that result. Refusal restores the authoritative state.
Widgets render that state, including unset and undecided values; undo
does not reconstruct widgets or replay baseline actions into the DOM. Page-widget
state is bounded by document version; widgets frozen into thread markup use the
conversation window.

Python also derives one top-level `activity` reading from the agent's status
declaration, claim and turn identity, watcher lease, pickup events, and unsettled
reader moves. The banner, thread receipts, margin receipts, neighboring-page rows,
agent state, and stop guard consume that projection. JavaScript may schedule a new
state read at its `next_transition_at`; it does not age, override, or independently
combine those facts.

The page directory is the durable record and deployment unit. `index.html` is
mutable author source; revisions are immutable, and append-only notes bind public
versions to them. The event log is append-only, while `data.json` is the explicit
replace-in-place authority for typed external data. A source id keeps one contract
for the page's lifetime.
`skills/leaf/scripts/leaf/page-storage.md` defines the complete layout.

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

Validate each input at its boundary: browser commands at `POST /api/event`,
authored markup at `version check`, and message markup at `check_markup`.
Admission derives server-owned event meaning after validation; downstream code
reads those fields directly. Event dependencies name declared identities;
ordinary detail text is never interpreted as a reference.

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
- Give every action a keyboard route. Keyboard shortcuts keep actions reachable without spending a
  page-level binding on each one.
- Follow `examples/CLAUDE.md`'s page-fixture rules when adding or changing a feature,
  and regenerate the derived corpus.
- If the feature changes what an agent can do or how it should do it, update
  `skills/leaf/SKILL.md` or the routed reference that owns the workflow. Shipped
  guidance sets goals for the reader's experience and names the surface they read
  on; it leaves format and phrasing to the agent's judgment.
- Update any public docs or generated outputs the feature affects.

The normal suite is:

```sh
uv run pytest tests
```

`tests/CLAUDE.md` owns environment setup, focused runs, nightly selection, and
the Linux suite. `wt merge` runs pre-commit and the everyday suite on the rebased
tree. Pull requests and main run that gate plus the website-worker checks. Tend
adds focused tests during review. A daily CI run exercises the complete suite in
one job.

That suite reads the Python adapter under `worker/`: `tests/test_website_server.py`
loads `worker/server.py` and `worker/reply.py` and drives their route, and pre-commit's
ruff hooks take them as they take every other Python file. Nothing on either landing
path parses `worker/src/`: pre-commit's whitespace and typos hooks take those files,
but its prettier and eslint hooks take JavaScript and HTML rather than
TypeScript. So a TypeScript change carries no gate until `ci`'s
`test` job runs it, which on a `wt merge` is after main has already moved. Run
it before landing one:

```sh
npm ci --prefix worker
npm run typecheck --prefix worker
npm test --prefix worker
```

Treat website performance as a phase profile, not one score. For a change that can
alter browser startup, compare the base and candidate readings from
`scripts/verify-site-local.sh`: document receipt, widget upgrade, authoritative
presentation, and the requests and bytes loaded by presentation. Compare request counts
and bytes directly; elapsed time is diagnostic because it varies with the machine and
network. If a change adds work before presentation, state the user-visible benefit and
why that work cannot wait until after presentation.

Land through a pull request or with `wt merge`, which squash-merges directly to
`main`. Landing requires the user's authorization. For a local merge, if a newer
`main` dislodges the merge after this branch passed the local gate,
`wt merge --no-hooks` may reuse that result; finish with
`git push origin main:main` because the skipped hook normally pushes.
`✗ Can't push to local main branch` is a fast-forward failure instead.

A branch lands with a red gate when every failure in it is one the branch did
not cause. Establish that from the failing node ids on the exact merge-base SHA,
under the same CI job and selection: a case can fail on CI's Linux fonts and pass
on a Mac, or fail inside the whole suite under the default `-n 2` and pass alone
under `-n0`. Use the base SHA's GitHub Actions run as the control; a local Docker
image is not the hosted runner, and an Apple-silicon image must either emulate the
CPU or give up installed Chrome. A green run several commits behind the base is
not that control. Until the failure reproduces on the base SHA, it is this
branch's. Once it does, the branch lands the ordinary way, and a red hook takes
the `--no-hooks` route above. `lint` is the only required check, so a red `test`
does not block a merge and this rule is all that gates one.

Installed sessions load host caches, not the checkout. After pushing, Claude
Code updates on its marketplace sweep. The post-merge hook refreshes an installed
Codex plugin; after a merge that skipped hooks, run
`codex plugin marketplace upgrade leaf`.
