/* Undo: the `z` walk and the one door every withdrawal goes through.

   The server's view of the shown revision lists, newest first, the user's gestures this
   document can take back (`served_state/document.py`); nothing here judges a candidate
   again. `z` takes the head of that list only when the server marks it `newest`, the
   user's newest gesture, so a reply sent since ends the walk; a widget's Undo, a
   reaction chip, and a reaction strip each name an exact entry. All of them withdraw
   through `withdraw`.

   `z` says what it takes and how long ago that was made, in the command reference, the
   floating panel's menu row and the notice its undo leaves ("Undo: resolved “Rollout
   safety” · 3d ago", then "Undid: resolved “Rollout safety” · 3d ago — sent"), in
   every tab and after a reload. A thread goes by its name as it stands now, a to-do by
   its title, an approval by its version and a reaction by where it stands, all of
   which the page already holds. An action's ids are words only in the document it was
   made in, so the server serves what the head did in that document's words
   (`gesture`, `GestureWords.gesture`), and the widget goes by its name on this page.
   An exact control's older entry carries no such reading, so its undo names only the
   widget. The age is the gesture's own `ts`, worded by the page's one clock (`ago`).

   A gesture leaves, by its attempt, what its undo needs from the page that made it
   (`retainGesture`). One that moves the user leaves how to put them back; a thread
   settlement's landing is the one that does (thread/folding.js). A withdrawal the log
   admits runs that reversal once the page presents it, under the intent of the press
   that asked for it. A widget's gesture leaves the words the widget named it by
   (`says`, pending/dispatch.js), and while this page holds them its undo is said in
   them, the name its own acknowledgement used: "Chose “Fast” — sent", then "Undid:
   Chose “Fast” · just now — sent". Both live with the page that made the gesture, so
   after a reload or from another tab the undo changes the thread and moves nobody. */
import { notice } from "./notifications.js";
import {
  applicationState,
  readApplication,
  whenDocumentPresented,
} from "./semantic-state.js";
import { runtime } from "./context.js";
import { pageCommand } from "./keyboard/register.js";
import { savedReadingSettled } from "./keyboard/bindings.js";
import { reactionPlace } from "./reactions.js";
import { PENDING } from "./thread/identity.js";
import { threadNamed } from "./thread/state.js";
import { threadName } from "./thread/messages.js";
import { addressableLabel, addressableWord } from "./addressable-names.js";
import { elementById } from "./passages.js";
import { ago } from "./presence.js";
import { excerptWords } from "./words.js";
import { retainUserIntent } from "./user-intent.js";
import { raiseError } from "./errors.js";

const WAIT = "Wait for the current change to finish before undoing";

const quoted = (words, cap = 60) => `“${excerptWords(words, cap)}”`;

// A widget as the chrome names it on this page, else the word for its kind.
function widgetNamed(id) {
  const element = elementById(id);
  if (!element) return "a widget";
  const label = addressableLabel(element);
  return label ? quoted(label) : `the ${addressableWord(element)}`;
}

// What an action did, from the server's reading of it in its own document. The verbs
// are core's: a widget's own verb, such as `move` or `edit`, may read as a noun, so a
// verb with no record form core knows is quoted as what was recorded.
function actionWords(event, gesture) {
  const widget = widgetNamed(event.widget);
  switch (gesture?.form) {
    case "choice":
      return `chose ${gesture.chosen.map((words) => quoted(words)).join(", ") || "nothing"} in ${widget}`;
    case "move":
      return `moved ${quoted(gesture.unit)} to ${quoted(gesture.to)} in ${widget}`;
    case "edit":
      return `edited ${widget}`;
    case "add":
      return `added ${quoted(gesture.words)} to ${widget}`;
    case "verb":
      return `recorded “${gesture.verb}” on ${widget}`;
    default:
      return `updated ${widget}`;
  }
}

const TODO_ENDINGS = {
  done: (title) => `marked ${title} done`,
  failed: (title) => `marked ${title} failed`,
  dropped: (title) => `dropped ${title}`,
};

// What a gesture did, in the words the page holds for it now.
function gestureWords(event, gesture) {
  if (event.token) return `${event.token} reaction on ${reactionPlace(event)}`;
  switch (event.kind) {
    case "resolve":
    case "unresolve": {
      const thread = threadNamed(event.parent);
      const name = thread ? quoted(threadName(thread), 48) : "a thread";
      return `${event.kind === "resolve" ? "resolved" : "reopened"} ${name}`;
    }
    case "done":
      return `approved v${event.version}`;
    case "todo_end": {
      const todo = runtime.todos.find(({ id }) => id === event.todo);
      return TODO_ENDINGS[event.outcome](todo ? quoted(todo.title) : "a to-do");
    }
    default:
      return actionWords(event, gesture);
  }
}

