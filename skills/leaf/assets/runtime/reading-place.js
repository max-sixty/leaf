/* The user's place in a scroller, written down as a landmark rather than an offset.
 *
 * A place names the first quotable block the user can see in a scroller, with that
 * block's distance below the scroller's landing edge; failing a quotable block, the
 * section it stands in; failing that, the raw offset, which only the same scroller can
 * take back. `capturePlace` reads one, of the page or of a reading region, and
 * `restorePlace` returns the user to it: the passage is found again by its words, so a
 * place survives what moved the pixels under it — a new revision, a resize, a view that
 * was hidden while its width changed. A restore jumps rather than glides.
 *
 * Whoever remembers a place owns when to take it and where to keep it: version
 * continuity (version.js) across revisions and reading-region shifts, a root tab set
 * (lf-tabs) for each of its views. The browser keeps a history entry's own offset
 * (history.js). `readingBlock` is the block the user is on, for the questions that ask
 * where a walk starts.
 */
import { banner } from "./banner.js";
import { clippedContents, landingInsets, shownBox } from "./geometry.js";
import {
  blockAt,
  closestAcross,
  cut,
  inChrome,
  pageText,
  quoteFrom,
  rangeOf,
  textNodesUnder,
} from "./passages.js";
import { resolveAnchor } from "./anchor-resolution.js";
import { targetElement, targetSegments } from "./resolved-target.js";
import {
  effectiveScroller,
  readingPosture,
  readingRegionFor,
  readingRegions,
  shownRegionBounds,
} from "./reading-regions.js";
import { moveScrollerBy, pageScroller } from "./scrolling.js";
import { under } from "./shadow.js";
import { retainUserIntent } from "./user-intent.js";
import { reveal } from "./widget-elements.js";

const LANDMARK_CAP = 160;
const HEADING = "h1, h2, h3, h4, h5, h6";

// The page's own text blocks the user can see, in document order, with the rect of each
// one's first line — one reading of what is in front of them, for the two questions that
// ask it: which passage the user returns to (below), and where a walk over the page's
// Asks starts when they have pointed at nothing.
// A block's landmark is the top of its first line (a range), not its border box; restore
// measures the matched text the same way, so the line box's leading cancels out.
export function textBlocks(root = document.querySelector("body > main")) {
  const seen = new Set();
  // Walk the page's composed text rather than querying only its light DOM. A declared
  // shadow root renders authored words at its host's place in reading order; those
  // words are pointable and resolvable through the shared passage reading, so version
  // continuity must be able to choose the same blocks as landmarks. Each word's block
  // is the one every passage reading uses (`blockAt`).
  return textNodesUnder(root)
    .map(({ node }) => blockAt(node))
    .filter((block) => block && !seen.has(block) && seen.add(block));
}

export function* blocksOnScreen(region = null, blocks = textBlocks()) {
  // Read the painted edge directly. The declared height may contain a safe-area
  // `calc()`, whose serialized value is not a number even though its box is exact.
  const page = { top: banner.getBoundingClientRect().bottom, bottom: innerHeight };
  const shown = region ? shownRegionBounds(region) : page;
  if (!shown) return;
  // A flowing region is read through the page, whose visible band starts below the
  // banner: a line hidden under it is not where the user is.
  const bounds =
    region && effectiveScroller(region) === pageScroller
      ? {
          top: Math.max(shown.top, page.top),
          bottom: Math.min(shown.bottom, page.bottom),
        }
      : shown;
  for (const block of blocks) {
    // [hidden] needs an explicit skip: hidden="until-found" resolves to
    // content-visibility, under which descendants still report real rects —
    // but what's behind an inactive tab isn't what the user is reading.
    if (
      inChrome(block) ||
      closestAcross(block, "[hidden]") ||
      (region && !under(block, region.body)) ||
      (!region &&
        readingRegionFor(block) &&
        readingPosture(readingRegionFor(block)) === "bounded")
    )
      continue;
    const range = document.createRange();
    range.selectNodeContents(block);
    const rect = range.getBoundingClientRect();
    const seen = clippedContents(rect, block, new Map());
    if (seen && seen.bottom > bounds.top && seen.top < bounds.bottom)
      yield [block, rect];
  }
}
// The one block the user is on, which is the first the walk above yields. Two
// things outside ask it — where an Ask walk starts, and where the keyboard
// reference hands a user back to — and they were asking it in two places with the
// same expression written out twice.
export const readingBlock = () => blocksOnScreen().next().value?.[0] ?? null;

// The quote and the section it's searched in come from the same block, or the search is
// filtered to a section the text isn't in and can only ever fail — restore then falls back
// to the section, which doesn't absorb content added above the user inside it.
export function capturePlace(region = null, blocks = textBlocks()) {
  const box = region ? effectiveScroller(region) : pageScroller;
  // Places are measured from the top of the box's visible band, below whatever covers
  // its top edge (the page's banner), so a region handed from the page to its own body
  // keeps the landmark at the same distance below what the user can see.
  const boxTop = shownBox(box).top + landingInsets(box).top;
  const landmarkTop = (top, block, blockTop = top) =>
    block?.matches(HEADING) ? top + Math.max(0, -blockTop) : top;
  const view = { y: box.scrollTop, scroller: scrollerIdentity(box) };
  for (const [block, rect] of blocksOnScreen(region, blocks)) {
    const section = closestAcross(block, "[id]");
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
    const text = cut(quoteFrom(textNodesUnder(block)), 0, LANDMARK_CAP);
    // A short line ("Risks") would match anywhere; keep scanning for a quotable block.
    if (text.length >= 24) {
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
      view.quoteTop = landmarkTop(rect.top - boxTop, block);
      break;
    }
  }
  return view;
}

// A restore jumps rather than glides: a page is free to set scroll-behavior: smooth, and
// animating from the replacement's raw position is worse than the jump it replaces.
// Moving to a mark the user asked for is the other case, and says so.
export const hasLandmark = (reading) => Boolean(reading?.quote || reading?.section);
export const rawOffsetFits = (reading, scroller) =>
  reading.scroller !== undefined && reading.scroller === scrollerIdentity(scroller);
function scrollerIdentity(scroller) {
  if (scroller === pageScroller) return "$page";
  return readingRegions().find(({ body }) => body === scroller)?.id;
}

export function restorePlace(view, region = null, currentIntent = retainUserIntent()) {
  if (!view) return;
  const box = region ? effectiveScroller(region) : pageScroller;
  const boxTop = shownBox(box).top + landingInsets(box).top;
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
  const section = targetElement(resolveAnchor({ section: view.section }, text));
  if (section) {
    reveal(section, currentIntent);
    // The shown reading on both sides of the subtraction, because the landmark is
    // whatever id stands nearest the block the user was on, and a section that
    // generates no box of its own is one a suggestion wrapping whole sections leaves
    // there. Read raw, both sides come back 0 and the correction is 0 — so the restore
    // that had somewhere to land did nothing, silently, and left the user at the top.
    moveScrollerBy(box, shownBox(section).top - boxTop - view.sectionTop);
  } else if (rawOffsetFits(view, box))
    box.scrollTo({ top: view.y, behavior: "instant" });
}
