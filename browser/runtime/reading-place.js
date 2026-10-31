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
 * the landmark. The user chose this on 2026-10-25 over keeping the first line at the
 * edge, which scrolls the title away where a header fixed beside that line drops into
 * the flow above it as the window narrows.
 * `capturePlace` reads one, of the page or of a reading region, and `restorePlace`
 * returns the user to it: the passage is found again by its words, so a place survives
 * what moved the pixels under it — a new revision, a resize, a view that was hidden
 * while its width changed. A focused destination in view (user-place.js,
 * `focusedInView`) is the live place while that gesture still holds focus in this
 * region. Focus on the reading surface itself keeps its passage as the place, and so
 * does focus on a container holding that passage, as a section a fragment landed on. The
 * destination's DOM identity stays local; serialized places and replaced elements use
 * the ordinary passage reading, and the node is held weakly, since a place can outlive
 * the document that drew it. A restore jumps rather than glides. It keeps the reader's
 * current disclosures and views: a landmark they concealed supplies no geometry. It
 * returns the reader to a place they had rather than choosing one, so it says where it
 * left each box it moved (scrolling.js, `placeKept`).
 *
 * Whoever remembers a place owns when to take it and where to keep it: version
 * continuity (version.js) across revisions, reading-region shifts and the subjects a
 * region shows in turn, a root tab set (lf-tabs) for each of its views. History's
 * working-place checkpoints separately own an entry's viewport offset (history.js).
 * `readingBlock` is the first block on screen in one region or the page;
 * `pageReadingBlock` is the block the user is reading, where a walk starts, and
 * `landingPlace` is where a let-go puts them, beside what they let go of where they see it. `openingPassage`
 * gives travel the passage its destination draws first, using the same rendered words
 * as the visible landmarks. It is independent of the viewport, so scrolling through a tall landing
 * does not turn a later passage into the navigation step's original arrival.
 */
import { setScroll } from "./arrivals.js";
import {
  clippedContents,
  landingBand,
  seenRect,
  shownBox,
  shownWindow,
  userScrollport,
  stuckBox,
} from "./geometry.js";
import { skipped } from "./shown-box.js";
import {
  blockAt,
  closestAcross,
  inChrome,
  pageBlocks,
  pageDocument,
  pageText,
  quoteFrom,
  rangeOf,
  readingFrom,
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
} from "./reading-regions.js";
import { followingItsEnd } from "./bounds.js";
import {
  aimedTop,
  moveScrollerBy,
  pageScroller,
  placeKept,
  scrollToEnd,
} from "./scrolling.js";
import { inUi, renderedParent, under, upFrom } from "./shadow.js";
import { runtime } from "./context.js";
import { retainUserIntent } from "./user-intent.js";
import { recentPlaceInput, focused } from "./focus.js";
import { focusedInView } from "./user-place.js";
import { scrollIntoReadingBand } from "./landing-scroll.js";
import { union } from "./rect.js";
import { pointerAt } from "./pointer.js";

