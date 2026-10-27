<!-- @noformat -->
<!-- Table padding exceeds the harness's 30,000-character single-read limit. -->

# Leaf glossary

The canonical names for the page a user sees and operates. Use them in element
declarations, JavaScript, CSS, visible copy, tests, examples and references. Where an
existing name disagrees, rename it rather than adding an alias. Events, comments,
threads, replies, obligations and activity are named by their protocol references, not here.

A term gets an entry once current behavior gives it a stable identity. Name the
narrowest established kind, and use the web platform's or UI design's name where one
exists (a drawer, a focus ring, a sticky header, a full-height layout). Give familiar
terms precise Leaf-specific definitions where needed; a name need not express every
rule of the concept it names. Qualify a noun another web or Leaf concept also uses.

## Reader-facing words

Use these words in UI labels, command help, errors and prose. Protocol fields and
implementation terms keep their exact spelling where the reader needs them.

| Term | Meaning and visible use |
|---|---|
| **Page** | The document the user reads and acts on |
| **Update** | One input the user sends the agent, of any kind, or several of mixed kinds: “Updates are saved” |
| **Response** | Work owed to user input of unknown kind: “2 responses owed” |
| **Answer** | The current value of an obligation, or the response that satisfies a user update; there is no separate Answer record |
| **Reply** | A message in a conversation, including an answer or an unprompted message |
| **Delivery** | How far an update has got toward the agent: **Queued for Claude** until a harness has queued it (**Up next**, stage `queued`) or handed it into the agent's turn (**Got it**, stage `picked_up`). Got it doesn't mean work has begun |
| **Queued for Claude** | An update no harness has queued or opened into a turn (stages `sending` and `sent`), whether or not the log has accepted it, in Leaf's italic voice with the agent's name; past the pickup grace it reads **Still queued for Claude** |
| **On it** | The agent has explicitly started this update or to-do (stage `working`); page activity alone doesn't mean it has |
| **Undo** | Taking back the user's latest update that can be taken back, leaving the user at what it changed (`undo.js`) |
| **Threads** | The mark in Leaf's panel and the view it opens, listing conversations. A **thread** is one conversation; a **comment box** is the field where the user writes a comment or reply |
| **Version** | A stamped page the user can revisit: **Showing v4** in the version picker, or **Showing Draft** for the live unstamped source |

Leaf's interface speaks in the agent's voice: the user is talking with the agent, and
the page is where that conversation happens. Every status, notice and label reads as
something the agent would say to the user in conversation (“Got it”, “Your turn”,
“running the browser suite”, “Lost the connection — reconnecting”), with no name in
front of it and never as a narrator describing the agent from outside (“Claude is
working”, “Waiting for Claude”), which puts a third party between them. A line Leaf
composes from what it observes, such as an agent that stopped or a server it can't
reach, is Leaf's best guess at what the agent would say, and reads the same way. Only
words the agent can't be saying, such as an instruction about the agent (“Not
answering — nudge the terminal”), Leaf's own state (“Lost the connection —
reconnecting”), an update the agent doesn't have yet (“Queued for Claude”, which
names the agent because the agent isn't the one speaking) or an error, are set apart
in italic, as a script sets a stage direction
apart from the lines (`pageStatus`, `voice`).

The agent's lines take no first person, so *me* and *my* always mean the user: **Me**
as an author, **Waiting on me** and **On me**, **my change**, and commands such as
**Edit my last message**. Never narrate what the user saw, decided or is doing (*since
I last looked*), since Leaf can't know it. Text addressed to the agent, such as
`x-instructions` and event handling, uses the second person, as does the website's
prose to a visitor.

Visible copy is personal, not technical: it speaks of the user, the agent and the page,
never of the machinery between them. Say what the user did (“Moved to Done”) or what
the agent is doing, not that something was sent, logged, stored or retried. Name the
machinery only where the user must act on it, as an unreachable server asks them to keep
the tab open.

