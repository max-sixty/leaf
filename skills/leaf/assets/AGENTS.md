# The page in the browser

This file owns browser-wide contracts: module boundaries, startup, state authority,
layout, and validation. Read each module's header for its local contract.
Page-authoring rules live in `../references/page-authoring.md`; package contracts live
in `../references/packages.md`. Repository `AGENTS.md`, "Cross-runtime invariants", owns
rules shared by Python and JavaScript.

Keep each rule with the modules it constrains: local contracts in module headers,
browser-wide contracts here, and cross-runtime contracts in repository instructions.
Describe current behavior, without retaining implementation history.

## Runtime ownership

`leaf.js` is the boot-only browser entry module: every owner is a module that exports
its capability and imports what it needs, and `leaf.js` imports them and runs the boot
sequence (Startup and presentation, below). It exports no capability and no owner
imports it back. The HTTP boundary places the vendored
`runtime/bootstrap.js` before loadable resources, carrying the delivery's CSP nonce; it can
show startup failure and hear a replacement server even if the module graph or
stylesheet never loads. A delivery carrying a site release also uses that bootstrap
to send one content-free startup profile after presentation, failure, timeout, or
navigation away; ordinary Leaf servers carry no release and emit no telemetry.
`runtime/widget-api.js` is the one public
helper surface for behavior modules and reexports capabilities directly from their
runtime owners; an owner never reaches back through the entry module or public facade.

The boot module constructs owners with explicit capabilities before mounting them.
These constructors retain their dependencies; their mounts install listeners and begin
reads that need the other owners. Pure projection, thread, and pending models fold
supplied records without importing DOM or application services. Renderers receive the semantic commands they use instead of importing the
application, delivery, or undo owner. Keep these boundaries transitive: an intermediate
helper must not restore a forbidden dependency. The public widget facade is the boundary
for authored behavior modules, not an internal shortcut between runtime owners.
The keyboard register stores declarations without evaluating their dynamic readings;
the first repaint after mounting evaluates them.
`.dependency-cruiser.mjs` declares the runtime's boundaries for the lint gate, which rejects
cycles, forbidden transitive dependencies, and a declaration naming a module that no
longer exists. Runtime imports use literal paths so the gate can read their edges. Only the authored interaction loader and registry widget loader use
computed imports; those load content modules rather than runtime owners.

The map names entry points for each concern. Their headers own module-local contracts;
subdirectories keep related models, controllers, and views together. Paths below are
relative to `runtime/` unless stated otherwise.

| Concern | Owners |
| --- | --- |
| Composition and semantic publication | `application.js`, `semantic-state.js`, `context.js` |
| Delivery, accepted state, and wakeups | `delivery.js`, `state-application.js`, `state-feed.js`, `layer-client.js`, `traffic.js` |
| State models, selectors, and projection | `projection/`, `thread/model.js`, `thread/workflow.js`, `thread/state.js`, `pending/`, `asks/model.js` |
| Widget capture and lifecycle | `document-identity.js`, `widget-descriptors.js`, `widget-controller.js`, `widget-loader.js`, `widget-upgrade.js` |
| Vocabulary and public helpers | `registry.js`, `widget-api.js`, `widget-elements.js`, `request-elements.js` |
| External data and authored projections | `data.js`, `projection/data.js`, `projection/authored.js` |
| Revision installs and continuity | `version.js`, `version-chooser.js`, `carry.js`, `dom-children.js`, `root-state.js`, `restore-state.js` |
| Shared repaint and geometry | `rendering.js`, `repaint.js`, `standing.js`, `page-geometry.js`, `geometry.js`, `rect.js`, `pointer.js` |
| Chrome assembly and available room | `chrome.js`, `chrome-layout.js`, `auxiliary-surfaces.js`, `drawn-edge.js` |
| Reading regions and scrolling | `reading-regions.js`, `reading-place.js`, `bounds.js`, `scrolling.js`, `reach.js`, `user-place.js` |
| Keyboard commands and their projections | `keyboard/AGENTS.md` |
| Focus and navigation | `focus.js`, `navigation.js`, `history.js`, `user-intent.js`, `walk-position.js` |
| Asks | `asks/view.js`, `asks/view-elements.js`, `asks/model.js` |
| Comment capture and entry | `composing/`, `drafts.js`, `media.js` |
| Threads and reply surfaces | `thread/`, `thread-panel.js` |
| Margin inventory, controls, and Page Map | `margin-entries.js`, `margin-entry-model.js`, `margin-model.js`, `margin-map-model.js`, `margin-projection.js`, `margin-cluster-view.js`, `page-map-dialog.js` |
| Margin placement | `margin-layout.js`, `margin-placement.js`, `thread-card-geometry.js` |
| Passage reading and target identity | `passages.js`, `text-alignment.js`, `anchor-coordinate.js`, `target-references.js`, `resolved-target.js`, `anchor-resolution.js` |
| Anchor paint, controls, and travel | `anchor-paint.js`, `anchor-note-view.js`, `anchor-controls.js`, `anchor-travel.js`, `target-paint.js`, `visual-parts.js`, `indication.js` |
| Banner, approvals, and the row, menu, and gesture control seats | `banner.js`, `banner-status-view.js`, `banner-approval.js`, `banner-shelf.js` |
| Trays and neighboring pages | `trays.js`, `live-leaves.js`, `live-leaves-list.js` |
| Activity timing and updates | `presence.js`, `updates.js` |
| Browser interaction diagnostics | `interaction-log.js` |
| Notices and announcements | `semantic-news.js`, `notifications.js`, `keyboard/shortcut-bar.js` |
| Reactions and design review | `reactions.js`, `design.js`, `design-readings.js` |
| Document presentation and validation | `presentation.js`, `validation.js`, `projection-watch.js` |
| Child pages and gallery playback | `specimen.js`, `interaction-gallery.js`, `interaction-gallery-frame.js` |
| Shadow trees and styles | `shadow.js`, `shadow-stage.js`, `stylesheets.js` |
| Rendering utilities | `icons.js`, `markdown.js`, `syntax.js`, `motion.js`, `storage.js` |

