# The page in the browser

This file holds the browser rules that span modules: how pages look and move, module
boundaries, which code owns each fact, and the render gates. Each module's header owns
its local contract, the contracts modules and packages build on are in
`../skills/leaf/references/module-*.md` and `../skills/leaf/references/packages.md`, and the rules shared with
Python are in root `AGENTS.md`, "Cross-runtime invariants".

Stylesheets need no build: page composition and the serving runtime place each file a
sheet `@import`s where the import stands (`stylesheet` in `src/leaf/source/layer.py`).

## Leaf's interface

These rules hold for everything Leaf draws: its runtime, its chrome and its bundled
packages. Each section opens with a goal, which
`../skills/leaf/references/interface-goals.md` gives other authors too, and the specs
under it are Leaf's own ways of meeting it; weigh a case no spec covers against its goal
and `../skills/leaf/SOUL.md`. A spec is guidance toward its goal, weighed
as root `AGENTS.md`'s opening says: a change that meets the goal more simply rewrites
the spec and its check. A spec names its check and owner where one exists. How
the owner meets it, and any exception the user chose for one surface, belong in that owner's header and
the check's credit, not here. Which specs should also bind other authors is still being
settled. Leaf targets desktop first, so judge layout at a representative desktop
viewport.

### The page holds still under the user's aim

A change the user didn't make moves nothing they are reading, pointing at or typing into,
since that would take their place and their aim away in the middle of the task
(`../skills/leaf/SOUL.md`, "Preserve the user's attention and work"). Every hold costs
code on each later change, so the guarantee is owed to the paths users take often: a
rare path the user takes in at a glance may move what is on screen rather than carry a
mechanism of its own (`../skills/leaf/SOUL.md`, "Keep Leaf's code plain").

A hold rule is tested in `tests/journeys/test_page_holds_still.py`, whose cases cross
places the user can be with changes that can arrive. A new rule joins it as a place, a
change or a move the user chose, and takes no browser test of its own, so each rule is
stated once and a new surface costs one row. Run the cases a change adds or touches by
`-k` before handing over: a new row leaves the test function as it was, so a pull
request's `test` job doesn't select it (`../tests/AGENTS.md`, "Run what the change
needs"). A separate test is for what those cases don't measure, such as that news the
rule draws at once is drawn.

- **Controls stay where the user aims.** A state change may repaint any box. What a
  press changes grows or shrinks its box away from the edge the box holds (next spec),
  whatever was pressed, so a pressed control between that edge and the change stays
  where it was, and one past the change moves with it, as a disclosure opening above its
  button moves the button down. A box that holds its size while the press acts keeps the
  control still. That is the platform's rule: CSS scroll anchoring prefers a focused text
  field or the find match as the node it keeps still, never a pressed control. When the
  press removes the control, the press's result takes its place, and that may be the
  next item's same control, as when Resolve in the floating panel moves the user on to
  the next thread (`panel/floating-panel.js`); a change the user asked for may reflow what it
  replaces, with motion the eye can follow. A scroll the gesture makes carries the
  pressed control only to bring it whole into a scroller that showed part of it, or
  where the gesture says it takes the user somewhere. Without a gesture, as when news
  arrives, a box may grow or shrink into free room, but reading content and controls
  stay put. The exception is a thread card narrower than
  the measure, which the user chose to let widen once, from its start, when a long message
  arrives, carrying its controls (`data-lf-widens`; `annotations/annotation-overlay/thread-preview.js`).
  No hard-to-undo action arrives under a pointer
  that hasn't moved. A reveal on hover, focus or a key never moves its ancestors or
  siblings, and typing may grow a field but never moves it. Check: `tests/shift_watch.js`,
  whose header lists what it credits.
- **A box's controls stand on an edge the box holds as its content changes**, or the
  box holds its size while they act. A thread card holds the edge it is attached by,
  and beside its subject the top of its reply box while the user writes words in it; the
  floating panel, standing on the window's foot, holds a list's foot, and a thread's
  height while a press on its head line acts. Each box's header says how (`panel/floating-panel.js`,
  **Opened**; `annotations/annotation-overlay/thread-preview.js`).
