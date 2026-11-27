/* This module owns declared shadow roots, the shadow.css rules they render under, and
 * the shared highlight rules. */
import { isStage } from "./arrivals.js";
import { declaredElements, registry } from "../state/registry.js";

// The open shadow roots under some root that hold the page's own words, from what the
// registry declares rather than from a sweep of every element: a `shadow` widget is
// making a promise about whose words those are, and a root some other library happened
// to attach is not covered by it. `getComposedRanges` is told only these, so what the
// capture can see and what the reading walks are one list.
//
// Which root to look under is the axis, because the whole document is not the only
// answer: a message arriving in the panel carries widget markup that upgrades in a
// subtree, so a pass over that subtree has the same boundary to cross and no document
// to ask about. A root is found under `root` as a selector would find its host: `root`
// itself or an element in `root`'s own tree, not one inside another root.
//
// A declared root is the stage a `shadow` widget built through `shadowStage`, so its
// host is an element of `root`'s tree whose tag declares `shadow`, which the browser
// finds (`declaredElements`). The answer costs what `root` holds rather than the stages
// the page holds, since the page reading's watch asks it of each node a change names.
// Two readers of the whole page ask otherwise. The selection's capture, which runs on
// every key and wheel step, hands the platform only the roots its ends stand in
// (`pageRange`, native-selection.js). A lookup of an id the document doesn't hold, which
// the runtime makes hundreds of times for one comment, asks each stage for the id and
// keeps what one of these roots holds (`declaredIn`, `elementById` in
// readings/passages.js). A root attached any other way carries none of a stage's marks
// or watches, and its host reads as one with no declared root: by its own children.
//
// A root refused for holding bare text (readings/passages.js, `refusesBareText`) leaves the list for
// good, and its host reads the same way.
/** @type {WeakSet<ShadowRoot>} */
const refusedRoots = new WeakSet();
/** @param {ShadowRoot} root */
export const refuseShadowRoot = (root) => refusedRoots.add(root);
// The declared root `host` holds the page's words in, or null.
/** @param {Element} host */
export const declaredRoot = (host) =>
  host.shadowRoot &&
  registry[host.localName]?.shadow &&
  isStage(host.shadowRoot) &&
  !refusedRoots.has(host.shadowRoot)
    ? host.shadowRoot
    : null;
/** @param {Document | DocumentFragment | Element} root @returns {ShadowRoot[]} */
export const shadowRootsIn = (root) =>
  declaredElements(root, (entry) => entry.shadow).flatMap(
    (host) => declaredRoot(host) ?? [],
  );
// Whether `stage` is one of the roots `shadowRootsIn(root)` lists.
/** @param {Document | DocumentFragment | Element} root @param {ShadowRoot} stage */
export const declaredIn = (root, stage) =>
  root.contains(stage.host) && declaredRoot(stage.host) === stage;
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
// rather than written here so a project override travels with the widget, and fetched
// during upgrade so the stage below stays synchronous for its callers.
export let shadowRules = "";
// One read for the tab. The three boundaries that import widget modules each ask for
// the rules the widgets they are about to upgrade render under, and a `shadow`
// widget can arrive at any of them — in the document, in a later version, or in an
// agent's reply — so the ask is repeated and the answer is not. Sharing the promise
// rather than the text also holds a second caller behind the first read instead of
// starting another.
/** @type {Promise<void> | null} */
let loading = null;
export function loadShadowRules() {
  loading ??= readShadowRules();
  return loading;
}
async function readShadowRules() {
  const { runtimeResource } = await import("../state/context.js");
  const response = await fetch(runtimeResource("/shadow.css"));
  if (!response.ok)
    throw new Error(`leaf: shadow.css failed to load (${response.status})`);
  shadowRules = await response.text();
}
