/* Mechanical user state carried across a live document replacement.
 *
 * Capture matches live elements to the outgoing authored source by id and tag. Restore
 * matches those identities in the arriving document and skips nodes the patch retained.
 * Generated controls may name a stable `data-lf-carry` key inside their nearest
 * named owner, which must itself match authored markup by id and tag. Another named
 * wrapper establishes a different scope, never skipped. Only focus and caret cross: their widget
 * owns their values and drawing. Other unnamed elements and changed tags carry nothing.
 *
 * Values, checked state, and disclosure state cross only when they differ from the
 * outgoing authored node. Read both nodes through the same platform properties: reflected
 * attributes and defaultValue do not provide a consistent baseline for these controls.
 * Nonzero inner scroll offsets, focus, and the focused control's caret also cross,
 * except a reading region body's vertical offset: where that scrolls to is the region
 * continuity's, which lands it on a passage rather than on a pixel offset the revision
 * has moved. Continuity keeps no sideways place, so a region's sideways offset crosses
 * here like any other box's. A box in skipped content (a tab not chosen, a closed
 * disclosure) carries no offset at all: reading one would make the browser style and
 * lay out all of that content first (`skipped`, geometry.js), a pass per hidden panel
 * on every revision.
 * Restoring this state creates no event and leaves draft values unsent.
 *
 * Value capture supports text boxes (`TEXT_BOX`) and non-file inputs; checked state supports checkbox
 * and radio inputs. Select values, contenteditable markup, and file-input values are
 * excluded.
 * Modules restore their own stored state, such as tabs and drafts, through their own
 * lifecycles. `version.js` owns when capture and restoration run for each install.
 */
import { focusDestination, readCaret } from "./focus.js";
import { TEXT_BOX } from "./control-selectors.js";
import { skipped } from "./geometry.js";
import { readingRegions } from "./reading-regions.js";

const holdsValue = (node) =>
  node.matches(TEXT_BOX) || (node.tagName === "INPUT" && node.type !== "file");
const holdsTick = (node) =>
  node.tagName === "INPUT" && (node.type === "checkbox" || node.type === "radio");

// Capture before replacement. JSON records can cross a reload; held nodes remain local
// so an in-place install can skip restoration on the nodes it kept.
export function captureCarry(root, authored) {
  const active = document.activeElement;
  const partOwner = active?.hasAttribute("data-lf-carry")
    ? active.parentElement?.closest("[id]")
    : null;
  const records = [];
  const held = new Map();
  const regionBodies = new Set(readingRegions().map(({ body }) => body));
  for (const node of root.querySelectorAll("[id]")) {
    const wrote = authored.querySelector(`#${CSS.escape(node.id)}`);
    if (wrote?.localName !== node.localName) continue;
    const record = { id: node.id, name: node.localName };
    const focusPart = node === partOwner;
    if (node === active || focusPart) {
      record.focus = true;
      if (focusPart) {
        record.part = active.getAttribute("data-lf-carry");
        record.partName = active.localName;
      }
    }
    if (node.localName === "details" && node.open !== wrote.open)
      record.open = node.open;
    if (!skipped(node)) {
      if (node.scrollTop && !regionBodies.has(node)) record.scrollTop = node.scrollTop;
      if (node.scrollLeft) record.scrollLeft = node.scrollLeft;
    }
    if (holdsValue(node) && node.value !== wrote.value) record.value = node.value;
    if (holdsTick(node) && node.checked !== wrote.checked)
      record.checked = node.checked;
    if (node === active || focusPart) {
      const caret = readCaret(active);
      if (caret) record.caret = caret;
    }
    // Omit identity-only records with no mechanical state to restore.
    if (Object.keys(record).length === 2) continue;
    records.push(record);
    held.set(record.id, node);
  }
  return { records, held };
}

// Restore authored values, disclosures, focus and caret in the replacement turn, so
// typing continues while renderers settle. Generated controls become visible after
// upgrade: their focus joins scroll in the returned post-layout correction, which
// runs while the install still owns navigation.
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
  const restoreFocus = (parts) =>
    handoffFocus(() => {
      for (const [arrived, record] of positions) {
        if (!record.focus || (record.part !== undefined) !== parts) continue;
        const target =
          record.part === undefined
            ? arrived
            : [
                ...arrived.querySelectorAll(
                  `[data-lf-carry="${CSS.escape(record.part)}"]`,
                ),
              ].find(
                (node) =>
                  node.parentElement?.closest("[id]") === arrived &&
                  node.localName === record.partName,
              );
        if (target) focusDestination(target, "return", { caret: record.caret });
      }
    });
  restoreFocus(false);
  return () => {
    for (const [arrived, record] of positions) {
      if (!arrived.isConnected) continue;
      if (record.scrollTop) arrived.scrollTop = record.scrollTop;
      if (record.scrollLeft) arrived.scrollLeft = record.scrollLeft;
    }
    // Initial generated controls have boxes but stay hidden until upgrade
    // (theme.css). Their focus joins the post-layout correction; authored fields
    // already took focus above so typing can continue while presentation is held.
    restoreFocus(true);
  };
}
