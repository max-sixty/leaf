# Scrolling and motion

Read with [module-authoring.md](module-authoring.md), which holds what every behavior module owes. This file covers reading regions and scrolling, travel and history, motion, and notices and spoken words.

## Scrolling

### Reading regions

A pane declares `x-reading-role: pane` and keeps `x-content: markup`: exactly one direct
body element between an optional native `header` first and an optional native `footer`
last. Leaf lays out every package's pane by the same rules from the first paint; its
module registers the pane's body as a reading region, below.

Whether a pane's body scrolls is the workspace Layout's decision (`layouts.css`). Where
the window is large enough, the workspace is full-height: it fills the window and gives
its body a definite height, so a pane that is the body or a direct cell of it may shrink
below its content and scrolls its body. A pane inside a section of the body, or inside
another pane's body, flows with what holds it, and elsewhere every pane takes its
content's height. A module measures no minimum and chooses no posture.

`--lf-full-height: 1` on a box says its children are given a definite height to fill; it
does not inherit. While the workspace is full-height, the Layout sets it on `main` for
the body and on a grid of panes for its cells. A widget given that height keys its rules
on `@container style(--lf-full-height: 1)`, which asks the widget's parent; it fits what
it shows to the height, so the reader moves through the workspace rather than scrolling
it, declares `--lf-holds-height: 1` on each part it scrolls within that height, and sets
`--lf-full-height: inherit` on each box that passes the height on to its parts, as a
playground does down to its panes. A widget deeper in the body, in a section or a tab, is
not told, and takes its content's height.

A module that composes regions out of boxes it generates, such as a playground's controls
beside its preview, gives those boxes the pane rules by marking them
`data-lf-reading-role="pane"` and `data-lf-generated`, with the pane grammar of one header,
one body and one footer. A generated pane scrolls its body where its widget passes the
height on to it, and its widget draws the frame around it: the workspace's hairline grid
joins only panes a page wrote. These attributes are the module's to write, never an
author's (`page check` refuses `data-lf-` markup). Keep the package theme to placement
inside that grammar, such as track sizes and chrome; a package copy of the full-height
rules is a second posture decision that drifts from the Layout's. Generate boxes rather
than `lf-pane` elements: those are authored words the render gate pairs with the file.

`registerReadingRegion({id, host, body})` binds a region's id to its host and to the body
that scrolls whenever the theme makes it scroll. Focus in a pane's header or footer
selects the pane through its host. It throws while another region holds the id, so
register it in `whileConnected` and return its cleanup there; an element that returns
claims the id again. Containment follows rendered slots, so native conversation parts
nominated into a shadow reader belong to the region registered around their outlets. A
compound widget whose parts scroll independently registers each, taking a stable id from
`compoundReadingRegionId(owner, localName)`.

`scrollerFor(element)` is the box that scrolls an element: its reading region's scroller,
or `pageScroller`, the document's. `readingPosture(node)` is `"bounded"` while the
region's body is its own scroller, and `"flow"` otherwise.

Leaf records the user's place in each region as they scroll and restores it when the
region's layout moves under them. A composition that hides or reveals regions, such as a
tab switch, runs the change through `preserveReadingRegions(owner, change)`, which awaits
the promise `change` returns before the visible regions' places are restored. A region
that shows one subject of several in turn, as a trace's saved tree shows one
checkpoint's elements, replaces its body's contents inside
`showReadingSubject(id, subject, render)`, and Leaf returns the reader to their place in
each subject. `watchReadingRegionTransitions(listener)` hears these changes, and returns
a function that stops it: `{phase: "shift", shifted}` whenever a shown region's scroller
or width changes, the window's height changes, or the page's width changes (an entry with
no region); `before` and `after` around `preserveReadingRegions`; and
`leaving` and `showing` around `showReadingSubject`.

### Holding the reader's place

A widget that re-renders or resizes content holds the user's place with
`placeKeeper(scroller, {items, identity})` rather than by restoring a `scrollTop`.
`items` is a selector for the nodes that can mark a place and `identity(node)` the key
each is rendered under, so a keyed re-render hands the place to the replacement. The
keeper's `around(mutate)` brackets one synchronous mutation, which moves no scroller
itself; `take()` and `finish(hold, following)` bracket a mutation that spans tasks,
following it frame by frame while `following()` is true. Use it also for a synchronous
change in the page scroller where native anchoring does not keep the focused control
still. `runtime/user-place.js` describes which node holds the place.

