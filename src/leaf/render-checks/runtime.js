import {
  USER_VIEW_RESTORE_CASES,
  scrolling,
  exceptionText,
} from "/runtime/check-api.js";
import { readThreads, threadActions } from "/runtime/widget-api.js";
import { at } from "./locate.js";
import { openRoots } from "./open-roots.js";

// The runtime has started once its chrome, the floating panel, is in the page.
export const runtimeStarted = () =>
  document.querySelector(".lf-floating-panel") !== null;
export const upgraded = () => document.body.dataset.lfUpgraded === "1";

// Finite animations delay final geometry reads. Infinite ambient animation, such as the
// status indicator, does not. `moving` is the render gate's shared reading of that
// boundary. A component that animates forever must not appear in it; a state transition
// that can still change boxes must. One on an element the page doesn't render changes
// no box, and Firefox never starts it: a colour transition the scheme starts on a
// control inside a closed `<details>` stays pending until the details open.
export function moving() {
  return openRoots(document)
    .flatMap((root) => root.getAnimations())
    .flatMap((animation) => {
      const effect = animation.effect;
      if (
        animation.playState !== "running" ||
        !Number.isFinite(effect?.getComputedTiming().endTime)
      )
        return [];
      const target = effect instanceof KeyframeEffect ? effect.target : null;
      if (target?.checkVisibility() === false) return [];
      const name = animation instanceof CSSAnimation ? animation.animationName : "";
      return [name ? `${at(target)} ${name}` : at(target)];
    });
}

// The page is settled once nothing is moving: no finite animation, and no scroll in
// flight, such as a landing's smooth glide, which is no animation and moves every box
// it scrolls. The runtime's reading of scrolls starts with its first call, so the
// probes take one as they load, before any input they wait out.
scrolling();
export const pageSettled = () => moving().length === 0 && !scrolling();
export const userViewRestoreCases = () => USER_VIEW_RESTORE_CASES;

const formControl = (/** @type {Element} */ node) =>
  customElements.get(node.localName)?.formAssociated === true;

// Where a node Chrome raised a DevTools issue about is, and whether the page owns it.
// A form-associated control's shadow tree is its module's implementation, so an issue
// there is the control's to fix; what the page put in its light DOM stays the page's.
/** @param {Node} initial */
export function issueNode(initial) {
  /** @type {Node | null} */
  let node = initial;
  let owned = true;
  for (
    let root = node.getRootNode();
    root instanceof ShadowRoot;
    root = root.host.getRootNode()
  )
    if (formControl(root.host)) owned = false;
  // Read ownership before placing an embedded document's issue at the frame
  // the page author can find. Cross-origin frames withhold that element.
  const view = (/** @type {Node} */ n) =>
    (n instanceof Document ? n : n.ownerDocument)?.defaultView;
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
