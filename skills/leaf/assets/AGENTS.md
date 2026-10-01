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

Nothing Leaf draws at run time moves the page's content. A margin row takes one of
two postures (`rowPosture`): in the rail beside its target, or as a pin over the page
by its target. A pin's first choice is its seat, just after the end of its target's
run of text or inside the top-right corner of its target's block, wherever the seat
covers no words and no other box that paints its own extent (`pinSpot`, `coverIn`).
Otherwise it takes the nearest room that covers none of them, preferring room that
touches its target to room on a neighbouring block, and reaching one line of words
further out only where it finds neither within reach. Where it finds no such room, it
sits inside its target's top-right corner (`seatRows`).

A pin that can fold, one whose face is a primary and one more control, folds to its
options' toggle where it finds no room for both. The toggle shows the marker face of
the kind its contribution declares, and is seated only where the pin's opened width
fits to its left within its bounds (`seatRows`). A press on the toggle, or the
keyboard arriving on it or standing at its target, opens it: the actions spread over
what lies beside it, the toggle stays under the press, and nothing else moves.

The rail and a pin are different kinds. The rail is room: a strip right of `main`
that sits wherever the window has room for it. It never moves, narrows, or indents
the column, and `data-rail` on `body` withholds or reserves it (`margin-layout.js`).
Only the left resident and the notes move the column over (`settleResidency`). A pin,
a passage mark, and everything else in the annotation layer is an overlay: it covers
what lies under it and takes no room. No rule pads, indents,
widens, or reflows a block, heading, or line to clear a pin, and nothing moves when a
marker arrives, leaves, or changes place, including a marker that always accompanies
its target, such as an Ask's. Reserved room would make the page's geometry depend on
which markers are shown and where, which is what the overlay exists to avoid. Where a pin
covers something the user needs, the answers are `o` (or More's Hide annotations
under a finger) and a better placement (`TODO.md`), never room made for it.

The auxiliary surfaces (Asks drawer, thread panel, Leaves drawer) lie over the page and
never change its geometry; the Asks drawer and panel leave the page live beside
them, and cover it where they would leave less than a usable page
(`--lf-auxiliary-beside`, read by `standsBeside`). The stylesheet, a Layout's or the
page's, decides which box scrolls, and the runtime reads the result.

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
must not move controls next to the gesture that caused it. News causes no layout
shift: when a box's content changes without a gesture, that box may grow or shrink
into free room, but no other element moves. So a thread's reply box stands at the
foot of the scroller that shows the thread, in the Threads panel as in the margin card,
and a reply grows the thread above it without moving the box or its caret. A change
the user requested may reflow the content it replaces, shown as motion the eye can
follow. A hover, focus, or
keyboard reveal never changes the space given to its ancestors or siblings. Typing
may grow its field at the edge its layout grows, but never carries the field. The
suite's browser fixture fails any test outside the nightly selection whose page makes a
layout shift Chrome reports without recent input, or whose typing carries its field
(`tests/shift_watch.js`).

A widget paints its final box before it upgrades. The theme gives each widget, under
`html[data-lf-live]`, the size its module will draw it at, so first paint already has
the page's geometry and upgrade adds behavior without moving what follows. The
widget quality check `keeps-first-box` measures each widget's box at first paint and
once the page presents (`leaf package check PACKAGE --render`,
`scripts/leaf/render_gate/widget_quality.py`); the suite runs it over every bundled
package and fails on a change `tests/known_widget_findings.py` does not list.

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
announcement for a listener. A gesture that moves the user, as settling a thread
does, owns the move back, which runs both when the log refuses the gesture and when
the user undoes it (`thread/folding.js`). A result only the
log can supply waits with `aria-busy`, painted on a delay so a fast answer shows
nothing. Persistent status text is for a state the user must return to, such as
failure.

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
uses the same two cues in blue. Reading is bookkeeping and never moves the user.

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
| Vocabulary and public helpers | `registry.js`, `widget-api.js`, `widget-elements.js` |
| External data | `data.js`, `projection/data.js`, `projection/authored.js` |
| Revision installs and continuity | `version.js`, `version-picker.js`, `carry.js`, `dom-children.js`, `root-state.js`, `restore-state.js` |
| Repaint and geometry | `rendering.js`, `repaint.js`, `standing.js`, `page-geometry.js`, `geometry.js`, `rect.js`, `pointer.js`, `floating.js` |
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
| Shadow trees and styles | `shadow.js`, `shadow-stage.js`, `stylesheets.js` |
| Paint that belongs to an element while it is in the page, and the shadow stages it may be in | `arrivals.js` |
| Utilities | `icons.js`, `markdown.js`, `syntax.js`, `motion.js`, `storage.js`, `interaction-log.js` |

