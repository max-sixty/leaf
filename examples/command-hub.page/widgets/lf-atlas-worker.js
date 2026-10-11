/* Atlas owns roster composition. A visible report keeps its reading until the
 * user asks for updates, while identity and state come from the public projection. */
import {
  ago,
  HeldReading,
  html,
  keeps,
  keepsText,
  once,
  readWork,
  render,
  updateSequence,
  watchOwner,
  watchUpdates,
  widgetController,
  workAncestor,
} from "/runtime/widget-api.js";
customElements.define(
  "lf-atlas-worker",
  class extends HTMLElement {
    #controller = widgetController(this);
    pending = false;
    connectedCallback() {
      if (!once(this)) return;
      if (!this.querySelector("details")) {
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        summary.append(
          this.querySelector(":scope > strong"),
          Object.assign(document.createElement("span"), {
            className: "atlas-worker-state",
            role: "status",
          }),
        );
        const body = document.createElement("div");
        body.className = "atlas-worker-body";
        body.append(
          Object.assign(document.createElement("p"), {
            className: "atlas-worker-report",
          }),
          ...this.childNodes,
        );
        details.append(summary, body);
        this.append(details);
      }
      this.reading = new HeldReading(
        () => [this.querySelector(".atlas-worker-body")],
        () => this.watching.refresh(),
      );
      watchOwner(this, { disconnect: () => this.reading.dispose() });
      this.#controller.subscribe(() => {});
      this.watching = watchUpdates(this, () => this.paint());
    }
    renderState(state) {
      keeps(this, "state", state.state.value);
    }
    paint() {
      const worker = readWork(workAncestor(this, "scope")).workers.find(
        (row) => row.element === this,
      );
      const report = updateSequence(this).findLast(
        (row) => row.source === "report" && row.disposition === "effective",
      );
      keepsText(
        this.querySelector(".atlas-worker-state"),
        `${worker.state}${worker.quiet ? " · quiet" : ""}`,
      );
      const next = JSON.stringify({
        heard: worker.heard,
        text: report?.text ?? "No report yet.",
      });
      const shown = this.reading.hold(next);
      const reading = JSON.parse(shown);
      render(
        html`${reading.text}${
          reading.heard
            ? html` Last heard
                <time datetime=${reading.heard} title=${reading.heard}
                  >${ago(reading.heard)}</time
                >`
            : ""
        }`,
        this.querySelector(".atlas-worker-report"),
      );
      if (this.pending !== (next !== shown)) {
        this.pending = next !== shown;
        this.dispatchEvent(new CustomEvent("atlas-reading", { bubbles: true }));
      }
    }
    showUpdates() {
      this.reading.show();
    }
  },
);
