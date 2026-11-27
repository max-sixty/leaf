/* The user's place in a scroller, written down as a landmark rather than an offset.
 *
 * A place names what stands at the scroller's landing edge. Where the edge cuts a
 * drawing (a replaced element such as an image or an svg, or a widget's custom
 * element) or a box that scrolls its words on its own without being a reading region,
 * the place is that box and how far through its height the edge cuts it, so the reader
 * keeps seeing the same part of it as it scales or as content arrives around it. It is
 * a live node, held weakly, so a revision that replaces it loses it, and the line below
 * it stands for it. Otherwise the place is the line at the edge: the first line whose
 * middle stands at or below the edge, read down the blocks on screen in document
 * order, quoted from its first character with the context a comment's capture gives a
 * quote (anchor-resolution.js, `anchorForPassage`), and that line's distance below the
 * edge. A projected passage retains that anchor's datum identity and source, so repeated
 * words on another row cannot take its place. The lines above it in its paragraph can
 * rewrap or be rewritten without moving the line the reader sees. A heading is read
 * whole, from its first word, wherever any
 * of it shows below the edge. A run of fewer than `QUOTABLE` characters, a nav's label
 * or a list of names, is apparatus beside the reading and names no place, nor do words
 * in a stuck box, which ride with every scroll, or in a box scrolling on its own. Where
 * blocks stand side by side at that line, as columns do, the line is taken from the one
 * across the reader's column: where their pointer last named their place, or failing
 * that where focus stands. Failing a line, the place is the first block's section;
 * failing that, the raw offset, which only the same scroller, at the same width and,
 * where it shows the document, in the same revision, can take back: otherwise it names
 * other content, and the browser's own scroll anchoring keeps what the reader saw better
 * than it can. Leaf's own interface, such as the Threads list, draws what the log holds
 * rather than the revision, and its words name no place, so where a revision reloads
 * the document and nothing is left to anchor, the box that replaces the one that read
 * the offset takes it back. A bounded block
 * following its newest entry has its end as its place (`bounds.js`, `followingItsEnd`),
 * however many entries have arrived since. A box standing at its start is read from its
 * top: its own box returns to its start, across a resize or a revision, so a page read
 * from its top keeps its title in view, and only a box its words are handed to takes
 * the landmark. The user chose this over keeping the first line at the
 * edge, which scrolls the title away where a header fixed beside that line drops into
 * the flow above it as the window narrows.
 * `capturePlace` reads one, of the page or of a reading region, and `restorePlace`
 * returns the user to it: the passage is found again by its words, so a place survives
 * what moved the pixels under it — a new revision, a resize, a view that was hidden
 * while its width changed. A focused destination where the user is (user-place.js,
 * `focusPlace`), and not riding a stuck box (dom/geometry.js, `stuckBox`), is the live place
 * while that gesture still holds focus in this region. Focus on the reading surface
 * itself keeps its passage as the place, and so
 * does focus on a container holding that passage, as a section a fragment landed on. The
 * destination's DOM identity stays local; serialized places and replaced elements use
 * the ordinary passage reading, and the node is held weakly, since a place can outlive
 * the document that drew it. A restore jumps rather than glides. It keeps the reader's
 * current disclosures and views: a landmark they concealed supplies no geometry. It
 * returns the reader to a place they had rather than choosing one, so it says where it
 * left each box it moved (dom/scrolling.js, `placeKept`).
 *
 * Whoever remembers a place owns when to take it and where to keep it: version
 * continuity (features/version.js) across revisions, reading-region shifts and the subjects a
 * region shows in turn, records/views.js for each view of the page's flow that a widget shows
 * in turn, and history for each entry the user leaves, in the entry's record
 * (records/history.js).
 * `readingBlock` is the block on screen the reader reads in one region or the page,
 * across the column their pointer or focus names, the column a captured place reads its
 * line from; `sectionsInView` names the sections of every block and drawing on screen,
 * which a page comment records; `pageReadingBlock` is what the user is reading where
 * focus is not where they are (user-place.js, `focusPlace`), where a walk starts; and
 * `landingPlace` is where a let-go puts them, beside what they let go of where they see
 * it. A glide under way moves where the reader reads and what they see beside them to
 * where it is headed, and leaves what a captured place records where it stands, since a
 * restore puts the page back from where it is.
 */
import { setScroll } from "../dom/arrivals.js";
import {
  clippedContents,
  landingBand,
  placeHolder,
  seenRect,
  shownBox,
  shownWindow,
  userScrollport,
  stuckBox,
  drawsText,
  placedBy,
  scrollsBy,
  stickyHolder,
} from "../dom/geometry.js";
import { scrollAxes } from "../dom/element-axes.js";
import { DRAWING, draws } from "../lib/shown-box.js";
import { layoutsChanged } from "../state/visual-parts.js";
import {
  composedParentNode,
  drawn,
  isElement,
  isHTML,
  skipped,
  skipper,
  renderedOrder,
  renderedParent,
  under,
  upFrom,
  closestAcross,
} from "../lib/shadow-tree.js";
import { inUi, inChrome } from "../base/ui-marks.js";
import {
  blockAt,
  layoutBox,
  HEADING,
  pageDocument,
  readsDocument,
  pageRuns,
  quoteFrom,
  rangeOf,
  readingFrom,
  readingParts,
  segmentsBox,
} from "./passages.js";
import {
  ADDRESSABLE,
  anchorForPassage,
  resolveAnchor,
  sectionOf,
} from "./anchor-resolution.js";
import { targetElement, targetSegments } from "./resolved-target.js";
import {
  containingReadingRegionFor,
  effectiveScroller,
  readingRegionFor,
  readingRegions,
  scrollersOf,
  shownRegionBounds,
  pageReadingRegion,
  unconcealedReadingRegions,
} from "./reading-regions.js";
import { followingItsEnd } from "./bounds.js";
import {
  aimedTop,
  moveScrollerBy,
  pageScroller,
  placeKept,
  scrollToEnd,
} from "../dom/scrolling.js";
import { runtime } from "../state/context.js";
import { retainUserIntent } from "../dom/user-intent.js";
import { recentPlaceInput, focused } from "../dom/focus.js";
import { focusPlace, readingAt, readingLine } from "./user-place.js";
import { scrollIntoView } from "./landing-scroll.js";
import { heldTravel, seenAhead, seenGlided, seenLanded } from "./scroll-containers.js";
import { shifted, union } from "../dom/rect.js";
import { pointerAt } from "../base/pointer.js";
import { keptEach } from "../state/kept.js";
import { objectIds } from "../base/ids.js";

/** @typedef {import("./passages.js").Segment} Segment
 * @typedef {import("./passages.js").BlockRun} BlockRun
 * @typedef {import("./reading-regions.js").ReadingRegion} ReadingRegion
 * @typedef {import("../base/box.js").Box} Box
 * @typedef {import("../dom/user-intent.js").UserIntent} UserIntent
 * @typedef {Partial<import("../../types/domain.js").Anchor> & {
 * y: number, scroller: string | undefined, width: number, revision: number | null,
 * start?: true, end?: true,
 * [READ_BOX]?: WeakRef<Element>,
 * [FOCUSED_PLACE]?: {node: WeakRef<Element>, body: WeakRef<Element>, region: string | undefined, intent: UserIntent},
 * [DRAWN_PLACE]?: {node: WeakRef<Element>, through: number}
 * } & ({quote: string, quoteTop: number} | {quote?: never, quoteTop?: never}) &
 * ({section: string, sectionTop: number | null} | {section?: null, sectionTop?: null})} ReadingPlace
 * @typedef {{segments: Segment[], boxes: DOMRect[]}} DrawnRun */

