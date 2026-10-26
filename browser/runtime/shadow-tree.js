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

// The same two climbs through every node rather than every element: a root, a shadow root
// or the document, is a step of its own, so a reading can stop at a root as well as at an
// element. The parent node, then a shadow root's host:
export const composedParentNode = (node) => node.parentNode ?? shadowHost(node);
// and as rendered, a slotted node's slot first.
const renderedParentNode = (node) => node.assignedSlot ?? composedParentNode(node);
// Is `node` inside `root`, or `root` itself? `Element.contains` stops at a shadow
// boundary and these readings walk through one, so the climb is the same one
// `closestAcross` makes. The boundary decides whether a quote is found at all: a section
// holding an x-shadow widget does not `contains` the words that widget renders, so
// narrowing a search to that section threw away every candidate inside it and the
// passage resolved to nothing — the anchor captured, the mark never painted.
export const under = (node, root) => {
  for (let at = node; at; at = composedParentNode(at)) if (at === root) return true;
  return false;
};
// Containment in the rendered tree, which includes slots and their shadow ancestors.
export const renderedUnder = (node, root) => {
  for (let at = node; at; at = renderedParentNode(at)) if (at === root) return true;
  return false;
};

// Which of two nodes the reader reaches first in the page as rendered: negative when `a`
// is, positive when `b` is, 0 for one node. A node comes before what it holds, so a
// section reaches the reader before the paragraph inside it. `compareDocumentPosition`
// calls nodes in separate shadow trees disconnected, in an implementation-specific
// order, and a host stands for its whole tree only by losing the order inside it, so
// the two rendered ancestries are compared from the top instead: the first nodes where
// they part share a parent, and that parent's tree orders them.
const renderedChain = (node) => {
  const chain = [];
  for (let at = node; at; at = renderedParent(at)) chain.push(at);
  return chain.reverse();
};
export function renderedOrder(a, b) {
  if (a === b) return 0;
  const left = renderedChain(a);
  const right = renderedChain(b);
  let index = 0;
  while (index < left.length && index < right.length && left[index] === right[index])
    index += 1;
  if (index === left.length || index === right.length)
    return left.length - right.length;
  return left[index].compareDocumentPosition(right[index]) &
    Node.DOCUMENT_POSITION_FOLLOWING
    ? -1
    : 1;
}

// `items` in the page's rendered order of their places (`placeOfItem`), those with no
// place after every placed one; items at one place, and the unplaced, keep their given
// order.
export const byRenderedOrder = (items, placeOfItem) => {
  const placed = items.map((item) => ({ item, place: placeOfItem(item) }));
  return [
    ...placed
      .filter(({ place }) => place)
      .sort((a, b) => renderedOrder(a.place, b.place)),
    ...placed.filter(({ place }) => !place),
  ].map(({ item }) => item);
};

// The kind of native layer the browser holds `node` as in the top layer: `"modal"` for a
// dialog shown modally, `"popover"` for an open popover, a dialog opened with
// `showPopover` included, which leaves the page behind it live; else null. A nonmodal open
// dialog is part of the page it stands in. Read node kind rather than realm-specific
// Element: a sample asks this of its frame.
export const nativeLayerKind = (node) => {
  if (node?.nodeType !== Node.ELEMENT_NODE || !node.isConnected) return null;
  if (node.matches("dialog:modal")) return "modal";
  return node.matches(":popover-open") ? "popover" : null;
};
// Whether `node` is itself a native layer, of either kind.
export const isNativeLayer = (node) => nativeLayerKind(node) !== null;

// The innermost native layer `node` stands in as rendered, itself included, or null: a
// box slotted into a popover stands in it.
export function nativeLayerHolding(node) {
  for (let at = node; at; at = renderedParent(at)) if (isNativeLayer(at)) return at;
  return null;
}

// Explicit inertness excludes a node through its composed ancestry. An open native
// modal escapes inherited inertness outside itself, but an inert modal or descendant
// remains excluded. Read node kind rather than realm-specific Element: a sample asks
// this of the frame its containing document holds too.
export function excludedByInert(node) {
  for (let owner = node; owner; owner = renderedParent(owner)) {
    if (owner.inert) return true;
    if (nativeLayerKind(owner) === "modal") break;
  }
  return false;
}
