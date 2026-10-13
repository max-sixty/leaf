# Leaf glossary

The canonical names for the page a user sees and operates. Use them in element
declarations, JavaScript, CSS, visible copy, tests, examples, and references. Where an
existing name disagrees, rename it rather than adding an alias. Events, comments,
threads, replies, asks, and activity are named by their protocol references, not here.

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
| **Page** | The document the user reads and acts on; *page instance* below names its durable directory |
| **Update** | One input the user sends the agent, of any kind, or a mixed collection of them: “Updates are saved” |
| **Response** | Work owed to user input whose kind is not known: “2 responses owed” |
| **Answer** | The current value within an ask, or the response that satisfies a user update. An ask contains its answer; no separate Answer record exists |
| **Reply** | A message in a conversation, including an answer or a proactive message |
| **Delivery** | How far an update has got toward the agent: **Sending**, **Sent**, **Queued**, then **Picked up**. Picked up does not claim work has begun |
| **Sent** | The delivery state of an update Leaf has logged that no harness has yet queued or opened into a turn (stage `sent` in `workflows.py`); before the log accepts it, the browser shows **Sending**. A message shows it, as does the margin row of the widget a widget action acted on |
| **Working** | The agent has explicitly started this update or to-do; page activity alone does not establish it |
| **Undo** | Taking back the latest eligible user update |
| **Threads** | The control and panel listing conversations. A **thread** is one conversation; a **comment box** is the field where the user writes a comment or reply |
| **Version** | A stamped page the user can revisit: **Showing v4** in the version picker, or **Showing Draft** for the live unstamped source |

Visible copy speaks in the user's voice, since the page is their own space. What is
theirs is named in the first person: **Me** as an author, **Waiting on me**, **My turn
to answer**, **my change**, and commands such as **Edit my last message**. What Leaf
reports to them drops the pronoun rather than saying *you* or *my*: “The draft is
kept”, “retrying the change”, “not in the version shown”. Text addressed to the agent,
such as `x-instructions` and event handling, stays in the second person, as does the
website's prose to a visitor.

Name an update's kind where it is known: a **comment**, **reply**, **choice**,
**reaction** or **approval**; in protocol text a widget's is an **action**, after its
event kind. Don't call an update a *move* or *feedback*, or an *input* as a count noun
(“an input”, “inputs”); *input* stays as a mass noun (“waiting for input”). Only the
user's input is an update: a worker's news is a **report**, and the agent's interim
thread message a **progress message**. Until an answer folds it, the thread draws the agent's
current line at its foot as the **working message**: a message's head over dim words, with
the sheen of a title being generated while the work runs. Update counts do not count revisions. Where the
kind is known, say **answer** or **reply** rather than *response*; the Questions panel
lists a reply the agent owes as **Reply** and a revision it owes as **Answer**. Undo
keeps its name whatever widget verb it withdraws.

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
| **In force** | An action, report, reaction or decision that no undo withdrew and no version note retracted; at each owner-unit-verb coordinate the latest in force wins (`events.InForce`, `StateProjection.in_force`; the served event field keeps its name, `stands`) |

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
- `x-owners`, the compound owner types that may hold it directly; with `x-within`, it
  may also stand at any depth inside the regions that key names, belonging to the
  nearest owner around them.
- `x-reading-role`, an authored reading-structure role.
- Every other `x-*` key declares a capability, not an element family.

Don't say *widget entry* for an element declaration, *item* for an addressable element
(it stays ordinary English for a list item), or *holder* for a compound owner.

## Authored reading structure

