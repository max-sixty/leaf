import {
  announce,
  notice
} from "./bundle-page-paint.js";

// runtime/errors.js
var KEPT = 20;
var raised = 0;
var errors = Object.freeze([]);
var presenters = /* @__PURE__ */ new Set();
var publish = (next) => {
  errors = Object.freeze(next.slice(0, KEPT));
  for (const present of presenters) present();
};
var change = (id, update) => publish(
  errors.map(
    (entry) => entry.id === id ? Object.freeze({ ...entry, ...update }) : entry
  )
);
var errorsReading = () => errors;
function registerErrorPresentation(present) {
  presenters.add(present);
}
function raiseError(message, { about = null, action = null } = {}) {
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
      seen: false
    }),
    ...errors
  ]);
  return Object.freeze({ clear: () => dismissError(id) });
}
function passError(id) {
  if (errors.some((entry) => entry.id === id && entry.inField))
    change(id, { inField: false });
}
function seeErrors() {
  if (errors.some((entry) => !entry.seen))
    publish(
      errors.map(
        (entry) => entry.seen ? entry : Object.freeze({ ...entry, seen: true })
      )
    );
}
function dismissError(id) {
  if (errors.some((entry) => entry.id === id))
    publish(errors.filter((entry) => entry.id !== id));
}
function dismissErrors() {
  if (errors.length) publish([]);
}

export {
  errorsReading,
  registerErrorPresentation,
  raiseError,
  passError,
  seeErrors,
  dismissError,
  dismissErrors
};
