/* Settlement command continuations. Thread views own every generated control.

   A settlement's landing is the surface's own: `optimistic` carries the user where the
   gesture leaves them, and `reverse` puts them back once it no longer stands. The log
   refusing it runs `reverse` here; the user taking it back runs the same `reverse`,
   which the undo door holds by the gesture's attempt, under the undo's intent.

   A sent settlement says what it did in the notice seat, since its landing may carry the
   user away from the thread and leave nothing on screen to say it was resolved; `z`
   says the reverse (undo.js). */
import { randomId } from "../ids.js";
import { paintKeys } from "../keyboard/scopes.js";
import { notice } from "../notifications.js";
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
  const attempt = randomId();
  const answer = resolved
    ? actions.reopen(key, { attempt })
    : actions.resolve(key, { attempt });
  if (!answer) return;
  notice(resolved ? "Reopened the thread" : "Resolved the thread");
  if (landing) retainReversal(attempt, landing.reverse);
  await landGesture({
    landing,
    answer,
    pending: () => Boolean(pendingSettlement(pendingEntries(), parent())),
  });
}

/** Carry the user where a sent gesture leaves them, and back if the log refuses it.
 *
 * `landing` is the surface's {optimistic, reverse}, or null; `answer` the send's
 * answer; `pending` whether the gesture is still on its way, so a landing the log
 * answered before the page presented the gesture waits for that answer. */
async function landGesture({ landing, answer, pending }) {
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
    pending() ? land(landing?.optimistic) : false,
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
