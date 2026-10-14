# The page in the browser

This file owns browser-wide contracts: how the page should look and move, module
boundaries, startup, state authority, and the render gates. Each module's header
owns its local contract. Page-authoring rules live in
`../references/page-authoring.md`, module authoring in `../references/module-*.md`,
package contracts in `../references/packages.md` and `package-*.md`, and rules
shared with Python in root `AGENTS.md`, "Cross-runtime invariants".

Shared stylesheet owners live under `styles/`: `styles/shadow.css` composes
`styles/components/` into the shared root sheet. Document composition loads that
sheet before the theme, and declared shadow roots adopt it too. Edit these sources
and `styles/theme.css` / `styles/chrome.css`, not generated `theme.css`, `shadow.css`
or `runtime/chrome.css`.
`build/AGENTS.md`, “Committed bundles”, owns rebuilding and checking them, including
bundled package entrypoints. Custom package authors supply complete sheets under
`../references/packages.md`, “Styles and composition”.

## Layout and motion

These invariants hold for every page and for everything Leaf draws on one. Each names
the check that enforces it, where one exists, and the modules whose headers own its
detail. Leaf's current product focus is desktop, so judge layout first at a
representative desktop viewport.

### Space and scrolling

- **The page owns its arrangement.** A page arranges itself with a shipped Layout
  class (`layouts.css`, `@layer lf-layouts`) or its own CSS. Leaf owns what pages and
  widgets coordinate through: the bands, the reading measure a Layout sets, and each
  widget's contract to fill the box it is given, declare the minimum it needs, and
  never let its content widen its holder.
