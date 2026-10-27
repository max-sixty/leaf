# The page in the browser

This file holds the browser rules that span modules: which runtime code owns each
interface rule, module boundaries, which code owns each fact, and the render gates.
Each module's header owns its local contract, the contracts modules and packages build on are in
`../skills/leaf/references/module-*.md` and `../skills/leaf/references/packages.md`, and the rules shared with
Python are in root `AGENTS.md`, "Cross-runtime invariants".

Stylesheets need no build: page composition and the serving runtime place each file a
sheet `@import`s where the import stands (`stylesheet` in `src/leaf/layer.py`).

## Interface owners

`../skills/leaf/references/interface-principles.md` holds the rules for everything drawn
on a page, with the check that holds each one; the runtime, package widgets and page CSS
all keep them. This table names the runtime code that owns each rule the runtime
carries out, by the rule's bold lead (paths under `runtime/` unless named otherwise).

| Rule                                                          | Owners                                                                                                                                                                                                                                                                              |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Nothing Leaf draws moves the page's content                   | `annotation-overlay/margin-placement.js`; `marginContentLayout` in `prepaint.js` moves the column for the left margin content and sidenotes                                                                                                                                         |
| A necessary scroller works like part of the document          | `reachScrollers` in `reach.js`                                                                                                                                                                                                                                                      |
| The page holds still under the user's aim                     | `travels` on a command's row in `keyboard/bindings.js`                                                                                                                                                                                                                              |
| News never moves what the reader is reading                   | `thread/held-news.js`, `newsMoves` in `thread/thread-card.js`, `threadsListing` in `floating-panel.js` for the rows of Threads, `reading-continuity.js` for a hidden tab; the exception is `fitAnswer` in `floating-panel.js`, credited by `appendGrowth` in `tests/shift_watch.js` |
| A box floating over the page grows inside the window          | `annotation-overlay/comment-placement.js` (attachment and bounds), `thread/card-anchor.js` (what each interaction preserves), `off-flow.js` (a carried box's return), `thread/reply-landing.js` (a field in flow)                                                                   |
| A gesture shows the result the page can draw as it is made    | `standGesture` in `drafts.js` (a send and the refusal that returns its words), `undo.js` (where undo leaves the user)                                                                                                                                                               |
| Typed words stay in their native editor                       | `annotation-overlay/composing/floating-response.js`                                                                                                                                                                                                                                 |
| Editing something keeps it where it stood and as it read      | `thread/message-edit.js`, `.lf-msg-editor` in `styles/components/response.css`, `facesOf` in `composing/text-field.js`, and the insets and `data-lf-gap` in `styles/components/reading.css`                                                                                         |
| Leaf's controls are few, and each shows a symbol              | `icon-paths.js`                                                                                                                                                                                                                                                                     |
| A control wears its role's face                               | `ACTION_FACES` in `prepaint.js`                                                                                                                                                                                                                                                     |
| Animations are restrained and finite                          | the sheen, `@keyframes lf-sheen` in `styles/components/surfaces.css`                                                                                                                                                                                                                |
| Nothing the user must read, press, or decide waits on a clock | `motion.js` (the motion gate, easing and reduced-motion check); `--lf-motion-*` in the theme for the document, and in a runtime surface's own sheet for that surface, as `floating-panel.css` does for the panel                                                                    |

## Runtime ownership

`leaf.js` only boots the page: it imports the owner modules, each of which exports its
capability, and starts them in the order "Startup and presentation" lists. Two classic
scripts run before any module. `runtime/prepaint.js` runs inline in every document,
served or exported, and sets `data-lf-interactive` so the theme gives widgets their
upgraded size. When something the page needs fails, it removes that attribute and names
the reason in `data-lf-startup-error`, and every widget shows its readable fallback.
`runtime/bootstrap.js` runs in a served page only, holds keys pressed before upgrade
and shows a startup failure.

Content modules import only `runtime/widget-api.js`, the public helper surface. Owners
receive their capabilities when constructed and read other owners in their mounts. The
projection, thread and pending models import no DOM or application services.
`.dependency-cruiser.mjs` enforces these boundaries and rejects cycles, so imports use
literal paths; only the widget and interaction loaders compute theirs.

Entry points per concern (paths under `runtime/`; each header owns the details):

| Concern                                                                                                     | Owners                                                                                                                                                   |
| ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Composition and the application's state                                                                     | `application.js`, `semantic-state.js`, `context.js`                                                                                                      |
| Delivery, accepted state, and wakeups                                                                       | `delivery.js`, `state-application.js`, `state-feed.js`, `layer-client.js`, `traffic.js`                                                                  |
| Undo and withdrawal                                                                                         | `undo.js`                                                                                                                                                |
| State models and projection                                                                                 | `projection/`, `thread/model.js`, `thread/workflow.js`, `thread/state.js`, `pending/`, `obligations/model.js`, `queues.js`                               |
| Widget capture and lifecycle                                                                                | `document-identity.js`, `widget-descriptors.js`, `widget-controller.js`, `widget-loader.js`, `widget-upgrade.js`                                         |
| Vocabulary and public helpers                                                                               | `registry.js`, `widget-api.js`, `widget-elements.js`                                                                                                     |
| External data                                                                                               | `data.js`, `projection/data.js`, `projection/authored.js`                                                                                                |
| Revision installs and continuity                                                                            | `version.js`, `version-picker.js`, `carry.js`, `dom-children.js`, `root-state.js`, `restore-state.js`                                                    |
| Repaint and geometry                                                                                        | `rendering.js`, `repaint.js`, `page-geometry.js`, `geometry.js`, `element-frame.js`, `css-anchors.js`, `rect.js`, `pointer.js`                           |
| Chrome and available space                                                                                  | `chrome.js`, `floating-panel.js`, `page-layout.js`, `page-controls.js`                                                                                   |
| Reading regions and scrolling                                                                               | `reading-regions.js`, `reading-place.js`, `bounds.js`, `scrolling.js`, `reach.js`, `user-place.js`                                                       |
| Keyboard                                                                                                    | `keyboard/AGENTS.md`                                                                                                                                     |
| Focus and navigation                                                                                        | `focus.js`, `current-target.js`, `navigation.js`, `queue-walk.js`, `history.js`, `user-intent.js`, `walk-position.js`                                    |
| Obligations                                                                                                 | `obligations/`                                                                                                                                           |
| Comment capture                                                                                             | `composing/`, `drafts.js`, `media.js`                                                                                                                    |
| Threads                                                                                                     | `thread/`                                                                                                                                                |
| Annotation inventory and controls                                                                           | `annotation-inventory.js`, `annotation-view.js`, `contributions.js`, `contribution-controls.js`, `inline-contributions.js`                               |
| Annotation records and Page Map                                                                             | `margin-model.js`, `margin-map-model.js`, `page-map-dialog.js`, `pointed-place.js`                                                                       |
| Pins, marks and floating placement (loaded only when `body` keeps the default `data-annotations="overlay"`) | `annotation-overlay/`                                                                                                                                    |
| Passages and target identity                                                                                | `passages.js`, `kernel-facts.js`, `text-alignment.js`, `anchor-coordinate.js`, `resolved-target.js`, `anchor-resolution.js`, `addressable-names.js`      |
| Anchor placement, decoration and travel                                                                     | `anchor-placement.js`, `anchor-note-view.js`, `anchor-controls.js`, `anchor-travel.js`, `target-paint.js`, `target-paint-geometry.js`, `visual-parts.js` |
| Page status and what a user copies about the page                                                           | `page-status.js`, `page-about.js`, `heading-links.js`                                                                                                    |
| Neighboring pages                                                                                           | `live-leaves.js`                                                                                                                                         |
| Activity and reports                                                                                        | `presence.js`, `activity-words.js`, `reports.js`                                                                                                         |
| Notices, errors and announcements                                                                           | `semantic-news.js`, `notifications.js`, `errors.js`, `keyboard/status-context.js`                                                                        |
| Reactions and design review                                                                                 | `reactions.js`, `design.js`, `design-readings.js`                                                                                                        |
| Presentation and validation                                                                                 | `presentation.js`, `declared-words.js`, `validation.js`, `leaf-element.js`                                                                               |
| Child pages                                                                                                 | `sample*.js`                                                                                                                                             |
| Shadow trees and styles                                                                                     | `shadow.js`, `shadow-stage.js`, `stylesheets.js`                                                                                                         |
| Paint that belongs to an element while it is in the page, whoever added it                                  | `arrivals.js`                                                                                                                                            |
| Utilities                                                                                                   | `abort.js`, `icons.js`, `markdown.js`, `syntax.js`, `motion.js`, `color-scheme.js`, `storage.js`, `interaction-log.js`                                   |

`runtime/rendering.js` runs every rendering callback in one pass per frame. Schedule
through its `nextRender`, `nextFrame`, `cancelRender` and `sizeObserver`; lint refuses
the browser's own. A rendering callback does its layout reads before its writes, since
a read after a write forces a synchronous layout.

A box that follows page content is positioned by CSS, with an anchor, a sticky offset
or a scroll timeline, because a scroll handler trails the scroll by a frame. Paint over
the page's targets goes through `paintSet` in `target-paint-geometry.js`. What a scroll
changes that CSS can't follow is read again when the scroll ends (`watchScrollEnds` in
`arrivals.js`).

