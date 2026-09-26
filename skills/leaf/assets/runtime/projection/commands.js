/* Undo: the `z` walk and the one door every withdrawal goes through.

   The server's view of the shown revision lists, newest first, the user's gestures this
   document can take back (`served_state/document.py`); nothing here judges a candidate
   again. `z` takes the head of that list, and a widget's Undo, a reaction chip, and a
   reaction strip each name an exact entry. All of them withdraw through `withdraw`. */
import { runtime } from "../context.js";
import { notice } from "../notifications.js";
import { readApplication } from "../semantic-state.js";
import { paintKeys } from "../keyboard/scopes.js";
import { pageCommand } from "../keyboard/register.js";
import { undoSentence } from "../reactions.js";
import { PENDING } from "../thread/identity.js";

const WAIT = "Wait for the current change to finish before undoing";

// Said in the kinds this file owns, never in the verb the action carries: `move` and
// `edit` read as nouns in that sentence and `choose` does not, and which of the two a
// widget's word is is not core's to know. A reaction's word is its token.
const words = {
  resolve: "Reopened the thread",
  unresolve: "Resolved the thread again",
  action: "Took back your last change",
  done: "Took back your approval",
};

export function createProjectionCommands({ post, stateApplying, unaccountedGesture }) {
  function undoable() {
    if (stateApplying()) return null;
    return readApplication().effective.view?.undo[0]?.event ?? null;
  }

  // Whether taking back this exact gesture now takes back what the user sees. The
  // ordered ledger sends the undo behind everything already queued, the target's own
  // unanswered send included, and the server remains final admission. Two things it
  // cannot order: an accepted action whose presentation is still outstanding may yet
  // change which gestures the page can honestly offer, and only an action has a
  // withdrawal the page draws before the log answers, so a message the log has not
  // taken waits for its answer.
  function withdrawable(event) {
    if (event.kind !== "action" && String(event.id).startsWith(PENDING)) return false;
    return !readApplication().unresolved.some(
      (entry) =>
        entry.event.kind === "action" &&
        entry.answered &&
        entry.readEvent &&
        entry.readEvent.id !== event.id &&
        !entry.presented,
    );
  }

  // The one withdrawal door. Returns null when the page refuses the withdrawal now,
  // otherwise the delivery, which yields the admitted undo or null.
  function withdraw(event) {
    if (!withdrawable(event)) {
      notice(WAIT);
      return null;
    }
    runtime.undoing = true;
    paintKeys();
    return post({ kind: "undo", undoes: event.id })
      .then((accepted) => {
        if (accepted)
          notice(
            `${event.token ? `Took back your ${event.token}` : words[event.kind]} — sent`,
          );
        return accepted;
      })
      .finally(() => {
        runtime.undoing = false;
        paintKeys();
      });
  }

  // The walk needs the page settled, not only the gesture it takes back: an
  // unaccounted gesture is newer than the list's head, so the head would be the
  // gesture before the one the user just made, and a reading still being applied may
  // replace the list.
  function undoLast() {
    if (stateApplying() || unaccountedGesture()) {
      notice(WAIT);
      return null;
    }
    const event = undoable();
    return event ? withdraw(event) : null;
  }

  // The last thing the user did to this page, put back. Its own key rather than the
  // platform's ⌘Z, which belongs to the box a user is typing in and is taken by the
  // browser everywhere else: this is a page-level press like every other letter, and the
  // typing scope keeps it off a composer's words by claiming its letters. The word is
  // "undo" and never the verb it is about to state — `move` is one widget's word, and a
  // line that said it would be naming a member where the mechanism is what holds.
  pageCommand({
    id: "history.undo",
    keys: ["z"],
    does: () => undoSentence(undoable),
    line: "undo",
    // Dead while the page holds a gesture no log read accounts for, this one's own send
    // included. The line drops the chip for as long as that is true rather than
    // promising a press that would undo the wrong thing.
    when: () => !unaccountedGesture() && Boolean(undoable()),
    run: (...args) => undoLast(...args),
  });

  return {
    undoable,
    undoLast,
    withdraw,
  };
}
