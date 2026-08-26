# leaf

Leaf is a page an agent hands to a user and the loop that carries anchored
comments and actions back. `README.md` covers the product. This file records the
architecture and the rules that keep it buildable.

## Product and stage

Leaf exists to give the agent and user a high-fidelity shared surface. A page can
use prose, diagrams, movable boards, comparisons, and other structures suited to
the subject. Comments stay attached to the words or element that prompted them.
The page can also change while work proceeds, so it is the work surface rather
than a report written after the fact. Packages let a project add themes, widgets,
modules, and other contributions without changing Leaf's kernel.

The project has no users, deployment, database, or persisted state that constrains
new code. Delete and regenerate stale state. Rename or reshape interfaces whenever
the result is simpler; backward compatibility has no weight yet. A guard belongs
only where the guarded state is reachable and there is a useful response.

Make improvements that follow from the code and these rules. Ask the user only
when the decision depends on purpose or intent that the repository cannot supply.

Validate data once at its boundary: browser events at `POST /api/event`, authored
markup at `version check`, a message's `markup` at `check_markup`, and replayed
action detail in the widget's `applyAction`. Downstream code reads validated
fields directly. The two markup doors read one parser and share what a fragment
can fail in its own right; `check_markup` says which checks those are and why
they sit where they do.

## Repository shape

Claude Code and Codex both resolve `plugins/leaf/` as the plugin payload. The
repo-root pointers are `.claude-plugin/marketplace.json` and
`.agents/plugins/marketplace.json`; the payload carries one manifest for each
host. Six parts live under `plugins/leaf/skills/leaf/`:

- `scripts/interact.py` is the `uv` script and public CLI entrypoint for the server,
  event log, `version check`, vendoring, and export. Pure implementation domains
  live beside it under `scripts/leaf/`: `files` owns atomic file
  operations, `events` the append-only model, `service` host and process
  lifetime, `registry` the merged vocabulary, and `projection` the standing
  state derived from events. `validation` owns event, markup, and authored-page
  checks; `rendering` owns the browser gate and standalone export; `cli` declares
  the Click surface. Schema, document, and browser-probe modules sit below those
  owners on the same dependency path. The payload's `bin/leaf` shim invokes the
  facade. There is no daemon or database.
- `assets/leaf.js` is the browser entry and comment layer.
  `assets/runtime/widget-api.js` is the public helper surface for behavior
  modules. Its private context, state projector, passage reader, anchor painter,
  conversation reconciler, and chrome stylesheet live beside that boundary
  under `assets/runtime/`. There is no build step.
- `assets/registry.json` is the kernel vocabulary and the layer-wide `$`
  declarations read by the runtime, linter, renderer, catalog, and docs.
- `assets/theme.css` owns tokens, elements, class idioms, and the shared look of
  runtime chrome.
- `assets/icon.svg` is the page and site mark. The runtime paints its `lf-tone`
  element with page status.
- `packages/default/` supplies the bundled content vocabulary. It enters the
  composer through the same package contract as an explicit package, `.leaf/`,
  or `~/.config/leaf/`. A package may carry a theme, zero or more widgets,
  helper modules, vendor files, typed external-data contracts, contribution or
  package-wide guidance, or top-level layer files.

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

The session record has two independent facts: host identity and session lifetime.
The launcher may translate the first, but the second comes from the host itself:
the session's own process, or for a daemon-hosted background job the record the
daemon keeps for it. A pipeline or shell wrapper is command lifetime, and a
background job's worker is sitting lifetime; tying the server to either retires
the page while the session still stands.

`page init` vendors the complete merged layer into a page directory. A reviewed
page therefore keeps the assets it was reviewed with.
`plugins/leaf/skills/leaf/references/internals/page-storage.md` defines every
file in a page directory.

