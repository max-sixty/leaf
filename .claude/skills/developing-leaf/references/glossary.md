# Leaf glossary

The canonical names for the page a user sees and operates. Use them in element
declarations, JavaScript, CSS, visible copy, tests, examples and references. Where an
existing name disagrees, rename it rather than adding an alias. Events, comments,
threads, replies, asks and activity are named by their protocol references, not here.

A term gets an entry once current behavior gives it a stable identity. Name the
narrowest established kind, and use the web platform's or UI design's name where one
exists (a drawer, a focus ring, a sticky header, a full-height layout). Coin a word
only where no standard name fits, and record under "Coined terms" the closest standard
term and why it doesn't fit. Qualify a noun another web or Leaf concept also uses.

## Reader-facing words

Use these words in UI labels, command help, errors and prose. Protocol fields and
implementation terms keep their exact spelling where the reader needs them.

| Term | Meaning and visible use |
|---|---|
| **Page** | The document the user reads and acts on; *page instance* below names its directory |
| **Update** | One input the user sends the agent, of any kind, or several of mixed kinds: “Updates are saved” |
| **Response** | Work owed to user input of unknown kind: “2 responses owed” |
| **Answer** | The current value of an ask, or the response that satisfies a user update. An ask contains its answer; there is no separate Answer record |
| **Reply** | A message in a conversation, including an answer or an unprompted message |
| **Delivery** | How far an update has got toward the agent: **Sending**, **Sent**, **Queued**, then **Picked up**. Picked up doesn't mean work has begun |
| **Sent** | An update Leaf has logged that no harness has queued or opened into a turn yet (stage `sent` in `workflows.py`); before the log accepts it, the browser shows **Sending** |
| **Working** | The agent has explicitly started this update or to-do; page activity alone doesn't mean it has |
| **Undo** | Taking back the user's latest update that can be taken back |
| **Threads** | The control and panel listing conversations. A **thread** is one conversation; a **comment box** is the field where the user writes a comment or reply |
| **Version** | A stamped page the user can revisit: **Showing v4** in the version picker, or **Showing Draft** for the live unstamped source |

Visible copy speaks in the user's voice, since the page is their space. Use the first
person only for labels that tell the user's side from the agent's: **Me** as an
author, **Waiting on me**, **My turn to answer**, **my change**, and commands such as
**Edit my last message**. Never narrate what the user saw, decided or is doing (*since
I last looked*): Leaf can't know it, and saying it in their voice is uncanny. Other
status drops the pronoun rather than saying *you* or *my*: “The draft is kept”, “New
messages”. Text addressed to the agent, such as `x-instructions` and event handling,
uses the second person, as does the website's prose to a visitor.

Name an update's kind where it is known: a **comment**, **reply**, **choice**,
**reaction** or **approval**; in protocol text a widget's is an **action**, after its
event kind. Don't call an update a *move* or *feedback*, or an *input* as a count noun;
*input* stays as a mass noun (“waiting for input”). Only the user's input is an update:
a worker's news is a **report**, and the agent's interim thread message a **progress
message**. Until an answer replaces it, the thread shows the agent's current line at
its foot as the **working message**. Update counts don't count revisions. Where the
kind is known, say **answer** or **reply** rather than *response*; the On panel lists a
reply the agent owes as **Reply** and a revision it owes as **Answer**. Undo keeps its
name whatever widget action it takes back.

The **Pages drawer**, opened by **All pages**, lists live pages on this machine. **No
session** means no agent session holds the page, on the banner and on neighboring-page
rows. **Page closed** means the page's work has ended.

## Pages, packages, and layers

| Term | Identity criterion |
|---|---|
| **Page instance** | One page directory: its source, revisions, selected layer, data, media and event history |
| **Package** | One composable source directory of declarations and their payload |
| **Leaf layer** | One checked, vendored composition of packages |
| **User session** | One browser tab's temporary interaction with a page instance |
| **In force** | An action, report, reaction or decision that no undo took back and no version note retracted. For each widget, unit and action kind, the latest one in force sets the state (`events.InForce`, `StateProjection.in_force`; the served event field is still called `stands`) |

A user session owns focus, scroll, selection and throwaway exploration; a lasting user
choice reaches the page instance through Leaf's events. Code in a package runs in the
page document beside every other script, so moving code into a package changes who
reuses it, not what it can reach.

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
| **Addressable element** | An authored element with an id that a user can target |

