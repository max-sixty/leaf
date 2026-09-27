/* The declarations a stylesheet has to read, painted onto the elements that make them.

   `markDeclared` writes each registry declaration a selector needs as a `data-lf-`
   attribute, and an authored occurrence's override in its place. The two tables say
   which declarations hold where: in the page, and anywhere a widget renders, a
   message's frozen markup included. */
import { registry, tagsDeclaring } from "./registry.js";
import { PAGE_PAINT_ATTRIBUTE, elementsIn } from "./presentation.js";
import { holdBounds } from "./bounds.js";

// The declarations a stylesheet has to read and cannot. Three of them today: one about
// the space a widget is given and two about how it participates in content, and none of the
// three is something a selector can derive from the element in hand or look up.
//
// Which widgets may stand wider than the column is the first. Prose is set to a measure
// and stays at it; a board's columns and a diagram's graph are as wide as what they hold,
// and a page carrying one had to be either a cramped board or a page whose every
// paragraph was widened to suit it. Neither is a choice a page should have to make, so
// the widget declares its capacity (x-space) and the theme spends the room the layout
// resolved by the CSS shell (--lf-room). `wide` uses the shared evidence cap;
// `available` uses all remaining room. Internal arrangement remains package-owned.
//
// Whether the widget is set among the words around it is the second (x-inline). What
// reads it is the pair of selectors asking whether a suggestion slot or a variant holds
// block content, which is HTML's phrasing content inverted: a custom element is in no
// closed platform set, so any widget in one of those makes it a block — an inline widget
// included, which is the one wrong answer the inversion gives. The exclusion that fixed
// it was four widget names, and a bundled chip's tag therefore stood in the integrated
// theme, saying nothing at all about the next layer's inline widget. It is one marker
// now, data-lf-inline, and an inline widget from any layer joins by declaring.
//
// Whether the widget quotes what it holds is the third (x-exhibit). An exhibit is a
// mention, not a use, so every rule saying "this takes input" — the hand, the lift, the
// joined shape, the reserved strips, the hover wash — stands down inside one. The
// declaration is the tag's and the question is the occurrence's, which is the shape
// quoted() has too: whether this element sits inside an exhibit. So the mark goes on the
// exhibit and the rules exclude what stands under it. That is the descendant half of the
// question — quoted() answers for the element itself as well — and it is the half these
// rules need while the tag they key on, lf-options, is not itself an exhibit. A layer
// that declared one to be would have to say so in its own rules. Ten of those rules spelled lf-sample before: a bundled
// tag, saying nothing about a project's own exhibit. quoted() still asks the registry
// rather than this paint, which is the arrangement and not an oversight — the
// declaration is the one representation, and the mark is how a stylesheet, which cannot
// read a registry, asks it the same thing.
//
// An attribute, because the theme cannot read the registry — the same arrangement x-says
// already has with data-lf-said. It is the
// runtime's paint on the page's own element, so it joins PAGE_PAINT_ATTRIBUTES: the
// version diff reads the live DOM against a file nothing has painted, and an attribute
// missing from that exclusion list is a change the author never made. Written before the
// modules import, because the first two decide the box each module renders into and the
// third decides what may be drawn as pressable while they do. It lands a registry fetch
// after the first authored paint: the document is already useful, and these declarations
// progressively specialize its widget layout before those widgets upgrade. A message
// body cannot render before the registry is read. The root is marked alongside its
// descendants: a rebuild is handed a clone of the widget itself, and the fact is that
// widget's own.
//
// What separates the two tables is where each fact holds. x-inline is true of the element
// wherever it renders, a thread's message included, or a chip-led comparison quoted into
// a reply would stack there and nowhere else. So is x-exhibit: quoting is the element's
// own fact, and a sample carried into a reply is quoted there too. A page's widget
// renders in both places, and only one of the three changes meaning when it moves. The
// room x-space hands out is the document's, and a message is the one place a
// widget of the page's vocabulary renders outside the document, where the room is the
// panel's (see msgNode).
//
// Two more are facts of the element wherever it renders. x-bound says it holds its
// own height and scrolls inside it. A page occurrence overrides x-bound with data-bound,
// as data-width overrides x-space. x-reading-role is the structural role the theme lays
// out, so a package's differently named pane takes the same rules as lf-pane.
//
// A bound is more than paint: the block scrolls, so it is a reading region and an `end`
// bound follows its newest entry (bounds.js). Whatever paints a bound hands the block to
// `holdBounds` in the same pass, so a bound in a message's markup is held as surely as
// one in the page, from whichever pass painted it.
export const MARKED_ANYWHERE = Object.freeze({
  "x-inline": PAGE_PAINT_ATTRIBUTE.inline,
  "x-exhibit": PAGE_PAINT_ATTRIBUTE.exhibit,
  "x-bound": PAGE_PAINT_ATTRIBUTE.bound,
  "x-reading-role": PAGE_PAINT_ATTRIBUTE.readingRole,
});
export const MARKED_IN_PAGE = Object.freeze({
  ...MARKED_ANYWHERE,
  "x-space": PAGE_PAINT_ATTRIBUTE.space,
});

// `markDeclared` exposes a declaration such as x-space as paint, and CSS computes the
// room after claimed margins.
// A declaration an authored occurrence may override, and the attribute it is written as.
const AUTHORED = Object.freeze({ "x-space": "data-width", "x-bound": "data-bound" });

// What an entry declares for a painted key.
const declaration = (entry, key) => entry[key];

export function markDeclared(root, painted) {
  for (const key of Object.keys(AUTHORED))
    if (painted[key])
      for (const el of elementsIn(root, `[${painted[key]}]`))
        el.removeAttribute(painted[key]);
  for (const [key, attr] of Object.entries(painted))
    for (const tag of tagsDeclaring((entry) => declaration(entry, key))) {
      const declared = declaration(registry[tag], key);
      for (const el of elementsIn(root, tag))
        el.setAttribute(attr, declared === true ? "" : declared);
    }
  for (const [key, authored] of Object.entries(AUTHORED))
    if (painted[key])
      for (const el of elementsIn(root, `[${authored}]`))
        el.setAttribute(painted[key], el.getAttribute(authored));
  if (painted["x-bound"]) holdBounds(root);
}
