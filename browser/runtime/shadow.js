/* This module owns declared shadow roots, the shadow.css rules they render under, and
 * the shared highlight rules. */
import { isStage, liveStages } from "./arrivals.js";
import { registry } from "./registry.js";
import {
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
const refusedRoots = new WeakSet();
export const refuseShadowRoot = (root) => refusedRoots.add(root);
// The declared root `host` holds the page's words in, or null.
export const declaredRoot = (host) =>
  host.shadowRoot &&
  registry[host.localName]?.["x-shadow"] &&
  isStage(host.shadowRoot) &&
  !refusedRoots.has(host.shadowRoot)
    ? host.shadowRoot
    : null;
export const shadowRootsIn = (root) =>
  liveStages().filter(
    (stage) => root.contains(stage.host) && declaredRoot(stage.host) === stage,
  );
export const pageShadowRoots = () => shadowRootsIn(document);
// Geometry walks the children that paint here: a host's shadow tree and a slot's
// assigned (or fallback) content, rather than the separate light-DOM ownership tree.
export const renderedChildren = (node) =>
  node.localName === "slot"
    ? node.assignedNodes({ flatten: true })
    : (node.shadowRoot ?? node).childNodes;

// What stands for `node` in the tree `root` roots (a Document or a ShadowRoot): the node
// itself when it is in that tree, else the host of the shadow tree holding it, climbed
// out until one is. Null when none is: a detached node, or one outside `root`
// altogether. A shadow tree renders where its host stands, so order and range
// questions, which the platform answers only within one tree, are asked of this.
export const hostIn = (node, root) => {
  let at = node;
  while (at && at.getRootNode() !== root) at = shadowHost(at.getRootNode());
  return at;
};

// Which layer a node stands in — the runtime's chrome, a declared label, or the
// document — is asked by every reading that climbs out of a widget, so it is answered
// here, beside the climb, where geometry.js and widget-elements.js can ask it without
// importing the passage readings back.
// The chrome over a node, read within one frame: above the frame it is nobody's, and with
// no frame at all it is the document's own reading, unchanged.
export const overIn = (el, selector, frame) => {
  const near = el.closest(selector);
  return near && (!frame || under(near, frame)) ? near : null;
};
// A label a widget declared as the page speaking (generatedElement), which the anchor
// pass reads over the chrome it sits in.
export const SAID = "[data-lf-said]";
// The pair `uiInside` weighs, the nearer deciding. The passage walk reads the same pair one
// element at a time on its way down (passages.js, `chromeMark`).
export const UI_MARKS = `.lf-ui, ${SAID}`;
// The same question one node at a time: is this the runtime's own chrome rather than the
// document? Every affordance asks it before acting on where the pointer or the caret is.
// The nearest element that answers wins: a declared label is the page's words inside the
// control it labels, and a control nested inside one is chrome again. `.lf-ui` alone was
// the answer once, and it is a look — which is how a user ended up reading a heading
// they could not point at, twice.
//
// Bounded or not, by the second argument, and that is the whole difference between the
// two ways this gets asked. Unbounded — `inUi` — the answer is about the page: a
// control is the runtime's apparatus wherever it stands, which is what a pointer or a
// caret needs to know. Bounded at an element, the answer is about that element's own
// insides, which is what a reading of one widget needs: the panel holding a widget an
// agent sent in a reply is itself `.lf-ui`, so asked the unbounded way every child of
// such a widget answers yes, and the widget reads as having nothing of its own left.
// The text readings took the same seam (quotable, shownParts, settledAway, authored);
// it is stated once here so
// that what a mark may hang on, what a settlement has emptied, and what a quote may
// name cannot come apart.
export const uiInside = (el, within) => {
  const near = el && overIn(el, UI_MARKS, within);
  return Boolean(near) && !near.matches(SAID);
};
export const inUi = (node) =>
  uiInside(node?.nodeType === 1 ? node : node?.parentElement, null);

// The layer's rules for shadow trees: every root's shadow.css, above adopted defaults,
// followed by semantic state.css (layer.py's `composed_sheets`). Read from the layer
// rather than written here so a project override travels with the widget, and fetched
// during upgrade so the stage below stays synchronous for its callers.
export let shadowRules = "";
// Every legitimate page shadow tree is built here, so repeat the theme's leading layer
// inside it: `hidden` hiding whatever display a rule states (theme.css), the
// generated-interface boundary, and transition suppression. The shadow's ordinary contents paint
// immediately and its generated interface paints after upgrade, on the same boundaries
// as authored and generated light DOM. A selector in the tree cannot see body's stamps,
// so the theme states each boundary as an inherited property these rules query with
// `@container style()`, which Chrome, Firefox and Safari support; `:host-context()`,
// which reads the stamps directly, has no Firefox or Safari support. The anonymous
// layer leads the tree's sheets, so these important declarations outrank every later
// layer.
export const SHADOW_LEADING_CSS = `
@layer {
  [hidden]:not([hidden="until-found"]),
  :host([hidden]:not([hidden="until-found"])) {
    display: none !important;
  }
  @media screen {
    @container style(--lf-before-presentation: 1) {
      *,
      *::before,
      *::after {
        transition: none !important;
      }
    }
    @container style(--lf-before-upgrade: 1) {
      .lf-ui {
        visibility: hidden !important;
      }
    }
  }
}`;
// One read for the tab. The three boundaries that import widget modules each ask for the
// rules the widgets they are about to upgrade render under, and an x-shadow widget can
// arrive at any of them — in the document, in a later version, or in an agent's reply —
// so the ask is repeated and the answer is not. Sharing the promise rather than the text
// also holds a second caller behind the first read instead of starting another.
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
