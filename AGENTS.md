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
- **Live revisions.** Agents update an open page continuously, with low latency,
  while the user reads, comments, and interacts.
- **Contextual threads.** Users read and answer floating threads beside the
  passages they concern.
- **Drawing comments.** Users point at visual details with freehand ink as well
  as text and semantic anchors.
- **Public website.** Visitors try interactive examples on leaf.page.
- **Consistency.** One interface across sessions and agents — keybindings,
  threads, and how a widget answers a move — so the user learns it
  once.
- **Trust.** An action records its meaning when taken, so a control does what
  it says and the record shows what the user decided.
- **Presentation craft.** Layout, type, and composition that hold at every
  width and beside every open panel, improved once and inherited by every
  page. A bespoke site starts from nothing each time.
- **Self-checks.** A check the agent runs on its own page, so a mistake reaches
  the agent rather than the user.

Leaf standardizes reading, commenting, and actions across sessions and agents.
Page content and composition remain the agent's and user's choices.

## Stage

Leaf has no users, deployment, database, or persisted state that constrains new
code. Prefer the simpler interface even when it is incompatible. Delete and
regenerate stale state. Add a guard only for a reachable condition with a useful
response.

Regenerate or discard claims, logs, and pages from earlier runtimes. Add no
migration, compatibility shim, or removal promise. Leave old state and recovery
instructions out of the handoff.

The state home is one directory per machine, written at once by every worktree,
harness and session on it, each running the leaf it was built from, so a record
older than the code reading it is ordinary rather than exceptional. If a record
lacks fields this version expects, Leaf ignores it where it is loaded and treats
the thing it described as absent. It neither migrates the record nor fails the
session: a session is never taken down by state it does not own.

Tests should protect behavior a user depends on. Treat rewriting or deleting a
test as an ordinary part of a code change. Check which behavior its assertion
protects, change it where that produces a better app, and say in the commit
which behavior changed.

Written contracts describe the current code; they impose no compatibility
obligation. Packages, harnesses, integrations, and consumers of the references are
all in this tree. When a different contract makes the code simpler, update it
and every consumer together, including prose that relies on the old shape.

Leaf's own restrictions do not settle what a feature may do either. When a
content security policy, a validator's refusal, an import allowlist, or a limit
on what some markup may carry stands between the user and a feature, raise it
with the user rather than dropping the feature or working around it quietly.
Name the restriction, what it blocks, what it protects, and what lifting it
would cost. It may guard something the user values, or it may be a side effect
nobody chose, and only the user can weigh the feature against it.

Coherent new features can be tried before every product detail is settled, so
long as any architectural problem they leave remains easy to fix.

Make improvements that follow from the repository. Ask the user only when the
choice depends on purpose or intent the code cannot supply.

## Fix the underlying issue

When packages or runtimes use the same concept, one owner defines its meaning
through a contract that expresses its different uses. A bug can reveal a
missing primitive, a misplaced boundary, or an unstated rule shared by several
packages.

Keep one canonical API per capability. Consumers own selections and transformations
of its returned data; sharing an implementation does not justify exposing those as
new APIs. Add a separate API only for an orthogonal capability or guarantee that
composing the existing API cannot provide; extend the canonical API when its
existing responsibility is incomplete.

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
`.agents/plugins/marketplace.json` both name `./` as the payload, and
`package.json`'s `pi` key makes it a Pi package, so Claude Code, Codex and Pi
install the tracked tree whole. Read the scoped `AGENTS.md` before changing its area.

- `bin/leaf`, `pyproject.toml`, and `uv.lock`: the launcher and its uv project;
- `skills/leaf/scripts/leaf/`: the CLI, server, event model, validation,
  projection, vendoring, and export (`skills/leaf/scripts/AGENTS.md`);
- `skills/leaf/assets/`: the browser runtime, registry, theme, and icon
  (`skills/leaf/assets/AGENTS.md`, and `skills/leaf/assets/runtime/keyboard/AGENTS.md`
  for commands, bindings, and scopes);
- `skills/leaf/packages/`: the bundled packages (`skills/leaf/packages/AGENTS.md`);
- `skills/leaf/references/`: contracts for page authors, package authors, and harnesses;
- `.claude/skills/developing-leaf/`: the maintainer workflow and vocabulary;
- `hooks/`: each harness's registrations of the `leaf hook` entry: `hooks.json`
  for Claude Code, with `claude-code.ts`, the opt-in hooks module that keeps its
  watch, `codex.json` for Codex, and `pi.ts`, the Pi extension;
- `evals/`: cases a headless agent answers, scoring the shipped instructions;
- `examples/`: the pages the site publishes, which are also the render corpus
  (`examples/AGENTS.md`);
- `tests/`: the suite, with the runtime's folds under `tests/runtime/`, which Node
  runs without a browser (`tests/AGENTS.md`);
