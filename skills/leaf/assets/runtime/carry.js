/* Mechanical user state carried across a live document replacement.
 *
 * Capture matches live elements to the outgoing authored source by id and tag. Restore
 * matches those identities in the arriving document and skips nodes the patch retained.
 * Unnamed elements, generated ids absent from the source, and changed tags carry nothing.
 *
 * Values, checked state, and disclosure state cross only when they differ from the
 * outgoing authored node. Read both nodes through the same platform properties: reflected
 * attributes and defaultValue do not provide a consistent baseline for these controls.
 * Nonzero inner scroll offsets, focus, and the focused control's caret also cross,
 * except a reading region's body: where that scrolls to is the region continuity's,
 * which lands it on a passage rather than on a pixel offset the revision has moved.
 * Restoring this state creates no event and leaves draft values unsent.
 *
 * Value capture supports text boxes (`TEXT_BOX`) and non-file inputs; checked state supports checkbox
 * and radio inputs. Select values, contenteditable markup, and file-input values are
 * excluded.
 * Modules restore their own stored state, such as tabs and drafts, through their own
 * lifecycles. `version.js` owns when capture and restoration run for each install.
 */
import { TEXT_BOX, focusDestination, readCaret } from "./focus.js";
import { readingRegions } from "./reading-regions.js";

const holdsValue = (node) =>
  node.matches(TEXT_BOX) || (node.tagName === "INPUT" && node.type !== "file");
const holdsTick = (node) =>
  node.tagName === "INPUT" && (node.type === "checkbox" || node.type === "radio");

// Capture before replacement. JSON records can cross a reload; held nodes remain local
// so an in-place install can skip restoration on the nodes it kept.
export function captureCarry(root, authored) {
  const active = document.activeElement;
  const records = [];
  const held = new Map();
  const regionBodies = new Set(readingRegions().map(({ body }) => body));
  for (const node of root.querySelectorAll("[id]")) {
    const wrote = authored.querySelector(`#${CSS.escape(node.id)}`);
    if (wrote?.localName !== node.localName) continue;
    const record = { id: node.id, name: node.localName };
    if (node === active) record.focus = true;
    if (node.localName === "details" && node.open !== wrote.open)
      record.open = node.open;
    if (!regionBodies.has(node)) {
      if (node.scrollTop) record.scrollTop = node.scrollTop;
      if (node.scrollLeft) record.scrollLeft = node.scrollLeft;
    }
    if (holdsValue(node) && node.value !== wrote.value) record.value = node.value;
    if (holdsTick(node) && node.checked !== wrote.checked)
      record.checked = node.checked;
    if (node === active) {
      const caret = readCaret(node);
      if (caret) record.caret = caret;
    }
    // Omit identity-only records with no mechanical state to restore.
    if (Object.keys(record).length === 2) continue;
    records.push(record);
    held.set(record.id, node);
  }
  return { records, held };
}

// Restore values, disclosures, focus and caret in the turn that replaces their nodes,
// so the user can keep typing while renderers settle. Only scroll needs the finished
// layout; the returned correction runs while the install still owns navigation.
// Kept nodes never lost their state, and a changed tag is a different control.
export function restoreCarry(
  records,
  held = new Map(),
  handoffFocus = (move) => move(),
) {
  const positions = [];
  for (const record of records ?? []) {
    const arrived = document.getElementById(record.id);
    if (!arrived || arrived === held.get(record.id)) continue;
    if (arrived.localName !== record.name) continue;
    if (record.open !== undefined) arrived.open = record.open;
    if (record.value !== undefined && holdsValue(arrived)) arrived.value = record.value;
    if (record.checked !== undefined && holdsTick(arrived))
      arrived.checked = record.checked;
    positions.push([arrived, record]);
  }
  // Values and disclosures are owed even when a connected widget took focus during
  // replacement. Only focus yields to that newer owner; its handoff keeps the same
  // input generation and adopts the synchronous transfer when still permitted.
  handoffFocus(() => {
    for (const [arrived, record] of positions)
      if (record.focus) focusDestination(arrived, record.caret);
  });
  return () => {
    for (const [arrived, record] of positions) {
      if (!arrived.isConnected) continue;
      if (record.scrollTop) arrived.scrollTop = record.scrollTop;
      if (record.scrollLeft) arrived.scrollLeft = record.scrollLeft;
    }
  };
}
