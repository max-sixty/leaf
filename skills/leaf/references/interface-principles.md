# Interface principles

These rules hold on every page and for everything drawn on one: Leaf's runtime and
chrome, every package's widgets and stylesheets, and a page's own CSS. They apply
[SOUL.md](../SOUL.md): "Preserve the user's attention and work" to space, stability,
typed words, editing and motion, and "Make the work concrete and playable" to the
visual grammar, so weigh a case none of them covers against those principles. Each
names the check that holds it where one exists; the render gate's checks report to
any page's author, and the others are Leaf's own tests. Leaf targets desktop first, so
judge layout at a representative desktop viewport.

Leaf's maintainers find the runtime module that owns each rule in
`../../../browser/AGENTS.md`, "Interface owners".

## Space and scrolling

- **The page owns its arrangement.** A page arranges itself with a shipped Layout
  class (`layouts.css`) or its own CSS. Leaf owns only what pages and widgets share: the
  bands, the reading measure a Layout sets, and each widget's duty to fill the box it
  gets, declare its minimum, and never widen its container.
- **A Layout, a style and a widget never read one another.** A Layout sets where boxes
  go and how large they are, a style (`theme.css`) sets type, spacing and form as tokens,
  and a widget reads only its own box and the theme's tokens. A widget therefore behaves
  the same in a shipped Layout as on a hand-written page that gives it the same box.
  Where one must react to another, the owner sets a token describing the box, such as
  `--lf-full-height`, and the reader matches it with a style query; a width needs no
  token, since a size query on the reader's container answers it. Before adding a token,
  ask whether a hand-written page with the same box would want the same answer. If not,
  the token describes a Layout rather than a box. Check:
  `test_layout_style_and_widgets_never_read_each_other`.