The kernel and packages merge in this order: `assets/`, the bundled default
package, explicit package paths in command order, `~/.config/leaf/`, then
`.leaf/`. The vendored registry records explicit paths under `$layer.packages`
so a plain re-init resolves the same packages. Theme files concatenate.
Runtime, icon, widget, and vendor files replace by path. Registry tag entries
replace whole, while members of shared `$` entries compose. Package-wide guidance
files with the same audience name concatenate in package order; contract guidance and
widget `x-guidance` stay attached to the contribution that owns them. Each initialization
validates the merged vocabulary and writes the same fresh layer epoch into the
runtime and registry. An open tab carrying an older contract reloads before its
next poll or event reaches the replacement server.

The page directory is both durable record and deployment unit. It contains
immutable version files, the append-only log, the explicit replace-in-place
`data.json` authority for page-bound sources validated against named contracts,
vendored assets, service
state, and status. Do not add a database, daemon, build output, or hidden derived
current-state file between those parts. A static export derives from the same
version, log, and data snapshot, then removes live handlers and replaces controls
with their answers.

A concrete data source id has one contract for the page's lifetime. Every immutable
version and every widget frozen into thread markup can keep consuming the current
replace-in-place snapshot, so clearing a value does not free its id for reuse. The
binding is derived from those documents, exposed by `page state`, and preserved across
re-vendoring; a new meaning requires a new source id.

## Ownership rules

Detailed browser, widget, and theme rules live in
`plugins/leaf/skills/leaf/CLAUDE.md`. Server and lint rules live beside the
facade and its `leaf` domains; test rules live in `tests/CLAUDE.md`;
corpus rules live in `examples/CLAUDE.md`. The rules below cross those
boundaries.

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

News about an item has one canonical projection even though its sources keep the
stores their lifetimes require. Logged widget reports and replace-in-place work
claims share a typed envelope and deterministic order. A target is always
`{kind, id}` because a widget id and a thread id are different identities even if
their spelling matches. `source` keeps authority visible. The closed `disposition`
is `effective` when an entry contributes to current state on its semantic
coordinate, `standing` when it still awaits settlement but is presently
outranked, and `settled` once its authority answers it. Do not infer disposition
from presence in the feed. A report is settled by a version note. A thread work
claim is effective while the thread is open and no later agent reply has answered
it; resolving hides it and reopening reveals it again. Widget work survives
unrelated versions and ends only when a later version note carries a `work`
settlement for the widget. A new claim on either subject starts after a later log
sequence. Registry
`x-report.update` names the required non-empty string detail field exposed as an
update's human-readable text; consumers do not guess it from widget vocabulary.

Presence derives a widget claim's origin version from its sequence boundary
before any consumer receives it. A version may not silently remove an active
claim's local seat, and neither may a layer re-vendor: settle the work in a later
version first. Pinned pages do not show widget work claimed on a later version.

A widget's local seat also stays declaration-driven. `x-work` explicitly admits
the transient line either as a generated child of block prose (`content`) or at
the start of a matching `x-conversation` (`conversation`), optionally under a
predicate. `x-content: prose` alone is not permission: that prose may itself be
a holder gesture or may stand in a hidden panel. Core must refuse an undeclared
target rather than branch on a tag name or infer a safe insertion point.