A widget that remembers where the user was reading, in a view it hides and shows again,
keeps a place rather than an offset: `capturePlace()` reads the page's place as a
landmark in its own words, and `restorePlace(place)` returns to it however the page has
moved since.

A region whose rows the log or the clock decides holds them back while their growth
would move what the user sees, with a `HeldReading` built with its widget:
`new HeldReading(this, region, changed)`, where `region()` returns the nodes the reading
draws and `changed()` draws the widget again. `hold(reading)` returns the reading to draw:
the new one where it is the first, equals the one drawn last, or would move nothing seen;
otherwise the one drawn last, until that growth would move nothing seen. `release()` lets
the next reading draw whatever it moves, and `show()` releases and draws now. The wait
continues across a return.

### Scrolling to a destination

`scrollIntoView(target, {block, behavior})` lands on a destination: it reveals the
target in inner overflow, horizontally by the nearest edge, then places it through its
enclosing reading regions. `block` defaults to `start` and accepts `center`, `end` and
`nearest`. For a vertical navigation that keeps sideways reading, use
`scrollIntoReadingBand(target, holder, block, behavior)`, where `target` is an element or
a Range and `holder` is the element whose reading regions contain it; `block` is `start`,
`center`, `end` or `nearest`. It places the target in the innermost region's reading band
and reveals it in enclosing regions, across shadow roots, without changing horizontal
offsets. Both stop at the current document, including inside a live sample, where native
`Element.scrollIntoView` can scroll the containing page; use them for an explicit
arrival, since entering visible controls and ordinary repainting keep the current
position.

`scrollLimit(box)` is the furthest a box scrolls down, and `atScrollEnd(box)` says whether
it stands there. `landingInsets(scroller)` reads the `scroll-padding` a scroller declares
on each edge. `shownWindow({within, gap})` is the `DOMRect` of the window the page shows,
clear of the chrome Leaf fixes to its edges, such as its panel at the foot, narrowed to the
rectangle `within` and inset by `gap`.

### Sticky headers

A sticky header, a sticky box over the top of its scroller, has a stated height, sticks at
`var(--lf-top)`, and adds its height to `--lf-top` for what it stands over. Its holder
passes the value it met on under a second name, since a custom property cannot read
itself:

```css
.file { --lf-top-outer: var(--lf-top); }
.file > .head { position: sticky; top: var(--lf-top); block-size: var(--head-h); }
.file > .rows { --lf-top: calc(var(--lf-top-outer) + var(--head-h)); }
.file .row { scroll-margin-top: var(--head-h); }
.file > .head { --lf-head-inset: var(--head-pad); }
```

The rows' `scroll-margin-top` has a landing on a row arrive below the header. Focus needs
nothing declared: a focused row lands below the headers stacked over it, and a control in
a stuck header counts as shown where it sticks. Leaf also reads what passes under
`--lf-top` as off screen, for read acknowledgement, arrival checks and chrome placement.
A header whose controls stand below where it sticks may say how far (`--lf-head-inset`),
so a control revealed from elsewhere lands exactly there. Put the stacked value on a box
that does not itself scroll.

Leaf starts `--lf-top` again on every box that scrolls and does not itself stick,
`overflow: hidden` included, so a header inside one sticks at that box's top. A box a
package makes scroll also states `--lf-top: 0px` beside its overflow, so the restart holds
from the first paint. A box that scrolls with `scroll-padding` of its own states that room
as `--lf-landing-room-start` beside its `--lf-top-start`. A header sticks below its
scroller's top padding; to have it stand on the scroller's top edge, state
`--lf-top-start` at minus that padding and `--lf-top: var(--lf-top-start)`. A box that only
clips, such as a card rounding its corners, uses `overflow: clip`: a `hidden` box is a
scroller, and a header inside it would scroll off with the page rather than stick at
the window's top.

### Sideways scrollers and container queries

