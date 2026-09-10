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

The boot module constructs owners with explicit capabilities before mounting them.
These constructors retain their dependencies; their mounts install listeners and begin
reads that need the other owners. Pure projection, conversation, and pending models fold
supplied records without importing DOM or application services. Renderers receive the semantic commands they use instead of importing the
application, delivery, or undo owner. Keep these boundaries transitive: an intermediate
helper must not restore a forbidden dependency. The public widget facade is the boundary
for authored behavior modules, not an internal shortcut between runtime owners.
The keyboard register stores declarations without evaluating their dynamic readings;
the first repaint after mounting evaluates them.
The lint gate rejects cycles, forbidden transitive dependencies, and missing module
names in its boundary declarations. Runtime imports use literal paths so the gate can
read their edges. Only the authored interaction loader and registry widget loader use
computed imports; those load content modules rather than runtime owners.
`runtime/chrome.js` owns only the shared chrome root; `leaf.js` assembles its parts,
mounts them, and wires behavior that needs them in the document;
`runtime/auxiliary-modality.js` owns the shared inert, scrim, focus, semantic, and
reading-scroll boundary while an auxiliary surface covers the document;
`runtime/repaint.js` owns the shared frame, whose fixed phases are wired at boot:
first keyboard-scope reflection, standing content, chrome layout, requested page
movement, then standing geometry. Work requested during a phase belongs to the next
frame. Synchronous input layout, ResizeObserver height-only placement, and the shell's
animation frames retain their own timing contracts;
`runtime/standing.js` owns the standing content and geometry phases;
`runtime/dom-children.js` reconciles retained children without moving nodes already in
place; conversation owners supply reaction teardown when removing their surfaces;
`runtime/focus.js` places focus on destinations, lending a tab stop only when needed;
`runtime/anchor-coordinate.js` compares anchor records without resolving DOM;
`runtime/walk-position.js` owns the transient ordinal for semantic Leaf keyboard walks,
shown in the useful status at the page foot, and the brief boundary state when another
press stays at the same destination; clamped and cyclic owners use the same reading, while
native focus traversal and gestures that rearrange state keep their local feedback;
`runtime/icons.js` owns the layer's icon table;
`runtime/context.js` owns the mutable facts shared across the browser layers and
their direct readers;
`runtime/native-layers.js` owns the browser's modal-dialog and popover order across the
document and declared shadow roots, including the modal floor beneath a nested popover;
`runtime/deferred-modals.js` holds authored modals outside the top layer until the
first presentation boundary;
`runtime/layer-client.js` owns the vendored-generation gate, shared event and media
POSTs, and page-error channel;
`runtime/traffic.js` owns the delivery ledger — posts and state reads issued and
ended, and the pending ledger's unresolved attempts — painted on the root element as
`data-lf-traffic` for whatever waits on the page from outside it;
`runtime/requests.js` owns typed one-shot request availability, sending, and the
server-projected request lifecycle watcher;
`runtime/asks/model.js` owns request discovery, folding, and the semantic Ask
subscription;
`runtime/asks/view.js` owns Ask chrome, marking, the Ask walk, and
Ask-local contextual command projection; `asks/view-elements.js` owns its passive paint
host and control selector;
`runtime/projection-watch.js` owns the lifetime-bound invalidation subscription shared
by the public semantic projection watchers;
`runtime/composing/capture.js` owns selection capture and snapping;
`runtime/composing/surface.js` owns floating comment geometry, addressable-element comment entry,
and page-click routing;
`runtime/composing/target-chooser.js` owns keyboard target hints and whole-page text search;
`runtime/composing/aim.js` owns modifier aim and captured presses;
`runtime/composing/drawing.js` owns one-stroke pointer capture and drawing commands;
`composing/drawing-record.js` owns drawing payload shape and validation; `composing/drawing-paint.js` owns their
projection into the page;
`runtime/composing/input.js` owns shared text input, including the thumbnail projection
of pasted page media; `runtime/composing/selection.js` owns selection-composer state;
`runtime/media.js` owns generated image blocks, delivery-route scoping, and the shared
full-image viewer;
`runtime/drawn-edge.js` owns the shared resizable boundary used by the thread panel
and tray panels, landing a new width through `chrome-layout.js`'s `landEdge`;
`runtime/trays.js` owns the left tray edge, active tray, registration, restore, and
shared tray furniture;
`runtime/live-leaves.js` owns the machine-leaves tray's rows, presence words, and walk;
`runtime/margin-entries.js` owns the public margin-entry grammar and contribution
registry; content modules contribute live controls and semantics there but never place
their own RHS rows;
`runtime/page-map-dialog.js` owns the complete searchable Page Map dialog, its retained action
proxies, filtering, modal lifecycle, and focus return;
`runtime/margin-projection.js` projects those contributions with page readings into the page
margin, supplies the Page Map entries, and owns anchored margin threads, the design-mode
exclusion of its top-layer preview, and one aggregated cluster for each page target;
`runtime/margin-layout.js` owns margin-row measurement, rail claims, responsive docking,
vertical packing, collision bands for wide page content, and transient margin-entry
label placement;
`runtime/reactions.js` owns reaction vocabulary, lists and their standing paint,
sending, keyboard mode, and reaction-specific undo wording;
`runtime/design.js` owns layer-review mode, targets, and legend geometry;
`runtime/design-readings.js` owns its passive names and constants;
`runtime/data.js` owns external-data acceptance, readiness, and source-contract
subscriptions;
`runtime/drafts.js` owns durable draft generations and cross-tab reconciliation;
`runtime/keyboard/` owns keyboard binding vocabulary and scoped interaction:
`bindings.js` the spelling, parsing, row fields, and checks; `scopes.js` where a group
of rows applies; `register.js` the declared page scopes; `dispatch.js` which scope
answers a press and what it owes the platform; `controller.js` the physical key listener
and mode transitions; `text-entry.js` the input and composition readings; `return-stack.js` what a keyboard entry owes on the way back out, using the
origin its caller captured before executing the command;
`shortcut-bar.js` the short help at the foot of the page, its More control, the useful
status opposite it or stacked above it when room is tight, and the shared reading of
their rendered boxes;
`command-reference.js` the complete command listing behind `?`; `go-to-sequence.js` the Go-to sequence;
`key-badge-placement.js` shared target visibility and the numeric Ask key-badge placement pass;
`hints.js` prefix-free transient labels and their no-drop placement pass;
`presentation.js` how a sequence row's presses are shown;
`runtime/keyboard/disclosure.js` owns the shared disclosure bindings and the
disclosure watch; `runtime/keyboard/page.js` owns the page's own scopes and rows;
`runtime/notifications.js` owns visual and assistive announcements and the notice
element the bottom status seats;
`runtime/restore-state.js` owns the browser-state arrangements the arrival gate exercises;
`runtime/reading-regions.js` owns reading-region identities, effective scrollers,
allocation and bounded/flow posture transitions;
`runtime/reading-layout.js` owns shared arrangement construction and furniture slots
used by structural and compound widgets, plus the page-room observation lifecycle that
root workspaces apply to their own minimum-size policy;
`runtime/pending/model.js` owns pending-record readings; `pending/state.js` owns the
ordered gesture ledger, with no network or rendering dependencies;
`runtime/delivery.js` owns serialized event delivery and retry, independently of whether
an accepted answer can be rendered;
`runtime/application.js` composes delivery, state application, projection, conversation,
and the pending ledger. Its command path enqueues, stages, and paints a gesture before
starting delivery;
`runtime/presence.js` owns the calibrated server clock, relative-time wording,
and the deadline at which canonical activity asks for another server read;
`runtime/state-feed.js` owns state reads, offline handling, the shared clock and deferred retries,
event-stream wakeups, and first-read presentation scheduling and retry;
`runtime/state-application.js` owns stale-answer ordering, application serialization,
state commit, projection, notification, pending accounting, and rollback;
`runtime/banner.js` owns banner wording, tone, tab-icon paint, and announcing a
status kind that has changed;
`runtime/banner-shelf.js` owns news-control reservation and focus continuity, and
the fold that decides which of the banner's controls stand on its row and which
stand in its menu;
`runtime/motion.js` owns reduced-motion policy, shared scroll behavior, and
Web Animations playback;
`runtime/interaction-gallery.js` and `runtime/interaction-gallery-frame.js` own the
Product Gallery's opt-in, ephemeral interaction replays, playback controls, and the
contained frames those replays run document-global chrome in. `data-lf-contained` marks
both sides of that boundary — the frame element out in the gallery and the body of the
page inside it — and a contained page is a picture rather than a place to stand: it
arrives restoring none of the reader's arrangements and placing no focus, and it leaves a
standalone copy with the scripts. Its body is written `inert` for the same reason: a
document tree has one focus, so the chrome a replay drives must not be able to take the
reader off the page they are standing on, and an inert subject ends a shown dialog's
focusing steps before they reach anything;
`runtime/markdown.js` owns safe, lazy Markdown rendering for runtime-supplied text;
`runtime/updates.js` owns the accepted claim snapshot and canonical action,
report, and work-claim feeds;
`runtime/version.js` owns version travel whole: the chooser control, its menu and the
newest-version chip, its `g V` destination row and the menu's local `v` scope, forced
live activation,
version-comparison state, its marks and chooser paint, the inline text diff a
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
module adopts, and keeps the chrome's paint hosts out of the containing-block chain for
document-positioned chrome. It also keeps page-attached paint below covering auxiliary surfaces
and paint for chrome targets above them.
`runtime/marks.css` is the marks' sheet, adopted by the document and by every shadow
stage;
`theme.css` is the render-blocking default theme: the live shell's final page claims,
tokens, element styles, class idioms, and the element-widgets CSS alone renders, with the
shadow slice widgets adopt; a package's `theme.css` is appended after it;
`runtime/resolved-target.js` owns the canonical result of resolving a durable anchor
into the current document;
`runtime/target-paint.js` owns element-target paint in the chrome layer;
`runtime/visual-parts.js` owns the package-declared semantic parts of a rendered
visual;
`runtime/chrome-layout.js` owns chrome geometry, the document room left after the panel
and trays, the final-layout column motion between auxiliary chrome states, and page repaint
caused by shell motion or reflow;
`runtime/thread-panel.js` owns panel visibility and workspace transitions;
`runtime/auxiliary-chrome.js` captures and restores the reader's workspace for navigation;
`runtime/presentation.js` owns runtime paint, optional page-interface settlement, and
the words it projects;
`runtime/reach.js` owns keyboard access to overflow, the containing block a
scroller owes what it scrolls, and the mark a box wears while it shows less
than it holds across;
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
`runtime/navigation.js` owns reader travel; `reading-regions.js` selects its scroller;
`runtime/anchor-resolution.js` resolves anchors without importing paint or travel;
`runtime/anchor-paint.js` owns their placed readings and marks;
`runtime/anchor-controls.js` routes presses on those marks;
`runtime/anchor-travel.js` owns anchor and projected-datum travel, revealing a destination
before resolving its current node and scrolling to it;
`runtime/page-geometry.js` coordinates page movement and anchor, drawing, and aim paint;
`runtime/conversation/model.js` folds supplied server threads and unresolved messages
as values; it reads no runtime store or DOM. `conversation/identity.js` owns pending
message identity. `conversation/state.js` holds the one derived conversation reading,
written by conversation presentation and consumed by its surfaces;
`runtime/conversation/messages.js` owns message rendering;
`runtime/conversation/replies.js` owns reply drafts and invokes its supplied reply command;
`runtime/conversation/inline.js` owns conversation seats rendered into the page;
`runtime/conversation/box.js` owns page-seated first-message boxes;
`runtime/conversation/folding.js` owns shared Resolve/Reopen controls and resolution-fold
state and motion;
`runtime/conversation/landing.js` owns conversation input discovery, focus travel,
and panel arrival;
`runtime/conversation/narrowing.js` owns comment-panel search and the lifecycle,
scope, subject, and detached-placement facet state;
`runtime/conversation/placement.js` owns document-order grouping;
`runtime/conversation/reaction-strips.js` owns the panel's message reaction surfaces
and disarms reaction keyboard mode before a conversation surface is removed;
`runtime/conversation/surfaces.js` owns registry-declared widget outlets and the set of
threads they claim from the margin-projection fallback;
`runtime/conversation/thread-card.js` owns retained panel thread cards, their quote
state, and their reply, resolve, and reopen controls;
`runtime/conversation/thread-list.js` owns retained panel list reconciliation;
`runtime/conversation/acknowledgments.js` paints the server-projected interaction
receipts in conversation seats; and
`runtime/conversation/presentation.js` composes retained conversation rendering;
`runtime/conversation/panel.js` owns the panel composer, and `panel-elements.js` owns the
passive panel elements and geometry readings;
`runtime/projection/authored.js` owns typed authored initial values and anchor
parentage; `runtime/projection/data.js` owns keyed runtime-data DOM reconciliation;
`runtime/projection/model.js` folds authored, canonical, and pending records without DOM;
`runtime/projection/state.js` holds the desired semantic reading;
`runtime/projection/presentation.js` normalizes DOM inputs and owns presentation, deferred
widget work, and node-specific commit proof within its constructed instance;
`runtime/projection/commands.js` owns action eligibility and undo commands.

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
| unresolved browser work | the application-owned pending ledger | commands enqueue; accepted state accounts receipts; projection commit proof permits action release |
| desired semantic state | authored state, log projection, then pending overlay | projection presentation installs the folded reading, which may precede deferred DOM work |
| rendered conversation | the server's thread projection, then pending messages | `foldThreads`, installed by conversation presentation |
| proof of what the DOM currently represents | the projection presentation instance's commit records | `stageOptimistic` and `present`; release requires the same instance's proof |
| anchor paint | thread and composer anchor records | the anchor paint owner |
| where each thread's passage lands | this version's resolution of its anchor | anchor paint writes a rich placed record with its element, exact datum, and exact/fallback/outdated status |
| widget-local Thread placement | exact projected-datum placements plus the widget's current layout | the conversation surface coordinator asks each declared adapter for an outlet, then records the threads it claimed before the margin projection reconciles |
| canonical agent activity | the server fold of status, claim and turn identity, watcher lease, pickup events, and unsettled interactions | the banner, receipts, margin, and leaves tray paint `activity`; the browser only asks for a fresh server reading at `next_transition_at` |
| composer visibility | `composerOpen` and `fabAnchor` | `showComposer` and `showFab` |
| the draft a hidden composer can be brought back to | the stored composer records, narrowed to those whose passage this document still holds | `keptDraft`, read by the `g D` destination and by the notice `showComposer` writes when a box holding words goes down |
| thread-panel visibility | the panel controller's constructed visibility reading | `setPanel` writes the reading and projects it to the panel class and body attribute |
| the narrowing on the thread list | the reader's find words and lifecycle, scope, subject, and detached-placement facets | `renarrow`, `revealThread`, and `widen` |
| how much of the thread list's top a pinned heading covers | the tallest `.lf-pinned` box as rendered, while the panel is open | `paintHeadRoom` writes `--lf-head-room`, called by `renderThreads` and by a `ResizeObserver` on the list |
| the thread list's viewport position through reflow | the live reference card in the open panel | `renderThreads` and the held `paintAcknowledgments` call preserve it through reconciliation, provisional work, and resolution folds |
| where the thread holding the focus stands in the list | the band the list declares landable through `scroll-padding` | `threadsBox`'s `focusin`, and its press through `pointerdown`/`pointerup`; `stepThread` for a key press that moves no focus, `landIn` for the box it puts the reader in, `placeThreadEdge` for an explicit edge placement, and `showThread` for a deliberate arrival |
| tray visibility | `trayIsOpenKey` | `setOpenTray` writes reader gestures; `restoreTrays` loads saved intent and `restoreTray` paints it at presentation |
| region width the reader drew | the reader's store, per edge | `drawnEdge`'s `set` and `restore` |
| keyboard meaning | registered scope and row objects, bounded by their document or current native-layer root; inner Escape steps, an eligible causal return frame, then fallbacks | the dispatcher and each visible key surface read the same binding-specific ownership |
| draft generation | the reader's draft record | draft-store helpers and `watchDraft` |

