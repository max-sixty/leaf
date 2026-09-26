# The page in the browser

This file owns browser-wide contracts: how the page should look and move, module
boundaries, startup, state authority, and the render gates. Each module's header
owns its local contract. Page-authoring rules live in
`../references/page-authoring.md`, package contracts in `../references/packages.md`,
and rules shared with Python in root `AGENTS.md`, "Cross-runtime invariants".

## Layout and motion

Leaf's current product focus is desktop; judge layout first at a representative
desktop viewport.

### Space and scrolling

Allocate width independently of scrolling posture. Prose keeps its reading
measure; visual evidence may take a wider area, and an inspection surface the
available task area. Core owns that allocation after chrome, frames, and margin
occupancy; packages declare their space needs and arrange content inside it.
Compact navigation doesn't reserve a full sidebar it no longer needs.

Nothing Leaf draws at run time moves the page's content. A margin row stands in
the rail a column page reserves, or as a pin inside its target's corner. The
auxiliary surfaces (Asks tray, thread panel, Leaves tray) stand over the page and
never change its geometry; the Asks tray and panel leave the page live beside
them, and cover it where they would leave less than a usable page
(`--lf-auxiliary-beside`, read by `standsBeside`). A workspace's scrolling
posture is the stylesheet's container query, which the runtime reads rather than
decides.

Ordinary content grows in flow. A bounded inspection object may scroll inside the
document and chain into it at its edges; isolate scrolling only at a bounded task
or modal boundary, and add no vertical scroller without an inspection need. Wheel
and touch keep their navigation meaning; deliberate controls enter pan and zoom.
Every necessary scroller has a keyboard route, visible bounds, and visible focus.
Allocate room before shrinking evidence, and keep narrow screens' access to
two-dimensional evidence deliberate. Expanding content keeps the allocation its
declaration gave it. An object that leaves flow for inspection keeps the controls
its task needs and restores the selection, inspection state, and document
position on return; a root workspace never duplicates itself in another
inspection layer.

### Stability

The page holds still under the user's aim. A state change may repaint any box but
must not move controls next to the gesture that caused it, and news arriving
without a gesture moves no chrome control. A change the user requested may reflow
the content it replaces, shown as motion the eye can follow. A hover, focus, or
keyboard reveal never changes the space given to its ancestors or siblings.

Generated interface first appears in its settled position. Reserve space before a
generated control appears; transient feedback may repaint a control or briefly
replace its label but never change its geometry (`reserve` sizes a control for
all its labels). An action awaiting confirmation dims its existing control after
the shared delay. The parent laying out adjacent actions gives them disjoint hit
boxes.

A gesture whose result the page can draw shows that result in the gesture (root
`AGENTS.md`, "The document starts state; the log changes it"); `standGesture`
owns both the send and the refusal that returns words to their box. The content
and its Undo are the confirmation, so success needs no notice beyond the
announcement for a listener. A result only the log can supply waits with
`aria-busy`, painted on a delay so a fast answer shows nothing. Persistent status
text is for a state the user must return to, such as failure.

### Visual grammar

Use visual treatments to carry hierarchy and state. Contours are solid; a dotted
or dashed line is a non-color cue for a distinct state (a draft, a drag
placeholder, design-mode geometry, a detached reference); lines inside authored
diagrams keep the document's own meaning. One contour carries one
control state, and a segmented group keeps one-pixel shared seams. Avoid rounded
one-sided borders and reflexive cards, tints, gradients, or soft shadows.

Each Thread's `unread` and `attention` are single readings that every surface
painting them consumes, so the Threads toggle, filters, panel, margin entry, and
Page Map change together. Workflow state rides the existing semantic control
rather than a colored edge: pickup colors its icon green, and working also colors
the interior and pulses once on arrival, which a repaint never replays. User attention wears
the same two channels in blue. Reading is bookkeeping and never moves the user.

### Motion

Nothing the user must read, press, or decide waits on a clock. Motion runs from a
state that is already true, and motion that must finish before the result can be
read is a pause. A motion the user waits on stays under 300ms; one that moves
nothing, such as a landing flash, may run longer. A delay may withhold a flicker
but never adds a minimum spinner time or a staged reveal. `runtime/motion.js` owns
the shared gate, ease, reduced-motion answer, and every duration two motions
share; the theme's guard answers for CSS.

