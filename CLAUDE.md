# leaf

Leaf is a page an agent hands to a user and the loop that carries anchored
comments and actions back. `README.md` covers the product. This file records the
architecture and the rules that keep it buildable.

## Product and stage

Leaf exists to give the agent and user a high-fidelity shared surface. A page can
use prose, diagrams, movable boards, comparisons, and other structures suited to
the subject. Comments stay attached to the words or element that prompted them.
The page can also change while work proceeds, so it is the work surface rather
than a report written after the fact. Theme, registry, and widget overlays let a
project add a shape the shipped vocabulary lacks.

The project has no users, deployment, database, or persisted state that constrains
new code. Delete and regenerate stale state. Rename or reshape interfaces whenever
the result is simpler; backward compatibility has no weight yet. A guard belongs
only where the guarded state is reachable and there is a useful response.

Make improvements that follow from the code and these rules. Ask the user only
when the decision depends on purpose or intent that the repository cannot supply.

Validate data once at its boundary: browser events at `POST /api/event`, authored
markup at `version check`, and replayed action detail in the widget's
`applyAction`. Downstream code reads validated fields directly.

## Repository shape

Claude Code and Codex both resolve `plugins/leaf/` as the plugin payload. The
repo-root pointers are `.claude-plugin/marketplace.json` and
`.agents/plugins/marketplace.json`; the payload carries one manifest for each
host. Six parts live under `plugins/leaf/skills/leaf/`:

- `scripts/interact.py` is one `uv` script containing the server, event log,
  `version check`, vendoring, and export. The payload's `bin/leaf` shim invokes
  it. There is no daemon or database.
- `assets/leaf.js` is the page runtime and comment layer. Its private styles live
  in the module. There is no build step.
- `assets/registry.json` is the integrated widget vocabulary and the layer-wide
  `$` declarations read by the runtime, linter, renderer, catalog, and docs.
- `assets/theme.css` owns tokens, element styles, class idioms, integrated widget
  rules, and the shared look of runtime chrome.
- `assets/icon.svg` is the page and site mark. The runtime paints its `lf-tone`
  element with page status.
- `bundled/` is an overlay layer containing shipped content widgets, their
  registry entries, modules, theme rules, and vendored libraries. It enters a
  page through the same merge as user and project customizations.

The seventh product part is repo-root `examples/`: complete pages that form the
render corpus. `examples/gallery.html` is generated from them.

Each example is both an authored page and an integration fixture. The corpus must
exercise every shipped widget and every declared relation the render gate can
observe. Edit the individual examples and regenerate the gallery; never patch the
generated gallery directly. The website publishes the same examples with one
vendored layer, so the corpus also proves that a page works outside the developer
server.

`plugins/leaf/hooks/hooks.json` serves both hosts. Codex supplies
`CLAUDE_PLUGIN_ROOT` as a compatibility alias. The launcher maps Codex thread
identity into the session record Claude Code supplies directly.

The session record has two independent facts: host identity and process lifetime.
The launcher may translate the first, but it must derive the second from the host
process itself. A pipeline or shell wrapper is command lifetime, not session
lifetime; tying the server to it retires the page as soon as the launching command
returns.

`page init` vendors the complete merged layer into a page directory. A reviewed
page therefore keeps the assets it was reviewed with. `interact.py`'s module
docstring defines every file in a page directory.

Layers merge from shipped integrated assets, through bundled widgets, then the
user's `~/.config/leaf/` and the project's `.leaf/`. Theme files concatenate.
Runtime, icon, widget, and vendor files replace by path. Registry tag entries
replace whole, while members of shared `$` entries compose. Each initialization
validates the merged vocabulary and writes the same fresh layer epoch into the
runtime and registry. An open tab carrying an older contract reloads before its
next poll or event reaches the replacement server.

