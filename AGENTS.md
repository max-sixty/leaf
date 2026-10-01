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
- **Trust.** An action records its meaning when taken, so a control does what
  it says and the record shows what the user decided.
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

`.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` both name
`./` as the plugin payload, so Claude Code and Codex install the tracked tree whole.
Before changing an area, read the `AGENTS.md` its entry names.

- `bin/leaf`, `pyproject.toml`, and `uv.lock`: the launcher and its uv project;
- `skills/leaf/scripts/leaf/`: the CLI, server, event model, validation,
  projection, vendoring, and export (`skills/leaf/scripts/AGENTS.md`);
- `skills/leaf/assets/`: the browser runtime, registry, theme, and icon
  (`skills/leaf/assets/AGENTS.md`, and `skills/leaf/assets/runtime/keyboard/AGENTS.md`
  for commands, bindings, and scopes);
- `skills/leaf/packages/`: the bundled packages (`skills/leaf/packages/AGENTS.md`);
- `skills/leaf/references/`: contracts for page authors, package authors, and hosts;
- `.claude/skills/developing-leaf/`: the maintainer workflow and vocabulary;
- `hooks/hooks.json`: the host hooks;
- `evals/`: cases a headless agent answers, scoring the shipped guidance;
- `examples/`: the pages the site publishes, which are also the render corpus
  (`examples/AGENTS.md`);
- `tests/`: the suite, with the runtime's folds under `tests/runtime/`, which Node
  runs without a browser (`tests/AGENTS.md`);
- `build/`: the browser framework's TypeScript and the builds of every committed
  browser bundle (`build/AGENTS.md`);
- `dev/`: the `leaf_dev` package and its `leaf-dev` commands (`dev/AGENTS.md`);
- `worker/`: the Cloudflare Worker behind <https://leaf.page/>, which routes each
  example to the Python server (`leaf_website`) in a per-user container
  (`worker/README.md`);
- `docs/`: the site's own pages, each a Leaf source;
- `TODO.md`: the ordered priority list;
- `notes/`: research and plans for unresolved work. When a design lands, its
  contract moves beside the code or into a reference, and the note is deleted.

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

A host copies the tracked tree into its plugin cache and builds nothing. `bin/leaf`
runs `uv run --no-dev` on the tree, so the install must be writable; Leaf writes
nothing else there. Point Codex at the git source, since a local-directory
marketplace also copies a checkout's `.venv`. A plugin update may replace the
directory wholesale, so state that must survive one belongs in the page directory or
the state home. Runtime dependencies, and those a package script declares, state a
floor and no cap. The host supplies Chrome and `jq`; Leaf never downloads a browser.

Files under `skills/leaf/assets/vendor/` and each package's `vendor/` are generated
and committed where their consumer reads them (`build/AGENTS.md`).

Every tracked byte ships in every install and stays in history, so the suite refuses
a binary file and pre-commit refuses a new file over 500 KB. An image a tool here
reads lives in `max-sixty/leaf-assets` at the path its reader looks for it, pinned by
`leaf-assets.json` (`dev/leaf_dev/leaf_assets.py`). Evidence, such as screenshots,
probe captures, recordings, and raw run output, stays in `.tmp/` and reaches the
user on a Leaf page; a note keeps the finding and the command that reproduces it.

## Cross-runtime invariants

### The document starts state; the log changes it

Authored markup is a page's initial state, and the append-only event log records
every change to it. Every current-state projection starts from the markup and
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
ledger of unresolved local work into current state; browser components read
selections from it. Presentation proof is separate: it records whether the required
renderers have committed the document's current semantic epoch. Renderer nodes,
promises, and DOM attributes never enter the semantic snapshot.

A publication also starts each renderer, which claims its region during the
synchronous publication and paints on the following pass. A caller that changes what
the page shows publishes and waits for proof; it neither names nor sequences
renderers. Where one renderer reads DOM another builds, that order is declared once,
beside the coordinator.

Focus, scroll, selection, disclosure, draft text, drag, and layout stay with their
browser owners until a gesture becomes a declared application fact, and repainting
them creates no semantic epoch. Neither the log nor any projection carries this
state, so it lives only as long as the node holding it: whatever replaces a node
carries the state across, under the identity the replacement already keys on, or
the user loses it.

Python derives page-wide `activity` and per-input `workflows` from the agent's
declaration and the evidence beside it (`skills/leaf/scripts/leaf/session-lifetime.md`).
The banner and neighboring-page rows show `activity`; messages, margin entries, and
thread attention read `workflows`, and thread attention also holds outstanding user
Asks. Page activity never implies work on every message. JavaScript adds its unresolved
local sends through the publisher and may schedule a read at `next_transition_at`; it
never ages or reclassifies workflow evidence.

A page's directory holds its whole durable record and is the unit Leaf deploys
(`skills/leaf/scripts/leaf/page-storage.md`).

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
  each, and a route a finger can take (`skills/leaf/assets/runtime/keyboard/AGENTS.md`,
  "Touch routes").
- Add or update its pages as `examples/AGENTS.md` describes, and regenerate the
  corpus.
- If it changes what an agent can do or how, update `skills/leaf/SKILL.md` or the
  one routed reference that owns the workflow; other references point at that
  section by name. Shipped guidance sets goals for the user's experience and names
  the surface they read on, and leaves format and phrasing to the agent. Score the
  change with `evals/` before and after (`/developing-leaf`, "Score a guidance
  change").

`uv run pytest tests` and `npm run test:runtime` are the everyday gate
(`tests/AGENTS.md`). The TypeScript in `worker/src/` and `build/browser/`, and the
JavaScript lock every committed bundle is built from, have gates neither the suite
nor pre-commit reaches. Both landing paths run them all: a pull request in its
`test` job, and `wt merge` in the pre-merge blocks of `.config/wt.toml`.
`wt hook pre-merge` runs that local gate without landing, on a committed tree, since
the bundle check fails on any uncommitted change. The site build, the Worker's
dry-run deploy, and `leaf-dev verify-site wrangler` run on a pull request and in
`publish-site` before it deploys, not in `wt merge`.

For a change that can alter browser startup, compare base and candidate at the
boundary it affects: served previews for a runtime change, and
`leaf-dev verify-site wrangler` for site delivery, Worker routing, or containers.
Read the comparison by phase: document receipt, widget upgrade, and authoritative
presentation. Compare the requests and bytes loaded before presentation directly;
elapsed time is diagnostic. A change that adds work before presentation states the
user-visible benefit and why it cannot wait. Bytes off that path, such as a lazily
loaded module, a vendored file, or the install's size, are not on their own a reason
for a change.

Land through a pull request or with `wt merge`, which squash-merges to `main`.
`/developing-leaf` covers landing with a red gate; Tend sessions follow
**Landing** in `.claude/skills/running-tend/SKILL.md`.
