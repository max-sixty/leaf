# Scrolling and motion

Read with [module-authoring.md](module-authoring.md), which holds what every behavior module owes. This file covers reading regions and scrolling, travel and history, motion, and notices and spoken words.

## Scrolling

### Reading regions

A pane widget declares `x-reading-role: pane` and `x-content: markup`, and holds one
body element, with an optional native `header` before it and `footer` after. Leaf lays
out every pane the same way from the first paint. Whether a pane's body scrolls is the
workspace Layout's decision (`layouts.css`), not the module's. In a large enough window
the workspace fills the window's height, and a pane that is its body, or a direct cell
of it, scrolls its body; elsewhere a pane grows with its content. Either way, the
module registers the body as a reading region, below.

While the workspace fills the window, the Layout sets `--lf-full-height: 1` on `main` and
on a grid of panes, telling their children they have a definite height to fill. A
widget keys its rules for that case on `@container style(--lf-full-height: 1)`, which
reads its parent, and fits what it shows to the height. It declares
`--lf-holds-height: 1` on each part that scrolls within it, and sets
`--lf-full-height: inherit` on each box that passes the height down, as a playground
does to its panes. The property doesn't inherit, so a widget nested in a section or tab
is not told and grows with its content.

A module that builds its own panes, such as a playground's controls beside its preview,
marks each generated box `data-lf-reading-role="pane"` and `data-lf-generated`, with a
header, a body and a footer, and draws the frame around them itself. Keep the package
theme to placement within the pane, such as track sizes, and don't copy the Layout's
full-height rules. Generate plain boxes rather than `lf-pane` elements, which the render
gate expects to find in the page's file.

Register the pane's body, and any other box the widget may scroll, with
`registerReadingRegion({id, host, body})` inside `whileConnected`, returning the
function it gives back as the cleanup. `body` is the box that may scroll, and `host` the
pane around it, so focus in the pane's header counts as being in the pane. Leaf then
keeps the user's place in the box. Registering an id that another live region holds
throws. A widget whose parts scroll independently registers each, with an id from
`compoundReadingRegionId(owner, localName)`.

`scrollerFor(element)` returns the box that scrolls an element, its region's or the
page's (`pageScroller`). `readingPosture(node)` is `"bounded"` while the region's body
scrolls itself, and `"flow"` otherwise.

When a change hides or shows regions, such as switching tabs, run it through
`preserveReadingRegions(owner, change)`, so Leaf restores the user's place in the
regions shown once `change`'s promise resolves. A region that shows one subject of
several at a time, as a trace's saved tree shows one checkpoint, replaces its body's
contents inside `showReadingSubject(id, subject, render)`, and the user returns to their
place in each subject. `watchReadingRegionTransitions(listener)` hears these changes and
any shift in a region's scroller or width; `runtime/reading-regions.js` describes them.

### Holding the reader's place

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

To take the user somewhere, call `scrollIntoView(target, {block, behavior})`. It
reveals the target inside any box that clips it, then places it in each reading region
around it; `block` defaults to `start`. For a vertical move that keeps the sideways
scroll, use `scrollIntoReadingBand(target, holder, block, behavior)`, where `target` is
an element or a Range and `holder` the element whose regions contain it. Unlike native
`Element.scrollIntoView`, both stay inside a live sample. Use them only for a deliberate
move; focusing a visible control or redrawing keeps the scroll.

`scrollLimit(box)` is how far a box scrolls down, and `atScrollEnd(box)` whether it is
there. `landingInsets(scroller)` reads a scroller's `scroll-padding`.
`shownWindow({within, gap})` is the window's visible rectangle clear of Leaf's fixed
chrome, narrowed to `within` and inset by `gap`.

### Sticky headers

A sticky header has a stated height, sticks at `var(--lf-top)`, and adds its height to
`--lf-top` for what lies below it. A custom property can't read itself, so the holder
copies the incoming value to a second name:

```css
.file { --lf-top-outer: var(--lf-top); }
.file > .head { position: sticky; top: var(--lf-top); block-size: var(--head-h); }
.file > .rows { --lf-top: calc(var(--lf-top-outer) + var(--head-h)); }
.file .row { scroll-margin-top: var(--head-h); }
.file > .head { --lf-head-inset: var(--head-pad); }
```

