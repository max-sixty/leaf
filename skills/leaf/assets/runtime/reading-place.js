/* The user's place in a scroller, written down as a landmark rather than an offset.
 *
 * A place names the first quotable block the user can see in a scroller, with that
 * block's distance below the scroller's landing edge; failing a quotable block, the
 * section it stands in; failing that, the raw offset, which only the same scroller can
 * take back. A bounded block following its newest entry has its end as its place
 * (`bounds.js`, `followingItsEnd`), however many entries have arrived since.
 * `capturePlace` reads one, of the page or of a reading region, and `restorePlace`
 * returns the user to it: the passage is found again by its words, so a place survives
 * what moved the pixels under it — a new revision, a resize, a view that was hidden
 * while its width changed. A visible focused destination is the live place while that
 * gesture still holds focus in this region. Focus on the reading surface itself keeps
 * its passage as the place. The destination's DOM identity stays local;
 * serialized places and replaced elements use the ordinary passage reading. A restore
 * jumps rather than glides.
 *
 * Whoever remembers a place owns when to take it and where to keep it: version
 * continuity (version.js) across revisions and reading-region shifts, a root tab set
 * (lf-tabs) for each of its views. The browser keeps a history entry's own offset
 * (history.js). `readingBlock` is the first block on screen in one region or the page;
 * `pageReadingBlock` is the block the user is reading, where a walk starts, and
 * `landingPlace` is where a let-go puts them. `openingPassage` gives travel the
 * passage its destination draws first, using the same rendered words as the visible
 * landmarks. It is independent of the viewport, so scrolling through a tall landing
 * does not turn a later passage into the trip's original arrival.
 */
import {
  clippedContents,
  landingBand,
  seenRect,
  shownBox,
  shownWindow,
  skipped,
} from "./geometry.js";
import {
  closestAcross,
  cut,
  inChrome,
  pageBlocks,
  pageText,
  quoteFrom,
  rangeOf,
} from "./passages.js";
import { ADDRESSABLE, resolveAnchor } from "./anchor-resolution.js";
import { targetElement, targetSegments } from "./resolved-target.js";
import {
  containingReadingRegionFor,
  effectiveScroller,
  readingPosture,
  readingRegionFor,
  readingRegions,
  shownRegionBounds,
  pageReadingRegion,
} from "./reading-regions.js";
import { followingItsEnd } from "./bounds.js";
import { moveScrollerBy, pageScroller, scrollToEnd } from "./scrolling.js";
import { renderedParent, under, upFrom } from "./shadow.js";
import { recentPlaceInput, retainUserIntent } from "./user-intent.js";
import { reveal } from "./widget-elements.js";
import { focused } from "./keyboard/scopes.js";
import { scrollIntoReadingBand } from "./landing-scroll.js";
import { union } from "./rect.js";

// A live focused place belongs to this DOM, not a serialized history record. Its
// symbol keeps that node out of JSON; the ordinary passage reading remains the
// fallback when a replacement or a later gesture has given focus elsewhere.
const FOCUSED_PLACE = Symbol("live focused place");
const focusedPlace = (reading) => {
  const place = reading?.[FOCUSED_PLACE];
  return place?.node.isConnected &&
    place.node === focused() &&
    under(place.node, place.body) &&
    containingReadingRegionFor(place.node)?.id === place.region &&
    place.intent()
    ? place.node
    : null;
};
const LANDMARK_CAP = 160;
const HEADING = "h1, h2, h3, h4, h5, h6";

// The page's own text blocks the user can see, in document order, with the rect of each
// one's first line — one reading of what is in front of them, for the two questions that
// ask it: which passage the user returns to (below), and where a walk over the page's
// Asks starts when they have pointed at nothing.
// A block's landmark is the top of its first line (a range), not its border box; restore
// measures the matched text the same way, so the line box's leading cancels out.
// The blocks are the page reading's (`pageBlocks`) rather than a query of the light DOM: a
// declared shadow root renders authored words at its host's place in reading order, and
// those words are pointable and resolvable through the same reading, so version
// continuity must be able to choose the same blocks as landmarks.
export const textBlocks = (root = document.querySelector("body > main")) =>
  pageBlocks().filter((block) => under(block, root));

