/* The layer stack: the native layers standing over the page, in the order they opened.

   Prepaint begins the one ordered list before a user can open an authored surface; this
   module adds focus return and runtime effects without restarting that observation.
   The list holds every popover and modal dialog standing over the page, oldest at
   the bottom. Each pushes an entry as it opens, so their order against each other is
   recorded when it happens rather than inferred from focus ancestry and open state at
   every read. `kind` reads each open layer's native mode (`popover` or `modal`); the dispatcher tiers the scopes over them
   and makes a modal a floor.

   A layer may open through a prototype method or through declarative popover activation,
   and a popover need not move focus into itself, so every opener declares its own
   opening in prepaint: the `showModal` and `showPopover` patches, and `beforetoggle` and `toggle`
   at the document and at each declared shadow boundary. `beforetoggle` makes a declarative
   opening visible synchronously to the command that caused it; `toggle` follows the
   completed native transition, and carries an opening whose earlier declarations this
   owner was not yet listening for. An opening arrives once, so a declaration naming a
   layer the stack already holds leaves its entry where the arrival put it, however many
   more times that same opening is declared. The entry keeps the control the layer was
   opened from, its `source`: a declarative opening's (`popovertarget`, `commandfor`) as
   the toggle names it, and a scripted one's from the `showPopover` call itself, since
   the event retargets a source inside a shadow root to its host and goes unheard from a
   root nobody staged. Dismissal stays each layer's own `popover` or `closedby` value. A
   popover opened declaratively inside a shadow root nobody staged fires a `toggle` this
   module cannot hear, so it never reaches the stack; `shadowStage` is the declared route
   for a widget's shadow tree.

   Every read prunes first, and an entry whose surface no longer stands is removed
   wherever it sits, so a dialog closed by script beneath another layer cannot linger as
   a false floor. Modal entry dismisses auto and hint popovers through the platform
   contract; a later opening joins as a new layer rather than preserving a hidden entry.
   The platform spares the popovers a modal dialog stands in, reading that nesting from
   the tree where a popover's comes from its `source`. So a modal opened from a control
   in a popover joins it for that opening (`showNativeLayer`'s `source`): runtime
   chrome carries its styling scope when the popover is authored outside its home.
   The popover, with any draft written in it, still stands when the modal closes;
   the dialog returns to its home as it closes, or as the popover does.
   While a modal stands over an owner, the page beneath is inert, so no press then is
   one away from that owner (`nativeModalAdmits`).
   An owner that reads where the user is before its modal opens dismisses those same
   popovers first (`dismissPopoversOutside`), so the reading finds the user already handed
   back from them.

   Whether a node is one of these layers, or stands in one as rendered, is asked of
   `shadow-tree.js` (`nativeLayerKind`, `isNativeLayer`, `nativeLayerHolding`), below this module and the
   modules it imports, so focus and inertness ask it too. Every reader that treats the top
   layer differently asks there: an anchor cannot reach out of it, it paints over every
   page level, and a cluster keeps its options open while the user visits one.

   Tab is the browser's in every layer. A modal makes the rest of the page inert, so the
   browser walks the user through the modal's stops in its own order, into and out of
   embedded frames, and past either end to its own interface and back, which is how a
   native modal dialog is meant to behave. Rejected: a Leaf loop wrapping Tab from one
   end of a modal to the other. It had to predict the browser's order to find the ends,
   and each prediction missed stops the browser takes (an editable box, a scroll box, a
   positive `tabindex`, a radio group's members), stranding them out of the keyboard's
   reach, and it needed a message protocol to carry Tab across a sample's frame.

   What Escape takes off is not recorded here, and not recorded anywhere: every step is
   read off the state standing in front of the user, by the owner of that state, through
   `pageRung` and the scopes each owner declares. `register.js` orders those steps and
   `dispatch.js` resolves one of them per press. This module answers only which native
   layers the browser is holding, because that is the one fact about the scene that its
   own DOM cannot be asked for in order. */

import {
  releaseFocus,
  closeLayer,
  focused,
  handBack,
  canPlaceFocus,
} from "../focus.js";
import { move } from "../dom-move.js";
import { renderedUnder } from "../shadow.js";
import {
  isHTML,
  isNativeLayer,
  nativeLayerHolding,
  nativeLayerKind,
} from "../shadow-tree.js";
import { chromeSheet } from "../stylesheets.js";
import { watchOwner } from "../arrivals.js";

