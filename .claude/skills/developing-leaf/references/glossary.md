# Leaf glossary

The canonical names for the page a user sees and operates. Use them in element
declarations, JavaScript, CSS, visible copy, tests, examples, and references. Where an
existing name disagrees, rename it rather than adding an alias. Events, comments,
threads, replies, Questions, and activity are named by their protocol references, not here.

A term gets an entry once current behavior gives it a stable identity. Name the
narrowest established kind, and where the web platform or UI design already names the
thing (a drawer, a focus ring, a sticky header, a full-height layout), use that name.
Coin a word only where no standard name fits, and record under "Coined terms" which
standard term comes closest and why it doesn't fit. Qualify a noun that another web or
Leaf concept also uses.

## Reader-facing words

Use these words in UI labels, command help, errors and prose. Protocol field names
and implementation terms retain their exact spelling when the reader needs them.

| Term | Meaning and visible use |
|---|---|
| **Page** | The document the user reads and acts on. Use *page* in prose and commands; *page instance* below identifies its durable directory |
| **Update** | A user input of any kind, or a mixed collection of inputs: “Your updates are saved”. Where its kind is known, name the **comment**, **reply**, **choice**, **reaction** or **approval** instead |
| **Response** | Aggregate work owed to user input when its required kind is not available: “2 responses owed”. Where the kind is known, name the **answer** or **reply** instead |
| **Answer** | The current value within a Question, or the response satisfying a user update. A Question contains its own answer; there is no separate Answer identity or collection. Use choice, reply or revision where its kind is known |
| **Reply** | A message in a conversation, including an answer or a proactive message. A reply owed by the agent is separate from delivery and work: the Questions panel calls message obligations **replies** and revision obligations **answers** until they arrive |
| **Delivery** | Whether an update reached the agent. **Sending**, **Queued** and **Picked up** describe delivery; Picked up does not claim work has begun |
| **Working** | The agent is currently working. A particular update or task says Working only when the agent explicitly starts it; page activity alone does not establish that fact |
| **Undo** | Take back the latest eligible user update. Do not rename this action after the widget verb it withdraws |
| **Threads** | The control and panel listing conversations. A **thread** is one conversation; a **comment box** is the field where the user writes a comment or reply |
| **Version** | A stamped page the user can revisit. The version picker says **Showing v4**; a live unstamped source says **Showing Draft**. Update counts do not count revisions |

The **Pages drawer**, opened by **All pages**, lists live pages on this machine. **No session** means no agent
session currently holds the page, on both the banner and neighboring-page rows.
**Page closed** means the page's work has ended.

## Pages, packages, and layers

| Term | Identity criterion |
|---|---|
| **Page instance** | One durable page directory: its source, revisions, selected layer, data, media, and event history |
| **Package** | One composable source directory of declarations and their payload |
| **Leaf layer** | One checked, vendored composition of packages |
| **User session** | One browser tab's temporary interaction with a page instance |

Core Leaf owns revision activation, scoped serving, the executable and inert-input
boundaries, target identity, event admission, comments, and export. A package owns
reusable declarations, widgets, browser modules, styles, data contracts, and instructions.
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
- `x-reading-role`, an authored reading-structure role.
- Every other `x-*` key declares a capability, not an element family.

Don't say *widget entry* for an element declaration, *item* for an addressable element
(it stays ordinary English for a list item), or *holder* for a compound owner.

## Authored reading structure

