/* An intentionally invalid renderer: complete state increments its current
 * count and appends its caption. Replaying it exposes both relative-state faults. */
import { keeps, LeafElement, nothing } from "/runtime/widget-api.js";

customElements.define(
  "lf-tally",
  class extends LeafElement {
    render() {
      const { state } = this;
      keeps(
        this,
        "count",
        Number(this.getAttribute("count")) + Number(state.step.value),
      );
      this.querySelector("pre").append(state.caption.value);
      return nothing;
    }
  },
);
