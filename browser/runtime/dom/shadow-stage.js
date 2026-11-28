// Compiled from shadow-stage.ts by build/typescript.mjs; edit that file.
/* A widget's shadow stage, independent of Leaf's page runtime. Retained nodes stay
   connected; authored light children are removed after the renderer has read them.
   WebKit unloads shadow iframes on replaceChildren(), so children leave individually.
   Native layer openings are observed in every stage, where toggle events stay local.

   Leaf installs its augmentation from stage-integration.js before widgets upgrade:
   shared styles and marks, and focus and passage watches belong to the host,
   not to a widget's staging lifecycle. Re-adoption restores shared adopted sheets
   without discarding a renderer's own. */
import { setChildren } from "./dom-children.js";
import { watchArrivalsIn } from "./arrivals.js";
import { stagesFailure } from "../lib/failure.js";
import { watchLayers } from "./keyboard/layer-stack.js";

let integration = null;
export const installStageIntegration = (adopt) => {
  integration = adopt;
};
export function adoptShadowStage(root) {
  watchArrivalsIn(root);
  watchLayers(root);
  integration?.(root);
  return root;
}

export function shadowStage(host, nodes) {
  const root = host.shadowRoot ?? stageFor(host);
  watchArrivalsIn(root);
  watchLayers(root);
  integration?.(root);
  // Keep retained nodes connected, preserving their focus and widget lifecycle.
  setChildren(root, nodes);
  for (const child of [...host.childNodes]) child.remove();
  host.removeAttribute("data-lf-failed");
  return root;
}

// A `shadow` widget shows only what its stage holds, so its failure box stands
// there, and the widget's next stage replaces it. Page layout can't see into the stage,
// so `data-lf-failed` says on the host that the stage holds a failure, as a light child
// `.lf-error` says it for every other widget.
function stageFor(host) {
  stagesFailure(host, (box) => {
    shadowStage(host, [box]);
    host.setAttribute("data-lf-failed", "");
    return true;
  });
  return host.attachShadow({ mode: "open" });
}
