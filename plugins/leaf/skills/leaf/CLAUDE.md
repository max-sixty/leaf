# The page in the browser

This file defines the contract for `assets/leaf.js`, the widget modules, and
`assets/theme.css`. It describes the current runtime. Page-authoring commands and
markup rules live in `references/page-authoring.md`; layer overlays and widget
scaffolding live in `references/customizing.md`. The repository-level `AGENTS.md`
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

`leaf.js` is one ES module with two layers. The widget layer loads the vendored
registry, imports modules declared by `x-upgrade`, renders registry-declared
words, and reconciles recorded state. The comment layer polls `GET /api/state`,
posts to `POST /api/event`, renders the status and conversation chrome, captures
anchors, and handles keyboard navigation. Both layers share the same registry,
passage model, event list, layout readings, and helper surface.

Each mutable fact has one writer:

| Fact | Authority | Browser writer |
| --- | --- | --- |
| authored widget state | the version's markup before upgrade | `captureAuthoredFacets` and `rememberAuthoredMarkup` capture it; neither changes it |
| version shown by the live document | the latest immutable version accepted at the activation boundary | `activateVersion` advances `currentVersion`; an immutable version path derives it from its URL |
| accepted history | the server event log | `receiveState` replaces `events` after a complete read |
| unresolved browser work | the ordered `outbox` | `post` adds, `accountOutbox` and `releaseProjectedOutbox` remove |
| rendered semantic state | authored state, log projection, then outbox overlay | `reconcileState` |
| proof of what the DOM currently represents | `committedProjection` | `stageOutboxAction` and `reconcileState` |
| anchor paint | thread and composer anchor records | `paintAnchors` |
| where each thread's passage lands | this version's resolution of its anchor | `paintAnchors` writes `placed` |
| composer visibility | `composerOpen` and `fabAnchor` | `showComposer` and `showFab` |
| panel visibility | `panelOpen` | `setPanel` |
| the narrowing on the thread list | the reader's find words and waiting-on-you press | `renarrow` and `widen` |
| tray visibility | `trayUp` | `showTray` |
| region width the reader drew | the reader's store, per edge | `drawnEdge`'s `set` and `restore` |
| keyboard meaning | registered scope and row objects | the dispatcher and each visible key surface read the register |
| draft generation | the reader's draft record | draft-store helpers and `watchDraft` |

Do not add a second cache, pending map, widget-specific replay list, or DOM
attribute as another source for one of these facts. A rendering may expose state,
but callers do not read the rendering to recover it. For example,
`style.display` does not answer whether the composer is open, and a focus ring
does not remember where an ask walk last landed.

`PAGE_PAINT_ATTRIBUTE` is the runtime's one list of attributes it may paint on
authored elements. `shallowSigs` excludes exactly those attributes. A widget's
own `data-lf-*` state remains visible to replay and to the render gate. Add a
runtime-authored attribute to `PAGE_PAINT_ATTRIBUTE` when its writer is added;
do not broaden the exclusion to every `data-lf-*` attribute.

Layout follows the same ownership rule. `syncLayout` may measure
`document.body`, but it writes only chrome boxes. The banner's reservation is
`body::before`, and the key line's reservation is padding on the chrome
container. Panel and tray strips come from attributes and media queries. A
`ResizeObserver` callback must not resize the box it observes, directly or
through a class or attribute that changes that box.

## Startup and presentation

A vendored runtime and registry are one generation. The runtime contains the
`"__LEAF_LAYER_GENERATION__"` placeholder and the registry carries the same
epoch after `page init`. `sameLayer` checks every successful state read and POST
response. If the server speaks a newer layer, the tab reloads before it polls or
posts again. Do not let one generation interpret another generation's registry
or events.

Startup order is load-bearing:

1. Fetch and validate the registry.
2. Index passage fences and clone recordless authored widgets while the DOM
   still contains only the version's markup.
3. Import modules declared by `x-upgrade`.
4. Wait for module settlement, then run the shared dressing passes.
5. Capture authored record facets from the upgraded, authored state.
6. Mark the document `data-lf-upgraded="1"`.
7. Read the first state, reconcile it, and present the page.

