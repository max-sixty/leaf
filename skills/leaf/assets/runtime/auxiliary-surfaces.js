/* One selected auxiliary surface, its remembered selection, and its covering boundary.

   Registered surfaces retain their own rendering and scrollports. Selecting one closes
   the previous surface before opening it; there is no per-surface visibility state.
   Restoration reserves the selected surface's room immediately. A surface whose rows
   need the first server reading declares presentation-time arrival, so its rendering
   and covering boundary wait for that reading without postponing the shell geometry.

   Responsive layout decides whether surfaces stand beside the page or over it. In the covering
   posture this owner makes every sibling reading surface inert, dims that entire
   background, gives the surface modal semantics, and moves focus in only when it was
   outside. It re-derives those siblings when the live version replaces the authored
   page. Leaving that posture restores exactly the inert and role state it found; it
   does not rebuild, hide, or scroll either side.

   Native inertness owns sequential focus and pointer reach. This owner adds the Tab
   wrap and programmatic-focus recovery that a non-top-layer surface still needs.
   Entering the boundary dismisses pre-existing outside popovers. Native dialogs, and
   popovers deliberately opened after entry, remain available to their top-layer owner. */

import { openPopovers } from "./keyboard/layer-stack.js";
import { registerAuxiliaryModality } from "./keyboard/register.js";
import { under } from "./shadow.js";
import { userStore } from "./storage.js";
import { pagePresented } from "./presentation.js";

export const AUXILIARY_SURFACE_KEY = "lf-auxiliary-surface";
let selectedKey = null;
export const currentAuxiliarySurface = () => selectedKey;

