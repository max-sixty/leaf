/* This module owns the shared readings of visible boxes and clipping, how much of the
 * window the page shows, and the one conversion from viewport boxes to
 * document-positioned chrome. */
import { excludedByInert, renderedParent, uiInside, under } from "./shadow.js";
import {
  nativeLayers,
  nativeModalAdmits,
  watchLayerChanges,
} from "./keyboard/layer-stack.js";
import { isNativeLayer } from "./shadow-tree.js";
import {
  clippingAxes,
  hasArea,
  intersect,
  overlaps,
  overlapsAcross,
  union,
} from "./rect.js";
import { cancelRender, nextRender, sizeObserver } from "./rendering.js";
import { watchScrolls } from "./arrivals.js";
import { isHTML, isElement } from "./shadow-tree.js";
import { elementBox } from "./shown-box.js";

/** @typedef {import('./rect.js').Box} Box
 * @typedef {{band: Box | null, axes: {x: boolean, y: boolean}, positioned: boolean,
 * block: Element | null | undefined, scrolls: boolean}} ClipEntry
 * @typedef {{surface: HTMLElement, box: Box}} Occluder
 * @typedef {Map<Element, ClipEntry> & Map<typeof PAST, Set<HTMLElement>> &
 * Map<typeof OCCLUDERS, Occluder[]>} ClipCache
 * @typedef {{box: Element, axes: {x: boolean, y: boolean}, scrolls: boolean,
 * covered: boolean, footed: boolean, band: Box | null}} ClipCut */

// The geometry owner uses the active document's visual viewport, including pinch
// zoom and the on-screen keyboard. Refuse a missing capability at this boundary.
const nativeViewport = window.visualViewport;
if (!nativeViewport) throw new Error("Leaf requires an active visual viewport");
export const visualViewport = nativeViewport;

/* Shared readings of the boxes the page actually shows.

   `shownBox` returns an element's own box or the union of the boxes its
   `display: contents` descendants paint. `shownParts` returns the visible elements on
   which an outline can be drawn, and `shownExtent` the box they cover together.
   `shownRect` clips an element's `shownBox` through scrolling ancestors' visible bands (less the sticky headers stuck over their tops) and the viewport,
   following native positioned containing blocks past intermediate overflow clips,
   then takes away what a declared occluder stands over (`declareOccluder`). It is what a box may be drawn over, which
   chrome can be: the floating panel is drawn above the page, not cut out of it. `seenRect` holds that to the room the chrome leaves (`shownWindow`), and it is
   the one reading of whether the user can see something.
   `clippedRect` applies that same clipping walk to a box measured some other way for an
   element, and `clippedContents` to a box measured from a Range, starting at the element
   that holds the Range and counting that element's own clip. Use:

   - `shownBox` for travel, bounds, and reading-position landmarks;
   - `shownParts` for obligation rings and element-anchor outlines;
   - `shownExtent` for what stands beside a target's parts: a margin row, the
     response field's room;
   - `shownRect` for visible placement of floating chrome and key badges;
   - `seenRect` for whether, and how much of, something is in front of the user;
   - `growthIsSeen` and `growthAfterIsSeen` for whether a change of size would move what
     the user sees (`motionBand`), which scroll anchoring makes a different question;
   - `whenNone` to hear when one of those readings stops holding for all of something;
   - `clippedRect` for an element's box the caller has adjusted;
   - `nearWindow` and `nearObserver` for whether a box standing against something
     belongs in layout yet;
   - `paintClips` for what cuts paint standing over an element, each cut in the plane
     of the box it belongs to;
   - `clippedContents` when the subject has no element box of its own;
   - `placeBox` and `clippedPlace` for a destination that is an element or a Range;
   - `presented` and `frameView` for whether the page puts a box before the user at all
     and what this page shows of a sample it holds, and `watchRoom` for when any of
     those readings may have changed.

   `skipped` (shown-box.js) is asked first by a reading that can leave out a box the
   browser is not drawing, since reading one in skipped content forces that content's
   style and layout.

   Do not read `getBoundingClientRect()` directly when the target may generate no box.
   A `display: contents` element reports an origin-like zero rectangle that does not
   represent where its contents are. An area greater than zero is not enough for shown
   parts either: clipped note text and hoisted controls can have measurable boxes while
   remaining the wrong semantic target, which is why `shownParts` takes the bounded
   chrome question (`uiInside`). `unmarkableElements`, in the render checks, detects
   declared items with no visible part on which a mark can land. */
// Where the page's shell ends on the right — the far edge of the room the document has,
// which is what a margin element is placed against and what the response surface may not
// overhang. The chrome stands over the page and takes none of it.
export const shellRight = () => document.body.getBoundingClientRect().right;

// How much of the window the page shows: the visible viewport, less the chrome fixed to
// its edges, the boxes the floating panel stands. Each stands over the page without
// clipping it, so no clip walk finds it; its owner declares it here
// (`declareWindowChrome`, floating-panel.js), and every reading of the room the page has
// starts from `shownWindow` rather than measuring the chrome itself. The chrome is read
// as the boxes standing in it rather than as a stated height, and each box bounds only
// the room it stands across, from the edge it stands nearer.
//
// The visible viewport is the part of the window the user sees: pinch zoom and a phone's
// software keyboard shrink it without resizing the layout viewport the page and its fixed
// chrome are laid out in, and a surface placed in the layout viewport alone can stand
// under the keyboard. `within` narrows the room to a box the caller keeps to, such as a
// reading region's shown bounds, and `gap` holds what stands in the room that far inside
// each of its edges. `viewport: "layout"` reads the room in the layout viewport instead,
// the window the page scrolls through, for a caller asking whether a scroll has carried
// something out of the page's room rather than whether the user can see it. `across`
// names the columns a box asking for its room stands in, where they are narrower than
// the room: chrome beside those columns takes none of its height, as the floating
// panel's row under the page column leaves a thread card in the margin the window's
// whole height.
//
// The chrome's owner also hands over the elements it draws, and a change of their size
// is announced as `ROOM_MOVED` (`watchRoom`), as is an occluder's (`declareOccluder`): a
// view opens or shuts above the floating panel's row, with no scroll or resize for a
// reader to hear.
//
// Chrome takes room from the page, not from itself: what stands in the chrome's elements
// is in the room its own chrome leaves (`item`), as the floating panel's field stands in
// the row it declares. Such a box is in front of the user wherever it is, so it names
// no place in the page (`inWindowChrome`).
/** @type {Map<() => readonly Box[], readonly Element[]>} */
const windowChrome = new Map(); // boxes -> the elements they stand
const chromeSizes = sizeObserver(() => announceRoom(document));
/** @param {Element} element */
const watchChrome = (element) => chromeSizes.observe(element, { box: "border-box" });
/** @param {() => readonly Box[]} boxes @param {readonly Element[]} elements */
export const declareWindowChrome = (boxes, elements) => {
  windowChrome.set(boxes, elements);
  elements.forEach(watchChrome);
};
/** @param {Node | null} node @param {readonly Element[]} elements */
const standsIn = (node, elements) =>
  Boolean(node) && elements.some((element) => under(node, element));
