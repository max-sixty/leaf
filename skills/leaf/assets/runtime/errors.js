/* Errors the user should know about: one call raises each, whatever failed, and the
   chrome decides where it shows, so no producer chooses a seat or a flag.

   An error is something the user did that did not take, such as a send the server
   refused or an image the field could not attach. `raiseError` records it with the
   text field it concerns, where there is one (`subject`), such as the box a refused
   send's words came back to, and hands back a handle whose `clear()` takes it down
   once it no longer holds. An error nobody clears stays until the user dismisses it.
   A condition that stands while a reading says so, such as the server being out of
   reach or the agent's latest save failing its check, holds an error through
   `holdingError`, which raises it when the condition begins and clears it when it
   ends.

   The floating panel places each error from what it draws (floating-panel.js): in its
   field, in the status's place, while that field is the error's subject, or, for an
   error with no subject, while the field is empty; over words its subject holds, it
   covers them until the user's first key or press there. The user's first edit in
   the field passes every error the field could say (`passErrors`). An error the
   field cannot say, or has passed, waits in the Errors list in the leaf's menu, with
   a dot on the leaf until the user opens the list (`seeErrors`). The user chose this
   on 17 October over errors riding the passing notice, which faded after four
   seconds, was replaced by whatever came next, and went unseen while the user typed.

   A screen reader hears each error as it is raised, unless its producer already says
   it aloud, as page-status.js does a change of status. News and acknowledgements stay
   notices (notifications.js); an error is never one. */
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
let unsaid = [];
/** @type {readonly RaisedError[]} */
let errors = Object.freeze([]);
const presenters = new Set();

const publish = (next) => {
  errors = Object.freeze(next.slice(0, KEPT));
  for (const present of presenters) present();
};

/** The standing errors, newest first. */
export const errorsReading = () => errors;

// The chrome registers how it repaints when the errors change.
export function registerErrorPresentation(present) {
  presenters.add(present);
}

/**
 * Tell the user something failed. `subject` is the text field it concerns, if any;
 * `announce: false` leaves the words to a producer that already says them aloud.
 * @param {string} message
 * @param {{ subject?: Element | null, announce?: boolean }} [options]
 */
export function raiseError(message, { subject = null, announce: speak = true } = {}) {
  const id = ++raised;
  if (speak && !unsaid.length)
    queueMicrotask(() => {
      announce(unsaid.map((said) => said.replace(/\.$/, "")).join(". "));
      unsaid = [];
    });
  if (speak) unsaid.push(message);
  publish([
    Object.freeze({ id, message, subject, at: Date.now(), passed: false, seen: false }),
    ...errors,
  ]);
  return Object.freeze({ clear: () => dismissError(id) });
}

/** The user edited past these errors where the field said them. */
export function passErrors(ids) {
  if (errors.some((entry) => ids.includes(entry.id) && !entry.passed))
    publish(
      errors.map((entry) =>
        ids.includes(entry.id) && !entry.passed
          ? Object.freeze({ ...entry, passed: true })
          : entry,
      ),
    );
}

/** The user opened the Errors list, so none it shows is news any more. */
export function seeErrors() {
  if (errors.some((entry) => !entry.seen))
    publish(
      errors.map((entry) =>
        entry.seen ? entry : Object.freeze({ ...entry, seen: true }),
      ),
    );
}

export function dismissError(id) {
  if (errors.some((entry) => entry.id === id))
    publish(errors.filter((entry) => entry.id !== id));
}

/**
 * An error for a condition its producer reads: calling the returned function with the
 * words the condition stands for raises the error, with other words replaces it, and
 * with null clears it.
 */
export function holdingError({ announce: speak = true } = {}) {
  let held = null;
  let said = null;
  return (/** @type {string | null} */ message) => {
    if (message === said) return;
    held?.clear();
    held = message ? raiseError(message, { announce: speak }) : null;
    said = message;
  };
}

export function dismissErrors() {
  if (errors.length) publish([]);
}
