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
uses the same word.

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
| **Content frame** | `body > main`, the root of authored content and its reading column in flow posture |
| **Workspace** | An authored structural composition that keeps task regions together |
| **Pane** | A leaf in a workspace composition that owns one reading region |
| **Partition** | A binary structural node arranging two panes or partitions |
| **Reading region** | A stable semantic place used by navigation and reading-position recovery |
| **Effective reading scroller** | The scroll container currently governing one reading region |
| **Reading posture** | The content frame's responsive presentation: `flow` or `bounded` |

A root workspace may produce bounded posture. An embedded workspace remains in flow.
A compound widget may own reading regions without being a pane.

## Chrome and auxiliary surfaces

| Term | Identity criterion |
|---|---|
| **Chrome** | Runtime-owned interface outside authored content, rooted at the one `.lf-chrome` container |
| **Banner** | The persistent chrome row carrying page status and global controls, including controls folded into its overflow disclosure |
| **Auxiliary surface** | Chrome opened `beside` or `covering` the content frame |
| **Thread panel** | The right-side auxiliary surface containing threads |
| **Tray** | A mutually exclusive auxiliary surface admitted by the one left-side tray position |

The current trays are the **Asks tray** and **Leaves tray**. Use *covering auxiliary
surface*, not *modal workspace*: a covering surface and a modal dialog are different
web interaction primitives.

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
| **Rail** | The right-hand lane and shell reservation used when the margin projection stands beside content |
| **Margin row** | One target-anchored geometry participant whose placement is `rail`, `docked`, or `withheld` |
| **Margin cluster** | The visible group attached to one target |
| **Margin contribution** | One provider's registered bundle of margin content |
| **Margin entry** | One ranked action, disclosure, or status in a contribution |

*Withheld* means no spatial allocation is currently available; it does not imply that
time alone will make the entry appear.

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
| **Design mode** | The `l` interaction that reinterprets input for interface comments until the reader exits |
| **Draw mode** | The `w` interaction that reinterprets pointer input as a drawing until the reader exits |
| **Go-to sequence** | The `g` prefix grammar that builds a current map of Go-to targets, paints transient hint codes, and resolves complete ordered addresses |
| **Target chooser** | The `s` interaction that presents addressable elements and ends when the reader chooses one or closes it |
| **Page search** | The `/` interaction that filters or walks text matches for a query |
| **Walk** | Ordered semantic movement among same-kind destinations |
| **Return** | Restoration of the origin captured before an entered transition; Escape unwinds an inner interaction before returning when necessary |
| **Key badge** | A keycap-shaped carrier for a binding or transient hint code |
| **Binding badge** | A key badge showing a command's currently resolved binding |

Reserve *mode* for Design mode and Draw mode, which persist until explicit exit. `g`
opens a sequence and `s` opens a chooser. A scope is the command-resolution mechanism
that these interactions may make applicable. Commands have stable dotted ids; bindings
are canonical normalized chords matched against keyboard events.

The keyboard help presentations are:

- **Shortcut bar**: the always-visible compact projection of commands applicable in
  the current keyboard context.
- **Shortcut shelf**: the expanded phase of the shortcut bar, not another surface.
- **Command reference**: the searchable complete catalog of commands. It includes
  pointer- and platform-triggered commands with no keyboard binding.
