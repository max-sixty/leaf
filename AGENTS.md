# leaf

@skills/leaf/SOUL.md

`SOUL.md`, above, holds Leaf's immovable principles: what a person using a Leaf
page and an agent writing one can count on. The sections from here to "Repository
map" are the principles Leaf is built by. Both are the maintainer's direction, and
their words change only when the maintainer asks.

Every instruction besides `SOUL.md`, in this file and in each area's `AGENTS.md`, is
guidance, and guidance is weighed against other guidance. Where a rule pulls against
another, or against a simpler design that serves `SOUL.md` as well, weigh what each
gives the user and what it costs later changes, and take the better. A change that
departs from a rule rewrites the rule, and says what a user will see differently,
with a picture where the difference shows. Weigh a case no rule covers the same way.

## Leaf's role

Core owns shared state, event, and lifecycle guarantees; packages own domain
behavior and widget presentation. Judge a simplification by the mechanisms it
removes and by the combinations of packages it keeps possible or rules out, not only
by whether the bundled widgets use what it removes.

An agent that writes a page, sets its data or changes Leaf works in a fast loop: it
reads what failed and tries again. So Leaf lets a failure surface through the parser
or check already in the agent's path. Leaf adds code to prevent a failure only where
nothing in the agent's path would report it and it would pass silently into
something the user relies on, such as an admitted event or a stored decision. Every
check, option and special case costs every later maintainer, so remove one that
gives nothing beyond what the agent's next attempt would give.

A reasonable choice is the agent's to make. Leaf helps it choose well and reflects
back what a choice does, and refuses only input that would break a guarantee
whatever the agent meant. Some choices harm the user only in some cases, as an edit
that relabels an option the user already picked can. Leaf accepts such a choice and
tells the agent what the choice did, rather than refusing every choice of that kind
to stop the worst one. Nor does Leaf's code make such a choice in the agent's place,
even where a fork of the agent acts for it, as in writing a thread's summary. The
code offers evidence, such as the range of messages it suggests folding into the
summary; the instructions state the goal; and the agent or the fork judges the case.
Code that decided by a cutoff on a measure would misjudge the cases near the cutoff.

## Stage

Leaf has no users, deployment, database or persisted state that constrains new code.
Prefer the simpler interface even when it is incompatible, and spend no code or test
complexity on compatibility with earlier runtimes. Claims, logs and pages that
earlier runtimes wrote are disposable, and so are old records in the state home,
which every worktree and session on the machine shares: regenerate or delete them.
Add no migration, compatibility shim, validator for old records, fallback read or
promise to remove any of these later, and leave old state and recovery instructions
out of the handoff.

Tests should protect behavior a user depends on. Rewriting or deleting a test is
ordinary: check which behavior its assertion protects, change the test where doing
so makes a better app, and say in the commit which behavior changed.

Written contracts describe the current code and promise no compatibility. Every
consumer of them is in this tree, so when a different contract would make the code
simpler, change the contract and every consumer together, prose included. A change
that keeps every guarantee needs no edit to contract prose, which states the
guarantees rather than how the code meets them; an edit for clarity is still
welcome.

Coherent new features can be tried before every product detail is settled, as long
as any architectural problem they leave stays easy to fix.

## The maintainer decides

Make the improvements the repository's goals and code already justify, and take a
call its guidance settles. The work doesn't wait on the maintainer for a call outside
the list below. Name the call, with the passage that settled it where one did, so
they can reverse it. Ask them only where a choice depends on a purpose or intent the
code can't tell you, or shapes what every later user, package author or change works
with:

- **What Leaf is for**, and any change to `SOUL.md` or these principles.
- **Waiving a guarantee.** A cost that breaks a guarantee `SOUL.md` states, such
  as losing the user's selection or typed words, is a defect to fix. Listing it
  as a call the maintainer may reverse doesn't make it a call. A cost to what
  guidance asks, such as a look or a rule of an area's `AGENTS.md`, is the change's
  own to weigh and take.
- **A requirement that keeps code complicated.** When a guarantee, one of these
  principles, or a choice the maintainer made expecting far less code is what
  keeps code complicated (`SOUL.md`, "Keep Leaf's code plain"), tell the
  maintainer what the requirement costs in code and what the user would see with
  less of it, and keep the requirement until they decide.
- **Taking a feature away.** "Regular maintenance" says what a proposal to remove
  one rests on.
- **Lifting a restriction.** A restriction Leaf imposes, such as a content
  security policy, a validator's refusal, an import allowlist or a markup limit,
  doesn't decide whether a feature is allowed. When one blocks a feature, don't
  drop the feature or quietly work around it: say what the restriction blocks,
  what it protects and what lifting it would cost. It may guard something the
  maintainer values, or be a side effect nobody chose.
