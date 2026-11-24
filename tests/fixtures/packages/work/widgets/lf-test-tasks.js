import { once } from "/runtime/widget-api.js";
import { keeps } from "/runtime/lib/keeps.js";
customElements.define(
  "lf-test-tasks",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      keeps(this, "role", "group");
      keeps(this, "aria-label", this.getAttribute("label") ?? "Tasks");
    }
  },
);
