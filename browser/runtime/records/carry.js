/* Mechanical user state carried across a live document replacement.
 *
 * Capture matches live elements to the outgoing authored source by id and tag. Restore
 * matches those identities in the arriving document and skips nodes the patch retained,
 * which keep their state, except a select: it holds its choice in its options, which
 * the patch may rebuild, so a retained select takes its choice back.
 * Generated controls may name a stable `data-lf-carry` key inside their nearest
 * named owner, which must itself match authored markup by id and tag. Another named
 * wrapper establishes a different scope, never skipped. A control in the shadow root
 * its widget draws into has the widget as its owner (`partOwner`), as one in the
 * widget's own tree does. Only focus and caret cross: their widget owns their values
 * and drawing. Other unnamed elements and changed tags carry nothing.
 *
 * A control's state (`state`) crosses only where it differs from the outgoing authored
 * node's. Read both nodes through the same platform properties: reflected attributes
 * and defaultValue do not provide a consistent baseline for these controls.
 * Nonzero inner scroll offsets, focus, and the focused control's caret also cross,
 * except a reading region body's vertical offset: where that scrolls to is the region
 * continuity's, which lands it on a passage rather than on a pixel offset the revision
 * has moved. Continuity keeps no sideways place, so a region's sideways offset crosses
 * here like any other box's. A box in skipped content (a tab not chosen, a closed
 * disclosure) carries no offset at all: reading one would make the browser style and
 * lay out all of that content first (`skipped`, lib/shadow-tree.js), a pass per hidden panel
 * on every revision.
 * Restoring this state creates no event and leaves draft values unsent.
 *
 * Which state a control carries, and how it goes back, is base/document-inputs.js's
 * (`controlState`, `putControlState`): contenteditable markup and file-input values
 * carry none.
 * Modules restore their own stored state, such as tabs and drafts, through their own
 * lifecycles. `features/version.js` owns when capture and restoration run for each install,
 * and which records a reload's arrival restores (`installArrival`).
 *
 * Focus is named by identity a reload keeps (`focusKey`), which history's record of an
 * entry uses too (history.js): a page element by the id and tag above, or by its
 * owner's and its `data-lf-carry` key; or a part of a drawn thread by the thread's id,
 * its reply or a message by the message it draws, or the drawing itself; with the
 * caret. Inside a message, as on the page, a name comes first: an element by its id,
 * which focus in its shadow tree counts as on it, and a generated control by its
 * owner's id and its key. An element nothing names is named by its place among the
 * elements like it (dom/focus.js, `likeSelector`) in the nearest holder something names,
 * the message or the page. That place names it only where the holder is drawn from the
 * same words: a message, whose words are the log's, or the page in the revision the key
 * was read in. A revision's handoff of page elements takes no such place, since it
 * names nothing the arriving revision must hold; the floating panel's and the margin's
 * handoffs of a thread view take a thread key whole (panel/floating-panel.js,
 * margin-projection.js, `captureCurrentLocation`).
 */
import { setScroll } from "../dom/arrivals.js";
import { focusDestination, likeSelector, readCaret, focused } from "../dom/focus.js";
import { inputs } from "../base/inputs.js";
import {
  closestAcross,
  hostIn,
  renderedUnder,
  skipped,
  upFrom,
} from "../lib/shadow-tree.js";
import { readingRegions } from "../readings/reading-regions.js";
import { elementById, inPage, pageDocument } from "../readings/passages.js";
import { ADDRESSABLE } from "../readings/anchor-resolution.js";
import { runtime } from "../state/context.js";
import { drawnThreadId, THREAD, threadPart, wholeThread } from "./thread/selectors.js";

// The named element a generated control's key is unique within: the nearest above it,
// out through the shadow root a widget draws into, where the page's own tree holds only
// the host.
/** @param {Element} part */
const partOwner = (part) => closestAcross(upFrom(part), "[id]");

const { controlState, putControlState } = inputs;

// A key names a page element by `id` and `name`, its tag, with `part` and `partName`
// for a generated control's `data-lf-carry` key and tag; or a part of a thread by
// `thread`, the thread's id, and `on`: its reply, a message (`message`), or its
// drawing. `at` is an unnamed element's place in its holder, and `revision` the page's
// as the key was read, which a place in the page needs (the header).
/** @typedef {{id?: string, name?: string, part?: string, partName?: string,
 * thread?: string, on?: "thread" | "message" | "reply", message?: string,
 * at?: [like: string, nth: number], revision?: number | null,
 * caret?: import("../base/held-place.js").Caret}} FocusKey */
