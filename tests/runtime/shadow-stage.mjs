/* A test's shadow stage: the open root a widget attaches, holding `nodes` and none of
   the host's light children, dressed as Leaf dresses a root at its host's `lf-connect`
   (element-integration.js), which puts Leaf's style node first. */
import { adoptShadowStage } from "/runtime/dom/shadow-stage.js";

/** @param {Element} host @param {Iterable<Node>} nodes */
export function shadowStage(host, nodes) {
  const root = host.shadowRoot ?? host.attachShadow({ mode: "open" });
  root.replaceChildren(...nodes);
  for (const child of [...host.childNodes]) child.remove();
  return adoptShadowStage(root);
}