// A live focused place belongs to this DOM, not a serialized history record. Its
// symbol keeps that node out of JSON; the ordinary passage reading remains the
// fallback when a replacement or a later gesture has given focus elsewhere. The node
// and its reading surface are held weakly: a place outlives the revision that removes
// them until the reader next records one.
const FOCUSED_PLACE = Symbol("live focused place");
/** @param {ReadingPlace | null | undefined} reading */
const focusedPlace = (reading) => {
  const place = reading?.[FOCUSED_PLACE];
  const node = place?.node.deref();
  return place &&
    node?.isConnected &&
    node === focused() &&
    under(node, place.body.deref()) &&
    containingReadingRegionFor(node)?.id === place.region &&
    place.intent()
    ? node
    : null;
};
// The box that read a raw offset, as local to this DOM as a focused place: a reading
// that crosses a reload arrives without it (`rawOffsetFits`).
const READ_BOX = Symbol("box that read the offset");
// A box the edge cuts that draws what the reader sees without words of the page, and
// how far through its height the edge cuts it: live like a focused place, and as local
// to this DOM. A revision that keeps the node keeps the place; one that replaces it
// leaves its section to stand for it.
const DRAWN_PLACE = Symbol("live drawn place");
/** @param {ReadingPlace | null | undefined} reading */
const drawnPlace = (reading) => {
  const place = reading?.[DRAWN_PLACE];
  const node = place?.node.deref();
  if (!place || !node?.isConnected || !drawsText(node)) return null;
  const top = () => {
    const rect = shownBox(node);
    return rect.top + place.through * rect.height;
  };
  return { node, top };
};
const LANDMARK_CAP = 160;
// The shortest run of words that names a reading place (`capturePlace`).
const QUOTABLE = 24;

// Whether a part of the page's reading (passages.js, `pageRuns`) may show words: rendered
// (`checkVisibility`), or with a rendered child, as an element whose display is
// `contents` has no box and shows through its children. A part the browser skips while it
// is far from the window (`content-visibility: auto`) shows its words as it nears it, so
// it may. A part the page skips, as in a closed tab, is asked nothing more: asking its box
// or its style has the browser style everything it holds.
/** @param {Element} part */
const showsWords = (part) =>
  part.checkVisibility() || [...part.children].some((child) => child.checkVisibility());
// Whether it may show words in the window now: drawn (`drawn`), or with a drawn child,
// and with a box that reaches the window, or none of its own.
/** @param {Element} part */
export const mayShow = (part) => {
  if (!drawn(part) && ![...part.children].some(drawn)) return false;
  const { top, right, bottom, left, width, height } = part.getBoundingClientRect();
  return (
    !(width || height) ||
    (bottom > 0 && top < innerHeight && right > 0 && left < innerWidth)
  );
};

// Source blocks include concealed words, since an anchor can reveal them. A reading
// place instead requires words the browser draws (dom/geometry.js, `drawsText`).
// The browser can bound a block's text in one Range read, including positioned
// children outside its own box. A Range cannot cross shadow roots or read skipped
// contents without forcing their layout; those blocks keep the per-segment reading.
/** @param {Element} block @param {Segment[]} segments @param {Range} range */
const textEnvelope = (block, segments, range) => {
  if (
    !segments.every(({ node }) => block.contains(node)) ||
    [...block.querySelectorAll("*")].some(skipped)
  )
    return null;
  range.selectNodeContents(block);
  return range.getBoundingClientRect();
};
// Where each run's words stood the last time a reading of the screen laid the page out,
// so a later reading measures only the runs that stood in its band rather than every
// block of the page on each scroll, key and focus. An observer of every block would read
// them all itself on each frame of a scroll, a cost on every wheel step that grows
// with the page.
//
// The page is laid out in frames: boxes whose runs keep their places relative to the box
// as anything scrolls, each laid out in its own coordinates (`originOf`). The box a
// reading reads is one, and so is every box inside it that moves what it holds against
// that box, or may hold it unlaid: one that scrolls, one sticky, one a box outside it
// places (dom/geometry.js, `placedBy`), as the window places a box fixed in it, and one that
// may skip its contents, a disclosure or a box with `content-visibility`, laid out once
// it draws them. A run stands where its own box and its words reach (`envelope`). A frame stands
// in the layout around it as one entry, which a reading descends into where its band
// reaches it: at its own box, or for a sticky box at the block it moves within
// (dom/geometry.js, `stickyHolder`). A box placed from outside moves with nothing the box
// around it holds, and a sticky box whose block is that box moves anywhere in it, so
// every reading of that box descends into them.
//
// A frame's layout stands while the page's words, the parts drawn, the window, and the
// frame's size, scroll axes and skipping are as they were, until a widget says its
// layout changed (state/visual-parts.js, `layoutsChanged`), and while every entry a reading
// finds in its band, and the first past it, stands where the layout has it: a change in
// flow at or above the band's foot moves one of those. A box moved by none of these, such
// as a paragraph a script transforms or one an anchor places, stays where the layout has
// it until a change lays the page out again. Any widget's notice lays out every frame
// again.
/** @typedef {{run: BlockRun, order: number}} Member
 * @typedef {{top: number, bottom: number, left: number, right: number}} Span
 * @typedef {Span & ({member: Member, byBox: boolean} | {frame: Element, at: Element})} Entry
 * @typedef {{key: string, laid: Entry[], reach: number[], held: Element[]}} Layout
 * @typedef {{source: string, members: Member[], layout: Layout | null}} Frame
 * @typedef {{key: string, runs: BlockRun[]}} ShownRuns
 * @typedef {{key: string, blocks: Set<Element>, holdsBlocks: WeakSet<Element>, holding: WeakSet<Element>}} BlockIndex
 * @typedef {{frames: WeakMap<Element, Frame>, shown: ShownRuns | null, index: BlockIndex | null}} Kept */
// The layout, the runs shown and their blocks hold the page's nodes, so they are kept with
// the page's reading (passages.js, `readsDocument`) and go with it: a revision that
// removes a block leaves none of them holding it.
const keptWithPage = keptEach((/** @type {Element} */ page) => {
  readsDocument(page);
  return /** @type {Kept} */ ({ frames: new WeakMap(), shown: null, index: null });
});
const kept = () => keptWithPage(pageDocument());
const idOf = objectIds();
// How a box frames what it holds wherever it is placed (`frameOf` adds a box placed from
// outside): `sticky` in the block it moves within, `flow` where it scrolls what it holds
// or may skip it, as a disclosure or a box with `content-visibility` does (`skipper`);
// null where it frames nothing.
/** @param {Element} element @param {CSSStyleDeclaration} style @returns {"sticky" | "flow" | null} */
function framing(element, style) {
  if (style.position === "sticky") return "sticky";
  return scrollsBy(style) ||
    style.contentVisibility !== "visible" ||
    isHTML(element, "details")
    ? "flow"
    : null;
}
// Whether a frame skips what it holds now: a disclosure while it is closed, or a box
// skipping its first run.
/** @param {Element} box @param {Element | null | undefined} first */
const skipping = (box, first) =>
  isHTML(box, "details") ? !box.open : Boolean(first && skipper(first) === box);