The page directory is both durable record and deployment unit. It contains
immutable version files, the append-only log, vendored assets, service state, and
status. Do not add a database, daemon, build output, or hidden current-state file
between those parts. A static export derives from the same version and log, then
removes live handlers and replaces controls with their answers.

## Ownership rules

Detailed browser, widget, and theme rules live in
`plugins/leaf/skills/leaf/CLAUDE.md`. Server and lint rules live beside the code
in `interact.py`; test rules live in `tests/CLAUDE.md`; corpus rules live in
`examples/CLAUDE.md`. The rules below cross those boundaries.

### The document is the initial state; the log owns transitions

Authored markup states a page's initial condition. The append-only event log
records every transition after it. There is no second store for the current
board, chosen option, or other widget state. Every projection starts with markup
and applies the standing log.

A later version does not cancel a reader action by omission. Replay preserves
the action unless the version explicitly retracts what it rests on. When a
rewrite invalidates a decision, put `restated` on the rewritten element.
`version check` refuses both a silent conflicting rewrite and an unearned
`restated` through `restatement_errors`. A version that honors a decision records
the resulting state or retires the decided content.

The default deliberately favors preserving a reader decision. Dropping it by
accident is invisible to both sides, while an author sees a stale decision at the
moment a rewrite conflicts with it and can decide whether `restated` is earned.
The check therefore routes that choice to the author instead of inferring assent
from a version's silence or from event acknowledgement.

The reader withdraws a gesture with one `undo` event naming the event taken back.
Nothing is deleted, and no counter-gesture is invented. Every fold and thread
reading drops the named event. The undo control offers a page-widget action only
on the version where that action was made, because a later version may already
have been authored around it. Hearing the undo on any version still triggers the
ordinary reconciliation of what remains. Threads are never pinned to a version;
the conversation outlives the document version that opened it.

Actions and reports project onto one semantic coordinate: owner widget, declared
fold unit, and facet. The latest surviving reader action wins its coordinate and
outranks provisional agent news there; different coordinates still compose in
event order. Reports remain live until a version note absorbs or overrules them.
Actions remain live until undo or a later retraction floor ends them. Both Python
and JavaScript derive those answers from the same registry declarations.

Page-widget actions and reports are bounded by their document version when the
projection asks what that version showed. Thread-widget actions live in frozen
log markup and take the whole conversation window. Version notes provide durable
retraction and report-absorption floors: the version after the note does not need
to repeat them. A pinned page may therefore show its historical widget state
while the comment panel shows a later retraction; each reading is answering its
own question.

An action rests on its sending widget and any detail ids contained by that
widget. Retraction uses that containment relation, so rewriting one card can
withdraw moves of that card without withdrawing unrelated moves on the board.
The same predicate governs replay, word survival, and the thread a decision
settles. A decision cannot stand in one reading after another has retracted it.

Reconciliation states the cheapest faithful result. A declared record can state
an absolute value or placement directly. A recordless action rebuilds its widget
from the inert authored clone, then replays every surviving action. The clone is
taken after the registry loads and before modules upgrade the document, while the
DOM still contains only authored markup. A position record includes both its
container and order field so restoring a move cannot put an item in the right
container at the wrong position.

The browser may also hold unresolved local work. Its outbox is an ordered overlay
after the authoritative log. A gesture that already changed the DOM, such as a
drag or edit, remains visible while unresolved. A decision press waits for the
accepted log state before painting its result. A refusal removes that attempt and
reconciles from authored records, standing log winners, and the remaining outbox
in order. Accepted attempts stay unresolved until a complete state application
accounts for them; retries keep the same attempt id and cannot reorder later
events. The runtime's detailed contract lives in its own `CLAUDE.md`.

Registry declarations choose these routes. Core does not branch on widget names.

### One representation answers one question

A passage is a sequence of `{node, start, end}` segments. The same segments serve
selection capture, quote search, reading-position landmarks, and version-diff
block keys. Python's `page_passages` is the file-side reading; callers slice its
`spoken` output instead of walking markup again. Element anchors remain distinct
because they name a box rather than text.