Do not add a second cache, pending map, widget-specific replay list, or DOM
attribute as another source for one of these facts. A rendering may expose state,
but callers do not read the rendering to recover it. For example,
`style.display` does not answer whether the composer is open, and a focus ring
does not remember where an Ask walk last landed.

## Startup and presentation

Startup order is load-bearing:

1. Construct the application, page commands, and UI owners in `leaf.js` before any
   mount reads another owner. Page keys must exist before the first input is wired,
   because its initial paint reads the input's binding badge. Adopt the sheets,
   attach chrome, mount the owners, and wire the shared repaint phases. Repaint invalidations made
   before repaint is mounted retain their intent without executing an incomplete frame.
2. Begin the first state read without applying its answer.
3. Restore the reader's arrangement from storage, and let focus go to the page.
4. Fetch and validate the registry.
5. Index passage fences and authored parent identities before upgrade changes the DOM.
6. Import the modules declared by `x-upgrade` for the tags this document
   contains, and no others.
7. Wait for module settlement, then run the shared dressing passes.
8. Capture authored record facets from the upgraded, authored state.
9. Settle optional runtime-owned page interface that composes those widgets.
10. Mark `body` `data-lf-upgraded="1"`.
11. Start the state feed; its first answer is applied, reconciled, and presents the
    page. The feed waits a bounded time for that answer and then presents without one,
    offline, rather than letting a container that has stopped answering decide whether
    the page arrives at all. The read is not cancelled by that wait: it keeps the page's
    one read slot, and its answer applies when it lands, as any later read's does.

