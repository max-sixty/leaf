/* A split gives its two declared children equal rows or columns. Nested splits inherit
   the outer arrangement's posture through the shared registration API. */
import {
  arrangeReadingElement,
  once,
  registerArrangedElement,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-split",
  class extends HTMLElement {
    #arrangement = null;

    connectedCallback() {
      if (!once(this)) {
        const content = this.querySelector(":scope > .lf-split-content");
        this.#arrangement = registerArrangedElement({ owner: this, content });
        return;
      }
      this.dataset.lfDirection = this.getAttribute("direction");
      this.#arrangement = arrangeReadingElement({
        owner: this,
        kind: "split",
      }).arrangement;
    }

    disconnectedCallback() {
      this.#arrangement?.cleanup();
      this.#arrangement = null;
    }
  },
);