`leaf.js` assembles chrome and mounts the shared repaint phases in order: keyboard-scope
reflection, standing content, chrome layout, requested page movement, and standing
geometry. Work requested during a phase runs after the phases, before the same frame
paints: `runtime/rendering.js` runs every rendering callback in one pass per frame, and
a step that must wait for the following frame, such as an animation tick, asks for
`nextFrame`. Synchronous input
layout, ResizeObserver height-only placement, and shell animation frames keep their own
timing contracts.

The stylesheet boundary follows where rules apply:

- `theme.css` holds page tokens, element styles, idioms, and CSS-only widgets. Each
  package theme follows it. Shared shadow rules are composed into `/shadow.css` and into
  `/theme.css` before the corresponding root's theme.
- `runtime/chrome.css` is adopted after page and package sheets. Shared control faces
  belong in page-side sheets; chrome rules must win by their selectors when moved ahead
  of those sheets. Its paint hosts stay outside the containing-block chain, with
  page-attached paint below covering auxiliary surfaces and chrome-target paint above.
- `runtime/marks.css` is adopted by both the document and shadow stages.
- `stylesheets.js` reads delivered `delivery_sheets` synchronously. CSS module scripts
  are unavailable in WebKit, and a module-scope await would delay page modules past
  `DOMContentLoaded`.

A selector whose `:has()` stands before its last combinator is restyled from the
document root. Chrome keeps one invalidation set for every such selector, keyed on
their rightmost compounds, and a trace of a drag-select shows it scheduling that set on
`html` for ordinary runtime writes (an `aria-pressed`, a `hidden`, a placeholder, a Lit
render), none of which touch the rules' own subjects. Each rightmost compound therefore
selects its targets across the whole document. A
compound with no class, id, attribute, or type in it (`> :not(.x)`, `> *`) makes
every such change restyle every element. On a 21,000-element page that cost 40 ms a
frame for as long as a drag-select lasted. A type costs one restyle for each element
of that type, so key a repeated element such as `details` or `li` by a class its
owner writes. `test_no_has_rule_restyles_the_whole_document` enforces the first
rule; the second is a judgment about how often the type repeats.

The shared `.lf-ui` face starts in the assets root's `shadow.css`, before component
rules. Its `:where(:root) .lf-ui` selector has class specificity and does not match inside
shadow trees, where the host's control face applies.

The auxiliary surfaces — the Asks tray, the thread panel, and the Leaves tray — stand over
the page and never change its geometry, so the page the author laid out is the page the
user reads with a surface up. The Asks tray and the thread panel leave the page live
beside them, and cover it (inert, behind the scrim) where they would leave less than a
usable page; `--lf-auxiliary-beside` states that rule once for both, and the runtime
reads it (`standsBeside`) rather than asking the viewport. The Leaves tray always covers
the page. `chrome-layout.js` must not override the user's position.
A workspace's posture is the stylesheet's: one container query on the workspace's own
box decides whether each pane's body scrolls, and the runtime reads which box scrolls
a region from that result rather than choosing it (`reading-regions.js`).

The widget layer loads the vendored
registry, imports modules declared by `x-upgrade`, renders registry-declared
words, and has each module's controller reconcile recorded state. The comment layer listens on `GET /api/news`
for the page's reading, reads `GET /api/state` when that reading moves,
posts to `POST /api/event`, renders the status and thread chrome, captures
anchors, and handles keyboard navigation. Both layers share the same registry,
passage model, event list, layout readings, and helper surface.

Each mutable fact has one writer:

