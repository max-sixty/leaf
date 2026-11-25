/* Leaf's augmentation of portable shadow stages. The widget owns its root and
   rendering; this owner adds the page's theme, shared marks and cross-root watches.
   A theme node stays connected while its text is unchanged, and takes the layer's
   shadow rules once they have loaded (dom/shadow.js). Renderer-owned adopted sheets remain
   in place, and re-adoption restores any shared sheets it replaced. */
import { installStageIntegration } from "./dom/shadow-stage.js";
import { loadShadowRules, shadowRules } from "./dom/shadow.js";
import { PendingTaskEvent } from "./lib/pending-task.js";
import { chromeSheet, marksSheet } from "./base/stylesheets.js";
import { watchCurrentLocationIn } from "./dom/focus.js";
import { installLayerStyleIntegration } from "./dom/keyboard/layer-stack.js";
import { move } from "./lib/dom-move.js";
import { watchPassageRoot } from "./readings/passages.js";

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