| Term | Identity criterion |
|---|---|
| **Page shell** | The body-level responsive sizing envelope after chrome reservations |
| **Content frame** | `body > main`, the root of authored content and its reading column in flow posture |
| **Layout** | A shipped class (`layouts.css`, the `lf-layouts` cascade layer) that arranges the box it is on: the page Layouts `layout-column`, `layout-sidebar` and `layout-workspace` on the content frame alone, and `layout-tiles` on any block |
| **Frame** | A box whose size comes from outside it: `main`, a root tab panel, a pane, a cell of a Layout or of the page's own grid, or any box declaring `--lf-block-frame`, whose values `theme.css` defines |
| **Text** and **surface** | How a block uses its frame's width. Text (a paragraph, list item, term or description, quote, caption or heading, or a block allocated the column) keeps the reading measure; every other box is a surface that uses the room its frame permits, with `wide` capped at `--wide` and `available` taking the available room |
| **Bounded block** | A block that holds its own height and scrolls inside it (`x-bound`, `data-bound`), which makes it a reading region |
| **Sidebar page** | A content frame on `layout-sidebar`, as wide as the window up to a cap: a wrapping layout placing the body beside its `aside` when both fit, with a header and footer across both. Every block starts at its region's left edge and takes its width, while text keeps the reading measure |
| **Margin sidebar** | `aside.sidebar`: page-level supporting material, typically navigation, in a column page's left margin where it fits and in flow otherwise. It creates no side-by-side content regions |
| **Workspace** | A page on `main.layout-workspace`, which keeps task regions together |
| **Full-height** | A workspace that fills the window exactly, where the window is large enough, marked by `--lf-full-height: 1` on `main`; the web calls it a full-height or app-shell layout. `layouts.css` says which of its boxes scroll |
| **Pane** | One reading region, typically in a workspace's body: an optional header, exactly one body element, an optional footer |
| **Reading region** | A stable semantic place used by navigation and reading-position recovery |
| **Effective reading scroller** | The scroll container currently governing one reading region |
| **Sticky header** | A sticky box of stated height that covers the top of the scroller it sticks in, such as an `lf-diff` file header, a root `lf-tabs` strip, or an open thread's title in the Threads list; `module-authoring.md`, "Sticky headers", says how headers stack |
| **Reading posture** | Whether a region's body scrolls on its own (`bounded`) or its container carries it (`flow`). The stylesheet decides it and the runtime reads it |

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
| **Leaf panel** | Opt-in chrome (`?lf-chrome=floating`, `floating-panel.js`): one box floating over the window's foot whose resting row holds the leaf, coloured by the agent's state and opening the leaf's menu of the page's other controls; the comment field, which shows the agent's status and passing notices while empty; and the Questions and Threads marks. Threads, Questions, Versions and the menu's groups open as views above that row, and folding leaves the leaf alone in the window's corner. It stands for the banner and the bottom bar, drawing their controls from the toolbar's rows (`banner-toolbar.js`) |
| **Banner** | Default chrome, which `?lf-chrome=classic` also restores after the Leaf panel was chosen (`prepaint.js`): the fixed row at the window's top: page status ending with the agent's Tasks count, the primary Approval, Comment on the page, Questions and Threads controls, and an overflow disclosure of secondary controls (`banner-toolbar.js` says where each control sits) |
| **Page comment card** | The card hung from the banner's Comment on the page control, holding the page's general comment box, the one place a page thread starts (`thread/page-comment.js`) |
| **Bottom bar** | Classic chrome's row at the window's foot, at one stated height (`--lf-bottom-bar-h`), holding the shortcut bar and the status |
| **Auxiliary surface** | Chrome opened `beside`, `over`, or `covering` the content frame |
| **Side panel** | The right-edge slot, with one width and one drawn edge, that the thread panel and the Questions panel take turns in; Questions and Threads are its two banner doors |
| **Thread panel** | The auxiliary surface listing threads, one of the two that take turns in the side panel |
| **Drawer** | An auxiliary surface built as a head over a list of rows, one open at a time: the Questions panel at the right edge, in the side panel, and the Pages drawer at the left |

The current drawers are the **Questions panel** (experimental) and the **Pages drawer**. Use *covering auxiliary
surface*, not *modal workspace*: a covering surface and a modal dialog are different
web interaction primitives. A covering surface makes the page inert behind it; a surface
over the page, such as the thread panel on a desktop window, takes no width from
it and leaves it live. A **sticky header** covers one edge of one scroller, and nothing
about it is modal.

## Page Map and the margin

**Page Map** is the page inventory, every destination and action on the page, shown
two ways: the compact **margin projection** beside the page, and the searchable modal
**Page Map dialog**. The margin projection has its own terms:

