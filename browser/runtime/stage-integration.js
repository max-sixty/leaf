/* Leaf's augmentation of portable shadow stages. The widget owns its root and
   rendering; this owner adds the page's theme, shared marks and cross-root watches.
   A theme node stays connected while its text is unchanged. Renderer-owned adopted
   sheets remain in place, and re-adoption restores any shared sheets it replaced.

   The layer's shadow rules are read when the first stage is built, since only a
   module's stage says a page needs them. A stage built before they land holds an empty
   theme node, which takes the rules as they arrive. */
import { liveStages } from "./arrivals.js";
import { installStageIntegration } from "./shadow-stage.js";
import { loadShadowRules, shadowRules } from "./shadow.js";
import { chromeSheet, marksSheet } from "./stylesheets.js";
import { watchCurrentLocationIn } from "./focus.js";
import { watchDisclosures } from "./keyboard/disclosure.js";
import { installLayerStyleIntegration } from "./keyboard/layer-stack.js";
import { move } from "./dom-move.js";
import { watchPassageRoot } from "./passages.js";

installLayerStyleIntegration((root) => {
  if (!root.adoptedStyleSheets.includes(chromeSheet))
    root.adoptedStyleSheets = [...root.adoptedStyleSheets, chromeSheet];
});

/** @type {WeakMap<ShadowRoot, HTMLStyleElement>} */
const styles = new WeakMap();
/** @type {Promise<void> | null} */
let rules = null;
function themeStages() {
  for (const stage of liveStages()) {
    const style = styles.get(stage);
    if (style && style.textContent !== shadowRules) style.textContent = shadowRules;
  }
}
installStageIntegration((root) => {
  root.adoptedStyleSheets = [...new Set([...root.adoptedStyleSheets, marksSheet])];
  watchDisclosures(root);
  watchCurrentLocationIn(root);
  let style = styles.get(root);
  if (!style) {
    style = document.createElement("style");
    style.setAttribute("data-lf-gen", "1");
    styles.set(root, style);
  }
  rules ??= loadShadowRules().then(themeStages);
  if (style.textContent !== shadowRules) style.textContent = shadowRules;
  if (style.parentNode !== root) move(root, style, root.firstChild);
  watchPassageRoot(root);
  return [style];
});
