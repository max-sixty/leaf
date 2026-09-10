# Keyboard command and binding ownership

Status: proposed

## Goal

Leaf needs one keyboard model that remains predictable as packages add widgets. A
package receiving focus must not change Leaf's application keys. A focused widget must
still be able to provide compact local operation, and a reader must be able to disable
character shortcuts without losing the commands they invoke.

The model separates three decisions:

- A command owner defines an action and implements it.
- A namespace owner assigns character bindings when commands compete for the same keys.
- The focused interaction owns standard editing, navigation, activation, and return
  behavior while it is active.

## Terms

**Command** is a stable capability in the keyboard register. Its owner supplies the
id, words, liveness, control, and implementation. A command can have no configured
keyboard binding and remain executable from a visible control or the complete command
reference.

**Binding** is a route from a key press to a command. Binding availability and command
availability are separate readings.

**Character shortcut** is a binding whose key produces non-space text and whose only
possible modifier is Shift. It includes letters, digits, punctuation, uppercase letter
routes, and character sequences such as `g t`. It excludes Space, named keys such as
Enter and ArrowRight, and chords such as Mod+Enter and Alt+w.

**Application namespace** contains Leaf's direct page and chrome character bindings.
Leaf assigns and protects these bindings. Core scopes may give one application key a
deliberate contextual meaning because Leaf owns every competing meaning; packages
cannot shadow it.

**Local namespace** contains a widget instance's direct bindings. The nearest semantic
owner on the focused DOM and shadow-DOM ancestry wins between nested local namespaces.
Package installation order does not participate.

**Mode namespace** exists only after an explicit interaction enters it. Go-to target
letters, item-selection hints, and a widget's own modal continuations belong to their
mode. A continuation may repeat a direct character because its prefix or active mode
already selected a different namespace.

**Focused interaction key** is a binding supplied by a native control, an established
interaction pattern, or an active mode. Arrow keys in tabs, Enter on a button,
Mod+Enter in an editor, and Escape from an open mode are focused interaction keys.

## Ownership rules

### Commands belong to the layer that implements the result

Leaf owns page reading, chrome, shared commenting, search, navigation, and workspace
commands. A widget owns commands that interpret or change that widget's content. A
widget can expose a control or target to a Leaf command without acquiring the command:
for example, a visual widget supplies a comment target while Leaf owns Comment.

The command owner does not necessarily assign its keyboard binding.

### Every character binding has an explicit namespace owner

Leaf assigns direct application shortcuts, including `c`, `/`, `t`, `a`, and `g`. Their
ownership comes from declared core application rows, independently of current liveness,
focus, page policy, or reader preference. A package cannot claim one through a nearer
scope.

Leaf may define contextual application behavior in scopes it owns. For example, `c`
retains the application Comment intent while Leaf resolves its current target. A core
key whose meanings differ by context remains Leaf's product grammar because Leaf sees
and validates the whole set. Packages extend such behavior through a capability API,
when one exists, rather than binding the protected key themselves.

A widget assigns direct character shortcuts only in its local namespace. It may use a
character not protected by the application namespace. Nested widgets remain composable:
the nearest local namespace that declares a character owns it, just as a focused tab
list's arrows take precedence over an enclosing deck's arrows. A local declaration
retains that ownership while its command is unavailable, so one state change cannot
make the same press fall through to an ancestor's different local action. Liveness
controls execution and projection, not ownership.

A mode owner assigns its continuation namespace. Its declarations reserve nothing
outside the active mode, so `g g` can coexist with direct `g`, and a generated Go-to
alphabet does not consume the page or widget alphabet. A mode declares which application
routes survive while it stands, along with its exit and return behavior.

Registration records provenance and namespace explicitly. Core application
registration produces protected application rows. The public widget `commands()` entry
point produces a local owner. A widget creates a mode through an API tied to that widget
instance and the command that enters it. Leaf does not infer authority from tag names,
command-id prefixes, or package load order.

### Leaf assigns aggregate addresses

Some character routes are properties of a collection rather than one command:

- Leaf allocates Ask digits after reading every action in the active Ask. Packages never
  declare contextual digits. A Decision command may retain one intrinsic non-character
  binding, such as ArrowLeft or Mod+Enter. Leaf allocates a digit only where the Decision
  command has no intrinsic binding and capacity remains.
- Leaf allocates generated Go-to addresses after reading every visible destination. A
  widget contributes a destination control; it does not choose an address.

An action remains a command and a visible control when no digit or generated character
is available.

### Focused interaction keys follow the active interaction

Named keys, Space, and modified chords are outside the character namespaces. The
nearest focused control or active interaction may claim them when the key is part of
that interaction:

- Native controls retain their platform activation, selection, adjustment, and editing
  keys.
- Widgets implement the keys required by their interaction pattern, such as arrows and
  Home/End in tabs.
- An exact editor scope may add a local chord such as Mod+Enter.
- An active mode may use Tab, Enter, and Escape for traversal, activation, and return.

