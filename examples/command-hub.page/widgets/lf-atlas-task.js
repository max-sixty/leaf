/* Atlas task rows keep their authored hierarchy and report identity. */
import {
  declarationFor,
  matchesWhen,
  threadBox,
  keeps,
  keepsText,
  once,
  widgetController,
} from "/runtime/widget-api.js";
customElements.define(
  "lf-atlas-task",
  class extends HTMLElement {
    #controller = widgetController(this);
    connectedCallback() {
      if (!once(this)) return;
      keeps(this, "role", "group");
      this.ariaLabelledByElements = [this.querySelector(":scope > strong")];
      const status =
        this.querySelector(':scope > [data-lf-said="status"]') ??
        document.createElement("p");
      status.className = "atlas-task-state";
      status.dataset.lfGen = "1";
      status.dataset.lfSaid = "status";
      this.prepend(status);
      this.statusLine = status;
      const seat = declarationFor(this, "x-thread-seat");
      if (seat && matchesWhen(this, seat.when)) {
        const thread = threadBox(this, "Say something here");
        if (thread) this.append(thread);
      }
      this.#controller.subscribe(() => {});
    }
    renderState(state) {
      const status = state.status.value;
      keeps(this, "status", status);
      keepsText(this.statusLine, status);
    }
  },
);
