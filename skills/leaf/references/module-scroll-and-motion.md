# Scrolling and motion

Read with [module-authoring.md](module-authoring.md), which holds what every behavior
module owes.

## Scrolling

### Reading regions

A pane widget declares `x-reading-role: pane` and `x-content: markup`, and holds one
body element, with an optional native `header` before it and `footer` after. Whether a
pane's body scrolls is the workspace Layout's decision (`layouts.css`), not the
module's, and either way the module registers the body as a reading region, below.

While the workspace fills the window, the Layout sets `--lf-full-height: 1` on `main` and
on a grid of panes, telling their children they have a definite height to fill. A
widget keys its rules for that case on `@container style(--lf-full-height: 1)`, which
reads its parent, and fits what it shows to the height. It declares
`--lf-holds-height: 1` on each part that scrolls within it, and sets
`--lf-full-height: inherit` on each box that passes the height down, as a playground
does to its panes. An `lf-ask` passes it to its answering widget, and page tabs to a
tab that is one block. The property doesn't inherit, so a widget nested in a section, or
in a tab of several blocks, is not told and grows with its content.

A module that builds its own panes, such as a playground's controls beside its preview,
marks each generated box `data-lf-reading-role="pane"` and `data-lf-generated`, with a
header, a body and a footer, and draws the frame around them itself. Keep the package
theme to placement within the pane, such as track sizes, and don't copy the Layout's
full-height rules. Generate plain boxes rather than `lf-pane` elements, which the render
gate expects to find in the page's file.

A module can generate a track beside its main content, such as a playground's controls
beside its preview. Mark it `data-lf-track`, and the Layout keeps it visible while the
window scrolls the taller content beside it, as with a sidebar page's track. When the
module stacks the track with the content, as on a phone, it declares
`--lf-track-scroll-behavior: flow` on the track's parent, and the track scrolls with
the page. Register the track as a reading region, since it may scroll.

A horizontal scroll surface uses the shared `scroll` class on its actual
viewport and declares overflow in its CSS. The class supplies containment. Leaf adds
keyboard access and continuation cues, inspecting these surfaces for overflow instead
of reading every descendant's styles. A reading region's body receives this class when
it registers; its CSS still decides whether the region scrolls or flows.
Sticky headers set `--lf-head-inset: 0px` beside their `position: sticky` rule so
keyboard focus counts the header's own inset as visible.

Register the pane's body, and any other box the widget may scroll, with
`registerReadingRegion({id, host, body})` inside `whileConnected`, returning the
function it gives back as the cleanup. `body` is the box that may scroll, and `host` the
pane around it, so focus in the pane's header counts as being in the pane. Leaf then
keeps the user's place in the box. Registering an id that another live region holds
throws, so a widget whose parts scroll independently registers each with an id from
`compoundReadingRegionId(owner, localName)`.

Give `body` a scrolling overflow (`auto` or `scroll`) only on an axis where its
content can outgrow it. A scrolling body bounds what stands in it, such as the card of
a comment on its contents, so a body sized to show everything it holds, as a
screenshot fitted to its box is, declares `visible` or `clip`, or `hidden` where it
keeps a `scrollbar-gutter` across states.

`scrollerFor(element)` returns the box that scrolls an element, its region's or the
page's (`pageScroller`). `regionScrollBehavior(node)` is `"bounded"` while the region's body
scrolls itself, and `"flow"` otherwise.

When a change hides or shows regions, such as switching tabs, run it through
`preserveReadingRegions(owner, change)`, so Leaf restores the user's place in the
regions shown once `change`'s promise resolves. A region that shows one subject of
several at a time, as a trace's saved tree shows one checkpoint, replaces its body's
contents inside `showReadingSubject(id, subject, render)`, and the user returns to their
place in each subject. `watchReadingRegionTransitions(listener)` hears these changes and
any shift in a region's scroller or width; `runtime/reading-regions.js` describes them.

### Holding the reader's place

`heldGrowth(element, change)` postpones one size-changing update while it would move
content the user is reading. It calls `change` immediately when no hold is needed;
otherwise it waits until the growth is out of view or the reading is interrupted.
The returned function cancels the pending change. When a user's own gesture requests
that change, cancel the hold and apply the change in that gesture.

