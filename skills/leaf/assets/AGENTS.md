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

The page owns its arrangement: a shipped Layout class (`@layer lf-layouts` in the
theme) or its own CSS. Leaf owns what pages and widgets coordinate through: the
bands, the reading measure as typography, and each widget's contract to fill the box
it is given, declare the minimum it needs, and never let its content size its holder.

Nothing Leaf draws at run time moves the page's content. A margin row sits either in
the rail, a strip right of `main` that appears where the window has room for it, or as
a pin over the page by its target (`rowPosture`). The rail never moves, narrows, or
indents the column, and `data-rail` on `body` withholds or reserves it
(`margin-layout.js`); the column moves over only to give room to the page's own asides
that declare `--lf-resident` (`settleResidency`). A pin, a passage mark, and everything
else in the annotation layer is an overlay that covers what lies under it; a pin takes
a seat that covers no words where one is within reach (`margin-placement.js`). Nothing
makes room for an overlay, so nothing moves when a marker arrives, leaves, or changes
place, even one that always accompanies its target, such as an Ask's: reserved room
would make the page's geometry depend on which markers are shown. Where a pin covers
something the user needs, the answers are `o`, or More's Hide annotations under a
finger, and a better placement.

The auxiliary surfaces (Asks drawer, thread panel, Leaves drawer) lie over the page and
never change its geometry; the Asks drawer and panel leave the page live beside
them, and cover it where they would leave less than a usable page
(`--lf-auxiliary-beside`, read by `standsBeside`). The stylesheet, a Layout's or the
page's, decides which box scrolls, and the runtime reads the result.

Content grows in flow. Add a vertical scroller only for a bounded inspection object,
which chains its scroll into the document at its edges, and isolate scrolling only at a
bounded task or a modal. Wheel and touch keep their navigation meaning; pan and zoom
need a deliberate control. Every scroller has a keyboard route, visible bounds, and
visible focus. Give evidence room before shrinking it, and decide how a narrow screen
shows two-dimensional evidence, such as a wide table or a diagram, rather than letting
it shrink. Expanding content keeps the room its `x-space` declaration gave it. An
object that leaves flow for inspection keeps the controls its task needs and, on
return, restores the selection, inspection state, and document position. A root
workspace is never shown again inside another inspection layer.

### Stability

The page holds still under the user's aim. A state change may repaint any box but
must not move controls next to the gesture that caused it. News causes no layout
shift: when a box's content changes without a gesture, that box may grow or shrink
into free room, but no other element moves. News grows where the reader isn't
looking: above the screen, where scroll anchoring takes the growth into what they
scrolled past, or below it. So a thread's reply box stands at the foot of the
scroller that shows the thread, in the Threads panel as in the margin card, and a
reply grows the thread above it without moving the box or its caret. Where news would
move what the reader is reading, it waits behind a control of fixed size until they
open it, as a reply arriving in a thread in the page's flow waits behind its head
row's notice (`thread/held-news.js`). A change the user requested may reflow the
content it replaces, shown as motion the eye can follow. A hover, focus, or
keyboard reveal never changes the space given to its ancestors or siblings. Typing
may grow its field at the edge its layout grows, but never carries the field. The
suite's browser fixture fails any test outside the nightly selection whose page makes a
layout shift Chrome reports without recent input, or whose typing carries its field
(`tests/shift_watch.js`).

A widget paints its final box before it upgrades: the theme sizes it under
`html[data-lf-live]` as its module will draw it. The widget-quality check
`keeps-first-box` measures this (`leaf package check PACKAGE --render`), and the
suite runs it over every bundled package, failing a finding
`tests/known_widget_findings.py` does not list. A generated control likewise appears
where it will stay: feedback may repaint it or swap its label but not resize it
(`reserve` sizes a control for all its labels), and adjacent actions get disjoint hit
boxes.

A gesture whose result the page can draw shows that result as it is made (root
`AGENTS.md`, "The document starts state; the log changes it"). `standGesture`
(`drafts.js`) owns both the send and the refusal that returns the words to their box.
The changed content and its Undo confirm success, so success needs no notice beyond the
screen-reader announcement. A gesture that moves the user, as settling a thread does,
owns the move back on refusal and on undo (`thread/folding.js`). A result only the log
can supply waits under `aria-busy`, which dims the existing control after a shared
delay, so a fast answer shows nothing. Persistent status text is for a state the user
must come back to, such as a failure.