Limits belong to the scarce operation. A quote is not truncated to protect the
event log. `LEAD_CAP` limits only the regular-expression lead used to find
candidates, and the resolver compares the remainder directly against the passage.

The two text readings answer different questions. `says` is what the user can see
and point at, including a widget label declared as page words. `wrote` is authored
text, excluding generated upgrade content. Version diffs and a widget naming one
of its own authored parts use `wrote`; anchors use `says`.

Generated words carry the same distinction. `data-lf-gen` excludes upgrade
content from `wrote`, while `data-lf-said` marks generated text that remains part
of `says`. Unmarked runtime chrome stays outside the page's reading. A widget
must use `says` when reading its own visible slot because the runtime may place
hidden comment announcements inside the widget's light DOM.

An element anchor uses the visible boxes of the element rather than inventing a
text passage. A `display: contents` wrapper has no box of its own, so browser
geometry uses `shownBox` or `shownParts` to read the boxes its contents paint.
Identity still crosses declared shadow roots through `elementById`, while the set
of widgets a page contains remains the document's declared vocabulary rather than
a sweep through module-created trees.

### File capture never promises more than browser capture

`selectionAnchor` captures from the DOM. `leaf comment` captures from a version
file. Both collapse text by the same rules, and `resolveAnchor` is the only search
implementation. Both readings apply the event log first, including reader edits
and retired content.

A module may render text the file parser cannot model. Registry declarations
place passage fences around that content. The file refuses a quote that crosses a
fence; the browser indexes the same fences before upgrades and clips captured
context to them afterward. A widget that adds words declares a model for them or
stays fenced.

The file parser also follows settled relations and reader edits. It refuses to
quote content the log retired or replaced and names the event responsible. This
keeps a command-line comment from creating an anchor the browser could never
paint. Browser capture never reaches across a fence merely because upgraded DOM
happens to put selectable text on both sides.

Context identifies an occurrence only when exactly one candidate confirms it in
full. With no full contextual match, a globally unique quote may identify itself.
A repeated quote detaches instead of falling back to document order, offsets, or
ordinals.

### The widget vocabulary stays open

A widget family grows by adding a complete entry to `registry.json`, plus a
module and theme rules when needed. Consumers dispatch on declarations, never on
a closed list of tag names. A new widget should touch only its own entry, module,
and rules.

Content widgets remain anonymous outside their own module. Core may name a tag
only when the Leaf loop itself is defined in terms of that tag; there are no such
content widgets today. The suggestion family retains one member-specific lint,
`suggestion_errors`, because its cardinality and nesting rules are not expressed
by the general holder/slot relation. Do not turn that validation into a generic
runtime branch.

Declarations describe general behavior:

- `x-upgrade` says that a module enhances the element.
- `x-awaits` says the element can hold a request for the reader. It feeds the
  banner count, asks tray, keyboard walk, help, and conditional actions. Its
  answer verbs are explicit; `rollup` derives a nested plan from ordinary
  interventions and child roll-ups without naming either family.
- `x-parent` declares the members that make up a holder. Combined with
  `x-retired-when`, it defines which slots a settlement retires.
- `x-withdrawn-as` states what an unanswered member becomes when the author
  withdraws it.
- `x-wide` names the kind of width (`box` or `drawing`) rather than hiding a
  second behavior in a boolean.
- `x-says`, `x-paints`, content, shadow, state, report, and record declarations
  give each shared consumer the information it needs without naming a widget.

An `x-` declaration recorded in the log is a durable contract. The vendored
registry stamp carries `$events`, and version checks compare the page's logged
contract with the incoming layer. Find the general property before adding a key;
do not hide a widget name behind a declaration whose meaning is still specific to
that widget.

The layer owns behavior that follows completely from a declaration. Replay paints
`data-lf-state` on a settlement holder and `data-lf-retired` on retired slots;
one theme rule hides them. A module supplies only its own choreography. The render
gate checks the visible result that declarations alone cannot prove.

