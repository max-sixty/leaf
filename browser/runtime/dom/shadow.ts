/* This module owns declared shadow roots and the shadow.css rules they render under. */
import { isStage, liveStages } from "./arrivals.js";
import { isElement, openRoot } from "../lib/shadow-tree.js";
import { registry } from "../state/registry.js";

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
// A declared root is the stage a `shadow` widget built through `shadowStage`, and its
// host an element of `root`'s tree that `declaredRoot` answers for. Each question asks
// whichever source costs less. Asked of the document, whose tree holds every stage not
// nested in another, the stages' registry answers (`liveStages`, arrivals.js), at the
// cost of the stages, since the anchor reading asks so on every wheel step and Tab
// (`pageQueryAll`, readings/passages.js), and a page of plain prose then pays nothing.
// Asked of anything else, as the page reading's watch asks of each node a change names,
// `root`'s own elements answer, at the cost of what `root` holds. Two readers of the
// whole page ask more narrowly still. The selection's capture hands the platform only the
// roots its ends stand in (`pageRange`, native-selection.js). A lookup of an id the
// document doesn't hold, which the runtime makes hundreds of times for one comment, asks
// each stage for the id and keeps what one of these roots holds (`declaredIn`,
// `elementById` in readings/passages.js). A root attached any other way carries none of
// a stage's marks or watches, and its host reads as one with no declared root: by its
// own children.
//
// A root refused for holding bare text (readings/passages.js, `refusesBareText`) leaves the list for
// good, and its host reads the same way.
const refusedRoots = new WeakSet<ShadowRoot>();
export const refuseShadowRoot = (root: ShadowRoot) => refusedRoots.add(root);
// The declared root `host` holds the page's words in, or null.
export const declaredRoot = (host: Element) => {
  const root = openRoot(host);
  return root &&
    registry[host.localName]?.shadow &&
    isStage(root) &&
    !refusedRoots.has(root)
    ? root
    : null;
};
const shadowRootsIn = (root: Document | DocumentFragment | Element): ShadowRoot[] =>
  root.nodeType === root.DOCUMENT_NODE
    ? liveStages().filter((stage) => declaredIn(root, stage))
    : [...(isElement(root) ? [root] : []), ...root.querySelectorAll("*")].flatMap(
        (host) => declaredRoot(host) ?? [],
      );
// Whether `stage` is one of the roots `shadowRootsIn(root)` lists.
export const declaredIn = (
  root: Document | DocumentFragment | Element,
  stage: ShadowRoot,
) => root.contains(stage.host) && declaredRoot(stage.host) === stage;
// Every element under `root` that `selector` names, in `root`'s own tree and the
// declared roots under it, so it costs what `root` holds rather than the page.
export const queryAllUnder = <E extends Element = Element>(
  root: Element | Document,
  selector: string,
): E[] =>
  [root, ...shadowRootsIn(root)].flatMap((scope) => {
    const elements: NodeListOf<E> = scope.querySelectorAll(selector);
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
let loading: Promise<void> | null = null;
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
