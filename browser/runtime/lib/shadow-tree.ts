/* Composed ancestry, read from the tree the browser builds and nothing else. Focus and
   shadow rendering share this walk, including slots and roots from another window, and
   with it the one reading of whether a node is an open native layer or stands in one:
   the runtime's dom/keyboard/layer-stack.js keeps the order layers opened in, and imports
   focus and inertness, which ask this too. It also holds the one reading of whether a
   node stands in content the browser skips (`skipper`), which Leaf's suite bundles into
   an init script and so takes from a module that imports nothing. Whether a node stands
   in Leaf's own chrome is the runtime's question (base/ui-marks.js). */
// The host of `root` when it is a shadow root, else null: the one test of whether a climb
// crosses to a host. It asks the root's kind, since other roots answer `host` too — a
// document names its `<form name="host">` there, and a detached subtree's root is an
// element, an `<a>` or `<area>` whose `host` is its URL's. The kind is its node type
// rather than `instanceof ShadowRoot`, whose class belongs to one window: an iframe's
// runtime climbs its parent document's elements out to the frame's place in the page.
export const isShadowRoot = (node: Node | null | undefined): node is ShadowRoot =>
  node != null && node.nodeType === node.DOCUMENT_FRAGMENT_NODE && "host" in node;
/** Native event origins can be nodes from another window; Window and other targets are not tree nodes. */
export const isNode = (node: unknown): node is Node =>
  typeof node === "object" &&
  node !== null &&
  "nodeType" in node &&
  typeof node.nodeType === "number";
export const isElement = (node: unknown): node is Element =>
  isNode(node) && node.nodeType === node.ELEMENT_NODE;
export const isText = (node: Node | null | undefined): node is Text =>
  node != null && node.nodeType === node.TEXT_NODE;
export function isHTML(node: unknown): node is HTMLElement;
export function isHTML<K extends keyof HTMLElementTagNameMap>(
  node: unknown,
  tag: K,
): node is HTMLElementTagNameMap[K];
export function isHTML(node: unknown, tag?: string) {
  return (
    isElement(node) &&
    node.namespaceURI === "http://www.w3.org/1999/xhtml" &&
    (tag === undefined || node.localName === tag)
  );
}
// An SVG element, of the named tag where one is given, in any window.
export function isSVG(node: unknown): node is SVGElement;
export function isSVG<K extends keyof SVGElementTagNameMap>(
  node: unknown,
  tag: K,
): node is SVGElementTagNameMap[K];
export function isSVG(node: unknown, tag?: string) {
  return (
    isElement(node) &&
    node.namespaceURI === "http://www.w3.org/2000/svg" &&
    (tag === undefined || node.localName === tag)
  );
}
const isSlottable = (node: Node | null | undefined): node is Element | Text =>
  isElement(node) || isText(node);
export const shadowHost = (root: Node | null | undefined) =>
  isShadowRoot(root) ? root.host : null;
// The parent, crossing a shadow root's boundary on the way up: the ordinary parent within
// a tree, and the host where a tree runs out. It is the one walk every reading that
// climbs out of a widget takes. Every question the runtime asks about where a node sits —
// which section, which block, which passage cell, whether it is chrome — is asked of the
// page, and a climb that stops at a shadow root answers about the widget's own markup
// instead.
export const upFrom = (node: Node | null | undefined): Element | null =>
  node?.parentElement ?? shadowHost(node?.getRootNode());
// The element a node stands in: the node itself where it is an element, else the
// element holding it, which for a text a shadow root holds straight under it, as an
// age's words or a widget template's top-level text, is the root's host (`upFrom`).
// A text's `parentElement` is null there.
export const holdingElement = (node: Node): Element | null =>
  isElement(node) ? node : upFrom(node);