- **An open design.** Where a visual or interaction design is still open after
  these principles, show the candidates side by side and let the maintainer
  select one (`/developing-leaf`, "Explore an open design"). Beside each
  candidate's picture, say what it costs in code, such as the mechanisms it adds,
  since a pick made on looks alone can commit Leaf to complicated code.
- **Changing core UX.** Changing how the user does a task on every page, such as
  commenting, replying or moving through the page, or adding or rebinding a
  keyboard shortcut, in Leaf's runtime or a bundled package. A user learns these
  once and relies on them everywhere, so the maintainer keeps the whole set in
  view. A smaller change within one of these tasks, such as what one press of
  Escape closes, is the change's own to weigh.
- **Growing the package interface.** Adding to the package interface, such as a
  declaration key, one of Leaf's elements, an event, a function or a new rule for
  using one. The maintainer keeps that interface small and coherent, and it sprawls
  through additions that each look reasonable alone ("Keep the package interface
  small"). `uv run leaf-dev interface --base` lists the names a change adds. A
  rename, or one more member of an existing family, such as a theme token beside
  its siblings, is the change's own to weigh.
- **Complicating the core.** Adding to the browser runtime or the server a
  mechanism that later changes there must reason about, such as a mode or state
  several modules read, a special case spread across owners, or a queue with
  ordering rules of its own. Such code costs every change near it ("Regular
  maintenance"). A fix that keeps the code's existing design, or a change that
  leaves the core simpler, is the change's own to weigh.

A change the list holds lands only once the maintainer has approved it, and a
request of theirs that named that very change approves it. Land the rest of the work
without it where the rest stands alone, as a new control can land without its
keyboard shortcut.

A choice that will come up again for each new case is better settled once.
Propose the rule that would decide every such case, with what adopting it
changes, rather than asking about the case in front of you.

## Responsiveness

When the user acts, the page draws each result that follows from the act alone, such
as the user's message in its thread, a widget's new state, whether that widget's own
question is now answered, or a thread they resolved. It draws them in the task that
handles the act, before the browser's next frame. The widget decides whether its
question is answered and its gesture carries that word to the log, where the server
reads it rather than deciding again (`awaits`), so a press that answers a question
moves it off On Me, and a deck to its next card, at once. Facts that depend on the
rest of the log, such as whose turn a thread is and whom an open obligation waits on,
arrive with the server's reading of the gesture: the page's state as the server
computes it from the whole log after admitting the gesture. A question a gesture
reopens stands as the user's until that reading says otherwise. That reading should be on
screen within 100 ms, since the server usually runs on the user's machine. The
browser doesn't predict that reading: a prediction is a second copy of the server's
rules, and each case it misses shows the wrong state until the reading arrives. Where
the reading takes longer than 100 ms, make that path faster.

These times hold on a large page too. A page's size is how much it holds: elements,
widgets, headings, obligations, threads, events and revisions. An input's work
depends on what it changes and on what the window shows, not on how much the page
holds. A keystroke, a wheel step or a hover costs the same on a page of ten sections
as of five hundred. So work that a pass would redo for the whole page, such as a
layout, a scan of the page's controls or a derivation of every record, runs only for
what changed: the code that makes each change records it as it happens, and the pass
never searches the page for changes. Neither an input's work in the browser nor the
bytes it moves grows with how long the session has run. The time to load a page, and
to compute or apply a reading of it, grows no faster than n log n in the page's size
n. The server checks each event against such a reading before admitting it to the
log, so its work per event may grow with the events the log holds. On the largest
page `leaf-dev bench` generates, a keystroke and a wheel step each fit in 12 ms of
main-thread time, and a click shows the server's reading within 100 ms. The 12 ms is
provisional, to be revisited once the architectural changes under way settle. A step that
walks one of the page's collections once for each member of another grows with the
square of the page, as finding each obligation's heading by reading every heading
did. So does a style or layout pass forced once per element, since each pass can
cover the whole page (`browser/AGENTS.md`, "Runtime ownership"). `leaf-dev bench`
measures how each cost grows with the page and reports it for a person to judge; no
test or job passes or fails on a measurement (`tests/AGENTS.md`, "Results do not
depend on execution speed").

## Pages across Leaf updates

A page records its authored content, its log and the packages it selects. The Leaf
that serves, checks or exports it supplies everything else: the runtime and the
state its server sends the page, the layer (registry, theme, widgets and package
modules) it composes from the packages the page selects, and the code that parses
and draws the page's content and log. So the event log and the records Leaf keeps
outside a page are the only data one Leaf version writes and another must read.

- **The page protocol**, the kernel registry's `$events.protocol`, is Leaf's only
  version: a Leaf serves and writes only pages at its own number. The build refuses
  any change to a logged event's schema until the number moves. Bump it also where a
  Leaf at the current number would misread an event or record that another Leaf at
  that number wrote, such as a logged value given a new meaning. A change to what
  the serving Leaf supplies keeps the number, even where the change alters how a
  logged message draws or how a comment's quote resolves. Bumps are rare, perhaps
  one in five hundred commits, and once Leaf is released only a bump may break an
  existing page. `layer-registry.md`, "Page protocol", says how the number is
  enforced and how records carry it.
- **A page's own code**, its widgets and scripts, and an installed package's modules
  call the public package API across Leaf versions. While Leaf is in alpha an update
  may change that API without a bump, since a bump would not repair code Leaf
  doesn't compose. `page check --render` and `package check --render` report a
  module an update breaks, and the agent fixes the module as it fixes any other
  check failure.

## Fix the underlying issue

When packages or runtimes share a concept, one owner defines its meaning in a
contract that covers each use. Keep one canonical API per capability. Each consumer
selects and transforms the canonical API's data in its own code, and that several
consumers would share such code is no reason to expose it as a new API. Add a
separate API only for a capability or guarantee that composing the existing one
can't provide, and extend the canonical API when its own responsibility is
incomplete.

Every change and review asks whether the immediate problem is a symptom of a deeper
one, such as a missing primitive, a misplaced boundary or an unstated rule several
packages share. Trace the cause upward from the symptom, layer by layer, until you
reach a layer that is correct as designed, and fix the layer just below it. If the
change can't make that fix, its author or reviewer names and proposes it. A passing
test for the reported case proves only that case. A second special case, a caller
repeating its callee's rule, a guard enforcing a rule the code never states, or a
flag passed down a stack to reach one use suggests that the boundary those pieces of
code share is still unsettled.

Where a simple change ends the defect, make it. A larger change that would also
save work nobody has measured as a cost adds a mechanism that no user benefits
from ("Weigh what a change adds").

Don't add another patch on top of existing ones. A change that fixes the symptom
and leaves the code harder to maintain doesn't go in, even with the real fix
filed behind it, because the next change has to undo the patch first. Defer an
underlying fix only when the change leaves it as easy to make as before.

## Use dependencies

For an established capability, use a maintained dependency, the platform or the
standard library, in prototypes too. Leaf's own code holds product-specific behavior
and the integration of its dependencies, and implements a mechanism itself only when
no existing one meets a concrete requirement. In the browser, use the platform's
layout, cascade and focus model first (`browser/AGENTS.md`, "The browser answers
first"). A control's look is such a capability: start from the design of the UI
library Leaf ships, themed through its tokens, and draw Leaf's own only where that
design fails a requirement of Leaf's, such as legibility on its palette. Build
browser dependencies in Leaf's build pipeline, and ship the built assets.

## Repository map

The whole repository is the plugin a harness installs.
`.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` name `./`
as the plugin's payload, and the `pi` key in `package.json` makes the repository a
Pi package. Read an area's `AGENTS.md` before changing or reviewing it.

The **plugin root**, the repository's top directory, is what a harness installs and
runs: the manifests there register Leaf's components with each harness, and
`bin/leaf` runs the uv project there. The **skill root**, `skills/leaf/`, holds the
agent's instructions, `SKILL.md` and its references. A copy of the skill root alone
is not an installation. `pyproject.toml` says where Python finds Leaf's modules,
`leaf.base.state` finds the plugin root, and `leaf.base.schema` derives the paths of the
resources under it. When a page is initialized, Leaf composes the core browser assets
and the page's packages into the page's layer.

- `README.md`: the product and its installation.
- `bin/leaf`, `pyproject.toml`, `uv.lock`: the launcher and its uv project.
- `src/leaf/`: the CLI, server and event model (`src/AGENTS.md`).
- `browser/`: the browser runtime, registry and theme, with the type check's
  configuration and declarations under `browser/types/`
  (`browser/AGENTS.md`; `browser/runtime/dom/keyboard/AGENTS.md`
  for commands, bindings and scopes, and for `readings/key-badges/` and `panel/page-keys/`).
- `packages/`: the bundled packages (`packages/AGENTS.md`).
- `skills/leaf/references/`: contracts for page authors, package authors and harnesses.
- `.claude/skills/developing-leaf/`: the maintainer workflow and vocabulary.
- `hooks/`: each harness's registration of `leaf hook` (`hooks.json` for Claude
  Code, `codex.json` for Codex), the scripts they run, Claude Code's hooks
  module `claude-code.ts`, and the Pi extension `pi.ts`.
- `evals/`: cases that score the shipped instructions by what a headless agent does
  with them, and experiments with their own Promptfoo configs (`dev/AGENTS.md`,
  "Experiments").
- `examples/`: the pages the site publishes, which are also the render corpus
  (`examples/AGENTS.md`).
- `tests/`: the suite, with the runtime's Node tests under `tests/runtime/`
  (`tests/AGENTS.md`).
- `build/`: the build of every generated browser file (`build/AGENTS.md`). A
  `vendor/` directory, such as `browser/vendor/`, holds generated browser modules,
  not only third-party code.
- `dev/`: the `leaf-dev` developer commands (`dev/AGENTS.md`).
- `worker/`: the Cloudflare Worker and containers behind <https://leaf.page/>
  (`worker/README.md`).
- `docs/`: the site's own pages, each a Leaf source. Each figure they give about
  Leaf, such as a wait, a cost or a rate, is one a reader can reproduce from the
  tree, with a `leaf-dev` command or from checked-in data. A measurement of sessions
  on one machine goes in `notes/` instead, even where it motivates a design the page
  describes.
- `notes/`: research, and plans for large work in progress or for a design not yet
  built. Work being built on a branch keeps its contract in its own code, not in a
  note; to show that work to the user, serve them a Leaf page whose source is a file
  in `.tmp/` (`/developing-leaf`, "Run `leaf`"). When a design lands, its contract moves beside the code or into a
  reference, and its note is deleted. `notes/TODO.md` lists the biggest current
  challenges and says how to query the backlog, which is the GitHub issues labelled
  `backlog`.
- `.config/`: tool configuration that needn't sit at the root, such as Worktrunk's
  `wt.toml`, the configs for knip and dependency-cruiser that their pre-commit hooks
  name, and the asset pin `leaf-assets.json`. GitHub lists every root entry above
  the README, so a file stays at the root only where a harness, tool or editor looks
  for it there.

Load `/developing-leaf` for any work whose subject is Leaf itself, including
research and prototypes that change no tracked code. The shipped `/leaf` skill is
for agents that use Leaf or extend its package interface.

### Where instructions live

A section of rules opens with the goal the rules serve, naming the value or
principle behind it where that isn't plain, so that a reader can weigh a case no
rule covers. A rule whose goal nobody can name is a candidate to cut once
`git log -S` shows no failure behind it.

Place an instruction by who must act on it and by what a session that misses it gets
wrong. Every session in the repository reads this file, including subagents and the
runs of Tend, the agent that reviews and maintains the repository from GitHub
Actions, so other instructions neither repeat this file's rules nor send their reader
back to them, though they may point to a detail it holds. A session that changes or
reviews an area also reads that area's `AGENTS.md`. A skill reaches only the sessions
that load it, and subagents and Tend's runs often don't load one. So an `AGENTS.md`
holds the instructions whose
omission could let a change break something: goals, invariants that span modules,
who owns what, the criteria a change or review is judged by, and the checks to run,
each stated as a goal rather than as steps. Instructions for one kind of task, such
as previewing a page, proving a visible change or landing, go in a project skill
such as `/developing-leaf`, since a session that misses them does the task slower or
worse but breaks nothing. They don't go in the shipped `/leaf` skill. A procedure
for a rarer task goes in the project skill's `references/`, and the skill points to
it by naming the task. `running-tend` holds only the instructions for what Tend's
runs do and other sessions don't. A call the maintainer makes that will come up
again goes into the guidance its next case will read, in the change that carries
the call out; a note in one agent's memory reaches no other agent.

A contract one module owns goes in that module's header, and a helper's contract in
its docstring. A contract several modules share goes in the protocol reference for
that boundary, which says what each side relies on, not how one side provides it. A
header also states the product decisions its module embodies, each with its reason,
whether the user made it, and what an alternative cost when it was tried, for a later
change to weigh again. A change that reverses a decision rewrites its statement
and says so in its commit.

Text in the tree, comments, tests and eval cases included, says what holds now
rather than how it came to be. The date of a decision or change, the request or
incident behind it, the measurements that settled it and the versions before it go
in the commit message, where `git log -L` finds them.

Don't copy into prose a list the code already keeps, such as the bundles in
`vendor.mjs`, or a count of its members. Point to the code's list instead, so adding
a member needs no prose edit. Where prose must repeat such a list, a test checks the
prose against the code's copy (`tests/AGENTS.md`, "Put each assertion at the boundary
that owns it").

In shipped text (the references, `--help`, UI strings, `SKILL.md`) and agent
instructions (the `AGENTS.md` files and project skills), a review reports these
defects:

- text written for a reader other than the one the text addresses, such as an
  explanation of a mechanism that reader doesn't need. In maintainer guidance, that
  includes a sentence explaining how the diff's code works, which belongs in the
  module's header; the guidance says what other code must rely on;
- a second copy of a rule another text owns;
- a sentence its reader can parse only on a second read, as with a coined term used
  without its definition, a pronoun whose antecedent sits in another clause or only in
  the diff, or a rule joined in one sentence to its mechanism and its exceptions;
- a sentence about how a rule came to be.

On the site's pages (`docs/`), a review reports a sentence its reader can parse only
on a second read, a heading that tells a story or states a thesis where the topic's
name belongs, as "The page directory is the record" does for "Page directory", and a
sentence that restates the heading over it.

### The install runs this tree

An install from git copies the tracked tree into the harness's plugin cache and
follows `main`. Claude Code can instead load a checkout in place, through
`--plugin-dir` or a local-path marketplace. Point Codex at the git source, since its
local-directory marketplace also copies a checkout's `.venv`. Nothing is built at
install time: installing, authoring pages, writing custom packages and exporting
need no browser build or npm.

Pages run the browser runtime's modules from the install that serves them, as the
tree holds them. Two kinds of file there are built and committed, so an edit reaches
pages only once a build writes them (`build/AGENTS.md`): the JavaScript compiled from
a TypeScript module, and the static copy of the floating panel's row a page shows at
first paint. Only a prepared installation, such as the website's container, compiles
the modules into one bundle, the kernel (`build/runtime-bundle.mjs`,
`leaf.source.runtime_selection.read_runtime`).

`bin/leaf` runs `uv run --no-dev` on the tree, which writes the tree's `.venv`, so the
install must be writable; Leaf writes nothing else into it. A plugin update may
replace the install's directory, so anything that must survive an update belongs in
the page directory or the state home.

Each runtime dependency, including one a bundled package's script uses, states a
minimum version and no maximum. The host supplies Chrome and `jq`; Leaf never
downloads a browser.

Every tracked byte ships in every install and stays in the history, so the tree
holds no binary or large file apart from the generated `vendor/` bundles. An image
that a tool in this repository reads lives in `max-sixty/leaf-assets` instead, at
the commit `.config/leaf-assets.json` pins. Publish a new image there as part of the
change that needs it, without asking for separate approval: other branches keep
reading the commit they pin, so only this checkout sees the new image until it
lands. The `dev/leaf_dev/leaf_assets.py` header says how to resolve a conflict over
the pin. Evidence, such as screenshots, probe captures, recordings and raw run
output, stays in `.tmp/` and reaches the user on a Leaf page. A note keeps the
finding and the command that reproduces it, not the capture itself.

## Cross-runtime invariants

### The document starts state; the log changes it

A page's authored markup is its initial state, and the append-only event log records
each change. Every computation of current state starts from the markup and applies
the events still in force. Don't add a database, a current-state file or a
per-widget replay list as a source of truth for page state, and don't treat the DOM
as one.

Each decision the user made carries over to later versions of the page. To ask the
user again because a rewrite changed what a decision rests on, mark the changed
element `restated`, which takes it out of the decisions resting on it (`events.md`,
"Widget answers"); leaving the decision out of the new version withdraws nothing. An `undo` event names
the gesture it withdraws, and never deletes an event or adds an opposite one.

The registry gives each widget action and report a key of three parts: the widget,
the unit of the widget's state that the action changes, and the verb (`events.md`).
From one consistent read of the log, Python computes which action wins each key,
which actions were withdrawn, the state of each thread and of each obligation on the
user's On Me list, and the updates the user has sent the agent. It serves the
result, the server's reading of the page, to the browser.

In the browser, only `applicationState` (`runtime/state/semantic-state.js`) combines the
authored initial values, the server's latest reading and the tab's unresolved
gestures into current state. It publishes each state as one immutable value, which
holds no renderer nodes, promises or DOM attributes. Components read that value
through selectors and never write it. Widgets draw the complete state, unset and
undecided values included. Undo never rebuilds a widget or replays authored actions
into the DOM. A page widget's state draws only on actions logged up to the version
the page shows, as a `restated` mark leaves them. A
widget in a thread message has neither bound: its state draws on actions from its
whole thread, since its markup lives in the log rather than in a version.

A gesture's own result shows in the task that sends it, before the server answers
("Responsiveness"); a disabled control, a spinner or a delivery status is not that
result. To the server's reading, the browser adds only what a gesture decides by
itself: a thread the user opens, the user's own reply and its wait for an answer,
whether the question of the widget it acts on is answered, as that widget says
(`awaits`), and the words of a refused send, kept for the user to send again. When the server refuses
a gesture, the browser returns to the server's state.

Focus, scroll position, selection, open disclosures, a drag and layout belong to the
browser until a gesture makes one of them part of the page's state. The log doesn't
record them, so each lasts only as long as its DOM node. Code that replaces a node
moves that state to the new node, matching the two by the key the replacement already
uses. A draft being typed also stays out of the log until the user sends it, but it
outlives its node: the page's server keeps it for every tab and device
(`src/leaf/serving/drafts.py`), and the agent never reads it.

Python decides where the agent's work stands, in the one vocabulary every record and
surface reads (`standing.py`): whose move it is, and whether the work is waiting,
running, blocked or done. `activity.py` decides it for the agent's work on the whole
page, which the Leaf panel shows, and for each obligation record and each update the
user handed over (`workflows.py`), which messages, thread attention, the On lists,
margin entries and the Stop hook read. A busy page doesn't mean every message is being
worked on. The browser adds its own unsent gestures to what the server sends, but
never changes where a workflow stands, not even as time passes, apart from a widget's
own word on its question: an obligation a gesture answers or reopens stands so until
the server's reading of the gesture arrives. Another page
learns a page's activity only from the row `server_rows.py` writes and from whether
the page's server is alive. It shows that activity only in its list of other pages
(`/api/pages`), and that list feeds no page's own state and no server's reading of a
page.

The page directory is the durable record and the unit of deployment
(`src/leaf/page-storage.md`).

### Validate once and share readings

Validate each input once, where it enters: every event at
`event_contracts.append_admitted`, whether the browser posted it or a command wrote
it; authored markup at `page check`; message markup at `check_markup`. Admission
copies the event's meaning, as its widget's registry entry declares it, into fields
on the event, so later readers use those fields directly instead of looking up the
widget. An event names what it depends on by declared ids, never by words in its
detail.

A passage, the text a comment points at, is a list of `{node, start, end}` segments.
`says` is visible text; `wrote` is authored text. Every anchor an agent gives a section
resolves, to its words or to its element. When the passage a comment quotes appears
more than once and no surrounding context picks one copy, the comment stands on its
section or in Threads rather than taking a copy by its order or offset.

Leaf derives each fact about the page once, and each place that reports on the page
picks the facts it needs. `leaf page state` tells a later session the facts a
delivery told the agent about an event, under the same names and computed by the
same code (`event_facts.py`). It leaves out the fields that asked something of the
agent at delivery (`answer`, `handling`, `waiting`, `settled`), and it shows a message
as the message now reads. A fact about the past, such as the settings the user had
open when they wrote, is derived from the log and never stored as a second copy.

### Read what the page states

Leaf takes each fact about a page from a place where the page states it: the
structure HTML defines, including the relations HTML defines between its elements,
such as a `<label>` and its control, or a declaration in an attribute the author
wrote, in a registry entry or in the event log. A declaration on a plain element uses
a standard attribute that means the same to every reader. A declaration on Leaf's own
element uses Leaf's attribute, such as `label`, since no standard defines that
element. Leaf takes no fact from how content looks or what it says, and reads words
only to quote, anchor and show them. So restyling a page changes no fact Leaf holds,
and rewording it changes only its words.

### Keep the layer open

A content widget is one a package ships, unlike Leaf's own elements in
`browser/registry.json`, such as `lf-suggestion`, which core code may name. Leaf's
runtime, server and stylesheets never branch on a content widget's tag name or keep
a list of content widgets' tag names. They read each tag's facts, such as `verbs` or
`reading-role`, from its element declaration in the registry. A package's modules
may name the widgets they compose, and a test or a `leaf-dev` command may name the
widgets it exercises; a test that covers every widget with some property finds them
in the registry. So a new content widget needs only files in its own package: its
element declaration, its module and its styles. The registry's `$` keys hold facts
about the layer as a whole, such as the event kinds in `$events`. Each tag's element
declaration is that tag's complete schema.

Leaf's own instructions are `skills/leaf/SKILL.md`, its references, and the entries in
`browser/registry.json` and in the kernel registry
(`browser/runtime/kernel-registry.json`). They don't depend on a widget's name either.
Where one of them tells an author what to use, it names the form the author needs, such
as a before-and-after pair, a chart or a choice. Where a behavior depends on a declared
fact, such as `awaits` or `reading-role`, it names that fact. It names a package's
widget only as an example of a form or of a declared fact, or inside a markup example.
The page's vocabulary (`leaf page vocabulary <page>`) tells the author which widget
provides each form, and `packages.md`, "A widget", says where a widget's own guidance
goes. So an author finds a widget the same way whether Leaf bundles it or another
package the page selects provides it, whatever the widget is called. A package's own
guidance, in its registry entries and its `instructions/author.md`, is that package's
advice rather than Leaf's, so it may name any widget.

### Keep the package interface small

A package leans on Leaf only through the package interface: the keys of an element
declaration, the widget protocol, Leaf's own elements, the data contracts Leaf's
packages declare, the public modules and the names each exports, and the styling
names the references declare. The public modules are those `$public-modules` in the
kernel registry lists outside the library: Leaf's own, such as `widget-api.js` and
`effect-widget.js`, and the dependencies Leaf serves, such as Effect UI. Another
author's package has nothing else, so Leaf's bundled widgets use nothing else. The
interface sprawls through names that each look reasonable alone, and every later
change keeps each name working, so Leaf keeps it small and coherent. A change meets a
widget's need without a new name where it can, and `packages/AGENTS.md`, "A widget's
need of Leaf", says how to choose where it can't.

A smaller interface is worth a small visible difference. Where a name's work is to
keep a look, a first paint or a behaviour exactly as it was, the name goes, and the
change shows what a user will see differently. A promise the user is owed on every
widget is Leaf's to keep from outside, for an element that imports nothing, so a name
stays for a guarantee `SOUL.md` states only while Leaf can't keep it that way. A shift
as a widget first draws on a loading page breaks no guarantee.

### Wait for the event that ends the work

Code waits for the event that ends the work, such as a response, a process's exit, a
lease's release or a socket's close, so a slow machine only makes the wait longer.
Code sets a deadline only to cap a cost, or where an outside party imposes one, such
as a harness's hook timeout or a peer that can hang without closing. An imposed
deadline is the outside party's whole budget, shared by every step under it, and it
must be at least ten times as long as the work takes on a loaded machine. When a
deadline expires and a slower path exists, the code takes that path rather than
failing.

## Weigh what a change adds

Whoever writes or reviews a change asks whether each thing the change adds is worth
what that thing costs later changes and users, by the same bar "Regular maintenance"
sets for keeping existing code. A change's size says little about that cost: a
two-line selector can reach every page.

- **What it adds**: a mode, branch or special case; one more member of a set,
  allowlist or tolerance; a wait, retry or timer; a public option; code or layout
  space kept for a state that may never occur; a reliance on a dependency's
  internals.
- **What it repeats**: code the change writes may already exist under another name,
  in another directory, language or package. Search for the question each new
  helper, constant, selector, style rule or inline check answers, not for its name.
  A copy is a second definition that every later change must keep in step, even when
  a comment names its source. Where the change couldn't reach the existing code,
  export, move or generate that code rather than copy it.
- **What it puts between the author and HTML**: be hesitant to add anything there,
  such as a tag, class, attribute or key that says what an HTML element, attribute or
  CSS property already says, a rule that reads meaning out of the author's markup
  ("Read what the page states"), or a pass that rewrites that markup. Authors and
  agents already write HTML well, and each such addition is one more thing every
  author must learn and every later change must keep working. Add one only for what
  HTML can't say.
- **What it buys**: a behavior a user sees, an outcome the maintainer asked for, or a
  cost it measurably removes. A green test buys only what the test protects, so name that.
- **Where its cost lands**: judge what the change reaches, not what it claims. Compare
  a selector's or guard's scope with the condition it names, find what else inherits
  from or sits inside the box it changes, and count how often a guard fires on a
  correct setup. Then compare who pays with who gains. A cost paid in every state or
  on every page usually outweighs the fix it buys for one transition.
- **The cheaper change**: a primitive from the platform or a dependency, a fix in the
  code that owns the behavior rather than in a caller, deleting a stale copy, or
  leaving the gap open with an issue filed. When `git log -L` shows earlier changes
  compensating for the same gap, ask whether the mechanism they patch is the wrong
  primitive, and whether a general form of the cheaper change would make all of
  those patches unnecessary.

Keep an addition when its benefit is concrete and no cheaper change buys the same, as
with a fix in a primitive that every caller gains from. Otherwise make the cheaper
change, or ask for it in review. When the fix for a review finding would add another
branch, flag or condition, first ask whether the finding shows the change's approach
is wrong.

## Regular maintenance

Whenever a survey, a review or the nightly sweep reads a file, look for code that
makes Leaf harder to develop than it is worth:

- **A mechanism users wouldn't miss.** Ask who would notice it gone and what it costs
  the changes around it. Code woven into the core runtime, the server or a shared
  contract costs every nearby change, so it must clear a much higher bar. Signs that
  such code doesn't clear it: a special case for one widget or gesture spread across
  several owners, such as code that holds the page still during the gesture or carries
  browser state to a replacement node; a public API whose only callers are tests or a
  single example; a mechanism that `git log --follow` shows was patched again and
  again (without `--follow`, a file's history stops at its last move). Code in its
  own module, such as a package, a widget or a `leaf-dev` command, costs little
  beyond its own files; remove it only when it is large and unused. Keep what
  `SOUL.md` guarantees, and each feature: something a user can do on a page, or a
  page or widget an author can build, by whatever route. A name of the package
  interface is not one. Nor is how a thing looks, when it first paints or exactly how
  it moves: a small difference in one of them is a price a removal may pay, and the
  removal shows it. Taking a feature
  away is the maintainer's call ("The maintainer decides"), so propose the removal
  with what users lose and what it deletes, measured as `/developing-leaf`'s "Measure
  a removal" says. The maintainer builds features ahead of their use, so little use
  on the maintainer's own pages doesn't show that a feature is unused: rest the
  proposal on a test of the feature itself, such as an honest attempt to place it in
  an example.
- **Code that chooses for the agent.** Code can settle a choice the agent could make
  by refusing it, by overriding what the agent wrote, by reading a meaning off the
  form of the agent's act rather than its declaration, or by binding the agent to a
  cutoff. Each stays or goes by "Leaf's role", whoever asked for it. Only a refusal
  prints a finding the agent reads, so find the others by comparing what the page
  draws with what the agent's write declared.
- **Several implementations of one capability.** Consolidate them into one, and move
  every caller to it ("Fix the underlying issue"). The other copies seldom sit beside
  the file you're reading, so search for them as **What it repeats** says.
- **A mechanism a dependency or the platform already provides.** Delegate it ("Use
  dependencies").
- **A name the package interface could lose.** `uv run leaf-dev interface` lists every
  name with its form and what uses it. Look at a function one bundled widget calls, a
  key one declaration sets, a styling name one sheet reads, and a name that says what
  HTML or another name already says. Move the promise into Leaf, or the code into the
  library or the widget, and remove the name (`packages/AGENTS.md`, "A widget's need of
  Leaf").

## Working on the repository

A choice about how something looks or moves can't be judged from a description, so
every UI option you leave to the user carries a picture of its result: a still pair,
a sketch, a diagram or a live sample.

Before writing words the user sees, such as a label, status line or placeholder, and
before naming anything the user operates or choosing an identifier for it, read
`.claude/skills/developing-leaf/references/glossary.md`, Leaf's canonical vocabulary
and guidance for visible text. A control may need no words at all
(`browser/AGENTS.md`, "Controls are few and quiet"). Before changing anything Leaf
draws, read "Leaf's interface" in `browser/AGENTS.md`.

The user judges a UI change by using it and by looking at it, so whoever hands one
over or reviews it does both (`/developing-leaf`, "Review a UI change"), with a
`/ui-sweep` pass for a theme or shared-control change.

Before finishing a feature:

- Every result a user can reach with a pointer must also be reachable by keyboard
  and by touch (`browser/runtime/dom/keyboard/AGENTS.md`, "Touch routes"), without a
  page-level binding for each result. The routes are owed to each result, not to
  each pointer gesture: a gesture needs another route only where, without it, a user
  could no longer see, reach or decide something. Dragging a thread card aside needs
  no other route, since Escape also uncovers the passage beneath the card.
- Follow `examples/AGENTS.md`. Each tool that reads the combined corpus page builds
  it on demand, so a feature needs no step to regenerate it.
- If the feature changes what an agent can do or how, update `skills/leaf/SKILL.md`
  or the one reference that owns the workflow, and point other references at that
  section. Shipped instructions set goals for the user's experience and name where
  the user reads the result, such as the page or the chat, and leave format and
  phrasing to the agent.

Score both versions of a change to agent instructions that an agent could read more
than one way, such as a new or reworded rule, a goal that competes with another, or
the removal of text that may have been producing a behavior (`/developing-leaf`,
"Score an instruction change"). Deleting a description of an input that can no
longer arrive, or correcting a fact, needs no score.

Several sessions share one machine, so local compute is often the bottleneck.
Before handing over, run the tests that cover what the change touches, and
`pnpm run test:runtime` when it reaches the runtime (`tests/AGENTS.md`, "Run what
the change needs"). The broad selection, `uv run pytest tests`, runs at landing: in
a pull request's `test` job and in `wt merge`'s pre-merge step. Don't run it by
hand, and don't run a whole browser test file or a later tier (`--run-main`,
`--run-nightly`, `tests/browser`, `tests/journeys`), even for a change that most of
the suite exercises: each takes minutes to over an hour and slows every session on
the host. Before widening your selection or its parallelism, check CPU, memory
pressure and other running suites, and on a busy host keep to focused checks.

The suite and pre-commit don't run three gates: the type check of the TypeScript in
`worker/src/`, the browser runtime's type check (`browser/types/`), and the check of
the lock every committed bundle is built from. `pnpm run check` runs all three, and
both ways of landing, a pull request and `wt merge`, run it too. The website's
delivery checks (the site build, the Worker's dry-run deploy, `leaf-dev site verify
website-worker`) run on a pull request and in `publish-site`, but not in `wt merge`.

When a change alters how a harness runs Leaf, such as its hooks or sandbox, run the
agent journey on that harness (`/developing-leaf`, "Run the agent journey").

For a change that can alter browser startup, compare base and head
(`/developing-leaf`, "Compare checkout versions"). A change that adds work before
the page first shows the server's state says what the user gains and why the work
can't wait. A better look or a more immediate answer to the user is gain enough: the
maintainer weighs how Leaf looks and responds far above the bytes it loads. Take it and report
the bytes, rather than putting the trade to the maintainer or building machinery to
save them. Saving bytes that don't load before that point, such as a lazy module's,
a vendored file's or the install's, doesn't by itself justify a change.

Land through a GitHub pull request, which squash-merges to `main`; use `wt merge`
only when the maintainer asks for it. For now, a failing check the change doesn't
cause blocks nothing (`tests/AGENTS.md`, "Run what the change needs"). Tend's runs
follow **Landing** in `.claude/skills/running-tend/SKILL.md`.
