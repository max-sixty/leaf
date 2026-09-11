/* A partition gives its two declared children equal rows or columns. Nested partitions
   inherit the outer reading arrangement's posture through the shared registration API. */
import {
  arrangeReadingElement,
  once,
  registerReadingElement,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-partition",
  class extends HTMLElement {
    #readingArrangement = null;

    connectedCallback() {
      if (!once(this)) {
        const content = this.querySelector(":scope > .lf-partition-content");
        this.#readingArrangement = registerReadingElement({ owner: this, content });
        return;
      }
      this.dataset.lfDirection = this.getAttribute("direction");
      this.#readingArrangement = arrangeReadingElement({
        owner: this,
        role: "partition",
      }).readingArrangement;
    }

    disconnectedCallback() {
      this.#readingArrangement?.cleanup();
      this.#readingArrangement = null;
    }
  },
);
