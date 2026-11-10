/* Where the page's open threads, its On me items and, while the changes view is on, its
 * changes stand along the contents: how many of each the section each row leads holds.
 *
 * A row's section is what its heading heads, by the one rule On me groups its items by
 * and a link's preview names a place by (`partOver`): an item belongs to the first row
 * met climbing from its element through the parts over it. So a paragraph under a
 * heading the outline leaves out, past `max-level`, counts in the row above that
 * heading, and On me's bands and the contents agree on where an item stands. An element
 * a row goes to (its `destination`), such as a section a thread is about as a whole,
 * belongs to that row, and anything above the first section's heading to the start
 * row. Items outside the document the outline covers count nowhere.
 *
 * Threads are the open ones, each at the element its anchor names, as a heading's link
 * preview counts them. On me items are the obligations waiting on the user that the
 * outline's document holds, by the rule every count of a region's obligations reads
 * (`obligationsIn`), each at the widget that asks it; a question answered in words
 * stands nowhere on the page, so it counts here only as its thread. A change counts once
 * in each section its blocks stand in, and a removal in the section it was taken from,
 * by where its gap stands: a paragraph taken from a section's end, whose gap stands
 * before the next section's heading, counts in the section that held it.
 *
 * Climbing costs a node's depth for each part it passes, and every element met on the
 * way keeps the row it reached, so the items under one heading climb it once. */
import { elementById, partOver, under } from "/runtime/widget-api.js";

/** @typedef {{threads: number, onMe: number, changes: number}} SectionMarks */
/** @typedef {{heading: Element | null, destination: Element}} MarkedSection */
/** @typedef {{
 *   threads: readonly {resolved?: unknown, anchor: {section?: string | null} | null}[],
 *   onMe: readonly {source: {id: string}}[],
 *   changes: readonly {blocks: readonly Element[], at: Element, gap: "before" | "after" | "in" | null}[],
 * }} MarkedReadings */

/** Each section's marks, by its heading (the start row's may be null), for those that
 *  hold any: from the page's threads (`readThreads().threads`), the obligations waiting
 *  on the user its document holds (`obligationsIn(scope, readObligations().user)`), and
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
  /** @type {Map<Element, MarkedSection>} */
  const rows = new Map();
  for (const section of sections) {
    rows.set(section.destination, section);
    if (section.heading) rows.set(section.heading, section);
  }
  /** @type {Map<Element, MarkedSection>} */
  const reached = new Map();
  /** @param {Element} element */
  const rowFor = (element) => {
    /** @type {Set<Element>} */
    const climbed = new Set();
    let row = null;
    for (
      let at = /** @type {Element | null} */ (element);
      at && !climbed.has(at);
      at = partOver(at)
    ) {
      row = rows.get(at) ?? reached.get(at) ?? null;
      if (row) break;
      climbed.add(at);
    }
    row ??= start;
    for (const at of climbed) reached.set(at, row);
    return row;
  };
  // The row a removal was taken from: the one holding the element its gap stands after
  // or in, and for a gap before an element, the part over that element as the page's
  // reading reached it, which a heading opening the next section is not in.
  /** @param {MarkedReadings["changes"][number]} removal */
  const removedFrom = ({ at, gap }) => {
    if (gap !== "before") return rowFor(at);
    const over = partOver(at);
    return over ? rowFor(over) : start;
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
