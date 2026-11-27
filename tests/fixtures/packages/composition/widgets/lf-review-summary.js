import { html } from "/vendor/lit.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { el } from "/runtime/lib/elements.js";
import { offer } from "/runtime/lib/controls.js";

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
      if (this.matches("[data-lf-exhibit] *")) return;
      this.lfCommands = {
        title: "Review result",
        rows: [
          {
            id: "review.pass",
            title: "Pass review",
            keys: ["p"],
            control: this.passButton,
            bindingBadge: null,
            when: () => this.state.review.available,
            run: () => this.review("pass"),
          },
          {
            id: "review.fail",
            title: "Fail review",
            keys: ["f"],
            control: this.failButton,
            bindingBadge: null,
            when: () => this.state.review.available,
            run: () => this.review("fail"),
          },
        ],
      };
      this.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
    }

    review(outcome) {
      return this.record(
        "review",
        { outcome },
        { says: outcome === "pass" ? "Passed review" : "Failed review" },
      );
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
          this.matches("[data-lf-exhibit] *")
            ? ""
            : html`<div class="review-buttons">
                ${this.passButton}${this.failButton}
              </div>`
        }
      `;
    }
  },
);
