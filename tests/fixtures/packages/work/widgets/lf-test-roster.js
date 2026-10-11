import { keeps, once } from "/runtime/widget-api.js";
export default class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    keeps(this, "role", "group");
    keeps(this, "aria-label", this.getAttribute("label") ?? "Workers");
  }
}