Lit owns template bindings and skips unchanged values. For imperative writes outside
those bindings, use `keeps` in `runtime/keeps.js`, whose header says what a redundant
write costs. Give each value one writer, since two owners that set it in turn rewrite
it whenever either paints. Checks: `tests/write_watch.js`
fails a write that changes nothing, and `scroll_findings` in `test_page_fixture_renders` fails a
value a scroll rewrites on every step.

A page's state depends on its present conditions, not on the path that led there.
Resized back to an earlier width, the page shows what it showed at that width; a
surface opened and closed leaves no extra nodes or listeners; a page nobody touches
writes nothing and requests no frames. So whatever sets a state also clears it when the
width or gesture behind it ends, and an absent value is a missing attribute, which
`keeps` writes for `null`. The margin departs from this by design, since a new row fits
around the rows already there (`margin-layout.js`). `test_page_fixture_renders` checks
these rules on every corpus page.

Stylesheets apply in cascade layers, in the order `CASCADE_LAYERS` in `layer.py` declares
(`../skills/leaf/references/packages.md`, "Styles and composition"). A widget package's rules
name the widgets they style, so a rule several packages need belongs in the kernel. Page and theme-package rules reach widget
controls as they reach the page's own; the chrome keeps unlayered page rules up to one
class's weight off itself (`styles/chrome-guard.css`).

