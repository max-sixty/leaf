/* Settlement command continuations and mechanical resolution-fold motion.
   Thread views own every generated control and reflected folding attribute. */
import { paintKeys } from "../keyboard/scopes.js";
import { FOLD_MS, motion } from "../motion.js";
import { pendingForParent } from "../pending/model.js";

export const pendingSettlement = (entries, id) =>
  pendingForParent(entries, id, ["resolve", "unresolve"]);

export async function settleThread({
  id,
  resolved,
  prepareLanding,
  pendingEntries,
  setResolved,
}) {
  if (pendingSettlement(pendingEntries(), id())) return;
  const landing = prepareLanding?.();
  const { answer, presentation } = setResolved(id(), !resolved);
  paintKeys();
  try {
    await presentation;
    const land = async (step) => {
      try {
        return Boolean(await step?.());
      } catch {
        return false;
      } // The conversation ticket reports presentation failures.
    };
    let landed = false;
    if (pendingSettlement(pendingEntries(), id()))
      landed = await land(landing?.optimistic);
    const accepted = await answer;
    if (!accepted) await land(landing?.refused);
    else if (!landed) await land(landing?.optimistic);
  } finally {
    paintKeys();
  }
}

const folding = new Map();
export function foldOut(id, node, repaintConversation) {
  const standing = folding.get(id);
  if (standing?.node.isConnected) return true;
  folding.delete(id);
  const style = getComputedStyle(node);
  const from = {
    height: node.getBoundingClientRect().height + "px",
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
  const record = { node, played };
  folding.set(id, record);
  played.finished.then(
    () => {
      if (folding.get(id) !== record) return;
      folding.delete(id);
      repaintConversation();
    },
    () => {},
  );
  return true;
}

export function finishFold(id) {
  const record = folding.get(id);
  folding.delete(id);
  record?.played.cancel();
}
export const hasFolding = () =>
  [...folding.values()].some(({ node }) => node.isConnected);
export const isFolding = (id) => folding.has(id);
