# The page in the browser

Authored browser framework TypeScript and its module tests live in `framework/`;
`build/browser/` owns the tools that compile it to the generated `vendor/` payload.

This file holds the browser rules that span modules: how pages look and move, module
boundaries, which code owns each fact, and the render gates. Each module's header owns
its local contract. Page authors read `../skills/leaf/references/page-authoring.md`, module authors
`../skills/leaf/references/module-*.md`, and package authors `../skills/leaf/references/packages.md`. Rules
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
  `--lf-full-height`, `--lf-wide-page`, `--lf-margin-content` and `--lf-density`
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
  (`../skills/leaf/references/page-layout.md`, "The rail and the margin"). Otherwise only the left
  margin content and sidenotes move the column, through `marginContentLayout` in
  `prepaint.js`. Checks: `test_a_comment_leaves_its_block_as_the_page_wrote_it` and the
  shift watch. Owner: `annotation-overlay/margin-placement.js`.
- **A control takes only its own room.** Leaf never reserves a strip, a row or
  full-width padding to seat one small control. The control joins a line that is
  already there, such as a head, the line over a field or a row's end, or a corner its
  content leaves free. The floating panel's more-room mark stands in the corner a long
  draft leaves free over the leaf (`floating-panel.js`, `expand`) rather than in a strip
  of its own over the words.
- **The chrome opens over the page and never changes its geometry.** The floating
  panel and the views it opens take no space from the page; the theme keeps the room
  its row rests in at the page's foot (`--lf-foot-room`, theme.css).
- **A widget in ordinary flow grows with its content.** A widget scrolls inside itself
  only when its task needs a region kept in view while its contents move, or for a
  live stream whose newest entry the reader follows. A box that keeps its own height
  declares `--lf-holds-height: 1`. Check: the widget quality check
  `grows-with-content` (`src/leaf/render_gate/widget_quality.py`), run on every
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
  The message header declares `text`: its labels may rewrap, its controls stay put. A
  thread card's transcript declares `append`: it may grow at its end, by new messages or by a last
  child marked `data-lf-append-tail` such as the working message, growing or giving way
  to the answer that takes its place, and only the reply
  row and later cards move with that growth. When the growth would push a reply row the
  user just sent below its landing band, the transcript scrolls instead
  (`sendLanding` in `thread/reply-landing.js`). Put the attribute on the box that owns
  the space. A nested region keeps every guarantee of the regions around it. Owners:
  `thread/thread-card.js`, `thread/messages.js`.
- **News never moves what the reader is reading.** News from the server grows above
  the screen, where scroll anchoring absorbs it, or below it. Anywhere else it waits
  behind a fixed-size control until the reader goes to it, and an editor in use stays
  still. Check: `test_news_just_after_a_press_moves_nothing`. Owners:
  `thread/held-news.js`, which also holds widget rows (`HeldReading`) and boxes a late
  arrival would resize (`heldGrowth`); `newsMoves` in `thread/thread-card.js`; and
  `reading-continuity.js` for a hidden tab. One exception, which the user chose: the
  answer the user waits for in the floating panel's thread grows that view up to its
  cap, its top edge and its name rising while its controls and the field stay put
  (`floating-panel.js`, `fitAnswer`). The shift watch credits exactly that growth: a
  scrollport declared to stand on its foot (`data-lf-rises`) that rises with its
  `append` region's growth, by no more than it, carrying its name
  (`appendGrowth` in `tests/shift_watch.js`).
- **A box floating over the page grows inside the window.** The comment box and the
  thread card grow toward the window edge that has room, and never scroll the page to
  make room (`annotation-overlay/comment-placement.js`). A box a scroll carried away
  comes back when the user types into it (`off-flow.js`). Only a field in flow
  scrolls to keep its controls in view (`thread/reply-landing.js`).
- **A widget paints its final box before it upgrades.** The theme sizes each widget
  under `html[data-lf-interactive]` as its module will draw it
  (`../skills/leaf/references/module-authoring.md`, "First paint"). Check: the widget quality check
  `keeps-first-box`, which fails on any finding `tests/known_widget_findings.py`
  doesn't list.
