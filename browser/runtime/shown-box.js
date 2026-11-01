/* Whether and where an element shows a box, and `measure`, which waits for one. Any
   document can load it, so a widget on a plain HTML page waits for its room as it does
   on a Leaf page (portable-api.js); geometry.js builds its readings of what the page
   shows on these. */
import { renderedParent } from "./shadow-tree.js";
import { sizeObserver } from "./rendering.js";

// Whether `el` stands in content the browser skips: what a `content-visibility: hidden`
// box holds, which a hidden tab's panel (`hidden="until-found"`) is, and a closed
// disclosure's content. The browser leaves skipped content unstyled and unlaid, and one
// question about any box inside — its computed style, its rect, its scroll offsets —
// makes it style and lay out that whole subtree first to answer. On the corpus, whose
// examples each stand in a hidden tab, those forced passes were most of a revision's
// style time. So a reading that has nothing to say about a box on no screen — where it
// stands, whether it scrolls, what room it takes — asks this first and leaves the box
// out until a pass after it is drawn: revealing a panel or opening a disclosure resizes
// what holds it, which brings those passes round. A reading that marks what the user
// will see once it is drawn (an anchor's outline) still asks, and pays.
//
// Answered without forcing anything: `checkVisibility` reads the tree the browser has,
// and is false for a box that is not drawn for any reason. The nearest drawn ancestor
// says which reason — a box skipping what it holds, or `display: none`/`contents` on
// the way down, which are not skipped and cheap to ask about — and it is drawn, so its
// own style is not skipped either. A disclosure skips through a pseudo-element of its
// own, so it is asked by its state rather than by its style.
//
/** @param {Element} element */
export const skipped = (element) => {
  if (element.checkVisibility({ contentVisibilityAuto: true })) return false;
  // A boxed descendant can retain layout while its auto container skips drawing.
  // Ask the native skip state before any geometry forces that content back.
  if (element.checkVisibility()) return true;
  let child = element;
  let box = renderedParent(element);
  while (box && !box.checkVisibility()) {
    child = box;
    box = renderedParent(box);
  }
  if (!box) return false;
  if (box.localName === "details")
    return !box.hasAttribute("open") && child.localName !== "summary";
  return getComputedStyle(box).contentVisibility === "hidden";
};

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
  const contents = document.createRange();
  contents.selectNodeContents(el);
  return contents.getBoundingClientRect();
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
/** @type {WeakMap<Element, () => void>} */
const measurements = new WeakMap();
/** @param {Element} el */
const drawn = (el) => {
  if (skipped(el)) return false;
  const box = elementBox(el);
  return Boolean(box.width || box.height);
};
const unmeasured = sizeObserver((entries) => {
  const taking = [];
  for (const { target } of entries) {
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
    return take();
  }
  measurements.set(el, take);
  unmeasured.observe(el);
}