// What stands for `node` in the tree `root` roots (a Document or a ShadowRoot): the node
// itself when it is in that tree, else the host of the shadow tree holding it, climbed
// out until one is. Null when none is: a detached node, or one outside `root`
// altogether. A shadow tree renders where its host stands, so a range question, which
// the platform answers only within one tree, is asked of this; an order question asks
// `renderedOrder`, which also follows slots.
export const hostIn = <N extends Node>(
  node: N | null | undefined,
  root: Node,
): N | Element | null => {
  let at: N | Element | null = node ?? null;
  while (at && at.getRootNode() !== root) at = shadowHost(at.getRootNode());
  return at;
};
// closest() stops at a shadow boundary, so a node inside a widget's shadow tree can't
// reach the section that holds it or the chrome marker above it — both out in the
// document. Same climb as upFrom, asked with a selector at each tree it passes through.
export function closestAcross(node: Node | null, selector: string): Element | null {
  let el = isElement(node) ? node : upFrom(node);
  while (el) {
    const hit = el.closest(selector);
    if (hit) return hit;
    el = shadowHost(el.getRootNode());
  }
  return null;
}

// The same step through the tree as rendered: a node slotted into a shadow tree renders
// inside its slot, so the slot is where it is scrolled and ordered, not its light parent.
export const renderedParent = (node: Node | null | undefined): Element | null =>
  (isSlottable(node) ? node.assignedSlot : null) ?? upFrom(node);
type RootOf = (host: Element) => ShadowRoot | null;

// The same step taken down, as the browser draws the tree: `each` is handed each node
// drawn as `node`'s child, in order, with any comment among them for the caller to pass
// over, and `eachRenderedElement` each element. A slot in a shadow tree draws what is
// assigned to it, a slot forwarded into it among them, or its own children where nothing
// is; anywhere else a slot is an ordinary element. A host draws the shadow root `rootOf`
// names in place of its children, and a light child only through a slot there: its open
// root by default, and its children where it names none, so a walk names the tree it
// reads: the page reading enters only declared roots (readings/passages.js, `readingChildren`),
// the keyboard's walk a closed stage too, and a walk of one tree none. Each steps from
// sibling to sibling, as a walk does (browser/AGENTS.md, "One answer for each
// question"), since Chromium keeps a node's `children` or `childNodes` list for the
// node's life once it is asked for. A walk of elements steps over the text between them
// unasked: handed every node, Tab stops over a long table take Chromium longer.
//
// A host's open root, read through the platform's own getter, which answers for an
// element of any window: a `<form>` answers `shadowRoot` with its control of that name.
const shadowRootOf = Object.getOwnPropertyDescriptor(Element.prototype, "shadowRoot")
  ?.get as (this: Element) => ShadowRoot | null;
export const openRoot = (host: Element): ShadowRoot | null => shadowRootOf.call(host);
// What `node` draws its children from: the nodes a slot draws in their place, or the
// node or root whose own children they are.
function drawnFrom(node: Node, rootOf: RootOf): Node[] | Node {
  if (isHTML(node, "slot") && isShadowRoot(node.getRootNode())) {
    const assigned = node.assignedNodes();
    if (assigned.length) return assigned;
  }
  return (isElement(node) && rootOf(node)) || node;
}
export function eachRenderedChild(
  node: Node,
  each: (child: Node) => void,
  rootOf: RootOf = openRoot,
) {
  const from = drawnFrom(node, rootOf);
  if (Array.isArray(from)) for (const child of from) each(child);
  else for (let child = from.firstChild; child; child = child.nextSibling) each(child);
}
export function eachRenderedElement(
  node: Node,
  each: (child: Element) => void,
  rootOf: RootOf = openRoot,
) {
  const from = drawnFrom(node, rootOf);
  if (Array.isArray(from)) {
    for (const child of from) if (isElement(child)) each(child);
    return;
  }
  for (
    let child = (from as Partial<ParentNode>).firstElementChild;
    child;
    child = child.nextElementSibling
  )
    each(child);
}

// `root` and every tree under it that `rootOf` names for a host, however deep they nest:
// each tree, then the trees under it, `root`'s own first and then its hosts' in document
// order. The walk finds hosts among each tree's elements, so it costs what `root` holds,
// and keeps the trees still to read in a list rather than calling itself, so no depth of
// nesting runs out the stack. Which trees it enters is the caller's, as for the walks
// above: every open root by default, the declared ones for the page reading, and a closed
// tree only where the caller holds it.
export function treesUnder<R extends Document | DocumentFragment | Element>(
  root: R,
  rootOf: RootOf = openRoot,
): (R | ShadowRoot)[] {
  const trees: (R | ShadowRoot)[] = [];
  const pending: (R | ShadowRoot)[] = [root];
  for (let tree = pending.pop(); tree; tree = pending.pop()) {
    trees.push(tree);
    const inner: ShadowRoot[] = [];
    const own = isElement(tree) ? rootOf(tree) : null;
    if (own) inner.push(own);
    for (const host of tree.querySelectorAll("*")) {
      const held = rootOf(host);
      if (held) inner.push(held);
    }
    for (const held of inner.reverse()) pending.push(held);
  }
  return trees;
}

