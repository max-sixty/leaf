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

const formControl = (node) => node.constructor.formAssociated === true;
// A form-associated custom element owns what its fields are called and labelled by,
// including its shadow implementation and light-DOM choices in a grouped control, so
// a finding about one of them is its module's to fix rather than the page's.
const insideControl = (node) => {
  for (let parent = upFrom(node); parent; parent = upFrom(parent))
    if (formControl(parent)) return true;
  return false;
};

// Where a node Chrome raised a DevTools issue about is, and whether the page owns it.
export const issueNode = (node) => ({ at: at(node), owned: !insideControl(node) });

export function unnamedFormFields() {
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

// The runtime's settled reading for chrome and geometry (runtime/rendering.js): nothing
// it queued for a rendering update is waiting and its last update was quiet.
export const renderingSettled = () =>
  document.querySelector("script[data-lf-entry]").lfRenderingSettled();

// Every post this tab has made to /api/event has ended, the page's error reports
// among them (`runtime/traffic.js`). A page that has posted nothing paints no ledger.
export function sendsAcked() {
  const traffic = document.documentElement.dataset.lfTraffic;
  if (traffic === undefined) return true;
  const { sends, acked } = JSON.parse(traffic);
  return sends === acked;
}