// Where a frame puts the origin of what it holds, in the window's coordinates: where its
// box stands, less what it has scrolled, as far as one scrolled pixel moves its contents
// in the window (`scrollAxes`).
/** @param {Element} box @param {ReturnType<typeof scrollAxes>} axes @returns {{x: number, y: number}} */
function originOf(box, axes) {
  if (box === pageScroller) return { x: -scrollX, y: -scrollY };
  const { left, top } = box.getBoundingClientRect();
  return {
    x: left - box.scrollLeft * axes.x.x - box.scrollTop * axes.y.x,
    y: top - box.scrollLeft * axes.x.y - box.scrollTop * axes.y.y,
  };
}
// The band a run's words may be drawn in: its block's own box, and the box a Range of
// its words reads, or failing that each word's; and whether that band is the block's own
// box (`byBox`), so a later reading can check the run by that box alone rather than by
// each of its words, which for a long text document's block is every line.
/** @param {BlockRun} run @param {Range} range @returns {(Span & {byBox: boolean}) | null} */
function envelope({ block, segments }, range) {
  if (!block) return null;
  const own = block.getBoundingClientRect();
  const words = textEnvelope(block, segments, range) ?? wordsBox(segments, range);
  /** @type {Box[]} */
  const drawn = [];
  for (const rect of [own, words])
    if (rect && (rect.width || rect.height)) drawn.push(rect);
  const reached = union(drawn);
  if (!reached) return null;
  const { top, bottom, left, right } = reached;
  const byBox =
    Math.abs(top - own.top) <= 1 &&
    Math.abs(bottom - own.bottom) <= 1 &&
    Math.abs(left - own.left) <= 1 &&
    Math.abs(right - own.right) <= 1;
  return { top, bottom, left, right, byBox };
}
/** @param {Segment[]} segments @param {Range} range */
const wordsBox = (segments, range) =>
  union([...drawnSegments(segments, range)].flatMap((one) => one?.[1] ?? []));