- **Generated interface appears in its final position.** Hold room before first paint
  only for what will be drawn, such as a widget's upgraded controls. Feedback may
  repaint a control or change its label, but never its size: `data-room`
  (`controls.css`) sizes a label to the widest of the words it can show. A parent
  laying out adjacent actions keeps their hit areas apart.
- **What may appear fits into what is already there.** Hold no empty room for a state
  that may never come, however likely: a failed save, a rewrite the user hasn't opened.
  Show it in a slot already on screen, as a message's head carries its delivery and its
  Edit beside the author, and let the user's gesture make the room it needs:
  `lf-file-editor.js` reports a file conflict in its status line and opens the two
  versions only on Compare, and a rewrite grows its message only once opened.
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
  contour shows one control state, and a segmented group shares one-pixel seams. Never
  round a box edged on one side: mark a state with a whole contour, or a stripe on a
  square box. Avoid reflexive cards, tints, gradients and soft shadows. Check:
  `test_no_rule_rounds_a_box_edged_on_one_side`, over Leaf's sheets and pages.
- **A face used twice is a token or a shared rule**, and a rule names it rather than
  spelling it out. A lift names one of the theme's three heights, `--raise-1` to
  `--raise-3` (`styles/theme.css`, beside `--shade`); boxes that wear one face, such as
  the chip a focused comment note and picture proxy show at the window's head, share one rule.
  Check: `test_every_lift_names_one_of_the_theme_s_heights_cast_in_the_scheme_s_ink`.
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

