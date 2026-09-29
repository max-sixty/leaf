/* A playground instruction upgrades authored prose around live value slots.
 * Its upgrade boundary keeps file captures from joining words across those slots;
 * the parent applies each validated value snapshot synchronously before copying or
 * submitting the resulting instruction. */
import { keepsText, once } from "/runtime/widget-api.js";

customElements.define(
  "lf-playground-output",
  class extends HTMLElement {
    connectedCallback() {
      once(this);
    }

    renderValues(values, controls) {
      for (const slot of this.querySelectorAll("lf-playground-value")) {
        const name = slot.getAttribute("for");
        keepsText(
          slot,
          `${values[name]}${controls.get(name).getAttribute("unit") ?? ""}`,
        );
      }
    }

    renderInstruction(instruction) {
      keepsText(this, instruction);
    }
  },
);
