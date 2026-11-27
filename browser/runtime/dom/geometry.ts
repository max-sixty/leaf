/* This module owns the shared readings of visible boxes and clipping, how much of the
 * window the page shows, where sticky boxes stand and how far a scroll carries what
 * they hold (`carried`), and the one conversion from viewport boxes to
 * document-positioned chrome. */
import { excludedByInert, renderedParent, skipped, under } from "../lib/shadow-tree.js";
import { uiInside } from "../base/ui-marks.js";
import { nativeModalAdmits, watchLayerChanges } from "./keyboard/layer-stack.js";
import { isNativeLayer, nativeLayerHolding } from "../lib/shadow-tree.js";
import {
  clippingAxes,
  hasArea,
  holds,
  intersect,
  overlapsAcross,
  union,
} from "./rect.js";
import { cancelRender, nextRender } from "../lib/frame-pass.js";
import { watchScrolls } from "./arrivals.js";
import { reachable } from "./scrolling.js";
import { holdingElement, isHTML, isElement, isSVG } from "../lib/shadow-tree.js";
import { contentsRects, draws, elementBox } from "../lib/shown-box.js";
import {
  carriedBox,
  elementAxes,
  elementBorderFrame,
  elementMatrix,
  innerBox,
  scrollAxes,
} from "./element-axes.js";
import { RUNTIME_PAINT_ATTRIBUTE } from "../base/page-paint.js";
import { keeps } from "../lib/keeps.js";
import { scrollRange } from "../lib/scroll-range.js";
import type { Box } from "../base/box.js";

type ClipEntry = {
  matrix: DOMMatrixReadOnly;
  band: Box | null;
  axes: { x: boolean; y: boolean };
  placer: Element | null | undefined;
  scrolls: boolean;
};
export type ClipCache = Map<Element, ClipEntry>;
type ClipCut = {
  box: Element;
  axes: { x: boolean; y: boolean };
  scrolls: boolean;
  covered: boolean;
  footed: boolean;
  band: Box | null;
};
export type Holders = Record<keyof Box, Element | null>;

// The geometry owner uses the active document's visual viewport, including pinch
// zoom and the on-screen keyboard. Refuse a missing capability at this boundary.
const nativeViewport = window.visualViewport;
if (!nativeViewport) throw new Error("Leaf requires an active visual viewport");
export const visualViewport = nativeViewport;