Authored HTML paints immediately on every page. The prepaint bootstrap marks the root
`data-lf-live`, and the render-blocking theme uses that fact to reserve the fixed banner
and the reader's restored workspace, so mounting the runtime does not move the document.
The same bootstrap projects that stored arrangement before the theme paints; runtime
restoration replaces the provisional root state with live body state.
Prose, ordinary links, scrolling, and layout remain usable while widgets upgrade and the
first state read is pending.
Generated interface constructed from authored markup participates in layout while it
settles, then `data-lf-upgraded` releases it from authored and tab-local state without
waiting for the first server reading. Durable controls remain unavailable until
`data-lf-presented`, and authored top-layer UI stays withheld until that same semantic
interaction boundary. A data-backed widget whose authored element has no content takes its
source-dependent space when that data arrives; stable geometry for that content requires
an authored reserve or a fixed rendering posture. Fixed status and unanchored discussion
chrome remain usable while a live page waits.
An optional page-interface failure reports itself without withholding presentation.
Modules must consult `actionAvailable` or `requestAvailable` before optimistic mutation
as well as before sending; their common send doors repeat the check. Selecting a passage
does not raise the anchored composer until the passage has survived the first projection.

`presentPage` owns the one transition from arrival to stateful interaction. Motion
helpers and the stylesheet collapse arrival animations until that boundary. Its final
synchronous `PRESENTATION` signal lets box-derived page apparatus replace provisional
geometry before the browser can paint the presented state. After it, a state change may
animate only where motion helps the reader follow a change. A failed startup does not
stamp the page presented as if it had read the log.

