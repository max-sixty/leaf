# Scrolling and motion

Read with [module-authoring.md](module-authoring.md).

## Scrolling

A widget whose box keeps a height of its own and scrolls what it holds, as a log or a
feed does, declares `bound` in its tag's declaration rather than scrolling a box
itself. Leaf then keeps the reader's place in the box, and an `end` bound follows the
newest entry while the reader is at the end (`page-layout.md`, "Bounds and widths").
To bound a box inside the widget instead, as under a caption, see `package-themes.md`,
"A theme change".

### Reading regions

A pane widget declares `reading-role: pane` and `content: markup`, and holds one
body element, with an optional native `header` before it and `footer` after. Whether a
pane's body scrolls is the workspace Layout's decision (`layouts.css`), not the
module's, and either way the module marks the body as a reading region, below.

While the workspace fills the window, the Layout sets `--lf-full-height: 1` on `main` and
on a grid of panes, telling their children they have a definite height to fill. A
widget keys its rules for that case on `@container style(--lf-full-height: 1)`, which
reads its parent, and fits what it shows to the height. It declares
`--lf-holds-height: 1` on each part that scrolls within it, and sets
`--lf-full-height: inherit` on each box that passes the height down, as a playground
does to its panes. A question's group, once told, passes it to its children, its last
block, such as the question's answer, taking the height the blocks before it leave, and
page tabs pass it to a tab that is one block. The property doesn't inherit, so a widget
nested deeper, or in a tab of several blocks, is not told and grows with its content.

A module that builds its own panes, such as a playground's controls beside its preview,
marks each generated box `data-lf-reading-role="pane"` and `data-lf-generated`, with a
header, a body and a footer, and draws the frame around them itself. Keep the package
theme to placement within the pane, such as track sizes, and don't copy the Layout's
full-height rules. A rule that sets a pane body's padding also states the top
padding as `--lf-pane-top`, which the workspace Layout reads to stick a header at the
body's edge where the body scrolls on its own. Generate plain boxes rather than `lf-pane` elements, which the render
gate expects to find in the page's file.

A module can generate a track beside its main content, such as a playground's controls
beside its preview. Mark it `data-lf-track`, and the Layout keeps it visible while the
window scrolls the taller content beside it, as with a sidebar page's track. When the
module stacks the track with the content, as on a phone, it declares
`--lf-track-scroll-behavior: flow` on the track's parent, and the track scrolls with
the page. Mark the track as a reading region, since it may scroll.

A horizontal scroll surface a module builds wears `data-lf-scroll` on its actual
viewport and declares overflow in its CSS; the page's own markup says the same with
`class="lf-scroll"` (`page-authoring.md`), a name the module leaves to the page, so the
page's CSS for it reaches only the page's own boxes. The mark supplies containment. Leaf adds keyboard
access and continuation cues, inspecting these surfaces for overflow instead of reading
every descendant's styles. A reading region's body wears the mark with a name, below;
its CSS still decides whether the region scrolls or flows.
Sticky headers set `--lf-head-inset: 0px` beside their `position: sticky` rule so
keyboard focus counts the header's own inset as visible.

Mark the pane's body, and any other box the widget may scroll,
`data-lf-scroll="NAME"`. A box that wears the mark with a name is a reading region for
as long as it stands in the page: Leaf keeps the user's place in it, and knows the
region in the task that marks the box. Where focus beside the box should count as being
in the region, as in a pane's header, mark the box around both
`data-lf-scroll-host="NAME"`. Leaf looks for that host between the box and the next
box around it that wears `data-lf-scroll` with a name.

To return the user to their place after a revision, Leaf knows a region by `NAME` and
the id of the nearest element with an id, starting at the host, or at the box where it
has no host, and going outward. An id the module writes counts as one. So give each box
of a widget its own name, and require an `id` in the declaration of a widget that marks
one. Where two boxes take one name under one such element, both are regions, but a
revision that replaces the two returns the user to their place in one of them alone.
A box in a thread message is a region whose place Leaf keeps only while the box stands.
Leaf finds the marks in the page, in a stage `shadowStage` builds and in the open
shadow root of an element that has said `lf-connect` (`module-plain-elements.md`).

Give the marked box a scrolling overflow (`auto` or `scroll`) only on an axis where its
content can outgrow it. A scrolling body bounds what stands in it, such as the card of
a comment on its contents, so a body sized to show everything it holds, as a
screenshot fitted to its box is, declares `visible` or `clip`, or `hidden` where it
keeps a `scrollbar-gutter` across states.

