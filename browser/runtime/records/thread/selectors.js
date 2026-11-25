/* Stable DOM relations shared by thread views and focus recovery. */
import { upFrom, closestAcross } from "../../lib/shadow-tree.js";
import { TEXT_FIELD } from "../../dom/control-selectors.js";
// A drawn thread: a thread on the page, in the margin or on a seat, or a chrome's view
// of one thread (`data-lf-thread-view`, as the floating panel's thread view and its head
// are), whose reply and Resolve the presentation draws outside it and declares on it
// (`threadPart`, below). Each names its thread's id in `data-lf-thread`, so focus
// anywhere in one stands in that thread for every reading of it, `c` included.
export const THREAD = ".lf-page-thread, [data-lf-thread-view]";
// The logged id a drawn thread carries. Each reader of the id takes it from here.
/** @param {Element | null | undefined} node */
export const drawnThreadId = (node) => node?.getAttribute("data-lf-thread") ?? null;
// The page threads drawn under `root` that carry the logged id `id`, in tree order.
/** @param {ParentNode} root @param {string} id */
export const drawnThreadsWithId = (root, id) =>
  root.querySelectorAll(`.lf-page-thread[data-lf-thread="${CSS.escape(id)}"]`);
// The row a drawn thread's reply is written in, and the box in it.
export const SAY_ROW = ".lf-thread-reply";
export const SAY_BOX = `:scope > ${SAY_ROW} ${TEXT_FIELD}`;

// A drawn thread's own parts: the box its reply is written in, the control that settles
// it, whose `lf-resolve` or `lf-reopen` says which way, and the press that moves it to
// Leaf's other place for it (`lf-thread-move`): a card's Open in panel, or the floating
// panel's Show on page (threads-in-panel.js). A card draws all three inside itself. A
// presentation that draws one elsewhere, as the floating panel draws the reply as its
// field and Resolve and Show on page on its view's head line, declares on the thread
// element where each stands (`declareThreadParts`): `reply`, `settlement` and `move`,
// each a function of that element answering the part, or null while the thread has none
// there. Every reading of a thread's parts goes through here (`threadPart`), so Enter,
// `r`, `p` and `c` answer alike whichever chrome draws the thread. A thread drawn within one that
// declares, as the thread the panel's view holds, its reply and Resolve drawn on the
// panel's own lines, has the enclosing drawing's parts where it holds none
// (`drawingsOf`).
//
// Such a presentation also declares `whole`, the element standing for the thread as a
// whole where its pieces stand apart, as the panel's view does for its head and its
// field (`wholeThread`), and `controls`, the element holding the controls it draws for
// the thread as its own, as the panel's head holds Close, which focus's identity finds
// by their keys (records/carry.js, `focusedBy`).
/** @typedef {{
 * reply: (thread: Element) => Element | null,
 * settlement: (thread: Element) => HTMLElement | null,
 * move: (thread: Element) => HTMLElement | null,
 * whole: (thread: Element) => Element | null,
 * controls: (thread: Element) => Element | null,
 * }} ThreadParts */
/** @type {WeakMap<Element, ThreadParts>} */
const declaredParts = new WeakMap();
/** @param {Element} thread @param {ThreadParts} parts */
export const declareThreadParts = (thread, parts) => declaredParts.set(thread, parts);
// The control `selector` names that is `thread`'s own, not a thread's inside it.
/** @param {Element} thread @param {string} selector */
const ownControl = (thread, selector) => {
  /** @type {NodeListOf<HTMLElement>} */
  const controls = thread.querySelectorAll(selector);
  return [...controls].find((control) => control.closest(THREAD) === thread) ?? null;
};
/** @type {Pick<ThreadParts, "reply" | "settlement" | "move" | "controls">} */
const ownParts = {
  reply: (thread) => thread.querySelector(SAY_BOX),
  controls: (thread) => thread,
  settlement: (thread) => ownControl(thread, ".lf-resolve, .lf-reopen"),
  move: (thread) => ownControl(thread, ".lf-thread-move"),
};
// The drawings of one thread from `thread` outward: itself, then each drawing of the
// same thread around it.
/** @param {Element} thread @returns {Generator<Element>} */
function* drawingsOf(thread) {
  const id = drawnThreadId(thread);
  /** @type {Element | null} */
  let at = thread;
  for (
    ;
    at === thread || (at && id && drawnThreadId(at) === id);
    at = closestAcross(upFrom(at), THREAD)
  )
    yield at;
}
// The whole of the thread drawn at `thread`: its outermost drawing, or the element that
// drawing declares as the whole. It holds the thread's messages, so a reading of them
// searches it, and it is the thread a keyboard stands on, as a reply box's way back.
/** @param {Element} thread */
export function wholeThread(thread) {
  let outer = thread;
  for (const drawing of drawingsOf(thread)) outer = drawing;
  return declaredParts.get(outer)?.whole(outer) ?? outer;
}
/** @overload @param {Element} thread @param {"settlement" | "move"} name @returns {HTMLElement | null} */
/** @overload @param {Element} thread @param {"reply" | "controls"} name @returns {Element | null} */
/** @param {Element} thread @param {"reply" | "settlement" | "move" | "controls"} name */
export function threadPart(thread, name) {
  for (const at of drawingsOf(thread)) {
    const part = (declaredParts.get(at) ?? ownParts)[name](at);
    if (part) return part;
  }
  return null;
}