// Each segment with the boxes its words are drawn in, or null for one the browser draws
// none of: in a parent that draws no text (dom/geometry.js, `drawsText`), and every later one
// inside the box skipping it, which passes unasked, since asking for a box inside skipped
// content lays it out. `drawn` keeps each parent's answer across the calls sharing it.
/** @param {Segment[]} segments @param {Range} range @param {Map<Element | null, boolean>} [drawn] @returns {Generator<[Segment, DOMRect[]] | null>} */
function* drawnSegments(segments, range, drawn = new Map()) {
  // Whether a null already stands for the segments since the last drawn one, so a long
  // run of skipped lines yields once.
  let broken = false;
  for (let at = 0; at < segments.length; at++) {
    const segment = /** @type {Segment} */ (segments[at]);
    const { node, start, end } = segment;
    let rects = null;
    const parent = renderedParent(node);
    if (!drawn.has(parent)) drawn.set(parent, drawsText(parent));
    if (drawn.get(parent)) {
      range.setStart(node, start);
      range.setEnd(node, end);
      rects = [...range.getClientRects()].filter((rect) => rect.width && rect.height);
    } else {
      const hidden = parent && skipper(parent);
      if (hidden) at = lastHeld(segments, at, hidden);
    }
    if (rects?.length) {
      broken = false;
      yield [segment, rects];
    } else if (!broken) {
      broken = true;
      yield null;
    }
  }
}
// The last of `segments` from `at` on that `box` holds. A walk meets what a box holds
// together, so they are found by doubling a step past `at` and then halving it, and a
// long text document's skipped lines cost a few questions a run of them rather than one
// a line. A segment `box` draws without
// holding it, as a slot draws what is assigned to it, can stand among those it holds.
// The search may stop at it, and `drawnSegments` asks it its own question, or step over
// it, which gives it the same answer: whatever a skipped box draws is undrawn too.
/** @param {readonly Segment[]} segments @param {number} at @param {Element} box */
function lastHeld(segments, at, box) {
  /** @param {number} i */
  const holds = (i) => box.contains(/** @type {Segment} */ (segments[i]).node);
  let low = at;
  let step = 1;
  for (; low + step < segments.length && holds(low + step); step *= 2) low += step;
  let high = Math.min(low + step, segments.length);
  while (high - low > 1) {
    const middle = (low + high) >> 1;
    if (holds(middle)) low = middle;
    else high = middle;
  }
  return low;
}
// The page's runs the user may see, in reading order, with what names that reading of
// the page: its words and the parts shown, read again only when either changes. A reading
// place reads them to find which passage the user returns to and where a walk starts;
// its landmark is the top of a block's first line (a range), not its border box, and a
// restore measures the matched text the same way, so the line box's leading cancels out.
// The blocks are the page reading's (passages.js, `pageRuns`) rather than a query of the
// light DOM: a declared shadow root renders authored words at its host's place in reading
// order, and those words are pointable and resolvable through the same reading, so
// version continuity must be able to choose the same blocks as landmarks. A part of the
// reading that can't show any (`showsWords`) is not read, so a place costs the documents
// drawn, not those in closed tabs. Whether a part reaches the window is left to the
// layout, so a part scrolling into view reads no run again.
/** @returns {ShownRuns} */
function shownRuns() {
  const parts = readingParts().filter(showsWords);
  const key = parts.map(idOf).join(" ");
  const keeping = kept();
  if (keeping.shown?.key !== key) {
    const showing = new Set(parts);
    keeping.shown = { key, runs: pageRuns((part) => showing.has(part)) };
  }
  return keeping.shown;
}
// The blocks of those runs, every element holding one (`holdsBlocks`), and every element
// holding one or a part of the page's reading (`holding`), read once for each reading of
// the page and parts shown, so a question about one node asks no list of the page.
/** @returns {BlockIndex} */
function blockIndex() {
  const { runs, key } = shownRuns();
  const keeping = kept();
  if (keeping.index?.key === key) return keeping.index;
  /** @type {Set<Element>} */
  const blocks = new Set();
  /** @type {WeakSet<Element>} */
  const holdsBlocks = new WeakSet();
  /** @type {WeakSet<Element>} */
  const holding = new WeakSet();
  /** @param {Element} element @param {WeakSet<Element>[]} sets */
  const hold = (element, ...sets) => {
    for (
      let at = /** @type {Node | null} */ (element);
      at;
      at = composedParentNode(at)
    ) {
      if (!isElement(at)) continue;
      const held = at;
      if (sets.every((set) => set.has(held))) return;
      for (const set of sets) set.add(held);
    }
  };
  for (const { block } of runs)
    if (block && !blocks.has(block)) {
      blocks.add(block);
      hold(block, holdsBlocks, holding);
    }
  for (const part of readingParts()) hold(part, holding);
  return (keeping.index = { key, blocks, holdsBlocks, holding });
}
// The runs whose words stood in `band` where the page was last laid out for `box`, in
// reading order, laying out again each frame that no longer stands. A box scrolling in
// the page shows only what stands across its band; the page's reading takes in what
// stands beside the window too, as `blocksOnScreen` asks only how far down it is.
/** @param {Element} box @param {Pick<Box, "top" | "bottom"> & Partial<Pick<Box, "left" | "right">>} band @param {Range} range */
function runsIn(box, band, range) {
  const { key, runs } = shownRuns();
  let frame = kept().frames.get(box);
  if (frame?.source !== key) {
    /** @type {Member[]} */
    const members = [];
    runs.forEach((run, order) => {
      if (run.block && under(run.block, box)) members.push({ run, order });
    });
    kept().frames.set(box, (frame = { source: key, members, layout: null }));
  }
  /** @type {Member[]} */
  const found = [];
  const page = [key, layoutsChanged(), innerWidth, innerHeight].join(" ");
  const across = {
    top: band.top,
    bottom: band.bottom,
    left: box === pageScroller ? -Infinity : (band.left ?? -Infinity),
    right: box === pageScroller ? Infinity : (band.right ?? Infinity),
  };
  readFrame(box, frame, page, across, range, found);
  return found.sort((a, b) => a.order - b.order).map(({ run }) => run);
}
/** @param {Element} box @param {Frame} frame @param {string} page @param {Span} band @param {Range} range @param {Member[]} found */
function readFrame(box, frame, page, band, range, found) {
  const axes = scrollAxes(box);
  const first = frame.members[0]?.run.block;
  const key = [
    page,
    box.clientWidth,
    box.scrollWidth,
    box.scrollHeight,
    axes.x.x,
    axes.x.y,
    axes.y.x,
    axes.y.y,
    skipping(box, first),
  ].join(" ");
  for (let fresh = frame.layout?.key !== key; ; fresh = true) {
    const origin = originOf(box, axes);
    if (fresh || !frame.layout) frame.layout = layOut(box, frame, key, origin, range);
    const { laid, reach, held } = frame.layout;
    const top = band.top - origin.y;
    const bottom = band.bottom - origin.y;
    const left = band.left - origin.x;
    const right = band.right - origin.x;
    let low = 0;
    let high = laid.length;
    while (low < high) {
      const middle = (low + high) >> 1;
      if ((reach[middle] ?? -Infinity) > top) high = middle;
      else low = middle + 1;
    }
    /** @type {Entry[]} */
    const inBand = [];
    let at = low;
    for (let one = laid[at]; one && one.top < bottom; one = laid[++at])
      if (one.bottom > top && one.right > left && one.left < right) inBand.push(one);
    const past = laid[at];
    /** @param {Entry} one */
    const stands = (one) => {
      if ("frame" in one) return standsAt(one, one.at.getBoundingClientRect());
      const { block } = one.member.run;
      if (block === box) return true;
      if (!block || skipped(block)) return false;
      return one.byBox
        ? standsAt(one, block.getBoundingClientRect())
        : standsAt(one, envelope(one.member.run, range));
    };
    /** @param {Entry} one @param {Pick<Box, "top" | "bottom" | "left" | "right"> | null} now */
    const standsAt = (one, now) => {
      return (
        now !== null &&
        Math.abs(now.top - origin.y - one.top) <= 1 &&
        Math.abs(now.bottom - origin.y - one.bottom) <= 1 &&
        Math.abs(now.left - origin.x - one.left) <= 1 &&
        Math.abs(now.right - origin.x - one.right) <= 1
      );
    };
    if (!fresh && !(inBand.every(stands) && (!past || stands(past)))) continue;
    for (const one of inBand) {
      if ("member" in one) found.push(one.member);
      else readInner(one.frame, page, band, range, found);
    }
    for (const inner of held) readInner(inner, page, band, range, found);
    return;
  }
}
// A frame inside the box a reading reads that scrolls what it holds shows only what
// stands in its own box, so its band is cut to that box, which a glide of the box around
// it carries with what it holds. The box a reading reads scrolls what it holds against its
// own box, so its band is the reading's.
/** @param {Element} box @param {string} page @param {Span} band @param {Range} range @param {Member[]} found */
function readInner(box, page, band, range, found) {
  const frame = kept().frames.get(box);
  if (!frame) return;
  if (scrollsBy(getComputedStyle(box))) {
    const { top, bottom, left, right } = box.getBoundingClientRect();
    band = {
      top: Math.max(band.top, top),
      bottom: Math.min(band.bottom, bottom),
      left: Math.max(band.left, left),
      right: Math.min(band.right, right),
    };
    if (band.bottom <= band.top || band.right <= band.left) return;
  }
  readFrame(box, frame, page, band, range, found);
}
// Lays out the runs a frame holds, each run outside the frames inside it as an entry of
// its own, and each such frame as one entry, or among those every reading descends into,
// with the runs it holds left for it to lay out where a reading reaches it.
/** @param {Element} box @param {Frame} frame @param {string} key @param {{x: number, y: number}} origin @param {Range} range @returns {Layout} */
function layOut(box, frame, key, origin, range) {
  /** @type {Map<Element, ReturnType<typeof framing>>} */
  const kinds = new Map();
  /** @type {Map<Element, Element>} */
  const holders = new Map();
  /** @type {Set<Element>} */
  const placed = new Set();
  // The frame `node` stands in inside `box`: the outermost box between them, climbing by
  // what places each (`placedBy`), that frames what it holds or that a box outside `box`
  // places; `box` itself where none does.
  /** @param {Element} node @returns {Element} */
  const frameOf = (node) => {
    if (node === box) return box;
    let holder = holders.get(node);
    if (holder === undefined) {
      const style = getComputedStyle(node);
      const kind = framing(node, style);
      kinds.set(node, kind);
      const placer = placedBy(node, style);
      const carrier = placer === undefined ? renderedParent(node) : placer;
      const outer =
        carrier && (placer === undefined || carrier === box || under(carrier, box))
          ? frameOf(carrier)
          : null;
      if (!outer) placed.add(node);
      holder = !outer || (outer === box && kind) ? node : outer;
      holders.set(node, holder);
    }
    return holder;
  };
  /** @param {{top: number, bottom: number, left: number, right: number}} rect @returns {Span} */
  const span = ({ top, bottom, left, right }) => ({
    top: top - origin.y,
    bottom: bottom - origin.y,
    left: left - origin.x,
    right: right - origin.x,
  });
  /** @type {Entry[]} */
  const laid = [];
  /** @type {Map<Element, Member[]>} */
  const inner = new Map();
  for (const member of frame.members) {
    const { block } = member.run;
    if (!block || inChrome(block)) continue;
    // A block the browser skips stands in the frame of the box skipping it, which is
    // drawn: asking the block's own style has the browser style what it skips.
    const skip = skipper(block);
    const holder = frameOf(skip ?? block);
    if (holder !== box) {
      const members = inner.get(holder);
      if (members) members.push(member);
      else inner.set(holder, [member]);
      continue;
    }
    if (skip) continue;
    // The frame's own block, such as a `pre` scrolling its lines, shows its words only
    // where the frame shows, so it stands in every band and is measured as it is read.
    if (block === box) {
      const all = {
        top: -Infinity,
        bottom: Infinity,
        left: -Infinity,
        right: Infinity,
      };
      laid.push({ member, ...all, byBox: false });
      continue;
    }
    const at = envelope(member.run, range);
    if (at) laid.push({ member, ...span(at), byBox: at.byBox });
  }
  /** @type {Element[]} */
  const held = [];
  for (const [holder, members] of inner) {
    kept().frames.set(holder, { source: frame.source, members, layout: null });
    const at = placed.has(holder)
      ? box
      : kinds.get(holder) === "sticky"
        ? stickyHolder(holder, box)
        : holder;
    if (at === box) held.push(holder);
    else if (at && !skipped(at)) {
      const rect = at.getBoundingClientRect();
      if (rect.bottom > rect.top) laid.push({ frame: holder, at, ...span(rect) });
    }
  }
  laid.sort((a, b) => a.top - b.top);
  /** @type {number[]} */
  const reach = [];
  for (const { bottom } of laid)
    reach.push(Math.max(reach.at(-1) ?? -Infinity, bottom));
  return { key, laid, reach, held };
}
// Each block's drawn words, with the union of their boxes, of the blocks under `inside`
// where one is given, from the runs `box` showed in `band` (`runsIn`).
/** @param {Element} box @param {Element | null} inside @param {Pick<Box, "top" | "bottom"> & Partial<Pick<Box, "left" | "right">>} band @returns {Generator<[Element, DOMRect, DrawnRun[]]>} */
function* renderedBlocks(box, inside, band) {
  // A datum can split its parent's words. Keep the parent's later continuation after
  // that datum, rather than collecting both sides under the parent's first occurrence.
  const drawn = new Map();
  const range = document.createRange();
  for (const blockRun of runsIn(box, band, range)) {
    const { block, segments } = blockRun;
    if (!block || (inside && !under(block, inside))) continue;
    // Skipped content stays unmeasured: asking for a box inside it lays it out.
    if (inChrome(block) || skipped(block)) continue;
    /** @type {DOMRect[]} */
    const boxes = [];
    /** @type {DrawnRun[]} */
    const runs = [];
    /** @type {DrawnRun | null} */
    let run = null;
    for (const one of drawnSegments(segments, range, drawn)) {
      if (!one) {
        run = null;
        continue;
      }
      const [segment, rects] = one;
      if (!run) runs.push((run = { segments: [], boxes: [] }));
      run.segments.push(segment);
      run.boxes.push(...rects);
      boxes.push(...rects);
    }
    const rect = union(boxes);
    if (rect)
      yield [block, new DOMRect(rect.left, rect.top, rect.width, rect.height), runs];
  }
}

