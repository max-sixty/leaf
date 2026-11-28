/* Leaf's augmentation of portable shadow stages. The widget owns its root and
   rendering; this owner adds the page's theme, shared marks and cross-root watches.
   The theme is one adopted sheet every stage shares, first among its adopted sheets,
   where a `<style>` of its own in each stage made the browser take the rules in once a
   stage: a page of 256 `lf-code` blocks spent about half a second of its profiled
   load inserting them.
   Renderer-owned adopted sheets remain in place, between the theme and the marks, and
   re-adoption restores any shared sheets it replaced. */
import { installStageIntegration } from "./dom/shadow-stage.js";
import { shadowRules } from "./dom/shadow.js";
import { chromeSheet, marksSheet } from "./base/stylesheets.js";
import { watchCurrentLocationIn } from "./dom/focus.js";
import { installLayerStyleIntegration } from "./dom/keyboard/layer-stack.js";
import { watchPassageRoot } from "./readings/passages.js";

installLayerStyleIntegration((root) => {
  if (!root.adoptedStyleSheets.includes(chromeSheet))
    root.adoptedStyleSheets = [...root.adoptedStyleSheets, chromeSheet];
});

// One sheet of the layer's shadow rules, adopted by every stage ahead of the sheets its
// renderer adopts, so the browser parses and holds the rules once for the page.
const theme = new CSSStyleSheet();
let themeText = "";
installStageIntegration((root) => {
  if (themeText !== shadowRules) theme.replaceSync((themeText = shadowRules));
  const others = root.adoptedStyleSheets.filter(
    (sheet) => sheet !== theme && sheet !== marksSheet,
  );
  root.adoptedStyleSheets = [theme, ...others, marksSheet];
  watchCurrentLocationIn(root);
  watchPassageRoot(root);
  return [];
});
