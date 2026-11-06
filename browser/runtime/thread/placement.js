/* Placement for threads: the page's order, which every reading of the threads
   shares, and the part of the page a thing stands in (`partOver`).

   On me groups every item under the part its subject stands in (`partOver` of the
   element it is about): questions, conversations and to-dos alike. A link's preview
   names a place by its own name, else by the part it stands in. So for a thread on a
   whole section, the preview names the section and On me says where that section
   stands: the preview says what a place is, On me where it is, and they agree wherever
   a place has no name of its own. */
import { addressableLabel, addressableWord, ownNaming } from "../addressable-names.js";
import { sectionOf } from "../anchor-resolution.js";
import {
  authoredScope,
  documentOutline,
  elementById,
  GENERATED,
  headed,
  HEADING,
  inPage,
  keptAnswer,
  leafSurface,
  pageDocument,
  pageReadingVersion,
  runsIntoLine,
} from "../passages.js";
import { agentName } from "../semantic-state.js";
import { readingRegionFor } from "../reading-regions.js";
import { byRenderedOrder, overIn, upFrom } from "../shadow.js";
import { threadState } from "./state.js";
import { threadAttention } from "./workflow.js";
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
/** @typedef {(id: string) => {place: Element | null} | null | undefined} PlacedAt */
/** @param {Pick<import("../../types/domain.js").Thread, "id" | "anchor">} t @param {PlacedAt} placedAt */
export const threadPlace = (t, placedAt) => {
  const place = placedAt(t.id)?.place ?? (t.anchor ? sectionOf(t.anchor) : null);
  return place?.isConnected && !leafSurface(place) ? place : null;
};

// The log's order is the tiebreak, so two threads on one paragraph read in the order they
// were opened, and a page that gave nothing an id keeps exactly the list it had.
/** @template {Pick<import("../../types/domain.js").Thread, "id" | "anchor">} T
 * @param {readonly T[]} threads @param {PlacedAt} placedAt */
export const inPageOrder = (threads, placedAt) =>
  byRenderedOrder(threads, /** @param {T} t */ (t) => threadPlace(t, placedAt));

// A document's own outline: the page's, or a message's markup, which is outlined as the
// page is. Read off the headings the author wrote rather than off <section> nesting,
// because both shapes are in the corpus and a heading is the thing a user navigates by in
// either — a page written as one flow of h2s has an outline just as much as one written
// as nested sections. It is recorded by the walk that reads the document's words
// (passages.js, `outlineFold`), so it holds what that reading holds, in its order:
// declared shadow trees as they draw, a slot's assignment and not its fallback, and none
// of Leaf's chrome. Each stands as long as its document's reading does
// (`documentOutline`).
/** @param {Node} node */
const outlineOf = (node) => documentOutline(authoredScope(node));
/** @param {readonly unknown[] | undefined} kept @param {readonly unknown[]} key */
const current = (kept, key) =>
  kept?.every((part, index) => part === key[index]) ?? false;
export const pageOutline = () => documentOutline(pageDocument()).outline;
/** The heading after `heading` in its document's outline, or null.
 * @param {Element} heading */
export function headingAfter(heading) {
  const { outline, at } = outlineOf(heading);
  const index = at.get(heading);
  return index === undefined ? null : (outline[index + 1] ?? null);
}

