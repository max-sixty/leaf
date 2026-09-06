# The page in the browser

This file holds the contracts that cross the browser runtime's modules: what boots in
which order, what the server and the page each own, the registry's grains, the
layer-wide UI laws, the page's own rows (`keyboard/page.js`), what a copy or print
keeps, the render gates, and how to work on the runtime. Everything one module
owns is stated in that module's header comment, and the map below names the owner of
each concern, so read the header before changing the module. Page-authoring commands
and markup rules live in `../references/page-authoring.md`; package authoring lives in
`../references/packages.md`. The repository-level `CLAUDE.md` owns the rules that cross
the JavaScript and Python runtimes, under "Cross-runtime invariants": the document
starts state and the log changes it, each input is validated once and its reading
shared, and the widget vocabulary stays open.

Keep this file about the boundaries between modules. Put an invariant beside the code
it constrains when that code is the only consumer. Put a cross-runtime invariant in the
repository instructions. Do not record the sequence of implementations that led to the
current one.

## Runtime ownership

`leaf.js` is the boot-only browser entry module: every owner is a module that exports
its capability and imports what it needs, and `leaf.js` imports them and runs the boot
sequence (Startup and presentation, below). It exports no capability and no owner
imports it back. The HTTP boundary places the vendored
`runtime/bootstrap.js` before loadable resources, with an exact CSP hash; it can
show startup failure and hear a replacement server even if the module graph or
stylesheet never loads. `runtime/widget-api.js` is the one public
helper surface for behavior modules and reexports capabilities directly from their
runtime owners; an owner never reaches back through the entry module or public facade.