export function createUndo({ post, stateApplying, unaccountedGesture }) {
  // Kept while its gesture can still be taken back: in flight, or on the undo list.
  /** @type {Map<string, {reverse?: (mayLand: unknown) => unknown, says?: string}>} */
  const gestures = new Map();
  function retainGesture(attempt, facts) {
    const { effective, unresolved } = readApplication();
    // Between versions the page holds no undo list to prune against.
    if (effective.view) {
      const liveAttempts = new Set([
        ...effective.view.undo.map(({ event }) => event.attempt),
        ...unresolved.map((entry) => entry.event.attempt),
      ]);
      for (const kept of gestures.keys())
        if (!liveAttempts.has(kept)) gestures.delete(kept);
    }
    gestures.set(attempt, { ...gestures.get(attempt), ...facts });
  }
  // What taking `event` back takes: by the name its gesture was acknowledged by where
  // this page made it, else in the words the page holds for it now.
  const said = (event) => {
    const gesture = runtime.undo.find((entry) => entry.event.id === event.id)?.gesture;
    return gestures.get(event.attempt)?.says ?? gestureWords(event, gesture);
  };
  // ...and how long ago it was made.
  const takes = (event) => [said(event), ago(event.ts)].filter(Boolean).join(" · ");

  // The gesture `z` would take on the list the page holds now.
  const head = () => {
    const [first] = runtime.undo;
    return first?.newest ? first.event : null;
  };
  function undoable() {
    return stateApplying() ? null : head();
  }
  // Whether taking back this exact gesture now takes back what the user sees. The
  // ordered ledger sends the undo behind everything already queued, the target's own
  // unanswered send included, and the server remains final admission. Two things it
  // cannot order: another action awaiting presentation may change which gestures
  // the page can honestly offer, whether or not its own POST has answered, and only
  // an action's withdrawal can name its target before the log does, so a message
  // the log has not taken waits for its answer.
  function withdrawable(event) {
    if (event.kind !== "action" && String(event.id).startsWith(PENDING)) return false;
    return !applicationState
      .unpresented()
      .some(
        (entry) =>
          entry.event.kind === "action" &&
          (entry.admitted?.id ?? entry.localId) !== event.id,
      );
  }

  // The one withdrawal door. Returns null when the page refuses the withdrawal now,
  // otherwise the delivery, which yields the admitted undo or null.
  function withdraw(event) {
    if (!withdrawable(event)) {
      raiseError(WAIT);
      return null;
    }
    const reverse = gestures.get(event.attempt)?.reverse;
    const taken = takes(event);
    const mayLand = retainUserIntent();
    const answer = post({ kind: "undo", undoes: event.id }).then((accepted) => {
      if (accepted) {
        notice(`Undid: ${taken} — sent`);
        gestures.delete(event.attempt);
      }
      return accepted;
    });
    if (reverse)
      void answer
        .then(async (accepted) => {
          if (!accepted) return;
          await whenDocumentPresented();
          await reverse(mayLand);
        })
        .catch(() => {});
    return answer;
  }

  // The walk needs the page settled, not only the gesture it takes back: an
  // unaccounted gesture is newer than the list's head, so the head would be the
  // gesture before the one the user just made, and a reading still being applied may
  // replace the list.
  function undoLast() {
    if (stateApplying() || unaccountedGesture()) {
      raiseError(WAIT);
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
    ready: savedReadingSettled,
    keys: ["z"],
    // Said from the list the page holds rather than `undoable`, so a reading being
    // applied leaves the words standing while it holds the press back. The menu's row
    // cuts long words, so it says the age at its end rather than after them.
    description: () => (head() ? `Undo: ${takes(head())}` : "Undo the latest update"),
    title: "undo",
    touch: () => (head() ? `Undo: ${said(head())}` : "Undo"),
    touchValue: () => (head() ? ago(head().ts) : ""),
    menu: "page",
    // Dead while the page holds a gesture no log read accounts for, this one's own send
    // included. The line drops the chip for as long as that is true rather than
    // promising a press that would undo the wrong thing.
    when: () => !unaccountedGesture() && Boolean(undoable()),
    run: (/** @type {Parameters<typeof undoLast>} */ ...args) => undoLast(...args),
  });

  return {
    retainGesture,
    undoable,
    undoLast,
    withdraw,
  };
}
