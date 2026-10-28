/* The instruction's upgrade boundary keeps authored passage capture from joining
 * prose across live value slots. The enclosing playground's shared Lit view owns
 * those slots and any instruction supplied by a contributor. Contributor words
 * are generated, so revision comparisons don't read them as authored prose. */
import { once } from "/runtime/widget-api.js";

customElements.define(
  "lf-playground-output",
  class extends HTMLElement {
    connectedCallback() {
      once(this);
    }
  },
);