Name an update's kind where it is known: a **comment**, **reply**, **choice**
or **reaction**; in protocol text a widget's is an **action**, after its
event kind. Don't call an update a *move* or *feedback*, or an *input* as a count noun;
*input* stays as a mass noun (“waiting for input”). Only the user's input is an update:
a worker's news is a **report**, and the agent's interim thread message a **progress
message**. The **working message** is the agent's current line, shown where it was said
until an answer replaces it. Update counts don't count revisions. Where the kind is
known, say **answer** or **reply** rather than *response*; On *agent* lists a reply the
agent owes as **Reply** and a revision it owes as **Answer**. Undo keeps its name
whatever widget action it takes back.

**All pages**, a view of Leaf's panel opened from Navigate in the leaf's menu, lists
live pages on this machine. **Not on this page right now** means no agent session holds
the page, in the panel's status and on All pages' rows. **Done with this page** means
the page's work has ended.

## Pages, packages, and layers

| Term | Identity criterion |
|---|---|
| **Page directory** | The directory containing a page’s source, revisions, selected layer, data, media and event history |
| **Package** | One composable source directory of declarations and their payload. Its code runs in the page document beside every other script, so a package bounds reuse, not reach |
| **Leaf layer** | One checked, vendored composition of packages |
| **User session** | One browser tab's temporary interaction with a page: its focus, scroll, selection and throwaway exploration |
| **In force** | An action, report, reaction or decision that no undo took back and no version note retracted; for each widget, unit and action kind, the latest one in force sets the state (`events.InForce`, `StateProjection.in_force`; the served event field is still called `stands`) |

For an authored occurrence say *Leaf element*, never *instance* alone.

## Declarations and elements

| Term | Identity criterion |
|---|---|
| **Leaf element type** | One registered `lf-*` tag |
| **Element declaration** | The registry record for one Leaf element type |
| **Element** | One authored HTML occurrence; a **Leaf element** uses a registered `lf-*` tag |
| **Widget** | A complete user-facing page feature, such as a chart, choice control or board. Leaf widgets are authored as Leaf elements |
| **Component** | A reusable implementation building block, such as a widget’s legend or an internal control. Use *widget* for the complete page feature and *element* for its authored HTML |
| **Compound owner** | A Leaf element whose body holds declared direct members |
| **Compound member** | A Leaf element whose declaration names the owner types that may hold it directly (`x-owners`) |
| **Structural element** | A Leaf element with a declared role in reading structure (`x-reading-role`) |
| **Addressable element** | An authored element with an id that a user can target |

An element declaration keeps independent properties in separate keys, which the
registry's `$keys` defines; an `x-*` key declares a capability, not an element family.

Don't say *widget entry* for an element declaration, *item* for an addressable element
or an obligation (it stays ordinary English for a list item or a row of a list), or
*holder* for a compound owner.

## Authored reading structure

