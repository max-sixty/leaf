/* Putting the user on an element, and back on it across a widget's own redraw.

   `focusOn(node)` puts the user on an element that may be no control of its own, as a
   widget hands them back to itself or lands them on a card or a block: an element focus
   would pass by wears `tabindex="-1"` for as long as it holds focus, and loses it as the
   user moves off, so it is no tab stop the author didn't write. An element that
   declares a stop keeps its own. Focus moves without scrolling; a widget that wants
   the element in view reveals it itself.

   `keepFocus(scope)`, read before a redraw that may replace or move the node the user
   is on inside `scope`, returns the step that puts them back once the redraw is done:
   on the same node where it still stands, else on the first stand-in that does, as
   the control that replaced theirs. A stand-in may be a function, asked only once the
   ones before it failed. It returns null where the user is outside `scope`, and its
   step does nothing where they are by then somewhere other than the page's body. It
   reads through open shadow trees; a closed one answers with its host. */

// The element focus is on, followed down through each open shadow tree.
const focused = () => {
  let at = document.activeElement;
  while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  return at;
};

/** @param {Node} node @param {Node} scope */
const within = (node, scope) => {
  /** @type {Node | null} */
  let at = node;
  while (at && at !== scope)
    at = at.parentNode ?? (at instanceof ShadowRoot ? at.host : null);
  return at === scope;
};

/** @param {Element} node */
const holdsFocus = (node) => {
  const root = node.getRootNode();
  return "activeElement" in root && root.activeElement === node;
};

/** @param {Element} element */
export function focusOn(element) {
  const node = /** @type {HTMLElement} */ (element);
  node.focus({ preventScroll: true });
  if (holdsFocus(node) || node.hasAttribute("tabindex")) return;
  node.setAttribute("tabindex", "-1");
  node.focus({ preventScroll: true });
  if (!holdsFocus(node)) {
    node.removeAttribute("tabindex");
    return;
  }
  const leave = () => {
    // A window losing system focus blurs the element but leaves it the document's
    // focused element, which focus returns to with the window.
    if (holdsFocus(node)) return;
    node.removeEventListener("blur", leave);
    if (node.getAttribute("tabindex") === "-1") node.removeAttribute("tabindex");
  };
  node.addEventListener("blur", leave);
}

/** @typedef {Element | null | undefined} StandIn */
/** @param {Node} scope
 * @returns {((...standIns: (StandIn | (() => StandIn))[]) => boolean) | null} */
export function keepFocus(scope) {
  const held = focused();
  if (!held || held === document.body || !within(held, scope)) return null;
  return (...standIns) => {
    const now = focused();
    if (now === held) return true;
    if (now && now !== document.body) return false;
    for (const standIn of [held, ...standIns]) {
      const node = typeof standIn === "function" ? standIn() : standIn;
      if (!node?.isConnected || !("focus" in node)) continue;
      focusOn(node);
      if (focused() === node) return true;
    }
    return false;
  };
}
