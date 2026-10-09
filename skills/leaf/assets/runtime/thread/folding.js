/* Settlement command continuations and mechanical resolution-fold motion.
   Thread views own every generated control and reflected folding attribute.

   A settlement's landing is the surface's own: `optimistic` carries the user where the
   gesture leaves them, and `reverse` puts them back once it no longer stands. The log
   refusing it runs `reverse` here; the user taking it back runs the same `reverse`,
   which the undo door holds by the gesture's attempt, under the undo's intent. */
import { newAttempt } from "../drafts.js";
import { paintKeys } from "../keyboard/scopes.js";
import { FOLD_MS, motion } from "../motion.js";
import { pendingForParent } from "../pending/model.js";
import { bindQueuedWork } from "../queued-work.js";
import { whenDocumentPresented } from "../semantic-state.js";

const pendingSettlement = (entries, id) =>
  pendingForParent(entries, id, ["resolve", "unresolve"]);

export async function settleThread({
  parent,
  key,
  resolved,
  prepareLanding,
  pendingEntries,
  actions,
  retainReversal,
}) {
  if (pendingSettlement(pendingEntries(), parent())) return;
  const landing = prepareLanding?.();
  const attempt = newAttempt();
  const answer = resolved
    ? actions.reopen(key, { attempt })
    : actions.resolve(key, { attempt });
  if (!answer) return;
  if (landing) retainReversal(attempt, landing.reverse);
  const land = async (step) => {
    try {
      return Boolean(await step?.());
    } catch {
      return false;
    } // The thread ticket reports presentation failures.
  };
  // These are the command's two deferred invocations, rather than the native async
  // tail that waits for them. Capture both before presentation yields the gesture.
  const startLanding = bindQueuedWork(() =>
    pendingSettlement(pendingEntries(), parent()) ? land(landing?.optimistic) : false,
  );
  const finishLanding = bindQueuedWork((accepted, landed) => {
    if (!accepted) return land(landing?.reverse);
    if (!landed) return land(landing?.optimistic);
  });
  const presentation = whenDocumentPresented();
  paintKeys();
  try {
    await presentation;
    const landed = await startLanding();
    const accepted = await answer;
    await finishLanding(accepted, landed);
  } finally {
    paintKeys();
  }
}

// Fold motion belongs to the rendered card. The same Thread can stand in several
// panels, each with its own node, disclosure, and animation lifetime.
const folding = new Map();
export function foldOut(node, repaintThread) {
  const standing = folding.get(node);
  if (standing && node.isConnected) return true;
  folding.delete(node);
  standing?.played.cancel();
  const style = getComputedStyle(node);
  // Every length holding the box open folds to nothing: an open panel card's floor
  // (`min-height`, chrome.css) as well as its height.
  const from = {
    height: node.getBoundingClientRect().height + "px",
    minHeight: style.minHeight,
    marginBottom: style.marginBottom,
    borderTopWidth: style.borderTopWidth,
    borderBottomWidth: style.borderBottomWidth,
    paddingTop: style.paddingTop,
    paddingBottom: style.paddingBottom,
    opacity: 1,
  };
  const to = Object.fromEntries(Object.keys(from).map((key) => [key, "0px"]));
  to.opacity = 0;
  const played = motion(node, [from, to], FOLD_MS);
  if (!played) return false;
  const record = { played };
  folding.set(node, record);
  played.finished.then(
    () => {
      if (folding.get(node) !== record) return;
      folding.delete(node);
      repaintThread();
    },
    () => {},
  );
  return true;
}

export function finishFold(node) {
  const record = folding.get(node);
  folding.delete(node);
  record?.played.cancel();
}
export const hasFolding = (root) =>
  [...folding.keys()].some((node) => node.isConnected && root.contains(node));
// Settles once every fold now running under `root` has ended, finished or cancelled.
export const whenFolded = (root) =>
  Promise.allSettled(
    [...folding]
      .filter(([node]) => root.contains(node))
      .map(([, { played }]) => played.finished),
  );
export const isFolding = (node) => folding.has(node);