`rememberAuthoredMarkup` runs before imports because a clone taken after upgrade
would contain generated controls and the module's once-only stamp. It stores
only widget families with a recordless durable action. `captureAuthoredFacets`
runs after upgrade because record-bearing widgets may arrange the authored state
in `connectedCallback`, but it must run before replay changes that state.

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

The page has three readiness facts:

- `data-lf-upgraded` means widget imports, asynchronous upgrades, geometry, and
  drawings have finished.
- `data-lf-applied` is the event coverage of the last complete semantic
  projection committed to the DOM.
- `data-lf-presented` means the initial authoritative projection, or the
  deliberate offline authored fallback, has crossed the presentation boundary.

Do not merge these stamps. A document can finish upgrading while its first state
read is pending. A projection can commit while finite reconciliation animations
are still settling. Any consumer that reads final boxes waits for upgraded,
applied, presented, and no finite animation reported by `MOVING`.

The authored `main` stays behind the presentation gate until the first state read
has either applied or established that the server is unavailable. Fixed recovery
chrome remains usable while it waits. `showModal()` calls from authored main are
temporarily represented as measurable non-modal dialogs; `presentPage` promotes
only connected, still-open dialogs whose reconciled branch remains visible.
This prevents a modal's top-layer inertness from disabling the recovery chrome.

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
`failSoft` its own element so the rest of the page and Comments remain usable,
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
same semantic coordinate as logged state and commits it on the exact widget and
unit nodes that carry it. `stateProjection` overlays all surviving recorded
outbox actions after logged winners in `outboxOrder`. Until a complete read
accounts for an attempt, its local winner outranks any older log winner on the
same coordinate.

A press whose result has not changed the DOM waits for the log. Recordless
settlements and completion presses do not enter the optimistic overlay. The
control may say `aria-busy` while the request is pending, but it must not paint
the accepted outcome before the server accepts it. A recorded toggle that the
next gesture computes from must paint before the next gesture, so the next
absolute detail includes the state the reader just chose.

`deliver` races the POST against `entry.read`. A poll can account for an attempt
whose POST response was lost, and the accepted POST state can account for it
without another GET. Transport errors, undecodable answers, and incomplete
answers retry the same attempt after `POLL_MS`. A response with `final: true`
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
complete state. It links accepted events to entries, resolves readers waiting on
those events, removes non-action entries whose delivery is complete, and calls
`releaseProjectedOutbox` for actions. Never remove an action merely because a
POST returned 200 or because an attempt appears in an event array that failed
partway through rendering.

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
refusal can change without the reader changing the words: a referenced version
can be published, a parent thread can arrive, or a layer can be re-vendored.
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
2. standing actions and reports in the authoritative log window;
3. surviving optimistic recorded actions in the outbox.

The semantic coordinate is
`JSON.stringify([ownerWidgetId, unitId, facet])`. `x-state` and `x-report`
declare the fold unit, facet, detail schema, and optional record form for every
verb. `unitOf` finds the unit from the declaration. No core consumer branches on
a widget tag or verb to determine state identity.

An `x-state` verb may also declare `requires`, a prerequisite over the standing
request projection `x-awaits` already defines. Its target is the sender or its
declared parent, and it may apply only when an absolute unsigned value would
increase. `actionAvailable` paints and guards the exact gesture, `sendAction`
checks at the common browser door, and POST evaluates the same declaration from
the authoritative log under the append lock. No eligibility cache sits beside
the ordinary ask and state projections. `x-awaits.answers` says which actions
actually close the request; orthogonal actions do not. `x-awaits.rollup` derives
a nested request from direct interventions and child roll-ups, using the same
reducer in the browser and file projection.

`stateProjection(upto)` is the pure derived view. It classifies every action and
report, applies version and retraction windows, drops withdrawn actions and
answered reports, folds the last action for each coordinate, retains report
winners, overlays unresolved local records, and gives a reader action precedence
over a provisional report on the same coordinate. Winners on independent
coordinates compose in event order through `compareProjected`.

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
`desired`. Add a consumer to one of these views instead of building another fold
over raw `events`.

`committedProjection` is not a second state authority. It is a checkpoint of
what node identities and semantic winner the DOM currently represents. Each
entry records the widget node, unit node, and projected entry for one coordinate.
Node identity matters because a rebuild or thread reconciliation may replace a
node without changing an event id. A coordinate with no winner is committed when
its authored baseline stands.

