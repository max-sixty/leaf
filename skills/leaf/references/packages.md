# Packages

A package is the directory Leaf authors, shares, and adds to a page. It may hold a
theme, one widget, a family of widgets, helper modules, libraries, external-data
contracts, or any combination of them. The layer is different: it is the checked
result that `page init` vendors after composing the kernel and packages.

## Package reach

Leaf's bundled `default` package reaches every page. Any other package reaches only the
pages that select it by name or path. Presentation or behavior used by only one page
stays in that version, in its `<style>` and its inline modules or `page/`. Everything
reusable belongs to a package. Leaf creates, checks, installs, and runs the whole
directory:

```bash
leaf package init PACKAGE
leaf package init PACKAGE --widget lf-callout
leaf package check PACKAGE
leaf package install PACKAGE
leaf package run NAME SCRIPT [ARGS]...
```

`package init` creates `registry.json`, `theme.css`, `guidance/`, `runtime/`,
`widgets/`, and `vendor/` without replacing existing contents. Add `--widget TAG` to
create one upgraded prose widget at the same time. Leaf adds a valid registry example
and the matching `widgets/TAG.js` module, which registers the element and upgrades it
`once`; it then checks the resulting composition, and leaves a new package's empty
theme ready for the widget's presentation.
An existing theme and other package files remain in place. Leaf refuses a tag or module
that already exists rather than replacing it. The package author edits that directory,
then checks its composition before adding the package to a page:

```bash
leaf package init packages/callout --widget lf-callout
leaf package check packages/callout
leaf page init --package packages/callout PAGE
```

Every package beyond the bundled default is selected explicitly, and the
always-present `default` package cannot be. A bare name selects an installed or
bundled package and never means a path. A path is project-relative or starts with
`~`: `--package ./.leaf`, `--package '~/.config/leaf'`, or `.` inside a repository
dedicated to one package. Absolute paths are refused because the vendored registry
is public.

`leaf package install SOURCE` checks that directory and copies it into
`~/.local/state/leaf/packages/`, where `--package NAME` reaches it by its directory
name from any project on this machine:

```bash
leaf package install packages/callout
leaf page init --package callout PAGE
```

The copy holds the package contract below, `scripts/` included, and nothing else in
the source directory, so a README and the author's own tests stay behind. A name that
a bundled or already installed package answers to is refused rather than replaced;
remove the installed directory to replace one. A page records the bare name, so
re-vendoring it on another machine needs the same package installed there.

Leaf also ships optional packages that select by bare name. `code-review` trials
guidance-led review authoring without adding widgets; select it or your own review
guidance package alongside the evidence packages the page needs. `diagram` adds `lf-diagram`
and the Agentic Mermaid renderer it draws with; `diff` adds `lf-diff`, the
`unified-diff` data contract, and the Pierre renderer; `swipe` adds a pass-or-keep
technical backlog deck; `playground` coordinates declarative controls and page-owned
structured contributors through one reset, restore, preview, output, and typed
configuration action; `targeting` lets users select preview elements and submit
structured, reversible change proposals; `command-hub` adds multi-agent
orchestration widgets; `pr-review` adds a typed pull-request brief with a safe Markdown
description and compact checks table, plus a data-backed unified call diff; `monitoring`
adds guidance for a release workspace with current state, checks, a run log, and a
rollback Ask; `visual-review` adds an ordered website run, aligned before-and-after evidence,
automatic compare orientation, authored focus with full-frame context, local flip and
overlay, fit and captured-size inspection, exact preview links, and case dispositions. `gallery`
adds the static gallery of page-edge action controls, disclosure controls, and status
indicators used only by the developer feature gallery, so ordinary pages do not select it.

The diagram and diff renderers are large and most pages draw neither, so they travel in
their own packages rather than in `default`. Packages declare no dependencies on each
other; a page states the whole list it needs.

## Package contract

Every package has the same partial layout:

```text
package/
├── registry.json       element declarations and shared $ declarations
├── theme.css           rules in the layer's shared cascade layer
├── shadow.css          rules that also reach declared shadow trees
├── guidance/           Markdown guides named for their audiences
├── runtime/            browser modules and replacements by vendored path
├── widgets/            entry modules and their private helpers
├── vendor/             third-party libraries or data files
├── scripts/            command-line tools `leaf package run` runs; never vendored
├── icon.svg            optional replacement by path
└── leaf.js             optional runtime replacement
```

No individual file is required. The kernel supplies the files every complete layer
needs. Theme files concatenate into one cascade layer, `lf-base`, so a package's rule
beats the kernel's by specificity and order as it would unlayered, while the Layouts
and the page's own stylesheet rank above every package rule whatever its specificity.
A package that declares widgets styles only those widgets: composition narrows each
rule in its `theme.css` and `shadow.css` to elements that are one of its widgets or
stand inside one, and in the shadow sheet every declared tree receives, to trees one of
its widgets hosts. A rule for `p` dresses the paragraphs in its widgets and no other,
and a rule for the box that holds a widget matches nothing. Composition refuses a rule
whose subject is `:root`, `html` or `body`, which no widget contains; state a widget's
tokens on its own element. What several packages' widgets share, such as the pane role
or a chip row, is the kernel's, and a package without widgets is a theme that reaches
the whole page as the kernel's does. A widget module's adopted sheet joins the same
layer. Shadow files concatenate too: a
declared `x-shadow` root built with `shadowStage` receives every package's `shadow.css`
in layer order, and the document reads each package's `shadow.css` just ahead of its
`theme.css`. Runtime, icon, widget,
and vendor files replace by path. A later package replaces a tag's complete element
declaration and one member inside a shared `$` declaration. A tag can be added or
replaced whole, but it has no deletion marker.
Shared `$` entries compose by member, and map-valued members compose one level further
by key; `null` deletes at either of those shared-entry grains when the merged registry
still validates. Guidance files with the same audience name concatenate in package order.
The merged vocabulary is validated before vendoring.

Each file directly under `guidance/` is named `<audience>.md`; the filename must match
`[a-z][a-z0-9-]*\.md`. Those files are for guidance that applies across the package.
The composed guide sets each package's passage under a heading naming the package, so a
file begins with its first rule rather than a title of its own.
A widget attaches its own guidance through `x-guidance`, while a data contract may
carry producer guidance beside its schema. Packages define audiences such as `author`,
`reviewer`, or `worker`; Leaf does not keep a role list. `leaf page guidance PAGE` lists
the audiences in the vendored page as a JSON array, and `leaf page guidance PAGE AUDIENCE` composes all
three sources. The page author reads the `author` audience when the list includes it;
that guide ends by naming the page's other audiences, so a package does not point at
its own.

Composition order is kernel, bundled default package, selected packages in command
order. Later packages win collisions. `page init`
records package selections under `$layer.packages`; a plain re-init resolves them again
in the same order. `page init --no-packages PAGE` clears the explicit list.

A package may contain zero, one, or many widgets. Those cardinalities do not change
its contract.

A replacement `runtime/layer-client.js` must retain the quoted
`"__LEAF_LAYER_GENERATION__"` placeholder exactly once. `page init` replaces it
with the same fresh epoch it writes into the merged registry; without that pair,
a runtime loaded before a re-vendor could speak the replacement registry as though
the two files were one contract.

