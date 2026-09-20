# Escape unwinds a hierarchy, not a history

## The contract

Every state a reader can reach has one canonical keyboard route down to it. Escape is
that route in reverse: each press undoes the last step of the canonical descent, in the
order the hierarchy defines, until the reader is back in the document.

The guarantee is stated over the hierarchy rather than over the reader's history. Leaf
does not record how a reader arrived, so Escape behaves the same from every route. A
mouse click and a Tab are arbitrary jumps into the hierarchy rather than descents
through it, and they get the same unwind as the canonical route; they are owed no
return to the control they landed on.

This is what Leaf guarantees to a reader, and the sentence that decides any case:

> The canonical keyboard route down to a state is matched, step for step, by the Escape
> route back out of it.

## The hierarchy

Outermost to innermost. A press descends when it puts up a level that was not there;
everything else is lateral.

1. **The document.** The reader's position in the authored page: their reading
   position, and the destinations they can stand on — a heading, an Ask, an option
   inside an Ask, any authored control. This is the floor. Escape's job ends here.
2. **Page-side state**, put on without entering chrome: a selection, a captured target,
   an unfolded margin cluster, the page composer.
3. **Auxiliary surfaces**: the Threads panel and the trays.
4. **Layers of a surface**: the panel's narrowing or find query.
5. **Native layers**: a margin card, the versions menu, a modal dialog.
6. **Boxes**: a composer, a reply box, a find box, which their surface contains.

Bounded interactions — the Go-to sequence, the target chooser, page search, reactions,
draw and design mode — own the keyboard while they stand and unwind themselves. They
are not levels of this hierarchy.

### Ordering: containment before kind

Levels alone do not order two things standing at once, because a reader inside the panel
may have left a selection on the page behind them. The rule is containment first:

- A step rooted **inside** the surface that contains focus comes before that surface.
- The surface comes next.
- A step rooted **outside** that surface comes after it.
- Kind order — selection, tray, narrowing, panel, page — applies only among siblings at
  one level.

Without this rule, Escape from a thread in the panel clears a selection the reader left
on the page, which is a level they are not in. `escapeOrder` already computes
containment for the current frame's surface; the rule generalizes it to the surface that
contains focus.

### Descending, lateral, and the presses that are both

- **Descending**: `g T`, `c`, `?`, `g V`, Enter on a marker, `/`, Enter into a reply box.
- **Lateral**: `t` and `a` walking from one thread or Ask to the next, Tab, scrolling,
  and replacing one auxiliary surface with another (`g A` from Threads).
- **Both**: a walk step that reaches a thread or Ask with no place on the page has to
  open the panel to get there. It descends for the surface and moves laterally for the
  place: the panel comes off on the way out, and the landing is the reader's position in
  the document, not the thread the walk came from.

A margin card is hoisted into the browser's top layer while anchored to a paragraph. It
counts as chrome for "which surface contains focus", and as page-anchored for "where the
reader lands".

## Where Escape lands

Each step lands at the parent of what it closed: a box at its container, a standing at
its floor, a surface at the document.

Landing in the document uses one register, which holds the reader's position in the page
and nothing else:

- It is written when focus leaves the page for chrome or a layer.
- It holds an **identity** — a section id and quote, as `captureRegion` does — not a
  node, so a revision or a repaint that replaces the node does not strand it.
- It is read when a step would otherwise land the reader on chrome.
- It lands by focusing the reading block and blurring it, never `letGo()`: focus then
  blur keeps the sequential focus navigation position, so the reader's next Tab
  continues from where they are, while `document.body.focus()` resets it to the skip
  link.

A chrome control — the Threads toggle, a margin marker, a mark's note, a tray row, a
margin option row — is never a landing.

The register holds the position at the moment of closing, not the destination the press
displaced. A walk moves focus and scrolls the page together; returning focus to where
the walk began, without the scroll, puts the reader's focus off screen and shows them
nothing. Escape closes surfaces; it does not rewind movement through the page.

## What this gives up

Each of these is a rule the reader can learn, and each is a case the current model gets
right by remembering:

1. A surface the reader already had open closes on the way out, because no state
   distinguishes one this press opened from one it found. A note pressed with Threads
   open costs Threads on the way back out.
2. `g A` from Threads leaves Threads shut afterwards, because surface replacement is
   lateral.
3. A press that opens a container only to hold its content costs two Escapes rather than
   one: `c` from the page opens Threads and focuses the page box, and the box and the
   panel come off separately.
4. A walk is not rewound. Heading, `a` to an Ask, `t` to a card, two Escapes: the reader
   lands in the document where they now are, not back at the heading.
