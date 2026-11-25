/* Leaf's augmentation of portable shadow stages. The widget owns its root and
   rendering; this owner adds the page's theme, shared marks and cross-root watches.
   A theme node stays connected while its text is unchanged, and takes the layer's
   shadow rules once they have loaded (shadow.js). Renderer-owned adopted sheets remain
   in place, and re-adoption restores any shared sheets it replaced. */
import { installStageIntegration } from "./shadow-stage.js";
import { loadShadowRules, shadowRules } from "./shadow.js";
import { PendingTaskEvent } from "./lib/pending-task.js";
import { chromeSheet, marksSheet } from "./stylesheets.js";
import { watchCurrentLocationIn } from "./focus.js";
import { installLayerStyleIntegration } from "./keyboard/layer-stack.js";
import { move } from "./dom-move.js";
import { watchPassageRoot } from "./passages.js";

installLayerStyleIntegration((root) => {
  if (!root.adoptedStyleSheets.includes(chromeSheet))
    root.adoptedStyleSheets = [...root.adoptedStyleSheets, chromeSheet];
});

/** @type {WeakMap<ShadowRoot, HTMLStyleElement>} */
const styles = new WeakMap();
/** @param {ShadowRoot} root */
const styleOf = (root) => {
  let style = styles.get(root);
  if (!style) {
    style = document.createElement("style");
    style.setAttribute("data-lf-gen", "1");
    styles.set(root, style);
  }
  return style;
};
installStageIntegration((root) => {
  root.adoptedStyleSheets = [...new Set([...root.adoptedStyleSheets, marksSheet])];
  watchCurrentLocationIn(root);
  const style = styleOf(root);
  const dress = () => {
    if (style.textContent !== shadowRules) style.textContent = shadowRules;
  };
  dress();
  // A page holds its presentation until the rules are in, so a widget that first
  // draws unstyled is styled before the page presents itself.
  if (!shadowRules)
    root.host.dispatchEvent(new PendingTaskEvent(loadShadowRules().then(dress)));
  if (style.parentNode !== root) move(root, style, root.firstChild);
  watchPassageRoot(root);
  return [style];
});
