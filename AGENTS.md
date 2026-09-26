# leaf

Leaf is a page an agent hands to a user and the loop that carries anchored
comments and actions back. `README.md` describes the product.

## Leaf's role

The agent is the author; the user is its principal. A Leaf page is how the
user sees the agent's work and steers it: they read, point at exact
passages, and act, and the agent answers by revising the page.

The agent decides both a page's content and its presentation. The user's
word overrides either, whether given in a comment or as a standing preference,
and Leaf's own defaults yield to both.

Leaf supplies what the agent builds with: primitives, instructions, and
templates. An agent could instead build a bespoke site for each task, so each
primitive must give the user something that site would not:

- **Difficult code.** Mechanisms too hard to write well each time: anchored
  threads, widgets whose state survives a revision, and the event log that
  returns each comment and decision to the agent as a structured event.
- **Consistency.** One interface across sessions and agents — keybindings,
  threads, and how a widget answers a move — so the user learns it
  once.
- **Trust.** A page runs under a locked-down content policy, and an action
  records its meaning when taken, so a control does what it says and the
  record shows what the user decided.
- **Presentation craft.** Layout, type, and composition that hold at every
  width and beside every open panel, improved once and inherited by every
  page. A bespoke site starts from nothing each time.
- **Self-checks.** A check the agent runs on its own page, so a mistake reaches
  the agent rather than the user.

Leaf is the medium: every choice on a page is the agent's or
the user's. Leaf fixes how to read, comment, and act, so that stays the same
across sessions and agents; what a page says and how it is composed is the
agent's to decide.

## Stage

Leaf has no users, deployment, database, or persisted state that constrains new
code. Prefer the simpler interface even when it is incompatible. Delete and
regenerate stale state. Add a guard only for a reachable condition with a useful
response.

Nothing is owed to what an older version wrote. A change needs no migration, no
shim that reads the old shape, and no dated note promising to remove one:
claims, logs, and pages vendored against an earlier runtime are regenerated or
thrown away. The handoff says nothing about them either. Steps for reviving
stranded state are that same migration written in prose, and they spend the
user's attention on state nobody needs.

The state home is one directory per machine, written at once by every worktree,
host and session on it, each running the leaf it was built from, so a record
older than the code reading it is ordinary rather than exceptional. If a record
lacks fields this version expects, Leaf ignores it where it is loaded and treats
the thing it described as absent. It neither migrates the record nor fails the
session: a session is never taken down by state it does not own.

The suite does not constrain new code either. Agents wrote every test in
`tests/`, and most are overfit on the implementation they were written against:
they assert the shape the code happened to take rather than the behavior a
user depends on. Changing or deleting a test is an ordinary part of a code
change. Read what the assertion was holding, rewrite it where that leaves a
better app, and say in the commit which behavior moved.

The written contracts do not constrain new code either. No package, host, or
integration exists outside this repository, so every reader of
`skills/leaf/references/`, a package's guidance, or a protocol sidecar is in
this tree. What those files state is what the code does now, and a promise to
nobody. When a change is simpler under a different contract, whether that is
an id's form, an event's shape, a command's output, or what a host is told
to key on, change the contract and its consumers in the same change. A
sentence in a reference saying that something relies on the current shape is
a consumer to update, never a reason to keep the shape or to carve an
exception around it.

Coherent new features can be tried before every product detail is settled, so
long as any architectural problem they leave remains easy to fix.

Make improvements that follow from the repository. Ask the user only when the
choice depends on purpose or intent the code cannot supply.

## Fix the underlying issue

Leaf's first implementation was written quickly, with weak abstractions. Many
small bugs reveal a missing primitive, a misplaced boundary, or a rule the code
never stated; the same problem can resurface in another package under a
different name. The current goal is a coherent shared layer: when packages or
runtimes use the same concept, one owner defines its meaning through a contract
that can express its different uses.

