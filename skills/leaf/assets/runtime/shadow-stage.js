/* The stage an x-shadow widget renders into. A module never calls attachShadow itself,
   because the marks the runtime paints come from a registry that is the document's while
   the ::highlight() rules styling them are not — they reach no shadow tree. A root
   attached anywhere else would show words the user can select and no mark could ever
   paint, which is the one failure this whole capability exists to avoid.

   The two sheets arrive differently on purpose. The theme's rules go in as a <style>
   element, because they are the page's look and a project overrides them with the
   page's stylesheet; marks are adopted, shared by the document and every stage.
   Passage annotation paint joins them only when the selected renderer owns it.

   It takes the nodes rather than handing back a root to fill, so the style cannot be
   left out: a module that wrote its own children would replace the one thing holding its
   look, and it would look right in exactly the session where someone remembered. Same
   reasoning as renderSaid — a rule each widget has to remember is a rule that gets
   forgotten, and the forgetting is invisible until a page ships without it. */
import { SHADOW_STARTUP_CSS, shadowRules } from "./shadow.js";
import {
  annotationMarkSheets,
  constructSheet,
  inBaseLayer,
  marksSheet,
} from "./stylesheets.js";
import { watchDisclosures } from "./keyboard/disclosure.js";
import { watchLayers } from "./keyboard/layer-stack.js";
import { setChildren } from "./dom-children.js";
import { watchPassageRoot } from "./passages.js";
import { liveStages, watchArrivalsIn } from "./arrivals.js";

// A third-party stylesheet that arrives with an on-demand bundle belongs wherever that
// bundle can draw: the document and every declared shadow stage. The vendored Web
// Awesome bundle calls this as it evaluates (build/webawesome/build.mjs).
// Keep one constructable sheet per name so a page parses it once, existing stages
// receive a late-loaded bundle, and stages built after registration inherit the sheet.
const widgetSheets = new Map();
export function registerWidgetStyles(name, text) {
  const existing = widgetSheets.get(name);
  if (existing) return existing;
  const sheet = constructSheet(inBaseLayer(text), name);
  widgetSheets.set(name, sheet);
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
  for (const root of liveStages())
    root.adoptedStyleSheets = [...root.adoptedStyleSheets, sheet];
  return sheet;
}

export function shadowStage(host, nodes) {
  const root = host.shadowRoot ?? host.attachShadow({ mode: "open" });
  // The stages' one registry (arrivals.js), and the watch over what stands in them: no
  // observer crosses the boundary on its own.
  watchArrivalsIn(root);
  root.adoptedStyleSheets = [
    ...annotationMarkSheets,
    marksSheet,
    ...widgetSheets.values(),
  ];
  // A root is the one place the shortcut bar's watch cannot reach on its own: a `toggle`
  // from inside one is not composed, and a MutationObserver does not cross the
  // boundary either.
  watchDisclosures(root);
  watchLayers(root);
  const style = document.createElement("style");
  style.textContent = SHADOW_STARTUP_CSS + shadowRules;
  // Fragment hydration can add a sheet while the user uses an existing control.
  // Keep retained nodes connected, preserving their focus and widget lifecycle.
  setChildren(root, [style, ...nodes]);
  // The page reading walks in here at the host's place in the string, and its observer
  // does not cross the boundary on its own.
  watchPassageRoot(root);
  return root;
}
