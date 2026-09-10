# Leaf glossary

This is the canonical vocabulary for the page a reader sees and operates. Use these
names in element declarations, JavaScript, CSS, visible copy, tests, examples, and
references. When an existing name disagrees with this glossary, change the name; do
not add an alias.

This reference does not define the protocol between the page and its agent. Events,
comments, conversations, replies, Asks, requests, receipts, activity, and their
lifecycles are owned by their protocol references.

## How to use the vocabulary

A term earns its own entry when current Leaf behavior can answer both questions:

1. What makes two instances the same kind?
2. What nearby thing is explicitly not that kind?

Name the narrowest established kind. Qualify a noun when another web or Leaf concept
uses the same word. Treat retention and meaning as separate dimensions: a mode can be
tab-scoped without becoming display state, for example.

## Packages, declarations, and elements

| Term | Identity criterion | Not this |
|---|---|---|
| **Package** | One composable source directory containing declarations and their payload | The composed Leaf layer |
| **Leaf layer** | One checked, vendored composition of packages | A CSS cascade layer |
| **Leaf element type** | One registered `lf-*` tag identity | A `$*` layer fact |
| **Element declaration** | The registry record for one Leaf element type | An authored occurrence of the type |
| **Leaf element** | One authored occurrence of a Leaf element type | A native HTML element or its declaration |
| **Compound owner** | A Leaf element whose body owns declared direct members | An open-markup container |
| **Compound member** | A Leaf element whose declaration admits one or more direct owner types | Any nested widget |
| **Structural element** | A Leaf element with a declared role in reading structure | A member with no reading role |
| **Addressable element** | An authored, identified element eligible as a reader target | Generated chrome or a compound member as such |

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

| Term | Identity criterion | Not this |
|---|---|---|
| **Page shell** | The body-level responsive sizing envelope after chrome reservations | The authored content root |
| **Content frame** | `body > main`, the root of authored content | A reading column in every posture |
| **Reading column** | The flow presentation of the content frame | A bounded workspace canvas |
| **Workspace** | An authored structural composition that keeps task regions together | Runtime auxiliary chrome |
| **Pane** | A leaf in a workspace composition that owns one reading region | Every reading region |
| **Partition** | A binary structural node arranging two panes or partitions | A pane or reading region |
| **Reading region** | A stable semantic place used by navigation and reading-position recovery | A physical overflow box |
| **Effective reading scroller** | The scroll container currently governing one reading region | Every scrollable ancestor |
| **Scrollport** | A physical overflow box | The semantic region it happens to scroll |
| **Reading arrangement** | The current relation between structural elements, regions, and their scrollers | Saved reader view state |
| **Reading posture** | The content frame's responsive presentation: `flow` or `bounded` | An interaction mode |

A root workspace may produce bounded posture. An embedded workspace remains in flow.
A compound widget may own reading regions without being a pane.

## Chrome and auxiliary surfaces

| Term | Identity criterion | Not this |
|---|---|---|
| **Chrome** | Runtime-owned interface outside authored content | Authored widgets |
| **Chrome root** | The one `.lf-chrome` container | The page shell |
| **Banner** | The persistent chrome row carrying page status and global controls | The shortcut bar or an auxiliary surface |
| **Banner control** | One control seated in the banner's global control order, whether on the row or folded into its overflow disclosure | A Go-to address or a status sentence |
| **Auxiliary surface** | Chrome opened alongside or over the content frame | An authored workspace |
| **Thread panel** | The right-side auxiliary surface containing threads | An ARIA tab panel |
| **Tray slot** | The left-side chrome position that admits one tray | A tray itself |
| **Tray** | A mutually exclusive auxiliary surface admitted by the tray slot | A generic panel |
| **Auxiliary placement** | Whether an auxiliary surface stands `beside` or `covering` the content frame | Reading posture |
| **Auxiliary chrome state** | Which auxiliary surfaces are open and where focus belongs among them | All saved reader view state |

The current trays are the **Asks tray** and **Leaves tray**. Use *covering auxiliary
surface*, not *modal workspace*: a covering surface and a modal dialog are different
web interaction primitives.

## Page Map and the margin

**Page Map** is the feature, not one of its projections. It has three presentations:

| Term | Identity criterion | Not this |
|---|---|---|
| **Page inventory** | The complete logical collection of Page Map destinations and actions | One visual projection of it |
| **Margin projection** | The compact page-side projection of the inventory | The complete inventory or only its rail placement |
| **Page Map dialog** | The searchable modal projection of the inventory | The Page Map feature as a whole |

The margin has a separate spatial hierarchy:

| Term | Identity criterion | Not this |
|---|---|---|
| **Page margin** | Lateral space outside the content frame | Width already reserved from the shell |
| **Margin strip** | Lateral width reserved from the shell | The rail inside it |
| **Rail** | The right-hand lane used when the margin projection stands beside content | A command chooser or dialog list |
| **Margin row** | One target-anchored geometry participant | Its visible grouped contents |
| **Margin cluster** | The visible group attached to one target | The geometry row as such |
| **Margin contribution** | One provider's registered bundle of margin content | One actionable or informational entry |
| **Margin entry** | One action, disclosure, or status in a contribution | An arbitrary DOM element |
| **Margin placement** | The spatial result `rail`, `docked`, or `withheld` | A temporal lifecycle |
| **Margin rank** | The declared ordering class of an entry | Purpose, tone, or lifecycle |