A `:has()` rule can turn a local write into a restyle of the whole page or chrome. An
unkeyed rightmost compound widens what it invalidates, and a condition on the chrome
root, `body` or `html` is re-evaluated on writes below it. Prefer a class that names the
targets, or a condition its owner sets on the styled element, and measure with
`leaf-dev profile SOURCE TRANSITION`.

### The browser answers first

A script that recomputes what the browser's layout engine, cascade or focus model
already decides disagrees with it under zoom, subpixel rounding, a transform or the
page's own CSS. Before a module measures, positions, stacks, isolates or tracks
something, find the browser feature that decides it and shape the markup and CSS to
use it:

| Question                                                                   | The browser feature that answers it                                                                 |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| How large a box is, including the widest of several labels                 | grid and flex tracks, `min-content` and `max-content`, labels stacked in one grid cell, `data-room` |
| Where a box sits relative to another box or its scroller                   | the containing block, sticky positioning, anchor positioning, scroll timelines                      |
| Which of Leaf's surfaces paints over which, with the page beneath them all | the top layer, and stacking contexts: the theme's `--lf-z-*` ladder, and `main` as one context at 0 |
| Whether a box is rendered at all                                           | `checkVisibility`                                                                                   |
| Which rules reach an element                                               | cascade layers, `@scope`, and a shadow root as the boundary                                         |