| Term | Identity criterion |
|---|---|
| **Page shell** | The body-level responsive sizing envelope after chrome reservations |
| **Content frame** | `body > main`, the root of authored content and its reading column in flow posture |
| **Layout** | A shipped class (`layouts.css`, the `lf-layouts` cascade layer) that arranges the box it is on: `layout-column`, `layout-wide`, `layout-sidebar`, `layout-tiles`, `layout-workspace`. A starting point the page's own CSS adjusts; nothing reads it back |
| **Wide page** | A content frame carrying a Layout other than `layout-column`: every block starts at one left edge and takes the page's width, while text keeps the reading measure. It is a width, not a separate kind of page |
| **Frame** | A box whose size comes from outside it: `main`, a root tab panel, a pane, a cell of a Layout or of the page's own grid, or any box declaring `--lf-block-frame`. A frame that draws one (`1`) holds what it holds to its width, never the page's room; a frame that only trims its edges and draws nothing (`trim`: `main`, a root tab panel, a command's goal) lets a surface break out as it would with no frame |
| **Text** and **surface** | How a block uses its frame's width: text (a paragraph, list item, term or description, quote, caption or heading) keeps the reading measure however wide its frame, as does a block allocated the column (`x-space` or `data-width` `column`), starting at the same edge; every other box is a surface that fills its frame. A surface with `x-space` or `data-width` past the column breaks out of it on a column page, and a `wide` one holds to `--wide` in a frame wider than that |
| **Bounded block** | A block that holds its own height and scrolls inside it (`x-bound`, `data-bound`); a reading region while it stands in the page, so what it scrolls moves it rather than the page |
| **Sidebar Layout** | `layout-sidebar`: a wrapping layout inside the content frame, placing the main region beside a smaller supporting region when both fit. It works on wide pages and nested blocks |
| **Margin sidebar** | `aside.sidebar`: page-level supporting material beside a column page, typically navigation. It sits in the left margin where space permits and returns to normal flow in a narrow window. It does not create side-by-side content regions |
| **Workspace** | A page on `main.layout-workspace`, which keeps task regions together |
| **Full-height** | A workspace filling the window exactly, where the window is large enough (`layouts.css`'s media query; `--lf-full-height: 1` on `main`): header and footer at their content's height, one body taking the rest, and the page itself does not scroll. A pane that is the body or a direct cell of it scrolls on its own, as does a pane a widget generates where the widget passes the height on (`--lf-full-height` does not inherit); anything deeper scrolls with the body. A widget that is the body fits what it shows to the height. Elsewhere the workspace flows and the page scrolls. The web's name for the arrangement is a full-height or app-shell layout |
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
| **Banner** | The persistent chrome row carrying page status, which ends with the agent's Tasks count, and the primary Approval, Comment on the page, Questions and Threads controls (Questions and Threads are the two doors to the side panel; the Tasks count opens Questions too), with secondary global controls in its overflow disclosure. While a user's gesture holds a next step, such as Comment on selection after a touch selection or Exit Draw mode while a finger is in Draw mode, that step stands on the row in those primary controls' place |
| **Page comment card** | The card hung from the banner's Comment on the page control (from More's door on a phone), holding the page's general box, the one composer that starts a page thread. A send keeps it open and focused and flashes Threads, where the thread then lives; it shows no thread itself |
| **Bottom bar** | The row at the window's foot, at one stated height (`--lf-bottom-bar-h`), holding the shortcut bar and the status; the page ends above it as it starts below the banner |
| **Auxiliary surface** | Chrome opened `beside`, `over`, or `covering` the content frame |
| **Thread panel** | The right-side auxiliary surface containing threads; it stands over the page and takes no width from it, and covers the page only where it leaves less than a usable page beside it. It shares the right edge, its width and its handle with the Questions panel, one at a time |
| **Drawer** | A mutually exclusive auxiliary surface built as a head over a list of rows, one at a time: the Questions panel slides in at the right edge and stands over the page as the thread panel does, and the Pages drawer slides in at the left and always covers |

The current drawers are the **Questions panel** (experimental) and the **Pages drawer**. Use *covering auxiliary
surface*, not *modal workspace*: a covering surface and a modal dialog are different
web interaction primitives. A covering surface makes the page inert behind it; a surface
over the page, such as the thread panel on a desktop window, takes no width from
it and leaves it live. A covering surface covers the content frame; a **sticky header**
stands over one edge of one scroller, and nothing about it is modal.

## Page Map and the margin

**Page Map** is the page inventory, every destination and action on the page, shown
two ways: the compact **margin projection** beside the page, and the searchable modal
**Page Map dialog**. The margin projection has its own terms:

| Term | Identity criterion |
|---|---|
| **Rail** | The right-hand strip beside `main` where margin rows stand beside their targets. It claims nothing: it stands wherever the room the page leaves right of the centred `main` holds it, and only `data-rail="right"` on `body` makes the shell give it up |
| **Margin resident** | Something the page's margin holds: the rail, the contents map, a column's first sidebar, its sidenotes. One measurement (`settleResidency`) admits them in that order where the room beside `main` holds them, moving the column over by `--lf-shift`, and writes `data-lf-margin` on `main` |
| **Margin row** | One target-anchored row whose placement is `rail`, `pin`, or `withheld` |
| **Pin** | A margin row standing over the page inside its target's top-right corner, where no rail stands: the page declared none, the room beside `main` does not hold one, the target sits in a pane that scrolls on its own, the target reaches past the rail's inner edge, or a hanging note stands level with it. It is an overlay: it covers what lies under it, and nothing reserves room for it or moves when it comes, goes, or changes place |
| **Folded pin** | A pin whose face, a contributed primary and one more control, found no room for both and stands as its options' toggle alone (`data-lf-folded`), seated at that size, wearing the marker face of the kind its primary contribution declares. Placement folds it; the gesture that opens any options opens it, as does the keyboard standing at its target, spreading its actions leftward over whatever stands beside it, the toggle staying under the press |
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
| **Scope** | A registered command-applicability and shadowing boundary |
| **Design mode** | The `l` interaction that reinterprets input for interface comments until the user exits |
| **Draw mode** | The `w` interaction that reinterprets pointer input as a drawing until the user exits |
| **Annotation layer** | Everything Leaf draws over the page's content: the margin rows standing as pins, the durable marks on commented and reacted passages, an open card, an unfolded cluster. The rail covers nothing and is not part of it. The layer takes no room, so showing or hiding any of it moves nothing on the page. `o`, or More's Hide annotations under a finger, toggles whether it shows, as tab view state rather than a mode |
| **Go-to sequence** | The `g` prefix grammar that builds a current map of Go-to targets, paints transient hint codes, and resolves complete ordered addresses |
| **Target picker** | The `s` interaction that presents addressable elements and ends when the user chooses one or closes it |
| **Page search** | The `/` interaction that filters or walks text matches for a query |
| **Walk** | Ordered semantic movement among one category of destination: open threads (`t`), the user's queue (`q`), a list's rows |
| **Queue** | What one side has to act on: the user's open Questions, explicit work tasks and updates to send again (`on_you`), or the agent's response obligations, work in hand and explicit tasks (`on_agent`). The Questions panel and `q` walk select these readings; its Done fold contains completed Questions and tasks |
| **Question** | One core record containing an agent request for user input, its typed answer and its lifecycle. A widget Question has identity `widget:<source-id>`; a prose Question has `reply:<agent-message-id>`. Widget state owns its values, the conversation owns prose settlement, and approval Questions track a stamped version's sign-off. An optional `lf-ask` adds prompt context without changing identity. A Question is distinct from explicit work and delivery recovery |
| **Task** | Explicit work owed by the agent or user, opened with `leaf task open`. Its owner and subject determine how it ends: the agent ends its own work with `leaf task end` or `--completes`; a user work task ends with Done or the agent ending it. Questions are separate records, not derived tasks |
| **Done** | The control ending explicit work the agent put on the user with `--on user`: a button beside its Questions panel row, `x` on that row or where `q` stands on the task, and a touch route on the banner. It writes `task_end`, which `z` takes back. A widget may also name its own answer-submission control Done; the panel's Done fold lists completed Questions and work |
| **Trip** | One travel to a destination, a thread's passage, a Question, a datum, or the element a followed fragment link names: it clears the auxiliary surface hiding the destination, then stays when the user already has it or departs, leaving a history entry. A fragment link always departs, by the entry the browser's navigation adds; Back or Forward to an entry whose fragment names an element the page has hidden since is a trip that departs by no entry |
| **Journey** | Consecutive trips each leaving from the last one's landing, which share one history entry so Back returns to where the first began; it may mix threads and Questions, and is not a walk |
| **Standing** | Holding a destination or a control inside it: a thread on the page or in the panel, a Question, or authored page content. A panel thread's title and its messages are one destination. Chrome controls, margin markers, mark notes, and contents-outline links are apparatus rather than destinations |
| **Standing target** | The addressable element a user stands at, from whichever side they hold it: the element or anything inside it, its margin cluster, a note it names on the details shelf (its comment note, a drawing's response proxies), or the thread card showing its threads. The element is a thread's parent, so the card shows while the user stands at its target and goes when they stand elsewhere on the page or let go. With Threads open, the list's expanded thread plays the card's part. A thread is about exactly its anchor's target, so standing at an element shows the threads of the innermost target holding it that has some (its own, else an enclosing one's), never those of anything inside it: a thread on a Question's options shows from the options, not from the Question. Every side answers alike: an open Question stood at from its card still wears its ring and takes its digits, `c` at an element whose own thread is shown continues it, and `q` and `t` step from the target |
| **Floor** | The place in a layer where the user stands on nothing: the page's body, the whole thread panel |
| **Unwind** | What Escape takes off, read from what stands in front of the user rather than from how they reached it: the innermost step of the ladder `skills/leaf/assets/runtime/keyboard/AGENTS.md` states, with containment before kind, each landing them at the parent of what it closed |
| **Landing** | Where a step leaves the user: a box at its container, a standing at its floor, a surface at the document, which is the block they are reading, focused and then blurred |
| **Layer stack** | The one ordered record of the popovers and modal dialogs standing over the page, in the order they opened; the dispatcher tiers scopes over it, and a covering auxiliary surface is its floor without being an entry |
| **Focus ring** | The one ring on whatever takes the user's next press: a focused control, a bounded decision, a Question stood at. It is drawn as an outline (`--focus-ring`), or as a shadow (`--focus-shadow`) where a box cannot spend its outline, and each rule that draws it names itself in `--lf-focus-ring`. It marks standing as well as DOM focus |
| **Key badge** | A keycap-shaped carrier for a binding or transient hint code |
| **Binding badge** | A key badge showing a command's currently resolved binding |

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