`runtime/rendering.js` runs every rendering callback in one pass per frame; schedule
through its `nextRender`, `nextFrame`, `cancelRender`, and `sizeObserver`, since
lint refuses the browser's own.

The browser moves what a scroll moves. A box that follows page content sits where
CSS puts it, by an anchor, a sticky offset, or a scroll timeline, and no scroll handler
writes its position, which would trail the scroll by a frame. Every write says only
what changed (`runtime/keeps.js`): while a highlight holds a range, Chrome repaints the
whole document for any write, so a write per scroll event makes every page with a
quoted comment judder. One place has one writer: two owners that each set it in turn
rewrite it every time either paints. A paint that more than one step of a script asks
for waits for the script to end (`rendering.js`, `afterScript`), rather than painting
the step between. The browser fixture fails a write that changes
nothing in any test (`tests/write_watch.js`), and
`test_a_scroll_writes_only_what_it_changes` fails a place a scroll writes on every step.

What a page renders and writes depends only on its current inputs. A page nobody
touches writes nothing, asks for no frame, and moves no focus; a surface opened and
closed again leaves the page as the last time did, holding no more nodes or listeners;
a resized page renders at each width what it rendered there before. So whatever sets a
state also clears it, when the width or the gesture that called for it ends, and
"none" has one spelling, the attribute's absence, which `keeps` writes for a null
value. The corpus holds each rule: `test_a_page_at_rest_does_nothing`,
`test_a_closed_surface_leaves_the_page_as_it_found_it` and
`test_a_resized_page_comes_back_as_it_was`.

Stylesheets apply in layers. `theme.css` holds page tokens, element styles,
idioms, and CSS-only widgets, and each package theme follows it; shared shadow
rules compose into `/shadow.css`, whose shared `.lf-ui` face comes before
component rules. In the document all of these, and each widget module's adopted
sheet, share the `lf-base` cascade layer; `layouts.css` is `lf-layouts` above it,
and the page's own CSS is unlayered above both (`layer.py`, `CASCADE_LAYERS`). Each
package's rules reach only its own widgets (`layer.py`, `widget_confinement`), so a rule
several packages' widgets need is the kernel's. The page's rules skip the chrome and
every `.lf-ui` control unless they name a widget or the layer's vocabulary
(`runtime/page-sheets.js`), and the chrome's root and `.lf-ui` state the whole face they
would otherwise inherit from the page.
`runtime/chrome.css` and `runtime/marks.css` stay unlayered, apart from
`chrome.css`'s form-control reset in `lf-reset`, below every layer that chooses a face.
Their paint lies over the page, so they are adopted after page and package sheets and
win by their selectors. `runtime/marks.css` is adopted by the document and shadow
stages.

A `:has()` whose rightmost compound carries no class, id, attribute, or type restyles
every element on ordinary runtime writes
(`test_no_has_rule_restyles_the_whole_document`); key a repeated type by a class
its owner writes. A `:has()` on the chrome root, `body` or `html` is read again on
every write below it and restyles it (`test_no_has_rule_stands_on_a_root`), so the
owner of such a condition states it as an attribute on the element the rule styles.

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
| the row inside a target a comment sits by | `pointed-place.js`: the line a pointing gesture landed on, held by the composer until sent, then under the thread's key with the words that find it again; where it sits now is anchor paint's placement record (`point`, `pointRow`), written in its pass, the only writer, which takes in what a send hands over; presentation only, and only the pointed threads' row, card and travel follow it |
| geometry readings: what a scroller shows, what a surface hides, what sticky headers cover, how much of the window the page shows | `geometry.js` (`visibleBand`, `declareOccluder`, `headerInset`, `shownWindow`, `seenRect`), so being on screen has one answer |