`projectionCommitted` compares the desired coordinate with that checkpoint.
Terminal events count as committed because this version has no applicable state
to paint. `projectionCoverage` converts coordinate commits back to event
coverage for `data-lf-applied`: superseded actions and answered reports are
covered when the coordinate that represents them is committed, and an undo is
covered when its target's coordinate has moved to the prior winner or authored
baseline.

### Reconciliation

`receiveState` is the only door for a complete server state, whether it came
from polling or an accepted POST. It:

1. verifies the layer generation;
2. rejects an event sequence older than `lastEventSeq`;
3. loads the Markdown renderer before any message body needs it;
4. installs candidate `events` and renders all log-derived surfaces;
5. calls `reconcileState` after thread widgets exist;
6. advances `lastEventSeq` only after the whole state renders;
7. accounts for outbox attempts;
8. dispatches `lf-actions` after replay.

If any required render throws, `receiveState` restores the prior event list,
phase, and sequence. A candidate history may be visible only during its own
synchronous application. Focus, undo, draft settlement, and later asynchronous
wakeups must not consume a log tail the page did not adopt.

`reconcileKnownState` protects those wakeups. It permits reconciliation only
from the last complete sequence, or from the authored-only initial state before
any events have been installed. Poll failure is allowed to retry a deferred
correction against that known state. It must not project a newer candidate whose
surrounding render failed.

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
`lf-actions`. Do not let polling fight the pointer by applying projection during
a drag.

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

Threads also read the whole log. `retractionFloors(Infinity)` keeps a
conversation current on a pinned page even when the document projection remains
historical. Registry-declared `x-conversation` seats show an exact-section
textual view while the owner exists in the current document; the Comments panel
keeps the complete thread and its interactive replies. Dropping the owner drops
only the inline seat.

`restated` and answered-report relations persist through version notes. The note
records the version floor for each affected id or report event; silence in a
later version does not revive retracted state. `retractedIds` uses containment,
not a global id lookup, when deciding which detailed parts an action rests on.

### Event sequences for modules

Projection answers where state stands. Some modules also need to narrate how the
state arrived or when it was last reported. They read that through the exported
sequence helpers, not through raw `events`.

`actionSequence(widget, action)` returns copies of the widget's matching
absolute action events in log order and within its applicable version window.
It includes only events for which `projectionCommitted` is true. A module must
not narrate an action whose `applyAction` is deferred while the body still shows
another value.

`reportSequence(widget, verb)` returns report events in log order without
dropping reports a version has answered. A module showing freshness asks when
the log last heard from a worker, which remains useful after publishing absorbs
that report into authored state. The semantic projection still excludes answered
reports from current desired state.

`sequence` is the shared traversal for both channels. It applies widget,
optional verb, kind, version window, and liveness in one place, then returns
structured clones so modules cannot mutate the private event list.
`watchActions` and `watchReports` subscribe those readings to `lf-actions` and
invoke the callback immediately. The same rendering function therefore handles
a module connected before the first state and one constructed by a later thread
reconcile.

`lf-actions` fires after a complete state has reconciled, including a poll whose
event list did not grow. This lets a module refresh elapsed time and retry a
render deferred by live input without owning a timer or a second event cursor.
Callbacks must render from the sequence they receive and return their cleanup
function from `watchActions` or `watchReports` when their element disconnects.

`publishedAt` is the timestamp of the note that published `currentVersion`. It is the
freshness floor for authored state when no report exists. A page that reports no
worker update is not timeless; its authored assertion is as old as its version.

`actionStands` answers whether one accepted action is still the reader's winner
for its semantic coordinate. It treats a newly accepted event as standing when
the tab has not yet installed an event list containing its id, then asks
`stateProjection` once authoritative history contains it. Modules use this
after a send whose visible choreography depends on whether the accepted action
survived later events.

## The widget vocabulary stays open