Where a feature nearly fits, change what the runtime asks of it, such as where a box
lives in the DOM. A module that answers one of these questions in script names in its
header the requirement the feature can't meet and the case that shows it, and without
that reason the change doesn't land. The same holds for patching a built-in prototype
or a dependency's internals.

Feature-detect only what a current stable engine lacks, and name that engine beside
the check (`// Firefox lacks ScrollTimeline.`), so the check goes when the engine ships
it. Call an API every engine ships directly, with no fallback, and record remaining
browser gaps in `notes/browser-support.md`.

Two script answers already exist. `focus.js` sets `data-lf-focus` and
`data-lf-focus-within`, because native `:focus` also matches retargeted shadow hosts
and a held label press; those attributes mark the user's current location, and rings are
styled with `data-lf-focus-visible` and `data-lf-focus-visible-within`, which also
follow the browser's focus visibility. `geometry.js` decides whether the user can see a
box (`seenRect`, `declareOccluder`), because Leaf's chrome covers the page without
clipping it.

### One writer for each fact

Each mutable fact has one authority and one writer in the browser. The application
publisher, `applicationState` in `semantic-state.js`, combines authored state, the
server's latest state and this tab's unresolved work into the one state every component
reads (root `AGENTS.md`, "The document starts state; the log changes it"):

| Fact                                                                                                          | Authority                                                                                                                                                                                          |
| ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| authored widget state                                                                                         | the validated source markup, captured before upgrade                                                                                                                                               |
| external data                                                                                                 | the latest page data; Leaf sets each bound source on the widget property x-data names (data.js)                                                                                                    |
| version shown                                                                                                 | the revision the delivery prelude names; a newer revision with the same executable identity patches in place, and a different one loads a fresh document                                           |
| accepted history                                                                                              | the server's event log and its `/api/state` answer, which the publisher adopts whole; each answer has one `through_seq`, and a version comparison asks `/api/view` at the sequence already applied |
| unresolved browser work, refusals included                                                                    | the publisher's one ordered list; the server records no refusal, since the condition behind one can change while the user's words stay the same                                                    |
| threads, workflow, attention, obligations, to-dos, activity, unread                                           | the server's state, which the browser selects without folding again (obligations: `obligations/model.js`); the browser adds only its own unresolved sends and the versions it is marking read      |
| what waits on the user and on the agent                                                                       | the server's `served_state.queues`, which `page state` prints; the publisher adds this tab's sends (`localQueues`)                                                                                 |
| what the DOM shows                                                                                            | the presentation coordinator's renderer tickets and preparation regions                                                                                                                            |
| when a document-wide renderer paints                                                                          | the DOM dependencies `PRESENTATION_DOM` in `runtime/semantic-state.js` declares                                                                                                                    |
| where each thread's passage is                                                                                | `anchor-placement.js`, resolving its anchor in this version                                                                                                                                        |
| the line inside a target that a comment sits by                                                               | `pointed-place.js` (`placePoints`); presentation only                                                                                                                                              |
| the side and line a comment box and its thread card sit by                                                    | `annotation-overlay/comment-placement.js` (`commentSide`)                                                                                                                                          |
| whether a margin row sits in the rail or as a pin, and where                                                  | `annotation-overlay/margin-layout.js`                                                                                                                                                              |
| what a scroller shows, what a surface hides, what sticky headers cover, how much of the window the page shows | `geometry.js` (`visibleBand`, `declareOccluder`, `headerInset`, `shownWindow`, `seenRect`, `motionBand`)                                                                                           |

Add no second cache, pending map, replay list or DOM attribute as another source for
one of these facts. A rendering may expose state, such as `data-lf-state` for CSS and
render checks, but no code reads it back.

When a revision replaces the document, a node the patch didn't rewrite keeps its state,
and `carry.js` carries the value, focus, caret and scroll of an element with an authored
id. A module keeps any other state in its own store under the element's id. Delay the
revision only for a gesture in progress that has no value to carry, such as an open
composer or menu (`version.js`).