## Runtime ownership

`leaf.js` is the boot-only entry: every owner is a module that exports its
capability and imports what it needs, and `leaf.js` imports them and runs the
boot sequence. `runtime/bootstrap.js` loads before everything else, can show a startup
failure even if the module graph never loads, and holds page keys pressed
before presentation. Content modules import only
`runtime/widget-api.js`, the public helper surface; owners never reach back
through it or the entry module. Owners are constructed with explicit capabilities
and cross-owner reads happen in their mounts. Pure projection, thread, and
pending models import no DOM or application services, and renderers receive the
commands they use. `.dependency-cruiser.mjs` enforces these boundaries and
rejects cycles, so runtime imports use literal paths; only the widget and
interaction loaders compute theirs, to load content modules.

Entry points per concern (paths under `runtime/`; each header owns the details):

| Concern | Owners |
| --- | --- |
| Composition and semantic publication | `application.js`, `semantic-state.js`, `context.js` |
| Delivery, accepted state, and wakeups | `delivery.js`, `state-application.js`, `state-feed.js`, `layer-client.js`, `traffic.js` |
| State models and projection | `projection/`, `thread/model.js`, `thread/workflow.js`, `thread/state.js`, `pending/`, `asks/model.js` |
| Widget capture and lifecycle | `document-identity.js`, `widget-descriptors.js`, `widget-controller.js`, `widget-loader.js`, `widget-upgrade.js` |
| Vocabulary and public helpers | `registry.js`, `widget-api.js`, `widget-elements.js`, `request-elements.js` |
| External data | `data.js`, `projection/data.js`, `projection/authored.js` |
| Revision installs and continuity | `version.js`, `version-chooser.js`, `carry.js`, `dom-children.js`, `root-state.js`, `restore-state.js` |
| Repaint and geometry | `rendering.js`, `repaint.js`, `standing.js`, `page-geometry.js`, `geometry.js`, `rect.js`, `pointer.js` |
| Chrome and available room | `chrome.js`, `chrome-layout.js`, `auxiliary-surfaces.js`, `drawn-edge.js` |
| Reading regions and scrolling | `reading-regions.js`, `reading-place.js`, `bounds.js`, `scrolling.js`, `reach.js`, `user-place.js` |
| Keyboard | `keyboard/AGENTS.md` |
| Focus and navigation | `focus.js`, `standing-target.js`, `navigation.js`, `history.js`, `user-intent.js`, `walk-position.js` |
| Asks | `asks/` |
| Comment capture | `composing/`, `drafts.js`, `media.js` |
| Threads | `thread/`, `thread-panel.js` |
| Margin and Page Map | `margin-*.js`, `page-map-dialog.js`, `thread-card-geometry.js` |
| Passages and target identity | `passages.js`, `text-alignment.js`, `anchor-coordinate.js`, `target-references.js`, `resolved-target.js`, `anchor-resolution.js` |
| Anchor paint and travel | `anchor-paint.js`, `anchor-note-view.js`, `anchor-controls.js`, `anchor-travel.js`, `target-paint.js`, `visual-parts.js`, `indication.js` |
| Banner and approvals | `banner*.js` |
| Trays and neighboring pages | `trays.js`, `live-leaves*.js` |
| Activity and updates | `presence.js`, `updates.js` |
| Notices and announcements | `semantic-news.js`, `notifications.js`, `keyboard/shortcut-bar.js` |
| Reactions and design review | `reactions.js`, `design.js`, `design-readings.js` |
| Presentation and validation | `presentation.js`, `validation.js`, `projection-watch.js`, `retained-face.js` |
| Child pages and gallery playback | `specimen.js`, `interaction-gallery*.js` |
| Shadow trees and styles | `shadow.js`, `shadow-stage.js`, `stylesheets.js` |
| Utilities | `icons.js`, `markdown.js`, `syntax.js`, `motion.js`, `storage.js`, `interaction-log.js` |

`runtime/rendering.js` runs every rendering callback in one pass per frame; schedule
through its `nextRender`, `nextFrame`, `cancelRender`, and `sizeObserver`, since
lint refuses the browser's own.

