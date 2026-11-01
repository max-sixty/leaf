/* Errors the user should know about: one call raises each, whatever failed, and the
   chrome decides where it shows, so no producer chooses a seat or a flag.

   An error is something the user did that did not take, such as a send the server
   refused or an image the field could not attach. `raiseError` records it with the
   text field it concerns, where there is one (`subject`), such as the box a refused
   send's words came back to, and hands back a handle whose `clear()` takes it down
   once it no longer holds. An error nobody clears stays until the user dismisses it.
   A condition that stands while a reading says so, such as the server refusing this
   tab's key or the agent's latest save failing its check, holds an error through
   `holdingError`, which raises it when the condition begins and clears it when it
   ends.

   An error about a text field stands at that field, wherever it is, covering the
   field's words and actions until the user comes back to them, by a key or an image
   there, a press on the cover or Resume writing (`g i`), or the field stops showing
   them (`passErrorsAt`; composing/input.js, `errorOver`). The floating panel's field
   also says an error about nothing, in its status's place while it is empty, until the
   user's first edit there (floating-panel.js). An error no field stands for, or one the user has
   passed, waits in the Errors list in the leaf's menu, with a dot on the leaf until
   the user opens the list (`seeErrors`). The user chose this on 17 October over
   errors riding the passing notice, which faded after four seconds, was replaced by
   whatever came next, and went unseen while the user typed; and on 19 October chose
   the cover at a passage's comment box, where the error had shown only as the leaf's
   dot, so nothing said a refused send's words had come back.

   A screen reader hears each error as it is raised, unless its producer already says
   it aloud, as page-status.js does a change of status. News and acknowledgements stay
   notices (notifications.js); an error is never one. */
import { signal } from "/runtime/framework.js";
import { announce } from "./notifications.js";

/**
 * @typedef {Readonly<{
 *   id: number,
 *   message: string,
 *   subject: Element | null,
 *   at: number,
 *   passed: boolean,
 *   seen: boolean,
 * }>} RaisedError
 */

// The list keeps the latest errors only; older ones have long stopped mattering.
const KEPT = 20;

let raised = 0;
// Errors raised in one task are announced together: the live region keeps only the
// last of several words written to it at once (notifications.js, `announce`).
/** @type {string[]} */
let unsaid = [];
/** @type {import("@preact/signals-core").Signal<readonly RaisedError[]>} */
const errors = signal(Object.freeze([]));

/** @param {readonly RaisedError[]} next */
const publish = (next) => {
  errors.value = Object.freeze(next.slice(0, KEPT));
};

/** The standing errors, newest first. */
export const errorsReading = () => errors.value;

/**
 * Tell the user something failed. `subject` is the text field it concerns, if any;
 * `announce: false` leaves the words to a producer that already says them aloud.
 * @param {string} message
 * @param {{ subject?: Element | null, announce?: boolean }} [options]
 */
export function raiseError(message, { subject = null, announce: speak = true } = {}) {
  return raise(message, subject, speak, null);
}

// Raise an error, taking the one `replaced` names down in the same reading, so the
// chrome never draws the moment between them.
/** @param {string} message @param {Element | null} subject @param {boolean} speak @param {number | null} replaced */
function raise(message, subject, speak, replaced) {
  const id = ++raised;
  if (speak && !unsaid.length)
    queueMicrotask(() => {
      announce(unsaid.map((said) => said.replace(/\.$/, "")).join(". "));
      unsaid = [];
    });
  if (speak) unsaid.push(message);
  publish([
    Object.freeze({ id, message, subject, at: Date.now(), passed: false, seen: false }),
    ...errors.peek().filter((entry) => entry.id !== replaced),
  ]);
  return Object.freeze({ id, clear: () => dismissError(id) });
}

/** The user edited past these errors where the field said them. */
/** @param {readonly number[]} ids */
export function passErrors(ids) {
  if (errors.peek().some((entry) => ids.includes(entry.id) && !entry.passed))
    publish(
      errors
        .peek()
        .map((entry) =>
          ids.includes(entry.id) && !entry.passed
            ? Object.freeze({ ...entry, passed: true })
            : entry,
        ),
    );
}

/** The user came back to the words in `subject`, so every error about it is passed. */
/** @param {Element | null} subject */
export function passErrorsAt(subject) {
  passErrors(
    errors
      .peek()
      .filter((entry) => entry.subject === subject)
      .map((entry) => entry.id),
  );
}

/** The user opened the Errors list, so none it shows is news any more. */
export function seeErrors() {
  if (errors.peek().some((entry) => !entry.seen))
    publish(
      errors
        .peek()
        .map((entry) => (entry.seen ? entry : Object.freeze({ ...entry, seen: true }))),
    );
}

/** @param {number} id */
export function dismissError(id) {
  if (errors.peek().some((entry) => entry.id === id))
    publish(errors.peek().filter((entry) => entry.id !== id));
}

/**
 * An error for a condition its producer reads: calling the returned function with the
 * words the condition stands for raises the error, with other words replaces it, and
 * with null clears it.
 */
export function holdingError({ announce: speak = true } = {}) {
  /** @type {ReturnType<typeof raise> | null} */
  let held = null;
  /** @type {string | null} */
  let said = null;
  return (/** @type {string | null} */ message) => {
    if (message === said) return;
    if (message) held = raise(message, null, speak, held?.id ?? null);
    else {
      held?.clear();
      held = null;
    }
    said = message;
  };
}

export function dismissErrors() {
  if (errors.peek().length) publish([]);
}
