# The page in the browser

This file holds the browser rules that span modules: how pages look and move, module
boundaries, which code owns each fact, and the render gates. Each module's header owns
its local contract, the contracts modules and packages build on are in
`../skills/leaf/references/module-*.md` and `../skills/leaf/references/packages.md`, and the rules shared with
Python are in root `AGENTS.md`, "Cross-runtime invariants".

Stylesheets need no build: page composition and the serving runtime place each file a
sheet `@import`s where the import stands (`stylesheet` in `src/leaf/layer.py`).

## Leaf's interface

These rules hold for everything Leaf draws: its runtime, its chrome and its bundled
packages. Each section opens with a goal, which
`../skills/leaf/references/interface-goals.md` gives other authors too, and the specs
under it are Leaf's own ways of meeting it; weigh a case no spec covers against its goal
and `../SOUL.md`. A spec names its check and owner where one exists. How the owner meets
it, and any exception the user chose for one surface, belong in that owner's header and
the check's credit, not here. Which specs should also bind other authors is still being
settled. Leaf targets desktop first, so judge layout at a representative desktop
viewport.

### The page holds still under the user's aim

A change the user didn't make moves nothing they are reading, pointing at or typing into,
since that would take their place and their aim away in the middle of the task
(`../SOUL.md`, "Preserve the user's attention and work"). Every hold costs code on each
later change, so the guarantee is owed to the paths users take often: a rare path the
user takes in at a glance may move what is on screen rather than carry a mechanism of its
own (`../SOUL.md`, "Keep the foundation small and extensible").

- **Controls stay where the user aims.** A state change may repaint any box, but a control
  the user pressed stays where it was while it still stands. When the press removes it,
  the press's result takes its place, and that may be the next item's same control, as
  when Resolve in the floating panel moves the user on to the next thread
  (`floating-panel.js`); a change the user asked for may reflow what it replaces, with
  motion the eye can follow. A scroll the gesture makes carries the pressed control only
  to bring it whole into a scroller that showed part of it, or where the gesture says it
  takes the user somewhere. Without a gesture, as when news arrives or a widget finishes
  loading, a box may grow or shrink into free room, but reading content and controls stay
  put. No hard-to-undo action arrives under a pointer that hasn't moved. A reveal on
  hover, focus or a key never moves its ancestors or siblings, and typing may grow a
  field but never moves it. Check: `tests/shift_watch.js`, whose header lists what it
  credits.
- **A box's controls stand on an edge the box holds as its content changes.** The same
  control may therefore stand at a thread card's head and at the floating panel's foot;
  each box's header says which edge it holds (`floating-panel.js`, **Opened**;
  `thread/card-anchor.js`).
- **News never moves what the reader is reading.** News from the server grows above the
  screen, where scroll anchoring absorbs it, or below it; anywhere else it waits behind a
  fixed-size control until the reader goes to it, and an editor in use stays still. An
  exception the user chose stays with its owner, as `fitAnswer` in `floating-panel.js`
  does. Check: `test_news_just_after_a_press_moves_nothing`. Owners: `thread/held-news.js`,
  and `threadsListing` in `floating-panel.js` for the rows of Threads.