// The same two climbs through every node rather than every element: a root, a shadow root
// or the document, is a step of its own, so a reading can stop at a root as well as at an
// element. The parent node, then a shadow root's host:
export const composedParentNode = (node: Node): Node | null =>
  node.parentNode ?? shadowHost(node);
// and as rendered, a slotted node's slot first.
const renderedParentNode = (node: Node): Node | null =>
  (isSlottable(node) ? node.assignedSlot : null) ?? composedParentNode(node);
// What one climb says about any two nodes, so its order and containment can't disagree.
// `order` is which of them a reader coming down that tree reaches first: negative when
// `a` is, positive when `b` is, 0 for one node. A node comes before what it holds, so a
// section reaches the reader before the paragraph inside it. `compareDocumentPosition`
// calls nodes in separate shadow trees disconnected, in an implementation-specific
// order, and a host stands for its whole tree only by losing the order inside it, so the
// two ancestries are compared from the top instead: the first nodes where they part
// share a parent, and that parent's tree orders them. A host's shadow root and its other
// children share a parent and no tree, and the root comes first. `ordering()` answers
// the same for a sort of many nodes, reading each node's climb once and each parent's
// children once, where a comparison alone would read both climbs and walk the siblings
// between the two. `under` is whether `node` is inside `root`, or `root` itself.
export function alongClimb(parentOf: (node: Node) => Node | null) {
  const chain = (node: Node) => {
    const nodes = [];
    for (let at = node as Node | null; at; at = parentOf(at)) nodes.push(at);
    return nodes.reverse();
  };
  const inTree = (first: Node, second: Node) =>
    first.compareDocumentPosition(second) & first.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
  const ordered = (
    left: Node[],
    right: Node[],
    siblings: (first: Node, second: Node) => number,
  ) => {
    let index = 0;
    while (index < left.length && index < right.length && left[index] === right[index])
      index += 1;
    const first = left[index];
    const second = right[index];
    if (!first || !second) return left.length - right.length;
    if (isShadowRoot(first)) return -1;
    if (isShadowRoot(second)) return 1;
    return siblings(first, second);
  };
  return {
    order: (a: Node, b: Node) => (a === b ? 0 : ordered(chain(a), chain(b), inTree)),
    ordering() {
      const chains: Map<Node, Node[]> = new Map();
      const chainOf = (node: Node) => {
        let nodes = chains.get(node);
        if (!nodes) chains.set(node, (nodes = chain(node)));
        return nodes;
      };
      const indices: Map<Node, Map<Node, number>> = new Map();
      const indexIn = (parent: Node, child: Node) => {
        let at = indices.get(parent);
        if (!at) {
          at = new Map();
          let index = 0;
          for (let node = parent.firstChild; node; node = node.nextSibling)
            at.set(node, index++);
          indices.set(parent, at);
        }
        return at.get(child)!;
      };
      // Children of one node in its own tree stand in the order of its child list;
      // anything else, such as a slot's fallback beside what it is assigned, is left to
      // the tree as `order` leaves it.
      const siblings = (first: Node, second: Node) => {
        const parent = first.parentNode;
        return parent && parent === second.parentNode
          ? indexIn(parent, first) - indexIn(parent, second)
          : inTree(first, second);
      };
      return (a: Node, b: Node) =>
        a === b ? 0 : ordered(chainOf(a), chainOf(b), siblings);
    },
    under(node: Node | null | undefined, root: Node | null | undefined) {
      for (let at = node; at; at = parentOf(at)) if (at === root) return true;
      return false;
    },
  };
}
// Is `node` inside `root`, or `root` itself? `Element.contains` stops at a shadow
// boundary and these readings walk through one, so the climb is the same one
// `closestAcross` makes. The boundary decides whether a quote is found at all: a section
// holding a `shadow` widget does not `contains` the words that widget renders, so a
// search narrowed to that section by `contains` would find no candidate inside it.
export const under = alongClimb(composedParentNode).under;
// Which of two nodes the reader reaches first in the page as rendered, and containment in
// the rendered tree, which includes slots and their shadow ancestors.
const rendered = alongClimb(renderedParentNode);
export const renderedOrder = rendered.order;
export const renderedOrdering = rendered.ordering;
export const renderedUnder = rendered.under;

