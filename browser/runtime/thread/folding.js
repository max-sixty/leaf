/* Settlement command continuations. Thread views own every generated control.

   A settlement's landing is the surface's own: `prepareLanding` returns the step that
   carries the user where the gesture leaves them, which may be away from the thread.
   The thread's container also names the reader the user had the thread in (`reader`,
   thread-card.js, `ViewOutlets`): the page, for a margin card, or the primary reader,
   for a whole thread there that lands the user elsewhere, as the floating panel's view
   does. The way back reopens the thread there (undo.js, `returnToThread`), since a
   route left to choose would choose for the thread as it stands: it put a thread
   resolved in its card in the panel, where resolved threads open, and one resolved in
   the panel's view in a card beside its passage. A seat names none, since a route to
   the thread finds it in the seat it stands in. A primary reader's part that leaves the
   user where they pressed draws the same card as a seat and names none either; a route
   to the thread asks the primary first. The log
   refusing the gesture takes the way back
   here, while the user has not acted since; undo.js keeps the reader for `z` and the
   notice's Undo (`retainGesture`), and the landing arms `z` to take the gesture in
   one press (`landedAway`).

   A sent settlement says what it did in the notice seat, since its landing may carry the
   user away from the thread and leave nothing on screen to say it was resolved, and
   offers the press that matters most next (`nextStep`). After a Resolve that is the
   next open thread, `t`'s press, while one stands open; after a Reopen, or a Resolve
   that left none open, it is the press that takes the settlement back, as `z` would
   (undo.js, `offerUndo`). The user chose Next thread on 6 November 2026, from three
   weeks of their keys: `t` came next after 130 of 406 Resolves and `z` after 7, so
   Undo, offered there since 31 October, gave way; `z` and the menu's Undo still take
   the Resolve back. The notice goes when the log refuses the settlement or it is taken
   back, so its press never acts for a settlement that no longer stands. It names the
   thread by its name, as `z` does and every surface that names a thread
   (`threadName`): "Resolved the thread" stood under the next thread a panel's Resolve
   moved the user on to, and read as that thread's (the user's choice, 31 October).
   Rejected: the words the thread is about, which `z` then named by its name. */
import { inputCount } from "../focus.js";
import { randomId } from "../ids.js";
import { pressCommand } from "../keyboard/dispatch.js";
import { notice } from "../notifications.js";
import { bindQueuedWork } from "../queued-work.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { retainUserIntent } from "../user-intent.js";
import { quotedWords } from "../words.js";
import { threadName } from "./messages.js";
import { anyOpenThread, threadNamed } from "./state.js";

// What the notice calls the thread, cut as undo.js cuts the names its notices quote,
// so a long name leaves the press beside it in view.
const NAMED = 48;

// The press a settlement's notice offers (the header's second paragraph): `t`'s next
// open thread after a Resolve while one stands open, standing no longer than the
// Resolve does, else the settlement's undo.
/** @param {boolean} resolving @param {import("../notifications.js").NoticePress} undo
 * @returns {import("../notifications.js").NoticePress} */
const nextStep = (resolving, undo) =>
  resolving && anyOpenThread()
    ? {
        action: "next-thread",
        command: "thread.next",
        run: () => pressCommand("thread.next"),
        stands: () => undo.stands() && anyOpenThread(),
      }
    : undo;

/** @typedef {() => boolean | void | Promise<boolean | void>} Landing */
/** @param {{
 * parent: () => string,
 * key: string,
 * resolved: boolean,
 * prepareLanding?: (() => Landing | null) | null,
 * reader?: import("../undo.js").Reader,
 * pendingEntries: ReturnType<typeof import("../pending/state.js").createPendingLedger>["snapshot"],
 * actions: Pick<ReturnType<typeof import("./actions.js").createThreadActions>, "reopen" | "resolve">,
 * undo: Pick<ReturnType<typeof import("../undo.js").createUndo>, "landedAway" | "offerUndo" | "retainGesture" | "returnToThread">,
 * }} dependencies */
export async function settleThread({
  parent,
  key,
  resolved,
  prepareLanding,
  reader = null,
  pendingEntries,
  actions,
  undo,
}) {
  const land = prepareLanding?.();
  const since = inputCount();
  const attempt = randomId();
  const thread = threadNamed(key);
  const named = thread ? quotedWords(threadName(thread), NAMED) : "the thread";
  const answer = resolved
    ? actions.reopen(key, { attempt })
    : actions.resolve(key, { attempt });
  if (!answer) return;
  undo.retainGesture(attempt, { settled: { reader } });
  notice(`${resolved ? "Reopened" : "Resolved"} ${named}`, {
    press: nextStep(!resolved, undo.offerUndo(attempt)),
  });
  if (land) undo.landedAway(attempt);
  await landGesture({
    land,
    answer,
    pending: () => pendingEntries().some((entry) => entry.event.attempt === attempt),
    // The landing has moved focus, so the return is the user's while no input has
    // come since the gesture, wherever focus now stands.
    refused: async () => {
      const mayReturn = retainUserIntent({ since });
      await whenDocumentPresented();
      return undo.returnToThread(parent(), mayReturn, reader);
    },
  });
}

/** Carry the user where a sent gesture leaves them, and back if the log refuses it.
 *
 * `land` is the surface's landing step, or null; `answer` the send's answer;
 * `pending` whether the gesture is still on its way, so a landing the log answered
 * before the page presented the gesture waits for that answer. */
/** @param {{land: Landing | null | undefined,
 * answer: Promise<import("../../types/domain.js").Event | null>,
 * pending: () => boolean,
 * refused: () => unknown,
 * }} continuation */
async function landGesture({ land, answer, pending, refused }) {
  /** @param {(() => unknown) | null | undefined} work */
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
  const finishLanding = bindQueuedWork(
    /** @param {import("../../types/domain.js").Event | null} accepted @param {boolean | undefined} landed */
    (accepted, landed) => {
      if (!accepted) return land && step(refused);
      if (!landed) return step(land);
    },
  );
  await whenDocumentPresented();
  const landed = await startLanding();
  const accepted = await answer;
  await finishLanding(accepted, landed);
}