When a widget redraws or resizes content where the user is reading, keep their place
with `placeKeeper(scroller, {items, identity})` rather than restoring `scrollTop`.
`items` selects the nodes that can mark a place, and `identity(node)` returns the key
each is drawn under, so a keyed redraw hands the place to the replacement. Wrap one
synchronous change, which must not scroll anything itself, in `around(mutate)`. For a
change spanning tasks, call `const hold = take()` before and `finish(hold, following)`
after; the keeper holds the place frame by frame while `following()` is true.

A widget that hides a view and shows it again later keeps the place as
`capturePlace()`, a landmark in the page's words, and returns to it with
`restorePlace(place)` however the page has moved since.

A list fed by the log or the clock, such as a feed of reports, shouldn't push the text
the user is reading. Build `new HeldReading(this, region, changed)`, where `region()`
returns the nodes the list draws into and `changed()` redraws the widget. Before each
draw, pass `hold()` the reading as a value that is `===` the last one only when nothing
changed, such as `JSON.stringify` of the rows, and draw what it returns: the new
reading, or the last one while the region's growth would move what the user sees.
`changed()` is called once that growth would be out of sight. `show()` lets the new
reading in and redraws, for a "Show new" control, and `release()` lets the next one in.

### Scrolling to a destination

To take the user somewhere, call `scrollIntoView(target, {block, behavior})`, which
reveals the target inside any box that clips it, then places it in each reading region
around it; `block` defaults to `start`. To bring an item into its own strip or list and
leave the page where it is, pass that box as `within`. For a vertical move that keeps
the sideways scroll, use `scrollIntoReadingBand(target, holder, block, behavior)`, where
`target` is an element or a Range and `holder` the element whose regions contain it.
Unlike native `Element.scrollIntoView`, both stay inside a live sample. Use them only
for a deliberate move; focusing a visible control or redrawing keeps the scroll.

A landing keeps the target's `scroll-margin` clear on every side, so a focused
control's ring shows. `fitsWhole(target)` says whether the target and those margins
fit, so a widget can bring in a heading or label with an item where there is room, and
the item alone where there is not.

To set a box's scroll position, use `setScroll(box, {top, left, behavior})`, also
available from `portable-api.js`. It defaults to `instant` and updates Leaf's scroll
readers before that position paints, including writes during resize delivery. Smooth
scrolling reports its positions through the browser's scroll events.

`scrollLimit(box)` is how far a box scrolls down, and `atScrollEnd(box)` whether it is
there. `landingInsets(scroller)` reads a scroller's `scroll-padding`.
`shownWindow({within, gap, across})` is the window's visible rectangle clear of Leaf's
fixed chrome, narrowed to `within` and inset by `gap`; with `across` (`{left, right}`),
only chrome standing across those columns takes room.

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

Leaf restarts `--lf-top` on every box that scrolls and doesn't stick, `overflow: hidden`
included, so a header inside one sticks at its top. A box a package makes scroll sets
`--lf-top: 0px` beside its `overflow`, so that holds from the first paint. A header
sticks below its scroller's top padding; to have it sit on the scroller's edge, set
`--lf-top-start` to minus that padding and `--lf-top: var(--lf-top-start)`. A scroller
with its own `scroll-padding` states it as `--lf-landing-room-start`. A box that only
clips, such as a card with rounded corners, uses `overflow: clip`, since a header inside
an `overflow: hidden` box scrolls away with the page.

### Headers over the document

`registerRootHeader(header)` contributes the actual border-box height of a header the
package places over the document. Independent contributions add, and resizing,
disconnecting and reconnecting the element update the total. Call its returned stop
when the header becomes local navigation. Only a header over the document belongs
here: a nested scroller uses the local sticky and landing inputs above. Packages own
where their headers are positioned; Leaf owns the aggregate root landing inset.

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
covering the page and opens whatever holds the element. A widget that opens the part a
fragment names reads it with `fragmentTarget(hash)`, which returns nothing for an id in
Leaf's chrome, in a message's markup, or on content a revision removed.