// The nearest element at or over `el` that matches `selector`, read within one frame:
// above the frame it is nobody's, and with no frame at all it is the document's own
// reading, unchanged.
export const overIn = (
  el: Element,
  selector: string,
  frame: Element | null | undefined,
) => {
  const near = el.closest(selector);
  return near && (!frame || under(near, frame)) ? near : null;
};
// `items` in the page's rendered order of their places (`placeOfItem`), those with no
// place after every placed one; items at one place, and the unplaced, keep their given
// order.
export const byRenderedOrder = <T>(
  items: readonly T[],
  placeOfItem: (item: T) => Node | null | undefined,
) => {
  const placed: { item: T; place: Node }[] = [];
  const unplaced: T[] = [];
  for (const item of items) {
    const place = placeOfItem(item);
    if (place) placed.push({ item, place });
    else unplaced.push(item);
  }
  const order = renderedOrdering();
  return [
    ...placed.sort((a, b) => order(a.place, b.place)).map(({ item }) => item),
    ...unplaced,
  ];
};

// The kind of native layer the browser holds `node` as in the top layer: `"modal"` for a
// dialog shown modally, `"popover"` for an open popover, a dialog opened with
// `showPopover` included, which leaves the page behind it live; else null. A nonmodal open
// dialog is part of the page it stands in. Read node kind rather than realm-specific
// Element: a sample asks this of its frame.
export const nativeLayerKind = (node: Node | null | undefined) => {
  if (!isElement(node) || !node.isConnected) return null;
  if (node.matches("dialog:modal")) return "modal";
  return node.matches(":popover-open") ? "popover" : null;
};
// Whether `node` is itself a native layer, of either kind.
export const isNativeLayer = (node: Node | null | undefined) =>
  nativeLayerKind(node) !== null;

// The innermost native layer `node` stands in as rendered, itself included, or null: a
// box slotted into a popover stands in it.
export function nativeLayerHolding(node: Element | null): Element | null {
  for (let at = node; at; at = renderedParent(at)) if (isNativeLayer(at)) return at;
  return null;
}

// Explicit inertness excludes a node through its composed ancestry. An open native
// modal escapes inherited inertness outside itself, but an inert modal or descendant
// remains excluded. Read node kind rather than realm-specific Element: a sample asks
// this of the frame its containing document holds too.
export function excludedByInert(node: Node | null) {
  for (let owner = node; owner; owner = renderedParent(owner)) {
    if (!isElement(owner)) continue;
    if (isHTML(owner) && owner.inert) return true;
    if (nativeLayerKind(owner) === "modal") break;
  }
  return false;
}

// Whether `el` stands in content the browser skips: what a `content-visibility: hidden`
// box holds, which a hidden tab's panel (`hidden="until-found"`) is, what an
// off-screen `content-visibility: auto` box holds, which a long text document's runs
// are, and a closed disclosure's content. The browser leaves skipped content unstyled and unlaid, and one
// question about any box inside — its computed style, its rect, its scroll offsets —
// makes it style and lay out that whole subtree first to answer. On a page whose parts
// stand in hidden tabs, as the corpus's do, those forced passes can be most of a
// revision's style time. So a reading that has nothing to say about a box on no screen
// — where it stands, whether it scrolls, what room it takes — asks this first and
// leaves the box out until a pass after it is drawn: revealing a panel or opening a
// disclosure resizes what holds it, which brings those passes round. An `auto` box
// draws what it holds at the size it already had, so a reading that follows it hears
// the box say so (`contentvisibilityautostatechange`). A reading that marks what the
// user will see once it is drawn (an anchor's outline) still asks, and pays.
//
// Answered without forcing anything: `checkVisibility({contentVisibilityAuto: true})`
// reads the tree the browser has, and is false for a box that is not drawn for any
// reason. Without that option the browser styles skipped `auto` content to answer, which
// over a long text document's lines restyled every run on the first scroll. The nearest
// drawn ancestor says which reason — a box skipping what it holds, or `display:
// none`/`contents` on the way down, which are not skipped and cheap to ask about — and
// it is drawn, so its own style is not skipped either. A disclosure skips through a
// pseudo-element of its own, so it is asked by its state rather than by its style.
//
// `skipper` names the box that skips `el`, so a reading over many elements under it,
// such as a long text document's lines in one run, asks once and passes over the rest.
export const drawn = (box: Element) =>
  box.checkVisibility({ contentVisibilityAuto: true });
