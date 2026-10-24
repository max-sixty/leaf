/* One request for permission, recorded as an ordinary widget action.
 *
 * Authored content says exactly what the user approves. Its identity survives page
 * stamps and unrelated edits; the author restates it when its scope changes. The
 * registry makes approve answer an obligation. Other unanswered requests do not
 * gate this one. Undo withdraws the same action through the widget controller.
 *
 * The initial drawing owns the persistent button and its reserved label widths;
 * changing from Approve to Undo approval keeps keyboard and touch position. */
import {
  commands,
  initialRender,
  LeafElement,
  nothing,
  quoted,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-approval",
  class extends LeafElement {
    // On me's card draws this widget itself (runtime obligations/seat.js), in the
    // form its theme gives `[data-lf-seat="card"]`.
    static seats = ["card"];

    static answerWords() {
      return "Approved";
    }

    #drawing;

    setup() {
      this.#drawing = initialRender(this);
      if (quoted(this)) {
        this.#drawing.button.disabled = true;
        return;
      }
      commands(this, "On an approval", [
        {
          id: "approval.answer",
          title: () => (this.state?.approve.action ? "Undo approval" : "Approve"),
          keys: [],
          contextKeys: ["1"],
          bindingBadge: null,
          decision: true,
          control: this.#drawing.button,
          when: () =>
            this.state?.approve.action
              ? Boolean(this.#undo())
              : Boolean(this.reading?.actions.approve.available),
          run: () => {
            if (this.state.approve.action) {
              const undo = this.#undo();
              if (undo)
                this.controller.dispatch({
                  kind: "undo",
                  target: undo.attempt ?? undo.id,
                });
            } else {
              this.controller.dispatch({
                kind: "action",
                verb: "approve",
                detail: {},
                says: "Approved",
              });
            }
          },
        },
      ]);
    }

    #undo() {
      const action = this.reading?.actions.approve;
      const latest = action?.inForce[0]?.event;
      return action?.undo.find((event) => event.id === latest?.id) ?? null;
    }

    render() {
      this.#drawing.paint(Boolean(this.state.approve.action));
      return nothing;
    }
  },
);
