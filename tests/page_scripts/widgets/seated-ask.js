/* A seated Ask whose press paints optimistically before dispatching settlement. */
import {
  keeps,
  keepsText,
  threadBox,
  offer,
  once,
  widgetController,
} from "/runtime/widget-api.js";

export default class extends HTMLElement {
  #controller;
  #stop = null;

  connectedCallback() {
    this.#controller ??= widgetController(this);
    if (!once(this)) {
      this.#stop ??= this.#controller.subscribe(() => {});
      return;
    }
    this.press = offer("button", "lf-settle", "Accept");
    this.press.onclick = () => {
      this.settled();
      this.#controller.dispatch({
        kind: "action",
        verb: "settle",
        detail: { answer: "yes" },
      });
    };
    this.append(this.press);
    const seat = threadBox(this, "Say something about this");
    if (seat) this.append(seat);
    this.#stop ??= this.#controller.subscribe(() => {});
  }

  disconnectedCallback() {
    this.#stop?.();
    this.#stop = null;
  }

  settled() {
    keepsText(this.press, "Accepted");
    keeps(this.press, "aria-pressed", true);
  }

  renderState(state) {
    if (state.settle.value) this.settled();
    else {
      keepsText(this.press, "Accept");
      keeps(this.press, "aria-pressed", false);
    }
  }
}