### One answer for each question

A question the runtime asks in many places has one owner, which every caller asks,
since a second copy drifts from it at the edges, such as under a stuck header or in a
shadow tree. Before writing or approving a predicate or measurement, look for its
question in "The browser answers first" and then here. A change that creates an owner
adds its row. Rows marked _lint_ are enforced in `eslint.config.mjs`.

| Question                                                                                              | Owner                                                                              |
| ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| What is focused, inside open shadow trees or through a held label press                               | `focus.js` `focused`, `focused(tree)` (_lint_)                                     |
| Whether the user is inside a scope, across shadow trees and slots                                     | `focus.js` `currentLocationIn` (_lint_)                                            |
| The user's working place, read before something borrows it and handed back after                      | `history.js` `readPlace`, `returnPlace`                                            |
| The page place focus or selection identifies, or none                                                 | `current-target.js` `currentLocationOrigin`                                        |
| Where a page walk starts, whether the user is on a stop or at it, and which item it steps to          | `current-target.js` `walkOrigin`, `stepFrom`                                       |
| Which of two nodes the reader reaches first, across shadow trees                                      | `shadow-tree.js` `renderedOrder`, `byRenderedOrder`                                |
| Whether a node is inside another across shadow trees                                                  | `shadow-tree.js` `under`, `renderedUnder`, `composedParentNode`                    |
| Put the user on an element, saying what moved them                                                    | `focus.js` `focusDestination(node, cause)` (_lint_)                                |
| Move a node, keeping the user's place in it                                                           | `dom-move.js` `move(parent, node, before)` (_lint_)                                |
| Make a list of nodes, some already placed, a parent's children                                        | `dom-children.js` `setChildren`                                                    |
| Whether a control takes typed letters                                                                 | `focus.js` `typesText`, `takesLetters`                                             |
| Which keys move a caret, and whether a key is Select All                                              | `control-selectors.js` `CARET_KEYS`, `selectsAll`                                  |
| A hint map's walk and choose rows                                                                     | `keyboard/hints.js` `createHintSession`                                            |
| Which focused control counts as the user's place: shown, and not under a stuck box                    | `user-place.js` `focusedInView`                                                    |
| Whether a click came from the keyboard                                                                | `pointer.js` `pressIsKeyboardActivation`                                           |
| Whether a press is a plain primary-button press with no modifier                                      | `pointer.js` `plainPress`                                                          |
| Which arrow means back along a row, in its text direction                                             | `keyboard/bindings.js` `rowArrows`                                                 |
| Whether any of a node is in front of the user                                                         | `geometry.js` `seenRect`; past top-layer surfaces, `clipsPastSurfaces`             |
| Whether a size change there would move what is seen                                                   | `geometry.js` `growthIsSeen`, `growthAfterIsSeen`                                  |
| When none of some nodes is seen any more                                                              | `geometry.js` `whenNone`                                                           |
| How much of the window the page shows                                                                 | `geometry.js` `shownWindow`                                                        |
| The window's box, less its scrollbars                                                                 | `geometry.js` `layoutWindow`                                                       |
| Whether the page shows a node at all, and what it shows of a sample it holds                          | `geometry.js` `presented`, `frameView`, `watchRoom`                                |
| Whether a box placed against a target belongs in layout yet                                           | `geometry.js` `nearWindow`, `nearObserver`                                         |
| Where an element or Range destination is, and how much of it survives clipping                        | `geometry.js` `placeBox`, `clippedPlace`                                           |
| Whether a box is stuck, and the band sticky headers cover                                             | `geometry.js` `stuckBox`, `headerInset`                                            |
| Whether a box scrolls, for a script or for the user                                                   | `geometry.js` `scrollContainer`, `userScrollport`                                  |
| Which axes a box clips                                                                                | `rect.js` `clippingAxes`                                                           |
| Whether a box is at its scroll end                                                                    | `scrolling.js` `atScrollEnd`, `SCROLL_SLACK`                                       |
| Whether the reader or layout chose a box's scroll position                                            | `scrolling.js` `chosenSince`, `placeKept`                                          |
| The page's `main`                                                                                     | `passages.js` `pageDocument`                                                       |
| The box the page's Layout arranges, and the shell it stands in (its parent)                           | `passages.js` `layoutBox`                                                          |
| Whether a place is already shown, and the space a landing needs                                       | `landing-scroll.js` `alreadyShown`, `landingRoom`                                  |
| Bring something into view without scrolling the page around it, or only inside one box (its `within`) | `landing-scroll.js` `scrollIntoView` (_lint_)                                      |
| Move a box to its end, or by an amount                                                                | `scrolling.js` `scrollToEnd`, `moveScrollerBy` (_lint_)                            |
| Open or close a native modal or popover                                                               | `keyboard/layer-stack.js` `showNativeLayer`, `closeNativeLayer` (_lint_)           |
| Whether a node is, or is inside, an open native layer, and of which kind                              | `shadow-tree.js` `nativeLayerKind`, `isNativeLayer`, `nativeLayerHolding` (_lint_) |
| Which native layers are open, in opening order, and whether a modal admits a node                     | `keyboard/layer-stack.js` `nativeLayers`, `nativeModalAdmits`                      |
| The element a URL fragment names                                                                      | `anchor-resolution.js` `fragmentTarget`                                            |
| The address a heading's link names                                                                    | `heading-links.js` `headingAddress`                                                |
| The language a file path means                                                                        | `syntax.js` `langForPath`, from the registry's `$languages`                        |
| Paint on the next frame, or watch a size                                                              | `rendering.js` `nextRender`, `nextFrame`, `sizeObserver` (_lint_)                  |
| Write a DOM value only when it changed                                                                | `keeps.js` `keeps`                                                                 |
| Threads, workflow, attention, obligations, and whether they are answered                              | the server's state, under "One writer for each fact"                               |
| A workflow's word, and its progress face on a control; an open to-do's word                           | `thread/workflow.js` `workflowLabel`, `progressFace`, `todoLabel`                  |
| A thread's word, which Threads states as its status                                                   | `thread/workflow.js` `threadAttention`                                             |
| What a thread's margin entry and Page Map row say of it: its line, turn and receipt                   | `margin-model.js` `threadMarks`                                                    |
| A thread's name, on every surface that names it                                                       | `thread/messages.js` `threadName` (`threadSummary(thread).topic` for packages)     |
| The thread a name names: its id, a message's, or this tab's attempt                                   | `thread/state.js` `threadNamed`, `threadIdNamed`                                   |
| The thread id a drawn thread carries                                                                  | `thread/selectors.js` `drawnThreadId`                                              |
| The draft a thread holds: its reply box or a rewrite                                                  | `drafts.js` `replyContext`, `rewriteContext`, `threadDraft`                        |
| Which obligations a region of the page holds                                                          | `obligations/place.js` `obligationsIn`                                             |
| What names the part of the page a node stands in: its heading, or a named region                      | `thread/placement.js` `partOver`                                                   |

