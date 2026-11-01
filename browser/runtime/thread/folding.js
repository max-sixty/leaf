/* Settlement command continuations. Thread views own every generated control.

   A settlement's landing is the surface's own: `prepareLanding` returns the step that
   carries the user where the gesture leaves them, which may be away from the thread.
   The thread is the place they return to: the log refusing the gesture returns them
   to it here, while they have not acted since, and the gesture arms `z` to take it
   back in one press that returns them too (undo.js, `landedAway` and
   `returnToThread`, which own where a withdrawn gesture leaves the user).

   A sent settlement says what it did in the notice seat, since its landing may carry the
   user away from the thread and leave nothing on screen to say it was resolved, and
   offers the press that takes that settlement back, as `z` would (undo.js,
   `offerUndo`), which says the reverse; the notice goes when the log refuses the
   settlement or it is taken back, so its press never takes back another. It names
   the thread by the words it is about, as the thread's head quotes them, else by its
   name: "Resolved the thread" stood under the next thread a panel's Resolve moved the
   user on to, and read as that thread's (the user's choice, 31 October). */
import { inputCount } from "../focus.js";
import { randomId } from "../ids.js";
import { paintKeys } from "../keyboard/scopes.js";
import { notice } from "../notifications.js";
import { bindQueuedWork } from "../queued-work.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { retainUserIntent } from "../user-intent.js";
import { excerptWords, quotedWords } from "../words.js";
import { anchorLabel, threadName, threadPassage } from "./messages.js";
import { threadNamed } from "./state.js";

// What the notice calls the thread, cut as undo.js cuts the names its notices quote,
// so a long passage leaves the press beside it in view.
const NAMED = 48;
function settledName(key) {
  const thread = threadNamed(key);
  if (!thread) return "the thread";
  const passage = threadPassage(thread);
  const label = anchorLabel(
    passage?.quote
      ? { ...passage, quote: excerptWords(passage.quote, NAMED) }
      : passage,
    thread.root.about,
  );
  return label || quotedWords(threadName(thread), NAMED);
}

export async function settleThread({
  parent,
  key,
  resolved,
  prepareLanding,
  pendingEntries,
  actions,
  landedAway,
  offerUndo,
  returnToThread,
}) {
  const land = prepareLanding?.();
  const since = inputCount();
  const attempt = randomId();
  const named = settledName(key);
  const answer = resolved
    ? actions.reopen(key, { attempt })
    : actions.resolve(key, { attempt });
  if (!answer) return;
  notice(`${resolved ? "Reopened" : "Resolved"} ${named}`, {
    press: offerUndo(attempt),
  });
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
