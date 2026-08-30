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
starts the page, but exports no capability. `runtime/widget-api.js` is the one public
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
`runtime/decisions/model.js` owns request discovery and folding;
`runtime/decisions/view.js` owns decision chrome, marking, and the decision walk;
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
`runtime/living-margin.js` owns the page map, compact map sheet, inline margin threads,
and the one aggregated action, communication, and information item for each page target;
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
`runtime/state-feed.js` owns state reads, offline handling, heartbeat replay,
event-stream wakeups, and first-read presentation scheduling and retry;
`runtime/state-application.js` owns stale-answer ordering, version preparation,
state commit, projection, notification, outbox accounting, and rollback;
`runtime/banner.js` owns banner wording, tone, and tab-icon paint;
`runtime/banner-shelf.js` owns news-control reservation and focus continuity, action-shelf
overflow travel, and the banner's touch bridge to the document scroller;
`runtime/motion.js` owns reduced-motion policy, shared scroll behavior, and
Web Animations playback;
`runtime/updates.js` owns the accepted claim snapshot and canonical action,
report, and work-claim feeds;
`runtime/version-diff.js` owns version-comparison state, marks, and chooser paint;
`runtime/version-activation.js` owns version document loading, authored-root
replacement, and activation serialization;
`runtime/version-navigation.js` owns version travel, the chooser control and menu,
its key scope, and forced live activation;
`runtime/widget-upgrade.js` owns widget upgrade guards, data bodies, fail-soft
rendering, and async settlement;
`runtime/widget-elements.js` owns widget-element construction, labels, gesture
guards, deferred measurement, layout-change signalling, and control sizing;
`runtime/registry.js` owns vocabulary queries;
`runtime/scrolling.js` owns the document scroller identity, relative scroller moves,
fixed-surface wheel forwarding, and the gutter its bar takes;
`runtime/chrome-style.js` owns the comment layer's private stylesheet, built from
the declaration-derived names and layout queries the runtime supplies it;
`runtime/chrome-layout.js` owns comment-panel visibility, chrome geometry, and the
document room left after the panel and trays;
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
`runtime/view-continuity.js` owns persisted semantic reading landmarks, arrival
landing across authored-document replacement, and the page-block reading used to
start directional walks;
`runtime/pointer.js` owns the shared unrounded pointer position;
`runtime/geometry.js` owns the shared readings of visible boxes and clipping;
`runtime/navigation.js` owns reader travel and scroller selection;
`runtime/anchors.js` owns anchor resolution, paint, and anchor-specific travel;
`runtime/conversation/model.js` adapts server-projected threads to browser callers;
`runtime/conversation/messages.js` owns message rendering;
`runtime/conversation/replies.js` owns reply drafts, mirrored send state, and delivery;
`runtime/conversation/inline.js` owns conversation seats rendered into the page;
`runtime/conversation/box.js` owns page-seated first-message boxes;
`runtime/conversation/folding.js` owns resolution-fold state and motion;
`runtime/conversation/landing.js` owns conversation input discovery, focus travel,
and panel arrival;
`runtime/conversation/narrowing.js` owns comment-panel search and waiting-on-reader
filter state;
`runtime/conversation/placement.js` owns document-order grouping;
`runtime/conversation/reaction-strips.js` owns the panel's message and page reaction
surfaces;
`runtime/conversation/thread-card.js` owns retained panel thread cards, their quote
state, and their reply, resolve, and reopen controls;
`runtime/conversation/thread-list.js` owns retained panel list reconciliation;
`runtime/conversation/work-lines.js` owns live claim seats; and
`runtime/conversation/reconcile.js` composes panel reconciliation;
`runtime/projection/authored.js` owns captured authored state and restore
statements; `runtime/projection/data.js` owns keyed runtime-data DOM
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
| authored widget state | the version's markup before upgrade | `captureAuthoredFacets` and `rememberAuthoredMarkup` capture it; neither changes it |
| external data | the latest accepted page data revision | `receiveState` replaces current values and retained captures; `watchData` delivers the authored current-or-snapshot selection to widget modules |
| projected data | an external snapshot or other records the widget is currently given | `projectData` reconciles their keyed rendering; the DOM does not become another record store |
| version shown by the live document | the latest immutable version accepted at the activation boundary | `activateVersion` advances `currentVersion`; an immutable version path derives it from its URL |
| accepted history | the server event log | `receiveState` replaces `events` after a complete read |
| the reading the page has applied | the server's `/api/state` answer | `receiveState` writes `runtime.reading` and paints `data-lf-reading` |
| unresolved browser work | the ordered `outbox` | `post` adds, `accountOutbox` and `releaseProjectedOutbox` remove |
| rendered semantic state | authored state, log projection, then outbox overlay | `reconcileState` |
| proof of what the DOM currently represents | `committedProjection` | `stageOutboxAction` and `reconcileState` |
| anchor paint | thread and composer anchor records | `paintAnchors` |
| where each thread's passage lands | this version's resolution of its anchor | `paintAnchors` writes `placed` |
| local agent work | the typed, log-projected claims in `status.work` | `paintWorkLines` paints every subject seat without becoming another store |
| composer visibility | `composerOpen` and `fabAnchor` | `showComposer` and `showFab` |
| panel visibility | `panelOpen` | `setPanel` |
| the narrowing on the thread list | the reader's find words and waiting-on-you press | `renarrow` and `widen` |
| how much of the thread list's top a pinned heading covers | the tallest `.lf-pinned` box as rendered, while the panel is open | `paintHeadRoom` writes `--lf-head-room`, called by `renderThreads` and by a `ResizeObserver` on the list |
| the thread list's viewport position through reflow | the live reference card in the open panel | `renderThreads` and the held `paintWorkLines` call preserve it through reconciliation, provisional work, and resolution folds |
| where the thread holding the focus stands in the list | the band the list declares landable through `scroll-padding` | `threadsBox`'s `focusin`, and its press through `pointerdown`/`pointerup`; `stepThread` for a key press that moves no focus, `landIn` for the box it puts the reader in, `placeThreadEdge` for an explicit edge placement, and `revealThread` for a deliberate centring |
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
authored elements. `shallowSigs` excludes exactly those attributes. A widget's
own `data-lf-*` state remains visible to replay and to the render gate. Add a
runtime-authored attribute to `PAGE_PAINT_ATTRIBUTE` when its writer is added;
do not broaden the exclusion to every `data-lf-*` attribute.

Layout follows the same ownership rule. CSS owns the document shell: `body` is
the `lf-shell` container, `main` composes margin claims, and container queries
choose their postures from the room actually left by panels and trays.
`syncLayout` measures only chrome whose placement or reservation depends on
rendered chrome, and writes only chrome boxes. A `ResizeObserver` callback must
not resize the box it observes, directly or through a class or attribute that
changes that box.

## Startup and presentation

A vendored runtime and registry are one generation. The runtime contains the
`"__LEAF_LAYER_GENERATION__"` placeholder and the registry carries the same
epoch after `page init`. `sameLayer` checks every successful state read and POST
response. If the server speaks a newer layer, the tab reloads before it reads or
posts again. Do not let one generation interpret another generation's registry
or events.