- **News moves what the reader reads only in the thread they are in.** News from the
  server grows above the screen, where scroll anchoring absorbs it, or below it. In the
  thread the user is in, what it adds draws at once, as in a chat: the page scrolls
  what stands above the control they are on up by the growth, and where the page can't
  scroll that far the control moves by the rest. Anywhere else on screen, and for a
  settlement (resolving or reopening) in their own thread, a thread keeps what it drew
  behind a fixed-size control until the reader goes to it. A thread not drawn yet, one
  the agent starts or one a reply reopens out of a closed Resolved disclosure, draws at
  once, the rare path the user chose to let move what follows it. An
  exception the user chose stays with its owner, as the floating panel's growth for an
  answer the user waits for (`panel/floating-panel.js`) does. Where news grows a thread's own
  box, the panel's view or a margin card, the growth may carry the box's secondary
  controls, such as Resolve or a message's pencil, from under a pointer resting on one;
  the words the user is writing and their Send stay (the user's choice). What news moves
  there travels to its new place rather than jumping, as the user chose: a view that
  scrolls glides to its end (`records/thread/thread-card.js`) and one that grows carries its
  parts (`dom/box-motion.js`).
  Check: `test_news_just_after_a_press_moves_nothing`. Owners: `records/thread/held-news.js`,
  and `threadsListing` in `panel/floating-panel.js` for the rows of Threads.
- **What the reader reads stays put through re-renders and revisions.** The browser's
  scroll anchoring holds it while content above changes height, so a render keeps the
  nodes it doesn't change, as a revision's patch, a widget whose module declares `lfPatch`
  and a message's words (`setRenderedChildren` in `dom/dom-children.js`) do. Leaf turns
  anchoring off in a box the reader reads in only while its own motion moves the box,
  as a glide does, whose landing then places the destination (`dom/scrolling.js`), or the
  box's content, as a ride does (`dom/box-motion.js`). A revision then restores the reader's
  landmark (`features/version.js`). One Leaf hold, acting once, keeps what anchoring can't: the
  control under the user's hands; for a reader whose focus is scrolled away, the
  reading line where growth starts between anchoring's box and it; and a place the
  change hides. A reader who focused nothing is anchoring's to keep. A reading from outside the tab
  takes it where it is applied and keeps it once the page shows it
  (`host/state-application.js`), whichever surfaces the reading redraws. A surface that
  changes with no reading behind it takes the same hold around that change, as Page
  Map does when a widget's own contribution joins it, and the dial around its fold; a
  gesture's own result is its handler's to place. Owner: `readings/user-place.js`
  (`holdUserPlace`, `holdPlace`, `holdPlaceOf`), whose header records the costs the
  user accepted.
  Checks:
  `test_an_edit_above_the_paragraph_read_holds_it_with_the_reply_box_scrolled_away`,
  `test_a_thread_joining_page_map_above_the_row_the_user_is_on_leaves_it_still`.
- **Nothing Leaf draws moves the page's content.** Pins, passage marks and runtime
  controls sit over the page and take no space, and no rule pads or widens a block to
  make room for them. The rail sits right of `main` when the window is wide enough and
  never moves or narrows the column (`../skills/leaf/references/page-layout.md`, "The
  rail and the margin"). Native block flow and wrapping rows place the page's own
  sidebars and notes from the first paint, and `runtime/readings/content-layout.js` reads their
  CSS geometry for annotations and never reallocates document space. The floating
  panel stands over the page too, with no room kept for it: the page lays out in the
  whole window, and the user folds the panel to its leaf where it covers what they
  read; it folds itself where focus lands on a place it alone would hide
  (`panel/floating-panel.js`, `giveWay`). Leaf's landings and readings of what the user sees count the panel's box
  (`dom/geometry.js`, `declareCover`). Checks:
  `test_a_comment_leaves_its_block_as_the_page_wrote_it` and the shift watch. Owner:
  `annotations/annotation-overlay/margin-placement.js`.
- **A box floating over the page grows inside the window**, toward the edge that has
  room, and sending and later growth never scroll the page to make room. Owners:
  `annotations/annotation-overlay/comment-placement.js` for attachment and bounds, and
  `annotations/annotation-overlay/thread-preview.js` for the edge a card holds. A freshly opened card
  may scroll to open clear of its target, and otherwise only a field in flow scrolls to
  keep its controls in view (`records/thread/reply-landing.js`).
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
  (`src/leaf/pages/render_gate/widget_quality.py`).
- **Room is held only for what will be drawn.** A state that may never come, such
  as a failed save, shows in a slot already on screen, as a message's head carries its
  delivery status, and the user's gesture makes the room it needs. Feedback may repaint
  a control or change its label, but never its size: `data-lf-room` (`controls.css`)
  sizes a label to the widest of the words it can show. Adjacent actions keep their hit areas
  apart.
- **Shared containers determine control dimensions.** When several modes share a
  container, as the comment field, page search, Threads' search and a thread's reply
  share the floating panel's field, the container sets its dimensions from a theme token
  and each mode's controls fill it. It grows only for content, such as typed words, or
  an explicit action, such as More room. A one-line control's visible height is
  `--lf-line` (`styles/tokens.css`). A field that runs to its frame's edges adds the
  frame's padding to that height, as a thread card's reply box does, a comment box
  does in the frame of the card it becomes, and the floating panel's field does while
  it holds the caret. A control's touch target meets the minimum
  `surfaces.css` sets; a control that derives its height from its font or the touch
  minimum instead changes the height of every container that holds it. Checks:
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
away or moves them out of reach (`../skills/leaf/SOUL.md`, "Preserve the user's
attention and work").

- **Typed words stay in their native editor until the user puts them away.** A box
  holding words closes only on a key or press meant to close it (Send, Cancel, Escape, a
  press elsewhere, another target) or when its subject leaves the document, never on a
  scroll, resize, timer or server news. Geometry decides where the box sits, never
  whether it exists: a box a scroll carried away comes back when the user types into it
  (`readings/off-flow.js`), and Resume writing (`g i`) shows the same editor. A re-render that
  replaces the box's node hands its words and caret to the replacement. Checks:
  `tests/words_watch.js` and `typed_box_findings` in the render gate tests. Owner:
  `annotations/annotation-overlay/composing/floating-response.js`.
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
  Owners: `records/thread/message-edit.js`, `.lf-msg-editor` in `styles/components/response.css`,
  and `annotations/composing/text-field.js`.

### A gesture shows its result at once

What the user's act decides by itself appears as they make it, so they see that it took
effect without waiting on the server (`../skills/leaf/SOUL.md`, "Make the work
concrete and playable"). Root `AGENTS.md`, "Responsiveness" and "The document starts state; the log
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
  words to their box (`standGesture` in `records/drafts.js`), an undone message or rewrite
  returns them to the draft they were written in (`giveBackWords`), and a gesture that
  moved the user, such as resolving a thread, leaves them at its place again (`records/undo.js`
  owns where undo leaves the user).

### Controls are few and quiet

Leaf's controls compete with the page's own words for the reader's attention, so each
earns its place against the content and takes no more room or emphasis than its task
needs (`../skills/leaf/SOUL.md`, "Let the user work as directly as in a terminal").

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
  action from `ACTIONS` in `runtime/lib/icon-paths.js`, which gives it the action's
  symbol, and says its name as its accessible name and its preview (below), without the
  word beside the symbol.
  An action shows one symbol, or one word, wherever Leaf offers it, so a reader who
  learns it in one place knows it in every other, and a press names an action, never an
  icon, so its symbol can't drift. One control whose symbol follows its state, such
  as play turning to pause, replaces a button for each state. A symbol only related to
  the action, such as a speech bubble for answering a question, leaves the reader
  guessing, and a preview doesn't fix that: the reader must already suspect the control
  to point at it. The rows of the leaf's menu keep their words, since the user opened
  the menu to read them. A reaction shows its emoji with no word, since the emoji is
  the message the user sends rather than a symbol for an action: the maintainer chose
  to let the user and the agent work out what each emoji means between them.

### Pointing reads; pressing acts

Hovering, Tabbing onto or holding a press on a mark, control or value shows its whole word
and a preview of what pressing it opens, or of the fact it stands for, so the user can
judge whether to go there before going (`../skills/leaf/SOUL.md`, "Make the work
concrete and playable").

- **A preview reads and never acts.** It says where a thread stands, what a link points
  at, what caused a change or the time behind an age; a control's says its word and
  each key that presses it from where the user is, as a key chip. Every preview wears one face, its name
  and key chips on the first line and its detail under them. It stands over the page
  beside what it previews, where the browser keeps it as the target moves, clear of
  the target's focus ring and inside the window, covering none of the targets beside
  it where a side is free of them, moves nothing around it
  ("The page holds still under the user's aim") and holds no control. The pointer can
  cross onto it and read it there (WCAG 1.4.13). Revealing a block's own controls, as Copy appears on a
  code block, is no preview and stays its block's.
  A thread's words and its margin entry read one preview, made from the reading every
  surface paints the thread from (`threadPreview`), and an age reads its clock time in
  the reader's zone (`agePreview`). Checks:
  `test_a_thread_previews_where_it_stands_from_its_words_and_its_entry`,
  `test_an_age_previews_its_clock_time_in_the_reader_s_zone`.
- **Every route that aims reads it.** A resting pointer reads it after a short dwell,
  keyboard focus Tab or Shift+Tab moved at once, since Tab is the keyboard's pointing,
  and a finger by a long press, the touch form of pointing, whose release presses
  nothing and leaves the preview standing until the next press, while a tap still
  presses, so a finger reads without acting and without sliding off, which on touch
  often scrolls instead; where a surface
  can't take a hold, it says the words at rest, as a panel row's cut words stand whole.
  So no fact is said to hover alone. A command's landing reads nothing: a walk such as
  `m`, an arrow key, a surface placing focus as it opens or handing it back as it
  closes. What the user asked a command for is the place it lands on, already in front
  of them, so a preview there would cover it and take their next Escape, and `K` reads
  it there on demand, inside a modal dialog too, as an editor's hover key does
  (check:
  `test_a_walk_s_landing_previews_nothing_and_tab_reads_it`). `K` also reads where
  the caret stands, inside what focus is on or anywhere while nothing has focus.
  Caret browsing in Chromium and Firefox walks the caret through words that take no
  focus, so there an element such as an age previews to the keyboard without a Tab
  stop of its own (check: `test_k_reads_the_caret_where_no_tab_reaches`). Safari has
  no such caret, so an age reaches the keyboard there without one: a row that shows
  an age names its clock time in the row's own preview, and an age an author wrote in
  the page takes a Go-to hint (check:
  `test_an_age_reads_its_time_to_the_keyboard_with_no_caret`;
  `../notes/browser-support.md`, "A keyboard caret in Safari"). A preview the user
  put away stays away until they aim again, whatever the element declares meanwhile. A `title` is its writer's: the
  browser's tooltip shows it to a pointer, and Leaf's preview to focus and a finger,
  so two tooltips never stand together. Leaf's own controls declare their words to the
  preview and write no title on Leaf.
- **A preview says what its target doesn't.** It carries what the user can't read
  where they aim: where a link or mark leads and what waits there, the fact behind a
  compact face, as the clock time behind an age or the value under a chart's point, a
  symbol's name, and the keys that press it. It never repeats what the target or what
  stands beside it already shows whole, such as a control's label, a menu row's key
  chip, a figure's caption or a row's heading, and a figure, chart or drawing previews no
  name of its own, since its content is what the user is looking at. Words a box cuts
  short, the target's or one around it, aren't shown, so their preview reads them whole.
  What has nothing more to say previews nothing. The browser's tooltip answers to the same rule: a `title` or an SVG
  `<title>` shows over everything inside it, so Leaf names a drawing for a reader who
  can't see it with `aria-label`, as `lf-diagram` does with Mermaid's `accTitle`, so no
  diagram shows its name as a tooltip (check: the `lf-diagram` case in
  `tests/smoke/test_plain_page.py`).
- **One owner shows every preview.** An element adds to what pointing at it reads
  (`lfPreview`, `../skills/leaf/references/module-previews.md`), a control's
  word and keys come from its name and the register, a link an author wrote into the
  page shows the place it names (`runtime/annotations/place-preview.js`), and a range's owner says
  where the pointer or a holding finger rests on it, as a thread's passage marks do
  (`annotations/anchor-paint.js`). `runtime/annotations/preview.js` shows one at a time on every route, puts it
  away on leave, blur or a press, and gives a screen reader the words it shows on focus
  as the focused element's description.
  While one stands it is Escape's first step, which does nothing else, so a preview
  over the surface the user is in never costs them that surface (WCAG 1.4.13). Checks:
  `test_a_control_previews_its_word_and_every_key_that_presses_it`,
  `test_a_link_into_the_page_previews_where_it_points`,
  `test_a_range_previews_beside_the_line_the_pointer_rests_on` and
  `test_a_finger_holding_a_thread_s_words_reads_it_above_them`.

### Visual treatment carries meaning

Each treatment draws the eye, so each marks hierarchy or state, and a difference the
reader sees always means something (`../skills/leaf/SOUL.md`, "Let the user work as
directly as in a terminal").

- **Contours are solid.** A dotted or dashed line marks a distinct state, such as a
  drag placeholder. One contour shows one control state, and a segmented group shares
  one-pixel seams. A box edged on one side is never rounded: mark a state with a
  whole contour, or a stripe on a square box. Avoid reflexive cards, tints, gradients and
  soft shadows. Check: `test_no_rule_rounds_a_box_edged_on_one_side`.
- **A box inside a frame either meets its edge or stands clear of it.** A box that
  meets its frame's edge, as the floating panel's field and a thread card's reply box
  do, takes the frame's rounding at the corners they share and is square at the
  others. A box that stands clear, by `--lf-clear` or more, keeps the corners its kind
  takes (`styles/tokens.css`, at `--lf-r`). So does a thumb that slides along its
  track, or a mark round by meaning such as a dot, wherever it stands. Boxes joined at
  seams count as one box.
- **A word about shown material stands outside it.** Where the page shows an
  interface rather than says something, as a capture or a quoted sample does, a word
  about it, such as Before and After or a sample's note, stands on the page just above
  its frame or gutter. Inside, the word reads as part of the interface, which could
  have drawn a band or a heading of its own.
- **One role, one face.** Two controls of one kind look the same, and a face used twice
  is a token or a shared rule ("Layouts, styles and controls", below, says how code
  keeps this).
- **A mark's colour says one thing, the same on every surface.** A mark reads the
  role for whose mark it is (`styles/tokens.css`, "Leaf's own marks"), never a hue, so
  the user's turn, a thread, the agent's work, what is unread, what changed and what
  is settled each look alike in the margin, the contents and the panel. Every surface
  paints a thread's `unread` and `attention` from one value, so the leaf's dot,
  Threads, the panel, a margin entry and the Page Map change together, and marking read
  never moves the user.

### Motion is brief and keeps the user oriented

Motion helps the eye follow a change, and costs the user time whenever they wait for it
(`../skills/leaf/SOUL.md`, "Preserve the user's attention and work").

- **Nothing the user must read, press or decide waits on a clock.** Motion the user waits
  on stays under 300ms. A delay may hide a flicker but never adds a minimum spinner time
  or a staged reveal. `runtime/dom/motion.js` owns the shared motion gate, easing and
  reduced-motion check, and `--lf-motion-*` properties set durations and curves: the
  theme's for the document, and a runtime surface's own sheet for that surface, as
  `floating-panel.css` does for the panel. A script reads one with
  `runtime/lib/motion-timing.js`.
- **Animations are restrained and finite, and acknowledge state changes.** The one continuous animation
  is the sheen (`@keyframes lf-sheen` in `styles/components/surfaces.css`), which marks
  agent work in progress. It stops when the work ends and is static under reduced
  motion.
- **The panel's leaf has a personality, and the user is still evolving it.** Leaf's
  mark answers moments with a brief gesture (`runtime/panel/floating-panel.js`, `MOTIONS`),
  such as a nod at the user's own key or a twirl as On Me empties, and droops while the
  agent is away. A change that adds a moment the user notices, such as a new kind of news,
  asks whether the leaf should answer it (`runtime/transport/notifications.js`, `gesture`). Each
  gesture so far moves the whole mark; giving the mark parts that move on their own,
  such as a blade that flexes on its stem, would give it more dexterity, and `MOTIONS`
  says what that takes.

### A region that must scroll behaves like the document

A region that scrolls by itself splits the reader's place in two, so it moves and is
reached like the page around it (`../skills/leaf/SOUL.md`, "Preserve the user's
attention and work").

- **A necessary scroller works like part of the document.** It passes scrolling on to
  the document at its edges, except at a bounded task or a modal. Wheel and touch keep
  moving through content; pan and zoom need a deliberate control. It has a keyboard
  route, visible bounds and visible focus, which `reachScrollers` in `runtime/dom/reach.js`
  supplies by giving every scrollable box a tab stop and painting the edge its content
  continues past. An object taken out of flow for inspection restores the selection and
  the document position on return. Checks: the reach tests and the axe sweep;
  `/ui-sweep` reviews scroll chaining and the return from inspection.

## Runtime ownership

`leaf.js` only boots the page: it imports the owner modules, each of which exports its
capability, and starts them in the order "Startup and presentation" lists. Classic
scripts run before any module. `runtime/prepaint.js` runs inline in every document,
served or exported. It marks the interactive document, restores native reading state
and reports startup failures. Content remains readable while modules load; controls
activate through their owning widget lifecycle. A failure removes the interactive mark
and names the reason in `data-lf-startup-error`.
`runtime/bootstrap.js` runs in a served page only, stands the floating panel's row from
the first paint, holds keys pressed before upgrade and shows a startup failure.

Of the runtime, content modules import only `runtime/widget-api.js`, the public helper
surface, and the modules of the library ("The library of shared web code"). A widget
that also runs off Leaf imports, in place of `widget-api.js`, only the part of it any
document loads, `runtime/portable-api.js`.
`module-authoring.md` defines these boundaries. Owners
receive their capabilities when constructed and read other owners in their mounts. The
projection, thread and pending models import no DOM or application services.
`../.config/dependency-cruiser.mjs` enforces these boundaries, eslint the runtime's
import layers ("Import layers"), and knip (`../.config/knip.js`) rejects import cycles.
Each reads the paths modules import, so imports use literal paths; only the widget and
interaction loaders compute theirs.

Each module owns one concern and states it in its header, so read the headers to find
an owner (`find runtime -name '*.js' | xargs head -n 3`). "One answer for each
question", below, indexes the owners a caller asks, and `dom/keyboard/AGENTS.md`
covers the keyboard's, in `dom/keyboard/`, `readings/key-badges/` and
`panel/page-keys/`.

`runtime/lib/frame-pass.js` runs every rendering callback in one pass per frame, the
runtime's and each package's alike, and `runtime/base/rendering.js` counts that work in the
settled reading. Schedule through the pass's `nextRender`, `nextFrame`, `cancelRender`
and `sizeObserver`; lint refuses the browser's own, except `requestAnimationFrame` in a
package, which is for motion that may run until the user stops it, such as playback,
and which the settled reading doesn't count. Nothing schedules a second pass beside it:
callbacks on two passes would paint a frame apart. A rendering callback does its layout reads before its writes, since
a read after a write forces a synchronous layout. `getComputedStyle` forces style, and
in Chromium so can a read of the page's selection, such as `rangeCount`. On a Leaf page a
forced style also lays out whatever in `body` is out of date, a closed tab's panel
included: `body` is a size container, and a size query reads it
(notes/browser-support.md, "A style read lays out a size container's contents").

A box that follows page content is positioned by CSS, with an anchor, a sticky offset
or a scroll timeline, because a scroll handler trails the scroll by a frame. Paint over
the page's targets goes through `paintSet` in `readings/target-paint-geometry.js`. What a scroll
changes that CSS can't follow is read again when the scroll ends (`watchScrollEnds` in
`dom/arrivals.js`), unless the reader would see it wrong until then. Such a reading is
taken at each scroll and writes only where its answer changes, as the solve of a
floating box an edge holds in does (`annotations/annotation-overlay/floating.js`), and the paint
that follows whether focus is in sight (`readings/user-place.js`, through `dom/geometry.js`
`whenChanges`).

Lit owns template bindings and skips unchanged values. For imperative writes outside
those bindings, use `keeps` in `runtime/lib/keeps.js`, whose header says what a redundant
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

Stylesheets apply in cascade layers, ranked by whose element a rule styles
(`DOCUMENT_LAYER_ORDER` in `layer.py`; `../skills/leaf/references/packages.md`,
"Styles and composition"): a theme's rules for the author's content below the page's
`base` layer, and Leaf's rules for what it draws above it and below the page's other
layers and unlayered rules. A widget package's
rules name the widgets they style, so a rule several packages need belongs in the
kernel. The page's unlayered rules, its layers after Leaf's and a package's overrides
reach widget controls as they reach the page's own; the chrome keeps unlayered page rules up to one class's
weight off itself (`styles/chrome-guard.css`), and a package restyles it on purpose by
part from its `chrome.css` (`chrome_restyle` in `layer.py`).

### Import layers

The runtime's modules stand in import layers, and a module names only modules of its
own layer and of the layers below it, whether it imports them or names their types.
Each layer is a directory of `runtime/`, apart from two. The entry points form the top
layer at the runtime's top level, since pages, packages and the server load them by
served path. The library (`lib/`) keeps its served path and belongs to the bottom layer.
`runtimeLayers` in `../eslint.config.mjs` lists the layers and says what to do when a
module names one above its own.

### The library of shared web code

Web code that packages share with one another or with the runtime has one home that
any of them can import, so that no package copies it and it adds nothing to Leaf's
interface. `runtime/lib/` is that home. It holds code that keeps none of the page's
state and calls nothing of Leaf's, such as a time axis's ticks or the words for a
thrown value. A function that reads the page's state, the registry or anything else
Leaf composes into a page is not library code, and stays in its owner behind
`widget-api.js`, which gains a name only as `../packages/AGENTS.md`, "A widget's need of
Leaf", says.

- A library module imports only `/vendor/` bundles and the modules beside it, so it
  loads in a document Leaf didn't compose (lint, the library's block in
  `../eslint.config.mjs`). Where it needs a stateless helper of the runtime's, the
  helper's module joins the library, and the runtime imports the helper from there.
- The runtime imports a library module by relative path. A package, a page and a
  render check import it by its served path, `/runtime/lib/<module>.js`.
  `$public-modules` in `runtime/kernel-registry.json` admits a package's or a page's
  import, and lists every module of the directory
  (`../tests/runtime/widget-api.test.mjs`).
- A module holds one concern, and each importer names the module that holds what it
  needs. Nothing in the runtime re-exports a library module, so neither `widget-api.js`
  nor `check-api.js` passes the library on (lint, the same block and
  `ownerRuntimeSyntax`).
- A prepared installation compiles the whole library into the chunk every page loads
  (`portableHomes` in `../build/runtime-bundle.mjs`). So a library module imports
  lazily any `/vendor/` bundle the page's boot doesn't already load.
- A module's header and JSDoc are its whole documentation. The package references say
  where the library is and describe none of its functions.

### What a style rule costs

A `:has()` rule can turn a local write into a restyle of the whole page or chrome. One
rule anywhere whose subject after a `:has()` names no element can make every write to
a state another `:has()` reads, such as a hover, restyle the page
(`test_a_has_leads_only_to_a_subject_naming_an_element` says which subjects name
one), and a condition on the chrome root, `body` or `html` is
re-evaluated on writes below it. A `:has(~ …)` asked of elements most selectors reach,
such as every child of `main`, makes each such write restyle every block before the
one written (`test_a_has_reads_no_sibling_of_an_element_most_selectors_reach`). Prefer
a class that names the targets, or a condition its owner sets on the styled element
or its parent, such as a property a style query reads, and measure with
`leaf-dev bench --read paint --profile`.

A `:has()` on a compound that a combinator follows, as in
`table:has(…) > * > tr > :first-child`, is asked again for every element the rule
tests, and Chromium answers a `:has(> …)` by reading the children afresh each time,
so the rule's cost grows with the square of the sibling group. Chromium keeps its
answer to a `:has()` whose argument starts with a descendant combinator for the
whole restyle, so put one that most elements fail ahead of the exact question, as
`table:has(th[scope="row"]:first-child):has(> * > tr > th[scope="row"]:first-child)`
does, or qualify the compound with a class that rejects most elements. An `@scope`
rooted on the compound also answers once, but its root needs a class, id or
attribute (`test_a_has_leads_only_to_a_subject_naming_an_element`), and it reaches
only the root's subtree, never its later siblings.

No `:has()` reads where focus is, by `:focus`, `:focus-visible` or a mark `dom/focus.js`
writes: each can make every focus move restyle much of the page
(`test_no_has_reads_where_focus_is`). A rule for focus anywhere in a box reads the box's
`data-lf-focus-within` or `data-lf-focus-visible-within` in the box's own compound.
Chromium answers a change to a state that a compound before the subject reads by
restyling every element under the changed one that the subject could match, whether or
not the rule matches there. Focus marks every ancestor of the focused element, `main`
included, and Go-to marks `body`, so a subject naming only a type, as `td` or `a` does,
restyled every cell or link on the page as focus entered `main`. What the box holds
names a class only it carries (toc.css, the map's words), or asks the box for a
property the box sets by a style query on a container the box names (reading.css, the
sticky row names). The query leaves what the box holds alone only while no style under
the container depends on it; once one does, Chromium restyles everything under the
container when the property changes. An inherited property restyles everything the box
holds when it changes, and so does an explicit `inherit` on each element between the
box and its readers. A rule for one control's focus
reads the box that control names with `--lf-focus-box` (base.css), which `dom/focus.js`
marks `data-lf-control-focus` and `data-lf-control-focus-visible`.

An explicit `inherit` of a property that doesn't inherit costs even when the property
stays the same. Once a child of a box writes one, Chromium restyles every child of the
box whenever the box's own style changes, as it does when a mark or ring is drawn on
the box (`test_holding_alt_over_an_article_restyles_none_of_the_sections_in_it`).
Register a property that boxes pass down as inheriting, and set it back on the boxes
it must not reach (layouts.css, `--lf-prose-measure`).

A `::highlight()` rule with no originating element adds to the restyle of every
element, on every page, whether or not the highlight has a range there. Name the
elements whose text the ranges paint. The comment marks can land on any text, so the
runtime marks each element holding marked words (`annotations/anchor-paint.js`, `holdWords`) and
their rules name those. A rule on the root alone would reach other elements only
where highlight styles inherit, and there it pins every mark to the root's tokens and
`color-scheme`, and makes Chromium restyle every element when even a non-inheriting
custom property changes on `html`.

### A rule costs only the elements it could style

A rule should cost only the elements it could style. In Chromium, a rule costs every
element unless it names a key: Chromium files each rule under one id, class, attribute
or type its subject names, and skips a rule at once for an element whose ancestors lack
the key an ancestor compound names. A key counts alone, in an `:is()` or `:where()` of
one selector, or in a nested rule's `&` when the rule it stands in has one selector. A
list names none, so `:is(.a, .b)`, `:where(p, li)` and `&::after` under two selectors
each cost every element a match. Write each member as a selector of its own, as
`.a, .b`. Where a lighter member must keep the list's weight, name the key at no weight
before the list, as `:where(.a):is(.a, .b[x])`, and in a nested rule under a list name
one, as `&:where(.a)::after`. Or give the rule an ancestor that names one, as
`:where(svg) :where(:not(foreignObject *))` does. A subject that can name none, such as
`*` or a frame's edge trims (`reading.css`), costs every element, so write one only for
what every element needs. Check: `test_a_rule_s_subject_names_a_key`, whose docstring
holds the measurement.

### Layouts, styles and controls

- **The page owns its arrangement.** A page arranges itself with a shipped Layout
  class (`layouts.css`) or its own CSS. Leaf owns only what pages and widgets share: the
  bands, the reading measure a Layout sets, and each widget's duty to fill the box it
  gets, declare its minimum, and never widen its container.
- **A Layout, a style and a widget never read one another.** A Layout sets where boxes
  go and how large they are, a style (`base.css`, with its tokens in
  `styles/tokens.css`) sets type, spacing and form as tokens, and a widget reads only
  its own box and the theme's tokens. A widget therefore behaves the same in a shipped
  Layout as on a hand-written page that gives it the same box.
  Where one must react to another, the owner sets a token describing the box, such as
  `--lf-full-height`, and the reader matches it with a style query; a width needs no
  token, since a size query on the reader's container answers it. Before adding a token,
  ask whether a hand-written page with the same box would want the same answer. If not,
  the token describes a Layout rather than a box. Check:
  `test_layout_style_and_widgets_never_read_each_other`.
- **A control wears its role's face.** Code builds a control by its role, with
  `offerAction` or `offeredAction`, and never names a face's classes, so two controls
  of one kind can't look different (`runtime/lib/control-faces.js`, `ACTION_FACES`,
  lists the roles). Only the role's rules in `controls.css` draw a press's ink, ground,
  frame and lift; a difference between two presses of a role is a variant the role
  declares, an attribute on the press, and a surface sets only its type and density. A
  new role needs a difference in the user's task, not only in a widget's taste. Checks:
  `test_controls_are_built_by_role_and_never_by_face`,
  `test_every_press_is_built_by_role`, `test_a_press_wears_its_role_s_face_alone`.
- **Leaf's elements wear only Leaf's names.** A class or data attribute the runtime
  or a package module writes starts with `lf-` or `data-lf-`, the names `page check`
  refuses an author (`../src/leaf/validation.md`), so a page's CSS for its own names
  never reaches Leaf's elements; a page restyles Leaf on purpose through the theme's
  tokens. The kernel's rules name no class a page coins for itself either, so a page's
  own `.button` or `.choice` keeps its author's look. A page's own controls take Leaf's
  faces by element, where its theme turns on markup's reading face, never by writing
  Leaf's names (`styles/components/controls.css`, "The faces of Leaf's control
  roles"); the `lf-` classes a page may write are those a kernel idiom declares, such
  as `lf-scroll` or `lf-tag`, which `page check` therefore lets it write. An idiom's
  rules name the bare words its entry tells an author to write with it, since they
  reach nothing outside the idiom: a variant beside its class, as `.warn` in
  `.lf-tag.warn`, and a drawing's marks inside `svg.lf-drawing`, such as `.box`. The
  kernel's other classes for authors are the Layouts' (`layout-column`,
  `density-working`).
  A library's names on an element Leaf draws for that library, such as Pierre's row
  attributes, stay the library's.
  Checks: `test_leaf_writes_its_own_marks_under_its_prefix`,
  `test_the_kernel_styles_no_class_a_page_coins`.
- **A face used twice is a token or a shared rule.** A lift names one of the theme's
  heights, `--lf-raise-1` to `--lf-raise-3` (`styles/tokens.css`). Check:
  `test_every_lift_names_one_of_the_theme_s_heights_cast_in_the_scheme_s_ink`.
- **Words share a baseline by layout alone.** A row whose words must stand on one
  baseline aligns its items by baseline or sets the words in one face. A row that
  centres words of two sizes leaves their baselines apart by a fraction of the
  difference in their sizes. The user chose to leave that gap rather than close it
  with a strut, a line box shorter than its words or an offset, since each needs rules
  of its own around it and stays right only while a check measures baselines.

### The browser answers first

A script that recomputes what the browser's layout engine, cascade or focus model
already decides disagrees with it under zoom, subpixel rounding, a transform or the
page's own CSS. Before a module measures, positions, stacks, isolates or tracks
something, find the browser feature that decides it and shape the markup and CSS to
use it:

| Question                                                                   | The browser feature that answers it                                                                                                |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| How large a box is, including the widest of several labels                 | grid and flex tracks, `min-content` and `max-content`, labels stacked in one grid cell, `data-lf-room`                             |
| Where a box sits relative to another box or its scroller                   | the containing block, sticky positioning, anchor positioning, scroll timelines                                                     |
| Which of Leaf's surfaces paints over which, with the page beneath them all | the top layer, and stacking contexts: the theme's `--lf-z-*` ladder, inside the chrome's root after `body` at the largest z-index  |
| Whether a box is rendered at all                                           | `checkVisibility`                                                                                                                  |
| Whether a word in a box is drawn                                           | `checkVisibility` of the nearest box, its `content-visibility`, and the word's `visibility` (`readings/passages.js` `drawsWithin`) |
| Where the reader's place stays as content above it changes height          | scroll anchoring, over renders that keep the nodes they don't change                                                               |
| Which rules reach an element                                               | cascade layers, `@scope`, and a shadow root as the boundary                                                                        |

Where a feature nearly fits, change what the runtime asks of it, such as where a box
lives in the DOM. A module that answers one of these questions in script names in its
header the requirement the feature can't meet and the case that shows it, and without
that reason the change doesn't land. The same holds for patching a built-in prototype
or a dependency's internals.

Feature-detect only what a current stable engine lacks, and name that engine beside
the check (`// Firefox lacks ScrollTimeline.`), so the check goes when the engine ships
it. Call an API every engine ships directly, with no fallback, and record remaining
browser gaps in `notes/browser-support.md`, whose "Recording and assessing a gap" says
which ones Leaf's code corrects.

These script answers already exist. `dom/focus.js` sets `data-lf-focus` and
`data-lf-focus-within`, because native `:focus` also matches retargeted shadow hosts
and a held label press; those attributes mark the user's current location, and rings are
styled with `data-lf-focus-visible` and `data-lf-focus-visible-within`, which also
follow the browser's focus visibility. `dom/geometry.js` decides whether the user can see a
box (`seenRect`), because Leaf's chrome covers the page without clipping it: each
surface fixed over the page declares the one box it covers (`declareCover`), and a box
is in front of the user where no scroller clips it and no such box covers it.
`readings/user-place.js` holds the user's place across one change (`holdPlaceOf`, and `holdPlace`
around a module's own), because scroll anchoring holds the first box on screen: it
can't keep still a control below growth on screen, the reading line below growth inside
that box, or a place the change hides.

### One writer for each fact

Each mutable fact has one authority and one writer in the browser. The application
publisher, `applicationState` in `state/semantic-state.js`, combines authored state, the
server's latest state and this tab's unresolved work into the one state every component
reads (root `AGENTS.md`, "The document starts state; the log changes it"):

| Fact                                                                                                           | Authority                                                                                                                                                                                                                                                                                                                                                                                     |
| -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| authored widget state                                                                                          | the validated source markup, captured before upgrade                                                                                                                                                                                                                                                                                                                                          |
| external data                                                                                                  | the latest page data; Leaf sets each bound source on the property its input names (host/data.js)                                                                                                                                                                                                                                                                                              |
| version shown                                                                                                  | the revision the delivery prelude names; a newer revision with the same executable identity patches in place, and a different one loads a fresh document                                                                                                                                                                                                                                      |
| accepted history                                                                                               | the server's event log and its `/api/state` answer, which the publisher adopts whole; an answer to a request naming the reading the tab holds may carry only the changes since, which the reader applies to that reading first (`completeState` in `transport/layer-client.js`); each answer has one `through_seq`, and a version comparison asks `/api/view` at the sequence already applied |
| unresolved browser work, refusals included                                                                     | the publisher's one ordered list; the server records no refusal, since the condition behind one can change while the user's words stay the same                                                                                                                                                                                                                                               |
| threads, workflow, attention, obligations, to-dos, activity, unread                                            | the server's state, which the browser selects without folding again (obligations: `records/obligations/model.js`); the browser adds only its own unresolved sends and the versions it is marking read                                                                                                                                                                                         |
| what waits on the user and on the agent                                                                        | the server's `served_state.queues`, which `page state` prints; the publisher adds this tab's sends (`localQueues`)                                                                                                                                                                                                                                                                            |
| the machine's other live pages                                                                                 | the server's `/api/pages` answer, read again only when a news look names another pages reading than the one last asked for (`host/live-leaves.js`, `hearPages`); it keeps no consistency with the page's own reading, and nothing this page reads waits for it                                                                                                                                |
| the user's unsent drafts                                                                                       | the page server's drafts (`src/leaf/serving/drafts.py`), read again when a news look names another drafts store or version than the tab holds (`records/drafts.js`, `hearDrafts`); the tab's own copy holds only words the server hasn't taken yet                                                                                                                                            |
| what the DOM shows                                                                                             | the presentation coordinator's renderer tickets and preparation regions                                                                                                                                                                                                                                                                                                                       |
| when a document-wide renderer paints                                                                           | the DOM dependencies `PRESENTATION_DOM` in `runtime/state/semantic-state.js` declares                                                                                                                                                                                                                                                                                                         |
| where each thread's passage is                                                                                 | `annotations/anchor-placement.js`, resolving its anchor in this version                                                                                                                                                                                                                                                                                                                       |
| the line inside a target that a comment sits by                                                                | `readings/pointed-place.js` (`placePoints`); presentation only                                                                                                                                                                                                                                                                                                                                |
| the side and line a comment box and its thread card sit by                                                     | `annotations/annotation-overlay/comment-placement.js` (`commentSide`)                                                                                                                                                                                                                                                                                                                         |
| whether a margin row sits in the rail or as a pin, and where                                                   | `annotations/annotation-overlay/margin-layout.js`                                                                                                                                                                                                                                                                                                                                             |
| what a scroller shows, what a surface covers, what sticky headers cover, how much of the window the page shows | `dom/geometry.js` (`visibleBand`, `declareCover`, `shownWindow`, `seenRect`, `growthIsSeen`)                                                                                                                                                                                                                                                                                                  |

Add no second cache, pending map, replay list or DOM attribute as another source for
one of these facts. A rendering may expose state, such as `data-lf-state` for CSS and
render checks, but no code reads it back.

A renderer repaints only when a value it read through a selector has changed, or
when code calls the renderer's `present()` after changing an input the renderer
reads from outside the state, such as a draft. Code that changes what the page shows
publishes the new state, then awaits `whenDocumentPresented()`; it doesn't call
renderers or decide their order. A renderer that depends on DOM another renderer
writes declares that dependency through `PRESENTATION_DOM`.
`whenDocumentPresented()` resolves once every renderer has written its DOM. It
doesn't wait for a widget's asynchronous preparation or for a gesture that holds
part of the page, such as a drag, to end; `whenApplicationPresented()` waits for
those too.

When a revision replaces the document, a node the patch didn't rewrite keeps its state,
and `records/carry.js` carries the value, focus, caret and scroll of an element with an authored
id. A module keeps any other state in its own store under the element's id. Delay the
revision only for a gesture in progress that has no value to carry, such as an open
composer or menu (`features/version.js`).

State a module keeps for one press, or for one view while it stays open, lives in one
record that starts when the press or view does and is dropped when it ends, rather than
in variables the module resets by hand. A module keeps its record against the press
through `dom/focus.js` `pressRecords`. A field added to the record ends with the others,
where a separate variable needs a reset at every place the press or view can end.

### One answer for each question

A question the runtime asks in many places has one owner, which every caller asks,
since a second copy drifts from it at the edges, such as under a stuck header or in a
shadow tree. Before writing or approving a predicate or measurement, look for its
question in "The browser answers first" and then here. A change that creates an owner
adds its row. Rows marked _lint_ are enforced in `eslint.config.mjs`, whose packages'
block names what a package answers with the browser's own call instead.

The table serves the runtime's own callers. A row is no reason to export its owner to
packages: a widget answers with the browser's own call or its own code, and asks Leaf
only for what Leaf alone holds (`../packages/AGENTS.md`, "A widget's need of Leaf").

| Question                                                                                              | Owner                                                                                  |
| ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| What is focused, inside open shadow trees or through a held label press                               | `dom/focus.js` `focused`, `focused(tree)` (_lint_)                                     |
| Whether the user is inside a scope, across shadow trees and slots                                     | `dom/focus.js` `currentLocationIn` (_lint_)                                            |
| The user's working place, read before something borrows it and handed back after                      | `records/history.js` `readPlace`, `returnPlace`                                        |
| Which thread view an entry of session history shows, the `?thread=` its URL names                     | `records/thread/address.js` `createThreadAddress`                                      |
| The link that opens a message's thread on that message                                                | `records/thread/address.js` `messageLink`                                              |
| Which member a widget shows of several, its name in the address, and the user's place in each         | `records/views.js` `keepView`, `entryView`                                             |
| Where the user's caret stands, and its element, through open shadow trees                             | `dom/native-selection.js` `userCaret`                                                  |
| The page place focus or the caret identifies, or none                                                 | `records/current-target.js` `currentLocationOrigin`                                    |
| Where a page walk starts, whether the user is on a stop or at it, and which item it steps to          | `records/current-target.js` `walkOrigin`, `stepFrom`                                   |
| The obligation the user is in, answered or not, and the question a thread's view asks them            | `records/current-target.js` `obligationIn`, `questionAsked`                            |
| Which of two nodes the reader reaches first, across shadow trees, alone or in a sort                  | `lib/shadow-tree.js` `renderedOrder`, `renderedOrdering`, `byRenderedOrder`            |
| What stands for a node in one tree: the node, or the host of the shadow tree holding it               | `lib/shadow-tree.js` `hostIn`                                                          |
| Whether a node is inside another across shadow trees                                                  | `lib/shadow-tree.js` `under`, `renderedUnder`, `composedParentNode`                    |
| Order and containment along another climb of the tree, as the page reading's own order is             | `lib/shadow-tree.js` `alongClimb`                                                      |
| The next element in a walk; Chromium keeps each `children` or `childNodes` list for its node's life   | `firstElementChild` and `nextElementSibling`, or `firstChild` and `nextSibling`        |
| The nodes a node draws as its children, through the shadow roots the walk names (`rootOf`)            | `lib/shadow-tree.js` `eachRenderedChild`, `eachRenderedElement`                        |
| Put the user on an element, saying what moved them                                                    | `dom/focus.js` `focusDestination(node, cause)` (_lint_)                                |
| Move a node, keeping the user's place in it                                                           | `dom/dom-move.js` `move(parent, node, before)` (_lint_)                                |
| Make a list of nodes, some already placed, a parent's children                                        | `dom/dom-children.js` `setChildren`                                                    |
| Whether a control takes typed letters                                                                 | `dom/focus.js` `typesText`, `takesLetters`                                             |
| Which keys the focused control keeps from Leaf's commands, a widget's typeahead included              | `dom/keyboard/text-entry.js` `nativeClaimAt`                                           |
| Which keys move a caret, and whether a key is Select All                                              | `dom/control-selectors.js` `CARET_KEYS`, `selectsAll`                                  |
| The keys that would make a command's press now, as a chip shows them                                  | `dom/keyboard/control-keys.js` `commandKeysNow`                                        |
| A hint map's walk and choose rows                                                                     | `readings/key-badges/hints.js` `createHintSession`                                     |
| Whether focus is where the user is: seen where the glides leave it, or a slide taking them to it      | `readings/user-place.js` `focusPlace`                                                  |
| What the user reads where focus isn't where they are, in their column                                 | `readings/reading-place.js` `pageReadingBlock`                                         |
| What stands at the reading line, and holding a node across a change anchoring can't keep still        | `readings/user-place.js` `readingAt`, `holdPlaceOf`                                    |
| Holding what the reader reads across a module's own change that hides it                              | `readings/user-place.js` `holdPlace`                                                   |
| Whether a click came from the keyboard                                                                | `base/pointer.js` `pressIsKeyboardActivation`                                          |
| Whether a press is a plain primary-button press with no modifier                                      | `lib/keys.js` `plainPress`                                                             |
| Which arrow means back along a row, in its text direction                                             | `lib/keys.js` `rowArrows`                                                              |
| Whether any of a node is in front of the user                                                         | `dom/geometry.js` `seenRect`; past the chrome's covers, `shownRect`                    |
| Whether a box, one with no height included, stands wholly above or below the window                   | `dom/geometry.js` `outOfWindow`                                                        |
| What the user sees of a node where the glides under way leave it, or as they carry it toward the view | `readings/scroll-containers.js` `seenGlided`, `seenLanded`, `seenAhead`                |
| Land the glides under way for a key whose work reads the page where it stands                         | `dom/scrolling.js` `landGlides`                                                        |
| Whether a size change there would move what is seen                                                   | `dom/geometry.js` `growthIsSeen`, `growthAfterIsSeen`                                  |
| When a reading of what is seen starts or stops holding, or holds for none of some nodes               | `dom/geometry.js` `whenChanges`, `whenNone`                                            |
| How much of the window the page shows                                                                 | `dom/geometry.js` `shownWindow`                                                        |
| The window's box, less its scrollbars                                                                 | `dom/geometry.js` `layoutWindow`                                                       |
| Whether a box shows what it holds, not only its own box as one hidden until found does                | `dom/geometry.js` `showsContents`                                                      |
| Whether the page shows a node at all, and what it shows of a sample it holds                          | `dom/geometry.js` `presented`, `frameView`, `watchRoom`                                |
| Whether a box placed against a target belongs in layout yet                                           | `dom/geometry.js` `nearWindow`, `nearObserver`                                         |
| Where an element or Range destination is, and how much of it survives clipping                        | `dom/geometry.js` `placeBox`, `clippedPlace`                                           |
| What a target draws, its list marker included, and where the marks round it stand                     | `dom/geometry.js` `inkedBox`, `markedBox`                                              |
| The room the marks round a target take beside it, a named box's round it included                     | `readings/mark-room.js` `markRoom`                                                     |
| Which box supplies each edge of what the page shows of an element: its own, a clip's, or the window's | `dom/geometry.js` `shownRectHeld`                                                      |
| What a node's contents are drawn in; a Range made for it slows every DOM write until it is collected  | `lib/shown-box.js` `contentsRects`, `contentsBox`                                      |
| How an element's layout pixels map to the viewport, through every transform, and a box carried by it  | `dom/element-axes.js` `elementMatrix`, `elementBorderFrame`, `carriedBox`              |
| The size a style writes to hold an element as it stands: its own layout pixels, fraction included     | `dom/element-axes.js` `elementBorderFrame`                                             |
| Whether a box is stuck, and the band sticky headers cover                                             | `dom/geometry.js` `stuckBox`, `visibleBand`                                            |
| What the page shows where the glides under way land, each box put back within the task                | `dom/scrolling.js` `whereGlidesLand`                                                   |
| How far a scroll of a box carries a node, which a sticky box around it rides only to its line         | `dom/geometry.js` `carried`                                                            |
| Whether a box scrolls, for a script or for the user                                                   | `dom/geometry.js` `scrollContainer`, `userScrollport`                                  |
| The box an input scrolls, along the chain native scrolling follows                                    | `readings/scroll-containers.js` `inputScroller`, `scrollChainOf`                       |
| Which axes a box clips                                                                                | `dom/rect.js` `clippingAxes`                                                           |
| Whether a box is at its scroll end                                                                    | `dom/scrolling.js` `atScrollEnd`, `SCROLL_SLACK`                                       |
| The positions a box's scroll takes on each axis, and whether a write would move it                    | `lib/scroll-range.js` `scrollRange`, `scrollMoves`                                     |
| Everything a box scrolls through, on screen, wherever it is scrolled to                               | `dom/geometry.js` `scrolledBox`                                                        |
| When a box's scroll ends, a glide's counted once, and whether the browser or a script moves it        | `dom/arrivals.js` `watchScrollEnds`, `holdScroll`, `browserScrolls` (_lint_)           |
| When the page shows a script's scroll, boxes anchored to what it moved included                       | `dom/arrivals.js` `scrollDrawn`                                                        |
| Whether the reader's input has set a box scrolling                                                    | `dom/arrivals.js` `readerScrolls`                                                      |
| Which way the reader's input heads a box, and where it found it                                       | `dom/scrolling.js` `readerScroll`                                                      |
| Whether the reader or layout chose a box's scroll position                                            | `dom/scrolling.js` `chosenSince`, `placeKept`                                          |
| The authored body, excluding Leaf's runtime surfaces                                                  | `readings/passages.js` `pageDocument`, `inPage`                                        |
| Whether focus stands on something in the page, which focus on the body doesn't                        | `readings/passages.js` `focusInPage`                                                   |
| The box the page's Layout arranges, the shell it stands in (its parent), and a page of parts' views   | `readings/passages.js` `layoutBox`, `layoutParts`                                      |
| Whether a place is already shown, which every nearest landing asks first, and the room a landing has  | `readings/landing-scroll.js` `alreadyShown`, `landingRoom`                             |
| Bring something into view without scrolling the page around it, or only inside one box (its `within`) | `readings/landing-scroll.js` `scrollIntoView` (_lint_)                                 |
| Move a box to its end, or by an amount                                                                | `dom/scrolling.js` `scrollToEnd`, `moveScrollerBy` (_lint_)                            |
| Set a box's offset outright; a package calls the browser's `scrollTo`, heard there, with a `behavior` | `dom/arrivals.js` `setScroll` (_lint_)                                                 |
| Keep a reader who stands at a box's end there as it changes, and say whether they stand there         | `dom/scrolling.js` `followEnd`                                                         |
| Open or close a native modal or popover                                                               | `dom/keyboard/layer-stack.js` `showNativeLayer`, `closeNativeLayer` (_lint_)           |
| Focus on a popover's control as it opens, and the control's `aria-expanded`                           | `dom/keyboard/layer-stack.js`, as each popover opens or closes                         |
| Whether a node is, or is inside, an open native layer, and of which kind                              | `lib/shadow-tree.js` `nativeLayerKind`, `isNativeLayer`, `nativeLayerHolding` (_lint_) |
| Whether a node stands in content the browser skips, the box that skips it, and every element it draws | `lib/shadow-tree.js` `skipped`, `skipper`, `drawnElements`                             |
| The closed box that hides a node until the user opens it: a closed disclosure or a tab not chosen     | `lib/shadow-tree.js` `closedOver`                                                      |
| Which native layers are open, in opening order, and whether a modal admits a node                     | `dom/keyboard/layer-stack.js` `nativeLayers`, `nativeModalAdmits`                      |
| The element a URL fragment names, or the part of a widget its key names; a package's address too      | `readings/anchor-resolution.js` `fragmentTarget`, `fragmentAddress`, `elementNamed`    |
| The element an id names, read from the element that gives it: its message first, then the page        | `readings/references.js` `authoredElement`                                             |
| The element an id names: the page's, else one an agent's message keeps, drawn or not                  | `records/thread/messages.js` `addressableAt`                                           |
| This page's URL with a fragment naming an element, or a widget's key                                  | `base/anchor-coordinate.js` `fragmentUrl`                                              |
| The address a heading's link names                                                                    | `records/heading-links.js` `headingAddress`                                            |
| The language a file path means                                                                        | `base/language-paths.js` `langForPath`, from the registry's `$languages`               |
| The attributes that bind a widget's input, which `host/data.js` asks to tell whether markup sets one  | `state/registry.js` `bindingAttributes`                                                |
| Whether an element's body is one `<pre>` holding text, by its declared `content`                      | `state/registry.js` `bodyIsData`, `DATA_CONTENT`                                       |
| Paint on the next frame, or watch a size                                                              | `lib/frame-pass.js` `nextRender`, `nextFrame`, `sizeObserver` (_lint_)                 |
| Write a DOM value only when it changed; a style property needs no guard (`lib/keeps.js` header)       | `lib/keeps.js` `keeps`                                                                 |
| A number that names an object in a key built of strings, the same at every ask                        | `base/ids.js` `objectIds`                                                              |
| Threads, workflow, attention, obligations, and whether they are answered                              | the server's state, under "One writer for each fact"                                   |
| What the floating panel's empty field says, for how long, and what its end offers                     | `panel/field-readings.js` `FIELD_READINGS`, `readField`                                |
| Who says a word a seat shows about the work, and the face it says it in                               | `base/voice.js` `agentSays`, `leafSays`, `voiced`                                      |
| Words as a label reads them, a count with its noun, and a label opening a sentence                    | `lib/words.js` `labelWords`, `counted`, `capitalized`                                  |
| The word for an element's kind, a widget's own word for it included                                   | `lib/element-word.js` `addressableWord`, `widgetWord`                                  |
| The order a position container lists its units in, and the rank that puts a unit at an index          | `lib/rank.js` `byRank`, `rankAt`, `authoredRank`                                       |
| Whether the page can copy here, with or without the Clipboard API                                     | `transport/copy-control.js` `canCopy`                                                  |
| What a version the comparison shows was saved after: the user's messages that waited                  | `features/change-provenance.js` `versionProvenance`                                    |
| A workflow's word, and its progress face on a control; an open to-do's word                           | `records/thread/workflow.js` `workflowWord`, `progressFace`, `todoWord`                |
| A thread's word, which Threads states as its status                                                   | `records/thread/workflow.js` `threadAttention`                                         |
| What a thread's margin entry and Page Map row say of it: its line, turn and receipt                   | `features/margin-model.js` `threadMarks`                                               |
| What an element (its `lfPreview`), control or range says when pointed at, on every route              | `annotations/preview.js` `pointRange`                                                  |
| What a place on the page shows as a preview, and the place a link into the page names                 | `annotations/place-preview.js` `placePreview`, `linkedPlace`                           |
| What a thread says when pointed at, on its passage mark and its margin entry                          | `records/thread/messages.js` `threadPreview`                                           |
| The clock time behind an age, and what an age previews                                                | `state/presence.js` `clockTime`, `agePreview`                                          |
| An age kept current in a page, a message or a widget's template: the `lf-age` element                 | `age.js`                                                                               |
| When a message was said: how long ago within the hour, then its time and day                          | `state/presence.js` `saidAt`                                                           |
| A time of day as the reader's platform writes it                                                      | `state/presence.js` `timeOfDay`                                                        |
| The keys that press a control from where the user is                                                  | `dom/keyboard/control-keys.js` `controlKeys`                                           |
| The keys the command hints label a control with from where the user is                                | `readings/key-badges/command-hints.js` `drawnKeys`                                     |
| Whether a margin entry changed since the inventory last collected: it is no longer the same object    | `features/annotation-inventory.js` `createAnnotationInventory`                         |
| A thread's name, on every surface that names it                                                       | `records/thread/messages.js` `threadName`                                              |
| The thread a name names: its key, its id, a message's, or this tab's attempt                          | `records/thread/state.js` `threadNamed`, `threadIdNamed`                               |
| The open conversations about an element or the part a heading heads, and whose turn                   | `records/thread/placement.js` `conversationsAbout`                                     |
| The thread id a drawn thread carries, and the page threads drawn with an id                           | `records/thread/selectors.js` `drawnThreadId`, `drawnThreadsWithId`                    |
| Where opening a thread puts the user: its reply, or the thread                                        | `records/thread/focus.js` `openingPart`                                                |
| Whether the user is writing a reply                                                                   | `records/thread/replies.js` `replyIsEditing`                                           |
| The draft a thread holds: its reply box or a rewrite                                                  | `records/drafts.js` `replyContext`, `rewriteContext`, `threadDraft`                    |
| Which message drafts hold words or a drawing, for every view of drafts                                | `records/drafts.js` `draftsReading`                                                    |
| Which obligations a region of the page holds                                                          | `records/obligations/place.js` `readObligations`                                       |
| What names the part of the page or a message a node stands in, and where a heading's part ends        | `records/thread/placement.js` `partOver`, `headingAfter`                               |
| Which element a heading titles                                                                        | `readings/addressable-names.js` `titledElement`                                        |
| A document's outline, and what stood over each element, as the walk reading it met them               | `readings/passages.js` `documentOutline`, `headed`                                     |
| A reading derived from the page, placement or the application state, kept until what it read moves    | `state/kept.js` `kept`, `keptEach`; a fact outside signals has a `version`             |
| What a reading of an element's words or children, or of a document, is kept by                        | `readings/passages.js` `readsElement`, `readsDocument`                                 |
| Which reading of the page stands, its words, ids and part names, for work that spans tasks            | `readings/passages.js` `pageReadingVersion`                                            |

### Facts both runtimes know

A fact Python and the browser both use, such as an event kind or how a page reads as
text, has one home. Either one runtime owns it and sends it to the other as data, as
the server sends its state in `/api/state`, whose type the build generates from
`served_state/state.schema.json`, or the kernel registry
(`runtime/kernel-registry.json`) declares it and both read the serving Leaf's copy:
the browser imports it as a JSON module through `runtime/state/kernel-facts.js`, so no build
stands between an edit and either reader. Only a fact the registry can't settle alone
is generated, as `build/vendor.mjs` writes `runtime/lib/syntax-languages.js` from
`$languages` and the grammars it bundles. Where runtime code must spell a value, a
generated type such as `ServedWorkKind` makes a misspelling fail the type check. Where only a literal can carry
the fact, as in a stylesheet's attribute selector, a check holds the spelling to the
declaration (`build/registry.test.mjs`). An algorithm both runtimes run shares a case
file that holds both to the same answers (`tests/*_cases.json`). A parity fixture, or a
test that scans one language's source for the other's names, is the last resort; in
review, ask why that fact isn't generated.

## Startup and presentation

Authored HTML paints at once, and the floating panel's row stands over it from the first
paint: the panel's own first drawing, generated into the document
(`build/panel-row.mjs`), which the panel takes over as it mounts. So mounting the runtime
moves nothing. Prose, links and scrolling work
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
7. Import the modules the layer holds (`$modules`) for the tags present, and no others.
8. Run the dressing passes and wait for the presentation coordinator.
9. Join the page-interface owners' reconciliation (`PAGE_INTERFACE`), separately
   from this document's own presentation check.
10. Land a fresh URL's fragment, prepare chrome that depends on anchors, then set
    `data-lf-upgraded="1"` and open comment capture on the shown document.
11. Start the state feed; its first answer presents the page (`presentPage`). A
    failed or expired read presents the page offline; a request with no answer
    keeps the loading status.

`readings/presentation.js` and `base/rendering.js` define the readiness stamps. Code outside the page
waits on `pageReadiness`, through `wait_until_ready` in Python, rather than combining
them itself.

## The widget vocabulary stays open

Core names a widget only when it is part of how Leaf works (root `AGENTS.md`, "Keep the
layer open"). Each declaration fact's meaning is its `$keys` entry in `registry.json`.
Use a boolean only when false has one clear meaning; otherwise declare named values.

Add a fact only where Leaf's server or `page check` must act on it without running the
widget's module, and the module can't keep the same rule itself. How an element stands
before its module draws is its package's stylesheet's to say. A rule about one
widget's markup that its module can check as it draws stays in the module, which reports a breach with an `error` event, even where
static validation could observe the same breach. The author then hears of the breach
from `page check --render`, and in a thread message only after the user opens the
thread. Keep a rule static where a breach would otherwise reach the log or a stored
decision (root `AGENTS.md`, "Leaf's role").

Python models only the text changes the registry declares. A module that changes text
in a way the file can't reproduce is fenced, and words a module generates are a passage
cell of their own, so browser capture stops at the fence and a selection across it
never becomes a quote the file can't confirm. Words Python should model belong in the
markup, where the file reads them (`content`).

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
that answer changes (`state/semantic-state.js`).

Test what one module decides on its own under `tests/runtime/`
(`pnpm run test:runtime`). The runtime is JavaScript a page runs as written.
`pnpm run check:browser` strictly type-checks every maintained runtime and widget
module; no file pragma is needed.
`../build/browser/build.mjs` owns checker selection; `types/` holds its configuration
and declarations. Declare a new
global, event detail or runtime element tag in `types/runtime-globals.d.ts`.