The holder/slot relation is also what permits an honoring version to drop ids the
decision retired. `retirement_slots` derives that permission for any declared
family. `x-withdrawn-as` covers the different author-side case in which an
unanswered holder is withdrawn. These are relations between declarations and
events, not special rules for suggestions.

CSS is a consumer too. A selector listing every framed tag closes the vocabulary.
A box declares `--lf-frame` where it draws its frame. Shared style queries use
that declaration to trim collapsed child margins and to limit the room a wide
exhibit may take inside the box. `main` hands page-wide room back to its contents.
The render gate checks trapped margins, clipping, and width on the composed page.

The declaration follows the drawn box rather than the tag. A nested task may draw
its frame only in a child selector, and a module may generate a framed class with
no corresponding element name. `x-content` says whether authored block flow can
enter a widget, but the browser decides which rule drew a box. Style queries and
render checks therefore read the composed result instead of maintaining parallel
tag lists.

Layer-wide facts live under `$` keys rather than under the first widget that needs
them. `$languages` owns tokenizer language names; widgets declare the attribute
that carries one through `x-language`. Layer merging composes `$` entries member
by member. A tag entry replaces whole because it is one indivisible schema
contract. `merge_layer_entries` supplies the same merged result to the stamp and
all gates.

An action's detail schema, semantic facet, fold unit, current-state eligibility,
and record form come from `x-state`; reports use the parallel `x-report` channel.
The browser presents and guards a conditional action from that declaration, while
POST interprets it again against the authoritative fold under the append lock.
Eligibility reuses the standing-request projection declared by `x-awaits`; it has
no separate cache or widget-state vocabulary.
`applyAction` states an absolute result and is idempotent because polling may apply
a standing winner again. `version check --render` exercises represented verbs in
log order through `RELATIVE_REPLAYS`.

`shallowSigs` reads authored state without text, while a record form extracts the
declared words and placement fields. The render gate reapplies every standing
winner for a coordinate, not each event in isolation. Two position units in one
container may both stand, so only the whole ordered projection can prove that
reapplication is a no-op.

A record form also defines which author-namespace attributes a module may write.
Entries use `additionalProperties: false`; undeclared runtime state belongs on
generated chrome, in platform state, or under `data-`. `UNDECLARED_ATTRS` checks
the rendered page, the only place module writes are visible.

The file lint closes the author's attribute namespace, but it cannot see a
module's writes. A module writes durable author state only through declared
record fields such as `chosen` or `status`. Transient tab state belongs on the
control that carries it or under `data-`; mirroring it onto the authored element
creates a second state representation that `shallowSigs` will treat as authored.

The same open-list rule binds documentation and scaffolding. `page catalog`
reads the merged registry and theme idioms. `leaf customize widget` scaffolds a
complete entry, a framed theme rule, and optionally an upgrade module that uses
the exported helper surface. Adding a twelfth widget must not require updating a
handwritten catalog, renderer branch, CSS tag list, or prose enumeration.

## Working on the repository

- Tests are browser integration tests. `tests/CLAUDE.md` defines what they must
  prove and how to avoid vacuous passes.
- A cloud container needs the pinned developer environment before it can run the
  suite:

  ```sh
  uv sync --frozen
  uv run playwright install chromium --only-shell
  uv run playwright install chrome
  uv tool install pre-commit
  ```

  A container without IPv6 cannot run the two tests that bind the stated-host
  wildcard `::`; run those from a workstation.
- Measure the real surface before changing performance. Use
  `examples/gallery.html` for runtime costs.
- Re-vendor before believing a render result. A page serves its vendored copy, so
  run `page init` again after changing the layer. A served page uses the quiescent
  stop, init, start sequence so the old contract releases its socket and lease
  before the new epoch appears at the same recorded URL.