/** @param {Node | null} node */
export const inWindowChrome = (node) =>
  [...windowChrome.values()].some((elements) => standsIn(node, elements));
// Every box the declared window chrome stands now, for a reading that keeps clear of
// them all, as Go-to's chips and a search's marks do; but for the chrome `item` stands
// in.
/** @param {Node | null} [item] */
export const windowChromeBoxes = (item = null) =>
  [...windowChrome]
    .filter(([, elements]) => !standsIn(item, elements))
    .flatMap(([boxes]) => boxes());
// The layout viewport's box, less the scrollbars the root draws at its edges, where
// nothing the page shows stands: `innerWidth` and `innerHeight` count a classic
// scrollbar. Every reading of the whole window's box starts here, `doc`'s for a sample
// asking it of its containing page.
/** @param {Document} [doc] */
export const layoutWindow = (doc = document) => ({
  left: 0,
  top: 0,
  right: doc.documentElement.clientWidth,
  bottom: doc.documentElement.clientHeight,
});
/** @param {{within?: Partial<import('./rect.js').Box> | null,
 * gap?: number, viewport?: "visual" | "layout", item?: Node | null,
 * across?: {left: number, right: number} | null}} [options] */
export function shownWindow({
  within = null,
  gap = 0,
  viewport = "visual",
  item = null,
  across = null,
} = {}) {
  const layout = layoutWindow();
  const { offsetLeft, offsetTop, width, height } =
    viewport === "visual"
      ? visualViewport
      : { offsetLeft: 0, offsetTop: 0, width: layout.right, height: layout.bottom };
  const left = Math.max(offsetLeft, within?.left ?? -Infinity) + gap;
  const right = Math.min(offsetLeft + width, within?.right ?? Infinity) - gap;
  let top = Math.max(offsetTop, within?.top ?? -Infinity);
  let bottom = Math.min(offsetTop + height, within?.bottom ?? Infinity);
  const middle = offsetTop + height / 2;
  for (const box of windowChromeBoxes(item)) {
    if (!overlapsAcross(box, across ?? { left, right })) continue;
    if (box.top + box.bottom < 2 * middle) top = Math.max(top, box.bottom);
    else bottom = Math.min(bottom, box.top);
  }
  top += gap;
  bottom -= gap;
  return new DOMRect(left, top, Math.max(0, right - left), Math.max(0, bottom - top));
}

// What a container lets the user see of what it holds, or null where it shows all of
// it. Overflow is one of three ways to draw nothing past an edge: paint containment and
// content-visibility both clip while overflow computes `visible`, and a box under either
// would be drawn at a rect the user never sees. The band itself is the padding box less
// whatever a scrollbar takes — clientLeft and clientWidth, where a border box says
// nothing about either, and a box drawn under a border is drawn nowhere as surely as one
// past the edge.
//
// `page check --render` imports this to ask which container cut a box away, so the
// band a handover is refused against and the band the page paints to are one reading.
// Written twice they disagreed twice, each copy right about one of the two things above
// and wrong about the other.
//
// The element's own document answers, so a sample can ask it of the containing page's
// boxes in that page's viewport coordinates.
/** @param {Element} el @returns {Box | null} */
export function shownBand(el) {
  const doc = el.ownerDocument;
  // The root element's border box travels with the document, while its scrollport stays
  // pinned to the viewport. Every other scroller's visible band can be derived from its
  // own box; the root is the platform-defined exception.
  if (el === doc.scrollingElement) return layoutWindow(doc);
  const s = getComputedStyle(el);
  const axes = clippingAxes(s);
  if (!axes.x && !axes.y) return null;
  const b = el.getBoundingClientRect();
  const scaleX = isHTML(el) && el.offsetWidth ? b.width / el.offsetWidth : 1;
  const scaleY = isHTML(el) && el.offsetHeight ? b.height / el.offsetHeight : 1;
  const left = b.left + el.clientLeft * scaleX,
    top = b.top + el.clientTop * scaleY;
  return {
    left,
    top,
    right: left + el.clientWidth * scaleX,
    bottom: top + el.clientHeight * scaleY,
  };
}

// The two bands of a scrollport, one reading each, beside the clip they start from.
//
// `visibleBand` is what the user can see through a scroller now: its shown band less the
// sticky headers stuck over its top and the sticky footers over its foot. A sticky
// header, such as a page `lf-tabs` strip or an `lf-diff` file header, has a stated
// height and paints over the scroller's contents without clipping them, so a band that
// ignored it would call what is under it shown. Which headers stand over a box is a fact
// of where the box stands, so the band is read for one box (`item`), and `headerInset`
// says how far the headers reach over it, as `footerInset` says for footers, such as a
// long thread's pinned reply row. The clip walk below applies the same reading at every
// ancestor, so `shownRect` and the readings built on it (read acknowledgement, the
// summaries a thread card keeps open, arrival checks, chrome placement) all answer "on
// screen" the same way; the place a re-render holds asks it of its one scroller
// directly.
//
// `landingBand` is where a landing may put something: the shown band less the
// `scroll-padding` the scroller declares, which is also what `scrollIntoView` honours.
// It clears what stands over the whole scroller (a page tab strip); a header
// over part of it, a diff's file header, is cleared by the `scroll-margin` of the rows
// it stands over. It is also where scroll anchoring looks for the box it keeps still:
// the spec's optimal viewing region, which Chrome reads from `scroll-padding` too
// (`motionBand`).
//
// A box scrolls, for these readings, when its computed overflow makes it a scroll
// container: `auto` and `scroll`, and `hidden` too, which a script or a landing can
// scroll though the user cannot, and which is the scroller a sticky box inside it sticks
// in. The runtime asks it of what a motion scrolls and which boxes scroll what they
// hold (`scrollsContent`), and of the boxes that hold sticky headers
// (`scrollContainer`). `userScrollport` is the same test without `hidden`: what the
// user, rather than a script, can scroll, which keyboard stops and edge marks read
// (reach.js, `paintSlot`), and the render checks asking what a reader can reach.
/** @param {string} overflow */
const scrollport = (overflow) => /^(auto|scroll|hidden)$/.test(overflow);
/** @param {string} overflow */
export const userScrollport = (overflow) => /^(auto|scroll)$/.test(overflow);
/** @param {Pick<CSSStyleDeclaration, "overflowX" | "overflowY">} style */
export const scrollsBy = ({ overflowX, overflowY }) =>
  scrollport(overflowX) || scrollport(overflowY);
/** @param {Element} el */
const scrolls = (el) => scrollsBy(getComputedStyle(el));
// A scroll container: the document's own scroller, or a box whose overflow scrolls.
/** @param {Element} box */
export const scrollContainer = (box) =>
  box === box.ownerDocument.scrollingElement || scrolls(box);
