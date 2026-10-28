/* The instruction's upgrade boundary keeps authored passage capture from joining
 * prose across live value slots. The enclosing playground's shared Lit view owns
 * those slots and any instruction supplied by a contributor. Contributor words
 * are generated, and are not read as authored prose. */
import { once } from "/runtime/widget-api.js";

customElements.define(
  "lf-playground-output",
  class extends HTMLElement {
    connectedCallback() {
      once(this);
    }
  },
);
