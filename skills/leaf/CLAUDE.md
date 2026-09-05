# The page in the browser

This file defines the contract for `assets/leaf.js`, its runtime modules under
`assets/runtime/`, the widget modules, and `assets/theme.css`. It describes the
current runtime. Page-authoring commands and
markup rules live in `references/page-authoring.md`; package authoring lives in
`references/packages.md`. The repository-level `AGENTS.md`
owns the rules that cross the JavaScript and Python runtimes:

- the document is the initial state and the event log outranks it;
- one representation serves each concept;
- the file's reading never claims more than the rendered page's reading;
- the widget vocabulary is open.

Keep this file about browser behavior and the boundaries that preserve those
rules. Put an invariant beside the code it constrains when that code is the only
consumer. Put a cross-runtime invariant in the repository instructions. Do not
record the sequence of implementations that led to the current one.

## Runtime ownership

`leaf.js` is the boot-only browser entry module: it composes the runtime owners and
starts the page, but exports no capability. The HTTP boundary places the vendored
`runtime/bootstrap.js` before loadable resources, with an exact CSP hash; it can
show startup failure and hear a replacement server even if the module graph or
stylesheet never loads. `runtime/widget-api.js` is the one public
helper surface for behavior modules and reexports capabilities directly from their
runtime owners. An owner may publish a factory-built capability after boot wires its
dependencies; it never reaches back through the entry module or public facade.
`runtime/context.js` owns the mutable facts shared across the browser layers and
their direct readers;
`runtime/deferred-modals.js` holds authored modals outside the top layer until the
first presentation boundary;
`runtime/layer-client.js` owns the vendored-generation gate, shared event POST,
and page-error channel;
`runtime/requests.js` owns typed one-shot request availability, sending, and the
server-projected request lifecycle watcher;
`runtime/decisions/model.js` owns request discovery, folding, and the semantic Decision
subscription;
`runtime/decisions/view.js` owns decision chrome, marking, the decision walk, and
Ask-local contextual command projection;
`runtime/projection-watch.js` owns the lifetime-bound invalidation subscription shared
by the public semantic projection watchers;
`runtime/composing/capture.js` owns selection capture and snapping;
`runtime/composing/surface.js` owns floating comment geometry and page-click routing;
`runtime/composing/targets.js` owns keyboard item hints and whole-page text search;
`runtime/composing/aim.js` owns modifier aim and captured presses;
`runtime/composing/input.js` and `runtime/composing/selection.js` own shared input
and selection-composer state;
`runtime/drawn-edge.js` owns the shared resizable boundary used by the thread panel
and tray panels;
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
`runtime/keyboard/` owns keyboard binding vocabulary and scoped interaction;
`runtime/keyboard/disclosure.js` owns the shared disclosure bindings;
`runtime/notifications.js` owns visual and assistive announcements;
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
version-comparison state, marks and chooser paint, version document loading,
authored-root replacement, the persisted semantic reading landmarks carried across that
replacement, and the page-block reading directional walks start from;
`runtime/widget-upgrade.js` owns widget upgrade guards, data bodies, fail-soft
rendering, and async settlement;
`runtime/widget-elements.js` owns widget-element construction, labels, gesture
guards, deferred measurement, layout-change signalling, and control sizing;
`runtime/registry.js` owns vocabulary queries;
`runtime/scrolling.js` owns the document scroller identity, relative scroller moves,
fixed-surface wheel forwarding, and the gutter its bar takes;
`runtime/chrome-style.js` owns the comment layer's private stylesheet, built from
the declaration-derived names and layout queries the runtime supplies it, and keeps
the root, body's layout shell, and the chrome's paint hosts out of the containing-block chain for
document-positioned chrome. It also keeps page-attached paint below covering workspaces
and paint for chrome targets above them;
`runtime/chrome-layout.js` owns comment-panel visibility, chrome geometry, the document
room left after the panel and trays, the final-layout column motion between workspace
states, and page repaint caused by shell motion or reflow;
`runtime/presentation.js` owns runtime paint and the words it projects;
`runtime/reach.js` owns keyboard access to overflow and the containing block a
scroller owes what it scrolls;
`runtime/shadow.js` owns declared shadow roots, their theme slice, and shared
highlight rules;
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
`runtime/conversation/reaction-strips.js` owns the panel's message and page reaction
surfaces;
`runtime/conversation/surfaces.js` owns registry-declared widget outlets and the set of
threads they claim from the living-margin fallback;
`runtime/conversation/thread-card.js` owns retained panel thread cards, their quote
state, and their reply, resolve, and reopen controls;
`runtime/conversation/thread-list.js` owns retained panel list reconciliation;
`runtime/conversation/acknowledgments.js` owns growing acknowledgment receipts and live claim seats; and
`runtime/conversation/reconcile.js` composes panel reconciliation;
`runtime/projection/authored.js` owns typed authored initial values and anchor
parentage; `runtime/projection/data.js` owns keyed runtime-data DOM
reconciliation; `runtime/projection/fold.js` adapts canonical action and report state
to live DOM nodes and the local outbox;
`runtime/projection.js` owns projection reconciliation and undo. The entry module
composes their mutually dependent callbacks.

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
| version shown by the live document | the latest mapped revision accepted at the activation boundary | `activateVersion` advances `currentVersion`; a public version address derives the version number from its URL |
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
does not remember where a decision walk last landed.

`PAGE_PAINT_ATTRIBUTE` is the runtime's one list of attributes it may paint on
authored elements. `shallowSigs` excludes exactly those attributes and reads only
id-bearing elements accepted by the bounded `authored` predicate. Generated elements
are absent; generated parents and siblings contribute neither the `in=` id nor sibling
position. An authored widget inside conversation chrome remains visible because its
widget frame bounds that predicate. A widget's own `data-lf-*` state remains visible to
replay and to the render gate. Add a runtime-authored attribute to
`PAGE_PAINT_ATTRIBUTE` when its writer is added; do not broaden the exclusion to every
`data-lf-*` attribute.

Layout follows the same ownership rule. CSS owns the document shell: `body` is
the `lf-shell` container, `main` composes margin claims, and container queries
choose their postures from the room actually left by panels and trays.
`syncLayout` measures only chrome whose placement or reservation depends on
rendered chrome, and writes only chrome boxes. `layoutSizes` watches
`document.body`'s content-box size without deriving a posture from it. A width
change schedules `syncLayout` and page repaint in the following frame after a
workspace lands its final shell; a height-only content reflow calls
`pageShifted` during observer delivery so page paint follows targets that moved.
That direct path may write only unobserved paint hosts and state or queue work for
a frame. A `ResizeObserver` callback must not resize the box it observes, directly
or through a class or attribute that changes that box.

## Startup and presentation

A vendored runtime and registry are one generation. The runtime contains the
`"__LEAF_LAYER_GENERATION__"` placeholder and the registry carries the same
epoch after `page init`. `sameLayer` checks every successful state read and POST
response. If the server speaks a newer layer, the tab reloads before it reads or
posts again. Do not let one generation interpret another generation's registry
or events. The adjacent `$layer.fingerprint` identifies the composed bytes across
vendoring epochs; it is diagnostic provenance, not a replacement for the fresh
generation's write fence. Repository example previews may also expose their safe
checkout provenance in a banner badge and copied diagnostic bundle. Ordinary pages
do not.

Startup order is load-bearing:

1. Begin the first state read without applying its answer.
2. Fetch and validate the registry.
3. Index passage fences and authored parent identities before upgrade changes the DOM.
4. Import the modules declared by `x-upgrade` for the tags this document
   contains, and no others.
5. Wait for module settlement, then run the shared dressing passes.
6. Capture authored record facets from the upgraded, authored state.
7. Mark `body` `data-lf-upgraded="1"`.
8. Apply the prepared state answer, reconcile it, and present the page.

