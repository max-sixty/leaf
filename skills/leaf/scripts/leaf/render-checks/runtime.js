import { USER_VIEW_RESTORE_CASES, upFrom } from "/runtime/widget-api.js";
import { validationPresentationReady } from "/runtime/validation.js";
import { at } from "./locate.js";
import { openRoots } from "./open-roots.js";

export const runtimeStarted = () => document.querySelector(".lf-banner") !== null;
export const upgraded = () => document.body.dataset.lfUpgraded === "1";
export const initiallyPresented = () => document.body.dataset.lfPresented === "1";
export const currentPresented = () =>
  initiallyPresented() && validationPresentationReady();
// A reader holding the server's reading taken at `taken` sees that reading presented,
// or a later one.
export const dataApplied = (version, taken) =>
  document.body.dataset.lfDataVersion === version ||
  Number(document.body.dataset.lfDataTaken ?? -Infinity) >= taken;
export const logApplied = (applied) =>
  Number(document.body.dataset.lfApplied ?? -1) >= applied;

// Finite animations delay final geometry reads. Infinite ambient animation, such as the
// status indicator, does not. `moving` is the render gate's shared reading of that
// boundary. A component that animates forever must not appear in it; a state transition
// that can still change boxes must.
export function moving() {
  return openRoots(document)
    .flatMap((root) => root.getAnimations())
    .filter(
      (animation) =>
        animation.playState === "running" &&
        Number.isFinite(animation.effect?.getComputedTiming().endTime),
    )
    .map((animation) =>
      animation.animationName
        ? `${at(animation.effect?.target)} ${animation.animationName}`
        : at(animation.effect?.target),
    );
}

export const pageSettled = () => moving().length === 0;
export const userViewRestoreCases = () => USER_VIEW_RESTORE_CASES;

export function unnamedFormFields() {
  const formControl = (node) => node.constructor.formAssociated === true;
  // A form-associated custom element owns the field's identity, including its
  // shadow implementation and light-DOM choices in a grouped control.
  const insideControl = (field) => {
    for (let parent = upFrom(field); parent; parent = upFrom(parent))
      if (formControl(parent)) return true;
    return false;
  };
  return openRoots(document).flatMap((root) =>
    [...root.querySelectorAll("*")]
      .filter((field) => field.matches("input,select,textarea") || formControl(field))
      .filter((field) => !insideControl(field))
      .filter((field) => !field.id && !field.getAttribute("name"))
      .map((field) => ({
        tag: field.localName,
        className: field.className,
        label:
          field.getAttribute("aria-label") ?? field.getAttribute("placeholder") ?? "",
      })),
  );
}

export function applyRestoreCase(restoreCase) {
  localStorage.clear();
  sessionStorage.clear();
  const store = restoreCase.store === "session" ? sessionStorage : localStorage;
  store.setItem(restoreCase.key, restoreCase.value);
}

let requestedFrame = 0;
let presentedFrame = 0;

// Ask the compositor for a rendering turn without handing page.evaluate a Promise
// whose settlement depends on that turn. The driver polls the synchronous fact below,
// so its own deadline still runs when a stopped compositor never calls us back.
export function requestFrame() {
  const requested = ++requestedFrame;
  requestAnimationFrame(() => {
    presentedFrame = Math.max(presentedFrame, requested);
  });
  return requested;
}
export const framePresented = (requested) => presentedFrame >= requested;
