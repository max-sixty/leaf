# Leaf glossary

The canonical names for the page a user sees and operates. Use them in element
declarations, JavaScript, CSS, visible copy, tests, examples, and references. Where an
existing name disagrees, rename it rather than adding an alias. Events, comments,
threads, replies, Asks, and activity are named by their protocol references, not here.

A term gets an entry once current behavior gives it a stable identity. Name the
narrowest established kind, and where the web platform or UI design already names the
thing (a drawer, a focus ring, a sticky header, a full-height layout), use that name.
Coin a word only where no standard name fits, and record under "Coined terms" which
standard term comes closest and why it doesn't fit. Qualify a noun that another web or
Leaf concept also uses.

## Pages, packages, and layers

| Term | Identity criterion |
|---|---|
| **Page instance** | One durable page directory: its source, revisions, selected layer, data, media, and event history |
| **Package** | One composable source directory of declarations and their payload |
| **Leaf layer** | One checked, vendored composition of packages |
| **User session** | One browser tab's temporary interaction with a page instance |

Core Leaf owns revision activation, scoped serving, the executable and inert-input
boundaries, target identity, event admission, comments, and export. A package owns
reusable declarations, widgets, browser modules, styles, data contracts, and guidance.
A page instance owns its content, page-local modules, styles, assets, and declarations,
its semantic target choices, drafts, and package selection. A user session owns focus,
scroll, selection, and disposable exploration state; a durable user choice enters the
page instance through Leaf's event path. Moving code into a package changes who reuses
and maintains it, not what it can reach: it runs in the page document beside every
other script.

For an authored occurrence say *Leaf element*, never *instance* alone.

## Declarations and elements

| Term | Identity criterion |
|---|---|
| **Leaf element type** | One registered `lf-*` tag |
| **Element declaration** | The registry record for one Leaf element type |
| **Leaf element** | One authored occurrence of a Leaf element type |
| **Compound owner** | A Leaf element whose body holds declared direct members |
| **Compound member** | A Leaf element whose declaration names the owner types that may hold it directly |
| **Structural element** | A Leaf element with a declared role in reading structure |
| **Addressable element** | An authored, identified element a user can target |

An element declaration keeps independent dimensions in separate keys:

- `x-content`, what its body holds: `markup`, `members`, `data`, or `empty`.
- `x-owners`, the compound owner types that may hold it directly.
- `x-required-members`, the member types a complete compound owner requires.
- `x-reading-role`, an authored reading-structure role.
- Every other `x-*` key declares a capability, not an element family.

Don't say *widget entry* for an element declaration, *item* for an addressable element
(it stays ordinary English for a list item), or *holder* for a compound owner.

## Authored reading structure

| Term | Identity criterion |
|---|---|
| **Page shell** | The body-level box that sizes the page within the room chrome reserves |
| **Content frame** | `body > main`, the root of authored content, and its reading column in flow posture |
| **Layout** | A shipped class in `layouts.css` (cascade layer `lf-layouts`) that arranges the box it is on: `layout-column`, `layout-wide`, `layout-sidebar`, `layout-tiles`, `layout-workspace`. The page's own CSS adjusts it, and the runtime never reads it back |
| **Wide page** | A content frame with a Layout other than `layout-column`: every block starts at one left edge and takes the page's width, while text keeps the reading measure. A width, not a kind of page |
| **Frame** | A box sized from outside: `main`, a root tab panel, a pane, a cell of a Layout or of the page's own grid, or any box declaring `--lf-block-frame: 1`. What it holds takes the frame's width, never the page's |
| **Text** and **surface** | How a block uses its frame's width. Text (a paragraph, list item, term or description, quote, caption, or heading) keeps the reading measure; every other box is a surface and fills its frame. On a column page, a surface whose `x-space` or `data-width` is wider than the column breaks out of it |
| **Bounded block** | A block with its own height that scrolls inside it (`x-bound`, `data-bound`). While in the page it is a reading region, so scrolling it moves its contents, not the page |
| **Workspace** | A page on `main.layout-workspace`, which keeps task regions together |
| **Full-height** | A workspace exactly filling the window, header and footer at their content's height and one body taking the rest, so the page itself doesn't scroll. Only where the window is large enough (`layouts.css`, which sets `--lf-full-height: 1` on `main`); elsewhere the workspace flows |
| **Pane** | One reading region, typically in a workspace's body: an optional header, exactly one body element, and an optional footer |
| **Reading region** | A stable semantic place that navigation and reading-position recovery use |
| **Effective reading scroller** | The scroll container currently governing one reading region (`effectiveScroller`) |
| **Sticky header** | A sticky box of stated height covering the top of the scroller it sticks in, such as an `lf-diff` file header or a root `lf-tabs` strip. Headers stack through `--lf-top`, and content under one counts as off screen (`headerInset`, geometry.js) |
| **Reading posture** | Whether a region's body scrolls on its own (`bounded`) or its container carries it (`flow`). The stylesheet decides, for a pane through the workspace Layout's media query, and the runtime reads the result (`readingPosture`) |

