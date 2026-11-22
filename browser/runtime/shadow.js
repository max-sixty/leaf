/* This module owns declared shadow roots, the shadow.css rules they render under, and
 * the shared highlight rules. */
import { isStage, liveStages } from "./arrivals.js";
import { declarationFor } from "./registry.js";

// The open shadow roots under some root that hold the page's own words, from what each
// widget's module declares rather than from a sweep of every element: a module that
// builds a stage is making a promise about whose words those are, and a root some other
// library happened to attach is not covered by it. `getComposedRanges` is told exactly
// these, so what the capture can see and what the reading walks are one list.
//
// Which root to look under is the axis, because the whole document is not the only
// answer: a message arriving in the panel carries widget markup that upgrades in a
// subtree, so a pass over that subtree has the same boundary to cross and no document
// to ask about. A root is found under `root` as a selector would find its host: `root`
// itself or an element in `root`'s own tree, not one inside another root.
//
// A widget's module declares a root by building it as a stage: through `shadowStage`,
// or as the render root of a `LeafElement` whose class says `static shadow = true`
// (leaf-element.js). So the roots come from the stages' registry (`liveStages`,
// arrivals.js), not from a query of `root`. Every id the document doesn't hold is looked
// for here (`elementById`, passages.js), as is an obligation's widget in a thread no one
// has opened, on every paint that places it, so this answer costs the number of stages,
// not the size of the page. A root attached any other way carries none of a stage's
// marks or watches, and its host reads as one with no declared root: by its own
// children. So does a stage on a host the layer declares no widget for, as a page
// script may build one: the file's reading knows no widget there.
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
  declarationFor(host) &&
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
// Every element under `root` that `selector` names, in `root`'s own tree and the
// declared roots under it, so it costs what `root` holds rather than the page.
/** @template {Element} [E=Element] @param {Element | Document} root @param {string} selector
 * @returns {E[]} */
export const queryAllUnder = (root, selector) =>
  [root, ...shadowRootsIn(root)].flatMap((scope) => {
    /** @type {NodeListOf<E>} */
    const elements = scope.querySelectorAll(selector);
    return [...elements];
  });

// The layer's rules for shadow trees: every root's shadow.css, above adopted defaults,
// followed by semantic state.css (layer.py's `composed_sheets`). Read from the layer
// rather than written here so a project override travels with the widget.
export let shadowRules = "";
// One read for the tab, which the first stage starts (stage-integration.js).
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