Startup order is load-bearing:

1. Begin the first state read without applying its answer.
2. Fetch and validate the registry.
3. Index passage fences and clone recordless authored widgets while the DOM
   still contains only the version's markup.
4. Import modules declared by `x-upgrade`.
5. Wait for module settlement, then run the shared dressing passes.
6. Capture authored record facets from the upgraded, authored state.
7. Mark `body` `data-lf-upgraded="1"`.
8. Apply the prepared state answer, reconcile it, and present the page.

`rememberAuthoredMarkup` runs before imports because a clone taken after upgrade
would contain generated controls and the module's once-only stamp. It stores
only widget families with a recordless durable action. `captureAuthoredFacets`
runs after upgrade because record-bearing widgets may arrange the authored state
in `connectedCallback`, but it must run before replay changes that state.
The state read overlaps those upgrades, but its answer stays buffered until both
captures have established the authored initial condition.

The served page root is a stable live document. Its first response projects the
latest immutable version and carries a runtime-only version marker. On a later
state read, `versionDocument` fetches the next immutable file in the background.
`activateVersion` replaces the authored head declarations, root attributes, and
`body > main`; runs the same fence, clone, dressing, settlement, and authored-facet
passes as startup; reconciles the log; and restores the semantic reading landmark.
The chrome, browser document, module globals, panel, and address remain standing.

That activation is one presentation boundary. Its async work runs in a
`startViewTransition` update callback where the platform supplies one, including
for reduced motion (whose transition duration collapses in the theme). Concurrent
state responses serialize behind `activatingState`; none may capture or replace a
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
  deliberate offline authored fallback, has crossed the presentation boundary.

Do not merge these stamps. A document can finish upgrading while its first state
read is pending, or the answer can wait unapplied while upgrades finish. A
projection can commit while finite reconciliation animations are still settling.
Any consumer that reads final boxes waits for upgraded, applied, presented, and
no finite animation reported by `moving`.

The presentation gate hides the authored `main` and makes it inert until the first
state read has either applied or established that the server is unavailable. The
static showcase's build sets `data-lf-eager`, which lifts the gate whole, leaving its
immutable authored document as ordinary readable HTML while its illustrative session,
widgets, and controls progressively arrive. Fixed recovery chrome remains usable while
a live page waits.
`showModal()` calls from authored main are temporarily represented as measurable
non-modal dialogs; `presentPage` promotes only connected, still-open dialogs whose
reconciled branch remains visible. This prevents a modal's top-layer inertness from
disabling the recovery chrome.

`presentPage` owns the one transition from arrival to live presentation. Motion
helpers and the stylesheet collapse arrival animations until that boundary.
After it, a state change may animate only where motion helps the reader follow a
change. A failed startup does not stamp the page presented as if it had read the
log.

`statePhase` distinguishes `waiting`, `ready`, and `offline`. An empty
`events` array while waiting means the log has not been read; it does not mean
there are no comments. A restored or newly opened panel keeps its general
composer usable and shows a loading state until that distinction resolves.

A failed fetch is a complete offline answer for presentation: the authored page
is honest when no log can be reached, so fixed status chrome reports the loss and
the page may appear. A successful response with malformed state is not an
offline answer. Parsing or rendering errors pass to the recovery boundary and
leave the candidate sequence unresolved.

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
or reported the local render error, because its continuation reveals and focuses
the thread the response creates.

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
it. An answer or thread-completion verb cannot require its own awaiting value, or
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
live DOM. Thread construction and recordless restoration can replace node
identities. Its result has four views: `actions`, `reports`, `classified`, and
`desired`. Add a browser consumer to one of these views or extend the Python wire
view instead of building another fold over raw `events`.

`committedProjection` is not a second state authority. It is a checkpoint of
what node identities and semantic winner the DOM currently represents. Each
entry records the widget node, unit node, and projected entry for one coordinate.
Node identity matters because a rebuild or thread reconciliation may replace a
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
it: a read of `GET /api/state`, an accepted POST answer, and the heartbeat
re-applying the state the page already holds. It:

1. verifies the layer generation;
2. rejects an answer taken before the one it holds, and an event sequence
   older than `lastEventSeq`;
3. loads the Markdown renderer before any message body needs it;
4. installs candidate `events` and renders all log-derived surfaces;
5. calls `reconcileState` after thread widgets exist;
6. advances `lastEventSeq` only after the whole state renders;
7. accounts for outbox attempts;
8. dispatches `lf-actions` after replay.

If any required render throws, `receiveState` restores the prior event list,
phase, sequence, and held answer. A candidate history may be visible only during its own
synchronous application. Focus, undo, draft settlement, and later asynchronous
wakeups must not consume a log tail the page did not adopt.

`reconcileKnownState` protects those wakeups. It permits reconciliation only
from the last complete sequence, or from the authored-only initial state before
any events have been installed. A read that brought nothing is allowed to retry
a deferred correction against that known state. It must not project a newer
candidate whose surrounding render failed.

`reconcileState` works at widget scope. When any coordinate in a widget is dirty,
it restores that widget's complete authored recorded composition, then applies
all current winners for the widget in logged and local order. This is necessary
for position units that share an ordered container; restoring one card against
siblings that still carry projected positions changes the meaning of its
authored index.

Every `applyAction(action, detail)` states an absolute value. Reapplying a
standing winner must be a no-op. Returning `false` means a live gesture prevents
safe application, so the coordinate and its outbox hold remain uncommitted until
a later wakeup. Throwing reports a page error and fails soft, but reconciliation
still records the layer-owned settlement paint when the declaration provides
one.

`watchProjectionDrag` waits for the last `.lf-dragging` marker to clear, then
reconciles, releases eligible outbox entries, repaints keys, and dispatches
`lf-actions`. Do not let a read or the heartbeat fight the pointer by applying
projection during a drag.

`rememberWrites` compares `shallowSigs` before and after each projected action
or report and records the ids replay changed. The render gate reads those marks
to check that a module writes only state declared by its record form. Text is
handled by the passage and restatement checks, not by the shallow signature.

### Authored restoration and undo

Record forms determine how authored state is captured and restored:

| Record kind | `domFacet` reads | `authoredDetail` restores |
| --- | --- | --- |
| `attribute` | sorted ids owned by the nearest recorded widget | the same sorted id set |
| `value` | the named attribute's string value | that value; absence has no statement |
| `position` | the declared containing id | containing id plus index among id-bearing children |
| `body` | collapsed words from `textNodesUnder` | the original uncollapsed authored words |

`authoredFacets` stores comparable values for pending-state paint.
`authoredDetails` stores the absolute detail that can state a unit's authored
value. `authoredStatements` groups those statements by widget for whole-widget
restoration. `authoredMarkup` stores a pristine clone only for recordless
families, where no verb can state the authored value.

Ownership of record members stops at `recordedOwner`, the nearest widget with a
declared record. A custom outer container must not capture or restore a nested
recorded widget's members.

An `undo` event names the event it withdraws. `takenBack` removes that gesture
from every fold; the log stays append-only. `undoable` walks the whole
authoritative log newest first, selects a standing user gesture, and offers an
action only on the version where that action was made. Thread resolution is not
version-scoped. Undo has no tab-local stack.