export function createAuxiliarySurfaces({
  chromeRoot,
  focusable,
  takeShell,
  syncLayout,
  afterChange,
}) {
  const controllers = new Map();
  const scrim = document.createElement("div");
  scrim.className = "lf-auxiliary-scrim";
  scrim.hidden = true;
  scrim.setAttribute("aria-hidden", "true");
  let active = null;
  let placingFocus = false;
  let mounted = false;
  let arriving = null;

  const deepestFocus = () => {
    let node = document.activeElement;
    while (node?.shadowRoot?.activeElement) node = node.shadowRoot.activeElement;
    return node;
  };
  const stops = (surface) =>
    [...surface.querySelectorAll(focusable)].filter(
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
  const nativeLayerContains = (node) => node?.closest?.("dialog:modal, :popover-open");
  const overlay = (node) => node.matches?.("dialog:not(.lf-thread-panel), [popover]");
  const background = (surface) => {
    const nodes = [];
    for (const child of document.body.children) {
      if (child !== chromeRoot) nodes.push(child);
    }
    for (const child of chromeRoot.children) {
      if (child !== surface && child !== scrim && !overlay(child)) nodes.push(child);
    }
    return nodes;
  };

  const syncBackground = (controller) => {
    const next = new Set(background(controller.surface));
    for (const [node, inert] of controller.suspended) {
      if (next.has(node)) continue;
      node.inert = inert;
      controller.suspended.delete(node);
    }
    for (const node of next) {
      if (!controller.suspended.has(node)) controller.suspended.set(node, node.inert);
      node.inert = true;
    }
  };

  const backgroundMutations = new MutationObserver(() => {
    if (active) syncBackground(active);
  });

  const focusMutations = new MutationObserver(() => {
    if (
      active &&
      !active.surface.contains(document.activeElement) &&
      !nativeLayerContains(document.activeElement)
    )
      place(active.focus() ?? active.surface);
  });

  function enter(controller) {
    if (active && active !== controller)
      throw new Error("leaf: two covering auxiliary surfaces cannot be modal together");
    if (active === controller) return;

    for (const popover of openPopovers())
      if (!under(popover, controller.surface)) popover.hidePopover();
    active = controller;
    syncBackground(controller);
    controller.role = controller.surface.getAttribute("role");
    controller.surface.setAttribute("role", "dialog");
    controller.surface.setAttribute("aria-modal", "true");
    document.body.dataset.lfCoveringSurface = controller.surface.id;
    scrim.hidden = false;
    backgroundMutations.observe(document.body, { childList: true });
    backgroundMutations.observe(chromeRoot, { childList: true });
    focusMutations.observe(controller.surface, { childList: true, subtree: true });

    if (!controller.surface.contains(document.activeElement))
      place(controller.focus() ?? controller.surface);
  }

  function leave(controller) {
    if (active !== controller) return;
    backgroundMutations.disconnect();
    focusMutations.disconnect();
    for (const [node, inert] of controller.suspended) node.inert = inert;
    controller.suspended.clear();
    if (controller.role === null) controller.surface.removeAttribute("role");
    else controller.surface.setAttribute("role", controller.role);
    controller.surface.removeAttribute("aria-modal");
    delete document.body.dataset.lfCoveringSurface;
    scrim.hidden = true;
    active = null;
  }

  function registerAuxiliarySurface({
    key,
    surface,
    scroller,
    covers,
    focus,
    show,
    hide,
    arrival = "mount",
  }) {
    if (!key || !surface?.id || !scroller || !covers || !focus || !show || !hide)
      throw new Error(
        "leaf: an auxiliary surface needs a key, named surface, scroller, covering reading, focus destination, and visibility callbacks",
      );
    if (controllers.has(key))
      throw new Error(`leaf: duplicate auxiliary surface ${key}`);
    const controller = {
      key,
      surface,
      scroller,
      covers,
      focus,
      show,
      hide,
      arrival,
      role: null,
      suspended: new Map(),
    };
    controllers.set(key, controller);
  }

  function sync() {
    const selected = controllers.get(selectedKey);
    if (active && (active !== selected || !active.covers())) leave(active);
    if (selected && selected !== arriving && selected.covers()) enter(selected);
  }

  function select(
    key,
    { remember = true, returnFocus = true, phase = "gesture" } = {},
  ) {
    if (key !== null && !controllers.has(key))
      throw new Error(`leaf: unknown auxiliary surface ${key}`);
    if (selectedKey === key) return;
    const previous = controllers.get(selectedKey);
    if (active) leave(active);
    selectedKey = key;
    arriving = null;
    const selected = controllers.get(key);
    // One surface goes down, the shell changes, the next comes up (`takeShell` says why
    // nothing renders in between).
    previous?.hide({ returnFocus });
    takeShell(key);
    if (selected) {
      if (
        phase === "arrival" &&
        selected.arrival === "presentation" &&
        !pagePresented()
      )
        arriving = selected;
      else selected.show({ phase });
    }
    sync();
    syncLayout();
    afterChange();
    if (remember) userStore.set(AUXILIARY_SURFACE_KEY, key ?? "");
  }

  function restore() {
    const key = userStore.get(AUXILIARY_SURFACE_KEY);
    select(controllers.has(key) ? key : null, { remember: false, phase: "arrival" });
  }

  function present() {
    if (!arriving) return;
    const surface = arriving;
    arriving = null;
    surface.show({ phase: "arrival" });
    sync();
    syncLayout();
    afterChange();
  }

  function mount() {
    if (mounted) return;
    mounted = true;
    scrim.addEventListener("pointerdown", (event) => event.preventDefault());
    scrim.addEventListener("click", () => select(null));
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
        nativeLayerContains(event.target)
      )
        return;
      place(active.focus() ?? active.surface);
    });
  }

  const coveringSurface = () => active?.surface ?? null;
  const coveringScroller = () => active?.scroller() ?? null;
  const coveringFocus = () => (active ? (active.focus() ?? active.surface) : null);
  // The keyboard register carries this reading to the dispatcher, whose own closure stops
  // there: a direct edge to this owner would give a key press this owner's whole
  // initialization graph.
  registerAuxiliaryModality({ coveringSurface });
  return {
    scrim,
    registerAuxiliarySurface,
    select,
    restore,
    present,
    sync,
    mount,
    coveringSurface,
    coveringScroller,
    coveringFocus,
  };
}
