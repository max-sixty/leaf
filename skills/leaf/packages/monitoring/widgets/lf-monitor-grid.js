/* The monitoring grid is one compound allocation whose child regions inherit the
   root's posture while keeping independent reading-region identities. */
import { once, registerReadingArrangement } from "/runtime/widget-api.js";

customElements.define(
  "lf-monitor-grid",
  class extends HTMLElement {
    #readingArrangement = null;

    connectedCallback() {
      if (once(this)) this.classList.add("lf-monitor-grid-arranged");
      this.#readingArrangement = registerReadingArrangement({
        owner: this,
        content: this,
      });
    }

    disconnectedCallback() {
      this.#readingArrangement?.cleanup();
      this.#readingArrangement = null;
    }
  },
);