// The page block a node stands in, among those the user may see.
/** @param {Node} node */
function passageBlock(node) {
  const { blocks } = blockIndex();
  for (
    let at = node instanceof Element ? node : node.parentElement;
    at;
    at = upFrom(at)
  )
    if (blocks.has(at)) return at;
  return null;
}

// What the reader can see of a region, or with none given of the page: null where they
// see none of it. A flowing region is read through the part of the window the page
// shows: a line hidden under the chrome is not where the user is.
/** @param {ReadingRegion | null | undefined} region */
function readingBounds(region) {
  const shown = region ? shownRegionBounds(region) : shownWindow();
  if (!shown) return null;
  return region && effectiveScroller(region) === pageScroller
    ? shownWindow({ within: shown })
    : shown;
}

// With `inside`, only the blocks under it are read. With `band`, only blocks whose words
// reach that band are measured. With `ahead`,
// they are read where the glides under way leave them (scroll-containers.js,
// `heldTravel`, `seenGlided`), since a key pressed while one runs acts as though it had
// landed (user-place.js, `focusPlace`). A region a glide around it carries is read
// where its bounds stand now.
/** @param {ReadingRegion | null} [region] @param {Element | null} [inside] @param {Pick<Box, "top" | "bottom"> | null} [band] @param {boolean} [ahead] @returns {Generator<[Element, DOMRect, Segment[][]]>} */
export function* blocksOnScreen(
  region = null,
  inside = null,
  band = null,
  ahead = false,
) {
  const bounds = readingBounds(region);
  if (!bounds) return;
  const travel = ahead
    ? heldTravel(region ? effectiveScroller(region) : pageScroller)
    : null;
  const near = travel ? shifted(bounds, -travel.x, -travel.y) : bounds;
  const box = region ? effectiveScroller(region) : pageScroller;
  for (const [block, rect, runs] of renderedBlocks(box, inside, band ?? near)) {
    if (region ? !under(block, region.body) : effectiveScroller(block) !== pageScroller)
      continue;
    const clips = new Map();
    const onScreen = runs.filter(({ boxes }) =>
      boxes.some((box) => {
        const now = clippedContents(box, block, clips, travel?.outer);
        const seen = now && travel ? seenGlided(block, now, travel) : now;
        return seen && seen.bottom > bounds.top && seen.top < bounds.bottom;
      }),
    );
    if (onScreen.length) yield [block, rect, onScreen.map(({ segments }) => segments)];
  }
}
// The block the reader reads in a reading region, or with none given in the page outside
// the regions that bound themselves, of those `within` an element where one is given:
// the first on screen across their column (`readerColumn`), the column a captured place
// takes its line from, else the first on screen. So where blocks stand side by side, a
// walk, a let-go and alignment start where the reader's pointer or focus is rather than
// at the top of the first column. A stuck
// box, such as a site header fixed over the page, rides along with every scroll, so
// it is never the block the reader is on (dom/geometry.js, `stuckBox`). Where every block
// on screen reads as stuck, as in an app shell fixed over the window that scrolls its
// own content, the first stands.
/** @param {ReadingRegion | null} [region] @param {Element} [within] */
export function readingBlock(region = null, within = region?.body) {
  const bounds = readingBounds(region);
  const body = region?.body ?? pageDocument();
  const column = bounds ? readerColumn(bounds, body) : null;
  /** @type {Element | null} */
  let first = null;
  /** @type {Element | null} */
  let unstuck = null;
  for (const [block, rect] of blocksOnScreen(region, within ?? null, null, true)) {
    first ??= block;
    if (stuckBox(block, region?.body ?? null)) continue;
    if (column === null || spans(block, rect, column)) return block;
    unstuck ??= block;
  }
  return unstuck ?? first;
}

// The block the user is reading on the page, for a walk's origin, the keyboard
// reference's hand-back and a let-go's landing: in the page region they last acted in
// (`pageReadingRegion`), or, where that region shows none, in the region carrying it, and
// so on out to the page. In a workspace whose panes bound themselves, the page outside
// them holds only its header, so a reading that started there left the pane the user
// was reading for the top of the page. With `bodies`, a region on screen that shows no
// text block (a figure, a widget) answers with its own body, so a landing there keeps
// the user in that region rather than on the document's body, which names the page.
/** @param {{bodies: boolean}} options */
function pageReading({ bodies }) {
  for (
    let region = pageReadingRegion();
    region;
    region = readingRegionFor(region.host.parentElement)
  ) {
    const block = readingBlock(region);
    if (block) return block;
    if (bodies && shownRegionBounds(region)) return region.body;
  }
  return readingBlock() ?? shownAtLine();
}
// What the user is at where the screen shows no text block, as a stretch of blank space
// between two asks or a figure: what stands at the reading line (user-place.js,
// `readingAt`), so a walk steps on from there and a let-go lands there, rather than at
// the top of the page. Where the line meets only the page's own boxes below the last
// block the page draws, as in the room a document keeps below its last line
// (layouts.css), the user has read to the end and is at that last block.
const shownAtLine = () => {
  const at = readingAt(pageDocument());
  const node = at && placeHolder(at);
  if (node && !under(layoutBox(), node)) return node;
  const last = lastDrawn(pageDocument());
  if (last && last.getBoundingClientRect().bottom <= readingLine()) return last;
  return node && node !== document.body ? node : null;
};
// The last block the page draws: the deepest of its last children that draw a box, past
// Leaf's chrome and what the page doesn't show, as a tab not chosen.
/** @param {Element} body */
function lastDrawn(body) {
  /** @type {Element | null} */
  let last = null;
  for (let at = body.lastElementChild; at;) {
    if (!inChrome(at) && at.checkVisibility() && at.getBoundingClientRect().height) {
      last = at;
      at = at.lastElementChild;
    } else at = at.previousElementSibling;
  }
  return last;
}
export const pageReadingBlock = () => pageReading({ bodies: false });