*Withheld* means no spatial allocation is currently available; it does not imply that
time alone will make the entry appear.

## Contents outline

**Contents outline** is generated page navigation derived from authored headings. Its
presentations are:

| Term | Identity criterion | Not this |
|---|---|---|
| **Contents spine** | The roomy margin presentation that distributes heading destinations over the document's height | The Page Map's margin projection |
| **Open contents outline** | The ordinary in-flow or scrollable presentation that exposes every included heading label | A sidebar as such |

`lf-toc` is the authored element that requests the contents outline. A sidebar is one
possible authored position for it, not the feature's name.

## Keyboard grammar

| Term | Identity criterion | Not this |
|---|---|---|
| **Keyboard context** | The complete runtime situation used to resolve commands: focus path, active surface, and any active mode, sequence, chooser, or native layer | Focus alone |
| **Scope** | A registered command-applicability and shadowing boundary | A mode or visual surface |
| **Binding** | One canonical normalized keyboard chord matched against a keyboard event | Its displayed spelling |
| **Command** | One stable semantic operation identified by a dotted id | A presentation group containing several operations |
| **Mode** | A bounded context that reinterprets inputs until the reader explicitly exits it | A prefix sequence or one-shot chooser |
| **Sequence** | A prefix grammar whose valid continuations narrow until completion or cancellation | A persistent mode |
| **Chooser** | A temporary interaction that presents candidates and ends when one is chosen or the interaction closes | Native text selection |
| **Search context** | A temporary interaction that filters or walks matches for a query | A chooser without a query |
| **Hint** | A transient visible input code attached to one candidate in the current interaction snapshot | A stable address |
| **Address** | A complete ordered token path selecting one candidate in the current Go-to map | One painted hint token |
| **Go-to target** | An addressable candidate in the Go-to map | Necessarily a navigation destination |
| **Destination** | A place or semantic region where navigation lands | A control activated in place |
| **Action target** | The semantic subject upon which an operation acts | `event.target` or a geometry box |

The named interaction contexts are:

- **Design mode**, entered with `l`.
- **Draw mode**, entered with `w`.
- **Go-to sequence**, opened with `g`.
- **Target chooser**, opened with `s`.
- **Page search**, opened with `/`.

`g` is not Go mode. `s` is not Select mode. A mode, sequence, chooser, and search may
each make a scope applicable, but the scope is the command mechanism rather than the
interaction kind.

The keyboard help presentations are:

- **Shortcut bar**: the always-visible compact projection of commands applicable in
  the current keyboard context.
- **Shortcut shelf**: the expanded phase of the shortcut bar, not another surface.
- **Command reference**: the searchable complete catalog of commands. It includes
  pointer- and platform-triggered commands with no keyboard binding, so it is not
  “all keyboard shortcuts.”

## Navigation verbs

| Verb | Use it for | Do not use it for |
|---|---|---|
| **Scroll** | Relative pixel movement of the effective reading scroller | Semantic destination changes |
| **Page step** | Relative viewport-sized scrolling | Walking among targets |
| **Walk** | Ordered semantic movement among same-kind destinations | Arbitrary scrolling |
| **Go to** | Resolve an address, then activate its Go-to target | Every change of focus |
| **Activate** | Invoke the current target's primary operation | Choose a different candidate |
| **Return** | Reverse an entered transition to a stored or structurally known origin | Any Escape action |
| **Retreat** | Remove one prefix, filter, or search substate while staying in an interaction | Close the whole interaction |
| **Exit** | Leave a mode | Close a panel or dialog |
| **Dismiss** | Close a surface without claiming origin restoration | Exit a mode |
| **Unwind** | Perform the innermost available Escape step when its concrete kind depends on context | A specific retreat, exit, dismiss, or return operation |

## Reader-local state

State names have two independent dimensions.

**Meaning**:

- **Navigation state** locates the reader in content, such as reading position and a
  return origin.
- **Display state** controls presentation, such as the selected tab, collapsed group,
  filter, wrap, or screenshot face.
- **Interaction context** is an active mode, sequence, chooser, or search.
- **Reader preference** is an intentionally shared presentation choice.

**Retention**:

- **Ephemeral** lasts only for the current interaction.
- **Tab-scoped** survives within one browser tab.
- **Page-scoped** belongs to one page.
- **Reader-scoped** is intentionally shared across pages for one reader.

Use **reader view state** only for a record that intentionally combines more than one
reader-local meaning for restoration. Do not call it a reading arrangement or
auxiliary chrome state.

## Authored presentation elements

| Term | Identity criterion | Not this |
|---|---|---|
| **Chronology** | Authored subject-matter entries in time order | Leaf's append-only event log |
| **Chronology entry** | One observation, intervention, warning, or failure in a chronology | A Leaf event |
| **Text document** | A file-backed textual data presentation | Its data source identity |
| **Tab set** | A control choosing one of several mutually exclusive views in a region | A set restricted to workstreams |
| **Tab panel** | The view shown for one tab | The thread panel |

The `source` attribute and source ids remain data-binding vocabulary. Native DOM events
and ordinary HTML list items remain correctly named when that is what they are.
