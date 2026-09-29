/* Placement for threads: the page's order, which every reading of the threads
   shares, the panel's Recent order, and the page part each thread stands in. */
import { addressableLabel, addressableWord, sectionOf } from "../anchor-resolution.js";
import { pageParts } from "../passages.js";
import { inChrome } from "../passages.js";
import { serverNow } from "../presence.js";
import { readingRegionFor } from "../reading-regions.js";
import { hostIn, upFrom } from "../shadow.js";
import { threadSummary } from "./model.js";
// ---------- where the panel puts a thread ----------
// The list reads in the page's order, not the log's. A page is a document with a
// beginning and an end, and the user walks the thread the way they walk the
// prose it is about: the thread on the lede is the first one, the thread on the punch
// list is the last, and t/T, the marks out on the page and the panel's own scroll all
// say the same order. Log order answered a different question — when a
// thread was opened — which is a question about one thread rather than about a list, and
// the message clocks already answer it.
//
// The panel's Recent order (below) is the one exception, and only the panel's: the
// user asked the list the other question, which thread moved last. The marks and the
// walk with the panel shut keep the page's order.
//
// Where a thread stands is where the anchor pass resolved its passage to (`placed`) — the
// same resolution the marks are drawn from, so the list and the page cannot disagree about
// which of two threads comes first. `inPageOrder` sorts by that placement and breaks
// ties by log order.
//
// A passage this version has rewritten falls back to the element the anchor names, which
// is the whole point of an anchor carrying one: an id survives a rewrite that takes the
// quote down with it, so a thread whose words are gone still belongs where it was about.
// It reads as detached in the list and keeps its place in the page's order, which are two
// true things rather than one true and one lost.
//
// What is left resolves nowhere at all: a general comment, which names nowhere, and an
// anchor whose element this version no longer holds either. Both go under the list rather
// than at some point in the middle of it.
// Where a thread stands, said in the document's own tree. A passage a widget renders into
// a declared shadow root is placed inside that root, and `compareDocumentPosition` answers
// across trees with "disconnected, in an implementation-specific order" — an order no
// user has ever seen, and one `contains` cannot correct. The host is the element the
// page holds, and where the page holds it is where those words are. A place in no tree at
// all — an element a version activation has replaced — is no place, which is the same
// answer an anchor that resolves nowhere gets.
const inPage = (el) => hostIn(el, document);

const threadPlace = (t, placedAt) =>
  inPage(placedAt(t.id)?.element ?? (t.anchor ? sectionOf(t.anchor) : null));

// Which of two elements the user reaches first. `compareDocumentPosition` answers for
// a containing element too — a section reaches the user before the paragraph inside it
// — which is what makes it the whole reading rather than a comparison of two indexes
// into a list this file would have to keep.
const pageOrder = (a, b) =>
  a === b
    ? 0
    : a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING
      ? -1
      : 1;

// The log's order is the tiebreak, so two threads on one paragraph read in the order they
// were opened, and a page that gave nothing an id keeps exactly the list it had.
export function inPageOrder(threads, placedAt) {
  const seat = new Map(threads.map((t, i) => [t, i]));
  const place = new Map(threads.map((t) => [t, threadPlace(t, placedAt)]));
  return [...threads].sort((a, b) => {
    const pa = place.get(a);
    const pb = place.get(b);
    if (!pa || !pb) return (pa ? 0 : 1) - (pb ? 0 : 1) || seat.get(a) - seat.get(b);
    return pageOrder(pa, pb) || seat.get(a) - seat.get(b);
  });
}

// The page's own outline, in document order. Read off the headings the author wrote
// rather than off <section> nesting, because both shapes are in the corpus and a heading
// is the thing a user navigates by in either — a page written as one flow of h2s has an
// outline just as much as one written as nested sections. The runtime's own chrome
// contributes none (pageParts), which also keeps a heading inside a reply's Markdown out
// of the page's outline.
export const pageOutline = () => pageParts("h1, h2, h3, h4, h5, h6");

const subjectLabel = (target) => addressableLabel(target) || addressableWord(target);

// A repeated outline subject needs the nearest named reading region to remain
// distinguishable after a route leaves the page. Unique subjects keep the author's own
// concise name. Page Map consumes this reading so navigation cannot add context that its
// destination drops.
export function outlineSubjectFor(target, peers = [target], outline = pageOutline()) {
  const label = subjectLabel(target);
  const repeated =
    outline.includes(target) &&
    peers.some(
      (candidate) =>
        candidate !== target &&
        outline.includes(candidate) &&
        subjectLabel(candidate) === label,
    );
  return { label, context: repeated ? regionLabel(target) : "" };
}

// The name of the nearest region around a node that has one: a bounded block inside a
// labelled pane is read as part of that pane.
function regionLabel(node) {
  for (
    let region = readingRegionFor(node);
    region;
    region = readingRegionFor(upFrom(region.host))
  ) {
    const label = region.host.getAttribute("aria-label")?.trim();
    if (label) return label;
  }
  return "";
}

// Which part of the page an element is in: the heading that names everything from itself
// to the next one. A place that contains a heading takes that heading rather than the one
// before it — an anchor on a whole <section> is about that section, not about the end of
// the one above.
function headingFor(place, outline) {
  let above = null;
  for (const heading of outline) {
    if (heading === place || place.contains(heading)) return heading;
    if (heading.compareDocumentPosition(place) & Node.DOCUMENT_POSITION_FOLLOWING)
      above = heading;
    else break;
  }
  return above;
}

// What Threads' narrowing reads of where a thread stands: whether its passage is gone
// from this version, which the Placement filter asks, and the name of the page part it
// stands in, which a search matches. A general comment names nowhere and is not gone; a
// thread in the runtime's own chrome, a reply's or the page design's, stands in no part.
export function threadSection(t, outline, placedAt) {
  const place = threadPlace(t, placedAt);
  if (!place)
    return Object.freeze({ gone: Boolean(t.detached_from || t.anchor), section: "" });
  const heading = inChrome(place) ? null : headingFor(place, outline);
  return Object.freeze({ gone: false, section: heading ? subjectLabel(heading) : "" });
}

// ---------- the panel's Recent order ----------
// A thread's latest message is when it last moved. A message still being sent has no
// clock yet and is moving now. Ties keep the log's order.
const lastMoved = (thread, now) => {
  const latest = threadSummary(thread).latest;
  return latest ? Date.parse(latest) : now;
};

export function inRecentOrder(threads) {
  const now = serverNow();
  const seat = new Map(threads.map((t, i) => [t, i]));
  const moved = new Map(threads.map((t) => [t, lastMoved(t, now)]));
  return [...threads].sort(
    (a, b) => moved.get(b) - moved.get(a) || seat.get(a) - seat.get(b),
  );
}
