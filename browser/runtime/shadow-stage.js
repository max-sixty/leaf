/* The stage an x-shadow widget renders into. A module never calls attachShadow itself,
   because the marks the runtime paints come from a registry that is the document's while
   the ::highlight() rules styling them are not — they reach no shadow tree. A root
   attached anywhere else would show words the user can select and no mark could ever
   paint, which is the one failure this whole capability exists to avoid.

   The two sheets arrive differently on purpose. The theme's rules go in as a <style>
   element, because they are the page's look and a project overrides them with the
   page's stylesheet; marks are adopted, shared by the document and every stage.
   Passage annotation paint joins them only when the selected renderer owns it.

   LeafElement stages its normal Lit root here, retaining authored light children for
   slots. An imperative renderer gives shadowStage the nodes to stage so replacing
   its content cannot drop the shared styles and watches.

   Adopted sheets supplied by an embedded renderer remain that renderer's: staging
   adds Leaf's sheets without discarding them. A renderer that replaces the adopted
   list stages again before yielding, restoring the shared annotation sheets too.

   shadowStage clears the host's authored children after the renderer has read them.
   WebKit's replaceChildren() and textContent = "" on a shadow host unload every iframe
   in its shadow tree, even with no child to remove, so this removes them one by one.
   Stage a concrete container and render templates inside it; retaining that container
   across updates keeps Lit's markers, native editors and directive lifetimes intact. */
import { shadowRules } from "./shadow.js";
import { annotationMarkSheets, marksSheet } from "./stylesheets.js";
import { watchCurrentLocationIn } from "./focus.js";
import { watchDisclosures } from "./keyboard/disclosure.js";
import { watchLayers } from "./keyboard/layer-stack.js";
import { setChildren } from "./dom-children.js";
import { move } from "./dom-move.js";
import { watchPassageRoot } from "./passages.js";
import { watchArrivalsIn } from "./arrivals.js";
import { stagesFailure } from "./widget-upgrade.js";

// A stage's theme <style>, kept while its rules are unchanged. A widget stages again
// whenever its content changes, and a fresh <style> restyles every node in the root,
// even with the same rules: a diff staging again as each file opened recomputed the
// style of every file already open.
const stageStyles = new WeakMap();

// Both Lit roots and imperative stages receive the same sheets and watches.
export function adoptShadowStage(root) {
  document.documentElement.lfStorage.keepDisclosures(root);
  // The stages' one registry (arrivals.js), and the watch over what stands in them: no
  // observer crosses the boundary on its own.
  watchArrivalsIn(root);
  root.adoptedStyleSheets = [
    ...new Set([...root.adoptedStyleSheets, ...annotationMarkSheets, marksSheet]),
  ];
  // A root is the one place the key paint's watch cannot reach on its own: a `toggle`
  // from inside one is not composed, and a MutationObserver does not cross the
  // boundary either. A focus move inside it reaches the document as no event at all.
  watchDisclosures(root);
  watchLayers(root);
  watchCurrentLocationIn(root);
  let style = stageStyles.get(root);
  if (!style) {
    style = document.createElement("style");
    style.setAttribute("data-lf-gen", "1");
  }
  if (style.textContent !== shadowRules) {
    style.textContent = shadowRules;
  }
  stageStyles.set(root, style);
  if (style.parentNode !== root) move(root, style, root.firstChild);
  watchPassageRoot(root);
  return root;
}

export function shadowStage(host, nodes) {
  const root = adoptShadowStage(host.shadowRoot ?? stageFor(host));
  const style = stageStyles.get(root);
  // Keep retained nodes connected, preserving their focus and widget lifecycle.
  setChildren(root, [style, ...nodes]);
  for (const child of [...host.childNodes]) child.remove();
  // The page reading walks in here at the host's place in the string, and its observer
  // does not cross the boundary on its own.
  watchPassageRoot(root);
  return root;
}

// An x-shadow widget shows only what its stage holds, so its failure box stands there,
// and the widget's next stage replaces it.
function stageFor(host) {
  stagesFailure(host, (box) => {
    shadowStage(host, [box]);
    return true;
  });
  return host.attachShadow({ mode: "open" });
}
