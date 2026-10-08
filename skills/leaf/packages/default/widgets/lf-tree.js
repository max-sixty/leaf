/* The initial producer owns the tree's structure. Upgrade adopts that drawing,
 * preserving the first paint and reporting an invalid empty body to the author. */
import { initialRender, once, failSoft } from "/runtime/widget-api.js";

customElements.define(
  "lf-tree",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      const { source, error } = initialRender(this);
      if (error) failSoft(this, error, source);
    }
  },
);