Page-widget actions and reports are bounded by their document version when the
projection asks what that version showed. Thread-widget actions live in frozen
log markup and take the whole conversation window. That markup is a second
document beside the version, with an element universe of its own: every reading
that must answer for a widget an agent sent — the action gate at the door, and
`page state` for a session picking the page up — builds it through
`thread_state`, so a decision made in the panel cannot stand at one and be
missing at the other. A wait batch answers for one too, and reads the log alone:
a delivery may not raise on the registry gate a vocabulary load is, so it
carries the conversation's gestures unfolded and leaves the fold to `page
state`. A fragment gets no stylesheet of its own; it has no page to dress.
Version notes provide durable
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

### The host supplies what leaf runs on

Leaf installs onto a host whose software supply chain is not ours. Every
dependency it reaches for resolves through the index that host already
configured, and the payload states nothing a host cannot answer.

So the payload ships no lock. `uv` resolves `interact.py`'s PEP 723 header
against the host's index the first time it meets those requirements, then reuses
the environment it built. A lock would install from the absolute pypi.org URLs it
records and ask no index at all, so a client on a private mirror is served around
it and one with no route to pypi.org cannot install. `uv.lock` beside
`pyproject.toml` is the developer's reproducibility, not the client's.

The header states a floor per dependency, the lowest version the suite passes on,
and `bin/leaf` hands Playwright the same. It states no upper cap. Neither
`UV_OVERRIDE` nor `UV_CONSTRAINT` loosens one, so a cap is the one thing here a
host cannot answer, and a guess at a major release that does not exist yet is a
poor thing to make unanswerable.

The interpreter is the host's too: where no installed Python satisfies
`requires-python`, uv fetches a build from GitHub, and `UV_PYTHON_DOWNLOADS` and
`UV_PYTHON_INSTALL_MIRROR` govern that. The render gate launches the host's
installed Chrome rather than downloading one. Nothing in the payload writes back
into its own install directory either: a host may mount it read-only, and an
update replaces it wholesale.

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
- `x-ask` says the element is the complete reading and arrival region around one
  nested request. The nested `x-awaits` widget still owns the answer and fold.
- `x-awaits` says the element can hold a request for the reader. It feeds the
  banner count, asks tray, keyboard walk, help, and conditional actions. Its
  answer verbs are explicit; `rollup` derives a nested plan from ordinary
  interventions and child roll-ups without naming either family.
- `x-conversation` and `x-awaits` on one widget is a request with a box under
  it, and two things take that request off the reader's list. An answer verb is
  one. A conversation standing in the widget's own seat while it waits on the
  agent is the other, and it is not an answer: the widget holds no state for it
  and its controls still offer one. Saying otherwise asked the reader a second
  time for what they had just written, in a box the page itself put under the
  question, while the panel showed that thread as the agent's to answer.
  An ordinary reply hands the conversation back. A conversation declared with
  `response: version` takes no agent reply: its page seat is text-only, the reply
  door refuses it, and the agent opens a separate thread when the revision needs
  clarification. While that thread waits on the reader in the same seat, it carries
  the original response through the stop gate; their answer hands both back to the
  agent. A version that records the decision ends the request, and only then may
  the agent resolve the original thread.
  The stop hook reads the same fact, so what leaves the reader's banner lands
  on the agent's own gate rather than nowhere; `awaits_agent` is the one
  spelling of it, beside the runtime's `awaitsAgent`. Which side opened the
  thread does not enter into it. Because it is not an answer, a reading that
  asks whether the request is answered takes the seats out again rather than
  sharing this one. An action's `requires` is one such reading. Where the
  reader is standing is the other: the ring and `c`'s destination say what the
  reader is working, not what they owe, and a widget they are mid-sentence in
  is still the question in front of them. Frozen thread markup seats no
  conversation, so only an action answers there.
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

The same open-list rule binds documentation and package validation. `page catalog`
reads the merged registry and theme idioms. `leaf package check PACKAGE` validates
the package through the same composition gate as `page init`. Adding a twelfth widget
must not require updating a handwritten catalog, renderer branch, CSS tag list, or
prose enumeration.

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
- Look at a composed page after changing the runtime, the theme, or the registry:
  `/ui-sweep`. Green is not the same as looked at. The suite and the render gate
  hold the invariants somebody has already stated, and a widget's spacing against
  its own frame was not one of them — a `choose` group's question shipped set into
  the frame an address column left of its own answers, on a corpus page, read in
  both palettes on every nightly run and toured by `gallery.html`, and stayed for
  three days. Nothing was missing from the corpus and no reading was wrong. The
  skill exists for exactly that class and this is the only thing that points at it.
- Land with `wt merge`, a direct local squash merge to main, never a PR. This
  chooses the landing form, not whether landing was requested. Finished work
  waits for the user's authorization unless the task already granted it.
- A merge dislodged by a newer main may land with `wt merge --no-hooks`, once
  the suite the hook runs has passed locally on this branch. The hook takes
  about as long as main's landing cadence, so re-running it forfeits the race as
  often as it wins, and it is the branch being tested rather than the merge. CI
  runs the same suite on every push to main, which is where a skipped hook is
  recovered. Finish with `git push origin main:main`: `wt merge` fast-forwards
  the local branch and stops there, and its `✗ Can't push to local main branch`
  names that fast-forward failing rather than a remote refusing.