`canUndoAction` asks whether removing the action leaves a state reconciliation
can paint. For a recorded coordinate, that means another desired winner or an
authored detail exists. For a recordless action, the authored markup clone must
exist. Recorded state is restored by absolute statements and replay. Recordless
state calls `rebuild` with the pristine clone, re-runs shared dressing, refreshes
passage fences, restores focus when the reader was inside the replaced widget,
and replays surviving projection onto the new node.

`markSettled` and `renderRetired` are layer responsibilities. The registry's
`x-parent` and `x-retired-when` declarations already state which holder and slot
an outcome settles, so modules do not need to duplicate the settlement mark or
the generic retired-slot hiding. A module may paint the same
`data-lf-state` optimistically as choreography, but authoritative replay writes
it and clears it when another outcome on the settlement facet wins.

`paintPending` compares each desired record with `authoredFacets`. It paints
`data-lf-pending` for reader actions and `data-lf-reported` for reports only
while the log differs from this version's authored state. Recordless decisions
remain pending while their holder remains in the document. These marks are
renderings of the projection, never inputs to it.

### Version and conversation windows

A page widget's projection stops at `currentVersion`. Later actions and reports belong to
documents written after this version. A widget instantiated inside frozen thread
markup is in chrome and reads the whole action sequence because the conversation,
not a page version, owns it.

The server projects threads from the whole log, so a conversation stays current
on a pinned page even when the document projection remains historical.
Registry-declared `x-conversation` seats show an exact-section
textual view while the owner exists in the current document. The living margin and
Threads panel keep complete threads with mirrored interactive replies. A root
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
not narrate an action whose `applyAction` is deferred while the body still shows
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
`updateSequence` filters the server-normalized update feed. `watchActions` and
`watchUpdates` subscribe the two public readings to `lf-actions` and invoke the
callback immediately. The same rendering function therefore handles a module
connected before the first state and one constructed by a later thread reconcile.

`lf-actions` fires after a complete state has reconciled, including a read whose
event list did not grow and the heartbeat's re-application of the state the page
already holds. This lets a module refresh elapsed time and retry a render
deferred by live input without owning a timer or a second event cursor.
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
| `x-work` | the content or conversation seat in which local agent work may appear, with an optional condition |
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
  every `applyAction` is absolute binds it too.

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
  reconstruction.
- Use `once(el, fn)` for generated chrome so reconnecting does not duplicate it.
- Reserve a control's room from inside `measure`. A widget upgrades wherever the
  runtime connects it, and a shut panel is `display: none`, where every word
  measures zero and the floor the press needs is nothing at all.
- Implement `applyAction(action, detail)` as an absolute statement and return
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
- Read authored or user-facing words with `says`, never raw `textContent`.
- Build injected controls with `offer`. Use `relabel` when a control's label is
  also one of the page's words.
- Register keys with `keys(el, title, rows)` during upgrade, not at module load.
- Call `quoted(el)` before wiring module-specific gestures. `sendAction` also
  refuses actions on an exhibited widget at the layer door.
- A visual declaring `{parts: ATTR}` must implement `lfVisualPartAt(target)` to
  return one token from ATTR and `lfVisualPart(part)` to return its current
  `{element, label}`. The authored widget remains the comment seat, the token is
  recorded as `anchor.visual`, and the returned element supplies only mark and
  travel geometry. The render gate refuses either missing method.
- Render externally supplied or derived records through `projectData`. Its root is an
  authored, id-bearing seat; record keys are stable within that seat, and its renderer
  receives the prior node so unchanged controls and selections can remain in place.
- Declare each external input through the widget's `x-data`, then subscribe with
  `watchData(widget, input, callback)`. The authored source attribute is the page's
  binding; the named contract is the input's meaning. An optional declared snapshot
  attribute selects an immutable capture, while its absence follows the replaceable
  current value. Treat the delivered envelope as complete, render `null` as absence,
  and dispose the watcher when the element disconnects. The watcher captures both
  authored selectors at subscription; mutating a live attribute cannot rebind it. A
  module does not fetch or retain a second copy.
- Keep durable standalone state in serializable HTML attributes. Export removes
  scripts and handlers.
- Remove hoisted chrome in `disconnectedCallback` when a reconstruction replaces
  the owner.

An `applyAction` may replace nodes. Callers therefore re-resolve the widget and
unit between applications. It must write only attributes represented by the
verb's record form on authored elements. Generated chrome may use platform
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
version-diff readings all use them. Never introduce another text walk for one of
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

### Data projections

The page has three kinds of visible words:

- authored prose is in both `says` and `wrote`;
- runtime apparatus is in neither reading;
- projected external or derived data is in `says` and not in `wrote`.

The last kind is a projection, not another source of truth. An id-bearing element in
the version is its seat. `projectData(seat, records, keyOf, render)` owns that seat's
children, labels each rendered element with the seat id (`data-lf-projection`) and its
record's stable key (`data-lf-datum`), and marks it generated. Records remain the
caller's input; the DOM never becomes another record store.

Where records come from outside the document, their authority is `data.json`: one
page-owned store with a replaceable current value and retained immutable captures.
`$data.contracts` declares reusable meanings and schemas. A widget's `x-data` names the
contract, the attribute carrying this page's concrete source id, and optionally an
attribute selecting one capture by data revision. `leaf data set` validates and
atomically replaces the current value. `leaf data capture` reads a UTF-8 text file,
may slice an inclusive line range, and both replaces current and retains the value
under the new data revision.
Neither command appends an event or runs package code, and capture stores no source
path. Each stored source retains its contract even after clear, so re-vendoring never has
to infer meaning from a source's spelling.

A source id keeps that contract across every immutable version and widget frozen into
a thread. Bindings without a snapshot selector read current; durable documents may
select a retained capture. Clearing removes current and unreferenced captures but never
releases the id for a new meaning. Re-vendoring must preserve the page-lifetime binding
and every standing selection. `page state` exposes those bindings and consumers to
producers. The browser keeps the accepted data revision independently from
`lastEventSeq`, because overlapping poll and POST responses can order the authorities
differently. `watchData(widget, input, callback)` delivers a clone of
`{contract, updated, value}` for current, a clone with `snapshot`, `label`, and optional
`lines` for a selected capture, or `null` before a bound current value exists. Modules
project the result into the authored seat; they do not fetch it, mutate the accepted
copy, or keep a hidden current-value map of their own.

Keys identify facts, not renderings or display strings. They are non-empty strings,
unique within one projection, and must remain with the same logical datum across
refreshes. `render` receives the prior element for the key and may update it in place;
returning a replacement is also valid. Reconciliation retains nodes already in their
place and schedules the shared anchor pass after synchronous projection work.

A selection wholly inside one datum captures `{section, datum, quote}`. Resolution
looks only for that key under that section. If the original words still stand, Leaf
marks them. If their display changes, Leaf outlines the same datum and keeps the old
quote in the thread; it never follows the old string to an equal value elsewhere. A
missing or duplicate key detaches rather than guessing. Selections crossing datum
boundaries remain ordinary quote anchors because they name a passage, not one fact.