- `build/`: the browser framework's TypeScript and the builds of every committed
  browser bundle (`build/AGENTS.md`);
- `dev/`: the `leaf_dev` package, whose `leaf-dev` commands preview, build, verify,
  and generate what the repository needs, and probe, screenshot, and compare
  versions of Leaf (`dev/AGENTS.md`);
- `worker/`: the Cloudflare Worker behind <https://leaf.page/>, serving published
  pages at the edge and routing private mutable state to `leaf_website` in
  per-user containers; `worker/README.md` owns deployment and diagnostics;
- `docs/`: the site's own pages, each a Leaf source, so changing what the site
  says is a page edit;
- `TODO.md`: the ordered priority list;
- `notes/`: research and plans for unresolved work. When a design lands, its
  contract moves beside the code or into a reference, and the note is deleted.

For any work whose subject is Leaf itself, load `/developing-leaf`, including
research and prototypes that change no tracked code. The shipped `/leaf` skill is
for agents that use Leaf or extend its package interface.

### Where instructions live

The sections above **Repository map** are the maintainer's direction; change them
only when the user asks. An `AGENTS.md` holds what an agent needs before changing
its area: goals, invariants that span modules, who owns what, and the gates to
run. A contract one module owns goes in that module's header, a helper's in its
docstring, and how a rule was found in the commit message. A header also records the
product decisions its module embodies and the alternatives they rejected; a change
that reverses one rewrites that record and says so in its commit. A workflow for one
kind of task goes in `/developing-leaf`.

### The install runs this tree

Consumer installers follow the CI-built `prepared` Git branch. The browser kernel
is compiled there; development branches keep its source modules. The leaf.page
container runs the same preparation, which `leaf-dev site` builds beside the site. Installation,
page authoring, custom packages, and export require no browser build or npm command.
`dev/leaf_dev/distribution.py` owns preparation and publication.

An install is the tracked tree copied into a harness's plugin cache, and nothing is
built at install time: `bin/leaf` is `uv run --no-dev` on the tree, so the
install must be writable, and Leaf writes nothing else there. Point Codex
at the git source, since a local-directory marketplace copies a checkout's
`.venv` too. A plugin update may replace the directory wholesale, so what has to
survive one belongs in the page directory or the state home. Runtime
dependencies, and those a package script declares, state a floor and no cap. The
host supplies Chrome and `jq`; leaf never downloads a browser.

Files under `skills/leaf/assets/vendor/` and each package's `vendor/` are
generated and committed where their consumer reads them; `build/AGENTS.md` says
how to regenerate them.

Every tracked byte ships in every install and stays in history, so the tree
holds no binary files and no large ones. An image a tool in this repository
reads, such as the demo recording, a catalog preview, an example page's image,
or an eval case's capture, is published to `max-sixty/leaf-assets` at the path
its reader looks for it and pinned by `leaf-assets.json`
(`dev/leaf_dev/leaf_assets.py`). Publishing there belongs to the change that
needs the images and takes no separate approval: it appends a commit and moves
only this checkout's pin, so no other branch reads a different image. A new media
`revision` also carries whatever other branches published since the old one, so a
conflict there takes the later pin. Where both branches published the same file,
the later pin holds the later publication's copy, so that file is published again
from the merged tree. A `thread_snapshots_revision` holds only its own branch's
reviewed appearance, so a conflict there is accepted again from the merged tree.
Evidence, such as screenshots, probe
captures, recordings and raw run output, stays in `.tmp/` and reaches the user
on a Leaf page; a note keeps the finding and the command that reproduces it,
not the capture. The suite refuses a binary file, and pre-commit refuses a new
file over 500 KB.

## Cross-runtime invariants

### The document starts state; the log changes it

Authored markup is a page's initial state. The append-only event log records
transitions. Every current-state projection starts from the markup and
applies the standing events, those not withdrawn. Add no database, derived
current-state file, widget-specific replay list, or DOM-backed authority beside them.

A later version keeps a user decision unless it explicitly retracts what the
decision rests on; use `restated` when a rewrite invalidates one. An `undo` event
names the gesture it withdraws; it never deletes an event or invents a
counter-event.

Actions and reports share one registry-declared key: owner widget, fold unit, and
verb. Admission records the command's declared meaning in the event, so a later
reader recovers it without the widget. Python derives winners, retractions,
settlement, Asks, threads, and updates in one transaction-consistent browser view.
JavaScript combines that view with authored initial values and unresolved local
gestures into complete widget and thread state, and widgets render it, unset and
undecided values included. Undo never reconstructs widgets or replays baseline
actions into the DOM. Page-widget state is bounded by document version; widgets
frozen into thread markup use the thread window.

