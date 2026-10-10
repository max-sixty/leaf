/* The layer stack: the native layers standing over the page, in the order they opened.

   One ordered list holds every popover and modal dialog standing over the page, oldest at
   the bottom. Each pushes an entry as it opens, so their order against each other is
   recorded when it happens rather than inferred from focus ancestry and open state at
   every read. `kind` reads the standing native mode (`popover` or `modal`); the dispatcher tiers the scopes over them
   and makes a modal a floor.

   A layer may open through a prototype method or through declarative popover activation,
   and a popover need not move focus into itself, so every opener declares its own
   opening here: the `showModal` and `showPopover` patches, and `beforetoggle` and `toggle`
   at the document and at each declared shadow boundary. `beforetoggle` makes a declarative
   opening visible synchronously to the command that caused it; `toggle` follows the
   completed native transition, and carries an opening whose earlier declarations this
   module was not yet listening for. An opening arrives once, so a declaration naming a
   layer the stack already holds leaves its entry where the arrival put it, however many
   more times that same opening is declared. Dismissal stays each layer's own `popover`
   or `closedby` value. A popover opened declaratively inside a shadow root nobody staged
   fires a `toggle` this module cannot hear, so it never reaches the stack; `shadowStage`
   is the declared route for a widget's shadow tree.

   Every read prunes first, and an entry whose surface no longer stands is removed
   wherever it sits, so a dialog closed by script beneath another layer cannot linger as
   a false floor. Modal entry dismisses auto and hint popovers through the platform
   contract; a later opening joins as a new layer rather than preserving a hidden entry.

   What Escape takes off is not recorded here, and not recorded anywhere: every step is
   read off the state standing in front of the user, by the owner of that state, through
   `pageRung` and the scopes each owner declares. `register.js` orders those steps and
   `dispatch.js` resolves one of them per press. This module answers only which native
   layers the browser is holding, because that is the one fact about the scene that its
   own DOM cannot be asked for in order. */

import {
  releaseFocus,
  holdFocus,
  closeLayer,
  focused,
  handBack,
  canPlaceFocus,
} from "../focus.js";
import { renderedUnder } from "../shadow.js";

const entries = [];
const watchedRoots = new WeakSet();
const nativeDialogShowModal = HTMLDialogElement.prototype.showModal;
const nativePopoverShow = HTMLElement.prototype.showPopover;

const held = (node) =>
  Boolean(node?.isConnected) && node.matches(":popover-open, dialog:modal");

function prune() {
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    if (!entries[index].active()) entries.splice(index, 1);
  }
}

// A standing entry is left alone wherever it sits, and not merely where it is already on
// top: `toggle` is queued rather than synchronous, so moving a layer on that last
// declaration would make it the newest thing on the stack after something else opened over
// it. A closed entry is pruned and an actual reopening joins at the top.
function pushNativeLayer(node) {
  const at = entries.findIndex((entry) => entry.root === node);
  const standing = at < 0 ? null : entries[at];
  if (standing?.active()) return;
  prune();
  const holding = focused();
  entries.push({
    root: node,
    get kind() {
      return node.matches(":modal") ? "modal" : "popover";
    },
    active: () => held(node),
    fromNowhere: !holding || holding === document.body,
    opener: holding && holding !== document.body ? holding : null,
  });
}

// A layer opened while nothing held focus has nobody to hand focus back to as it closes,
// so the browser leaves focus on the hidden control it held until the next rendering
// update drops it, and a key pressed in that frame was dispatched from a control the
// user can no longer see. Closing such a popover lets go at once, as its opening found
// the user: standing nowhere. A modal is still modal as it announces its close, with the
// page behind it inert, so a let-go there lands no one and only takes the body's stop
// and gives it back; the modal's owner lands the user as it closes it (the Page Map's
// cancellation returns to its opener or reading position; the command reference closes).
function closing(event) {
  if (event.newState !== "closed") return;
  const entry = entries.find((candidate) => candidate.root === event.target);
  if (
    entry?.kind === "popover" &&
    entry.fromNowhere &&
    !document.documentElement.inert &&
    canPlaceFocus() &&
    renderedUnder(focused(), event.target)
  )
    releaseFocus();
}