Do not add a second cache, pending map, widget-specific replay list, or DOM
attribute as another source for one of these facts; a rendering may expose state,
but no caller reads it back. `data-lf-state` and `data-lf-retired` are output for
CSS and render checks only.

Each kind of state that replacing the document would destroy has its own way across
(root `AGENTS.md`, "The document starts state; the log changes it", says why). The
patch keeps a node it did not rewrite; an authored id gets `carry.js`'s carry; a
module's own state is written to its store and read back under the same id; a walk
restores its standing by declared id. A hold, which defers the revision, is for a
gesture that is not a value: an open composer, a drag, an unresolved delivery, an open
menu.

## Startup and presentation

Startup order is load-bearing:

1. Construct the application, page commands, and UI owners in `leaf.js`; every
   owner exists before the first input is wired, then sheets are adopted, chrome
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
banner and bottom bar so mounting the runtime moves nothing. Prose, links, and
scrolling work while widgets upgrade. Page keys wait, because a command reads
state the first answer brings: the bootstrap holds printed keys pressed before
presentation and the keyboard controller replays them in order once the page
presents, while any other key or a pointer press drops the held run. Durable
controls wait for `data-lf-presented` (`../references/packages.md`, "A theme change"). An async
producer joins settlement before `data-lf-upgraded`, or stays off the
presentation path through `afterPresentation`, which declares the deferred
arrival so `pageReadiness` still answers for it. `presentPage` owns the one
transition to stateful interaction; its synchronous `PRESENTATION` signal lets
box-derived apparatus replace provisional geometry before the presented state
paints. A reader outside the page waits on `pageReadiness`, through
`wait_until_ready` in Python, rather than combining these stamps.
`renderingSettled` in `runtime/rendering.js` is its last stage and also a live
reading of its own: whether chrome has caught up with input since.

## Authoritative projection

Python owns the durable Ask and thread projections, including whether an Ask is
answered (the registry's `$awaits.answered`); root `AGENTS.md`, "The document starts
state; the log changes it", states what the browser adds to them and how far each
widget's projection reaches. The server ships page and thread Asks as
`document.asks` and the thread's `asks`, and each thread's `attention` (`needs_user`
or `waiting`) as the one reading of whose turn it is. Every state read has one
`through_seq`, and version comparison asks `/api/view` at the sequence already
applied. `restated` and answered reports persist through version notes, so silence
in a later version does not revive retracted state. The server keeps no refusal
receipts, because the condition behind a refusal can change without the user's words
changing.

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

`leaf page check <page> --render` is the browser contract: both color schemes at a
1200×900 and a 540×720 viewport, a sweep of widths from 360px to 1920px for the
sideways readings, the runtime's actual readiness and motion boundary, and reapplied
standing state. Run it, or the relevant browser
test file, after changing `leaf.js`, a runtime owner, a widget module, the registry,
or the theme. `../scripts/leaf/validation.md`, "Browser validation", lists its
readings and the contract each one holds.

Put a check on the side that can observe the fact: static validation owns schema,
ids, nesting, passages, event shapes, and file readings; the browser owns computed
layout, composed trees, module writes, focus, and replay idempotence.
Readings of widget state use the publisher's own reading; never write a test-only
interpretation of it.

The gates judge contracts, not how the page looks. A change to what the page
draws, including one made for geometry, is proved with before/after screenshots
of each state it touches. `uv run leaf-dev stills` takes them for a catalogue of
states and crops the ones that changed (`/developing-leaf`, "Prove and hand off a
visible change").

## Working on the runtime

`build/browser/build.mjs` compiles the TypeScript foundation into
`vendor/browser-runtime.js` and writes `vendor/lit.js`, the page's one copy of Lit
(`build/AGENTS.md` owns the commands). What a module decides on its own is
tested under `tests/runtime/` (`npm run test:runtime`; `tests/AGENTS.md` says
which readings may go there).