### Visual grammar

Use visual treatments to carry hierarchy and state. Contours are solid; a dotted
or dashed line is a non-color cue for a distinct state (a draft, a drag
placeholder, design-mode geometry, a detached reference); lines inside authored
diagrams keep the document's own meaning. One contour carries one
control state, and a segmented group keeps one-pixel shared seams. Avoid rounded
one-sided borders and reflexive cards, tints, gradients, or soft shadows.

Each Thread's `unread` and `attention` are single readings that every surface
painting them consumes, so the Threads toggle, filters, panel, margin entry, and
Page Map change together. Workflow state is shown on the existing semantic control
rather than as a colored edge: pickup colors its icon green, and working also colors
the interior and pulses once on arrival, which a repaint never replays. User attention
uses the same two cues in blue. Marking read is bookkeeping and never moves the user.

### Motion

Nothing the user must read, press, or decide waits on a clock. Motion runs from a
state that is already true, and motion that must finish before the result can be
read is a pause. A motion the user waits on stays under 300ms; one that moves
nothing, such as a landing flash, may run longer. A delay may withhold a flicker
but never adds a minimum spinner time or a staged reveal. `runtime/motion.js` owns
the shared gate, ease, reduced-motion answer, and every duration two motions
share; the theme's guard answers for CSS.

## Runtime ownership

`leaf.js` only boots: it constructs each owner module with explicit capabilities and
runs the boot sequence. `runtime/bootstrap.js` loads first, reports a startup failure
even if the module graph never loads, and holds keys pressed before presentation.
Content modules import only `runtime/widget-api.js`, the public helper surface, and
owners never import back through it or the entry; cross-owner reads happen in mounts.
The projection, thread, and pending models are pure, importing no DOM or application
service, and renderers receive the commands they use. `.dependency-cruiser.mjs`
enforces these boundaries and rejects cycles, so imports use literal paths; only the
widget and interaction loaders compute theirs.

Entry points per concern (paths under `runtime/`; each header owns the details):

| Concern | Owners |
| --- | --- |
| Composition and semantic publication | `application.js`, `semantic-state.js`, `context.js` |
| Delivery, accepted state, and wakeups | `delivery.js`, `state-application.js`, `state-feed.js`, `layer-client.js`, `traffic.js` |
| State models and projection | `projection/`, `thread/model.js`, `thread/workflow.js`, `thread/state.js`, `pending/`, `asks/model.js` |
| Widget capture and lifecycle | `document-identity.js`, `widget-descriptors.js`, `widget-controller.js`, `widget-loader.js`, `widget-upgrade.js` |
| Vocabulary and public helpers | `registry.js`, `widget-api.js`, `widget-elements.js` |
| External data | `data.js`, `projection/data.js`, `projection/authored.js` |
| Revision installs and continuity | `version.js`, `version-picker.js`, `carry.js`, `dom-children.js`, `root-state.js`, `restore-state.js` |
| Repaint, writes, and geometry | `rendering.js`, `repaint.js`, `keeps.js`, `standing.js`, `page-geometry.js`, `geometry.js`, `rect.js`, `pointer.js`, `floating.js` |
| Chrome and available room | `chrome.js`, `chrome-layout.js`, `auxiliary-surfaces.js`, `drawn-edge.js` |
| Reading regions and scrolling | `reading-regions.js`, `reading-place.js`, `bounds.js`, `scrolling.js`, `reach.js`, `user-place.js` |
| Keyboard | `keyboard/AGENTS.md` |
| Focus and navigation | `focus.js`, `standing-target.js`, `navigation.js`, `history.js`, `user-intent.js`, `walk-position.js` |
| Asks | `asks/` |
| Comment capture | `composing/`, `drafts.js`, `media.js` |
| Threads | `thread/`, `thread-panel.js` |
| Margin and Page Map | `margin-*.js`, `page-map-dialog.js`, `thread-card-geometry.js`, `pointed-place.js` |
| Passages and target identity | `passages.js`, `text-alignment.js`, `anchor-coordinate.js`, `target-references.js`, `resolved-target.js`, `anchor-resolution.js` |
| Anchor paint and travel | `anchor-paint.js`, `anchor-note-view.js`, `anchor-controls.js`, `anchor-travel.js`, `target-paint.js`, `visual-parts.js`, `indication.js` |
| Banner and approvals | `banner*.js` |
| Drawers and neighboring pages | `drawers.js`, `live-leaves*.js` |
| Activity and updates | `presence.js`, `updates.js` |
| Notices and announcements | `semantic-news.js`, `notifications.js`, `keyboard/shortcut-bar.js` |
| Reactions and design review | `reactions.js`, `design.js`, `design-readings.js` |
| Presentation and validation | `presentation.js`, `validation.js`, `projection-watch.js`, `retained-face.js` |
| Child pages and gallery playback | `sample.js`, `interaction-gallery*.js` |
| Shadow trees and styles | `shadow.js`, `shadow-stage.js`, `stylesheets.js`, `page-sheets.js` |
| Paint that follows an element of one kind wherever it stands, shadow stages included | `arrivals.js` |
| Utilities | `icons.js`, `markdown.js`, `syntax.js`, `motion.js`, `storage.js`, `interaction-log.js` |