HTMLDialogElement.prototype.showModal = function () {
  if (!this.matches(":modal")) pushNativeLayer(this);
  return nativeDialogShowModal.call(this);
};

HTMLElement.prototype.showPopover = function (...args) {
  if (!this.matches(":popover-open")) pushNativeLayer(this);
  return nativePopoverShow.apply(this, args);
};

// Leaf opens native layers through this operation. A sample suppresses the
// platform's automatic focusing steps before opening: they can reveal the containing
// frame even when the child already holds focus. Its owner places focus explicitly
// through focusDestination, which prevents native scrolling. Restoring the layer
// afterward moves no focus. Authored
// scripts keep the native methods; this is the runtime's navigation contract.
export function showNativeLayer(layer, { source, modal = true } = {}) {
  const withholdFocus = Boolean(document.documentElement.lfSample) && !layer.inert;
  if (withholdFocus) layer.inert = true;
  try {
    if (layer instanceof HTMLDialogElement) {
      if (modal) layer.showModal();
      else layer.show();
    } else layer.showPopover(source ? { source } : undefined);
  } finally {
    if (withholdFocus) layer.inert = false;
  }
}

// Closing a native layer may return focus to a remembered opener, including one
// in another modal that escapes ancestor inertness. Inhibit those roots only for
// an actual native close; generic disclosure closes have no native return to stop.
export function closeNativeLayer(layer) {
  const dialog = layer instanceof HTMLDialogElement;
  if (dialog ? !layer.open : !layer.matches(":popover-open")) return;
  const standing = focused();
  const returnTo = entries.find((entry) => entry.root === layer)?.opener;
  const returnLocally =
    document.documentElement.lfSample && standing && renderedUnder(standing, layer);
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

export function watchLayers(root) {
  if (watchedRoots.has(root)) return;
  watchedRoots.add(root);
  // Native dialog commands also announce their opening here, without invoking
  // the patched prototype. Nonmodal show() entries are pruned by held().
  const opened = (event) => {
    if (event.newState === "open" && event.target?.matches?.("[popover], dialog"))
      pushNativeLayer(event.target);
  };
  root.addEventListener("beforetoggle", opened, true);
  root.addEventListener("beforetoggle", closing, true);
  root.addEventListener("toggle", opened, true);
}

watchLayers(document);

// The layers the browser is holding, bottom to top.
export function nativeLayers() {
  prune();
  return entries.filter((entry) => entry.active());
}

// Same-origin embedded pages consult the native owner of the document holding their
// frame. The bridge exposes the owner's reading, never a second stack. An ordinary
// host without Leaf cannot supply opening order: require containment in every standing
// modal there, so an unobserved layer never becomes evidence that a child was shown.
const NATIVE_LAYERS = Symbol.for("leaf.nativeLayers");
Object.defineProperty(document, NATIVE_LAYERS, { value: nativeLayers });
export function nativeModalAdmits(node) {
  const owner = node.ownerDocument;
  const reading = owner[NATIVE_LAYERS];
  if (reading) {
    const modal = reading().findLast((layer) => layer.kind === "modal")?.root;
    return !modal || renderedUnder(node, modal);
  }
  return [...owner.querySelectorAll("dialog:modal")].every((modal) =>
    renderedUnder(node, modal),
  );
}

// Raising a native ancestor appends it above its standing descendants. Re-seat those
// same layers after its transition, in their native order; their owners and retained
// nodes keep the reading and the eventual return. The browser state changes in one
// turn, before any queued close event can see a descendant left closed.
export function transitionNativeAncestor(root, transition) {
  const descendants = nativeLayers().filter(
    (layer) => layer.root !== root && renderedUnder(layer.root, root),
  );
  const held = holdFocus(root);
  closeLayer(
    () => {
      for (const layer of descendants.toReversed()) closeNativeLayer(layer.root);
      transition();
      for (const layer of descendants)
        showNativeLayer(layer.root, { source: layer.root.lfInvoker });
    },
    () => held?.(),
  );
}

// Modal owners close pre-existing popovers before establishing a new floor.
export const openPopovers = () =>
  nativeLayers()
    .filter((entry) => entry.kind === "popover")
    .map((entry) => entry.root);
