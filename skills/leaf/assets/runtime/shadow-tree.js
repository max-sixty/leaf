/* Composed ancestry without runtime dependencies. Focus and shadow rendering share
   this walk, including slots and roots from another window, and with it the one reading
   of whether a node is an open native layer or stands in one: keyboard/layer-stack.js
   keeps the order layers opened in, and imports focus and inertness, which ask this
   too. */
// The host of `root` when it is a shadow root, else null: the one test of whether a climb
// crosses to a host. It asks the root's kind, since other roots answer `host` too — a
// document names its `<form name="host">` there, and a detached subtree's root is an
// element, an `<a>` or `<area>` whose `host` is its URL's. The kind is its node type
// rather than `instanceof ShadowRoot`, whose class belongs to one window: an iframe's
// runtime climbs its parent document's elements out to the frame's place in the page.
export const shadowHost = (root) =>
  root?.nodeType === Node.DOCUMENT_FRAGMENT_NODE ? (root.host ?? null) : null;
// The parent, crossing a shadow root's boundary on the way up: the ordinary parent within
// a tree, and the host where a tree runs out. It is the one walk every reading that
// climbs out of a widget takes. Every question the runtime asks about where a node sits —
// which section, which block, which passage cell, whether it is chrome — is asked of the
// page, and a climb that stops at a shadow root answers about the widget's own markup
// instead.
export const upFrom = (node) => node?.parentElement ?? shadowHost(node?.getRootNode());
// The same step through the tree as rendered: a node slotted into a shadow tree renders
// inside its slot, so the slot is where it is scrolled and ordered, not its light parent.
export const renderedParent = (node) => node?.assignedSlot ?? upFrom(node);
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