| Fact | Authority | Browser writer |
| --- | --- | --- |
| authored widget state | validated source markup before widget upgrade | `stageAuthoredStates` decodes typed initial values; the application admits them atomically with descriptors, revision identity, and a matching server reading |
| external data | the page data reading taken latest | `receiveState` replaces the source values; `watchData` delivers each bound source's value to widget modules |
| projected data | an external snapshot or other records the widget is currently given | `projectData` reconciles their keyed rendering; the DOM does not become another record store |
| version shown by the live document | the immutable revision named by its delivery prelude | a newer active revision whose executable identity is this document's is patched onto the authored page in place; one whose differs navigates the stable live address into a fresh document; a public version address derives the version number from its URL |
| accepted history | the server event log | the application publisher adopts one complete server answer |
| the reading the page has applied | the server's `/api/state` answer | the publisher adopts `reading`; state presentation paints `data-lf-reading` only after every required view succeeds |
| unresolved browser work | the publisher's one ordered ledger | commands enqueue; accepted state accounts receipts; projection commit proof permits action release |
| desired semantic state | authored state, log projection, then pending overlay | the application publisher exposes one folded reading, which may precede deferred DOM work |
| rendered thread | the server's thread projection, then pending messages | the publisher exposes one effective thread; thread presentation adapts it to retained DOM nodes |
| message workflow and thread attention | the server's exact-input `workflows` and each Thread's aggregated `attention` | the publisher adds local Sending and the attention local sends imply; message metadata, compact rows, and margin entries share `thread/workflow.js`'s labels |
| which Asks stand and which the user owes | the server's one `leaf.asks` fold, shipped as the view's `document.asks` and the thread's `asks` | the publisher concatenates the page and thread readings and publishes them unchanged (Authoritative projection, below) |
| proof of what the DOM currently represents | controller presentation tickets plus projection coordinate commits | each controller completes total rendering and auxiliary updates through `updateComplete`; projection commits gate coverage, provenance, chrome, and pending release |
| when a document-wide renderer paints | the publication that opened the epoch | each presenter claims its region in the publication and paints on the next pass, in the order `runtime/semantic-state.js` declares (root `AGENTS.md`, Cross-runtime invariants) |
| anchor paint | thread and composer anchor records | the anchor paint owner |
| where each thread's passage lands | this version's resolution of its anchor | anchor paint writes a rich placed record with its element, exact datum, and exact/fallback/outdated status |
| widget-local Thread placement | exact projected-datum placements plus the widget's current layout | the thread surface coordinator asks each declared adapter for an outlet, then records the threads it claimed before the margin projection reconciles |
| canonical page activity | the server `activity` fold (root `AGENTS.md`, Cross-runtime invariants) | the banner and Leaves tray paint it; the browser only asks for a fresh server reading at `next_transition_at` |
| which agent content the user has not read | the server's `read_state` reading, shipped as each Thread's `unread` | the publisher removes the versions this tab is marking read; `thread/read.js` sends `read` for exposed prose and Mark read, outside the gesture queue |
| meaningful new page information | unread agent content, user Asks, canonical response workflows, request receipts, and page activity in the accepted server reading | `semantic-news.js` compares only readings whose complete document presentation succeeded: unread content is news the first time this tab sees it, and everything else is news only against an earlier reading. `notifications.js` owns the one status-line and live-region queue, and rechecks deferred assertions against the latest successfully presented reading before display |
| composer visibility | `composerOpen` and `fabAnchor` | `showComposer` and `showFab` |
| the draft a hidden composer can be brought back to | the stored composer records, narrowed to those whose passage this document still holds | `keptDraft`, read by the `g D` destination and by the notice `showComposer` writes when a box holding words goes down |
| auxiliary-surface selection | the auxiliary-surface owner's one registered key | `select` closes the previous surface before opening the next; `restore` reselects the remembered one and `present` completes state-dependent arrival |
| the narrowing and order of the thread list | the user's find words, lifecycle, scope, subject, and detached-placement facets, and Page or Recent order | `renarrow`, `revealThread`, and `widen`; neither of the last two changes the order |
| how much of a scroller's top a sticky cover takes | the tallest declared cover's rendered box | `declareCoverRoom` (`geometry.js`) observes the covers and writes the property a `scroll-padding` or `scroll-margin` reads: the thread list's run headings as `--lf-head-room` on the list (`renderThreads`), each `lf-diff` file header on its file, a root `lf-tabs` strip as `--lf-root-tab-clear` on the document |
| a nested scroller's viewport position through a re-render | one reference node in the scroller's visible band, handed across to whatever the render puts under its identity | `user-place.js`'s place hold, taken by whatever re-renders the scroller: the thread list's `renderThreads` (generated presentation, receipt updates, provisional work, resolution folds) and `holdThroughDisclosure`, the Page Map's `renderSheet`, and the margin card's `buildThreadCard` for the same thread; a package takes it through the widget API. The document's scroller takes none: native anchoring holds it |
| where the thread holding the focus stands in the list | the band the list declares landable through `scroll-padding` | `threadsBox`'s `focusin`, and its press through `pointerdown`/`pointerup`; `stepThread` for a key press that moves no focus, `landIn` for the box it puts the user in, `placeThreadEdge` for an explicit edge placement, and `showThread` for a deliberate arrival. A press's correction is instant, because the click that follows it in the same gesture writes this same scroll and a write cancels an animation instead of superseding it (`landing.js`, at `land`) |
| whether the margin card shows, and which target's threads | the user's standing target: focus on the target or inside it, its margin cluster, or the card | `margin-projection.js`'s `followStanding` on focus arrival, the standing scope's `release` (`focus.js`), `pressAway` for a press outside the card, its target, and its cluster, and the explicit opens (`t`, a marker, a mark); with Threads open, `followStanding` expands the target's thread in the list instead (`accompanyThread`, `thread/landing.js`) |
| the margin card's place in its transcript | the card list's own scroll, held through a re-render of the same thread by the place hold above | a landing through `scrollThreadIntoView`, a send revealing its reply, `buildThreadCard` starting another thread at the top, or a new agent turn following the visible tail; placing the card writes none |
| how much of a scroller the user can see, and where a landing may put something | the scroller's shown band less the covers declared through `declareCoverRoom` that stick in it, or less its declared `scroll-padding` | `visibleBand` and `landingBand` in `geometry.js`; `shownRect`'s clip walk applies `visibleBand` at every ancestor, so whether something is on screen has one answer |
| what a surface standing over the page hides | the surface's own box, for what stacks beneath it and outside it | the surface declares itself once through `declareOccluder` (`geometry.js`); the thread panel does, and `shownRect` takes what it stands over away, so exposure, travel, and badge placement read it alike |
| which surface a trip clears to show its destination | the selected auxiliary surface, where it covers the page or stands over most of the destination (`hides`, `geometry.js`) | `clearFor` on the auxiliary-surface owner, called from travel's one `trip` entry (`anchor-travel.js`), which then reads past whatever surface still stands |
| region width the user drew | the user's store, per edge | `drawnEdge`'s `set` and `restore` |
| keyboard meaning | registered scope and row objects, tiered over the layer stack the popovers and modal dialogs pushed; for Escape, inner steps, then the surface holding focus with whatever stands inside it, then every step rooted outside it | the dispatcher and each visible key surface read the same binding-specific ownership |
| draft generation | the user's draft record | draft-store helpers and `watchDraft` |