`data-lf-projection`, `data-lf-datum`, and `data-lf-gen` are written by `projectData`,
never authored in a version. A custom widget joins through the helper alone; no
consumer names its tag. Export preserves the rendered elements and their labels as a
snapshot, while dropping the scripts that could refresh them. Print preserves the same
readable words. Neither medium claims that the snapshot remains live.

The three visual voices are prose, apparatus, and evidence. Page prose uses the
serif, labels and controls use the sans, and literal evidence uses the mono
face. Typography is presentation, not passage permission. A chip may look like
apparatus and still be a page word the reader can quote.

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
`aimedItem` may keep document retargeting when the host is the semantic item.
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
The anchor runtime exposes only the questions those features ask — `isMarked`,
`placedAt`, and a snapshot from `pendingMarkParts` — so the pass-owned maps and
arrays cannot acquire a second writer through the entrypoint.

The same pass answers a second question and records it apart. `placed` is where
each thread's passage lands in this version; `marked` is what was drawn for it.
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
press on a page mark reaches `showThread`, which focuses the thread
with `preventScroll` before its deliberate reveal; the page and card therefore
both say which comment that press opened, and the next key belongs to the thread
scope. `paintHere` repaints it beside the decision ring, and `paintAnchors` repaints
it after rebuilding the ranges it holds.

The panel paints the same fact on the card, through `.lf-thread:focus-within` —
the same predicate, so the two halves cannot disagree about which comment the
reader is in. `:focus-visible` instead answers which input modality should draw
the browser's focus indicator.

`lf-mark-hover` answers a different question — which thread the pointer is
indicating — and reads both surfaces in one frame. A card is the thread's view in
the list the way a mark is its view in the prose, so resting on the card lights
the passage exactly as resting on the passage lights it, and a reader sweeping a
full panel is told what each comment is about without pressing anything. There is
one answer rather than two because the pointer is in one place: `markAt` refuses a
point that lands in the chrome, so `hoveredThreadOf` and the page's hit test
cannot both name a thread. Both are read inside `refreshHover`'s frame, which is
also what settles `:hover` — asking for it from inside the pointer event that
moves it asks mid-move — and a second writer to this highlight would be
overwritten by whichever frame ran last.

The whole card answers, not the quote alone, because the card is where the eye is
while it reads the comment. `body.lf-over-mark` stays with the page's own reading:
it is the promise that a press here opens something, and over a card the press on
offer is the card's, which `.lf-quote` states for itself. `setPanel` asks the
question again on the way out as well as in, because the panel is one of the two
surfaces this reads: closing it from the keyboard, with a hand resting on a card,
takes that card out from under a pointer that never moved.

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
target's living-margin item, beside that target's decisions and actions; the
pill inside is the reaction's own eraser, posting the ordinary `undo` through
`withdraw`. It wears `lf-ui` and `data-lf-gen`, so no reading takes it for the
page's words. `markAt` does not see it: a reaction takes no press to a card and
has no hover. Export keeps the glyph with its press taken off and writes the wash
into the words as a `<mark>` (BAKE), the highlight registry being script state
no file can hold.

The bar the selection raises is `.lf-fab-bar`: the `.lf-fab` comment glyph every
route into the composer still goes through, followed by one reaction ellipsis.
For a page target, the ellipsis hands Comment and the layer's token buttons to
that target's shared margin item; it never opens a box below the floating bar.
`showFab` shows and places the compact bar; `activateAimTarget` raises it for both
the ⌥ press and keyboard item hint. `r` opens the same choices on the selection,
the standing item, or the latest agent message in the thread the reader is in.
With none of those targets, it shows “Select something to react to” and opens
nothing. Page-wide reactions remain an explicit ellipsis above the panel's general
comment box. `REACT` claims the keyboard while a list is open: arrows move among
tokens, Enter or Space presses the focused one, digits remain optional accelerators
in declaration order, and a stray key closes the list before keeping its ordinary
meaning.

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

`scrollToThread` is the one travel every "show me that comment's passage" ends
in. The target's own box first comes into view instantly, including inside a
sideways scroller, then `moveScrollerBy` glides the exact mark to its final position in
the region that holds it. The travel owns no standing or arrival state. Focus
already supplies the durable answer through `paintStanding`, and a transient
page effect does not observe, restart, or reconcile across the browser's
scrolling operation.

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

`placeClear` moves floating controls away from selectable or interactive content
they would cover. It reads the general `data-lf-offer` marker, not a list of
widget controls.

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
its place for the page's life. When a row runs out of room, the leftmost
status-like item may yield its own width so controls to its right remain fixed.

`syncLayout` derives only floating chrome placement and reservations from current
chrome boxes. CSS owns the document shell: `body` is the named `lf-shell` inline-size
container, `main` composes its left and right claims, and container queries grant or
withdraw margin postures. No JavaScript measures that shell or mirrors a cramped state.

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
`--lf-claim-right` is the project-layer extension claim. A script-free copy therefore
answers the same layout from its own viewport without exporting session geometry.

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

A handle lives inside the region it draws, so a drawn region must not be its own
scroll container: a scroller clips a handle straddling its border and carries it
away with the content. A tray is a shell holding a `.lf-tray-list`, and every
tray list reserves the key line's room. Wide content reads the shell's CSS value directly;
there is no observed measurement loop or second number system to reconcile during a
transition.

The banner and key line reserve their space in normal flow. A fixed or absolute
chrome surface may lie above that reservation, but the reservation itself
travels to print and export only when that medium contains the surface it
serves.

### Target margin items

The right margin has one projected item per page target. That item is the single
place for controls the reader can use on the target, communications they can
start about it, and standing information such as comment threads, decisions,
outcomes, changes, or agent activity. It is a flex row: content controls precede
the target's page-map marker, and temporary communication controls follow it. A
target with no map reading may have controls without a marker.

Content modules contribute through `registerMarginItem`; they own their verbs and
events, never placement or control styling. Every press in a contribution is built
with `marginAction(control, {glyph, label, tone, collapse})`. That is the one RHS
control type: it owns the capsule, height, type, focus, state paint, and the glyph/word
anatomy shared by decisions, editing, communications, and information triggers.
Horizontal width may follow the label. `collapse: "auto"` keeps the word whenever the
complete target item fits and hides it only when the shared layout needs the room;
`always` is for vocabulary whose glyph is sufficient in the row. Collapsing changes
paint, not the DOM or accessible name.

The living margin groups contributions and state readings by exact target identity
and owns one generated host plus its accessible group name. At wide widths it hoists
that host into the main positioning context, preserving source and tab order when
several targets share a top-level block. At compact widths it returns the host to flow
immediately after the target's rendered text block (or the target itself). Adding
another target action must not add another absolute row, control type, or rail
measurement.

That ordered target collection is the Page map's complete location count and the source
for the `g m` address list. A location's informational marker announces its position in
the complete collection. The numbered chord exposes the collection's first nine
locations; later locations remain in the Page map and ordinary focus order rather than
making a one-digit chord ambiguous. Addressing an item opens its marker when it has one;
an action-only item receives focus on its first available action without performing it.
In the compact posture, an informational item opens the Page map sheet at that location
instead of reviving the hidden desktop preview; an action-only item keeps its direct
focus arrival on the action docked into the page.