`registry.json` is the layer contract shared by rendering, validation, catalog,
event parsing, replay, and export. Core code may name a widget only when the
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
| `x-says` | named attributes are visible words at declared edges |
| `x-paints` | named attributes communicate facts through paint and need a quiet spoken reading |
| `x-verbatim` | authored data must agree with the rendered words |
| `x-shadow` | a declared open shadow tree is part of the page's composed reading |
| `x-state` | reader action verbs, current eligibility, facets, units, schemas, and records |
| `x-report` | report verbs with the same semantic state shape |
| `x-parent` | the child widgets whose decisions belong to this holder |
| `x-retired-when` | outcome-to-slot retirement relations |
| `x-withdrawn-as` | the author's state for a withdrawn recordless decision |
| `x-awaits` | the condition, explicit answer verbs, and optional nested roll-up for a request |
| `x-conversation` | the condition under which the widget owns a conversation seat |
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
- `rowPresence` and the ask tray read `x-awaits` rather than a tag selector.
- `standingState` exposes replay winners to the render gate without naming a
  widget.

A module owns only its choreography and semantics that no declaration can
express. For example, a suggestion module may animate its slots and write the
visible deletion and insertion words. It does not own the general meaning of a
settled holder.

The stylesheet uses declarations as open selectors too. A box that draws a
frame declares `--lf-frame: 1` in the rule that draws it. Style queries use that
custom property to trim child margins and to bound wide content. A project box
then receives the same behavior without joining a tag list. `main` hands wide
room back to its contents explicitly because it is the outer page frame.

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

A behavior module imports only the public helper surface from `leaf.js`. Do not
reach into runtime globals, query private chrome, or duplicate a runtime helper
inside a module. The scaffold names the minimum obligations:

- Define the custom element once and make `connectedCallback` safe to run after
  reconstruction.
- Use `once(el, fn)` for generated chrome so reconnecting does not duplicate it.
- Implement `applyAction(action, detail)` as an absolute statement and return
  `false` only while a live gesture makes application unsafe.
- Call `sendAction` for recorded user state. The detail must match the declared
  browser schema.
- For a verb with `requires`, use `actionAvailable(el, verb, detail)` for both its
  visible control state and its gesture guard. `sendAction` and POST repeat that
  declared check at their respective doors.
- Read authored or user-facing words with `says`, never raw `textContent`.
- Build injected controls with `offer`. Use `relabel` when a control's label is
  also one of the page's words.
- Register keys with `keys(el, title, rows)` during upgrade, not at module load.
- Call `quoted(el)` before wiring module-specific gestures. `sendAction` also
  refuses actions on an exhibited widget at the layer door.
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

Keep them as named readings. A boolean passed to one ambiguous reader makes
callers choose semantics at each call site.

`GENERATED` is `.lf-ui, [data-lf-gen]`. It marks words that are not authored.
`data-lf-said` is nearer than `.lf-ui` and declares that a label inside
chrome-looking structure is still one of the page's words. This lets a tab label
or draft heading remain quotable while runtime controls stay outside the
passage. `relabel` writes the said marker; `offer` writes the control marker.
They are independent facts and neither clears the other.

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

`COVERED_WORDS` is the render gate for text that is present in a browser reading
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
the visible words promised by that widget's entry. `SILENT_WORDS` examines open
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
`itemSays` labels a compact view from an item's own opening words. An ask that
needs a useful row label states it on itself, commonly through an `x-says`
attribute; the row does not infer a heading from surrounding layout.

`paintAnchors` is the only anchor writer. One pass decides thread marks,
element outlines, and the open composer's pending mark. It clears and paints
through the same composed-tree helpers, then records exactly what it drew in
`marked`, `pendingMarks`, and `pendingOutline`. Other features consult those
records rather than looking for arbitrary DOM paint.

The same pass answers a second question and records it apart. `placed` is where
each thread's passage lands in this version; `marked` is what was drawn for it.
They differ for a resolved thread, which has a place and no paint, and for an
element anchor, whose paint is the boxes its contents show through rather than
the element the anchor named. The panel's order reads `placed`, so the list and
the page cannot disagree about which of two threads comes first, and one walk of
the document's text answers both. `renderPanel` therefore paints before it
renders the list. Do not resolve a thread's anchor a second time to sort it.

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
Use:

- `shownBox` for travel, bounds, and reading-position landmarks;
- `shownParts` for ask rings and element-anchor outlines;
- `shownRect` for visible placement of floating chrome and address chips.

Do not read `getBoundingClientRect()` directly when the target may generate no
box. A `display: contents` element reports an origin-like zero rectangle that
does not represent where its contents are. `UNMARKABLE_ITEMS` detects declared
items with no visible part on which a mark can land.

