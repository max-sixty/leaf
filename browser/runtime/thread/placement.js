/* Placement for threads: the page's order, which every reading of the threads
   shares. */
import {
  addressableLabel,
  addressableWord,
  declaredName,
} from "../addressable-names.js";
import { sectionOf } from "../anchor-resolution.js";
import { leafSurface, pageParts, pageReadingVersion } from "../passages.js";
import { documentChanged } from "../semantic-state.js";
import { readingRegionFor } from "../reading-regions.js";
import { byRenderedOrder, renderedOrder, upFrom } from "../shadow.js";
// ---------- where the panel puts a thread ----------
// The list reads in the page's order, not the log's. A page is a document with a
// beginning and an end, and the user walks the thread the way they walk the
// prose it is about: the thread on the lede is the first one, the thread on the punch
// list is the last, and t/T, the marks out on the page and the panel's own scroll all
// say the same order. Log order answered a different question — when a
// thread was opened — which is a question about one thread rather than about a list, and
// the message clocks already answer it.
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
// What is left resolves nowhere on the page: a general comment, which names nowhere; an
// anchor whose element this version no longer holds either; and an anchor in another
// thread's message, such as a comment on a widget an agent's reply carries. Such a
// message is drawn in a Leaf surface only while something shows it, and the walk itself
// opens and closes those views, so a place there would move the thread up and down the
// list between presses and `t` would visit it twice and skip its neighbour. They all go
// under the list, in log order, rather than at some point in the middle of it.
// Where a thread stands, for every reading of the page's order of threads: the list's
// sort and both walks' steps (`threadPlace` in destination.js). A passage a widget renders into a declared shadow root is
// placed inside that root, and the page's order is read across those trees
// (`renderedOrder`, shadow-tree.js), so threads inside one widget keep their order among
// themselves. A place in no tree at all — an element a version activation has replaced —
// is no place, which is the same answer an anchor that resolves nowhere gets.
export const threadPlace = (t, placedAt) => {
  const place = placedAt(t.id)?.place ?? (t.anchor ? sectionOf(t.anchor) : null);
  return place?.isConnected && !leafSurface(place) ? place : null;
};

// The log's order is the tiebreak, so two threads on one paragraph read in the order they
// were opened, and a page that gave nothing an id keeps exactly the list it had.
export const inPageOrder = (threads, placedAt) =>
  byRenderedOrder(threads, (t) => threadPlace(t, placedAt));

// The page's own outline, in the order it renders, widgets' shadow trees included. Read off the headings the author wrote
// rather than off <section> nesting, because both shapes are in the corpus and a heading
// is the thing a user navigates by in either — a page written as one flow of h2s has an
// outline just as much as one written as nested sections. The runtime's own chrome
// contributes none (pageParts), which also keeps a heading inside a reply's Markdown out
// of the page's outline.
//
// It is a reading of the page's own nodes, so it stands until the page reading moves
// (passages.js, `pageReadingVersion`) or a caller says the document changed
// (`presentDocument`): a thread pass over an unchanged page reads the outline it read.
let outlined = null;
export function pageOutline() {
  const key = [pageReadingVersion(), documentChanged()];
  if (outlined?.key.every((part, index) => part === key[index]))
    return outlined.outline;
  const outline = Object.freeze(
    byRenderedOrder(pageParts("h1, h2, h3, h4, h5, h6"), (heading) => heading),
  );
  outlined = { key, outline };
  return outline;
}

// What names the part of the page a node stands in: the heading over it, else the
// nearest region holding it whose declaration titles it (`declaredName`), such as a tab
// by its label, or null where neither does. A run-in title, a paragraph's leading
// <strong>, names its paragraph and no part. On me's place for an item and an obligation's arrival
// (obligations/view.js, `arrivalRegion`) both ask it.
//
// A heading heads its container from where it stands on: the outline's last heading
// before the node, in the rendered order (`renderedOrder`), whose container holds the
// node, asked from the node's innermost container out, so the nearest part wins. A
// heading in a `header` or `hgroup` heads what holds that, as HTML's outline reads it,
// so a page's title in its header heads the page's sections. The container is what
// "the heading over this" means: a question's own heading stands inside the question,
// so it heads neither the question, which it follows, nor the next question, which its
// container does not hold. A heading the reader cannot see, as in a tab not selected,
// still heads its part, so a part's name does not change as the page shows or hides
// it; an arrival measures what it lands on and passes one that shows nothing. On the
// corpus page, whose pages stand in tabs with their titles in headers and their last
// sections untitled, the container alone sent every item to the corpus's own title.
const HEADERS = "header, hgroup";
const headed = (heading) => {
  const at = upFrom(heading);
  return at?.matches(HEADERS) ? upFrom(at) : at;
};
export function partOver(node, outline = pageOutline()) {
  const heads = new Map();
  for (const heading of outline)
    if (renderedOrder(heading, node) < 0) heads.set(headed(heading), heading);
  for (let at = upFrom(node); at; at = upFrom(at)) {
    const heading = heads.get(at);
    if (heading) return heading;
    if (declaredName(at)) return at;
  }
  return null;
}

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