/** @typedef {{home: NonNullable<HTMLDialogElement["parentNode"]>, chrome: boolean, scope: HTMLElement | null}} ModalHome */
const layerState = window.lfLayerState;
layerState.focused = () => focused();
const watchedRoots = new WeakSet();

// A layer opened while nothing held focus has nobody to hand focus back to as it closes,
// so the browser leaves focus on the hidden control it held until the next rendering
// update drops it, and a key pressed in that frame was dispatched from a control the
// user can no longer see. Closing such a popover lets go at once, as its opening found
// the user: having no current location. A modal is still modal as it announces its close, with the
// page behind it inert, so a let-go there lands no one and only takes the body's stop
// and gives it back; the modal's owner lands the user as it closes it (the Page Map's
// cancellation returns to its opener or reading position; the command reference closes).
// A modal standing in a closing popover (`seatModal`) goes with it, as the popover's own
// nested popovers do, rather than stay modal inside a box no longer shown.
/** @param {ToggleEvent} event */
function closing(event) {
  if (event.newState !== "closed") return;
  const entry = nativeLayers().find((candidate) => candidate.root === event.target);
  if (entry?.kind === "popover")
    for (const layer of nativeLayers().toReversed())
      if (layer.kind === "modal" && renderedUnder(layer.root, entry.root))
        closeNativeLayer(layer.root);
  if (
    entry?.kind === "popover" &&
    entry.fromNowhere &&
    !document.documentElement.inert &&
    canPlaceFocus() &&
    renderedUnder(focused(), entry.root)
  )
    releaseFocus();
}

// Leaf opens native layers through this operation. A sample suppresses the
// platform's automatic focusing steps before opening: they can reveal the containing
// frame even when the child already holds focus. Its owner places focus explicitly
// through focusDestination, which prevents native scrolling. Restoring the layer
// afterward moves no focus. Authored
// scripts keep the native methods; this is the runtime's navigation contract.
/** @overload @param {HTMLDialogElement} layer @param {{source?: Element, modal?: boolean}} [options] @returns {void} */
/** @overload @param {HTMLElement} layer @param {{source?: HTMLElement, modal?: boolean}} [options] @returns {void} */
/** @param {HTMLElement} layer @param {{source?: Element, modal?: boolean}} [options] */
export function showNativeLayer(layer, { source, modal = true } = {}) {
  const withholdFocus = Boolean(document.documentElement.lfSample) && !layer.inert;
  if (withholdFocus) layer.inert = true;
  try {
    if (layer instanceof HTMLDialogElement) {
      if (modal) {
        if (source) seatModal(layer, source);
        layer.showModal();
      } else layer.show();
    } else {
      if (source && !isHTML(source))
        throw new TypeError("A popover source must be an HTML element");
      layer.showPopover(source ? { source } : undefined);
    }
  } finally {
    if (withholdFocus) layer.inert = false;
  }
}

// Native modal entry preserves its source popover only when the modal stands inside
// it. A runtime dialog can cross from chrome into an authored popover: carry its
// private styling scope with it, and adopt the same sheet if that popover is in a
// shadow tree. The source popover and its controls then survive under the modal,
// without a second reopening or focus-return mechanism. Other dialogs keep the
// styles of their own home, so only move within that home. A foreign seat can leave
// with its widget or revision. Native removal keeps a dialog's open attribute and
// emits no close event, so the shared connection lifetime closes and restores it.
/** @type {WeakMap<HTMLDialogElement, ModalHome>} */
const modalHomes = new WeakMap();
/** @param {HTMLDialogElement} dialog @param {Element} source */
function seatModal(dialog, source) {
  let place = modalHomes.get(dialog);
  if (!place) {
    const parent = dialog.parentNode;
    if (!parent) throw new Error("A modal dialog needs a connected home");
    place = {
      home: parent,
      chrome: Boolean(dialog.closest(".lf-chrome")),
      scope: null,
    };
    modalHomes.set(dialog, place);
    const home = place;
    const restore = () => {
      if (dialog.parentNode !== home.home) move(home.home, dialog);
      home.scope?.remove();
    };
    dialog.addEventListener("close", () => {
      if (!dialog.open) restore();
    });
    watchOwner(dialog, {
      disconnect() {
        if (dialog.parentNode === home.home) return;
        closeNativeLayer(dialog);
        restore();
      },
    });
  }
  const holder = nativeLayerHolding(source);
  let seat = place.home;
  if (holder && nativeLayerKind(holder) === "popover") {
    if (renderedUnder(holder, place.home)) seat = holder;
    else if (place.chrome) {
      if (!place.scope) {
        place.scope = document.createElement("div");
        place.scope.className = "lf-chrome";
      }
      const root = holder.getRootNode();
      if (root instanceof ShadowRoot && !root.adoptedStyleSheets.includes(chromeSheet))
        root.adoptedStyleSheets = [...root.adoptedStyleSheets, chromeSheet];
      if (place.scope.parentNode !== holder) move(holder, place.scope);
      seat = place.scope;
    }
  }
  if (dialog.parentNode !== seat) move(seat, dialog);
}