| Concern                                                                                                     | Owners                                                                                                                                                                    |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Composition and the application's state                                                                     | `application.js`, `semantic-state.js`, `context.js`                                                                                                                       |
| Delivery, accepted state, and wakeups                                                                       | `delivery.js`, `state-application.js`, `state-feed.js`, `layer-client.js`, `traffic.js`                                                                                   |
| Undo and withdrawal                                                                                         | `undo.js`                                                                                                                                                                 |
| State models and projection                                                                                 | `projection/`, `thread/model.js`, `thread/workflow.js`, `thread/state.js`, `pending/`, `obligations/model.js`, `queues.js`                                                |
| Widget capture and lifecycle                                                                                | `document-identity.js`, `widget-descriptors.js`, `widget-controller.js`, `widget-loader.js`, `widget-upgrade.js`                                                          |
| Vocabulary and public helpers                                                                               | `registry.js`, `widget-api.js`, `widget-elements.js`                                                                                                                      |
| External data                                                                                               | `data.js`, `projection/data.js`, `projection/authored.js`                                                                                                                 |
| Revision installs and continuity                                                                            | `version.js`, `version-picker.js`, `carry.js`, `dom-children.js`, `root-state.js`, `restore-state.js`                                                                     |
| Repaint and geometry                                                                                        | `rendering.js`, `repaint.js`, `page-geometry.js`, `geometry.js`, `element-frame.js`, `css-anchors.js`, `rect.js`, `pointer.js`                                            |
| Chrome and available space                                                                                  | `chrome.js`, `floating-panel.js`, `page-layout.js`, `page-controls.js`                                                                                                    |
| Reading regions and scrolling                                                                               | `reading-regions.js`, `reading-place.js`, `bounds.js`, `scrolling.js`, `reach.js`, `user-place.js`                                                                        |
| Keyboard                                                                                                    | `keyboard/AGENTS.md`                                                                                                                                                      |
| Focus and navigation                                                                                        | `focus.js`, `current-target.js`, `navigation.js`, `queue-walk.js`, `history.js`, `user-intent.js`, `walk-position.js`                                                     |
| Obligations                                                                                                 | `obligations/`                                                                                                                                                            |
| Comment capture                                                                                             | `composing/`, `drafts.js`, `media.js`                                                                                                                                     |
| Threads                                                                                                     | `thread/`                                                                                                                                                                 |
| Annotation inventory and controls                                                                           | `annotation-inventory.js`, `annotation-view.js`, `contributions.js`, `contribution-controls.js`, `inline-contributions.js`                                                |
| Annotation records and Page Map                                                                             | `margin-model.js`, `margin-map-model.js`, `page-map-dialog.js`, `pointed-place.js`                                                                                        |
| Pins, marks and floating placement (loaded only when `body` keeps the default `data-annotations="overlay"`) | `annotation-overlay/`                                                                                                                                                     |
| Passages and target identity                                                                                | `passages.js`, `passage-facts.js`, `text-alignment.js`, `anchor-coordinate.js`, `resolved-target.js`, `anchor-resolution.js`, `addressable-names.js`                      |
| Anchor placement, decoration and travel                                                                     | `anchor-placement.js`, `anchor-note-view.js`, `anchor-controls.js`, `anchor-travel.js`, `target-paint.js`, `target-paint-geometry.js`, `visual-parts.js`, `indication.js` |
| Page status and what a user copies about the page                                                           | `page-status.js`, `page-about.js`                                                                                                                                         |
| Neighboring pages                                                                                           | `live-leaves.js`                                                                                                                                                          |
| Activity and reports                                                                                        | `presence.js`, `activity-words.js`, `reports.js`                                                                                                                          |
| Notices, errors and announcements                                                                           | `semantic-news.js`, `notifications.js`, `errors.js`, `keyboard/status-context.js`                                                                                         |
| Reactions and design review                                                                                 | `reactions.js`, `design.js`, `design-readings.js`                                                                                                                         |
| Presentation and validation                                                                                 | `presentation.js`, `declared-words.js`, `validation.js`, `leaf-element.js`                                                                                                |
| Child pages                                                                                                 | `sample*.js`                                                                                                                                                              |
| Shadow trees and styles                                                                                     | `shadow.js`, `shadow-stage.js`, `stylesheets.js`, `page-sheets.js`                                                                                                        |
| Paint that belongs to an element while it is in the page, whoever added it                                  | `arrivals.js`                                                                                                                                                             |
| Utilities                                                                                                   | `abort.js`, `icons.js`, `markdown.js`, `syntax.js`, `motion.js`, `color-scheme.js`, `storage.js`, `interaction-log.js`                                                    |

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
declares (`../skills/leaf/references/packages.md`, "Styles and composition"). Each widget package's
rules reach only its own widgets (`widget_confinement` in `layer.py`), so a rule several
packages need belongs in the kernel. Page and theme-package rules skip the chrome and
every `.lf-ui` control. A page stylesheet explicitly marked `data-controls` or
a theme package's `controls.css` grants access (`runtime/page-sheets.js`).
`runtime/stylesheets.js` says which sheets the document and shadow roots adopt.

A `:has()` rule can make a local write invalidate a whole page or the chrome.
An unkeyed rightmost compound can widen the invalidation targets; a condition on the
chrome root, `body` or `html` can be re-evaluated on writes below it. Prefer a class
that names the targets or a condition its owner sets on the styled element.
Confirm the cost in the browser: `leaf-dev profile SOURCE TRANSITION` reports
forced style recalculations, their element counts, and style invalidations with
the writes that caused them.

### The browser answers first

Every page already runs a layout engine, a cascade and a focus model. A script that
recomputes one of their answers disagrees with them under zoom, subpixel rounding, a
transform or the page's own CSS. Before a module measures, positions, stacks, isolates
or tracks something, find the browser feature that decides it and shape the markup and
CSS to use it:

| Question                                                                   | The browser feature that answers it                                                                 |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| How large a box is, including the widest of several labels                 | grid and flex tracks, `min-content` and `max-content`, labels stacked in one grid cell, `data-room` |
| Where a box sits relative to another box or its scroller                   | the containing block, sticky positioning, anchor positioning, scroll timelines                      |
| Which of Leaf's surfaces paints over which, with the page beneath them all | the top layer, and stacking contexts: the theme's `--lf-z-*` ladder, and `main` as one context at 0 |
| Whether a box is rendered at all                                           | `checkVisibility`                                                                                   |
| Which rules reach an element                                               | cascade layers, `@scope`, and a shadow root as the boundary                                         |

