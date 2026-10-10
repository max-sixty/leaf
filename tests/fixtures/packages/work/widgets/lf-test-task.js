/* A local consumer exercises declaration-driven reports without shipping a task UI. */
import {
  declarationFor,
  matchesWhen,
  threadBox,
  keeps,
  keepsText,
  once,
  readWork,
  watchUpdates,
  widgetController,
  workAncestor,
} from "/runtime/widget-api.js";
customElements.define(
  "lf-test-task",
  class extends HTMLElement {
    #controller = widgetController(this);
    connectedCallback() {
      if (!once(this)) return;
      keeps(this, "role", "group");
      this.ariaLabelledByElements = [this.querySelector(":scope > strong")].filter(
        Boolean,
      );
      this.statusLine =
        this.querySelector(':scope > [data-lf-said="status"]') ??
        document.createElement("span");
      this.statusLine.className = "work-state";
      this.statusLine.dataset.lfGen = "1";
      this.statusLine.dataset.lfSaid = "status";
      this.append(this.statusLine);
      this.progress = document.createElement("output");
      this.progress.className = "work-progress";
      this.progress.dataset.lfGen = "1";
      this.append(this.progress);
      const seat = declarationFor(this, "x-thread-seat");
      if (seat && matchesWhen(this, seat.when)) {
        const thread = threadBox(this, "Say something here");
        if (thread) this.append(thread);
      }
      this.#controller.subscribe(() => {});
      watchUpdates(this, () => {
        const row = readWork(
          workAncestor(this, "scope") ?? this.parentElement,
        ).goals.find((row) => row.element === this);
        keepsText(this.progress, `${row.finished}/${row.leaves.length} done`);
      });
    }
    renderState(state) {
      keeps(this, "status", state.status.value);
      keepsText(this.statusLine, state.status.value ?? "");
    }
  },
);