Stylesheets apply in layers. `theme.css` holds page tokens, element styles,
idioms, and CSS-only widgets, and each package theme follows it; shared shadow
rules compose into `/shadow.css`, whose shared `.lf-ui` face comes before
component rules. `runtime/chrome.css` is adopted after page and package sheets and
wins by its selectors. `runtime/marks.css` is adopted by the document and shadow
stages. A `:has()` whose rightmost compound carries no class, id, attribute, or
type restyles every element on ordinary runtime writes
(`test_no_has_rule_restyles_the_whole_document`); key a repeated type by a class
its owner writes.

### One writer for each fact

Each mutable fact has one authority and one browser writer. The application
publisher combines authored state, the admitted server reading, and the ordered
ledger of unresolved local work into the one semantic reading every component
selects from:

| Fact | Authority |
| --- | --- |
| authored widget state | validated source markup, staged before upgrade and admitted atomically with descriptors and revision identity |
| external data | the latest page data reading; `watchData` delivers each bound source |
| version shown | the revision the delivery prelude names; a newer revision with the same executable identity patches in place, a different one navigates to a fresh document |
| accepted history, and the reading applied | the server event log and its `/api/state` answer, adopted whole by the publisher |
| unresolved browser work | the publisher's one ordered ledger |
| thread, workflow, attention, Asks, activity, unread | the server's folds; the browser adds only its own unresolved sends and the versions it is marking read |
| what the DOM represents | controller presentation tickets and projection commits |
| when a document-wide renderer paints | the publication that opened the epoch, in the order `runtime/semantic-state.js` declares |
| where each thread's passage lands | anchor paint's resolution of its anchor in this version |
| geometry readings: what a scroller shows, what a surface hides, cover room | `geometry.js` (`visibleBand`, `declareOccluder`, `declareCoverRoom`), so being on screen has one answer |

Do not add a second cache, pending map, widget-specific replay list, or DOM
attribute as another source for one of these facts; a rendering may expose state,
but no caller reads it back. `data-lf-state` and `data-lf-retired` are output for
CSS and render checks only.

User state that replacing the document would destroy survives by what it is. The
patch keeps a node it did not rewrite; an authored id gets `carry.js`'s carry; a
module's own state is written to its store and read back under the same id; a walk
restores its standing by declared id. A hold, which defers the revision, is for a
gesture that is not a value: an open composer, a drag, an unresolved delivery, an
open menu.

## Startup and presentation

Startup order is load-bearing:

1. Construct the application, page commands, and UI owners in `leaf.js`; every
   owner stands before the first input is wired, then sheets are adopted, chrome
   attached, owners mounted, and the repaint phases wired.
2. Begin the first state read without applying its answer.
3. Restore the user's arrangement from storage.
4. Fetch and validate the registry.
5. Index passage fences and parent identities, then capture each widget's
   descriptor and typed authored state from the source DOM.
6. Publish that document contract once.
7. Import the modules `x-upgrade` declares for the tags present, and no others.
8. Run the dressing passes and wait for the coordinator publication.
9. Present the optional runtime-owned page-interface region.
10. Land a fresh URL's fragment, then stamp `data-lf-upgraded="1"`.
11. Start the state feed; its first answer presents the page, or after a bounded
    wait the page presents offline and applies the answer when it lands.

Authored HTML paints immediately, and the render-blocking theme reserves the
banner and shortcut band so mounting the runtime moves nothing. Prose, links, and
scrolling work while widgets upgrade. Page keys wait, because a command reads
state the first answer brings: the bootstrap holds printed keys pressed before
presentation and the keyboard controller replays them in order once the page
presents, while any other key or a pointer press drops the held run. Durable
controls wait for `data-lf-presented` (`../references/packages.md`, "A theme change"). An async
producer joins settlement before `data-lf-upgraded`, or stays off the
presentation path through `afterPresentation`, which declares the deferred
arrival so `pageArrived` still answers for it. `presentPage` owns the one
transition to stateful interaction; its synchronous `PRESENTATION` signal lets
box-derived apparatus replace provisional geometry before the presented state
paints. `renderingSettled` in `runtime/rendering.js` is the separate, live
reading of whether chrome has caught up.

## Authoritative projection