`margin-layout` places, packs, docks, and measures the complete host. Its rail
claim is the widest stable contribution seen and is monotonic for the document's
lifetime, so settling an action cannot shift the readable column. A temporary
contribution registers with `claim: false`: it borrows available RHS room and
docks the complete host when it cannot fit, without moving the column on first
open or leaving blank room after close. Below the margin breakpoint the complete
host docks into flow. Visibility and vertical placement read `shownParts` and
`shownBox`, not the target's raw client rect: a project may set `display: contents`
while its rendered descendants remain usable, and a collapsed target has no
rendered part to offer.

The reaction key extends this same item for a page selection or item. It moves
Comment and the declared reaction buttons to the right of the existing marker;
it does not open a palette below the target. Conversation reactions remain in
their conversation-owned strip. The event still carries its durable authored
anchor, while the temporary item resolves selected text to the first rendered
block, matching the target where replay later seats its standing reaction.

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

Synthetic restoration steps are silent. When reconciliation resets a widget to
its authored composition and applies several winners, intermediate absolute
placements must not animate. Capture the final authoritative correction and
show one FLIP from the optimistic state to that result. A live drag defers the
whole correction.

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
at upgrade, on a new version, on a rebuild, on the panel's reconcile — so a
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

The reader's cell is an option and is dressed as one. It holds a conversation
seat rather than a pick, but what it is for is the answer the menu hasn't got,
so it takes the cells' fill and their column and states no inset of its own. A
cell that dresses as apparatus tells the reader to skip it.

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

`--serif` is the page's prose, `--sans` is apparatus and runtime chrome, and
`--mono` is literal evidence. `.lf-ui` reads `--sans`. Form-control normalization
lives in the `lf-reset` cascade layer so an unlayered semantic type choice can
override it without specificity contests.

The runtime's private stylesheet is one `@scope` rooted at `.lf-chrome`. Private
class names do not escape that root. The global vocabulary is deliberately
small: shared `.lf-ui`, `.lf-btn`, `.lf-pill`, `.lf-address`, and the markers the
runtime paints on page elements. Adding a global selector widens the widget
contract and must be covered by the render suite.

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

A press that opens a surface and then steps into something inside it pushes two
layers at once, and Escape can only hand one of them back. The reader reads that
as Escape not undoing what the key did, and no surface can tell them otherwise,
because what the key line promises is one press. Where a press looks like it
wants two layers, the second layer earns a key of its own — usually the same
letter again, from the scope the first press stood up. That press is the
reader's own next step rather than a toll, and the layer it leaves between is
where the surface's own keys become reachable at all. `c` into the thread panel
and then its box is that shape, and the paragraphs above own the detail.

Landing focus in what a press opened is arrival, not a second layer: a tray on
its first row, the versions menu on a version, the panel on its list. The second
layer is a box the surface does not shadow — the reference's search box is inside
a surface too, and what keeps it one layer is `HELP` standing nearer with a claim
over the whole keyboard, so the box's letters were never the page's to take back.

The rule holds for a sequence as much as for a surface, where the stack it is
about is the reader's rather than the dispatcher's. The address chord arms on
`g`. A panel mnemonic exchanges that window for its destination, so `g T` leaves
the Threads panel as one Escape rung. A document-list mnemonic narrows the
window instead: the armed chip reads `g` and then `g h`, the chips on the page
narrow with it, and Escape returns to the destination menu before another Escape
closes it.

A layer also owes a way out at all, over the same page the way in is live on.
`versionsOffered` (there is a menu) answers for the key, the mode binding its
Escape, and the button; `versionsToWalk` (there is somewhere to step) answers for
the menu's own scope. One predicate for both left `v` opening a menu on a page
whose Escape no scope was live to bind. A section merges the rows of every scope
sharing its title, so a contributor the page hasn't got must bring none — `merge`
drops it — or the two capabilities cannot differ in liveness under one heading.

A press may deliberately leave layers standing while moving focus outside them. That is
not an Escape rung, because it gives no layer back. The address chord states what remains
open: beside the document, `g p` returns from the thread panel to the document and keeps
both the panel and its narrowing. A panel covering the document cannot make that promise,
so its ordinary Escape rung remains the route back.

### Item selection is explicit

`s` names the visible items and declared visual parts that Alt-click can aim at. Both
routes read `aimTargetAt`, then raise the same comment and reaction bar. The target kind
changes only the anchor: a whole item names its authored id, while a visual part adds
its declared token and resolves the bar against that part's geometry.

The short, viewport-local hints form a prefix-free tree over one alphabet. Most targets
cost one letter; only the tail branches when the viewport holds more targets than the
alphabet. Unlike `g` addresses, these hints are ephemeral and make no promise across a
scroll or revision. They are the whole route, so none may be dropped because its chip
collides.

Tab and Shift-Tab walk the visible target map and announce each item. Enter chooses the
last one announced. A viewport change that removes or renames that target clears the
announced choice before Enter can act on it.

`/` opens a real search input over the whole page reading, either directly from the page
or from the visible item hints. Tab walks repeated occurrences and Enter makes a native
browser Selection from the active match. Escape returns to the surface that opened search:
the page after a direct `/`, or the visible hints after `s` then `/`. The mode keeps `?`
available and claims the rest of the page's keyboard while it stands.

`rung()` has a single `panelOpen` branch, and that is the rule rather than a
looseness in it: a surface and where the reader stands in it are one layer. The
panel's list and the thread `t` walks to are the same rung, which is why `c` from
either of them is the box — the box being the layer below. So the click that
opened the panel is the press one Escape gives back, whichever of its contents
the reader walked to first.

The register owns capabilities, not controls. Every capability the chrome offers
has a row, and each control that reaches one names its key through `also`; a
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
is often repeated or held. `d` and `u` move down and up by 60% of the reading page,
leaving native Space free for the platform and focused controls. Other letters come
from words the surface says: `w` narrows to threads waiting on the reader, while panel
destinations use an uppercase mnemonic after `g`: `g T`, `g A`, and `g L` go to
Threads, Asks, and All leaves. A key spelling something nothing on screen says is a
key nobody reaches for twice.

A row whose press turns a mode on and off states the mode rather than the toggle.
`does` and `line` are functions of whether it stands, so the sentence says which
way this press will go, and Escape takes the mode off through the rung ladder
rather than through a second binding of its own.

Which scope a row belongs to follows from what its press acts on. The page holds
the presses whose subject is the page: `/` searches its text, `s` names its visible
items, `c` comments on it, `t`/`T` and `a`/`A` walk its open sets, `d`/`u` move its
reading, and `g` opens its destinations. A surface holds the presses
whose
subject is that surface's own
contents, because contents the reader is not looking at are not a thing to act
on: `w` narrows the thread panel's list and `/` searches it, and both live in
`PANEL`. The page's alphabet is small and every letter spent there is spent on
every page, so a letter earns page scope only by acting on the page.

