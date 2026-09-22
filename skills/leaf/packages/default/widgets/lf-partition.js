/* A partition gives its two declared children equal rows or columns. Nested partitions
   inherit the outer reading arrangement's posture through the shared registration API. */
import { arrangeReadingElement, once } from "/runtime/widget-api.js";

customElements.define(
  "lf-partition",
  class extends HTMLElement {
    #layout = null;

    connectedCallback() {
      if (!this.#layout) {
        this.dataset.lfDirection = this.getAttribute("direction");
        this.#layout = arrangeReadingElement({ owner: this, role: "partition" });
        once(this);
      }
      this.#layout.connect();
    }

    disconnectedCallback() {
      this.#layout?.disconnect();
    }
  },
);