## What crosses to the server

The server does not retain refusal receipts. The condition behind a refusal can change
without the reader changing the words: a referenced revision can be activated, a parent
thread can arrive, or a layer can be re-vendored. Caching the refusal would strand a
valid draft behind an obsolete answer.

Interactive event `markup` has a different door from every other field: only the CLI
can write it, after validating it against the vendored registry, while the browser
event schema refuses it.

## Authoritative projection

`runtime/projection/model.js` owns the record fold; `projection/presentation.js`
combines it with authored DOM readings and keeps desired state separate from proof of
what each current widget node has rendered. Python derives the durable side (below). What both must honor: an `x-state` verb may
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
authoritative owner relation and admits it only when the one matching member container
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
complete index. With the panel closed, a thread margin entry and the `t`/`T` walk use that
inline seat; with it open, they use its indexed cards. A press on a marked passage or its
accessible comment-count note follows the same rule. Opening Threads while an inline
thread holds focus carries that thread into the panel and keeps focus on its card.
A root
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

The registry has two grains. An element declaration is one complete schema and later layers
replace it whole. A `$` entry is a shared namespace and layers merge its members.
Shared facts such as languages, tones, idioms, and event definitions belong
under `$languages`, `$tones`, `$idioms`, and `$events`. A consumer reaching into
some named widget to find a layer-wide list is reading the wrong owner.

