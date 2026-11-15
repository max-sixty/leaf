/* Whether and where an element shows a box, and `measure`, which waits for one. Any
   document can load it, so a widget on a plain HTML page waits for its room as it does
   on a Leaf page (portable-api.js); geometry.js builds its readings of what the page
   shows on these. */
import { skipped } from "./shadow-tree.js";
import { sizeObserver } from "./rendering.js";

// What a node's contents are drawn in, read through the one range this module keeps.
// A Range a page makes stays live until a collection reclaims it, and every change to
// the document walks each live range to keep its ends in place: a range made for each
// node of a pass over the page left every later write as slow as the page was large,
// half a millisecond each at 1,024 sections of the bench's asks page. The range lets go
// of the node once read, so it holds nothing a page has removed.
const contents = document.createRange();
/** @template T @param {Node} node @param {(range: Range) => T} read @returns {T} */
function readContents(node, read) {
  contents.selectNodeContents(node);
  try {
    return read(contents);
  } finally {
    contents.setStart(document, 0);
    contents.collapse(true);
  }
}
// The boxes of the lines `node`'s contents are drawn in, and the box around them all.
/** @param {Node} node */
export const contentsRects = (node) =>
  readContents(node, (range) => [...range.getClientRects()]);
/** @param {Node} node */
export const contentsBox = (node) =>
  readContents(node, (range) => range.getBoundingClientRect());

// The box an element shows as. An element that generates none of its own — a
// display: contents wrapper — shows as what its contents paint, so its bounds are
// theirs, and a range asks the platform for that union in one read. Its own rect is
// (0,0) at the document's origin, which is not a degenerate box but a wrong one: it
// reads as a real place at the top of the page, so whatever measured it travelled there.
//
// No widget in the vocabulary displays as contents, but the wrong answer is the
// platform's rather than any widget's: a page or a project layer styles any wrapper
// this way in a line. So the answer is a fact about elements, kept here rather than in
// one reader, and every reader asks this one function, or geometry.js's `shownBox`
// built on it, where an element is.
/** @param {Element} el */
export function elementBox(el) {
  const r = el.getBoundingClientRect();
  // A zero-sized box still belongs to its element. Only a boxless wrapper takes
  // its bounds from contents, which a hidden-until-found panel deliberately skips.
  if (r.width || r.height || skipped(el) || getComputedStyle(el).display !== "contents")
    return r;
  return contentsBox(el);
}

// A number a widget can only read off a box the browser has laid out, such as the room
// a pick mark's word will need or the width a chart is drawn for. Each is measured
// rather than stated for the same reason — the face this page is actually set in, or
// the room it actually gives, which no constant names across two platforms — and each
// reads 0 where there is no box to read.
//
// A widget upgrades wherever the runtime connects it, and not every one of those places
// is drawn. A message body is built for every comment the log carries and connected
// whether or not the user has opened the panel, and a shut panel is `display: none`:
// every box beneath it is zero. `once` then refuses the second upgrade that would put
// it right, and the body is cached for the life of the tab and never rebuilt — so a
// zero taken there is indistinguishable from a measurement and stands for good. A pick
// column collapsed to nothing, a grip drawn over the card's own title.
//
// So the module states the measurement and the runtime takes it: now, where there is
// something to read, and otherwise the first time there is. ResizeObserver is the
// browser's own answer to "this has a box now", and the one that answers it wherever
// the element sits — a message scrolled past the panel's own fold has been laid out
// just the same, which is the question an IntersectionObserver would get wrong.
//
// The observation ends at the reading it was waiting for, so what a measurement writes
// cannot return through what triggered it: after the unobserve there is no second
// delivery to the element that was just written.
//
// Skipped content, a shut tab's panel or a closed disclosure, has no box either, though
// asking for its rect would lay it out and answer with one (`skipped`). A widget there
// waits until the user opens the panel, whichever of its module and the panel's upgraded
// first, and a chart's bundle waits with it.
//
// Paper prints a shut panel open too, but a box laid out for a sheet is not the room
// the user will see: the screen alone holds an undrawn widget at its stated height
// (layouts.css), and a measurement stands for good. So a box on paper is no box, and a
// widget paper reached is observed afresh once the page is back on screen, since the
// browser reports only a change from the size it last delivered and the screen may lay
// the box out at the size paper did.
/** @type {WeakMap<Element, () => void>} */
const measurements = new WeakMap();
const paper = matchMedia("print");
/** @type {Set<Element>} */
const onPaper = new Set();
paper.addEventListener("change", () => {
  if (paper.matches) return;
  for (const el of onPaper) unmeasured.observe(el);
  onPaper.clear();
});
/** @param {Element} el */
const drawn = (el) => {
  if (paper.matches || skipped(el)) return false;
  const box = elementBox(el);
  return Boolean(box.width || box.height);
};
const unmeasured = sizeObserver((entries) => {
  const taking = [];
  for (const { target } of entries) {
    if (paper.matches) {
      unmeasured.unobserve(target);
      onPaper.add(target);
      continue;
    }
    if (!drawn(target)) continue;
    unmeasured.unobserve(target);
    const take = measurements.get(target);
    if (take) taking.push(take);
    measurements.delete(target);
  }
  // Every one released before any of them is taken: a measurement writes room its own
  // widget spends, which resizes it, and a widget still observed when that happens is a
  // second delivery inside the round that wrote it.
  for (const take of taking) take();
});
/** @param {Element} el @param {() => void} take */
export function measure(el, take) {
  // The box it shows as, not this element's own rect: a `display: contents` wrapper
  // draws no box of its own and never will, and its contents are what the measurement
  // is about. Asked the narrow way it would wait forever, holding the take and the
  // observation with it.
  if (drawn(el)) {
    // A wait already pending for this element is over: it was waiting for the box
    // this reading just found. Left pending it would deliver a second reading of
    // the same number, which is harmless and still a claim that nothing was read.
    if (measurements.delete(el)) unmeasured.unobserve(el);
    onPaper.delete(el);
    return take();
  }
  measurements.set(el, take);
  unmeasured.observe(el);
}
