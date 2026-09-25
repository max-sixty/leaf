/* A grid's count needs no script: the theme reads `columns="3"` as a selector. A track
   template is the one value a stylesheet cannot read out of an attribute, so the module
   paints it as --lf-grid-template, with the two numbers the width it stacks below is made
   of: --lf-grid-scale, how many of its narrowest track the template is wide, and
   --lf-grid-gaps, the gaps between its tracks (the theme, at the stacking rule). The
   paint follows the attribute, so a revision that changes the template or turns it into
   a count repaints in place. */
import { once } from "/runtime/widget-api.js";

const COUNT = /^[1-6]$/;
const PAINTED = ["--lf-grid-template", "--lf-grid-scale", "--lf-grid-gaps"];

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
        const tracks = columns.split(" ");
        const fr = tracks.map(parseFloat);
        // Each track is at least nothing rather than its content's minimum, so what a
        // cell holds cannot move the split; a wide cell scrolls or wraps inside it.
        this.style.setProperty(
          "--lf-grid-template",
          tracks.map((track) => `minmax(0, ${track})`).join(" "),
        );
        this.style.setProperty(
          "--lf-grid-scale",
          String(fr.reduce((a, b) => a + b, 0) / Math.min(...fr)),
        );
        this.style.setProperty("--lf-grid-gaps", String(tracks.length - 1));
      } else {
        for (const name of PAINTED) this.style.removeProperty(name);
      }
      if (!this.getAttribute("style")) this.removeAttribute("style");
    }
  },
);
