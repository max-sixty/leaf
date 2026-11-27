/* Settlement command continuations. Thread views own every generated control.

   A settlement's landing is the surface's own: `prepareLanding` returns the step that
   carries the user where the gesture leaves them, which may be away from the thread.
   The log refusing the gesture takes the way back to the thread here, while the user
   has not acted since, once the page presents the refusal, so the route to the thread
   reads it open again and opens it where every route opens it, by the user's choice of
   where threads open (records/undo.js, `returnToThread`). records/undo.js notes the settlement for ⌘Z
   and the notice's Undo (`retainGesture`).

   A sent settlement says what it did in the notice seat, since its landing may carry the
   user away from the thread and leave nothing on screen to say it was resolved, and
   offers the press that matters most next (`nextStep`). After a Resolve that is the
   next open thread, `t`'s press, while one stands open; after a Reopen, or a Resolve
   that left none open, it is ⌘Z's Undo, while ⌘Z would take the settlement back
   (records/undo.js, `offerUndo`). The user chose Next thread over Undo there; ⌘Z and the
   menu's Undo still take the Resolve back. The notice goes when the log refuses the
   settlement or it is taken back, so its press never acts for a settlement that no
   longer stands. It names the thread by its name, as ⌘Z does and every surface that
   names a thread (`threadName`): "Resolved the thread" would stand under the next
   thread a panel's Resolve moves the user on to, and read as that thread's (the user's
   choice). Rejected: the words the thread is about, while ⌘Z names it by its name. A
   Resolve that leaves no thread open says that instead, "All threads resolved": with
   none left there is no next thread for the words to be read as, ⌘Z still names the
   thread it takes back, and the user asked for the field to mark the moment. The words
   are Threads' own: "All done" would speak for On Me and the agent's list too, which
   may still hold something, and Done is what an On list and a to-do call what left them
   (glossary.md, "Reader-facing words"). */
import { inputCount } from "../../dom/focus.js";
import { randomId } from "../../base/ids.js";
import { notice } from "../../transport/notifications.js";
import { bindQueuedWork } from "../../lib/queued-work.js";
import { whenDocumentPresented } from "../../state/semantic-state.js";
import { retainUserIntent } from "../../dom/user-intent.js";
import { quotedWords } from "../../lib/words.js";
import { threadName } from "./messages.js";
import { anyOpenThread, threadNamed } from "./state.js";
import type { NoticePress } from "../../transport/notifications.js";
import type { createPendingLedger } from "../pending/state.js";
import type { createThreadActions } from "./actions.js";
import type { createUndo } from "../undo.js";
import type { Event } from "../../../types/domain.js";

// What the notice calls the thread, cut as records/undo.js cuts the names its notices quote,
// so a long name leaves the press beside it in view.
const NAMED = 48;

// The press a settlement's notice offers (the header's second paragraph): `t`'s next
// open thread after a Resolve while one stands open, standing no longer than the
// Resolve does, else the settlement's undo.
const nextStep = (resolving: boolean, undo: NoticePress): NoticePress =>
  resolving && anyOpenThread()
    ? {
        action: "next-thread",
        command: "thread.next",
        stands: () => undo.stands() && anyOpenThread(),
      }
    : undo;

export type Landing = () => boolean | void | Promise<boolean | void>;
export async function settleThread({
  parent,
  key,
  resolved,
  prepareLanding,
  pendingEntries,
  actions,
  undo,
}: {
  parent: () => string;
  key: string;
  resolved: boolean;
  prepareLanding?: (() => Landing | null) | null;
  pendingEntries: ReturnType<typeof createPendingLedger>["snapshot"];
  actions: Pick<ReturnType<typeof createThreadActions>, "reopen" | "resolve">;
  undo: Pick<
    ReturnType<typeof createUndo>,
    "offerUndo" | "retainGesture" | "returnToThread"
  >;
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
  undo.retainGesture(attempt, { settled: true });
  const said = resolved
    ? `Reopened ${named}`
    : anyOpenThread()
      ? `Resolved ${named}`
      : "All threads resolved";
  notice(said, { press: nextStep(!resolved, undo.offerUndo(attempt)) });
  await landGesture({
    land,
    answer,
    pending: () => pendingEntries().some((entry) => entry.event.attempt === attempt),
    // The landing has moved focus, so the return is the user's while no input has
    // come since the gesture, wherever focus now stands.
    refused: async () => {
      const mayReturn = retainUserIntent({ since });
      await whenDocumentPresented();
      return undo.returnToThread(parent(), mayReturn);
    },
  });
}

/** Carry the user where a sent gesture leaves them, and back if the log refuses it.
 *
 * `land` is the surface's landing step, or null; `answer` the send's answer;
 * `pending` whether the gesture is still on its way, so a landing the log answered
 * before the page presented the gesture waits for that answer. */
async function landGesture({
  land,
  answer,
  pending,
  refused,
}: {
  land: Landing | null | undefined;
  answer: Promise<Event | null>;
  pending: () => boolean;
  refused: () => unknown;
}) {
  const step = async (work: (() => unknown) | null | undefined) => {
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
    (accepted: Event | null, landed: boolean | undefined) => {
      if (!accepted) return land && step(refused);
      if (!landed) return step(land);
    },
  );
  await whenDocumentPresented();
  const landed = await startLanding();
  const accepted = await answer;
  await finishLanding(accepted, landed);
}
