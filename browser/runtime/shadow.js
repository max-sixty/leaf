/* This module owns declared shadow roots, the shadow.css rules they render under, and
 * the shared highlight rules. */
import { isStage, liveStages } from "./arrivals.js";
import { registry } from "./registry.js";
export { overIn, SAID, UI_MARKS, uiInside, inUi } from "./shadow-tree.js";
import {
  isElement,
  isHTML,
  excludedByInert,
  byRenderedOrder,
  composedParentNode,
  renderedOrder,
  renderedParent,
  renderedUnder,
  shadowHost,
  under,
  upFrom,
} from "./shadow-tree.js";
export {
  excludedByInert,
  byRenderedOrder,
  composedParentNode,
  renderedOrder,
  renderedParent,
  renderedUnder,
  shadowHost,
  under,
  upFrom,
};

// The open shadow roots under some root that hold the page's own words, from what the
// registry declares rather than from a sweep of every element: an x-shadow widget is
// making a promise about whose words those are, and a root some other library happened
// to attach is not covered by it. `getComposedRanges` is told exactly these, so what the
// capture can see and what the reading walks are one list.
//
// Which root to look under is the axis, because the whole document is not the only
// answer: a message arriving in the panel carries widget markup that upgrades in a
// subtree, so a pass over that subtree has the same boundary to cross and no document
// to ask about. A root is found under `root` as a selector would find its host: `root`
// itself or an element in `root`'s own tree, not one inside another root.
//
// A declared root is the stage an x-shadow widget built through `shadowStage`, so the
// roots come from the stages' registry (`liveStages`, arrivals.js), not from a query of
// `root`. Every id the document doesn't hold is looked for here (`elementById`,
// passages.js), as is an obligation's widget in a thread no one has opened, on every
// paint that places it, so this answer costs the number of stages, not the size of the
// page. A root attached any other way carries none of a stage's marks or watches, and
// its host reads as one with no declared root: by its own children.
//
// A root refused for holding bare text (passages.js, `refusesBareText`) leaves the list for
// good, and its host reads the same way.
/** @type {WeakSet<ShadowRoot>} */
const refusedRoots = new WeakSet();
/** @param {ShadowRoot} root */
export const refuseShadowRoot = (root) => refusedRoots.add(root);
// The declared root `host` holds the page's words in, or null.
/** @param {Element} host */
export const declaredRoot = (host) =>
  host.shadowRoot &&
  registry[host.localName]?.["x-shadow"] &&
  isStage(host.shadowRoot) &&
  !refusedRoots.has(host.shadowRoot)
    ? host.shadowRoot
    : null;
/** @param {Node} root */
export const shadowRootsIn = (root) =>
  liveStages().filter(
    (stage) => root.contains(stage.host) && declaredRoot(stage.host) === stage,
  );
export const pageShadowRoots = () => shadowRootsIn(document);
// Geometry walks the children that paint here: a host's shadow tree and a slot's
// assigned (or fallback) content, rather than the separate light-DOM ownership tree.
/** @param {Node} node */
export const renderedChildren = (node) =>
  isHTML(node, "slot")
    ? node.assignedNodes({ flatten: true })
    : (isElement(node) ? (node.shadowRoot ?? node) : node).childNodes;

// What stands for `node` in the tree `root` roots (a Document or a ShadowRoot): the node
// itself when it is in that tree, else the host of the shadow tree holding it, climbed
// out until one is. Null when none is: a detached node, or one outside `root`
// altogether. A shadow tree renders where its host stands, so order and range
// questions, which the platform answers only within one tree, are asked of this.
/** @param {Node | null} node @param {Node} root */
export const hostIn = (node, root) => {
  let at = node;
  while (at && at.getRootNode() !== root) at = shadowHost(at.getRootNode());
  return at;
};

// The layer's rules for shadow trees: every root's shadow.css, above adopted defaults,
// followed by semantic state.css (layer.py's `composed_sheets`). Read from the layer
// rather than written here so a project override travels with the widget, and fetched
// during upgrade so the stage below stays synchronous for its callers.
export let shadowRules = "";
// One read for the tab. The three boundaries that import widget modules each ask for the
// rules the widgets they are about to upgrade render under, and an x-shadow widget can
// arrive at any of them — in the document, in a later version, or in an agent's reply —
// so the ask is repeated and the answer is not. Sharing the promise rather than the text
// also holds a second caller behind the first read instead of starting another.
/** @type {Promise<void> | null} */
let loading = null;
export function loadShadowRules() {
  loading ??= readShadowRules();
  return loading;
}
async function readShadowRules() {
  const { runtimeResource } = await import("./context.js");
  const response = await fetch(runtimeResource("/shadow.css"));
  if (!response.ok)
    throw new Error(`leaf: shadow.css failed to load (${response.status})`);
  shadowRules = await response.text();
}