The extension keys describe general behavior:

| Declaration | Meaning to the layer |
| --- | --- |
| `x-upgrade` | import this tag's module |
| `x-content` | the element contains authored markup, owned members, data, or nothing |
| `x-required-members` | fixed member roles: exactly one direct member for every value of a required member enum |
| `x-inline` | the widget stands in an inline run |
| `x-measured` | authored scalar words are pinned at an instant to one live data input; checks compare that instant with the source's latest update |
| `x-says` | named attributes are visible words at declared edges |
| `x-paints` | named attributes communicate facts through paint and need a quiet spoken reading |
| `x-verbatim` | own authored or canonically projected words and the order and identity of nested upgraded boundaries must agree with the rendering |
| `x-shadow` | a declared open shadow tree is part of the page's composed reading |
| `x-state` | reader action verbs, current eligibility, facets, units, schemas, and records |
| `x-report` | report verbs with the same semantic state shape |
| `x-request` | direct-child command offers, typed one-shot external-operation verbs, and whether a ready lifecycle is an Ask |
| `x-refers` | element-id attributes and optional package-owned map predicates that type their targets |
| `x-owners` | the element types that may directly own this member |
| `x-retired-when` | outcome-to-slot retirement relations |
| `x-withdrawn-as` | the author's state for a withdrawn recordless decision |
| `x-ask-surface` | the complete reading and arrival region around one nested Ask source |
| `x-awaits` | the condition, explicit answer verbs, and optional nested roll-up for an Ask |
| `x-conversation` | the condition under which the widget owns a conversation seat, and whether its root requires a version response |
| `x-thread-surface` | the upgraded widget may provide local outlets for complete Threads anchored to its exact projected data |
| `x-work` | admits local agent work without a pending reader move, through a content or conversation seat and optional condition; an admitted page-widget claim then appears at the page edge through its target margin entry |
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
Each preserving owner also receives its source and document-order occurrence before
upgrade. The file reader derives that same provenance for page markup and each frozen
thread event, so anonymous owners and their nested widget boundaries remain distinct.

Do not broaden the Python reader by guessing a module's DOM. Declare modelable
words with `x-says`, `x-paints`, or the appropriate content key. Keep the widget
fenced when its transformation cannot be represented faithfully.