User state that a document replacement would otherwise destroy has four routes, and
which one a fact takes is decided by what the fact is, not by where it was noticed:
the patch keeps the node, so state on a node it did not rewrite needs nothing; an
authored id gets `carry.js`'s mechanical carry; a module's own state is the module's to
write to its store and read back under that same id, as the tab store and the draft
store already do; and a walk restores its standing by declared id on top of those. A
hold — deferring the revision — is for a gesture that is not a value: an open composer,
a drag, an unresolved delivery, an open menu. A value never justifies a hold, because a
hold postpones the loss rather than preventing it: the words die when the user blurs.

Do not add a second cache, pending map, widget-specific replay list, or DOM
attribute as another source for one of these facts. A rendering may expose state,
but callers do not read the rendering to recover it. For example,
`style.display` does not answer whether the composer is open, and a focus ring
does not remember where an Ask walk last landed.
`data-lf-state` and `data-lf-retired` are settlement output for CSS and render
checks. Controllers and retirement painters receive the publisher's explicit outcome;
they never read either attribute back as semantic input.

## Startup and presentation

Startup order is load-bearing:

1. Construct the application, page commands, and UI owners in `leaf.js` before any
   mount reads another owner. Each owner contributes its own keys as it is constructed, and
   the register assembles and checks the page's stack on the first read of it, so every
   owner must stand before the first input is wired: its initial paint reads the input's
   binding badge, which resolves that stack. Adopt the sheets,
   attach chrome, mount the owners, and wire the shared repaint phases. Repaint invalidations made
   before repaint is mounted retain their intent without executing an incomplete frame.
2. Begin the first state read without applying its answer.
3. Restore the user's arrangement from storage, and let focus go to the page.
4. Fetch and validate the registry.
5. Index passage fences and authored parent identities, then capture each widget's
   immutable descriptor and typed authored state from the source DOM.
6. Publish that complete document contract once. No component is connected because
   Leaf still needs it to discover semantic input.
7. Import the modules declared by `x-upgrade` for the tags this document contains, and
   no others.
8. Start the shared dressing passes and wait for the current coordinator publication,
   including controller-registered widget preparation and the dressing region.
9. Present the optional runtime-owned page-interface region that composes those widgets.
10. Land a fresh URL's fragment in the upgraded geometry (`version.js`, `aimArrival`,
    which lands it again once the page presents), then mark `body` `data-lf-upgraded="1"`.
