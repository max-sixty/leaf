/* This module owns the shared readings of visible boxes and clipping, and the one
 * conversion from viewport boxes to document-positioned chrome. */
import { uiInside } from "./shadow.js";

/* Shared readings of the boxes the page actually shows.

   `shownBox` returns an element's own box or the union of the boxes its
   `display: contents` descendants paint. `shownParts` returns the visible elements on
   which an outline can be drawn. `shownRect` clips the result through scrolling
   ancestors and the viewport, stopping ancestor clipping at a fixed-position box.
   `clippedRect` applies that same clipping walk to a box measured some other way for an
   element, and `clippedContents` to a box measured from a Range, starting at the element
   that holds the Range and counting that element's own clip. Use:

   - `shownBox` for travel, bounds, and reading-position landmarks;
   - `shownParts` for Ask rings and element-anchor outlines;
   - `shownRect` for visible placement of floating chrome and key badges;
   - `clippedRect` for an element's box the caller has adjusted;
   - `clippedContents` when the subject has no element box of its own.

   Do not read `getBoundingClientRect()` directly when the target may generate no box.
   A `display: contents` element reports an origin-like zero rectangle that does not
   represent where its contents are. An area greater than zero is not enough for shown
   parts either: clipped note text and hoisted controls can have measurable boxes while
   remaining the wrong semantic target, which is why `shownParts` takes the bounded
   chrome question (`uiInside`). `unmarkableElements`, in the render checks, detects
   declared items with no visible part on which a mark can land. */
// Where the page's shell ends on the right — the far edge of the room the document has,
// which is what a margin resident is placed against and what the response surface may not
// overhang. Body's content box and not its border box, because the strip a standing panel
// or tray takes is a transparent border (theme.css says why it has to be one), so
// `getBoundingClientRect().right` is the window's edge rather than the page's. Read live
// rather than derived from a panel width, since a reader may have drawn the edge
// anywhere and the stylesheet decides whether the strip is taken at all.
export const shellRight = () => {
  const body = document.body;
  const { borderLeftWidth } = getComputedStyle(body);
  return (
    body.getBoundingClientRect().left +
    (Number.parseFloat(borderLeftWidth) || 0) +
    body.clientWidth
  );
};
// Whether two boxes share any pixel. The one spelling of a question three chrome passes
// ask: placement, badge reservation, and the clear part left of a box behind furniture.
export const overlaps = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

// Document-anchored chrome is positioned from the document origin, while the boxes it
// follows are read in viewport coordinates. Convert once at that boundary.
export function documentPoint(left, top) {
  return {
    left: left + scrollX,
    top: top + scrollY,
  };
}

// What a container lets the reader see of what it holds, or null where it shows all of
// it. Overflow is one of three ways to draw nothing past an edge: paint containment and
// content-visibility both clip while overflow computes `visible`, and a box under either
// would be drawn at a rect the reader never sees. The band itself is the padding box less
// whatever a scrollbar takes — clientLeft and clientWidth, where a border box says
// nothing about either, and a box drawn under a border is drawn nowhere as surely as one
// past the edge.
//
// `version check --render` imports this to ask which container cut a box away, so the
// band a handover is refused against and the band the page paints to are one reading.
// Written twice they disagreed twice, each copy right about one of the two things above
// and wrong about the other.
export function shownBand(el) {
  // The root element's border box travels with the document, while its scrollport stays
  // pinned to the viewport. Every other scroller's visible band can be derived from its
  // own box; the root is the platform-defined exception.
  if (el === document.scrollingElement)
    return {
      left: 0,
      top: 0,
      right: document.documentElement.clientWidth,
      bottom: document.documentElement.clientHeight,
    };
  const s = getComputedStyle(el);
  if (
    s.overflowX === "visible" &&
    s.overflowY === "visible" &&
    !/paint|strict|content/.test(s.contain) &&
    s.contentVisibility === "visible"
  )
    return null;
  const b = el.getBoundingClientRect();
  const left = b.left + el.clientLeft,
    top = b.top + el.clientTop;
  return {
    left,
    top,
    right: left + el.clientWidth,
    bottom: top + el.clientHeight,
  };
}