Leaf derives a focused native control's claim footprint from its element semantics and
role. Text fields claim text and editing keys; buttons retain Enter and Space; ranges,
radios, selects, and other native controls retain their adjustment keys. This footprint
sits ahead of ancestor widget scopes. An exact control may add behavior deliberately,
but an ancestor cannot take a native key first. If no interaction claims a key, the
browser owns it. Composition and AltGraph text production take precedence over command
chords.

The active interaction owns its Escape inverse, while Leaf orders nested inverses
through the return stack. A widget declares how to leave the mode it opened; it does not
decide which outer surface closes next.

### Configuration filters bindings, not commands

The reader setting is **Use character shortcuts**. The page may deny character
shortcuts with:

```html
<meta name="lf-character-shortcuts" content="off">
```

Omission allows them. The effective setting is on only when the page allows character
shortcuts and the reader preference is on. A page cannot force them on. Leaf reads the
validated page policy at initial presentation and revision activation.

The reader preference applies across Leaf pages on the same host. It is stored as a
one-year host-scoped cookie with no `Domain`, `Path=/`, and `SameSite=Strict`. A page
writes the cookie and its in-memory reading together. Pages re-read it when they regain
focus or visibility because cookie changes do not emit a cross-port event. If persistence
is unavailable, the setting lasts in memory for the current page. Other hosts and
partitioned embedded browsers keep independent preferences.

When character shortcuts are off:

- Character dispatch, configured keycaps, generated character hints, shortcut-bar
  entries, and `aria-keyshortcuts` disappear together.
- Commands, controls, Space, named-key routes, and modified chords remain available.
- The complete command reference retains executable commands and omits their disabled
  character route. A purely instructional character row with no executable command is
  omitted.
- A mode opened from a control or the command reference retains its focused Tab, Enter,
  and Escape behavior. Character continuations and character hints remain off.

The preference control remains editable when the page denies shortcuts. The reference
shows the stored reader preference and effective page state separately, so a checked
preference does not imply that the current page enables it.

## Case matrix

| Case | Command owner | Namespace or convention | Result |
| --- | --- | --- | --- |
| Comment on a visual part | Leaf; widget supplies the target | Application | `c` retains Leaf's Comment intent and resolves the current target. |
| Decision in `lf-options` | Widget | Leaf Ask allocator | The action receives the next free `1`-`9`; Tab and native activation remain. |
| Swipe Decision | Swipe widget | Focused interaction | ArrowLeft and ArrowRight remain intrinsic routes; Leaf does not add a digit. |
| Widget button in Go-to | Widget | Leaf mode allocator | Leaf assigns a visible, prefix-free address from the whole scene. |
| Page text search | Leaf | Application | `/` searches all text in the active page reading surface. |
| Thread-list search | Leaf | Application context | `/` searches the focused thread list under Leaf's declared contextual grammar. |
| Diff file-name filter | Diff widget | None while `/` is protected | The visible filter control and command remain; the widget cannot shadow page `/`. |
| Next diff hunk | Diff widget | Local | `]` is stable within the focused diff while it remains unprotected. |
| Nested widget also using `]` | Nested widget | Nearer local namespace | The nested widget owns `]` while focused; the enclosing diff does not run it. |
| Go-to continuation `g` | Leaf | Go-to mode | `g g` is valid because the second `g` is not in the application namespace. |
| Tabs | Tabs widget | Established tabs pattern | ArrowLeft, ArrowRight, Home, and End operate only in the focused tab list. |
| Range inside a swipe deck | Browser | Native control footprint | ArrowLeft adjusts the range and never reaches the enclosing deck. |
| Native button | Widget or Leaf | Browser | Enter and Space activate the button without a duplicate Leaf route. |
| Draft submission | Draft owner | Exact editor scope | Mod+Enter submits while Enter remains a newline. |
| Leave a widget mode | Widget owns the inverse; Leaf owns nesting | Focused mode and return stack | Escape leaves the innermost active interaction, then returns outward. |
| Go-to opened from the reference while character shortcuts are off | Leaf | Focused Go-to mode | Tab selects a destination, Enter activates it, and Escape leaves; letter hints stay absent. |

## Register contract

The register remains the single declaration source. It produces three readings:

- **Command definitions** retain stable identity, source instance, semantic scope,
  liveness, implementation, and invocation arguments independently of shortcuts.
- **Configured shortcut routes** apply page policy and reader preference to declared
  bindings. They do not depend on current focus or command liveness.
- **Resolved shortcut routes** apply scope ancestry, current liveness, mode ownership,
  native claims, and local shadowing for one explicit interaction context.

Key dispatch, the shortcut bar, a control's tooltip, and `aria-keyshortcuts` consume
resolved routes for their context. The complete reference combines command definitions
with configured routes because it also documents commands outside the reader's current
focus. It uses each scope's existing capability and reach rules rather than pretending
every listed command is immediately reachable.

Explicit command invocation never simulates or requires a key press. It resolves a
command by stable id and captured source instance, then revalidates semantic scope,
liveness, native-layer availability, and source connection before acting. Keyboard
interception claims, text-entry claims, and local key shadowing apply only to shortcut
dispatch. A routed command retains its declared invocation argument after its character
route is filtered out.