// How `active` is named inside `holder`, a message or the page, names first: a generated
// control by its named owner's id and its `data-lf-carry` key and tag; the element
// focus is on, or whose shadow tree holds it, by its id; else its place among the
// elements like it in the nearest element with an id inside the holder, or the holder.
/** @param {Element} holder @param {Element} active @returns {FocusKey} */
export function nameIn(holder, active) {
  const page = holder === pageDocument();
  /** @param {Element | null | undefined} node @returns {node is Element} */
  const inside = (node) =>
    Boolean(node && node !== holder && renderedUnder(node, holder)) &&
    (!page || inPage(/** @type {Element} */ (node)));
  const part = active.getAttribute("data-lf-carry");
  const owner = part === null ? null : partOwner(active);
  if (part !== null && inside(owner))
    return { id: owner.id, name: owner.localName, part, partName: active.localName };
  const found = closestAcross(active, ADDRESSABLE);
  const named = inside(found) ? found : null;
  const root = named ?? holder;
  const standIn = hostIn(active, root.getRootNode()) ?? active;
  if (named && standIn === named) return { id: named.id, name: named.localName };
  const like = likeSelector(standIn);
  const nth = [...root.querySelectorAll(like)].indexOf(standIn);
  return {
    ...(named && { id: named.id, name: named.localName }),
    ...(nth >= 0 && { at: /** @type {[string, number]} */ ([like, nth]) }),
  };
}
/** @param {Element | null} active @returns {FocusKey | null} */
export function focusKey(active) {
  if (!active || active === document.body) return null;
  const caret = readCaret(active);
  /** @param {FocusKey} key @returns {FocusKey} */
  const withCaret = (key) => (caret ? { ...key, caret } : key);
  const drawing = closestAcross(active, THREAD);
  const whole = drawing && wholeThread(drawing);
  const thread = drawnThreadId(whole);
  if (whole && thread) {
    const reply = threadPart(whole, "reply");
    if (reply && renderedUnder(active, reply))
      return withCaret({ thread, on: "reply" });
    const turn = closestAcross(active, "[data-lf-message]");
    const message =
      turn && renderedUnder(turn, whole) ? turn.getAttribute("data-lf-message") : null;
    // A control a view of the thread draws as its own, as Close or Resolve on its head
    // line, by the key it declares (`data-lf-carry`).
    if (!turn || !message) {
      const part = active.getAttribute("data-lf-carry");
      return withCaret({ thread, on: "thread", ...(part !== null && { part }) });
    }
    const named = turn === active ? {} : nameIn(turn, active);
    return withCaret({ thread, on: "message", message, ...named });
  }
  if (!inPage(active)) return null;
  const key = nameIn(pageDocument(), active);
  return withCaret(key.at ? { ...key, revision: runtime.currentRevision } : key);
}

// The element a focus key names now, or null: a thread's part in the drawing of the
// thread `drawing` finds, its reply, else in the message the key names, or in the
// drawing where the key names none, the element named there, else at its place there,
// else the message, else the drawing; a page
// element by its id or its owner's key, else at its place in its holder while the page
// shows the key's revision, else that holder.
/** @param {FocusKey} key @param {(thread: string) => Element | null} drawing @returns {Element | null} */
function focusedBy(key, drawing) {
  if (key.thread) {
    const whole = drawing(key.thread);
    if (!whole) return null;
    const reply = key.on === "reply" ? threadPart(whole, "reply") : null;
    if (reply) return reply;
    if (key.on === "thread")
      return (
        (key.part !== undefined &&
          threadPart(whole, "controls")?.querySelector(
            `[data-lf-carry="${CSS.escape(key.part)}"]`,
          )) ||
        whole
      );
    const turn = key.message
      ? whole.querySelector(`[data-lf-message="${CSS.escape(key.message)}"]`)
      : null;
    if (key.message && !turn) return whole;
    return namedIn(turn ?? whole, key);
  }
  const page = pageDocument();
  const owner = key.id ? elementById(key.id, page) : page;
  if (!owner || (key.name && owner.localName !== key.name)) return null;
  if (key.part !== undefined) return keyedFocus(owner, key);
  const placed = key.revision === runtime.currentRevision;
  const target =
    (placed && key.at && owner.querySelectorAll(key.at[0])[key.at[1]]) || owner;
  return target === page ? null : target;
}

// The element `key` names inside `holder` (`nameIn`), as a message or a draft's box:
// the element with its id, or its owner's generated control, else at its place, else
// the holder; a place inside a holder that isn't the page stays valid across
// revisions.
/** @param {Element} holder @param {FocusKey} key @returns {Element | null} */
export function namedIn(holder, key) {
  const owner = key.id ? holder.querySelector(`[id="${CSS.escape(key.id)}"]`) : holder;
  if (!owner || (key.name && owner.localName !== key.name)) return holder;
  if (key.part !== undefined) return keyedFocus(owner, key);
  return (key.at && owner.querySelectorAll(key.at[0])[key.at[1]]) || owner;
}

// Returns the user to what `key` names (`focusedBy`), with the caret it kept, where
// `accept` takes the element; answers the element, or null where nothing took focus.
/** @param {FocusKey} key @param {(thread: string) => Element | null} drawing
 * @param {(target: Element) => boolean} [accept] @returns {Element | null} */
export function focusByKey(key, drawing, accept = () => true) {
  const target = focusedBy(key, drawing);
  if (!target || !accept(target)) return null;
  focusDestination(target, "return", { caret: key.caret ?? null });
  return target;
}