A box a package makes scroll text sideways carries the class `lf-text-scroller`. An
overlay scrollbar paints over the box's lower edge and widens under the pointer, so while
the box scrolls, Leaf adds room for that bar below its last line.

A composition allocates a Leaf element's outer box. The package owns how the element's
contents use that allocation, based on its available inline size rather than the page
shell or a reading posture. Prefer intrinsic grid or flex layout. When the contents need a
discrete breakpoint, make the element a query container and apply the conditional rules
to its descendants. A rule for the host inside that block silently fails: an unnamed query
answers from the nearest ancestor container, and `body` is a container, so the rule
follows the page shell instead. Keep the host's own layout intrinsic, or put the
properties that change on a descendant layout box.

## Travel and history

A place on the page is an ordinary fragment link; Leaf follows it the way it travels to a
thread, clearing a panel that covers the page and opening whatever holds the element. A
widget that asks which of its parts a fragment names reads it with `fragmentTarget(hash)`,
as Leaf's own arrival does, so the widget opens the part the landing goes to: an id in
Leaf's chrome, in a message's markup, or on content a revision settled away names
nothing.

When Leaf travels to a target, such as a comment anchor or an ask, it first dispatches
`lf-reveal` on each ancestor of the target and the target itself, outermost first, with
`detail: {target, mayReveal, present, replacedView}`. A widget that folds content listens
for it and opens whatever holds `target`. `mayReveal` is the traveller's kept intent
(`module-input.md`, "Delayed work"): an asynchronous listener checks it after each wait. A widget replacing a
mutually exclusive visible view opens it and calls `replacedView()` synchronously during
dispatch, and travel places that destination at once; expanding content within the
current view reports no replacement. A listener joins later layout through
`present(promise)`, and travel waits for those promises and reads fresh geometry for its
final placement. `lf-tabs` is the worked example.

A widget that adds same-document history entries adds them with `pushEntry(url)` and
`replaceEntry(url)`. It places the page itself at Back or Forward to one of its entries by
claiming that traversal with `claimTraversals(claim, {signal})`: `claim(url)` returns the
function that places the page for an entry of its own, or nothing for any other, and
aborting `signal` withdraws the claim. Every other traversal returns the user to where
they left the entry: its focus, selection and offset where Leaf recorded them, else the
browser's saved offset. Where the element an entry's fragment names is no longer shown,
the traversal reaches the widget holding it shut as `lf-reveal` and lands on it, as a
followed link does.

## Motion

A module that moves something calls `motion(element, keyframes, ms)` rather than
`element.animate`. The stylesheet's reduced-motion guard reaches CSS animation and
transitions but not a Web Animations call, so `motion` is where a user who asked for
stillness is answered: it returns `null` under that preference and before
`body[data-lf-presented]`. A caller treats no animation and a finished one as the same
state. `reducedMotion()`, `scrollBehavior()` and `onMotionPreferenceChange(listener)`
answer the same preference where a module has to branch on it; the last returns a
function that stops listening. Spend a duration only on letting the eye follow a box from
where it was to where it is: a result the module can already draw is drawn in the
gesture rather than after a wait.

`foldDuration()` reads how long a unit takes to leave, from the document-root
`--lf-motion-fold` stylesheet input; a widget retiring one calls it each time rather than
choosing a number or caching a value. The `--lf-motion-*` time inputs accept CSS
calculations and are set on the document root, including when the animated element lives
in a shadow tree.

A temporary yellow cue calls `backgroundFlash(element, ms)`. It supplies only the starting
tint; the browser fades to the element's live CSS background, including any hover or
theme change during the cue, and it shares `motion`'s gates and cleanup.

## Notices and spoken words

`notice(message)` shows a moment's news in Leaf's status line and announces it to screen
readers, such as the acknowledgement of a gesture the widget recorded. News that arrives
without the user's gesture passes `{background: true}` and waits behind what the user just
did; `{announce: false}` shows it without announcing it. `announce(message)` only
announces, for words the screen already shows.

`quietWord(element, word)` gives an element a word screen readers say and the screen does
not show, placed after the element's leading `<strong>` title; an empty word removes it.
Pass the element's whole quiet word each time. Leaf writes the quiet word of an element it
marks as rewritten, changed by the user, or reported, so a module writes quiet words only
on parts it builds.