| Term | Identity criterion |
|---|---|
| **Page shell** | The body-level box that sizes the page after the chrome takes its space |
| **Content frame** | `body > main`, the root of authored content and its reading column when its scroll behavior is `flow` |
| **Layout** | A shipped class (`layouts.css`, the `lf-layouts` cascade layer) that arranges the box it is on: a page Layout on the content frame only, `layout-tiles` on any block |
| **Frame** | A box whose size comes from outside it, such as `main`, a root tab panel, a part, a pane or a cell of a Layout, or any box declaring `--lf-block-frame`. It sets its children's width and trims their outer margins |
| **Text** and **surface** | How a block uses its frame's width. Text (a paragraph, list item, quote, caption, heading, or a block given the column) keeps the reading measure. Every other block is a surface and takes the width its frame allows: `wide` up to `--wide`, `available` all of it |
| **Bounded block** | A block that keeps its own height and scrolls inside it (`x-bound`, `data-bound`), which makes it a reading region |
| **Sidebar page** | A content frame on `layout-sidebar`, as wide as the window up to a cap, with the body beside its `aside` when both fit |
| **Margin sidebar** | `aside.sidebar` on a column page: supporting material, usually navigation, in the left margin where it fits and in flow otherwise |
| **Workspace** | A page on `main.layout-workspace`, which keeps task regions together |
| **Part** | One `lf-part` of a page of parts, listed down the window's left edge under the page's title (`page-layout.md`, "A page of parts"). Not a **view**, which is Leaf's panel's |
| **Full-height** | A workspace that exactly fills the window, where the window is large enough (`--lf-full-height: 1` on `main`); the web calls it a full-height or app-shell layout |
| **Pane** | One reading region, usually in a workspace: an optional header, exactly one body element, an optional footer |
| **Reading region** | A stable place on the page that navigation and reading-position recovery use |
| **Effective reading scroller** | The scroll container that currently scrolls one reading region |
| **Sticky header** | A sticky box of known height covering the top of its scroller, such as an `lf-diff` file header or a root `lf-tabs` strip (`module-scroll-and-motion.md`, "Sticky headers") |
| **Scroll behavior** | Whether a region's body scrolls on its own (`bounded`) or its container scrolls it (`flow`). The stylesheet decides it and the runtime reads it |

A root `lf-tabs` and an embedded `lf-tabs` are the same element type; placement changes
only how they look. Only a full-height workspace gives a pane `bounded` scroll
behavior. A compound widget may own reading regions without being a pane.

## Chrome and the Leaf panel

| Term | Identity criterion |
|---|---|
| **Chrome** | Interface the runtime draws outside authored content, rooted at the one `.lf-chrome` container |
| **Leaf panel** | Leaf's chrome (`floating-panel.js`): one box floating at the bottom of the window. Its **row** contains the leaf, the comment field, and one **seat** at the end. That seat shows the **On me mark**, with its count and a dot when a thread has an unread reply. While a view or stance is active, the seat instead shows the ✕ that closes it. A **folded** panel shows only the leaf in the window's corner |
| **Leaf** | The mark at the row's start, coloured by the agent's state; a press opens the leaf's menu, or unfolds a folded panel |
| **Leaf's menu** | The small menu above the leaf of the page's other controls (`page-controls.js`), one line each with its shortcut. A row ending in a chevron opens its list in the menu's place: Navigate, Annotations, About this page, Versions |
| **Comment field** | The panel's one box for writing: a page comment, or a reply while a thread is open. Search uses the same space with a persistent **Search page** or **Search threads** label and keeps the comment draft and caret. Outside search, the empty field shows the agent's status, a temporary notice or a walk's position in place of a placeholder; in an open thread it shows whose turn it is and a walk's position beside the leaf, and Reply with its key at its end |
| **View** | What opens above the row and covers the page beneath it: a thread, the On view (tabs On me, On *agent*, Threads and the plan) or All pages. Escape or a press on the page closes it |

A view takes no width from the page and leaves it live. A thread about a passage opens
as a **thread card** beside its words, and in the panel where nothing on the page
draws it or the user moves it there with the card's **Open in panel**. A comment on selected words is written in the **anchored comment box**, which
opens beside them and becomes their thread card on Send.

## Page Map and the margin

**Page Map** is the page's inventory of every destination and action, shown two ways:
the compact **margin projection** beside the page, and the searchable **Page Map
dialog**. The margin projection has its own terms:

| Term | Identity criterion |
|---|---|
| **Rail** | The strip right of `main` where margin rows sit beside their targets, where there is room, without moving the column (`page-layout.md`, "The rail and the margin") |
| **Margin content** | Something the margin holds where there is room beside `main`: the rail, the contents map, a column page's first sidebar, its sidenotes (`marginContentLayout` in `prepaint.js`) |
| **Margin row** | One row tied to a target and aligned with it, placed in the `rail`, as a `pin`, or `withheld` (`groupFor` in `annotation-inventory.js` says which rows a target gets) |
| **Pin** | A margin row drawn over the page beside its target, used where the row can't sit in the rail (`rowPlacement`; `seatRows` in `margin-placement.js` places it) |
| **Folded pin** | A pin drawn as its options' toggle alone (`data-lf-folded`) because its full face found no room |
| **Margin lane** | The layer holding one scroller's margin rows: the root lane for the document, and one lane per bounded reading region, clipped to what that region shows |
| **Margin cluster** | The visible group attached to one target |
| **Margin contribution** | One provider's registered bundle of margin content |
| **Margin entry** | One ranked action, disclosure or status in a contribution |
| **Contributed control** | A margin entry a package adds to a target's cluster, such as a suggestion's Accept and Reject |

A row is *withheld* while no part of its target shows in its region, as inside a closed
`details` or an inactive tab; the word says nothing about whether it will appear later.

## Contents outline

`lf-toc` requests the **contents outline**, navigation built from the page's headings.
Where the margin has room it may show the **contents spine** instead, which spreads
the headings over the document's height.

## Keyboard interactions

| Term | Identity criterion |
|---|---|
| **Scope** | A registered boundary where commands apply and can hide outer ones |
| **Design mode** | The `l` interaction that turns input into interface comments until the user exits |
| **Draw mode** | The `w` interaction that turns pointer input into a drawing until the user exits |
| **Annotation layer** | Everything Leaf draws over the page's content: pins, marks on commented and reacted passages, an open card, an unfolded cluster, but not the rail. `o` toggles whether it shows |
| **Go-to sequence** | The `g` keys: Leaf paints hint codes on the current Go-to targets and goes to the one whose code the user types |
| **Target picker** | The `s` interaction that shows addressable elements and ends when the user picks one or closes it |
| **Page search** | The `/` interaction that filters or steps through text matches for a query |
| **Walk** | Stepping in order through one kind of destination: open threads (`t`), the user's On me list (`m`), a list's rows. A press steps off the stop the user is on, in its destination, and arrives at one they are only at, such as one they just left with Escape (`current-target.js`) |
| **Obligation** | What a widget or an agent's message waits on the user for, what an update the user handed over is owed, or a to-do given to the user (`obligations.py`, `readObligations()`): its prompt, its answer once given, its status and its next actor, under an id that never changes (`widget:<id>`, `message:<message>`, `update:<event-id>`, or the to-do's own id). A thread is never one |
| **On me** | The user's list of everything waiting on them (`queues.on_user`): the open obligations whose next actor is the user and the to-dos the agent gave them. `m` walks it. Labels for what waits on the user name the list, as **Next on me** and **Waiting on me** do, and a row names its obligation by the widget's word (`x-word`) |
| **On *agent*** | The agent's list of everything waiting on it (`queues.on_agent`), named for the agent, such as **On Claude**: the obligations whose next actor is the agent and its own to-dos. Prose about no particular agent writes `On <agent>` |
| **To-do** | Explicit work owed until it ends (`todo` in the protocol), by the agent or by the user |
| **Plan** | The agent's outline of the page's work (`plan` in the protocol): goals and steps by depth, each step plain or naming a to-do or obligation, which it arranges without owning |
| **Tally** | `lf-tally`: how many of a region's obligations are still open and whose turn each is, “2 of 8 to answer · 1 on Claude”, with an optional Next on me that walks the region's obligations waiting on the user |
| **Deck** | `lf-deck`: cards worked through one at a time, each holding its own obligations. An answered card moves on by itself; **Later** leaves one waiting for the end of the pass and records nothing |
| **Resend** | An update a harness handed back to the user to send again: its obligation stays in On me, next actor the user, until they do |
| **Done** | The control with which the user ends a to-do the agent gave them (`todo_end`). A widget may also call its own submit control Done |
| **Done items** | The items that left either list, under a Done heading at the foot of the On view; resolved threads stand likewise under Resolved at the foot of Threads |
| **Navigation step** | One move to a destination, such as a thread's passage, an obligation, or the element a followed fragment link names. It clears any surface hiding the destination, then stays put if the user already sees it, or moves and adds a history entry (`history.js`) |
| **Navigation group** | Consecutive navigation steps, each starting where the last landed, that share one history entry, so Back returns to where the first began |
| **Current location** | The destination the user is at, directly or through a control inside it: a thread on the page or in the panel, an obligation, or authored page content. A panel thread's title and its messages are one destination; chrome controls, margin rows, comment notes and contents links are not destinations |
| **Current target** | The addressable element the user is at, whether focus is on the element, inside it, on its margin cluster, on a note it names on the details shelf, or on the thread card showing its threads (`current-target.js`) |
| **Floor** | The place in a layer where the user is at nothing: the page's body, or an open view of Leaf's panel as a whole |
| **Unwind** | What one Escape closes: the innermost open step, decided by what is open now (`runtime/keyboard/AGENTS.md`, "Escape"). It lands the user on the parent of what it closed |
| **Landing** | Where a step leaves the user. Closing a box lands on its container, leaving a destination lands on the layer's floor, and closing a surface lands on the document block the user was reading |
| **Layer stack** | Leaf's ordered record of the popovers and modal dialogs open over the page (`keyboard/layer-stack.js`); an open view of Leaf's panel sits beneath it without being an entry |
| **Focus ring** | The one ring on whatever takes the user's next press: a focused control, a bounded decision, an obligation the user is at. It shows the current location as well as DOM focus (`--focus-ring` in `theme.css`) |
| **Key badge** | A keycap-shaped label for a binding or a hint code |
| **Binding badge** | A key badge showing a command's current binding |