A root `lf-tabs` and an embedded one are the same element type; placement changes only
their presentation. Only a full-height workspace gives a pane bounded posture, so a
pane anywhere else, a page tab's included, stays in flow. A compound widget may own
reading regions without being a pane, and its own stylesheet decides whether their
bodies scroll.

## Chrome and auxiliary surfaces

| Term | Identity criterion |
|---|---|
| **Chrome** | Runtime-owned interface outside authored content, rooted at the one `.lf-chrome` container |
| **Banner** | The persistent chrome row carrying page status, the Approval and Threads controls, and More for the rest (banner-toolbar.js) |
| **Bottom bar** | The row at the window's foot, at one stated height (`--lf-bottom-bar-h`), holding the shortcut bar and the status; the page ends above it as it starts below the banner |
| **Auxiliary surface** | Chrome opened over the content frame, taking no width from it. It either covers the page, making it inert, or stands `beside` it, leaving it live, until the window leaves too little page beside it (auxiliary-surfaces.js) |
| **Thread panel** | The auxiliary surface on the right that holds threads; it stands beside the page |
| **Drawer** | An auxiliary surface that slides in at the window's left edge, one at a time. The **Asks drawer** stands beside the page; the **Leaves drawer** always covers it |
| **Details shelf** | The one chrome container holding the notes an element names through `aria-details` |

Say *covering auxiliary surface*, not *modal workspace*: a modal dialog is a different
web primitive. A sticky header covers one edge of one scroller and is not modal.

## Page Map and the margin

**Page Map** is the page inventory, every destination and action on the page, shown
two ways: the compact **margin projection** beside the page, and the searchable modal
**Page Map dialog**. The margin projection has its own terms:

| Term | Identity criterion |
|---|---|
| **Rail** | The strip right of `main` where margin rows sit beside their targets, wherever the room there fits `--rail`; it never moves the column. A page sets `data-rail` on `body` to make room for it (`right`) or withhold it (`none`) (margin-layout.js) |
| **Margin resident** | Something the margin holds: the rail, the contents map, a column's first sidebar, its sidenotes. `settleResidency` admits those the room beside `main` holds and writes them as `data-lf-margin` on `main` |
| **Margin row** | One target-anchored row whose placement is `rail`, `pin`, or `withheld` |
| **Pin** | A margin row lying over the page by its target where the rail can't hold it (`rowPosture`, margin-placement.js). It covers what lies under it, and nothing reserves room for it or moves when it appears, disappears, or moves |
| **Folded pin** | A pin without room for its face, showing only its options toggle (`data-lf-folded`); opened, it spreads its actions leftward over its surroundings (margin-placement.js) |
| **Margin lane** | The layer holding the margin rows of one scroller: the root lane for the document, and one lane per bounded reading region, clipped to what that region shows |
| **Margin cluster** | The visible group attached to one target |
| **Margin contribution** | One provider's registered bundle of margin content |
| **Margin entry** | One ranked action, disclosure, or status in a contribution |
| **Contributed control** | A margin entry a package puts in a target's cluster, such as a suggestion's Accept and Reject |

A row is *withheld* while its target shows no part of itself in its region: inside a
closed `details`, in an inactive tab, or in a pane scrolled past it. A withheld row is
out of the tab order, and the term says nothing about whether the entry will appear
later.

## Contents outline

`lf-toc` requests the **contents outline**, navigation generated from the page's
headings. In ordinary flow it lists every included heading; where the margin has room
it may show the **contents spine** instead, which spreads the heading destinations over
the document's height.

## Keyboard interactions