- **A Layout, a style and a widget never read one another.** A Layout (`layouts.css`)
  sets where boxes go and how large they are, and takes its gaps from the theme's
  spacing tokens (`--sp-*`). A style (the kernel's `theme.css`) sets type, spacing and
  form as tokens under a class any block can take, such as `density-working`. Widgets
  and chrome read their own box and the theme's tokens, so a widget behaves the same in
  a shipped Layout as on a page whose own CSS gives it the same box. Where one has to
  answer another, the owner sets a token describing the box and the reader keys on it
  with a style query: `--lf-full-height` (this box's children have a definite height
  to fill; it does not inherit), `--lf-wide-page` (the page spans the window),
  `--lf-resident` (what sits in the column's margin, or beside a sidebar page's body), and `--lf-density` (the working
  setting, for what a width alone cannot decide). A width needs no token, since a size
  query on the reader's own container answers it. Before adding a token, ask whether a
  hand-written page giving the same box would want the same answer; if not, the token
  names the Layout rather than the box. Only the page itself, and the checks that
  advise its author, name Layout classes. Check:
  `test_layout_style_and_widgets_never_read_each_other`.
- **Nothing Leaf draws moves the page's content.** Runtime controls, pins, passage
  marks and the rest of the annotation layer lie over the page and take no room, even
  when their CSS loads before first paint: adding, removing or moving one keeps every
  block's position, wrapping and size. No rule pads, indents, widens or reflows a block
  to clear a pin, since reserved room would make the page's geometry depend on which
  markers exist and where. A pin stands by its target, over the target's own words
  where no seat beside it is clear; hiding annotations reveals what it covers. The rail sits right of `main` wherever the window
  has room, and seating it there never moves, narrows or indents the column
  (`content-layout.js`). `data-rail` on `body` withholds or reserves it: `"right"` makes
  the shell give up the rail's width, so the page's layout gets narrower
  (`annotation-theme.css`). Otherwise only the left resident and sidenotes move the
  column, through prepaint.js `residency`.
  Checks: `test_a_comment_leaves_its_block_as_the_page_wrote_it` and the shift watch
  ("Stability"). Owners: `runtime/annotation-overlay/margin-placement.js` for where a margin
  row sits and when a pin folds.
- **Auxiliary surfaces open over the page and never change its geometry.** The
  On panel, the thread panel and the Pages drawer take no room from the page;
  `auxiliary-surfaces.js` says when one leaves the page live beside it and when it
  covers the page (`--lf-auxiliary-beside`, `standsBeside`). Which box scrolls is the
  stylesheet's, a Layout's or the page's, and the runtime reads it rather than deciding
  it. The Threads panel's design is being reconsidered (`TODO.md`, "Reconsider thread
  navigation"): carry findings about its layout and interaction into that redesign
  rather than polishing the current panel.
- **A widget in ordinary flow grows with its content.** Internal vertical scrolling
  needs a task that benefits from keeping a region in view while its contents move, or
  a live stream whose newest entry the reader follows; being an inspection object is
  not enough. A box that holds its own height declares `--lf-holds-height: 1`, as a
  bounded block's theme and a full-height workspace's scrolling regions do. Check: the
  widget quality check `grows-with-content` (`scripts/leaf/render_gate/widget_quality.py`),
  run on each package's worked examples and, in the suite, on every corpus page. Page
  authors' side: `../references/page-layout.md`, "Bounds and widths".
- **A necessary scroller works like part of the document.** It chains into the
  document at its edges; isolate scrolling only at a bounded task or modal boundary.
  Wheel and touch keep their navigation meaning, and deliberate controls enter pan and
  zoom. It has a keyboard route, visible bounds and visible focus. Allocate room before
  shrinking evidence, and keep narrow screens' access to two-dimensional evidence
  deliberate. Expanding content keeps the allocation its declaration gave it. An object
  that leaves flow for inspection keeps the controls its task needs and restores the
  selection, inspection state and document position on return; a root workspace never
  duplicates itself in another inspection layer. Owner: `runtime/reach.js`
  (`reachScrollers`) gives every box a mouse can scroll a tab stop and paints the
  edge its content continues past. Checks: the reach tests
  (`test_a_scroll_box_inside_a_widgets_shadow_tree_takes_the_keyboard`,
  `test_a_hidden_scroller_is_reached_once_it_is_shown`,
  `test_a_marked_scrolling_visual_keeps_its_keyboard_focus_ring`) and the axe sweep.
  Chaining, room allocation and inspection return have no test; `/ui-sweep` reviews
  them.

### Stability

- **The page holds still under the user's aim.** A state change may repaint any box
  but must not move controls next to the gesture that caused it. Without a gesture, a
  box may grow or shrink into free room, but reading content and controls stay put. A
  change the user requested may reflow the content it replaces, as motion the eye can
  follow. A hover, focus or keyboard reveal never changes the space given to its
  ancestors or siblings. Typing may grow its field at the edge its layout grows, but
  never carries the field. Check: `tests/shift_watch.js`, which the suite's browser
  fixture runs on unmarked tests and on marked ones that opt in with `watch_shifts`. It
  fails a protected box moving on screen without input, news landing just after a press
  included, and typing carrying its field.
- **A runtime region that repacks inside itself declares it with `data-lf-reflow`.**
  The value names the stationary box and what may move inside it. In a `text` region,
  such as a message header, labels may repack while every contained control stays put.
  In a `controls` region, such as the shortcut bar, hints and controls may repack. In
  an `append` region, a thread card's transcript in the panel or the margin, its end
  may grow within its stationary scrollport while existing messages stay put: new
  children, or, where none joins, a last child declared its growing tail
  (`data-lf-append-tail`), the working message or a streaming reply. The idle reply row and later cards may move by that growth, and no
  other change may. A scrollport sized to what it holds, as the margin's floating card
  is, counts as stationary while it grows only at its foot, by that growth. Declare the
  box that owns the room, not an auto-sized inner label group or a boxless wrapper. A
  nested region holds its own boundary and every enclosing declaration's guarantees,
  including across a shadow root, and never relaxes them. Neighbours and the page's reading
  content stay put. Check: the shift watch. Owners: `thread/thread-card.js`,
  `thread/messages.js` and `keyboard/shortcut-bar.js` declare today's regions.
- **News never moves what the reader is reading.** News grows where the reader isn't
  looking: above the screen, where scroll anchoring takes the growth into what they
  scrolled past, or below it. Otherwise it waits behind a control of fixed size until a
  gesture of theirs takes them to it, and an active composition keeps its editor still.
  A hidden tab ends the reading this protects; keyboard blur does not. Check:
  `test_news_just_after_a_press_moves_nothing` and the shift watch. Owners:
  `thread/held-news.js` for every thread surface and, through `HeldReading`, for a
  widget's rows that only the log or the clock decides, and through `heldGrowth` for
  a box a deferred arrival resizes, such as a live sample's frame; `thread/thread-card.js`
  (`newsMoves`) for whether a change would move what is seen; `thread/thread-list.js`
  for the Threads panel's reading place; `thread/thread-list-view.js` (`keeping`) for a
  card news would take out of the panel's view; `reading-continuity.js` for a hidden
  tab.
- **A turn of the user's own takes them with it.** A turn that takes its card out of
  the Threads panel's view, as a reply under "Waiting on me" or a rewrite or Reopen
  under Resolved does, widens the view to one that holds the thread and takes the user
  with it; a refusal puts the view back only while they have not acted since. Owners:
  `thread/thread-card.js` (`#speak`), `thread/folding.js`.
- **A box floating over the page grows inside the window.** The comment box and the
  thread card grow toward whichever edge still has room as the user types, and never
  scroll the page for their growth (`comment-placement.js` in the default package). One
  a scroll carried away comes back for the words typed into it (`off-flow.js`). Only a
  field in flow keeps its controls in view, as a browser keeps a caret in view
  (`thread/reply-landing.js`).
- **A widget paints its final box before it upgrades.** The theme gives each widget,
  under `html[data-lf-interactive]`, the size its module will draw it at, so upgrade
  adds behavior without moving what follows, in a served page and an export alike.
  Where the module draws a fixed structure, delivery writes that structure in for the
  first paint (`x-prepaint`), so the browser sizes it, wrapping included. Check: the
  widget quality check `keeps-first-box` (`leaf package check PACKAGE --render`,
  `widget_quality.py`); the suite runs it over every bundled package and fails on a
  finding `tests/known_widget_findings.py` does not list.
- **Generated interface first appears in its settled position.** Reserve space before
  a generated control appears. Transient feedback may repaint a control or briefly
  replace its label but never changes its geometry (`data-lf-room`, `controls.css`,
  sizes a label for all its words). An action awaiting confirmation dims its
  existing control after the shared delay. The parent laying out adjacent actions gives
  them disjoint hit boxes.
- **An unlikely event fits into what is already there.** Reserve no room for a state
  the user rarely meets, such as a failed save or another writer changing a file.
  Show it in a surface that already stands and already has room, such as a status
  slot, rather than in a new region, and let the user's own gesture expand it where it
  carries more: a file conflict says so in the editor's status, and its two versions
  open only on Compare (`lf-file-editor.js` in the file-editor package). Room held
  empty for an unlikely event is a defect, and so is the jump when it arrives. The
  settled position above is for interface the ordinary course of use brings, such as
  a label's other words; an unlikely event takes no room of its own.
- **A gesture shows the result the page can draw as it is made** (root `AGENTS.md`,
  "The document starts state; the log changes it"). `standGesture` in `drafts.js` owns
  both the send and the refusal that returns words to their box. The content and its
  Undo are the confirmation, so success needs no notice beyond the announcement for a
  listener. A gesture that moves the user, as settling a thread does, owns the move
  back, which runs both when the log refuses it and when the user takes it back
  (`thread/folding.js`). A result only the log can supply waits with `aria-busy`,
  painted on a delay so a fast answer shows nothing. Persistent status text is for a
  state the user must return to, such as failure.

### Words stay where they were typed

- **Typed words stay with their native editor until the user puts them away.** A box
  holding words closes only in answer to a key or a press that means to close it (Send,
  Cancel, Escape, a press elsewhere, another target) or when its subject leaves the
  document; a scroll, a resize, a panel, a closed disclosure, a timer, or the server's
  news never closes it. Geometry decides where a box sits, never whether it exists: a
  box follows its passage through every scrolling ancestor, including out of view,
  keeping its words, anchor and caret, and Resume writing (`g i`) reveals that same
  editor. Only where no usable room remains does the presenter withhold the box, and
  its words and caret stay with its native node (`standFab`,
  `runtime/composing/surface.js`). A re-render that replaces a box's node hands its
  words and caret to the replacement. Checks: `tests/words_watch.js`, through which the
  suite's browser fixture fails any test whose page loses typed words without a key or
  press, and `typed_box_findings` in `tests/*/test_render_gate.py`, which scrolls every
  corpus page to both ends and back with each typed box open. Owner: the default
  package's `composing/floating-response.js` for where the box floats.

### Visual grammar

- **Visual treatments carry hierarchy and state.** Contours are solid; a dotted or
  dashed line is a non-color cue for a distinct state (a draft, a drag placeholder,
  design-mode geometry, a detached reference), and lines inside authored diagrams keep
  the document's own meaning. One contour carries one control state, and a segmented
  group keeps one-pixel shared seams. Avoid rounded one-sided borders and reflexive
  cards, tints, gradients, or soft shadows.
- **Each thread's `unread` and `attention` are single readings** that every surface
  painting them consumes, so the Threads toggle, filters, panel, margin entry, and Page
  Map change together. Workflow state rides the existing semantic control rather than
  competing with attention for color. Green marks the user's turn; other thread
  controls stay blue. Pickup and work use status words, with one brief pulse when work
  begins that a repaint never replays. Reading is bookkeeping and never moves the user.

### Motion

- **Animations are restrained and finite, and acknowledge state changes.** An
  unchanged state does not animate continuously. One sheen, `@keyframes lf-sheen` in
  `styles/components/surfaces.css`, is the only continuous animation, and it marks work
  under way: across “Generating title” on an untitled thread awaiting the agent, across
  a thread's working message while the agent's work on it runs, and across the floating
  panel's empty field while it says the agent is working. It stops when that state ends,
  and is static under reduced motion.
- **Nothing the user must read, press, or decide waits on a clock.** Motion runs from
  a state that is already true, and motion that must finish before the result can be
  read is a pause. A motion the user waits on stays under 300ms; one that moves
  nothing, such as a landing flash, may run longer. A delay may withhold a flicker but
  never adds a minimum spinner time or a staged reveal. `runtime/motion.js` owns the
  shared gate, ease, and reduced-motion answer. Typed `--lf-motion-*` properties in the
  theme own shared durations; their readers resolve the live document-root values for
  JavaScript. The theme's guard answers for CSS.

## Runtime ownership

`leaf.js` is the boot-only entry: every owner is a module that exports its
capability and imports what it needs, and `leaf.js` imports them and runs the
boot sequence. Two classic scripts run before the first paint, which no module
reaches. `runtime/prepaint.js` runs first, inline in the head after the canonical
link, in every document the runtime runs in, served or exported. It marks the root
`data-lf-interactive`, so the themes give each widget its upgraded box, and takes the
mark off when the runtime could not start because something it needs did not arrive
or the page declared it failed (naming why in `data-lf-startup-error`), so the themes
give back the readable fallback for every widget at once, and a declared failure
never presents (`leaf.js`); it declares the page's storage scope; and it decides which
member an `x-views` holder opens on. `runtime/bootstrap.js` runs next, in a served
page only, before any resource the page loads. It marks the page live
(`data-lf-live`), so the theme reserves the chrome's room; it shows a startup failure
and waits for a server that can start the page, even if the module graph never loads,
or says the page has a problem where the fault is the page's own, as words a module
staged where the page cannot read them; and it holds page keys until their declared inputs are available. Content modules import only
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
| Undo and withdrawal | `undo.js` |
| State models and projection | `projection/`, `thread/model.js`, `thread/workflow.js`, `thread/state.js`, `pending/`, `asks/model.js`, `queues.js` |
| Widget capture and lifecycle | `document-identity.js`, `widget-descriptors.js`, `widget-controller.js`, `widget-loader.js`, `widget-upgrade.js` |
| Vocabulary and public helpers | `registry.js`, `widget-api.js`, `widget-elements.js` |
| External data | `data.js`, `projection/data.js`, `projection/authored.js` |
| Revision installs and continuity | `version.js`, `version-picker.js`, `carry.js`, `dom-children.js`, `root-state.js`, `restore-state.js` |
| Repaint and geometry | `rendering.js`, `repaint.js`, `page-geometry.js`, `geometry.js`, `element-frame.js`, `scroll-motion.js`, `css-anchors.js`, `rect.js`, `pointer.js` |
| Chrome and available room | `chrome.js`, `chrome-layout.js`, `auxiliary-surfaces.js`, `drawn-edge.js` |
| Reading regions and scrolling | `reading-regions.js`, `reading-place.js`, `bounds.js`, `scrolling.js`, `reach.js`, `user-place.js` |
| Keyboard | `keyboard/AGENTS.md` |
| Focus and navigation | `focus.js`, `standing-target.js`, `navigation.js`, `queue-walk.js`, `history.js`, `user-intent.js`, `walk-position.js` |
| Asks | `asks/` |
| Comment capture | `composing/`, `drafts.js`, `media.js` |
| Threads | `thread/`, `thread-panel.js` |
| Annotation inventory and controls | `annotation-inventory.js`, `annotation-view.js`, `contributions.js`, `contribution-controls.js`, `inline-contributions.js` |
| Annotation records and Page Map | `margin-model.js`, `margin-map-model.js`, `page-map-dialog.js`, `pointed-place.js` |
| Physical annotation presentation | `annotation-overlay/` |
| Passages and target identity | `passages.js`, `passage-facts.js`, `text-alignment.js`, `anchor-coordinate.js`, `resolved-target.js`, `anchor-resolution.js`, `addressable-names.js` |
| Anchor placement, decoration and travel | `anchor-placement.js`, `anchor-note-view.js`, `anchor-controls.js`, `anchor-travel.js`, `target-paint.js`, `target-paint-geometry.js`, `visual-parts.js`, `indication.js` |
| Banner and approvals | `banner*.js` |
| Drawers and neighboring pages | `drawers.js`, `queue-panel.js`, `queue-list.js`, `live-leaves*.js` |
| Activity and reports | `presence.js`, `activity-words.js`, `reports.js` |
| Notices and announcements | `semantic-news.js`, `notifications.js`, `keyboard/shortcut-bar.js` |
| Reactions and design review | `reactions.js`, `design.js`, `design-readings.js` |
| Presentation and validation | `presentation.js`, `declared-words.js`, `validation.js`, `projection-watch.js`, `retained-face.js` |
| Child pages | `sample*.js` |
| Shadow trees and styles | `shadow.js`, `shadow-stage.js`, `stylesheets.js` |
| Elements a paint belongs to while they stand, and the stages they stand in | `arrivals.js` |
| Utilities | `abort.js`, `icons.js`, `markdown.js`, `syntax.js`, `motion.js`, `color-scheme.js`, `storage.js`, `interaction-log.js` |

The executable body declaration `data-annotations` selects the physical overlay
or page-owned presentation. `leaf.js` imports `runtime/annotation-overlay/index.js`
only for overlay presentation; no other owner can reach that graph. Core retains
target readings, inventory, native controls, Thread/composer lifetimes and
active/draft drawing ink. The overlay owns pins, contextual floating placement,
posted drawing paint, marks and annotation visibility. Page-owned views consume the
same owners through `widget-api.js`.

`runtime/rendering.js` runs every rendering callback in one pass per frame; schedule
through its `nextRender`, `nextFrame`, `cancelRender`, and `sizeObserver`, since
lint refuses the browser's own.

The browser moves what a scroll moves. A box that follows page content stands where
CSS puts it, by an anchor, a sticky offset, or a scroll timeline, and no scroll handler
writes its position, which would trail the scroll by a frame. Paint over the page's
targets, whether a box, a chip, a mark or ink, stands in a paint set
(`target-paint-geometry.js`, `paintSet`); what a scroll changes about it, such as which
chip the banner holds in, is read once the scroll settles (`arrivals.js`,
`watchScrollEnds`). Every write says only
what changed (`runtime/keeps.js`): while a highlight holds a range, Chrome repaints the
whole document for any write, so a write per scroll event makes every page with a
quoted comment judder. One place has one writer: two owners that each set it in turn
rewrite it every time either paints. A paint that more than one step of a script asks
for waits for the script to end (`rendering.js`, `afterScript`), rather than painting
the step between. The browser fixture fails a write that changes
nothing in any test (`tests/write_watch.js`), `test_page_fixture_renders`
fails a place a scroll writes on every step (`scroll_findings`), and
`test_a_scroll_carries_paint_over_targets_and_writes_it_once_settled` fails paint
a mode writes on a scroll gesture's frames.

What a page says follows from where it stands now, not from how it got there. The one
history its arrangement keeps is the order its margin rows came in, since a row that
arrives yields to those already there rather than moving them (`margin-layout.js`). A page
nobody touches writes nothing, asks for no frame, and moves no focus; a surface opened
and closed again leaves the page as the last time did, holding no more nodes or
listeners; a page resized says at each width what it said there before. So whatever
sets a state also clears it, when the width or the gesture that called for it ends,
and "none" has one spelling, the attribute's absence, which `keeps` writes for a null
value. The corpus holds each rule, in
`test_page_fixture_renders`.

Stylesheets apply in cascade layers, in the order `layer.py`'s `CASCADE_LAYERS`
declares and `../references/packages.md`, "Styles and composition", describes;
`state.css` takes the top tier so semantic retirement wins over package defaults,
Layouts and theme packages, whose `lf-theme` tier sits above the Layouts. `theme.css`
holds page tokens, element styles, idioms, and CSS-only widgets, and each package theme
follows it; shared shadow rules compose into `/shadow.css`, whose shared native
`.lf-ui-face` defaults come before component rules. Custom-element hosts own their
appearance; `.lf-ui` marks apparatus without imposing a face. Each widget package's
rules reach only its own widgets (`layer.py`, `widget_confinement`), so a rule several
packages' widgets need is the kernel's. The page's rules, and a theme package's, skip
the chrome and every `.lf-ui` control unless they name a widget or the layer's
vocabulary (`runtime/page-sheets.js`). The chrome's root and native `.lf-ui-face` defaults
state the face they would otherwise inherit from the page; imported components
receive theme variables, preserving their own state presentation.
`runtime/stylesheets.js` owns chrome and mark precedence, including the overridable
indication default in `runtime/marks.css`. Chrome and apparatus marks are adopted
after page and package sheets. `runtime/marks.css` is adopted by the document and
shadow stages. A `:has()` whose rightmost compound carries no class, id, attribute, or
type restyles every element on ordinary runtime writes
(`test_no_has_rule_restyles_the_whole_document`); key a repeated type by a class
its owner writes. A `:has()` on the chrome root, `body` or `html` is read again on
every write below it and restyles it (`test_no_has_rule_stands_on_a_root`), so the
owner of such a condition states it as an attribute on the element the rule styles.

### The browser answers first

The browser runs a layout engine, a cascade, and a focus model on every page. A script
that recomputes one of their answers disagrees with them under zoom, subpixel
rounding, a transform, or the page's own CSS. So before a module measures, positions,
stacks, isolates, or tracks something, find the browser feature that already decides
it, and shape the markup and CSS so the runtime uses its answer:

| Question | The browser feature that answers it |
| --- | --- |
| How large a box is, including the widest of several labels | grid and flex tracks, `min-content` and `max-content`, labels stacked in one grid cell, a label's room drawn invisibly beside its words (`data-lf-room`) |
| Where a box stands against another box or the scroller holding it | the containing block, sticky positioning, anchor positioning, scroll timelines |
| Which of Leaf's surfaces paints over which, and that the page paints beneath them all | the top layer, and stacking contexts: the theme's `--lf-z-*` ladder, and `main` as one context at 0 |
| Whether a box is rendered at all | `checkVisibility` |
| Which rules reach an element | cascade layers, `@scope`, and a shadow root as the boundary |

Where the feature nearly fits, change what the runtime asks of it, such as where a
box lives in the DOM or which element carries a style, rather than computing its
answer. A module that answers one of these questions in script says why in its
header: the requirement the feature cannot meet and the case that shows it. A review
asks for that reason, and a change that adds a script answer without one does not
land. Patching a built-in prototype or a dependency's internals needs the same reason.

Some questions already have script answers. `focus.js` paints
`data-lf-focus` and `data-lf-focus-within` because native `:focus` also matches
retargeted shadow hosts and a held label press, so style focus on those marks.
Whether the user can see a box, and what covers it, stay with `geometry.js`
(`seenRect`, `declareOccluder`), since Leaf's chrome stands over the page without
clipping it, and some of it, such as the shortcut bar, takes no pointer hits for
`elementsFromPoint` to find.

Each rendering callback gathers its layout reads before it writes: a read after a
write forces a synchronous style and layout. A document-wide renderer that reads DOM
another one materializes takes an entry in `PRESENTATION_ORDER`
(`runtime/semantic-state.js`), which says why CSS or the publication cannot supply
that reading.

### One writer for each fact

Each mutable fact has one authority and one browser writer. The application publisher
combines authored state, the admitted server reading, and the ordered ledger of
unresolved local work into the one reading every component selects from:

| Fact | Authority |
| --- | --- |
| authored widget state | validated source markup, staged before upgrade and admitted atomically with descriptors and revision identity |
| external data | the latest page data reading; `watchData` delivers each bound source |
| version shown | the revision the delivery prelude names; a newer revision with the same executable identity patches in place, a different one navigates to a fresh document |
| accepted history, and the reading applied | the server event log and its `/api/state` answer, adopted whole by the publisher |
| unresolved browser work | the publisher's one ordered ledger |
| thread, workflow, attention, asks, to-dos, activity, unread | the server's folds; the browser adds only its own unresolved sends and the versions it is marking read |
| what is waiting on the user and on the agent, and what is done | the server's selection (`served_state.queues`), which `page state` prints; the publisher places this tab's sends against it (`localQueues`) |
| what the DOM represents | the presentation coordinator's renderer tickets and preparation regions |
| when a document-wide renderer paints | the publication that opened the epoch, in the order `runtime/semantic-state.js` declares |
| where each thread's passage lands | `anchor-placement.js`'s resolution of its anchor in this version |
| the row inside a target a comment stands by | `pointed-place.js`'s points, written only by anchor placement's pass (`placePoints`) into its placement record; presentation only |
| the side and line a comment's box and its thread card stand by | `annotation-overlay/comment-placement.js` (`commentSide`), for both surfaces |
| whether a margin row stands in the rail or as a pin, and its seat | `annotation-overlay/margin-layout.js`, through `margin-placement.js`'s folds |
| geometry readings: what a scroller shows, what a surface hides, what sticky headers stand over, how much of the window the page shows, where a change of size moves what is seen | `geometry.js` (`visibleBand`, `declareOccluder`, `headerInset`, `shownWindow`, `seenRect`, `motionBand`), so being on screen, and moving what is, each have one answer |

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

### One answer for each question

A question the runtime asks in many places has one owner, which every caller asks. A
second copy usually starts where a symptom appeared and its author did not find the
first, then drifts from it at the edges: under a stuck header, in a shadow tree, in
right-to-left text. Before writing a predicate or reading, or approving one in review,
look for its question in "The browser answers first", then here. A change that
creates an owner adds its row; a caller that keeps its own test says why beside it.
Rows marked *lint* are enforced in `eslint.config.mjs`.

| Question | Owner |
| --- | --- |
| Where the user stands: focus inside open shadow trees, or a label press holding them; asked in one tree, the node standing for it there | `focus.js` `focused`, `focused(tree)` (*lint*) |
| Whether the user stands in a scope, across shadow trees and slots | `focus.js` `standingIn` (*lint*) |
| The user's working place, read before something borrows it and handed back after | `history.js` `readPlace`, `returnPlace` |
| Where a page walk starts, and which item it steps to from there | `standing-target.js` `walkOrigin`, `stepFrom` |
| Which of two nodes the reader reaches first, across shadow trees | `shadow-tree.js` `renderedOrder`, `byRenderedOrder` |
| Whether a node stands inside another across shadow trees, by composed parents or as rendered | `shadow-tree.js` `under`, `renderedUnder`, `composedParentNode` |
| Put the user on an element, saying what moved them | `focus.js` `focusDestination(node, cause)` (*lint*) |
| Place a node that may already stand somewhere, keeping the user's place in it | `dom-move.js` `move(parent, node, before)` (*lint*) |
| Make a list of nodes, some already placed, a parent's children | `dom-children.js` `setChildren` |
| Whether a control takes typed letters | `focus.js` `typesText`, `takesLetters` |
| Which keys move a caret, and whether a key is Select All | `control-selectors.js` `CARET_KEYS`, `selectsAll` |
| A hint map's walk and choose rows | `keyboard/hints.js` `createHintSession`, its session's walkRows |
| Which focused control counts as the user's place: shown, and not under a stuck box | `user-place.js` `focusedInView` |
| Whether a click came from the keyboard | `pointer.js` `pressIsKeyboardActivation` |
| Whether a press is the plain one a control claims: primary button, no modifier | `pointer.js` `plainPress` |
| Which arrow means back along a row, in its text direction | `keyboard/bindings.js` `rowArrows` |
| Whether any of a node is in front of the user | `geometry.js` `seenRect`; past top-layer surfaces, `clipsPastSurfaces` |
| Whether a change of size there would move what is seen | `geometry.js` `motionBand`, `growthIsSeen`, `growthAfterIsSeen` |
| When none of some nodes is seen any more | `geometry.js` `whenNone` |
| How much of the window the page shows | `geometry.js` `shownWindow` |
| The window's box, less its scrollbars | `geometry.js` `layoutWindow` |
| Whether the page puts a node before the user at all, what the pages holding it show of its window, and when either may have changed | `geometry.js` `presented`, `containingView`, `frameView`, `watchRoom` |
| Whether a box standing against a target belongs in layout yet | `geometry.js` `nearWindow`, `nearObserver` |
| Where an element-or-Range destination stands, and what clips leave of it | `geometry.js` `placeBox`, `clippedPlace` |
| Whether a box is stuck, and the band sticky headers cover | `geometry.js` `stuckBox`, `headerInset` |
| Whether a box scrolls, for a script or for the user | `geometry.js` `scrollContainer`, `scrollport`, `userScrollport` |
| Which axes a box clips | `rect.js` `clippingAxes` |
| Whether a box is at its scroll end | `scrolling.js` `atScrollEnd`, `SCROLL_SLACK` |
| Whether the reader chose where a box stands, or layout put it there | `scrolling.js` `chosenSince`, `placeKept` |
| The page's `main` | `passages.js` `pageDocument` |
| Whether a place is already shown, and the room a landing needs | `landing-scroll.js` `alreadyShown`, `landingRoom` |
| Bring something into view without scrolling the page around it | `landing-scroll.js` `scrollIntoView` (*lint*) |
| Open or close a native modal or popover | `keyboard/layer-stack.js` `showNativeLayer`, `closeNativeLayer` (*lint*) |
| Whether a node is an open native layer, of which kind, or stands in one as rendered | `shadow-tree.js` `nativeLayerKind`, `isNativeLayer`, `nativeLayerHolding` (*lint*) |
| Which native layers are open, in opening order, and whether a modal admits a node | `keyboard/layer-stack.js` `nativeLayers`, `nativeModalAdmits` |
| The element a URL fragment names | `anchor-resolution.js` `fragmentTarget` |
| The language a file path means | `syntax.js` `langForPath`, from the registry's `$languages` |
| Paint on the next frame, or watch a size | `rendering.js` `nextRender`, `nextFrame`, `sizeObserver` (*lint*) |
| Write a DOM value only when it changed | `keeps.js` `keeps` |
| Threads, workflow, attention, asks, settlement | the server's folds, under "One writer for each fact" |
| Which asks a region of the page holds | `asks/place.js` `asksIn` |

### Facts both runtimes know

A fact Python and the browser both use, such as an event kind, a registry key, or the
languages a page can highlight, has one home, so the two runtimes cannot disagree
about it. Either one language owns it and the other receives it as data, as the
browser receives the server's folds in `/api/state`, or the registry declares it,
Python reads it there, and the browser's copy is generated from it, as
`build/registry.mjs` writes `runtime/syntax-languages.js` from `$languages`. A parity
fixture or a test that scans one language's source for the other's names keeps two
copies in step instead, so in review a new one is a flag that asks why the fact is
not generated.

## Startup and presentation

`leaf.js` boots in this order, each step relying on those before it:

1. Construct every owner, then adopt sheets, attach chrome, mount the owners, and wire
   the repaint phases, so no input is wired before its owner exists.
2. Begin the first state read, without applying its answer.
3. Restore the user's arrangement from storage.
4. Fetch and validate the registry.
5. Index passage fences and parent identities, then capture each widget's
   descriptor and typed authored state from the source DOM.
6. Publish that document contract once.
7. Import the modules `x-upgrade` declares for the tags present, and no others.
8. Run the dressing passes and wait for the coordinator publication.
9. Join the page-interface owners' reconciliation (`PAGE_INTERFACE`), separate from
   this document's semantic proof.
10. Land a fresh URL's fragment, prepare anchor-dependent chrome, then stamp
    `data-lf-upgraded="1"` and open comment capture against the shown document.
11. Start the state feed; its first answer presents the page. A failed or expired
    read presents offline; an unanswered request keeps its loading status.

Authored HTML paints immediately, and the render-blocking theme reserves the
banner and bottom bar so mounting the runtime moves nothing. Prose, links, and
scrolling work while widgets upgrade. New comments, anchors, drawing and their
keys work at upgrade, while private thread history still says it is loading.
The bootstrap holds printed keys before upgrade; the controller replays them
in order as each command's declared input becomes ready. A history-dependent
key keeps its ordered run until presentation, while any other key or a pointer
press drops the held run. Ordinary UI commands use the shown document immediately;
commands that need saved readings declare that dependency. Offline presentation
discards pending keys and ends startup capture. Decision commands await the canonical
saved reading
(`../references/module-authoring.md`, "Startup and presentation"). An async
producer joins settlement before `data-lf-upgraded`, or stays off the
presentation path through `afterPresentation`, which waits for presentation before
starting it, or `deferredArrival`, which counts work already running. Both declare
the deferred arrival, so `pageReadiness` still answers for it and startup lands the
fragment again once it has. Work stays on the presentation path when the page reads
it or when its landing would move what the reader sees (`growthIsSeen`), as a live
sample's child does only where its frame's resize would be seen (`lf-sample.js`).
`presentPage` owns initial authoritative presentation; its synchronous
`PRESENTATION` signal lets
box-derived apparatus replace provisional geometry before the presented state
paints. A reader outside the page waits on `pageReadiness`, through
`wait_until_ready` in Python, rather than combining these stamps.
`renderingState` in `runtime/rendering.js` supplies its last stage and a live
reading of its own: `updatesSettled` says chrome has caught up with queued work;
`preparationsSettled` says registered finite preparation has landed. Full readiness
requires both; readers inspecting intermediate paint can select the first.

## Authoritative projection

Python owns ask membership, widget completion and thread settlement. The server
ships complete page and frozen-thread inventories as `document.asks` and
`thread.asks`; prose asks join that same thread inventory. An ask
contains its source, prompt, typed answer, status and next actor. The browser
selects each widget answer from the same local-inclusive state its controls draw,
without folding its `x-awaits.answered` completion rule again. A required-version
approval is another ask source: its local approval or undo updates its contained
answer and status immediately, with refusal restoring the admitted reading. A thread
gesture changes no served thread's attention and no ask until the server's reading of it
arrives (root `AGENTS.md`, "Responsiveness"). Asks derive their queue rows directly, while to-dos hold
explicit committed work. Every state read has
one `through_seq`, and version comparison asks `/api/view` at the sequence
already applied. A page widget's projection stops at the current revision; a
widget in frozen thread markup reads the whole log. `restated` and answered
reports persist through version notes, so silence in a later version does not
revive retracted state. The server keeps no refusal receipts, because the
condition behind a refusal can change without the user's words changing.

## The widget vocabulary stays open

Core names a widget only when it is part of how Leaf works (root `AGENTS.md`, "Keep
the layer open"; the merge grains are in `../references/packages.md`, "Package
contract"). Each `x-` key's meaning is its `$keys` entry in `registry.json`. Use a
boolean only when false has one clear meaning; otherwise declare named values.

The Python reader models only transformations the registry declares. A module that
changes text in a way the file cannot reproduce is fenced: browser capture stops at the
fence, so a selection crossing it never becomes a quote the file cannot confirm.
Declare modelable words with `x-says` or the content key, and keep a
widget fenced when its transformation cannot be represented.

## Render gates

Run `leaf page check <page> --render`, or the relevant browser test file, after
changing `leaf.js`, a runtime owner, a widget module, the registry, or the theme;
`../scripts/leaf/validation.md`, "Browser validation", lists what it reads. Put a
check on the side that can observe the fact: static validation owns schema, ids,
nesting, passages, event shapes, and file readings; the browser owns computed layout,
composed trees, module writes, focus, and replay idempotence. A test reads widget state
through the publisher's own reading, never a test-only interpretation of it.

The gates judge contracts, not how the page looks. A change to what the page
draws, including one made for geometry, is proved with before/after screenshots
of each state it touches. `uv run leaf-dev stills` takes them for a catalogue of
states and crops the ones that changed (`/developing-leaf`, "Prove and hand off a
visible change").

## Working on the runtime

`../references/module-authoring.md`, "Template rendering" and "Retained nodes", own
container ownership and how placements keep the user's place. Paints whose contract requires the current
turn use `render`; `LitElement` schedules updates on a microtask and belongs only to
runtime faces that permit that delay.

A watcher's paint subscribes to every selection it reads (`projection-watch.js`), so a
reader a paint can call derives what it returns inside its own selection (`readPart`)
rather than selecting a broader part and narrowing it afterwards: the paint then runs
again only when that answer moves. Reading the whole root inside a paint throws.

`build/browser/build.mjs` compiles the TypeScript foundation into
`vendor/browser-runtime.js` and the modules beside it in `vendor/browser-runtime/`,
which import the runtime's own modules, and writes `vendor/lit.js`, the page's one copy of Lit
(`build/AGENTS.md` owns the commands). What a module decides on its own is
tested under `tests/runtime/` (`pnpm run test:runtime`; `tests/AGENTS.md` says
which readings may go there). `pnpm run check:browser` type-checks every runtime
module, `leaf.js`, and the kernel's and packages' widget modules; a module marked
`// @ts-check` is held to strict mode, and the rest are checked without it. A module
imports the framework by its served path, `/vendor/browser-runtime.js`, which the
check reads as the framework's TypeScript source. What the classic scripts hang on
`<html>` and `window`, the events the runtime dispatches with a detail, and the
runtime's own elements by tag are declared once in `build/browser/runtime-globals.d.ts`
(`build/browser/build.mjs`, `typecheck`).