A replacement `icon.svg` must be valid SVG and contain an element with
`class="lf-tone"`. The runtime paints the page's status on that element; without it,
the tab mark cannot say whether the page is working, waiting, or offline.

## A theme change

Tokens change every surface that reads them: `--accent`, `--r`, the three faces
`--serif` (body prose), `--sans` (apparatus: chrome, injected controls, and annotations
embedded in evidence), and `--mono` (literal evidence). Ordinary selectors tune one
element or widget. A shape the project reuses across pages is an idiom — declare it
under `$idioms` in the package's
`registry.json` (a selector, a description, an example) and style it in the layer's
`theme.css`; the page's merged `registry.json` then carries it beside the shipped ones.

A rule that draws a box's inset — padding, border, or tinted field — declares
`--lf-block-frame: 1` in the same rule. The shared layout uses that declaration to trim child
margins and bound wide content. The trim follows the frame's edge down through each
first or last child, so a wrapper between the frame and the margin it trims declares
nothing. A box that lays its children
out side by side (a flex row, a grid) declares `--lf-holds-edge: 1`, so the trim stops at
it rather than taking one item's margin and leaving the others'.

Delivery paints declared layout facts into the served document as `[data-lf-inline]`,
`[data-lf-space]`, `[data-lf-bound]`, and `[data-lf-exhibit]`; shared selectors read those attributes
instead of naming widget tags. The registry's `$keys` entries for `x-space` and
`x-bound` say what each declaration requests; none of them
chooses the widget's internal layout, which the package arranges inside the allocation.
How wide the page is, and how its blocks are arranged, is the page's choice, made with a
Layout class or its own CSS (`page-authoring.md`, "Layouts"); a package's element fills
the box it is given, and its `x-space` states the width it prefers, which a page may
override.
A widget that needs a minimum width to stay usable, such as a board's columns at a
readable size, states it as `min-inline-size` capped by the box it stands in:
`min(<its floor>, 100cqi, var(--lf-box-cap, 100vw))`. `100cqi` measures the nearest size
container, which is the page's shell or a framed box around the widget (a pane's body, a
card), and a sample, which cannot be one, states `--lf-box-cap`. So in a box
narrower than the floor the widget scrolls inside itself rather than widening the page.
When a bounded widget's scroller should be a box inside it, such as a listing under a
caption that stays in view, the package theme moves the bound there under
`[data-lf-bound]` and declares `--lf-bound-box: 1` on that box, which is the one Leaf
registers as the block's reading region and keeps on its newest entry. A box a
package scrolls sideways needs no declaration of its own: the runtime
measures every scroller on each layout and marks each edge with content beyond it.
Leaf fades the content at those edges, so a widget that has to scroll says so without
the package writing anything. An interactive
affordance stands down inside `[data-lf-exhibit]`, where the widget is quoted rather
than offered. The stylesheet is
inlined into an export, which opens offline, so use fonts available on the user's
machine rather than a remote font.

`body[data-lf-presented]` means the initial authoritative projection, or the deliberate
offline fallback, is safe for recorded interaction. Authored content is already visible:
Leaf disables its arrival transitions and durable widget actions before that stamp.
Printed keys pressed earlier are held and reach the page's key handlers only after the
stamp lands, in order, so a package's keys need no arrival guard either.
Package styles need no arrival guard. A package opens a dialog or popover only after that
stamp or in response to a user gesture; Leaf does not defer top-layer UI during startup.
A widget that keeps part of its own upgrade off the presentation path — a heavy renderer
it earns the right to load only once the user has the page — runs that work through
`afterPresentation(() => …)`, which is both the wait and the declaration. The page then
answers for it: until every such arrival lands, the page reads as still arriving, so a
user outside it waits on the page rather than on a widget it would have to know about.
A declared `x-shadow` widget gets the same transition protection when it builds its root
with `shadowStage`.

## A widget

The element declaration is JSON Schema over the element's attributes, plus the `x-` keys that
say how the layer treats the tag — its content model, whether a module upgrades it, which
attributes the user sees as words, its action verbs and their record forms, whether it
stands as one of the page's Asks. The merged registry's `$keys` entry defines each key,
and `$state` defines each `x-state` verb member, including `creates` for user-added
children, while `$awaits` defines when a widget's Ask is answered. Every element
declaration carries a
non-empty `description`. Its first plain sentence identifies the widget's purpose; the
rest explains its detailed contract. An entry's `x-example` must validate and is the
markup an author queries with that entry.

A `boolean` attribute is present or absent, as in HTML, so it names what its presence
means, and the widget's default is its absence: `lf-diff collapsed`,
`lf-options multiple`, `lf-shot outlines`. A feature a page usually wants is still
off until the author asks for it, and the guidance that routes to the widget says
when to ask.

The shipped element declarations are the worked examples. For the keys that reshape a
widget's role on the page:

| Key                  | Shipped example                                                |
| -------------------- | -------------------------------------------------------------- |
| `x-reading-role`     | `lf-pane`                                                      |
| `x-required-members` | `lf-swipe-deck` in `swipe`                                     |
| `x-visual`           | `lf-chart` declares `whole`, `lf-diagram` in `diagram` `parts`  |
| `x-bound`            | `lf-activity`                                                  |
| `x-history`          | `lf-activity`                                                  |
| `x-patch`            | `lf-tabs`                                                      |
| `x-thread-surface`   | `lf-diff` in `diff`, `lf-visual-review` in `visual-review`     |

A visual with generated part ids declares accepted `x-visual.prefixes` and calls
`registerVisualParts(source, read, {reveal, label})`. The `read` function returns
the parts currently drawn as `{id, element, label}` records. `reveal(id)` draws an
absent part when someone follows its thread; `label(id)` names that part in
Threads without changing the visual's state, and returns `null` for an unknown id.

A CSS-only widget is an entry and a theme rule. One with reusable behavior takes a
module. The widget owns its implementation: supporting modules can sit beside its entry
module and use relative imports, while third-party or data files can live under
`vendor/`. `page init` carries both directories into the page with the registry and
theme.

`/runtime/widget-api.js` is the whole Leaf API a behavior module gets: a module imports
only that public helper surface, and does not reach into the runtime's private owners,
query private chrome, or duplicate a runtime helper inside itself. Resolve canonical
`/media/…` paths from typed data with `scopedMediaUrl(path)` before assigning them to
generated images or links. It uses the page's public root across ordinary, MCP, and
published pages while the source retains its canonical path.

Registry-declared inline Markdown formats authored text, not strings a module assigns
with `textContent`. For changing Markdown prose, load the renderer with `loadMarkdown()`
and paint the current value with `inlineMarkdownFragment()`; repaint that value when
loading completes. A changing numeric readout keeps surrounding text still with
tabular numerals and a slot wide enough for its largest value.

### What a behavior module owes