11. Start the state feed; its first answer is applied and reconciled, then current
    coordinator readiness presents the page. The feed waits a bounded time for that
    answer and then presents without one,
    offline, rather than letting a container that has stopped answering decide whether
    the page arrives at all. The read is not cancelled by that wait: it keeps the page's
    one read slot, and its answer applies when it lands, as any later read's does.

Authored HTML paints immediately on every page. The prepaint bootstrap marks the root
`data-lf-live`, and the render-blocking theme uses that fact to reserve the fixed banner
and the shortcut band, so mounting the runtime does not move the document. A restored
auxiliary surface stands over the page and reserves nothing.
Prose, ordinary links, scrolling, and layout remain usable while widgets upgrade and the
first state read is pending.
Generated interface constructed from authored markup participates in layout while it
settles, then `data-lf-upgraded` releases it from authored and tab-local state without
waiting for the first server reading. Durable controls remain unavailable until
`data-lf-presented`; what a package may do before and after that stamp is
`../references/packages.md`, "A theme change". A data-backed widget whose authored
element has no content takes its source-dependent space when that data arrives; stable
geometry for that content requires an authored reserve or a fixed rendering posture.
Fixed status and unanchored discussion chrome remain usable while a live page waits.
An optional page-interface failure reports itself without withholding presentation.
Selecting a passage does not raise the anchored composer until the passage has
survived the first projection.

`presentPage` owns the one transition from arrival to stateful interaction. Motion
helpers and the stylesheet collapse arrival animations until that boundary. Its final
synchronous `PRESENTATION` signal lets box-derived page apparatus replace provisional
geometry before the browser can paint the presented state. After it, a state change may
animate only where motion helps the user follow a change. A failed startup does not
stamp the page presented as if it had read the log.

`data-lf-presented` is stamped before the chrome that presentation paints has landed.
Whether chrome and geometry have caught up is a separate, live reading,
`renderingSettled` in `runtime/rendering.js`, whose header owns what it counts and why
the stamp does not wait on it. Schedule a rendering callback or watch a size through
that module's `nextRender`, `nextFrame`, `cancelRender`, and `sizeObserver`; lint
refuses the browser's own.

## What crosses to the server

The server does not retain refusal receipts. The condition behind a refusal can change
without the user changing the words: a referenced revision can be activated, a parent
thread can arrive, or a layer can be re-vendored. Caching the refusal would strand a
valid draft behind an obsolete answer.

Interactive event `markup` has a different door from every other field: only the CLI
can write it, after validating it against the vendored registry, while the browser
event schema refuses it.

## Authoritative projection

Python owns the durable Ask and thread projections. The browser publisher adopts
those readings and combines them with authored state and unresolved gestures;
`runtime/projection/model.js` folds widget state, and `projection/presentation.js` records
coverage and provenance. Widget controllers keep desired state separate from proof of
rendering.

Whether an Ask is answered is the registry's `$awaits.answered` condition over standing
state, which Python evaluates. Keep that reading on the server rather than adding a
browser Ask fold.

The server supplies page and thread Ask collections through each view's
`document.asks` and the thread's `asks`. The publisher combines them page first;
`runtime/asks/model.js` exposes their immutable selections. Each Ask identifies the
surface to visit and the source that answers it.

Every state read has one `through_seq`. Its normal response projects the displayed
revision and the active revision it may install. Version comparison requests its base
from `/api/view` at the sequence already applied to the DOM, keeping related views on
one log snapshot without projecting all historical revisions on every read.

Python supplies each thread's raw `awaits_user` and aggregated `attention`.
`awaitsUser` reads unresolved `attention`, which includes recovery even when the raw
flag is false. The browser never ranks workflows into attention again; it adjusts the
server's reading for unresolved local sends only. The thread model sets a thread
holding an unresolved send to wait on that send, which also retires a failed workflow's
recovery while keeping its historical message status; the publisher restores a
standing structural Ask that send cannot answer, and hands a thread the server left
with the agent back to the user when a send there is refused. Otherwise refusal
restores the accepted attention.
The server's rules for structural and prose obligations live in `../scripts/leaf/events.md`,
"Threads".

### Version and thread windows

A page widget's projection stops at `runtime.currentRevision`; a widget in frozen
thread markup reads the whole log (root `AGENTS.md`, Cross-runtime invariants).

The server projects threads from the whole log, so a thread stays current
on a pinned page even when the document projection remains historical.
Registry-declared `x-thread-seat` seats show an exact-section
textual view while the owner exists in the current document. A declared
`x-thread-surface` seats the canonical composer and Thread views inside the widget on
the terms in `../references/packages.md`, "Widget-local Thread surfaces". Dropping
the owner drops only the inline seat.

`restated` and answered-report relations persist through version notes. The note
records the version floor for each affected id or report event; silence in a
later version does not revive retracted state. Python's projection uses
containment, not a global id lookup, when deciding which detailed parts an action
rests on.

## The widget vocabulary stays open