// The element a page key names under `owner`, the element with its id: the owner, or
// the generated control of its key and tag whose nearest named owner it is, in the
// owner's own tree or in its shadow root.
/** @param {Element} owner @param {{part?: string, partName?: string}} key */
function keyedFocus(owner, { part, partName }) {
  if (part === undefined) return owner;
  const keyed = `[data-lf-carry="${CSS.escape(part)}"]`;
  return (
    [owner, owner.shadowRoot]
      .flatMap((tree) => [...(tree?.querySelectorAll(keyed) ?? [])])
      .find((node) => node.localName === partName && partOwner(node) === owner) ?? null
  );
}

// Capture before replacement. JSON records can cross a reload; held nodes remain local
// so an in-place install can skip restoration on the nodes it kept. Only a key naming
// an element by its id or its owner's key carries focus here (the header).
/** @typedef {{id: string, name: string, state?: ControlState, focus?: boolean, part?: string, partName?: string, scrollTop?: number, scrollLeft?: number, caret?: import("../base/held-place.js").Caret}} CarryRecord */
/** @param {ParentNode} root @param {ParentNode} authored */
export function captureCarry(root, authored) {
  // The focused control in whichever tree holds it, a widget's shadow root included.
  const key = focusKey(focused());
  const focus = key?.id && !key.at && !key.thread ? key : null;
  const records = [];
  const held = new Map();
  const regionBodies = new Set(readingRegions().map(({ body }) => body));
  for (const node of root.querySelectorAll("[id]")) {
    if (!inPage(node)) continue;
    const wrote = authored.querySelector(`#${CSS.escape(node.id)}`);
    if (wrote?.localName !== node.localName) continue;
    /** @type {CarryRecord} */
    const record = { id: node.id, name: node.localName };
    if (focus?.id === node.id && focus.name === node.localName)
      Object.assign(record, focus, { focus: true });
    const state = controlState(node);
    if (state && JSON.stringify(state) !== JSON.stringify(controlState(wrote)))
      record.state = state;
    if (!skipped(node)) {
      if (node.scrollTop && !regionBodies.has(node)) record.scrollTop = node.scrollTop;
      if (node.scrollLeft) record.scrollLeft = node.scrollLeft;
    }
    // Omit identity-only records with no mechanical state to restore.
    if (Object.keys(record).length === 2) continue;
    records.push(record);
    held.set(record.id, node);
  }
  return { records, held };
}

// What records carry of the document itself, the state of its controls, which a Back
// within one document keeps too, without where the user was in it, focus, caret and
// scroll offsets, which belong to the entry the records were read on
// (features/version.js, `installArrival`).
/** @param {readonly CarryRecord[] | null | undefined} records @returns {CarryRecord[]} */
export const documentState = (records) =>
  (records ?? []).map(({ id, name, state }) => ({ id, name, ...(state && { state }) }));

// Restore authored values, disclosures, focus and caret in the replacement turn, so
// typing continues while renderers settle. Generated controls become visible after
// upgrade: their focus joins scroll in the returned post-layout correction, which
// runs while the install still owns navigation.
// A kept node keeps its state, apart from a select's choice (the header), and a
// changed tag is a different control.
/** @param {readonly CarryRecord[] | null | undefined} records
 * @param {ReadonlyMap<string, Element>} [held]
 * @param {(move: () => void) => unknown} [handoffFocus] */
export function restoreCarry(
  records,
  held = new Map(),
  handoffFocus = (move) => move(),
) {
  /** @type {{arrived: Element, record: CarryRecord}[]} */
  const positions = [];
  for (const record of records ?? []) {
    const arrived = elementById(record.id, pageDocument());
    if (!arrived || arrived.localName !== record.name) continue;
    const kept = arrived === held.get(record.id);
    if (record.state && (!kept || arrived instanceof HTMLSelectElement))
      putControlState(arrived, record.state);
    if (!kept) positions.push({ arrived, record });
  }
  // Values and disclosures are owed even when a connected widget took focus during
  // replacement. Only focus yields to that newer owner; its handoff keeps the same
  // input generation and adopts the synchronous transfer when still permitted.
  /** @param {boolean} parts */
  const restoreFocus = (parts) =>
    handoffFocus(() => {
      for (const { arrived, record } of positions) {
        if (!record.focus || (record.part !== undefined) !== parts) continue;
        const target = keyedFocus(arrived, record);
        if (target)
          focusDestination(
            target,
            "return",
            record.caret ? { caret: record.caret } : {},
          );
      }
    });
  restoreFocus(false);
  return () => {
    for (const { arrived, record } of positions) {
      if (!arrived.isConnected) continue;
      if (record.scrollTop || record.scrollLeft)
        setScroll(arrived, {
          top: record.scrollTop || arrived.scrollTop,
          left: record.scrollLeft || arrived.scrollLeft,
        });
    }
    // Initial generated controls have boxes but stay hidden until upgrade
    // (base.css). Their focus joins the post-layout correction; authored fields
    // already took focus above so typing can continue while presentation is held.
    restoreFocus(true);
  };
}
