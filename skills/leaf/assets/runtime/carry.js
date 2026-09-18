/* Mechanical reader state carried across a document replacement.
 *
 * An install replaces the nodes a revision rewrote, and a widget goes whole because a
 * controller owns its children once it is connected. Everything the reader had put into
 * those nodes goes with them: words half typed into a field, the caret inside them, a
 * box they had opened, how far they had scrolled inside one, and the focus that says
 * where they are. None of it is in the event log, so no projection can put it back, and
 * a reader whose page was rewritten under them had simply lost it.
 *
 * What makes it recoverable is the authored id. That is the identity `patchTree` matches
 * nodes on first, that threads, the version diff, `restated`, the tab store and the draft
 * store already key on, and that a version check refuses to let a revision quietly drop.
 * An element keeping its id through a revision is the same element as far as the page is
 * concerned, whatever the patch had to do to its node. That is the whole warrant here:
 * this carries state between two nodes the author named the same thing. An element with
 * no id carries nothing, which is the honest answer — version.js's header says why a
 * shape is not an identity, and this module is what that header's exception is made of.
 *
 * Mechanical, not semantic. None of this is a decision: a reader's answer reaches the log
 * as an event and comes back through the projection, while what is here is the state of
 * the apparatus they were reaching for it with. So a carry never creates a gesture, and a
 * value it puts back is exactly as unsent as it was before.
 *
 * Reader-changed state only, and what the reader changed is what the live node no longer
 * agrees with the author about. A field answers that itself: `defaultValue` and
 * `defaultChecked` are what the author wrote, so a field still matching one holds nothing
 * of the reader's, and the arriving revision's text is the better answer. A disclosure
 * answers nothing — `open` reflects, so the attribute moves with the reader — and the
 * baseline comes instead from the authored markup of the revision the reader is standing
 * in. That is the same `before` side `dom-children.js` diffs against, and for the same
 * reason it gives there: the live page differs from the author in everything the reader,
 * the runtime and every module have done to it since it loaded, so the page is never one
 * side of this comparison. Read the live box alone and a box the reader never touched is
 * carried over the arriving revision that opened it, which arrives shut.
 *
 * The baseline is also what the authored id means here. An id the outgoing source does
 * not carry was made by a module rather than by the author, and what a module makes is
 * the module's to put back from its own store; this carries nothing for it.
 *
 * Deliberately not carried: a `<select>`, whose authored default is an attribute on one
 * of its options rather than a property of the control, and a `contenteditable`, whose
 * value is markup and therefore the document's rather than the apparatus's. Neither has
 * a surface in Leaf today. State a module keeps for itself — the tab store's selection,
 * the draft store's words — is already restored by that module reading its own store back
 * under the same id, and does not belong here.
 */
import { focusDestination, readCaret } from "./focus.js";

const holdsWords = (node) =>
  (node.tagName === "TEXTAREA" || node.tagName === "INPUT") && !node.isContentEditable;
const holdsTick = (node) =>
  node.tagName === "INPUT" && (node.type === "checkbox" || node.type === "radio");

// Read the reader's state off the standing document, before the patch takes its nodes
// away, against `authored` — the inert authored `main` of the revision the reader is
// standing in. The records are plain JSON because the other install has to put them in a
// store and open a new document with them; the nodes they came from stay here, in a map
// the in-place install uses to tell a replaced node from one the patch kept.
export function captureCarry(root, authored) {
  const active = document.activeElement;
  const records = [];
  const held = new Map();
  for (const node of root.querySelectorAll("[id]")) {
    const wrote = authored.querySelector(`#${CSS.escape(node.id)}`);
    if (!wrote) continue;
    const record = { id: node.id, name: node.localName };
    if (node === active) record.focus = true;
    if (node.localName === "details" && node.open !== wrote.hasAttribute("open"))
      record.open = node.open;
    if (node.scrollTop) record.scrollTop = node.scrollTop;
    if (node.scrollLeft) record.scrollLeft = node.scrollLeft;
    if (holdsWords(node) && node.value !== node.defaultValue) record.value = node.value;
    if (holdsTick(node) && node.checked !== node.defaultChecked)
      record.checked = node.checked;
    if (node === active) {
      const caret = readCaret(node);
      if (caret) record.caret = caret;
    }
    // Two keys is the id and its tag, which is a record of nothing.
    if (Object.keys(record).length === 2) continue;
    records.push(record);
    held.set(record.id, node);
  }
  return { records, held };
}

// Put it back, once the arriving document has been upgraded and presented.
//
// Only onto a node the install actually replaced. One the patch kept never lost any of
// this, and writing over it would undo whatever the reader has done since — `held` is how
// the in-place install says which is which, and the other install passes none, because a
// fresh document kept nothing. An id the revision dropped, or gave to a different kind of
// element, is not the same element and keeps nothing.
export function restoreCarry(records, held = new Map()) {
  for (const record of records ?? []) {
    const arrived = document.getElementById(record.id);
    if (!arrived || arrived === held.get(record.id)) continue;
    if (arrived.localName !== record.name) continue;
    if (record.open !== undefined) arrived.open = record.open;
    if (record.value !== undefined && holdsWords(arrived)) arrived.value = record.value;
    if (record.checked !== undefined && holdsTick(arrived))
      arrived.checked = record.checked;
    if (record.scrollTop) arrived.scrollTop = record.scrollTop;
    if (record.scrollLeft) arrived.scrollLeft = record.scrollLeft;
    if (!record.focus) continue;
    // The element may have been focusable only through a tab stop the runtime lent it,
    // which the arriving node has not been lent; `focusDestination` lends it again for
    // as long as the reader holds it, and puts the caret back in the same act.
    focusDestination(arrived, record.caret);
  }
}