export const skipper = (element: Element): Element | null => {
  if (drawn(element)) return null;
  let child = element;
  let box = renderedParent(element);
  while (box && !drawn(box)) {
    child = box;
    box = renderedParent(box);
  }
  if (!box) return null;
  if (box.localName === "details")
    return !box.hasAttribute("open") && child.localName !== "summary" ? box : null;
  return getComputedStyle(box).contentVisibility !== "visible" ? box : null;
};
export const skipped = (element: Element) => Boolean(skipper(element));

// The closed box that hides `node` until the user opens it: a closed `<details>` holding
// it outside its summary, or a box `hidden="until-found"` (an unchosen tab's panel, a
// file a diff filters out), `node` itself or one round it. These are the boxes the
// browser's find opens, and Leaf's travel too (dom/widget-elements.js, `reveal`), so they
// are read from the markup, whatever a stylesheet draws in their place: a package may
// keep a hidden panel's layout and only make it invisible. Where closed boxes nest, it
// is the outermost, the one the page shows. An off-screen `content-visibility: auto`
// box is no closed box: it draws what it holds as the window nears it.
export const closedOver = (node: Node): Element | null => {
  let closed = null;
  let child: Node = node;
  for (let at = node instanceof Element ? node : renderedParent(node); at;) {
    if (
      untilFound(at) ||
      (at instanceof HTMLDetailsElement &&
        !at.open &&
        child !== at &&
        !(child instanceof HTMLElement && child.localName === "summary"))
    )
      closed = at;
    child = at;
    at = renderedParent(at);
  }
  return closed;
};
// Whether `node` is `hidden="until-found"`, read as the browser reads the attribute.
export const untilFound = (node: Node | null) =>
  node instanceof HTMLElement && node.hidden === "until-found";

// Every element the browser draws at or under `root`, through the open shadow trees of
// the hosts it draws, each tree in its own order, which a reading of the page as drawn
// walks (render-checks/open-roots.js, `drawnPage`). An element that draws no box of its
// own, under `display: contents` or a slot, is left out and what it holds is walked. A
// box under `content-visibility: hidden`, such as a folded tab panel, skips everything
// it holds, so once `skipper` names it for one child the rest go unasked. An `auto` box
// on screen draws the children beside one that draws no box, and a closed disclosure
// draws its summary wherever it stands, so under either each child is asked whether it
// is drawn, though nothing it holds is asked. A slotted child stands in its slot rather
// than beside its siblings, so each asks for itself, and a host draws no child that no
// slot takes.
//
// One case goes unwalked: a `display: contents` child of an `auto` box on screen.
// `skipper` names the box for any child of it that draws no box, on screen or not, and
// telling such a child from a skipped line would mean asking each undrawn child its
// `display`, which makes the browser style it.
export function drawnElements(root: Element): Element[] {
  const found: Element[] = [];
  const within = (child: Element | null, hosted: boolean) => {
    // Whether `skipper` named a box for an earlier child. It names the same box for
    // every later child the browser doesn't draw, since its climb starts from the
    // parent they share.
    let skipping = false;
    for (; child; child = child.nextElementSibling) {
      if (drawn(child)) {
        found.push(child);
        walk(child);
        continue;
      }
      if (hosted && !child.assignedSlot) continue;
      if (skipping && !child.assignedSlot) continue;
      const box = skipper(child);
      if (box) {
        if (child.assignedSlot) continue;
        if (getComputedStyle(box).contentVisibility === "hidden") return;
        skipping = true;
        continue;
      }
      if (getComputedStyle(child).display === "contents") walk(child);
    }
  };
  const walk = (parent: Element) => {
    const shadow = parent.shadowRoot;
    if (shadow) within(shadow.firstElementChild, false);
    within(parent.firstElementChild, shadow !== null);
  };
  if (drawn(root)) {
    found.push(root);
    walk(root);
  }
  return found;
}