`inUi` keeps runtime chrome out of shown parts. An area greater than zero is not
enough: clipped note text and hoisted controls can have measurable boxes while
remaining the wrong semantic target.

A control containing a page word is built by `offer` as a selectable
`span[role="button"]`. The shared listener supplies Enter and Space semantics.
`offer` distinguishes a click from the mouseup ending an active text selection
by comparing the selection's focus end with the release. It does not suppress a
press merely because an older selection contains the control or because the
pointer landed beside selected text.

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

`syncLayout` derives floating placement and reservations from current boxes.
`layoutSizes` observes the body and chrome elements that affect those results.
Its callbacks write only chrome. Window changes need no parallel resize
listener when body observation already represents them.

The document scrolls `body`, not the viewport. `pageScroller` is the shared
answer for reading position, paging, and libraries. A library that guesses
`document.scrollingElement` must be given `pageScroller` explicitly. The open
comment panel and tray panel each occupy their own strip when the viewport can
hold it and cover the page under their respective media query otherwise.
`stateStrip` and `stateRoom` are the geometry readings, and both count every
strip the chrome holds; CSS owns the body's corresponding layout.

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
tray list reserves the key line's room. `stateRoom` compares whole-pixel
readings — the measured box against the window less every strip — rather than
subtracting a transitioning margin from an integer box. Mixing the two flickers
`--lf-room` by a pixel per frame, and each flip relayouts the page from inside
the observation that asked for it.

The banner and key line reserve their space in normal flow. A fixed or absolute
chrome surface may lie above that reservation, but the reservation itself
travels to print and export only when that medium contains the surface it
serves.

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
as the status indicator, does not. `MOVING` is the render gate's shared reading
of that boundary. A component that animates forever must not appear in it; a
state transition that can still change boxes must.

The movement tests ask both paths that can shift a target:

- press a control and compare the rest of its line;
- let a poll introduce news and compare all persistent chrome controls.

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

`markDeclared` exposes this declaration and `stateRoom` computes room after chrome
strips and claimed margins. A drawing inside a framed box uses that box's room,
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

`TRAPPED_MARGINS` reads computed layout in the browser and reports a framed box
whose visible inset exceeds what its own padding states. Flex and grid item
margins are placements rather than collapsed block margins and are excluded.

Overflow is acceptable only when the reader can reach it or the box explicitly
signals the cut. A scroll container may expose content in its scroll direction.
`text-overflow` may signal omitted text. Plain clipping does not make content
reachable. `MISPLACED_BOXES`, `CLIPPED_CONTROLS`, and `COVERED_WORDS` enforce
the distinct geometry, interaction, and text consequences.

`TINY_BOXES` ensures each declared widget upgrades to a usable box.
`UNREACHABLE_WORDS` catches rendered words outside reachable flow.
`MISPLACED_BOXES` asks each container's actual overflow behavior. Do not exempt
a box merely because an ancestor declares `overflow`.

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

A group joined into one control has cells, and its children arrive from every
layer: the options are the author's, the box for words is the module's, the
question and the Done press are the runtime's. Each brings the spacing it wears
standing alone, and the grid stretches all of them to the same column whatever
they were written as.

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

## Keyboard, focus, and navigation

One register defines every runtime and widget key. A row binds keys, states what
the press does, decides when it is live, and runs it. A scope says where a group
of rows applies and which platform keys that context claims. The dispatcher,
key line, `?` reference, control tooltips, and announcements are projections of
those objects.

The register owns capabilities, not controls. Every capability the chrome offers
has a row, and each control that reaches one names its key through `also`; a
control is a route to a capability rather than a capability of its own, so a
second route needs no second row. A run heading in the comment panel presses the
page to where that run is about, which is what `g c` already reaches through any
thread in the run — where `w` and `/` are capabilities nothing else reaches, and
each earns a row. A capability with no row is one the key line never advertises,
the reference never lists, and a reader working from the keyboard never finds,
because those three are projections of the register. Add the row in the change
that adds the capability.

The letter comes from a word the surface says. `l` opens the leaves, `a` the
asks, `w` the comments waiting on the reader — each spelling what the reader can
read off the control it presses. Where the letter a control's word wants is
already taken, change the word or take a different capability's: a key spelling
something nothing on screen says is a key nobody reaches for twice.

