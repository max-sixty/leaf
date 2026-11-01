/* Leaf's augmentation of portable shadow stages. The widget owns its root and
   rendering; this owner adds the page's theme, shared marks and cross-root watches.
   A theme node stays connected while its text is unchanged. Renderer-owned adopted
   sheets remain in place, and re-adoption restores any shared sheets it replaced. */
import { installStageIntegration } from "./shadow-stage.js";
import { shadowRules } from "./shadow.js";
import { annotationMarkSheets, marksSheet } from "./stylesheets.js";
import { watchCurrentLocationIn } from "./focus.js";
import { watchDisclosures } from "./keyboard/disclosure.js";
import { watchLayers } from "./keyboard/layer-stack.js";
import { move } from "./dom-move.js";
import { watchPassageRoot } from "./passages.js";
import { watchArrivalsIn } from "./arrivals.js";

const styles = new WeakMap();
installStageIntegration((root) => {
  watchArrivalsIn(root);
  root.adoptedStyleSheets = [
    ...new Set([...root.adoptedStyleSheets, ...annotationMarkSheets, marksSheet]),
  ];
  watchDisclosures(root);
  watchLayers(root);
  watchCurrentLocationIn(root);
  let style = styles.get(root);
  if (!style) {
    style = document.createElement("style");
    style.setAttribute("data-lf-gen", "1");
    styles.set(root, style);
  }
  if (style.textContent !== shadowRules) style.textContent = shadowRules;
  if (style.parentNode !== root) move(root, style, root.firstChild);
  watchPassageRoot(root);
  return [style];
});