Core code may name a widget only when the widget is part of how Leaf itself works
(root `AGENTS.md`, "Keep the layer open"); the merge grains are
`../references/packages.md`, "Package contract".
Shared facts such as languages, tones, idioms, and event definitions belong
under `$languages`, `$tones`, `$idioms`, and `$events`. A consumer reaching into
some named widget to find a layer-wide list is reading the wrong owner.

Each `x-` key's meaning is its `$keys` entry in `registry.json`; read that entry
before editing a declaration.

Booleans are appropriate only when the false case has one clear meaning.
`x-space` distinguishes the shared wide measure from all available room. A fact
that needs distinct behavior should carry those named
values instead of hiding one widget's policy in `true`.

### Data projections

External data's authority, its commands, and the page-lifetime source-id contract are
`../references/packages.md`, "External or derived data"; the browser's side is the
ownership rows above and `runtime/data.js`.

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
but unavailable to the user because of clipping, hiding, generated chrome, or
another boundary. Keep the runtime's generated markers and the gate's exclusions
in agreement.

## Layout and motion

### Space and scrolling

Allocate width independently of scrolling posture. Prose keeps its reading measure;
visual evidence may use a wider area, and an inspection surface may use the available
task area. Core owns that allocation after chrome, enclosing frames, and actual margin
occupancy. Packages declare their space needs and arrange content within the allocation;
authors choose the reading sequence and evidence. Width demand is independent of a
widget's internal drawing layout. Compact navigation must not reserve a full sidebar
when its presentation no longer needs one, and a free side may use room the other side
cannot take. Nothing Leaf draws at run time moves the page's content: a margin row
stands in the rail a column page reserves, or over the page as a pin inside its target's
top-right corner, and expanding content keeps the allocation its own declaration gave it.

Ordinary document content grows in flow. A bounded inspection object may scroll inside
that document, with native scroll chaining into the document at its boundary, including
when the object has no overflow. Use the effective reading posture, not a widget's tag,
to choose scroll ownership: a bounded task region owns its scrolling, while an embedded
or responsive flow arrangement cooperates with its containing document. A nested
inspection object chains into its containing reading region; isolation belongs at the
bounded task or modal boundary, not every descendant that overflows. Avoid adding another
vertical scroller inside a region without an inspection need. Modal surfaces isolate
background scrolling. Wheel and ordinary touch gestures retain their navigation
meaning; deliberate controls or gestures enter pan and zoom. Every necessary scroller
has a keyboard route, discernible bounds, and visible focus.

Inspection preserves useful detail. Allocate room before shrinking evidence; support
aligned detail and whole-object context rather than treating a fitted overview as proof
of legibility. If an object temporarily leaves document flow for inspection, keep the
controls needed to complete the task available and preserve the selected object,
inspection state, and surrounding document position on return. A root workspace does
not duplicate itself in another inspection layer. Narrow screens reflow surrounding
prose and controls while retaining deliberate access to two-dimensional evidence.

### Stability

The page must hold still under the user's aim. A state change may repaint any
box, but it must not move controls adjacent to the gesture that caused it. News
arriving without a gesture must not move any chrome control. A content change
the user requested may reflow the content it replaces, provided the change is
shown as trackable motion rather than an unexplained jump.

A transient hover, focus, or keyboard reveal never changes the space allocated to its
ancestors or siblings. Reveal supporting navigation over the settled page, with enough
background to keep its labels legible, or let an explicit persistent control reconfigure
the page. The same rule applies whether the revealed surface is generated by core, a
package, or authored markup.

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
or page-interface settlement before `data-lf-upgraded` releases that interface. A producer
that stays off the presentation path on purpose goes through `afterPresentation`, which
waits and declares the arrival in one call, so `pageArrived` still answers for it and
nothing outside the page has to name the widget that deferred; `deferredArrival` is that
declaration on its own, for runtime work that defers without waiting for presentation.
Apparatus that also depends on authoritative replay takes one synchronous reading on
`PRESENTATION`, then uses `sizeObserver` or the shared layout signal for later changes.
An asynchronous producer's default may reserve space without painting; a box-derived
reading taken before replay does paint, and `PRESENTATION` replaces it.

An action awaiting confirmation dims its existing control after the shared delay; it
does not gain another mark or change geometry. Durable workflow state uses the control's
semantic label or agent-workflow treatment. Reserve space before a generated control
appears. Transient feedback may repaint a control or
briefly replace its label, but neither may change its geometry; `reserve` measures all
enumerable labels in the control's current font and sets a minimum width. Re-measure
after changing type tokens. The banner status keeps a concise one-line summary with
ellipsis; its native disclosure and hover title expose the complete activity reading.
The disclosure is keyboard- and touch-accessible, and its CSS reservation stays
independent of changing copy. Status kind changes announce the complete reading.
Pair local visual feedback with `notice` for an assistive announcement.