Every change and every review must assess whether the immediate problem is a
symptom of an underlying problem. Follow its causes until the next boundary is
right as designed; the wrong boundary below it is where the fix belongs. If the
current change cannot make that fix, the author or reviewer names and proposes
it. A passing test for the reported case establishes only that case. A second
special case, a caller repeating its callee's rule, a guard restating a rule
the code never states, or a flag passed through a stack to reach one use
suggests the shared boundary remains unsettled.

Do not add another patch on top of the ones already there. A change that
settles the immediate symptom and leaves the code harder to maintain does not
go in, and filing the real fix behind it does not redeem it: the next change
has to undo that patch first. Deferring an underlying fix is reasonable only
when the current change leaves it as easy to make as it was before.

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

`evals/` scores the shipped guidance with cases a headless agent answers.
`examples/` is the authored-page and render corpus. `tests/` covers the file,
CLI, browser, and published-site boundaries, and in `tests/runtime/` the folds the
shipped runtime performs, which Node runs without one. `scripts/` owns developer preview,
site, demo, vendor, and browser-framework tooling. `worker/` is the Cloudflare
Worker behind <https://leaf.page/> — it serves the built site and routes each
example to the canonical Python server in a per-user container. Its container
adapter, `worker/server.py`, is ordinary Python that `tests/` covers. Its
TypeScript half and the TypeScript under `scripts/browser/` are the two parts of
the tree with gates of their own that `tests/` does not reach.
`worker/README.md` names Leaf's three Cloudflare tokens, what each reaches, and
how an unattended agent loads one for API and Wrangler access.

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

- `skills/leaf/assets/AGENTS.md`: browser runtime, widget modules, registry, and theme;
- `skills/leaf/scripts/AGENTS.md`: Python boundaries and protocol references;
- `examples/AGENTS.md`: corpus and preview fixtures;
- `tests/AGENTS.md`: test setup and evidence rules;
- `scripts/AGENTS.md`: repository tooling and generated outputs.

For any work whose subject is Leaf itself, load `/developing-leaf`, including
interface research and prototypes that will not change tracked code. The shipped
`/leaf` skill is for agents that use Leaf or extend its public package interface.

### The install runs this tree

An install is this tracked tree, copied into a host's plugin cache. Claude Code
copies exactly the tracked files; Codex copies its marketplace clone wholesale,
`.git` included, and a local-directory marketplace would sweep in a checkout's
`.venv` too — measured, 163M — so point Codex at the git source. Nothing is
built at install time: `bin/leaf` is `uv run --no-dev` on this tree, and `uv`
owns what that writes, so the install has to be writable by the session running
leaf. Leaf writes nothing else there, and a plugin update may replace the
directory wholesale, so what has to survive one belongs in the page directory or
the state home.

