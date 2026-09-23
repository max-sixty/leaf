/* A grid's count needs no script: the theme reads `columns="3"` as a selector. A track
   template is the one value a stylesheet cannot read out of an attribute, so the module
   paints it as --lf-grid-template, with --lf-grid-stack for the span each cell takes when
   the grid is too narrow for the tracks. The paint follows the attribute, so a revision
   that changes the template or turns it into a count repaints in place. */
import { once } from "/runtime/widget-api.js";

const COUNT = /^[1-6]$/;

customElements.define(
  "lf-grid",
  class extends HTMLElement {
    static observedAttributes = ["columns"];

    connectedCallback() {
      this.#paint();
      once(this);
    }

    attributeChangedCallback() {
      this.#paint();
    }

    #paint() {
      const columns = this.getAttribute("columns");
      if (columns && !COUNT.test(columns)) {
        this.style.setProperty("--lf-grid-template", columns);
        this.style.setProperty("--lf-grid-stack", "1 / -1");
      } else {
        this.style.removeProperty("--lf-grid-template");
        this.style.removeProperty("--lf-grid-stack");
      }
      if (!this.getAttribute("style")) this.removeAttribute("style");
    }
  },
);