// A live focused place belongs to this DOM, not a serialized history record. Its
// symbol keeps that node out of JSON; the ordinary passage reading remains the
// fallback when a replacement or a later gesture has given focus elsewhere. The node
// and its reading surface are held weakly: a place outlives the revision that removes
// them until the reader next records one.
const FOCUSED_PLACE = Symbol("live focused place");
const focusedPlace = (reading) => {
  const place = reading?.[FOCUSED_PLACE];
  const node = place?.node.deref();
  return node?.isConnected &&
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
const drawnPlace = (reading) => {
  const place = reading?.[DRAWN_PLACE];
  const node = place?.node.deref();
  if (!node?.isConnected || !drawsLandmark(node)) return null;
  const top = () => {
    const rect = shownBox(node);
    return rect.top + place.through * rect.height;
  };
  return { node, top };
};
// What draws something to see without words: a replaced element, or a widget, which is
// a custom element. Empty boxes and spacers draw nothing, so no place stands on them.
const DRAWING = "img, svg, canvas, video, picture, iframe, object, embed";
const draws = (element) => element.matches(DRAWING) || element.localName.includes("-");
const LANDMARK_CAP = 160;
// The shortest run of words that names a reading place (`capturePlace`).
const QUOTABLE = 24;
const HEADING = "h1, h2, h3, h4, h5, h6";

// The page's own text blocks the user can see, in document order, with the rect of each
// one's first line — one reading of what is in front of them, for the two questions that
// ask it: which passage the user returns to (below), and where a walk over what is
// on the user starts when they have pointed at nothing.
// A block's landmark is the top of its first line (a range), not its border box; restore
// measures the matched text the same way, so the line box's leading cancels out.
// The blocks are the page reading's (`pageBlocks`) rather than a query of the light DOM: a
// declared shadow root renders authored words at its host's place in reading order, and
// those words are pointable and resolvable through the same reading, so version
// continuity must be able to choose the same blocks as landmarks.
export const textBlocks = (root = pageDocument()) =>
  pageBlocks().filter((block) => under(block, root));

// Source blocks include concealed words, since an anchor can reveal them. A reading
// place instead requires words the browser draws. Ask the text's own parent, rather
// than its block: display: contents still draws text, and a child can restore visibility
// inside a concealed block. Skipped subtrees are left alone before asking for any boxes.
const drawsLandmark = (parent) => {
  if (!parent || skipped(parent) || getComputedStyle(parent).visibility !== "visible")
    return false;
  // Text in display: contents has no parent box to ask. Its first boxed ancestor
  // supplies the browser's opacity/display reading; visibility belongs to the text
  // parent, since its children may override that ancestor.
  let box = parent;
  while (box && getComputedStyle(box).display === "contents") box = renderedParent(box);
  return Boolean(box?.checkVisibility({ opacityProperty: true }));
};
const blockRuns = new WeakMap();
// The browser can bound a block's text in one Range read, including positioned
// children outside its own box. A Range cannot cross shadow roots or read skipped
// contents without forcing their layout; those blocks keep the per-segment reading.
const textEnvelope = (block, segments, range) => {
  if (
    !segments.every(({ node }) => block.contains(node)) ||
    [...block.querySelectorAll("*")].some(skipped)
  )
    return null;
  range.selectNodeContents(block);
  return range.getBoundingClientRect();
};
// Each block's drawn words, with the union of their boxes. Outside the reading band,
// the native text envelope can rule a block out before individual tokens are measured.
function* renderedBlocks(blocks, within = null) {
  const reading = pageText();
  if (!blockRuns.has(reading)) {
    const groups = [];
    for (const segment of reading.segments) {
      let group = groups.at(-1);
      if (!group || group.block !== segment.block)
        groups.push((group = { block: segment.block, segments: [] }));
      group.segments.push(segment);
    }
    blockRuns.set(reading, groups);
  }
  // A datum can split its parent's words. Keep the parent's later continuation after
  // that datum, rather than collecting both sides under the parent's first occurrence.
  const allowed = new Set(blocks);
  const drawn = new Map();
  const range = document.createRange();
  for (const { block, segments } of blockRuns.get(reading)) {
    if (!allowed.has(block)) continue;
    // Skipped content stays unmeasured: asking for a box inside it lays it out.
    if (inChrome(block) || skipped(block)) continue;
    if (within) {
      const own = block.getBoundingClientRect();
      if (own.height && (own.bottom <= within.top || own.top >= within.bottom)) {
        const envelope = textEnvelope(block, segments, range);
        if (
          envelope &&
          (envelope.bottom <= within.top || envelope.top >= within.bottom)
        )
          continue;
      }
    }
    const boxes = [],
      runs = [];
    let run = null;
    for (const segment of segments) {
      const { node, start, end } = segment;
      const parent = renderedParent(node);
      if (!drawn.has(parent)) drawn.set(parent, drawsLandmark(parent));
      if (!drawn.get(parent)) {
        run = null;
        continue;
      }
      range.setStart(node, start);
      range.setEnd(node, end);
      const rects = [...range.getClientRects()].filter(
        (rect) => rect.width && rect.height,
      );
      if (!rects.length) {
        run = null;
        continue;
      }
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

// The passage grain is shared by reading input and travel's produced landing. A
// containing destination opens at its first rendered passage, independently of the
// viewport: scrolling through a tall destination cannot redefine where it landed.
export function passageBlock(node) {
  const blocks = pageBlocks();
  for (let at = node; at; at = upFrom(at)) if (blocks.includes(at)) return at;
  return null;
}
export function openingPassage(where) {
  if (where instanceof Range) return passageBlock(where.startContainer);
  if (!where) return null;
  const blocks = pageBlocks().filter((block) => under(block, where));
  return renderedBlocks(blocks).next().value?.[0] ?? null;
}

// What the reader can see of a region, or with none given of the page: null where they
// see none of it. A flowing region is read through the part of the window the page
// shows: a line hidden under the chrome is not where the user is.
function readingBounds(region) {
  const shown = region ? shownRegionBounds(region) : shownWindow();
  if (!shown) return null;
  return region && effectiveScroller(region) === pageScroller
    ? shownWindow({ within: shown })
    : shown;
}

// With `band`, only blocks whose own box reaches that band are measured.
export function* blocksOnScreen(region = null, blocks = textBlocks(), band = null) {
  const bounds = readingBounds(region);
  if (!bounds) return;
  for (const [block, rect, runs] of renderedBlocks(blocks, band ?? bounds)) {
    if (region ? !under(block, region.body) : effectiveScroller(block) !== pageScroller)
      continue;
    const clips = new Map();
    const onScreen = runs.filter(({ boxes }) =>
      boxes.some((box) => {
        const seen = clippedContents(box, block, clips);
        return seen && seen.bottom > bounds.top && seen.top < bounds.bottom;
      }),
    );
    if (onScreen.length) yield [block, rect, onScreen.map(({ segments }) => segments)];
  }
}
// The first visible block in a reading region, or with none given in the page outside
// the regions that bound themselves, for alignment when nothing is selected.
export const readingBlock = (region = null) =>
  blocksOnScreen(region, textBlocks(region?.body)).next().value?.[0] ?? null;

// The block the user is reading on the page, for a walk's origin, the keyboard
// reference's hand-back and a let-go's landing: in the page region they last acted in
// (`pageReadingRegion`), or, where that region shows none, in the region carrying it, and
// so on out to the page. In a workspace whose panes bound themselves, the page outside
// them holds only its header, so a reading that started there left the pane the user
// was reading for the top of the page. With `bodies`, a region on screen that shows no
// text block (a figure, a widget) answers with its own body, so a landing there keeps
// the user in that region rather than on the document's body, which names the page.
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
  return readingBlock();
}
export const pageReadingBlock = () => pageReading({ bodies: false });
// A let-go lands beside what it let go of while the user sees it: its first block on
// screen, or, for a node inside a block, that block. Only failing that is it what they
// are reading.
export function landingPlace(from = null) {
  if (from && from !== document.body && !inChrome(from)) {
    const blocks = textBlocks(from);
    const own = blocks.length ? blocks : [blockAt(from)].filter(Boolean);
    const shown = blocksOnScreen(readingRegionFor(from), own).next().value?.[0];
    if (shown) return shown;
    // A widget holding no text block, such as an ask's options, is its own landing.
    if (!own.length && seenRect(from, new Map())) return from;
  }
  return pageReading({ bodies: true });
}

// Where across the box the reader works: their pointer, where it last named their place
// over what they see of the box, else the focus they stand on in it, else null, which
// leaves every column to count.
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
  const at = focusedInView();
  if (!at || !under(at, body)) return null;
  const rect = shownBox(at);
  return (rect.left + rect.right) / 2;
}
// Whether a block stands across `column`: its own box where it draws one, else the box
// its words make.
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
function lineAt(run, edge, range, whole) {
  const boxes = (node, start, end) => {
    range.setStart(node, start);
    range.setEnd(node, end);
    return [...range.getClientRects()].filter((rect) => rect.width && rect.height);
  };
  const reaches = (rect) =>
    Boolean(rect) && (whole ? rect.bottom : (rect.top + rect.bottom) / 2) >= edge;
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
function lineAnchor(segments) {
  const { text, units } = readingFrom(segments);
  if (!text) return null;
  const from = units[0].start;
  const to = units[Math.min(units.length, LANDMARK_CAP) - 1].end;
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
  return anchor.quote && !anchor.detached ? { anchor, range } : null;
}
// The box that scrolls `node`'s words on its own, outermost first, between it and `box`,
// the scroller a place is read for: content taller than its own box, under an overflow
// the reader can scroll. A box that only clips, as `overflow: hidden` around floats or
// a decoration hanging past its foot does, moves its words only with the page. Where a
// scrolling box is no reading region of its own, its words move with its scroll as well
// as the page's, so they name no place in `box`.
function scrollsAlone(node, box) {
  let alone = null;
  for (
    let at = renderedParent(node);
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
// is a block of its own is the picture.
function drawnAt(body, box, x, edge, blocks) {
  const holdsText = (element) => blocks.some((block) => under(block, element));
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
export function capturePlace(region = null, blocks = textBlocks()) {
  const box = region ? effectiveScroller(region) : pageScroller;
  // Places are measured from the top of the box's landing band, below whatever covers
  // its top edge (the window's head room), so a region handed from the page to its own body
  // keeps the landmark at the same distance below what the user can see. A box a move
  // left off its aim by its rounding is read as if it stood at the aim (scrolling.js,
  // `aimedTop`).
  const boxTop = landingBand(box).top + aimedTop(box) - box.scrollTop;
  const landmarkTop = (top, block, blockTop = top) =>
    block?.matches(HEADING) ? top + Math.max(0, -blockTop) : top;
  // The raw offset, with the width that wrapped the box's contents and the revision
  // that drew the document when it was read.
  const view = {
    y: box.scrollTop,
    scroller: scrollerIdentity(box),
    width: box.clientWidth,
    revision: runtime.currentRevision,
    [READ_BOX]: new WeakRef(box),
  };
  if (box.scrollTop === 0) view.start = true;
  const currentLocation = focusedInView();
  const body = region?.body ?? pageDocument();
  const currentLocationBody = readingRegionFor(currentLocation)?.body ?? body;
  const focusPlace = () => ({
    node: new WeakRef(currentLocation),
    body: new WeakRef(body),
    region: containingReadingRegionFor(currentLocation)?.id,
    intent: retainUserIntent({ source: currentLocation }),
  });
  const hasFocusedLandmark =
    recentPlaceInput() === "focus" &&
    currentLocation &&
    under(currentLocation, body) &&
    // Focus on the reading surface itself names its contents, not a landmark.
    !under(currentLocationBody, currentLocation);
  if (region && followingItsEnd(box))
    return {
      ...view,
      ...(hasFocusedLandmark && { [FOCUSED_PLACE]: focusPlace() }),
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
  // where in the box the reader is (geometry.js, `stuckBox`).
  const range = document.createRange();
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
  let sectioned = null;
  let line = null;
  for (const [block, rect, runs] of blocksOnScreen(region, blocks)) {
    if (stuckBox(block, box) || scrollsAlone(block, box)) continue;
    const section = closestAcross(block, ADDRESSABLE);
    sectioned ??= section && { block, rect, section };
    line = lineOf(block, rect, runs);
    if (line) break;
  }
  if (line && column !== null && !spans(line.block, line.rect, column)) {
    const row = { top: boxTop, bottom: line.bottom };
    for (const [block, rect, runs] of blocksOnScreen(region, blocks, row)) {
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
    view.section = section.id;
    view.sectionTop = landmarkTop(
      shownBox(section).top - boxTop,
      block,
      rect.top - boxTop,
    );
  }
  if (line) {
    const { block, rect, landmark } = line;
    named = block;
    // The complete canonical anchor keeps a projected passage's identity as well as
    // its words. Its section replaces the fallback even when null, so restoration
    // cannot search in an earlier block's unrelated section.
    Object.assign(view, landmark.anchor);
    const section = sectionOf(view);
    view.sectionTop =
      section && landmarkTop(shownBox(section).top - boxTop, block, rect.top - boxTop);
    // A heading partly under the edge is restored whole: normalize here, once, rather
    // than teaching every restore path to repair it after document replacement.
    view.quoteTop = landmarkTop(
      landmark.range.getBoundingClientRect().top - boxTop,
      block,
    );
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
    const drawn = drawnAt(body, box, x, boxTop, blocks);
    if (drawn) {
      named = drawn.box;
      view[DRAWN_PLACE] = { node: new WeakRef(drawn.box), through: drawn.through };
    }
  }
  if (hasFocusedLandmark && !(named && under(named, currentLocation)))
    view[FOCUSED_PLACE] = focusPlace();
  return view;
}

// The quote's words where the page draws every one of them, else none.
const drawnQuote = (view) => {
  const segments = targetSegments(view.quote && resolveAnchor(view));
  return segments.every(({ node }) => drawsLandmark(renderedParent(node)))
    ? segments
    : [];
};
// What a place stands on now, found as `restorePlace` finds it: the live focused
// destination, the drawing the edge cut, the passage's drawn words, or the drawn
// section. `node` names it and `top` reads where the point it keeps stands. Null where the place has no landmark the page draws, so
// only its own scroller's offset can take it.
function landmarkOf(view) {
  const live = focusedPlace(view);
  if (live) return { node: live, top: () => shownBox(live).top };
  const drawn = drawnPlace(view);
  if (drawn) return drawn;
  const segments = drawnQuote(view);
  if (segments.length)
    return {
      node: segments[0].node,
      top: () => rangeOf(segments).getBoundingClientRect().top,
    };
  const section =
    view.section && targetElement(resolveAnchor({ section: view.section }));
  return section && drawsLandmark(section)
    ? { node: section, top: () => shownBox(section).top }
    : null;
}
export const placeNode = (view) => landmarkOf(view)?.node ?? null;
// How far below its box's landing edge a place's landmark stands now, or null.
export function placeOffset(view, region = null) {
  const landmark = landmarkOf(view);
  const box = region ? effectiveScroller(region) : pageScroller;
  return landmark ? landmark.top() - landingBand(box).top : null;
}

// A restore jumps rather than glides: a page is free to set scroll-behavior: smooth, and
// animating from the replacement's raw position is worse than the jump it replaces.
// Moving to a mark the user asked for is the other case, and says so.
export const hasLandmark = (reading) =>
  Boolean(
    focusedPlace(reading) ||
    drawnPlace(reading) ||
    reading?.end ||
    reading?.quote ||
    reading?.section,
  );
const sameScroller = (reading, scroller) =>
  reading.scroller !== undefined && reading.scroller === scrollerIdentity(scroller);
// A raw offset names the same content only in the box that read it, at the width it
// read it, in the revision that drew it: a box rewrapped to another width, or showing
// a revision that added or took away content, puts something else there, where the
// browser's own anchoring does better than the old offset. Leaf's interface shows the
// log, which a revision does not redraw, so a box of it that replaced the one that read
// the offset, as a reloaded document's does, has nothing else to keep the reader's place.
export const rawOffsetFits = (reading, scroller) =>
  sameScroller(reading, scroller) &&
  reading.width === scroller.clientWidth &&
  (reading.revision === runtime.currentRevision ||
    (inUi(scroller) && reading[READ_BOX]?.deref() !== scroller));
function scrollerIdentity(scroller) {
  if (scroller === pageScroller) return "$page";
  return readingRegions().find(({ body }) => body === scroller)?.id;
}

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
      const boxTop = landingBand(box).top;
      // Restoration keeps the reader's disclosures and chosen views: a landmark
      // the user has since concealed supplies no geometry, and nothing reopens
      // it. Explicit navigation reveals a destination before restoring a place.
      const drawn = drawnPlace(view);
      const segments = drawn && under(drawn.node, body) ? [] : drawnQuote(view);
      if (drawn && under(drawn.node, body)) {
        moveScrollerBy(box, drawn.top() - boxTop);
      } else if (segments.length) {
        moveScrollerBy(
          box,
          rangeOf(segments).getBoundingClientRect().top - boxTop - view.quoteTop,
        );
      } else if (!currentLocation) {
        // An unresolved or concealed passage leaves live focus as the precise
        // destination; section and raw-offset fallbacks belong to readings without one.
        const found = targetElement(resolveAnchor({ section: view.section }));
        const section = found && drawsLandmark(found) ? found : null;
        if (section) {
          // A section containing the scroller cannot align its contents by its
          // outer rectangle. Keep the old offset only where it still fits.
          if (under(box, section))
            setScroll(box, {
              top: rawOffsetFits(view, box) ? view.y : 0,
              behavior: "instant",
            });
          else moveScrollerBy(box, shownBox(section).top - boxTop - view.sectionTop);
        } else if (rawOffsetFits(view, box))
          setScroll(box, { top: view.y, behavior: "instant" });
      }
    }
  }
  // A restored passage or end can carry its focused control beyond the new
  // viewport. Nearest reveal changes nothing when the destination already fits.
  if (currentLocation)
    scrollIntoReadingBand(currentLocation, currentLocation, "nearest", "instant");
  placeKept(box, ...(currentLocation ? scrollersOf(currentLocation) : []));
}
