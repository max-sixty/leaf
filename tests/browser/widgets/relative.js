/* An intentionally invalid renderer: complete state increments its current
 * count and appends its caption. Replaying it exposes both relative-state faults. */
import { keeps, once, widgetController } from "/runtime/widget-api.js";

customElements.define(
  "lf-tally",
  class extends HTMLElement {
    #controller = widgetController(this);
    #stop;
    connectedCallback() {
      once(this);
      this.#stop ??= this.#controller.subscribe(() => {});
    }
    disconnectedCallback() {
      this.#stop?.();
      this.#stop = null;
    }
    renderState(state) {
      keeps(
        this,
        "count",
        Number(this.getAttribute("count")) + Number(state.step.value),
      );
      this.querySelector("pre").append(state.caption.value);
    }
  },
);
