/* Settlement command continuations. Thread views own every generated control.

   A settlement's landing is the surface's own: `prepareLanding` returns the step that
   carries the user where the gesture leaves them, which may be away from the thread.
   The thread is the place they return to: the log refusing the gesture returns them
   to it here, while they have not acted since, and the gesture arms `z` to take it
   back in one press that returns them too (undo.js, `landedAway` and
   `returnToThread`, which own where a withdrawn gesture leaves the user).

   A sent settlement says what it did in the notice seat, since its landing may carry the
   user away from the thread and leave nothing on screen to say it was resolved; `z`
   says the reverse (undo.js). */
import { inputCount } from "../focus.js";
import { randomId } from "../ids.js";
import { paintKeys } from "../keyboard/scopes.js";
import { notice } from "../notifications.js";
import { bindQueuedWork } from "../queued-work.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { retainUserIntent } from "../user-intent.js";

export async function settleThread({
  parent,
  key,
  resolved,
  prepareLanding,
  pendingEntries,
  actions,
  landedAway,
  returnToThread,
}) {
  const land = prepareLanding?.();
  const since = inputCount();
  const attempt = randomId();
  const answer = resolved
    ? actions.reopen(key, { attempt })
    : actions.resolve(key, { attempt });
  if (!answer) return;
  notice(resolved ? "Reopened the thread" : "Resolved the thread");
  if (land) landedAway(attempt);
  await landGesture({
    land,
    answer,
    pending: () => pendingEntries().some((entry) => entry.event.attempt === attempt),
    // The landing has moved focus, so the return is the user's while no input has
    // come since the gesture, wherever focus now stands.
    refused: async () => {
      const mayReturn = retainUserIntent({ since });
      await whenDocumentPresented();
      return returnToThread(parent(), mayReturn);
    },
  });
}

/** Carry the user where a sent gesture leaves them, and back if the log refuses it.
 *
 * `land` is the surface's landing step, or null; `answer` the send's answer;
 * `pending` whether the gesture is still on its way, so a landing the log answered
 * before the page presented the gesture waits for that answer. */
async function landGesture({ land, answer, pending, refused }) {
  const step = async (work) => {
    try {
      return Boolean(await work?.());
    } catch {
      return false;
    } // The thread ticket reports presentation failures.
  };
  // These are the command's two deferred invocations, rather than the native async
  // tail that waits for them. Capture both before presentation yields the gesture.
  const startLanding = bindQueuedWork(() => (pending() ? step(land) : false));
  const finishLanding = bindQueuedWork((accepted, landed) => {
    if (!accepted) return land && step(refused);
    if (!landed) return step(land);
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