A row whose press turns a mode on and off states the mode rather than the toggle.
`does` and `line` are functions of whether it stands, so the sentence says which
way this press will go, and Escape takes the mode off through the rung ladder
rather than through a second binding of its own.

Which scope a row belongs to follows from what its press acts on. The page holds
the presses whose subject is the page: `c` comments on it, `a` and `l` open what
is about it. A surface holds the presses whose subject is that surface's own
contents, because contents the reader is not looking at are not a thing to act
on: `w` narrows the comment panel's list and `/` searches it, and both live in
`PANEL`. The page's alphabet is small and every letter spent there is spent on
every page, so a letter earns page scope only by acting on the page.

Standing in a surface is where focus is, not merely that the surface is open. A
tray's or panel's own button lives in the banner, so opening by pointer leaves
the reader outside it, and a key, a Tab or a click on its contents is what puts
them in. Inside a text box the letter is a character — the typing scope claims
what types one — so a reader reaches a surface's letters from its list rather
than from its composer.

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
- `run` performs one result. A run-less row documents a native control whose
  platform behavior must remain untouched.

`live` answers the declared liveness once for every projection. Do not repeat a
guard inside `run` if the guard changes whether the key should be shown. When
the reference needs to describe a page capability while the key line needs to
promise an immediate press, keep `pageHas` and `readerIn` separate.

`checked` validates declarations when they enter the register. `parsed` and
`answers` share the supported modifiers `Mod`, `Alt`, and `Shift`. Unknown
modifier names are errors rather than bindings that accidentally fire on a bare
key. `spell` is the one platform-aware display of a binding. `PRESS` states the
native key behavior of controls; links retain their platform distinction from
buttons.

A label names this press, not the broad feature. Prefer "Comment on selection"
or "Hide comments" to "Comment" or "Toggle". Compute the word through `word`
when visible state chooses the sentence. Repaint through `paintHere` when any
fact used by a word or liveness predicate changes.

### Scope and dispatch

Scopes nest by focus. `scopesFor` produces the active stack and element scopes
are spliced where their elements stand. The dispatcher walks innermost first.
The first live row answering the event runs, prevents the platform default when
it owns the press, and stops. A focused widget may shadow a page key without
either scope naming the other.

`claims` lists platform keys a scope consumes even when no registered row
answers them. A text entry scope uses `takesLetters` and claims only keys that
would type into that specific control. It does not blanket radio, checkbox,
slider, Enter, Escape, or a send chord merely because they are form-related.

One box inside another scope states only what it does differently. `FINDING`
stands before `TYPING` in `SCOPES`, so the find box keeps every text-box key and
shadows the one it answers for itself: Escape lets the narrowing go, and the box
on the press after that. One press is one rung there as everywhere else.

A true mode may own the keyboard. An armed address chord and the open reference
claim the relevant keys through their scope. A longer-lived menu keeps the
reference available through `allButTheReference`. Closing an overlay restores
focus to `helpFrom` so the reader returns to the control that opened it.

Escape is an ordinary binding in the register. The innermost scope that binds it
owns one unwind step. A control-specific Escape, panel dismissal, ask release,
and return to the page cannot cascade from one keypress. A scope does not need a
private `keydown` listener or hand-written `preventDefault` to protect that
contract.

`offer` supplies the two press keys for injected span controls at the shared
bubble listener. A widget that already handled the event can prevent its default
before that listener. Native controls stay native and their run-less rows only
project the platform press into help.

### Standing somewhere

Focus is the reader's current place. `focused` follows it through declared
shadow roots. `markHere` paints one `--here-ring` around the semantic ask or
control that contains focus. The ring is derived on each paint; it does not
store the ask walk's position.

`landed` stores where the ask walk last arrived. This is distinct from focus:
the banner's Asks button retains focus while the walk moves through the page.
Clicking elsewhere removes the focus-derived ring without erasing the walk's
useful continuation point.

`shownParts` supplies ring targets when a page styles an ask with
`display: contents`. A normal boxed ask wears one outline on its own box.
Hoisted controls use the same ring token through the shared pill rule.

`rung` and `letGo` put focus on `body` when the reader leaves chrome or releases
an ask. `body` has a tab stop because a short page may not become focusable from
overflow alone. Focus rather than blur hands Space, PageDown, arrows, Home, and
End back to the page's actual scroll box. `letGo` also runs synchronously during
module evaluation so a fresh page accepts native scrolling before asynchronous
upgrade, without stealing focus from a control the reader reaches during that
upgrade.

