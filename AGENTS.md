# leaf

@SOUL.md

## Leaf's role

Core owns shared state, event, and lifecycle guarantees; packages own domain
behavior and widget presentation. Judge simplifications by the mechanisms they
remove and the package compositions they preserve or rule out, rather than by
use in bundled widgets alone.

An agent that writes a page, sets its data or changes Leaf works in a fast loop:
it reads what failed and tries again. So Leaf lets a failure surface through the
parser or check already in the agent's path. It adds code to prevent a failure
only where nothing in the agent's path would report it, so it would pass
silently into something the user relies on, such as an admitted event or a
stored decision. Every check, option and special case costs every later
maintainer, so remove one that buys nothing the agent's next attempt would not.

## Stage

Leaf has no users, deployment, database or persisted state that constrains new
code. Prefer the simpler interface even when it is incompatible, and spend no
code or test complexity on compatibility with earlier runtimes. Claims, logs and
pages from earlier runtimes, and old records in the state home every worktree
and session on the machine shares, are disposable: regenerate or delete them.
Add no migration, compatibility shim, old-record validator, fallback read or
removal promise, and leave old state and recovery instructions out of the
handoff.

Tests should protect behavior a user depends on. Rewriting or deleting one is
ordinary: check which behavior its assertion protects, change it where that
makes a better app, and say in the commit which behavior changed.

Written contracts describe the current code and promise no compatibility. Every
consumer of them is in this tree, so when a different contract makes the code
simpler, change it and every consumer together, prose included. A change that
keeps every guarantee changes no contract prose.

A restriction Leaf imposes, such as a content security policy, a validator's
refusal, an import allowlist or a markup limit, doesn't decide whether a feature
is allowed. When one blocks a feature, don't drop the feature or quietly work
around it: tell the user what the restriction blocks, what it protects and what
lifting it would cost. It may guard something the user values, or be a side
effect nobody chose, so only the user can weigh the feature against it.

Coherent new features can be tried before every product detail is settled, as
long as any architectural problem they leave stays easy to fix. Make
improvements that follow from the repository, and ask the user only when the
choice depends on purpose or intent the code can't supply.

## Responsiveness

When the user acts, the page draws what that act decides by itself before the
browser's next frame, in the task that handles it: the user's message in its
thread, a widget's new state, a thread they resolved. Facts that depend on the
rest of the log, such as whose turn a thread is and which obligations the user owes,
arrive with the server's reading of the gesture, which should be on screen within
100 ms since the server usually runs on the user's machine. The browser doesn't
predict that reading: a prediction is a second copy of the server's rules, and
each case it misses shows the wrong state until the reading arrives. Where the
reading takes longer than 100 ms, make that path faster.

## Pages across Leaf updates

A page records its authored content, its log and the packages it selects. The Leaf
that serves, checks or exports it supplies everything else: the runtime, and the
layer (registry, theme, widgets and package modules) it composes from the page's
selection. So what changes with Leaf ships together, and what crosses the gap
between Leaf versions is only what a page keeps: its event log and the records kept
outside it.

- **A protocol bump** changes the kernel registry's `$events.protocol`, and every
  page at another number is refused until the session holding it takes it to the
  new number, which it does itself on its first command or hook naming the page.
  Bump it only for a change a Leaf at the same number would misread in the log or
  in a record kept outside a page. A change to the runtime, the served state, the
  bundled widgets and their registry entries, the theme or the public package API
  (`widget-api.js` and its portable part `portable-api.js`) never bumps it. It is
  Leaf's only version, so a record kept outside a page, such as a browser draft,
  carries the protocol at which its own shape last changed (`layer-registry.md`,
  "Page protocol", owns the rules). Bumps are rare, perhaps one in five hundred
  commits. Once Leaf is released, only a bump may break an existing page.
- **A page's own code**, its widgets and scripts, and an installed package's
  modules call the public package API across Leaf versions. While Leaf is in alpha
  an update may change that API without a bump, since a bump would not repair code
  Leaf doesn't compose; `page check --render` and `package check --render` report a
  module it breaks, and the agent fixes it as any other check failure.

## Fix the underlying issue

When packages or runtimes share a concept, one owner defines its meaning in a
contract that covers each use. Keep one canonical API per capability. Consumers
select and transform the data it returns themselves; a shared implementation is
no reason to expose those as new APIs. Add a separate API only for a capability
or guarantee that composing the existing one can't provide, and extend the
canonical API when its own responsibility is incomplete.

