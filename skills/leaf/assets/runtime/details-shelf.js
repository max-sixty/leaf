/* Runtime apparatus about an authored element, kept out of the page's structure.
 *
 * Some of what the runtime says about an element is a control a screen reader must be
 * able to reach from that element: a commented block's note, a drawing's "Respond to…"
 * proxies. None of it may stand inside or beside the element. An element added among the
 * page's own changes which child is first, last, and only, and what an `h2 + p` rule
 * finds next, so the page's own rules would restyle and move its content for as long as
 * the apparatus stood (assets/AGENTS.md, "Space and scrolling").
 *
 * So each such note stands on one shelf in the chrome, and its element names it as its
 * details, ARIA's relation for an annotation, which the browser exposes on the element's
 * accessibility node; screen readers differ in how they announce it and whether they
 * offer a move to its target. That relation is the only trace on the element. It is
 * written through element reflection, which reaches the shelf in the document from an
 * element inside a widget's shadow tree, where an id reference cannot. `aria-owns` would
 * seat a note in the element's reading order, but Chrome has no reflection for it, so it
 * could name notes only for elements in the document's own tree.
 *
 * Every writer of the relation goes through here, so an element holding notes of more
 * than one kind names all of them, and whatever its own `aria-details` names stays ahead
 * of them. A revision that keeps the element patches its attributes to the new source and
 * takes the relation off with it, so `shelve` is asked on every pass rather than once:
 * where the relation this module wrote no longer stands, the element's current value is
 * the authored one to keep, and the one to restore when its last note goes.
 *
 * Nothing on the shelf is a Tab stop: from the chrome it would come after the whole
 * page, away from the element it is about, so each owner takes its controls out of the
 * Tab order. Focus on a note stands at its element (standing-target.js).
 */
import { chromeRoot } from "./chrome.js";
import { declareSide } from "./standing-target.js";
import { offer } from "./widget-elements.js";

// element -> { notes, authored, authoredElements, written }; a note's element, read back.
const records = new Map();
const owners = new WeakMap();
let shelf = null;

declareSide((node) => {
  for (let at = node; at && at !== shelf; at = at.parentElement) {
    const element = owners.get(at);
    if (element) return element;
  }
  return null;
});

const same = (left, right) =>
  left.length === right.length && left.every((node, index) => node === right[index]);

const standing = (element, record) =>
  record.written !== null && same(element.ariaDetailsElements ?? [], record.written);

function name(element, record) {
  if (!standing(element, record)) {
    record.authored = element.getAttribute("aria-details");
    record.authoredElements = element.ariaDetailsElements ?? [];
    record.written = null;
  }
  const wanted = [...record.authoredElements, ...record.notes];
  if (record.written && same(record.written, wanted)) return;
  element.ariaDetailsElements = wanted;
  record.written = element.ariaDetailsElements ?? [];
}

// Stand `note` on the shelf and have `element` name it. Idempotent, and meant to be asked
// on every pass that finds the note still owed.
export function shelve(element, note) {
  shelf ??= offer("div", "lf-details-shelf");
  if (!shelf.isConnected) chromeRoot.append(shelf);
  if (note.parentNode !== shelf) shelf.append(note);
  owners.set(note, element);
  let record = records.get(element);
  if (!record) {
    record = { notes: [], authored: null, authoredElements: [], written: null };
    records.set(element, record);
  }
  if (!record.notes.includes(note)) record.notes.push(note);
  name(element, record);
}

// Take `note` off the shelf and out of `element`'s relation. The element's authored
// `aria-details` comes back with its last note, unless a revision has since written the
// attribute, which is then the authored value already.
export function unshelve(element, note) {
  note.remove();
  owners.delete(note);
  const record = records.get(element);
  if (!record?.notes.includes(note)) return;
  record.notes = record.notes.filter((held) => held !== note);
  if (record.notes.length) {
    name(element, record);
    return;
  }
  if (standing(element, record)) {
    if (record.authored === null) element.removeAttribute("aria-details");
    else element.setAttribute("aria-details", record.authored);
  }
  records.delete(element);
}
