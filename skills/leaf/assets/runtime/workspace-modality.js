/* The shared modal boundary for an auxiliary workspace that covers the document.

   Visibility owners keep their ordinary surfaces and scrollports while responsive
   layout decides whether they stand beside the page or over it. In the covering
   posture this owner makes every sibling reading surface inert, dims the covered page,
   gives the workspace modal semantics, and moves focus in only when it was outside. It
   re-derives those siblings when the live version replaces the authored page. Leaving
   that posture restores exactly the inert and role state it found; it does not rebuild,
   hide, or scroll either side.

   Native inertness owns sequential focus and pointer reach. This owner adds the Tab
   wrap and programmatic-focus recovery that a non-top-layer workspace still needs.
   Native dialogs opened above it remain available to their top-layer owner. */

export function createWorkspaceModality({ chromeRoot, focusable }) {
  const controllers = new Set();
  const scrim = document.createElement("div");
  scrim.className = "lf-workspace-scrim";
  scrim.hidden = true;
  scrim.setAttribute("aria-hidden", "true");
  let active = null;
  let placingFocus = false;
  let mounted = false;

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
  const nativeModalContains = (node) => node?.closest?.("dialog:modal");
  const overlay = (node) => node.matches?.("dialog:not(.lf-panel)");
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
      !nativeModalContains(document.activeElement)
    )
      place(active.focus() ?? active.surface);
  });

  function enter(controller) {
    if (active && active !== controller)
      throw new Error("leaf: two covering workspaces cannot be modal together");
    if (active === controller) return;

    active = controller;
    syncBackground(controller);
    controller.role = controller.surface.getAttribute("role");
    controller.surface.setAttribute("role", "dialog");
    controller.surface.setAttribute("aria-modal", "true");
    document.body.dataset.lfModalWorkspace = controller.surface.id;
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
    delete document.body.dataset.lfModalWorkspace;
    scrim.hidden = true;
    active = null;
  }

  function register({ surface, scroller, covers, focus, dismiss }) {
    if (!surface?.id || !scroller || !covers || !focus || !dismiss)
      throw new Error(
        "leaf: a modal workspace needs a named surface, scroller, covering reading, focus destination, and dismissal",
      );
    const controller = {
      surface,
      scroller,
      covers,
      focus,
      dismiss,
      open: false,
      role: null,
      suspended: new Map(),
      sync(open) {
        controller.open = open;
        if (open && covers()) enter(controller);
        else leave(controller);
      },
    };
    controllers.add(controller);
    return controller;
  }

  function sync() {
    for (const controller of controllers) controller.sync(controller.open);
  }

  function mount() {
    if (mounted) return;
    mounted = true;
    scrim.addEventListener("pointerdown", (event) => event.preventDefault());
    scrim.addEventListener("click", () => active?.dismiss());
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
        nativeModalContains(event.target)
      )
        return;
      place(active.focus() ?? active.surface);
    });
  }

  const coveringSurface = () => active?.surface ?? null;
  const coveringScroller = () => active?.scroller() ?? null;
  const openSurfaceFor = (node) => {
    for (const controller of controllers)
      if (controller.open && controller.surface.contains(node))
        return controller.surface;
    return null;
  };

  return {
    scrim,
    register,
    sync,
    mount,
    coveringSurface,
    coveringScroller,
    openSurfaceFor,
  };
}
