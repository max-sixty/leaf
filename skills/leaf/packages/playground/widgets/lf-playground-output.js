/* A playground instruction upgrades authored prose around live value slots.
 * Its upgrade boundary keeps file captures from joining words across those slots;
 * the parent applies each validated value snapshot synchronously before copying or
 * submitting the resulting instruction. */
import { keepsText, once } from "/runtime/widget-api.js";

export default class extends HTMLElement {
  connectedCallback() {
    once(this);
  }

  renderInstruction(instruction) {
    keepsText(this, instruction);
  }
}
