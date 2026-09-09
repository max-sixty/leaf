/* The monitoring grid is one compound allocation whose child regions inherit the
   root's posture while keeping independent reading-region identities. */
import { once, registerArrangement } from "/runtime/widget-api.js";

customElements.define(
  "lf-monitor-grid",
  class extends HTMLElement {
    #arrangement = null;

    connectedCallback() {
      if (once(this)) this.classList.add("lf-monitor-grid-arranged");
      this.#arrangement = registerArrangement({ owner: this, content: this });
    }

    disconnectedCallback() {
      this.#arrangement?.cleanup();
      this.#arrangement = null;
    }
  },
);