Where a feature nearly fits, change what the runtime asks of it, such as where a box
lives in the DOM, rather than computing the answer. A module that answers one of these
questions in script names in its header the requirement the feature can't meet and the
case that shows it; without that reason, the change doesn't land. The same holds for
patching a built-in prototype or a dependency's internals.

Feature-detect only what a current stable engine lacks, and name that engine beside
the check (`// Firefox lacks ScrollTimeline.`), so the check goes when the engine ships
it. Call an API every engine ships directly, with no fallback, and record the check in
`notes/browser-support.md`.

Two script answers already exist. `focus.js` sets `data-lf-focus` and
`data-lf-focus-within`, because native `:focus` also matches retargeted shadow hosts
and a held label press. Those attributes express current location; style rings with
`data-lf-focus-visible` and `data-lf-focus-visible-within`, which also account for
the browser's focus visibility. `geometry.js` decides
whether the user can see a box (`seenRect`, `declareOccluder`), because Leaf's chrome
covers the page without clipping it.

A rendering callback does its layout reads before its writes, because a read after a
write forces a synchronous layout. A document-wide renderer that reads DOM another
renderer creates takes an entry in `PRESENTATION_ORDER` (`runtime/semantic-state.js`),
which says why CSS can't supply that reading.

### One writer for each fact

Each mutable fact has one authority and one writer in the browser. The application
publisher (`application.js`) combines authored state, the server's latest state and
the ordered list of this tab's unresolved work into the one state every component reads:

| Fact                                                                                                          | Authority                                                                                                                                                |
| ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| authored widget state                                                                                         | the validated source markup, captured before upgrade                                                                                                     |
| external data                                                                                                 | the latest page data; a widget reads each bound source through `this.data` (data.js)                                                                     |
| version shown                                                                                                 | the revision the delivery prelude names; a newer revision with the same executable identity patches in place, and a different one loads a fresh document |
| accepted history                                                                                              | the server's event log and its `/api/state` answer, which the publisher adopts whole                                                                     |
| unresolved browser work                                                                                       | the publisher's one ordered list                                                                                                                         |
| threads, workflow, attention, obligations, to-dos, activity, unread                                           | the server's state; the browser adds only its own unresolved sends and the versions it is marking read                                                   |
| what waits on the user and on the agent                                                                       | the server's `served_state.queues`, which `page state` prints; the publisher adds this tab's sends (`localQueues`)                                       |
| what the DOM shows                                                                                            | the presentation coordinator's renderer tickets and preparation regions                                                                                  |
| when a document-wide renderer paints                                                                          | the order `PRESENTATION_ORDER` in `runtime/semantic-state.js` declares                                                                                   |
| where each thread's passage is                                                                                | `anchor-placement.js`, resolving its anchor in this version                                                                                              |
| the line inside a target that a comment sits by                                                               | `pointed-place.js` (`placePoints`); presentation only                                                                                                    |
| the side and line a comment box and its thread card sit by                                                    | `annotation-overlay/comment-placement.js` (`commentSide`)                                                                                                |
| whether a margin row sits in the rail or as a pin, and where                                                  | `annotation-overlay/margin-layout.js`                                                                                                                    |
| what a scroller shows, what a surface hides, what sticky headers cover, how much of the window the page shows | `geometry.js` (`visibleBand`, `declareOccluder`, `headerInset`, `shownWindow`, `seenRect`, `motionBand`)                                                 |

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
adds its row. Rows marked _lint_ are enforced in `eslint.config.mjs`.

