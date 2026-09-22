/* lf-specimen: quoted content, or a complete live page authored in a template.
 * The shared host owns the child page and its independent event log. Entry is
 * explicit so a specimen cannot steal focus while the surrounding page loads.
 * Ordinary children remain static quotation. A disconnect releases the child;
 * moving the retained element within a document does not reset its work. */
import {
  mountSpecimen,
  once,
  offer,
  relabel,
  widgetController,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-specimen",
  class extends HTMLElement {
    #host;
    #frame;
    #template;
    #enter;
    #reset;
    #status;
    #active = false;
    #ready;
    #mounting = false;

    get ready() {
      return this.#ready;
    }

    connectedCallback() {
      if (once(this)) this.#build();
      if (!this.#frame || this.#host || this.#mounting) return;
      this.#mounting = true;
      const ready = mountSpecimen(this.#frame, { template: this.#template.id }).then(
        async (host) => {
          this.#mounting = false;
          if (!this.isConnected) {
            // Destroy cancels presentation; nobody awaits this removed element.
            host.ready.catch(() => {});
            await host.destroy();
            throw new DOMException("specimen disconnected", "AbortError");
          }
          this.#host = host;
          return host.ready;
        },
        (error) => {
          this.#mounting = false;
          throw error;
        },
      );
      widgetController(this).present(this.#track(ready));
    }

    disconnectedCallback() {
      queueMicrotask(() => {
        if (this.isConnected || !this.#host) return;
        const host = this.#host;
        this.#host = null;
        host.destroy().catch((error) => this.#failure(error));
      });
    }

    #build() {
      this.#template = this.querySelector(":scope > template[data-specimen]");
      if (!this.#template) return;
      this.dataset.lfSpecimenLive = "";
      this.#frame = document.createElement("iframe");
      this.#frame.className = "lf-specimen-frame";
      this.#frame.title = this.getAttribute("label") || "Leaf specimen";
      this.#frame.addEventListener("lf-specimen-enter", () => this.#entered(true));
      this.#frame.addEventListener("lf-specimen-leave", () => this.#entered(false));

      const controls = document.createElement("div");
      controls.className = "lf-specimen-controls lf-ui";
      controls.dataset.lfGen = "1";
      const actions = document.createElement("div");
      this.#enter = offer("button", "lf-btn", "Enter specimen");
      this.#enter.addEventListener("click", () => {
        if (this.#active) this.#host.leave();
        else this.#host.enter(this.#enter);
      });
      this.#reset = offer("button", "lf-btn", "Reset");
      this.#reset.addEventListener("click", () => {
        this.reset().catch(() => {}); // #track paints the failed operation.
      });
      this.#status = offer("span", "lf-specimen-status");
      this.#status.setAttribute("role", "status");
      actions.append(this.#enter, this.#reset, this.#status);
      controls.append(actions);
      this.append(controls, this.#frame);
    }

    #entered(active) {
      this.#active = active;
      relabel(this.#enter, active ? "Return to page" : "Enter specimen", {
        says: false,
      });
      this.#status.textContent = active
        ? "Escape returns to this page after closing open controls."
        : "Changes stay in this specimen.";
    }

    #failure(error) {
      if (error.name === "AbortError") return;
      this.#status.textContent = error.message;
      this.#enter.disabled = true;
      this.#reset.disabled = false;
    }

    #track(promise) {
      this.#enter.disabled = true;
      this.#reset.disabled = true;
      this.#status.textContent = "Loading specimen…";
      const ready = promise.then((doc) => {
        if (this.#ready !== ready) return doc;
        this.#enter.disabled = false;
        this.#reset.disabled = false;
        this.#entered(false);
        return doc;
      });
      this.#ready = ready;
      ready.catch((error) => {
        if (this.#ready === ready) this.#failure(error);
      });
      return this.#ready;
    }

    async reset() {
      if (this.#mounting) await this.#ready;
      if (!this.#host) {
        this.connectedCallback();
        return this.#ready;
      }
      return this.#track(this.#host.reset());
    }

    async lfPrepareExport() {
      await this.#ready;
      if (this.#frame) this.querySelector(":scope > .lf-specimen-controls").remove();
    }
  },
);