// What names the part of the page, or of a message's markup, a node stands in: the
// heading over it, else the nearest element holding it that the authoring contract
// names (addressable-names.js, `ownNaming`), or null where none does. On me's bands
// and a link's preview read it as the header says, and an obligation's arrival
// (obligations/view.js, `arrivalRegion`) lands on it.
//
// From the node's innermost container out, the nearest part wins: in each, the last
// heading the reading met before the node that heads that container (passages.js,
// `headed`), else the container's own name by the contract: its declared name, its
// leading heading or disclosure's summary, its caption, or the `aria-label` or <label>
// its author gave it. So a <section> the author wrote names what stands in it before
// its heading, a sub-heading inside it heads what follows the sub-heading, a captioned
// figure or table names what it holds, and a region the author labelled is a part. A
// run-in label, a leading <strong> that words follow before a <br> or a block element,
// as a paragraph's or a titled option's is, names its own element and makes no part: a
// bold label opening a line is no place a reader groups by, so On me's bands and a
// preview's name go on to the part holding the line. A <strong> alone on its line, over
// a <br> or a container's blocks, names that container as a part, as a heading would.
// Which it is is the markup's (`runsIntoLine`), not the line the browser draws: a
// drawn line moved with every style a page could set, a box-less wrapper, kept
// newlines, hidden words, and renamed a part as the reader opened a disclosure, where
// Python's names, read off the document, never move. The contract stops short of the document the node stands in and the
// page's column, whose leading heading titles the page, and passes a
// slot, whose own children are the fallback its assignment replaces, and what Leaf
// generates in the document, whose labels are Leaf's. A heading in a `header` or
// `hgroup` heads what holds that, so a page's title in its header heads the page's
// sections. The container is what "the heading over this" means: a question's own
// heading stands inside the question, so it heads neither the question, which it
// follows, nor the next question, which its container does not hold. A heading the
// reader cannot see, as in a tab not selected, still heads its part, so a part's name
// does not change as the page shows or hides it; an arrival measures what it lands on
// and passes one that shows nothing. On the corpus page, whose pages stand in tabs with
// their titles in headers and their last sections untitled, the container alone sent
// every item to the corpus's own title.
//
// Replaced: only a declared name or a leading heading named a container, while the
// preview named a place by its nearest named holder first (`holderNaming`). The two
// rules disagreed under a sub-heading inside a titled section, the preview saying the
// section and On me the sub-heading; one rule now says the sub-heading for both.
//
// The reading records what stood over each element as its walk reached it, so a call
// costs the node's depth: On me asks it of every item it lists. A node the reading never
// reached, as one the page does not draw, stands as the nearest element it reached does.
/** @param {Element} node */
export function partOver(node) {
  const { over } = outlineOf(node);
  let state = over.get(node);
  for (let at = upFrom(node); state === undefined && at; at = upFrom(at)) {
    const outer = over.get(at);
    if (outer !== undefined) state = { container: at, heading: null, up: outer };
  }
  const scope = authoredScope(node);
  for (let at = state ?? null; at; at = at.up) {
    if (at.heading) return at.heading;
    const { container } = at;
    if (!namesWhatItHolds(container, scope)) continue;
    const naming = ownNaming(container);
    if (!naming) continue;
    // A heading that titles its container heads what the container holds; any other
    // name makes the container the part.
    if (!("by" in naming)) return container;
    if (
      naming.by === node ||
      (naming.by.localName === "strong" && runsIn(naming.by, container))
    )
      continue;
    return naming.by.matches(HEADING) ? naming.by : container;
  }
  return null;
}
// Whether a title runs into words on its own line, as a paragraph's bold lead-in runs
// into its sentence, read off the markup (`runsIntoLine`), so a place is the same part
// whatever the reader opens or the page draws. A title alone on its line heads what
// follows it. Kept as long as its document's reading stands, as the markup does.
/** @param {Element} title @param {Element} container */
const runsIn = (title, container) =>
  keptAnswer(title, "runs into its line", () => runsIntoLine(title, container));
// Whether the contract's name for `container` names what it holds: short of the document
// it stands in and the page's column, never a slot, and never what Leaf generated there.
/** @param {Element} container @param {Element} scope */
const namesWhatItHolds = (container, scope) =>
  container !== scope &&
  container.localName !== "slot" &&
  !(container.localName === "main" && container.parentElement === scope) &&
  !overIn(container, GENERATED, scope);

// Every part of the page a node stands in, outermost first: the part over it
// (`partOver`), then the heading of a higher rank over each heading (the outline's
// `above`), else the part over its container, as a reader of the page passes through
// them to reach the node. A heading's own trail leaves it out. Each step costs what
// `partOver` does, so a trail costs its length times that.
/** @param {Element} node @returns {Element[]} */
export function partTrail(node) {
  /** @param {Element} at @returns {Element | null} */
  const over = (at) => {
    const { above } = outlineOf(at);
    if (!above.has(at)) return partOver(at);
    const container = headed(at);
    return above.get(at) ?? (container ? partOver(container) : null);
  };
  /** @type {Element[]} */
  const trail = [];
  for (let part = over(node); part; part = over(part)) trail.unshift(part);
  return trail;
}