- Land with `wt merge`, a direct local squash merge to main, never a PR. This
  chooses the landing form, not whether landing was requested. Finished work
  waits for the user's authorization unless the task already granted it.
- Sessions load host caches, not the checkout. Both marketplaces install from
  GitHub main. Claude Code keys an unversioned manifest by commit and updates on
  its marketplace sweep. Codex requires
  `codex plugin marketplace upgrade leaf`, followed by
  `codex plugin add leaf@leaf`. A pushed change reaches the next session.

### The suite

`test_interact.py` covers lint, vendoring, publishing, catalog, export, thread
markup, and file-side anchors. `test_render.py` covers the browser runtime and
examples. `test_product_page.py` covers `docs/`. `test_site.py` builds and reads
the published site. The journey test selects a passage, comments, moves a card,
follows a version, and checks the surviving anchor and log.

The browser corpus is read in both color schemes. It checks widget upgrades,
usable boxes, independent document and panel scrolling, script-free textarea
sizing, control stability under presses and arriving news, print, and page width
on a phone. A second sweep reads each example as a returning reader with the
panel, a tray, or design mode restored. Every other corpus reading is a first
visit, so restoration cannot hide an arrival regression.

The developer environment comes from `pyproject.toml` and `uv.lock`. Leaf's own
runtime dependencies remain in `interact.py`'s PEP 723 header. Tests load that
script by path and therefore need the same packages.

The everyday suite needs no network after setup and runs one shipped page through
the browser gate:

```sh
uv run pytest tests
```

`test_render.py` and `test_site.py` are marked nightly. A focused browser run must
include `--run-nightly`; without it pytest deselects the module and exits 5. Turn
xdist off while iterating:

```sh
uv run pytest tests/test_render.py -q -n0 --run-nightly -k board
```

Run the complete suite before handoff. It needs a network because the installed
launcher's browser path may resolve Playwright outside `uv.lock`:

```sh
uv run pytest tests --run-nightly
```

Ruff and prettier come from `.pre-commit-config.yaml`. `wt merge` runs them and
the suite through `.config/wt.toml`; CI repeats both on main and pull requests.

```sh
pre-commit run --all-files
```

The Linux container supplies the pinned headless shell, installed Chrome, and CI
fonts. It accepts pytest arguments and needs a Docker daemon that can run
linux/amd64:

```sh
scripts/linux-suite.sh
```

Fixtures relocate only Leaf's XDG config and state homes. They leave the rest of
the home intact so subprocesses can use the developer's `uv` cache. The nightly
modules drive separate headless shells under xdist; focused debugging uses one
worker so browser timing and output remain readable.

### Driving a page by hand

`scripts/preview.py [example]` freshly vendors and serves a shipped example;
`examples/CLAUDE.md` defines its fixtures. For another page, run `page init` and
serve it in-process with `interact.handler_for(page_dir, token)`, then open the
key as `?t=…`. `server start` instead attaches a live page to the session and its
hooks.

### The website

`scripts/site.py` builds <https://leaf.page/> in `.tmp/site`.
`.github/workflows/publish-site.yaml` runs it for relevant pushes to `main`. The
build rewrites checkout-relative asset paths, publishes one vendored layer and
each example at `examples/<name>/versions/v1.html`, and refuses unresolved local
links. Asset references become site copies; other payload paths become GitHub
links. `docs/session.js` loads before the vendored runtime and puts the example
event log in the reader's tab; no agent reads it on the static site.

```sh
scripts/site.py
```

`scripts/record-demo.sh` drives the shipped server and Chrome to write
`docs/demo.gif`, which the README and site use.

### Vendored bundles

`scripts/vendor-highlight.sh` rebuilds
`plugins/leaf/skills/leaf/assets/vendor/highlight.esm.js`. It reads
`$languages.names` from the registry so the browser bundle and lint accept the
same languages.

`scripts/vendor-marked.sh` copies the pinned, dependency-free
`vendor/marked.esm.js` used for thread Markdown.
