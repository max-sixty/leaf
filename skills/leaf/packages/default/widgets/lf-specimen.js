/* lf-specimen: quoted content, or a complete live page authored in a template.
 * The shared host owns the child page and its independent event log. The frame
 * takes its child's height, so the surrounding page scrolls the specimen like any
 * other block and focus moves into it the way it moves into any iframe; the child's
 * final Escape brings focus back to this element. Ordinary children remain static
 * quotation. A disconnect releases the child; moving the retained element within a
 * document does not reset its work. */
import {
  cancelRender,
  mountSpecimen,
  nextRender,
  once,
  offer,
  widgetController,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-specimen",
  class extends HTMLElement {
    #host;
    #frame;
    #template;
    #reset;
    #status;
    #fit;
    #fitting = 0;
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
        cancelRender(this.#fitting);
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
      this.#frame.addEventListener("lf-specimen-return", () => {
        this.tabIndex = -1;
        this.focus({ preventScroll: true });
      });

      const controls = document.createElement("div");
      controls.className = "lf-specimen-controls lf-ui";
      controls.dataset.lfGen = "1";
      const actions = document.createElement("div");
      this.#reset = offer("button", "lf-btn", "Reset");
      this.#reset.addEventListener("click", () => {
        this.reset().catch(() => {}); // #track paints the failed operation.
      });
      this.#status = offer("span", "lf-specimen-status");
      this.#status.setAttribute("role", "status");
      actions.append(this.#reset, this.#status);
      controls.append(actions);
      this.append(controls, this.#frame);
    }

    // The frame's height follows its child's page, so nothing scrolls inside it. The
    // write waits a frame: the new height relays out the containing page, which can
    // reach the child's body again inside the observation that asked for it. The observer
    // is the child's own, watching its own body; the write it queues is this page's, and
    // this page's settled reading counts it. A reset replaces the child, so it cancels
    // the write the last child queued.
    #follow(doc) {
      this.#fit?.disconnect();
      cancelRender(this.#fitting);
      const frame = this.#frame;
      const view = doc.defaultView;
      const size = () => {
        cancelRender(this.#fitting);
        this.#fitting = nextRender(() => {
          const border = frame.offsetHeight - frame.clientHeight;
          const height = `${Math.ceil(doc.body.getBoundingClientRect().height) + border}px`;
          if (frame.style.height !== height) frame.style.height = height;
        });
      };
      this.#fit = new view.ResizeObserver(size);
      this.#fit.observe(doc.body);
    }

    #failure(error) {
      if (error.name === "AbortError") return;
      this.#status.textContent = error.message;
      this.#reset.disabled = false;
    }

    #track(promise) {
      this.#reset.disabled = true;
      this.#status.textContent = "Loading specimen…";
      const ready = promise.then((doc) => {
        if (this.#ready !== ready) return doc;
        this.#reset.disabled = false;
        this.#status.textContent = "";
        this.#follow(doc);
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
  },
);
