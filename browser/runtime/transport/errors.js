/* Errors the user should know about: one call raises each, whatever failed, and the
   chrome decides where it shows, so no producer chooses a seat or a flag.

   An error is something the user did that did not take, such as a send the server
   refused or an image the field could not attach. `raiseError` records it with the
   text field it concerns, where there is one (`subject`), such as the box a refused
   send's words came back to, and hands back a handle whose `clear()` takes it down
   once it no longer holds. An error nobody clears stays until the user dismisses it.
   A package's widget raises one with an `lf-error` event on the window, which carries
   only words.
   A condition that stands while a reading says so, such as the server refusing this
   tab's key or the agent's latest save failing its check, holds an error through
   `holdingError`, which raises it when the condition begins and clears it when it
   ends.

   An error about a text field stands at that field, wherever it is, covering the
   field's words and actions until the user comes back to them, by a key or an image
   there, a press on the cover or Resume writing (`g i`), or the field stops showing
   them (`passErrorsAt`, `errorOver`; annotations/composing/input.js). The floating panel's field
   also says an error about nothing, in its status's place while it is empty, until the
   user's first edit there (panel/floating-panel.js). An error no field stands for, or one the user has
   passed, waits in the Errors list in the leaf's menu, with a dot on the leaf and on
   the menu's Errors until the user opens the list (`seeErrors`), so the row the
   dotted leaf leads to reads at once. The user chose this over
   errors riding the passing notice, which fades after four seconds, gives way to
   whatever comes next, and goes unseen while the user types; and chose
   the cover at a passage's comment box over the error showing only as the leaf's
   dot, which leaves nothing saying a refused send's words have come back.

   An error about no text field may offer the one press that recovers from it
   (`press`), as a refused send whose words came back out of view offers Resume
   writing, while that press can still act (its `stands`). The floating panel's field
   shows it after the error's words with the keys that would make it now, as it shows a
   notice's (panel/field-readings.js, `end`), and the Errors list offers it beside Dismiss. A
   text field's cover draws no press, so an error about one offers none.

   A screen reader hears each error as it is raised, unless its producer already says
   it aloud, as panel/page-status.js does a change of status. News and acknowledgements stay
   notices (notifications.js); an error is never one.

   Each error keeps the revision the page showed and the stack it was raised from
   (`revision`, `stack`), so whoever is handed a copy of it starts from the source and
   the code that raised it, however the page has moved on since (panel/floating-panel.js,
   `errorReport`).
   The tab's trace records it among the gestures that led to it (interaction-log.js). */
import { signal, untracked } from "/vendor/signals-core.js";
import { runtime } from "../state/context.js";
import { recordInteraction } from "./interaction-log.js";
import { announce, gesture } from "./notifications.js";

/**
 * @typedef {Readonly<{
 *   id: number,
 *   message: string,
 *   subject: Element | null,
 *   press: import("./notifications.js").NoticePress | null,
 *   at: number,
 *   revision: number | null,
 *   stack: string,
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

/** The newest error about a text field the user has not come back to, which covers its
 * words.
 * @param {Element | null | undefined} subject */
export const errorOver = (subject) =>
  errorsReading().find((error) => error.subject === subject && !error.passed) ?? null;

/**
 * Tell the user something failed. `subject` is the text field it concerns, if any;
 * `announce: false` leaves the words to a producer that already says them aloud;
 * `press` is the press that recovers from an error about no field.
 * @param {string} message
 * @param {{ subject?: Element | null, announce?: boolean,
 *   press?: import("./notifications.js").NoticePress | null }} [options]
 */
export function raiseError(
  message,
  { subject = null, announce: speak = true, press = null } = {},
) {
  return raise(message, subject, speak, null, press);
}

// Raise an error, taking the one `replaced` names down in the same reading, so the
// chrome never draws the moment between them.
/** @param {string} message @param {Element | null} subject @param {boolean} speak @param {number | null} replaced
 * @param {import("./notifications.js").NoticePress | null} [press] */
function raise(message, subject, speak, replaced, press = null) {
  const id = ++raised;
  if (speak && !unsaid.length)
    queueMicrotask(() => {
      announce(unsaid.map((said) => said.replace(/\.$/, "")).join(". "));
      unsaid = [];
    });
  if (speak) unsaid.push(message);
  const stack = new Error(message).stack ?? "";
  recordInteraction("error", { message, stack });
  publish([
    Object.freeze({
      id,
      message,
      subject,
      press,
      at: Date.now(),
      revision: untracked(() => runtime.currentRevision ?? null),
      stack,
      passed: false,
      seen: false,
    }),
    ...errors.peek().filter((entry) => entry.id !== replaced),
  ]);
  // An error about no field is the panel's to say, and its leaf shakes at it.
  if (!subject) gesture("error");
  return Object.freeze({ id, clear: () => dismissError(id) });
}

// A widget raises an error about no text field from outside Leaf's helpers: an
// `lf-error` event on the window whose `detail` is the words, as `lf-announce` carries
// words for a listener. A detail that is no words throws here, so the page reports it
// rather than leave the user untold.
addEventListener("lf-error", (event) => {
  if (typeof event.detail !== "string" || !event.detail)
    throw new TypeError(
      "leaf: an lf-error event's detail is the words to tell the user",
    );
  raiseError(event.detail);
});

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