The owners form one import cycle, which fixes what a module body may touch as it
evaluates: its own declarations, a module the cycle does not reach (the
`leaf/evaluation-order` rule in `eslint.config.mjs` computes that set from the import
graph; `context.js`, `registry.js`, `widget-elements.js`, `keyboard/scopes.js` are
examples), and a function declaration of another owner — referenced, never called,
since the callee's own imports may not have evaluated yet. A read of another owner's
part is a mount step under `runtime/chrome.js`'s `mountChrome`, and a value read from
one is asked for at use. The register (`keyboard/scopes.js`) stays outside the cycle
because it owns the repaint frame (`paintHere`) and `leaf.js`, not the register,
imports `standing.js` and registers its painting as the first boot step. The page's
own scope list is built on first use (`keyboard/page.js`: `pageScopes`) because its
members are other owners' constants. Evaluation order is fixed by the import graph
and the same on every page, so a read that breaks this is no error until an unrelated
import edge reorders the walk, and then an uncaught `ReferenceError` at boot on every
page. The browser gate is the guarantee (`leaf version check --render` and the
everyday smoke test read page errors); the lint rule is the early, line-precise word:
it refuses a module-scope read of a cycle binding or call of a cycle function, over the
whole runtime directory whenever a runtime file is committed, and it does not see a
callback another module runs during evaluation.
`runtime/chrome.js` owns the chrome's root, the order its parts stack in, and
`mountChrome`, the one step that puts them in the document and wires what needs them
there;
`runtime/standing.js` owns the one repaint of where the reader stands, in the order
the geometry demands;
`runtime/icons.js` owns the layer's icon table;
`runtime/context.js` owns the mutable facts shared across the browser layers and
their direct readers;
`runtime/deferred-modals.js` holds authored modals outside the top layer until the
first presentation boundary;
`runtime/layer-client.js` owns the vendored-generation gate, shared event and media
POSTs, and page-error channel;
`runtime/traffic.js` owns the delivery ledger — posts and state reads issued and
ended, and the outbox's unresolved attempts — painted on the root element as
`data-lf-traffic` for whatever waits on the page from outside it;
`runtime/requests.js` owns typed one-shot request availability, sending, and the
server-projected request lifecycle watcher;
`runtime/asks/model.js` owns request discovery, folding, and the semantic Ask
subscription;
`runtime/asks/view.js` owns Ask chrome, marking, the Ask walk, and
Ask-local contextual command projection;
`runtime/projection-watch.js` owns the lifetime-bound invalidation subscription shared
by the public semantic projection watchers;
`runtime/composing/capture.js` owns selection capture and snapping;
`runtime/composing/surface.js` owns floating comment geometry and page-click routing;
`runtime/composing/targets.js` owns keyboard item hints and whole-page text search;
`runtime/composing/aim.js` owns modifier aim and captured presses;
`runtime/composing/input.js` owns shared text input, including the thumbnail projection
of pasted page media; `runtime/composing/selection.js` owns selection-composer state;
`runtime/media.js` owns generated image blocks, delivery-route scoping, and the shared
full-image viewer;
`runtime/drawn-edge.js` owns the shared resizable boundary used by the thread panel
and tray panels, landing a new width through `chrome-layout.js`'s `landEdge`;
`runtime/trays.js` owns the left tray edge, active tray, registration, restore, and
shared tray furniture;
`runtime/live-leaves.js` owns the machine-leaves tray's rows, presence words, and walk;
`runtime/living-margin.js` owns the page map, compact map sheet, anchored margin threads,
the design-mode exclusion of its top-layer preview, and the one aggregated Button cluster
for each page target;
content modules contribute live controls and semantics through its registration seam but
never place their own RHS rows;
`runtime/margin-layout.js` owns margin-row measurement, rail claims, responsive docking,
vertical packing, and collision bands for wide page content;
`runtime/reactions.js` owns reaction vocabulary, lists and their standing paint,
sending, keyboard mode, and reaction-specific undo wording;
`runtime/design.js` owns layer-review mode, targets, and legend geometry;
`runtime/data.js` owns external-data acceptance, readiness, and source-contract
subscriptions;
`runtime/drafts.js` owns durable draft generations and cross-tab reconciliation;
`runtime/keyboard/` owns keyboard binding vocabulary and scoped interaction:
`bindings.js` the spelling, parsing, row fields, and checks; `scopes.js` where a group
of rows applies; `dispatch.js` which scope answers a press and what it owes the
platform; `return-stack.js` what a keyboard entry owes on the way back out;
`keyline.js` the short help at the foot of the page and its More control;
`reference.js` the complete listing behind `?`; `address.js` the go-to chord;
`address-placement.js` shared address visibility and the numeric Ask placement pass;
`hints.js` prefix-free transient labels and their no-drop placement pass;
`presentation.js` how a chord row's presses are shown;
`runtime/keyboard/disclosure.js` owns the shared disclosure bindings and the
disclosure watch; `runtime/keyboard/page.js` owns the page's own scopes and rows;
`runtime/notifications.js` owns visual and assistive announcements and the notice
element the banner seats;
`runtime/arrangements.js` owns the browser-state arrangements the arrival gate exercises;
`runtime/outbox.js` owns ordered gesture delivery and accounting;
`runtime/presence.js` owns claim freshness and attendance judgment;
`runtime/state-feed.js` owns state reads, offline handling, the shared clock and deferred retries,
event-stream wakeups, and first-read presentation scheduling and retry;
`runtime/state-application.js` owns stale-answer ordering, application serialization,
state commit, projection, notification, outbox accounting, and rollback;
`runtime/banner.js` owns banner wording, tone, tab-icon paint, and announcing a
status kind that has changed;
`runtime/banner-shelf.js` owns news-control reservation and focus continuity, and
the fold that decides which of the banner's addresses stand on its row and which
stand in its menu;
`runtime/motion.js` owns reduced-motion policy, shared scroll behavior, and
Web Animations playback;
`runtime/markdown.js` owns safe, lazy Markdown rendering for runtime-supplied text;
`runtime/updates.js` owns the accepted claim snapshot and canonical action,
report, and work-claim feeds;
`runtime/version.js` owns version travel whole: the chooser control, its menu and the
newest-version chip, its `g V` destination row and the menu's local `v` scope, forced
live activation,
version-comparison state, its marks and chooser paint, the earlier reading a
marked block discloses, version document loading,
authored-root replacement, the persisted semantic reading landmarks carried across that
replacement, and the page-block reading directional walks start from;
`runtime/widget-upgrade.js` owns widget upgrade guards, data bodies, fail-soft
rendering, and async settlement;
`runtime/widget-elements.js` owns widget-element construction, the response control's
anatomy (`responseAction`), labels, gesture guards, deferred measurement, layout-change signalling, and control sizing;
`runtime/registry.js` owns vocabulary queries;
`runtime/scrolling.js` owns the document scroller identity, relative scroller moves,
fixed-surface wheel forwarding, and the gutter its bar takes;
`runtime/chrome.css` is the comment layer's private stylesheet, a CSS module the boot
module adopts, and keeps the root, body's layout shell, and the chrome's paint hosts out
of the containing-block chain for document-positioned chrome. It also keeps page-attached
paint below covering workspaces and paint for chrome targets above them.
`runtime/marks.css` is the marks' sheet, adopted by the document and by every shadow
stage;
`theme.css` is the default theme: tokens, element styles, class idioms, and the
element-widgets CSS alone renders, with the shadow slice widgets adopt; a package's
`theme.css` is appended after it;
`runtime/resolved-target.js` owns the canonical result of resolving a durable anchor
into the current document;
`runtime/target-paint.js` owns element-target paint in the chrome layer;
`runtime/visual-parts.js` owns the package-declared semantic parts of a rendered
visual;
`runtime/chrome-layout.js` owns comment-panel visibility, chrome geometry, the document
room left after the panel and trays, the final-layout column motion between workspace
states, and page repaint caused by shell motion or reflow;
`runtime/presentation.js` owns runtime paint and the words it projects;
`runtime/reach.js` owns keyboard access to overflow and the containing block a
scroller owes what it scrolls;
`runtime/shadow.js` owns declared shadow roots, their theme slice, shared
highlight rules, the parent walk that crosses a root, and the chrome question
(`uiInside`, `inUi`: which layer a node stands in); `runtime/shadow-stage.js`
owns the stage an x-shadow widget renders into;
`runtime/widget-loader.js` owns registry loading, pre-upgrade passage fences,
dynamic widget imports, and initial settlement;
`runtime/storage.js` owns page addressing and browser-backed stores;
`runtime/syntax.js` owns code tokenization and highlighting;
`runtime/passages.js` owns the DOM reading and quote resolver;
`runtime/text-alignment.js` owns lossless, language-aware whole-text alignment;
`runtime/pointer.js` owns the shared unrounded pointer position;
`runtime/geometry.js` owns the shared readings of visible boxes and clipping, plus the
conversion from viewport boxes to document-positioned chrome;
`runtime/navigation.js` owns reader travel and scroller selection;
`runtime/anchors.js` owns anchor resolution, paint, anchor-specific travel, and
cross-widget projected-datum travel;
`runtime/conversation/model.js` adapts server-projected threads to browser callers;
`runtime/conversation/messages.js` owns message rendering;
`runtime/conversation/replies.js` owns reply drafts, mirrored send state, and delivery;
`runtime/conversation/inline.js` owns conversation seats rendered into the page;
`runtime/conversation/box.js` owns page-seated first-message boxes;
`runtime/conversation/folding.js` owns shared Resolve/Reopen controls and resolution-fold
state and motion;
`runtime/conversation/landing.js` owns conversation input discovery, focus travel,
and panel arrival;
`runtime/conversation/narrowing.js` owns comment-panel search and waiting-on-reader
filter state;
`runtime/conversation/placement.js` owns document-order grouping;
`runtime/conversation/reaction-strips.js` owns the panel's message reaction surfaces;
`runtime/conversation/surfaces.js` owns registry-declared widget outlets and the set of
threads they claim from the living-margin fallback;
`runtime/conversation/thread-card.js` owns retained panel thread cards, their quote
state, and their reply, resolve, and reopen controls;
`runtime/conversation/thread-list.js` owns retained panel list reconciliation;
`runtime/conversation/acknowledgments.js` owns growing acknowledgment receipts and live claim seats; and
`runtime/conversation/reconcile.js` composes panel reconciliation and
`runtime/conversation/panel.js` builds the panel's parts;
`runtime/projection/authored.js` owns typed authored initial values and anchor
parentage; `runtime/projection/data.js` owns keyed runtime-data DOM
reconciliation; `runtime/projection/fold.js` adapts canonical action and report state
to live DOM nodes and the local outbox;
`runtime/projection.js` owns projection reconciliation and undo.

