/* This module owns the shared readings of visible boxes and clipping, how much of the
 * window the page shows, and the one conversion from viewport boxes to
 * document-positioned chrome. */
import { excludedByInert, renderedParent, uiInside, under, upFrom } from "./shadow.js";
import { nativeModalAdmits, watchLayerChanges } from "./keyboard/layer-stack.js";
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
import { sampleVisibility } from "./sample-visibility.js";

/* Shared readings of the boxes the page actually shows.

   `shownBox` returns an element's own box or the union of the boxes its
   `display: contents` descendants paint. `shownParts` returns the visible elements on
   which an outline can be drawn, and `shownExtent` the box they cover together.
   `shownRect` clips an element's `shownBox` through scrolling ancestors' visible bands (less the sticky headers stuck over their tops) and the viewport,
   following native positioned containing blocks past intermediate overflow clips,
   then takes away what a declared occluder stands over (`declareOccluder`). It is what a box may be drawn over, which
   chrome can be: the banner and the shortcut bar are drawn above the page, not cut out
   of it. `seenRect` holds that to the room the chrome leaves (`shownWindow`), and it is
   the one reading of whether the user can see something.
   `clippedRect` applies that same clipping walk to a box measured some other way for an
   element, and `clippedContents` to a box measured from a Range, starting at the element
   that holds the Range and counting that element's own clip. Use:

   - `shownBox` for travel, bounds, and reading-position landmarks;
   - `shownParts` for ask rings and element-anchor outlines;
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
   - `presented`, `frameView` and `containingView` for whether the page puts a box
     before the user at all and what the pages holding this one show of its window, and
     `watchRoom` for when any of those readings may have changed.

   `skipped` is asked first by a reading that can leave out a box the browser is not
   drawing, since reading one in skipped content forces that content's style and layout.

   Do not read `getBoundingClientRect()` directly when the target may generate no box.
   A `display: contents` element reports an origin-like zero rectangle that does not
   represent where its contents are. An area greater than zero is not enough for shown
   parts either: clipped note text and hoisted controls can have measurable boxes while
   remaining the wrong semantic target, which is why `shownParts` takes the bounded
   chrome question (`uiInside`). `unmarkableElements`, in the render checks, detects
   declared items with no visible part on which a mark can land. */
// Where the page's shell ends on the right — the far edge of the room the document has,
// which is what a margin resident is placed against and what the response surface may not
// overhang. The auxiliary surfaces stand over the page and take none of it.
export const shellRight = () => document.body.getBoundingClientRect().right;