A surface may also hold the next step of a page key, which is the third row in
`PANEL` and the one exception the rule has: the page's `c` lands the reader on
the comment list and the panel's `c` puts them in its box. The letter is the
same because the intent is, one scope in — as `g` names a document list and then
a member of it — and the inner row stands down wherever the page's own key has a
nearer
answer, so the two never offer the reader a choice about which one runs.

A scope's rows act on contents the reader is looking at rather than standing in,
which is why they can be sorted by surface at all. One press is not like that:
`c` follows the reader, and what it means is whatever they are standing in.

That it reaches into the panel is not an exception. Page scope already crosses
there: `t`/`T` can land on cards in Threads, and `a`/`A` can land on an ask an
agent sent inside a thread. A page key that takes the reader somewhere owes them
an answer once they are standing there.
Rescoping `c` per surface would not even buy the tidiness it looks like — the
reader stands in one place at a time, so it is several rows spelling one key,
each live exactly where the others are not.

Its destination is the anchor the 💬 carries, then the open thread the reader is
in, then the item they are standing in, and, when none of those is in hand, the
conversation itself. `commentDestination` decides it once and states the
sentence, the key line and the press together, so the reference, the line and
what happens cannot come to spell it differently. The pointer's answers outrank
the standing: a selection or a raised 💬 is the more recent thing the reader
said. `standingItem` and `standingConversation` are what "standing" means here,
and **Standing somewhere** below owns that reading.

The last of the four names the room rather than a box in it, and is the one place
a surface holds a `c` of its own. It is not a second reading of the page's key
but the same intent one scope further in, the way `g` names a list and then a
member of it: the page's `c` opens the panel and stands the reader on its list,
and the panel's `c` puts them in the general box. Landing straight in that box is
what it replaced, and that box is the one place in the panel where the panel's own
letters are all shadowed — the typing scope claims a letter first — so the press
that promised the comments left `w` and `/` unreachable until the reader pressed
Escape. The panel's row is not the several-rows-one-key shape either, because it
stands down wherever the page's key has the nearer answer: a live 💬, or the
conversation the reader is standing in, whose own box `Enter` already reaches.
A resolved thread offers no box, so the row answers there and the general
box is the honest destination.

The item's box is the composer, on the item, and not a widget's own conversation
seat even where it has one. `openOnItem` writes the anchor `renderConversations`
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

Widgets register through `keys(el, title, rows)` in
`connectedCallback`. A module loaded on a page with no instance must contribute
no scope or help section. Runtime scopes live in `SCOPES`; `merge` is the only
function that gathers scope sections. Preserve the order of that list because
the dispatcher and key line walk inward to outward while the full reference
groups the same scopes for reading.

A row has these meanings:

- `keys` is a binding or computed list of bindings.
- `does` is the sentence for the press, or a function when the current state
  changes the sentence.
- `when` says whether the capability exists.
- `at`, expressed by the current `readerIn` predicate, says whether this press
  can act at the reader's current position.
- `run` performs one result. A run-less row names a press it does not make: the
  platform's own on a link, or one another scope's row already runs.
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
before `TYPING`; the general text-entry claim then stands before any ancestor
widget, and ancestor scopes still stand before unrelated core modes. Escape lets
the narrowing go, and the box on the press after that. One press is one rung there
as everywhere else.

A box hands the reader back to the conversation it is written in, which is the
rung `c` came down. `backFromBox` climbs `SAYS_IN` from the box where
`standingConversation` climbs it from where the reader stands, so the press in
and the press out name one element and one word — "comment on the thread" going
in, "back to thread" coming out. The panel's general box has no conversation and
lands on the list. A page-owned first-message seat has no standing place of its
own; a widget control that explicitly enters its box supplies both the return
control and the caller-owned word for that route through `landInConversation`.
A visit reached by Tab supplies neither and leaves the page's own "let go"
standing. Asking whether the container can take focus is what keeps every other
route a relation rather than a list of containers that happen to be focusable.

A key may repeat across nesting scopes to mean the same intent one scope further
in. `c` reads that way: from
the page it goes to the comments and stands the reader on the list, and from
inside the panel it opens the general box. A landing is chosen for the keys it
leaves live — the general box shadows every letter the panel's own scope binds,
so landing there would have made `w` and `/` cost an Escape first. Put the reader
where the surface's keys answer and let a second press take them into the box.
Where a box has a key that reaches it, the box says so itself through its
placeholder `address`, which is what a screen reader hears.

A true mode may own the keyboard. An armed address chord and the open reference
claim the relevant keys through their scope. A longer-lived menu keeps the
reference available through `allButTheReference`. Closing an overlay restores
focus to `helpFrom` so the reader returns to the control that opened it.

Escape is an ordinary binding in the register for Leaf-owned modes. The innermost scope that binds it
owns one unwind step. A control-specific Escape, panel dismissal, decision release,
and return to the page cannot cascade from one keypress. A scope does not need a
private `keydown` listener or hand-written `preventDefault` to protect that
contract.

Auto popovers and modal dialogs are the platform's modes. While one is the active top
layer, the page rung stands down and browser Escape closes it; Leaf updates from the
resulting `toggle`, `cancel`, or `close` event. Register Escape only when Leaf adds a
distinct inner step, such as leaving a text box before closing its dialog or collapsing
the keyboard reference's expanded shelf.

`offer` creates the native element named by the caller; ordinary buttons and links need
no Leaf activation binding. A `selectableOffer` registers its widget-specific keys.
A run-less row may still project a native press when that meaning is worth naming in
help, but it never reimplements the press.

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
already, and the log's news about the content — `restated`, `pending`,
`reported` — has no second carrier, while the band also has the washed cell and
the address chips.

Every rule that draws the ring names it in `--lf-here-ring`, in the same
declaration (theme.css carries why). Whether a box wears a ring is the outline's
answer; the name says which rule drew it, so nothing re-runs the layer's selectors
to find that out. The property is registered non-inheriting, so a name means the
box rather than each of its words.

A press that acts on where the reader is standing reads it through
`standingItem`: the unanswered decision where focus is on a control that works it — a
pick, a ✓, a mark — and the innermost item everywhere else, which is the ⌥ aim's
own reading. It answers nothing in the chrome, where a reader is working on the
page rather than standing in it.

Unanswered rather than open: `standingIn` reads `unansweredDecisions`, not `openDecisions`.
The two part on a widget whose own seat is mid-conversation with the agent, which
leaves the reader's list while its pick stays unmade and its controls stay live.
Following the list took the ring off that widget the moment the remark was sent and
moved `c` down to whichever option the focus rested on — a second thread on the
child rather than the next line of the reader's own — and the agent's reply put both
back, with nothing the reader did moving either. An answered decision parts from neither
list, so a picked group gains no ring, and a press from one of its picks names the
option under the focus rather than the question.

The ring is therefore paintable on a decision the `a`/`A` ask walk will not step to and the
tray does not list, which is the accepted cost: the walk and the tray are the reader's
list and this is not. Nothing strands the reader there — `markHere` looks its tray row
up by id and finds none, the same as on every page with the tray shut, and the Escape
rung reads focus rather than the list, so the way out is the one they always have.