Python owns the durable Ask and thread projections, including whether an Ask is
answered (the registry's `$awaits.answered`); the browser adds no second fold.
The server ships page and thread Asks as `document.asks` and the thread's
`asks`, and each thread's `attention`, the one reading of whose turn a thread is
(`needs_user` or `waiting`), which the browser adjusts only for its own
unresolved sends; a refusal restores the accepted reading. Every state read has
one `through_seq`, and version comparison asks `/api/view` at the sequence
already applied. A page widget's projection stops at the current revision; a
widget in frozen thread markup reads the whole log. `restated` and answered
reports persist through version notes, so silence in a later version does not
revive retracted state. The server keeps no refusal receipts, because the
condition behind a refusal can change without the user's words changing.

## The widget vocabulary stays open

Core names a widget only when it is part of how Leaf works (root `AGENTS.md`,
"Keep the layer open"); the merge grains are `../references/packages.md`,
"Package contract". Layer-wide facts live under `$languages`, `$tones`,
`$idioms`, and `$events`; each `x-` key's meaning is its `$keys` entry in
`registry.json`. Use a boolean only when false has one clear meaning; otherwise
declare named values.

The Python reader models only transformations the registry declares. A module
that changes text in a way the file cannot reproduce is fenced: browser capture
stops at the fence, so a selection crossing it is not captured as a quote the file
cannot confirm. Declare modelable words with `x-says`, `x-paints`, or the content
key, and keep the widget fenced when its transformation cannot be represented.

## Render gates

`leaf version check <page> --render` is the browser contract: both color schemes,
the runtime's actual readiness and motion boundary, screen and print, and
reapplied standing state. Run it, or the relevant browser test file, after
changing `leaf.js`, a runtime owner, a widget module, the registry, or the theme.
`leaf/render-checks/index.js` exports one probe per failure class, invoked by
`leaf/render_checks.py` and composed by `leaf/render_gate/`:

| Reading | Contract |
| --- | --- |
| window-error channel | no runtime, module, resource, or ResizeObserver error reached the page |
| `unnamedFormFields` | every field or form-associated control has an id or name |
| `issueNode` | a DevTools issue outside a form control's shadow tree is the page's, placed at its frame if it has one |
| `upgraded`, `moving` | upgrade completed and geometry settled |
| `invalidPaints` | every var()-backed SVG paint resolves in each scheme |
| `tinyBoxes` | every declared widget has a usable box |
| `unmarkableElements` | every addressable element has a visible part to outline |
| `misplacedBoxes` | boxes stay in the column or in reachable overflow at every width |
| `squeezedTables` | a table scrolls sideways only with every column at its longest unbreakable run |
| `withheldRoom` | a drawing scrolls only when room, net of margin residents, ran short |
| `strandedMargins` | every margin marker has an element to stand by |
| `silentCuts` | a box showing less than it holds marks each edge with content beyond it |
| `clippedControls` | controls are visible and reachable |
| `unreachableWords`, `coveredWords` | visible words stay in reachable flow and are not silently clipped or claimed by chrome |
| `unreadSyntax` | highlighting does not alter source words |
| `shownVerbatim` | preserving owners agree with their projected passage |
| `silentWords` | `x-says` and `x-paints` promises reach the rendered page |
| `undeclaredAttrs` | modules write no undeclared author-namespace state |
| `retiredSlots` | settlement marks agree with the projection |
| `trappedMargins`, `splitEdges` | framed boxes show only their inset and edge rows line up |
| `paperWords`, `paperVoids` | print keeps every statement and gives room only to what it draws |
| `replayOverrides` | the log, not conflicting markup, determines projected state |
| `relativeReplays` | rendering a complete widget state twice changes nothing |
| `misalignedSplits`, `coveringMargins`, `shrunkLabels` | advice only |

Put a check on the side that can observe the fact: static validation owns schema,
ids, nesting, passages, event shapes, and file readings; the browser owns computed
layout, composed trees, module writes, focus, print, and replay idempotence.
Readings of widget state use the publisher's own reading; never write a test-only
interpretation of it.

## Working on the runtime

`scripts/browser/build.mjs` compiles the TypeScript foundation into
`vendor/browser-runtime.js` and writes `vendor/lit.js`, the page's one copy of Lit
(`scripts/AGENTS.md` owns the commands). What a module decides on its own is
tested under `tests/runtime/` (`npm run test:runtime`; `tests/AGENTS.md` says
which readings may go there).
