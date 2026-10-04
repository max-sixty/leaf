# The page in the browser

This file owns browser-wide contracts: how the page should look and move, module
boundaries, startup, state authority, and the render gates. Each module's header
owns its local contract. Page-authoring rules live in
`../references/page-authoring.md`, module authoring in
`../references/module-authoring.md`, package contracts in `../references/packages.md`,
and rules shared with Python in root `AGENTS.md`, "Cross-runtime invariants".

## Layout and motion

Leaf's current product focus is desktop; judge layout first at a representative
desktop viewport.

### Space and scrolling

The page owns its arrangement: a shipped Layout class (`@layer lf-layouts` in the
theme) or its own CSS. Leaf owns what pages and widgets coordinate through: the
bands, the reading measure as typography, and each widget's contract to fill the box
it is given, declare the minimum it needs, and never let its content size its holder.

Auxiliary runtime controls overlay the page's existing geometry. Adding a control
preserves content position, wrapping, and block size, including when its CSS loads
before first paint. Keep covered content reachable through placement or disclosure
rather than padding or a reserved row.

A margin row sits in the
rail beside its target (`rowPosture`), or as a pin by its target: in room found where
it covers no words and no other box that paints its own extent, clear of neighbouring
blocks where its target has room of its own, and reaching one line of words further
out only where it has none within reach (`pinSpot`, `coverIn`), and otherwise inside
its target's corner. A pin whose face is a primary and one more control that finds no
room for both stands folded to its options' toggle, wearing the face of the kind its
contribution declares, seated at that size where the actions it opens to fit inside its
bounds (`seatRows`); a press on the toggle, or the keyboard arriving on it or standing
at its target, opens it, spreading the actions over what stands beside it with the
toggle left under the press, and moves nothing else.

The rail and a pin are different kinds. The rail is room: a strip right of `main`
that sits wherever the window has room for it. It never moves, narrows, or indents
the column, and `data-rail` on `body` withholds or reserves it (`content-layout.js`).
Only the left resident and the notes move the column over (`settleResidency` there). A pin,
a passage mark, and everything else in the annotation layer is an overlay: it covers
what lies under it and takes no room. No rule pads, indents,
widens, or reflows a block, heading, or line to clear a pin, and nothing moves when a
marker arrives, leaves, or changes place, including a marker that always accompanies
its target, such as an Ask's. Reserved room would make the page's geometry depend on
which markers stand and where, which is what the overlay exists to avoid. Where a pin
covers something the user needs, the answers are `o` (or More's Hide annotations
under a finger) and a better placement (`TODO.md`), never room made for it.

