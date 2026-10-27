/* A playground instruction upgrades authored prose around live value slots.
 * Its upgrade boundary keeps file captures from joining words across those slots;
 * the parent applies each validated value snapshot synchronously before copying or
 * submitting the resulting instruction. An instruction provider's words replace the
 * authored prose, so they are generated, and not read as the author's. */
import { generatedElement, keepsText, once } from "/runtime/widget-api.js";

customElements.define(
  "lf-playground-output",
  class extends HTMLElement {
    connectedCallback() {
      once(this);
    }

    renderInstruction(instruction) {
      generatedElement(this, { says: true });
      keepsText(this, instruction);
    }
  },
);
