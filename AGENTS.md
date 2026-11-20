# leaf

@skills/leaf/SOUL.md

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

A reasonable choice is the agent's to make. Leaf helps it choose well and
reflects back what a choice does, and refuses only input that would break a
guarantee whatever the agent meant. Where a choice harms the user only in some
cases, as an edit that relabels an option the user already picked does, Leaf
accepts it and tells the agent what it did, rather than refusing every choice
of that kind to stop the worst one. Leaf's code doesn't make such a choice in the
agent's place either, even where a fork of the agent acts for it, as in writing a
thread's summary. It offers evidence, such as the range it suggests folding, the
instructions state the goal, and the agent or fork judges the case, since a
cutoff on a measure misjudges the cases near it.

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

These times hold on a large page too. A page's size is how much it holds:
elements, widgets, headings, obligations, threads, events and revisions. An
input's work depends on what it changes and on what the window shows, not on how
much the page holds. A keystroke, a wheel step or a hover costs the same on a page
of ten sections as of five hundred. So work that a pass would redo for the whole
page, such as a layout, a scan of the page's controls or a derivation of every
record, runs only for the change that makes it necessary, which its owner records
when the change happens. Neither an input's work in the browser nor the bytes it
moves grows with how long the session has run. Loading a page, and computing or
applying a reading of it, grow no faster than the page times the logarithm of its
size. The server admits each event against such a reading, so its work per event
may grow with the events the log holds. On the largest page `leaf-dev bench`
generates, a keystroke and a wheel step each fit in 8 ms of main-thread time, and a
click shows the server's reading within 100 ms. A step that walks one of those
collections for each member of another, as finding each obligation's heading by
reading every heading did, grows with the square of the page. So does a style or
layout pass forced once per element, since each pass can cover the whole page
(`browser/AGENTS.md`, "Runtime ownership"). `leaf-dev bench` measures how each
cost grows with the page.

## Pages across Leaf updates

A page records its authored content, its log and the packages it selects. The Leaf
that serves, checks or exports it supplies everything else: the runtime and the
state the server sends it, the layer (registry, theme, widgets and package
modules) it composes from the page's selection, and how it parses and draws what
the page keeps. So only the event log and the records Leaf keeps outside a page
cross between Leaf versions.

- **The page protocol**, the kernel registry's `$events.protocol`, is Leaf's only
  version: a Leaf serves and writes only pages at its own number. The build refuses
  any change to a logged event's schema until the number moves. Bump it also where a
  Leaf at the current number would misread an event or record that another Leaf at
  that number wrote, such as a logged value given a new meaning. A change to what the
  serving Leaf supplies keeps the number, even where a logged message or a comment's
  quote then draws or resolves differently. Bumps are rare, perhaps one in five
  hundred commits, and once Leaf is released only a bump may break an existing page.
  `layer-registry.md`, "Page protocol", says how the number is enforced and how
  records carry it.
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
Read an area's `AGENTS.md` before changing or reviewing it.

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
  module `claude-code.ts` with the contracts it declares to Claude Code
  (`leaf-state.d.ts`), such as the values it keeps in `$.state`, and the Pi
  extension `pi.ts`.
- `evals/`: cases a headless agent answers, scoring the shipped instructions, and
  experiments with their own Promptfoo configs (`dev/AGENTS.md`, "Experiments").
- `examples/`: the pages the site publishes, also the render corpus
  (`examples/AGENTS.md`).
- `tests/`: the suite, with the runtime's Node tests under `tests/runtime/`
  (`tests/AGENTS.md`).
- `build/`: the build of every generated browser file (`build/AGENTS.md`). A
  `vendor/` directory, such as `browser/vendor/`, holds generated browser
  modules, not only third-party code.
- `dev/`: the `leaf-dev` developer commands
  (`dev/AGENTS.md`).
- `worker/`: the Cloudflare Worker and containers behind <https://leaf.page/>
  (`worker/README.md`).
- `docs/`: the site's own pages, each a Leaf source. A figure they give about Leaf,
  such as a wait, a cost or a rate, is one a reader can reproduce from the tree,
  with a `leaf-dev` command or from checked-in data. A measurement of
  sessions on one machine stays in `notes/`, even where it motivates a design the
  page describes.
- `notes/`: what the code doesn't hold yet: research, and plans for large work in
  progress or a design not yet built. Work built on a branch keeps its contract in
  its code, and a page that shows it to the user is a preview of a file in `.tmp/`.
  When a design lands, its contract moves beside the code or into a reference and
  the note is deleted. `notes/TODO.md` holds the biggest current challenges, and
  how to query the backlog, the GitHub issues labelled `backlog`.
- `.config/`: tool configuration that needn't sit at the root, such as Worktrunk's
  `wt.toml`, the knip and dependency-cruiser configs their pre-commit hooks name,
  and the asset pin `leaf-assets.json`. GitHub lists every root entry above the
  README, so a file stays at the root only where a harness, tool or editor looks for
  it there.

