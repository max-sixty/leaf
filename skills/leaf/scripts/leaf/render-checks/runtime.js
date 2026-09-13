import { READER_VIEW_RESTORE_CASES } from "/runtime/widget-api.js";
import { validationPresentationReady } from "/runtime/validation.js";
import { openRoots } from "./open-roots.js";

export const runtimeStarted = () => document.querySelector(".lf-banner") !== null;
export const upgraded = () => document.body.dataset.lfUpgraded === "1";
export const initiallyPresented = () => document.body.dataset.lfPresented === "1";
export const currentPresented = () =>
  initiallyPresented() && validationPresentationReady();
export const dataApplied = (revision) =>
  Number(document.body.dataset.lfDataRevision ?? -1) >= revision;
export const logApplied = (applied) =>
  Number(document.body.dataset.lfApplied ?? -1) >= applied;

// Finite animations delay final geometry reads. Infinite ambient animation, such as the
// status indicator, does not. `moving` is the render gate's shared reading of that
// boundary. A component that animates forever must not appear in it; a state transition
// that can still change boxes must.
export function moving() {
  const at = (el) => {
    for (let node = el; node; node = node.getRootNode?.()?.host) {
      const named = node.closest?.("[id]");
      if (named) return `<${named.tagName.toLowerCase()} id=${named.id}>`;
    }
    return `<${el?.tagName?.toLowerCase() ?? "?"}>`;
  };
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
export const readerViewRestoreCases = () => READER_VIEW_RESTORE_CASES;

export function unnamedFormFields() {
  return openRoots(document).flatMap((root) =>
    [...root.querySelectorAll("input,select,textarea")]
      .filter((field) => !field.id && !field.name)
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
