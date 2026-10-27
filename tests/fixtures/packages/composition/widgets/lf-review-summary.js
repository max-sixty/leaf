import { LeafElement, commands, el, html, offer, quoted } from "/runtime/widget-api.js";

// Only the generated controls repaint; authored evidence keeps its nodes and state.
customElements.define(
  "lf-review-summary",
  class extends LeafElement {
    passButton = offer("button", "lf-btn", "Pass review");
    failButton = offer("button", "lf-btn", "Fail review");

    createRenderRoot() {
      const root = el("div", "review-controls");
      this.append(root);
      return root;
    }

    setup() {
      this.querySelector(":scope > [data-lf-prepaint]")?.remove();
      if (quoted(this)) return;
      commands(this, "Review result", [
        {
          id: "review.pass",
          title: "Pass review",
          keys: ["p"],
          control: this.passButton,
          bindingBadge: null,
          when: () => this.reading.actions.review.available,
          run: () => this.review("pass"),
        },
        {
          id: "review.fail",
          title: "Fail review",
          keys: ["f"],
          control: this.failButton,
          bindingBadge: null,
          when: () => this.reading.actions.review.available,
          run: () => this.review("fail"),
        },
      ]);
    }

    review(outcome) {
      return this.controller.dispatch({
        kind: "action",
        verb: "review",
        detail: { outcome },
        says: outcome === "pass" ? "Passed review" : "Failed review",
      });
    }

    render() {
      const outcome = this.state.review.detail?.outcome;
      const result =
        outcome === "pass"
          ? "Passed review"
          : outcome === "fail"
            ? "Failed review"
            : "Not reviewed";
      return html`
        <p
          class="review-result"
          data-outcome=${outcome ?? ""}
          data-lf-gen="1"
          data-lf-said
        >
          ${result}
        </p>
        ${
          quoted(this)
            ? ""
            : html`<div class="review-buttons">
                ${this.passButton}${this.failButton}
              </div>`
        }
      `;
    }
  },
);