// Source blocks include concealed words, since an anchor can reveal them. A reading
// place instead requires words the browser draws. Ask the text's own parent, rather
// than its block: display: contents still draws text, and a child can restore visibility
// inside a concealed block. Skipped subtrees are left alone before asking for any boxes.
const blockWords = new WeakMap();
function* renderedBlocks(blocks) {
  const reading = pageText();
  if (!blockWords.has(reading)) {
    const words = new Map();
    for (const segment of reading.segments) {
      if (!words.has(segment.block)) words.set(segment.block, []);
      words.get(segment.block).push(segment);
    }
    blockWords.set(reading, words);
  }
  const words = blockWords.get(reading);
  const drawn = new Map();
  const range = document.createRange();
  for (const block of blocks) {
    if (inChrome(block) || skipped(block)) continue;
    const boxes = [],
      runs = [];
    let run = null;
    for (const segment of words.get(block)) {
      const { node, start, end } = segment;
      const parent = renderedParent(node);
      if (!drawn.has(parent)) {
        let visible = false;
        if (!skipped(parent) && getComputedStyle(parent).visibility === "visible") {
          // Text in display: contents has no parent box to ask. Its first boxed
          // ancestor supplies the browser's opacity/display reading; visibility
          // belongs to the text parent, since its children may override that ancestor.
          let box = parent;
          while (box && getComputedStyle(box).display === "contents")
            box = renderedParent(box);
          visible = Boolean(box?.checkVisibility({ opacityProperty: true }));
        }
        drawn.set(parent, visible);
      }
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

export function* blocksOnScreen(region = null, blocks = textBlocks()) {
  const shown = region ? shownRegionBounds(region) : shownWindow();
  if (!shown) return;
  // A flowing region is read through the part of the window the page shows: a line
  // hidden under the banner is not where the user is.
  const bounds =
    region && effectiveScroller(region) === pageScroller
      ? shownWindow({ within: shown })
      : shown;
  for (const [block, rect, runs] of renderedBlocks(blocks)) {
    if (
      region
        ? !under(block, region.body)
        : readingPosture(readingRegionFor(block)) === "bounded"
    )
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
export const landingPlace = () => pageReading({ bodies: true });

// The quote and the section it's searched in come from the same block, or the search is
// filtered to a section the text isn't in and can only ever fail — restore then falls back
// to the section, which doesn't absorb content added above the user inside it.
export function capturePlace(region = null, blocks = textBlocks()) {
  const box = region ? effectiveScroller(region) : pageScroller;
  // Places are measured from the top of the box's landing band, below whatever covers
  // its top edge (the page's banner), so a region handed from the page to its own body
  // keeps the landmark at the same distance below what the user can see.
  const boxTop = landingBand(box).top;
  const landmarkTop = (top, block, blockTop = top) =>
    block?.matches(HEADING) ? top + Math.max(0, -blockTop) : top;
  const view = { y: box.scrollTop, scroller: scrollerIdentity(box) };
  const standing = focused();
  const body = region?.body ?? document.querySelector("body > main");
  const standingBody = readingRegionFor(standing)?.body ?? body;
  if (
    recentPlaceInput() === "focus" &&
    standing &&
    under(standing, body) &&
    // Focus on the reading surface itself names its contents, not a landmark.
    !under(standingBody, standing) &&
    seenRect(standing, new Map())
  )
    view[FOCUSED_PLACE] = {
      node: standing,
      body,
      region: containingReadingRegionFor(standing)?.id,
      intent: retainUserIntent({ source: standing }),
    };
  if (region && followingItsEnd(box)) return { ...view, end: true };
  for (const [block, rect, runs] of blocksOnScreen(region, blocks)) {
    const section = closestAcross(block, ADDRESSABLE);
    if (!view.section && section) {
      // The first on-screen block's section, kept only until a quotable block supplies
      // its own: a page with nothing quotable on screen still has somewhere to land.
      view.section = section.id;
      view.sectionTop = landmarkTop(
        shownBox(section).top - boxTop,
        block,
        rect.top - boxTop,
      );
    }
    // Written down the way a comment's quote is, so the search that re-finds it is
    // looking for a string of the same kind.
    // Concealed words split a block's drawn runs. A landmark uses one uninterrupted
    // run so the ordinary quote resolver can find it in the complete source reading.
    const run = runs.find((segments) => quoteFrom(segments).length >= 24);
    const text = run && cut(quoteFrom(run), 0, LANDMARK_CAP);
    // A short line ("Risks") would match anywhere; keep scanning for a quotable block.
    if (text) {
      // Unconditionally, so a quotable block under no section clears the earlier one
      // rather than sending the search into a subtree its text isn't in.
      view.section = section?.id;
      view.sectionTop =
        section &&
        landmarkTop(shownBox(section).top - boxTop, block, rect.top - boxTop);
      view.quote = text;
      // A partially covered paragraph is still a reading place: its visible lines
      // should stay where the user left them. A heading identifies the place as a
      // whole, so a coordinate that hides its opening words is not a valid heading
      // landmark. Normalize both quote and fallback section state here, once, rather
      // than teaching every restore path to repair it after document replacement.
      view.quoteTop = landmarkTop(
        rangeOf(run).getBoundingClientRect().top - boxTop,
        block,
      );
      break;
    }
  }
  return view;
}

// A restore jumps rather than glides: a page is free to set scroll-behavior: smooth, and
// animating from the replacement's raw position is worse than the jump it replaces.
// Moving to a mark the user asked for is the other case, and says so.
export const hasLandmark = (reading) =>
  Boolean(focusedPlace(reading) || reading?.end || reading?.quote || reading?.section);
export const rawOffsetFits = (reading, scroller) =>
  reading.scroller !== undefined && reading.scroller === scrollerIdentity(scroller);
function scrollerIdentity(scroller) {
  if (scroller === pageScroller) return "$page";
  return readingRegions().find(({ body }) => body === scroller)?.id;
}

export function restorePlace(view, region = null, currentIntent = retainUserIntent()) {
  if (!view || !currentIntent()) return;
  const box = region ? effectiveScroller(region) : pageScroller;
  const standing = focusedPlace(view);
  // A focus that remains visible after its region joins a different scroller can
  // still be far from the passage's old reading band. Restore the landmark there;
  // a focus with no saved landmark remains the only place to restore.
  if (
    standing &&
    (rawOffsetFits(view, box) || (!view.quote && !view.section && !view.end)) &&
    under(standing, region?.body ?? document.querySelector("body > main"))
  ) {
    scrollIntoReadingBand(standing, standing, "nearest", "instant");
    return;
  }
  if (view.end) {
    scrollToEnd(box);
    return;
  }
  const boxTop = landingBand(box).top;
  const text = pageText();
  const found = view.quote && resolveAnchor(view, text);
  const segments = targetSegments(found);
  if (segments.length) {
    reveal(segments[0].node.parentElement, currentIntent); // the passage may sit behind a tab
    moveScrollerBy(
      box,
      rangeOf(segments).getBoundingClientRect().top - boxTop - view.quoteTop,
    );
    return;
  }
  // Repeated passage words may have no unique anchor. In that case the live
  // focused control is still a precise place in this document; a section's
  // opening is only a fallback for a reading with no such destination.
  if (
    standing &&
    under(standing, region?.body ?? document.querySelector("body > main"))
  ) {
    scrollIntoReadingBand(standing, standing, "nearest", "instant");
    return;
  }
  const section = targetElement(resolveAnchor({ section: view.section }, text));
  if (section) {
    reveal(section, currentIntent);
    // A section containing this scroller cannot move when its contents scroll.
    // Its outer rectangle therefore supplies no alignment inside the body: keep
    // the old offset only in the same box, otherwise arrive at the section's opening.
    if (under(box, section)) {
      box.scrollTo({ top: rawOffsetFits(view, box) ? view.y : 0, behavior: "instant" });
      return;
    }
    // The shown reading on both sides of the subtraction, because the landmark is
    // whatever id stands nearest the block the user was on, and a section that
    // generates no box of its own is one a suggestion wrapping whole sections leaves
    // there. Read raw, both sides come back 0 and the correction is 0 — so the restore
    // that had somewhere to land did nothing, silently, and left the user at the top.
    moveScrollerBy(box, shownBox(section).top - boxTop - view.sectionTop);
  } else if (rawOffsetFits(view, box))
    box.scrollTo({ top: view.y, behavior: "instant" });
}