// Closing a native layer may return focus to a remembered opener, including one
// in another modal that escapes ancestor inertness. Inhibit those roots only for
// an actual native close; generic disclosure closes have no native return to stop.
/** @param {HTMLElement} layer */
export function closeNativeLayer(layer) {
  const dialog = layer instanceof HTMLDialogElement;
  if (dialog ? !layer.open : !isNativeLayer(layer)) return;
  const currentLocation = focused();
  const returnTo = nativeLayers().find((entry) => entry.root === layer)?.opener;
  const returnLocally =
    document.documentElement.lfSample &&
    currentLocation &&
    renderedUnder(currentLocation, layer);
  const inhibited = document.documentElement.lfSample
    ? [
        document.documentElement,
        ...nativeLayers()
          .filter((entry) => entry.kind === "modal")
          .map((entry) => entry.root),
      ].filter((node) => !node.inert)
    : [];
  closeLayer(
    () => {
      for (const node of inhibited) node.inert = true;
      try {
        if (dialog) layer.close();
        else layer.hidePopover();
      } finally {
        for (const node of inhibited) node.inert = false;
      }
    },
    returnLocally &&
      (() => {
        if (!canPlaceFocus()) return;
        if (returnTo) handBack(returnTo);
        else releaseFocus();
      }),
  );
}

// Each native layer once it has opened or closed, in the document or any stage, where
// `toggle` does not reach the document: what a modal admits changes with it
// (`nativeModalAdmits`). Returns the call that stops listening.
/** @type {Set<(event: ToggleEvent) => void>} */
const changeListeners = new Set();
/** @param {(event: ToggleEvent) => void} listener */
export function watchLayerChanges(listener) {
  changeListeners.add(listener);
  return () => changeListeners.delete(listener);
}
/** @param {ToggleEvent} event */
const changed = (event) => {
  if (
    !(event.target instanceof HTMLElement) ||
    !event.target.matches("[popover], dialog")
  )
    return;
  for (const listener of changeListeners) listener(event);
};

/** @param {Parameters<Window["lfLayerState"]["watch"]>[0]} root */
export function watchLayers(root) {
  if (watchedRoots.has(root)) return;
  watchedRoots.add(root);
  layerState.watch(root);
  root.addEventListener("beforetoggle", closing, true);
  root.addEventListener("toggle", changed, true);
}

watchLayers(document);

// The layers the browser is holding, bottom to top.
export function nativeLayers() {
  return layerState.read();
}

// Same-origin embedded pages consult the native owner of the document holding their
// frame. The bridge exposes the owner's reading, never a second stack. An ordinary
// host without Leaf cannot supply opening order: require containment in every open
// modal there, so an unobserved layer never becomes evidence that a child was shown.
const NATIVE_LAYERS = Symbol.for("leaf.nativeLayers");
Object.defineProperty(document, NATIVE_LAYERS, { value: nativeLayers });
/** @param {Element} node */
export function nativeModalAdmits(node) {
  /** @type {Document & {[NATIVE_LAYERS]?: () => LeafNativeLayer[]}} */
  const owner = node.ownerDocument;
  const reading = owner[NATIVE_LAYERS];
  if (reading) {
    const modal = reading().findLast((layer) => layer.kind === "modal")?.root;
    return !modal || renderedUnder(node, modal);
  }
  return [...owner.querySelectorAll("dialog")]
    .filter((dialog) => nativeLayerKind(dialog) === "modal")
    .every((modal) => renderedUnder(node, modal));
}

// The auto and hint popovers standing outside `root`, which modal entry dismisses,
// closed newest first. A manual popover is its owner's to close, there as on the page.
/** @param {Element} root */
export function dismissPopoversOutside(root) {
  for (const entry of nativeLayers().toReversed())
    if (
      entry.kind === "popover" &&
      entry.root.popover !== "manual" &&
      !renderedUnder(entry.root, root)
    )
      closeNativeLayer(entry.root);
}
