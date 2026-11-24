/* A seated obligation whose press paints optimistically before dispatching settlement. */
import { nothing } from "/vendor/lit.js";
import { threadSurface } from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { offer, offerAction } from "/runtime/lib/controls.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";

export function defineSeatedObligation() {
  customElements.define(
    "lf-verdict",
    class extends LeafElement {
      setup() {
        this.press = offer("button", "lf-settle", "Accept");
        this.press.onclick = () => {
          this.settled();
          this.record("settle", { answer: "yes" });
        };
        // The threads about the verdict, and the comment box that starts one, stand
        // under its press.
        this.threads = offer("div", "lf-test-threads");
        this.comment = offerAction("symbol", "lf-test-comment", undefined, {
          action: "comment",
        });
        this.comment.addEventListener("click", () => threadSurface(this).open?.(this));
        this.append(this.press, this.threads, this.comment);
      }

      threadOutlets(targets, { onCommit }) {
        const writing = targets.some(({ thread }) => !thread);
        onCommit(() => {
          this.writing = writing;
          this.requestUpdate();
        });
        return targets.map(() => this.threads);
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
        this.comment.toggleAttribute(
          "hidden",
          this.writing || !threadSurface(this).open,
        );
        return nothing;
      }
    },
  );
}
