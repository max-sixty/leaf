/* An anonymous report consumer keeps clock and report identity tests independent
 * of the Atlas example's composition. */
import {
  ago,
  clocked,
  html,
  keeps,
  once,
  quietSince,
  render,
  saidAt,
  updateSequence,
  watchOwner,
  watchUpdates,
  widgetController,
} from "/runtime/widget-api.js";
customElements.define(
  "lf-test-worker",
  class extends HTMLElement {
    #controller = widgetController(this);
    connectedCallback() {
      if (!once(this)) return;
      this.line = document.createElement("div");
      this.line.dataset.lfGen = "1";
      this.append(this.line);
      watchOwner(this, {
        connect: () => (this.paint = clocked(this, () => this.show())),
        disconnect: () => this.paint.stop(),
      });
      this.#controller.subscribe(() => {});
      watchUpdates(this, () => this.paint());
    }
    renderState(state) {
      keeps(this, "state", state.state.value);
    }
    show() {
      const reports = updateSequence(this).filter(
        (row) => row.source === "report" && row.action === "state",
      );
      const heard = reports.at(-1)?.ts ?? saidAt(this);
      const current = reports.findLast((row) => row.disposition === "effective");
      const state = this.#controller.read().state.state.value;
      render(
        html`<span class="lf-state">${state}</span>
          ${current?.text ? html`<span class="lf-doing">${current.text}</span>` : ""}
          ${["working", "waiting"].includes(state) && quietSince(heard) ? html`<span class="lf-cold">quiet</span>` : ""}
          <span class="lf-heard">last heard ${ago(heard)}</span>`,
        this.line,
      );
    }
  },
);
