/* This module owns the shared resizable boundary the thread panel and tray panels are
 * drawn by: its width, its keys and handle, and the user's remembered answer. How the
 * shell takes a new width is the layout writer's (`land`, chrome-layout.js's landEdge),
 * handed to each edge, so this module stays outside the owner cycle and an edge can be
 * drawn as its owner evaluates. */
import { userStore } from "./storage.js";
import { el } from "./widget-elements.js";
import { keys } from "./keyboard/scopes.js";
import { setRuntimeRootStyle } from "./root-state.js";

// The step an arrow takes, in the column's own gutter: the smallest move that shows in a
// page of prose.
const EDGE_STEP = 24;
let activeResize = null;

/** A region held to one side of the window, and the boundary the user draws it by.
 *
 * The page has two — the thread panel on the right, the tray panel on the left — and
 * they are the same furniture reflected, so this is one function rather than two
 * near-copies. What differs is what it is handed: which side the region is held to, the
 * width it stands at until the user says otherwise, how narrow they may draw it, the
 * property the cascade reads the standing width from, the key their store keeps the choice
 * under, and one noun, which every surface that names the region says in its own sentence.
 * Nothing below differs, which is the point: the second edge cost a call rather than a
 * copy, and a third would too.
 *
 * The width the user asked for and the width the region stands at are two facts rather
 * than one. A window too narrow to honour a choice does not un-make it, and widening that
 * window again is not a request to be told what the user once said — so the choice is
 * kept and the standing width is derived from it. Everything reads `width`; nothing holds
 * the number.
 *
 * One width, and a handle for each region on that side: the left edge holds two trays one
 * at a time, and each wears the edge it is drawn by, because a handle outside them both
 * would not slide in with the tray it belongs to. They are handles onto one fact rather
 * than two facts — `state` is the one writer, and it says the same thing on every one.
 */