// How much of the window the page shows: the visible viewport, less the chrome fixed to
// its edges: the banner over its head, and the boxes the bottom bar's owner and the
// floating panel stand. Each stands over the page without clipping it, so no clip walk
// finds it; its owner declares it here (`declareBanner`, banner.js; `declareWindowChrome`,
// keyboard/shortcut-bar.js and floating-panel.js), and every reading of the room the page
// has starts from `bannerFoot` or `shownWindow` rather than measuring the chrome itself.
//
// The banner's foot is its painted edge, since its declared height (`--lf-banner-h`) is a
// safe-area `calc()` whose serialized value is not a number. The other chrome is read as
// the boxes standing in it rather than as a stated height (`--lf-bottom-bar-h`), because
// the status rises above a covering panel's foot, and stands at the window's head over
// the floating panel; each box bounds only the room it stands across, from the edge it
// stands nearer.
//
// The visible viewport is the part of the window the user sees: pinch zoom and a phone's
// software keyboard shrink it without resizing the layout viewport the page and its fixed
// chrome are laid out in, and a surface placed in the layout viewport alone can stand
// under the keyboard. `within` narrows the room to a box the caller keeps to, such as a
// reading region's shown bounds, and `gap` holds what stands in the room that far inside
// each of its edges. `viewport: "layout"` reads the room in the layout viewport instead,
// the window the page scrolls through, for a caller asking whether a scroll has carried
// something out of the page's room rather than whether the user can see it.
//
// Each bar's owner also hands over the elements it draws, and a change of their size is
// announced as `ROOM_MOVED` (`watchRoom`), as is an occluder's (`declareOccluder`): a
// coarse pointer arriving deepens the banner's rows, the shortcut bar wraps as its hints
// change, and a panel opens, shuts or is dragged wider, each with no scroll or resize
// for a reader to hear.
let banner = null;
const windowChrome = new Set();
const chromeSizes = sizeObserver(() => announceRoom(document));
const watchChrome = (element) => chromeSizes.observe(element, { box: "border-box" });
export const declareBanner = (element) => {
  banner = element;
  watchChrome(element);
};
export const declareWindowChrome = (boxes, elements) => {
  windowChrome.add(boxes);
  elements.forEach(watchChrome);
};
// Every box the declared window chrome stands now, for a reading that keeps clear of
// them all, as Go-to's chips and a search's marks do.
export const windowChromeBoxes = () => [...windowChrome].flatMap((boxes) => boxes());
export const bannerFoot = () => banner?.getBoundingClientRect().bottom ?? 0;
// The layout viewport's box, less the scrollbars the root draws at its edges, where
// nothing the page shows stands: `innerWidth` and `innerHeight` count a classic
// scrollbar. Every reading of the whole window's box starts here, `doc`'s for a sample
// asking it of its containing page.
export const layoutWindow = (doc = document) => ({
  left: 0,
  top: 0,
  right: doc.documentElement.clientWidth,
  bottom: doc.documentElement.clientHeight,
});
export function shownWindow({ within = null, gap = 0, viewport = "visual" } = {}) {
  const layout = layoutWindow();
  const { offsetLeft, offsetTop, width, height } =
    viewport === "visual"
      ? window.visualViewport
      : { offsetLeft: 0, offsetTop: 0, width: layout.right, height: layout.bottom };
  const left = Math.max(offsetLeft, within?.left ?? -Infinity) + gap;
  const right = Math.min(offsetLeft + width, within?.right ?? Infinity) - gap;
  let top = Math.max(offsetTop, bannerFoot(), within?.top ?? -Infinity);
  let bottom = Math.min(offsetTop + height, within?.bottom ?? Infinity);
  const middle = offsetTop + height / 2;
  for (const box of windowChromeBoxes()) {
    if (!overlapsAcross(box, { left, right })) continue;
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
export function shownBand(el) {
  const doc = el.ownerDocument;
  // The root element's border box travels with the document, while its scrollport stays
  // pinned to the viewport. Every other scroller's visible band can be derived from its
  // own box; the root is the platform-defined exception.
  if (el === doc.scrollingElement) return layoutWindow(doc);
  const s = doc.defaultView.getComputedStyle(el);
  const axes = clippingAxes(s);
  if (!axes.x && !axes.y) return null;
  const b = el.getBoundingClientRect();
  const scaleX = el.offsetWidth ? b.width / el.offsetWidth : 1;
  const scaleY = el.offsetHeight ? b.height / el.offsetHeight : 1;
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
// It clears what stands over the whole scroller (the banner, a page tab strip); a header
// over part of it, a diff's file header, is cleared by the `scroll-margin` of the rows
// it stands over. It is also where scroll anchoring looks for the box it keeps still:
// the spec's optimal viewing region, which Chrome reads from `scroll-padding` too
// (`motionBand`).
//
// A box scrolls, for these readings, when its computed overflow makes it a scroll
// container: `auto` and `scroll`, and `hidden` too, which a script or a landing can
// scroll though the user cannot, and which is the scroller a sticky box inside it sticks
// in. The runtime asks it of what a motion scrolls and which boxes scroll what they
// hold (scroll-motion.js, `scrollsContent`), and of the boxes that hold sticky headers
// (`scrollContainer`). `userScrollport` is the same test without `hidden`: what the
// user, rather than a script, can scroll, which keyboard stops and edge marks read
// (reach.js, `paintSlot`), and the render checks asking what a reader can reach.
export const scrollport = (overflow) => /^(auto|scroll|hidden)$/.test(overflow);
export const userScrollport = (overflow) => /^(auto|scroll)$/.test(overflow);
export const scrollsBy = ({ overflowX, overflowY }) =>
  scrollport(overflowX) || scrollport(overflowY);
const scrolls = (el) => scrollsBy(getComputedStyle(el));
// A scroll container: the document's own scroller, or a box whose overflow scrolls.
export const scrollContainer = (box) =>
  box === box.ownerDocument.scrollingElement || scrolls(box);
// How far below the top of `scroller`'s band the view of `el` starts, past the sticky
// headers stuck over it. Each header adds its stated height to `--lf-top` for what it
// stands over (theme.css), so where the `--lf-top` computed at `el` exceeds the
// scroller's own, headers stand over `el`, and their foot is that value below the
// scroller's padding edge, where a sticky box is measured from. The root's own value is
// the banner, which is left to `shownWindow`, so with no header over `el` nothing is
// taken. A header that is not stuck stands above its content, so the reading holds
// whether it is stuck or not, except at the end of what the header stands over, where
// the header is pushed up with it and the reading still counts its height as covered. A
// header sticks in a box that scrolls, so a box that only clips (`overflow: clip`, paint
// containment) has none over it. A box that scrolls starts `--lf-top` again for what it
// holds, so the value is read past every box between `el` and `scroller` that scrolls,
// at the parent of the outermost: inside a sideways scroller the value counts from that
// scroller, and the headers over `scroller`'s band are those outside it. A header's
// holder puts the stacked value on a box that does not scroll (theme.css, at `--lf-top`).
const slotHolder = (el, scroller) => {
  let at = el;
  for (let box = el; box && box !== scroller; box = upFrom(box))
    if (box.nodeType === 1 && scrolls(box)) at = upFrom(box);
  return at;
};
// The inset read at `at`, the box where the slot counts from `scroller`.
const insetAt = (at, scroller, slot, padding) => {
  const read = (box) =>
    Number.parseFloat(getComputedStyle(box).getPropertyValue(slot)) || 0;
  const inset = at?.nodeType === 1 ? read(at) : 0;
  if (inset <= read(scroller)) return 0;
  return (Number.parseFloat(getComputedStyle(scroller)[padding]) || 0) + inset;
};
const TOP = ["--lf-top", "paddingTop"];
const FOOT = ["--lf-bottom", "paddingBottom"];
const edgeInset = (el, scroller, edge) =>
  !scrollContainer(scroller) || el === scroller
    ? 0
    : insetAt(slotHolder(el, scroller), scroller, ...edge);
export const headerInset = (el, scroller) => edgeInset(el, scroller, TOP);
// The same reading at the foot, for a box sticking there (`--lf-bottom`, theme.css):
// how far above the bottom of `scroller`'s band the view of `el` ends.
const footerInset = (el, scroller) => edgeInset(el, scroller, FOOT);
export function visibleBand(scroller, item = null) {
  const band = shownBand(scroller);
  if (!band || !item) return band;
  const top = band.top + headerInset(item, scroller);
  const bottom = band.bottom - footerInset(item, scroller);
  return bottom > top ? { ...band, top, bottom } : null;
}
// The sticky box holding `node` while it is stuck, else null. A stuck box stands at the
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
export function stuckBox(node, within = null) {
  for (let el = node; el?.nodeType === 1 && el !== within; el = renderedParent(el))
    if (getComputedStyle(el).position === "sticky" && sticks(el)) return el;
  return null;
}
// Whether `sticky` stands where sticking holds it, in the scroller around it. A sticky
// box that clips what it holds, as a tab strip does, still sticks in that scroller.
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
  while (parent !== scroller && getComputedStyle(parent).display === "contents")
    parent = renderedParent(parent);
  const content = band.top - scroller.scrollTop;
  const holder =
    parent === scroller
      ? { top: content + padTop, bottom: content + scroller.scrollHeight - padBottom }
      : shownBox(parent);
  const topLine = band.top + padTop + Number.parseFloat(style.top);
  const footLine = band.bottom - padBottom - Number.parseFloat(style.bottom);
  if (box.top <= topLine + 1 && holder.top < box.top - 1) return true;
  if (Math.abs(box.bottom - footLine) <= 1) return true;
  return box.bottom > footLine && holder.bottom > box.bottom + 1;
}
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
export function landingInsets(scroller) {
  const style = getComputedStyle(scroller);
  const inset = (side) => Number.parseFloat(style[`scrollPadding${side}`]) || 0;
  return {
    top: inset("Top"),
    right: inset("Right"),
    bottom: inset("Bottom"),
    left: inset("Left"),
  };
}
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
export const skipped = (el) =>
  document.documentElement.lfInitial.skipped(el, renderedParent);
// The box an element shows as. An element that generates none of its own — a
// display: contents wrapper — shows as what its contents paint, so its bounds are
// theirs, and a range asks the platform for that union in one read. Its own rect is
// (0,0) at the document's origin, which is not a degenerate box but a wrong one: it
// reads as a real place at the top of the page, so whatever measured it travelled there.
//
// No widget in the vocabulary displays as contents, but the wrong answer is the
// platform's rather than any widget's: a page or a project layer styles any wrapper
// this way in a line. So the answer is a fact about elements, kept here rather than in
// one reader, and every reader asks this one function where an element is.
export function shownBox(el) {
  if (el === document.scrollingElement) {
    const { left, top, right, bottom } = shownBand(el);
    return new DOMRect(left, top, right - left, bottom - top);
  }
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
// The box an element's shown parts cover together: a mark hung on the element stands at
// its corner, so a comment on one shape of a drawing stands on that shape rather than at
// the drawing's edge. An element with no shown part has none.
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
export function shownRect(item, clips) {
  return clippedRect(shownBox(item), item, clips);
}
// What of an item the user sees: what every box over it lets through, within the room the
// chrome leaves. `within` keeps a bottom-bar box from cutting the item unless it stands
// across it. The chrome cuts the item's top and foot only; its sides stay shownRect's, the
// layout viewport's, since a pinch zoom's visual viewport is a pan across the page and not
// a clip — read with its sides, a message wider than the zoomed view was never seen whole
// across, and never counted read. Null when none of it shows.
export function seenRect(item, clips) {
  const shown = shownRect(item, clips);
  if (!shown) return null;
  const room = shownWindow({ within: shown });
  return room.width > 0 && room.height > 0
    ? { left: shown.left, top: room.top, right: shown.right, bottom: room.bottom }
    : null;
}
// Whether the page puts `node` before the user at all, before any question of where:
// drawn and visible, not inert, inside the topmost modal, and not hidden with
// `aria-hidden`. Exposure asks it of a message body and of each frame holding the page.
export function presented(node) {
  if (
    !node.checkVisibility({ visibilityProperty: true }) ||
    excludedByInert(node) ||
    !nativeModalAdmits(node)
  )
    return false;
  for (let at = node; at; at = renderedParent(at))
    if (at.getAttribute?.("aria-hidden") === "true") return false;
  return true;
}
// What this page shows of a frame it holds, in the frame's own viewport coordinates:
// the frame's `seenRect`, within `within`, what the pages holding this one show of its
// window (`containingView`), or null where the user sees none of it. The frame's page
// cannot read this itself: only this page's module knows the banner, bottom bar and
// occluders standing over the frame, which cut it as they cut any of this page's boxes.
export function frameView(frame, within) {
  const seen = seenRect(frame, new Map());
  const shown = seen && intersect(seen, within);
  if (!shown || !hasArea(shown)) return null;
  const rect = frame.getBoundingClientRect();
  const scaleX = rect.width / frame.offsetWidth || 1;
  const scaleY = rect.height / frame.offsetHeight || 1;
  const x = (at) => (at - rect.left) / scaleX - frame.clientLeft;
  const y = (at) => (at - rect.top) / scaleY - frame.clientTop;
  return {
    left: x(shown.left),
    top: y(shown.top),
    right: x(shown.right),
    bottom: y(shown.bottom),
  };
}
// What the pages holding this one show of its window, in its own coordinates: the whole
// window at the top, and in a same-origin frame what the holding page reads of that
// frame (`frameView`), asked through the holder's document, where its own geometry
// answers and asks its own holder in turn. Null where no holder answers: a cross-origin
// holder hides the frame element, and one without Leaf declares none of its chrome, so
// nothing it shows is evidence. An isolated sample's holder answers over the sample's
// port instead (sample-visibility.js), from the same `frameView`.
const FRAME_VIEW = Symbol.for("leaf.frameView");
Object.defineProperty(document, FRAME_VIEW, {
  value: (frame) => {
    const within = presented(frame) && containingView();
    return within ? frameView(frame, within) : null;
  },
});
// The frame holding this page, where its holder is of this origin. An isolated sample's
// holder is another origin, which answers over the sample's port, and WebKit reports
// even reading `frameElement` there as a sandbox violation.
const holdingFrame = () => (sampleVisibility() ? null : window.frameElement);
export function containingView() {
  const frame = holdingFrame();
  if (!frame) return window === window.top ? layoutWindow() : null;
  return frame.ownerDocument[FRAME_VIEW]?.(frame) ?? null;
}
// Everything besides a reader's own boxes that changes what `seenRect` and
// `containingView` read, so a reader of what the user sees watches it here rather than
// keeping its own list: a scroll, a shadow stage's included (`watchScrolls`); a resize;
// the visual viewport, which a soft keyboard or a pinch-pan moves without either; a
// native layer opening or closing, which changes what a modal admits
// (`watchLayerChanges`); and chrome the room is measured against changing size or
// ending a slide (`ROOM_MOVED`). In a same-origin frame it watches the same of the
// holding page, through its document, and of the pages holding that one in turn, and
// the frame moving in its holder's viewport, which no event in either page announces.
// Returns the call that stops watching.
const ROOM_MOVED = "lf-room-moved";
export const announceRoom = (target) =>
  target.dispatchEvent(new Event(ROOM_MOVED, { bubbles: true, composed: true }));
const WATCH_ROOM = Symbol.for("leaf.watchRoom");
Object.defineProperty(document, WATCH_ROOM, {
  value: (callback) => watchRoom(callback),
});
export function watchRoom(callback) {
  const viewport = window.visualViewport;
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
  const frame = holdingFrame();
  const holder = frame?.ownerDocument[WATCH_ROOM];
  if (holder) {
    // What this page leaves in its holder goes with the page, whether or not the
    // watcher ever stops, so a reloaded frame leaves no listener of its old self there.
    const moves = new frame.ownerDocument.defaultView.IntersectionObserver(callback, {
      threshold: [0, 1],
    });
    moves.observe(frame);
    const unhold = holder(callback);
    const leave = (event) => {
      if (!event.persisted) stopHolding();
    };
    const stopHolding = () => {
      moves.disconnect();
      unhold();
      window.removeEventListener("pagehide", leave);
    };
    window.addEventListener("pagehide", leave);
    stops.push(stopHolding);
  }
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
// change moves only what is under the banner, scrolled past, or in the gap between the
// banner and the band, which it carries up under the banner; below it, a change pushes
// down everything after it, even where the seen top stands lower, as a diff's file
// header reaches below the root's band and hides the change. Past the seen foot a change
// moves only what is under the bottom bar or below the window. Only heights count: a
// change hidden sideways, by a clip or a pinch zoom's pan, still moves what follows it.
// The scroller that anchors is the innermost with more to scroll than it shows, since
// one that grows with what it holds, such as a code block that scrolls only sideways,
// hands the change out to the box around it; one scrolled to its top anchors nothing, so
// there the band starts at that scroller's own top, wherever the window cuts it.
export function motionBand(item, clips) {
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
  const anchors = !scroller
    ? cut.top
    : scroller.scrollTop > 0
      ? landingBand(scroller).top
      : shownBand(scroller).top;
  return anchors < room.bottom ? { top: anchors, bottom: room.bottom } : null;
}
// Whether a change of size anywhere in `node` would move what the user sees: some of it
// stands in its `motionBand`. A node not drawn changes nothing.
export function growthIsSeen(node, clips = new Map()) {
  const { top, bottom, height } = node.getBoundingClientRect();
  if (!height) return false;
  const band = motionBand(node, clips);
  return Boolean(band) && bottom > band.top && top < band.bottom;
}
// Whether growth after `node`, at its foot, would move what the user sees: the foot
// stands inside its `motionBand`.
export function growthAfterIsSeen(node, clips = new Map()) {
  const { bottom, height } = node.getBoundingClientRect();
  if (!height) return false;
  const band = motionBand(node, clips);
  return Boolean(band) && bottom > band.top && bottom < band.bottom;
}
// Calls `leave` once `holds(node, clips)` stops holding for every one of `nodes`, and
// again each time it stops after holding once more; returns the step that stops
// watching. `holds` is a reading of geometry such as `seenRect` or `growthIsSeen`. Every
// watch is read in one rendering pass with one clip cache, after anything that changes
// what the page shows of its window (`watchRoom`), or a watched node entering or leaving
// the window, which a change of layout moving it does. A pass calls `leave` only once
// every watch is read, so one that redraws cannot stale another's reading.
const watches = new Set();
let watchPass = null;
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
export function whenNone(nodes, holds, leave) {
  let held = null;
  const watch = {
    leave,
    // Whether `holds` has just stopped holding for every node.
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
    unlisten();
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
export const startsAt = (item, clips) => {
  const fragments = item.getClientRects();
  return (fragments.length ? [...fragments] : [shownBox(item)])
    .map((box) => clippedRect(box, item, clips))
    .find(Boolean);
};
// The clips standing over a box, applied to it. Taken apart from shownRect because the two
// readings above and a painted Range want the same walk over different boxes.
const clippedRect = (box, item, clips) => clipped(box, item, clips, false);
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
export function paintClips(item, box, clips, aboveSurfaces, held = false) {
  const walk = clipWalk(item, clips, held);
  const plane = walk.fixed ? "window" : "page";
  const root = item.ownerDocument.scrollingElement;
  const hidden = { plane, window: { left: 0, top: 0, right: 0, bottom: 0 }, bands: [] };
  // The root's band is the window's, which cuts only below a header stuck over it.
  let window = walk.cuts.find(({ box: cut, covered }) => cut === root && covered)?.band;
  const bands = walk.cuts.filter(({ box: cut }) => cut !== root).reverse();
  let shown = cutBy(box, walk.cuts, root, false);
  // Cut away by the bands, the box keeps them, which a scroll may bring it into; under
  // headers that cover a band whole, it has none to keep.
  if (!shown)
    return walk.cuts.some(({ band }) => !band)
      ? hidden
      : { plane, window: window ?? null, bands };
  for (const { surface, box: over, level } of aboveSurfaces
    ? openOccluders(clips)
    : []) {
    if (!overlaps(shown, over) || under(item, surface) || stackLevel(item) >= level)
      continue;
    const left = uncovered(shown, over);
    if (!left) return hidden;
    window ??= shownBand(root);
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
export const nearObserver = (callback) =>
  new IntersectionObserver(callback, { rootMargin: "100%", scrollMargin: "600px" });
export function nearWindow(target, clips = new Map()) {
  if (!target.checkVisibility()) return false;
  const box = pagePlaneRect(shownBox(target), target, clips);
  const { right: width, bottom: height } = layoutWindow();
  return (
    Boolean(box) &&
    box.bottom >= -height &&
    box.top <= 2 * height &&
    box.right >= -width &&
    box.left <= 2 * width
  );
}
// The same walk for a box measured from what an element holds: a Range inside it. The
// holder's own band stands over its contents, where it says nothing about the holder's
// own box, so text scrolled out of the `pre` it sits in directly is text nobody sees.
export const clippedContents = (box, holder, clips) =>
  clipped(box, holder, clips, true);
function clipped(box, item, clips, held, inWindow = true) {
  const root = item.ownerDocument.scrollingElement;
  const shown = cutBy(box, clipWalk(item, clips, held).cuts, root, inWindow);
  return shown && occluded(shown, item, clips);
}
// `box` less the bands of `cuts`, each on the axes it clips, or null where they leave
// none of it. In the window's plane the window cuts it; in the page's plane the root's
// band is the window, which cuts nothing there, and only a header stuck over its top
// does.
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
function clipWalk(item, clips, held) {
  // From the box itself, not from its parent: an element is not clipped by its own
  // overflow — that clips what it holds — so its band is skipped and only its position is
  // read. Its position matters when the item is itself fixed: a fixed box escapes its
  // ancestors' clips, so in design mode the thread panel the aim resolves is not clipped
  // away by body's band.
  // Cross an open shadow boundary through its host. A package surface rendered in a
  // declared shadow stage is still clipped by that host and by the page containers
  // outside it; stopping at the ShadowRoot would let chrome paint where the package
  // itself cannot.
  // Where the sticky headers over each scroller's top and footers over its foot are read
  // (`headerInset`, `footerInset`): the item, until a box that scrolls starts the slots
  // again for what it holds, and that box's parent from there out. The walk passes every
  // such box on its way, so it carries the place rather than climbing to it at each cut.
  let holder = item;
  let escaped = false,
    containing = null;
  const cuts = [];
  for (let a = item; a; a = upFrom(a)) {
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
            a.offsetParent !== undefined &&
            ["fixed", "absolute"].includes(getComputedStyle(a).position),
          block: a.offsetParent,
          scrolls: scrollContainer(a),
        }),
      );
    }
    if (escaped && a === containing) escaped = false;
    if (!escaped && (held || a !== item) && c.band) {
      const covered = c.band.top + (c.scrolls ? insetAt(holder, a, ...TOP) : 0);
      const footed = c.band.bottom - (c.scrolls ? insetAt(holder, a, ...FOOT) : 0);
      cuts.push({
        box: a,
        axes: c.axes,
        scrolls: c.scrolls,
        covered: c.axes.y && covered > c.band.top,
        band:
          c.axes.y && covered >= footed
            ? null
            : c.axes.y
              ? { ...c.band, top: covered, bottom: footed }
              : c.band,
      });
    }
    if (c.scrolls) holder = upFrom(a);
    if (!escaped && c.positioned) {
      escaped = true;
      containing = c.block;
    }
  }
  return { cuts, fixed: escaped && !containing };
}

// A surface that stands over the page without clipping it: the thread panel, over the
// right of a live page at a desktop window, or a view open in the floating panel, over
// the page's foot (floating-panel.js). Nothing in the page's own tree says so,
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
const occluders = new Set();
// An occluder on its way out (motion.js, `slide`) covers nothing the user is reading past.
export const LEAVING = "data-lf-leaving";
// Whether a declared occluder stands now: rendered, and not on its way out. A
// disconnected surface has no box, so `checkVisibility` answers for that too.
const standsNow = (surface) =>
  !surface.hasAttribute(LEAVING) && surface.checkVisibility();
// Where an occluder stands, not where its slide has carried it this frame: every declared
// occluder is fixed to the window or stands in a box that is, so its offsets, summed up
// to that box, are its viewport box without the slide's transform. Each offset runs
// from inside its parent's border, which the sum steps across.
function restingBox(surface) {
  let left = 0,
    top = 0;
  for (let at = surface; at; at = at.offsetParent) {
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
// stands: the side panel, Threads or On, whichever is open (drawers.js). What is
// laid out beside the page, as the comment box is, keeps left of it, and a margin row it
// reaches is one the user has lost (chrome-layout.js).
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
export const clipsPast = (surfaces) => new Map([[PAST, new Set(surfaces)]]);
// A clip pass that reads past every occluder, for what stands above them all: a list in
// the top layer still hangs from a trigger the thread panel stands over.
export const clipsPastSurfaces = () => clipsPast(occluders);
// Whether an occluder hides a destination, an element or a Range, wherever travel lands
// it: whether it stands over most of it, asked of what the page's clips leave of the
// destination. Travel moves a destination along its scroller's block axis only, so a
// surface standing the whole height of the room the page shows, as a side panel does,
// covers every place the landing can bring it to, and the question is the inline one:
// more than half its width. A block the width of the column keeps most of itself clear
// of the thread panel at a desktop window and is seen where it stands, beside the panel;
// words at the right end of a line, or a box in the right margin, land under it. One
// scrolled out of the window is asked it at its own box, which is where the landing will
// bring it into view. A surface standing over part of that height, as a view open in the
// floating panel stands over its foot, covers a destination only where it stands now,
// so it is asked of both axes there: more than half the destination's area.
export function hides(surface, where) {
  const holder = placeHolder(where);
  if (!holder || !occluders.has(surface) || !standsNow(surface)) return false;
  if (under(holder, surface) || stackLevel(holder) >= stackLevel(surface)) return false;
  const box = placeBox(where);
  const { left, top, right, bottom } =
    clippedPlace(where, clipsPast([surface]), box) ?? box;
  const over = restingBox(surface);
  const across = Math.min(right, over.right) - Math.max(left, over.left);
  const room = shownWindow({ viewport: "layout" });
  if (over.top <= room.top + 1 && over.bottom >= room.bottom - 1)
    return across > (right - left) / 2;
  const down = Math.min(bottom, over.bottom) - Math.max(top, over.top);
  return (
    across > 0 && down > 0 && across * down > ((right - left) * (bottom - top)) / 2
  );
}
// Whether any open occluder hides `where`, by the same measure. A seat a panel stands
// over is no place to put the user, since the panels dominate what focus reaches.
export const underOccluder = (where) =>
  [...occluders].some((surface) => hides(surface, where));
// The element a destination is measured through: itself, or the element holding a
// Range's start.
export const placeHolder = (where) =>
  where instanceof Range
    ? where.startContainer instanceof Element
      ? where.startContainer
      : where.startContainer.parentElement
    : where;
// A destination's box: a Range's own, or an element's shown box (`shownBox`).
export const placeBox = (where) =>
  where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
// What the page's clips leave of a destination's `box`: a Range's walked from the
// element holding it (`clippedContents`), an element's from itself (`clippedRect`).
export const clippedPlace = (where, clips, box = placeBox(where)) =>
  where instanceof Range
    ? clippedContents(box, placeHolder(where), clips)
    : clippedRect(box, where, clips);
// Where a box stacks among the page's root-level layers: the z-index of its outermost
// positioned ancestor that sets one, and above all of them in the top layer. Both are
// read up the tree as rendered, where a slotted box stacks inside its slot's ancestors.
export function stackLevel(node) {
  let level = 0;
  for (let a = node; a; a = renderedParent(a)) {
    if (isNativeLayer(a)) return Infinity;
    const { position, zIndex } = getComputedStyle(a);
    if (position !== "static" && zIndex !== "auto") level = Number(zIndex);
  }
  return level;
}
const OCCLUDERS = Symbol("occluders");
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
      level: stackLevel(surface),
    }));
  clips.set(OCCLUDERS, open);
  return open;
}
const area = (box) => (box.right - box.left) * (box.bottom - box.top);
function occluded(rect, item, clips) {
  for (const { surface, box, level } of openOccluders(clips)) {
    if (!overlaps(rect, box) || under(item, surface) || stackLevel(item) >= level)
      continue;
    rect = uncovered(rect, box);
    if (!rect) return null;
  }
  return rect;
}
// The largest part of `rect` that `box` does not stand over, or null where it covers it.
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