The widget layer loads the vendored
registry, imports modules declared by `x-upgrade`, renders registry-declared
words, and reconciles recorded state. The comment layer listens on `GET /api/news`
for the page's reading, reads `GET /api/state` when that reading moves,
posts to `POST /api/event`, renders the status and conversation chrome, captures
anchors, and handles keyboard navigation. Both layers share the same registry,
passage model, event list, layout readings, and helper surface.

Each mutable fact has one writer:

| Fact | Authority | Browser writer |
| --- | --- | --- |
| authored widget state | markup after widget upgrade, before projection | `captureAuthoredFacets` reads typed initial values; `rememberAuthoredParents` preserves pre-upgrade anchor parentage |
| external data | the latest accepted page data revision | `receiveState` replaces current values and retained captures; `watchData` delivers the authored current-or-snapshot selection to widget modules |
| projected data | an external snapshot or other records the widget is currently given | `projectData` reconciles their keyed rendering; the DOM does not become another record store |
| version shown by the live document | the latest mapped revision accepted at the activation boundary | `activateRevision` advances `runtime.currentRevision`; a public version address derives the version number from its URL |
| accepted history | the server event log | `receiveState` replaces `events` after a complete read |
| the reading the page has applied | the server's `/api/state` answer | `receiveState` writes `runtime.reading` and paints `data-lf-reading` |
| unresolved browser work | the ordered `outbox` | `post` adds, `accountOutbox` and `releaseProjectedOutbox` remove |
| rendered semantic state | authored state, log projection, then outbox overlay | `reconcileState` |
| proof of what the DOM currently represents | `committedProjection` | `stageOutboxAction` and `reconcileState` |
| anchor paint | thread and composer anchor records | `paintAnchors` |
| where each thread's passage lands | this version's resolution of its anchor | `paintAnchors` writes a rich `placed` record with its element, exact datum, and exact/fallback/outdated status |
| widget-local Thread placement | exact projected-datum placements plus the widget's current layout | the conversation surface coordinator asks each declared adapter for an outlet, then records the threads it claimed before the living margin reconciles |
| reader acknowledgment and local agent work | the canonical acknowledgment projection plus typed claims in `status.work` | `paintAcknowledgments` paints conversation-local fallbacks; the living margin maps page subjects onto their existing Target Button without becoming another store |
| composer visibility | `composerOpen` and `fabAnchor` | `showComposer` and `showFab` |
| panel visibility | `panelOpen` | `setPanel` |
| the narrowing on the thread list | the reader's find words and waiting-on-you press | `renarrow` and `widen` |
| how much of the thread list's top a pinned heading covers | the tallest `.lf-pinned` box as rendered, while the panel is open | `paintHeadRoom` writes `--lf-head-room`, called by `renderThreads` and by a `ResizeObserver` on the list |
| the thread list's viewport position through reflow | the live reference card in the open panel | `renderThreads` and the held `paintAcknowledgments` call preserve it through reconciliation, provisional work, and resolution folds |
| where the thread holding the focus stands in the list | the band the list declares landable through `scroll-padding` | `threadsBox`'s `focusin`, and its press through `pointerdown`/`pointerup`; `stepThread` for a key press that moves no focus, `landIn` for the box it puts the reader in, `placeThreadEdge` for an explicit edge placement, and `showThread` for a deliberate arrival |
| tray visibility | `trayUp` | `showTray` writes reader gestures; `restoreTrays` loads saved intent and `restoreTray` paints it at presentation |
| region width the reader drew | the reader's store, per edge | `drawnEdge`'s `set` and `restore` |
| keyboard meaning | registered scope and row objects | the dispatcher and each visible key surface read the register |
| draft generation | the reader's draft record | draft-store helpers and `watchDraft` |