The layer is the document's other boundary, and a pointer drag that crosses it is
not a passage: past the page's last words the browser extends through everything
between, so the release puts back what the drag had inside the document and offers
nothing where it had nothing (`leftThePage`, read on the pointer path alone). Select
all lands its far end past the page by definition and still means the document, which
is why the rule is the gesture's rather than every selection's.

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

Leaf's chrome and widgets use solid contours by default. A dotted or dashed line is
appropriate when its style is the non-color cue that separates a state or affordance
from an ordinary contour; editable drafts, drag placeholders, design-mode geometry,
and detached references use it this way. Prefer an existing label, action, or shape
when that already makes the distinction. Lines inside authored diagrams retain the
document's own semantics.

The parent laying out adjacent actions owns their complete allocations. Different
actions have disjoint hit boxes, and a compact control's larger aim may not cover a
sibling's visible surface.

During startup, generated interface first appears in its settled upgrade position, from
authored and tab-local state. An asynchronous producer joins the applicable widget, data,
or page-interface settlement before `data-lf-upgraded` releases that interface. Apparatus
that also depends on authoritative replay takes one synchronous reading on `PRESENTATION`,
then uses `ResizeObserver` or the shared layout signal for later changes. An asynchronous
producer's default may reserve space without painting; a box-derived reading taken before
replay does paint, and `PRESENTATION` replaces it.

Control state is paint: ink, fill, border, or an inset ring. Do not express it by
changing font weight, size, padding, border width, or another metric. Reserve
space before a generated control appears. Transient feedback may repaint a control or
briefly replace its label, but neither may change its geometry; `reserve` measures all
enumerable labels in the control's current font and sets a minimum width. Re-measure
after changing type tokens. The banner status stays on one line with ellipsis and a
complete hover title; its CSS reservation stays independent of changing copy. Pair
local visual feedback with `notice` for an assistive announcement.

Submission feedback uses the shared lifecycle: the result of the gesture as durable
confirmation, and `notice` for a transient acknowledgment. Persistent status text is for
a state the reader must return to or act on, such as failure.

Where the page can produce that result itself, it produces it in the gesture. A
suggestion decision paints its projected outcome; a comment or reply paints the message
and opens its thread. The application overlays pending work on the log and restores
authoritative state on refusal. The content and its Undo control are the confirmation,
so neither path needs a success notice; announce the same outcome for a reader listening
to the page. For a message that announcement is `post`'s, made where the gesture is first
known to be a message, so a box that sends one adds no second announcement. A box whose
press did something beyond sending writes one notice for both and names the send in it,
because a later write replaces the live region rather than joining it. A gesture whose
result only the log can supply waits instead, with
`aria-busy` on the surface, which `chrome.css` paints on a delay so a fast answer shows
nothing at all.

## Keyboard, focus, and navigation

One register defines every runtime and widget key. A row binds keys, states what
the press does, decides when it is live, and runs it. A scope says where a group
of rows applies and which platform keys that context claims. The dispatcher,
shortcut bar, `?` reference, control tooltips, and announcements are projections of
those objects.

Escape has one additional semantic order that declaration position cannot change. An
active core mode marked `escape: "inner"` and an exact focused element may consume its
own inner step first. The latest eligible command return frame follows, then ordinary
scene-derived and containing-scope fallbacks. Browser-owned modal and popover boundaries
are applied outside that order, so a covered frame remains suspended and an unhandled
native dismissal reaches the platform.

Treat that register as a product grammar, not a collection of locally convenient
shortcuts. A binding belongs only when its key is the canonical spelling for that action
in the active scope. Reusing a key in a nearer scope must preserve that meaning; a
familiar alternative or an unused key does not justify an alias, because every binding
spends the scope's namespace. Before adding or changing a binding, survey the complete
register for meaning, scope, native overlap, entry and exit symmetry, and focus
restoration.
Each generated hint names the exact visible control it activates. An aggregate location
may expose each of its visible margin entries or focus itself; it never selects a descendant
action for the reader. A press a widget built is one of those controls too, read off the
value `offer` and `selectableOffer` write: the tag for a button, the type for a native
checkbox or radio, or the role for a selectable offer. This lets a capability decline a
page letter without becoming unreachable. The row states the capability, and the sequence
reaches each control that routes to one. The reading stops where the theme's hand stops,
because it is the same reading.
Document every inconsistency the survey exposes in the task handoff. If the rules
here do not settle one, escalate it to the user before choosing locally; the
absence of a dispatch conflict does not make a binding precise.