Only Design mode and Draw mode are *modes*, lasting until an explicit exit; `o`
toggles what the page shows without changing what input means. Commands have stable
dotted ids.

A *binding* is one key a scope's row declares for a command; code, the register and
package authors use this word. A *shortcut* is the whole key sequence a user
presses, prefix included (`g d`), and the only word visible text uses. A *keyboard
route* is any keyboard path to an action, including Tab to a native control. A row's
`routes` are its extra keyed meanings, each with its own id and binding.

The **command reference** is the keyboard help: the searchable catalog of all
commands, including pointer and platform ones with no key, opened by `?` or Keyboard
shortcuts in the leaf's menu.

## Related terms

The current location may be a target reached through its margin cluster, thread card
or note on the details shelf, while DOM focus is on one node. Say *focus* when naming
that browser state and *current location* for the destination it represents. An event
not taken back is *in force*, the latest value is *current*, and work still owed is
*open*.

These distinctions clarify related terms:

- **Landing** and **Floor**, not *focus restoration*, which names neither where a step
  leaves the user nor the place that holds nothing.
- **Unwind**, not *dismiss*: one Escape can close a selection or a filter as well as a
  surface, and only surfaces are dismissed.
- **Walk**: stepping through one kind of destination, as a DOM `TreeWalker` does;
  roving focus moves only within one widget.
- **Frame**, **Text** and **surface**: CSS's *containing block* names a box that sizes
  its children, and `margin-trim` the trimming of their edge margins; a frame does
  both.
- **Rail**: a *gutter* is a code editor's line-number strip, and Material's
  *navigation rail* holds destinations, not notes.
- **Details shelf**: the one chrome container for the notes an element names through
  `aria-details`; ARIA names the relation, not a place to keep the notes.
- **Layer stack**: Leaf's record of the popovers and dialogs in the platform's *top
  layer*, which the platform keeps but doesn't expose.
- **Key badge**: it carries hint codes as well as bindings, so *keycap* would misname
  half its uses.
- **Tally**: a *progress indicator* draws completion as a bar or ring, and a *counter*
  counts anything; a tally counts a region's open obligations against their total and leads to the next.

**Pin**, **Toolbar** and **Picker** keep their ordinary UI meanings. Qualify **picker**
(the target picker, the version picker) where the reaction picker could be meant.