An element declaration keeps independent properties in separate keys: `x-content`
(what its body holds: `markup`, `members`, `data` or `empty`), `x-owners` (the compound
owner types that may hold it directly; with `x-within`, it may also sit at any depth
inside the regions that key names), and `x-reading-role` (an authored reading-structure
role). Every other `x-*` key declares a capability, not an element family.

Don't say *widget entry* for an element declaration, *item* for an addressable element
(it stays ordinary English for a list item), or *holder* for a compound owner.

## Authored reading structure

| Term | Identity criterion |
|---|---|
| **Page shell** | The body-level box that sizes the page after the chrome takes its space |
| **Content frame** | `body > main`, the root of authored content and its reading column in flow posture |
| **Layout** | A shipped class (`layouts.css`, the `lf-layouts` cascade layer) that arranges the box it is on: the page Layouts `layout-column`, `layout-sidebar` and `layout-workspace` on the content frame only, and `layout-tiles` on any block |
| **Frame** | A box whose size comes from outside it: `main`, a root tab panel, a pane, a cell of a Layout or of the page's own grid, or any box declaring `--lf-block-frame`. It sets its children's width and trims their outer margins |
| **Text** and **surface** | How a block uses its frame's width. Text (a paragraph, list item, quote, caption, heading, or a block given the column) keeps the reading measure. Every other block is a surface and takes the width its frame allows: `wide` up to `--wide`, `available` all of it |
| **Bounded block** | A block that keeps its own height and scrolls inside it (`x-bound`, `data-bound`), which makes it a reading region |
| **Sidebar page** | A content frame on `layout-sidebar`, as wide as the window up to a cap, with the body beside its `aside` when both fit |
| **Margin sidebar** | `aside.sidebar` on a column page: supporting material, usually navigation, in the left margin where it fits and in flow otherwise |
| **Workspace** | A page on `main.layout-workspace`, which keeps task regions together |
| **Full-height** | A workspace that exactly fills the window, where the window is large enough, marked by `--lf-full-height: 1` on `main`; the web calls it a full-height or app-shell layout |
| **Pane** | One reading region, usually in a workspace: an optional header, exactly one body element, an optional footer |
| **Reading region** | A stable place on the page that navigation and reading-position recovery use |
| **Effective reading scroller** | The scroll container that currently scrolls one reading region |
| **Sticky header** | A sticky box of known height covering the top of its scroller, such as an `lf-diff` file header, a root `lf-tabs` strip, or an open thread's title in the Threads list (`module-scroll-and-motion.md`, "Sticky headers") |
| **Reading posture** | Whether a region's body scrolls on its own (`bounded`) or its container scrolls it (`flow`). The stylesheet decides it and the runtime reads it |

A root `lf-tabs` and an embedded `lf-tabs` are the same element type; placement changes
only how they look. Only a full-height workspace gives a pane bounded posture; any other
pane, including a page tab's, stays in flow. A compound widget may own reading regions
without being a pane, and its own stylesheet decides whether they scroll.

## Chrome and auxiliary surfaces

| Term | Identity criterion |
|---|---|
| **Chrome** | Interface the runtime draws outside authored content, rooted at the one `.lf-chrome` container |
| **Leaf panel** | Opt-in chrome (`?lf-chrome=floating`, `floating-panel.js`) that replaces the banner and bottom bar with one box floating at the window's foot: the leaf, which opens a menu of the page's controls, the comment field, and the On me and Threads marks |
| **Banner** | The default chrome (`?lf-chrome=classic` restores it): the fixed row at the window's top with page status, the agent's count (**On Claude: 2**), the primary controls, and a More menu of the rest (`banner-toolbar.js`) |
| **Page comment card** | The card under the banner's Comment on the page control, holding the page's general comment box, the one place a page thread starts (`thread/page-comment.js`) |
| **Bottom bar** | Classic chrome's row at the window's foot, of fixed height (`--lf-bottom-bar-h`), holding the shortcut bar and the status |
| **Auxiliary surface** | Chrome opened `beside`, `over` or `covering` the content frame |
| **Side panel** | The right-edge slot, with one width and one drawn edge, that the thread panel and the On panel share; the banner's On me and Threads controls open it. The On panel's head is a tab per list, On me and On *agent*, and the open tab serves as its title |
| **Thread panel** | The auxiliary surface listing threads, one of the two in the side panel |
| **Drawer** | An auxiliary surface with a head over a list of rows, one open at a time: the On panel in the side panel, and the Pages drawer at the left |

The current drawers are the **On panel** (experimental) and the **Pages drawer**. Say
*covering auxiliary surface*, not *modal workspace*: a covering surface makes the page
inert behind it, but it is not a modal dialog. A surface over the page, such as the
thread panel on a desktop window, takes no width from the page and leaves it live. A
**sticky header** covers one edge of one scroller and is not modal.