`scrollerFor(element)` returns the box that scrolls an element, its region's or the
page's, which is the document's own (`document.scrollingElement`).

When a change hides or shows regions, such as switching tabs, run it through
`preserveReadingRegions(owner, change)`, so Leaf restores the user's place in the
regions shown once `change`'s promise resolves. A region that shows one subject of
several at a time, as a trace's saved tree shows one checkpoint, replaces its body's
contents inside `showReadingSubject(body, subject, render)`, and the user returns to
their place in each subject.

### Holding the reader's place

When a widget redraws or resizes content where the user is reading, the browser's
scroll anchoring keeps their place: don't restore `scrollTop` or set
`overflow-anchor: none`. Redraw by keeping the nodes the change leaves as they were,
as `setRenderedChildren` does for a subtree the module renders whole
([module-authoring.md](module-authoring.md), "Retained nodes"), since a node that replaces
the one anchoring holds loses the place. Where a change
hides what the reader is reading, as folding it does, anchoring can't hold it: read
`const hold = holdPlace(column, standIn)` before the change and call `hold()` after
it, in the same task. Leaf reads the words at the reading line, a quarter of the way
down the window, in the middle of `column`, the box the change is made in, and
`hold()` puts them back where they stood. Where the change hid, removed or rewrote
them, `hold()` calls `standIn(node)` and puts the node it returns in their place, as
a section's gist takes the place of a paragraph folded behind it. `node` is the
element that held the words, which may stand deep inside the block the change hid:
look outward from it for that block, as `node.closest` does. For words a widget drew
in its shadow tree, `node` is that widget. The change itself scrolls nothing.

Leaf keeps the user's place in a member a widget hides and shows again later, where
the members are views of the page (`module-state.md`, "State only this tab keeps").

A list fed by the log or the clock, such as a feed of reports, shouldn't push the text
the user is reading. Build `new HeldReading(this, region, changed)`, where `region()`
returns the nodes the list draws into and `changed()` redraws the widget. Before each
draw, pass `hold()` the reading as a value that is `===` the last one only when nothing
changed, such as `JSON.stringify` of the rows, and draw what it returns: the new
reading, or the last one while the region's growth would move what the user sees.
`changed()` is called once that growth would be out of sight. `show()` lets the new
reading in and redraws, for a "Show new" control, and `release()` lets the next one in.

### Scrolling to a destination

To take the user somewhere, call `scrollIntoView(target, {block, behavior})`, where
`target` is an element or a Range. It places the target at `block` in its own reading
region, the box that scrolls it as the user reads, and every other box that scrolls
it, inside or around that region, reveals it at the nearest edge, so a start landing in
a bounded pane aligns it in the pane and moves the page only to show it; `block`
defaults to `start`. A `smooth` landing glides, and lands at once for a user who asked
for less motion. Sideways, each box reveals it at the nearest edge. A `nearest`
landing moves nothing where the target is already shown: the user sees all of it where
it fits, and as much of it as the window holds where it is longer, which
`alreadyShown(target)` answers for a widget deciding whether to land something else.
Pass `sideways: false` to align what the user is reading and keep their place across
its lines. To bring an item into its own strip or list and leave the page where
it is, pass that box as `within`: the item comes in at the nearest edge of each box,
at once, whatever `block` and `behavior` say. Unlike native `Element.scrollIntoView`,
it stays inside a live sample. Use it only for a deliberate move; focusing a visible
control or redrawing keeps the scroll.

`scrollersOf(node)` yields every box whose scroll moves a node, innermost first, out
to the page's `document.scrollingElement`. A widget that keeps something in view as
another widget moves, as `lf-code` keeps the line a film runs, sets the scroll of the
first (`scrollTo`, below) unless it is the page, so the page stays where the reader
left it. It and `onUserInput` ([module-input.md](module-input.md)), which says when
the reader's hand is in that box, are also available from `portable-api.js`.

A landing keeps the target's `scroll-margin` clear on every side, so a focused
control's ring shows. To bring in a heading or label with an item where there is room,
and the item alone where there is not, pass a Range or element holding both as
`including`, which lands in the target's place where it and its margins fit.

To set a box's scroll position, call the browser's own
`box.scrollTo({top, left, behavior: "instant"})`. Leaf hears that write as it is made,
and updates its scroll readers before the position paints, including a write during
resize delivery. Say the `behavior`: left out, the box's `scroll-behavior` decides,
which a page may set to smooth, and a smooth scroll reports its positions only through
the browser's scroll events. A write of the position a box already holds stops a scroll
the browser is driving there, so a module that may write one, as it restores an offset
or keeps one box beside another, first asks whether the write would move the box
(`/runtime/lib/scroll-range.js`).