Binding parsing, canonicalization, classification, matching, and text-entry ownership
share one parsed representation. The parser preserves a literal `+`, normalizes Unicode
character keys to NFC, rejects unsupported declarations at registration, and
distinguishes AltGraph text production from Ctrl+Alt command chords.

## Validation

Declaration-time validation rejects:

- a package local binding protected by the application namespace;
- structurally unconditional duplicate meanings in the same dispatch scope;
- a package-declared contextual Ask digit or generated Go-to address;
- a route that loses its command identity or invocation argument when its binding is
  filtered;
- unsupported or non-canonical key syntax.

Conditional and context-specific alternatives may share a binding. Scene resolution
applies namespace and semantic-scope precedence, then checks computed liveness, current
mode, native ownership, and composed ancestry. It rejects multiple live meanings at the
same resulting precedence instead of choosing by declaration order. Different nested
local owners resolve by semantic ancestry. A nearer owner's unavailable declaration
suppresses a different ancestor-local meaning for that key. Browser tests exercise
transitions because arbitrary liveness predicates cannot be proved mutually exclusive
statically.

## Likely implementation failures

- Filtering `bindings(row)` directly can remove the command from reference invocation,
  Decision discovery, or routed-command identity along with its shortcut.
- Applying the dispatcher's current focus claims to the complete reference can hide
  commands that are valid in another documented scope.
- Reading route declarations directly can leave Ask chips, generated hints, tooltips, or
  `aria-keyshortcuts` visible after dispatch has disabled them.
- Treating every core character as one flat reserved set can consume the complete
  alphabet and reject valid mode continuations.
- Letting a dead local row fall through can change an ancestor key's meaning as widget
  state changes.
- An incomplete native claim footprint can make an enclosing widget intercept a range,
  radio, select, or editor key.
- Splitting bindings on every `+`, counting JavaScript string length, or ignoring
  AltGraph can misclassify literal punctuation and composed text.
- Page-local storage can make the preference reset when a newly handed local page uses a
  different port. Cookies need explicit focus and visibility synchronization.
- Adding a future protected application character can invalidate a package that already
  uses it. Composition must report the incompatible layer change; Leaf cannot silently
  take the key.

## Cutover

The change replaces the current coupled binding/command reading rather than adding a
second command system.

1. Complete the shared binding parser and character classifier.
2. Add explicit application, local, and mode namespace provenance at the core and
   package registration boundaries.
3. Derive command definitions, configured routes, and context-resolved routes from the
   existing register.
4. Complete native control claim footprints and local ownership resolution.
5. Move Ask digits and generated destinations through the shared allocator readings.
6. Apply configured and resolved character filtering to dispatch and every projection.
7. Add the reader preference, page policy, and standing chrome door to the existing
   keyboard reference.
8. Remove conflicting package bindings, including diff `/`, without compatibility
   aliases.

Tests cover a character shortcut and its surviving command, both branches of a routed
command, intrinsic and allocated Decision routes, digit-capacity exhaustion, generated
Go-to hints, widget-local punctuation, a rejected application/widget conflict, nested
local precedence, dead-child suppression, native controls inside keyboard-active
widgets, text entry, AltGraph and composed Unicode input, every page-policy/reader-setting
combination, and preference continuity across local page ports.

## Alternatives

### Let the nearest scope override application keys

This needs the least new registry structure and preserves unrestricted local freedom.
The shared resolver can keep dispatch and projections aligned, but a learned page key
can still change meaning when a package receives focus. Package behavior becomes part of
Leaf's application grammar without Leaf assigning it.

### Reserve every character for Leaf

This gives the application grammar complete stability and leaves widgets with native
controls, named keys, and modified chords. It also removes useful focused operations
such as diff hunk navigation even though they do not compete with an application key.

### Reject every character collision across nested widgets

This prevents local shadowing but makes independently valid widgets incompatible when
an author composes them. Semantic focus ancestry already supplies a deterministic local
owner, so the restriction adds composition failures without protecting application
keys further.

### Let widgets request meanings and have Leaf assign every character

A global allocator eliminates collisions. The same widget action can receive different
keys as page composition changes, so documentation, learned operation, and package tests
cannot rely on a stable local binding. Semantic command ids do not make arbitrary
generated letters memorable.

### Give each package a fixed character prefix

Prefixes partition the namespace, but they add a step to every local command and reserve
letters for packages that may not be present. Nested active modes still need focus and
return rules.

### Route protected keys through contextual capability providers

Leaf could own a semantic command such as Find and let the focused widget provide its
implementation. This is preferable to arbitrary shadowing when every provider keeps the
same user intent. It is not suitable for diff file-name filtering yet: page `/` searches
all rendered text, while the diff filter changes the visible file set by name. A shared
Find capability would first need one contract for search domain, result traversal, empty
results, and return behavior.

Protected application bindings, explicit mode namespaces, and nearest-owner local
precedence preserve Leaf's learned grammar without making independently composed widgets
share one global alphabet. Leaf allocates only the collections that no single widget can
know.