- **Nothing Leaf draws moves the page's content.** Pins, passage marks and runtime
  controls sit over the page and take no space, and no rule pads or widens a block to
  make room for them. The rail sits right of `main` when the window is wide enough and
  never moves or narrows the column (`../skills/leaf/references/page-layout.md`, "The
  rail and the margin"). Native document tracks and wrapping rows place the page's own
  sidebars and notes from the first paint, and `runtime/content-layout.js` reads their
  CSS geometry for annotations and never reallocates document space. The chrome opens
  over the page too, in the
  room the theme keeps at the page's foot (`--lf-foot-room`). Checks:
  `test_a_comment_leaves_its_block_as_the_page_wrote_it` and the shift watch. Owner:
  `annotation-overlay/margin-placement.js`.
- **A box floating over the page grows inside the window**, toward the edge that has
  room, and sending and later growth never scroll the page to make room. Owners:
  `annotation-overlay/comment-placement.js` for attachment and bounds, and
  `thread/card-anchor.js` for what each interaction preserves. A freshly opened card may
  scroll to open clear of its target, and otherwise only a field in flow scrolls to keep
  its controls in view (`thread/reply-landing.js`).
- **Readable content comes before activation.** Authored HTML paints while browser
  modules load. Each widget owns one Lit view across its lifetime; native slots retain
  authored children and CSS owns their initial layout. Each control waits only for the
  behavior or state it needs, and nothing holds the whole document behind widget
  readiness (`../skills/leaf/references/module-authoring.md`, "First paint").
- **A widget grows with its content.** In ordinary flow a widget grows with its content,
  and keeps its visible geometry as its state updates. It scrolls inside itself only when
  its task needs a region kept in view while its contents move, or for a live stream
  whose newest entry the reader follows, and then declares `--lf-holds-height: 1`. Checks: the widget
  quality checks `keeps-first-box` and `grows-with-content`
  (`src/leaf/render_gate/widget_quality.py`).
- **Room is held only for what will be drawn**, such as a widget's upgraded controls, and
  generated interface appears in its final position. A state that may never come, such
  as a failed save, shows in a slot already on screen, as a message's head carries its
  delivery status, and the user's gesture makes the room it needs. Feedback may repaint
  a control or change its label, but never its size: `data-room` (`controls.css`) sizes
  a label to the widest of the words it can show. Adjacent actions keep their hit areas
  apart.
- **Shared containers determine control dimensions.** When several modes share a
  container, as the comment field, page search, Threads' search and a thread's reply
  share the floating panel's field, the container sets its dimensions from a theme token
  and each mode's controls fill it. It grows only for content, such as typed words, or
  an explicit action, such as More room. A one-line control's visible height is
  `--lf-line` (`base.css`), and its touch target meets the minimum `surfaces.css` sets;
  a control that derives its height from its font or the touch minimum instead changes
  the height of every container that holds it. Checks:
  `test_whatever_the_field_holds_the_row_keeps_its_line` compares the row's height with
  its token in each mode, since a check that controls fit the row would pass a row that
  grew to fit them, and `tests/swap_watch.js` fails a flex row whose height follows a
  replacement child.
- **A runtime region whose contents rearrange inside it declares `data-lf-reflow`** on
  the box that owns the space: `text` where its labels may rewrap while its controls
  stay put, as in a message header, and `append` where it grows only at its end, as a
  thread card's transcript does. A nested region keeps every guarantee of the regions
  around it. The `tests/shift_watch.js` header says how the watch credits each.

### Typed words survive

Words the user has typed are work they haven't sent yet, so nothing Leaf does takes them
away or moves them out of reach (`../SOUL.md`, "Preserve the user's attention and work").

- **Typed words stay in their native editor until the user puts them away.** A box
  holding words closes only on a key or press meant to close it (Send, Cancel, Escape, a
  press elsewhere, another target) or when its subject leaves the document, never on a
  scroll, resize, timer or server news. Geometry decides where the box sits, never
  whether it exists: a box a scroll carried away comes back when the user types into it
  (`off-flow.js`), and Resume writing (`g i`) shows the same editor. A re-render that
  replaces the box's node hands its words and caret to the replacement. Checks:
  `tests/words_watch.js` and `typed_box_findings` in the render gate tests. Owner:
  `annotation-overlay/composing/floating-response.js`.
- **Editing something keeps it where it stood and as it read**, so the user finds what
  they meant to change where they saw it, and sees what saving will show. Opening a
  message, a draft or any value for editing draws it in its display's place and face:
  every line of its words keeps its position, type and breaks, and its pictures and
  other parts keep their places and sizes. The editor adds only what editing needs, such
  as a field's frame, Save and Discard, or a picture's removal mark, in room the display
  already has: around the content, or at the head where the display's own control
  stood. Where the frame needs room the display lacks, the display keeps that room at
  rest, rather than the content moving on opening, as a scroller holding messages keeps
  the thread's text inset beside them. Checks:
  `test_a_rewrite_keeps_the_message_as_it_stood` and `test_a_draft_edits_where_it_reads`.
  Owners: `thread/message-edit.js`, `.lf-msg-editor` in `styles/components/response.css`,
  and `composing/text-field.js`.

### A gesture shows its result at once

What the user's act decides by itself appears as they make it, so they see that it took
effect without waiting on the server (`../SOUL.md`, "Make the work concrete and
playable"). Root `AGENTS.md`, "Responsiveness" and "The document starts state; the log
changes it", say which results the browser draws and which wait for the server's
reading.

- **The result confirms the gesture.** The new content and its Undo confirm success, so
  success needs no notice beyond the announcement for a listener. Content whose result
  only the log can supply, such as a message being sent or an upload, waits with
  `aria-busy`; a control a package marks busy fades after a delay, so a fast answer shows
  nothing, and keeps its cursor. Persistent status text is for a state the user must
  return to, such as a failure.
- **The pressed control stays live.** It draws from the same reading, the pending
  gesture included, so it shows no busy or disabled face while the gesture travels, and
  a second press does what the control then says, such as Undo, which names a pending
  gesture by its attempt.
- **A refused or undone gesture gives back what it took.** A refusal restores the
  server's state, and delivery says why in the notice seat. A refused send returns the
  words to their box (`standGesture` in `drafts.js`), and a gesture that moved the user,
  such as resolving a thread, leaves them at its place again (`undo.js` owns where undo
  leaves the user).

### Controls are few and quiet

Leaf's controls compete with the page's own words for the reader's attention, so each
earns its place against the content and takes no more room or emphasis than its task
needs (`../SOUL.md`, "Let the user work as directly as in a terminal").

- **A surface at rest shows only what its task needs**, and the leaf's menu holds the
  rest. Symbols, below, are no licence for more controls.
- **A control takes only its own room.** Leaf never reserves a strip, a row or
  full-width padding to seat one small control. The control joins a line that is
  already there, such as a head, the line over a field or a row's end, or a corner its
  content leaves free.
- **A control shows a symbol where a standard symbol for its action exists, and its word
  where none does.** A standard symbol is one readers already know for that action from
  the software they use, such as ✕ for close, ✓ for resolve, ‹ and › for back and next, and
  the symbols for play, pause, copy and undo, so they can tell what the control does
  before hovering it; a symbol is smaller and quieter than a word. The control names its
  action from `ACTIONS` in `runtime/icon-paths.js`, which gives it the action's symbol,
  and says its name as tooltip and accessible name, without the word beside the symbol.
  An action shows one symbol, or one word, wherever Leaf offers it, so a reader who
  learns it in one place knows it in every other, and a press names an action, never an
  icon, so its symbol can't drift. One control whose symbol follows its state, such
  as play turning to pause, replaces a button for each state. A symbol only related to
  the action, such as a speech bubble for answering a question, leaves the reader
  guessing, and a tooltip doesn't fix that: the reader must already suspect the control
  to hover it, and a touch screen has no hover. The rows of the leaf's menu keep their
  words, since the user opened the menu to read them.

### Visual treatment carries meaning

Each treatment draws the eye, so each marks hierarchy or state, and a difference the
reader sees always means something (`../SOUL.md`, "Let the user work as directly as in a terminal").

- **Contours are solid.** A dotted or dashed line marks a distinct state, such as a
  draft or a drag placeholder. One contour shows one control state, and a segmented group
  shares one-pixel seams. A box edged on one side is never rounded: mark a state with a
  whole contour, or a stripe on a square box. Avoid reflexive cards, tints, gradients and
  soft shadows. Check: `test_no_rule_rounds_a_box_edged_on_one_side`.
- **One role, one face.** Two controls of one kind look the same, and a face used twice
  is a token or a shared rule ("Layouts, styles and controls", below, says how code
  keeps this).
- **Green marks the user's turn; other thread controls stay blue.** Every surface paints
  a thread's `unread` and `attention` from one value, so the On me mark's dot, Threads,
  the panel, a margin entry and the Page Map change together, and marking read never
  moves the user.

### Motion is brief and keeps the user oriented

Motion helps the eye follow a change, and costs the user time whenever they wait for it
(`../SOUL.md`, "Preserve the user's attention and work").

- **Nothing the user must read, press or decide waits on a clock.** Motion the user waits
  on stays under 300ms. A delay may hide a flicker but never adds a minimum spinner time
  or a staged reveal. `runtime/motion.js` owns the shared motion gate, easing and
  reduced-motion check, and `--lf-motion-*` properties set durations and curves: the
  theme's for the document, and a runtime surface's own sheet for that surface, as
  `floating-panel.css` does for the panel.
- **Animations are restrained and finite, and acknowledge state changes.** The one continuous animation
  is the sheen (`@keyframes lf-sheen` in `styles/components/surfaces.css`), which marks
  agent work in progress. It stops when the work ends and is static under reduced
  motion.

### A region that must scroll behaves like the document

A region that scrolls by itself splits the reader's place in two, so it moves and is
reached like the page around it (`../SOUL.md`, "Preserve the user's attention and
work").

- **A necessary scroller works like part of the document.** It passes scrolling on to
  the document at its edges, except at a bounded task or a modal. Wheel and touch keep
  moving through content; pan and zoom need a deliberate control. It has a keyboard
  route, visible bounds and visible focus, which `reachScrollers` in `runtime/reach.js`
  supplies by giving every scrollable box a tab stop and painting the edge its content
  continues past. An object taken out of flow for inspection restores the selection and
  the document position on return. Checks: the reach tests and the axe sweep;
  `/ui-sweep` reviews scroll chaining and the return from inspection.

## Runtime ownership

`leaf.js` only boots the page: it imports the owner modules, each of which exports its
capability, and starts them in the order "Startup and presentation" lists. Two classic
scripts run before any module. `runtime/prepaint.js` runs inline in every document,
served or exported. It marks the interactive document, restores native reading state
and reports startup failures. Content remains readable while modules load; controls
activate through their owning widget lifecycle. A failure removes the interactive mark
and names the reason in `data-lf-startup-error`.
`runtime/bootstrap.js` runs in a served page only, holds keys pressed before upgrade
and shows a startup failure.

Content modules import only `runtime/widget-api.js`, the public helper surface, or a
widget that also runs off Leaf only its part any document loads,
`runtime/portable-api.js`;
`module-authoring.md` defines these boundaries. Owners
receive their capabilities when constructed and read other owners in their mounts. The
projection, thread and pending models import no DOM or application services.
`.dependency-cruiser.mjs` enforces these boundaries and rejects cycles, so imports use
literal paths; only the widget and interaction loaders compute theirs.

Entry points per concern (paths under `runtime/`; each header owns the details):

| Concern                                                                                                     | Owners                                                                                                                                                     |
| ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Composition and the application's state                                                                     | `application.js`, `semantic-state.js`, `context.js`                                                                                                        |
| Delivery, accepted state, and wakeups                                                                       | `delivery.js`, `state-application.js`, `state-feed.js`, `layer-client.js`, `traffic.js`                                                                    |
| Undo and withdrawal                                                                                         | `undo.js`                                                                                                                                                  |
| State models and projection                                                                                 | `projection/`, `thread/model.js`, `thread/workflow.js`, `thread/state.js`, `pending/`, `obligations/model.js`, `queues.js`                                 |
| Widget capture and lifecycle                                                                                | `document-identity.js`, `widget-descriptors.js`, `widget-controller.js`, `widget-loader.js`, `widget-upgrade.js`                                           |
| Vocabulary and public helpers                                                                               | `registry.js`, `widget-api.js`, `portable-api.js`, `widget-elements.js`, `widget-upgrade.js`                                                               |
| External data                                                                                               | `data.js`, `projection/data.js`, `projection/authored.js`                                                                                                  |
| Revision installs and continuity                                                                            | `version.js`, `version-picker.js`, `carry.js`, `dom-children.js`, `root-state.js`, `restore-state.js`, `since-seen.js`                                     |
| Repaint and geometry                                                                                        | `rendering.js`, `repaint.js`, `page-geometry.js`, `geometry.js`, `shown-box.js`, `element-frame.js`, `css-anchors.js`, `rect.js`, `pointer.js`             |
| Chrome and available space                                                                                  | `chrome.js`, `floating-panel.js`, `page-layout.js`, `page-controls.js`                                                                                     |
| Reading regions and scrolling                                                                               | `reading-regions.js`, `reading-place.js`, `bounds.js`, `scrolling.js`, `reach.js`, `user-place.js`                                                         |
| Keyboard                                                                                                    | `keyboard/AGENTS.md`                                                                                                                                       |
| Focus and navigation                                                                                        | `focus.js`, `current-target.js`, `navigation.js`, `queue-walk.js`, `history.js`, `user-intent.js`, `walk-position.js`, `change-walk.js`                    |
| Obligations                                                                                                 | `obligations/`                                                                                                                                             |
| Comment capture                                                                                             | `composing/`, `drafts.js`, `media.js`                                                                                                                      |
| Threads                                                                                                     | `thread/`                                                                                                                                                  |
| Annotation inventory and controls                                                                           | `annotation-inventory.js`, `annotation-view.js`, `contributions.js`, `contribution-controls.js`, `inline-contributions.js`                                 |
| Annotation records and Page Map                                                                             | `margin-model.js`, `margin-map-model.js`, `page-map-dialog.js`, `pointed-place.js`                                                                         |
| Pins, marks and floating placement (loaded only when `body` keeps the default `data-annotations="overlay"`) | `annotation-overlay/`                                                                                                                                      |
| Passages and target identity                                                                                | `passages.js`, `kernel-facts.js`, `text-alignment.js`, `anchor-coordinate.js`, `resolved-target.js`, `anchor-resolution.js`, `addressable-names.js`        |
| Anchor placement, decoration and travel                                                                     | `anchor-placement.js`, `anchor-note-view.js`, `anchor-controls.js`, `anchor-travel.js`, `target-paint.js`, `target-paint-geometry.js`, `visual-parts.js`   |
| Page status and what a user copies about the page                                                           | `page-status.js`, `page-about.js`, `heading-links.js`                                                                                                      |
| Neighboring pages                                                                                           | `live-leaves.js`                                                                                                                                           |
| Activity and reports                                                                                        | `presence.js`, `activity-words.js`, `reports.js`, `at-work.js`                                                                                             |
| Notices, errors and announcements                                                                           | `semantic-news.js`, `notifications.js`, `errors.js`, `keyboard/status-context.js`                                                                          |
| Reactions and design review                                                                                 | `reactions.js`, `design.js`, `design-readings.js`                                                                                                          |
| Presentation and validation                                                                                 | `presentation.js`, `declared-words.js`, `validation.js`, `leaf-element.js`                                                                                 |
| Child pages                                                                                                 | `sample*.js`                                                                                                                                               |
| Shadow trees and styles                                                                                     | `shadow.js`, `shadow-stage.js`, `stylesheets.js`, `base-layer.js`                                                                                          |
| Paint that belongs to an element while it is in the page, whoever added it                                  | `arrivals.js`                                                                                                                                              |
| Utilities                                                                                                   | `abort.js`, `icons.js`, `markdown.js`, `syntax.js`, `syntax-tokens.js`, `motion.js`, `color-scheme.js`, `storage.js`, `tab-store.js`, `interaction-log.js` |

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
class's weight off itself (`styles/chrome-guard.css`), and a package restyles it on
purpose by part from its `chrome.css` (`chrome_restyle` in `layer.py`).

A `:has()` rule can turn a local write into a restyle of the whole page or chrome. An
unkeyed rightmost compound widens what it invalidates, and a condition on the chrome
root, `body` or `html` is re-evaluated on writes below it. Prefer a class that names the
targets, or a condition its owner sets on the styled element, and measure with
`leaf-dev profile SOURCE TRANSITION`.

### Layouts, styles and controls

- **The page owns its arrangement.** A page arranges itself with a shipped Layout
  class (`layouts.css`) or its own CSS. Leaf owns only what pages and widgets share: the
  bands, the reading measure a Layout sets, and each widget's duty to fill the box it
  gets, declare its minimum, and never widen its container.
- **A Layout, a style and a widget never read one another.** A Layout sets where boxes
  go and how large they are, a style (`base.css`) sets type, spacing and form as tokens,
  and a widget reads only its own box and the theme's tokens. A widget therefore behaves
  the same in a shipped Layout as on a hand-written page that gives it the same box.
  Where one must react to another, the owner sets a token describing the box, such as
  `--lf-full-height`, and the reader matches it with a style query; a width needs no
  token, since a size query on the reader's container answers it. Before adding a token,
  ask whether a hand-written page with the same box would want the same answer. If not,
  the token describes a Layout rather than a box. Check:
  `test_layout_style_and_widgets_never_read_each_other`.
- **A control wears its role's face.** Code builds a control by its role, with
  `offerAction` or `offeredAction`, and never names a face's classes, so two controls
  of one kind can't look different (`runtime/control-faces.js`, `ACTION_FACES`, lists the
  roles). A new role needs a difference in the user's task, not only in a widget's
  taste. Check: `test_controls_are_built_by_role_and_never_by_face`.
- **A face used twice is a token or a shared rule.** A lift names one of the theme's
  heights, `--raise-1` to `--raise-3` (`base.css`). Check:
  `test_every_lift_names_one_of_the_theme_s_heights_cast_in_the_scheme_s_ink`.

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

State a module keeps for one press, or for one view while it stays open, lives in one
record that starts when the press or view does and is dropped when it ends, rather than
in variables the module resets by hand. A module keeps its record against the press
through `focus.js` `pressRecords`. A field added to the record ends with the others,
where a separate variable needs a reset at every place the press or view can end.

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
| Whether a box shows what it holds, not only its own box as one hidden until found does                | `geometry.js` `showsContents`                                                      |
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
| Who says a word a seat shows about the work, and the face it says it in                               | `voice.js` `agentSays`, `leafSays`, `voiced`                                       |
| A workflow's word, and its progress face on a control; an open to-do's word                           | `thread/workflow.js` `workflowWord`, `progressFace`, `todoWord`                    |
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
(`pnpm run test:runtime`). The runtime is JavaScript a page runs as written.
`pnpm run check:browser` strictly type-checks every maintained runtime and widget
module; no file pragma is needed.
`../build/browser/build.mjs` owns checker selection; `types/` holds its configuration
and declarations. Declare a new
global, event detail or runtime element tag in `types/runtime-globals.d.ts`.