Do not add a second cache, pending map, widget-specific replay list, or DOM
attribute as another source for one of these facts. A rendering may expose state,
but callers do not read the rendering to recover it. For example,
`style.display` does not answer whether the composer is open, and a focus ring
does not remember where an Ask walk last landed.

## Startup and presentation

Startup order is load-bearing:

1. Register the standing painter into the register's repaint frame, adopt the chrome
   and marks sheets, and mount the chrome (`mountChrome`: the banner's arrangement,
   the parts into the document, the banner's reservations, then every owner's wiring
   of another owner's part).
2. Begin the first state read without applying its answer.
3. Restore the reader's arrangement from storage, and let focus go to the page.
4. Fetch and validate the registry.
5. Index passage fences and authored parent identities before upgrade changes the DOM.
6. Import the modules declared by `x-upgrade` for the tags this document
   contains, and no others.
7. Wait for module settlement, then run the shared dressing passes.
8. Capture authored record facets from the upgraded, authored state.
9. Mark `body` `data-lf-upgraded="1"`.
10. Start the state feed; its first answer is applied, reconciled, and presents the
    page.

Authored HTML paints immediately on every page. Its prose, ordinary links, scrolling,
and layout remain usable while widgets upgrade and the first state read is pending.
`data-lf-presented` does not release paint: it releases recorded widget actions and
authored top-layer UI once the first state read has either applied or established that
the server is unavailable. Modules must consult `actionAvailable` or
`requestAvailable` before optimistic mutation as well as before sending; their common
send doors repeat the check. Fixed status and unanchored discussion chrome remain usable
while a live page waits; selecting a passage does not raise the anchored composer until
the passage has survived the first projection.

`presentPage` owns the one transition from arrival to stateful interaction. Motion
helpers and the stylesheet collapse arrival animations until that boundary, and the
stylesheet withholds only dialogs and popovers rather than the authored document.
After it, a state change may animate only where motion helps the reader follow a
change. A failed startup does not stamp the page presented as if it had read the
log.

## What crosses to the server

The server does not retain refusal receipts. The condition behind a refusal can change
without the reader changing the words: a referenced revision can be activated, a parent
thread can arrive, or a layer can be re-vendored. Caching the refusal would strand a
valid draft behind an obsolete answer.

Interactive event `markup` has a different door from every other field: only the CLI
can write it, after validating it against the vendored registry, while the browser
event schema refuses it.

## Authoritative projection

The projection's inputs, coordinate, and views are `runtime/projection/fold.js`'s;
Python derives the durable side (below). What both must honor: an `x-state` verb may
declare `requires`, a prerequisite over the standing Ask projection that
`x-awaits` defines. Its target is the sender or its
declared parent, and `awaiting` states whether that Ask must be open or closed.
`actionAvailable` paints and guards the action, `sendAction` checks at the common
browser door, and POST evaluates the same declaration from the authoritative log
under the append lock. No eligibility cache sits beside the ordinary Ask and state
projections. `x-awaits.answers` says which actions actually close the Ask;
orthogonal actions do not, and neither does a conversation standing in the widget's
declared `x-conversation` seat — that takes the Ask off the reader's list without
answering it, which is why this gate reads the projection with no seats in
it. An answer with a position record may declare
`completion: {empty: {within, when}}`: POST applies the candidate position to the
authoritative holder relation and admits it only when the one matching item container
inside the answering widget is empty. The same predicate decides whether a standing
record answers the Ask, so no private completion flag can diverge from the durable
arrangement. An answer or thread-completion verb cannot require its own awaiting value, or
an aggregate parent's awaiting value, to be false: either prerequisite is circular
while the Ask stands. `x-awaits.rollup` carries the logical OR of its nearest
local Asks and child roll-ups in Python; the aggregate owner never originates
or surfaces an Ask. The
browser receives the resulting ids and awaiting values.

Python's `state_projection` is the durable derived view. Under the same page
transaction as `/api/state`, `browser_state` serializes its classified events and
winners, Asks, conversations, updates, undo candidates, receipts, and coverage at
one `through_seq`. A normal response projects the revision the tab shows and the
active revision it may install next. A version comparison requests its older base
from `/api/view` at the exact `through_seq` already applied to the live DOM, so every
view used together has the same sequence basis without every state read parsing all
historical revisions. Page coordinates use that revision's document window;
conversation coordinates use the unbounded frozen-markup window.

`awaitsReader` first reads any standing local `x-awaits` or `x-request.ask`
Ask carried anywhere in the unresolved thread; a later plain turn does not hide
an earlier structural Ask. With no such Ask, it reads the latest spoken turn:
an agent comment is a question and an agent reply's explicit `awaits` field marks a
prose request. A `settles` token standing on that latest prose request answers it
without closing the thread.

### Version and conversation windows

A page widget's projection stops at the revision the tab shows (`runtime.currentRevision`). Later actions and reports belong to
documents written after this version. A widget instantiated inside frozen thread
markup is in chrome and reads the whole action sequence because the conversation,
not a page version, owns it.

The server projects threads from the whole log, so a conversation stays current
on a pinned page even when the document projection remains historical.
Registry-declared `x-conversation` seats show an exact-section
textual view while the owner exists in the current document. A declared
`x-thread-surface` may instead seat the complete shared Thread view beside an exact
projected datum. The widget owns only the outlet's layout and visibility; core owns the
messages, replies, reactions, settlement, receipts, focus, and fallback. The living
margin carries a thread while no widget claims it, and the Threads panel remains the
complete index. A root
declared with `response: {kind: version, verb: <answer>}` keeps that exact-section
view text-only and refuses an agent reply because the next authored version is its
response. Dropping the owner drops only the inline seat.

`restated` and answered-report relations persist through version notes. The note
records the version floor for each affected id or report event; silence in a
later version does not revive retracted state. Python's projection uses
containment, not a global id lookup, when deciding which detailed parts an action
rests on.

An Ask the reader answers with a request for change is answered by a version, not
a reply (`runtime/asks/model.js` reads the seat): authored state in a later
version must answer an originating open Ask, or change the declared answer when
the Ask was already answered; a reader action in the log cannot substitute for
that revision. Only then may the agent resolve the thread that carried the request.
Threads owns the reader-facing clarification; the page's Ask remains the proposal
with the agent rather than counting both.

## The widget vocabulary stays open

`registry.json` is the layer contract shared by rendering, validation, agent
queries, event parsing, replay, and export. Core code may name a widget only when the
widget is part of how Leaf itself works. Content widgets remain anonymous
outside their module. The test for a general mechanism is whether another widget
family can join by adding its entry, module, and theme rules without editing a
consumer.

The registry has two grains. A tag entry is one complete schema and later layers
replace it whole. A `$` entry is a shared namespace and layers merge its members.
Shared facts such as languages, tones, idioms, and event definitions belong
under `$languages`, `$tones`, `$idioms`, and `$events`. A consumer reaching into
some named widget to find a layer-wide list is reading the wrong owner.

The extension keys describe general behavior:

| Declaration | Meaning to the layer |
| --- | --- |
| `x-upgrade` | import this tag's module |
| `x-content` | the element contains prose, items, data, or no authored content |
| `x-children` | fixed item roles: exactly one direct child for every value of a required child enum |
| `x-inline` | the widget stands in an inline run |
| `x-measured` | authored scalar words are pinned at an instant to one live data input; checks compare that instant with the source's latest update |
| `x-says` | named attributes are visible words at declared edges |
| `x-paints` | named attributes communicate facts through paint and need a quiet spoken reading |
| `x-verbatim` | authored data must agree with the rendered words |
| `x-shadow` | a declared open shadow tree is part of the page's composed reading |
| `x-state` | reader action verbs, current eligibility, facets, units, schemas, and records |
| `x-report` | report verbs with the same semantic state shape |
| `x-request` | direct-child command offers, typed one-shot external-operation verbs, and whether a ready lifecycle is an Ask |
| `x-refers` | element-id attributes and optional package-owned map predicates that type their targets |
| `x-parent` | the child widgets whose state and Ask membership belong to this holder |
| `x-retired-when` | outcome-to-slot retirement relations |
| `x-withdrawn-as` | the author's state for a withdrawn recordless decision |
| `x-ask-surface` | the complete reading and arrival region around one nested Ask source |
| `x-awaits` | the condition, explicit answer verbs, and optional nested roll-up for an Ask |
| `x-conversation` | the condition under which the widget owns a conversation seat, and whether its root requires a version response |
| `x-thread-surface` | the upgraded widget may provide local outlets for complete Threads anchored to its exact projected data |
| `x-work` | admits local agent work without a pending reader move, through a content or conversation seat and optional condition; an admitted page-widget claim then appears at the page edge through its Target Button |
| `x-exhibit` | this occurrence is evidence, not an actionable live widget |
| `x-wide` | whether width follows a box or a drawing |

Use the exact current `$keys` descriptions and schema when editing an entry.
This table states ownership, not a replacement schema.

Booleans are appropriate only when the false case has one clear meaning.
`x-wide` uses values because a box and a source-sized drawing answer different
width questions. A fact that needs distinct behavior should carry those named
values instead of hiding one widget's policy in `true`.

### Data projections

Where records come from outside the document, their authority is `data.json`: one
page-owned store with a replaceable current value and retained immutable captures.
`$data.contracts` declares reusable meanings and schemas. A widget's `x-data` names the
contract, the attribute carrying this page's concrete source id, and optionally an
attribute selecting one capture by data revision. `leaf data set` validates and
atomically replaces the current value. `leaf data capture` reads a UTF-8 file; text
captures may slice an inclusive line range, while an explicit format may transform the
file into a contract-shaped value. Both replace current and retain the value under the
new data revision.
Neither command appends an event or runs package code, and capture stores no source
path. Each stored source retains its contract even after clear, so re-vendoring never has
to infer meaning from a source's spelling.

A source id keeps that contract across every stamped version and widget frozen into
a thread. Bindings without a snapshot selector read current; durable documents may
select a retained capture. Clearing removes current and unreferenced captures but never
releases the id for a new meaning. Re-vendoring must preserve the page-lifetime binding
and every standing selection. `page state` exposes those bindings and consumers to
producers.

### Passage fences

The Python reader can model only transformations declared by the registry. A
widget whose module changes text in a way the file cannot reproduce is fenced.
`rememberPassageParts` indexes these boundaries before upgrade, and browser
capture clips context to the same declared boundary after upgrade. A selection
crossing a fence is not captured as a quote the file cannot later confirm.

Do not broaden the Python reader by guessing a module's DOM. Declare modelable
words with `x-says`, `x-paints`, or the appropriate content key. Keep the widget
fenced when its transformation cannot be represented faithfully.

`coveredWords` is the render gate for text that is present in a browser reading
but unavailable to the reader because of clipping, hiding, generated chrome, or
another boundary. Keep the runtime's generated markers and the gate's exclusions
in agreement.

## Layout and motion

The page must hold still under the reader's aim. A state change may repaint any
box, but it must not move controls adjacent to the gesture that caused it. News
arriving without a gesture must not move any chrome control. A content change
the reader requested may reflow the content it replaces, provided the change is
shown as trackable motion rather than an unexplained jump.

Control state is paint: ink, fill, border, or an inset ring. Do not express it by
changing font weight, size, padding, border width, or another metric. Reserve
space before a label changes or a generated control appears. `reserve` measures
all enumerable labels in the control's current font and sets a minimum width.
Re-measure after changing type tokens; avoid numeric reservations where the
possible words are available.

## Keyboard, focus, and navigation

One register defines every runtime and widget key. A row binds keys, states what
the press does, decides when it is live, and runs it. A scope says where a group
of rows applies and which platform keys that context claims. The dispatcher,
key line, `?` reference, control tooltips, and announcements are projections of
those objects.

Treat that register as a product grammar, not a collection of locally convenient
shortcuts. Before adding or changing a binding, survey the complete register for
meaning, scope, native overlap, entry and exit symmetry, and focus restoration.
Document every inconsistency the survey exposes in the task handoff. If the rules
here do not settle one, escalate it to the user before choosing locally; the
absence of a dispatch conflict does not make a binding precise.

### Page scope rows (keyboard/page.js)

The register owns capabilities, not controls. Every capability the chrome offers
has a row, and each control that reaches one is named by `control`; a
control is a route to a capability rather than a capability of its own, so a
second route needs no second row. A run heading in the thread panel presses the
page to where that run is about. That travel is a capability, just as `w` and `/`
are capabilities nothing else reaches, and each earns a row. A capability with
no row is one the key line never advertises,
the reference never lists, and a reader working from the keyboard never finds,
because those three are projections of the register. Add the row in the change
that adds the capability.

Directional category walks use the category's letter, with case stating direction:
lowercase advances and Shift goes back. `t`/`T` walks open threads and `a`/`A`
walks open asks. Both walks clamp at their first and last items. Keep these as single-key
presses rather than prefix sequences; a walk is often repeated or held. While the reader
stands anywhere in an Ask, its widget's
ordered actions keep a canonical binding where they declare one and otherwise take the
next free `1`–`9`. Core projects that exact list into the key line and visible control
chips. Each action is a command route; that route is the one
binding-to-control identity used by dispatch, the reference, the key line, its address,
and `aria-keyshortcuts`; core does not mint a second identity for the projection. Tab
walks the real controls without replacing that action map;
a control's scope adds only its native or local mechanics. `j`/`k` scroll
down/up by 60 pixels; `d`/`u` move 60% of
the reading page. Both follow the active region, share a quick glide, and jump under
reduced motion. Native Space stays with the platform and focused controls. Other letters come
from words the surface says: `w` narrows to threads waiting on the reader, while the
the Go-to chord (`keyboard/address.js`) uses case to separate complete destinations from numbered
lists. A key spelling something nothing on screen says is a key nobody reaches for twice.
Approval spends no fixed page letter: its visible button stays in the Tab order and takes
native Enter or Space, while the Ask-local list gives it a contextual binding. In particular,
a conditional chord mnemonic must not share its final key
with a page action, or a dead destination can fall through into a different operation.

`c` is reserved for commenting. Enter keeps native activation, submission, or the
focused control's local continuation. A page option mark is a checkbox and toggles with
Space or its Ask digit; it gives Enter no second meaning. The Another option field is an
ordinary Tab stop, and Enter submits once that field holds focus. In a thread there is no
second add form, so Enter from its option mark continues into the thread's existing reply.

A row whose press turns a mode on and off states the mode rather than the toggle.
`does` and `line` are functions of whether it stands, so the sentence says which
way this press will go. When turning it on is an entry, its `returnFrame` states
Escape's inverse rather than a second row guessing from the resulting scene.

Which scope a row belongs to follows from what its press acts on. The page holds
the presses whose subject is the page: `/` searches its text, `s` names its visible
items, `c` comments on it, `t`/`T` and `a`/`A` walk its open sets, `j`/`k` and `d`/`u` move its
reading, and `g` opens its destinations. A surface holds the presses
whose
subject is that surface's own
contents, because contents the reader is not looking at are not a thing to act
on: `w` narrows the thread panel's list and `/` searches it, and both live in
`PANEL`. The page's alphabet is small and every letter spent there is spent on
every page, so a letter earns page scope only by acting on the page.

A surface may also hold the contextual form of a page intent. `c` always means
comment; its destination follows what the reader is standing on. From the Threads
list the panel row enters the page-comment box. Everywhere the page has a nearer
answer—a selection, item, or conversation—the page row enters that box instead.
The rows are mutually exclusive, so the register never asks the reader to choose
between two meanings for `c`.

That the page row reaches into Threads is not an exception. Page scope already crosses
there: `t`/`T` can land on cards in Threads, and `a`/`A` can land on an ask an agent
sent inside a thread. A page key that takes the reader somewhere owes them an answer
once they are standing there. The destination, label, command, and return frame all
come from `commentDestination`, so the same contextual reading governs every projection.

The destination is the anchor the 💬 carries, then the open thread the reader is
in or the single inline thread held by a pressed Page-map marker, then the item they are
standing in, and, when none of those is in hand, the page-comment box.
`commentDestination` decides it once and states the
sentence, return frame, key line and press together, so the reference, the line,
what happens, and the way back cannot come to spell it differently. The pointer's answers outrank
the standing: a selection or a raised 💬 is the more recent thing the reader
said. `standingItem` and `standingConversation` are what "standing" means here,
and **Standing somewhere** below owns that reading.

The page-comment box lives in the Threads panel, but entering it does not mean “open
Threads”: `g T` owns that destination and lands on the list where `w` and `/` remain
reachable. `c` opens the panel only as the implementation container its requested box
needs, focuses the cursor immediately, and records the prior workspace in one frame.
Escape therefore returns directly to the exact prior control or reading place. From an
already-entered Threads list, `c` adds one nested frame and Escape returns to that list.
A resolved thread has no reply box, so the general box is the honest contextual answer.

The item's box is the composer, on the item, and not a widget's own conversation
seat even where it has one. `commentOnTarget` writes the anchor `renderConversations`
collects, so the remark lands in that seat's conversation by either route; reaching
into the seat instead means escaping an author-written id into a selector, asking
whether the box can take focus, and choosing among the boxes a seat holds once it
carries threads. One route answers those by not asking them.

`LINK` and `DISCLOSURE` describe the platform controls a reader may land on and the
immediate word for their next press. A fold reached by a generated hint lands on its
summary after opening it; a link reached through Tab still says that Enter follows it.
A summary says whether it will open or close from its current state. This avoids one scope per
native tag while keeping the next press visible.

### Standing somewhere

A press that acts on where the reader is standing reads it through
`standingItem`: the unanswered Ask where focus is on a control that works it — a
pick, a ✓, a mark — an answered Ask on its explicit review arrival, and the
innermost item everywhere else, which is the ⌥ aim's own reading. It answers nothing
in ordinary chrome, where a reader is working on the page rather than standing in it.

## Standalone copies and print

`version export` produces the already-upgraded DOM, drops scripts, and marks the
root `.lf-copy`. Anything meant to survive must be present in markup and CSS.
Module handlers do not survive.

Widget affordances fall into three groups:

- A control whose state and behavior are native HTML and CSS may remain
  interactive in a copy. `lf-shot` uses a serialized checkbox state.
- Generated controls that require JavaScript are stripped or disarmed. Export
  removes their runtime tab stops and roles while preserving labels declared as
  page words.
- Module-specific visual affordances guarded by live script exist only under
  `html:not(.lf-copy)`.

Projected data is a fourth question with a different answer: a copy keeps the current
`projectData` rendering, including its projection and datum labels, but loses the
module that could refresh it. It is therefore a labelled snapshot, not a live
projection.

`test_an_exported_page_fixture_stands_on_its_own` strips scripts, opens the copy, and
asks what still looks actionable. Keep that end-to-end test general rather than
asserting one widget's exported implementation.

## Render gates

`leaf version check <page> --render` is the browser contract. It re-vendors
before loading, runs both color schemes, waits for the runtime's actual readiness
and finite motion boundary, reads screen and print, and reapplies standing state.
A local browser check is required after changing `leaf.js`, a runtime owner, a widget
module, the registry, or the theme.

The named JavaScript exports in `leaf/render-checks/index.js`, invoked by
`leaf/render_checks.py` and composed by `leaf/render_gate/`, each answer one failure
class. That facade is `leaf/render-checks/index.js`; its directory groups runtime,
reachability, layout, replay, word, widget-contract, and framing probe owners. The
served graph imports the public widget API statically, so the JavaScript parser and
module loader validate its syntax, dependencies, and named exports.
`coveredWords` is reexported from the import-free `render-checks/standalone.js`, which
lets the same implementation inspect an exported `file://` copy after its runtime has
been removed. `render-checks/init.js` installs the pre-navigation window-error channel.

| Reading | Contract |
| --- | --- |
| window-error init channel | no runtime, module, resource, or ResizeObserver error reached the page |
| `upgraded` and `moving` | upgrade completed and final geometry settled |
| `invalidPaints` | every var()-backed SVG paint resolves to a valid value in each scheme |
| `tinyBoxes` | every declared widget has a usable rendered box |
| `unmarkableItems` | every pointable item has a visible part for an outline |
| `misplacedBoxes` | boxes stay in the column or in genuinely reachable overflow |
| `squeezedTables` | a table scrolls sideways only with every column at its longest unbreakable run |
| `withheldRoom` | a drawing scrolls only when the room, net of margin residents at its band, ran short |
| `clippedControls` | actionable controls are visible and reachable |
| `unreachableWords` | visible page words remain in reachable flow |
| `coveredWords` | browser words are not silently clipped, hidden, or claimed by chrome |
| `unreadSyntax` | syntax highlighting does not erase or alter source words |
| `silentWords` | `x-says` and `x-paints` promises reach the composed rendered page |
| `undeclaredAttrs` | modules do not write undeclared author-namespace state |
| `retiredSlots` | declared settlement marks and retired-slot visibility agree with the projection |
| `trappedMargins` | framed boxes show only their declared inset |
| `paperWords` | print keeps every page statement and removes only affordance |
| `replayOverrides` | the log, not conflicting authored markup, determines projected state |
| `relativeReplays` | rendering each complete widget state twice changes nothing |

`standingState` and `shallowSigs` are exported by their projection owner through the
widget API for these gates. Keep their
readings aligned with the runtime's projection and authored-state definitions.
Do not create a test-only interpretation of a widget's state.

The static check and browser gate cover different boundaries. Static validation
owns schema, ids, nesting, stable passages, event shapes, restatements, and file
readings. The browser owns computed layout, composed trees, module writes,
focusable controls, screen/print agreement, and replay idempotence. Put a check
on the side that can observe the fact.

Named journey tests retain behaviors that a generic render reading cannot drive:

- `test_a_refused_attempt_is_re_read_against_the_page_that_refused_it` covers
  refusal without a durable receipt.
- `test_a_reader_arrives_at_what_they_left_rather_than_watching_it_arrive`
  covers every `ARRANGEMENTS` restore.
- `test_a_page_nobody_has_touched_scrolls_from_the_keyboard` covers the initial
  focus handoff to `body`.
- `test_a_commented_block_says_so_to_a_screen_reader` covers the accessible
  comment note without polluting the passage.
- `test_refused_recorded_actions_restore_from_the_log_and_surviving_outbox`
  covers rejection against authoritative history plus later local overlays.
- `test_a_foreign_edit_waits_for_a_live_draft_and_replays_in_order` covers a
  deferred editor correction.
- `test_authored_page_paints_but_durable_controls_wait_for_first_replay` covers
  the split between immediate authored paint and the later semantic-interaction
  boundary rather than only the two readiness stamps.

Keep causal fixtures narrow, but retain a distinct case when only a real gesture,
state read, reload, second tab, storage fault, shadow root, print medium, or
animation can expose the behavior.

## Working on the runtime

Run `node --check` on the module, formatting, and a focused real-browser test while
iterating. A module that reads another owner as it evaluates parses and lints clean and
fails only in the browser, as `Cannot access X before initialization` at boot; the
rule and its remedies are under Runtime ownership above. Before handing over a runtime or theme
change, run the relevant full browser file or `leaf version check --render` on
the affected example. `node --check` cannot validate browser bindings, computed
layout, or reconciliation; the layer tests parse every vendored stylesheet.

Re-vendor a page before trusting its browser result. A page directory carries
the runtime, registry, modules, vendor files, and theme copied by `page init`; a
page not re-vendored is testing an older layer.
