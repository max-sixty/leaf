import {
  USER_VIEW_RESTORE_CASES,
  scrolling,
  exceptionText,
  upFrom,
} from "/runtime/check-api.js";
import { readThreads, threadActions } from "/runtime/widget-api.js";
import { at } from "./locate.js";
import { openRoots } from "./open-roots.js";

// Work the page holds back until the reader nears its node, such as each live
// sample's page, started at once (`start_near_work`).
export { startNearWork } from "/runtime/check-api.js";

// The runtime has started once its chrome, the floating panel, is in the page.
export const runtimeStarted = () =>
  document.querySelector(".lf-floating-panel") !== null;
export const upgraded = () => document.body.dataset.lfUpgraded === "1";

// Finite animations delay final geometry reads. Infinite ambient animation, such as the
// status indicator, does not. `finiteMotion` is the render gate's shared reading of that
// boundary. A component that animates forever must not appear in it; a state transition
// that can still change boxes must. One on an element the page doesn't render changes
// no box, and Firefox never starts it: a colour transition the scheme starts on a
// control inside a closed `<details>` stays pending until the details open. A
// scroll-driven animation, such as the contents map's lens or a margin card's message
// heads, moves only while something scrolls, which `scrolling` reads, and a paused one
// isn't running, so neither is in it. Only an animation on a document timeline runs
// on the clock: Firefox 159 gave a message head's view-timeline animation a finite end
// (30769 ms on 2026-11-11), where Chromium gives a percentage.
const finiteMotion = () =>
  openRoots(document)
    .flatMap((root) => root.getAnimations())
    .filter((animation) => {
      const effect = animation.effect;
      if (
        animation.playState !== "running" ||
        !(animation.timeline instanceof DocumentTimeline) ||
        !Number.isFinite(effect?.getComputedTiming().endTime)
      )
        return false;
      const target = effect instanceof KeyframeEffect ? effect.target : null;
      return target?.checkVisibility() !== false;
    });

export const moving = () =>
  finiteMotion().map((animation) => {
    const effect = animation.effect;
    const target = effect instanceof KeyframeEffect ? effect.target : null;
    const name = animation instanceof CSSAnimation ? animation.animationName : "";
    return name ? `${at(target)} ${name}` : at(target);
  });

// A resize can set the page moving where a load at that size would not: a value the
// new width's rules change eases from the value the old width set. A load's reading
// waits its motion out (`pageSettled`); the gate's sweep finishes what a resize started
// instead, which ends on the same page, and says how many it finished.
export function finishMoving() {
  const motion = finiteMotion();
  for (const animation of motion) animation.finish();
  return motion.length;
}

// Whether the motion `finiteMotion` reads has ended within each element a selector
// names, shadow trees included; a selector naming nothing reads as at rest. A test reads
// one surface's geometry once that surface rests, while motion elsewhere runs on.
export const restingIn = (/** @type {string[]} */ ...selectors) => {
  const roots = selectors.flatMap((selector) => document.querySelector(selector) ?? []);
  return !finiteMotion().some((animation) => {
    const effect = animation.effect;
    /** @type {Node | null} */
    let node = effect instanceof KeyframeEffect ? effect.target : null;
    while (node && !roots.some((root) => root === node))
      node = node.parentNode ?? (node instanceof ShadowRoot ? node.host : null);
    return node !== null;
  });
};

// The page is settled once nothing is moving: no finite animation, and no scroll in
// flight, such as a landing's glide, which is no animation and moves every box it
// scrolls.
export const pageSettled = () => moving().length === 0 && !scrolling();
export const userViewRestoreCases = () => USER_VIEW_RESTORE_CASES;

const formControl = (/** @type {Element} */ node) =>
  node.ownerDocument.defaultView?.customElements.get(node.localName)?.formAssociated ===
  true;

// Where a node Chrome raised a DevTools issue about is, and whether the page owns it.
// A form-associated control's shadow tree is its module's implementation, so an issue
// there is the control's to fix; what the page put in its light DOM stays the page's.
/** @param {Node} initial */
export function issueNode(initial) {
  /** @type {Node | null} */
  let node = initial;
  let owned = true;
  // Roots and custom-element definitions belong to the node's own window.
  for (let host = upFrom(node.getRootNode()); host; host = upFrom(host.getRootNode()))
    if (formControl(host)) owned = false;
  // Read ownership before placing an embedded document's issue at the frame
  // the page author can find. Cross-origin frames withhold that element.
  const view = (/** @type {Node} */ n) =>
    (n.nodeType === n.DOCUMENT_NODE ? /** @type {Document} */ (n) : n.ownerDocument)
      ?.defaultView;
  while (node && view(node) !== globalThis.top) node = view(node)?.frameElement ?? null;
  if (!node) return null;
  return { at: at(node), owned };
}

/** @param {(typeof USER_VIEW_RESTORE_CASES)[number]} restoreCase */
export function applyRestoreCase(restoreCase) {
  localStorage.clear();
  sessionStorage.clear();
  const store = restoreCase.store === "session" ? sessionStorage : localStorage;
  store.setItem(restoreCase.key, restoreCase.value);
}

// Every post this tab has made to /api/event has ended, the page's error reports
// among them (`runtime/traffic.js`). A page that has posted nothing paints no ledger.
export function sendsAcked() {
  const traffic = document.documentElement.dataset.lfTraffic;
  if (traffic === undefined) return true;
  const { sends, acked } = JSON.parse(traffic);
  return sends === acked;
}

// The threads whose messages carry authored markup, whose widgets render only where the
// thread is drawn: in its margin card, or in the floating panel's thread view where
// nothing on the page shows it. The gate opens each in turn to read them.
export const threadsHoldingMarkup = () =>
  readThreads()
    .threads.filter((thread) =>
      thread.msgs.some((message) => message.body.kind === "authored"),
    )
    .map((thread) => thread.key);

// Open one thread where a reader would find it, without moving focus or the page.
// A probe is synchronous, so the opening's answer is kept for `threadOpening` to read:
// null while it runs, then whether it drew the thread, or the error it threw.
/** @typedef {{shown: boolean, error?: string}} OpeningAnswer */
/** @type {{key: string, answer: OpeningAnswer | null} | null} */
let opening = null;
/** @param {string} key */
export function openThreadToCheck(key) {
  /** @type {{key: string, answer: OpeningAnswer | null}} */
  const current = { key, answer: null };
  opening = current;
  threadActions.open(key, { focus: false, travel: false }).then(
    (/** @type {unknown} */ destination) =>
      (current.answer = { shown: Boolean(destination) }),
    (/** @type {unknown} */ error) =>
      (current.answer = { shown: false, error: exceptionText(error) }),
  );
}
export const threadOpening = (/** @type {string} */ key) =>
  opening?.key === key ? opening.answer : null;