// Whether the reader sees a node where they read `block` (`readingBlock`): in its
// reading region, on screen where the glides under way leave it, and passing each test
// `readingBlock` chose the block by, so outside a stuck box unless the block stands in
// one, as it does where every block on screen rides a fixed shell, and across the
// reader's column wherever the block stands across it. A walk asks it of its stops,
// which need hold no words (records/current-target.js, `stepFrom`). The block's own readings
// are taken once, for every node asked. The block is on screen, so a node a window's
// height or more above or below it is off screen however the glides under way move the
// region holding both. Such a node is judged by its box alone, without measuring what
// clips it, since a walk asks this of every stop the page holds.
/** @param {Element} block @returns {(node: Element) => boolean} */
export function seenWhereRead(block) {
  const region = readingRegionFor(block) ?? null;
  const box = region?.body ?? null;
  const stuck = Boolean(stuckBox(block, box));
  const bounds = readingBounds(region);
  const body = box ?? pageDocument();
  const reader = bounds ? readerColumn(bounds, body) : null;
  const read = shownBox(block);
  const column = reader !== null && spans(block, read, reader) ? reader : null;
  /** @param {DOMRect} shown */
  const afar = (shown) =>
    (shown.width > 0 || shown.height > 0) &&
    (shown.bottom <= read.top - innerHeight || shown.top >= read.bottom + innerHeight);
  return (node) => {
    if (readingRegionFor(node)?.id !== region?.id) return false;
    const shown = shownBox(node);
    return (
      !afar(shown) &&
      seenLanded(node) &&
      (stuck || !stuckBox(node, box)) &&
      (column === null || spans(node, shown, column))
    );
  };
}

// The sections whose words or pictures the user sees, by id in page order: the
// addressable element around each text block and each drawing on screen, on the page
// and in every reading region it shows. A comment on the page as a whole records them
// (events.md, `viewing`), so on a page that shows one section at a time, "this one"
// still says which, even of a slide that is only a chart. An id a script or a shadow
// tree repeats is listed once, since the record refuses a repeated id.
export function sectionsInView() {
  /** @type {Set<Element>} */
  const sections = new Set();
  /** @param {Element} node */
  const add = (node) => {
    const section = closestAcross(node, ADDRESSABLE);
    if (section) sections.add(section);
  };
  for (const region of [null, ...unconcealedReadingRegions()]) {
    for (const [block] of blocksOnScreen(region)) add(block);
    const bounds = readingBounds(region);
    const body = region?.body ?? pageDocument();
    if (!bounds) continue;
    const clips = new Map();
    for (const drawing of body.querySelectorAll(DRAWING)) {
      if (!region && effectiveScroller(drawing) !== pageScroller) continue;
      const seen = drawing.checkVisibility() && seenRect(drawing, clips);
      if (seen && seen.bottom > bounds.top && seen.top < bounds.bottom) add(drawing);
    }
  }
  return [...new Set([...sections].sort(renderedOrder).map(({ id }) => id))];
}

// A let-go lands beside what it let go of while the user sees it where the glides under
// way leave it: its first block on screen, or, for a node inside a block, that block.
// Only failing that is it what they are reading, read where the glides leave them too,
// so Tab pressed as `g g` carries a control away carries on from the page's top.
/** @param {Element | null} [from] */
export function landingPlace(from = null) {
  if (from && from !== document.body && !inChrome(from)) {
    const own = blockIndex().holdsBlocks.has(from) ? from : blockAt(from);
    const region = readingRegionFor(from) ?? null;
    const shown = own && blocksOnScreen(region, own, null, true).next().value?.[0];
    if (shown) return shown;
    // A widget holding no text block, such as an ask's options, is its own landing.
    if (!own && seenAhead(from)) return from;
  }
  return pageReading({ bodies: true });
}

// Where across the box the reader works: their pointer, where it last named their place
// over what they see of the box, else the focus they stand on in it, else null, which
// leaves every column to count.
/** @param {Box} bounds @param {Element} body */
function readerColumn(bounds, body) {
  if (recentPlaceInput() === "pointer") {
    const { x, y } = pointerAt();
    return x >= bounds.left &&
      x <= bounds.right &&
      y >= bounds.top &&
      y <= bounds.bottom
      ? x
      : null;
  }
  const at = focusPlace();
  if (!at || !under(at, body)) return null;
  const rect = shownBox(at);
  return (rect.left + rect.right) / 2;
}
// Whether a block stands across `column`: its own box where it draws one, else the box
// its words make.
/** @param {Element} block @param {Box} rect @param {number} column */
const spans = (block, rect, column) => {
  const own = block.getBoundingClientRect();
  const across = own.width ? own : rect;
  return column >= across.left && column <= across.right;
};

