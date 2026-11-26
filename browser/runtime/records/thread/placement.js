/* Placement for threads: the page's order, which the walks and the marks share, and
   the part of the page a thing stands in (`partOver`).

   On Me groups every item under the part its subject stands in (`partOver` of the
   element it is about): questions, conversations and to-dos alike. A link's preview
   names a place by its own name, else by the part it stands in. So for a thread on a
   whole section, the preview names the section and On Me says where that section
   stands: the preview says what a place is, On Me where it is, and they agree wherever
   a place has no name of its own. */
import {
  addressableLabel,
  ownNaming,
  titlingHeading,
} from "../../readings/addressable-names.js";
import { addressableWord } from "../../lib/element-word.js";
import { sectionOf } from "../../readings/anchor-resolution.js";
import {
  authoredScope,
  documentOutline,
  elementById,
  GENERATED,
  headed,
  HEADING,
  inPage,
  leafSurface,
  pageDocument,
} from "../../readings/passages.js";
import { agentName } from "../../state/semantic-state.js";
import { readingRegionFor } from "../../readings/reading-regions.js";
import { overIn, upFrom } from "../../lib/shadow-tree.js";
import { threadState } from "./state.js";
import { threadAttention } from "./workflow.js";
import { kept } from "../../state/kept.js";
// ---------- where a thread stands in the page's order ----------
// The `t` walk steps through threads in the page's order, not the log's. A page is a
// document with a beginning and an end, and the user walks the threads the way they
// walk the prose they are about: the thread on the lede is the first one, the thread on
// the punch list is the last, and t/T and the marks out on the page say the same order.
// Threads, the panel's list, answers a different question, what changed last, and reads
// newest first (panel/floating-panel.js, `threadsListing`).
//
// Where a thread stands is where the anchor pass resolved its passage to (`placed`) — the
// same resolution the marks are drawn from, so the walk and the page cannot disagree
// about which of two threads comes first. A walk sorts by that placement
// (`byRenderedOrder`), which breaks ties by log order, so two threads on one paragraph
// read in the order they were opened.
//
// A passage this version has rewritten falls back to the element the anchor names, which
// is the whole point of an anchor carrying one: an id survives a rewrite that takes the
// quote down with it, so a thread whose words are gone still belongs where it was about.
// It reads as detached and keeps its place in the page's order, which are two true
// things rather than one true and one lost.
//
// What is left resolves nowhere on the page: a general comment, which names nowhere; an
// anchor whose element this version no longer holds either; and an anchor in another
// thread's message, such as a comment on a widget an agent's reply carries. Such a
// message is drawn in a Leaf surface only while something shows it, and the walk itself
// opens and closes those views, so a place there would move the thread up and down the
// walk between presses and `t` would visit it twice and skip its neighbour. They all go
// after every placed thread, in log order, rather than at some point in the middle.
// Where a thread stands, for every reading of the page's order of threads: both walks'
// steps (`threadPlace` in destination.js) and the order of Threads' drafts. A passage a
// widget renders into a declared shadow root is placed inside that root, and the page's
// order is read across those trees (`renderedOrder`, lib/shadow-tree.js), so threads
// inside one widget keep their order among themselves. A place in no tree at all — an
// element a version activation has replaced — is no place, which is the same answer an
// anchor that resolves nowhere gets.
/** @typedef {(id: string) => {place: Element | null} | null | undefined} PlacedAt */
/** Where anchor placement puts a thread, a saved draft or the comment being composed
 * (annotations/anchor-placement.js), as the readers it is handed to read it.
 * @typedef {ReturnType<typeof import("./state.js").allThreads>[number]} Thread
 * @typedef {import("../../../types/contract.js").CompleteUnion<import("../../readings/resolved-target.js").ResolvedTarget & {message?: string}>} ResolvedTarget
 * @typedef {ResolvedTarget & {messageTarget: ReturnType<typeof import("./messages.js").messageHolding>,
 * point: Element | null, pointRow: string | null, pointWords: string | null}} Placement
 * @typedef {ReturnType<typeof import("../../readings/anchor-resolution.js").resolveAnchor>} PendingPlacement
 * @typedef {{open: boolean, anchor: import("../../../types/domain.js").Anchor | null, about: string | null,
 * drawing: import("../../../types/domain.js").DraftDrawing | null}} ThreadDraft
 * @typedef {{readings: {thread: Thread, placement: Placement}[],
 * draft: ThreadDraft & {resolved: PendingPlacement}, action: PendingPlacement}} PlacementReading
 * @typedef {{placedAt: (id: string | null | undefined) => Placement | undefined,
 * savedAt: (context: string) => Placement | undefined, pendingAt: () => PendingPlacement}} ThreadPlacements
 */
