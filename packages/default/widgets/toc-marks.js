/* Where the page's open threads, its On Me items and, while the changes view is on, its
 * changes stand along the contents: how many of each the section each row leads holds.
 *
 * A row's section is its stretch of the page, as the map draws it: from its destination
 * (toc-view.js), the element its heading titles or an identified one inside that
 * (`titledElement`), to the next row's. An item counts in the row whose stretch holds
 * its first word, so a thread about a whole question or the section around it counts
 * in the question's row, as does a paragraph after the question before the next
 * heading, which the map marks as part of that row while the reader is on it. A heading
 * the outline leaves out, past `max-level`, starts no stretch, so what stands under it
 * counts in the row above. Anything before the first section's destination belongs to
 * the start row. Items outside the document the outline covers count nowhere, and one
 * inside a widget's shadow tree stands where its host does.
 *
 * Threads are the open ones, each at the element its anchor names, as a heading's link
 * preview counts them. On Me items are the obligations waiting on the user that the
 * outline's document holds, by the rule every count of a region's obligations reads
 * (`readObligations(region)`), each at the widget that asks it; a question answered in words
 * stands nowhere on the page, so it counts here only as its thread. A change counts once
 * in each section its blocks stand in, and a removal in the section it was taken from,
 * by where its gap stands: a paragraph taken from a section's end, whose gap stands
 * before the next section's heading, counts in the section that held it.
 *
 * Rejected: counting each item under the first row met climbing the parts over it
 * (`partOver`), the rule On Me groups by, which puts a question in the part around it,
 * so a thread about a whole question counted in the row above, and a paragraph after a
 * question in a different row from the map's.
 *
 * Each item costs a binary search over the rows, comparing positions in the document. */
import { elementById } from "/runtime/widget-api.js";
import { under } from "/runtime/lib/shadow-tree.js";

/** @typedef {{threads: number, onMe: number, changes: number}} SectionMarks */
/** @typedef {{heading: Element | null, destination: Element}} MarkedSection */
/** @typedef {{
 *   threads: readonly {resolved?: unknown, anchor: {section?: string | null} | null}[],
 *   onMe: readonly {source: {id: string}}[],
 *   changes: readonly {blocks: readonly Element[], at: Element, gap: "before" | "after" | "in" | null}[],
 * }} MarkedReadings */

/** Each section's marks, by its heading (the start row's may be null), for those that
 *  hold any: from the page's threads (`readThreads().threads`), the obligations waiting
 *  on the user its document holds (`readObligations(scope).user`), and
 *  the comparison's changes in it (`comparisonChanges(scope)`).
 * @param {Element} scope the document the outline covers
 * @param {readonly MarkedSection[]} sections the outline's rows, the start row first
 * @param {MarkedReadings} readings
 * @returns {Map<Element | null, SectionMarks>} */
export function sectionMarks(scope, sections, { threads, onMe, changes }) {
  const [start] = sections;
  /** @type {Map<Element | null, SectionMarks>} */
  const marks = new Map();
  if (!start) return marks;
  // Each row's stretch starts at its destination's first word, in the page's order,
  // which the outline's order keeps: a heading's destination never holds an earlier one.
  const starts = sections
    .slice(1)
    .map((row) => ({ row, at: firstWord(row.destination) }));
  // The row whose stretch holds `node`: the last starting at it or before it, or with
  // `strictly`, before it.
  /** @param {Node} node @param {boolean} [strictly] */
  const rowAt = (node, strictly = false) => {
    let low = 0;
    let high = starts.length;
    while (low < high) {
      const middle = (low + high) >> 1;
      const at = /** @type {Node} */ (starts[middle]?.at);
      if (at === node ? !strictly : follows(at, node)) low = middle + 1;
      else high = middle;
    }
    return starts[low - 1]?.row ?? start;
  };
  /** @param {Element} element */
  const rowFor = (element) => rowAt(firstWord(inScope(element, scope)));
  // The row a removal was taken from: the one holding the last word its gap stands after
  // or in, and for a gap before an element, the one holding what stands before that
  // element's first word, which is not the row an element opens.
  /** @param {MarkedReadings["changes"][number]} removal */
  const removedFrom = ({ at, gap }) => {
    const element = inScope(at, scope);
    return gap === "before"
      ? rowAt(firstWord(element), true)
      : rowAt(lastWord(element));
  };
  /** @param {MarkedSection} row @param {keyof SectionMarks} kind */
  const count = (row, kind) => {
    const held = marks.get(row.heading) ?? { threads: 0, onMe: 0, changes: 0 };
    held[kind] += 1;
    marks.set(row.heading, held);
  };

  for (const thread of threads) {
    const section = thread.resolved ? null : thread.anchor?.section;
    const element = section ? elementById(section) : null;
    if (element && under(element, scope)) count(rowFor(element), "threads");
  }
  for (const item of onMe) {
    const element = elementById(item.source.id);
    if (element) count(rowFor(element), "onMe");
  }
  for (const change of changes) {
    const touched = new Set(
      change.blocks.length ? change.blocks.map(rowFor) : [removedFrom(change)],
    );
    for (const row of touched) count(row, "changes");
  }
  return marks;
}

/** What a section's marks say, in the words its link's preview shows them in, or ""
 *  for none: "2 threads · 1 waiting on me · 1 change".
 * @param {SectionMarks | undefined} marks */
export function marksWords(marks) {
  if (!marks) return "";
  /** @param {number} count @param {string} one */
  const counted = (count, one) => `${count} ${one}${count === 1 ? "" : "s"}`;
  return [
    marks.threads ? counted(marks.threads, "thread") : "",
    marks.onMe ? `${marks.onMe} waiting on me` : "",
    marks.changes ? counted(marks.changes, "change") : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

// Whether `node` stands after `at` in the page, inside it included.
/** @param {Node} at @param {Node} node */
const follows = (at, node) =>
  Boolean(at.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING);
// The element's first and last words, or the element where it has none.
/** @param {Element} element @returns {Node} */
function firstWord(element) {
  const walker = element.ownerDocument.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode())
    if (node.textContent?.trim()) return node;
  return element;
}
/** @param {Element} element @returns {Node} */
function lastWord(element) {
  const walker = element.ownerDocument.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  for (let node = walker.lastChild(); node; node = walker.previousNode())
    if (node.textContent?.trim()) return node;
  return element;
}
// Where an element stands in the outline's document: itself, or the host of the shadow
// tree it stands in.
/** @param {Element} element @param {Element} scope @returns {Element} */
function inScope(element, scope) {
  let at = element;
  for (
    let root = at.getRootNode();
    root !== scope.getRootNode();
    root = at.getRootNode()
  )
    if (root instanceof ShadowRoot) at = root.host;
    else break;
  return at;
}
