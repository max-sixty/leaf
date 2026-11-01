/* A widget's shadow stage, independent of Leaf's page runtime. Retained nodes stay
   connected; authored light children are removed after the renderer has read them.
   WebKit unloads shadow iframes on replaceChildren(), so children leave individually.

   Leaf installs its augmentation from stage-integration.js before widgets upgrade:
   shared styles and marks, focus, disclosure and passage watches belong to the host,
   not to a widget's staging lifecycle. Re-adoption restores shared adopted sheets
   without discarding a renderer's own. The host returns its retained style nodes so
   imperative staging keeps them alongside the rendering. */
import { setChildren } from "./dom-children.js";
import { watchArrivalsIn } from "./arrivals.js";
import { stagesFailure } from "./widget-upgrade.js";

let integration = null;
export const installStageIntegration = (adopt) => {
  integration = adopt;
};
export function adoptShadowStage(root) {
  watchArrivalsIn(root);
  integration?.(root);
  return root;
}

export function shadowStage(host, nodes) {
  const root = host.shadowRoot ?? stageFor(host);
  watchArrivalsIn(root);
  const styles = integration?.(root) ?? [];
  // Keep retained nodes connected, preserving their focus and widget lifecycle.
  setChildren(root, [...styles, ...nodes]);
  for (const child of [...host.childNodes]) child.remove();
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