/** @param {Pick<import("../../../types/domain.js").Thread, "id" | "anchor">} t @param {PlacedAt} placedAt */
export const threadPlace = (t, placedAt) => {
  const place = placedAt(t.id)?.place ?? (t.anchor ? sectionOf(t.anchor) : null);
  return place?.isConnected && !leafSurface(place) ? place : null;
};

// A document's own outline: the page's, or a message's markup, which is outlined as the
// page is. Read off the headings the author wrote rather than off <section> nesting,
// because both shapes are in the corpus and a heading is the thing a user navigates by in
// either — a page written as one flow of h2s has an outline just as much as one written
// as nested sections. It is recorded by the walk that reads the document's words
// (readings/passages.js, `outlineFold`), so it holds what that reading holds, in its order:
// declared shadow trees as they draw, a slot's assignment and not its fallback, and none
// of Leaf's chrome. Each stands as long as its document's reading does
// (`documentOutline`).
/** @param {Node} node */
const outlineOf = (node) => documentOutline(authoredScope(node));
/** The heading after `heading` in its document's outline, or null.
 * @param {Element} heading */
export function headingAfter(heading) {
  const { outline, at } = outlineOf(heading);
  const index = at.get(heading);
  return index === undefined ? null : (outline[index + 1] ?? null);
}

// What names the part of the page, or of a message's markup, a node stands in: the
// heading over it, else the nearest element holding it that the authoring contract
// names (readings/addressable-names.js, `ownNaming`), or null where none does. On Me's bands
// and a link's preview read it as the header says, and an obligation's arrival
// (records/obligations/view.js, `arrivalRegion`) lands on it.
//
// From the node's innermost container out, the nearest part wins: in each, the last
// heading the reading met before the node that heads that container (readings/passages.js,
// `headed`), else the container's own name by the contract: its declared name, its
// leading heading or disclosure's summary, its caption, or the `aria-label` or <label>
// its author gave it. So a <section> the author wrote names what stands in it before
// its heading, a sub-heading inside it heads what follows the sub-heading, a captioned
// figure or table names what it holds, a region the author labelled is a part, and so is
// a widget its `label` names, such as an option card or a tab. A <strong> names nothing,
// so it makes no part. The contract stops
// short of the document the node stands in and the page's column, whose leading heading
// titles the page, and passes a slot, whose own children are the fallback its
// assignment replaces, and what Leaf generates in the document, whose labels are
// Leaf's. A heading in a `header` or `hgroup` heads what holds that, so a page's title
// in its header heads the page's sections. The container is what "the heading over
// this" means: a question's own heading stands inside the question, so it heads neither
// the question, which it follows, nor the next question, which its container does not
// hold. The question stands in the part around it, which is where On Me groups it; what
// a heading counts as its own also takes in the element it titles
// (`conversationsAbout`). A heading the reader cannot see, as in a tab not selected,
// still heads its part, so a part's name does not change as the page shows or hides it;
// an arrival measures what it lands on and passes one that shows nothing. On the corpus
// page, whose pages stand in tabs with their titles in headers and their last sections
// untitled, the container alone would send every item to the corpus's own title.
//
// Rejected: only a declared name or a leading heading naming a container, while the
// preview names a place by its nearest named holder first (`holderNaming`). The two
// rules disagree under a sub-heading inside a titled section, the preview saying the
// section and On Me the sub-heading; one rule says the sub-heading for both.
//
// The reading records what stood over each element as its walk reached it, so a call
// costs the node's depth: On Me asks it of every item it lists. A node the reading never
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
    // A heading that titles its container heads what the container holds, and any other
    // name makes the container the part.
    if (!("by" in naming)) return container;
    if (naming.by === node) continue;
    return naming.by.matches(HEADING) ? naming.by : container;
  }
  return null;
}
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
// itself and the element it titles (readings/addressable-names.js, `titledElement`), so a
// conversation about a heading, or about the whole question or section it titles, is
// its part's, not the part before it.
//
// Rejected: a heading counting only what `partOver` puts under it, which places a
// question in the part around it, so a thread about a whole question counts under the
// heading before the question, and the question's own heading previews none.
//
// Kept until something it read changes (state/kept.js, `kept`): the threads, a new value
// whenever any thread's contents change, its turns included; the agent's name the
// turns are said in; and the page's reading, since an anchor names an element of the
// page.
/** @typedef {{threads: number, turn: NonNullable<ReturnType<typeof threadAttention>> | null}} Conversations */
const gatherConversations = kept(() => {
  const { all, bySection } = threadState();
  const agent = agentName();
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
          .find((attention) => attention?.turn === "user") ?? null,
    };
    for (let at = /** @type {Element | null} */ (element); at; at = upFrom(at))
      add(inside, at, these);
    for (let at = headingOf(element); at; at = parentHeading(at, parents))
      add(headed, at, these);
  }
  return { inside, headed };
});
/** The open conversations about `place`: for a heading, about the part it heads; for
 * any other element, about it or anything it holds. Null where there are none.
 * @param {Element} place */
