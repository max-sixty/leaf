# Leaf glossary

This is the canonical vocabulary for the page a user sees and operates. Use these
names in element declarations, JavaScript, CSS, visible copy, tests, examples, and
references. When an existing name disagrees with this glossary, change the name; do
not add an alias.

This reference does not define the protocol between the page and its agent. Events,
comments, threads, replies, Asks, activity, and their lifecycles are owned by
their protocol references.

## How to use the vocabulary

A term earns its own entry when current Leaf behavior supplies a stable identity
criterion. Add a short example only when the definition would otherwise remain
abstract.

Name the narrowest established kind. Where the web platform or UI design already names
the thing (a drawer, a focus ring, a sticky header, a full-height layout), use that name,
since it is the one a user, a page author, and a newcomer to the code already know. Coin
a word only for a concept with no standard name, and let its entry say which standard
term comes closest and why it does not fit. Qualify a noun when another web or Leaf
concept uses the same word.

## Pages, packages, and layers

| Term | Identity criterion |
|---|---|
| **Page instance** | One durable page directory, including its source, revisions, selected layer, data, media, and event history |
| **Package** | One composable source directory containing declarations and their payload |
| **Leaf layer** | One checked, vendored composition of packages |
| **User session** | One browser tab's temporary interaction with a page instance |

Core Leaf owns revision activation, scoped serving, executable and inert-input
boundaries, target identity, event admission, comments, and export. A
package owns reusable declarations, widgets, browser modules, styles, data contracts,
and instructions. A page instance owns its content, page-local modules, styles, assets, and
declarations, semantic target choices, drafts, and package selection. A user session
owns focus, scroll, selection, and disposable exploration state; durable user choices
enter the page instance through Leaf's event path.

Use a package when the source is reusable, the Leaf layer for the checked composition
vendored into one or more page instances, and the page instance for the durable authored
artifact. Packaging code changes its reuse and maintenance owner; it does not isolate
that code from other executable code in the page document.

Do not use *instance* alone for an authored occurrence; use *Leaf element*.

## Declarations and elements

| Term | Identity criterion |
|---|---|
| **Leaf element type** | One registered `lf-*` tag identity |
| **Element declaration** | The registry record for one Leaf element type |
| **Leaf element** | One authored occurrence of a Leaf element type |
| **Compound owner** | A Leaf element whose body owns declared direct members |
| **Compound member** | A Leaf element whose declaration admits one or more direct owner types |
| **Structural element** | A Leaf element with a declared role in reading structure |
| **Addressable element** | An authored, identified element eligible as a user target |

An element declaration keeps independent dimensions independent:

- `x-content` is its **body grammar**: `markup`, `members`, `data`, or `empty`.
- `x-owners` lists the compound owner types that may contain it directly.
- `x-required-members` lists the member types a complete compound owner requires.
- `x-reading-role` declares an authored reading-structure role.
- Other `x-*` keys declare capabilities, not element families.

Do not use *widget entry* for an element declaration, *item* for an addressable
element, or *holder* for a compound owner. *Item* remains ordinary English for a list
item.

## Authored reading structure