Use one contour to carry one control state. Do not stack a colored border with an inset
underline or ring on the same selected control; the second edge reads as a stray border.
In a segmented group, keep one-pixel shared seams and let fill, ink, or one outline make
the selection distinct without adding another line inside it.

Message workflow stays on the existing semantic margin control whenever one survives:
pickup uses a green icon, moving any positive or negative tone to the existing contour;
working keeps the green icon, colors the interior green, and pulses once on arrival. A
generated status carries the same workflow when no semantic control exists. Message
metadata carries it beside the triggering message; thread cards do not repeat it as a
colored edge. Quiet or ended work releases the control. Reduced motion suppresses arrival,
and repainting or replacing a carrier cannot replay it.

Each Thread's `unread` is the one reading of what the user has not read. The
Threads toggle's dot and label, the panel's **Unread** jump and per-thread counts, the
**New since you last looked** boundaries, a margin entry's dot and its Page Map row
all paint it, so they change together. Reading is bookkeeping and never moves the
user: a mark inside a thread is drawn in room the content keeps whether or not
it is unread, so a receipt changes no box the user is looking at. The server counts
a reply, reaction, widget answer, resolve, or reopen as reading what the thread held
before it; the page adds exposure: a whole prose body shown in one surface, whatever
its own scrollers still hold, since geometry cannot tell how much of a wide code line
was read. An authored body with widgets is read by answering it or by **Mark thread
read**. An edit is a new version and reads as unread again.

Each Thread's canonical `attention` is its aggregate user obligation or waiting
workflow. A concrete user Ask outranks concurrent agent work; that work remains the
secondary status. Local failure or recovery may add user-owned attention beyond the
server's raw `awaits_user` value. Margin, Page Map, and compact thread rows consume
that same attention instead of deriving another aggregate from member turns or workflow
stages. User attention wears the same two channels in blue — icon and interior — and
says "On you" for an Ask or the exact recovery label in its visible and accessible name.

Submission feedback uses the shared lifecycle: the result of the gesture as durable
confirmation, and `notice` for a transient acknowledgment. Persistent status text is for
a state the user must return to or act on, such as failure.

Where the page can produce that result itself, it produces it in the gesture. A
suggestion decision paints its projected outcome; a comment or reply paints the message
and opens its thread. Drawing the result moves the words, so the box they were written
in reads empty in that same turn. The user's answer stands on screen once, rather than
beside a copy of itself still waiting to be sent. The generation is unsettled until the
log answers, and a refusal returns it to the box. The runtime's send owns both halves
(`standGesture`), so no box empties or refills itself.
The application overlays pending work on the log and restores authoritative state on
refusal. The content and its Undo control are the confirmation,
so neither path needs a success notice; announce the same outcome for a user listening
to the page. For a message that announcement is `post`'s, made where the gesture is first
known to be a message, so a box that sends one adds no second announcement. A box whose
press did something beyond sending writes one notice for both and names the send in it,
because a later write replaces the live region rather than joining it. A gesture whose
result only the log can supply waits instead, with
`aria-busy` on the surface, which `chrome.css` paints on a delay so a fast answer shows
nothing at all.

### Motion

Nothing the user must read, press, or decide waits on a clock. Motion runs from a state
that is already true: a fold collapses room the user has already been told is going, a
carry moves a card that has already arrived. Motion that has to finish before the result
can be read is a pause.

A motion the user is waiting to end runs as long as the eye needs to follow a box from
where it was to where it is, and stays under 300ms. A motion that moves nothing carries
no such bound, so a landing flash or an arrival pulse may run longer; the user reads
straight through it.

The `aria-busy` wait above withholds a look rather than a result. It removes a flicker a
fast answer would otherwise paint and leave, and a delay may subtract that way. A minimum
spinner time, a staged reveal, or a pause that makes work read as substantial adds one
instead.

`runtime/motion.js` owns the shared gate, the ease, and the reduced-motion answer for the
motion it plays; the theme's guard answers for CSS. A duration two motions share belongs
there under one name, as `FOLD_MS` is, because two numbers written for one reason are free
to disagree. A duration one motion uses states its reason where it is passed. CSS
transitions answer to the same ceiling.

## Render gates

`leaf version check <page> --render` is the browser contract. It runs both color
schemes, waits for the runtime's actual readiness and finite motion boundary, reads
screen and print, and reapplies standing state.
A local browser check is required after changing `leaf.js`, a runtime owner, a widget
module, the registry, or the theme.

The named JavaScript exports in `leaf/render-checks/index.js`, invoked by
`leaf/render_checks.py` and composed by `leaf/render_gate/`, each answer one failure
class. That facade is `leaf/render-checks/index.js`; its directory groups runtime,
reachability, layout, replay, word, widget-contract, and framing probe owners. The
served graph imports the public widget API statically, so the JavaScript parser and
module loader validate its syntax, dependencies, and named exports.
`render-checks/init.js` installs the pre-navigation window-error channel.
`render-checks/driver.js` stays outside `PROBE_SOURCES` and the served probe module graph;
Playwright installs it as an init script or reads it directly on an already-open page,
and repository lint checks the source.

