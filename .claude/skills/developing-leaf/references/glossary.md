# Leaf glossary

This is the canonical vocabulary for the page a reader sees and operates. Use these
names in element declarations, JavaScript, CSS, visible copy, tests, examples, and
references. When an existing name disagrees with this glossary, change the name; do
not add an alias.

This reference does not define the protocol between the page and its agent. Events,
comments, conversations, replies, Asks, requests, receipts, activity, and their
lifecycles are owned by their protocol references.

## How to use the vocabulary

A term earns its own entry when current Leaf behavior supplies a stable identity
criterion. Add a short example only when the definition would otherwise remain
abstract.

Name the narrowest established kind. Qualify a noun when another web or Leaf concept
uses the same word. Treat retention and meaning as separate dimensions: a mode can be
tab-scoped without becoming display state, for example.

## Packages, declarations, and elements

| Term | Identity criterion |
|---|---|
| **Package** | One composable source directory containing declarations and their payload |
| **Leaf layer** | One checked, vendored composition of packages |
| **Leaf element type** | One registered `lf-*` tag identity |
| **Element declaration** | The registry record for one Leaf element type |
| **Leaf element** | One authored occurrence of a Leaf element type |
| **Compound owner** | A Leaf element whose body owns declared direct members |
| **Compound member** | A Leaf element whose declaration admits one or more direct owner types |
| **Structural element** | A Leaf element with a declared role in reading structure |
| **Addressable element** | An authored, identified element eligible as a reader target |

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
| **Content frame** | `body > main`, the root of authored content |
| **Reading column** | The flow presentation of the content frame |
| **Workspace** | An authored structural composition that keeps task regions together |
| **Pane** | A leaf in a workspace composition that owns one reading region |
| **Partition** | A binary structural node arranging two panes or partitions |
| **Reading region** | A stable semantic place used by navigation and reading-position recovery |
| **Effective reading scroller** | The scroll container currently governing one reading region |
| **Scrollport** | A physical overflow box |
| **Reading arrangement** | The current relation between structural elements, regions, and their scrollers |
| **Reading posture** | The content frame's responsive presentation: `flow` or `bounded` |

A root workspace may produce bounded posture. An embedded workspace remains in flow.
A compound widget may own reading regions without being a pane.

## Chrome and auxiliary surfaces

| Term | Identity criterion |
|---|---|
| **Chrome** | Runtime-owned interface outside authored content |
| **Chrome root** | The one `.lf-chrome` container |
| **Banner** | The persistent chrome row carrying page status and global controls |
| **Banner control** | One control seated in the banner's global control order, whether on the row or folded into its overflow disclosure |
| **Auxiliary surface** | Chrome opened alongside or over the content frame |
| **Thread panel** | The right-side auxiliary surface containing threads |
| **Tray slot** | The left-side chrome position that admits one tray |
| **Tray** | A mutually exclusive auxiliary surface admitted by the tray slot |
| **Auxiliary placement** | Whether an auxiliary surface stands `beside` or `covering` the content frame |
| **Auxiliary chrome state** | Which auxiliary surfaces are open and where focus belongs among them |

The current trays are the **Asks tray** and **Leaves tray**. Use *covering auxiliary
surface*, not *modal workspace*: a covering surface and a modal dialog are different
web interaction primitives.

## Page Map and the margin

**Page Map** is the feature, not one of its projections. It has three presentations:

| Term | Identity criterion |
|---|---|
| **Page inventory** | The complete logical collection of Page Map destinations and actions |
| **Margin projection** | The compact page-side projection of the inventory |
| **Page Map dialog** | The searchable modal projection of the inventory |

The margin has a separate spatial hierarchy:

| Term | Identity criterion |
|---|---|
| **Page margin** | Lateral space outside the content frame |
| **Margin strip** | Lateral width reserved from the shell |
| **Rail** | The right-hand lane used when the margin projection stands beside content |
| **Margin row** | One target-anchored geometry participant |
| **Margin cluster** | The visible group attached to one target |
| **Margin contribution** | One provider's registered bundle of margin content |
| **Margin entry** | One action, disclosure, or status in a contribution |
| **Margin placement** | The spatial result `rail`, `docked`, or `withheld` |
| **Margin rank** | The declared ordering class of an entry |

*Withheld* means no spatial allocation is currently available; it does not imply that
time alone will make the entry appear.

## Contents outline

**Contents outline** is generated page navigation derived from authored headings. Its
presentations are:

| Term | Identity criterion |
|---|---|
| **Contents spine** | The roomy margin presentation that distributes heading destinations over the document's height |
| **Open contents outline** | The ordinary in-flow or scrollable presentation that exposes every included heading label |

`lf-toc` is the authored element that requests the contents outline. A sidebar is one
possible authored position for it, not the feature's name.

## Keyboard grammar

| Term | Identity criterion |
|---|---|
| **Keyboard context** | The complete runtime situation used to resolve commands: focus path, active surface, and any active mode, sequence, chooser, or native layer |
| **Scope** | A registered command-applicability and shadowing boundary |
| **Binding** | One canonical normalized keyboard chord matched against a keyboard event |
| **Command** | One stable semantic operation identified by a dotted id |
| **Mode** | A bounded context that reinterprets inputs until the reader explicitly exits it |
| **Sequence** | A prefix grammar whose valid continuations narrow until completion or cancellation |
| **Chooser** | A temporary interaction that presents candidates and ends when one is chosen or the interaction closes |
| **Search context** | A temporary interaction that filters or walks matches for a query |
| **Hint** | A transient visible input code attached to one candidate in the current interaction snapshot |
| **Address** | A complete ordered token path selecting one candidate in the current Go-to map |
| **Go-to target** | An addressable candidate in the Go-to map |
| **Destination** | A place or semantic region where navigation lands |
| **Action target** | The semantic subject upon which an operation acts |

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

| Verb | Use it for |
|---|---|
| **Scroll** | Relative pixel movement of the effective reading scroller |
| **Page step** | Relative viewport-sized scrolling |
| **Walk** | Ordered semantic movement among same-kind destinations |
| **Go to** | Resolve an address, then activate its Go-to target |
| **Activate** | Invoke the current target's primary operation |
| **Return** | Reverse an entered transition to a stored or structurally known origin |
| **Retreat** | Remove one prefix, filter, or search substate while staying in an interaction |
| **Exit** | Leave a mode |
| **Dismiss** | Close a surface without claiming origin restoration |
| **Unwind** | Perform the innermost available Escape step when its concrete kind depends on context |

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

| Term | Identity criterion |
|---|---|
| **Chronology** | Authored subject-matter entries in time order |
| **Chronology entry** | One observation, intervention, warning, or failure in a chronology |
| **Text document** | A file-backed textual data presentation |
| **Tab set** | A control choosing one of several mutually exclusive views in a region |
| **Tab panel** | The view shown for one tab |

The `source` attribute and source ids remain data-binding vocabulary. Native DOM events
and ordinary HTML list items remain correctly named when that is what they are.