Load `/developing-leaf` for any work whose subject is Leaf itself, including
research and prototypes that change no tracked code. The shipped `/leaf` skill is
for agents that use Leaf or extend its package interface.

### Where instructions live

The sections above **Repository map**, and the `SOUL.md` they import, are the
maintainer's direction; change them only when the user asks.

Place an instruction by who must act on it and what missing it costs. Every
session in the repository reads this file, subagents and Tend's runs included, and
one that changes or reviews an area reads that area's `AGENTS.md`; a skill reaches
only the sessions that load it, and subagents and Tend's runs often don't. So an
`AGENTS.md` holds what a change could break by missing: goals, invariants that span
modules, who owns what, the criteria a change or review is judged by, and the gates
to run, stated as goals rather than steps. How to do one kind of task, such as
previewing a page, proving a visible change or landing, goes in a project skill such
as `/developing-leaf`, not in the shipped `/leaf` skill, since missing it makes the
task slower or worse but breaks nothing; a procedure for a rarer task goes in that
skill's `references/`, behind a pointer that names the task. `running-tend` holds
only what Tend's jobs alone do.

A contract one module owns goes in that module's header, a helper's in its
docstring. A contract several modules share goes in the protocol reference for that
boundary, which says what each side relies on, not how one side provides it. A
header also states the product decisions its module embodies, each with its reason,
whether the user made it, and any alternative a later change might reach for, with
why that alternative fails. A change that reverses a decision rewrites its statement
and says so in its commit.

Text in the tree, comments, tests and eval cases included, says what holds now
rather than how it came to be. The date of a decision or change, the request or
incident behind it, the measurements that settled it and the versions before it go
in the commit message, where `git log -L` finds them.

Don't copy into prose a list the code already keeps, such as the bundles in
`vendor.mjs`; point to it, so a new member needs no edit. Where the prose must
list them, a test holds the list to the code's copy (`tests/AGENTS.md`, "Put
each assertion at the boundary that owns it").

Shipped text (the references, `--help`, UI strings, `SKILL.md`) and agent
instructions (the `AGENTS.md` files and project skills) reach a reader who has only
that text and the files it points to, never the session or the diff that wrote it. In
such text, a review reports these defects, which Leaf calls public surface traps:

- text written for a reader other than the one the text addresses, such as an
  explanation of a mechanism that reader doesn't need. In maintainer guidance, that
  includes a sentence about how the diff's code works: the module header holds it, and
  the guidance says what other code must rely on;
- a second copy of a rule another text owns;
- a sentence its reader can parse only on a second read, as with a coined term used
  without its definition, a pronoun whose antecedent sits in another clause or only in
  the diff, or a rule joined in one sentence to its mechanism and its exceptions;
- a sentence about how a rule came to be.

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
exporting need no browser build or npm. Pages run the browser runtime's source
modules from the serving install, so a runtime change takes no build, but for one to
the floating panel's row, whose first-paint copy the build draws (`build/AGENTS.md`).
Only a prepared installation, such as the website's container, compiles them into a
kernel (`build/runtime-bundle.mjs`, `leaf.runtime_selection.read_runtime`).
`bin/leaf` is `uv run --no-dev` on the tree, so the install must be writable,
and Leaf writes nothing else there. A plugin update may replace the directory,
so anything that must survive one belongs in the page directory or the state
home.

Runtime dependencies,
including a bundled package script's, state a minimum version and no maximum. The
host supplies Chrome and `jq`; Leaf never downloads a browser.

Every tracked byte ships in every install and stays in history, so the tree holds
no binary or large files except the generated `vendor/` bundles. An image a tool here reads lives in
`max-sixty/leaf-assets`, pinned by
`.config/leaf-assets.json`. Publish there as part of the change that needs it, with no
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
state of each On Me obligation and thread, and the user's updates, and serves that to the
browser.

In the browser, only `applicationState` (`runtime/semantic-state.js`) combines the
authored initial values, the server's latest reading and the tab's unresolved
gestures into current state. It publishes each state as one immutable value that
components read through selectors and never write, holding no renderer nodes,
promises or DOM attributes. Widgets draw the complete state, unset and undecided
values included, and undo never rebuilds widgets or replays authored actions
into the DOM. A page widget's state is bounded by
the document version; a widget in a thread message is bounded by its thread's
window.

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
thread the user opens, the user's own reply and its wait for an answer, and the
resend a refused send leaves. A refusal restores the
server's state.

Focus, scroll, selection, open disclosures, a drag and layout stay with the
browser until a gesture makes them part of the page's state. The log doesn't
record them, so they live only as long as their DOM node: code that replaces a
node carries that state to the new node, matched by the key the replacement
already uses. A draft being typed stays out of the log too, until Send, but
outlives its node: the page's server keeps it for every tab and device
(`src/leaf/drafts.py`), and the agent never reads it.