- Sessions load host caches, not the checkout. Both marketplaces install from
  GitHub main. Claude Code keys an unversioned manifest by commit and updates on
  its marketplace sweep. Codex requires
  `codex plugin marketplace upgrade leaf`, followed by
  `codex plugin add leaf@leaf`. A pushed change reaches the next session.

### The suite

The `test_interact_*.py` modules cover lint, vendoring, publishing, catalog,
export, thread markup, and file-side anchors. The `test_render_*.py` modules
cover the browser runtime and examples. Shared file-side fixtures live in
`interact_support.py`. `render_support.py` is the browser-test compatibility
facade: the Playwright harness lives in `render_harness.py`, while the reusable
case corpus is grouped by interaction, layout, navigation, and widget behavior
in `render_cases_*.py`. `test_product_page.py` covers `docs/`. `test_site.py`
builds and reads the published site. The journey test selects a passage,
comments, moves a card, follows a version, and checks the surviving anchor and
log.

The browser corpus is read in both color schemes, and each example is read under
the log it ships, so a thread and any widget a message carries are part of what
the sweeps see. It checks widget upgrades, usable boxes, independent document and
panel scrolling, script-free textarea sizing, control stability under presses and
arriving news, print, and page width on a phone. A second sweep reads each
example as a returning reader with the panel, a tray, or design mode restored.
Every other corpus reading is a first visit, so restoration cannot hide an
arrival regression.

The developer environment comes from `pyproject.toml` and `uv.lock`. Leaf's own
runtime dependencies remain in `interact.py`'s PEP 723 header. Pytest adds
`plugins/leaf/skills/leaf/scripts` to its import path, and tests import the
`leaf` owner modules directly, so the developer environment needs the
same packages.

The everyday suite needs no network after setup and runs one shipped page through
the browser gate:

```sh
uv run pytest tests
```

The `test_render_*.py` modules and `test_site.py` are marked nightly. Broad
discovery leaves them out; an explicit file, node id, `-k`, `-m`, or `--lf`
selection runs what it names. Turn xdist off while iterating:

```sh
uv run pytest tests/test_render_widgets.py -q -n0 -k board
```

After a failure, rerun only the failed cases while debugging:

```sh
uv run pytest --lf --lfnf=none -x -n0
```

Ruff and prettier come from `.pre-commit-config.yaml`. `wt merge` is the complete
suite gate: `.config/wt.toml` runs them and `uv run pytest tests --run-nightly`
once against the rebased tree. The nightly run needs a network: the installed
launcher resolves its own dependencies, Playwright included, through the host's
index rather than out of `uv.lock`. CI repeats both on main and pull requests.

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
serve it in-process with `leaf.http.handler_for(page_dir, token)` after
adding `plugins/leaf/skills/leaf/scripts` to the Python import path, then open the
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

`scripts/vendor-plot.sh` rebuilds
`plugins/leaf/skills/leaf/packages/default/vendor/plot.esm.js`, which draws
`lf-chart`. Observable Plot publishes no entry point a browser can load — its
ESM imports d3 by bare specifier and its UMD build leaves d3 external — so this
bundles the two together, the way the highlight bundle is built.
