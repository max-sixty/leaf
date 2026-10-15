# The page in the browser

This file holds the browser rules that span modules: how pages look and move, module
boundaries, which code owns each fact, and the render gates. Each module's header owns
its local contract. Page authors read `../references/page-authoring.md`, module authors
`../references/module-*.md`, and package authors `../references/packages.md`. Rules
shared with Python are in root `AGENTS.md`, "Cross-runtime invariants".

Edit stylesheet sources, never the generated sheets: `styles/components/`,
`styles/shadow.css` (which composes them into the sheet the document and every shadow
root load), `styles/theme.css` and `styles/chrome.css`. `build/AGENTS.md`, “Committed
bundles”, rebuilds `theme.css`, `shadow.css` and `runtime/chrome.css` from them.

## Layout and motion

These rules hold on every page and for everything Leaf draws on one; each names its
check and owners where they exist. Leaf targets desktop first, so judge layout at a
representative desktop viewport.

### Space and scrolling

- **The page owns its arrangement.** A page arranges itself with a shipped Layout
  class (`layouts.css`, `@layer lf-layouts`) or its own CSS. Leaf owns only what pages
  and widgets share: the bands, the reading measure a Layout sets, and each widget's
  duty to fill the box it gets, declare its minimum, and never widen its container.
- **A Layout, a style and a widget never read one another.** A Layout sets where boxes
  go and how large they are. A style (`theme.css`) sets type, spacing and form as tokens
  under a class such as `density-working`. A widget reads only its own box and the
  theme's tokens, so it behaves the same in a shipped Layout as on a hand-written page
  that gives it the same box. Where one must react to another, the owner sets a token
  describing the box and the reader matches it with a style query, as with
  `--lf-full-height`, `--lf-wide-page`, `--lf-resident` and `--lf-density`
  (`layouts.css` and `theme.css` define them). A width needs no token: a size query on the reader's
  container answers it. Before adding a token, ask whether a hand-written page with the
  same box would want the same answer; if not, the token describes a Layout, not a box.
  Check: `test_layout_style_and_widgets_never_read_each_other`.
- **Nothing Leaf draws moves the page's content.** Pins, passage marks, runtime
  controls and the rest of the annotation layer sit over the page and take no space, so
  every block keeps its position, wrapping and size when one appears or moves. No rule
  pads or widens a block to make room for a pin. A pin sits by its target, over the
  target's words when no spot beside it is clear. The rail sits right of `main` when
  the window is wide enough, and never moves or narrows the column
  (`content-layout.js`); `data-rail` on `body` withholds or reserves it
  (`../references/page-layout.md`, "The rail and the margin"). Otherwise only the left
  margin resident and sidenotes move the column, through `residency` in
  `prepaint.js`. Checks: `test_a_comment_leaves_its_block_as_the_page_wrote_it` and the
  shift watch. Owner: `annotation-overlay/margin-placement.js`.
