/* lf-sample: quoted content, or a complete live page authored in a template.
 * The shared host owns the child page and its independent event log. The frame
 * takes its child's height, so the surrounding page scrolls the sample like any
 * other block and focus moves into it the way it moves into any iframe. A `window`
 * sample is instead a whole Leaf window at the frame's own height, chrome included,
 * and scrolls inside itself. The child's
 * final Escape brings focus back to this element. Full view promotes the same frame
 * into a native modal dialog, keeping its document, gestures, and drafts alive. The
 * sample retains its embedded allocation while the dialog fills the viewport; Return
 * to page and the child's final Escape restore the Full view button. Each child announces
 * lf-sample-ready with its sample element, on first mount and Reset. Reset stays focusable
 * while loading but accepts no new press, preserving the parent's keyboard position.
 * Ordinary children remain static
 * quotation. A disconnect releases the child; moving the retained element within a
 * document does not reset its work. */
import {
  cancelRender,
  nextRender,
  keeps,
  mountSample,
  once,
  offer,
  widgetController,
  focusDestination,
  closeLayer,
  showNativeLayer,
  closeNativeLayer,
  handBack,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-sample",
  class extends HTMLElement {
    #host;
    #frame;
    #template;
    #reset;
    #status;
    #heightReading;
    #fitting = 0;
    #ready;
    #mounting = false;
    #viewOperation;
    #view;
    #full;

    get ready() {
      return this.#ready;
    }

    connectedCallback() {
      if (once(this)) this.#build();
      // Removal ends native modality even when a retained widget reconnects before
      // its host is retired. Reconcile the presentation with that platform state.
      if (
        this.#view?.getAttribute("role") === "dialog" &&
        !this.#view.matches(":modal")
      )
        this.#embed();
      if (!this.#frame || this.#host || this.#mounting) return;
      this.#mounting = true;
      const ready = mountSample(this.#frame, {
        template: this.#template.id,
        window: this.hasAttribute("window") || this.#view.matches(":modal"),
      }).then(
        async (host) => {
          this.#mounting = false;
          if (!this.isConnected) {
            // Destroy cancels presentation; nobody awaits this removed element.
            host.ready.catch(() => {});
            await host.destroy();
            throw new DOMException("sample disconnected", "AbortError");
          }
          this.#host = host;
          host.on("height", ({ height }) => this.#height(height));
          host.on("loading", () => this.#track(host.ready));
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
        if (this.isConnected) return;
        if (this.#view?.getAttribute("role") === "dialog") this.#embed();
        this.#viewOperation?.abort();
        if (!this.#host) return;
        const host = this.#host;
        this.#host = null;
        cancelRender(this.#fitting);
        host.destroy().catch((error) => this.#failure(error));
      });
    }

    #build() {
      this.#template = this.querySelector(":scope > template[data-sample]");
      if (!this.#template) return;
      this.dataset.lfSampleLive = "";
      this.#frame = document.createElement("iframe");
      this.#frame.className = "lf-sample-frame";
      this.#frame.title = this.getAttribute("label") || "Leaf sample";
      this.#frame.addEventListener("lf-sample-return", () => {
        if (this.#view.matches(":modal")) this.#return();
        else focusDestination(this, "return");
      });

      this.#view = document.createElement("dialog");
      this.#view.className = "lf-sample-view";
      this.#view.setAttribute("open", "");
      this.#view.setAttribute("role", "presentation");
      this.#view.addEventListener("cancel", (event) => {
        event.preventDefault();
        this.#return();
      });

      const controls = document.createElement("div");
      controls.className = "lf-sample-controls lf-ui";
      controls.dataset.lfGen = "1";
      const actions = document.createElement("div");
      this.#reset = offer("button", "lf-btn", "Reset");
      this.#reset.addEventListener("click", () => {
        if (this.#reset.ariaDisabled === "true") return;
        this.reset().catch(() => {}); // #track paints the failed operation.
      });
      this.#status = offer("span", "lf-sample-status");
      this.#status.setAttribute("role", "status");
      this.#full = offer("button", "lf-btn", "Full view");
      this.#full.addEventListener("click", () => {
        if (this.#view.matches(":modal")) this.#return();
        else {
          // The frame never moves in the DOM: reparenting it destroys its browsing
          // context. Native modality supplies focus containment and parent isolation.
          // The label stays in flow; reserve only the controls and frame leaving it.
          const height =
            this.#frame.getBoundingClientRect().bottom -
            controls.getBoundingClientRect().top;
          this.style.setProperty("--lf-sample-height", `${height}px`);
          closeNativeLayer(this.#view);
          this.#view.setAttribute("role", "dialog");
          this.#view.setAttribute("aria-label", this.#frame.title);
          this.#full.textContent = "Return to page";
          showNativeLayer(this.#view);
          this.#setWindow(true);
          focusDestination(this.#full, "move");
        }
      });
      actions.append(this.#reset, this.#full, this.#status);
      controls.append(actions);
      this.#view.append(controls, this.#frame);
      this.append(this.#view);
    }

    #return() {
      closeLayer(
        () => this.#embed(),
        () => handBack(this.#full),
      );
      if (this.#heightReading !== undefined)
        this.#height(this.#heightReading, { immediate: true });
    }

    #embed() {
      closeNativeLayer(this.#view);
      // Initial open markup keeps the embedded group visible without the native
      // focusing steps of show(), which could scroll the containing page.
      this.#view.setAttribute("open", "");
      this.#view.setAttribute("role", "presentation");
      this.#view.removeAttribute("aria-label");
      this.style.removeProperty("--lf-sample-height");
      this.#full.textContent = "Full view";
      this.#setWindow(this.hasAttribute("window"));
    }

    #setWindow(value) {
      this.#host?.setWindow(value).then(
        ({ height }) => this.#height(height),
        (error) => this.#failure(error),
      );
    }

    // The child owns its body observer and reports values over the private port.
    // Full view retains the embedded height while its same frame fills the dialog;
    // returning applies the current block reading without replacing any native editor.
    #height(height, { immediate = false } = {}) {
      if (this.hasAttribute("window") || this.#view.matches(":modal")) return;
      this.#heightReading = height;
      cancelRender(this.#fitting);
      const fit = () => {
        const frame = this.#frame;
        const next = `${this.#heightReading + frame.offsetHeight - frame.clientHeight}px`;
        if (frame.style.height !== next) frame.style.height = next;
      };
      if (immediate) fit();
      else this.#fitting = nextRender(fit);
    }

    #failure(error) {
      if (error.name === "AbortError") return;
      this.#status.textContent = error.message;
      keeps(this.#reset, "aria-disabled", null);
    }

    #track(promise) {
      keeps(this.#reset, "aria-disabled", "true");
      this.#status.textContent = "Loading sample…";
      const ready = promise.then(async (reading) => {
        if (this.#ready !== ready) return reading;
        const current = await this.#host.setWindow(
          this.hasAttribute("window") || this.#view.matches(":modal"),
        );
        if (this.#ready !== ready) return reading;
        this.#height(current.height, { immediate: true });
        keeps(this.#reset, "aria-disabled", null);
        this.#status.textContent = "";
        this.dispatchEvent(
          new CustomEvent("lf-sample-ready", {
            bubbles: true,
            detail: { sample: this },
          }),
        );
        return reading;
      });
      this.#ready = ready;
      ready.catch((error) => {
        if (this.#ready === ready) this.#failure(error);
      });
      return this.#ready;
    }

    // Latest selection wins, including a selection waiting on a replacement child.
    // The outer control remains the keyboard stop while the child draws its view.
    async showThread(id, { surface = "page", status, waiting } = {}) {
      this.#viewOperation?.abort();
      const operation = new AbortController();
      this.#viewOperation = operation;
      const { signal } = operation;
      const ready = this.#ready;
      let cancelled;
      const cancellation = new Promise((resolve) => {
        cancelled = () => resolve(false);
        signal.addEventListener("abort", cancelled, { once: true });
      });
      const select = async () => {
        if (signal.aborted || ready !== this.#ready || !this.isConnected) return false;
        const shown = await this.#host.showThread(id, {
          surface,
          status,
          waiting,
          signal,
        });
        if (signal.aborted || ready !== this.#ready || !this.isConnected) return false;
        return shown;
      };
      try {
        return await Promise.race([ready.then(select), cancellation]);
      } finally {
        signal.removeEventListener("abort", cancelled);
      }
    }

    async reset() {
      this.#viewOperation?.abort();
      if (this.#mounting) await this.#ready;
      if (!this.#host) {
        this.connectedCallback();
        return this.#ready;
      }
      return this.#track(this.#host.reset());
    }
  },
);
