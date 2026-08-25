/* Generic task rows retain their compact chip projection. A command surface owns its
 * richer row projection at the root, so ordinary task trees never inherit fleet UI. */
import { once } from "/leaf.js";
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
    connectedCallback() {
      if (!once(this)) return;
      if (!closestCommandRole(this.parentElement, "command")) renderChips(this);
    }

    applyAction(action, detail) {
      if (action !== "status") return;
      this.setAttribute("status", detail.status);
      if (closestCommandRole(this.parentElement, "command")) return;
      for (const task of this.closest("lf-tasks").querySelectorAll("lf-task"))
        renderChips(task);
    }
  },
);
