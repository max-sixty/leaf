/* Every task is a named group, so its authored nesting is also its accessible
 * hierarchy. Its own title supplies the name directly, including later text edits;
 * status, prose, controls and child tasks remain readable inside that group.
 * Generic task rows retain their compact chip projection. A command surface owns its
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

    connectedCallback() {
      if (!once(this)) return;
      this.setAttribute("role", "group");
      const title = this.querySelector(":scope > strong");
      if (title) this.ariaLabelledByElements = [title];
      if (!closestCommandRole(this.parentElement, "command")) renderChips(this);
      this.#controller.subscribe(() => {});
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