A total, idempotent `renderState(state)`; `widgetController(owner).dispatch()` for recorded user state, with a
detail matching the declared browser schema; `says()` over `textContent`; `offer()` and
`relabel()` on anything injected, with its room reserved from inside `measure` and
`layoutChanged` called after a view swap (await its returned promise before restoring
scroll against the resulting layout); asynchronous visible preparation is registered
through `controller.present(promise)`; box-derived apparatus takes its first visible
reading synchronously from `PRESENTATION` and observes later changes through the normal
layout signals (each helper's header under `runtime/` says why), scheduling a paint with
`nextRender`/`cancelRender` and watching a size with `sizeObserver` rather than the
browser's own, so that a reader waiting for the page to settle after a gesture — a
check, a test — waits for that work too (`nextRender` asked for from another rendering
callback runs in that callback's frame, and otherwise in the next frame; a step that
must not run in the frame that asked for it, such as an animation tick, asks for
`nextFrame`; a playback loop that runs until
the user stops it stays on `requestAnimationFrame`, or the page never settles while it
plays);
`keeps(node, name,
value)` for any name or state a reactive render writes, handed the boolean or count raw,
since an unconditional `setAttribute` restates itself on every publication and
`toggleAttribute` already keeps the rule for flags; `once()` in a `connectedCallback` that is safe to run after reconnection, and
hoisted chrome removed and any `indicate` cleared with `null` in `disconnectedCallback`
when the owner disconnects;
`commands()` at upgrade — through `DISCLOSE(el)` over anything that folds, the runtime
owning those commands — `quoted()` before wiring input, controller command availability
before an optimistic gesture.

`renderState` receives the state of every declared verb, keyed by verb name, including
the initial values an undo returns to. A widget-unit verb's state is `{action, value,
detail}`: `action` is null for authored state; `value` is the typed record value, or
the verb's name for a recordless verb that stands (null means undecided); `detail`
retains generated-child labels and other declared event data. A per-part verb's state
contains `units`, keyed by unit id, and a position verb's also contains `value`, a map
from container id to the complete ordered ids it holds, and `ranks`, each listed unit's
rank. A position record carries a rank rather than an index, so a unit's placement
stands whichever other moves stand, until a version authors the container's units
differently and its markup places the unit: dispatch `rankAt(state.<verb>, container, index,
unit)` from `runtime/widget-api.js` for a unit dropped at `index` among the container's
other units. Missing recordless units are
undecided. Render the final composition and keep independent
nested widgets mounted; never recreate the owner to restore an initial state.
The controller ignores the renderer's return value. A live editor or pointer/keyboard
rearrangement calls `controller.defer()` before its first local DOM mutation and invokes
the returned one-shot resume only after dispatch has synchronously staged the semantic
result, or after cancellation has restored the prior local DOM. Resume reconciles the
newest publisher reading. Optional recorded scalar attributes have a null initial
value and must be removed when that value returns.

### The widget controller

`widgetController(owner)` is the one semantic interface; callers supply no options.
Leaf captures the owner's identity and revision-bound declaration before upgrade, so an
author change to those facts fails closed. Its methods are `read`, `subscribe`,
`dispatch`, `defer`, and `present`.

`read()` returns an immutable `{authored, state, thread, provenance, actions}`
snapshot. `authored` is the typed baseline decoded from
validated source markup; `state` is that baseline with admitted and unresolved records
folded over it; `thread.heldBy` is the `id` of the open, admitted Thread whose root
holds this widget, or `null`. Each `actions` entry carries its availability and
exact history or Undo candidates. Guard every optimistic mutation with its entry's
availability; `dispatch()` repeats the same check.

`subscribe(callback)` invokes immediately, returns cleanup, and should be stopped on
disconnect; reconnecting subscribes again. For each reading the controller calls the
module's `renderState(state)` first and these subscribers after. Report-only and quoted
semantic widgets subscribe too, even with no interactive controls. What the declaration
alone determines, such as a holder's settlement (`x-retired-when`), Leaf paints whether
or not the module subscribes.

`dispatch({kind: "action", verb, detail, attempt?})` and
`dispatch({kind: "undo", target})` return `null` when the newest reading refuses the
command, otherwise `{reading, delivery}`. The returned reading already holds the
optimistic result; delivery later yields the admitted event or null, and a refusal
restores authoritative state. Undo targets only a stable `id` or `attempt` from the
current entry's candidates. The server remains final admission for every command.

### Reading regions

A pane declares `x-reading-role: pane` and keeps `x-content: markup`: exactly one direct
body element between an optional native `header` first and an optional native `footer`
last. The validator reads the role rather than the tag name, and delivery paints it into
the served document as `data-lf-reading-role`, which the kernel's theme and the
workspace Layout lay out as a pane from the first paint, so every package's pane takes
the same rules; its module registers the pane's body as described below.

Whether a pane's body scrolls is the workspace Layout's (`layouts.css`). Where the
window is large enough, the workspace is full-height: it fills the window, and the
Layout gives its body a definite height, so a pane that is the body or a direct cell of
it may shrink below its content and scrolls its body; a pane inside a section of the
body, or inside another pane's body, flows with what holds it, and elsewhere every pane
takes its content's height. Nothing in a module measures a minimum or chooses a
posture. While the workspace is full-height, the Layout sets `--lf-full-height: 1` on
`main`, and a widget that should grow to fill the height it is given, such as a
playground's stage, keys its rules on `@container style(--lf-full-height: 1)`. A behavior
module that composes regions out of boxes it generates, such as a playground's controls
beside its preview, takes the pane rules by marking those boxes
`data-lf-reading-role="pane"` and `data-lf-generated`, with the pane grammar of one
header, one body, and one footer. A generated pane scrolls its body wherever it stands in
a full-height workspace, since its widget sizes it. The attributes are the module's to
write and never an author's, since `page check` refuses `data-lf-` markup. Keep the
package theme to placement inside that grammar, such as track sizes and chrome; a
package copy of the full-height rules is a second posture decision that drifts from the
Layout's. Generate boxes rather than `lf-pane` elements themselves: those are authored
words the render gate pairs with the file.

`registerReadingRegion({id, host, body})` binds a region's identity to its host and to
the body that scrolls it whenever the theme makes it scroll. The host makes focus in a
pane's header or footer select that pane. Register from `connectedCallback` and call
the returned cleanup from `disconnectedCallback`, so a reconnect can claim the same id.
`readingPosture(node)` is `bounded` exactly while the region's body is its own
scroller, and `watchReadingRegionTransitions(listener)` receives a `shift` when a
region's scroller changes without a gesture; the continuity owner records the user's
place as they scroll and restores it there.

A compound widget whose parts scroll independently registers each with
`registerReadingRegion({id, host, body})`, taking a stable id from
`compoundReadingRegionId(owner, localName)`. A composition that hides or reveals regions,
such as a tab switch, runs the change through `preserveReadingRegions(owner, change)`,
which awaits the change's returned layout promise before restoring the visible regions'
scrollers. `runtime/reading-regions.js` describes the region model.

A widget that re-renders or resizes content inside a scroller of its own holds the
user's place with `placeKeeper(scroller, {items, identity})` rather than by restoring a
`scrollTop`; `runtime/user-place.js` describes it.

A widget that remembers where the user was reading, in a view it hides and shows again,
keeps a place rather than an offset: `capturePlace()` reads the page's place as a
landmark in its own words, and `restorePlace(place)` returns to it however the page has
moved since (`runtime/reading-place.js`). A widget that adds same-document history
entries adds them with `pushEntry(url)` and `replaceEntry(url)`, and places the page
itself at Back or Forward to one of them by claiming that traversal with
`claimTraversals(claim, {signal})`. Every other traversal returns the user to the offset
the entry was left at (`runtime/history.js`), unless the element the entry's fragment
names is no longer shown: that one reaches the widget holding it shut as `lf-reveal`
and lands on it, as a followed link to it does.

A sticky header, a sticky box over the top of its scroller, declares the room it takes
with `declareStickyHeaders(host, property, headers)`, which keeps `property` on `host` at
the tallest header's height for a `scroll-padding` or `scroll-margin` to read, so every
landing, native or the runtime's, arrives below it. The same declaration tells the
runtime that what passes under the header is not on screen, for read acknowledgement,
arrival checks, and chrome placement.

A composition allocates a Leaf element's outer box. The package owns how the element's
contents use that allocation, based on its available inline size rather than the page
shell or a reading posture. Prefer intrinsic grid or flex layout. When the contents need
a discrete breakpoint, make the element a query container and apply the conditional
rules to its descendants. A host rule inside that block does not fail: an unnamed query
answers from the nearest ancestor container, and `body` is a container, so the rule
silently follows the page shell instead. Keep the host's own layout intrinsic, or put
the properties that change on a descendant layout box.

### Focus, motion, and travel

A module that puts the user somewhere calls `focusDestination(element)` rather than
`element.focus()`, wherever that place is not already a control. It lends the element the
tab stop a control has for exactly as long as it holds it, so the browser's own Tab order
continues from there and no `tabindex` is left on the page behind the user. What needs
it is a widget's own Escape step landing them back in the thing it took them out of: the
patch a file filter belongs to, the exhibit a box was about.

A module that moves, hides, or replaces nodes the user may be standing in, as a reorder or
a re-render does, calls `holdFocus(scope)` before the change and the function it returns
after it. Moving a focused node drops its focus to the page body; the returned function
puts the user back on that node, with its caret, or on the first drawn stand-in it is
passed, such as the replacement keyed on the same identity. It does nothing once focus was
placed elsewhere in the meantime, and `holdFocus` returns `null` where the user stands
outside `scope`.

A module that takes the user to a thread calls `openThread(id, {focus})`
with the Thread's `id`. It opens the thread where the page shows it, inline beside
its passage or widget, and in Threads when it has no place on the page, the same choice a
mark and `t` make; `focus: "thread"` lands on the thread and the default `"reply"` lands in
its reply box. A place on the page is an ordinary fragment link; Leaf follows it the
way it travels to a thread, clearing a panel that covers the page and opening whatever
holds the element.

A module that names an element away from it, in a feed row or a summary, reads the page's
shared names rather than its own. `addressableLabel(element)` is what the chrome calls
it: first the name the authoring contract gives it (the attribute its entry declares
with `x-name`, else a leading `<summary>`, heading, or titled member's `<strong>`,
inside a leading `<header>` too), else its caption or `aria-label`. An element whose
words are its own, such as a paragraph or a list item, is otherwise named by those
words cut short; any other element takes the name of the nearest element holding it
that has one, so a question's options are named by the question. Past that, plain
markup is named by its words cut short and a widget by nothing: the label is empty, and
`addressableWord(element)` is the word for its kind. A
widget whose title is an attribute, as a column's `label` is, declares `x-name`.
`anchorLabel(anchor, about)` names a comment's anchor the way Threads does, and
`markdownWords(text)` is the words a Markdown string renders to.

A message's widget markup is a document of its own, and it may repeat the shapes the page
holds. A module that finds a partner element by reference, as a seat names the widget it
serves, searches `authoredScope(element)`: the page's `main`, or the body of the message
whose markup holds the element. A search of the whole `document` lets quoted markup answer
for the page.

A module that moves something calls `motion(element, keyframes, ms)` rather than
`element.animate`. The stylesheet's reduced-motion guard reaches CSS animation and
transitions, not a Web Animations call a module makes for itself, so `motion` is where a
user who asked for stillness is answered: it returns `null` under that preference,
before `body[data-lf-presented]`, and while standing state is being restored into
replacement markup, and a caller treats no animation and a finished one as the same
state. `reducedMotion()`, `scrollBehavior()`, and `onMotionPreferenceChange()` answer the
same preference where a module has to branch on it, and `FOLD_MS` is how long a unit takes
to leave, so a widget retiring one uses that constant rather than choosing a number. Spend
a duration only on letting the eye follow a box from where it was to where it is. A result
the module can already draw is drawn in the gesture rather than after a wait.

A navigation captures `retainUserIntent()` in the gesture that starts it, before its
first wait, and checks the returned predicate after every wait before moving focus or
scroll: loading a file, a deferred value, or a renderer is a wait, and a user who pressed on
in the meantime is not moved back. A predicate taken after a wait would carry a newer
gesture's authority. If the navigation itself opens or closes a surface that moves
focus, `currentIntent.handoff(() => changeSurface())` preserves that synchronous focus
transfer without renewing the original input generation. After a wait, check the
predicate before starting that synchronous handoff. If the synchronous work already
moved focus, the handoff keeps and adopts that destination instead of running the old
focus move. A skipped move returns false, so a caller that requires the surface change
can decline; adoption alone does not report that the move ran.

When Leaf travels to a target, such as a comment anchor or an Ask, it first dispatches
`lf-reveal` on each ancestor of the target and the target itself, outermost first, with
`detail: {target, mayReveal, present}`. A widget that folds content listens for it and
opens whatever holds `target`. `mayReveal` is the traveller's retained intent: an
asynchronous listener checks it after each wait. A listener whose opening settles
asynchronously passes that promise to `present(promise)`, so the travel waits for the
target's geometry. `lf-tabs` is the worked example.

`registerMarginContribution({key, target, source?, read, activate})` is the package boundary for
page-edge actions. `read()` returns the contribution's complete current reading,
including immutable `marginEntry({...})` records; it never returns controls. Leaf renders
those same records independently in the target's Margin cluster and in Page Map.
Reading items in `readings` have nonempty `id` strings, unique within that contribution;
other contributions may reuse an ID. Leaf retains each projected control by the opaque
contribution key and entry key while its native kind remains compatible. Actions and disclosures are buttons; statuses are spans,
so crossing that semantic boundary replaces the host instead of emulating a button.
`target` is an
element or a function returning the element that currently anchors the action. `source`
defaults to that target and may separately name the semantic owner when presentation has
to move to a surviving ancestor.
`activate(token, context)` is the sole effect path and receives the projected origin,
surface, input kind, current entry, and a focus capability. That capability moves the
current surface only when activation owned keyboard standing and otherwise returns
false. The returned registration
exposes `entry`, `control`, `contains`, `activate`, `focus`, `update`, and `unregister`;
`update()` replaces the whole reading and may synchronously lay it out or focus a
surviving key. Keep text fields, history, and other mechanical editing state in the
widget. Publish only action and status records to the margin, with explicit `element` or
`entries` relations when a disclosure owns another surface or entry.

A contribution stands in its target's cluster wherever that cluster stands: in the rail
beside a column page, or as a pin over the page by the target, where an unfolding
cluster grows leftward. Leaf inserts nothing into the
page's content for it, so its controls come after the page's content in the tab order;
the margin's own keyboard routes, `t`, and the Page Map reach them from the target.
Nothing about the contribution changes with the posture, and a package never places or
sizes its controls itself.

### Following a reference

A module reaches another widget through an attribute its entry declares in `x-refers`
(References between widgets, below) rather than looking the id up itself. Leaf
resolves the attribute in the owner's own authored document first, so a widget in a
reply finds its message's element before a page element with the same id, as the server
does, and then in the page, which a reply's widget may name. Both verbs below
throw a `TypeError` for an attribute the owner's entry does not declare.

A key addresses elements under the named widget in one key space: a registered visual
part's id, a projected datum's key, or, where the widget's parts have a private address,
whatever its `lfElementsFor(key)` maps to elements under itself. `lf-code` answers its
`hi` grammar, so `"3-5,8"` addresses those lines.

`navigateToDatum(widget, attribute, key, messages)` travels to the first element a key
addresses. Leaf resolves declared shadow trees, asks the target to hydrate lazy data or
draw a visual part it shows only in another state, opens its containing disclosure, focuses that disclosure, updates the fragment, and
announces the supplied `success` or `missing` message. A lazy target may implement
`lfRevealDatum(key)` to return its hydration promise and `lfDataDatum(key)` to map a
semantic key to the rendered projected element.

#### Indicating (experimental)

The signature and the `lfElementsFor` hook may change. `indicate(widget, attribute,
key)` marks the elements a key addresses, in place of whatever that widget last
indicated through the same attribute, and returns whether anything is marked; `null`
clears it. Leaf paints the marked elements with `data-lf-indicated` and nothing else,
leaving the target's own ARIA state alone, and never scrolls, focuses, reveals, hydrates,
or announces for them, so a driver may move its indication every animation frame without
moving the page; the driver's own narration says what the mark means.
An indication is browser state, like hover: the log never records it, and a new revision
does not carry it. A widget whose parts have a face of their own styles
`[data-lf-indicated]` on them; the default is an accent outline. A target that re-renders
what a key addresses calls `layoutChanged(this)`, and every standing indication resolves
again.

### Commands and keyboard routes

A widget contributes each command once with `commands(source, title, rows, options)`.
The dispatcher, shortcut bar, command reference, `aria-keyshortcuts`, and Ask projection all
consume those same live rows. Set a row or route's `decision` to its concise, non-empty
action-name string—or a function returning one—and give it `control` for the visible
element that performs the action. A Decision action begins an answer, answers, advances,
or revises the Ask containing `source`. The action name is separate from `label`, which
remains the command register's own-scope keycap override. A row with no bindings when
`commands()` registers it must provide a non-empty string `label`, a `label` function, or
a Decision action name. This also applies when computed `keys` is initially empty and
gains bindings later. The command reference uses a keyless Decision command's action name
rather than a blank keycap.
Every ordered Decision receives one of the Ask's contextual `1` through `9` routes while
capacity remains, independently of any intrinsic widget binding. The Ask digit and the
widget binding share one command id and source-scoped command reference. Invoking either
therefore rechecks the original scope and liveness and calls the original `run` (or
clicks a run-less native control). A focused widget declaration
wins when it collides with an Ask digit; undeclared digits continue to the Ask.

`bindingBadge` may name an empty face a widget already positions. Each supplied face
belongs to one action; core writes the reachable Ask digit there while the whole face is
connected, visible, and uncovered. Otherwise core paints its own binding badge at the
visible control. Routes let one parameterized row contribute distinct controls and
intrinsic bindings. Do not maintain a second Ask-control list or declare the Ask's
contextual digits in the package.

Command scopes compose by focused ancestry. The exact control scope is nearest, followed
by containing widget scopes and Leaf's outer page scopes. A scope owns only the bindings
whose rows implement a Leaf invocation, so an undeclared key falls outward. An
implemented declaration keeps its key while its command is unavailable, so the key never
exposes an ancestor's different meaning: liveness removes execution and projections, not
the claim. Escape means one step back at every depth, so no ancestor's Escape is a
different meaning, and a dead inner Escape declaration passes the key to the next live
return rather than stranding it. A row without
`run` only presents native behavior or a shared outer handler and does not shadow it. Text
fields and other native interactions retain their editing keys ahead of ancestor widget
scopes.

Use `commandScope(title, rows, options)` when Leaf, rather than the widget, creates the
focusable control. Put the returned capability on a margin-entry record's `scope`; each
projection attaches that scope to its own visible control. When the same command set
also applies to retained widget DOM, attach that one capability with
`commands(element, scope)` instead of declaring the rows again. Use
`commands(element, title, rows, options)` for a scope that exists only on widget-owned
DOM.

Every visible press a widget builds with `offer()` or `selectableOffer()` also joins the
generated target map after `g`. Packages do not declare another `g` binding or repeat
those controls in a destination list. Text and range inputs remain ordinary Tab stops;
buttons, checkboxes, radios, and selectable controls are addressable because they have a
discrete activation. A custom element with a complete host-level `focus()` and `click()`
contract passes `true` as `offer()`'s fifth `pressable` argument; its tag then supplies the
same addressable marker as a native control.

When the scope belongs to an Ask, `options.answer` may read its concise current answer for
the answered row in the Asks drawer. Leaf normalizes whitespace and bounds the displayed
answer; the package owns its meaning and words. Attach the answer reader to one stable scope
owned by the Ask, even when several descendant scopes contribute controls. Answer metadata
stays readable after a scope's availability condition closes, while the command rows remain gated.

Register the command once, not every nearby button. Evidence nested inside an
option is not an answer, and a shared-margin entry may sit outside the Ask source. When
controls or availability change, keep the row fields computed and call `paintKeys()`;
every command projection then updates together. A package that needs the page-wide open
Ask set calls `watchAsks(owner, callback)`. It invokes `callback(openAsks)` on the
microtask after subscribing and again after each state change, at most once per
microtask and possibly with an unchanged set; it skips calls while `owner` is
disconnected, and returns a cleanup function the owner calls on disconnect. Each
Ask is an immutable `{id, tag, sourceId, sourceTag, thread}` record; resolve a node only
to present or focus it, never to decide membership or answered state. The set is empty
until the page's first server reading is admitted, and it changes with each later
reading rather than when a gesture is sent, because only the log says which authored
Asks still stand and which of them are answered. Package semantic behavior subscribes only through its
controller.

Every row passed to `commands()` has a stable dotted `id`, such as `draft.save`. Keep that
identity when its key or wording changes: the command browser and repeated widget
instances use it instead of display prose. If one compact row binds keys with different
meanings, add `routes` with an `id`, `binding`, and action sentence for each meaning. The
shortcut bar stays compact, while the command reference lists and runs each route on its own.
Use `runFromCommandReference: false` only for a parameterized step that cannot be run without a
choice the command reference does not have, such as a generated hint tied to the live viewport. An
optional `reach` on a row or scope supplies the short place phrase shown when a command
is not available (for example, `in an open draft editor`).

A list of focusable rows takes its walk from `rowWalk({id, noun, plural, rows})`, whose
two returned rows go into the list's own scope: ArrowUp and ArrowDown step and clamp,
Home and End reach the ends, and each landing shows its position, such as `Option 3 of
7`. `rows()` returns the list as it stands at each press.

A widget-owned composition box is the runtime's text field, `offer(TEXT_FIELD)` from the
widget API: a Markdown editor that shows the draft the way the sent message will read
and answers the textarea members a box needs (`value`, the selection, `placeholder`,
`readOnly`, `name`, `aria-label`), firing `input` for the user's edits only. Wire it
with `wireInput()`, which registers Enter for the contextual action on physical
keyboards and leaves Shift+Enter as a newline. On touch keyboards, Enter stays a newline
and the visible control submits; Mod+Enter is also available where a modifier key
exists. The helper also owns shared draft persistence, busy state, and shortcut
projections. A direct editor that needs more commands, such as Save and Cancel,
registers those rows on its box with the same text-entry meanings. `TEXT_BOX` matches
the text field and any native textarea, for code asking whether an element takes typed
paragraphs.

The call returns the box's one seam onto its draft, and a box holds more than its
`.value`: an image pasted into one is kept as Markdown and shown as a thumbnail beside
the words, never in the field. So `sync.value()` reads the whole draft, `sync.load()`
replaces it — a stored record, a draft arriving from another tab, the emptiness a send
leaves — and `sync()` says the box's standing changed. The send button, placeholder, and
whatever the widget's own `paint` option draws from the box repaint once, in the
runtime's next standing paint, before that frame shows. Write `.value` only to seed the
box before wiring it.

## User state

A widget whose user changes something records each change as an `action` event in the
page's append-only log. The package writes no storage or server code. It declares verbs
under the element's `x-state`, and Leaf validates each event at the log's one append
door, folds the log into current state, gives that state to the module, and lists it
for the agent under `state` in `leaf page state`.

The swipe package is a small complete example. `packages/swipe/registry.json`
declares one verb on `lf-swipe-deck` and the condition that answers its Ask, and
`widgets/lf-swipe-deck.js` subscribes to and dispatches it:

```json
{
  "x-state": {
    "swipe": {
      "detail": {
        "type": "object",
        "properties": {
          "card": { "type": "string" },
          "to": { "type": "string" },
          "rank": { "type": "string" }
        },
        "required": ["card", "to", "rank"],
        "additionalProperties": false
      },
      "unit": "card",
      "record": { "kind": "position", "within": "lf-swipe-pile", "value": "to", "rank": "rank" }
    }
  },
  "x-awaits": {
    "region": true,
    "answered": {
      "swipe": { "empty": { "within": "lf-swipe-pile", "when": { "verdict": ["unseen"] } } }
    }
  }
}
```

`detail` is the JSON Schema every event of that verb must satisfy. Each verb is its own
piece of state: the owning element, the `unit`, and the verb together form the fold
coordinate. At each coordinate the latest surviving action stands, and different
coordinates stand side by side. Swiping a card again therefore replaces that card's
earlier verdict, while verdicts on different cards coexist. `unit` is `"widget"` for a
verb that states the whole widget's value at once, or the detail field naming the
element it is per. `record` says how the standing state reads in markup: here, the
card's position inside a pile. `page check` refuses a version that contradicts
it without `restated`, and `authoring-revisions.md`, "Honor user state", says which
record forms the agent's next version writes back. The `$keys`
entries in `assets/registry.json` define each key exactly.

`x-awaits.answered` says when the widget's Ask is answered, as a condition on that
standing state for each verb that can answer it. `{}` holds while the verb's state
stands, `when` narrows a verb to instances with matching attributes, and `empty` holds
while the named container inside the widget has no members. Here the deck is answered
once its `unseen` pile is empty, so the swipe that empties it is the answer and
returning any card reopens the Ask. The one-line forms elsewhere follow the same
shape: `"answered": {"edit": {}}` answers a draft once an edit stands, and
`"answered": {"choose": {"when": {"multiple": [false]}}, "answer": {"when":
{"multiple": [true]}}}` answers a single-choice group by its pick and a `multiple` group
by its Done press.

The module reads and writes through `widgetController(owner)`, described under "A
widget": `subscribe` delivers the authored baseline with the fold applied, and
`dispatch({kind: "action", verb, detail})` sends a gesture whose result is on screen
before the server admits it.

A verb that lets the user add a real child declares `creates: {child, words}`.
Its fold unit names the detail field carrying the new child's canonical element id,
`words` names the field carrying its non-empty words, and the detail holds exactly those
two required fields with no record form. Each added child therefore stands on its own
coordinate: a later action of another verb leaves it in place, and undoing the `add`
removes it. The child tag admits the sender through `x-owners`, requires only its
canonical `id`, and has `x-content: markup`. The append door refuses an id the sending
document already holds, and `page check` enforces the declared tag and
direct-ownership relation once an author writes the child into the markup.

A verb whose state the agent writes rather than the user declares `"writer": "agent"`
beside its `detail`, `unit`, and `record`. A worker posts it with
`leaf page report`, the page paints it live, and it stands until a version
answers it; the user has no control for it. Its record is required and may not be `body`, and it may name the detail field
carrying its short human-readable news with `update`. Every verb has exactly one
writer, so a coordinate never holds a user's action and an agent's report at once.
Command Hub's `lf-task` `status` is the shipped example, and a widget declaring such a
verb also declares the boolean `overruled` attribute a version keeps its own state
with. A worker that reacts to the user's actions follows them as they land with
`leaf page events PAGE --follow`.

## References between widgets

Use `x-refers` when authored attributes point at other page objects. Its value is
a map from attribute names to target contracts. `{}` accepts any existing element id.
A typed contract uses `via` to name a package-owned shared registry map and `where` to
match a declaration there:

```json
{
  "x-refers": {
    "target": { "via": "$command.widgets", "where": { "role": "goal" } },
    "worker": { "via": "$command.widgets", "where": { "role": "worker" } }
  }
}
```

Leaf validates the generic relation; the package owns the map, roles, and participating
widget tags. A later package can therefore add another goal or worker widget by merging
its entry into `$command.widgets`, without changing core.

## Page history

A widget that renders the page's history declares `x-history` and reads it through
`watchHistory(owner, callback)`: the server's rows, newest first, each already
carrying its thread, whether it was undone, the name an agent's row is shown under
as `agent`, and a gesture's words as the document it was made in had them. The
widget words those facts; it does not fold the log.

## External or derived data

Authored markup says what a version begins with; the event log says what users and
agents did afterward. A current deployment, sensor reading, worktree, or query result
is neither. Leaf keeps that third authority as one replaceable JSON file per source.

The source id belongs to the page: it says which concrete feed this page uses. Its
meaning comes from a named contract under `$data.contracts`, which can travel in any
package and be shared by more than one widget:

```json
{
  "$data": {
    "description": "Reusable build-data contracts.",
    "contracts": {
      "build-status": {
        "description": "Current result keyed by branch.",
        "schema": {
          "type": "object",
          "additionalProperties": { "enum": ["passing", "failing"] }
        }
      }
    }
  }
}
```

A widget declares the inputs it knows how to present. Each input names its contract and
the attribute that will carry the page's source id. Make that attribute required when
the widget cannot work without the input; an optional unbound input delivers `null`.
Widget-specific operating
instructions can travel in `x-guidance`; contract-specific producer instructions can
travel beside the contract in `guidance`. Package guidance files are for instructions
that really apply to the package as a whole.

```json
{
  "lf-builds": {
    "type": "object",
    "properties": {
      "id": { "type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$" },
      "source": { "type": "string", "pattern": "^[a-z][a-z0-9-]*$" }
    },
    "required": ["id", "source"],
    "additionalProperties": false,
    "x-content": "empty",
    "x-data": {
      "builds": {
        "contract": "build-status",
        "source": "source"
      }
    },
    "x-guidance": {
      "author": "Bind `source` to the build feed this page should show."
    },
    "x-upgrade": true
  }
}
```

The page makes the concrete binding in ordinary authored markup. Several widgets may
share one source when they read the same contract; two independent feeds use different
ids.

```html
<lf-builds id="release-builds" source="release-ci"></lf-builds>
```

The host gathers the value; Leaf does not run a provider or fetch a package URL. Set a
complete value using the page's source id:

```bash
printf '%s' '{"main":"passing"}' | leaf data set PAGE release-ci
leaf data set PAGE release-ci --file build-state.json
sed -n '20,44p' CHANGELOG.md | jq -Rs . | leaf data set PAGE release-notes
leaf data clear PAGE release-ci
```

Each source's value is an ordinary JSON file at `data/<source>.json` in the page
directory, and `data.json` records the contract each source id was first set under.
`data set` checks the binding and validates the value before replacing that file
atomically; a rejected value leaves the file untouched. Once a source has been set,
any process may rewrite its file with plain JSON. Every reading validates the file
against the contract, so a value that fails it reaches users as that source's error
rather than as data, and `page check` and `page state` report it. Tabs hear a
rewritten file as they hear any other page change.

A source's revision is a digest of its file's bytes, and its `updated` instant is the
file's modification time. Nothing keeps a replaced value: every document that binds a
source reads its current value, including stamped versions and widgets frozen into
threads. A document that must keep one value binds its own source id and nothing
rewrites that source. Source revisions and event sequences are independent: an old poll
may contain new data, and a new event response may contain old data, so neither orders
the other.

`data set` is the one write. A value that has to be derived from a file — a text
excerpt, a patch split into files — is the producer's to build, and a contract that
needs more than `jq` says how in its producer `guidance`. A package may ship that tool
as a Python file under `scripts/`, declaring its dependencies in inline script metadata
(PEP 723) with floors and no cap. `leaf package run NAME SCRIPT [ARGS]...` finds the
package by the name `--package` selects it by, bundled or installed, and runs the
script with `uv run --script` in the environment its header declares, apart from
Leaf's own. The script owns stdin, stdout, and the exit status, so guidance prints the
pipeline with no path in it:

```bash
git diff main... | leaf package run diff patch_manifest.py | leaf data set PAGE review-patch
```

`package check` and `package install` refuse a `scripts/*.py` without that header,
since uv would run it in whatever project the caller's directory reaches, and refuse a
constraint other than a `>=` floor. A subdirectory of `scripts/` holds helpers and is
not checked or run. A page never vendors `scripts/`. When a producer upstream of `data set` fails and
writes nothing, `data set` refuses the empty input and points back at that producer's
own error.

A source id keeps one contract for the lifetime of the page. `data clear` removes the
current value and keeps the recorded contract, so the id is never released for a new
meaning. Use a new source id for a new contract. Re-vendoring preserves each binding
and refuses an incoming registry that would change a bound contract's schema.
`leaf page state PAGE` exposes the complete `data_bindings` inventory so a producer can
discover the ids, contracts, widgets, and documents it needs without parsing markup.
Every source value goes to every user of the page, including fields a module does not
paint. Do not put credentials or private host state in it.

A contract whose value holds keyed rows declares `records`: the top-level array field
and each row's key field. A source replacement is accepted only when every row has a
non-empty, unique string key. Rows that each carry a large, independently useful
payload may name that field `deferred`. The source file still holds the complete value,
and readings validate all of it, but `/api/state` sends each row with that field
omitted; a widget uses `loadDeferred(snapshot, key)` to fetch one row's payload
using the delivery `watchData` handed it. A request naming a source revision the file
no longer holds is refused instead of combining a new payload with an old manifest.
This is how a collapsed `lf-diff` can show thousands of files without transferring or
rendering every patch first.

```json
{
  "records": { "items": "files", "key": "key", "deferred": "patch" },
  "schema": {
    "type": "object",
    "properties": {
      "files": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "key": { "type": "string" },
            "patch": { "type": "string" }
          },
          "required": ["key", "patch"]
        }
      }
    },
    "required": ["files"]
  }
}
```

A module subscribes through its own input declaration:

```js
this.stopWatching = watchData(this, "builds", (snapshot) => render(snapshot));
```

The callback receives `null` while the source has no readable value, otherwise a clone
of `{source, contract, revision, updated, value, origin}`. `revision` identifies the
value itself, so a renderer can distinguish two writes even when their wall clock
timestamps coincide. It runs immediately and again when that source revision changes.
A value that fails its contract is delivered as `null`; `page state` and `page check`
report why.
Return the cleanup function from the element's disconnect path. The callback must
state the whole rendering and remain idempotent.

Time readings made synchronously in controller, `watchData`, `watchUpdates`, and
`watchHistory` callbacks subscribe that paint to Leaf's shared clock. Calls to `ago`,
`shortAgo` and `quietSince` refresh the callback only when their result changes. `ago(ts)`
says how long ago `ts` was as the page words it everywhere ("2h ago"), and `shortAgo(ts)`
is the same reading for a tight seat ("2h"). `quietSince(ts)`
says whether working last heard at `ts` has gone unheard past the server's working
grace, the same bound the page's own activity reads. For another
rounded time reading, use `clockValue((now) => reading)`, whose `now` argument is the
calibrated server-now value in milliseconds. For a paint outside these
subscriptions, wrap it with `clocked(element, paint)` and call the returned function
where state changes; call its `.stop()` on disconnect. Time reads after an `await`
belong in a separate synchronous `clocked` paint. The timer does not reapply state or
redeliver unchanged data to keep a timestamp current.

`origin` identifies the declared `input`, concrete `source`, `contract`, and source
`revision`. An unchanged source keeps that origin when another source changes. Passing
`{snapshot}` to `projectData` supplies this default origin. When the emitter knows the
exact JSON coordinate within the source value, its `originOf(record, index)` returns
`{...snapshot.origin, path: [...]}`;
path segments are object keys or array indices. A formatted or parsed record may only
name its whole input. This identifies construction inputs, not an inverse edit mapping.

Render the value with `projectData(root, records, keyOf, render, options)`. The root is an
id-bearing authored seat and owns the projection's children. `keyOf` returns a
non-empty rendering key, unique in that projection; `render` receives
`(record, priorNode, index)` and returns its element, reusing `priorNode` where that
preserves a focused control or selection. Leaf marks those words as readable data
rather than authored prose and reconciles their order by key. A renderer
that owns a nested layout passes `{nested: true}` and returns its existing descendants;
Leaf labels those nodes without moving them, and the module orders each container with
`setChildren(parent, nodes)`, which moves only what is out of place and keeps the user
in a node it moves. Add `labelOf(record, index)` when a thread
should name a projected datum with a human coordinate; the rendering key remains opaque to
the runtime. A widget declaring `x-data` passes `{snapshot}` with the delivery from
`watchData`, including `null` when no current value exists. Leaf stamps the projection
with that snapshot's source and revision. Pass `identify(record, index)` when the
emitter can name the same subject across source replacements. Its non-empty string
need not equal the rendering key and must be unique within the projection; a comment
follows that subject and retains the quote from the value the user saw. A reused
identifier for a new subject needs a new identity. Other projected keys remain exact
only within the captured revision; replacing that value marks their placement outdated.
Derived projections omit `snapshot`
and retain their section/key identity. If a `watchData` callback renders asynchronously,
it returns that promise so Leaf publishes the source revision as ready only after the
projection settles. A rejection is reported as that subscriber's page
error; it does not make later state
reads repeat the same page-wide failure. A rejection from the callback's first run is
stronger: Leaf drops that subscription, so the callback is not asked to restate again
until the element is reconnected.

Leaf records the default origin or `originOf(record, index)` result as JSON in
`data-lf-origin` on each datum; a null origin removes any previous provenance. Derived records outside the data
store can instead name their contributing widget seats as `{derived: [{widget: id}]}`.
Leaf never infers them from displayed
text or datum keys.

## Reading and opening Threads from a widget

`readThreads()` returns the same immutable `{phase, threads}` collection the
Threads panel reads. `threads` contains conversations; a bare reaction record without
a spoken turn is not a listed Thread. `watchThreads(owner, callback)` calls a connected
widget with that collection initially and after relevant application updates; it returns a stop
function for `disconnectedCallback`. Each widget keeps its own search, filter, and
order state and derives its displayed rows from the collection. `threadTurns(thread)`
selects a Thread's displayed turns, and `threadSummary(thread)` gives its topic and
latest activity. An agent-authored message or closing event carries `agent`, the
name it is shown under. `openThread(thread.id)` takes the user to Leaf's canonical
conversation surface for that Thread. The widget does not need to render or own the
conversation to provide that route.

`threadActions` lets a package add its own controls over the current Thread reading
and Leaf's optimistic event path:

```js
threadActions.reply(thread.key, text);
threadActions.resolve(thread.key);
threadActions.reopen(thread.key);
threadActions.toggleReaction(thread.key, agentMessage.id, token);
```

Each method returns `null` when the current reading does not offer that action,
otherwise a promise resolving to the admitted event or `null` if admission refuses it.
The action changes `readThreads()` immediately; the server remains final. A reply
requires non-empty text. A reaction requires an addressable agent message and a token
in the current layer's vocabulary; pressing an already standing token takes it back.
Use the Thread's stable `key`, which survives admission of a locally opened Thread.
Leaf's reply editors keep one durable draft per Thread; a package input retains its
own draft.

## Rendering Threads in a widget

`mountThreadViews(owner, render)` lets a package supply containers for Leaf's core
conversation view. It registers one consumer per Element and returns a handle with
`read()`, `update()`, and `unregister()`. The callback receives the same immutable
Thread collection as `readThreads()` on its initial presentation and on later
publications. A Thread waiting on the user has unresolved
`attention.kind === "needs_user"`, which
includes recovery after a failed response; `"waiting"` means it is with the agent.
A Thread's `id` is the name Asks and workflows give it; its `root` is the first
message it still holds, whose id differs where the log lost the opening message.
Each Thread's `key` survives admission of a pending gesture, and its `anchor`
names the `section` (the widget's id) and `datum` it rests on. A returned promise
delays that widget's mirror repaint without holding up Leaf's panel, margin, or
read presentation. The second argument's `signal` is aborted when a newer render
supersedes it or the consumer unregisters. Asynchronous callbacks check it before
changing their UI. The owner unregisters on disconnect.

For a Thread list or dashboard, `surfaces.render(thread.key, outlet)` shows a
conversation in an Element inside the widget. Each widget chooses its own Threads,
containers, filters, and order. Several widgets may render the same Thread, and
removing one does not remove another's view. These are mirrors: they do not take the
Thread away from its page or margin position. Leaf renders the messages, reply editor,
reactions, resolution controls, and receipts. An authored message's interactive
widgets open in the Threads panel, as they do from other inline Thread views.

```js
this.threads = mountThreadViews(this, (collection, surfaces) => {
  for (const thread of collection.threads) {
    const outlet = this.outletFor(thread.key);
    if (outlet) surfaces.render(thread.key, outlet);
  }
});
```

The widget owns outlet creation and layout. Leaf requires every outlet to remain
inside its owner, and a consumer may render each Thread only once per callback.
The handle's `update()` requests a new render after a local layout change.

## Widget-local Thread placement

A widget declares `"x-thread-surface": true` to place Thread UI beside its own
projected data. Use `consumeThreads(owner, render)` with
`surfaces.place(thread.key, outlet)` for an exact datum and
`surfaces.placeComposition(outlet)` for its active composer. The callback
selects its Threads and hands each an outlet it owns. Here
`this.outletFor` stands for the widget's own method, which finds or creates the outlet
element beside the datum and returns `null` when the datum is not displayed
(`lf-diff`'s `threadOutletFor` is the worked example):

```js
this.threadSurface = consumeThreads(this, (collection, surfaces) => {
  for (const thread of collection.threads) {
    if (thread.anchor?.section !== this.id || !thread.anchor.datum) continue;
    const target = surfaces.target(thread.key);
    const outlet = target && this.outletFor(target);
    if (outlet) surfaces.place(thread.key, outlet);
  }
  const outlet = surfaces.composition && this.outletFor(surfaces.composition);
  if (outlet) surfaces.placeComposition(outlet);
});
```

`target(key)` returns `{anchor, placement}` only for an exact datum belonging to the
widget, otherwise `null`; `placement.datumElement` is the rendered datum.
`composition` supplies the equivalent placement for the active composer, which may
precede any Thread. The widget owns outlet creation, removal, and layout.
Leaf validates target ownership and outlet containment before committing placements.
Core moves its one composer node or renders retained messages, replies, reactions,
settlement controls, and receipts into each outlet. A claimed thread does not also
appear in the margin projection; the Threads panel remains the complete index. With
Threads closed, `t`/`T` lands on this local surface before trying the margin-projection
fallback. Clicking the Threads toggle from the focused surface carries the same thread
into the panel.

The consumer omits placements for data that is filtered, collapsed, or not yet hydrated.
That keeps lazy widgets lazy and restores the margin-projection fallback. Deliberate thread
travel may reveal the datum through `lfRevealDatum`; the ordinary reconciliation pass
then invokes the consumer again. The registration handle's `update()` invalidates layout-only
visibility changes, and `unregister()` removes the surface when the widget disconnects.
If a callback throws, Leaf reports a page error, clears that registration's core-owned
views, and returns its threads to the margin. Other registrations continue, and the
next ordinary reconciliation retries the consumer. Outlets must remain inside their
widget after the callback completes; disconnected outlets claim no threads. Core message-rendering
errors still fail the state application rather than accepting a partial thread.

The registration handle's `open(datum, { origin })` accepts one projected element owned
by the widget. Core captures its full datum coordinate, including external-data source
revision, opens the ordinary anchored draft, and seats the response bar in the consumer's
outlet when the datum still resolves exactly. `origin` is the widget control to which
Escape may return focus. Widgets do not receive draft, submission, or event APIs.

## Seeing it

After `leaf page init` re-vendors the page (`serving-pages.md`, "Re-vendoring and
layer epochs"), run `leaf page check <page> --render` on the version that uses
the replacement layer. Note the re-vendor in the next stamped version's changelog.

The render gate is where a module's mistakes surface — an upgrade that defines no element, a widget of no
size, a `x-verbatim` the rendered words contradict, a shadow root the declaration doesn't
declare, a word the registry promised that never reached the page, an attribute left on
the element that its declaration doesn't name, a `renderState` that changes the page when handed the same state again.

Then put it on the page. A widget is reviewed in place: the version that follows the
comment uses it where the comment asked, and the user comments on it there.