// The two bands of a scrollport, one reading each, beside the clip they start from.
//
// `visibleBand` is what the reader can see through a scroller now: its shown band less
// the sticky chrome standing over an edge of it. A sticky box declares itself with
// `.lf-pinned` (the thread list's run headings); stuck, it paints over the scroller's
// contents without clipping them, so a clip walk calls what is under it shown. Read acknowledgement,
// the summaries a thread card keeps open, and the place a re-render holds all ask this.
//
// `landingBand` is where a landing may put something: the shown band less the
// `scroll-padding` the scroller declares, which is also what `scrollIntoView` honours.
// It reserves room for the tallest cover wherever one might stick, so it is never wider
// than the visible band a landing arrives in.
export const PINNED = ".lf-pinned";
export function visibleBand(scroller) {
  const band = shownBand(scroller);
  if (!band) return null;
  const covers = [...scroller.querySelectorAll(PINNED)]
    .filter((cover) => cover.checkVisibility())
    .map((cover) => cover.getBoundingClientRect());
  return insetBand(band, covers);
}
export function landingBand(scroller) {
  const band = shownBand(scroller);
  if (!band) return null;
  const style = getComputedStyle(scroller);
  const inset = (side) => Number.parseFloat(style[`scrollPadding${side}`]) || 0;
  return {
    left: band.left + inset("Left"),
    top: band.top + inset("Top"),
    right: band.right - inset("Right"),
    bottom: band.bottom - inset("Bottom"),
  };
}
// A band less the covers standing over its edges. A cover stands over the top edge when
// it straddles it, and a cover resting on another stuck cover straddles the edge the
// first one leaves, so the covers are taken in order from the edge inward. A cover in
// the middle of the band is content passing through, not chrome over it. Null once the
// covers leave no band.
export function insetBand(band, covers) {
  const across = covers.filter(
    (cover) => cover.left < band.right && cover.right > band.left,
  );
  let { top, bottom } = band;
  for (const cover of [...across].sort((a, b) => a.top - b.top))
    if (cover.top <= top && cover.bottom > top) top = cover.bottom;
  for (const cover of [...across].sort((a, b) => b.bottom - a.bottom))
    if (cover.bottom >= bottom && cover.top < bottom) bottom = cover.top;
  return bottom > top ? { ...band, top, bottom } : null;
}
// The box an element shows as. An element that generates none of its own — a
// display: contents wrapper — shows as what its contents paint, so its bounds are
// theirs, and a range asks the platform for that union in one read. Its own rect is
// (0,0) at the document's origin, which is not a degenerate box but a wrong one: it
// reads as a real place at the top of the page, so whatever measured it travelled there.
//
// No widget in the vocabulary is one now — lf-suggestion was, and its theme comment
// carries what that cost — but the wrong answer is the platform's rather than that
// widget's: a page or a project layer styles any wrapper this way in a line. This
// lived inside the legend's own reading once, where it stood as a fact about the
// legend rather than about elements, which is exactly why the travel went on asking
// the element directly and centred the top of the document. One answer to "where is
// this element", so there is no second way to ask.
export function shownBox(el) {
  if (el === document.scrollingElement)
    return {
      x: 0,
      y: 0,
      left: 0,
      top: 0,
      right: document.documentElement.clientWidth,
      bottom: document.documentElement.clientHeight,
      width: document.documentElement.clientWidth,
      height: document.documentElement.clientHeight,
    };
  const r = el.getBoundingClientRect();
  if (r.width || r.height) return r;
  const contents = document.createRange();
  contents.selectNodeContents(el);
  return contents.getBoundingClientRect();
}
// The same reading in elements rather than pixels, for the marks the runtime paints on
// the page's own elements: an outline needs a box to hang on, so a mark aimed at a
// boxless element goes to the boxes its contents make. Read from the platform rather
// than from the registry, because generating no box is not a fact about which widget
// this is — any wrapper in any layer can do it, and CSS has no selector that says so.
//
// Area, where shownBox asks only for a box, because the two want different things of
// one: bounds are bounds whichever dimension is flat, while a ring is only worth hanging
// where it can be seen.
//
// The runtime's own chrome leaves by name rather than on that test. Area read as though
// it were doing the job, and it was doing it by luck: a suggestion hangs its controls off
// a span with no width, so the apparatus fell out on its own. The line saying how many
// comments a block holds is clipped to a pixel and has one — so a decision that had been
// commented on wore its ring on the runtime's word about the page rather than on the
// page, and the pixel it hung from moves the first time a comment lands. That question is
// already asked, declared labels and all, and it is the one the anchor pass puts
// to a text node — so what a mark hangs on and what a quote may name cannot come apart.
// Bounded at the element, for the reason given where the question is stated: a widget an
// agent sent stands inside the panel, and asked about the page instead it would have no
// child of its own left to fall back to.
export function shownParts(el) {
  const r = el.getBoundingClientRect();
  if (r.width && r.height) return [el];
  return [...el.children]
    .filter((child) => !uiInside(child, el))
    .flatMap((child) => shownParts(child));
}
// An item's bounds, held to what the page shows of them: the rect a box in the chrome's
// layer is drawn from, for the aim's box and the legend's alike. The layer is one no
// ancestor's clip can reach — that is the point of it — so the box owes the clips an
// answer of its own: an option's table box runs on under its group's overflow: hidden,
// and a card half-scrolled out of a board is half gone. A box drawn from the raw rect
// claims pixels the page has already refused, over the neighbour standing in them.
// The root scrollport's viewport band is one of these too: what is scrolled off screen
// has no rect, and a legend draws boxes for what is on it and nothing for the rest.
//
// The walk stops at a box the viewport holds rather than the document: nothing above a
// `position: fixed` element clips it, so the ancestors past that one are answering about a
// flow the element left. Every box in the chrome is behind one — the thread panel is
// fixed, so a reply box measured through the page flow's ancestors came back wholly clipped
// away at any window wide enough for the panel to stand beside the page rather than over
// it. The one caller before this asked
// only about the page's own items, none of which is ever inside a fixed box, which is why
// the walk could be written as "every ancestor" and read as complete.
//
// Which leaves the viewport itself, applied to everything: for a box in the page it is
// the root's band, and for one in a fixed layer it is the whole of what clips it.
//
// `clips` caches each ancestor's answer for one pass: the legend asks for every item
// on the page in one breath, and the items share their scrollers, so what a pass spends
// on the walk is two style reads per ancestor rather than two per item per ancestor.
export function shownRect(item, clips) {
  return clippedRect(shownBox(item), item, clips);
}
// Where a member begins, as the reader sees it: the first of the boxes it paints that
// survives the clips, rather than the bounds of all of them. They are the same box for
// anything in flow and different for an inline that wraps, whose bounds run from the
// column's left margin to its right — so a digit placed on that corner sat four hundred
// pixels from the link it addressed, a line above it, on top of somebody else's sentence.
// `shownBox`'s union answers "how much room does this take", which is what a legend box and
// an aim outline want; this answers "where does it start", which is what anything hung on a
// corner wants. The first that survives rather than the first outright, since a link whose
// opening line has scrolled away still has a corner on the line below it.
export const startsAt = (item, clips) => {
  const fragments = item.getClientRects();
  return (fragments.length ? [...fragments] : [shownBox(item)])
    .map((box) => clippedRect(box, item, clips))
    .find(Boolean);
};
// The clips standing over a box, applied to it. Taken apart from shownRect because the two
// readings above and a painted Range want the same walk over different boxes.
export const clippedRect = (box, item, clips) => clipped(box, item, clips, false);
// The same walk for a box measured from what an element holds: a Range inside it. The
// holder's own band stands over its contents, where it says nothing about the holder's
// own box, so text scrolled out of the `pre` it sits in directly is text nobody sees.
export const clippedContents = (box, holder, clips) =>
  clipped(box, holder, clips, true);
