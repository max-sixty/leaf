/* A seated Ask whose press paints optimistically before dispatching settlement. */
import {
  keeps,
  keepsText,
  threadBox,
  offer,
  LeafElement,
  nothing,
} from "/runtime/widget-api.js";

export function defineSeatedAsk() {
  customElements.define(
    "lf-verdict",
    class extends LeafElement {
      setup() {
        this.press = offer("button", "lf-settle", "Accept");
        this.press.onclick = () => {
          this.settled();
          this.controller.dispatch({
            kind: "action",
            verb: "settle",
            detail: { answer: "yes" },
          });
        };
        this.append(this.press);
        const seat = threadBox(this, "Say something about this");
        if (seat) this.append(seat);
      }

      settled() {
        keepsText(this.press, "Accepted");
        keeps(this.press, "aria-pressed", true);
      }

      render() {
        if (this.state.settle.value) this.settled();
        else {
          keepsText(this.press, "Accept");
          keeps(this.press, "aria-pressed", false);
        }
        return nothing;
      }
    },
  );
}
