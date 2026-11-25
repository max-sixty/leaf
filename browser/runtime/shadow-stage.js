/* A widget's shadow stage: the open shadow root of an element that says `lf-connect`
   with the root attached, which Leaf dresses as the page's (element-integration.js).
   The widget owns the root and what it renders there; Leaf adds the arrival and layer
   watches, and the stage integration adds the page's shared styles and marks and the
   focus and passage watches. Native layer openings are observed in every stage, where
   toggle events stay local.

   Leaf installs that integration from stage-integration.js before widgets upgrade.
   Re-adoption restores shared adopted sheets without discarding a renderer's own, and
   puts the theme's style node first in the root, so a widget renders beside it rather
   than replacing the root's children. */
import { watchArrivalsIn } from "./arrivals.js";
import { watchLayers } from "./keyboard/layer-stack.js";

/** @type {((root: ShadowRoot) => Node[]) | null} */
let integration = null;
/** @param {(root: ShadowRoot) => Node[]} adopt */
export const installStageIntegration = (adopt) => {
  integration = adopt;
};
/** @param {ShadowRoot} root */
export function adoptShadowStage(root) {
  watchArrivalsIn(root);
  watchLayers(root);
  integration?.(root);
  return root;
}
