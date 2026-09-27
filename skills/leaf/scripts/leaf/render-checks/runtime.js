import { USER_VIEW_RESTORE_CASES } from "/runtime/widget-api.js";
import { at } from "./locate.js";
import { openRoots } from "./open-roots.js";

export const runtimeStarted = () => document.querySelector(".lf-banner") !== null;
export const upgraded = () => document.body.dataset.lfUpgraded === "1";

// Finite animations delay final geometry reads. Infinite ambient animation, such as the
// status indicator, does not. `moving` is the render gate's shared reading of that
// boundary. A component that animates forever must not appear in it; a state transition
// that can still change boxes must.
export function moving() {
  return openRoots(document)
    .flatMap((root) => root.getAnimations())
    .filter(
      (animation) =>
        animation.playState === "running" &&
        Number.isFinite(animation.effect?.getComputedTiming().endTime),
    )
    .map((animation) =>
      animation.animationName
        ? `${at(animation.effect?.target)} ${animation.animationName}`
        : at(animation.effect?.target),
    );
}

export const pageSettled = () => moving().length === 0;
export const userViewRestoreCases = () => USER_VIEW_RESTORE_CASES;

const formControl = (node) => node.constructor.formAssociated === true;

// Where a node Chrome raised a DevTools issue about is, and whether the page owns it.
// A form-associated control's shadow tree is its module's implementation, so an issue
// there is the control's to fix; what the page put in its light DOM stays the page's.
export function issueNode(node) {
  let owned = true;
  for (let root = node.getRootNode(); root.host; root = root.host.getRootNode())
    if (formControl(root.host)) owned = false;
  return { at: at(node), owned };
}

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
