/* The shared modal boundary for an auxiliary workspace that covers the document.

   Workspaces keep their ordinary DOM and scrollports while responsive layout decides
   whether they stand beside the page or over it. In the covering posture this owner
   makes every sibling reading surface inert, gives the workspace modal semantics, and
   moves focus in only when it was outside. Removing the posture restores exactly the
   inert and role state it found; it does not rebuild, hide, or scroll either side.

   Native inertness owns sequential focus and pointer reach. The theme locks the root
   scrollport from the body attribute written here. Dialogs that may open above the
   workspace remain available to their native top-layer owner. */

import { chromeRoot } from "./chrome.js";
import { FOCUSABLE } from "./reach.js";

const overlay = (node) => node.matches?.("dialog:not(.lf-panel)");

const controllers = new Set();
let active = null;
let placingFocus = false;
const focusMutations = new MutationObserver(() => {
  if (
    active &&
    !active.surface.contains(document.activeElement) &&
    !document.activeElement?.closest?.("dialog:modal")
  )
    place(active.focus() ?? active.surface);
});

const deepestFocus = () => {
  let node = document.activeElement;
  while (node?.shadowRoot?.activeElement) node = node.shadowRoot.activeElement;
  return node;
};

const stops = (surface) =>
  [...surface.querySelectorAll(FOCUSABLE)].filter(
    (node) =>
      node.tabIndex >= 0 &&
      !node.matches(":disabled") &&
      !node.inert &&
      node.checkVisibility(),
  );

const place = (node) => {
  placingFocus = true;
  try {
    node.focus({ preventScroll: true });
  } finally {
    placingFocus = false;
  }
};

// Inertness removes every background stop; this one shared boundary supplies the wrap a
// non-top-layer workspace still needs when the platform would otherwise move from its
// last stop to body. It also returns programmatic focus that tries to enter the inert
// background. A native modal opened above the workspace remains the platform's owner.
document.addEventListener(
  "keydown",
  (event) => {
    if (
      !active ||
      event.key !== "Tab" ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey
    )
      return;
    const available = stops(active.surface);
    if (!available.length) {
      event.preventDefault();
      place(active.surface);
      return;
    }
    const at = available.indexOf(deepestFocus());
    if (
      (!event.shiftKey && at === available.length - 1) ||
      (event.shiftKey && at === 0)
    ) {
      event.preventDefault();
      place(event.shiftKey ? available.at(-1) : available[0]);
    }
  },
  true,
);

document.addEventListener("focusin", (event) => {
  if (
    !active ||
    placingFocus ||
    active.surface.contains(event.target) ||
    event.target?.closest?.("dialog:modal")
  )
    return;
  place(active.focus() ?? active.surface);
});

const background = (surface) => {
  const nodes = [];
  for (const child of document.body.children) {
    if (child !== chromeRoot) nodes.push(child);
  }
  for (const child of chromeRoot.children) {
    if (child !== surface && !overlay(child)) nodes.push(child);
  }
  return nodes;
};

function enter(controller) {
  if (active && active !== controller)
    throw new Error("leaf: two covering workspaces cannot be modal together");
  if (active === controller) return;

  const suspended = background(controller.surface).map((node) => [node, node.inert]);
  for (const [node] of suspended) node.inert = true;
  controller.suspended = suspended;
  controller.role = controller.surface.getAttribute("role");
  controller.surface.setAttribute("role", "dialog");
  controller.surface.setAttribute("aria-modal", "true");
  document.body.dataset.lfModalWorkspace = controller.surface.id;
  active = controller;
  focusMutations.observe(controller.surface, { childList: true, subtree: true });

  if (!controller.surface.contains(document.activeElement)) {
    const destination = controller.focus() ?? controller.surface;
    place(destination);
  }
}

function leave(controller) {
  if (active !== controller) return;
  focusMutations.disconnect();
  for (const [node, inert] of controller.suspended) node.inert = inert;
  controller.suspended = [];
  if (controller.role === null) controller.surface.removeAttribute("role");
  else controller.surface.setAttribute("role", controller.role);
  controller.surface.removeAttribute("aria-modal");
  delete document.body.dataset.lfModalWorkspace;
  active = null;
}

export function modalWorkspace({ surface, scroller, covers, focus }) {
  if (!surface?.id || !scroller || !covers || !focus)
    throw new Error(
      "leaf: a modal workspace needs a named surface, scroller, covering reading, and focus destination",
    );
  const controller = {
    surface,
    scroller,
    covers,
    focus,
    open: false,
    role: null,
    suspended: [],
    sync(open) {
      controller.open = open;
      if (open && covers()) enter(controller);
      else leave(controller);
    },
  };
  controllers.add(controller);
  return controller;
}

export const coveringWorkspaceScroller = () => active?.scroller() ?? null;
export const coveringWorkspaceSurface = () => active?.surface ?? null;
export const openWorkspaceSurfaceFor = (node) => {
  for (const controller of controllers)
    if (controller.open && controller.surface.contains(node)) return controller.surface;
  return null;
};