// Whether `box` scrolls what it holds: it clips into a scrollport, `hidden` included,
// which a script or focus can scroll, and holds more than that scrollport shows on that
// axis. An inline SVG drawing clips what it draws but scrolls none of it.
/** @param {Node | null} box */
export function scrollsContent(box) {
  if (!isElement(box) || box.namespaceURI === "http://www.w3.org/2000/svg")
    return false;
  const style = getComputedStyle(box);
  return (
    (scrollport(style.overflowX) && box.scrollWidth > box.clientWidth) ||
    (scrollport(style.overflowY) && box.scrollHeight > box.clientHeight)
  );
}
// How far below the top of `scroller`'s band the view of `el` starts, past the sticky
// headers stuck over it. Each header adds its stated height to `--lf-top` for what it
// stands over (base.css), so where the `--lf-top` computed at `el` exceeds the
// scroller's own, headers stand over `el`, and their foot is that value below the
// scroller's padding edge, where a sticky box is measured from. The root's own value is
// the head room, which is left to `shownWindow`, so with no header over `el` nothing is
// taken. A header that is not stuck stands above its content, so the reading holds
// whether it is stuck or not, except at the end of what the header stands over, where
// the header is pushed up with it and the reading still counts its height as covered. A
// header sticks in a box that scrolls, so a box that only clips (`overflow: clip`, paint
// containment) has none over it. A box that scrolls starts `--lf-top` again for what it
// holds, so the value is read past every box between `el` and `scroller` that scrolls,
// at the parent of the outermost: inside a sideways scroller the value counts from that
// scroller, and the headers over `scroller`'s band are those outside it. A header's
// holder puts the stacked value on a box that does not scroll (base.css, at `--lf-top`).
/** @param {Element} el @param {Element} scroller */
const slotHolder = (el, scroller) => {
  /** @type {Element | null} */
  let at = el;
  /** @type {Element | null} */
  let box = el;
  for (; box && box !== scroller; box = renderedParent(box))
    if (box.nodeType === 1 && scrolls(box)) at = renderedParent(box);
  return at;
};
// The inset read at `at`, the box where the slot counts from `scroller`.
/** @param {Element | null} at @param {Element} scroller @param {string} slot @param {"paddingTop" | "paddingBottom"} padding */
const insetAt = (at, scroller, slot, padding) => {
  /** @param {Element} box */
  const read = (box) =>
    Number.parseFloat(getComputedStyle(box).getPropertyValue(slot)) || 0;
  const inset = at?.nodeType === 1 ? read(at) : 0;
  if (inset <= read(scroller)) return 0;
  return (Number.parseFloat(getComputedStyle(scroller)[padding]) || 0) + inset;
};
/** @type {[string, "paddingTop"]} */
const TOP = ["--lf-top", "paddingTop"];
// Where a header sticking at the top of `scroller` stands, below its border edge: past
// its padding, at the slot it starts (`--lf-top`, base.css).
/** @param {Element} scroller */
export function slotTop(scroller) {
  const style = getComputedStyle(scroller);
  return (
    (Number.parseFloat(style.paddingTop) || 0) +
    (Number.parseFloat(style.getPropertyValue("--lf-top")) || 0)
  );
}
/** @type {[string, "paddingBottom"]} */
const FOOT = ["--lf-bottom", "paddingBottom"];
/** @param {Element} el @param {Element} scroller @param {[string, "paddingTop" | "paddingBottom"]} edge */
const edgeInset = (el, scroller, edge) =>
  !scrollContainer(scroller) || el === scroller
    ? 0
    : insetAt(slotHolder(el, scroller), scroller, ...edge);
/** @param {Element} el @param {Element} scroller */
export const headerInset = (el, scroller) => edgeInset(el, scroller, TOP);
// The same reading at the foot, for a box sticking there (`--lf-bottom`, base.css):
// how far above the bottom of `scroller`'s band the view of `el` ends.
/** @param {Element} el @param {Element} scroller */
const footerInset = (el, scroller) => edgeInset(el, scroller, FOOT);
/** @param {Element} scroller @param {Element | null} [item] */
export function visibleBand(scroller, item = null) {
  const band = shownBand(scroller);
  if (!band || !item) return band;
  const top = band.top + headerInset(item, scroller);
  const bottom = band.bottom - footerInset(item, scroller);
  return bottom > top ? { ...band, top, bottom } : null;
}
// The cuts the declared sticky headers and footers over `item` make, read by the clip
// walk paint reads its bands from (`paintClips`), so a box passing under them and the
// paint over `item` agree, a fixed or absolute box escaping the scrollers around it
// included: one for each box that scrolls `item` where a header stands over its top or
// a footer over its foot, the document's included, outermost first. Each is
// `{box, band}`, with `band` cut at the header's foot and the footer's top and open
// past the box's other edges, so it holds whatever size the box grows to, or null
// where they cover all of it. A header that is not stuck stands above what it heads,
// so the cut holds at every scroll. `clips` is the walk's cache, shared by a pass that
// reads many.
const OPEN = 100000;
/** @param {Element} item @param {ClipCache} [clips] */
export function headerCuts(item, clips = new Map()) {
  return clipWalk(item, clips, false)
    .cuts.filter(({ covered, footed }) => covered || footed)
    .reverse()
    .map(({ box, band, covered, footed }) => ({
      box,
      band: band && {
        left: band.left - OPEN,
        right: band.right + OPEN,
        top: covered ? band.top : band.top - OPEN,
        bottom: footed ? band.bottom : band.bottom + OPEN,
      },
    }));
}
// The sticky box holding `node` while it is stuck, or the box fixed in the window
// holding it, else null. A box fixed in the window, as a page of parts' column is
// (layouts.css), stands there wherever the page is scrolled, so it is always stuck; a
// fixed box anchored to the page's words, as the inline thread card is
// (annotation-overlay/floating.js), or held by a transformed box around it, moves with
// what holds it as the page scrolls, so it is not. A
// stuck box stands at the
// edge of the scroller it sticks in, or is pushed past it by its holder's end, rather
// than at its own place in its holder, whose edge has scrolled beyond it: a page tab
// strip over its panel's sixtieth paragraph, an open thread's title over the turns read
// below it, a reply row pinned at the foot of a long thread. It rides along with every
// scroll, so being in view says nothing about where in its holder the user is. Whatever
// a stuck box holds rides with it, a control in a scroller of its own included, such as
// a reply row's attachment shelf, so every sticky box around `node` is asked, up to
// `within` where it is given: a reader asking where in one scroller the user is asks only
// of the boxes that scroller carries, and a sticky box around the scroller, such as a
// sidebar's block that sticks beside the page and scrolls what it holds, rides with none
// of that scroller's scrolls.
//
// A box standing on its foot line in its own place counts as stuck too: a reply row at
// the very end of its thread. Anything growing before it, a turn arriving or its own
// draft, pushes it past that line, where it sticks, so it holds still as a stuck box
// does, and a reader asking whether news moves it, or whether aiming a scroll at it
// moves anything, gets the same answer either side of that line. Where else a box
// stands in its own place is read from its holder's border box, which the box's own
// place lies within, so a box exactly on its top line in its own place may read stuck
// by its holder's padding: that boundary is one scroll offset wide.
//
// Which band a sticky box covers is a different question, answered from its stated
// height whether it is stuck or not (`headerInset`, `footerInset`).
/** @param {Element} node @param {Element | null} [within] */
export function stuckBox(node, within = null) {
  /** @type {Element | null} */
  let el = node;
  for (; el?.nodeType === 1 && el !== within; el = renderedParent(el)) {
    const style = getComputedStyle(el);
    if (style.position === "sticky" ? sticks(el) : inWindow(el, style)) return el;
  }
  return null;
}
// A fixed box stands in the window where nothing around it holds it instead, which
// leaves it no offset parent, and no anchor positions it.
/** @param {Element} el @param {CSSStyleDeclaration} style */
const inWindow = (el, style) =>
  style.position === "fixed" &&
  isHTML(el) &&
  el.offsetParent === null &&
  !style.positionAnchor.startsWith("--");
