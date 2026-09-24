/* A grid's count needs no script: the theme reads `columns="3"` as a selector. A track
   template is the one value a stylesheet cannot read out of an attribute, so the module
   paints it as --lf-grid-template, and how many narrowest tracks wide the template is as
   data-lf-grid-scale, which the theme's stacking rules read. The paint follows the attribute, so a revision
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
        // How many of its narrowest track the template is wide, which is what the
        // width it stacks below is a multiple of (the theme, at the stacking rules).
        const fr = columns.split(" ").map(parseFloat);
        const scale = fr.reduce((a, b) => a + b, 0) / Math.min(...fr);
        this.dataset.lfGridScale = String(Math.min(8, Math.ceil(scale - 1e-9)));
      } else {
        this.style.removeProperty("--lf-grid-template");
        delete this.dataset.lfGridScale;
      }
      if (!this.getAttribute("style")) this.removeAttribute("style");
    }
  },
);
