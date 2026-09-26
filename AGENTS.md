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
`.agents/plugins/marketplace.json` both name `./` as the payload, so Claude Code
and Codex install the tracked tree whole.

- `pyproject.toml`, `uv.lock`, and `bin/leaf`: the uv project and the launcher
  that runs it;
- `skills/leaf/scripts/leaf/`: the CLI, server, event model, validation,
  projection, vendoring, and export, with their internal contracts beside them;
- `skills/leaf/assets/`: the browser runtime, registry, theme, and icon;
- `skills/leaf/packages/`: the bundled content vocabularies, widgets, and modules;
- `skills/leaf/mcp-app/`: the MCP App resource an MCP host reads;
- `skills/leaf/references/`: contracts for page authors, package authors, and hosts;
- `.claude/skills/developing-leaf/`: the maintainer workflow and vocabulary;
- `hooks/hooks.json`: the shared host hooks;
- `evals/`: cases a headless agent answers, scoring the shipped guidance;
- `examples/`: the authored pages the site publishes and the render corpus;
- `tests/`: the file, CLI, browser, and published-site boundaries, and in
  `tests/runtime/` the runtime's folds, which Node runs without a browser;
- `scripts/`: preview, site, demo, vendor, and browser-framework tooling;
- `worker/`: the Cloudflare Worker behind <https://leaf.page/>, which routes each
  example to the Python server in a per-user container; `worker/README.md` names
  its tokens and how an unattended agent loads one;
- `docs/`: the site's own pages, each a Leaf source, so changing what the site
  says is a page edit;
- `TODO.md`: the ordered priority list;
- `notes/`: research and plans for unresolved work. Once a design lands, its
  contract moves beside the code or into the reference whose reader acts on it,
  and the note is deleted.

Read the scoped instructions for the area being changed:
`skills/leaf/assets/AGENTS.md` (browser runtime, widgets, registry, theme),
`skills/leaf/scripts/AGENTS.md` (Python owners and protocol references),
`examples/AGENTS.md` (pages and corpus), `tests/AGENTS.md` (setup and evidence),
and `scripts/AGENTS.md` (tooling and generated outputs).

For any work whose subject is Leaf itself, load `/developing-leaf`, including
research and prototypes that change no tracked code. The shipped `/leaf` skill is
for agents that use Leaf or extend its package interface.

### Where guidance lives

The sections above **Repository map** are the maintainer's direction; change them
only when the user asks. An `AGENTS.md` holds what an agent needs before changing
its area: goals, invariants that span modules, who owns what, and the gates to
run. A contract one module owns goes in that module's header, a helper's in its
docstring, and how a rule was found in the commit message. A workflow for one
kind of task goes in `/developing-leaf`.

### The install runs this tree

An install is the tracked tree copied into a host's plugin cache, and nothing is
built at install time: `bin/leaf` is `uv run --no-dev` on the tree, so the
install must be writable, and Leaf writes nothing else there. Point Codex
at the git source, since a local-directory marketplace copies a checkout's
`.venv` too. A plugin update may replace the directory wholesale, so what has to
survive one belongs in the page directory or the state home. Runtime
dependencies, and those a package script declares, state a floor and no cap. The
host supplies Chrome and `jq`; leaf never downloads a browser.

Files under `skills/leaf/assets/vendor/`, each package's `vendor/`, and
`skills/leaf/mcp-app/` are generated and committed where their consumer reads
them; `scripts/AGENTS.md` names the script that regenerates each.

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

- Give every action a keyboard route, without spending a page-level binding on
  each one.
- Follow `examples/AGENTS.md` when adding or changing a feature, and regenerate
  the derived corpus.
- If the feature changes what an agent can do or how it should do it, update
  `skills/leaf/SKILL.md` or the one routed reference that owns the workflow;
  other references point at that section by name. Shipped guidance sets goals
  for the user's experience and names the surface they read on; it leaves
  format and phrasing to the agent. Score the change with `evals/` before and
  after, and add a case for the behavior it targets (`evals/README.md`).

`uv run pytest tests` and `npm run test:runtime` are the everyday gate
(`tests/AGENTS.md`). Two TypeScript trees and the JavaScript lock have gates the
suite and pre-commit do not reach. A pull request runs them; a direct `wt merge`
does not, so run the one a change touches before landing it that way:

```sh
# scripts/browser/
npm ci
npm run check:browser && npm run test:browser

# worker/src/
npm ci --prefix worker
npm run typecheck --prefix worker
npm test --prefix worker

# package.json or package-lock.json: rebuild every bundle and commit the result
npm ci && npm run build:browser && uv run scripts/vendor.py
```

For a change that can alter browser startup, compare base and candidate at the
boundary it affects: served previews for a runtime change,
`scripts/verify-site-local.sh` for site delivery, Worker routing, or containers.
Read the comparison as a phase profile: document receipt, widget upgrade,
authoritative presentation, and the requests and bytes loaded by presentation.
Compare requests and bytes directly; elapsed time is diagnostic. A change that
adds work before presentation states the user-visible benefit and why it cannot
wait. Bytes outside that profile, such as a lazily loaded module, a vendored file,
or the install's size, are not a reason for a change on their own.

Land through a pull request or with `wt merge`, which squash-merges to `main`.
`/developing-leaf` covers landing with a red gate; Tend sessions follow
**Landing** in `.claude/skills/running-tend/SKILL.md`.