`landingInsets(scroller)` is how far a landing keeps from each edge of a
scroller: its `scroll-padding`, and on the document the band Leaf states for its
chrome, which holds while the user writes in a floating box.
`shownWindow({within, gap, across})` is the window's visible rectangle clear of Leaf's
fixed chrome, narrowed to `within` and inset by `gap`; with `across` (`{left, right}`),
only chrome standing across those columns takes room. It reads the visual viewport,
which pinch zoom and a phone's keyboard shrink, or with `viewport: "layout"` the layout
viewport.

### Sticky headers

A sticky header has a stated height, sticks at `var(--lf-top)`, and adds its height to
`--lf-top` for what lies below it. A custom property can't read itself, so the holder
copies the incoming value to a second name:

```css
.file {
  --lf-top-outer: var(--lf-top);
}
.file > .head {
  position: sticky;
  top: var(--lf-top);
  block-size: var(--head-h);
  --lf-head-inset: var(--head-pad);
}
.file > .rows {
  --lf-top: calc(var(--lf-top-outer) + var(--head-h));
}
.file .row {
  scroll-margin-top: var(--head-h);
}
```

The rows' `scroll-margin-top` makes a scroll to a row land below the header.
`--lf-head-inset` says how far below the header's top edge its controls sit, so a
revealed control lands exactly there. Put the stacked value on a box that doesn't scroll
itself.

A box a package makes scroll sets `--lf-top: 0px` beside its `overflow`, so a header
inside it sticks at its top from the first paint. It sets `--lf-top-covered` to the
same value with it: the part of `--lf-top` the box's own `scroll-padding` already
clears, so a landing inside the box keeps clear only the headers stuck inside it. Leaf also restarts `--lf-top` on a box
marked as a scroll surface, such as a registered reading region's body, once it finds
the box scrolling and not sticking, `overflow: hidden` included. Leaf reads no other
box's overflow, so in a box that scrolls without that declaration or the mark, a header
sticks as far below the box's top as the headers stacked over the box, and covers what
lies under the header. A header sticks below its scroller's top padding; to have it sit
on the scroller's edge, set `--lf-top-start` to minus that padding and
`--lf-top: var(--lf-top-start)`. A scroller
with its own `scroll-padding` states it as `--lf-landing-room-start`. A box that only
clips, such as a card with rounded corners, uses `overflow: clip`, since a header inside
an `overflow: hidden` box scrolls away with the page.

Leaf leaves `--lf-landing-room` over a landing for its focus ring. A box a package
sticks beside the content it lists, as a side list does, sets its `top` that far below
`--lf-top`.

### Headers over the document

Mark a header the package places over the document `data-lf-root-header`, and Leaf
adds its actual border-box height to the root's landing inset while it stands in the
page with the mark. Independent headers add, and resizing the element, removing it or
taking its mark off updates the total, so take the mark off when the header becomes
local navigation. Only a header over the document belongs here: a nested scroller uses
the local sticky and landing inputs above. Packages own where their headers are
positioned; Leaf owns the aggregate root landing inset.

### Sideways scrollers and container queries

Give a box a package scrolls sideways the class `lf-text-scroller`, and Leaf leaves room
below its last line for an overlay scrollbar. Write its overflow as `auto hidden`. A
`visible` vertical axis would compute to `auto` beside the scrolling one, and a box that
scrolls vertically restarts the landing band, so a landing inside it would no longer
clear the sticky headers above it.

The page decides how big a Leaf element's box is, and the package how its contents use
that space, from the element's own width; prefer intrinsic grid or flex layout. For a
breakpoint, make the element a query container and put the conditional rules on its
descendants, since a rule for the element itself inside that query follows the nearest
container above it.

## Travel and history

