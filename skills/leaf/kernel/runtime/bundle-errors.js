import {
  announce,
  notice
} from "./bundle-page-paint.js";

// runtime/errors.js
var KEPT = 20;
var raised = 0;
var unsaid = [];
var errors = Object.freeze([]);
var presenters = /* @__PURE__ */ new Set();
var publish = (next) => {
  errors = Object.freeze(next.slice(0, KEPT));
  for (const present of presenters) present();
};
var errorsReading = () => errors;
function registerErrorPresentation(present) {
  presenters.add(present);
}
function raiseError(message, { subject = null, announce: speak = true } = {}) {
  const id = ++raised;
  if (speak && !unsaid.length)
    queueMicrotask(() => {
      announce(unsaid.map((said) => said.replace(/\.$/, "")).join(". "));
      unsaid = [];
    });
  if (speak) unsaid.push(message);
  if (!presenters.size) notice(message, { announce: false });
  publish([
    Object.freeze({ id, message, subject, at: Date.now(), passed: false, seen: false }),
    ...errors
  ]);
  return Object.freeze({ clear: () => dismissError(id) });
}
function passErrors(ids) {
  if (errors.some((entry) => ids.includes(entry.id) && !entry.passed))
    publish(
      errors.map(
        (entry) => ids.includes(entry.id) && !entry.passed ? Object.freeze({ ...entry, passed: true }) : entry
      )
    );
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
function holdingError({ announce: speak = true } = {}) {
  let held = null;
  let said = null;
  return (message) => {
    if (message === said) return;
    held?.clear();
    held = message ? raiseError(message, { announce: speak }) : null;
    said = message;
  };
}
function dismissErrors() {
  if (errors.length) publish([]);
}

export {
  errorsReading,
  registerErrorPresentation,
  raiseError,
  passErrors,
  seeErrors,
  dismissError,
  holdingError,
  dismissErrors
};
