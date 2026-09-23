import { projectData, watchData, widgetController } from "/runtime/widget-api.js";

customElements.define(
  "lf-job-requests",
  class extends HTMLElement {
    connectedCallback() {
      this.controller ??= widgetController(this);
      this.stopReading ??= this.controller.subscribe(() => this.render());
      this.stopData ??= watchData(this, "jobs", (snapshot) => {
        this.snapshot = snapshot;
        this.render();
      });
    }

    disconnectedCallback() {
      this.stopReading?.();
      this.stopData?.();
      this.stopReading = null;
      this.stopData = null;
    }

    render() {
      const snapshot = this.snapshot;
      if (!snapshot) return;
      const reading = this.controller.read();
      projectData(
        this,
        snapshot.value.rows,
        (row) => row.id,
        (row, prior) => {
          const item = prior ?? document.createElement("p");
          if (!prior) {
            const label = document.createElement("strong");
            const button = document.createElement("button");
            button.type = "button";
            button.className = "lf-btn lf-ui";
            button.textContent = "Restart";
            item.append(label, " · ", button);
          }
          item.querySelector("strong").textContent = `${row.id} (${row.state})`;
          const button = item.querySelector("button");
          const seat = reading.requestUnits[row.id];
          button.disabled = seat?.phase !== "ready" ||
            seat.seat.data_revision !== snapshot.revision;
          button.onclick = () => this.controller.dispatch({
            kind: "request",
            verb: "restart",
            detail: { target: row.id, state: row.state },
            data_revision: snapshot.revision,
          });
          return item;
        },
        { snapshot },
      );
    }
  },
);
