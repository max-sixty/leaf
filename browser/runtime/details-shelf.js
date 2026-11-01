/* Runtime apparatus about an authored element, kept out of the page's structure.
 *
 * Some of what the runtime says about an element is a control a screen reader must be
 * able to reach from that element: a commented block's note, a drawing's "Respond to…"
 * proxies. None of it may stand inside or beside the element. An element added among the
 * page's own changes which child is first, last, and only, and what an `h2 + p` rule
 * finds next, so the page's own rules would restyle and move its content for as long as
 * the apparatus stood (browser/AGENTS.md, "The page holds still under the user's aim").
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
 * of them. Writing the relation leaves the content attribute empty, so an attribute that
 * is anything else was written by the page: first as authored, or by a revision that
 * keeps the element and patches its attributes to the new source, which takes the
 * relation off with it. `shelve` is therefore asked on every pass rather than once, and
 * the value it finds is the authored one to keep ahead of the notes and to restore when
 * the last of them goes.
 *
 * Nothing on the shelf is a Tab stop: from the chrome it would come after the whole
 * page, away from the element it is about, so each owner takes its controls out of the
 * Tab order. The shelf stands fixed at the window's head, so a note focused at rest moves
 * nothing (chrome.css). Focus on a note stands at its element (current-target.js).
 */
import { chromeRoot } from "./chrome.js";
import { move } from "./dom-move.js";
import { declareSide } from "./current-target.js";
import { upFrom } from "./shadow.js";
import { offer } from "./widget-elements.js";

// element -> { notes, authored }; a note's element, read back.
/** @typedef {{notes: Element[], authored: string | null}} ShelfRecord */
/** @type {Map<Element, ShelfRecord>} */
const records = new Map();
/** @type {WeakMap<Node, Element>} */
const owners = new WeakMap();
/** @type {HTMLDivElement | null} */
let shelf = null;

declareSide((node) => {
  /** @type {Element | null} */
  let at = node;
  for (; at && at !== shelf; at = upFrom(at)) {
    const element = owners.get(at);
    if (element) return element;
  }
  return null;
});

/** @template T @param {readonly T[]} left @param {readonly T[]} right */
const same = (left, right) =>
  left.length === right.length && left.every((node, index) => node === right[index]);

// The elements an authored `aria-details` names, looked up where the element stands.
/** @param {Element} element @param {string | null} value */
const authoredDetails = (element, value) => {
  const root = element.getRootNode();
  if (!("getElementById" in root)) return [];
  return (value ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .flatMap((id) => {
      const node = root.getElementById(id);
      return node ? [node] : [];
    });
};

// The relation this module wrote still stands where the attribute is the empty value
// writing it leaves.
/** @param {Element} element */
const written = (element) => element.getAttribute("aria-details") === "";

/** @param {Element} element @param {ShelfRecord} record */
function name(element, record) {
  if (!written(element)) record.authored = element.getAttribute("aria-details");
  const wanted = [...authoredDetails(element, record.authored), ...record.notes];
  if (written(element) && same(element.ariaDetailsElements ?? [], wanted)) return;
  element.ariaDetailsElements = wanted;
}

// Stand `note` on the shelf and have `element` name it. Idempotent, and meant to be asked
// on every pass that finds the note still owed.
/** @param {Element} element @param {Element} note */
export function shelve(element, note) {
  shelf ??= offer("div", "lf-details-shelf");
  if (!shelf.isConnected) chromeRoot.append(shelf);
  if (note.parentNode !== shelf) move(shelf, note, null);
  owners.set(note, element);
  let record = records.get(element);
  if (!record) {
    record = { notes: [], authored: null };
    records.set(element, record);
  }
  if (!record.notes.includes(note)) record.notes.push(note);
  name(element, record);
}

// Take `note` off the shelf and out of `element`'s relation. The element's authored
// `aria-details` comes back with its last note.
/** @param {Element} element @param {Element} note */
export function unshelve(element, note) {
  const record = records.get(element);
  if (record?.notes.includes(note)) {
    record.notes = record.notes.filter((held) => held !== note);
    if (record.notes.length) name(element, record);
    else {
      if (written(element)) {
        if (record.authored === null) element.removeAttribute("aria-details");
        else element.setAttribute("aria-details", record.authored);
      }
      records.delete(element);
    }
  }
  note.remove();
  owners.delete(note);
}