A sequential key route is rendered as one box per physical step. The boxes stay close
enough to read as one route. In an active mode, only the longest leading sequence that
matches presses the mode accepted wears the pressed face; another route's next key stays
neutral. A visible control's transient destination uses the same detached overlay shape as
a generated target hint. The placement pass centers it in the open space immediately below
and keeps it clear of its control if it must use another side. It stands only while its sequence
is active; the complete reference and control tooltip keep the route available at rest.

The complete reference gives each distinct filter or destination its own command row.
Search preserves a typed trailing separator and case: a query such as `g ` asks for sequence
continuations, and `g t` ranks the lowercase filter ahead of `g T`. Every declared
alternative is indexed from the register even when its rendered cell compacts alternatives
into one face. All binding-prefix matches lead the result list across scopes; prose and
scope matches follow them. The visible row order is the keyboard command-rail order too.

### Page scope rows (keyboard/page.js)

The register owns capabilities, not controls. Every capability the chrome offers
has a row, and each control that reaches one is named by `control`; a
control is a route to a capability rather than a capability of its own, so a
second route needs no second row. A run heading in the thread panel presses the
page to where that run is about. That travel is a capability, just as `w` and `/`
are capabilities nothing else reaches, and each earns a row. A capability with
no row is one the shortcut bar never advertises,
the reference never lists, and a reader working from the keyboard never finds,
because those three are projections of the register. Add the row in the change
that adds the capability.

Directional category walks use the category's letter, with case stating direction:
lowercase advances and Shift goes back. `t`/`T` walks open threads and `a`/`A`
walks open asks. Both walks clamp at their first and last destinations. Keep these as single-key
presses rather than prefix sequences; a walk is often repeated or held. The thread walk
uses inline thread roots while Threads is closed and panel cards while it is open; only a
thread with no page or widget-local inline destination opens the complete index as a fallback.
An active textual search in the thread panel instead owns `n`/`N`: those keys enter the
found list from its container and then walk its matches, while `t`/`T` stands down so the
motion has one spelling in that scope. For page search, Enter accepts the current match and
`n`/`N` walks the next or previous one. Letters remain query text while a search input has
focus; Tab and Shift-Tab walk page-search matches before acceptance.
While the reader stands anywhere in an Ask, its widget's
ordered actions keep a canonical binding where they declare one and otherwise take the
next free `1`–`9`. Core projects that exact list into the shortcut bar and visible control
chips. Each action is a command route; that route is the one
binding-to-control identity used by dispatch, the reference, the shortcut bar, its binding badge,
and `aria-keyshortcuts`; core does not mint a second identity for the projection. A package
may lend one empty binding-badge face per action. Core uses it only while the whole face is
visible, uncovered, and claimed by that action alone; otherwise core draws its own badge. Tab
walks the real controls without replacing that action map;
a control's scope adds only its native or local mechanics. `j`/`k` scroll
down/up by 60 pixels; `d`/`u` move 60% of
the reading page. Both follow the active region, share a quick glide, and jump under
reduced motion. Native Space stays with the platform and focused controls. Other letters come
from words the surface says: `w` narrows to threads waiting on the reader while focus is
in that panel, and enters Draw mode from the page. The Go-to sequence
(`keyboard/go-to-sequence.js`) uses uppercase letters for named destinations and lowercase
letters for target-kind filters and generated hints. `g t` and `g a` filter to visible
Thread and Ask controls; their uppercase counterparts open the complete panels. `g m`
contains every visible margin control and status indicator. A key spelling something
nothing on screen says is a key nobody reaches for twice.
Approval spends no fixed page letter: its visible button stays in the Tab order and takes
native Enter or Space, while the Ask-local list gives it a contextual binding. In particular,
a conditional sequence mnemonic must not share its final key
with a page action, or a dead destination can fall through into a different operation.

`c` is reserved for commenting. Enter keeps native activation or text editing, and the
focused control's local continuation. A page option mark is a checkbox and toggles with
Space or its Ask digit; it gives Enter no second meaning. The Another option field is an
ordinary Tab stop and takes the next Ask digit after the authored options when one of the
nine addresses remains. It follows the same text-box contract as every other textarea:
Enter writes a newline and Mod+Enter adds the option. In a thread there is no second add
form, so Enter from its option mark continues into the thread's existing reply.

A row whose press turns a mode on and off states the mode rather than the toggle.
`does` and `line` are functions of whether it stands, so the sentence says which
way this press will go. When turning it on is an entry, its `returnFrame` states
Escape's inverse rather than a second row guessing from the resulting scene.