export function drawnEdge({ side, noun, wide, min, prop, key, when, land }) {
  const handles = new Set();
  let chosen = wide;
  // What the window will allow: the window itself. How much of the page a region may take
  // before it covers the page instead is not this bound's to say; the room the region
  // leaves decides that, the same way on either side (auxiliary-surfaces.js,
  // `standsBeside`), so a user drawing a region past a usable page gets the region they
  // drew, covering the page, rather than an edge that stops short of their hand.
  const cap = () => document.documentElement.clientWidth;
  // The floor gives way to the cap and not the other way about: a window too narrow for
  // the floor is still the window, and a region wider than the one it stands in has put
  // its own controls off the screen. Asked in two places and written once — of a width the
  // user is dragging to, so the edge never goes anywhere their hand did not, and of the
  // width they chose on some other day, whose window is not this one.
  const held = (want) => Math.min(cap(), Math.max(min, want));
  const width = () => held(chosen);
  // The one writer of the property the cascade reads that width from: the region's own box
  // and the strip the page yields are both stated against it. Written rather than read back
  // off the region because a closed one measures zero, which is exactly when the page most
  // needs to know how wide it will be. The runtime's own readers — the shortcut bar's cap, the
  // room a wide widget spends — ask `width` instead of this property, so what the cascade
  // lays out and what the runtime measures cannot come apart.
  function state() {
    setRuntimeRootStyle(document.documentElement, prop, width() + "px");
    // Where the edge stands and how far it may go, which is what a listener hears change
    // on every step — the platform's own announcement, and the whole reason the edge is a
    // separator. The cap moves with the window, so it is restated wherever the width is.
    for (const handle of handles) {
      handle.setAttribute("aria-valuenow", String(Math.round(width())));
      handle.setAttribute("aria-valuemax", String(Math.round(cap())));
      // A boundary with no distance to travel is not a control. This happens to the
      // comment sheet at the supported 320px floor: leaving its separator in the tab
      // order promised a resize no pointer or arrow could make. Transfer a user who
      // was standing on it before taking it away — the browser otherwise silently
      // drops focus to body during a rotation that closes the range.
      const fixed = cap() <= min;
      if (fixed && handle === document.activeElement)
        handle.lfFixedFocus().focus({ preventScroll: true });
      handle.hidden = fixed;
    }
  }
  // The user's answer, taken and kept. Held to the window on the way in, because a drag
  // is direct: what they see is what they asked for, and storing a width the window
  // refused would hand it back to them on some later window as a place they never put the
  // edge.
  function set(want) {
    chosen = Math.round(held(want));
    userStore.set(key, String(chosen));
    land(state);
  }
  /** The region's own edge, said as what it is: a separator between two regions, which is
   * the platform's word for a boundary the user moves. That word is worth having for
   * what comes with it — the edge carries the width it stands at, so an arrow step is
   * announced by the platform itself, where a press built for the job would have had to say
   * so in words of its own and would have promised an activation an edge has not got.
   *
   * It goes in the region rather than beside it, so it travels with whatever the region
   * does: the tray panel's edge slides in with the tray standing on it, and a closed
   * region's edge is hidden by the same rule that hides the region.
   */
  function handle(region, fixedFocus) {
    const edge = el("div", "lf-ui lf-edge");
    // The owner names the control that survives when this edge has no range. Stored on
    // the handle because state walks all mirrored handles together, while the target is
    // each region's own — the thread panel closes, each tray returns to its toggle.
    edge.lfFixedFocus = fixedFocus;
    edge.dataset.lfSide = side;
    edge.setAttribute("role", "separator");
    edge.setAttribute("aria-orientation", "vertical");
    edge.setAttribute("aria-label", `${noun[0].toUpperCase()}${noun.slice(1)} width`);
    edge.setAttribute("aria-valuemin", String(min));
    edge.tabIndex = 0;
    // Where on the edge the user took hold, kept for the length of the drag so the
    // boundary stays under the point they grabbed. Without it the region jumps by up to
    // the handle's own width on the first move, which is the page moving under an aim that
    // had just arrived.
    edge.addEventListener("pointerdown", (event) => {
      if (activeResize || !event.isPrimary || event.button !== 0) return;
      // A fresh native pointer focus clears a keyboard ring even when this handle
      // already owns focus. Cancelling pointerdown and focusing by script preserves
      // that ring. The chrome's user-select rule already protects page selections.
      edge.blur();
      edge.setPointerCapture(event.pointerId);
      const box = region.getBoundingClientRect();
      activeResize = {
        edge,
        pointerId: event.pointerId,
        grab: event.clientX - (side === "right" ? box.left : box.right),
      };
      document.body.toggleAttribute("data-lf-sizing", true);
    });
    edge.addEventListener("pointermove", (event) => {
      if (
        activeResize?.edge !== edge ||
        activeResize.pointerId !== event.pointerId ||
        !edge.hasPointerCapture(event.pointerId)
      )
        return;
      // The region's far edge is the window's, so the width is what the pointer leaves
      // between the two — read off the window rather than off the region, which is the box
      // this is about to resize.
      const at = event.clientX - activeResize.grab;
      set(side === "right" ? document.documentElement.clientWidth - at : at);
    });
    // Resizing is not an outside press on the page's open composer. Keep native
    // pointer focus, but consume the compatibility press in its gesture owner.
    edge.addEventListener("mousedown", (event) => event.stopPropagation());
    // A touch drag may generate no compatibility mouse event to focus the handle.
    // Completion, cancellation, and capture loss end only the gesture this edge began.
    const finish = (event) => {
      if (activeResize?.edge !== edge || activeResize.pointerId !== event.pointerId)
        return;
      activeResize = null;
      edge.focus({ preventScroll: true });
      document.body.toggleAttribute("data-lf-sizing", false);
    };
    for (const ending of ["pointerup", "pointercancel", "lostpointercapture"])
      edge.addEventListener(ending, finish);
    // Arrows, and not a pair of letters, because the user is standing on the edge
    // itself — the direction is the whole of what they have left to say. Away from the
    // side the region is held to widens it, which is the same reading the pointer makes of
    // the same gesture.
    const wider = side === "right" ? "ArrowLeft" : "ArrowRight";
    keys(
      edge,
      `On the ${noun}'s edge`,
      [
        {
          id: "region.resize",
          keys: ["ArrowLeft", "ArrowRight"],
          routes: [
            {
              id: "region.resize-left",
              binding: "ArrowLeft",
              does: `Move the ${noun}'s edge left`,
            },
            {
              id: "region.resize-right",
              binding: "ArrowRight",
              does: `Move the ${noun}'s edge right`,
            },
          ],
          label: "arrows",
          does: `Resize the ${noun}`,
          line: `resize the ${noun}`,
          repeat: true,
          run: (binding) => set(width() + (binding === wider ? EDGE_STEP : -EDGE_STEP)),
        },
      ],
      when,
    );
    handles.add(edge);
    region.prepend(edge);
    state();
    return edge;
  }
  // The user's own answer, put back over the default at the foot of the module, where
  // every other remembered arrangement is restored. Stated whether or not they have chosen
  // one, since a user who has said nothing is a user whose answer is the default.
  function restore() {
    chosen = parseFloat(userStore.get(key)) || wide;
    state();
  }
  return { width, state, restore, handle, key };
}
