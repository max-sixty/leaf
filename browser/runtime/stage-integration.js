// Compiled from stage-integration.ts by build/typescript.mjs; edit that file.
/* Leaf's augmentation of portable shadow stages. The widget owns its root and
   rendering; this owner adds the page's theme, shared marks and cross-root watches.
   A theme node stays connected while its text is unchanged. Renderer-owned adopted
   sheets remain in place, and re-adoption restores any shared sheets it replaced. */
import { installStageIntegration } from "./dom/shadow-stage.js";
import { shadowRules } from "./dom/shadow.js";
import { chromeSheet, marksSheet } from "./base/stylesheets.js";
import { watchCurrentLocationIn } from "./dom/focus.js";
import { installLayerStyleIntegration } from "./dom/keyboard/layer-stack.js";
import { move } from "./dom/dom-move.js";
import { watchPassageRoot } from "./readings/passages.js";

installLayerStyleIntegration((root) => {
  if (!root.adoptedStyleSheets.includes(chromeSheet))
    root.adoptedStyleSheets = [...root.adoptedStyleSheets, chromeSheet];
});

const styles = new WeakMap();
installStageIntegration((root) => {
  root.adoptedStyleSheets = [...new Set([...root.adoptedStyleSheets, marksSheet])];
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