### Facts both runtimes know

A fact Python and the browser both use, such as an event kind or how a page reads as
text, has one home. Either one runtime owns it and sends it to the other as data, as
the server sends its state in `/api/state`, whose type the build generates from
`served_state/state.schema.json`, or the kernel registry
(`runtime/kernel-registry.json`) declares it and both read the serving Leaf's copy:
the browser imports it as a JSON module through `runtime/kernel-facts.js`, so no build
stands between an edit and either reader. Only a fact the registry can't settle alone
is generated, as `build/vendor.mjs` writes `runtime/syntax-languages.js` from
`$languages` and the grammars it bundles. Where runtime code must spell a value, a
generated type such as `ServedWorkKind` makes a misspelling fail the type check. Where only a literal can carry
the fact, as in a stylesheet's attribute selector, a check holds the spelling to the
declaration (`build/registry.test.mjs`). An algorithm both runtimes run shares a case
file that holds both to the same answers (`tests/*_cases.json`). A parity fixture, or a
test that scans one language's source for the other's names, is the last resort; in
review, ask why that fact isn't generated.

## Startup and presentation

Authored HTML paints at once, and the render-blocking theme reserves the floating
panel's room, so mounting the runtime moves nothing. Prose, links and scrolling work
while widgets upgrade; comments and drawing work from `data-lf-upgraded`.
`../skills/leaf/references/module-authoring.md`, "Startup and presentation", says how a module
keeps work off the presentation path and how held keys replay.

