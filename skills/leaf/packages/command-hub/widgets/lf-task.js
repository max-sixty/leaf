/* Generic task rows retain their compact chip projection. A command surface owns its
 * richer row projection at the root, so ordinary task trees never inherit fleet UI. */
import { once, widgetController } from "/runtime/widget-api.js";
import { closestCommandRole } from "/widgets/command-model.js";

function renderChips(task) {
  task.querySelector(":scope > .lf-chips[data-lf-gen]")?.remove();
  const labels = [
    task.getAttribute("owner"),
    task.getAttribute("when"),
    ...(task.getAttribute("tags")?.split(",") ?? []),
  ].filter(Boolean);
  const leaves = [...task.querySelectorAll("lf-task")].filter(
    (item) => !item.querySelector("lf-task"),
  );
  if (leaves.length) {
    const done = leaves.filter((item) => item.getAttribute("status") === "done").length;
    labels.push(`${done}/${leaves.length} done`);
  }
  if (!labels.length) return;
  const row = document.createElement("div");
  row.className = "lf-chips";
  row.dataset.lfGen = "1";
  for (const label of labels)
    row.append(Object.assign(document.createElement("span"), { textContent: label }));
  const title = task.querySelector(":scope > strong");
  if (title) title.after(row);
  else task.prepend(row);
}

customElements.define(
  "lf-task",
  class extends HTMLElement {
    #controller = widgetController(this);
    #stop = null;

    connectedCallback() {
      if (once(this) && !closestCommandRole(this.parentElement, "command"))
        renderChips(this);
      this.#stop ??= this.#controller.subscribe(() => {});
    }

    disconnectedCallback() {
      this.#stop?.();
      this.#stop = null;
    }

    renderState(state) {
      const value = state.status.value;
      if (value === this.getAttribute("status")) return;
      if (value === null) this.removeAttribute("status");
      else this.setAttribute("status", value);
      if (closestCommandRole(this.parentElement, "command")) return;
      for (const task of this.closest("lf-tasks").querySelectorAll("lf-task"))
        renderChips(task);
    }
  },
);