- **Nothing Leaf draws moves the page's content.** Pins, passage marks and runtime
  controls sit over the page and take no space, and no rule pads or widens a block to
  make room for them. The rail sits right of `main` when the window is wide enough and
  never moves or narrows the column ([page-layout.md](page-layout.md), "The rail and the
  margin"). Only the left margin content and sidenotes move the column. Checks:
  `test_a_comment_leaves_its_block_as_the_page_wrote_it` and the shift watch.
- **A control takes only its own room.** Leaf never reserves a strip, a row or
  full-width padding to seat one small control. The control joins a line that is
  already there, such as a head, the line over a field or a row's end, or a corner its
  content leaves free.
- **The chrome opens over the page and never changes its geometry.** The theme keeps
  the room the floating panel's row rests in at the page's foot (`--lf-foot-room`).
- **A widget in ordinary flow grows with its content.** It scrolls inside itself only
  when its task needs a region kept in view while its contents move, or for a live
  stream whose newest entry the reader follows, and then declares
  `--lf-holds-height: 1`. Check: the widget quality check `grows-with-content`
  (`../../../src/leaf/render_gate/widget_quality.py`).
- **A necessary scroller works like part of the document.** It passes scrolling on to
  the document at its edges, except at a bounded task or a modal. Wheel and touch keep
  moving through content; pan and zoom need a deliberate control. It has a keyboard
  route, visible bounds and visible focus, which Leaf supplies by giving every
  scrollable box a tab stop and painting the edge its content continues past. An object
  taken out of flow for inspection restores the selection and the document position on
  return. Checks: the reach tests and the axe sweep; `/ui-sweep` reviews scroll
  chaining and the return from inspection.

## Stability

- **The page holds still under the user's aim.** A state change may repaint any box,
  but must not move the controls next to the gesture that caused it. A scroll the
  gesture makes may not carry the control it was made on either, except to bring it
  whole into a scroller that showed only part of it, or where the gesture takes the
  user somewhere and says so: a command as a walk or Go-to does (`travels`,
  [module-input.md](module-input.md)), or a press by the history entry it adds, as a
  link or a root tab set's switch does. Without a gesture, a box may grow or shrink
  into free room, but reading content and controls stay put. A change the user asked
  for may reflow the content it replaces, with motion the eye can follow. A reveal on
  hover, focus or a key never changes the size or position of its ancestors or
  siblings, and typing may grow a field but never moves it. Check:
  `../../../tests/shift_watch.js`, run on every browser test outside a module marked
  `shifts_unsurveyed` (`../../../tests/AGENTS.md`, "Browser errors").
- **Stability is owed to the common path** ([SOUL.md](../SOUL.md), "Keep the foundation
  small and extensible"). Every hold costs code on each later change, so a rare path the
  user reads at a glance moves what is on screen rather than carry a mechanism of its
  own. Words a refused send hands back, and a draft typed in another tab, grow the reply
  field as typing does, in a card as in the floating panel, and a refused turn gives its
  room back as it folds: what the user is about to send shows whole before the layout
  holds (the user's choice, 25 October 2026).
- **Shared containers determine control dimensions.** When several modes share a
  container, that container sets its dimensions from a theme token and each mode's
  controls fill it. For example, the comment field, page search, Threads' search,
  a thread's reply and the seated comment box share the floating panel's field.
  The container grows only for content, such as typed words, or an explicit action,
  such as More room. Changing labels (`data-room`, below) and rendering a widget
  after its first paint (`keeps-first-box`) follow the same sizing rule. A
  one-line control's visible height is `--lf-line` (theme.css); its touch target meets
  the minimum size set by surfaces.css. A control that instead derives its visible
  height from its font or the touch-target minimum changes the height of every
  container that holds it. Check:
  `test_whatever_the_field_holds_the_row_keeps_its_line`
  compares the row's height with its token in each mode. Checking only that controls
  fit inside the row would miss a row that grew to fit them. `tests/swap_watch.js`,
  which the browser fixture runs on every test, fails the test if a flex row's height
  changes to match a replacement child control.
- **A runtime region whose contents rearrange inside it declares `data-lf-reflow`**
  on the box that owns the space: `text` where its labels may rewrap while its controls
  stay put, as in a message header, and `append` where it grows only at its end, as a
  thread card's transcript does. A nested region keeps every guarantee of the regions
  around it. The `tests/shift_watch.js` header says how the watch credits an `append`
  region.
- **News never moves what the reader is reading.** News from the server grows above
  the screen, where scroll anchoring absorbs it, or below it. Anywhere else it waits
  behind a fixed-size control until the reader goes to it, and an editor in use stays
  still. Check: `test_news_just_after_a_press_moves_nothing`. The user chose one
  exception: the answer they wait for in the floating panel's thread grows that view
  upward while its controls stay put.
- **A box floating over the page grows inside the window**, toward the edge that has
  room. Sending and later growth never scroll the page to make room. A freshly opened
  card above or below its target may scroll to open clear of it. A box a scroll carried
  away comes back when the user types into it. Only a field in flow scrolls to keep its
  controls in view.
- **A widget paints its final box before it upgrades.** The theme sizes each widget
  under `html[data-lf-interactive]` as its module will draw it
  ([module-authoring.md](module-authoring.md), "First paint"). Check: the widget quality
  check `keeps-first-box`, which fails on any finding `tests/known_widget_findings.py`
  doesn't list.
- **Generated interface appears in its final position, and room is held only for what
  will be drawn**, such as a widget's upgraded controls. A state that may never come,
  such as a failed save, shows in a slot already on screen, as a message's head carries
  its delivery status, and the user's gesture makes the room it needs, as
  `lf-file-editor` opens the two versions of a file conflict only on Compare.
  Feedback may repaint a control or change its label, but never its size: `data-room`
  (`controls.css`) sizes a label to the widest of the words it can show. Adjacent
  actions keep their hit areas apart.
- **A gesture shows the result the page can draw as it is made** (`../../../AGENTS.md`,
  "Responsiveness"). The new content and its Undo confirm success, so success needs no
  notice beyond the announcement for a listener. A gesture that moves the user, such as
  resolving a thread, leaves them at its place again when it is refused or undone. A
  result only the log can supply waits with `aria-busy`, shown after a delay so a fast
  answer shows nothing. Persistent status text is for a state the user must return to,
  such as a failure.

## Words stay where they were typed

- **Typed words stay in their native editor until the user puts them away.** A box
  holding words closes only on a key or press meant to close it (Send, Cancel, Escape,
  a press elsewhere, another target) or when its subject leaves the document, never on
  a scroll, resize, timer or server news. Geometry decides where the box sits, never
  whether it exists, and Resume writing (`g i`) shows the same editor. A re-render that
  replaces the box's node hands its words and caret to the replacement. Checks:
  `tests/words_watch.js` and `typed_box_findings` in the render gate tests.

## Editing in place

- **Editing something keeps it where it stood and as it read.** Opening a message, a
  draft or any value for editing draws it in its display's place and face: every line
  of its words keeps its position, type and breaks, and its pictures and other parts
  keep their places and sizes. The editor adds only what editing needs, such as a
  field's frame, Save and Discard, or a picture's removal mark, in room the display
  already has: around the content, or at the head where the display's own control
  stood. Where the frame needs room the display lacks, give the display that room at
  rest rather than move the content on opening: a scroller holding messages keeps the
  thread's text inset beside them, and the user's own words keep the column of the box
  they write in. The user then finds what they meant to change where they saw it, and
  sees what saving will show. A message's display keeps the blocks its draft showed,
  and a draft's editor takes the faces its prose has. Checks:
  `test_a_rewrite_keeps_the_message_as_it_stood` and
  `test_a_draft_edits_where_it_reads`.

## Visual grammar

- **Visual treatments carry hierarchy and state.** Contours are solid. A dotted or
  dashed line marks a distinct state, such as a draft or a drag placeholder. One
  contour shows one control state, and a segmented group shares one-pixel seams. A box
  edged on one side is never rounded: mark a state with a whole contour, or a stripe on
  a square box. Avoid reflexive cards, tints, gradients and soft shadows. Check:
  `test_no_rule_rounds_a_box_edged_on_one_side`.
- **Leaf's controls are few, and each shows a symbol where a standard symbol for its
  action exists, and its word where none does.** A standard symbol is one readers
  already know for that action from the software they use, such as ✕ for close, ✓ for
  done, ‹ and › for back and next, and the symbols for play, pause, copy and undo, so
  they can tell what the control does before hovering it. The words on Leaf's controls
  compete with the page's own words for the reader's attention, and a symbol is
  smaller and quieter. Draw it from Leaf's icons ([module-reading.md](module-reading.md), "Icons")
  and give the control its name as tooltip and accessible name, without the word beside
  the symbol. One control whose symbol follows its state, such as play turning to
  pause, replaces a button for each state. A symbol that is only related to the action,
  such as a speech bubble for answering a question, leaves the reader guessing, and a
  tooltip doesn't fix that: the reader must already suspect the control to hover it,
  and a touch screen has no hover. The rows of the leaf's menu keep their words too,
  since the user opened the menu to read them. Symbols don't license more controls: a
  surface at rest shows only what its task needs, and the leaf's menu holds the rest.
- **A control wears its role's face.** Code builds a control by its role, with
  `offerAction` or `offeredAction` ([module-authoring.md](module-authoring.md),
  "Generated controls"), and never names a face's classes, so two controls of one kind
  can't look different. A new role needs a difference in the user's task, not only in
  a widget's taste. Check: `test_controls_are_built_by_role_and_never_by_face`.
- **A face used twice is a token or a shared rule.** A lift names one of the theme's
  heights, `--raise-1` to `--raise-3` (`theme.css`). Check:
  `test_every_lift_names_one_of_the_theme_s_heights_cast_in_the_scheme_s_ink`.
- **Every surface paints a thread's `unread` and `attention` from one value**, so the
  On me mark's dot, Threads, panel, margin entry and Page Map change together. Green marks
  the user's turn; other thread controls stay blue. Marking read never moves the user.

## Motion

- **Animations are restrained and finite, and acknowledge state changes.** The one
  continuous animation is the sheen, which marks agent work in progress. It stops when
  the work ends and is static under reduced motion.
- **Nothing the user must read, press, or decide waits on a clock.** Motion the user
  waits on stays under 300ms. A delay may hide a flicker but never adds a minimum
  spinner time or a staged reveal. Animate through Leaf's shared motion gate
  ([module-scroll-and-motion.md](module-scroll-and-motion.md), "Motion"), and take
  durations and curves from the theme's `--lf-motion-*` properties.