| Term | Identity criterion |
|---|---|
| **Page shell** | The body-level responsive sizing envelope after chrome reservations |
| **Content frame** | `body > main`, the root of authored content and its reading column in flow posture |
| **Layout** | A shipped class (`layouts.css`, the `lf-layouts` cascade layer) that arranges the box it is on: `layout-column`, `layout-wide`, `layout-sidebar`, `layout-tiles`, `layout-workspace`. A starting point the page's own CSS adjusts; nothing reads it back |
| **Wide page** | A content frame carrying a Layout other than `layout-column`: every block starts at one left edge and takes the page's width, while text keeps the reading measure. It is a width, not a separate kind of page |
| **Frame** | A box whose size comes from outside it: `main`, a root tab panel, a pane, a cell of a Layout or of the page's own grid, or any box declaring `--lf-block-frame`. A frame that draws one (`1`) holds what it holds to its width, never the page's room; a frame that only trims its edges and draws nothing (`trim`: `main`, a root tab panel, a command's goal) lets a surface break out as it would with no frame |
| **Text** and **surface** | How a block uses its frame's width: text (a paragraph, list item, term or description, quote, caption or heading) keeps the reading measure however wide its frame, and every other box is a surface that fills its frame. A surface with `x-space` or `data-width` past the column breaks out of it on a column page, and a `wide` one holds to `--wide` in a frame wider than that |
| **Bounded block** | A block that holds its own height and scrolls inside it (`x-bound`, `data-bound`); a reading region while it stands in the page, so what it scrolls moves it rather than the page |
| **Workspace** | A page on `main.layout-workspace`, which keeps task regions together |
| **Full-height** | A workspace filling the window exactly, where the window is large enough (`layouts.css`'s media query; `--lf-full-height: 1` on `main`): header and footer at their content's height, one body taking the rest, and the page itself does not scroll. A pane that is the body or a direct cell of it scrolls on its own; anything deeper scrolls with the body. Elsewhere the workspace flows and the page scrolls. The web's name for the arrangement is a full-height or app-shell layout |
| **Pane** | One reading region, typically in a workspace's body: an optional header, exactly one body element, an optional footer |
| **Reading region** | A stable semantic place used by navigation and reading-position recovery |
| **Effective reading scroller** | The scroll container currently governing one reading region |
| **Sticky header** | A sticky box of stated height that stands over the top of the scroller it sticks in, such as an `lf-diff` file header, a root `lf-tabs` strip, or an open thread's title in the Threads list. It sticks at `--lf-top` and adds its height to `--lf-top` for what it stands over, so headers stack. What passes under it is not on screen (`headerInset`), and a landing arrives clear of it |
| **Reading posture** | Whether a region's body scrolls on its own (`bounded`) or the region is carried by its container (`flow`); the stylesheet decides, for a pane the workspace Layout's media query, and the runtime reads the result |

A root `lf-tabs` and an embedded `lf-tabs` remain the same element type; placement
changes their presentation rather than creating another structural kind. Only a
full-height workspace gives a pane bounded posture; a pane anywhere else, a page tab's
included, remains in flow.
A compound widget may own reading regions without being a pane, and its own
stylesheet decides whether their bodies scroll.

## Chrome and auxiliary surfaces

| Term | Identity criterion |
|---|---|
| **Chrome** | Runtime-owned interface outside authored content, rooted at the one `.lf-chrome` container |
| **Banner** | The persistent chrome row carrying page status, which ends with the two queues' counts (a press on them opens the Queue panel), and the primary Approval and Threads controls, with secondary global controls in its overflow disclosure. While a user's gesture holds a next step, such as Comment on selection after a touch selection or Exit Draw mode while a finger is in Draw mode, that step stands on the row in Approval and Threads' place |
| **Bottom bar** | The row at the window's foot, at one stated height (`--lf-bottom-bar-h`), holding the shortcut bar and the status; the page ends above it as it starts below the banner |
| **Auxiliary surface** | Chrome opened `beside`, `over`, or `covering` the content frame |
| **Thread panel** | The right-side auxiliary surface containing threads; it stands over the page and takes no width from it, and covers the page only where it leaves less than a usable page beside it |
| **Drawer** | A mutually exclusive auxiliary surface that slides in at the window's left edge, one at a time; the Queue panel stands over the page as the thread panel does, and the Leaves drawer always covers |

The current drawers are the **Queue panel** (experimental) and the **Leaves drawer**. Use *covering auxiliary
surface*, not *modal workspace*: a covering surface and a modal dialog are different
web interaction primitives. A covering surface makes the page inert behind it; a surface
over the page, such as the thread panel on a desktop window, takes no width from
it and leaves it live. A covering surface covers the content frame; a **sticky header**
stands over one edge of one scroller, and nothing about it is modal.

## Page Map and the margin

**Page Map** is the feature spanning one inventory and its two projections:

| Term | Identity criterion |
|---|---|
| **Page inventory** | The complete logical collection of Page Map destinations and actions |
| **Margin projection** | The compact page-side projection of the inventory |
| **Page Map dialog** | The searchable modal projection of the inventory |

The margin projection has a separate registration and layout hierarchy:

| Term | Identity criterion |
|---|---|
| **Rail** | The right-hand strip beside `main` where margin rows stand beside their targets. It claims nothing: it stands wherever the room the page leaves right of the centred `main` holds it, and only `data-rail="right"` on `body` makes the shell give it up |
| **Margin resident** | Something the page's margin holds: the rail, the contents map, a column's first sidebar, its sidenotes. One measurement (`settleResidency`) admits them in that order where the room beside `main` holds them, moving the column over by `--lf-shift`, and writes `data-lf-margin` on `main` |
| **Pin** | A margin row standing over the page inside its target's top-right corner, where no rail stands: the page declared none, the room beside `main` does not hold one, the target sits in a pane that scrolls on its own, the target reaches past the rail's inner edge, or a hanging note stands level with it. It is an overlay: it covers what lies under it, and nothing reserves room for it or moves when it comes, goes, or changes place |
| **Folded pin** | A pin whose face, a contributed primary and one more control, found no room for both and stands as its options' toggle alone (`data-lf-folded`), seated at that size, wearing the marker face of the kind its primary contribution declares. Placement folds it; the gesture that opens any options opens it, as does the keyboard standing at its target, spreading its actions leftward over whatever stands beside it, the toggle staying under the press |
| **Margin row** | One target-anchored geometry participant whose placement is `rail`, `pin`, or `withheld` |
| **Margin lane** | The layer holding the margin rows of one scroller: the root lane for the document, one lane per bounded reading region, clipped to what that region shows |
| **Contributed control** | A margin entry a package puts in a target's cluster, such as a suggestion's Accept and Reject |
| **Margin cluster** | The visible group attached to one target |
| **Margin contribution** | One provider's registered bundle of margin content |
| **Margin entry** | One ranked action, disclosure, or status in a contribution |

*Withheld* means the row's target shows no part of itself in its region: a closed
`details`, an inactive tab, or a pane scrolled past it. A withheld row is out of the tab
order; it does not imply that time alone will make the entry appear.

## Contents outline

**Contents outline** is generated page navigation derived from authored headings.

| Term | Identity criterion |
|---|---|
| **Contents spine** | The roomy margin presentation that distributes heading destinations over the document's height |

`lf-toc` requests the contents outline. In ordinary flow it exposes every included
heading label; when the margin has room, it may present the proportional contents
spine instead.

## Keyboard interactions

| Term | Identity criterion |
|---|---|
| **Scope** | A registered command-applicability and shadowing boundary |
| **Design mode** | The `l` interaction that reinterprets input for interface comments until the user exits |
| **Draw mode** | The `w` interaction that reinterprets pointer input as a drawing until the user exits |
| **Annotation layer** | Everything Leaf draws over the page's content: the margin rows standing as pins, the durable marks on commented and reacted passages, an open card, an unfolded cluster. The rail covers nothing and is not part of it. The layer takes no room, so showing or hiding any of it moves nothing on the page. `o`, or More's Hide annotations under a finger, toggles whether it shows, as tab view state rather than a mode |
| **Go-to sequence** | The `g` prefix grammar that builds a current map of Go-to targets, paints transient hint codes, and resolves complete ordered addresses |
| **Target picker** | The `s` interaction that presents addressable elements and ends when the user chooses one or closes it |
| **Page search** | The `/` interaction that filters or walks text matches for a query |
| **Walk** | Ordered semantic movement among one category of destination: open threads (`t`), the user's queue (`a`), a list's rows |
| **Queue** | What one side has to act on: the user's (`on_you`: their open tasks, then each thread or page move to send again) or the agent's (`on_agent`: owed replies, moves in hand that owe nothing, its open tasks). `agent_state.queues` and `runtime/queues.js` select both from the same readings; `a` walks the user's, and the Queue panel lists both, with the ended tasks folded beneath as Done |
| **Task** | The one item both queues hold besides moves: something owed, with an `owner`, the agent or the user, and a subject (a thread, a widget, an element, or the page). The agent's come from `leaf task open`; the user's from an Ask in the markup, a thread question (`--awaits`), or `leaf task open --on user`. How a task ends follows from its owner and subject: the agent's at `leaf task end` or `--completes`, an Ask's when its widget answers it, a thread's at the user's reply, any other of the user's at their **Done**; the agent can end any. A row and the item named by how it ends: Ask, Question, Task (`taskNoun`) |
| **Done** | The control that ends a task on the user no widget answers: a button beside its Queue panel row, `x` on that row or where `a` stands on the task, and a step on the banner's row under a finger. It writes the user's `task_end`, which `z` takes back like any gesture. Distinct from the Queue panel's Done fold, which lists ended tasks |
| **Trip** | One travel to a destination, a thread's passage, an Ask, a datum, or the element a followed fragment link names: it clears the auxiliary surface hiding the destination, then stays when the user already has it or departs, leaving a history entry. A fragment link always departs, by the entry the browser's navigation adds; Back or Forward to an entry whose fragment names an element the page has hidden since is a trip that departs by no entry |
| **Journey** | Consecutive trips each leaving from the last one's landing, which share one history entry so Back returns to where the first began; it may mix threads and Asks, and is not a walk |
| **Standing** | Holding a destination or a control inside it: a thread on the page or in the panel, an Ask, or authored page content. A panel thread's title and its messages are one destination. Chrome controls, margin markers, mark notes, and contents-outline links are apparatus rather than destinations |
| **Standing target** | The addressable element a user stands at, from whichever side they hold it: the element or anything inside it, its margin cluster, a note it names on the details shelf (its comment note, a drawing's response proxies), or the thread card showing its threads. The element is a thread's parent, so the card shows while the user stands at its target and goes when they stand elsewhere on the page or let go. With Threads open, the list's expanded thread plays the card's part. A thread is about exactly its anchor's target, so standing at an element shows the threads of the innermost target holding it that has some (its own, else an enclosing one's), never those of anything inside it: a thread on an Ask's options shows from the options, not from the Ask. Every side answers alike: an open Ask stood at from its card still wears its ring and takes its digits, `c` at an element whose own thread is shown continues it, and `a` and `t` step from the target |
| **Floor** | The place in a layer where the user stands on nothing: the page's body, the whole thread panel |
| **Unwind** | What Escape takes off, read from what stands in front of the user rather than from how they reached it: the innermost step of the ladder `skills/leaf/assets/runtime/keyboard/AGENTS.md` states, with containment before kind, each landing them at the parent of what it closed |
| **Landing** | Where a step leaves the user: a box at its container, a standing at its floor, a surface at the document, which is the block they are reading, focused and then blurred |
| **Layer stack** | The one ordered record of the popovers and modal dialogs standing over the page, in the order they opened; the dispatcher tiers scopes over it, and a covering auxiliary surface is its floor without being an entry |
| **Focus ring** | The one ring on whatever takes the user's next press: a focused control, a bounded decision, an Ask stood at. It is drawn as an outline (`--focus-ring`), or as a shadow (`--focus-shadow`) where a box cannot spend its outline, and each rule that draws it names itself in `--lf-focus-ring`. It marks standing as well as DOM focus |
| **Key badge** | A keycap-shaped carrier for a binding or transient hint code |
| **Binding badge** | A key badge showing a command's currently resolved binding |

Reserve *mode* for Design mode and Draw mode, which persist until explicit exit. `g`
opens a sequence, `s` opens a picker, and `o` is a toggle: it changes what the page
shows, not what input means. A scope is the command-resolution mechanism
that these interactions may make applicable. Commands have stable dotted ids; bindings
are canonical normalized chords matched against keyboard events.

*Binding* and *shortcut* name two things. A binding is one chord a scope's row declares
for a command; code, the register, and package authors use it. A shortcut is the whole
key sequence a user presses to reach the command, a sequence prefix included (`g d`),
and it is the only word user-visible text uses. *Keyboard route* is wider than either:
any keyboard path to an action, Tab to a native control included. A row's `routes` are
its extra keyed meanings, each with its own id and binding; a route is never another
name for a binding or a shortcut.

The keyboard help presentations are:

- **Shortcut bar**: the always-visible compact projection of commands applicable in
  the current keyboard context, drawn in the bottom bar.
- **Expanded shortcut bar**: the phase More's first press opens, showing the rest of
  the current commands in up to two rows; not another surface.
- **Command reference**: the searchable complete catalog of commands. It includes
  pointer- and platform-triggered commands with no keyboard binding.

## Coined terms

These terms name Leaf concepts that no standard term covers, so they stay:

- **Standing**, not *focus*: a user stands at a target from its margin cluster, its
  thread card, or its note on the details shelf as well as from the element, while DOM
  focus is on one node. Where the two coincide, say *focus*.
- **Trip** and **Journey**, not *navigation*: a trip decides whether to leave a history
  entry (it stays when the user already has the destination), and a journey shares one
  entry across trips. Web navigation always adds an entry, or replaces one.
- **Landing** and **Floor**, not *focus restoration*: a landing is where any step leaves
  the user, including a box's close and a surface's, and the floor is the place in a
  layer that holds nothing, which focus restoration has no name for.
- **Unwind**, not *dismiss*: one Escape takes off whichever step stands innermost, a
  selection or a narrowing as well as a surface, and only surfaces are dismissed.
- **Walk**: ordered movement among one category of destination, as a DOM `TreeWalker` walks;
  roving focus moves within one widget.
- **Frame**, **Text**, and **surface**: the CSS terms (containing block, `margin-trim`)
  each cover half of a frame, which both sizes what it holds and trims its edge margins.
- **Reading posture**, **Bounded block**, and **Margin resident**: whether a region
  scrolls on its own, and what the margin admits, are decisions Leaf makes and reads
  back; *scroll container* names only the CSS outcome.
- **Rail**: the strip of margin rows beside the column. A *gutter* is a code editor's
  line-number strip, and Material's *navigation rail* holds destinations, not notes.
- **Details shelf**: the one chrome container holding the notes an element names through
  `aria-details`; ARIA names the relation, not a place to keep its targets.
- **Layer stack**: Leaf's ordered record of the popovers and dialogs in the platform's
  *top layer*, which the platform keeps but does not expose.
- **Key badge**: a keycap-shaped label that carries a hint code as well as a binding,
  so *keycap* alone would misname half its uses.

**Pin**, **Banner**, **Drawer**, **Toolbar**, and **Picker** keep their ordinary UI
meanings. Qualify **picker** (the target picker, the version picker) where the reaction
picker could be meant.