function clipped(box, item, clips, held) {
  let left = Math.max(box.left, 0),
    top = Math.max(box.top, 0),
    right = Math.min(box.right, innerWidth),
    bottom = Math.min(box.bottom, innerHeight);
  // From the box itself, not from its parent: an element is not clipped by its own
  // overflow — that clips what it holds — so its band is skipped and only its position is
  // read. Starting at the parent instead asked the question of every ancestor of a fixed
  // box and never of the box, which is the same bug one level up: in design mode the aim
  // resolves the thread panel itself, and the panel measured through body's band came
  // back wholly clipped away, so a mode whose row promises a click on the chrome drew
  // nothing over the chrome.
  // Cross an open shadow boundary through its host. A package surface rendered in a
  // declared shadow stage is still clipped by that host and by the page containers
  // outside it; stopping at the ShadowRoot would let chrome paint where the package
  // itself cannot.
  for (let a = item; a; a = a.parentElement ?? a.getRootNode()?.host ?? null) {
    let c = clips.get(a);
    if (c === undefined)
      clips.set(
        a,
        (c = {
          band: shownBand(a),
          // Read here rather than out of shownBand, whose answer is a band and is the
          // render gate's too: what clips a box and what a box is positioned against are
          // two facts, and one of them is this walk's alone.
          fixed: getComputedStyle(a).position === "fixed",
        }),
      );
    if ((held || a !== item) && c.band) {
      left = Math.max(left, c.band.left);
      top = Math.max(top, c.band.top);
      right = Math.min(right, c.band.right);
      bottom = Math.min(bottom, c.band.bottom);
    }
    if (c.fixed) break;
  }
  return right > left && bottom > top ? { left, top, right, bottom } : null;
}