Every change and review asks whether the immediate problem is a symptom of a
deeper one, such as a missing primitive, a misplaced boundary or an unstated rule
several packages share. Trace the cause up through the layers that produced it
and fix the highest one that is wrong, just below the first one that is correct
as designed. If the change can't make that fix, its author or reviewer names and
proposes it. A passing test for the reported case proves only that case. A
second special case, a caller repeating its callee's rule, a guard enforcing a
rule the code never states, or a flag passed down a stack to reach one use
suggests the shared boundary is still unsettled.

Don't add another patch on top of existing ones. A change that fixes the symptom
and leaves the code harder to maintain doesn't go in, even with the real fix
filed behind it, because the next change has to undo the patch first. Defer an
underlying fix only when the change leaves it as easy to make as before.

## Repository map

The repository is the plugin: `.claude-plugin/marketplace.json` and
`.agents/plugins/marketplace.json` name `./` as the payload, and
`package.json`'s `pi` key makes it a Pi package. The payload is the whole
repository, whether a harness copies it into a cache or loads it in place.
Read an area's `AGENTS.md` before changing it.

The **plugin root** is the installation and execution boundary: manifests register
harness components there, and `bin/leaf` runs its uv project. The **skill root**,
`skills/leaf/`, is the agent's instruction entry point, with `SKILL.md` and its
references; copied alone, it is not an installation. `pyproject.toml` owns
Python's module location, `leaf.state` locates the plugin root, and
`leaf.schema` derives the resource paths. Page initialization composes the core
browser assets and the packages into a page's layer.

- `README.md`: the product and its installation.
- `bin/leaf`, `pyproject.toml`, `uv.lock`: the launcher and its uv project.
- `src/leaf/`: the CLI, server and event model (`src/AGENTS.md`).
- `browser/`: the browser runtime, registry and theme, with the type check's
  configuration and declarations under `browser/types/`
  (`browser/AGENTS.md`; `browser/runtime/keyboard/AGENTS.md`
  for commands, bindings and scopes).
- `packages/`: the bundled packages (`packages/AGENTS.md`).
- `skills/leaf/references/`: contracts for page authors, package authors and harnesses.
- `.claude/skills/developing-leaf/`: the maintainer workflow and vocabulary.
- `hooks/`: each harness's registration of `leaf hook` (`hooks.json` for Claude
  Code, `codex.json` for Codex), the scripts they run, Claude Code's hooks
  module `claude-code.ts`, and the Pi extension `pi.ts`.
- `evals/`: cases a headless agent answers, scoring the shipped instructions.
- `examples/`: the pages the site publishes, also the render corpus
  (`examples/AGENTS.md`).
- `tests/`: the suite, with the runtime's Node tests under `tests/runtime/`
  (`tests/AGENTS.md`).
- `build/`: the build of every generated browser file (`build/AGENTS.md`). A
  `vendor/` directory, such as `browser/vendor/`, holds generated browser
  modules, not only third-party code.
- `dist/kernel/`: the compiled core runtime pages run, generated and
  committed; it is a delivery form of the runtime, not a skill or an
  installation root.
- `dev/`: the `leaf-dev` developer commands
  (`dev/AGENTS.md`).
- `worker/`: the Cloudflare Worker and containers behind <https://leaf.page/>
  (`worker/README.md`).
- `docs/`: the site's own pages, each a Leaf source.
- `TODO.md`: the biggest current challenges, and how to query the backlog, the
  GitHub issues labelled `backlog`.
- `notes/`: what the code doesn't hold yet: research, and plans for large work in
  progress or a design not yet built. Work built on a branch keeps its contract in
  its code, and a page that shows it to the user is a preview of a file in `.tmp/`.
  When a design lands, its contract moves beside the code or into a reference and
  the note is deleted.

Load `/developing-leaf` for any work whose subject is Leaf itself, including
research and prototypes that change no tracked code. The shipped `/leaf` skill is
for agents that use Leaf or extend its package interface.

### Where instructions live

The sections above **Repository map**, and the `SOUL.md` they import, are the
maintainer's direction; change them only when the user asks. An `AGENTS.md` holds what an agent needs before changing
its area: goals, invariants that span modules, who owns what, and the gates to
run. A contract one module owns goes in that module's header, a helper's in its
docstring, and how a rule was found in the commit message. A contract several modules
share goes in the protocol reference for that boundary, which says what each side
relies on, not how one side provides it. A header also records
the product decisions its module embodies and the alternatives they rejected; a
change that reverses one rewrites that record and says so in its commit. A
maintainer's workflow for one kind of task goes in a project skill such as
`/developing-leaf`, not in the shipped `/leaf` skill.