| Reading | Contract |
| --- | --- |
| window-error init channel | no runtime, module, resource, or ResizeObserver error reached the page |
| `unnamedFormFields` | every native field or form-associated custom control has an id or name; a custom control owns its implementation fields and grouped choices |
| `upgraded` and `moving` | upgrade completed and final geometry settled |
| `invalidPaints` | every var()-backed SVG paint resolves to a valid value in each scheme |
| `tinyBoxes` | every declared widget has a usable rendered box |
| `unmarkableElements` | every addressable element has a visible part for an outline |
| `misplacedBoxes` | boxes stay in the column or in genuinely reachable overflow, at every swept width |
| `misalignedSplits` | advice only: a page's layout grids split where its busiest grid does |
| `squeezedTables` | a table scrolls sideways only with every column at its longest unbreakable run |
| `withheldRoom` | a drawing scrolls only when the room, net of margin residents at its band, ran short |
| `strandedMargins` | every margin marker has an element it can stand by |
| `coveringMargins` | advice only: which margin pins stand over lines of the page's text |
| `shrunkLabels` | advice only: which drawings scale their painted labels below a legible size at the desktop viewport |
| `silentCuts` | a box showing less than it holds across paints a mark on each edge with content beyond it |
| `clippedControls` | actionable controls are visible and reachable |
| `unreachableWords` | visible page words remain in reachable flow |
| `coveredWords` | browser words are not silently clipped, hidden, or claimed by chrome |
| `unreadSyntax` | syntax highlighting does not erase or alter source words |
| `shownVerbatim` | every preserving owner agrees with its revision- or thread-scoped projected passage |
| `silentWords` | `x-says` and `x-paints` promises reach the composed rendered page |
| `undeclaredAttrs` | modules do not write undeclared author-namespace state |
| `retiredSlots` | declared settlement marks and retired-slot visibility agree with the projection |
| `trappedMargins` | framed boxes show only their declared inset |
| `paperWords` | print keeps every page statement and removes only affordance |
| `paperVoids` | print gives room to nothing it does not also draw |
| `replayOverrides` | the log, not conflicting authored markup, determines projected state |
| `relativeReplays` | rendering each complete widget state twice changes nothing |

`validationWidgetStates` is an internal publisher-backed validation adapter;
`shallowSigs` is the DOM signature helper. Keep their readings aligned with the
runtime's projection and authored-state definitions.
Do not create a test-only interpretation of a widget's state.

The static check and browser gate cover different boundaries. Static validation
owns schema, ids, nesting, stable passages, event shapes, restatements, and file
readings. The browser owns computed layout, composed trees, module writes,
focusable controls, screen/print agreement, and replay idempotence. Put a check
on the side that can observe the fact.

Named journey tests retain behaviors that a generic render reading cannot drive:

- `test_a_refused_attempt_is_re_read_against_the_page_that_refused_it` covers
  refusal without a durable receipt.
- `test_a_user_arrives_at_what_they_left_rather_than_watching_it_arrive`
  covers every `USER_VIEW_RESTORE_CASES` restore.
- `test_a_page_nobody_has_touched_scrolls_from_the_keyboard` covers the initial
  focus handoff to `body`.
- `test_a_commented_block_says_so_to_a_screen_user` covers the accessible
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

`scripts/browser/build.mjs` owns the compiled TypeScript foundation in
`vendor/browser-runtime.js`; contributor diagnostics (the manifest, licenses, and
source map) live under `scripts/browser/generated/`. The manifest names its inputs,
exports, and output hashes; `scripts/AGENTS.md`
owns the contributor build and check commands. The same build writes `vendor/lit.js`,
the page's one copy of Lit, which the framework bundle imports and which the Web
Awesome bundle (`scripts/vendor.py webawesome`) imports as well rather than carrying
its own; neither has any other import or a runtime compiler. Content modules import
only `runtime/widget-api.js`. Server projection entries carry the declaration admitted from
their captured revision, so neither active nor historical views reinterpret an event
through the current DOM's registry.

Run `node --check` on the module, formatting, and a focused real-browser test while
iterating. What a module decides on its own — a value folded from values, a tree
question answered from the tree — is tested in `tests/runtime/*.test.mjs`, which imports
it into a document object model rather than a browser and answers in under a second
(`npm run test:runtime`); `tests/AGENTS.md` owns which readings may go there.
A module that reads another owner as it evaluates parses and lints clean and
fails only in the browser, as `Cannot access X before initialization` at boot; the
rule and its remedies are under Runtime ownership above. Before handing over a runtime or theme
change, run the relevant full browser file or `leaf version check --render` on
the affected example. `node --check` cannot validate browser bindings, computed
layout, or reconciliation; the layer tests parse every vendored stylesheet.