Before Leaf travels to a target, such as a comment's anchor, it reveals the target as
the browser's find-in-page does: it opens each closed `<details>` holding it, and fires
`beforematch` at each element holding it that is `hidden="until-found"`, then removes
that attribute. It also opens a closed popover holding the target. A widget that folds
content hides it with `hidden="until-found"` and opens it on `beforematch`, as `lf-tabs`
does for a panel, so the browser's find reaches it too. A widget that switches view sets
`hidden` on the view it leaves, a sibling of the one it opens, before its `beforematch`
handler returns; Leaf reads that as a replaced view and places the target at once rather
than scrolling from the old view's reading position. A widget that keeps the box of
what it hides, as `lf-visual-review` stacks its cases in one cell, may set
`content-visibility: visible` with `visibility: hidden` on it; the browser's find then
skips it, but Leaf's travel still opens it. Leaf waits for the `updateComplete` of each
Lit element holding what it revealed before placing the target, so a widget whose view
switch finishes later extends its own `updateComplete`.

A widget that adds history entries uses `pushEntry(url)` and `replaceEntry(url)`. An
entry a press adds says the press takes the user somewhere, as a link's does, so its
result may scroll away the control pressed; `replaceEntry` only renames the entry the
user is on. To
restore the page itself when the user goes Back or Forward to one of its entries, call
`claimTraversals(claim, {signal})`, where `claim(url)` returns a function that restores
the page for an entry of the widget's, or nothing. The handler may be asynchronous.
When it only reveals the destination view, it resolves to `false`, and Leaf restores
the entry's saved viewport after the view is shown. Otherwise the handler owns
viewport placement.

## Motion

Animate with `motion(element, keyframes, ms, pseudoElement?)`; a disclosure can animate
its `::details-content` without a wrapper. `motion` returns `null` for a user who asked
for less motion, and before `body[data-lf-presented]`; treat that as a finished
animation. `reducedMotion()`, `scrollBehavior()` and
`onMotionPreferenceChange(listener)` read the preference where a module must branch on
it. Animate only to help the eye follow a box from where it was to where it is, and draw
a result the module already has during the gesture, not after a delay.

A widget removing an item asks `foldDuration()` each time rather than choosing a
number, and a retained frame returning from an editor to its reading uses the shorter
`returnDuration()`.

`foldBlock(element)` animates a block from its ordinary CSS size to zero, margins,
padding, borders and minimum size included. It returns an Animation, or `null` where it
retires the block at once, as under reduced motion. Retire the block's state at once,
since the effect keeps its pixels drawn until the fold finishes; keep its ordinary
sizing rules while it leaves, and cancel the effect if retirement is reversed.

`backgroundFlash(element, ms)` gives an element a brief yellow tint that fades to its
own background. `flashDuration()` is how long Leaf's own arrival tint lasts, as on a
newly arrived message.

## Notices and spoken words

`notice(message)` shows a moment's news in Leaf's panel, in the italic Leaf sets its
own words in, and announces it to screen readers, such as a view the widget switched
to. A recorded gesture is acknowledged by
the `says` its dispatch gives (`module-state.md`, "The widget controller"). News not
caused by the user passes `{background: true}` and waits behind what the user just did;
`{announce: false}` only shows it. `announce(message)` only announces, for words already
on screen: it dispatches an `lf-announce` event on the window carrying `message` as its
`detail`, which Leaf says in its live region and a page without Leaf leaves unsaid.

`raiseError(message)` tells the user a gesture failed, such as a value the server
refused, and the Leaf panel shows it until they have dealt with it. Its handle's
`clear()` takes the error down once it no longer holds. Use it for failures only.

A `data-lf-quiet` attribute gives an element words screen readers say after its leading
`<strong>` title but the screen doesn't show: Leaf writes them there while the attribute
stands, and takes them away with it. Set the whole quiet word each time. Leaf writes
quiet words for elements it marks as rewritten, changed or reported, so declare them only
on parts the module builds or owns, such as a code line or a suggestion's slot. A page
without Leaf, whose theme would leave them on screen, writes none.