`runtime/rendering.js` runs every rendering callback in one pass per frame. Schedule
through its `nextRender`, `nextFrame`, `cancelRender`, `afterScript`, and
`sizeObserver`; lint refuses the browser's own.

A box that follows page content is placed by CSS (an anchor, a sticky offset, a scroll
timeline), never by a scroll handler, which trails the scroll by a frame. Every write
says only what changed (`runtime/keeps.js`), because while a highlight holds a range
Chrome repaints the whole document on any write; the browser fixture fails a write
that changes nothing (`tests/write_watch.js`). Each place has one writer, since two
owners setting it in turn rewrite it on every paint.

What a page renders and writes depends only on its current inputs. A page nobody
touches writes nothing, requests no frame, and moves no focus; a surface opened and
closed leaves no extra nodes or listeners; a resized page renders at each width what
it rendered there before. So whatever sets a state also clears it when the width or
gesture that called for it ends, and "none" is the attribute's absence, which `keeps`
writes for a null value. `tests/test_render_gate.py` holds each of these over the
corpus.

Stylesheets apply in cascade layers (`layer.py`, `CASCADE_LAYERS`): the theme, package
themes, `/shadow.css`, and widget sheets share `lf-base`, `layouts.css` is
`lf-layouts` above it, and the page's own CSS is unlayered above both. A package's
rules reach only its own widgets (`widget_confinement`), so a rule several packages
need belongs to the kernel. The page's rules skip the chrome and every `.lf-ui`
control unless they name a widget or the layer's vocabulary (`runtime/page-sheets.js`),
so the chrome's root and `.lf-ui` state the whole face they would otherwise inherit.
`runtime/chrome.css` and `runtime/marks.css` are unlayered and adopted last, so they win
by selector; `chrome.css`'s form-control reset alone sits in `lf-reset`, below every
layer that chooses a face.

A `:has()` whose rightmost compound has no class, id, attribute, or type restyles
every element on ordinary runtime writes, so key a repeated type by a class its owner
writes. A `:has()` on the chrome root, `body`, or `html` is read again on every write
below it, so its owner states the condition as an attribute on the element the rule
styles. `test_no_has_rule_restyles_the_whole_document` and
`test_no_has_rule_stands_on_a_root` enforce both.

### One writer for each fact

Each mutable fact has one authority and one browser writer. The application publisher
combines authored state, the admitted server reading, and the ordered ledger of
unresolved local work into the one reading every component selects from:

| Fact | Authority |
| --- | --- |
| authored widget state | validated source markup, staged before upgrade and admitted atomically with descriptors and revision identity |
| external data | the latest page data reading; `watchData` delivers each bound source |
| version shown | the revision the delivery prelude names; a newer revision with the same executable identity patches in place, a different one navigates to a fresh document |
| accepted history | the server event log's `/api/state` answer, adopted whole; each answer has one `through_seq`, and a version comparison asks `/api/view` at the sequence already applied |
| unresolved browser work, refusals included | the publisher's ordered ledger; the server records no refusal, since the condition behind one can change while the user's words stay the same |
| thread, workflow, attention, Asks (answered by `$awaits.answered`), activity, unread | the server's folds, which the browser renders rather than derives; it adds only its own unresolved sends and the versions it is marking read |
| what the DOM represents | controller presentation tickets and projection commits |
| when a document-wide renderer paints | the publication that opened the epoch, in the order `runtime/semantic-state.js` declares |
| where a thread's passage lands | anchor paint's resolution of its anchor in this version |
| the row inside a target a comment was pointed at | `pointed-place.js`; the composer holds it until the send hands it over, and anchor paint's pass is then its one writer |
| what is visible: what a scroller shows, what a surface hides, what sticky headers cover, how much of the window the page shows | `geometry.js` (`visibleBand`, `declareOccluder`, `headerInset`, `shownWindow`, `seenRect`) |