### The key line and reference

The key line shows what keys do at the reader's current scope. It walks outward,
drops duplicate bindings shadowed by an inner scope, and yields lower-priority
page rows when width runs out. The `?` entry remains available. The line is
`aria-hidden` because placeholders, live announcements, and the full reference
carry the same facts for assistive technology.

The reference lists every live capability the page has, grouped by scope.
Computed ranges count current members. A declaration must survive `merge` with
its `when`, `at`, `claims`, and rows intact so the reference does not advertise
a scope the current page cannot enter.

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
as soon as the poll announces the version, but `midComposition` or an open version
menu defers activation and leaves the newest-version chip visible. Ending the
composition releases the version on the ordinary next poll; pressing the chip is
an explicit override and still keeps the live address. `goVersion` is the one door
for both that in-place newest-version request and travel to an older immutable
version.

An older version is historical rather than live: choosing one navigates to its
immutable file with `?pin`, and it stays at `currentVersion` while offering the
newest-version chip. The view record carries reading position and the ask-walk
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
can populate state-dependent rows. It restores intent through `showTray` without
replaying opening motion. `ARRANGEMENTS` supplies one render arrangement for
each persisted tray.

Ask rows come from `x-awaits`, not from a list of ask tags. `itemSays` supplies
each row's own label. Selecting a row travels through the same ask-arrival
function as `n` and `p`, so numbered and directional navigation agree about
focus, reveal, scroll, and `landed`.

An ask is answered only through a verb listed in `x-awaits.answers`; do not infer
that every state change is an answer. A `rollup` instance evaluates its own `when`,
then matching direct non-rollup interventions, then child
roll-ups, and finally itself as a leaf. The visible list keeps the deepest open
member, while `actionAvailable` may query an ancestor's exact value.

### Address chord

`g` opens one address mode. A second letter names a list, and a digit names a
member. `g g` and `g G` complete the chord themselves, gliding to the top and
bottom of the visible scroller: an edge is one place, so the second key is the
whole address, and because every page has a top the mode never arms empty and
the page-level `g` row needs no capability gate. `ADDRESSES` is the whole list
vocabulary. Each entry declares:

- its letter and user-facing name;
- the sentence shown in help;
- its members in stable address order;
- the box a chip is placed from, where that is not the member itself;
- how to show a list that draws nothing until asked;
- how to arrive at one member.

A list's capability is not declared: it is whether the list is non-empty, read
where the row asks. Consumers do not branch on which address list is active.
Adding a list adds one entry. The page-level `g` row promises only the mode;
ranges belong to the list rows inside it.

Arming the mode paints the whole offer: every list contributes chips at once, and
a letter narrows them to its own list. A chip carries the letter and the digit,
and keeps both after the letter is pressed, because it states which member this
is rather than how much of the address is left to type. `addressKeys` is the one
spelling of that pair; the key line's ranges and the placeholder that speaks a
reply box's whole address both build on it.

Addresses are stable within the document. The first addressable members do not
change identity as the reader scrolls. Chips are painted only for members whose
`shownRect` is visible, but an off-screen member remains reachable by the same
address. A list drawn nowhere the reader can see, such as the comments behind a
shut panel, therefore contributes no chip until its letter reveals it. Chips live
in runtime chrome rather than authored markup.

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
walk's origin. `askStep` compares document positions rather than incrementing an
index remembered by the walk. A panel thread walk may use log order because the
list itself is its complete ordered space.

`captureView` stores a passage-based reading landmark, correction within the
block, and the last ask landmark. `restoreView` resolves the landmark after
upgrade and corrects the scroll from the rendered box. A URL fragment outranks
the saved view on a fresh navigation; the saved view outranks a leftover
fragment on reload or back navigation. `landArrival` applies that ranking only
after final page geometry is available.

Focus and selection are not restored across documents. Restoring focus onto a
control would change the next Space from page scroll to activation, and a
selection may refer to words the new version replaced. The saved ask landmark
preserves directional continuity without claiming the reader still stands
there.

## Chrome, conversations, and text input

