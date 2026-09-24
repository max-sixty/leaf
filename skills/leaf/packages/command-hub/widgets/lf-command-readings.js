/* Where a command's readings stand when the page puts them beside its tree. The element
 * is a seat: the lf-command it names renders the outcome, stopped-work, and fleet panels
 * into it (lf-command.js, `home`), because the command owns the snapshot, the focus
 * repair across repaints, and the views its counts open. Being an upgraded element is
 * what fences those generated words from the authored grid around them.
 *
 * The seat tells its command when it connects and disconnects, so the command moves its
 * panels in or back to its own head then, rather than at the next state reading. The
 * command is looked up in the seat's own authored document, the one it was in when it
 * connected, since a disconnected seat no longer has one. */
import { authoredScope, once } from "/runtime/widget-api.js";

customElements.define(
  "lf-command-readings",
  class extends HTMLElement {
    #scope = null;

    connectedCallback() {
      once(this);
      this.#scope = authoredScope(this);
      this.#command()?.reseat?.();
    }

    disconnectedCallback() {
      this.#command()?.reseat?.();
      this.#scope = null;
    }

    // `reseat` is absent while the command's module has not upgraded it yet; the
    // command finds its seat itself on its first paint.
    #command() {
      return this.#scope.querySelector(`lf-command[id="${this.getAttribute("for")}"]`);
    }
  },
);