Link to a place on the page with an ordinary fragment link; Leaf clears any panel
covering the page and opens whatever holds the element. A fragment can also name a
part of a widget by the widget's id and a key
([module-reading.md, "Following a reference"](module-reading.md#following-a-reference)).
A widget that opens the part a
fragment names reads it with `elementById(hash)`
([module-reading.md, "Reading the page"](module-reading.md#reading-the-page)).

Before Leaf travels to a target, such as a comment's anchor, it reveals the target as
the browser's find-in-page does: it opens each closed `<details>` holding it, and fires
`beforematch` at each element holding it that is `hidden="until-found"`, then removes
that attribute. It also opens a closed popover holding the target. A widget that folds
content hides it with `hidden="until-found"` and opens it on `beforematch`, as `lf-tabs`
does for a panel, so the browser's find reaches it too; print shows it open. Take a
folded element that is itself a Tab stop out of the Tab order, since the fold hides
only what it holds. Where the reveal replaces one view with another, Leaf places the
target at once rather than scrolling from the old view's reading position. It reads a
replaced view from a sibling of the element revealed that is `hidden` once that
element's `beforematch` listeners have run: Leaf hides the member a `views` widget
leaves (`module-state.md`, "State only this tab keeps"), and any other widget sets
`hidden` on the view it leaves in its listener. A widget that keeps the box of
what it hides, as one that stacks its views in one cell does, may set
`content-visibility: visible` with `visibility: hidden` on it; the browser's find then
skips it, but Leaf's travel still opens it. Leaf waits for the `updateComplete` of each
Lit element holding what it revealed before placing the target, so a widget whose view
switch finishes later extends its own `updateComplete`.

Leaf writes the page's history entries, and a widget writes none: one whose members
are the page's views says so, and Leaf adds an entry for each switch between them
(`module-plain-elements.md`, "The page's views"). Leaf keeps where the user was on each
entry, and Back, Forward and a reload return them there. An entry a press adds says the
press takes the user somewhere, as a link's does, so its result may scroll away the
control pressed. Where an entry's fragment still names a place the page doesn't show
once its view is open, Leaf reveals that place and lands there.

## Motion

Animate with `motion(element, keyframes, ms, pseudoElement?)`; a disclosure can animate
its `::details-content` without a wrapper. `motion` returns `null` for a user who asked
for less motion, and before `body[data-lf-presented]`; treat that as a finished
animation. Where a module must branch on the preference itself, as for the `behavior`
of a smooth `scrollTo`, it reads the `prefers-reduced-motion` media query.
Animate only to help the eye follow a box from where it was to where it is, and draw a
result the module already has during the gesture, not after a delay.

A package's stylesheet animates with a `transition` or an `animation`. Leaf turns the
sheet's transitions off until the page is presented (`module-authoring.md`, "Startup
and presentation"), though an `animation` plays as soon as its rule matches. For a
user who asked for less motion, Leaf turns the transitions off and ends the
animations at once. `element.animate` has neither guard, so it plays before the page
is presented and for that user.

A widget removing an item, or returning a retained frame from an editor to its
reading, takes the time of its fold from `--lf-motion-fold` rather than choosing a
number (`package-themes.md`, "Theme tokens"). The
library's [`motion-timing.js`](../../../browser/runtime/lib/motion-timing.js) reads a
token's time in milliseconds.

`backgroundFlash(element)` gives an element a brief yellow tint that fades to its
own background, and tints each box inside it that paints a background of its own too.
It lasts as long as Leaf's own arrival tint, as on a newly arrived message.

## Notices and spoken words

To announce words already on screen, dispatch an `lf-announce` event on the window
with the words as its `detail`:
`window.dispatchEvent(new CustomEvent("lf-announce", { detail: words }))`. Leaf says
them in its live region, and a page without Leaf leaves them unsaid. To tell a
listener which keys act next, as after a card is grabbed, give `detail` as
`{ words, rows }`, where `rows` holds the command rows that act (`module-input.md`,
"Command rows"). After the words Leaf names each row's keys and title, such as
`Escape cancel`, leaving out a row no key would run as the words are said.

An `lf-error` event, dispatched the same way, tells the user that something they did
has not taken, such as a value the server refused (`module-plain-elements.md`,
"`lf-error`").

A `data-lf-quiet` attribute gives an element words screen readers say at its start,
but the screen doesn't show: Leaf writes them there while the attribute stands, and
takes them away with it. The words stand in a first child of class `lf-quiet`, which
takes no room. Set the whole quiet word each time. Leaf writes
quiet words for elements it marks as rewritten, changed or reported, so declare them only
on parts the module builds or owns, such as a code line or a suggestion's slot. A page
without Leaf, whose theme would leave them on screen, writes none. Where a control's
quiet words are all its face leaves unsaid, its preview reads them alone, as a check's
verdict; a widget whose quiet words the page shows another way, as a column's head
shows each cell's run, declares the control's `lfPreview` returning `false`
(`module-previews.md`).
