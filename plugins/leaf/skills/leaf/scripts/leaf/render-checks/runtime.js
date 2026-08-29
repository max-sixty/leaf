import { ARRANGEMENTS } from "/runtime/widget-api.js";

export const runtimeStarted = () => document.querySelector(".lf-banner") !== null;
export const upgraded = () => document.body.dataset.lfUpgraded === "1";
export const presented = () => document.body.dataset.lfPresented === "1";
export const dataApplied = (revision) =>
  Number(document.body.dataset.lfDataRevision ?? -1) >= revision;
export const logApplied = (applied) =>
  Number(document.body.dataset.lfApplied ?? -1) >= applied;

export function moving() {
  const roots = (root) => [
    root,
    ...[...root.querySelectorAll("*")]
      .filter((el) => el.shadowRoot)
      .flatMap((el) => roots(el.shadowRoot)),
  ];
  const at = (el) => {
    for (let node = el; node; node = node.getRootNode?.()?.host) {
      const named = node.closest?.("[id]");
      if (named) return `<${named.tagName.toLowerCase()} id=${named.id}>`;
    }
    return `<${el?.tagName?.toLowerCase() ?? "?"}>`;
  };
  return roots(document)
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
export const arrangements = () => ARRANGEMENTS;
export function arrange(arrangement) {
  localStorage.clear();
  sessionStorage.clear();
  const store = arrangement.store === "session" ? sessionStorage : localStorage;
  store.setItem(arrangement.key, arrangement.value);
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