| Term | Identity criterion |
|---|---|
| **Rail** | The strip right of `main` where margin rows sit beside their targets. Seated where the room beside `main` holds it, it never moves the column; only `data-rail="right"` on `body` makes the shell give up the rail's width, so the page's layout gets narrower (`annotation-theme.css`). `page-authoring.md`, "The rail and the margin", says when a page has one |
| **Margin resident** | Something the page's margin holds: the rail, the contents map, a column's first sidebar, its sidenotes. One measurement, prepaint.js `residency`, admits each where the room beside `main` holds it |
| **Margin row** | One target-anchored row whose placement is `rail`, `pin`, or `withheld` |
| **Pin** | A margin row drawn over the page by its target, used where the row cannot sit in the rail (`rowPosture`). It sits at the end of its target's text or inside its target's top-right corner, or, where that would cover words, a control, another block or another pin, at the nearest free spot that still reads as its target's (`pinSpot` in `margin-placement.js`). Where no such spot exists, it folds or tries clear space outside its containing boundary. Without a clear seat it is withheld, and Page Map retains its thread and actions (`seatRows`, `margin-layout.js`) |
| **Folded pin** | A pin drawn as its options' toggle alone (`data-lf-folded`) because its whole face found no room (`seatRows` in `margin-placement.js`) |
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
| **Annotation layer** | Everything Leaf draws over the page's content: pins, the marks on commented and reacted passages, an open card, an unfolded cluster. The rail is not part of it. `o` toggles whether it shows |
| **Go-to sequence** | The `g` prefix grammar that builds a current map of Go-to targets, paints transient hint codes, and resolves complete ordered addresses |
| **Target picker** | The `s` interaction that presents addressable elements and ends when the user chooses one or closes it |
| **Page search** | The `/` interaction that filters or walks text matches for a query |
| **Walk** | Ordered semantic movement among one category of destination: open threads (`t`), the user's Questions (`q`), a list's rows |
| **Questions** | The user's list, everything waiting on the user (`queues.questions`): open asks, to-dos the agent put on the user, and resends. An open ask the user has commented on leaves it until the agent replies, since the comment's answer is then on Tasks. The banner's Questions control opens the Questions panel, and the `q` walk steps through the same list; the panel's Done fold holds completed asks and to-dos |
| **Tasks** | The agent's list, everything waiting on the agent (`queues.tasks`): answers it owes, work in hand, and its own to-dos. The banner ends with its count, and the Questions panel shows it as its Tasks section. A message the user sends counts among Tasks as an answer the agent owes before any to-do exists |
| **Ask** | One core record of a request for the user's input, with its typed answer and its lifecycle. A widget ask has identity `widget:<source-id>`; a prose ask, from a reply sent with `--ask`, has `reply:<agent-message-id>`; an approval ask, `approval:v<version>`, tracks a stamped version's sign-off. Widget state owns a widget ask's values, and the conversation owns a prose ask's settlement. An optional `lf-ask` frames one or more asks with prompt context without changing their identity. An ask is distinct from a to-do and from a resend |
| **To-do** | Explicit work owed until it ends (`todo` in the protocol), by the agent or by the user. An ask is a separate record, not a to-do |
| **Tally** | `lf-tally`: how many of the asks a region holds (`asksIn`) are still open, “7 of 8 to answer”, with an optional Next question that walks the region's asks waiting on the user |
| **Resend** | An update the user has to send again, which stays on Questions until they do |
| **Done** | The control with which the user ends a to-do the agent put on them; it writes `todo_end`. A widget may also name its own answer-submission control Done |
| **Done fold** | The Questions panel's third list, below Questions and Tasks: asks answered, here or elsewhere, or withdrawn, and to-dos ended |
| **Trip** | One travel to a destination (a thread's passage, an ask, a datum, or the element a followed fragment link names): it clears the auxiliary surface hiding the destination, then stays where the user already has it, or departs and leaves a history entry (`history.js`) |
| **Journey** | Consecutive trips each leaving from the last one's landing, which share one history entry so Back returns to where the first began; it may mix threads and asks, and is not a walk |
| **Standing** | Holding a destination or a control inside it: a thread on the page or in the panel, an ask, or authored page content. A panel thread's title and its messages are one destination; chrome controls, margin rows, comment notes, and contents-outline links are apparatus, not destinations |
| **Standing target** | The addressable element the user stands at, whether they hold the element or something inside it, its margin cluster, a note it names on the details shelf, or the thread card showing its threads (`standing-target.js`) |
| **Floor** | The place in a layer where the user stands on nothing: the page's body, the whole thread panel |
| **Unwind** | What Escape takes off, read from what stands in front of the user rather than from how they reached it: the innermost step of the ladder `skills/leaf/assets/runtime/keyboard/AGENTS.md` states, with containment before kind, each landing them at the parent of what it closed |
| **Landing** | Where a step leaves the user. Closing a box lands on its container, ending a standing lands on the layer's floor, and closing a surface lands on the document block the user was reading, which is focused and then blurred |
| **Layer stack** | The one ordered record of the popovers and modal dialogs open over the page, in the order they opened (`keyboard/layer-stack.js`); a covering auxiliary surface is its floor without being an entry |
| **Focus ring** | The one ring on whatever takes the user's next press: a focused control, a bounded decision, an ask stood at. It marks standing as well as DOM focus; `theme.css` (`--lf-focus-ring`) says how a rule draws it |
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
  focus is on one node. Where the two coincide, say *focus*. *Standing* means only
  where the user is: say *in force* for an event not withdrawn, *current* for the
  latest value, *open* for something still owed or on screen, and *persistent* for a
  serve that outlives sessions.
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
- **Tally**: a *progress indicator* draws completion as a bar or ring and a *counter*
  counts anything; a tally counts what is left of one region's asks against their whole
  and leads to the next, so neither name says what it counts or that it navigates.

**Pin**, **Banner**, **Drawer**, **Toolbar**, and **Picker** keep their ordinary UI
meanings. Qualify **picker** (the target picker, the version picker) where the reaction
picker could be meant.