5. A control reached by Tab or by click is not returned to.

## Why

Every change to this area since the layer stack landed has been an attribution fix —
which press owns which surface — and the frame descriptor has grown a field per case:
`standing`, `surface`, `ownEntry`, `handsOn`, `older`, `press`. Six such changes landed
in three days and one more is deferred. Attribution is history kept consistent with a
present that other routes keep changing underneath it: a walk step opens the panel, a
send exchanges the composer for a card, a card is exchanged for the panel, a modal
re-shows a popover. Each new route is a new case.

A hierarchy has no attribution to keep consistent. It costs the five behaviours above
and removes the category.

## The plan

### Phase 1 — containment before kind

Order Escape steps by containment of the surface holding focus, then by kind, with the
frames still in place. This is an improvement on its own — it fixes the selection case
above — and it de-risks the deletion, because the ladder has to carry the whole load
afterwards. Touches `keyboard/register.js` (the STACK order and `rung`) and
`keyboard/dispatch.js` (`escapeOrder`).

### Phase 2 — the register

Add the reading register: written on focus leaving the page, held by identity, landing
by focus-then-blur. Route the ladder's landings through it, starting with the panel's
close, which today hands focus to the toggle. Touches `keyboard/layer-stack.js`
(`restoreReturnPlace`'s reading branch is the model), `thread-panel.js`, and the rungs
that land on chrome.

### Phase 3 — delete the frames

Remove `returnFrame` from every row that declares one, and with it: `invoke`'s frame
half and adoption, per-press origins (`pressOrigin`, `readingPlace`, `currentOrigin`,
`handsOn`), press identity and attribution (`openedByThisPress`, `auxiliaryOpened`),
`heldStanding`, the escape census (`older`), and `ownEntry`. Keep the native layer stack
with its suspension rule, the STANDING scope, the fallback ladder, and the reading
restore. Touches `keyboard/layer-stack.js`, `keyboard/dispatch.js`, `navigation.js`,
`asks/view.js`, `margin-projection.js`, `thread-panel.js`, `composing/*`,
`conversation/*`, `version.js`, and the two packaged widgets that declare a frame
(`lf-options.js`, `lf-diff.js`).

### Phase 4 — words

The shortcut bar reads its Escape wording off the current frame. Without frames it reads
off the ladder, which already says "close threads", "back to list", "show all",
"dismiss conversation". Two phrases need a home: the generic "back" a frame supplied,
and "back to the page" for a landing in the document.

### Phase 5 — tests

About thirty tests pin exact landings from the attribution work. Rewrite them to the new
contract rather than preserving them. Add the probe's assertions to every journey: the
blurred landing block, whether it is on screen, the scroll position, and where the next
Tab goes.

## Issues to expect

- **The probe lies by default.** A blurred landing reads as `body` whatever block it
  landed on, and nothing records scroll, so an off-screen return looks like a success.
  The probe must record the blurred element, whether it is on screen, `scrollY`, and the
  next Tab's landing. Most journeys start at scroll 0, where "reading position" and "top
  of the document" coincide — the probe needs journeys that start scrolled.
- **Pointer light dismiss.** The register must fire from Leaf's own Escape steps and not
  when a click dismisses a popover, or the click's own landing is overridden. Telling
  those apart today uses the pointerdown reading that phase 3 deletes; keep that much.
- **The card stays Leaf-intercepted.** The browser returns focus to a popover's invoker,
  which this contract says not to do, so Leaf keeps a step over the card and lands on the
  register instead. "The browser gives it free" does not apply here.
- **Revisions under the register.** A revision replacing the node the register holds must
  not land the reader on `body`; that is what holding an identity is for, and it is the
  case most likely to be missed, since it needs the page to change while a surface stands.
- **Reply boxes in a card.** With the box frames gone, the step that takes focus from a
  card's reply box back to its thread must come from the text-entry scope rather than the
  Page Map's step. Phase 1's containment rule should produce that; if it does not, the
  STACK order needs one edit.
- **Touch and keyboard-equipped tablets.** There is no Escape on touch, so none of this
  fires; on a tablet with a keyboard, a landing in the document is blurred, so there is
  no focus ring anywhere after Escape. Screen-reader users hear a control's name on an
  invoker restore and nothing on a blurred landing — worth one VoiceOver pass.
- **Packages.** `returnFrame` is a row field a package may declare; two bundled widgets
  use it. The public contract promises only "Escape means one step back at every depth",
  so the prose survives and the field goes.
- **Sequencing against PR 858.** That PR records which press opened the panel, which
  phase 3 deletes. It fixes live bugs, so land it first and let this branch remove it;
  do not hold it behind this work.