The rows' `scroll-margin-top` makes a scroll to a row land below the header; a focused
row lands there without it. `--lf-head-inset` says how far below the header's top edge
its controls sit, so a revealed control lands exactly there. Put the stacked value on a
box that doesn't scroll itself.

Leaf restarts `--lf-top` on every box that scrolls and doesn't stick, `overflow: hidden`
included, so a header inside one sticks at its top. A box a package makes scroll sets
`--lf-top: 0px` beside its `overflow`, so that holds from the first paint. A header
sticks below its scroller's top padding; to have it sit on the scroller's edge, set
`--lf-top-start` to minus that padding and `--lf-top: var(--lf-top-start)`. A scroller
with its own `scroll-padding` states it as `--lf-landing-room-start`. A box that only
clips, such as a card with rounded corners, uses `overflow: clip`, since a header inside
an `overflow: hidden` box scrolls away with the page.

### Sideways scrollers and container queries

Give a box a package scrolls sideways the class `lf-text-scroller`, and Leaf leaves room
below its last line for an overlay scrollbar.

The page decides how big a Leaf element's box is; the package decides how its contents
use that space, from the element's own width. Prefer intrinsic grid or flex layout. For
a breakpoint, make the element a query container and put the conditional rules on its
descendants. A rule for the element itself inside that query follows the nearest
container above it, which may be `body`, so move what changes to an inner box.

## Travel and history

Link to a place on the page with an ordinary fragment link; Leaf clears any panel
covering the page and opens whatever holds the element. A widget that opens the part a
fragment names reads it with `fragmentTarget(hash)`, which returns nothing for an id in
Leaf's chrome, in a message's markup, or on content a revision removed.

Before Leaf travels to a target, such as a comment's anchor, it dispatches `lf-reveal`
on each ancestor of the target and the target itself, outermost first, with
`detail: {target, mayReveal, present, replacedView}`. A widget that folds content opens
whatever holds `target`. An asynchronous listener checks `mayReveal()` after each wait,
since it turns false once the user moves on. A widget that switches view to show the
target, as `lf-tabs` does, calls `replacedView()` during the event. A listener passes
later layout work to `present(promise)`, which Leaf waits for before placing the target.

A widget that adds history entries uses `pushEntry(url)` and `replaceEntry(url)`. To
restore the page itself when the user goes Back or Forward to one of its entries, call
`claimTraversals(claim, {signal})`, where `claim(url)` returns a function that restores
the page for an entry of the widget's, or nothing. Other traversals return the user to
the focus and scroll Leaf recorded.

## Motion

Animate with `motion(element, keyframes, ms)`, not `element.animate`. The stylesheet's
reduced-motion rule doesn't reach Web Animations, so `motion` returns `null` for a user
who asked for less motion, and before `body[data-lf-presented]`; treat that as a
finished animation. `reducedMotion()`, `scrollBehavior()` and
`onMotionPreferenceChange(listener)` read the preference where a module must branch on
it. Animate only to help the eye follow a box from where it was to where it is, and
draw a result the module already has during the gesture, not after a delay.

A widget removing an item asks `foldDuration()` each time rather than choosing a number;
it reads `--lf-motion-fold` on the document root, where every `--lf-motion-*` duration is
set, even for an element in a shadow tree.

`backgroundFlash(element, ms)` gives an element a brief yellow tint that fades to its
own background.

## Notices and spoken words

`notice(message)` shows a moment's news in Leaf's status line and announces it to screen
readers, such as confirming a gesture the widget recorded. News not caused by the user
passes `{background: true}` and waits behind what the user just did; `{announce: false}`
only shows it. `announce(message)` only announces, for words already on screen.

`quietWord(element, word)` gives an element words screen readers say after its leading
`<strong>` title but the screen doesn't show; pass the whole quiet word each time, or an
empty one to remove it. Leaf writes quiet words for elements it marks as rewritten,
changed or reported, so write them only on parts the module builds.
