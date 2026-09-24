/* Where a command's readings stand when the page puts them beside its tree. The element
 * is a seat: the lf-command it names renders the outcome, stopped-work, and fleet panels
 * into it (lf-command.js, `home`), because the command owns the snapshot, the focus
 * repair across repaints, and the views its counts open. Being an upgraded element is
 * what fences those generated words from the authored grid around them. */
import { once } from "/runtime/widget-api.js";

customElements.define(
  "lf-command-readings",
  class extends HTMLElement {
    connectedCallback() {
      once(this);
    }
  },
);