// The run's segments from the first character of its first line whose middle stands at
// or below `edge`; null where the whole run stands above the edge. A run's lines follow one another down the page, so that character is
// found by halving. A heading is read `whole`: any of it below the edge names it from
// its first word, since a heading identifies the place as a whole, and a coordinate
// that hides its opening words is no heading landmark.
/** @param {Segment[]} run @param {number} edge @param {Range} range @param {boolean} whole */
function lineAt(run, edge, range, whole) {
  /** @param {Text} node @param {number} start @param {number} end */
  const boxes = (node, start, end) => {
    range.setStart(node, start);
    range.setEnd(node, end);
    return [...range.getClientRects()].filter((rect) => rect.width && rect.height);
  };
  /** @param {DOMRect | undefined} rect */
  const reaches = (rect) =>
    rect !== undefined && (whole ? rect.bottom : (rect.top + rect.bottom) / 2) >= edge;
  for (const [at, segment] of run.entries()) {
    const { node, start, end } = segment;
    if (!reaches(boxes(node, start, end).at(-1))) continue;
    if (whole) return run;
    let low = start;
    let high = end - 1;
    while (low < high) {
      const middle = (low + high) >> 1;
      if (reaches(boxes(node, middle, end)[0])) high = middle;
      else low = middle + 1;
    }
    // Half a surrogate pair is no character of its own.
    const unit = node.data.charCodeAt(low);
    if (unit >= 0xdc00 && unit <= 0xdfff && low > start) low -= 1;
    return [{ ...segment, start: low }, ...run.slice(at + 1)];
  }
  return null;
}
// A line's words as a comment's capture quotes a passage: at most LANDMARK_CAP
// characters from its first, with the context that names this occurrence among the
// page's words, and the range they span. Null where no context can.
/** @param {Segment[]} segments */
function lineAnchor(segments) {
  const { text, units } = readingFrom(segments);
  if (!text) return null;
  const from = units[0]?.start;
  const to = units[Math.min(units.length, LANDMARK_CAP) - 1]?.end;
  if (!from || !to) return null;
  /** @type {Segment[]} */
  const quoted = [];
  for (const segment of segments) {
    if (!quoted.length && segment.node !== from.node) continue;
    const start = quoted.length ? segment.start : from.offset;
    const end = segment.node === to.node ? to.offset : segment.end;
    if (end > start) quoted.push({ ...segment, start, end });
    if (segment.node === to.node) break;
  }
  const range = rangeOf(quoted);
  const anchor = anchorForPassage(quoted, range.commonAncestorContainer);
  return anchor?.quote && !anchor.detached
    ? { anchor: { ...anchor, quote: anchor.quote }, range }
    : null;
}
// The box that scrolls `node`'s words on its own, outermost first, between it and `box`,
// the scroller a place is read for: content taller than its own box, under an overflow
// the reader can scroll. A box that only clips, as `overflow: hidden` around floats or
// a decoration hanging past its foot does, moves its words only with the page. Where a
// scrolling box is no reading region of its own, its words move with its scroll as well
// as the page's, so they name no place in `box`. The box itself stands between nothing,
// so its own words, as a bounded region's body draws them, scroll with it alone.
/** @param {Node} node @param {Element} box */
function scrollsAlone(node, box) {
  let alone = null;
  for (
    let at = node === box ? null : renderedParent(node);
    at?.nodeType === 1 && at !== box;
    at = renderedParent(at)
  )
    if (
      at !== document.body &&
      userScrollport(getComputedStyle(at).overflowY) &&
      at.scrollHeight > at.clientHeight
    )
      alone = at;
  return alone;
}
// What the landing edge cuts at `x` when no words stand there, and how far through its
// height the edge cuts it: a drawing, or a box scrolling on its own, whose words say
// nothing about the page's place. Null where the edge stands in words, between blocks,
// in a box that draws nothing, or in another scroller's region. The browser's hit test
// names it: the page's topmost element under that point, past anything Leaf draws over
// the page. A drawing is widened to the largest box around it that holds no text
// block, so a chart is its host rather than a mark it drew, and a picture whose caption
// is a block of its own is the picture. A part of the page's reading holds words wherever
// it stands, shown or not, so a box holding one holds text.
/** @param {Element} body @param {Element} box @param {number} x @param {number} edge */
function drawnAt(body, box, x, edge) {
  const { holding } = blockIndex();
  const holdsText = (/** @type {Element} */ element) => holding.has(element);
  for (const hit of document.elementsFromPoint(x, edge + 1)) {
    if (inChrome(hit) || inUi(hit)) continue;
    if (hit === body || !under(hit, body) || effectiveScroller(hit) !== box)
      return null;
    let found = scrollsAlone(hit, box);
    if (!found) {
      if (passageBlock(hit) || holdsText(hit)) return null;
      let drawing = draws(hit);
      found = hit;
      for (
        let up = upFrom(found);
        up && up !== body && !holdsText(up);
        up = upFrom(up)
      ) {
        found = up;
        drawing ||= draws(up);
      }
      if (!drawing) return null;
    }
    const rect = shownBox(found);
    if (!(rect.height && rect.top <= edge + 1 && rect.bottom > edge)) return null;
    return { box: found, through: Math.max(0, (edge - rect.top) / rect.height) };
  }
  return null;
}
/** @param {ReadingRegion | null} [region] @returns {ReadingPlace | null} */
export function capturePlace(region = null) {
  const box = region ? effectiveScroller(region) : pageScroller;
  // Places are measured from the top of the box's landing band, below whatever covers
  // its top edge (the window's head room), so a region handed from the page to its own body
  // keeps the landmark at the same distance below what the user can see. A box a move
  // left off its aim by its rounding is read as if it stood at the aim (dom/scrolling.js,
  // `aimedTop`).
  const band = landingBand(box);
  if (!band) return null;
  const boxTop = band.top + aimedTop(box) - box.scrollTop;
  /** @param {number} top @param {Element} block @param {number} [blockTop] */
  const landmarkTop = (top, block, blockTop = top) =>
    block.matches(HEADING) ? top + Math.max(0, -blockTop) : top;
  // The raw offset, with the width that wrapped the box's contents and the revision
  // that drew the document when it was read.
  /** @type {ReadingPlace} */
  let view = {
    y: box.scrollTop,
    scroller: scrollerIdentity(box),
    width: box.clientWidth,
    revision: runtime.currentRevision,
    [READ_BOX]: new WeakRef(box),
  };
  if (box.scrollTop === 0) view.start = true;
  // Focus names a place in what it stands over only where it rides with it.
  const at = focusPlace();
  const currentLocation = at && !stuckBox(at) ? at : null;
  const body = region?.body ?? pageDocument();
  const currentLocationBody = readingRegionFor(currentLocation)?.body ?? body;
  const focusedRecord =
    recentPlaceInput() === "focus" &&
    currentLocation &&
    under(currentLocation, body) &&
    !under(currentLocationBody, currentLocation)
      ? {
          node: new WeakRef(currentLocation),
          body: new WeakRef(body),
          region: containingReadingRegionFor(currentLocation)?.id,
          intent: retainUserIntent({ source: currentLocation }),
        }
      : null;
  if (region && followingItsEnd(box))
    return {
      ...view,
      ...(focusedRecord && { [FOCUSED_PLACE]: focusedRecord }),
      end: true,
    };
  const bounds = readingBounds(region);
  const column = bounds && readerColumn(bounds, body);
  // The block whose words name the place, so focus on a container the user reads
  // through, such as a section a fragment landed on, names that passage rather than
  // itself: only focus on what the passage is not inside, a control, is the place.
  let named = null;
  // The first line at or below the edge, read down the blocks on screen in document
  // order. Where blocks stand side by side at that line, as columns do, the one across
  // the reader's column is theirs; a block lower down that alone reaches their column
  // is not. A stuck box rides along with every scroll, so its words say nothing about
  // where in the box the reader is (dom/geometry.js, `stuckBox`).
  const range = document.createRange();
  /** @param {Element} block @param {DOMRect} rect @param {Segment[][]} runs */
  const lineOf = (block, rect, runs) => {
    for (const run of runs) {
      // A run shorter than a quotable line, a nav's label or a list of names, is
      // apparatus beside the reading rather than a place in it.
      if (quoteFrom(run).length < QUOTABLE) continue;
      const segments = lineAt(run, boxTop, range, block.matches(HEADING));
      if (!segments) continue;
      const landmark = lineAnchor(segments);
      if (!landmark) return null;
      const box = [...landmark.range.getClientRects()].find((r) => r.width && r.height);
      return { block, rect, landmark, bottom: box?.bottom ?? -Infinity };
    }
    return null;
  };
  /** @type {{block: Element, rect: DOMRect, section: Element} | null} */
  let sectioned = null;
  /** @type {ReturnType<typeof lineOf>} */
  let line = null;
  for (const [block, rect, runs] of blocksOnScreen(region)) {
    if (stuckBox(block, box) || scrollsAlone(block, box)) continue;
    const section = closestAcross(block, ADDRESSABLE);
    sectioned ??= section && { block, rect, section };
    line = lineOf(block, rect, runs);
    if (line) break;
  }
  if (line && column !== null && !spans(line.block, line.rect, column)) {
    const row = { top: boxTop, bottom: line.bottom };
    for (const [block, rect, runs] of blocksOnScreen(region, null, row)) {
      if (
        block === line.block ||
        stuckBox(block, box) ||
        scrollsAlone(block, box) ||
        !spans(block, rect, column)
      )
        continue;
      const beside = lineOf(block, rect, runs);
      if (beside && beside.landmark.range.getBoundingClientRect().top < line.bottom) {
        line = beside;
        break;
      }
    }
  }
  // The section the first block stands in, kept only until a line supplies its own: a
  // page with nothing quotable on screen still has somewhere to land.
  if (sectioned) {
    const { block, rect, section } = sectioned;
    named = block;
    view = {
      ...view,
      section: section.id,
      sectionTop: landmarkTop(shownBox(section).top - boxTop, block, rect.top - boxTop),
    };
  }
  if (line) {
    const { block, rect, landmark } = line;
    named = block;
    // The complete canonical anchor keeps a projected passage's identity as well as
    // its words. Its section replaces the fallback even when null, so restoration
    // cannot search in an earlier block's unrelated section.
    const section = sectionOf(landmark.anchor);
    view = {
      ...view,
      ...landmark.anchor,
      quoteTop: landmarkTop(landmark.range.getBoundingClientRect().top - boxTop, block),
      ...(landmark.anchor.section
        ? {
            section: landmark.anchor.section,
            sectionTop:
              section &&
              landmarkTop(shownBox(section).top - boxTop, block, rect.top - boxTop),
          }
        : { section: null, sectionTop: null }),
    };
  }
  // What the edge cuts in the reader's column, or in the middle of what the box shows,
  // is what they see there, ahead of the line below it, which stands for it where the
  // node is gone.
  if (bounds) {
    // A pointer resting in the margin beside the box's contents names no column there.
    const across = shownBox(body);
    const left = Math.max(across.left, bounds.left);
    const right = Math.min(across.right, bounds.right);
    const x =
      column !== null && column >= left && column <= right
        ? column
        : (left + right) / 2;
    const drawn = drawnAt(body, box, x, boxTop);
    if (drawn) {
      named = drawn.box;
      view[DRAWN_PLACE] = { node: new WeakRef(drawn.box), through: drawn.through };
    }
  }
  if (focusedRecord && !(named && under(named, currentLocation)))
    view[FOCUSED_PLACE] = focusedRecord;
  return view;
}

