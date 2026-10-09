import { once } from "/runtime/widget-api.js";

// The `unfamiliar-package` case's widget: a meter and a label drawn from the
// element's attributes.
customElements.define(
  "lf-burn",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      const consumed = Number(this.getAttribute("consumed"));
      const meter = document.createElement("meter");
      meter.value = consumed;
      meter.high = 0.75;
      const label = document.createElement("span");
      label.textContent = `${Math.round(consumed * 100)}% of the ${this.getAttribute(
        "window",
      )} budget spent against ${this.getAttribute("objective")}%`;
      this.append(meter, label);
    }
  },
);