A page loads what it uses. `importWidgets` is the one import-on-demand door: it
takes the markup about to be upgraded, imports each declared tag standing in it
once per tab, and loads the shadow rules only where an `x-shadow` widget is among
them. Three boundaries introduce markup and all three call it — startup with the
document, a version activation with the incoming `main`, and the state
application with the frozen markup an agent's reply carries, ahead of the panel
building a body. Each of them names the tags it needs, so nothing imports on a
mutation after the element is already connected. A module whose own payload is
large (`lf-diff`'s renderer) imports it on first render for the same reason.
`missingUpgrades` therefore reports the page's own widgets; that a declared
module exists at all stays `package check`'s.

`rememberAuthoredParents` records parent identities before imports for anchor ownership.
`captureAuthoredFacets` runs after upgrade because widgets may arrange authored state
in `connectedCallback`. It records typed initial values before projection changes them.
The first server answer stays buffered until these initial readings exist. Frozen
thread widgets use the same boundary: the list connects them, waits for their
registered upgrades, and captures initial values before the state application
projects any winners. Concurrent applications wait for this whole boundary.

The served page root is a stable live document. Its first response projects the
latest immutable revision and carries a runtime-only version marker. On a later
state read, `versionDocument` fetches the next mapped revision in the background.
`activateVersion` replaces the authored head declarations, root attributes, and
`body > main`; runs the same fence, parent, dressing, settlement, and authored-facet
passes as startup; reconciles the log; and restores the semantic reading landmark
and the reader's standing. That standing is written down by id before the swap —
the nearest element carrying one, and the control within it by kind and position —
and handed back after it: the same control where the revision kept it, its owner
where the revision kept only that, and nothing where it kept neither. A chord armed
before the swap is the runtime's and holds through it; its chips are read off the
document standing afterwards. The gestures `midComposition` names — item hints, a
reaction list, page search, a drag or grab — defer the activation instead.
The chrome, browser document, module globals, panel, and address remain standing.

That activation is one presentation boundary. Its async work runs in a
`startViewTransition` update callback where the platform supplies one, including
for reduced motion (whose transition duration collapses in the theme). Concurrent
state responses serialize behind the active application; none may capture or replace a
half-upgraded main. A runtime without the API applies the same ordered boundary
without animation. If activation fails after advancing the document, reload the
stable root rather than leaving a mixed version. A layer-generation change always
reloads: soft activation is only valid within one vendored contract.

The page has three readiness facts, all three written on `body` rather than on the
root element. A reader waiting on the root sees an empty `dataset` forever, with
every module loaded, nothing logged and nothing failed — which reads exactly like
a page that never started, and sends the search to the server, the page key and
the vendored layer in turn:

- `data-lf-upgraded` means widget imports, asynchronous upgrades, geometry, and
  drawings have finished.
- `data-lf-applied` is the event coverage of the last complete semantic
  projection committed to the DOM.
- `data-lf-presented` means the initial authoritative projection, or the
  deliberate offline authored fallback, has crossed the semantic-interaction
  boundary.

Do not merge these stamps. A document can finish upgrading while its first state
read is pending, or the answer can wait unapplied while upgrades finish. A
projection can commit while finite reconciliation animations are still settling.
Any consumer that reads final boxes waits for upgraded, applied, presented, and
no finite animation reported by `moving`.

Authored HTML paints immediately on every page. Its prose, ordinary links, scrolling,
and layout remain usable while widgets upgrade and the first state read is pending.
`data-lf-presented` does not release paint: it releases recorded widget actions and
authored top-layer UI once the first state read has either applied or established that
the server is unavailable. Modules must consult `actionAvailable` or
`requestAvailable` before optimistic mutation as well as before sending; their common
send doors repeat the check. Fixed status and unanchored discussion chrome remain usable
while a live page waits; selecting a passage does not raise the anchored composer until
the passage has survived the first projection.
`showModal()` calls from authored main are temporarily represented as measurable
non-modal dialogs; `presentPage` promotes only connected, still-open dialogs whose
reconciled branch remains visible. This prevents a modal's top-layer inertness from
disabling the recovery chrome. `showPopover()` opens natively so the widget can observe
and cancel it through `:popover-open`; the startup stylesheet withholds its top-layer
paint and interaction, and `presentPage` closes any open popover whose reconciled branch
is no longer visible.

`presentPage` owns the one transition from arrival to stateful interaction. Motion
helpers and the stylesheet collapse arrival animations until that boundary, and the
stylesheet withholds only dialogs and popovers rather than the authored document.
After it, a state change may animate only where motion helps the reader follow a
change. A failed startup does not stamp the page presented as if it had read the
log.

`statePhase` distinguishes `waiting`, `ready`, and `offline`. An empty
`events` array while waiting means the log has not been read; it does not mean
there are no comments. A restored or newly opened panel keeps its general
composer usable and shows a loading state until that distinction resolves.

A failed fetch is a complete offline answer for interaction: the authored page
is the best state available when no log can be reached, so fixed status chrome reports
the loss and its controls may activate. A successful response with malformed state is not an
offline answer. Parsing or rendering errors pass to the recovery boundary and
leave the candidate sequence unresolved; authored content stays readable while
state-dependent controls remain unavailable.

Required widget imports reject through the startup or activation boundary; a missing
module cannot count as a completed upgrade.

`reportPageError` is the common runtime error surface. A widget failure may
`failSoft` its own element so the rest of the page and Threads remain usable,
but it does not convert a partial state read into a committed one. The window
error listener, module load failures, and render gate all report through the
same page-level evidence. Do not catch an error merely to stamp readiness or
continue accounting for outbox attempts.

## Event delivery and the ordered outbox

Every browser event receives an `attempt` before its first POST. The attempt is
the idempotency key for one user gesture, not for a payload shape or a button.
Under the server's append lock:

- the first accepted attempt appends one event;
- an exact concurrent request or retry returns that event;
- the same attempt with a different payload is refused;
- a completed refusal leaves no durable receipt, so the same attempt may be
  evaluated again after the state that caused the refusal changes.

The browser sends through `post`. It rejects reuse of an attempt already present
in this tab's `outbox`, appends one entry, stages an optimistic recorded action
when appropriate, repaints key availability, and starts `drainOutbox`. There is
one queue and one delivery loop. Entries send in browser gesture order because
the log order is part of the user's statement.

Each entry separates three facts:

- `answered`: the server definitively accepted or refused the request;
- `readEvent`: a complete state read contained the accepted attempt;
- `projection`: the local semantic coordinate and absolute recorded value that
  the widget already painted.

Acceptance and application are not the same fact. A successful POST must include
state containing the event minted for the attempt. `deliver` then knows the
request was accepted and may open the queue for the next entry. The caller of a
successful comment waits until `receiveState` has either rendered that response
or reported the local render error, because its continuation opens the complete
conversation view and may focus the reply box the response creates.

An accepted action stays in the outbox until a complete applied state contains
its attempt and `committedProjection` proves the authoritative coordinate now
represented by the DOM. If applying the POST's state throws, the caller still
receives the accepted event and the queue advances, but the entry keeps replay
and undo held until a later poll applies a complete state. Do not resend an
accepted event because its rendering failed.

A recorded action may be optimistic because its gesture has already changed the
DOM. Drag and edit are examples. `stageOutboxAction` gives that local value the
same semantic coordinate as the server view and commits it on the exact widget
and unit nodes that carry it. The browser projection adapter overlays all
surviving recorded outbox actions after authoritative winners in `outboxOrder`.
Until a complete read accounts for an attempt, its local winner outranks any
older log winner on the same coordinate.

A press whose result has not changed the DOM waits for the log. Recordless
settlements and completion presses do not enter the optimistic overlay. The
control may say `aria-busy` while the request is pending, but it must not paint
the accepted outcome before the server accepts it. A recorded toggle that the
next gesture computes from must paint before the next gesture, so the next
absolute detail includes the state the reader just chose.

`deliver` races the POST against `entry.read`. A poll can account for an attempt
whose POST response was lost, and the accepted POST state can account for it
without another GET. Transport errors, undecodable answers, and incomplete
answers retry the same attempt after `RETRY_MS`. A response with `final: true`
and `ok: false` is a definitive refusal only when it names this attempt, or
omits an attempt. A layer-generation refusal reloads instead of retrying a body
under the wrong vocabulary.

On refusal, `drainOutbox` marks a recorded action `rejected`. It immediately
stops contributing an optimistic winner, then `reconcileKnownState` restores
the coordinate from the last complete authoritative state. The entry remains
until `localCoordinateCommitted` proves the optimistic token no longer
represents the DOM. Delivery may continue while that correction waits for a
live drag or editor to finish.

`accountOutbox` runs only after `receiveState` has installed and rendered a
complete state. It links receipt events to entries, resolves readers waiting on
those events, removes non-action entries whose delivery is complete, and calls
`releaseProjectedOutbox` for actions. Never remove an action merely because a POST
returned 200 or because an attempt appears in a receipt list that failed partway
through rendering.

`unaccountedGesture` is true while undo is in flight, the outbox is nonempty, or
a widget is visibly dragging. Navigation and undo both consult it. Navigating
would destroy unresolved local work; undo cannot choose a stable last gesture
while an earlier gesture is unresolved.

### Attempts held by drafts

A draft generation stores `{text, attempt, base}` while active and
`{attempt, base, settled: true}` after settlement. Its attempt is minted on the
keystroke that creates the generation, not on Send, and is reused by every tab
that sends that generation. A refusal does not mint a new attempt. Pressing Send
again re-evaluates the same attempt against current server state.

This is why the server does not retain refusal receipts. The condition behind a
refusal can change without the reader changing the words: a referenced revision
can be activated, a parent thread can arrive, or a layer can be re-vendored.
Caching the refusal would strand a valid draft behind an obsolete answer.

A new edit, including replacing text with the same characters, creates a new
attempt. A successful send settles only the exact active generation it sent.
`sendDraft` refreshes the shared record and compares both untrimmed text and
attempt immediately before POST; `settleDraft` repeats the generation check
before writing the tombstone. Text typed while the request is in flight
therefore survives its response.

## Authoritative projection

The DOM is a projection of three ordered inputs:

1. the authored state captured from this version;
2. standing actions and reports in the server's transaction-consistent browser view;
3. surviving optimistic recorded actions in the outbox.

The semantic coordinate is
`JSON.stringify([ownerWidgetId, unitId, facet])`. `x-state` and `x-report`
declare the fold unit, facet, detail schema, and optional record form for every
verb. `unitOf` finds the unit from the declaration. No core consumer branches on
a widget tag or verb to determine state identity.

An `x-state` verb may also declare `requires`, a prerequisite over the standing
decision projection `x-awaits` already defines. Its target is the sender or its
declared parent, and `awaiting` states whether that decision must be open or closed.
`actionAvailable` paints and guards the action, `sendAction` checks at the common
browser door, and POST evaluates the same declaration from the authoritative log
under the append lock. No eligibility cache sits beside the ordinary decision and state
projections. `x-awaits.answers` says which actions actually close the decision;
orthogonal actions do not, and neither does a conversation standing in the widget's
declared `x-conversation` seat — that takes the decision off the reader's list without
answering it, which is why this gate reads the projection with no seats in
it. An answer with a position record may declare
`completion: {empty: {within, when}}`: POST applies the candidate position to the
authoritative holder relation and admits it only when the one matching item container
inside the answering widget is empty. The same predicate decides whether a standing
record answers the Decision, so no private completion flag can diverge from the durable
arrangement. An answer or thread-completion verb cannot require its own awaiting value, or
an aggregate parent's awaiting value, to be false: either prerequisite is circular
while the decision stands. `x-awaits.rollup` carries the logical OR of its nearest
local decisions and child roll-ups in Python; the aggregate owner never originates
or surfaces a decision. The
browser receives the resulting ids and awaiting values.

Python's `state_projection` is the durable derived view. Under the same page
transaction as `/api/state`, `browser_state` serializes its classified events and
winners, decisions, conversations, updates, undo candidates, receipts, and coverage at
one `through_seq`. A normal response projects the revision the tab shows and the
active revision it may install next. A version comparison requests its older base
from `/api/view` at the exact `through_seq` already applied to the live DOM, so every
view used together has the same sequence basis without every state read parsing all
historical revisions. Page coordinates use that revision's document window;
conversation coordinates use the unbounded frozen-markup window.

The browser's `stateProjection` is a DOM adapter. It resolves those declared
coordinates back to current widget modules and overlays unresolved local records.
It does not derive retractions, settlements, thread structure, decisions, updates, or
undo eligibility from raw events. Winners on independent coordinates still
compose in event order through `compareProjected`.

The two durable channels share the coordinate model but retain their meaning:

- `x-state` records the reader's actions. The latest surviving action wins its
  coordinate.
- `x-report` records provisional agent or worker state. Reports remain live
  until a version note answers their event ids.
- A reader action wins over a live report on the same coordinate. Different
  facets on the same unit remain independent.

`stateProjection` is uncached because registry declarations resolve through the
live DOM. Thread construction and revision activation can introduce new nodes. Its result has four views: `actions`, `reports`, `classified`, and
`desired`. Add a browser consumer to one of these views or extend the Python wire
view instead of building another fold over raw `events`.

`committedProjection` is not a second state authority. It is a checkpoint of
what node identities and semantic winner the DOM currently represents. Each
entry records the widget node, unit node, and projected entry for one coordinate.
Node identity matters because a revision activation or thread reconciliation may replace a
node without changing an event id. A coordinate with no winner is committed when
its authored baseline stands.

`projectionCommitted` compares the desired coordinate with that checkpoint.
Terminal events count as committed because this version has no applicable state
to paint. The server supplies coverage records and `projectionCoverage` checks
their coordinates against DOM commits for `data-lf-applied`: superseded actions
and answered reports are covered when the coordinate that represents them is
committed, and an undo is covered when its target's coordinate has moved to the
prior winner or authored baseline.

### Reconciliation

`receiveState` is the only door for a complete server state. Three callers use
it: a read of `GET /api/state`, an accepted POST answer, and a deferred version
activation that has become available. The clock retries explicitly deferred widget
projections without replaying a whole state. An unchanged page performs no state paint.
It:

1. verifies the layer generation;
2. rejects an answer taken before the one it holds, and an event sequence
   older than `lastEventSeq`;
3. loads the Markdown renderer before any message body needs it;
4. installs candidate `events` and renders all log-derived surfaces;
5. awaits thread-widget upgrades and initial capture, then calls `reconcileState`;
6. advances `lastEventSeq` only after the whole state renders;
7. accounts for outbox attempts;
8. dispatches `lf-actions` after replay.

If any required render throws, `receiveState` restores the prior event list,
phase, sequence, and held answer. A candidate history may be visible only during its own
application. Focus, undo, draft settlement, and later asynchronous
wakeups must not consume a log tail the page did not adopt.

`reconcileKnownState` protects those wakeups. It permits reconciliation only
from the last complete sequence, or from the authored-only initial state before
any events have been installed. A read that brought nothing is allowed to retry
a deferred correction against that known state. It must not project a newer
candidate whose surrounding render failed.

`reconcileState` delivers one complete facet map through `renderState(state)`.
`widgetStates` starts with typed authored values, overlays the server's desired winners
and unresolved local gestures, and composes ordered containers entirely in memory.
No reset actions, baseline replay, or cloned subtree reconstruction occur.

Each widget facet has `{action, value, detail}`. `action` is the winning verb, or `null`
for authored state. `value` is the typed record value, or the winning verb (with `null`
meaning undecided) for a recordless facet. `detail` preserves the winning event's detail,
including generated child labels; the authored detail contains the declared record field.
A facet with a non-widget unit has `units`, mapping each standing unit to that same
facet shape. Its `value` maps container ids to complete ordered id lists for a position
record, and is an empty object for recordless units. Missing recordless units are undecided.
Widget-absolute position records retain their containing id as `value` and their final
index in the declared detail field; ordering across those owners is composed together.

Render every declared facet, including null/empty values, while retaining the widget and
independent child widgets. Repeating a complete state must change nothing. Return `false`
only while a live gesture prevents safe rendering; the coordinate and outbox hold stay
uncommitted until a later wakeup. A widget ending that gesture dispatches `lf-projection`
on `document`; the state feed coalesces retries into a microtask so the gesture stages
its local action before correction runs. Throwing reports a page error and fails soft; the layer
still renders declared settlement marks.

`watchProjectionDrag` waits for the last `.lf-dragging` marker to clear, then
reconciles, releases eligible outbox entries, repaints keys, and dispatches
`lf-actions`. Do not let a read or the heartbeat fight the pointer by applying
projection during a drag.

`shallowSigs` reads authored tags, individual attributes, and placement. The render
gate temporarily renders the authored state and surviving decisions from earlier
revisions, intersects their writes with the author's changed facts, then restores
current state. New actions on this revision cannot contradict its authoring. No
per-render DOM write history is kept. Text has the passage and restatement checks.

### Authored state and undo

`authoredStates` holds the one typed initial condition per owner. Comparison readings
come from those same values, collapsing body whitespace and omitting position indexes
only where origin/diff checks require those comparisons.

| Record kind | Complete initial value |
| --- | --- |
| `attribute` | sorted owned ids carrying the declared attribute |
| `value` | the attribute string, or `null` when absent |
| `position` | ordered id lists per container; an individual widget also names its containing id/index |
| `body` | uncollapsed authored words from `textNodesUnder` |
| no record | `null` for a widget facet; an empty unit map otherwise |

Ownership of record members stops at `recordedOwner`, the nearest widget with a
declared record. A custom outer container must not capture or restore a nested
recorded widget's members.

An `undo` event names the event it withdraws. `takenBack` removes that gesture
from every fold; the log stays append-only. `undoable` walks the whole
authoritative log newest first, selects a standing user gesture, and offers an
action only on the version where that action was made. Thread resolution is not
version-scoped. Undo has no tab-local stack.

`canUndoAction` requires a mounted authored owner with a complete renderer or generic
retirement semantics. Undo selects a different complete projection; the same renderer
handles it without replacing the owner, its independent children, or their controls.

`renderSettlement` and `renderRetired` are layer responsibilities. The registry's
`x-parent` and `x-retired-when` declarations identify the holder and slots; the complete
facet's winning action paints the outcome, and its null baseline clears it. A module
may render the same marks as part of its animation choreography.

`paintStateOrigins` compares each desired record with its authored facet. It paints
`data-lf-reader-override` for reader actions and `data-lf-reported` for reports only
while the log differs from this version's authored state. Recordless decisions
retain the reader-origin mark while their holder remains in the document. These
marks describe origin, not unfinished work; receipts own processing and completion.
They are renderings of the projection, never inputs to it.

### Version and conversation windows

A page widget's projection stops at `currentVersion`. Later actions and reports belong to
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

### Event sequences for modules

Projection answers where state stands. Some modules also need to narrate how the
state arrived or when it was last reported. They read that through the exported
sequence helpers, not through raw `events`.

`actionSequence(widget, action)` returns copies of the widget's matching
absolute action events in log order and within its applicable version window.
It includes only events for which `projectionCommitted` is true. A module must
not narrate an action whose `renderState` is deferred while the body still shows
another value.

`updateSequence(target)` is the one reading of news about an item. Its target is
either a widget element or an explicit `{kind, id}` pair; a bare id is not an
identity and is rejected because a thread and a widget may spell theirs alike.
With no target it returns the whole ordered feed. Reports from the append-only
log and ephemeral thread work claims from status storage share a common envelope:
`id`, typed `target`, `source`, `action`, structured `detail`, declared
human-readable `text`, `ts`, attribution, and `disposition`. Report envelopes
also retain their version and sequence; a claim carries `log_floor`, the log
sequence it followed.

The source discriminator is semantic, not an implementation leak. A report
stands until a stamped revision's note absorbs or overrules it; a claim stands until the
thread receives an agent reply after that sequence or is resolved. The closed
disposition is `effective` when an update contributes to current state on its
semantic coordinate, `standing` when it still needs source-specific settlement
but is presently outranked, and `settled` when that authority answers it. An
older unabsorbed report can therefore be standing, and a reader action can mask
a report that a version still owes an answer. Settled entries remain in the feed
when their source retains history. A module showing freshness therefore still
sees when the log last heard from a worker after a stamp absorbs the worker's
report.

An x-report verb may name one required non-empty string detail field with
`update`. That is the envelope's `text`; consumers never infer prose from a
field, verb, or widget name. Claims use their required detail as `detail.text`
and `text`. The state boundary performs this normalization once, before
downstream code sees private status storage.

`actionSequence` traverses the classified events in the installed server view,
then returns structured clones so modules cannot mutate the reading.
`updateSequence` filters the server-normalized update feed. `watchActions`,
`watchUpdates`, and `watchDecisions` subscribe their public semantic readings to the
runtime's projection invalidation and invoke the callback immediately. The same
rendering function therefore handles a module connected before the first state and one
constructed by a later thread reconcile.

`lf-actions` fires after a complete state has reconciled, including a read whose
event list did not grow. The clock dispatches it only after retrying an explicitly
deferred projection. The outbox fires it too, for the reconciliation it performs on an
answer of its own — a refused action, or a read event — which withdraws or
settles a winner without applying a state. Every pass that reconciles is
therefore heard through this one event, which is what keeps a surface reading the
projection rather than the DOM current with a withdrawal. Time-dependent paints are
separate: `presence.js` records synchronous `ago`, `quietSince`, and `clockValue`
readings inside a `clocked` callback. The shared tick reruns only callbacks whose
reading changed and drops disconnected owners. Subscription callbacks use this same
mechanism, so a new widget owes no entry in a kernel list of clock consumers.
A held state does not reset the measured server clock offset.
Callbacks must render from the sequence they receive and return their cleanup
function from `watchActions` or `watchUpdates` when their element disconnects.

`active.revision` identifies the immutable document currently shown;
`active.version` is its public stamp when it has one, otherwise null, and
`active.label` is `vN`, `Draft after vN`, or `Draft`. The timestamp of the latest
note for that revision is the freshness floor for authored state when no report
exists. A page that reports no worker update is not timeless; its authored
assertion is as old as its revision.

`actionStands` answers whether one accepted action is still the reader's winner
for its semantic coordinate. It treats a newly accepted event as standing when
the tab has not yet installed an event list containing its id, then asks
the installed projection once an authoritative receipt contains it. Modules use this
after a send whose visible choreography depends on whether the accepted action
survived later events.

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
| `x-request` | direct-child command offers, typed one-shot external-operation verbs, and whether a ready lifecycle is a decision |
| `x-refers` | element-id attributes and optional package-owned map predicates that type their targets |
| `x-parent` | the child widgets whose decisions belong to this holder |
| `x-retired-when` | outcome-to-slot retirement relations |
| `x-withdrawn-as` | the author's state for a withdrawn recordless decision |
| `x-decision` | the complete reading and arrival region around one nested decision source |
| `x-awaits` | the condition, explicit answer verbs, and optional nested roll-up for a decision |
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

`widgetEntries` and `tagsDeclaring` are the general iteration doors.
`stateSpecs` is the one traversal of both `x-state` and `x-report`. New code
that loops over tag names or repeats those channel traversals is a closed list in
another form. CSS selectors follow the same rule: a list of framed widget tags is
still a closed consumer.

### Layer-owned defaults

If registry declarations and the log contain enough information to implement a
behavior, the layer implements it once. Current examples are:

- `renderSaid` turns `x-says` values into real selectable text.
- `renderQuiet` gives `x-paints` facts a clipped spoken reading.
- `markDeclared` exposes the declared width model, inline run, and quoting to
  the theme.
- `markSettled` paints the holder's authoritative settlement.
- `renderRetired` marks slots retired by the declared holder relation.
- `rowPresence` reads `x-awaits`, while the decision tray projects a declared `x-decision`
  region around that source where one exists; neither names a tag.
- A holder declaring `x-request.decision` joins that same decision projection only while its
  canonical request lifecycle is `ready`. Pending and completed requests are the host's
  turn; a failed receipt returns the holder to the reader without a package-maintained
  pending flag.
- `standingState` exposes replay winners to the render gate without naming a
  widget, the panel's own folds included: a widget an agent sent folds the way a
  page widget does and the poll replays it the same way, so the premise that
  every `renderState` is absolute binds it too.

A module owns only its choreography and semantics that no declaration can
express. For example, a suggestion module may animate its slots and write the
visible deletion and insertion words. It does not own the general meaning of a
settled holder.

The stylesheet uses declarations as open selectors too. A box that draws a
frame declares `--lf-frame: 1` in the rule that draws it. Style queries use that
custom property to trim child margins and to bound wide content. A project box
then receives the same behavior without joining a tag list. `main` hands wide
room back to its contents explicitly because it is the outer page frame.

`main` declares `--lf-column: 1` in the same rule, claiming that its `max-width`
is the readable column. The file lint measures every fixed pixel width against
that number, so a package or page setting a column of its own claims it in the
rule that sets it; a width with no claim beside it is a width and nothing more.

Where the fact belongs to the registry rather than to the rule that draws the
box, `markDeclared` paints it and the selector reads the paint. The lists that
ask whether a suggestion slot or a variant holds block content invert HTML's
phrasing content, which answers "block" for every custom element, so they
exclude `[data-lf-inline]` rather than the tags that declare `x-inline`. The
affordance rules that draw a choose group as a control exclude the descendants of
`[data-lf-exhibit]` for the same reason, asking in CSS the question `quoted()`
asks in JavaScript. A tag name in a shared list is a closed vocabulary wherever it
appears, and one layer's tag written into another layer's stylesheet is that plus
a leak.

### Module contract

A behavior module imports only the public helper surface from
`runtime/widget-api.js`. Do not reach into its private owners, query private
chrome, or duplicate a runtime helper inside a module. Every module has these
minimum obligations:

- Define the custom element once and make `connectedCallback` safe to run after
  reconnection.
- Use `once(el, fn)` for generated chrome so reconnecting does not duplicate it.
- Reserve a control's room from inside `measure`. A widget upgrades wherever the
  runtime connects it, and a shut panel is `display: none`, where every word
  measures zero and the floor the press needs is nothing at all.
- Implement `renderState(state)` as a total, idempotent rendering and return
  `false` only while a live gesture makes application unsafe.
- Call `sendAction` for recorded user state. The detail must match the declared
  browser schema.
- Call `sendRequest` for a one-shot external operation. Its detail must match the
  widget's `x-request` verb and the verb must be offered by one of this instance's
  declared direct children; an authored holder has at least one such child and offers
  each verb once. Requests are not replayable state and are not undoable;
  project it with `watchRequestLifecycle` instead of joining raw history or inventing
  a pending store. Core supplies the request seat, its ordered `{request, receipt}`
  attempts, the latest attempt, and the lifecycle phase (`ready`, `pending`, or
  `completed`) under the right document boundary: page holders read only the current
  revision, while holders in frozen thread markup read their whole lifetime. Python
  places this lifecycle in the browser view; modules do not join raw event history.
  When `x-request.decision` is true, that same lifecycle is also the decision projection's source:
  ready means the reader owes the choice, pending and completed do not, and a failure
  reopens it. Browser and POST eligibility consume that shared projection.
  `watchHistory` remains the audit-log surface for widgets that intentionally render
  events themselves.
- Call `layoutChanged(el)` after view state rearranges descendants without resizing its
  outer box. `ResizeObserver` already covers size changes; geometry consumers listen to
  this signal instead of watching every DOM mutation.
- For a verb with `requires`, use `actionAvailable(el, verb)` for both its
  visible control state and its gesture guard. `sendAction` and POST repeat that
  declared check at their respective doors.
- Write a name or state through `keeps(node, name, value)` wherever the render runs on
  the `lf-actions` heartbeat. It compares against what the attribute reads back as, so
  hand it a boolean or a count raw rather than stringifying at the call site. A
  `watchActions` callback paints every two seconds on a
  page nobody has touched, and an unconditional `setAttribute` restates itself at that
  rate: a mutation record a screen reader rebuilds its buffer from, and — for `open` and
  `aria-expanded` — a repaint of every key on the page. `toggleAttribute` already keeps
  the rule for flags.
- Read authored or user-facing words with `says`, never raw `textContent`.
- Build injected controls with `offer`. Use `relabel` when a control's label is
  also one of the page's words.
- Register capabilities with `commands(el, title, rows)` during upgrade, not at module
  load. Set `decision` to the concise action name and add `control` to the same row or
  route when that control answers or advances the containing Ask; call `paintKeys` when
  its liveness or computed fields change. Do not maintain a second Ask-control list.
- Subscribe to the page-wide open Ask projection with `watchDecisions(el, callback)`
  only when a package needs that reading. It invokes immediately, returns cleanup, and
  keeps packages off the internal `lf-actions` signal.
- Call `quoted(el)` before wiring module-specific gestures. `sendAction` also
  refuses actions on an exhibited widget at the layer door.
- A visual declaring `{parts: ATTR}` calls `registerVisualParts(source, read)` once.
  `read` returns its complete current `{id, element, label, surface?}` inventory; core
  admits only tokens authored in ATTR and derives both token lookup and the deepest hit.
  `surface` defaults to `element` and may name one descendant whose native paint excludes
  decoration from the target contour. It changes paint only: the returned element remains
  the hit and travel target. The authored widget remains the comment seat, and `id` is
  recorded as `anchor.visual`. Marks and aim follow an SVG surface's painted geometry
  primitives; a surface with none, and every other element, uses the shown box. Call the
  registration's `update()` after any rendering or geometry change, including an in-place
  attribute or style change. The render gate validates the inventory and requires every
  authored token to resolve.
- Render externally supplied or derived records through `projectData`. Its root is an
  authored, id-bearing seat; record keys are stable within that seat, and its renderer
  receives the prior node so unchanged controls and selections can remain in place. A
  renderer that owns a nested layout passes `{nested: true}` and returns each existing
  descendant; `projectData` then owns the labels without moving those nodes. Pass
  `labelOf` when generic chrome should name a datum in human terms instead of exposing
  its stable key. When the records came from `watchData`, pass the delivered `snapshot`;
  comments then retain the exact source revision the widget displayed.
- A widget declaring `x-thread-surface: true` may call `registerThreadSurface` with
  `begin`, `outletFor`, and `end`. The adapter owns local layout and returns an outlet
  only when the exact datum is currently visible. Core renders the complete Thread,
  suppresses the living-margin copy while the outlet stands, and restores the fallback
  when it does not. An adapter failure reports a page error and releases that widget's
  core views to the fallback without interrupting other conversations; core rendering
  errors still fail state application. Call the handle's `update` after a layout-only
  visibility change and `unregister` on disconnect.
- Cross-widget datum travel goes through `navigateToDatum(widget, attribute, key,
  messages)`, where `attribute` is declared by the caller's `x-refers`. Core resolves
  the target across declared shadow roots and owns lazy reveal, disclosure focus,
  scrolling, history, and announcements. A target with lazy or semantic coordinates may
  supply `lfRevealDatum(key)` and `lfDataDatum(key)`; callers do not inspect its DOM.
- Declare each external input through the widget's `x-data`, then subscribe with
  `watchData(widget, input, callback)`. The authored source attribute is the page's
  binding; the named contract is the input's meaning. An optional declared snapshot
  attribute selects an immutable capture, while its absence follows the replaceable
  current value. Treat the delivered envelope as complete, render `null` as absence,
  return an asynchronous render promise so the page's data-readiness stamp waits for
  the projection, and dispose the watcher when the element disconnects. The watcher
  captures both authored selectors at subscription; mutating a live attribute cannot
  rebind it. A module does not fetch or retain a second copy.
- Keep durable standalone state in serializable HTML attributes. Export removes
  scripts and handlers.
- Remove hoisted chrome in `disconnectedCallback` when the owner disconnects.

A `renderState` retains its owner and independent nested widgets. It must write only
attributes represented by declared record forms on authored elements. Generated chrome may use platform
attributes and `data-*` state. Returning success while writing undeclared
author-namespace attributes breaks the file/DOM comparison.

`worksInside` decides whether a container gesture may take a click. It treats
platform interactive elements as their own controls and uses `x-parent` to
distinguish a container's declared member widgets from nested widgets that own
their own interaction. Containers may name their own generated apparatus as an
exception. The general answer fails closed: declining one ambiguous container
gesture is safer than recording a choice while the reader operates nested
evidence.

## The page's reading

Passages use one representation: ordered segments
`{node, start, end}` over composed text. `textNodesUnder` produces the segments,
and quote capture, quote resolution, reading position, item labels, and
version-comparison readings all use them. Never introduce another text walk for one of
those jobs.

Two readings are intentionally different:

- `says` is what the rendered page tells the reader. It includes registry or
  module-generated words declared as part of the page.
- `wrote` is what the author placed in the version. It excludes generated
  runtime and widget words and is appropriate for version comparison.

Both are bounded by the root they are handed. `.lf-ui` says the runtime built a
node rather than the author, and a reading rooted at the document takes that
straight. Rooted at an element it is a different sentence, and the difference is
the whole of what a widget in a message needs: such a widget stands inside the
thread panel, so the panel is `.lf-ui` over every word it says, and an unbounded
reading has it saying nothing at all. Chrome above the root is not the root's
apparatus; chrome inside it still is. A page-rooted walk does not move.

Keep them as named readings. A boolean passed to one ambiguous reader makes
callers choose semantics at each call site.

`GENERATED` is `.lf-ui, [data-lf-gen]`. It marks words that are not authored.
`data-lf-said` is nearer than `.lf-ui` and declares that a label inside
chrome-looking structure is still one of the page's words. This lets a tab label
or draft heading remain quotable while runtime controls stay outside the
passage. `relabel` writes the said marker; `offer` writes the control marker.
They are independent facts and neither clears the other.

A label copied off another element on the page is a route to those words rather
than a second place the page says them. Say it once: a contents link, a roster
row naming a worker, any generated index entry stays chrome, and the passage
lives where the page speaks it. Two copies of one label carry the same text and,
being fenced, the same empty context, so neither can be told from the other and
a drag across either detaches.

A route a widget builds outside any control needs nothing further: chrome carries
no offer marker, so no medium takes its words away (`lf-toc`'s rows). A route that
is a control declares itself with `says: "echo"`, `relabel`'s third answer, and
this is the one place the two questions the marker pair answers come apart. An
echo is no passage, and it is still what its row is about: a roster row is a name
and a chip, and a sheet that dropped the name would print the chip alone.
`data-lf-echo` therefore strikes the paper bargain `data-lf-said` strikes — the
press goes, the words stay — without entering the `says` reading. Paper is the
medium that bargain holds in. A copy still divides on the value `offer` wrote: an
echoed route is empty-valued and stays a live fragment link, but an echo on a
`button` would be removed with its words, because the pass that keeps a press's
words in a copy reads `data-lf-said` alone. The first widget to echo a label off a
real press is what makes that reachable, and what teaches those two passes the
third answer.

### Data projections

The page has three kinds of visible words:

- authored prose is in both `says` and `wrote`;
- runtime apparatus is in neither reading;
- projected external or derived data is in `says` and not in `wrote`.

The last kind is a projection, not another source of truth. An id-bearing element in
the version is its seat. `projectData(seat, records, keyOf, render, options)` owns that seat's
children, labels each rendered element with the seat id (`data-lf-projection`) and its
record's stable key (`data-lf-datum`), and marks it generated. With `{nested: true}` it
labels descendants a renderer already placed without reconciling their layout. An
optional `labelOf(record, index)` supplies the human coordinate thread chrome reads;
core never interprets the opaque key. When records came from `watchData`, the `snapshot`
option carries that delivery's source id and revision, including across asynchronous
rendering. Leaf stamps the seat and each datum with that provenance. Records remain the
caller's input; the DOM never becomes another record store.

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
producers. The browser keeps the accepted data revision independently from
`lastEventSeq`, because overlapping poll and POST responses can order the authorities
differently. `watchData(widget, input, callback)` delivers a clone of
`{source, contract, revision, updated, value, origin}` for current, a clone with
`snapshot`, `label`, and optional `lines` for a selected capture, or `null` before a bound current value exists. It
redelivers only when that source revision changes; overlapping reads await the same
in-flight rendering before stamping readiness. Its synchronous time readings refresh
independently of data delivery. Modules
project the result into the authored seat; they do not fetch it, mutate the accepted
copy, or keep a hidden current-value map of their own.

The watcher constructs `origin` from the accepted source binding. `projectData` reads
it from the supplied snapshot; emitters override `originOf` only to add a source-value
path where construction knows that coordinate. The helper writes `data-lf-origin` beside each datum and clears it when an
origin or nested datum retires. The package reference owns the origin fields; no reading
infers them from a datum key or rendered text.

Keys identify facts, not renderings or display strings. They are non-empty strings,
unique within one projection, and must remain with the same logical datum across
refreshes. `render` receives the prior element for the key and may update it in place;
returning a replacement is also valid. Reconciliation retains nodes already in their
place and schedules the shared anchor pass after synchronous projection work.

A selection wholly inside a derived datum captures `{section, datum, quote}`. A datum
projected from `watchData` also captures `{source, data_revision}`. Within that source
revision, resolution looks only for the key under its section. If the original words
still stand, Leaf marks them. If their display changes, Leaf outlines the same datum and
keeps the old quote in the thread. A current-source replacement makes the placement
outdated: the thread keeps its section context and remains in the panel, but it does not
mark or attach to a datum from the new revision. An authored snapshot remains exact.
A missing or duplicate key detaches rather than guessing. Selections crossing datum
boundaries remain ordinary quote anchors because they name a passage, not one fact.

`data-lf-projection`, `data-lf-datum`, `data-lf-origin`, `data-lf-source`,
`data-lf-source-revision`, and `data-lf-gen` are written by
`projectData`, never authored in a version. A custom widget joins through the helper alone; no
consumer names its tag. Export preserves the rendered elements and their labels as a
snapshot, while dropping the scripts that could refresh them. Print preserves the same
readable words. Neither medium claims that the snapshot remains live.

Ordinary action controls use `.lf-btn`, whose shared theme rules also enter
declared shadow trees. Packages may set placement and density, but keep its
shape, border, hover, and disabled treatment. Margin Buttons, reaction chips,
and status labels retain their own forms.

The three visual voices are prose, apparatus, and evidence. Body prose uses the
serif; labels, controls, and annotations embedded in evidence use the sans; and
literal evidence uses the mono face. Typography is presentation, not passage
permission. A chip or code annotation may look like apparatus and still be a
page word the reader can quote.

`renderSaid` materializes words that CSS would otherwise paint through
`content: attr(...)`. A visible word must exist in a text node if the reader can
point at it. Module-generated words that cannot be declared by attribute are
inserted at the correct edge and marked `data-lf-gen`. Do not place a generated
suffix after a control that semantically ends the row.

The two edges are not mirror images. `after` goes inside the element's own words,
because trailing chrome stands beside the last of them and a span past it lands
on the far side of the apparatus. `before` goes at the element's start, because
leading chrome is not something the words stand beside: a module puts one there
to speak for the whole element, and stepping past it renders the element's own
opening words underneath a summary of them.

`renderQuiet` handles facts conveyed only by paint, such as an attribute-driven
status. These words are clipped, unselectable, excluded from clipboard and
anchor readings, but available to assistive technology. `quietFacts` derives
them from `x-paints`. The paint and its quiet reading must agree.

The runtime may inject its own words inside a widget. Comment-note buttons, for
example, can be placed on a text block owned by that widget. A module reading
its slot or body must call `says` so runtime words do not become authored or user
content. Place injected lines on the block or anchored element, not on an
intermediate body node from which a draft editor seeds its text.

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

### Shadow trees

Only open roots declared through `x-shadow` join the page reading.
`pageShadowRoots` enumerates them. `textNodesUnder` crosses those roots,
`pageRange` requests them from `getComposedRanges`, and `upFrom`,
`containsAcross`, and `closestAcross` cross back to the host.

Identity crosses the same boundary. `elementById` searches the document and
declared open roots. `pageQueryAll` clears or queries marks everywhere the
runtime may write. `focused` descends through retargeted
`document.activeElement` until it finds the actual control.

Hit testing asks two different questions. `elementFromPointAcross` and
`markAt` may descend into a shadow root when the exact marked text matters.
`aimedTarget` may keep document retargeting when the host is the semantic item.
Choose the reading by the question, not by convenience.

The page's widget inventory remains the document's declared inventory. Do not
silently discover nested widget families inside shadow roots as new top-level
content. A module that stages a declared widget inside a shadow tree still owes
the visible words promised by that widget's entry. `silentWords` examines open
roots and catches promised words that are absent, clipped, or hidden. It also
catches a module that replaces declared words after the shared render passes.

## Anchors and marks

`selectionAnchor` and the file-side comment capture produce the same collapsed
quote, surrounding context, and section identity. `resolveAnchor` is the only
search implementation. It accepts an occurrence only when full context confirms
one candidate. A quote that occurs once may stand without context; a repeated
quote with no unique context detaches instead of using document order or an old
offset.

The search pattern uses only a bounded lead (`LEAD_CAP`) to locate candidates.
`confirmRest` walks the remainder against passage text. Do not truncate the
stored quote to satisfy a regular-expression limit; the stored quote is the
passage the reader selected.

An element anchor has no text range. `sectionOf` resolves its id and marking uses
visible element parts. Text anchors use `segmentsIn`, `spanIn`, and `rangeOf`.
`itemSays` labels a compact view from an item's own opening words. A decision that
needs a useful row label states it on itself, commonly through an `x-says`
attribute; the row does not infer a heading from surrounding layout.

`paintAnchors` is the only anchor writer. One pass decides thread marks,
element outlines, and the open composer's pending mark. It clears and paints
through the same composed-tree helpers, then records exactly what it drew in
`marked`, `pendingMarks`, and `pendingOutline`. Other features consult those
records rather than looking for arbitrary DOM paint.
The anchor runtime exposes only the questions other features ask — `isMarked` and
`placedAt` — so the pass-owned maps and arrays cannot acquire a second writer through
the entrypoint.

The same pass answers a second question and records it apart. `placed` records at least
`{element, datumElement, exact, status}` for each thread; `status` is `exact`, `fallback`,
or `outdated`. `marked` is what was drawn for it.
They differ for a resolved thread, which has a place and no paint, and for an
element anchor, whose paint is the boxes its contents show through rather than
the element the anchor named. The panel's order reads `placed`, so the list and
the page cannot disagree about which of two threads comes first, and one walk of
the document's text answers both. `renderPanel` therefore paints before it
renders the list. Do not resolve a thread's anchor a second time to sort it.

`paintStanding` is the second reading of that record: the thread holding the
panel's focus paints its own passage apart from every other mark, as
`lf-mark-here` over its ranges and as a class of the same name over its element
parts. It reads the focus, through `closest`, rather than being written where a
travel left the reader — the argument `markHere` makes for the decision ring, and for
the same reason. Every route that puts the reader in a thread therefore paints
it: the quote's press, the `t`/`T` walk, a click on the card, a reply box. A
press on a page mark reaches `showThread`, which focuses the reply box before its
deliberate reveal. Escape returns to the card; `t`/`T` then walk the threads.
`paintHere` repaints it beside the decision ring, and `paintAnchors` repaints
it after rebuilding the ranges it holds.

The panel paints the same fact on the card, through `.lf-thread:focus-within` —
the same predicate, so the two halves cannot disagree about which comment the
reader is in. `:focus-visible` instead answers which input modality should draw
the browser's focus indicator. While typing, the reply box carries the strong
focus ring and the enclosing thread keeps a subdued outline.

`lf-mark-hover` answers a different question — which thread the pointer is
indicating — and reads both surfaces in one frame. A card is the thread's view in
the list the way a mark is its view in the prose, so resting on the card lights
the passage exactly as resting on the passage lights its bounded quote, and a reader
sweeping a full panel is told what each comment is about without pressing anything. The
semantic class stays on the card while its quote takes the wash: a long thread can span
several viewports, while the clamped quote is the panel's compact representation of the
passage. There is one answer rather than two because the pointer is in one place:
`markAt` refuses a point that lands in the chrome, so `hoveredThreadOf` and the page's hit
test cannot both name a thread. Both are read inside `refreshHover`'s frame, which is also
what settles `:hover` — asking for it from inside the pointer event that moves it asks
mid-move — and a second writer to this highlight would be overwritten by whichever frame
ran last.

`body.lf-over-mark` stays with the page's own reading: it is the promise that a press
here opens something, and over a card the press on offer is the card's, which
`.lf-quote` states for itself. `setPanel` asks the question again on the way out as
well as in, because the panel is one of the two surfaces this reads: closing it from
the keyboard, with a hand resting on a card, takes that card out from under a pointer
that never moved.

Hover state keeps both the semantic id and painted card node because reconciliation
can replace one without changing the other. `paintAnchors` rebinds replaced ranges
and element parts; `renderThreads`, page movement, and a version transition's end
refresh the reading when content moves under a stationary pointer.

`paintHover` paints both kinds of anchor, as `paintStanding` does. `::highlight`
paints glyphs, so a box takes no wash; the element mark says the same rank in the
property it has, one weight up from the posted hairline
(`.lf-mark-el.lf-mark-hover`). Without that, an element-anchored comment answered
the pointer with nothing at all — which from the panel, where there is no page
cursor to change, reads as a broken hover rather than as a passage with no words.

Three steps of one wash, because three things a mark can be are three distances
from the reader's attention: `--mark` posted, `--mark-hover` indicated,
`--mark-strong` stood in. The middle step exists because this gesture puts the
pointer over the panel by construction — a hover sharing the standing wash left
the two lit identically whenever a hand rested where it had just clicked. It was
the hover that moved down rather than the standing wash up, because the
measurement in `theme.css` binds in one direction only, so the step costs no
contrast and gains some.

The highlights rank `lf-mark`, `lf-mark-hover`, `lf-mark-here`, `lf-pending`, and
a higher one supplies only the properties it states, so a standing mark under the
pointer keeps its own wash and its own ink and takes nothing from the hover.
Pointing at one comment while standing in another therefore says both, in two
washes a reader can tell apart.

### Reactions

A bare reaction — a token comment nobody has replied to — is paint, not a
thread. `paintAnchors` resolves its anchor like any comment's and records it in
`reacted` rather than `marked`: a wash through the `lf-react` highlight on a
passage, `lf-react-el` on an element's shown parts, and a glyph reconciled by
`seatReactions`. Its `.lf-reacts` span is an unpositioned contribution to the
target's Button cluster; the
pill inside is the reaction's own eraser, posting the ordinary `undo` through
`withdraw`. It wears `lf-ui` and `data-lf-gen`, so no reading takes it for the
page's words. `markAt` does not see it: a reaction takes no press to a card and
has no hover. Export keeps the glyph with its press taken off and writes the wash
into the words as a `<mark>` (BAKE), the highlight registry being script state
no file can hold.

The bar a selection or keyboard-selected item raises is `.lf-fab-bar`: the durable,
compact `.lf-fab-input` followed by one response ellipsis. An explicit item target opens
and focuses that field immediately. Selecting a passage opens the field without taking
focus or collapsing the browser selection; the reader can still copy the selection or use
its native context menu, then enter the field with Comment. The field grows in place and
never transfers text into a second composer card. A one-line note is a pill. A longer one
widens up to a readable 80ch and then wraps, and grows into the available clear band
before it scrolls; its corner stays the pill's 16px rather than growing with the box,
so the corner never reaches over the first or last line. Placement states a float's
room as `--lf-float-w` and `--lf-float-h`; the bar is capped by it and the field's
`--lf-response-room` excludes its neighboring controls. The field's scroll extent
supplies its desired height without temporarily resizing it and losing the reader's
scroll position. When the target fills the viewport, the viewport still caps the field.
When a covering panel leaves no usable band for the response bar, placement withdraws
it without discarding its draft. If the disappearing bar held focus, the visible
Threads list takes it; an unrelated focused control keeps it. A partially exposed
page remains interactive whenever the bar fits its actual remaining room.
Enter inserts a newline; `Mod+Enter` sends. Tab changes the same bar into Comment,
Suggest when the anchor is a quote, and the layer's reaction tokens.
`.lf-response-control` keeps the field and every
choice on one baseline with one type, border, corner, and elevation; the bar keeps its
DOM owner and accessible name while its contents change. Comment restores the field and
Suggest restores it in replacement-text mode. Their structural icons use the same
stroked SVG vocabulary as Target Buttons; only authored reaction tokens supply text glyphs.

`showFab` places the bar; `openComposer` binds its field to the durable draft and takes the
focus decision. Every explicit item and visual route passes its resolved anchor to
`commentOnTarget`, which focuses the same field and carries an unsent draft to the new
target. Automatic passage selection opens that passage's own durable draft without moving
focus. Submitted words still in flight remain owned by their original anchor, while a
later target starts clean and keeps focus. For a page
target, `r` contributes Comment, Suggest where available, and the reaction Buttons to
that target's existing Button options. Those temporary Buttons borrow the cluster's room
and dock with it when necessary; they do not claim permanent rail width. A thread-local
`r` opens the conversation-owned row on the latest agent message.
With none of those targets, it shows “Select something to react to” and opens
nothing. Page-wide reactions remain an explicit ellipsis above the panel's general
comment box. `REACT` claims the keyboard while a list is open. Arrow keys wrap through
every visible Button in the target's shared cluster, including its primary actions and
Page-map overflow; floating and message-local rows walk their own choices. Tab and
Shift-Tab follow that same order. The Page-map dialog remains part of the response's
target context but owns its native keyboard walk and Escape while open. Closing it
restores its exact opener; selecting overflow presses the original Button before its
temporary target is released.
Enter or Space presses the focused choice, digits remain optional reaction accelerators
in declaration order, and a stray key closes the list before keeping its ordinary meaning.

`conversation/model.js` reads the log by `isReaction`, `spoken`, `turns`, and
`bareReaction`, the names `events.py` reads it by, and answers `reactionsOn` and
`reactionStanding` from the fold it last built. The panel lists `conversational`
threads only; a card shows its turns and its root, so a thread that grew out of a
reaction opens on the mark, whose body `conversation/messages.js` writes as the
glyph and its word. `paintReactStrips` puts one reaction surface under each agent
message and marks the latest one `lf-open`, which keeps its ellipsis visible and
makes it the thread's `r` target. Older ellipses appear while the reader is in the
thread. A closed surface shows only standing tokens, pressed and wearing their
word; opening it replaces the ellipsis with the complete list. `paintPageStrip`
builds the explicit page-wide surface above the general box. A token press closes
the list and returns focus to the ellipsis; any standing mark remains visible as
its own eraser.
`awaitsReader` first reads any standing local `x-awaits` or `x-request.decision`
Decision carried anywhere in the unresolved thread; a later plain turn does not hide
an earlier structural Decision. With no such Decision, it reads the latest spoken turn:
an agent comment is a question and an agent reply's explicit `awaits` field marks a
prose request. A `settles` token standing on that latest prose request answers it
without closing the thread.

`scrollToThread` is the one travel every "show me that comment's passage" ends in. Each
nested scrollport first reveals the exact range instantly on both axes without writing the
document's position, then `moveScrollerBy` glides that range to its final position in the
region that holds it. The travel owns no standing or arrival state. Focus already supplies
the durable answer through `paintStanding`, and a transient page effect does not observe,
restart, or reconcile across the browser's scrolling operation.

Use the CSS custom highlight registry for text marks. Wrapping ranges mutates and
splits authored text nodes, can cancel a click between pointer down and pointer
up, and creates a second DOM representation for the passage. `markAt` performs
geometric hit testing over the ranges recorded by `paintAnchors`.

Custom highlights create no accessibility nodes. `noteMarks` adds one hidden,
unselectable button to each block that contains comments and states the comment
count. It names the block rather than copying the selected words. Keep that line
outside selection, quote capture, widget word readings, and clipboard output.

`shownBox` returns an element's own box or the union of the boxes its
`display: contents` descendants paint. `shownParts` returns the visible elements
on which an outline can be drawn. `shownRect` clips the result through scrolling
ancestors and the viewport, stopping ancestor clipping at a fixed-position box.
`clippedRect` applies that same clipping walk to a box already measured from a
Range, using the element that owns the Range as the start of the walk.
Use:

- `shownBox` for travel, bounds, and reading-position landmarks;
- `shownParts` for decision rings and element-anchor outlines;
- `shownRect` for visible placement of floating chrome and address chips;
- `clippedRect` only when the subject has no element box of its own.

Do not read `getBoundingClientRect()` directly when the target may generate no
box. A `display: contents` element reports an origin-like zero rectangle that
does not represent where its contents are. `unmarkableItems` detects declared
items with no visible part on which a mark can land.

A module that needs a number off a live box states the measurement through
`measure(el, take)` rather than taking it at upgrade. A widget upgrades wherever
the runtime connects it, and a message body is connected whether or not the
reader has opened the panel — where every box is zero, `once` refuses the second
upgrade that would correct it, and the body is cached and never rebuilt, so the
zero is permanent and reads exactly like a measurement. `measure` takes the
reading now where there is a box and once more the first time there is one. Its
observation ends at that reading, which is what keeps a written custom property
out of the round that triggered it.

The chrome question takes a bound: `uiInside(el, within)`, of which `inUi` is the
unbounded case. Unbounded, the answer is about the page — a control is the
runtime's apparatus wherever it stands, which is what a pointer or a caret needs.
Bounded at an element, it is about that element's own insides, which is what a
reading of one widget needs: the panel holding a widget an agent sent is itself
`.lf-ui`, so asked the unbounded way every child of such a widget answers yes.
`quotable`, `shownParts` and `settledAway` all take it, and `authored` takes the
same bound on the generated question — so what a mark may hang on, what a
settlement has emptied, and what a quote may name cannot come apart. An area greater than zero is not enough for shown parts
either: clipped note text and hoisted controls can have measurable boxes while
remaining the wrong semantic target.

A control is built by `offer` as the corresponding native element, so activation,
disabled state, focus, and accessibility stay the browser's. The explicit
`selectableOffer` exception is for a page word whose text must remain selectable, such
as a tab name or chosen option; its widget owns the complete keyboard pattern. Both
constructors mark generated chrome consistently. The shared drag guard distinguishes a
click from the mouseup ending an active text selection by comparing the selection's
focus end with the release. It
does not suppress a press merely because an older selection contains the control or
because the pointer landed beside selected text.

`placeClear` fits the response bar into a free band bounded by the viewport,
its target, and controls carrying `data-lf-offer`. A quoted passage keeps its
whole paragraph clear. Placement prioritizes proximity to the target, then
visible writing space; geometry supplies CSS room constraints, while CSS owns
the field's content sizing.

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

Generated rows that switch views keep the same outer box. Controls may give up
ink while retaining their cells. A status item that can appear later reserves
its place for the page's life. When a row runs out of room it gives up whole
controls before it gives up any control's words, and it gives them up to
somewhere a reader can still reach: the banner's row folds the addresses it
cannot hold into one menu (`foldShelf`) rather than clipping them or scrolling
them off its own edge, and its status sentence keeps a floor stated in the row's
own characters so a crowded row can never cut it. The row reads in one order at
every width, and a control the fold has taken is still at its place in that
order.

`syncLayout` derives only floating chrome placement and reservations from current
chrome boxes. CSS owns the document shell: `body` is the named `lf-shell` inline-size
container, `main` composes its left and right claims, and queries grant or withdraw
margin postures. JavaScript may hear the shell's content-box size without deriving a
posture or mirroring cramped state. `layoutSizes` schedules `syncLayout` and page
repaint after a width change. `moveShell` lands the final responsive shell in one pass,
then animates only the reading column's presentation offset and repaints page-attached
chrome along that route. A height-only change sends `pageShifted`
directly so a content reflow re-places document-attached paint without re-running
chrome reservation.

Which question a floor asks belongs to the posture it grants. A floor asking how much
room is left beside a panel or tray is a container query on `lf-shell`: 1152 and 1416
for the sidebar and sidenote strips, 1208 and 1472 for the thread's beside posture. The
living margin's 900 asks the window instead, because it is half of a pair —
`@media screen and (max-width: 899px)` stops drawing the margin at all, and a marker's
presence is not something a container can be asked about without the answer depending on
the strip the marker is asking for. Both halves of such a pair ask the same medium, or a
panel narrowing `body` under the floor withdraws the strip while the window keeps the
markers on screen with nothing reserved for them.

The browser's root is the document scrollport. `pageScroller` is the shared answer for
reading position and paging; native fragments, history restoration, wheel/touch input,
and browser UI all use that same root. Root scroll events are reported on `document`,
while nested scrollports report on their elements. Use `scrollerFor(el)` where a widget
may be one an agent sent, since a widget in a message is scrolled by the panel's own list
and by nothing else. Threads and trays are alternate auxiliary workspaces, so only one
stands at a time. The
strip-taking workspaces—Threads and Asks—take room when the viewport can hold
them and cover the page under their respective media query otherwise; Leaves
always covers because its rows leave this page.
The shell's inline size already reflects the margins a beside panel or tray takes.
`--strip-l`, `--strip-r`, and `--lf-room` are CSS-owned readings resolved on `main`;
`--lf-shell-inset-left` carries the left workspace offset to viewport-fixed page
furniture; `--lf-claim-right` is the project-layer extension claim. A script-free copy
therefore answers the same layout from its own viewport without exporting session geometry.

Both regions fixed to a side of the window are drawn by the reader. `drawnEdge`
is the one implementation: each caller supplies the side its region is held to, a
default width, a floor, the custom property the cascade reads the standing width
from, a store key, and one noun that every surface naming the region says in its
own sentence. Nothing else differs, and no consumer names a region. A handle
carries `role="separator"` with the width it stands at, so an arrow step is the
platform's own announcement. The width the reader chose and the width a region
stands at are separate facts: a window too narrow to honour a choice does not
overwrite it, and a region beside the page is capped at half that window. Ask the
covering media query of the default width and never of the reader's, or a drag
changes the page's posture under the hand making it. Both trays share one width,
which belongs to the side rather than to either tray.

A workspace covering the page is drawn over it and never shown modally: the `<dialog>`
it is built on is only ever `show()`n. Modality makes the rest of the document inert,
and covering is the posture in which the page most needs to stay live — the banner
toggle that opened the workspace is how it closes, the toggle beside it is the other
workspace this one replaces, and the strip of page still showing beside a covering
sheet is still page a hint can name. What modality would have carried is already owned
elsewhere: the covering sheet's scroll lock is the stylesheet's, and Escape is the
ladder's. The surfaces that really are modes of the page — the keyboard reference and
the page map sheet — keep `showModal()` and the backdrop that comes with it. Opening a
`<dialog>` runs the browser's focusing steps at either spelling, so a caller that means
to leave the reader where they were has to put the focus back.

Closing is not the mirror of that. The platform hides the dialog and restores focus at
once but hands `close` to a task of its own, so a reader who leaves a surface and
returns to it in the same breath — Esc off an overflow route and straight back onto the
control that named it — is standing in the next opening before the first one's close
arrives. A handler that tears down the opening's state therefore reads whether the
dialog is open again and gives that reopening its state back rather than taking it: a
`close` overtaken by a reopen has nothing left to close. The state a late close would
have cleared is what the surface is read by, and losing it is silent — the sheet still
stands, still says its name, and the next press inside it means something else.

The same task boundary decides who puts focus back. A surface's own close route returns
the reader to the control that opened it, which is right for a press on that control and
wrong for a keyboard entry: the dispatcher captured the reader's exact place before the
command ran and restores it synchronously, so a return route delivered a task later
overwrites the restore and leaves them holding a door they never touched. A close that
places the reader itself therefore says so, by raising the flag the `close` handler
reads: `leavePageMap` unwinding the dispatcher's frame, so that frame's restore stands,
and the two activation routes that land the reader on the map control or on the control
the row forwards to. A close that raises nothing — the Close button, the platform's own
dismissal — still runs the surface's own route.

A handle lives inside the region it draws, so a drawn region must not be its own
scroll container: a scroller clips a handle straddling its border and carries it
away with the content. A tray is a shell holding a `.lf-tray-list`, and every
tray list reserves the key line's room where their horizontal spans meet. Wide content
reads the shell's CSS value directly; there is no observed measurement loop or second
number system to reconcile during a transition.

The banner and key line reserve their space in normal flow. A fixed or absolute
chrome surface may lie above that reservation, but the reservation itself
travels to print and export only when that medium contains the surface it
serves.

### Target Buttons

The right margin has one projected cluster per page target. Leaf calls its repeated
fitting a Button: like a coat button, it is one consistent piece attached to the
passage, not a synonym for every HTML `<button>` on the page. The cluster is the
single place for controls the reader can use on the target, communications they can
start about it, and standing information such as comment threads, decisions,
changes, or agent activity.

At rest a cluster has a two-Button budget: the primary and one peer, or the primary
and `…` when there are at least two peers. Hiding one peer costs the same fitting as
showing it and adds a press, so it is not overflow. With no contributed control,
standing information supplies the primary Button in the fitting declared by its face.

The expanded budget is six fittings, including the primary or visible reading marker
where one exists; a target made only of peer choices uses all six. A larger set shows
the Buttons that fit and a final Page-map Button whose label gives the remaining count. That opens
the existing Page map at the first excess action; every excess control has its own
named row which performs that exact action. Do not grow another popover for overflow.
The same limit and exact-action route apply when the cluster docks on a narrow screen.

An engaged contribution exposes its peers within that budget. Engagement is the
owner's semantic interaction state, not DOM focus: an open editor, for example, keeps
Save and Cancel exposed until either action ends the edit, even if focus moves within
the document. An unsettled reader action engages the whole target in the same way,
keeping its delivery lifecycle visible until the handoff settles. An engaged set has
no `…`; completion and escape actions take the first fittings, so the density limit
cannot hide the way to finish or leave the active interaction.

Keyboard arrival unfolds that same cluster immediately: Tab into any of its Buttons
replaces `…` with the expanded set, and Left/Right wrap through those visible
Buttons. A pointer press on `…` makes the same replacement and lands on the first
revealed Button. Escape folds that temporary expansion, restores `…`, and returns
focus to it; moving focus or the pointer outside folds without taking focus. None of
those routes folds peers required by an engaged contribution, and moving into a modal
or thread surface the cluster opened does not count as leaving it. The cluster uses
one temporary expansion state for both keyboard and pointer routes; focus does not
create a parallel presentation. A category walk that lands on a Button does not unfold
its peers: it is navigation rather than Tab arrival, so one Escape still lets go of the
destination the walk put down. A numbered Page-map address arrives the same way and
then presses that Button, so anything unfolded there is the press's own result rather
than the arrival's, and Escape still lets go of where the press left the reader.

An unsettled reader action reuses that same Button rather than growing a status row
inside authored content. Its information face advances from **Sent** or **Waiting for
pickup** to **Picked up**, then to **Active** only when a typed local claim exists; an
acknowledgment keeps the same retained target cluster throughout that live handoff. The
first three phases report a move already made, so the Button wears the flat `status`
behavior below. **Active** raises it back into a disclosure. Once no receipt or claim is
live, the generated Button disappears; the widget and action projection carry the
durable state. A thread's existing Thread Button remains the page-edge route to the
exact receipt in the full conversation; an **Active** claim joins that engaged cluster
as an exposed peer. A standalone page-widget claim gets an **Active** Button directly.
When no page edge exists—inside the full thread panel or a widget frozen into
conversation chrome—the compact `.lf-receipt` remains the local fallback.

Content modules contribute through `registerMarginItem({key, target, controls, subject,
state, ...})`; they own their verbs and events, never placement or control styling. `key`
is stable within a target. Optional `subject` is a string or live reading of the concise
semantic subject used to name that target away from its own paint. Supply it only when
plain text concatenation loses a relation the widget paints visually, such as a rewrite's
`old → new`; contributions at the same target must agree. `state` is a value or live reading of `idle`, `engaged`, `busy`,
`failed`, or `settled`; active states keep the owner's peers exposed. A contribution
item that sets `represents` and names its
`kind` is also the visible reading of that state, so the margin suppresses a generated
reading of the same kind at that exact target rather than showing the fact twice.
Every fitting in a contribution is built with
`marginButton(control, {key, icon, label, context, behavior, tone, role,
state, writesRelation, writesSeat})`; an authored reaction can supply `glyph` instead
of `icon`, never both.
That is the one RHS control type: it owns the circle, size, type, focus, state paint,
and glyph/word anatomy shared
by decisions, editing, communications, and information triggers. Its behavior states
what the fitting promises. Behavior, tone, and state are independent axes: never
use a heavier border to mean positive, busy, selected, or complete.

`marginButton` also establishes the canonical Button record: key, face, label, context,
behavior, tone, role, lifecycle state, and the relation writer the
call declared. The record carries that last one because the options group rebuilds a
proxy Button from it, and a proxy that re-inferred the default would write a relation
its source has no writer for. Registration assigns its stable owner and
rejects duplicate Button keys within that owner. The compact rail and complete Page map
both render from this record; neither infers semantics by scraping the contributor's
painted DOM. Transient native state such as disabled and `aria-expanded` is mirrored
onto a retained proxy, while the original contributor control remains the only
activation owner.

- `action` has a uniformly heavier ring and a small lower shadow, carries an imperative
  verb, and performs its effect immediately;
- `disclosure` has a firmer single ring than status and the same paper surface. It carries
  `aria-expanded`, reveals or hides context without settling it, and includes the
  generated More Button whose ellipsis is its whole face. `marginButton` writes that
  attribute's default unless the call says `writesRelation: false`, which declares that
  another writer decides the disclosure's relation — the margin's own readings, whose
  `aria-controls` and `aria-expanded` are settled together from whether the reading opens
  a thread. Two writers over one attribute say something different each pass, so no
  record of theirs restates anything while the document's disclosure watch reads the pair
  as news. `writesSeat: false` says the same thing about the control's `tabindex`: the
  rail's roving stop writes every row's seat on the frame after each pass, so a marker
  that seated itself here would have the next pass contradict it. The two are declared
  apart because they part on the reading options, which stand outside the rail's walk
  and own their own seat while another writer owns their relation;
- `status` reports a move already made and offers no press. It keeps its icon and its
  circular Button silhouette and seat in the cluster on the page surface with a ghost
  keyline, but gives up its raised edge, hover response, pointer, and tab stop. It remains a
  `status` in the accessibility tree so the Page map can still land there and name the
  phase. Status is live-session information, so a copy drops it.

A generated reading wears more than one of those over its life — a Thread Button while
there is something to open, a status once the move is reported — and one element has to
carry both, or the seat moves under a reader standing in it. Such a control is therefore
a span, since a `<button>` cannot stop being one, and the activation the platform then
does not supply is declared by the page map's own scope (`margin.press`) rather than by a
listener on the control: a key the register does not hold is a key no surface can
promise.

Material and ring weight distinguish immediate actions, disclosures, and statuses:
Action is raised, Open is outlined, and a read-only report stays flat behind the palest
ring. Their resting interiors all use the page surface, so fill does not imply that a
status is selected or pressed. The shape stays shared, with no added mark. A lone
non-thread informational Button reveals
its target directly. Each additional non-thread reading gets its own peer Button under `…`;
pressing one reveals that reading directly rather than collecting readings in a card.
All threads at one target share one Thread Button and one conversation card. That card
opens only on a press, never merely on focus or hover; when the document cannot leave
it room beside the source, the same press opens the full Threads surface. The thread
card is the only generated contextual pane, not a generic container for alternatives.

Tone is `neutral`, `positive`, or `negative`, expressed through icon color only;
rings, fills, and state marks keep their shared neutral treatment. An interactive
Button's state has a separate small corner mark: a dot for engaged, an open moving ring
for busy (static under reduced motion), a diamond for failed, and a square for settled.
The mark is enough to state that a Button is busy, so the Button itself stays at full
opacity and keeps its pointer. Busy also sets `aria-busy="true"`; failed and settled
actions need visible words, not color or shape alone. A status's phase is its transient
hover or focus label instead of a corner mark. Standing reactions reuse the settled
square in their margin palette and seated marks, so they remain distinct from hover
without changing the shared ring or fill. Reaction toggles retain their vocabulary labels and `aria-pressed`;
withdrawing a token returns its palette Button to idle.
`marginButtonState(control, state)` changes that axis without changing the verb, ring,
or tone. Built-in faces use the shared monochrome SVG vocabulary with `currentColor`;
emoji and font-dependent symbols are not structural icons. Reaction glyphs are content
declared by the layer and retain their declared vocabulary order.

Ordering is semantic, not registration or DOM order. Active contributors rank failed,
busy, then engaged; ordinary contributors follow. Within that order, roles rank
`complete`, `escape`, `primary`, `secondary`, `reading`, then `overflow`. Stable
contributor and control keys break ties. The primary is the first available contributed
control; generated readings follow direct controls, and a temporary communication
palette keeps its own keyed order after those readings. Reordering a module's setup
must not move an unrelated action into the primary fitting.

A failed mutation leaves **Failed · Retry · Cancel** at its target. Retry makes a new
attempt only after a definitive refusal; an ambiguous transport result stays busy
while the outbox retries the same attempt. Details is a disclosure only when there is
useful detail to show. An editor retains the user's text; typing again returns from
failed to engaged. Reversible actions normally act immediately and offer Undo, which
withdraws the named logged gesture under the same authored-version, replayability,
and pending-delivery guards as keyboard Undo. Confirmation is for a genuinely irreversible
effect, not routine Save or Accept. Settled outcomes are visible receipt text beside
an active Undo or context disclosure: never leave an inert Button-shaped status.

The Page-map keyboard scope owns the cluster's way back out. When a thread card stands
over an unfolded `…` group, Escape closes the card first and folds the secondary Buttons
on the next press; each rung is named on the key line before it runs.

A gesture that unfolds a cluster for its own use puts that fold back, and only that one:
putting the reaction choices away folds back the cluster the raise unfolded, so a disarm
over a reply strip or over a fold the reader opened themselves takes away no layer the
gesture put on. That put-down folds without claiming the focus — it runs from wherever
the reader is standing, so taking the focus would throw them onto a cluster they may
have left, and would send a press already on its way to a Button they were not standing
on.

Every Button-shaped fitting keeps one circle. Its label appears as transient chrome on
hover or keyboard focus without changing the cluster's geometry. An open
disclosure suppresses the label because the context it opened now names the Button's
result. A disclosure label ends in an ellipsis because it opens something; action and
status labels do not. A status may add a quieter context line, such as how long ago its
phase began. The complete label remains in the DOM, and
its accessible name tracks the control or status.

A marker's accessible name also carries where it stands in the walk: which location of
how many, and how far down the page. That is how a reader listening places it, and it
belongs to the name alone. Painted beside the phase, the same words read as progress
rather than position.

Hover or focus on any interactive fitting illuminates its exact target, including a
cluster displaced by packing. Hovering a status shows its label and connects it to the
target with a softer neutral trace, without lifting the fitting or borrowing the accent
ring that promises interaction. A numbered Page-map arrival may still focus it and
illuminate the target deliberately. Labels stay inside the viewport without moving the
fitting.
Dense and narrow-screen tests must exercise that association and activate an excess
action through Page map; counting hidden DOM nodes is not evidence of reachability.

The living margin groups contributions and state readings by exact target identity,
chooses the primary, and owns the generated disclosure and `…` Buttons plus the
cluster's accessible group name. At wide widths it hoists that host into the main
positioning context, preserving source and tab order when several targets share a
top-level block. At compact widths it returns the host to flow immediately after the
target's rendered text block (or the target itself). Adding another target action must
not add another absolute row, control type, or rail measurement.

Each render reads once which contributed controls paint, and it does not take that
reading on paper. Print takes every injected control out of the page, so the reading
comes back empty there and folds every cluster to nothing — the medium written down as
the page's state, standing on screen after the print preview closes. A render asked for
while `print` matches is refused whole and taken once the screen is back. It is the
thread list's head-room rule on the layer's other measuring surface: a reading taken
where the box is `display: none` is not a measurement.

That ordered target collection is the Page map's complete location count and the source
for the `g m` address list. A location's disclosure Button announces its position in the
complete collection. The numbered chord exposes up to nine locations in the visible
window, starting at one. `g M` and the banner's Map control open the complete sheet,
which projects the same currently available contributed controls in owner and role order,
plus readings that have no direct control. An offered reading that merely describes its
owner's controls is omitted there rather than becoming a parallel “open action” beside the
real verbs.
Ordinary entry focuses the sheet's filter, so a large map is searchable by Button name,
concise target name, or the visible passage containing that target without tabbing through
every preceding action. A spill opens this complete sheet focused on the first control the
compact cluster omitted; it does not make a smaller overflow-only menu.

Live reconciliation retains the DOM identity of each surviving Button and each of its
hit-tested descendants, including a count badge. State-feed refreshes can arrive between
pointerdown and pointerup, so rebuilding an unchanged face would cancel the browser's
click even if its replacement had identical markup. The open Page map follows the same
rule for its groups and action proxies; a refresh updates their meaning without replacing
the control under focus or a held pointer.

A thread card names the target without offering a second route to the panel the banner
already opens. At wide widths it is the conversation itself, measured eight pixels
beside the pressed Thread Button in the same turn it is shown or changes size. While
that Button keeps focus, `c` enters the card's one reply box; several roots leave the
destination ambiguous and preserve the page's ordinary route to the panel. Replacing an
open panel waits for the column's workspace motion before choosing the card posture. When the
document cannot leave the card room beside its Button, the press opens the full Threads
surface instead.

Every live page may grow a page-edge Button — an anchored comment can arrive on one
made entirely of prose — so the living margin reserves the rail as it is built and
never gives it back. The runtime states that reservation as `data-lf-rail` on the root,
and the cascade spends it there; neither reads what is standing in the margin, because
a row's placement depends on the strip it would be answering about. A copy takes no
gestures, so the bake drops the reservation unless a margin item survived into the file.

`margin-layout` places, packs, docks, and measures the complete host. Its rail claim is
the widest stable contribution seen over a floor of the generated marker's own fitting,
and is monotonic for the document's lifetime, so neither settling an action nor taking
one back shifts the readable column. A first contribution wider than that floor still
widens the claim once; `reserve` is how a contribution declares that width in advance.
A temporary contribution registers with `claim: false`: it borrows available RHS room
and docks the complete host when it cannot fit, without moving the column on first open
or leaving blank room after close. A stable contribution whose future primary and `…`
fitting is wider than its resting one declares that pixel width with `reserve`; the
claim includes it before the control changes. Below the margin breakpoint the complete
host docks into flow. Visibility and vertical placement read `shownParts` and
`shownBox`, not the target's raw client rect: a project may set `display: contents`
while its rendered descendants remain usable, and a collapsed target has no rendered
part to offer.

The `r` key unfolds this same cluster's secondary Button group for a page selection or
item and shows the declared reaction Buttons together within the six-fitting budget.
Comment and Suggest retain their separate `c` and compact response-bar routes rather than
displacing reactions from the mode that explicitly asked for them. The digit register and
visible choices therefore name the same complete set. The choices do not widen the rail
or open a separate palette below the target. The compact response bar's Tab state stays in
that bar. Conversation reactions remain in
their conversation-owned strip. The event still carries its durable authored anchor,
while the temporary item resolves selected text to the first rendered block, matching
the target where replay later seats its standing reaction.

### Presentation and state motion

Arrival is not a gesture. Restored panel, tray, drawn-width, design-mode, widget,
and reading-position state appears at rest. `motion` finishes Web Animations
immediately before `data-lf-presented`; theme transitions use the same
presentation stamp. `ARRANGEMENTS` declares each stored runtime arrangement the
render suite must visit. Add a new remembered surface there when the surface is
introduced.

After presentation, changes that remove a visible unit use a short fold. The
semantic state is true at the start of the fold, while the old pixels collapse
so the eye can follow them. Reconciliation, not the originating press, owns the
fold because the same change can arrive from another tab or the agent. A
resolved thread leaves the open-thread vocabulary at once, folds in place, then
moves under the resolved disclosure.

Projection composes the complete final state before rendering. Ordered containers
measure once around that composition and show one FLIP from the current layout
to the final layout. A live drag defers the whole correction.

Finite animations delay final geometry reads. Infinite ambient animation, such
as the status indicator, does not. `moving` is the render gate's shared reading
of that boundary. A component that animates forever must not appear in it; a
state transition that can still change boxes must.

The movement tests ask both paths that can shift a target:

- press a control and compare the rest of its line;
- let news arrive and compare all persistent chrome controls.

A pixel diff is required for borders, outlines, and shadows that can paint
outside unchanged rectangles. Box comparisons alone cannot see those changes.

### Width, frames, and overflow

Text may break at any character needed to keep the page inside its column.
`overflow-wrap` is inherited from the page. Any token that must remain one unit,
such as a small badge or key chip, declares `white-space: nowrap` locally.
Test long identifiers and paths, not only ordinary prose.

A wide widget reads the room declared by `x-wide`:

- `box` fills the available box and clamps its contents there;
- `drawing` may size from its source up to the room available to it.

`markDeclared` exposes this declaration and CSS computes room after chrome strips and
claimed margins. A drawing inside a framed box uses that box's room,
not the outer page's. Size the widget's box with `contain: inline-size` where its
contents would otherwise make the box itself wider.

Every box that frames authored block flow declares `--lf-frame: 1` where the
frame is drawn. The declaration may belong to a nested-state selector or a
generated internal box rather than the tag's base rule. Widgets with
`x-content: prose` or `items` can admit authored flow; data-only, empty, and
inline widgets do not automatically owe a frame declaration.

The shared style query trims the outer margins of the first and last
non-generated children inside a frame. It ignores `GENERATED` because a
positioned pick mark or clipped spoken word must not become the visible content
edge. A transparent wrapper that lets a grandchild's margin collapse through it
declares the frame at the wrapper level only when it is the boundary responsible
for that flow.

`trappedMargins` reads computed layout in the browser and reports a framed box
whose visible inset exceeds what its own padding states. Flex and grid item
margins are placements rather than collapsed block margins and are excluded.

Overflow is acceptable only when the reader can reach it or the box explicitly
signals the cut. A scroll container may expose content in its scroll direction.
`text-overflow` may signal omitted text. Plain clipping does not make content
reachable. `misplacedBoxes`, `clippedControls`, and `coveredWords` enforce
the distinct geometry, interaction, and text consequences.

`squeezedTables` reports a table that scrolls sideways with a cell in it wrapped.
A scrolling table's columns are all at their longest unbreakable run, so a cell
wrapping there wraps at a word a line — beside a name that could not break (an
identifier written outside `<code>`, a bare URL), or because the table has more
columns than the measure holds. A column wraps when it stands wider with
wrapping turned off — its content asked for more than its longest run — which
hidden content, laid out on demand but size-contained, cannot change. The
finding lists the wrapping columns with their widths, names the widest, and
leaves the diagnosis to the author. A table that scrolls with nothing left to
wrap is the theme's honest third case.

`tinyBoxes` ensures each declared widget upgrades to a usable box.
`unreachableWords` catches rendered words outside reachable flow.
`misplacedBoxes` asks each container's actual overflow behavior. Do not exempt
a box merely because an ancestor declares `overflow`.

A box that scrolls contains what it scrolls. Out-of-flow content inside a scroll
container that is not a containing block is positioned against the page instead:
the scroller neither carries it nor clips it, and the page grows a scrollbar
reaching for a box that belongs to the scroller. The runtime hangs a word clipped
to nothing inside the block each comment lands on, so a comment on the far column
of a table wider than the window scrolled the whole page sideways. The runtime
answers for the word it hangs: the sweep that gives every scrolling box a tab
stop (`reachScrollers`) marks each static one `data-lf-holds`, and one theme rule
positions the mark, in the document and in every declared shadow tree. It reads
the composed box, so a page author's scroller and a package's are held on the
same terms as the theme's own, and no stylesheet declares a position beside its
overflow for the word's sake. The mark is written when a sweep reaches the box —
at upgrade, on a new version, and on the panel's reconcile — so a
scroller a module builds outside its own settlement owes the `reachScrollers`
call it already owes for the stop.

### Forms follow authored content

A widget derives its visual form from content when the content already states
the distinction. `lf-options` is cards when options contain titled arguments and
rows when they are bare labels. Do not add a second layout attribute that can
disagree with that markup.

Rules specific to one form include the form predicate in their selector. Avoid
general rules followed by a reset for the other form; specificity can leave the
wrong state partially active. A rule stays general only when its effect is true
in every form.

Row prose must remain prose. A table layout may create an anonymous cell around
mixed inline content without inserting a wrapper that changes authorship or
spacing. Flex gaps applied to raw inline children can turn authored spaces into
layout gaps and split code or emphasis into separate items. Joined answerable
rows keep their complete width inside the group's border with
`box-sizing: border-box`.

Whether a group is answerable is independent of its form. The presence of
`choose` gives the whole group a visible control boundary in cards and rows.
Each form chooses its presentation, not whether the page admits a response.

Joined into one control and standing alone are a second axis across that one,
and the rule above holds on it too. The group declares which side it is on
(`--lf-joined`) and the rules that dress an option standing alone sit under that
style query, because half of what decides it — the medium, and a copy's class on
the root — cannot go inside a `:not()`.

A group joined into one control has cells, and its children arrive from every
layer: the authored options are the author's, while the option the reader writes
and the Done press are the runtime's. Each brings the spacing it wears standing
alone, and the grid stretches all of them to the same column whatever they were
written as.

The reader's cell is an add form dressed as an option. It creates and selects a
real generated option through the same absolute `choose` state as the authored
options; it is not a conversation seat. What it is for is the answer the menu
hasn't got, so it takes the cells' fill and their column and states no inset of
its own. A cell that dresses as apparatus tells the reader to skip it.

So what every cell owes is said over every child, and only what one kind alone
answers is said by naming it. Block margins are zeroed for all of them, because
the hairline is the whole of what separates a cell from the next; the inset each
holds its words off the frame by is a floor at zero specificity, which any cell
with an answer of its own outranks. Naming kinds is how three children got their
margins reset and the fourth kept an 8px band under a line already separating,
and how the question got no inset at all. Reserved columns the cells share, such
as the room a keyboard address stands in, are named once and read by everything
that opens at them — including the forms the frame never reaches, since a
settled group reserves the same column on the cards behind its disclosure.

### Typography and scoped chrome

Typography follows [Data projections](#data-projections). An authored `lf-note`
inside `lf-code` takes `--sans` because the module presents it as a review row
inside evidence; its words remain selectable page prose. `.lf-ui` also reads
`--sans`. Form-control normalization lives in the `lf-reset` cascade layer so an
unlayered semantic type choice can override it without specificity contests.

The runtime's private stylesheet is one `@scope` rooted at `.lf-chrome`. Private
class names do not escape that root. The global vocabulary is deliberately
small: shared `.lf-ui`, `.lf-btn`, `.lf-pill`, `.lf-address`, `.lf-skip`, and the
markers the runtime paints on page elements. Adding a global selector widens the
widget contract and must be covered by the render suite.

`--aim-floor` is the smallest box the layer offers a reader to aim at, on either
axis, and the one thing a coarse pointer changes about it. The query is asked
once, in theme.css; every rule that states the floor reads the token, so a
control joins both answers by joining one of them.

A shared class owns only the look shared on both sides of the scope line.
Placement remains with each surface. For example, an address chip may share
type, border, and color while a reply box and an option reserve and position it
differently.

Use `inChrome` when the question is whether an element belongs to the runtime's
document layer. Use `.lf-ui` when the question is whether words or styling are
runtime apparatus. Use `data-lf-offer` when the question is whether something is
an injected control. These markers are not interchangeable.

Anything acting on where the pointer or the caret is needs both of the first two,
and `pageWords` is that conjunction. Either half alone leaves a hole a widget in a
message falls through: a declared label is nearer than the panel and answers the
apparatus question for itself, so `.lf-ui` alone let a drag across a question an
agent asked read as a passage of the page and write an anchor onto a widget id no
version holds. File capture already refuses that, and file capture is the reading
that promises less.

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

Binding spelling is canonical: modifiers are ordered `Mod`, `Alt`, `Shift`, and
single-letter keys are lowercase. A produced punctuation glyph carries no Shift
prefix because the keyboard layout owns that modifier. Validate that form when a
scope enters the register and compare canonical identities when checking ownership;
modifier order and letter case do not make distinct presses in the dispatcher.

### The keyboard is a stack

A press that takes the reader in pushes one layer. Escape pops one. The way out
is therefore as deep as the way in, and the reader walks it back without having
counted: three presses in, three Escapes out, each giving up the press that
earned it.

A command that enters a temporary surface declares one `returnFrame`. The dispatcher
captures the reader's exact focus or reading block before it runs, and pushes the frame
only after the declared layer is active. Escape closes that frame and restores the
captured place. The command may reveal containing chrome and focus its destination in
one transaction: `c` from the page opens and focuses the page-comment box, and its one
Escape closes that whole entry because the panel is the box's container, not a second
destination the reader requested.

A frame is active only while its owning surface still stands and the reader remains in
the layer it entered. A latent filter value or mode flag is not enough: closing a panel or
leaving a widget must retire its frame so core Escape cannot advertise or mutate hidden
state elsewhere on the page.

Two independently requested entries remain two frames. `g T` enters the Threads list;
`c` from that list enters its page-comment box. Two Escapes return first to the list and
then to the exact place and workspace `g T` displaced. A filter or other state entered
inside a surface gets its own frame or its control's own nearer Escape step. Never infer
the inverse of a keyboard entry from whatever panels happen to be open afterwards.

A bounded mode may instead own its complete entry, nesting, cancellation, and origin
machine inside the one scope that claims the keyboard while it stands. Help, the `g`
address window, item selection, page search, and reactions use that form. Such a mode does
not also push a command frame. What is forbidden is the middle state: opening with an
ordinary `run`, then asking a shared scene inspection or unrelated outer scope to guess
what Escape should restore.

Landing focus in what a press opened is arrival, not a second layer: a tray on
its first row, the versions menu on a version, the panel on its list, or the comment
box `c` named. A later command into a different mode is another layer. The reference's
search box is part of its one complete mode because `HELP` owns the whole keyboard while
it stands; its letters were never the page's to take back.

The rule holds for a sequence as much as for a surface, where the stack it is
about is the reader's rather than the dispatcher's. The address chord arms on
`g`. A panel mnemonic exchanges that window for its destination, so `g T` leaves
the Threads panel as one Escape rung. A document-list mnemonic narrows the
window instead. Each hint keeps its complete route, such as `g h 1`; `g`
starts blue, then `h` turns blue in place when it is pressed. Escape returns to
the destination menu before another Escape closes it.

A layer also owes a way out at all, over the same page the way in is live on.
`versionsOffered` (there is a menu) answers for the destination, the mode standing over
the page, and the button; `versionsToWalk` (there is somewhere to step) answers
for the menu's own scope. One predicate for both left `g V` opening a menu on a
page whose way out no scope was live over. Where the platform owns the dismissal
the mode's own rows still have to be live over the same page, since a mode with
no live row is a claim the surfaces never hear. A section merges the rows of
every scope sharing its title, so a contributor the page hasn't got must bring
none — `merge` drops it — or the two capabilities cannot differ in liveness under
one heading.

A press may deliberately leave layers standing while moving focus outside them. That is
not an Escape rung, because it gives no layer back. The address chord states what remains
open: beside the document, `g p` returns from the thread panel to the document and keeps
both the panel and its narrowing. A panel covering the document cannot make that promise,
so its ordinary Escape rung remains the route back.

### Item selection is explicit

Normal reading mode leaves a plain click on unadorned authored content to the browser.
Visible native and Leaf controls keep their click actions; text selection targets words.
Alt-click, `s`, and a visual's “Respond to…” proxy are explicit Comment gestures. They
pass the target from `aimTargetAt` or the visual provider to `commentOnTarget`, which opens
the compact field and focuses its cursor in the same transaction. A whole item or picture
names its authored id, while a visual part adds its declared token. Tab exchanges that
field for choices in the same bar and focuses Comment first. Tab, Shift-Tab, and the arrow
keys then wrap through every choice. Comment and Escape restore the field; Escape from the
field hides the draft. The same anchor resolves both states against the target's geometry.

The short, viewport-local hints form a prefix-free tree over one alphabet. Most targets
cost one letter; only the tail branches when the viewport holds more targets than the
alphabet. Unlike `g` addresses, these hints are ephemeral and make no promise across a
scroll or revision. They are the whole route, so none may be dropped because its chip
collides. Each chip begins at its target's visible top-left corner. A target whose visible
box is strictly smaller and fully enclosed by another target steps its chip right once per
enclosing box. If that position crosses the key-line band and the target has visible room
beside it, the chip moves into that room; otherwise it moves above the band. An ancestor
and descendant with the same visible box name one target: the innermost remains, matching
direct aim. Equal boxes outside one containment chain stay at the same depth, and the
collision pass separates their chips without inventing a hierarchy or moving them beyond
the viewport foot. Membership is fixed for the length of a scroll and re-read once it
settles, so a target arriving mid-scroll is named at rest rather than on the frame it
appears.

Tab and Shift-Tab walk the visible target map and announce each item. Enter chooses the
last one announced. A viewport change that removes or renames that target clears the
announced choice before Enter can act on it.

`/` opens a real search input over the whole page reading, either directly from the page
or from the visible item hints. Tab walks repeated occurrences and Enter makes a native
browser Selection from the active match. Escape returns to the surface that opened search:
the page after a direct `/`, or the visible hints after `s` then `/`. The mode keeps `?`
available and claims the rest of the page's keyboard while it stands.

The return stack records entry history; `rung()` is only the fallback for state reached
without a registered entry, such as a pointer-opened panel or focus the reader moved by
ordinary traversal. A keyboard command with `returnFrame` never asks `rung()` to guess
its inverse. Moving within an entered surface—`t` walking from the Threads list to a
thread, for example—does not push another frame, so Escape still returns through the
entry that opened the surface.

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
walks open asks. Keep these as single-key presses rather than prefix sequences; a walk
is often repeated or held. While the reader stands anywhere in an Ask, its widget's
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
[Go-to chord](#go-to-chord) uses case to separate complete destinations from numbered
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

Standing in a surface is where focus is, not merely that the surface is open. A
tray's or panel's own button lives in the banner, so opening by pointer leaves
the reader outside it, and a key, a Tab or a click on its contents is what puts
them in. Inside a text box the letter is a character, Enter writes a newline, and
arrows move the caret. The typing scope claims those text-editing keys, so a reader
reaches a surface's letters and walks from its list rather than from its composer.

Core registers scopes through internal `keys(el, title, rows)`; package widgets receive
the same register as `commands(el, title, rows)` in `connectedCallback`. A module loaded
on a page with no instance must contribute
no scope or help section. Runtime scopes live in `SCOPES`; `merge` is the only
function that gathers scope sections. Preserve the order of that list because
the dispatcher and key line walk inward to outward while the full reference
groups the same scopes for reading.

A row has these meanings:

- `keys` is a binding or computed list of bindings.
- `label` optionally overrides the compact keycap in the command's own scope. A keyless
  Decision command falls back to its `decision` action name in the complete reference.
  An Ask instead shows the resolved binding beside that separate action name, so an
  inline hint always says what the reader actually presses.
- `control` is the visible element that activates the capability. `decision` is a
  non-empty action-name string or a function returning one; it includes that command in
  its containing Ask. The row may carry an existing `address` and has zero or one live
  binding. A keyless decision command receives its contextual number from the Ask
  projection. Routes may carry the same fields when one row describes a parameterized
  family of controls.
- `does` is the sentence for the press, or a function when the current state
  changes the sentence.
- `when` says whether the capability exists. When a destination surface is available
  independently of its members, its row stays live and opens the surface even when the
  collection is empty. Member-dependent rows use the collection as their capability.
- `at`, expressed by the current `readerIn` predicate, says whether this press
  can act at the reader's current position.
- `run` performs one result. A run-less row names a press it does not make: the
  platform's own on a link, or one another scope's row already runs.
- `returnFrame`, when the result enters a temporary layer, returns its `active`, `close`,
  `does`, and `line` contract. The dispatcher captures the origin before `run`, validates
  the descriptor, and pushes it only if the layer is active afterwards. Do not call the
  return stack from a command or restore focus in the command's close path; declaring the
  frame is what makes keyboard invocation and reference invocation obey the same stack.
  A command surface that already displaced the reader, such as the modal reference, passes
  its saved origin into dispatcher invocation instead of letting a closing implementation
  control become the origin.
- `native: true` performs `run` without preventing the platform default. Use it
  when Leaf must change state before the browser completes the same press, not
  to leave an otherwise owned press half-handled. It still follows the ordinary
  `repeat` policy; declare `repeat: true` when repeated keydowns must also run.

`live` answers the declared liveness once for every projection. Do not repeat a
guard inside `run` if the guard changes whether the key should be shown. When
the reference needs to describe a page capability while the key line needs to
promise an immediate press, keep `pageHas` and `readerIn` separate.

`checked` validates declarations when they enter the register. `activeRows` also
refuses two live meanings for one binding in the same scope; rows may reuse a
binding only when their `when` predicates make the states exclusive. `parsed` and
`answers` share the supported modifiers `Mod`, `Alt`, and `Shift`. Unknown modifier
names are errors rather than bindings that accidentally fire on a bare key. `spell`
is the one platform-aware display of a binding. `PRESS` states the native key
behavior of controls, and `DISCLOSE` reads the whole set a disclosure answers off
the element it is asked about; links retain their platform distinction from buttons.

A label names this press, not the broad feature. Prefer "Comment on selection"
or "Hide comments" to "Comment" or "Toggle". Compute the word through `word`
when visible state chooses the sentence. Repaint through `paintHere` when any
fact used by a word or liveness predicate changes.

### Scope and dispatch

Scopes nest by focus. `scopesFor` produces the active stack and element scopes
are spliced where their elements stand. The dispatcher walks innermost first.
The first live row answering the event runs, prevents the platform default when
it owns the press, and stops. A `native` row runs and stops the scope walk but
leaves that default intact. A focused widget may shadow a page key without either
scope naming the other.

Leaf must not block standard platform or browser shortcuts. A handler prevents a default
only after a Leaf command owns the complete modified press; secondary clicks and the
native context menu remain the browser's too.

`claims` lists platform keys a scope consumes even when no registered row answers
them. A text entry scope uses `takesLetters` and claims character keys plus the keys
that edit that specific control: Enter, deletion, caret movement, Home/End, and page
movement. The claim follows the base key through modifiers, so Shift+Arrow selection,
Alt character composition, and Mod editing commands remain native. It does not blanket
radio, checkbox, slider, Escape, or unrelated function keys merely because they are
form-related. An exact element scope is nearer than that claim, so a wired textarea
keeps its own Escape or send row; the typing claim then stands before any scope on an
ancestor widget. This ordering lets a widget contain an editor without taking letters,
newlines, or caret keys from it.

One box inside another scope states only what it does differently. The find box
registers its Escape and Enter on the exact input element, so those rows stand
before the command return frame; that frame stands before `TYPING`, and the general
text-entry claim stands before any ancestor widget. Escape therefore lets a live query
go, then leaves the box through the `/` frame, then leaves the panel through its entry
frame. A plain composer with no control-specific Escape goes directly through the
command frame instead of paying a generic “leave the textarea” step the entry never made.

A keyboard-entered box hands the reader back through its captured return frame.
`boxReturnFrame` and `standingConversation` climb the same conversation relation, so
“comment on the thread” going in and “back to thread” coming out name one element.
The panel's general box returns to the Threads list when it was entered there, and to
the prior page place and workspace when page `c` entered it directly. `backFromBox`
remains the fallback for Tab or pointer arrival, where no keyboard entry exists to
restore. A page-owned first-message seat has no standing place of its own; a widget
control that explicitly enters its box supplies the caller-owned return target through
`landInConversation`.

A key may repeat across nesting scopes to mean the same intent in context. `c` reads
that way: from the page it enters the nearest comment box; from the Threads list it
enters the page-comment box one frame below that list. `g T`, not `c`, is what enters
Threads as a navigable surface and leaves `w` and `/` live. Where a box has a key that
reaches it, the box says so itself through its placeholder `address`, which is what a
screen reader hears.

A true mode may own the keyboard. An armed address chord and the open reference
claim the relevant keys through their scope. A longer-lived menu keeps the
reference available through `allButTheReference`. Closing the reference restores
the shared captured `helpOrigin`, so the reader returns to the control or reading
place that opened it. A modal
dialog clears the top layer's auto popovers on its way in, so the reference notes
the ones it was opened over and stands them back up before that restore — the
overlay that says what a menu's keys are cannot be what takes the menu away. It
stands each one back up from that layer's own invoker — `lfInvoker`, the link a
layer declares because the platform's own runs one way only — so the layer's way
out survives the round trip too.

Escape is an ordinary binding in the register for Leaf-owned modes. A focused control's
specific inner step stands first, the latest active command return frame next, then the
generic text and containing scopes. The innermost live row owns exactly one unwind step.
A query clear, box return, panel dismissal, decision release, and return to the page
cannot cascade from one keypress. A scope does not need a private `keydown` listener or
hand-written `preventDefault` to protect that contract.

Auto popovers and modal dialogs are the platform's modes. While one is the active top
layer, the page rung stands down and browser Escape closes it; Leaf updates from the
resulting `toggle`, `cancel`, or `close` event. Register Escape only when Leaf adds a
distinct inner step, such as leaving a text box before closing its dialog or collapsing
the keyboard reference's expanded shelf.

A popover hands focus back to whatever had it when the popover showed — not to its
invoker, and not to `showPopover({source})`, which buys the anchor and the invoker
relationship and nothing about focus. So a key that opens a layer runs the press from
the control itself rather than opening it from the page, and every door leaves the same
way out. Where Leaf has to hand focus back itself, scope that to the door that needs it
rather than to focus landing on the body: a light dismissal restores nothing on purpose,
and a reader who pressed away into the page is not asking to be moved to the control
they pressed away from.

`offer` creates the native element named by the caller; ordinary buttons and links need
no Leaf activation binding. A `selectableOffer` registers its widget-specific keys.
A run-less row may still project a native press when that meaning is worth naming in
help, but it never reimplements the press.

When Leaf handles a binding that promises a visible control's activation, its command
path calls that control's `click()`; it does not call the handler or reproduce its
result. A platform-native press stays native. Arrival may focus or reveal the control
before activation. Modality checks belong only to gesture guards before activation,
such as refusing the mouseup that ends a text-selection drag.

A disclosure adds ← and →, which no browser answers, so its row runs the press
itself — through the element's own click, so keyboard and pointer stay one
behaviour. They sit on the row that already carries Enter and Space rather than
a row of their own, because two rows changing one thing spend both of the key
line's hints saying one word twice.

Only the direction that changes something is bound: → over a shut section, ←
over an open one, and both where the reader is standing on no disclosure at all,
which is the question the reference asks. So every key a surface names is a key
that works, and the row's one word covers the three keys it binds.

`DISCLOSE` answers that for an element, and every row over a disclosure reads
it — this scope's, and a widget's own row re-wording the same press. Two rows
naming different sets is not two promises but one: `lineRows` prints the nearer
row and drops the other whole, so a widget naming one key fewer takes the rest
off the line, and one key more promises what nothing runs. It also answers where
the element stands, the arrows being named only where this scope reaches: a
widget's disclosure inside a comment message keeps the platform's pair alone.

One scope covers both spellings, `details > summary` and ARIA's disclosure
pattern (`aria-expanded` on a button), because a reader standing on a settled
group cannot see which of the two they are standing on. A widget keeping the
pattern is covered by keeping it rather than by being named. The attribute alone
would be too wide: a combobox wears it over a box words are typed into, and a
treeitem in a walk of its own, where the arrows belong to the caret and the walk.

Which way a disclosure stands is watched as state, not heard as an event. A
`toggle` is not composed, so one from a shadow-staged `<details>` reaches no
document listener, and an `aria-expanded` control fires nothing anywhere. Both
keep that state in an attribute, so one `MutationObserver` over `open` and
`aria-expanded` repaints for both, and `shadowStage` hands it each root.

That watch repaints the register and not the line alone. A row bound through
`DISCLOSE` answers from the state the watch is already reading, so both surfaces
naming its keys turn over together — the line the reader sees and the
`aria-keyshortcuts` a listener is read — and a widget declaring a disclosure row
owes no repaint of its own.

State, and not the write that carries it: the watch compares each record against
the attribute's current value and repaints only where the two differ. The paint
restates both attributes on the controls it owns, so a watch reading every record
as news repaints for its own writing, and the page runs at its refresh rate with
nobody touching it. Nothing on screen says so — what said it was the suite, whose
every browser test paid for it until the run went over its bound.

### Standing somewhere

Focus is the reader's current place. `focused` follows it through declared
shadow roots. A native label activation may pass through `body` or a focusable
container between the pointer press and the control's focus; Leaf treats that
interval as one logical standing without changing DOM focus or preventing label
text selection.
`documentFocused` retargets the logical standing to its document host. Painted
focus readings use one of those two functions; CSS reads the matching `.lf-focus`,
`.lf-focus-visible`, and `.lf-focus-within` projections. A key ends the pointer
interval and restores physical focus before dispatch. Code that acts on physical
focus otherwise reads `document.activeElement` directly. `markHere` paints one
`--here-ring` around the semantic decision or control that contains focus. The ring
is derived on each paint; it does not store the decision walk's position.

A control that draws the band on itself draws it only where nothing else holds
that box's one outline. A decision written out around the control wears the band
already, and the log's news about the content — `restated`, `reader-override`,
`reported` — has no second carrier, while the band also has the washed cell and
the address chips.

Every rule that draws the ring names it in `--lf-here-ring`, in the same
declaration (theme.css carries why). Whether a box wears a ring is the outline's
answer; the name says which rule drew it, so nothing re-runs the layer's selectors
to find that out. The property is registered non-inheriting, so a name means the
box rather than each of its words.

A press that acts on where the reader is standing reads it through
`standingItem`: the unanswered decision where focus is on a control that works it — a
pick, a ✓, a mark — an answered decision on its explicit review arrival, and the
innermost item everywhere else, which is the ⌥ aim's own reading. It answers nothing
in ordinary chrome, where a reader is working on the page rather than standing in it.

Semantic rather than merely open: `standingIn` first reads `unansweredDecisions` to
preserve the special case below, then `allDecisions` only for an answered Ask's tray
row or the semantic focus that row lands on, so the Ask can still be worked without
turning focus on one of its options into focus on the whole question. Neither reading
is merely `openDecisions`. The unanswered and reader lists part on a widget whose own
seat is mid-conversation with the agent, which
leaves the reader's worklist while its pick stays unmade and its controls stay live.
Following the list took the ring off that widget the moment the remark was sent and
moved `c` down to whichever option the focus rested on — a second thread on the
child rather than the next line of the reader's own — and the agent's reply put both
back, with nothing the reader did moving either. An answered decision leaves both
worklists but stays in `allDecisions`, so a tray row can return the reader to it and
the same Ask-local numeric actions can revise its answer.

The ring is therefore paintable on a decision the `a`/`A` ask walk will not step to.
The tray does list it: the walk is a worklist, while the tray is the complete route
through the active Ask inventory. The Escape rung still reads focus rather than either
list, so the way out is the one it always has.

Working a decision and standing in one are different facts, and `markHere`'s ring
answers the second. A reader who tabbed to a link inside a question has named
something more particular than the question, so a press there means the link's
own block; reading the ring instead overrode what they named, and made the same
markup answer differently according to whether its question was still open. The
two agree wherever the reader is working the decision, which is every arrival the decision
walk makes.

`standingConversation` is the exception, and covers all three containers that
hold a conversation the reader can stand in: the panel's thread, a conversation
seated on the page, and each thread inside that seat. It asks for the box rather
than for the container's class, because a resolved thread is built by the same
function and wears the same class while having no box to reach, and a collapsed
one answers the same honest way.

The banner's Asks count is durable progress: `Asks 3/7` means three of the seven
active Decisions are answered. `allDecisions` supplies the denominator and
`unansweredDecisions` supplies what remains outside the numerator, so moving focus
or walking the page changes neither number. At 7/7 the same button stays available
and takes the positive treatment; it is both the completion signal and the route back
through the answers.

`landed` stores where the decision walk last arrived. This is distinct from focus:
clicking elsewhere removes the focus-derived ring without erasing either the walk's
useful continuation point or the answer progress in the banner.

`shownParts` supplies ring targets when a page styles a decision with
`display: contents`. A normal boxed decision wears one outline on its own box.
Hoisted controls use the same ring token through the shared pill rule.

The ring is drawn outside the box it names, so wherever the reader can be
standing, something has to have kept room for it. Two rules cover every case, and
which one applies is the same question theme.css already answers about the ring's
gap. A box that stands on its own draws its ring outside itself, and every scroll
region that box can land in reserves `--here-ring-room` at its edges through
`scroll-padding` — the document does this for its foot, the thread list for both
of its own, where the outward rings are the controls inside a card. A box whose
own edge touches something that paints draws its ring inset instead, because
nothing outside it is free: a thread touches the heading above it in flow, and no
scroll position separates them. A box a sticky offset holds against its
scroller's own edge is that case with the scroll taken out of it, which is why a
run heading insets too. Where a module decides
whether a control fits somewhere, the room is part of what has to fit; the
suggestion row carries it as trailing padding so that the fit is still one
measured box rather than a length read out of CSS.

Reserved room only reaches a control that lands in it, and a press lands nowhere:
the browser focuses the card under the pointer and scrolls nothing. So the thread
list lands a thread that takes the focus, whoever moved it, and that is the row
the ownership table carries. Without it a list nudged a dozen pixels leaves the
first card of a run under its own stuck heading by the width of an inset ring,
which is a card with three sides. A press lands when it is over rather than as
focus arrives, because focus arrives on the way down and the press may be the
start of a drag across the comment's own words; a drag that ends in the thread
takes no landing at all. What it lands is the thread the completed gesture leaves
the reader in, not the one the focus moved to, so a press on the thread they are
already standing in — which moves no focus — brings it back like any other.

This is an arrival rule and not a promise about the paint. Scrolling the list
under a standing thread cuts its ring again, and nothing re-lands it: the reader
is moving away from what they were standing in, and a control under something is
a fact about where it was put. A thread taller than the list's own scrollport is
the excepted case in both directions — there is no scroll that shows all of it,
which is the same thing the ring reading declines to report. Landing in a reply
inside such a thread reveals its composer and actions together; an editor too
tall to fit with its actions reveals the focused control itself.

`test_no_ring_the_panel_draws_on_a_walk_down_its_list_is_cut_or_covered`,
`test_a_comment_the_pointer_lands_on_comes_out_from_under_the_run_heading`, and
`test_every_ring_the_layer_draws_is_shown_whole_somewhere_in_the_corpus` hold
this for the panel's own walk, for a press inside its list, and for every shipped
page's tab order. They ask one question: where the control can be seen, so can the ring
that names it. A control that itself stands under a fixed bar is not a finding —
that is a fact about where it was put — and neither is a box too tall for the
region it is in.

`restoreReturnPlace` restores the exact connected control a command displaced. When
the reader had no control focused it restores the captured reading block without
leaving that block as an artificial activation target; if neither survives, it focuses
`body`. Pointer and ordinary-traversal fallbacks use `rung` and `letGo` for that last
case. `body` has a tab stop because a short page may not become focusable from overflow
alone. Focus rather than blur hands Space, PageDown, arrows, Home, and End back to the
page's actual scroll box. `letGo` also runs synchronously during module evaluation so a
fresh page accepts native scrolling before asynchronous upgrade, without stealing focus
from a control the reader reaches during that upgrade.

### The key line and reference

The key line is short help, not the keyboard reference. It walks outward from the
reader's innermost scope and drops bindings shadowed there. The ordinary shortlist is
the first live row, then a promotable Escape or the next row. At rest on the page that is `c`
and `r`, the two presses that say something back, beside the More control. Search, item
selection and reading-page movement are ordinary rows ranked below them, named by the
shelf and the reference: a glance that spends its room on ways of finding something to
act on never names the act, and scrolling is the one capability no page has to
advertise. Ranking is a row's place in its scope, so moving the row is how the line's
order changes. An active chord instead shows every live row in its scope, so computed
bindings, ranges, and capability filtering are the same ones dispatch and the reference
use. Each destination row keeps its complete
chord: already pressed keys take the accent face and pending keys keep the ordinary face.
Changing progress changes only those faces, not the sequence's keys or geometry. A mode's
Escape or back row remains a separate control rather than appearing as a destination
chord. `lineWhen` may hide only an ordinary hint without changing the command's liveness
or its place in the reference. Hint chips are `aria-hidden` because placeholders and live
announcements carry the same facts for assistive technology.

The compact line wraps when chord rows need the room. Ordinary hints yield from the
end on a window too narrow for them, but active chord rows do not; More is the one
control that always survives.

`syncLayout` reserves the line's footprint only in a scroll region whose horizontal span
meets it. Each reservation is the band from the line's top to that region's own foot: the
window for the document and trays, and the thread list's rendered bottom at the top of the
complete panel foot. The line's height, inset, any lift and the device's safe area are
therefore one measurement off the rendered box rather than four numbers to keep in step.
Over a covering thread panel, the line starts at its ordinary bottom inset and rises above
the panel foot only when their rendered rectangles collide; a thread list in another lane
keeps its stylesheet inset and reserves nothing for the line. A coarse pointer is drawn no
line at all — there is no keyboard to advertise, and every hint would name a key the reader
cannot press — so the footprint is zero and nothing reserves room for it. The line and its
chips take no pointer events; the More control does, because it is the only pointer route
to the reference and so to the character-shortcut preference, which cannot be made to
depend on the character key it turns off.

The accessible More control and its `?` binding share one progressive route. The
first activation unfolds additional current-scene rows into a shelf capped at two
lines; the second opens the complete reference. Escape returns through those layers,
and another command folds the shelf before it runs. Expansion and contraction are
announced because the revealed hint chips themselves remain visual. When there is no
additional current row, the first activation opens the reference directly. The native
control also opens it directly when character shortcuts are off.

The reference lists every live capability the page has, grouped by scope, and
filters those rows by normalized key, action, line word, and scope text. Search
is a projection of the same gathered rows rather than another binding index.
Computed ranges count current members. A declaration must survive `merge` with
its `when`, `at`, `claims`, and rows intact so the reference does not advertise
a scope the current page cannot enter.

The reference is a complete keyboard layer. Its registered Tab row cycles
through the close control, search field, and actual overflow regions without
letting focus enter the page behind it. Escape and the close control share one
registered row. Closing restores the element that opened it and keeps an already
expanded shortcut shelf open. Restoration waits one frame only when that element is
the temporarily removed More control.

The reference also owns the persistent character-shortcut preference. Turning
it off removes unmodified and Shift-only letter, number, and punctuation bindings
from dispatch, the key line, the reference, tooltips, address labels, placeholders,
and `aria-keyshortcuts` in one projection. Space is activation, not a character
shortcut, and remains live. The native More button and its Enter activation are
the route back to the setting; do not make the setting depend on the character
key it disables.

`aria-keyshortcuts` is another projection of the register. Element scopes expose
their currently available rows, including the scope's capability gate, and a
row's `control` exposes the key that duplicates it. `Mod` expands to both
Meta and Control because the dispatcher accepts both. The attribute cannot express a
sequential chord: spaces separate alternatives. An associated `control` in a chord
scope therefore omits `aria-keyshortcuts` and exposes the complete route through its
title and the keyboard reference. Call `paintKeys` when a state change moves row
liveness so this projection and the visible surfaces change together.

An overlay may become stale while open. If a row goes dead, its dispatch no
longer runs. A newly live row may wait until the reference is reopened. Do not
rebuild a focused help surface under the reader merely to keep it live to the
latest poll.

### Doors, trays, and version travel

One surface owns each destination. The version control opens the complete
version list with notes and comparison controls. There are no separate
older/newer page keys. A comparison base is the focused row in the menu; opening
the menu lands on the current base, and walking to the version being read clears
the comparison because it has no earlier base to mark against.

`runtime/version.js` owns the whole move, because a move between two documents of
one page is one gesture: the walk through the menu states a comparison per row,
an activation drops the standing comparison and puts it back, the chooser's word
says whether one is standing, and the activation captures the reading landmark
before it replaces the authored main. Split into modules, those four facts travel
as callbacks passed back and forth; kept together they are ordinary local calls.
The surface the rest of the runtime sees is the three key rows; the chooser's nodes
and the labels the banner reserves for; `renderVersions` and `prepareActivation`,
which state application drives; the arrival landing; the menu and comparison
readings the composing surface and the margin take; and `readingBlock`, the block
the reader is on, which the decision walk and the keyboard reference start from.

The live root follows the newest version without navigating. It begins fetching
as soon as a state read announces the version, but `midComposition` or an open
version menu defers activation and leaves the newest-version chip visible. Ending
the composition releases the version on the next heartbeat; pressing the chip is
an explicit override and still keeps the live address. `goActive` is the one door
for that in-place newest-version request and for the way back to the live address
from a pinned document; `goVersion` is the door to an older public version.

An older version is historical rather than live: choosing one navigates to its
virtual version address with `?pin`, and it stays at `currentVersion` while offering
the newest-version chip. The view record carries reading position and the decision-walk
landmark across that document navigation. Focus and a selection do not cross to a
new document. On live activation, runtime-chrome nodes and their focus survive;
authored-main nodes are replaced, so the semantic landmark—not a DOM node—is the
continuity guarantee.

The left side holds one tray at a time. `showTray` owns `trayUp` and renders
the complete outcome for leaves and asks. The leaves tray overlays the
document because its rows leave the page. The asks tray takes a strip because
its rows travel within the page and the reader must keep the target visible.
Both entry controls call the same tray setter.

Keyboard destinations also capture the workspace they replace. `g T`, `g A`, and
`g L` may exchange a standing panel or tray for another; their return frame restores
that prior workspace and re-resolves its semantic row when reconciliation rebuilt it.
`g M` uses the same frame for the complete Page-map sheet. `g V` contributes the
version menu's own return frame to that destination vocabulary. Direct destinations
therefore restore the standing their owner displaced rather than merely focusing the
destination's banner control after closing it.

`restoreTray` runs after all declarations exist and after the first projection
can populate state-dependent rows. It calls its supplied `beforeOpen` policy to
retire Threads, then presents the remembered tray directly without replaying
opening motion. `ARRANGEMENTS` supplies one render arrangement for each persisted
tray.

Decision rows come from every active local `x-awaits` source and holder declaring
`x-request.decision`, answered or open, not from a list of decision tags. Where a source
is nested in an `x-decision` region, the row names the region: its heading, context, and
evidence are the decision the reader is being sent to, while the source remains the
owner of the answer. `itemSays` supplies each row's own label and the owned command
scope's `options.answer` supplies its current answer. Selecting a tray row travels through
the same decision-arrival function as `a` and `A`, so the panel and directional walk agree
about focus, reveal, arrival placement, and `landed`; only the tray's list is wider,
preserving answered routes for review and revision.

An arrival stands the reader on the decision, which is the element the scroll has just
aligned and the one the ring names. The widget's contributed actions are addressable
there by their declared bindings, with `1`–`9` as the default; its controls remain the
next Tab stops, a stop at `tabindex: -1`
keeping its place in document order. Landing the answering control
instead puts them as far down the decision as its context and evidence are long, off
the screen the same gesture arranged. A decision a page styles boxless has nothing to
stand on and keeps the control as its landing. A widget rebuilt under a reader is not
an arrival and hands back the control they were working (`standOn`).

A request decision is answered at acceptance rather than by replayable widget state. Its
pending lifecycle therefore leaves the reader's list immediately and hands the next
word to the host; a terminal failure returns it, while success keeps it closed. Page
holders scope that reading to their authored revision and frozen thread holders scope it
to the conversation document's lifetime, exactly as the request seat does.

A decision is answered by a verb listed in `x-awaits.answers`; do not infer that every
state change is an answer. Two things take a decision off the reader's list, and only
that one is an answer. The other is a conversation standing in the widget's own
declared seat (`x-conversation`) while it waits on the agent: `seatRoot` finds a root
anchored on the widget and nothing else, which is the anchor `renderConversations`
collects into that seat, and `awaitsAgent` says the next word there is the agent's.
So the banner's count and the panel's reading of the same thread cannot disagree
about whose turn it is. Whose thread it is does not enter into it — the agent may
open one in the seat too, and once the reader has answered there the question is
with the agent either way. An ordinary agent reply hands the conversation back.
A `response: {kind: version, verb: <answer>}` conversation accepts no agent reply;
the agent incorporates it into a version or opens a separate thread for
clarification. While that thread waits on the reader in the same seat, it carries
the original response through the stop gate; their answer hands both threads back
to the agent. Authored state in a later version must answer an originating open
Decision, or change the declared answer when the Decision was already answered; a reader
action in the log cannot substitute for that revision. Only then may the agent
resolve the original thread. Threads owns the reader-facing clarification; the
page's Decision remains the proposal with the agent rather than counting both.

That combined reading is what `openDecisions` returns, so the `a`/`A` walk follows the
reader's worklist and a request the agent owes the next word on does not belong on it.
The banner and tray instead use `allDecisions`, the current page-and-thread inventory
that retains an answered action Decision and a request throughout its lifecycle.

Three readings ask the other question — whether the request is *answered* — and all
say so by emptying the seats (`answeredContext`, stated beside the shape rather than
by a caller reaching into it, so a member derived from those conversations later
cannot escape the emptying). An action's `requires` is one: a conversation does not
answer a question the widget holds no state for, and refusing a pick over the reader's
own remark would refuse them the answer they were asked for. The version-response
resolve gate is another. Where the reader is standing preserves that reading first,
then widens through `allDecisions` for answered-review routes; **Standing somewhere**
owns it. Frozen thread markup seats no conversation of its own, so only an action
answers there. A `rollup` instance is an
aggregate-only owner: it awaits when any nearest local decision or child roll-up
awaits, but it never enters the visible list. The standing projection keeps every
open local member; an enclosing `x-decision` replaces that member only on the
visible/navigation surface. `actionAvailable` still queries whether the source or an
ancestor's aggregate is open. A module reading `openDecisions()` calls
`decisionSource()` when it needs the actionable widget rather than the reader-facing
region.

### Go-to chord

`g` opens one destination mode. For mnemonic letters, case determines the production:

| Form | Meaning | Current routes |
| --- | --- | --- |
| `g` + uppercase mnemonic | The mnemonic completes a direct destination. | `g T` Threads, `g A` Asks, `g L` All leaves, `g M` complete Page map, `g V` Versions |
| `g` + lowercase mnemonic + digit | The mnemonic selects a numbered list; the digit selects one of up to nine members. | `g m 1` Page-map location, `g t 1` tab, `g h 1` hyperlink, `g f 1` fold |

Uppercase and lowercase mnemonics are parallel namespaces. A mnemonic may occupy both:
`g m` starts the numbered Page-map location list, while `g M` completes a direct trip to
the searchable Page map sheet. Each form contributes its own command row; its capability
and landing behavior remain independent.

`g g` and
`g G` complete the chord themselves, gliding to the top and bottom of the visible
scroller. When a thread holds focus, `g k` and `g j`
place that card at the top or bottom of its list without moving the page. From a
beside-panel, `g p` returns focus to the page while keeping the panel and its narrowing.
An edge is one place, so the second key completes the route; because every page has a
top, the mode never arms empty and the page-level `g` row needs no capability gate.
Completing a direct destination exchanges the transient chord for one return frame;
Escape restores the exact standing and workspace captured before `g` armed.
`BUILTIN_DIRECT_DESTINATIONS` declares the uppercase destinations the address owner
itself implements. Another owner contributes a complete row through `directDestinations`,
as version travel does for `g V`; both enter the same `GO` scope. Each destination declares
its mnemonic, words, capability, landing, and return. `ADDRESSES` is the lowercase
numbered page-list vocabulary. Each entry declares:

- its letter and user-facing name;
- the sentence shown in help;
- its ordered members and whether the numbered window follows the viewport;
- how to arrive at one member.

A list's capability is not declared: it is whether the list is non-empty, read
where the row asks. Consumers do not branch on which address list is active.
Adding a direct destination or a numbered list adds one entry to its vocabulary.
The page-level `g` row promises only the mode; destinations and ranges belong to
the rows inside it. Completing an address runs that list's destination: a tab selects
and takes focus, a same-document hyperlink follows and leaves focus on its fragment
target, an external hyperlink names the browser tab it opens, a fold opens and takes
focus, and a Page-map location presses its first available Button. The complete Page map
remains a direct destination beside that numbered prefix.

Arming the mode shows the available direct destinations and numbered lists in the key
line and paints `data-lf-goto` on the body, so the contents map can reveal its labels as
it does on hover. Each row shows its complete chord. Each visible numbered member shows its
complete address, such as `g h 1`. A direct mnemonic completes the travel and moves
focus inside its destination. A numbered-list mnemonic narrows the inline hints to that
list's current numbered window without changing their labels or geometry. The following
digit selects immediately. Escape backs out to the list menu before it closes the mode.

Every sequential step has its own fixed keycap. A compact choice label such as `g / G`
remains one decision point and is spoken as “g or G”; a sequence's accessible label says
“then” between adjacent keycaps. In a live chord, pressed keys take the accent ground and
pending keys remain neutral, matching ordinary bindings. The complete reference shows
every route with all steps neutral because it describes rather than enacts them.

`chordPrefix` is the stable start of every route. Control titles and the reference combine
it with the destination row; the reference uses `completeChordSteps` where a row has more
than one remaining step. `chordKeys` adds the named list to that prefix as the structured
reading of current progress, which the key line and page chips apply to each complete route.

Numbered addresses are capped at nine per list. Tabs, links, and folds keep the first
nine document members, so those identities do not change as the reader scrolls and an
off-screen member within that prefix remains reachable. Page-map locations instead
number the visible window from one; their complete searchable identity lives in the
Page map sheet. That window stays fixed during a scroll and is read again at
`scrollend`. Chips live in runtime chrome rather than authored markup. They sit above
their targets and move inside the viewport below the banner before overlapping chips
are removed.

`LINK` and `DISCLOSURE` describe the platform controls a reader may land on and the
immediate word for their next press. An addressed fold lands on its summary after
opening it; a link reached through Tab still says that Enter follows it. A summary
says whether it will open or close from its current state. This avoids one scope per
native tag while keeping the next press visible.

The address mode has no timeout. A prefix with no competing complete binding
remains active until a listed key completes it, Escape cancels it, or an
unrelated key disarms it and is redispatched with its ordinary meaning. The
reader is not charged a time limit for reading the addresses just painted.

### Directional walks and arrival

A directional page walk starts from the reader's place, in this order:

1. current focus;
2. selection or caret;
3. the walk's last `landed` item;
4. the current reading block and scroll position.

The banner is an address, not a page position, so its controls do not become the
walk's origin. `decisionStep` compares document positions rather than incrementing an
index remembered by the walk. A panel thread walk may use log order because the
list itself is its complete ordered space.

Arriving at a page decision puts its arrival region's start below the banner, not
the decision's own top edge. A widget declaring `x-decision` states that region and
the walk is handed the region rather than the source inside it. Nothing else declares
one, and an edit to a phrase cannot: what explains it is the sentence it stands in and
the heading over that. `arrivalRegion` reads that region off the document instead. Its
candidates are the blocks before the decision whose own parent still contains it — so a
block wrapped in something the decision stands outside of, another ask or a section of
its own, is not this decision's context — and of those it takes the last heading, then
the text block holding the decision or, for a change that is its own block, the nearest
remaining block before it. The first candidate whose start still leaves the decision's
foot on screen wins, falling back to the decision itself. That bound is what lets the
widest candidate go first, and it keeps the region inside one screen without a rule
about distance. A candidate that paints no box is not a place to arrive at: an element
generating none measures at the document's origin, which would read as a region at the
top of the page.

The sweep is the document's own blocks in document order, so a decision staged inside a
declared shadow tree takes a heading standing over its host but not one inside that
tree. The travel moves the page's scroller, so the decision's own box is brought into
view first for the sake of a decision inside a nested scroller, which that placement
would never reach. A decision whose region already stands clear of the banner, and which
`readableDestination` reads as unclipped on every edge, is not travelled to at all: the
press moves the ring and the focus and leaves the page still. A thread decision keeps
its centred arrival in the panel's own list.

`captureView` stores a passage-based reading landmark, correction within the
block, and the last decision landmark. `restoreView` resolves the landmark after
upgrade and corrects the scroll from the rendered box. A URL fragment outranks
the saved view on a fresh navigation; the saved view outranks a leftover
fragment on reload or back navigation. `landArrival` applies that ranking only
after final page geometry is available.

Focus and selection are not restored across document travel. Restoring focus
onto a control the reader never stood on would change the next Space from page
scroll to activation, and a selection may refer to words the new version replaced.
The saved decision landmark preserves directional continuity without claiming the
reader still stands there. A live activation is the other case: the reader's own
standing carries across it (see "Startup and presentation"), so the next press
means what it meant before the swap.

## Chrome, conversations, and text input

`.lf-chrome` is one fixed runtime root containing the banner and its notice, the
tray panel, thread panel, composer, floating comment control, live region, key line,
help, inspection paint, legend, and address layer. The page and panel are
separate scroll regions.

One control stands outside it, and it has to: the skip link is the layer's route
in from the top of the document, and tab order is document order while the
chrome is last. It is prepended to the body, rests transparent as the comment
note does — every reading that asks whether a box is on screen asks
`opacityProperty` — and carries the offer marker, so paper and a copy drop it
with every other injected control.
It takes no register row — a control is a route to a capability rather than a
capability of its own, and this one's design is to be found by the first Tab
rather than advertised. Opening or closing one calls its state setter, updates
the persisted intent, and schedules the shared layout and key paint.

`.lf-receipt` is transient runtime chrome for a subject with no page-edge Button.
`paintAcknowledgments` is its one writer. An unsettled reader message paints after
that exact message in the full thread panel, and an event-backed widget frozen into
conversation chrome paints beneath its owner. Inline page conversations and page
widgets use their target's existing margin cluster instead; an explicit page-widget
claim is the cluster's **Active** reading. The fallback receipt wears `lf-ui` and
`data-lf-gen`: it is an account of the conversation, not authored words, so selection
and diff readings skip it. Reconcile widget state first and paint receipts afterward,
so each receipt describes the state the widget now displays. Keep surviving nodes
across state applications, and in their place, so an unchanged phase is not
re-announced: a node taken out of the document and put back replays every
animation it wears and re-announces its live region. A phase change is a change
of words and of the Active ink, with no motion. Its live state span changes only
with semantic phase or detail; the separate age clock may repaint on a heartbeat
without entering the live region.

The thread list reconciles nodes rather than rebuilding them. `setChildren`
preserves existing message, reply, and textarea nodes when the same event still
stands. Applying a state must not discard a reader's caret, focus, reply text,
or disclosure state. Reconciliation preserves node identity; the list's own
hold, rather than the browser's scroll anchoring, preserves viewport position.
Tests pin the thread's box rather than a particular scroll offset.

Panel and inline settlement controls read pending work from the outbox. Their busy
labels reserve their width, keep focus, and prevent another submission while the
request is pending. The accepted projection decides when the thread resolves or
reopens. Resolving the last thread in an inline card closes it and returns focus
to page navigation; a conversation seated in the page keeps a Reopen control.

`renderThreads` holds one live card through every list mutation. It chooses the
card under the pointer while the pointer is in the list, then the card containing
focus, then the topmost visible card. It records later visible cards before the
mutation and refreshes their baselines after each correction, so a live successor can
take over if the first leaves or becomes hidden. The held `paintAcknowledgments` call covers
claim-only mutations too. The list follows changes in the card's content position,
keeping reflow out from under the pointer without fighting an intentional scroll.
Browser scroll anchoring is disabled only for the life of a hold so those two
authorities cannot compensate the same change; outside a held mutation the browser
keeps its native safety net. The correction runs after each mutation and on every
frame of a resolution fold; fold completion removes its node through `renderThreads`,
under the same hold.

### The order the list reads in

The list is the page's order, not the log's. `inPageOrder` sorts by where the
anchor pass placed each thread and breaks ties by log order, so the panel, the
marks down the page, and the `t`/`T` walk are one order. A thread
whose passage this version rewrote falls back to the element its anchor names,
because an id survives a rewrite that takes a quote down with it. A thread that
resolves nowhere — a comment about the page as a whole, or one whose element is
gone too — goes under the list rather than into the middle of it.

`pageOutline` reads the page's own headings, and `groupFor` names the run of
threads under each. A run's heading is one node kept across reconciles and stuck
to the top of the list while its run scrolls past. A stuck box is held by its
margin edge inside the scroller's content, so the room above a heading is its own
padding and the pin is drawn back over `--lf-list-inset`, the property the list
spends its own inset from. A margin there, or a `top` of zero, leaves a strip the
list scrolls through in full view.

Being pinned is `.lf-pinned`, worn by the run headings and by the resolved
disclosure's summary, which takes the slot from the last heading when the reader
reaches it. One class carries the mechanics, so the slot cannot move in one of
them; it is also what `renderThreads` sweeps to answer how much of the list's top
stands covered. That answer is the one number in the list's `scroll-padding` that
CSS cannot work out, because a long heading wraps — the tallest is written to
`--lf-head-room`, and a `ResizeObserver` on the list writes it again when the
reader draws the panel narrower and a heading wraps — a drag posts no event, so a
reconcile never comes. Without it a walk lands threads under the heading with the
opening words of the comment behind it, which is what
`test_no_focus_ring_the_keyboard_lands_on_is_cut_or_covered` holds.

The measurement is taken only while the panel is open, and this is a rule rather
than an optimization. Shut, the panel is `display: none` and every heading
measures zero, so the number written is not the room a heading takes but the
absence of a panel. Taking it anyway costs a forced layout on every reconcile,
for a page whose reader may never open the panel at all — and that cost is not
notional: it delayed an event's acknowledgement past the window an undo is
offered in, so a press the key line had just promised was refused, which
`test_an_action_response_accounts_for_its_gesture_without_a_follow_up_poll`
caught under a loaded machine and nowhere else. The observer covers the reopen,
a box arriving being a resize, so the number is written at the first moment it
can be right. A retained value from the last open panel is a real measurement
and stands until then; the property is unset until the first open, where the
`0px` fallback in the rule is the honest answer.

### Narrowing the list

Two narrowings compose: the words the reader is looking for (`finding`, over each
thread's messages, its anchor label, and the part of the page it is on) and
whether the latest agent message asks the reader to answer (`needsYou`, through
`awaitsReader`). Both are the panel's own view. The page's marks, the inline
conversation seats and the
banner's count go on saying what the log says, and the panel's head says
`Showing N of M` for as long as a narrowing stands, because a list that goes
quiet about what it is hiding is a trap.

Neither is stored. A remembered narrowing greets a returning reader with part of
a conversation and nothing on screen saying why. `ARRANGEMENTS` is for what the
page restores; a look at a list is not one.

Neither takes a card out of the document. An open thread the narrowing hides keeps
its node, `hidden`: a widget an agent sent in a reply is instantiated once, in that
card, and the banner's Asks count, the tray's rows and the `a`/`A` walk all find it
by id. `openThreads` and the `t`/`T` walk read only the cards that show.

`showThread` reveals a directly requested thread or message. It clears a narrowing
that hides the destination and finishes an outgoing resolution fold before opening
the resolved disclosure. A thread opens in its reply box, or on its card when
resolved; a message takes focus at its own words so Tab reaches its controls.
A thread too tall for its scrollport starts at the earliest complete content block that
still leaves its reply area visible. That puts the first visible content on a clean boundary
instead of leaving an arbitrary partial message line below the pinned heading. The transient
arrival flash belongs to the revealed target — short card, reply area, message, or oversized
editor — rather than to a long card spanning beyond the scrollport. The explicit `t`/`T` walk
remains on cards; Enter starts a reply and Escape returns to the card.

A reply send keeps its editor and actions visible only while the reader remains
there. Moving to another input, closing the panel, or scrolling away relinquishes
that continuation. The send preserves the panel's narrowing. A general-comment
send keeps focus in its originating box.

Messages render from Markdown after escaping raw HTML. Literal text such as a
generic type remains text and cannot inject markup. Interactive event `markup`
has a different door: only the CLI can write it after validating against the
vendored registry, while the browser event schema refuses it. A widget in that
markup is instantiated once in the panel; inline conversation seats show a
textual projection with a link to that reply's controls in Threads.

An agent message edit is a later event folded onto the original message id. The
panel and an inline conversation update the existing message node and show
`edited`; the text wrapper alone is replaced. The message's cached markup nodes
stay connected because their widget state and authored baseline belong to the
original event, not to the prose revision.

Fragment links in messages use the browser's `hidden="until-found"` behavior to
reveal authored disclosures and tabs. `paintAnchors` marks a link detached when
this version no longer has the id and refuses its press. A thread outlives its
version, but a fragment target may not.

`wireInput` gives runtime textareas one input contract: persist each edit, keep the send
button and placeholder current, prevent parallel sends of one local surface, and send
with `Mod+Enter`. Enter retains the textarea's native newline. The stylesheet owns
textarea growth through `field-sizing: content`, within the room supplied by floating
placement. Script does not derive textarea height from its text. `wireInput`'s sync
refreshes the composer's placement for typed and programmatic edits alike, including
drafts mirrored from another tab.

The selection composer keeps its passage painted after an explicit Comment gesture moves
focus into the textarea. Automatic passage selection leaves the native selection in place.
Its `.lf-composer` wrapper contributes state and draft machinery through
`display: contents`; only `.lf-fab-input` draws. `showComposer` states the whole visible
outcome from `composerOpen`, `pendingAnchor`, and `fabAnchor`; `openComposer`'s `focus`
option decides focus independently. Outside clicks and Escape hide without discarding
words. A successful send or an explicit draft close discards the local record.

An accepted anchored comment continues in the open Threads panel, widening a filter
that would hide it. With the panel closed, an exact projected-datum comment opens in a
declared widget Thread surface when that widget supplies a visible outlet. A local
surface uses the canonical Thread fold and core-owned controls; only its container and
layout belong to the widget. Closing, filtering, or lazily withholding
the datum removes the claim and restores the living-margin fallback. Deliberate travel
may reveal or hydrate the datum, then runs the same reconciliation path to claim it.
A page marker uses an already-open panel; with the panel closed, other comments open
inline where the layout has room and use the panel at narrower widths.
The send focuses the reply box only when no later selection, edit, or typing gesture
stands. Live pages reserve conversation room at the wide layout's existing floors,
so the first comment and the last resolution leave the document column in place.
`--thread-card-floor` bounds an inline card when the remaining margin is too narrow;
the card then covers the page rather than becoming an unreadable sliver.
News arriving without the reader's send gesture may show a notice and count but
does not move focus or scroll the panel. `notice` is the one visible surface for a
moment's news — a recorded gesture, an arrived version, a refused send — and it
stands in the banner's status slot in place of the status line, which returns when
the notice fades; the live region hears the same words. It is text rather than a
control: what a notice names, the banner's own buttons reach. There is no second
surface for news, so nothing floats in a corner to become a stale pointer target.

## Durable drafts

Every unsent text surface persists:

- the general comment box;
- each thread reply;
- the selection composer, including its anchor and mode;
- a conversation's first message and replies;
- an `lf-draft` edit.

The store is `localStorage` scoped by page and draft context, because the text
must survive reload, version navigation, server restart, and closing the tab
where it was typed. `draftCache` keeps a readable local branch when storage
writes fail. Storage failure may reduce cross-tab durability; it never disables
the live Send or Save action.

One context has one shared generation. `watchDraft` mirrors storage changes into
every connected view. The DOM's listener cleanup is the index: a watcher stops
when its box is disconnected, so panel reconciliation does not maintain a
parallel map of live inputs.

An active record and a settled tombstone are different records. An empty active
`text` means the reader intentionally cleared the box. A tombstone means Send or
Cancel settled that generation. The implementation never depends on
`removeItem` to distinguish them, because deletion can fail independently and
could otherwise resurrect old words.

`base` records the durable shared generation a local edit descends from. A chain
of nondurable local writes keeps that base. Storage news from the base cannot
erase the branch; an unrelated later shared generation owns the context and
retires it. Before writing a settlement, Send, Cancel, and log reconciliation
refresh the shared generation so a stale tab cannot tombstone a newer edit.

The log outranks draft storage. `attemptAccepted` treats an active generation as
settled when its attempt already appears in `events`, even if stale storage
returns active words after reload. A successful storage write followed by a
failed read remains sendable from cache.

Settlement is generation-specific. `activeDraftRecord` filters tombstones and
accepted attempts. `sendDraft` snapshots the current record, checks ownership
immediately before POST, and settles only that attempt. `mirrorDraft` updates
visible text only when doing so will not erase a newer local generation.

The selection composer keys drafts by anchor, not by one global composer slot.
Its stored record carries the anchor, mode, and last-touch time; startup reopens
the most recently touched draft. Different passages may therefore hold
independent unfinished comments.

An `lf-draft` editor is a live gesture. Its `renderState` returns `false` while
the editor is open, so remote edits and refusal correction wait rather than
overwriting the textarea. Closing the editor lets the authoritative projection
apply in order.

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

A report has two seats — a thread's own `.lf-receipt` line, and a margin reading
`marginButton` has given the `status` behavior. Both are live-session information:
Sent, Waiting for pickup, and Picked up report a move an agent is still making, and a
file has nothing behind that claim. A copy drops both seats rather than turning
provisional news into a statement. The durable action remains applied in the widget's
serialized state; the page map does not add another record for the copy to carry.

Where a durable margin item stands is the same question in every medium, and a file
cannot dock: the packing pass measured the rail at the width the page was exported at
and left with the scripts. So under that floor and on paper, where no rail is drawn, a
copy's remaining margin items take the docked shape rather than the absolute seat they
were exported into, which hangs off the page box. Not the rows that same pass withheld:
an item whose target is not shown wears `lf-waiting` into the file, and a shape taken on
the medium's terms would be the only thing standing a record beside a passage the file
was folding away when exported.
Paper later unfolds that passage through CSS, but a script-free copy cannot rerun the
packing pass, so its serialized `lf-waiting` reading remains withheld. Changing that
behavior belongs to the live and copied layouts together, not to this export override.

Paint that promises a gesture — the pointer hand above all — hangs on how a press is
spelled, never on a control class alone. Export takes the role off and leaves the class,
so a hand hung on the class is a hand a file cannot answer. The layer's own spelling is
the value `offer` writes into `data-lf-offer`: the tag or role for a press it built, the
empty string for the rest of the chrome a widget makes. The theme's one pressable rule
reads that value, and the marker outlives the role — a press carrying page words becomes
a span in a copy and keeps its words — so the copy clears the value where it strips the
role, and the promise leaves with the thing that could have answered it. A guard in the
theme would not do: it would have to be written twice, once for the document and once for
the slice a declared shadow tree renders under, where `html:not(.lf-copy)` matches
nothing at all.

A control that keeps its shape in a copy keeps its name too, and the name needs
a role that admits one: a glyph whose word is collapsed away is an `img` with a text
alternative, not a bare span wearing `aria-label`.

Projected data is a fourth question with a different answer: a copy keeps the current
`projectData` rendering, including its projection and datum labels, but loses the
module that could refresh it. It is therefore a labelled snapshot, not a live
projection.

Put a layout grant in a selector strong enough to override the withheld base
rule. Put a standalone-only affordance guard in
`:where(html:not(.lf-copy))` so the guard does not add specificity to every rule
inside it.

Print asks a stricter question than export because nothing on paper is
interactive. `data-lf-offer` identifies injected controls to remove, while
`data-lf-said` preserves a decision word the page speaks through a control and
`data-lf-echo` a name a control copies off the row it routes to. What the two word
markers keep is the word and not the shape: a control that survives paper
gives up its ground, corner, border, underline, marker and pointer hand, because
nothing on a sheet can answer the press they promise. Colour stays, being part of
what the control says.

Paper opens what a page puts behind a gesture, for the same reason: a settled
group's cards, an inactive tab's panel, and a shut `<details>` all print open. A
page that means a disclosure to stay shut on paper says so in its own stylesheet.
`paperWords` compares the screen and print readings across the whole page.
`coveredWords` runs again in print. A wrong offer/said declaration is fixed
where the label is created, not by naming its widget in print CSS.

The live-page scrolling and chrome reservations stay under the live guard. A
copy with no panel uses an ordinary centered document and must not retain room
for absent runtime furniture.

`test_an_exported_page_fixture_stands_on_its_own` strips scripts, opens the copy, and
asks what still looks actionable. Keep that end-to-end test general rather than
asserting one widget's exported implementation.

## Render gates

`leaf version check <page> --render` is the browser contract. It re-vendors
before loading, runs both color schemes, waits for the runtime's actual readiness
and finite motion boundary, reads screen and print, and reapplies standing state.
A local browser check is required after changing `leaf.js`, a widget module, the
registry, or the theme.

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

`standingState` and `shallowSigs` are published by their projection owner through the
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

Run `node --check skills/leaf/assets/leaf.js`, formatting, and a
focused real-browser test while iterating. Before handing over a runtime or theme
change, run the relevant full browser file or `leaf version check --render` on
the affected example. `node --check` cannot validate browser bindings, runtime
CSS inside the module's template literal, computed layout, or reconciliation.

Re-vendor a page before trusting its browser result. A page directory carries
the runtime, registry, modules, vendor files, and theme copied by `page init`; a
page not re-vendored is testing an older layer.