Don't copy into prose a list the code already keeps, such as the bundles in
`vendor.mjs`; point to it, so a new member needs no edit. Where the prose must
list them, a test holds the list to the code's copy (`tests/AGENTS.md`, "Put
each assertion at the boundary that owns it").

### Use dependencies

Use maintained dependencies, including the platform and standard library, for
established capabilities, in prototypes too. Leaf code owns product-specific
behavior and integration, and writes a mechanism itself only when existing ones
can't meet a concrete requirement. In the browser, use the platform's layout,
cascade and focus model first (`browser/AGENTS.md`, "The browser
answers first"). Build browser dependencies in Leaf's pipeline and ship ready
assets.

### The install runs this tree

Git-sourced consumer installs copy the tracked tree into a harness's plugin
cache and follow `main`. Claude Code's `--plugin-dir` and local-path marketplace
plugins can load in place instead; point Codex at the git source, since its
local-directory marketplace also copies a checkout's `.venv`. Nothing is built
at install time: installing, authoring pages, writing custom packages and
exporting need no browser build or npm. Pages run the browser runtime the serving
install holds: the kernel committed in `dist/kernel/` while it matches the tree's
modules, and the source modules where a merge has left it stale
(`leaf.runtime_selection.read_runtime`). `bin/leaf` is `uv run --no-dev` on the tree, so
the install must be writable, and Leaf writes nothing else there. A plugin
update may replace the directory, so anything that must survive one belongs in
the page directory or the state home.

Runtime dependencies,
including a bundled package script's, state a minimum version and no maximum. The
host supplies Chrome and `jq`; Leaf never downloads a browser.

Every tracked byte ships in every install and stays in history, so the tree holds
no binary or large files except the kernel. An image a tool here reads lives in
`max-sixty/leaf-assets`, pinned by
`leaf-assets.json`. Publish there as part of the change that needs it, with no
separate approval, since publishing moves only this checkout's pin; the
`dev/leaf_dev/leaf_assets.py` header says how to resolve a conflict over the
pins. Evidence, such as screenshots, probe captures, recordings and raw run
output, stays in `.tmp/` and reaches the user on a Leaf page; a note keeps the
finding and the command that reproduces it, not the capture.

## Cross-runtime invariants

### The document starts state; the log changes it

A page's authored markup is its initial state, and the append-only event log
records each change. Every reading of current state starts from the markup and
applies the events still in force. Add no database, current-state file,
per-widget replay list, or the DOM as the source of truth for page state.

A later version keeps each decision the user made. To withdraw one, because a
rewrite invalidated what it rests on, mark it `restated`; leaving it out
retracts nothing. An `undo` event names the gesture it withdraws; it never
deletes an event or invents a counter-event.

The registry keys each widget action and report by its widget, the unit of that
widget's state it changes, and its verb (`events.md`). From one consistent read
of the log, Python computes which action wins each key, what was withdrawn, the
state of each On me obligation and thread, and the user's updates, and serves that to the
browser.

In the browser, only `applicationState` (`runtime/semantic-state.js`) combines the
authored initial values, the server's latest reading and the tab's unresolved
gestures into current state. It publishes each state as one immutable value that
components read through selectors and never write, holding no renderer nodes,
promises or DOM attributes. Widgets draw the complete state, unset and undecided
values included, and undo never rebuilds widgets or replays authored actions
into the DOM. A page widget's state is bounded by
the document version; a widget frozen into a thread message is bounded by its
thread's window.

A renderer repaints only when something it read through a selector has changed,
or when whoever changes an input outside the state, such as a draft, calls its
`present()`. Code that changes what the page shows publishes, then awaits
`whenDocumentPresented()`; it doesn't call renderers or decide their order.
Where one renderer depends on DOM another writes, it declares that dependency
through `PRESENTATION_DOM`. DOM completion is separate from asynchronous
preparation, gesture holds and semantic presentation proof.

A gesture's own result shows in the task that sends it, before the server
answers ("Responsiveness"); a disabled control, spinner or delivery status is
not that result. The browser adds only what a gesture decides by itself: a
to-do the user ends, a thread the user opens, the user's own reply and its wait
for an answer, and the resend a refused send leaves. A refusal restores the
server's state.

Focus, scroll, selection, open disclosures, a draft being typed, a drag and
layout stay with the browser until a gesture makes them part of the page's
state. The log doesn't record them, so they live only as long as their DOM node:
code that replaces a node carries that state to the new node, matched by the key
the replacement already uses.

Python decides where the agent's work stands: `activity.py` for the whole page,
read by the Leaf panel, and `workflows.py` for each update
the user handed over, read by messages, thread attention, margin entries and the
Stop hook; thread attention also reads the user's outstanding obligations. A busy page
doesn't mean every message is being worked on. The browser adds its own unsent
gestures but never ages or reclassifies a workflow. Other pages read a page's
activity only from the row `server_rows.py` writes and whether its server is
alive.

The page directory is the durable record and the unit of deployment
(`src/leaf/page-storage.md`).

### Validate once and share readings

Validate each input once, where it enters: every event at
`event_contracts.append_admitted`, whether the browser posted it or a command
wrote it; authored markup at `page check`; message markup at `check_markup`.
Admission writes the event's declared meaning into it, so later readers use
those fields directly, without the widget. An event names what it depends on by
declared ids, never by its detail text.

A passage, the text a comment points at, is a list of `{node, start, end}`
segments that Python and the browser collapse and resolve by the same rules.
`says` is visible text; `wrote` is authored text. Python never accepts an anchor
the rendered page can't resolve. Repeated text with no context to pick one copy
detaches instead of falling back to order or offsets.

### Keep the layer open

No code outside a content widget's module names it, so a new widget family needs
only a registry entry, its module and theme rules. Everything else reads registry
declarations, never lists of tag names. Layer-wide facts live under `$` keys;
each tag's entry is its complete schema.

## Working on the repository

When the user is to choose among designs, show the candidates side by side and
let them select one (`/developing-leaf`, "Explore an open design").

Before finishing a feature:

- Give every result a pointer reaches a keyboard route and a touch route
  (`runtime/keyboard/AGENTS.md`, "Touch routes"), without a page-level binding
  for each. The route is owed to the result, not each gesture: ask what a user
  could no longer see, reach or decide without the gesture. Dragging a thread
  card aside needs no route, since Escape also uncovers the passage beneath it.
- Follow `examples/AGENTS.md`; corpus consumers generate their fixture on demand.
- If the feature changes what an agent can do or how, update
  `skills/leaf/SKILL.md` or the one reference that owns the workflow, and point
  other references at that section. Shipped instructions set goals for the user's
  experience and name the surface they read on, leaving format and phrasing to
  the agent. Where an agent could read the change more than one way, score it with
  `evals/` before and after (`/developing-leaf`, "Score an instruction change").

Several sessions share one machine, so local compute is often the bottleneck.
Before handing over, run the tests that cover what the change touches, and
`pnpm run test:runtime` when it reaches the runtime (`tests/AGENTS.md`, "Run what
the change needs"). The broad selection, `uv run pytest tests`, runs at landing,
in a pull request's `test` job and `wt merge`'s pre-merge. Don't run it by hand,
nor a whole browser test file or later tier (`--run-main`, `--run-nightly`,
`tests/browser`, `tests/journeys`), even for a change most of the suite runs
through: each takes minutes to over an hour and slows every session on the host.
Before widening your selection or its parallelism, check CPU, memory pressure and
other running suites, and on a busy host keep to focused checks.

The TypeScript in `worker/src/`, the browser runtime's type check
(`browser/types/`), and the lock every committed bundle is built from, have gates
the suite and pre-commit don't reach.
`pnpm run check` runs them, and both
landing paths run them too. The website's delivery checks (the site build, the
Worker's dry-run deploy, `leaf-dev verify-site website-worker`) run on a pull
request and in `publish-site`, but not in `wt merge`.

For a change that can alter browser startup, compare base and candidate: served
previews for a runtime change, `leaf-dev verify-site website-worker` for site
delivery, Worker routing or containers. Read the comparison by phase (the
document arriving, widgets upgrading, the page first showing the server's
state), and compare the requests and bytes loaded before that last phase
directly; elapsed time is only diagnostic. A change that adds work on that path
says what the user gains and why it can't wait. Bytes off the path, such as a
lazy module, a vendored file or the install's size, are not alone a reason for a
change.

Land through a GitHub pull request, which squash-merges to `main`; use `wt merge`
only when the user asks for it. For now, a failing check the change doesn't cause blocks nothing (`tests/AGENTS.md`,
"Run what the change needs"). Tend sessions follow **Landing** in
`.claude/skills/running-tend/SKILL.md`.