// The quote's words where the page draws every one of them, else none.
/** @param {ReadingPlace} view */
const drawnQuote = (view) => {
  const segments = targetSegments(
    view.quote ? resolveAnchor({ ...view, quote: view.quote }) : null,
  );
  return segments.every(({ node }) => drawsText(renderedParent(node))) ? segments : [];
};
// What a place stands on now, found as `restorePlace` finds it: the live focused
// destination, the drawing the edge cut, the passage's drawn words, or the drawn
// section. `node` names it and `top` reads where the point it keeps stands. Null where the place has no landmark the page draws, so
// only its own scroller's offset can take it.
/** @param {ReadingPlace} view */
function landmarkOf(view) {
  const live = focusedPlace(view);
  if (live) return { node: live, top: () => shownBox(live).top };
  const drawn = drawnPlace(view);
  if (drawn) return drawn;
  const segments = drawnQuote(view);
  const [first] = segments;
  if (first)
    return {
      node: first.node,
      top: () => segmentsBox(segments).top,
    };
  const section =
    view.section && targetElement(resolveAnchor({ section: view.section }));
  return section && drawsText(section)
    ? { node: section, top: () => shownBox(section).top }
    : null;
}
/** @param {ReadingPlace} view */
export const placeNode = (view) => landmarkOf(view)?.node ?? null;
// How far below its box's landing edge a place's landmark stands now, or null.
/** @param {ReadingPlace} view @param {ReadingRegion | null} [region] */
export function placeOffset(view, region = null) {
  const landmark = landmarkOf(view);
  const box = region ? effectiveScroller(region) : pageScroller;
  const band = landingBand(box);
  return landmark && band ? landmark.top() - band.top : null;
}

// A restore jumps rather than glides: a page is free to set scroll-behavior: smooth, and
// animating from the replacement's raw position is worse than the jump it replaces.
// Moving to a mark the user asked for is the other case, and says so.
/** @param {ReadingPlace | null | undefined} reading */
export const hasLandmark = (reading) =>
  Boolean(
    focusedPlace(reading) ||
    drawnPlace(reading) ||
    reading?.end ||
    reading?.quote ||
    reading?.section,
  );
/** @param {ReadingPlace} reading @param {Element} scroller */
const sameScroller = (reading, scroller) =>
  reading.scroller !== undefined && reading.scroller === scrollerIdentity(scroller);
// A raw offset names the same content only in the box that read it, at the width it
// read it, in the revision that drew it: a box rewrapped to another width, or showing
// a revision that added or took away content, puts something else there, where the
// browser's own anchoring does better than the old offset. Leaf's interface shows the
// log, which a revision does not redraw, so a box of it that replaced the one that read
// the offset, as a reloaded document's does, has nothing else to keep the reader's place.
/** @param {ReadingPlace} reading @param {Element} scroller */
export const rawOffsetFits = (reading, scroller) =>
  sameScroller(reading, scroller) &&
  reading.width === scroller.clientWidth &&
  (reading.revision === runtime.currentRevision ||
    (inUi(scroller) && reading[READ_BOX]?.deref() !== scroller));
/** @param {Element} scroller */
function scrollerIdentity(scroller) {
  if (scroller === pageScroller) return "$page";
  return readingRegions().find(({ body }) => body === scroller)?.id;
}

/** @param {ReadingPlace | null | undefined} view @param {ReadingRegion | null} [region] @param {UserIntent} [currentIntent] */
export function restorePlace(view, region = null, currentIntent = retainUserIntent()) {
  if (!view || !currentIntent()) return;
  const box = region ? effectiveScroller(region) : pageScroller;
  const body = region?.body ?? pageDocument();
  const destination = focusedPlace(view);
  const currentLocation = destination && under(destination, body) ? destination : null;
  // Within one scroller, live focus is the reading place. Across a handover,
  // first preserve the passage's reading band, then keep that focus reachable.
  if (!currentLocation || !sameScroller(view, box)) {
    if (view.end) {
      scrollToEnd(box);
    } else if (view.start && sameScroller(view, box)) {
      setScroll(box, { top: 0, behavior: "instant" });
    } else {
      const band = landingBand(box);
      if (!band) return;
      const boxTop = band.top;
      // Restoration keeps the reader's disclosures and chosen views: a landmark
      // the user has since concealed supplies no geometry, and nothing reopens
      // it. Explicit navigation reveals a destination before restoring a place.
      const drawn = drawnPlace(view);
      const segments = drawn && under(drawn.node, body) ? [] : drawnQuote(view);
      if (drawn && under(drawn.node, body)) {
        moveScrollerBy(box, drawn.top() - boxTop);
      } else if (segments.length && view.quote) {
        moveScrollerBy(box, segmentsBox(segments).top - boxTop - view.quoteTop);
      } else if (!currentLocation) {
        // An unresolved or concealed passage leaves live focus as the precise
        // destination; section and raw-offset fallbacks belong to readings without one.
        const found = view.section
          ? targetElement(resolveAnchor({ section: view.section }))
          : null;
        const section = found && drawsText(found) ? found : null;
        if (section && view.section) {
          // A section containing the scroller cannot align its contents by its
          // outer rectangle. Keep the old offset only where it still fits.
          if (under(box, section))
            setScroll(box, {
              top: rawOffsetFits(view, box) ? view.y : 0,
              behavior: "instant",
            });
          else
            moveScrollerBy(
              box,
              shownBox(section).top - boxTop - Number(view.sectionTop),
            );
        } else if (rawOffsetFits(view, box))
          setScroll(box, { top: view.y, behavior: "instant" });
      }
    }
  }
  // A restored passage or end can carry its focused control beyond the new
  // viewport. Nearest reveal changes nothing when the destination already fits.
  if (currentLocation)
    scrollIntoView(currentLocation, {
      block: "nearest",
      behavior: "instant",
      kept: true,
    });
  placeKept(box, ...(currentLocation ? scrollersOf(currentLocation) : []));
}