`.lf-chrome` is one fixed runtime root containing the banner, the tray panel,
comment panel, composer, floating comment control, toast, live region, key line,
help, inspection paint, legend, and address layer. The page and panel are
separate scroll regions. Opening or closing one calls its state setter, updates
the persisted intent, and schedules the shared layout and key paint.

The thread list reconciles nodes rather than rebuilding them. `setChildren`
preserves existing message, reply, and textarea nodes when the same event still
stands. Polling must not discard a reader's caret, focus, reply text, disclosure
state, or scroll anchor. The browser's scroll anchoring keeps the visible thread
steady when a message is inserted above it; tests pin the thread's box rather
than a particular scroll offset.

### The order the list reads in

The list is the page's order, not the log's. `inPageOrder` sorts by where the
anchor pass placed each thread and breaks ties by log order, so the panel, the
marks down the page, the j/k walk and the `g c` digits are one order. A thread
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

### Narrowing the list

Two narrowings compose: the words the reader is looking for (`finding`, over each
thread's messages, its anchor label, and the part of the page it is on) and
whether the agent spoke last (`needsYou`, through `awaitsReader`). Both are the
panel's own view. The page's marks, the inline conversation seats and the
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
A reveal that widened for a reply would take the reader's narrowing away for
having been used, which is how the waiting-on-you list is emptied.

Messages render from Markdown after escaping raw HTML. Literal text such as a
generic type remains text and cannot inject markup. Interactive event `markup`
has a different door: only the CLI can write it after validating against the
vendored registry, while the browser event schema refuses it. A widget in that
markup is instantiated once in the panel; inline conversation seats show a
textual projection rather than copying interactive ids.

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

Put a layout grant in a selector strong enough to override the withheld base
rule. Put a standalone-only affordance guard in
`:where(html:not(.lf-copy))` so the guard does not add specificity to every rule
inside it.

Print asks a stricter question than export because nothing on paper is
interactive. `data-lf-offer` identifies injected controls to remove, while
`data-lf-said` preserves a decision word the page speaks through a control.
`PAPER_WORDS` compares the screen and print readings across the whole page.
`COVERED_WORDS` runs again in print. A wrong offer/said declaration is fixed
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

The JavaScript readings embedded in `interact.py` each answer one failure class:

| Reading | Contract |
| --- | --- |
| `WINDOW_ERRORS` | no runtime, module, resource, or ResizeObserver error reached the page |
| `UPGRADED` and `MOVING` | upgrade completed and final geometry settled |
| `TINY_BOXES` | every declared widget has a usable rendered box |
| `UNMARKABLE_ITEMS` | every pointable item has a visible part for an outline |
| `MISPLACED_BOXES` | boxes stay in the column or in genuinely reachable overflow |
| `CLIPPED_CONTROLS` | actionable controls are visible and reachable |
| `UNREACHABLE_WORDS` | visible page words remain in reachable flow |
| `COVERED_WORDS` | browser words are not silently clipped, hidden, or claimed by chrome |
| `UNREAD_SYNTAX` | syntax highlighting does not erase or alter source words |
| `SILENT_WORDS` | `x-says` and `x-paints` promises reach the composed rendered page |
| `UNDECLARED_ATTRS` | modules do not write undeclared author-namespace state |
| `RETIRED_SLOTS` | declared settlement marks and retired-slot visibility agree with the projection |
| `TRAPPED_MARGINS` | framed boxes show only their declared inset |
| `PAPER_WORDS` | print keeps every page statement and removes only affordance |
| `REPLAY_OVERRIDES` | the log, not conflicting authored markup, determines projected state |
| `RELATIVE_REPLAYS` | reapplying each standing absolute winner moves nothing |

`standingState` and `shallowSigs` are exported for these gates. Keep their
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
poll, reload, second tab, storage fault, shadow root, print medium, or animation
can expose the behavior.

## Working on the runtime

Run `node --check plugins/leaf/skills/leaf/assets/leaf.js`, formatting, and a
focused real-browser test while iterating. Before handing over a runtime or theme
change, run the relevant full browser file or `leaf version check --render` on
the affected example. `node --check` cannot validate browser bindings, runtime
CSS inside the module's template literal, computed layout, or reconciliation.

Re-vendor a page before trusting its browser result. A page directory carries
the runtime, registry, modules, vendor files, and theme copied by `page init`; a
page not re-vendored is testing an older layer.