A rendering may expose state, as `data-lf-state` and `data-lf-retired` do for CSS and
render checks, but no code reads it back.

Replacing the document destroys state, and each kind crosses its own way: the patch
keeps a node it did not rewrite, an authored id's state goes through `carry.js`, a
module's own state goes to its store and is read back under the same id, and a walk
restores its position by declared id. A hold, which defers the revision, is only for a
gesture that is not a value: an open composer, a drag, an unresolved delivery, an open
menu.

## Startup and presentation

`leaf.js` boots in this order, each step relying on those before it:

1. Construct every owner, then adopt sheets, attach chrome, mount the owners, and wire
   the repaint phases, so no input is wired before its owner exists.
2. Begin the first state read, without applying its answer.
3. Restore the user's arrangement from storage.
4. Fetch and validate the registry.
5. Capture passage fences, parent identities, and each widget's descriptor and
   authored state from the source DOM, and publish that document once.
6. Import only the modules `x-upgrade` declares for the tags present, run the dressing
   passes, wait for the coordinator's publication, and present the optional
   page-interface region.
7. Land a fresh URL's fragment, then stamp `data-lf-upgraded="1"`.
8. Start the state feed. Its first answer presents the page; after a bounded wait the
   page presents offline and applies the answer when it lands.

Authored HTML paints at once, and the render-blocking theme reserves the banner and
bottom bar, so mounting the runtime moves nothing. Prose, links, and scrolling work
while widgets upgrade. Page keys wait for presentation, since a command reads state
the first answer brings: the bootstrap holds printed keys and the keyboard controller
replays them once the page presents, while any other key or a pointer press drops
them. Durable controls wait for `data-lf-presented` (`../references/packages.md`, "A
theme change"). An async producer joins settlement before `data-lf-upgraded`, or stays
off the presentation path through `afterPresentation`, which `pageReadiness` still
counts. `presentPage` in `leaf.js` is the one transition to stateful interaction, and
its synchronous `PRESENTATION` event lets box-derived apparatus replace provisional
geometry before the presented state paints. A reader outside the page waits on
`pageReadiness` (from Python, `wait_until_ready`) rather than combining stamps.

## The widget vocabulary stays open

Core names a widget only when it is part of how Leaf works (root `AGENTS.md`, "Keep
the layer open"; the merge grains are in `../references/packages.md`, "Package
contract"). Each `x-` key's meaning is its `$keys` entry in `registry.json`. Use a
boolean only when false has one clear meaning; otherwise declare named values.

The Python reader models only transformations the registry declares. A module that
changes text in a way the file cannot reproduce is fenced: browser capture stops at the
fence, so a selection crossing it never becomes a quote the file cannot confirm.
Declare modelable words with `x-says`, `x-paints`, or the content key, and keep a
widget fenced when its transformation cannot be represented.

## Render gates

Run `leaf page check <page> --render`, or the relevant browser test file, after
changing `leaf.js`, a runtime owner, a widget module, the registry, or the theme;
`../scripts/leaf/validation.md`, "Browser validation", lists what it reads. Put a
check on the side that can observe the fact: static validation owns schema, ids,
nesting, passages, event shapes, and file readings; the browser owns computed layout,
composed trees, module writes, focus, and replay idempotence. A test reads widget state
through the publisher's own reading, never a test-only interpretation of it.

The gates judge contracts, not appearance. Prove a change to what the page draws with
before/after screenshots of each state it touches (`uv run leaf-dev stills`;
`/developing-leaf`, "Prove and hand off a visible change").

## Working on the runtime

`tests/runtime/` holds what one module decides on its own (`npm run test:runtime`;
`tests/AGENTS.md` says which readings belong there). `build/browser/build.mjs`
compiles the TypeScript foundation into `vendor/browser-runtime.js` and writes
`vendor/lit.js`, the page's one copy of Lit; `build/AGENTS.md` has the commands.
