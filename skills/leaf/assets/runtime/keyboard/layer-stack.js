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
   An owner that reads where the user stands before its modal opens dismisses those same
   popovers first (`dismissPopoversOutside`), so the reading finds the user already handed
   back from them.

   Whether a node stands in one of these layers is asked here too (`nativeLayerHolding`),
   of the tree as rendered, by every reader that treats the top layer differently: an
   anchor cannot reach out of it, it paints over every page level, and a cluster keeps
   its options open while the user visits one.

   A standing modal holds Tab. The browser moves the user through it in its own order,
   but forward from the last stop it leaves the page for its own interface, so this
   module wraps the user from either end of the newest modal to its other end. The wrap
   runs after Leaf's keyboard dispatch, so a mode that walks its own stops with Tab keeps
   the key. A modal that holds more than the user should cycle through, as the
   auxiliary envelope holds its whole foreground beside the covering surface, names the
   region its loop holds as it opens (`showNativeLayer`'s `holds`).

   A frame is one stop of the loop around it, as a sample's Full view holds its frame
   last, but a key pressed inside the frame reaches only the frame's own document. The
   frame's owner tells that document whether its frame stands in a loop (`inLoop`), and
   the document joins it (`joinOuterLoop`): with no modal of its own, its whole body is
   its loop, and Tab past either end of it asks the containing page to move the user on
   past the frame (`movePast`), to the neighbouring stop or round to the other end. The
   containing page decides that when asked, so the frame's document never holds a
   reading of the stops around it. A move that lands on a frame enters its document at
   the matching end through the frame's owner (`enterFrameBy`). A page in a frame
   standing in a loop is itself in that loop, so frames nest.

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
  deepFocus,
  focused,
  focusDestination,
  handBack,
  canPlaceFocus,
  tabStops,
} from "../focus.js";
import { renderedParent, renderedUnder, under } from "../shadow.js";

const entries = [];
const watchedRoots = new WeakSet();
// The region each modal's Tab loop holds, where its opener named one (`showNativeLayer`).
const tabRegions = new WeakMap();
const nativeDialogShowModal = HTMLDialogElement.prototype.showModal;
const nativePopoverShow = HTMLElement.prototype.showPopover;

// Whether `node` is itself a native layer the browser holds in the top layer: an open
// popover or a modal dialog. A nonmodal open dialog is part of the page it stands in.
// Read node kind rather than realm-specific Element: a sample asks this of its frame.
export const isNativeLayer = (node) =>
  node?.nodeType === Node.ELEMENT_NODE &&
  node.isConnected &&
  node.matches(":popover-open, dialog:modal");

// The innermost native layer `node` stands in as rendered, itself included, or null: a
// box slotted into a popover stands in it.
export function nativeLayerHolding(node) {
  for (let at = node; at; at = renderedParent(at)) if (isNativeLayer(at)) return at;
  return null;
}

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
    active: () => isNativeLayer(node),
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
// A modal's Tab loop holds the modal itself, or the region `holds` reads at each press.
export function showNativeLayer(layer, { source, modal = true, holds } = {}) {
  if (holds) tabRegions.set(layer, holds);
  else tabRegions.delete(layer);
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

// Each native layer once it has opened or closed, in the document or any stage, where
// `toggle` does not reach the document: what a modal admits changes with it
// (`nativeModalAdmits`). Returns the call that stops listening.
const changeListeners = new Set();
export function watchLayerChanges(listener) {
  changeListeners.add(listener);
  return () => changeListeners.delete(listener);
}
const changed = (event) => {
  if (!event.target?.matches?.("[popover], dialog")) return;
  for (const listener of changeListeners) listener(event);
};

export function watchLayers(root) {
  if (watchedRoots.has(root)) return;
  watchedRoots.add(root);
  // Native dialog commands also announce their opening here, without invoking
  // the patched prototype. Nonmodal show() entries are pruned by isNativeLayer().
  const opened = (event) => {
    if (event.newState === "open" && event.target?.matches?.("[popover], dialog"))
      pushNativeLayer(event.target);
  };
  root.addEventListener("beforetoggle", opened, true);
  root.addEventListener("beforetoggle", closing, true);
  root.addEventListener("toggle", opened, true);
  root.addEventListener("toggle", changed, true);
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

// The control that names `root` as its `popovertarget`: the platform's own record of
// which button opens a popover, which a scripted reopening hands back as its source.
const declaredInvoker = (root) =>
  root.id
    ? root.getRootNode().querySelector(`[popovertarget="${CSS.escape(root.id)}"]`)
    : null;

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
        showNativeLayer(layer.root, { source: declaredInvoker(layer.root) });
    },
    () => held?.(),
  );
}

