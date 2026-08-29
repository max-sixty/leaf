import { uiInside } from "./passages.js";

/* Shared readings of the boxes the page actually shows. */
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
// body is the page's own scroller, so its edge is one of these too: what is scrolled
// off screen has no rect, and a legend draws boxes for what is on it and nothing for
// the rest.
//
// The walk stops at a box the viewport holds rather than the document: nothing above a
// `position: fixed` element clips it, so the ancestors past that one are answering about a
// flow the element left. Every box in the chrome is behind one — the thread panel is
// fixed, and body is the page's scroller narrowed to the column beside it — so a reply box
// measured through body's band came back wholly clipped away, at any window wide enough for
// the panel to stand beside the page rather than over it. The one caller before this asked
// only about the page's own items, none of which is ever inside a fixed box, which is why
// the walk could be written as "every ancestor" and read as complete.
//
// Which leaves the viewport itself, applied to everything: for a box in the page it is
// what body's own band already said, and for one in a fixed layer it is the whole of what
// clips it.
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
export function clippedRect(box, item, clips) {
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
  for (let a = item; a; a = a.parentElement) {
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
    if (a !== item && c.band) {
      left = Math.max(left, c.band.left);
      top = Math.max(top, c.band.top);
      right = Math.min(right, c.band.right);
      bottom = Math.min(bottom, c.band.bottom);
    }
    if (c.fixed) break;
  }
  return right > left && bottom > top ? { left, top, right, bottom } : null;
}