`leaf.js` boots in this order, each step relying on those before it:

1. Construct every owner, then adopt sheets, attach chrome, mount the owners, and
   wire the repaint phases, so no input is wired before its owner exists.
2. Start the first state read, without applying its answer.
3. Restore the user's arrangement from storage.
4. Fetch and validate the registry.
5. Index passage fences and parent ids, then capture each widget's descriptor and
   typed authored state from the source DOM.
6. Publish that document contract once.
7. Import the modules `x-upgrade` declares for the tags present, and no others.
8. Run the dressing passes and wait for the presentation coordinator.
9. Join the page-interface owners' reconciliation (`PAGE_INTERFACE`), separately
   from this document's own presentation check.
10. Land a fresh URL's fragment, prepare chrome that depends on anchors, then set
    `data-lf-upgraded="1"` and open comment capture on the shown document.
11. Start the state feed; its first answer presents the page (`presentPage`). A
    failed or expired read presents the page offline; a request with no answer
    keeps the loading status.

`presentation.js` and `rendering.js` define the readiness stamps. Code outside the page
waits on `pageReadiness`, through `wait_until_ready` in Python, rather than combining
them itself.

## The widget vocabulary stays open

Core names a widget only when it is part of how Leaf works (root `AGENTS.md`, "Keep the
layer open"). Each `x-` key's meaning is its `$keys` entry in `registry.json`. Use a
boolean only when false has one clear meaning; otherwise declare named values.

Python models only the text changes the registry declares. A module that changes text
in a way the file can't reproduce is fenced, and browser capture stops at the fence, so
a selection across it never becomes a quote the file can't confirm. Declare words Python
can model with `x-says` or the content key.

## Render gates

Run `leaf page check <page> --render`, or the relevant browser test file, after
changing `leaf.js`, a runtime owner, a widget module, the registry or the theme
(`../src/leaf/validation.md`, "Browser validation"). Put a check on the side that
can observe the fact: static validation owns schema, ids, nesting, passages, event
shapes and file readings, and the browser owns computed layout, composed trees, module
writes, focus and replay idempotence.

The gates check contracts, not looks. Prove a change to what the page draws with
before/after stills of each state it touches (`/developing-leaf`, "Prove and hand off a
visible change").

## Working on the runtime

Give each component's generated UI one Lit renderer from first paint through live
updates. When changing it, move its existing generated structure and changing bindings
into that renderer together; a Lit child inside a manually updated view leaves two
renderers to maintain. Lit provides node retention, synchronous drawing and
unchanged-value checks. Keep imperative rendering of generated UI only for a requirement
Lit cannot meet, and record that requirement beside the implementation. The rendering
APIs and retained-node operations are in
`../skills/leaf/references/module-authoring.md`,
"Rendering".

A paint that must land in the current turn uses `render`. `LitElement` schedules
updates on a microtask, so code that reads the document right after a paint (a focus
move onto a control just drawn, a measurement, held news) would have to await `updateComplete` and let other work
run first. Use it only for runtime views that can wait. A paint reads state
through `readPart` selectors that return exactly what it draws, so it reruns only when
that answer changes (`semantic-state.js`).

Test what one module decides on its own under `tests/runtime/`
(`pnpm run test:runtime`). The browser framework, `runtime/framework.js` and the
modules behind it, is JavaScript a page runs as written. `pnpm run check:browser`
type-checks the runtime and widget modules, strictly where a module is marked
`// @ts-check`, which the build requires of every framework module; `types/` holds the
check's configuration and the declarations it reads. Declare a new global, event detail or runtime element tag in
`types/runtime-globals.d.ts`.