// ---------- where the open conversations stand ----------
// Gathered once for each reading of the threads and the page, so asking about a place
// costs a lookup, whatever the page holds: under each element, the conversations about
// it or anything it holds; under each heading, those about what it heads, as `partOver`
// reads ownership, its own part and those of the headings below its level; each with
// the turn one owes the user (`threadAttention`), the first found. A heading heads
// itself, so a conversation about a heading is its part's, not the part before it.
// Kept against exactly what it reads: the threads as the thread reading publishes them,
// a new value whenever any thread's contents change, its turns included; the agent's
// name the turns are said in; and the page's reading, since an anchor names an element
// of the page.
/** @typedef {{threads: number, turn: NonNullable<ReturnType<typeof threadAttention>> | null}} Conversations
 * @typedef {{key: readonly unknown[], inside: Map<Element, Conversations>, headed: Map<Element, Conversations>}} Gathered */
/** @type {Gathered | null} */
let gathered = null;
/** @returns {Gathered} */
function gatherConversations() {
  const { all, bySection } = threadState();
  const agent = agentName();
  const key = [all, agent, pageReadingVersion()];
  if (gathered && current(gathered.key, key)) return gathered;
  /** @type {Map<Element, Conversations>} */
  const inside = new Map();
  /** @type {Map<Element, Conversations>} */
  const headed = new Map();
  /** @type {Map<Element, Element | null>} */
  const parents = new Map();
  /** @param {Map<Element, Conversations>} map @param {Element} at @param {Conversations} these */
  const add = (map, at, these) => {
    const held = map.get(at);
    map.set(
      at,
      held
        ? { threads: held.threads + these.threads, turn: held.turn ?? these.turn }
        : these,
    );
  };
  for (const [id, positions] of bySection) {
    const element = elementById(id);
    if (!element || !inPage(element)) continue;
    const threads = positions.flatMap((at) => all[at] ?? []);
    const these = {
      threads: threads.length,
      turn:
        threads
          .map((thread) => threadAttention(thread, agent))
          .find((attention) => attention?.kind === "needs_user") ?? null,
    };
    for (let at = /** @type {Element | null} */ (element); at; at = upFrom(at))
      add(inside, at, these);
    for (let at = headingOf(element); at; at = parentHeading(at, parents))
      add(headed, at, these);
  }
  gathered = { key, inside, headed };
  return gathered;
}
/** The open conversations about `place`: for a heading, about the part it heads; for
 * any other element, about it or anything it holds. Null where there are none.
 * @param {Element} place */
export function conversationsAbout(place) {
  const { inside, headed } = gatherConversations();
  return (place.matches(HEADING) ? headed : inside).get(place) ?? null;
}
// The heading that heads `element`: itself, or the first heading over it (`partOver`).
/** @param {Element} element @returns {Element | null} */
function headingOf(element) {
  for (
    let at = element.matches(HEADING) ? element : partOver(element);
    at;
    at = partOver(at)
  )
    if (at.matches(HEADING)) return at;
  return null;
}
// The heading whose part holds `heading`'s: the first heading over it at a higher level.
/** @param {Element} heading @param {Map<Element, Element | null>} parents @returns {Element | null} */
function parentHeading(heading, parents) {
  const known = parents.get(heading);
  if (known !== undefined) return known;
  let at = headingOf(partOver(heading) ?? heading);
  if (at === heading) at = null;
  while (at && level(at) >= level(heading)) at = parentHeading(at, parents);
  parents.set(heading, at);
  return at;
}
/** @param {Element} heading */
const level = (heading) => Number(heading.localName.slice(1));

/** @param {Element} target */
const subjectLabel = (target) => addressableLabel(target) || addressableWord(target);

// A repeated outline subject needs the nearest named reading region to remain
// distinguishable after a route leaves the page. Unique subjects keep the author's own
// concise name. Page Map consumes this reading so navigation cannot add context that its
// destination drops.
/** @param {Element} target @param {readonly Element[]} [peers] @param {readonly Element[]} [outline] */
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
/** @param {Element} node */
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
