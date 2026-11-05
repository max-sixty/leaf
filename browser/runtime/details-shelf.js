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
 * Tab order, and builds each as a proxy (control-faces.js, `proxy`), which shows
 * nothing of its own. Focus on a note stands at what it stands for (`standsFor`): the
 * user's place is there (current-target.js), and the focus brings it into view,
 * nearest, as a focus move to it would, opening what folds it away. The focus ring
 * stands round it, in a drawn part's own contour (target-paint.js, the proxy ring), on
 * any focus, visible or not: nothing but the keys or assistive technology reaches the
 * shelf. The ring follows what the note stands for while focus stays, so a target the
 * page draws anew, which shelves the note under the new element, takes it with it.
 * A note standing for a place the element only stands beside, as a removed paragraph's
 * gap stands beside the block after it, has its owner open, bring into view and ring
 * that place instead (margin-bars.js), and says so as it is shelved (`presents:
 * false`). The shelf stands fixed, so the focus moves the page no other way
 * (chrome.css).
 */
import { chromeRoot } from "./chrome.js";
import { move } from "./dom-move.js";
import { declareSide } from "./current-target.js";
import { focused, onCurrentLocation } from "./focus.js";
import { visualAt } from "./anchor-resolution.js";
import { paintProxyRing } from "./target-paint.js";
import { scrollIntoView } from "./landing-scroll.js";
import { upFrom } from "./shadow.js";
import { retainUserIntent } from "./user-intent.js";
import { offer, reveal } from "./widget-elements.js";

// element -> { notes, authored }; a note -> its element and the reading of what a
// node in it stands for.
/** @typedef {{notes: Element[], authored: string | null}} ShelfRecord */
/** @typedef {(node: Element) => Element | null} StandsFor */
/** @typedef {{element: Element, standsFor: StandsFor, presents: boolean}} ShelfOwner */
/** @type {Map<Element, ShelfRecord>} */
const records = new Map();
/** @type {WeakMap<Node, ShelfOwner>} */
const owners = new WeakMap();
/** @type {HTMLDivElement | null} */
let shelf = null;

// How the note a node on the shelf is in was shelved, or null for a node off the shelf.
/** @param {Element} node */
function noteOf(node) {
  /** @type {Element | null} */
  let at = node;
  for (; at && at !== shelf; at = upFrom(at)) {
    const owner = owners.get(at);
    if (owner) return owner;
  }
  return null;
}
// What a node on the shelf stands for: what its note's owner reads for the node, such as
// one of a picture's parts for that part's proxy, else the element naming the note.
// Null for a node off the shelf.
/** @param {Element} node */
function standsFor(node) {
  const owner = noteOf(node);
  return owner && (owner.standsFor(node) ?? owner.element);
}
declareSide(standsFor);

// The element the proxy ring stands round, null while it stands nowhere.
/** @type {Element | null} */
let ringed = null;
// Ring what the focused node on the shelf stands for, or nothing where focus is off
// it. Asked on each focus move and each shelving, which is where what a focused note
// stands for can change.
function ring() {
  const node = focused();
  const target = node && noteOf(node)?.presents ? standsFor(node) : null;
  if (target === ringed && (!target || target.isConnected)) return;
  ringed = target;
  const part = target && visualAt(target, { unclaimed: false })?.part;
  paintProxyRing(target, part?.element === target ? part.surface : target);
}
onCurrentLocation((node) => {
  if (node && noteOf(node)?.presents && standsFor(node)) {
    reveal(standsFor(node), retainUserIntent());
    // What the reveal opened may have drawn the target anew.
    scrollIntoView(standsFor(node), { behavior: "instant", block: "nearest" });
  }
  ring();
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
// on every pass that finds the note still owed. `standsFor` reads what a node in the
// note stands for where that is not `element` itself, and `presents: false` leaves
// showing that place on focus to the note's owner. A note shelved under another element
// moves to it, keeping its node, so a user on it stays there.
/** @param {Element} element @param {Element} note @param {StandsFor} [standsFor] */
export function shelve(
  element,
  note,
  standsFor = () => null,
  { presents = true } = {},
) {
  shelf ??= offer("div", "lf-details-shelf");
  if (!shelf.isConnected) chromeRoot.append(shelf);
  if (note.parentNode !== shelf) move(shelf, note, null);
  const before = owners.get(note)?.element;
  if (before && before !== element) forget(before, note);
  owners.set(note, { element, standsFor, presents });
  let record = records.get(element);
  if (!record) {
    record = { notes: [], authored: null };
    records.set(element, record);
  }
  if (!record.notes.includes(note)) record.notes.push(note);
  name(element, record);
  ring();
}

// Take `note` off the shelf and out of `element`'s relation.
/** @param {Element} element @param {Element} note */
export function unshelve(element, note) {
  forget(element, note);
  note.remove();
  owners.delete(note);
}

// Take `note` out of `element`'s relation. The element's authored `aria-details` comes
// back with its last note.
/** @param {Element} element @param {Element} note */
function forget(element, note) {
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
}