// Whether `sticky` stands where sticking holds it, in the scroller around it. A sticky
// box that clips what it holds, as a tab strip does, still sticks in that scroller.
/** @param {Element} sticky */
function sticks(sticky) {
  let scroller = renderedParent(sticky);
  while (scroller?.nodeType === 1 && !scrollContainer(scroller))
    scroller = renderedParent(scroller);
  if (scroller?.nodeType !== 1) return false;
  const band = shownBand(scroller);
  if (!band) return false;
  const style = getComputedStyle(sticky);
  const room = getComputedStyle(scroller);
  const padTop = Number.parseFloat(room.paddingTop) || 0;
  const padBottom = Number.parseFloat(room.paddingBottom) || 0;
  const box = sticky.getBoundingClientRect();
  // The holder is the box the sticky stands in: past any `display: contents` wrapper,
  // and where that is the scroller itself, its scrolled content rather than its frame.
  let parent = renderedParent(sticky);
  while (
    parent &&
    parent !== scroller &&
    getComputedStyle(parent).display === "contents"
  )
    parent = renderedParent(parent);
  const content = band.top - scroller.scrollTop;
  const holder =
    parent === scroller
      ? { top: content + padTop, bottom: content + scroller.scrollHeight - padBottom }
      : parent && shownBox(parent);
  if (!holder) return false;
  const topLine = band.top + padTop + Number.parseFloat(style.top);
  const footLine = band.bottom - padBottom - Number.parseFloat(style.bottom);
  if (box.top <= topLine + 1 && holder.top < box.top - 1) return true;
  if (Math.abs(box.bottom - footLine) <= 1) return true;
  return box.bottom > footLine && holder.bottom > box.bottom + 1;
}
/** @param {Element} scroller */
export function landingBand(scroller) {
  const band = shownBand(scroller);
  if (!band) return null;
  const inset = landingInsets(scroller);
  return {
    left: band.left + inset.left,
    top: band.top + inset.top,
    right: band.right - inset.right,
    bottom: band.bottom - inset.bottom,
  };
}
// How far each edge of `landingBand` stands in from the scroller's shown band: the
// `scroll-padding` it declares. Callers that measure from the scroller's own box take
// the clearance here rather than reading the style themselves.
/** @param {Element} scroller */
export function landingInsets(scroller) {
  const style = getComputedStyle(scroller);
  /** @param {"Top" | "Right" | "Bottom" | "Left"} side */
  const inset = (side) => Number.parseFloat(style[`scrollPadding${side}`]) || 0;
  return {
    top: inset("Top"),
    right: inset("Right"),
    bottom: inset("Bottom"),
    left: inset("Left"),
  };
}
// The box an element shows as (`elementBox`, shown-box.js), and for the document's
// scroller the band of the window it shows.
/** @param {Element} el @returns {DOMRect} */
export function shownBox(el) {
  if (el === document.scrollingElement) {
    const { left, top, right, bottom } = layoutWindow(el.ownerDocument);
    return new DOMRect(left, top, right - left, bottom - top);
  }
  return elementBox(el);
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
/** @param {Element} el @returns {Element[]} */
export function shownParts(el) {
  const r = el.getBoundingClientRect();
  if (r.width && r.height) return [el];
  return [...el.children]
    .filter((child) => !uiInside(child, el))
    .flatMap((child) => shownParts(child));
}
// The box an element's shown parts cover together: a mark hung on the element stands at
// its corner, so a comment on one shape of a drawing stands on that shape rather than at
// the drawing's edge. An element with no shown part has none.
/** @param {Element} el */
export const shownExtent = (el) =>
  union(shownParts(el).map((part) => part.getBoundingClientRect()));
// An item's bounds, held to what the page shows of them: the rect a box in the chrome's
// layer is drawn from, for the aim's box and the legend's alike. The layer is one no
// ancestor's clip can reach — that is the point of it — so the box owes the clips an
// answer of its own: an option's table box runs on under its group's overflow: hidden,
// and a card half-scrolled out of a board is half gone. A box drawn from the raw rect
// claims pixels the page has already refused, over the neighbour standing in them.
// The root scrollport's viewport band is one of these too: what is scrolled off screen
// has no rect, and a legend draws boxes for what is on it and nothing for the rest.
//
// Positioned descendants escape intermediate overflow clips up to their native
// containing block. The viewport holds a fixed box with no offsetParent; a transformed,
// filtered or layout-contained ancestor instead holds it and still clips its contents.
// Absolute boxes follow the same containing-block boundary. A DOM ancestor's overflow
// does not clip a box whose containing block lies outside that ancestor.
//
// Which leaves the viewport itself, applied to everything: for a box in the page it is
// the root's band, and for one in a fixed layer it is the whole of what clips it.
//
// `clips` caches each ancestor's answer for one pass: the legend asks for every item
// on the page in one breath, and the items share their scrollers, so what a pass spends
// on the walk is two style reads per ancestor rather than two per item per ancestor.
/** @param {Element} item @param {ClipCache} clips */
export function shownRect(item, clips) {
  return clippedRect(shownBox(item), item, clips);
}
// What of an item the user sees: what every box over it lets through, within the room the
// chrome leaves, but for chrome the item stands in. `within` keeps a bottom-bar box from
// cutting the item unless it stands across it. The chrome cuts the item's top and foot
// only; its sides stay shownRect's, the
// layout viewport's, since a pinch zoom's visual viewport is a pan across the page and not
// a clip — read with its sides, a message wider than the zoomed view was never seen whole
// across, and never counted read. Null when none of it shows. `box` is the extent asked
// about, the item's own by default, or wider, as a focus ring's room is.
/** @param {Element | Range} item @param {ClipCache} clips @param {Box} [box] */
export function seenRect(item, clips, box = placeBox(item)) {
  const shown = clippedPlace(item, clips, box);
  if (!shown) return null;
  const room = shownWindow({ within: shown, item: placeHolder(item) });
  return room.width > 0 && room.height > 0
    ? { left: shown.left, top: room.top, right: shown.right, bottom: room.bottom }
    : null;
}
// Whether the page draws `node` with what it holds: rendered (`checkVisibility`, with its
// `options`) and not hidden until found. An element `hidden="until-found"` keeps a box
// of its own while the browser skips its contents, until find-in-page or `reveal`
// (widget-elements.js) opens it, and `checkVisibility` answers only for that box, so
// it alone would count a folded thread message or an unchosen tab's panel as shown.
/** @param {Element} node @param {CheckVisibilityOptions} [options] */
export const showsContents = (node, options) =>
  node.getAttribute("hidden") !== "until-found" && node.checkVisibility(options);
// Whether the page puts `node` before the user at all, before any question of where:
// drawn with its contents and visible, not inert, inside the topmost modal, and not
// hidden with `aria-hidden`. Exposure asks it of a message body and of a sample's frame.
/** @param {Element} node */
export function presented(node) {
  if (
    !showsContents(node, { visibilityProperty: true }) ||
    excludedByInert(node) ||
    !nativeModalAdmits(node)
  )
    return false;
  /** @type {Element | null} */
  let at = node;
  for (; at; at = renderedParent(at))
    if (at.getAttribute?.("aria-hidden") === "true") return false;
  return true;
}
// What this page shows of a sample's frame it holds, in the frame's own viewport
// coordinates: the frame's `seenRect`, within `within`, the window or what this page's
// own holder shows of it, or null where the user sees none of it. The sample cannot
// read this itself: only this page's module knows the chrome and occluders
// standing over the frame, which cut it as they cut any of this page's boxes. A page in
// an ordinary iframe reads only its own window.
/** @param {HTMLIFrameElement} frame @param {Box} within */
export function frameView(frame, within) {
  const seen = seenRect(frame, new Map());
  const shown = seen && intersect(seen, within);
  if (!shown || !hasArea(shown)) return null;
  const rect = frame.getBoundingClientRect();
  const scaleX = rect.width / frame.offsetWidth || 1;
  const scaleY = rect.height / frame.offsetHeight || 1;
  /** @param {number} at */
  const x = (at) => (at - rect.left) / scaleX - frame.clientLeft;
  /** @param {number} at */
  const y = (at) => (at - rect.top) / scaleY - frame.clientTop;
  return {
    left: x(shown.left),
    top: y(shown.top),
    right: x(shown.right),
    bottom: y(shown.bottom),
  };
}
// Everything besides a reader's own boxes that changes what `seenRect` reads, so a
// reader of what the user sees watches it here rather than keeping its own list: a
// scroll, a shadow stage's included (`watchScrolls`); a resize; the visual viewport,
// which a soft keyboard or a pinch-pan moves without either; a native layer opening or
// closing, which changes what a modal admits (`watchLayerChanges`); and chrome the room
// is measured against changing size or ending a slide (`ROOM_MOVED`). Returns the call
// that stops watching.
const ROOM_MOVED = "lf-room-moved";
/** @param {EventTarget} target */
const announceRoom = (target) =>
  target.dispatchEvent(new Event(ROOM_MOVED, { bubbles: true, composed: true }));
/** @param {() => void} callback */
export function watchRoom(callback) {
  const viewport = visualViewport;
  /** @type {[EventTarget, string, boolean?][]} */
  const listening = [
    [window, "resize"],
    [viewport, "scroll"],
    [viewport, "resize"],
    [document, ROOM_MOVED, true],
  ];
  for (const [target, type, capture] of listening)
    target.addEventListener(type, callback, capture);
  const stops = [
    watchScrolls(callback),
    watchLayerChanges(callback),
    () => {
      for (const [target, type, capture] of listening)
        target.removeEventListener(type, callback, capture);
    },
  ];
  return () => {
    for (const stop of stops) stop();
  };
}
// Where, in the window's coordinates, a change of size at `item` would move what the
// user sees, as `{top, bottom}`, or null where it would move nothing seen. A change
// moves everything after it in the boxes that scroll it, in every column, so the band
// spans what the clips over `item` and the chrome leave of the window's height, read as
// `seenRect` reads it but across the whole width. Scroll anchoring keeps still the first
// box in the scroller's landing band (`landingBand`: the spec's optimal viewing region,
// which Chrome and WebKit take from `scroll-padding`), so a change above that band moves
// only what stands above the change. Chrome forfeits that for a layout in which a
// `details` both opens or shuts and changes what it holds, so a writer doing both lays
// out the disclosure first (thread-card.js, an outlet thread settling). The band
// therefore starts at the landing band's top, wherever the seen top stands. Above it, a
// change moves only what is scrolled past, or in the gap between the window's head and
// the band, which it carries up past the head; below it, a change pushes
// down everything after it, even where the seen top stands lower, as a diff's file
// header reaches below the root's band and hides the change. Past the seen foot a change
// moves only what is under the floating panel or below the window. Only heights count: a
// change hidden sideways, by a clip or a pinch zoom's pan, still moves what follows it.
// The scroller that anchors is the innermost with more to scroll than it shows, since
// one that grows with what it holds, such as a code block that scrolls only sideways,
// hands the change out to the box around it; one scrolled to its top anchors nothing, so
// there the band starts at that scroller's own top, wherever the window cuts it.
/** @param {Element} item @param {ClipCache} clips */
function motionBand(item, clips) {
  const walk = clipWalk(item, clips, false);
  const all = { left: -Infinity, top: -Infinity, right: Infinity, bottom: Infinity };
  const heights = walk.cuts.map((each) => ({
    ...each,
    axes: { ...each.axes, x: false },
  }));
  const cut = cutBy(all, heights, item.ownerDocument.scrollingElement, true);
  if (!cut) return null;
  const room = shownWindow({ within: cut });
  if (room.height <= 0) return null;
  const scroller = walk.cuts.find(
    ({ box, scrolls }) => scrolls && box.scrollHeight > box.clientHeight,
  )?.box;
  const anchorBand = !scroller
    ? cut
    : scroller.scrollTop > 0
      ? landingBand(scroller)
      : shownBand(scroller);
  return anchorBand && anchorBand.top < room.bottom
    ? { top: anchorBand.top, bottom: room.bottom }
    : null;
}
// Whether a change of size anywhere in `node` would move what the user sees: some of it
// stands in its `motionBand`. A node not drawn changes nothing.
/** @param {Element} node @param {ClipCache} [clips] */
export function growthIsSeen(node, clips = new Map()) {
  const { top, bottom, height } = node.getBoundingClientRect();
  if (!height) return false;
  const band = motionBand(node, clips);
  return band !== null && bottom > band.top && top < band.bottom;
}
// Whether growth after `node`, at its foot, would move what the user sees: the foot
// stands inside its `motionBand`.
/** @param {Element} node @param {ClipCache} [clips] */
export function growthAfterIsSeen(node, clips = new Map()) {
  const { bottom, height } = node.getBoundingClientRect();
  if (!height) return false;
  const band = motionBand(node, clips);
  return band !== null && bottom > band.top && bottom < band.bottom;
}
// Calls `leave` once `holds(node, clips)` stops holding for every one of `nodes`, and
// again each time it stops after holding once more; returns the step that stops
// watching. `holds` is a reading of geometry such as `seenRect` or `growthIsSeen`. Every
// watch is read in one rendering pass with one clip cache, after anything that changes
// what the page shows of its window (`watchRoom`), or a watched node entering or leaving
// the window, which a change of layout moving it does. A pass calls `leave` only once
// every watch is read, so one that redraws cannot stale another's reading.
/** @type {Set<{read: (clips: ClipCache) => boolean, leave: () => void}>} */
const watches = new Set();
/** @type {ReturnType<typeof nextRender> | null} */
let watchPass = null;
/** @type {(() => void) | null} */
let unlisten = null;
const readWatches = () => {
  watchPass = null;
  const clips = new Map();
  const left = [...watches].filter((watch) => watch.read(clips));
  for (const watch of left) if (watches.has(watch)) watch.leave();
};
const rereadWatches = () => {
  watchPass ??= nextRender(readWatches);
};
/** @param {readonly Element[]} nodes @param {(node: Element, clips: ClipCache) => unknown} holds @param {() => void} leave */
export function whenNone(nodes, holds, leave) {
  /** @type {boolean | null} */
  let held = null;
  const watch = {
    leave,
    // Whether `holds` has just stopped holding for every node.
    /** @param {ClipCache} clips */
    read(clips) {
      const now = nodes.some((node) => node.isConnected && Boolean(holds(node, clips)));
      const stopped = !now && held !== false;
      held = now;
      return stopped;
    },
  };
  watches.add(watch);
  unlisten ??= watchRoom(rereadWatches);
  const observer = new IntersectionObserver(rereadWatches);
  for (const node of nodes) observer.observe(node);
  return () => {
    observer.disconnect();
    watches.delete(watch);
    if (watches.size) return;
    unlisten?.();
    unlisten = null;
    if (watchPass !== null) cancelRender(watchPass);
    watchPass = null;
  };
}

// Where a member begins, as the user sees it: the first of the boxes it paints that
// survives the clips, rather than the bounds of all of them. They are the same box for
// anything in flow and different for an inline that wraps, whose bounds run from the
// column's left margin to its right — so a digit placed on that corner sat four hundred
// pixels from the link it addressed, a line above it, on top of somebody else's sentence.
// `shownBox`'s union answers "how much room does this take", which is what a legend box and
// an aim outline want; this answers "where does it start", which is what anything hung on a
// corner wants. The first that survives rather than the first outright, since a link whose
// opening line has scrolled away still has a corner on the line below it.
/** @param {Element} item @param {ClipCache} clips */
export const startsAt = (item, clips) => {
  const fragments = item.getClientRects();
  return (fragments.length ? [...fragments] : [shownBox(item)])
    .map((box) => clippedRect(box, item, clips))
    .find(Boolean);
};
// The clips standing over a box, applied to it. Taken apart from shownRect because the two
// readings above and a painted Range want the same walk over different boxes.
// `stop` reads only native ancestor bands before that boundary. Viewport, occluders
// and sticky headers belong to the outer plane; margin seats keep their place while
// their CSS frames apply those cuts.
/** @param {Box} box @param {Element} item @param {ClipCache} clips @param {Element} [stop] */
export const clippedRect = (box, item, clips, stop) =>
  clipped(box, item, clips, false, true, stop);
// What cuts paint standing over an item's `box`, by the plane each cut stands in.
// `plane` is the one the paint stands in: the window's where a fixed box escapes every
// clip around it, and the page's otherwise, which the root scroll carries. `bands` are
// the boxes between it and the item whose bands cut it, outermost first, each band less
// the headers stuck over the item's view of it (`headerInset`); each stands in the plane
// of the box that holds it, kept where they cut the box whole. `window` is what the
// window leaves the paint, in the
// window's plane: the room below a header stuck over the root's top, cut, for paint
// stacked `aboveSurfaces`, at the edge of each declared occluder standing over what the
// bands leave of the box, on the side `occluded` keeps, or null where neither cuts it,
// and empty where a cut hides the box whole. Paint stacked under the surfaces is hidden
// by them where they stand. The window's own edges cut nothing in the page's plane, since paint past them
// is not drawn anyway, and cutting it there would move the cut with every scroll. Paint
// over what `item` holds (`held`), as words inside it, is cut by its own band too.
/** @param {Element} item @param {Box} box @param {ClipCache} clips @param {boolean} aboveSurfaces @param {boolean} [held] */
export function paintClips(item, box, clips, aboveSurfaces, held = false) {
  const walk = clipWalk(item, clips, held);
  const plane = walk.fixed ? "window" : "page";
  const root = item.ownerDocument.scrollingElement;
  const hidden = { plane, window: { left: 0, top: 0, right: 0, bottom: 0 }, bands: [] };
  // The root's band is the window's, which cuts only below a header stuck over it.
  let window = walk.cuts.find(({ box: cut, covered }) => cut === root && covered)?.band;
  /** @type {(ClipCut & {band: Box})[]} */
  const bands = [];
  for (const cut of walk.cuts) {
    const band = cut.band;
    if (!band) return hidden;
    if (cut.box !== root) bands.unshift({ ...cut, band });
  }
  let shown = cutBy(box, walk.cuts, root, false);
  // Cut away by the bands, the box keeps them, which a scroll may bring it into; under
  // headers that cover a band whole, it has none to keep.
  if (!shown) return { plane, window: window ?? null, bands };
  for (const { surface, box: over } of aboveSurfaces ? openOccluders(clips) : []) {
    if (
      !overlaps(shown, over) ||
      under(item, surface) ||
      stackOrder(item, surface) >= 0
    )
      continue;
    const left = uncovered(shown, over);
    if (!left) return hidden;
    window ??= layoutWindow(item.ownerDocument);
    window = {
      left: left.left > shown.left ? Math.max(window.left, over.right) : window.left,
      top: left.top > shown.top ? Math.max(window.top, over.bottom) : window.top,
      right:
        left.right < shown.right ? Math.min(window.right, over.left) : window.right,
      bottom:
        left.bottom < shown.bottom ? Math.min(window.bottom, over.top) : window.bottom,
    };
    shown = left;
  }
  return { plane, window: window ?? null, bands };
}
// The same walk for a box drawn in the document plane, which a root scroll carries with
// the page: the page's own boxes cut it, and the window does not, so a box scrolled off
// screen keeps its place for a reader asking how far away it stands.
/** @param {Box} box @param {Element} item @param {ClipCache} clips */
const pagePlaneRect = (box, item, clips) => clipped(box, item, clips, false, false);
// Whether a box Leaf stands against `target` belongs in layout: the target stands within
// a screen of the window, and within 600px of being scrolled into each scroller around
// it, so ordinary scrolling brings the box into layout before it carries the target on
// screen. A box out of layout costs no layout pass, where boxes hidden beside the shown
// ones made every pass revisit them all. `nearObserver` maintains the reading for the
// anchored controls (css-anchors.js, `anchorView`) and paint sets (target-paint-geometry.js,
// `paintSet`); `nearWindow` reads it at once for a first presentation, which cannot wait
// for the observer's first task. It clips at each scroller exactly, so it calls near only
// what the observer will, and the observer's first record adds the rest.
/** @param {IntersectionObserverCallback} callback */
export const nearObserver = (callback) =>
  new IntersectionObserver(callback, { rootMargin: "100%", scrollMargin: "600px" });
/** @param {Element} target @param {ClipCache} [clips] */
export function nearWindow(target, clips = new Map()) {
  if (!target.checkVisibility()) return false;
  const box = pagePlaneRect(shownBox(target), target, clips);
  const { right: width, bottom: height } = layoutWindow();
  return (
    box !== null &&
    box.bottom >= -height &&
    box.top <= 2 * height &&
    box.right >= -width &&
    box.left <= 2 * width
  );
}
// The same walk for a box measured from what an element holds: a Range inside it. The
// holder's own band stands over its contents, where it says nothing about the holder's
// own box, so text scrolled out of the `pre` it sits in directly is text nobody sees.
/** @param {Box} box @param {Element} holder @param {ClipCache} clips @param {Element} [stop] */
export const clippedContents = (box, holder, clips, stop) =>
  clipped(box, holder, clips, true, true, stop);
/** @param {Box} box @param {Element} item @param {ClipCache} clips @param {boolean} held @param {boolean} [inWindow] @param {Element} [stop] */
function clipped(box, item, clips, held, inWindow = true, stop) {
  const root = item.ownerDocument.scrollingElement;
  const shown = cutBy(
    box,
    clipWalk(item, clips, held, stop).cuts,
    root,
    inWindow && !stop,
  );
  return stop ? shown : shown && occluded(shown, item, clips);
}
// `box` less the bands of `cuts`, each on the axes it clips, or null where they leave
// none of it. In the window's plane the window cuts it; in the page's plane the root's
// band is the window, which cuts nothing there, and only a header stuck over its top
// does.
/** @param {Box} box @param {ClipCut[]} cuts @param {Element | null} root @param {boolean} inWindow */
function cutBy(box, cuts, root, inWindow) {
  let shown = inWindow ? intersect(box, layoutWindow()) : box;
  for (const { box: cut, band, axes, covered } of cuts) {
    if (!band) return null;
    const edges =
      !inWindow && cut === root
        ? {
            left: -Infinity,
            top: covered ? band.top : -Infinity,
            right: Infinity,
            bottom: Infinity,
          }
        : band;
    shown = intersect(shown, edges, axes);
  }
  const { left, top, right, bottom } = shown;
  return hasArea(shown) ? { left, top, right, bottom } : null;
}
// The clips standing over an item, innermost first: each ancestor whose band cuts it,
// with that band less the headers stuck over its top and the footers over its foot, and
// whether a fixed box among the item's ancestors escapes every clip further out, the
// root's included.
/** @param {Element} item @param {ClipCache} clips @param {boolean} held @param {Element} [stop] */
function clipWalk(item, clips, held, stop) {
  // From the box itself, not from its parent: an element is not clipped by its own
  // overflow — that clips what it holds — so its band is skipped and only its position is
  // read. Its position matters when the item is itself fixed: a fixed box escapes its
  // ancestors' clips, so in design mode the floating panel the aim resolves is not
  // clipped away by body's band.
  // Cross an open shadow boundary through its host. A package surface rendered in a
  // declared shadow stage is still clipped by that host and by the page containers
  // outside it; stopping at the ShadowRoot would let chrome paint where the package
  // itself cannot.
  // Where the sticky headers over each scroller's top and footers over its foot are read
  // (`headerInset`, `footerInset`): the item, until a box that scrolls starts the slots
  // again for what it holds, and that box's parent from there out. The walk passes every
  // such box on its way, so it carries the place rather than climbing to it at each cut.
  /** @type {Element | null} */
  let holder = item;
  let escaped = false;
  /** @type {Element | null | undefined} */
  let containing = null;
  /** @type {ClipCut[]} */
  const cuts = [];
  /** @type {Element | null} */
  let a = item;
  for (; a && a !== stop; a = renderedParent(a)) {
    let c = clips.get(a);
    if (c === undefined) {
      clips.set(
        a,
        (c = {
          band: shownBand(a),
          axes:
            a === a.ownerDocument.scrollingElement
              ? { x: true, y: true }
              : clippingAxes(getComputedStyle(a)),
          // Read here rather than out of shownBand, whose answer is a band and is the
          // render gate's too: what clips a box and what a box is positioned against are
          // two facts, and one of them is this walk's alone.
          positioned:
            isHTML(a) && ["fixed", "absolute"].includes(getComputedStyle(a).position),
          block: isHTML(a) ? a.offsetParent : undefined,
          scrolls: scrollContainer(a),
        }),
      );
    }
    if (escaped && a === containing) escaped = false;
    if (!escaped && (held || a !== item) && c.band) {
      const covered =
        c.band.top + (!stop && c.scrolls ? insetAt(holder, a, ...TOP) : 0);
      const footed =
        c.band.bottom - (!stop && c.scrolls ? insetAt(holder, a, ...FOOT) : 0);
      cuts.push({
        box: a,
        axes: c.axes,
        scrolls: c.scrolls,
        covered: c.axes.y && covered > c.band.top,
        footed: c.axes.y && footed < c.band.bottom,
        band:
          c.axes.y && covered >= footed
            ? null
            : c.axes.y
              ? { ...c.band, top: covered, bottom: footed }
              : c.band,
      });
    }
    if (c.scrolls) holder = renderedParent(a);
    if (!escaped && c.positioned) {
      escaped = true;
      containing = c.block;
    }
  }
  return { cuts, fixed: escaped && !containing };
}

// A surface that stands over the page without clipping it: a view open in the floating
// panel, over the page's foot (floating-panel.js). Nothing in the page's own tree says so,
// since the surface is fixed chrome beside the page rather than an ancestor of what it
// stands over, so the surface declares itself. The
// clip walk then takes what it stands over away from any box stacked beneath it, and a
// travel destination, an exposure reading, and a badge's placement all read the part
// under it as hidden. What the surface holds is its own to show, and what stacks above
// it (a door's menu, the key-badge layer, the top layer) is drawn over it rather than
// hidden by it.
//
// What is left of a box is a box: the largest rectangle of it the occluder leaves, so
// every pixel of the answer is one the user sees, and a box the occluder reaches into
// reads as less than whole.
/** @type {Set<HTMLElement>} */
const occluders = new Set();
// Whether a declared occluder stands now: rendered. A disconnected surface has no box,
// so `checkVisibility` answers for that too.
/** @param {Element} surface */
const standsNow = (surface) => surface.checkVisibility();
// Where an occluder stands, not where its slide has carried it this frame: every declared
// occluder is fixed to the window or stands in a box that is, so its offsets, summed up
// to that box, are its viewport box without the slide's transform. Each offset runs
// from inside its parent's border, which the sum steps across.
/** @param {HTMLElement} surface */
function restingBox(surface) {
  let left = 0,
    top = 0;
  /** @type {Element | null} */
  let at = surface;
  for (; at && isHTML(at); at = at.offsetParent) {
    left += at.offsetLeft + (at === surface ? 0 : at.clientLeft);
    top += at.offsetTop + (at === surface ? 0 : at.clientTop);
  }
  return {
    left,
    top,
    right: left + surface.offsetWidth,
    bottom: top + surface.offsetHeight,
  };
}
/** @param {HTMLElement} surface */
export const declareOccluder = (surface) => {
  occluders.add(surface);
  watchChrome(surface);
  return () => {
    occluders.delete(surface);
    chromeSizes.unobserve(surface);
    announceRoom(document);
  };
};
// Where the surface standing at the window's right edge begins, or Infinity where none
// stands. What is laid out beside the page, as the comment box is, keeps left of it.
export function rightCover() {
  const edge = layoutWindow().right;
  let left = Infinity;
  for (const surface of occluders) {
    if (!standsNow(surface)) continue;
    const box = restingBox(surface);
    if (box.left > 0 && box.right >= edge - 1) left = Math.min(left, box.left);
  }
  return left;
}
// A clip pass that reads past some occluders. Travel asks what the page shows of a
// destination beside the surface it leaves open, which is the most any movement of
// the page can show while that surface stands.
const PAST = Symbol("past");
/** @param {Iterable<HTMLElement>} surfaces @returns {ClipCache} */
const clipsPast = (surfaces) => {
  /** @type {ClipCache} */
  const clips = new Map();
  clips.set(PAST, new Set(surfaces));
  return clips;
};
// A clip pass that reads past every occluder, for what stands above them all: a list in
// the top layer still hangs from a trigger a panel view stands over.
export const clipsPastSurfaces = () => clipsPast(occluders);
// How much of a destination, an element or a Range, an occluder stands over, from 0 to
// 1: of what the page's clips leave of it, or of the box travel will land it at
// (`landed`, landing-scroll.js `landedBox`). Travel moves a destination along its
// scroller's block axis only, so a surface standing the whole height of the room the
// page shows would cover every place the landing can bring it to, and the share is the
// inline one, of its width. One scrolled out of the window is asked it at its own box.
// A surface standing over part of that height, as a view open in the floating panel
// stands over its foot, covers a destination only where it stands, so the share is of
// its area there. What holds the surface, as the chrome's dialog holds the panel, is
// not covered by it. A destination is hidden where more than half of it is covered
// (`hides`); travel, which promises the whole of it, asks of any part
// (floating-panel.js, `clearFor`).
/** @param {HTMLElement} surface @param {Element | Range} where @param {Box | null} [landed] */
export function coveredShare(surface, where, landed = null) {
  const holder = placeHolder(where);
  if (!holder || !occluders.has(surface) || !standsNow(surface)) return 0;
  if (under(holder, surface) || under(surface, holder)) return 0;
  if (stackOrder(holder, surface) >= 0) return 0;
  const box = landed ?? placeBox(where);
  const { left, top, right, bottom } =
    landed ?? clippedPlace(where, clipsPast([surface]), box) ?? box;
  const over = restingBox(surface);
  const across = Math.max(0, Math.min(right, over.right) - Math.max(left, over.left));
  const room = shownWindow({ viewport: "layout" });
  if (over.top <= room.top + 1 && over.bottom >= room.bottom - 1)
    return across / (right - left || 1);
  const down = Math.max(0, Math.min(bottom, over.bottom) - Math.max(top, over.top));
  return (across * down) / ((right - left) * (bottom - top) || 1);
}
/** @param {HTMLElement} surface @param {Element | Range} where */
const hides = (surface, where) => coveredShare(surface, where) > 0.5;
// Whether any open occluder hides `where`, by the same measure. A seat a panel stands
// over is no place to put the user, since the panels dominate what focus reaches.
/** @param {Element | Range} where */
export const underOccluder = (where) =>
  [...occluders].some((surface) => hides(surface, where));
// The element a destination is measured through: itself, or the element holding a
// Range's start.
/** @param {Element | Range} where */
export const placeHolder = (where) =>
  where instanceof Range
    ? isElement(where.startContainer)
      ? where.startContainer
      : where.startContainer.parentElement
    : where;
// A destination's box: a Range's own, or an element's shown box (`shownBox`).
/** @param {Element | Range} where */
export const placeBox = (where) =>
  where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
// What the page's clips leave of a destination's `box`: a Range's walked from the
// element holding it (`clippedContents`), an element's from itself (`clippedRect`).
/** @param {Element | Range} where @param {ClipCache} clips @param {Box} [box] */
export const clippedPlace = (where, clips, box = placeBox(where)) => {
  if (!(where instanceof Range)) return clippedRect(box, where, clips);
  const holder = placeHolder(where);
  return holder && clippedContents(box, holder, clips);
};
// Compare the planes the browser paints, then the root stacking levels inside
// one plane. The native layer owner supplies opening order. Within the chrome's
// permanent layer the panel, threads and marks retain their own z-index ladder.
/** @param {Element} node */
const stacking = (node) => {
  let level = 0;
  /** @type {Element | null} */
  let at = node;
  for (; at; at = renderedParent(at)) {
    if (isNativeLayer(at)) return { layer: at, level };
    const { position, zIndex } = getComputedStyle(at);
    if (position !== "static" && zIndex !== "auto") level = Number(zIndex);
  }
  return { layer: null, level };
};
/** @param {Element} left @param {Element} right */
export function stackOrder(left, right) {
  const a = stacking(left),
    b = stacking(right);
  if (a.layer === b.layer) return a.level - b.level;
  const layers = nativeLayers();
  return (
    layers.findIndex(({ root }) => root === a.layer) -
    layers.findIndex(({ root }) => root === b.layer)
  );
}
const OCCLUDERS = Symbol("occluders");
/** @param {ClipCache} clips */
function openOccluders(clips) {
  let open = clips.get(OCCLUDERS);
  if (open) return open;
  const past = clips.get(PAST);
  open = [...occluders]
    .filter(standsNow)
    .filter((surface) => !past?.has(surface))
    .map((surface) => ({
      surface,
      box: restingBox(surface),
    }));
  clips.set(OCCLUDERS, open);
  return open;
}
/** @param {Box} box */
const area = (box) => (box.right - box.left) * (box.bottom - box.top);
/** @param {Box} rect @param {Element} item @param {ClipCache} clips */
function occluded(rect, item, clips) {
  for (const { surface, box } of openOccluders(clips)) {
    if (!overlaps(rect, box) || under(item, surface) || stackOrder(item, surface) >= 0)
      continue;
    const remaining = uncovered(rect, box);
    if (!remaining) return null;
    rect = remaining;
  }
  return rect;
}
// The largest part of `rect` that `box` does not stand over, or null where it covers it.
/** @param {Box} rect @param {Box} box */
function uncovered(rect, box) {
  if (!overlaps(rect, box)) return rect;
  const sides = [
    { ...rect, right: Math.min(rect.right, box.left) },
    { ...rect, left: Math.max(rect.left, box.right) },
    { ...rect, bottom: Math.min(rect.bottom, box.top) },
    { ...rect, top: Math.max(rect.top, box.bottom) },
  ].filter((side) => side.right > side.left && side.bottom > side.top);
  return sides.length
    ? sides.reduce((most, side) => (area(side) > area(most) ? side : most))
    : null;
}
