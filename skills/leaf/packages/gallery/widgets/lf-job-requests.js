import { projectData, watchData, widgetController } from "/runtime/widget-api.js";

customElements.define(
  "lf-job-requests",
  class extends HTMLElement {
    connectedCallback() {
      this.controller ??= widgetController(this);
      this.seats ??= new Map();
      this.stopData ??= watchData(this, "jobs", (snapshot) => {
        this.snapshot = snapshot;
        this.render();
      });
    }

    disconnectedCallback() {
      this.stopData?.();
      this.stopData = null;
      for (const stop of this.seats?.values() ?? []) stop();
      this.seats?.clear();
    }

    render() {
      const snapshot = this.snapshot;
      if (!snapshot) return;
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
          const seat = this.controller.request(row.id);
          const paint = (reading) => {
            button.disabled =
              !reading.requests.restart.available ||
              reading.request?.seat.data_revision !== snapshot.revision;
          };
          this.seats.get(row.id)?.();
          this.seats.set(row.id, seat.subscribe(paint));
          paint(seat.read());
          button.onclick = () =>
            seat.dispatch({
              kind: "request",
              verb: "restart",
              detail: { target: row.id, state: row.state },
            });
          return item;
        },
        { snapshot },
      );
      for (const [key, stop] of this.seats) {
        if (snapshot.value.rows.some((row) => row.id === key)) continue;
        stop();
        this.seats.delete(key);
      }
    }
  },
);