## Page Map and the margin

**Page Map** is the page's inventory of every destination and action, shown two ways:
the compact **margin projection** beside the page, and the searchable **Page Map
dialog**. The margin projection has its own terms:

| Term | Identity criterion |
|---|---|
| **Rail** | The strip right of `main` where margin rows sit beside their targets. It appears where there is room beside `main` and never moves the column; `data-rail="right"` on `body` reserves its width and narrows the page instead (`page-layout.md`, "The rail and the margin") |
| **Margin resident** | Something the margin holds: the rail, the contents map, a column page's first sidebar, its sidenotes. `residency` in `prepaint.js` admits each where there is room beside `main` |
| **Margin row** | One row tied to a target, placed in the `rail`, as a `pin`, or `withheld` |
| **Pin** | A margin row drawn over the page by its target, used where the row can't sit in the rail (`rowPosture`). It takes the first spot touching its target that covers no words, control, media or other pin; with none free it folds, and failing that it covers the target (`seatRows` in `margin-placement.js`) |
| **Folded pin** | A pin drawn as its options' toggle alone (`data-lf-folded`) because its full face found no room |
| **Margin lane** | The layer holding one scroller's margin rows: the root lane for the document, and one lane per bounded reading region, clipped to what that region shows |
| **Margin cluster** | The visible group attached to one target |
| **Margin contribution** | One provider's registered bundle of margin content |
| **Margin entry** | One ranked action, disclosure or status in a contribution |
| **Contributed control** | A margin entry a package adds to a target's cluster, such as a suggestion's Accept and Reject |

A row is *withheld* while no part of its target shows in its region: inside a closed
`details`, in an inactive tab, or in a pane scrolled past it. A withheld row is out of
the tab order; the word says nothing about whether it will appear later.

## Contents outline

`lf-toc` requests the **contents outline**, navigation built from the page's headings.
In flow it lists every included heading; where the margin has room it may show the
**contents spine** instead, which spreads the headings over the document's height.

## Keyboard interactions

| Term | Identity criterion |
|---|---|
| **Scope** | A registered boundary where commands apply and can hide outer ones |
| **Design mode** | The `l` interaction that turns input into interface comments until the user exits |
| **Draw mode** | The `w` interaction that turns pointer input into a drawing until the user exits |
| **Annotation layer** | Everything Leaf draws over the page's content: pins, marks on commented and reacted passages, an open card, an unfolded cluster. The rail is not part of it. `o` toggles whether it shows |
| **Go-to sequence** | The `g` keys: Leaf paints hint codes on the current Go-to targets and goes to the one whose code the user types |
| **Target picker** | The `s` interaction that shows addressable elements and ends when the user picks one or closes it |
| **Page search** | The `/` interaction that filters or steps through text matches for a query |
| **Walk** | Stepping in order through one kind of destination: open threads (`t`), the user's On me list (`m`), a list's rows |
| **On me** | The user's list of everything waiting on them (`queues.on_user`): open asks, to-dos the agent gave them, and resends. An ask the user has commented on leaves it until the agent replies. `m` walks it |
| **On *agent*** | The agent's list of everything waiting on it (`queues.on_agent`), named for the agent, such as **On Claude**: answers it owes, work in hand and its own to-dos. Prose about no particular agent writes `On <agent>` |
| **Ask** | One record of a request for the user's input, with its typed answer: a widget ask (`widget:<source-id>`), a prose ask from a reply sent with `--ask` (`reply:<agent-message-id>`), or an approval ask for a stamped version (`approval:v<version>`). `lf-ask` frames asks with context without changing their ids. The interface calls it an ask, never a question |
| **To-do** | Explicit work owed until it ends (`todo` in the protocol), by the agent or by the user |
| **Tally** | `lf-tally`: how many of a region's asks (`asksIn`) are still open, “7 of 8 to answer”, with an optional Next on me that walks the region's asks waiting on the user |
| **Resend** | An update the user has to send again, which stays in On me until they do |
| **Done** | The control with which the user ends a to-do the agent gave them; it writes `todo_end`. A widget may also call its own submit control Done |
| **Done fold** | The items that left a list, folded under it in the On panel |
| **Trip** | One move to a destination, such as a thread's passage, an ask, or the element a followed fragment link names. It clears any surface hiding the destination, then stays put if the user already sees it, or moves and adds a history entry (`history.js`) |
| **Journey** | Consecutive trips, each starting where the last landed, that share one history entry, so Back returns to where the first began |
| **Standing** | Being at a destination or a control inside it: a thread on the page or in the panel, an ask, or authored page content. A panel thread's title and its messages are one destination; chrome controls, margin rows, comment notes and contents links are not destinations |
| **Standing target** | The addressable element the user is at, whether focus is on the element, inside it, on its margin cluster, on a note it names on the details shelf, or on the thread card showing its threads (`standing-target.js`) |
| **Floor** | The place in a layer where the user is at nothing: the page's body, or the whole thread panel |
| **Unwind** | What one Escape closes: the innermost open step, decided by what is open now rather than how the user got there (`runtime/keyboard/AGENTS.md`, "Escape"). It lands the user on the parent of what it closed |
| **Landing** | Where a step leaves the user. Closing a box lands on its container, leaving a destination lands on the layer's floor, and closing a surface lands on the document block the user was reading |
| **Layer stack** | Leaf's ordered record of the popovers and modal dialogs open over the page (`keyboard/layer-stack.js`); a covering auxiliary surface sits beneath it without being an entry |
| **Focus ring** | The one ring on whatever takes the user's next press: a focused control, a bounded decision, an ask the user is at. It shows standing as well as DOM focus (`--lf-focus-ring` in `theme.css`) |
| **Key badge** | A keycap-shaped label for a binding or a hint code |
| **Binding badge** | A key badge showing a command's current binding |