Working a decision and standing in one are different facts, and `markHere`'s ring
answers the second. A reader who addressed a link inside a question has named
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

`landed` stores where the decision walk last arrived. This is distinct from focus:
the banner's Asks button retains focus while the walk moves through the page.
Clicking elsewhere removes the focus-derived ring without erasing the walk's
useful continuation point.

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
which is the same thing the ring reading declines to report.

`test_no_ring_the_panel_draws_on_a_walk_down_its_list_is_cut_or_covered`,
`test_a_comment_the_pointer_lands_on_comes_out_from_under_the_run_heading`, and
`test_every_ring_the_layer_draws_is_shown_whole_somewhere_in_the_corpus` hold
this for the panel's own walk, for a press inside its list, and for every shipped
page's tab order. They ask one question: where the control can be seen, so can the ring
that names it. A control that itself stands under a fixed bar is not a finding —
that is a fact about where it was put — and neither is a box too tall for the
region it is in.

`rung` and `letGo` put focus on `body` when the reader leaves chrome or releases
a decision. `body` has a tab stop because a short page may not become focusable from
overflow alone. Focus rather than blur hands Space, PageDown, arrows, Home, and
End back to the page's actual scroll box. `letGo` also runs synchronously during
module evaluation so a fresh page accepts native scrolling before asynchronous
upgrade, without stealing focus from a control the reader reaches during that
upgrade.

### The key line and reference

The key line is short help, not the keyboard reference. It walks outward from the
reader's innermost scope and drops bindings shadowed there. The ordinary shortlist is
the first live row, then a promotable Escape or the next row; rows declaring
`linePriority: persistent` remain beside that context. An active chord instead shows
every live row in its scope, so computed bindings, ranges, and capability filtering are
the same ones dispatch and the reference use. `lineWhen` may hide only an ordinary hint
without changing the command's liveness or its place in the reference. Hint chips are
`aria-hidden` because placeholders and live announcements carry the same facts for
assistive technology.

The compact line wraps when persistent or chord rows need the room. Ordinary hints may
yield from the end to stay within two rows, but persistent rows and active chord rows do
not. The interactive More control stays before persistent hints, so a wider face wraps a
visual fact rather than moving a compact target down beside page or panel furniture.
`syncLayout` reserves the rendered height in each scroll region.

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
row's `also` control exposes the key that duplicates it. `Mod` expands to both
Meta and Control because the dispatcher
accepts both. Call `paintKeys` when a state change moves row liveness so this
projection and the visible surfaces change together.

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

The live root follows the newest version without navigating. It begins fetching
as soon as a state read announces the version, but `midComposition` or an open
version menu defers activation and leaves the newest-version chip visible. Ending
the composition releases the version on the next heartbeat; pressing the chip is
an explicit override and still keeps the live address. `goVersion` is the one door
for both that in-place newest-version request and travel to an older immutable
version.

An older version is historical rather than live: choosing one navigates to its
immutable file with `?pin`, and it stays at `currentVersion` while offering the
newest-version chip. The view record carries reading position and the decision-walk
landmark across that document navigation. Focus and a selection do not cross to a
new document. On live activation, runtime-chrome nodes and their focus survive;
authored-main nodes are replaced, so the semantic landmark—not a DOM node—is the
continuity guarantee.

The left side holds one tray at a time. `showTray` owns `trayUp` and renders
the complete outcome for leaves and asks. The leaves tray overlays the
document because its rows leave the page. The asks tray takes a strip because
its rows travel within the page and the reader must keep the target visible.
Both entry controls call the same tray setter.

`restoreTray` runs after all declarations exist and after the first projection
can populate state-dependent rows. It calls its supplied `beforeOpen` policy to
retire Threads, then presents the remembered tray directly without replaying
opening motion. `ARRANGEMENTS` supplies one render arrangement for each persisted
tray.

Decision rows come from local `x-awaits` sources and ready holders declaring
`x-request.decision`, not from a list of decision tags. Where an `x-awaits` source is
nested in an `x-decision` region, the row names the region: its heading, context, and
evidence are the decision the reader is being sent to, while the source remains
the owner of the answer. `itemSays` supplies each row's own label. Selecting a
tray row travels through the same decision-arrival function as `a` and `A`, so the
panel and directional walk agree about focus, reveal, start-aligned scroll, and
`landed`.

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

That combined reading is what `openDecisions` returns, so the
banner, the tray and the `a`/`A` walk all follow it: those three are the reader's
list, and a request the agent owes the next word on does not belong on one.

Three readings ask the other question — whether the request is *answered* — and all
say so by emptying the seats (`answeredContext`, stated beside the shape rather than
by a caller reaching into it, so a member derived from those conversations later
cannot escape the emptying). An action's `requires` is one: a conversation does not
answer a question the widget holds no state for, and refusing a pick over the reader's
own remark would refuse them the answer they were asked for. The version-response
resolve gate is another. Where the reader is standing is the third, through
`unansweredDecisions`; **Standing somewhere** owns it. Frozen thread markup seats no
conversation of its own, so only an action answers there. A `rollup` instance is an
aggregate-only owner: it awaits when any nearest local decision or child roll-up
awaits, but it never enters the visible list. The standing projection keeps every
open local member; an enclosing `x-decision` replaces that member only on the
visible/navigation surface. `actionAvailable` still queries whether the source or an
ancestor's aggregate is open. A module reading `openDecisions()` calls
`decisionSource()` when it needs the actionable widget rather than the reader-facing
region.

### Go-to chord

`g` opens one destination mode. `T`, `A`, and `L` complete a direct trip to
Threads, Asks, and All leaves. `m`, `h`, and `f` name the page's numbered
page-map item, hyperlink, and fold lists, and one digit names a member. `g g` and
`g G` complete the chord themselves, gliding to the top and bottom of the visible
scroller. When a thread holds focus, `g k` and `g j`
place that card at the top or bottom of its list without moving the page. From a
beside-panel, `g p` returns focus to the page while keeping the panel and its narrowing.
An edge is one place, so the second key is the whole address; because every page has a
top, the mode never arms empty and the page-level `g` row needs no capability gate.
`PANEL_DESTINATIONS` is the direct panel vocabulary. Each entry declares its
mnemonic, words, capability, and landing. `ADDRESSES` is the numbered page-list
vocabulary. Each entry declares:

- its letter and user-facing name;
- the sentence shown in help;
- its members in stable address order;
- how to arrive at one member.

A list's capability is not declared: it is whether the list is non-empty, read
where the row asks. Consumers do not branch on which address list is active.
Adding a panel destination or a numbered list adds one entry to its vocabulary.
The page-level `g` row promises only the mode; destinations and ranges belong to
the rows inside it.

