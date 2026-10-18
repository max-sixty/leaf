/* Errors the user should know about: one call raises each, whatever failed, and the
   chrome decides where it shows, so no producer chooses a seat or a flag.

   An error is something the user did that did not take, such as a send the server
   refused or an image the field could not attach, or a condition that stands until it
   clears. `raiseError` records it and hands back
   a handle whose `clear()` takes it down once it no longer holds: a condition ends, a
   retry works. An error nobody clears stays until the user dismisses it.

   The floating panel shows the newest error in its field, in place of the status the
   field says while empty, until the user's first edit (`passError`); then it waits in
   the Errors list in the leaf's menu, with a dot on the leaf until the user opens the
   list (`seeErrors`). The user chose this on 17 October over errors riding the
   passing notice, which faded after four seconds, was replaced by whatever came next,
   and went unseen while the user typed, so whether an error showed depended on what
   the user was doing (floating-panel.js). The banner chrome keeps no list; with no
   chrome presenting errors, each passes as a notice in its status line instead.

   A screen reader hears each error as it is raised. News and acknowledgements stay
   notices (notifications.js); an error is never one. */
import { announce, notice } from "./notifications.js";

/**
 * @typedef {{ label: string, run: () => void }} ErrorAction
 * @typedef {Readonly<{
 *   id: number,
 *   message: string,
 *   about: string | null,
 *   action: ErrorAction | null,
 *   at: number,
 *   inField: boolean,
 *   seen: boolean,
 * }>} RaisedError
 */

// The list keeps the latest errors only; older ones have long stopped mattering.
const KEPT = 20;

let raised = 0;
/** @type {readonly RaisedError[]} */
let errors = Object.freeze([]);
const presenters = new Set();

const publish = (next) => {
  errors = Object.freeze(next.slice(0, KEPT));
  for (const present of presenters) present();
};
const change = (id, update) =>
  publish(
    errors.map((entry) =>
      entry.id === id ? Object.freeze({ ...entry, ...update }) : entry,
    ),
  );

/** The standing errors, newest first. */
export const errorsReading = () => errors;

// A chrome that shows errors registers how it repaints; one that registers nothing
// leaves each error to the notice seat.
export function registerErrorPresentation(present) {
  presenters.add(present);
}

/**
 * Tell the user something failed. `about` names what it concerns, such as "your page
 * comment", for the Errors list; `action` offers the press that would fix it.
 * @param {string} message
 * @param {{ about?: string | null, action?: ErrorAction | null }} [options]
 */
export function raiseError(message, { about = null, action = null } = {}) {
  const id = ++raised;
  announce(message);
  if (!presenters.size) notice(message, { announce: false });
  publish([
    Object.freeze({
      id,
      message,
      about,
      action,
      at: Date.now(),
      inField: true,
      seen: false,
    }),
    ...errors,
  ]);
  return Object.freeze({ clear: () => dismissError(id) });
}

/** The user edited past the error in the field, which leaves it in the list. */
export function passError(id) {
  if (errors.some((entry) => entry.id === id && entry.inField))
    change(id, { inField: false });
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

export function dismissErrors() {
  if (errors.length) publish([]);
}
