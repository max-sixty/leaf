/* The ordinary task collection names the hierarchy its task groups express.
 * Group semantics preserve each task's prose and native controls without imposing
 * the keyboard model of an interactive tree or moving any authored nodes. */
import { once } from "/runtime/widget-api.js";

customElements.define(
  "lf-tasks",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      this.setAttribute("role", "group");
      this.setAttribute("aria-label", "Tasks");
    }
  },
);