The auxiliary surfaces (Asks drawer, thread panel, Leaves drawer) stand over the page and
never change its geometry; the Asks drawer and panel leave the page live beside
them, and cover it where they would leave less than a usable page
(`--lf-auxiliary-beside`, read by `standsBeside`). Which box scrolls is the
stylesheet's, a Layout's or the page's, which the runtime reads rather than decides.

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
must not move controls next to the gesture that caused it. Without a gesture, a box
may grow or shrink into free room, but reading content and controls stay put.
Runtime regions declare bounded internal reflow with `data-lf-reflow`. A `text`
region, such as a conversation header, declares its own stationary box: labels may
repack inside it while every contained control stays put. A `controls` region,
such as the adaptive shortcut bar, permits its hints and controls to repack inside
its stationary box. Declare the box that owns the available room, rather than an
auto-sized inner label group or a boxless wrapper. A nested region must hold its own
boundary and every enclosing declaration's guarantees; it never borrows an outer
declaration or relaxes one, including across a shadow root. Both painted positions stay inside
that boundary, and neighbours and ordinary page reading content stay put. Typing
still cannot carry its field.
News grows where the reader isn't looking: above the screen, where scroll anchoring
takes the growth into what they scrolled past, or below it. A short thread's reply
box follows its last message; a long panel thread pins the
box at its scroller's foot. News that would move a reply in flow waits behind the
thread's existing notice; a pinned reply lets the transcript grow above it.
Where news would move what the reader is reading, it waits behind a control of fixed size:
in a seat in the page's flow, an agent's reply, the reopening it brings, and a
thread the agent starts wait behind a notice in a row the seat already draws, and a
thread that would open a seat of its own, as on a diff line with no thread, waits in
the margin behind its marker (`thread/held-news.js`). It shows once a gesture of theirs
takes them to it: opening the notice or the thread, walking to the thread or one of its
Asks, or replying there. In the Threads panel, a card
news takes out of the view, as another actor resolving its thread under Open does,
stays where it stands, drawn as the news left it in the shape it stood in, until its
going would move nothing the user sees or they change the view
(`thread/thread-list-view.js`, `keeping`). A region whose rows only the
log or the clock decides, so no first paint can size it, shows none of them until the
reader opens them through a control of fixed size the widget already draws, as a
command's counts open its lists; after that a change to its rows waits the same way
while its growth would be seen (`HeldReading`, command-hub's `lf-command.js`). A
fixed-height box that scrolls them is no answer: nothing tells the reader a row is
cut off, since a scroller shows no edge until it is scrolled.
A change the user requested may reflow the
content it replaces, shown as motion the eye can follow. A hover, focus, or
keyboard reveal never changes the space given to its ancestors or siblings. Typing
may grow its field at the edge its layout grows, but never carries the field. The
suite's browser fixture watches ordinary tests and nightly tests marked `watch_shifts`
for a protected box moving on screen without input, news landing just after a press included,
or typing carrying its field (`tests/shift_watch.js`).

A widget paints its final box before it upgrades. The theme gives each widget, under
`html[data-lf-interactive]`, the size its module will draw it at, so first paint
already has the page's geometry and upgrade adds behavior without moving what follows,
in a served page and an export alike. The
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
does, owns the move back, and both ways it can stop standing run it: the log
refusing it and the user taking it back (`thread/folding.js`). A result only the
log can supply waits with `aria-busy`, painted on a delay so a fast answer shows
nothing. Persistent status text is for a state the user must return to, such as
failure.

### Words stay where they were typed

What the user has typed stays with its native editor until they put it away. A box holding
words closes only in answer to a key or a press that means to close it (Send,
Cancel, Escape, a press elsewhere, another target) or when its subject leaves the
document; a scroll, a resize, a panel, a closed disclosure, a timer, or the server's
news never closes it. Geometry decides where a box stands, never whether: a box
follows its passage through every scrolling ancestor, including out of view,
keeping its words, anchor, and caret. Resume writing (`g i`) reveals that same
editor and its passage. Native CSS attachment carries continuous scroll; target
or field resize invalidates physical placement (`floating-response.js`).
Only where no usable room remains does the presenter withhold the box; its
words and caret remain with its native node (`standFab`, `runtime/composing/surface.js`). A re-render that replaces a box's node hands its
words and caret to the replacement. The suite's browser fixture fails any test
whose page loses typed words without a key or press (`tests/words_watch.js`), and
every corpus page is scrolled to both ends and back with each typed box open
(`test_words_in_a_box_survive_scrolling_away_and_back`).

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
rather than competing with attention for color. Green marks a move the user owes;
other thread controls stay blue. Pickup and work use status words, with one brief
pulse when work begins that a repaint never replays. Reading is bookkeeping and
never moves the user.

### Motion

Use restrained, finite animations to acknowledge state changes. Do not animate
continuously while a state remains unchanged.

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
boot sequence. Two classic scripts run before the first paint, which no module
reaches. `runtime/bootstrap.js` runs in a served page only and loads before everything
else. It marks the page live (`data-lf-live`), so the theme reserves the chrome's room;
it shows a startup failure and waits for a server that can start the page, even if
the module graph never loads; and it holds page keys pressed before presentation.
`runtime/prepaint.js` runs in every document the runtime runs in, served or exported,
ahead of the bootstrap. It marks the root `data-lf-interactive`, so the themes give
each widget its upgraded box, and takes the mark off when the runtime could not start
because something it needs did not arrive (naming why in `data-lf-startup-error`), so
the themes give back the readable fallback for every widget at once; it declares the
page's storage scope;
and it decides which member an `x-views` holder opens on. Content modules import only
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
| Repaint and geometry | `rendering.js`, `repaint.js`, `standing.js`, `page-geometry.js`, `geometry.js`, `rect.js`, `pointer.js` |
| Chrome and available room | `chrome.js`, `chrome-layout.js`, `auxiliary-surfaces.js`, `drawn-edge.js` |
| Reading regions and scrolling | `reading-regions.js`, `reading-place.js`, `bounds.js`, `scrolling.js`, `reach.js`, `user-place.js` |
| Keyboard | `keyboard/AGENTS.md` |
| Focus and navigation | `focus.js`, `standing-target.js`, `navigation.js`, `history.js`, `user-intent.js`, `walk-position.js` |
| Asks | `asks/` |
| Comment capture | `composing/`, `drafts.js`, `media.js` |
| Threads | `thread/`, `thread-panel.js` |
| Annotation inventory and controls | `annotation-inventory.js`, `annotation-view.js`, `contributions.js`, `contribution-controls.js`, `inline-contributions.js` |
| Annotation records and Page Map | `margin-model.js`, `margin-map-model.js`, `page-map-dialog.js`, `pointed-place.js` |
| Physical annotation presentation | `../packages/default/runtime/annotation-overlay/` |
| Passages and target identity | `passages.js`, `text-alignment.js`, `anchor-coordinate.js`, `target-references.js`, `resolved-target.js`, `anchor-resolution.js` |
| Anchor placement, decoration and travel | `anchor-placement.js`, `anchor-note-view.js`, `anchor-controls.js`, `anchor-travel.js`, `target-paint.js`, `target-paint-geometry.js`, `visual-parts.js`, `indication.js` |
| Banner and approvals | `banner*.js` |
| Drawers and neighboring pages | `drawers.js`, `live-leaves*.js` |
| Activity and updates | `presence.js`, `updates.js` |
| Notices and announcements | `semantic-news.js`, `notifications.js`, `keyboard/shortcut-bar.js` |
| Reactions and design review | `reactions.js`, `design.js`, `design-readings.js` |
| Presentation and validation | `presentation.js`, `validation.js`, `projection-watch.js`, `retained-face.js` |
| Child pages and gallery playback | `sample.js`, `interaction-gallery*.js` |
| Shadow trees and styles | `shadow.js`, `shadow-stage.js`, `stylesheets.js` |
| Elements a paint belongs to while they stand, and the stages they stand in | `arrivals.js` |
| Utilities | `icons.js`, `markdown.js`, `syntax.js`, `motion.js`, `color-scheme.js`, `storage.js`, `interaction-log.js` |

The executable body declaration `data-annotations` selects the default physical
renderer or page-owned presentation. `leaf.js` imports the default package's
`runtime/annotation-overlay/index.js` only for overlay presentation; core owners
cannot reach that graph. Core retains target readings, inventory, native controls,
Thread/composer lifetimes and active/draft drawing ink. The selected package owns
pins, contextual floating placement, posted drawing paint, marks and annotation
visibility. Page-owned views consume the same owners through `widget-api.js`.

`runtime/rendering.js` runs every rendering callback in one pass per frame; schedule
through its `nextRender`, `nextFrame`, `cancelRender`, and `sizeObserver`, since
lint refuses the browser's own.

The browser moves what a scroll moves. A box that follows page content stands where
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

What a page says follows from where it stands now, not from how it got there. The one
history its arrangement keeps is the order its margin rows came in, since a row that
arrives yields to those already there rather than moving them (`margin-layout.js`). A page
nobody touches writes nothing, asks for no frame, and moves no focus; a surface opened
and closed again leaves the page as the last time did, holding no more nodes or
listeners; a page resized says at each width what it said there before. So whatever
sets a state also clears it, when the width or the gesture that called for it ends,
and "none" has one spelling, the attribute's absence, which `keeps` writes for a null
value. The corpus holds each rule: `test_a_page_at_rest_does_nothing`,
`test_a_closed_surface_leaves_the_page_as_it_found_it` and
`test_a_resized_page_comes_back_as_it_was`.

Stylesheets apply in layers. `theme.css` holds page tokens, element styles,
idioms, and CSS-only widgets, and each package theme follows it; shared shadow
rules compose into `/shadow.css`, whose shared `.lf-ui` face comes before
component rules. In the document all of these, and each widget module's adopted
sheet, share the `lf-base` cascade layer; `layouts.css` is `lf-layouts` above it,
and `state.css` is `lf-state` above both so semantic retirement wins over package
defaults and Layouts. The page's own CSS stays unlayered above those tiers,
and inline widget motion outranks them (`layer.py`, `CASCADE_LAYERS`). Shared
shadow rules use `lf-shadow` above adopted widget defaults in `lf-base`, and
`state.css` reaches every declared shadow stage above both. Each
package's rules reach only its own widgets (`layer.py`, `widget_confinement`), so a rule
several packages' widgets need is the kernel's. The page's rules skip the chrome and
every `.lf-ui` control unless they name a widget or the layer's vocabulary
(`runtime/page-sheets.js`), and the chrome's root and `.lf-ui` state the whole face they
would otherwise inherit from the page.
`runtime/chrome.css` and `runtime/marks.css` stay unlayered, apart from
`chrome.css`'s form-control reset in `lf-reset`, below every layer that chooses a face.
Their paint lies over the page, so they are adopted after page and package sheets and win by their
selectors. `runtime/marks.css` is adopted by the document and shadow stages. A `:has()` whose rightmost compound carries no class, id, attribute, or
type restyles every element on ordinary runtime writes
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
| where each thread's passage lands | `anchor-placement.js`'s resolution of its anchor in this version |
| the row inside a target a comment stands by | `pointed-place.js`: the line a pointing gesture landed on, held by the composer until sent, then under the thread's key with the words that find it again; where it stands now is `anchor-placement.js`'s placement record (`point`, `pointRow`), written in its read, the only writer, which takes in what a send hands over; presentation only, and only the pointed threads' row, card and travel follow it |
| the side and line a comment's box and its thread card stand by, and which edge a growing one holds | the default package's `comment-placement.js` (`commentSide`, `holding`), for both surfaces; each surface's own module measures its content and reports its gestures, and decides neither |
| whether a margin row stands in the rail or as a pin, its seat, and the order rows are seated in | `margin-layout.js`, through `margin-placement.js`'s folds (`rowPosture`, `seatRows`, `packRows`, `arrivals`) |
| geometry readings: what a scroller shows, what a surface hides, what sticky headers stand over, how much of the window the page shows | `geometry.js` (`visibleBand`, `declareOccluder`, `headerInset`, `shownWindow`, `seenRect`), so being on screen has one answer |

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
9. Join optional runtime-owned page-interface imports and installation. Their contained
   sample documents are deferred arrivals, separate from this document's semantic proof.
10. Land a fresh URL's fragment, then stamp `data-lf-upgraded="1"`.
11. Start the state feed; its first answer presents the page, or after a bounded
    wait the page presents offline and applies the answer when it lands.

Authored HTML paints immediately, and the render-blocking theme reserves the
banner and bottom bar so mounting the runtime moves nothing. Prose, links, and
scrolling work while widgets upgrade. Page keys wait, because a command reads
state the first answer brings: the bootstrap holds printed keys pressed before
presentation and the keyboard controller replays them in order once the page
presents, while any other key or a pointer press drops the held run. Durable
controls wait for `data-lf-presented` (`../references/module-authoring.md`, "Startup and presentation"). An async
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

`leaf page check <page> --render` is the browser contract: both color schemes,
the runtime's actual readiness and motion boundary, screen and print, and
reapplied standing state. Run it, or the relevant browser test file, after
changing `leaf.js`, a runtime owner, a widget module, the registry, or the theme.
`leaf/render-checks/index.js` exports one probe per failure class, invoked by
`leaf/render_checks.py` and composed by `leaf/render_gate/`:

| Reading | Contract |
| --- | --- |
| window-error channel | no runtime, module, resource, or ResizeObserver error reached the page |
| `issueNode` | a DevTools issue outside a form control's shadow tree is the page's, placed at its frame if it has one |
| `upgraded`, `moving` | upgrade completed and geometry settled |
| `invalidPaints` | every var()-backed SVG paint resolves in each scheme |
| `tinyBoxes` | every declared widget has a usable box |
| `unmarkableElements` | every addressable element has a visible part to outline |
| `misplacedBoxes` | boxes stay in the column or in reachable overflow at every width |
| `squeezedTables` | a table scrolls sideways only with every column at its longest unbreakable run |
| `strandedMargins` | every margin marker has an element to stand by |
| `clippedControls` | controls are visible and reachable |
| `unreachableWords`, `coveredWords` | visible words stay in reachable flow and are not silently clipped or claimed by chrome |
| `unreadSyntax` | highlighting does not alter source words |
| `shownVerbatim` | preserving owners agree with their projected passage |
| `silentWords` | `x-says` and `x-paints` promises reach the rendered page |
| `undeclaredAttrs` | modules write no undeclared author-namespace state |
| `retiredSlots` | settlement marks agree with the projection |
| `trappedMargins`, `splitEdges` | suite only: the theme's frame trim reaches Leaf's own boxes |
| `replayOverrides` | the log, not conflicting markup, determines projected state |
| `relativeReplays` | rendering a complete widget state twice changes nothing |
| `shrunkLabels` | advice only |

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