| Question                                                                                              | Owner                                                                              |
| ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| What is focused, inside open shadow trees or through a held label press                               | `focus.js` `focused`, `focused(tree)` (_lint_)                                     |
| Whether the user is inside a scope, across shadow trees and slots                                     | `focus.js` `currentLocationIn` (_lint_)                                            |
| The user's working place, read before something borrows it and handed back after                      | `history.js` `readPlace`, `returnPlace`                                            |
| The page place focus or selection identifies, or none                                                 | `current-target.js` `currentLocationOrigin`                                        |
| Where a page walk starts, falling back to visible reading, and which item it steps to                 | `current-target.js` `walkOrigin`, `stepFrom`                                       |
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

### Facts both runtimes know

A fact Python and the browser both use, such as an event kind or the languages a page
can highlight, has one home. Either one language owns it and sends it to the other as
data, as the server sends its state in `/api/state`, whose type the build generates
from `served_state/state.schema.json`, or the registry declares it and the browser's
copy is generated, as `build/registry.mjs` writes `runtime/syntax-languages.js` from
`$languages`. Where runtime code must spell a value, as a comparison does, a generated
type makes a spelling the declaration lacks fail the type check, as `ServedWorkKind`
and `AuthoredAllocations` do. Where only a literal can carry the fact, as a
stylesheet's attribute selector spells a mark's paint or Python's markup names an
attribute the runtime reads, a check holds the spelling to the declaration or to the
other runtime's spelling (`build/registry.test.mjs`). An algorithm both runtimes run
can't be generated, so a shared case file holds both to the same answers
(`tests/*_cases.json`). Anywhere else, a parity fixture, or a test that scans one
language's source for the other's names, keeps two copies in step instead; in review,
ask why that fact isn't generated.

## Startup and presentation

Authored HTML paints at once, and the render-blocking theme reserves the floating
panel's room at the page's foot, so mounting the runtime moves nothing. Prose, links
and scrolling work while widgets upgrade; comments and drawing work from
`data-lf-upgraded`, while thread history still shows as loading. `../skills/leaf/references/module-authoring.md`, "Startup and
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

Python decides which obligations exist, when a widget is complete, and when a thread is
answered. Each view carries every obligation record once, the page's and its frozen threads'
(`obligations`); a row of On me names its obligation by id, and the publisher joins the two. The
browser reads a widget's answer from
the same state its controls draw and doesn't reapply the `x-awaits.answered` rule. A
thread gesture changes no attention and no obligation until the server's reading of it arrives (root `AGENTS.md`, "Responsiveness").

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
(`../src/leaf/validation.md`, "Browser validation"). Put a check on the side that
can observe the fact: static validation owns schema, ids, nesting, passages, event
shapes and file readings; the browser owns computed layout, composed trees, module
writes, focus and replay idempotence.

The gates check contracts, not looks. Prove a change to what the page draws with
before/after screenshots of each state it touches, from `uv run leaf-dev stills`
(`/developing-leaf`, "Prove and hand off a visible change").

## Working on the runtime

A paint that must land in the current turn uses `render`; `LitElement` schedules
updates on a microtask and suits only runtime views that can wait that long. The
microtask costs no frame, but code that reads the document right after a paint, such
as a focus move onto a control just drawn, a measurement, held news
(`thread/held-news.js`) or a region committing in `PRESENTATION_ORDER`'s pass, would
await `updateComplete` and let other work run in between: the margin's chip
placement took three ordering bugs to settle when it went asynchronous. Tracking
reads needs no microtask, since a Preact `effect` tracks in the current script.

A Lit render subscribes to every selection it reads (`leaf-element.js`), so a
reader called from a paint selects exactly what it returns (`readPart`) rather than
selecting more and narrowing it. The paint then reruns only when that answer changes.
Reading the whole root inside a paint subscribes it to every publication.

Test what one module decides on its own under `tests/runtime/` (`pnpm run
test:runtime`). `pnpm run check:browser` type-checks the runtime and widget modules,
strictly where a module is marked `// @ts-check`; `build/AGENTS.md` owns the framework
build. A new global, event detail or runtime element tag is declared in
`browser/framework/runtime-globals.d.ts`.