- **Auxiliary surfaces open over the page and never change its geometry.** The On
  panel, the thread panel and the Pages drawer take no space from the page;
  `auxiliary-surfaces.js` decides whether one sits beside a live page or covers it
  (`standsBeside`). The Threads panel is being redesigned (`TODO.md`, "Reconsider
  thread navigation"): put findings about it into that redesign rather than polishing
  the current panel.
- **A widget in ordinary flow grows with its content.** A widget scrolls inside itself
  only when its task needs a region kept in view while its contents move, or for a
  live stream whose newest entry the reader follows. A box that keeps its own height
  declares `--lf-holds-height: 1`. Check: the widget quality check
  `grows-with-content` (`scripts/leaf/render_gate/widget_quality.py`), run on every
  corpus page.
- **A necessary scroller works like part of the document.** It passes scrolling on to
  the document at its edges, except at a bounded task or a modal. Wheel and touch keep
  moving through content; pan and zoom need a deliberate control. It has a keyboard
  route, visible bounds and visible focus: `reachScrollers` in `runtime/reach.js` gives
  every box a mouse can scroll a tab stop and paints the edge its content continues
  past. An object taken out of flow for inspection restores the selection and the
  document position on return. Checks: the reach tests in the browser suite and the axe
  sweep; `/ui-sweep` reviews scroll chaining and the return from inspection.

### Stability

- **The page holds still under the user's aim.** A state change may repaint any box,
  but must not move the controls next to the gesture that caused it. Without a gesture,
  a box may grow or shrink into free room, but reading content and controls stay put. A change
  the user asked for may reflow the content it replaces, with motion the eye can
  follow. Revealing something on hover, focus or a key never changes the size or
  position of its ancestors or siblings, and typing may grow a field but never moves it. Check:
  `tests/shift_watch.js`, which the browser fixture runs on every test outside a
  module marked `shifts_unsurveyed` (`tests/AGENTS.md`, "Browser errors").
- **A runtime region whose contents rearrange inside it declares `data-lf-reflow`.**
  The message header declares `text`: its labels may rewrap, its controls stay put. The
  shortcut bar declares `controls`: hints and controls may rearrange. A thread card's
  transcript declares `append`: it may grow at its end, by new messages or by a last
  child marked `data-lf-append-tail` such as the working message, and only the reply
  row and later cards move with that growth. When the growth would push a reply row the
  user just sent below its landing band, the transcript scrolls instead
  (`sendLanding` in `thread/reply-landing.js`). Put the attribute on the box that owns
  the space. A nested region keeps every guarantee of the regions around it. Owners: `thread/thread-card.js`, `thread/messages.js`,
  `keyboard/shortcut-bar.js`.
- **News never moves what the reader is reading.** News from the server grows above
  the screen, where scroll anchoring absorbs it, or below it. Anywhere else it waits
  behind a fixed-size control until the reader goes to it, and an editor in use stays
  still. Check: `test_news_just_after_a_press_moves_nothing`. Owners:
  `thread/held-news.js`, which also holds widget rows (`HeldReading`) and boxes a late
  arrival would resize (`heldGrowth`); `newsMoves` in `thread/thread-card.js`;
  `thread/thread-list.js` for the Threads panel's reading place; `keeping` in
  `thread/thread-list-view.js` for a card news would take out of view; and
  `reading-continuity.js` for a hidden tab. One exception, which the user chose: the
  answer the user waits for in the floating panel's thread grows that view up to its
  cap, its head rising while the field stays put (`floating-panel.js`, `fitAnswer`).
  The shift watch credits exactly that growth: a scrollport declared to stand on its
  foot (`data-lf-rises`) that rises with its `append` region's growth, by no more than
  it, carrying its head (`appendGrowth` in `tests/shift_watch.js`).
- **A turn of the user's own takes them with it.** When the user's reply or Reopen
  moves its card out of the Threads panel's current filter, the panel widens its view
  to keep the thread and the user together. If the server refuses, the view goes back
  only if the user hasn't acted since (`thread/folding.js`).
- **A box floating over the page grows inside the window.** The comment box and the
  thread card grow toward the window edge that has room, and never scroll the page to
  make room (`annotation-overlay/comment-placement.js`). A box a scroll carried away
  comes back when the user types into it (`off-flow.js`). Only a field in flow
  scrolls to keep its controls in view (`thread/reply-landing.js`).
- **A widget paints its final box before it upgrades.** The theme sizes each widget
  under `html[data-lf-interactive]` as its module will draw it
  (`../references/module-authoring.md`, "First paint"). Check: the widget quality check
  `keeps-first-box`, which fails on any finding `tests/known_widget_findings.py`
  doesn't list.
- **Generated interface appears in its final position.** Reserve space before a
  generated control appears. Feedback may repaint a control or change its label, but
  never its size: `data-lf-room` (`controls.css`) sizes a label to the widest of the
  words it can show. A parent laying out adjacent actions keeps their hit areas apart.
- **An unlikely event fits into what is already there.** Reserve no space for a state
  the user rarely meets, such as a failed save. Show it in a surface already on screen,
  and let the user's gesture expand it: `lf-file-editor.js` reports a file conflict in
  its status line and opens the two versions only on Compare.
- **A gesture shows the result the page can draw as it is made** (root `AGENTS.md`,
  "The document starts state; the log changes it"). `standGesture` in `drafts.js`
  handles a send and the refusal that returns the words to their box. The new content
  and its Undo confirm success, so success needs no notice beyond the announcement
  for a listener. A gesture that moves the
  user, such as resolving a thread, moves them back when it is refused or undone
  (`thread/folding.js`). A result only the log can supply waits with `aria-busy`, shown
  after a delay so a fast answer shows nothing. Persistent status text is for a
  state the user must return to, such as a failure.

### Words stay where they were typed

- **Typed words stay in their native editor until the user puts them away.** A box
  holding words closes only on a key or press meant to close it (Send, Cancel, Escape,
  a press elsewhere, another target) or when its subject leaves the document; a scroll,
  resize, timer or server news never closes it. Geometry decides where the box
  sits, never whether it exists: it follows its passage through
  scrolling ancestors, out of view too, and Resume writing (`g i`) shows the same
  editor. A re-render that replaces the box's node hands its words and caret to the
  replacement. Checks: `tests/words_watch.js`, which fails any test whose page loses
  typed words without a key or press, and `typed_box_findings` in the render gate tests.
  Owner: `annotation-overlay/composing/floating-response.js`.

### Visual grammar

- **Visual treatments carry hierarchy and state.** Contours are solid. A dotted or
  dashed line marks a distinct state, such as a draft or a drag placeholder. One
  contour shows one control state, and a segmented group shares one-pixel seams. Avoid
  rounded one-sided borders and reflexive cards, tints, gradients and soft shadows.
- **Each thread's `unread` and `attention` are computed once**, and every surface that
  paints them uses that value, so the Threads toggle, filters, panel, margin entry and
  Page Map change together. Green marks the user's turn; other thread controls stay
  blue. Marking read never moves the user.

### Motion

- **Animations are restrained and finite, and acknowledge state changes.** The one
  continuous animation is the sheen, `@keyframes lf-sheen` in
  `styles/components/surfaces.css`, which marks agent work in progress, such as a
  thread's working message. It stops when the work ends and is static under reduced
  motion.
- **Nothing the user must read, press, or decide waits on a clock.** Motion the user
  waits on stays under 300ms. A delay may hide a flicker but never adds a minimum
  spinner time or a staged reveal. `runtime/motion.js` owns the shared motion gate,
  easing and reduced-motion check, and the theme's `--lf-motion-*` properties set durations.

## Runtime ownership

`leaf.js` only boots the page: each owner is a module that exports its capability, and
`leaf.js` imports the owners and starts them in the order "Startup and presentation"
lists below. Two classic scripts run before any module. `runtime/prepaint.js` runs
inline in every document, served or exported, and sets `data-lf-interactive` so the
theme gives widgets their upgraded size. When something the page needs doesn't
arrive, or the page declares a failure, it removes that attribute and names the reason in `data-lf-startup-error`, and every widget shows its
readable fallback. `runtime/bootstrap.js` runs in a served page only: it sets
`data-lf-live`, holds keys pressed before upgrade, and shows a startup failure.

Content modules import only `runtime/widget-api.js`, the public helper surface. Owners
receive their capabilities when constructed and read other owners in their mounts. Pure
projection, thread and pending models import no DOM or application services.
`.dependency-cruiser.mjs` enforces these boundaries and rejects cycles, so imports use
literal paths; only the widget and interaction loaders compute theirs.

Entry points per concern (paths under `runtime/`; each header owns the details):

| Concern | Owners |
| --- | --- |
| Composition and the application's state | `application.js`, `semantic-state.js`, `context.js` |
| Delivery, accepted state, and wakeups | `delivery.js`, `state-application.js`, `state-feed.js`, `layer-client.js`, `traffic.js` |
| Undo and withdrawal | `undo.js` |
| State models and projection | `projection/`, `thread/model.js`, `thread/workflow.js`, `thread/state.js`, `pending/`, `asks/model.js`, `queues.js` |
| Widget capture and lifecycle | `document-identity.js`, `widget-descriptors.js`, `widget-controller.js`, `widget-loader.js`, `widget-upgrade.js` |
| Vocabulary and public helpers | `registry.js`, `widget-api.js`, `widget-elements.js` |
| External data | `data.js`, `projection/data.js`, `projection/authored.js` |
| Revision installs and continuity | `version.js`, `version-picker.js`, `carry.js`, `dom-children.js`, `root-state.js`, `restore-state.js` |
| Repaint and geometry | `rendering.js`, `repaint.js`, `page-geometry.js`, `geometry.js`, `element-frame.js`, `css-anchors.js`, `rect.js`, `pointer.js` |
| Chrome and available space | `chrome.js`, `chrome-layout.js`, `auxiliary-surfaces.js`, `drawn-edge.js` |
| Reading regions and scrolling | `reading-regions.js`, `reading-place.js`, `bounds.js`, `scrolling.js`, `reach.js`, `user-place.js` |
| Keyboard | `keyboard/AGENTS.md` |
| Focus and navigation | `focus.js`, `standing-target.js`, `navigation.js`, `queue-walk.js`, `history.js`, `user-intent.js`, `walk-position.js` |
| Asks | `asks/` |
| Comment capture | `composing/`, `drafts.js`, `media.js` |
| Threads | `thread/`, `thread-panel.js` |
| Annotation inventory and controls | `annotation-inventory.js`, `annotation-view.js`, `contributions.js`, `contribution-controls.js`, `inline-contributions.js` |
| Annotation records and Page Map | `margin-model.js`, `margin-map-model.js`, `page-map-dialog.js`, `pointed-place.js` |
| Pins, marks and floating placement (loaded only when `body` keeps the default `data-annotations="overlay"`) | `annotation-overlay/` |
| Passages and target identity | `passages.js`, `passage-facts.js`, `text-alignment.js`, `anchor-coordinate.js`, `resolved-target.js`, `anchor-resolution.js`, `addressable-names.js` |
| Anchor placement, decoration and travel | `anchor-placement.js`, `anchor-note-view.js`, `anchor-controls.js`, `anchor-travel.js`, `target-paint.js`, `target-paint-geometry.js`, `visual-parts.js`, `indication.js` |
| Banner and approvals | `banner*.js` |
| Drawers and neighboring pages | `drawers.js`, `queue-panel.js`, `queue-list.js`, `live-leaves*.js` |
| Activity and reports | `presence.js`, `activity-words.js`, `reports.js` |
| Notices and announcements | `semantic-news.js`, `notifications.js`, `keyboard/shortcut-bar.js` |
| Reactions and design review | `reactions.js`, `design.js`, `design-readings.js` |
| Presentation and validation | `presentation.js`, `declared-words.js`, `validation.js`, `projection-watch.js`, `retained-face.js` |
| Child pages | `sample*.js` |
| Shadow trees and styles | `shadow.js`, `shadow-stage.js`, `stylesheets.js`, `page-sheets.js` |
| Paint that belongs to an element while it is in the page, whoever added it | `arrivals.js` |
| Utilities | `abort.js`, `icons.js`, `markdown.js`, `syntax.js`, `motion.js`, `color-scheme.js`, `storage.js`, `interaction-log.js` |

`runtime/rendering.js` runs every rendering callback in one pass per frame. Schedule
through its `nextRender`, `nextFrame`, `cancelRender` and `sizeObserver`; lint refuses
the browser's own.

CSS positions a box that follows page content, with an anchor, a sticky offset or a
scroll timeline, because a scroll handler would trail the scroll by a frame. Paint over
the page's targets goes through `paintSet` in `target-paint-geometry.js`. Anything a
scroll changes that CSS can't follow, such as which hint chips `keyboard/hints.js`
shows, is read again when the scroll ends (`watchScrollEnds` in `arrivals.js`).

Write a DOM value only when it changes, through `keeps` in `runtime/keeps.js`. While a
CSS highlight marks a quoted comment, Chrome repaints the whole document on any write,
so a write per scroll event makes the page judder. Give each value one writer, since
two owners that set it in turn rewrite it whenever either paints. When several steps of
one script ask for the same paint, `afterScript` in `rendering.js` runs it once after
the script. Checks: `tests/write_watch.js` fails a write that changes nothing, and
`scroll_findings` in `test_page_fixture_renders` fails a value a scroll rewrites on
every step.

A page's state depends on its present conditions, not on the path that led there.
Resized back to an earlier width, the page shows what it showed at that width; a surface
opened and closed leaves no extra nodes or listeners; a page nobody touches writes
nothing and requests no frames. So whatever sets a state also clears it when the width
or gesture behind it ends, and an absent value is a missing attribute, which `keeps`
writes for `null`. The margin is the one exception, by design: a new row fits around
the rows already there rather than moving them (`margin-layout.js`).
`test_page_fixture_renders` checks these rules on every corpus page.

Stylesheets apply in cascade layers, in the order `CASCADE_LAYERS` in `layer.py`
declares (`../references/packages.md`, "Styles and composition"). Each widget package's
rules reach only its own widgets (`widget_confinement` in `layer.py`), so a rule several
packages need belongs in the kernel. Page and theme-package rules skip the chrome and
every `.lf-ui` control unless they name a widget or the layer's vocabulary
(`runtime/page-sheets.js`).
`runtime/stylesheets.js` says which sheets the document and shadow roots adopt.

A `:has()` rule restyles far more than it means to in two shapes. When its rightmost
compound has no class, id, attribute or type, every runtime write restyles every
element (`test_no_has_rule_restyles_the_whole_document`); key it by a class its owner
writes. When it sits on the chrome root, `body` or `html`, every write below re-evaluates
it (`test_no_has_rule_stands_on_a_root`); have the condition's owner set an attribute
on the styled element instead.

### The browser answers first

Every page already runs a layout engine, a cascade and a focus model. A script that
recomputes one of their answers disagrees with them under zoom, subpixel rounding, a
transform or the page's own CSS. Before a module measures, positions, stacks, isolates
or tracks something, find the browser feature that decides it and shape the markup and
CSS to use it:

| Question | The browser feature that answers it |
| --- | --- |
| How large a box is, including the widest of several labels | grid and flex tracks, `min-content` and `max-content`, labels stacked in one grid cell, `data-lf-room` |
| Where a box sits relative to another box or its scroller | the containing block, sticky positioning, anchor positioning, scroll timelines |
| Which of Leaf's surfaces paints over which, with the page beneath them all | the top layer, and stacking contexts: the theme's `--lf-z-*` ladder, and `main` as one context at 0 |
| Whether a box is rendered at all | `checkVisibility` |
| Which rules reach an element | cascade layers, `@scope`, and a shadow root as the boundary |

Where a feature nearly fits, change what the runtime asks of it, such as where a box
lives in the DOM, rather than computing the answer. A module that answers one of these
questions in script names in its header the requirement the feature can't meet and the
case that shows it; without that reason, the change doesn't land. The same holds for
patching a built-in prototype or a dependency's internals.

Two script answers already exist. `focus.js` sets `data-lf-focus` and
`data-lf-focus-within`, because native `:focus` also matches retargeted shadow hosts
and a held label press; style focus with those attributes. `geometry.js` decides
whether the user can see a box (`seenRect`, `declareOccluder`), because Leaf's chrome
covers the page without clipping it and the shortcut bar takes no pointer hits for
`elementsFromPoint` to find.

A rendering callback does its layout reads before its writes, because a read after a
write forces a synchronous layout. A document-wide renderer that reads DOM another
renderer creates takes an entry in `PRESENTATION_ORDER` (`runtime/semantic-state.js`),
which says why CSS can't supply that reading.

### One writer for each fact

Each mutable fact has one authority and one writer in the browser. The application
publisher (`application.js`) combines authored state, the server's latest state and
the ordered list of this tab's unresolved work into the one state every component reads:

| Fact | Authority |
| --- | --- |
| authored widget state | the validated source markup, captured before upgrade |
| external data | the latest page data; a widget reads each bound source through `this.data` (data.js) |
| version shown | the revision the delivery prelude names; a newer revision with the same executable identity patches in place, and a different one loads a fresh document |
| accepted history | the server's event log and its `/api/state` answer, which the publisher adopts whole |
| unresolved browser work | the publisher's one ordered list |
| threads, workflow, attention, asks, to-dos, activity, unread | the server's state; the browser adds only its own unresolved sends and the versions it is marking read |
| what waits on the user and on the agent | the server's `served_state.queues`, which `page state` prints; the publisher adds this tab's sends (`localQueues`) |
| what the DOM shows | the presentation coordinator's renderer tickets and preparation regions |
| when a document-wide renderer paints | the order `PRESENTATION_ORDER` in `runtime/semantic-state.js` declares |
| where each thread's passage is | `anchor-placement.js`, resolving its anchor in this version |
| the line inside a target that a comment sits by | `pointed-place.js` (`placePoints`); presentation only |
| the side and line a comment box and its thread card sit by | `annotation-overlay/comment-placement.js` (`commentSide`) |
| whether a margin row sits in the rail or as a pin, and where | `annotation-overlay/margin-layout.js` |
| what a scroller shows, what a surface hides, what sticky headers cover, how much of the window the page shows | `geometry.js` (`visibleBand`, `declareOccluder`, `headerInset`, `shownWindow`, `seenRect`, `motionBand`) |

Add no second cache, pending map, replay list or DOM attribute as another source for
one of these facts. A rendering may expose state, such as `data-lf-state` and
`data-lf-retired` for CSS and render checks, but no code reads it back.

When a revision replaces the document, user state survives by its kind. A node the
patch didn't rewrite keeps its state. An element with an authored id gets its value,
focus, caret and scroll carried by `carry.js`. A module writes its own state to its
store and reads it back under the same id. Delaying the revision is only for a gesture
in progress that has no value to carry, such as an open composer or an open menu
(`version.js`).

### One answer for each question

A question the runtime asks in many places has one owner, which every caller asks. A
second copy usually starts where a symptom appeared and its author didn't find the
first, then drifts at the edges: under a stuck header, in a shadow tree, in
right-to-left text. Before writing or approving a predicate or measurement, look for its
question in "The browser answers first" and then here. A change that creates an owner
adds its row. Rows marked *lint* are enforced in `eslint.config.mjs`.

| Question | Owner |
| --- | --- |
| What is focused, inside open shadow trees or through a held label press | `focus.js` `focused`, `focused(tree)` (*lint*) |
| Whether the user is inside a scope, across shadow trees and slots | `focus.js` `standingIn` (*lint*) |
| The user's working place, read before something borrows it and handed back after | `history.js` `readPlace`, `returnPlace` |
| Where a page walk starts, and which item it steps to | `standing-target.js` `walkOrigin`, `stepFrom` |
| Which of two nodes the reader reaches first, across shadow trees | `shadow-tree.js` `renderedOrder`, `byRenderedOrder` |
| Whether a node is inside another across shadow trees | `shadow-tree.js` `under`, `renderedUnder`, `composedParentNode` |
| Put the user on an element, saying what moved them | `focus.js` `focusDestination(node, cause)` (*lint*) |
| Move a node, keeping the user's place in it | `dom-move.js` `move(parent, node, before)` (*lint*) |
| Make a list of nodes, some already placed, a parent's children | `dom-children.js` `setChildren` |
| Whether a control takes typed letters | `focus.js` `typesText`, `takesLetters` |
| Which keys move a caret, and whether a key is Select All | `control-selectors.js` `CARET_KEYS`, `selectsAll` |
| A hint map's walk and choose rows | `keyboard/hints.js` `createHintSession` |
| Which focused control counts as the user's place: shown, and not under a stuck box | `user-place.js` `focusedInView` |
| Whether a click came from the keyboard | `pointer.js` `pressIsKeyboardActivation` |
| Whether a press is a plain primary-button press with no modifier | `pointer.js` `plainPress` |
| Which arrow means back along a row, in its text direction | `keyboard/bindings.js` `rowArrows` |
| Whether any of a node is in front of the user | `geometry.js` `seenRect`; past top-layer surfaces, `clipsPastSurfaces` |
| Whether a size change there would move what is seen | `geometry.js` `motionBand`, `growthIsSeen`, `growthAfterIsSeen` |
| When none of some nodes is seen any more | `geometry.js` `whenNone` |
| How much of the window the page shows | `geometry.js` `shownWindow` |
| The window's box, less its scrollbars | `geometry.js` `layoutWindow` |
| Whether the page shows a node at all, and what the pages holding it show of its window | `geometry.js` `presented`, `containingView`, `frameView`, `watchRoom` |
| Whether a box placed against a target belongs in layout yet | `geometry.js` `nearWindow`, `nearObserver` |
| Where an element or Range destination is, and how much of it survives clipping | `geometry.js` `placeBox`, `clippedPlace` |
| Whether a box is stuck, and the band sticky headers cover | `geometry.js` `stuckBox`, `headerInset` |
| Whether a box scrolls, for a script or for the user | `geometry.js` `scrollContainer`, `scrollport`, `userScrollport` |
| Which axes a box clips | `rect.js` `clippingAxes` |
| Whether a box is at its scroll end | `scrolling.js` `atScrollEnd`, `SCROLL_SLACK` |
| Whether the reader or layout chose a box's scroll position | `scrolling.js` `chosenSince`, `placeKept` |
| The page's `main` | `passages.js` `pageDocument` |
| Whether a place is already shown, and the space a landing needs | `landing-scroll.js` `alreadyShown`, `landingRoom` |
| Bring something into view without scrolling the page around it | `landing-scroll.js` `scrollIntoView` (*lint*) |
| Open or close a native modal or popover | `keyboard/layer-stack.js` `showNativeLayer`, `closeNativeLayer` (*lint*) |
| Whether a node is, or is inside, an open native layer, and of which kind | `shadow-tree.js` `nativeLayerKind`, `isNativeLayer`, `nativeLayerHolding` (*lint*) |
| Which native layers are open, in opening order, and whether a modal admits a node | `keyboard/layer-stack.js` `nativeLayers`, `nativeModalAdmits` |
| The element a URL fragment names | `anchor-resolution.js` `fragmentTarget` |
| The language a file path means | `syntax.js` `langForPath`, from the registry's `$languages` |
| Paint on the next frame, or watch a size | `rendering.js` `nextRender`, `nextFrame`, `sizeObserver` (*lint*) |
| Write a DOM value only when it changed | `keeps.js` `keeps` |
| Threads, workflow, attention, asks, and whether they are answered | the server's state, under "One writer for each fact" |
| Which asks a region of the page holds | `asks/place.js` `asksIn` |

### Facts both runtimes know

A fact Python and the browser both use, such as an event kind or the languages a page
can highlight, has one home. Either one language owns it and sends it to the other as
data, as the server sends its state in `/api/state`, or the registry declares it and
the browser's copy is generated, as `build/registry.mjs` writes
`runtime/syntax-languages.js` from `$languages`. A parity fixture, or a test that scans
one language's source for the other's names, keeps two copies in step instead; in
review, ask why that fact isn't generated.

## Startup and presentation

Authored HTML paints at once, and the render-blocking theme reserves the banner and
bottom bar, so mounting the runtime moves nothing. Prose, links and scrolling work while
widgets upgrade; comments and drawing work from `data-lf-upgraded`, while thread
history still shows as loading. `../references/module-authoring.md`, "Startup and
presentation", says how a module keeps work off the presentation path and how held
keys replay.

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

`presentPage` performs the first authoritative presentation; its synchronous
`PRESENTATION` signal lets apparatus measured from boxes replace provisional
geometry before the presented state paints. `renderingState` (rendering.js) adds
readiness's last stage: `updatesSettled` says the chrome has caught up with queued
work, and `preparationsSettled` that registered finite preparations have landed.
Full readiness needs both; a reader inspecting intermediate paint can use the
first alone. Code outside the page waits on `pageReadiness`, through
`wait_until_ready` in Python, rather than combining these stamps itself.

## Authoritative projection

Python decides which asks exist, when a widget is complete, and when a thread is
answered. The server sends complete ask lists for the page (`document.asks`) and for
each thread's frozen markup (`thread.asks`). The browser reads a widget's answer from
the same state its controls draw and doesn't reapply the `x-awaits.answered` rule. A
required-version approval is an ask the browser updates at once, restoring the server's
state on refusal. A thread gesture changes no attention and no ask until the server's
reading of it arrives (root `AGENTS.md`, "Responsiveness").

Every state read carries one `through_seq`, and version comparison asks `/api/view` at
the sequence already applied. A page widget's projection stops at the current revision;
a widget in frozen thread markup reads the whole log. The server records no refusals,
because the condition behind one can change while the user's words stay the same.

## The widget vocabulary stays open

Core names a widget only when it is part of how Leaf works (root `AGENTS.md`, "Keep the
layer open"). Each `x-` key's meaning is its `$keys` entry in `registry.json`. Use a
boolean only when false has one clear meaning; otherwise declare named values.

Python models only the text changes the registry declares. A module that changes text
in a way the file can't reproduce is fenced: browser capture stops at the fence, so a
selection across it never becomes a quote the file can't confirm. Declare words Python
can model with `x-says` or the content key.

## Render gates

Run `leaf page check <page> --render`, or the relevant browser test file, after
changing `leaf.js`, a runtime owner, a widget module, the registry or the theme
(`../scripts/leaf/validation.md`, "Browser validation"). Put a check on the side that
can observe the fact: static validation owns schema, ids, nesting, passages, event
shapes and file readings; the browser owns computed layout, composed trees, module
writes, focus and replay idempotence.

The gates check contracts, not looks. Prove a change to what the page draws with
before/after screenshots of each state it touches, from `uv run leaf-dev stills`
(`/developing-leaf`, "Prove and hand off a visible change").

## Working on the runtime

A paint that must land in the current turn uses `render`; `LitElement` schedules
updates on a microtask and suits only runtime views that can wait that long.

A watcher's paint subscribes to every selection it reads (`projection-watch.js`), so a
reader called from a paint selects exactly what it returns (`readPart`) rather than
selecting more and narrowing it. The paint then reruns only when that answer changes.
Reading the whole root inside a paint throws.

Test what one module decides on its own under `tests/runtime/` (`pnpm run
test:runtime`). `pnpm run check:browser` type-checks the runtime and widget modules,
strictly where a module is marked `// @ts-check`; `build/AGENTS.md` owns the framework
build. A new global, event detail or runtime element tag is declared in
`build/browser/runtime-globals.d.ts`.
