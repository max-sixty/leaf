import { once } from "/runtime/lib/once.js";
import { keeps } from "/runtime/lib/keeps.js";
customElements.define(
  "lf-test-plan",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      keeps(this, "role", "group");
      keeps(this, "aria-label", this.getAttribute("label") ?? "");
    }
  },
);