Python decides where the agent's work stands: `activity.py` for the whole page,
read by the Leaf panel, and `workflows.py` for each update
the user handed over, read by messages, thread attention, margin entries and the
Stop hook; thread attention also reads the user's outstanding obligations. A busy page
doesn't mean every message is being worked on. The browser adds its own unsent
gestures but never ages or reclassifies a workflow. Other pages read a page's
activity only from the row `server_rows.py` writes and whether its server is
alive, and only into their list of other pages (`/api/pages`), which no page's
own state or reading takes.

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

Each fact Leaf derives about the page is derived once, and each place that
reports the page selects what its purpose needs. Whatever a delivery tells the
agent about an event, apart from what it asks of the agent at the time (`answer`,
`handling`, `waiting`, `settled`), `leaf page state` tells a later session about the
same event, or the message as it now reads, under the same name and from the same code
(`event_facts.py`). A fact about the past, such as the settings the user had open
when they wrote, is derived from the log and never stored as a second copy.

### Read what the page states

Leaf takes each fact about a page from where the page states it: the structure HTML
defines, including the relations it gives its own elements, or a declaration in an
author's attribute, a registry entry or the event log. A declaration on a plain
element uses a standard attribute that means the same to every reader; one on Leaf's
own element uses Leaf's attribute, such as `label`, since no standard defines that
element. Leaf takes no fact from how content looks or what it says, and reads words
only to quote, anchor and show them, so restyling a page changes no fact Leaf holds
and rewording it changes only its words. Any other reading of markup is an exception
the maintainer agrees to.

### Keep the layer open

A content widget is one a package ships, unlike Leaf's own elements in
`browser/registry.json`, such as `lf-suggestion`, which core code may name. Leaf's
runtime, server and stylesheets never branch on a content widget's tag name or keep a
list of content widgets' tag names. They read each tag's facts, such as `verbs` or
`reading-role`, from its element declaration in the registry. A package's modules may
name the widgets they compose, and a test or a `leaf-dev` command the widgets it
exercises; a test that covers every widget with some property finds them in the
registry. So a new content widget needs only files in its own package: its element
declaration, its module and its styles. The registry's `$` keys hold facts
about the layer as a whole, such as the event kinds in `$events`. Each tag's element
declaration is that tag's complete schema.

Leaf's shipped instructions don't depend on a widget's name either. Where a shipped
instruction tells an author what to use, it names the form the author needs, such as a
before-and-after pair, a chart or a choice. Where a behavior depends on a declared
fact, such as `awaits` or `reading-role`, it names that fact. It names a package's
widget only as an example of a form or of a declared fact, or inside a markup example. The page's vocabulary
(`leaf page vocabulary <page>`) tells the author which widget provides each form, and
`packages.md`, "A widget", says where a widget's own guidance goes. So an author finds
a widget the same way whether Leaf bundles it or another package the page selects
provides it, whatever the widget is called.

### Wait for the event that ends the work

Code waits for a response, a process's exit, a lease's release or a socket's
close, so a slow machine only makes the wait longer. A deadline stands only
where an outside party imposes one, such as a harness's hook timeout or a peer
that can hang without closing, or to cap a cost. It is that party's whole
budget, which every step under it shares, and it sits at least ten times above
the work on a loaded machine. Where a slower path exists, expiry takes it rather
than failing.

## Weigh what a change adds

Whoever writes or reviews a change asks whether what it adds is worth what later
changes and users pay for it, by the bar "Regular maintenance" sets for code already
there. Size says little: a two-line selector can reach every page.

- **What it adds**: a mode, branch or special case; one more member of a set,
  allowlist or tolerance; a wait, retry or timer; a public option; room reserved for a
  state that may not come; a reliance on a dependency's internals.
- **What it repeats**: code the change writes may already exist under another name, in
  another directory, language or package. Search for the question each new helper,
  constant, selector, style rule or inline check answers, not for its name. A copy is a
  second home even when a comment names its source. Where the change couldn't reach
  the owner, export, move or generate the owner rather than copy it.
- **What it puts between the author and HTML**: be hesitant to add anything there,
  such as a tag, class, attribute or key for what an HTML element, attribute or CSS
  property already says, a rule that reads meaning out of the author's markup ("Read
  what the page states"), or a pass that rewrites it. Authors and agents already write HTML well, and each such
  layer is one more thing every author learns and every later change keeps working.
  Add one only for what HTML can't say.
- **What it buys**: a behavior a user sees, a request the maintainer made, or a
  measured cost. A green test buys what the test protects, so name that.