Arming the mode paints the whole offer. A panel mnemonic completes the travel and
moves focus inside the panel. Every numbered list contributes chips for its first
nine members at once, and its mnemonic narrows them to that list. The following
digit selects immediately. Escape backs out to the list menu before it closes the
mode. A chip carries the whole address — leader, letter, and number — so it states
which member this is and what remains to type. Every key on it is set at the chip's
one size, and the split between what is
behind the reader and what is still to press is carried by ground: the spent keys
sit on the chip's own, the live ones on a lit block (`.lf-spent`, `.lf-lit`). Colour
alone will not carry it — muted against accent is a difference in hue and barely one
in lightness, and on a key that small the two halves read as one word — but size was
the wrong second channel. One box holding two type sizes reads as a fault, and
because a press moves a key from one size to the other it re-set every chip on
screen, each narrowing 2.4px and sliding 1.2px as the reader was reading it. A lit
ground says the same thing while taking no advance — the block's padding is cancelled
by an equal negative margin — so a press lights one more key and moves no glyph. Paid for
in advance instead, the key crossing between the halves steps by that padding, which is the
same fault one glyph smaller.

While the chord stands, the key line uses that same accent ground for the leader and
the visible continuation keys. The active colour belongs to the chord state rather than
to one hard-coded key, so every future continuation inherits the cue.

`chordKeys` is the one reading of how far a numbered address has come. The key
line drops those keys after saying them in the chip that heads it, the reference
puts them in front of each row so every entry shows the complete chord, and a
chip on the page sets them back.

Numbered addresses are stable within the document and capped at nine per list. The
first nine members do not change identity as the reader scrolls. Chips are painted
only for addressable members whose `shownRect` is visible, but an off-screen member
within that prefix remains reachable by the same address. Chips live in runtime
chrome rather than authored markup.

`NATIVE` describes the platform controls a chord may land on and the immediate
word for their next press. A summary says whether it will open or close from its
current state. This avoids one scope per native tag while keeping the next press
visible.

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

`captureView` stores a passage-based reading landmark, correction within the
block, and the last decision landmark. `restoreView` resolves the landmark after
upgrade and corrects the scroll from the rendered box. A URL fragment outranks
the saved view on a fresh navigation; the saved view outranks a leftover
fragment on reload or back navigation. `landArrival` applies that ranking only
after final page geometry is available.

Focus and selection are not restored across documents. Restoring focus onto a
control would change the next Space from page scroll to activation, and a
selection may refer to words the new version replaced. The saved decision landmark
preserves directional continuity without claiming the reader still stands
there.

## Chrome, conversations, and text input

`.lf-chrome` is one fixed runtime root containing the banner, the tray panel,
thread panel, composer, floating comment control, toast, live region, key line,
help, inspection paint, legend, and address layer. The page and panel are
separate scroll regions. Opening or closing one calls its state setter, updates
the persisted intent, and schedules the shared layout and key paint.

`.lf-work-line` is transient runtime chrome that may also stand inside a page
widget. `paintWorkLines` is its one writer. A thread subject paints in the panel
and every inline conversation seat; a page-widget subject paints only in the
content or conversation seat its active `x-work` declaration names. A content
seat is block prose, but block prose alone grants no seat. The line wears `lf-ui`
and `data-lf-gen`:
it is an account of the widget, not authored words of the widget, so selection
and diff readings skip it. Reconcile widget state first and paint work afterward,
because a module may rebuild the subtree that seats it. Keep surviving nodes
across state applications so an unchanged claim is not re-announced.

The thread list reconciles nodes rather than rebuilding them. `setChildren`
preserves existing message, reply, and textarea nodes when the same event still
stands. Applying a state must not discard a reader's caret, focus, reply text,
or disclosure state. Reconciliation preserves node identity; the list's own
hold, rather than the browser's scroll anchoring, preserves viewport position.
Tests pin the thread's box rather than a particular scroll offset.

`renderThreads` holds one live card through every list mutation. It chooses the
card under the pointer while the pointer is in the list, then the card containing
focus, then the topmost visible card. It records later visible cards before the
mutation and refreshes their baselines after each correction, so a live successor can
take over if the first leaves or becomes hidden. The held `paintWorkLines` call covers
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

`revealThread` and `showThread` are two asks, not one with a flag.
`revealThread` confirms something the reader was already watching — a reply
landing in a thread in front of them — and takes the list as it stands.
`showThread` insists: a press out on the page or in a message knows nothing of
the narrowing it would be asking past, and a comment the reader has just written
cannot vanish into a narrowing it does not match, so the narrowing goes instead.
It focuses the containing thread before `revealThread` scrolls it, making the
thread the standing result rather than a card flashed while focus remains on the
page. `preventScroll` keeps that focus call out of the scroll, so the list's own
landing and then the reveal place the thread, in that order.
A reveal that widened for a reply would take the reader's narrowing away for
having been used, which is how the waiting-on-you list is emptied.

Messages render from Markdown after escaping raw HTML. Literal text such as a
generic type remains text and cannot inject markup. Interactive event `markup`
has a different door: only the CLI can write it after validating against the
vendored registry, while the browser event schema refuses it. A widget in that
markup is instantiated once in the panel; inline conversation seats show a
textual projection rather than copying interactive ids.

An agent message edit is a later event folded onto the original message id. The
panel and an inline conversation update the existing message node and show
`edited`; the text wrapper alone is replaced. The message's cached markup nodes
stay connected because their widget state and authored baseline belong to the
original event, not to the prose revision.

Fragment links in messages use the browser's `hidden="until-found"` behavior to
reveal authored disclosures and tabs. `paintAnchors` marks a link detached when
this version no longer has the id and refuses its press. A thread outlives its
version, but a fragment target may not.

`wireInput` gives runtime textareas the same input contract: persist each edit,
send with `Mod+Enter`, keep the send button and placeholder current, and prevent
parallel sends of one local surface. The stylesheet owns textarea growth through
`field-sizing: content`. Script does not measure or set textarea height.

The selection composer keeps its passage painted after focus moves into the
textarea. It quotes the passage in the box only when the current version can no
longer paint it. `showComposer` states the whole visible and focus outcome from
`composerOpen`, `pendingAnchor`, and `fabAnchor`. Outside clicks and Escape hide
without discarding words; Cancel explicitly discards.

Sending a comment reveals and focuses the thread created by the accepted event.
News arriving without the reader's send gesture may show a toast and count but
does not move focus or scroll the panel. `showToast` clears click behavior as it
fades so invisible toast chrome cannot remain a pointer target.

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

An `lf-draft` editor is a live gesture. Its `applyAction` returns `false` while
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

Paint that promises a gesture — the pointer hand above all — hangs on how a press is
spelled (`button`, `[role="button"]`), never on a control class alone. Export takes
the role off and leaves the class, so a hand hung on the class is a hand a file cannot
answer. A control that keeps its shape in a copy keeps its name too, and the name needs
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
`data-lf-said` preserves a decision word the page speaks through a control.
`paperWords` compares the screen and print readings across the whole page.
`coveredWords` runs again in print. A wrong offer/said declaration is fixed
where the label is created, not by naming its widget in print CSS.

The live-page scrolling and chrome reservations stay under the live guard. A
copy with no panel uses an ordinary centered document and must not retain room
for absent runtime furniture.

`test_an_exported_example_stands_on_its_own` strips scripts, opens the copy, and
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
| `relativeReplays` | reapplying each standing absolute winner moves nothing |

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
- `test_first_replay_is_the_pages_first_presentation` covers the presentation
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