Runtime dependencies, and those a package script declares, state a floor and no
cap. The host supplies Chrome and the `jq` version the README names; leaf never
downloads a browser (`skills/leaf/scripts/leaf/validation.md`, "Browser
validation").

Files under `skills/leaf/assets/vendor/`, any package's `vendor/` — `default/`,
`diagram/`, `diff/` today — and `skills/leaf/mcp-app/` are committed payload
outputs, and each sits where its consumer reads it. A bundle lives in the
package whose widget imports it, so a page that never draws a diagram or a diff
never vendors their renderers; the MCP App resource sits outside the layer
because an MCP host reads it from the install rather than from a page. Their
generators and source-version choices live under `scripts/`; follow
`scripts/AGENTS.md`, update or run the owning script, and do not patch a
generated bundle directly.

## Cross-runtime invariants

### The document starts state; the log changes it

Authored markup is the initial condition. The append-only event log records
transitions. Every current-state projection starts with markup and applies the
standing log; do not add a database, derived current-state file, widget-specific
replay list, or DOM-backed authority beside them.

A later version preserves a user decision unless it explicitly retracts what
the decision rests on. Use `restated` when a rewrite invalidates one. An `undo`
event names the gesture withdrawn; it never deletes or invents a counter-event.

Actions and reports share the registry-declared coordinate of owner widget,
fold unit, and verb. Admission records the command's declared meaning in the
event, so historical readers do not need a surviving widget to recover it.
Python derives winners, retractions, settlement, asks, threads, and updates in
one transaction-consistent browser view. JavaScript combines that view with
authored initial values and unresolved local gestures to derive complete widget
and thread state. Every forward gesture whose semantic result the page can draw is on
screen in the turn that sends it, before the log answers; a disabled control, spinner,
or other delivery status is not that result. What the page can draw is what its own
document settles: a widget's state, a thread's turn. Which Asks the document still holds
and which of them the user owes are settled by the whole log, so that reading moves
when the state a gesture's own POST returns is adopted, and the browser never folds a
second answer to it. Refusal restores the authoritative state.
Widgets render that state, including unset and undecided values; undo
does not reconstruct widgets or replay baseline actions into the DOM. Page-widget
state is bounded by document version; widgets frozen into thread markup use the
thread window.

The active document has one immutable application publication. Its publisher alone
combines authored baselines, the complete admitted server reading, and the ordered
unresolved ledger into current state; browser components consume read-only selections
from it. Presentation proof is separate: it records whether required renderers have
committed the active document's current semantic epoch. Renderer nodes, promises, and
DOM attributes never enter the semantic snapshot.

A publication is also what starts a renderer. Each one claims its region inside that
synchronous publication and paints the current root on the pass that follows, so a
caller that changes what the page shows publishes and waits for proof rather than
naming renderers or sequencing them. Where one renderer reads DOM another materializes,
that order is declared once, beside the coordinator, not repeated at each publisher.

Focus, scroll, selection, disclosure, draft editing, drag, and layout remain with their
mechanical browser owners until a gesture becomes a declared application fact. Their
renderings are not semantic authority, and repainting them does not create a semantic
epoch. That state also lives exactly as long as the node holding it: the log does not
record it and no projection returns it, so whatever replaces a node hands it across
itself, under the identity that replacement already keys on, or the user loses it.

Python derives page-wide `activity` and exact-input `workflows` from the agent's
status declaration, claim and turn identity, watcher lease, delivery, and response
evidence. The banner and neighboring-page rows describe page activity. Messages,
thread attention, and margin entries consume the canonical workflows; thread
attention also retains outstanding user Asks. Page activity does not imply work
on every message. JavaScript adds unresolved local sends through the application
publisher and may schedule a read at `next_transition_at`; it does not age or
independently reclassify accepted workflow evidence. The stop guard consumes the
same underlying response obligations.

The page directory is the durable record and deployment unit: mutable `index.html`,
immutable revisions, an append-only event log, and one replaceable JSON file per
external-data source under `data/`, whose source ids keep the contract `data.json`
records for the page's lifetime. `skills/leaf/scripts/leaf/page-storage.md`
defines the complete layout.

A request is a durable, non-undoable one-shot instruction whose external effect
may precede its receipt. The append door admits one pending request per declared
seat atomically; failure reopens the seat and success completes it. Exactly one
terminal receipt names each accepted request. Page seats are scoped to their
authored revision, while a seat in frozen thread markup lasts for that document's
whole lifetime. Packages own verbs, host meaning, guidance, and UI; Leaf owns only
the typed transport and canonical lifecycle projection. A package may declare that a
ready request is a user ask; acceptance hands the turn to the host, success closes it,
and failure returns it through that same projection.

### Validate once and share readings

Validate each input at its boundary: every event at the one append door, whether a
browser posted it or a command wrote it; authored markup at `version check`; and
message markup at `check_markup`. Admission derives server-owned event meaning
after validation; downstream code reads those fields directly. Event dependencies name declared identities;
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
- Follow `examples/AGENTS.md`'s page-fixture rules when adding or changing a feature,
  and regenerate the derived corpus.
- If the feature changes what an agent can do or how it should do it, update
  `skills/leaf/SKILL.md` or the routed reference that owns the workflow, and only
  that one: another reference whose reader meets the mechanism points at that
  section by name rather than restating it, since each copy drifts on the next
  change. Shipped guidance sets goals for the user's experience and names the
  surface they read on; it leaves format and phrasing to the agent's judgment.
  Score the change with `evals/` before and after, and add a case for the
  behavior it targets; `evals/README.md` says how.
- Update any public docs or generated outputs the feature affects.

`tests/AGENTS.md` owns environment setup, focused runs, nightly selection, and
the Linux authority.

The Python suite reads the adapter under `worker/`: `tests/test_website_server.py`
loads `worker/server.py` and drives its routes. Pre-commit's ruff hooks take it as they
take every other Python file. Four gates sit outside both the suite and pre-commit: the
TypeScript in `worker/src/` and in `scripts/browser/`, which prettier and eslint do not
parse; the committed bundles, which a rebuild from the root `package-lock.json` must
reproduce byte for byte; and the shipped runtime's folds under `tests/runtime/`, which
Node runs without a browser. Both landing paths run all four: a pull request in its
`test` job, and `wt merge` in the pre-merge blocks of `.config/wt.toml`, which name each
command. `wt hook pre-merge` runs that whole local gate without landing, on a committed
tree: the bundle check fails on any uncommitted change. The website's delivery checks —
the site build, the Worker's dry-run deploy, and `scripts/verify-site-local.sh` — run
on a pull request and in `publish-site` before it deploys, not in `wt merge`.

For a change that can alter browser startup, compare base and candidate at the
boundary the change affects: locally served previews for browser runtime changes;
`scripts/verify-site-local.sh` for changes to built-site delivery, Worker routing,
or containers. Treat performance as a phase profile: document receipt, widget
upgrade, authoritative presentation, and requests and bytes loaded by presentation.
Compare request counts and bytes directly; elapsed time is diagnostic because it
varies with the machine and network. If a change adds work before presentation,
state the user-visible benefit and why that work cannot wait until after presentation.
Bytes outside that profile — a lazily loaded module, a vendored file, the size of the
install — are not a reason for a change on their own.

Land through a pull request or with `wt merge`, which squash-merges directly to
`main`. User-directed landing requires the user's authorization; Tend sessions
follow **Landing** in `.claude/skills/running-tend/SKILL.md`. For a local merge,
if a newer `main` dislodges the merge after this branch passed the local gate,
`wt merge --no-hooks` may reuse that result; finish with
`git push origin main:main` because the skipped hook normally pushes.
`✗ Can't push to local main branch` is a fast-forward failure instead.

For user-directed landing, a branch lands with a red gate when every failure in
it is one the branch did not cause. Establish that from the failing node ids on
the exact merge-base SHA, under the same CI job and selection: a case can fail
on CI's Linux fonts and pass on a Mac, or fail inside the whole suite under the
default `-n 2` and pass alone
under `-n0`. Use the base SHA's GitHub Actions run as the control; a local Docker
image is not the hosted runner, and an Apple-silicon image must either emulate the
CPU or give up installed Chrome. A green run several commits behind the base is
not that control. Main's own push run survives the next merge and goes on to the
nightly selection once the everyday gate is green, but main holds one nightly slot,
so a commit whose turn a newer one took carries no nightly result. Push that SHA as
a branch and dispatch `ci` on it: a dispatch holds a slot per branch and does not
wait behind main's. Until the
failure reproduces on the base SHA, treat it as this branch's. Once it does, the
branch lands the ordinary way, and a red hook takes
the `--no-hooks` route above. `lint` is the only required GitHub check, so a red
`test` does not technically block a merge; this procedure gates user-directed
landing.

Installed sessions load host caches, not the checkout. After pushing, Claude
Code updates on its marketplace sweep. The post-merge hook refreshes an installed
Codex plugin; after a merge that skipped hooks, run
`codex plugin marketplace upgrade leaf`.