- **Where its cost lands**: read the change's reach rather than its claim, such as a
  selector's or guard's scope against the condition it names, what else inherits from
  or sits in the box it changes, and how often a guard fires on a correct setup. Then
  compare who pays with who gains: a cost paid in every state or on every page to fix
  one transition usually outweighs it.
- **The cheaper change**: a platform or dependency primitive, the fix in the owner
  rather than a caller, the stale copy deleted, or the gap left open with an issue.
  When `git log -L` shows earlier changes compensating for the same gap, ask whether
  the mechanism is the wrong primitive and the cheaper change its general form.

Keep an addition whose benefit is concrete when no cheaper change buys it, as with a
fix in a primitive every caller gains from; otherwise make the cheaper change, or ask
for it in review. When the fix for a finding would add another branch, flag or
condition, first ask whether the finding is about the approach.

## Regular maintenance

Whenever a survey, a review or the nightly sweep reads a file, look for code that
makes Leaf harder to develop than it is worth:

- **A mechanism users wouldn't miss.** Ask who would notice it gone and what it costs
  the changes around it. Code woven into the core runtime, the server or a shared
  contract costs every nearby change, so it must clear a much higher bar. Signs it
  doesn't: a hold, carry or special case for one widget or gesture spread across
  several owners; a public API whose only callers are tests or a single example; a
  mechanism `git log --follow` shows patched again and again (without `--follow`, a file's
  history stops at its last move). Code in its own module, such as a
  package, a widget or a `leaf-dev` command, costs little beyond its own files; remove
  it only when it is large and unused. Keep anything users would notice losing,
  including Leaf's interface guarantees. Taking a feature away is the maintainer's
  call, so propose the removal with what users lose and what it deletes, measured
  as `/developing-leaf`'s "Measure a removal" says.
- **Several implementations of one capability.** Consolidate them into one home and
  move every caller to it ("Fix the underlying issue"). The other copies seldom sit
  beside the file you're reading, so search for them as **What it repeats** says.
- **A mechanism a dependency or the platform already provides.** Delegate it ("Use
  dependencies").

## Working on the repository

When the user is to choose among designs, show the candidates side by side and
let them select one (`/developing-leaf`, "Explore an open design"). A choice about
how something looks or moves can't be judged from a description, so every UI option
you leave to the user carries a picture of its result: a still pair, a sketch, a
diagram or a live sample. That includes the calls a PR body leaves to the user, and
the decisions a page relays from it.

Before writing words the user sees, such as a label, status line or placeholder, or
naming anything they operate or an identifier for one, read
`.claude/skills/developing-leaf/references/glossary.md`, Leaf's canonical vocabulary
and guidance for visible text. A control may need no words at all
(`browser/AGENTS.md`, "Controls are few and quiet"). Before changing anything Leaf
draws, read "Leaf's interface" in `browser/AGENTS.md`.

The user judges a UI change by using it and by looking at it, so whoever hands one
over or reviews it does both (`/developing-leaf`, "Review a UI change"), with a
`/ui-sweep` pass for a theme or shared-control change.

Before finishing a feature:

- Give every result a pointer reaches a keyboard route and a touch route
  (`browser/runtime/keyboard/AGENTS.md`, "Touch routes"), without a page-level binding
  for each. The route is owed to the result, not each gesture: ask what a user
  could no longer see, reach or decide without the gesture. Dragging a thread
  card aside needs no route, since Escape also uncovers the passage beneath it.
- Follow `examples/AGENTS.md`; corpus consumers generate their fixture on demand.
- If the feature changes what an agent can do or how, update
  `skills/leaf/SKILL.md` or the one reference that owns the workflow, and point
  other references at that section. Shipped instructions set goals for the user's
  experience and name the surface they read on, leaving format and phrasing to
  the agent.

Score any change to agent instructions that an agent could read more than one way,
such as a new or reworded rule, a goal that competes with another or a cut that may
have carried a behavior, before and after (`/developing-leaf`, "Score an instruction
change"). Deleting a description of an input that can no longer arrive, or correcting
a fact, needs no score.

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
Worker's dry-run deploy, `leaf-dev site verify website-worker`) run on a pull
request and in `publish-site`, but not in `wt merge`.

A change to how a harness runs Leaf, such as its hooks or sandbox, runs the agent
journey on that harness (`/developing-leaf`, "Run the agent journey").

Compare base and head for a change that can alter browser startup
(`/developing-leaf`, "Compare checkout versions"). A change that adds work before the
page first shows the server's state says what the user gains and why it can't wait.
Bytes off that path, such as a lazy module, a vendored file or the install's size,
are not alone a reason for a change.

Land through a GitHub pull request, which squash-merges to `main`; use `wt merge`
only when the user asks for it. For now, a failing check the change doesn't cause blocks nothing (`tests/AGENTS.md`,
"Run what the change needs"). Tend sessions follow **Landing** in
`.claude/skills/running-tend/SKILL.md`.
