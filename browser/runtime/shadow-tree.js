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
/** @param {Node | null | undefined} node @returns {node is ShadowRoot} */
const isShadowRoot = (node) =>
  node != null && node.nodeType === node.DOCUMENT_FRAGMENT_NODE && "host" in node;
/** Native event origins can be nodes from another window; Window and other targets are not tree nodes.
 * @param {unknown} node @returns {node is Node} */
export const isNode = (node) =>
  typeof node === "object" &&
  node !== null &&
  "nodeType" in node &&
  typeof node.nodeType === "number";
/** @param {unknown} node @returns {node is Element} */
export const isElement = (node) => isNode(node) && node.nodeType === node.ELEMENT_NODE;
/** @param {Node | null | undefined} node @returns {node is Text} */
export const isText = (node) => node != null && node.nodeType === node.TEXT_NODE;
/** @overload @param {unknown} node @returns {node is HTMLElement} */
/** @template {keyof HTMLElementTagNameMap} K @overload
 * @param {unknown} node @param {K} tag @returns {node is HTMLElementTagNameMap[K]} */
/** @param {unknown} node @param {string} [tag] */
export function isHTML(node, tag) {
  return (
    isElement(node) &&
    node.namespaceURI === "http://www.w3.org/1999/xhtml" &&
    (tag === undefined || node.localName === tag)
  );
}
/** @param {Node | null | undefined} node @returns {node is Element | Text} */
const isSlottable = (node) => isElement(node) || isText(node);
/** @param {Node | null | undefined} root */
export const shadowHost = (root) => (isShadowRoot(root) ? root.host : null);
// The parent, crossing a shadow root's boundary on the way up: the ordinary parent within
// a tree, and the host where a tree runs out. It is the one walk every reading that
// climbs out of a widget takes. Every question the runtime asks about where a node sits —
// which section, which block, which passage cell, whether it is chrome — is asked of the
// page, and a climb that stops at a shadow root answers about the widget's own markup
// instead.
/** @param {Node | null | undefined} node @returns {Element | null} */
export const upFrom = (node) => node?.parentElement ?? shadowHost(node?.getRootNode());
/** Native inline style belongs to HTML, SVG and MathML elements, in any window.
 * @param {Element} node @returns {node is HTMLElement | SVGElement | MathMLElement} */
export const isStyledElement = (node) =>
  node.namespaceURI === "http://www.w3.org/1999/xhtml" ||
  node.namespaceURI === "http://www.w3.org/2000/svg" ||
  node.namespaceURI === "http://www.w3.org/1998/Math/MathML";
// The same step through the tree as rendered: a node slotted into a shadow tree renders
// inside its slot, so the slot is where it is scrolled and ordered, not its light parent.
/** @param {Node | null | undefined} node @returns {Element | null} */
export const renderedParent = (node) =>
  (isSlottable(node) ? node.assignedSlot : null) ?? upFrom(node);

// The same two climbs through every node rather than every element: a root, a shadow root
// or the document, is a step of its own, so a reading can stop at a root as well as at an
// element. The parent node, then a shadow root's host:
/** @param {Node} node @returns {Node | null} */
export const composedParentNode = (node) => node.parentNode ?? shadowHost(node);
// and as rendered, a slotted node's slot first.
/** @param {Node} node @returns {Node | null} */
const renderedParentNode = (node) =>
  (isSlottable(node) ? node.assignedSlot : null) ?? composedParentNode(node);
// Is `node` inside `root`, or `root` itself? `Element.contains` stops at a shadow
// boundary and these readings walk through one, so the climb is the same one
// `closestAcross` makes. The boundary decides whether a quote is found at all: a section
// holding an x-shadow widget does not `contains` the words that widget renders, so
// narrowing a search to that section threw away every candidate inside it and the
// passage resolved to nothing — the anchor captured, the mark never painted.
/** @param {Node | null | undefined} node @param {Node | null | undefined} root */
export const under = (node, root) => {
  for (let at = node; at; at = composedParentNode(at)) if (at === root) return true;
  return false;
};
// Containment in the rendered tree, which includes slots and their shadow ancestors.
/** @param {Node | null | undefined} node @param {Node | null | undefined} root */
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
/** @param {Node | null} node */
const renderedChain = (node) => {
  const chain = [];
  for (let at = node; at; at = renderedParent(at)) chain.push(at);
  return chain.reverse();
};
/** @param {Node} a @param {Node} b */
export function renderedOrder(a, b) {
  if (a === b) return 0;
  const left = renderedChain(a);
  const right = renderedChain(b);
  let index = 0;
  while (index < left.length && index < right.length && left[index] === right[index])
    index += 1;
  const first = left[index];
  const second = right[index];
  if (!first || !second) return left.length - right.length;
  return first.compareDocumentPosition(second) & first.DOCUMENT_POSITION_FOLLOWING
    ? -1
    : 1;
}

// `items` in the page's rendered order of their places (`placeOfItem`), those with no
// place after every placed one; items at one place, and the unplaced, keep their given
// order.
/** @template T @param {readonly T[]} items @param {(item: T) => Node | null | undefined} placeOfItem */
export const byRenderedOrder = (items, placeOfItem) => {
  /** @type {{item: T, place: Node}[]} */
  const placed = [];
  /** @type {T[]} */
  const unplaced = [];
  for (const item of items) {
    const place = placeOfItem(item);
    if (place) placed.push({ item, place });
    else unplaced.push(item);
  }
  return [
    ...placed.sort((a, b) => renderedOrder(a.place, b.place)).map(({ item }) => item),
    ...unplaced,
  ];
};

// The kind of native layer the browser holds `node` as in the top layer: `"modal"` for a
// dialog shown modally, `"popover"` for an open popover, a dialog opened with
// `showPopover` included, which leaves the page behind it live; else null. A nonmodal open
// dialog is part of the page it stands in. Read node kind rather than realm-specific
// Element: a sample asks this of its frame.
/** @param {Node | null | undefined} node */
export const nativeLayerKind = (node) => window.lfLayerState.kind(node);
// Whether `node` is itself a native layer, of either kind.
/** @param {Node | null | undefined} node */
export const isNativeLayer = (node) => nativeLayerKind(node) !== null;

// The innermost native layer `node` stands in as rendered, itself included, or null: a
// box slotted into a popover stands in it.
/** @param {Element | null} node @returns {Element | null} */
export function nativeLayerHolding(node) {
  for (let at = node; at; at = renderedParent(at)) if (isNativeLayer(at)) return at;
  return null;
}

// Explicit inertness excludes a node through its composed ancestry. An open native
// modal escapes inherited inertness outside itself, but an inert modal or descendant
// remains excluded. Read node kind rather than realm-specific Element: a sample asks
// this of the frame its containing document holds too.
/** @param {Node | null} node */
export function excludedByInert(node) {
  for (let owner = node; owner; owner = renderedParent(owner)) {
    if (!isElement(owner)) continue;
    if (isHTML(owner) && owner.inert) return true;
    if (nativeLayerKind(owner) === "modal") break;
  }
  return false;
}