export function conversationsAbout(place) {
  const { inside, headed } = gatherConversations();
  return (place.matches(HEADING) ? headed : inside).get(place) ?? null;
}
// The heading that heads `element`, the later in the page of two: the first heading met
// climbing the parts over it (`partOver`), and the heading titling the nearest element
// around it that a heading titles (`titlingHeading`). So a thread about a question is
// its heading's, though `partOver` puts the question in the part around it, and a
// sub-heading inside a titled section still heads what follows it there.
/** @param {Element} element @returns {Element | null} */
function headingOf(element) {
  let over = element.matches(HEADING) ? element : partOver(element);
  while (over && !over.matches(HEADING)) over = partOver(over);
  /** @type {Element | null} */
  let titled = null;
  for (let at = /** @type {Element | null} */ (element); at && !titled; at = upFrom(at))
    titled = at.matches(HEADING) ? at : titlingHeading(at);
  if (!over || !titled) return over ?? titled;
  return over.compareDocumentPosition(titled) & Node.DOCUMENT_POSITION_FOLLOWING
    ? titled
    : over;
}
// The heading whose part holds `heading`'s: the first heading over it at a higher level.
/** @param {Element} heading @param {Map<Element, Element | null>} parents @returns {Element | null} */
function parentHeading(heading, parents) {
  const known = parents.get(heading);
  if (known !== undefined) return known;
  let at = partOver(heading);
  while (at && !at.matches(HEADING)) at = partOver(at);
  while (at && level(at) >= level(heading)) at = parentHeading(at, parents);
  parents.set(heading, at);
  return at;
}
/** @param {Element} heading */
const level = (heading) => Number(heading.localName.slice(1));

/** @param {Element} target */
const subjectLabel = (target) => addressableLabel(target) || addressableWord(target);

// A repeated outline subject needs the nearest named reading region to remain
// distinguishable after a route leaves the page: the name of that region, its context.
// Unique subjects keep the author's own concise name, and take none. Page Map consumes
// this reading so navigation cannot add context that its destination drops. A subject
// is repeated where another of `peers` in the page's outline has its label; the peers
// are counted by label once, so each target's context costs one lookup rather than a
// walk of the others, and a target outside the outline reads no label at all.
/** @param {readonly Element[]} peers @returns {(target: Element) => string} */
export function outlineContexts(peers) {
  const { at } = documentOutline(pageDocument());
  /** @type {Map<Element, string>} */
  const labels = new Map();
  /** @param {Element} target */
  const labelOf = (target) => {
    const kept = labels.get(target);
    if (kept !== undefined) return kept;
    const label = subjectLabel(target);
    labels.set(target, label);
    return label;
  };
  const named = new Set(peers.filter((peer) => at.has(peer)));
  /** @type {Map<string, number>} */
  const counted = new Map();
  for (const peer of named)
    counted.set(labelOf(peer), (counted.get(labelOf(peer)) ?? 0) + 1);
  return (target) => {
    if (!at.has(target)) return "";
    const others = (counted.get(labelOf(target)) ?? 0) - (named.has(target) ? 1 : 0);
    return others > 0 ? regionLabel(target) : "";
  };
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