| Term | Identity criterion |
|---|---|
| **Scope** | A registered boundary deciding which commands apply and which they shadow |
| **Design mode** | `l`: input is read as interface comments until the user exits |
| **Draw mode** | `w`: pointer input draws until the user exits |
| **Annotation layer** | Everything Leaf draws over the page's content, the rail excepted: pinned margin rows, the marks on commented and reacted passages, an open card, an unfolded cluster. It takes no room. `o`, or More's Hide annotations under a finger, toggles it as tab view state |
| **Go-to sequence** | The `g` prefix: it builds a current map of Go-to targets, paints transient hint codes, and resolves complete ordered addresses |
| **Target picker** | `s`: presents addressable elements until the user chooses one or closes it |
| **Page search** | `/`: filters or walks text matches for a query |
| **Walk** | Ordered movement among destinations of one kind |
| **Trip** | One travel to a destination (a thread's passage, an Ask, a datum, or the element a followed fragment link names). It clears the auxiliary surface hiding the destination, then stays if the user already has it or departs, leaving a history entry (anchor-travel.js) |
| **Journey** | Consecutive trips, each leaving from the last one's landing, that share one history entry, so Back returns to where the first began. It may mix threads and Asks, and is not a walk |
| **Standing** | Holding a destination or a control inside it: a thread on the page or in the panel, an Ask, or authored page content. A panel thread's title and messages are one destination. Chrome controls, margin markers, mark notes, and contents-outline links are apparatus, not destinations |
| **Standing target** | The addressable element a user stands at, from any side they hold it: the element or anything inside it, its margin cluster, a note it names on the details shelf (its comment note, a drawing's response proxies), or the thread card showing its threads |
| **Floor** | Where in a layer the user stands on nothing: the page's body, or the whole thread panel |
| **Unwind** | What one Escape takes off, read from what is in front of the user rather than how they got there: the innermost step of the ladder in `skills/leaf/assets/runtime/keyboard/AGENTS.md`, containment before kind, each step landing them at the parent of what it closed |
| **Landing** | Where a step leaves the user: closing a box lands at its container, leaving a standing at its floor, and closing a surface at the block the user was reading (`letGo`, focus.js) |
| **Layer stack** | The one ordered record of the popovers and modal dialogs open over the page, in the order they opened. The dispatcher tiers scopes over it; a covering auxiliary surface is its floor without being an entry |
| **Focus ring** | The one ring on whatever takes the user's next press, marking standing as well as DOM focus: a focused control, a bounded decision, an Ask stood at. Drawn as `--focus-ring` or `--focus-shadow`, each rule naming itself in `--lf-focus-ring` |
| **Key badge** | A keycap-shaped label for a binding or a transient hint code |
| **Binding badge** | A key badge showing a command's currently resolved binding |

A thread's parent is its standing target: its thread card shows while the user stands
there and goes when they stand elsewhere on the page or let go. With Threads open, the
list's expanded thread takes the card's part. A thread is about exactly its anchor's
target, so standing at an element shows the threads of the innermost target holding it
that has any (its own, else an enclosing one's), never those of anything inside it: a
thread on an Ask's options shows from the options, not from the Ask. Every side
behaves alike: an open Ask stood at from its card keeps its ring and takes its digits,
`c` at an element whose own thread is shown continues it, and `a` and `t` step from the
target.

Only Design mode and Draw mode are *modes*, lasting until an explicit exit. `g` opens a
sequence, `s` opens a picker, and `o` is a toggle that changes what the page shows, not
what input means. Commands have stable dotted ids; bindings are canonical normalized
chords matched against keyboard events.

A *binding* is one chord a scope's row declares for a command, the word code, the
register, and package authors use. A *shortcut* is the whole key sequence a user
presses to reach the command, prefix included (`g d`), and the only word user-visible
text uses. A *keyboard route* is any keyboard path to an action, Tab to a native
control included. A row's `routes` are its extra keyed meanings, each with its own id
and binding, never another name for a binding or a shortcut.

The keyboard help comes in three presentations:

- **Shortcut bar**: the always-visible compact list of commands that apply in the
  current keyboard context, drawn in the bottom bar.
- **Expanded shortcut bar**: what More's first press opens, the rest of the current
  commands in up to two rows; not another surface.
- **Command reference**: the searchable complete catalog of commands, including
  pointer- and platform-triggered ones with no keyboard binding.

## Coined terms

Each coined term, the standard term nearest it, and why that term doesn't fit:

- **Standing**, not *focus*: a user stands at a target from its margin cluster, thread
  card, or details-shelf note as well as from the element, while DOM focus is on one
  node. Where the two coincide, say *focus*. The event log's *standing*, an event not
  yet withdrawn (`skills/leaf/scripts/leaf/events.md`), is a different term; write
  *standing event* or *standing action* where both could be read.
- **Trip** and **Journey**, not *navigation*: web navigation always adds or replaces a
  history entry, while a trip may leave none and a journey shares one across trips.
- **Landing** and **Floor**, not *focus restoration*: a landing follows any step, a
  box's close as well as a surface's, and focus restoration has no word for a layer's
  empty place.
- **Unwind**, not *dismiss*: Escape also takes off a selection or a narrowing, and only
  surfaces are dismissed.
- **Walk**, as a DOM `TreeWalker` walks: *roving focus* moves within one widget.
- **Frame**, **Text**, and **surface**: the CSS terms each cover half of a frame, which
  both sizes what it holds (containing block) and trims its edge margins
  (`margin-trim`).
- **Reading posture**, **Bounded block**, and **Margin resident**: *scroll container*
  names only the CSS outcome, not the decision Leaf makes and reads back.
- **Rail**: a *gutter* is a code editor's line-number strip, and Material's *navigation
  rail* holds destinations, not notes.
- **Details shelf**: ARIA's `aria-details` names the relation, not a place to keep its
  targets.
- **Layer stack**: the platform keeps the *top layer*'s order but doesn't expose it.
- **Key badge**: it carries hint codes as well as bindings, so *keycap* would misname
  half its uses.

**Pin**, **Banner**, **Drawer**, **Toolbar**, and **Picker** keep their ordinary UI
meanings. Qualify **picker** (the target picker, the version picker) where the reaction
picker could be meant.