Only Design mode and Draw mode are *modes*, lasting until an explicit exit. `g` opens a
sequence, `s` a picker, and `o` toggles what the page shows without changing what
input means. Commands have stable dotted ids.

A *binding* is one key a scope's row declares for a command; code, the register and
package authors use the word. A *shortcut* is the whole key sequence a user presses,
prefix included (`g d`), and the only word visible text uses. A *keyboard route* is any
keyboard path to an action, including Tab to a native control. A row's `routes` are
its extra keyed meanings, each with its own id and binding.

The keyboard help comes in three forms:

- **Shortcut bar**: the always-visible list of commands that apply now, in the bottom
  bar.
- **Expanded shortcut bar**: what More's first press opens, the rest of the current
  commands in up to two rows; not another surface.
- **Command reference**: the searchable catalog of all commands, including pointer and
  platform ones with no key.

## Coined terms

These name Leaf concepts no standard term covers:

- **Standing**, not *focus*: a user can be at a target through its margin cluster,
  thread card or note on the details shelf as well as the element, while DOM focus is
  on one node. Where the two coincide, say *focus*. Use *standing* only for where the
  user is: say *in force* for an event not taken back, *current* for the latest value,
  *open* for something still owed or on screen.
- **Trip** and **Journey**, not *navigation*: a trip decides whether to add a history
  entry, and a journey shares one entry across trips, while web navigation always adds
  or replaces one.
- **Landing** and **Floor**, not *focus restoration*: a landing is where any step leaves
  the user, and the floor is the place in a layer that holds nothing; focus restoration
  names neither.
- **Unwind**, not *dismiss*: one Escape can close a selection or a filter as well as a
  surface, and only surfaces are dismissed.
- **Walk**: stepping through one kind of destination, as a DOM `TreeWalker` does;
  roving focus moves only within one widget.
- **Frame**, **Text** and **surface**: CSS's *containing block* names a box that sizes
  its children, and `margin-trim` the trimming of their edge margins; a frame does
  both, so neither name fits.
- **Reading posture**, **Bounded block** and **Margin resident**: whether a region
  scrolls on its own, and what the margin holds, are choices Leaf makes; *scroll
  container* names only the CSS result.
- **Rail**: the strip of margin rows beside the column. A *gutter* is a code editor's
  line-number strip, and Material's *navigation rail* holds destinations, not notes.
- **Details shelf**: the one chrome container for the notes an element names through
  `aria-details`; ARIA names the relation, not a place to keep the notes.
- **Layer stack**: Leaf's record of the popovers and dialogs in the platform's *top
  layer*, which the platform keeps but doesn't expose.
- **Key badge**: it carries hint codes as well as bindings, so *keycap* would misname
  half its uses.
- **Tally**: a *progress indicator* draws completion as a bar or ring, and a *counter*
  counts anything; a tally counts a region's open asks against their total and leads to
  the next one.

**Pin**, **Banner**, **Drawer**, **Toolbar** and **Picker** keep their ordinary UI
meanings. Qualify **picker** (the target picker, the version picker) where the reaction
picker could be meant.