Which scope a row belongs to follows from what its press acts on. The page holds
the presses whose subject is the page: `/` searches its text, `n`/`N` repeats that
search, `s` names its visible
addressable elements, `c` comments on it, `t`/`T` and `a`/`A` walk its open sets, `j`/`k` and `d`/`u` move its
reading, and `g` opens its destinations. A surface holds the presses
whose
subject is that surface's own
contents, because contents the reader is not looking at are not a thing to act
on: `w` narrows the thread panel's list, while `/` searches it and `n`/`N` walk
the results. Those bindings live in `PANEL`. The page's alphabet is small and every
letter spent there is spent on every page, so a letter earns page scope only by acting
on the page.

A surface may also hold the contextual form of a page intent. `c` always means
comment; its destination follows what the reader is standing on. From the Threads
list the panel row enters the page-comment box. Everywhere the page has a nearer
answer—a selection, addressable element, or conversation—the page row enters that box instead.
The rows are mutually exclusive, so the register never asks the reader to choose
between two meanings for `c`.

Each composition box's placeholder — the general box, each per-thread reply, the compact
anchored composer, and composition boxes contributed by widgets — adds the live key that
enters that exact box when one exists. Once focused, it adds the box's registered
submission sequence. The accessible name states the box's purpose without either key, and
placeholder text uses the theme's muted text color at full opacity.

That the page row reaches into Threads is not an exception. Page scope already crosses
surfaces: `t`/`T` can land on inline or panel thread cards, and `a`/`A` can land on an ask
an agent sent inside a thread. A page key that takes the reader somewhere owes them an
answer once they are standing there. The destination, label, command, and return frame
all come from `commentDestination`, so the same contextual reading governs every projection.

The destination is the anchor the 💬 carries, then the open thread the reader is
in or the single inline thread held by a pressed Page Map marker, then the element they are
standing in, and, when none of those is in hand, the page-comment box.
`commentDestination` decides it once and states the
sentence, return frame, shortcut bar and press together, so the reference, the line,
what happens, and the way back cannot come to spell it differently. The pointer's answers outrank
the standing: a selection or a raised 💬 is the more recent thing the reader
said. `standingElement` and `standingConversation` are what "standing" means here,
and **Standing somewhere** below owns that reading.

The page-comment box lives in the Threads panel, but entering it does not mean “open
Threads”: `g T` owns that destination and lands on the list where `w` and `/` remain
reachable. `c` opens the panel only as the implementation container its requested box
needs, focuses the cursor immediately, and records the prior auxiliary surface in one frame.
Escape therefore returns directly to the exact prior control or reading place. From an
already-entered Threads list, `c` adds one nested frame and Escape returns to that list.
A resolved thread has no reply box, so the general box is the honest contextual answer.

The addressable element's box is the composer, on the element, and not a widget's own conversation
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
`standingElement`: the unanswered Ask where focus is on a control that works it — a
pick, a ✓, a mark — an answered Ask on its explicit review arrival, and the
innermost addressable element everywhere else, which is the ⌥ aim's own reading. It answers nothing
in ordinary chrome, where a reader is working on the page rather than standing in it.

## Standalone copies and print

`version export` waits for the already-presented DOM, drops scripts, and marks the root
`.lf-copy`. Anything meant to survive must be present in markup and CSS.
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
| `unnamedFormFields` | every input, select, and textarea has an id or name Chrome can identify |
| `upgraded` and `moving` | upgrade completed and final geometry settled |
| `invalidPaints` | every var()-backed SVG paint resolves to a valid value in each scheme |
| `tinyBoxes` | every declared widget has a usable rendered box |
| `unmarkableElements` | every addressable element has a visible part for an outline |
| `misplacedBoxes` | boxes stay in the column or in genuinely reachable overflow |
| `squeezedTables` | a table scrolls sideways only with every column at its longest unbreakable run |
| `withheldRoom` | a drawing scrolls only when the room, net of margin residents at its band, ran short |
| `silentCuts` | a box showing less than it holds across fades each edge with content beyond it |
| `clippedControls` | actionable controls are visible and reachable |
| `unreachableWords` | visible page words remain in reachable flow |
| `coveredWords` | browser words are not silently clipped, hidden, or claimed by chrome |
| `unreadSyntax` | syntax highlighting does not erase or alter source words |
| `shownVerbatim` | every preserving owner agrees with its revision- or conversation-scoped projected passage |
| `silentWords` | `x-says` and `x-paints` promises reach the composed rendered page |
| `undeclaredAttrs` | modules do not write undeclared author-namespace state |
| `retiredSlots` | declared settlement marks and retired-slot visibility agree with the projection |
| `trappedMargins` | framed boxes show only their declared inset |
| `paperWords` | print keeps every page statement and removes only affordance |
| `paperVoids` | print gives room to nothing it does not also draw |
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
  covers every `READER_VIEW_RESTORE_CASES` restore.
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