// The auto and hint popovers standing outside `root`, which modal entry dismisses,
// closed newest first. A manual popover is its owner's to close, there as on the page.
export function dismissPopoversOutside(root) {
  for (const entry of nativeLayers().toReversed())
    if (
      entry.kind === "popover" &&
      entry.root.popover !== "manual" &&
      !renderedUnder(entry.root, root)
    )
      closeNativeLayer(entry.root);
}

// The loop around the user in this document: the newest modal's region, or, with no
// modal, the whole body where this document's frame stands in a loop around it. `outer`
// is that loop, which takes the user past this document's ends.
let outerLoop = null;
export const joinOuterLoop = (loop) => {
  outerLoop = loop;
};
function currentLoop() {
  const modal = nativeLayers().findLast((entry) => entry.kind === "modal")?.root;
  if (modal) return { region: tabRegions.get(modal)?.() ?? modal, outer: null };
  return outerLoop?.standing() ? { region: document.body, outer: outerLoop } : null;
}
// The stop the user stands at: the innermost one holding `node`, so a control inside a
// component's shadow tree stands at the stop its host declares.
const standingAt = (stops, node) => stops.findLastIndex((stop) => under(node, stop));

// How a frame's owner puts the user inside its document, at its first stop or its last.
const frameEntries = new WeakMap();
export const enterFrameBy = (frame, enter) => {
  frameEntries.set(frame, enter);
  return () => frameEntries.delete(frame);
};
function enter(stop, backward) {
  const entry = frameEntries.get(stop);
  if (entry) entry(backward);
  else focusDestination(stop, "step");
}
// Moves the user from stop `at` of `loop`, one stop on, round from one end to the other,
// or, past an end of a frame's document, on past its frame in the page around it.
function step(loop, stops, at, backward) {
  const next = at + (backward ? -1 : 1);
  if (next >= 0 && next < stops.length) enter(stops[next], backward);
  else if (loop.outer) loop.outer.leave(backward);
  else if (stops.length) enter(backward ? stops.at(-1) : stops[0], backward);
  else focusDestination(loop.region, "step");
}
// Puts the user at this document's first stop in its loop, or its last, as a move
// entering its frame.
export function enterLoop(backward) {
  const loop = currentLoop();
  const stops = loop ? tabStops(loop.region) : [];
  if (stops.length) enter(backward ? stops.at(-1) : stops[0], backward);
}
// Whether `frame` is a stop of the loop around the user here.
export function inLoop(frame) {
  const loop = currentLoop();
  return (
    Boolean(loop) &&
    renderedUnder(frame, loop.region) &&
    tabStops(loop.region).includes(frame)
  );
}
// The user Tabbed past an end of `frame`'s document: they move on past the frame. A
// frame that left the loop's stops since its document heard otherwise has no neighbour,
// so the user goes to the loop's near end rather than nowhere.
export function movePast(frame, backward) {
  const loop = currentLoop();
  if (!loop) return;
  const stops = tabStops(loop.region);
  const at = stops.indexOf(frame);
  step(loop, stops, at >= 0 ? at : backward ? stops.length : -1, backward);
}

// Where Tab would leave the loop around the user, the loop moves them instead: round to
// its other end, or, in a frame's document, on past the frame.
addEventListener("keydown", (event) => {
  if (
    event.defaultPrevented ||
    event.key !== "Tab" ||
    event.altKey ||
    event.ctrlKey ||
    event.metaKey
  )
    return;
  const backward = event.shiftKey;
  const loop = currentLoop();
  if (!loop) return;
  const stops = tabStops(loop.region);
  const at = standingAt(stops, deepFocus());
  if (stops.length && at !== (backward ? 0 : stops.length - 1)) return;
  event.preventDefault();
  step(loop, stops, stops.length ? at : -1, backward);
});