A forward gesture whose result the page can draw shows that result in the turn that
sends it, before the log answers; a disabled control, spinner, or other delivery
status is not that result. The page can draw what its own document settles, such as
a widget's state or a thread's turn. Which Asks the document still holds, and which
of them the user owes, depend on the whole log, so that reading changes only when
the browser adopts the state the gesture's own POST returns; the browser never
derives it. A refusal restores the authoritative state.

The active document has one immutable application publication. Only its publisher
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
evidence. The banner describes page activity; each serving page publishes a compact
canonical activity summary for neighboring rows (`server_rows.py`). The summary is
disposable delivery output; neighboring readers consult it and server liveness,
never another page's log or document.
Messages, thread attention, and margin entries consume the canonical workflows;
thread attention also retains outstanding user Asks. Page activity does not imply
work on every message. JavaScript adds unresolved local sends through the
application publisher and may schedule a read at `next_transition_at`; it does not
age or independently reclassify accepted workflow evidence. The stop guard consumes
the same underlying response obligations.

The page directory is the durable record and deployment unit: mutable `index.html`,
immutable revisions, an append-only event log, and one replaceable JSON file per
external-data source under `data/`. `data.json` records each source's current
contract; a later document may replace that binding. `skills/leaf/scripts/leaf/page-storage.md`
defines the complete layout.

### Validate once and share readings

Validate each input once, at its boundary: every event at the one append door,
whether the browser posted it or a command wrote it; authored markup at
`page check`; message markup at `check_markup`. Admission then derives the event's
server-owned meaning, and downstream code reads those fields directly. Event
dependencies name declared identities; ordinary detail text is never read as a
reference.

A passage is one sequence of `{node, start, end}` segments, and the file and browser
readings share its collapse and resolution rules. `says` is visible, pointable text;
`wrote` is authored text. File capture never accepts an anchor the rendered page
cannot resolve. Repeated text without unique context detaches rather than falling
back to order or offsets.

### Keep the layer open

Content widgets stay anonymous outside their module, so a new family needs only a
complete registry entry, its module, and theme rules. Runtime, Python, CSS, tests,
agent queries, and docs read declarations, never tag-name lists. Layer-wide facts
live under `$` keys; each tag entry is one complete schema.

## Working on the repository

When the user is to choose among designs, show the candidates in a playground
(`/developing-leaf`, "Explore an open design").

Before finishing a feature:

- Give every action a keyboard route, without spending a page-level binding on
  each one, and a route a finger can take (`runtime/keyboard/AGENTS.md`, "Touch
  routes").
- Follow `examples/AGENTS.md` when adding or changing a feature, and regenerate
  the derived corpus.
- If the feature changes what an agent can do or how it should do it, update
  `skills/leaf/SKILL.md` or the one routed reference that owns the workflow;
  other references point at that section by name. Shipped instructions set goals
  for the user's experience and name the surface they read on; they leave
  format and phrasing to the agent. Where an agent could read the change more
  than one way, score it with `evals/` before and after (`/developing-leaf`,
  "Score an instruction change").

Local compute is often the bottleneck because several sessions share one machine.
Before widening a local test selection or increasing parallelism, check current
CPU use, memory pressure, and other running test suites. Weigh the extra evidence
against the cost to all sessions; on a busy host, favor focused checks and avoid
redundant overlapping runs. The required landing gates still have to pass.

Before handing over, run the tests that hold what the change touches; the broad
selection, `uv run pytest tests`, and `npm run test:runtime` run at landing
(`tests/AGENTS.md`, "Run what the change needs"). Two TypeScript trees,
`worker/src/` and `build/browser/`, and the JavaScript lock every committed bundle is built from have gates the suite and
pre-commit do not reach. Both landing paths run all of them: a pull request in its
`test` job, and `wt merge` in the pre-merge blocks of `.config/wt.toml`.
`package.json` owns their shared Node gate list in `check` and their earlier
bundle rebuild in `check:bundles`. `wt hook pre-merge` runs that local gate without landing, on a committed
tree, since the bundle check fails on any uncommitted change. The website's delivery
checks — the site build, the Worker's dry-run deploy, and
`leaf-dev verify-site website-worker` — run on a pull request and in `publish-site` before it
deploys, not in `wt merge`.

For a change that can alter browser startup, compare base and candidate at the
boundary it affects: served previews for a runtime change, and
`leaf-dev verify-site website-worker` for site delivery, Worker routing, or containers.
Read the comparison by phase: document receipt, widget upgrade, and authoritative
presentation. Compare the requests and bytes loaded before presentation directly;
elapsed time is diagnostic. A change that adds work before presentation states the
user-visible benefit and why it cannot wait. Bytes off that path, such as a lazily
loaded module, a vendored file, or the install's size, are not on their own a reason
for a change.

Land through a pull request or with `wt merge`, which squash-merges to `main`.
`/developing-leaf` covers landing with a red gate; Tend sessions follow
**Landing** in `.claude/skills/running-tend/SKILL.md`.