/* Shared readings of the boxes the page actually shows.

   `shownBox` returns an element's own box or the union of the boxes its
   `display: contents` descendants paint. `shownParts` returns the visible elements on
   which an outline can be drawn, and `shownExtent` the box they cover together.
   `shownRect` clips an element's `shownBox` through scrolling ancestors' visible bands
   (less the sticky headers stuck over their tops) and the viewport, following native
   positioned containing blocks past intermediate overflow clips. It is what a box may
   be drawn over, which chrome can be: the floating panel is drawn above the page, not
   cut out of it. `seenRect` takes from that the boxes the chrome covers
   (`declareCover`), and it is the one reading of whether the user can see something, a
   Range's words included.
   `clippedRect` applies that same clipping walk to a box measured some other way for an
   element, and `clippedContents` to a box measured from a Range, starting at the element
   that holds the Range and counting that element's own clip. Use:

   - `shownBox` for travel, bounds, and reading-position landmarks;
   - `shownParts` for obligation rings and element-anchor outlines;
   - `shownExtent` for what stands beside a target's parts: a margin row, the
     response field's room;
   - `shownRect` for visible placement of floating chrome and key badges, and
     `shownRectHeld` for the box each of its edges belongs to;
   - `seenRect` for whether, and how much of, something is in front of the user;
   - `growthIsSeen` and `growthAfterIsSeen` for whether a change of size would move what
     the user sees (`motionBand`), which scroll anchoring makes a different question;
   - `whenChanges` to hear when one of those readings starts or stops holding, and
     `whenNone` when it stops holding for all of something;
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

   `skipped` (lib/shadow-tree.js) is asked first by a reading that can leave out a box the
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

// The layout viewport's box, less the scrollbars the root draws at its edges, where
// nothing the page shows stands: `innerWidth` and `innerHeight` count a classic
// scrollbar. Every reading of the whole window's box starts here, `doc`'s for a sample
// asking it of its containing page.
export const layoutWindow = (doc: Document = document) => ({
  left: 0,
  top: 0,
  right: doc.documentElement.clientWidth,
  bottom: doc.documentElement.clientHeight,
});
// The chrome standing over the page: each surface fixed over it, such as the floating
// panel, declares the one box it covers (`declareCover`), read when asked: where it is
// drawn now (`box`), and where it comes to rest (`rest`), which differ while it moves. A
// surface covers what it stands over without clipping it, so no clip walk finds it.
// What the surface holds is its own to show, so a reading of a node inside it leaves its
// box out, and the top layer paints over every surface, so nothing covers a node
// standing in an open native layer, a menu or a modal.
const covers: Set<{ surface: Element; box: () => Box | null; rest: () => Box | null }> =
  new Set();
export function declareCover(
  surface: Element,
  box: () => Box | null,
  rest: () => Box | null = box,
) {
  const cover = { surface, box, rest };
  covers.add(cover);
  return () => void covers.delete(cover);
}
// The boxes the declared surfaces cover over `item`, or over any page box: where they
// are drawn now, or with `rest`, where they will stand once their motion ends.
export const coverBoxes = (
  item: Node | null = null,
  { rest = false }: { rest?: boolean } = {},
) =>
  isElement(item) && nativeLayerHolding(item)
    ? []
    : [...covers].flatMap((cover) => {
        if (item && under(item, cover.surface)) return [];
        const at = rest ? cover.rest() : cover.box();
        return at && hasArea(at) ? [at] : [];
      });
// How much of the window the page shows: the visible viewport, less the boxes the chrome
// covers (`coverBoxes`), each bounding only the room it stands across, from the edge it
// stands nearer.
//
// The visible viewport is the part of the window the user sees: pinch zoom and a phone's
// software keyboard shrink it without resizing the layout viewport the page and its fixed
// chrome are laid out in. `within` narrows the room to a box the caller keeps to, such as
// a reading region's shown bounds, and `gap` holds what stands in the room that far
// inside each of its edges. `viewport: "layout"` reads the room in the layout viewport
// instead. `across` names the columns a box asking for its room stands in, where they
// are narrower than the room: a cover beside them takes none of its height, as the
// floating panel under the page column leaves a thread card in the margin the window's
// whole height. `item` names the node the room is read for, so a surface's own box
// takes no room from what it holds (`coverBoxes`), as the floating panel's open view
// covers none of the thread it shows. A chrome owner that changes the box it covers
// says so (`announceRoom`), since no scroll or resize tells a reader.
export function shownWindow({
  within = null,
  gap = 0,
  viewport = "visual",
  across = null,
  item = null,
}: {
  within?: Partial<Box> | null;
  gap?: number;
  viewport?: "visual" | "layout";
  across?: { left: number; right: number } | null;
  item?: Node | null;
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
  for (const box of coverBoxes(item)) {
    if (!overlapsAcross(box, across ?? { left, right })) continue;
    ({ top, bottom } = coverCut(box, top, bottom, { offsetTop, height }));
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
// past the edge — read against the container's own bounding rect through its frame
// (element-axes.js, `innerBox`, on `matrix`, the container's map, where the caller
// holds it), so a turned container's band is the box its turned padding box covers.
// A box that clips both axes with `overflow: clip` paints what it holds past its
// padding box by its `overflow-clip-margin`, in its own pixels, and its band reaches as
// far; Chromium paints no margin where either axis clips another way. A margin measured
// from the content or border box, which no sheet here writes, reads as none, and so
// does WebKit's, which has no such property. Inside an SVG drawing a box clips only
// where it sets a viewport of its own (`drawnViewport`).
//
// `page check --render` imports this to ask which container cut a box away, so the
// band a handover is refused against and the band the page paints to are one reading.
// Written twice they disagreed twice, each copy right about one of the two things above
// and wrong about the other.
//
// The element's own document answers, so a sample can ask it of the containing page's
// boxes in that page's viewport coordinates.
export function shownBand(el: Element, matrix?: DOMMatrixReadOnly): Box | null {
  const doc = el.ownerDocument;
  // The root element's border box travels with the document, while its scrollport stays
  // pinned to the viewport. Every other scroller's visible band can be derived from its
  // own box; the root is the platform-defined exception.
  if (el === doc.scrollingElement) return layoutWindow(doc);
  const s = getComputedStyle(el);
  const axes = clippingAxes(s);
  if (!axes.x && !axes.y) return null;
  if (isSVG(el) && el.ownerSVGElement) return drawnViewport(el);
  const reach =
    s.overflowX === "clip" && s.overflowY === "clip"
      ? parseFloat(s.overflowClipMargin) || 0
      : 0;
  const inner = {
    left: el.clientLeft - reach,
    top: el.clientTop - reach,
    right: el.clientLeft + el.clientWidth + reach,
    bottom: el.clientTop + el.clientHeight + reach,
  };
  return innerBox(el, inner, matrix);
}
// The box a viewport nested in an SVG drawing, a nested <svg> or a <foreignObject>, clips
// what it holds to: the one its x, y, width and height set in the user space it stands
// in, its own transform included, carried to the window by SVG's own map
// (`getScreenCTM`). A foreignObject's map is that space's; a nested <svg>'s also fits
// its viewBox into the box, which `viewBoxFit` takes back out. Any other element of a
// drawing sets no viewport and clips nothing.
function drawnViewport(el: SVGElement) {
  const viewport = isSVG(el, "svg") || isSVG(el, "foreignObject") ? el : null;
  const screen = viewport?.getScreenCTM();
  if (!viewport || !screen) return null;
  const left = viewport.x.animVal.value;
  const top = viewport.y.animVal.value;
  const { a, b, c, d, e, f } = screen;
  const map = new window.DOMMatrix([a, b, c, d, e, f]);
  return carriedBox(
    isSVG(viewport, "svg") ? map.multiply(viewBoxFit(viewport).inverse()) : map,
    {
      left,
      top,
      right: left + viewport.width.animVal.value,
      bottom: top + viewport.height.animVal.value,
    },
  );
}
// The map a nested <svg> adds inside its box, from its own user units to the space it
// stands in: its viewBox fitted to its x, y, width and height as its preserveAspectRatio
// says, or the move to x and y where it sets no viewBox (SVG, "The equivalent transform
// of an SVG viewport").
function viewBoxFit(svg: SVGSVGElement) {
  const x = svg.x.animVal.value;
  const y = svg.y.animVal.value;
  const width = svg.width.animVal.value;
  const height = svg.height.animVal.value;
  const view = svg.viewBox.animVal;
  if (!view.width || !view.height) return new window.DOMMatrix().translate(x, y);
  const { align, meetOrSlice } = svg.preserveAspectRatio.animVal;
  const fits = align !== window.SVGPreserveAspectRatio.SVG_PRESERVEASPECTRATIO_NONE;
  const slices = meetOrSlice === window.SVGPreserveAspectRatio.SVG_MEETORSLICE_SLICE;
  let sx = width / view.width;
  let sy = height / view.height;
  if (fits) sx = sy = slices ? Math.max(sx, sy) : Math.min(sx, sy);
  // The aligned values run xMinYMin, xMidYMin, xMaxYMin, xMinYMid, … from 2: across
  // fastest, each a third of the free room further than the one before.
  const step = fits
    ? align - window.SVGPreserveAspectRatio.SVG_PRESERVEASPECTRATIO_XMINYMIN
    : 0;
  return new window.DOMMatrix()
    .translate(
      x - view.x * sx + ((width - view.width * sx) * (step % 3)) / 2,
      y - view.y * sy + ((height - view.height * sy) * Math.floor(step / 3)) / 2,
    )
    .scale(sx, sy);
}
// Which of the window's axes a box's clip cuts, from the axes it clips on itself
// (`clippingAxes`) and its map into the window. A clip on both axes cuts both. A clip on
// one cuts the window's axis that one's direction lies nearest, so a quarter turn swaps
// the axes and a slant keeps them, at the slant's few pixels' error.
function windowAxes(local: { x: boolean; y: boolean }, matrix: DOMMatrixReadOnly) {
  if (local.x === local.y) return local;
  const [across, down] = local.x ? [matrix.a, matrix.b] : [matrix.c, matrix.d];
  const nearAcross = Math.abs(across) >= Math.abs(down);
  return { x: nearAcross, y: !nearAcross };
}

// A box of text in `node` stretched across its line's leading, half the gap between
// the line's height and the box's on each side, so a paragraph's lines meet with no gap
// between them and whatever stands on a line holds every point of its height.
export function lined(rect: Box, node: Node): Box {
  const holder = node instanceof Element ? node : node.parentElement;
  const pitch = holder ? parseFloat(getComputedStyle(holder).lineHeight) : NaN;
  const half = Number.isFinite(pitch)
    ? Math.max(0, (pitch - (rect.bottom - rect.top)) / 2)
    : 0;
  return {
    left: rect.left,
    right: rect.right,
    top: rect.top - half,
    bottom: rect.bottom + half,
  };
}

// Whether the point lies over the character at `at` in a text node, or with `whole`
// over its line (`lined`).
export function overCharacter(
  node: Node,
  at: number,
  x: number,
  y: number,
  whole: boolean = false,
) {
  if (at >= (node.textContent?.length ?? 0)) return false;
  const character = document.createRange();
  character.setStart(node, at);
  character.setEnd(node, at + 1);
  return [...character.getClientRects()].some((rect) =>
    holds(whole ? lined(rect, node) : rect, x, y),
  );
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
// `scroll-padding` the scroller declares, which is also what `scrollIntoView` honours,
// and less the chrome standing across what it lands (`landingBand`'s header). The root
// states its top apart (`landingInsets`), which its padding copies but for while a
// floating editor holds focus, when the browser's own caret reveal is given none.
// It clears what stands over the whole scroller (a page tab strip); a header
// over part of it, a diff's file header, is cleared by the `scroll-margin` of the rows
// it stands over. Scroll anchoring looks for the box it keeps still in the band the
// padding leaves: the spec's optimal viewing region, which Chrome reads from
// `scroll-padding` too (`motionBand`).
//
// A box scrolls, for these readings, when its computed overflow makes it a scroll
// container: `auto` and `scroll`, and `hidden` too, which a script or a landing can
// scroll though the user cannot, and which is the scroller a sticky box inside it sticks
// in. The runtime asks it of what a motion scrolls and which boxes scroll what they
// hold (`scrollsContent`), and of the boxes that hold sticky headers
// (`scrollContainer`). `userScrollport` is the same test without `hidden`: what the
// user, rather than a script, can scroll, which keyboard stops and edge marks read
// (reach.js, `paintSlot`), and the render checks asking what a reader can reach.
const scrollport = (overflow: string) => /^(auto|scroll|hidden)$/.test(overflow);
export const userScrollport = (overflow: string) => /^(auto|scroll)$/.test(overflow);
export const scrollsBy = ({
  overflowX,
  overflowY,
}: Pick<CSSStyleDeclaration, "overflowX" | "overflowY">) =>
  scrollport(overflowX) || scrollport(overflowY);
const scrolls = (el: Element) => scrollsBy(getComputedStyle(el));
// A scroll container: the document's own scroller, or a box whose overflow scrolls.
export const scrollContainer = (box: Element) =>
  box === box.ownerDocument.scrollingElement || scrolls(box);
// Whether `box` scrolls what it holds: it clips into a scrollport, `hidden` included,
// which a script or focus can scroll, and holds more than that scrollport shows on that
// axis. An inline SVG drawing clips what it draws but scrolls none of it.
export function scrollsContent(box: Node | null) {
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
const slotHolder = (el: Element, scroller: Element) => {
  let at: Element | null = el;
  let box: Element | null = el;
  for (; box && box !== scroller; box = renderedParent(box))
    if (box.nodeType === 1 && scrolls(box)) at = renderedParent(box);
  return at;
};
// The inset read at `at`, the box where the slot counts from `scroller`.
const insetAt = (
  at: Element | null,
  scroller: Element,
  slot: string,
  padding: "paddingTop" | "paddingBottom",
) => {
  const read = (box: Element) =>
    Number.parseFloat(getComputedStyle(box).getPropertyValue(slot)) || 0;
  const inset = at?.nodeType === 1 ? read(at) : 0;
  if (inset <= read(scroller)) return 0;
  return (Number.parseFloat(getComputedStyle(scroller)[padding]) || 0) + inset;
};
const TOP: [string, "paddingTop"] = ["--lf-top", "paddingTop"];
const FOOT: [string, "paddingBottom"] = ["--lf-bottom", "paddingBottom"];
const edgeInset = (
  el: Element,
  scroller: Element,
  edge: [string, "paddingTop" | "paddingBottom"],
) =>
  !scrollContainer(scroller) || el === scroller
    ? 0
    : insetAt(slotHolder(el, scroller), scroller, ...edge);
const headerInset = (el: Element, scroller: Element) => edgeInset(el, scroller, TOP);
// The same reading at the foot, for a box sticking there (`--lf-bottom`, base.css):
// how far above the bottom of `scroller`'s band the view of `el` ends.
const footerInset = (el: Element, scroller: Element) => edgeInset(el, scroller, FOOT);
export function visibleBand(scroller: Element, item: Element | null = null) {
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
export function headerCuts(item: Element, clips: ClipCache = new Map()) {
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
// (annotations/annotation-overlay/floating.js), or held by a transformed box around it, moves with
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
export function stuckBox(node: Element, within: Element | null = null) {
  let el: Element | null = node;
  for (; el?.nodeType === 1 && el !== within; el = renderedParent(el)) {
    const style = getComputedStyle(el);
    if (style.position === "sticky" ? sticks(el) : inWindow(el, style)) return el;
  }
  return null;
}
// A fixed box stands in the window where nothing around it holds it instead, which
// leaves it no offset parent: a transformed, filtered or contained ancestor holds it as
// its containing block, and the box then rides every scroll that moves that ancestor,
// as an absolute one does. Such an ancestor is its offset parent in Chromium and
// Firefox alike. A null offset parent says only that much: CSSOM View's offsetParent
// (https://drafts.csswg.org/cssom-view/#dom-htmlelement-offsetparent) also returns
// null for an element that generates no box, for `body` and for the root, so a fixed
// `display: contents` ancestor, which places nothing, reads as fixed in the window and
// ends a landing's walk short of the scroller that would show what it holds, and a
// fixed `body` under a transformed root reads as fixed though the root's scroll moves
// it. Neither is handled; main stopped at every fixed box, which these share.
export const fixedInWindow = (
  el: Element,
  style: CSSStyleDeclaration = getComputedStyle(el),
) => style.position === "fixed" && (!isHTML(el) || el.offsetParent === null);
// The box that places a box positioned out of flow, past every box between them, which
// neither moves nor clips it: its containing block, its offset parent as above, or null
// for a box fixed in the window, which rides no box. Undefined for a box in flow, which
// its rendered parent places.
export const placedBy = (
  el: Element,
  style: CSSStyleDeclaration = getComputedStyle(el),
): Element | null | undefined =>
  isHTML(el) && (style.position === "fixed" || style.position === "absolute")
    ? el.offsetParent
    : undefined;
// A box stuck in the window: fixed there, and placed by no anchor.
export const inWindow = (
  el: Element,
  style: CSSStyleDeclaration = getComputedStyle(el),
) => isHTML(el) && fixedInWindow(el, style) && !style.positionAnchor.startsWith("--");
// The box a sticky box moves within, its containing block: the first box around it that
// holds blocks, past `display: contents` and inline wrappers, or `stop` where the climb
// reaches it first.
export function stickyHolder(sticky: Element, stop: Element | null = null) {
  let parent = renderedParent(sticky);
  while (
    parent &&
    parent !== stop &&
    /^(contents|inline)$/.test(getComputedStyle(parent).display)
  )
    parent = renderedParent(parent);
  return parent;
}
// Where `sticky` sticks: the scroller around it, that scroller's shown band and padding,
// and the lines its top and its foot stick at, each NaN on a side it doesn't stick to.
// A sticky box that clips what it holds, as a tab strip does, still sticks in that
// scroller.
function stickLines(sticky: Element, style: CSSStyleDeclaration) {
  let scroller = renderedParent(sticky);
  while (scroller?.nodeType === 1 && !scrollContainer(scroller))
    scroller = renderedParent(scroller);
  if (scroller?.nodeType !== 1) return null;
  const band = shownBand(scroller);
  if (!band) return null;
  const room = getComputedStyle(scroller);
  const padTop = Number.parseFloat(room.paddingTop) || 0;
  const padBottom = Number.parseFloat(room.paddingBottom) || 0;
  return {
    scroller,
    band,
    padTop,
    padBottom,
    top: band.top + padTop + Number.parseFloat(style.top),
    foot: band.bottom - padBottom - Number.parseFloat(style.bottom),
  };
}
// Whether `sticky` stands where sticking holds it, in the scroller around it.
function sticks(sticky: Element) {
  const lines = stickLines(sticky, getComputedStyle(sticky));
  if (!lines) return false;
  const { scroller, band, padTop, padBottom, top: topLine, foot: footLine } = lines;
  const box = sticky.getBoundingClientRect();
  // Where that holder is the scroller itself, its scrolled content rather than its frame.
  const parent = stickyHolder(sticky, scroller);
  const content = band.top - scroller.scrollTop;
  const holder =
    parent === scroller
      ? { top: content + padTop, bottom: content + scroller.scrollHeight - padBottom }
      : parent && shownBox(parent);
  if (!holder) return false;
  if (box.top <= topLine + 1 && holder.top < box.top - 1) return true;
  if (Math.abs(box.bottom - footLine) <= 1) return true;
  return box.bottom > footLine && holder.bottom > box.bottom + 1;
}
// How far sticking moves `sticky` from its own place in its holder, `{x, y}` in client
// pixels, zero for a box that is not sticky or stands in its own place. Its own place
// is the one reading of a sticky box that holds at every scroll. Layout answers
// nothing else from where the box is drawn: its client rect and `offsetTop` both
// include the offset, and a box that stuck has lost the place it stuck from. A view
// timeline on the box knows that place, since the timeline's range runs from it. With
// the scrollport's end inset by all of its length, a box that sticks at its top starts
// its range at its own top, and one that sticks at its foot ends it at its own foot,
// counted in its scroller's scrolled content, at any scroll. Chromium and WebKit agree
// on that reading. Where a view timeline can't say where its range starts, the shift
// reads zero, which leaves a sticky box read where it is drawn (notes/browser-support.md,
// "Sticky boxes' own place").
//
// That place leaves out the offset of every sticky box in the scroller, so for a sticky
// box inside another in the same scroller the outer box's offset is taken off and the
// answer is the inner box's own: a walk down the boxes adds each one's shift to those
// around it.
let timelineOffsets: boolean | null = null;
// Firefox 157 lacks `ViewTimeline`; Firefox 159 builds one and throws NotSupportedError
// on reading its `startOffset` and `endOffset`.
function readsTimelineOffsets() {
  if (timelineOffsets !== null) return timelineOffsets;
  if (!("ViewTimeline" in globalThis)) return (timelineOffsets = false);
  try {
    void new globalThis.ViewTimeline({ subject: document.documentElement }).startOffset;
    timelineOffsets = true;
  } catch (error) {
    if (!(error instanceof DOMException && error.name === "NotSupportedError"))
      throw error;
    timelineOffsets = false;
  }
  return timelineOffsets;
}
export function stuckShift(
  sticky: Element,
  style: CSSStyleDeclaration = getComputedStyle(sticky),
) {
  const shift = { x: 0, y: 0 };
  if (style.position !== "sticky" || !readsTimelineOffsets()) return shift;
  for (const axis of ["y", "x"] as const) {
    const own = displaced(sticky, style, axis);
    if (!own) continue;
    let outer = renderedParent(sticky);
    for (
      ;
      outer?.nodeType === 1 && outer !== own.scroller;
      outer = renderedParent(outer)
    ) {
      const around = getComputedStyle(outer);
      if (around.position !== "sticky") continue;
      own.by -= displaced(outer, around, axis)?.by ?? 0;
      break;
    }
    if (Math.abs(own.by) >= 0.5) shift[axis] = own.by;
  }
  return shift;
}
const SIDES = {
  y: { start: "top", end: "bottom", size: "height" },
  x: { start: "left", end: "right", size: "width" },
} as const;
// How far a sticky box is drawn from its own place on one axis, and the scroller that
// place is counted in, or null where the box sticks on neither of that axis's sides.
function displaced(sticky: Element, style: CSSStyleDeclaration, axis: "x" | "y") {
  const { start, end, size } = SIDES[axis];
  const fromStart = style[start] !== "auto";
  if (!fromStart && style[end] === "auto") return null;
  const timeline = new globalThis.ViewTimeline({
    subject: sticky,
    axis,
    inset: "0px 100%",
  });
  const scroller = timeline.source;
  const range = fromStart ? timeline.startOffset : timeline.endOffset;
  if (!scroller || !range) return null;
  const box = sticky.getBoundingClientRect();
  // Where the scrolled content's origin stands in the window.
  const frame =
    scroller === scroller.ownerDocument.scrollingElement
      ? { top: 0, left: 0 }
      : scroller.getBoundingClientRect();
  const origin =
    axis === "y"
      ? frame.top + scroller.clientTop - scroller.scrollTop
      : frame.left + scroller.clientLeft - scroller.scrollLeft;
  const own = origin + range.to("px").value - (fromStart ? 0 : box[size]);
  return { by: own - box[start], scroller };
}
// A scroller's landing band: its shown band less the room its landings keep at each
// edge (`landingInsets`). The chrome at the window's foot takes no room from the page,
// so a scroller inside the page can reach under it. Where a cover stands across the
// columns a landing's destination stands in (`across`), the band ends above it
// (`footCover`) plus however far a scroll of the page that far carries the scroller up
// before it first stops (`carried`), and the root's band brings the destination the
// rest of the way clear.
export const landingBand = (
  scroller: Element,
  across: { left: number; right: number } | null = null,
) => {
  const band = insetBand(scroller, landingInsets(scroller));
  const root = document.documentElement;
  if (!band || !across || scroller === root) return band;
  const reach = footCover(
    getComputedStyle(root),
    coverBoxes(scroller, { rest: true }),
    across,
  );
  if (reach === null) return band;
  const foot = layoutWindow().bottom - reach;
  if (band.bottom > foot)
    band.bottom = Math.max(
      band.top,
      foot + carried(scroller, root, band.bottom - foot),
    );
  return band;
};
// How far up from the window's foot a landing stops for the covers standing at that
// foot (`coverBoxes`), read where they come to rest: their reach, with the room the
// root keeps above them (`--lf-landing-foot`, base.css), or null where none stands
// there or nothing states that room, as on an export. `across` narrows them to the
// covers in a destination's columns.
//
// Reading the covers keeps a landing above a view the panel holds open, as when a
// thread opened in the panel lands its passage, `m` walks with On Me open, or a press
// on words the view opens over brings them clear. A fixed room above the window's foot
// needs none of this code. Sized to the panel's row, it left each of those landings
// under the open view; sized at half the window, it still left some under a tall view,
// and it moved tall boxes the user already saw whole. The maintainer chose to read the
// covers, though it may be more than landings need. Once it needs more code than this,
// replace it with a fixed room and let those landings stand under an open view.
function footCover(
  rootStyle: CSSStyleDeclaration,
  boxes: Box[],
  across: { left: number; right: number } | null = null,
) {
  const clear = Number.parseFloat(rootStyle.getPropertyValue("--lf-landing-foot"));
  if (Number.isNaN(clear)) return null;
  const { bottom } = layoutWindow();
  let top = bottom;
  for (const box of boxes)
    if (box.top + box.bottom > bottom && (!across || overlapsAcross(box, across)))
      top = Math.min(top, box.top);
  return top < bottom ? bottom - top + clear : null;
}
// How far a scroll of `box` by `by`, in its scroll offset and down positive, carries
// `node` before `node` first stops riding it, in the same measure: the whole scroll for
// what the box scrolls as content, as far as the box can scroll that way (scrolling.js,
// `reachable`), and none where a box fixed in the window holds `node`. A sticky box
// holding `node` that sticks in `box` rides the scroll until it reaches a line it
// sticks at, and `node` rides the least any of them does. So a side list standing a
// pixel short of its top line rides a scroll of the page down for that pixel alone,
// and a box its holder's end has pushed past its line rides back to the line, and the
// other way with the holder. Lines are read in the box's own scroll units, through its
// transforms (element-axes.js, `scrollAxes`), since a sticky box's insets are.
//
// The first stop is what a move needs: scrolling a region further than it carries the
// destination scrolls the text beside it and leaves the destination where it was
// (readings/landing-scroll.js, `readingBandMoves`), and a stop is read exactly from where the
// box is drawn, in Chromium and Firefox alike. Where a scroll goes on past it, a box's
// own place coming back to its line or its holder's end reaching it carries the box on,
// which only a view timeline would let a reading compute (`stuckShift`) and Firefox
// can't read one; where a glide leaves a node is read there instead (scrolling.js,
// `whereGlidesLand`). A box on its line reads as stuck there, as `stuckBox` reads it,
// though it may stand there in its own place and leave the line when the scroll goes
// the other way.
export function carried(node: Element, box: Element, by: number) {
  let ride = reachable(box, by);
  const way = Math.sign(ride);
  const scale = scrollAxes(box).y.y;
  let el: Element | null = node;
  for (; ride && scale && el && el !== box; el = renderedParent(el)) {
    const style = getComputedStyle(el);
    if (inWindow(el, style)) return 0;
    if (style.position !== "sticky") continue;
    const lines = stickLines(el, style);
    if (lines?.scroller !== box) continue;
    const { band, padTop, padBottom } = lines;
    const { top, bottom } = el.getBoundingClientRect();
    // How far the box's local top and foot stand from the band's, which a flipped
    // scroller draws at the other edge of the window.
    const [start, end] =
      scale > 0
        ? [top - band.top, band.bottom - bottom]
        : [band.bottom - bottom, top - band.top];
    // How far the box stands inside each line, and so how far the scroll carries it
    // toward that line before it reaches it: up to a unit below zero where the box is
    // on the line, further below where the scroll carries it away from the line, and
    // NaN on a side it doesn't stick to.
    const size = Math.abs(scale);
    const below = start / size - padTop - Number.parseFloat(style.top);
    const above = end / size - padBottom - Number.parseFloat(style.bottom);
    for (const short of [way * below, -way * above])
      if (short >= -1) ride = way * Math.min(way * ride, Math.max(0, short));
  }
  return ride;
}
function insetBand(scroller: Element, inset: ReturnType<typeof scrollPadding>) {
  const band = shownBand(scroller);
  if (!band) return null;
  return {
    left: band.left + inset.left,
    top: band.top + inset.top,
    right: band.right - inset.right,
    bottom: band.bottom - inset.bottom,
  };
}
// How far each edge of `landingBand` stands in from the scroller's shown band: the
// band the scroller states, else the `scroll-padding` it declares. The root states its
// top in `--lf-landing-top` (base.css), which a floating editor's override hides from
// the browser alone, and ends above the chrome at the window's foot (`footCover`),
// which never reaches the browser: as the root's `scroll-padding-bottom`, a band across
// the whole window would have the browser's own reveals scroll the page under a box
// stuck beside the panel. Callers that measure from the scroller's own box take the
// clearance here rather than reading the style themselves.
export function landingInsets(scroller: Element) {
  const style = getComputedStyle(scroller);
  const padding = scrollPadding(style);
  const top = Number.parseFloat(style.getPropertyValue("--lf-landing-top"));
  const root = scroller === document.documentElement;
  return {
    ...padding,
    top: Number.isNaN(top) ? padding.top : top,
    bottom: root
      ? (footCover(style, coverBoxes(null, { rest: true })) ?? padding.bottom)
      : padding.bottom,
  };
}
function scrollPadding(style: CSSStyleDeclaration) {
  const inset = (side: "Top" | "Right" | "Bottom" | "Left") =>
    Number.parseFloat(style[`scrollPadding${side}`]) || 0;
  return {
    top: inset("Top"),
    right: inset("Right"),
    bottom: inset("Bottom"),
    left: inset("Left"),
  };
}
// The box an element shows as (`elementBox`, lib/shown-box.js), and for the document's
// scroller the band of the window it shows.
export function shownBox(el: Element): DOMRect {
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
// The runtime's own chrome leaves by name rather than on that test. Area only seems to
// do the job, by luck: a suggestion hangs its controls off
// a span with no width, so the apparatus falls out on its own. The line saying how many
// comments a block holds is clipped to a pixel and has one — so a decision that has been
// commented on would wear its ring on the runtime's word about the page rather than on the
// page, and the pixel it hangs from moves the first time a comment lands. That question is
// already asked, declared labels and all, and it is the one the anchor pass puts
// to a text node — so what a mark hangs on and what a quote may name cannot come apart.
// Bounded at the element, for the reason given where the question is stated: a widget an
// agent sent stands inside the panel, and asked about the page instead it would have no
// child of its own left to fall back to.
//
// A box with no area may hold content the browser skips, as a closed tab's panel does.
// A reading of what is drawn now leaves that content out (`leaveSkipped`) rather than
// read its boxes, which lays it out to answer: Firefox can take hundreds of milliseconds
// to lay out a closed tab's panel holding a text document of several megabytes.
// A mark that must stand once the content is drawn reads it, and pays (lib/shadow-tree.js,
// `skipped`).
export function shownParts(
  el: Element,
  { leaveSkipped = false }: { leaveSkipped?: boolean } = {},
): Element[] {
  const r = el.getBoundingClientRect();
  if (r.width && r.height) return [el];
  return [...el.children]
    .filter((child) => !uiInside(child, el) && !(leaveSkipped && skipped(child)))
    .flatMap((child) => shownParts(child, { leaveSkipped }));
}
// The box an element's shown parts cover together: a mark hung on the element stands at
// its corner, so a comment on one shape of a drawing stands on that shape rather than at
// the drawing's edge. An element with no shown part has none.
export const shownExtent = (el: Element) =>
  union(shownParts(el).map((part) => part.getBoundingClientRect()));
// How far what Leaf draws round `box` reaches past its left and right edges to take in
// a list marker beside it, in CSS pixels. The browser draws an outside marker beyond
// its item's border box, in the column the list keeps for it, and gives the marker no
// box of its own, so a mark that followed the box alone would run between the marker
// and the words. So a box that draws an outside marker (`display: list-item`, with a
// marker, outside), or a block that opens one, standing at its content's first line and
// start edge as a loose list's paragraph does, reaches by the list inset
// (`--lf-list-inset`) on the item's start side. Every other box reaches 0, such as an
// item's second paragraph, which no marker stands beside, or a link that opens an item,
// which keeps to its own edge. What a target draws (`inkedBox`), where its marks stand
// (`markedBox`) and the marks a box draws round itself (surfaces.css,
// `[data-lf-beside-marker]`) all reach by this.
function markerReach(box: Element): { left: number; right: number } {
  const none = { left: 0, right: 0 };
  const own = getComputedStyle(box);
  if (own.display.startsWith("inline")) return none;
  const at = box.getBoundingClientRect();
  let style = own;
  let item = box;
  while (!style.display.includes("list-item")) {
    const holder = item.parentElement;
    if (!holder) return none;
    style = getComputedStyle(holder);
    // A `display: contents` holder draws no box of its own to stand at the corner of.
    if (style.display !== "contents" && !opens(at, holder, style)) return none;
    item = holder;
  }
  // The marker's own `content` draws it where the list style draws none, and hides it.
  const marker = getComputedStyle(item, "::marker").content;
  if (
    style.listStylePosition !== "outside" ||
    marker === "none" ||
    (marker === "normal" &&
      style.listStyleType === "none" &&
      style.listStyleImage === "none")
  )
    return none;
  const reach = Number.parseFloat(own.getPropertyValue("--lf-list-inset"));
  return style.direction === "rtl"
    ? { left: 0, right: reach }
    : { left: reach, right: 0 };
}
// Whether a box at `at` opens `holder`: stands at its content's first line and start edge.
function opens(at: DOMRect, holder: Element, style: CSSStyleDeclaration) {
  const outer = holder.getBoundingClientRect();
  const scale = scaleOf(holder);
  const px = (value: string) => Number.parseFloat(value);
  const top = outer.top + (px(style.borderTopWidth) + px(style.paddingTop)) * scale.y;
  const start =
    style.direction === "rtl"
      ? outer.right - (px(style.borderRightWidth) + px(style.paddingRight)) * scale.x
      : outer.left + (px(style.borderLeftWidth) + px(style.paddingLeft)) * scale.x;
  const edge = style.direction === "rtl" ? at.right : at.left;
  return Math.abs(edge - start) <= 1 && Math.abs(at.top - top) <= 1;
}
// Reads what decides where the marks on each of `boxes` stand besides the box's kind,
// which only its layout says, and returns the write that says it on each, which
// element-marks.css reads to draw them: the side the box reaches over a list marker on
// (`markerReach`, `data-lf-beside-marker`), and whether a box clipping it would cut
// marks standing outside it (`clipsMarks`, `data-lf-flush`). A mark's writer reads this
// with its other reads and writes it with its other writes, so marking many boxes lays
// the page out once.
export function readMarkRoom(boxes: Element[]) {
  const clips: ClipCache = new Map();
  const reads = boxes.map((box) => {
    const { left, right } = markerReach(box);
    return {
      box,
      side: left ? "left" : right ? "right" : null,
      flush: clipsMarks(box, clips, Boolean(left || right)) ? "" : null,
    };
  });
  return () =>
    reads.forEach(({ box, side, flush }) => {
      keeps(box, RUNTIME_PAINT_ATTRIBUTE.besideMarker, side);
      keeps(box, RUNTIME_PAINT_ATTRIBUTE.flush, flush);
    });
}
// Whether the box clipping `box` would cut the marks Leaf draws outside it: on an axis
// it clips, their room (`markedOf`) reaches past what it shows, which for a box that
// scrolls is everything it scrolls through (`scrolledBox`), so a scroll never changes
// the answer. Only the nearest clip on each axis counts: it holds the marks it leaves
// whole inside its own box, and a clip further out cuts that box as it would the
// marks. A box sticky on an axis doesn't stand where it would in what scrolls, so on
// that axis it is read against what the clip shows, the scrollport it sticks in. Where
// the clip would cut the marks, the box stands them inside its edge (element-marks.css,
// `[data-lf-flush]`), as a table filling a scroll area does. A box's kind can't say
// this, since it turns on what holds the box, and no CSS can: no selector asks whether
// a box meets a clip's edge, and `overflow-clip-margin` lets a clip's contents paint
// past it only for `overflow: clip`, never for a box that scrolls. The window is no
// such clip: a box that a layout stands at the window's edge, as a full-height
// workspace's body, says where its marks stand (layouts.css). Read half a pixel of the
// box's own short, for the whole pixels of a scroll size.
// A box whose stamp is in force (`--lf-flush-at`) reads where the stamp stands its
// marks, so it keeps the stamp while a mark shows, standing the mark inside, whole,
// until it goes. A painter reads before it marks, so a fresh mark reads the box as its
// kind and layout leave it, and a stamp left on a box no longer marked decides nothing.
// The stamp stands marks no further in than a box whose kind stands them inside, so
// such a box takes it only to stop reaching over a list marker (`reaches`).
function clipsMarks(box: Element, clips: ClipCache, reaches: boolean) {
  if (getComputedStyle(box).getPropertyValue("--lf-flush-at")) return true;
  const room = bandRoom(box);
  if (room <= 0 && !reaches) return false;
  const scale = scaleOf(box);
  const marked = markedOf(box, room, scale);
  const { cuts } = clipWalk(box, clips, false);
  return (["x", "y"] as const).some((axis) => {
    const cut = cuts.find(({ axes }) => axes[axis]);
    const entry = cut && clips.get(cut.box);
    if (!cut || !entry || cut.box === box.ownerDocument.scrollingElement) return false;
    const shows =
      cut.scrolls && isHTML(cut.box) && !sticksIn(box, cut.box, axis)
        ? scrolledBox(cut.box, entry.matrix)
        : entry.band;
    const short = 0.5 * scale[axis];
    return Boolean(
      shows &&
      (axis === "x"
        ? marked.left < shows.left - short || marked.right > shows.right + short
        : marked.top < shows.top - short || marked.bottom > shows.bottom + short),
    );
  });
}
// Whether `box`, or a box round it inside `clip`, sticks on `axis`.
function sticksIn(box: Element, clip: Element, axis: "x" | "y") {
  const sides =
    axis === "x" ? (["left", "right"] as const) : (["top", "bottom"] as const);
  for (let at = box as Element | null; at && at !== clip; at = renderedParent(at)) {
    const style = getComputedStyle(at);
    if (style.position === "sticky" && sides.some((side) => style[side] !== "auto"))
      return true;
  }
  return false;
}
// Everything `scroller` scrolls through, wherever it is scrolled to: its padding box
// carried back to where its scroll starts (`scrollRange`) and grown to its scroll
// size, on screen, so where a box stands in it is the same at every scroll. Not the
// document's scroller, whose box travels with its scroll.
export function scrolledBox(scroller: HTMLElement, matrix?: DOMMatrixReadOnly) {
  const range = scrollRange(scroller);
  const left = scroller.clientLeft - (scroller.scrollLeft - range.left[0]);
  const top = scroller.clientTop - (scroller.scrollTop - range.top[0]);
  return innerBox(
    scroller,
    {
      left,
      top,
      right: left + Math.max(scroller.scrollWidth, scroller.clientWidth),
      bottom: top + Math.max(scroller.scrollHeight, scroller.clientHeight),
    },
    matrix,
  );
}
// How many of the window's pixels a band one CSS pixel wide round `box` takes across
// (`x`) and down (`y`), under the transforms on it and every box round it
// (element-axes.js, `elementAxes`): other than 1 under a scale, as in a slide scaled
// to fit the window, and under a rotation, which turns each side's band partly
// across and partly down.
function scaleOf(box: Element): { x: number; y: number } {
  const { x, y } = elementAxes(box);
  return { x: Math.abs(x.x) + Math.abs(y.x), y: Math.abs(x.y) + Math.abs(y.y) };
}
// What `part` draws: its border box, reaching over a list marker beside it.
function inkOf(
  part: Element,
  rect: DOMRect = part.getBoundingClientRect(),
  scale: { x: number; y: number } = scaleOf(part),
): Box {
  const reach = markerReach(part);
  return {
    left: rect.left - reach.left * scale.x,
    top: rect.top,
    right: rect.right + reach.right * scale.x,
    bottom: rect.bottom,
  };
}
// The box a target occupies on screen, as the reader sees it: what its shown parts
// (`shownParts`) draw together, each reaching over a list marker beside it
// (`markerReach`), or null where no part shows. Paint that stands beside a target,
// such as the margin's bars, stands beside this.
export const inkedBox = (target: Element): Box | null =>
  union(shownParts(target).map((part) => inkOf(part)));
// The room the band of a mark on `part` takes outside it (`--lf-band-room`, its gap
// and its width), or none where it stands inside it, as a table cell's does.
const bandRoom = (part: Element) =>
  Math.max(
    0,
    Number.parseFloat(getComputedStyle(part).getPropertyValue("--lf-band-room")),
  );
// Where the marks Leaf draws round `part` stand: `room` (`bandRoom`) outside what it
// draws (`inkOf`).
function markedOf(
  part: Element,
  room: number = bandRoom(part),
  scale: { x: number; y: number } = scaleOf(part),
): Box {
  const rect = part.getBoundingClientRect();
  const ink = inkOf(part, rect, scale);
  return {
    left: ink.left - room * scale.x,
    top: ink.top - room * scale.y,
    right: ink.right + room * scale.x,
    bottom: ink.bottom + room * scale.y,
  };
}
// Where the marks Leaf draws round `target` stand (surfaces.css): round each shown
// part, the room its band takes outside what the part draws (`inkedBox`), together;
// or null where no part shows. Every box states its room whether or not a mark shows,
// so a surface that stands clear of the marks, such as a thread's card or a preview,
// clears them before they show.
export const markedBox = (target: Element): Box | null =>
  union(shownParts(target).map((part) => markedOf(part)));
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
export function shownRect(item: Element, clips: ClipCache) {
  return clippedRect(shownBox(item), item, clips);
}
// `shownRect` with the box that supplies each of its edges (`holders`): the item's own,
// a box whose band clips it there, or null where the window does. A floating surface
// held in at one of those edges stands in that box's plane (floating.js).
export function shownRectHeld(
  item: Element,
  clips: ClipCache,
): (Box & { holders: Holders }) | null {
  const root = item.ownerDocument.scrollingElement;
  const own = item === root ? null : item;
  const holders: Holders = { left: own, top: own, right: own, bottom: own };
  const cuts = clipWalk(item, clips, false).cuts;
  const shown = cutBy(shownBox(item), cuts, root, true, holders);
  return shown && { ...shown, holders };
}
// What of an item the user sees: what every box over it lets through, within the visible
// viewport's height, less the boxes the chrome covers (`coverBoxes`), or null when none
// of it shows. A cover reaching into the item's columns takes the item from the cover to
// the window's edge it stands nearer (`coverCut`), so what is left is one box the user
// sees whole; a cover beside the item takes nothing. The viewport cuts
// only the item's top and foot; its sides stay the clip walk's, the layout viewport's,
// since a pinch zoom's visual viewport is a pan across the page and not a clip, and read
// with its sides a message wider than the zoomed view was never seen whole across, and
// never counted read. `item` is an element or a Range, and `box` the extent asked about,
// the item's own by default, or wider, as a focus ring's room is. `rest` reads the
// covers where they come to rest (`coverBoxes`), for a key that acts on the page as
// its motion will leave it.
export function seenRect(
  item: Element | Range,
  clips: ClipCache,
  box: Box = placeBox(item),
  rest: boolean = false,
) {
  const holder = placeHolder(item);
  // What clips a box only cuts it, so a box the visible viewport's height doesn't reach
  // shows nothing in front of the user, and its walk goes unread.
  if (!holder || outOfWindow(box)) return null;
  const shown = clippedPlace(item, clips, box);
  return shown ? inFront(shown, holder, rest) : null;
}
// Whether `box` stands wholly above or below the visible viewport, where none of it is
// in front of the user. It answers for a box with no height too, such as an empty
// outlet a comment box would be seated in (annotations/composing/surface.js, `seatFab`).
export function outOfWindow({ top, bottom }: Box) {
  const { offsetTop, height } = visualViewport;
  return bottom <= offsetTop || top >= offsetTop + height;
}
// What of `box`, already cut by every box clipping `item`, is in front of the user: its
// part within the visible viewport's height, less the boxes the chrome covers
// (`uncovered`), or null where none of it is. `seenRect` reads every item through it,
// and a box with no element of its own, a search match's line, asks it directly
// (key-badge-placement.js, `clearPart`).
export function inFront(box: Box, item: Node, rest: boolean = false) {
  const held = inViewportHeight(box);
  return held && uncovered(held, item, rest);
}
// What of `box` the visible viewport's height holds, or null where it holds none of it.
function inViewportHeight({ left, top, right, bottom }: Box) {
  const { offsetTop, height } = visualViewport;
  top = Math.max(top, offsetTop);
  bottom = Math.min(bottom, offsetTop + height);
  return bottom > top ? { left, top, right, bottom } : null;
}
// Whether the boxes the chrome covers, where they come to rest, are all that keeps the
// user from seeing `item` at `box`: some of it shows through every box clipping it and
// within the visible viewport's height, and the covers leave none of that, cut by the
// rule `seenRect` cuts with.
export function hiddenByCovers(item: Element | Range, box: Box) {
  const holder = placeHolder(item);
  if (!holder || outOfWindow(box)) return false;
  const shown = clippedPlace(item, new Map(), box);
  const held = shown && inViewportHeight(shown);
  return held ? !uncovered(held, holder, true) : false;
}
// The span `top` to `bottom` less what a cover in its columns takes: everything from the
// cover to the edge of `viewport` it stands nearer, the visible viewport unless the
// caller reads another, as the floating panel at the window's foot leaves no room under
// it. The page the gap between it and that edge shows is no room to read in, and
// counting a box seen there would leave a landing short of a message the panel hides.
// A span wholly past that edge keeps all of itself, as a seat scrolled below the window
// is under no cover there. `shownWindow` cuts by it in the viewport it reads, `uncovered`
// in the visible one.
function coverCut(
  over: Box,
  top: number,
  bottom: number,
  { offsetTop, height }: { offsetTop: number; height: number } = visualViewport,
) {
  if (over.top + over.bottom < 2 * offsetTop + height)
    return bottom <= offsetTop
      ? { top, bottom }
      : { top: Math.max(top, over.bottom), bottom };
  return top >= offsetTop + height
    ? { top, bottom }
    : { top, bottom: Math.min(bottom, over.top) };
}
// What of `box` the boxes the chrome covers leave (`coverBoxes`), but for one holding
// `item`, or null where they leave none of it: a cover reaching into the box's columns
// takes it from the cover to the window's edge it stands nearer (`coverCut`). `seenRect`
// and paint stacked above the chrome (`paintClips`) cut by it.
function uncovered(
  { left, top, right, bottom }: Box,
  item: Node,
  rest: boolean = false,
) {
  for (const over of coverBoxes(item, { rest })) {
    if (!overlapsAcross(over, { left, right })) continue;
    ({ top, bottom } = coverCut(over, top, bottom));
  }
  return bottom > top ? { left, top, right, bottom } : null;
}
// Whether the boxes the chrome covers will stand over any of `box` for `item`, by the
// rule `seenRect` cuts with, read where each comes to rest: a surface asks it before
// giving way to a place a landing is about to show (panel/floating-panel.js, `clearFor`), and
// a view still opening will cover what its drawn box doesn't reach yet. A cover's cut
// answers, not whether anything is left, so an empty box, such as a seat with nothing
// in it yet, is covered only where a cover stands over it.
export const covered = (box: Box, item: Node) =>
  coverBoxes(item, { rest: true }).some((over) => {
    if (!overlapsAcross(over, box)) return false;
    const left = coverCut(over, box.top, box.bottom);
    return left.top > box.top || left.bottom < box.bottom;
  });
// Whether the page draws `node` with what it holds: rendered (`checkVisibility`, with its
// `options`) and not hidden until found. An element `hidden="until-found"` keeps a box
// of its own while the browser skips its contents, until find-in-page or `reveal`
// (widget-elements.js) opens it, and `checkVisibility` answers only for that box, so
// it alone would count a folded thread message or an unchosen tab's panel as shown.
export const showsContents = (node: Element, options?: CheckVisibilityOptions) =>
  node.getAttribute("hidden") !== "until-found" && node.checkVisibility(options);
// Whether the page puts `node` before the user at all, before any question of where:
// drawn with its contents and visible, not inert, inside the topmost modal, and not
// hidden with `aria-hidden`. Exposure asks it of a message body and of a sample's frame.
export function presented(node: Element) {
  if (
    !showsContents(node, { visibilityProperty: true }) ||
    excludedByInert(node) ||
    !nativeModalAdmits(node)
  )
    return false;
  let at: Element | null = node;
  for (; at; at = renderedParent(at))
    if (at.getAttribute("aria-hidden") === "true") return false;
  return true;
}
// What this page shows of a sample's frame it holds, in the frame's own viewport
// coordinates: the frame's `seenRect`, within `within`, the window or what this page's
// own holder shows of it, carried into the frame's viewport by the inverse of its frame
// (element-axes.js, `elementBorderFrame`), or null where the user sees none of it. A
// turned frame's own viewport shows the box that covers what the user sees. The sample
// cannot read this itself: only this page knows the boxes its chrome covers over the
// frame, which cut it as they cut any of this page's boxes. A page in an ordinary
// iframe reads only its own window.
export function frameView(frame: HTMLIFrameElement, within: Box) {
  const seen = seenRect(frame, new Map());
  const shown = seen && intersect(seen, within);
  if (!shown || !hasArea(shown)) return null;
  const { matrix } = elementBorderFrame(frame);
  return carriedBox(
    matrix.translate(frame.clientLeft, frame.clientTop).inverse(),
    shown,
  );
}
// Everything besides a reader's own boxes that changes what `seenRect` reads, so a
// reader of what the user sees watches it here rather than keeping its own list: a
// scroll, a shadow stage's included (`watchScrolls`); a resize; the visual viewport,
// which a soft keyboard or a pinch-pan moves without either; a native layer opening or
// closing, which changes what a modal admits (`watchLayerChanges`); and chrome the room
// is measured against changing the box it covers, which its owner announces
// (`ROOM_MOVED`). Returns the call that stops watching.
const ROOM_MOVED = "lf-room-moved";
export const announceRoom = (target: EventTarget = document) =>
  target.dispatchEvent(new Event(ROOM_MOVED, { bubbles: true, composed: true }));
export function watchRoom(callback: () => void) {
  const viewport = visualViewport;
  const listening: [EventTarget, string, boolean?][] = [
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
// box in the band the scroller's `scroll-padding` leaves (the spec's optimal viewing
// region, which Chrome and WebKit take from it, and the root's landing band but while a
// floating editor holds focus: `landingBand`), so a change above that band moves
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
function motionBand(item: Element, clips: ClipCache) {
  const walk = clipWalk(item, clips, false);
  const all = { left: -Infinity, top: -Infinity, right: Infinity, bottom: Infinity };
  const heights = walk.cuts.map((each) => ({
    ...each,
    axes: { ...each.axes, x: false },
  }));
  const cut = cutBy(all, heights, item.ownerDocument.scrollingElement, true);
  if (!cut) return null;
  const room = shownWindow({ within: cut, item });
  if (room.height <= 0) return null;
  const scroller = walk.cuts.find(
    ({ box, scrolls }) => scrolls && box.scrollHeight > box.clientHeight,
  )?.box;
  const anchorBand = !scroller
    ? cut
    : scroller.scrollTop > 0
      ? insetBand(scroller, scrollPadding(getComputedStyle(scroller)))
      : shownBand(scroller);
  return anchorBand && anchorBand.top < room.bottom
    ? { top: anchorBand.top, bottom: room.bottom }
    : null;
}
// Whether a change of size anywhere in `node` would move what the user sees: some of it
// stands in its `motionBand`. A node not drawn changes nothing.
export function growthIsSeen(node: Element, clips: ClipCache = new Map()) {
  const { top, bottom, height } = node.getBoundingClientRect();
  if (!height) return false;
  const band = motionBand(node, clips);
  return band !== null && bottom > band.top && top < band.bottom;
}
// Whether growth after `node`, at its foot, would move what the user sees: the foot
// stands inside its `motionBand`.
export function growthAfterIsSeen(node: Element, clips: ClipCache = new Map()) {
  const { bottom, height } = node.getBoundingClientRect();
  if (!height) return false;
  const band = motionBand(node, clips);
  return band !== null && bottom > band.top && bottom < band.bottom;
}
// Calls `changed(now)` each time whether `holds(clips)` holds changes, its first reading
// included; returns the step that stops watching. `holds` is a reading of geometry such
// as `seenRect` or `growthIsSeen`. Every watch is read in one rendering pass with one
// clip cache, after anything that changes what the page shows of its window
// (`watchRoom`), a scroll's every frame included, or one of `nodes` entering or leaving
// the window, which a change of layout moving it does. A pass calls back only once
// every watch is read, so one that redraws cannot stale another's reading.
const watches: Set<{ read: (clips: ClipCache) => boolean; report: () => void }> =
  new Set();
let watchPass: ReturnType<typeof nextRender> | null = null;
let unlisten: (() => void) | null = null;
const readWatches = () => {
  watchPass = null;
  const clips = new Map();
  const moved = [...watches].filter((watch) => watch.read(clips));
  for (const watch of moved) if (watches.has(watch)) watch.report();
};
const rereadWatches = () => {
  watchPass ??= nextRender(readWatches);
};
export function whenChanges(
  holds: (clips: ClipCache) => unknown,
  changed: (now: boolean) => void,
  nodes: readonly Element[] = [],
) {
  let held: boolean | null = null;
  const watch = {
    report: () => changed(Boolean(held)),
    read(clips: ClipCache) {
      const now = Boolean(holds(clips));
      const moved = now !== held;
      held = now;
      return moved;
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
// Calls `leave` once `holds(node, clips)` stops holding for every one of `nodes`, and
// again each time it stops after holding once more (`whenChanges`).
export const whenNone = (
  nodes: readonly Element[],
  holds: (node: Element, clips: ClipCache) => unknown,
  leave: () => void,
) =>
  whenChanges(
    (clips) => nodes.some((node) => node.isConnected && Boolean(holds(node, clips))),
    (now) => {
      if (!now) leave();
    },
    nodes,
  );

// Where a member begins, as the user sees it: the first of the boxes it paints that
// survives the clips, rather than the bounds of all of them. They are the same box for
// anything in flow and different for an inline that wraps, whose bounds run from the
// column's left margin to its right — so a digit placed on that corner sat four hundred
// pixels from the link it addressed, a line above it, on top of somebody else's sentence.
// `shownBox`'s union answers "how much room does this take", which is what a legend box and
// an aim outline want; this answers "where does it start", which is what anything hung on a
// corner wants. The first that survives rather than the first outright, since a link whose
// opening line has scrolled away still has a corner on the line below it.
export const startsAt = (item: Element, clips: ClipCache) => {
  const fragments = item.getClientRects();
  return (fragments.length ? [...fragments] : [shownBox(item)])
    .map((box) => clippedRect(box, item, clips))
    .find(Boolean);
};
// What `item` draws inside `within`, one of its own boxes: the box round its words
// (`drawsText`) and the drawings among its contents (`draws`), or null where it draws
// neither there, as a control its stylesheet alone draws. A control's box can begin in
// padding the user can't see, as a tab's or an icon button's does, so a chip hung on
// that corner stands as near a neighbour's label as its own; hung on what the control
// draws, it stands on its label or glyph.
export function drawnBox(item: Element, within: Box) {
  const drawn: Box[] = [];
  const visit = (node: Node) => {
    for (const child of node.childNodes)
      if (child.nodeType === Node.TEXT_NODE) {
        if (drawsText(child.parentElement)) drawn.push(...contentsRects(child));
      } else if (child instanceof Element) {
        if (!draws(child)) visit(child);
        else if (
          child.checkVisibility({ opacityProperty: true, visibilityProperty: true })
        )
          drawn.push(child.getBoundingClientRect());
      }
  };
  visit(item);
  return union(drawn.map((box) => intersect(box, within)).filter(hasArea));
}
// The clips standing over a box, applied to it. Taken apart from shownRect because the two
// readings above and a painted Range want the same walk over different boxes.
// `stop` reads only native ancestor bands before that boundary. The viewport and sticky
// headers belong to the outer plane; margin seats keep their place while their CSS
// frames apply those cuts.
export const clippedRect = (
  box: Box,
  item: Element,
  clips: ClipCache,
  stop?: Element,
) => clipped(box, item, clips, false, true, stop);
// What cuts paint standing over an item's `box`, by the plane each cut stands in.
// `plane` is the one the paint stands in: the window's where a fixed box escapes every
// clip around it, and the page's otherwise, which the root scroll carries. `bands` are
// the boxes between it and the item whose bands cut it, outermost first, each band less
// the headers stuck over the item's view of it (`headerInset`); each stands in the plane
// of the box that holds it, kept where they cut the box whole. `window` is what the
// window leaves the paint, in the window's plane: the room below a header stuck over the
// root's top, cut, for paint stacked `aboveSurfaces`, at the edge of each box the chrome
// covers over what the bands leave of the box (`uncovered`), or null where neither cuts
// it, and empty where a cut hides the box whole. Paint stacked under the chrome is hidden
// by it where it stands. The window's own edges cut nothing in the page's plane, since
// paint past them is not drawn anyway, and cutting it there would move the cut with every
// scroll. Paint over what `item` holds (`held`), as words inside it, is cut by its own
// band too.
export function paintClips(
  item: Element,
  box: Box,
  clips: ClipCache,
  aboveSurfaces: boolean,
  held: boolean = false,
) {
  const walk = clipWalk(item, clips, held);
  const plane = walk.fixed ? "window" : "page";
  const root = item.ownerDocument.scrollingElement;
  const hidden = { plane, window: { left: 0, top: 0, right: 0, bottom: 0 }, bands: [] };
  // The root's band is the window's, which cuts only below a header stuck over it.
  let window = walk.cuts.find(({ box: cut, covered }) => cut === root && covered)?.band;
  const bands: (ClipCut & { band: Box })[] = [];
  for (const cut of walk.cuts) {
    const band = cut.band;
    if (!band) return hidden;
    if (cut.box !== root) bands.unshift({ ...cut, band });
  }
  // Cut away by the bands, the box keeps them, which a scroll may bring it into; under
  // headers that cover a band whole, it has none to keep.
  const shown = aboveSurfaces ? cutBy(box, walk.cuts, root, false) : null;
  if (shown) {
    const left = uncovered(shown, item);
    if (!left) return hidden;
    if (left.top > shown.top || left.bottom < shown.bottom) {
      window ??= layoutWindow(item.ownerDocument);
      window = {
        ...window,
        top: Math.max(window.top, left.top),
        bottom: Math.min(window.bottom, left.bottom),
      };
    }
  }
  return { plane, window: window ?? null, bands };
}
// The same walk for a box drawn in the document plane, which a root scroll carries with
// the page: the page's own boxes cut it, and the window does not, so a box scrolled off
// screen keeps its place for a reader asking how far away it stands.
const pagePlaneRect = (box: Box, item: Element, clips: ClipCache) =>
  clipped(box, item, clips, false, false);
// Whether a box Leaf stands against `target` belongs in layout: the target stands within
// a screen of the window, and within 600px of being scrolled into each scroller around
// it, so ordinary scrolling brings the box into layout before it carries the target on
// screen. A box out of layout costs no layout pass, where boxes hidden beside the shown
// ones made every pass revisit them all. `nearObserver` maintains the reading for the
// anchored controls (css-anchors.js, `anchorView`) and paint sets (readings/target-paint-geometry.js,
// `paintSet`), and starts work a widget holds until the reader nears it
// (readings/presentation.js, `whenNear`); `nearWindow` reads it at once for a first
// presentation, which cannot wait for the observer's first task. It clips at each
// scroller exactly, so it calls near only what the observer will, and the observer's
// first record adds the rest. A percentage scroll margin misreads in Chromium
// (notes/browser-support.md, "Percentage scroll margins in Chromium").
export const nearObserver = (callback: IntersectionObserverCallback) =>
  new IntersectionObserver(callback, { rootMargin: "100%", scrollMargin: "600px" });
export function nearWindow(target: Element, clips: ClipCache = new Map()) {
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
// Whether the browser draws the text `parent` holds. Ask the text's own parent rather than
// a block around it: display: contents still draws text, and a child can restore
// visibility inside a concealed block. Skipped subtrees are left alone before asking for
// any boxes. Text in display: contents has no parent box to ask, so its first boxed
// ancestor supplies the browser's opacity and display reading; visibility belongs to the
// text's parent, since its children may override that ancestor.
export const drawsText = (parent: Element | null) => {
  if (!parent || skipped(parent) || getComputedStyle(parent).visibility !== "visible")
    return false;
  let box: Element | null = parent;
  while (box && getComputedStyle(box).display === "contents") box = renderedParent(box);
  return Boolean(box?.checkVisibility({ opacityProperty: true }));
};
// The same walk for a box measured from what an element holds: a Range inside it. The
// holder's own band stands over its contents, where it says nothing about the holder's
// own box, so text scrolled out of the `pre` it sits in directly is text nobody sees.
export const clippedContents = (
  box: Box,
  holder: Element,
  clips: ClipCache,
  stop?: Element,
) => clipped(box, holder, clips, true, true, stop);
function clipped(
  box: Box,
  item: Element,
  clips: ClipCache,
  held: boolean,
  inWindow: boolean = true,
  stop?: Element,
) {
  const root = item.ownerDocument.scrollingElement;
  return cutBy(box, clipWalk(item, clips, held, stop).cuts, root, inWindow && !stop);
}
const BOX_EDGES: readonly (keyof Box)[] = ["left", "top", "right", "bottom"];
// `box` less the bands of `cuts`, each on the axes it clips, or null where they leave
// none of it. In the window's plane the window cuts it; in the page's plane the root's
// band is the window, which cuts nothing there, and only a header stuck over its top
// does. `holders`, where given, starts with the box each edge of `box` belongs to and
// ends with the box each edge of the answer does: the clip whose band cut that edge
// furthest in, the first on a tie, or null where the window or the root's band did.
function cutBy(
  box: Box,
  cuts: ClipCut[],
  root: Element | null,
  inWindow: boolean,
  holders?: Holders,
) {
  const cut = (
    shown: Box,
    edges: Box,
    holder: Element | null,
    axes?: { x: boolean; y: boolean },
  ) => {
    const next = intersect(shown, edges, axes);
    if (holders)
      for (const edge of BOX_EDGES)
        if (next[edge] !== shown[edge]) holders[edge] = holder;
    return next;
  };
  let shown = inWindow ? cut(box, layoutWindow(), null) : box;
  for (const { box: clip, band, axes, covered } of cuts) {
    if (!band) return null;
    const edges =
      !inWindow && clip === root
        ? {
            left: -Infinity,
            top: covered ? band.top : -Infinity,
            right: Infinity,
            bottom: Infinity,
          }
        : band;
    shown = cut(shown, edges, clip === root ? null : clip, axes);
  }
  const { left, top, right, bottom } = shown;
  return hasArea(shown) ? { left, top, right, bottom } : null;
}
// The clips standing over an item, innermost first: each ancestor whose band cuts it,
// with that band less the headers stuck over its top and the footers over its foot, and
// whether a fixed box among the item's ancestors escapes every clip further out, the
// root's included.
function clipWalk(item: Element, clips: ClipCache, held: boolean, stop?: Element) {
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
  let holder: Element | null = item;
  let escaped = false;
  let containing: Element | null | undefined = null;
  const cuts: ClipCut[] = [];
  clipEntries(item, clips, stop);
  let a: Element | null = item;
  for (; a && a !== stop; a = renderedParent(a)) {
    const c = clips.get(a) as ClipEntry;
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
    if (!escaped && c.placer !== undefined) {
      escaped = true;
      containing = c.placer;
    }
  }
  return { cuts, fixed: escaped && !containing };
}
// Each box's entry from `item` out to `stop`, made from the outside in, so a box's map
// into the window (element-axes.js, `elementMatrix`) turns the map of the box it stands
// in, and a pass reads each box's transform once however many walks pass the box.
function clipEntries(item: Element, clips: ClipCache, stop?: Element) {
  const walked: Element[] = [];
  for (let a = item as Element | null; a && a !== stop; a = renderedParent(a))
    walked.push(a);
  let above = stop ? clips.get(stop)?.matrix : undefined;
  for (const box of walked.reverse()) {
    let entry = clips.get(box);
    if (!entry) {
      const matrix = elementMatrix(box, above);
      entry = {
        matrix,
        band: shownBand(box, matrix),
        axes:
          box === box.ownerDocument.scrollingElement
            ? { x: true, y: true }
            : windowAxes(clippingAxes(getComputedStyle(box)), matrix),
        // Read here rather than out of shownBand, whose answer is a band and is the
        // render gate's too: what clips a box and what a box is positioned against are
        // two facts.
        placer: placedBy(box),
        scrolls: scrollContainer(box),
      };
      clips.set(box, entry);
    }
    above = entry.matrix;
  }
}

// The element a destination is measured through and scrolls with: itself, or the
// element holding a Range's start (`holdingElement`).
export const placeHolder = (where: Element | Range) =>
  where instanceof Range ? holdingElement(where.startContainer) : where;
// A destination's box: a Range's own, or an element's shown box (`shownBox`).
export const placeBox = (where: Element | Range) =>
  where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
// What the page's clips leave of a destination's `box`: a Range's walked from the
// element holding it (`clippedContents`), an element's from itself (`clippedRect`),
// out to `stop` where one is given.
export const clippedPlace = (
  where: Element | Range,
  clips: ClipCache,
  box: Box = placeBox(where),
  stop: Element | undefined = undefined,
) => {
  if (!(where instanceof Range)) return clippedRect(box, where, clips, stop);
  const holder = placeHolder(where);
  return holder && clippedContents(box, holder, clips, stop);
};
// Where a box stacks among the page's root-level layers: the z-index of its outermost
// positioned ancestor that sets one, and above all of them in the top layer. Both are
// read up the tree as rendered, where a slotted box stacks inside its slot's ancestors.
// The chrome's root follows `body` at the largest z-index and wins every tie by tree
// order (elements.css, `:root > .lf-chrome`), so a chrome box reads its own rung above every
// level a page box can read, whatever z-index the page sets.
export const CHROME_LEVEL = 2 ** 31;
export function stackLevel(node: Element) {
  let level = 0;
  let a: Element | null = node;
  for (; a; a = renderedParent(a)) {
    if (isNativeLayer(a)) return Infinity;
    if (a.matches(":root > .lf-chrome")) return CHROME_LEVEL + level;
    const { position, zIndex } = getComputedStyle(a);
    if (position !== "static" && zIndex !== "auto") level = Number(zIndex);
  }
  return level;
}
