/* The live sample's stable viewport and loading controls paint before modules run.
 * The behavior module adopts this same drawing; the child page owns only its own
 * readiness, never its parent's allocation or presentation proof. */
export function initialSample(host, { offer }) {
  const template = host.querySelector(":scope > template[data-sample]");
  if (!template) return null;
  host.dataset.lfSampleLive = "";
  const frame = document.createElement("iframe");
  frame.className = "lf-sample-frame";
  frame.title = host.getAttribute("label") || "Leaf sample";
  const view = document.createElement("dialog");
  view.className = "lf-sample-view";
  view.dataset.lfGen = "1";
  view.setAttribute("open", "");
  view.setAttribute("role", "presentation");
  const controls = document.createElement("div");
  controls.className = "lf-sample-controls lf-ui";
  controls.dataset.lfGen = "1";
  const actions = document.createElement("div");
  const reset = offer("button", "lf-btn", "Reset");
  reset.disabled = true;
  reset.setAttribute("aria-disabled", "true");
  const full = offer("button", "lf-btn", "Full view");
  full.disabled = true;
  const status = offer("span", "lf-sample-status", "Loading sample…");
  status.setAttribute("role", "status");
  actions.append(reset, full, status);
  controls.append(actions);
  const exhibit = document.createElement("div");
  exhibit.className = "lf-sample-exhibit";
  exhibit.append(frame);
  view.append(controls, exhibit);
  host.append(view);
  return { template, frame, view, controls, reset, full, status };
}
